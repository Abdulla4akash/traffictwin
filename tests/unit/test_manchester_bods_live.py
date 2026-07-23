"""Offline tests for the explicit BODS-to-live-map vertical slice."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import httpx
import pytest

import traffictwin.integration.manchester.bods_live as live
from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    make_clock,
    make_transport,
    siri_xml,
)
from traffictwin.integration.manchester.bods_live import (
    BODS_LIVE_SCENE_RELATIVE_PATH,
    BodsLiveWorkflowError,
    build_bods_live_scene,
    refresh_bods_live_scene,
)
from traffictwin.integration.manchester.map_layers import ManchesterMapScene
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene


def _refresh(workspace: Path) -> tuple[live.BodsLiveRefresh, list[tuple[str, str, dict[str, str]]]]:
    calls: list[tuple[str, str, dict[str, str]]] = []
    with httpx.Client(transport=make_transport(siri_xml(), calls)) as client:
        result = refresh_bods_live_scene(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=make_clock(),
        )
    return result, calls


def test_explicit_refresh_publishes_private_validated_local_scene(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path

    result, calls = _refresh(workspace)

    assert len(calls) == 1
    assert calls[0][2]["api_key"] == API_KEY
    assert result.summary.records_accepted == 2
    assert result.summary.synthetic_records == 2
    assert result.summary.live_vehicle == 0
    assert result.summary.transit_live_available is False
    assert result.summary.road_traffic_live_available is False
    assert result.summary.public_export_available is False
    assert result.scene.mode == "live_vehicles"
    assert result.scene.layers[0].request.publication_class.value == "private"
    assert result.scene.layers[0].request.source == "bods_siri_vm"
    assert result.scene.layers[0].freshness_truth_state == "synthetic"

    target = workspace / BODS_LIVE_SCENE_RELATIVE_PATH
    assert target.is_file() and not target.is_symlink()
    assert target.stat().st_mode & 0o777 == 0o600
    persisted = ManchesterMapScene.model_validate_json(target.read_bytes())
    assert persisted == result.scene
    assert result.summary.scene_fingerprint == persisted.fingerprint()
    assert result.summary.scene_file_sha256 == sha256(target.read_bytes()).hexdigest()

    loaded = load_local_manchester_scene(workspace, "live_vehicles")
    assert loaded.status == "available"
    assert loaded.scene == persisted
    for artifact in workspace.rglob("*"):
        if artifact.is_file() and not artifact.is_symlink():
            assert API_KEY.encode() not in artifact.read_bytes()


def test_refresh_refuses_unmarked_workspace_before_transport(tmp_path: Path) -> None:
    workspace = tmp_path / "ordinary-directory"
    workspace.mkdir()
    calls: list[tuple[str, str, dict[str, str]]] = []
    with (
        httpx.Client(transport=make_transport(siri_xml(), calls)) as client,
        pytest.raises(BodsLiveWorkflowError) as excinfo,
    ):
        refresh_bods_live_scene(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=make_clock(),
        )
    assert excinfo.value.code == "WORKSPACE_INVALID"
    assert calls == []
    assert API_KEY not in str(excinfo.value)


def test_scene_publication_failure_preserves_previous_scene(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result, _calls = _refresh(workspace)
    target = workspace / BODS_LIVE_SCENE_RELATIVE_PATH
    before = target.read_bytes()

    monkeypatch.setattr(live, "BODS_LIVE_SCENE_MAX_BYTES", 1)
    with pytest.raises(BodsLiveWorkflowError) as excinfo:
        live._publish_live_scene(workspace, result.scene.canonical_json().encode("utf-8"))
    assert excinfo.value.code == "SCENE_SIZE_REFUSED"
    assert target.read_bytes() == before


def test_scene_builder_rejects_report_drift(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result, _calls = _refresh(workspace)
    drifted = result.report.model_copy(update={"records": ()})

    with pytest.raises(BodsLiveWorkflowError) as excinfo:
        build_bods_live_scene(result.acquisition, drifted)
    assert excinfo.value.code == "PARSER_REPORT_MISMATCH"

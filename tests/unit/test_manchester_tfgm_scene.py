"""Offline tests for the accepted TfGM signal-to-MAN-08 scene bridge."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_map_layers import request as synthetic_layer_request
from tests.unit.test_manchester_tfgm_acquisition import acquire, make_request
from traffictwin.integration.manchester.scene_publication import (
    ManchesterScenePublicationRequest,
)
from traffictwin.integration.manchester.tfgm_acquisition import (
    TFGM_ZIP_MEMBER_PATH,
    TfgmAcquisitionResult,
)
from traffictwin.integration.manchester.tfgm_scene import (
    TFGM_SCENE_LAYER_ID,
    TfgmSceneError,
    TfgmSignalLayerSummary,
    build_tfgm_signal_layer,
    publish_tfgm_latest_scene,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene

EVALUATED_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _accepted(tmp_path: Path) -> tuple[Path, TfgmAcquisitionResult]:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    return workspace, acquire(workspace, make_request())


def test_accepted_snapshot_builds_private_static_reference_layer(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)

    built = build_tfgm_signal_layer(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.records_accepted == 3
    assert built.summary.spatial_admitted == 3
    assert built.summary.spatial_excluded == 0
    assert built.summary.layer_status == "available"
    assert built.summary.publication_class == "private"
    assert built.summary.live_state_available is False
    assert built.summary.phase_available is False
    assert built.summary.traffic_count_available is False
    assert built.layer_request.layer_id == TFGM_SCENE_LAYER_ID
    assert built.layer_request.source == "tfgm_signals"
    assert built.layer_request.publication_class.value == "private"
    assert built.layer_request.freshness is not None
    assert built.layer_request.freshness.truth_state == "synthetic"
    assert built.layer_request.snapshot_fingerprint == acquisition.fingerprint()
    assert built.parser_report.fingerprint() == acquisition.parser_report_fingerprint
    assert all(record.live_state_available is False for record in built.parser_report.records)
    assert all(record.phase_available is False for record in built.parser_report.records)


def test_explicit_publication_populates_latest_available_scene(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)

    result = publish_tfgm_latest_scene(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
    )

    assert result.publication.scene.mode == "latest_available"
    assert result.publication.private_layer_present is True
    assert result.publication.public_export_performed is False
    assert result.publication.scene.visible_layer_ids == (TFGM_SCENE_LAYER_ID,)
    target = workspace / "manchester/scenes/latest_available.json"
    assert target.is_file()
    assert target.stat().st_mode & 0o777 == 0o600
    loaded = load_local_manchester_scene(workspace, "latest_available")
    assert loaded.status == "available"
    assert loaded.scene == result.publication.scene


def test_additional_layers_remain_separate_and_are_not_fused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    additional = synthetic_layer_request(layer_id="synthetic-context", title="Synthetic context")

    result = publish_tfgm_latest_scene(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
        additional_layer_requests=(additional,),
    )

    assert tuple(layer.request.layer_id for layer in result.publication.scene.layers) == (
        "synthetic-context",
        TFGM_SCENE_LAYER_ID,
    )
    assert result.publication.scene.source_fusion_performed is False
    assert result.publication.scene.cross_scope_totals_available is False
    assert result.publication.scene.scopes_treated_as_equal is False


def test_build_performs_no_network_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, acquisition = _accepted(tmp_path)

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("source-to-scene replay must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    built = build_tfgm_signal_layer(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 3


def test_unmarked_workspace_is_refused_before_snapshot_access(tmp_path: Path) -> None:
    _workspace, acquisition = _accepted(tmp_path)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    with pytest.raises(TfgmSceneError) as excinfo:
        build_tfgm_signal_layer(
            ordinary,
            acquisition,
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "WORKSPACE_INVALID"


def test_mutated_accepted_zip_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    target = workspace / "accepted" / acquisition.snapshot_id / "raw" / TFGM_ZIP_MEMBER_PATH
    target.chmod(0o600)
    target.write_bytes(target.read_bytes() + b"drift")

    with pytest.raises(TfgmSceneError) as excinfo:
        build_tfgm_signal_layer(
            workspace,
            acquisition,
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "ACCEPTED_SNAPSHOT_INVALID"


def test_mutated_parser_binding_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    drifted = acquisition.model_copy(update={"parser_report_fingerprint": "0" * 64})

    with pytest.raises(TfgmSceneError) as excinfo:
        build_tfgm_signal_layer(
            workspace,
            drifted,
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "PARSER_REPORT_MISMATCH"


def test_duplicate_tfgm_layer_cannot_be_published(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    built = build_tfgm_signal_layer(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
    )

    with pytest.raises(ValidationError, match="sorted unique"):
        ManchesterScenePublicationRequest(
            mode="latest_available",
            layer_requests=(built.layer_request, built.layer_request),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("records_accepted", 4),
        ("spatial_admitted", 2),
        ("spatial_excluded", 1),
        ("layer_status", "unavailable"),
        ("publication_class", "redistributable_derived"),
        ("live_state_available", True),
        ("traffic_count_available", True),
    ],
)
def test_summary_mutations_are_refused(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    workspace, acquisition = _accepted(tmp_path)
    summary = build_tfgm_signal_layer(
        workspace,
        acquisition,
        evaluated_at_utc=EVALUATED_AT,
    ).summary
    payload = json.loads(summary.model_dump_json())
    payload[field] = value

    with pytest.raises(ValidationError):
        TfgmSignalLayerSummary.model_validate(payload)

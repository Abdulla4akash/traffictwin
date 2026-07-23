"""Offline tests for bounded MAN-08 historical/latest scene publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_map_layers import request as layer_request
from traffictwin.integration.manchester.models import ManchesterPublicationClass
from traffictwin.integration.manchester.scene_publication import (
    ManchesterScenePublicationError,
    ManchesterScenePublicationReceipt,
    ManchesterScenePublicationRequest,
    publish_historical_scene,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene


def _workspace(tmp_path: Path) -> Path:
    return initialise_v07_workspace(tmp_path / "workspace-v0.7").path


def _request(**changes: object) -> ManchesterScenePublicationRequest:
    values: dict[str, object] = {
        "mode": "latest_available",
        "layer_requests": (layer_request(),),
    }
    values.update(changes)
    return ManchesterScenePublicationRequest.model_validate(values)


def test_latest_scene_is_published_to_fixed_private_local_file(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)

    receipt = publish_historical_scene(workspace, _request())

    target = workspace / "manchester/scenes/latest_available.json"
    assert target.is_file() and not target.is_symlink()
    assert target.stat().st_mode & 0o777 == 0o600
    assert receipt.file_publication.relative_path == target.relative_to(workspace).as_posix()
    assert receipt.file_publication.replaced_existing is False
    assert receipt.file_publication.public_export_performed is False
    assert receipt.scene.mode == "latest_available"
    assert receipt.scene_status == "available"
    assert receipt.public_export_performed is False
    assert (
        ManchesterScenePublicationReceipt.model_validate_json(receipt.model_dump_json()) == receipt
    )

    loaded = load_local_manchester_scene(workspace, "latest_available")
    assert loaded.status == "available"
    assert loaded.scene == receipt.scene


def test_historical_scene_uses_its_own_fixed_file(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    request = _request(
        mode="historical_replay",
        layer_requests=(layer_request(mode="historical_replay"),),
    )

    receipt = publish_historical_scene(workspace, request)

    assert receipt.file_publication.relative_path == ("manchester/scenes/historical_replay.json")
    assert (workspace / receipt.file_publication.relative_path).is_file()
    loaded = load_local_manchester_scene(workspace, "historical_replay")
    assert loaded.status == "available"
    assert loaded.scene == receipt.scene


def test_request_has_no_arbitrary_path_network_or_live_mode() -> None:
    fields = set(ManchesterScenePublicationRequest.model_fields)
    assert fields.isdisjoint({"path", "url", "host", "query", "timeout", "api_key"})

    with pytest.raises(ValidationError):
        _request(destination_path="elsewhere.json")
    with pytest.raises(ValidationError):
        _request(
            mode="live_vehicles",
            layer_requests=(layer_request(mode="live_vehicles"),),
        )


def test_request_refuses_unsorted_duplicates_and_cross_mode_layers() -> None:
    alpha = layer_request(layer_id="alpha", title="Alpha")
    beta = layer_request(layer_id="beta", title="Beta")

    with pytest.raises(ValidationError, match="sorted unique"):
        _request(layer_requests=(beta, alpha))
    with pytest.raises(ValidationError, match="sorted unique"):
        _request(layer_requests=(alpha, alpha))
    with pytest.raises(ValidationError, match="match the scene mode"):
        _request(layer_requests=(layer_request(mode="historical_replay"),))


def test_unmarked_workspace_is_refused_without_creating_scene(tmp_path: Path) -> None:
    workspace = tmp_path / "ordinary"
    workspace.mkdir()

    with pytest.raises(ManchesterScenePublicationError) as excinfo:
        publish_historical_scene(workspace, _request())

    assert excinfo.value.code == "WORKSPACE_INVALID"
    assert not (workspace / "manchester").exists()


def test_interrupted_replace_preserves_previous_scene(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = _workspace(tmp_path)
    first = publish_historical_scene(workspace, _request())
    target = workspace / first.file_publication.relative_path
    before = target.read_bytes()
    changed = _request(
        layer_requests=(layer_request(title="Changed synthetic layer"),),
    )

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("synthetic interrupted replacement")

    monkeypatch.setattr(
        "traffictwin.integration.manchester.scene_publication.os.replace",
        fail_replace,
    )
    with pytest.raises(ManchesterScenePublicationError) as excinfo:
        publish_historical_scene(workspace, changed)

    assert excinfo.value.code == "SCENE_PUBLICATION_FAILED"
    assert target.read_bytes() == before
    assert list(target.parent.glob(".latest_available-*")) == []


def test_target_symlink_is_refused_without_touching_external_file(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    target = workspace / "manchester/scenes/latest_available.json"
    target.parent.mkdir(parents=True)
    external = tmp_path / "external.json"
    external.write_text("unchanged", encoding="utf-8")
    target.symlink_to(external)

    with pytest.raises(ManchesterScenePublicationError) as excinfo:
        publish_historical_scene(workspace, _request())

    assert excinfo.value.code == "SCENE_PATH_REFUSED"
    assert external.read_text(encoding="utf-8") == "unchanged"


def test_parent_symlink_is_refused_before_creating_external_directories(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (workspace / "manchester/scenes").symlink_to(external, target_is_directory=True)

    with pytest.raises(ManchesterScenePublicationError) as excinfo:
        publish_historical_scene(workspace, _request())

    assert excinfo.value.code == "SCENE_PATH_REFUSED"
    assert list(external.iterdir()) == []


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("request_fingerprint",), "0" * 64),
        (("scene_fingerprint",), "1" * 64),
        (("file_publication", "file_sha256"), "2" * 64),
        (("file_publication", "byte_size"), 1),
        (("layer_count",), 2),
        (("visible_layer_count",), 0),
        (("scene_status",), "unavailable"),
        (("private_layer_present",), True),
    ],
)
def test_receipt_tampering_is_refused(
    tmp_path: Path,
    path: tuple[str, ...],
    value: object,
) -> None:
    receipt = publish_historical_scene(_workspace(tmp_path), _request())
    payload = json.loads(receipt.model_dump_json())
    cursor = payload
    for key in path[:-1]:
        cursor = cursor[key]
    cursor[path[-1]] = value

    with pytest.raises(ValidationError):
        ManchesterScenePublicationReceipt.model_validate(payload)


def test_private_layer_is_local_only_and_explicitly_reported(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    request = _request(
        layer_requests=(layer_request(publication_class=ManchesterPublicationClass.PRIVATE),),
    )

    receipt = publish_historical_scene(workspace, request)

    assert receipt.private_layer_present is True
    assert receipt.scene.layers[0].local_rendering_available is True
    assert receipt.scene.layers[0].public_export_available is False
    assert receipt.public_export_performed is False

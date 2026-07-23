"""Offline tests for the accepted DfT-count-point-to-MAN-08 scene bridge."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.unit.test_manchester_dft_acquisition import (
    acquire,
    count_point_row,
    envelope_bytes,
    make_request,
    raw_row,
)
from tests.unit.test_manchester_map_layers import request as synthetic_layer_request
from traffictwin.integration.manchester.dft_acquisition import DftAcquisitionResult
from traffictwin.integration.manchester.dft_scene import (
    DFT_COUNT_POINT_LAYER_ID,
    DftCountPointLayerSummary,
    DftSceneError,
    build_dft_count_point_layer,
    publish_dft_count_point_scene,
)
from traffictwin.integration.manchester.models import ManchesterPublicationClass
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.manchester_operations import load_local_manchester_scene

EVALUATED_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
MATCHED_COORDINATES = {
    "longitude": -2.2501081932913074,
    "latitude": 53.48295687253339,
}


def _acquire_count_points(
    workspace: Path,
    rows: list[dict[str, object]] | None = None,
    **request_overrides: object,
) -> DftAcquisitionResult:
    supplied = rows or [count_point_row(**MATCHED_COORDINATES)]
    page_size = len(supplied)
    result = acquire(
        workspace,
        {1: envelope_bytes(supplied, 1, 1, page_size, page_size)},
        make_request("count_points", page_size=page_size, **request_overrides),
    )
    assert isinstance(result, DftAcquisitionResult)
    return result


def _accepted(tmp_path: Path) -> tuple[Path, DftAcquisitionResult]:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    return workspace, _acquire_count_points(workspace)


def test_accepted_count_points_build_historical_reference_layer(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)

    built = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="historical_replay",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.layer_id == DFT_COUNT_POINT_LAYER_ID
    assert built.summary.records_accepted == 1
    assert built.summary.distinct_count_points == 1
    assert built.summary.spatial_admitted == 1
    assert built.summary.layer_status == "available"
    assert built.summary.raw_count_values_included is False
    assert built.summary.aadf_values_included is False
    assert built.summary.source_time_promoted_to_utc is False
    assert built.summary.live_road_traffic_available is False
    assert built.layer_request.source == "dft"
    assert built.layer_request.freshness is not None
    assert built.layer_request.freshness.truth_state == "synthetic"
    assert built.parser_report.fingerprint() == acquisition.parser_report_fingerprint


@pytest.mark.parametrize("mode", ["historical_replay", "latest_available"])
def test_explicit_publication_populates_fixed_scene(tmp_path: Path, mode: str) -> None:
    workspace, acquisition = _accepted(tmp_path)

    result = publish_dft_count_point_scene(
        workspace,
        acquisition,
        mode=mode,  # type: ignore[arg-type]
        evaluated_at_utc=EVALUATED_AT,
    )

    assert result.publication.scene.mode == mode
    assert result.publication.scene.visible_layer_ids == (DFT_COUNT_POINT_LAYER_ID,)
    loaded = load_local_manchester_scene(workspace, mode)
    assert loaded.scene == result.publication.scene


def test_additional_layer_stays_separate_without_scope_fusion(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    context = synthetic_layer_request(layer_id="synthetic-context", title="Synthetic context")

    result = publish_dft_count_point_scene(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
        additional_layer_requests=(context,),
    )

    assert tuple(layer.request.layer_id for layer in result.publication.scene.layers) == (
        DFT_COUNT_POINT_LAYER_ID,
        "synthetic-context",
    )
    assert result.publication.scene.source_fusion_performed is False
    assert result.publication.scene.cross_scope_totals_available is False
    assert result.publication.scene.scopes_treated_as_equal is False


def test_build_performs_no_network_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace, acquisition = _accepted(tmp_path)

    def refuse_socket(*_args: object, **_kwargs: object) -> socket.socket:
        raise AssertionError("accepted-count-point replay must not use the network")

    monkeypatch.setattr(socket, "socket", refuse_socket)
    built = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 1


def test_unmarked_workspace_is_refused_before_snapshot_access(tmp_path: Path) -> None:
    _workspace, acquisition = _accepted(tmp_path)
    ordinary = tmp_path / "ordinary"
    ordinary.mkdir()

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            ordinary,
            acquisition,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "WORKSPACE_INVALID"


def test_raw_counts_are_never_relabelled_as_reference_layer(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result = acquire(
        workspace,
        {1: envelope_bytes([raw_row()], 1, 1, 1, 1)},
        make_request("raw_counts"),
    )
    assert isinstance(result, DftAcquisitionResult)

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            workspace,
            result,
            mode="historical_replay",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "DATASET_REFUSED"


def test_mutated_accepted_page_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    target = workspace / "accepted" / acquisition.snapshot_id / "raw/pages/page-0001.json"
    target.chmod(0o600)
    target.write_bytes(target.read_bytes() + b"drift")

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            workspace,
            acquisition,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "ACCEPTED_SNAPSHOT_INVALID"


def test_mutated_parser_binding_is_refused(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    drifted = acquisition.model_copy(update={"parser_report_fingerprint": "0" * 64})

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            workspace,
            drifted,
            mode="latest_available",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "PARSER_REPORT_MISMATCH"


def test_publication_class_cannot_be_relabelled_after_acquisition(tmp_path: Path) -> None:
    workspace, acquisition = _accepted(tmp_path)
    request = acquisition.request.model_copy(
        update={"publication_class": ManchesterPublicationClass.REDISTRIBUTABLE_RAW}
    )
    drifted = acquisition.model_copy(update={"request": request})

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            workspace,
            drifted,
            mode="historical_replay",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "ACCEPTED_SNAPSHOT_MISMATCH"


def test_duplicate_count_point_identity_is_refused_not_arbitrated(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    rows = [
        count_point_row(**MATCHED_COORDINATES),
        count_point_row(id=502, aadf_year=2024, **MATCHED_COORDINATES),
    ]
    acquisition = _acquire_count_points(workspace, rows)

    with pytest.raises(DftSceneError) as excinfo:
        build_dft_count_point_layer(
            workspace,
            acquisition,
            mode="historical_replay",
            evaluated_at_utc=EVALUATED_AT,
        )

    assert excinfo.value.code == "COUNT_POINT_IDENTITY_CONFLICT"


def test_coordinate_mismatch_is_reconciled_as_unavailable(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    acquisition = _acquire_count_points(workspace, [count_point_row()])

    built = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 0
    assert built.summary.spatial_excluded == 1
    assert built.summary.layer_status == "unavailable"
    assert built.spatial_report.results[0].reason == "dual_coordinate_mismatch"


def test_partial_coordinate_admission_remains_visible_and_reconciled(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    rows = [
        count_point_row(**MATCHED_COORDINATES),
        count_point_row(id=502, count_point_id=54321, aadf_year=2025),
    ]
    acquisition = _acquire_count_points(workspace, rows)

    built = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.spatial_admitted == 1
    assert built.summary.spatial_excluded == 1
    assert built.summary.layer_status == "partial"


def test_public_export_follows_snapshot_publication_class(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    acquisition = _acquire_count_points(
        workspace,
        publication_class=ManchesterPublicationClass.REDISTRIBUTABLE_RAW,
    )

    built = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="historical_replay",
        evaluated_at_utc=EVALUATED_AT,
    )

    assert built.summary.publication_class is ManchesterPublicationClass.REDISTRIBUTABLE_RAW
    assert built.summary.public_export_available is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("records_accepted", 2),
        ("distinct_count_points", 2),
        ("spatial_admitted", 0),
        ("layer_status", "unavailable"),
        ("public_export_available", True),
        ("raw_count_values_included", True),
        ("aadf_values_included", True),
        ("source_time_promoted_to_utc", True),
        ("live_road_traffic_available", True),
        ("cross_source_join_performed", True),
    ],
)
def test_summary_mutations_are_refused(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    workspace, acquisition = _accepted(tmp_path)
    summary = build_dft_count_point_layer(
        workspace,
        acquisition,
        mode="latest_available",
        evaluated_at_utc=EVALUATED_AT,
    ).summary
    payload = json.loads(summary.model_dump_json())
    payload[field] = value

    with pytest.raises(ValidationError):
        DftCountPointLayerSummary.model_validate(payload)

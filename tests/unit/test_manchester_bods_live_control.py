"""Offline tests for operator-triggered BODS refresh coordination."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

import traffictwin.integration.manchester.bods_live_control as control
from tests.unit.test_manchester_bods_acquisition import (
    API_KEY,
    BOX,
    make_transport,
    siri_xml,
)
from traffictwin.integration.manchester.bods_live import BodsLiveWorkflowError
from traffictwin.integration.manchester.bods_live_control import (
    BODS_LIVE_CONTROL_RELATIVE_PATH,
    BodsLiveControlError,
    BodsLiveControlState,
    bods_live_history_rows,
    coordinated_bods_live_refresh,
    load_bods_live_control_state,
    project_bods_live_scene_for_display,
)
from traffictwin.integration.manchester.freshness import (
    FreshnessEvaluationRequest,
    evaluate_source_freshness,
)
from traffictwin.integration.manchester.map_layers import (
    MapLayerRequest,
    build_map_layer,
    build_map_scene,
)
from traffictwin.integration.manchester.models import (
    ManchesterPublicationClass,
    ManchesterValidationState,
)
from traffictwin.integration.manchester.spatial import (
    ManchesterSpatialPointEvidence,
    evaluate_spatial_batch,
)
from traffictwin.release.compatibility import initialise_v07_workspace


def _clock(start: datetime) -> Callable[[], datetime]:
    values = iter(start + timedelta(seconds=offset) for offset in range(100))
    return lambda: next(values)


def _run(workspace: Path, started_at: datetime) -> control.ControlledBodsLiveRefresh:
    calls: list[tuple[str, str, dict[str, str]]] = []
    with httpx.Client(transport=make_transport(siri_xml(), calls)) as client:
        result = coordinated_bods_live_refresh(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=_clock(started_at),
        )
    assert len(calls) == 1
    return result


def test_explicit_refresh_persists_only_bounded_aggregate_history(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path

    result = _run(workspace, datetime(2026, 7, 22, 10, tzinfo=UTC))

    state = load_bods_live_control_state(workspace)
    assert state == result.state
    assert state.attempts_total == 1
    assert state.successes_total == 1
    assert state.failures_total == 0
    assert state.last_attempt_status == "succeeded"
    assert state.latest_success == result.refresh.summary
    assert state.history == (result.refresh.summary,)
    assert state.policy.minimum_interval_seconds == 60
    assert state.policy.automatic_source_polling_available is False
    rows = bods_live_history_rows(state)
    assert rows[0]["Live buses"] == result.refresh.summary.live_vehicle
    assert rows[0]["Bee Network buses"] == result.refresh.summary.bee_network_franchised
    target = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    payload = target.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o600
    assert API_KEY.encode() not in payload
    assert b"VehicleRef" not in payload


def test_minimum_interval_blocks_transport_before_request(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    _run(workspace, datetime(2026, 7, 22, 10, tzinfo=UTC))
    calls: list[tuple[str, str, dict[str, str]]] = []
    with (
        httpx.Client(transport=make_transport(siri_xml(), calls)) as client,
        pytest.raises(BodsLiveControlError) as excinfo,
    ):
        coordinated_bods_live_refresh(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            http_client=client,
            utc_now=_clock(datetime(2026, 7, 22, 10, 0, 30, tzinfo=UTC)),
        )
    assert excinfo.value.code == "REFRESH_TOO_SOON"
    assert calls == []
    assert load_bods_live_control_state(workspace).attempts_total == 1


def test_failure_is_counted_without_replacing_prior_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    success = _run(workspace, datetime(2026, 7, 22, 10, tzinfo=UTC))

    def fail(*_args: object, **_kwargs: object) -> None:
        raise BodsLiveWorkflowError("SYNTHETIC_FAILURE", "synthetic safe failure")

    monkeypatch.setattr(control, "refresh_bods_live_scene", fail)
    with pytest.raises(BodsLiveWorkflowError):
        coordinated_bods_live_refresh(
            workspace,
            BOX,
            api_key=API_KEY,
            synthetic=True,
            utc_now=_clock(datetime(2026, 7, 22, 10, 2, tzinfo=UTC)),
        )
    state = load_bods_live_control_state(workspace)
    assert state.attempts_total == 2
    assert state.successes_total == 1
    assert state.failures_total == 1
    assert state.last_attempt_status == "failed"
    assert state.last_failure_code == "SYNTHETIC_FAILURE"
    assert state.latest_success == success.refresh.summary
    assert state.history == (success.refresh.summary,)


def test_concurrent_lock_refuses_without_touching_state(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    lock = workspace / control.BODS_LIVE_CONTROL_LOCK_RELATIVE_PATH
    lock.parent.mkdir(parents=True)
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(BodsLiveControlError) as excinfo:
            coordinated_bods_live_refresh(
                workspace,
                BOX,
                api_key=API_KEY,
                synthetic=True,
                utc_now=_clock(datetime(2026, 7, 22, 10, tzinfo=UTC)),
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    assert excinfo.value.code == "REFRESH_BUSY"
    assert load_bods_live_control_state(workspace).attempts_total == 0


def test_state_tamper_is_rejected(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    _run(workspace, datetime(2026, 7, 22, 10, tzinfo=UTC))
    target = workspace / BODS_LIVE_CONTROL_RELATIVE_PATH
    target.write_bytes(target.read_bytes().replace(b'"successes_total":1', b'"successes_total":0'))
    with pytest.raises(BodsLiveControlError) as excinfo:
        load_bods_live_control_state(workspace)
    assert excinfo.value.code == "CONTROL_STATE_INVALID"


def test_initial_state_is_valid_and_side_effect_free(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    state = load_bods_live_control_state(workspace)
    assert state == control.initial_bods_live_control_state()
    assert not (workspace / BODS_LIVE_CONTROL_RELATIVE_PATH).exists()
    assert BodsLiveControlState.model_validate_json(state.canonical_json()) == state


def test_display_projection_ages_live_buses_to_stale_without_mutating_scene() -> None:
    observed = datetime(2026, 7, 22, 9, 59, 30, tzinfo=UTC)
    source_evaluation = datetime(2026, 7, 22, 10, tzinfo=UTC)
    freshness = evaluate_source_freshness(
        FreshnessEvaluationRequest(
            source="bods_siri_vm",
            evidence_validation=ManchesterValidationState.ACCEPTED,
            snapshot_available=True,
            use_mode="live",
            evaluated_at_utc=source_evaluation,
            observed_at_utc=observed,
            valid_until_utc=datetime(2026, 7, 22, 10, 5, tzinfo=UTC),
            synthetic=False,
        )
    )
    evidence = ManchesterSpatialPointEvidence(
        source="bods_siri_vm",
        source_record_fingerprint="e" * 64,
        point_id="bods:private-token",
        coordinate_kind="wgs84",
        longitude_epsg4326=Decimal("-2.25"),
        latitude_epsg4326=Decimal("53.49"),
        geographic_scope="request_bounding_box",
        scope_basis="bods_request_bounds",
        scope_evidence_fingerprint="f" * 64,
        geometry_meaning="transit_vehicle_position",
        source_record_state="eligible",
        uncertainty_basis="source_not_stated",
        synthetic=False,
    )
    layer = build_map_layer(
        MapLayerRequest(
            layer_id="bods-bee-network-live",
            title="Bee Network buses · live",
            mode="live_vehicles",
            source="bods_siri_vm",
            snapshot_id="bods_siri_vm-20260722T100000Z-abcdef012345",
            snapshot_fingerprint="1" * 64,
            spatial_report=evaluate_spatial_batch((evidence,)),
            freshness=freshness,
            publication_class=ManchesterPublicationClass.PRIVATE,
            licence_id="OGL-v3.0",
            attribution_lines=("Private BODS SIRI-VM research snapshot.",),
            synthetic=False,
        )
    )
    source_scene = build_map_scene("live_vehicles", (layer,))

    projected = project_bods_live_scene_for_display(
        source_scene,
        evaluated_at_utc=datetime(2026, 7, 22, 10, 2, tzinfo=UTC),
    )

    assert source_scene.layers[0].freshness_truth_state == "live_vehicle"
    assert source_scene.layers[0].request.title.endswith("· live")
    assert projected.layers[0].freshness_truth_state == "stale"
    assert projected.layers[0].stale_badge_visible is True
    assert projected.layers[0].reason == "stale_cached_evidence"
    assert projected.layers[0].request.title.endswith("· stale cached")
    assert projected.status == "partial"


def test_display_projection_keeps_synthetic_scene_synthetic(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    result = _run(workspace, datetime(2026, 7, 22, 10, tzinfo=UTC))
    projected = project_bods_live_scene_for_display(
        result.refresh.scene,
        evaluated_at_utc=datetime(2026, 8, 22, 10, tzinfo=UTC),
    )
    assert projected == result.refresh.scene

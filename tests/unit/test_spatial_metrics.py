from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.helpers import FIXED_TIME, fixed_clock
from traffictwin.canonical.records import InfrastructureRecord, TaskRecord, VehicleStateRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.domain.spatial import (
    DEFAULT_TASK_RSU_TARGET_CONTRACT,
    TaskRsuTargetContract,
    VehicleSpatialGridContract,
)
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.ingestion.manifest import BundleManifest
from traffictwin.metrics.engine import compute_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.spatial import RSU_TASK_BREAKDOWN_KEYS, VEHICLE_GRID_KEYS
from traffictwin.metrics.windowed import WindowedMetricConfig, compute_windowed_metrics
from traffictwin.provenance.query import build_provenance_context, get_metric_contributions
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

GRID_CONTRACT = VehicleSpatialGridContract(
    coordinate_frame_id="unit-source-frame",
    cell_width_m=100,
    cell_height_m=100,
)


def _context(
    *,
    target_contract: TaskRsuTargetContract | None = DEFAULT_TASK_RSU_TARGET_CONTRACT,
    grid_contract: VehicleSpatialGridContract | None = GRID_CONTRACT,
) -> RunMetricContext:
    return RunMetricContext(
        run_id="run-spatial",
        experiment_id="exp-spatial",
        seed_id="seed-spatial",
        algorithm="synthetic-test",
        random_seed=7,
        synthetic=True,
        task_rsu_target_contract=target_contract,
        vehicle_spatial_grid_contract=grid_contract,
    )


def _evidence() -> EvidenceAvailability:
    return EvidenceAvailability(
        tasks=EvidenceStatus.AVAILABLE,
        infrastructure=EvidenceStatus.AVAILABLE,
        vehicles=EvidenceStatus.AVAILABLE,
    )


def _task(
    task_id: str,
    target_id: str | None,
    completed: bool,
    latency_ms: float | None,
    row: int,
    *,
    decision: Decision = Decision.V2I,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        vehicle_id=f"veh-{row}",
        task_class=TaskClass.T1,
        arrival_time_s=float(row),
        deadline_ms=100,
        decision=decision,
        completed=completed,
        latency_ms=latency_ms,
        target_id=target_id,
        source_file="tasks.csv",
        source_row=row,
    )


def _vehicle(
    vehicle_id: str,
    x: float | None,
    y: float | None,
    speed: float | None,
    row: int,
) -> VehicleStateRecord:
    return VehicleStateRecord(
        timestamp_s=float(row),
        vehicle_id=vehicle_id,
        x=x,
        y=y,
        speed_mps=speed,
        source_file="vehicles.csv",
        source_row=row,
    )


def _tables() -> CanonicalTables:
    return CanonicalTables(
        tasks=[
            _task("t1", "rsu-1", True, 120, 1),
            _task("t2", "rsu-1", False, None, 2),
            _task("t3", "rsu-2", True, 80, 3),
            _task("t4", "rsu-2", True, 90, 4),
            _task("local", None, True, 20, 5, decision=Decision.LOCAL),
        ],
        infrastructure=[
            InfrastructureRecord(
                timestamp_s=1,
                rsu_id="rsu-1",
                source_file="infra.csv",
                source_row=1,
            ),
            InfrastructureRecord(
                timestamp_s=2,
                rsu_id="rsu-2",
                source_file="infra.csv",
                source_row=2,
            ),
        ],
        vehicles=[
            _vehicle("v1", 10, 10, 10, 1),
            _vehicle("v2", 90, 10, 20, 2),
            _vehicle("v1", 110, 10, 30, 3),
            _vehicle("v3", 110, 110, 40, 4),
        ],
    )


def _metrics(
    tables: CanonicalTables | None = None,
    context: RunMetricContext | None = None,
) -> MetricCollection:
    return compute_metrics(
        tables or _tables(),
        context or _context(),
        _evidence(),
        MetricEngineConfig(),
        clock=lambda: FIXED_TIME,
    )


def test_spatial_contracts_are_strict_and_fingerprinted() -> None:
    assert len(DEFAULT_TASK_RSU_TARGET_CONTRACT.fingerprint()) == 64
    assert len(GRID_CONTRACT.fingerprint()) == 64
    with pytest.raises(ValueError):
        VehicleSpatialGridContract(coordinate_frame_id="frame", cell_width_m=0)


def test_per_rsu_and_grid_metrics_have_exact_values_and_coverage() -> None:
    metrics = _metrics().by_key()

    assert metrics[RSU_TASK_BREAKDOWN_KEYS[0]].value == {"rsu-1": 2, "rsu-2": 2}
    assert metrics[RSU_TASK_BREAKDOWN_KEYS[1]].value == {"rsu-1": 0.5, "rsu-2": 1.0}
    assert metrics[RSU_TASK_BREAKDOWN_KEYS[2]].value == {"rsu-1": 1.0, "rsu-2": 0.0}
    assert metrics[VEHICLE_GRID_KEYS[0]].value == {"x0:y0": 2, "x1:y0": 1, "x1:y1": 1}
    assert metrics[VEHICLE_GRID_KEYS[1]].value == {"x0:y0": 2, "x1:y0": 1, "x1:y1": 1}
    assert metrics[VEHICLE_GRID_KEYS[2]].value == {
        "x0:y0": 15.0,
        "x1:y0": 30.0,
        "x1:y1": 40.0,
    }
    for key in (*RSU_TASK_BREAKDOWN_KEYS, *VEHICLE_GRID_KEYS):
        assert metrics[key].status is MetricStatus.AVAILABLE
        assert metrics[key].metadata["coverage_fraction"] == 1.0


def test_missing_contracts_keep_both_families_unavailable() -> None:
    metrics = _metrics(context=_context(target_contract=None, grid_contract=None)).by_key()

    assert metrics[RSU_TASK_BREAKDOWN_KEYS[0]].reason_codes == [
        UnavailableReason.TASK_RSU_TARGET_CONTRACT_UNAVAILABLE
    ]
    assert metrics[VEHICLE_GRID_KEYS[0]].reason_codes == [
        UnavailableReason.VEHICLE_SPATIAL_GRID_CONTRACT_UNAVAILABLE
    ]


def test_target_family_rejects_missing_and_unknown_targets_without_assignment() -> None:
    tables = _tables()
    tables.tasks[0] = tables.tasks[0].model_copy(update={"target_id": None})
    tables.tasks[2] = tables.tasks[2].model_copy(update={"target_id": "rsu-unknown"})
    metrics = _metrics(tables).by_key()

    for key in RSU_TASK_BREAKDOWN_KEYS:
        assert metrics[key].status is MetricStatus.UNAVAILABLE
        assert metrics[key].reason_codes == [
            UnavailableReason.TARGET_COVERAGE_INSUFFICIENT,
            UnavailableReason.TARGET_JOIN_INCOMPATIBLE,
        ]
        assert metrics[key].metadata["coverage_fraction"] == 0.5


def test_deadline_groups_remain_partial_and_null_when_support_is_missing() -> None:
    tables = _tables()
    tables.tasks[0] = tables.tasks[0].model_copy(update={"latency_ms": None})
    metric = _metrics(tables).by_key()[RSU_TASK_BREAKDOWN_KEYS[2]]

    assert metric.status is MetricStatus.PARTIAL
    assert metric.value == {"rsu-1": None, "rsu-2": 0.0}
    assert metric.metadata["deadline_coverage_fraction"] == pytest.approx(2 / 3)


def test_grid_family_requires_complete_coordinates_and_speed_stays_partial() -> None:
    missing_position = _tables()
    missing_position.vehicles[0] = missing_position.vehicles[0].model_copy(update={"x": None})
    missing_metrics = _metrics(missing_position).by_key()
    assert missing_metrics[VEHICLE_GRID_KEYS[0]].reason_codes == [
        UnavailableReason.COORDINATE_COVERAGE_INSUFFICIENT
    ]

    missing_speed = _tables()
    missing_speed.vehicles[3] = missing_speed.vehicles[3].model_copy(update={"speed_mps": None})
    speed = _metrics(missing_speed).by_key()[VEHICLE_GRID_KEYS[2]]
    assert speed.status is MetricStatus.PARTIAL
    assert speed.value == {"x0:y0": 15.0, "x1:y0": 30.0, "x1:y1": None}
    assert speed.metadata["speed_coverage_fraction"] == 0.75

    no_positions = _tables()
    no_positions.vehicles = [
        record.model_copy(update={"x": None, "y": None}) for record in no_positions.vehicles
    ]
    no_position_metrics = _metrics(no_positions).by_key()
    count = no_position_metrics[VEHICLE_GRID_KEYS[0]]
    assert count.status is MetricStatus.UNAVAILABLE
    assert count.reason_codes == [UnavailableReason.COORDINATE_COVERAGE_INSUFFICIENT]
    assert count.metadata["coverage_fraction"] == 0.0
    assert count.metadata["minimum_x_m"] is None


def test_fixed_windows_reuse_exact_in_window_target_and_coordinate_evidence() -> None:
    series = compute_windowed_metrics(
        _tables(),
        _context(),
        _evidence(),
        WindowedMetricConfig(width_s=60, analysis_start_s=0, analysis_end_s=60),
        clock=lambda: FIXED_TIME,
    )
    metrics = series.slices[0].metrics

    assert metrics is not None
    assert metrics.by_key()[RSU_TASK_BREAKDOWN_KEYS[1]].value == {
        "rsu-1": 0.5,
        "rsu-2": 1.0,
    }
    assert metrics.by_key()[VEHICLE_GRID_KEYS[0]].value == {
        "x0:y0": 2,
        "x1:y0": 1,
        "x1:y1": 1,
    }


def test_manifest_contracts_require_explicit_columns_and_coordinate_units() -> None:
    base: dict[str, Any] = {
        "schema_version": "1.0",
        "bundle": {
            "bundle_id": "bundle-spatial",
            "created_at": "2026-07-20T00:00:00Z",
            "source": "test",
        },
        "run": {
            "run_id": "run-spatial",
            "experiment_id": "exp-spatial",
            "seed_id": "seed-spatial",
            "algorithm": "test",
            "random_seed": 1,
        },
        "environment": {"name": "test"},
        "files": {
            "tasks": {"path": "tasks.csv", "required_columns": ["task_id"]},
            "infra_state": {"path": "infra.csv", "required_columns": ["rsu_id"]},
            "vehicle_state": {
                "path": "vehicles.csv",
                "required_columns": ["vehicle_id", "x", "y"],
                "units": {"x": "m", "y": "m"},
            },
        },
        "task_rsu_target_contract": DEFAULT_TASK_RSU_TARGET_CONTRACT.model_dump(mode="json"),
        "vehicle_spatial_grid_contract": GRID_CONTRACT.model_dump(mode="json"),
        "provenance": {"producer": "test"},
    }
    with pytest.raises(ValueError, match="target_id column"):
        BundleManifest.model_validate(base)

    base["files"]["tasks"]["required_columns"].append("target_id")
    base["files"]["vehicle_state"]["units"].pop("x")
    with pytest.raises(ValueError, match="x and y units"):
        BundleManifest.model_validate(base)


def test_spatial_contribution_ledgers_preserve_exact_row_eligibility(tmp_path: Path) -> None:
    bundle_path = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    context = build_provenance_context(bundle_path, clock=fixed_clock)

    targets = get_metric_contributions(context, RSU_TASK_BREAKDOWN_KEYS[1])
    grid = get_metric_contributions(context, VEHICLE_GRID_KEYS[0])

    assert targets.complete_row_ledger
    assert targets.included_row_count > 0
    assert targets.excluded_row_count > 0
    assert grid.complete_row_ledger
    assert grid.included_row_count == grid.candidate_row_count

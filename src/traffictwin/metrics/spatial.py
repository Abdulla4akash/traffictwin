"""Evidence-gated per-RSU task outcomes and vehicle spatial-grid summaries."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime

from traffictwin.canonical.records import TaskRecord, VehicleStateRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision
from traffictwin.domain.spatial import TaskRsuTargetContract, VehicleSpatialGridContract
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonObject,
    JsonScalar,
    MetricStatus,
    MetricValue,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.statistics import arithmetic_mean

RSU_TASK_BREAKDOWN_KEYS = (
    "spatial.rsu.task.count_by_target",
    "spatial.rsu.task.completion_rate_by_target",
    "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
)
VEHICLE_GRID_KEYS = (
    "spatial.vehicle.observation_count_by_grid_cell",
    "spatial.vehicle.distinct_count_by_grid_cell",
    "spatial.vehicle.speed.mean_mps_by_grid_cell",
)
SPATIAL_KEYS = (*RSU_TASK_BREAKDOWN_KEYS, *VEHICLE_GRID_KEYS)


def spatial_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Compute all explicitly contracted per-RSU and spatial-grid outputs."""

    return [
        *_rsu_task_metrics(tables, context, evidence, config, computed_at),
        *_vehicle_grid_metrics(tables, context, evidence, config, computed_at),
    ]


def eligible_v2i_target(task: TaskRecord, rsu_ids: set[str]) -> bool:
    """Return whether one task has an exact eligible V2I-to-RSU join."""

    return task.decision is Decision.V2I and bool(task.target_id) and task.target_id in rsu_ids


def valid_vehicle_position(record: VehicleStateRecord) -> bool:
    """Return whether one vehicle row has finite canonical x/y values."""

    return (
        record.x is not None
        and record.y is not None
        and math.isfinite(record.x)
        and math.isfinite(record.y)
    )


def valid_vehicle_speed(record: VehicleStateRecord) -> bool:
    """Return whether one vehicle row has a finite non-negative speed."""

    return (
        record.speed_mps is not None and math.isfinite(record.speed_mps) and record.speed_mps >= 0
    )


def grid_cell_id(record: VehicleStateRecord, contract: VehicleSpatialGridContract) -> str:
    """Assign an eligible vehicle observation to the fixed axis-aligned grid."""

    if record.x is None or record.y is None:
        raise ValueError("grid assignment requires x and y")
    x_index = math.floor((record.x - contract.origin_x_m) / contract.cell_width_m)
    y_index = math.floor((record.y - contract.origin_y_m) / contract.cell_height_m)
    return f"x{x_index}:y{y_index}"


def _rsu_task_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    contract = context.task_rsu_target_contract
    base_metadata = _task_contract_metadata(contract)
    if evidence.tasks is not EvidenceStatus.AVAILABLE:
        return _unavailable_family(
            RSU_TASK_BREAKDOWN_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            ["tasks"],
            base_metadata,
        )
    if evidence.infrastructure is not EvidenceStatus.AVAILABLE or not tables.infrastructure:
        return _unavailable_family(
            RSU_TASK_BREAKDOWN_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            ["infrastructure.rsu_id"],
            base_metadata,
        )
    if contract is None:
        return _unavailable_family(
            RSU_TASK_BREAKDOWN_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.TASK_RSU_TARGET_CONTRACT_UNAVAILABLE],
            ["manifest.task_rsu_target_contract"],
            base_metadata,
        )

    v2i_tasks = [task for task in tables.tasks if task.decision is Decision.V2I]
    if not v2i_tasks:
        return _unavailable_family(
            RSU_TASK_BREAKDOWN_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.METRIC_NOT_APPLICABLE],
            ["at least one canonical V2I task"],
            base_metadata,
        )

    rsu_ids = {record.rsu_id for record in tables.infrastructure}
    admitted = [task for task in v2i_tasks if eligible_v2i_target(task, rsu_ids)]
    missing_target_count = sum(not task.target_id for task in v2i_tasks)
    unknown_target_count = sum(
        bool(task.target_id) and task.target_id not in rsu_ids for task in v2i_tasks
    )
    grouped: dict[str, list[TaskRecord]] = defaultdict(list)
    for task in admitted:
        assert task.target_id is not None
        grouped[task.target_id].append(task)
    metadata = _target_metadata(
        contract,
        grouped,
        population_count=len(v2i_tasks),
        missing_target_count=missing_target_count,
        unknown_target_count=unknown_target_count,
    )
    reasons: list[UnavailableReason] = []
    missing: list[str] = []
    if len(admitted) < len(v2i_tasks):
        reasons.append(UnavailableReason.TARGET_COVERAGE_INSUFFICIENT)
        missing.append("complete non-empty target_id coverage for canonical V2I tasks")
    if unknown_target_count:
        reasons.append(UnavailableReason.TARGET_JOIN_INCOMPATIBLE)
        missing.append("exact target_id match to an in-scope canonical infrastructure.rsu_id")
    if reasons:
        return _unavailable_family(
            RSU_TASK_BREAKDOWN_KEYS,
            context,
            config,
            computed_at,
            reasons,
            missing,
            metadata,
            warnings=[
                "Per-RSU task outcomes require complete explicit V2I execution-target joins; "
                "unmatched tasks are not assigned to a nearest or assumed RSU."
            ],
        )

    counts = {rsu_id: len(tasks) for rsu_id, tasks in sorted(grouped.items())}
    completion = {
        rsu_id: sum(task.completed for task in tasks) / len(tasks)
        for rsu_id, tasks in sorted(grouped.items())
    }
    deadline_metric = _deadline_miss_by_rsu(
        grouped,
        metadata,
        context,
        config,
        computed_at,
    )
    warning = (
        "Observed execution-target grouping is descriptive lineage, not evidence that an RSU "
        "caused a task outcome."
    )
    return [
        available_metric(
            RSU_TASK_BREAKDOWN_KEYS[0],
            counts,
            context,
            config,
            computed_at,
            warnings=[warning],
            metadata=metadata,
        ),
        available_metric(
            RSU_TASK_BREAKDOWN_KEYS[1],
            completion,
            context,
            config,
            computed_at,
            warnings=[warning],
            metadata=metadata,
        ),
        deadline_metric,
    ]


def _deadline_miss_by_rsu(
    grouped: dict[str, list[TaskRecord]],
    base_metadata: JsonObject,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    values: dict[str, float | None] = {}
    support: dict[str, int] = {}
    completed_support: dict[str, int] = {}
    completed_count = 0
    eligible_count = 0
    for rsu_id, tasks in sorted(grouped.items()):
        completed = [task for task in tasks if task.completed]
        eligible = [task for task in completed if task.latency_ms is not None]
        completed_support[rsu_id] = len(completed)
        support[rsu_id] = len(eligible)
        completed_count += len(completed)
        eligible_count += len(eligible)
        values[rsu_id] = (
            sum(
                task.latency_ms is not None and task.latency_ms > task.deadline_ms
                for task in eligible
            )
            / len(eligible)
            if eligible
            else None
        )
    metadata: JsonObject = {
        **base_metadata,
        "completed_task_count": completed_count,
        "deadline_eligible_count": eligible_count,
        "deadline_coverage_fraction": (
            eligible_count / completed_count if completed_count else None
        ),
        "completed_group_support_counts": _scalar_counts(completed_support),
        "deadline_group_support_counts": _scalar_counts(support),
    }
    if eligible_count == 0:
        return unavailable_metric(
            RSU_TASK_BREAKDOWN_KEYS[2],
            context,
            config,
            computed_at,
            [UnavailableReason.NO_LATENCY_VALUES],
            ["completed V2I tasks with observed latency by target RSU"],
            warnings=[
                "No completed targeted V2I task has latency evidence; per-RSU misses are not zero."
            ],
            metadata=metadata,
        )
    partial = eligible_count < completed_count or any(value is None for value in values.values())
    return available_metric(
        RSU_TASK_BREAKDOWN_KEYS[2],
        values,
        context,
        config,
        computed_at,
        status=MetricStatus.PARTIAL if partial else MetricStatus.AVAILABLE,
        warnings=[
            "Incomplete completed-task latency support is represented as partial/null by RSU, "
            "never as zero.",
            "Observed execution-target grouping is descriptive lineage, not causal attribution.",
        ]
        if partial
        else ["Observed execution-target grouping is descriptive lineage, not causal attribution."],
        metadata=metadata,
    )


def _vehicle_grid_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    contract = context.vehicle_spatial_grid_contract
    base_metadata = _grid_contract_metadata(contract)
    if evidence.vehicles is not EvidenceStatus.AVAILABLE:
        return _unavailable_family(
            VEHICLE_GRID_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            ["vehicles"],
            base_metadata,
        )
    if contract is None:
        return _unavailable_family(
            VEHICLE_GRID_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.VEHICLE_SPATIAL_GRID_CONTRACT_UNAVAILABLE],
            ["manifest.vehicle_spatial_grid_contract"],
            base_metadata,
        )
    records = list(tables.vehicles)
    if not records:
        return _unavailable_family(
            VEHICLE_GRID_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.NO_VALID_ROWS],
            ["vehicles"],
            base_metadata,
        )

    positioned = [record for record in records if valid_vehicle_position(record)]
    grouped: dict[str, list[VehicleStateRecord]] = defaultdict(list)
    for record in positioned:
        grouped[grid_cell_id(record, contract)].append(record)
    metadata = _grid_metadata(contract, grouped, population_count=len(records))
    if len(positioned) < len(records):
        return _unavailable_family(
            VEHICLE_GRID_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.COORDINATE_COVERAGE_INSUFFICIENT],
            ["finite vehicles.x and vehicles.y for every in-scope vehicle observation"],
            metadata,
            warnings=[
                "Spatial cells require complete contracted coordinates; missing rows are not "
                "dropped or assigned to an unknown/zero cell."
            ],
        )

    observation_counts = {cell: len(cell_records) for cell, cell_records in sorted(grouped.items())}
    distinct_counts = {
        cell: len({record.vehicle_id for record in cell_records})
        for cell, cell_records in sorted(grouped.items())
    }
    warning = (
        "Cells belong only to the declared source coordinate frame; they are not geographic "
        "areas without separate CRS evidence."
    )
    return [
        available_metric(
            VEHICLE_GRID_KEYS[0],
            observation_counts,
            context,
            config,
            computed_at,
            warnings=[warning],
            metadata=metadata,
        ),
        available_metric(
            VEHICLE_GRID_KEYS[1],
            distinct_counts,
            context,
            config,
            computed_at,
            warnings=[warning],
            metadata=metadata,
        ),
        _speed_by_grid_cell(grouped, metadata, context, config, computed_at),
    ]


def _speed_by_grid_cell(
    grouped: dict[str, list[VehicleStateRecord]],
    base_metadata: JsonObject,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    values: dict[str, float | None] = {}
    support: dict[str, int] = {}
    total_count = sum(len(records) for records in grouped.values())
    eligible_count = 0
    for cell, records in sorted(grouped.items()):
        speeds = [
            record.speed_mps
            for record in records
            if valid_vehicle_speed(record) and record.speed_mps is not None
        ]
        eligible_count += len(speeds)
        support[cell] = len(speeds)
        values[cell] = arithmetic_mean(speeds) if speeds else None
    metadata: JsonObject = {
        **base_metadata,
        "speed_eligible_count": eligible_count,
        "speed_population_count": total_count,
        "speed_coverage_fraction": eligible_count / total_count if total_count else None,
        "speed_group_support_counts": _scalar_counts(support),
    }
    if eligible_count == 0:
        return unavailable_metric(
            VEHICLE_GRID_KEYS[2],
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
            ["vehicles.speed_mps"],
            warnings=["No eligible speed evidence exists; cell speed is not represented as zero."],
            metadata=metadata,
        )
    partial = eligible_count < total_count or any(value is None for value in values.values())
    return available_metric(
        VEHICLE_GRID_KEYS[2],
        values,
        context,
        config,
        computed_at,
        status=MetricStatus.PARTIAL if partial else MetricStatus.AVAILABLE,
        warnings=[
            "Missing cell speed evidence remains null/partial rather than zero.",
            "Cells are source-frame summaries, not geographic or causal evidence.",
        ]
        if partial
        else ["Cells are source-frame summaries, not geographic or causal evidence."],
        metadata=metadata,
    )


def _task_contract_metadata(contract: TaskRsuTargetContract | None) -> JsonObject:
    return {
        "task_rsu_target_contract_version": contract.schema_version if contract else "1.0",
        "task_rsu_target_contract_fingerprint": contract.fingerprint() if contract else None,
        "target_semantics": contract.target_semantics if contract else None,
        "target_join_method": contract.join_method if contract else None,
        "minimum_target_coverage_fraction": (
            contract.minimum_target_coverage_fraction if contract else 1.0
        ),
        "attribution_interpretation": contract.attribution_interpretation if contract else None,
    }


def _target_metadata(
    contract: TaskRsuTargetContract,
    grouped: dict[str, list[TaskRecord]],
    *,
    population_count: int,
    missing_target_count: int,
    unknown_target_count: int,
) -> JsonObject:
    group_ids = sorted(grouped)
    eligible_count = sum(len(tasks) for tasks in grouped.values())
    return {
        **_task_contract_metadata(contract),
        "group_set_fingerprint": _group_set_fingerprint("rsu_target", group_ids),
        "group_count": len(group_ids),
        "group_support_counts": {rsu_id: len(grouped[rsu_id]) for rsu_id in group_ids},
        "eligible_count": eligible_count,
        "population_count": population_count,
        "coverage_fraction": eligible_count / population_count if population_count else None,
        "missing_target_count": missing_target_count,
        "unknown_target_count": unknown_target_count,
    }


def _grid_contract_metadata(contract: VehicleSpatialGridContract | None) -> JsonObject:
    return {
        "vehicle_spatial_grid_contract_version": contract.schema_version if contract else "1.0",
        "vehicle_spatial_grid_contract_fingerprint": contract.fingerprint() if contract else None,
        "coordinate_frame_id": contract.coordinate_frame_id if contract else None,
        "coordinate_unit": contract.canonical_coordinate_unit if contract else None,
        "origin_x_m": contract.origin_x_m if contract else None,
        "origin_y_m": contract.origin_y_m if contract else None,
        "cell_width_m": contract.cell_width_m if contract else None,
        "cell_height_m": contract.cell_height_m if contract else None,
        "assignment_method": contract.assignment_method if contract else None,
        "geographic_interpretation": contract.geographic_interpretation if contract else None,
    }


def _grid_metadata(
    contract: VehicleSpatialGridContract,
    grouped: dict[str, list[VehicleStateRecord]],
    *,
    population_count: int,
) -> JsonObject:
    cells = sorted(grouped)
    positioned = [record for records in grouped.values() for record in records]
    eligible_count = len(positioned)
    x_values = [record.x for record in positioned if record.x is not None]
    y_values = [record.y for record in positioned if record.y is not None]
    return {
        **_grid_contract_metadata(contract),
        "group_set_fingerprint": _group_set_fingerprint("vehicle_grid_cell", cells),
        "cell_count": len(cells),
        "cell_support_counts": {cell: len(grouped[cell]) for cell in cells},
        "eligible_count": eligible_count,
        "population_count": population_count,
        "coverage_fraction": eligible_count / population_count if population_count else None,
        "minimum_x_m": min(x_values) if x_values else None,
        "maximum_x_m": max(x_values) if x_values else None,
        "minimum_y_m": min(y_values) if y_values else None,
        "maximum_y_m": max(y_values) if y_values else None,
    }


def _group_set_fingerprint(dimension: str, groups: list[str]) -> str:
    encoded = json.dumps(
        {"group_dimension": dimension, "groups": groups},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _scalar_counts(counts: dict[str, int]) -> dict[str, JsonScalar]:
    return dict(counts)


def _unavailable_family(
    keys: tuple[str, ...],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    reasons: list[UnavailableReason],
    missing: list[str],
    metadata: JsonObject,
    *,
    warnings: list[str] | None = None,
) -> list[MetricValue]:
    return [
        unavailable_metric(
            key,
            context,
            config,
            computed_at,
            reasons,
            missing,
            warnings=warnings,
            metadata=metadata,
        )
        for key in keys
    ]

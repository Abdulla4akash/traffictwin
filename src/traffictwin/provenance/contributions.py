"""Complete canonical-row contribution ledgers for deterministic run metrics."""

from __future__ import annotations

import csv
import math
from io import StringIO

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.canonical.records import (
    CanonicalRecord,
    InfrastructureRecord,
    TaskRecord,
    VehicleStateRecord,
)
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.catalogue import metric_definition_for_result
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.fairness import (
    RSU_FAIRNESS_KEYS,
    VEHICLE_TIER_FAIRNESS_KEYS,
    capacity_normalised_load,
    stable_vehicle_tiers,
)
from traffictwin.metrics.plugins import (
    PluginMetricContract,
    PluginRowPolicy,
    plugin_contract_from_metric,
)
from traffictwin.metrics.results import JsonValue, MetricCollection
from traffictwin.metrics.spatial import (
    RSU_TASK_BREAKDOWN_KEYS,
    VEHICLE_GRID_KEYS,
    eligible_v2i_target,
    valid_vehicle_position,
    valid_vehicle_speed,
)
from traffictwin.metrics.windowed import (
    MetricWindow,
    WindowedMetricSeries,
    bundle_result_for_window,
)


class MetricContributionRow(BaseModel):
    """One canonical input row and its deterministic metric inclusion state."""

    model_config = ConfigDict(extra="forbid")

    canonical_table: str
    record_id: str
    source_file: str
    source_row: int = Field(ge=1)
    included: bool
    inclusion_reason: str
    canonical_values: dict[str, JsonValue]


class MetricContributionReport(BaseModel):
    """Unbounded row-level ledger for one run metric."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    metric_key: str
    metric_status: str
    metric_value: JsonValue
    required_tables: list[str]
    candidate_row_count: int = Field(ge=0)
    included_row_count: int = Field(ge=0)
    excluded_row_count: int = Field(ge=0)
    complete_row_ledger: bool = True
    rows: list[MetricContributionRow]
    limitations: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


class WindowMetricContributionReport(BaseModel):
    """Complete accepted-row ledger scoped to one fixed metric window."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    window: MetricWindow
    contribution_report: MetricContributionReport
    limitations: list[str]

    def to_json(self) -> str:
        """Return readable JSON."""

        return self.model_dump_json(indent=2)


def build_metric_contribution_report(
    bundle: BundleValidationResult,
    metrics: MetricCollection,
    metric_key: str,
    *,
    config: MetricEngineConfig | None = None,
) -> MetricContributionReport:
    """List every canonical candidate row and whether it entered one metric calculation."""

    metric = metrics.by_key().get(metric_key)
    if metric is None:
        raise ValueError(f"metric is not present in the collection: {metric_key}")
    definition = metric_definition_for_result(metric)
    if definition is None:
        raise ValueError(f"row contribution rules are unavailable for metric: {metric_key}")
    engine_config = config or MetricEngineConfig()
    plugin_contract = plugin_contract_from_metric(metric)
    rows: list[MetricContributionRow] = []
    for table_name in definition.required_tables:
        records = _records(bundle.canonical, table_name)
        for record in records:
            included, reason = _inclusion(
                metric_key,
                table_name,
                record,
                bundle.canonical,
                engine_config,
                energy_contract_available=(
                    bundle.manifest is not None and bundle.manifest.energy_contract is not None
                ),
                task_rsu_target_contract_available=(
                    bundle.manifest is not None
                    and bundle.manifest.task_rsu_target_contract is not None
                ),
                vehicle_spatial_grid_contract_available=(
                    bundle.manifest is not None
                    and bundle.manifest.vehicle_spatial_grid_contract is not None
                ),
                plugin_contract=plugin_contract,
                plugin_execution_attempted=bool(
                    metric.metadata.get("plugin_execution_attempted", False)
                ),
            )
            rows.append(
                MetricContributionRow(
                    canonical_table=table_name,
                    record_id=_record_id(table_name, record),
                    source_file=record.source_file,
                    source_row=record.source_row,
                    included=included,
                    inclusion_reason=reason,
                    canonical_values=record.model_dump(mode="json"),
                )
            )
    rows.sort(key=lambda row: (row.canonical_table, row.source_file, row.source_row, row.record_id))
    included_count = sum(int(row.included) for row in rows)
    return MetricContributionReport(
        run_id=metrics.run_id,
        metric_key=metric_key,
        metric_status=metric.status.value,
        metric_value=metric.value,
        required_tables=definition.required_tables,
        candidate_row_count=len(rows),
        included_row_count=included_count,
        excluded_row_count=len(rows) - included_count,
        rows=rows,
        limitations=[
            "The ledger includes every canonical candidate row and applies the same field-level "
            "eligibility predicates as the metric engine.",
            "For grouped and percentile metrics, included rows identify the complete input set; "
            "the report does not claim an individual row caused the aggregate result.",
            "Source validation exclusions occur before canonicalisation and remain in the normal "
            "validation report rather than this accepted-row ledger.",
            *(
                [
                    "For a custom metric, included means the row was supplied through the "
                    "contracted plugin input view; the trusted function may combine those rows "
                    "non-additively."
                ]
                if plugin_contract is not None
                else []
            ),
        ],
    )


def contribution_report_to_csv(report: MetricContributionReport) -> str:
    """Render a complete contribution ledger as deterministic CSV."""

    output = StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "metric_key",
            "canonical_table",
            "record_id",
            "source_file",
            "source_row",
            "included",
            "inclusion_reason",
            "canonical_values_json",
        ]
    )
    for row in report.rows:
        writer.writerow(
            [
                report.metric_key,
                row.canonical_table,
                row.record_id,
                row.source_file,
                row.source_row,
                row.included,
                row.inclusion_reason,
                _canonical_json(row.canonical_values),
            ]
        )
    return output.getvalue()


def build_window_metric_contribution_report(
    bundle: BundleValidationResult,
    series: WindowedMetricSeries,
    window_ordinal: int,
    metric_key: str,
    *,
    config: MetricEngineConfig | None = None,
) -> WindowMetricContributionReport:
    """Build an ordinary complete-row ledger after exact half-open window filtering."""

    window_slice = series.slice_at(window_ordinal)
    if window_slice.metrics is None:
        raise ValueError(f"window {window_ordinal} was excluded and has no metric collection")
    filtered = bundle_result_for_window(bundle, window_slice.window)
    report = build_metric_contribution_report(
        filtered,
        window_slice.metrics,
        metric_key,
        config=config,
    )
    return WindowMetricContributionReport(
        window=window_slice.window,
        contribution_report=report,
        limitations=[
            "Candidate rows are first assigned by the versioned half-open window anchor policy, "
            "then evaluated by the ordinary metric eligibility predicates.",
            "This is arithmetic lineage for accepted evidence, not causal attribution.",
        ],
    )


def _records(tables: CanonicalTables, table_name: str) -> list[CanonicalRecord]:
    mapping: dict[str, list[CanonicalRecord]] = {
        "tasks": list(tables.tasks),
        "infrastructure": list(tables.infrastructure),
        "vehicles": list(tables.vehicles),
        "traffic": list(tables.traffic),
        "trips": list(tables.trips),
        "incidents": list(tables.incidents),
    }
    return mapping.get(table_name, [])


def _inclusion(
    metric_key: str,
    table_name: str,
    record: CanonicalRecord,
    tables: CanonicalTables,
    config: MetricEngineConfig,
    *,
    energy_contract_available: bool,
    task_rsu_target_contract_available: bool,
    vehicle_spatial_grid_contract_available: bool,
    plugin_contract: PluginMetricContract | None,
    plugin_execution_attempted: bool,
) -> tuple[bool, str]:
    values = record.model_dump(mode="python")
    if plugin_contract is not None:
        requirement = next(
            (item for item in plugin_contract.inputs if item.table.value == table_name),
            None,
        )
        if requirement is None:
            return False, "canonical table is not declared by the plugin contract"
        if not plugin_execution_attempted:
            return False, "plugin execution was not attempted because availability failed"
        complete = all(values.get(field) is not None for field in requirement.required_fields)
        if requirement.row_policy is PluginRowPolicy.DROP_INCOMPLETE:
            return _predicate(
                complete,
                "all declared plugin fields are present and the row entered the bounded input",
            )
        return _predicate(
            complete,
            "the complete-row contract was satisfied and the row entered the bounded input",
        )
    if table_name == "tasks":
        if metric_key == "task.completed.count":
            return _predicate(bool(values["completed"]), "completed is true")
        if metric_key.startswith("task.latency."):
            latency = values.get("latency_ms")
            return _predicate(
                isinstance(latency, int | float) and latency >= 0,
                "latency_ms is present and non-negative",
            )
        if metric_key == "task.deadline_miss.completed_observed_rate":
            return _predicate(
                bool(values["completed"]) and values.get("latency_ms") is not None,
                "completed is true and latency_ms is observed",
            )
        if metric_key == "task.drops.by_cause":
            return _predicate(bool(values.get("drop_reason")), "drop_reason is present")
        if metric_key.startswith(("task.energy.", "task.energy_delay_product.")):
            if not energy_contract_available:
                return False, "versioned task-energy contract is unavailable"
            energy = values.get("energy_j")
            energy_valid = (
                isinstance(energy, int | float)
                and not isinstance(energy, bool)
                and math.isfinite(float(energy))
                and energy >= 0
            )
        if metric_key == "task.energy.mean_per_observed_task_j":
            return _predicate(
                energy_valid,
                "energy_j is present, finite, and non-negative under the declared contract",
            )
        if metric_key == "task.energy.per_completed_j":
            return _predicate(
                bool(values["completed"]) and energy_valid,
                "completed is true and energy_j is present, finite, and non-negative",
            )
        if metric_key == "task.energy_delay_product.mean_j_ms":
            latency = values.get("latency_ms")
            latency_valid = (
                isinstance(latency, int | float)
                and not isinstance(latency, bool)
                and math.isfinite(float(latency))
                and latency >= 0
            )
            return _predicate(
                bool(values["completed"]) and energy_valid and latency_valid,
                "completed is true and eligible energy_j and latency_ms are both present",
            )
        if metric_key in VEHICLE_TIER_FAIRNESS_KEYS:
            tiered_ids = set(stable_vehicle_tiers(tables))
            return _predicate(
                str(values["vehicle_id"]) in tiered_ids,
                "task vehicle has a stable non-empty operational tier in the metric scope",
            )
        if metric_key in RSU_TASK_BREAKDOWN_KEYS:
            if not task_rsu_target_contract_available:
                return False, "versioned task-to-RSU target contract is unavailable"
            rsu_ids = {item.rsu_id for item in tables.infrastructure}
            assert isinstance(record, TaskRecord)
            joined = eligible_v2i_target(record, rsu_ids)
            if metric_key.endswith("deadline_miss.completed_observed_rate_by_target"):
                return _predicate(
                    joined and record.completed and record.latency_ms is not None,
                    "task has an exact V2I target join and completed observed latency",
                )
            return _predicate(
                joined,
                "task is V2I with a non-empty exact target_id-to-rsu_id join",
            )
        if metric_key in {
            "task.decision_share.local",
            "task.decision_share.v2i",
            "task.decision_share.v2v",
            "task.offload.rate",
        }:
            return _predicate(
                str(values["decision"]) in {"local", "v2i", "v2v"},
                "decision is one of local, v2i, or v2v and enters the recognised denominator",
            )
        return True, "all accepted task rows enter this metric"
    if table_name == "vehicles":
        if metric_key in VEHICLE_TIER_FAIRNESS_KEYS:
            stable_ids = set(stable_vehicle_tiers(tables))
            return _predicate(
                str(values["vehicle_id"]) in stable_ids and bool(values.get("tier")),
                "tier is present and stable for this vehicle in the metric scope",
            )
        if metric_key in VEHICLE_GRID_KEYS:
            if not vehicle_spatial_grid_contract_available:
                return False, "versioned vehicle spatial-grid contract is unavailable"
            assert isinstance(record, VehicleStateRecord)
            positioned = valid_vehicle_position(record)
            if metric_key == "spatial.vehicle.speed.mean_mps_by_grid_cell":
                return _predicate(
                    positioned and valid_vehicle_speed(record),
                    "finite x/y and finite non-negative speed are present under the grid contract",
                )
            return _predicate(
                positioned,
                "finite x/y are present under the grid contract",
            )
        return True, "all accepted vehicle rows enter this metric"
    if table_name == "infrastructure":
        if metric_key in RSU_TASK_BREAKDOWN_KEYS:
            if not task_rsu_target_contract_available:
                return False, "versioned task-to-RSU target contract is unavailable"
            targeted_ids = {
                task.target_id
                for task in tables.tasks
                if eligible_v2i_target(
                    task,
                    {item.rsu_id for item in tables.infrastructure},
                )
            }
            return _predicate(
                values.get("rsu_id") in targeted_ids,
                "RSU ID is an exact admitted V2I execution target",
            )
        if "queue_length" in metric_key:
            return _predicate(values.get("queue_length") is not None, "queue_length is present")
        if "utilisation" in metric_key:
            return _predicate(
                values.get("utilisation_fraction") is not None,
                "utilisation_fraction is present",
            )
        if metric_key.startswith("infra.saturation."):
            return _predicate(
                values.get("utilisation_fraction") is not None,
                (
                    "utilisation_fraction is present; saturated and non-saturated rows both "
                    f"determine episodes at threshold {config.saturation_threshold}"
                ),
            )
        if metric_key in RSU_FAIRNESS_KEYS:
            assert isinstance(record, InfrastructureRecord)
            return _predicate(
                capacity_normalised_load(record) is not None,
                "non-negative active_tasks and positive capacity are present",
            )
        return True, "all accepted infrastructure rows enter this metric"
    if table_name == "traffic":
        if metric_key.startswith("traffic.count."):
            return _predicate(values.get("count") is not None, "count is present")
        if metric_key.startswith("traffic.speed."):
            return _predicate(
                values.get("average_speed_mps") is not None,
                "average_speed_mps is present",
            )
        return True, "all accepted traffic rows enter this metric"
    if table_name == "trips":
        completed = values.get("duration_s") is not None or values.get("arrival_time_s") is not None
        if metric_key == "trip.completed.count":
            return _predicate(completed, "arrival or duration evidence is present")
        if metric_key == "trip.incomplete.count":
            return _predicate(not completed, "arrival and duration evidence are absent")
        if metric_key.startswith("trip.duration."):
            return _predicate(completed, "an explicit or derived duration is available")
        return True, "all accepted trip rows enter this metric"
    return True, "all accepted rows in the required table enter this metric"


def _predicate(included: bool, positive_reason: str) -> tuple[bool, str]:
    return (
        (True, positive_reason)
        if included
        else (False, "eligibility condition not met: " + positive_reason)
    )


def _record_id(table_name: str, record: CanonicalRecord) -> str:
    values = record.model_dump(mode="python")
    for key in ("task_id", "trip_id", "incident_id"):
        if values.get(key):
            return str(values[key])
    if table_name == "infrastructure":
        return f"{values.get('rsu_id')}@{values.get('timestamp_s')}"
    if table_name == "vehicles":
        return f"{values.get('vehicle_id')}@{values.get('timestamp_s')}"
    if table_name == "traffic":
        return f"{values.get('sensor_id')}@{values.get('timestamp_s')}"
    return f"{record.source_file}:{record.source_row}"


def _canonical_json(values: dict[str, JsonValue]) -> str:
    import json

    return json.dumps(values, sort_keys=True, separators=(",", ":"), allow_nan=False)

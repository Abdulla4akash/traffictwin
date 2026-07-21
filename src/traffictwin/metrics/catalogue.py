"""Central metric catalogue."""

from __future__ import annotations

from typing import TYPE_CHECKING

from traffictwin.metrics.definitions import AggregationScope, MetricDefinition, MetricDomain

if TYPE_CHECKING:
    from traffictwin.metrics.plugins import MetricPluginRegistry
    from traffictwin.metrics.results import MetricValue

METRIC_VERSION = "1.0"

_WINDOW_TASK_KEYS = (
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.completion.rate_by_class",
    "task.completion.rate_by_vehicle_tier",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
    "task.deadline_miss.completed_observed_rate",
    "task.incomplete.rate",
    "task.latency.count",
    "task.latency.mean_ms",
    "task.latency.p50_ms",
    "task.latency.p95_ms",
    "task.latency.p99_ms",
    "task.decision.counts",
    "task.decision_share.local",
    "task.decision_share.v2i",
    "task.decision_share.v2v",
    "task.decision_share.unknown",
    "task.offload.rate",
    "task.drops.by_cause",
    "task.energy.mean_per_observed_task_j",
    "task.energy.per_completed_j",
    "task.energy_delay_product.mean_j_ms",
)
_WINDOW_INFRASTRUCTURE_KEYS = (
    "infra.rsu.summary",
    "infra.observed_rsu.count",
    "infra.queue_length.mean",
    "infra.queue_length.max",
    "infra.utilisation.mean",
    "infra.utilisation.p95",
    "infra.saturation.episode_count",
    "infra.saturation.duration_s",
    "infra.load_balance.jain_capacity_normalised",
    "fairness.rsu.capacity_normalised_load.by_group",
    "fairness.rsu.capacity_normalised_load.max_gap",
)
_WINDOW_RSU_TASK_KEYS = (
    "spatial.rsu.task.count_by_target",
    "spatial.rsu.task.completion_rate_by_target",
    "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
)
_WINDOW_VEHICLE_KEYS = (
    "spatial.vehicle.observation_count_by_grid_cell",
    "spatial.vehicle.distinct_count_by_grid_cell",
    "spatial.vehicle.speed.mean_mps_by_grid_cell",
)
_WINDOW_TRAFFIC_KEYS = (
    "traffic.observation.count",
    "traffic.count.total",
    "traffic.count.mean",
    "traffic.speed.mean_mps",
    "traffic.speed.p50_mps",
    "traffic.speed.p95_mps",
    "traffic.speed.min_mps",
    "traffic.time_coverage",
    "traffic.sensor.count",
)
_WINDOW_TRIP_KEYS = (
    "trip.records.count",
    "trip.completed.count",
    "trip.incomplete.count",
    "trip.completion.rate",
    "trip.duration.count",
    "trip.duration.mean_s",
    "trip.duration.p50_s",
    "trip.duration.p95_s",
    "trip.duration.min_s",
    "trip.duration.max_s",
)

_WINDOW_ANCHORS_BY_KEY = {
    **dict.fromkeys(_WINDOW_TASK_KEYS, "tasks.arrival_time_s"),
    **dict.fromkeys(_WINDOW_INFRASTRUCTURE_KEYS, "infrastructure.timestamp_s"),
    **dict.fromkeys(_WINDOW_RSU_TASK_KEYS, "tasks.arrival_time_s"),
    **dict.fromkeys(_WINDOW_VEHICLE_KEYS, "vehicles.timestamp_s"),
    **dict.fromkeys(_WINDOW_TRAFFIC_KEYS, "traffic.timestamp_s"),
    **dict.fromkeys(_WINDOW_TRIP_KEYS, "trips.departure_time_s"),
}


def _definition(
    key: str,
    name: str,
    description: str,
    domain: MetricDomain,
    unit: str,
    scope: AggregationScope = AggregationScope.RUN,
    *,
    required_tables: list[str] | None = None,
    required_fields: dict[str, list[str]] | None = None,
    higher_is_better: bool | None = None,
    limitations: list[str] | None = None,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        human_name=name,
        description=description,
        domain=domain,
        unit=unit,
        aggregation_scope=scope,
        required_tables=required_tables or [],
        required_fields=required_fields or {},
        implementation_version=METRIC_VERSION,
        higher_is_better=higher_is_better,
        time_window_applicable=key in _WINDOW_ANCHORS_BY_KEY,
        time_anchor=_WINDOW_ANCHORS_BY_KEY.get(key),
        limitations=limitations or [],
    )


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    definition.key: definition
    for definition in [
        _definition(
            "task.generated.count",
            "Tasks generated",
            "Count of valid task records.",
            MetricDomain.TASK,
            "count",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.completed.count",
            "Tasks completed",
            "Count of valid completed task records.",
            MetricDomain.TASK,
            "count",
            required_tables=["tasks"],
            higher_is_better=True,
        ),
        _definition(
            "task.completion.rate",
            "Task completion rate",
            "Completed valid tasks divided by generated valid tasks.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=True,
        ),
        _definition(
            "task.completion.rate_by_class",
            "Completion rate by task class",
            "Completion rate grouped by task class.",
            MetricDomain.TASK,
            "ratio",
            AggregationScope.TASK_CLASS,
            required_tables=["tasks"],
            higher_is_better=True,
        ),
        _definition(
            "task.completion.rate_by_vehicle_tier",
            "Completion rate by vehicle tier",
            "Completion rate grouped by stable operational vehicle tier under the fairness "
            "evidence policy.",
            MetricDomain.TASK,
            "ratio",
            AggregationScope.VEHICLE_TIER,
            required_tables=["tasks", "vehicles"],
            higher_is_better=True,
            limitations=[
                "Vehicle tier is an operational resource group, not a protected or demographic "
                "attribute."
            ],
        ),
        _definition(
            "fairness.vehicle_tier.completion_rate.max_gap",
            "Vehicle-tier completion-rate maximum gap",
            "Maximum minus minimum completion rate across admitted operational vehicle tiers.",
            MetricDomain.FAIRNESS,
            "ratio",
            AggregationScope.VEHICLE_TIER,
            required_tables=["tasks", "vehicles"],
            required_fields={"tasks": ["vehicle_id", "completed"], "vehicles": ["tier"]},
            higher_is_better=False,
            limitations=[
                "A small gap can coexist with uniformly poor completion outcomes.",
                "No protected or demographic attribute is inferred.",
            ],
        ),
        _definition(
            "fairness.vehicle_tier.completion_rate.jain",
            "Vehicle-tier completion-rate Jain index",
            "Jain index over admitted operational vehicle-tier completion rates.",
            MetricDomain.FAIRNESS,
            "index",
            AggregationScope.VEHICLE_TIER,
            required_tables=["tasks", "vehicles"],
            required_fields={"tasks": ["vehicle_id", "completed"], "vehicles": ["tier"]},
            higher_is_better=True,
            limitations=[
                "A high index can coexist with uniformly poor completion outcomes.",
                "Undefined when every admitted group completion rate is zero.",
            ],
        ),
        _definition(
            "task.deadline_miss.completed_observed_rate",
            "Completed-task deadline miss rate",
            "Deadline miss rate over completed tasks with latency and deadline values.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.incomplete.rate",
            "Incomplete task rate",
            "Incomplete valid tasks divided by generated valid tasks.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.latency.count",
            "Latency observation count",
            "Count of non-missing non-negative latency observations.",
            MetricDomain.TASK,
            "count",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.latency.mean_ms",
            "Mean latency",
            "Arithmetic mean of valid latency observations.",
            MetricDomain.TASK,
            "ms",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.latency.p50_ms",
            "P50 latency",
            "50th percentile of valid latency observations.",
            MetricDomain.TASK,
            "ms",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.latency.p95_ms",
            "P95 latency",
            "95th percentile of valid latency observations.",
            MetricDomain.TASK,
            "ms",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.latency.p99_ms",
            "P99 latency",
            "99th percentile of valid latency observations.",
            MetricDomain.TASK,
            "ms",
            required_tables=["tasks"],
            higher_is_better=False,
            limitations=[
                "A sample percentile is descriptive and is not a worst-case or confidence bound."
            ],
        ),
        _definition(
            "task.decision.counts",
            "Decision counts",
            "Counts by canonical decision.",
            MetricDomain.TASK,
            "count",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.decision_share.local",
            "Local decision share",
            "Local decisions divided by recognised decisions.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.decision_share.v2i",
            "V2I decision share",
            "V2I decisions divided by recognised decisions.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.decision_share.v2v",
            "V2V decision share",
            "V2V decisions divided by recognised decisions.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.decision_share.unknown",
            "Unknown decision share",
            "Unknown decisions divided by all decisions.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.offload.rate",
            "Offload rate",
            "V2I plus V2V decisions divided by recognised decisions.",
            MetricDomain.TASK,
            "ratio",
            required_tables=["tasks"],
            higher_is_better=None,
        ),
        _definition(
            "task.drops.by_cause",
            "Drops by cause",
            "Task counts grouped by drop reason when available.",
            MetricDomain.TASK,
            "count",
            required_tables=["tasks"],
            higher_is_better=False,
        ),
        _definition(
            "task.energy.mean_per_observed_task_j",
            "Mean energy per observed task",
            "Mean per-task total energy over task records with eligible energy evidence.",
            MetricDomain.TASK,
            "J/task",
            required_tables=["tasks"],
            required_fields={"tasks": ["energy_j"]},
            higher_is_better=False,
            limitations=[
                "Missing task energy is excluded and reported as coverage, never treated as zero."
            ],
        ),
        _definition(
            "task.energy.per_completed_j",
            "Energy per completed task",
            "Mean per-task total energy over completed tasks with eligible energy evidence.",
            MetricDomain.TASK,
            "J/task",
            required_tables=["tasks"],
            required_fields={"tasks": ["completed", "energy_j"]},
            higher_is_better=False,
            limitations=["Partial completed-task energy coverage is explicit and is not compared."],
        ),
        _definition(
            "task.energy_delay_product.mean_j_ms",
            "Mean energy-delay product",
            "Mean per-task product of total energy in joules and latency in milliseconds over "
            "eligible completed tasks.",
            MetricDomain.TASK,
            "J*ms/task",
            required_tables=["tasks"],
            required_fields={"tasks": ["completed", "energy_j", "latency_ms"]},
            higher_is_better=False,
            limitations=[
                "Available only under an explicit compatible task-energy evidence contract."
            ],
        ),
        _definition(
            "infra.rsu.summary",
            "Per-RSU infrastructure summary",
            "Per-RSU observations, queue, utilisation, arrivals, drops, and active-task summaries.",
            MetricDomain.INFRASTRUCTURE,
            "mixed",
            AggregationScope.RSU,
            required_tables=["infrastructure"],
            higher_is_better=None,
        ),
        _definition(
            "infra.observed_rsu.count",
            "Observed RSU count",
            "Number of RSUs observed in infrastructure records.",
            MetricDomain.INFRASTRUCTURE,
            "count",
            required_tables=["infrastructure"],
            higher_is_better=None,
        ),
        _definition(
            "infra.queue_length.mean",
            "Mean queue length",
            "Mean queue length across valid infrastructure observations.",
            MetricDomain.INFRASTRUCTURE,
            "tasks",
            required_tables=["infrastructure"],
            higher_is_better=False,
        ),
        _definition(
            "infra.queue_length.max",
            "Maximum queue length",
            "Maximum queue length across valid infrastructure observations.",
            MetricDomain.INFRASTRUCTURE,
            "tasks",
            required_tables=["infrastructure"],
            higher_is_better=False,
        ),
        _definition(
            "infra.utilisation.mean",
            "Mean utilisation",
            "Mean utilisation across valid infrastructure observations.",
            MetricDomain.INFRASTRUCTURE,
            "fraction",
            required_tables=["infrastructure"],
            higher_is_better=False,
        ),
        _definition(
            "infra.utilisation.p95",
            "P95 utilisation",
            "95th percentile utilisation across valid infrastructure observations.",
            MetricDomain.INFRASTRUCTURE,
            "fraction",
            required_tables=["infrastructure"],
            higher_is_better=False,
        ),
        _definition(
            "infra.saturation.episode_count",
            "Saturation episode count",
            "Number of per-RSU saturation episodes using configured threshold.",
            MetricDomain.INFRASTRUCTURE,
            "count",
            required_tables=["infrastructure"],
            higher_is_better=False,
        ),
        _definition(
            "infra.saturation.duration_s",
            "Saturation duration",
            "Total observed saturation duration using timestamp differences.",
            MetricDomain.INFRASTRUCTURE,
            "s",
            required_tables=["infrastructure"],
            higher_is_better=False,
            limitations=["Synthetic default threshold is not a validated research threshold."],
        ),
        _definition(
            "infra.load_balance.jain_capacity_normalised",
            "Jain capacity-normalised load balance",
            "Jain index over per-RSU mean active-tasks-to-capacity load under the fairness policy.",
            MetricDomain.FAIRNESS,
            "index",
            AggregationScope.RSU,
            required_tables=["infrastructure"],
            required_fields={"infrastructure": ["rsu_id", "active_tasks", "capacity"]},
            higher_is_better=True,
            limitations=[
                "Load balance does not establish task-outcome equality or causal attribution."
            ],
        ),
        _definition(
            "fairness.rsu.capacity_normalised_load.by_group",
            "Capacity-normalised load by RSU",
            "Mean non-negative active_tasks / positive capacity for each admitted canonical RSU.",
            MetricDomain.FAIRNESS,
            "fraction",
            AggregationScope.RSU,
            required_tables=["infrastructure"],
            required_fields={"infrastructure": ["rsu_id", "active_tasks", "capacity"]},
            higher_is_better=None,
            limitations=["RSU identifiers are operational groups, not spatial attribution."],
        ),
        _definition(
            "fairness.rsu.capacity_normalised_load.max_gap",
            "RSU capacity-normalised load maximum gap",
            "Maximum minus minimum admitted per-RSU mean active-tasks-to-capacity load.",
            MetricDomain.FAIRNESS,
            "fraction",
            AggregationScope.RSU,
            required_tables=["infrastructure"],
            required_fields={"infrastructure": ["rsu_id", "active_tasks", "capacity"]},
            higher_is_better=False,
            limitations=[
                "This is infrastructure load disparity, not per-task RSU outcome attribution."
            ],
        ),
        _definition(
            "spatial.rsu.task.count_by_target",
            "V2I task count by execution-target RSU",
            "Count of canonical V2I tasks grouped by exact evidenced execution-target RSU.",
            MetricDomain.SPATIAL,
            "count",
            AggregationScope.RSU,
            required_tables=["tasks", "infrastructure"],
            required_fields={
                "tasks": ["decision", "target_id"],
                "infrastructure": ["rsu_id"],
            },
            higher_is_better=None,
            limitations=[
                "Requires a versioned task-to-RSU target contract and complete exact joins.",
                "Target lineage is descriptive and is not causal assignment evidence.",
            ],
        ),
        _definition(
            "spatial.rsu.task.completion_rate_by_target",
            "V2I task completion rate by execution-target RSU",
            "Completion rate of canonical V2I tasks grouped by exact evidenced target RSU.",
            MetricDomain.SPATIAL,
            "ratio",
            AggregationScope.RSU,
            required_tables=["tasks", "infrastructure"],
            required_fields={
                "tasks": ["decision", "target_id", "completed"],
                "infrastructure": ["rsu_id"],
            },
            higher_is_better=True,
            limitations=[
                "Unknown or unmatched targets make the family unavailable rather than being "
                "dropped or assigned to a nearest RSU."
            ],
        ),
        _definition(
            "spatial.rsu.task.deadline_miss.completed_observed_rate_by_target",
            "Completed-observed deadline miss rate by execution-target RSU",
            "Deadline misses divided by completed V2I tasks with observed latency, grouped by "
            "exact target RSU.",
            MetricDomain.SPATIAL,
            "ratio",
            AggregationScope.RSU,
            required_tables=["tasks", "infrastructure"],
            required_fields={
                "tasks": ["decision", "target_id", "completed", "latency_ms", "deadline_ms"],
                "infrastructure": ["rsu_id"],
            },
            higher_is_better=False,
            limitations=[
                "Groups without completed observed latency remain null/partial, not zero.",
                "This denominator excludes incomplete tasks, matching the ordinary miss metric.",
            ],
        ),
        _definition(
            "spatial.vehicle.observation_count_by_grid_cell",
            "Vehicle observation count by spatial grid cell",
            "Count of vehicle-state observations assigned to each declared source-frame cell.",
            MetricDomain.SPATIAL,
            "observations",
            AggregationScope.SPATIAL_CELL,
            required_tables=["vehicles"],
            required_fields={"vehicles": ["x", "y"]},
            higher_is_better=None,
            limitations=[
                "Requires a versioned coordinate-frame/grid contract and complete x/y coverage.",
                "Cells are not geographic areas without separate CRS evidence.",
            ],
        ),
        _definition(
            "spatial.vehicle.distinct_count_by_grid_cell",
            "Distinct vehicle count by spatial grid cell",
            "Distinct canonical vehicle IDs observed in each declared source-frame cell.",
            MetricDomain.SPATIAL,
            "vehicles",
            AggregationScope.SPATIAL_CELL,
            required_tables=["vehicles"],
            required_fields={"vehicles": ["vehicle_id", "x", "y"]},
            higher_is_better=None,
            limitations=[
                "A vehicle observed in multiple cells contributes once to each relevant cell."
            ],
        ),
        _definition(
            "spatial.vehicle.speed.mean_mps_by_grid_cell",
            "Mean vehicle speed by spatial grid cell",
            "Arithmetic mean of eligible canonical vehicle speeds in each source-frame cell.",
            MetricDomain.SPATIAL,
            "m/s",
            AggregationScope.SPATIAL_CELL,
            required_tables=["vehicles"],
            required_fields={"vehicles": ["x", "y", "speed_mps"]},
            higher_is_better=None,
            limitations=[
                "Missing speed support remains partial/null and is never replaced with zero.",
                "This is a descriptive source-frame summary, not a congestion cause or map.",
            ],
        ),
        _definition(
            "traffic.observation.count",
            "Traffic observation count",
            "Count of valid traffic observations.",
            MetricDomain.TRAFFIC,
            "count",
            required_tables=["traffic"],
            higher_is_better=None,
        ),
        _definition(
            "traffic.count.total",
            "Total traffic count",
            "Sum of available traffic count observations.",
            MetricDomain.TRAFFIC,
            "vehicles",
            required_tables=["traffic"],
            higher_is_better=None,
        ),
        _definition(
            "traffic.count.mean",
            "Mean traffic count",
            "Mean count per traffic observation.",
            MetricDomain.TRAFFIC,
            "vehicles",
            required_tables=["traffic"],
            higher_is_better=None,
        ),
        _definition(
            "traffic.speed.mean_mps",
            "Mean speed",
            "Mean traffic speed.",
            MetricDomain.TRAFFIC,
            "m/s",
            required_tables=["traffic"],
            higher_is_better=True,
        ),
        _definition(
            "traffic.speed.p50_mps",
            "P50 speed",
            "50th percentile traffic speed.",
            MetricDomain.TRAFFIC,
            "m/s",
            required_tables=["traffic"],
            higher_is_better=True,
        ),
        _definition(
            "traffic.speed.p95_mps",
            "P95 speed",
            "95th percentile traffic speed.",
            MetricDomain.TRAFFIC,
            "m/s",
            required_tables=["traffic"],
            higher_is_better=True,
        ),
        _definition(
            "traffic.speed.min_mps",
            "Minimum speed",
            "Minimum traffic speed.",
            MetricDomain.TRAFFIC,
            "m/s",
            required_tables=["traffic"],
            higher_is_better=True,
        ),
        _definition(
            "traffic.time_coverage",
            "Traffic time coverage",
            "First timestamp, last timestamp, and duration.",
            MetricDomain.TRAFFIC,
            "s",
            required_tables=["traffic"],
            higher_is_better=None,
        ),
        _definition(
            "traffic.sensor.count",
            "Traffic sensor count",
            "Number of observed sensors.",
            MetricDomain.TRAFFIC,
            "count",
            required_tables=["traffic"],
            higher_is_better=None,
        ),
        _definition(
            "trip.records.count",
            "Trip record count",
            "Total trip records.",
            MetricDomain.TRIP,
            "count",
            required_tables=["trips"],
            higher_is_better=None,
        ),
        _definition(
            "trip.completed.count",
            "Completed trip count",
            "Trip records with arrival or valid duration evidence.",
            MetricDomain.TRIP,
            "count",
            required_tables=["trips"],
            higher_is_better=True,
        ),
        _definition(
            "trip.incomplete.count",
            "Incomplete trip count",
            "Trip records without completion evidence.",
            MetricDomain.TRIP,
            "count",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "trip.completion.rate",
            "Trip completion rate",
            "Completed trips divided by total trip records.",
            MetricDomain.TRIP,
            "ratio",
            required_tables=["trips"],
            higher_is_better=True,
        ),
        _definition(
            "trip.duration.count",
            "Trip duration observation count",
            "Count of valid trip duration observations.",
            MetricDomain.TRIP,
            "count",
            required_tables=["trips"],
            higher_is_better=None,
        ),
        _definition(
            "trip.duration.mean_s",
            "Mean trip duration",
            "Mean valid trip duration.",
            MetricDomain.TRIP,
            "s",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "trip.duration.p50_s",
            "P50 trip duration",
            "50th percentile trip duration.",
            MetricDomain.TRIP,
            "s",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "trip.duration.p95_s",
            "P95 trip duration",
            "95th percentile trip duration.",
            MetricDomain.TRIP,
            "s",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "trip.duration.min_s",
            "Minimum trip duration",
            "Minimum valid trip duration.",
            MetricDomain.TRIP,
            "s",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "trip.duration.max_s",
            "Maximum trip duration",
            "Maximum valid trip duration.",
            MetricDomain.TRIP,
            "s",
            required_tables=["trips"],
            higher_is_better=False,
        ),
        _definition(
            "comparison.absolute_delta",
            "Absolute delta",
            "Variation metric value minus baseline metric value.",
            MetricDomain.COMPARISON,
            "metric_unit",
            AggregationScope.SEED_PAIR,
            higher_is_better=None,
        ),
        _definition(
            "comparison.relative_delta",
            "Relative delta",
            "Absolute delta divided by the absolute baseline value, "
            "with explicit zero-baseline handling.",
            MetricDomain.COMPARISON,
            "ratio",
            AggregationScope.SEED_PAIR,
            higher_is_better=None,
        ),
        _definition(
            "comparison.seed_aligned_difference",
            "Seed-aligned difference",
            "Difference for runs aligned by experiment and random seed where required.",
            MetricDomain.COMPARISON,
            "metric_unit",
            AggregationScope.SEED_PAIR,
            higher_is_better=None,
        ),
    ]
}


def metric_catalogue(
    plugin_registry: MetricPluginRegistry | None = None,
) -> dict[str, MetricDefinition]:
    """Return the core catalogue plus explicitly admitted local extensions."""

    definitions = dict(METRIC_DEFINITIONS)
    if plugin_registry is not None:
        definitions.update(plugin_registry.definitions())
    return {key: definitions[key] for key in sorted(definitions)}


def get_metric_definition(
    key: str,
    plugin_registry: MetricPluginRegistry | None = None,
) -> MetricDefinition:
    """Return a metric definition by key."""

    return metric_catalogue(plugin_registry)[key]


def window_metric_catalogue(
    plugin_registry: MetricPluginRegistry | None = None,
) -> dict[str, MetricDefinition]:
    """Return metrics with a declared deterministic time anchor."""

    return {
        key: definition
        for key, definition in metric_catalogue(plugin_registry).items()
        if definition.time_window_applicable
    }


def metric_definition_for_result(metric: MetricValue) -> MetricDefinition | None:
    """Resolve a core definition or a validated definition embedded by the plugin engine."""

    definition = METRIC_DEFINITIONS.get(metric.metric_key)
    if definition is not None:
        return definition
    from traffictwin.metrics.plugins import plugin_contract_from_metric

    contract = plugin_contract_from_metric(metric)
    if contract is None or contract.definition.key != metric.metric_key:
        return None
    return contract.definition

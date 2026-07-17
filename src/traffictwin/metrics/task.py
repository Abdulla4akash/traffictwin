"""Task metric calculators."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from traffictwin.canonical.records import TaskRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricValue, RunMetricContext, UnavailableReason
from traffictwin.metrics.statistics import arithmetic_mean, percentile_linear

TASK_KEYS = [
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.completion.rate_by_class",
    "task.completion.rate_by_vehicle_tier",
    "task.deadline_miss.completed_observed_rate",
    "task.incomplete.rate",
    "task.latency.count",
    "task.latency.mean_ms",
    "task.latency.p50_ms",
    "task.latency.p95_ms",
    "task.decision.counts",
    "task.decision_share.local",
    "task.decision_share.v2i",
    "task.decision_share.v2v",
    "task.decision_share.unknown",
    "task.offload.rate",
    "task.drops.by_cause",
    "task.energy.per_completed_j",
]


def task_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Compute task metrics."""

    if evidence.tasks is not EvidenceStatus.AVAILABLE:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
                ["tasks"],
            )
            for key in TASK_KEYS
        ]

    tasks = list(tables.tasks)
    generated = len(tasks)
    if generated == 0:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.NO_VALID_ROWS],
                ["tasks"],
            )
            for key in TASK_KEYS
        ]

    completed = sum(1 for task in tasks if task.completed)
    incomplete = generated - completed
    latencies = [
        task.latency_ms for task in tasks if task.latency_ms is not None and task.latency_ms >= 0
    ]
    decision_counts = Counter(task.decision.value for task in tasks)
    recognised_count = sum(
        decision_counts[decision.value] for decision in (Decision.LOCAL, Decision.V2I, Decision.V2V)
    )
    results = [
        available_metric("task.generated.count", generated, context, config, computed_at),
        available_metric("task.completed.count", completed, context, config, computed_at),
        available_metric(
            "task.completion.rate", completed / generated, context, config, computed_at
        ),
        available_metric(
            "task.incomplete.rate", incomplete / generated, context, config, computed_at
        ),
        available_metric(
            "task.completion.rate_by_class",
            _completion_rate_by_class(tasks),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.decision.counts",
            {decision.value: decision_counts[decision.value] for decision in Decision},
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.decision_share.local",
            _share(decision_counts[Decision.LOCAL.value], recognised_count),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.decision_share.v2i",
            _share(decision_counts[Decision.V2I.value], recognised_count),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.decision_share.v2v",
            _share(decision_counts[Decision.V2V.value], recognised_count),
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.decision_share.unknown",
            decision_counts[Decision.UNKNOWN.value] / generated,
            context,
            config,
            computed_at,
        ),
        available_metric(
            "task.offload.rate",
            _share(
                decision_counts[Decision.V2I.value] + decision_counts[Decision.V2V.value],
                recognised_count,
            ),
            context,
            config,
            computed_at,
        ),
    ]
    results.extend(_latency_metrics(latencies, context, config, computed_at))
    results.append(_deadline_miss_metric(tasks, context, config, computed_at))
    results.append(_vehicle_tier_metric(tables, context, config, computed_at))
    results.append(_drops_metric(tasks, context, config, computed_at))
    results.append(_energy_metric(tasks, context, config, computed_at))
    return results


def _completion_rate_by_class(tasks: list[TaskRecord]) -> dict[str, float | None]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for task in tasks:
        grouped[task.task_class.value].append(task.completed)
    result: dict[str, float | None] = {}
    for task_class in TaskClass:
        values = grouped.get(task_class.value, [])
        result[task_class.value] = None if not values else sum(values) / len(values)
    return result


def _latency_metrics(
    latencies: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    if not latencies:
        return [
            available_metric("task.latency.count", 0, context, config, computed_at),
            unavailable_metric(
                "task.latency.mean_ms",
                context,
                config,
                computed_at,
                [UnavailableReason.NO_LATENCY_VALUES],
                ["tasks.latency_ms"],
            ),
            unavailable_metric(
                "task.latency.p50_ms",
                context,
                config,
                computed_at,
                [UnavailableReason.NO_LATENCY_VALUES],
                ["tasks.latency_ms"],
            ),
            unavailable_metric(
                "task.latency.p95_ms",
                context,
                config,
                computed_at,
                [UnavailableReason.NO_LATENCY_VALUES],
                ["tasks.latency_ms"],
            ),
        ]
    return [
        available_metric("task.latency.count", len(latencies), context, config, computed_at),
        available_metric(
            "task.latency.mean_ms", arithmetic_mean(latencies), context, config, computed_at
        ),
        available_metric(
            "task.latency.p50_ms", percentile_linear(latencies, 0.50), context, config, computed_at
        ),
        available_metric(
            "task.latency.p95_ms", percentile_linear(latencies, 0.95), context, config, computed_at
        ),
    ]


def _deadline_miss_metric(
    tasks: list[TaskRecord],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    observed = [task for task in tasks if task.completed and task.latency_ms is not None]
    if not observed:
        return unavailable_metric(
            "task.deadline_miss.completed_observed_rate",
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
            ["tasks.latency_ms"],
        )
    misses = sum(
        1 for task in observed if task.latency_ms is not None and task.latency_ms > task.deadline_ms
    )
    return available_metric(
        "task.deadline_miss.completed_observed_rate",
        misses / len(observed),
        context,
        config,
        computed_at,
        metadata={"denominator": len(observed), "incomplete_tasks_excluded": True},
    )


def _vehicle_tier_metric(
    tables: CanonicalTables,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    tiers = {vehicle.vehicle_id: vehicle.tier for vehicle in tables.vehicles if vehicle.tier}
    if not tiers:
        return unavailable_metric(
            "task.completion.rate_by_vehicle_tier",
            context,
            config,
            computed_at,
            [UnavailableReason.VEHICLE_TIER_UNAVAILABLE],
            ["vehicles.tier"],
        )
    grouped: dict[str, list[bool]] = defaultdict(list)
    for task in tables.tasks:
        tier = tiers.get(task.vehicle_id)
        if tier:
            grouped[tier].append(task.completed)
    values = {tier: sum(completed) / len(completed) for tier, completed in sorted(grouped.items())}
    return available_metric(
        "task.completion.rate_by_vehicle_tier", values, context, config, computed_at
    )


def _drops_metric(
    tasks: list[TaskRecord],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    reasons = Counter(task.drop_reason for task in tasks if task.drop_reason)
    if not reasons:
        return unavailable_metric(
            "task.drops.by_cause",
            context,
            config,
            computed_at,
            [UnavailableReason.METRIC_NOT_APPLICABLE],
            ["tasks.drop_reason"],
        )
    return available_metric(
        "task.drops.by_cause", dict(sorted(reasons.items())), context, config, computed_at
    )


def _energy_metric(
    tasks: list[TaskRecord],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    energies = [task.energy_j for task in tasks if task.completed and task.energy_j is not None]
    if not energies:
        return unavailable_metric(
            "task.energy.per_completed_j",
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
            ["tasks.energy_j"],
        )
    return available_metric(
        "task.energy.per_completed_j",
        arithmetic_mean(energies),
        context,
        config,
        computed_at,
    )


def _share(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator

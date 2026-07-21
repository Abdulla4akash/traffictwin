"""Task metric calculators."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime

from traffictwin.canonical.records import TaskRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.energy import TaskEnergyContract
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonObject,
    MetricStatus,
    MetricValue,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.statistics import (
    PERCENTILE_METHOD_VERSION,
    arithmetic_mean,
    percentile_linear,
)

TASK_KEYS = [
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.completion.rate_by_class",
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
        task.latency_ms
        for task in tasks
        if task.latency_ms is not None and math.isfinite(task.latency_ms) and task.latency_ms >= 0
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
    results.append(_drops_metric(tasks, context, config, computed_at))
    results.extend(_energy_metrics(tasks, context, config, computed_at))
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
    percentile_specs = (
        ("task.latency.p50_ms", 0.50),
        ("task.latency.p95_ms", 0.95),
        ("task.latency.p99_ms", 0.99),
    )
    if not latencies:
        results = [
            available_metric("task.latency.count", 0, context, config, computed_at),
            unavailable_metric(
                "task.latency.mean_ms",
                context,
                config,
                computed_at,
                [UnavailableReason.NO_LATENCY_VALUES],
                ["tasks.latency_ms"],
            ),
        ]
        results.extend(
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.NO_LATENCY_VALUES],
                ["tasks.latency_ms"],
                metadata=_percentile_metadata(percentile, 0, config),
            )
            for key, percentile in percentile_specs
        )
        return results
    results = [
        available_metric("task.latency.count", len(latencies), context, config, computed_at),
        available_metric(
            "task.latency.mean_ms", arithmetic_mean(latencies), context, config, computed_at
        ),
    ]
    results.extend(
        _latency_percentile_metric(
            key,
            percentile,
            latencies,
            context,
            config,
            computed_at,
        )
        for key, percentile in percentile_specs
    )
    return results


def _latency_percentile_metric(
    key: str,
    percentile: float,
    latencies: list[float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> MetricValue:
    metadata = _percentile_metadata(percentile, len(latencies), config)
    if len(latencies) < config.minimum_sample_size:
        return unavailable_metric(
            key,
            context,
            config,
            computed_at,
            [UnavailableReason.INSUFFICIENT_SAMPLE_SIZE],
            ["tasks.latency_ms"],
            metadata=metadata,
        )
    warnings = []
    if len(latencies) == 1:
        warnings.append("Single-observation percentile equals the sole valid latency observation.")
    return available_metric(
        key,
        percentile_linear(latencies, percentile),
        context,
        config,
        computed_at,
        warnings=warnings,
        metadata=metadata,
    )


def _percentile_metadata(
    percentile: float,
    sample_count: int,
    config: MetricEngineConfig,
) -> JsonObject:
    return {
        "percentile_fraction": percentile,
        "percentile_method": config.percentile_method,
        "percentile_method_version": PERCENTILE_METHOD_VERSION,
        "sample_count": sample_count,
        "minimum_sample_size": config.minimum_sample_size,
    }


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


def _energy_metrics(
    tasks: list[TaskRecord],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    keys = (
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
        "task.energy_delay_product.mean_j_ms",
    )
    contract = context.energy_contract
    if contract is None:
        return [
            unavailable_metric(
                key,
                context,
                config,
                computed_at,
                [UnavailableReason.ENERGY_CONTRACT_UNAVAILABLE],
                ["manifest.energy_contract"],
                metadata={"energy_family_version": "1.0"},
            )
            for key in keys
        ]

    observed_energy = [
        energy for task in tasks if (energy := task.energy_j) is not None and _valid_energy(energy)
    ]
    completed = [task for task in tasks if task.completed]
    completed_energy = [
        energy
        for task in completed
        if (energy := task.energy_j) is not None and _valid_energy(energy)
    ]
    energy_delay_products = [
        task.energy_j * task.latency_ms
        for task in completed
        if _valid_energy(task.energy_j)
        and _valid_latency(task.latency_ms)
        and task.energy_j is not None
        and task.latency_ms is not None
    ]
    return [
        _energy_mean_metric(
            "task.energy.mean_per_observed_task_j",
            observed_energy,
            len(tasks),
            contract.per_task_eligibility,
            contract,
            context,
            config,
            computed_at,
            missing=["tasks.energy_j"],
            partial_when_incomplete=False,
        ),
        _energy_mean_metric(
            "task.energy.per_completed_j",
            completed_energy,
            len(completed),
            contract.per_completed_eligibility,
            contract,
            context,
            config,
            computed_at,
            missing=["tasks.completed", "tasks.energy_j"],
            partial_when_incomplete=True,
        ),
        _energy_mean_metric(
            "task.energy_delay_product.mean_j_ms",
            energy_delay_products,
            len(completed),
            contract.energy_delay_eligibility,
            contract,
            context,
            config,
            computed_at,
            missing=["tasks.completed", "tasks.energy_j", "tasks.latency_ms"],
            partial_when_incomplete=True,
        ),
    ]


def _energy_mean_metric(
    key: str,
    values: list[float],
    population_count: int,
    eligibility_policy: str,
    contract: TaskEnergyContract,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    *,
    missing: list[str],
    partial_when_incomplete: bool,
) -> MetricValue:
    metadata = _energy_metadata(
        contract,
        eligibility_policy,
        eligible_count=len(values),
        population_count=population_count,
    )
    if not values:
        return unavailable_metric(
            key,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_FIELD_UNAVAILABLE],
            missing,
            metadata=metadata,
        )
    warnings = []
    incomplete_count = max(0, population_count - len(values))
    if incomplete_count:
        warnings.append(
            f"{incomplete_count} in-scope task record(s) lacked eligible energy evidence and "
            "were excluded rather than treated as zero."
        )
    status = (
        MetricStatus.PARTIAL
        if partial_when_incomplete and incomplete_count
        else MetricStatus.AVAILABLE
    )
    return available_metric(
        key,
        arithmetic_mean(values),
        context,
        config,
        computed_at,
        warnings=warnings,
        metadata=metadata,
        status=status,
    )


def _energy_metadata(
    contract: TaskEnergyContract,
    eligibility_policy: str,
    *,
    eligible_count: int,
    population_count: int,
) -> JsonObject:
    return {
        "energy_family_version": "1.0",
        "energy_contract_fingerprint": contract.fingerprint(),
        "energy_contract_version": contract.schema_version,
        "energy_quantity": contract.quantity,
        "energy_unit": contract.canonical_energy_unit,
        "delay_unit": contract.canonical_delay_unit,
        "eligibility_policy": eligibility_policy,
        "eligible_count": eligible_count,
        "population_count": population_count,
        "coverage_fraction": eligible_count / population_count if population_count else None,
    }


def _valid_energy(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value >= 0


def _valid_latency(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value >= 0


def _share(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator

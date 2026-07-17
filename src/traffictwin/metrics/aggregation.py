"""Experiment-level metric aggregation."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.results import (
    JsonScalar,
    MetricCollection,
    MetricStatus,
    UnavailableReason,
)
from traffictwin.metrics.statistics import (
    arithmetic_mean,
    paired_differences,
    percentile_linear,
    sample_standard_deviation,
)

DEFAULT_AGGREGATE_METRICS = [
    "task.completion.rate",
    "task.latency.p95_ms",
    "infra.queue_length.mean",
    "infra.utilisation.mean",
    "traffic.speed.mean_mps",
    "trip.duration.mean_s",
]


class AggregateMetricSummary(BaseModel):
    """Descriptive aggregate for one scalar metric."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    status: str
    n: int
    mean: float | None = None
    sample_sd: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    p50: float | None = None
    reason_codes: list[UnavailableReason] = Field(default_factory=list)


class ConditionSummary(BaseModel):
    """Aggregated metrics for a seed/algorithm/checkpoint condition."""

    model_config = ConfigDict(extra="forbid")

    condition_id: str
    experiment_id: str | None
    seed_id: str | None
    algorithm: str | None
    checkpoint: str | None
    run_count: int
    random_seeds: list[int]
    metrics: list[AggregateMetricSummary]


class PairedDifferenceSummary(BaseModel):
    """Paired variation-baseline differences by common random seed."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    baseline_seed_id: str
    variation_seed_id: str
    paired_count: int
    unmatched_baseline_random_seeds: list[int]
    unmatched_variation_random_seeds: list[int]
    mean_paired_difference: float | None = None
    sample_sd_paired_difference: float | None = None


class ExperimentAggregationReport(BaseModel):
    """Experiment-level descriptive aggregation report."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str | None
    metric_version: str | None
    generated_at: datetime
    condition_count: int
    conditions: list[ConditionSummary]
    paired_differences: list[PairedDifferenceSummary] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return JSON output."""

        return self.model_dump_json(indent=2)


def aggregate_experiment(
    collections: list[MetricCollection],
    *,
    metric_keys: list[str] | None = None,
    baseline_seed_id: str | None = None,
    variation_seed_id: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ExperimentAggregationReport:
    """Aggregate compatible metric collections by condition."""

    generated_at = clock() if clock is not None else datetime.now(UTC)
    keys = metric_keys or DEFAULT_AGGREGATE_METRICS
    grouped: dict[tuple[JsonScalar, JsonScalar, JsonScalar, JsonScalar], list[MetricCollection]] = (
        defaultdict(list)
    )
    for collection in collections:
        context = _context(collection)
        grouped[
            (
                context["experiment_id"],
                context["seed_id"],
                context["algorithm"],
                context["checkpoint"],
            )
        ].append(collection)

    conditions = [
        _condition_summary(group, keys)
        for _, group in sorted(grouped.items(), key=lambda item: _condition_sort_key(item[0]))
    ]
    paired = []
    if baseline_seed_id is not None and variation_seed_id is not None:
        paired = [
            paired_metric_difference(collections, baseline_seed_id, variation_seed_id, key)
            for key in keys
        ]
    return ExperimentAggregationReport(
        experiment_id=_single_or_none(
            context["experiment_id"] for context in map(_context, collections)
        ),
        metric_version=_single_or_none(collection.metric_version for collection in collections),
        generated_at=generated_at,
        condition_count=len(conditions),
        conditions=conditions,
        paired_differences=paired,
    )


def paired_metric_difference(
    collections: list[MetricCollection],
    baseline_seed_id: str,
    variation_seed_id: str,
    metric_key: str,
) -> PairedDifferenceSummary:
    """Calculate paired differences for one scalar metric by random seed."""

    baseline_values: dict[int, float] = {}
    variation_values: dict[int, float] = {}
    for collection in collections:
        context = _context(collection)
        value = _numeric_metric_value(collection, metric_key)
        if value is None or context["random_seed"] is None:
            continue
        random_seed = int(context["random_seed"])
        if context["seed_id"] == baseline_seed_id:
            baseline_values[random_seed] = value
        elif context["seed_id"] == variation_seed_id:
            variation_values[random_seed] = value

    differences, unmatched_baseline, unmatched_variation = paired_differences(
        baseline_values,
        variation_values,
    )
    return PairedDifferenceSummary(
        metric_key=metric_key,
        baseline_seed_id=baseline_seed_id,
        variation_seed_id=variation_seed_id,
        paired_count=len(differences),
        unmatched_baseline_random_seeds=unmatched_baseline,
        unmatched_variation_random_seeds=unmatched_variation,
        mean_paired_difference=arithmetic_mean(differences),
        sample_sd_paired_difference=sample_standard_deviation(differences),
    )


def aggregate_metric_values(
    collections: list[MetricCollection],
    metric_key: str,
) -> AggregateMetricSummary:
    """Aggregate one scalar metric across metric collections."""

    values = [
        value
        for collection in collections
        if (value := _numeric_metric_value(collection, metric_key)) is not None
    ]
    if not values:
        return AggregateMetricSummary(
            metric_key=metric_key,
            status="unavailable",
            n=0,
            reason_codes=[UnavailableReason.NO_VALID_ROWS],
        )
    return AggregateMetricSummary(
        metric_key=metric_key,
        status="available",
        n=len(values),
        mean=arithmetic_mean(values),
        sample_sd=sample_standard_deviation(values),
        minimum=min(values),
        maximum=max(values),
        p50=percentile_linear(values, 0.50),
    )


def _condition_summary(
    collections: list[MetricCollection],
    metric_keys: list[str],
) -> ConditionSummary:
    context = _context(collections[0])
    return ConditionSummary(
        condition_id="|".join(
            str(context[key] or "")
            for key in ("experiment_id", "seed_id", "algorithm", "checkpoint")
        ),
        experiment_id=str(context["experiment_id"])
        if context["experiment_id"] is not None
        else None,
        seed_id=str(context["seed_id"]) if context["seed_id"] is not None else None,
        algorithm=str(context["algorithm"]) if context["algorithm"] is not None else None,
        checkpoint=str(context["checkpoint"]) if context["checkpoint"] is not None else None,
        run_count=len(collections),
        random_seeds=sorted(
            int(seed)
            for collection in collections
            if (seed := _context(collection)["random_seed"]) is not None
        ),
        metrics=[aggregate_metric_values(collections, key) for key in metric_keys],
    )


def _numeric_metric_value(collection: MetricCollection, metric_key: str) -> float | None:
    metric = collection.by_key().get(metric_key)
    if metric is None or metric.status is not MetricStatus.AVAILABLE:
        return None
    if not isinstance(metric.value, int | float) or isinstance(metric.value, bool):
        return None
    if not math.isfinite(float(metric.value)):
        return None
    return float(metric.value)


def _context(collection: MetricCollection) -> dict[str, JsonScalar]:
    first = collection.results[0] if collection.results else None
    return {
        "experiment_id": first.experiment_id if first else None,
        "seed_id": first.seed_id if first else None,
        "algorithm": first.algorithm if first else None,
        "checkpoint": first.checkpoint if first else None,
        "random_seed": first.random_seed if first else None,
    }


def _condition_sort_key(
    key: tuple[JsonScalar, JsonScalar, JsonScalar, JsonScalar],
) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in key)


def _single_or_none(values: Iterable[object]) -> str | None:
    unique = {value for value in values if value is not None}
    if len(unique) == 1:
        return str(next(iter(unique)))
    return None

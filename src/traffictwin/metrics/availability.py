"""Metric availability helpers."""

from __future__ import annotations

from datetime import datetime

from traffictwin.metrics.catalogue import get_metric_definition
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonObject,
    JsonScalar,
    JsonValue,
    MetricStatus,
    MetricValue,
    RunMetricContext,
    UnavailableReason,
)


def unavailable_metric(
    key: str,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    reasons: list[UnavailableReason],
    missing: list[str],
    warnings: list[str] | None = None,
    *,
    status: MetricStatus = MetricStatus.UNAVAILABLE,
    metadata: JsonObject | None = None,
) -> MetricValue:
    """Build an unavailable metric value from its definition."""

    definition = get_metric_definition(key)
    return MetricValue(
        metric_key=key,
        status=status,
        value=None,
        unit=definition.unit,
        scope=definition.aggregation_scope.value,
        required_evidence=definition.required_tables,
        missing_evidence=missing,
        reason_codes=reasons,
        warnings=warnings or [],
        implementation_version=config.metric_version,
        run_id=context.run_id,
        experiment_id=context.experiment_id,
        seed_id=context.seed_id,
        algorithm=context.algorithm,
        checkpoint=context.checkpoint,
        random_seed=context.random_seed,
        synthetic=context.synthetic,
        environment=context.environment,
        environment_version=context.environment_version,
        environment_commit=context.environment_commit,
        computed_at=computed_at,
        metadata=metadata or {},
    )


def available_metric(
    key: str,
    value: JsonValue,
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    *,
    dimensions: dict[str, JsonScalar] | None = None,
    warnings: list[str] | None = None,
    metadata: JsonObject | None = None,
    status: MetricStatus = MetricStatus.AVAILABLE,
) -> MetricValue:
    """Build an available metric value from its definition."""

    definition = get_metric_definition(key)
    return MetricValue(
        metric_key=key,
        status=status,
        value=value,
        unit=definition.unit,
        scope=definition.aggregation_scope.value,
        dimensions=dimensions or {},
        required_evidence=definition.required_tables,
        warnings=warnings or [],
        implementation_version=config.metric_version,
        run_id=context.run_id,
        experiment_id=context.experiment_id,
        seed_id=context.seed_id,
        algorithm=context.algorithm,
        checkpoint=context.checkpoint,
        random_seed=context.random_seed,
        synthetic=context.synthetic,
        environment=context.environment,
        environment_version=context.environment_version,
        environment_commit=context.environment_commit,
        computed_at=computed_at,
        metadata=metadata or {},
    )

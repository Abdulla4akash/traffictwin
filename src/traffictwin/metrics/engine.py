"""Central metric engine."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.availability import unavailable_metric
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.comparison import comparison_placeholder_metrics
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.fairness import fairness_metrics
from traffictwin.metrics.infrastructure import infrastructure_metrics
from traffictwin.metrics.plugins import (
    MetricPluginRegistry,
    compute_plugin_metrics,
    invalid_plugin_metrics,
)
from traffictwin.metrics.results import (
    MetricCollection,
    MetricStatus,
    RunMetricContext,
    UnavailableReason,
)
from traffictwin.metrics.spatial import spatial_metrics
from traffictwin.metrics.task import task_metrics
from traffictwin.metrics.traffic import traffic_metrics
from traffictwin.metrics.trips import trip_metrics


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def compute_metrics(
    canonical_tables: CanonicalTables,
    run_context: RunMetricContext,
    evidence_availability: EvidenceAvailability,
    config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> MetricCollection:
    """Compute deterministic metrics over canonical records."""

    engine_config = config or MetricEngineConfig()
    generated_at = clock()
    if not run_context.validation_may_import:
        results = [
            unavailable_metric(
                key,
                run_context,
                engine_config,
                generated_at,
                [UnavailableReason.INVALID_SOURCE_DATA],
                ["validation"],
                status=MetricStatus.INVALID,
            )
            for key in metric_catalogue()
        ]
        if plugin_registry is not None:
            results.extend(invalid_plugin_metrics(plugin_registry, run_context, generated_at))
    else:
        results = [
            *task_metrics(
                canonical_tables, run_context, evidence_availability, engine_config, generated_at
            ),
            *infrastructure_metrics(
                canonical_tables,
                run_context,
                evidence_availability,
                engine_config,
                generated_at,
            ),
            *fairness_metrics(
                canonical_tables,
                run_context,
                evidence_availability,
                engine_config,
                generated_at,
            ),
            *spatial_metrics(
                canonical_tables,
                run_context,
                evidence_availability,
                engine_config,
                generated_at,
            ),
            *traffic_metrics(
                canonical_tables, run_context, evidence_availability, engine_config, generated_at
            ),
            *trip_metrics(
                canonical_tables, run_context, evidence_availability, engine_config, generated_at
            ),
            *(
                compute_plugin_metrics(
                    plugin_registry,
                    canonical_tables,
                    run_context,
                    evidence_availability,
                    engine_config,
                    generated_at,
                )
                if plugin_registry is not None
                else []
            ),
            *comparison_placeholder_metrics(run_context, engine_config, generated_at),
        ]
    results = sorted(results, key=lambda metric: metric.metric_key)
    return MetricCollection(
        run_id=run_context.run_id,
        metric_version=engine_config.metric_version,
        results=results,
        unavailable_count=sum(1 for metric in results if metric.status is MetricStatus.UNAVAILABLE),
        partial_count=sum(1 for metric in results if metric.status is MetricStatus.PARTIAL),
        generated_at=generated_at,
        input_fingerprint=run_context.source_bundle_fingerprint,
    )


def run_context_from_bundle(result: BundleValidationResult) -> RunMetricContext:
    """Build metric run context from a validated bundle result."""

    if result.manifest is None:
        raise ValueError("bundle manifest is required for metric context")
    manifest = result.manifest
    return RunMetricContext(
        run_id=manifest.run.run_id,
        experiment_id=manifest.run.experiment_id,
        seed_id=manifest.run.seed_id,
        algorithm=manifest.run.algorithm,
        checkpoint=manifest.run.checkpoint,
        random_seed=manifest.run.random_seed,
        synthetic=manifest.environment.name == "synthetic",
        environment=manifest.environment.name,
        environment_version=manifest.environment.version,
        environment_commit=manifest.environment.commit,
        source_bundle_fingerprint=result.fingerprint,
        energy_contract=manifest.energy_contract,
        task_rsu_target_contract=manifest.task_rsu_target_contract,
        vehicle_spatial_grid_contract=manifest.vehicle_spatial_grid_contract,
        validation_may_import=result.report.may_import,
    )


def compute_metrics_for_bundle(
    result: BundleValidationResult,
    config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> MetricCollection:
    """Compute metrics from a Phase 2 bundle validation result."""

    return compute_metrics(
        result.canonical,
        run_context_from_bundle(result),
        result.evidence,
        config,
        plugin_registry=plugin_registry,
        clock=clock,
    )

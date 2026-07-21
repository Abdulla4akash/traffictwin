"""Deterministic canonical metrics for validated SUMO result packages."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from traffictwin.integration.sumo.models import SumoValidationResult
from traffictwin.metrics.engine import compute_metrics, utc_now
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginRegistry
from traffictwin.metrics.results import MetricCollection, RunMetricContext


def run_context_from_sumo(result: SumoValidationResult) -> RunMetricContext:
    """Build metric provenance from the declared SUMO source manifest."""

    if result.manifest is None:
        raise ValueError("SUMO result manifest is required for metric context")
    manifest = result.manifest
    return RunMetricContext(
        run_id=manifest.run.run_id,
        experiment_id=manifest.run.experiment_id,
        seed_id=manifest.run.seed_id,
        algorithm=manifest.run.algorithm,
        random_seed=manifest.run.random_seed,
        synthetic=manifest.source.synthetic,
        environment="sumo",
        environment_version=manifest.source.sumo_version,
        environment_commit=manifest.source.source_commit,
        source_bundle_fingerprint=result.fingerprint,
        validation_may_import=result.report.may_import,
    )


def compute_metrics_for_sumo(
    result: SumoValidationResult,
    config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> MetricCollection:
    """Compute existing deterministic metrics over supported canonical SUMO trips."""

    return compute_metrics(
        result.canonical,
        run_context_from_sumo(result),
        result.evidence,
        config,
        plugin_registry=plugin_registry,
        clock=clock,
    )

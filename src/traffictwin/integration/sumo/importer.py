"""Idempotent registry import for validated SUMO result packages."""

from __future__ import annotations

from pathlib import Path

from traffictwin.domain.enums import ExecutionMode, RunStatus, ValidationStatus
from traffictwin.domain.run import Run
from traffictwin.integration.sumo.metrics import compute_metrics_for_sumo
from traffictwin.integration.sumo.models import SumoImportResult, SumoValidationResult
from traffictwin.integration.sumo.validation import validate_sumo_results
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.storage.registry import Registry


def import_sumo_results(
    path: str | Path,
    registry_path: str | Path,
    *,
    validation_result: SumoValidationResult | None = None,
    metric_config: MetricEngineConfig | None = None,
) -> SumoImportResult:
    """Validate, register, and store canonical metrics without modifying raw XML."""

    result = validation_result or validate_sumo_results(path)
    if result.manifest is None or result.fingerprint is None or not result.report.may_import:
        return SumoImportResult(
            bundle_id=result.report.bundle_id,
            run_id=result.report.run_id,
            status="rejected",
            message="SUMO result package rejected; registry was not mutated",
        )
    manifest = result.manifest
    run = Run(
        run_id=manifest.run.run_id,
        experiment_id=manifest.run.experiment_id,
        seed_id=manifest.run.seed_id,
        algorithm=manifest.run.algorithm,
        random_seed=manifest.run.random_seed,
        environment_version=manifest.source.sumo_version,
        environment_commit=manifest.source.source_commit,
        execution_mode=ExecutionMode.IMPORTED,
        status=RunStatus.IMPORTED,
        source_bundle=str(Path(path)),
        validation_status=ValidationStatus.VALID,
    )
    registry = Registry(registry_path)
    imported = registry.register_bundle_import(
        run=run,
        bundle_id=manifest.bundle.bundle_id,
        source_reference=str(Path(path)),
        fingerprint=result.fingerprint,
        manifest_json=manifest.model_dump_json(),
        validation_report_json=result.report.to_json(),
        import_status=result.report.status.value,
    )
    metrics_stored = False
    if imported.created:
        metrics = compute_metrics_for_sumo(result, metric_config)
        metrics_stored = registry.store_metric_collection(
            run_id=metrics.run_id,
            metric_version=metrics.metric_version,
            source_fingerprint=metrics.input_fingerprint,
            payload_json=metrics.model_dump_json(),
        )
    return SumoImportResult(
        bundle_id=imported.bundle_id,
        run_id=imported.run_id,
        created=imported.created,
        idempotent=imported.idempotent,
        status=imported.status,
        metrics_stored=metrics_stored,
        message=imported.message,
    )

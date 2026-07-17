"""Evidence-pack construction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_evidence_pack(
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection | None = None,
    config: MetricEngineConfig | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> EvidencePack:
    """Build a deterministic evidence pack from a validated bundle result."""

    engine_config = config or MetricEngineConfig()
    collection = metric_collection or compute_metrics_for_bundle(
        bundle_result,
        engine_config,
        clock=clock,
    )
    generated_at = clock()
    manifest = bundle_result.manifest
    synthetic = manifest.environment.name == "synthetic" if manifest is not None else False
    run_context = (
        {
            "run_id": manifest.run.run_id,
            "experiment_id": manifest.run.experiment_id,
            "seed_id": manifest.run.seed_id,
            "algorithm": manifest.run.algorithm,
            "checkpoint": manifest.run.checkpoint,
            "random_seed": manifest.run.random_seed,
            "environment": manifest.environment.name,
            "environment_version": manifest.environment.version,
            "environment_commit": manifest.environment.commit,
        }
        if manifest is not None
        else {"run_id": bundle_result.report.run_id}
    )
    warnings = [
        finding.code.value
        for finding in bundle_result.report.findings
        if finding.severity.value in {"warning", "error", "fatal"}
    ]
    return EvidencePack(
        pack_id=_pack_id(bundle_result.report.run_id, bundle_result.fingerprint),
        generated_at=generated_at,
        synthetic=synthetic,
        run_context=run_context,
        source_bundle_fingerprint=bundle_result.fingerprint,
        validation_summary={
            "status": bundle_result.report.status.value,
            "may_import": bundle_result.report.may_import,
            "finding_count": len(bundle_result.report.findings),
            "counts_by_severity": bundle_result.report.counts_by_severity,
            "validator_version": bundle_result.report.validator_version,
        },
        evidence_availability=bundle_result.evidence,
        metric_engine_config=engine_config,
        metric_collection=collection,
        excluded_record_counts=dict.fromkeys(bundle_result.canonical.record_counts(), 0),
        warnings=warnings,
        provenance={
            "bundle_id": bundle_result.report.bundle_id,
            "bundle_source": str(bundle_result.source),
            "manifest_version": manifest.schema_version if manifest is not None else None,
            "metric_version": collection.metric_version,
        },
    )


def _pack_id(run_id: str | None, fingerprint: str | None) -> str:
    suffix = (fingerprint or "no-fingerprint")[:12]
    return f"evidence-{run_id or 'unknown'}-{suffix}"

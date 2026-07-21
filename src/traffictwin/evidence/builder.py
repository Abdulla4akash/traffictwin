"""Evidence-pack construction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import (
    TemporalEvidenceConfig,
    TemporalEvidenceReason,
    build_temporal_evidence,
    invalidate_temporal_evidence,
)
from traffictwin.ingestion.bundle import BundleValidationResult
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginRegistry
from traffictwin.metrics.results import MetricCollection
from traffictwin.metrics.windowed import WindowedMetricSeries


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_evidence_pack(
    bundle_result: BundleValidationResult,
    metric_collection: MetricCollection | None = None,
    config: MetricEngineConfig | None = None,
    *,
    plugin_registry: MetricPluginRegistry | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> EvidencePack:
    """Build a deterministic evidence pack from a validated bundle result."""

    engine_config = config or MetricEngineConfig()
    collection = metric_collection or compute_metrics_for_bundle(
        bundle_result,
        engine_config,
        plugin_registry=plugin_registry,
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
            "energy_contract_fingerprint": (
                manifest.energy_contract.fingerprint()
                if manifest.energy_contract is not None
                else None
            ),
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
            "energy_contract_fingerprint": (
                manifest.energy_contract.fingerprint()
                if manifest is not None and manifest.energy_contract is not None
                else None
            ),
        },
    )


def _pack_id(run_id: str | None, fingerprint: str | None) -> str:
    suffix = (fingerprint or "no-fingerprint")[:12]
    return f"evidence-{run_id or 'unknown'}-{suffix}"


def attach_temporal_evidence(
    evidence_pack: EvidencePack,
    window_series: WindowedMetricSeries,
    config: TemporalEvidenceConfig,
) -> EvidencePack:
    """Attach validated window evidence while preserving the EvidencePack rule boundary."""

    temporal = build_temporal_evidence(window_series, config)
    if evidence_pack.metric_collection.run_id != window_series.run_id:
        temporal = invalidate_temporal_evidence(temporal, TemporalEvidenceReason.RUN_MISMATCH)
    pack_fingerprint = evidence_pack.source_bundle_fingerprint
    series_fingerprint = window_series.input_fingerprint
    if pack_fingerprint != series_fingerprint:
        temporal = invalidate_temporal_evidence(
            temporal,
            TemporalEvidenceReason.SOURCE_FINGERPRINT_MISMATCH,
        )
    temporal_fingerprint = temporal.fingerprint()
    return evidence_pack.model_copy(
        update={
            "pack_id": f"{evidence_pack.pack_id}-temporal-{temporal_fingerprint[:12]}",
            "temporal_evidence": temporal,
            "warnings": sorted(
                {
                    *evidence_pack.warnings,
                    *(
                        ["Temporal evidence is unavailable or invalid; R6 will not evaluate it."]
                        if temporal.status.value != "available"
                        else []
                    ),
                }
            ),
            "provenance": {
                **evidence_pack.provenance,
                "temporal_evidence_fingerprint": temporal_fingerprint,
                "window_series_fingerprint": temporal.series_fingerprint,
            },
        },
        deep=True,
    )

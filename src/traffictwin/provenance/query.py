"""Read-only provenance query service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.metrics.catalogue import metric_catalogue
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.builder import build_metric_trace, build_rule_trace, build_run_trace
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceNodeType, ProvenanceTrace, SourceRowPreview
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.provenance.source_rows import get_source_row
from traffictwin.rules.catalogue import rule_catalogue
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules

Clock = Callable[[], datetime]


class ProvenanceQueryError(ValueError):
    """Raised when a provenance query cannot be answered honestly."""


@dataclass(frozen=True)
class ProvenanceContext:
    """Reusable provenance context for a validated bundle."""

    bundle_path: Path
    validation: BundleValidationResult
    metrics: MetricCollection | None
    evidence_pack: EvidencePack | None
    diagnostic_report: DiagnosticReport | None

    @property
    def analysis_ready(self) -> bool:
        """Return whether metrics/evidence/diagnostics are available."""

        return self.metrics is not None and self.evidence_pack is not None


def build_provenance_context(
    path: str | Path,
    *,
    metric_config: MetricEngineConfig | None = None,
    rule_config: RuleSetConfig | None = None,
    clock: Clock | None = None,
) -> ProvenanceContext:
    """Validate a bundle and build existing deterministic artifacts for tracing."""

    bundle_path = Path(path)
    result = validate_bundle(bundle_path)
    if result.manifest is None or not result.report.may_import:
        return ProvenanceContext(bundle_path, result, None, None, None)
    metric_clock = _coerce_clock(clock)
    metrics = compute_metrics_for_bundle(
        result,
        metric_config or MetricEngineConfig(),
        clock=metric_clock,
    )
    evidence_pack = build_evidence_pack(
        result,
        metrics,
        metric_config or MetricEngineConfig(),
        clock=metric_clock,
    )
    diagnostic_report = evaluate_rules(
        evidence_pack,
        rule_config,
        clock=metric_clock,
    )
    return ProvenanceContext(bundle_path, result, metrics, evidence_pack, diagnostic_report)


def list_traceable_runs(context: ProvenanceContext) -> list[str]:
    """Return traceable run ids for a context."""

    if context.validation.manifest is None:
        return []
    return [context.validation.manifest.run.run_id]


def list_traceable_metrics(context: ProvenanceContext) -> list[str]:
    """Return metric keys present in the current context."""

    if context.metrics is None:
        return []
    catalogue = metric_catalogue()
    return [key for key in catalogue if key in context.metrics.by_key()]


def list_traceable_rules(context: ProvenanceContext) -> list[str]:
    """Return diagnostic rule ids present in the current context."""

    if context.diagnostic_report is None:
        return []
    known_rules = rule_catalogue()
    return [
        result.rule_id
        for result in context.diagnostic_report.results
        if result.rule_id in known_rules
    ]


def get_metric_provenance(
    context: ProvenanceContext,
    metric_key: str,
    *,
    clock: Clock | None = None,
) -> ProvenanceTrace:
    """Build provenance for one metric key."""

    if context.metrics is None:
        raise ProvenanceQueryError("metric provenance requires an accepted bundle")
    return build_metric_trace(
        metric_key,
        context.validation,
        context.metrics,
        context.evidence_pack,
        context.diagnostic_report,
        clock=_coerce_clock(clock),
    )


def get_rule_provenance(
    context: ProvenanceContext,
    rule_id: str,
    *,
    clock: Clock | None = None,
) -> ProvenanceTrace:
    """Build provenance for one diagnostic rule result."""

    if (
        context.metrics is None
        or context.evidence_pack is None
        or context.diagnostic_report is None
    ):
        raise ProvenanceQueryError("rule provenance requires an accepted bundle")
    return build_rule_trace(
        rule_id,
        context.validation,
        context.metrics,
        context.evidence_pack,
        context.diagnostic_report,
        clock=_coerce_clock(clock),
    )


def get_run_provenance(
    context: ProvenanceContext,
    *,
    clock: Clock | None = None,
) -> ProvenanceTrace:
    """Build provenance for the selected run context."""

    return build_run_trace(
        context.validation,
        context.metrics,
        context.evidence_pack,
        context.diagnostic_report,
        clock=_coerce_clock(clock),
    )


def get_source_provenance(
    context: ProvenanceContext,
    source_file: str,
    source_row: int,
    *,
    context_rows: int = 2,
) -> SourceRowPreview:
    """Return a read-only source-row preview."""

    return get_source_row(
        context.bundle_path,
        source_file,
        source_row,
        context_rows=context_rows,
        canonical_tables=context.validation.canonical,
        validation_report=context.validation.report,
        manifest=context.validation.manifest,
    )


def search_provenance(context: ProvenanceContext, query: str) -> list[str]:
    """Search traceable identifiers in a deterministic in-memory catalogue."""

    needle = query.lower()
    values: list[str] = []
    if context.validation.manifest is not None:
        manifest = context.validation.manifest
        values.extend(
            [
                manifest.run.run_id,
                manifest.run.experiment_id,
                manifest.run.seed_id,
                manifest.run.algorithm,
                manifest.run.checkpoint or "",
                manifest.bundle.bundle_id,
            ]
        )
        values.extend(declaration.path for declaration in manifest.files.values())
    values.extend(list_traceable_metrics(context))
    values.extend(list_traceable_rules(context))
    values.extend(finding.code.value for finding in context.validation.report.findings)
    return sorted({value for value in values if value and needle in value.lower()})


def export_provenance(trace: ProvenanceTrace, output_format: str) -> str:
    """Export a trace as JSON or Markdown."""

    if output_format == "json":
        return trace_to_json(trace)
    if output_format == "markdown":
        return trace_to_markdown(trace)
    msg = "output_format must be 'json' or 'markdown'"
    raise ProvenanceQueryError(msg)


def dependent_rules_for_metric(metric_key: str) -> list[str]:
    """Return diagnostic rules that cite a metric key in public metadata."""

    rules = rule_catalogue()
    return [
        rule_id
        for rule_id, definition in rules.items()
        if metric_key in definition.required_evidence
    ]


def node_type_counts(trace: ProvenanceTrace) -> dict[str, int]:
    """Return node counts by type for UI summaries."""

    counts: dict[str, int] = {node_type.value: 0 for node_type in ProvenanceNodeType}
    for node in trace.nodes:
        counts[node.node_type.value] += 1
    return {key: value for key, value in counts.items() if value}


def _coerce_clock(clock: Clock | None) -> Clock:
    if clock is None:
        from traffictwin.provenance.builder import utc_now

        return utc_now
    return clock

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
from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.plugins import MetricPluginRegistry
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.builder import build_metric_trace, build_rule_trace, build_run_trace
from traffictwin.provenance.completeness import (
    ClaimEvidence,
    ProvenanceCompletenessReport,
    assess_claim_evidence,
    build_provenance_completeness_report,
)
from traffictwin.provenance.contributions import (
    MetricContributionReport,
    build_metric_contribution_report,
)
from traffictwin.provenance.differences import (
    DifferenceContributionError,
    DifferenceContributionReport,
    build_difference_contribution_report,
)
from traffictwin.provenance.graph_export import (
    DEFAULT_GRAPH_EDGE_LIMIT,
    DEFAULT_GRAPH_NODE_LIMIT,
    GraphExportError,
    GraphRedactionMode,
    ProvenanceGraphView,
    build_provenance_graph_view,
    provenance_graph_to_dot,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.markdown import trace_to_markdown
from traffictwin.provenance.models import ProvenanceNodeType, ProvenanceTrace, SourceRowPreview
from traffictwin.provenance.serialization import trace_to_json
from traffictwin.provenance.source_rows import get_source_row
from traffictwin.reporting.claims import (
    analysis_claim_references,
    comparison_claim_references,
    full_report_claim_references,
    standard_claim_exclusions,
)
from traffictwin.reporting.models import ReportClaimKind, ReportClaimReference, ResearchReportType
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
    plugin_registry: MetricPluginRegistry | None = None,
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
        plugin_registry=plugin_registry,
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
    return sorted(context.metrics.by_key())


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


def get_metric_contributions(
    context: ProvenanceContext,
    metric_key: str,
) -> MetricContributionReport:
    """Return the complete canonical-row contribution ledger for one metric."""

    if context.metrics is None:
        raise ProvenanceQueryError("metric contributions require an accepted bundle")
    try:
        return build_metric_contribution_report(
            context.validation,
            context.metrics,
            metric_key,
        )
    except ValueError as exc:
        raise ProvenanceQueryError(str(exc)) from exc


def get_difference_contributions(
    baseline: ProvenanceContext,
    variation: ProvenanceContext,
    metric_key: str,
) -> DifferenceContributionReport:
    """Return compatible baseline/variation accepted-row difference lineage."""

    if baseline.metrics is None or variation.metrics is None:
        raise ProvenanceQueryError(
            "difference contributions require two accepted analysis-ready bundles"
        )
    try:
        return build_difference_contribution_report(
            baseline.validation,
            baseline.metrics,
            variation.validation,
            variation.metrics,
            metric_key,
        )
    except DifferenceContributionError as exc:
        raise ProvenanceQueryError(str(exc)) from exc


def get_report_provenance_completeness(
    context: ProvenanceContext,
    report_type: ResearchReportType | str = ResearchReportType.RUN,
    *,
    comparison_baseline: ProvenanceContext | None = None,
    clock: Clock | None = None,
) -> ProvenanceCompletenessReport:
    """Inventory and score every typed claim in one run-like report template."""

    try:
        selected_type = ResearchReportType(report_type)
    except ValueError as exc:
        choices = ", ".join(
            item.value
            for item in (
                ResearchReportType.RUN,
                ResearchReportType.DIAGNOSTICS,
                ResearchReportType.FULL,
            )
        )
        raise ProvenanceQueryError(f"report_type must be one of: {choices}") from exc
    if selected_type not in {
        ResearchReportType.RUN,
        ResearchReportType.DIAGNOSTICS,
        ResearchReportType.FULL,
    }:
        raise ProvenanceQueryError("use the comparison completeness query for comparison reports")
    _require_analysis_claim_context(context)
    assert context.metrics is not None
    assert context.diagnostic_report is not None
    assert context.validation.manifest is not None
    run_id = context.validation.manifest.run.run_id
    generated_at = _coerce_clock(clock)()

    def stable_clock() -> datetime:
        return generated_at

    if selected_type is ResearchReportType.DIAGNOSTICS:
        report_id = f"report-diagnostics-{run_id}"
        references = analysis_claim_references(
            report_id,
            context.metrics,
            context.diagnostic_report,
            metric_section="Metric Evidence Used",
        )
    else:
        run_report_id = f"report-run-{run_id}"
        references = analysis_claim_references(
            run_report_id,
            context.metrics,
            context.diagnostic_report,
            metric_section="Metrics",
        )
        report_id = run_report_id
        if selected_type is ResearchReportType.FULL:
            report_id = f"report-full-{run_id}"
            if comparison_baseline is not None:
                comparison, comparison_id = _comparison_report_and_id(
                    comparison_baseline,
                    context,
                    stable_clock,
                )
                references.extend(comparison_claim_references(comparison_id, comparison))
            references = full_report_claim_references(report_id, references)
    evidence = [
        _claim_evidence(
            reference,
            context,
            comparison_baseline=comparison_baseline,
            clock=stable_clock,
        )
        for reference in references
    ]
    return build_provenance_completeness_report(
        report_id=report_id,
        report_type=selected_type,
        claim_evidence=evidence,
        exclusions=standard_claim_exclusions(selected_type),
        clock=stable_clock,
    )


def get_comparison_provenance_completeness(
    baseline: ProvenanceContext,
    variation: ProvenanceContext,
    *,
    clock: Clock | None = None,
) -> ProvenanceCompletenessReport:
    """Inventory and score every typed metric claim in a comparison report."""

    generated_at = _coerce_clock(clock)()

    def stable_clock() -> datetime:
        return generated_at

    comparison, report_id = _comparison_report_and_id(baseline, variation, stable_clock)
    references = comparison_claim_references(report_id, comparison)
    evidence = [
        _claim_evidence(
            reference,
            variation,
            comparison_baseline=baseline,
            clock=stable_clock,
        )
        for reference in references
    ]
    return build_provenance_completeness_report(
        report_id=report_id,
        report_type=ResearchReportType.COMPARISON,
        claim_evidence=evidence,
        exclusions=standard_claim_exclusions(ResearchReportType.COMPARISON),
        clock=stable_clock,
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


def get_provenance_graph_view(
    trace: ProvenanceTrace,
    *,
    node_limit: int = DEFAULT_GRAPH_NODE_LIMIT,
    edge_limit: int = DEFAULT_GRAPH_EDGE_LIMIT,
    redaction_mode: GraphRedactionMode | str = GraphRedactionMode.SAFE,
) -> ProvenanceGraphView:
    """Return one deterministic bounded and path-safe view of an existing trace."""

    try:
        return build_provenance_graph_view(
            trace,
            node_limit=node_limit,
            edge_limit=edge_limit,
            redaction_mode=redaction_mode,
        )
    except GraphExportError as exc:
        raise ProvenanceQueryError(str(exc)) from exc


def export_provenance(
    trace: ProvenanceTrace,
    output_format: str,
    *,
    node_limit: int = DEFAULT_GRAPH_NODE_LIMIT,
    edge_limit: int = DEFAULT_GRAPH_EDGE_LIMIT,
    redaction_mode: GraphRedactionMode | str = GraphRedactionMode.SAFE,
) -> str:
    """Export a trace as JSON/Markdown or a bounded DOT/GraphML graph."""

    if output_format == "json":
        return trace_to_json(trace)
    if output_format == "markdown":
        return trace_to_markdown(trace)
    if output_format in {"dot", "graphml"}:
        view = get_provenance_graph_view(
            trace,
            node_limit=node_limit,
            edge_limit=edge_limit,
            redaction_mode=redaction_mode,
        )
        return (
            provenance_graph_to_dot(view)
            if output_format == "dot"
            else provenance_graph_to_graphml(view)
        )
    msg = "output_format must be one of: json, markdown, dot, graphml"
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


def _require_analysis_claim_context(context: ProvenanceContext) -> None:
    if (
        context.validation.manifest is None
        or context.metrics is None
        or context.evidence_pack is None
        or context.diagnostic_report is None
    ):
        raise ProvenanceQueryError(
            "provenance completeness requires an accepted analysis-ready bundle"
        )


def _comparison_report_and_id(
    baseline: ProvenanceContext,
    variation: ProvenanceContext,
    clock: Clock,
) -> tuple[ComparisonReport, str]:
    _require_analysis_claim_context(baseline)
    _require_analysis_claim_context(variation)
    assert baseline.metrics is not None
    assert variation.metrics is not None
    comparison = compare_metric_collections(
        baseline.metrics,
        variation.metrics,
        baseline_seed=baseline.validation.seed,
        variation_seed=variation.validation.seed,
        clock=clock,
    )
    report_id = f"report-compare-{baseline.metrics.run_id}-vs-{variation.metrics.run_id}"
    return comparison, report_id


def _claim_evidence(
    reference: ReportClaimReference,
    context: ProvenanceContext,
    *,
    comparison_baseline: ProvenanceContext | None,
    clock: Clock,
) -> ClaimEvidence:
    if reference.claim_kind is ReportClaimKind.METRIC_RESULT:
        return _metric_claim_evidence(reference, context, clock)
    if reference.claim_kind is ReportClaimKind.RULE_RESULT:
        return _rule_claim_evidence(reference, context, clock)
    if reference.claim_kind is ReportClaimKind.METRIC_COMPARISON:
        if comparison_baseline is None:
            return ClaimEvidence(
                reference=reference,
                artifact_status="unavailable",
                reason_codes=("comparison_baseline_context_unavailable",),
            )
        try:
            difference = get_difference_contributions(
                comparison_baseline,
                context,
                reference.artifact_key,
            )
            return ClaimEvidence(
                reference=reference,
                artifact_status=difference.status.value,
                difference_report=difference,
                reason_codes=(
                    *difference.comparison_reason_codes,
                    *difference.compatibility_findings,
                ),
            )
        except ProvenanceQueryError as exc:
            return ClaimEvidence(
                reference=reference,
                artifact_status="unavailable",
                reason_codes=(f"difference_provenance_unavailable:{exc}",),
            )
    raise ProvenanceQueryError(f"unsupported report claim kind: {reference.claim_kind}")


def _metric_claim_evidence(
    reference: ReportClaimReference,
    context: ProvenanceContext,
    clock: Clock,
) -> ClaimEvidence:
    if context.metrics is None:
        return ClaimEvidence(
            reference=reference,
            artifact_status="unavailable",
            reason_codes=("metric_collection_unavailable",),
        )
    metric = context.metrics.by_key().get(reference.artifact_key)
    if metric is None:
        return ClaimEvidence(
            reference=reference,
            artifact_status="unavailable",
            reason_codes=("metric_result_not_present",),
        )
    trace = get_metric_provenance(context, reference.artifact_key, clock=clock)
    ledger: MetricContributionReport | None = None
    ledger_reasons: list[str] = []
    try:
        ledger = get_metric_contributions(context, reference.artifact_key)
    except ProvenanceQueryError as exc:
        ledger_reasons.append(f"accepted_row_ledger_unavailable:{exc}")
    return ClaimEvidence(
        reference=reference,
        artifact_status=metric.status.value,
        trace=trace,
        contribution_report=ledger,
        required_evidence=tuple(metric.required_evidence),
        reason_codes=(
            *ledger_reasons,
            *(f"missing_evidence:{item}" for item in metric.missing_evidence),
            *(f"metric_reason:{item.value}" for item in metric.reason_codes),
        ),
    )


def _rule_claim_evidence(
    reference: ReportClaimReference,
    context: ProvenanceContext,
    clock: Clock,
) -> ClaimEvidence:
    if context.diagnostic_report is None:
        return ClaimEvidence(
            reference=reference,
            artifact_status="insufficient_evidence",
            reason_codes=("diagnostic_report_unavailable",),
        )
    result = next(
        (
            item
            for item in context.diagnostic_report.results
            if item.rule_id == reference.artifact_key
        ),
        None,
    )
    if result is None:
        return ClaimEvidence(
            reference=reference,
            artifact_status="insufficient_evidence",
            reason_codes=("rule_result_not_present",),
        )
    trace = get_rule_provenance(context, result.rule_id, clock=clock)
    metric_keys = context.metrics.by_key() if context.metrics is not None else {}
    dependencies = []
    for metric_key in sorted(key for key in result.evidence_keys if key in metric_keys):
        dependency_reference = ReportClaimReference(
            claim_id=f"{reference.claim_id}:dependency:{metric_key}",
            claim_kind=ReportClaimKind.METRIC_RESULT,
            artifact_key=metric_key,
            section=reference.section,
            label=metric_key,
        )
        dependencies.append(
            assess_claim_evidence(_metric_claim_evidence(dependency_reference, context, clock))
        )
    definition = rule_catalogue().get(result.rule_id)
    required = tuple(definition.required_evidence) if definition is not None else ()
    return ClaimEvidence(
        reference=reference,
        artifact_status=result.status.value,
        trace=trace,
        required_evidence=required,
        dependency_assessments=tuple(dependencies),
        reason_codes=tuple(f"missing_evidence:{item}" for item in result.missing_evidence),
    )


def _coerce_clock(clock: Clock | None) -> Clock:
    if clock is None:
        from traffictwin.provenance.builder import utc_now

        return utc_now
    return clock

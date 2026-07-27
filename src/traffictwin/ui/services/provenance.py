"""Provenance, comparison, and completeness services."""

from __future__ import annotations

from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections
from traffictwin.provenance.completeness import ProvenanceCompletenessReport
from traffictwin.provenance.contributions import MetricContributionReport
from traffictwin.provenance.differences import DifferenceContributionReport
from traffictwin.provenance.graph_export import GraphRedactionMode, ProvenanceGraphView
from traffictwin.provenance.models import ProvenanceTrace, SourceRowPreview
from traffictwin.provenance.query import (
    ProvenanceContext,
    ProvenanceQueryError,
    get_comparison_provenance_completeness,
    get_difference_contributions,
    get_metric_contributions,
    get_metric_provenance,
    get_provenance_graph_view,
    get_report_provenance_completeness,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
)
from traffictwin.reporting.models import ResearchReportType
from traffictwin.ui.services.models import BundleAnalysis, ServiceError


def provenance_context_for_ui(analysis: BundleAnalysis) -> ProvenanceContext:
    """Build a read-only provenance context from already computed UI artifacts."""

    return ProvenanceContext(
        bundle_path=analysis.source_path,
        validation=analysis.validation,
        metrics=analysis.metrics,
        evidence_pack=analysis.evidence_pack,
        diagnostic_report=analysis.diagnostic_report,
    )


def metric_provenance_for_ui(analysis: BundleAnalysis, metric_key: str) -> ProvenanceTrace:
    """Build a metric provenance trace for the selected analysis."""

    return get_metric_provenance(provenance_context_for_ui(analysis), metric_key)


def metric_contributions_for_ui(
    analysis: BundleAnalysis,
    metric_key: str,
) -> MetricContributionReport:
    """Build the complete canonical-row contribution ledger for one metric."""

    return get_metric_contributions(provenance_context_for_ui(analysis), metric_key)


def rule_provenance_for_ui(analysis: BundleAnalysis, rule_id: str) -> ProvenanceTrace:
    """Build a diagnostic-rule provenance trace for the selected analysis."""

    return get_rule_provenance(provenance_context_for_ui(analysis), rule_id)


def run_provenance_for_ui(analysis: BundleAnalysis) -> ProvenanceTrace:
    """Build a run-level provenance trace for the selected analysis."""

    return get_run_provenance(provenance_context_for_ui(analysis))


def provenance_graph_for_ui(
    trace: ProvenanceTrace,
    *,
    node_limit: int,
    edge_limit: int,
    redaction_mode: GraphRedactionMode | str = GraphRedactionMode.SAFE,
) -> ProvenanceGraphView | ServiceError:
    """Build the typed bounded graph projection used by the explorer and downloads."""

    try:
        return get_provenance_graph_view(
            trace,
            node_limit=node_limit,
            edge_limit=edge_limit,
            redaction_mode=redaction_mode,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("The bounded provenance graph is unavailable.", str(exc))


def source_preview_for_ui(
    analysis: BundleAnalysis,
    source_file: str,
    source_row: int,
    *,
    context_rows: int = 2,
) -> SourceRowPreview:
    """Return a read-only source-row preview for the selected analysis."""

    return get_source_provenance(
        provenance_context_for_ui(analysis),
        source_file,
        source_row,
        context_rows=context_rows,
    )


def compare_runs_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> ComparisonReport | ServiceError:
    """Compare two analysis-ready bundles."""

    if baseline.metrics is None or variation.metrics is None:
        return ServiceError("Both baseline and variation must be accepted before comparison.")
    return compare_metric_collections(
        baseline.metrics,
        variation.metrics,
        baseline_seed=baseline.validation.seed,
        variation_seed=variation.validation.seed,
    )


def difference_contributions_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
    metric_key: str,
) -> DifferenceContributionReport | ServiceError:
    """Build typed PRO-01 lineage without placing arithmetic in the UI."""

    try:
        return get_difference_contributions(
            provenance_context_for_ui(baseline),
            provenance_context_for_ui(variation),
            metric_key,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Difference provenance is unavailable.", str(exc))


def report_provenance_completeness_for_ui(
    analysis: BundleAnalysis,
    report_type: ResearchReportType | str,
) -> ProvenanceCompletenessReport | ServiceError:
    """Build the typed PRO-03 denominator and classifications for one report template."""

    try:
        return get_report_provenance_completeness(
            provenance_context_for_ui(analysis),
            report_type,
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Report provenance completeness is unavailable.", str(exc))


def comparison_provenance_completeness_for_ui(
    baseline: BundleAnalysis,
    variation: BundleAnalysis,
) -> ProvenanceCompletenessReport | ServiceError:
    """Build the typed PRO-03 denominator for one comparison report."""

    try:
        return get_comparison_provenance_completeness(
            provenance_context_for_ui(baseline),
            provenance_context_for_ui(variation),
        )
    except ProvenanceQueryError as exc:
        return ServiceError("Comparison provenance completeness is unavailable.", str(exc))

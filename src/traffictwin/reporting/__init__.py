"""Deterministic standalone research-report export."""

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from traffictwin.annotations import (
    AnalystAnnotation,
    AnalystAnnotationContract,
    AnalystAnnotationHistory,
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
    analyst_annotation_contract,
    analyst_annotation_id,
)
from traffictwin.reporting.annotation_rendering import (
    ReportAnnotationError,
    attach_analyst_annotations,
    attach_registry_annotations,
)
from traffictwin.reporting.diffing import (
    ReportClaimDiff,
    ReportDiffClassification,
    ReportDiffCompatibilityCode,
    ReportDiffContract,
    ReportDiffError,
    ReportFieldChange,
    ReportSectionDiff,
    StructuredReportDiff,
    StructuredReportDiffStatus,
    compare_structured_reports,
    parse_research_report_json,
    report_diff_contract,
    report_diff_to_markdown,
    report_scientific_fingerprint,
)
from traffictwin.reporting.executive import (
    ExecutiveSummary,
    ExecutiveSummaryAvailability,
    ExecutiveSummaryContract,
    ExecutiveSummaryError,
    ExecutiveSummaryFormat,
    ExecutiveSummaryHighlight,
    ExecutiveSummaryProvenanceLink,
    ExecutiveSummarySourceMode,
    executive_summary_contract,
    executive_summary_to_html,
    executive_summary_to_markdown,
    project_executive_summary,
)
from traffictwin.reporting.executive_pdf import (
    ExecutiveSummaryLayoutError,
    executive_summary_to_pdf_bytes,
)
from traffictwin.reporting.latex import (
    LatexExportContract,
    ResearchExportFile,
    ResearchExportKind,
    ResearchExportProjection,
    ResearchExportReceipt,
    ResearchFigureEntry,
    ResearchFigureFormat,
    escape_latex,
    latex_export_contract,
    project_comparison_report,
    project_diagnostic_report,
    project_metric_collection,
    project_statistical_study,
    projection_to_latex_fragment,
    projection_to_pdf,
    projection_to_svg,
    write_projection_exports,
)
from traffictwin.reporting.models import (
    ReportClaimAvailability,
    ReportClaimExclusion,
    ReportClaimKind,
    ReportClaimReference,
    ReportClaimSnapshot,
    ResearchReport,
    ResearchReportType,
)


def build_run_report(
    path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> ResearchReport:
    """Lazily build a run report without creating import cycles."""

    from traffictwin.reporting.builder import build_run_report as implementation

    return implementation(path, clock=clock)


def build_diagnostics_report(
    path: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> ResearchReport:
    """Lazily build a diagnostics report without creating import cycles."""

    from traffictwin.reporting.builder import build_diagnostics_report as implementation

    return implementation(path, clock=clock)


def build_comparison_report(
    baseline: str | Path,
    variation: str | Path,
    *,
    clock: Callable[[], datetime] | None = None,
) -> ResearchReport:
    """Lazily build a comparison report without creating import cycles."""

    from traffictwin.reporting.builder import build_comparison_report as implementation

    return implementation(baseline, variation, clock=clock)


def build_full_report(
    path: str | Path,
    *,
    comparison_baseline: str | Path | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ResearchReport:
    """Lazily build a full report without creating import cycles."""

    from traffictwin.reporting.builder import build_full_report as implementation

    return implementation(path, comparison_baseline=comparison_baseline, clock=clock)


def report_to_pdf_bytes(report: ResearchReport) -> bytes:
    """Lazily render PDF bytes without eager renderer imports."""

    from traffictwin.reporting.pdf import report_to_pdf_bytes as implementation

    return implementation(report)


__all__ = [
    "AnalystAnnotation",
    "AnalystAnnotationContract",
    "AnalystAnnotationHistory",
    "AnalystAnnotationRequest",
    "AnalystAnnotationTargetKind",
    "AnalystArtifactReference",
    "AnalystDecisionLabel",
    "analyst_annotation_contract",
    "analyst_annotation_id",
    "attach_analyst_annotations",
    "attach_registry_annotations",
    "build_comparison_report",
    "build_diagnostics_report",
    "build_full_report",
    "build_run_report",
    "compare_structured_reports",
    "ExecutiveSummary",
    "ExecutiveSummaryAvailability",
    "ExecutiveSummaryContract",
    "ExecutiveSummaryError",
    "ExecutiveSummaryFormat",
    "ExecutiveSummaryHighlight",
    "ExecutiveSummaryLayoutError",
    "ExecutiveSummaryProvenanceLink",
    "ExecutiveSummarySourceMode",
    "executive_summary_contract",
    "executive_summary_to_html",
    "executive_summary_to_markdown",
    "executive_summary_to_pdf_bytes",
    "escape_latex",
    "LatexExportContract",
    "latex_export_contract",
    "project_comparison_report",
    "project_diagnostic_report",
    "project_executive_summary",
    "project_metric_collection",
    "project_statistical_study",
    "projection_to_latex_fragment",
    "projection_to_pdf",
    "projection_to_svg",
    "parse_research_report_json",
    "ReportClaimAvailability",
    "ReportClaimDiff",
    "ReportClaimExclusion",
    "ReportClaimKind",
    "ReportClaimReference",
    "ReportClaimSnapshot",
    "ReportDiffClassification",
    "ReportDiffCompatibilityCode",
    "ReportDiffContract",
    "ReportDiffError",
    "ReportFieldChange",
    "ReportAnnotationError",
    "ReportSectionDiff",
    "report_diff_contract",
    "report_diff_to_markdown",
    "report_scientific_fingerprint",
    "ResearchReport",
    "ResearchReportType",
    "ResearchExportFile",
    "ResearchExportKind",
    "ResearchExportProjection",
    "ResearchExportReceipt",
    "ResearchFigureEntry",
    "ResearchFigureFormat",
    "report_to_pdf_bytes",
    "StructuredReportDiff",
    "StructuredReportDiffStatus",
    "write_projection_exports",
]

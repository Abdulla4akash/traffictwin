"""Workspace report, executive summary, annotation, and research export services."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from traffictwin.annotations import (
    AnalystAnnotation,
    AnalystAnnotationHistory,
    AnalystAnnotationRequest,
    AnalystAnnotationTargetKind,
    AnalystArtifactReference,
    AnalystDecisionLabel,
)
from traffictwin.experiments.regression_gate import (
    parse_statistical_study_json,
)
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.reporting.annotation_rendering import attach_registry_annotations
from traffictwin.reporting.builder import (
    build_comparison_report,
    build_diagnostics_report,
    build_full_report,
    build_run_report,
)
from traffictwin.reporting.diffing import (
    ReportDiffError,
    compare_structured_reports,
    parse_research_report_json,
    report_diff_to_markdown,
)
from traffictwin.reporting.executive import (
    ExecutiveSummaryError,
    executive_summary_to_html,
    executive_summary_to_markdown,
    project_executive_summary,
)
from traffictwin.reporting.executive_pdf import (
    ExecutiveSummaryLayoutError,
    executive_summary_to_pdf_bytes,
)
from traffictwin.reporting.html import report_to_html
from traffictwin.reporting.latex import (
    ResearchExportReceipt,
    project_comparison_report,
    project_diagnostic_report,
    project_metric_collection,
    project_statistical_study,
    write_projection_exports,
)
from traffictwin.reporting.markdown import report_to_markdown
from traffictwin.reporting.pdf import report_to_pdf_bytes
from traffictwin.storage.registry import (
    Registry,
)
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import (
    ExecutiveSummaryView,
    ReportEntry,
    ServiceError,
    StructuredReportDiffView,
)


def list_workspace_reports(workspace_path: str | Path | None) -> list[ReportEntry]:
    """Return report files from a standalone workspace."""

    if workspace_path is None:
        return []
    report_dir = Path(workspace_path) / "reports"
    if not report_dir.exists():
        return []
    entries: list[ReportEntry] = []
    for path in sorted(report_dir.glob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in {".md", ".html", ".json", ".pdf", ".svg", ".tex"}:
            continue
        stat = path.stat()
        entries.append(
            ReportEntry(
                path=path,
                name=path.name,
                report_type=_infer_report_type(path.name),
                format_label={
                    ".html": "HTML",
                    ".json": "JSON",
                    ".pdf": "PDF",
                    ".svg": "SVG",
                    ".tex": "LaTeX",
                }.get(suffix, "Markdown"),
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
                size_bytes=stat.st_size,
                scenario_hint=_scenario_hint(path.name),
            )
        )
    return entries


def regenerate_report_for_ui(
    report_type: Literal["run", "compare", "diagnostics", "full"],
    primary_path: str | Path,
    output_path: str | Path,
    *,
    secondary_path: str | Path | None = None,
    annotation_registry_path: str | Path | None = None,
) -> Path | ServiceError:
    """Generate a deterministic report through the existing reporting layer."""

    output = Path(output_path)
    try:
        if report_type == "run":
            report = build_run_report(primary_path)
        elif report_type == "compare":
            if secondary_path is None:
                return ServiceError("Comparison report requires a variation bundle path.")
            report = build_comparison_report(primary_path, secondary_path)
        elif report_type == "diagnostics":
            report = build_diagnostics_report(primary_path)
        elif report_type == "full":
            report = build_full_report(primary_path, comparison_baseline=secondary_path)
        else:
            return ServiceError("Unsupported report type.", report_type)
        if annotation_registry_path is not None:
            registry_path = Path(annotation_registry_path)
            if not registry_path.is_file():
                return ServiceError(
                    "Annotation registry is unavailable.",
                    str(registry_path),
                )
            report = attach_registry_annotations(report, Registry(registry_path))
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix.lower() == ".json":
            output.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        elif output.suffix.lower() == ".pdf":
            output.write_bytes(report_to_pdf_bytes(report))
        else:
            payload = (
                report_to_html(report)
                if output.suffix.lower() == ".html"
                else report_to_markdown(report)
            )
            output.write_text(payload, encoding="utf-8")
    except Exception as exc:
        return ServiceError("Report could not be generated.", str(exc))
    return output


def compare_structured_reports_for_ui(
    baseline_path: str | Path,
    variation_path: str | Path,
) -> StructuredReportDiffView | ServiceError:
    """Compare two saved report JSON payloads through the REP-03 library boundary."""

    try:
        baseline = parse_research_report_json(Path(baseline_path).read_bytes())
        variation = parse_research_report_json(Path(variation_path).read_bytes())
        report = compare_structured_reports(baseline, variation)
        return StructuredReportDiffView(
            report=report,
            json_payload=report.model_dump_json(indent=2) + "\n",
            markdown_payload=report_diff_to_markdown(report),
        )
    except (OSError, ReportDiffError) as exc:
        return ServiceError("Structured reports could not be compared.", str(exc))


def build_executive_summary_for_ui(
    source_report_path: str | Path,
) -> ExecutiveSummaryView | ServiceError:
    """Build all REP-04 outputs from one saved typed report through the library boundary."""

    source = Path(source_report_path)
    try:
        report = parse_research_report_json(source.read_bytes())
        summary = project_executive_summary(
            report,
            source_report_reference=source.name,
        )
        return ExecutiveSummaryView(
            summary=summary,
            json_payload=summary.model_dump_json(indent=2) + "\n",
            markdown_payload=executive_summary_to_markdown(summary),
            html_payload=executive_summary_to_html(summary),
            pdf_payload=executive_summary_to_pdf_bytes(summary),
        )
    except (
        OSError,
        ReportDiffError,
        ExecutiveSummaryError,
        ExecutiveSummaryLayoutError,
    ) as exc:
        return ServiceError("Executive summary could not be generated.", str(exc))


def append_analyst_annotation_for_ui(
    registry_path: str | Path,
    *,
    target_kind: AnalystAnnotationTargetKind | str,
    target_id: str,
    author_label: str,
    note: str,
    decision_label: AnalystDecisionLabel | str = AnalystDecisionLabel.OBSERVATION,
    target_fingerprint: str | None = None,
) -> AnalystAnnotation | ServiceError:
    """Append one REP-02 annotation through the typed registry boundary."""

    try:
        request = AnalystAnnotationRequest(
            target=AnalystArtifactReference(
                kind=AnalystAnnotationTargetKind(target_kind),
                artifact_id=target_id,
                artifact_fingerprint=target_fingerprint or None,
            ),
            author_label=author_label,
            note=note,
            decision_label=AnalystDecisionLabel(decision_label),
        )
        return Registry(registry_path).append_analyst_annotation(request)
    except Exception as exc:
        return ServiceError("Analyst annotation could not be appended.", str(exc))


def list_analyst_annotations_for_ui(
    registry_path: str | Path,
    *,
    target_kind: AnalystAnnotationTargetKind | str,
    target_id: str,
    target_fingerprint: str | None = None,
    limit: int = 100,
) -> AnalystAnnotationHistory | ServiceError:
    """Read one target-scoped REP-02 history page for the Reports UI."""

    try:
        target = AnalystArtifactReference(
            kind=AnalystAnnotationTargetKind(target_kind),
            artifact_id=target_id,
            artifact_fingerprint=target_fingerprint or None,
        )
        return Registry(registry_path).list_analyst_annotations(target=target, limit=limit)
    except Exception as exc:
        return ServiceError("Analyst annotation history could not be loaded.", str(exc))


def generate_research_export_for_ui(
    export_kind: Literal["metrics", "comparison", "statistical_study", "rules"],
    primary_path: str | Path,
    table_output_path: str | Path,
    *,
    secondary_path: str | Path | None = None,
    figure_output_path: str | Path | None = None,
    overwrite: bool = False,
) -> ResearchExportReceipt | ServiceError:
    """Build REP-01 outputs through the deterministic reporting library."""

    try:
        if export_kind == "statistical_study":
            study = parse_statistical_study_json(Path(primary_path).read_bytes())
            projection = project_statistical_study(study)
        else:
            primary = validate_bundle_for_ui(primary_path)
            if primary.metrics is None or primary.diagnostic_report is None:
                return ServiceError(
                    "Research export requires an accepted bundle.",
                    primary.validation.report.status.value,
                )
            if export_kind == "metrics":
                projection = project_metric_collection(primary.metrics)
            elif export_kind == "rules":
                projection = project_diagnostic_report(primary.diagnostic_report)
            elif export_kind == "comparison":
                if secondary_path is None:
                    return ServiceError("Comparison export requires a second bundle path.")
                secondary = validate_bundle_for_ui(secondary_path)
                if secondary.metrics is None:
                    return ServiceError(
                        "Comparison export requires two accepted bundles.",
                        secondary.validation.report.status.value,
                    )
                projection = project_comparison_report(
                    compare_metric_collections(primary.metrics, secondary.metrics)
                )
            else:
                return ServiceError("Unsupported research export kind.", export_kind)
        return write_projection_exports(
            projection,
            table_output_path,
            figure_path=figure_output_path,
            overwrite=overwrite,
        )
    except (FileExistsError, OSError, ValidationError, ValueError) as exc:
        return ServiceError("Research export could not be generated.", str(exc))


def _infer_report_type(name: str) -> str:
    lowered = name.lower()
    if "diagnostic" in lowered:
        return "diagnostics"
    if " vs " in lowered or "_vs_" in lowered:
        return "comparison"
    if "full" in lowered:
        return "full"
    return "run"


def _scenario_hint(name: str) -> str | None:
    stem = Path(name).stem
    for prefix in ("baseline", "stressed", "under_offloading", "infrastructure_bottleneck"):
        if stem.startswith(prefix):
            return prefix
    return None

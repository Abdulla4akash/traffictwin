"""Report Dashboard page."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import streamlit as st

from traffictwin.annotations import (
    AnalystAnnotationTargetKind,
    AnalystDecisionLabel,
)
from traffictwin.ui.components.cards import report_card, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    append_analyst_annotation_for_ui,
    build_executive_summary_for_ui,
    compare_structured_reports_for_ui,
    generate_research_export_for_ui,
    list_analyst_annotations_for_ui,
    list_workspace_reports,
    regenerate_report_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render report inventory and deliberate report generation."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.REPORTS))
    st.info("Reports are deterministic exports. They are never regenerated automatically.")
    workspace = config.workspace_path
    reports = list_workspace_reports(workspace)

    section_header("Available Reports")
    query = st.text_input("Search reports", value="")
    filtered = [
        report
        for report in reports
        if not query
        or query.lower()
        in " ".join(
            [
                report.name,
                report.report_type,
                report.format_label,
                report.scenario_hint or "",
            ]
        ).lower()
    ]
    if filtered:
        for report in filtered:
            with st.expander(report.name, expanded=False):
                report_card(
                    title=report.name,
                    report_type=report.report_type,
                    path=str(report.path),
                    modified=report.modified_at,
                    format_label=report.format_label,
                )
                st.download_button(
                    "Download",
                    data=report.path.read_bytes(),
                    file_name=report.name,
                )
    else:
        st.info("No reports found for the active workspace.")

    section_header("Regenerate Report", "Choose explicit inputs before regenerating.")
    default_bundle = (
        workspace / "bundles" / "baseline"
        if workspace is not None
        else Path("tests/fixtures/bundles/baseline_valid")
    )
    report_type = st.selectbox("Report type", ["run", "compare", "diagnostics", "full"])
    primary = Path(st.text_input("Primary bundle path", value=str(default_bundle)))
    secondary_value = ""
    if report_type in {"compare", "full"}:
        default_secondary = (
            workspace / "bundles" / "stressed_demand"
            if workspace is not None
            else Path("tests/fixtures/bundles/variation_valid")
        )
        secondary_value = st.text_input(
            "Secondary/baseline bundle path",
            value=str(default_secondary),
        )
    default_output = (
        workspace / "reports" / f"manual_{report_type}.md"
        if workspace is not None
        else Path("reports") / f"manual_{report_type}.md"
    )
    output = Path(st.text_input("Output report path", value=str(default_output)))
    include_annotations = st.checkbox(
        "Include matching append-only analyst annotations",
        value=False,
        disabled=not config.registry_path.is_file(),
        help=(
            "Annotations render in a separate non-computed section and never change report "
            "claims or findings."
        ),
    )
    if st.button("Regenerate Selected Report"):
        generated = regenerate_report_for_ui(
            report_type,
            primary,
            output,
            secondary_path=Path(secondary_value) if secondary_value else None,
            annotation_registry_path=config.registry_path if include_annotations else None,
        )
        if isinstance(generated, ServiceError):
            st.error(generated.message)
            st.code(generated.detail or "")
        else:
            st.success(f"Report generated: {generated}")

    report_root = workspace / "reports" if workspace is not None else Path("reports")
    section_header(
        "One-page Executive Summary (REP-04)",
        "Render a supervisor-facing A4 summary from one saved typed report JSON.",
    )
    st.info(
        "The summary selects existing typed claims by a published deterministic policy. Source "
        "mode, complete availability counts, every warning and limitation, and provenance links "
        "remain visible. PDF overflow is refused instead of deleting caveats."
    )
    executive_source = Path(
        st.text_input(
            "Executive summary source report JSON",
            value=str(report_root / "baseline_report.json"),
            key="reports_executive_source",
        )
    )
    if st.button("Generate One-page Executive Summary", key="reports_executive_generate"):
        executive_view = build_executive_summary_for_ui(executive_source)
        if isinstance(executive_view, ServiceError):
            st.error(executive_view.message)
            st.code(executive_view.detail or "")
        else:
            summary = executive_view.summary
            st.success(
                f"Executive summary ready · {summary.source_mode.value} · "
                f"fingerprint {summary.fingerprint()[:12]}"
            )
            availability = summary.availability
            availability_columns = st.columns(4)
            availability_columns[0].metric("Typed claims", availability.total_claims)
            availability_columns[1].metric("Available", availability.available_claims)
            availability_columns[2].metric("Unavailable", availability.unavailable_claims)
            availability_columns[3].metric("Beyond highlights", summary.omitted_claims)
            st.dataframe(
                [
                    {
                        "rank": item.rank,
                        "claim": item.label,
                        "status": item.status,
                        "availability": item.availability.value,
                        "value": item.display_value,
                        "provenance": item.provenance_reference_id,
                    }
                    for item in summary.highlights
                ],
                width="stretch",
                hide_index=True,
            )
            st.warning("\n\n".join(summary.warnings))
            with st.expander("Limitations and provenance links", expanded=True):
                for limitation in summary.limitations:
                    st.write(f"- {limitation}")
                for link in summary.provenance_links:
                    st.markdown(
                        f"- **{link.reference_id}** [{link.label}]({link.href}) "
                        f"`{link.fingerprint[:12]}`"
                    )
            download_columns = st.columns(4)
            download_columns[0].download_button(
                "Download Summary PDF",
                data=executive_view.pdf_payload,
                file_name="executive_summary.pdf",
                mime="application/pdf",
            )
            download_columns[1].download_button(
                "Download Summary HTML",
                data=executive_view.html_payload,
                file_name="executive_summary.html",
                mime="text/html",
            )
            download_columns[2].download_button(
                "Download Summary Markdown",
                data=executive_view.markdown_payload,
                file_name="executive_summary.md",
                mime="text/markdown",
            )
            download_columns[3].download_button(
                "Download Summary JSON",
                data=executive_view.json_payload,
                file_name="executive_summary.json",
                mime="application/json",
            )

    section_header(
        "Structured Report Diff (REP-03)",
        "Compare saved typed report JSON payloads before rendering; prose is never evidence.",
    )
    st.info(
        "The diff uses typed metric, rule, and comparison claim snapshots only. Narrative text, "
        "layout, timestamps, analyst annotations, and reproduction commands are excluded."
    )
    diff_baseline = Path(
        st.text_input(
            "Baseline structured report JSON",
            value=str(report_root / "baseline_report.json"),
            key="reports_diff_baseline",
        )
    )
    diff_variation = Path(
        st.text_input(
            "Variation structured report JSON",
            value=str(report_root / "variation_report.json"),
            key="reports_diff_variation",
        )
    )
    if st.button("Compare Structured Reports", key="reports_diff_compare"):
        diff_view = compare_structured_reports_for_ui(diff_baseline, diff_variation)
        if isinstance(diff_view, ServiceError):
            st.error(diff_view.message)
            st.code(diff_view.detail or "")
        else:
            diff_report = diff_view.report
            st.success(
                f"Structured diff status: {diff_report.status.value} · "
                f"fingerprint {diff_report.fingerprint()[:12]}"
            )
            st.dataframe(
                [
                    {
                        "section": section.section,
                        "classification": section.classification.value,
                        "typed_claims": len(section.claims),
                        "unavailable_reasons": ", ".join(
                            item.value for item in section.unavailable_reasons
                        ),
                    }
                    for section in diff_report.sections
                ],
                width="stretch",
                hide_index=True,
            )
            st.download_button(
                "Download Structured Diff JSON",
                data=diff_view.json_payload,
                file_name="structured_report_diff.json",
                mime="application/json",
            )
            st.download_button(
                "Download Structured Diff Markdown",
                data=diff_view.markdown_payload,
                file_name="structured_report_diff.md",
                mime="text/markdown",
            )

    section_header(
        "Analyst Annotations (REP-02)",
        "Append notes or decisions to typed artifact references without rewriting evidence.",
    )
    st.info(
        "Analyst-authored history is structurally separate from computed findings. Entries are "
        "append-only: they cannot edit metrics, rules, provenance, fingerprints, or earlier notes."
    )
    annotation_kind = st.selectbox(
        "Annotation target type",
        [item.value for item in AnalystAnnotationTargetKind],
        index=1,
        key="reports_annotation_kind",
    )
    selected_run = st.session_state.get("selected_run_id")
    annotation_target_id = st.text_input(
        "Annotation target ID",
        value=str(selected_run or "run-baseline-001"),
        key="reports_annotation_target_id",
    )
    annotation_fingerprint = st.text_input(
        "Exact target fingerprint (optional)",
        value="",
        key="reports_annotation_fingerprint",
    )
    annotation_author = st.text_input(
        "Analyst author label",
        value="",
        key="reports_annotation_author",
    )
    annotation_decision = st.selectbox(
        "Analyst decision label",
        [item.value for item in AnalystDecisionLabel],
        key="reports_annotation_decision",
    )
    annotation_note = st.text_area(
        "Analyst note",
        value="",
        max_chars=4_000,
        key="reports_annotation_note",
    )
    if st.button("Append Analyst Annotation", key="reports_annotation_append"):
        appended = append_analyst_annotation_for_ui(
            config.registry_path,
            target_kind=annotation_kind,
            target_id=annotation_target_id,
            target_fingerprint=annotation_fingerprint or None,
            author_label=annotation_author,
            note=annotation_note,
            decision_label=annotation_decision,
        )
        if isinstance(appended, ServiceError):
            st.error(appended.message)
            st.code(appended.detail or "")
        else:
            st.success(f"Annotation #{appended.sequence} appended: {appended.annotation_id}")
    if config.registry_path.is_file() and annotation_target_id:
        history = list_analyst_annotations_for_ui(
            config.registry_path,
            target_kind=annotation_kind,
            target_id=annotation_target_id,
            target_fingerprint=annotation_fingerprint or None,
        )
        if isinstance(history, ServiceError):
            st.warning(history.message)
        elif history.annotations:
            st.caption(
                f"Append-only history · {len(history.annotations)} entries · "
                f"fingerprint {history.fingerprint()[:12]}"
            )
            st.dataframe(
                [
                    {
                        "sequence": item.sequence,
                        "created_at": item.created_at.isoformat(),
                        "author": item.author_label,
                        "decision_label": item.decision_label.value,
                        "note": item.note,
                        "target": item.target.key,
                        "annotation_id": item.annotation_id,
                    }
                    for item in history.annotations
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No analyst-authored history for this exact target scope.")
    else:
        st.caption("The active registry will be created only when an annotation is appended.")

    section_header(
        "LaTeX Research Export (REP-01)",
        "Render escaped tables and deterministic SVG/PDF figures from existing typed results.",
    )
    st.caption(
        "This renderer does not calculate metrics, statistics, or diagnoses. Source mode and "
        "limitations remain visible in every artifact."
    )
    export_kind = cast(
        Literal["metrics", "comparison", "statistical_study", "rules"],
        st.selectbox(
            "Research artifact",
            ["metrics", "comparison", "statistical_study", "rules"],
            key="reports_latex_kind",
        ),
    )
    research_primary_default = default_bundle
    if export_kind == "statistical_study":
        research_primary_default = (
            workspace / "exports" / "statistical_study.json"
            if workspace is not None
            else Path("statistical_study.json")
        )
    research_output_root = workspace / "reports" if workspace is not None else Path("reports")
    if st.session_state.get("_reports_latex_defaults_kind") != export_kind:
        st.session_state["reports_latex_primary"] = str(research_primary_default)
        st.session_state["reports_latex_output"] = str(
            research_output_root / f"research_{export_kind}.tex"
        )
        st.session_state["_reports_latex_defaults_kind"] = export_kind
    research_primary = Path(
        st.text_input(
            "Research source path",
            key="reports_latex_primary",
        )
    )
    research_secondary: Path | None = None
    if export_kind == "comparison":
        comparison_default = (
            workspace / "bundles" / "stressed_demand"
            if workspace is not None
            else Path("tests/fixtures/bundles/variation_valid")
        )
        research_secondary = Path(
            st.text_input(
                "Comparison variation bundle",
                value=str(comparison_default),
                key="reports_latex_secondary",
            )
        )
    table_output = Path(
        st.text_input(
            "LaTeX table output",
            key="reports_latex_output",
        )
    )
    figure_format = st.selectbox(
        "Static figure",
        ["svg", "pdf", "none"],
        key="reports_latex_figure_format",
    )
    figure_output: Path | None = None
    if figure_format != "none":
        figure_signature = f"{export_kind}:{figure_format}"
        if st.session_state.get("_reports_latex_figure_signature") != figure_signature:
            st.session_state["reports_latex_figure_output"] = str(
                research_output_root / f"research_{export_kind}.{figure_format}"
            )
            st.session_state["_reports_latex_figure_signature"] = figure_signature
        figure_output = Path(
            st.text_input(
                "Figure output",
                key="reports_latex_figure_output",
            )
        )
    research_overwrite = st.checkbox(
        "Overwrite exact existing research-export files",
        value=False,
        key="reports_latex_overwrite",
    )
    if st.button("Generate LaTeX Research Export", key="reports_latex_generate"):
        receipt = generate_research_export_for_ui(
            export_kind,
            research_primary,
            table_output,
            secondary_path=research_secondary,
            figure_output_path=figure_output,
            overwrite=research_overwrite,
        )
        if isinstance(receipt, ServiceError):
            st.error(receipt.message)
            st.code(receipt.detail or "")
        else:
            st.success(f"Research export generated: {receipt.projection_fingerprint[:12]}")
            st.dataframe(
                [item.model_dump(mode="json") for item in receipt.files],
                width="stretch",
                hide_index=True,
            )

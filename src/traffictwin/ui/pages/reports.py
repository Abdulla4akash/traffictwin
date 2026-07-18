"""Report Dashboard page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.ui.components.cards import report_card, section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
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
    if st.button("Regenerate Selected Report"):
        generated = regenerate_report_for_ui(
            report_type,
            primary,
            output,
            secondary_path=Path(secondary_value) if secondary_value else None,
        )
        if isinstance(generated, ServiceError):
            st.error(generated.message)
            st.code(generated.detail or "")
        else:
            st.success(f"Report generated: {generated}")

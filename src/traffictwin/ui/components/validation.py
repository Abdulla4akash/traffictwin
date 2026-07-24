"""Validation report components."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.tables import (
    table_column_config,
    validation_finding_rows,
    validation_summary_rows,
)
from traffictwin.validation.report import ValidationReport


def render_validation_report(report: ValidationReport) -> None:
    """Render validation summary and findings."""

    st.subheader("Validation Report")
    st.markdown(badge_markdown(report.status.value))
    summary_rows = validation_summary_rows(report)
    st.dataframe(
        summary_rows,
        width="stretch",
        hide_index=True,
        column_config=table_column_config(summary_rows),
    )
    if report.findings:
        with st.expander(f"Findings ({len(report.findings)})", expanded=True):
            finding_rows = validation_finding_rows(report)
            st.dataframe(
                finding_rows,
                width="stretch",
                hide_index=True,
                column_config=table_column_config(finding_rows),
            )
    else:
        st.success("No validation findings.")

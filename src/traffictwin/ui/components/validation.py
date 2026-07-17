"""Validation report components."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.tables import validation_finding_rows, validation_summary_rows
from traffictwin.validation.report import ValidationReport


def render_validation_report(report: ValidationReport) -> None:
    """Render validation summary and findings."""

    st.subheader("Validation Report")
    st.table(validation_summary_rows(report))
    if report.findings:
        with st.expander(f"Findings ({len(report.findings)})", expanded=True):
            st.dataframe(validation_finding_rows(report), width="stretch")
    else:
        st.success("No validation findings.")

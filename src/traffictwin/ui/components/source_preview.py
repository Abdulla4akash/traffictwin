"""Source-row preview components."""

from __future__ import annotations

import streamlit as st

from traffictwin.provenance.models import SourceRowPreview


def render_source_row_preview(preview: SourceRowPreview) -> None:
    """Render a safe, bounded source-row preview."""

    st.write(
        {
            "file": preview.file,
            "row": preview.row_number,
            "status": preview.status.value,
            "inclusion_status": preview.inclusion_status,
            "canonical_record_type": preview.canonical_record_type or "Unavailable",
        }
    )
    if preview.warnings:
        st.warning("\n".join(preview.warnings))
    if preview.raw_values:
        st.markdown("**Requested raw row**")
        st.dataframe([preview.raw_values], width="stretch", hide_index=True)
    if preview.surrounding_rows:
        st.markdown("**Surrounding rows**")
        st.dataframe(
            [{"row_number": row.row_number, **row.values} for row in preview.surrounding_rows],
            width="stretch",
            hide_index=True,
        )
    if preview.canonical_values:
        with st.expander("Canonical mapping"):
            st.json(preview.canonical_values)
    if preview.conversions:
        with st.expander("Declared mapping and units"):
            st.json(preview.conversions)
    if preview.validation_findings:
        with st.expander("Validation findings for this row", expanded=True):
            st.dataframe(preview.validation_findings, width="stretch", hide_index=True)

"""Source-row preview components."""

from __future__ import annotations

import streamlit as st

from traffictwin.provenance.models import SourceRowPreview
from traffictwin.ui.components.badges import badge_markdown


def render_source_row_preview(preview: SourceRowPreview) -> None:
    """Render a safe, bounded source-row preview."""

    with st.container(border=True):
        st.markdown(f"**Source row** — `{preview.file}`, row {preview.row_number}")
        st.markdown(
            f"{badge_markdown(preview.status.value)} :gray-badge[{preview.inclusion_status}]"
        )
        st.caption(f"Canonical record type: {preview.canonical_record_type or 'Unavailable'}")
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

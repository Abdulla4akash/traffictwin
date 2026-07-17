"""Evidence & Diagnostic Readiness page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.labels import DIAGNOSTIC_NOTICE
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.tables import metric_rows


def render() -> None:
    """Render evidence readiness."""

    st.title("Evidence & Diagnostic Readiness")
    st.info(DIAGNOSTIC_NOTICE)
    analysis = load_selected_analysis()
    if analysis is None:
        return
    render_source_caption(analysis)
    report = analysis.validation.report
    insufficient = analysis.validation.insufficient_evidence

    st.subheader("Validation Status")
    st.json(
        {
            "status": report.status.value,
            "may_import": report.may_import,
            "counts_by_severity": report.counts_by_severity,
        }
    )

    st.subheader("Evidence Availability")
    st.json(analysis.validation.evidence.model_dump(mode="json"))

    st.subheader("Diagnostic Readiness")
    st.json(insufficient.model_dump(mode="json"))

    st.subheader("Metric Collection Summary")
    if analysis.metrics is not None:
        st.write(
            {
                "run_id": analysis.metrics.run_id,
                "metric_version": analysis.metrics.metric_version,
                "metric_count": len(analysis.metrics.results),
                "unavailable_count": analysis.metrics.unavailable_count,
                "partial_count": analysis.metrics.partial_count,
            }
        )
        with st.expander("Metric details"):
            st.dataframe(metric_rows(analysis.metrics), width="stretch", hide_index=True)

    st.subheader("Evidence Pack")
    if analysis.evidence_pack is None:
        st.info("Evidence pack is unavailable because the bundle was not accepted.")
    else:
        st.write(
            {
                "pack_id": analysis.evidence_pack.pack_id,
                "fingerprint": analysis.evidence_pack.fingerprint(),
            }
        )
        st.download_button(
            "Download EvidencePack JSON",
            data=analysis.evidence_pack.to_json(),
            file_name=f"{analysis.evidence_pack.pack_id}.json",
            mime="application/json",
        )

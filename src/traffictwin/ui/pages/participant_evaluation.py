"""Labelled mock participant-result analysis page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from pydantic import ValidationError

from traffictwin.evaluation.participants import (
    analyse_participant_results,
    load_mock_participant_dataset,
    participant_analysis_to_csv,
)
from traffictwin.ui.components.badges import badge_markdown
from traffictwin.ui.tables import table_column_config


def render() -> None:
    """Render descriptive mock-data analysis without implying ethics approval."""

    st.title("Mock Evaluation Analysis")
    st.warning(
        "MOCK DATA ONLY. Ethics approval has not been inferred, no participants have been "
        "recruited, and this page does not authorise data collection."
    )

    st.subheader("Participant-study readiness")
    with st.container(border=True):
        st.markdown(
            f"**Dataset mode:** {badge_markdown('synthetic mock')} · "
            f"**Ethics approval:** {badge_markdown('unavailable')} · "
            f"**Supervisor confirmation:** {badge_markdown('unavailable')} · "
            f"**Recruitment:** {badge_markdown('not started')}"
        )
        st.markdown(
            "No recruitment, consent collection, or formal participant study may begin until "
            "the required institutional ethics approval and supervisor confirmation are recorded. "
            "This page only analyses a labelled synthetic-mock file to verify the software; it "
            "does not create, imply, or accept any of those approvals."
        )
    prerequisites = [
        {"prerequisite": "Institutional ethics approval", "state": "unavailable"},
        {"prerequisite": "Supervisor confirmation of the study design", "state": "unavailable"},
        {"prerequisite": "Approved consent and information sheet", "state": "unavailable"},
        {"prerequisite": "Recruitment authorisation", "state": "unavailable"},
    ]
    st.dataframe(
        prerequisites,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(prerequisites),
    )
    st.caption(
        "Every prerequisite is unavailable. Draft evaluation materials under docs/evaluation/ "
        "remain unsubmitted drafts, not approvals."
    )

    st.subheader("Mock analysis (synthetic only)")
    path = Path(
        st.text_input(
            "Labelled mock result file",
            value="docs/evaluation/mock_results.json",
        )
    )
    if not path.is_file():
        st.info("Select an existing JSON file explicitly labelled dataset_mode=synthetic_mock.")
        return
    try:
        report = analyse_participant_results(load_mock_participant_dataset(path))
    except (OSError, ValueError, ValidationError) as exc:
        st.error("The file was rejected by the synthetic mock-result contract.")
        st.code(str(exc))
        return
    with st.container(border=True):
        st.markdown(f"**Source:** {badge_markdown('synthetic mock')} descriptive analysis only")
        columns = st.columns(3)
        columns[0].metric("Mock records", report.total_records, border=True)
        columns[1].metric("Included", report.included_records, border=True)
        columns[2].metric("Withdrawn excluded", report.withdrawn_records_excluded, border=True)
    st.markdown("**Task summaries**")
    task_rows = [row.model_dump(mode="json") for row in report.task_aggregates]
    st.dataframe(
        task_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(task_rows),
    )
    st.markdown("**Rating summaries**")
    rating_rows = [row.model_dump(mode="json") for row in report.rating_aggregates]
    st.dataframe(
        rating_rows,
        hide_index=True,
        width="stretch",
        column_config=table_column_config(rating_rows),
    )
    st.markdown("**Supplied comment-code counts**")
    comment_rows = [
        {"comment_code": code, "count": count}
        for code, count in report.coded_comment_counts.items()
    ]
    if comment_rows:
        st.dataframe(
            comment_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(comment_rows),
        )
    else:
        st.caption("No coded comments were supplied in the mock dataset.")
    for limitation in report.limitations:
        st.caption(limitation)
    with st.expander("Advanced: complete mock analysis (raw)"):
        st.json(report.model_dump(mode="json"))
    downloads = st.columns(2)
    downloads[0].download_button(
        "Download mock analysis JSON",
        data=report.to_json(),
        file_name="mock-participant-analysis.json",
        mime="application/json",
    )
    downloads[1].download_button(
        "Download mock analysis CSV",
        data=participant_analysis_to_csv(report),
        file_name="mock-participant-analysis.csv",
        mime="text/csv",
    )

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


def render() -> None:
    """Render descriptive mock-data analysis without implying ethics approval."""

    st.title("Mock Evaluation Analysis")
    st.warning(
        "MOCK DATA ONLY. Ethics approval has not been inferred, no participants have been "
        "recruited, and this page does not authorise data collection."
    )
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
    columns = st.columns(3)
    columns[0].metric("Mock records", report.total_records)
    columns[1].metric("Included", report.included_records)
    columns[2].metric("Withdrawn excluded", report.withdrawn_records_excluded)
    st.subheader("Task summaries")
    st.table(
        [row.model_dump(mode="json") for row in report.task_aggregates],
    )
    st.subheader("Rating summaries")
    st.table(
        [row.model_dump(mode="json") for row in report.rating_aggregates],
    )
    st.subheader("Supplied comment-code counts")
    st.json(report.coded_comment_counts)
    for limitation in report.limitations:
        st.caption(limitation)
    st.download_button(
        "Download mock analysis JSON",
        data=report.to_json(),
        file_name="mock-participant-analysis.json",
        mime="application/json",
    )
    st.download_button(
        "Download mock analysis CSV",
        data=participant_analysis_to_csv(report),
        file_name="mock-participant-analysis.csv",
        mime="text/csv",
    )

"""Lightweight local search page."""

from __future__ import annotations

import streamlit as st

from traffictwin.registry_search import SearchCategory
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import ServiceError, search_for_ui
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render local deterministic search."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.SEARCH))
    st.info(
        "REP-05 searches local registry records and bounded report text only. "
        "It is read-only, path-redacted, deterministic, and uses no external service."
    )
    query = st.text_input(
        "Search findings, annotations, reports, runs, experiments, and evidence references"
    )
    controls = st.columns([3, 1])
    selected = controls[0].multiselect(
        "Categories",
        options=[category.value for category in SearchCategory],
        default=[category.value for category in SearchCategory],
        format_func=lambda value: value.replace("_", " ").title(),
    )
    limit = controls[1].selectbox("Result limit", options=[10, 25, 50, 100, 200], index=2)

    section_header("Results")
    if not query:
        st.caption(
            "Enter an identifier, research term, finding statement, annotation text, report term, "
            "or evidence key. All query terms must match."
        )
        return
    if not selected:
        st.warning("Select at least one result category.")
        return
    result = search_for_ui(
        query,
        config.registry_path,
        config.workspace_path,
        categories=selected,
        limit=int(limit),
    )
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            st.caption(result.detail)
        return

    summary = st.columns(4)
    summary[0].metric("Candidates", result.candidate_count)
    summary[1].metric("Matches", result.matching_count)
    summary[2].metric("Returned", result.returned_count)
    summary[3].metric("Redactions", result.redaction_count)
    if result.hits:
        st.dataframe(
            [
                {
                    "rank": hit.rank,
                    "category": hit.category.value.replace("_", " ").title(),
                    "title": hit.title,
                    "snippet": hit.snippet,
                    "reference": hit.reference,
                    "score": hit.score,
                }
                for hit in result.hits
            ],
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No local record matched every query term in the selected categories.")
    if result.omitted_match_count:
        st.caption(f"{result.omitted_match_count} lower-ranked matches were omitted by the limit.")
    if result.skipped_report_count:
        st.warning(
            f"{result.skipped_report_count} report files were skipped because they were unsafe, "
            "unreadable, or outside the text-size contract."
        )
    st.caption(f"Deterministic result fingerprint: `{result.fingerprint()}`")

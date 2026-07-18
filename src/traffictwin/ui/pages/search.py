"""Lightweight local search page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import search_for_ui
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render local deterministic search."""

    render_page_header(st.session_state.get("_active_ui_page", UiPage.SEARCH))
    st.info("Search is local and metadata-only; no external search service is used.")
    query = st.text_input("Search runs, experiments, reports, metrics, rules, and source files")
    hits = search_for_ui(query, config.registry_path, config.workspace_path)

    section_header("Results")
    if hits:
        st.dataframe(
            [
                {
                    "category": hit.category,
                    "title": hit.title,
                    "detail": hit.detail,
                    "reference": hit.reference,
                }
                for hit in hits
            ],
            hide_index=True,
            width="stretch",
        )
    elif query:
        st.info("No local metadata matched the query.")
    else:
        st.caption("Enter a run ID, metric key, rule ID, report name, or source file name.")

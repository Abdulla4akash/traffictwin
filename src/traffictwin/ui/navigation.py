"""Navigation helpers."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.labels import PAGE_DESCRIPTIONS, UiPage

PAGE_GROUPS: dict[str, list[UiPage]] = {
    "Workspace": [
        UiPage.HOME,
        UiPage.GUIDED_DEMO,
        UiPage.EXPERIMENT_MANAGER,
        UiPage.REPORTS,
        UiPage.SEARCH,
    ],
    "Workflow": [UiPage.SCENARIO, UiPage.BUNDLE_IMPORT, UiPage.TOS_DATA, UiPage.COMPARE],
    "Analysis": [
        UiPage.TOS_RESULTS,
        UiPage.TOS_REPLAY,
        UiPage.TOS_TRAINING,
        UiPage.RUN_OVERVIEW,
        UiPage.OPERATIONS,
        UiPage.INFRASTRUCTURE,
        UiPage.JOURNEY_TIME,
        UiPage.EVIDENCE,
        UiPage.PROVENANCE,
    ],
    "Project": [UiPage.SETTINGS, UiPage.ABOUT],
}


def page_options() -> list[str]:
    """Return page labels in sidebar order."""

    return [page.value for pages in PAGE_GROUPS.values() for page in pages]


def select_page() -> UiPage:
    """Render and return the selected page."""

    label = st.sidebar.radio("Navigation", page_options(), key="active_page")
    return UiPage(label)


def activate_page(page: UiPage) -> None:
    """Select a page from a Streamlit widget callback."""

    st.session_state["active_page"] = page.value


def render_sidebar_context(page: UiPage) -> None:
    """Render consistent sidebar context for the active page."""

    st.sidebar.caption(PAGE_DESCRIPTIONS[page])


def render_page_header(page: UiPage) -> None:
    """Render a consistent page heading and breadcrumb."""

    st.caption(f"TrafficTwin / {page.value}")
    st.title(page.value)
    st.caption(PAGE_DESCRIPTIONS[page])

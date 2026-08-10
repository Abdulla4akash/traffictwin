"""Navigation helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

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
    "Workflow": [
        UiPage.EXPERIMENT_PLANNER,
        UiPage.PARAMETER_SWEEP,
        UiPage.SCENARIO_MUTATION,
        UiPage.WHATIF_STUDIO,
        UiPage.SCENARIO,
        UiPage.MANIFEST_WIZARD,
        UiPage.BUNDLE_IMPORT,
        UiPage.SUMO_IMPORT,
        UiPage.TOS_DATA,
        UiPage.VEC_WORKBENCH,
        UiPage.COMPARE,
    ],
    "Analysis": [
        UiPage.TOS_RESULTS,
        UiPage.TOS_REPLAY,
        UiPage.TOS_TRAINING,
        UiPage.TRIVIALITY,
        UiPage.RUN_OVERVIEW,
        UiPage.TEMPORAL_METRICS,
        UiPage.ENERGY,
        UiPage.FAIRNESS,
        UiPage.THRESHOLD_SENSITIVITY,
        UiPage.STATISTICAL_STUDY,
        UiPage.SPATIAL_RSU,
        UiPage.OPERATIONS,
        UiPage.INFRASTRUCTURE,
        UiPage.JOURNEY_TIME,
        UiPage.CONSEQUENCE_LENSES,
        UiPage.PORTFOLIO_EXPLORER,
        UiPage.MANCHESTER_EVIDENCE_HUB,
        UiPage.EVIDENCE,
        UiPage.PROVENANCE,
        UiPage.RESOURCE_STRATEGY_EXPLORER,
    ],
    "Project": [UiPage.PARTICIPANT_EVALUATION, UiPage.SETTINGS, UiPage.ABOUT],
}

V07_PENDING_PAGE_KEY = "_v07_pending_page"


def page_options() -> list[str]:
    """Return page labels in sidebar order."""

    return [page.value for pages in PAGE_GROUPS.values() for page in pages]


def select_page() -> UiPage:
    """Render and return the selected page."""

    label = st.sidebar.radio("Navigation", page_options(), key="active_page")
    return UiPage(label)


def activate_page(page: UiPage) -> None:
    """Select a page from a Streamlit widget callback."""

    if st.session_state.get("_v07_navigation_active") is True:
        # ``st.switch_page`` triggers a rerun and is therefore a no-op when invoked
        # from inside a widget callback.  Persist the exact target and consume it at
        # the start of the next top-level page execution instead.
        st.session_state[V07_PENDING_PAGE_KEY] = page.value
        return
    st.session_state["active_page"] = page.value


def redirect_pending_v07_page(current_page: UiPage) -> None:
    """Consume one callback-requested candidate route at top-level execution."""

    if st.session_state.get("_v07_navigation_active") is not True:
        return
    pending = st.session_state.pop(V07_PENDING_PAGE_KEY, None)
    if pending is None:
        return
    try:
        target = UiPage(pending)
    except ValueError as exc:
        raise ValueError(f"unknown pending v0.7 page: {pending!r}") from exc
    if target is current_page:
        return

    from traffictwin.ui.navigation_v07 import page_script_for

    st.switch_page(page_script_for(target))


def navigation_button(
    button: Callable[..., bool],
    label: str,
    page: UiPage,
    *,
    key: str | None = None,
    kind: str | None = None,
    width: Literal["content", "stretch"] = "content",
) -> None:
    """Render one router-aware page action without callback rerun traps."""

    kwargs: dict[str, object] = {"width": width}
    if key is not None:
        kwargs["key"] = key
    if kind is not None:
        kwargs["type"] = kind

    if st.session_state.get("_v07_navigation_active") is True:
        if button(label, **kwargs):
            from traffictwin.ui.navigation_v07 import page_script_for

            st.switch_page(page_script_for(page))
        return
    button(label, on_click=activate_page, args=(page,), **kwargs)


def render_sidebar_context(page: UiPage) -> None:
    """Render the page description once, as shared sidebar context."""

    st.sidebar.caption(PAGE_DESCRIPTIONS[page])


def render_page_header(page: UiPage) -> None:
    """Render a consistent page heading and breadcrumb.

    The page description renders once, in the sidebar context, so the header
    stays a small breadcrumb plus title without duplicated copy.
    """

    st.caption(f"TrafficTwin / {page.value}")
    st.title(page.value)

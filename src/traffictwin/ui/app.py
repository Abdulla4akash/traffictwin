"""Streamlit app entry point."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import select_page
from traffictwin.ui.pages import (
    bundle_import,
    compare,
    evidence_readiness,
    home,
    infrastructure,
    journey_time,
    operations,
    run_overview,
    scenario_studio,
)
from traffictwin.ui.state import ensure_session_state, load_ui_config


def main() -> None:
    """Run the Streamlit application."""

    config = load_ui_config()
    st.set_page_config(page_title=config.page_title, layout="wide")
    ensure_session_state(st.session_state)
    st.sidebar.title("TrafficTwin")
    st.sidebar.caption("Import-first research UI")
    page = select_page()

    if page is UiPage.HOME:
        home.render(config)
    elif page is UiPage.SCENARIO:
        scenario_studio.render(config)
    elif page is UiPage.BUNDLE_IMPORT:
        bundle_import.render(config)
    elif page is UiPage.OPERATIONS:
        operations.render()
    elif page is UiPage.RUN_OVERVIEW:
        run_overview.render()
    elif page is UiPage.INFRASTRUCTURE:
        infrastructure.render(config.metric_engine_config)
    elif page is UiPage.COMPARE:
        compare.render()
    elif page is UiPage.JOURNEY_TIME:
        journey_time.render()
    elif page is UiPage.EVIDENCE:
        evidence_readiness.render()


if __name__ == "__main__":
    main()

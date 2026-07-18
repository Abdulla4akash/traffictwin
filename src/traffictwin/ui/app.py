"""Streamlit app entry point."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_sidebar_context, select_page
from traffictwin.ui.pages import (
    about,
    bundle_import,
    compare,
    evidence_readiness,
    experiment_manager,
    home,
    infrastructure,
    journey_time,
    operations,
    provenance_explorer,
    reports,
    run_overview,
    scenario_builder,
    search,
    settings,
    tos_data_import,
    tos_replay,
    tos_results,
    tos_training_audit,
)
from traffictwin.ui.state import ensure_session_state, load_ui_config
from traffictwin.ui.theme import apply_research_theme


def main() -> None:
    """Run the Streamlit application."""

    config = load_ui_config()
    st.set_page_config(page_title=config.page_title, layout="wide")
    apply_research_theme()
    ensure_session_state(st.session_state)
    if config.workspace_path is not None:
        default_bundle = config.default_fixture_path / "baseline"
        current_bundle = str(st.session_state.get("selected_bundle_path", ""))
        if default_bundle.exists() and (
            not current_bundle or current_bundle.startswith("tests/fixtures")
        ):
            st.session_state["selected_bundle_path"] = str(default_bundle)
            st.session_state["selected_baseline_run"] = str(default_bundle)
            variation = config.default_fixture_path / "stressed_demand"
            if variation.exists():
                st.session_state["selected_variation_run"] = str(variation)
    st.sidebar.title("TrafficTwin")
    st.sidebar.caption("Import-first research UI")
    page = select_page()
    st.session_state["_active_ui_page"] = page
    render_sidebar_context(page)

    if page is UiPage.HOME:
        home.render(config)
    elif page is UiPage.SCENARIO:
        scenario_builder.render(config)
    elif page is UiPage.BUNDLE_IMPORT:
        bundle_import.render(config)
    elif page is UiPage.TOS_DATA:
        tos_data_import.render(config)
    elif page is UiPage.TOS_RESULTS:
        tos_results.render(config)
    elif page is UiPage.TOS_REPLAY:
        tos_replay.render(config)
    elif page is UiPage.TOS_TRAINING:
        tos_training_audit.render(config)
    elif page is UiPage.EXPERIMENT_MANAGER:
        experiment_manager.render(config)
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
    elif page is UiPage.PROVENANCE:
        provenance_explorer.render()
    elif page is UiPage.REPORTS:
        reports.render(config)
    elif page is UiPage.SEARCH:
        search.render(config)
    elif page is UiPage.SETTINGS:
        settings.render(config)
    elif page is UiPage.ABOUT:
        about.render()


if __name__ == "__main__":
    main()

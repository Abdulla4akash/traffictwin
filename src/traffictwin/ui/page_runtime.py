"""Shared execution boundary for legacy and v0.7 Streamlit page routers."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from traffictwin.ui.guided_runtime import render_guided_assistant
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import redirect_pending_v07_page, render_sidebar_context
from traffictwin.ui.pages import (
    about,
    bundle_import,
    bus_sessions,
    compare,
    energy,
    evidence_readiness,
    experiment_manager,
    experiment_planner,
    fairness,
    guided_demo,
    home,
    infrastructure,
    journey_time,
    manchester_operations,
    manifest_inference,
    match_review,
    operations,
    parameter_sweep,
    participant_evaluation,
    provenance_explorer,
    reports,
    rsu_monitor,
    run_overview,
    scenario_builder,
    scenario_mutation,
    search,
    settings,
    spatial_rsu,
    statistical_study,
    sumo_import,
    temporal_metrics,
    threshold_sensitivity,
    tos_data_import,
    tos_replay,
    tos_results,
    tos_training_audit,
    triviality,
    vec_workbench,
)
from traffictwin.ui.state import UiConfig, load_ui_config

PageRenderer = Callable[[UiConfig], None]


PAGE_RENDERERS: dict[UiPage, PageRenderer] = {
    UiPage.HOME: home.render,
    UiPage.GUIDED_DEMO: guided_demo.render,
    UiPage.EXPERIMENT_PLANNER: experiment_planner.render,
    UiPage.PARAMETER_SWEEP: parameter_sweep.render,
    UiPage.SCENARIO_MUTATION: scenario_mutation.render,
    UiPage.SCENARIO: scenario_builder.render,
    UiPage.BUNDLE_IMPORT: bundle_import.render,
    UiPage.MANIFEST_WIZARD: manifest_inference.render,
    UiPage.SUMO_IMPORT: sumo_import.render,
    UiPage.TOS_DATA: tos_data_import.render,
    UiPage.VEC_WORKBENCH: lambda _config: vec_workbench.render(),
    UiPage.TOS_RESULTS: tos_results.render,
    UiPage.TOS_REPLAY: tos_replay.render,
    UiPage.TOS_TRAINING: tos_training_audit.render,
    UiPage.EXPERIMENT_MANAGER: experiment_manager.render,
    UiPage.TRIVIALITY: triviality.render,
    UiPage.OPERATIONS: operations.render,
    UiPage.RUN_OVERVIEW: lambda _config: run_overview.render(),
    UiPage.TEMPORAL_METRICS: lambda _config: temporal_metrics.render(),
    UiPage.ENERGY: lambda _config: energy.render(),
    UiPage.FAIRNESS: lambda _config: fairness.render(),
    UiPage.THRESHOLD_SENSITIVITY: lambda _config: threshold_sensitivity.render(),
    UiPage.STATISTICAL_STUDY: statistical_study.render,
    UiPage.SPATIAL_RSU: lambda _config: spatial_rsu.render(),
    UiPage.INFRASTRUCTURE: lambda config: infrastructure.render(config.metric_engine_config),
    UiPage.COMPARE: lambda _config: compare.render(),
    UiPage.JOURNEY_TIME: lambda _config: journey_time.render(),
    UiPage.EVIDENCE: lambda _config: evidence_readiness.render(),
    UiPage.PROVENANCE: lambda _config: provenance_explorer.render(),
    UiPage.REPORTS: reports.render,
    UiPage.PARTICIPANT_EVALUATION: lambda _config: participant_evaluation.render(),
    UiPage.SEARCH: search.render,
    UiPage.SETTINGS: settings.render,
    UiPage.ABOUT: lambda _config: about.render(),
}


def render_registered_page(page: UiPage, config: UiConfig) -> None:
    """Render one exact registered page through its existing tested service boundary."""

    render_guided_assistant(page)
    PAGE_RENDERERS[page](config)


def run_page_script(page: UiPage) -> None:
    """Execute one direct ``app_pages`` script under the v0.7 router."""

    redirect_pending_v07_page(page)
    st.session_state["_active_ui_page"] = page
    render_sidebar_context(page)
    render_registered_page(page, load_ui_config())


def run_match_review_page_script() -> None:
    """Execute the additive Match Review page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "match-review"
    st.sidebar.caption(
        "Record one named analyst decision at a time; pending rows stay visibly pending."
    )
    match_review.render(load_ui_config())


def run_bus_sessions_page_script() -> None:
    """Execute the additive Bus Sessions page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "bus-sessions"
    st.sidebar.caption(
        "Aggregate-only measurements from attended bus sessions; buses are never general traffic."
    )
    bus_sessions.render(load_ui_config())


def run_rsu_monitor_page_script() -> None:
    """Execute the additive RSU Monitor page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "rsu-monitor"
    st.sidebar.caption(
        "Per-RSU load over one imported run's window; historical replay, never live."
    )
    rsu_monitor.render(load_ui_config())


def run_manchester_page_script() -> None:
    """Execute the additive Manchester page without changing the 34-page inventory."""

    st.session_state["_active_ui_route"] = "manchester"
    st.sidebar.caption(
        "Explore validated local Manchester evidence without hidden external source access."
    )
    manchester_operations.render(load_ui_config())

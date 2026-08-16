"""Shared execution boundary for legacy and v0.7 Streamlit page routers."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from traffictwin.ui.guided_runtime import render_guided_assistant
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import redirect_pending_v07_page, render_sidebar_context
from traffictwin.ui.pages import (
    about,
    analyst,
    baseline_registry,
    bundle_import,
    bus_sessions,
    calibration_workbench,
    campaigns,
    compare,
    consequence_lenses,
    contract_drafting,
    data_contract_workbench,
    energy,
    event_aligned_analysis,
    event_scenario_bridge,
    evidence_admission,
    evidence_readiness,
    experiment_manager,
    experiment_planner,
    fairness,
    guided_demo,
    home,
    infrastructure,
    journey_time,
    manchester_evidence_hub,
    manchester_gate_d,
    manchester_operations,
    manifest_inference,
    match_review,
    metric_contract_registry,
    operations,
    parameter_sweep,
    participant_evaluation,
    platform_analytics,
    platform_composer,
    platform_decision_safety,
    platform_evidence_matrix,
    platform_forecasts,
    platform_inventory,
    platform_observatory,
    platform_xai_audit,
    portfolio_explorer,
    preregistration_studio,
    provenance_explorer,
    reports,
    reproducibility_replay,
    resource_strategy_explorer,
    rsu_monitor,
    run_overview,
    scenario_builder,
    scenario_mutation,
    search,
    settings,
    source_health,
    spatial_rsu,
    statistical_study,
    study_accrual,
    study_capsule,
    study_workspace,
    sumo_import,
    temporal_metrics,
    threshold_sensitivity,
    tos_data_import,
    tos_replay,
    tos_results,
    tos_training_audit,
    tradeoff_explorer,
    triviality,
    vec_workbench,
    whatif_studio,
    workspace_activation,
)
from traffictwin.ui.state import UiConfig, load_ui_config

PageRenderer = Callable[[UiConfig], None]


PAGE_RENDERERS: dict[UiPage, PageRenderer] = {
    UiPage.HOME: home.render,
    UiPage.GUIDED_DEMO: guided_demo.render,
    UiPage.EXPERIMENT_PLANNER: experiment_planner.render,
    UiPage.PARAMETER_SWEEP: parameter_sweep.render,
    UiPage.SCENARIO_MUTATION: scenario_mutation.render,
    UiPage.WHATIF_STUDIO: whatif_studio.render,
    UiPage.SCENARIO: scenario_builder.render,
    UiPage.DATA_CONTRACT_WORKBENCH: lambda _config: data_contract_workbench.render(_config),
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
    UiPage.EVENT_ALIGNED_ANALYSIS: lambda _config: event_aligned_analysis.render(),
    UiPage.ENERGY: lambda _config: energy.render(),
    UiPage.FAIRNESS: lambda _config: fairness.render(),
    UiPage.THRESHOLD_SENSITIVITY: lambda _config: threshold_sensitivity.render(),
    UiPage.STATISTICAL_STUDY: statistical_study.render,
    UiPage.SPATIAL_RSU: lambda _config: spatial_rsu.render(),
    UiPage.INFRASTRUCTURE: lambda config: infrastructure.render(config.metric_engine_config),
    UiPage.COMPARE: lambda _config: compare.render(),
    UiPage.JOURNEY_TIME: lambda _config: journey_time.render(),
    UiPage.CONSEQUENCE_LENSES: lambda _config: consequence_lenses.render(),
    UiPage.PORTFOLIO_EXPLORER: lambda _config: portfolio_explorer.render(),
    UiPage.MANCHESTER_EVIDENCE_HUB: lambda _config: manchester_evidence_hub.render(),
    UiPage.PREREGISTRATION_STUDIO: preregistration_studio.render,
    UiPage.EVIDENCE: lambda _config: evidence_readiness.render(),
    UiPage.PROVENANCE: lambda _config: provenance_explorer.render(),
    UiPage.RESOURCE_STRATEGY_EXPLORER: lambda _config: resource_strategy_explorer.render(
        load_ui_config()
    ),
    UiPage.REPORTS: reports.render,
    UiPage.STUDY_CAPSULE: study_capsule.render,
    UiPage.PARTICIPANT_EVALUATION: lambda _config: participant_evaluation.render(),
    UiPage.SEARCH: search.render,
    UiPage.SETTINGS: settings.render,
    UiPage.ABOUT: lambda _config: about.render(),
    UiPage.STUDY_WORKSPACE: study_workspace.render,
    UiPage.EVIDENCE_ADMISSION_INBOX: evidence_admission.render,
    UiPage.METRIC_CONTRACT_REGISTRY: metric_contract_registry.render,
    UiPage.CALIBRATION_WORKBENCH: calibration_workbench.render,
    UiPage.BASELINE_REGISTRY: baseline_registry.render,
    UiPage.STUDY_ACCRUAL_MONITOR: study_accrual.render,
    UiPage.REPRODUCIBILITY_REPLAY: reproducibility_replay.render,
    UiPage.CONTRACT_DRAFTING_ASSISTANT: contract_drafting.render,
    UiPage.EVENT_SCENARIO_BRIDGE: lambda _config: event_scenario_bridge.render(),
    UiPage.MULTIOBJECTIVE_TRADEOFF: tradeoff_explorer.render,
    UiPage.WORKSPACE_ACTIVATION: workspace_activation.render,
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


def run_campaigns_page_script() -> None:
    """Execute the additive Campaigns page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "campaigns"
    st.sidebar.caption(
        "One named campaign receipt at a time; a terminal record, never a live campaign."
    )
    campaigns.render(load_ui_config())


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


def run_source_health_page_script() -> None:
    """Execute the additive read-only Source Health page."""

    st.session_state["_active_ui_route"] = "source-health"
    st.sidebar.caption(
        "Local configuration and worker metadata only; no credential test or provider request."
    )
    source_health.render(load_ui_config())


def run_platform_inventory_page_script() -> None:
    """Execute the additive Data Inventory page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-inventory"
    st.sidebar.caption(
        "Allowlisted read-only inventory of recorded datasets; no raw quarantine byte is opened."
    )
    platform_inventory.render(load_ui_config())


def run_platform_forecasts_page_script() -> None:
    """Execute the additive Forecasts page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-forecasts"
    st.sidebar.caption("Bus-fleet climatology with support counts; a forecast is never evidence.")
    platform_forecasts.render(load_ui_config())


def run_analyst_page_script() -> None:
    """Execute the additive TrafficTwin Analyst page outside the normative inventory."""

    st.session_state["_active_ui_route"] = "analyst"
    st.sidebar.caption(
        "Deterministic diagnosis first; optional AI prose renders the result without changing it."
    )
    analyst.render(load_ui_config())


def run_platform_composer_page_script() -> None:
    """Execute the additive What-If Composer page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-composer"
    st.sidebar.caption(
        "Draft-only what-if scenarios; signing and execution are human acts outside this app."
    )
    platform_composer.render(load_ui_config())


def run_platform_analytics_page_script() -> None:
    """Execute the additive Analytics Quality page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-analytics-quality"
    st.sidebar.caption(
        "Immutable operational-quality reports; readiness is never scientific confidence."
    )
    platform_analytics.render(load_ui_config())


def run_platform_evidence_matrix_page_script() -> None:
    """Execute the additive Evidence Matrix page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-evidence-matrix"
    st.sidebar.caption(
        "Digest-bound coverage and exclusions; standing is read-only and effects are not pooled."
    )
    platform_evidence_matrix.render(load_ui_config())


def run_platform_observatory_page_script() -> None:
    """Execute the additive Mechanism Observatory outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-mechanism-observatory"
    st.sidebar.caption(
        "Role-labelled mechanism cards with support, limitations, deviations and citations."
    )
    platform_observatory.render(load_ui_config())


def run_platform_decision_safety_page_script() -> None:
    """Execute the additive Decision Safety page outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-decision-safety"
    st.sidebar.caption(
        "Metric-specific Ruleset v2 advice and non-executable drafts; no execution authority."
    )
    platform_decision_safety.render(load_ui_config())


def run_platform_xai_audit_page_script() -> None:
    """Execute the additive synthetic Decision Audit outside the 34-page inventory."""

    st.session_state["_active_ui_route"] = "platform-xai-audit"
    st.sidebar.caption(
        "Synthetic decision audit only; no causal, faithful, validated or optimality claim."
    )
    platform_xai_audit.render(load_ui_config())


def run_manchester_gate_d_page_script() -> None:
    """Execute the additive read-only Manchester Gate-D integration page."""

    st.session_state["_active_ui_route"] = "manchester-gate-d"
    st.sidebar.caption(
        "Gate-D candidate integration only; no review, run, baseline or comparison result."
    )
    manchester_gate_d.render(load_ui_config())

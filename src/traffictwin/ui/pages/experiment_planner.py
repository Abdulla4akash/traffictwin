"""Reproducible experiment-planning page."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.planning import ExperimentPlanSummary
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import activate_page, render_page_header
from traffictwin.ui.services import (
    ExperimentPlannerCatalog,
    ServiceError,
    experiment_plan_yaml_for_ui,
    load_experiment_planner_catalog,
    prepare_experiment_plan_for_ui,
    register_experiment_plan_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render a validated experiment design without launching work."""

    render_page_header(UiPage.EXPERIMENT_PLANNER)
    badge_row(["PLANNED", "REPRODUCIBLE", "NO DIRECT LAUNCH"])
    st.info(
        "Use registered scenario seeds to define a baseline, variations, policy labels, and "
        "common random seeds. This page records a research plan only; it never creates runs or "
        "launches a simulator."
    )

    result = load_experiment_planner_catalog(config.registry_path)
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            with st.expander("Technical detail"):
                st.code(result.detail, language=None)
        return
    catalog = result
    if not catalog.seeds:
        st.warning(
            "No scenario seeds are registered. Create or import a seed before defining an "
            "experiment plan."
        )
        st.button(
            "Open Scenario Builder",
            type="primary",
            on_click=activate_page,
            args=(UiPage.SCENARIO,),
        )
        return

    _render_plan_form(catalog)
    summary = st.session_state.get("latest_experiment_plan")
    if isinstance(summary, ExperimentPlanSummary):
        _render_plan_preview(summary, config)
    _render_existing_plans(catalog)


def _render_plan_form(catalog: ExperimentPlannerCatalog) -> None:
    section_header(
        "Research Design",
        "All conditions reference immutable registered ScenarioSeed records.",
    )
    seed_by_id = {seed.seed_id: seed for seed in catalog.seeds}
    seed_ids = list(seed_by_id)
    default_baseline = "seed-baseline" if "seed-baseline" in seed_by_id else seed_ids[0]
    baseline_seed_id = st.selectbox(
        "Baseline seed",
        seed_ids,
        index=seed_ids.index(default_baseline),
        format_func=lambda seed_id: _seed_label(seed_id, seed_by_id),
        help="The reference condition against which variations are described.",
    )
    variation_options = [seed_id for seed_id in seed_ids if seed_id != baseline_seed_id]
    preferred_variation = (
        ["seed-stressed_demand"]
        if "seed-stressed_demand" in variation_options
        else variation_options[:1]
    )

    with st.form("experiment_plan_form"):
        experiment_id = st.text_input("Experiment ID", value="exp-planned-study")
        research_question = st.text_area(
            "Research question",
            value="How do the selected scenario conditions change deterministic outcomes?",
        )
        hypothesis = st.text_area(
            "Working hypothesis (optional)",
            value="The variation may change task, infrastructure, or journey outcomes.",
            help="This is researcher-supplied planning metadata, not a diagnostic conclusion.",
        )
        variation_seed_ids = st.multiselect(
            "Variation seeds",
            variation_options,
            default=preferred_variation,
            format_func=lambda seed_id: _seed_label(seed_id, seed_by_id),
        )
        selected_algorithms = st.multiselect(
            "Registered policy or algorithm labels",
            catalog.algorithms,
            default=catalog.algorithms[:1],
            help="Labels are metadata. TrafficTwin does not execute these policies here.",
        )
        additional_algorithms = st.text_input(
            "Additional policy labels",
            value="",
            placeholder="synthetic-policy-a, synthetic-policy-b",
            help="Comma-separated labels for planned conditions not yet represented by a run.",
        )
        default_seed = str(seed_by_id[baseline_seed_id].evaluation.random_seed)
        common_random_seeds = st.text_input(
            "Common random seeds",
            value=default_seed,
            help="Comma-separated non-negative integers used across every planned condition.",
        )
        submitted = st.form_submit_button("Validate Plan", type="primary")

    if not submitted:
        return
    plan = prepare_experiment_plan_for_ui(
        experiment_id=experiment_id,
        research_question=research_question,
        hypothesis=hypothesis,
        baseline_seed_id=baseline_seed_id,
        variation_seed_ids=variation_seed_ids,
        algorithms=selected_algorithms,
        additional_algorithm_labels=additional_algorithms,
        common_random_seeds=common_random_seeds,
        registered_seeds=catalog.seeds,
    )
    if isinstance(plan, ServiceError):
        st.session_state["latest_experiment_plan"] = None
        st.error(plan.message)
        if plan.detail:
            st.caption(plan.detail)
        return
    st.session_state["latest_experiment_plan"] = plan
    st.success("The experiment plan is valid. Review the matrix before registering it.")


def _render_plan_preview(summary: ExperimentPlanSummary, config: UiConfig) -> None:
    section_header(
        "Validated Plan Preview",
        "Each row is a planned run slot. No Run records or result values are created.",
    )
    cols = st.columns(4)
    cols[0].metric("Conditions", summary.condition_count)
    cols[1].metric("Policy labels", summary.algorithm_count)
    cols[2].metric("Common seeds", summary.replicate_count)
    cols[3].metric("Planned run slots", summary.planned_run_count)

    for warning in summary.warnings:
        st.warning(warning)
    st.dataframe(
        [cell.as_row() for cell in summary.preview_cells],
        hide_index=True,
        width="stretch",
    )

    section_header("Seed Changes")
    change_rows = [
        {"variation_seed_id": variation_id, **change}
        for variation_id, changes in summary.seed_differences.items()
        for change in changes
    ]
    if change_rows:
        st.dataframe(change_rows, hide_index=True, width="stretch")
    elif summary.experiment.variation_seed_ids:
        st.info("The selected seed snapshots have no non-provenance parameter differences.")
    else:
        st.info("No variation seed is selected, so this plan does not define a comparison.")

    yaml_text = experiment_plan_yaml_for_ui(summary)
    action_cols = st.columns(2)
    action_cols[0].download_button(
        "Download Plan YAML",
        data=yaml_text,
        file_name=f"{summary.experiment.experiment_id}.yaml",
        mime="application/yaml",
        use_container_width=True,
    )
    if action_cols[1].button(
        "Register Planned Experiment",
        type="primary",
        use_container_width=True,
    ):
        registered = register_experiment_plan_for_ui(summary, config.registry_path)
        if isinstance(registered, ServiceError):
            st.error(registered.message)
            if registered.detail:
                st.caption(registered.detail)
        else:
            st.session_state["latest_registered_experiment_id"] = registered.experiment_id
            st.success(
                f"Registered {registered.experiment_id} with status {registered.status.value}. "
                "No runs were created."
            )
    st.button(
        "Open Experiment Manager",
        on_click=activate_page,
        args=(UiPage.EXPERIMENT_MANAGER,),
    )


def _render_existing_plans(catalog: ExperimentPlannerCatalog) -> None:
    section_header("Registered Experiment Plans")
    if not catalog.experiments:
        st.info("No experiment plans are registered yet.")
        return
    st.dataframe(
        [
            {
                "experiment_id": experiment.experiment_id,
                "status": experiment.status.value,
                "baseline_seed_id": experiment.baseline_seed_id,
                "variations": ", ".join(experiment.variation_seed_ids) or "None",
                "policies": ", ".join(experiment.algorithms),
                "common_seeds": ", ".join(map(str, experiment.common_random_seed_set)),
            }
            for experiment in catalog.experiments
        ],
        hide_index=True,
        width="stretch",
    )


def _seed_label(seed_id: str, seed_by_id: Mapping[str, ScenarioSeed]) -> str:
    seed = seed_by_id[seed_id]
    return f"{seed.name} ({seed_id})"

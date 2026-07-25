"""Reproducible experiment-planning page."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.planning import ExperimentPlanSummary
from traffictwin.experiments.protocol import (
    ExperimentProtocol,
    ExperimentProtocolSlot,
    ProtocolBundleMatch,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.guided_runtime import complete_guided_action
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button, render_page_header
from traffictwin.ui.services import (
    ExperimentPlannerCatalog,
    ServiceError,
    build_experiment_protocol_for_ui,
    experiment_plan_yaml_for_ui,
    experiment_protocol_csv_for_ui,
    experiment_protocol_yaml_for_ui,
    load_experiment_planner_catalog,
    load_registered_experiment_protocol_for_ui,
    match_bundle_to_protocol_for_ui,
    prepare_experiment_plan_for_ui,
    register_experiment_plan_for_ui,
)
from traffictwin.ui.state import UiConfig


def render(config: UiConfig) -> None:
    """Render a validated experiment design without launching work."""

    render_page_header(UiPage.EXPERIMENT_PLANNER)
    badge_row(["PLANNED", "REPRODUCIBLE", "NO DIRECT LAUNCH"])
    st.markdown(
        f"{badge_markdown('planned')} **1 Define** → **2 Validate** → **3 Inspect run matrix** → "
        "**4 Register**"
    )
    st.info(
        "Use registered scenario seeds to define a baseline, variations, policy labels, and "
        "common random seeds. This page records a research plan only; it never creates runs or "
        "launches a simulator."
    )

    result = load_experiment_planner_catalog(config.registry_path)
    if isinstance(result, ServiceError):
        st.error(result.message)
        if result.detail:
            with st.expander("Advanced: technical detail"):
                st.code(result.detail, language=None)
        return
    catalog = result
    if not catalog.seeds:
        st.warning(
            "No scenario seeds are registered. Create or import a seed before defining an "
            "experiment plan."
        )
        navigation_button(
            st.button,
            "Open Scenario Builder",
            UiPage.SCENARIO,
            kind="primary",
        )
        return

    _render_plan_form(catalog)
    summary = st.session_state.get("latest_experiment_plan")
    if isinstance(summary, ExperimentPlanSummary):
        _render_plan_preview(summary, config, catalog)
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


def _render_plan_preview(
    summary: ExperimentPlanSummary,
    config: UiConfig,
    catalog: ExperimentPlannerCatalog,
) -> None:
    section_header(
        "Validated Plan Preview",
        "Each row is a planned run slot. No Run records or result values are created.",
    )
    cols = st.columns(4)
    cols[0].metric("Conditions", summary.condition_count)
    cols[1].metric("Policy labels", summary.algorithm_count)
    cols[2].metric("Common seeds", summary.replicate_count)
    cols[3].metric("Planned run slots", summary.planned_run_count)
    st.markdown(
        f"{badge_markdown('reproducible')} **Common-random-seed design** · run matrix = "
        f"{summary.condition_count} conditions × {summary.algorithm_count} policies × "
        f"{summary.replicate_count} common seeds = **{summary.planned_run_count}** run slots. "
        "Registering the plan records these slots; it never creates or launches runs."
    )

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

    protocol_result = build_experiment_protocol_for_ui(summary.experiment, catalog.seeds)
    if isinstance(protocol_result, ServiceError):
        st.error(protocol_result.message)
        if protocol_result.detail:
            st.caption(protocol_result.detail)
        return
    protocol = protocol_result

    section_header(
        "Execution Protocol",
        "A deterministic coordination checklist only. It does not create Run records or "
        "launch work.",
    )
    st.dataframe(
        [_slot_row(slot) for slot in protocol.slots[:200]],
        hide_index=True,
        width="stretch",
    )
    if len(protocol.slots) > 200:
        st.caption(f"Showing 200 of {len(protocol.slots)} run slots. Exports contain every slot.")
    for warning in protocol.warnings:
        st.warning(warning)
    action_cols = st.columns(3)
    action_cols[0].download_button(
        "Download Plan YAML",
        data=experiment_plan_yaml_for_ui(summary),
        file_name=f"{summary.experiment.experiment_id}.yaml",
        mime="application/yaml",
        width="stretch",
        key="download-current-plan-yaml",
    )
    action_cols[1].download_button(
        "Download Protocol YAML",
        data=experiment_protocol_yaml_for_ui(protocol),
        file_name=f"{summary.experiment.experiment_id}-protocol.yaml",
        mime="application/yaml",
        width="stretch",
        key="download-current-protocol-yaml",
    )
    action_cols[2].download_button(
        "Download Run Sheet CSV",
        data=experiment_protocol_csv_for_ui(protocol),
        file_name=f"{summary.experiment.experiment_id}-run-sheet.csv",
        mime="text/csv",
        width="stretch",
        key="download-current-protocol-csv",
    )
    st.caption(
        "Stage 4 · Register. Registration stores the plan and its run matrix only; execution stays "
        "a separate, later step and is never started here."
    )
    if st.button(
        "Register Planned Experiment",
        type="primary",
        width="stretch",
        key="register-current-experiment-plan",
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
            complete_guided_action(
                UiPage.EXPERIMENT_PLANNER,
                "register_experiment_plan",
            )
    navigation_button(
        st.button,
        "Open Experiment Manager",
        UiPage.EXPERIMENT_MANAGER,
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
    section_header(
        "Registered Protocol Export",
        "Rebuild a stable checklist from a registered experiment and its seed snapshots.",
    )
    experiment_ids = [experiment.experiment_id for experiment in catalog.experiments]
    selected_id = st.selectbox(
        "Registered experiment",
        experiment_ids,
        key="registered-protocol-experiment",
    )
    protocol_result = load_registered_experiment_protocol_for_ui(
        selected_id,
        catalog.registry_path,
    )
    if isinstance(protocol_result, ServiceError):
        st.error(protocol_result.message)
        if protocol_result.detail:
            st.caption(protocol_result.detail)
        return
    _render_registered_protocol(protocol_result)


def _render_registered_protocol(protocol: ExperimentProtocol) -> None:
    cols = st.columns(3)
    cols[0].metric("Run slots", len(protocol.slots))
    cols[1].metric("Conditions", 1 + len(protocol.experiment.variation_seed_ids))
    cols[2].metric("Common seeds", len(protocol.experiment.common_random_seed_set))
    download_cols = st.columns(2)
    download_cols[0].download_button(
        "Download Registered Protocol YAML",
        data=experiment_protocol_yaml_for_ui(protocol),
        file_name=f"{protocol.experiment.experiment_id}-protocol.yaml",
        mime="application/yaml",
        width="stretch",
        key=f"download-registered-protocol-yaml-{protocol.experiment.experiment_id}",
    )
    download_cols[1].download_button(
        "Download Registered Run Sheet CSV",
        data=experiment_protocol_csv_for_ui(protocol),
        file_name=f"{protocol.experiment.experiment_id}-run-sheet.csv",
        mime="text/csv",
        width="stretch",
        key=f"download-registered-protocol-csv-{protocol.experiment.experiment_id}",
    )

    with st.expander("Match a completed bundle", expanded=False):
        st.caption(
            "The bundle is validated and compared with the protocol. This does not import it or "
            "change the registry."
        )
        bundle_path = st.text_input(
            "Completed bundle directory or ZIP",
            placeholder="tests/fixtures/bundles/baseline_valid",
            key=f"protocol-bundle-path-{protocol.experiment.experiment_id}",
        )
        if st.button(
            "Check Bundle Match",
            disabled=not bundle_path.strip(),
            key=f"match-protocol-bundle-{protocol.experiment.experiment_id}",
        ):
            match = match_bundle_to_protocol_for_ui(protocol, bundle_path.strip())
            if isinstance(match, ServiceError):
                st.error(match.message)
                if match.detail:
                    st.caption(match.detail)
            else:
                _render_protocol_match(match)


def _render_protocol_match(match: ProtocolBundleMatch) -> None:
    st.markdown(f"**Match status:** `{match.status.value.upper()}`")
    st.markdown(f"**Protocol slot:** `{match.matched_slot_id or 'Unavailable'}`")
    for finding in match.findings:
        st.info(finding)
    if match.mismatches:
        st.dataframe(
            [mismatch.model_dump(mode="json") for mismatch in match.mismatches],
            hide_index=True,
            width="stretch",
        )


def _slot_row(slot: ExperimentProtocolSlot) -> dict[str, object]:
    row = slot.model_dump(mode="json")
    return {
        "slot": row["slot_id"],
        "role": row["role"],
        "seed": row["seed_id"],
        "policy": row["algorithm"],
        "random_seed": row["random_seed"],
        "expected_run_id": row["expected_run_id"],
        "expected_bundle_id": row["expected_bundle_id"],
    }


def _seed_label(seed_id: str, seed_by_id: Mapping[str, ScenarioSeed]) -> str:
    seed = seed_by_id[seed_id]
    return f"{seed.name} ({seed_id})"

"""Home / Project Status page."""

from __future__ import annotations

import streamlit as st

from traffictwin.demo.workspace import workspace_status
from traffictwin.ui.components.badges import badge_row, evidence_state_badge
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import REQUIRED_PROTOTYPE_NOTICE, UiPage
from traffictwin.ui.manchester_operations import (
    build_manchester_deck,
    load_local_manchester_scene,
    visible_layer_ids,
)
from traffictwin.ui.navigation import navigation_button
from traffictwin.ui.services import list_workspace_reports, load_project_status
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import ColumnDisplay, capability_rows, table_column_config


def render(config: UiConfig) -> None:
    """Render the Home page."""

    if st.session_state.get("_v07_navigation_active") is True:
        _render_v07_home(config)
        return

    _render_legacy_home(config)


def _render_v07_home(config: UiConfig) -> None:
    """Render the focused v0.7 research entry point without hiding evidence limits."""

    status = load_project_status(config.registry_path)
    summary = status.registry_summary
    run_count = summary.run_count if summary else 0
    comparison_count = (
        workspace_status(config.workspace_path).comparison_count
        if config.workspace_path is not None
        else 0
    )
    workspace = None if config.workspace_path is None else str(config.workspace_path)
    manchester = load_local_manchester_scene(workspace, "latest_available")
    visible_layers = visible_layer_ids(manchester.scene) if manchester.scene is not None else ()

    st.title("Model a traffic scenario. Run or import it. Compare the evidence.")
    st.caption(
        "A reproducible research workspace for Manchester observations, SUMO/VEC evidence, "
        "and deterministic analysis. Evidence labels describe what is actually loaded."
    )

    with st.container(horizontal=True):
        if st.button(
            "Explore Manchester",
            type="primary",
            icon=":material/map:",
            width="stretch",
            key="home_v07_manchester",
        ):
            st.switch_page("app_pages/manchester.py")
        navigation_button(
            st.button,
            "Create scenario",
            UiPage.SCENARIO,
            key="home_v07_scenario",
            width="stretch",
        )
        navigation_button(
            st.button,
            "Open latest run",
            UiPage.RUN_OVERVIEW,
            key="home_v07_latest_run",
            width="stretch",
        )

    with st.container(horizontal=True):
        with st.container(border=True):
            st.caption("Manchester evidence")
            evidence_state_badge(manchester.status)
        st.metric("Visible local layers", len(visible_layers), border=True)
        st.metric("Registered runs", run_count, border=True)
        st.metric("Comparisons", comparison_count, border=True)

    st.subheader("Current evidence context")
    if manchester.scene is not None and visible_layers:
        st.pydeck_chart(
            build_manchester_deck(manchester.scene, visible_layers),
            width="stretch",
            height=430,
            key="home_v07_manchester_map",
        )
        st.caption(
            f"Latest accepted local scene · {len(visible_layers)} source-separated layer(s) · "
            f"state: {manchester.scene.status.replace('_', ' ')} · basemap disabled"
        )
    else:
        with st.container(border=True):
            st.markdown("**No accepted latest-available Manchester scene is loaded.**")
            st.write(manchester.message)
            st.caption(
                "You can still build synthetic scenarios, import completed runs, inspect "
                "Randy/TOS evidence, and use the guided workflow. Missing observations are not "
                "filled with synthetic or stale values."
            )

    st.subheader("Next reproducible actions")
    with st.container(horizontal=True):
        with st.container(border=True):
            st.markdown("**Inspect or acquire evidence**")
            st.caption(
                "Use Manchester Operations for local source-separated scenes and the explicit "
                "bounded live-bus action."
            )
        with st.container(border=True):
            st.markdown("**Run or import**")
            st.caption(
                "Use the controlled SUMO/VEC pages or import completed generic, SUMO, and TOS "
                "artifacts."
            )
        with st.container(border=True):
            st.markdown("**Compare and explain**")
            st.caption(
                "Compute deterministic metrics, comparisons, diagnostics, provenance, and "
                "research exports."
            )

    reports = list_workspace_reports(config.workspace_path)[:5]
    if status.latest_runs or reports:
        st.subheader("Recent research activity")
        if status.latest_runs:
            st.dataframe(
                [
                    {
                        "Run": run.run_id,
                        "Algorithm": run.algorithm,
                        "Seed": run.random_seed,
                        "Status": run.status.value,
                    }
                    for run in status.latest_runs[:5]
                ],
                hide_index=True,
                width="stretch",
            )
        if reports:
            st.caption(
                f"{len(reports)} recent report artifact(s) are available from the configured "
                "workspace."
            )

    st.warning(
        "Manchester sources remain evidence-specific: DfT is historical survey evidence, "
        "WebTRIS is historical/latest-available strategic-road evidence, TfGM signals are "
        "infrastructure references, BODS positions are buses, and National Highways supplies "
        "strategic-road operational events—not continuous city-road flow or congestion.",
        icon=":material/info:",
    )
    st.caption(REQUIRED_PROTOTYPE_NOTICE)


def _render_legacy_home(config: UiConfig) -> None:
    """Preserve the complete v0.6 home while the v0.7 router remains opt-in."""

    status = load_project_status(config.registry_path)
    st.title("TrafficTwin")
    st.caption("What-if experimentation and decision-support platform")
    st.info(REQUIRED_PROTOTYPE_NOTICE)
    badge_row(["SYNTHETIC", "IMPORTED", "HISTORICAL REPLAY"])

    section_header("Research Workflow")
    action_cols = st.columns(2)
    navigation_button(
        action_cols[0].button,
        "Start Guided Demo",
        UiPage.GUIDED_DEMO,
        kind="primary",
        width="stretch",
    )
    navigation_button(
        action_cols[1].button,
        "Plan an Experiment",
        UiPage.EXPERIMENT_PLANNER,
        key="home_plan_experiment",
        width="stretch",
    )
    navigation_button(
        st.button,
        "Open Imported TOS Results",
        UiPage.TOS_RESULTS,
        width="stretch",
    )

    with st.container(border=True):
        st.markdown(
            f"**Implementation phase:** {status.current_phase} · "
            f"**Design version:** {status.canonical_design_version}"
        )
        st.markdown(
            f"**Registry:** {'Present' if status.registry_exists else 'Missing'} · "
            f"**Adapter:** `{status.capability_manifest.adapter}`"
        )

    summary = status.registry_summary
    seed_count = summary.seed_count if summary else 0
    experiment_count = summary.experiment_count if summary else 0
    run_count = summary.run_count if summary else 0
    metric_count = summary.metric_collection_count if summary else 0
    cols = st.columns(4)
    cols[0].metric("Seeds", seed_count)
    cols[1].metric("Experiments", experiment_count)
    cols[2].metric("Runs", run_count)
    cols[3].metric("Metric collections", metric_count)

    if config.workspace_path is not None:
        section_header("Standalone Demo")
        demo_status = workspace_status(config.workspace_path)
        st.info(
            "Standalone mode uses repository-contained synthetic fixtures only. "
            "It does not use Randy, SUMO, or live Manchester data."
        )
        st.markdown(
            f"**Workspace:** {'Ready' if demo_status.valid_workspace else 'Missing'} · "
            f"**Diagnostics:** {demo_status.diagnostics_status}"
        )
        demo_cols = st.columns(2)
        demo_cols[0].metric("Synthetic scenarios", demo_status.scenario_count)
        demo_cols[1].metric("Imported runs", demo_status.imported_run_count)
        st.caption(f"Workspace: {demo_status.path}")
        report_count = len(list_workspace_reports(config.workspace_path))
        export_dir = config.workspace_path / "exports"
        provenance_count = (
            len(list(export_dir.glob("*provenance*.json"))) if export_dir.exists() else 0
        )
        comparison_count = demo_status.comparison_count
        cols = st.columns(3)
        cols[0].metric("Available reports", report_count)
        cols[1].metric("Comparisons", comparison_count)
        cols[2].metric("Provenance exports", provenance_count)

        section_header("Quick Actions")
        first_actions = st.columns(2)
        navigation_button(
            first_actions[0].button,
            "Build a Scenario",
            UiPage.SCENARIO,
            width="stretch",
        )
        navigation_button(
            first_actions[1].button,
            "Plan an Experiment",
            UiPage.EXPERIMENT_PLANNER,
            key="home_quick_plan_experiment",
            width="stretch",
        )
        second_actions = st.columns(2)
        navigation_button(
            second_actions[0].button,
            "Open Reports",
            UiPage.REPORTS,
            width="stretch",
        )
        navigation_button(
            second_actions[1].button,
            "Trace Provenance",
            UiPage.PROVENANCE,
            width="stretch",
        )

        section_header("Recent Workspace Artifacts")
        reports = list_workspace_reports(config.workspace_path)[:5]
        if reports:
            report_rows = [
                {
                    "report": report.name,
                    "type": report.report_type,
                    "format": report.format_label,
                    "scenario": report.scenario_hint,
                }
                for report in reports
            ]
            st.dataframe(
                report_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(report_rows),
            )
        else:
            st.info("No report artifacts found in the active workspace.")

    section_header("Latest Imported Runs")
    if status.latest_runs:
        run_rows = [
            {
                "run_id": run.run_id,
                "algorithm": run.algorithm,
                "status": run.status.value,
                "experiment_id": run.experiment_id,
                "seed_id": run.seed_id,
                "random_seed": run.random_seed,
            }
            for run in status.latest_runs
        ]
        st.dataframe(
            run_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(
                run_rows,
                overrides={"run_id": ColumnDisplay(key="run_id", label="Run", hidden=False)},
            ),
        )
        with st.expander("Advanced: run identifiers"):
            st.dataframe(
                run_rows,
                hide_index=True,
                width="stretch",
                column_config=table_column_config(run_rows, hide_machine_ids=False),
            )
    else:
        st.info("No registered runs yet. Import a synthetic or historical bundle first.")

    section_header("Current Limitations")
    st.markdown(
        "- Direct simulator launch is unavailable for the default generic CSV adapter.\n"
        "- Private Manchester acquisition is bounded to explicit BODS bus-position snapshots "
        "and National Highways strategic-road closures/incidents, imposed temporary speed "
        "restrictions, and VMS status. Continuous city-road flow, measured speed/congestion, "
        "traffic-signal phases, and background polling remain unavailable; WebTRIS is "
        "historical/latest-available, not near-live.\n"
        "- Diagnostic hypotheses R0-R3 are deterministic candidates, not proven causes.\n"
        "- TOS Data evaluation summaries and instrumented arrays can be inspected offline; "
        "exact VEC foreground evaluation is available only through request-specific "
        "preflight in the VEC workbench. SUMO launch and promotion of source-specific "
        "RSU pressure to canonical infrastructure metrics remain unavailable."
    )

    with st.expander("Advanced: capability manifest"):
        manifest_rows = capability_rows(status.capability_manifest)
        st.dataframe(
            manifest_rows,
            hide_index=True,
            width="stretch",
            column_config=table_column_config(manifest_rows),
        )

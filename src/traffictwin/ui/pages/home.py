"""Home / Project Status page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from traffictwin.demo.workspace import workspace_status
from traffictwin.integration.manchester.boundary_reference import ManchesterBoundaryError
from traffictwin.ui.components.badges import badge_row, evidence_state_badge
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.demo_workspace_service import (
    _DEMO_WORKSPACE_FLASH_KEY,
    DEFAULT_DEMO_WORKSPACE_PATH,
    ensure_demo_workspace,
    resolve_effective_demo_paths,
)
from traffictwin.ui.labels import REQUIRED_PROTOTYPE_NOTICE, UiPage
from traffictwin.ui.manchester_context import load_manchester_context
from traffictwin.ui.manchester_operations import (
    build_manchester_deck,
    load_local_manchester_scene,
    visible_layer_ids,
)
from traffictwin.ui.navigation import activate_page, navigation_button
from traffictwin.ui.services import list_workspace_reports, load_project_status
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import ColumnDisplay, capability_rows, table_column_config

# Stable session-state intent for the built-in E2 mode in Resource Strategy Explorer.
E2_RESOURCE_STRATEGY_INTENT_KEY = "resource_strategy_intent"
E2_RESOURCE_STRATEGY_INTENT_VALUE = "e2"

# Stable session-state intent for the built-in E3 mode in Resource Strategy Explorer.
E3_RESOURCE_STRATEGY_INTENT_KEY = "resource_strategy_intent"
E3_RESOURCE_STRATEGY_INTENT_VALUE = "e3"


def _on_inspect_e2_research() -> None:
    """Record E2 intent then navigate via the proven callback router."""

    st.session_state[E2_RESOURCE_STRATEGY_INTENT_KEY] = E2_RESOURCE_STRATEGY_INTENT_VALUE
    activate_page(UiPage.RESOURCE_STRATEGY_EXPLORER)


def _on_inspect_e3_research() -> None:
    """Record E3 intent then navigate via the proven callback router."""

    st.session_state[E3_RESOURCE_STRATEGY_INTENT_KEY] = E3_RESOURCE_STRATEGY_INTENT_VALUE
    activate_page(UiPage.RESOURCE_STRATEGY_EXPLORER)


def render(config: UiConfig) -> None:
    """Render the Home page."""

    if st.session_state.get("_v07_navigation_active") is True:
        _render_v07_home(config)
        return

    _render_legacy_home(config)


def _render_v07_home(config: UiConfig) -> None:
    """Render the focused v0.7 research entry point without hiding evidence limits."""

    effective_workspace, effective_registry_path = resolve_effective_demo_paths(config)
    # One-shot flash from the immediate rerun after in-browser workspace creation
    flash = st.session_state.pop(_DEMO_WORKSPACE_FLASH_KEY, None)
    if isinstance(flash, dict) and flash.get("message"):
        if flash.get("status") == "created":
            st.success(str(flash["message"]))
            st.info(
                "Follow Guided Demo to continue. Manchester scenes remain unavailable in a "
                "demo workspace — they require a separately activated real workspace with "
                "accepted Manchester artifacts."
            )
        elif flash.get("status") == "already_exists":
            st.info(str(flash["message"]))
        else:
            st.info(str(flash["message"]))
    status = load_project_status(effective_registry_path)
    summary = status.registry_summary
    run_count = summary.run_count if summary else 0
    comparison_count = _comparison_count_for(effective_workspace)
    workspace = str(effective_workspace) if effective_workspace is not None else None
    manchester = load_local_manchester_scene(workspace, "latest_available")
    visible_layers = visible_layer_ids(manchester.scene) if manchester.scene is not None else ()

    st.title("Model a traffic scenario. Run or import it. Compare the evidence.")
    st.caption(
        "A reproducible research workspace for Manchester observations, SUMO/VEC evidence, "
        "and deterministic analysis. Evidence labels describe what is actually loaded."
    )

    with st.container(horizontal=True):
        navigation_button(
            st.button,
            "Create what-if comparison",
            UiPage.WHATIF_STUDIO,
            key="home_v07_whatif",
            width="stretch",
            kind="primary",
        )
        if st.button(
            "Explore Manchester",
            icon=":material/map:",
            width="stretch",
            key="home_v07_manchester",
        ):
            st.switch_page("app_pages/manchester.py")
        navigation_button(
            st.button,
            "Start Guided Demo",
            UiPage.GUIDED_DEMO,
            key="home_v07_guided_demo",
            width="stretch",
        )
        navigation_button(
            st.button,
            "Open latest run",
            UiPage.RUN_OVERVIEW,
            key="home_v07_latest_run",
            width="stretch",
        )
    st.caption(
        "What-If Studio generates a deterministic synthetic baseline/variation "
        "pair locally — SYNTHETIC / DETERMINISTIC / LOCAL. It is not Manchester "
        "observation, not a live traffic forecast, and does not run SUMO, VEC, a "
        "provider feed, or an admitted research campaign."
    )
    with st.container(horizontal=True):
        navigation_button(
            st.button,
            "Create scenario",
            UiPage.SCENARIO,
            key="home_v07_scenario",
            width="stretch",
        )
        st.caption(
            "Scenario Builder remains available below for direct synthetic preset "
            "authoring without the pair workflow."
        )

    with st.container(horizontal=True):
        with st.container(border=True):
            st.caption("Manchester evidence")
            evidence_state_badge(manchester.status)
        st.metric("Visible local layers", len(visible_layers), border=True)
        st.metric("Registered runs", run_count, border=True)
        st.metric("Comparisons", comparison_count, border=True)

    with st.container(border=True):
        st.markdown("**Inspect real E2 research — admitted VEC study**")
        st.caption(
            "Bounded E2b/E2c/E2d resource-strategy evidence (Manchester incident hour "
            "2024-03-15 20:00–21:00, evaluator seed 0, 1× service, zero backhaul, four "
            "matched fleet draws). This is admitted VEC research, not Manchester "
            "observation, not a live forecast, and not Kubernetes deployment."
        )
        st.button(
            "Inspect real E2 research",
            key="home_inspect_e2_research",
            width="stretch",
            type="primary",
            on_click=_on_inspect_e2_research,
        )
        st.caption(
            "Opens Resource Strategy Explorer and preselects the built-in E2 mode via "
            "a stable session-state intent. Synthetic demonstration remains available "
            "separately in the explorer."
        )

    with st.container(border=True):
        st.markdown("**Inspect E3 Dynamic Resource V2 — dormant staged design (no results)**")
        st.caption(
            "Bounded E3a/E3b/E3c staged design (14 arms, 56 configs, fleet_draw N=4, "
            "evaluator_seed 0, 10 RSUs, 3600 ticks dormant). No E3 research results exist today; "
            "typed semantics and structure only. Admission not yet authorized."
        )
        st.button(
            "Inspect E3 Dynamic Resource V2",
            key="home_inspect_e3_research",
            width="stretch",
            type="primary",
            on_click=_on_inspect_e3_research,
        )
        st.caption(
            "Opens Resource Strategy Explorer and preselects the built-in E3 mode via "
            "a stable session-state intent. This is dormant staged design, not Manchester "
            "observation, not a live forecast, and not deployment. Today there are no results; "
            "every numeric surface renders NOT_EXECUTED / NO_E3_RESEARCH_RESULTS_AVAILABLE."
        )

    has_workspace, workspace_ready, _ws_status = _workspace_presence(effective_workspace)

    if not has_workspace or not workspace_ready:
        _render_demo_workspace_empty_state()
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
        _render_static_manchester_context(has_workspace, workspace_ready)
        with st.container(border=True):
            if not has_workspace or not workspace_ready:
                st.markdown("**No demo workspace is configured — create one to begin.**")
                st.caption(
                    "The demo workspace is synthetic and local. It contains no Manchester, "
                    "Randy, or live data. A fresh demo lets you run the entire import-first "
                    "workflow without any provider credential."
                )
            else:
                st.markdown("**No accepted latest-available Manchester scene is loaded.**")
                st.write(manchester.message)
                st.caption(
                    "You can still build synthetic scenarios, import completed runs, inspect "
                    "Randy/TOS evidence, and use the guided workflow. Missing observations are "
                    "not filled with synthetic or stale values."
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

    reports = list_workspace_reports(effective_workspace)[:5]
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


def _resolve_effective_demo_paths(config: UiConfig) -> tuple[Path | None, Path]:
    """Compatibility shim — delegates to the central resolver."""

    return resolve_effective_demo_paths(config)


def _comparison_count_for(workspace: Path | None) -> int:
    if workspace is None:
        return 0
    try:
        return workspace_status(workspace).comparison_count
    except (OSError, ValueError):
        return 0


def _workspace_presence(
    workspace: Path | None,
) -> tuple[bool, bool, object | None]:
    """Return (has_workspace, workspace_ready, status)."""

    if workspace is None:
        return False, False, None
    try:
        status = workspace_status(workspace)
    except (OSError, ValueError):
        return True, False, None
    return True, status.valid_workspace, status


def _render_demo_workspace_empty_state() -> None:
    """Offer a one-click synthetic workspace beside the honest empty state."""

    with st.container(border=True):
        st.markdown("**Create a demo workspace**")
        st.caption(
            "No workspace is configured for this app process. Create a local synthetic demo "
            "workspace to explore the end-to-end workflow without Manchester, Randy, or live "
            "provider data. All generated records carry `synthetic: true` and a deterministic "
            "created instant."
        )
        with st.expander("Advanced: workspace location", expanded=False):
            st.caption(
                f"Default directory: `{DEFAULT_DEMO_WORKSPACE_PATH}` (relative to the process "
                "working directory). Change it only to a safe, empty/non-existent directory; "
                "existing files outside the marker are not overwritten."
            )
        path_input = st.text_input(
            "Demo workspace path",
            value=str(DEFAULT_DEMO_WORKSPACE_PATH),
            key="home_demo_workspace_path",
            help="Must not be /, $HOME, or the repository root, and must be empty or new.",
        )
        create_col, _hint_col = st.columns([1, 2])
        if create_col.button(
            "Create demo workspace",
            type="primary",
            width="stretch",
            key="home_create_demo_workspace",
        ):
            result = ensure_demo_workspace(path_input)
            if result.status in {"created", "already_exists"}:
                st.session_state["active_registry_path"] = str(result.path / "registry.sqlite")
                st.session_state["_active_demo_workspace_path"] = str(result.path)
                st.session_state[_DEMO_WORKSPACE_FLASH_KEY] = {
                    "status": result.status,
                    "message": result.message,
                }
                st.rerun()
            else:
                st.error(result.message)
                if result.reason == "non_empty_without_force":
                    st.caption(
                        "The target directory is not empty and has no TrafficTwin marker. "
                        "Choose an empty/new directory or remove/relocate the existing content."
                    )


def _render_static_manchester_context(
    has_workspace: bool,
    workspace_ready: bool,
) -> None:
    """Render the offline Greater Manchester boundary when no scene is available."""

    try:
        context = load_manchester_context()
    except ManchesterBoundaryError:
        st.caption(
            "Static geographic context unavailable — the offline boundary asset "
            "could not be loaded. No live or observed traffic scene is displayed."
        )
        return

    st.markdown("**Manchester study-area context — static geographic reference**")
    st.caption("Static geographic context — no live or observed traffic scene is loaded.")
    st.pydeck_chart(
        context.deck,
        width="stretch",
        height=380,
        key="home_manchester_context_map",
    )
    # Use the canonical attribution so a change in boundary_reference propagates.
    os_attr, ons_attr = context.attribution
    greater_ref = context.greater_manchester.reference
    manchester_ref = context.manchester.reference
    st.caption(
        f"Offline reference — {greater_ref.official_name} Combined Authority "
        f"({greater_ref.official_code}) and {manchester_ref.official_name} Local "
        f"Authority ({manchester_ref.official_code}), {greater_ref.reference_date} "
        f"{greater_ref.source_generalisation}. Source: {greater_ref.source_owner} "
        f"licensed under the Open Government Licence v.3.0. {os_attr} {ons_attr} "
        f"This outline is geographic context only; it is not a traffic scene, "
        f"provider telemetry, or a calibrated network."
    )
    if has_workspace and workspace_ready:
        st.caption(
            "Synthetic demo workspace is active, but the boundary above remains "
            "geographic context only — it does not represent Manchester observed traffic "
            "or a calibrated simulation."
        )
    st.caption(
        "No accepted Manchester traffic scene is currently loaded. Use Explore "
        "Manchester or Start Guided Demo for the next supported step."
    )


def _render_legacy_home(config: UiConfig) -> None:
    """Preserve the complete v0.6 home while the v0.7 router remains opt-in."""

    status = load_project_status(config.registry_path)
    st.title("TrafficTwin")
    st.caption("What-if experimentation and decision-support platform")
    st.info(REQUIRED_PROTOTYPE_NOTICE)
    badge_row(["SYNTHETIC", "IMPORTED", "HISTORICAL REPLAY"])

    section_header("Research workflow")
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
    legacy_second = st.columns(2)
    navigation_button(
        legacy_second[0].button,
        "Create what-if comparison",
        UiPage.WHATIF_STUDIO,
        key="home_legacy_whatif",
        width="stretch",
    )
    navigation_button(
        legacy_second[1].button,
        "Open Comparison",
        UiPage.COMPARE,
        key="home_legacy_compare",
        width="stretch",
    )
    st.caption(
        "What-If Studio generates a deterministic synthetic baseline/variation "
        "pair locally — SYNTHETIC / DETERMINISTIC / LOCAL. It is not Manchester "
        "observation, not a live traffic forecast, and does not run SUMO, VEC, a "
        "provider feed, or an admitted research campaign."
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
        section_header("Standalone demo")
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

        section_header("Quick actions")
        first_actions = st.columns(2)
        navigation_button(
            first_actions[0].button,
            "Build a Scenario",
            UiPage.SCENARIO,
            width="stretch",
        )
        # Routes to the same planner as the Research Workflow row above, and is
        # kept because this Quick Actions block is the retained v0.6 home
        # surface. The label differs deliberately: two buttons sharing one label
        # are indistinguishable to anyone traversing by keyboard or screen
        # reader, even though a sighted user tells them apart by position.
        navigation_button(
            first_actions[1].button,
            "Plan an Experiment from Quick Actions",
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
        with st.container(border=True):
            st.markdown("**Inspect real E2 research — admitted VEC study**")
            st.caption(
                "Bounded E2b/E2c/E2d resource-strategy evidence (Manchester incident hour "
                "2024-03-15 20:00–21:00, evaluator seed 0, 1× service, zero backhaul, four "
                "matched fleet draws). This is admitted VEC research, not Manchester "
                "observation, not a live forecast, and not Kubernetes deployment."
            )
            st.button(
                "Inspect real E2 research",
                key="home_legacy_inspect_e2_research",
                width="stretch",
                type="primary",
                on_click=_on_inspect_e2_research,
            )
            st.caption(
                "Opens Resource Strategy Explorer and preselects the built-in E2 mode via "
                "a stable session-state intent."
            )
        with st.container(border=True):
            st.markdown("**Inspect E3 Dynamic Resource V2 — dormant (no results)**")
            st.caption(
                "Bounded E3a/E3b/E3c dormant staged design (14 arms, 56 configs). "
                "No results exist today; semantics and structure only."
            )
            st.button(
                "Inspect E3 Dynamic Resource V2",
                key="home_legacy_inspect_e3_research",
                width="stretch",
                type="primary",
                on_click=_on_inspect_e3_research,
            )
            st.caption(
                "Opens Resource Strategy Explorer with the built-in E3 mode preselected. "
                "Dormant design only, not Manchester observation, not deployment. "
                "No results today."
            )

        section_header("Recent workspace artifacts")
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

    section_header("Latest imported runs")
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

    section_header("Current limitations")
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

"""Home / Project Status page."""

from __future__ import annotations

import streamlit as st

from traffictwin.demo.workspace import workspace_status
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.labels import REQUIRED_PROTOTYPE_NOTICE, UiPage
from traffictwin.ui.navigation import activate_page
from traffictwin.ui.services import list_workspace_reports, load_project_status
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import capability_rows


def render(config: UiConfig) -> None:
    """Render the Home page."""

    status = load_project_status(config.registry_path)
    st.title("TrafficTwin")
    st.caption("What-if experimentation and decision-support platform")
    st.info(REQUIRED_PROTOTYPE_NOTICE)
    badge_row(["SYNTHETIC", "IMPORTED", "HISTORICAL REPLAY"])

    section_header("Research Workflow")
    action_cols = st.columns(2)
    action_cols[0].button(
        "Start Guided Demo",
        type="primary",
        on_click=activate_page,
        args=(UiPage.GUIDED_DEMO,),
        use_container_width=True,
    )
    action_cols[1].button(
        "Plan an Experiment",
        key="home_plan_experiment",
        on_click=activate_page,
        args=(UiPage.EXPERIMENT_PLANNER,),
        use_container_width=True,
    )
    st.button(
        "Open Imported TOS Results",
        on_click=activate_page,
        args=(UiPage.TOS_RESULTS,),
        use_container_width=True,
    )

    cols = st.columns(4)
    cols[0].metric("Implementation phase", status.current_phase)
    cols[1].metric("Design version", status.canonical_design_version)
    cols[2].metric("Registry", "Present" if status.registry_exists else "Missing")
    cols[3].metric("Adapter", status.capability_manifest.adapter)

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
        demo_cols = st.columns(4)
        demo_cols[0].metric("Workspace", "Ready" if demo_status.valid_workspace else "Missing")
        demo_cols[1].metric("Synthetic scenarios", demo_status.scenario_count)
        demo_cols[2].metric("Imported runs", demo_status.imported_run_count)
        demo_cols[3].metric("Diagnostics", demo_status.diagnostics_status)
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
        first_actions[0].button(
            "Build a Scenario",
            on_click=activate_page,
            args=(UiPage.SCENARIO,),
            use_container_width=True,
        )
        first_actions[1].button(
            "Plan an Experiment",
            key="home_quick_plan_experiment",
            on_click=activate_page,
            args=(UiPage.EXPERIMENT_PLANNER,),
            use_container_width=True,
        )
        second_actions = st.columns(2)
        second_actions[0].button(
            "Open Reports",
            on_click=activate_page,
            args=(UiPage.REPORTS,),
            use_container_width=True,
        )
        second_actions[1].button(
            "Trace Provenance",
            on_click=activate_page,
            args=(UiPage.PROVENANCE,),
            use_container_width=True,
        )

        section_header("Recent Workspace Artifacts")
        reports = list_workspace_reports(config.workspace_path)[:5]
        if reports:
            st.table(
                [
                    {
                        "report": report.name,
                        "type": report.report_type,
                        "format": report.format_label,
                        "scenario": report.scenario_hint,
                    }
                    for report in reports
                ],
            )
        else:
            st.info("No report artifacts found in the active workspace.")

    section_header("Capability Manifest")
    st.table(capability_rows(status.capability_manifest))

    section_header("Latest Imported Runs")
    if status.latest_runs:
        st.table(
            [
                {
                    "run_id": run.run_id,
                    "experiment_id": run.experiment_id,
                    "seed_id": run.seed_id,
                    "algorithm": run.algorithm,
                    "random_seed": run.random_seed,
                    "status": run.status.value,
                }
                for run in status.latest_runs
            ],
        )
    else:
        st.info("No registered runs yet. Import a synthetic or historical bundle first.")

    section_header("Current Limitations")
    st.write(
        [
            "Direct simulator launch is unavailable for the default generic CSV adapter.",
            "No live, near-live, or true-live Manchester data is connected.",
            "Diagnostic hypotheses R0-R3 are deterministic candidates, not proven causes.",
            (
                "TOS Data evaluation summaries and instrumented arrays can be inspected offline; "
                "direct Randy/VEC launch, SUMO conversion, and promotion of source-specific RSU "
                "pressure to canonical infrastructure metrics remain unavailable."
            ),
        ]
    )

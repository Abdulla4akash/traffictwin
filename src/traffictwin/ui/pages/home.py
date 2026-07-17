"""Home / Project Status page."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import REQUIRED_PROTOTYPE_NOTICE
from traffictwin.ui.services import load_project_status
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tables import capability_rows


def render(config: UiConfig) -> None:
    """Render the Home page."""

    status = load_project_status(config.registry_path)
    st.title("TrafficTwin")
    st.caption("What-if experimentation and decision-support platform")
    st.info(REQUIRED_PROTOTYPE_NOTICE)
    badge_row(["SYNTHETIC", "IMPORTED", "HISTORICAL REPLAY"])

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

    st.subheader("Capability Manifest")
    st.dataframe(capability_rows(status.capability_manifest), hide_index=True, width="stretch")

    st.subheader("Latest Imported Runs")
    if status.latest_runs:
        st.dataframe(
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
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("No registered runs yet. Import a synthetic or historical bundle first.")

    st.subheader("Current Limitations")
    st.write(
        [
            "Direct simulator launch is unavailable for the default generic CSV adapter.",
            "No live, near-live, or true-live Manchester data is connected.",
            "Diagnostic hypotheses R0-R3 are deterministic candidates, not proven causes.",
            "SUMO and Randy/VEC adapters remain blocked until real schemas exist.",
        ]
    )

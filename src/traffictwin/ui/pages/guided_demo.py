"""Guided demonstration of the existing deterministic workflow."""

from __future__ import annotations

import streamlit as st

from traffictwin.demo.workspace import workspace_status
from traffictwin.ui.components.badges import badge_row, status_badge
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.guided import DemoTrack, GuidedDemoProgress, steps_for_track
from traffictwin.ui.guided_runtime import (
    begin_guided_workflow,
    load_guided_progress,
    resume_guided_workflow,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package


def render(config: UiConfig) -> None:
    """Render the guided research workflow."""

    render_page_header(UiPage.GUIDED_DEMO)
    st.info(
        "TrafficTwin analyses experiment artifacts. The simulation environment produces records; "
        "TrafficTwin validates, measures, compares, diagnoses, and traces them; the researcher "
        "interprets the evidence and its limits."
    )

    selected = st.radio(
        "Evidence track",
        [track.value for track in DemoTrack],
        horizontal=True,
        key="guided_demo_track",
    )
    track = DemoTrack(selected)
    _render_track_status(config, track)

    steps = steps_for_track(track)
    progress = load_guided_progress()
    matching_progress = progress if progress is not None and progress.track is track else None
    if matching_progress is not None and matching_progress.finished:
        _render_completion(matching_progress)
    current_index = matching_progress.step_index if matching_progress is not None else 0
    step = steps[current_index]
    st.progress((current_index + 1) / len(steps))
    section_header(
        f"Stage {current_index + 1} of {len(steps)}: {step.title}",
        f"Research pipeline stage: {step.key}",
    )

    input_col, operation_col, output_col = st.columns(3)
    with input_col:
        st.markdown("**Evidence input**")
        st.write(step.input_label)
    with operation_col:
        st.markdown("**Deterministic operation**")
        st.write(step.operation_label)
    with output_col:
        st.markdown("**Evidence output**")
        st.write(step.output_label)
    st.warning(step.boundary)
    st.markdown("**Your task**")
    st.write(step.instruction)

    if matching_progress is not None and matching_progress.active:
        controls = st.columns(3)
        if controls[0].button(
            "Resume current task",
            type="primary",
            width="stretch",
            key="guided_resume_workflow",
        ):
            resume_guided_workflow(matching_progress)
        if controls[1].button(
            "Restart this track",
            width="stretch",
            key="guided_restart_workflow",
        ):
            begin_guided_workflow(track)
        if controls[2].button(
            "Exit guided mode",
            width="stretch",
            key="guided_exit_workflow",
        ):
            st.session_state["guided_demo_progress"] = matching_progress.exit().model_dump(
                mode="json"
            )
            st.rerun()
    elif matching_progress is not None and not matching_progress.finished:
        controls = st.columns(2)
        if controls[0].button(
            "Resume guided workflow",
            type="primary",
            width="stretch",
            key="guided_resume_paused_workflow",
        ):
            resume_guided_workflow(matching_progress)
        if controls[1].button(
            "Restart this track",
            width="stretch",
            key="guided_restart_paused_workflow",
        ):
            begin_guided_workflow(track)
    else:
        label = "Start again" if matching_progress is not None else "Start guided workflow"
        if st.button(
            label,
            type="primary",
            width="stretch",
            key="guided_start_workflow",
        ):
            begin_guided_workflow(track)

    with st.expander(f"Full {len(steps)}-stage journey", expanded=False):
        completed = (
            set(matching_progress.completed_step_keys) if matching_progress is not None else set()
        )
        skipped = (
            set(matching_progress.skipped_step_keys) if matching_progress is not None else set()
        )
        for index, candidate in enumerate(steps, start=1):
            outcome = (
                "completed"
                if candidate.key in completed
                else "skipped"
                if candidate.key in skipped
                else "upcoming"
            )
            st.markdown(
                f"**{index}. {candidate.title}** — {candidate.target_page.value} · {outcome}"
            )
            st.caption(candidate.instruction)


def _render_completion(progress: GuidedDemoProgress) -> None:
    """Render an honest completion summary without claiming skipped stages complete."""

    steps = steps_for_track(progress.track)
    completed = len(progress.completed_step_keys)
    skipped = len(progress.skipped_step_keys)
    st.success(
        f"Guided workflow finished: {completed} completed and {skipped} explicitly skipped "
        f"out of {len(steps)} stages."
    )
    if skipped:
        st.warning("Skipped stages remain skipped; the guide does not count them as evidence.")


def _render_track_status(config: UiConfig, track: DemoTrack) -> None:
    section_header("Active evidence context")
    if track is DemoTrack.STANDALONE:
        badge_row(["SYNTHETIC", "OFFLINE", "DETERMINISTIC"])
        if config.workspace_path is None:
            st.warning("No standalone workspace is configured for this app process.")
            return
        status = workspace_status(config.workspace_path)
        workspace_label = "Ready" if status.valid_workspace else "Unavailable"
        st.markdown(
            f"**Workspace:** {workspace_label} | **Scenarios:** {status.scenario_count} | "
            f"**Imported runs:** {status.imported_run_count} | "
            f"**Comparisons:** {status.comparison_count}"
        )
        if status.messages:
            st.caption("; ".join(status.messages))
        return

    badge_row(["IMPORTED SIMULATION", "HISTORICAL", "READ-ONLY"])
    package = active_tos_package(config)
    if package is None:
        return
    inventory = package.report.inventory
    status_badge(package.report.status.value)
    st.markdown(
        f"**Evaluation rows:** {inventory.evaluation_rows} | "
        f"**Per-step arrays:** {inventory.perstep_files} | "
        f"**Per-task arrays:** {inventory.pertask_files} | "
        f"**Mobility traces:** {inventory.trace_files}"
    )
    st.markdown(
        f"**Training histories:** {inventory.training_csv_files} | "
        f"**Training summaries:** {inventory.training_summary_files} | "
        f"**Instrumented runs:** {len(package.instrumented_runs)}"
    )
    if package.report.package_fingerprint:
        st.caption(f"Package fingerprint: {package.report.package_fingerprint}")

"""Guided demonstration of the existing deterministic workflow."""

from __future__ import annotations

import streamlit as st

from traffictwin.demo.workspace import workspace_status
from traffictwin.ui.components.badges import badge_row, status_badge
from traffictwin.ui.components.cards import section_header
from traffictwin.ui.guided import DemoTrack, bounded_step, steps_for_track
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import navigation_button, render_page_header
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package


def _reset_stage() -> None:
    st.session_state["guided_demo_step"] = 0


def _move_stage(delta: int, step_count: int) -> None:
    current = int(st.session_state.get("guided_demo_step", 0))
    st.session_state["guided_demo_step"] = bounded_step(current + delta, step_count)


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
        on_change=_reset_stage,
    )
    track = DemoTrack(selected)
    _render_track_status(config, track)

    steps = steps_for_track(track)
    current_index = bounded_step(int(st.session_state.get("guided_demo_step", 0)), len(steps))
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

    back_col, open_col, next_col = st.columns(3)
    back_col.button(
        "Previous stage",
        disabled=current_index == 0,
        on_click=_move_stage,
        args=(-1, len(steps)),
        use_container_width=True,
    )
    navigation_button(
        open_col.button,
        f"Open {step.target_page.value}",
        step.target_page,
        kind="primary",
        use_container_width=True,
    )
    next_col.button(
        "Next stage",
        disabled=current_index == len(steps) - 1,
        on_click=_move_stage,
        args=(1, len(steps)),
        use_container_width=True,
    )


def _render_track_status(config: UiConfig, track: DemoTrack) -> None:
    section_header("Active Evidence Context")
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

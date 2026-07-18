"""Deterministic historical replay and source-array exploration for TOS data."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from traffictwin.integration.tos import TosReplayPoint
from traffictwin.integration.tos.readers import instrumented_key_for_run
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import render_page_header
from traffictwin.ui.services import (
    ServiceError,
    TosPackageView,
    load_tos_replay_for_ui,
    load_tos_replay_series_for_ui,
    load_tos_rsu_series_for_ui,
    load_tos_task_sample_for_ui,
    tos_rsu_summary_for_ui,
    tos_task_summary_for_ui,
    tos_trace_summary_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package
from traffictwin.ui.tos_replay_state import (
    TosReplayControl,
    advance_replay,
    restart_replay,
    step_replay,
)


def render(config: UiConfig) -> None:
    """Render replay controls and evidence-safe mobility/RSU/task panels."""

    render_page_header(UiPage.TOS_REPLAY)
    badge_row(["HISTORICAL REPLAY", "IMPORTED SIMULATION", "NOT LIVE"])
    st.info(
        "Replay uses supplied per-step arrays and processed SUMO FCD traces. Vehicle slots are "
        "time-local, RSU pressure is not CPU utilisation, and no trip records are available."
    )
    package = active_tos_package(config)
    if package is None or not package.instrumented_runs:
        if package is not None:
            st.info("No matched per-step and summary artifacts are available.")
        return
    run_key = st.selectbox("Instrumented run", package.instrumented_runs, key="tos_replay_run")
    series_key = f"tos_replay_series:{run_key}"
    series = st.session_state.get(series_key)
    if not isinstance(series, list):
        loaded = load_tos_replay_series_for_ui(package.source_path, run_key)
        if isinstance(loaded, ServiceError):
            st.error(loaded.message)
            return
        series = loaded
        st.session_state[series_key] = series
    if not series:
        st.info("The selected run has no replay points.")
        return
    _replay_controls(package, run_key, series)
    _render_trace_profile(package, run_key)
    _render_rsu_explorer(package, run_key)
    _render_task_explorer(package, run_key)


@st.fragment(run_every=0.5)  # type: ignore[untyped-decorator]
def _replay_controls(
    package: TosPackageView,
    run_key: str,
    series: list[TosReplayPoint],
) -> None:
    maximum = len(series) - 1
    state_key = f"tos_replay_control:{run_key}"
    state = st.session_state.get(state_key)
    if not isinstance(state, TosReplayControl):
        state = TosReplayControl()
    speed = st.select_slider(
        "Playback speed",
        options=[0.25, 0.5, 1.0, 2.0, 5.0],
        value=state.speed,
        format_func=lambda value: f"{value:g}x",
        key=f"tos_replay_speed:{run_key}",
    )
    state = TosReplayControl(position=state.position, playing=state.playing, speed=float(speed))
    buttons = st.columns(6)
    if buttons[0].button("Play", key=f"tos_play:{run_key}", disabled=state.playing):
        state = TosReplayControl(position=state.position, playing=True, speed=state.speed)
    if buttons[1].button("Pause", key=f"tos_pause:{run_key}", disabled=not state.playing):
        state = TosReplayControl(position=state.position, playing=False, speed=state.speed)
    if buttons[2].button("Restart", key=f"tos_restart:{run_key}"):
        state = restart_replay(state)
    if buttons[3].button("Step back", key=f"tos_back:{run_key}"):
        state = step_replay(state, maximum, -1)
    if buttons[4].button("Step forward", key=f"tos_forward:{run_key}"):
        state = step_replay(state, maximum, 1)
    jump = int(
        st.slider(
            "Timeline scrubber",
            min_value=0,
            max_value=maximum,
            value=int(state.position),
            key=f"tos_jump:{run_key}",
        )
    )
    if buttons[5].button("Jump", key=f"tos_jump_button:{run_key}"):
        state = TosReplayControl(position=float(jump), playing=False, speed=state.speed)
    index = min(maximum, max(0, int(state.position)))
    point = series[index]
    st.progress(index / maximum if maximum else 1.0, text=f"Index {index} of {maximum}")
    metrics = st.columns(5)
    metrics[0].metric("Simulation time", f"{point.timestamp_s:g} s")
    metrics[1].metric("Arrivals", point.arrivals)
    metrics[2].metric("Deadline met", point.deadline_met)
    metrics[3].metric("Active slots", point.active_vehicle_slots)
    metrics[4].metric("State", "PLAYING" if state.playing else "PAUSED")
    start = max(0, index - 240)
    visible = series[start : index + 1]
    timeline = go.Figure()
    timeline.add_trace(
        go.Scatter(
            x=[item.timestamp_s for item in visible],
            y=[item.arrivals for item in visible],
            name="Arrivals",
            mode="lines",
        )
    )
    timeline.add_trace(
        go.Scatter(
            x=[item.timestamp_s for item in visible],
            y=[item.deadline_met for item in visible],
            name="Deadline met",
            mode="lines",
        )
    )
    timeline.update_layout(
        xaxis_title="Simulation time (s)",
        yaxis_title="Tasks per source step",
        height=300,
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
    )
    st.plotly_chart(timeline, width="stretch", key=f"tos_timeline_chart:{run_key}")
    if st.button("Load spatial frame at current index", key=f"tos_spatial:{run_key}:{index}"):
        st.session_state[f"tos_spatial_frame:{run_key}"] = load_tos_replay_for_ui(
            package.source_path, run_key, index, max_vehicles=250
        )
    frame = st.session_state.get(f"tos_spatial_frame:{run_key}")
    if isinstance(frame, ServiceError):
        st.error(frame.message)
    elif frame is not None:
        _render_spatial_frame(frame)
    st.session_state[state_key] = advance_replay(state, maximum)


def _render_spatial_frame(frame: object) -> None:
    vehicles = frame.vehicles  # type: ignore[attr-defined]
    rsus = frame.rsus  # type: ignore[attr-defined]
    figure = go.Figure()
    if vehicles:
        figure.add_trace(
            go.Scatter(
                x=[vehicle.position_x_source_units for vehicle in vehicles],
                y=[vehicle.position_y_source_units for vehicle in vehicles],
                text=[vehicle.slot_reference for vehicle in vehicles],
                customdata=[vehicle.speed_source_units for vehicle in vehicles],
                mode="markers",
                name="Vehicle slots",
                hovertemplate=(
                    "%{text}<br>x=%{x:.1f} m<br>y=%{y:.1f} m"
                    "<br>speed=%{customdata:.2f} m/s<extra></extra>"
                ),
            )
        )
    figure.add_trace(
        go.Scatter(
            x=[rsu.position_x_source_units for rsu in rsus],
            y=[rsu.position_y_source_units for rsu in rsus],
            text=[rsu.rsu_reference for rsu in rsus],
            mode="markers",
            marker={"symbol": "square", "size": 12},
            name="RSUs",
        )
    )
    figure.update_layout(
        xaxis_title="Network x (m)",
        yaxis_title="Network y (m)",
        height=430,
        title="Processed FCD coordinate plane",
    )
    st.plotly_chart(figure, width="stretch")
    st.caption(
        "This is a source coordinate plane, not a geographic live map. Only a bounded vehicle "
        "sample is rendered."
    )


def _render_trace_profile(package: TosPackageView, run_key: str) -> None:
    evaluation = next(
        (row for row in package.evaluation_runs if instrumented_key_for_run(row) == run_key),
        None,
    )
    if evaluation is None:
        return
    with st.expander("Processed mobility profile"):
        if st.button("Summarise processed FCD trace", key=f"tos_trace_summary:{run_key}"):
            st.session_state[f"tos_trace_summary_value:{run_key}"] = tos_trace_summary_for_ui(
                package, evaluation.trace
            )
        summary = st.session_state.get(f"tos_trace_summary_value:{run_key}")
        if isinstance(summary, ServiceError):
            st.error(summary.message)
        elif summary is not None:
            st.write(
                {
                    "trace": summary.trace_file,
                    "timeline_points": summary.timeline_point_count,
                    "active_slot_observations": summary.observation_count,
                    "mean_speed_mps": summary.speed_mps.mean,
                    "p50_speed_mps": summary.speed_mps.p50,
                }
            )
            profile = go.Figure(
                go.Scatter(
                    x=[point.timestamp_s for point in summary.profile],
                    y=[point.mean_speed_mps for point in summary.profile],
                    mode="lines",
                    name="Mean active-slot speed",
                )
            )
            profile.update_layout(
                xaxis_title="Simulation time (s)", yaxis_title="Speed (m/s)", height=320
            )
            st.plotly_chart(profile, width="stretch")
            for warning in summary.warnings:
                st.caption(warning)


def _render_rsu_explorer(package: TosPackageView, run_key: str) -> None:
    with st.expander("RSU pressure explorer"):
        st.info(
            "Pressure = active in-flight tasks / recorded maximum concurrent tasks. Remaining "
            "compute backlog is in milliseconds. Neither is CPU utilisation."
        )
        if st.button("Summarise all RSUs", key=f"tos_rsu_summary:{run_key}"):
            st.session_state[f"tos_rsu_summary_value:{run_key}"] = tos_rsu_summary_for_ui(
                package, run_key
            )
        summary = st.session_state.get(f"tos_rsu_summary_value:{run_key}")
        if isinstance(summary, ServiceError):
            st.error(summary.message)
        elif summary is not None:
            st.dataframe(
                [
                    {
                        "RSU": rsu.rsu_reference,
                        "mean pressure": rsu.concurrency_pressure_fraction.mean,
                        "max pressure": rsu.concurrency_pressure_fraction.maximum,
                        "mean backlog ms": rsu.remaining_compute_backlog_ms.mean,
                        "max backlog ms": rsu.remaining_compute_backlog_ms.maximum,
                        "peak pressure time s": rsu.peak_pressure_timestamp_s,
                    }
                    for rsu in summary.rsus
                ],
                hide_index=True,
                width="stretch",
            )
        if st.button("Load downsampled RSU history", key=f"tos_rsu_history:{run_key}"):
            st.session_state[f"tos_rsu_history_value:{run_key}"] = load_tos_rsu_series_for_ui(
                package.source_path, run_key, stride=10
            )
        points = st.session_state.get(f"tos_rsu_history_value:{run_key}")
        if isinstance(points, list) and points:
            chart = go.Figure()
            for reference in sorted({point.rsu_reference for point in points}):
                selected = [point for point in points if point.rsu_reference == reference]
                chart.add_trace(
                    go.Scatter(
                        x=[point.timestamp_s for point in selected],
                        y=[point.concurrency_pressure_fraction for point in selected],
                        mode="lines",
                        name=reference,
                    )
                )
            chart.update_layout(
                xaxis_title="Simulation time (s)",
                yaxis_title="Concurrency pressure (fraction)",
                height=360,
            )
            st.plotly_chart(chart, width="stretch")


def _render_task_explorer(package: TosPackageView, run_key: str) -> None:
    if run_key not in package.pertask_runs:
        return
    with st.expander("Task outcome explorer"):
        st.warning(
            "task_met means modelled latency within the class deadline. It does not mean that a "
            "late task physically completed later."
        )
        if st.button("Build exact task summary", key=f"tos_task_summary:{run_key}"):
            with st.spinner("Aggregating the complete showcase array..."):
                st.session_state[f"tos_task_summary_value:{run_key}"] = tos_task_summary_for_ui(
                    package, run_key
                )
        summary = st.session_state.get(f"tos_task_summary_value:{run_key}")
        if isinstance(summary, ServiceError):
            st.error(summary.message)
        elif summary is not None:
            columns = st.columns(4)
            columns[0].metric("Tasks", summary.task_count)
            columns[1].metric("Deadline success", f"{summary.deadline_success_rate:.1%}")
            columns[2].metric("Latency P50", f"{summary.latency_ms.p50:.1f} ms")
            columns[3].metric("Latency max", f"{summary.latency_ms.maximum:.1f} ms")
            breakdown = st.segmented_control(
                "Breakdown",
                ["Task class", "Decision"],
                default="Task class",
                key=f"tos_task_breakdown:{run_key}",
            )
            rows = summary.by_task_class if breakdown == "Task class" else summary.by_decision
            st.dataframe(
                [item.model_dump(mode="json") for item in rows],
                hide_index=True,
                width="stretch",
            )
        if st.button("Load bounded task sample", key=f"tos_task_sample:{run_key}"):
            st.session_state[f"tos_task_sample_value:{run_key}"] = load_tos_task_sample_for_ui(
                package.source_path, run_key, limit=100
            )
        sample = st.session_state.get(f"tos_task_sample_value:{run_key}")
        if sample is not None and not isinstance(sample, ServiceError):
            st.dataframe(
                [item.model_dump(mode="json") for item in sample.observations],
                hide_index=True,
                width="stretch",
            )

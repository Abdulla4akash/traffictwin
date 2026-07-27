"""RSU Monitor page: which RSU is overwhelmed, and how overwhelmed.

A thin surface over :mod:`traffictwin.ui.rsu_monitor_services`. The page reads
one already-imported TOS run through the accepted RSU loaders, shows the
cross-RSU load asymmetry, and drills into exactly one selected RSU at a time.
Every derived number is computed in the tested service module; this file only
selects, labels, and draws.

This is historical replay of imported arrays, never live monitoring. Pressure
is in-flight tasks over the recorded maximum concurrent tasks — not CPU
utilisation — and the two measurements the source genuinely lacks (per-RSU
energy, per-RSU processed tasks) stay visibly unavailable.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.rsu_monitor_services import (
    RsuLoadProfile,
    RsuMonitorError,
    RsuMonitorView,
    build_rsu_monitor_view,
)
from traffictwin.ui.services import (
    ServiceError,
    TosPackageView,
    load_tos_rsu_series_for_ui,
    tos_task_summary_for_ui,
)
from traffictwin.ui.state import UiConfig
from traffictwin.ui.tos_context import active_tos_package

_STRIDE_CHOICES = (1, 5, 10, 30, 60)


def render(config: UiConfig) -> None:
    """Render the per-RSU load drill-down for one imported instrumented run."""

    st.title("RSU Monitor")
    badge_row(["HISTORICAL REPLAY", "IMPORTED SIMULATION", "NOT LIVE"])
    st.caption(
        "Per-RSU load over one imported run's trace window. Pressure is active "
        "in-flight tasks divided by the recorded maximum concurrent tasks; it is "
        "not CPU utilisation, and nothing here is live monitoring."
    )

    package = active_tos_package(config)
    if package is None:
        return
    if not package.instrumented_runs:
        st.info(
            "This package has no matched per-step artifacts, so no RSU history "
            "is available. Import an instrumented run on the TOS Data Import page."
        )
        return

    run_key = st.selectbox("Instrumented run", package.instrumented_runs, key="rsu_monitor_run")
    stride = st.select_slider(
        "Sampling stride (steps between plotted points)",
        options=_STRIDE_CHOICES,
        value=10,
        key="rsu_monitor_stride",
        help="A larger stride downsamples the window; it never smooths or interpolates.",
    )
    view = _load_view(package, str(run_key), int(stride))
    if view is None:
        return

    _render_window_identity(view)
    _render_asymmetry(view)
    _render_selected_rsu(view)
    _render_unavailable(view)
    _render_run_level_tasks(package, str(run_key))


def _load_view(package: TosPackageView, run_key: str, stride: int) -> RsuMonitorView | None:
    points = load_tos_rsu_series_for_ui(package.source_path, run_key, stride=stride)
    if isinstance(points, ServiceError):
        st.error(points.message)
        if points.detail:
            with st.expander("Advanced: technical detail"):
                st.code(points.detail, language=None)
        return None
    view = build_rsu_monitor_view(points, run_key, stride=stride)
    if isinstance(view, RsuMonitorError):
        st.info(view.message)
        if view.detail:
            with st.expander("Advanced: technical detail"):
                st.code(view.detail, language=None)
        return None
    return view


def _render_window_identity(view: RsuMonitorView) -> None:
    identity = view.identity
    columns = st.columns(4)
    columns[0].metric("RSUs in window", identity.rsu_count)
    columns[1].metric("Sampled points", identity.point_count)
    columns[2].metric("Window (s)", f"{identity.window_duration_s:.0f}")
    columns[3].metric("Stride", identity.stride)
    st.caption(
        f"Run `{identity.run_key}` — source `{identity.source_file}`, simulation "
        f"seconds {identity.first_timestamp_s:.0f}–{identity.last_timestamp_s:.0f}, "
        f"RSU semantics evidenced at commit `{identity.semantics_evidence_commit}`."
    )


def _render_asymmetry(view: RsuMonitorView) -> None:
    asymmetry = view.asymmetry
    st.subheader("Load asymmetry across all RSUs")
    if asymmetry.rsu_count == 1:
        st.caption("This window records a single RSU, so there is no load to spread.")
    else:
        st.caption(
            f"**{asymmetry.busiest_rsu_reference}** carries the highest mean pressure "
            f"({asymmetry.highest_mean_pressure:.3f}) and "
            f"{asymmetry.busiest_share_of_active_task_time:.1%} of all in-flight "
            f"task-observations — {asymmetry.busiest_share_ratio_to_even:.2f}× an even "
            f"split across {asymmetry.rsu_count} RSUs. "
            f"{asymmetry.saturated_rsu_count} of {asymmetry.rsu_count} reached the "
            "recorded concurrency maximum at least once."
        )
    st.dataframe(
        [
            {
                "RSU": profile.rsu_reference,
                "mean pressure": round(profile.mean_pressure, 6),
                "peak pressure": round(profile.peak_pressure, 6),
                "mean in-flight tasks": round(profile.mean_active_task_count, 4),
                "peak in-flight tasks": profile.peak_active_task_count,
                "mean backlog (ms)": round(profile.mean_backlog_ms, 3),
                "peak backlog (ms)": round(profile.peak_backlog_ms, 3),
                "saturated share": round(profile.saturated_share, 6),
                "max concurrent": profile.max_concurrent_tasks,
            }
            for profile in view.profiles
        ],
        hide_index=True,
        width="stretch",
    )


def _render_selected_rsu(view: RsuMonitorView) -> None:
    st.subheader("One RSU over the window")
    reference = st.selectbox(
        "RSU (listed busiest first)",
        view.rsu_references,
        key="rsu_monitor_selected",
    )
    profile = view.profile_for(str(reference))
    if profile is None:
        st.info("That RSU is not present in this window.")
        return
    columns = st.columns(4)
    columns[0].metric("Mean pressure", f"{profile.mean_pressure:.3f}")
    columns[1].metric("Peak pressure", f"{profile.peak_pressure:.3f}")
    columns[2].metric("Peak backlog (ms)", f"{profile.peak_backlog_ms:.0f}")
    columns[3].metric("Peak in-flight tasks", profile.peak_active_task_count)
    st.caption(
        f"Peak pressure at simulation second {profile.peak_pressure_timestamp_s:.0f}; "
        f"peak backlog at {profile.peak_backlog_timestamp_s:.0f}. "
        f"{profile.saturated_observation_count} of {profile.observation_count} sampled "
        f"points sat at the recorded maximum of {profile.max_concurrent_tasks} "
        "concurrent tasks."
    )
    st.plotly_chart(_queue_figure(profile), width="stretch")
    st.plotly_chart(_backlog_figure(profile), width="stretch")


def _queue_figure(profile: RsuLoadProfile) -> go.Figure:
    timestamps = [point.timestamp_s for point in profile.points]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=[point.active_task_count for point in profile.points],
            mode="lines",
            name="In-flight tasks",
        )
    )
    figure.add_trace(
        go.Scatter(
            x=timestamps,
            y=[profile.max_concurrent_tasks] * len(profile.points),
            mode="lines",
            name="Recorded maximum concurrent",
            line={"dash": "dash"},
        )
    )
    figure.update_layout(
        title=f"{profile.rsu_reference}: in-flight tasks against recorded capacity",
        xaxis_title="Simulation time (s)",
        yaxis_title="Tasks",
        height=320,
    )
    return figure


def _backlog_figure(profile: RsuLoadProfile) -> go.Figure:
    figure = go.Figure(
        go.Scatter(
            x=[point.timestamp_s for point in profile.points],
            y=[point.remaining_compute_backlog_ms for point in profile.points],
            mode="lines",
            name="Remaining compute backlog",
        )
    )
    figure.update_layout(
        title=f"{profile.rsu_reference}: remaining compute backlog",
        xaxis_title="Simulation time (s)",
        yaxis_title="Backlog (ms)",
        height=320,
    )
    return figure


def _render_unavailable(view: RsuMonitorView) -> None:
    with st.expander("Measurements this source does not carry"):
        for item in view.unavailable:
            st.warning(f"**{item.measurement}** — {item.status}. {item.reason}")


def _render_run_level_tasks(package: TosPackageView, run_key: str) -> None:
    if run_key not in package.pertask_runs:
        return
    with st.expander("Run-level task outcomes (not per RSU)"):
        st.caption(
            "These totals describe the whole run. The per-task arrays carry no RSU "
            "attribution, so none of it can be assigned to an individual RSU."
        )
        if st.button("Summarise run-level task outcomes", key=f"rsu_monitor_tasks:{run_key}"):
            st.session_state[f"rsu_monitor_tasks_value:{run_key}"] = tos_task_summary_for_ui(
                package, run_key
            )
        summary = st.session_state.get(f"rsu_monitor_tasks_value:{run_key}")
        if isinstance(summary, ServiceError):
            st.error(summary.message)
        elif summary is not None:
            st.write(
                {
                    "run_key": summary.run_key,
                    "task_count": summary.task_count,
                    "deadline_success_count": summary.deadline_success_count,
                    "deadline_success_rate": summary.deadline_success_rate,
                    "mean_latency_ms": summary.latency_ms.mean,
                }
            )
            st.caption(
                "Deadline success means modelled latency within the class deadline; "
                "it does not mean a late task physically completed later."
            )

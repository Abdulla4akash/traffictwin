"""Operations View in historical replay mode."""

from __future__ import annotations

import streamlit as st

from traffictwin.ui.charts import (
    infrastructure_series,
    line_figure,
    task_event_series,
    traffic_series,
)
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.labels import DataMode
from traffictwin.ui.pages.helpers import load_selected_analysis, render_source_caption
from traffictwin.ui.state import (
    ReplayClockState,
    ReplayFilters,
    replay_clock_from_tables,
    replay_filter_options,
    replay_window_counts,
)

PLAYBACK_SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0]


def render() -> None:
    """Render historical replay operations view."""

    st.title("Operations View")
    analysis = load_selected_analysis()
    if analysis is None:
        return
    badge_row([DataMode.HISTORICAL_REPLAY.value, DataMode.SYNTHETIC.value])
    render_source_caption(analysis)

    clock = replay_clock_from_tables(analysis.validation.canonical)
    stored = st.session_state.get("replay_clock")
    if isinstance(stored, dict):
        clock = ReplayClockState.model_validate(stored)
        if clock.max_timestamp_s == 0 and clock.min_timestamp_s == 0:
            clock = replay_clock_from_tables(analysis.validation.canonical)

    st.subheader("Replay Clock")
    cols = st.columns(4)
    cols[0].metric("Current timestamp", f"{clock.current_timestamp_s:.1f} s")
    cols[1].metric("First timestamp", f"{clock.min_timestamp_s:.1f} s")
    cols[2].metric("Final timestamp", f"{clock.max_timestamp_s:.1f} s")
    speed = cols[3].selectbox(
        "Playback speed",
        PLAYBACK_SPEEDS,
        index=_speed_index(clock.playback_speed),
        format_func=lambda value: f"{value:g}x",
    )
    clock = clock.model_copy(update={"playback_speed": speed})

    step_s = max(1.0, min(30.0, (clock.max_timestamp_s - clock.min_timestamp_s) / 20.0))
    play_col, pause_col, resume_col, restart_col, back_col, forward_col = st.columns(6)
    if play_col.button("Play"):
        clock = clock.play()
    if pause_col.button("Pause"):
        clock = clock.pause()
    if resume_col.button("Resume"):
        clock = clock.resume()
    if restart_col.button("Restart"):
        clock = clock.restart()
    if back_col.button("Step Back"):
        clock = clock.step(-step_s)
    if forward_col.button("Step Forward"):
        clock = clock.step(step_s)

    jump = st.number_input(
        "Timestamp jump (s)",
        min_value=float(clock.min_timestamp_s),
        max_value=float(clock.max_timestamp_s),
        value=float(clock.current_timestamp_s),
        step=1.0,
    )
    clock = clock.scrub(jump)

    scrubbed = st.slider(
        "Timeline scrubber",
        min_value=float(clock.min_timestamp_s),
        max_value=float(clock.max_timestamp_s),
        value=float(clock.current_timestamp_s),
    )
    clock = clock.scrub(scrubbed)
    options = replay_filter_options(analysis.validation.canonical)
    stored_filters = st.session_state.get("replay_filters")
    filters = (
        ReplayFilters.model_validate(stored_filters)
        if isinstance(stored_filters, dict)
        else ReplayFilters()
    )
    st.subheader("Replay Filters")
    filter_cols = st.columns(4)
    vehicle = filter_cols[0].selectbox(
        "Vehicle",
        ["All", *options["vehicles"]],
        index=_option_index(["All", *options["vehicles"]], filters.vehicle_id),
    )
    rsu = filter_cols[1].selectbox(
        "RSU",
        ["All", *options["rsus"]],
        index=_option_index(["All", *options["rsus"]], filters.rsu_id),
    )
    task_class = filter_cols[2].selectbox(
        "Task class",
        ["All", *options["task_classes"]],
        index=_option_index(["All", *options["task_classes"]], filters.task_class),
    )
    incident = filter_cols[3].selectbox(
        "Incident",
        ["All", *options["incident_types"]],
        index=_option_index(["All", *options["incident_types"]], filters.incident_type),
    )
    filters = ReplayFilters(
        vehicle_id=None if vehicle == "All" else vehicle,
        rsu_id=None if rsu == "All" else rsu,
        task_class=None if task_class == "All" else task_class,
        incident_type=None if incident == "All" else incident,
    )
    st.session_state["replay_clock"] = clock.model_dump(mode="json")
    st.session_state["replay_filters"] = filters.model_dump(mode="json")
    st.json(
        replay_window_counts(
            analysis.validation.canonical,
            clock.current_timestamp_s,
            filters=filters,
        )
    )

    traffic_rows = traffic_series(analysis.validation.canonical)
    if traffic_rows:
        st.plotly_chart(
            line_figure(
                traffic_rows,
                x_key="timestamp_s",
                y_keys=["count", "average_speed_mps"],
                title="Traffic count and average speed over time",
                y_title="Traffic observation",
            ),
            width="stretch",
        )
    else:
        render_unavailable_panel(
            "Traffic panel unavailable", ["traffic_obs.csv"], ["EVIDENCE_TRAFFIC_UNAVAILABLE"]
        )

    infra_rows = infrastructure_series(analysis.validation.canonical)
    if infra_rows:
        st.plotly_chart(
            line_figure(
                infra_rows,
                x_key="timestamp_s",
                y_keys=["queue_length", "utilisation_fraction"],
                title="RSU queue and utilisation over time",
                y_title="Infrastructure state",
            ),
            width="stretch",
        )
    else:
        render_unavailable_panel(
            "RSU panel unavailable", ["infra_state.csv"], ["EVIDENCE_INFRA_UNAVAILABLE"]
        )

    task_rows = task_event_series(analysis.validation.canonical)
    if task_rows:
        st.plotly_chart(
            line_figure(
                task_rows,
                x_key="timestamp_s",
                y_keys=["arrivals", "completions"],
                title="Task arrivals and completions over time",
                y_title="Tasks",
            ),
            width="stretch",
        )
    else:
        render_unavailable_panel(
            "Task panel unavailable", ["tasks.csv"], ["EVIDENCE_TASKS_UNAVAILABLE"]
        )

    if analysis.validation.canonical.vehicles:
        st.dataframe(
            [record.model_dump(mode="json") for record in analysis.validation.canonical.vehicles],
            width="stretch",
        )
    else:
        st.info("Vehicle coordinates are unavailable; map views are not rendered.")


def _speed_index(speed: float) -> int:
    if speed in PLAYBACK_SPEEDS:
        return PLAYBACK_SPEEDS.index(speed)
    return PLAYBACK_SPEEDS.index(1.0)


def _option_index(options: list[str], selected: str | None) -> int:
    if selected is None or selected not in options:
        return 0
    return options.index(selected)

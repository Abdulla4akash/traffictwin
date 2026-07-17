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
from traffictwin.ui.state import ReplayClockState, replay_clock_from_tables, replay_window_counts


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
    speed = cols[3].number_input(
        "Playback speed", min_value=0.1, value=clock.playback_speed, step=0.5
    )
    clock = clock.model_copy(update={"playback_speed": speed})

    play_col, pause_col, reset_col = st.columns(3)
    if play_col.button("Play"):
        clock = clock.play()
    if pause_col.button("Pause"):
        clock = clock.pause()
    if reset_col.button("Reset"):
        clock = replay_clock_from_tables(analysis.validation.canonical, speed=speed)

    scrubbed = st.slider(
        "Timeline scrubber",
        min_value=float(clock.min_timestamp_s),
        max_value=float(clock.max_timestamp_s),
        value=float(clock.current_timestamp_s),
    )
    clock = clock.scrub(scrubbed)
    st.session_state["replay_clock"] = clock.model_dump(mode="json")
    st.json(replay_window_counts(analysis.validation.canonical, clock.current_timestamp_s))

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

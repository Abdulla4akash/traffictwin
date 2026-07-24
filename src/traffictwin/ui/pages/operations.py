"""Operations View in historical replay mode."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from traffictwin.ui.charts import (
    corridor_figure,
    infrastructure_series,
    line_figure,
    task_event_series,
    traffic_series,
)
from traffictwin.ui.components.badges import badge_markdown, badge_row
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.labels import DataMode
from traffictwin.ui.pages.helpers import (
    load_selected_analysis,
    render_source_caption,
    selected_bundle_path,
)
from traffictwin.ui.services import ReplayBundleChoice, list_replay_bundles_for_ui
from traffictwin.ui.state import (
    ReplayClockState,
    ReplayFilters,
    UiConfig,
    replay_clock_from_tables,
    replay_filter_options,
    replay_window_counts,
)
from traffictwin.ui.tables import table_column_config

PLAYBACK_SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0]
FILTER_WIDGET_KEYS = (
    "replay_filter_vehicle",
    "replay_filter_rsu",
    "replay_filter_task_class",
    "replay_filter_incident",
)


def render(config: UiConfig | None = None) -> None:
    """Render historical replay operations view."""

    st.title("Operations View")
    current_path = selected_bundle_path()
    replay_root = _replay_root(config, current_path)
    choices = list_replay_bundles_for_ui(replay_root, current_path=current_path)
    if choices:
        selected_path = _render_replay_bundle_selector(choices, current_path)
        _activate_replay_bundle(selected_path)
    analysis = load_selected_analysis()
    if analysis is None:
        return
    badge_row([DataMode.HISTORICAL_REPLAY.value, DataMode.SYNTHETIC.value])
    st.caption(
        "Historical replay of recorded synthetic/source evidence. This is not live monitoring: "
        "the clock scrubs stored timestamps and no external feed is polled."
    )
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
    vehicle_options = ["All", *options["vehicles"]]
    rsu_options = ["All", *options["rsus"]]
    task_class_options = ["All", *options["task_classes"]]
    incident_options = ["All", *options["incident_types"]]
    _initialise_filter_widget("replay_filter_vehicle", vehicle_options, filters.vehicle_id)
    _initialise_filter_widget("replay_filter_rsu", rsu_options, filters.rsu_id)
    _initialise_filter_widget("replay_filter_task_class", task_class_options, filters.task_class)
    _initialise_filter_widget("replay_filter_incident", incident_options, filters.incident_type)
    incident_type_label = (
        "incident type" if len(options["incident_types"]) == 1 else "incident types"
    )
    st.caption(
        f"Available: {len(options['vehicles'])} vehicles · {len(options['rsus'])} RSUs · "
        f"{len(options['task_classes'])} task classes · "
        f"{len(options['incident_types'])} {incident_type_label}. "
        "Choose a value to filter the current-window counts and matching views below."
    )
    st.button(
        "Reset filters",
        key="replay_filter_reset",
        on_click=_reset_filter_widgets,
    )
    vehicle = cast(str, st.session_state["replay_filter_vehicle"])
    st.markdown("**Vehicle**")
    vehicle_cols = st.columns([1, 3, 1, 1])
    vehicle_cols[0].button(
        "Previous",
        key="replay_filter_vehicle_previous",
        on_click=_step_vehicle_filter,
        args=(options["vehicles"], -1),
        disabled=not options["vehicles"],
        width="stretch",
    )
    if vehicle == "All":
        vehicle_cols[1].info("Selected: all vehicles")
    else:
        vehicle_cols[1].success(f"Selected: {vehicle}")
    vehicle_cols[2].button(
        "Next",
        key="replay_filter_vehicle_next",
        on_click=_step_vehicle_filter,
        args=(options["vehicles"], 1),
        disabled=not options["vehicles"],
        width="stretch",
    )
    vehicle_cols[3].button(
        "Clear",
        key="replay_filter_vehicle_clear",
        on_click=_clear_vehicle_filter,
        disabled=vehicle == "All",
        width="stretch",
    )
    with st.expander("Choose a vehicle directly", expanded=vehicle == "All"):
        if options["vehicles"]:
            vehicle_grid = st.columns(5)
            for index, vehicle_id in enumerate(options["vehicles"]):
                vehicle_grid[index % len(vehicle_grid)].button(
                    vehicle_id,
                    key=f"replay_filter_vehicle_choice_{index}",
                    on_click=_set_vehicle_filter,
                    args=(vehicle_id,),
                    type="primary" if vehicle_id == vehicle else "secondary",
                    width="stretch",
                )
        else:
            st.caption("No vehicle-state records are available in this bundle.")
    st.caption(
        "The selected vehicle filters vehicle rows, the corridor plane, task events, and replay "
        "counts. Use a vehicle button or Previous/Next; Clear restores all vehicles."
    )

    filter_cols = st.columns(3)
    rsu = filter_cols[0].selectbox(
        "RSU",
        rsu_options,
        key="replay_filter_rsu",
        help=(
            "Filter infrastructure counts and the RSU queue/utilisation chart."
            if options["rsus"]
            else "No infrastructure records are available in this bundle."
        ),
        disabled=not options["rsus"],
    )
    task_class = filter_cols[1].selectbox(
        "Task class",
        task_class_options,
        key="replay_filter_task_class",
        help=(
            "Filter task arrival/completion counts and the task-event chart."
            if options["task_classes"]
            else "No task records are available in this bundle."
        ),
        disabled=not options["task_classes"],
    )
    incident = filter_cols[2].selectbox(
        "Incident",
        incident_options,
        key="replay_filter_incident",
        help=(
            "Filter incident counts and active incident annotations."
            if options["incident_types"]
            else "This bundle contains no incident records, so All is the only valid value."
        ),
        disabled=not options["incident_types"],
    )
    filters = ReplayFilters(
        vehicle_id=None if vehicle == "All" else vehicle,
        rsu_id=None if rsu == "All" else rsu,
        task_class=None if task_class == "All" else task_class,
        incident_type=None if incident == "All" else incident,
    )
    st.session_state["replay_clock"] = clock.model_dump(mode="json")
    st.session_state["replay_filters"] = filters.model_dump(mode="json")

    def _filter_badge(value: str | None) -> str:
        return badge_markdown(value) if value is not None else ":gray-badge[all]"

    st.markdown(
        f"**Active filters** — vehicle {_filter_badge(filters.vehicle_id)} · "
        f"RSU {_filter_badge(filters.rsu_id)} · "
        f"task class {_filter_badge(filters.task_class)} · "
        f"incident {_filter_badge(filters.incident_type)}"
    )

    counts = replay_window_counts(
        analysis.validation.canonical,
        clock.current_timestamp_s,
        filters=filters,
    )
    with st.container(border=True):
        st.markdown(
            f"**Current 60-second window** ending at {clock.current_timestamp_s:.1f} s "
            "(filtered counts over recorded evidence)"
        )
        count_cols = st.columns(6)
        count_cols[0].metric("Task arrivals", counts["task_arrivals"], border=True)
        count_cols[1].metric("Task completions", counts["task_completions"], border=True)
        count_cols[2].metric("Traffic rows", counts["traffic_observations"], border=True)
        count_cols[3].metric("RSU rows", counts["infrastructure_observations"], border=True)
        count_cols[4].metric("Vehicle rows", counts["vehicle_observations"], border=True)
        count_cols[5].metric("Incidents", counts["incidents"], border=True)

    st.subheader("Synthetic/source corridor plane")
    corridor = corridor_figure(
        analysis.validation.canonical,
        clock.current_timestamp_s,
        vehicle_id=filters.vehicle_id,
        incident_type=filters.incident_type,
    )
    if corridor is not None:
        st.caption(
            "This is a replay of source x/y coordinates, not a geographic map or live position. "
            "Incident locations remain text metadata unless a source coordinate exists."
        )
        st.plotly_chart(corridor, width="stretch")
    else:
        render_unavailable_panel(
            "Coordinate-plane replay unavailable",
            ["vehicle_state.csv with x and y fields"],
            ["EVIDENCE_VEHICLE_COORDINATES_UNAVAILABLE"],
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

    infra_rows = infrastructure_series(
        analysis.validation.canonical,
        rsu_id=filters.rsu_id,
    )
    if infra_rows:
        st.plotly_chart(
            line_figure(
                infra_rows,
                x_key="timestamp_s",
                y_keys=["queue_length", "utilisation_fraction"],
                title=(
                    "RSU queue and utilisation over time"
                    if filters.rsu_id is None
                    else f"RSU queue and utilisation over time · {filters.rsu_id}"
                ),
                y_title="Infrastructure state",
            ),
            width="stretch",
        )
    else:
        render_unavailable_panel(
            "RSU panel unavailable", ["infra_state.csv"], ["EVIDENCE_INFRA_UNAVAILABLE"]
        )

    task_rows = task_event_series(
        analysis.validation.canonical,
        vehicle_id=filters.vehicle_id,
        task_class=filters.task_class,
    )
    if task_rows:
        st.plotly_chart(
            line_figure(
                task_rows,
                x_key="timestamp_s",
                y_keys=["arrivals", "completions"],
                title=_task_chart_title(filters),
                y_title="Tasks",
            ),
            width="stretch",
        )
    else:
        render_unavailable_panel(
            "Task panel unavailable", ["tasks.csv"], ["EVIDENCE_TASKS_UNAVAILABLE"]
        )

    if analysis.validation.canonical.vehicles:
        with st.expander("Canonical vehicle-state rows", expanded=False):
            vehicle_records = [
                record
                for record in analysis.validation.canonical.vehicles
                if filters.vehicle_id is None or record.vehicle_id == filters.vehicle_id
            ]
            vehicle_rows = [record.model_dump(mode="json") for record in vehicle_records]
            st.caption(
                "Source vehicle-state rows for the selected vehicle filter. These are recorded "
                "replay coordinates, not live positions."
            )
            st.dataframe(
                vehicle_rows,
                width="stretch",
                hide_index=True,
                column_config=table_column_config(vehicle_rows, hide_machine_ids=False),
            )


def _speed_index(speed: float) -> int:
    if speed in PLAYBACK_SPEEDS:
        return PLAYBACK_SPEEDS.index(speed)
    return PLAYBACK_SPEEDS.index(1.0)


def _replay_root(config: UiConfig | None, current_path: Path) -> Path:
    """Choose the configured bundle catalogue when it contains the active bundle."""

    if config is None:
        return current_path.parent
    configured = config.default_fixture_path
    try:
        current_path.resolve().relative_to(configured.resolve())
    except ValueError:
        return current_path.parent
    return configured


def _render_replay_bundle_selector(
    choices: list[ReplayBundleChoice],
    current_path: Path,
) -> str:
    """Render an explicit bundle selector and prefer incident evidence in the demo."""

    options = [str(choice.path) for choice in choices]
    choice_by_path = {str(choice.path): choice for choice in choices}
    current = str(current_path)
    widget_value = st.session_state.get("replay_bundle_path")
    stored_value = st.session_state.get("replay_selected_bundle_path")
    if widget_value not in options:
        st.session_state["replay_bundle_path"] = (
            stored_value if stored_value in options else _preferred_replay_path(choices, current)
        )
    selected = st.selectbox(
        "Replay dataset",
        options,
        key="replay_bundle_path",
        format_func=lambda value: _replay_bundle_label(choice_by_path[value]),
        help=(
            "Choose which validated run bundle supplies the vehicle, RSU, task, and incident "
            "filter options. The synthetic stressed-demand demo includes incident evidence."
        ),
    )
    st.caption(
        "Filter choices come from this dataset. Select an incident-capable dataset to enable "
        "the Incident filter."
    )
    return cast(str, selected)


def _preferred_replay_path(
    choices: list[ReplayBundleChoice],
    current: str,
) -> str:
    """Prefer an incident-capable demo when the application opens on its baseline."""

    current_choice = next((choice for choice in choices if str(choice.path) == current), None)
    if (
        current_choice is not None
        and current_choice.path.name == "baseline"
        and current_choice.incident_count == 0
    ):
        incident_choice = next(
            (choice for choice in choices if choice.incident_count > 0),
            None,
        )
        if incident_choice is not None:
            return str(incident_choice.path)
    if current_choice is not None:
        return current
    incident_choice = next((choice for choice in choices if choice.incident_count > 0), None)
    return str((incident_choice or choices[0]).path)


def _replay_bundle_label(choice: ReplayBundleChoice) -> str:
    """Return a compact evidence summary for one replay bundle."""

    name = choice.path.name.replace("_", " ").title()
    vehicle_label = "vehicle" if choice.vehicle_count == 1 else "vehicles"
    incident_label = "incident" if choice.incident_count == 1 else "incidents"
    return (
        f"{name} — {choice.vehicle_count} {vehicle_label}, {choice.incident_count} {incident_label}"
    )


def _activate_replay_bundle(selected_path: str) -> None:
    """Switch replay evidence and reset state that belongs to the previous bundle."""

    previous = st.session_state.get("replay_active_bundle_path")
    st.session_state["selected_bundle_path"] = selected_path
    st.session_state["replay_selected_bundle_path"] = selected_path
    if previous == selected_path:
        return
    st.session_state["replay_active_bundle_path"] = selected_path
    st.session_state["replay_clock"] = ReplayClockState().model_dump(mode="json")
    _reset_filter_widgets()


def _initialise_filter_widget(
    key: str,
    options: list[str],
    selected: str | None,
) -> None:
    """Initialise or repair one stable replay-filter widget value."""

    current = st.session_state.get(key)
    if current in options:
        return
    st.session_state[key] = selected if selected in options else "All"


def _reset_filter_widgets() -> None:
    """Reset all replay-filter widgets before Streamlit reruns the page."""

    for key in FILTER_WIDGET_KEYS:
        st.session_state[key] = "All"
    st.session_state["replay_filters"] = ReplayFilters().model_dump(mode="json")


def _step_vehicle_filter(vehicle_ids: list[str], direction: int) -> None:
    """Move to an adjacent available vehicle using deterministic wraparound."""

    if not vehicle_ids:
        return
    current = st.session_state.get("replay_filter_vehicle", "All")
    if current not in vehicle_ids:
        next_index = 0 if direction >= 0 else len(vehicle_ids) - 1
    else:
        next_index = (vehicle_ids.index(current) + direction) % len(vehicle_ids)
    st.session_state["replay_filter_vehicle"] = vehicle_ids[next_index]


def _clear_vehicle_filter() -> None:
    """Return the dedicated vehicle control to its unfiltered state."""

    st.session_state["replay_filter_vehicle"] = "All"


def _set_vehicle_filter(vehicle_id: str) -> None:
    """Select one available vehicle from the direct button grid."""

    st.session_state["replay_filter_vehicle"] = vehicle_id


def _task_chart_title(filters: ReplayFilters) -> str:
    qualifiers = [value for value in (filters.vehicle_id, filters.task_class) if value]
    if not qualifiers:
        return "Task arrivals and completions over time"
    return f"Task arrivals and completions over time · {' · '.join(qualifiers)}"

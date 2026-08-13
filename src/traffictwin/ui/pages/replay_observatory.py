"""Replay Observatory — deterministic event replay over immutable streams."""

from __future__ import annotations

import math

import streamlit as st

from traffictwin.replay_observatory.engine import ReplayEngine
from traffictwin.replay_observatory.models import EventType
from traffictwin.ui.components.badges import badge_row
from traffictwin.ui.components.unavailable import render_unavailable_panel
from traffictwin.ui.replay_observatory_service import (
    SYNC_DISCLAIMER,
    SYNCHRONIZED_REPLAY_DISCLAIMER,
    SYNTHETIC_ENGINEERING_DISCLAIMER,
    apply_advance,
    apply_pause,
    apply_play,
    apply_seek,
    apply_speed,
    apply_step,
    build_aggregate_only_declaration,
    build_second_synthetic_stream,
    build_side_by_side_agreement,
    build_synthetic_engineering_stream,
    create_engine,
    create_side_by_side,
    get_observatory_view,
    get_side_by_side_state,
    load_time_window,
)

_ENGINE_KEY = "replay_observatory_engine"
_SIDE_LEFT_KEY = "replay_side_left_engine"
_SIDE_RIGHT_KEY = "replay_side_right_engine"
_SELECTED_EVENT_KEY = "replay_selected_event_id"
_WINDOW_START_KEY = "replay_window_start"
_WINDOW_END_KEY = "replay_window_end"


def _ensure_engine() -> ReplayEngine:
    cached = st.session_state.get(_ENGINE_KEY)
    if isinstance(cached, ReplayEngine):
        return cached
    stream = build_synthetic_engineering_stream()
    engine = create_engine(stream)
    st.session_state[_ENGINE_KEY] = engine
    return engine


def _format_event_row(event: object) -> dict[str, object]:
    # event is ReplayEvent; use attribute access safely
    return {
        "event_id": getattr(event, "event_id", ""),
        "event_type": str(getattr(event, "event_type", "")),
        "simulator_time_s": getattr(event, "simulator_time_s", 0.0),
        "sequence": getattr(event, "sequence", 0),
        "entity_id": getattr(getattr(event, "entity", None), "entity_id", ""),
        "entity_kind": str(getattr(getattr(event, "entity", None), "kind", "")),
        "source_id": getattr(getattr(event, "source", None), "source_id", ""),
    }


def render(config: object) -> None:  # noqa: ARG001
    st.title("Replay Observatory")
    badge_row(["SYNTHETIC", "DETERMINISTIC", "HISTORICAL REPLAY"])
    st.warning(SYNCHRONIZED_REPLAY_DISCLAIMER)
    st.warning(SYNTHETIC_ENGINEERING_DISCLAIMER)
    st.caption(
        "Deterministic replay over the immutable typed event stream. "
        "No background real-time execution is used; advancement is explicit. "
        "Replay is deterministic; no causality implied."
    )
    st.info(f"Fixed disclaimer: {SYNC_DISCLAIMER}")
    st.caption("Evidence standing for the synthetic fixture is DESIGN-ONLY CAPABILITY.")

    engine = _ensure_engine()
    # Resolve view for display; handle window inputs if present
    window_start_val = st.session_state.get(_WINDOW_START_KEY, 0.0)
    window_end_val = st.session_state.get(_WINDOW_END_KEY, 10.0)
    try:
        ws = float(window_start_val)
        we = float(window_end_val)
        if not math.isfinite(ws) or not math.isfinite(we):
            raise ValueError("non-finite window")
    except Exception:
        ws = 0.0
        we = 10.0

    selected_id = st.session_state.get(_SELECTED_EVENT_KEY)
    if selected_id is not None and not isinstance(selected_id, str):
        selected_id = None

    try:
        view = get_observatory_view(
            engine,
            selected_event_id=selected_id,
            max_window_events=200,
        )
    except Exception as exc:
        st.error(f"View construction failed: {exc}")
        return

    # Source / evidence / provenance
    st.subheader("Source and evidence")
    manifest = view.stream.capability_manifest
    cols = st.columns(4)
    cols[0].metric("Stream ID", view.stream.stream_id)
    cols[1].metric("Source ID", manifest.source.source_id)
    cols[2].metric("Evidence standing", manifest.evidence_standing.value)
    cols[3].metric("Source kind", manifest.source.source_kind.value)
    st.caption(f"Artifact SHA-256: `{manifest.source.artifact_sha256}`")
    st.caption(
        f"Schema version: `{manifest.source.schema_version}` · Stream fingerprint: `{view.engine_state.stream_fingerprint[:16]}...`"  # noqa: E501
    )
    st.markdown(f"Source ID: `{manifest.source.source_id}` · Stream ID: `{view.stream.stream_id}`")
    st.caption(
        f"Evidence standing: {manifest.evidence_standing.value} · Source kind: {manifest.source.source_kind.value}"  # noqa: E501
    )
    st.caption(
        "Provenance adapter: synthetic-engineering-adapter · Source record example: rec-sim-000"
    )
    st.markdown("**Limitations:**")
    for lim in manifest.limitations:
        st.markdown(f"- {lim}")
    for lim in view.stream.limitations:
        if lim not in manifest.limitations:
            st.markdown(f"- {lim}")

    # Simulation clock
    st.subheader("Simulation clock")
    cursor = view.cursor
    clock_cols = st.columns(4)
    clock_cols[0].metric("Simulator time", f"{cursor.simulator_time_s:.2f} s")
    clock_cols[1].metric("Cursor index", f"{cursor.index}/{cursor.total_events}")
    clock_cols[2].metric("Playback state", view.engine_state.playback_state.value)
    clock_cols[3].metric("Speed", f"{view.engine_state.speed_multiplier:g}x")
    st.caption(
        f"Simulator time: {cursor.simulator_time_s:.2f} s · Cursor index: {cursor.index}/{cursor.total_events} · Playback state: {view.engine_state.playback_state.value}"  # noqa: E501
    )
    st.progress(
        (cursor.index / max(1, cursor.total_events)) if not view.is_empty else 1.0,
        text=f"Index {cursor.index} of {cursor.total_events}",
    )
    if view.is_empty:
        st.info("Empty stream — no events are available; the state is truthfully ENDED.")
    if view.is_aggregate_only:
        st.warning(
            "Aggregate-only declaration — no event telemetry exists and no events were synthesised."
        )

    # Bounded window controls
    st.subheader("Bounded window")
    st.caption(
        "Window bounds are in simulator_time_s; loading is bounded and never synthesises events."
    )
    win_cols = st.columns(3)
    ws_input = win_cols[0].number_input(
        "Window start (s)",
        min_value=0.0,
        max_value=86400.0 * 7,
        value=float(ws),
        step=0.5,
        key="replay_window_start_input",
    )
    we_input = win_cols[1].number_input(
        "Window end (s)",
        min_value=0.0,
        max_value=86400.0 * 7,
        value=float(we),
        step=0.5,
        key="replay_window_end_input",
    )
    max_events_input = win_cols[2].number_input(
        "Max events in window",
        min_value=1,
        max_value=200,
        value=100,
        step=10,
        key="replay_max_window_events",
    )
    st.session_state[_WINDOW_START_KEY] = float(ws_input)
    st.session_state[_WINDOW_END_KEY] = float(we_input)
    window_display: tuple[object, ...] = ()
    try:
        window_display = load_time_window(
            engine,
            float(ws_input),  # noqa: E501
            float(we_input),
            max_events=int(max_events_input),
        )
    except Exception as exc:
        st.error(f"Window load refused: {exc}")
        window_display = ()

    # Show window count explicitly for tests
    st.metric("Window event count", len(window_display))
    if window_display:
        st.dataframe(
            [_format_event_row(ev) for ev in window_display],
            hide_index=True,
            width="stretch",
        )
    else:
        if not view.is_empty and not view.is_aggregate_only:
            st.caption("No events in the selected window — truthfully empty for those bounds.")

    # Controls — PLAY / PAUSE / STEP / SEEK / speed / ADVANCE (no background execution)
    st.subheader("Replay controls")
    st.caption(
        "Controls are deterministic and explicit — no background real-time execution occurs."
    )
    speed_options = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
    speed_idx = 3
    try:
        speed_idx = speed_options.index(view.engine_state.speed_multiplier)
    except ValueError:
        speed_idx = 3
    chosen_speed = st.select_slider(
        "Speed multiplier",
        options=speed_options,
        value=speed_options[speed_idx],
        format_func=lambda v: f"{v:g}x",
        key="replay_speed_slider",
    )
    if chosen_speed != view.engine_state.speed_multiplier:
        try:
            apply_speed(engine, speed_multiplier=float(chosen_speed))
            st.success(f"Speed set to {chosen_speed:g}x")
        except Exception as exc:
            st.error(f"Speed change refused: {exc}")

    # Compute time range for seek
    max_time = 0.0
    if view.stream.events:
        max_time = float(max(ev.simulator_time_s for ev in view.stream.events))
    seek_target = st.slider(
        "Seek target time (s)",
        min_value=0.0,
        max_value=max(10.0, max_time + 2.0),
        value=float(min(cursor.simulator_time_s, max(10.0, max_time + 2.0))),
        step=0.5,
        key="replay_seek_slider",
    )
    adv_delta = st.number_input(
        "Advance delta (s)",
        min_value=0.0,
        max_value=3600.0,
        value=0.5,
        step=0.5,
        key="replay_advance_delta",
    )

    btn_cols = st.columns(6)
    if btn_cols[0].button("PLAY", key="replay_play"):
        try:
            apply_play(engine)
            st.success("Playback state: playing")
        except Exception as exc:
            st.error(f"PLAY refused: {exc}")
    if btn_cols[1].button("PAUSE", key="replay_pause"):
        try:
            apply_pause(engine)
            st.success("Playback state: paused")
        except Exception as exc:
            st.error(f"PAUSE refused: {exc}")
    if btn_cols[2].button("STEP", key="replay_step_forward"):
        try:
            apply_step(engine, count=1, direction="forward")
            st.success("Stepped forward by 1")
        except Exception as exc:
            st.error(f"STEP refused: {exc}")
    if btn_cols[3].button("STEP BACK", key="replay_step_back"):
        try:
            apply_step(engine, count=1, direction="backward")
            st.success("Stepped backward by 1")
        except Exception as exc:
            st.error(f"STEP BACK refused: {exc}")
    if btn_cols[4].button("SEEK", key="replay_seek_button"):
        try:
            apply_seek(engine, target_time_s=float(seek_target))
            st.success(f"Seeked to {float(seek_target):.2f} s")
        except Exception as exc:
            st.error(f"SEEK refused: {exc}")
    if btn_cols[5].button("ADVANCE", key="replay_advance_button"):
        try:
            # ADVANCE only moves while PLAYING; otherwise it is an explicit no-op
            apply_advance(engine, delta_s=float(adv_delta))
            st.success(f"Advanced by {float(adv_delta):.2f} s (scaled by speed)")
        except Exception as exc:
            st.error(f"ADVANCE refused: {exc}")

    # Also provide a bounded window load button that re-reads
    if st.button("Load window", key="replay_load_window"):
        try:
            loaded = load_time_window(
                engine,
                float(ws_input),
                float(we_input),
                max_events=int(max_events_input),
            )
            st.success(
                f"Loaded {len(loaded)} events in window [{float(ws_input):.2f}, {float(we_input):.2f}]"  # noqa: E501
            )
        except Exception as exc:
            st.error(f"Load window refused: {exc}")

    # Event timeline
    st.subheader("Event timeline")
    st.caption(
        "Only event types genuinely present in the stream are listed; others are unavailable."
    )
    st.markdown(
        f"**Present event types:** {', '.join(str(t.value) for t in view.present_event_types) or '—'}"  # noqa: E501
    )
    if view.unavailable_event_types:
        st.markdown(
            f"**Unavailable event types:** {', '.join(str(t.value) for t in view.unavailable_event_types)}"  # noqa: E501
        )
    # Full timeline up to window limit
    timeline_events = view.window_events
    if timeline_events:
        st.dataframe(
            [_format_event_row(ev) for ev in timeline_events],
            hide_index=True,
            width="stretch",
        )
    else:
        if view.is_empty or view.is_aggregate_only:
            st.caption(
                "No timeline — stream carries no events (truthful empty/aggregate-only state)."
            )
        else:
            st.caption("Timeline is empty for the current cursor window.")

    # Selected entity details
    st.subheader("Selected entity details")
    if view.stream.events:
        options = [ev.event_id for ev in view.stream.events]
        chosen = st.selectbox(
            "Select event",
            options=options,
            index=min(cursor.index, len(options) - 1) if not cursor.is_at_end else 0,
            key="replay_selected_event",
        )
        if chosen:
            st.session_state[_SELECTED_EVENT_KEY] = str(chosen)
            # Render details for chosen
            chosen_event = next(
                (ev for ev in view.stream.events if ev.event_id == str(chosen)), None
            )
            if chosen_event is not None:
                st.json(
                    {
                        "event_id": chosen_event.event_id,
                        "event_type": str(chosen_event.event_type),
                        "simulator_time_s": chosen_event.simulator_time_s,
                        "sequence": chosen_event.sequence,
                        "entity": {
                            "kind": str(chosen_event.entity.kind),
                            "entity_id": chosen_event.entity.entity_id,
                        },
                        "source": {
                            "source_id": chosen_event.source.source_id,
                            "source_kind": str(chosen_event.source.source_kind),
                            "artifact_sha256": chosen_event.source.artifact_sha256,
                        },
                        "provenance": {
                            "source_artifact_sha256": chosen_event.provenance.source_artifact_sha256,  # noqa: E501
                            "source_record_id": chosen_event.provenance.source_record_id,
                            "adapter_id": chosen_event.provenance.adapter_id,
                            "adapter_version": chosen_event.provenance.adapter_version,
                        },
                        "evidence_standing": str(chosen_event.evidence_standing.value),
                        "payload": chosen_event.payload.model_dump(mode="json"),
                    }
                )
                # truthful source/evidence/provenance captions
                st.caption(
                    f"Evidence standing: {chosen_event.evidence_standing.value} · "
                    f"Provenance record: {chosen_event.provenance.source_record_id} · "
                    f"Adapter: {chosen_event.provenance.adapter_id}"
                )
    else:
        st.caption("No entity details — empty stream carries no selectable events.")

    # Truthful unavailable panels for absent telemetry
    st.subheader("Telemetry availability")
    # Map specific unavailable types to panels
    absent = set(view.unavailable_event_types)
    if EventType.EXECUTION_TARGET in absent:
        render_unavailable_panel(
            "Execution target is unavailable",
            ["execution_target event class not present in this stream"],
            ["EXECUTION_TARGET_UNAVAILABLE"],
        )
    else:
        st.caption("Execution target telemetry is present for this stream.")
    if EventType.RESOURCE_STATE in absent:
        render_unavailable_panel(
            "Resource state is unavailable",
            ["resource_state event class not present in this stream"],
            ["RESOURCE_STATE_UNAVAILABLE"],
        )
    else:
        st.caption("Resource state telemetry is present for this stream.")
    if EventType.TASK_FORWARD in absent:
        render_unavailable_panel(
            "Task forwarding is unavailable",
            ["task_forward event class not present in this stream"],
            ["TASK_FORWARD_UNAVAILABLE"],
        )
    else:
        st.caption("Task forwarding telemetry is present for this stream.")
    if EventType.DEADLINE_OUTCOME in absent:
        render_unavailable_panel(
            "Deadline outcome is unavailable",
            ["deadline_outcome event class not present in this stream"],
            ["DEADLINE_OUTCOME_UNAVAILABLE"],
        )
    else:
        st.caption("Deadline outcome telemetry is present for this stream.")
    if EventType.TASK_ADMISSION in absent:
        render_unavailable_panel(
            "Task admission is unavailable",
            ["task_admission event class not present in this stream"],
            ["TASK_ADMISSION_UNAVAILABLE"],
        )
    else:
        st.caption("Task admission telemetry is present for this stream.")

    # Truthful aggregate/empty handling demo buttons
    st.subheader("Empty and aggregate truthfulness")
    agg_cols = st.columns(2)
    if agg_cols[0].button("Load aggregate-only demo", key="replay_load_aggregate"):
        try:
            agg_stream = build_aggregate_only_declaration()
            agg_engine = create_engine(agg_stream)
            st.session_state[_ENGINE_KEY] = agg_engine
            st.success("Loaded aggregate-only declaration — zero events, no telemetry synthesised.")
            st.rerun()
        except Exception as exc:
            st.error(f"Aggregate demo refused: {exc}")
    if agg_cols[1].button("Reload synthetic engineering fixture", key="replay_reload_synthetic"):
        try:
            syn = build_synthetic_engineering_stream()
            st.session_state[_ENGINE_KEY] = create_engine(syn)
            st.success("Reloaded synthetic engineering fixture.")
            st.rerun()
        except Exception as exc:
            st.error(f"Reload refused: {exc}")

    # Side-by-side workflow — exact compatibility agreement only
    st.subheader("Side-by-side comparison")
    st.caption(
        "Side-by-side requires an exact compatibility agreement: common time basis "
        "(simulator_time_s), time units (seconds), schema version, identity namespace, "
        "declared present types, and explicit acknowledgement."
    )
    st.warning("synchronized visual replay is not causal evidence")
    st.info(f"Fixed causal disclaimer carried on every synchronized state: {SYNC_DISCLAIMER}")

    left_stream = build_synthetic_engineering_stream(stream_id="synthetic-engineering-001")
    right_stream = build_second_synthetic_stream(stream_id="synthetic-engineering-002")
    st.caption(
        f"Left fingerprint: `{left_stream.fingerprint()[:12]}...` · "
        f"Right fingerprint: `{right_stream.fingerprint()[:12]}...`"
    )

    compat_ack = st.checkbox(
        "I acknowledge compatibility: common time basis/unit/schema/identity namespace/declared types",  # noqa: E501
        value=False,
        key="replay_side_compat_ack",
    )
    identity_ns = st.text_input(
        "Identity namespace",
        value="replay-observatory",
        key="replay_side_identity_ns",
    )
    time_basis = st.selectbox(
        "Time basis",
        options=["simulator_time_s"],
        index=0,
        key="replay_side_time_basis",
    )
    time_units = st.selectbox(
        "Time units",
        options=["seconds", "s"],
        index=0,
        key="replay_side_time_units",
    )
    window_start_side = st.number_input(
        "Side-by-side window start (s)",
        min_value=0.0,
        max_value=100.0,
        value=0.0,
        step=0.5,
        key="replay_side_window_start",
    )
    window_end_side = st.number_input(
        "Side-by-side window end (s)",
        min_value=0.0,
        max_value=100.0,
        value=7.0,
        step=0.5,
        key="replay_side_window_end",
    )
    if st.button("Create side-by-side comparison", key="replay_create_side_by_side"):
        try:
            if time_basis != "simulator_time_s":
                raise ValueError("time_basis must be simulator_time_s")
            if time_units not in ("seconds", "s"):
                raise ValueError("time_units must be seconds")
            agreement = build_side_by_side_agreement(
                left_stream=left_stream,
                right_stream=right_stream,
                window_start_s=float(window_start_side),
                window_end_s=float(window_end_side),
                identity_namespace=str(identity_ns),
                compatibility_acknowledged=bool(compat_ack),
            )
            replay = create_side_by_side(left_stream, right_stream, agreement)
            state = get_side_by_side_state(replay)
            st.success(
                "Side-by-side comparison created — synchronization is not evidence of causality."
            )
            st.json(
                {
                    "agreement_fingerprint": agreement.fingerprint(),
                    "left_window_count": len(state.left_window),
                    "right_window_count": len(state.right_window),
                    "unavailable_left": [str(t.value) for t in state.unavailable_left_event_types],
                    "unavailable_right": [
                        str(t.value) for t in state.unavailable_right_event_types
                    ],
                    "causal_disclaimer": state.causal_disclaimer,
                }
            )
            st.caption("synchronized visual replay is not causal evidence")
            # Store for potential further inspection
            st.session_state["replay_side_state"] = state
        except Exception as exc:
            st.error(f"Side-by-side refused: {exc}")

    # Demonstrate truthful no fabrication: attempted task outcome synthesis is absent
    st.caption(
        "No execution RSUs, task outcomes, or Dynamic Resource/E3 semantics are "
        "manufactured by this observatory. Unavailable event types remain unavailable."
    )

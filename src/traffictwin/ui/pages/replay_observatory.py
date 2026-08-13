# ruff: noqa: E501
"""Replay Observatory — deterministic event replay over immutable streams."""

from __future__ import annotations

import math

import streamlit as st

from traffictwin.replay_observatory.engine import PlaybackState, ReplayEngine, ReplayEngineState
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


def _describe_relation(playhead_s: float, cursor_s: float) -> str:
    """Pure helper returning truthful relation copy; never prints a false inequality."""

    ph = float(playhead_s)
    cs = float(cursor_s)
    if abs(ph - cs) < 1e-9:
        return f"playhead and cursor coincide at {ph:.2f} s"
    if ph < cs:
        return f"playhead {ph:.2f} s precedes cursor event time {cs:.2f} s"
    return f"playhead {ph:.2f} s follows cursor event time {cs:.2f} s"


_ENGINE_KEY = "replay_observatory_engine"
_SIDE_LEFT_KEY = "replay_side_left_engine"
_SIDE_RIGHT_KEY = "replay_side_right_engine"
_SELECTED_EVENT_KEY = "replay_selected_event_id"
_WINDOW_START_KEY = "replay_window_start"
_WINDOW_END_KEY = "replay_window_end"
_LAST_RECEIPT_KEY = "replay_last_receipt"
_LAST_BEFORE_KEY = "replay_last_before_state"


def _ensure_engine() -> ReplayEngine:
    cached = st.session_state.get(_ENGINE_KEY)
    if isinstance(cached, ReplayEngine):
        return cached
    stream = build_synthetic_engineering_stream()
    engine = create_engine(stream)
    st.session_state[_ENGINE_KEY] = engine
    return engine


def _format_event_row(event: object) -> dict[str, object]:
    return {
        "event_id": getattr(event, "event_id", ""),
        "event_type": str(getattr(event, "event_type", "")),
        "simulator_time_s": getattr(event, "simulator_time_s", 0.0),
        "sequence": getattr(event, "sequence", 0),
        "entity_id": getattr(getattr(event, "entity", None), "entity_id", ""),
        "entity_kind": str(getattr(getattr(event, "entity", None), "kind", "")),
        "source_id": getattr(getattr(event, "source", None), "source_id", ""),
    }


def _describe_receipt(receipt: object, before: ReplayEngineState | None) -> tuple[str, str]:
    """Derive a truthful banner from the canonical receipt/resulting_state."""

    try:
        req = getattr(receipt, "request", None)
        rs: ReplayEngineState | None = getattr(receipt, "resulting_state", None)
        if req is None or rs is None:
            return "info", str(receipt)
        control = str(getattr(req, "control", ""))
        # Speed change via apply_speed reuses PLAY/PAUSE with speed_multiplier; detect speed delta
        req_speed = getattr(req, "speed_multiplier", None)
        before_speed = before.speed_multiplier if before is not None else None
        speed_changed = (
            req_speed is not None and before_speed is not None and req_speed != before_speed
        )
        # Generic speed banner when speed changed regardless of control
        if speed_changed and rs is not None:
            return (
                "success",
                f"Speed set to {rs.speed_multiplier:g}x — playback {rs.playback_state.value}, "
                f"playhead {rs.playhead_time_s:.2f} s, cursor {rs.cursor.index}/{rs.cursor.total_events} "
                f"at {rs.cursor.simulator_time_s:.2f} s (event time)",
            )
        if control == "play":
            if rs.empty_stream:
                return (
                    "info",
                    f"PLAY unavailable — empty stream has zero events; state remains ENDED "
                    f"(no-op, playhead {rs.playhead_time_s:.2f} s, cursor 0/0)",
                )
            # aggregate-only is also empty_stream; above covers
            if before is not None and before.end_of_stream and rs.end_of_stream:
                return (
                    "info",
                    f"PLAY no-op — already at end (cursor {rs.cursor.index}/{rs.cursor.total_events}, "
                    f"ENDED; playhead {rs.playhead_time_s:.2f} s)",
                )
            if rs.playback_state is PlaybackState.PLAYING:
                return (
                    "success",
                    f"Playback state: playing — playhead {rs.playhead_time_s:.2f} s, "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {rs.cursor.simulator_time_s:.2f} s, "
                    f"speed {rs.speed_multiplier:g}x",
                )
            if rs.playback_state is PlaybackState.ENDED:
                return (
                    "info",
                    f"PLAY resulted in ENDED — stream at end or empty "
                    f"(cursor {rs.cursor.index}/{rs.cursor.total_events}, playhead {rs.playhead_time_s:.2f} s)",
                )
            return (
                "success",
                f"Playback state: {rs.playback_state.value} — playhead {rs.playhead_time_s:.2f} s",
            )
        if control == "pause":
            if rs.playback_state is PlaybackState.PAUSED:
                return (
                    "success",
                    f"Playback state: paused — playhead {rs.playhead_time_s:.2f} s, "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {rs.cursor.simulator_time_s:.2f} s",
                )
            if rs.playback_state is PlaybackState.ENDED:
                return (
                    "info",
                    f"PAUSE resulted in ENDED — empty or at end "
                    f"(cursor {rs.cursor.index}/{rs.cursor.total_events}, playhead {rs.playhead_time_s:.2f} s)",
                )
            return "success", f"Playback state: {rs.playback_state.value}"
        if control == "advance":
            delta = getattr(req, "advance_delta_s", 0.0)
            try:
                delta_f = float(delta) if delta is not None else 0.0
            except Exception:
                delta_f = 0.0
            if before is not None and before.playback_state is not PlaybackState.PLAYING:
                return (
                    "info",
                    f"ADVANCE no-op while {before.playback_state.value.upper()} — advancement requires PLAYING "
                    f"(delta {delta_f:.2f} s, speed {rs.speed_multiplier:g}x; "
                    f"playhead remains {rs.playhead_time_s:.2f} s, "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {rs.cursor.simulator_time_s:.2f} s)",
                )
            if delta_f == 0.0:
                return (
                    "info",
                    f"ADVANCE no-op — zero delta (playhead {rs.playhead_time_s:.2f} s, "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events})",
                )
            if before is not None and before.end_of_stream:
                return (
                    "info",
                    f"ADVANCE no-op — already ENDED (cursor {rs.cursor.index}/{rs.cursor.total_events}, "
                    f"playhead {rs.playhead_time_s:.2f} s)",
                )
            before_ph = before.playhead_time_s if before is not None else 0.0
            before_idx = before.cursor.index if before is not None else 0
            if rs.playhead_time_s == before_ph and rs.cursor.index == before_idx:
                return (
                    "info",
                    f"ADVANCE no-op — no progress (playhead {rs.playhead_time_s:.2f} s, "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events})",
                )
            if rs.end_of_stream and before is not None and not before.end_of_stream:
                return (
                    "success",
                    f"Advanced to end — playhead clamped to {rs.playhead_time_s:.2f} s "
                    f"(cursor {rs.cursor.index}/{rs.cursor.total_events}, ENDED)",
                )
            return (
                "success",
                f"Advanced by {delta_f:.2f} s (scaled by speed {rs.speed_multiplier:g}x) — "
                f"playhead {rs.playhead_time_s:.2f} s, cursor {rs.cursor.index}/{rs.cursor.total_events} "
                f"at {rs.cursor.simulator_time_s:.2f} s, playback {rs.playback_state.value}",
            )
        if control == "step":
            direction = str(getattr(req, "step_direction", "forward"))
            count = getattr(req, "step_count", 1)
            if before is not None and before.cursor.is_at_end and rs.cursor.is_at_end:
                return (
                    "info",
                    f"STEP {direction} no-op — already at end "
                    f"(cursor {rs.cursor.index}/{rs.cursor.total_events}, ENDED; playhead {rs.playhead_time_s:.2f} s)",
                )
            if before is not None and before.cursor.index == rs.cursor.index:
                return (
                    "info",
                    f"STEP {direction} no-op — cursor unchanged at {rs.cursor.index}/{rs.cursor.total_events} "
                    f"(playhead {rs.playhead_time_s:.2f} s)",
                )
            b_idx = before.cursor.index if before is not None else -1
            return (
                "success",
                f"Stepped {direction} by {count} — cursor {b_idx}→{rs.cursor.index}/{rs.cursor.total_events} "
                f"at {rs.cursor.simulator_time_s:.2f} s, playhead {rs.playhead_time_s:.2f} s, "
                f"playback {rs.playback_state.value}",
            )
        if control == "seek":
            target = getattr(req, "target_time_s", rs.playhead_time_s)
            try:
                t_f = float(target) if target is not None else rs.playhead_time_s
            except Exception:
                t_f = rs.playhead_time_s
            cursor_t = float(rs.cursor.simulator_time_s)
            playhead_t = float(rs.playhead_time_s)
            if abs(cursor_t - playhead_t) < 1e-9:
                return (
                    "success",
                    f"Seeked to {t_f:.2f} s — playhead {playhead_t:.2f} s (requested/accumulated), "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {cursor_t:.2f} s "
                    f"(event time) — playhead and cursor coincide at {playhead_t:.2f} s (exact-event seek)",
                )
            if playhead_t < cursor_t:
                return (
                    "success",
                    f"Seeked to {t_f:.2f} s — playhead {playhead_t:.2f} s (requested/accumulated), "
                    f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {cursor_t:.2f} s "
                    f"(event time) — distinct; playhead {playhead_t:.2f} s precedes cursor event time {cursor_t:.2f} s "
                    f"(SEEK target falls before selected next event)",
                )
            return (
                "success",
                f"Seeked to {t_f:.2f} s — playhead {playhead_t:.2f} s (requested/accumulated), "
                f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {cursor_t:.2f} s "
                f"(event time) — distinct; playhead {playhead_t:.2f} s follows cursor event time {cursor_t:.2f} s "
                f"(SEEK target lies after final event)",
            )
        # fallback
        return (
            "success",
            f"{control.upper()} — playback {rs.playback_state.value}, playhead {rs.playhead_time_s:.2f} s, "
            f"cursor {rs.cursor.index}/{rs.cursor.total_events} at {rs.cursor.simulator_time_s:.2f} s",
        )
    except Exception as exc:
        return "error", f"Receipt banner failed: {exc}"


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
    # Scoped synthetic disclaimer placeholder — filled after view to avoid claiming
    # DESIGN-ONLY when aggregate-only mode is active.
    _synthetic_disclaimer_ph = st.empty()

    engine = _ensure_engine()

    # ---- Controls mutating engine BEFORE view, so same render shows post-action state ----
    st.subheader("Replay controls")
    st.caption(
        "Controls are deterministic and explicit — no background real-time execution occurs."
    )

    speed_options = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
    try:
        _cur_state = engine.state()
        cur_speed = _cur_state.speed_multiplier
    except Exception:
        cur_speed = 1.0
    speed_idx = 3
    try:
        speed_idx = speed_options.index(cur_speed)
    except ValueError:
        speed_idx = 3
    chosen_speed = st.select_slider(
        "Speed multiplier",
        options=speed_options,
        value=speed_options[speed_idx],
        format_func=lambda v: f"{v:g}x",
        key="replay_speed_slider",
    )
    pending_receipt = None
    pending_before: ReplayEngineState | None = None
    if chosen_speed != cur_speed:
        try:
            before = engine.state()
            receipt = apply_speed(engine, speed_multiplier=float(chosen_speed))
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"Speed change refused: {exc}")

    # Compute time range for seek from engine directly
    max_time = 0.0
    if engine.stream.events:
        max_time = float(max(ev.simulator_time_s for ev in engine.stream.events))
    # Use playhead time for default seek target derived from engine state (pre-action slider default).
    try:
        _st = engine.state()
        default_seek = float(min(_st.playhead_time_s, max(10.0, max_time + 2.0)))
    except Exception:
        default_seek = 0.0
    seek_target = st.slider(
        "Seek target time (s)",
        min_value=0.0,
        max_value=max(10.0, max_time + 2.0),
        value=float(default_seek),
        step=0.5,
        key="replay_seek_slider",
    )
    # Placeholder for post-action seek caption — filled after view construction to avoid
    # labelling pre-action values as current cursor/playhead time.
    _seek_caption_ph = st.empty()
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
            before = engine.state()
            receipt = apply_play(engine)
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"PLAY refused: {exc}")
    if btn_cols[1].button("PAUSE", key="replay_pause"):
        try:
            before = engine.state()
            receipt = apply_pause(engine)
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"PAUSE refused: {exc}")
    if btn_cols[2].button("STEP", key="replay_step_forward"):
        try:
            before = engine.state()
            receipt = apply_step(engine, count=1, direction="forward")
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"STEP refused: {exc}")
    if btn_cols[3].button("STEP BACK", key="replay_step_back"):
        try:
            before = engine.state()
            receipt = apply_step(engine, count=1, direction="backward")
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"STEP BACK refused: {exc}")
    if btn_cols[4].button("SEEK", key="replay_seek_button"):
        try:
            before = engine.state()
            receipt = apply_seek(engine, target_time_s=float(seek_target))
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"SEEK refused: {exc}")
    if btn_cols[5].button("ADVANCE", key="replay_advance_button"):
        try:
            before = engine.state()
            receipt = apply_advance(engine, delta_s=float(adv_delta))
            pending_receipt = receipt
            pending_before = before
        except Exception as exc:
            st.error(f"ADVANCE refused: {exc}")

    # Persist last receipt for rerun visibility (aggregate reload already reruns)
    if pending_receipt is not None:
        st.session_state[_LAST_RECEIPT_KEY] = pending_receipt
        if pending_before is not None:
            st.session_state[_LAST_BEFORE_KEY] = pending_before

    # ---- Build canonical view AFTER controls — same render shows post-action state ----
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

    # Ensure selected-event state rendered is post-action: prefer widget's current value
    # over stale session key, then verify against post-action view.
    _widget_selected = st.session_state.get("replay_selected_event")
    if isinstance(_widget_selected, str) and _widget_selected:
        selected_id = _widget_selected
    else:
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

    # Fill post-action placeholders (scope synthetic disclaimer and seek caption to verified view)
    if view.is_aggregate_only:
        _synthetic_disclaimer_ph.caption(
            "Aggregate-only declaration — zero events, no telemetry synthesised; "
            "evidence standing is SYNTHETIC DATA (aggregate), not DESIGN-ONLY. "
            "Synthetic engineering fixture (when loaded) is DESIGN-ONLY CAPABILITY."
        )
    else:
        _synthetic_disclaimer_ph.caption(
            "Evidence standing for the synthetic engineering fixture (currently loaded stream "
            f"{view.stream.stream_id}) is DESIGN-ONLY CAPABILITY — not Manchester observation."
        )
    # Seek-target caption rendered from post-action view (not pre-action _st)
    _cursor_t_post = float(view.cursor.simulator_time_s)
    _playhead_t_post = float(view.engine_state.playhead_time_s)
    _relation_post = _describe_relation(_playhead_t_post, _cursor_t_post)
    if abs(_cursor_t_post - _playhead_t_post) < 1e-9:
        _seek_caption_ph.caption(
            f"Seek target {seek_target:.2f} s — cursor event time {_cursor_t_post:.2f} s and "
            f"playhead time {_playhead_t_post:.2f} s — {_relation_post}"
        )
    else:
        _seek_caption_ph.caption(
            f"Seek target {seek_target:.2f} s — cursor event time {_cursor_t_post:.2f} s vs "
            f"playhead time {_playhead_t_post:.2f} s — distinct; {_relation_post}"
        )

    # Truthful receipt banner derived from canonical receipt/resulting_state
    # Show banner for this run's pending receipt, or persisted last receipt if still current
    display_receipt = (
        pending_receipt if pending_receipt is not None else st.session_state.get(_LAST_RECEIPT_KEY)
    )
    display_before = (
        pending_before if pending_before is not None else st.session_state.get(_LAST_BEFORE_KEY)
    )
    if display_receipt is not None:
        # Only show if receipt still matches current engine state (exact live binding would pass)
        try:
            # Verify coherence without raising: check fingerprint etc.
            rs = getattr(display_receipt, "resulting_state", None)
            if rs is not None and rs.stream_fingerprint == engine.stream_fingerprint:
                # Also check speed/playhead/cursor match current engine to avoid stale banner
                cur = engine.state()
                if (
                    rs.cursor == cur.cursor
                    and rs.playhead_time_s == cur.playhead_time_s
                    and rs.playback_state == cur.playback_state
                    and rs.speed_multiplier == cur.speed_multiplier
                ):
                    kind, text = _describe_receipt(display_receipt, display_before)
                    if kind == "success":
                        st.success(text)
                    elif kind == "error":
                        st.error(text)
                    else:
                        st.info(text)
                else:
                    st.warning(
                        "Receipt state mismatch — banner withheld: receipt no longer matches live engine state"
                    )
            else:
                st.warning("Receipt state mismatch — banner withheld: stream fingerprint mismatch")
        except Exception:
            st.error(
                "Receipt banner error — receipt/state coherence check failed (withheld without leaking internals)"
            )

    # Source / evidence / provenance — derived ONLY from currently loaded stream/manifest
    st.subheader("Source and evidence")
    manifest = view.stream.capability_manifest
    cols = st.columns(4)
    cols[0].metric("Stream ID", view.stream.stream_id)
    cols[1].metric("Source ID", manifest.source.source_id)
    cols[2].metric("Evidence standing", manifest.evidence_standing.value)
    cols[3].metric("Source kind", manifest.source.source_kind.value)
    st.caption(f"Artifact SHA-256: `{manifest.source.artifact_sha256}`")
    st.caption(
        f"Schema version: `{manifest.source.schema_version}` · Stream fingerprint: `{view.engine_state.stream_fingerprint[:16]}...`"
    )
    st.markdown(f"Source ID: `{manifest.source.source_id}` · Stream ID: `{view.stream.stream_id}`")
    st.caption(
        f"Evidence standing: {manifest.evidence_standing.value} · Source kind: {manifest.source.source_kind.value}"
    )
    # Provenance caption derived from currently loaded stream only
    if view.stream.events:
        # Derive from actual loaded events, not hardcoded fixture
        exemplar = view.stream.events[0]
        st.caption(
            f"Provenance adapter: {exemplar.provenance.adapter_id} · "
            f"Source record example: {exemplar.provenance.source_record_id} — "
            f"derived from currently loaded stream ({view.stream.stream_id})"
        )
        st.caption(
            "Source record IDs in loaded stream: "
            + ", ".join(f"`{ev.provenance.source_record_id}`" for ev in view.stream.events[:3])
            + (" …" if len(view.stream.events) > 3 else "")
        )
    else:
        st.caption(
            "Provenance: Unavailable — aggregate-only/empty stream has no event provenance "
            "(zero events, derived from currently loaded stream)"
        )
        st.caption("Adapter ID: Unavailable — no events in currently loaded stream")
        st.caption("Source record ID: Unavailable — no events in currently loaded stream")
    st.markdown("**Limitations:**")
    for lim in manifest.limitations:
        st.markdown(f"- {lim}")
    for lim in view.stream.limitations:
        if lim not in manifest.limitations:
            st.markdown(f"- {lim}")

    # Simulation clock — cursor event time vs playhead time distinctly labelled
    st.subheader("Simulation clock")
    cursor = view.cursor
    state = view.engine_state
    clock_cols = st.columns(5)
    clock_cols[0].metric("Cursor event time", f"{cursor.simulator_time_s:.2f} s")
    clock_cols[1].metric("Playhead time", f"{state.playhead_time_s:.2f} s")
    clock_cols[2].metric("Cursor index", f"{cursor.index}/{cursor.total_events}")
    clock_cols[3].metric("Playback state", state.playback_state.value)
    clock_cols[4].metric("Speed", f"{state.speed_multiplier:g}x")
    _clock_relation = _describe_relation(
        float(state.playhead_time_s), float(cursor.simulator_time_s)
    )
    if abs(float(cursor.simulator_time_s) - float(state.playhead_time_s)) < 1e-9:
        st.caption(
            f"Cursor event time (selected event): {cursor.simulator_time_s:.2f} s · "
            f"Playhead time (requested/accumulated): {state.playhead_time_s:.2f} s — "
            f"{_clock_relation}"
        )
    else:
        st.caption(
            f"Cursor event time (selected event): {cursor.simulator_time_s:.2f} s · "
            f"Playhead time (requested/accumulated): {state.playhead_time_s:.2f} s — "
            f"distinct; {_clock_relation}; playhead drives ADVANCE, cursor selects event"
        )
    st.caption(
        f"Simulator time: {cursor.simulator_time_s:.2f} s · Playhead time: {state.playhead_time_s:.2f} s · "
        f"Cursor index: {cursor.index}/{cursor.total_events} · Playback state: {state.playback_state.value}"
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
    st.caption(
        f"Bounded window [{float(ws_input):.2f}, {float(we_input):.2f}] s — "
        f"filtered view (max {int(max_events_input)} events), never synthesises events; "
        f"Timeline window starts at cursor — index {cursor.index} at {cursor.simulator_time_s:.2f} s (event time)"
    )
    window_display: tuple[object, ...] = ()
    try:
        window_display = load_time_window(
            engine,
            float(ws_input),
            float(we_input),
            max_events=int(max_events_input),
        )
    except Exception as exc:
        st.error(f"Window load refused: {exc}")
        window_display = ()

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
                f"Loaded {len(loaded)} events in window [{float(ws_input):.2f}, {float(we_input):.2f}]"
            )
        except Exception as exc:
            st.error(f"Load window refused: {exc}")

    # Event timeline — window starts at cursor, distinct from bounded window controls
    st.subheader("Event timeline")
    st.caption(
        "Only event types genuinely present in the stream are listed; others are unavailable."
    )
    _timeline_relation = _describe_relation(
        float(state.playhead_time_s), float(cursor.simulator_time_s)
    )
    if abs(float(cursor.simulator_time_s) - float(state.playhead_time_s)) < 1e-9:
        st.caption(
            f"Timeline window starts at cursor — index {cursor.index} ({cursor.simulator_time_s:.2f} s) — "
            f"showing up to 200 events from cursor forward ({_timeline_relation})"
        )
    else:
        st.caption(
            f"Timeline window starts at cursor — index {cursor.index} ({cursor.simulator_time_s:.2f} s) — "
            f"showing up to 200 events from cursor forward (distinct; {_timeline_relation})"
        )
    st.markdown(
        f"**Present event types:** {', '.join(str(t.value) for t in view.present_event_types) or '—'}"
    )
    if view.unavailable_event_types:
        st.markdown(
            f"**Unavailable event types:** {', '.join(str(t.value) for t in view.unavailable_event_types)}"
        )
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
                            "source_artifact_sha256": chosen_event.provenance.source_artifact_sha256,
                            "source_record_id": chosen_event.provenance.source_record_id,
                            "adapter_id": chosen_event.provenance.adapter_id,
                            "adapter_version": chosen_event.provenance.adapter_version,
                        },
                        "evidence_standing": str(chosen_event.evidence_standing.value),
                        "payload": chosen_event.payload.model_dump(mode="json"),
                    }
                )
                st.caption(
                    f"Evidence standing: {chosen_event.evidence_standing.value} · "
                    f"Provenance record: {chosen_event.provenance.source_record_id} · "
                    f"Adapter: {chosen_event.provenance.adapter_id} — "
                    f"derived from currently loaded stream"
                )
    else:
        st.caption("No entity details — empty stream carries no selectable events.")

    # Truthful unavailable panels for absent telemetry
    st.subheader("Telemetry availability")
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
            # Clear last receipt to avoid stale banner tied to previous stream fingerprint
            st.session_state.pop(_LAST_RECEIPT_KEY, None)
            st.session_state.pop(_LAST_BEFORE_KEY, None)
            st.success("Loaded aggregate-only declaration — zero events, no telemetry synthesised.")
            st.rerun()
        except Exception as exc:
            st.error(f"Aggregate demo refused: {exc}")
    if agg_cols[1].button("Reload synthetic engineering fixture", key="replay_reload_synthetic"):
        try:
            syn = build_synthetic_engineering_stream()
            st.session_state[_ENGINE_KEY] = create_engine(syn)
            st.session_state.pop(_LAST_RECEIPT_KEY, None)
            st.session_state.pop(_LAST_BEFORE_KEY, None)
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
    st.caption(
        "Time basis: simulator_time_s (fixed) · Time units: seconds (fixed) — exact agreement required"
    )

    left_stream = build_synthetic_engineering_stream(stream_id="synthetic-engineering-001")
    right_stream = build_second_synthetic_stream(stream_id="synthetic-engineering-002")
    # Exact stream identities side-by-side (never borrowed)
    left_manifest = left_stream.capability_manifest
    right_manifest = right_stream.capability_manifest
    id_cols = st.columns(2)
    id_cols[0].markdown(
        f"**Left stream** — ID: `{left_stream.stream_id}` · Source: `{left_manifest.source.source_id}` "
        f"(`{left_manifest.source.source_kind.value}`) · Evidence: `{left_manifest.evidence_standing.value}` · "
        f"Fingerprint: `{left_stream.fingerprint()[:12]}...`"
    )
    id_cols[1].markdown(
        f"**Right stream** — ID: `{right_stream.stream_id}` · Source: `{right_manifest.source.source_id}` "
        f"(`{right_manifest.source.source_kind.value}`) · Evidence: `{right_manifest.evidence_standing.value}` · "
        f"Fingerprint: `{right_stream.fingerprint()[:12]}...`"
    )
    st.caption(
        f"Left fingerprint: `{left_stream.fingerprint()[:12]}...` · "
        f"Right fingerprint: `{right_stream.fingerprint()[:12]}...`"
    )

    compat_ack = st.checkbox(
        "I acknowledge compatibility: common time basis/unit/schema/identity namespace/declared types",
        value=False,
        key="replay_side_compat_ack",
    )
    identity_ns = st.text_input(
        "Identity namespace",
        value="replay-observatory",
        key="replay_side_identity_ns",
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
            agreement = build_side_by_side_agreement(
                left_stream=left_stream,
                right_stream=right_stream,
                window_start_s=float(window_start_side),
                window_end_s=float(window_end_side),
                identity_namespace=str(identity_ns),
                compatibility_acknowledged=bool(compat_ack),
            )
            replay = create_side_by_side(left_stream, right_stream, agreement)
            state_side = get_side_by_side_state(replay)
            st.success(
                "Side-by-side comparison created — synchronization is not evidence of causality."
            )
            st.json(
                {
                    "agreement_fingerprint": agreement.fingerprint(),
                    "left_stream_id": left_stream.stream_id,
                    "right_stream_id": right_stream.stream_id,
                    "left_source_id": left_manifest.source.source_id,
                    "right_source_id": right_manifest.source.source_id,
                    "left_window_count": len(state_side.left_window),
                    "right_window_count": len(state_side.right_window),
                    "unavailable_left": [
                        str(t.value) for t in state_side.unavailable_left_event_types
                    ],
                    "unavailable_right": [
                        str(t.value) for t in state_side.unavailable_right_event_types
                    ],
                    "causal_disclaimer": state_side.causal_disclaimer,
                }
            )
            st.caption("synchronized visual replay is not causal evidence")
            st.session_state["replay_side_state"] = state_side
        except Exception as exc:
            st.error(f"Side-by-side refused: {exc}")

    st.caption(
        "No execution RSUs, task outcomes, or Dynamic Resource/E3 semantics are "
        "manufactured by this observatory. Unavailable event types remain unavailable."
    )

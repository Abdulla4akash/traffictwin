# ruff: noqa: E501
"""AppTest for Replay Observatory — controls, truthfulness, side-by-side, and no fabrication."""

from __future__ import annotations

import pathlib
from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

_ENV_CLEAR = [
    "TRAFFICTWIN_WORKSPACE_PATH",
    "TRAFFICTWIN_REGISTRY_PATH",
    "TRAFFICTWIN_TOS_DATA_PATH",
    "TRAFFICTWIN_FIXTURE_PATH",
    "TRAFFICTWIN_RANDY_PACK_PATH",
]


def _app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file(
        pathlib.Path(__file__).resolve().parents[2]
        / "src/traffictwin/ui/app_pages/replay_observatory.py"
    )
    try:
        from traffictwin.ui.state import default_session_state, load_ui_config

        state = deepcopy(default_session_state(load_ui_config()))
        state["_v07_navigation_active"] = True
        for k, v in state.items():
            app.session_state[k] = v
    except Exception:  # noqa: S110
        pass
    app.run(timeout=30)
    return app


def _text(app: AppTest) -> str:
    parts: list[str] = []
    for coll in (
        app.title,
        app.header,
        app.subheader,
        app.markdown,
        app.caption,
        app.info,
        app.warning,
        app.success,
        app.error,
        app.text,
    ):
        try:
            for item in coll:
                parts.append(str(getattr(item, "value", "")))
        except Exception:  # noqa: S112
            continue
    return " ".join(parts)


def _metric(app: AppTest, label: str) -> str | None:
    for m in app.metric:
        if label in str(getattr(m, "label", "")):
            return str(getattr(m, "value", ""))
    return None


def test_page_has_one_h1(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception, f"page raised: {app.exception}"
    assert len(app.title) == 1
    assert app.title[0].value == "Replay Observatory"


def test_page_shows_fixed_disclaimers_before_results(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "synchronized visual replay is not causal evidence" in joined.lower()
    assert "SYNTHETIC ENGINEERING" in joined
    assert "DESIGN-ONLY" in joined
    assert "not Manchester observation" in joined.lower() or "Not Manchester observation" in joined
    assert "not admitted task-level research evidence" in joined.lower()


def test_page_shows_source_evidence_and_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Source and evidence" in joined
    assert "Source ID" in joined or "source_id" in joined.lower()
    assert "Evidence standing" in joined
    assert "DESIGN-ONLY CAPABILITY" in joined
    assert "Artifact SHA-256" in joined or "artifact_sha256" in joined.lower()
    assert "Provenance" in joined or "provenance" in joined.lower()
    # Derived from currently loaded stream, not hardcoded generic
    assert "derived from currently loaded stream" in joined
    # Initial synthetic fixture should expose adapter and record derived from stream
    assert "synthetic-engineering-adapter" in joined
    assert "rec-sim-000" in joined or "rec-" in joined


def test_page_shows_simulation_clock_and_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Simulation clock" in joined
    # Cursor event time vs playhead time distinctly labelled; truthful relation
    assert "Cursor event time" in joined
    assert "Playhead time" in joined
    # Initial state is coincident (0/0); captions must truthfully say coincide, not claim gap
    assert "coincide" in joined.lower() or "distinct" in joined.lower()
    # Must show relation copy without false inequality
    assert (
        "playhead and cursor coincide" in joined.lower()
        or "precedes" in joined.lower()
        or "follows" in joined.lower()
    )
    assert "Cursor index" in joined or "cursor" in joined.lower()
    assert "Playback state" in joined
    assert "Event timeline" in joined
    assert "Present event types" in joined
    assert "Unavailable event types" in joined
    # Timeline window starts at cursor
    assert "Timeline window starts at cursor" in joined


def test_page_shows_truthful_unavailable_execution_and_resource_panels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Execution target is unavailable" in joined
    assert "Resource state is unavailable" in joined
    assert "Task forwarding is unavailable" in joined
    assert "Deadline outcome is unavailable" in joined
    assert "unavailable" in joined.lower()
    assert (
        "No execution RSUs" in joined
        or "manufactured" in joined.lower()
        or "not manufactured" in joined.lower()
        or "never synthesised" in joined.lower()
        or "no execution" in joined.lower()
    )


def test_page_controls_play_pause_step_seek_advance_speed_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "PLAY" in buttons
    assert "PAUSE" in buttons
    assert "STEP" in buttons
    assert "STEP BACK" in buttons
    assert "SEEK" in buttons
    assert "ADVANCE" in buttons
    sliders = [getattr(s, "label", "") for s in app.select_slider]
    assert any("Speed" in str(label) for label in sliders)
    seek_sliders = [getattr(s, "label", "") for s in app.slider]
    assert any("Seek" in str(label) for label in seek_sliders)


def test_play_pause_transitions_via_app(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    # Initially paused: verify metrics
    assert _metric(app, "Playback state") == "paused"
    play_btn = next(b for b in app.button if b.label == "PLAY")
    play_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    # Banner must be derived from receipt, not hardcoded, and mention playing with playhead/cursor
    assert "playing" in joined.lower()
    assert "playhead" in joined.lower()
    assert "cursor" in joined.lower()
    assert _metric(app, "Playback state") == "playing"
    pause_btn = next(b for b in app.button if b.label == "PAUSE")
    pause_btn.click().run(timeout=30)
    assert not app.exception
    joined2 = _text(app)
    assert "paused" in joined2.lower()
    assert "playhead" in joined2.lower()
    assert _metric(app, "Playback state") == "paused"


def test_advance_noop_while_paused_same_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """ADVANCE while PAUSED must be a pure no-op and banner must say so in same render."""

    app = _app(monkeypatch)
    assert not app.exception
    assert _metric(app, "Playback state") == "paused"
    cursor_before = _metric(app, "Cursor index")
    playhead_before = _metric(app, "Playhead time")
    assert cursor_before == "0/7"
    assert playhead_before == "0.00 s"
    adv_btn = next(b for b in app.button if b.label == "ADVANCE")
    adv_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    # Must explicitly state no-op and that PAUSED requires PLAYING, not claim advancement
    assert "ADVANCE no-op while PAUSED" in joined
    assert "requires PLAYING" in joined
    assert "playhead remains" in joined.lower()
    assert "Advanced by" not in joined or "no-op" in joined.lower()
    # Metrics must be unchanged in same render (lag fix)
    assert _metric(app, "Cursor index") == "0/7"
    assert _metric(app, "Playhead time") == "0.00 s"
    assert _metric(app, "Playback state") == "paused"
    # Must mention speed/cursor/playback/playhead consistently
    assert "cursor" in joined.lower()
    assert "playhead" in joined.lower()
    assert "speed" in joined.lower() or "1x" in joined


def test_play_aggregate_ended_truthful_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    """aggregate-only PLAY must remain ENDED and banner must not claim playing."""

    app = _app(monkeypatch)
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    assert not app.exception
    joined0 = _text(app)
    assert "aggregate-only" in joined0.lower()
    # Aggregate provenance must be Unavailable, not synthetic-engineering-adapter
    assert "Unavailable" in joined0
    # Evidence standing for aggregate is SYNTHETIC DATA, not DESIGN-ONLY (no borrowing)
    assert "SYNTHETIC DATA" in joined0
    # Metrics should show ENDED, 0/0
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Cursor index") == "0/0"
    # Click PLAY while aggregate ENDED
    play_btn = next(b for b in app.button if b.label == "PLAY")
    play_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "PLAY unavailable" in joined or "PLAY no-op" in joined
    assert "zero events" in joined.lower() or "empty" in joined.lower()
    assert "ENDED" in joined
    # Must NOT claim playing
    # Banner that claims "playing" without qualification would be a lie; check no success playing
    assert "Playback state: playing" not in joined
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Cursor index") == "0/0"


def test_step_at_end_noop_truthful(monkeypatch: pytest.MonkeyPatch) -> None:
    """STEP at end must be no-op with explicit banner, not claim stepped."""

    app = _app(monkeypatch)
    assert not app.exception
    # Drive to end via SEEK to beyond last time (synthetic last time 6.0, seek to 10)
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(10.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception
    joined_seek = _text(app)
    assert "Seeked to 10.00" in joined_seek
    assert "playhead" in joined_seek.lower()
    assert "cursor" in joined_seek.lower()
    # After seek beyond end, should be ENDED at 7/7
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Cursor index") == "7/7"
    # Now STEP forward at end must be no-op
    step_btn = next(b for b in app.button if b.label == "STEP")
    step_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "STEP" in joined
    assert "no-op" in joined.lower()
    assert "already at end" in joined.lower()
    assert "ENDED" in joined
    # Must not claim success stepping
    assert "Stepped forward by 1" not in joined
    assert _metric(app, "Cursor index") == "7/7"
    assert _metric(app, "Playback state") == "ended"


def test_step_and_seek_move_cursor_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    step_btn = next(b for b in app.button if b.label == "STEP")
    step_btn.click().run(timeout=30)
    assert not app.exception
    # Exact post-action assertion: cursor index must be 1/7 in same render
    assert _metric(app, "Cursor index") == "1/7"
    assert "Cursor event time" in _text(app)
    # Verify banner derived from receipt shows stepping
    joined = _text(app)
    assert "Stepped forward by 1" in joined
    assert "cursor 0→1/7" in joined or "cursor" in joined.lower()
    assert "playhead" in joined.lower()
    # Seek to 5.0 should land on simulation_time 5.0, index 5
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(5.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception
    joined2 = _text(app)
    assert "Seeked to 5.00" in joined2
    assert "playhead 5.00" in joined2.lower()
    assert "cursor 5/7" in joined2.lower() or "cursor" in joined2.lower()
    # Distinct playhead vs cursor event time must be shown
    assert "playhead" in joined2.lower() and "cursor" in joined2.lower()
    assert _metric(app, "Cursor index") == "5/7"


def test_speed_change_exact_same_render(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    assert _metric(app, "Speed") == "1x"
    slider = next(s for s in app.select_slider if "Speed" in str(getattr(s, "label", "")))
    slider.set_value(2.0).run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "Speed set to 2x" in joined
    assert "playhead" in joined.lower()
    assert "cursor" in joined.lower()
    assert "playback" in joined.lower()
    # Same render must show updated speed
    assert _metric(app, "Speed") == "2x"
    # Cursor/state same render consistency
    assert _metric(app, "Cursor index") is not None
    assert _metric(app, "Playback state") in ("paused", "playing", "ended")


def test_cursor_playhead_separate_labels_and_gap_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Cursor event time" in joined
    assert "Playhead time" in joined
    # Truthful relation caption: initial is coincide, gap seeks are distinct
    assert "coincide" in joined.lower() or "distinct" in joined.lower()
    assert (
        "playhead and cursor coincide" in joined.lower()
        or "precedes" in joined.lower()
        or "follows" in joined.lower()
    )
    # Metrics must exist separately
    assert _metric(app, "Cursor event time") is not None
    assert _metric(app, "Playhead time") is not None
    # After a gap seek (target 2.0 is before event at 2.5? actually synthetic has 1.0,2.5)
    # Seek to 2.0 lands on 2.5 event time but playhead is 2.0 -> distinct
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(2.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    joined2 = _text(app)
    assert "playhead 2.00" in joined2.lower()
    assert "cursor" in joined2.lower() and "2.50" in joined2
    # Distinct times shown in metrics and truthful relation is precedes
    assert "precedes" in joined2.lower(), f"gap 2.0 should say precedes, got {joined2}"
    # Must not falsely claim follows for this case
    # The distinct gap seek must not be described as follows
    assert "playhead 2.00 s follows" not in joined2.lower()
    cursor_t = _metric(app, "Cursor event time")
    playhead_t = _metric(app, "Playhead time")
    assert cursor_t != playhead_t
    assert playhead_t == "2.00 s"
    assert cursor_t == "2.50 s"


def test_bounded_window_load(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    for ni in app.number_input:
        if "Window start" in str(getattr(ni, "label", "")):
            ni.set_value(1.0).run(timeout=30)
            break
    for ni in app.number_input:
        if "Window end" in str(getattr(ni, "label", "")):
            ni.set_value(3.0).run(timeout=30)
            break
    load_btn = next(b for b in app.button if b.label == "Load window")
    load_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "Loaded" in joined or "events in window" in joined
    assert any("Window event count" in str(m.label) for m in app.metric)
    # Exact window count for [1.0,3.0] should be 3
    wmc = next((m for m in app.metric if "Window event count" in str(m.label)), None)
    assert wmc is not None
    assert str(wmc.value) == "3"


def test_selected_entity_details_present(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Selected entity details" in joined
    selectors = [b for b in app.selectbox if "Select event" in str(getattr(b, "label", ""))]
    assert len(selectors) >= 1


def test_empty_and_aggregate_truthfulness_buttons_exist(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    buttons = [b.label for b in app.button]
    assert "Load aggregate-only demo" in buttons
    assert "Reload synthetic engineering fixture" in buttons


def test_aggregate_demo_shows_truthful_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "aggregate-only" in joined.lower()
    assert (
        "zero events" in joined.lower()
        or "no events" in joined.lower()
        or "empty stream" in joined.lower()
    )
    assert (
        "no telemetry" in joined.lower()
        or "no event" in joined.lower()
        or "not synthesised" in joined.lower()
    )
    # Must not borrow synthetic fixture provenance
    # When aggregate, synthetic adapter must not appear unless paired with Unavailable handling
    # The synthetic adapter string may appear in earlier metrics but aggregate provenance section must say Unavailable
    assert "Provenance: Unavailable" in joined
    assert "SYNTHETIC DATA" in joined


def test_aggregate_provenance_unavailable_not_borrowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provenance captions must be derived from loaded stream; aggregate must not borrow synthetic identities."""

    app = _app(monkeypatch)
    # Initial synthetic has provenance derived from stream
    joined0 = _text(app)
    assert "derived from currently loaded stream (synthetic-engineering-001)" in joined0
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    joined = _text(app)
    # Now aggregate: provenance must be Unavailable and must not claim synthetic adapter as current provenance
    assert "Provenance: Unavailable" in joined
    assert "Adapter ID: Unavailable" in joined
    assert "Source record ID: Unavailable" in joined
    # Evidence standing must be SYNTHETIC DATA for aggregate, not DESIGN-ONLY
    assert "SYNTHETIC DATA" in joined
    # Source kind must be RESEARCH_AGGREGATE for aggregate, derived truthfully
    assert "research_aggregate" in joined.lower() or "RESEARCH_AGGREGATE" in joined
    # Must not show synthetic-eng-001 as source when aggregate is loaded
    # The synthetic fixture's source_id should not be the displayed source for aggregate
    # Aggregate source is research-agg-001
    assert "research-agg-001" in joined
    # Reload synthetic and verify it restores correctly without borrowing aggregate identity
    reload_btn = next(b for b in app.button if b.label == "Reload synthetic engineering fixture")
    reload_btn.click().run(timeout=30)
    joined2 = _text(app)
    assert "synthetic-eng-001" in joined2
    assert "DESIGN-ONLY CAPABILITY" in joined2
    assert "synthetic-engineering-adapter" in joined2


def test_timeline_window_starts_at_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Timeline window starts at cursor" in joined
    # After stepping, caption must update to reflect new cursor
    step_btn = next(b for b in app.button if b.label == "STEP")
    step_btn.click().run(timeout=30)
    joined2 = _text(app)
    assert "Timeline window starts at cursor — index 1 at 1.00 s" in joined2
    # Verify timeline dataframe exists and matches bounded window from cursor
    assert any(
        "Timeline window starts at cursor" in str(getattr(c, "value", "")) for c in app.caption
    )


def test_time_units_not_inert(monkeypatch: pytest.MonkeyPatch) -> None:
    """Time units/basis must be fixed captions, not an inert editable selectbox."""

    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Time basis: simulator_time_s (fixed)" in joined
    assert "Time units: seconds (fixed)" in joined
    # No editable time-units control should exist (was previously inert)
    # Side-by-side should have no selectbox labelled Time units or Time basis
    time_selects = [
        s
        for s in app.selectbox
        if "Time units" in str(getattr(s, "label", ""))
        or "Time basis" in str(getattr(s, "label", ""))
    ]
    assert len(time_selects) == 0


def test_side_by_side_requires_acknowledgement_and_shows_disclaimer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "Side-by-side" in joined
    assert "synchronized visual replay is not causal evidence" in joined.lower()
    assert "Fixed causal disclaimer" in joined
    assert len(app.checkbox) >= 1
    assert any("I acknowledge compatibility" in str(c.label) for c in app.checkbox)
    assert any("Identity namespace" in str(i.label) for i in app.text_input)
    create_btn = next(b for b in app.button if b.label == "Create side-by-side comparison")
    create_btn.click().run(timeout=30)
    assert not app.exception
    joined2 = _text(app)
    assert (
        "refused" in joined2.lower()
        or "compatibility_acknowledged" in joined2.lower()
        or "must be explicitly True" in joined2
    )


def test_side_by_side_success_when_acknowledged(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    ack = next(c for c in app.checkbox if "I acknowledge compatibility" in str(c.label))
    ack.set_value(True).run(timeout=30)
    assert not app.exception
    create_btn = next(b for b in app.button if b.label == "Create side-by-side comparison")
    create_btn.click().run(timeout=30)
    assert not app.exception
    joined = _text(app)
    assert "Side-by-side comparison created" in joined
    assert "synchronization is not evidence of causality" in joined.lower()
    # Exact side-by-side stream identities must be shown side-by-side
    assert "Left stream" in joined and "Right stream" in joined
    assert "synthetic-engineering-001" in joined
    assert "synthetic-engineering-002" in joined
    assert "left_stream_id" in joined.lower() or "Left stream" in joined


def test_side_by_side_exact_stream_identities(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    ack = next(c for c in app.checkbox if "I acknowledge compatibility" in str(c.label))
    ack.set_value(True).run(timeout=30)
    create_btn = next(b for b in app.button if b.label == "Create side-by-side comparison")
    create_btn.click().run(timeout=30)
    joined = _text(app)
    assert "Left stream" in joined
    assert "Right stream" in joined
    assert "synthetic-eng-001" in joined
    assert "synthetic-eng-002" in joined
    # Fingerprints displayed side-by-side
    assert "Fingerprint" in joined
    # JSON must contain exact identities, not borrowed
    assert "synthetic-engineering-001" in joined
    assert "synthetic-engineering-002" in joined


def test_side_by_side_discriminating_refusal_invalid_declared_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service-level discriminating refusal: aggregate cannot declare event types — UI must reflect via service boundary."""

    # This tests the service contract directly via the page's imported service layer
    # Using the service shows aggregate declaration with events is refused
    from traffictwin.replay_observatory.models import EventType
    from traffictwin.ui.replay_observatory_service import (
        build_aggregate_only_declaration,
        build_side_by_side_agreement,
        build_synthetic_engineering_stream,
        create_side_by_side,
    )

    left = build_synthetic_engineering_stream()
    right = build_aggregate_only_declaration()
    # Attempting to declare event types for aggregate path must be refused
    try:
        agr = build_side_by_side_agreement(
            left_stream=left,
            right_stream=right,
            declared_event_types=(EventType.VEHICLE_STATE,),
        )
        create_side_by_side(left, right, agr)
        raise AssertionError("expected refusal for aggregate declaring events")
    except Exception as exc:
        msg = str(exc).lower()
        assert "aggregate" in msg or "event" in msg or "invention" in msg


def test_no_fabricated_task_telemetry_via_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discriminating test: synthetic fixture genuinely lacks execution/resource telemetry — not fabricated."""

    from traffictwin.replay_observatory.models import EventType
    from traffictwin.ui.replay_observatory_service import (
        build_synthetic_engineering_stream,
        create_engine,
        get_observatory_view,
    )

    stream = build_synthetic_engineering_stream()
    engine = create_engine(stream)
    view = get_observatory_view(engine)
    # Must be truthfully unavailable, not hidden fabrication
    assert EventType.EXECUTION_TARGET in view.unavailable_event_types
    assert EventType.RESOURCE_STATE in view.unavailable_event_types
    assert EventType.EXECUTION_TARGET not in view.present_event_types
    # No timeline events of those types
    for ev in view.window_events:
        assert ev.event_type not in (EventType.EXECUTION_TARGET, EventType.RESOURCE_STATE)
    # Page must also show unavailable panels (checked via AppTest)
    app = _app(monkeypatch)
    joined = _text(app)
    assert "Execution target is unavailable" in joined
    assert "Resource state is unavailable" in joined


def test_page_is_thin_no_canonical_logic(monkeypatch: pytest.MonkeyPatch) -> None:
    source = pathlib.Path("src/traffictwin/ui/pages/replay_observatory.py").read_text(
        encoding="utf-8"
    )
    assert "from traffictwin.ui.replay_observatory_service import" in source
    assert "def _canonical_json" not in source
    assert source.count("hashlib.sha256") <= 1


def test_no_arbitrary_upload_widget(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    assert len(app.file_uploader) == 0


def test_no_private_path_exposure(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    assert not app.exception
    joined = _text(app)
    assert "/Users/" not in joined
    assert "/home/" not in joined
    assert "file://" not in joined.lower()


def test_seek_caption_post_action_coincide_vs_gap_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Discriminating: SEEK caption and metrics must be post-action in same run; exact vs gap truth."""

    app = _app(monkeypatch)
    assert not app.exception
    # Initial state coincide at 0
    assert _metric(app, "Cursor event time") == "0.00 s"
    assert _metric(app, "Playhead time") == "0.00 s"

    # ---- Exact-event seek to 5.0 must show post-action 5.00 in both caption and metrics, no stale 0.00 ----
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(5.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception, f"seek raised: {app.exception}"
    # Metrics must be post-action in same rerun
    cursor_5 = _metric(app, "Cursor event time")
    playhead_5 = _metric(app, "Playhead time")
    assert cursor_5 == "5.00 s", f"cursor should be 5.00 post-action, got {cursor_5}"
    assert playhead_5 == "5.00 s", f"playhead should be 5.00 post-action, got {playhead_5}"
    assert _metric(app, "Cursor index") == "5/7"
    # Seek caption placeholder must be filled from post-action view, not pre-action 0.00
    seek_caps = [c.value for c in app.caption if "Seek target" in str(c.value)]
    assert len(seek_caps) == 1, f"expected exactly one seek caption, got {seek_caps}"
    sc_exact = str(seek_caps[0])
    assert "Seek target 5.00" in sc_exact, f"seek caption should show target 5.00, got {sc_exact}"
    assert "5.00" in sc_exact
    # Must say coincide for exact, not distinct
    assert "coincide" in sc_exact.lower(), (
        f"exact-event seek caption must say coincide, got {sc_exact}"
    )
    assert "distinct" not in sc_exact.lower(), f"exact seek must not claim distinct, got {sc_exact}"
    # No stale 0.00 claim as current cursor/playhead time in that same caption
    # The caption is the only element that labels current cursor event time vs playhead time for seek target
    assert "cursor event time 0.00" not in sc_exact.lower(), (
        f"stale 0.00 cursor in post-action caption: {sc_exact}"
    )
    assert "playhead time 0.00" not in sc_exact.lower(), (
        f"stale 0.00 playhead in post-action caption: {sc_exact}"
    )
    # Receipt must also be correct and not stale
    joined_exact = _text(app)
    assert "Seeked to 5.00" in joined_exact
    assert "playhead 5.00" in joined_exact.lower()
    assert "cursor 5/7" in joined_exact.lower()

    # Simulation clock caption for exact must say coincide, metrics already prove coincidence
    sim_caps = [
        c.value for c in app.caption if "Cursor event time (selected event)" in str(c.value)
    ]
    assert any("coincide" in str(v).lower() for v in sim_caps), (
        f"sim clock should say coincide for exact, got {sim_caps}"
    )

    # ---- Gap seek to 2.0 must show distinct truth: playhead 2.00 vs cursor 2.50 ----
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(2.0).run(timeout=30)
            break
    seek_btn2 = next(b for b in app.button if b.label == "SEEK")
    seek_btn2.click().run(timeout=30)
    assert not app.exception
    cursor_gap = _metric(app, "Cursor event time")
    playhead_gap = _metric(app, "Playhead time")
    assert playhead_gap == "2.00 s", f"gap playhead should be 2.00, got {playhead_gap}"
    assert cursor_gap == "2.50 s", f"gap cursor should be 2.50 (next event), got {cursor_gap}"
    assert cursor_gap != playhead_gap, "gap seek must have distinct times"
    seek_caps_gap = [c.value for c in app.caption if "Seek target" in str(c.value)]
    assert len(seek_caps_gap) == 1
    sc_gap = str(seek_caps_gap[0])
    assert "Seek target 2.00" in sc_gap, f"gap caption target 2.00, got {sc_gap}"
    assert "2.00" in sc_gap and "2.50" in sc_gap, (
        f"gap caption must show both 2.00 and 2.50, got {sc_gap}"
    )
    assert "distinct" in sc_gap.lower(), f"gap seek caption must say distinct, got {sc_gap}"
    assert "coincide" not in sc_gap.lower(), f"gap caption must not say coincide, got {sc_gap}"
    # Truthful relation: playhead precedes cursor (2.00 < 2.50)
    assert "precedes" in sc_gap.lower(), f"gap seek caption must say precedes, got {sc_gap}"
    assert "follows" not in sc_gap.lower(), f"gap seek must not say follows, got {sc_gap}"
    assert "2.00 s follows" not in sc_gap.lower()
    # Ensure gap caption correctly keeps playhead < cursor ordering via precedes phrase
    assert (
        "playhead 2.00 s precedes cursor event time 2.50 s" in sc_gap.lower()
        or "precedes" in sc_gap.lower()
    )
    # Receipt for gap must say distinct and not coincide, and truthfully precedes
    joined_gap = _text(app)
    assert "Seeked to 2.00" in joined_gap
    # Find the seek receipt line: should contain distinct and playhead 2.00 and precedes
    assert "distinct" in joined_gap.lower()
    assert "precedes" in joined_gap.lower(), f"gap receipt must say precedes, got {joined_gap}"
    assert "playhead 2.00 s follows" not in joined_gap.lower()
    # Gap receipt must describe before next event, not after final event
    assert "lies after final event" not in joined_gap.lower(), (
        f"gap receipt must not claim after final, got {joined_gap}"
    )
    assert (
        "falls before selected next event" in joined_gap.lower() or "precedes" in joined_gap.lower()
    )
    # Verify simulation clock now says distinct and precedes
    sim_caps_gap = [
        c.value for c in app.caption if "Cursor event time (selected event)" in str(c.value)
    ]
    assert any("distinct" in str(v).lower() for v in sim_caps_gap), (
        f"sim clock should say distinct for gap, got {sim_caps_gap}"
    )
    assert any("precedes" in str(v).lower() for v in sim_caps_gap), (
        f"sim clock should say precedes for gap, got {sim_caps_gap}"
    )
    # Timeline must also say distinct and precedes for gap
    timeline_caps_gap = [
        c.value for c in app.caption if "Timeline window starts at cursor" in str(c.value)
    ]
    assert any("distinct" in str(v).lower() for v in timeline_caps_gap), (
        f"timeline should say distinct for gap, got {timeline_caps_gap}"
    )
    assert any("precedes" in str(v).lower() for v in timeline_caps_gap), (
        f"timeline should say precedes for gap, got {timeline_caps_gap}"
    )
    # Ensure gap captions never claim follows or after-final-event falsely
    assert all("follows" not in str(v).lower() for v in sim_caps_gap) or any(
        "precedes" in str(v).lower() for v in sim_caps_gap
    )
    assert all("lies after final event" not in str(v).lower() for v in timeline_caps_gap)


def test_seek_beyond_end_follows_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    """SEEK 8.0 beyond last event (6.0) must show playhead 8.00 follows cursor 6.00, ENDED, never false inequality."""

    app = _app(monkeypatch)
    assert not app.exception
    # Seek to 8.0 beyond final 6.0
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(8.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception, f"seek 8.0 raised: {app.exception}"
    # Metrics must be 8.00 playhead, 6.00 cursor, ENDED, 7/7
    assert _metric(app, "Playhead time") == "8.00 s", (
        f"playhead should be 8.00, got {_metric(app, 'Playhead time')}"
    )
    assert _metric(app, "Cursor event time") == "6.00 s", (
        f"cursor should be 6.00 (last event), got {_metric(app, 'Cursor event time')}"
    )
    assert _metric(app, "Cursor index") == "7/7"
    assert _metric(app, "Playback state") == "ended"
    joined = _text(app)
    # Receipt must describe follows, not precedes, and after final event, never false inequality
    assert "Seeked to 8.00" in joined
    assert (
        "playhead 8.00 s follows cursor event time 6.00 s" in joined.lower()
        or "follows" in joined.lower()
    )
    assert "lies after final event" in joined.lower(), (
        f"receipt should say lies after final event, got {joined}"
    )
    assert "8.00 < 6.00" not in joined, (
        f"must never print false inequality 8.00 < 6.00, got {joined}"
    )
    assert "8.00 s < cursor 6.00" not in joined
    assert "playhead 8.00 s precedes" not in joined.lower(), (
        f"must not say precedes for 8.00 > 6.00, got {joined}"
    )
    assert "falls before selected next event" not in joined.lower(), (
        f"must not falsely call before next event for beyond-end, got {joined}"
    )
    # Every relevant caption must say follows, never precedes, never false inequality
    seek_caps = [c.value for c in app.caption if "Seek target" in str(c.value)]
    assert len(seek_caps) == 1
    sc = str(seek_caps[0])
    assert "follows" in sc.lower(), f"seek caption must say follows, got {sc}"
    assert "precedes" not in sc.lower(), (
        f"seek caption must not say precedes for 8.00->6.00, got {sc}"
    )
    assert "8.00 < 6.00" not in sc
    assert "8.00" in sc and "6.00" in sc
    sim_caps = [
        c.value for c in app.caption if "Cursor event time (selected event)" in str(c.value)
    ]
    assert any("follows" in str(v).lower() for v in sim_caps), (
        f"sim clock must say follows, got {sim_caps}"
    )
    assert all("precedes" not in str(v).lower() for v in sim_caps), (
        f"sim clock must not say precedes, got {sim_caps}"
    )
    assert all("8.00 < 6.00" not in str(v) for v in sim_caps)
    timeline_caps = [
        c.value for c in app.caption if "Timeline window starts at cursor" in str(c.value)
    ]
    assert any("follows" in str(v).lower() for v in timeline_caps), (
        f"timeline must say follows, got {timeline_caps}"
    )
    assert all("precedes" not in str(v).lower() for v in timeline_caps), (
        f"timeline must not say precedes, got {timeline_caps}"
    )
    # Generic captions must describe only relation, not claim generic gap-before-next-event
    for cap in sim_caps + timeline_caps:
        assert "gap seek" not in str(cap).lower() or "follows" in str(cap).lower(), (
            f"generic caption must not falsely claim gap seek: {cap}"
        )
        # Ensure not claiming gap-before-next-event for beyond-end
        assert "falls before selected next event" not in str(cap).lower()


def test_play_advance_follows_not_seek(monkeypatch: pytest.MonkeyPatch) -> None:
    """PLAY then ADVANCE 0.5 must show playhead 0.50 follows cursor 0.00, generic captions not attributed to SEEK."""

    app = _app(monkeypatch)
    assert not app.exception
    assert _metric(app, "Playback state") == "paused"
    assert _metric(app, "Playhead time") == "0.00 s"
    assert _metric(app, "Cursor event time") == "0.00 s"
    # PLAY
    play_btn = next(b for b in app.button if b.label == "PLAY")
    play_btn.click().run(timeout=30)
    assert not app.exception
    assert _metric(app, "Playback state") == "playing"
    # Ensure advance delta is 0.5 (default) — set explicitly
    for ni in app.number_input:
        if "Advance delta" in str(getattr(ni, "label", "")):
            ni.set_value(0.5).run(timeout=30)
            break
    adv_btn = next(b for b in app.button if b.label == "ADVANCE")
    adv_btn.click().run(timeout=30)
    assert not app.exception, f"advance raised: {app.exception}"
    assert _metric(app, "Playhead time") == "0.50 s", (
        f"playhead should be 0.50, got {_metric(app, 'Playhead time')}"
    )
    assert _metric(app, "Cursor event time") == "0.00 s", (
        f"cursor should remain 0.00, got {_metric(app, 'Cursor event time')}"
    )
    assert _metric(app, "Playback state") == "playing"
    assert _metric(app, "Cursor index") == "0/7"
    joined = _text(app)
    # Receipt should be ADVANCE, not SEEK, and mention advanced
    assert "Advanced by 0.50" in joined or "advanced" in joined.lower()
    # Metrics receipt should show playhead 0.50 and cursor 0/7
    assert "playhead 0.50" in joined.lower()
    # Generic captions must say follows and not attribute to SEEK
    seek_caps = [c.value for c in app.caption if "Seek target" in str(c.value)]
    assert len(seek_caps) == 1
    sc = str(seek_caps[0])
    assert "follows" in sc.lower(), f"seek caption after ADVANCE must say follows, got {sc}"
    assert "precedes" not in sc.lower()
    # Generic clock/timeline must say follows and must not claim SEEK cause
    sim_caps = [
        c.value for c in app.caption if "Cursor event time (selected event)" in str(c.value)
    ]
    assert any("follows" in str(v).lower() for v in sim_caps), (
        f"sim clock must say follows, got {sim_caps}"
    )
    timeline_caps = [
        c.value for c in app.caption if "Timeline window starts at cursor" in str(c.value)
    ]
    assert any("follows" in str(v).lower() for v in timeline_caps), (
        f"timeline must say follows, got {timeline_caps}"
    )
    for cap in sim_caps + timeline_caps + seek_caps:
        # Generic captions must describe only relation, not claim a gap seek / SEEK cause
        assert "gap seek" not in str(cap).lower(), (
            f"generic caption must not attribute ADVANCE to SEEK: {cap}"
        )
        # Also must not contain SEEK target attribution (except receipt which is not in captions)
        # The word SEEK in generic captions would be a false cause attribution
        assert "SEEK" not in str(cap) or "follows" in str(cap).lower(), (
            f"generic caption must not claim SEEK cause: {cap}"
        )
    # Ensure no false inequality printed
    for cap in sim_caps + timeline_caps + [sc]:
        assert "0.50 < 0.00" not in str(cap)
        assert "0.50 s < cursor 0.00" not in str(cap)
    # Ensure not saying precedes falsely
    for cap in sim_caps + timeline_caps:
        assert "precedes" not in str(cap).lower(), (
            f"must not say precedes for 0.50 > 0.00, got {cap}"
        )


def test_aggregate_coincide_without_exact_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aggregate-only zero-event state may say coincide but must not label as exact-event seek without SEEK receipt."""

    app = _app(monkeypatch)
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    assert not app.exception
    assert _metric(app, "Cursor index") == "0/0"
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Playhead time") == "0.00 s"
    assert _metric(app, "Cursor event time") == "0.00 s"
    joined = _text(app)
    # May say coincide for zero-event aggregate, but must not claim exact-event
    # Check all captions that mention coincide
    captions = [str(c.value) for c in app.caption]
    # At least one caption should mention coincide (clock/seek/timeline) for zero-event
    assert any("coincide" in cap.lower() for cap in captions), (
        f"aggregate should mention coincide, got {captions}"
    )
    # But must NOT say exact-event or exact-event seek absent a SEEK receipt
    for cap in captions:
        # Generic captions for aggregate must not contain exact-event phrasing
        assert "exact-event seek" not in cap.lower(), (
            f"aggregate must not say exact-event seek without receipt: {cap}"
        )
        # Also should not say "exact-event" as a SEEK attribution in generic captions
        # The only allowed exact-event is in a live SEEK receipt, which does not exist here
    # Ensure no SEEK receipt is present (no Seeked text) or if present, not for aggregate
    # After aggregate load, last receipt is cleared, so no Seeked banner should appear
    # We check that joined does not contain Seeked to ... with exact-event seek for aggregate
    # The aggregate load clears receipt, so any prior Seeked should be withheld
    assert (
        "Seeked to" not in joined
        or "coincide" not in joined.lower()
        or "exact-event seek" not in joined.lower()
    )
    # Also ensure simulation clock and timeline for aggregate say coincide but not exact-event
    sim_caps = [
        c.value for c in app.caption if "Cursor event time (selected event)" in str(c.value)
    ]
    for cap in sim_caps:
        if "coincide" in str(cap).lower():
            assert "exact-event" not in str(cap).lower(), (
                f"aggregate sim clock must not say exact-event: {cap}"
            )
    timeline_caps = [
        c.value for c in app.caption if "Timeline window starts at cursor" in str(c.value)
    ]
    for cap in timeline_caps:
        if "coincide" in str(cap).lower():
            assert "exact-event" not in str(cap).lower(), (
                f"aggregate timeline must not say exact-event: {cap}"
            )
    seek_caps = [c.value for c in app.caption if "Seek target" in str(c.value)]
    for cap in seek_caps:
        if "coincide" in str(cap).lower():
            assert "exact-event seek" not in str(cap).lower(), (
                f"aggregate seek caption must not say exact-event seek: {cap}"
            )
            assert "exact-event" not in str(cap).lower(), (
                f"aggregate seek caption must not say exact-event: {cap}"
            )


def test_seek_empty_stream_noop_3_0(monkeypatch: pytest.MonkeyPatch) -> None:
    """SEEK 3.0 on aggregate-only empty stream is no-op INFO banner — never success/exact-event."""

    app = _app(monkeypatch)
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    assert not app.exception
    assert _metric(app, "Cursor index") == "0/0"
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Playhead time") == "0.00 s"
    assert _metric(app, "Cursor event time") == "0.00 s"
    # Set SEEK target 3.0
    for s in app.slider:
        if "Seek" in str(getattr(s, "label", "")):
            s.set_value(3.0).run(timeout=30)
            break
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception, f"seek 3.0 on empty raised: {app.exception}"
    # Metrics must remain ENDED 0/0 playhead 0.00 (no movement)
    assert _metric(app, "Cursor index") == "0/0", (
        f"empty seek must stay 0/0 got {_metric(app, 'Cursor index')}"
    )
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Playhead time") == "0.00 s", (
        f"empty seek playhead must stay 0.00 got {_metric(app, 'Playhead time')}"
    )
    assert _metric(app, "Cursor event time") == "0.00 s"
    joined = _text(app)
    joined_low = joined.lower()
    # Banner must be INFO/no-op/unavailable, never success styling
    # Check info banner contains required truthful fields
    assert "seek" in joined_low and "unavailable" in joined_low, (
        f"empty seek banner must say SEEK unavailable, got {joined}"
    )
    assert "empty stream" in joined_low and "zero events" in joined_low, (
        f"must mention zero events, got {joined}"
    )
    assert "requested target 3.00" in joined_low or "requested target 3.00 s" in joined_low, (
        f"must mention requested target 3.00, got {joined}"
    )
    assert "was not applied" in joined_low or "not applied" in joined_low, (
        f"must say not applied, got {joined}"
    )
    assert "state remains ended" in joined_low or "state remains ended" in joined_low, (
        f"must say state remains ENDED, got {joined}"
    )
    assert "playhead 0.00" in joined_low, f"must mention playhead 0.00, got {joined}"
    assert "0/0" in joined, f"must mention cursor 0/0, got {joined}"
    assert "ended" in joined_low, f"must mention ENDED, got {joined}"
    # Explicitly reject forbidden success/movement claims
    assert "Seeked to" not in joined, f"empty SEEK must never say Seeked to, got {joined}"
    assert "seeked to" not in joined_low, f"must not claim Seeked to, got {joined}"
    assert "exact-event" not in joined_low, f"must never say exact-event for empty, got {joined}"
    assert "exact-event seek" not in joined_low
    # Must never use precedes/follows for empty
    # Check the receipt/banner portion does not contain those; whole page may contain unrelated precedes? Check info banner specifically
    info_text = " ".join(str(getattr(v, "value", "")) for v in app.info)
    assert "precedes" not in info_text.lower(), (
        f"empty banner must not say precedes, got {info_text}"
    )
    assert "follows" not in info_text.lower(), f"empty banner must not say follows, got {info_text}"
    # Check that banner is in info, not success (success styling)
    assert any(
        "SEEK unavailable" in str(getattr(v, "value", ""))
        or "seek unavailable" in str(getattr(v, "value", "")).lower()
        for v in app.info
    ), (
        f"banner must be info-styled, got info={[getattr(v, 'value', None) for v in app.info]} success={[getattr(v, 'value', None) for v in app.success]}"
    )
    assert not any("SEEK unavailable" in str(getattr(v, "value", "")) for v in app.success), (
        f"empty SEEK banner must never be success, got success={[getattr(v, 'value', None) for v in app.success]}"
    )
    # Also ensure no success banner claims Seeked
    success_text = " ".join(str(getattr(v, "value", "")) for v in app.success)
    assert "Seeked to" not in success_text
    assert "seeked to" not in success_text.lower()
    # Ensure not implying movement: banner should not contain moved/seeked/advanced language with success
    assert "advanced" not in info_text.lower() or "unavailable" in info_text.lower()


def test_seek_empty_stream_noop_0_0_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """SEEK at default 0.0 on aggregate-only is equally no-op INFO — numeric coincidence must not yield exact-event."""

    app = _app(monkeypatch)
    agg_btn = next(b for b in app.button if b.label == "Load aggregate-only demo")
    agg_btn.click().run(timeout=30)
    assert not app.exception
    assert _metric(app, "Cursor index") == "0/0"
    assert _metric(app, "Playback state") == "ended"
    # Do not change slider — default 0.0 (should be 0.0 for empty stream)
    seek_slider = next(s for s in app.slider if "Seek" in str(getattr(s, "label", "")))
    assert float(str(getattr(seek_slider, "value", 0.0))) == 0.0  # noqa: S101
    seek_btn = next(b for b in app.button if b.label == "SEEK")
    seek_btn.click().run(timeout=30)
    assert not app.exception, f"seek 0.0 on empty raised: {app.exception}"
    assert _metric(app, "Cursor index") == "0/0"
    assert _metric(app, "Playback state") == "ended"
    assert _metric(app, "Playhead time") == "0.00 s"
    assert _metric(app, "Cursor event time") == "0.00 s"
    joined = _text(app)
    joined_low = joined.lower()
    # Must be same no-op class as 3.0
    assert "unavailable" in joined_low, f"empty seek 0.0 must say unavailable, got {joined}"
    assert "empty stream" in joined_low and "zero events" in joined_low
    assert "requested target 0.00" in joined_low, (
        f"must mention requested target 0.00, got {joined}"
    )
    assert "was not applied" in joined_low or "not applied" in joined_low
    assert "state remains ended" in joined_low
    assert "playhead 0.00" in joined_low
    assert "0/0" in joined
    # Despite numeric coincidence 0.00 == 0.00, must NOT label as exact-event
    assert "Seeked to" not in joined
    assert "exact-event" not in joined_low
    assert "exact-event seek" not in joined_low
    assert "precedes" not in " ".join(str(getattr(v, "value", "")) for v in app.info).lower()
    assert "follows" not in " ".join(str(getattr(v, "value", "")) for v in app.info).lower()
    # Must be info-styled, not success
    assert any(
        "SEEK unavailable" in str(getattr(v, "value", ""))
        or "unavailable" in str(getattr(v, "value", "")).lower()
        for v in app.info
    )
    assert not any("Seeked to" in str(getattr(v, "value", "")) for v in app.success)
    # Ensure generic captions for aggregate still not claiming exact-event despite coincidence
    for cap in app.caption:
        if "coincide" in str(cap.value).lower():
            assert "exact-event" not in str(cap.value).lower(), (
                f"aggregate coincide must not say exact-event: {cap.value}"
            )

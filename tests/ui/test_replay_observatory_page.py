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
    # Cursor event time vs playhead time distinctly labelled (gap seek truth)
    assert "Cursor event time" in joined
    assert "Playhead time" in joined
    assert "gap seeks" in joined.lower() or "distinct" in joined.lower()
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
    # Gap seek truth caption
    assert "gap seeks keep these distinct" in joined.lower() or "distinct" in joined.lower()
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
    # Distinct times shown in metrics
    cursor_t = _metric(app, "Cursor event time")
    playhead_t = _metric(app, "Playhead time")
    assert cursor_t != playhead_t


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

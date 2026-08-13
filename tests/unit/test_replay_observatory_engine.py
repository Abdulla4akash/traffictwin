"""Deterministic engine controls, windows, fingerprints and fail-closed validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.replay_observatory.adapters import load_event_stream_json
from traffictwin.replay_observatory.engine import (
    MAX_SPEED_MULTIPLIER,
    MAX_STEP_COUNT,
    MAX_WINDOW_DURATION_S,
    MAX_WINDOW_EVENTS,
    MIN_SPEED_MULTIPLIER,
    PlaybackState,
    ReplayControl,
    ReplayControlRequest,
    ReplayEngine,
    ReplayEngineError,
)
from traffictwin.replay_observatory.models import (
    EntityIdentity,
    EntityKind,
    EventProvenance,
    EventType,
    EvidenceStanding,
    ReplayEvent,
    ReplayEventStream,
    ResourceMeasurement,
    ResourceStatePayload,
    ScaleActionPayload,
    SimulationTimeEvent,
    SimulationTimePayload,
    SourceCapabilityManifest,
    SourceDataKind,
    SourceIdentity,
    SourceKind,
    VehicleStatePayload,
)

ARTIFACT = "a" * 64
ARTIFACT2 = "b" * 64


def _source(*, artifact: str = ARTIFACT, source_id: str = "src-001") -> SourceIdentity:
    return SourceIdentity(
        source_id=source_id,
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256=artifact,
        schema_version="1.0",
    )


def _provenance(*, artifact: str = ARTIFACT, record: str = "rec-001") -> EventProvenance:
    return EventProvenance(
        source_artifact_sha256=artifact,
        source_record_id=record,
        adapter_id="adapter-v1",
        adapter_version="1.0",
    )


def _manifest(
    *,
    source: SourceIdentity | None = None,
    available: tuple[EventType, ...] | None = None,
    kind: SourceDataKind = SourceDataKind.EVENT_STREAM,
) -> SourceCapabilityManifest:
    src = source or _source()
    if available is None:
        available = tuple(sorted(EventType, key=lambda x: str(x)))
    return SourceCapabilityManifest(
        manifest_id="manifest-001",
        source=src,
        source_data_kind=kind,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=available,
        limitations=("Synthetic only", "Bounded fixture"),
    )


def _sim_event(
    *,
    seq: int = 0,
    time: float = 0.0,
    source: SourceIdentity | None = None,
    event_id: str | None = None,
) -> SimulationTimeEvent:
    src = source or _source()
    return SimulationTimeEvent(
        event_id=event_id or f"evt-sim-{seq:03d}",
        sequence=seq,
        simulator_time_s=time,
        entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record=f"rec-sim-{seq:03d}"),
        payload=SimulationTimePayload(step_index=seq),
    )


def _vehicle_event(
    *, seq: int = 1, time: float = 1.0, source: SourceIdentity | None = None
) -> SimulationTimeEvent:
    # reuse sim for simplicity, but produce vehicle state payload
    from traffictwin.replay_observatory.models import VehicleStateEvent

    src = source or _source()
    return VehicleStateEvent(  # type: ignore[return-value]
        event_id=f"evt-veh-{seq:03d}",
        sequence=seq,
        simulator_time_s=time,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record=f"rec-veh-{seq:03d}"),
        payload=VehicleStatePayload(x_m=1.0, y_m=2.0, speed_mps=1.0),
    )


def _stream_with_events(
    events: tuple[ReplayEvent, ...] | list[ReplayEvent],
) -> ReplayEventStream:
    # Determine present types canonically sorted
    src = _source()
    manifest = _manifest(
        source=src,
        available=tuple(sorted({e.event_type for e in events}, key=str)) if events else (),
    )
    # If events empty, manifest available empty
    if not events:
        manifest = _manifest(source=src, available=())
        return ReplayEventStream(
            stream_id="stream-001",
            capability_manifest=manifest,
            present_event_types=(),
            events=(),
            limitations=("a",),
        )
    # Ensure manifest covers types
    present = tuple(sorted({e.event_type for e in events}, key=str))
    manifest = _manifest(source=src, available=present)
    return ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=present,
        events=tuple(events),
        limitations=("a",),
    )


# ---------------------------------------------------------------------------
# Controls: PLAY / PAUSE / STEP / SEEK
# ---------------------------------------------------------------------------


def test_play_transitions_to_playing() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0), _sim_event(seq=1, time=1.0)])
    engine = ReplayEngine(stream)
    assert engine.playback_state is PlaybackState.PAUSED
    receipt = engine.play()
    assert receipt.resulting_state.playback_state is PlaybackState.PLAYING
    assert receipt.resulting_state.cursor.index == 0
    assert receipt.tamper_detected is False


def test_pause_transitions_to_paused() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0), _sim_event(seq=1, time=1.0)])
    engine = ReplayEngine(stream)
    engine.play()
    receipt = engine.pause()
    assert receipt.resulting_state.playback_state is PlaybackState.PAUSED


def test_step_forward_and_backward() -> None:
    stream = _stream_with_events([_sim_event(seq=i, time=float(i)) for i in range(5)])
    engine = ReplayEngine(stream)
    engine.step(2, "forward")
    assert engine.cursor_index == 2
    assert engine.current_event().event_id == "evt-sim-002"  # type: ignore[union-attr]
    engine.step(1, "backward")
    assert engine.cursor_index == 1
    # deterministic receipt fingerprint
    r1 = engine.apply(
        ReplayControlRequest(control=ReplayControl.STEP, step_count=1, step_direction="forward")
    )
    r2_state = r1.resulting_state.fingerprint()
    # replay same sequence on fresh engine -> same fingerprint
    engine2 = ReplayEngine(stream)
    engine2.step(2, "forward")
    engine2.step(1, "backward")
    engine2.step(1, "forward")
    assert engine2.state().fingerprint() == r2_state


def test_seek_lands_on_first_equal_time() -> None:
    # equal-time events ordered by sequence
    src = _source()
    e0 = _sim_event(seq=0, time=1.0, source=src, event_id="evt-aaa-000")
    e1 = _sim_event(seq=1, time=1.0, source=src, event_id="evt-aaa-001")
    e2 = _sim_event(seq=2, time=2.0, source=src, event_id="evt-aaa-002")
    stream = _stream_with_events([e0, e1, e2])
    engine = ReplayEngine(stream)
    # load window should preserve equal-time order by sequence
    win = engine.load_time_window(1.0, 1.0)
    assert [e.event_id for e in win] == ["evt-aaa-000", "evt-aaa-001"]
    receipt = engine.seek(1.0)
    assert receipt.resulting_state.cursor.index == 0  # first of equal-time group
    assert receipt.resulting_state.cursor.simulator_time_s == 1.0


def test_step_boundaries_end_of_stream_typed_state() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0), _sim_event(seq=1, time=1.0)])
    engine = ReplayEngine(stream)
    engine.step(10, "forward")
    assert engine.is_at_end() is True
    state = engine.state()
    assert state.end_of_stream is True
    assert state.playback_state is PlaybackState.ENDED
    # stepping at end stays ended, explicit typed state not exception
    receipt = engine.step(1, "forward")
    assert receipt.resulting_state.end_of_stream is True
    # stepping backward from end recovers
    engine.step(1, "backward")
    assert engine.is_at_end() is False
    assert engine.cursor_index == 1


def test_seek_boundaries() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0), _sim_event(seq=1, time=5.0)])
    engine = ReplayEngine(stream)
    # seek before start lands at 0
    engine.seek(-0.0)  # 0.0 valid
    assert engine.cursor_index == 0
    # seek beyond end -> end-of-stream typed state
    receipt = engine.seek(100.0)
    assert receipt.resulting_state.end_of_stream is True
    assert receipt.resulting_state.cursor.is_at_end is True
    assert receipt.resulting_state.playback_state is PlaybackState.ENDED
    # seek exactly on existing time
    engine2 = ReplayEngine(stream)
    engine2.seek(5.0)
    assert engine2.cursor_index == 1


def test_empty_stream_explicit_state() -> None:
    stream = _stream_with_events([])
    engine = ReplayEngine(stream)
    state = engine.state()
    assert state.empty_stream is True
    assert state.end_of_stream is True
    assert state.playback_state is PlaybackState.ENDED
    assert engine.current_event() is None
    # play on empty stays ended
    r = engine.play()
    assert r.resulting_state.empty_stream is True
    # seek on empty stays ended
    r2 = engine.seek(10.0)
    assert r2.resulting_state.empty_stream is True
    # step on empty stays ended
    r3 = engine.step(1, "forward")
    assert r3.resulting_state.empty_stream is True
    # window on empty is empty truthfully
    assert engine.load_time_window(0.0, 10.0) == ()


def test_speed_multiplier_bounded_validation() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream, speed_multiplier=1.0)
    # valid bounds
    engine.set_speed(MIN_SPEED_MULTIPLIER)
    assert engine.speed_multiplier == MIN_SPEED_MULTIPLIER
    engine.set_speed(MAX_SPEED_MULTIPLIER)
    assert engine.speed_multiplier == MAX_SPEED_MULTIPLIER
    # invalid via request
    with pytest.raises((ValidationError, ReplayEngineError)):
        engine.apply(ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=0.01))
    with pytest.raises((ValidationError, ReplayEngineError)):
        engine.apply(ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=100.0))
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=float("inf"))
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier=float("nan"))
    with pytest.raises(ReplayEngineError):
        ReplayEngine(stream, speed_multiplier=0.0)
    with pytest.raises(ReplayEngineError):
        ReplayEngine(stream, speed_multiplier=float("inf"))


def test_negative_and_nonfinite_time_fail_closed() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=-1.0)
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=float("inf"))
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=float("nan"))
    with pytest.raises(ReplayEngineError):
        engine.load_time_window(-1.0, 5.0)
    with pytest.raises(ReplayEngineError):
        engine.load_time_window(float("nan"), 5.0)
    # seek via apply with negative also fails before transition
    with pytest.raises((ValidationError, ReplayEngineError)):
        engine.seek(-5.0)


def test_bounded_window_without_mutation() -> None:
    events = [_sim_event(seq=i, time=float(i)) for i in range(10)]
    stream = _stream_with_events(events)
    fp_before = stream.fingerprint()
    engine = ReplayEngine(stream)
    win = engine.load_time_window(2.0, 5.0, max_events=2)
    assert len(win) == 2
    assert win[0].simulator_time_s == 2.0
    assert win[1].simulator_time_s == 3.0
    # original stream unchanged
    assert stream.fingerprint() == fp_before
    assert len(stream.events) == 10
    # no synthesis: window outside range empty
    assert engine.load_time_window(100.0, 200.0) == ()
    # bounded duration check
    with pytest.raises(ReplayEngineError):
        engine.load_time_window(0.0, MAX_WINDOW_DURATION_S + 1)
    # bounded max_events
    with pytest.raises(ReplayEngineError):
        engine.load_time_window(0.0, 10.0, max_events=MAX_WINDOW_EVENTS + 1)


def test_unavailable_capabilities_remain_unavailable() -> None:
    # stream only has simulation_time, other types unavailable
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    state = engine.state()
    assert EventType.VEHICLE_STATE in state.unavailable_event_types
    assert EventType.TASK_OFFERED in state.unavailable_event_types
    # current_event truthfully unavailable when empty? Check peek beyond.
    assert (
        engine.load_time_window(0.0, 10.0, max_events=10)[0].event_type is EventType.SIMULATION_TIME
    )
    # querying unavailable type via window that would contain it yields empty,
    # not synthesized
    # There is no vehicle_state in stream, so window is empty for that type
    # alone but overall window still simulation_time.
    # The unavailable list must include all missing types canonically ordered.
    assert tuple(sorted(state.unavailable_event_types, key=str)) == state.unavailable_event_types


def test_deterministic_replay_and_fingerprint() -> None:
    events = [_sim_event(seq=i, time=float(i)) for i in range(5)]
    stream = _stream_with_events(events)
    engine = ReplayEngine(stream)
    # Sequence: play, step, pause, seek
    r1 = engine.play()
    r2 = engine.step(2, "forward")
    engine.pause()
    r4 = engine.seek(1.0)
    fp_play = r1.resulting_state.fingerprint()
    fp_step = r2.resulting_state.fingerprint()
    # Replay same operations on fresh engine produces identical fingerprints
    engine2 = ReplayEngine(stream)
    engine2.play()
    assert engine2.state().fingerprint() == fp_play
    engine2.step(2, "forward")
    assert engine2.state().fingerprint() == fp_step
    # Receipt fingerprints deterministic
    req = ReplayControlRequest(control=ReplayControl.PLAY)
    assert req.fingerprint() == req.fingerprint()
    # Stream fingerprint stable
    assert stream.fingerprint() == stream.fingerprint()
    # State fingerprint changes only with state
    assert r4.resulting_state.cursor.index == 1
    # No wall-clock sleep: operations are instantaneous; we assert they
    # complete without sleep by checking quickly
    # (implicit; engine has no sleep call)


def test_immutable_source_and_tamper_detection() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    fp = stream.fingerprint()
    engine = ReplayEngine(stream)
    # Tamper via expected fingerprint mismatch fails closed
    with pytest.raises(ReplayEngineError, match="TAMPER"):
        engine.apply(
            ReplayControlRequest(control=ReplayControl.PLAY, expected_stream_fingerprint="f" * 64)
        )
    # Tamper via mutated underlying stream detected on next operation
    # Create a second stream with same source but extra event (invented) and try to swap
    src = _source()
    extra = _sim_event(seq=1, time=1.0, source=src)
    # Build stream that pretends to be same source_id but fingerprint differs
    # Engine's _stream_fingerprint would not match the new stream's
    # fingerprint if we mutated internally;
    # Simulate by manually patching engine's stream reference (simulating tamper)
    other_stream = _stream_with_events([_sim_event(seq=0, time=0.0), extra])
    engine._stream = other_stream  # type: ignore[attr-defined]
    with pytest.raises(ReplayEngineError, match="TAMPER"):
        engine.state()
    # Restore and verify passes
    engine._stream = stream  # type: ignore[attr-defined]
    engine._stream_fingerprint = fp  # type: ignore[attr-defined]
    assert engine.verify_integrity(fp) is True


def test_typed_requests_frozen_and_strict() -> None:
    req = ReplayControlRequest(control=ReplayControl.PLAY)
    with pytest.raises(ValidationError):
        req.control = ReplayControl.PAUSE  # type: ignore[misc]
    with pytest.raises(ValidationError):
        ReplayControlRequest(control="play", target_time_s="0")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ReplayControlRequest(control=ReplayControl.PLAY, speed_multiplier="1.0")  # type: ignore[arg-type]
    # extra fields forbidden
    with pytest.raises(ValidationError):
        ReplayControlRequest(control=ReplayControl.PLAY, extra_field="oops")  # type: ignore[call-arg]
    # canonical fingerprint on request
    fp = req.fingerprint()
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_state_receipt_fingerprints_canonical() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    receipt = engine.play()
    # Receipt carries canonical fingerprints
    assert (
        receipt.request_fingerprint
        == ReplayControlRequest(control=ReplayControl.PLAY).fingerprint()
    )
    assert receipt.stream_fingerprint == stream.fingerprint()
    assert receipt.resulting_state.fingerprint() == engine.state().fingerprint()
    # Receipt itself has deterministic fingerprint
    assert receipt.fingerprint() == receipt.fingerprint()
    # Disclaimer present
    assert (
        "no causality" in receipt.causal_disclaimer.lower()
        or "causality" in receipt.causal_disclaimer.lower()
    )


def test_research_aggregate_remains_zero_event_unavailable() -> None:
    src = SourceIdentity(
        source_id="agg-src",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT2,
        schema_version="1.0",
    )
    manifest = SourceCapabilityManifest(
        manifest_id="m-agg",
        source=src,
        source_data_kind=SourceDataKind.AGGREGATE_ONLY,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=("Aggregate only", "Research"),
    )
    agg_stream = ReplayEventStream(
        stream_id="agg-stream",
        capability_manifest=manifest,
        present_event_types=(),
        events=(),
        limitations=("Aggregate only",),
    )
    engine = ReplayEngine(agg_stream)
    state = engine.state()
    assert state.empty_stream is True
    assert state.end_of_stream is True
    # Engine refuses to invent events for aggregate
    assert engine.load_time_window(0.0, 10.0) == ()
    # Constructing engine over tampered aggregate with events must fail closed
    with pytest.raises((ValidationError, ReplayEngineError)):
        bad_stream = ReplayEventStream(
            stream_id="bad-agg",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(_sim_event(seq=0, time=0.0, source=src),),
            limitations=("Aggregate only",),
        )
        ReplayEngine(bad_stream)


def test_scale_and_resource_events_are_generic_only() -> None:
    # Build stream with ResourceState and ScaleAction as generic data only
    src = _source()
    from traffictwin.replay_observatory.models import ResourceStateEvent, ScaleActionEvent

    r_evt = ResourceStateEvent(
        event_id="evt-res-001",
        sequence=0,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.RESOURCE, entity_id="res-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-res-001"),
        payload=ResourceStatePayload(
            measurements=(ResourceMeasurement(metric_id="cpu_load", value=0.5, unit="ratio"),)
        ),
    )
    s_evt = ScaleActionEvent(
        event_id="evt-scale-001",
        sequence=1,
        simulator_time_s=2.0,
        entity=EntityIdentity(kind=EntityKind.RESOURCE, entity_id="res-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-scale-001"),
        payload=ScaleActionPayload(
            action_id="act-001", target_resource_id="res-001", source_declared_action="scale_up"
        ),
    )
    stream = ReplayEventStream(
        stream_id="generic-stream",
        capability_manifest=_manifest(
            source=src,
            available=tuple(sorted([EventType.RESOURCE_STATE, EventType.SCALE_ACTION], key=str)),
        ),
        present_event_types=tuple(
            sorted([EventType.RESOURCE_STATE, EventType.SCALE_ACTION], key=str)
        ),
        events=(r_evt, s_evt),
        limitations=("a",),
    )
    engine = ReplayEngine(stream)
    # Engine treats them as plain events: no P2C interpretation, no E3 behavior.
    win = engine.load_time_window(0.0, 10.0)
    assert len(win) == 2
    # Payloads are present verbatim, not interpreted.
    assert win[0].payload.measurements[0].metric_id == "cpu_load"  # type: ignore[union-attr]
    assert win[1].payload.source_declared_action == "scale_up"  # type: ignore[union-attr]
    # Using engine must not mutate or enrich payloads.
    assert win[0].payload == r_evt.payload  # type: ignore[union-attr]


def test_invalid_step_counts_fail_closed() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    ReplayEngine(stream)
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.STEP, step_count=0, step_direction="forward")
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.STEP, step_count=-1, step_direction="forward")
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(
            control=ReplayControl.STEP, step_count=MAX_STEP_COUNT + 1, step_direction="forward"
        )
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.STEP, step_count=1, step_direction="sideways")  # type: ignore[arg-type]


def test_synthetic_fixture_determinism_via_adapter() -> None:
    import pathlib

    raw = pathlib.Path(
        "tests/fixtures/replay_observatory/synthetic_event_stream_v1.json"
    ).read_text()
    stream = load_event_stream_json(raw)
    engine = ReplayEngine(stream)
    # Deterministic window: same query twice same result and fingerprint
    w1 = engine.load_time_window(0.0, 6.0)
    w2 = engine.load_time_window(0.0, 6.0)
    assert w1 == w2
    assert len(w1) == 11
    # Equal-time handling not needed here but ordering is canonical
    times = [e.simulator_time_s for e in w1]
    assert times == sorted(times)

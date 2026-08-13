"""Deterministic engine controls, windows, fingerprints and fail-closed validation."""

from __future__ import annotations

from collections.abc import Sequence

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


def _stream_with_events(events: Sequence[ReplayEvent]) -> ReplayEventStream:
    # Canonically tuple-ise (Sequence is covariant, so list[SimulationTimeEvent] is accepted)
    events_tuple = tuple(events)
    src = _source()
    # Determine present types canonically sorted
    manifest = _manifest(
        source=src,
        available=tuple(sorted({e.event_type for e in events_tuple}, key=str))
        if events_tuple
        else (),
    )
    # If events empty, manifest available empty
    if not events_tuple:
        manifest = _manifest(source=src, available=())
        return ReplayEventStream(
            stream_id="stream-001",
            capability_manifest=manifest,
            present_event_types=(),
            events=(),
            limitations=("a",),
        )
    # Ensure manifest covers types
    present = tuple(sorted({e.event_type for e in events_tuple}, key=str))
    manifest = _manifest(source=src, available=present)
    return ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=present,
        events=events_tuple,
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
    object.__setattr__(engine, "_stream", other_stream)
    with pytest.raises(ReplayEngineError, match="TAMPER"):
        engine.state()
    # Restore and verify passes
    object.__setattr__(engine, "_stream", stream)
    object.__setattr__(engine, "_stream_fingerprint", fp)
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
    assert win[0].payload == r_evt.payload


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


# ---------------------------------------------------------------------------
# Additional hardening: forged streams, request fingerprint, cursor/state
# invariants, advance with speed, pause/end, and receipt verification
# ---------------------------------------------------------------------------


def test_forged_stream_via_model_copy_fails_closed() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0), _sim_event(seq=1, time=1.0)])
    # Forge by inventing a vehicle event not in manifest's available types
    from traffictwin.replay_observatory.models import VehicleStateEvent

    src = _source()
    v_extra = VehicleStateEvent(
        event_id="evt-forged-veh-099",
        sequence=99,
        simulator_time_s=5.0,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-099"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-forged-099"),
        payload=VehicleStatePayload(x_m=0.0, y_m=0.0, speed_mps=0.0),
    )
    forged = stream.model_copy(update={"events": tuple(list(stream.events) + [v_extra])})
    with pytest.raises(ReplayEngineError, match="INVALID_STREAM"):
        ReplayEngine(forged)


def test_forged_manifest_event_type_inflation_fails() -> None:
    # Stream with only SIMULATION_TIME, try to inflate available types via manifest copy
    src = _source()
    e = _sim_event(seq=0, time=0.0, source=src)
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    stream = ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=(EventType.SIMULATION_TIME,),
        events=(e,),
        limitations=("a",),
    )
    # Forge manifest to claim vehicle_state available
    # but not present yet fails on present vs available
    # Instead forge stream to include vehicle event without manifest cap
    from traffictwin.replay_observatory.models import VehicleStateEvent

    v_evt = VehicleStateEvent(
        event_id="evt-veh-999",
        sequence=1,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-999"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-veh-999"),
        payload=VehicleStatePayload(x_m=0.0, y_m=0.0, speed_mps=0.0),
    )
    forged_stream = stream.model_copy(
        update={
            "events": (e, v_evt),
            "present_event_types": (EventType.SIMULATION_TIME, EventType.VEHICLE_STATE),
        }
    )
    with pytest.raises(ReplayEngineError, match="INVALID_STREAM"):
        ReplayEngine(forged_stream)


def test_forged_event_source_evidence_inflation_fails() -> None:
    src1 = _source(artifact=ARTIFACT, source_id="src-001")
    src2 = _source(artifact=ARTIFACT2, source_id="src-002")
    e = _sim_event(seq=0, time=0.0, source=src1)
    stream = _stream_with_events([e])
    # Forge event source to mismatch manifest
    forged_event = e.model_copy(update={"source": src2})
    forged_stream = stream.model_copy(update={"events": (forged_event,)})
    with pytest.raises(ReplayEngineError, match="INVALID_STREAM"):
        ReplayEngine(forged_stream)


def test_forged_invalid_ordering_fails() -> None:
    src = _source()
    e0 = _sim_event(seq=0, time=0.0, source=src)
    e1 = _sim_event(seq=1, time=1.0, source=src)
    # Reverse order violates canonical (simulator_time_s, sequence, event_id)
    stream = _stream_with_events([e0, e1])
    forged = stream.model_copy(update={"events": (e1, e0)})
    with pytest.raises(ReplayEngineError, match="INVALID_STREAM"):
        ReplayEngine(forged)


def test_forged_request_via_model_copy_caught() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    req = ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=1.0)
    forged_req = req.model_copy(update={"target_time_s": -5.0})
    with pytest.raises(ReplayEngineError, match="INVALID_REQUEST"):
        engine.apply(forged_req)


def test_request_fingerprint_mismatch_fails() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    req = ReplayControlRequest(control=ReplayControl.PLAY)
    receipt = engine.apply(req)
    # Forge receipt request fingerprint
    forged_receipt = receipt.model_copy(update={"request_fingerprint": "0" * 64})
    with pytest.raises((ValidationError, ReplayEngineError)):
        forged_receipt.verify_against(engine)


def test_cursor_invariants_structural() -> None:
    from traffictwin.replay_observatory.engine import ReplayCursor

    # empty cursor must have total 0, index 0, event_id None
    with pytest.raises(ValidationError):
        ReplayCursor(
            index=1,
            simulator_time_s=0.0,
            event_id=None,
            is_empty=True,
            is_at_end=True,
            total_events=0,
        )
    with pytest.raises(ValidationError):
        ReplayCursor(
            index=0,
            simulator_time_s=0.0,
            event_id="evt-001",
            is_empty=True,
            is_at_end=True,
            total_events=0,
        )
    with pytest.raises(ValidationError):
        ReplayCursor(
            index=0,
            simulator_time_s=1.0,
            event_id=None,
            is_empty=False,
            is_at_end=False,
            total_events=1,
        )


def test_state_invariants_and_verifiers() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    state = engine.state()
    # Tamper cursor via model_copy
    from traffictwin.replay_observatory.engine import ReplayEngineState

    forged_cursor = state.cursor.model_copy(update={"is_empty": True})
    with pytest.raises(ValidationError):
        ReplayEngineState(
            playback_state=state.playback_state,
            cursor=forged_cursor,
            speed_multiplier=state.speed_multiplier,
            stream_fingerprint=state.stream_fingerprint,
            window_start_s=state.window_start_s,
            window_end_s=state.window_end_s,
            unavailable_event_types=state.unavailable_event_types,
            end_of_stream=state.end_of_stream,
            empty_stream=state.empty_stream,
            playhead_time_s=state.playhead_time_s,
        )
    # Verify exact catches tampered stream
    forged_stream = stream.model_copy(update={"events": ()})
    # Direct verify should fail because total_events mismatch
    with pytest.raises(ReplayEngineError):
        state.cursor.verify_against_stream(forged_stream)
    # Receipt verification catches tampered state
    req = ReplayControlRequest(control=ReplayControl.PLAY)
    receipt = engine.apply(req)
    forged_state = receipt.resulting_state.model_copy(update={"stream_fingerprint": "f" * 64})
    forged_receipt = receipt.model_copy(
        update={"resulting_state": forged_state, "stream_fingerprint": "f" * 64}
    )
    with pytest.raises((ValidationError, ReplayEngineError)):
        forged_receipt.verify_against(engine)


def test_advance_half_and_double_speed() -> None:
    events = [_sim_event(seq=i, time=float(i)) for i in range(5)]
    stream = _stream_with_events(events)
    engine = ReplayEngine(stream, speed_multiplier=1.0)
    engine.play()
    # speed 0.5x: delta 2.0 => 1.0 sim time forward
    engine.set_speed(0.5)
    engine.play()
    r = engine.advance(2.0)
    assert r.resulting_state.cursor.index == 1
    assert r.resulting_state.cursor.simulator_time_s == 1.0
    # speed 2.0: delta 1.0 => 2.0 sim time forward from 1.0 => 3.0
    engine.set_speed(2.0)
    # still playing
    r2 = engine.advance(1.0)
    assert r2.resulting_state.cursor.index == 3
    assert r2.resulting_state.cursor.simulator_time_s == 3.0
    assert r2.resulting_state.playback_state is PlaybackState.PLAYING
    # Receipt is same typed ReplayReceipt and binds request
    assert r2.request.control is ReplayControl.ADVANCE
    assert r2.request_fingerprint == r2.request.fingerprint()
    # Deterministic: replay same sequence on fresh engine
    engine2 = ReplayEngine(stream, speed_multiplier=0.5)
    engine2.play()
    engine2.advance(2.0)
    engine2.set_speed(2.0)
    engine2.advance(1.0)
    assert engine2.state().cursor.index == engine.state().cursor.index


def test_advance_equal_time_ordering() -> None:
    src = _source()
    e0 = _sim_event(seq=0, time=0.0, source=src, event_id="evt-aaa-000")
    e1 = _sim_event(seq=1, time=1.0, source=src, event_id="evt-aaa-001")
    e2 = _sim_event(seq=2, time=1.0, source=src, event_id="evt-aaa-002")
    e3 = _sim_event(seq=3, time=2.0, source=src, event_id="evt-aaa-003")
    present = tuple(sorted({e.event_type for e in (e0, e1, e2, e3)}, key=str))
    manifest = _manifest(source=src, available=present)
    stream = ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=present,
        events=(e0, e1, e2, e3),
        limitations=("a",),
    )
    engine = ReplayEngine(stream)
    engine.play()
    # At time 0.0, advance 1.0 => target 1.0 lands on first of equal-time group (e1)
    r = engine.advance(1.0)
    assert r.resulting_state.cursor.index == 1
    assert r.resulting_state.cursor.event_id == "evt-aaa-001"
    # Next advance 0.0 stays at same group head
    r2 = engine.advance(0.0)
    assert r2.resulting_state.cursor.index == 1
    # Advance 0.5 at 1x with playhead accumulation: from 1.0 group, next advance of 0.5
    # should step to next member of same-time group (e2) to preserve stable order,
    # not jump to 2.0
    r3 = engine.advance(0.5)
    assert r3.resulting_state.cursor.index == 2
    assert r3.resulting_state.cursor.event_id == "evt-aaa-002"


def test_advance_paused_and_ended_explicit() -> None:
    stream = _stream_with_events([_sim_event(seq=i, time=float(i)) for i in range(3)])
    engine = ReplayEngine(stream)
    # Initially PAUSED, advance should not move
    r = engine.advance(1.0)
    assert r.resulting_state.cursor.index == 0
    assert r.resulting_state.playback_state is PlaybackState.PAUSED
    # PLAY then advance moves
    engine.play()
    r2 = engine.advance(1.0)
    assert r2.resulting_state.cursor.index == 1
    assert r2.resulting_state.playback_state is PlaybackState.PLAYING
    # PAUSE then advance no move
    engine.pause()
    r3 = engine.advance(2.0)
    assert r3.resulting_state.cursor.index == 1
    assert r3.resulting_state.playback_state is PlaybackState.PAUSED
    # Seek to end then advance stays ended
    engine.seek(10.0)
    assert engine.is_at_end()
    r4 = engine.advance(1.0)
    assert r4.resulting_state.end_of_stream is True
    assert r4.resulting_state.playback_state is PlaybackState.ENDED
    # Empty stream
    empty = _stream_with_events([])
    e_engine = ReplayEngine(empty)
    r5 = e_engine.advance(1.0)
    assert r5.resulting_state.empty_stream is True


def test_advance_never_sleeps_and_preserves_speed() -> None:
    import time

    stream = _stream_with_events([_sim_event(seq=i, time=float(i)) for i in range(10)])
    engine = ReplayEngine(stream)
    engine.play()
    start = time.monotonic()
    r = engine.advance(5.0)
    elapsed = time.monotonic() - start
    assert elapsed < 0.05  # no sleep
    assert r.resulting_state.speed_multiplier == 1.0
    # Speed still bound after advance
    with pytest.raises((ValidationError, ReplayEngineError)):
        ReplayControlRequest(control=ReplayControl.ADVANCE, advance_delta_s=float("inf"))


def test_receipt_binds_exact_request_and_stream() -> None:
    stream = _stream_with_events([_sim_event(seq=0, time=0.0)])
    engine = ReplayEngine(stream)
    req = ReplayControlRequest(control=ReplayControl.SEEK, target_time_s=0.0)
    receipt = engine.apply(req)
    assert receipt.request == req
    assert receipt.request_fingerprint == req.fingerprint()
    assert receipt.stream_fingerprint == stream.fingerprint()
    assert receipt.resulting_state.stream_fingerprint == receipt.stream_fingerprint
    # Verify passes
    receipt.verify_against(engine, req)
    # Forged stream fingerprint fails
    forged = receipt.model_copy(update={"stream_fingerprint": "a" * 64})
    # Construction itself should fail validation due to state mismatch
    with pytest.raises((ValidationError, ReplayEngineError)):
        forged.verify_against(engine)


# ---------------------------------------------------------------------------
# Opus B1 discriminating probes: playhead, equal-time, fractional, end/pause
# ---------------------------------------------------------------------------


def _equal_time_stream_5() -> ReplayEventStream:
    src = _source()
    e0 = _sim_event(seq=0, time=0.0, source=src, event_id="evt-aaa-000")
    e1 = _sim_event(seq=1, time=1.0, source=src, event_id="evt-aaa-001")
    e2 = _sim_event(seq=2, time=1.0, source=src, event_id="evt-aaa-002")
    e3 = _sim_event(seq=3, time=1.0, source=src, event_id="evt-aaa-003")
    e4 = _sim_event(seq=4, time=2.0, source=src, event_id="evt-aaa-004")
    e5 = _sim_event(seq=5, time=3.0, source=src, event_id="evt-aaa-005")
    present = tuple(sorted({e.event_type for e in (e0, e1, e2, e3, e4, e5)}, key=str))
    manifest = _manifest(source=src, available=present)
    return ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=present,
        events=(e0, e1, e2, e3, e4, e5),
        limitations=("a",),
    )


def test_opus_b1_advance_zero_is_noop_from_middle_of_equal_time_group() -> None:
    stream = _equal_time_stream_5()
    engine = ReplayEngine(stream)
    engine.step(2, "forward")
    assert engine.cursor_index == 2
    assert engine.current_event().event_id == "evt-aaa-002"  # type: ignore[union-attr]
    engine.play()
    before_ph = engine.state().playhead_time_s
    before_idx = engine.cursor_index
    r = engine.advance(0.0)
    assert r.resulting_state.cursor.index == before_idx
    assert r.resulting_state.playhead_time_s == before_ph
    assert engine.cursor_index == before_idx
    # also from first and last of group
    engine2 = ReplayEngine(stream)
    engine2.step(1, "forward")
    engine2.play()
    r2 = engine2.advance(0.0)
    assert r2.resulting_state.cursor.index == 1
    engine3 = ReplayEngine(stream)
    engine3.step(3, "forward")
    engine3.play()
    r3 = engine3.advance(0.0)
    assert r3.resulting_state.cursor.index == 3


def test_opus_b1_advance_from_middle_half_and_double_speed() -> None:
    stream = _equal_time_stream_5()
    # half speed
    engine_h = ReplayEngine(stream)
    engine_h.step(2, "forward")
    engine_h.play()
    engine_h.set_speed(0.5)
    engine_h.play()
    before_h = engine_h.state().playhead_time_s
    r_h = engine_h.advance(1.0)
    # effective 0.5, must move exactly one within equal-time group, monotonic, never rewind
    assert r_h.resulting_state.cursor.index == 3
    assert r_h.resulting_state.cursor.event_id == "evt-aaa-003"
    assert r_h.resulting_state.playhead_time_s == pytest.approx(before_h + 0.5)
    assert r_h.resulting_state.cursor.index > 2
    # double speed
    engine_d = ReplayEngine(stream)
    engine_d.step(2, "forward")
    engine_d.play()
    engine_d.set_speed(2.0)
    engine_d.play()
    before_d = engine_d.state().playhead_time_s
    r_d = engine_d.advance(0.5)
    # effective 1.0, also one step within group for our deterministic equal-time handling
    assert r_d.resulting_state.cursor.index == 3
    assert r_d.resulting_state.playhead_time_s == pytest.approx(before_d + 1.0)
    # both preserve stable order by event_id
    assert r_h.resulting_state.cursor.event_id == r_d.resulting_state.cursor.event_id


def test_opus_b1_repeated_fractional_advances_accumulate() -> None:
    # events spaced 1.0 apart: 0.0, 1.0, 2.0, 3.0
    src = _source()
    events = [_sim_event(seq=i, time=float(i), source=src) for i in range(4)]
    stream = _stream_with_events(events)
    engine = ReplayEngine(stream)
    engine.play()
    # playhead starts at 0.0
    assert engine.state().playhead_time_s == 0.0
    # three fractional 0.4 advances should accumulate to 1.2 and only then move to index1
    r1 = engine.advance(0.4)
    assert r1.resulting_state.cursor.index == 0
    assert r1.resulting_state.playhead_time_s == pytest.approx(0.4)
    r2 = engine.advance(0.4)
    assert r2.resulting_state.cursor.index == 0
    assert r2.resulting_state.playhead_time_s == pytest.approx(0.8)
    r3 = engine.advance(0.4)
    assert r3.resulting_state.cursor.index == 1
    assert r3.resulting_state.playhead_time_s == pytest.approx(1.2)
    # further fractional
    r4 = engine.advance(0.4)
    assert r4.resulting_state.cursor.index == 1
    assert r4.resulting_state.playhead_time_s == pytest.approx(1.6)
    r5 = engine.advance(0.4)
    assert r5.resulting_state.cursor.index == 2
    assert r5.resulting_state.playhead_time_s == pytest.approx(2.0)


def test_opus_b1_advance_end_and_pause_explicit() -> None:
    stream = _equal_time_stream_5()
    engine = ReplayEngine(stream)
    engine.play()
    engine.seek(10.0)
    assert engine.is_at_end()
    ph_before = engine.state().playhead_time_s
    r_end = engine.advance(1.0)
    assert r_end.resulting_state.end_of_stream is True
    assert r_end.resulting_state.playback_state is PlaybackState.ENDED
    assert r_end.resulting_state.cursor.is_at_end is True
    assert r_end.resulting_state.playhead_time_s == ph_before
    # pause behavior: advance while paused is no-op
    engine2 = ReplayEngine(stream)
    engine2.step(1, "forward")
    assert engine2.playback_state is PlaybackState.PAUSED
    ph2_before = engine2.state().playhead_time_s
    r_pause = engine2.advance(1.0)
    assert r_pause.resulting_state.cursor.index == 1
    assert r_pause.resulting_state.playback_state is PlaybackState.PAUSED
    assert r_pause.resulting_state.playhead_time_s == ph2_before
    # empty stream
    empty = _stream_with_events([])
    e_engine = ReplayEngine(empty)
    r_empty = e_engine.advance(1.0)
    assert r_empty.resulting_state.empty_stream is True
    assert r_empty.resulting_state.playhead_time_s == 0.0


def test_opus_b1_playhead_bind_through_transitions() -> None:
    stream = _equal_time_stream_5()
    engine = ReplayEngine(stream)
    # initial playhead 0.0
    s0 = engine.state()
    assert s0.playhead_time_s == 0.0
    engine.play()
    s1 = engine.state()
    assert s1.playhead_time_s == 0.0
    assert s1.playback_state is PlaybackState.PLAYING
    engine.pause()
    s2 = engine.state()
    assert s2.playhead_time_s == 0.0
    assert s2.playback_state is PlaybackState.PAUSED
    engine.seek(1.0)
    s3 = engine.state()
    assert s3.playhead_time_s == 1.0
    assert s3.cursor.index == 1
    engine.step(1, "forward")
    s4 = engine.state()
    assert s4.playhead_time_s == 1.0  # same time group, playhead tracks cursor time
    assert s4.cursor.index == 2
    engine.play()
    engine.set_speed(2.0)
    s5 = engine.state()
    assert s5.speed_multiplier == 2.0
    assert s5.playhead_time_s == s4.playhead_time_s
    r = engine.advance(0.5)
    assert r.resulting_state.playhead_time_s == pytest.approx(s5.playhead_time_s + 1.0)
    # receipt binds playhead and is verifiable
    r.resulting_state.verify_against_engine(engine)
    r.verify_against(engine)
    # tamper playhead fails
    forged_state = r.resulting_state.model_copy(update={"playhead_time_s": 999.0})
    with pytest.raises((ValidationError, ReplayEngineError)):
        forged_state.verify_against_engine(engine)

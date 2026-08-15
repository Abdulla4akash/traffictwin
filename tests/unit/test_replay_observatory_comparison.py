"""Side-by-side replay contract: explicit agreement, compatibility and non-causal sync."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.replay_observatory.comparison import (
    CAUSAL_DISCLAIMER,
    AlignmentMode,
    ComparisonAgreementError,
    SideBySideAgreement,
    SideBySideReplay,
)
from traffictwin.replay_observatory.engine import ReplayEngineError
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
    TaskOfferedEvent,
    TaskOfferedPayload,
)

ARTIFACT = "a" * 64
ARTIFACT2 = "b" * 64
ARTIFACT3 = "c" * 64


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
    *, source: SourceIdentity | None = None, available: tuple[EventType, ...] | None = None
) -> SourceCapabilityManifest:
    src = source or _source()
    if available is None:
        available = tuple(sorted(EventType, key=lambda x: str(x)))
    return SourceCapabilityManifest(
        manifest_id="manifest-001",
        source=src,
        source_data_kind=SourceDataKind.EVENT_STREAM,
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


def _stream(
    source: SourceIdentity | None = None,
    events: tuple[ReplayEvent, ...] | list[ReplayEvent] | None = None,
) -> ReplayEventStream:
    src = source or _source()
    if events is None:
        events = [_sim_event(seq=i, time=float(i), source=src) for i in range(3)]
    if not events:
        return ReplayEventStream(
            stream_id="stream-001",
            capability_manifest=_manifest(source=src, available=()),
            present_event_types=(),
            events=(),
            limitations=("a",),
        )
    present = tuple(sorted({e.event_type for e in events}, key=str))
    manifest = _manifest(source=src, available=present)
    return ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=present,
        events=tuple(events),
        limitations=("a",),
    )


def _agreement_for(
    left: ReplayEventStream,
    right: ReplayEventStream,
    **overrides: object,
) -> SideBySideAgreement:
    base: dict[str, object] = {
        "time_basis": "simulator_time_s",
        "time_units": "seconds",
        "alignment": AlignmentMode.CLOCK_ALIGN,
        "tolerance_s": 0.1,
        "window_start_s": 0.0,
        "window_end_s": 10.0,
        "left_stream_fingerprint": left.fingerprint(),
        "right_stream_fingerprint": right.fingerprint(),
        "identity_namespace": "src-001",
        "compatibility_acknowledged": True,
        "declared_event_types": tuple(
            sorted(set(left.present_event_types) & set(right.present_event_types), key=str)
        ),
        "causal_disclaimer": CAUSAL_DISCLAIMER,
    }
    base.update(overrides)
    return SideBySideAgreement.model_validate(base)


# ---------------------------------------------------------------------------
# Explicit agreement required
# ---------------------------------------------------------------------------


def test_side_by_side_requires_explicit_agreement() -> None:
    left = _stream()
    right = _stream(source=_source(source_id="src-001"))  # same namespace
    # Valid agreement succeeds
    agreement = _agreement_for(left, right)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    assert state.agreement_fingerprint == agreement.fingerprint()
    # Missing fingerprints fails (invalid pattern triggers ValidationError via runtime payload)
    with pytest.raises(ValidationError):
        SideBySideAgreement.model_validate(
            {
                "time_basis": "simulator_time_s",
                "time_units": "seconds",
                "alignment": "clock_align",
                "tolerance_s": 0.1,
                "window_start_s": 0.0,
                "window_end_s": 1.0,
                "left_stream_fingerprint": "bad",
                "right_stream_fingerprint": right.fingerprint(),
                "identity_namespace": "src-001",
                "compatibility_acknowledged": True,
                "causal_disclaimer": CAUSAL_DISCLAIMER,
            }
        )


def test_same_time_basis_and_units_enforced() -> None:
    left = _stream()
    right = _stream()
    with pytest.raises(ValidationError):
        _agreement_for(left, right, time_basis="wall_clock")
    with pytest.raises(ValidationError):
        _agreement_for(left, right, time_units="milliseconds")


def test_compatible_source_schema_and_fingerprints() -> None:
    left = _stream()
    right = _stream()
    # fingerprint mismatch fails
    bad_agreement = _agreement_for(left, right, left_stream_fingerprint="f" * 64)
    with pytest.raises(ComparisonAgreementError, match="FINGERPRINT"):
        SideBySideReplay(left, right, bad_agreement)
    # schema version mismatch fails
    other_src = SourceIdentity(
        source_id="src-001",
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256=ARTIFACT2,
        schema_version="2.0",
    )
    right2 = _stream(source=other_src, events=[_sim_event(seq=0, time=0.0, source=other_src)])
    agreement = SideBySideAgreement(
        time_basis="simulator_time_s",
        time_units="seconds",
        alignment=AlignmentMode.CLOCK_ALIGN,
        tolerance_s=0.1,
        window_start_s=0.0,
        window_end_s=10.0,
        left_stream_fingerprint=left.fingerprint(),
        right_stream_fingerprint=right2.fingerprint(),
        identity_namespace="src-001",
        compatibility_acknowledged=True,
        declared_event_types=(),
        causal_disclaimer=CAUSAL_DISCLAIMER,
    )
    with pytest.raises(ComparisonAgreementError, match="INCOMPATIBLE_SCHEMA"):
        SideBySideReplay(left, right2, agreement)


def test_compatible_event_availability_and_identity_namespace() -> None:
    src_a = _source(source_id="src-a")
    src_b = _source(source_id="src-b")
    # left declares simulation_time, right declares vehicle_state disjoint ->
    # declared empty is OK but declaring unavailable fails
    from traffictwin.replay_observatory.models import VehicleStateEvent, VehicleStatePayload

    left = _stream(source=src_a, events=[_sim_event(seq=0, time=0.0, source=src_a)])
    veh_evt = VehicleStateEvent(
        event_id="evt-veh-000",
        sequence=0,
        simulator_time_s=0.0,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
        source=src_b,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src_b.artifact_sha256, record="rec-veh-000"),
        payload=VehicleStatePayload(x_m=1.0, y_m=1.0, speed_mps=1.0),
    )
    right = ReplayEventStream(
        stream_id="s-right",
        capability_manifest=_manifest(source=src_b, available=(EventType.VEHICLE_STATE,)),
        present_event_types=(EventType.VEHICLE_STATE,),
        events=(veh_evt,),
        limitations=("a",),
    )
    # declaring vehicle_state as common should fail because left lacks it
    with pytest.raises(ComparisonAgreementError, match="INCOMPATIBLE_CAPABILITIES"):
        bad = _agreement_for(left, right, declared_event_types=(EventType.VEHICLE_STATE,))
        SideBySideReplay(left, right, bad)
    # empty declared types is compatible (truthful unavailable)
    good = _agreement_for(left, right, declared_event_types=())
    replay = SideBySideReplay(left, right, good)
    state = replay.synchronized_state()
    assert EventType.VEHICLE_STATE in state.unavailable_left_event_types
    assert EventType.SIMULATION_TIME in state.unavailable_right_event_types


def test_declared_alignment_tolerance_window_validation() -> None:
    left = _stream()
    right = _stream()
    # tolerance negative fails
    with pytest.raises(ValidationError):
        _agreement_for(left, right, tolerance_s=-1.0)
    # window end < start fails
    with pytest.raises(ValidationError):
        _agreement_for(left, right, window_start_s=5.0, window_end_s=2.0)
    # nonfinite tolerance
    with pytest.raises(ValidationError):
        _agreement_for(left, right, tolerance_s=float("inf"))
    # window too large
    with pytest.raises(ValidationError):
        _agreement_for(left, right, window_start_s=0.0, window_end_s=1_000_000.0)


def test_synchronization_not_evidence_of_causality_explicit() -> None:
    left = _stream()
    right = _stream()
    agreement = _agreement_for(left, right)
    assert agreement.causal_disclaimer == CAUSAL_DISCLAIMER
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    assert state.causal_disclaimer == CAUSAL_DISCLAIMER
    assert "not evidence of causality" in state.causal_disclaimer
    receipt = replay.synchronized_receipt()
    assert receipt.causal_disclaimer == CAUSAL_DISCLAIMER
    # Immutable fingerprints carried
    assert receipt.left_stream_fingerprint == left.fingerprint()
    assert receipt.right_stream_fingerprint == right.fingerprint()
    assert receipt.agreement_fingerprint == agreement.fingerprint()


def test_never_fabricate_missing_event_rsu_execution_target() -> None:
    # left has task_offered but no execution_target
    src = _source()
    offer = TaskOfferedEvent(
        event_id="evt-offer-001",
        sequence=0,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-offer-001"),
        payload=TaskOfferedPayload(offered_to_entity_id="res-001"),
    )
    left = ReplayEventStream(
        stream_id="left-offer",
        capability_manifest=_manifest(source=src, available=(EventType.TASK_OFFERED,)),
        present_event_types=(EventType.TASK_OFFERED,),
        events=(offer,),
        limitations=("a",),
    )
    right = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    agreement = _agreement_for(left, right, declared_event_types=(), window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    assert state.missing_execution_target is True
    # No fabrication: windows contain only present events
    assert all(ev.event_type is not EventType.EXECUTION_TARGET for ev in state.left_window)
    assert all(ev.event_type is not EventType.EXECUTION_TARGET for ev in state.right_window)


def test_research_aggregate_remains_zero_event_unavailable() -> None:
    agg_src = SourceIdentity(
        source_id="agg-src",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT3,
        schema_version="1.0",
    )
    agg_manifest = SourceCapabilityManifest(
        manifest_id="m-agg",
        source=agg_src,
        source_data_kind=SourceDataKind.AGGREGATE_ONLY,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=("Aggregate only", "Research aggregate"),
    )
    agg_stream = ReplayEventStream(
        stream_id="agg-stream",
        capability_manifest=agg_manifest,
        present_event_types=(),
        events=(),
        limitations=("Aggregate only",),
    )
    left = _stream()
    agreement = SideBySideAgreement(
        time_basis="simulator_time_s",
        time_units="seconds",
        alignment=AlignmentMode.CLOCK_ALIGN,
        tolerance_s=0.1,
        window_start_s=0.0,
        window_end_s=10.0,
        left_stream_fingerprint=left.fingerprint(),
        right_stream_fingerprint=agg_stream.fingerprint(),
        identity_namespace="src-001",
        compatibility_acknowledged=True,
        declared_event_types=(),
        causal_disclaimer=CAUSAL_DISCLAIMER,
    )
    replay = SideBySideReplay(left, agg_stream, agreement)
    state = replay.synchronized_state()
    assert state.aggregate_unavailable is True
    assert state.right_window == ()
    # Attempt to declare events on aggregate fails
    with pytest.raises(ComparisonAgreementError, match="AGGREGATE"):
        bad_agreement = SideBySideAgreement(
            time_basis="simulator_time_s",
            time_units="seconds",
            alignment=AlignmentMode.CLOCK_ALIGN,
            tolerance_s=0.1,
            window_start_s=0.0,
            window_end_s=10.0,
            left_stream_fingerprint=left.fingerprint(),
            right_stream_fingerprint=agg_stream.fingerprint(),
            identity_namespace="src-001",
            compatibility_acknowledged=True,
            declared_event_types=(EventType.SIMULATION_TIME,),
            causal_disclaimer=CAUSAL_DISCLAIMER,
        )
        SideBySideReplay(left, agg_stream, bad_agreement)


def test_scale_and_resource_are_generic_source_present_only() -> None:
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
    # Comparison with generic streams preserves payloads verbatim, no scaling interpretation
    right = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    agreement = _agreement_for(stream, right, declared_event_types=(), window_end_s=10.0)
    replay = SideBySideReplay(stream, right, agreement)
    state = replay.synchronized_state()
    # Left window contains generic events as stored
    assert any(ev.event_type is EventType.RESOURCE_STATE for ev in state.left_window)
    assert any(ev.event_type is EventType.SCALE_ACTION for ev in state.left_window)
    # No inferred P2C or stale state
    rs = [e for e in state.left_window if e.event_type is EventType.RESOURCE_STATE][0]
    # Narrow to ResourceStateEvent for typed payload access
    assert isinstance(rs.payload, ResourceStatePayload)
    assert rs.payload.measurements[0].metric_id == "cpu_load"


def test_side_by_side_state_and_controls_discriminated() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    # seek both aligns cursors without claiming causality
    receipt = replay.seek_both(2.0)
    assert receipt.resulting_state.left_state.cursor.index == 2
    assert receipt.resulting_state.right_state.cursor.index == 2
    assert receipt.causal_disclaimer == CAUSAL_DISCLAIMER
    # step both
    receipt2 = replay.step_both(1, "forward")
    assert receipt2.resulting_state.left_state.cursor.index == 3
    # invalid seek fails closed
    with pytest.raises(ComparisonAgreementError):
        replay.seek_both(-1.0)
    with pytest.raises(ComparisonAgreementError):
        replay.seek_both(float("inf"))


def test_fingerprints_immutable_and_canonical() -> None:
    left = _stream()
    right = _stream()
    agreement = _agreement_for(left, right)
    fp1 = agreement.fingerprint()
    fp2 = agreement.fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 64
    # Tampered agreement fingerprint mismatched on construction fails
    bad = _agreement_for(left, right, left_stream_fingerprint="a" * 64)
    with pytest.raises(ComparisonAgreementError):
        SideBySideReplay(left, right, bad)


def test_missing_execution_target_detection_side_by_side() -> None:
    # Both streams without execution target should be flagged correctly but not fabricated
    src = _source()
    # stream with only simulation_time, no task events -> not missing execution target (no offer)
    left = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    right = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    agreement = _agreement_for(left, right)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    assert state.missing_execution_target is False
    # Side-by-side engine must not invent execution_target
    assert state.left_window == tuple(e for e in left.events if 0.0 <= e.simulator_time_s <= 10.0)


def test_incompatible_identity_namespace_still_requires_explicit() -> None:
    left = _stream(source=_source(source_id="alpha-src"))
    right = _stream(source=_source(source_id="beta-src"))
    # explicit namespace declared is required; we test that frozen validation holds
    agreement = _agreement_for(left, right, identity_namespace="alpha-src")
    # construction succeeds because we allow distinct namespaces when explicitly declared
    replay = SideBySideReplay(left, right, agreement)
    assert replay.agreement.identity_namespace == "alpha-src"
    # invalid namespace fails strict validation
    with pytest.raises(ValidationError):
        _agreement_for(left, right, identity_namespace="bad namespace with spaces")


# ---------------------------------------------------------------------------
# Additional hardening: forged agreement/stream, window, namespace, disclaimer
# ---------------------------------------------------------------------------


def test_forged_stream_manifest_via_model_copy_fails_side_by_side() -> None:
    left = _stream()
    right = _stream()
    # Forge left by adding invented event
    extra = _sim_event(seq=99, time=99.0, source=_source())
    forged_left = left.model_copy(update={"events": tuple(list(left.events) + [extra])})
    agreement = _agreement_for(left, right)
    # Using original left/right fingerprints agreement will mismatch forged left
    with pytest.raises(ComparisonAgreementError):
        SideBySideReplay(forged_left, right, agreement)
    # Also forging agreement fingerprint fails
    forged_agreement = agreement.model_copy(update={"left_stream_fingerprint": "f" * 64})
    with pytest.raises(ComparisonAgreementError):
        # revalidation will catch fingerprint mismatch or tamper
        SideBySideReplay(left, right, forged_agreement)


def test_wrong_agreement_stream_window_fails() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=2.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    # Tamper state window: forge left_window outside agreement window
    tampered_state = state.model_copy(
        update={"left_window": (_sim_event(seq=0, time=5.0, source=_source()),)}
    )
    # model_copy bypasses validation, so verify should fail
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        tampered_state.verify_against(left, right)
    # Wrong stream fingerprint in receipt fails
    receipt = replay.synchronized_receipt()
    forged_receipt = receipt.model_copy(update={"left_stream_fingerprint": "b" * 64})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_receipt.verify_against(left, right)
    # Stale stream: modify underlying stream to have extra event, then verify should fail
    forged_left = left.model_copy(
        update={"events": tuple(list(left.events) + [_sim_event(seq=10, time=10.0)])}
    )
    with pytest.raises(ComparisonAgreementError):
        receipt.verify_against(forged_left, right)


def test_namespace_mismatch_fails() -> None:
    left = _stream(source=_source(source_id="alpha-src"))
    right = _stream(source=_source(source_id="beta-src"))
    # Common namespace applies to both; left/right explicit must match
    with pytest.raises(ValidationError):
        _agreement_for(
            left, right, identity_namespace="alpha-src", left_identity_namespace="wrong-ns"
        )
    with pytest.raises(ValidationError):
        _agreement_for(
            left, right, identity_namespace="alpha-src", right_identity_namespace="other-ns"
        )
    # Missing compatibility acknowledgement fails
    with pytest.raises(ValidationError):
        SideBySideAgreement.model_validate(
            {
                "time_basis": "simulator_time_s",
                "time_units": "seconds",
                "alignment": "clock_align",
                "tolerance_s": 0.1,
                "window_start_s": 0.0,
                "window_end_s": 10.0,
                "left_stream_fingerprint": left.fingerprint(),
                "right_stream_fingerprint": right.fingerprint(),
                "identity_namespace": "alpha-src",
                "compatibility_acknowledged": False,
                "causal_disclaimer": CAUSAL_DISCLAIMER,
            }
        )


def test_causal_disclaimer_required_and_bound() -> None:
    left = _stream()
    right = _stream()
    # Exact disclaimer required on agreement
    with pytest.raises(ValidationError):
        _agreement_for(left, right, causal_disclaimer="causality claimed")
    agreement = _agreement_for(left, right)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    receipt = replay.synchronized_receipt()
    assert state.causal_disclaimer == CAUSAL_DISCLAIMER
    assert receipt.causal_disclaimer == CAUSAL_DISCLAIMER
    # Forge state disclaimer via model_copy bypasses validation, verify catches
    tampered_state = state.model_copy(update={"causal_disclaimer": "bad"})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        tampered_state.verify_against(left, right)
    tampered_receipt = receipt.model_copy(update={"causal_disclaimer": "bad"})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        tampered_receipt.verify_against(left, right)
    # Forge agreement disclaimer via model_copy should be caught
    _ = agreement.model_copy(update={"causal_disclaimer": CAUSAL_DISCLAIMER})
    # No-op copy still passes; but creating with wrong value fails
    with pytest.raises(ValidationError):
        SideBySideAgreement.model_validate(
            {
                **agreement.model_dump(mode="json"),
                "causal_disclaimer": "synchronization is causality",
            }
        )


def test_side_by_side_receipt_and_state_exact_verifiers() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    agreement = _agreement_for(left, right)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    receipt = replay.synchronized_receipt()
    # Exact verifiers pass on canonical
    state.verify_against(left, right)
    state.verify_exact(left, right)
    receipt.verify_against(left, right)
    receipt.verify_exact(left, right)
    # Tamper agreement fingerprint inside state should fail
    forged_state = state.model_copy(update={"agreement_fingerprint": "0" * 64})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_state.verify_against(left, right)
    # Tamper stream fingerprint inside receipt
    forged_receipt = receipt.model_copy(update={"agreement_fingerprint": "1" * 64})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_receipt.verify_against(left, right)
    # Verify before and after transitions: SideBySideReplay verifies integrity
    # Mutate underlying stream to simulate tamper, next operation should fail
    object.__setattr__(replay, "_left_stream", left.model_copy(update={"events": ()}))
    with pytest.raises(ComparisonAgreementError):
        replay.synchronized_state()


def test_side_by_side_operations_verify_integrity_before_after() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(4)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(4)])
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    # seek and step should verify before/after
    r1 = replay.seek_both(1.0)
    assert r1.resulting_state.left_state.cursor.index == 1
    r2 = replay.step_both(1, "forward")
    assert r2.resulting_state.right_state.cursor.index == 2
    # Tamper right stream fingerprint mismatch should be caught on next seek
    object.__setattr__(replay, "_right_stream", right.model_copy(update={"events": ()}))
    with pytest.raises(ComparisonAgreementError):
        replay.step_both(1, "forward")


def test_compatibility_schema_and_identity_namespace_enforced() -> None:
    # Same replay schema/source schema required
    src_v1 = SourceIdentity(
        source_id="src-001",
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256=ARTIFACT,
        schema_version="1.0",
    )
    src_v2 = SourceIdentity(
        source_id="src-001",
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256=ARTIFACT2,
        schema_version="2.0",
    )
    left = _stream(source=src_v1)
    right = _stream(source=src_v2, events=[_sim_event(seq=0, time=0.0, source=src_v2)])
    with pytest.raises(ComparisonAgreementError, match="INCOMPATIBLE_SCHEMA"):
        SideBySideReplay(left, right, _agreement_for(left, right))
    # Declared types must be present, not just available
    src = _source()
    left2 = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    right2 = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    # Try to declare vehicle_state which is not present
    with pytest.raises(ComparisonAgreementError, match="INCOMPATIBLE_CAPABILITIES"):
        bad = _agreement_for(left2, right2, declared_event_types=(EventType.VEHICLE_STATE,))
        SideBySideReplay(left2, right2, bad)
    # Aggregate never gains events: declare events on aggregate fails
    agg_src = SourceIdentity(
        source_id="agg-src",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT3,
        schema_version="1.0",
    )
    agg_manifest = SourceCapabilityManifest(
        manifest_id="m-agg",
        source=agg_src,
        source_data_kind=SourceDataKind.AGGREGATE_ONLY,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=("a",),
    )
    agg_stream = ReplayEventStream(
        stream_id="agg-stream",
        capability_manifest=agg_manifest,
        present_event_types=(),
        events=(),
        limitations=("a",),
    )
    left3 = _stream()
    with pytest.raises(ComparisonAgreementError, match="AGGREGATE"):
        bad2 = SideBySideAgreement(
            time_basis="simulator_time_s",
            time_units="seconds",
            alignment=AlignmentMode.CLOCK_ALIGN,
            tolerance_s=0.1,
            window_start_s=0.0,
            window_end_s=10.0,
            left_stream_fingerprint=left3.fingerprint(),
            right_stream_fingerprint=agg_stream.fingerprint(),
            identity_namespace="src-001",
            compatibility_acknowledged=True,
            declared_event_types=(EventType.SIMULATION_TIME,),
            causal_disclaimer=CAUSAL_DISCLAIMER,
        )
        SideBySideReplay(left3, agg_stream, bad2)


def test_missing_execution_target_truthful_no_synthesis() -> None:
    src = _source()
    offer = TaskOfferedEvent(
        event_id="evt-offer-002",
        sequence=0,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-002"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-offer-002"),
        payload=TaskOfferedPayload(offered_to_entity_id="res-002"),
    )
    left = ReplayEventStream(
        stream_id="left-offer2",
        capability_manifest=_manifest(source=src, available=(EventType.TASK_OFFERED,)),
        present_event_types=(EventType.TASK_OFFERED,),
        events=(offer,),
        limitations=("a",),
    )
    right = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    agreement = _agreement_for(left, right, declared_event_types=(), window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    assert state.missing_execution_target is True
    # Windows truthfully do not contain execution_target
    assert all(ev.event_type is not EventType.EXECUTION_TARGET for ev in state.left_window)
    assert all(ev.event_type is not EventType.EXECUTION_TARGET for ev in state.right_window)
    # Receipt also truthful
    receipt = replay.synchronized_receipt()
    assert receipt.resulting_state.missing_execution_target is True
    # No synthesis after seek/step
    replay.seek_both(0.0)
    state2 = replay.synchronized_state()
    assert state2.missing_execution_target is True


# ---------------------------------------------------------------------------
# Opus B2 discriminating probes: exact windows, cursors, unavailable, aggregate, stale
# ---------------------------------------------------------------------------


def test_opus_b2_window_prefix_not_allowed() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    # exact full window has 5 events each (0..4)
    assert len(state.left_window) == 5
    # truncate to prefix should fail verification
    truncated = state.model_copy(update={"left_window": state.left_window[:2]})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        truncated.verify_against(left, right)
    truncated_r = state.model_copy(update={"right_window": state.right_window[:1]})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        truncated_r.verify_against(left, right)
    # empty prefix also fails when window non-empty
    empty_prefix = state.model_copy(update={"left_window": ()})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        empty_prefix.verify_against(left, right)


def test_opus_b2_forged_aggregate_unavailable_rejected() -> None:
    left = _stream()
    agg_src = SourceIdentity(
        source_id="agg-src",
        source_kind=SourceKind.RESEARCH_AGGREGATE,
        artifact_sha256=ARTIFACT3,
        schema_version="1.0",
    )
    agg_manifest = SourceCapabilityManifest(
        manifest_id="m-agg",
        source=agg_src,
        source_data_kind=SourceDataKind.AGGREGATE_ONLY,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=(),
        limitations=("Aggregate only",),
    )
    agg_stream = ReplayEventStream(
        stream_id="agg-stream",
        capability_manifest=agg_manifest,
        present_event_types=(),
        events=(),
        limitations=("Aggregate only",),
    )
    agreement = SideBySideAgreement(
        time_basis="simulator_time_s",
        time_units="seconds",
        alignment=AlignmentMode.CLOCK_ALIGN,
        tolerance_s=0.1,
        window_start_s=0.0,
        window_end_s=10.0,
        left_stream_fingerprint=left.fingerprint(),
        right_stream_fingerprint=agg_stream.fingerprint(),
        identity_namespace="src-001",
        compatibility_acknowledged=True,
        declared_event_types=(),
        causal_disclaimer=CAUSAL_DISCLAIMER,
    )
    replay = SideBySideReplay(left, agg_stream, agreement)
    state = replay.synchronized_state()
    assert state.aggregate_unavailable is True
    receipt = replay.synchronized_receipt()
    assert receipt.resulting_state.aggregate_unavailable is True
    # forge to false should fail
    forged_state = state.model_copy(update={"aggregate_unavailable": False})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_state.verify_against(left, agg_stream)
    forged_receipt_state = receipt.resulting_state.model_copy(
        update={"aggregate_unavailable": False}
    )
    forged_receipt = receipt.model_copy(update={"resulting_state": forged_receipt_state})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_receipt.verify_against(left, agg_stream)


def test_opus_b2_erased_unavailable_types_rejected() -> None:
    src_a = _source(source_id="src-a")
    src_b = _source(source_id="src-b")
    from traffictwin.replay_observatory.models import VehicleStateEvent, VehicleStatePayload

    left = _stream(source=src_a, events=[_sim_event(seq=0, time=0.0, source=src_a)])
    veh_evt = VehicleStateEvent(
        event_id="evt-veh-000",
        sequence=0,
        simulator_time_s=0.0,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
        source=src_b,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src_b.artifact_sha256, record="rec-veh-000"),
        payload=VehicleStatePayload(x_m=1.0, y_m=1.0, speed_mps=1.0),
    )
    right = ReplayEventStream(
        stream_id="s-right",
        capability_manifest=SourceCapabilityManifest(
            manifest_id="m1",
            source=src_b,
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            available_event_types=(EventType.VEHICLE_STATE,),
            limitations=("a",),
        ),
        present_event_types=(EventType.VEHICLE_STATE,),
        events=(veh_evt,),
        limitations=("a",),
    )
    agreement = _agreement_for(left, right, declared_event_types=())
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    # left is missing vehicle_state, right missing simulation_time
    assert EventType.VEHICLE_STATE in state.unavailable_left_event_types
    assert EventType.SIMULATION_TIME in state.unavailable_right_event_types
    # erase unavailable types should fail
    forged_left_erased = state.model_copy(update={"unavailable_left_event_types": ()})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_left_erased.verify_against(left, right)
    forged_right_erased = state.model_copy(update={"unavailable_right_event_types": ()})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_right_erased.verify_against(left, right)
    # duplicate should also fail via exact verifier (model_copy bypasses validation)
    forged_dup = state.model_copy(
        update={"unavailable_left_event_types": (EventType.VEHICLE_STATE, EventType.VEHICLE_STATE)}
    )
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_dup.verify_against(left, right)


def test_opus_b2_stale_receipt_after_transition_fails() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(5)])
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    receipt_before = replay.synchronized_receipt()
    # structural verify passes against current streams
    receipt_before.verify_against(left, right)
    # transition both engines
    replay.seek_both(3.0)
    state_after = replay.synchronized_state()
    assert state_after.left_state.cursor.index == 3
    assert receipt_before.resulting_state.left_state.cursor.index == 0
    # stale receipt must fail via its own exact live verifier
    with pytest.raises(ComparisonAgreementError):
        receipt_before.verify_against_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        receipt_before.resulting_state.verify_against_replay(replay)
    # structural stream-only verify still passes (window exact, not live)
    receipt_before.verify_against(left, right)
    # live mismatch also via nested engine verifier
    with pytest.raises(ReplayEngineError):
        receipt_before.resulting_state.left_state.verify_against_engine(replay.left_engine)
    assert (
        receipt_before.resulting_state.left_state.cursor.index
        != state_after.left_state.cursor.index
    )
    # current receipt/state must pass exact live verifier
    receipt_after = replay.synchronized_receipt()
    receipt_after.verify_against(left, right)
    receipt_after.verify_against_replay(replay)
    receipt_after.resulting_state.verify_against_replay(replay)
    receipt_after.resulting_state.left_state.verify_against_engine(replay.left_engine)
    # stale state directly fails live check
    stale_state = receipt_before.resulting_state
    with pytest.raises(ComparisonAgreementError):
        stale_state.verify_against_replay(replay)
    # step_both also makes previous receipt stale
    replay.step_both(1, "forward")
    with pytest.raises(ComparisonAgreementError):
        receipt_after.verify_against_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        receipt_after.resulting_state.verify_against_replay(replay)


def test_opus_b2_missing_execution_target_per_task_precise() -> None:
    src = _source()
    # offered task-001 and task-002, only task-001 has execution target
    offer1 = TaskOfferedEvent(
        event_id="evt-offer-001",
        sequence=0,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-offer-001"),
        payload=TaskOfferedPayload(offered_to_entity_id="res-001"),
    )
    offer2 = TaskOfferedEvent(
        event_id="evt-offer-002",
        sequence=1,
        simulator_time_s=2.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-002"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-offer-002"),
        payload=TaskOfferedPayload(offered_to_entity_id="res-002"),
    )
    from traffictwin.replay_observatory.models import ExecutionTargetEvent, ExecutionTargetPayload

    exec1 = ExecutionTargetEvent(
        event_id="evt-exec-001",
        sequence=2,
        simulator_time_s=3.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-exec-001"),
        payload=ExecutionTargetPayload(execution_resource_id="res-001"),
    )
    # stream has offer1, offer2 but only exec1 -> missing for task-002
    present = tuple(sorted([EventType.TASK_OFFERED, EventType.EXECUTION_TARGET], key=str))
    manifest = SourceCapabilityManifest(
        manifest_id="m-precise",
        source=src,
        source_data_kind=SourceDataKind.EVENT_STREAM,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=present,
        limitations=("a",),
    )
    left = ReplayEventStream(
        stream_id="left-precise",
        capability_manifest=manifest,
        present_event_types=present,
        events=(offer1, offer2, exec1),
        limitations=("a",),
    )
    right = _stream(source=src, events=[_sim_event(seq=0, time=0.0, source=src)])
    agreement = _agreement_for(left, right, declared_event_types=(), window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    # precise per-task: task-002 missing -> true
    assert state.missing_execution_target is True
    # now add exec for task-002, missing should be false
    exec2 = ExecutionTargetEvent(
        event_id="evt-exec-002",
        sequence=3,
        simulator_time_s=4.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-002"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record="rec-exec-002"),
        payload=ExecutionTargetPayload(execution_resource_id="res-002"),
    )
    left2 = ReplayEventStream(
        stream_id="left-precise2",
        capability_manifest=manifest,
        present_event_types=present,
        events=(offer1, offer2, exec1, exec2),
        limitations=("a",),
    )
    agreement2 = _agreement_for(left2, right, declared_event_types=(), window_end_s=10.0)
    replay2 = SideBySideReplay(left2, right, agreement2)
    state2 = replay2.synchronized_state()
    assert state2.missing_execution_target is False
    # forged missing false when actually true should fail
    forged = state.model_copy(update={"missing_execution_target": False})
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged.verify_against(left, right)


def test_opus_b2_max_events_bound_and_duplicate_unavailable() -> None:
    left = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    right = _stream(events=[_sim_event(seq=i, time=float(i)) for i in range(3)])
    agreement = _agreement_for(left, right)
    replay = SideBySideReplay(left, right, agreement)
    # max_events 0 should be rejected
    with pytest.raises(ReplayEngineError):
        replay.left_engine.load_time_window(0.0, 10.0, max_events=0)
    # duplicate unavailable should be rejected via verifier
    state = replay.synchronized_state()
    forged_dup2 = state.model_copy(
        update={"unavailable_left_event_types": (EventType.VEHICLE_STATE, EventType.VEHICLE_STATE)}
    )
    with pytest.raises((ValidationError, ComparisonAgreementError)):
        forged_dup2.verify_against(left, right)


# ---------------------------------------------------------------------------
# Remediation BLOCKER 2: stale same-timestamp state/receipt must fail live verification
# ---------------------------------------------------------------------------


def _same_time_stream(num: int = 3, time: float = 5.0) -> ReplayEventStream:
    src = _source()
    evs = []
    for i in range(num):
        evs.append(_sim_event(seq=i, time=time, source=src, event_id=f"evt-same-{i:03d}"))
    present = tuple(sorted({e.event_type for e in evs}, key=str))
    manifest = SourceCapabilityManifest(
        manifest_id="m-same",
        source=src,
        source_data_kind=SourceDataKind.EVENT_STREAM,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=present,
        limitations=("a",),
    )
    return ReplayEventStream(
        stream_id=f"stream-same-{num}",
        capability_manifest=manifest,
        present_event_types=present,
        events=tuple(evs),
        limitations=("a",),
    )


def test_remediation_stale_same_timestamp_left_right_both_states() -> None:
    left = _same_time_stream(3, 5.0)
    right = _same_time_stream(3, 5.0)
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    stale_state = replay.synchronized_state()
    stale_receipt = replay.synchronized_receipt()
    # Current objects must pass live verification
    stale_state.verify_against_replay(replay)
    stale_state.verify_exact_replay(replay)
    stale_receipt.verify_against_replay(replay)
    stale_receipt.verify_exact_replay(replay)
    # Structural verifier passes for stale (intentionally not live)
    stale_state.verify_against(left, right)
    stale_state.verify_exact(left, right)
    stale_receipt.verify_against(left, right)
    # After step_both(1), cursor moves from index0 to index1 (same time 5.0)
    replay.step_both(1, "forward")
    cur_state = replay.synchronized_state()
    cur_receipt = replay.synchronized_receipt()
    # Current must pass
    cur_state.verify_against_replay(replay)
    cur_receipt.verify_against_replay(replay)
    # Stale must now fail live verification despite same timestamp (playhead same)
    with pytest.raises(ComparisonAgreementError):
        stale_state.verify_against_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        stale_state.verify_exact_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        stale_receipt.verify_against_replay(replay)
    # Structural still passes (not live)
    stale_state.verify_against(left, right)
    stale_receipt.verify_against(left, right)
    # Hybrid stale left: left stale but right current should fail live, but structural
    # still passes because left cursor remains self-consistent.
    hybrid_left_stale = cur_state.model_copy(update={"left_state": stale_state.left_state})
    # Structural (stream-only) passes because stale left is still self-consistent.
    hybrid_left_stale.verify_against(left, right)
    # Live must fail due to left index mismatch.
    with pytest.raises(ComparisonAgreementError):
        hybrid_left_stale.verify_against_replay(replay)
    # Verify that left index stale fails even though playhead time equal (5.0)
    assert (
        stale_state.left_state.cursor.simulator_time_s
        == cur_state.left_state.cursor.simulator_time_s
        == 5.0
    )
    assert stale_state.left_state.cursor.index != cur_state.left_state.cursor.index
    hybrid = stale_state
    with pytest.raises(ComparisonAgreementError):
        hybrid.verify_against_replay(replay)
    # Right-only stale similarly
    right_stale = replay.synchronized_state()
    replay.step_both(1, "forward")  # now at index2
    newer = replay.synchronized_state()
    assert right_stale.right_state.cursor.index == 1
    assert newer.right_state.cursor.index == 2
    assert (
        right_stale.right_state.cursor.simulator_time_s
        == newer.right_state.cursor.simulator_time_s
        == 5.0
    )
    with pytest.raises(ComparisonAgreementError):
        right_stale.verify_against_replay(replay)
    # Both stale (original) still fails after two steps
    with pytest.raises(ComparisonAgreementError):
        stale_state.verify_against_replay(replay)


def test_remediation_stale_same_timestamp_receipts_left_right() -> None:
    left = _same_time_stream(3, 5.0)
    right = _same_time_stream(3, 5.0)
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    r0 = replay.synchronized_receipt()
    r0.verify_against_replay(replay)
    replay.step_both(1, "forward")
    r1 = replay.synchronized_receipt()
    r1.verify_against_replay(replay)
    # r0 is stale (index0) must fail live even though same time
    with pytest.raises(ComparisonAgreementError):
        r0.verify_against_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        r0.verify_exact_replay(replay)
    # structural still passes
    r0.verify_against(left, right)
    # left/right both checked via state inside receipt; ensure cursor index mismatch triggers
    assert r0.resulting_state.left_state.cursor.index == 0
    assert r1.resulting_state.left_state.cursor.index == 1
    assert r0.resulting_state.left_state.cursor.simulator_time_s == 5.0
    # paused/playing: step sets paused, but verify still requires exact cursor
    assert r1.resulting_state.left_state.cursor.index == 1
    # After another step, r1 becomes stale
    replay.step_both(1, "forward")
    with pytest.raises(ComparisonAgreementError):
        r1.verify_against_replay(replay)


def test_remediation_stale_after_seek_same_timestamp() -> None:
    left = _same_time_stream(3, 5.0)
    right = _same_time_stream(3, 5.0)
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    # Seek to 5.0 lands on first of group (paused)
    replay.seek_both(5.0)
    s_seek = replay.synchronized_state()
    r_seek = replay.synchronized_receipt()
    s_seek.verify_against_replay(replay)
    r_seek.verify_against_replay(replay)
    # Step to next sibling (still paused after step)
    replay.step_both(1, "forward")
    with pytest.raises(ComparisonAgreementError):
        s_seek.verify_against_replay(replay)
    with pytest.raises(ComparisonAgreementError):
        r_seek.verify_against_replay(replay)
    # Current passes
    cur = replay.synchronized_state()
    cur.verify_against_replay(replay)
    # Structural verifier for s_seek still passes (not live)
    s_seek.verify_against(left, right)


def test_remediation_structural_vs_live_verifier_naming() -> None:
    left = _same_time_stream(3, 5.0)
    right = _same_time_stream(3, 5.0)
    agreement = _agreement_for(left, right, window_start_s=0.0, window_end_s=10.0)
    replay = SideBySideReplay(left, right, agreement)
    state = replay.synchronized_state()
    receipt = replay.synchronized_receipt()
    # Structural verifiers are clearly named and do not assert freshness
    state.verify_against(left, right)
    state.verify_exact(left, right)
    receipt.verify_against(left, right)
    receipt.verify_exact(left, right)
    # Live verifiers are clearly separate
    state.verify_against_replay(replay)
    state.verify_exact_replay(replay)
    receipt.verify_against_replay(replay)
    receipt.verify_exact_replay(replay)
    # After stale, structural still passes but live fails
    replay.step_both(1, "forward")
    state.verify_against(left, right)  # structural still passes
    with pytest.raises(ComparisonAgreementError):
        state.verify_against_replay(replay)

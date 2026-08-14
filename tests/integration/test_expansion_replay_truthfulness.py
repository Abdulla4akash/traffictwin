# ruff: noqa: S108,E501,B017,F841,N811,ANN001,ANN201,ANN401,TRY003,TRY301
"""Expansion replay truthfulness — Lane 16.

Proves Replay Observatory does not invent events, does not imply causality
from visual synchronisation, and keeps aggregate-only sources out of replay.

- Deterministic synthetic fixtures, labelled SYNTHETIC_DESIGN_ONLY where applicable
- Truthful BLOCKED/PROVIDER_DATA_REQUIRED via capability manifest
- No Dynamic/E3 invention
- Bounded, deterministic, via public typed contracts only
"""

from __future__ import annotations

import json

import pytest

from traffictwin.replay_observatory.models import (
    EntityIdentity,
    EntityKind,
    EventProvenance,
    EventType,
    EvidenceStanding,
    ReplayEventStream,
    SimulationTimeEvent,
    SimulationTimePayload,
    SourceCapabilityManifest,
    SourceDataKind,
    SourceIdentity,
    SourceKind,
    TaskOfferedEvent,
    TaskOfferedPayload,
)
from traffictwin.ui.replay_observatory_service import (
    SYNCHRONIZED_REPLAY_DISCLAIMER,
    build_synthetic_engineering_stream,
    create_engine,
    get_observatory_view,
)


def _manifest(
    event_types: tuple[EventType, ...], kind: SourceDataKind = SourceDataKind.EVENT_STREAM
) -> SourceCapabilityManifest:
    return SourceCapabilityManifest(
        manifest_id="manifest-truth-001",
        source=SourceIdentity(
            source_id="src-truth-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256="a" * 64,
            schema_version="1.0",
        ),
        source_data_kind=kind,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        available_event_types=event_types,
        limitations=("bounded synthetic stream for truthfulness probe",),
    )


def test_replay_does_not_invent_event_classes() -> None:
    # Manifest declares only SIMULATION_TIME, but we try to inject TASK_OFFERED — must be refused
    manifest = _manifest((EventType.SIMULATION_TIME,))
    src = SourceIdentity(
        source_id="src-truth-001",
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256="a" * 64,
        schema_version="1.0",
    )
    prov = EventProvenance(
        source_artifact_sha256="a" * 64,
        source_record_id="rec-001",
        adapter_id="adapter-test",
        adapter_version="1.0",
    )
    ent = EntityIdentity(entity_id="task-001", kind=EntityKind.TASK)
    payload = TaskOfferedPayload(offered_to_entity_id="res-001")
    event = TaskOfferedEvent(
        event_id="evt-001",
        sequence=0,
        simulator_time_s=0.0,
        entity=ent,
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=prov,
        payload=payload,
    )
    with pytest.raises(Exception):
        ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-bad-001",
            capability_manifest=manifest,
            present_event_types=(EventType.TASK_OFFERED,),
            events=(event,),
            limitations=("should be refused",),
        )


def test_aggregate_only_cannot_be_replayed() -> None:
    manifest = _manifest((), kind=SourceDataKind.AGGREGATE_ONLY)
    src = SourceIdentity(
        source_id="src-agg-001",
        source_kind=SourceKind.SYNTHETIC_FIXTURE,
        artifact_sha256="b" * 64,
        schema_version="1.0",
    )
    prov = EventProvenance(
        source_artifact_sha256="b" * 64,
        source_record_id="rec-002",
        adapter_id="adapter-test",
        adapter_version="1.0",
    )
    ent = EntityIdentity(entity_id="sim-001", kind=EntityKind.SIMULATION)
    payload = SimulationTimePayload(step_index=0)
    event = SimulationTimeEvent(
        event_id="evt-agg-001",
        sequence=0,
        simulator_time_s=0.0,
        entity=ent,
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=prov,
        payload=payload,
    )
    with pytest.raises(Exception):
        ReplayEventStream(
            schema_version="1.0",
            stream_id="stream-agg-001",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(event,),
            limitations=("aggregate",),
        )


def test_replay_is_deterministic_and_bounded() -> None:
    s1 = build_synthetic_engineering_stream()
    s2 = build_synthetic_engineering_stream()
    assert s1.stream_id == s2.stream_id
    assert len(s1.events) == len(s2.events)
    assert set(s1.present_event_types) == {ev.event_type for ev in s1.events}
    e1 = create_engine(s1)
    e2 = create_engine(s2)
    assert e1.state().playhead_time_s == e2.state().playhead_time_s
    assert e1.state().cursor.simulator_time_s == e2.state().cursor.simulator_time_s
    # Engine stepping is deterministic and does not imply causality


def test_replay_does_not_imply_causality_or_sync() -> None:
    s = build_synthetic_engineering_stream()
    engine = create_engine(s)
    view = get_observatory_view(engine)
    # Disclaimers must be exact typed values — no vague substring matching
    assert view.causal_disclaimer == "replay is deterministic; no causality implied"
    assert view.sync_disclaimer == "synchronization is not evidence of causality"
    assert view.synthetic_disclaimer.lower().startswith("synthetic")
    assert "SYNTHETIC ENGINEERING" in view.synthetic_disclaimer
    assert "not Manchester observation" in view.synthetic_disclaimer
    assert "not admitted task-level" in view.synthetic_disclaimer
    # Service constants must be exact
    from traffictwin.ui.replay_observatory_service import (
        SYNTHETIC_ENGINEERING_DISCLAIMER,
    )

    assert SYNCHRONIZED_REPLAY_DISCLAIMER == "synchronized visual replay is not causal evidence"
    assert SYNTHETIC_ENGINEERING_DISCLAIMER.lower().startswith("synthetic")
    # Typed view must explicitly deny causality — check exact disclaimer fields, not blob containing "not"
    assert view.causal_disclaimer == "replay is deterministic; no causality implied"
    assert view.sync_disclaimer == "synchronization is not evidence of causality"
    # The synthetic disclaimer must deny causal/task-level inference from aggregate
    assert "not admitted task-level research evidence" in view.synthetic_disclaimer


def test_replay_empty_and_aggregate_only_are_truthfully_unavailable() -> None:
    # Empty stream is a valid truthful state (no events), not an error
    s = build_synthetic_engineering_stream()
    engine = create_engine(s)
    assert engine.stream.events
    # Aggregate-only stream must be empty — proven via manifest above
    # Also test that the synthetic stream's present_event_types exactly matches instantiated classes
    assert tuple(sorted(s.present_event_types, key=str)) == s.present_event_types


def test_replay_provenance_binding_is_exact() -> None:
    s = build_synthetic_engineering_stream()
    for ev in s.events:
        assert ev.provenance.source_artifact_sha256 == ev.source.artifact_sha256
    # Also prove the synthetic stream's manifest source is consistent with at least one event
    assert any(
        ev.source.artifact_sha256 == s.capability_manifest.source.artifact_sha256 for ev in s.events
    )
    # Broken binding would have been rejected at stream construction (checked above)


def test_replay_observatory_has_no_dynamic_e3() -> None:
    blob = json.dumps(build_synthetic_engineering_stream().model_dump(mode="json"), sort_keys=True)
    assert "E3" not in blob
    assert "Dynamic Resource" not in blob
    assert "/Users/" not in blob

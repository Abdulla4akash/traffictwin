"""Strong mutation tests for immutable strict replay observatory models."""

from __future__ import annotations

import hashlib
import json
import pathlib

import pytest
from pydantic import ValidationError

from traffictwin.replay_observatory.models import (
    DeadlineOutcomePayload,
    EntityIdentity,
    EntityKind,
    EventProvenance,
    EventType,
    EvidenceStanding,
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
    TaskForwardPayload,
    TaskOfferedEvent,
    TaskOfferedPayload,
    VehicleStateEvent,
    VehicleStatePayload,
    WorkloadQuantity,
)

ARTIFACT = "a" * 64
ARTIFACT2 = "b" * 64


def _source(
    *,
    source_id: str = "src-001",
    kind: SourceKind = SourceKind.SYNTHETIC_FIXTURE,
    artifact: str = ARTIFACT,
) -> SourceIdentity:
    return SourceIdentity(
        source_id=source_id,
        source_kind=kind,
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
    kind: SourceDataKind = SourceDataKind.EVENT_STREAM,
    standing: EvidenceStanding = EvidenceStanding.SYNTHETIC_DATA,
    available: tuple[EventType, ...] | None = None,
) -> SourceCapabilityManifest:
    src = source or _source()
    # canonical lexical order by str()
    if available is None:
        available = tuple(sorted(EventType, key=lambda x: str(x)))
    return SourceCapabilityManifest(
        manifest_id="manifest-001",
        source=src,
        source_data_kind=kind,
        evidence_standing=standing,
        available_event_types=available,
        limitations=("Synthetic only", "Bounded fixture"),
    )


def _sim_event(
    *, seq: int = 0, time: float = 0.0, source: SourceIdentity | None = None
) -> SimulationTimeEvent:
    src = source or _source()
    return SimulationTimeEvent(
        event_id=f"evt-sim-{seq:03d}",
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
) -> VehicleStateEvent:
    src = source or _source()
    return VehicleStateEvent(
        event_id=f"evt-veh-{seq:03d}",
        sequence=seq,
        simulator_time_s=time,
        entity=EntityIdentity(kind=EntityKind.VEHICLE, entity_id="veh-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record=f"rec-veh-{seq:03d}"),
        payload=VehicleStatePayload(x_m=10.0, y_m=20.0, speed_mps=3.0),
    )


def _task_offered_event(
    *, seq: int = 2, time: float = 2.0, source: SourceIdentity | None = None
) -> TaskOfferedEvent:
    src = source or _source()
    return TaskOfferedEvent(
        event_id=f"evt-offer-{seq:03d}",
        sequence=seq,
        simulator_time_s=time,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(artifact=src.artifact_sha256, record=f"rec-offer-{seq:03d}"),
        payload=TaskOfferedPayload(offered_to_entity_id="resource-001"),
    )


# ---------------------------------------------------------------------------
# Evidence standing must be exact v08 vocabulary
# ---------------------------------------------------------------------------


def test_evidence_standing_exact_vocabulary() -> None:
    assert EvidenceStanding.SYNTHETIC_DATA.value == "SYNTHETIC DATA"
    assert EvidenceStanding.REAL_MANCHESTER_DATA.value == "REAL MANCHESTER DATA"
    assert (
        EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA.value
        == "REAL EXTERNAL NON-MANCHESTER DATA"
    )
    assert EvidenceStanding.SIMULATION_OUTPUT.value == "SIMULATION OUTPUT"
    assert EvidenceStanding.DESIGN_ONLY_CAPABILITY.value == "DESIGN-ONLY CAPABILITY"
    # no alias, underscore variant must fail via validation
    with pytest.raises(ValidationError):
        SourceCapabilityManifest(
            manifest_id="m1",
            source=_source(),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing="SYNTHETIC_DATA",  # type: ignore[arg-type]
            available_event_types=(),
            limitations=("a",),
        )


def test_evidence_standing_rejects_unknown() -> None:
    with pytest.raises(ValidationError):
        SimulationTimeEvent(
            event_id="evt-001",
            sequence=0,
            simulator_time_s=0.0,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=_source(),
            evidence_standing="REAL DATA",  # type: ignore[arg-type]
            provenance=_provenance(),
            payload=SimulationTimePayload(step_index=0),
        )


# ---------------------------------------------------------------------------
# Immutable strict base
# ---------------------------------------------------------------------------


def test_immutable_frozen() -> None:
    evt = _sim_event()
    with pytest.raises(ValidationError):
        evt.event_id = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        evt.sequence = 999  # type: ignore[misc]


def test_strict_rejects_coercion() -> None:
    # strict=True should reject int-as-string coercion
    with pytest.raises(ValidationError):
        SimulationTimePayload(step_index="0")  # type: ignore[arg-type]


def test_extra_forbid() -> None:
    with pytest.raises(ValidationError):
        SourceIdentity(
            source_id="src-001",
            source_kind=SourceKind.SYNTHETIC_FIXTURE,
            artifact_sha256=ARTIFACT,
            schema_version="1.0",
            extra_field="oops",  # type: ignore[call-arg]
        )


def test_allow_inf_nan_rejected() -> None:
    with pytest.raises(ValidationError):
        VehicleStatePayload(x_m=float("inf"), y_m=0.0, speed_mps=1.0)
    with pytest.raises(ValidationError):
        VehicleStatePayload(x_m=float("nan"), y_m=0.0, speed_mps=1.0)


# ---------------------------------------------------------------------------
# Identifier validation
# ---------------------------------------------------------------------------


def test_identifier_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        EntityIdentity(kind=EntityKind.VEHICLE, entity_id="bad id with spaces")
    with pytest.raises(ValidationError):
        EntityIdentity(kind=EntityKind.VEHICLE, entity_id="-leading-dash")
    with pytest.raises(ValidationError):
        SourceIdentity(
            source_id="",
            source_kind=SourceKind.SUMO,
            artifact_sha256=ARTIFACT,
            schema_version="1.0",
        )


def test_artifact_sha256_pattern() -> None:
    with pytest.raises(ValidationError):
        SourceIdentity(
            source_id="src-001",
            source_kind=SourceKind.SUMO,
            artifact_sha256="not-hex",
            schema_version="1.0",
        )
    with pytest.raises(ValidationError):
        SourceIdentity(
            source_id="src-001",
            source_kind=SourceKind.SUMO,
            artifact_sha256="A" * 64,
            schema_version="1.0",
        )


# ---------------------------------------------------------------------------
# Capability manifest validations
# ---------------------------------------------------------------------------


def test_manifest_duplicate_types_rejected() -> None:
    with pytest.raises(ValidationError, match="duplicates"):
        SourceCapabilityManifest(
            manifest_id="m1",
            source=_source(),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME, EventType.SIMULATION_TIME),
            limitations=("a",),
        )


def test_manifest_unsorted_rejected() -> None:
    # reverse order should fail
    sorted_types = tuple(sorted(EventType, key=lambda x: str(x)))
    unsorted = tuple(reversed(sorted_types))
    if unsorted != sorted_types:
        with pytest.raises(ValidationError, match="lexical"):
            SourceCapabilityManifest(
                manifest_id="m1",
                source=_source(),
                source_data_kind=SourceDataKind.EVENT_STREAM,
                evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
                available_event_types=unsorted,
                limitations=("a",),
            )


def test_manifest_aggregate_cannot_declare_events() -> None:
    with pytest.raises(ValidationError, match="aggregate-only"):
        SourceCapabilityManifest(
            manifest_id="m1",
            source=_source(kind=SourceKind.RESEARCH_AGGREGATE),
            source_data_kind=SourceDataKind.AGGREGATE_ONLY,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            available_event_types=(EventType.SIMULATION_TIME,),
            limitations=("a",),
        )


def test_manifest_research_aggregate_must_be_aggregate_only() -> None:
    with pytest.raises(ValidationError, match="aggregate-only"):
        SourceCapabilityManifest(
            manifest_id="m1",
            source=_source(kind=SourceKind.RESEARCH_AGGREGATE),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            available_event_types=(),
            limitations=("a",),
        )


def test_manifest_limitations_required() -> None:
    with pytest.raises(ValidationError):
        SourceCapabilityManifest(
            manifest_id="m1",
            source=_source(),
            source_data_kind=SourceDataKind.EVENT_STREAM,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            available_event_types=(),
            limitations=(),
        )


# ---------------------------------------------------------------------------
# Portability: private paths and secrets must fail closed
# ---------------------------------------------------------------------------


def test_private_path_rejected() -> None:
    # absolute path in string field is rejected via bounded identifier before portability
    with pytest.raises(ValidationError, match="bounded portable identifier"):
        VehicleStatePayload(x_m=0.0, y_m=0.0, speed_mps=1.0, edge_id="/tmp/evil")  # noqa: S108
    # also via direct portability rejection on a free-form string field
    with pytest.raises(ValidationError, match="private path"):
        SourceIdentity(
            source_id="src-001",
            source_kind=SourceKind.SUMO,
            artifact_sha256=ARTIFACT,
            schema_version="/Users/evil/path",
        )


def test_secret_key_rejected() -> None:
    # secret-bearing field name injected via measurements? Use ResourceMeasurement with metric_id containing api_key?  # noqa: E501
    # Actually metric_id is identifier, but secret key detection is on dict keys, not values; we need to test via creating a dict with secret key then validating -> use model with extra? Instead test _assert_portable via direct model that contains dict key secret  # noqa: E501
    # Build a ResourceStatePayload with measurements containing a secret-like value should be rejected via secret_value regex  # noqa: E501
    with pytest.raises(ValidationError, match="secret"):
        # value containing bearer token pattern
        ResourceMeasurement(metric_id="cpu_load", value=1.0, unit="ratio")
        # create event with payload containing secret string in provenance? use private path in provenance field that passes identifier but contains secret pattern  # noqa: E501
        # proven via secret value in string field: supply workload unit containing secret? unit is identifier, cannot contain secret-like value; so test secret value in string field that is not identifier-constrained  # noqa: E501
        # Use VehicleState edge_id with secret-like? But edge_id is identifier, won't allow bearer. Instead test via creating a ReplayEventStream with private path in limitation string containing secret pattern  # noqa: E501
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=_manifest(available=()),
            present_event_types=(),
            events=(),
            limitations=("api_key=secret12345 bypass",),
        )


def test_secret_value_rejected() -> None:
    with pytest.raises(ValidationError, match="secret"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=_manifest(available=()),
            present_event_types=(),
            events=(),
            limitations=("bearer abcdefghijklmnopqrstuvwxyz.123456",),
        )


# ---------------------------------------------------------------------------
# Stream contract validations
# ---------------------------------------------------------------------------


def test_stream_present_must_match_actual() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME, EventType.VEHICLE_STATE))
    evt = _sim_event(source=src)
    # present says vehicle_state but actual is simulation_time -> mismatch
    with pytest.raises(ValidationError, match="present_event_types"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.VEHICLE_STATE,),
            events=(evt,),
            limitations=("a",),
        )


def test_stream_invented_event_not_declared() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt = _vehicle_event(source=src)
    with pytest.raises(ValidationError, match="not declared"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.VEHICLE_STATE,),
            events=(evt,),
            limitations=("a",),
        )


def test_stream_mismatched_source_identity() -> None:
    src = _source(artifact=ARTIFACT)
    other = _source(artifact=ARTIFACT2, source_id="other-src")
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt = _sim_event(source=other)
    with pytest.raises(ValidationError, match="source identity"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt,),
            limitations=("a",),
        )


def test_stream_mismatched_evidence_standing() -> None:
    src = _source()
    manifest = _manifest(
        source=src, standing=EvidenceStanding.SYNTHETIC_DATA, available=(EventType.SIMULATION_TIME,)
    )
    evt = SimulationTimeEvent(
        event_id="evt-001",
        sequence=0,
        simulator_time_s=0.0,
        entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
        source=src,
        evidence_standing=EvidenceStanding.SIMULATION_OUTPUT,
        provenance=_provenance(),
        payload=SimulationTimePayload(step_index=0),
    )
    with pytest.raises(ValidationError, match="evidence standing"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt,),
            limitations=("a",),
        )


def test_stream_entity_kind_enforced() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.VEHICLE_STATE,))
    # vehicle_state requires VEHICLE, but give TASK
    with pytest.raises(ValidationError, match="requires entity kind"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.VEHICLE_STATE,),
            events=(
                VehicleStateEvent(
                    event_id="evt-001",
                    sequence=0,
                    simulator_time_s=0.0,
                    entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
                    source=src,
                    evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
                    provenance=_provenance(),
                    payload=VehicleStatePayload(x_m=0.0, y_m=0.0, speed_mps=1.0),
                ),
            ),
            limitations=("a",),
        )


def test_stream_duplicate_event_ids_rejected() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt1 = _sim_event(seq=0, time=0.0, source=src)
    _sim_event(seq=1, time=1.0, source=src)
    # force same event_id
    evt2_dup = SimulationTimeEvent(
        event_id=evt1.event_id,
        sequence=1,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(record="rec-dup"),
        payload=SimulationTimePayload(step_index=1),
    )
    with pytest.raises(ValidationError, match="unique"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt1, evt2_dup),
            limitations=("a",),
        )


def test_stream_duplicate_sequences_rejected() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt1 = _sim_event(seq=0, time=0.0, source=src)
    evt2 = SimulationTimeEvent(
        event_id="evt-002",
        sequence=0,
        simulator_time_s=1.0,
        entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(record="rec-002"),
        payload=SimulationTimePayload(step_index=1),
    )
    with pytest.raises(ValidationError, match="unique"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt1, evt2),
            limitations=("a",),
        )


def test_stream_canonical_order_enforced() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt1 = _sim_event(seq=1, time=1.0, source=src)
    evt2 = _sim_event(seq=0, time=0.0, source=src)
    with pytest.raises(ValidationError, match="canonical order"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt1, evt2),
            limitations=("a",),
        )


def test_stream_aggregate_cannot_have_events() -> None:
    src = _source(kind=SourceKind.RESEARCH_AGGREGATE)
    manifest = _manifest(
        source=src,
        kind=SourceDataKind.AGGREGATE_ONLY,
        available=(),
        standing=EvidenceStanding.SYNTHETIC_DATA,
    )
    evt = _sim_event(source=src)
    with pytest.raises(ValidationError, match="aggregate-only"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.SIMULATION_TIME,),
            events=(evt,),
            limitations=("a",),
        )


def test_stream_provenance_mismatch_rejected() -> None:
    src = _source(artifact=ARTIFACT)
    with pytest.raises(ValidationError, match="fingerprint"):
        SimulationTimeEvent(
            event_id="evt-001",
            sequence=0,
            simulator_time_s=0.0,
            entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
            source=src,
            evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
            provenance=EventProvenance(
                source_artifact_sha256=ARTIFACT2,
                source_record_id="rec-001",
                adapter_id="adapter-v1",
                adapter_version="1.0",
            ),
            payload=SimulationTimePayload(step_index=0),
        )


def test_stream_fingerprint_deterministic_and_distinct() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt = _sim_event(source=src)
    s1 = ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=(EventType.SIMULATION_TIME,),
        events=(evt,),
        limitations=("a",),
    )
    s2 = ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=(EventType.SIMULATION_TIME,),
        events=(evt,),
        limitations=("a",),
    )
    assert s1.fingerprint() == s2.fingerprint()
    # mutate one field -> different fingerprint
    evt2 = SimulationTimeEvent(
        event_id="evt-002",
        sequence=0,
        simulator_time_s=0.0,
        entity=EntityIdentity(kind=EntityKind.SIMULATION, entity_id="sim-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(record="rec-002"),
        payload=SimulationTimePayload(step_index=1),
    )
    s3 = ReplayEventStream(
        stream_id="stream-001",
        capability_manifest=manifest,
        present_event_types=(EventType.SIMULATION_TIME,),
        events=(evt2,),
        limitations=("a",),
    )
    assert s1.fingerprint() != s3.fingerprint()
    # canonical_json must be stable
    assert s1.canonical_json() == s2.canonical_json()
    assert len(s1.fingerprint()) == 64


def test_stream_immutable_fingerprint_not_mutated() -> None:
    src = _source()
    manifest = _manifest(source=src, available=(EventType.SIMULATION_TIME,))
    evt = _sim_event(source=src)
    stream = ReplayEventStream(
        stream_id="s1",
        capability_manifest=manifest,
        present_event_types=(EventType.SIMULATION_TIME,),
        events=(evt,),
        limitations=("a",),
    )
    with pytest.raises(ValidationError):
        stream.stream_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Payload validations
# ---------------------------------------------------------------------------


def test_deadline_outcome_met_requires_completion_before_deadline() -> None:
    with pytest.raises(ValidationError):
        DeadlineOutcomePayload(deadline_s=10.0, completed_at_s=11.0, outcome="met")
    with pytest.raises(ValidationError):
        DeadlineOutcomePayload(deadline_s=10.0, completed_at_s=None, outcome="met")


def test_deadline_outcome_unavailable_no_completion() -> None:
    with pytest.raises(ValidationError):
        DeadlineOutcomePayload(deadline_s=10.0, completed_at_s=5.0, outcome="unavailable")


def test_deadline_outcome_missed_requires_after_deadline() -> None:
    with pytest.raises(ValidationError):
        DeadlineOutcomePayload(deadline_s=10.0, completed_at_s=5.0, outcome="missed")


def test_resource_measurements_unique_and_sorted() -> None:
    with pytest.raises(ValidationError, match="unique"):
        ResourceStatePayload(
            measurements=(
                ResourceMeasurement(metric_id="cpu", value=1.0, unit="ratio"),
                ResourceMeasurement(metric_id="cpu", value=2.0, unit="ratio"),
            )
        )
    with pytest.raises(ValidationError, match="canonical"):
        ResourceStatePayload(
            measurements=(
                ResourceMeasurement(metric_id="queue", value=1.0, unit="tasks"),
                ResourceMeasurement(metric_id="cpu", value=1.0, unit="ratio"),
            )
        )


def test_scale_action_delta_unit_coherence() -> None:
    with pytest.raises(ValidationError):
        ScaleActionPayload(
            action_id="a1",
            target_resource_id="r1",
            source_declared_action="scale_up",
            delta=1.0,
            unit=None,
        )
    with pytest.raises(ValidationError):
        ScaleActionPayload(
            action_id="a1",
            target_resource_id="r1",
            source_declared_action="scale_up",
            delta=None,
            unit="replica",
        )


def test_task_forward_distinct_resources() -> None:
    with pytest.raises(ValidationError):
        TaskForwardPayload(from_resource_id="r1", to_resource_id="r1")


def test_workload_quantity_positive() -> None:
    with pytest.raises(ValidationError):
        WorkloadQuantity(value=0.0, unit="ms")
    with pytest.raises(ValidationError):
        WorkloadQuantity(value=-1.0, unit="ms")


def test_synthetic_fixture_is_synthetic_data() -> None:
    path = pathlib.Path("tests/fixtures/replay_observatory/synthetic_event_stream_v1.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["capability_manifest"]["evidence_standing"] == "SYNTHETIC DATA"
    for evt in data["events"]:
        assert evt["evidence_standing"] == "SYNTHETIC DATA"
    # fingerprint via model matches file content canonical
    from traffictwin.replay_observatory.adapters import load_event_stream_json

    stream = load_event_stream_json(path.read_text())
    assert stream.capability_manifest.evidence_standing is EvidenceStanding.SYNTHETIC_DATA
    # verify fingerprint is sha256 of canonical json
    canonical = stream.canonical_json()
    assert stream.fingerprint() == hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_e2_aggregate_never_becomes_task_event() -> None:
    # Research aggregate manifest cannot have events; ensure model refuses task-level event with research aggregate source  # noqa: E501
    src = _source(kind=SourceKind.RESEARCH_AGGREGATE, artifact=ARTIFACT)
    manifest = _manifest(
        source=src,
        kind=SourceDataKind.AGGREGATE_ONLY,
        available=(),
        standing=EvidenceStanding.SYNTHETIC_DATA,
    )
    # Attempt to create stream with task event should fail
    evt = TaskOfferedEvent(
        event_id="evt-001",
        sequence=0,
        simulator_time_s=0.0,
        entity=EntityIdentity(kind=EntityKind.TASK, entity_id="task-001"),
        source=src,
        evidence_standing=EvidenceStanding.SYNTHETIC_DATA,
        provenance=_provenance(),
        payload=TaskOfferedPayload(offered_to_entity_id="r1"),
    )
    with pytest.raises(ValidationError):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=manifest,
            present_event_types=(EventType.TASK_OFFERED,),
            events=(evt,),
            limitations=("a",),
        )


def test_present_event_types_canonical_order_required() -> None:
    src = _source()
    # intentionally unsorted present types
    with pytest.raises(ValidationError, match="lexical"):
        ReplayEventStream(
            stream_id="s1",
            capability_manifest=_manifest(
                source=src, available=(EventType.SIMULATION_TIME, EventType.VEHICLE_STATE)
            ),
            present_event_types=(EventType.VEHICLE_STATE, EventType.SIMULATION_TIME),
            events=(_sim_event(source=src), _vehicle_event(source=src)),
            limitations=("a",),
        )


def test_all_11_event_types_instantiable_when_declared() -> None:
    src = _source()
    manifest = _manifest(source=src)
    # Use synthetic fixture as proof that all 11 can be instantiated together
    path = pathlib.Path("tests/fixtures/replay_observatory/synthetic_event_stream_v1.json")
    from traffictwin.replay_observatory.adapters import load_event_stream_json

    stream = load_event_stream_json(path.read_text())
    assert set(stream.present_event_types) == set(manifest.available_event_types)
    assert len(stream.events) == 11


def test_scale_action_generic_no_e3_semantics() -> None:
    # Ensure scale_action payload carries no cost or policy inference
    payload = ScaleActionPayload(
        action_id="scale-001", target_resource_id="r1", source_declared_action="scale_up"
    )
    assert payload.delta is None
    assert payload.unit is None
    # with delta/unit both present is allowed but still generic
    payload2 = ScaleActionPayload(
        action_id="scale-002",
        target_resource_id="r1",
        source_declared_action="scale_down",
        delta=2.0,
        unit="replica",
    )
    assert payload2.delta == 2.0
    # ensure no extra fields like cost or policy are present
    assert not hasattr(payload, "cost")
    assert not hasattr(payload, "policy")

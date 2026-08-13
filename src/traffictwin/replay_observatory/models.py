"""Strict, evidence-bound event models for the Replay Observatory.

This module is deliberately a data contract, not a simulator or resource-strategy
implementation.  A replay stream can contain only event classes declared by its
source capability manifest, and aggregate-only sources cannot contain events.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION: Literal["1.0"] = "1.0"
MAX_EVENTS_PER_STREAM = 10_000
MAX_MEASUREMENTS_PER_EVENT = 64

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_PRIVATE_PATH_RE = re.compile(
    r"(?:^|[\s\"'=])(?:file://|/(?:Users|home|tmp|var/folders)/|[A-Za-z]:\\\\)",
    re.IGNORECASE,
)
_SECRET_KEY_RE = re.compile(
    r"(?:^|_)(?:api_?key|password|secret|access_?token|auth_?token|private_?key|credential)(?:$|_)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"(?:api[_-]?key|password|secret|access[_-]?token|auth[_-]?token)\s*[:=]\s*\S+|"
    r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _validate_identifier(value: str, *, label: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"{label} must be a bounded portable identifier")
    return value


def _assert_portable(value: object, *, location: str = "$") -> None:
    """Reject workstation paths and secret-bearing material without redaction."""

    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if _SECRET_KEY_RE.search(key_text):
                raise ValueError(f"{location}.{key_text} is a forbidden secret-bearing field")
            _assert_portable(child, location=f"{location}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _assert_portable(child, location=f"{location}[{index}]")
    elif isinstance(value, str):
        if value.startswith("/") or _PRIVATE_PATH_RE.search(value):
            raise ValueError(f"{location} contains an absolute/private path")
        if _SECRET_VALUE_RE.search(value):
            raise ValueError(f"{location} contains secret-like material")


class ReplayModel(BaseModel):
    """Immutable strict base for all replay contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_portability(self) -> ReplayModel:
        _assert_portable(self.model_dump(mode="json"))
        return self


class EvidenceStanding(StrEnum):
    """Exact v0.8 Manchester evidence vocabulary; no strengthened aliases."""

    REAL_MANCHESTER_DATA = "REAL MANCHESTER DATA"
    REAL_EXTERNAL_NON_MANCHESTER_DATA = "REAL EXTERNAL NON-MANCHESTER DATA"
    SYNTHETIC_DATA = "SYNTHETIC DATA"
    SIMULATION_OUTPUT = "SIMULATION OUTPUT"
    DESIGN_ONLY_CAPABILITY = "DESIGN-ONLY CAPABILITY"


class EventType(StrEnum):
    SIMULATION_TIME = "simulation_time"
    VEHICLE_STATE = "vehicle_state"
    TASK_OFFERED = "task_offered"
    TASK_INGRESS = "task_ingress"
    TASK_ADMISSION = "task_admission"
    TASK_FORWARD = "task_forward"
    EXECUTION_TARGET = "execution_target"
    TASK_REJECTED = "task_rejected"
    DEADLINE_OUTCOME = "deadline_outcome"
    RESOURCE_STATE = "resource_state"
    SCALE_ACTION = "scale_action"


class EntityKind(StrEnum):
    SIMULATION = "simulation"
    VEHICLE = "vehicle"
    TASK = "task"
    RESOURCE = "resource"


class SourceDataKind(StrEnum):
    EVENT_STREAM = "event_stream"
    AGGREGATE_ONLY = "aggregate_only"


class SourceKind(StrEnum):
    SUMO = "sumo"
    INFRASTRUCTURE = "infrastructure"
    SCIENTIFIC_TELEMETRY = "scientific_telemetry"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    RESEARCH_AGGREGATE = "research_aggregate"


class EntityIdentity(ReplayModel):
    kind: EntityKind
    entity_id: str

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, value: str) -> str:
        return _validate_identifier(value, label="entity_id")


class SourceIdentity(ReplayModel):
    source_id: str
    source_kind: SourceKind
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1, max_length=32)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value: str) -> str:
        return _validate_identifier(value, label="source_id")


class EventProvenance(ReplayModel):
    source_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_record_id: str
    adapter_id: str
    adapter_version: str = Field(min_length=1, max_length=32)

    @field_validator("source_record_id", "adapter_id")
    @classmethod
    def validate_ids(cls, value: str, info: object) -> str:
        field_name = getattr(info, "field_name", "identifier")
        return _validate_identifier(value, label=str(field_name))


class SourceCapabilityManifest(ReplayModel):
    """Source-declared ceiling for the event types an adapter may instantiate."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    manifest_id: str
    source: SourceIdentity
    source_data_kind: SourceDataKind
    evidence_standing: EvidenceStanding
    available_event_types: tuple[EventType, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1, max_length=32)

    @field_validator("manifest_id")
    @classmethod
    def validate_manifest_id(cls, value: str) -> str:
        return _validate_identifier(value, label="manifest_id")

    @model_validator(mode="after")
    def validate_capabilities(self) -> SourceCapabilityManifest:
        if len(set(self.available_event_types)) != len(self.available_event_types):
            raise ValueError("available_event_types must not contain duplicates")
        if tuple(sorted(self.available_event_types, key=str)) != self.available_event_types:
            raise ValueError("available_event_types must use canonical lexical order")
        if self.source_data_kind is SourceDataKind.AGGREGATE_ONLY and self.available_event_types:
            raise ValueError("aggregate-only sources cannot declare event capabilities")
        if (
            self.source.source_kind is SourceKind.RESEARCH_AGGREGATE
            and self.source_data_kind is not SourceDataKind.AGGREGATE_ONLY
        ):
            raise ValueError("research aggregate identities must remain aggregate-only")
        return self


class SimulationTimePayload(ReplayModel):
    step_index: int = Field(ge=0)


class VehicleStatePayload(ReplayModel):
    x_m: float
    y_m: float
    speed_mps: float = Field(ge=0)
    heading_degrees: float | None = Field(default=None, ge=0, lt=360)
    edge_id: str | None = None
    lane_id: str | None = None

    @field_validator("edge_id", "lane_id")
    @classmethod
    def validate_network_ids(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, label=str(getattr(info, "field_name", "network_id")))


class WorkloadQuantity(ReplayModel):
    value: float = Field(gt=0)
    unit: str

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, value: str) -> str:
        return _validate_identifier(value, label="unit")


class TaskOfferedPayload(ReplayModel):
    offered_to_entity_id: str
    workload: WorkloadQuantity | None = None

    @field_validator("offered_to_entity_id")
    @classmethod
    def validate_target(cls, value: str) -> str:
        return _validate_identifier(value, label="offered_to_entity_id")


class TaskIngressPayload(ReplayModel):
    ingress_resource_id: str

    @field_validator("ingress_resource_id")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        return _validate_identifier(value, label="ingress_resource_id")


class TaskAdmissionPayload(ReplayModel):
    decision: Literal["admitted"] = "admitted"
    admission_resource_id: str

    @field_validator("admission_resource_id")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        return _validate_identifier(value, label="admission_resource_id")


class TaskForwardPayload(ReplayModel):
    from_resource_id: str
    to_resource_id: str

    @field_validator("from_resource_id", "to_resource_id")
    @classmethod
    def validate_resource(cls, value: str, info: object) -> str:
        return _validate_identifier(value, label=str(getattr(info, "field_name", "resource_id")))

    @model_validator(mode="after")
    def validate_distinct_resources(self) -> TaskForwardPayload:
        if self.from_resource_id == self.to_resource_id:
            raise ValueError("task forwarding requires distinct source and target resources")
        return self


class ExecutionTargetPayload(ReplayModel):
    execution_resource_id: str

    @field_validator("execution_resource_id")
    @classmethod
    def validate_resource(cls, value: str) -> str:
        return _validate_identifier(value, label="execution_resource_id")


class TaskRejectedPayload(ReplayModel):
    reason_code: str

    @field_validator("reason_code")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        return _validate_identifier(value, label="reason_code")


class DeadlineOutcomePayload(ReplayModel):
    deadline_s: float = Field(ge=0)
    completed_at_s: float | None = Field(default=None, ge=0)
    outcome: Literal["met", "missed", "unavailable"]

    @model_validator(mode="after")
    def validate_outcome(self) -> DeadlineOutcomePayload:
        if self.outcome == "unavailable" and self.completed_at_s is not None:
            raise ValueError("unavailable deadline outcome cannot carry a completion time")
        if self.outcome == "met" and (
            self.completed_at_s is None or self.completed_at_s > self.deadline_s
        ):
            raise ValueError("met deadline requires completion at or before the deadline")
        if self.outcome == "missed" and (
            self.completed_at_s is not None and self.completed_at_s <= self.deadline_s
        ):
            raise ValueError("missed deadline completion must be after the deadline")
        return self


class ResourceMeasurement(ReplayModel):
    metric_id: str
    value: float
    unit: str

    @field_validator("metric_id", "unit")
    @classmethod
    def validate_labels(cls, value: str, info: object) -> str:
        return _validate_identifier(value, label=str(getattr(info, "field_name", "identifier")))


class ResourceStatePayload(ReplayModel):
    measurements: tuple[ResourceMeasurement, ...] = Field(
        min_length=1, max_length=MAX_MEASUREMENTS_PER_EVENT
    )

    @model_validator(mode="after")
    def validate_measurements(self) -> ResourceStatePayload:
        metric_ids = [measurement.metric_id for measurement in self.measurements]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("resource measurements must have unique metric IDs")
        if metric_ids != sorted(metric_ids):
            raise ValueError("resource measurements must use canonical metric-ID order")
        return self


class ScaleActionPayload(ReplayModel):
    """Source-declared scale event only; no policy, E3, or cost semantics are inferred."""

    action_id: str
    target_resource_id: str
    source_declared_action: str
    delta: float | None = None
    unit: str | None = None

    @field_validator("action_id", "target_resource_id", "source_declared_action", "unit")
    @classmethod
    def validate_labels(cls, value: str | None, info: object) -> str | None:
        if value is None:
            return None
        return _validate_identifier(value, label=str(getattr(info, "field_name", "identifier")))

    @model_validator(mode="after")
    def validate_delta_unit(self) -> ScaleActionPayload:
        if (self.delta is None) != (self.unit is None):
            raise ValueError("scale delta and unit must either both be present or both be absent")
        return self


class ReplayEventBase(ReplayModel):
    event_id: str
    sequence: int = Field(ge=0)
    simulator_time_s: float = Field(ge=0)
    entity: EntityIdentity
    source: SourceIdentity
    evidence_standing: EvidenceStanding
    provenance: EventProvenance

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        return _validate_identifier(value, label="event_id")

    @model_validator(mode="after")
    def validate_provenance_binding(self) -> ReplayEventBase:
        if self.provenance.source_artifact_sha256 != self.source.artifact_sha256:
            raise ValueError("event provenance fingerprint must match source artifact identity")
        if not math.isfinite(self.simulator_time_s):
            raise ValueError("simulator_time_s must be finite")
        return self


class SimulationTimeEvent(ReplayEventBase):
    event_type: Literal[EventType.SIMULATION_TIME] = EventType.SIMULATION_TIME
    payload: SimulationTimePayload


class VehicleStateEvent(ReplayEventBase):
    event_type: Literal[EventType.VEHICLE_STATE] = EventType.VEHICLE_STATE
    payload: VehicleStatePayload


class TaskOfferedEvent(ReplayEventBase):
    event_type: Literal[EventType.TASK_OFFERED] = EventType.TASK_OFFERED
    payload: TaskOfferedPayload


class TaskIngressEvent(ReplayEventBase):
    event_type: Literal[EventType.TASK_INGRESS] = EventType.TASK_INGRESS
    payload: TaskIngressPayload


class TaskAdmissionEvent(ReplayEventBase):
    event_type: Literal[EventType.TASK_ADMISSION] = EventType.TASK_ADMISSION
    payload: TaskAdmissionPayload


class TaskForwardEvent(ReplayEventBase):
    event_type: Literal[EventType.TASK_FORWARD] = EventType.TASK_FORWARD
    payload: TaskForwardPayload


class ExecutionTargetEvent(ReplayEventBase):
    event_type: Literal[EventType.EXECUTION_TARGET] = EventType.EXECUTION_TARGET
    payload: ExecutionTargetPayload


class TaskRejectedEvent(ReplayEventBase):
    event_type: Literal[EventType.TASK_REJECTED] = EventType.TASK_REJECTED
    payload: TaskRejectedPayload


class DeadlineOutcomeEvent(ReplayEventBase):
    event_type: Literal[EventType.DEADLINE_OUTCOME] = EventType.DEADLINE_OUTCOME
    payload: DeadlineOutcomePayload


class ResourceStateEvent(ReplayEventBase):
    event_type: Literal[EventType.RESOURCE_STATE] = EventType.RESOURCE_STATE
    payload: ResourceStatePayload


class ScaleActionEvent(ReplayEventBase):
    event_type: Literal[EventType.SCALE_ACTION] = EventType.SCALE_ACTION
    payload: ScaleActionPayload


ReplayEvent: TypeAlias = Annotated[
    SimulationTimeEvent
    | VehicleStateEvent
    | TaskOfferedEvent
    | TaskIngressEvent
    | TaskAdmissionEvent
    | TaskForwardEvent
    | ExecutionTargetEvent
    | TaskRejectedEvent
    | DeadlineOutcomeEvent
    | ResourceStateEvent
    | ScaleActionEvent,
    Field(discriminator="event_type"),
]

_EXPECTED_ENTITY_KIND: dict[EventType, EntityKind] = {
    EventType.SIMULATION_TIME: EntityKind.SIMULATION,
    EventType.VEHICLE_STATE: EntityKind.VEHICLE,
    EventType.TASK_OFFERED: EntityKind.TASK,
    EventType.TASK_INGRESS: EntityKind.TASK,
    EventType.TASK_ADMISSION: EntityKind.TASK,
    EventType.TASK_FORWARD: EntityKind.TASK,
    EventType.EXECUTION_TARGET: EntityKind.TASK,
    EventType.TASK_REJECTED: EntityKind.TASK,
    EventType.DEADLINE_OUTCOME: EntityKind.TASK,
    EventType.RESOURCE_STATE: EntityKind.RESOURCE,
    EventType.SCALE_ACTION: EntityKind.RESOURCE,
}


class ReplayEventStream(ReplayModel):
    """Immutable, canonically ordered event stream with an evidence ceiling."""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    stream_id: str
    capability_manifest: SourceCapabilityManifest
    present_event_types: tuple[EventType, ...] = ()
    events: tuple[ReplayEvent, ...] = Field(max_length=MAX_EVENTS_PER_STREAM)
    limitations: tuple[str, ...] = Field(min_length=1, max_length=32)

    @field_validator("stream_id")
    @classmethod
    def validate_stream_id(cls, value: str) -> str:
        return _validate_identifier(value, label="stream_id")

    @model_validator(mode="after")
    def validate_stream_contract(self) -> ReplayEventStream:
        if tuple(sorted(self.present_event_types, key=str)) != self.present_event_types:
            raise ValueError("present_event_types must use canonical lexical order")
        if len(set(self.present_event_types)) != len(self.present_event_types):
            raise ValueError("present_event_types must not contain duplicates")

        actual_types = frozenset(event.event_type for event in self.events)
        if actual_types != frozenset(self.present_event_types):
            raise ValueError("present_event_types must exactly match instantiated event classes")
        if (
            self.capability_manifest.source_data_kind is SourceDataKind.AGGREGATE_ONLY
            and self.events
        ):
            raise ValueError("aggregate-only sources cannot be adapted into replay events")
        if not actual_types <= frozenset(self.capability_manifest.available_event_types):
            raise ValueError("event type is not declared by the source capability manifest")

        event_ids: set[str] = set()
        sequences: set[int] = set()
        prior_key: tuple[float, int, str] | None = None
        for event in self.events:
            if event.source != self.capability_manifest.source:
                raise ValueError("event source identity must exactly match the capability manifest")
            if event.evidence_standing is not self.capability_manifest.evidence_standing:
                raise ValueError(
                    "event evidence standing must match the source capability manifest"
                )
            expected_kind = _EXPECTED_ENTITY_KIND[event.event_type]
            if event.entity.kind is not expected_kind:
                raise ValueError(
                    f"{event.event_type.value} requires entity kind {expected_kind.value}"
                )
            if event.event_id in event_ids:
                raise ValueError("event IDs must be unique")
            if event.sequence in sequences:
                raise ValueError("event sequences must be unique")
            event_ids.add(event.event_id)
            sequences.add(event.sequence)
            key = (event.simulator_time_s, event.sequence, event.event_id)
            if prior_key is not None and key <= prior_key:
                raise ValueError(
                    "events must use strict canonical order (simulator_time_s, sequence, event_id)"
                )
            prior_key = key
        return self

    def canonical_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_dict())

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

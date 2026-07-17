"""Canonical in-memory record models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.enums import Decision, TaskClass


class CanonicalRecord(BaseModel):
    """Base record carrying source provenance."""

    model_config = ConfigDict(extra="forbid")

    source_file: str
    source_row: int = Field(ge=1)


class TaskRecord(CanonicalRecord):
    """Canonical task record."""

    task_id: str
    vehicle_id: str
    task_class: TaskClass
    arrival_time_s: float
    deadline_ms: float
    decision: Decision
    completed: bool
    completion_time_s: float | None = None
    latency_ms: float | None = None
    target_id: str | None = None
    workload_cycles: float | None = None
    data_size_bytes: float | None = None
    energy_j: float | None = None
    drop_reason: str | None = None


class InfrastructureRecord(CanonicalRecord):
    """Canonical infrastructure state record."""

    timestamp_s: float
    rsu_id: str
    queue_length: float | None = None
    utilisation_fraction: float | None = None
    arrivals: int | None = None
    active_tasks: int | None = None
    drops: int | None = None
    capacity: float | None = None


class VehicleStateRecord(CanonicalRecord):
    """Canonical vehicle state record."""

    timestamp_s: float
    vehicle_id: str
    x: float | None = None
    y: float | None = None
    speed_mps: float | None = None
    lane: str | None = None
    tier: str | None = None


class TrafficObservationRecord(CanonicalRecord):
    """Canonical traffic observation record."""

    timestamp_s: float
    sensor_id: str
    count: int | None = None
    average_speed_mps: float | None = None
    location: str | None = None


class TripRecord(CanonicalRecord):
    """Canonical trip record."""

    trip_id: str
    vehicle_id: str | None = None
    departure_time_s: float
    arrival_time_s: float | None = None
    duration_s: float | None = None
    route_id: str | None = None


class IncidentRecord(CanonicalRecord):
    """Canonical incident record."""

    incident_id: str
    timestamp_s: float
    incident_type: str
    location: str | None = None
    severity: str | None = None

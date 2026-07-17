"""In-memory canonical table container."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.canonical.records import (
    IncidentRecord,
    InfrastructureRecord,
    TaskRecord,
    TrafficObservationRecord,
    TripRecord,
    VehicleStateRecord,
)


class CanonicalTables(BaseModel):
    """Canonical in-memory records produced from a bundle."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[TaskRecord] = Field(default_factory=list)
    infrastructure: list[InfrastructureRecord] = Field(default_factory=list)
    vehicles: list[VehicleStateRecord] = Field(default_factory=list)
    traffic: list[TrafficObservationRecord] = Field(default_factory=list)
    trips: list[TripRecord] = Field(default_factory=list)
    incidents: list[IncidentRecord] = Field(default_factory=list)

    def record_counts(self) -> dict[str, int]:
        """Return canonical record counts by table."""

        return {
            "tasks": len(self.tasks),
            "infrastructure": len(self.infrastructure),
            "vehicles": len(self.vehicles),
            "traffic": len(self.traffic),
            "trips": len(self.trips),
            "incidents": len(self.incidents),
        }

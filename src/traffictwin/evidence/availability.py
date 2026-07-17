"""Evidence availability state used by future metrics and rules."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class EvidenceStatus(StrEnum):
    """Availability state for an evidence category."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class EvidenceAvailability(BaseModel):
    """Structured evidence availability summary."""

    model_config = ConfigDict(extra="forbid")

    tasks: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    infrastructure: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    vehicles: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    traffic: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    trips: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    incidents: EvidenceStatus = EvidenceStatus.UNAVAILABLE
    diagnosis: EvidenceStatus = EvidenceStatus.UNAVAILABLE

    def available_categories(self) -> list[str]:
        """Return categories that are fully available."""

        return [
            name
            for name, value in self.model_dump().items()
            if value == EvidenceStatus.AVAILABLE.value
        ]

    def unavailable_categories(self) -> list[str]:
        """Return categories that are unavailable or invalid."""

        return [
            name
            for name, value in self.model_dump().items()
            if value in {EvidenceStatus.UNAVAILABLE.value, EvidenceStatus.INVALID.value}
        ]

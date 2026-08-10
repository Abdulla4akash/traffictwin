"""STA-04 typed adapter for the Baseline Registry.

Integrates promoted baselines with the existing regression-gate machinery
without rewriting STA-04 logic. A promoted baseline exports a
regression-gate reference that can be compared against live subjects via
exact fingerprint verification.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from traffictwin.baseline_registry.models import BaselineRecord, _fingerprint


class BaselineSta04Reference(BaseModel):
    """Portable regression-gate reference exported from a promoted baseline."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=3, max_length=32)
    baseline_id: str = Field(min_length=2, max_length=128)
    scope_id: str = Field(min_length=2, max_length=128)
    artifact_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    artifact_type: str = Field(min_length=3, max_length=64)
    baseline_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    regression_gate_policy: str = Field(min_length=12, max_length=1000)
    metric_contracts: list[str] = Field(default_factory=list)
    cohort_definition: str = Field(min_length=8, max_length=2000)
    evidence_standing: str = Field(min_length=3, max_length=64)
    source_standing: str = Field(min_length=3, max_length=64)
    exported_at: datetime
    limitations: str = Field(min_length=12, max_length=2000)

    @field_validator("exported_at")
    @classmethod
    def validate_exported_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("exported_at must be timezone-aware")
        return v

    def fingerprint(self) -> str:
        payload = self.model_dump(mode="json", exclude={"exported_at"})
        # Exclude wall-clock exported_at from identity
        return _fingerprint(payload)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def canonical_json(self) -> str:
        payload = self.model_dump(mode="json")
        payload["exported_at"] = "<normalised>"
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def baseline_to_sta04_reference(
    record: BaselineRecord,
    *,
    clock: datetime | None = None,
) -> BaselineSta04Reference:
    """Export a promoted baseline as a typed STA-04 reference artifact."""
    now = clock if clock is not None else datetime.now(UTC)
    return BaselineSta04Reference(
        schema_version=record.schema_version,
        baseline_id=record.baseline_id,
        scope_id=record.scope.scope_id,
        artifact_fingerprint=record.artifact_fingerprint,
        artifact_type=record.artifact_type.value,
        baseline_fingerprint=record.record_fingerprint,
        regression_gate_policy=record.regression_gate_policy,
        metric_contracts=list(record.metric_contracts),
        cohort_definition=record.cohort_definition,
        evidence_standing=record.evidence_standing.value,
        source_standing=record.source_standing.value,
        exported_at=now,
        limitations=record.limitations,
    )


def verify_baseline_reference_against_subject(
    reference: BaselineSta04Reference,
    subject_fingerprint: str,
) -> bool:
    """Check exact artifact fingerprint match without recomputing subject."""
    normalized = subject_fingerprint.strip().lower()
    return normalized == reference.artifact_fingerprint.lower()


def baseline_reference_is_compatible_with_subject_fingerprint(
    record: BaselineRecord,
    subject_fingerprint: str,
) -> bool:
    """Convenience: check a live record directly against a subject fingerprint."""
    return record.artifact_fingerprint.lower() == subject_fingerprint.strip().lower()


__all__ = [
    "BaselineSta04Reference",
    "baseline_to_sta04_reference",
    "verify_baseline_reference_against_subject",
    "baseline_reference_is_compatible_with_subject_fingerprint",
]

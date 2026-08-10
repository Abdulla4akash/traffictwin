"""Typed models for Study Accrual & Deviation Monitor."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base that rejects unknown fields and validates on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AccrualCellStatus(StrEnum):
    """Mutually exclusive final state for one planned cell."""

    PLANNED_MISSING = "planned_missing"
    ATTACHED_UNADMITTED = "attached_unadmitted"
    ATTACHED_ADMITTED = "attached_admitted"
    INCOMPATIBLE = "incompatible"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXTRA = "extra"
    COMPLETE = "complete"


class AccrualDeviationCode(StrEnum):
    """Typed deviation identifiers — only inferred when explicit record exists."""

    EXTRA_CELL = "extra_cell"
    MISSING_CELL = "missing_cell"
    POST_EVIDENCE_AMENDMENT = "post_evidence_amendment"
    METRIC_CONTRACT_MISMATCH = "metric_contract_mismatch"
    UNIT_MISMATCH = "unit_mismatch"
    DUPLICATE_ATTACHMENT = "duplicate_attachment"
    REJECTED_EVIDENCE = "rejected_evidence"
    WITHDRAWN_EVIDENCE = "withdrawn_evidence"
    STOPPING_RULE_OVERRUN = "stopping_rule_overrun"
    UNPLANNED_INTERIM_LOOK = "unplanned_interim_look"


class AccrualDeviation(StrictModel):
    code: AccrualDeviationCode
    cell_id: str | None = None
    message: str = Field(min_length=8)
    details: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 8:
            raise ValueError("deviation message must contain at least 8 characters")
        return s

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("cell_id must contain non-space characters when provided")
        return s


class AccrualWarning(StrictModel):
    code: str = Field(min_length=4)
    message: str = Field(min_length=8)
    severity: str = Field(default="warning")

    @field_validator("code", "message", "severity")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s


class AccrualTimelineEntry(StrictModel):
    timestamp: str | None = None
    event_type: str = Field(min_length=3)
    cell_id: str | None = None
    message: str = Field(min_length=8)
    details: dict[str, Any] | None = None

    @field_validator("event_type", "message")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("cell_id must contain non-space characters when provided")
        return s


class StoppingProgress(StrictModel):
    max_replicates: int | None = Field(default=None, ge=1)
    interim_looks_allowed: int = Field(ge=0)
    interim_looks_used: int = Field(ge=0)
    expected_count: int = Field(ge=0)
    attached_count: int = Field(ge=0)
    admitted_count: int = Field(ge=0)
    remaining: int = Field(ge=0)
    is_overrun: bool = False
    overrun_by: int = Field(default=0, ge=0)
    status: str = Field(min_length=3)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("status must contain non-space characters")
        return s


class AccrualCellEntry(StrictModel):
    cell_id: str = Field(min_length=1)
    arm_id: str | None = None
    seed_id: str | None = None
    policy_label: str | None = None
    replication_id: int | None = None
    metric_key: str | None = None
    metric_version: str | None = None
    replication_unit: str | None = None
    expected_identity: dict[str, Any] | None = None
    attachment_state: str = Field(min_length=3)
    admission_state: str = Field(min_length=3)
    compatibility: str = Field(min_length=3)
    first_observed_time: str | None = None
    latest_decision: str | None = None
    deviation_reason: str | None = None
    status: AccrualCellStatus

    @field_validator("attachment_state", "admission_state", "compatibility", "cell_id")
    @classmethod
    def validate_text(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s


class AccrualSnapshot(StrictModel):
    plan_id: str = Field(min_length=1)
    plan_fingerprint: str | None = None
    plan_version: int = Field(ge=1)
    plan_status: str = Field(min_length=2)
    expected_count: int = Field(ge=0)
    attached_count: int = Field(ge=0)
    admitted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    incompatible_count: int = Field(ge=0)
    extra_count: int = Field(ge=0)
    remaining_count: int = Field(ge=0)
    complete_count: int = Field(ge=0)
    attached_unadmitted_count: int = Field(ge=0)
    attached_admitted_count: int = Field(ge=0)
    planned_missing_count: int = Field(ge=0)
    withdrawn_count: int = Field(ge=0)
    post_evidence_amendment_count: int = Field(ge=0)
    power_plan_fingerprint: str | None = None


class AccrualReport(StrictModel):
    schema_version: str = Field(default="1.0", min_length=1)
    snapshot: AccrualSnapshot
    cells: list[AccrualCellEntry] = Field(default_factory=list)
    deviations: list[AccrualDeviation] = Field(default_factory=list)
    warnings: list[AccrualWarning] = Field(default_factory=list)
    stopping_progress: StoppingProgress
    timeline: list[AccrualTimelineEntry] = Field(default_factory=list)
    amendment_history: list[dict[str, Any]] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    power_plan_fingerprint: str | None = None
    fingerprint: str | None = None
    is_unavailable: bool = False
    unavailable_reason: str | None = None

    def canonical_payload(self) -> dict[str, Any]:
        """Return deterministic payload for fingerprinting, excluding wall-clock."""
        data = self.model_dump(mode="json", by_alias=True)
        # Remove volatile fingerprint and wall-clock fields
        data.pop("fingerprint", None)
        # Normalise timestamps in cells and timeline
        for cell in data.get("cells", []):
            if cell.get("first_observed_time") is not None:
                # Keep ISO but ensure sorted representation; raw value is already ISO
                pass
        for entry in data.get("timeline", []):
            if entry.get("timestamp") is not None:
                pass
        # Sort cells and deviations for determinism
        data["cells"] = sorted(data.get("cells", []), key=lambda c: c.get("cell_id", ""))
        data["deviations"] = sorted(
            data.get("deviations", []),
            key=lambda d: (d.get("code", ""), d.get("cell_id") or ""),
        )
        data["warnings"] = sorted(data.get("warnings", []), key=lambda w: w.get("code", ""))
        data["timeline"] = sorted(
            data.get("timeline", []),
            key=lambda t: (
                t.get("timestamp") or "",
                t.get("event_type", ""),
                t.get("cell_id") or "",
            ),
        )
        # Sort amendment_history by version for determinism
        data["amendment_history"] = sorted(
            data.get("amendment_history", []), key=lambda a: a.get("version", 0)
        )
        data["blockers"] = sorted(data.get("blockers", []))
        return data

    def compute_fingerprint(self) -> str:
        payload = self.canonical_payload()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def fingerprint_or_compute(self) -> str:
        if self.fingerprint is not None:
            return self.fingerprint
        return self.compute_fingerprint()


def _normalise_timestamp(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        # Normalise to UTC ISO Zulu without local path contamination
        if value.tzinfo is None:  # noqa: SIM108
            # Treat naive as UTC for portability but mark as normalised? Fail-closed earlier.
            dt = value.replace(tzinfo=UTC)
        else:
            dt = value.astimezone(UTC)
        return dt.isoformat().replace("+00:00", "Z")
    # String: attempt to parse but keep deterministic; if not parseable, return stripped
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:  # noqa: SIM108
            dt = dt.replace(tzinfo=UTC)
        else:
            dt = dt.astimezone(UTC)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return s

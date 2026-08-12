"""Typed models for Study Accrual & Deviation Monitor — remediation hardened."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base that rejects unknown fields and validates on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FrozenStrictModel(BaseModel):
    """Frozen variant for deterministic artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class AccrualCellStatus(StrEnum):
    """Mutually exclusive final state for one planned cell."""

    PLANNED_MISSING = "planned_missing"
    ATTACHED_UNADMITTED = "attached_unadmitted"
    INCOMPATIBLE = "incompatible"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXTRA = "extra"
    COMPLETE = "complete"
    DUPLICATE = "duplicate"


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
    GATE_REPORT_MISMATCH = "gate_report_mismatch"


class AccrualReviewState(StrEnum):
    """Typed review decision for Study Accrual handoff."""

    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


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
    planned_replicate_count: int = Field(ge=0)
    observed_replicate_count: int = Field(ge=0)
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
    planned_missing_count: int = Field(ge=0)
    withdrawn_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    post_evidence_amendment_count: int = Field(ge=0)
    power_plan_fingerprint: str | None = None
    planned_replicate_count: int = Field(ge=0)
    observed_replicate_count: int = Field(ge=0)


class AccrualReport(FrozenStrictModel):
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
        """Return deterministic payload for fingerprinting, excluding wall-clock.

        Runtime generation/retrieval clock is excluded; declared evidence/amendment
        timestamps are semantic timeline data and ARE preserved in the fingerprint.
        """
        data = self.model_dump(mode="json", by_alias=True)
        data.pop("fingerprint", None)
        data["cells"] = sorted(data.get("cells", []), key=lambda c: c.get("cell_id", ""))
        data["deviations"] = sorted(
            data.get("deviations", []),
            key=lambda d: (d.get("code", ""), d.get("cell_id") or ""),
        )
        data["warnings"] = sorted(data.get("warnings", []), key=lambda w: w.get("code", ""))

        def _canonical_details(details: Any) -> str:  # noqa: ANN401
            if details is None:
                return ""
            return json.dumps(
                details, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
            )

        data["timeline"] = sorted(
            data.get("timeline", []),
            key=lambda t: (
                t.get("timestamp") or "",
                t.get("event_type", ""),
                t.get("cell_id") or "",
                _canonical_details(t.get("details")),
                t.get("message") or "",
            ),
        )
        data["amendment_history"] = sorted(
            data.get("amendment_history", []), key=lambda a: a.get("version", 0)
        )
        data["blockers"] = sorted(data.get("blockers", []))
        return data

    def compute_fingerprint(self) -> str:
        payload = self.canonical_payload()
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def fingerprint_or_compute(self) -> str:
        if self.fingerprint is not None:
            return self.fingerprint
        return self.compute_fingerprint()


# ---------------------------------------------------------------------------
# Typed review handoff — replaces untyped generic_review_payload
# ---------------------------------------------------------------------------

MAX_REVIEW_DECISIONS = 10000
MAX_CELL_ID_LENGTH = 64
MAX_REASON_LENGTH = 500
MAX_INTERIM_LOOKS = 100


class AccrualReviewDecision(StrictModel):
    cell_id: str = Field(min_length=1, max_length=MAX_CELL_ID_LENGTH)
    state: AccrualReviewState
    decision_fingerprint: str | None = Field(default=None, min_length=8)
    source_reference: str | None = Field(default=None, min_length=4)
    decided_at: datetime | None = None
    reason: str | None = Field(default=None, min_length=8, max_length=MAX_REASON_LENGTH)

    @field_validator("cell_id")
    @classmethod
    def validate_cell_id(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("cell_id must contain non-space characters")
        if len(s) > MAX_CELL_ID_LENGTH:
            raise ValueError(f"cell_id exceeds max length {MAX_CELL_ID_LENGTH}")
        return s

    @field_validator("decision_fingerprint", "source_reference", "reason")
    @classmethod
    def validate_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters when provided")
        return s

    @field_validator("decided_at")
    @classmethod
    def validate_decided_at(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware; naive timestamps are rejected")
        return v.astimezone(UTC)


class AccrualReviewHandoff(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    source_fingerprint: str | None = Field(default=None, min_length=16)
    decisions: list[AccrualReviewDecision] = Field(default_factory=list)
    interim_looks_used: int | None = Field(default=None, ge=0, le=MAX_INTERIM_LOOKS)

    @field_validator("source_fingerprint")
    @classmethod
    def validate_source_fp(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("source_fingerprint must contain non-space characters when provided")
        if len(s) < 16:
            raise ValueError("source_fingerprint must contain at least 16 characters")
        return s

    @field_validator("decisions")
    @classmethod
    def validate_decisions(cls, v: list[AccrualReviewDecision]) -> list[AccrualReviewDecision]:
        if len(v) > MAX_REVIEW_DECISIONS:
            raise ValueError(f"too many review decisions: {len(v)} exceeds {MAX_REVIEW_DECISIONS}")
        # Check duplicate cell_id + same state contradictions via model_validator below
        return v

    @model_validator(mode="after")
    def validate_no_contradictions(self) -> AccrualReviewHandoff:
        seen: dict[str, AccrualReviewState] = {}
        for dec in self.decisions:
            if dec.cell_id in seen:
                # Duplicate decision for same cell — reject regardless of same/different state
                raise ValueError(f"duplicate review decision for cell {dec.cell_id!r}")
            seen[dec.cell_id] = dec.state
        return self


def _normalise_timestamp(value: datetime | str | None) -> str | None:
    """Return UTC-normalised ISO timestamp or raise on invalid time basis.

    - Aware datetime → normalized to UTC Z.
    - Naive datetime → raises ValueError (fail-closed, do not invent UTC).
    - String → parsed as ISO; if naive → raises; if invalid → raises ValueError.
    - None → None.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware; naive timestamps are rejected")
        dt = value.astimezone(UTC)
        return dt.isoformat().replace("+00:00", "Z")
    s = str(value).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception as exc:
        raise ValueError(f"invalid timestamp string {s!r}: {exc}") from exc
    if dt.tzinfo is None:
        raise ValueError(f"timestamp string must be timezone-aware: {s!r}")
    dt = dt.astimezone(UTC)
    return dt.isoformat().replace("+00:00", "Z")

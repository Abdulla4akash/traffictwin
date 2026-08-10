"""Strict typed models for the Baseline Registry & Promotion Workflow (V4).

The newest, fastest, or lowest-error candidate must never be promoted
automatically. Promotion requires an explicit review record.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASELINE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
BASELINE_METHOD_VERSION: Literal["1.0"] = "1.0"

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[-+][A-Za-z0-9.-]+)?$")

# Absolute-path patterns – must be redacted in portable artifacts.
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_ABS = re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+")

MAX_CANDIDATES = 500
MAX_LEDGER_ENTRIES = 5000
MAX_METRIC_CONTRACTS = 64
MAX_LIMITATIONS_LEN = 2000


def _contains_absolute_path(value: str) -> bool:
    return bool(
        _WINDOWS_PATH.search(value)
        or _FILE_URI.search(value)
        or _HOME_PATH.search(value)
        or (_POSIX_ABS.search(value) and "/" in value and value.count("/") > 1)
    )


def _validate_identifier(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must contain non-space characters")
    if _contains_absolute_path(stripped):
        raise ValueError(f"{field_name} must not contain absolute local paths")
    if not _IDENTIFIER_RE.fullmatch(stripped):
        raise ValueError(
            f"{field_name} must use 2-128 letters, digits, dots, underscores, or hyphens"
        )
    if len(stripped) < 2 or len(stripped) > 128:
        raise ValueError(f"{field_name} must be 2-128 characters")
    return stripped


def _validate_sha256(value: str, field_name: str) -> str:
    stripped = value.strip().lower()
    if not _SHA256_RE.fullmatch(stripped):
        raise ValueError(f"{field_name} must be a 64-character lowercase hex SHA-256")
    return stripped


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _fingerprint(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _validate_no_absolute_path(value: str, field_name: str) -> str:
    stripped = value.strip()
    if _contains_absolute_path(stripped):
        raise ValueError(f"{field_name} must not contain absolute local paths")
    return stripped


# ---------------------------------------------------------------------------
# Strict base
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    """Strict base – no unknown fields, validated on assignment."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class FrozenStrictModel(BaseModel):
    """Frozen strict base for immutable records."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class BaselineArtifactType(StrEnum):
    """Bounded artifact families that can be baselined."""

    METRIC_COLLECTION = "metric_collection"
    PAIRED_STATISTICAL_STUDY = "paired_statistical_study"
    EVIDENCE_PACK = "evidence_pack"
    COMPARISON_REPORT = "comparison_report"
    RUN_BUNDLE = "run_bundle"
    DETERMINISTIC_REPORT = "deterministic_report"
    SYNTHETIC_DERIVED = "synthetic_derived"


class BaselineEvidenceStanding(StrEnum):
    """Evidence/admission standing for a candidate or baseline."""

    ADMITTED_RESEARCH = "admitted_research"
    SYNTHETIC_DEMONSTRATION = "synthetic_demonstration"
    IMPORTED = "imported"
    HISTORICAL_OBSERVATION = "historical_observation"
    UNADMITTED_RESEARCH = "unadmitted_research"
    AUTHORED_CONFIGURATION = "authored_configuration"
    UNAVAILABLE = "unavailable"


class BaselineSourceStanding(StrEnum):
    """Source standing for a candidate or baseline."""

    VERIFIED = "verified"
    SYNTHETIC = "synthetic"
    IMPORTED = "imported"
    HISTORICAL = "historical"
    UNADMITTED = "unadmitted"
    UNAVAILABLE = "unavailable"


class BaselineStatus(StrEnum):
    """Status of a baseline record or candidate."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    UNAVAILABLE = "unavailable"
    BLOCKED = "blocked"


class BaselineLedgerEventKind(StrEnum):
    """Append-only ledger event kinds."""

    CANDIDATE_REGISTERED = "candidate_registered"
    APPROVED = "approved"
    PROMOTED = "promoted"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"
    RESTORED_AS_NEW_PROMOTION = "restored_as_new_promotion"


class BaselinePromotionOperation(StrEnum):
    """Typed promotion operation."""

    PROMOTE = "promote"
    SUPERSEDE = "supersede"
    RESTORE = "restore"


# ---------------------------------------------------------------------------
# Small models
# ---------------------------------------------------------------------------


class BaselineScope(StrictModel):
    """Purpose/scope definition for a baseline lane with typed evidence policy."""

    scope_id: str = Field(min_length=2, max_length=128)
    purpose: str = Field(min_length=12, max_length=2000)
    cohort_definition: str = Field(min_length=8, max_length=2000)
    allowed_evidence_standings: tuple[BaselineEvidenceStanding, ...] = Field(
        default=(BaselineEvidenceStanding.ADMITTED_RESEARCH,),
        min_length=1,
        max_length=16,
    )

    @field_validator("scope_id")
    @classmethod
    def validate_scope_id(cls, v: str) -> str:
        return _validate_identifier(v, "scope_id")

    @field_validator("purpose", "cohort_definition")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if _contains_absolute_path(stripped):
            raise ValueError("value must not contain absolute local paths")
        if not stripped:
            raise ValueError("value must contain non-space characters")
        return stripped

    @field_validator("allowed_evidence_standings", mode="before")
    @classmethod
    def validate_allowed_before(cls, v: object) -> tuple[BaselineEvidenceStanding, ...]:
        if not isinstance(v, (list, tuple)):
            raise ValueError("allowed_evidence_standings must be a list or tuple")
        items = list(v)
        if not items:
            raise ValueError("allowed_evidence_standings must be non-empty")
        # Coerce to enum and validate
        coerced: list[BaselineEvidenceStanding] = []
        for item in items:
            try:
                ev = (
                    item
                    if isinstance(item, BaselineEvidenceStanding)
                    else BaselineEvidenceStanding(item)
                )  # noqa: E501
            except ValueError as exc:
                raise ValueError(f"unsupported evidence standing: {item}") from exc
            if ev is BaselineEvidenceStanding.UNAVAILABLE:
                raise ValueError("UNAVAILABLE must never be an allowed policy value")
            coerced.append(ev)
        if len(set(coerced)) != len(coerced):
            raise ValueError("allowed_evidence_standings must not contain duplicates")
        # Canonicalize: sorted by value string
        canonical = tuple(sorted(set(coerced), key=lambda x: x.value))
        # If original order was different but set same, we canonicalize to sorted
        return canonical

    def canonical_payload(self) -> dict[str, Any]:
        # Ensure allowed standings are serialized as sorted value strings for fingerprint stability
        payload = self.model_dump(mode="json")
        # model_dump already gives list of strings sorted via validator, but ensure canonical order
        payload["allowed_evidence_standings"] = sorted(payload["allowed_evidence_standings"])
        return payload

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


class BaselineCandidate(StrictModel):
    """A candidate artifact proposed as a baseline for a scope."""

    candidate_id: str = Field(min_length=2, max_length=128)
    scope: BaselineScope
    artifact_fingerprint: str = Field(min_length=64, max_length=64)
    artifact_type: BaselineArtifactType
    schema_version: str = Field(min_length=3, max_length=32)
    metric_contracts: list[str] = Field(default_factory=list, max_length=MAX_METRIC_CONTRACTS)
    cohort_definition: str = Field(min_length=8, max_length=2000)
    evidence_standing: BaselineEvidenceStanding
    source_standing: BaselineSourceStanding
    regression_gate_policy: str = Field(min_length=12, max_length=1000)
    limitations: str = Field(min_length=12, max_length=MAX_LIMITATIONS_LEN)
    created_at: datetime

    @field_validator("candidate_id")
    @classmethod
    def validate_candidate_id(cls, v: str) -> str:
        return _validate_identifier(v, "candidate_id")

    @field_validator("artifact_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "artifact_fingerprint")

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        stripped = v.strip()
        if not _VERSION_RE.fullmatch(stripped):
            raise ValueError("schema_version must be a dotted numeric version")
        return stripped

    @field_validator("metric_contracts")
    @classmethod
    def validate_metric_contracts(cls, v: list[str]) -> list[str]:
        for item in v:
            stripped = item.strip()
            if not stripped:
                raise ValueError("metric_contracts items must not be blank")
            if len(stripped) > 256:
                raise ValueError("metric_contracts item too long")
            if _contains_absolute_path(stripped):
                raise ValueError("metric_contracts must not contain absolute paths")
        if len(v) != len(set(v)):
            raise ValueError("metric_contracts must not contain duplicates")
        return [s.strip() for s in v]

    @field_validator("regression_gate_policy", "limitations", "cohort_definition")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if _contains_absolute_path(stripped):
            raise ValueError("value must not contain absolute local paths")
        return stripped

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return v

    @model_validator(mode="after")
    def validate_cohort_matches_scope(self) -> BaselineCandidate:
        if self.cohort_definition != self.scope.cohort_definition:
            raise ValueError("candidate cohort_definition must equal scope cohort_definition")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json")
        # Ensure scope's allowed standings are canonical sorted
        if "scope" in payload and "allowed_evidence_standings" in payload["scope"]:
            payload["scope"]["allowed_evidence_standings"] = sorted(
                payload["scope"]["allowed_evidence_standings"]
            )
        return payload

    def fingerprint(self) -> str:
        payload = self.canonical_payload()
        return _fingerprint(payload)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class BaselineApproval(StrictModel):
    """Explicit approval binding an exact candidate and scope."""

    approval_id: str = Field(min_length=2, max_length=128)
    candidate_id: str = Field(min_length=2, max_length=128)
    scope_id: str = Field(min_length=2, max_length=128)
    artifact_fingerprint: str = Field(min_length=64, max_length=64)
    approver: str = Field(min_length=3, max_length=128)
    approval_note: str = Field(min_length=12, max_length=2000)
    approved_at: datetime
    approval_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("approval_id", "candidate_id", "scope_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        return _validate_identifier(v, "identifier")

    @field_validator("artifact_fingerprint", "approval_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "fingerprint")

    @field_validator("approver", "approval_note")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if _contains_absolute_path(stripped):
            raise ValueError("value must not contain absolute local paths")
        if not stripped:
            raise ValueError("value must not be blank")
        return stripped

    @field_validator("approved_at")
    @classmethod
    def validate_approved_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("approved_at must be timezone-aware")
        return v

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"approval_fingerprint"})
        return payload

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class BaselineRecord(StrictModel):
    """A promoted, versioned baseline binding all required dimensions."""

    baseline_id: str = Field(min_length=2, max_length=128)
    scope: BaselineScope
    artifact_fingerprint: str = Field(min_length=64, max_length=64)
    artifact_type: BaselineArtifactType
    schema_version: str = Field(min_length=3, max_length=32)
    metric_contracts: list[str] = Field(default_factory=list, max_length=MAX_METRIC_CONTRACTS)
    cohort_definition: str = Field(min_length=8, max_length=2000)
    evidence_standing: BaselineEvidenceStanding
    source_standing: BaselineSourceStanding
    approval_fingerprint: str = Field(min_length=64, max_length=64)
    effective_date: date
    superseded_baseline_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    regression_gate_policy: str = Field(min_length=12, max_length=1000)
    limitations: str = Field(min_length=12, max_length=MAX_LIMITATIONS_LEN)
    candidate_id: str = Field(min_length=2, max_length=128)
    status: BaselineStatus = BaselineStatus.ACTIVE
    created_at: datetime
    record_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("baseline_id", "candidate_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        return _validate_identifier(v, "identifier")

    @field_validator("artifact_fingerprint", "approval_fingerprint", "record_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "fingerprint")

    @field_validator("superseded_baseline_fingerprint")
    @classmethod
    def validate_superseded(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_sha256(v, "superseded_baseline_fingerprint")

    @field_validator("schema_version")
    @classmethod
    def validate_schema(cls, v: str) -> str:
        stripped = v.strip()
        if not _VERSION_RE.fullmatch(stripped):
            raise ValueError("schema_version must be a dotted numeric version")
        return stripped

    @field_validator("metric_contracts")
    @classmethod
    def validate_metric_contracts(cls, v: list[str]) -> list[str]:
        for item in v:
            stripped = item.strip()
            if not stripped:
                raise ValueError("metric_contracts items must not be blank")
            if _contains_absolute_path(stripped):
                raise ValueError("metric_contracts must not contain absolute paths")
        if len(v) != len(set(v)):
            raise ValueError("metric_contracts must not contain duplicates")
        return [s.strip() for s in v]

    @field_validator("regression_gate_policy", "limitations", "cohort_definition")
    @classmethod
    def validate_text(cls, v: str) -> str:
        stripped = v.strip()
        if _contains_absolute_path(stripped):
            raise ValueError("value must not contain absolute local paths")
        return stripped

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return v

    @model_validator(mode="after")
    def validate_cohort(self) -> BaselineRecord:
        if self.cohort_definition != self.scope.cohort_definition:
            raise ValueError("record cohort_definition must equal scope cohort_definition")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"record_fingerprint"})
        if "scope" in payload and "allowed_evidence_standings" in payload["scope"]:
            payload["scope"]["allowed_evidence_standings"] = sorted(
                payload["scope"]["allowed_evidence_standings"]
            )
        return payload

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class BaselineLedgerEntry(StrictModel):
    """One append-only ledger event."""

    entry_index: int = Field(ge=0)
    event_kind: BaselineLedgerEventKind
    timestamp: datetime
    scope_id: str = Field(min_length=2, max_length=128)
    candidate_id: str | None = Field(default=None, min_length=2, max_length=128)
    baseline_id: str | None = Field(default=None, min_length=2, max_length=128)
    artifact_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    approval_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    superseded_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    registry_parent_fingerprint: str = Field(min_length=64, max_length=64)
    entry_fingerprint: str = Field(min_length=64, max_length=64)
    actor: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("scope_id")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        return _validate_identifier(v, "scope_id")

    @field_validator("candidate_id", "baseline_id")
    @classmethod
    def validate_optional_ids(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_identifier(v, "identifier")

    @field_validator(
        "artifact_fingerprint",
        "approval_fingerprint",
        "superseded_fingerprint",
        "registry_parent_fingerprint",
        "entry_fingerprint",
    )
    @classmethod
    def validate_optional_fp(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _validate_sha256(v, "fingerprint")

    @field_validator("timestamp")
    @classmethod
    def validate_ts(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v

    @field_validator("actor", "note")
    @classmethod
    def validate_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            return None
        if _contains_absolute_path(stripped):
            raise ValueError("value must not contain absolute local paths")
        return stripped

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"entry_fingerprint"})
        return payload

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class BaselineRegistry(StrictModel):
    """Append-only registry holding ledger and derived active view."""

    schema_version: Literal["1.0"] = BASELINE_SCHEMA_VERSION
    created_at: datetime
    ledger: list[BaselineLedgerEntry] = Field(default_factory=list, max_length=MAX_LEDGER_ENTRIES)
    candidates: dict[str, BaselineCandidate] = Field(default_factory=dict)
    approvals: dict[str, BaselineApproval] = Field(default_factory=dict)
    active_baselines: dict[str, BaselineRecord] = Field(default_factory=dict)
    registry_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return v

    @field_validator("registry_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "registry_fingerprint")

    @model_validator(mode="after")
    def validate_sizes(self) -> BaselineRegistry:
        if len(self.candidates) > MAX_CANDIDATES:
            raise ValueError("too many candidates")
        if len(self.ledger) > MAX_LEDGER_ENTRIES:
            raise ValueError("too many ledger entries")
        if len(self.active_baselines) > MAX_CANDIDATES:
            raise ValueError("too many active baselines")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"registry_fingerprint", "created_at"})
        return payload

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())


class BaselinePromotionRequest(StrictModel):
    """Request to promote a candidate to active baseline."""

    candidate_id: str = Field(min_length=2, max_length=128)
    scope_id: str = Field(min_length=2, max_length=128)
    artifact_fingerprint: str = Field(min_length=64, max_length=64)
    approval_fingerprint: str = Field(min_length=64, max_length=64)
    registry_parent_fingerprint: str = Field(min_length=64, max_length=64)
    requested_by: str = Field(min_length=3, max_length=128)
    requested_at: datetime
    operation: BaselinePromotionOperation = BaselinePromotionOperation.PROMOTE

    @field_validator("candidate_id", "scope_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        return _validate_identifier(v, "identifier")

    @field_validator("artifact_fingerprint", "approval_fingerprint", "registry_parent_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "fingerprint")

    @field_validator("requested_by")
    @classmethod
    def validate_requested_by(cls, v: str) -> str:
        stripped = v.strip()
        if _contains_absolute_path(stripped):
            raise ValueError("requested_by must not contain absolute paths")
        if len(stripped) < 3:
            raise ValueError("requested_by must contain at least 3 characters")
        return stripped

    @field_validator("requested_at")
    @classmethod
    def validate_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        return v

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


class BaselinePromotionReceipt(StrictModel):
    """Result of a promotion attempt – either promoted or blocked."""

    request: BaselinePromotionRequest
    status: BaselineStatus
    promoted_record: BaselineRecord | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    audit: BaselineCompatibilityAudit | None = None
    receipt_fingerprint: str = Field(min_length=64, max_length=64)
    created_at: datetime

    @field_validator("receipt_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "receipt_fingerprint")

    @field_validator("created_at")
    @classmethod
    def validate_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return v

    @model_validator(mode="after")
    def validate_receipt(self) -> BaselinePromotionReceipt:
        if self.status is BaselineStatus.ACTIVE and self.promoted_record is None:
            raise ValueError("ACTIVE receipt requires promoted_record")
        if (
            self.status not in (BaselineStatus.ACTIVE, BaselineStatus.BLOCKED)
            and self.promoted_record is not None
        ):
            raise ValueError("only ACTIVE/BLOCKED receipts may carry promoted_record logic")
        if self.status is BaselineStatus.BLOCKED and self.promoted_record is not None:
            raise ValueError("BLOCKED receipt must not carry promoted_record")
        if self.status is BaselineStatus.UNAVAILABLE and self.promoted_record is not None:
            raise ValueError("UNAVAILABLE receipt must not carry promoted_record")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude={"receipt_fingerprint"})
        return payload

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


class BaselineCompatibilityAudit(StrictModel):
    """Compatibility audit for a promotion gate."""

    candidate_id: str = Field(min_length=2, max_length=128)
    scope_id: str = Field(min_length=2, max_length=128)
    artifact_fingerprint_verified: bool
    scope_compatible: bool
    evidence_policy_satisfied: bool
    source_standing_satisfied: bool
    approval_binds: bool
    no_stale_parent: bool
    operation_preconditions_satisfied: bool
    findings: list[str] = Field(default_factory=list, max_length=64)
    passed: bool
    audit_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator("candidate_id", "scope_id")
    @classmethod
    def validate_ids(cls, v: str) -> str:
        return _validate_identifier(v, "identifier")

    @field_validator("audit_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_sha256(v, "audit_fingerprint")

    @field_validator("findings")
    @classmethod
    def validate_findings(cls, v: list[str]) -> list[str]:
        for item in v:
            if _contains_absolute_path(item):
                raise ValueError("findings must not contain absolute paths")
        return v

    @model_validator(mode="after")
    def validate_passed(self) -> BaselineCompatibilityAudit:
        expected = (
            self.artifact_fingerprint_verified
            and self.scope_compatible
            and self.evidence_policy_satisfied
            and self.source_standing_satisfied
            and self.approval_binds
            and self.no_stale_parent
            and self.operation_preconditions_satisfied
        )
        if self.passed is not expected:
            raise ValueError("passed must equal conjunction of all gate checks")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude={"audit_fingerprint"})

    def compute_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)

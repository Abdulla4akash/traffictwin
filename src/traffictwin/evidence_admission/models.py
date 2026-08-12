"""Typed domain models for the Evidence Admission Inbox.

Validation is not admission. Only an explicit human decision in the admitted
state may create an admitted EvidenceAttachment for Preregistration Studio.

Evidence and authority boundary: this module records human review decisions
over imported/validated artifacts; it does not establish external validity,
real-world robustness, or Manchester evidence, and it never automatically
admits evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.preregistration.models import ArtifactAdmission, EvidenceAttachment

# ---------------------------------------------------------------------------
# Canonical fingerprint helper (deterministic, local-path free)
# ---------------------------------------------------------------------------

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]*$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

MAX_CASE_ID_LENGTH = 64
MAX_CELL_ID_LENGTH = 128
MAX_METRIC_KEY_LENGTH = 128
MAX_METRIC_VERSION_LENGTH = 64
MAX_UNIT_LENGTH = 32
MAX_REASON_LENGTH = 500
MAX_REVIEWER_LABEL_LENGTH = 64
MAX_FINDING_CODE_LENGTH = 64
MAX_FINDING_DESC_LENGTH = 500
MAX_REQUESTED_FIELDS = 10
MAX_REQUESTED_FIELD_LENGTH = 64
MAX_FINDINGS = 32


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_identifier(value: str, field_name: str) -> str:
    s = value.strip()
    if not s:
        raise ValueError(f"{field_name} must contain non-space characters")
    if not _IDENTIFIER_RE.fullmatch(s):
        raise ValueError(
            f"{field_name} must start with alphanumeric and contain only "
            "letters, numbers, dots, underscores, colons, or hyphens"
        )
    return s


def _validate_hex64(value: str, field_name: str) -> str:
    s = value.strip().lower()
    if not _HEX64_RE.fullmatch(s):
        raise ValueError(f"{field_name} must be 64-character lower-case hex")
    return s


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    """Strict base rejecting unknown fields and validating on assignment."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        str_strip_whitespace=False,
        frozen=True,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EvidenceReviewState(StrEnum):
    """Human review states for one evidence candidate."""

    PENDING = "pending"
    NEEDS_INFORMATION = "needs_information"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class EvidenceMode(StrEnum):
    """Observed evidence mode for one candidate binding."""

    AUTHORED_CONFIGURATION = "authored_configuration"
    SYNTHETIC_EVIDENCE = "synthetic_evidence"
    IMPORTED_EVIDENCE = "imported_evidence"
    HISTORICAL_OBSERVATION = "historical_observation"
    ADMITTED_RESEARCH = "admitted_research"
    UNAVAILABLE = "unavailable"


class RightsPrivacyStanding(StrEnum):
    """Privacy/rights standing before admission."""

    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    UNAVAILABLE = "unavailable"
    PENDING_REVIEW = "pending_review"


class ValidationStanding(StrEnum):
    """Artifact validation standing - validation is not admission."""

    VALIDATED = "validated"
    PENDING = "pending"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class CompatibilityStanding(StrEnum):
    """Metric/version/unit compatibility with the preregistration cell."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNRESOLVED = "unresolved"


class FindingCategory(StrEnum):
    """Category for one review finding."""

    RIGHTS_PRIVACY = "rights_privacy"
    VALIDATION = "validation"
    COMPATIBILITY = "compatibility"
    EVIDENCE_MODE = "evidence_mode"
    SOURCE_CONTRACT = "source_contract"
    OTHER = "other"


class FindingSeverity(StrEnum):
    """Severity of one review finding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


# ---------------------------------------------------------------------------
# Small models
# ---------------------------------------------------------------------------


class EvidenceCandidateBinding(StrictModel):
    """Typed binding between a candidate artifact and its preregistration cell."""

    candidate_artifact_fingerprint: str = Field(description="64-char hex artifact fingerprint")
    expected_preregistration_cell_id: str = Field(min_length=1, max_length=MAX_CELL_ID_LENGTH)
    observed_metric_key: str = Field(min_length=1, max_length=MAX_METRIC_KEY_LENGTH)
    observed_metric_version: str = Field(min_length=1, max_length=MAX_METRIC_VERSION_LENGTH)
    observed_metric_unit: str = Field(min_length=1, max_length=MAX_UNIT_LENGTH)
    evidence_mode: EvidenceMode
    source_contract_result_fingerprint: str = Field(description="64-char hex contract fingerprint")

    @field_validator("candidate_artifact_fingerprint", "source_contract_result_fingerprint")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        return _validate_hex64(v, "fingerprint")

    @field_validator("expected_preregistration_cell_id")
    @classmethod
    def validate_cell(cls, v: str) -> str:
        return _validate_identifier(v, "expected_preregistration_cell_id")

    @field_validator("observed_metric_key", "observed_metric_version", "observed_metric_unit")
    @classmethod
    def validate_metric(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


class EvidenceReviewFinding(StrictModel):
    """One structured finding surfaced before the decision controls."""

    code: str = Field(min_length=1, max_length=MAX_FINDING_CODE_LENGTH)
    category: FindingCategory
    severity: FindingSeverity
    description: str = Field(min_length=1, max_length=MAX_FINDING_DESC_LENGTH)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        return _validate_identifier(v, "finding code")

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("description must contain non-space characters")
        return s


# ---------------------------------------------------------------------------
# Ledger decision entry (append-only, hash-chained)
# ---------------------------------------------------------------------------


class EvidenceReviewDecision(StrictModel):
    """One immutable decision entry in the hash-chained ledger.

    Every decision binds the previous fingerprint, the case fingerprint,
    the requested transition, the reason, the reviewer, the timestamp,
    and optional requested-information fields. In-place editing is never
    permitted; a correction creates a new entry.
    """

    decision_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_fingerprint: str = Field(description="64-char hex case fingerprint at decision time")
    previous_decision_fingerprint: str = Field(description="64-char hex previous entry fingerprint")
    decision: EvidenceReviewState
    reason: str = Field(min_length=1, max_length=MAX_REASON_LENGTH)
    reviewer_label: str = Field(min_length=1, max_length=MAX_REVIEWER_LABEL_LENGTH)
    decision_timestamp: datetime
    requested_information_fields: list[str] = Field(default_factory=list)

    @field_validator("decision_id", "case_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_identifier(v, "decision_id/case_id")

    @field_validator("case_fingerprint", "previous_decision_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_hex64(v, "decision fingerprint")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("reviewer_label")
    @classmethod
    def validate_reviewer(cls, v: str) -> str:
        return _validate_identifier(v, "reviewer_label")

    @field_validator("requested_information_fields")
    @classmethod
    def validate_requested(cls, v: list[str]) -> list[str]:
        if len(v) > MAX_REQUESTED_FIELDS:
            raise ValueError(
                f"requested_information_fields must contain at most {MAX_REQUESTED_FIELDS}"
            )
        cleaned: list[str] = []
        for item in v:
            s = item.strip()
            if not s:
                raise ValueError("requested field must contain non-space characters")
            if len(s) > MAX_REQUESTED_FIELD_LENGTH:
                raise ValueError(f"requested field exceeds {MAX_REQUESTED_FIELD_LENGTH} characters")
            if not _IDENTIFIER_RE.fullmatch(s):
                raise ValueError(f"requested field {s!r} has invalid identifier shape")
            cleaned.append(s)
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("requested_information_fields must not contain duplicates")
        return sorted(cleaned)

    @field_validator("decision_timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware")
        return v.astimezone(UTC)

    def canonical_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        return data

    def fingerprint(self) -> str:
        payload = self.canonical_payload()
        return _fingerprint(payload)


class EvidenceReviewLedger(StrictModel):
    """Append-only hash-chained decision ledger for one case.

    The chain is verified by checking that each entry's
    previous_decision_fingerprint equals the predecessor's fingerprint,
    starting from the genesis sentinel (64 zeros) for the first entry.
    """

    case_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_fingerprint: str = Field(description="64-char hex case fingerprint")
    decisions: tuple[EvidenceReviewDecision, ...] = Field(default_factory=tuple)

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        return _validate_identifier(v, "case_id")

    @field_validator("case_fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        return _validate_hex64(v, "case fingerprint")

    @property
    def tail_fingerprint(self) -> str:
        if not self.decisions:
            return "0" * 64
        return self.decisions[-1].fingerprint()

    @property
    def current_state(self) -> EvidenceReviewState | None:
        if not self.decisions:
            return None
        return self.decisions[-1].decision

    def verify(self) -> list[str]:
        """Return list of chain violations; empty means verified."""
        violations: list[str] = []
        expected_prev = "0" * 64
        seen_ids: set[str] = set()
        for dec in self.decisions:
            if dec.decision_id in seen_ids:
                violations.append(f"duplicate decision_id {dec.decision_id!r}")
            seen_ids.add(dec.decision_id)
            if dec.case_id != self.case_id:
                violations.append(f"decision {dec.decision_id!r} has mismatched case_id")
            if dec.case_fingerprint != self.case_fingerprint:
                violations.append(f"decision {dec.decision_id!r} has mismatched case_fingerprint")
            if dec.previous_decision_fingerprint != expected_prev:
                violations.append(
                    f"decision {dec.decision_id!r} has stale previous fingerprint "
                    f"expected {expected_prev[:8]}… got {dec.previous_decision_fingerprint[:8]}…"
                )
            expected_prev = dec.fingerprint()
        return violations

    def verifies(self) -> bool:
        return not self.verify()


# ---------------------------------------------------------------------------
# Review case
# ---------------------------------------------------------------------------


class EvidenceReviewCase(StrictModel):
    """One human-review case between validation and preregistration admission.

    The case binds the candidate artifact, its preregistration cell,
    observed metric key/version/unit, evidence mode, contract fingerprint,
    rights/privacy, validation, and compatibility standings, plus the
    ledger-derived current state. The reviewer history lives in the ledger.
    """

    case_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    candidate_artifact_fingerprint: str
    expected_preregistration_cell_id: str = Field(min_length=1, max_length=MAX_CELL_ID_LENGTH)
    observed_metric_key: str = Field(min_length=1, max_length=MAX_METRIC_KEY_LENGTH)
    observed_metric_version: str = Field(min_length=1, max_length=MAX_METRIC_VERSION_LENGTH)
    observed_metric_unit: str = Field(min_length=1, max_length=MAX_UNIT_LENGTH)
    evidence_mode: EvidenceMode
    source_contract_result_fingerprint: str
    rights_privacy_standing: RightsPrivacyStanding
    validation_standing: ValidationStanding
    compatibility_standing: CompatibilityStanding
    findings: list[EvidenceReviewFinding] = Field(default_factory=list)
    current_state: EvidenceReviewState = EvidenceReviewState.PENDING
    created_at: datetime
    updated_at: datetime
    candidate_binding: EvidenceCandidateBinding | None = None
    ledger_tail_fingerprint: str = Field(default="0" * 64)

    @field_validator("case_id")
    @classmethod
    def validate_case_id(cls, v: str) -> str:
        return _validate_identifier(v, "case_id")

    @field_validator("candidate_artifact_fingerprint", "source_contract_result_fingerprint")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        return _validate_hex64(v, "fingerprint")

    @field_validator("expected_preregistration_cell_id")
    @classmethod
    def validate_cell(cls, v: str) -> str:
        return _validate_identifier(v, "expected_preregistration_cell_id")

    @field_validator("observed_metric_key", "observed_metric_version", "observed_metric_unit")
    @classmethod
    def validate_metric_fields(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("findings")
    @classmethod
    def validate_findings(cls, v: list[EvidenceReviewFinding]) -> list[EvidenceReviewFinding]:
        if len(v) > MAX_FINDINGS:
            raise ValueError(f"findings must contain at most {MAX_FINDINGS} entries")
        codes = [f.code for f in v]
        if len(set(codes)) != len(codes):
            raise ValueError("finding codes must be unique within a case")
        return v

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_timestamps(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        return v.astimezone(UTC)

    @field_validator("ledger_tail_fingerprint")
    @classmethod
    def validate_tail(cls, v: str) -> str:
        return _validate_hex64(v, "ledger_tail_fingerprint")

    @model_validator(mode="after")
    def validate_binding_consistency(self) -> EvidenceReviewCase:
        if self.candidate_binding is not None:
            if (
                self.candidate_binding.candidate_artifact_fingerprint
                != self.candidate_artifact_fingerprint
            ):
                raise ValueError("candidate_binding fingerprint does not match case fingerprint")
            if (
                self.candidate_binding.expected_preregistration_cell_id
                != self.expected_preregistration_cell_id
            ):
                raise ValueError("candidate_binding cell_id does not match case cell_id")
            if self.candidate_binding.observed_metric_key != self.observed_metric_key:
                raise ValueError("candidate_binding metric_key does not match case metric_key")
            if self.candidate_binding.observed_metric_version != self.observed_metric_version:
                raise ValueError("candidate_binding metric_version does not match case")
            if self.candidate_binding.observed_metric_unit != self.observed_metric_unit:
                raise ValueError("candidate_binding unit does not match case unit")
            if self.candidate_binding.evidence_mode != self.evidence_mode:
                raise ValueError("candidate_binding evidence_mode does not match case")
            if (
                self.candidate_binding.source_contract_result_fingerprint
                != self.source_contract_result_fingerprint
            ):
                raise ValueError("candidate_binding contract fingerprint does not match case")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Deterministic payload for identity, excluding wall-clock and transient ledger tail."""
        data = self.model_dump(mode="json")
        # Exclude volatile timestamps from identity; keep semantic but normalise
        for key in ("created_at", "updated_at"):
            data[key] = "<normalised>"
        # Ledger tail is derived chain state, not semantic identity of the binding
        data.pop("ledger_tail_fingerprint", None)
        # current_state is derived from ledger, not part of binding fingerprint
        data.pop("current_state", None)
        # Remove findings ordering variance by sorting
        if "findings" in data and isinstance(data["findings"], list):
            data["findings"] = sorted(data["findings"], key=lambda x: x.get("code", ""))
        return data

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def evidence_and_authority_boundary(self) -> str:
        return (
            "Validation is not admission. This queue records human review over "
            "imported/validated artifacts; it does not establish external validity, "
            "Manchester evidence, causality, or optimality. Only an explicit admitted "
            "decision may create an admitted EvidenceAttachment."
        )


# ---------------------------------------------------------------------------
# Export and receipt
# ---------------------------------------------------------------------------


class EvidenceAdmissionExport(StrictModel):
    """Deterministic admitted attachment export derived from an admitted case.

    The attachment uses is_admitted=True and an admission label consistent
    with Preregistration Studio (ArtifactAdmission.ADMITTED).
    """

    export_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_fingerprint: str
    ledger_tail_fingerprint: str
    attachment: EvidenceAttachment
    exported_at: datetime
    fingerprint: str = Field(description="64-char hex export fingerprint")

    @field_validator("export_id", "case_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_identifier(v, "export_id/case_id")

    @field_validator("case_fingerprint", "ledger_tail_fingerprint", "fingerprint")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        return _validate_hex64(v, "fingerprint")

    @field_validator("exported_at")
    @classmethod
    def validate_ts(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("exported_at must be timezone-aware")
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def validate_admission(self) -> EvidenceAdmissionExport:
        if self.attachment.is_admitted is not True:
            raise ValueError("admission export attachment must have is_admitted=True")
        if self.attachment.admission_label != ArtifactAdmission.ADMITTED:
            raise ValueError("admission export attachment must have admission_label=admitted")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["exported_at"] = "<normalised>"
        data.pop("fingerprint", None)
        return data

    def computed_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


class EvidenceReviewReceipt(StrictModel):
    """Portable receipt for one ledger decision, without credential data."""

    receipt_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    decision_id: str = Field(min_length=1, max_length=MAX_CASE_ID_LENGTH)
    case_fingerprint: str
    decision_fingerprint: str
    ledger_tail_fingerprint: str
    decision: EvidenceReviewState
    reason: str = Field(min_length=1, max_length=MAX_REASON_LENGTH)
    reviewer_label: str = Field(min_length=1, max_length=MAX_REVIEWER_LABEL_LENGTH)
    decision_timestamp: datetime
    previous_decision_fingerprint: str
    requested_information_fields: list[str] = Field(default_factory=list)
    fingerprint: str

    @field_validator("receipt_id", "case_id", "decision_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        return _validate_identifier(v, "id")

    @field_validator(
        "case_fingerprint",
        "decision_fingerprint",
        "ledger_tail_fingerprint",
        "previous_decision_fingerprint",
        "fingerprint",
    )
    @classmethod
    def validate_hex(cls, v: str) -> str:
        return _validate_hex64(v, "fingerprint")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("value must contain non-space characters")
        return s

    @field_validator("reviewer_label")
    @classmethod
    def validate_reviewer(cls, v: str) -> str:
        return _validate_identifier(v, "reviewer_label")

    @field_validator("decision_timestamp")
    @classmethod
    def validate_ts(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("decision_timestamp must be timezone-aware")
        return v.astimezone(UTC)

    def canonical_payload(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        data["decision_timestamp"] = "<normalised>"
        data.pop("fingerprint", None)
        return data

    def computed_fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

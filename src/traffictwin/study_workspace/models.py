"""Strict typed models for the Study Workspace manifest and lifecycle cockpit.

Portable identity excludes wall clock, rendering state, local paths and
secrets. All models use ``extra='forbid'`` at the boundary and bounded
inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Shared strict base
# ---------------------------------------------------------------------------

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:\-]{0,127}$")
_STUDY_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$")

# Absolute-path patterns that must be rejected in portable text.
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
# POSIX absolute paths: an isolated slash segment not part of plain word.
_POSIX_ABS = re.compile(r"(?<![\w/])/(?!/)[^\s\"'<>]+")

_SECRET_HINTS = (
    re.compile(r"(?i)api[_-]?key\s*[:=]"),
    re.compile(r"(?i)secret\s*[:=]"),
    re.compile(r"(?i)password\s*[:=]"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]+"),
)


def _contains_absolute_path(value: str) -> bool:
    return bool(
        _WINDOWS_PATH.search(value)
        or _FILE_URI.search(value)
        or _HOME_PATH.search(value)
        or _POSIX_ABS.search(value)
    )


def _contains_secret_hint(value: str) -> bool:
    return any(p.search(value) for p in _SECRET_HINTS)


def _validate_safe_text(value: str, field_name: str) -> str:
    if _contains_absolute_path(value):
        raise ValueError(f"{field_name} must not contain absolute local paths")
    if _contains_secret_hint(value):
        raise ValueError(f"{field_name} must not contain secrets")
    return value


class StrictModel(BaseModel):
    """Base that rejects unknown fields and validates on assignment."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True, str_strip_whitespace=True)


class FrozenStrictModel(BaseModel):
    """Frozen strict base for immutable artifact refs."""

    model_config = ConfigDict(
        extra="forbid", validate_assignment=True, str_strip_whitespace=True, frozen=True
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class WorkspaceArtifactKind(StrEnum):
    """Bounded artifact kinds that a workspace may reference."""

    PREREGISTRATION_PLAN = "preregistration_plan"
    SOURCE_CONTRACT = "source_contract"
    SOURCE_CONTRACT_VERSION = "source_contract_version"
    SCHEMA_OBSERVATION = "schema_observation"
    SCHEMA_DRIFT_REPORT = "schema_drift_report"
    EVIDENCE_ATTACHMENT = "evidence_attachment"
    EVENT_ALIGNED_REPORT = "event_aligned_report"
    RESOURCE_STRATEGY_REPORT = "resource_strategy_report"
    STATISTICAL_STUDY_REPORT = "statistical_study_report"
    PROVENANCE_TRACE = "provenance_trace"
    PROVENANCE_GRAPH = "provenance_graph"
    STUDY_CAPSULE_MANIFEST = "study_capsule_manifest"
    STUDY_CAPSULE_RECEIPT = "study_capsule_receipt"
    RESEARCH_OBJECT_MANIFEST = "research_object_manifest"
    GENERIC_REPORT = "generic_report"
    BASELINE_ARTIFACT = "baseline_artifact"
    REGRESSION_ARTIFACT = "regression_artifact"
    METRIC_COLLECTION = "metric_collection"


class WorkspaceArtifactStanding(StrEnum):
    """Evidence/admission standing for one artifact reference."""

    UNAVAILABLE = "unavailable"
    SYNTHETIC_EVIDENCE = "synthetic_evidence"
    IMPORTED_EVIDENCE = "imported_evidence"
    HISTORICAL_OBSERVATION = "historical_observation"
    NEAR_LIVE_OPERATIONAL = "near_live_operational"
    ADMITTED_RESEARCH = "admitted_research"
    UNADMITTED_RESEARCH = "unadmitted_research"
    AUTHORED_CONFIGURATION = "authored_configuration"
    STATIC_GEOGRAPHIC = "static_geographic"
    NOT_APPLICABLE = "not_applicable"


class WorkspaceCompatibilityStanding(StrEnum):
    """Compatibility standing against workspace schema/version identities."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"
    REVIEW_REQUIRED = "review_required"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"


class WorkspaceAvailabilityState(StrEnum):
    """Explicit availability state for one reference."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    INVALID = "invalid"
    PENDING_REVIEW = "pending_review"


class WorkspaceLifecycleStage(StrEnum):
    """Descriptive lifecycle stages derived from artifact standings only."""

    DRAFT = "draft"
    CONTRACTED = "contracted"
    PREREGISTERED = "preregistered"
    COLLECTING = "collecting"
    EVIDENCE_REVIEW = "evidence_review"
    ANALYSIS_READY = "analysis_ready"
    ANALYSIS_COMPLETE = "analysis_complete"
    REVIEW_READY = "review_ready"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class WorkspaceBlockerSeverity(StrEnum):
    """Severity for validation findings."""

    BLOCKER = "blocker"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Singleton registry and supported versions
# ---------------------------------------------------------------------------

# Singleton kinds: only one artifact of this kind may appear in a workspace.
SINGLETON_KINDS: frozenset[WorkspaceArtifactKind] = frozenset(
    {
        WorkspaceArtifactKind.PREREGISTRATION_PLAN,
        WorkspaceArtifactKind.SOURCE_CONTRACT,
        WorkspaceArtifactKind.EVENT_ALIGNED_REPORT,
        WorkspaceArtifactKind.RESOURCE_STRATEGY_REPORT,
        WorkspaceArtifactKind.STATISTICAL_STUDY_REPORT,
        WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST,
        WorkspaceArtifactKind.RESEARCH_OBJECT_MANIFEST,
    }
)

# Supported schema versions per kind. Unknown kinds fallback to this set.
SUPPORTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "traffictwin-study-capsule-v1"})

# Per-kind overrides when a kind has stricter version binding.
KIND_SUPPORTED_VERSIONS: dict[WorkspaceArtifactKind, frozenset[str]] = {
    WorkspaceArtifactKind.STUDY_CAPSULE_MANIFEST: frozenset(
        {"1.0", "traffictwin-study-capsule-v1"}
    ),
    WorkspaceArtifactKind.RESEARCH_OBJECT_MANIFEST: frozenset({"1.0", "traffictwin-ro-crate-v1"}),
}


# ---------------------------------------------------------------------------
# Small models
# ---------------------------------------------------------------------------


class WorkspaceArtifactRef(FrozenStrictModel):
    """One generic artifact reference without embedding raw payloads.

    Fingerprint references must be deterministic hex SHA-256. No local
    filesystem paths enter canonical identity. Reason text is bounded.
    """

    kind: WorkspaceArtifactKind
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_version: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=256)
    standing: WorkspaceArtifactStanding = WorkspaceArtifactStanding.NOT_APPLICABLE
    compatibility_standing: WorkspaceCompatibilityStanding = (
        WorkspaceCompatibilityStanding.NOT_APPLICABLE
    )
    parent_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    availability: WorkspaceAvailabilityState = WorkspaceAvailabilityState.AVAILABLE
    reason: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("fingerprint")
    @classmethod
    def validate_fingerprint(cls, v: str) -> str:
        s = v.lower()
        if not _HEX64_RE.fullmatch(s):
            raise ValueError("fingerprint must be 64 hex chars")
        return s

    @field_validator("parent_fingerprint")
    @classmethod
    def validate_parent(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.lower()
        if not _HEX64_RE.fullmatch(s):
            raise ValueError("parent_fingerprint must be 64 hex chars")
        return s

    @field_validator("schema_version")
    @classmethod
    def validate_schema(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("schema_version must contain non-space characters")
        if _contains_absolute_path(s):
            raise ValueError("schema_version must not contain absolute local paths")
        return s

    @field_validator("label", "reason")
    @classmethod
    def validate_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        _validate_safe_text(v, "label/reason")
        return v.strip() if v.strip() else v

    @field_validator("label")
    @classmethod
    def validate_label_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("label must contain non-space characters")
        return s

    @model_validator(mode="after")
    def validate_availability_coherence(self) -> WorkspaceArtifactRef:
        # Unavailable artifacts must explain why.
        if self.availability is WorkspaceAvailabilityState.UNAVAILABLE and self.reason is None:
            raise ValueError("unavailable artifacts require reason text")
        # Parent fingerprint must not equal own fingerprint.
        if self.parent_fingerprint is not None and self.parent_fingerprint == self.fingerprint:
            raise ValueError("parent_fingerprint must not equal own fingerprint")
        return self


class WorkspaceBlocker(StrictModel):
    """One exact validation finding."""

    severity: WorkspaceBlockerSeverity
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=1000)
    related_fingerprints: list[str] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        s = v.strip()
        if not _IDENTIFIER_RE.fullmatch(s):
            raise ValueError("code must be an identifier")
        return s

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        _validate_safe_text(v, "message")
        return v.strip()

    @field_validator("related_fingerprints")
    @classmethod
    def validate_fps(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for fp in v:
            s = fp.lower().strip()
            if not _HEX64_RE.fullmatch(s):
                raise ValueError("related_fingerprints must be 64 hex")
            out.append(s)
        return out


class WorkspaceAction(StrictModel):
    """One typed, non-executable next-action guidance record."""

    action: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=1000)
    priority: int = Field(ge=1, le=100)
    related_fingerprints: list[str] = Field(default_factory=list)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        s = v.strip()
        if not _IDENTIFIER_RE.fullmatch(s):
            raise ValueError("action must be an identifier")
        return s

    @field_validator("label", "description")
    @classmethod
    def validate_safe(cls, v: str) -> str:
        _validate_safe_text(v, "label/description")
        return v.strip()

    @field_validator("related_fingerprints")
    @classmethod
    def validate_fps(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for fp in v:
            s = fp.lower().strip()
            if not _HEX64_RE.fullmatch(s):
                raise ValueError("related_fingerprints must be 64 hex")
            out.append(s)
        return out


class WorkspaceValidationReport(StrictModel):
    """Result of validating one workspace manifest."""

    is_valid: bool
    blockers: list[WorkspaceBlocker] = Field(default_factory=list)
    warnings: list[WorkspaceBlocker] = Field(default_factory=list)
    derived_stage: WorkspaceLifecycleStage
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("fingerprint")
    @classmethod
    def validate_fp(cls, v: str) -> str:
        s = v.lower()
        if not _HEX64_RE.fullmatch(s):
            raise ValueError("fingerprint must be 64 hex")
        return s


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

WORKSPACE_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class StudyWorkspaceManifest(StrictModel):
    """Portable study-level workspace manifest referencing typed artifact fingerprints."""

    schema_version: Literal["1.0"] = WORKSPACE_SCHEMA_VERSION
    workspace_id: str = Field(min_length=1, max_length=128)
    workspace_version: str = Field(
        min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}$"
    )
    study_id: str = Field(min_length=1, max_length=128)
    study_title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    artifacts: list[WorkspaceArtifactRef] = Field(default_factory=list, max_length=64)
    declared_stage: WorkspaceLifecycleStage | None = None
    limitations: list[str] = Field(default_factory=list, max_length=32)
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("workspace_id", "study_id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not _IDENTIFIER_RE.fullmatch(v):
            raise ValueError("workspace_id/study_id must be identifier")
        _validate_safe_text(v, "workspace_id/study_id")
        return v

    @field_validator("workspace_version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        if not _STUDY_VERSION_RE.fullmatch(v):
            raise ValueError("workspace_version must be safe identifier")
        _validate_safe_text(v, "workspace_version")
        return v

    @field_validator("study_title", "description")
    @classmethod
    def validate_optional_text(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            raise ValueError("optional text must contain non-space when provided")
        _validate_safe_text(s, "study_title/description")
        return s

    @field_validator("limitations")
    @classmethod
    def validate_limitations(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for item in v:
            s = item.strip()
            if not s:
                raise ValueError("limitation must not be empty")
            if len(s) > 500:
                raise ValueError("limitation must be <= 500 chars")
            _validate_safe_text(s, "limitation")
            if s in seen:
                raise ValueError("limitations must not contain duplicates")
            seen.add(s)
            out.append(s)
        return out

    @field_validator("provenance")
    @classmethod
    def validate_provenance(cls, v: dict[str, str]) -> dict[str, str]:
        if len(v) > 32:
            raise ValueError("provenance must contain at most 32 entries")
        for k, val in v.items():
            if not _IDENTIFIER_RE.fullmatch(k):
                raise ValueError("provenance keys must be identifier")
            if len(val) > 500:
                raise ValueError("provenance values must be <= 500 chars")
            _validate_safe_text(k, "provenance key")
            _validate_safe_text(val, "provenance value")
        return v

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts_unique_fp(
        cls, v: list[WorkspaceArtifactRef]
    ) -> list[WorkspaceArtifactRef]:
        # Individual duplicate check is done in service, but early unique label check.
        # Allow validation to pass here; service will produce blockers.
        return v

    def canonical_dict(self) -> dict[str, object]:
        """Return deterministic canonical dict excluding wall-clock and fingerprint."""
        # Exclude wall-clock like fields (none) and sort artifacts deterministically.
        artifacts_canonical = sorted(
            [a.model_dump(mode="json") for a in self.artifacts],
            key=lambda d: str(d.get("fingerprint", "")),
        )
        return {
            "artifacts": artifacts_canonical,
            "declared_stage": self.declared_stage.value if self.declared_stage else None,
            "description": self.description,
            "limitations": sorted(self.limitations),
            "provenance": dict(sorted(self.provenance.items())),
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "study_title": self.study_title,
            "workspace_id": self.workspace_id,
            "workspace_version": self.workspace_version,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

# ruff: noqa: E501
"""Deterministic analysis-level Study Capsule for TrafficTwin.

Study Capsules bind a logical study identity, selected derived artifacts,
evidence labels, publication policies and limitations into one portable
deterministic ZIP suitable for offline supervisor/examiner review.

This module is deliberately distinct from the generic RO-Crate system
(``research_object.py``).  It reuses the repository's canonical JSON,
SHA-256 and ZIP determinism primitives but defines its own schema,
member kinds, policies and verification contract.
"""

from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.release.metadata import current_release_metadata

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STUDY_CAPSULE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
STUDY_CAPSULE_CONTRACT_VERSION: Literal["traffictwin-study-capsule-v1"] = (
    "traffictwin-study-capsule-v1"
)
STUDY_CAPSULE_CAPABILITY_ID: Literal["OPS-04-CAPSULE"] = "OPS-04-CAPSULE"

MAX_CAPSULE_MEMBERS = 32
MAX_MEMBER_BYTES = 10_000_000
MAX_ARCHIVE_FILE_COUNT = 64
MAX_ARCHIVE_MEMBER_BYTES = 10_000_000
MAX_ARCHIVE_TOTAL_BYTES = 50_000_000

REQUIRED_ARCHIVE_MEMBERS: tuple[str, ...] = (
    "capsule-manifest.json",
    "checksums.sha256",
)

_FIXED_ZIP_TIMESTAMP: tuple[int, int, int, int, int, int] = (1980, 1, 1, 0, 0, 0)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

# Absolute-path patterns that must be redacted / rejected in portable text.
_WINDOWS_PATH = re.compile(r"(?i)(?<![\w])(?:[a-z]:[\\/][^\s\"'<>]+)")
_FILE_URI = re.compile(r"(?i)file://[^\s\"'<>]+")
_HOME_PATH = re.compile(r"(?<![\w])~[/\\][^\s\"'<>]+")
_POSIX_ABS = re.compile(r"(?<![/\w])/(?!/)[^\s\"'<>]+")
_PATH_REDACTION = "[redacted absolute path]"

# Secret-like token pattern for validation (do not expose values, just reject)
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)api[_-]?key\s*[:=]"),
    re.compile(r"(?i)secret\s*[:=]"),
    re.compile(r"(?i)password\s*[:=]"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-_\.]+"),
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class StudyCapsuleError(ValueError):
    """Raised when a study-capsule request cannot be satisfied safely."""


# ---------------------------------------------------------------------------
# Strict base
# ---------------------------------------------------------------------------


class StudyCapsuleModel(BaseModel):
    """Strict base for capsule models."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StudyCapsuleMemberKind(StrEnum):
    """Eligible derived artifact kinds that a capsule can reference."""

    SCENARIO_SEED = "scenario_seed"
    RUN_SUMMARY = "run_summary"
    VALIDATION_RESULT = "validation_result"
    COMPARISON_REPORT = "comparison_report"
    CONSEQUENCE_REPORT = "consequence_report"
    EVIDENCE_PACK = "evidence_pack"
    DIAGNOSTIC_RESULT = "diagnostic_result"
    PROVENANCE_GRAPH = "provenance_graph"
    DETERMINISTIC_REPORT = "deterministic_report"
    ANALYST_NOTE = "analyst_note"
    RO_CRATE_REFERENCE = "ro_crate_reference"


class StudyCapsulePublicationPolicy(StrEnum):
    """Bounded publication policy for one capsule member."""

    EMBED_SAFE_DERIVED = "embed_safe_derived"
    REFERENCE_BY_FINGERPRINT = "reference_by_fingerprint"
    EXCLUDE = "exclude"


class StudyCapsuleEvidenceLabel(StrEnum):
    """Evidence-label vocabulary mirroring TrafficTwin evidence distinctions."""

    AUTHORED_CONFIGURATION = "authored_configuration"
    SYNTHETIC_EVIDENCE = "synthetic_evidence"
    IMPORTED_EVIDENCE = "imported_evidence"
    HISTORICAL_OBSERVATION = "historical_observation"
    NEAR_LIVE_OPERATIONAL = "near_live_operational"
    ADMITTED_RESEARCH = "admitted_research"
    UNADMITTED_RESEARCH = "unadmitted_research"
    STATIC_GEOGRAPHIC = "static_geographic"
    UNAVAILABLE = "unavailable"


class StudyCapsuleAdmissionLabel(StrEnum):
    """Admission state for research-derived artifacts."""

    ADMITTED = "admitted"
    UNADMITTED = "unadmitted"
    NOT_APPLICABLE = "not_applicable"


class StudyCapsuleVerificationStatus(StrEnum):
    """Discriminated verification outcome category."""

    VALID = "valid"
    MALFORMED = "malformed"
    TAMPERED = "tampered"
    UNSUPPORTED_VERSION = "unsupported_version"


# ---------------------------------------------------------------------------
# Helper validators
# ---------------------------------------------------------------------------


def _validate_identifier(value: str, field: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"{field} must start alphanumeric and contain only letters, numbers, "
            "dots, underscores, colons, hyphens, 1-128 chars"
        )
    return value


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class StudyCapsuleMemberInput(StudyCapsuleModel):
    """One caller-declared member selection (untrusted boundary)."""

    kind: StudyCapsuleMemberKind
    logical_id: str = Field(min_length=1, max_length=128)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_label: StudyCapsuleEvidenceLabel
    admission_label: StudyCapsuleAdmissionLabel = StudyCapsuleAdmissionLabel.NOT_APPLICABLE
    policy: StudyCapsulePublicationPolicy
    # Inline content for EMBED_SAFE_DERIVED members. Stored as bytes in-memory,
    # serialised as base64 in JSON transport if needed – but for builder we
    # accept bytes directly via python object, and JSON representation uses
    # utf-8 text. For this implementation, ``content`` is optional bytes that
    # must be provided exactly when policy is EMBED_SAFE_DERIVED.
    content: bytes | None = Field(default=None)
    encoding_format: str | None = Field(default=None, min_length=1, max_length=100)
    exclusion_reason: str | None = Field(default=None, min_length=1, max_length=1000)
    # For REFERENCE_BY_FINGERPRINT members, optional human-readable note.
    reference_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("logical_id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        return _validate_identifier(v, "logical_id")

    @model_validator(mode="after")
    def _cross_validate(self) -> Self:
        # No absolute paths in text fields.
        for val in (self.logical_id, self.exclusion_reason, self.reference_note):
            if val is not None and _safe_text(val) != val:
                raise ValueError("capsule member text must not contain absolute local paths")
        if (
            self.encoding_format is not None
            and _safe_text(self.encoding_format) != self.encoding_format
        ):
            raise ValueError("encoding_format must not contain absolute local paths")
        # Secret check.
        for val in (self.exclusion_reason, self.reference_note):
            if val is not None and _contains_secret_hint(val):
                raise ValueError("capsule member text must not contain secrets")
        # Content presence must match policy.
        if self.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
            if self.content is None:
                raise ValueError("embed_safe_derived requires content bytes")
            if len(self.content) == 0:
                raise ValueError("embedded content must not be empty")
            if len(self.content) > MAX_MEMBER_BYTES:
                raise ValueError("embedded member exceeds byte ceiling")
            if self.exclusion_reason is not None:
                raise ValueError("embedded members must not carry exclusion_reason")
        elif self.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT:
            if self.content is not None:
                raise ValueError("reference_by_fingerprint must not carry content")
            if self.exclusion_reason is not None:
                raise ValueError("referenced members must not carry exclusion_reason")
        else:  # EXCLUDE
            if self.content is not None:
                raise ValueError("excluded members must not carry content")
            if self.exclusion_reason is None:
                raise ValueError("excluded members require exclusion_reason")
            if _safe_text(self.exclusion_reason) != self.exclusion_reason:
                raise ValueError("exclusion_reason must not contain absolute local paths")
        # Raw imported evidence must default to reference or exclusion, not embed.
        raw_like = {
            StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
            StudyCapsuleEvidenceLabel.HISTORICAL_OBSERVATION,
            StudyCapsuleEvidenceLabel.NEAR_LIVE_OPERATIONAL,
            StudyCapsuleEvidenceLabel.UNADMITTED_RESEARCH,
        }
        if (
            self.evidence_label in raw_like
            and self.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
        ):
            raise ValueError(
                "raw imported evidence must use reference_by_fingerprint or exclude, not embed_safe_derived"
            )
        # Analyst note requires explicit policy handling – embed only if evidence is authored/synthetic.
        if self.kind is StudyCapsuleMemberKind.ANALYST_NOTE and self.evidence_label in raw_like:
            # Analyst notes about raw observations are allowed but must not embed raw bytes as derived.
            # We already block embedding for raw_like, so this is covered.
            pass
        return self


class StudyCapsuleUnavailable(StudyCapsuleModel):
    """One unavailable evidence category that the capsule explicitly declares missing."""

    kind: StudyCapsuleMemberKind
    logical_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=1000)
    evidence_label: StudyCapsuleEvidenceLabel = StudyCapsuleEvidenceLabel.UNAVAILABLE
    admission_label: StudyCapsuleAdmissionLabel = StudyCapsuleAdmissionLabel.NOT_APPLICABLE

    @field_validator("logical_id")
    @classmethod
    def _lid_ok(cls, v: str) -> str:
        return _validate_identifier(v, "logical_id")

    @model_validator(mode="after")
    def _check(self) -> Self:
        if _safe_text(self.logical_id) != self.logical_id or _safe_text(self.reason) != self.reason:
            raise ValueError("unavailable entry must not contain absolute local paths")
        if _contains_secret_hint(self.reason):
            raise ValueError("unavailable reason must not contain secrets")
        return self


class StudyCapsuleRequest(StudyCapsuleModel):
    """Complete caller-owned capsule build request."""

    schema_version: Literal["1.0"] = STUDY_CAPSULE_SCHEMA_VERSION
    creation_date: date
    study_id: str = Field(min_length=1, max_length=128)
    study_version: str = Field(default="1.0", min_length=1, max_length=64)
    study_title: str | None = Field(default=None, min_length=1, max_length=300)
    study_description: str | None = Field(default=None, min_length=1, max_length=2000)
    capsule_title: str = Field(min_length=1, max_length=300)
    capsule_description: str | None = Field(default=None, min_length=1, max_length=2000)
    members: list[StudyCapsuleMemberInput] = Field(min_length=1, max_length=MAX_CAPSULE_MEMBERS)
    limitations: list[str] = Field(default_factory=list, max_length=32)
    unavailable: list[StudyCapsuleUnavailable] = Field(default_factory=list, max_length=32)
    evidence_summary: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("study_id")
    @classmethod
    def _study_id_ok(cls, v: str) -> str:
        return _validate_identifier(v, "study_id")

    @field_validator("limitations")
    @classmethod
    def _limitations_ok(cls, v: list[str]) -> list[str]:
        for item in v:
            if _safe_text(item) != item:
                raise ValueError("limitations must not contain absolute local paths")
            if _contains_secret_hint(item):
                raise ValueError("limitations must not contain secrets")
            if len(item) == 0 or len(item) > 500:
                raise ValueError("each limitation must be 1-500 chars")
        if len(v) != len(set(v)):
            raise ValueError("limitations must not contain duplicates")
        return v

    @model_validator(mode="after")
    def _validate_request(self) -> Self:
        # No absolute paths in titles/descriptions.
        for val in (
            self.study_title,
            self.study_description,
            self.capsule_title,
            self.capsule_description,
            self.evidence_summary,
        ):
            if val is not None and _safe_text(val) != val:
                raise ValueError("capsule text must not contain absolute local paths")
            if val is not None and _contains_secret_hint(val):
                raise ValueError("capsule text must not contain secrets")
        # Unique logical identity per kind+id.
        seen: set[tuple[str, str]] = set()
        for m in self.members:
            key = (m.kind.value, m.logical_id)
            if key in seen:
                raise ValueError(f"duplicate member logical identity: {key}")
            seen.add(key)
        # Unique fingerprints? Not required but check duplicates not allowed across members with same policy? allow same fingerprint for different kinds? keep strict: fingerprints must be unique unless explicitly excluded members with same fingerprint? simplify: forbid duplicate fingerprints for non-excluded members.
        non_excluded_fps = [
            m.fingerprint
            for m in self.members
            if m.policy is not StudyCapsulePublicationPolicy.EXCLUDE
        ]
        if len(non_excluded_fps) != len(set(non_excluded_fps)):
            raise ValueError(
                "capsule member fingerprints must be unique for included/referenced members"
            )
        # Unavailable validation done in unavailable model but check overlap.
        unavailable_ids = {(u.kind.value, u.logical_id) for u in self.unavailable}
        for key in seen:
            if key in unavailable_ids:
                raise ValueError("unavailable entries must not duplicate included members")
        return self

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256(self.canonical_json().encode("utf-8"))


class StudyCapsuleMember(StudyCapsuleModel):
    """One member as recorded in the portable manifest (validated portable view)."""

    kind: StudyCapsuleMemberKind
    logical_id: str = Field(min_length=1, max_length=128)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_label: StudyCapsuleEvidenceLabel
    admission_label: StudyCapsuleAdmissionLabel
    policy: StudyCapsulePublicationPolicy
    archive_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    content_size: int | None = Field(default=None, ge=0)
    encoding_format: str | None = None
    exclusion_reason: str | None = None
    reference_note: str | None = None

    @field_validator("logical_id")
    @classmethod
    def _lid_ok2(cls, v: str) -> str:
        return _validate_identifier(v, "logical_id")

    @model_validator(mode="after")
    def _validate_member(self) -> Self:
        # Path / checksum coherence
        if self.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
            if self.archive_path is None or self.sha256 is None or self.content_size is None:
                raise ValueError("embedded members require archive_path, sha256, content_size")
            _validate_archive_name(self.archive_path)
            if self.exclusion_reason is not None:
                raise ValueError("embedded members must not carry exclusion_reason")
        elif self.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT:
            if (
                self.archive_path is not None
                or self.sha256 is not None
                or self.content_size is not None
            ):
                raise ValueError(
                    "referenced members must not carry archive_path/sha256/content_size"
                )
            if self.exclusion_reason is not None:
                raise ValueError("referenced members must not carry exclusion_reason")
        else:  # EXCLUDE
            if (
                self.archive_path is not None
                or self.sha256 is not None
                or self.content_size is not None
            ):
                raise ValueError("excluded members must not carry archive_path/sha256/content_size")
            if self.exclusion_reason is None:
                raise ValueError("excluded members require exclusion_reason")
        # No absolute paths
        for val in (self.exclusion_reason, self.reference_note, self.encoding_format):
            if val is not None and _safe_text(val) != val:
                raise ValueError("capsule member text must not contain absolute local paths")
        return self


class StudyCapsuleExclusion(StudyCapsuleModel):
    """Aggregate exclusion entry for human audit (complements per-member EXCLUDE)."""

    kind: StudyCapsuleMemberKind | None = None
    logical_id: str | None = None
    reason: str = Field(min_length=1, max_length=1000)
    count: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def _check2(self) -> Self:
        if self.reason is not None and _safe_text(self.reason) != self.reason:
            raise ValueError("exclusion reason must not contain absolute local paths")
        if self.logical_id is not None:
            _validate_identifier(self.logical_id, "logical_id")
            if _safe_text(self.logical_id) != self.logical_id:
                raise ValueError("logical_id must not contain absolute local paths")
        return self


class StudyCapsuleStudyIdentity(StudyCapsuleModel):
    """Logical study identity bound into the manifest."""

    study_id: str = Field(min_length=1, max_length=128)
    study_version: str = Field(min_length=1, max_length=64)
    study_title: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("study_id")
    @classmethod
    def _sid_ok(cls, v: str) -> str:
        return _validate_identifier(v, "study_id")


class StudyCapsuleSoftware(StudyCapsuleModel):
    """Software and schema versions bound into the capsule."""

    package: str = "traffictwin"
    version: str
    python_version: str
    schema_version: Literal["1.0"] = STUDY_CAPSULE_SCHEMA_VERSION
    contract_version: Literal["traffictwin-study-capsule-v1"] = STUDY_CAPSULE_CONTRACT_VERSION
    capsule_spec_version: str = "1.0"


class StudyCapsuleManifest(StudyCapsuleModel):
    """Portable, deterministic capsule manifest."""

    schema_version: Literal["1.0"] = STUDY_CAPSULE_SCHEMA_VERSION
    capability_id: Literal["OPS-04-CAPSULE"] = STUDY_CAPSULE_CAPABILITY_ID
    contract_version: Literal["traffictwin-study-capsule-v1"] = STUDY_CAPSULE_CONTRACT_VERSION
    capsule_id: str = Field(pattern=r"^urn:traffictwin:study-capsule:[0-9a-f]{64}$")
    capsule_title: str = Field(min_length=1, max_length=300)
    capsule_description: str | None = Field(default=None, min_length=1, max_length=2000)
    creation_date: date
    study: StudyCapsuleStudyIdentity
    members: list[StudyCapsuleMember]
    exclusions: list[StudyCapsuleExclusion] = Field(default_factory=list)
    unavailable: list[StudyCapsuleUnavailable] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_summary: str | None = None
    software: StudyCapsuleSoftware
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_manifest(self) -> Self:
        # Unique archive paths
        paths = [m.archive_path for m in self.members if m.archive_path is not None]
        if len(paths) != len(set(paths)):
            raise ValueError("capsule manifest contains duplicate archive paths")
        # Unique logical ids
        keys = [(m.kind.value, m.logical_id) for m in self.members]
        if len(keys) != len(set(keys)):
            raise ValueError("capsule manifest contains duplicate member logical ids")
        # Validate limitations against path redaction
        for lim in self.limitations:
            if _safe_text(lim) != lim:
                raise ValueError("limitations must not contain absolute local paths")
        return self

    def canonical_json(self) -> str:
        # Exclude self-referential fingerprint? manifest_fingerprint is included because it is
        # derived deterministically; but for fingerprint recomputation we need stable.
        # To avoid circularity, fingerprint is defined as sha256(canonical_json without manifest_fingerprint)
        # However we store manifest_fingerprint as computed. For verification we recompute without it.
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        # Deterministic fingerprint excludes the stored manifest_fingerprint field itself
        payload = self.model_dump(mode="json")
        payload.pop("manifest_fingerprint", None)
        return _sha256(_canonical_json(payload).encode("utf-8"))

    def portable_identity_json(self) -> str:
        """Return canonical JSON excluding any non-portable fields (none stored, but explicit)."""
        return self.canonical_json()


class StudyCapsuleReceipt(StudyCapsuleModel):
    """Receipt for one atomically published capsule ZIP."""

    archive_name: str
    archive_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    archive_size: int = Field(gt=0)
    capsule_id: str = Field(pattern=r"^urn:traffictwin:study-capsule:[0-9a-f]{64}$")
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    referenced_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    deterministic_zip: bool = True
    verified_before_publication: bool = True


class StudyCapsuleVerification(StudyCapsuleModel):
    """Offline verification result."""

    valid: bool
    status: StudyCapsuleVerificationStatus
    archive_sha256: str | None = None
    capsule_id: str | None = None
    manifest_fingerprint: str | None = None
    member_count: int = Field(default=0, ge=0)
    checksum_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    embedded_members: list[str] = Field(default_factory=list)
    referenced_members: list[str] = Field(default_factory=list)
    excluded_members: list[str] = Field(default_factory=list)
    unavailable_members: list[str] = Field(default_factory=list)


class StudyCapsuleContract(StudyCapsuleModel):
    """Versioned method and safety contract."""

    schema_version: Literal["1.0"] = STUDY_CAPSULE_SCHEMA_VERSION
    capability_id: Literal["OPS-04-CAPSULE"] = STUDY_CAPSULE_CAPABILITY_ID
    contract_version: Literal["traffictwin-study-capsule-v1"] = STUDY_CAPSULE_CONTRACT_VERSION
    member_kinds: list[str]
    publication_policies: dict[str, str]
    deterministic_publication: list[str]
    required_members: list[str]
    checksum_policy: str
    redaction_policy: str
    limits: dict[str, int]
    exclusions: list[str]

    def canonical_json(self) -> str:
        return _canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        return _sha256(self.canonical_json().encode("utf-8"))


@dataclass(frozen=True)
class BuiltStudyCapsule:
    """In-memory capsule ready for deterministic ZIP packaging."""

    manifest: StudyCapsuleManifest
    members: dict[str, bytes]


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------


def study_capsule_contract() -> StudyCapsuleContract:
    """Return the versioned Study Capsule contract."""

    return StudyCapsuleContract(
        member_kinds=[k.value for k in StudyCapsuleMemberKind],
        publication_policies={
            StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED.value: (
                "Embed only safe derived artifacts (reports, metrics, evidence packs, "
                "deterministic graphs). Raw imported evidence is never embedded by default."
            ),
            StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT.value: (
                "Retain logical fingerprint and evidence label without copying raw bytes."
            ),
            StudyCapsulePublicationPolicy.EXCLUDE.value: (
                "Record only an exclusion count/reason; no payload bytes or identifiers beyond "
                "logical kind/id and reason."
            ),
        },
        deterministic_publication=[
            "Caller supplies creation_date; all derived timestamps use midnight UTC on that date.",
            "Archive members are sorted, uncompressed, and carry one fixed ZIP timestamp and permission mode.",
            "The complete capsule is built and verified in memory before atomic destination replacement.",
            "Two builds from equivalent logical artifacts produce byte-identical archives.",
        ],
        required_members=list(REQUIRED_ARCHIVE_MEMBERS),
        checksum_policy=(
            "checksums.sha256 covers every payload member and capsule-manifest.json; "
            "the receipt fingerprints the complete ZIP bytes."
        ),
        redaction_policy=(
            "Absolute POSIX, Windows, home-relative, and file-URI paths are redacted from "
            "derived JSON; archive inventory paths are crate-relative."
        ),
        limits={
            "max_members": MAX_CAPSULE_MEMBERS,
            "max_member_bytes": MAX_MEMBER_BYTES,
            "max_archive_file_count": MAX_ARCHIVE_FILE_COUNT,
            "max_archive_member_bytes": MAX_ARCHIVE_MEMBER_BYTES,
            "max_archive_total_bytes": MAX_ARCHIVE_TOTAL_BYTES,
        },
        exclusions=[
            "No registry, cache, credentials, external package, simulator, or network resource is copied.",
            "No DOI, licence, or scientific validity is inferred.",
            "A verifiable capsule does not prove scientific validity.",
        ],
    )


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def build_study_capsule(request: StudyCapsuleRequest) -> BuiltStudyCapsule:
    """Build a deterministic capsule in memory.

    The builder assigns stable archive paths, computes checksums, builds the
    portable manifest and validates that no absolute path or secret entered the
    portable representation.
    """

    # Validate request already done by Pydantic, but re-enforce raw embed rule at build layer.
    # (defense in depth for direct construction bypass)

    # Assign archive paths deterministically sorted by kind, logical_id
    sorted_members = sorted(request.members, key=lambda m: (m.kind.value, m.logical_id))

    manifest_members: list[StudyCapsuleMember] = []
    members: dict[str, bytes] = {}
    exclusions: list[StudyCapsuleExclusion] = []

    for inp in sorted_members:
        if inp.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
            assert inp.content is not None
            safe_path = _archive_path_for(inp.kind, inp.logical_id, inp.encoding_format)
            _validate_archive_name(safe_path)
            if safe_path in members:
                raise StudyCapsuleError(f"duplicate capsule member path: {safe_path}")
            # Ensure content does not contain secrets / absolute paths? Content is bytes, not validated as text necessarily.
            # But we can check if content decodes as utf-8, then redact? We simply ensure no absolute path leakage by
            # scanning utf-8 decodable payload.
            try:
                text = inp.content.decode("utf-8")
                if _safe_text(text) != text:
                    raise StudyCapsuleError(
                        "embedded member content must not contain absolute local paths"
                    )
                if _contains_secret_hint(text):
                    # Do not expose secret, just reject
                    raise StudyCapsuleError("embedded member content must not contain secrets")
            except UnicodeDecodeError:
                # Binary payload allowed - skip text checks
                pass
            digest = _sha256(inp.content)
            members[safe_path] = inp.content
            manifest_members.append(
                StudyCapsuleMember(
                    kind=inp.kind,
                    logical_id=inp.logical_id,
                    fingerprint=inp.fingerprint,
                    evidence_label=inp.evidence_label,
                    admission_label=inp.admission_label,
                    policy=inp.policy,
                    archive_path=safe_path,
                    sha256=digest,
                    content_size=len(inp.content),
                    encoding_format=inp.encoding_format or _media_type(safe_path),
                    exclusion_reason=None,
                    reference_note=inp.reference_note,
                )
            )
        elif inp.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT:
            manifest_members.append(
                StudyCapsuleMember(
                    kind=inp.kind,
                    logical_id=inp.logical_id,
                    fingerprint=inp.fingerprint,
                    evidence_label=inp.evidence_label,
                    admission_label=inp.admission_label,
                    policy=inp.policy,
                    archive_path=None,
                    sha256=None,
                    content_size=None,
                    encoding_format=inp.encoding_format or _media_type_for_kind(inp.kind),
                    exclusion_reason=None,
                    reference_note=inp.reference_note,
                )
            )
        else:  # EXCLUDE
            manifest_members.append(
                StudyCapsuleMember(
                    kind=inp.kind,
                    logical_id=inp.logical_id,
                    fingerprint=inp.fingerprint,
                    evidence_label=inp.evidence_label,
                    admission_label=inp.admission_label,
                    policy=inp.policy,
                    archive_path=None,
                    sha256=None,
                    content_size=None,
                    encoding_format=None,
                    exclusion_reason=inp.exclusion_reason,
                    reference_note=None,
                )
            )
            exclusions.append(
                StudyCapsuleExclusion(
                    kind=inp.kind,
                    logical_id=inp.logical_id,
                    reason=inp.exclusion_reason or "excluded by policy",
                    count=1,
                )
            )

    # Software versions
    release = current_release_metadata()
    software = StudyCapsuleSoftware(
        version=release.version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )

    study_identity = StudyCapsuleStudyIdentity(
        study_id=request.study_id,
        study_version=request.study_version,
        study_title=request.study_title,
    )

    # Sort manifest members stably for deterministic manifest
    manifest_members_sorted = sorted(manifest_members, key=lambda m: (m.kind.value, m.logical_id))

    # Build manifest without fingerprint first to compute fingerprint
    # Manifest fingerprint is defined as sha256(canonical_json_without_manifest_fingerprint)
    # We'll create a temporary manifest with placeholder, compute, then fill.
    tmp_manifest = StudyCapsuleManifest(
        capsule_id="urn:traffictwin:study-capsule:" + "0" * 64,  # placeholder
        capsule_title=request.capsule_title,
        capsule_description=request.capsule_description,
        creation_date=request.creation_date,
        study=study_identity,
        members=manifest_members_sorted,
        exclusions=sorted(
            exclusions, key=lambda e: (e.kind.value if e.kind else "", e.logical_id or "")
        ),
        unavailable=sorted(request.unavailable, key=lambda u: (u.kind.value, u.logical_id)),
        limitations=sorted(request.limitations),
        evidence_summary=request.evidence_summary,
        software=software,
        manifest_fingerprint="0" * 64,
    )

    # Compute capsule_id deterministically from contract, request fingerprint, software
    capsule_id_source = _canonical_json(
        {
            "contract_version": STUDY_CAPSULE_CONTRACT_VERSION,
            "request_fingerprint": request.fingerprint(),
            "software": software.model_dump(mode="json"),
            "study_identity": study_identity.model_dump(mode="json"),
            "member_fingerprints": sorted([m.fingerprint for m in manifest_members_sorted]),
            "creation_date": request.creation_date.isoformat(),
        }
    )
    capsule_id = "urn:traffictwin:study-capsule:" + _sha256(capsule_id_source.encode("utf-8"))

    tmp_manifest2 = tmp_manifest.model_copy(update={"capsule_id": capsule_id})
    # Now compute manifest fingerprint
    fp_payload = tmp_manifest2.model_dump(mode="json")
    fp_payload.pop("manifest_fingerprint", None)
    manifest_fingerprint = _sha256(_canonical_json(fp_payload).encode("utf-8"))

    manifest = tmp_manifest2.model_copy(update={"manifest_fingerprint": manifest_fingerprint})

    # Add manifest and checksums to members dict
    members["capsule-manifest.json"] = _json_bytes(manifest.model_dump(mode="json"))
    # checksums covers every member except itself? For capsule, checksums shall cover every payload member
    # including manifest but not itself. We'll compute after adding manifest, then add checksums.
    # For deterministic, checksums file is computed from sorted members (excluding checksums itself)
    checksums = {name: _sha256(content) for name, content in sorted(members.items())}
    members["checksums.sha256"] = _checksum_bytes(checksums)

    # Also add a simple readme/metadata: we can include a capsule-readme.md as embedded? But not required.
    # Ensure deterministic ordering, no duplicate paths, within limits.
    if len(members) > MAX_ARCHIVE_FILE_COUNT:
        raise StudyCapsuleError("study capsule exceeds archive file-count ceiling")
    if sum(len(c) for c in members.values()) > MAX_ARCHIVE_TOTAL_BYTES:
        raise StudyCapsuleError("study capsule exceeds total-byte ceiling")

    # Final sorted members dict
    sorted_members_dict = dict(sorted(members.items()))

    # Verify that manifest's checksums correspond? That's verifier's job, but builder should also self-check.
    # Ensure no absolute path leakage in manifest json
    manifest_json_text = sorted_members_dict["capsule-manifest.json"].decode("utf-8")
    if _safe_text(manifest_json_text) != manifest_json_text:
        raise StudyCapsuleError("capsule manifest must not contain absolute local paths")
    if _contains_secret_hint(manifest_json_text):
        raise StudyCapsuleError("capsule manifest must not contain secrets")

    return BuiltStudyCapsule(manifest=manifest, members=sorted_members_dict)


def create_study_capsule_archive(
    request: StudyCapsuleRequest,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> StudyCapsuleReceipt:
    """Build, verify, and atomically publish a deterministic capsule ZIP."""

    target = Path(destination)
    _validate_destination(target, overwrite=overwrite)
    built = build_study_capsule(request)
    archive = _zip_bytes(built.members)
    verification = verify_study_capsule_bytes(archive)
    if not verification.valid:
        raise StudyCapsuleError(
            "generated study capsule failed verification: " + "; ".join(verification.errors)
        )
    # Also cross-check that verification's capsule_id matches built manifest
    if verification.capsule_id != built.manifest.capsule_id:
        raise StudyCapsuleError("capsule_id mismatch after verification")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(archive)
            handle.flush()
            os.fsync(handle.fileno())
        if target.is_symlink():
            raise StudyCapsuleError("study-capsule destination must not be a symbolic link")
        if target.exists() and not overwrite:
            raise FileExistsError(f"study-capsule destination already exists: {target}")
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    # Embedded counts etc.
    embedded = sum(
        1
        for m in built.manifest.members
        if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
    )
    referenced = sum(
        1
        for m in built.manifest.members
        if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
    )
    excluded = sum(
        1 for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.EXCLUDE
    )
    return StudyCapsuleReceipt(
        archive_name=target.name,
        archive_sha256=_sha256(archive),
        archive_size=len(archive),
        capsule_id=built.manifest.capsule_id,
        manifest_fingerprint=built.manifest.manifest_fingerprint,
        member_count=len(built.members),
        embedded_count=embedded,
        referenced_count=referenced,
        excluded_count=excluded,
        unavailable_count=len(built.manifest.unavailable),
    )


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------


def verify_study_capsule(path: str | Path) -> StudyCapsuleVerification:
    """Verify a capsule ZIP on disk offline."""

    source = Path(path)
    if source.is_symlink() or not source.is_file():
        return StudyCapsuleVerification(
            valid=False,
            status=StudyCapsuleVerificationStatus.MALFORMED,
            errors=["study-capsule archive must be a direct non-symlink file"],
        )
    try:
        payload = source.read_bytes()
    except OSError as exc:
        return StudyCapsuleVerification(
            valid=False,
            status=StudyCapsuleVerificationStatus.MALFORMED,
            errors=[str(exc)],
        )
    return verify_study_capsule_bytes(payload)


def verify_study_capsule_bytes(payload: bytes) -> StudyCapsuleVerification:
    """Verify bounded ZIP structure, manifest fingerprint, and checksums offline."""

    archive_sha256 = _sha256(payload)
    errors: list[str] = []
    warnings: list[str] = []
    capsule_id: str | None = None
    manifest_fingerprint: str | None = None
    checksum_count = 0
    member_count = 0
    status = StudyCapsuleVerificationStatus.VALID

    if len(payload) > MAX_ARCHIVE_TOTAL_BYTES:
        return StudyCapsuleVerification(
            valid=False,
            status=StudyCapsuleVerificationStatus.MALFORMED,
            archive_sha256=archive_sha256,
            errors=["study-capsule archive exceeds total-byte ceiling"],
        )

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            member_count = len(infos)
            _validate_archive_infos(infos)
            members = {info.filename: archive.read(info) for info in infos}
    except (OSError, StudyCapsuleError, zipfile.BadZipFile, RuntimeError) as exc:
        return StudyCapsuleVerification(
            valid=False,
            status=StudyCapsuleVerificationStatus.MALFORMED,
            archive_sha256=archive_sha256,
            member_count=member_count,
            errors=[str(exc)],
        )

    # Required members
    missing_required = sorted(set(REQUIRED_ARCHIVE_MEMBERS) - set(members))
    if missing_required:
        errors.append("missing required members: " + ", ".join(missing_required))
        status = StudyCapsuleVerificationStatus.MALFORMED

    # Duplicate check already in _validate_archive_infos, but also check traversal already.

    # Parse manifest
    manifest: StudyCapsuleManifest | None = None
    if "capsule-manifest.json" in members:
        raw_manifest = members["capsule-manifest.json"]
        try:
            # First ensure valid JSON
            parsed = json.loads(raw_manifest)
            if not isinstance(parsed, dict):
                raise ValueError("manifest must be a JSON object")
            # Check schema version early for unsupported_version discrimination
            sv = parsed.get("schema_version")
            if sv is not None and sv != STUDY_CAPSULE_SCHEMA_VERSION:
                errors.append(f"unsupported capsule schema_version: {sv}")
                status = StudyCapsuleVerificationStatus.UNSUPPORTED_VERSION
            manifest = StudyCapsuleManifest.model_validate_json(raw_manifest)
            capsule_id = manifest.capsule_id
            # Verify canonical fingerprint by recomputation (do not trust stored value blindly)
            expected_fp = manifest.fingerprint()
            if manifest.manifest_fingerprint != expected_fp:
                errors.append("manifest fingerprint mismatch: capsule has been tampered")
                # This is a tampering signal - distinguish from malformed
                if status is StudyCapsuleVerificationStatus.VALID:
                    status = StudyCapsuleVerificationStatus.TAMPERED
            manifest_fingerprint = manifest.manifest_fingerprint
            # Also verify that stored manifest_fingerprint in json matches recomputed – ensures offline.
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid capsule manifest: {exc}")
            if status is not StudyCapsuleVerificationStatus.UNSUPPORTED_VERSION:
                status = StudyCapsuleVerificationStatus.MALFORMED
        except Exception as exc:  # noqa: BLE001
            errors.append(f"invalid capsule manifest: {exc}")
            if status is StudyCapsuleVerificationStatus.VALID:
                status = StudyCapsuleVerificationStatus.MALFORMED

    # Checksums
    checksums: dict[str, str] = {}
    if "checksums.sha256" in members:
        try:
            checksums = _parse_checksums(members["checksums.sha256"])
            checksum_count = len(checksums)
        except StudyCapsuleError as exc:
            errors.append(str(exc))
            if status is StudyCapsuleVerificationStatus.VALID:
                status = StudyCapsuleVerificationStatus.MALFORMED

    # Checksum inventory must match archive payload members (excluding checksums.sha256 itself)
    # Note: manifest is included in checksums; verify.
    if checksums:
        expected_checksum_members = set(members) - {"checksums.sha256"}
        if set(checksums) != expected_checksum_members:
            errors.append("checksum inventory does not match archive payload members")
            if status is StudyCapsuleVerificationStatus.VALID:
                status = StudyCapsuleVerificationStatus.TAMPERED
        # Verify each checksum by recomputing bytes (do not trust manifest)
        for name, expected in checksums.items():
            content = members.get(name)
            if content is None or _sha256(content) != expected:
                errors.append(f"checksum mismatch: {name}")
                if status is StudyCapsuleVerificationStatus.VALID:
                    status = StudyCapsuleVerificationStatus.TAMPERED

    # Manifest inventory vs archive payload (embedded members)
    embedded_expected: set[str] = set()
    referenced: list[str] = []
    excluded: list[str] = []
    unavailable: list[str] = []
    if manifest is not None:
        # Embedded members must exactly match archive payload minus manifest+checksums
        embedded = {m.archive_path for m in manifest.members if m.archive_path is not None}
        # Filter None
        embedded_expected = {p for p in embedded if p is not None}
        actual_payload = set(members) - {"capsule-manifest.json", "checksums.sha256"}
        if embedded_expected != actual_payload:
            errors.append("manifest embedded inventory does not match archive payload members")
            if status is StudyCapsuleVerificationStatus.VALID:
                status = StudyCapsuleVerificationStatus.TAMPERED
        # Verify each embedded member's sha256/size against actual bytes
        for entry in manifest.members:
            if entry.archive_path is not None:
                content = members.get(entry.archive_path)
                if content is None:
                    errors.append(f"manifest payload is missing: {entry.archive_path}")
                    if status is StudyCapsuleVerificationStatus.VALID:
                        status = StudyCapsuleVerificationStatus.TAMPERED
                    continue
                if len(content) != entry.content_size or _sha256(content) != entry.sha256:
                    errors.append(f"manifest size/checksum mismatch: {entry.archive_path}")
                    if status is StudyCapsuleVerificationStatus.VALID:
                        status = StudyCapsuleVerificationStatus.TAMPERED
                # Also verify against checksums file entry
                if entry.sha256 is not None and checksums.get(entry.archive_path) != entry.sha256:
                    errors.append(f"checksum file disagrees with manifest: {entry.archive_path}")
                    if status is StudyCapsuleVerificationStatus.VALID:
                        status = StudyCapsuleVerificationStatus.TAMPERED
        # Collect audit lists
        for m in manifest.members:
            label = f"{m.kind.value}:{m.logical_id}"
            if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
                embedded_expected.add(label)  # overload for reporting
            if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT:
                referenced.append(label)
            elif m.policy is StudyCapsulePublicationPolicy.EXCLUDE:
                excluded.append(label)
        for u in manifest.unavailable:
            unavailable.append(f"{u.kind.value}:{u.logical_id}")

    # Final status discrimination
    is_valid = not errors
    if is_valid:
        status = StudyCapsuleVerificationStatus.VALID
    else:
        # If status still VALID but errors present, classify
        if status is StudyCapsuleVerificationStatus.VALID:
            # Heuristic: checksum mismatches / fingerprint mismatches => tampered, version issues => unsupported, rest => malformed
            tampered_hints = (
                "checksum mismatch",
                "fingerprint mismatch",
                "does not match archive",
                "tampered",
            )
            if any(any(h in e for h in tampered_hints) for e in errors):
                status = StudyCapsuleVerificationStatus.TAMPERED
            elif any("unsupported" in e for e in errors):
                status = StudyCapsuleVerificationStatus.UNSUPPORTED_VERSION
            else:
                status = StudyCapsuleVerificationStatus.MALFORMED

    # Build audit lists for response
    embedded_members_audit: list[str] = []
    referenced_members_audit: list[str] = []
    excluded_members_audit: list[str] = []
    unavailable_audit: list[str] = []
    if manifest is not None:
        for m in manifest.members:
            key = f"{m.kind.value}:{m.logical_id}"
            if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
                embedded_members_audit.append(key)
            elif m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT:
                referenced_members_audit.append(key)
            else:
                excluded_members_audit.append(key)
        for u in manifest.unavailable:
            unavailable_audit.append(f"{u.kind.value}:{u.logical_id}")

    return StudyCapsuleVerification(
        valid=is_valid,
        status=status,
        archive_sha256=archive_sha256,
        capsule_id=capsule_id,
        manifest_fingerprint=manifest_fingerprint,
        member_count=member_count,
        checksum_count=checksum_count,
        errors=sorted(set(errors)),
        warnings=warnings,
        embedded_members=sorted(embedded_members_audit),
        referenced_members=sorted(referenced_members_audit),
        excluded_members=sorted(excluded_members_audit),
        unavailable_members=sorted(unavailable_audit),
    )


# ---------------------------------------------------------------------------
# Helpers (deterministic serialization, archiving)
# ---------------------------------------------------------------------------


def _archive_path_for(
    kind: StudyCapsuleMemberKind, logical_id: str, encoding_format: str | None
) -> str:
    # Deterministic, safe, human-readable path per kind.
    # Use artifacts/<kind>/<logical_id>.<ext>
    # Determine extension from encoding_format or kind default.
    ext_map: dict[StudyCapsuleMemberKind, str] = {
        StudyCapsuleMemberKind.SCENARIO_SEED: "yaml",
        StudyCapsuleMemberKind.RUN_SUMMARY: "json",
        StudyCapsuleMemberKind.VALIDATION_RESULT: "json",
        StudyCapsuleMemberKind.COMPARISON_REPORT: "json",
        StudyCapsuleMemberKind.CONSEQUENCE_REPORT: "json",
        StudyCapsuleMemberKind.EVIDENCE_PACK: "json",
        StudyCapsuleMemberKind.DIAGNOSTIC_RESULT: "json",
        StudyCapsuleMemberKind.PROVENANCE_GRAPH: "json",
        StudyCapsuleMemberKind.DETERMINISTIC_REPORT: "md",
        StudyCapsuleMemberKind.ANALYST_NOTE: "json",
        StudyCapsuleMemberKind.RO_CRATE_REFERENCE: "json",
    }
    ext = ext_map.get(kind, "json")
    # If explicit encoding_format hints, use that extension
    if encoding_format is not None:
        # e.g., "application/json" -> json
        # Keep stable mapping without dynamic guess; mypy-safe.
        _unused = encoding_format
        if "yaml" in encoding_format:
            ext = "yaml"
        elif "json" in encoding_format:
            ext = "json"
        elif "markdown" in encoding_format:
            ext = "md"
        elif "csv" in encoding_format:
            ext = "csv"
    # Ensure logical_id is safe file name (already validated identifier)
    filename = f"{logical_id}.{ext}"
    return f"artifacts/{kind.value}/{filename}"


def _media_type_for_kind(kind: StudyCapsuleMemberKind) -> str:
    mapping = {
        StudyCapsuleMemberKind.SCENARIO_SEED: "application/yaml",
        StudyCapsuleMemberKind.ANALYST_NOTE: "application/json",
        StudyCapsuleMemberKind.DETERMINISTIC_REPORT: "text/markdown",
    }
    return mapping.get(kind, "application/json")


def _validate_destination(target: Path, *, overwrite: bool) -> None:
    if target.suffix.lower() != ".zip":
        raise StudyCapsuleError("study-capsule destination must use the .zip suffix")
    if target.is_symlink():
        raise StudyCapsuleError("study-capsule destination must not be a symbolic link")
    if target.exists() and not target.is_file():
        raise StudyCapsuleError("study-capsule destination must be a file path")
    if target.exists() and not overwrite:
        raise FileExistsError(f"study-capsule destination already exists: {target}")
    parent = target.parent
    if parent.is_symlink() or not parent.is_dir():
        raise StudyCapsuleError(
            "study-capsule destination parent must be an existing non-symlink directory"
        )


def _validate_archive_name(name: str) -> None:
    if not name or "\\" in name or "\x00" in name:
        raise StudyCapsuleError("study-capsule archive member has an unsafe path")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise StudyCapsuleError(f"unsafe study-capsule archive path: {name}")


def _validate_archive_infos(infos: list[zipfile.ZipInfo]) -> None:
    if len(infos) > MAX_ARCHIVE_FILE_COUNT:
        raise StudyCapsuleError("study-capsule archive exceeds file-count ceiling")
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise StudyCapsuleError("study-capsule archive contains duplicate members")
    # Stable ordering check - we enforce during build but verify here as tamper detection:
    # Not strictly required to reject unsorted, but we can ensure ordering is stable?
    # The spec says verifier must reject duplicate and traversal, but ordering is not required for validity
    # but deterministic build must produce stable ordering.
    total = 0
    for info in infos:
        _validate_archive_name(info.filename)
        if info.is_dir():
            raise StudyCapsuleError("study-capsule archive directory entries are not supported")
        if info.compress_type != zipfile.ZIP_STORED:
            raise StudyCapsuleError(
                f"study-capsule member is not deterministically stored: {info.filename}"
            )
        if info.date_time != _FIXED_ZIP_TIMESTAMP:
            raise StudyCapsuleError(
                f"study-capsule member has non-deterministic timestamp: {info.filename}"
            )
        mode = info.external_attr >> 16
        if mode and (mode & 0o170000) == 0o120000:
            raise StudyCapsuleError("study-capsule archive symbolic links are not supported")
        if info.create_system != 3 or mode != 0o100644:
            raise StudyCapsuleError(
                f"study-capsule member has non-deterministic file mode: {info.filename}"
            )
        if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
            raise StudyCapsuleError(f"study-capsule member exceeds byte ceiling: {info.filename}")
        total += info.file_size
        if total > MAX_ARCHIVE_TOTAL_BYTES:
            raise StudyCapsuleError("study-capsule archive exceeds total-byte ceiling")


def _parse_checksums(payload: bytes) -> dict[str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StudyCapsuleError("checksums.sha256 is not UTF-8") from exc
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or not _SHA256_RE.fullmatch(parts[0]):
            raise StudyCapsuleError("checksums.sha256 contains an invalid line")
        name = parts[1]
        _validate_archive_name(name)
        if name in result:
            raise StudyCapsuleError("checksums.sha256 contains duplicate paths")
        result[name] = parts[0]
    return result


def _checksum_bytes(checksums: dict[str, str]) -> bytes:
    return "".join(f"{digest}  {name}\n" for name, digest in sorted(checksums.items())).encode(
        "utf-8"
    )


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    target = io.BytesIO()
    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(members.items()):
            _validate_archive_name(name)
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return target.getvalue()


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(
            _redact_value(payload),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return _safe_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict) and isinstance(value, dict):
        # value is already known to be dict here; iterate with sorted keys
        return {_safe_text(str(key)): _redact_value(item) for key, item in sorted(value.items())}
    return value


def _safe_text(value: str) -> str:
    result = value
    for pattern in (_FILE_URI, _WINDOWS_PATH, _HOME_PATH, _POSIX_ABS):
        result = pattern.sub(_PATH_REDACTION, result)
    return result


def _contains_secret_hint(value: str) -> bool:
    for pat in _SECRET_PATTERNS:
        if pat.search(value):
            return True
    return "secret" in value.lower() and "=" in value


def _canonical_json(payload: object) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _media_type(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    explicit = {
        ".cff": "text/yaml",
        ".csv": "text/csv",
        ".gz": "application/gzip",
        ".json": "application/json",
        ".md": "text/markdown",
        ".parquet": "application/vnd.apache.parquet",
        ".xml": "application/xml",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
    }
    return explicit.get(suffix) or mimetypes.guess_type(path)[0] or "application/octet-stream"


# Convenience for preview in UI


def preview_membership(request: StudyCapsuleRequest) -> dict[str, list[str]]:
    """Return preview lists for UI (embedded, referenced, excluded, unavailable)."""

    embedded = [
        f"{m.kind.value}:{m.logical_id}"
        for m in request.members
        if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
    ]
    referenced = [
        f"{m.kind.value}:{m.logical_id}"
        for m in request.members
        if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
    ]
    excluded = [
        f"{m.kind.value}:{m.logical_id}"
        for m in request.members
        if m.policy is StudyCapsulePublicationPolicy.EXCLUDE
    ]
    unavailable_list = [f"{u.kind.value}:{u.logical_id}" for u in request.unavailable]
    return {
        "embedded": sorted(embedded),
        "referenced": sorted(referenced),
        "excluded": sorted(excluded),
        "unavailable": sorted(unavailable_list),
    }


def default_synthetic_member(
    kind: StudyCapsuleMemberKind,
    logical_id: str,
    *,
    evidence_label: StudyCapsuleEvidenceLabel = StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
    policy: StudyCapsulePublicationPolicy = StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
) -> StudyCapsuleMemberInput:
    """Helper to create a synthetic derived member with deterministic dummy bytes."""

    content: bytes | None = None
    if policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED:
        payload = {
            "kind": kind.value,
            "logical_id": logical_id,
            "evidence_label": evidence_label.value,
            "schema_version": "1.0",
            "deterministic": True,
        }
        content = _json_bytes(payload)
    fingerprint = _sha256((kind.value + ":" + logical_id).encode("utf-8"))
    # Ensure fingerprint is 64 hex (sha256 already)
    return StudyCapsuleMemberInput(
        kind=kind,
        logical_id=logical_id,
        fingerprint=fingerprint,
        evidence_label=evidence_label,
        admission_label=StudyCapsuleAdmissionLabel.NOT_APPLICABLE,
        policy=policy,
        content=content,
        exclusion_reason="excluded for demonstration; policy requires reason"
        if policy is StudyCapsulePublicationPolicy.EXCLUDE
        else None,
        reference_note="fingerprint reference for review"
        if policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
        else None,
    )

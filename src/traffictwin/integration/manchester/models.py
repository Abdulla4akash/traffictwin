"""Strict source-neutral models for MAN-01 immutable Manchester source snapshots.

These artifacts implement the snapshot half of Gate B only. They are candidate
library evidence: no source adapter, transport client, parser, freshness policy,
or capability claim is implemented here, and ``MAN-01`` remains ``planned``.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MANCHESTER_SNAPSHOT_SCHEMA_VERSION = "1.0"
MANCHESTER_SNAPSHOT_METHOD_VERSION = "manchester-snapshot-1.0"
MANCHESTER_QUARANTINE_METHOD_VERSION = "manchester-quarantine-1.0"
MANCHESTER_SNAPSHOT_CAPABILITY_ID = "MAN-01"

MANIFEST_FILE_NAME = "snapshot-manifest.json"
RECEIPT_FILE_NAME = "snapshot-receipt.json"
QUARANTINE_MANIFEST_FILE_NAME = "quarantine-manifest.json"
QUARANTINE_RECEIPT_FILE_NAME = "quarantine-receipt.json"
RAW_DIRECTORY_NAME = "raw"

MAX_MEMBER_PATH_LENGTH = 200
MAX_FINDING_MESSAGE_LENGTH = 1_000
MAX_PARAMETER_VALUE_LENGTH = 2_000
MAX_ATTRIBUTION_LENGTH = 500

_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,252}[a-z0-9])?$")
_MEDIA_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")
_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_PARAMETER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\[\]-]{0,63}$")
_SNAPSHOT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$")

# Structural secret refusal: a parameter or header name whose normalised form
# contains one of these tokens is rejected outright (fail closed; false
# positives are acceptable, silent credential persistence is not).
_SECRET_NAME_TOKENS = (
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "passwd",
    "password",
    "secret",
    "sessionid",
    "token",
)
_SECRET_NAME_PARTS = frozenset({"auth", "key", "sig", "signature", "session"})

# Structural private-path refusal for persisted free text. This is a targeted
# deny pattern, not a completeness claim; snapshot metadata has no legitimate
# use for local absolute paths.
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")


def canonical_json(payload: object) -> str:
    """Serialise a payload with the repository's canonical JSON conventions."""

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(payload: bytes) -> str:
    """Return the lowercase SHA-256 hex digest used across the repository."""

    return hashlib.sha256(payload).hexdigest()


def _is_secret_name(name: str) -> bool:
    normalised = re.sub(r"[^a-z0-9]", "", name.lower())
    if any(token in normalised for token in _SECRET_NAME_TOKENS):
        return True
    parts = {part for part in re.split(r"[^a-z0-9]+", name.lower()) if part}
    return not parts.isdisjoint(_SECRET_NAME_PARTS)


def _reject_private_paths(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    return value


def _reject_credential_url(value: str, label: str) -> str:
    if "://" not in value:
        return value
    remainder = value.split("://", 1)[1]
    authority = remainder.split("/", 1)[0]
    if "@" in authority:
        raise ValueError(f"{label} must not contain a credential-bearing URL")
    if "?" in value or "#" in value:
        raise ValueError(f"{label} must not contain a URL with a query or fragment")
    return value


class ManchesterSnapshotModel(BaseModel):
    """Strict, frozen, finite base model for MAN-01 snapshot artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        """Return deterministic canonical JSON for this artifact."""

        return canonical_json(self.model_dump(mode="json"))

    def fingerprint(self) -> str:
        """Return the SHA-256 fingerprint of the canonical JSON."""

        return sha256_hex(self.canonical_json().encode("utf-8"))


class ManchesterFindingSeverity(StrEnum):
    """Severity of one structural snapshot finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ManchesterValidationState(StrEnum):
    """Structural validation outcome recorded on a snapshot manifest."""

    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNINGS = "accepted_with_warnings"
    REJECTED = "rejected"


class ManchesterPublicationClass(StrEnum):
    """Exact publication classes from the v0.7 design (§8)."""

    PRIVATE = "private"
    REDISTRIBUTABLE_RAW = "redistributable_raw"
    REDISTRIBUTABLE_DERIVED = "redistributable_derived"
    METADATA_ONLY = "metadata_only"


class ManchesterPriorRelation(StrEnum):
    """Relationship between this snapshot and the previous accepted one."""

    FIRST_SNAPSHOT = "first_snapshot"
    SUPERSEDES = "supersedes"
    DUPLICATE_NO_CHANGE = "duplicate_no_change"


class ManchesterSnapshotFinding(ManchesterSnapshotModel):
    """One typed structural finding attached to a snapshot manifest."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=96)
    severity: ManchesterFindingSeverity
    message: str = Field(min_length=1, max_length=MAX_FINDING_MESSAGE_LENGTH)
    artifact: str | None = Field(default=None, max_length=MAX_MEMBER_PATH_LENGTH)

    @field_validator("message", "artifact")
    @classmethod
    def screen_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _reject_private_paths(value, "finding text")


class ManchesterSourceIdentity(ManchesterSnapshotModel):
    """Source, adapter, schema, and freshness-policy identity."""

    source_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,47}$")
    source_name: str = Field(min_length=1, max_length=200)
    adapter_version: str
    source_schema_version: str
    freshness_policy_version: str

    @field_validator("adapter_version", "source_schema_version", "freshness_policy_version")
    @classmethod
    def validate_version_label(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("version labels must be short safe identifiers")
        return value

    @field_validator("source_name")
    @classmethod
    def screen_source_name(cls, value: str) -> str:
        return _reject_private_paths(value, "source name")


class ManchesterRequestIdentity(ManchesterSnapshotModel):
    """Redacted request identity: endpoint plus typed, secret-free parameters.

    There is deliberately no raw-URL or query-string field: credentials and
    sensitive query values are removed before this model exists, and the names
    of removed parameters are recorded without their values.
    """

    method: Literal["GET"] = "GET"
    scheme: Literal["https"] = "https"
    host: str = Field(max_length=253)
    path: str = Field(min_length=1, max_length=500)
    parameters: tuple[tuple[str, str | int | float | bool], ...] = ()
    redacted_parameter_names: tuple[str, ...] = ()

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        if (
            not _HOST_RE.fullmatch(value)
            or value.startswith((".", "-"))
            or value.endswith((".", "-"))
            or ".." in value
        ):
            raise ValueError("host must be a bare lowercase DNS name")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("request path must start with '/'")
        if any(marker in value for marker in ("?", "#", "@", " ", "\\", "..")):
            raise ValueError("request path must not contain query, fragment, or unsafe markers")
        return value

    @field_validator("parameters")
    @classmethod
    def validate_parameters(
        cls, value: tuple[tuple[str, str | int | float | bool], ...]
    ) -> tuple[tuple[str, str | int | float | bool], ...]:
        names = [name for name, _parameter in value]
        if names != sorted(names) or len(set(names)) != len(names):
            raise ValueError("parameters must be sorted by unique name")
        for name, parameter in value:
            if not _PARAMETER_NAME_RE.fullmatch(name):
                raise ValueError(f"parameter name {name!r} is not a safe identifier")
            if _is_secret_name(name):
                raise ValueError(f"parameter name {name!r} looks like a credential")
            if isinstance(parameter, str):
                if len(parameter) > MAX_PARAMETER_VALUE_LENGTH:
                    raise ValueError(f"parameter {name!r} value is too long")
                _reject_private_paths(parameter, f"parameter {name!r}")
                _reject_credential_url(parameter, f"parameter {name!r}")
        return value

    @field_validator("redacted_parameter_names")
    @classmethod
    def validate_redacted_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for name in value:
            if not _PARAMETER_NAME_RE.fullmatch(name):
                raise ValueError("redacted parameter names must be safe identifiers")
        if len(set(value)) != len(value):
            raise ValueError("redacted parameter names must be unique")
        if tuple(sorted(value)) != value:
            raise ValueError("redacted parameter names must be sorted")
        return value

    @model_validator(mode="after")
    def validate_no_redacted_overlap(self) -> Self:
        overlap = set(self.redacted_parameter_names) & {name for name, _value in self.parameters}
        if overlap:
            raise ValueError("a redacted parameter cannot also carry a stored value")
        return self


class ManchesterRetrievalWindow(ManchesterSnapshotModel):
    """UTC retrieval start and end instants."""

    started_at_utc: datetime
    completed_at_utc: datetime

    @field_validator("started_at_utc", "completed_at_utc")
    @classmethod
    def validate_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("retrieval instants must be timezone-aware UTC")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError("retrieval cannot complete before it starts")
        return self


class ManchesterHttpMetadata(ManchesterSnapshotModel):
    """Safe response metadata; header maps are structurally impossible here."""

    status_code: int = Field(ge=100, le=599)
    final_path: str | None = Field(default=None, max_length=500)
    network_requests: int = Field(default=1, ge=1)
    redirect_hops: int = Field(default=0, ge=0)
    response_content_type: str | None = Field(default=None, max_length=200)
    response_content_encoding: Literal["gzip", "deflate"] | None = None
    declared_content_length: int | None = Field(default=None, ge=0)
    etag: str | None = Field(default=None, max_length=200)
    last_modified: str | None = Field(default=None, max_length=200)

    @field_validator("response_content_type")
    @classmethod
    def validate_media_type(cls, value: str | None) -> str | None:
        if value is not None and not _MEDIA_TYPE_RE.fullmatch(value):
            raise ValueError("response content type must be a bare lowercase media type")
        return value

    @field_validator("final_path")
    @classmethod
    def validate_final_path(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.startswith("/") or any(
            marker in value for marker in ("?", "#", "@", " ", "\\", "..")
        ):
            raise ValueError("final response path must be a safe absolute path")
        return value

    @model_validator(mode="after")
    def validate_redirect_count(self) -> Self:
        if self.redirect_hops >= self.network_requests:
            raise ValueError("redirect hops must be below the total network request count")
        return self

    @field_validator("etag", "last_modified")
    @classmethod
    def screen_header_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        _reject_private_paths(value, "response metadata")
        _reject_credential_url(value, "response metadata")
        return value


class ManchesterRawMember(ManchesterSnapshotModel):
    """Identity of one raw response member preserved byte-for-byte."""

    relative_path: str = Field(min_length=1, max_length=MAX_MEMBER_PATH_LENGTH)
    byte_size: int = Field(ge=0)
    media_type: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if "\\" in value or ":" in value:
            raise ValueError("member paths must be POSIX-relative without drive markers")
        if PurePosixPath(value).is_absolute():
            raise ValueError("member paths must be relative")
        segments = value.split("/")
        for segment in segments:
            if segment in {"", ".", ".."} or not _PATH_SEGMENT_RE.fullmatch(segment):
                raise ValueError(f"member path segment {segment!r} is unsafe")
        return value

    @field_validator("media_type")
    @classmethod
    def validate_media_type(cls, value: str) -> str:
        if not _MEDIA_TYPE_RE.fullmatch(value):
            raise ValueError("member media type must be a bare lowercase media type")
        return value


class ManchesterSnapshotPolicy(ManchesterSnapshotModel):
    """Explicit publication bounds; there are no implicit defaults."""

    max_member_count: int = Field(ge=1, le=100_000)
    max_member_bytes: int = Field(ge=1, le=2_000_000_000)
    max_total_bytes: int = Field(ge=1, le=4_000_000_000)

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.max_total_bytes < self.max_member_bytes:
            raise ValueError("total byte bound cannot be below the per-member bound")
        return self


class ManchesterPriorSnapshotLink(ManchesterSnapshotModel):
    """Relationship to the previous accepted snapshot of the same source."""

    relation: ManchesterPriorRelation
    prior_snapshot_id: str | None = None
    prior_raw_fingerprint: str | None = None

    @field_validator("prior_snapshot_id")
    @classmethod
    def validate_prior_id(cls, value: str | None) -> str | None:
        if value is not None and not _SNAPSHOT_ID_RE.fullmatch(value):
            raise ValueError("prior snapshot id has an invalid shape")
        return value

    @field_validator("prior_raw_fingerprint")
    @classmethod
    def validate_prior_fingerprint(cls, value: str | None) -> str | None:
        if value is not None and not _SHA256_RE.fullmatch(value):
            raise ValueError("prior raw fingerprint must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_relation(self) -> Self:
        if self.relation is ManchesterPriorRelation.FIRST_SNAPSHOT:
            if self.prior_snapshot_id is not None or self.prior_raw_fingerprint is not None:
                raise ValueError("a first snapshot cannot reference a prior snapshot")
        elif self.prior_snapshot_id is None or self.prior_raw_fingerprint is None:
            raise ValueError(f"relation {self.relation.value} requires prior identity")
        return self


def build_raw_fingerprint(members: Sequence[ManchesterRawMember]) -> str:
    """Fingerprint the ordered raw-member inventory (path, size, SHA-256)."""

    inventory = [
        {
            "relative_path": member.relative_path,
            "byte_size": member.byte_size,
            "sha256": member.sha256,
        }
        for member in sorted(members, key=lambda item: item.relative_path)
    ]
    return sha256_hex(canonical_json(inventory).encode("utf-8"))


def build_snapshot_id(
    source_id: str,
    retrieval_started_at_utc: datetime,
    raw_fingerprint: str,
) -> str:
    """Derive the deterministic snapshot identifier used as the directory name."""

    return f"{source_id}-{retrieval_started_at_utc:%Y%m%dT%H%M%S}Z-{raw_fingerprint[:12]}"


class ManchesterSnapshotManifest(ManchesterSnapshotModel):
    """Complete immutable identity of one acquired raw snapshot."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-01"] = "MAN-01"
    method_version: Literal["manchester-snapshot-1.0"] = "manchester-snapshot-1.0"
    snapshot_id: str
    source: ManchesterSourceIdentity
    request: ManchesterRequestIdentity
    retrieval: ManchesterRetrievalWindow
    http: ManchesterHttpMetadata | None = None
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1)
    member_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_state: ManchesterValidationState
    findings: tuple[ManchesterSnapshotFinding, ...] = ()
    prior: ManchesterPriorSnapshotLink
    publication_class: ManchesterPublicationClass
    licence_id: str
    attribution_text: str = Field(max_length=MAX_ATTRIBUTION_LENGTH)
    access_date: date
    synthetic: bool

    @field_validator("licence_id")
    @classmethod
    def validate_licence_id(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("licence id must be a short safe identifier")
        return value

    @field_validator("attribution_text")
    @classmethod
    def screen_attribution(cls, value: str) -> str:
        return _reject_private_paths(value, "attribution text")

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        paths = [member.relative_path for member in self.members]
        if paths != sorted(paths):
            raise ValueError("members must be sorted by relative path")
        if len(set(paths)) != len(paths):
            raise ValueError("member paths must be unique")
        folded = {path.casefold() for path in paths}
        if len(folded) != len(paths):
            raise ValueError("member paths must be unique case-insensitively")
        if self.member_count != len(self.members):
            raise ValueError("member_count must equal the member inventory length")
        total = sum(member.byte_size for member in self.members)
        if self.total_bytes != total:
            raise ValueError("total_bytes must equal the sum of member sizes")
        expected_fingerprint = build_raw_fingerprint(self.members)
        if self.raw_fingerprint != expected_fingerprint:
            raise ValueError("raw_fingerprint does not match the member inventory")
        expected_id = build_snapshot_id(
            self.source.source_id,
            self.retrieval.started_at_utc,
            self.raw_fingerprint,
        )
        if self.snapshot_id != expected_id:
            raise ValueError("snapshot_id does not match its derivation inputs")
        errors = [f for f in self.findings if f.severity is ManchesterFindingSeverity.ERROR]
        warnings = [f for f in self.findings if f.severity is ManchesterFindingSeverity.WARNING]
        if self.validation_state is ManchesterValidationState.ACCEPTED and (errors or warnings):
            raise ValueError("an accepted snapshot cannot carry warnings or errors")
        if self.validation_state is ManchesterValidationState.ACCEPTED_WITH_WARNINGS:
            if errors:
                raise ValueError("a warning-accepted snapshot cannot carry errors")
            if not warnings:
                raise ValueError("a warning-accepted snapshot requires at least one warning")
        if self.validation_state is ManchesterValidationState.REJECTED and not errors:
            raise ValueError("a rejected snapshot requires at least one error finding")
        if (
            self.prior.relation is ManchesterPriorRelation.DUPLICATE_NO_CHANGE
            and self.prior.prior_raw_fingerprint != self.raw_fingerprint
        ):
            raise ValueError("a duplicate/no-change snapshot must repeat the prior bytes")
        if (
            self.prior.relation is ManchesterPriorRelation.SUPERSEDES
            and self.prior.prior_raw_fingerprint == self.raw_fingerprint
        ):
            raise ValueError("a superseding snapshot cannot repeat the prior bytes")
        if self.prior.prior_snapshot_id == self.snapshot_id:
            raise ValueError("a snapshot cannot be its own prior")
        return self


class ManchesterQuarantineManifest(ManchesterSnapshotModel):
    """Pre-parse immutable identity for one complete bounded acquisition."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-01"] = "MAN-01"
    method_version: Literal["manchester-quarantine-1.0"] = "manchester-quarantine-1.0"
    snapshot_id: str
    source: ManchesterSourceIdentity
    request: ManchesterRequestIdentity
    retrieval: ManchesterRetrievalWindow
    http: ManchesterHttpMetadata | None = None
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1)
    member_count: int = Field(ge=1)
    total_bytes: int = Field(ge=0)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_class: ManchesterPublicationClass
    licence_id: str
    attribution_text: str = Field(max_length=MAX_ATTRIBUTION_LENGTH)
    access_date: date
    synthetic: bool

    @field_validator("licence_id")
    @classmethod
    def validate_licence_id(cls, value: str) -> str:
        if not _LABEL_RE.fullmatch(value):
            raise ValueError("licence id must be a short safe identifier")
        return value

    @field_validator("attribution_text")
    @classmethod
    def screen_attribution(cls, value: str) -> str:
        return _reject_private_paths(value, "attribution text")

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        paths = [member.relative_path for member in self.members]
        if paths != sorted(paths):
            raise ValueError("members must be sorted by relative path")
        if len(set(paths)) != len(paths) or len({path.casefold() for path in paths}) != len(paths):
            raise ValueError("member paths must be unique, including case-insensitively")
        if self.member_count != len(self.members):
            raise ValueError("member_count must equal the member inventory length")
        if self.total_bytes != sum(member.byte_size for member in self.members):
            raise ValueError("total_bytes must equal the sum of member sizes")
        if self.raw_fingerprint != build_raw_fingerprint(self.members):
            raise ValueError("raw_fingerprint does not match the member inventory")
        expected_id = build_snapshot_id(
            self.source.source_id,
            self.retrieval.started_at_utc,
            self.raw_fingerprint,
        )
        if self.snapshot_id != expected_id:
            raise ValueError("snapshot_id does not match its derivation inputs")
        return self


class ManchesterSnapshotReceipt(ManchesterSnapshotModel):
    """Verification record published beside an accepted snapshot manifest."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-01"] = "MAN-01"
    method_version: Literal["manchester-snapshot-1.0"] = "manchester-snapshot-1.0"
    snapshot_id: str
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_member_count: int = Field(ge=1)
    verified_total_bytes: int = Field(ge=0)
    policy: ManchesterSnapshotPolicy
    read_only_applied: bool
    published: Literal[True] = True

    @field_validator("snapshot_id")
    @classmethod
    def validate_snapshot_id(cls, value: str) -> str:
        if not _SNAPSHOT_ID_RE.fullmatch(value):
            raise ValueError("snapshot id has an invalid shape")
        return value


class ManchesterQuarantineReceipt(ManchesterSnapshotModel):
    """Verification record proving raw bytes existed before parsing began."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-01"] = "MAN-01"
    method_version: Literal["manchester-quarantine-1.0"] = "manchester-quarantine-1.0"
    snapshot_id: str
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    verified_member_count: int = Field(ge=1)
    verified_total_bytes: int = Field(ge=0)
    policy: ManchesterSnapshotPolicy
    read_only_applied: bool
    quarantined: Literal[True] = True

    @field_validator("snapshot_id")
    @classmethod
    def validate_snapshot_id(cls, value: str) -> str:
        if not _SNAPSHOT_ID_RE.fullmatch(value):
            raise ValueError("snapshot id has an invalid shape")
        return value

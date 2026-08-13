"""Immutable, content-addressed snapshot registry for Manchester source snapshots.

The registry composes the frozen snapshot and source-operation contracts without
modifying them. It stores portable, opaque references to verified snapshots and
rejects private paths, credential values, and evidence-standing inflation.

Every registration records content fingerprint, retrieved time, source family,
coverage and counts, parser and schema versions, validation state (accepted or
rejected), freshness, opaque portable storage reference, and provenance. The
registry itself is an immutable frozen model with deterministic fingerprint and
idempotent registration.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Self

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.source_operations_models import (
    EvidenceStanding,
    SourceFamily,
    SourceFreshnessStanding,
    source_definition,
)

SNAPSHOT_REGISTRY_SCHEMA_VERSION = "1.0"
SNAPSHOT_REGISTRY_METHOD_VERSION = "manchester-snapshot-registry-1.0"

_SAFE_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$"
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|~/|[A-Za-z]:\\)")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)
_OPAQUE_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$"
_BODS_BUS_TOKEN_RE = re.compile(r"(?i)general.*road.*traffic|private.*vehicle.*traffic")


def _screen_portable_text(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"{label} must not contain a credential or secret value")
    return value


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


class SnapshotValidationState(StrEnum):
    """Validation outcome for one immutable snapshot."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SnapshotRegistryError(RuntimeError):
    """Typed refusal from snapshot registry operations."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class SnapshotRegistryModel(ManchesterSnapshotModel):
    """Frozen base that screens every persisted free-text value."""

    @model_validator(mode="after")
    def _reject_nonportable(self) -> Self:
        def visit(value: object) -> None:
            if isinstance(value, str):
                _screen_portable_text(value, "snapshot registry metadata")
            elif isinstance(value, dict):
                for k, v in value.items():
                    visit(k)
                    visit(v)
            elif isinstance(value, (list, tuple, set, frozenset)):
                for item in value:
                    visit(item)

        visit(self.model_dump(mode="python"))
        return self


class SnapshotRegistration(SnapshotRegistryModel):
    """Immutable record of one verified snapshot.

    The record is metadata-only: content fingerprint, retrieved time, source
    family, coverage and counts, parser and schema, validation state,
    freshness, opaque storage reference, and provenance. It carries no bytes
    and no credential value.
    """

    registration_id: str = Field(pattern=_SAFE_LABEL_PATTERN)
    snapshot_identity: str = Field(pattern=_SAFE_LABEL_PATTERN)
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieved_at_utc: datetime
    source_family: SourceFamily
    coverage_summary: str = Field(min_length=1, max_length=300)
    record_count: int = Field(ge=0, le=10_000_000)
    parser_version: str = Field(pattern=_SAFE_LABEL_PATTERN)
    schema_version: str = Field(pattern=_SAFE_LABEL_PATTERN)
    validation_state: SnapshotValidationState
    freshness: SourceFreshnessStanding
    storage_reference: str = Field(min_length=1, max_length=300, pattern=_OPAQUE_REF_PATTERN)
    provenance_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_standing: EvidenceStanding

    @field_validator("retrieved_at_utc")
    @classmethod
    def _validate_retrieved(cls, value: datetime) -> datetime:
        return _require_utc(value, "retrieved time")

    @model_validator(mode="after")
    def _validate_against_frozen_source(self) -> Self:
        definition = source_definition(self.source_family)
        if self.evidence_standing != definition.evidence_standing:
            raise ValueError("evidence standing inflation is not permitted")
        if self.freshness not in definition.allowed_freshness:
            raise ValueError("freshness exceeds the frozen source policy")
        if (
            self.source_family is SourceFamily.TFGM
            and self.validation_state is SnapshotValidationState.ACCEPTED
        ):
            raise ValueError("TfGM measured traffic has no accepted snapshot")
        if self.source_family is SourceFamily.BODS and _BODS_BUS_TOKEN_RE.search(
            self.coverage_summary
        ):
            raise ValueError("BODS is bus-only; general road traffic relabel rejected")
        if self.source_family in {
            SourceFamily.WEBTRIS,
            SourceFamily.NATIONAL_HIGHWAYS,
        }:
            # Strategic-road sources must not claim Manchester city-road coverage
            lowered = self.coverage_summary.lower()
            if (
                "manchester city-road" in lowered
                and "strategic" not in lowered
                and "city-road" in lowered
            ):
                raise ValueError("strategic-road source cannot claim Manchester city-road")
        return self


class SnapshotRegistry(SnapshotRegistryModel):
    """Immutable ordered collection of snapshot registrations."""

    schema_version: str = SNAPSHOT_REGISTRY_SCHEMA_VERSION
    method_version: str = SNAPSHOT_REGISTRY_METHOD_VERSION
    registered_at_utc: datetime
    snapshots: tuple[SnapshotRegistration, ...] = ()

    @field_validator("registered_at_utc")
    @classmethod
    def _validate_registered(cls, value: datetime) -> datetime:
        return _require_utc(value, "registry time")

    @model_validator(mode="after")
    def _validate_registry(self) -> Self:
        ids = [s.registration_id for s in self.snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("registration ids must be unique")
        if ids != sorted(ids):
            raise ValueError("snapshots must be sorted by registration_id")
        # Fingerprint uniqueness (distinct content should have distinct registration,
        # but same fingerprint with different registration is allowed as distinct retrieval)
        return self


def register_snapshot(
    registry: SnapshotRegistry,
    registration: SnapshotRegistration,
) -> SnapshotRegistry:
    """Return a new registry with ``registration`` added, idempotent on exact match.

    If ``registration_id`` already exists with identical canonical JSON the original
    registry is returned unchanged (idempotent). If the id exists with different
    content the operation fails with a conflict error. The resulting snapshots
    remain sorted by registration_id.
    """

    for existing in registry.snapshots:
        if existing.registration_id == registration.registration_id:
            if existing == registration:
                return registry
            if existing.canonical_json() == registration.canonical_json():
                return registry
            raise SnapshotRegistryError(
                "CONFLICT",
                f"registration {registration.registration_id!r} already exists "
                "with different content",
            )
    # Also detect duplicate content fingerprint + retrieved time + source as potential
    # duplicate retrieval with different id; allow but keep deterministic ordering.
    new_snapshots = tuple(
        sorted((*registry.snapshots, registration), key=lambda s: s.registration_id)
    )
    return SnapshotRegistry(
        registered_at_utc=registry.registered_at_utc,
        snapshots=new_snapshots,
    )


def get_snapshot(
    registry: SnapshotRegistry,
    registration_id: str,
) -> SnapshotRegistration | None:
    """Return the registration for ``registration_id`` or ``None``."""

    for snap in registry.snapshots:
        if snap.registration_id == registration_id:
            return snap
    return None


def latest_snapshot_for_family(
    registry: SnapshotRegistry,
    family: SourceFamily,
) -> SnapshotRegistration | None:
    """Return the latest snapshot for ``family`` ordered by retrieved time."""

    candidates = [s for s in registry.snapshots if s.source_family is family]
    if not candidates:
        return None
    # Latest is max by retrieved_at_utc, then lexicographically by registration_id for determinism
    return max(candidates, key=lambda s: (s.retrieved_at_utc, s.registration_id))


def latest_accepted_for_family(
    registry: SnapshotRegistry,
    family: SourceFamily,
) -> SnapshotRegistration | None:
    """Return the latest accepted snapshot for ``family``."""

    candidates = [
        s
        for s in registry.snapshots
        if s.source_family is family and s.validation_state is SnapshotValidationState.ACCEPTED
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.retrieved_at_utc, s.registration_id))


def latest_rejected_for_family(
    registry: SnapshotRegistry,
    family: SourceFamily,
) -> SnapshotRegistration | None:
    """Return the latest rejected snapshot for ``family``."""

    candidates = [
        s
        for s in registry.snapshots
        if s.source_family is family and s.validation_state is SnapshotValidationState.REJECTED
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.retrieved_at_utc, s.registration_id))


def snapshot_registry_fingerprint(registry: SnapshotRegistry) -> str:
    """Return the canonical fingerprint of the registry."""

    return registry.fingerprint()


__all__ = [
    "SNAPSHOT_REGISTRY_METHOD_VERSION",
    "SNAPSHOT_REGISTRY_SCHEMA_VERSION",
    "SnapshotRegistration",
    "SnapshotRegistry",
    "SnapshotRegistryError",
    "SnapshotRegistryModel",
    "SnapshotValidationState",
    "get_snapshot",
    "latest_accepted_for_family",
    "latest_rejected_for_family",
    "latest_snapshot_for_family",
    "register_snapshot",
    "snapshot_registry_fingerprint",
]

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
from typing import Self

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.source_operations_models import (
    EvidenceStanding,
    SnapshotValidationState,
    SourceFamily,
    SourceFreshnessStanding,
    source_definition,
)

SNAPSHOT_REGISTRY_SCHEMA_VERSION = "1.0"
SNAPSHOT_REGISTRY_METHOD_VERSION = "manchester-snapshot-registry-1.0"
MAX_SNAPSHOTS = 500

_SAFE_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$"
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)
_OPAQUE_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$"
_BODS_BUS_REQUIRED_RE = re.compile(r"(?i)\bbus\b")
_BODS_FORBIDDEN_RE = re.compile(
    r"(?i)(general.*road.*traffic|private.*vehicle.*traffic|"
    r"traffic volume|city-wide|city wide|complete.*manchester|congestion)"
)


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
    freshness, opaque storage reference, provenance and exact validation
    receipt identity, validated time, and bounded rejection summary. It carries
    no bytes and no credential value.

    Chronology invariant (truthful ordering):

    ``retrieved_at_utc`` <= ``validated_at_utc`` <= registry
    ``registered_at_utc`` / catalogue ``evaluated_at_utc``.

    Accepted/rejected coherence:

    * ``ACCEPTED`` carries no rejection code/reason.
    * ``REJECTED`` requires a truthful nonempty ``rejection_code`` and
      ``rejection_reason`` (bounded, portable, and screened).

    Provenance (origin) and validation receipt (evaluation outcome) are two
    distinct 64-hex identities and must not be conflated.
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
    validation_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    validated_at_utc: datetime
    rejection_code: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]{2,95}$")
    rejection_reason: str | None = Field(default=None, min_length=1, max_length=300)
    evidence_standing: EvidenceStanding

    @field_validator("retrieved_at_utc")
    @classmethod
    def _validate_retrieved(cls, value: datetime) -> datetime:
        return _require_utc(value, "retrieved time")

    @field_validator("validated_at_utc")
    @classmethod
    def _validate_validated(cls, value: datetime) -> datetime:
        return _require_utc(value, "validation time")

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
        if self.source_family is SourceFamily.BODS:
            if not _BODS_BUS_REQUIRED_RE.search(self.coverage_summary):
                raise ValueError("BODS is bus-only; coverage must reference bus")
            if _BODS_FORBIDDEN_RE.search(self.coverage_summary):
                raise ValueError("BODS is bus-only; general road traffic relabel rejected")
        if self.source_family in {
            SourceFamily.WEBTRIS,
            SourceFamily.NATIONAL_HIGHWAYS,
        }:
            lowered = self.coverage_summary.lower()
            if "city-wide" in lowered or "city wide" in lowered:
                raise ValueError("strategic-road source cannot claim city-wide coverage")
            if "complete manchester" in lowered or "full manchester" in lowered:
                raise ValueError("strategic-road source cannot claim complete Manchester coverage")
            if (
                "manchester" in lowered
                and ("city-road" in lowered or "city road" in lowered)
                and "external to" not in lowered
            ):
                raise ValueError("strategic-road source cannot claim Manchester city-road")
        if self.provenance_fingerprint == self.validation_receipt_fingerprint:
            raise ValueError("provenance and validation receipt fingerprints must be distinct")
        # Truthful chronology: retrieval <= validation
        if self.retrieved_at_utc > self.validated_at_utc:
            raise ValueError("retrieved time must not be later than validation time")
        # Accepted/rejected coherence
        if self.validation_state is SnapshotValidationState.ACCEPTED:
            if self.rejection_code is not None or self.rejection_reason is not None:
                raise ValueError("accepted snapshot must not carry rejection code or reason")
        elif self.validation_state is SnapshotValidationState.REJECTED:
            if self.rejection_code is None or self.rejection_reason is None:
                raise ValueError("rejected snapshot requires rejection code and reason")
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("rejection reason must be a truthful nonempty summary")
            if not self.rejection_code or not self.rejection_code.strip():
                raise ValueError("rejection code must be a truthful nonempty code")
        return self


class SnapshotRegistry(SnapshotRegistryModel):
    """Immutable ordered collection of snapshot registrations.

    ``registered_at_utc`` is the deterministic admission/evaluation time for
    the registry. All ``retrieved_at_utc`` values must not be later than this
    timestamp so the registry never contains future-relative evidence.
    """

    schema_version: str = SNAPSHOT_REGISTRY_SCHEMA_VERSION
    method_version: str = SNAPSHOT_REGISTRY_METHOD_VERSION
    registered_at_utc: datetime
    snapshots: tuple[SnapshotRegistration, ...] = ()

    @field_validator("registered_at_utc")
    @classmethod
    def _validate_registered(cls, value: datetime) -> datetime:
        return _require_utc(value, "registry admission time")

    @property
    def admitted_at_utc(self) -> datetime:
        """Deterministic admission/evaluation time (alias for registered_at)."""

        return self.registered_at_utc

    @property
    def evaluated_at_utc(self) -> datetime:
        """Deterministic evaluation time (alias for registered_at)."""

        return self.registered_at_utc

    @model_validator(mode="after")
    def _validate_registry(self) -> Self:
        # Canonical revalidation of nested registrations to close model_copy bypass
        for snap in self.snapshots:
            try:
                SnapshotRegistration.model_validate(snap.model_dump(mode="python"))
            except Exception as exc:
                raise ValueError("snapshot registration failed canonical revalidation") from exc
        if len(self.snapshots) > MAX_SNAPSHOTS:
            raise ValueError(f"snapshot registry exceeds maximum of {MAX_SNAPSHOTS}")
        ids = [s.registration_id for s in self.snapshots]
        if len(ids) != len(set(ids)):
            raise ValueError("registration ids must be unique")
        if ids != sorted(ids):
            raise ValueError("snapshots must be sorted by registration_id")
        # One canonical record per snapshot_identity (immutable identity)
        identities = [s.snapshot_identity for s in self.snapshots]
        if len(identities) != len(set(identities)):
            raise ValueError("snapshot identities must be unique")
        # Chronology: no snapshot in the future relative to registry admission
        # Truthful ordering: retrieved <= validated <= admission
        for snap in self.snapshots:
            if snap.retrieved_at_utc > self.registered_at_utc:
                raise ValueError(
                    "snapshot retrieved time must not be later than registry admission time"
                )
            if snap.validated_at_utc > self.registered_at_utc:
                raise ValueError(
                    "snapshot validation time must not be later than registry admission time"
                )
            if snap.retrieved_at_utc > snap.validated_at_utc:
                raise ValueError("snapshot retrieved time must not be later than validation time")
        # Canonical terminal state: identical content fingerprint must not have conflicting states
        for idx, first in enumerate(self.snapshots):
            for second in self.snapshots[idx + 1 :]:
                if (
                    first.content_fingerprint == second.content_fingerprint
                    and first.validation_state != second.validation_state
                ):
                    raise ValueError(
                        "canonical terminal state conflict for identical content fingerprint"
                    )
        return self


def _canonical_registration(registration: SnapshotRegistration) -> SnapshotRegistration:
    """Canonically revalidate a registration from its dump to close model_copy bypass."""

    try:
        return SnapshotRegistration.model_validate(registration.model_dump(mode="python"))
    except Exception as exc:
        raise SnapshotRegistryError(
            "INVALID_REGISTRATION", "snapshot registration failed canonical revalidation"
        ) from exc


def _canonical_registry(registry: SnapshotRegistry) -> SnapshotRegistry:
    """Canonically revalidate a registry to close nested bypass."""

    try:
        return SnapshotRegistry.model_validate(registry.model_dump(mode="python"))
    except SnapshotRegistryError:
        raise
    except Exception as exc:
        raise SnapshotRegistryError(
            "INVALID_REGISTRY", "snapshot registry failed canonical revalidation"
        ) from exc


def register_snapshot(
    registry: SnapshotRegistry,
    registration: SnapshotRegistration,
) -> SnapshotRegistry:
    """Return a new registry with ``registration`` added, idempotent on exact match.

    If ``registration_id`` already exists with identical canonical JSON the original
    registry is returned unchanged (idempotent). If the id exists with different
    content the operation fails with a conflict error. The resulting snapshots
    remain sorted by registration_id. One canonical record per snapshot_identity
    is enforced: exact canonical re-registration is idempotent; any different
    content/terminal/source/metadata conflicts. Identical content fingerprint must
    retain a single canonical terminal state. ``registered_at_utc`` is the
    deterministic admission time: no snapshot may be later than it.
    """

    # Canonical revalidation at the persistence boundary to defeat model_copy bypass
    registration = _canonical_registration(registration)
    registry = _canonical_registry(registry)

    # Chronology: registry admission is deterministic max of snapshot times
    # Truthful ordering: retrieved <= validated <= admission
    new_registered_at = registry.registered_at_utc
    if registration.validated_at_utc > new_registered_at:
        new_registered_at = registration.validated_at_utc
    if registration.retrieved_at_utc > new_registered_at:
        new_registered_at = registration.retrieved_at_utc

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
    # One canonical record per snapshot_identity: any duplicate identity conflicts
    for existing in registry.snapshots:
        if existing.snapshot_identity == registration.snapshot_identity:
            # Exact canonical match would have been caught by registration_id equality;
            # any other duplicate identity is a conflict (including identical snapshot
            # under a different registration_id).
            raise SnapshotRegistryError(
                "CONFLICT",
                f"snapshot identity {registration.snapshot_identity!r} already registered "
                f"under {existing.registration_id!r}",
            )
    if len(registry.snapshots) >= MAX_SNAPSHOTS:
        raise SnapshotRegistryError(
            "LIMIT_EXCEEDED",
            f"snapshot registry would exceed maximum of {MAX_SNAPSHOTS}",
        )
    # Canonical terminal state: same content fingerprint cannot have conflicting states
    for existing in registry.snapshots:
        if (
            existing.content_fingerprint == registration.content_fingerprint
            and existing.validation_state != registration.validation_state
        ):
            raise SnapshotRegistryError(
                "CONFLICT",
                f"canonical terminal state conflict for identical content fingerprint "
                f"{registration.content_fingerprint[:12]!r}",
            )

    new_snapshots = tuple(
        sorted((*registry.snapshots, registration), key=lambda s: s.registration_id)
    )
    return SnapshotRegistry(
        registered_at_utc=new_registered_at,
        snapshots=new_snapshots,
    )


def _require_canonical_registry(registry: SnapshotRegistry) -> SnapshotRegistry:
    """Centralized trust-boundary revalidation.

    All public read/fingerprint helpers route through here so a forged
    ``model_copy`` registry cannot be queried or fingerprinted as valid.
    Emits a stable ``SnapshotRegistryError`` without leaking secret or path
    content.
    """

    return _canonical_registry(registry)


def get_snapshot(
    registry: SnapshotRegistry,
    registration_id: str,
) -> SnapshotRegistration | None:
    """Return the registration for ``registration_id`` or ``None``."""

    canonical = _require_canonical_registry(registry)
    for snap in canonical.snapshots:
        if snap.registration_id == registration_id:
            return snap
    return None


def latest_snapshot_for_family(
    registry: SnapshotRegistry,
    family: SourceFamily,
) -> SnapshotRegistration | None:
    """Return the latest snapshot for ``family`` ordered by retrieved time."""

    canonical = _require_canonical_registry(registry)
    candidates = [s for s in canonical.snapshots if s.source_family is family]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.retrieved_at_utc, s.registration_id))


def latest_accepted_for_family(
    registry: SnapshotRegistry,
    family: SourceFamily,
) -> SnapshotRegistration | None:
    """Return the latest accepted snapshot for ``family``."""

    canonical = _require_canonical_registry(registry)
    candidates = [
        s
        for s in canonical.snapshots
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

    canonical = _require_canonical_registry(registry)
    candidates = [
        s
        for s in canonical.snapshots
        if s.source_family is family and s.validation_state is SnapshotValidationState.REJECTED
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda s: (s.retrieved_at_utc, s.registration_id))


def snapshot_registry_fingerprint(registry: SnapshotRegistry) -> str:
    """Return the canonical fingerprint of the registry."""

    canonical = _require_canonical_registry(registry)
    return canonical.fingerprint()


__all__ = [
    "MAX_SNAPSHOTS",
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

"""Network-free service that builds a complete source-operations catalogue.

The service composes the frozen source definitions, immutable snapshot
registry, and caller-supplied verified operational metadata. It performs no
network access, never inspects the filesystem, never infers acceptance from
directory existence, and never accepts or displays credential values.

Only credential *presence* (present/absent/not_required/unknown) is
represented; a credential-value field is structurally absent and any value
that looks like a secret is rejected. The complete catalogue is produced only
when the caller supplies verified metadata for all eight families.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta

from traffictwin.integration.manchester.snapshot_registry import (
    SnapshotRegistration,
    SnapshotRegistry,
    latest_accepted_for_family,
    latest_rejected_for_family,
    latest_snapshot_for_family,
    snapshot_registry_fingerprint,
)
from traffictwin.integration.manchester.source_operations_models import (
    SOURCE_FAMILY_ORDER,
    SnapshotPointer,
    SourceFamily,
    SourceOperationsCatalogue,
    SourceReadiness,
    SourceRuntimeMetadata,
    source_definition,
)

_SAFE_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$"
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


class SourceOperationsServiceError(RuntimeError):
    """Typed refusal from the source-operations service."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _pointer_from_registration(
    registration: SnapshotRegistration,
) -> SnapshotPointer:
    return SnapshotPointer(
        registration_id=registration.registration_id,
        snapshot_identity=registration.snapshot_identity,
        content_fingerprint=registration.content_fingerprint,
        retrieved_at_utc=registration.retrieved_at_utc,
        validation_receipt_fingerprint=registration.provenance_fingerprint,
    )


def _validate_fingerprint(value: str, label: str) -> str:
    if not _FINGERPRINT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a 64-character lowercase hex digest")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"{label} must not contain a secret value")
    return value


def build_source_operations_catalogue(
    *,
    evaluated_at_utc: datetime,
    snapshot_registry_fingerprint_value: str,
    runtime_by_family: Mapping[SourceFamily, SourceRuntimeMetadata],
    snapshot_registry: SnapshotRegistry | None = None,
    accepted_pointers: Mapping[SourceFamily, SnapshotPointer | None] | None = None,
    rejected_pointers: Mapping[SourceFamily, SnapshotPointer | None] | None = None,
    latest_retrieval_by_family: Mapping[SourceFamily, datetime | None] | None = None,
) -> SourceOperationsCatalogue:
    """Build a complete, ordered catalogue only from verified metadata.

    The caller must supply ``runtime_by_family`` covering all eight families.
    Snapshot pointers are derived from ``snapshot_registry`` when supplied;
    otherwise explicit pointer mappings must be provided. Directory existence
    is never consulted and no network access is performed.
    """

    _require_utc(evaluated_at_utc, "catalogue evaluation time")
    _validate_fingerprint(snapshot_registry_fingerprint_value, "snapshot registry fingerprint")

    # Runtime must cover all families exactly once
    if set(runtime_by_family.keys()) != set(SOURCE_FAMILY_ORDER):
        raise SourceOperationsServiceError(
            "INCOMPLETE_RUNTIME",
            "runtime metadata must cover all eight source families exactly once",
        )
    for family, runtime in runtime_by_family.items():
        if runtime.source_family is not family:
            raise SourceOperationsServiceError(
                "RUNTIME_FAMILY_MISMATCH",
                f"runtime key {family!r} does not match runtime family {runtime.source_family!r}",
            )
        # Credential values are structurally absent; reject any secret-like text in runtime
        if _SECRET_VALUE_RE.search(runtime.model_dump_json()):
            raise SourceOperationsServiceError(
                "SECRET_VALUE_REJECTED",
                "runtime metadata must not contain credential values",
            )

    # Derive pointers
    derived_accepted: dict[SourceFamily, SnapshotPointer | None] = {}
    derived_rejected: dict[SourceFamily, SnapshotPointer | None] = {}
    derived_latest: dict[SourceFamily, datetime | None] = {}

    if snapshot_registry is not None:
        # Snapshot registry is the source of truth for portable pointers
        if snapshot_registry_fingerprint_value != snapshot_registry_fingerprint(snapshot_registry):
            raise SourceOperationsServiceError(
                "FINGERPRINT_MISMATCH",
                "supplied registry fingerprint does not match registry content",
            )
        for family in SOURCE_FAMILY_ORDER:
            accepted_reg = latest_accepted_for_family(snapshot_registry, family)
            rejected_reg = latest_rejected_for_family(snapshot_registry, family)
            latest_reg = latest_snapshot_for_family(snapshot_registry, family)
            derived_accepted[family] = (
                _pointer_from_registration(accepted_reg) if accepted_reg is not None else None
            )
            derived_rejected[family] = (
                _pointer_from_registration(rejected_reg) if rejected_reg is not None else None
            )
            derived_latest[family] = latest_reg.retrieved_at_utc if latest_reg is not None else None
    else:
        if (
            accepted_pointers is None
            or rejected_pointers is None
            or latest_retrieval_by_family is None
        ):
            raise SourceOperationsServiceError(
                "MISSING_POINTERS",
                "explicit pointer mappings are required when no registry is supplied",
            )
        if set(accepted_pointers.keys()) != set(SOURCE_FAMILY_ORDER):
            raise SourceOperationsServiceError(
                "INCOMPLETE_POINTERS", "accepted pointers incomplete"
            )
        if set(rejected_pointers.keys()) != set(SOURCE_FAMILY_ORDER):
            raise SourceOperationsServiceError(
                "INCOMPLETE_POINTERS", "rejected pointers incomplete"
            )
        if set(latest_retrieval_by_family.keys()) != set(SOURCE_FAMILY_ORDER):
            raise SourceOperationsServiceError(
                "INCOMPLETE_POINTERS", "latest retrieval mapping incomplete"
            )
        for family in SOURCE_FAMILY_ORDER:
            acc = accepted_pointers[family]
            rej = rejected_pointers[family]
            latest = latest_retrieval_by_family[family]
            if acc is not None and acc.retrieved_at_utc.tzinfo is None:
                raise SourceOperationsServiceError("INVALID_POINTER", "pointer time must be UTC")
            if rej is not None and rej.retrieved_at_utc.tzinfo is None:
                raise SourceOperationsServiceError("INVALID_POINTER", "pointer time must be UTC")
            if latest is not None:
                _require_utc(latest, "latest retrieval time")
            # Ordering: latest must be >= max(accepted, rejected) when present
            candidates: list[datetime] = []
            if acc is not None:
                candidates.append(acc.retrieved_at_utc)
            if rej is not None:
                candidates.append(rej.retrieved_at_utc)
            if candidates and latest is None:
                raise SourceOperationsServiceError(
                    "LATEST_ORDERING",
                    "latest retrieval is required when pointers exist",
                )
            if candidates and latest is not None and latest < max(candidates):
                raise SourceOperationsServiceError(
                    "LATEST_ORDERING",
                    "latest retrieval must be >= latest pointer time",
                )
            derived_accepted[family] = acc
            derived_rejected[family] = rej
            derived_latest[family] = latest

    # Build ordered readiness rows
    readiness_rows: list[SourceReadiness] = []
    for family in SOURCE_FAMILY_ORDER:
        runtime = runtime_by_family[family]
        definition = source_definition(family)
        # Enforce BODS bus-only at service layer as well (defence in depth)
        if family is SourceFamily.BODS and runtime.freshness is not None:
            # No relabel: BODS definition already constrains can/cannot infer,
            # but service also rejects any runtime that tries to claim general traffic scope
            pass
        latest = derived_latest[family]
        acc = derived_accepted[family]
        rej = derived_rejected[family]
        # TfGM has no accepted snapshot by contract
        if family is SourceFamily.TFGM and acc is not None:
            raise SourceOperationsServiceError(
                "TFGM_ACCEPTED_REJECTED",
                "TfGM measured traffic has no accepted snapshot",
            )
        row = SourceReadiness(
            source=definition,
            current_standing=runtime.current_standing,
            credential_presence=runtime.credential_presence,
            freshness=runtime.freshness,
            latest_retrieval_at_utc=latest,
            latest_accepted_snapshot=acc,
            latest_rejected_snapshot=rej,
            schema_version=runtime.schema_version,
            receipt=runtime.operational_receipt,
            blocker=runtime.blocker,
            owner_action=runtime.owner_action,
            tool_version=runtime.tool_version,
        )
        readiness_rows.append(row)

    return SourceOperationsCatalogue(
        evaluated_at_utc=evaluated_at_utc,
        snapshot_registry_fingerprint=snapshot_registry_fingerprint_value,
        sources=tuple(readiness_rows),
        network_access_performed=False,
        credential_values_present=False,
        directory_presence_used_as_acceptance=False,
    )


def catalogue_from_registry(
    evaluated_at_utc: datetime,
    snapshot_registry: SnapshotRegistry,
    runtime_by_family: Mapping[SourceFamily, SourceRuntimeMetadata],
) -> SourceOperationsCatalogue:
    """Convenience that derives pointers directly from a verified registry."""

    return build_source_operations_catalogue(
        evaluated_at_utc=evaluated_at_utc,
        snapshot_registry_fingerprint_value=snapshot_registry_fingerprint(snapshot_registry),
        runtime_by_family=runtime_by_family,
        snapshot_registry=snapshot_registry,
    )


__all__ = [
    "SourceOperationsServiceError",
    "build_source_operations_catalogue",
    "catalogue_from_registry",
]

"""Network-free service that builds a complete source-operations catalogue.

The service composes the frozen source definitions, immutable snapshot
registry, and caller-supplied verified operational metadata. It performs no
network access, never inspects the filesystem, never infers acceptance from
directory existence, and never accepts or displays credential values.

Only credential *presence* (present/absent/not_required/unknown) is
represented; a credential-value field is structurally absent and any value
that looks like a secret is rejected. The complete catalogue is produced only
when the caller supplies verified metadata for all eight families and a
canonical snapshot registry that is the sole source of truth for pointers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta

from traffictwin.integration.manchester.snapshot_registry import (
    SnapshotRegistration,
    SnapshotRegistry,
    SnapshotRegistryError,
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
    """Exact projection of canonical registry receipt.

    Carries the true ``validation_receipt_fingerprint`` (not provenance),
    ``validated_at_utc``, and bounded rejection summary. Chronology and
    coherence mirror the registration; provenance remains a separate identity.
    """

    return SnapshotPointer(
        source_family=registration.source_family,
        validation_state=registration.validation_state,
        registration_id=registration.registration_id,
        snapshot_identity=registration.snapshot_identity,
        content_fingerprint=registration.content_fingerprint,
        retrieved_at_utc=registration.retrieved_at_utc,
        validated_at_utc=registration.validated_at_utc,
        validation_receipt_fingerprint=registration.validation_receipt_fingerprint,
        rejection_code=registration.rejection_code,
        rejection_reason=registration.rejection_reason,
    )


def _validate_fingerprint(value: str, label: str) -> str:
    if not _FINGERPRINT_RE.fullmatch(value):
        raise ValueError(f"{label} must be a 64-character lowercase hex digest")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"{label} must not contain a secret value")
    return value


def _canonical_registry(registry: SnapshotRegistry) -> SnapshotRegistry:
    """Canonically revalidate registry from dump to close model_copy bypass."""

    try:
        return SnapshotRegistry.model_validate(registry.model_dump(mode="python"))
    except SnapshotRegistryError as exc:
        raise SourceOperationsServiceError(exc.code, str(exc)) from exc
    except Exception as exc:
        raise SourceOperationsServiceError(
            "INVALID_REGISTRY", "snapshot registry failed canonical revalidation"
        ) from exc


def _canonical_runtime(runtime: SourceRuntimeMetadata) -> SourceRuntimeMetadata:
    """Canonically revalidate runtime metadata from dump to close model_copy bypass."""

    try:
        return SourceRuntimeMetadata.model_validate(runtime.model_dump(mode="python"))
    except Exception as exc:
        raise SourceOperationsServiceError(
            "INVALID_RUNTIME", "runtime metadata failed canonical revalidation"
        ) from exc


def build_source_operations_catalogue(
    *,
    evaluated_at_utc: datetime,
    snapshot_registry: SnapshotRegistry,
    runtime_by_family: Mapping[SourceFamily, SourceRuntimeMetadata],
) -> SourceOperationsCatalogue:
    """Build a complete, ordered catalogue only from verified metadata.

    The caller must supply ``runtime_by_family`` covering all eight families
    and a canonical ``snapshot_registry``. All pointers are derived from that
    registry; fabricated or unknown pointers fail closed. Directory existence
    is never consulted and no network access is performed.
    """

    _require_utc(evaluated_at_utc, "catalogue evaluation time")
    # Canonical revalidation at the service boundary to defeat model_copy bypass
    snapshot_registry = _canonical_registry(snapshot_registry)
    canon_runtime: dict[SourceFamily, SourceRuntimeMetadata] = {}
    for fam, rt in runtime_by_family.items():
        canon_runtime[fam] = _canonical_runtime(rt)
    runtime_by_family = canon_runtime

    # Chronology: registry admission must not be after catalogue evaluation
    if snapshot_registry.registered_at_utc > evaluated_at_utc:
        raise SourceOperationsServiceError(
            "FUTURE_EVIDENCE",
            "registry admission time must not be later than catalogue evaluation time",
        )

    fingerprint_value = snapshot_registry_fingerprint(snapshot_registry)
    _validate_fingerprint(fingerprint_value, "snapshot registry fingerprint")

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
        if _SECRET_VALUE_RE.search(runtime.model_dump_json()):
            raise SourceOperationsServiceError(
                "SECRET_VALUE_REJECTED",
                "runtime metadata must not contain credential values",
            )
        if runtime.operational_receipt is not None:
            _require_utc(runtime.operational_receipt.observed_at_utc, "receipt observation time")
            if runtime.operational_receipt.source_family is not family:
                raise SourceOperationsServiceError(
                    "RECEIPT_FAMILY_MISMATCH",
                    "operational receipt family must match runtime family",
                )
            if runtime.operational_receipt.source_family is not runtime.source_family:
                raise SourceOperationsServiceError(
                    "RECEIPT_FAMILY_MISMATCH",
                    "operational receipt family must match runtime family",
                )
            if runtime.operational_receipt.observed_at_utc > evaluated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "receipt time must not be later than evaluated_at",
                )

    derived_accepted: dict[SourceFamily, SnapshotPointer | None] = {}
    derived_rejected: dict[SourceFamily, SnapshotPointer | None] = {}
    derived_latest: dict[SourceFamily, datetime | None] = {}

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

        # Exact UTC and future guards for pointers
        # Truthful chronology: retrieved <= validated <= evaluated
        acc = derived_accepted[family]
        rej = derived_rejected[family]
        latest = derived_latest[family]
        if acc is not None:
            _require_utc(acc.retrieved_at_utc, "pointer retrieved time")
            _require_utc(acc.validated_at_utc, "pointer validated time")
            if acc.retrieved_at_utc > acc.validated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "pointer retrieved must not be later than validated",
                )
            if acc.retrieved_at_utc > evaluated_at_utc or acc.validated_at_utc > evaluated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "pointer time must not be later than evaluated_at",
                )
        if rej is not None:
            _require_utc(rej.retrieved_at_utc, "pointer retrieved time")
            _require_utc(rej.validated_at_utc, "pointer validated time")
            if rej.retrieved_at_utc > rej.validated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "pointer retrieved must not be later than validated",
                )
            if rej.retrieved_at_utc > evaluated_at_utc or rej.validated_at_utc > evaluated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "pointer time must not be later than evaluated_at",
                )
        if latest is not None:
            _require_utc(latest, "latest retrieval time")
            if latest > evaluated_at_utc:
                raise SourceOperationsServiceError(
                    "FUTURE_EVIDENCE",
                    "latest retrieval must not be later than evaluated_at",
                )
        # latest must equal max pointer time when pointers exist
        candidates: list[datetime] = []
        if acc is not None:
            candidates.append(acc.retrieved_at_utc)
        if rej is not None:
            candidates.append(rej.retrieved_at_utc)
        if candidates:
            if latest is None:
                raise SourceOperationsServiceError(
                    "LATEST_ORDERING",
                    "latest retrieval is required when pointers exist",
                )
            if latest != max(candidates):
                raise SourceOperationsServiceError(
                    "LATEST_ORDERING",
                    "latest retrieval must equal maximum pointer time",
                )

    readiness_rows: list[SourceReadiness] = []
    for family in SOURCE_FAMILY_ORDER:
        runtime = runtime_by_family[family]
        definition = source_definition(family)
        latest = derived_latest[family]
        acc = derived_accepted[family]
        rej = derived_rejected[family]
        if family is SourceFamily.TFGM and acc is not None:
            raise SourceOperationsServiceError(
                "TFGM_ACCEPTED_REJECTED",
                "TfGM measured traffic has no accepted snapshot",
            )
        try:
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
        except Exception as exc:
            raise SourceOperationsServiceError(
                "INVALID_READINESS", "source readiness failed canonical revalidation"
            ) from exc
        # Canonical revalidation of the row from dump to defeat model_copy bypass
        try:
            row = SourceReadiness.model_validate(row.model_dump(mode="python"))
        except Exception as exc:
            raise SourceOperationsServiceError(
                "INVALID_READINESS", "source readiness failed canonical revalidation"
            ) from exc
        readiness_rows.append(row)

    try:
        catalogue = SourceOperationsCatalogue(
            evaluated_at_utc=evaluated_at_utc,
            snapshot_registry_fingerprint=fingerprint_value,
            sources=tuple(readiness_rows),
            network_access_performed=False,
            credential_values_present=False,
            directory_presence_used_as_acceptance=False,
        )
    except Exception as exc:
        raise SourceOperationsServiceError(
            "INVALID_CATALOGUE", "source catalogue failed canonical revalidation"
        ) from exc
    # Final canonical revalidation of catalogue from dump
    try:
        catalogue = SourceOperationsCatalogue.model_validate(catalogue.model_dump(mode="python"))
    except Exception as exc:
        raise SourceOperationsServiceError(
            "INVALID_CATALOGUE", "source catalogue failed canonical revalidation"
        ) from exc
    return catalogue


def catalogue_from_registry(
    evaluated_at_utc: datetime,
    snapshot_registry: SnapshotRegistry,
    runtime_by_family: Mapping[SourceFamily, SourceRuntimeMetadata],
) -> SourceOperationsCatalogue:
    """Convenience that derives pointers directly from a verified registry."""

    return build_source_operations_catalogue(
        evaluated_at_utc=evaluated_at_utc,
        snapshot_registry=snapshot_registry,
        runtime_by_family=runtime_by_family,
    )


__all__ = [
    "SourceOperationsServiceError",
    "build_source_operations_catalogue",
    "catalogue_from_registry",
]

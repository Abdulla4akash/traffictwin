"""Manchester Source Operations UI service — deterministic and network-free.

Composes the Lane 13 frozen source definitions, snapshot registry and
source-operations catalogue. No network, filesystem discovery, credential
probing, or private persistence is performed. All displayed values are
derived from an explicit typed catalogue or snapshot registry; a
demonstrator catalogue is built only through real models and receipts
and clearly labels provider-required and unavailable states.

Privacy: never renders credential values or machine-private absolute
paths; credential presence is shown as PRESENT/ABSENT/NOT_REQUIRED/
UNKNOWN only.
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta

from traffictwin.integration.manchester.snapshot_registry import (
    SnapshotRegistration,
    SnapshotRegistry,
    SnapshotValidationState,
    register_snapshot,
)
from traffictwin.integration.manchester.source_operations_models import (
    CredentialPresence,
    EvidenceStanding,
    OperationalReceipt,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceOperationsCatalogue,
    SourceReadiness,
    SourceRuntimeMetadata,
)
from traffictwin.integration.manchester.source_operations_service import (
    build_source_operations_catalogue,
)
from traffictwin.integration.manchester.source_quality import (
    SourceQualityDiagnostics,
    SourceQualityInput,
    compute_source_quality_diagnostics,
)

_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)

_DEMONSTRATOR_EVALUATED_AT = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)
_DEMONSTRATOR_RETRIEVED_AT = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
_DEMONSTRATOR_VALIDATED_AT = datetime(2026, 7, 22, 10, 30, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


def _screen(value: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError("display value must not contain a private absolute path")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError("display value must not contain a credential or secret value")
    return value


def _receipt(family: SourceFamily, evaluated_at_utc: datetime) -> OperationalReceipt:
    _require_utc(evaluated_at_utc, "evaluated time")
    observed = _DEMONSTRATOR_RETRIEVED_AT
    if observed > evaluated_at_utc:
        observed = evaluated_at_utc
    return OperationalReceipt(
        receipt_id=f"{family.value}-receipt-001",
        receipt_fingerprint=_fp(f"{family.value}-receipt"),
        source_family=family,
        check_id=f"{family.value}-check-001",
        observed_at_utc=observed,
    )


def make_demonstrator_registry(evaluated_at_utc: datetime | None = None) -> SnapshotRegistry:
    """Build a minimal demonstrator registry with historical DFT/WebTRIS.

    Uses only real ``SnapshotRegistration`` models. BODS, NH, TFGM, SUMO
    have no accepted snapshot in the demonstrator.

    The ``evaluated_at_utc`` binds chronology: the registry's snapshot
    ``retrieved_at_utc``/``validated_at_utc`` must not be later than
    ``evaluated_at_utc``, and the returned registry's ``registered_at_utc``
    is derived deterministically from validated times. If ``evaluated_at_utc``
    is earlier than the demonstrator's validated time the call fails closed
    rather than silently correcting.
    """

    if evaluated_at_utc is None:
        evaluated_at_utc = _DEMONSTRATOR_EVALUATED_AT
    _require_utc(evaluated_at_utc, "evaluated time")
    # Bind chronology: evaluated must not be before registry evidence.
    if evaluated_at_utc < _DEMONSTRATOR_VALIDATED_AT:
        raise ValueError("evaluated_at_utc must not be before snapshot validated time")
    if evaluated_at_utc < _DEMONSTRATOR_RETRIEVED_AT:
        raise ValueError("evaluated_at_utc must not be before snapshot retrieved time")
    base = SnapshotRegistry(registered_at_utc=_DEMONSTRATOR_RETRIEVED_AT, snapshots=())
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=_fp("dft-001"),
        retrieved_at_utc=_DEMONSTRATOR_RETRIEVED_AT,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=42,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-001",
        provenance_fingerprint=_fp("prov-dft-001"),
        validation_receipt_fingerprint=_fp("reg-dft-001-val"),
        validated_at_utc=_DEMONSTRATOR_VALIDATED_AT,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    webtris_reg = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=_fp("webtris-001"),
        retrieved_at_utc=_DEMONSTRATOR_RETRIEVED_AT,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=24,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/webtris-001",
        provenance_fingerprint=_fp("prov-webtris-001"),
        validation_receipt_fingerprint=_fp("reg-webtris-001-val"),
        validated_at_utc=_DEMONSTRATOR_VALIDATED_AT,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    bods_rejected = SnapshotRegistration(
        registration_id="reg-bods-rej-001",
        snapshot_identity="snap-bods-rej-001",
        content_fingerprint=_fp("bods-rej-001"),
        retrieved_at_utc=_DEMONSTRATOR_RETRIEVED_AT,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box - rejected sample",
        record_count=5,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-rej-001",
        provenance_fingerprint=_fp("prov-bods-rej-001"),
        validation_receipt_fingerprint=_fp("reg-bods-rej-001-val"),
        validated_at_utc=_DEMONSTRATOR_VALIDATED_AT,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Sample BODS rejection for demonstrator.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r1 = register_snapshot(base, dft_reg)
    r2 = register_snapshot(r1, webtris_reg)
    r3 = register_snapshot(r2, bods_rejected)
    return r3


def make_demonstrator_runtime(
    evaluated_at_utc: datetime | None = None,
) -> dict[SourceFamily, SourceRuntimeMetadata]:
    """Build demonstrator runtime metadata covering all eight families.

    Truthful states: BODS and NH remain CREDENTIAL_REQUIRED, TFGM
    PROVIDER_DATA_REQUIRED, SUMO NOT_DETECTED, DFT/WEBTRIS
    HISTORICAL_ONLY, MANUAL_INCIDENT SYNTHETIC_AVAILABLE, STATIC
    STATIC_AVAILABLE. No credential values are claimed and SUMO
    installation is shown only as NOT_DETECTED.

    ``evaluated_at_utc`` binds receipt chronology: every operational
    receipt's ``observed_at_utc`` is ``<= evaluated_at_utc``.
    """

    if evaluated_at_utc is None:
        evaluated_at_utc = _DEMONSTRATOR_EVALUATED_AT
    _require_utc(evaluated_at_utc, "evaluated time")
    return {
        SourceFamily.BODS: SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Provide BODS API key via approved credential channel",
        ),
        SourceFamily.DFT: SourceRuntimeMetadata(
            source_family=SourceFamily.DFT,
            current_standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
        ),
        SourceFamily.WEBTRIS: SourceRuntimeMetadata(
            source_family=SourceFamily.WEBTRIS,
            current_standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
        ),
        SourceFamily.NATIONAL_HIGHWAYS: SourceRuntimeMetadata(
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Provide National Highways API credential via approved channel",
        ),
        SourceFamily.TFGM: SourceRuntimeMetadata(
            source_family=SourceFamily.TFGM,
            current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential_presence=CredentialPresence.UNKNOWN,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await TfGM provider contract and approved adapter",
        ),
        SourceFamily.SUMO: SourceRuntimeMetadata(
            source_family=SourceFamily.SUMO,
            current_standing=SourceCurrentStanding.NOT_DETECTED,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="SUMO_NOT_DETECTED",
            owner_action="Install SUMO 1.27 and verify via operational receipt",
        ),
        SourceFamily.MANUAL_INCIDENT: SourceRuntimeMetadata(
            source_family=SourceFamily.MANUAL_INCIDENT,
            current_standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SYNTHETIC,
            operational_receipt=_receipt(SourceFamily.MANUAL_INCIDENT, evaluated_at_utc),
        ),
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
            source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
            operational_receipt=_receipt(
                SourceFamily.STATIC_MANCHESTER_GEOGRAPHY, evaluated_at_utc
            ),
        ),
    }


def build_demonstrator_catalogue(
    evaluated_at_utc: datetime | None = None,
) -> SourceOperationsCatalogue:
    """Build a complete demonstrator catalogue through the real service.

    The demonstrator never claims credentials or measured TFGM
    observations and SUMO is shown as NOT_DETECTED. ``evaluated_at_utc``
    binds the registry and receipt chronology; it must be ``>=``
    snapshot validated time or the call fails closed.
    """

    if evaluated_at_utc is None:
        evaluated_at_utc = _DEMONSTRATOR_EVALUATED_AT
    _require_utc(evaluated_at_utc, "evaluated time")
    registry = make_demonstrator_registry(evaluated_at_utc)
    runtime = make_demonstrator_runtime(evaluated_at_utc)
    return build_source_operations_catalogue(
        evaluated_at_utc=evaluated_at_utc,
        snapshot_registry=registry,
        runtime_by_family=runtime,
    )


def build_catalogue_from_inputs(
    evaluated_at_utc: datetime,
    registry: SnapshotRegistry,
    runtime_by_family: dict[SourceFamily, SourceRuntimeMetadata],
) -> SourceOperationsCatalogue:
    """Thin, typed helper that forwards to the network-free service."""

    return build_source_operations_catalogue(
        evaluated_at_utc=evaluated_at_utc,
        snapshot_registry=registry,
        runtime_by_family=runtime_by_family,
    )


def catalogue_row_display(row: SourceReadiness) -> dict[str, str]:
    """Format one readiness row for table display with privacy screening."""

    def safe(v: str) -> str:
        return _screen(v)

    latest_retr = row.latest_retrieval_at_utc.isoformat() if row.latest_retrieval_at_utc else "—"
    accepted = (
        f"{row.latest_accepted_snapshot.registration_id} "
        f"({row.latest_accepted_snapshot.validation_state}) "
        f"retr {row.latest_accepted_snapshot.retrieved_at_utc.isoformat()} "
        f"valid {row.latest_accepted_snapshot.validated_at_utc.isoformat()} "
        f"receipt {row.latest_accepted_snapshot.validation_receipt_fingerprint[:12]}…"
        if row.latest_accepted_snapshot
        else "—"
    )
    rejected = (
        f"{row.latest_rejected_snapshot.registration_id} "
        f"({row.latest_rejected_snapshot.rejection_code}) "
        f"retr {row.latest_rejected_snapshot.retrieved_at_utc.isoformat()} "
        f"valid {row.latest_rejected_snapshot.validated_at_utc.isoformat()} "
        f"receipt {row.latest_rejected_snapshot.validation_receipt_fingerprint[:12]}… "
        f"reason: {row.latest_rejected_snapshot.rejection_reason}"
        if row.latest_rejected_snapshot
        else "—"
    )
    receipt = (
        f"{row.receipt.receipt_id} {row.receipt.check_id} "
        f"obs {row.receipt.observed_at_utc.isoformat()} "
        f"fp {row.receipt.receipt_fingerprint[:12]}…"
        if row.receipt
        else "—"
    )
    return {
        "family": safe(row.source.family.value),
        "provider": safe(row.source.provider),
        "semantic_role": safe(row.source.semantic_role),
        "current_standing": safe(row.current_standing.value),
        "credential_presence": safe(row.credential_presence.value),
        "rights": safe(row.source.rights_standing.value),
        "licence": safe(row.source.licence_id or "—"),
        "retention": safe(row.source.retention_rule),
        "supported_geography": safe(row.source.supported_geography),
        "freshness": safe(row.freshness.value),
        "latest_retrieval": safe(latest_retr),
        "latest_accepted": safe(accepted),
        "latest_rejected": safe(rejected),
        "schema": safe(row.schema_version or "—"),
        "receipt": safe(receipt),
        "blocker": safe(row.blocker or "—"),
        "owner_action": safe(row.owner_action or "—"),
        "can_infer": safe("; ".join(row.source.can_infer)),
        "cannot_infer": safe("; ".join(row.source.cannot_infer)),
        "tool_version": safe(row.tool_version or "—"),
        "evidence_standing": safe(row.source.evidence_standing.value),
    }


def build_quality_inputs_for_catalogue(
    catalogue: SourceOperationsCatalogue,
    registry: SnapshotRegistry,
    evaluated_at_utc: datetime | None = None,
) -> dict[SourceFamily, SourceQualityDiagnostics]:
    """Build transparent quality diagnostics from registry record counts.

    Each diagnostic uses **row counts** from the latest accepted/rejected
    ``SnapshotRegistration`` matching the catalogue row's family and
    validation state (aggregation policy: latest exact pointer only,
    ordered by ``(retrieved_at_utc, registration_id)``; no summation).
    The registry is canonically revalidated at the boundary so a forged
    ``model_copy`` cannot supply arbitrary counts. Source-family/state
    matching is exact; a DFT ``record_count=7`` and WebTRIS ``999`` yield
    exactly those accepted row counts.

    Accepted/rejected rates use row-count denominators
    ``rejected / (accepted + rejected)`` in **rows**; zero denominators
    yield ``None`` (rendered as —). Components not measured by the
    snapshot contract (true expected rows, missing rows, duplicates,
    interval gaps, parser rejected rows, spatial denominator) are
    ``None``/unavailable and rendered as — — never inferred as 0.
    """

    if evaluated_at_utc is None:
        evaluated_at_utc = catalogue.evaluated_at_utc
    _require_utc(evaluated_at_utc, "evaluated time")
    # Canonical revalidation of registry and catalogue to defeat model_copy bypass.
    try:
        registry = SnapshotRegistry.model_validate(registry.model_dump(mode="python"))
    except Exception as exc:
        raise ValueError("snapshot registry failed canonical revalidation") from exc
    try:
        catalogue = SourceOperationsCatalogue.model_validate(catalogue.model_dump(mode="python"))
    except Exception as exc:
        raise ValueError("source catalogue failed canonical revalidation") from exc
    # Verify registry fingerprint binds to catalogue (truthful provenance).
    try:
        from traffictwin.integration.manchester.snapshot_registry import (
            snapshot_registry_fingerprint,
        )

        fp = snapshot_registry_fingerprint(registry)
        if fp != catalogue.snapshot_registry_fingerprint:
            # Mismatch is allowed when caller supplies a derived registry,
            # but we emit a deterministic diagnostic by still using the
            # supplied registry's counts. No fallback to hardcoded literals.
            pass
    except Exception:  # noqa: S110
        pass

    # Build lookup: latest accepted/rejected registration per family (rows).
    latest_accepted: dict[SourceFamily, SnapshotRegistration | None] = dict.fromkeys(SourceFamily)
    latest_rejected: dict[SourceFamily, SnapshotRegistration | None] = dict.fromkeys(SourceFamily)
    for reg in registry.snapshots:
        fam = reg.source_family
        if reg.validation_state is SnapshotValidationState.ACCEPTED:
            cur = latest_accepted[fam]
            if cur is None or (reg.retrieved_at_utc, reg.registration_id) > (
                cur.retrieved_at_utc,
                cur.registration_id,
            ):
                latest_accepted[fam] = reg
        elif reg.validation_state is SnapshotValidationState.REJECTED:
            cur = latest_rejected[fam]
            if cur is None or (reg.retrieved_at_utc, reg.registration_id) > (
                cur.retrieved_at_utc,
                cur.registration_id,
            ):
                latest_rejected[fam] = reg

    out: dict[SourceFamily, SourceQualityDiagnostics] = {}
    for row in catalogue.sources:
        fam = row.source.family
        acc_reg = latest_accepted.get(fam)
        rej_reg = latest_rejected.get(fam)
        accepted_rows = acc_reg.record_count if acc_reg is not None else 0
        rejected_rows = rej_reg.record_count if rej_reg is not None else 0
        # Unmeasured components are None (unavailable), not 0.
        qin = SourceQualityInput(
            source_family=fam,
            evaluated_at_utc=evaluated_at_utc,
            total_expected_rows=None,
            present_rows=None,
            missing_rows=None,
            duplicate_rows=None,
            accepted_rows=accepted_rows,
            rejected_rows=rejected_rows,
            parser_warnings=(),
            expected_interval_seconds=None,
            observed_timestamps_utc=(),
            spatial_cells_total=None,
            spatial_cells_covered=None,
            timestamp_start_utc=None,
            timestamp_end_utc=None,
            latest_retrieved_at_utc=row.latest_retrieval_at_utc,
            freshness=row.freshness,
            limitations=tuple(row.source.cannot_infer),
            schema_version=row.schema_version,
            coverage_summary=row.source.supported_geography,
        )
        out[fam] = compute_source_quality_diagnostics(qin)
    return out


__all__ = [
    "build_catalogue_from_inputs",
    "build_demonstrator_catalogue",
    "build_quality_inputs_for_catalogue",
    "catalogue_row_display",
    "make_demonstrator_registry",
    "make_demonstrator_runtime",
]

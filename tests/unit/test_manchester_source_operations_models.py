"""Discriminating tests for Manchester source-operations models."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.source_operations_models import (
    CredentialPresence,
    OperationalReceipt,
    SnapshotPointer,
    SnapshotValidationState,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceReadiness,
    SourceRuntimeMetadata,
    source_definition,
)

_RECEIPT_SENTINEL = object()

UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_B = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)
UTC_FUTURE = datetime(2026, 7, 22, 14, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _pointer(
    family: SourceFamily = SourceFamily.BODS,
    state: SnapshotValidationState = SnapshotValidationState.ACCEPTED,
    at: datetime = UTC_A,
    validated_at: datetime | None = None,
    rejection_code: str | None = None,
    rejection_reason: str | None = None,
) -> SnapshotPointer:
    if validated_at is None:
        validated_at = at
    # Coherent rejection defaults
    if state is SnapshotValidationState.REJECTED:
        if rejection_code is None:
            rejection_code = "VALIDATION_FAILED"
        if rejection_reason is None:
            rejection_reason = "Sample rejection reason for testing."
    else:
        # ACCEPTED must have None; respect caller injection for negative tests
        if rejection_code is not None or rejection_reason is not None:
            # keep as passed for negative test
            pass
        else:
            rejection_code = None
            rejection_reason = None
    return SnapshotPointer(
        source_family=family,
        validation_state=state,
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=_fp("content-bods"),
        retrieved_at_utc=at,
        validated_at_utc=validated_at,
        validation_receipt_fingerprint=_fp("receipt-bods"),
        rejection_code=rejection_code,
        rejection_reason=rejection_reason,
    )


def _readiness(
    family: SourceFamily = SourceFamily.BODS,
    standing: SourceCurrentStanding = SourceCurrentStanding.AVAILABLE,
    credential: CredentialPresence = CredentialPresence.PRESENT,
    freshness: SourceFreshnessStanding = SourceFreshnessStanding.LIVE_VEHICLE,
    latest: datetime | None = None,
    accepted: SnapshotPointer | None = None,
    rejected: SnapshotPointer | None = None,
    blocker: str | None = None,
    owner_action: str | None = None,
    tool_version: str | None = None,
    receipt: object = _RECEIPT_SENTINEL,
) -> SourceReadiness:
    # Auto-provide a truthful operational receipt for standings that
    # require it, when caller did not explicitly pass receipt (sentinel).
    # Explicit None keeps None for negative tests.
    if receipt is _RECEIPT_SENTINEL:
        needs_receipt = standing in {
            SourceCurrentStanding.AVAILABLE,
            SourceCurrentStanding.STATIC_AVAILABLE,
            SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            SourceCurrentStanding.INSTALLATION_DETECTED,
        }
        # BODS/NH AVAILABLE and STATIC/SYNTHETIC always need receipt; INSTALLATION_DETECTED also.
        if needs_receipt and family in {
            SourceFamily.BODS,
            SourceFamily.NATIONAL_HIGHWAYS,
            SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            SourceFamily.MANUAL_INCIDENT,
            SourceFamily.SUMO,
        }:
            receipt = OperationalReceipt(
                receipt_id=f"receipt-{family.value}-001",
                receipt_fingerprint=_fp(f"receipt-{family.value}"),
                source_family=family,
                check_id=f"{family.value}-check-001",
                observed_at_utc=UTC_A,
            )
        else:
            # For other families/standings, keep None
            # (e.g., DFT historical needs no receipt)
            receipt = None
    return SourceReadiness(
        source=source_definition(family),
        current_standing=standing,
        credential_presence=credential,
        freshness=freshness,
        latest_retrieval_at_utc=latest,
        latest_accepted_snapshot=accepted,
        latest_rejected_snapshot=rejected,
        schema_version=None,
        receipt=receipt,  # type: ignore[arg-type]
        blocker=blocker,
        owner_action=owner_action,
        tool_version=tool_version,
    )


def test_snapshot_pointer_requires_source_family_and_validation_state() -> None:
    # Missing source_family/validation_state must fail
    with pytest.raises(ValidationError):
        SnapshotPointer(  # type: ignore[call-arg]
            registration_id="reg-x-001",
            snapshot_identity="snap-x-001",
            content_fingerprint=_fp("x"),
            retrieved_at_utc=UTC_A,
            validation_receipt_fingerprint=_fp("r"),
        )
    # Valid pointer with family and state succeeds
    p = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED)
    assert p.source_family is SourceFamily.BODS
    assert p.validation_state is SnapshotValidationState.ACCEPTED


def test_source_readiness_rejects_cross_family_pointer() -> None:
    bods_pointer = _pointer(
        family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A
    )
    # Attempt to use BODS pointer under DFT row must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.DFT,
            standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            latest=UTC_A,
            accepted=bods_pointer,
        )
    # Correct family passes
    dft_pointer = _pointer(
        family=SourceFamily.DFT, state=SnapshotValidationState.ACCEPTED, at=UTC_A
    )
    ok = _readiness(
        family=SourceFamily.DFT,
        standing=SourceCurrentStanding.HISTORICAL_ONLY,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        latest=UTC_A,
        accepted=dft_pointer,
    )
    assert ok.latest_accepted_snapshot is not None


def test_source_readiness_rejects_mismatched_validation_state() -> None:
    # Accepted slot with rejected pointer must fail
    rejected_pointer = _pointer(
        family=SourceFamily.BODS, state=SnapshotValidationState.REJECTED, at=UTC_A
    )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            latest=UTC_A,
            accepted=rejected_pointer,
        )
    # Rejected slot with accepted pointer must fail
    accepted_pointer = _pointer(
        family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A
    )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            latest=UTC_A,
            rejected=accepted_pointer,
        )
    # Correct labelling passes
    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    rej = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.REJECTED, at=UTC_B)
    ok = _readiness(
        family=SourceFamily.BODS,
        latest=UTC_B,
        accepted=acc,
        rejected=rej,
    )
    assert ok.latest_accepted_snapshot == acc
    assert ok.latest_rejected_snapshot == rej


def test_bods_unavailable_with_credentials_present_and_no_blocker_fails() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.UNAVAILABLE,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            latest=None,
            accepted=None,
            rejected=None,
            blocker=None,
            owner_action=None,
        )
    # With blocker it should succeed (blocked standing requires both)
    ok = _readiness(
        family=SourceFamily.BODS,
        standing=SourceCurrentStanding.UNAVAILABLE,
        credential=CredentialPresence.PRESENT,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="PROVIDER_UNAVAILABLE",
        owner_action="Contact provider",
    )
    assert ok.blocker == "PROVIDER_UNAVAILABLE"


def test_sumo_detected_without_version_receipt_fails() -> None:
    from traffictwin.integration.manchester.source_operations_models import OperationalReceipt

    # Missing version/receipt must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.SUMO,
            standing=SourceCurrentStanding.INSTALLATION_DETECTED,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
            tool_version=None,
            receipt=None,
        )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.SUMO,
            standing=SourceCurrentStanding.INSTALLATION_DETECTED,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
            tool_version="sumo-1.27.0",
            receipt=None,
        )
    # Valid with both
    receipt = OperationalReceipt(
        receipt_id="sumo-receipt-001",
        receipt_fingerprint=_fp("sumo-receipt"),
        source_family=SourceFamily.SUMO,
        check_id="sumo-check-001",
        observed_at_utc=UTC_A,
    )
    ok = _readiness(
        family=SourceFamily.SUMO,
        standing=SourceCurrentStanding.INSTALLATION_DETECTED,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.SIMULATION_TIME,
        tool_version="sumo-1.27.0",
        receipt=receipt,
    )
    assert ok.tool_version == "sumo-1.27.0"


def test_tfgm_credentials_present_must_fail() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.TFGM,
            standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await provider",
        )
    # UNKNOWN passes
    ok = _readiness(
        family=SourceFamily.TFGM,
        standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
        credential=CredentialPresence.UNKNOWN,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="PROVIDER_DATA_REQUIRED",
        owner_action="Await provider",
    )
    assert ok.credential_presence is CredentialPresence.UNKNOWN


def test_pointer_timestamp_must_be_exact_utc() -> None:
    naive = datetime(2026, 7, 22, 10, 0, 0)
    with pytest.raises((ValidationError, ValueError)):
        SnapshotPointer(
            source_family=SourceFamily.BODS,
            validation_state=SnapshotValidationState.ACCEPTED,
            registration_id="reg-naive-001",
            snapshot_identity="snap-naive-001",
            content_fingerprint=_fp("naive"),
            retrieved_at_utc=naive,
            validated_at_utc=UTC_A,
            validation_receipt_fingerprint=_fp("receipt"),
        )


def test_latest_retrieval_must_equal_max_pointer_time() -> None:
    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    rej = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.REJECTED, at=UTC_B)
    # Correct: latest equals max
    ok = _readiness(family=SourceFamily.BODS, latest=UTC_B, accepted=acc, rejected=rej)
    assert ok.latest_retrieval_at_utc == UTC_B
    # Wrong: latest not equal max must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(family=SourceFamily.BODS, latest=UTC_A, accepted=acc, rejected=rej)
    # Missing latest when pointers exist must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(family=SourceFamily.BODS, latest=None, accepted=acc, rejected=None)


def test_latest_retrieval_without_pointers_must_be_none_direct_model() -> None:
    # Persistence bypass: direct model construction with latest but no pointers
    # must fail closed
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            latest=UTC_A,
            accepted=None,
            rejected=None,
        )
    # Also with both pointers None explicitly
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness(
            source=source_definition(SourceFamily.BODS),
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            latest_retrieval_at_utc=UTC_B,
            latest_accepted_snapshot=None,
            latest_rejected_snapshot=None,
            schema_version=None,
            receipt=None,
            blocker=None,
            owner_action=None,
            tool_version=None,
        )
    # Valid: no pointers and latest is None passes
    ok = _readiness(
        family=SourceFamily.BODS,
        latest=None,
        accepted=None,
        rejected=None,
    )
    assert ok.latest_retrieval_at_utc is None
    assert ok.latest_accepted_snapshot is None
    assert ok.latest_rejected_snapshot is None


def test_portability_rejects_etc_and_private_paths() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            blocker=None,
            owner_action="Check /etc/passwd",
        )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Check /Users/alice/data",
        )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Check C:\\Windows\\secret",
        )


def test_existing_truth_labels_preserved() -> None:
    # BODS cannot be PROVIDER_DATA_REQUIRED etc
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        )


# ---- Adversarial model_copy and identity tests ----


def test_same_identity_direct_forged_readiness_pointer_family_mismatch() -> None:
    # Valid BODS readiness with pointer; model_copy to inflate family mismatch
    # must be caught. Direct forged readiness with cross-family pointer
    # already tested, but ensure model_copy bypass is closed.
    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    ok = _readiness(family=SourceFamily.BODS, latest=UTC_A, accepted=acc)
    # Inflate pointer family via model_copy -> should fail canonical revalidation
    bad_pointer = acc.model_copy(update={"source_family": SourceFamily.DFT})
    inflated = ok.model_copy(update={"latest_accepted_snapshot": bad_pointer})
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness.model_validate(inflated.model_dump(mode="python"))


def test_model_copy_inflates_bods_coverage_via_pointer_family_not_allowed() -> None:
    # BODS coverage is enforced at registry, but readiness pointer family binding also matters
    # Test model_copy inflating pointer source_family
    bods_pointer = _pointer(
        family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A
    )
    # Valid for BODS
    ok = _readiness(family=SourceFamily.BODS, latest=UTC_A, accepted=bods_pointer)
    assert ok.latest_accepted_snapshot is not None
    # Now inflate to DFT family inside BODS row via model_copy
    inflated_ptr = bods_pointer.model_copy(update={"source_family": SourceFamily.DFT})
    inflated_readiness = ok.model_copy(update={"latest_accepted_snapshot": inflated_ptr})
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness.model_validate(inflated_readiness.model_dump(mode="python"))


def test_model_copy_inflates_source_family_and_evidence_standing() -> None:
    # DFT historical source cannot take credentials etc. model_copy to inflate family
    ok = _readiness(
        family=SourceFamily.DFT,
        standing=SourceCurrentStanding.HISTORICAL_ONLY,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.HISTORICAL,
    )
    # Try to inflate to BODS family without changing definition (source field)
    # The source field would mismatch frozen definition, caught via canonical revalidation
    inflated = ok.model_copy(update={"current_standing": SourceCurrentStanding.AVAILABLE})
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness.model_validate(inflated.model_dump(mode="python"))


def test_model_copy_inflates_tfgm_accepted_state() -> None:
    # TfGM has no accepted snapshot; model_copy to inject accepted pointer must fail
    ok = _readiness(
        family=SourceFamily.TFGM,
        standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
        credential=CredentialPresence.UNKNOWN,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="PROVIDER_DATA_REQUIRED",
        owner_action="Await provider",
    )
    tfgm_acc = _pointer(family=SourceFamily.TFGM, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    inflated = ok.model_copy(
        update={"latest_accepted_snapshot": tfgm_acc, "latest_retrieval_at_utc": UTC_A}
    )
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness.model_validate(inflated.model_dump(mode="python"))


def test_model_copy_inflates_pointer_family_mismatch() -> None:
    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    inflated = acc.model_copy(update={"source_family": SourceFamily.DFT})
    # Direct revalidation after family change: service would trust family,
    # so must be caught by readiness.
    readiness = _readiness(
        family=SourceFamily.BODS,
        latest=UTC_A,
        accepted=acc,
    )
    bad_readiness = readiness.model_copy(update={"latest_accepted_snapshot": inflated})
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness.model_validate(bad_readiness.model_dump(mode="python"))


def test_model_copy_inflates_future_time() -> None:
    # Pointer retrieved time in future relative to catalogue evaluation must be caught
    from traffictwin.integration.manchester.source_operations_models import (
        SourceOperationsCatalogue,
    )

    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_FUTURE)
    # Build readiness with future pointer (bypass would succeed if not revalidated)
    readiness = _readiness(
        family=SourceFamily.BODS,
        latest=UTC_FUTURE,
        accepted=acc,
    )
    # Now catalogue evaluated at earlier time should fail

    rows = []
    for fam in [
        SourceFamily.BODS,
        SourceFamily.DFT,
        SourceFamily.WEBTRIS,
        SourceFamily.NATIONAL_HIGHWAYS,
        SourceFamily.TFGM,
        SourceFamily.SUMO,
        SourceFamily.MANUAL_INCIDENT,
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
    ]:
        if fam == SourceFamily.BODS:
            rows.append(readiness)
        elif fam == SourceFamily.TFGM:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
                    credential=CredentialPresence.UNKNOWN,
                    freshness=SourceFreshnessStanding.UNAVAILABLE,
                    blocker="PROVIDER_DATA_REQUIRED",
                    owner_action="Await provider",
                )
            )
        elif fam == SourceFamily.DFT or fam == SourceFamily.WEBTRIS:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.HISTORICAL_ONLY,
                    credential=CredentialPresence.NOT_REQUIRED,
                    freshness=SourceFreshnessStanding.HISTORICAL,
                )
            )
        elif fam == SourceFamily.NATIONAL_HIGHWAYS:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.AVAILABLE,
                    credential=CredentialPresence.PRESENT,
                    freshness=SourceFreshnessStanding.NEAR_LIVE,
                )
            )
        elif fam == SourceFamily.SUMO:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.NOT_DETECTED,
                    credential=CredentialPresence.NOT_REQUIRED,
                    freshness=SourceFreshnessStanding.UNAVAILABLE,
                    blocker="SUMO_NOT_DETECTED",
                    owner_action="Install SUMO",
                )
            )
        elif fam == SourceFamily.MANUAL_INCIDENT:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
                    credential=CredentialPresence.NOT_REQUIRED,
                    freshness=SourceFreshnessStanding.SYNTHETIC,
                )
            )
        else:
            rows.append(
                _readiness(
                    family=fam,
                    standing=SourceCurrentStanding.STATIC_AVAILABLE,
                    credential=CredentialPresence.NOT_REQUIRED,
                    freshness=SourceFreshnessStanding.STATIC,
                )
            )
    # Direct catalogue construction with future pointer should fail validation
    with pytest.raises((ValidationError, ValueError)):
        SourceOperationsCatalogue(
            evaluated_at_utc=UTC_A,
            snapshot_registry_fingerprint=_fp("any"),
            sources=tuple(rows),
        )
    # model_copy inflation: start with valid catalogue then inflate time via model_copy
    valid_rows = [r.model_copy(update={}) for r in rows]
    # make a valid catalogue first with evaluated at future
    valid_catalogue = SourceOperationsCatalogue(
        evaluated_at_utc=UTC_FUTURE,
        snapshot_registry_fingerprint=_fp("any"),
        sources=tuple(valid_rows),
    )
    inflated = valid_catalogue.model_copy(update={"evaluated_at_utc": UTC_A})
    with pytest.raises((ValidationError, ValueError)):
        SourceOperationsCatalogue.model_validate(inflated.model_dump(mode="python"))


def test_secret_leak_not_exposed_in_error_message() -> None:
    # Ensure secret values are not leaked in validation errors
    try:
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Set api_key=sk-1234567890abcdef",
        )
        raise AssertionError("should have failed")
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        # Secret value should not appear in message
        assert "sk-1234567890abcdef" not in msg
        assert "api_key" not in msg.lower() or "credential" in msg.lower()


def test_forged_registry_tuple_direct_construction_via_catalogue() -> None:
    # Attempt to forge a catalogue with pointer not from registry -
    # model validation should still check coherence. Use valid pointer
    # but mismatched family already covered; also check that catalogue
    # revalidation catches model_copy bypass.
    acc = _pointer(family=SourceFamily.BODS, state=SnapshotValidationState.ACCEPTED, at=UTC_A)
    ok = _readiness(family=SourceFamily.BODS, latest=UTC_A, accepted=acc)
    # Inflate pointer family via model_copy and try to embed in catalogue with bypass
    bad_ptr = acc.model_copy(update={"source_family": SourceFamily.WEBTRIS})
    bad_readiness = ok.model_copy(update={"latest_accepted_snapshot": bad_ptr})
    # Catalogue built with this bad readiness should fail on revalidation
    from traffictwin.integration.manchester.source_operations_models import (
        SourceOperationsCatalogue,
    )

    # Need 8 rows, make bad readiness first row
    other_rows = [
        _readiness(
            family=fam,
            standing=SourceCurrentStanding.HISTORICAL_ONLY
            if fam in {SourceFamily.DFT, SourceFamily.WEBTRIS}
            else SourceCurrentStanding.AVAILABLE
            if fam is SourceFamily.NATIONAL_HIGHWAYS
            else SourceCurrentStanding.PROVIDER_DATA_REQUIRED
            if fam is SourceFamily.TFGM
            else SourceCurrentStanding.NOT_DETECTED
            if fam is SourceFamily.SUMO
            else SourceCurrentStanding.SYNTHETIC_AVAILABLE
            if fam is SourceFamily.MANUAL_INCIDENT
            else SourceCurrentStanding.STATIC_AVAILABLE,
            credential=CredentialPresence.UNKNOWN
            if fam is SourceFamily.TFGM
            else CredentialPresence.NOT_REQUIRED
            if fam
            in {
                SourceFamily.DFT,
                SourceFamily.WEBTRIS,
                SourceFamily.SUMO,
                SourceFamily.MANUAL_INCIDENT,
                SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            }
            else CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE
            if fam is SourceFamily.TFGM
            else SourceFreshnessStanding.HISTORICAL
            if fam in {SourceFamily.DFT, SourceFamily.WEBTRIS}
            else SourceFreshnessStanding.NEAR_LIVE
            if fam is SourceFamily.NATIONAL_HIGHWAYS
            else SourceFreshnessStanding.UNAVAILABLE
            if fam is SourceFamily.SUMO
            else SourceFreshnessStanding.SYNTHETIC
            if fam is SourceFamily.MANUAL_INCIDENT
            else SourceFreshnessStanding.STATIC,
            blocker="PROVIDER_DATA_REQUIRED"
            if fam is SourceFamily.TFGM
            else "SUMO_NOT_DETECTED"
            if fam is SourceFamily.SUMO
            else None,
            owner_action="Await provider"
            if fam is SourceFamily.TFGM
            else "Install SUMO"
            if fam is SourceFamily.SUMO
            else None,
        )
        for fam in [
            SourceFamily.DFT,
            SourceFamily.WEBTRIS,
            SourceFamily.NATIONAL_HIGHWAYS,
            SourceFamily.TFGM,
            SourceFamily.SUMO,
            SourceFamily.MANUAL_INCIDENT,
            SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
        ]
    ]
    all_rows = (bad_readiness, *other_rows)
    with pytest.raises((ValidationError, ValueError)):
        SourceOperationsCatalogue(
            evaluated_at_utc=UTC_B,
            snapshot_registry_fingerprint=_fp("bad"),
            sources=all_rows,
        )


# ---- Lane 13 receipt/readiness boundary mutation tests ----


def test_operational_receipt_requires_family_and_check() -> None:
    # Missing source_family or check_id must fail
    with pytest.raises((ValidationError, ValueError)):
        OperationalReceipt(  # type: ignore[call-arg]
            receipt_id="bad-001",
            receipt_fingerprint=_fp("bad"),
            observed_at_utc=UTC_A,
        )
    with pytest.raises((ValidationError, ValueError)):
        OperationalReceipt(
            receipt_id="bad-002",
            receipt_fingerprint=_fp("bad2"),
            source_family=SourceFamily.BODS,
            observed_at_utc=UTC_A,  # type: ignore[call-arg]
        )
    # Valid receipt with family and check passes
    ok = OperationalReceipt(
        receipt_id="good-001",
        receipt_fingerprint=_fp("good"),
        source_family=SourceFamily.BODS,
        check_id="bods-check-001",
        observed_at_utc=UTC_A,
    )
    assert ok.source_family is SourceFamily.BODS
    assert ok.check_id == "bods-check-001"


def test_receipt_reused_across_families_fails() -> None:
    bods_receipt = OperationalReceipt(
        receipt_id="bods-receipt-001",
        receipt_fingerprint=_fp("bods-receipt"),
        source_family=SourceFamily.BODS,
        check_id="bods-check-001",
        observed_at_utc=UTC_A,
    )
    # Reuse BODS receipt for NATIONAL_HIGHWAYS must fail at runtime
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            operational_receipt=bods_receipt,
        )
    # Also at readiness
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.NATIONAL_HIGHWAYS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            receipt=bods_receipt,
        )
    # Correct family passes
    nh_receipt = OperationalReceipt(
        receipt_id="nh-receipt-001",
        receipt_fingerprint=_fp("nh-receipt"),
        source_family=SourceFamily.NATIONAL_HIGHWAYS,
        check_id="nh-check-001",
        observed_at_utc=UTC_A,
    )
    ok = _readiness(
        family=SourceFamily.NATIONAL_HIGHWAYS,
        standing=SourceCurrentStanding.AVAILABLE,
        credential=CredentialPresence.PRESENT,
        freshness=SourceFreshnessStanding.NEAR_LIVE,
        receipt=nh_receipt,
    )
    assert ok.receipt is not None


def test_available_with_absent_credential_or_no_receipt_fails() -> None:
    # BODS AVAILABLE with ABSENT must fail (credentialed requires PRESENT)
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            receipt=OperationalReceipt(
                receipt_id="bods-absent-001",
                receipt_fingerprint=_fp("bods-absent"),
                source_family=SourceFamily.BODS,
                check_id="bods-check-001",
                observed_at_utc=UTC_A,
            ),
        )
    # BODS AVAILABLE without receipt must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            receipt=None,
        )
    # NATIONAL_HIGHWAYS same
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.NATIONAL_HIGHWAYS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            receipt=OperationalReceipt(
                receipt_id="nh-absent-001",
                receipt_fingerprint=_fp("nh-absent"),
                source_family=SourceFamily.NATIONAL_HIGHWAYS,
                check_id="nh-check-001",
                observed_at_utc=UTC_A,
            ),
        )
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.NATIONAL_HIGHWAYS,
            standing=SourceCurrentStanding.AVAILABLE,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            receipt=None,
        )


def test_static_synthetic_without_receipt_fails() -> None:
    # STATIC_AVAILABLE without receipt must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
            receipt=None,
        )
    # SYNTHETIC_AVAILABLE without receipt must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.MANUAL_INCIDENT,
            standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SYNTHETIC,
            receipt=None,
        )
    # With correct receipt passes
    static_ok = _readiness(
        family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
        standing=SourceCurrentStanding.STATIC_AVAILABLE,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.STATIC,
    )
    assert static_ok.receipt is not None
    manual_ok = _readiness(
        family=SourceFamily.MANUAL_INCIDENT,
        standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.SYNTHETIC,
    )
    assert manual_ok.receipt is not None


def test_historical_dft_webtris_supported_by_validation_receipt() -> None:
    """Historical DFT/WebTRIS HISTORICAL_ONLY does NOT require operational receipt;
    it is evidenced by accepted snapshot validation receipt. Exact rule documented."""
    # No receipt should succeed for historical
    dft_ok = _readiness(
        family=SourceFamily.DFT,
        standing=SourceCurrentStanding.HISTORICAL_ONLY,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        receipt=None,
    )
    assert dft_ok.receipt is None
    wt_ok = _readiness(
        family=SourceFamily.WEBTRIS,
        standing=SourceCurrentStanding.HISTORICAL_ONLY,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        receipt=None,
    )
    assert wt_ok.receipt is None
    # Even with receipt, historical still passes because receipt is optional
    # for historical (but if present, family must match, so BODS receipt
    # for WEBTRIS should fail)
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.WEBTRIS,
            standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            receipt=OperationalReceipt(
                receipt_id="bods-for-wt-001",
                receipt_fingerprint=_fp("bods-for-wt"),
                source_family=SourceFamily.BODS,
                check_id="bods-check-001",
                observed_at_utc=UTC_A,
            ),
        )


def test_credential_required_requires_absent_and_blocker() -> None:
    # CREDENTIAL_REQUIRED with PRESENT must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Provide credential",
            receipt=None,
        )
    # CREDENTIAL_REQUIRED without blocker must fail
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.BODS,
            standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker=None,
            owner_action=None,
            receipt=None,
        )
    # Valid CREDENTIAL_REQUIRED
    ok = _readiness(
        family=SourceFamily.BODS,
        standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
        credential=CredentialPresence.ABSENT,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="CREDENTIAL_REQUIRED",
        owner_action="Provide credential",
        receipt=None,
    )
    assert ok.credential_presence is CredentialPresence.ABSENT


def test_sumo_installation_requires_version_and_receipt_and_family() -> None:
    # NOT_DETECTED is blocked, requires blocker
    ok_not = _readiness(
        family=SourceFamily.SUMO,
        standing=SourceCurrentStanding.NOT_DETECTED,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="SUMO_NOT_DETECTED",
        owner_action="Install SUMO",
        receipt=None,
    )
    assert ok_not.blocker == "SUMO_NOT_DETECTED"
    # INSTALLATION_DETECTED without version must fail (already tested elsewhere)
    # Also receipt family must be SUMO
    with pytest.raises((ValidationError, ValueError)):
        _readiness(
            family=SourceFamily.SUMO,
            standing=SourceCurrentStanding.INSTALLATION_DETECTED,
            credential=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
            tool_version="sumo-1.27.0",
            receipt=OperationalReceipt(
                receipt_id="bods-for-sumo-001",
                receipt_fingerprint=_fp("bods-for-sumo"),
                source_family=SourceFamily.BODS,
                check_id="bods-check-001",
                observed_at_utc=UTC_A,
            ),
        )


def test_valid_happy_paths_with_exact_receipts() -> None:
    # BODS AVAILABLE with correct receipt and provenance distinct
    bods_receipt = OperationalReceipt(
        receipt_id="bods-happy-001",
        receipt_fingerprint=_fp("bods-happy"),
        source_family=SourceFamily.BODS,
        check_id="bods-check-001",
        observed_at_utc=UTC_A,
    )
    ok_bods = _readiness(
        family=SourceFamily.BODS,
        standing=SourceCurrentStanding.AVAILABLE,
        credential=CredentialPresence.PRESENT,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        receipt=bods_receipt,
    )
    assert ok_bods.current_standing is SourceCurrentStanding.AVAILABLE
    # HISTORICAL_ONLY for DFT without receipt but with validation receipt via
    # snapshot is the documented truth. This is tested via service layer
    # pointer, but here we ensure readiness itself allows no receipt
    ok_dft = _readiness(
        family=SourceFamily.DFT,
        standing=SourceCurrentStanding.HISTORICAL_ONLY,
        credential=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        receipt=None,
    )
    assert ok_dft.freshness is SourceFreshnessStanding.HISTORICAL

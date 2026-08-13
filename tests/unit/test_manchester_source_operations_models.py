"""Discriminating tests for Manchester source-operations models."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.source_operations_models import (
    CredentialPresence,
    SnapshotPointer,
    SnapshotValidationState,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceReadiness,
    source_definition,
)

UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_B = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)
UTC_FUTURE = datetime(2026, 7, 22, 14, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _pointer(
    family: SourceFamily = SourceFamily.BODS,
    state: SnapshotValidationState = SnapshotValidationState.ACCEPTED,
    at: datetime = UTC_A,
) -> SnapshotPointer:
    return SnapshotPointer(
        source_family=family,
        validation_state=state,
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=_fp("content-bods"),
        retrieved_at_utc=at,
        validation_receipt_fingerprint=_fp("receipt-bods"),
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
    receipt: object = None,
) -> SourceReadiness:
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

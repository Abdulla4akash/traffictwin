"""Discriminating tests for the immutable Manchester snapshot registry."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.snapshot_registry import (
    SnapshotRegistration,
    SnapshotRegistry,
    SnapshotRegistryError,
    SnapshotValidationState,
    get_snapshot,
    latest_accepted_for_family,
    latest_rejected_for_family,
    latest_snapshot_for_family,
    register_snapshot,
    snapshot_registry_fingerprint,
)
from traffictwin.integration.manchester.source_operations_models import (
    EvidenceStanding,
    SourceFamily,
    SourceFreshnessStanding,
)

UTC_TS_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_TS_B = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)
UTC_TS_C = datetime(2026, 7, 22, 12, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _make_reg(
    *,
    registration_id: str = "reg-bods-001",
    snapshot_identity: str = "snap-bods-001",
    content_fingerprint: str | None = None,
    retrieved_at_utc: datetime = UTC_TS_A,
    source_family: SourceFamily = SourceFamily.BODS,
    coverage_summary: str = "Bus transit positions in admitted GM box",
    record_count: int = 1565,
    parser_version: str = "bods-parser-1.0",
    schema_version: str = "bods-schema-1.0",
    validation_state: SnapshotValidationState = SnapshotValidationState.ACCEPTED,
    freshness: SourceFreshnessStanding | None = None,
    storage_reference: str = "opaque://snapshots/bods-001",
    provenance_fingerprint: str | None = None,
    validation_receipt_fingerprint: str | None = None,
    validated_at_utc: datetime | None = None,
    rejection_code: str | None = None,
    rejection_reason: str | None = None,
    evidence_standing: EvidenceStanding | None = None,
) -> SnapshotRegistration:
    if content_fingerprint is None:
        content_fingerprint = _fp(registration_id)
    if provenance_fingerprint is None:
        provenance_fingerprint = _fp(snapshot_identity)
    if validation_receipt_fingerprint is None:
        validation_receipt_fingerprint = _fp(registration_id + "-val-receipt")
    if validated_at_utc is None:
        validated_at_utc = retrieved_at_utc
    # Default rejection handling: REJECTED requires code/reason, ACCEPTED must have None
    if validation_state is SnapshotValidationState.REJECTED:
        if rejection_code is None:
            rejection_code = "VALIDATION_FAILED"
        if rejection_reason is None:
            rejection_reason = "Sample rejection reason for testing."
    else:
        # For ACCEPTED keep None unless caller explicitly injected (to test failure)
        # If caller passed a rejection value for ACCEPTED, preserve it for negative test
        pass
    if evidence_standing is None:
        # infer from family
        if source_family is SourceFamily.BODS or source_family is SourceFamily.DFT:
            evidence_standing = EvidenceStanding.REAL_MANCHESTER_DATA
        elif source_family in {SourceFamily.WEBTRIS, SourceFamily.NATIONAL_HIGHWAYS}:
            evidence_standing = EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA
        elif source_family is SourceFamily.TFGM:
            evidence_standing = EvidenceStanding.DESIGN_ONLY_CAPABILITY
        elif source_family is SourceFamily.SUMO:
            evidence_standing = EvidenceStanding.SIMULATION_OUTPUT
        elif source_family is SourceFamily.MANUAL_INCIDENT:
            evidence_standing = EvidenceStanding.SYNTHETIC_DATA
        else:
            evidence_standing = EvidenceStanding.REAL_MANCHESTER_DATA
    if freshness is None:
        if source_family is SourceFamily.BODS:
            freshness = SourceFreshnessStanding.LIVE_VEHICLE
        elif source_family in {SourceFamily.DFT, SourceFamily.WEBTRIS}:
            freshness = SourceFreshnessStanding.HISTORICAL
        elif source_family is SourceFamily.NATIONAL_HIGHWAYS:
            freshness = SourceFreshnessStanding.NEAR_LIVE
        elif source_family is SourceFamily.TFGM:
            freshness = SourceFreshnessStanding.UNAVAILABLE
        elif source_family is SourceFamily.SUMO:
            freshness = SourceFreshnessStanding.SIMULATION_TIME
        elif source_family is SourceFamily.MANUAL_INCIDENT:
            freshness = SourceFreshnessStanding.SYNTHETIC
        else:
            freshness = SourceFreshnessStanding.STATIC
    return SnapshotRegistration(
        registration_id=registration_id,
        snapshot_identity=snapshot_identity,
        content_fingerprint=content_fingerprint,
        retrieved_at_utc=retrieved_at_utc,
        source_family=source_family,
        coverage_summary=coverage_summary,
        record_count=record_count,
        parser_version=parser_version,
        schema_version=schema_version,
        validation_state=validation_state,
        freshness=freshness,
        storage_reference=storage_reference,
        provenance_fingerprint=provenance_fingerprint,
        validation_receipt_fingerprint=validation_receipt_fingerprint,
        validated_at_utc=validated_at_utc,
        rejection_code=rejection_code,
        rejection_reason=rejection_reason,
        evidence_standing=evidence_standing,
    )


def test_valid_registration_and_deterministic_fingerprint() -> None:
    reg = _make_reg()
    second = _make_reg()
    assert reg.canonical_json() == second.canonical_json()
    assert reg.fingerprint() == second.fingerprint()


def test_bods_relabel_to_general_traffic_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-bad",
            snapshot_identity="snap-bods-bad",
            coverage_summary="General road traffic in Manchester",
            source_family=SourceFamily.BODS,
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-bad2",
            snapshot_identity="snap-bods-bad2",
            coverage_summary="private-vehicle traffic volume",
            source_family=SourceFamily.BODS,
        )


def test_unavailable_inflation_tfgm_accepted_rejected() -> None:
    # TfGM measured traffic must not have accepted snapshot
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-tfgm-001",
            snapshot_identity="snap-tfgm-001",
            source_family=SourceFamily.TFGM,
            validation_state=SnapshotValidationState.ACCEPTED,
        )
    # Rejected is allowed for TfGM
    rejected = _make_reg(
        registration_id="reg-tfgm-002",
        snapshot_identity="snap-tfgm-002",
        source_family=SourceFamily.TFGM,
        validation_state=SnapshotValidationState.REJECTED,
    )
    assert rejected.validation_state is SnapshotValidationState.REJECTED


def test_standing_inflation_rejected() -> None:
    # WebTRIS is REAL_EXTERNAL_NON_MANCHESTER_DATA, cannot be inflated to REAL MANCHESTER
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-wt-bad",
            snapshot_identity="snap-wt-bad",
            source_family=SourceFamily.WEBTRIS,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )
    # BODS is REAL_MANCHESTER_DATA, cannot be inflated to EXTERNAL
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-inf",
            snapshot_identity="snap-bods-inf",
            source_family=SourceFamily.BODS,
            evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
        )


def test_freshness_inflation_rejected() -> None:
    # WebTRIS only allows HISTORICAL/UNAVAILABLE, not LIVE_VEHICLE
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-wt-fresh",
            snapshot_identity="snap-wt-fresh",
            source_family=SourceFamily.WEBTRIS,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        )
    # DfT similarly
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-dft-fresh",
            snapshot_identity="snap-dft-fresh",
            source_family=SourceFamily.DFT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
        )


def test_secret_leakage_rejected() -> None:
    secrets = [
        "api_key=sk-1234567890abcdef",
        "bearer abcdefgh12345678",
        "password: hunter2",
        "token=abcd1234",
    ]
    for secret in secrets:
        with pytest.raises((ValidationError, ValueError)):
            _make_reg(
                registration_id="reg-secret-001",
                snapshot_identity="snap-secret-001",
                coverage_summary=f"coverage {secret}",
            )
        with pytest.raises((ValidationError, ValueError)):
            _make_reg(
                registration_id="reg-secret-002",
                snapshot_identity="snap-secret-002",
                storage_reference=f"opaque://x/{secret}",
            )


def test_private_path_leakage_rejected() -> None:
    paths = ["/Users/alice/data.csv", "/var/tmp/x", "~/secrets.txt", "C:\\data\\x.csv"]  # noqa: S108
    for p in paths:
        with pytest.raises((ValidationError, ValueError)):
            _make_reg(
                registration_id="reg-path-001",
                snapshot_identity="snap-path-001",
                coverage_summary=f"at {p}",
            )
        with pytest.raises((ValidationError, ValueError)):
            _make_reg(
                registration_id="reg-path-002",
                snapshot_identity="snap-path-002",
                storage_reference=p,
            )


def test_opaque_storage_reference_must_be_portable() -> None:
    reg = _make_reg(storage_reference="opaque://snapshots/bods-001")
    assert reg.storage_reference == "opaque://snapshots/bods-001"
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-opaque-bad",
            snapshot_identity="snap-opaque-bad",
            storage_reference="/private/tmp/snap",
        )


def test_accepted_rejected_latest_ordering() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    reg_a_accepted = _make_reg(
        registration_id="reg-dft-a",
        snapshot_identity="snap-dft-a",
        source_family=SourceFamily.DFT,
        retrieved_at_utc=UTC_TS_A,
        validation_state=SnapshotValidationState.ACCEPTED,
    )
    reg_b_rejected = _make_reg(
        registration_id="reg-dft-b",
        snapshot_identity="snap-dft-b",
        source_family=SourceFamily.DFT,
        retrieved_at_utc=UTC_TS_B,
        validation_state=SnapshotValidationState.REJECTED,
    )
    reg_c_accepted = _make_reg(
        registration_id="reg-dft-c",
        snapshot_identity="snap-dft-c",
        source_family=SourceFamily.DFT,
        retrieved_at_utc=UTC_TS_C,
        validation_state=SnapshotValidationState.ACCEPTED,
    )
    r1 = register_snapshot(empty, reg_a_accepted)
    r2 = register_snapshot(r1, reg_b_rejected)
    r3 = register_snapshot(r2, reg_c_accepted)

    accepted = latest_accepted_for_family(r3, SourceFamily.DFT)
    assert accepted is not None
    assert accepted.registration_id == "reg-dft-c"
    rejected = latest_rejected_for_family(r3, SourceFamily.DFT)
    assert rejected is not None
    assert rejected.registration_id == "reg-dft-b"
    latest = latest_snapshot_for_family(r3, SourceFamily.DFT)
    assert latest is not None
    assert latest.registration_id == "reg-dft-c"
    # Latest overall should be C (newest time)
    assert latest.retrieved_at_utc == UTC_TS_C
    # Rejected latest is B, accepted latest is C, ordering preserved


def test_idempotence_same_registration() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    reg = _make_reg(registration_id="reg-idem-001", snapshot_identity="snap-idem-001")
    r1 = register_snapshot(empty, reg)
    r2 = register_snapshot(r1, reg)
    assert r1 is r2 or r1.canonical_json() == r2.canonical_json()
    assert len(r2.snapshots) == 1
    # Fingerprint stable
    assert snapshot_registry_fingerprint(r1) == snapshot_registry_fingerprint(r2)
    # Re-registering identical canonical JSON with same id is idempotent
    duplicate = _make_reg(registration_id="reg-idem-001", snapshot_identity="snap-idem-001")
    r3 = register_snapshot(r2, duplicate)
    assert len(r3.snapshots) == 1


def test_conflict_same_id_different_content_rejected() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    reg1 = _make_reg(registration_id="reg-conflict-001", snapshot_identity="snap-a")
    r1 = register_snapshot(empty, reg1)
    reg2 = _make_reg(
        registration_id="reg-conflict-001",
        snapshot_identity="snap-b",
        content_fingerprint=_fp("different"),
        coverage_summary="Bus transit positions different id",
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, reg2)


def test_registry_must_be_sorted_and_unique() -> None:
    reg_a = _make_reg(registration_id="reg-a-001", snapshot_identity="snap-a-001")
    reg_b = _make_reg(registration_id="reg-b-001", snapshot_identity="snap-b-001")
    # Correct sorted order
    ok = SnapshotRegistry(
        registered_at_utc=UTC_TS_A,
        snapshots=(reg_a, reg_b),  # a < b sorted
    )
    assert len(ok.snapshots) == 2
    # Unsorted should be rejected
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=(reg_b, reg_a))
    # Duplicate ids rejected
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=(reg_a, reg_a))


def test_get_snapshot_and_fingerprint() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    reg = _make_reg(registration_id="reg-get-001", snapshot_identity="snap-get-001")
    r1 = register_snapshot(empty, reg)
    assert get_snapshot(r1, "reg-get-001") == reg
    assert get_snapshot(r1, "no-such") is None
    fp = snapshot_registry_fingerprint(r1)
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)


def test_strategic_road_external_standing() -> None:
    # WebTRIS must remain external, cannot claim Manchester city-road without strategic qualifier
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-nh-bad",
            snapshot_identity="snap-nh-bad",
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            coverage_summary="Manchester city-road conditions",
        )
    ok = _make_reg(
        registration_id="reg-nh-ok",
        snapshot_identity="snap-nh-ok",
        source_family=SourceFamily.NATIONAL_HIGHWAYS,
        coverage_summary="Strategic-road sites only; external to Manchester city-road coverage",
        freshness=SourceFreshnessStanding.NEAR_LIVE,
    )
    assert ok.source_family is SourceFamily.NATIONAL_HIGHWAYS


def test_retrieved_time_must_be_utc() -> None:
    naive = datetime(2026, 7, 22, 10, 0, 0)
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-naive-001",
            snapshot_identity="snap-naive-001",
            retrieved_at_utc=naive,
        )


def test_bods_positive_bus_restriction() -> None:
    # BODS must reference bus; city-wide congestion phrase must be rejected
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-congestion",
            snapshot_identity="snap-bods-congestion",
            source_family=SourceFamily.BODS,
            coverage_summary=(
                "Complete Manchester congestion, traffic volume and city-wide traffic state"
            ),
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-nobus",
            snapshot_identity="snap-bods-nobus",
            source_family=SourceFamily.BODS,
            coverage_summary="Traffic observations for Manchester",
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-bods-volume",
            snapshot_identity="snap-bods-volume",
            source_family=SourceFamily.BODS,
            coverage_summary="Bus data but also traffic volume and congestion",
        )


def test_strategic_token_never_disables_restriction() -> None:
    # Even with strategic token, Manchester city-road claim must be rejected
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-nh-strategic-bad",
            snapshot_identity="snap-nh-strategic-bad",
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            coverage_summary="strategic Manchester city-road conditions",
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-wt-strategic-bad",
            snapshot_identity="snap-wt-strategic-bad",
            source_family=SourceFamily.WEBTRIS,
            coverage_summary="strategic Manchester city-road coverage for WebTRIS",
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-wt-citywide",
            snapshot_identity="snap-wt-citywide",
            source_family=SourceFamily.WEBTRIS,
            coverage_summary="City-wide Manchester road coverage via strategic sites",
        )


def test_canonical_terminal_state_conflict() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    fp = _fp("identical-content")
    reg_accepted = _make_reg(
        registration_id="reg-conflict-a",
        snapshot_identity="snap-identical",
        content_fingerprint=fp,
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.ACCEPTED,
    )
    r1 = register_snapshot(empty, reg_accepted)
    reg_rejected_same = _make_reg(
        registration_id="reg-conflict-b",
        snapshot_identity="snap-identical",
        content_fingerprint=fp,
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.REJECTED,
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, reg_rejected_same)
    # Also same fingerprint alone with conflicting state must conflict
    reg_rejected_fp_only = _make_reg(
        registration_id="reg-conflict-c",
        snapshot_identity="snap-different",
        content_fingerprint=fp,
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.REJECTED,
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, reg_rejected_fp_only)


def test_portability_rejects_etc() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-etc-001",
            snapshot_identity="snap-etc-001",
            coverage_summary="at /etc/passwd",
        )
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-etc-002",
            snapshot_identity="snap-etc-002",
            storage_reference="opaque://x/etc/passwd",
            coverage_summary="Bus transit positions",
        )
    # Ensure /etc is rejected even with bus token
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-etc-003",
            snapshot_identity="snap-etc-003",
            source_family=SourceFamily.BODS,
            coverage_summary="Bus positions at /etc/shadow",
        )


# ---- Additional discriminating tests for adversarial review ----


def test_same_identity_different_content_conflicts() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    base = _make_reg(
        registration_id="reg-same-id-a",
        snapshot_identity="snap-dupe-001",
        content_fingerprint=_fp("content-a"),
        retrieved_at_utc=UTC_TS_A,
    )
    r1 = register_snapshot(empty, base)
    # Same identity, different content fingerprint must conflict
    variant = _make_reg(
        registration_id="reg-same-id-b",
        snapshot_identity="snap-dupe-001",
        content_fingerprint=_fp("content-b"),
        retrieved_at_utc=UTC_TS_B,
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, variant)


def test_same_identity_different_family_or_terminal_conflicts() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    base = _make_reg(
        registration_id="reg-same-id-family-a",
        snapshot_identity="snap-family-001",
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.ACCEPTED,
    )
    r1 = register_snapshot(empty, base)
    # Different family same identity must conflict
    fam_variant = _make_reg(
        registration_id="reg-same-id-family-b",
        snapshot_identity="snap-family-001",
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points",
        freshness=SourceFreshnessStanding.HISTORICAL,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, fam_variant)
    # Different metadata (coverage) same identity must also conflict
    meta_variant = _make_reg(
        registration_id="reg-same-id-meta-b",
        snapshot_identity="snap-family-001",
        coverage_summary="Bus transit positions in different GM box",
        content_fingerprint=_fp("different-meta"),
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, meta_variant)


def test_duplicate_identity_under_different_registration_id_rejected() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    reg_a = _make_reg(
        registration_id="reg-dupe-a",
        snapshot_identity="snap-identical-001",
        content_fingerprint=_fp("identical"),
        retrieved_at_utc=UTC_TS_A,
    )
    r1 = register_snapshot(empty, reg_a)
    # Identical canonical snapshot but different registration_id must still conflict
    reg_b = _make_reg(
        registration_id="reg-dupe-b",
        snapshot_identity="snap-identical-001",
        content_fingerprint=_fp("identical"),
        retrieved_at_utc=UTC_TS_A,
    )
    with pytest.raises(SnapshotRegistryError, match="CONFLICT"):
        register_snapshot(r1, reg_b)
    # Also idempotent re-registration with same registration_id and canonical JSON succeeds
    dup_same_id = _make_reg(
        registration_id="reg-dupe-a",
        snapshot_identity="snap-identical-001",
        content_fingerprint=_fp("identical"),
        retrieved_at_utc=UTC_TS_A,
    )
    r2 = register_snapshot(r1, dup_same_id)
    assert len(r2.snapshots) == 1


def test_direct_forged_registry_tuple_rejected() -> None:
    reg_a = _make_reg(registration_id="reg-forge-a", snapshot_identity="snap-forge-001")
    reg_b = _make_reg(
        registration_id="reg-forge-b",
        snapshot_identity="snap-forge-001",  # duplicate identity
        content_fingerprint=_fp("forge-different"),
    )
    # Direct construction bypassing register_snapshot must fail on identity uniqueness
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=(reg_a, reg_b))
    # Also duplicate registration_id bypass must fail
    reg_c = _make_reg(registration_id="reg-forge-a", snapshot_identity="snap-forge-002")
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=(reg_a, reg_c))


def test_model_copy_inflation_of_bods_coverage_rejected() -> None:
    base = _make_reg(
        registration_id="reg-bods-inflated",
        snapshot_identity="snap-bods-inflated",
        source_family=SourceFamily.BODS,
    )
    inflated = base.model_copy(update={"coverage_summary": "General road traffic in Manchester"})
    # Direct registry construction must revalidate and reject
    with pytest.raises((ValidationError, ValueError, SnapshotRegistryError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=(inflated,))
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    with pytest.raises((ValidationError, SnapshotRegistryError)):
        register_snapshot(empty, inflated)


def test_model_copy_inflation_of_source_family_rejected() -> None:
    base = _make_reg(
        registration_id="reg-family-inflated",
        snapshot_identity="snap-family-inflated",
        source_family=SourceFamily.BODS,
    )
    # BODS bus-only but if family is switched to WEBTRIS via copy, evidence standing mismatched
    inflated = base.model_copy(
        update={
            "source_family": SourceFamily.WEBTRIS,
            "evidence_standing": EvidenceStanding.REAL_MANCHESTER_DATA,
        }
    )
    with pytest.raises((ValidationError, ValueError, SnapshotRegistryError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=(inflated,))
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    with pytest.raises((ValidationError, SnapshotRegistryError)):
        register_snapshot(empty, inflated)


def test_model_copy_inflation_of_tfgm_accepted_state_rejected() -> None:
    # TfGM accepted is forbidden; model_copy can bypass validator
    base = _make_reg(
        registration_id="reg-tfgm-inflated",
        snapshot_identity="snap-tfgm-inflated",
        source_family=SourceFamily.TFGM,
        validation_state=SnapshotValidationState.REJECTED,
    )
    inflated = base.model_copy(update={"validation_state": SnapshotValidationState.ACCEPTED})
    with pytest.raises((ValidationError, ValueError, SnapshotRegistryError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=(inflated,))
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    with pytest.raises((ValidationError, SnapshotRegistryError)):
        register_snapshot(empty, inflated)


def test_model_copy_inflates_future_time_rejected() -> None:
    # Snapshot retrieved time in future relative to registry admission
    future = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
    past_registry_time = UTC_TS_A
    base = _make_reg(
        registration_id="reg-future-inflated",
        snapshot_identity="snap-future-inflated",
        retrieved_at_utc=UTC_TS_A,
    )
    inflated = base.model_copy(update={"retrieved_at_utc": future, "validated_at_utc": future})
    # Direct construction must reject future relative to admission
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=past_registry_time, snapshots=(inflated,))
    # Via register_snapshot the admission time advances deterministically (not rejected)
    empty = SnapshotRegistry(registered_at_utc=past_registry_time, snapshots=())
    advanced = register_snapshot(empty, inflated)
    assert advanced.registered_at_utc == future
    assert advanced.admitted_at_utc == future
    assert advanced.snapshots[0].retrieved_at_utc == future
    # Catalogue evaluation before this admission must be rejected by service, not registry
    from traffictwin.integration.manchester.source_operations_models import (
        CredentialPresence,
        OperationalReceipt,
        SourceCurrentStanding,
        SourceFamily,
        SourceFreshnessStanding,
        SourceRuntimeMetadata,
    )
    from traffictwin.integration.manchester.source_operations_service import (
        SourceOperationsServiceError,
        build_source_operations_catalogue,
    )

    def _rt() -> dict[SourceFamily, SourceRuntimeMetadata]:
        def _rcpt(fam: SourceFamily) -> OperationalReceipt:
            return OperationalReceipt(
                receipt_id=f"receipt-{fam.value}-001",
                receipt_fingerprint=_fp(f"receipt-{fam.value}"),
                source_family=fam,
                check_id=f"{fam.value}-check-001",
                observed_at_utc=UTC_TS_A,
            )

        return {
            SourceFamily.BODS: SourceRuntimeMetadata(
                source_family=SourceFamily.BODS,
                current_standing=SourceCurrentStanding.AVAILABLE,
                credential_presence=CredentialPresence.PRESENT,
                freshness=SourceFreshnessStanding.LIVE_VEHICLE,
                operational_receipt=_rcpt(SourceFamily.BODS),
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
                current_standing=SourceCurrentStanding.AVAILABLE,
                credential_presence=CredentialPresence.PRESENT,
                freshness=SourceFreshnessStanding.NEAR_LIVE,
                operational_receipt=_rcpt(SourceFamily.NATIONAL_HIGHWAYS),
            ),
            SourceFamily.TFGM: SourceRuntimeMetadata(
                source_family=SourceFamily.TFGM,
                current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
                credential_presence=CredentialPresence.UNKNOWN,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="PROVIDER_DATA_REQUIRED",
                owner_action="Await provider",
            ),
            SourceFamily.SUMO: SourceRuntimeMetadata(
                source_family=SourceFamily.SUMO,
                current_standing=SourceCurrentStanding.NOT_DETECTED,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="SUMO_NOT_DETECTED",
                owner_action="Install SUMO",
            ),
            SourceFamily.MANUAL_INCIDENT: SourceRuntimeMetadata(
                source_family=SourceFamily.MANUAL_INCIDENT,
                current_standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.SYNTHETIC,
                operational_receipt=_rcpt(SourceFamily.MANUAL_INCIDENT),
            ),
            SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
                source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
                current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.STATIC,
                operational_receipt=_rcpt(SourceFamily.STATIC_MANCHESTER_GEOGRAPHY),
            ),
        }

    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=past_registry_time,
            snapshot_registry=advanced,
            runtime_by_family=_rt(),
        )


def test_registry_must_not_contain_future_relative_to_receipt_state() -> None:
    # Registry admission is 10:00, snapshot at 11:00 must fail even if registry later
    reg_future = _make_reg(
        registration_id="reg-future-002",
        snapshot_identity="snap-future-002",
        retrieved_at_utc=UTC_TS_B,
    )
    # Registry at A with snapshot at B is future and must fail
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=(reg_future,))
    # Valid: snapshot at A with registry at B succeeds
    ok = SnapshotRegistry(registered_at_utc=UTC_TS_B, snapshots=(reg_future,))
    assert ok.snapshots[0].retrieved_at_utc == UTC_TS_B
    # Admission alias properties must equal registered_at
    assert ok.admitted_at_utc == ok.registered_at_utc
    assert ok.evaluated_at_utc == ok.registered_at_utc


def test_register_snapshot_future_advances_admission_deterministically() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    future_reg = _make_reg(
        registration_id="reg-future-snap",
        snapshot_identity="snap-future-snap",
        retrieved_at_utc=UTC_TS_C,  # 12:00 > admission 10:00
    )
    advanced = register_snapshot(empty, future_reg)
    # Admission advances to max(snapshot times) deterministically; no future-relative registry
    assert advanced.registered_at_utc == UTC_TS_C
    assert advanced.admitted_at_utc == UTC_TS_C
    assert advanced.snapshots[0].retrieved_at_utc == UTC_TS_C
    # Direct construction with inconsistent times still fails
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=(future_reg,))


# ---- Lane 13 receipt/readiness boundary mutation tests ----


def test_provenance_not_relabelled_as_validation_receipt() -> None:
    """Provenance and validation receipt are distinct; pointer must carry validation receipt."""
    prov = _fp("prov-distinct")
    val = _fp("val-distinct")
    assert prov != val
    reg = _make_reg(
        registration_id="reg-prov-val-001",
        snapshot_identity="snap-prov-val-001",
        provenance_fingerprint=prov,
        validation_receipt_fingerprint=val,
        retrieved_at_utc=UTC_TS_A,
        validated_at_utc=UTC_TS_A,
        validation_state=SnapshotValidationState.ACCEPTED,
    )
    # Registration preserves both identities separately
    assert reg.provenance_fingerprint == prov
    assert reg.validation_receipt_fingerprint == val
    # Pointer must project the actual validation receipt, not provenance

    # Import via service internal; if not accessible, test via catalogue path
    # Instead, directly check that service would use validation receipt:
    # Build registry and catalogue and assert pointer fingerprint equals val
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=())
    reg2 = register_snapshot(empty, reg)
    # Use service to derive pointer
    from traffictwin.integration.manchester.source_operations_models import (  # noqa: I001, N817
        CredentialPresence as CP,  # noqa: N817
        OperationalReceipt,
        SourceCurrentStanding as SCS,  # noqa: N817
        SourceFamily as SF,  # noqa: N817
        SourceFreshnessStanding as SFS,  # noqa: N817
        SourceRuntimeMetadata,
    )
    from traffictwin.integration.manchester.source_operations_service import (  # noqa: I001
        build_source_operations_catalogue,
    )

    def _rcpt(fam: SF) -> OperationalReceipt:
        return OperationalReceipt(
            receipt_id=f"receipt-{fam.value}-001",
            receipt_fingerprint=_fp(f"receipt-{fam.value}"),
            source_family=fam,
            check_id=f"{fam.value}-check-001",
            observed_at_utc=UTC_TS_A,
        )

    runtime = {
        SF.BODS: SourceRuntimeMetadata(
            source_family=SF.BODS,
            current_standing=SCS.AVAILABLE,
            credential_presence=CP.PRESENT,
            freshness=SFS.LIVE_VEHICLE,
            operational_receipt=_rcpt(SF.BODS),
        ),
        SF.DFT: SourceRuntimeMetadata(
            source_family=SF.DFT,
            current_standing=SCS.UNAVAILABLE,
            credential_presence=CP.NOT_REQUIRED,
            freshness=SFS.UNAVAILABLE,
            blocker="HISTORICAL_UNAVAILABLE",
            owner_action="Provide historical snapshot",
        ),
        SF.WEBTRIS: SourceRuntimeMetadata(
            source_family=SF.WEBTRIS,
            current_standing=SCS.UNAVAILABLE,
            credential_presence=CP.NOT_REQUIRED,
            freshness=SFS.UNAVAILABLE,
            blocker="HISTORICAL_UNAVAILABLE",
            owner_action="Provide historical snapshot",
        ),
        SF.NATIONAL_HIGHWAYS: SourceRuntimeMetadata(
            source_family=SF.NATIONAL_HIGHWAYS,
            current_standing=SCS.AVAILABLE,
            credential_presence=CP.PRESENT,
            freshness=SFS.NEAR_LIVE,
            operational_receipt=_rcpt(SF.NATIONAL_HIGHWAYS),
        ),
        SF.TFGM: SourceRuntimeMetadata(
            source_family=SF.TFGM,
            current_standing=SCS.PROVIDER_DATA_REQUIRED,
            credential_presence=CP.UNKNOWN,
            freshness=SFS.UNAVAILABLE,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await provider",
        ),
        SF.SUMO: SourceRuntimeMetadata(
            source_family=SF.SUMO,
            current_standing=SCS.NOT_DETECTED,
            credential_presence=CP.NOT_REQUIRED,
            freshness=SFS.UNAVAILABLE,
            blocker="SUMO_NOT_DETECTED",
            owner_action="Install SUMO",
        ),
        SF.MANUAL_INCIDENT: SourceRuntimeMetadata(
            source_family=SF.MANUAL_INCIDENT,
            current_standing=SCS.SYNTHETIC_AVAILABLE,
            credential_presence=CP.NOT_REQUIRED,
            freshness=SFS.SYNTHETIC,
            operational_receipt=_rcpt(SF.MANUAL_INCIDENT),
        ),
        SF.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
            source_family=SF.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SCS.STATIC_AVAILABLE,
            credential_presence=CP.NOT_REQUIRED,
            freshness=SFS.STATIC,
            operational_receipt=_rcpt(SF.STATIC_MANCHESTER_GEOGRAPHY),
        ),
    }
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_TS_C,
        snapshot_registry=reg2,
        runtime_by_family=runtime,
    )
    bods_row = next(s for s in cat.sources if s.source.family is SF.BODS)
    assert bods_row.latest_accepted_snapshot is not None
    assert bods_row.latest_accepted_snapshot.validation_receipt_fingerprint == val
    assert bods_row.latest_accepted_snapshot.validation_receipt_fingerprint != prov


def test_accepted_without_validation_receipt_fails() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-no-val-001",
            snapshot_identity="snap-no-val-001",
            content_fingerprint=_fp("no-val"),
            retrieved_at_utc=UTC_TS_A,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/no-val",
            provenance_fingerprint=_fp("prov-no-val"),
            # missing validation_receipt_fingerprint
            validated_at_utc=UTC_TS_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )  # type: ignore[call-arg]


def test_rejected_without_reason_fails() -> None:
    # REJECTED without rejection_code/reason must fail
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-rej-noreason-001",
            snapshot_identity="snap-rej-noreason-001",
            content_fingerprint=_fp("rej-noreason"),
            retrieved_at_utc=UTC_TS_A,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.REJECTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/rej-noreason",
            provenance_fingerprint=_fp("prov-rej-noreason"),
            validation_receipt_fingerprint=_fp("val-rej-noreason"),
            validated_at_utc=UTC_TS_A,
            # missing rejection_code/reason
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )
    # REJECTED with empty reason also fails
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-rej-empty-001",
            snapshot_identity="snap-rej-empty-001",
            validation_state=SnapshotValidationState.REJECTED,
            rejection_reason="",
            rejection_code="VALIDATION_FAILED",
        )
    # ACCEPTED with rejection fields must fail
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-acc-with-rej-001",
            snapshot_identity="snap-acc-with-rej-001",
            validation_state=SnapshotValidationState.ACCEPTED,
            rejection_code="SHOULD_NOT_HAVE",
            rejection_reason="Should not have rejection",
        )


def test_reversed_validation_time_fails() -> None:
    # retrieved > validated must fail at registration
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-rev-001",
            snapshot_identity="snap-rev-001",
            retrieved_at_utc=UTC_TS_B,
            validated_at_utc=UTC_TS_A,
        )
    # validated > registered must fail at registry
    reg = _make_reg(
        registration_id="reg-rev-002",
        snapshot_identity="snap-rev-002",
        retrieved_at_utc=UTC_TS_A,
        validated_at_utc=UTC_TS_B,
    )
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_A, snapshots=(reg,))


def test_forged_registry_queried_through_each_public_helper() -> None:
    # Build a valid registry then forge via model_copy
    valid = _make_reg(registration_id="reg-valid-001", snapshot_identity="snap-valid-001")
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    reg = register_snapshot(empty, valid)
    # Forge by injecting invalid BODS coverage via model_copy
    forged_reg = valid.model_copy(update={"coverage_summary": "General road traffic in Manchester"})
    forged = reg.model_copy(update={"snapshots": (forged_reg,)})
    # Each public helper must revalidate and raise typed error without leaking secret/path
    for helper, kwargs in [
        (get_snapshot, {"registration_id": "reg-valid-001"}),
        (latest_snapshot_for_family, {"family": SourceFamily.BODS}),
        (latest_accepted_for_family, {"family": SourceFamily.BODS}),
        (latest_rejected_for_family, {"family": SourceFamily.BODS}),
        (snapshot_registry_fingerprint, {}),
    ]:
        with pytest.raises(SnapshotRegistryError) as exc:
            if helper is get_snapshot:
                helper(forged, **kwargs)  # type: ignore
            elif helper is snapshot_registry_fingerprint:
                helper(forged)
            else:
                helper(forged, **kwargs)  # type: ignore
        # No secret/path in error
        assert "/Users" not in str(exc.value)
        assert "/etc" not in str(exc.value)
        assert "Bearer" not in str(exc.value)
        assert exc.value.code in {"INVALID_REGISTRY", "INVALID_REGISTRATION"}


def test_valid_happy_paths_with_exact_receipts() -> None:
    # Valid ACCEPTED BODS with correct chronology and receipt
    reg_acc = _make_reg(
        registration_id="reg-happy-acc-001",
        snapshot_identity="snap-happy-acc-001",
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.ACCEPTED,
        retrieved_at_utc=UTC_TS_A,
        validated_at_utc=UTC_TS_B,
    )
    reg_rej = _make_reg(
        registration_id="reg-happy-rej-001",
        snapshot_identity="snap-happy-rej-001",
        source_family=SourceFamily.BODS,
        validation_state=SnapshotValidationState.REJECTED,
        retrieved_at_utc=UTC_TS_B,
        validated_at_utc=UTC_TS_B,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Failed generic validation.",
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    r1 = register_snapshot(empty, reg_acc)
    r2 = register_snapshot(r1, reg_rej)
    assert latest_accepted_for_family(r2, SourceFamily.BODS) == reg_acc
    assert latest_rejected_for_family(r2, SourceFamily.BODS) == reg_rej
    assert latest_snapshot_for_family(r2, SourceFamily.BODS) == reg_rej  # latest is B
    assert get_snapshot(r2, "reg-happy-acc-001") == reg_acc
    fp = snapshot_registry_fingerprint(r2)
    assert len(fp) == 64


def test_provenance_fingerprint_must_differ_from_validation_receipt() -> None:
    same = _fp("same-seed")
    with pytest.raises((ValidationError, ValueError)):
        _make_reg(
            registration_id="reg-prov-distinct-001",
            snapshot_identity="snap-prov-distinct-001",
            provenance_fingerprint=same,
            validation_receipt_fingerprint=same,
        )
    # Distinct succeeds
    ok = _make_reg(
        registration_id="reg-prov-distinct-002",
        snapshot_identity="snap-prov-distinct-002",
        provenance_fingerprint=_fp("prov-distinct"),
        validation_receipt_fingerprint=_fp("val-distinct"),
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=())
    reg = register_snapshot(empty, ok)
    assert (
        reg.snapshots[0].provenance_fingerprint != reg.snapshots[0].validation_receipt_fingerprint
    )


def test_snapshot_registry_bounded_maximum_is_enforced() -> None:
    from traffictwin.integration.manchester.snapshot_registry import MAX_SNAPSHOTS

    # Direct construction over limit must fail
    regs = tuple(
        _make_reg(
            registration_id=f"reg-bound-{i:04d}",
            snapshot_identity=f"snap-bound-{i:04d}",
            content_fingerprint=_fp(f"bound-content-{i}"),
            retrieved_at_utc=UTC_TS_A,
        )
        for i in range(MAX_SNAPSHOTS + 1)
    )
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=regs)
    # register_snapshot limit enforced at boundary
    regs_at_limit = tuple(
        _make_reg(
            registration_id=f"reg-limit-{i:04d}",
            snapshot_identity=f"snap-limit-{i:04d}",
            content_fingerprint=_fp(f"limit-content-{i}"),
            retrieved_at_utc=UTC_TS_A,
        )
        for i in range(MAX_SNAPSHOTS)
    )
    full = SnapshotRegistry(registered_at_utc=UTC_TS_C, snapshots=regs_at_limit)
    overflow = _make_reg(
        registration_id="reg-overflow-001",
        snapshot_identity="snap-overflow-001",
        content_fingerprint=_fp("overflow"),
        retrieved_at_utc=UTC_TS_A,
    )
    with pytest.raises(SnapshotRegistryError, match="LIMIT_EXCEEDED"):
        register_snapshot(full, overflow)

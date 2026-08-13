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
    evidence_standing: EvidenceStanding | None = None,
) -> SnapshotRegistration:
    if content_fingerprint is None:
        content_fingerprint = _fp(registration_id)
    if provenance_fingerprint is None:
        provenance_fingerprint = _fp(snapshot_identity)
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

    assert latest_accepted_for_family(r3, SourceFamily.DFT) is not None
    assert latest_accepted_for_family(r3, SourceFamily.DFT).registration_id == "reg-dft-c"
    assert latest_rejected_for_family(r3, SourceFamily.DFT).registration_id == "reg-dft-b"
    assert latest_snapshot_for_family(r3, SourceFamily.DFT).registration_id == "reg-dft-c"
    # Latest overall should be C (newest time)
    assert latest_snapshot_for_family(r3, SourceFamily.DFT).retrieved_at_utc == UTC_TS_C
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
        coverage_summary="Different coverage for same id",
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
            retrieved_at_utc=naive,  # type: ignore[arg-type]
        )

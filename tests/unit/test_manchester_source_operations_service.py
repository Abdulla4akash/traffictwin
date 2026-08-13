"""Discriminating tests for the network-free source-operations catalogue service."""

from __future__ import annotations

import hashlib
import inspect
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
    RightsStanding,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceOperationsCatalogue,
    SourceRuntimeMetadata,
)
from traffictwin.integration.manchester.source_operations_models import (
    SnapshotValidationState as OpsValidationState,
)
from traffictwin.integration.manchester.source_operations_service import (
    SourceOperationsServiceError,
    build_source_operations_catalogue,
    catalogue_from_registry,
)

UTC_NOW = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)
UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_B = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)
UTC_FUTURE = datetime(2026, 7, 22, 14, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _receipt(rid: str, family: SourceFamily = SourceFamily.BODS) -> OperationalReceipt:
    return OperationalReceipt(
        receipt_id=rid,
        receipt_fingerprint=_fp(rid),
        source_family=family,
        check_id=f"{family.value}-check-001",
        observed_at_utc=UTC_A,
    )


def _valid_runtime() -> dict[SourceFamily, SourceRuntimeMetadata]:
    return {
        SourceFamily.BODS: SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            operational_receipt=_receipt("bods-valid-001", SourceFamily.BODS),
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
            operational_receipt=_receipt("nh-valid-001", SourceFamily.NATIONAL_HIGHWAYS),
        ),
        SourceFamily.TFGM: SourceRuntimeMetadata(
            source_family=SourceFamily.TFGM,
            current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential_presence=CredentialPresence.UNKNOWN,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await provider response and approved access",
        ),
        SourceFamily.SUMO: SourceRuntimeMetadata(
            source_family=SourceFamily.SUMO,
            current_standing=SourceCurrentStanding.NOT_DETECTED,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="SUMO_NOT_DETECTED",
            owner_action="Install SUMO 1.27 and verify",
        ),
        SourceFamily.MANUAL_INCIDENT: SourceRuntimeMetadata(
            source_family=SourceFamily.MANUAL_INCIDENT,
            current_standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SYNTHETIC,
            operational_receipt=_receipt("manual-valid-001", SourceFamily.MANUAL_INCIDENT),
        ),
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
            source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
            operational_receipt=_receipt(
                "static-valid-001", SourceFamily.STATIC_MANCHESTER_GEOGRAPHY
            ),
        ),
    }


def _registry_with_dft_webtris() -> SnapshotRegistry:
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=_fp("dft-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester; bounded historical acquisition.",
        record_count=100,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-001",
        provenance_fingerprint=_fp("prov-dft-001"),
        validation_receipt_fingerprint=_fp("reg-dft-001-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    webtris_reg = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=_fp("webtris-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        record_count=100,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/webtris-001",
        provenance_fingerprint=_fp("prov-webtris-001"),
        validation_receipt_fingerprint=_fp("reg-webtris-001-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    r1 = register_snapshot(empty, dft_reg)
    return register_snapshot(r1, webtris_reg)


def _unavailable_runtime() -> dict[SourceFamily, SourceRuntimeMetadata]:
    base = _valid_runtime()
    base[SourceFamily.DFT] = SourceRuntimeMetadata(
        source_family=SourceFamily.DFT,
        current_standing=SourceCurrentStanding.UNAVAILABLE,
        credential_presence=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="HISTORICAL_UNAVAILABLE",
        owner_action="Provide historical snapshot",
    )
    base[SourceFamily.WEBTRIS] = SourceRuntimeMetadata(
        source_family=SourceFamily.WEBTRIS,
        current_standing=SourceCurrentStanding.UNAVAILABLE,
        credential_presence=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        blocker="HISTORICAL_UNAVAILABLE",
        owner_action="Provide historical snapshot",
    )
    return base


def _empty_registry() -> SnapshotRegistry:
    return SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())


def test_build_complete_catalogue_from_verified_metadata() -> None:
    # Empty registry with DFT/WEBTRIS unavailable must succeed
    unavailable = _unavailable_runtime()
    empty = _empty_registry()
    catalogue_unavail = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
        runtime_by_family=unavailable,
    )
    assert isinstance(catalogue_unavail, SourceOperationsCatalogue)
    # With accepted DFT/WebTRIS snapshots, HISTORICAL_ONLY succeeds
    runtime = _valid_runtime()
    with_registry = _registry_with_dft_webtris()
    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=with_registry,
        runtime_by_family=runtime,
    )
    assert isinstance(catalogue, SourceOperationsCatalogue)
    assert len(catalogue.sources) == 8
    assert tuple(s.source.family for s in catalogue.sources) == (
        SourceFamily.BODS,
        SourceFamily.DFT,
        SourceFamily.WEBTRIS,
        SourceFamily.NATIONAL_HIGHWAYS,
        SourceFamily.TFGM,
        SourceFamily.SUMO,
        SourceFamily.MANUAL_INCIDENT,
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
    )
    assert catalogue.network_access_performed is False
    assert catalogue.credential_values_present is False
    assert catalogue.directory_presence_used_as_acceptance is False
    bods_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.BODS)
    assert any("General or private-vehicle road traffic" in s for s in bods_row.source.cannot_infer)
    assert bods_row.source.evidence_standing == EvidenceStanding.REAL_MANCHESTER_DATA
    assert bods_row.source.semantic_role == "bus_vehicle_positions"
    wt_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.WEBTRIS)
    assert wt_row.source.evidence_standing == EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA
    nh_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.NATIONAL_HIGHWAYS)
    assert nh_row.source.evidence_standing == EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA
    tfgm_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.TFGM)
    assert tfgm_row.source.evidence_standing == EvidenceStanding.DESIGN_ONLY_CAPABILITY
    assert tfgm_row.current_standing == SourceCurrentStanding.PROVIDER_DATA_REQUIRED
    assert tfgm_row.latest_accepted_snapshot is None
    # Now with one BODS accepted snapshot via registry (also need DFT/WebTRIS)
    bods_reg = SnapshotRegistration(
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=_fp("bods-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=1565,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-001",
        provenance_fingerprint=_fp("prov-bods"),
        validation_receipt_fingerprint=_fp("reg-bods-001-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg1 = register_snapshot(with_registry, bods_reg)
    cat2 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg1,
        runtime_by_family=runtime,
    )
    bods_row2 = next(s for s in cat2.sources if s.source.family is SourceFamily.BODS)
    assert bods_row2.latest_accepted_snapshot is not None
    assert bods_row2.latest_accepted_snapshot.registration_id == "reg-bods-001"
    assert bods_row2.latest_accepted_snapshot.source_family is SourceFamily.BODS
    assert bods_row2.latest_accepted_snapshot.validation_state is OpsValidationState.ACCEPTED
    assert bods_row2.latest_retrieval_at_utc == UTC_A


def test_bods_relabel_via_tampered_definition_rejected() -> None:
    from traffictwin.integration.manchester.source_operations_models import (
        SourceDefinition,
        SourceReadiness,
    )

    tampered = SourceDefinition(
        family=SourceFamily.BODS,
        provider="Evil Provider",
        semantic_role="general_road_traffic",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        rights_standing=RightsStanding.PROVIDER_CONTRACT_REQUIRED,
        licence_id="OGL-v3.0",
        retention_rule="x",
        supported_geography="x",
        can_infer=("General road traffic",),
        cannot_infer=("Nothing",),
        allowed_current_standings=(SourceCurrentStanding.AVAILABLE,),
        allowed_freshness=(SourceFreshnessStanding.LIVE_VEHICLE,),
    )
    with pytest.raises((ValidationError, ValueError)):
        SourceReadiness(
            source=tampered,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            latest_retrieval_at_utc=None,
            latest_accepted_snapshot=None,
            latest_rejected_snapshot=None,
            receipt=None,
            blocker=None,
            owner_action=None,
        )


def test_unavailable_inflation_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.TFGM,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.UNKNOWN,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
        )
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.DFT,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
        )
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.SUMO,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
        )


def test_secret_and_path_leakage_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Set api_key=[REDACTED]",
        )
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            blocker=None,
            owner_action="token: secret1234",
        )
    with pytest.raises((ValidationError, ValueError, SourceOperationsServiceError)):
        bad = SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Check /Users/alice/secret.txt",
        )
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family={**_valid_runtime(), SourceFamily.BODS: bad},
        )
    # /etc must also be rejected
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Check /etc/passwd",
        )


def test_accepted_rejected_latest_ordering_and_service_validation() -> None:
    runtime = _valid_runtime()
    empty = _empty_registry()
    # Create registry with accepted at A and rejected at B (later) for DFT
    reg_acc = SnapshotRegistration(
        registration_id="reg-dft-acc",
        snapshot_identity="snap-dft-acc",
        content_fingerprint=_fp("acc-a"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-acc",
        provenance_fingerprint=_fp("prov-acc"),
        validation_receipt_fingerprint=_fp("reg-dft-acc-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg_rej = SnapshotRegistration(
        registration_id="reg-dft-rej",
        snapshot_identity="snap-dft-rej",
        content_fingerprint=_fp("rej-b"),
        retrieved_at_utc=UTC_B,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points rejected",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-rej",
        provenance_fingerprint=_fp("prov-rej"),
        validation_receipt_fingerprint=_fp("reg-dft-rej-val"),
        validated_at_utc=UTC_B,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Sample rejection reason for testing.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r1 = register_snapshot(empty, reg_acc)
    r2 = register_snapshot(r1, reg_rej)
    webtris_acc = SnapshotRegistration(
        registration_id="reg-webtris-acc-test2",
        snapshot_identity="snap-webtris-acc-test2",
        content_fingerprint=_fp("webtris-acc-test2"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/webtris-acc-test2",
        provenance_fingerprint=_fp("prov-webtris-test2"),
        validation_receipt_fingerprint=_fp("reg-webtris-acc-test2-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    r3 = register_snapshot(r2, webtris_acc)

    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=r3,
        runtime_by_family=runtime,
    )
    dft_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.DFT)
    assert dft_row.latest_accepted_snapshot is not None
    assert dft_row.latest_accepted_snapshot.registration_id == "reg-dft-acc"
    assert dft_row.latest_rejected_snapshot is not None
    assert dft_row.latest_rejected_snapshot.registration_id == "reg-dft-rej"
    assert dft_row.latest_retrieval_at_utc == UTC_B
    assert dft_row.latest_accepted_snapshot.source_family is SourceFamily.DFT
    assert dft_row.latest_rejected_snapshot.source_family is SourceFamily.DFT

    # latest must equal max pointer time – construction with wrong latest must fail
    from traffictwin.integration.manchester.source_operations_models import (
        source_definition,
    )

    acc_ptr = dft_row.latest_accepted_snapshot
    rej_ptr = dft_row.latest_rejected_snapshot
    with pytest.raises((ValidationError, ValueError)):
        from traffictwin.integration.manchester.source_operations_models import SourceReadiness

        SourceReadiness(
            source=source_definition(SourceFamily.DFT),
            current_standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
            latest_retrieval_at_utc=UTC_A,
            latest_accepted_snapshot=acc_ptr,
            latest_rejected_snapshot=rej_ptr,
            receipt=None,
            blocker=None,
            owner_action=None,
        )


def test_tfgm_has_no_accepted_snapshot_via_service() -> None:
    # Registry creation itself must reject TfGM accepted at model validation
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-tfgm-acc",
            snapshot_identity="snap-tfgm-acc",
            content_fingerprint=_fp("tfgm-acc"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.TFGM,
            coverage_summary="TfGM rejected coverage",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            storage_reference="opaque://x/tfgm-acc",
            provenance_fingerprint=_fp("prov-tfgm"),
            validation_receipt_fingerprint=_fp("reg-tfgm-acc-val"),
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
        )
    # Also service must reject if somehow accepted exists – test via direct readiness
    from traffictwin.integration.manchester.source_operations_models import SnapshotPointer

    bad_acc = SnapshotPointer(
        source_family=SourceFamily.TFGM,
        validation_state=OpsValidationState.ACCEPTED,
        registration_id="reg-tfgm-acc",
        snapshot_identity="snap-tfgm-acc",
        content_fingerprint=_fp("tfgm-acc"),
        retrieved_at_utc=UTC_A,
        validated_at_utc=UTC_A,
        validation_receipt_fingerprint=_fp("receipt"),
    )
    # Direct readiness with TfGM accepted must fail
    with pytest.raises((ValidationError, ValueError)):
        from traffictwin.integration.manchester.source_operations_models import (
            SourceReadiness,
            source_definition,
        )

        SourceReadiness(
            source=source_definition(SourceFamily.TFGM),
            current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential_presence=CredentialPresence.UNKNOWN,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            latest_retrieval_at_utc=UTC_A,
            latest_accepted_snapshot=bad_acc,
            latest_rejected_snapshot=None,
            receipt=None,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await provider",
        )


def test_idempotence_and_catalogue_fingerprint_stable() -> None:
    # empty with unavailable
    empty_unavail = _unavailable_runtime()
    empty = _empty_registry()
    c1e = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
        runtime_by_family=empty_unavail,
    )
    c2e = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
        runtime_by_family=empty_unavail,
    )
    assert c1e.canonical_json() == c2e.canonical_json()
    # with registry containing DFT/WebTRIS accepted
    reg = _registry_with_dft_webtris()
    runtime = _valid_runtime()
    c1 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg,
        runtime_by_family=runtime,
    )
    c2 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg,
        runtime_by_family=runtime,
    )
    assert c1.canonical_json() == c2.canonical_json()
    assert c1.fingerprint() == c2.fingerprint()
    assert c1.fingerprint() != _fp("different")


def test_catalogue_from_registry_derives_pointers() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    bods_reg = SnapshotRegistration(
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=_fp("bods-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=1565,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-001",
        provenance_fingerprint=_fp("prov-bods"),
        validation_receipt_fingerprint=_fp("reg-bods-001-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=_fp("dft-001"),
        retrieved_at_utc=UTC_B,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points 2km",
        record_count=100,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-001",
        provenance_fingerprint=_fp("prov-dft"),
        validation_receipt_fingerprint=_fp("reg-dft-001-val"),
        validated_at_utc=UTC_B,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Sample rejection reason for testing.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg1 = register_snapshot(empty, bods_reg)
    reg2 = register_snapshot(reg1, dft_reg)
    # DFT rejected-only with HISTORICAL_ONLY would fail; use UNAVAILABLE for this probe
    runtime = _unavailable_runtime()
    catalogue = catalogue_from_registry(UTC_NOW, reg2, runtime)
    bods_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.BODS)
    dft_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.DFT)
    assert bods_row.latest_accepted_snapshot is not None
    assert bods_row.latest_accepted_snapshot.registration_id == "reg-bods-001"
    assert bods_row.latest_retrieval_at_utc == UTC_A
    assert dft_row.latest_rejected_snapshot is not None
    assert dft_row.latest_rejected_snapshot.registration_id == "reg-dft-001"
    assert dft_row.latest_retrieval_at_utc == UTC_B
    assert dft_row.latest_accepted_snapshot is None


def test_incomplete_runtime_rejected() -> None:
    runtime = _valid_runtime()
    incomplete = {k: v for k, v in runtime.items() if k is not SourceFamily.BODS}
    with pytest.raises(SourceOperationsServiceError, match="INCOMPLETE_RUNTIME"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=incomplete,  # type: ignore[arg-type]
        )


def test_never_uses_directory_existence_and_no_credential_values() -> None:
    sig = inspect.signature(build_source_operations_catalogue)
    params = set(sig.parameters.keys())
    assert "workspace_root" not in params
    assert "directory" not in params
    assert "credential_value" not in params
    assert "api_key" not in params
    assert "accepted_pointers" not in params
    assert "rejected_pointers" not in params
    assert "latest_retrieval_by_family" not in params
    assert "snapshot_registry_fingerprint_value" not in params
    assert "credential_value" not in SourceRuntimeMetadata.model_fields
    assert "api_key" not in SourceRuntimeMetadata.model_fields
    runtime = _valid_runtime()
    reg = _registry_with_dft_webtris()
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg,
        runtime_by_family=runtime,
    )
    j = cat.model_dump_json()
    assert "api_key" not in j.lower()
    assert "bearer" not in j.lower()


def test_fabricated_pointer_fails_closed() -> None:
    # Service no longer accepts explicit pointers; only registry-derived pointers exist
    # Fabricated pointer cannot be injected – verify signature has no explicit pointer params
    import inspect

    sig = inspect.signature(build_source_operations_catalogue)
    assert "accepted_pointers" not in sig.parameters
    # Attempting to pass fabricated fingerprint via old kwarg must fail
    with pytest.raises(TypeError):
        build_source_operations_catalogue(  # type: ignore[call-arg]
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_empty_registry(),
            runtime_by_family=_valid_runtime(),
            accepted_pointers={},
        )


def test_future_evidence_fails_closed() -> None:
    runtime = _valid_runtime()
    empty = _empty_registry()
    future_reg = SnapshotRegistration(
        registration_id="reg-bods-future",
        snapshot_identity="snap-bods-future",
        content_fingerprint=_fp("future"),
        retrieved_at_utc=UTC_FUTURE,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/future",
        provenance_fingerprint=_fp("prov-future"),
        validation_receipt_fingerprint=_fp("reg-bods-future-val"),
        validated_at_utc=UTC_FUTURE,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg_future = register_snapshot(empty, future_reg)
    # Pointer time later than evaluated_at must fail
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=reg_future,
            runtime_by_family=runtime,
        )
    # Receipt future also fails
    bad_runtime = dict(_valid_runtime())
    bad_runtime[SourceFamily.SUMO] = SourceRuntimeMetadata(
        source_family=SourceFamily.SUMO,
        current_standing=SourceCurrentStanding.INSTALLATION_DETECTED,
        credential_presence=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.SIMULATION_TIME,
        tool_version="sumo-1.27.0",
        operational_receipt=OperationalReceipt(
            receipt_id="sumo-future-001",
            receipt_fingerprint=_fp("sumo-future"),
            source_family=SourceFamily.SUMO,
            check_id="sumo-check-future",
            observed_at_utc=UTC_FUTURE,
        ),
    )
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=bad_runtime,
        )


def test_pointer_timestamp_must_be_exact_utc_via_service() -> None:
    # Service must reject naive datetime in receipt (via model validation)
    with pytest.raises((ValidationError, ValueError)):
        OperationalReceipt(
            receipt_id="naive-receipt",
            receipt_fingerprint=_fp("naive"),
            source_family=SourceFamily.BODS,
            check_id="bods-check-naive",
            observed_at_utc=datetime(2026, 7, 22, 10, 0, 0),  # naive
        )


# ---- Adversarial model_copy and trusted-instance bypass tests ----


def test_model_copy_inflates_bods_coverage_via_service() -> None:
    runtime = _valid_runtime()
    bods_reg = SnapshotRegistration(
        registration_id="reg-bods-inflated",
        snapshot_identity="snap-bods-inflated",
        content_fingerprint=_fp("bods-inflated"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/bods-inflated",
        provenance_fingerprint=_fp("prov-inflated"),
        validation_receipt_fingerprint=_fp("reg-bods-inflated-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    inflated = bods_reg.model_copy(
        update={"coverage_summary": "General road traffic in Manchester"}
    )
    # register_snapshot must revalidate and reject inflated BODS coverage
    with pytest.raises((ValidationError, SourceOperationsServiceError, Exception)):
        # Try via service: need to get inflated into registry first –
        # but registry construction itself should fail. Direct registry
        # with inflated snapshot should fail canonical revalidation.
        bad_registry = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=(inflated,))
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=bad_registry,
            runtime_by_family=runtime,
        )
    # Also if we bypass registry construction via model_copy, service should catch
    valid_reg = SnapshotRegistry(registered_at_utc=UTC_NOW, snapshots=(bods_reg,))
    forged = valid_reg.model_copy(update={"snapshots": (inflated,)})
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=forged,
            runtime_by_family=runtime,
        )


def test_model_copy_inflates_source_family_via_service() -> None:
    runtime = _valid_runtime()
    base = SnapshotRegistration(
        registration_id="reg-family-inflated",
        snapshot_identity="snap-family-inflated",
        content_fingerprint=_fp("family-inflated"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/family-inflated",
        provenance_fingerprint=_fp("prov-family"),
        validation_receipt_fingerprint=_fp("reg-family-inflated-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    inflated = base.model_copy(
        update={
            "source_family": SourceFamily.WEBTRIS,
            "evidence_standing": EvidenceStanding.REAL_MANCHESTER_DATA,
        }
    )
    forged = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=()).model_copy(
        update={"snapshots": (inflated,)}
    )
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=forged,
            runtime_by_family=runtime,
        )


def test_model_copy_inflates_tfgm_accepted_state_via_service() -> None:
    # TfGM accepted should be rejected even via model_copy bypass
    tfgm_rej = SnapshotRegistration(
        registration_id="reg-tfgm-rej",
        snapshot_identity="snap-tfgm-rej",
        content_fingerprint=_fp("tfgm-rej"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.TFGM,
        coverage_summary="TfGM rejected coverage",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.UNAVAILABLE,
        storage_reference="opaque://x/tfgm-rej",
        provenance_fingerprint=_fp("prov-tfgm-rej"),
        validation_receipt_fingerprint=_fp("reg-tfgm-rej-val"),
        validated_at_utc=UTC_A,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Sample rejection reason for testing.",
        evidence_standing=EvidenceStanding.DESIGN_ONLY_CAPABILITY,
    )
    inflated = tfgm_rej.model_copy(update={"validation_state": SnapshotValidationState.ACCEPTED})
    forged = SnapshotRegistry(registered_at_utc=UTC_NOW, snapshots=()).model_copy(
        update={"snapshots": (inflated,)}
    )
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=forged,
            runtime_by_family=_valid_runtime(),
        )


def test_model_copy_inflates_pointer_family_via_service() -> None:
    # Service must not trust pre-built pointers; they are derived from registry.
    # Test that a forged runtime with inflated family via model_copy is rejected at service boundary
    valid = _valid_runtime()[SourceFamily.BODS]
    inflated_runtime = valid.model_copy(update={"source_family": SourceFamily.DFT})
    bad_runtime = dict(_valid_runtime())
    bad_runtime[SourceFamily.BODS] = inflated_runtime
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=bad_runtime,
        )


def test_model_copy_inflates_future_time_via_service() -> None:
    runtime = _valid_runtime()
    future_reg = SnapshotRegistration(
        registration_id="reg-future-bods",
        snapshot_identity="snap-future-bods",
        content_fingerprint=_fp("future-bods"),
        retrieved_at_utc=UTC_FUTURE,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/future-bods",
        provenance_fingerprint=_fp("prov-future-bods"),
        validation_receipt_fingerprint=_fp("reg-future-bods-val"),
        validated_at_utc=UTC_FUTURE,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    # Need registry admission at FUTURE so direct registry passes,
    # but catalogue evaluated earlier fails.
    reg_at_future = SnapshotRegistry(registered_at_utc=UTC_FUTURE, snapshots=(future_reg,))
    # Service evaluated at NOW should reject pointer future evidence
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=reg_at_future,
            runtime_by_family=runtime,
        )
    # Also model_copy inflation: take valid reg at UTC_A and inflate retrieved time to future
    valid_bods = SnapshotRegistration(
        registration_id="reg-valid-bods",
        snapshot_identity="snap-valid-bods",
        content_fingerprint=_fp("valid-bods"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/valid-bods",
        provenance_fingerprint=_fp("prov-valid-bods"),
        validation_receipt_fingerprint=_fp("reg-valid-bods-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    inflated = valid_bods.model_copy(update={"retrieved_at_utc": UTC_FUTURE})
    forged_registry = SnapshotRegistry(
        registered_at_utc=UTC_FUTURE, snapshots=(valid_bods,)
    ).model_copy(update={"snapshots": (inflated,)})
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_A,
            snapshot_registry=forged_registry,
            runtime_by_family=runtime,
        )


def test_direct_forged_registry_tuple_via_service_rejected() -> None:
    bods_a = SnapshotRegistration(
        registration_id="reg-forge-a",
        snapshot_identity="snap-forge-001",
        content_fingerprint=_fp("forge-a"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/forge-a",
        provenance_fingerprint=_fp("prov-forge-a"),
        validation_receipt_fingerprint=_fp("reg-forge-a-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    bods_b = SnapshotRegistration(
        registration_id="reg-forge-b",
        snapshot_identity="snap-forge-001",
        content_fingerprint=_fp("forge-b"),
        retrieved_at_utc=UTC_B,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions different GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/forge-b",
        provenance_fingerprint=_fp("prov-forge-b"),
        validation_receipt_fingerprint=_fp("reg-forge-b-val"),
        validated_at_utc=UTC_B,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    # Attempt to forge registry directly via model_copy bypassing register_snapshot
    forged = SnapshotRegistry(registered_at_utc=UTC_NOW, snapshots=()).model_copy(
        update={"snapshots": (bods_a, bods_b)}
    )
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=forged,
            runtime_by_family=_valid_runtime(),
        )


def test_registry_admission_time_must_not_exceed_evaluation() -> None:
    # Registry with admission after catalogue evaluation must fail
    future_registry = SnapshotRegistry(registered_at_utc=UTC_FUTURE, snapshots=())
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=future_registry,
            runtime_by_family=_valid_runtime(),
        )


def test_secret_path_not_leaked_in_service_error() -> None:
    # Ensure secret values do not appear in service error messages
    bad_runtime = _valid_runtime()[SourceFamily.BODS].model_copy(
        update={
            "owner_action": "Check /Users/alice/secret.txt",
            "blocker": "CREDENTIAL_REQUIRED",
            "current_standing": SourceCurrentStanding.CREDENTIAL_REQUIRED,
            "credential_presence": CredentialPresence.ABSENT,
            "freshness": SourceFreshnessStanding.UNAVAILABLE,
        }
    )
    crafted = dict(_valid_runtime())
    crafted[SourceFamily.BODS] = bad_runtime
    try:
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=crafted,
        )
        raise AssertionError("should have failed")
    except SourceOperationsServiceError as exc:
        msg = str(exc)
        assert "/Users/alice" not in msg
        assert "secret" not in msg.lower() or "revalidation" in msg.lower()


# ---- Lane 13 receipt/readiness boundary mutation tests ----


def test_provenance_as_receipt_confusion_rejected() -> None:
    """Pointer must carry actual validation receipt, not provenance."""
    prov = _fp("prov-confusion")
    val = _fp("val-confusion")
    assert prov != val
    reg = SnapshotRegistration(
        registration_id="reg-confusion-001",
        snapshot_identity="snap-confusion-001",
        content_fingerprint=_fp("confusion-content"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/confusion",
        provenance_fingerprint=prov,
        validation_receipt_fingerprint=val,
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    reg2 = register_snapshot(empty, reg)
    runtime = _unavailable_runtime()
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg2,
        runtime_by_family=runtime,
    )
    bods_row = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    assert bods_row.latest_accepted_snapshot is not None
    assert bods_row.latest_accepted_snapshot.validation_receipt_fingerprint == val
    assert bods_row.latest_accepted_snapshot.validation_receipt_fingerprint != prov
    # Also ensure service helper uses validation receipt directly
    from traffictwin.integration.manchester.source_operations_service import (
        _pointer_from_registration,
    )

    ptr = _pointer_from_registration(reg)
    assert ptr.validation_receipt_fingerprint == val
    assert ptr.validation_receipt_fingerprint != prov
    assert ptr.validated_at_utc == UTC_A


def test_accepted_without_validation_receipt_fails_via_service() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-acc-no-val-001",
            snapshot_identity="snap-acc-no-val-001",
            content_fingerprint=_fp("acc-no-val"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/acc-no-val",
            provenance_fingerprint=_fp("prov-acc-no-val"),
            # missing validation_receipt_fingerprint
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )  # type: ignore[call-arg]


def test_rejected_without_reason_fails_via_service() -> None:
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-rej-noreason-001",
            snapshot_identity="snap-rej-noreason-001",
            content_fingerprint=_fp("rej-noreason"),
            retrieved_at_utc=UTC_A,
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
            validated_at_utc=UTC_A,
            # missing rejection_code/reason
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )
    # accepted with rejection must also fail
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-acc-with-rej-001",
            snapshot_identity="snap-acc-with-rej-001",
            content_fingerprint=_fp("acc-with-rej"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/acc-with-rej",
            provenance_fingerprint=_fp("prov-acc-with-rej"),
            validation_receipt_fingerprint=_fp("val-acc-with-rej"),
            validated_at_utc=UTC_A,
            rejection_code="SHOULD_NOT_HAVE",
            rejection_reason="Should not have",
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )


def test_reversed_validation_time_fails_via_service() -> None:
    # retrieved > validated must fail
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-rev-time-001",
            snapshot_identity="snap-rev-time-001",
            content_fingerprint=_fp("rev-time"),
            retrieved_at_utc=UTC_B,
            source_family=SourceFamily.BODS,
            coverage_summary="Bus transit positions in admitted GM box",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/rev-time",
            provenance_fingerprint=_fp("prov-rev-time"),
            validation_receipt_fingerprint=_fp("val-rev-time"),
            validated_at_utc=UTC_A,
            evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
        )
    # validated > registered must fail at registry
    reg = SnapshotRegistration(
        registration_id="reg-rev-reg-001",
        snapshot_identity="snap-rev-reg-001",
        content_fingerprint=_fp("rev-reg"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/rev-reg",
        provenance_fingerprint=_fp("prov-rev-reg"),
        validation_receipt_fingerprint=_fp("val-rev-reg"),
        validated_at_utc=UTC_B,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistry(registered_at_utc=UTC_A, snapshots=(reg,))
    # validated > evaluated must fail at catalogue
    empty = SnapshotRegistry(registered_at_utc=UTC_B, snapshots=(reg,))
    # Need runtime with receipts
    runtime = _valid_runtime()
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_A,
            snapshot_registry=empty,
            runtime_by_family=runtime,
        )


def test_receipt_reused_across_families_fails_via_service() -> None:
    bods_receipt = OperationalReceipt(
        receipt_id="bods-reuse-001",
        receipt_fingerprint=_fp("bods-reuse"),
        source_family=SourceFamily.BODS,
        check_id="bods-check-001",
        observed_at_utc=UTC_A,
    )
    # Direct runtime validation must fail when reusing receipt across families
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            operational_receipt=bods_receipt,
        )
    # Service must also reject forged runtime via model_copy bypass
    valid_nh = _valid_runtime()[SourceFamily.NATIONAL_HIGHWAYS]
    forged_nh = valid_nh.model_copy(update={"operational_receipt": bods_receipt})
    bad_runtime = dict(_valid_runtime())
    bad_runtime[SourceFamily.NATIONAL_HIGHWAYS] = forged_nh
    with pytest.raises((ValidationError, SourceOperationsServiceError, ValueError)):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=bad_runtime,
        )


def test_available_with_absent_credential_or_no_receipt_fails_via_service() -> None:
    # BODS AVAILABLE with ABSENT must fail at model level
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            operational_receipt=OperationalReceipt(
                receipt_id="bods-absent-001",
                receipt_fingerprint=_fp("bods-absent"),
                source_family=SourceFamily.BODS,
                check_id="bods-check-001",
                observed_at_utc=UTC_A,
            ),
        )
    # Service must also catch forged via model_copy bypass
    valid_bods = _valid_runtime()[SourceFamily.BODS]
    forged_bods = valid_bods.model_copy(update={"credential_presence": CredentialPresence.ABSENT})
    bad1 = dict(_valid_runtime())
    bad1[SourceFamily.BODS] = forged_bods
    with pytest.raises((SourceOperationsServiceError, ValidationError, ValueError)):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_registry_with_dft_webtris(),
            runtime_by_family=bad1,
        )
    # Also test direct construction with absent fails (second instance)
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            operational_receipt=OperationalReceipt(
                receipt_id="bods-absent-002",
                receipt_fingerprint=_fp("bods-absent2"),
                source_family=SourceFamily.BODS,
                check_id="bods-check-001",
                observed_at_utc=UTC_A,
            ),
        )
    # BODS AVAILABLE without receipt
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        )
    # STATIC_AVAILABLE without receipt
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
        )


def test_forged_registry_queried_through_each_public_helper_via_service() -> None:
    from traffictwin.integration.manchester.snapshot_registry import (
        SnapshotRegistryError,
        get_snapshot,
        latest_accepted_for_family,
        latest_rejected_for_family,
        latest_snapshot_for_family,
        snapshot_registry_fingerprint,
    )

    valid = SnapshotRegistration(
        registration_id="reg-valid-forge-001",
        snapshot_identity="snap-valid-forge-001",
        content_fingerprint=_fp("valid-forge"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/valid-forge",
        provenance_fingerprint=_fp("prov-valid-forge"),
        validation_receipt_fingerprint=_fp("val-valid-forge"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    reg = register_snapshot(empty, valid)
    forged_reg = valid.model_copy(update={"coverage_summary": "General road traffic in Manchester"})
    forged = reg.model_copy(update={"snapshots": (forged_reg,)})
    for helper in [  # noqa: E501
        get_snapshot,
        latest_snapshot_for_family,
        latest_accepted_for_family,
        latest_rejected_for_family,
        snapshot_registry_fingerprint,
    ]:
        with pytest.raises(SnapshotRegistryError):
            if helper is get_snapshot:
                helper(forged, "reg-valid-forge-001")
            elif helper is snapshot_registry_fingerprint:
                helper(forged)
            else:
                helper(forged, SourceFamily.BODS)  # type: ignore


def test_exact_valid_happy_paths() -> None:
    # Exact valid: BODS AVAILABLE with receipt, DFT historical with validation receipt, etc.
    bods_receipt = OperationalReceipt(
        receipt_id="bods-happy-001",
        receipt_fingerprint=_fp("bods-happy"),
        source_family=SourceFamily.BODS,
        check_id="bods-check-001",
        observed_at_utc=UTC_A,
    )
    nh_receipt = OperationalReceipt(
        receipt_id="nh-happy-001",
        receipt_fingerprint=_fp("nh-happy"),
        source_family=SourceFamily.NATIONAL_HIGHWAYS,
        check_id="nh-check-001",
        observed_at_utc=UTC_A,
    )
    static_receipt = OperationalReceipt(
        receipt_id="static-happy-001",
        receipt_fingerprint=_fp("static-happy"),
        source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
        check_id="static-check-001",
        observed_at_utc=UTC_A,
    )
    manual_receipt = OperationalReceipt(
        receipt_id="manual-happy-001",
        receipt_fingerprint=_fp("manual-happy"),
        source_family=SourceFamily.MANUAL_INCIDENT,
        check_id="manual-check-001",
        observed_at_utc=UTC_A,
    )
    sumo_receipt = OperationalReceipt(
        receipt_id="sumo-happy-001",
        receipt_fingerprint=_fp("sumo-happy"),
        source_family=SourceFamily.SUMO,
        check_id="sumo-check-001",
        observed_at_utc=UTC_A,
    )
    # Build registry with accepted BODS and historical DFT
    bods_reg = SnapshotRegistration(
        registration_id="reg-bods-happy-001",
        snapshot_identity="snap-bods-happy-001",
        content_fingerprint=_fp("bods-happy-content"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/bods-happy",
        provenance_fingerprint=_fp("prov-bods-happy"),
        validation_receipt_fingerprint=_fp("val-bods-happy"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-happy-001",
        snapshot_identity="snap-dft-happy-001",
        content_fingerprint=_fp("dft-happy-content"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-happy",
        provenance_fingerprint=_fp("prov-dft-happy"),
        validation_receipt_fingerprint=_fp("val-dft-happy"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    webtris_reg = SnapshotRegistration(
        registration_id="reg-webtris-happy-001",
        snapshot_identity="snap-webtris-happy-001",
        content_fingerprint=_fp("webtris-happy-content"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/webtris-happy",
        provenance_fingerprint=_fp("prov-webtris-happy"),
        validation_receipt_fingerprint=_fp("val-webtris-happy"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    r1 = register_snapshot(empty, bods_reg)
    r2 = register_snapshot(r1, dft_reg)
    r3 = register_snapshot(r2, webtris_reg)
    runtime = {
        SourceFamily.BODS: SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            operational_receipt=bods_receipt,
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
            operational_receipt=nh_receipt,
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
            current_standing=SourceCurrentStanding.INSTALLATION_DETECTED,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
            tool_version="sumo-1.27.0",
            operational_receipt=sumo_receipt,
        ),
        SourceFamily.MANUAL_INCIDENT: SourceRuntimeMetadata(
            source_family=SourceFamily.MANUAL_INCIDENT,
            current_standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SYNTHETIC,
            operational_receipt=manual_receipt,
        ),
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
            source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
            operational_receipt=static_receipt,
        ),
    }
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=r3,
        runtime_by_family=runtime,
    )
    assert len(cat.sources) == 8
    bods_row = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    assert bods_row.latest_accepted_snapshot is not None
    assert bods_row.latest_accepted_snapshot.validation_receipt_fingerprint == _fp("val-bods-happy")
    assert bods_row.receipt is not None
    assert bods_row.receipt.source_family is SourceFamily.BODS
    dft_row = next(s for s in cat.sources if s.source.family is SourceFamily.DFT)
    assert dft_row.latest_accepted_snapshot is not None
    assert dft_row.latest_accepted_snapshot.validation_receipt_fingerprint == _fp("val-dft-happy")
    # Catalogue pointers must be exact projections: check validated
    # time and rejection
    assert bods_row.latest_accepted_snapshot.validated_at_utc == UTC_A
    assert (
        dft_row.latest_accepted_snapshot.retrieved_at_utc
        <= dft_row.latest_accepted_snapshot.validated_at_utc
    )
    # No secret/path in catalogue
    j = cat.model_dump_json()
    assert "/Users" not in j
    assert "/etc" not in j
    assert "api_key" not in j.lower()


# ---- Lane 13 B1 SERVICE discriminating tests ----


def test_historical_only_refused_on_empty_registry_via_service() -> None:
    empty = _empty_registry()
    runtime = _valid_runtime()
    with pytest.raises(SourceOperationsServiceError, match="HISTORICAL_ONLY_WITHOUT_ACCEPTED"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=empty,
            runtime_by_family=runtime,
        )
    # Empty with unavailable succeeds
    unavail = _unavailable_runtime()
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
        runtime_by_family=unavail,
    )
    assert cat.snapshot_registry_fingerprint is not None


def test_historical_only_accepted_pointer_success_for_dft_and_webtris_via_service() -> None:
    reg = _registry_with_dft_webtris()
    runtime = _valid_runtime()
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg,
        runtime_by_family=runtime,
    )
    for fam in (SourceFamily.DFT, SourceFamily.WEBTRIS):
        row = next(s for s in cat.sources if s.source.family is fam)
        assert row.current_standing is SourceCurrentStanding.HISTORICAL_ONLY
        assert row.latest_accepted_snapshot is not None
        assert row.latest_accepted_snapshot.validation_state is OpsValidationState.ACCEPTED
        assert row.latest_accepted_snapshot.source_family is fam
        assert row.latest_accepted_snapshot.validation_receipt_fingerprint is not None
        assert row.latest_accepted_snapshot.validated_at_utc is not None
        assert row.latest_retrieval_at_utc == row.latest_accepted_snapshot.retrieved_at_utc


def test_historical_only_refused_when_only_rejected_via_service() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    dft_rej = SnapshotRegistration(
        registration_id="reg-dft-rej-only",
        snapshot_identity="snap-dft-rej-only",
        content_fingerprint=_fp("dft-rej-only"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-rej-only",
        provenance_fingerprint=_fp("prov-dft-rej-only"),
        validation_receipt_fingerprint=_fp("reg-dft-rej-only-val"),
        validated_at_utc=UTC_A,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Sample rejection reason for testing.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg = register_snapshot(empty, dft_rej)
    # Need also WebTRIS accepted to isolate DFT failure, but WebTRIS will need accepted
    webtris_acc = SnapshotRegistration(
        registration_id="reg-webtris-acc-002",
        snapshot_identity="snap-webtris-acc-002",
        content_fingerprint=_fp("webtris-acc-002"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/webtris-acc-002",
        provenance_fingerprint=_fp("prov-webtris-acc-002"),
        validation_receipt_fingerprint=_fp("reg-webtris-acc-002-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    reg2 = register_snapshot(reg, webtris_acc)
    runtime = _valid_runtime()
    with pytest.raises(SourceOperationsServiceError, match="HISTORICAL_ONLY_WITHOUT_ACCEPTED"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=reg2,
            runtime_by_family=runtime,
        )


def test_bods_historical_only_refused_via_service() -> None:
    bods_acc = SnapshotRegistration(
        registration_id="reg-bods-hist-001",
        snapshot_identity="snap-bods-hist-001",
        content_fingerprint=_fp("bods-hist-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/bods-hist-001",
        provenance_fingerprint=_fp("prov-bods-hist-001"),
        validation_receipt_fingerprint=_fp("reg-bods-hist-001-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    reg = register_snapshot(empty, bods_acc)
    # Add DFT/WebTRIS accepted so service reaches BODS check
    dft_acc = SnapshotRegistration(
        registration_id="reg-dft-acc-bods-test",
        snapshot_identity="snap-dft-acc-bods-test",
        content_fingerprint=_fp("dft-acc-bods-test"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/dft-acc-bods-test",
        provenance_fingerprint=_fp("prov-dft-acc-bods-test"),
        validation_receipt_fingerprint=_fp("reg-dft-acc-bods-test-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    webtris_acc = SnapshotRegistration(
        registration_id="reg-webtris-acc-bods-test",
        snapshot_identity="snap-webtris-acc-bods-test",
        content_fingerprint=_fp("webtris-acc-bods-test"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary=(
            "Selected strategic-road sites only; external to Manchester city-road coverage."
        ),
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://x/webtris-acc-bods-test",
        provenance_fingerprint=_fp("prov-webtris-acc-bods-test"),
        validation_receipt_fingerprint=_fp("reg-webtris-acc-bods-test-val"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    reg2 = register_snapshot(reg, dft_acc)
    reg3 = register_snapshot(reg2, webtris_acc)
    # Direct construction of BODS HISTORICAL_ONLY must fail at model boundary
    with __import__("pytest").raises((__import__("pydantic").ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.HISTORICAL_ONLY,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
        )
    # Test via model_copy bypass at service boundary
    # Create valid BODS then copy-inflate to HISTORICAL_ONLY
    valid_bods = _valid_runtime()[SourceFamily.BODS]
    forged = valid_bods.model_copy(
        update={
            "current_standing": SourceCurrentStanding.HISTORICAL_ONLY,
            "freshness": SourceFreshnessStanding.HISTORICAL,
            "credential_presence": CredentialPresence.NOT_REQUIRED,
            "operational_receipt": None,
        }
    )
    bad_runtime2 = dict(_valid_runtime())
    bad_runtime2[SourceFamily.BODS] = forged
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=reg3,
            runtime_by_family=bad_runtime2,
        )


def test_historical_only_model_copy_refusal_via_service() -> None:
    reg = _registry_with_dft_webtris()
    runtime = _valid_runtime()
    # Valid should succeed
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=reg,
        runtime_by_family=runtime,
    )
    assert cat is not None
    # Model_copy removal of accepted snapshot is not via runtime but via registry forgery
    # Forge registry via model_copy to remove DFT accepted but keep runtime HISTORICAL_ONLY
    forged_reg = reg.model_copy(
        update={
            "snapshots": tuple(s for s in reg.snapshots if s.source_family is not SourceFamily.DFT)
        }
    )
    with pytest.raises(SourceOperationsServiceError, match="HISTORICAL_ONLY_WITHOUT_ACCEPTED"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=forged_reg,
            runtime_by_family=runtime,
        )
    # Forge runtime via model_copy to claim HISTORICAL_ONLY without registry
    unavail = _unavailable_runtime()
    inflated = unavail[SourceFamily.DFT].model_copy(
        update={
            "current_standing": SourceCurrentStanding.HISTORICAL_ONLY,
            "freshness": SourceFreshnessStanding.HISTORICAL,
            "blocker": None,
            "owner_action": None,
        }
    )
    bad = dict(unavail)
    bad[SourceFamily.DFT] = inflated
    # Use empty registry – should fail
    empty = _empty_registry()
    with pytest.raises(SourceOperationsServiceError):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=empty,
            runtime_by_family=bad,
        )


def test_historical_only_direct_construction_refusal_via_service() -> None:
    # Direct SourceReadiness construction without pointer already covered in model tests;
    # service must also fail closed when HISTORICAL_ONLY runtime has no accepted snapshot
    empty = _empty_registry()
    runtime = _valid_runtime()
    with pytest.raises(SourceOperationsServiceError, match="HISTORICAL_ONLY_WITHOUT_ACCEPTED"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=empty,
            runtime_by_family=runtime,
        )

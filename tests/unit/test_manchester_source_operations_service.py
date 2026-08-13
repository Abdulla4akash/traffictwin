"""Discriminating tests for the network-free source-operations catalogue service."""

from __future__ import annotations

import hashlib
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
    SnapshotPointer,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceOperationsCatalogue,
    SourceRuntimeMetadata,
)
from traffictwin.integration.manchester.source_operations_service import (
    SourceOperationsServiceError,
    build_source_operations_catalogue,
    catalogue_from_registry,
)

UTC_NOW = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)
UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_B = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _receipt(rid: str) -> OperationalReceipt:
    return OperationalReceipt(
        receipt_id=rid,
        receipt_fingerprint=_fp(rid),
        observed_at_utc=UTC_A,
    )


def _valid_runtime() -> dict[SourceFamily, SourceRuntimeMetadata]:
    return {
        SourceFamily.BODS: SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
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
        ),
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY: SourceRuntimeMetadata(
            source_family=SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
            current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.STATIC,
        ),
    }


def _empty_pointers() -> dict[SourceFamily, SnapshotPointer | None]:
    return dict.fromkeys(SourceFamily, None)  # type: ignore[arg-type]  # noqa: C420


def _empty_latest() -> dict[SourceFamily, datetime | None]:
    return dict.fromkeys(SourceFamily, None)  # type: ignore[arg-type]  # noqa: C420


def test_build_complete_catalogue_from_verified_metadata() -> None:
    runtime = _valid_runtime()
    accepted = _empty_pointers()
    rejected = _empty_pointers()
    latest = _empty_latest()
    # Add one accepted BODS pointer
    fp = _fp("bods-content")
    bods_pointer = SnapshotPointer(
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=fp,
        retrieved_at_utc=UTC_A,
        validation_receipt_fingerprint=_fp("receipt-bods"),
    )
    accepted[SourceFamily.BODS] = bods_pointer
    latest[SourceFamily.BODS] = UTC_A

    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry_fingerprint_value=_fp("registry"),
        runtime_by_family=runtime,
        accepted_pointers=accepted,
        rejected_pointers=rejected,
        latest_retrieval_by_family=latest,
    )
    assert isinstance(catalogue, SourceOperationsCatalogue)
    assert len(catalogue.sources) == 8
    assert tuple(s.source.family for s in catalogue.sources) == tuple(
        SourceFamily.__members__.values()
    ) or tuple(s.source.family for s in catalogue.sources) == (
        SourceFamily.BODS,
        SourceFamily.DFT,
        SourceFamily.WEBTRIS,
        SourceFamily.NATIONAL_HIGHWAYS,
        SourceFamily.TFGM,
        SourceFamily.SUMO,
        SourceFamily.MANUAL_INCIDENT,
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
    )
    # Network-free and credential-value-free
    assert catalogue.network_access_performed is False
    assert catalogue.credential_values_present is False
    assert catalogue.directory_presence_used_as_acceptance is False
    # BODS remains bus-only
    bods_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.BODS)
    assert any("General or private-vehicle road traffic" in s for s in bods_row.source.cannot_infer)
    assert bods_row.source.evidence_standing == EvidenceStanding.REAL_MANCHESTER_DATA
    assert bods_row.source.semantic_role == "bus_vehicle_positions"
    # WebTRIS/NH are external strategic-road
    wt_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.WEBTRIS)
    assert wt_row.source.evidence_standing == EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA
    nh_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.NATIONAL_HIGHWAYS)
    assert nh_row.source.evidence_standing == EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA
    # TfGM is design-only unavailable
    tfgm_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.TFGM)
    assert tfgm_row.source.evidence_standing == EvidenceStanding.DESIGN_ONLY_CAPABILITY
    assert tfgm_row.current_standing == SourceCurrentStanding.PROVIDER_DATA_REQUIRED
    assert tfgm_row.latest_accepted_snapshot is None


def test_bods_relabel_via_tampered_definition_rejected() -> None:
    # Directly constructing a SourceReadiness with tampered BODS definition should fail frozen check
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
    # The service builds from frozen definitions, so tampered definition never enters via service.
    # But direct readiness creation with tampered source must be rejected by frozen equality check.
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
    # Try to inflate TfGM to AVAILABLE
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.TFGM,
            current_standing=SourceCurrentStanding.AVAILABLE,  # not allowed
            credential_presence=CredentialPresence.UNKNOWN,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
        )
    # Try to inflate DfT to AVAILABLE (only HISTORICAL_ONLY/UNAVAILABLE allowed)
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.DFT,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.HISTORICAL,
        )
    # Service should also reject if runtime tries to inflate
    # We already validated metadata creation fails; also verify SUMO rejects AVAILABLE.
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.SUMO,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
        )


def test_secret_and_path_leakage_rejected() -> None:
    # Runtime metadata must reject secret-like owner_action
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Set api_key=sk-1234567890abcdef",
        )
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.NATIONAL_HIGHWAYS,
            current_standing=SourceCurrentStanding.AVAILABLE,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.NEAR_LIVE,
            blocker=None,
            owner_action="token: secret1234",  # secret pattern in free text screening
        )
    # Service should reject runtime containing secret in dump
    with pytest.raises((ValidationError, ValueError, SourceOperationsServiceError)):
        # owner_action containing private path
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
            snapshot_registry_fingerprint_value=_fp("reg"),
            runtime_by_family={**_valid_runtime(), SourceFamily.BODS: bad},
            accepted_pointers=_empty_pointers(),
            rejected_pointers=_empty_pointers(),
            latest_retrieval_by_family=_empty_latest(),
        )


def test_accepted_rejected_latest_ordering_and_service_validation() -> None:
    runtime = _valid_runtime()
    # Create pointers with ordering: accepted at A, rejected at B (later)
    fp_a = _fp("acc-a")
    fp_r = _fp("rej-b")
    acc = SnapshotPointer(
        registration_id="reg-dft-acc",
        snapshot_identity="snap-dft-acc",
        content_fingerprint=fp_a,
        retrieved_at_utc=UTC_A,
        validation_receipt_fingerprint=_fp("receipt-acc"),
    )
    rej = SnapshotPointer(
        registration_id="reg-dft-rej",
        snapshot_identity="snap-dft-rej",
        content_fingerprint=fp_r,
        retrieved_at_utc=UTC_B,
        validation_receipt_fingerprint=_fp("receipt-rej"),
    )
    accepted = _empty_pointers()
    rejected = _empty_pointers()
    latest = _empty_latest()
    accepted[SourceFamily.DFT] = acc
    rejected[SourceFamily.DFT] = rej
    latest[SourceFamily.DFT] = UTC_B  # latest is max of both

    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry_fingerprint_value=_fp("registry"),
        runtime_by_family=runtime,
        accepted_pointers=accepted,
        rejected_pointers=rejected,
        latest_retrieval_by_family=latest,
    )
    dft_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.DFT)
    assert dft_row.latest_accepted_snapshot == acc
    assert dft_row.latest_rejected_snapshot == rej
    assert dft_row.latest_retrieval_at_utc == UTC_B

    # Latest must be >= max pointer time; supplying earlier latest should fail
    bad_latest = dict(latest)
    bad_latest[SourceFamily.DFT] = UTC_A
    with pytest.raises(SourceOperationsServiceError, match="LATEST_ORDERING"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry_fingerprint_value=_fp("registry2"),
            runtime_by_family=runtime,
            accepted_pointers=accepted,
            rejected_pointers=rejected,
            latest_retrieval_by_family=bad_latest,
        )
    # Latest required when pointers exist, but missing should fail
    missing_latest = dict(latest)
    missing_latest[SourceFamily.DFT] = None
    with pytest.raises(SourceOperationsServiceError, match="LATEST_ORDERING"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry_fingerprint_value=_fp("registry3"),
            runtime_by_family=runtime,
            accepted_pointers=accepted,
            rejected_pointers=rejected,
            latest_retrieval_by_family=missing_latest,
        )


def test_tfgm_has_no_accepted_snapshot_via_service() -> None:
    runtime = _valid_runtime()
    accepted = _empty_pointers()
    # Try to give TfGM an accepted pointer
    fp = _fp("tfgm-acc")
    bad_acc = SnapshotPointer(
        registration_id="reg-tfgm-acc",
        snapshot_identity="snap-tfgm-acc",
        content_fingerprint=fp,
        retrieved_at_utc=UTC_A,
        validation_receipt_fingerprint=_fp("receipt"),
    )
    accepted[SourceFamily.TFGM] = bad_acc
    latest = _empty_latest()
    latest[SourceFamily.TFGM] = UTC_A
    with pytest.raises(SourceOperationsServiceError, match="TFGM"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry_fingerprint_value=_fp("reg"),
            runtime_by_family=runtime,
            accepted_pointers=accepted,
            rejected_pointers=_empty_pointers(),
            latest_retrieval_by_family=latest,
        )


def test_idempotence_and_catalogue_fingerprint_stable() -> None:
    runtime = _valid_runtime()
    accepted = _empty_pointers()
    rejected = _empty_pointers()
    latest = _empty_latest()
    c1 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry_fingerprint_value=_fp("stable-reg"),
        runtime_by_family=runtime,
        accepted_pointers=accepted,
        rejected_pointers=rejected,
        latest_retrieval_by_family=latest,
    )
    c2 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry_fingerprint_value=_fp("stable-reg"),
        runtime_by_family=runtime,
        accepted_pointers=accepted,
        rejected_pointers=rejected,
        latest_retrieval_by_family=latest,
    )
    assert c1.canonical_json() == c2.canonical_json()
    assert c1.fingerprint() == c2.fingerprint()
    assert c1.fingerprint() != _fp("different")


def test_catalogue_from_registry_derives_pointers() -> None:
    # Build a registry with BODS accepted and DfT rejected
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
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg1 = register_snapshot(empty, bods_reg)
    reg2 = register_snapshot(reg1, dft_reg)
    runtime = _valid_runtime()
    catalogue = catalogue_from_registry(UTC_NOW, reg2, runtime)
    bods_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.BODS)
    dft_row = next(s for s in catalogue.sources if s.source.family is SourceFamily.DFT)
    assert bods_row.latest_accepted_snapshot is not None
    assert bods_row.latest_accepted_snapshot.registration_id == "reg-bods-001"
    assert bods_row.latest_retrieval_at_utc == UTC_A
    assert dft_row.latest_rejected_snapshot is not None
    assert dft_row.latest_rejected_snapshot.registration_id == "reg-dft-001"
    assert dft_row.latest_retrieval_at_utc == UTC_B
    # Rejected DfT, accepted is None
    assert dft_row.latest_accepted_snapshot is None


def test_incomplete_runtime_rejected() -> None:
    runtime = _valid_runtime()
    incomplete = {k: v for k, v in runtime.items() if k is not SourceFamily.BODS}
    with pytest.raises(SourceOperationsServiceError, match="INCOMPLETE_RUNTIME"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry_fingerprint_value=_fp("reg"),
            runtime_by_family=incomplete,  # type: ignore[arg-type]
            accepted_pointers=_empty_pointers(),
            rejected_pointers=_empty_pointers(),
            latest_retrieval_by_family=_empty_latest(),
        )


def test_never_uses_directory_existence_and_no_credential_values() -> None:
    # Service signature has no directory/path param and no credential value field
    import inspect

    sig = inspect.signature(build_source_operations_catalogue)
    params = set(sig.parameters.keys())
    assert "workspace_root" not in params
    assert "directory" not in params
    assert "credential_value" not in params
    assert "api_key" not in params
    # Runtime model must not have credential value field
    assert "credential_value" not in SourceRuntimeMetadata.model_fields
    assert "api_key" not in SourceRuntimeMetadata.model_fields
    # Catalogue must not contain credential values
    runtime = _valid_runtime()
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry_fingerprint_value=_fp("reg2"),
        runtime_by_family=runtime,
        accepted_pointers=_empty_pointers(),
        rejected_pointers=_empty_pointers(),
        latest_retrieval_by_family=_empty_latest(),
    )
    # No secret in JSON
    j = cat.model_dump_json()
    assert "api_key" not in j.lower()
    assert "bearer" not in j.lower()


def test_fingerprint_mismatch_rejected_when_using_registry() -> None:
    empty = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    bods_reg = SnapshotRegistration(
        registration_id="reg-bods-001",
        snapshot_identity="snap-bods-001",
        content_fingerprint=_fp("bods-001"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions",
        record_count=10,
        parser_version="p-1.0",
        schema_version="s-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://x/bods",
        provenance_fingerprint=_fp("prov"),
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg = register_snapshot(empty, bods_reg)
    runtime = _valid_runtime()
    # Supply wrong fingerprint
    with pytest.raises(SourceOperationsServiceError, match="FINGERPRINT_MISMATCH"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry_fingerprint_value=_fp("wrong"),
            runtime_by_family=runtime,
            snapshot_registry=reg,
        )

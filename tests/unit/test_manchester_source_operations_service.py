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


def _empty_registry() -> SnapshotRegistry:
    return SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())


def test_build_complete_catalogue_from_verified_metadata() -> None:
    runtime = _valid_runtime()
    empty = _empty_registry()
    # Build with empty registry (no snapshots) via registry-only path
    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
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
    # Now with one BODS accepted snapshot via registry
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
    reg1 = register_snapshot(empty, bods_reg)
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
            snapshot_registry=_empty_registry(),
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
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r1 = register_snapshot(empty, reg_acc)
    r2 = register_snapshot(r1, reg_rej)

    catalogue = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=r2,
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
    runtime = _valid_runtime()
    empty = _empty_registry()
    c1 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
        runtime_by_family=runtime,
    )
    c2 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=empty,
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
    assert dft_row.latest_accepted_snapshot is None


def test_incomplete_runtime_rejected() -> None:
    runtime = _valid_runtime()
    incomplete = {k: v for k, v in runtime.items() if k is not SourceFamily.BODS}
    with pytest.raises(SourceOperationsServiceError, match="INCOMPLETE_RUNTIME"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_empty_registry(),
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
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_NOW,
        snapshot_registry=_empty_registry(),
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
            observed_at_utc=UTC_FUTURE,
        ),
    )
    with pytest.raises(SourceOperationsServiceError, match="FUTURE_EVIDENCE"):
        build_source_operations_catalogue(
            evaluated_at_utc=UTC_NOW,
            snapshot_registry=_empty_registry(),
            runtime_by_family=bad_runtime,
        )


def test_pointer_timestamp_must_be_exact_utc_via_service() -> None:
    # Service must reject naive datetime in receipt (via model validation)
    with pytest.raises((ValidationError, ValueError)):
        OperationalReceipt(
            receipt_id="naive-receipt",
            receipt_fingerprint=_fp("naive"),
            observed_at_utc=datetime(2026, 7, 22, 10, 0, 0),  # naive
        )

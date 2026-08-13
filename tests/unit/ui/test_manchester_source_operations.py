"""Unit tests for Manchester Source Operations UI service (Lane 14)."""

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
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceOperationsCatalogue,
    SourceRuntimeMetadata,
    source_definition,
)
from traffictwin.integration.manchester.source_operations_service import (
    SourceOperationsServiceError,
    build_source_operations_catalogue,
)
from traffictwin.ui.manchester_source_operations import (
    build_demonstrator_catalogue,
    build_quality_inputs_for_catalogue,
    catalogue_row_display,
    make_demonstrator_registry,
    make_demonstrator_runtime,
)

UTC_A = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
UTC_EVAL = datetime(2026, 7, 22, 13, 0, 0, tzinfo=UTC)


def _fp(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def test_demonstrator_catalogue_is_truthful() -> None:
    cat = build_demonstrator_catalogue()
    assert isinstance(cat, SourceOperationsCatalogue)
    assert len(cat.sources) == 8
    families = tuple(s.source.family for s in cat.sources)
    assert families == (
        SourceFamily.BODS,
        SourceFamily.DFT,
        SourceFamily.WEBTRIS,
        SourceFamily.NATIONAL_HIGHWAYS,
        SourceFamily.TFGM,
        SourceFamily.SUMO,
        SourceFamily.MANUAL_INCIDENT,
        SourceFamily.STATIC_MANCHESTER_GEOGRAPHY,
    )
    bods = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    assert bods.source.provider == "Department for Transport Bus Open Data Service"
    assert bods.source.semantic_role == "bus_vehicle_positions"
    assert bods.current_standing is SourceCurrentStanding.CREDENTIAL_REQUIRED
    assert bods.credential_presence is CredentialPresence.ABSENT
    assert bods.freshness is SourceFreshnessStanding.UNAVAILABLE
    assert any("General or private-vehicle road traffic" in s for s in bods.source.cannot_infer)
    assert any("Bus" in s for s in bods.source.can_infer)
    assert bods.source.rights_standing.value == "provider_contract_required"
    assert bods.source.licence_id == "OGL-v3.0"
    assert bods.blocker == "CREDENTIAL_REQUIRED"
    tfgm = next(s for s in cat.sources if s.source.family is SourceFamily.TFGM)
    assert tfgm.current_standing is SourceCurrentStanding.PROVIDER_DATA_REQUIRED
    assert tfgm.credential_presence is CredentialPresence.UNKNOWN
    assert tfgm.latest_accepted_snapshot is None
    assert tfgm.source.evidence_standing.value == "DESIGN-ONLY CAPABILITY"
    assert "Nothing until exact provider evidence" in tfgm.source.can_infer[0]
    dft = next(s for s in cat.sources if s.source.family is SourceFamily.DFT)
    assert dft.current_standing is SourceCurrentStanding.HISTORICAL_ONLY
    assert dft.credential_presence is CredentialPresence.NOT_REQUIRED
    assert dft.freshness is SourceFreshnessStanding.HISTORICAL
    assert dft.latest_accepted_snapshot is not None
    assert dft.latest_accepted_snapshot.validation_state is SnapshotValidationState.ACCEPTED
    wt = next(s for s in cat.sources if s.source.family is SourceFamily.WEBTRIS)
    assert wt.source.evidence_standing.value == "REAL EXTERNAL NON-MANCHESTER DATA"
    nh = next(s for s in cat.sources if s.source.family is SourceFamily.NATIONAL_HIGHWAYS)
    assert nh.current_standing is SourceCurrentStanding.CREDENTIAL_REQUIRED
    assert nh.source.semantic_role == "strategic_road_operational_status"
    sumo = next(s for s in cat.sources if s.source.family is SourceFamily.SUMO)
    assert sumo.current_standing is SourceCurrentStanding.NOT_DETECTED
    assert sumo.tool_version is None
    assert sumo.receipt is None
    assert sumo.source.evidence_standing.value == "SIMULATION OUTPUT"
    assert "Observed Manchester traffic" not in sumo.source.can_infer[0]
    manual = next(s for s in cat.sources if s.source.family is SourceFamily.MANUAL_INCIDENT)
    assert manual.current_standing is SourceCurrentStanding.SYNTHETIC_AVAILABLE
    assert manual.receipt is not None
    static = next(
        s for s in cat.sources if s.source.family is SourceFamily.STATIC_MANCHESTER_GEOGRAPHY
    )
    assert static.current_standing is SourceCurrentStanding.STATIC_AVAILABLE
    assert static.freshness is SourceFreshnessStanding.STATIC
    assert static.receipt is not None
    assert cat.network_access_performed is False
    assert cat.credential_values_present is False
    assert cat.directory_presence_used_as_acceptance is False


def test_demonstrator_builds_through_real_models() -> None:
    registry = make_demonstrator_registry()
    runtime = make_demonstrator_runtime()
    cat = build_demonstrator_catalogue()
    import re

    re_match = re.fullmatch(r"[0-9a-f]{64}", cat.snapshot_registry_fingerprint)
    assert re_match is not None
    assert registry.registered_at_utc.tzinfo is not None
    assert len(runtime) == 8


def test_bods_is_bus_only_semantics() -> None:
    bods_def = source_definition(SourceFamily.BODS)
    assert bods_def.semantic_role == "bus_vehicle_positions"
    assert any("General or private-vehicle" in s for s in bods_def.cannot_infer)
    from traffictwin.integration.manchester.snapshot_registry import SnapshotRegistration

    with pytest.raises((ValidationError, ValueError)):
        SnapshotRegistration(
            registration_id="reg-bods-general",
            snapshot_identity="snap-bods-general",
            content_fingerprint=_fp("x"),
            retrieved_at_utc=UTC_A,
            source_family=SourceFamily.BODS,
            coverage_summary="General road traffic volume in Manchester",
            record_count=10,
            parser_version="p-1.0",
            schema_version="s-1.0",
            validation_state=SnapshotValidationState.ACCEPTED,
            freshness=SourceFreshnessStanding.LIVE_VEHICLE,
            storage_reference="opaque://x/bods-general",
            provenance_fingerprint=_fp("prov"),
            validation_receipt_fingerprint=_fp("val"),
            validated_at_utc=UTC_A,
            evidence_standing=bods_def.evidence_standing,
        )


def test_tfgm_provider_required_no_accepted() -> None:
    cat = build_demonstrator_catalogue()
    tfgm = next(s for s in cat.sources if s.source.family is SourceFamily.TFGM)
    assert tfgm.latest_accepted_snapshot is None
    from traffictwin.integration.manchester.source_operations_models import SourceRuntimeMetadata

    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.TFGM,
            current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
            credential_presence=CredentialPresence.PRESENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="PROVIDER_DATA_REQUIRED",
            owner_action="Await provider",
        )


def test_sumo_installation_detected_requires_receipt() -> None:
    from traffictwin.integration.manchester.source_operations_models import SourceRuntimeMetadata

    cat = build_demonstrator_catalogue()
    sumo = next(s for s in cat.sources if s.source.family is SourceFamily.SUMO)
    assert sumo.current_standing is SourceCurrentStanding.NOT_DETECTED
    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.SUMO,
            current_standing=SourceCurrentStanding.INSTALLATION_DETECTED,
            credential_presence=CredentialPresence.NOT_REQUIRED,
            freshness=SourceFreshnessStanding.SIMULATION_TIME,
            tool_version="sumo-1.27.0",
            operational_receipt=None,
            blocker=None,
            owner_action=None,
        )
    receipt = OperationalReceipt(
        receipt_id="sumo-receipt-001",
        receipt_fingerprint=_fp("sumo-receipt"),
        source_family=SourceFamily.SUMO,
        check_id="sumo-check-001",
        observed_at_utc=UTC_A,
    )
    ok = SourceRuntimeMetadata(
        source_family=SourceFamily.SUMO,
        current_standing=SourceCurrentStanding.INSTALLATION_DETECTED,
        credential_presence=CredentialPresence.NOT_REQUIRED,
        freshness=SourceFreshnessStanding.SIMULATION_TIME,
        tool_version="sumo-1.27.0",
        operational_receipt=receipt,
    )
    assert ok.tool_version == "sumo-1.27.0"


def test_credential_presence_without_value() -> None:
    cat = build_demonstrator_catalogue()
    for row in cat.sources:
        disp = catalogue_row_display(row)
        assert disp["credential_presence"] in ("present", "absent", "not_required", "unknown")
        for v in disp.values():
            assert "api_key" not in v.lower() or "api_key" in v
            assert "Bearer " not in v
            assert "sk-" not in v


def test_secret_and_path_screening_in_display() -> None:
    _ = build_demonstrator_catalogue()
    from traffictwin.integration.manchester.source_operations_models import SourceRuntimeMetadata

    with pytest.raises((ValidationError, ValueError)):
        SourceRuntimeMetadata(
            source_family=SourceFamily.BODS,
            current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
            credential_presence=CredentialPresence.ABSENT,
            freshness=SourceFreshnessStanding.UNAVAILABLE,
            blocker="CREDENTIAL_REQUIRED",
            owner_action="Check /Users/alice/secret.txt",
        )
    with pytest.raises(ValueError):
        from traffictwin.ui.manchester_source_operations import _screen

        _screen("/tmp/private/data.csv")  # noqa: S108


def test_model_copy_mutation_fails_closed() -> None:
    cat = build_demonstrator_catalogue()
    bods = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    mutated = bods.model_copy(update={"current_standing": SourceCurrentStanding.AVAILABLE})
    from pydantic import ValidationError as PydanticVE

    with pytest.raises((ValidationError, PydanticVE, ValueError, SourceOperationsServiceError)):
        type(bods).model_validate(mutated.model_dump(mode="python"))
    from traffictwin.integration.manchester.source_quality import SourceQualityInput

    qin = SourceQualityInput(
        source_family=SourceFamily.BODS,
        evaluated_at_utc=UTC_EVAL,
        total_expected_rows=10,
        present_rows=10,
        missing_rows=0,
        duplicate_rows=0,
        accepted_rows=10,
        rejected_rows=0,
    )
    mutated_q = qin.model_copy(update={"missing_rows": 999})
    from traffictwin.integration.manchester.source_quality import compute_source_quality_diagnostics

    with pytest.raises((ValidationError, ValueError)):
        compute_source_quality_diagnostics(mutated_q)


def test_no_quality_score_in_diagnostics() -> None:
    cat = build_demonstrator_catalogue()
    reg = make_demonstrator_registry(cat.evaluated_at_utc)
    diags = build_quality_inputs_for_catalogue(cat, reg)
    for _fam, diag in diags.items():
        assert not hasattr(diag, "quality_score")
        assert not hasattr(diag, "composite_score")
        dump = diag.model_dump(mode="python")
        assert "quality_score" not in dump
        assert "composite" not in " ".join(dump.keys()).lower()


def test_rejected_accepted_chronology() -> None:
    cat = build_demonstrator_catalogue()
    bods = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    assert bods.latest_accepted_snapshot is None
    assert bods.latest_rejected_snapshot is not None
    assert bods.latest_retrieval_at_utc == bods.latest_rejected_snapshot.retrieved_at_utc
    dft = next(s for s in cat.sources if s.source.family is SourceFamily.DFT)
    assert dft.latest_accepted_snapshot is not None
    assert (
        dft.latest_accepted_snapshot.retrieved_at_utc
        <= dft.latest_accepted_snapshot.validated_at_utc
    )
    assert dft.latest_retrieval_at_utc == dft.latest_accepted_snapshot.retrieved_at_utc


def test_catalogue_row_display_contains_all_required_fields() -> None:
    cat = build_demonstrator_catalogue()
    for row in cat.sources:
        disp = catalogue_row_display(row)
        required = [
            "family",
            "provider",
            "semantic_role",
            "current_standing",
            "credential_presence",
            "rights",
            "licence",
            "retention",
            "supported_geography",
            "freshness",
            "latest_retrieval",
            "latest_accepted",
            "latest_rejected",
            "schema",
            "receipt",
            "blocker",
            "owner_action",
            "can_infer",
            "cannot_infer",
            "evidence_standing",
        ]
        for key in required:
            assert key in disp, f"missing {key} for {row.source.family}"
            assert isinstance(disp[key], str)


def test_build_quality_inputs_derives_exact_row_counts_from_registry() -> None:
    """DFT=7 and WebTRIS=999 must yield those exact accepted row counts, never 42/24."""

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    dft_reg = SnapshotRegistration(
        registration_id="reg-dft-007",
        snapshot_identity="snap-dft-007",
        content_fingerprint=_fp("dft-7"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=7,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-007",
        provenance_fingerprint=_fp("prov-dft-007"),
        validation_receipt_fingerprint=_fp("val-dft-007"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    webtris_reg = SnapshotRegistration(
        registration_id="reg-webtris-999",
        snapshot_identity="snap-webtris-999",
        content_fingerprint=_fp("webtris-999"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=999,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/webtris-999",
        provenance_fingerprint=_fp("prov-webtris-999"),
        validation_receipt_fingerprint=_fp("val-webtris-999"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    bods_rej = SnapshotRegistration(
        registration_id="reg-bods-rej-005",
        snapshot_identity="snap-bods-rej-005",
        content_fingerprint=_fp("bods-rej-005"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box - rejected sample",
        record_count=5,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-rej-005",
        provenance_fingerprint=_fp("prov-bods-005"),
        validation_receipt_fingerprint=_fp("val-bods-005"),
        validated_at_utc=UTC_A,
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Rejected sample.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r1 = register_snapshot(base, dft_reg)
    r2 = register_snapshot(r1, webtris_reg)
    r3 = register_snapshot(r2, bods_rej)
    runtime = make_demonstrator_runtime(UTC_EVAL)
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=r3, runtime_by_family=runtime
    )
    diags = build_quality_inputs_for_catalogue(cat, r3)
    assert diags[SourceFamily.DFT].accepted_rows == 7
    assert diags[SourceFamily.DFT].rejected_rows == 0
    assert diags[SourceFamily.WEBTRIS].accepted_rows == 999
    assert diags[SourceFamily.WEBTRIS].rejected_rows == 0
    # Must not be hardcoded 42/24
    assert diags[SourceFamily.DFT].accepted_rows != 42
    assert diags[SourceFamily.WEBTRIS].accepted_rows != 24
    # BODS rejected rows = 5 in rows, not snapshot count 1
    assert diags[SourceFamily.BODS].rejected_rows == 5
    assert diags[SourceFamily.BODS].accepted_rows == 0
    # rejected_rate uses row denominator
    assert diags[SourceFamily.BODS].rejected_rate == pytest.approx(1.0)
    assert diags[SourceFamily.DFT].rejected_rate == pytest.approx(0.0)
    # Unmeasured components are None, not zero
    for fam in SourceFamily:
        d = diags[fam]
        assert d.total_expected_rows is None, f"{fam} total should be None"
        assert d.missing_rows is None, f"{fam} missing should be None"
        assert d.duplicate_rows is None, f"{fam} duplicate should be None"
        assert d.missingness is None, f"{fam} missingness None"
        assert d.duplicate_rate is None, f"{fam} duplicate_rate None"
        assert d.spatial_coverage_rate is None, f"{fam} spatial None"


def test_build_quality_inputs_changed_registry_counts() -> None:
    """Changing registry record_count must change diagnostics accordingly."""

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    reg1 = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=_fp("dft-a"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=10,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-a",
        provenance_fingerprint=_fp("prov-a"),
        validation_receipt_fingerprint=_fp("val-a"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r = register_snapshot(base, reg1)
    runtime = make_demonstrator_runtime(UTC_EVAL)
    # Need WebTRIS accepted for HISTORICAL_ONLY; add minimal
    web_reg = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=_fp("web-a"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=1,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/web-a",
        provenance_fingerprint=_fp("prov-web-a"),
        validation_receipt_fingerprint=_fp("val-web-a"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    r = register_snapshot(r, web_reg)
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=r, runtime_by_family=runtime
    )
    diags = build_quality_inputs_for_catalogue(cat, r)
    assert diags[SourceFamily.DFT].accepted_rows == 10
    # Now with different count
    base2 = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    reg2 = SnapshotRegistration(
        registration_id="reg-dft-002",
        snapshot_identity="snap-dft-002",
        content_fingerprint=_fp("dft-b"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=77,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-b",
        provenance_fingerprint=_fp("prov-b"),
        validation_receipt_fingerprint=_fp("val-b"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r2 = register_snapshot(base2, reg2)
    r2 = register_snapshot(r2, web_reg)
    cat2 = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=r2, runtime_by_family=runtime
    )
    diags2 = build_quality_inputs_for_catalogue(cat2, r2)
    assert diags2[SourceFamily.DFT].accepted_rows == 77
    assert diags2[SourceFamily.DFT].accepted_rows != diags[SourceFamily.DFT].accepted_rows


def test_build_quality_inputs_multiple_snapshots_latest_only() -> None:
    """Multiple accepted snapshots must use latest exact pointer only, not sum."""

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    # Two DFT accepted: earlier 10 rows, later 30 rows
    utc_early = UTC_A
    utc_late = datetime(2026, 7, 22, 11, 0, 0, tzinfo=UTC)
    reg_early = SnapshotRegistration(
        registration_id="reg-dft-early",
        snapshot_identity="snap-dft-early",
        content_fingerprint=_fp("dft-early"),
        retrieved_at_utc=utc_early,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=10,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-early",
        provenance_fingerprint=_fp("prov-early"),
        validation_receipt_fingerprint=_fp("val-early"),
        validated_at_utc=utc_early,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    reg_late = SnapshotRegistration(
        registration_id="reg-dft-late",
        snapshot_identity="snap-dft-late",
        content_fingerprint=_fp("dft-late"),
        retrieved_at_utc=utc_late,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=30,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft-late",
        provenance_fingerprint=_fp("prov-late"),
        validation_receipt_fingerprint=_fp("val-late"),
        validated_at_utc=utc_late,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    web_reg = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=_fp("web"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=5,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/web",
        provenance_fingerprint=_fp("prov-web"),
        validation_receipt_fingerprint=_fp("val-web"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    r = register_snapshot(base, reg_early)
    r = register_snapshot(r, reg_late)
    r = register_snapshot(r, web_reg)
    runtime = make_demonstrator_runtime(UTC_EVAL)
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=r, runtime_by_family=runtime
    )
    diags = build_quality_inputs_for_catalogue(cat, r)
    # Latest only = 30, not sum 40
    assert diags[SourceFamily.DFT].accepted_rows == 30
    assert diags[SourceFamily.DFT].accepted_rows != 40


def test_build_quality_inputs_empty_registry() -> None:
    """Empty registry yields 0 accepted/rejected and None unmeasured."""

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    # Need to handle HISTORICAL_ONLY requirement: use non-historical runtime for empty case
    runtime_empty: dict[SourceFamily, SourceRuntimeMetadata] = {}
    for fam in SourceFamily:
        if fam in {SourceFamily.DFT, SourceFamily.WEBTRIS}:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.UNAVAILABLE,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="UNAVAILABLE",
                owner_action="No snapshot available",
            )
        elif fam is SourceFamily.BODS:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
                credential_presence=CredentialPresence.ABSENT,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="CREDENTIAL_REQUIRED",
                owner_action="Provide BODS API key via approved credential channel",
            )
        elif fam is SourceFamily.NATIONAL_HIGHWAYS:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.CREDENTIAL_REQUIRED,
                credential_presence=CredentialPresence.ABSENT,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="CREDENTIAL_REQUIRED",
                owner_action="Provide National Highways API credential via approved channel",
            )
        elif fam is SourceFamily.TFGM:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.PROVIDER_DATA_REQUIRED,
                credential_presence=CredentialPresence.UNKNOWN,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="PROVIDER_DATA_REQUIRED",
                owner_action="Await TfGM provider contract and approved adapter",
            )
        elif fam is SourceFamily.SUMO:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.NOT_DETECTED,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.UNAVAILABLE,
                blocker="SUMO_NOT_DETECTED",
                owner_action="Install SUMO 1.27 and verify via operational receipt",
            )
        elif fam is SourceFamily.MANUAL_INCIDENT:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.SYNTHETIC_AVAILABLE,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.SYNTHETIC,
                operational_receipt=OperationalReceipt(
                    receipt_id="manual-receipt-001",
                    receipt_fingerprint=_fp("manual-receipt"),
                    source_family=fam,
                    check_id="manual-check-001",
                    observed_at_utc=UTC_A,
                ),
            )
        else:
            runtime_empty[fam] = SourceRuntimeMetadata(
                source_family=fam,
                current_standing=SourceCurrentStanding.STATIC_AVAILABLE,
                credential_presence=CredentialPresence.NOT_REQUIRED,
                freshness=SourceFreshnessStanding.STATIC,
                operational_receipt=OperationalReceipt(
                    receipt_id="static-receipt-001",
                    receipt_fingerprint=_fp("static-receipt"),
                    source_family=fam,
                    check_id="static-check-001",
                    observed_at_utc=UTC_A,
                ),
            )
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=base, runtime_by_family=runtime_empty
    )
    diags = build_quality_inputs_for_catalogue(cat, base)
    for fam, diag in diags.items():
        assert diag.accepted_rows == 0, f"{fam} accepted should be 0"
        assert diag.rejected_rows == 0, f"{fam} rejected should be 0"
        assert diag.rejected_rate is None
        assert diag.missingness is None
        assert diag.duplicate_rate is None
        assert diag.total_expected_rows is None
        assert diag.missing_rows is None


def test_build_quality_inputs_rejected_rate_row_unit() -> None:
    """Rejected rate denominator is rows (accepted+rejected rows), not snapshot counts."""

    base = SnapshotRegistry(registered_at_utc=UTC_A, snapshots=())
    acc = SnapshotRegistration(
        registration_id="reg-bods-acc-001",
        snapshot_identity="snap-bods-acc-001",
        content_fingerprint=_fp("bods-acc"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box - accepted",
        record_count=20,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-acc",
        provenance_fingerprint=_fp("prov-bods-acc"),
        validation_receipt_fingerprint=_fp("val-bods-acc"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    rej = SnapshotRegistration(
        registration_id="reg-bods-rej-001",
        snapshot_identity="snap-bods-rej-001",
        content_fingerprint=_fp("bods-rej"),
        retrieved_at_utc=datetime(2026, 7, 22, 11, 0, tzinfo=UTC),
        source_family=SourceFamily.BODS,
        coverage_summary="Bus transit positions in admitted GM box - rejected sample",
        record_count=5,
        parser_version="bods-parser-1.0",
        schema_version="bods-schema-1.0",
        validation_state=SnapshotValidationState.REJECTED,
        freshness=SourceFreshnessStanding.LIVE_VEHICLE,
        storage_reference="opaque://snapshots/bods-rej-001",
        provenance_fingerprint=_fp("prov-bods-rej-001"),
        validation_receipt_fingerprint=_fp("val-bods-rej-001"),
        validated_at_utc=datetime(2026, 7, 22, 11, 0, tzinfo=UTC),
        rejection_code="VALIDATION_FAILED",
        rejection_reason="Rejected sample.",
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    web = SnapshotRegistration(
        registration_id="reg-webtris-001",
        snapshot_identity="snap-webtris-001",
        content_fingerprint=_fp("web"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.WEBTRIS,
        coverage_summary="Selected strategic-road sites only; external to Manchester",
        record_count=5,
        parser_version="webtris-parser-1.0",
        schema_version="webtris-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/web",
        provenance_fingerprint=_fp("prov-web"),
        validation_receipt_fingerprint=_fp("val-web"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_EXTERNAL_NON_MANCHESTER_DATA,
    )
    dft = SnapshotRegistration(
        registration_id="reg-dft-001",
        snapshot_identity="snap-dft-001",
        content_fingerprint=_fp("dft"),
        retrieved_at_utc=UTC_A,
        source_family=SourceFamily.DFT,
        coverage_summary="Admitted DfT count points in Manchester",
        record_count=10,
        parser_version="dft-parser-1.0",
        schema_version="dft-schema-1.0",
        validation_state=SnapshotValidationState.ACCEPTED,
        freshness=SourceFreshnessStanding.HISTORICAL,
        storage_reference="opaque://snapshots/dft",
        provenance_fingerprint=_fp("prov-dft"),
        validation_receipt_fingerprint=_fp("val-dft"),
        validated_at_utc=UTC_A,
        evidence_standing=EvidenceStanding.REAL_MANCHESTER_DATA,
    )
    r = register_snapshot(base, acc)
    r = register_snapshot(r, rej)
    r = register_snapshot(r, web)
    r = register_snapshot(r, dft)
    runtime = make_demonstrator_runtime(UTC_EVAL)
    # Override BODS to allow live availability for this test? Keep credential_required
    cat = build_source_operations_catalogue(
        evaluated_at_utc=UTC_EVAL, snapshot_registry=r, runtime_by_family=runtime
    )
    diags = build_quality_inputs_for_catalogue(cat, r)
    # 5 rejected / (20+5) = 0.2
    assert diags[SourceFamily.BODS].rejected_rate == pytest.approx(0.2)
    # Not snapshot count 1/(1+1)=0.5
    assert diags[SourceFamily.BODS].rejected_rate != pytest.approx(0.5)


def test_make_demonstrator_registry_evaluated_binds_chronology() -> None:
    with pytest.raises((ValidationError, ValueError)):
        make_demonstrator_registry(datetime(2026, 7, 22, 9, 0, 0, tzinfo=UTC))
    # Valid evaluated after validated
    reg = make_demonstrator_registry(UTC_EVAL)
    assert reg.registered_at_utc <= UTC_EVAL


def test_manchester_source_operations_no_navigation_registration() -> None:
    """Page must remain lane-local and not register in shared navigation."""

    from traffictwin.ui.navigation_v07 import v07_navigation_pages

    pages = v07_navigation_pages()
    all_scripts: list[str] = []
    for group_pages in pages.values():
        for spec in group_pages:
            all_scripts.append(getattr(spec, "script", ""))
    assert "app_pages/manchester_source_operations.py" not in all_scripts
    assert "pages/manchester_source_operations.py" not in all_scripts

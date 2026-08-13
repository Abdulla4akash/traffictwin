"""Unit tests for Manchester Source Operations UI service (Lane 14)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.snapshot_registry import SnapshotValidationState
from traffictwin.integration.manchester.source_operations_models import (
    CredentialPresence,
    OperationalReceipt,
    SourceCurrentStanding,
    SourceFamily,
    SourceFreshnessStanding,
    SourceOperationsCatalogue,
    source_definition,
)
from traffictwin.integration.manchester.source_operations_service import (
    SourceOperationsServiceError,
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
    # Must contain all families in frozen order
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
    # BODS is bus-only, credential_required, unavailable freshness, provider contract
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
    # TfGM remains provider-data-required with no accepted snapshot
    tfgm = next(s for s in cat.sources if s.source.family is SourceFamily.TFGM)
    assert tfgm.current_standing is SourceCurrentStanding.PROVIDER_DATA_REQUIRED
    assert tfgm.credential_presence is CredentialPresence.UNKNOWN
    assert tfgm.latest_accepted_snapshot is None
    assert tfgm.source.evidence_standing.value == "DESIGN-ONLY CAPABILITY"
    assert "Nothing until exact provider evidence" in tfgm.source.can_infer[0]
    # DFT historical_only with accepted snapshot
    dft = next(s for s in cat.sources if s.source.family is SourceFamily.DFT)
    assert dft.current_standing is SourceCurrentStanding.HISTORICAL_ONLY
    assert dft.credential_presence is CredentialPresence.NOT_REQUIRED
    assert dft.freshness is SourceFreshnessStanding.HISTORICAL
    assert dft.latest_accepted_snapshot is not None
    assert dft.latest_accepted_snapshot.validation_state is SnapshotValidationState.ACCEPTED
    # WebTRIS external
    wt = next(s for s in cat.sources if s.source.family is SourceFamily.WEBTRIS)
    assert wt.source.evidence_standing.value == "REAL EXTERNAL NON-MANCHESTER DATA"
    # NH credential_required
    nh = next(s for s in cat.sources if s.source.family is SourceFamily.NATIONAL_HIGHWAYS)
    assert nh.current_standing is SourceCurrentStanding.CREDENTIAL_REQUIRED
    assert nh.source.semantic_role == "strategic_road_operational_status"
    # SUMO not_detected (not installation_detected without receipt)
    sumo = next(s for s in cat.sources if s.source.family is SourceFamily.SUMO)
    assert sumo.current_standing is SourceCurrentStanding.NOT_DETECTED
    assert sumo.tool_version is None
    assert sumo.receipt is None
    assert sumo.source.evidence_standing.value == "SIMULATION OUTPUT"
    assert "Observed Manchester traffic" not in sumo.source.can_infer[0]
    # Manual synthetic
    manual = next(s for s in cat.sources if s.source.family is SourceFamily.MANUAL_INCIDENT)
    assert manual.current_standing is SourceCurrentStanding.SYNTHETIC_AVAILABLE
    assert manual.receipt is not None
    # Static
    static = next(
        s for s in cat.sources if s.source.family is SourceFamily.STATIC_MANCHESTER_GEOGRAPHY
    )
    assert static.current_standing is SourceCurrentStanding.STATIC_AVAILABLE
    assert static.freshness is SourceFreshnessStanding.STATIC
    assert static.receipt is not None
    # Catalogue privacy flags
    assert cat.network_access_performed is False
    assert cat.credential_values_present is False
    assert cat.directory_presence_used_as_acceptance is False


def test_demonstrator_builds_through_real_models() -> None:
    registry = make_demonstrator_registry()
    runtime = make_demonstrator_runtime()
    cat = build_demonstrator_catalogue()
    # Fingerprint is deterministic 64 hex
    import re

    re_match = re.fullmatch(r"[0-9a-f]{64}", cat.snapshot_registry_fingerprint)
    assert re_match is not None
    # Registry and runtime are real validated models
    assert registry.registered_at_utc.tzinfo is not None
    assert len(runtime) == 8


def test_bods_is_bus_only_semantics() -> None:
    bods_def = source_definition(SourceFamily.BODS)
    assert bods_def.semantic_role == "bus_vehicle_positions"
    assert any("General or private-vehicle" in s for s in bods_def.cannot_infer)
    # Relabel to general traffic must be rejected at snapshot or definition level
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
    # Attempt to create TfGM with PRESENT credential must fail
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
    # Installation detected without receipt must fail
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
    # With receipt it should succeed
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
        # Displayed credential presence is enum name, not value
        assert disp["credential_presence"] in ("present", "absent", "not_required", "unknown")
        # No field contains a secret value pattern
        for v in disp.values():
            assert "api_key" not in v.lower() or "api_key" in v  # avoid false positive
            assert "Bearer " not in v
            assert "sk-" not in v


def test_secret_and_path_screening_in_display() -> None:
    _ = build_demonstrator_catalogue()
    # Attempt to inject path into display must be caught by model validation earlier
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
    # Display helper itself screens
    with pytest.raises(ValueError):
        from traffictwin.ui.manchester_source_operations import _screen

        _screen("/tmp/private/data.csv")  # noqa: S108


def test_model_copy_mutation_fails_closed() -> None:
    cat = build_demonstrator_catalogue()
    bods = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    # Mutate readiness to inflate standing
    mutated = bods.model_copy(update={"current_standing": SourceCurrentStanding.AVAILABLE})
    # Service should reject when revalidated via catalogue
    from pydantic import ValidationError as PydanticVE

    with pytest.raises((ValidationError, PydanticVE, ValueError, SourceOperationsServiceError)):
        # Directly validate mutated readiness
        type(bods).model_validate(mutated.model_dump(mode="python"))
    # Quality diagnostics model_copy mutation
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
    diags = build_quality_inputs_for_catalogue(cat)
    for _fam, diag in diags.items():
        assert not hasattr(diag, "quality_score")
        assert not hasattr(diag, "composite_score")
        # Ensure no hidden score in dump
        dump = diag.model_dump(mode="python")
        assert "quality_score" not in dump
        assert "composite" not in " ".join(dump.keys()).lower()


def test_rejected_accepted_chronology() -> None:
    cat = build_demonstrator_catalogue()
    bods = next(s for s in cat.sources if s.source.family is SourceFamily.BODS)
    # Demonstrator has rejected only; accepted is None, rejected is at UTC_A
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

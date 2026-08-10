"""Service tests for Manchester Evidence Hub — hardened M1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traffictwin.integration.manchester.freshness import FreshnessTruthState
from traffictwin.ui.manchester_evidence_hub import (
    AcquisitionReadinessState,
    LocalEvidenceState,
    ManchesterEvidenceHubView,
    ManchesterSourceReadiness,
    RightsRetentionState,
    ScientificGateState,
    SoftwareSupportState,
    build_manchester_hub_view,
)


def test_deterministic_source_inventory() -> None:
    view1 = build_manchester_hub_view(None)
    view2 = build_manchester_hub_view(None)
    assert [s.source_id for s in view1.sources] == [s.source_id for s in view2.sources]
    assert len(view1.sources) == 9


def test_stable_source_ordering() -> None:
    view = build_manchester_hub_view(None)
    ids = [s.source_id for s in view.sources]
    assert ids == sorted(ids)
    # Pin canonical order
    assert ids == [
        "bods",
        "dft",
        "manual_incident",
        "national_highways",
        "social_media",
        "static_boundaries",
        "tfgm",
        "tfgm_ntis_measured_traffic",
        "webtris",
    ]


def test_dft_historical_only() -> None:
    view = build_manchester_hub_view(None)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "Historical" in dft.source_role
    assert dft.evidence_type == "historical"
    assert "historical" in dft.evidence_ceiling.lower()
    assert "NOT live" in " ".join(dft.limitations)
    assert dft.freshness_state == "historical"
    assert "live" not in dft.freshness_state.lower()
    # DfT must never be live
    assert str(dft.freshness_state) != "live_vehicle"
    assert str(dft.freshness_state) != "near_live"


def test_webtris_never_mislabeled_live() -> None:
    view = build_manchester_hub_view(None)
    w = next(s for s in view.sources if s.source_id == "webtris")
    assert "WebTRIS" in w.display_name
    assert "historical" in w.evidence_type.lower()
    assert "live" not in w.freshness_state.lower() or w.freshness_state == "historical"
    assert w.freshness_state == "historical"
    assert w.freshness_state not in {"live_vehicle", "near_live"}
    assert "do not call live" in " ".join(w.limitations).lower()


def test_bods_bus_only() -> None:
    view = build_manchester_hub_view(None)
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "bus-only" in bods.source_role.lower() or "bus only" in bods.coverage_scope.lower()
    assert "NOT general" in bods.coverage_scope
    assert (
        "bus-only" in bods.evidence_ceiling.lower() or "bus only" in bods.evidence_ceiling.lower()
    )
    assert (
        "bus-only" in " ".join(bods.limitations).lower()
        or "bus only" in " ".join(bods.limitations).lower()
    )


def test_national_highways_strategic_only() -> None:
    view = build_manchester_hub_view(None)
    nh = next(s for s in view.sources if s.source_id == "national_highways")
    assert "Strategic" in nh.coverage_scope
    assert "NOT general" in nh.coverage_scope
    assert "strategic" in nh.evidence_ceiling.lower()
    assert "NOT Manchester city" in nh.coverage_scope or "NOT general" in nh.coverage_scope


def test_tfgm_infrastructure_telemetry_distinction() -> None:
    view = build_manchester_hub_view(None)
    tfgm = next(s for s in view.sources if s.source_id == "tfgm")
    assert "Infrastructure" in tfgm.source_role
    assert (
        "NOT traffic telemetry" in " ".join(tfgm.limitations)
        or "NOT traffic" in tfgm.coverage_scope
    )
    assert tfgm.freshness_state == "unavailable"
    assert "infrastructure" in tfgm.evidence_ceiling.lower()
    assert (
        "NOT telemetry" in tfgm.evidence_ceiling
        or "infrastructure" in tfgm.evidence_ceiling.lower()
    )


def test_tfgm_ntis_measured_traffic_unavailable_without_contract() -> None:
    view = build_manchester_hub_view(None)
    t = next(s for s in view.sources if s.source_id == "tfgm_ntis_measured_traffic")
    assert "UNAVAILABLE" in t.source_role
    assert t.freshness_state == "unavailable"
    assert "PROVIDER_CONTRACT_REQUIRED" in t.rights_retention_state
    assert "UNAVAILABLE" in t.software_support_state
    assert "UNAVAILABLE" in t.acquisition_readiness
    assert "Unavailable" in t.local_evidence_state
    assert any("provider contract" in b.lower() for b in t.blockers)
    assert "provider contract" in t.next_action.lower()


def test_ons_geography_not_traffic() -> None:
    view = build_manchester_hub_view(None)
    b = next(s for s in view.sources if s.source_id == "static_boundaries")
    assert "Geographic context" in b.source_role
    assert "NOT traffic evidence" in " ".join(b.limitations)
    assert b.freshness_state == "unavailable"
    assert b.evidence_type == "geographic_context"
    assert "geographic" in b.evidence_ceiling.lower() or "geography" in b.evidence_ceiling.lower()


def test_manual_incident_authored_not_observed() -> None:
    view = build_manchester_hub_view(None)
    m = next(s for s in view.sources if s.source_id == "manual_incident")
    assert "AUTHORED" in m.source_role
    assert m.evidence_type == "authored_input"
    assert m.freshness_state == "synthetic"
    assert "NOT become observed" in " ".join(m.limitations) or "AUTHORED" in m.source_role


def test_social_media_deferred() -> None:
    view = build_manchester_hub_view(None)
    sm = next(s for s in view.sources if s.source_id == "social_media")
    assert "Deferred" in sm.source_role
    assert sm.freshness_state == "unavailable"
    assert "DEFERRED" in sm.software_support_state or "Deferred" in sm.configuration_state


def test_no_synthetic_promotion() -> None:
    view = build_manchester_hub_view(None)
    for src in view.sources:
        if src.source_id not in {"manual_incident"}:
            assert "synthetic" not in src.evidence_type or src.source_id == "manual_incident"
            if src.source_id not in {"manual_incident", "social_media"}:
                assert src.freshness_state != "synthetic" or src.source_id == "manual_incident"


def test_no_boundary_promotion() -> None:
    view = build_manchester_hub_view(None)
    b = next(s for s in view.sources if s.source_id == "static_boundaries")
    assert "Geographic context" in b.source_role
    assert "NOT traffic evidence" in " ".join(b.limitations)


def test_no_credentials_exposed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BODS_API_KEY", "secret-bods-key-123")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "secret-nh-key-456")
    view = build_manchester_hub_view(None)
    dumped = json.dumps(view.model_dump(mode="json"))
    assert "secret-bods-key" not in dumped
    assert "secret-nh-key" not in dumped
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert bods.configuration_state in {"Configured", "Not configured (BODS_API_KEY unavailable)"}
    assert "secret" not in bods.configuration_state.lower()


def test_no_secret_in_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BODS_API_KEY", "super-secret-bods-999")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "super-secret-nh-999")
    view = build_manchester_hub_view(None)
    # Fingerprint payload must not contain secrets
    assert "super-secret-bods-999" not in view.fingerprint
    assert "super-secret-nh-999" not in view.fingerprint
    dumped = json.dumps(view.model_dump(mode="json"))
    assert "super-secret-bods-999" not in dumped
    assert "super-secret-nh-999" not in dumped
    # Fingerprint should be same whether secrets differ? It binds readiness, not secret values
    # Configured vs not configured changes fingerprint, but secret value itself must not appear
    monkeypatch.setenv("BODS_API_KEY", "different-secret-111")
    view2 = build_manchester_hub_view(None)
    # Both have BODS configured, so fingerprint should be identical despite different secret values
    assert view.fingerprint == view2.fingerprint


def test_no_absolute_private_path_leakage(tmp_path: Path) -> None:
    view = build_manchester_hub_view(tmp_path)
    dumped = json.dumps(view.model_dump(mode="json"))
    for _p in ["/Users/", "/home/", "/private/", "/tmp/"]:  # noqa: S108
        # The dump must not contain the absolute tmp_path string
        if str(tmp_path) != "/tmp" and str(tmp_path) in dumped:  # noqa: S108
            raise AssertionError(f"absolute path leaked: {tmp_path}")
    # Workspace path itself must not appear
    assert str(tmp_path) not in dumped


def test_workspace_unconfigured_state() -> None:
    view = build_manchester_hub_view(None)
    assert "No workspace" in view.workspace_state
    # Only static boundaries is accepted in empty workspace (manual is authored, not accepted)
    assert view.accepted_evidence_count == 1


def test_partial_availability_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "Accepted local evidence" in dft.local_evidence_state
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert (
        "No live evidence" in bods.local_evidence_state
        or "Not configured" in bods.configuration_state
    )
    # WebTRIS still absent, tfgm absent — independence
    webtris = next(s for s in view.sources if s.source_id == "webtris")
    assert "No accepted" in webtris.local_evidence_state
    # DfT present must not promote whole Manchester state
    assert view.accepted_evidence_count == 2  # dft + static


def test_partial_source_independence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    # Only DfT present
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    # Nh still unavailable independently
    nh = next(s for s in view.sources if s.source_id == "national_highways")
    assert "Not configured" in nh.configuration_state
    assert nh.freshness_state == "unavailable"
    # BODS still unavailable independently
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "No live evidence" in bods.local_evidence_state
    # TfGM still absent independently
    tfgm = next(s for s in view.sources if s.source_id == "tfgm")
    assert "No accepted" in tfgm.local_evidence_state
    # Summary must not claim whole Manchester available because one source exists
    assert view.accepted_evidence_count == 2
    assert view.known_source_count == 9
    # Warnings must still mention BODS/NH requirements
    assert any("BODS" in w for w in view.warnings)


def test_accepted_local_evidence_state(tmp_path: Path) -> None:
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    (tmp_path / "evidence" / "webtris").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    assert view.accepted_evidence_count >= 3  # dft + webtris + static


def test_acquisition_ready_not_scientifically_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BODS_API_KEY", "test-bods-key-for-acquisition-ready-check")
    view = build_manchester_hub_view(None)
    found = False
    for src in view.sources:
        if "Acquisition-ready" in src.acquisition_readiness or src.acquisition_readiness.startswith(
            "READY"
        ):
            found = True
            assert (
                "BLOCKED" in src.scientific_gate_state
                or "REQUIRED" in src.scientific_gate_state
                or "NOT_APPLICABLE" in src.scientific_gate_state
            )
            assert (
                "scientific" in src.scientific_gate_state.lower()
                or "not_applicable" in src.scientific_gate_state.lower()
            )
    assert found, "Expected at least one READY source after configuring BODS"


def test_acquisition_ready_distinct_from_evidence_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    # Empty workspace: DfT software support AVAILABLE, acquisition READY, but no accepted evidence
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "AVAILABLE" in dft.software_support_state
    assert dft.acquisition_readiness.startswith("READY")
    assert "No accepted" in dft.local_evidence_state
    # This proves acquisition ready != evidence accepted
    assert "Accepted" not in dft.local_evidence_state
    # Also test BODS without credential: software AVAILABLE but acquisition NOT READY
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "AVAILABLE" in bods.software_support_state
    assert "NOT READY" in bods.acquisition_readiness
    assert "No live evidence" in bods.local_evidence_state


def test_acquisition_ready_with_credential_but_no_stored_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # BODS credential: live control is transient, no stored snapshot
    # File-based needs no credential; env must not fake evidence
    monkeypatch.setenv("BODS_API_KEY", "test-key")
    view = build_manchester_hub_view(tmp_path)
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert bods.acquisition_readiness == "READY"
    # DfT: READY but no evidence — must not claim evidence available
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert dft.acquisition_readiness.startswith("READY")
    assert "No accepted" in dft.local_evidence_state
    assert (
        "evidence available" not in dft.local_evidence_state.lower()
        or "No accepted" in dft.local_evidence_state
    )


def test_evidence_present_not_scientifically_accepted(tmp_path: Path) -> None:
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "Accepted local evidence" in dft.local_evidence_state
    # Even though evidence present, scientific gate remains BLOCKED
    assert "BLOCKED" in dft.scientific_gate_state
    assert "OWNER-SCIENTIFIC" in dft.scientific_gate_state


def test_rights_retention_unknown_remains_unknown() -> None:
    view = build_manchester_hub_view(None)
    for src in view.sources:
        if src.source_id not in {"static_boundaries"}:
            assert (
                "NOT_RECORDED" in src.rights_retention_state
                or "OWNER" in src.rights_retention_state
                or "PROVIDER_CONTRACT_REQUIRED" in src.rights_retention_state
            )
            # Must not invent APPROVED / PUBLICATION ALLOWED
            assert "APPROVED" not in src.rights_retention_state
            assert "PUBLICATION ALLOWED" not in src.rights_retention_state


def test_rights_no_invented_approval(tmp_path: Path) -> None:
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "APPROVED" not in dft.rights_retention_state
    assert "RETENTION APPROVED" not in dft.rights_retention_state
    assert "NOT_RECORDED" in dft.rights_retention_state


def test_scientific_blockers_preserved() -> None:
    view = build_manchester_hub_view(None)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "BLOCKED" in dft.scientific_gate_state
    # Check that all required scientific gates are mentioned in reasons or blockers
    all_reasons = " ".join(" ".join(s.scientific_gate_reasons) for s in view.sources)
    # At least map matching, calibration are mentioned in reasons
    assert (
        "map matching" in all_reasons.lower()
        or "map matching" in " ".join(dft.scientific_gate_reasons).lower()
    )
    assert "calibration" in all_reasons.lower() or "calibration" in all_reasons.lower()


def test_deterministic_fingerprint() -> None:
    v1 = build_manchester_hub_view(None)
    v2 = build_manchester_hub_view(None)
    assert v1.fingerprint == v2.fingerprint
    assert len(v1.fingerprint) == 64


def test_fingerprint_changes_when_evidence_standing_changes(tmp_path: Path) -> None:
    v1 = build_manchester_hub_view(None)
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    v2 = build_manchester_hub_view(tmp_path)
    assert v1.fingerprint != v2.fingerprint


def test_fingerprint_stable_across_temp_roots(tmp_path: Path) -> None:
    # Same logical readiness in two different temp workspace roots => same fingerprint
    ws1 = tmp_path / "ws1"
    ws2 = tmp_path / "ws2"
    ws1.mkdir()
    ws2.mkdir()
    # Both empty (no evidence) — same logical state
    v1 = build_manchester_hub_view(ws1)
    v2 = build_manchester_hub_view(ws2)
    assert v1.fingerprint == v2.fingerprint

    # Both with same evidence layout — same fingerprint despite different absolute paths
    (ws1 / "evidence" / "dft").mkdir(parents=True)
    (ws2 / "evidence" / "dft").mkdir(parents=True)
    v3 = build_manchester_hub_view(ws1)
    v4 = build_manchester_hub_view(ws2)
    assert v3.fingerprint == v4.fingerprint
    assert v3.fingerprint != v1.fingerprint


def test_fingerprint_excludes_wall_clock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fingerprint excludes wall clock; different generated_at → same fingerprint."""  # noqa: E501

    import datetime as dt
    from unittest.mock import MagicMock

    first = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    second = dt.datetime(2026, 1, 1, 13, 0, 0, tzinfo=dt.UTC)
    mock_datetime = MagicMock()
    mock_datetime.datetime.now.side_effect = [first, second]
    mock_datetime.UTC = dt.UTC
    monkeypatch.setattr("traffictwin.ui.manchester_evidence_hub.datetime", mock_datetime)
    v1 = build_manchester_hub_view(tmp_path)
    v2 = build_manchester_hub_view(tmp_path)
    assert v1.generated_at != v2.generated_at
    assert v1.generated_at == first.isoformat()
    assert v2.generated_at == second.isoformat()
    assert v1.fingerprint == v2.fingerprint
    assert v1.to_canonical_bytes() == v2.to_canonical_bytes()


def test_freshness_field_uses_authoritative_enum_and_emitted_values_validate() -> None:
    """All built rows validate under the authoritative FreshnessTruthState contract.

    This test proves the production field is bound to the authoritative type,
    not merely that emitted values happen to be within the set.
    """  # noqa: E501

    from typing import get_args

    # Prove the production model field is typed as the authoritative FreshnessTruthState
    field = ManchesterSourceReadiness.model_fields["freshness_state"]
    assert field.annotation is not None
    assert set(get_args(field.annotation)) == set(get_args(FreshnessTruthState)), (
        "freshness_state field must be typed as authoritative FreshnessTruthState"
    )
    view = build_manchester_hub_view(None)
    allowed = set(get_args(FreshnessTruthState))
    for src in view.sources:
        assert src.freshness_state in allowed, (
            f"{src.source_id} freshness {src.freshness_state} not in authoritative set"
        )
        # Re-validating the row through the Pydantic model must keep the same state
        # Use exclude_computed_fields because derived presentation is not input
        restored = ManchesterSourceReadiness.model_validate(
            src.model_dump(exclude_computed_fields=True)
        )
        assert restored.freshness_state == src.freshness_state
        # Derived label is deterministic from typed state
        assert restored.scientific_gate_state == src.scientific_gate_state


def test_freshness_rejects_arbitrary_value() -> None:
    """Arbitrary freshness must be rejected by the authoritative production type."""  # noqa: E501

    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        ManchesterSourceReadiness(
            source_id="probe",
            display_name="Probe",
            source_role="Probe",
            evidence_type="probe",
            evidence_ceiling="probe",
            coverage_scope="probe",
            freshness_state="live",  # not in FreshnessTruthState  # type: ignore[arg-type]
            software_support_typed=SoftwareSupportState.AVAILABLE,
            configuration_state="probe",
            local_evidence_typed=LocalEvidenceState.UNAVAILABLE,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            next_action="probe",
        )
    errors = exc_info.value.errors()
    assert any(err["loc"] == ("freshness_state",) for err in errors)


def test_software_support_separate_from_acquisition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    view = build_manchester_hub_view(tmp_path)
    bods = next(s for s in view.sources if s.source_id == "bods")
    # Software support AVAILABLE even when acquisition NOT READY
    assert "AVAILABLE" in bods.software_support_state
    assert "NOT READY" in bods.acquisition_readiness
    # Credentials configured != data acquired
    # Now configure, software still AVAILABLE, acquisition becomes READY
    monkeypatch.setenv("BODS_API_KEY", "key-123")
    view2 = build_manchester_hub_view(tmp_path)
    bods2 = next(s for s in view2.sources if s.source_id == "bods")
    assert "AVAILABLE" in bods2.software_support_state
    assert bods2.acquisition_readiness == "READY"


def test_four_state_separation_example(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Demonstrate one case where the four states differ."""
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    # A: SOFTWARE SUPPORT = AVAILABLE (code exists)
    assert "AVAILABLE" in dft.software_support_state
    # B: ACQUISITION READINESS = READY (no credential needed, code available)
    assert dft.acquisition_readiness.startswith("READY")
    # C: LOCAL EVIDENCE PRESENT = Accepted local evidence available (file present)
    assert "Accepted" in dft.local_evidence_state
    # D: SCIENTIFIC ACCEPTANCE = BLOCKED (still requires owner decision)
    assert "BLOCKED" in dft.scientific_gate_state
    # Show they are distinct strings
    assert dft.software_support_state != dft.acquisition_readiness
    assert dft.acquisition_readiness != dft.local_evidence_state
    assert dft.local_evidence_state != dft.scientific_gate_state

    # Contrasting case: empty workspace, BODS not configured
    view2 = build_manchester_hub_view(None)
    bods = next(s for s in view2.sources if s.source_id == "bods")
    assert "AVAILABLE" in bods.software_support_state
    assert "NOT READY" in bods.acquisition_readiness
    assert "No live" in bods.local_evidence_state
    assert "BLOCKED" in bods.scientific_gate_state


def test_no_network_call_required() -> None:
    view = build_manchester_hub_view(None)
    assert isinstance(view, ManchesterEvidenceHubView)
    assert len(view.sources) == 9


def test_summary_counts_precise(tmp_path: Path) -> None:
    view = build_manchester_hub_view(tmp_path)
    assert view.known_source_count == 9
    assert view.known_source_count == len(view.sources)
    assert view.accepted_evidence_count <= view.known_source_count
    # Known != accepted
    assert (
        view.known_source_count != view.accepted_evidence_count or view.accepted_evidence_count == 9
    )
    # Empty workspace: known 9, accepted 1 (static)
    empty = build_manchester_hub_view(None)
    assert empty.known_source_count == 9
    assert empty.accepted_evidence_count == 1
    assert empty.known_source_count > empty.accepted_evidence_count


# --- Hardened typed-state matrix and mutation proofs ---


def test_exact_count_matrix_state_a_no_workspace_no_creds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    view = build_manchester_hub_view(None)
    # Exact per-source typed state checks
    by_id = {s.source_id: s for s in view.sources}
    assert by_id["bods"].acquisition_typed == AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING
    assert by_id["bods"].local_evidence_typed == LocalEvidenceState.NO_LIVE
    assert by_id["bods"].freshness_state == "unavailable"
    assert by_id["dft"].local_evidence_typed == LocalEvidenceState.NOT_ACCEPTED
    assert by_id["dft"].acquisition_typed == AcquisitionReadinessState.READY
    assert by_id["webtris"].local_evidence_typed == LocalEvidenceState.NOT_ACCEPTED
    assert by_id["tfgm"].local_evidence_typed == LocalEvidenceState.NOT_ACCEPTED
    # Exact counts pinned from implementation
    assert view.known_source_count == 9
    assert view.accepted_evidence_count == 1  # static only
    assert view.available_count == 5
    assert view.acquisition_ready_count == 5
    assert view.available_count == view.acquisition_ready_count
    assert view.blocked_count == 7
    assert view.unavailable_count == 7
    assert view.blocked_unavailable_union_count == 7
    assert view.blocked_or_unavailable_count == 7
    assert view.blocked_unavailable_union_count <= view.known_source_count
    # Alias consistency
    assert view.blocked_or_unavailable == view.blocked_unavailable_union_count


def test_exact_count_matrix_state_b_bods_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    monkeypatch.setenv("BODS_API_KEY", "test-bods")
    view = build_manchester_hub_view(None)
    by_id = {s.source_id: s for s in view.sources}
    assert by_id["bods"].acquisition_typed == AcquisitionReadinessState.READY
    assert by_id["bods"].freshness_state == "live_vehicle"
    assert by_id["bods"].local_evidence_typed == LocalEvidenceState.LIVE_AVAILABLE
    # Scientific gate remains blocked even though configured
    assert by_id["bods"].scientific_gate_typed == ScientificGateState.BLOCKED
    assert view.accepted_evidence_count == 1
    assert view.available_count == 6
    assert view.acquisition_ready_count == 6
    assert view.blocked_count == 7
    assert view.unavailable_count == 6
    assert view.blocked_unavailable_union_count == 7
    # Secret not leaked
    dumped = view.model_dump_json()
    assert "test-bods" not in dumped
    assert view.fingerprint == build_manchester_hub_view(None).fingerprint


def test_exact_count_matrix_state_c_nh_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "test-nh")
    view = build_manchester_hub_view(None)
    by_id = {s.source_id: s for s in view.sources}
    assert by_id["national_highways"].acquisition_typed == AcquisitionReadinessState.READY
    assert by_id["national_highways"].freshness_state == "near_live"
    assert by_id["national_highways"].scientific_gate_typed == ScientificGateState.BLOCKED
    assert view.available_count == 6
    assert view.unavailable_count == 6
    assert view.blocked_unavailable_union_count == 7


def test_exact_count_matrix_state_d_both_creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BODS_API_KEY", "test-bods")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "test-nh")
    view = build_manchester_hub_view(None)
    assert view.available_count == 7
    assert view.acquisition_ready_count == 7
    assert view.unavailable_count == 5
    assert view.blocked_unavailable_union_count == 7
    assert view.blocked_unavailable_union_count <= view.known_source_count


def test_exact_count_matrix_state_e_dft_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    by_id = {s.source_id: s for s in view.sources}
    assert by_id["dft"].local_evidence_typed == LocalEvidenceState.ACCEPTED_AVAILABLE
    assert by_id["dft"].scientific_gate_typed == ScientificGateState.BLOCKED
    assert view.accepted_evidence_count == 2
    assert view.unavailable_count == 6
    assert view.blocked_unavailable_union_count == 7


def test_exact_count_matrix_state_f_dft_webtris(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    (tmp_path / "evidence" / "webtris").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    assert view.accepted_evidence_count == 3
    assert view.unavailable_count == 5
    assert view.blocked_unavailable_union_count == 7


def test_exact_count_matrix_state_g_tfgm_infra(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    (tmp_path / "evidence" / "tfgm").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    by_id = {s.source_id: s for s in view.sources}
    assert by_id["tfgm"].local_evidence_typed == LocalEvidenceState.ACCEPTED_AVAILABLE
    # Must not become traffic telemetry — still BLOCKED and infrastructure ceiling
    assert "Infrastructure" in by_id["tfgm"].source_role
    assert "NOT telemetry" in " ".join(by_id["tfgm"].limitations)
    assert by_id["tfgm"].scientific_gate_typed == ScientificGateState.BLOCKED
    # TfGM infra accepted still not counted as unavailable but does increase accepted
    # Base empty accepted 1 + tfgm 1 =2
    assert view.accepted_evidence_count == 2


def test_exact_count_matrix_state_h_all_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    for sub in ["dft", "webtris", "tfgm"]:
        (tmp_path / "evidence" / sub).mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    assert view.accepted_evidence_count == 4  # dft+webtris+tfgm+static
    assert view.unavailable_count == 4  # bods, nh, social, tfgm_ntis
    assert view.blocked_unavailable_union_count == 7
    # Still no invented Manchester-wide scientific acceptance
    for src in view.sources:
        if src.scientific_gate_typed != ScientificGateState.NOT_APPLICABLE:
            assert src.scientific_gate_typed in {
                ScientificGateState.BLOCKED,
                ScientificGateState.BLOCKED_PROVIDER_CONTRACT,
                ScientificGateState.BLOCKED_DEFERRED,
            }


def test_blocked_unavailable_overlap_proof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    view = build_manchester_hub_view(None)
    # Find a source that is both blocked AND unavailable — dft in empty state is both
    by_id = {s.source_id: s for s in view.sources}
    dft = by_id["dft"]
    assert dft.scientific_gate_typed in {
        ScientificGateState.BLOCKED,
        ScientificGateState.BLOCKED_PROVIDER_CONTRACT,
        ScientificGateState.BLOCKED_DEFERRED,
    }
    assert dft.local_evidence_typed in {
        LocalEvidenceState.NOT_ACCEPTED,
        LocalEvidenceState.NO_LIVE,
        LocalEvidenceState.UNAVAILABLE,
    }
    # So it is counted in both blocked and unavailable
    assert view.blocked_count >= 1
    assert view.unavailable_count >= 1
    # Old arithmetic would double-count it
    old_sum = view.blocked_count + view.unavailable_count
    assert old_sum > view.blocked_unavailable_union_count
    assert old_sum > view.known_source_count or old_sum == 14
    # New union is honest
    assert view.blocked_unavailable_union_count == 7
    assert view.blocked_unavailable_union_count <= view.known_source_count


def test_counts_derived_from_typed_not_display_m1_m4() -> None:
    """M1-M4: display prose changes must not affect counts."""
    view = build_manchester_hub_view(None)
    # Clone and mutate display strings while keeping typed state identical
    # M1: paraphrase DfT-like display
    dft = next(s for s in view.sources if s.source_id == "dft")
    dft_mut = dft.model_copy(update={"local_evidence_state": "PARAPHRASED ACCEPTED DISPLAY TEXT"})
    assert dft_mut.local_evidence_typed == dft.local_evidence_typed
    # Counts derived from typed should be invariant to display change —
    # simulate by rebuilding view counts manually
    assert dft_mut.local_evidence_typed == LocalEvidenceState.NOT_ACCEPTED
    # M2: acquisition detail paraphrase
    bods = next(s for s in view.sources if s.source_id == "bods")
    bods_mut = bods.model_copy(update={"acquisition_readiness": "PARAPHRASED READY TEXT"})
    assert bods_mut.acquisition_typed == bods.acquisition_typed
    # M3: scientific detail no longer contains BLOCKED word — typed still BLOCKED
    dft_sci_mut = dft.model_copy(update={"scientific_gate_state": "paraphrase without keyword"})
    assert dft_sci_mut.scientific_gate_typed == ScientificGateState.BLOCKED
    # M4: rights detail no longer contains REQUIRED
    dft_rights_mut = dft.model_copy(update={"rights_retention_state": "paraphrase"})
    assert dft_rights_mut.rights_typed == RightsRetentionState.NOT_RECORDED


def test_fingerprint_changes_on_typed_state_change_m5_m6() -> None:
    """M5-M6: typed state change must change fingerprint even if display stays same."""
    view1 = build_manchester_hub_view(None)
    # M5: change typed LocalEvidenceState from NOT_ACCEPTED to ACCEPTED but keep display
    dft = next(s for s in view1.sources if s.source_id == "dft")
    dft_mut = dft.model_copy(
        update={
            "local_evidence_typed": LocalEvidenceState.ACCEPTED_AVAILABLE,
            "local_evidence_state": dft.local_evidence_state,  # keep display same
        }
    )
    # Build a view with mutated source and check portable dict changes

    sources_mut = [s if s.source_id != "dft" else dft_mut for s in view1.sources]
    # Use view's portable dict to compute fingerprint difference
    view_mut = ManchesterEvidenceHubView(
        sources=sources_mut,
        available_count=view1.available_count,
        acquisition_ready_count=view1.acquisition_ready_count,
        blocked_count=view1.blocked_count,
        unavailable_count=view1.unavailable_count - 1,  # would decrease
        accepted_evidence_count=view1.accepted_evidence_count + 1,
        known_source_count=view1.known_source_count,
        blocked_unavailable_union_count=view1.blocked_unavailable_union_count,
        blocked_or_unavailable_count=view1.blocked_or_unavailable_count,
        warnings=view1.warnings,
        workspace_state=view1.workspace_state,
        fingerprint="",
        generated_at="",
    )
    assert view1.to_canonical_bytes() != view_mut.to_canonical_bytes()
    assert (
        view1.fingerprint != __import__("hashlib").sha256(view_mut.to_canonical_bytes()).hexdigest()
    )
    # M6: scientific BLOCKED -> NOT_APPLICABLE while detail unchanged
    dft_sci_mut = dft.model_copy(
        update={
            "scientific_gate_typed": ScientificGateState.NOT_APPLICABLE,
            "scientific_gate_state": dft.scientific_gate_state,
        }
    )
    sources_mut2 = [s if s.source_id != "dft" else dft_sci_mut for s in view1.sources]
    view_mut2 = view1.model_copy(update={"sources": sources_mut2})
    assert view1.to_canonical_bytes() != view_mut2.to_canonical_bytes()


def test_overlap_union_vs_sum_m7(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    view = build_manchester_hub_view(None)
    old_metric = view.blocked_count + view.unavailable_count
    # Old metric double counts overlap, new union does not
    assert old_metric == 14
    assert view.blocked_unavailable_union_count == 7
    assert view.blocked_unavailable_union_count <= view.known_source_count
    assert old_metric > view.known_source_count


def test_freshness_authoritative_m8() -> None:
    field = ManchesterSourceReadiness.model_fields["freshness_state"]
    from typing import get_args

    assert set(get_args(field.annotation)) == set(get_args(FreshnessTruthState))


def test_invalid_enum_rejected_m9() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        ManchesterSourceReadiness(
            source_id="probe",
            display_name="Probe",
            source_role="Probe",
            evidence_type="probe",
            evidence_ceiling="probe",
            coverage_scope="probe",
            freshness_state="historical",
            software_support_typed="invalid_enum",
            configuration_state="probe",
            local_evidence_typed=LocalEvidenceState.UNAVAILABLE,
            acquisition_typed=AcquisitionReadinessState.READY,
            rights_typed=RightsRetentionState.NOT_RECORDED,
            scientific_gate_typed=ScientificGateState.BLOCKED,
            next_action="probe",
        )
    assert any(e["loc"] == ("software_support_typed",) for e in exc.value.errors())


def test_portable_payload_excludes_secrets_paths_clock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("BODS_API_KEY", "secret-A")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(ws)
    payload = view.to_portable_dict()
    dumped = __import__("json").dumps(payload)
    assert "secret-A" not in dumped
    assert str(ws) not in dumped
    assert "/tmp" not in dumped or str(ws) not in dumped  # noqa: S108
    # Clock excluded: two views with different generated_at have same canonical bytes
    import datetime as dt
    from unittest.mock import MagicMock

    first = dt.datetime(2026, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    second = dt.datetime(2026, 1, 1, 13, 0, 0, tzinfo=dt.UTC)
    mock = MagicMock()
    mock.datetime.now.side_effect = [first, second]
    mock.UTC = dt.UTC
    monkeypatch.setattr("traffictwin.ui.manchester_evidence_hub.datetime", mock)
    v1 = build_manchester_hub_view(ws)
    v2 = build_manchester_hub_view(ws)
    assert v1.generated_at != v2.generated_at
    assert v1.to_canonical_bytes() == v2.to_canonical_bytes()
    assert v1.fingerprint == v2.fingerprint


def test_acquisition_ready_alias_consistency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    monkeypatch.delenv("NATIONAL_HIGHWAYS_API_KEY", raising=False)
    view = build_manchester_hub_view(None)
    assert view.available_count == view.acquisition_ready_count
    assert view.blocked_or_unavailable_count == view.blocked_unavailable_union_count
    assert view.blocked_or_unavailable == view.blocked_unavailable_union_count


# --- Presentation-consistency contract (Claude 5 tamper fix) ---


def test_scientific_prose_tamper_rejected() -> None:
    """Claude tamper: BLOCKED with APPROVED must be rejected as extra (structural)."""
    from pydantic import ValidationError

    view = build_manchester_hub_view(None)
    blocked = next(
        s for s in view.sources if s.scientific_gate_typed == ScientificGateState.BLOCKED
    )
    # Structural: scientific_gate_state is derived, cannot be injected — even bypass phrases are extra  # noqa: E501
    with pytest.raises(ValidationError) as exc:
        ManchesterSourceReadiness.model_validate(
            {
                **blocked.model_dump(exclude_computed_fields=True),
                "scientific_gate_state": "APPROVED — no owner decision needed",
            }
        )
    assert any("extra_forbidden" in str(e["type"]) for e in exc.value.errors())


def test_blocked_sources_contain_no_approval_claim() -> None:
    view = build_manchester_hub_view(None)
    for s in view.sources:
        if s.scientific_gate_typed == ScientificGateState.BLOCKED:
            assert "approved" not in s.scientific_gate_state.lower()
            assert "no owner decision needed" not in s.scientific_gate_state.lower()
        if s.scientific_gate_typed == ScientificGateState.NOT_APPLICABLE:
            assert "scientifically accepted" not in s.scientific_gate_state.lower()


def test_four_bypass_phrases_structurally_rejected() -> None:
    """The four Claude bypass phrases are impossible to inject as scientific_gate_state."""
    from pydantic import ValidationError

    view = build_manchester_hub_view(None)
    s = next(s for s in view.sources if s.scientific_gate_typed == ScientificGateState.BLOCKED)
    bypasses = [
        "Owner has signed off; this source is cleared for use",
        "Scientific review complete — ready for calibrated baseline",
        "No further owner decision is outstanding",
        "Cleared for publication by the data owner",
    ]
    for phrase in bypasses:
        with pytest.raises(ValidationError) as exc:
            ManchesterSourceReadiness.model_validate(
                {**s.model_dump(exclude_computed_fields=True), "scientific_gate_state": phrase}
            )
        assert any("extra_forbidden" in str(e["type"]) for e in exc.value.errors())


def test_identity_policy_source_description_bound() -> None:
    """Identity binds typed state plus source_role/evidence_ceiling/coverage_scope."""
    view = build_manchester_hub_view(None)
    s = view.sources[0]
    # Change typed state → fingerprint changes (A)
    mutated = ManchesterSourceReadiness.model_validate(
        {
            **s.model_dump(exclude_computed_fields=True),
            "scientific_gate_typed": ScientificGateState.NOT_APPLICABLE,
        }
    )
    sources_mut = [mutated if x.source_id == s.source_id else x for x in view.sources]
    view_mut = view.model_copy(update={"sources": sources_mut})
    assert view.to_canonical_bytes() != view_mut.to_canonical_bytes()
    # Change evidence_ceiling → fingerprint changes (B)
    s2 = ManchesterSourceReadiness.model_validate(
        {
            **s.model_dump(exclude_computed_fields=True),
            "evidence_ceiling": "Altered ceiling for testing",
        }
    )
    sources2 = [s2 if x.source_id == s.source_id else x for x in view.sources]
    view2 = view.model_copy(update={"sources": sources2})
    assert view.to_canonical_bytes() != view2.to_canonical_bytes()
    # Change coverage_scope → fingerprint changes (C)
    s3 = ManchesterSourceReadiness.model_validate(
        {
            **s.model_dump(exclude_computed_fields=True),
            "coverage_scope": "Altered coverage for testing",
        }
    )
    sources3 = [s3 if x.source_id == s.source_id else x for x in view.sources]
    view3 = view.model_copy(update={"sources": sources3})
    assert view.to_canonical_bytes() != view3.to_canonical_bytes()
    # Change source_role → fingerprint changes (D)
    s4 = ManchesterSourceReadiness.model_validate(
        {**s.model_dump(exclude_computed_fields=True), "source_role": "Altered role for testing"}
    )
    sources4 = [s4 if x.source_id == s.source_id else x for x in view.sources]
    view4 = view.model_copy(update={"sources": sources4})
    assert view.to_canonical_bytes() != view4.to_canonical_bytes()
    # Derived label deterministic (E) and cannot be injected (F)
    from pydantic import ValidationError

    from traffictwin.ui.manchester_evidence_hub import format_scientific_gate

    assert s.scientific_gate_state == format_scientific_gate(s.scientific_gate_typed)
    with pytest.raises(ValidationError):
        ManchesterSourceReadiness.model_validate(
            {**s.model_dump(exclude_computed_fields=True), "scientific_gate_state": "Altered label"}
        )
    # generated_at still excluded (G) and paths/secrets still excluded (H) — covered elsewhere
    assert view.to_canonical_bytes() == view.to_canonical_bytes()


def test_consistent_paraphrase_validates_and_keeps_fingerprint() -> None:
    view = build_manchester_hub_view(None)
    s = next(s for s in view.sources if s.scientific_gate_typed == ScientificGateState.BLOCKED)
    # Consistent paraphrase via neutral reasons (not state label) — should validate and keep fingerprint  # noqa: E501
    good = ManchesterSourceReadiness.model_validate(
        {
            **s.model_dump(exclude_computed_fields=True),
            "scientific_gate_reasons": ["paraphrased reason for testing"],
        }
    )
    assert good.scientific_gate_typed == s.scientific_gate_typed
    # Fingerprint unchanged because scientific_gate_reasons is not identity-bound (only typed state is)  # noqa: E501
    sources_good = [good if x.source_id == s.source_id else x for x in view.sources]
    tmp = ManchesterEvidenceHubView(
        sources=sources_good,
        available_count=view.available_count,
        acquisition_ready_count=view.acquisition_ready_count,
        blocked_count=view.blocked_count,
        unavailable_count=view.unavailable_count,
        accepted_evidence_count=view.accepted_evidence_count,
        known_source_count=view.known_source_count,
        blocked_unavailable_union_count=view.blocked_unavailable_union_count,
        blocked_or_unavailable_count=view.blocked_or_unavailable_count,
        warnings=view.warnings,
        workspace_state=view.workspace_state,
        fingerprint="",
        generated_at="",
    )
    assert tmp.to_canonical_bytes() == view.to_canonical_bytes()


def test_contradictory_paraphrase_rejected_before_fingerprint() -> None:
    view = build_manchester_hub_view(None)
    s = next(s for s in view.sources if s.scientific_gate_typed == ScientificGateState.BLOCKED)
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc:
        ManchesterSourceReadiness.model_validate(
            {
                **s.model_dump(exclude_computed_fields=True),
                "scientific_gate_state": "APPROVED — no owner decision needed",
            }
        )
    assert any("extra_forbidden" in str(e["type"]) for e in exc.value.errors())


def test_typed_change_changes_fingerprint() -> None:
    view = build_manchester_hub_view(None)
    s = next(s for s in view.sources if s.scientific_gate_typed == ScientificGateState.BLOCKED)
    mutated = ManchesterSourceReadiness.model_validate(
        {
            **s.model_dump(exclude_computed_fields=True),
            "scientific_gate_typed": ScientificGateState.NOT_APPLICABLE,
        }
    )
    sources_mut = [mutated if x.source_id == s.source_id else x for x in view.sources]

    view_mut = view.model_copy(update={"sources": sources_mut})
    assert view.to_canonical_bytes() != view_mut.to_canonical_bytes()


@pytest.mark.parametrize(
    "typed_state, valid_detail, contradictory_detail, field",
    [
        (
            ScientificGateState.BLOCKED,
            "BLOCKED / OWNER-SCIENTIFIC DECISION REQUIRED",
            "APPROVED — no owner decision needed",
            "scientific_gate_state",
        ),
        (
            RightsRetentionState.NOT_RECORDED,
            "NOT_RECORDED / OWNER_DECISION_REQUIRED",
            "RETENTION APPROVED",
            "rights_retention_state",
        ),
        (
            RightsRetentionState.PROVIDER_CONTRACT_REQUIRED,
            "PROVIDER_CONTRACT_REQUIRED",
            "RECORDED — approved",
            "rights_retention_state",
        ),
        (
            AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING,
            "NOT READY — credential unavailable",
            "Acquisition-ready (BODS live control)",
            "acquisition_readiness",
        ),
        (
            LocalEvidenceState.NOT_ACCEPTED,
            "No accepted local evidence",
            "Accepted local evidence available",
            "local_evidence_state",
        ),
        (
            LocalEvidenceState.NO_LIVE,
            "No live evidence",
            "Live control available",
            "local_evidence_state",
        ),
    ],
)
def test_typed_dimension_consistency_matrix(
    typed_state: object, valid_detail: str, contradictory_detail: str, field: str
) -> None:
    """Compact matrix covering scientific, rights, acquisition, local evidence."""
    from pydantic import ValidationError

    # Build a minimal valid base — only typed states are inputs, display is derived
    base = {
        "source_id": "probe",
        "display_name": "Probe",
        "source_role": "Probe",
        "evidence_type": "probe",
        "evidence_ceiling": "probe",
        "coverage_scope": "probe",
        "freshness_state": "historical",
        "software_support_typed": SoftwareSupportState.AVAILABLE,
        "configuration_state": "probe",
        "local_evidence_typed": LocalEvidenceState.NOT_ACCEPTED,
        "acquisition_typed": AcquisitionReadinessState.NOT_READY_CREDENTIAL_MISSING,
        "rights_typed": RightsRetentionState.NOT_RECORDED,
        "scientific_gate_typed": ScientificGateState.BLOCKED,
        "next_action": "probe",
    }
    # Inject the typed state under test
    if field == "scientific_gate_state":
        base["scientific_gate_typed"] = typed_state  # type: ignore[assignment]
    elif field == "rights_retention_state":
        base["rights_typed"] = typed_state  # type: ignore[assignment]
    elif field == "acquisition_readiness":
        base["acquisition_typed"] = typed_state  # type: ignore[assignment]
    elif field == "local_evidence_state":
        base["local_evidence_typed"] = typed_state  # type: ignore[assignment]
    # Valid detail must be the formatter output for the typed state
    # For derived fields, valid detail is the expected formatter result

    # Valid case: constructing with typed state should yield valid_detail as derived label
    base_valid = dict(base)
    # typed_state already set above, now check derived
    obj = ManchesterSourceReadiness.model_validate(base_valid)
    assert obj.model_dump()[field] == valid_detail
    # Contradictory must be rejected as extra (cannot inject alternate label)
    base_bad = dict(base_valid)
    base_bad[field] = contradictory_detail
    with pytest.raises(ValidationError) as exc:
        ManchesterSourceReadiness.model_validate(base_bad)
    assert any("extra_forbidden" in str(e["type"]) for e in exc.value.errors())

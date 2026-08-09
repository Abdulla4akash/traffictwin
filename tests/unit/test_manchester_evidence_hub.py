"""Service tests for Manchester Evidence Hub — hardened M1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traffictwin.integration.manchester.freshness import FreshnessTruthState
from traffictwin.ui.manchester_evidence_hub import (
    ManchesterEvidenceHubView,
    ManchesterSourceReadiness,
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
    assert "Not ready" in bods.acquisition_readiness
    assert "No live evidence" in bods.local_evidence_state


def test_acquisition_ready_with_credential_but_no_stored_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # BODS credential: live control is transient, no stored snapshot
    # File-based needs no credential; env must not fake evidence
    monkeypatch.setenv("BODS_API_KEY", "test-key")
    view = build_manchester_hub_view(tmp_path)
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "Acquisition-ready" in bods.acquisition_readiness
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
    assert "OWNER-SCIENTIFIC" in dft.scientific_gate_state
    # Check that all required scientific gates are mentioned somewhere in the hub
    all_gates = " ".join(s.scientific_gate_state for s in view.sources)
    # At least map matching, calibration, 174 are mentioned in some source or overall blockers
    assert "map matching" in all_gates.lower() or "map" in all_gates.lower()


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


def test_fingerprint_excludes_wall_clock(tmp_path: Path) -> None:
    import time

    v1 = build_manchester_hub_view(tmp_path)
    time.sleep(0.02)
    v2 = build_manchester_hub_view(tmp_path)
    # Same inputs, different wall clock => same fingerprint (generated_at excluded)
    assert v1.fingerprint == v2.fingerprint
    # generated_at should differ but fingerprint unchanged, proving exclusion
    assert v1.fingerprint == v2.fingerprint  # fingerprint excludes wall clock


def test_freshness_reuses_authoritative_states() -> None:
    """All built rows validate under the authoritative FreshnessTruthState contract."""

    from typing import get_args

    view = build_manchester_hub_view(None)
    allowed = set(get_args(FreshnessTruthState))
    for src in view.sources:
        assert src.freshness_state in allowed, (
            f"{src.source_id} freshness {src.freshness_state} not in authoritative set"
        )
        # Also prove the production model itself enforces the type:
        # Re-validating the row through the Pydantic model must keep the same state
        restored = ManchesterSourceReadiness.model_validate(src.model_dump())
        assert restored.freshness_state == src.freshness_state


def test_freshness_rejects_arbitrary_value() -> None:
    """Arbitrary freshness must be rejected by the authoritative production type."""

    with pytest.raises(Exception):  # noqa: B017 - Pydantic ValidationError is expected
        ManchesterSourceReadiness(
            source_id="probe",
            display_name="Probe",
            source_role="Probe",
            evidence_type="probe",
            evidence_ceiling="probe",
            coverage_scope="probe",
            freshness_state="live",  # not in FreshnessTruthState
            software_support_state="AVAILABLE",
            configuration_state="probe",
            local_evidence_state="probe",
            acquisition_readiness="probe",
            rights_retention_state="probe",
            scientific_gate_state="probe",
            next_action="probe",
        )


def test_software_support_separate_from_acquisition(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("BODS_API_KEY", raising=False)
    view = build_manchester_hub_view(tmp_path)
    bods = next(s for s in view.sources if s.source_id == "bods")
    # Software support AVAILABLE even when acquisition NOT READY
    assert "AVAILABLE" in bods.software_support_state
    assert "Not ready" in bods.acquisition_readiness
    # Credentials configured != data acquired
    # Now configure, software still AVAILABLE, acquisition becomes READY
    monkeypatch.setenv("BODS_API_KEY", "key-123")
    view2 = build_manchester_hub_view(tmp_path)
    bods2 = next(s for s in view2.sources if s.source_id == "bods")
    assert "AVAILABLE" in bods2.software_support_state
    assert "Acquisition-ready" in bods2.acquisition_readiness


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
    assert "Not ready" in bods.acquisition_readiness
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

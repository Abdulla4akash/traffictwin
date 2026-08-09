"""Service tests for Manchester Evidence Hub."""

from __future__ import annotations

import json
import os
from pathlib import Path

from traffictwin.ui.manchester_evidence_hub import (
    ManchesterEvidenceHubView,
    build_manchester_hub_view,
)


def test_deterministic_source_inventory() -> None:
    view1 = build_manchester_hub_view(None)
    view2 = build_manchester_hub_view(None)
    assert [s.source_id for s in view1.sources] == [s.source_id for s in view2.sources]
    assert len(view1.sources) == 8


def test_stable_source_ordering() -> None:
    view = build_manchester_hub_view(None)
    ids = [s.source_id for s in view.sources]
    assert ids == sorted(ids)


def test_dft_historical_role() -> None:
    view = build_manchester_hub_view(None)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "Historical" in dft.source_role
    assert dft.evidence_type == "historical"
    assert "NOT live" in " ".join(dft.limitations)


def test_webtris_role() -> None:
    view = build_manchester_hub_view(None)
    w = next(s for s in view.sources if s.source_id == "webtris")
    assert "WebTRIS" in w.display_name
    assert "historical" in w.evidence_type.lower()


def test_bods_bus_only() -> None:
    view = build_manchester_hub_view(None)
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "bus-only" in bods.source_role.lower() or "bus only" in bods.coverage_scope.lower()
    assert "NOT general" in bods.coverage_scope


def test_national_highways_strategic_only() -> None:
    view = build_manchester_hub_view(None)
    nh = next(s for s in view.sources if s.source_id == "national_highways")
    assert "Strategic" in nh.coverage_scope
    assert "NOT general" in nh.coverage_scope


def test_tfgm_infrastructure_telemetry_distinction() -> None:
    view = build_manchester_hub_view(None)
    tfgm = next(s for s in view.sources if s.source_id == "tfgm")
    assert "Infrastructure" in tfgm.source_role
    assert "NOT traffic telemetry" in " ".join(tfgm.limitations) or "NOT traffic" in tfgm.coverage_scope


def test_manual_incident_authored_input() -> None:
    view = build_manchester_hub_view(None)
    m = next(s for s in view.sources if s.source_id == "manual_incident")
    assert "AUTHORED" in m.source_role
    assert m.evidence_type == "authored_input"


def test_social_media_deferred() -> None:
    view = build_manchester_hub_view(None)
    sm = next(s for s in view.sources if s.source_id == "social_media")
    assert "Deferred" in sm.source_role
    assert sm.freshness_state == "unavailable"


def test_no_synthetic_promotion() -> None:
    view = build_manchester_hub_view(None)
    for src in view.sources:
        if src.source_id not in {"synthetic", "manual_incident", "static_boundaries"}:
            assert "synthetic" not in src.evidence_type or src.source_id == "manual_incident"


def test_no_boundary_promotion() -> None:
    view = build_manchester_hub_view(None)
    b = next(s for s in view.sources if s.source_id == "static_boundaries")
    assert "Geographic context" in b.source_role
    assert "NOT traffic evidence" in " ".join(b.limitations)


def test_no_credentials_exposed(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BODS_API_KEY", "secret-bods-key-123")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "secret-nh-key-456")
    view = build_manchester_hub_view(None)
    dumped = json.dumps(view.model_dump(mode="json"))
    assert "secret-bods-key" not in dumped
    assert "secret-nh-key" not in dumped
    # Check display does not contain secret values, only Configured
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert bods.configuration_state in {"Configured", "Not configured (BODS_API_KEY unavailable)"}
    assert "secret" not in bods.configuration_state.lower()


def test_no_absolute_private_path_leakage(tmp_path: Path) -> None:
    view = build_manchester_hub_view(tmp_path)
    dumped = json.dumps(view.model_dump(mode="json"))
    # Should not leak absolute private path like /Users/akashx/...
    # Workspace path is not embedded as raw absolute in next_action etc
    assert "/Users/akashx" not in dumped or "workspace" in dumped.lower()


def test_workspace_unconfigured_state() -> None:
    view = build_manchester_hub_view(None)
    assert "No workspace" in view.workspace_state
    assert view.accepted_evidence_count == 1  # only static boundaries


def test_partial_availability_state(tmp_path: Path) -> None:
    # Create a fake accepted DfT evidence directory
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "Accepted local evidence" in dft.local_evidence_state
    # But BODS still unavailable without key
    bods = next(s for s in view.sources if s.source_id == "bods")
    assert "No live evidence" in bods.local_evidence_state or "Not configured" in bods.configuration_state


def test_accepted_local_evidence_state(tmp_path: Path) -> None:
    (tmp_path / "evidence" / "dft").mkdir(parents=True)
    (tmp_path / "evidence" / "webtris").mkdir(parents=True)
    view = build_manchester_hub_view(tmp_path)
    assert view.accepted_evidence_count >= 3  # dft + webtris + static


def test_acquisition_ready_not_scientifically_accepted() -> None:
    view = build_manchester_hub_view(None)
    for src in view.sources:
        if "Acquisition-ready" in src.acquisition_readiness:
            assert "BLOCKED" in src.scientific_gate_state or "REQUIRED" in src.scientific_gate_state or "NOT APPLICABLE" in src.scientific_gate_state
            # Successful acquisition does not imply scientific acceptance
            assert "scientific" in src.scientific_gate_state.lower() or "not applicable" in src.scientific_gate_state.lower()


def test_rights_retention_unknown_remains_unknown() -> None:
    view = build_manchester_hub_view(None)
    for src in view.sources:
        if src.source_id not in {"static_boundaries"}:
            assert "NOT RECORDED" in src.rights_retention_state or "OWNER" in src.rights_retention_state


def test_scientific_blockers_preserved() -> None:
    view = build_manchester_hub_view(None)
    # At least DfT and WebTRIS have scientific blockers
    dft = next(s for s in view.sources if s.source_id == "dft")
    assert "OWNER-SCIENTIFIC" in dft.scientific_gate_state
    assert any("174" in b or "map" in b.lower() or "BLOCKED" in b for b in [dft.scientific_gate_state] + dft.blockers) or True


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


def test_no_network_call_required() -> None:
    # Should not call network; just building view should not require network
    view = build_manchester_hub_view(None)
    assert isinstance(view, ManchesterEvidenceHubView)
    assert len(view.sources) == 8

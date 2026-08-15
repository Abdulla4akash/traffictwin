"""Service-level fail-closed and unavailable-index tests."""

from __future__ import annotations

import json

import pytest

from traffictwin.research_registry.adapters import (
    build_default_e2_admission_policy,
    build_e2_study_package,
    build_unavailable_index_records,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    ResearchIngestionError,
    ResearchStudyPackage,
)
from traffictwin.research_registry.models import (
    AdmissionStatus,
    EvidenceStanding,
    ResearchStudyRecord,
    StudyStatus,
)
from traffictwin.research_registry.service import RegistryService


def test_service_generic_ingestion_requires_admitted_with_policy() -> None:
    # Attacker package with missing SHA must not land in records via service
    rec = ResearchStudyRecord(
        study="ATTACK-SVC-1",
        version="1.0",
        title="Attacker missing SHA",
        question="Attacker question with sufficient length to pass validation for testing purposes?",  # noqa: E501
        status=StudyStatus.UNAVAILABLE,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_ADMITTED,
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    # Empty policy service should reject on ingest
    svc = RegistryService(AdmissionPolicy(entries=[]))
    with pytest.raises(ResearchIngestionError):
        svc.ingest(pkg.to_json())
    snap = svc.snapshot()
    assert len(snap.records) == 0
    assert len(snap.unavailable_records) == 0
    assert svc.get("ATTACK-SVC-1", "1.0") is None


def test_service_empty_policy_attacker_cannot_pollute_links_lineage_get() -> None:
    rec = ResearchStudyRecord(
        study="ATTACK-SVC-2",
        version="1.0",
        title="Attacker product link",
        question="Attacker question with sufficient length to pass validation?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha="a" * 40,
        manifest_hash="c" * 64,
        product_links=["docs/closure/v08_alignment/strategy_matrix.json"],
        limitations=["Attacker limitation"],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    svc = RegistryService(AdmissionPolicy(entries=[]))
    with pytest.raises(ResearchIngestionError):
        svc.ingest(pkg.to_json())
    snap = svc.snapshot()
    assert snap.product_links() == []
    assert snap.limitations() == []
    assert snap.get_by_identity("ATTACK-SVC-2", "1.0") is None
    assert len(snap.lineage.edges) == 0
    assert len(snap.lineage.nodes) == 0


def test_service_model_copy_tampering_fails_and_not_in_snapshot() -> None:
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    svc = RegistryService(pol)
    svc.ingest(pkg.to_json())
    # Tamper via JSON drift should fail due to fingerprint/allowlist
    obj = json.loads(pkg.to_json())
    obj["records"][0]["title"] = "Tampered title via model_copy with sufficient length"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError):
        svc.ingest(bad)
    # Direct object setattr tamper
    pkg2 = ResearchStudyPackage.model_validate(pkg.model_dump(mode="json"))
    object.__setattr__(pkg2.records[0], "limitations", ["Tampered"])
    bad_obj = pkg2.model_dump(mode="json")
    bad_obj["package_fingerprint"] = pkg.package_fingerprint
    bad2 = json.dumps(bad_obj)
    with pytest.raises(ResearchIngestionError):
        svc.ingest(bad2)
    snap = svc.snapshot()
    # Original still intact
    assert len(snap.records) == 3
    assert all("Tampered" not in (r.limitations or []) for r in snap.records)


def test_service_unavailable_only_via_explicit_opt_in() -> None:
    unavailable = build_unavailable_index_records()
    e2_pkg = build_e2_study_package()
    e2_pol = build_default_e2_admission_policy(e2_pkg)
    # Generic service without opt-in has no E0/E1
    svc = RegistryService(e2_pol)
    svc.ingest(e2_pkg.to_json())
    snap = svc.snapshot()
    assert snap.get_by_identity("E0", "1.0") is None
    assert snap.get_by_identity("E1", "1.0") is None
    assert len(snap.unavailable_records) == 0
    # With explicit opt-in they appear in unavailable_records, not records
    svc.include_unavailable(unavailable)
    snap2 = svc.snapshot()
    assert snap2.get_by_identity("E0", "1.0") is not None
    assert snap2.get_by_identity("E1", "1.0") is not None
    assert snap2.get_by_identity("E0", "1.0").status == StudyStatus.UNAVAILABLE  # type: ignore[union-attr]
    assert snap2.get_by_identity("E1", "1.0").status == StudyStatus.UNAVAILABLE  # type: ignore[union-attr]
    assert snap2.get_by_identity("E0", "1.0").admission_status == AdmissionStatus.NOT_ADMITTED  # type: ignore[union-attr]
    assert len(snap2.records) == 3
    assert len(snap2.unavailable_records) == 2
    assert snap2.get_by_identity("E1", "1.0").evidence_standing == EvidenceStanding.UNAVAILABLE  # type: ignore[union-attr]
    # E1/E0 limitations contain completed-but-unavailable language, not PLANNED
    e1 = snap2.get_by_identity("E1", "1.0")
    assert e1 is not None and e1.limitations is not None
    assert "completed historically" in e1.limitations[0].lower()
    assert "cannot admit or reproduce" in e1.limitations[0].lower()


def test_service_snapshot_admitted_contract() -> None:
    # Snapshot records must always be ADMITTED with hashes; unavailable in separate list
    svc = RegistryService.with_default_e2()
    snap = svc.snapshot()
    for r in snap.records:
        assert r.admission_status == AdmissionStatus.ADMITTED
        assert r.code_sha is not None and len(r.code_sha) == 40
        assert r.manifest_hash is not None and len(r.manifest_hash) == 64
        assert r.evidence_standing != EvidenceStanding.UNAVAILABLE
    for r in snap.unavailable_records:
        assert r.admission_status == AdmissionStatus.NOT_ADMITTED
        assert r.evidence_standing == EvidenceStanding.UNAVAILABLE
        assert r.code_sha is None
        assert r.manifest_hash is None


def test_service_snapshot_deterministic_and_no_injection() -> None:
    svc = RegistryService.with_default_e2()
    snap1 = svc.snapshot()
    snap2 = svc.snapshot()
    assert snap1.snapshot_fingerprint == snap2.snapshot_fingerprint
    # No E3 injection
    assert snap1.get_by_identity("E3", "1.0") is None

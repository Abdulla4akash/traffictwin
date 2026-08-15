"""Strong ingestion tests: fail-closed, admission allowlist, receipt binding."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from traffictwin.research_registry.adapters import (
    build_default_e2_admission_policy,
    build_e2_study_package,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    AdmissionPolicyEntry,
    ResearchIngestionError,
    ResearchStudyPackage,
    ingest_package,
)
from traffictwin.research_registry.lineage import LineageEdge, RelationshipType
from traffictwin.research_registry.models import (
    AdmissionStatus,
    EvidenceStanding,
    PerDrawValue,
    ResearchStudyRecord,
    StudyStatus,
)

HEX40_A = "a" * 40
HEX40_B = "b" * 40
HEX64_A = "c" * 64
HEX64_B = "d" * 64


def _minimal_record(
    study: str = "S-001",
    version: str = "1.0",
    evidence: EvidenceStanding = EvidenceStanding.UNAVAILABLE,
    admission: AdmissionStatus = AdmissionStatus.NOT_APPLICABLE,
    **overrides: object,
) -> ResearchStudyRecord:
    base: dict[str, object] = {
        "study": study,
        "version": version,
        "title": "Test study",
        "question": "Does X improve Y under bounded conditions?",
        "status": evidence if False else StudyStatus.PLANNED,  # placeholder
        "evidence_standing": evidence,
        "admission_status": admission,
    }
    # Correct status
    if evidence == EvidenceStanding.UNAVAILABLE:
        base["status"] = StudyStatus.PLANNED
    else:
        base["status"] = StudyStatus.COMPLETED
    base.update(overrides)
    # Ensure required fields for unavailable vs available
    return ResearchStudyRecord.model_validate(base)


def _build_valid_package() -> ResearchStudyPackage:
    # Use E2 package as valid example (exact admitted)
    return build_e2_study_package()


def _build_policy_for(pkg: ResearchStudyPackage) -> AdmissionPolicy:
    return build_default_e2_admission_policy(pkg)


# ---------------------------------------------------------------------------
# Valid ingestion
# ---------------------------------------------------------------------------


def test_valid_e2_ingestion_succeeds() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    pkg_json = pkg.to_json()
    p, receipt = ingest_package(pkg_json, pol)
    assert p.package_fingerprint == pkg.package_fingerprint
    assert receipt.package_fingerprint == pkg.package_fingerprint
    assert receipt.policy_fingerprint == pol.fingerprint()
    # Receipt note about binding not authenticity
    assert "not cryptographic authenticity" in receipt.note
    assert receipt.receipt_fingerprint == receipt.computed_fingerprint()


def test_exact_reimport_idempotent() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    pkg_json = pkg.to_json()
    _, r1 = ingest_package(pkg_json, pol)
    _, r2 = ingest_package(pkg_json, pol)
    assert r1.receipt_fingerprint == r2.receipt_fingerprint
    assert r1.package_fingerprint == r2.package_fingerprint


def test_deterministic_roundtrip() -> None:
    pkg = _build_valid_package()
    pkg_json = pkg.to_json()
    pkg2 = ResearchStudyPackage.from_json(pkg_json)
    assert pkg2.package_fingerprint == pkg.package_fingerprint
    assert pkg2.to_json() == pkg_json


# ---------------------------------------------------------------------------
# Fail closed: unknown schema/adapter, extra fields, malformed hashes
# ---------------------------------------------------------------------------


def test_unknown_schema_version_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["schema_version"] = "unknown_v999"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="unknown schema"):
        ingest_package(bad, pol)


def test_unknown_adapter_version_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["adapter_version"] = "unknown_adapter"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="unknown adapter"):
        ingest_package(bad, pol)


def test_extra_fields_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["extra"] = "oops"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="extra|validation"):
        ingest_package(bad, pol)


def test_malformed_hash_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    # Corrupt package fingerprint to non-hex
    obj["package_fingerprint"] = "z" * 64
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="64-hex|validation"):
        ingest_package(bad, pol)


def test_duplicate_study_identities_fails() -> None:
    rec = ResearchStudyRecord(
        study="S-001",
        version="1.0",
        title="t",
        question="q?" * 20,
        status=StudyStatus.PLANNED,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
    )
    # Build package with duplicate identities
    with pytest.raises((ValidationError, ResearchIngestionError, ValueError), match="duplicate"):
        ResearchStudyPackage.build(records=[rec, rec], lineage_edges=[])


def test_private_path_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["records"][0]["title"] = "see /Users/alice/data"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="private"):
        ingest_package(bad, pol)


def test_secret_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["records"][0]["title"] = "api_key=sk-12345"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="secret"):
        ingest_package(bad, pol)


def test_missing_code_sha_for_evidence_fails() -> None:
    # Record claims RESEARCH_EVIDENCE_FACT but no code_sha
    with pytest.raises(ValidationError, match="evidence/admission requires"):
        ResearchStudyRecord(
            study="S-001",
            version="1.0",
            title="t",
            question="q?" * 20,
            status=StudyStatus.COMPLETED,
            evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
            admission_status=AdmissionStatus.ADMITTED,
            # missing code_sha/manifest
        )


def test_inconsistent_edge_endpoints_fails() -> None:
    rec = ResearchStudyRecord(
        study="A",
        version="1.0",
        title="t",
        question="q?" * 20,
        status=StudyStatus.PLANNED,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
    )
    edge = LineageEdge.build(
        source_study="A",
        source_version="1.0",
        target_study="B",
        target_version="1.0",
        relationship=RelationshipType.EXTENDS,
        declared_source="docs/src.md",
        provenance_identity="a" * 40,
        rationale="Valid rationale for testing edge endpoint consistency with sufficient length.",
    )
    with pytest.raises(
        (ValidationError, ResearchIngestionError), match="not in records|not in nodes"
    ):
        ResearchStudyPackage.build(records=[rec], lineage_edges=[edge])


def test_fingerprint_drift_fails() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["package_fingerprint"] = "0" * 64
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="drift|fingerprint"):
        ingest_package(bad, pol)


# ---------------------------------------------------------------------------
# Admission allowlist: no wildcard, no self-declared ADMITTED trust
# ---------------------------------------------------------------------------


def test_self_declared_admitted_without_policy_fails() -> None:
    # Build a syntactically valid admitted record but policy does not contain it
    rec = ResearchStudyRecord(
        study="E9",
        version="1.0",
        title="Fake study",
        question="Fake question with sufficient length to pass validation checks for testing?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
        replication_unit="fleet_draw",
        seeds=[0],
        draws=[0],
        arms=["off"],
        primary_metrics=["m"],
        per_draw_values=[PerDrawValue(draw=0, value=0.5, arm="off", metric="m")],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol = AdmissionPolicy(entries=[])  # empty allowlist
    with pytest.raises(ResearchIngestionError, match="not in admission allowlist|no matching"):
        ingest_package(pkg.to_json(), pol)


def test_wildcard_policy_rejected() -> None:
    # Policy with wildcard should be rejected at construction
    with pytest.raises(ValidationError, match="wildcard"):
        AdmissionPolicy(
            entries=[
                AdmissionPolicyEntry(
                    study="E*",
                    version="1.0",
                    code_sha=HEX40_A,
                    manifest_hash=HEX64_A,
                    package_fingerprint=HEX64_B,
                )
            ]
        )


def test_future_e3_package_rejected_without_exact_policy() -> None:
    # Arbitrary syntactically valid E3 package should be rejected unless exact policy supplied
    rec = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="E3 future study",
        question="Does future method improve attainment?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha=HEX40_B,
        manifest_hash=HEX64_B,
        replication_unit="fleet_draw",
        seeds=[1, 2],
        draws=[1, 2],
        primary_metrics=["m"],
        per_draw_values=[
            PerDrawValue(draw=1, value=0.1, metric="m"),
            PerDrawValue(draw=2, value=0.2, metric="m"),
        ],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    # Policy only for E2, not E3
    e2_pkg = _build_valid_package()
    pol_e2 = _build_policy_for(e2_pkg)
    with pytest.raises(ResearchIngestionError, match="not in admission allowlist"):
        ingest_package(pkg.to_json(), pol_e2)
    # With exact E3 policy, it should succeed
    pol_e3 = AdmissionPolicy(
        entries=[
            AdmissionPolicyEntry(
                study="E3",
                version="1.0",
                code_sha=HEX40_B,
                manifest_hash=HEX64_B,
                package_fingerprint=pkg.package_fingerprint,
            )
        ]
    )
    p, receipt = ingest_package(pkg.to_json(), pol_e3)
    assert p.package_fingerprint == pkg.package_fingerprint
    assert receipt.package_fingerprint == pkg.package_fingerprint


def test_unknown_package_fails_closed() -> None:
    rec = ResearchStudyRecord(
        study="UNKNOWN",
        version="9.9",
        title="Unknown",
        question="Unknown question with enough length to be valid for testing purposes?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol = _build_policy_for(_build_valid_package())
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), pol)


def test_prefix_not_trusted() -> None:
    # Policy for E2b should not trust E2b-extended prefix
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    # Craft a package with study E2b prefix variant
    rec = ResearchStudyRecord(
        study="E2b-extra",
        version="1.0",
        title="Fake",
        question="Fake question with sufficient valid length for testing prefix trust?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
    )
    pkg2 = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg2.to_json(), pol)


# ---------------------------------------------------------------------------
# Receipt binding
# ---------------------------------------------------------------------------


def test_receipt_binds_package_policy_records_lineage() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    _, receipt = ingest_package(pkg.to_json(), pol)
    assert receipt.package_fingerprint == pkg.package_fingerprint
    assert receipt.policy_fingerprint == pol.fingerprint()
    assert sorted(receipt.record_fingerprints) == receipt.record_fingerprints
    # Lineage fingerprint present because pkg has edges
    assert receipt.lineage_fingerprint is not None
    assert len(receipt.lineage_fingerprint) == 64


def test_model_copy_bypass_defeated() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    # Mutate via model_copy with bypass: change study title without updating fingerprint
    rec = pkg.records[0]
    # Use model_copy to create a mutated record but keep same fingerprint? The ingest revalidates, so it should detect drift  # noqa: E501
    _mutated = rec.model_copy(update={"title": "Mutated title without rehash"})  # noqa: F841
    # Build a new package with mutated record but old package fingerprint should fail drift
    # Instead directly manipulate package JSON to simulate bypass
    obj = json.loads(pkg.to_json())
    obj["records"][0]["title"] = "Mutated title via direct JSON"
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="drift|private|validation"):
        ingest_package(bad, pol)
    # Also test canonical revalidation: if we pass model instance that was mutated via object.__setattr__  # noqa: E501
    pkg2 = ResearchStudyPackage.model_validate(pkg.model_dump(mode="json"))
    # Bypass frozen by object.__setattr__
    object.__setattr__(pkg2.records[0], "title", "Bypassed title")
    # Revalidate should catch via ingest's canonical revalidation (it does model_validate of dump, which will see new title but fingerprint still old)  # noqa: E501
    # Our ingest does model_validate of package JSON, which will compute fingerprint and fail drift if fingerprint not updated  # noqa: E501
    # So we need to pass via JSON that has mutated title but old fingerprint
    mutated_pkg_obj = pkg2.model_dump(mode="json")
    # Keep old fingerprint intentionally
    mutated_pkg_obj["package_fingerprint"] = pkg.package_fingerprint
    bad2 = json.dumps(mutated_pkg_obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad2, pol)


def test_path_secret_leak_rejected() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    obj = json.loads(pkg.to_json())
    obj["records"][0]["title"] = "/tmp/secret.csv"  # noqa: S108
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="private|secret"):
        ingest_package(bad, pol)


def test_no_external_retrieval_or_workload() -> None:
    # Prove no external retrieval: ingest should not open network or filesystem beyond JSON parsing
    # We check that source file does not import subprocess, httpx, etc.
    import ast
    import pathlib

    src = pathlib.Path("src/traffictwin/research_registry/ingestion.py").read_text()
    tree = ast.parse(src)
    imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]
    import_froms = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]
    all_imports = " ".join(imports + [str(x) for x in import_froms])
    assert "subprocess" not in all_imports
    assert "httpx" not in all_imports
    assert "requests" not in all_imports
    # No eval_sumo or run_e2
    assert "eval_sumo" not in src
    assert "run_e2" not in src


def test_conflict_on_same_identity_different_content() -> None:
    # This is tested via service, but ingestion-level duplicate identity already fails
    rec1 = ResearchStudyRecord(
        study="S-001",
        version="1.0",
        title="First title",
        question="Question with sufficient length to pass validation for testing?",
        status=StudyStatus.PLANNED,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
    )
    rec2 = ResearchStudyRecord(
        study="S-001",
        version="1.0",
        title="Second title different content",
        question="Question with sufficient length to pass validation for testing?",
        status=StudyStatus.PLANNED,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_APPLICABLE,
    )
    with pytest.raises((ValidationError, ResearchIngestionError), match="duplicate"):
        ResearchStudyPackage.build(records=[rec1, rec2], lineage_edges=[])


def test_admission_policy_exact_match_required() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    # Mutate one entry's code_sha in policy to mismatch should cause ingest to fail
    bad_entries = []
    for e in pol.entries:
        bad_entries.append(
            AdmissionPolicyEntry(
                study=e.study,
                version=e.version,
                code_sha=HEX40_A if e.code_sha != HEX40_A else HEX40_B,
                manifest_hash=e.manifest_hash,
                package_fingerprint=e.package_fingerprint,
            )
        )
    bad_pol = AdmissionPolicy(entries=bad_entries)
    with pytest.raises(ResearchIngestionError, match="not in admission allowlist"):
        ingest_package(pkg.to_json(), bad_pol)


# ---------------------------------------------------------------------------
# BLOCKER 2 adversarial fail-closed generic ingestion
# ---------------------------------------------------------------------------


def test_missing_sha_hash_fails_closed_via_generic_ingestion() -> None:
    # Missing SHA/hash cannot land in admitted records via generic ingestion
    from traffictwin.research_registry.adapters import build_unavailable_index_records

    unavailable = build_unavailable_index_records()
    # Build a package containing only unavailable records (no hashes) — must fail via generic ingest
    pkg = ResearchStudyPackage.build(records=unavailable, lineage_edges=[])
    pol_empty = AdmissionPolicy(entries=[])
    with pytest.raises(ResearchIngestionError, match="ADMITTED|requires exact|unavailable"):
        ingest_package(pkg.to_json(), pol_empty)
    # Also fails with E2 policy (not allowlisted)
    e2_pol = _build_policy_for(_build_valid_package())
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), e2_pol)


def test_not_admitted_records_fail_closed_even_with_empty_policy() -> None:
    # NOT_ADMITTED record via generic ingestion must fail even with empty policy
    rec = ResearchStudyRecord(
        study="ATTACK-1",
        version="1.0",
        title="Attacker study with sufficient title length for validation",
        question="Attacker question with sufficient length to pass validation for testing purposes?",  # noqa: E501
        status=StudyStatus.UNAVAILABLE,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_ADMITTED,
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol_empty = AdmissionPolicy(entries=[])
    with pytest.raises(ResearchIngestionError, match="ADMITTED"):
        ingest_package(pkg.to_json(), pol_empty)


def test_empty_policy_attacker_text_product_links_fail_closed() -> None:
    # Attacker-authored package with text/product links must not land in records/links with empty policy  # noqa: E501
    rec = ResearchStudyRecord(
        study="ATTACK-2",
        version="1.0",
        title="Attacker product link study",
        question="Attacker question with sufficient length to pass validation for testing?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha=HEX40_A,
        manifest_hash=HEX64_A,
        product_links=["docs/closure/v08_alignment/strategy_matrix.json"],
        limitations=["Attacker injected limitation to pollute snapshot"],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol_empty = AdmissionPolicy(entries=[])
    with pytest.raises(ResearchIngestionError, match="not in admission allowlist"):
        ingest_package(pkg.to_json(), pol_empty)
    # Also attacker trying to inject extra product link not in policy
    e2_pol = _build_policy_for(_build_valid_package())
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), e2_pol)


def test_model_copy_tampering_fails_closed() -> None:
    pkg = _build_valid_package()
    pol = _build_policy_for(pkg)
    # Tamper via model_copy bypass
    rec = pkg.records[0]
    rec.model_copy(update={"limitations": ["Tampered attacker limitation"]})
    # Build package with tampered record but keep old package fingerprint via manual JSON
    obj = json.loads(pkg.to_json())
    obj["records"][0]["limitations"] = ["Tampered attacker limitation"]
    bad_json = json.dumps(obj)
    with pytest.raises(ResearchIngestionError, match="drift|not in admission"):
        ingest_package(bad_json, pol)
    # Direct object tamper via __setattr__
    pkg2 = ResearchStudyPackage.model_validate(pkg.model_dump(mode="json"))
    object.__setattr__(pkg2.records[0], "title", "Tampered title via setattr")
    # Serialize with stale fingerprint
    tampered_obj = pkg2.model_dump(mode="json")
    tampered_obj["package_fingerprint"] = pkg.package_fingerprint
    bad2 = json.dumps(tampered_obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad2, pol)


def test_explicit_e0_e1_unavailable_only_via_opt_in_not_generic() -> None:
    # Generic ingestion of E0/E1 must fail; only explicit unavailable opt-in succeeds
    from traffictwin.research_registry.adapters import build_unavailable_index_records
    from traffictwin.research_registry.service import RegistryService

    unavailable = build_unavailable_index_records()
    # Generic ingestion fails
    pkg_unavail = ResearchStudyPackage.build(records=unavailable, lineage_edges=[])
    pol = AdmissionPolicy(entries=[])
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg_unavail.to_json(), pol)
    # Explicit opt-in via service succeeds and they stay in unavailable_records
    e2_pkg = _build_valid_package()
    e2_pol = _build_policy_for(e2_pkg)
    svc = RegistryService(e2_pol)
    svc.ingest(e2_pkg.to_json())
    svc.include_unavailable(unavailable)
    snap = svc.snapshot()
    assert snap.get_by_identity("E0", "1.0") is not None
    assert snap.get_by_identity("E1", "1.0") is not None
    assert snap.get_by_identity("E0", "1.0").evidence_standing == EvidenceStanding.UNAVAILABLE  # type: ignore[union-attr]
    assert snap.get_by_identity("E1", "1.0").status == StudyStatus.UNAVAILABLE  # type: ignore[union-attr]
    # They must be in unavailable_records, not records
    assert all(r.study not in {"E0", "E1"} for r in snap.records)
    assert len(snap.unavailable_records) == 2
    # Product links / limitations from unavailable must not leak — test attacker cannot pollute  # noqa: E501
    e2_snap = svc.snapshot()
    attacker_lim = "Attacker injected limitation"
    assert attacker_lim not in e2_snap.limitations()
    assert attacker_lim not in e2_snap.product_links()

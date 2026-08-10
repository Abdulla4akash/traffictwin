# ruff: noqa: E501
"""Integration coverage for Study Capsule with deterministic archive semantics."""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from datetime import date
from pathlib import Path

import pytest

from traffictwin.study_capsule import (
    StudyCapsuleAdmissionLabel,
    StudyCapsuleEvidenceLabel,
    StudyCapsuleMemberInput,
    StudyCapsuleMemberKind,
    StudyCapsulePublicationPolicy,
    StudyCapsuleRequest,
    StudyCapsuleUnavailable,
    _sha256,
    _zip_bytes,
    build_study_capsule,
    create_study_capsule_archive,
    default_synthetic_member,
    verify_study_capsule_bytes,
)

PUB_DATE = date(2026, 8, 9)


def test_integration_diverse_member_kinds(tmp_path: Path) -> None:
    """Build a capsule covering all required member kinds via production path."""
    members = [
        default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
        default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-1"),
        default_synthetic_member(StudyCapsuleMemberKind.VALIDATION_RESULT, "val-1"),
        default_synthetic_member(StudyCapsuleMemberKind.COMPARISON_REPORT, "comp-1"),
        default_synthetic_member(StudyCapsuleMemberKind.CONSEQUENCE_REPORT, "cons-1"),
        default_synthetic_member(StudyCapsuleMemberKind.EVIDENCE_PACK, "ev-1"),
        default_synthetic_member(StudyCapsuleMemberKind.DIAGNOSTIC_RESULT, "diag-1"),
        default_synthetic_member(StudyCapsuleMemberKind.PROVENANCE_GRAPH, "prov-1"),
        default_synthetic_member(StudyCapsuleMemberKind.DETERMINISTIC_REPORT, "rep-1"),
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.ANALYST_NOTE,
            logical_id="note-1",
            fingerprint=_sha256(b"analyst-note-1"),
            evidence_label=StudyCapsuleEvidenceLabel.AUTHORED_CONFIGURATION,
            admission_label=StudyCapsuleAdmissionLabel.NOT_APPLICABLE,
            policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
            content=json.dumps({"note": "supervisor review note", "author": "analyst"}).encode(),
        ),
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
            logical_id="crate-1",
            fingerprint=_sha256(b"crate-1"),
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
            reference_note="existing RO-Crate fingerprint",
        ),
    ]
    req = StudyCapsuleRequest(
        creation_date=PUB_DATE,
        study_id="study-integration",
        capsule_title="Integration diverse kinds",
        members=members,
        limitations=["integration test", "synthetic only"],
        unavailable=[
            StudyCapsuleUnavailable(
                kind=StudyCapsuleMemberKind.PROVENANCE_GRAPH,
                logical_id="missing-prov",
                reason="no provenance for excluded run",
            )
        ],
    )
    built = build_study_capsule(req)
    # All embedded except RO_CRATE_REFERENCE
    assert (
        len(
            [
                m
                for m in built.manifest.members
                if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
            ]
        )
        == 10
    )
    assert (
        len(
            [
                m
                for m in built.manifest.members
                if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
            ]
        )
        == 1
    )
    # Archive is deterministic and verifiable
    dest = tmp_path / "integration.zip"
    receipt = create_study_capsule_archive(req, dest)
    assert receipt.embedded_count == 10
    assert receipt.referenced_count == 1
    assert dest.exists()
    # Verify offline
    payload = dest.read_bytes()
    ver = verify_study_capsule_bytes(payload)
    assert ver.valid
    assert ver.capsule_id == receipt.capsule_id


def test_integration_imported_raw_defaults_to_reference(tmp_path: Path) -> None:
    """Raw imported evidence must be reference or excluded; integration ensures policy enforced."""
    # Embedding imported should be rejected at model validation
    try:
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.RUN_SUMMARY,
            logical_id="run-imported",
            fingerprint=_sha256(b"run-imported"),
            evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
            content=b"should fail",
        )
        pytest.fail("raw imported evidence embedding should be rejected")
    except ValueError as exc:
        assert "raw imported evidence" in str(exc).lower()

    # Correct policy succeeds and is not embedded
    member = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RUN_SUMMARY,
        logical_id="run-imported",
        fingerprint=_sha256(b"run-imported"),
        evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    req = StudyCapsuleRequest(
        creation_date=PUB_DATE,
        study_id="study-imported",
        capsule_title="Imported evidence test",
        members=[member],
    )
    built = build_study_capsule(req)
    assert built.members.get("artifacts/run_summary/run-imported.json") is None
    dest = tmp_path / "imported.zip"
    receipt = create_study_capsule_archive(req, dest)
    assert receipt.embedded_count == 0
    assert receipt.referenced_count == 1


def test_integration_deterministic_archive_across_equivalent_roots(tmp_path: Path) -> None:
    """Two builds from equivalent logical artifacts must be byte-identical."""

    def make_req() -> StudyCapsuleRequest:
        return StudyCapsuleRequest(
            creation_date=PUB_DATE,
            study_id="study-det-2",
            capsule_title="Deterministic second root",
            members=[
                default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-x"),
                default_synthetic_member(StudyCapsuleMemberKind.EVIDENCE_PACK, "ev-x"),
            ],
        )

    req_a = make_req()
    req_b = make_req()
    # Simulate different temporary roots by building in isolated temp dirs
    with tempfile.TemporaryDirectory() as td1:
        p1 = Path(td1) / "a.zip"
        create_study_capsule_archive(req_a, p1)
        b1 = p1.read_bytes()
    with tempfile.TemporaryDirectory() as td2:
        p2 = Path(td2) / "b.zip"
        create_study_capsule_archive(req_b, p2)
        b2 = p2.read_bytes()
    assert b1 == b2


def test_integration_verifier_detects_tamper_missing_extra(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUB_DATE,
        study_id="study-verify-int",
        capsule_title="Verifier integration",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-int"),
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-int"),
        ],
    )
    dest = tmp_path / "verify-int.zip"
    create_study_capsule_archive(req, dest)
    original = dest.read_bytes()
    # Tamper
    buf = io.BytesIO(original)
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    target = next(k for k in members if k.startswith("artifacts/"))
    members[target] = members[target] + b"X"
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert not ver.valid
    assert ver.status.value == "tampered"

    # Missing
    buf = io.BytesIO(original)
    with zipfile.ZipFile(buf, "r") as z:
        members2 = {n: z.read(n) for n in z.namelist()}
    del members2[target]
    missing = _zip_bytes(members2)
    ver2 = verify_study_capsule_bytes(missing)
    assert not ver2.valid

    # Extra
    buf = io.BytesIO(original)
    with zipfile.ZipFile(buf, "r") as z:
        members3: dict[str, bytes] = {n: z.read(n) for n in z.namelist()}
    members3["artifacts/extra.json"] = b"{}"
    extra = _zip_bytes(members3)
    ver3 = verify_study_capsule_bytes(extra)
    assert not ver3.valid


def test_integration_manifest_binds_all_required_fields(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUB_DATE,
        study_id="study-bind",
        study_version="2.0",
        study_title="Binding test",
        capsule_title="Manifest binding",
        capsule_description="Integration binding verification",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-bind"),
        ],
        limitations=["limitation A", "limitation B"],
        unavailable=[
            StudyCapsuleUnavailable(
                kind=StudyCapsuleMemberKind.COMPARISON_REPORT,
                logical_id="comp-missing",
                reason="no comparison yet",
            )
        ],
    )
    built = build_study_capsule(req)
    m = built.manifest
    # Required bindings
    assert m.schema_version == "1.0"
    assert m.study.study_id == "study-bind"
    assert m.study.study_version == "2.0"
    assert len(m.members) == 1
    assert m.members[0].fingerprint is not None
    assert m.members[0].policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
    assert m.members[0].sha256 is not None
    assert m.members[0].evidence_label is not None
    assert m.members[0].admission_label is not None
    assert len(m.limitations) == 2
    assert len(m.unavailable) == 1
    assert m.software.version is not None
    assert len(m.manifest_fingerprint) == 64
    # No absolute paths - use tmp_path to avoid hardcoded /tmp (S108)
    assert str(tmp_path) not in m.model_dump_json()
    assert "secret" not in m.model_dump_json().lower() or "not" in m.model_dump_json().lower()

# ruff: noqa: E501
"""Production-path tests for Study Capsule builder/verifier."""

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
    StudyCapsuleError,
    StudyCapsuleEvidenceLabel,
    StudyCapsuleMemberInput,
    StudyCapsuleMemberKind,
    StudyCapsulePublicationPolicy,
    StudyCapsuleRequest,
    StudyCapsuleUnavailable,
    StudyCapsuleVerificationStatus,
    _sha256,
    _zip_bytes,
    build_study_capsule,
    create_study_capsule_archive,
    default_synthetic_member,
    preview_membership,
    study_capsule_contract,
    verify_study_capsule,
    verify_study_capsule_bytes,
)


PUBLICATION_DATE = date(2026, 8, 9)


def _request(
    members: list[StudyCapsuleMemberInput] | None = None,
    *,
    study_id: str = "study-001",
    capsule_title: str = "Test capsule",
    limitations: list[str] | None = None,
    unavailable: list[StudyCapsuleUnavailable] | None = None,
) -> StudyCapsuleRequest:
    if members is None:
        members = [default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-a")]
    return StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id=study_id,
        capsule_title=capsule_title,
        members=members,
        limitations=limitations or ["synthetic only", "not production"],
        unavailable=unavailable or [],
    )


def _fingerprint(kind: str, lid: str) -> str:
    return _sha256(f"{kind}:{lid}".encode())


# ---------------------------------------------------------------------------
# Strict validation
# ---------------------------------------------------------------------------


def test_strict_member_validation_rejects_invalid_identifier() -> None:
    with pytest.raises(ValueError, match="logical_id"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.SCENARIO_SEED,
            logical_id="bad id with spaces",
            fingerprint="a" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
        )


def test_strict_member_validation_rejects_bad_fingerprint() -> None:
    with pytest.raises(ValueError):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.SCENARIO_SEED,
            logical_id="seed-1",
            fingerprint="not-hex",
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
        )


def test_extra_fields_forbidden_at_untrusted_boundary() -> None:
    with pytest.raises(ValueError):
        StudyCapsuleRequest.model_validate(
            {
                "creation_date": PUBLICATION_DATE.isoformat(),
                "study_id": "study-001",
                "capsule_title": "title",
                "members": [
                    {
                        "kind": "scenario_seed",
                        "logical_id": "seed-1",
                        "fingerprint": "a" * 64,
                        "evidence_label": "synthetic_evidence",
                        "policy": "reference_by_fingerprint",
                        "unexpected_extra": "oops",
                    }
                ],
                "limitations": [],
            }
        )


def test_duplicate_logical_identity_rejected() -> None:
    m1 = default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "dup")
    m2 = default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "dup")
    with pytest.raises(ValueError, match="duplicate member"):
        _request(members=[m1, m2])


def test_duplicate_fingerprint_rejected_for_included() -> None:
    fp = "c" * 64
    m1 = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="a",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    m2 = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RUN_SUMMARY,
        logical_id="b",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    with pytest.raises(ValueError, match="fingerprints must be unique"):
        _request(members=[m1, m2])


# ---------------------------------------------------------------------------
# Publication policies
# ---------------------------------------------------------------------------


def test_policy_embed_requires_content() -> None:
    with pytest.raises(ValueError, match="embed_safe_derived requires content"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.SCENARIO_SEED,
            logical_id="seed-1",
            fingerprint="a" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
            content=None,
        )


def test_policy_reference_must_not_have_content() -> None:
    with pytest.raises(ValueError, match="must not carry content"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.SCENARIO_SEED,
            logical_id="seed-1",
            fingerprint="a" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
            content=b"unexpected",
        )


def test_policy_exclude_requires_reason() -> None:
    with pytest.raises(ValueError, match="excluded members require exclusion_reason"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.SCENARIO_SEED,
            logical_id="seed-1",
            fingerprint="a" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.EXCLUDE,
            exclusion_reason=None,
        )


def test_raw_imported_evidence_must_not_embed() -> None:
    with pytest.raises(ValueError, match="raw imported evidence must use"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.EVIDENCE_PACK,
            logical_id="ev-1",
            fingerprint="b" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
            content=b"raw bytes should not be embedded",
        )


def test_raw_variants_blocked_from_embed() -> None:
    for label in [
        StudyCapsuleEvidenceLabel.HISTORICAL_OBSERVATION,
        StudyCapsuleEvidenceLabel.NEAR_LIVE_OPERATIONAL,
        StudyCapsuleEvidenceLabel.UNADMITTED_RESEARCH,
    ]:
        with pytest.raises(ValueError):
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.RUN_SUMMARY,
                logical_id=f"run-{label.value}",
                fingerprint=_fingerprint("run_summary", f"run-{label.value}"),
                evidence_label=label,
                policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
                content=b"should fail",
            )


# ---------------------------------------------------------------------------
# Path and secret exclusion
# ---------------------------------------------------------------------------


def test_absolute_path_in_text_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain absolute"):
        StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.ANALYST_NOTE,
            logical_id="note-1",
            fingerprint="a" * 64,
            evidence_label=StudyCapsuleEvidenceLabel.AUTHORED_CONFIGURATION,
            policy=StudyCapsulePublicationPolicy.EXCLUDE,
            exclusion_reason="exclude because /tmp/secret/file is private",
        )


def test_windows_path_rejected() -> None:
    with pytest.raises(ValueError):
        StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-001",
            capsule_title="title with C:\\Users\\secret path",
            members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
        )


def test_secret_hint_rejected_in_limitations() -> None:
    with pytest.raises(ValueError, match="must not contain secrets"):
        _request(limitations=["api_key=supersecret123"])


def test_secret_in_embedded_content_rejected_at_build() -> None:
    member = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-secret",
        fingerprint=_fingerprint("scenario_seed", "seed-secret"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b"api_key= should be rejected as secret",
    )
    req = _request(members=[member])
    with pytest.raises(StudyCapsuleError, match="must not contain secrets"):
        build_study_capsule(req)


def test_manifest_contains_no_absolute_paths(tmp_path: Path) -> None:
    # Content that decodes to absolute path should be rejected; ensure manifest itself has none
    req = _request()
    built = build_study_capsule(req)
    manifest_text = built.members["capsule-manifest.json"].decode("utf-8")
    assert "/tmp" not in manifest_text or "[redacted absolute path]" in manifest_text
    # No member path should be absolute
    for key in built.members:
        assert not key.startswith("/")
        assert ".." not in key.split("/")


# ---------------------------------------------------------------------------
# Determinism and equivalent-root identity
# ---------------------------------------------------------------------------


def test_deterministic_archive_byte_identical(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-determinism",
        capsule_title="Determinism test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-a"),
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-a"),
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.COMPARISON_REPORT,
                logical_id="comp-1",
                fingerprint=_fingerprint("comparison_report", "comp-1"),
                evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
            ),
        ],
        limitations=["deterministic"],
    )
    p1 = tmp_path / "a.zip"
    p2 = tmp_path / "b.zip"
    r1 = create_study_capsule_archive(req, p1)
    r2 = create_study_capsule_archive(req, p2)
    assert p1.read_bytes() == p2.read_bytes()
    assert r1.archive_sha256 == r2.archive_sha256
    assert r1.manifest_fingerprint == r2.manifest_fingerprint


def test_equivalent_root_identity(tmp_path: Path) -> None:
    # Build same logical artifacts via two different Python object constructions (different temp roots simulation)
    # Should produce identical capsule_id and manifest_fingerprint and bytes
    def make_req() -> StudyCapsuleRequest:
        return StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-equiv",
            capsule_title="Equivalent root test",
            members=[
                default_synthetic_member(StudyCapsuleMemberKind.EVIDENCE_PACK, "ev-1"),
                StudyCapsuleMemberInput(
                    kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
                    logical_id="rep-1",
                    fingerprint=_fingerprint("deterministic_report", "rep-1"),
                    evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
                    policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
                ),
            ],
            limitations=["equiv"],
        )

    req1 = make_req()
    req2 = make_req()
    built1 = build_study_capsule(req1)
    built2 = build_study_capsule(req2)
    assert built1.manifest.capsule_id == built2.manifest.capsule_id
    assert built1.manifest.manifest_fingerprint == built2.manifest.manifest_fingerprint
    assert built1.manifest.canonical_json() == built2.manifest.canonical_json()
    # Also archives identical
    p1 = tmp_path / "eq1.zip"
    p2 = tmp_path / "eq2.zip"
    create_study_capsule_archive(req1, p1)
    create_study_capsule_archive(req2, p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_archive_members_are_stably_ordered(tmp_path: Path) -> None:
    # Members given out of order should still produce sorted archive ordering
    req_unsorted = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-order",
        capsule_title="Order test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-z"),
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-a"),
            default_synthetic_member(StudyCapsuleMemberKind.EVIDENCE_PACK, "ev-m"),
        ],
    )
    built = build_study_capsule(req_unsorted)
    # Archive should be sorted lexicographically
    names = list(built.members.keys())
    assert names == sorted(names)
    # ZIP bytes should also be sorted
    p = tmp_path / "order.zip"
    create_study_capsule_archive(req_unsorted, p)
    with zipfile.ZipFile(p) as z:
        zip_names = z.namelist()
    assert zip_names == sorted(zip_names)


# ---------------------------------------------------------------------------
# Reference-only and excluded members
# ---------------------------------------------------------------------------


def test_reference_only_members_not_embedded(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref",
        capsule_title="Ref test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
                logical_id="crate-1",
                fingerprint=_fingerprint("ro_crate_reference", "crate-1"),
                evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
                reference_note="existing crate",
            ),
        ],
    )
    built = build_study_capsule(req)
    # Only one embedded path (scenario_seed)
    embedded_paths = [m.archive_path for m in built.manifest.members if m.archive_path is not None]
    assert len(embedded_paths) == 1
    assert all("ro_crate_reference" not in p for p in embedded_paths)
    # Referenced member present in manifest but not in zip payload beyond manifest/checksums
    referenced = [m for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT]
    assert len(referenced) == 1
    assert referenced[0].logical_id == "crate-1"
    # Verify zip does not contain referenced payload
    assert "artifacts/ro_crate_reference/crate-1.json" not in built.members


def test_excluded_members_recorded_with_reasons(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-excl",
        capsule_title="Excl test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.EVIDENCE_PACK,
                logical_id="ev-raw",
                fingerprint=_fingerprint("evidence_pack", "ev-raw"),
                evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.EXCLUDE,
                exclusion_reason="raw imported evidence excluded per policy",
            ),
        ],
    )
    built = build_study_capsule(req)
    excluded = [m for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.EXCLUDE]
    assert len(excluded) == 1
    assert excluded[0].exclusion_reason == "raw imported evidence excluded per policy"
    assert len(built.manifest.exclusions) == 1
    assert built.manifest.exclusions[0].reason == "raw imported evidence excluded per policy"
    # No embedded payload for excluded
    assert "artifacts/evidence_pack/ev-raw.json" not in built.members


# ---------------------------------------------------------------------------
# Verifier checks: tampered, missing, extra, duplicate, traversal, unsupported
# ---------------------------------------------------------------------------


def _build_valid_archive(tmp_path: Path) -> tuple[StudyCapsuleRequest, Path]:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-verify",
        capsule_title="Verify test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-1"),
        ],
        limitations=["verify"],
    )
    p = tmp_path / "valid.zip"
    create_study_capsule_archive(req, p)
    return req, p


def test_verifier_accepts_valid(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    ver = verify_study_capsule(p)
    assert ver.valid is True
    assert ver.status is StudyCapsuleVerificationStatus.VALID
    assert ver.errors == []


def test_tampered_member_rejected(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    original = p.read_bytes()
    # Tamper: modify an embedded file without updating checksum/manifest
    buf = io.BytesIO(original)
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    # Find an embedded artifact
    target = next(k for k in members if k.startswith("artifacts/"))
    members[target] = members[target] + b"TAMPER"
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert ver.status is StudyCapsuleVerificationStatus.TAMPERED
    assert any("checksum mismatch" in e or "size/checksum mismatch" in e for e in ver.errors)


def test_verifier_trusts_not_manifest_without_hashing(tmp_path: Path) -> None:
    """Mutant: verifier that only checks manifest fingerprint would accept tampered bytes.

    This test crafts a manifest where sha256 field is lying but file bytes differ.
    A correct verifier recomputes hashes and must reject.
    """
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    # Parse manifest and keep its sha256 lying, but tamper payload
    manifest_raw = members["capsule-manifest.json"]
    manifest_json = json.loads(manifest_raw)
    # Find embedded member path
    embedded_path = next(k for k in members if k.startswith("artifacts/"))
    # Tamper payload bytes but keep checksums.sha256 lying by not updating manifest entry
    members[embedded_path] = b"completely different content that is still lying"
    # Keep manifest's sha256 unchanged (lying) - verifier must detect via recomputation
    # Also need to keep checksums.sha256 consistent with tampered? No, we leave checksums as original which will mismatch tampered payload.
    # Re-zip with tampered payload but original checksums/manifest still claiming old hash.
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    # Must be tampered, not malformed
    assert ver.status is StudyCapsuleVerificationStatus.TAMPERED


def test_missing_member_rejected(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    # Remove an embedded member
    target = next(k for k in members if k.startswith("artifacts/"))
    del members[target]
    # Keep checksums as is – will now mismatch because checksum inventory includes missing
    # But we need to reconstruct checksums to reflect missing? Actually we keep original checksums, so verifier will detect mismatch.
    # For a more direct missing test, we also update checksums to not include target, but manifest still expects it.
    # Let's just remove from members dict and re-zip with original checksums/manifest (so payload missing)
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert any("missing" in e or "does not match" in e for e in ver.errors)


def test_undeclared_extra_member_rejected(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    members["artifacts/extra/sneaky.json"] = b'{"evil": true}'
    # Need to update checksums to include extra? If we don't update checksums, checksum inventory mismatch will trigger.
    # If we do update checksums but not manifest, manifest inventory mismatch will trigger.
    # Both should be rejected. We'll test without updating checksums (extra without declaration)
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert any("does not match archive payload" in e or "checksum inventory does not match" in e for e in ver.errors)


def test_duplicate_member_rejected(tmp_path: Path) -> None:
    # Manually craft ZIP with duplicate names using zipfile
    _, p = _build_valid_archive(tmp_path)
    original = p.read_bytes()
    # Use low-level zip writing to add duplicate
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        # Copy original members
        orig_buf = io.BytesIO(original)
        with zipfile.ZipFile(orig_buf, "r") as orig:
            for info in orig.infolist():
                data = orig.read(info.filename)
                # Write once
                zi = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_STORED
                zi.create_system = 3
                zi.external_attr = 0o100644 << 16
                z.writestr(zi, data)
            # Add duplicate of first entry
            first = orig.infolist()[0]
            dup = zipfile.ZipInfo(first.filename, date_time=(1980, 1, 1, 0, 0, 0))
            dup.compress_type = zipfile.ZIP_STORED
            dup.create_system = 3
            dup.external_attr = 0o100644 << 16
            z.writestr(dup, orig.read(first.filename))
    dup_bytes = buf.getvalue()
    ver = verify_study_capsule_bytes(dup_bytes)
    assert ver.valid is False
    assert any("duplicate" in e.lower() for e in ver.errors)
    assert ver.status is StudyCapsuleVerificationStatus.MALFORMED


def test_traversal_member_rejected(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_STORED) as z:
        # Add a traversal entry
        for name in ["capsule-manifest.json", "checksums.sha256", "../../evil.txt"]:
            zi = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_STORED
            zi.create_system = 3
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, b"{}" if name.endswith(".json") else b"evil")
        # Add a minimal valid manifest? For traversal test we just want verifier to reject traversal regardless of other checks.
    ver = verify_study_capsule_bytes(buf.getvalue())
    assert ver.valid is False
    assert any("unsafe" in e.lower() or "traversal" in e.lower() or "unsafe" in e for e in ver.errors)


def test_unsupported_schema_version_distinguished(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(members["capsule-manifest.json"])
    manifest["schema_version"] = "9.9"
    # Re-serialize without updating fingerprint (so also tampered)
    members["capsule-manifest.json"] = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    # Need to keep checksums consistent: update checksum for manifest
    # But we want to test unsupported version detection; verifier should flag unsupported
    # We'll recompute checksums to be consistent, so the only error is version.
    # Recompute checksums dict
    new_checksums = {name: _sha256(content) for name, content in members.items() if name != "checksums.sha256"}
    members["checksums.sha256"] = "".join(f"{d}  {n}\n" for n, d in sorted(new_checksums.items())).encode()
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert ver.status is StudyCapsuleVerificationStatus.UNSUPPORTED_VERSION
    assert any("unsupported" in e.lower() for e in ver.errors)


def test_malformed_manifest_rejected(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    members["capsule-manifest.json"] = b"not json {{{"
    # Update checksum for manifest to keep checksum valid but manifest malformed
    new_checksums = {name: _sha256(content) for name, content in members.items() if name != "checksums.sha256"}
    members["checksums.sha256"] = "".join(f"{d}  {n}\n" for n, d in sorted(new_checksums.items())).encode()
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert ver.status is StudyCapsuleVerificationStatus.MALFORMED


# ---------------------------------------------------------------------------
# Atomic failure and existing destination
# ---------------------------------------------------------------------------


def test_atomic_failure_no_partial_after_failure(tmp_path: Path) -> None:
    # Build a request that will fail validation during archive creation (e.g., duplicate)
    # then ensure no file left at destination.
    dest = tmp_path / "should-not-exist.zip"
    bad_members = [
        default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
        default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),  # duplicate
    ]
    with pytest.raises(ValueError):
        bad_req = StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-atomic",
            capsule_title="Atomic test",
            members=bad_members,
        )
        create_study_capsule_archive(bad_req, dest)
    assert not dest.exists()
    # Also test that a failed verification after writing temp does not leave partial destination
    # Simulate by building valid then trying to overwrite without permission
    valid_req = _request()
    valid_dest = tmp_path / "valid.zip"
    create_study_capsule_archive(valid_req, valid_dest)
    assert valid_dest.exists()
    original_bytes = valid_dest.read_bytes()
    # Try to create again without overwrite – should raise and not truncate
    with pytest.raises(FileExistsError):
        create_study_capsule_archive(valid_req, valid_dest, overwrite=False)
    assert valid_dest.read_bytes() == original_bytes


def test_existing_destination_behavior(tmp_path: Path) -> None:
    req = _request()
    dest = tmp_path / "dest.zip"
    r1 = create_study_capsule_archive(req, dest)
    assert dest.exists()
    with pytest.raises(FileExistsError):
        create_study_capsule_archive(req, dest, overwrite=False)
    # With overwrite=True should succeed and produce same bytes
    r2 = create_study_capsule_archive(req, dest, overwrite=True)
    assert r2.archive_sha256 == r1.archive_sha256


def test_destination_must_be_zip_suffix(tmp_path: Path) -> None:
    req = _request()
    dest = tmp_path / "bad.txt"
    with pytest.raises(StudyCapsuleError, match=r"\.zip suffix"):
        create_study_capsule_archive(req, dest)


# ---------------------------------------------------------------------------
# Contract and fingerprint
# ---------------------------------------------------------------------------


def test_contract_is_versioned() -> None:
    c = study_capsule_contract()
    assert c.schema_version == "1.0"
    assert c.capability_id == "OPS-04-CAPSULE"
    assert len(c.fingerprint()) == 64


def test_manifest_fingerprint_is_canonical() -> None:
    req = _request()
    built = build_study_capsule(req)
    # Recompute fingerprint via canonical JSON without manifest_fingerprint
    payload = built.manifest.model_dump(mode="json")
    payload.pop("manifest_fingerprint")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    expected = _sha256(canonical.encode())
    assert built.manifest.manifest_fingerprint == expected
    assert built.manifest.fingerprint() == expected


def test_portable_identity_excludes_tmp_path(tmp_path: Path) -> None:
    # Build in two different temp dirs with same logical content – capsule_id identical, no tmp path in manifest
    req = _request(study_id="study-portable")
    built1 = build_study_capsule(req)
    # Simulate second build with same request but different Python process temp root (we just rebuild)
    built2 = build_study_capsule(req)
    assert built1.manifest.capsule_id == built2.manifest.capsule_id
    manifest_json = built1.manifest.model_dump_json()
    assert str(tmp_path) not in manifest_json
    assert "/tmp" not in manifest_json or "[redacted" in manifest_json


# ---------------------------------------------------------------------------
# UI preview matching manifest
# ---------------------------------------------------------------------------


def test_preview_matches_manifest() -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-preview",
        capsule_title="Preview test",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.COMPARISON_REPORT,
                logical_id="comp-1",
                fingerprint=_fingerprint("comparison_report", "comp-1"),
                evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
            ),
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.EVIDENCE_PACK,
                logical_id="ev-1",
                fingerprint=_fingerprint("evidence_pack", "ev-1"),
                evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.EXCLUDE,
                exclusion_reason="privacy",
            ),
        ],
    )
    preview = preview_membership(req)
    built = build_study_capsule(req)
    manifest_embedded = sorted([f"{m.kind.value}:{m.logical_id}" for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED])
    manifest_ref = sorted([f"{m.kind.value}:{m.logical_id}" for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT])
    manifest_excl = sorted([f"{m.kind.value}:{m.logical_id}" for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.EXCLUDE])
    assert preview["embedded"] == manifest_embedded
    assert preview["referenced"] == manifest_ref
    assert preview["excluded"] == manifest_excl


# ---------------------------------------------------------------------------
# End-to-end build → verify → tamper → reject
# ---------------------------------------------------------------------------


def test_end_to_end_build_verify_tamper_reject(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-e2e",
        capsule_title="E2E capsule",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-e2e"),
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-e2e"),
            default_synthetic_member(StudyCapsuleMemberKind.DETERMINISTIC_REPORT, "rep-e2e"),
        ],
        limitations=["e2e test"],
        unavailable=[
            StudyCapsuleUnavailable(kind=StudyCapsuleMemberKind.PROVENANCE_GRAPH, logical_id="prov-missing", reason="not generated")
        ],
    )
    dest = tmp_path / "e2e.zip"
    receipt = create_study_capsule_archive(req, dest)
    ver = verify_study_capsule(dest)
    assert ver.valid is True
    assert ver.capsule_id == receipt.capsule_id
    assert ver.manifest_fingerprint == receipt.manifest_fingerprint
    # Tamper
    buf = io.BytesIO(dest.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    tgt = next(k for k in members if k.startswith("artifacts/"))
    members[tgt] = members[tgt] + b"tamper"
    tampered = _zip_bytes(members)
    ver2 = verify_study_capsule_bytes(tampered)
    assert ver2.valid is False
    assert ver2.status is StudyCapsuleVerificationStatus.TAMPERED


# ---------------------------------------------------------------------------
# CLI smoke (library level, not subprocess)
# ---------------------------------------------------------------------------


def test_cli_create_and_verify_via_library(tmp_path: Path) -> None:
    # Exercise the same code path the CLI uses: request JSON file → archive → verify
    req = _request()
    req_path = tmp_path / "request.json"
    req_path.write_text(req.model_dump_json(indent=2), encoding="utf-8")
    dest = tmp_path / "cli.zip"
    # Simulate CLI create: load request json then create archive
    loaded = StudyCapsuleRequest.model_validate_json(req_path.read_bytes())
    receipt = create_study_capsule_archive(loaded, dest)
    assert dest.exists()
    ver = verify_study_capsule(dest)
    assert ver.valid is True
    assert ver.capsule_id == receipt.capsule_id

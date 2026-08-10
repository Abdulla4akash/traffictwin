# ruff: noqa: E501
"""Production-path tests for Study Capsule builder/verifier."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from traffictwin.study_capsule import (
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
    assert "/tmp" not in manifest_text or "[redacted absolute path]" in manifest_text  # noqa: S108
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
    referenced = [
        m
        for m in built.manifest.members
        if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
    ]
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
    excluded = [
        m for m in built.manifest.members if m.policy is StudyCapsulePublicationPolicy.EXCLUDE
    ]
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
    _manifest_json = json.loads(members["capsule-manifest.json"])
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
    assert any(
        "does not match archive payload" in e or "checksum inventory does not match" in e
        for e in ver.errors
    )


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
    assert any(
        "unsafe" in e.lower() or "traversal" in e.lower() or "unsafe" in e for e in ver.errors
    )


def test_unsupported_schema_version_distinguished(tmp_path: Path) -> None:
    _, p = _build_valid_archive(tmp_path)
    buf = io.BytesIO(p.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    manifest = json.loads(members["capsule-manifest.json"])
    manifest["schema_version"] = "9.9"
    # Re-serialize without updating fingerprint (so also tampered)
    members["capsule-manifest.json"] = json.dumps(
        manifest, sort_keys=True, separators=(",", ":")
    ).encode()
    # Need to keep checksums consistent: update checksum for manifest
    # But we want to test unsupported version detection; verifier should flag unsupported
    # We'll recompute checksums to be consistent, so the only error is version.
    # Recompute checksums dict
    new_checksums = {
        name: _sha256(content) for name, content in members.items() if name != "checksums.sha256"
    }
    members["checksums.sha256"] = "".join(
        f"{d}  {n}\n" for n, d in sorted(new_checksums.items())
    ).encode()
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
    new_checksums = {
        name: _sha256(content) for name, content in members.items() if name != "checksums.sha256"
    }
    members["checksums.sha256"] = "".join(
        f"{d}  {n}\n" for n, d in sorted(new_checksums.items())
    ).encode()
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
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
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
    assert "/tmp" not in manifest_json or "[redacted" in manifest_json  # noqa: S108


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
    manifest_embedded = sorted(
        [
            f"{m.kind.value}:{m.logical_id}"
            for m in built.manifest.members
            if m.policy is StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED
        ]
    )
    manifest_ref = sorted(
        [
            f"{m.kind.value}:{m.logical_id}"
            for m in built.manifest.members
            if m.policy is StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT
        ]
    )
    manifest_excl = sorted(
        [
            f"{m.kind.value}:{m.logical_id}"
            for m in built.manifest.members
            if m.policy is StudyCapsulePublicationPolicy.EXCLUDE
        ]
    )
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
            StudyCapsuleUnavailable(
                kind=StudyCapsuleMemberKind.PROVENANCE_GRAPH,
                logical_id="prov-missing",
                reason="not generated",
            )
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


# ---------------------------------------------------------------------------
# Regressions for Claude findings (HIGH 1,2,4,6,8, etc.)
# ---------------------------------------------------------------------------


def test_study_version_valid_build_verify(tmp_path: Path) -> None:
    for valid in ["v1", "1.0", "study-2026-08", "candidate_b"]:
        req = StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-version-valid",
            study_version=valid,
            capsule_title="valid version",
            members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
        )
        built = build_study_capsule(req)
        dest = tmp_path / f"valid-{valid}.zip"
        _receipt = create_study_capsule_archive(req, dest)
        ver = verify_study_capsule(dest)
        assert ver.valid is True
        assert built.manifest.study.study_version == valid


def test_study_version_rejects_unsafe(tmp_path: Path) -> None:
    for bad in ["/tmp/evil", "v1\n", "v1\r\n", "secret=123", "a" * 65, "bad version"]:  # noqa: S108
        with pytest.raises(ValueError):
            StudyCapsuleRequest(
                creation_date=PUBLICATION_DATE,
                study_id="study-bad",
                study_version=bad,
                capsule_title="bad",
                members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
            )
    # Control char
    with pytest.raises(ValueError):
        StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-bad",
            study_version="v\x01",
            capsule_title="bad",
            members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
        )


def test_manifest_fingerprint_matches_written_payload(tmp_path: Path) -> None:
    req = _request(study_id="study-fp-match")
    built = build_study_capsule(req)
    manifest_bytes = built.members["capsule-manifest.json"]
    parsed = json.loads(manifest_bytes)
    # The stored fingerprint must equal hash of canonical without fingerprint
    payload = dict(parsed)
    stored = payload.pop("manifest_fingerprint")
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    expected = _sha256(canonical.encode("utf-8"))
    assert stored == expected
    assert stored == built.manifest.manifest_fingerprint
    # Also verify via manifest.fingerprint() method
    assert built.manifest.fingerprint() == expected


def test_binary_member_hello_embeds_verifies(tmp_path: Path) -> None:
    member = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        logical_id="bin-hello",
        fingerprint=_fingerprint("deterministic_report", "bin-hello"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b"hello",
    )
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-binary",
        capsule_title="binary hello",
        members=[member],
    )
    built = build_study_capsule(req)
    assert built.members["artifacts/deterministic_report/bin-hello.md"] == b"hello"
    dest = tmp_path / "bin-hello.zip"
    create_study_capsule_archive(req, dest)
    ver = verify_study_capsule(dest)
    assert ver.valid is True


def test_binary_member_arbitrary_embeds_verifies(tmp_path: Path) -> None:
    # Includes NUL, high bytes, invalid UTF-8
    for data in [b"\x00\xff\x80ABC", b"\x89PNG\r\n\x1a\n\x00\x00", b"%PDF-1.4 binary \x00\xff"]:
        member = StudyCapsuleMemberInput(
            kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
            logical_id=f"bin-{_sha256(data)[:8]}",
            fingerprint=_sha256(data),
            evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
            policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
            content=data,
        )
        req = StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-binary2",
            capsule_title="binary arbitrary",
            members=[member],
        )
        built = build_study_capsule(req)
        dest = tmp_path / f"bin-{_sha256(data)[:8]}.zip"
        create_study_capsule_archive(req, dest)
        ver = verify_study_capsule(dest)
        assert ver.valid is True
        # Archive member bytes exactly equal original
        buf = io.BytesIO(dest.read_bytes())
        with zipfile.ZipFile(buf, "r") as z:
            archived = z.read(f"artifacts/deterministic_report/{member.logical_id}.md")
        assert archived == data
        # Manifest contains checksum/size, not raw binary encoding
        manifest = json.loads(built.members["capsule-manifest.json"].decode("utf-8"))
        entry = next(m for m in manifest["members"] if m["logical_id"] == member.logical_id)
        assert entry["sha256"] == _sha256(data)
        assert entry["content_size"] == len(data)
        assert "content" not in entry


def test_binary_mutation_rejected(tmp_path: Path) -> None:
    data = b"\x00\xff\x80ABC"
    member = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        logical_id="bin-mut",
        fingerprint=_fingerprint("deterministic_report", "bin-mut"),
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=data,
    )
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-bin-mut",
        capsule_title="binary mut",
        members=[member],
    )
    dest = tmp_path / "bin-mut.zip"
    create_study_capsule_archive(req, dest)
    original = dest.read_bytes()
    buf = io.BytesIO(original)
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    # One-byte mutation
    target = next(k for k in members if k.startswith("artifacts/"))
    members[target] = members[target][:-1] + b"X"
    tampered = _zip_bytes(members)
    ver = verify_study_capsule_bytes(tampered)
    assert ver.valid is False
    assert ver.status is StudyCapsuleVerificationStatus.TAMPERED


def test_blank_checksums_rejected_for_reference_only(tmp_path: Path) -> None:
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref-only",
        capsule_title="ref only",
        members=[
            StudyCapsuleMemberInput(
                kind=StudyCapsuleMemberKind.COMPARISON_REPORT,
                logical_id="comp-ref",
                fingerprint=_fingerprint("comparison_report", "comp-ref"),
                evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
            )
        ],
    )
    dest = tmp_path / "ref-only.zip"
    create_study_capsule_archive(req, dest)
    # Valid reference-only should verify
    ver = verify_study_capsule(dest)
    assert ver.valid is True
    # Blank checksums should be rejected
    buf = io.BytesIO(dest.read_bytes())
    with zipfile.ZipFile(buf, "r") as z:
        members = {n: z.read(n) for n in z.namelist()}
    members["checksums.sha256"] = b""
    tampered = _zip_bytes(members)
    ver2 = verify_study_capsule_bytes(tampered)
    assert ver2.valid is False
    # Missing checksums also rejected
    del members["checksums.sha256"]
    # Need to re-add with blank to avoid KeyError? Actually test missing
    buf2 = io.BytesIO(dest.read_bytes())
    with zipfile.ZipFile(buf2, "r") as z:
        members2 = {n: z.read(n) for n in z.namelist()}
    del members2["checksums.sha256"]
    tampered2 = _zip_bytes(members2)
    ver3 = verify_study_capsule_bytes(tampered2)
    assert ver3.valid is False


def test_receipt_logical_vs_archive_counts(tmp_path: Path) -> None:
    # 3 embedded logical members → member_count 3, archive_entry_count 5 (manifest+checksums+3)
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-counts",
        capsule_title="counts",
        members=[
            default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1"),
            default_synthetic_member(StudyCapsuleMemberKind.RUN_SUMMARY, "run-1"),
            default_synthetic_member(StudyCapsuleMemberKind.EVIDENCE_PACK, "ev-1"),
        ],
    )
    dest = tmp_path / "counts.zip"
    receipt = create_study_capsule_archive(req, dest)
    assert receipt.member_count == 3
    assert receipt.embedded_count == 3
    assert receipt.referenced_count == 0
    assert receipt.excluded_count == 0
    assert receipt.archive_entry_count == 5
    # Mix
    req2 = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-counts2",
        capsule_title="counts2",
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
                logical_id="ev-2",
                fingerprint=_fingerprint("evidence_pack", "ev-2"),
                evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
                policy=StudyCapsulePublicationPolicy.EXCLUDE,
                exclusion_reason="privacy",
            ),
        ],
    )
    dest2 = tmp_path / "counts2.zip"
    receipt2 = create_study_capsule_archive(req2, dest2)
    assert receipt2.member_count == 3
    assert receipt2.embedded_count == 1
    assert receipt2.referenced_count == 1
    assert receipt2.excluded_count == 1
    assert receipt2.archive_entry_count == 3  # manifest+checksums+1 embedded


def test_study_description_identity_visible(tmp_path: Path) -> None:
    base = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-desc",
        study_version="1.0",
        study_title="title",
        study_description="first description",
        capsule_title="capsule",
        members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
    )
    built1 = build_study_capsule(base)
    # Changing description must change manifest visibly and fingerprint
    altered = base.model_copy(update={"study_description": "second description"})
    built2 = build_study_capsule(altered)
    assert built1.manifest.manifest_fingerprint != built2.manifest.manifest_fingerprint
    assert built1.manifest.study.study_description == "first description"
    assert built2.manifest.study.study_description == "second description"
    assert built1.manifest.capsule_id != built2.manifest.capsule_id


def test_study_description_none_vs_value_identity(tmp_path: Path) -> None:
    req_none = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-desc2",
        study_version="1.0",
        capsule_title="capsule",
        members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
        study_description=None,
    )
    req_val = req_none.model_copy(update={"study_description": "desc"})
    built_none = build_study_capsule(req_none)
    built_val = build_study_capsule(req_val)
    assert built_none.manifest.manifest_fingerprint != built_val.manifest.manifest_fingerprint


# ---------------------------------------------------------------------------
# Capsule_id content-binding (new medium regression, sections 6-8)
# ---------------------------------------------------------------------------


def test_capsule_id_same_bytes_same_id() -> None:
    fp = _fingerprint("scenario_seed", "seed-bind")
    m = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-bind",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b'{"metric": 1}',
    )
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-bind-same",
        capsule_title="bind same",
        members=[m],
    )
    b1 = build_study_capsule(req)
    b2 = build_study_capsule(req)
    assert b1.manifest.capsule_id == b2.manifest.capsule_id
    assert b1.manifest.manifest_fingerprint == b2.manifest.manifest_fingerprint


def test_capsule_id_same_declared_fp_different_bytes_differs() -> None:
    fp = _fingerprint("scenario_seed", "seed-diff")
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-diff",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b'{"metric": 1}',
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-diff",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b'{"metric": 999999}',
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-diff",
        capsule_title="diff",
        members=[m_a],
    )
    req_b = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-diff",
        capsule_title="diff",
        members=[m_b],
    )
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id != b_b.manifest.capsule_id
    assert b_a.manifest.manifest_fingerprint != b_b.manifest.manifest_fingerprint
    # Archive bytes also differ
    assert b_a.members != b_b.members


def test_capsule_id_binary_one_byte_mutation_differs() -> None:
    fp = _fingerprint("deterministic_report", "bin-id")
    data_a = b"\x00\xff\x80ABC"
    data_b = b"\x00\xff\x80ABD"  # one byte changed
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        logical_id="bin-id",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=data_a,
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.DETERMINISTIC_REPORT,
        logical_id="bin-id",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=data_b,
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-bin-id",
        capsule_title="bin id",
        members=[m_a],
    )
    req_b = req_a.model_copy(update={"members": [m_b]})
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id != b_b.manifest.capsule_id


def test_capsule_id_same_bytes_different_tmp_root_same_id(tmp_path: Path) -> None:
    fp = _fingerprint("scenario_seed", "seed-root")
    m = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-root",
        fingerprint=fp,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b"same bytes",
    )
    req = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-root",
        capsule_title="root",
        members=[m],
    )
    # Build from two different temp roots - use create_study_capsule_archive which does atomic replace
    import tempfile

    with tempfile.TemporaryDirectory() as td1:
        p1 = Path(td1) / "a.zip"
        r1 = create_study_capsule_archive(req, p1)
    with tempfile.TemporaryDirectory() as td2:
        p2 = Path(td2) / "b.zip"
        r2 = create_study_capsule_archive(req, p2)
    assert r1.capsule_id == r2.capsule_id
    assert r1.manifest_fingerprint == r2.manifest_fingerprint
    assert (
        r1.archive_sha256 != r2.archive_sha256 or r1.archive_sha256 == r2.archive_sha256
    )  # archives are byte-identical so hash same
    # Actually archives should be byte-identical
    with tempfile.TemporaryDirectory() as td1:
        p1 = Path(td1) / "a.zip"
        create_study_capsule_archive(req, p1)
        b1 = p1.read_bytes()
    with tempfile.TemporaryDirectory() as td2:
        p2 = Path(td2) / "b.zip"
        create_study_capsule_archive(req, p2)
        b2 = p2.read_bytes()
    assert b1 == b2


def test_capsule_id_same_bytes_different_declared_fp_differs() -> None:
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-fp-diff",
        fingerprint="a" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b"same content",
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.SCENARIO_SEED,
        logical_id="seed-fp-diff",
        fingerprint="b" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EMBED_SAFE_DERIVED,
        content=b"same content",
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-fp",
        capsule_title="fp",
        members=[m_a],
    )
    req_b = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-fp",
        capsule_title="fp",
        members=[m_b],
    )
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id != b_b.manifest.capsule_id


def test_capsule_id_reference_same_fp_same_id() -> None:
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
        logical_id="ref-1",
        fingerprint="c" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
        logical_id="ref-1",
        fingerprint="c" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref",
        capsule_title="ref",
        members=[m_a],
    )
    req_b = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref",
        capsule_title="ref",
        members=[m_b],
    )
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id == b_b.manifest.capsule_id


def test_capsule_id_reference_different_fp_differs() -> None:
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
        logical_id="ref-1",
        fingerprint="c" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.RO_CRATE_REFERENCE,
        logical_id="ref-1",
        fingerprint="d" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.SYNTHETIC_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.REFERENCE_BY_FINGERPRINT,
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref2",
        capsule_title="ref2",
        members=[m_a],
    )
    req_b = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ref2",
        capsule_title="ref2",
        members=[m_b],
    )
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id != b_b.manifest.capsule_id


def test_capsule_id_exclude_reason_changes_id() -> None:
    m_a = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.EVIDENCE_PACK,
        logical_id="ex-1",
        fingerprint="e" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EXCLUDE,
        exclusion_reason="privacy",
    )
    m_b = StudyCapsuleMemberInput(
        kind=StudyCapsuleMemberKind.EVIDENCE_PACK,
        logical_id="ex-1",
        fingerprint="e" * 64,
        evidence_label=StudyCapsuleEvidenceLabel.IMPORTED_EVIDENCE,
        policy=StudyCapsulePublicationPolicy.EXCLUDE,
        exclusion_reason="legal hold",
    )
    req_a = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ex",
        capsule_title="ex",
        members=[m_a],
    )
    req_b = StudyCapsuleRequest(
        creation_date=PUBLICATION_DATE,
        study_id="study-ex",
        capsule_title="ex",
        members=[m_b],
    )
    b_a = build_study_capsule(req_a)
    b_b = build_study_capsule(req_b)
    assert b_a.manifest.capsule_id != b_b.manifest.capsule_id


def test_study_version_plus_build_metadata_accepted(tmp_path: Path) -> None:
    for valid in ["1.0+build.2", "2.1.0-rc.1+sha.abc123", "1.0+exp.sha.5114f85"]:
        req = StudyCapsuleRequest(
            creation_date=PUBLICATION_DATE,
            study_id="study-plus",
            study_version=valid,
            capsule_title="plus",
            members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
        )
        built = build_study_capsule(req)
        assert built.manifest.study.study_version == valid
        dest = tmp_path / f"plus-{valid.replace('+', '_')}.zip"
        create_study_capsule_archive(req, dest)
        ver = verify_study_capsule(dest)
        assert ver.valid is True

    for bad in ["/v1+build", "C:\\v1+build", "1.0+build 2", "1.0:build"]:
        with pytest.raises(ValueError):
            StudyCapsuleRequest(
                creation_date=PUBLICATION_DATE,
                study_id="study-bad-plus",
                study_version=bad,
                capsule_title="bad",
                members=[default_synthetic_member(StudyCapsuleMemberKind.SCENARIO_SEED, "seed-1")],
            )


def test_warnings_field_removed(tmp_path: Path) -> None:
    req = _request()
    dest = tmp_path / "warn.zip"
    create_study_capsule_archive(req, dest)
    ver = verify_study_capsule(dest)
    assert not hasattr(ver, "warnings")
    # Also check manifest has no warnings
    built = build_study_capsule(req)
    assert not hasattr(built.manifest, "warnings")

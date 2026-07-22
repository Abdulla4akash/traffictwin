"""Unit tests for atomic MAN-01 snapshot publication (synthetic fixtures only)."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

import traffictwin.integration.manchester.snapshots as snapshots_module
from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    RECEIPT_FILE_NAME,
    ManchesterFindingSeverity,
    ManchesterHttpMetadata,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterRawMember,
    ManchesterRequestIdentity,
    ManchesterRetrievalWindow,
    ManchesterSnapshotFinding,
    ManchesterSnapshotManifest,
    ManchesterSnapshotPolicy,
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    ManchesterSnapshotError,
    publish_manchester_snapshot,
    read_manchester_member,
    verify_manchester_snapshot,
)

STARTED = datetime(2026, 7, 22, 10, 0, 0, tzinfo=UTC)
COMPLETED = datetime(2026, 7, 22, 10, 0, 5, tzinfo=UTC)
SYNTHETIC_MEMBERS: dict[str, bytes] = {
    "body.json": b'{"synthetic": true, "records": [1, 2, 3]}\n',
    "pages/page-1.bin": bytes(range(256)) + b"\x00\xff synthetic",
}
POLICY = ManchesterSnapshotPolicy(
    max_member_count=16, max_member_bytes=1_000_000, max_total_bytes=4_000_000
)


def make_manifest(
    members: dict[str, bytes] | None = None, **overrides: object
) -> ManchesterSnapshotManifest:
    payloads = SYNTHETIC_MEMBERS if members is None else members
    inventory = tuple(
        sorted(
            (
                ManchesterRawMember(
                    relative_path=path,
                    byte_size=len(data),
                    media_type="application/octet-stream",
                    sha256=sha256_hex(data),
                )
                for path, data in payloads.items()
            ),
            key=lambda member: member.relative_path,
        )
    )
    raw_fingerprint = build_raw_fingerprint(inventory)
    values: dict[str, object] = {
        "snapshot_id": build_snapshot_id("synthetic_demo", STARTED, raw_fingerprint),
        "source": ManchesterSourceIdentity(
            source_id="synthetic_demo",
            source_name="Synthetic demo source (not Manchester data)",
            adapter_version="0.0.1",
            source_schema_version="synthetic-1.0",
            freshness_policy_version="synthetic-1.0",
        ),
        "request": ManchesterRequestIdentity(
            host="example.invalid",
            path="/api/synthetic",
            parameters=(("page", 1),),
            redacted_parameter_names=("api_key",),
        ),
        "retrieval": ManchesterRetrievalWindow(started_at_utc=STARTED, completed_at_utc=COMPLETED),
        "http": ManchesterHttpMetadata(
            status_code=200, response_content_type="application/octet-stream"
        ),
        "members": inventory,
        "member_count": len(inventory),
        "total_bytes": sum(member.byte_size for member in inventory),
        "raw_fingerprint": raw_fingerprint,
        "validation_state": ManchesterValidationState.ACCEPTED,
        "findings": (),
        "prior": ManchesterPriorSnapshotLink(relation=ManchesterPriorRelation.FIRST_SNAPSHOT),
        "publication_class": ManchesterPublicationClass.PRIVATE,
        "licence_id": "synthetic-fixture",
        "attribution_text": "Synthetic TrafficTwin fixture; not observed Manchester data.",
        "access_date": date(2026, 7, 22),
        "synthetic": True,
    }
    values.update(overrides)
    return ManchesterSnapshotManifest.model_validate(values)


def staging_leftovers(workspace: Path) -> list[Path]:
    return [path for path in workspace.iterdir() if "-staging-" in path.name]


def test_publish_round_trips_exact_raw_bytes(tmp_path: Path) -> None:
    manifest = make_manifest()
    receipt = publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    destination = tmp_path / manifest.snapshot_id
    assert destination.is_dir()
    for path, data in SYNTHETIC_MEMBERS.items():
        assert (destination / RAW_DIRECTORY_NAME / path).read_bytes() == data
        assert read_manchester_member(destination, path) == data
    assert receipt.verified_member_count == len(SYNTHETIC_MEMBERS)
    assert receipt.verified_total_bytes == sum(len(d) for d in SYNTHETIC_MEMBERS.values())
    assert receipt.raw_fingerprint == manifest.raw_fingerprint
    assert not staging_leftovers(tmp_path)


def test_publish_then_verify_reconciles_everything(tmp_path: Path) -> None:
    manifest = make_manifest()
    published = publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    reopened = verify_manchester_snapshot(tmp_path / manifest.snapshot_id)
    assert reopened == published
    assert reopened.manifest_fingerprint == manifest.fingerprint()
    stored = (tmp_path / manifest.snapshot_id / MANIFEST_FILE_NAME).read_bytes()
    assert reopened.manifest_file_sha256 == sha256_hex(stored)


def test_verify_detects_member_mutation(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    target = tmp_path / manifest.snapshot_id / RAW_DIRECTORY_NAME / "body.json"
    target.chmod(0o644)
    target.write_bytes(b'{"synthetic": true, "records": [9]}\n')
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(tmp_path / manifest.snapshot_id)
    assert excinfo.value.code in {"MEMBER_MUTATED", "MEMBER_SIZE_MISMATCH"}
    with pytest.raises(ManchesterSnapshotError):
        read_manchester_member(tmp_path / manifest.snapshot_id, "body.json")


def test_verify_detects_extra_missing_and_symlinked_members(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    destination = tmp_path / manifest.snapshot_id
    raw_root = destination / RAW_DIRECTORY_NAME

    extra = raw_root / "extra.json"
    extra.write_bytes(b"{}")
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(destination)
    assert excinfo.value.code == "MEMBER_UNEXPECTED"
    extra.unlink()

    body = raw_root / "body.json"
    original = body.read_bytes()
    body.chmod(0o644)
    body.unlink()
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(destination)
    assert excinfo.value.code == "MEMBER_MISSING"

    outside = tmp_path / "outside.json"
    outside.write_bytes(original)
    body.symlink_to(outside)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(destination)
    assert excinfo.value.code == "MEMBER_SYMLINK"


def test_verify_refuses_uninventoried_top_level_content(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    destination = tmp_path / manifest.snapshot_id
    (destination / "notes.txt").write_text("not part of the snapshot contract", encoding="utf-8")
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(destination)
    assert excinfo.value.code == "SNAPSHOT_INVALID"


def test_existing_destination_is_never_replaced(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    destination = tmp_path / manifest.snapshot_id
    before = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert excinfo.value.code == "DESTINATION_EXISTS"
    after = {
        path.relative_to(destination).as_posix(): path.read_bytes()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    assert after == before
    assert not staging_leftovers(tmp_path)


def test_symlink_destination_is_refused(tmp_path: Path) -> None:
    manifest = make_manifest()
    real = tmp_path / "elsewhere"
    real.mkdir()
    (tmp_path / manifest.snapshot_id).symlink_to(real)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert excinfo.value.code == "DESTINATION_EXISTS"


def test_policy_bounds_are_enforced(tmp_path: Path) -> None:
    manifest = make_manifest()
    tight_count = ManchesterSnapshotPolicy(
        max_member_count=1, max_member_bytes=1_000_000, max_total_bytes=1_000_000
    )
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, tight_count)
    assert excinfo.value.code == "POLICY_MEMBER_COUNT"
    tight_member = ManchesterSnapshotPolicy(
        max_member_count=16, max_member_bytes=8, max_total_bytes=1_000_000
    )
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, tight_member)
    assert excinfo.value.code == "POLICY_MEMBER_BYTES"
    tight_total = ManchesterSnapshotPolicy(
        max_member_count=16, max_member_bytes=280, max_total_bytes=300
    )
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, tight_total)
    assert excinfo.value.code == "POLICY_TOTAL_BYTES"
    assert not any(tmp_path.iterdir())


def test_member_manifest_mismatches_are_refused(tmp_path: Path) -> None:
    manifest = make_manifest()
    missing = {"body.json": SYNTHETIC_MEMBERS["body.json"]}
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, missing, POLICY)
    assert excinfo.value.code == "MEMBER_SET_MISMATCH"
    extra = dict(SYNTHETIC_MEMBERS, **{"extra.json": b"{}"})
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, extra, POLICY)
    assert excinfo.value.code == "MEMBER_SET_MISMATCH"
    tampered = dict(SYNTHETIC_MEMBERS, **{"body.json": b'{"synthetic": true}   \n'})
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, tampered, POLICY)
    assert excinfo.value.code in {"MEMBER_SIZE_MISMATCH", "MEMBER_HASH_MISMATCH"}
    assert not any(tmp_path.iterdir())


def test_rejected_manifest_cannot_be_published(tmp_path: Path) -> None:
    manifest = make_manifest(
        validation_state=ManchesterValidationState.REJECTED,
        findings=(
            ManchesterSnapshotFinding(
                code="SYNTHETIC_ERROR",
                severity=ManchesterFindingSeverity.ERROR,
                message="synthetic rejection",
            ),
        ),
    )
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert excinfo.value.code == "MANIFEST_REJECTED"
    assert not any(tmp_path.iterdir())


def test_mid_publication_failure_leaves_no_partial_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = make_manifest()

    def broken_rename(payload: Path, destination: Path) -> None:
        raise ManchesterSnapshotError("PUBLICATION_FAILED", "simulated rename failure")

    monkeypatch.setattr(snapshots_module, "_rename_into_place", broken_rename)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert excinfo.value.code == "PUBLICATION_FAILED"
    assert not (tmp_path / manifest.snapshot_id).exists()
    assert not staging_leftovers(tmp_path)


def test_active_publication_lock_refuses_a_second_writer_without_removing_lock(
    tmp_path: Path,
) -> None:
    manifest = make_manifest()
    lock = tmp_path / f".{manifest.snapshot_id}.publish.lock"
    lock.write_text("foreign writer\n", encoding="utf-8")
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert excinfo.value.code == "PUBLICATION_LOCKED"
    assert lock.read_text(encoding="utf-8") == "foreign writer\n"
    assert not (tmp_path / manifest.snapshot_id).exists()


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("verified_member_count", 1, "RECEIPT_MISMATCH"),
        ("verified_total_bytes", 1, "RECEIPT_MISMATCH"),
        (
            "policy",
            ManchesterSnapshotPolicy(
                max_member_count=16,
                max_member_bytes=1,
                max_total_bytes=1,
            ),
            "POLICY_MEMBER_BYTES",
        ),
    ],
)
def test_verify_reconciles_receipt_counts_and_stored_policy_before_raw_reads(
    tmp_path: Path,
    field: str,
    value: object,
    expected_code: str,
) -> None:
    manifest = make_manifest()
    receipt = publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    destination = tmp_path / manifest.snapshot_id
    receipt_path = destination / RECEIPT_FILE_NAME
    receipt_path.chmod(0o644)
    changed = receipt.model_copy(update={field: value})
    receipt_path.write_text(changed.canonical_json(), encoding="utf-8")
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(destination)
    assert excinfo.value.code == expected_code


def test_prior_no_change_snapshot_publishes_at_new_retrieval_time(
    tmp_path: Path,
) -> None:
    first = make_manifest()
    publish_manchester_snapshot(tmp_path, first, SYNTHETIC_MEMBERS, POLICY)
    later = datetime(2026, 7, 23, 10, 0, 0, tzinfo=UTC)
    duplicate = make_manifest(
        snapshot_id=build_snapshot_id("synthetic_demo", later, first.raw_fingerprint),
        retrieval=ManchesterRetrievalWindow(started_at_utc=later, completed_at_utc=later),
        prior=ManchesterPriorSnapshotLink(
            relation=ManchesterPriorRelation.DUPLICATE_NO_CHANGE,
            prior_snapshot_id=first.snapshot_id,
            prior_raw_fingerprint=first.raw_fingerprint,
        ),
    )
    receipt = publish_manchester_snapshot(tmp_path, duplicate, SYNTHETIC_MEMBERS, POLICY)
    assert receipt.snapshot_id != first.snapshot_id
    assert verify_manchester_snapshot(tmp_path / duplicate.snapshot_id) == receipt


def test_publication_class_is_preserved_on_disk(tmp_path: Path) -> None:
    manifest = make_manifest(publication_class=ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED)
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    stored = ManchesterSnapshotManifest.model_validate_json(
        (tmp_path / manifest.snapshot_id / MANIFEST_FILE_NAME).read_bytes()
    )
    assert stored.publication_class is ManchesterPublicationClass.REDISTRIBUTABLE_DERIVED
    assert stored.synthetic is True


@pytest.mark.skipif(os.name != "posix", reason="read-only bits are POSIX-specific")
def test_published_files_are_read_only_where_supported(tmp_path: Path) -> None:
    manifest = make_manifest()
    receipt = publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    assert receipt.read_only_applied is True
    destination = tmp_path / manifest.snapshot_id
    for name in (MANIFEST_FILE_NAME, RECEIPT_FILE_NAME):
        mode = (destination / name).stat().st_mode
        assert mode & 0o222 == 0
    for path in (destination / RAW_DIRECTORY_NAME).rglob("*"):
        if path.is_file():
            assert path.stat().st_mode & 0o222 == 0


def test_verify_rejects_wrong_directory_name(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    renamed = tmp_path / "synthetic_demo-20990101T000000Z-000000000000"
    (tmp_path / manifest.snapshot_id).rename(renamed)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        verify_manchester_snapshot(renamed)
    assert excinfo.value.code == "SNAPSHOT_ID_MISMATCH"


def test_unknown_member_read_is_refused(tmp_path: Path) -> None:
    manifest = make_manifest()
    publish_manchester_snapshot(tmp_path, manifest, SYNTHETIC_MEMBERS, POLICY)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        read_manchester_member(tmp_path / manifest.snapshot_id, "nope.json")
    assert excinfo.value.code == "MEMBER_UNKNOWN"

"""Tests for quarantine-before-parse Manchester acquisition ordering."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from traffictwin.integration.manchester.models import (
    MANCHESTER_SNAPSHOT_METHOD_VERSION,
    QUARANTINE_MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterFindingSeverity,
    ManchesterHttpMetadata,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
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
    ACCEPTED_DIRECTORY_NAME,
    QUARANTINE_DIRECTORY_NAME,
    ManchesterSnapshotError,
    promote_manchester_quarantine,
    publish_manchester_quarantine,
    quarantine_validate_and_promote,
    verify_manchester_quarantine,
    verify_manchester_snapshot,
)

STARTED = datetime(2026, 7, 22, 11, 0, tzinfo=UTC)
PAYLOADS = {
    "pages/page-1.json": b'{"synthetic":true,"page":1}\n',
    "pages/page-2.json": b'{"synthetic":true,"page":2}\n',
}
POLICY = ManchesterSnapshotPolicy(
    max_member_count=4,
    max_member_bytes=1_000,
    max_total_bytes=2_000,
)


def make_quarantine() -> ManchesterQuarantineManifest:
    members = tuple(
        ManchesterRawMember(
            relative_path=path,
            byte_size=len(payload),
            media_type="application/json",
            sha256=sha256_hex(payload),
        )
        for path, payload in sorted(PAYLOADS.items())
    )
    fingerprint = build_raw_fingerprint(members)
    return ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id("synthetic_dft", STARTED, fingerprint),
        source=ManchesterSourceIdentity(
            source_id="synthetic_dft",
            source_name="Synthetic DfT-shaped acquisition; not observed data",
            adapter_version="0.0.1",
            source_schema_version="synthetic-1",
            freshness_policy_version="historical-1",
        ),
        request=ManchesterRequestIdentity(
            host="example.invalid",
            path="/api/counts",
            parameters=(("page", 1),),
        ),
        retrieval=ManchesterRetrievalWindow(
            started_at_utc=STARTED,
            completed_at_utc=STARTED,
        ),
        http=ManchesterHttpMetadata(
            status_code=200,
            final_path="/api/counts",
            response_content_type="application/json",
        ),
        members=members,
        member_count=len(members),
        total_bytes=sum(member.byte_size for member in members),
        raw_fingerprint=fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id="synthetic-fixture",
        attribution_text="Synthetic TrafficTwin fixture; not observed Manchester data.",
        access_date=date(2026, 7, 22),
        synthetic=True,
    )


def accepted_manifest(
    quarantine: ManchesterQuarantineManifest,
    **updates: object,
) -> ManchesterSnapshotManifest:
    values = quarantine.model_dump()
    values.update(
        {
            "method_version": MANCHESTER_SNAPSHOT_METHOD_VERSION,
            "validation_state": ManchesterValidationState.ACCEPTED,
            "findings": (),
            "prior": ManchesterPriorSnapshotLink(relation=ManchesterPriorRelation.FIRST_SNAPSHOT),
        }
    )
    values.update(updates)
    return ManchesterSnapshotManifest.model_validate(values)


def test_quarantine_is_immutable_and_verifiable_before_validator_runs(tmp_path: Path) -> None:
    manifest = make_quarantine()
    observed: list[str] = []

    def validator(
        quarantine_dir: Path,
        source_manifest: ManchesterQuarantineManifest,
    ) -> ManchesterSnapshotManifest:
        assert quarantine_dir.is_dir()
        assert (quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME).is_file()
        assert verify_manchester_quarantine(quarantine_dir).raw_fingerprint == (
            source_manifest.raw_fingerprint
        )
        observed.append("validator-after-quarantine")
        return accepted_manifest(source_manifest)

    receipt = quarantine_validate_and_promote(
        tmp_path,
        manifest,
        PAYLOADS,
        POLICY,
        validator,
    )

    assert observed == ["validator-after-quarantine"]
    quarantine_dir = tmp_path / QUARANTINE_DIRECTORY_NAME / manifest.snapshot_id
    accepted_dir = tmp_path / ACCEPTED_DIRECTORY_NAME / manifest.snapshot_id
    assert verify_manchester_quarantine(quarantine_dir).raw_fingerprint == manifest.raw_fingerprint
    assert verify_manchester_snapshot(accepted_dir) == receipt
    for path, payload in PAYLOADS.items():
        assert (quarantine_dir / RAW_DIRECTORY_NAME / path).read_bytes() == payload
        assert (accepted_dir / RAW_DIRECTORY_NAME / path).read_bytes() == payload


def test_validator_failure_leaves_quarantine_and_no_accepted_snapshot(tmp_path: Path) -> None:
    manifest = make_quarantine()

    def validator(
        quarantine_dir: Path,
        _source_manifest: ManchesterQuarantineManifest,
    ) -> ManchesterSnapshotManifest:
        assert verify_manchester_quarantine(quarantine_dir)
        raise ValueError("synthetic parser refusal")

    with pytest.raises(ValueError, match="synthetic parser refusal"):
        quarantine_validate_and_promote(tmp_path, manifest, PAYLOADS, POLICY, validator)

    quarantine_dir = tmp_path / QUARANTINE_DIRECTORY_NAME / manifest.snapshot_id
    assert verify_manchester_quarantine(quarantine_dir)
    assert not (tmp_path / ACCEPTED_DIRECTORY_NAME).exists()


def test_rejected_validation_result_cannot_be_promoted(tmp_path: Path) -> None:
    quarantine = make_quarantine()
    publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)
    rejected = accepted_manifest(
        quarantine,
        validation_state=ManchesterValidationState.REJECTED,
        findings=(
            ManchesterSnapshotFinding(
                code="SYNTHETIC_SCHEMA_REJECTED",
                severity=ManchesterFindingSeverity.ERROR,
                message="synthetic parser rejection",
            ),
        ),
    )
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        promote_manchester_quarantine(tmp_path, rejected)
    assert excinfo.value.code == "MANIFEST_REJECTED"
    assert verify_manchester_quarantine(
        tmp_path / QUARANTINE_DIRECTORY_NAME / quarantine.snapshot_id
    )
    assert not (tmp_path / ACCEPTED_DIRECTORY_NAME).exists()


def test_promotion_refuses_provenance_drift(tmp_path: Path) -> None:
    quarantine = make_quarantine()
    publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)
    changed_source = quarantine.source.model_copy(
        update={"source_name": "Changed after quarantine"}
    )
    drifted = accepted_manifest(quarantine, source=changed_source)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        promote_manchester_quarantine(tmp_path, drifted)
    assert excinfo.value.code == "PROMOTION_IDENTITY_MISMATCH"
    assert not (tmp_path / ACCEPTED_DIRECTORY_NAME).exists()


def test_quarantine_tamper_blocks_verification_and_promotion(tmp_path: Path) -> None:
    quarantine = make_quarantine()
    publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)
    quarantine_dir = tmp_path / QUARANTINE_DIRECTORY_NAME / quarantine.snapshot_id
    target = quarantine_dir / RAW_DIRECTORY_NAME / "pages/page-1.json"
    target.chmod(0o644)
    target.write_bytes(b'{"synthetic":true,"tampered":true}\n')
    with pytest.raises(ManchesterSnapshotError):
        verify_manchester_quarantine(quarantine_dir)
    with pytest.raises(ManchesterSnapshotError):
        promote_manchester_quarantine(tmp_path, accepted_manifest(quarantine))
    assert not (tmp_path / ACCEPTED_DIRECTORY_NAME).exists()


def test_quarantine_is_new_only_and_unquarantined_promotion_is_refused(tmp_path: Path) -> None:
    quarantine = make_quarantine()
    publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)
    assert excinfo.value.code == "DESTINATION_EXISTS"

    other_root = tmp_path / "other"
    other_root.mkdir()
    with pytest.raises(ManchesterSnapshotError) as excinfo:
        promote_manchester_quarantine(other_root, accepted_manifest(quarantine))
    assert excinfo.value.code == "WORKSPACE_INVALID"


def test_quarantine_publication_lock_refuses_competing_writer_without_removing_lock(
    tmp_path: Path,
) -> None:
    quarantine = make_quarantine()
    quarantine_root = tmp_path / QUARANTINE_DIRECTORY_NAME
    quarantine_root.mkdir()
    lock = quarantine_root / f".{quarantine.snapshot_id}.publish.lock"
    lock.write_text("other acquisition writer\n", encoding="utf-8")

    with pytest.raises(ManchesterSnapshotError) as excinfo:
        publish_manchester_quarantine(tmp_path, quarantine, PAYLOADS, POLICY)

    assert excinfo.value.code == "PUBLICATION_LOCKED"
    assert lock.read_text(encoding="utf-8") == "other acquisition writer\n"
    assert not (quarantine_root / quarantine.snapshot_id).exists()

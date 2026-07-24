"""Tests for the REL-01 attested activation, backup, and rollback slice."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from traffictwin.release.attestation import (
    V06ProducerAttestation,
    build_v06_producer_attestation,
)
from traffictwin.release.compatibility import (
    V06_REGISTRY_SCHEMA_VERSION,
    initialise_v07_workspace,
)
from traffictwin.release.migration import (
    V06MigrationError,
    load_v06_migration_receipt,
    migrate_v06_registry,
    preview_v06_migration,
    rollback_v06_migration,
)
from traffictwin.storage.migrations import migrate_registry

FIXED_NOW = datetime(2026, 7, 24, 18, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attested_source(tmp_path: Path) -> tuple[Path, V06ProducerAttestation]:
    source = tmp_path / "v06.sqlite"
    migrate_registry(source, target_version=V06_REGISTRY_SCHEMA_VERSION)
    attestation = build_v06_producer_attestation(
        source, operator_name="Abdulla Al Mamun Akash", attested_at=FIXED_NOW
    )
    return source, attestation


def test_preview_is_read_only_and_binds_attested_provenance(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    source_before = source.read_bytes()
    active_before = workspace.active_registry_path.read_bytes()

    preview = preview_v06_migration(source, workspace.path, attestation)

    assert preview.operation == "attested_same_schema_activation"
    assert preview.source_product_version == "0.6.0"
    assert preview.attestation_fingerprint == attestation.fingerprint()
    assert preview.schema_transformation_required is False
    assert preview.automatic_execution is False
    assert preview.rollback_supported is True
    assert preview.has_required_space
    assert preview.migration_id.startswith("mig-")
    assert source.read_bytes() == source_before
    assert workspace.active_registry_path.read_bytes() == active_before


def test_preview_refuses_unbound_attestation_and_sidecars(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)

    with source.open("ab") as handle:
        handle.write(b"drift")
    with pytest.raises(V06MigrationError, match="ATTESTATION_NOT_VERIFIED"):
        preview_v06_migration(source, workspace.path, attestation)

    fresh, fresh_attestation = _attested_source(tmp_path / "fresh")
    fresh.with_name(fresh.name + "-wal").write_bytes(b"open")
    with pytest.raises(V06MigrationError, match="SOURCE_NOT_CHECKPOINTED"):
        preview_v06_migration(fresh, workspace.path, fresh_attestation)


def test_migration_backs_up_activates_and_receipts_byte_exactly(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    source_before = source.read_bytes()
    active_before = workspace.active_registry_path.read_bytes()

    result = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)

    assert source.read_bytes() == source_before
    assert workspace.active_registry_path.read_bytes() == source_before
    assert result.backup_registry_path.read_bytes() == active_before
    receipt = result.receipt
    assert receipt.active_registry_sha256_after == hashlib.sha256(source_before).hexdigest()
    assert receipt.backup_registry_sha256 == hashlib.sha256(active_before).hexdigest()
    assert receipt.scientific_admission == "unavailable"
    assert receipt.rollback_available is True
    persisted = load_v06_migration_receipt(result.receipt_path)
    assert persisted.fingerprint() == receipt.fingerprint()
    assert not any(path.name.startswith(".traffictwin") for path in workspace.path.iterdir())


def test_repeat_migration_and_quarantined_backup_are_refused(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    original_active = _sha256(workspace.active_registry_path)
    first = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    source_sha = _sha256(source)

    rollback_v06_migration(workspace.path, first.receipt_path, clock=lambda: FIXED_NOW)
    assert _sha256(workspace.active_registry_path) == original_active

    # Re-migrating the same source after rollback resumes idempotently and
    # re-activates it, reusing the same source-derived backup directory.
    resumed = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    assert resumed.backup_directory == first.backup_directory
    assert _sha256(workspace.active_registry_path) == source_sha

    # A backup directory that somehow lost its receipt is quarantined, not
    # silently overwritten.
    receipt_only_dir = first.receipt_path
    receipt_only_dir.unlink()
    with pytest.raises(V06MigrationError, match="MIGRATION_QUARANTINED"):
        migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)


def test_rollback_restores_previous_registry_and_preserves_backup(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    active_before = workspace.active_registry_path.read_bytes()
    result = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)

    rollback = rollback_v06_migration(workspace.path, result.receipt_path, clock=lambda: FIXED_NOW)

    assert workspace.active_registry_path.read_bytes() == active_before
    assert result.backup_registry_path.read_bytes() == active_before
    assert rollback.receipt.restored_registry_sha256 == hashlib.sha256(active_before).hexdigest()
    assert rollback.receipt.backup_preserved is True
    assert rollback.receipt_path.is_file()


def test_rollback_refuses_diverged_active_or_tampered_backup(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    result = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)

    with workspace.active_registry_path.open("ab") as handle:
        handle.write(b"new state")
    with pytest.raises(V06MigrationError, match="ACTIVE_REGISTRY_DIVERGED"):
        rollback_v06_migration(workspace.path, result.receipt_path, clock=lambda: FIXED_NOW)

    workspace.active_registry_path.write_bytes(source.read_bytes())
    with result.backup_registry_path.open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(V06MigrationError, match="BACKUP_BYTES_CHANGED"):
        rollback_v06_migration(workspace.path, result.receipt_path, clock=lambda: FIXED_NOW)


def test_receipt_reload_refuses_tampered_reconciliation(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    result = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)

    payload = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    payload["active_registry_sha256_after"] = "f" * 64
    tampered = tmp_path / "tampered-receipt.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(V06MigrationError, match="RECEIPT_INVALID"):
        load_v06_migration_receipt(tampered)


def test_active_registry_cannot_be_its_own_source(tmp_path: Path) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    attestation = build_v06_producer_attestation(
        workspace.active_registry_path,
        operator_name="Abdulla Al Mamun Akash",
        attested_at=FIXED_NOW,
    )

    with pytest.raises(V06MigrationError, match="SOURCE_IS_ACTIVE_REGISTRY"):
        preview_v06_migration(workspace.active_registry_path, workspace.path, attestation)


def test_cli_attest_migrate_and_rollback_chain(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from traffictwin.cli import app

    runner = CliRunner()
    source, _ = _attested_source(tmp_path)
    workspace = tmp_path / "workspace-v0.7"
    assert runner.invoke(app, ["release", "v07-workspace-init", str(workspace)]).exit_code == 0
    active = workspace / "registry" / "traffictwin.sqlite"
    active_before = _sha256(active)
    attestation_path = tmp_path / "attestation.json"

    attested = runner.invoke(
        app,
        [
            "release",
            "v06-attest",
            str(source),
            "--operator",
            "Abdulla Al Mamun Akash",
            "--output",
            str(attestation_path),
        ],
    )
    assert attested.exit_code == 0, attested.output
    assert "migration_approved: false" in attested.output

    preview = runner.invoke(
        app,
        [
            "release",
            "v06-migrate-preview",
            str(source),
            str(workspace),
            "--attestation",
            str(attestation_path),
        ],
    )
    assert preview.exit_code == 0, preview.output
    assert "operation: attested_same_schema_activation" in preview.output
    assert "source_product_version: 0.6.0 (operator attested)" in preview.output
    assert _sha256(active) == active_before

    migrated = runner.invoke(
        app,
        [
            "release",
            "v06-migrate",
            str(source),
            str(workspace),
            "--attestation",
            str(attestation_path),
        ],
    )
    assert migrated.exit_code == 0, migrated.output
    assert "rollback_available: true" in migrated.output
    assert "scientific_admission: unavailable" in migrated.output
    assert _sha256(active) == _sha256(source)
    receipt_line = next(
        line for line in migrated.output.splitlines() if line.startswith("receipt: ")
    )
    receipt_path = receipt_line.removeprefix("receipt: ").strip()

    rolled_back = runner.invoke(
        app,
        ["release", "v06-rollback", str(workspace), "--receipt", receipt_path],
    )
    assert rolled_back.exit_code == 0, rolled_back.output
    assert "backup_preserved: true" in rolled_back.output
    assert _sha256(active) == active_before


def test_rollback_receipt_refuses_path_traversal_backup(tmp_path: Path) -> None:
    """A hand-crafted receipt cannot steer the restore outside the workspace."""

    import hashlib as _hashlib

    from traffictwin.release.migration import V06MigrationError

    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    active = workspace.active_registry_path
    active_sha = _sha256(active)
    outside = tmp_path / "evil.sqlite"
    outside.write_bytes(b"attacker-controlled-bytes")
    evil_sha = _hashlib.sha256(outside.read_bytes()).hexdigest()

    # A receipt whose reconciliation passes but whose backup path traverses out.
    tampered = {
        "schema_version": "traffictwin.v06-migration.v1",
        "capability_id": "REL-01",
        "capability_status": "planned",
        "migration_id": "mig-" + "a" * 16,
        "migrated_at": "2026-07-24T12:00:00+00:00",
        "attestation_fingerprint": "b" * 64,
        "source_product_version": "0.6.0",
        "source_registry_sha256_before": active_sha,
        "source_registry_sha256_after": active_sha,
        "backup_registry_sha256": evil_sha,
        "active_registry_sha256_before": evil_sha,
        "active_registry_sha256_after": active_sha,
        "source_schema_version": 5,
        "target_schema_version": 5,
        "backup_registry_relative_path": "../evil.sqlite",
        "source_unchanged_during_migration": True,
        "rollback_available": True,
        "scientific_admission": "unavailable",
    }
    receipt_path = tmp_path / "tampered-receipt.json"
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(V06MigrationError, match="RECEIPT_INVALID"):
        rollback_v06_migration(workspace.path, receipt_path, clock=lambda: FIXED_NOW)
    # The active registry is untouched by the refused rollback.
    assert _sha256(active) == active_sha


def test_rollback_refuses_absolute_backup_path(tmp_path: Path) -> None:
    """An absolute backup path in a receipt is refused before any read."""

    import hashlib as _hashlib

    from traffictwin.release.migration import V06MigrationError

    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    active_sha = _sha256(workspace.active_registry_path)
    outside = tmp_path / "abs-evil.sqlite"
    outside.write_bytes(b"attacker")
    tampered = {
        "schema_version": "traffictwin.v06-migration.v1",
        "capability_id": "REL-01",
        "capability_status": "planned",
        "migration_id": "mig-" + "c" * 16,
        "migrated_at": "2026-07-24T12:00:00+00:00",
        "attestation_fingerprint": "d" * 64,
        "source_product_version": "0.6.0",
        "source_registry_sha256_before": active_sha,
        "source_registry_sha256_after": active_sha,
        "backup_registry_sha256": _hashlib.sha256(b"attacker").hexdigest(),
        "active_registry_sha256_before": _hashlib.sha256(b"attacker").hexdigest(),
        "active_registry_sha256_after": active_sha,
        "source_schema_version": 5,
        "target_schema_version": 5,
        "backup_registry_relative_path": str(outside),
        "source_unchanged_during_migration": True,
        "rollback_available": True,
        "scientific_admission": "unavailable",
    }
    receipt_path = tmp_path / "abs-receipt.json"
    receipt_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(V06MigrationError, match="RECEIPT_INVALID"):
        rollback_v06_migration(workspace.path, receipt_path, clock=lambda: FIXED_NOW)
    assert _sha256(workspace.active_registry_path) == active_sha


def test_crash_after_swap_before_receipt_is_resumable(tmp_path: Path) -> None:
    """A crash between activation and receipt cannot happen post-fix, but a crash
    between backup-publish and swap resumes to the activated state."""

    from unittest.mock import patch

    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    original_active = _sha256(workspace.active_registry_path)
    source_sha = _sha256(source)

    # Simulate power loss immediately after the backup+receipt directory is
    # published but before the active registry is swapped.
    def boom(src: object, dst: object) -> None:
        raise KeyboardInterrupt("crash before active swap")

    with (
        patch("traffictwin.release.migration.os.replace", boom),
        pytest.raises(KeyboardInterrupt),
    ):
        migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)

    # The active registry is still the original; backup + receipt are durable.
    assert _sha256(workspace.active_registry_path) == original_active
    backup_dir = next((workspace.path / "compatibility" / "backups").iterdir())
    assert (backup_dir / "migration-receipt.json").is_file()

    # A retry resumes deterministically and completes the activation.
    resumed = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    assert _sha256(workspace.active_registry_path) == source_sha
    # And the receipt from the interrupted run remains valid for rollback.
    rollback_v06_migration(workspace.path, resumed.receipt_path, clock=lambda: FIXED_NOW)
    assert _sha256(workspace.active_registry_path) == original_active


def test_already_activated_retry_is_idempotent(tmp_path: Path) -> None:
    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    first = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    source_sha = _sha256(source)

    again = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    assert again.backup_directory == first.backup_directory
    assert again.receipt.fingerprint() == first.receipt.fingerprint()
    assert _sha256(workspace.active_registry_path) == source_sha


def test_migration_refuses_source_inside_workspace(tmp_path: Path) -> None:
    from traffictwin.release.migration import V06MigrationError

    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    # A compatibility copy lives inside the workspace and must not be a source.
    inside = workspace.path / "compatibility" / "v0.6" / "copy" / "registry.sqlite"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(source.read_bytes())
    inside_attestation = build_v06_producer_attestation(
        inside, operator_name="Op", attested_at=FIXED_NOW
    )
    with pytest.raises(V06MigrationError, match="SOURCE_INSIDE_WORKSPACE"):
        preview_v06_migration(inside, workspace.path, inside_attestation)


def test_rollback_receipt_reloads_and_is_write_once(tmp_path: Path) -> None:
    from traffictwin.release.migration import (
        load_v06_rollback_receipt,
    )

    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    result = migrate_v06_registry(source, workspace.path, attestation, clock=lambda: FIXED_NOW)
    rollback = rollback_v06_migration(workspace.path, result.receipt_path, clock=lambda: FIXED_NOW)

    reloaded = load_v06_rollback_receipt(rollback.receipt_path)
    assert reloaded.fingerprint() == rollback.receipt.fingerprint()
    assert reloaded.migration_id == result.receipt.migration_id

    # A second rollback is idempotent: the registry is already restored, so it
    # returns the same recorded rollback receipt rather than acting again.
    again = rollback_v06_migration(workspace.path, result.receipt_path, clock=lambda: FIXED_NOW)
    assert again.receipt.fingerprint() == rollback.receipt.fingerprint()


def test_migration_refusal_branches(tmp_path: Path) -> None:
    from traffictwin.release.migration import (
        V06MigrationError,
        load_v06_migration_receipt,
        preview_v06_migration,
    )

    source, attestation = _attested_source(tmp_path)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)

    # Oversized / missing receipt refusals.
    big = tmp_path / "big.json"
    big.write_text("x" * (64 * 1024 + 1), encoding="utf-8")
    with pytest.raises(V06MigrationError, match="RECEIPT_OVERSIZED"):
        load_v06_migration_receipt(big)
    with pytest.raises(V06MigrationError, match="RECEIPT_MISSING_OR_UNSAFE"):
        load_v06_migration_receipt(tmp_path / "absent.json")

    # Naive clock is refused.
    with pytest.raises(V06MigrationError, match="NAIVE_CLOCK"):
        migrate_v06_registry(
            source,
            workspace.path,
            attestation,
            clock=lambda: FIXED_NOW.replace(tzinfo=None),
        )
    # The workspace is unchanged after the refusal.
    assert (
        preview_v06_migration(source, workspace.path, attestation).source_product_version == "0.6.0"
    )

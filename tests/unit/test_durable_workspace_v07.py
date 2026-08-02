from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.release.durable_workspace import (
    DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH,
    V07DurableWorkspaceError,
    create_durable_v07_workspace,
    load_durable_workspace_receipt,
    preview_durable_v07_workspace,
)

FIXED_NOW = datetime(2026, 8, 3, 9, 30, tzinfo=UTC)


def _private_parent(tmp_path: Path) -> Path:
    parent = tmp_path / "private-owner-root"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    return parent


def test_preview_is_path_free_stable_and_mutation_free(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"

    first = preview_durable_v07_workspace(target)
    second = preview_durable_v07_workspace(target)

    assert first.workspace_handle.startswith("workspace-")
    assert first.target_absent is True
    assert first.parent_owner_only is True
    assert first.activatable is True
    assert first.confirmation_fingerprint() == second.confirmation_fingerprint()
    assert not target.exists()
    assert str(parent) not in first.model_dump_json()


def test_preview_refuses_repository_descendant_and_unsafe_parent(tmp_path: Path) -> None:
    repository_target = Path(__file__).resolve().parents[2] / "unsafe-workspace-v0.7"
    with pytest.raises(V07DurableWorkspaceError, match="REPOSITORY_TARGET_FORBIDDEN"):
        preview_durable_v07_workspace(repository_target)

    parent = tmp_path / "shared"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    with pytest.raises(V07DurableWorkspaceError, match="PARENT_PERMISSIONS_UNSAFE"):
        preview_durable_v07_workspace(parent / "workspace-v0.7")


def test_create_publishes_owner_only_workspace_backup_and_receipt(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)

    result = create_durable_v07_workspace(
        target,
        expected_plan_fingerprint=plan.confirmation_fingerprint(),
        clock=lambda: FIXED_NOW,
    )

    assert result.workspace_path == target
    assert result.inspection.valid is True
    assert result.receipt.created_at_utc == FIXED_NOW
    assert result.receipt.contains_accepted_source_data is False
    assert result.receipt.source_acquisition_performed is False
    assert result.receipt.baseline_backup.isolated_restore_verified is True
    assert result.receipt.active_registry_sha256 == result.receipt.baseline_backup.backup_sha256
    assert (target / DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH).is_file()
    assert load_durable_workspace_receipt(target) == result.receipt
    assert stat.S_IMODE(target.stat().st_mode) == 0o700
    for directory, _, files in os.walk(target):
        assert stat.S_IMODE(Path(directory).stat().st_mode) == 0o700
        for name in files:
            assert stat.S_IMODE((Path(directory) / name).stat().st_mode) == 0o600
    assert list((target / "manchester/accepted").iterdir()) == []
    assert str(target) not in result.receipt.model_dump_json()


def test_confirmation_mismatch_refuses_without_target_or_staging(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"

    with pytest.raises(V07DurableWorkspaceError, match="PLAN_MISMATCH"):
        create_durable_v07_workspace(target, expected_plan_fingerprint="0" * 64)

    assert not target.exists()
    assert list(parent.iterdir()) == []


def test_exact_retry_returns_verified_existing_receipt(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)
    expected = plan.confirmation_fingerprint()
    first = create_durable_v07_workspace(target, expected_plan_fingerprint=expected)

    retried = create_durable_v07_workspace(target, expected_plan_fingerprint=expected)

    assert first.receipt.exact_retry is False
    assert retried.receipt.exact_retry is True
    assert retried.receipt.fingerprint() != first.receipt.fingerprint()
    assert load_durable_workspace_receipt(target).exact_retry is False


@pytest.mark.parametrize(
    "fault_stage",
    ["workspace_created", "baseline_backup_verified", "receipt_written", "before_publish"],
)
def test_prepublication_fault_cleans_owned_staging(tmp_path: Path, fault_stage: str) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)

    def fail(stage: str) -> None:
        if stage == fault_stage:
            raise RuntimeError("injected stop")

    with pytest.raises(RuntimeError, match="injected stop"):
        create_durable_v07_workspace(
            target,
            expected_plan_fingerprint=plan.confirmation_fingerprint(),
            fault_hook=fail,
        )

    assert not target.exists()
    assert list(parent.iterdir()) == []


def test_target_appearing_at_publication_is_not_overwritten(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)

    def collide(stage: str) -> None:
        if stage == "before_publish":
            target.mkdir(mode=0o700)

    with pytest.raises(V07DurableWorkspaceError, match="TARGET_COLLISION"):
        create_durable_v07_workspace(
            target,
            expected_plan_fingerprint=plan.confirmation_fingerprint(),
            fault_hook=collide,
        )

    assert target.is_dir()
    assert list(target.iterdir()) == []
    assert [item for item in parent.iterdir() if item != target] == []


def test_postpublication_fault_is_recoverable_by_exact_retry(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)
    expected = plan.confirmation_fingerprint()

    def fail(stage: str) -> None:
        if stage == "after_publish":
            raise RuntimeError("lost caller after publish")

    with pytest.raises(RuntimeError, match="lost caller"):
        create_durable_v07_workspace(
            target,
            expected_plan_fingerprint=expected,
            fault_hook=fail,
        )

    recovered = create_durable_v07_workspace(target, expected_plan_fingerprint=expected)
    assert recovered.receipt.exact_retry is True


def test_existing_unmanaged_target_and_backup_drift_fail_closed(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    unmanaged = parent / "unmanaged"
    unmanaged.mkdir(mode=0o700)
    with pytest.raises(V07DurableWorkspaceError, match="EXISTING_TARGET_UNMANAGED"):
        create_durable_v07_workspace(
            unmanaged,
            expected_plan_fingerprint="1" * 64,
        )

    target = parent / "workspace-v0.7"
    plan = preview_durable_v07_workspace(target)
    expected = plan.confirmation_fingerprint()
    create_durable_v07_workspace(target, expected_plan_fingerprint=expected)
    backup = target / DURABLE_WORKSPACE_BACKUP_RELATIVE_PATH
    backup.write_bytes(b"corrupt")
    backup.chmod(0o600)
    with pytest.raises(V07DurableWorkspaceError, match="BACKUP_INVALID"):
        create_durable_v07_workspace(target, expected_plan_fingerprint=expected)


def test_orphan_staging_blocks_preview_without_deleting_it(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    orphan = parent / ".traffictwin-v07-durable-deadbeefdeadbeef"
    orphan.mkdir(mode=0o700)

    plan = preview_durable_v07_workspace(parent / "workspace-v0.7")

    assert plan.activatable is False
    assert plan.blockers == ("ORPHAN_STAGING_PRESENT",)
    assert len(plan.orphan_staging_handles) == 1
    assert orphan.is_dir()
    assert str(orphan) not in plan.model_dump_json()


def test_symlinked_parent_and_path_bearing_io_error_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = _private_parent(tmp_path)
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(parent, target_is_directory=True)
    with pytest.raises(V07DurableWorkspaceError, match="PARENT_INVALID"):
        preview_durable_v07_workspace(linked_parent / "workspace-v0.7")

    def fail_disk_usage(_: Path) -> None:
        raise OSError(f"private path: {parent}")

    monkeypatch.setattr("traffictwin.release.durable_workspace.shutil.disk_usage", fail_disk_usage)
    with pytest.raises(V07DurableWorkspaceError) as captured:
        preview_durable_v07_workspace(parent / "workspace-v0.7")
    assert captured.value.code == "WORKSPACE_IO_FAILED"
    assert str(parent) not in str(captured.value)


def test_cli_preview_and_create_are_path_free_and_confirmation_gated(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    runner = CliRunner()

    preview = runner.invoke(
        app,
        ["release", "v07-durable-preview", str(target), "--format", "json"],
    )
    assert preview.exit_code == 0, preview.output
    payload = json.loads(preview.output)
    assert payload["activatable"] is True
    assert str(target) not in preview.output

    refused = runner.invoke(
        app,
        [
            "release",
            "v07-durable-create",
            str(target),
            "--expected-plan",
            "0" * 64,
        ],
    )
    assert refused.exit_code == 1
    assert "PLAN_MISMATCH" in refused.output
    assert not target.exists()

    created = runner.invoke(
        app,
        [
            "release",
            "v07-durable-create",
            str(target),
            "--expected-plan",
            payload["plan_fingerprint"],
            "--format",
            "json",
        ],
    )
    assert created.exit_code == 0, created.output
    receipt = json.loads(created.output)
    assert receipt["workspace_reopened_and_verified"] is True
    assert receipt["contains_accepted_source_data"] is False
    assert str(target) not in created.output


def test_cli_rejects_unknown_output_format_before_mutation(tmp_path: Path) -> None:
    parent = _private_parent(tmp_path)
    target = parent / "workspace-v0.7"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "release",
            "v07-durable-create",
            str(target),
            "--expected-plan",
            "0" * 64,
            "--format",
            "yaml",
        ],
    )

    assert result.exit_code == 1
    assert not target.exists()

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

import traffictwin.release.compatibility as compatibility
from traffictwin.release.compatibility import (
    V06_REGISTRY_SCHEMA_VERSION,
    V06RegistryCopyError,
    V07WorkspaceError,
    copy_v06_registry,
    initialise_v07_workspace,
    inspect_v07_workspace,
    preview_v06_registry_copy,
    v07_workspace_contract,
)
from traffictwin.storage.migrations import CURRENT_REGISTRY_SCHEMA_VERSION, migrate_registry

FIXED_NOW = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _closed_registry(path: Path) -> Path:
    migrate_registry(path, target_version=V06_REGISTRY_SCHEMA_VERSION)
    return path


def test_contract_keeps_foundation_planned_and_copy_only() -> None:
    contract = v07_workspace_contract()

    assert contract.capability_id == "REL-01"
    assert contract.capability_status == "planned"
    assert contract.workspace_namespace == "workspace-v0.7"
    assert contract.cache_namespace == "traffictwin-cache-v0.7"
    assert any("No in-place" in item for item in contract.exclusions)
    assert any("remain pending" in item for item in contract.limitations)
    assert len(contract.fingerprint()) == 64


def test_initialise_creates_exact_separate_workspace_and_current_registry(tmp_path: Path) -> None:
    target = tmp_path / "workspace-v0.7"

    result = initialise_v07_workspace(target, clock=lambda: FIXED_NOW)

    assert result.path == target
    assert result.inspection.valid is True
    assert result.inspection.manifest.created_at == FIXED_NOW
    assert result.inspection.manifest.workspace_namespace == "workspace-v0.7"
    assert result.inspection.manifest.cache_namespace == "traffictwin-cache-v0.7"
    assert result.inspection.manifest.compatibility_source_mutation_allowed is False
    assert result.inspection.manifest.compatibility_activation_automatic is False
    assert (
        result.inspection.active_registry_status.current_version == CURRENT_REGISTRY_SCHEMA_VERSION
    )
    assert (target / "manchester/raw").is_dir()
    assert (target / "compatibility/v0.6").is_dir()


def test_initialise_is_new_only_and_preserves_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "valuable"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("do not replace", encoding="utf-8")

    with pytest.raises(FileExistsError, match="already exists"):
        initialise_v07_workspace(target, clock=lambda: FIXED_NOW)

    assert marker.read_text(encoding="utf-8") == "do not replace"


def test_workspace_inspection_refuses_tampered_or_symlinked_layout(tmp_path: Path) -> None:
    target = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW).path
    manifest_path = target / compatibility.V07_MANIFEST_NAME
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["cache_namespace"] = "shared-with-v0.6"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(V07WorkspaceError, match="invalid v0.7 workspace manifest"):
        inspect_v07_workspace(target)

    target_two = initialise_v07_workspace(
        tmp_path / "workspace-v0.7-two", clock=lambda: FIXED_NOW
    ).path
    raw = target_two / "manchester/raw"
    raw.rmdir()
    raw.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(V07WorkspaceError, match="escapes its root|missing or unsafe"):
        inspect_v07_workspace(target_two)


def test_preview_is_read_only_and_reports_unknown_product_version(tmp_path: Path) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    source_before = source.read_bytes()
    active_before = workspace.active_registry_path.read_bytes()

    preview = preview_v06_registry_copy(source, workspace.path)

    assert preview.operation == "copy_only_not_migration"
    assert preview.source_product_version is None
    assert preview.source_registry_schema_version == V06_REGISTRY_SCHEMA_VERSION
    assert preview.backup_required is False
    assert preview.automatic_activation is False
    assert preview.target_relative_directory.startswith("compatibility/v0.6/")
    assert preview.has_required_space
    assert source.read_bytes() == source_before
    assert workspace.active_registry_path.read_bytes() == active_before


def test_copy_is_byte_exact_receipted_and_never_activates(tmp_path: Path) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    with sqlite3.connect(source) as conn:
        conn.execute(
            "INSERT INTO seeds VALUES (?, ?, ?, ?)",
            (
                "preserved-seed",
                '{"marker":"preserve exact payload"}',
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    source_before = source.read_bytes()
    active_before = workspace.active_registry_path.read_bytes()

    result = copy_v06_registry(source, workspace.path, clock=lambda: FIXED_NOW)

    assert result.registry_path.read_bytes() == source_before
    assert source.read_bytes() == source_before
    assert workspace.active_registry_path.read_bytes() == active_before
    assert result.receipt.byte_exact is True
    assert result.receipt.automatic_activation is False
    assert result.receipt.scientific_admission == "unavailable"
    assert result.receipt.source_registry_sha256_before == _sha256(source)
    assert result.receipt.copied_registry_sha256 == _sha256(result.registry_path)
    persisted = json.loads(result.receipt_path.read_text(encoding="utf-8"))
    assert persisted == result.receipt.model_dump(mode="json")
    assert not any(
        path.name.startswith(".traffictwin") for path in result.directory.parent.iterdir()
    )


def test_copy_refuses_existing_snapshot_without_replacing_it(tmp_path: Path) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    first = copy_v06_registry(source, workspace.path, clock=lambda: FIXED_NOW)
    first_registry = first.registry_path.read_bytes()
    first_receipt = first.receipt_path.read_bytes()

    with pytest.raises(FileExistsError, match="already exists"):
        copy_v06_registry(source, workspace.path, clock=lambda: FIXED_NOW)

    assert first.registry_path.read_bytes() == first_registry
    assert first.receipt_path.read_bytes() == first_receipt


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_preview_refuses_open_or_uncheckpointed_source_sidecars(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    Path(f"{source}{suffix}").write_bytes(b"not closed")
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)

    with pytest.raises(V06RegistryCopyError, match="closed and checkpointed"):
        preview_v06_registry_copy(source, workspace.path)


def test_preview_refuses_symlink_and_source_inside_target_workspace(tmp_path: Path) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    source_link = tmp_path / "linked.sqlite"
    source_link.symlink_to(source)
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)

    with pytest.raises(V07WorkspaceError, match="non-symlinked regular file"):
        preview_v06_registry_copy(source_link, workspace.path)

    inside = _closed_registry(workspace.path / "compatibility/v0.6/source.sqlite")
    with pytest.raises(V06RegistryCopyError, match="outside the v0.7 workspace"):
        preview_v06_registry_copy(inside, workspace.path)


def test_copy_failure_cleans_staging_and_preserves_both_registries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _closed_registry(tmp_path / "v0.6.sqlite")
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7", clock=lambda: FIXED_NOW)
    source_before = source.read_bytes()
    active_before = workspace.active_registry_path.read_bytes()

    def corrupt_copy(source_path: str | Path, destination_path: str | Path) -> None:
        del source_path
        Path(destination_path).write_bytes(b"not sqlite")

    monkeypatch.setattr("traffictwin.release.compatibility.shutil.copyfile", corrupt_copy)

    with pytest.raises(V06RegistryCopyError, match="verification failed"):
        copy_v06_registry(source, workspace.path, clock=lambda: FIXED_NOW)

    compatibility_root = workspace.path / compatibility.V06_COMPATIBILITY_ROOT
    assert list(compatibility_root.iterdir()) == []
    assert source.read_bytes() == source_before
    assert workspace.active_registry_path.read_bytes() == active_before


def test_naive_clock_is_rejected_without_publishing_workspace(tmp_path: Path) -> None:
    target = tmp_path / "workspace-v0.7"

    with pytest.raises(ValueError, match="timezone-aware"):
        initialise_v07_workspace(target, clock=lambda: datetime(2026, 7, 22, 12, 0))

    assert not target.exists()
    assert not any(path.name.startswith(".traffictwin-v07") for path in tmp_path.iterdir())

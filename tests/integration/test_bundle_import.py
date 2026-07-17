from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from traffictwin.ingestion.bundle import import_bundle, validate_bundle
from traffictwin.storage.registry import Registry, RegistryConflictError
from traffictwin.validation.report import ImportStatus


def test_directory_bundle_validate_and_import(tmp_path: Path) -> None:
    bundle = Path("tests/fixtures/bundles/baseline_valid")
    registry_path = tmp_path / "registry.sqlite"

    validation = validate_bundle(bundle)
    imported = import_bundle(bundle, registry_path)
    summary = Registry(registry_path).inspect()

    assert validation.report.status is ImportStatus.ACCEPTED
    assert imported.created
    assert not imported.idempotent
    assert summary.run_count == 1
    assert summary.bundle_import_count == 1
    assert Registry(registry_path).get_run("run-baseline-001").seed_id == "s1-gridlock-baseline"


def test_repeated_import_is_idempotent(tmp_path: Path) -> None:
    bundle = Path("tests/fixtures/bundles/baseline_valid")
    registry_path = tmp_path / "registry.sqlite"

    first = import_bundle(bundle, registry_path)
    second = import_bundle(bundle, registry_path)

    assert first.created
    assert second.idempotent
    assert Registry(registry_path).inspect().bundle_import_count == 1


def test_conflicting_run_id_is_rejected(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    conflict_bundle = tmp_path / "conflict"
    import_bundle(Path("tests/fixtures/bundles/baseline_valid"), registry_path)
    shutil.copytree(Path("tests/fixtures/bundles/baseline_valid"), conflict_bundle)
    manifest = conflict_bundle / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "bundle-baseline-001",
            "bundle-conflict-001",
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryConflictError, match="run_id already exists"):
        import_bundle(conflict_bundle, registry_path)


def test_partial_bundle_imports_with_warnings(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    result = import_bundle(Path("tests/fixtures/bundles/partial_valid"), registry_path)

    assert result.created
    assert result.status == "accepted_with_warnings"
    assert Registry(registry_path).inspect().run_count == 1

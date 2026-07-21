from __future__ import annotations

import hashlib
import os
import shutil
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version
from pathlib import Path

import pytest
import yaml

from tests.helpers import FIXTURES, fixed_clock
from traffictwin.config.capabilities import CapabilitySupport, default_export_import_manifest
from traffictwin.doctor import (
    DoctorCheck,
    DoctorCheckStatus,
    DoctorOverallStatus,
    DoctorReport,
    doctor_contract,
    run_doctor,
)
from traffictwin.ingestion.bundle import inspect_bundle_cache, validate_bundle_cached
from traffictwin.ingestion.cache import CanonicalCacheState
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest
from traffictwin.storage.migrations import migrate_registry


def _inventory(root: Path) -> dict[str, tuple[str, int, int]]:
    if root.is_file():
        return {
            root.name: (
                hashlib.sha256(root.read_bytes()).hexdigest(),
                root.stat().st_size,
                root.stat().st_mtime_ns,
            )
        }
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _minimal_workspace(path: Path) -> Path:
    path.mkdir()
    for name in ("seeds", "bundles", "reports", "exports", "logs"):
        (path / name).mkdir()
    (path / "workspace.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "workspace_type": "traffictwin_standalone_demo",
                "synthetic": True,
                "registry": "registry.sqlite",
                "scenarios": [],
                "comparisons": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    migrate_registry(path / "registry.sqlite", clock=fixed_clock)
    return path


def _copy_baseline(path: Path) -> Path:
    destination = path / "bundle"
    shutil.copytree(FIXTURES / "baseline_valid", destination)
    return destination


def _check(report: DoctorReport, check_id: str) -> DoctorCheck:
    return next(item for item in report.checks if item.check_id == check_id)


def test_doctor_contract_and_capability_boundaries_are_explicit() -> None:
    contract = doctor_contract()

    assert contract.capability_id == "OPS-03"
    assert contract.contract_version == "traffictwin-doctor-v1"
    assert contract.command == "traffictwin doctor"
    assert "numpy" in contract.optional_distributions
    assert "sumo" in contract.optional_commands
    assert len(contract.fingerprint()) == 64
    assert default_export_import_manifest().supports.environment_doctor is CapabilitySupport.TRUE
    assert sumo_results_capability_manifest().supports.environment_doctor is CapabilitySupport.FALSE
    assert tos_data_capability_manifest().supports.environment_doctor is CapabilitySupport.FALSE


def test_default_doctor_is_healthy_while_optional_absence_and_blockers_stay_visible() -> None:
    report = run_doctor()

    assert report.overall_status is DoctorOverallStatus.HEALTHY
    assert report.read_only
    assert not report.mutations_performed
    assert _check(report, "integration.generic-import").status is DoctorCheckStatus.PASS
    assert _check(report, "capability.direct-launch").status is DoctorCheckStatus.BLOCKED
    assert not _check(report, "capability.direct-launch").required
    assert _check(report, "permission.tos-publication").status is DoctorCheckStatus.UNAVAILABLE
    assert len(report.fingerprint()) == 64


def test_missing_optional_dependency_does_not_break_the_core_installation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def without_numpy(name: str) -> str:
        if name == "numpy":
            raise PackageNotFoundError(name)
        return distribution_version(name)

    monkeypatch.setattr("traffictwin.doctor.distribution_version", without_numpy)

    report = run_doctor()

    numpy = next(item for item in report.dependencies if item.name == "numpy")
    assert not numpy.available
    assert not numpy.required
    assert _check(report, "dependency.optional.numpy").status is DoctorCheckStatus.UNAVAILABLE
    assert _check(report, "integration.tos-read-only").status is DoctorCheckStatus.UNAVAILABLE
    assert report.overall_status is DoctorOverallStatus.HEALTHY


def test_healthy_workspace_and_registry_are_inspected_without_mutation(tmp_path: Path) -> None:
    workspace = _minimal_workspace(tmp_path / "workspace")
    before = _inventory(workspace)

    first = run_doctor(workspace=workspace)
    second = run_doctor(workspace=workspace, registry=workspace / "registry.sqlite")

    assert first.overall_status is DoctorOverallStatus.HEALTHY
    assert first.workspace is not None
    assert first.workspace.status is DoctorCheckStatus.PASS
    assert len(first.registries) == 1
    assert first.registries[0].status is DoctorCheckStatus.PASS
    assert first.registries[0].migration is not None
    assert first.registries[0].migration.integrity_check == "ok"
    assert len(second.registries) == 1
    assert second.registries[0].sources == ["workspace", "explicit"]
    assert before == _inventory(workspace)


def test_corrupt_registry_copy_is_blocked_and_unchanged(tmp_path: Path) -> None:
    registry = tmp_path / "corrupt.sqlite"
    registry.write_bytes(b"not a sqlite database\x00raw-copy")
    before = _inventory(registry)

    report = run_doctor(registry=registry)

    assert report.overall_status is DoctorOverallStatus.BLOCKED
    assert report.blocking_check_ids == ["registry.target-1.integrity"]
    assert report.registries[0].status is DoctorCheckStatus.BLOCKED
    assert report.registries[0].migration is None
    assert "inspection failed" in (report.registries[0].error or "")
    assert before == _inventory(registry)


def test_stale_cache_is_visible_degraded_and_no_input_is_mutated(tmp_path: Path) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"
    old = validate_bundle_cached(bundle, cache_root)
    with (bundle / "tasks.csv").open("a", encoding="utf-8") as handle:
        handle.write("t4,veh-4,T1,10,100,local,true,10.05,50,\n")
    expected = inspect_bundle_cache(bundle, cache_root)
    assert expected.state is CanonicalCacheState.MISS
    assert expected.cache_entry is not None
    shutil.copytree(Path(old.cache.cache_entry or ""), Path(expected.cache_entry))
    bundle_before = _inventory(bundle)
    cache_before = _inventory(cache_root)

    report = run_doctor(bundle=bundle, cache_root=cache_root)

    assert report.overall_status is DoctorOverallStatus.DEGRADED
    assert report.cache is not None
    assert report.cache.state is CanonicalCacheState.STALE
    assert _check(report, "cache.integrity").status is DoctorCheckStatus.WARNING
    assert bundle_before == _inventory(bundle)
    assert cache_before == _inventory(cache_root)


def test_cache_miss_is_read_only_and_does_not_create_the_requested_root(tmp_path: Path) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "absent-cache"
    before = _inventory(bundle)

    report = run_doctor(bundle=bundle, cache_root=cache_root)

    assert report.overall_status is DoctorOverallStatus.DEGRADED
    assert report.cache is not None
    assert report.cache.state is CanonicalCacheState.MISS
    assert not cache_root.exists()
    assert before == _inventory(bundle)


def test_permission_limited_registry_is_blocked_without_opening_or_changing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "permission-limited.sqlite"
    migrate_registry(registry, clock=fixed_clock)
    before = _inventory(registry)
    original_mode = registry.stat().st_mode
    registry.chmod(0)
    real_access = os.access

    def deny_registry_read(path: os.PathLike[str] | str, mode: int) -> bool:
        if Path(path).resolve() == registry.resolve() and mode & os.R_OK:
            return False
        return real_access(path, mode)

    monkeypatch.setattr("traffictwin.doctor.os.access", deny_registry_read)
    try:
        report = run_doctor(registry=registry)
    finally:
        registry.chmod(original_mode)

    assert report.overall_status is DoctorOverallStatus.BLOCKED
    assert _check(report, "permission.registry.target-1.read").status is DoctorCheckStatus.BLOCKED
    assert report.registries[0].migration is None
    assert before == _inventory(registry)


def test_unpaired_cache_options_and_unsafe_workspace_declaration_are_blocked(
    tmp_path: Path,
) -> None:
    bundle = _copy_baseline(tmp_path)
    missing_option = run_doctor(bundle=bundle)
    workspace = _minimal_workspace(tmp_path / "workspace")
    manifest_path = workspace / "workspace.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["scenarios"] = [{"name": "escape", "bundle": "../outside"}]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    unsafe = run_doctor(workspace=workspace)

    assert missing_option.overall_status is DoctorOverallStatus.BLOCKED
    assert "configuration.cache-targets" in missing_option.blocking_check_ids
    assert unsafe.overall_status is DoctorOverallStatus.BLOCKED
    assert unsafe.workspace is not None
    assert unsafe.workspace.unsafe_declared_paths == ["../outside"]

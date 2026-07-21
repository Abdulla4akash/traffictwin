from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml

from tests.helpers import FIXTURES, fixed_clock
from traffictwin.config.capabilities import (
    CapabilitySupport,
    default_export_import_manifest,
)
from traffictwin.ingestion.bundle import (
    inspect_bundle_cache,
    validate_bundle,
    validate_bundle_cached,
)
from traffictwin.ingestion.cache import (
    CanonicalCacheConfigurationError,
    CanonicalCacheState,
    canonical_cache_contract,
    canonical_cache_key,
)
from traffictwin.integration.sumo import sumo_results_capability_manifest
from traffictwin.integration.tos import tos_data_capability_manifest
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def _inventory(root: Path) -> dict[str, tuple[str, int, int]]:
    return {
        path.relative_to(root).as_posix(): (
            hashlib.sha256(path.read_bytes()).hexdigest(),
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _copy_baseline(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    destination = tmp_path / "bundle"
    shutil.copytree(FIXTURES / "baseline_valid", destination)
    return destination


def test_cache_contract_binds_every_required_identity_and_capability_boundary() -> None:
    contract = canonical_cache_contract()

    assert contract.capability_id == "OPS-02"
    assert contract.contract_version == "canonical-parquet-cache-v1"
    assert contract.canonical_tables == [
        "tasks",
        "infrastructure",
        "vehicles",
        "traffic",
        "trips",
        "incidents",
    ]
    assert {
        "raw_bundle_fingerprint",
        "adapter_version",
        "manifest_mapping_fingerprint",
        "canonical_schema_fingerprint",
    }.issubset(contract.key_components)
    assert len(contract.canonical_schema_fingerprint) == 64
    assert len(contract.fingerprint()) == 64
    assert (
        default_export_import_manifest().supports.canonical_table_caching is CapabilitySupport.TRUE
    )
    assert (
        sumo_results_capability_manifest().supports.canonical_table_caching
        is CapabilitySupport.FALSE
    )
    assert (
        tos_data_capability_manifest().supports.canonical_table_caching is CapabilitySupport.FALSE
    )


def test_cold_write_and_warm_hit_are_exact_and_do_not_mutate_raw_or_cache(
    tmp_path: Path,
) -> None:
    bundle = write_synthetic_bundle(preset_config("stressed_demand"), tmp_path / "bundle")
    cache_root = tmp_path / "cache"
    raw_before = _inventory(bundle)

    first = validate_bundle_cached(bundle, cache_root)
    raw_after_write = _inventory(bundle)
    cache_after_write = _inventory(cache_root)
    second = validate_bundle_cached(bundle, cache_root)

    assert first.cache.state is CanonicalCacheState.WRITTEN
    assert second.cache.state is CanonicalCacheState.HIT
    assert second.validation == first.validation
    assert compute_metrics_for_bundle(
        second.validation,
        clock=fixed_clock,
    ) == compute_metrics_for_bundle(first.validation, clock=fixed_clock)
    assert raw_before == raw_after_write == _inventory(bundle)
    assert cache_after_write == _inventory(cache_root)
    assert {path.suffix for path in cache_root.rglob("*.parquet")} == {".parquet"}
    assert len(list(cache_root.rglob("*.parquet"))) == 6
    assert first.validation.canonical.vehicles
    assert first.validation.canonical.incidents


def test_status_is_read_only_and_a_miss_does_not_create_the_cache_root(tmp_path: Path) -> None:
    cache_root = tmp_path / "absent-cache"

    status = inspect_bundle_cache(FIXTURES / "baseline_valid", cache_root)

    assert status.state is CanonicalCacheState.MISS
    assert not cache_root.exists()


def test_rejected_bundle_is_never_published(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"

    result = validate_bundle_cached(FIXTURES / "invalid_rows", cache_root)

    assert not result.validation.report.may_import
    assert result.cache.state is CanonicalCacheState.UNAVAILABLE
    assert not cache_root.exists()


def test_raw_change_invalidates_the_entry_and_publishes_a_new_key(
    tmp_path: Path,
) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"
    first = validate_bundle_cached(bundle, cache_root)
    first_entry = Path(first.cache.cache_entry or "")
    with (bundle / "tasks.csv").open("a", encoding="utf-8") as handle:
        handle.write("t4,veh-4,T1,10,100,local,true,10.05,50,\n")

    status = inspect_bundle_cache(bundle, cache_root)
    second = validate_bundle_cached(bundle, cache_root)

    assert status.state is CanonicalCacheState.MISS
    assert second.cache.state is CanonicalCacheState.WRITTEN
    assert second.cache.cache_key != first.cache.cache_key
    assert first_entry.exists()
    assert len([path for path in cache_root.iterdir() if path.is_dir()]) == 2


def test_key_changes_for_mapping_adapter_validator_schema_and_format() -> None:
    result = validate_bundle(FIXTURES / "baseline_valid")
    assert result.fingerprint is not None
    assert result.manifest is not None
    base = canonical_cache_key(result.fingerprint, result.manifest)
    payload = result.manifest.model_dump(mode="json")
    payload["files"]["tasks"]["units"]["deadline_ms"] = "s"
    changed_manifest = type(result.manifest).model_validate(payload)

    variants = {
        canonical_cache_key(result.fingerprint, changed_manifest).fingerprint(),
        canonical_cache_key(
            result.fingerprint,
            result.manifest,
            adapter_version="generic-tabular-v2",
        ).fingerprint(),
        canonical_cache_key(
            result.fingerprint,
            result.manifest,
            validator_version="future-validator",
        ).fingerprint(),
        canonical_cache_key(
            result.fingerprint,
            result.manifest,
            schema_fingerprint="1" * 64,
        ).fingerprint(),
        canonical_cache_key(
            result.fingerprint,
            result.manifest,
            cache_format_version="future-format",
        ).fingerprint(),
    }

    assert base.fingerprint() not in variants
    assert len(variants) == 5


def test_corrupt_checksum_falls_back_to_raw_without_overwriting_bad_entry(
    tmp_path: Path,
) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"
    first = validate_bundle_cached(bundle, cache_root)
    entry = Path(first.cache.cache_entry or "")
    tasks_cache = entry / "tasks.parquet"
    tasks_cache.write_bytes(tasks_cache.read_bytes() + b"tamper")
    bad_bytes = tasks_cache.read_bytes()

    status = inspect_bundle_cache(bundle, cache_root)
    fallback = validate_bundle_cached(bundle, cache_root)

    assert status.state is CanonicalCacheState.CORRUPT
    assert "size mismatch" in status.detail
    assert fallback.cache.state is CanonicalCacheState.CORRUPT
    assert fallback.validation.report.may_import
    assert fallback.validation.canonical == validate_bundle(bundle).canonical
    assert tasks_cache.read_bytes() == bad_bytes


def test_stale_and_incompatible_entries_are_visibly_rejected(tmp_path: Path) -> None:
    stale_bundle = _copy_baseline(tmp_path / "stale")
    stale_cache = tmp_path / "stale-cache"
    old = validate_bundle_cached(stale_bundle, stale_cache)
    with (stale_bundle / "tasks.csv").open("a", encoding="utf-8") as handle:
        handle.write("t4,veh-4,T1,10,100,local,true,10.05,50,\n")
    expected = inspect_bundle_cache(stale_bundle, stale_cache)
    assert expected.state is CanonicalCacheState.MISS
    assert expected.cache_entry is not None
    shutil.copytree(Path(old.cache.cache_entry or ""), Path(expected.cache_entry))

    stale = inspect_bundle_cache(stale_bundle, stale_cache)

    incompatible_bundle = _copy_baseline(tmp_path / "incompatible")
    incompatible_cache = tmp_path / "incompatible-cache"
    written = validate_bundle_cached(incompatible_bundle, incompatible_cache)
    entry_json = Path(written.cache.cache_entry or "") / "entry.json"
    document = json.loads(entry_json.read_text(encoding="utf-8"))
    document["key"]["adapter_version"] = "unsupported-adapter"
    entry_json.write_text(json.dumps(document), encoding="utf-8")

    incompatible = inspect_bundle_cache(incompatible_bundle, incompatible_cache)

    assert stale.state is CanonicalCacheState.STALE
    assert incompatible.state is CanonicalCacheState.INCOMPATIBLE


def test_symlink_payload_and_cache_inside_raw_bundle_are_rejected(tmp_path: Path) -> None:
    bundle = _copy_baseline(tmp_path)
    with pytest.raises(CanonicalCacheConfigurationError, match="outside the raw"):
        validate_bundle_cached(bundle, bundle / ".cache")

    cache_root = tmp_path / "cache"
    written = validate_bundle_cached(bundle, cache_root)
    entry = Path(written.cache.cache_entry or "")
    target = entry / "tasks.parquet"
    replacement = tmp_path / "replacement.parquet"
    replacement.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(replacement)

    assert inspect_bundle_cache(bundle, cache_root).state is CanonicalCacheState.CORRUPT


def test_failed_write_publishes_no_partial_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"

    def fail_write(*args: object, **kwargs: object) -> None:
        raise OSError("injected Parquet write failure")

    monkeypatch.setattr(pq, "write_table", fail_write)
    result = validate_bundle_cached(bundle, cache_root)

    assert result.validation.report.may_import
    assert result.cache.state is CanonicalCacheState.WRITE_FAILED
    assert cache_root.exists()
    assert list(cache_root.iterdir()) == []


def test_concurrent_valid_publication_is_reused_without_a_temporary_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"
    original_rename = Path.rename

    def publish_concurrently(source: Path, target: Path) -> Path:
        shutil.copytree(source, target)
        raise OSError("simulated concurrent directory publication")

    monkeypatch.setattr(Path, "rename", publish_concurrently)
    result = validate_bundle_cached(bundle, cache_root)
    monkeypatch.setattr(Path, "rename", original_rename)

    assert result.validation.report.may_import
    assert result.cache.state is CanonicalCacheState.HIT
    assert [path.name for path in cache_root.iterdir()] == [result.cache.cache_key]


def test_zip_bundle_uses_the_same_cold_then_warm_cache_semantics(tmp_path: Path) -> None:
    bundle = _copy_baseline(tmp_path / "source")
    archive = Path(shutil.make_archive(str(tmp_path / "bundle"), "zip", bundle))
    cache_root = tmp_path / "cache"

    cold = validate_bundle_cached(archive, cache_root)
    warm = validate_bundle_cached(archive, cache_root)

    assert cold.cache.state is CanonicalCacheState.WRITTEN
    assert warm.cache.state is CanonicalCacheState.HIT
    assert warm.validation == cold.validation


def test_manifest_raw_bytes_remain_part_of_identity_even_for_non_mapping_metadata(
    tmp_path: Path,
) -> None:
    bundle = _copy_baseline(tmp_path)
    cache_root = tmp_path / "cache"
    first = validate_bundle_cached(bundle, cache_root)
    manifest_path = bundle / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"]["notes"] = "changed provenance without mapping change"
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    second_status = inspect_bundle_cache(bundle, cache_root)

    assert second_status.state is CanonicalCacheState.MISS
    assert second_status.cache_key != first.cache.cache_key

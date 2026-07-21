"""Benchmark cold canonicalisation/cache publication against verified warm reuse."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import shutil
import statistics
import sys
import tempfile
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import yaml

from traffictwin.ingestion.bundle import (
    CachedBundleValidationResult,
    inspect_bundle_cache,
    validate_bundle_cached,
)


def main() -> None:
    """Generate one bounded fixture and emit measured OPS-02 acceptance evidence."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=20_000)
    parser.add_argument("--warm-repeat", type=int, default=5)
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    if args.warm_repeat < 1:
        parser.error("--warm-repeat must be at least 1")

    with tempfile.TemporaryDirectory(prefix="traffictwin-cache-benchmark-") as temporary:
        root = Path(temporary)
        bundle = _write_generated_bundle(root / "bundle", args.rows)
        cache_root = root / "cache"
        initial_source_bytes = _source_size(bundle)
        raw_before = _file_hashes(bundle)

        cold, cold_seconds, cold_peak = _measure(lambda: validate_bundle_cached(bundle, cache_root))
        raw_after = _file_hashes(bundle)
        warm_samples: list[float] = []
        warm_peaks: list[int] = []
        warm_results: list[CachedBundleValidationResult] = []
        for _ in range(args.warm_repeat):
            warm, elapsed, peak = _measure(lambda: validate_bundle_cached(bundle, cache_root))
            warm_results.append(warm)
            warm_samples.append(elapsed)
            warm_peaks.append(peak)

        with (bundle / "tasks.csv").open("a", encoding="utf-8") as handle:
            handle.write(
                f"cache-invalidated-{args.rows:08d},veh-cache,T1,{args.rows / 10:.1f},"
                f"250,local,true,{args.rows / 10 + 0.1:.1f},100,\n"
            )
        invalidated_status = inspect_bundle_cache(bundle, cache_root)
        invalidated, invalidated_seconds, invalidated_peak = _measure(
            lambda: validate_bundle_cached(bundle, cache_root)
        )

        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "benchmark": "canonical_table_cache",
            "capability_id": "OPS-02",
            "scope": (
                "generated synthetic local implementation benchmark; not a simulator, "
                "city-scale, deployment, or performance guarantee"
            ),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "generated_task_rows": args.rows,
            "initial_source_bytes": initial_source_bytes,
            "warm_repeat_count": args.warm_repeat,
            "cold": {
                "cache_state": cold.cache.state.value,
                "runtime_seconds": cold_seconds,
                "peak_traced_memory_bytes": cold_peak,
            },
            "warm": {
                "cache_states": [item.cache.state.value for item in warm_results],
                "runtime_seconds_samples": warm_samples,
                "runtime_seconds_median": statistics.median(warm_samples),
                "peak_traced_memory_bytes_samples": warm_peaks,
                "peak_traced_memory_bytes_max": max(warm_peaks),
            },
            "equivalence": {
                "all_validation_results_exact": all(
                    item.validation == cold.validation for item in warm_results
                ),
                "raw_files_unchanged_by_cache": raw_before == raw_after,
                "canonical_record_counts": cold.validation.canonical.record_counts(),
            },
            "invalidation": {
                "status_before_rebuild": invalidated_status.state.value,
                "rebuild_cache_state": invalidated.cache.state.value,
                "runtime_seconds": invalidated_seconds,
                "peak_traced_memory_bytes": invalidated_peak,
                "new_key": invalidated.cache.cache_key != cold.cache.cache_key,
            },
            "cache_payload_bytes_after_two_keys": _source_size(cache_root),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


def _measure(
    function: Callable[[], CachedBundleValidationResult],
) -> tuple[CachedBundleValidationResult, float, int]:
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    result = function()
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_generated_bundle(destination: Path, row_count: int) -> Path:
    shutil.copytree(Path("tests/fixtures/bundles/baseline_valid"), destination)
    tasks = destination / "tasks.csv"
    with tasks.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "task_id",
                "vehicle_id",
                "task_class",
                "arrival_time",
                "deadline_ms",
                "decision",
                "completed",
                "completion_time",
                "latency_ms",
                "target_id",
            ]
        )
        for index in range(row_count):
            arrival = index / 10.0
            writer.writerow(
                [
                    f"cache-task-{index:08d}",
                    f"veh-{index % 2_000:05d}",
                    f"T{index % 3 + 1}",
                    f"{arrival:.1f}",
                    250,
                    ("local", "v2i", "v2v")[index % 3],
                    "true",
                    f"{arrival + 0.1:.1f}",
                    100,
                    "rsu-1" if index % 3 == 1 else "",
                ]
            )
    manifest_path = destination / "manifest.yaml"
    raw = cast(dict[str, Any], yaml.safe_load(manifest_path.read_text(encoding="utf-8")))
    cast(dict[str, Any], raw["bundle"])["bundle_id"] = "bundle-cache-benchmark"
    cast(dict[str, Any], raw["run"])["run_id"] = "run-cache-benchmark"
    cast(dict[str, Any], raw["provenance"])["notes"] = (
        "Generated synthetic canonical-cache benchmark fixture"
    )
    manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return destination


def _source_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


if __name__ == "__main__":
    main()

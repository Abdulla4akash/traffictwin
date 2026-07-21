"""Benchmark ordinary and streaming canonicalisation on a generated synthetic bundle."""

from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import platform
import shutil
import sys
import tempfile
import tracemalloc
from collections.abc import Callable
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Any, cast

import yaml

from traffictwin.canonical.tables import CanonicalTables
from traffictwin.ingestion.bundle import validate_bundle, validate_bundle_streaming
from traffictwin.ingestion.streaming import CanonicalChunk, StreamingCanonicalisationConfig

TABLE_NAMES = ("tasks", "infrastructure", "vehicles", "traffic", "trips", "incidents")


def main() -> None:
    """Generate one fixture, benchmark paths, and print reproducible JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=75_000)
    parser.add_argument("--chunk-rows", default="257,1024,4096")
    args = parser.parse_args()
    if args.rows < 1:
        parser.error("--rows must be at least 1")
    chunk_sizes = [int(value.strip()) for value in args.chunk_rows.split(",") if value.strip()]
    if not chunk_sizes or any(value < 1 for value in chunk_sizes):
        parser.error("--chunk-rows must contain positive comma-separated integers")

    with tempfile.TemporaryDirectory(prefix="traffictwin-stream-benchmark-") as temporary:
        bundle = _write_generated_bundle(Path(temporary) / "bundle", args.rows)
        fixture_bytes = _source_size(bundle)
        ordinary, ordinary_seconds, ordinary_peak = _measure(lambda: validate_bundle(bundle))
        ordinary_digests = _canonical_digests(ordinary.canonical)
        ordinary_report = ordinary.report.model_dump(mode="json", exclude={"import_timestamp"})
        ordinary_counts = ordinary.canonical.record_counts()
        del ordinary
        gc.collect()

        streaming_results: list[dict[str, object]] = []
        for chunk_rows in chunk_sizes:
            digests = _new_digests()
            consume = _digest_consumer(digests)
            config = StreamingCanonicalisationConfig(chunk_rows=chunk_rows)
            streamed, elapsed, peak = _measure(
                partial(validate_bundle_streaming, bundle, config=config, consumer=consume)
            )
            report_equivalent = (
                streamed.report.model_dump(mode="json", exclude={"import_timestamp"})
                == ordinary_report
            )
            counts_equivalent = streamed.streaming.canonical_record_counts == ordinary_counts
            digests_equivalent = _finish_digests(digests) == ordinary_digests
            streaming_results.append(
                {
                    "chunk_rows": chunk_rows,
                    "runtime_seconds": elapsed,
                    "peak_traced_memory_bytes": peak,
                    "chunk_count": streamed.streaming.chunk_count,
                    "max_observed_chunk_source_rows": (
                        streamed.streaming.max_observed_chunk_source_rows
                    ),
                    "max_observed_chunk_decoded_bytes": (
                        streamed.streaming.max_observed_chunk_decoded_bytes
                    ),
                    "canonical_digest_equivalent": digests_equivalent,
                    "canonical_counts_equivalent": counts_equivalent,
                    "validation_report_equivalent": report_equivalent,
                    "equivalent": digests_equivalent and counts_equivalent and report_equivalent,
                }
            )
            del streamed
            gc.collect()

        payload = {
            "schema_version": "1.0",
            "benchmark": "streaming_canonicalisation",
            "scope": "generated synthetic implementation benchmark; not a city-scale claim",
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "generated_task_rows": args.rows,
            "total_source_bytes": fixture_bytes,
            "ordinary": {
                "runtime_seconds": ordinary_seconds,
                "peak_traced_memory_bytes": ordinary_peak,
                "canonical_record_counts": ordinary_counts,
            },
            "streaming": streaming_results,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))


def _measure(function: Callable[[], Any]) -> tuple[Any, float, int]:
    gc.collect()
    tracemalloc.start()
    started = perf_counter()
    result = function()
    elapsed = perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return result, elapsed, peak


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
                    f"large-task-{index:08d}",
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
    cast(dict[str, Any], raw["bundle"])["bundle_id"] = "bundle-streaming-benchmark"
    cast(dict[str, Any], raw["run"])["run_id"] = "run-streaming-benchmark"
    cast(dict[str, Any], raw["provenance"])["notes"] = (
        "Generated synthetic streaming benchmark fixture"
    )
    manifest_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return destination


def _new_digests() -> dict[str, hashlib._Hash]:
    return {name: hashlib.sha256() for name in TABLE_NAMES}


def _digest_consumer(digests: dict[str, hashlib._Hash]) -> Callable[[CanonicalChunk], None]:
    def consume(chunk: CanonicalChunk) -> None:
        _update_digests(digests, chunk.canonical)

    return consume


def _canonical_digests(tables: CanonicalTables) -> dict[str, str]:
    digests = _new_digests()
    _update_digests(digests, tables)
    return _finish_digests(digests)


def _update_digests(digests: dict[str, hashlib._Hash], tables: CanonicalTables) -> None:
    for table_name in TABLE_NAMES:
        records = getattr(tables, table_name)
        for record in records:
            payload = json.dumps(
                record.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            digests[table_name].update(len(payload).to_bytes(8, "big"))
            digests[table_name].update(payload)


def _finish_digests(digests: dict[str, hashlib._Hash]) -> dict[str, str]:
    return {name: digest.hexdigest() for name, digest in digests.items()}


def _source_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


if __name__ == "__main__":
    main()

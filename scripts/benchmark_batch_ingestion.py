"""Measure deterministic batch validation over explicit local bundle inputs."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter

from traffictwin.ingestion.batch import BatchBundleSummary, validate_bundle_batch
from traffictwin.ingestion.bundle import validate_bundle


def main() -> None:
    """Run the local implementation benchmark and emit one JSON document."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="Explicit bundle paths or quoted glob patterns")
    parser.add_argument("--repeat", type=int, default=3, help="Measured repetitions (default: 3)")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")

    runtime_samples: list[float] = []
    peak_samples: list[int] = []
    summary: BatchBundleSummary | None = None
    for _ in range(args.repeat):
        tracemalloc.start()
        started = perf_counter()
        summary = validate_bundle_batch(args.inputs)
        runtime_samples.append(perf_counter() - started)
        _, peak = tracemalloc.get_traced_memory()
        peak_samples.append(peak)
        tracemalloc.stop()

    assert summary is not None
    sources = [Path(result.source) for result in summary.results]
    direct_projection = [_direct_projection(path) for path in sources]
    batch_projection = [
        {
            "source": result.source,
            "bundle_id": result.bundle_id,
            "run_id": result.run_id,
            "fingerprint": result.fingerprint,
            "status": result.validation_status.value,
            "may_import": result.may_import,
            "finding_count": result.finding_count,
        }
        for result in summary.results
    ]
    payload = {
        "schema_version": "1.0",
        "benchmark": "batch_bundle_validation",
        "scope": "local implementation benchmark; not a simulator or city-scale claim",
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "input_references": args.inputs,
        "fixture_count": len(sources),
        "total_source_bytes": sum(_source_size(path) for path in sources),
        "repeat_count": args.repeat,
        "runtime_seconds_samples": runtime_samples,
        "runtime_seconds_median": statistics.median(runtime_samples),
        "peak_memory_bytes_samples": peak_samples,
        "peak_memory_bytes_max": max(peak_samples),
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "input_issue_count": len(summary.input_issues),
        "sequential_equivalent": batch_projection == direct_projection,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def _direct_projection(path: Path) -> dict[str, object]:
    result = validate_bundle(path)
    return {
        "source": path.as_posix(),
        "bundle_id": result.report.bundle_id,
        "run_id": result.report.run_id,
        "fingerprint": result.fingerprint,
        "status": result.report.status.value,
        "may_import": result.report.may_import,
        "finding_count": len(result.report.findings),
    }


def _source_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if path.is_dir():
        return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())
    return 0


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Verify VEC-05 over all audited tripinfo/occupancy scenario joins."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal, cast, overload

import numpy as np

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot
from traffictwin.integration.vec_trip_join import build_trip_join_dataset

TRIPINFO_SCENARIOS = {
    "tripinfo/tripinfo_2024-03-15_incident_reactive.xml.gz": ("inc",),
    "tripinfo/tripinfo_2024-09-15_weekend.xml.gz": ("we",),
    "tripinfo/tripinfo_2024-09-18_ucl_event.xml.gz": ("ev",),
    "tripinfo/tripinfo_2024-10-15_workingday.xml.gz": ("wd_am", "wd_pm"),
}
_git_executable = shutil.which("git")
if _git_executable is None:
    raise RuntimeError("git executable not found")
GIT_EXECUTABLE: str = _git_executable


@overload
def _git(repo: Path, *args: str, text: Literal[True] = True) -> str: ...


@overload
def _git(repo: Path, *args: str, text: Literal[False]) -> bytes: ...


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(  # noqa: S603 - fixed read-only Git argv, never a shell
        [GIT_EXECUTABLE, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return cast(str | bytes, result.stdout)


def _blob(repo: Path, path: str) -> bytes:
    return _git(repo, "show", f"{TOS_DATA_AUDITED_COMMIT}:{path}", text=False)


def _trace(payload: bytes) -> dict[str, Any]:
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def verify(tos_data_repo: Path) -> dict[str, Any]:
    repo = tos_data_repo.resolve(strict=True)
    before = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if (
        before
        or _git(repo, "rev-parse", "refs/remotes/origin/main").strip() != TOS_DATA_AUDITED_COMMIT
    ):
        raise RuntimeError("tos-data must be clean with origin/main at the audited commit")
    reports: list[dict[str, Any]] = []
    source_files: dict[str, dict[str, Any]] = {}
    for trip_path, scenarios in TRIPINFO_SCENARIOS.items():
        trip_blob = _blob(repo, trip_path)
        source_files[trip_path] = {
            "path": trip_path,
            "sha256": hashlib.sha256(trip_blob).hexdigest(),
            "size_bytes": len(trip_blob),
        }
        for scenario in scenarios:
            trace_path = f"traces/trace_{scenario}_fullrsu.npz"
            occupancy_path = f"occupancy/occupancy_{scenario}.csv"
            trace_blob = _blob(repo, trace_path)
            occupancy_blob = _blob(repo, occupancy_path)
            trace = _trace(trace_blob)
            reader = csv.reader(io.StringIO(occupancy_blob.decode("utf-8-sig")))
            identity = build_vehicle_identity_snapshot(
                trace, next(reader), list(reader), scenario=scenario
            )
            dataset = build_trip_join_dataset(trace, identity, trip_blob, source_path=trip_path)
            reports.append(dataset.report.model_dump(mode="json"))
            for path, payload in ((trace_path, trace_blob), (occupancy_path, occupancy_blob)):
                source_files[path] = {
                    "path": path,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
    after = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if after != before:
        raise RuntimeError("tos-data changed during read-only trip verification")
    return {
        "schema_version": "1.0",
        "capability": "VEC-05",
        "status": "accepted",
        "source_commit": TOS_DATA_AUDITED_COMMIT,
        "tripinfo_file_count": len(TRIPINFO_SCENARIOS),
        "scenario_join_count": len(reports),
        "total_occupancy_vehicles": sum(item["occupancy_vehicle_count"] for item in reports),
        "total_matched_vehicles": sum(item["matched_vehicle_count"] for item in reports),
        "total_right_censored": sum(item["right_censored_count"] for item in reports),
        "total_missing_before_boundary": sum(
            item["missing_before_boundary_count"] for item in reports
        ),
        "reports": reports,
        "sources": [source_files[path] for path in sorted(source_files)],
        "external_source_unchanged": True,
        "raw_vehicle_ids_published": False,
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tos-data-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = verify(args.tos_data_repo)
    _write(args.output, record)
    print(
        f"VEC-05 accepted: {record['total_matched_vehicles']} matched vehicles across "
        f"{record['scenario_join_count']} scenario joins"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify VEC-03 identity coverage against exact audited tos-data Git blobs."""

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
from typing import Any, cast

import numpy as np

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot

SCENARIOS = ("ev", "inc", "wd_am", "wd_pm", "we")
_git_executable = shutil.which("git")
if _git_executable is None:
    raise RuntimeError("git executable not found")
GIT_EXECUTABLE: str = _git_executable


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(  # noqa: S603 - fixed read-only Git argv, never a shell
        [GIT_EXECUTABLE, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return cast(str | bytes, result.stdout)


def _blob(repo: Path, path: str) -> bytes:
    return cast(bytes, _git(repo, "show", f"{TOS_DATA_AUDITED_COMMIT}:{path}", text=False))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify(tos_data_repo: Path) -> dict[str, Any]:
    """Return a permission-safe exact-blob verification record for all scenarios."""

    repo = tos_data_repo.resolve(strict=True)
    before = str(_git(repo, "status", "--porcelain=v1", "--untracked-files=all"))
    origin_main = str(_git(repo, "rev-parse", "refs/remotes/origin/main")).strip()
    if before or origin_main != TOS_DATA_AUDITED_COMMIT:
        raise RuntimeError("tos-data must be clean with origin/main at the audited commit")

    reports: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        trace_path = f"traces/trace_{scenario}_fullrsu.npz"
        occupancy_path = f"occupancy/occupancy_{scenario}.csv"
        trace_blob = _blob(repo, trace_path)
        occupancy_blob = _blob(repo, occupancy_path)
        with np.load(io.BytesIO(trace_blob), allow_pickle=False) as archive:
            trace = {key: archive[key] for key in archive.files}
        reader = csv.reader(io.StringIO(occupancy_blob.decode("utf-8-sig")))
        header = next(reader)
        rows = list(reader)
        snapshot = build_vehicle_identity_snapshot(
            trace,
            header,
            rows,
            scenario=scenario,
        )
        reports.append(snapshot.report.model_dump(mode="json"))
        for role, path, payload in (
            ("trace", trace_path, trace_blob),
            ("occupancy", occupancy_path, occupancy_blob),
        ):
            sources.append(
                {
                    "scenario": scenario,
                    "role": role,
                    "path": path,
                    "sha256": _sha256(payload),
                    "size_bytes": len(payload),
                }
            )

    after = str(_git(repo, "status", "--porcelain=v1", "--untracked-files=all"))
    if after != before:
        raise RuntimeError("tos-data changed during read-only identity verification")
    return {
        "schema_version": "1.0",
        "capability": "VEC-03",
        "status": "accepted",
        "source_commit": TOS_DATA_AUDITED_COMMIT,
        "blob_access": "git show <audited-commit>:<repo-relative-path>",
        "interval_semantics": "inclusive",
        "scenario_count": len(reports),
        "total_active_trace_cells": sum(item["active_trace_cells"] for item in reports),
        "total_identity_cells": sum(item["identity_cells"] for item in reports),
        "total_spans": sum(item["span_count"] for item in reports),
        "total_distinct_vehicle_visits_by_scenario": sum(
            item["distinct_vehicle_count"] for item in reports
        ),
        "reports": reports,
        "sources": sources,
        "external_source_unchanged": True,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
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
    _atomic_write(args.output, record)
    print(
        f"VEC-03 accepted: {record['total_identity_cells']} cells across "
        f"{record['scenario_count']} scenarios"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

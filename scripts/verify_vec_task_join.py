#!/usr/bin/env python3
"""Verify VEC-04 against every audited run with matched per-step/per-task evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Literal, cast, overload

import numpy as np

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot
from traffictwin.integration.vec_task_join import build_task_join_report

PERTASK_PATHS = (
    "instrumented/pertask/baseline_uk2030_inc_fs0_pertask.npz",
    "instrumented/pertask/baseline_uk2030_wd_am_fs0_pertask.npz",
    "instrumented/pertask/fcd_s102_uk2030_we_fs0_pertask.npz",
    "instrumented/pertask/glk_mappo_uk2030_inc_fs0_pertask.npz",
    "instrumented/pertask/ukft_mappo_uk2030_inc_fs0_pertask.npz",
    "instrumented/pertask/ukft_mappo_uk2030_wd_am_fs0_pertask.npz",
)
SCENARIO_PATTERN = re.compile(r"_(wd_am|wd_pm|ev|inc|we)_fs\d+_pertask\.npz$")
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


def _npz(payload: bytes) -> dict[str, Any]:
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _scenario(path: str) -> str:
    match = SCENARIO_PATTERN.search(path)
    if match is None:
        raise RuntimeError(f"could not derive scenario from {path}")
    return match.group(1)


def _perstep_path(pertask_path: str) -> str:
    return pertask_path.replace("instrumented/pertask/", "instrumented/perstep/").replace(
        "_pertask.npz", "_perstep.npz"
    )


def verify(tos_data_repo: Path) -> dict[str, Any]:
    repo = tos_data_repo.resolve(strict=True)
    before = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    origin_main = _git(repo, "rev-parse", "refs/remotes/origin/main").strip()
    if before or origin_main != TOS_DATA_AUDITED_COMMIT:
        raise RuntimeError("tos-data must be clean with origin/main at the audited commit")

    identities: dict[str, tuple[dict[str, Any], Any]] = {}
    reports: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    for pertask_path in PERTASK_PATHS:
        scenario = _scenario(pertask_path)
        if scenario not in identities:
            trace_path = f"traces/trace_{scenario}_fullrsu.npz"
            occupancy_path = f"occupancy/occupancy_{scenario}.csv"
            trace_blob = _blob(repo, trace_path)
            occupancy_blob = _blob(repo, occupancy_path)
            trace = _npz(trace_blob)
            reader = csv.reader(io.StringIO(occupancy_blob.decode("utf-8-sig")))
            header = next(reader)
            identity = build_vehicle_identity_snapshot(
                trace, header, list(reader), scenario=scenario
            )
            identities[scenario] = (trace, identity)
            for path, payload in ((trace_path, trace_blob), (occupancy_path, occupancy_blob)):
                sources[path] = {
                    "path": path,
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                }
        trace, identity = identities[scenario]
        perstep_path = _perstep_path(pertask_path)
        perstep_blob = _blob(repo, perstep_path)
        pertask_blob = _blob(repo, pertask_path)
        run_label = Path(pertask_path).name.removesuffix("_pertask.npz")
        report = build_task_join_report(
            trace,
            _npz(perstep_blob),
            _npz(pertask_blob),
            identity,
            run_label=run_label,
        )
        reports.append(report.model_dump(mode="json"))
        for path, payload in ((perstep_path, perstep_blob), (pertask_path, pertask_blob)):
            sources[path] = {
                "path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }

    after = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if after != before:
        raise RuntimeError("tos-data changed during read-only task-join verification")
    return {
        "schema_version": "1.0",
        "capability": "VEC-04",
        "status": "accepted",
        "source_commit": TOS_DATA_AUDITED_COMMIT,
        "matched_run_count": len(reports),
        "scenario_count": len(identities),
        "total_tasks": sum(report["total_tasks"] for report in reports),
        "total_deadline_met_tasks": sum(report["deadline_met_tasks"] for report in reports),
        "total_no_eligible_target_tasks": sum(
            report["target_availability_counts"]["no_eligible_target"] for report in reports
        ),
        "reports": reports,
        "sources": [sources[path] for path in sorted(sources)],
        "external_source_unchanged": True,
        "limitations": [
            "no eligible target is not classified as failure",
            "actions do not confirm transfer",
            "eventual completion, link quality, and per-task energy remain unavailable",
        ],
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
        f"VEC-04 accepted: {record['total_tasks']} tasks across "
        f"{record['matched_run_count']} matched runs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

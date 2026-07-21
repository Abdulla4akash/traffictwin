#!/usr/bin/env python3
"""Verify VEC-09 scientific admission over one audited source-evidence run."""

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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast, overload

import numpy as np

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot
from traffictwin.integration.vec_reproduction import VecReproductionReport
from traffictwin.integration.vec_science import build_vec_scientific_admission
from traffictwin.integration.vec_task_join import build_task_join_report
from traffictwin.integration.vec_trip_join import build_trip_join_dataset

RUN_LABEL = "fcd_s102_uk2030_we_fs0"
SCENARIO = "we"
TRACE_PATH = "traces/trace_we_fullrsu.npz"
OCCUPANCY_PATH = "occupancy/occupancy_we.csv"
PERSTEP_PATH = f"instrumented/perstep/{RUN_LABEL}_perstep.npz"
PERTASK_PATH = f"instrumented/pertask/{RUN_LABEL}_pertask.npz"
TRIPINFO_PATH = "tripinfo/tripinfo_2024-09-15_weekend.xml.gz"
COMPUTED_AT = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)

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


def verify(tos_data_repo: Path, reproduction_report_path: Path) -> dict[str, Any]:
    """Build a permission-safe VEC-09 admission record from pinned Git blobs."""

    repo = tos_data_repo.resolve(strict=True)
    before = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if (
        before
        or _git(repo, "rev-parse", "refs/remotes/origin/main").strip() != TOS_DATA_AUDITED_COMMIT
    ):
        raise RuntimeError("tos-data must be clean with origin/main at the audited commit")

    reproduction = VecReproductionReport.model_validate_json(
        reproduction_report_path.read_text(encoding="utf-8")
    )
    if reproduction.grade.value != "numerically_equivalent":
        raise RuntimeError("VEC-09 requires the accepted numerically-equivalent VEC-08 report")

    paths = (TRACE_PATH, OCCUPANCY_PATH, PERSTEP_PATH, PERTASK_PATH, TRIPINFO_PATH)
    blobs = {path: _blob(repo, path) for path in paths}
    trace = _npz(blobs[TRACE_PATH])
    reader = csv.reader(io.StringIO(blobs[OCCUPANCY_PATH].decode("utf-8-sig")))
    identity = build_vehicle_identity_snapshot(
        trace,
        next(reader),
        list(reader),
        scenario=SCENARIO,
    )
    perstep = _npz(blobs[PERSTEP_PATH])
    pertask = _npz(blobs[PERTASK_PATH])
    task_report = build_task_join_report(
        trace,
        perstep,
        pertask,
        identity,
        run_label=RUN_LABEL,
    )
    trip_report = build_trip_join_dataset(
        trace,
        identity,
        blobs[TRIPINFO_PATH],
        source_path=TRIPINFO_PATH,
    ).report
    admission = build_vec_scientific_admission(
        trace,
        perstep,
        pertask,
        identity,
        task_report,
        reproduction_report_fingerprint=reproduction.fingerprint(),
        reproduction_grade=reproduction.grade.value,
        computed_at=COMPUTED_AT,
        trip_report=trip_report,
    )

    after = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if after != before:
        raise RuntimeError("tos-data changed during read-only scientific admission")
    return {
        "schema_version": "1.0",
        "capability": "VEC-09",
        "status": "accepted",
        "source_commit": TOS_DATA_AUDITED_COMMIT,
        "selected_run_label": RUN_LABEL,
        "selection_label_preserved": "_s102_best_of_seeds",
        "reproduction_scope": (
            "VEC-08 establishes the pinned engine path separately; VEC-09 computes metrics "
            "from the selected audited VEC-04/VEC-05 evidence run."
        ),
        "admission": admission.model_dump(mode="json"),
        "sources": [
            {
                "path": path,
                "sha256": hashlib.sha256(blobs[path]).hexdigest(),
                "size_bytes": len(blobs[path]),
            }
            for path in sorted(paths)
        ],
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
    parser.add_argument("--reproduction-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    record = verify(args.tos_data_repo, args.reproduction_report)
    _write(args.output, record)
    metrics = record["admission"]["evidence_pack"]["metric_collection"]["results"]
    available = sum(item["status"] == "available" for item in metrics)
    unavailable = len(metrics) - available
    print(f"VEC-09 accepted: {available} metrics available, {unavailable} unavailable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

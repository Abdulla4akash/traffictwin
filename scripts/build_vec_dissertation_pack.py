#!/usr/bin/env python3
"""Build the real permission-bounded VEC-11 dissertation pack from pinned Git blobs."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Literal, cast, overload

import numpy as np

from traffictwin.integration.tos.contract_v2 import (
    TOS_DATA_AUDITED_COMMIT,
    VEC_ENV_AUDITED_COMMIT,
)
from traffictwin.integration.vec_identity import build_vehicle_identity_snapshot
from traffictwin.integration.vec_publication import (
    derive_sanitised_matched_sample,
    render_vec_dissertation_pack,
    write_vec_dissertation_pack,
)
from traffictwin.integration.vec_science import VecScientificAdmissionReport
from traffictwin.integration.vec_task_join import build_task_join_report
from traffictwin.integration.vec_trip_join import build_trip_join_dataset

RUN_LABEL = "fcd_s102_uk2030_we_fs0"
SCENARIO = "we"
TRACE_PATH = "traces/trace_we_fullrsu.npz"
OCCUPANCY_PATH = "occupancy/occupancy_we.csv"
PERSTEP_PATH = f"instrumented/perstep/{RUN_LABEL}_perstep.npz"
PERTASK_PATH = f"instrumented/pertask/{RUN_LABEL}_pertask.npz"
TRIPINFO_PATH = "tripinfo/tripinfo_2024-09-15_weekend.xml.gz"

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


def _validate_external_repo(repo: Path, commit: str) -> str:
    before = _git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if before or _git(repo, "rev-parse", "refs/remotes/origin/main").strip() != commit:
        raise RuntimeError(f"{repo.name} must be clean with origin/main at its audited commit")
    return before


def _blob(repo: Path, path: str) -> bytes:
    return _git(repo, "show", f"{TOS_DATA_AUDITED_COMMIT}:{path}", text=False)


def _npz(payload: bytes) -> dict[str, Any]:
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def build(
    tos_data_repo: Path,
    vec_env_repo: Path,
    scientific_report_path: Path,
    output: Path,
) -> None:
    """Build the real pack without checking out or modifying either external repository."""

    tos_repo = tos_data_repo.resolve(strict=True)
    vec_repo = vec_env_repo.resolve(strict=True)
    tos_before = _validate_external_repo(tos_repo, TOS_DATA_AUDITED_COMMIT)
    vec_before = _validate_external_repo(vec_repo, VEC_ENV_AUDITED_COMMIT)

    trace = _npz(_blob(tos_repo, TRACE_PATH))
    occupancy = _blob(tos_repo, OCCUPANCY_PATH).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(occupancy))
    identity = build_vehicle_identity_snapshot(trace, next(reader), list(reader), scenario=SCENARIO)
    perstep = _npz(_blob(tos_repo, PERSTEP_PATH))
    pertask = _npz(_blob(tos_repo, PERTASK_PATH))
    task_report = build_task_join_report(trace, perstep, pertask, identity, run_label=RUN_LABEL)
    trip_dataset = build_trip_join_dataset(
        trace,
        identity,
        _blob(tos_repo, TRIPINFO_PATH),
        source_path=TRIPINFO_PATH,
    )
    report_record = json.loads(scientific_report_path.read_text(encoding="utf-8"))
    if (
        report_record.get("status") != "accepted"
        or report_record.get("source_commit") != TOS_DATA_AUDITED_COMMIT
        or report_record.get("selected_run_label") != RUN_LABEL
        or report_record.get("selection_label_preserved") != "_s102_best_of_seeds"
        or report_record.get("raw_vehicle_ids_published") is not False
    ):
        raise RuntimeError("the VEC-09 machine record is not the accepted disclosed source")
    admission = VecScientificAdmissionReport.model_validate(report_record["admission"])
    rows = derive_sanitised_matched_sample(
        trace,
        perstep,
        pertask,
        identity,
        task_report,
        trip_dataset,
        admission,
    )
    _, payloads = render_vec_dissertation_pack(
        rows,
        admission,
        task_report,
        trip_dataset,
        sensitive_vehicle_ids=[span.sumo_vehicle_id for span in identity.spans],
    )
    write_vec_dissertation_pack(output, payloads)

    if _git(tos_repo, "status", "--porcelain=v1", "--untracked-files=all") != tos_before:
        raise RuntimeError("tos-data changed during read-only VEC-11 publication")
    if _git(vec_repo, "status", "--porcelain=v1", "--untracked-files=all") != vec_before:
        raise RuntimeError("vec_env changed during read-only VEC-11 publication")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tos-data-repo", type=Path, required=True)
    parser.add_argument("--vec-env-repo", type=Path, required=True)
    parser.add_argument("--scientific-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.tos_data_repo, args.vec_env_repo, args.scientific_report, args.output)
    print("VEC-11 accepted: 3 sanitised matched rows and permission-manifested aggregates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

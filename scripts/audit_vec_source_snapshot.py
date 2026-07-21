#!/usr/bin/env python3
"""Build the deterministic VEC-01 audit from pinned external Git objects.

The external repositories are read-only inputs.  This script reads blobs directly
from the audited commits, so it neither checks out nor modifies either worktree.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal, cast, overload

import numpy as np

VEC_COMMIT = "068b4ea33e640f206ce6a7d04f3d6fae2ac831f4"
TOS_COMMIT = "f6c67acbed3360dba3a0d5c8d1fd557caa99ecff"

VEC_EVIDENCE = {
    "docs/REPRODUCING.md",
    "eval/build_trace.py",
    "eval/eval_sumo_stage1_mc.py",
    "eval/place_rsus_cover.py",
    "eval/reconstruct_occupancy.py",
    "jaxmarl/env/vec_jax.py",
    "validation/fidelity_trace_replay.py",
}

TOS_ROOT_EVIDENCE = {
    "DATA_DICTIONARY.md",
    "README.md",
    "evals/eval_results_master.csv",
}

TOS_EVIDENCE_PREFIXES = (
    "checkpoints/",
    "instrumented/json/",
    "instrumented/perstep/",
    "instrumented/pertask/",
    "occupancy/",
    "traces/",
    "tripinfo/",
)

SCENARIOS = ("wd_am", "wd_pm", "ev", "inc", "we")
PERSTEP_SCENARIO_RE = re.compile(r"_(wd_am|wd_pm|ev|inc|we)_fs0_perstep\.npz$")

TRACE_BY_SCENARIO = {scenario: f"traces/trace_{scenario}_fullrsu.npz" for scenario in SCENARIOS}
OCCUPANCY_BY_SCENARIO = {scenario: f"occupancy/occupancy_{scenario}.csv" for scenario in SCENARIOS}
TRIPINFO_SCENARIOS = {
    "tripinfo/tripinfo_2024-03-15_incident_reactive.xml.gz": ("inc",),
    "tripinfo/tripinfo_2024-09-15_weekend.xml.gz": ("we",),
    "tripinfo/tripinfo_2024-09-18_ucl_event.xml.gz": ("ev",),
    "tripinfo/tripinfo_2024-10-15_workingday.xml.gz": ("wd_am", "wd_pm"),
}

PERSTEP_KEYS = {
    "times",
    "slot_tier",
    "slot_is_ev",
    "arrivals",
    "done",
    "lat_sum",
    "active",
    "n_local",
    "n_v2i",
    "n_v2v",
    "veh_action",
    "veh_k",
    "veh_done",
    "veh_queue_ms",
    "veh_best_rsu",
    "veh_best_v2v",
    "rsu_busy_ms",
    "rsu_load",
}

PERTASK_KEYS = {"task_type", "task_lat_ms", "task_met", "task_active"}

_git_executable = shutil.which("git")
if _git_executable is None:
    raise RuntimeError("git executable not found")
GIT_EXECUTABLE: str = _git_executable


@overload
def _git(repo: Path, *args: str, text: Literal[True] = True) -> str: ...


@overload
def _git(repo: Path, *args: str, text: Literal[False]) -> bytes: ...


def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(  # noqa: S603 - fixed executable and argument vector, never a shell
        [GIT_EXECUTABLE, "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=text,
    )
    return cast(str | bytes, result.stdout)


def _blob(repo: Path, commit: str, path: str) -> bytes:
    return _git(repo, "show", f"{commit}:{path}", text=False)


def _paths(repo: Path, commit: str) -> list[str]:
    output = _git(repo, "ls-tree", "-r", "--name-only", commit)
    return [line for line in str(output).splitlines() if line]


def _source_state(repo: Path, commit: str) -> dict[str, Any]:
    commit_lines = str(
        _git(
            repo,
            "show",
            "-s",
            "--format=%H%n%P%n%an%n%aI%n%cI%n%s",
            commit,
        )
    ).splitlines()
    status = str(_git(repo, "status", "--porcelain=v1", "--untracked-files=all"))
    branch = str(_git(repo, "branch", "--show-current")).strip()
    head = str(_git(repo, "rev-parse", "HEAD")).strip()
    remote_main = str(_git(repo, "rev-parse", "refs/remotes/origin/main")).strip()
    remote_url = str(_git(repo, "remote", "get-url", "origin")).strip()
    return {
        "audited_commit": commit_lines[0],
        "audited_commit_parents": commit_lines[1].split(),
        "author_name": commit_lines[2],
        "authored_at": commit_lines[3],
        "committed_at": commit_lines[4],
        "subject": commit_lines[5],
        "remote_url": remote_url,
        "origin_main": remote_main,
        "origin_main_matches_audited_commit": remote_main == commit,
        "worktree_branch": branch,
        "worktree_head": head,
        "worktree_clean": not status,
        "worktree_at_audited_commit": head == commit,
    }


def _schema(npz: np.lib.npyio.NpzFile) -> dict[str, dict[str, object]]:
    return {
        key: {"dtype": str(npz[key].dtype), "shape": list(npz[key].shape)}
        for key in sorted(npz.files)
    }


def _scalar(value: object) -> str | int | float | bool:
    scalar: object = value.item() if isinstance(value, (np.ndarray, np.generic)) else value
    if not isinstance(scalar, (str, int, float, bool)):
        raise TypeError("expected a scalar string, integer, float, or boolean")
    return scalar


def _float_close(left: float, right: float, *, rel_tol: float = 2e-6) -> bool:
    return math.isclose(left, right, rel_tol=rel_tol, abs_tol=1e-6)


def _scenario_from_perstep(path: str) -> str:
    match = PERSTEP_SCENARIO_RE.search(path)
    if match is None:
        raise ValueError(f"cannot identify scenario from {path}")
    return match.group(1)


def _json_path_from_perstep(path: str) -> str:
    return path.replace("instrumented/perstep/", "instrumented/json/").replace(
        "_perstep.npz", ".json"
    )


def _trace_and_occupancy(
    tos_repo: Path,
    tos_commit: str,
) -> tuple[dict[str, Any], dict[str, set[str]], dict[str, set[str]]]:
    summaries: dict[str, Any] = {}
    vehicle_ids: dict[str, set[str]] = {}
    boundary_vehicle_ids: dict[str, set[str]] = {}
    for scenario in SCENARIOS:
        trace_path = TRACE_BY_SCENARIO[scenario]
        occupancy_path = OCCUPANCY_BY_SCENARIO[scenario]
        trace_bytes = _blob(tos_repo, tos_commit, trace_path)
        with np.load(io.BytesIO(trace_bytes), allow_pickle=False) as trace:
            trace_schema = _schema(trace)
            mask = np.asarray(trace["mask"], dtype=bool)
            times = np.asarray(trace["times"])
            t_count = int(_scalar(trace["T"]))
            max_n = int(_scalar(trace["maxN"]))
            rsu_count = int(trace["rsu_xy"].shape[0])
            reconstructed = np.zeros_like(mask)
            trace_summary = {
                "path": trace_path,
                "schema": trace_schema,
                "T": t_count,
                "maxN": max_n,
                "dt_seconds": float(_scalar(trace["dt"])),
                "first_time": float(times[0]),
                "last_time": float(times[-1]),
                "times_are_one_second_contiguous": bool(
                    times.size <= 1 or np.all(np.diff(times) == 1.0)
                ),
                "mask_true_count": int(mask.sum()),
                "rsu_count": rsu_count,
                "window": str(_scalar(trace["window"])),
                "sumo_seed": (
                    int(_scalar(trace["sumo_seed"])) if "sumo_seed" in trace.files else None
                ),
            }

            occupancy_text = _blob(tos_repo, tos_commit, occupancy_path).decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(occupancy_text))
            rows = list(reader)
            expected_header = ["sumo_vehicle_id", "slot", "t_enter", "t_exit"]
            invalid_spans = 0
            slot_out_of_range = 0
            time_out_of_range = 0
            spans_by_slot: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
            spans_by_vehicle: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
            visit_seconds = 0
            ids: set[str] = set()
            for row in rows:
                vehicle_id = row["sumo_vehicle_id"]
                slot = int(row["slot"])
                enter = int(row["t_enter"])
                exit_ = int(row["t_exit"])
                ids.add(vehicle_id)
                if exit_ < enter:
                    invalid_spans += 1
                    continue
                if not 0 <= slot < max_n:
                    slot_out_of_range += 1
                    continue
                if not (0 <= enter <= exit_ < t_count):
                    time_out_of_range += 1
                    continue
                visit_seconds += exit_ - enter + 1
                spans_by_slot[slot].append((enter, exit_, vehicle_id))
                spans_by_vehicle[vehicle_id].append((enter, exit_, slot))
                reconstructed[enter : exit_ + 1, slot] = True

            slot_overlaps = 0
            for slot_spans in spans_by_slot.values():
                slot_spans.sort()
                slot_overlaps += sum(
                    current[0] <= previous[1]
                    for previous, current in zip(slot_spans, slot_spans[1:], strict=False)
                )
            vehicle_overlaps = 0
            for vehicle_spans in spans_by_vehicle.values():
                vehicle_spans.sort()
                vehicle_overlaps += sum(
                    current[0] <= previous[1]
                    for previous, current in zip(vehicle_spans, vehicle_spans[1:], strict=False)
                )

            occupancy_summary = {
                "path": occupancy_path,
                "header": reader.fieldnames,
                "header_matches_contract": reader.fieldnames == expected_header,
                "row_count": len(rows),
                "unique_vehicle_id_count": len(ids),
                "unique_slot_count": len(spans_by_slot),
                "inclusive_visit_seconds": visit_seconds,
                "invalid_span_count": invalid_spans,
                "slot_out_of_range_count": slot_out_of_range,
                "time_out_of_range_count": time_out_of_range,
                "slot_overlap_count": slot_overlaps,
                "same_vehicle_overlap_count": vehicle_overlaps,
                "exact_mask_match": bool(np.array_equal(reconstructed, mask)),
                "visit_seconds_match_mask": visit_seconds == int(mask.sum()),
            }
            vehicle_ids[scenario] = ids
            boundary_vehicle_ids[scenario] = {
                vehicle_id
                for vehicle_id, spans in spans_by_vehicle.items()
                if any(exit_ == t_count - 1 for _, exit_, _ in spans)
            }
            occupancy_summary["vehicle_ids_ending_at_trace_boundary"] = len(
                boundary_vehicle_ids[scenario]
            )
            summaries[scenario] = {"trace": trace_summary, "occupancy": occupancy_summary}
    return summaries, vehicle_ids, boundary_vehicle_ids


def _perstep(
    tos_repo: Path,
    tos_commit: str,
    paths: Iterable[str],
    trace_summaries: dict[str, Any],
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    violations: Counter[str] = Counter()
    action_target_counts: Counter[str] = Counter()
    signal_file_counts: Counter[str] = Counter()
    for path in sorted(paths):
        scenario = _scenario_from_perstep(path)
        trace = trace_summaries[scenario]["trace"]
        run = json.loads(_blob(tos_repo, tos_commit, _json_path_from_perstep(path)))
        with np.load(io.BytesIO(_blob(tos_repo, tos_commit, path)), allow_pickle=False) as data:
            keys = set(data.files)
            t_count = trace["T"]
            max_n = trace["maxN"]
            rsu_count = trace["rsu_count"]
            shape_ok = (
                data["times"].shape == (t_count,)
                and data["slot_tier"].shape == (max_n,)
                and data["slot_is_ev"].shape == (max_n,)
                and all(
                    data[key].shape == (t_count,)
                    for key in (
                        "arrivals",
                        "done",
                        "lat_sum",
                        "active",
                        "n_local",
                        "n_v2i",
                        "n_v2v",
                    )
                )
                and all(
                    data[key].shape == (t_count, max_n)
                    for key in (
                        "veh_action",
                        "veh_k",
                        "veh_done",
                        "veh_queue_ms",
                        "veh_best_rsu",
                        "veh_best_v2v",
                    )
                )
                and all(
                    data[key].shape == (t_count, rsu_count) for key in ("rsu_busy_ms", "rsu_load")
                )
            )
            target_range_ok = bool(
                np.all((data["veh_best_rsu"] >= -1) & (data["veh_best_rsu"] < rsu_count))
                and np.all((data["veh_best_v2v"] >= -1) & (data["veh_best_v2v"] < max_n))
            )
            tier_range_ok = bool(np.all((data["slot_tier"] >= 0) & (data["slot_tier"] <= 2)))
            times_match = bool(
                data["times"].size == t_count
                and float(data["times"][0]) == trace["first_time"]
                and float(data["times"][-1]) == trace["last_time"]
                and np.all(np.diff(data["times"]) == 1.0)
            )
            arrivals = int(np.sum(data["arrivals"], dtype=np.int64))
            done = int(np.sum(data["done"], dtype=np.int64))
            latency_sum = float(np.sum(data["lat_sum"], dtype=np.float64))
            local = int(np.sum(data["n_local"], dtype=np.int64))
            v2i = int(np.sum(data["n_v2i"], dtype=np.int64))
            v2v = int(np.sum(data["n_v2v"], dtype=np.int64))
            vehicle_arrivals = int(np.sum(data["veh_k"], dtype=np.int64))
            vehicle_done = int(np.sum(data["veh_done"], dtype=np.int64))
            weighted_local = int(np.sum(data["veh_k"] * (data["veh_action"] == 0), dtype=np.int64))
            weighted_v2i = int(np.sum(data["veh_k"] * (data["veh_action"] == 1), dtype=np.int64))
            weighted_v2v = int(np.sum(data["veh_k"] * (data["veh_action"] == 2), dtype=np.int64))
            computed_latency = latency_sum / arrivals
            computed_ev_share = float(np.mean(data["slot_is_ev"]))
            aggregate_deltas = {
                "completion": done / arrivals - float(run["completion"]),
                "avg_latency_ms_per_task": computed_latency - float(run["avg_latency_ms_per_task"]),
                "p_local": local / arrivals - float(run["p_local"]),
                "p_v2i": v2i / arrivals - float(run["p_v2i"]),
                "p_v2v": v2v / arrivals - float(run["p_v2v"]),
                "fleet_ev_share": computed_ev_share - float(run["fleet_ev_share"]),
            }
            summary_matches_json = bool(
                arrivals == int(run["total_tasks"])
                and _float_close(done / arrivals, float(run["completion"]))
                and math.isclose(
                    computed_latency,
                    float(run["avg_latency_ms_per_task"]),
                    rel_tol=1e-5,
                    abs_tol=1e-3,
                )
                and _float_close(local / arrivals, float(run["p_local"]))
                and _float_close(v2i / arrivals, float(run["p_v2i"]))
                and _float_close(v2v / arrivals, float(run["p_v2v"]))
                and list(np.bincount(data["slot_tier"], minlength=3)) == run["fleet_tier_hist"]
                and _float_close(computed_ev_share, float(run["fleet_ev_share"]))
            )

            v2i_selected = (data["veh_action"] == 1) & (data["veh_k"] > 0)
            v2v_selected = (data["veh_action"] == 2) & (data["veh_k"] > 0)
            target_counts = {
                "v2i_decision_rows_with_tasks": int(v2i_selected.sum()),
                "v2i_decision_rows_without_eligible_target": int(
                    (v2i_selected & (data["veh_best_rsu"] < 0)).sum()
                ),
                "v2v_decision_rows_with_tasks": int(v2v_selected.sum()),
                "v2v_decision_rows_without_eligible_target": int(
                    (v2v_selected & (data["veh_best_v2v"] < 0)).sum()
                ),
            }
            action_target_counts.update(target_counts)
            signal_counts = {
                "files_with_positive_vehicle_queue": int(np.any(data["veh_queue_ms"] > 0)),
                "files_with_positive_rsu_busy": int(np.any(data["rsu_busy_ms"] > 0)),
                "files_with_positive_rsu_load": int(np.any(data["rsu_load"] > 0)),
            }
            signal_file_counts.update(signal_counts)
            target_columns = np.arange(max_n, dtype=np.int64)[None, :]
            checks = {
                "exact_keys": keys == PERSTEP_KEYS,
                "shapes_match_trace": shape_ok,
                "times_match_trace": times_match,
                "active_count_matches_trace_mask": int(np.sum(data["active"], dtype=np.int64))
                == trace["mask_true_count"],
                "internal_task_counts_reconcile": (
                    vehicle_arrivals == arrivals
                    and vehicle_done == done
                    and local + v2i + v2v == arrivals
                    and (weighted_local, weighted_v2i, weighted_v2v) == (local, v2i, v2v)
                ),
                "value_ranges_valid": bool(
                    np.all((data["veh_action"] >= 0) & (data["veh_action"] <= 2))
                    and np.all((data["veh_k"] >= 0) & (data["veh_k"] <= 5))
                    and np.all((data["veh_done"] >= 0) & (data["veh_done"] <= data["veh_k"]))
                    and np.all(np.isfinite(data["veh_queue_ms"]))
                    and np.all(data["veh_queue_ms"] >= 0)
                    and np.all(np.isfinite(data["rsu_busy_ms"]))
                    and np.all(data["rsu_busy_ms"] >= 0)
                    and np.all(data["rsu_load"] >= 0)
                ),
                "tier_range_valid": tier_range_ok,
                "target_ranges_valid": target_range_ok,
                "eligible_v2v_targets_are_not_self": bool(
                    np.all((data["veh_best_v2v"] < 0) | (data["veh_best_v2v"] != target_columns))
                ),
                "aggregates_match_run_json": summary_matches_json,
            }
            violations.update(key for key, passed in checks.items() if not passed)
            files.append(
                {
                    "path": path,
                    "scenario": scenario,
                    "json_path": _json_path_from_perstep(path),
                    "checks": checks,
                    "aggregate_deltas": aggregate_deltas,
                    "action_target_counts": target_counts,
                    "signal_counts": signal_counts,
                }
            )
    return {
        "file_count": len(files),
        "expected_key_schema": sorted(PERSTEP_KEYS),
        "failed_check_counts": dict(sorted(violations.items())),
        "action_target_counts": dict(sorted(action_target_counts.items())),
        "signal_file_counts": dict(sorted(signal_file_counts.items())),
        "files": files,
    }


def _pertask(tos_repo: Path, tos_commit: str, paths: Iterable[str]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(paths):
        with np.load(io.BytesIO(_blob(tos_repo, tos_commit, path)), allow_pickle=False) as data:
            shapes = {tuple(data[key].shape) for key in data.files}
            files.append(
                {
                    "path": path,
                    "schema": _schema(data),
                    "exact_keys": set(data.files) == PERTASK_KEYS,
                    "all_arrays_share_shape": len(shapes) == 1,
                    "contains_per_task_energy": any("energy" in key.lower() for key in data.files),
                    "contains_eventual_physical_completion": any(
                        key in {"task_physically_completed", "task_eventual_completion"}
                        for key in data.files
                    ),
                }
            )
    return {
        "file_count": len(files),
        "expected_key_schema": sorted(PERTASK_KEYS),
        "files": files,
    }


def _checkpoints(tos_repo: Path, tos_commit: str, paths: Iterable[str]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    expected_shapes = {
        "Dense_0.bias": [64],
        "Dense_0.kernel": [17, 64],
        "Dense_1.bias": [64],
        "Dense_1.kernel": [64, 64],
        "Dense_2.bias": [3],
        "Dense_2.kernel": [64, 3],
    }
    for path in sorted(paths):
        blob = _blob(tos_repo, tos_commit, path)
        with np.load(io.BytesIO(blob), allow_pickle=False) as data:
            schema = _schema(data)
            files.append(
                {
                    "path": path,
                    "bytes": len(blob),
                    "schema": schema,
                    "exact_parameter_names": set(data.files) == set(expected_shapes),
                    "shapes_match_17x64x64x3_actor": all(
                        key in schema and schema[key]["shape"] == shape
                        for key, shape in expected_shapes.items()
                    ),
                    "all_parameters_float32": all(
                        schema[key]["dtype"] == "float32" for key in schema
                    ),
                }
            )
    return {"file_count": len(files), "files": files}


def _tripinfo(
    tos_repo: Path,
    tos_commit: str,
    vehicle_ids: dict[str, set[str]],
    boundary_vehicle_ids: dict[str, set[str]],
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path, scenarios in TRIPINFO_SCENARIOS.items():
        raw = gzip.decompress(_blob(tos_repo, tos_commit, path))
        seen: set[str] = set()
        duplicate_ids = 0
        invalid_times = 0
        min_depart: float | None = None
        max_arrival: float | None = None
        trip_count = 0
        # The XML is a SHA-pinned producer artifact, not an arbitrary upload.
        for _, element in ET.iterparse(  # noqa: S314
            io.BytesIO(raw), events=("end",)
        ):
            if element.tag.rsplit("}", 1)[-1] != "tripinfo":
                continue
            trip_count += 1
            vehicle_id = element.attrib.get("id", "")
            if vehicle_id in seen:
                duplicate_ids += 1
            seen.add(vehicle_id)
            try:
                depart = float(element.attrib["depart"])
                arrival = float(element.attrib["arrival"])
                if not (math.isfinite(depart) and math.isfinite(arrival) and arrival >= depart):
                    invalid_times += 1
                min_depart = depart if min_depart is None else min(min_depart, depart)
                max_arrival = arrival if max_arrival is None else max(max_arrival, arrival)
            except (KeyError, TypeError, ValueError):
                invalid_times += 1
            element.clear()
        joins: dict[str, Any] = {}
        for scenario in scenarios:
            occupancy_ids = vehicle_ids[scenario]
            missing = occupancy_ids - seen
            missing_at_boundary = missing & boundary_vehicle_ids[scenario]
            joins[scenario] = {
                "occupancy_vehicle_count": len(occupancy_ids),
                "matched_vehicle_count": len(occupancy_ids & seen),
                "missing_vehicle_count": len(missing),
                "missing_vehicle_ending_at_trace_boundary_count": len(missing_at_boundary),
                "missing_vehicle_before_trace_boundary_count": len(missing - missing_at_boundary),
                "complete_occupancy_join": not missing,
            }
        files.append(
            {
                "path": path,
                "uncompressed_bytes": len(raw),
                "trip_count": trip_count,
                "unique_vehicle_id_count": len(seen),
                "duplicate_vehicle_id_count": duplicate_ids,
                "invalid_time_count": invalid_times,
                "minimum_depart_seconds": min_depart,
                "maximum_arrival_seconds": max_arrival,
                "occupancy_joins": joins,
            }
        )
    return {"file_count": len(files), "files": files}


def _master_csv(tos_repo: Path, tos_commit: str) -> dict[str, Any]:
    path = "evals/eval_results_master.csv"
    reader = csv.DictReader(io.StringIO(_blob(tos_repo, tos_commit, path).decode("utf-8-sig")))
    rows = list(reader)
    return {
        "path": path,
        "columns": reader.fieldnames,
        "row_count": len(rows),
        "engine_values": sorted({row.get("engine_version", "") for row in rows}),
        "cell_values": sorted({row.get("cell", "") for row in rows}),
    }


def _licence_files(paths: Iterable[str]) -> list[str]:
    names = {"license", "licence", "copying", "notice", "citation.cff"}
    return sorted(
        path
        for path in paths
        if Path(path).name.lower() in names
        or Path(path).name.lower().startswith(("license.", "licence."))
    )


def build_audit(
    vec_repo: Path,
    tos_repo: Path,
    permission_images: Iterable[tuple[str, Path]] = (),
) -> dict[str, Any]:
    vec_paths = _paths(vec_repo, VEC_COMMIT)
    tos_paths = _paths(tos_repo, TOS_COMMIT)
    missing_vec = sorted(VEC_EVIDENCE - set(vec_paths))
    tos_evidence = sorted(
        path
        for path in tos_paths
        if path in TOS_ROOT_EVIDENCE or path.startswith(TOS_EVIDENCE_PREFIXES)
    )
    missing_tos = sorted(TOS_ROOT_EVIDENCE - set(tos_paths))
    if missing_vec or missing_tos:
        raise RuntimeError(f"required evidence missing: vec={missing_vec}, tos={missing_tos}")

    evidence: list[dict[str, Any]] = []
    for repository, repo, commit, paths in (
        ("vec_env", vec_repo, VEC_COMMIT, sorted(VEC_EVIDENCE)),
        ("tos-data", tos_repo, TOS_COMMIT, tos_evidence),
    ):
        for evidence_path in paths:
            blob = _blob(repo, commit, evidence_path)
            evidence.append(
                {
                    "repository": repository,
                    "path": evidence_path,
                    "bytes": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest(),
                }
            )

    for label, path in permission_images:
        blob = path.read_bytes()
        evidence.append(
            {
                "repository": "user-supplied-randy-email",
                "path": label,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
    evidence.sort(key=lambda item: (item["repository"], item["path"]))

    trace_summaries, vehicle_ids, boundary_vehicle_ids = _trace_and_occupancy(tos_repo, TOS_COMMIT)
    perstep_paths = [path for path in tos_evidence if path.startswith("instrumented/perstep/")]
    pertask_paths = [path for path in tos_evidence if path.startswith("instrumented/pertask/")]
    checkpoint_paths = [path for path in tos_evidence if path.startswith("checkpoints/")]
    perstep = _perstep(tos_repo, TOS_COMMIT, perstep_paths, trace_summaries)
    pertask = _pertask(tos_repo, TOS_COMMIT, pertask_paths)
    checkpoints = _checkpoints(tos_repo, TOS_COMMIT, checkpoint_paths)
    tripinfo = _tripinfo(
        tos_repo,
        TOS_COMMIT,
        vehicle_ids,
        boundary_vehicle_ids,
    )

    all_occupancy_exact = all(
        item["occupancy"]["exact_mask_match"]
        and item["occupancy"]["slot_overlap_count"] == 0
        and item["occupancy"]["same_vehicle_overlap_count"] == 0
        for item in trace_summaries.values()
    )
    all_pertask_lacks_energy = all(
        not item["contains_per_task_energy"] for item in pertask["files"]
    )
    all_pertask_lacks_physical_completion = all(
        not item["contains_eventual_physical_completion"] for item in pertask["files"]
    )

    return {
        "schema_version": "traffictwin.vec-source-snapshot-audit.v1",
        "capability_id": "VEC-01",
        "audit_outcome": "accepted_with_scoped_blockers",
        "audit_method": {
            "external_repositories_modified": False,
            "blob_access": "git show <commit>:<path>",
            "npz_loading": "numpy.load(..., allow_pickle=False)",
            "occupancy_interval_interpretation": (
                "inclusive t_enter/t_exit as documented by producer"
            ),
        },
        "sources": {
            "vec_env": _source_state(vec_repo, VEC_COMMIT),
            "tos-data": _source_state(tos_repo, TOS_COMMIT),
        },
        "evidence_inventory": {
            "file_count": len(evidence),
            "total_bytes": sum(item["bytes"] for item in evidence),
            "files": evidence,
        },
        "observations": {
            "trace_and_occupancy": trace_summaries,
            "perstep": perstep,
            "pertask": pertask,
            "checkpoints": checkpoints,
            "tripinfo": tripinfo,
            "evaluation_master": _master_csv(tos_repo, TOS_COMMIT),
            "licence_files": {
                "vec_env": _licence_files(vec_paths),
                "tos-data": _licence_files(tos_paths),
            },
        },
        "claims_reconciliation": [
            {
                "claim": (
                    "The named trace/evaluator writers are present at the reviewed vec_env commit."
                ),
                "status": "confirmed",
                "evidence": sorted(VEC_EVIDENCE),
            },
            {
                "claim": "Two frozen actor checkpoints are present and structurally loadable.",
                "status": "confirmed_with_size_mismatch",
                "observed_bytes": [item["bytes"] for item in checkpoints["files"]],
                "reported_approximate_bytes_each": 74000,
            },
            {
                "claim": (
                    "Occupancy tables exactly identify SUMO vehicle visits for all five traces."
                ),
                "status": "confirmed" if all_occupancy_exact else "rejected",
            },
            {
                "claim": (
                    "The supplied scenario-day tripinfo files support exact-ID occupancy joins."
                ),
                "status": "confirmed_with_incomplete_coverage",
                "limit": (
                    "Some occupancy vehicles have no tripinfo record; most unmatched vehicles "
                    "persist to the trace boundary, while the incident trace also has unmatched "
                    "earlier exits."
                ),
            },
            {
                "claim": (
                    "veh_best_rsu/veh_best_v2v identify an eligible decision-time target, "
                    "with -1 for none."
                ),
                "status": "confirmed_with_semantic_limit",
                "limit": (
                    "The selected action can be V2I/V2V while its target is -1; action counts "
                    "are decisions/attempts, not proof that a transfer occurred."
                ),
            },
            {
                "claim": (
                    "Per-task evidence supports exact per-task energy and eventual physical "
                    "completion."
                ),
                "status": "not_supported",
                "per_task_energy_absent": all_pertask_lacks_energy,
                "eventual_physical_completion_absent": all_pertask_lacks_physical_completion,
            },
            {
                "claim": (
                    "Any one-second SUMO FCD plus its network can pass through the same builder."
                ),
                "status": "partially_confirmed",
                "limits": [
                    (
                        "The builder emits dt=1.0 rather than deriving and rejecting "
                        "non-one-second input."
                    ),
                    "The default RSU placement is tied to hard-coded Drakewell sensor coordinates.",
                ],
            },
            {
                "claim": "Sanitized samples and aggregates may be reused for the dissertation.",
                "status": "confirmed_as_scoped_written_permission",
                "limit": (
                    "No repository licence or CITATION file was observed; permission does not "
                    "admit raw/private artifacts for redistribution."
                ),
            },
        ],
        "dependent_blockers": [
            {
                "id": "per_task_energy_absent",
                "blocks": ["VEC-09"],
                "detail": "The six per-task NPZ files contain no per-task energy field.",
            },
            {
                "id": "eventual_physical_completion_absent",
                "blocks": ["VEC-02", "VEC-09"],
                "detail": (
                    "task_met/done and JSON completion represent deadline success, not an "
                    "eventual physical-completion event."
                ),
            },
            {
                "id": "action_is_not_transfer_proof",
                "blocks": ["VEC-04", "VEC-09"],
                "detail": (
                    "V2I/V2V action selections can have no eligible target; transfer claims "
                    "require eligibility-aware treatment."
                ),
            },
            {
                "id": "fcd_resolution_not_enforced",
                "blocks": ["VEC-06"],
                "detail": (
                    "build_trace.py writes dt=1.0 and TrafficTwin must independently reject "
                    "non-one-second input."
                ),
            },
            {
                "id": "rsu_placement_is_manchester_specific",
                "blocks": ["VEC-06"],
                "detail": (
                    "The reviewed builder contains fixed Drakewell sensor locations; arbitrary "
                    "networks need explicit placement inputs or a validated separate step."
                ),
            },
            {
                "id": "evaluator_repo_path_hard_coded",
                "blocks": ["VEC-07", "VEC-08"],
                "detail": (
                    "The evaluator prepends a fixed ~/scratch source path; a safe runner must "
                    "control and verify import resolution."
                ),
            },
            {
                "id": "no_repository_licence",
                "blocks": ["VEC-12"],
                "detail": (
                    "No licence/CITATION file was found; publication must remain within Randy's "
                    "written sanitized-sample/aggregate permission."
                ),
            },
        ],
        "rights_boundary": {
            "authority": "Randy Putra written response supplied by the dissertation owner",
            "permitted": [
                "sanitized samples",
                "aggregates",
                "dissertation use with both repositories cited",
            ],
            "required_labels": [
                "engine v2_post_nrsus_fix",
                "_s102 best-of-seeds when those rows are used",
            ],
            "not_inferred": [
                "open-source licence",
                "raw data redistribution",
                "checkpoint redistribution",
                "blanket publication permission",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vec-repo", type=Path, required=True)
    parser.add_argument("--tos-repo", type=Path, required=True)
    parser.add_argument(
        "--permission-image",
        action="append",
        default=[],
        metavar="LABEL=PATH",
        help="Hash a private permission screenshot without copying it into the repository.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    permission_images: list[tuple[str, Path]] = []
    for value in args.permission_image:
        if "=" not in value:
            parser.error("--permission-image must use LABEL=PATH")
        label, raw_path = value.split("=", 1)
        permission_images.append((label, Path(raw_path).resolve()))
    audit = build_audit(
        args.vec_repo.resolve(),
        args.tos_repo.resolve(),
        permission_images,
    )
    rendered = json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

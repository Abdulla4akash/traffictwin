#!/usr/bin/env python3
"""Fail-closed validation for the one-arm E2b factorial missing cell."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from validate_e2_native_placement_pilot import (
    add_check,
    compare_array_sets,
    load_npz,
    validate_run as validate_e2_run,
)


def load_selected(path: Path, keys: tuple[str, ...]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in keys}


def validate_run(run_dir: Path, *, arm: dict, manifest: dict, expected_steps: int) -> dict:
    result = validate_e2_run(
        run_dir, arm=arm, manifest=manifest, expected_steps=expected_steps
    )
    if "summary" not in result or not (run_dir / "per_task.npz").is_file():
        return result

    task = load_selected(
        run_dir / "per_task.npz",
        (
            "task_ingress_rsu",
            "task_selected_execution_rsu",
            "task_execution_rsu",
            "task_forwarded",
            "task_forwarding_latency_ms",
            "task_v2i_admitted",
            "task_outcome",
        ),
    )
    ingress = task["task_ingress_rsu"]
    selected = task["task_selected_execution_rsu"]
    execution = task["task_execution_rsu"]
    forwarded = task["task_forwarded"].astype(bool)
    forwarding_ms = task["task_forwarding_latency_ms"]
    admitted = task["task_v2i_admitted"].astype(bool)
    outcome = task["task_outcome"]
    attempt = ingress >= 0
    gate_rejected = outcome == 3

    checks = result["checks"]
    add_check(
        checks,
        "ingress_dla_selected_equals_ingress",
        np.array_equal(selected[attempt], ingress[attempt]),
        bool(np.array_equal(selected[attempt], ingress[attempt])),
        True,
    )
    add_check(
        checks,
        "ingress_dla_admitted_executes_at_ingress",
        np.array_equal(execution[admitted], ingress[admitted]),
        bool(np.array_equal(execution[admitted], ingress[admitted])),
        True,
    )
    add_check(checks, "ingress_dla_no_forwarding", not np.any(forwarded),
              int(forwarded.sum()), 0)
    add_check(checks, "ingress_dla_zero_forwarding_latency",
              np.all(forwarding_ms == 0.0),
              float(forwarding_ms.sum(dtype=np.float64)), 0.0)
    add_check(checks, "ingress_dla_gate_reject_selected_is_ingress",
              np.array_equal(selected[gate_rejected], ingress[gate_rejected]),
              bool(np.array_equal(selected[gate_rejected], ingress[gate_rejected])), True)
    add_check(checks, "ingress_dla_gate_reject_execution_sentinel",
              np.all(execution[gate_rejected] == -1),
              np.unique(execution[gate_rejected]).tolist(), [-1])
    add_check(checks, "ingress_dla_gate_reject_not_admitted",
              not np.any(admitted[gate_rejected]),
              int(admitted[gate_rejected].sum()), 0)
    add_check(checks, "ingress_dla_gate_reject_not_forwarded",
              not np.any(forwarded[gate_rejected]),
              int(forwarded[gate_rejected].sum()), 0)
    path = result["summary"]["v2i_path_metrics"]
    add_check(checks, "ingress_dla_path_aggregate_forwarding_zero",
              path["forwarded_admitted_task_count"] == 0
              and path["forwarded_share_of_admitted_v2i"] == 0.0
              and path["total_forwarding_latency_ms"] == 0.0,
              {
                  "count": path["forwarded_admitted_task_count"],
                  "share": path["forwarded_share_of_admitted_v2i"],
                  "latency_ms": path["total_forwarding_latency_ms"],
              },
              {"count": 0, "share": 0.0, "latency_ms": 0.0},
    )
    matrix = np.asarray(path["ingress_to_execution_pair_matrix"], dtype=np.int64)
    add_check(checks, "ingress_dla_path_matrix_diagonal",
              int(matrix.sum() - np.trace(matrix)) == 0,
              int(matrix.sum() - np.trace(matrix)), 0)
    gate_by_ingress = np.bincount(
        ingress[gate_rejected], minlength=manifest["design"]["rsus"]
    ).astype(np.int64)
    add_check(checks, "ingress_dla_gate_rejection_reconciles",
              int(gate_by_ingress.sum())
              == int(result["summary"]["v2i_gate_rejected"]),
              int(gate_by_ingress.sum()), int(result["summary"]["v2i_gate_rejected"]))
    result["gate_rejection_count_by_ingress_rsu"] = gate_by_ingress.tolist()
    result["status"] = "passed" if all(check["pass"] for check in checks) else "failed"
    return result


def compare_to_completed_e2_reference(
    manifest: dict, phase: str, candidate: dict
) -> dict:
    reference_dir = Path(
        manifest["completed_e2_reuse"]["reference_runs"][phase]["off"]
    )
    reference_summary = json.loads((reference_dir / "summary.json").read_text())
    candidate_dir = Path(candidate["run_dir"])
    reference_step = load_selected(
        reference_dir / "per_step.npz",
        ("veh_action", "veh_actor_logits", "slot_tier", "slot_is_ev"),
    )
    candidate_step = load_selected(
        candidate_dir / "per_step.npz",
        ("veh_action", "veh_actor_logits", "slot_tier", "slot_is_ev"),
    )
    reference_task = load_selected(
        reference_dir / "per_task.npz", ("task_active", "task_type")
    )
    candidate_task = load_selected(
        candidate_dir / "per_task.npz", ("task_active", "task_type")
    )
    reference_logits = reference_step["veh_actor_logits"]
    candidate_logits = candidate_step["veh_actor_logits"]
    same_logit_schema = (
        reference_logits.shape == candidate_logits.shape
        and reference_logits.dtype == candidate_logits.dtype == np.float32
    )
    if same_logit_schema:
        max_abs = float(np.max(np.abs(
            reference_logits.astype(np.float64) - candidate_logits.astype(np.float64)
        ), initial=0.0))
    else:
        max_abs = float("inf")
    tolerance = float(
        manifest["cross_arm_actor_stream_contract"]["logit_diagnostic"][
            "absolute_tolerance"
        ]
    )
    fields = {
        "offered_tasks": reference_summary["n_offered"]
        == candidate["summary"]["n_offered"],
        "task_active": reference_task["task_active"].tobytes()
        == candidate_task["task_active"].tobytes(),
        "task_type": reference_task["task_type"].tobytes()
        == candidate_task["task_type"].tobytes(),
        "fleet_tier": reference_step["slot_tier"].tobytes()
        == candidate_step["slot_tier"].tobytes(),
        "fleet_is_ev": reference_step["slot_is_ev"].tobytes()
        == candidate_step["slot_is_ev"].tobytes(),
        "vehicle_action": reference_step["veh_action"].tobytes()
        == candidate_step["veh_action"].tobytes(),
    }
    logit_pass = same_logit_schema and np.isfinite(max_abs) and max_abs <= tolerance
    return {
        "reference": str(reference_dir.resolve()),
        "candidate": candidate["run_dir"],
        "pass": all(fields.values()) and logit_pass,
        "fields": fields,
        "actor_logit_diagnostic": {
            "pass": logit_pass,
            "shape_dtype_equal": same_logit_schema,
            "byte_exact": same_logit_schema
            and reference_logits.tobytes() == candidate_logits.tobytes(),
            "maximum_absolute_difference": max_abs,
            "absolute_tolerance": tolerance,
            "reference_sha256": hashlib.sha256(reference_logits.tobytes()).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate_logits.tobytes()).hexdigest(),
            "interpretation": manifest["cross_arm_actor_stream_contract"][
                "logit_diagnostic"
            ]["interpretation"],
        },
    }


def validate_phase(manifest: dict, phase: str) -> dict:
    raw_root = Path(manifest["outputs"]["raw_root"])
    arm = manifest["arms"][0]
    expected_steps = (
        manifest["smoke_gate"]["steps"]
        if phase == "smoke"
        else manifest["design"]["steps"]
    )
    repeats = (
        manifest["smoke_gate"]["serial_repeats_per_arm"]
        if phase == "smoke"
        else 1
    )
    runs = [
        validate_run(
            raw_root / phase / arm["id"] / f"run_{repeat}",
            arm=arm,
            manifest=manifest,
            expected_steps=expected_steps,
        )
        for repeat in range(1, repeats + 1)
    ]
    if any(run["status"] != "passed" for run in runs):
        return {
            "schema_version": "e2b_placement_admission_validation_v1",
            "phase": phase,
            "status": "failed",
            "runs": runs,
            "repeat_checks": [],
            "completed_e2_reference_check": None,
        }

    repeat_checks = []
    if phase == "smoke":
        left, right = runs
        left_summary, right_summary = dict(left["summary"]), dict(right["summary"])
        left_summary.pop("wall_s", None)
        right_summary.pop("wall_s", None)
        step_cmp = compare_array_sets(
            load_npz(Path(left["run_dir"]) / "per_step.npz"),
            load_npz(Path(right["run_dir"]) / "per_step.npz"),
        )
        task_cmp = compare_array_sets(
            load_npz(Path(left["run_dir"]) / "per_task.npz"),
            load_npz(Path(right["run_dir"]) / "per_task.npz"),
        )
        repeat_checks.append({
            "arm": arm["id"],
            "pass": left_summary == right_summary
            and step_cmp["pass"] and task_cmp["pass"],
            "scientific_summary_exact_excluding_wall_s": left_summary == right_summary,
            "per_step": step_cmp,
            "per_task": task_cmp,
        })

    reference_check = compare_to_completed_e2_reference(manifest, phase, runs[0])
    passed = (
        all(run["status"] == "passed" for run in runs)
        and all(check["pass"] for check in repeat_checks)
        and reference_check["pass"]
    )
    return {
        "schema_version": "e2b_placement_admission_validation_v1",
        "phase": phase,
        "status": "passed" if passed else "failed",
        "statistical_status": "one-seed descriptive mechanism-decomposition pilot",
        "runs": runs,
        "repeat_checks": repeat_checks,
        "completed_e2_reference_check": reference_check,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    if args.output_json.exists():
        raise SystemExit(f"refusing to overwrite {args.output_json}")
    validation = validate_phase(json.loads(args.manifest.read_text()), args.phase)
    args.output_json.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": validation["status"], "output": str(args.output_json)}, indent=2))
    return 0 if validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

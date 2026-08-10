#!/usr/bin/env python3
"""Validate E2 native-placement smoke or full outputs.

The validator is deterministic and read-only. It treats task slots as records,
not independent statistical replicates, and performs no controller inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


REJECTION_FIELDS = {
    3: "v2i_gate_rejected",
    4: "v2i_cap_rejected",
    5: "local_mqd_rejected",
    6: "v2v_mqd_rejected",
    7: "v2i_unavailable",
    8: "v2v_unavailable",
}
PATH_KEYS = (
    "task_ingress_rsu",
    "task_selected_execution_rsu",
    "task_execution_rsu",
    "task_forwarded",
    "task_forwarding_latency_ms",
    "task_v2i_admitted",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def close(a: float, b: float, *, scale: float = 1.0) -> bool:
    return abs(float(a) - float(b)) <= max(1e-5, abs(scale) * 2e-6)


def latency_close(a: float, b: float) -> bool:
    """Float32-appropriate aggregate tolerance predeclared before E2 runs."""
    return bool(np.isclose(float(a), float(b), rtol=1e-4, atol=1e-3))


def add_check(checks: list[dict], name: str, passed: bool, observed: Any, expected: Any) -> None:
    checks.append({
        "name": name,
        "pass": bool(passed),
        "observed": observed,
        "expected": expected,
    })


def array_record(value: np.ndarray) -> dict:
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "sha256": hashlib.sha256(value.tobytes()).hexdigest(),
    }


def compare_array_sets(left: dict[str, np.ndarray], right: dict[str, np.ndarray]) -> dict:
    missing_left = sorted(set(right) - set(left))
    missing_right = sorted(set(left) - set(right))
    comparisons = []
    for key in sorted(set(left) & set(right)):
        a, b = left[key], right[key]
        passed = a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()
        comparisons.append({
            "name": key,
            "pass": bool(passed),
            "left": array_record(a),
            "right": array_record(b),
        })
    return {
        "pass": not missing_left and not missing_right and all(x["pass"] for x in comparisons),
        "missing_left": missing_left,
        "missing_right": missing_right,
        "comparisons": comparisons,
    }


def validate_path_arrays(
    *,
    per_step: dict[str, np.ndarray],
    per_task: dict[str, np.ndarray],
    summary: dict,
    rsu_lb: str,
    n_rsus: int,
    checks: list[dict],
) -> dict:
    shape = per_task["task_active"].shape
    expected_dtypes = {
        "task_ingress_rsu": np.dtype(np.int16),
        "task_selected_execution_rsu": np.dtype(np.int16),
        "task_execution_rsu": np.dtype(np.int16),
        "task_forwarded": np.dtype(np.bool_),
        "task_forwarding_latency_ms": np.dtype(np.float32),
        "task_v2i_admitted": np.dtype(np.bool_),
    }
    for key in PATH_KEYS:
        value = per_task.get(key)
        add_check(checks, f"path_{key}_present", value is not None, key in per_task, True)
        if value is not None:
            add_check(checks, f"path_{key}_shape", value.shape == shape, list(value.shape), list(shape))
            add_check(checks, f"path_{key}_dtype", value.dtype == expected_dtypes[key],
                      str(value.dtype), str(expected_dtypes[key]))

    if any(key not in per_task for key in PATH_KEYS):
        return {
            "v2i_attempts": None,
            "v2i_admitted": None,
            "forwarded": None,
            "execution_count_per_rsu": None,
            "execution_share_range": None,
        }

    ingress = per_task["task_ingress_rsu"]
    selected = per_task["task_selected_execution_rsu"]
    execution = per_task["task_execution_rsu"]
    forwarded = per_task["task_forwarded"].astype(bool)
    forwarding_ms = per_task["task_forwarding_latency_ms"]
    admitted = per_task["task_v2i_admitted"].astype(bool)
    active = per_task["task_active"].astype(bool)
    actions = per_step["veh_action"][:, None, :]
    expected_attempt = active & (actions == 1)
    attempt = ingress >= 0

    add_check(checks, "path_attempt_identity", np.array_equal(attempt, expected_attempt),
              int(attempt.sum()), int(expected_attempt.sum()))
    add_check(checks, "path_selected_presence", np.array_equal(selected >= 0, attempt),
              int((selected >= 0).sum()), int(attempt.sum()))
    add_check(checks, "path_execution_presence", np.array_equal(execution >= 0, admitted),
              int((execution >= 0).sum()), int(admitted.sum()))
    valid_indices = all(
        not np.any((per_task[key] < -1) | (per_task[key] >= n_rsus))
        for key in ("task_ingress_rsu", "task_selected_execution_rsu", "task_execution_rsu")
    )
    add_check(checks, "path_index_domain", valid_indices, "all indices", f"[-1,{n_rsus})")
    expected_forwarded = admitted & (execution != ingress)
    add_check(checks, "path_forwarded_definition", np.array_equal(forwarded, expected_forwarded),
              int(forwarded.sum()), int(expected_forwarded.sum()))
    add_check(checks, "path_nonforwarded_latency_zero", np.all(forwarding_ms[~forwarded] == 0.0),
              float(forwarding_ms[~forwarded].sum(dtype=np.float64)), 0.0)
    add_check(checks, "path_forwarding_latency_finite_nonnegative",
              np.isfinite(forwarding_ms).all() and np.all(forwarding_ms >= 0.0),
              [float(forwarding_ms.min(initial=0.0)), float(forwarding_ms.max(initial=0.0))],
              "finite and >=0")
    add_check(checks, "zero_backhaul_charged_latency_zero", np.all(forwarding_ms == 0.0),
              float(forwarding_ms.sum(dtype=np.float64)), 0.0)
    if rsu_lb == "off":
        add_check(checks, "off_selected_equals_ingress", np.array_equal(
            selected[attempt], ingress[attempt]), True, True)

    outcome = per_task["task_outcome"]
    rejected_v2i = np.isin(outcome, (3, 4, 7))
    expected_admitted = expected_attempt & np.isin(outcome, (1, 2))
    add_check(checks, "v2i_admission_outcome_identity", np.array_equal(
        admitted, expected_admitted), int(admitted.sum()), int(expected_admitted.sum()))
    add_check(checks, "rejected_v2i_has_no_execution", np.all(execution[rejected_v2i] == -1),
              np.unique(execution[rejected_v2i]).tolist(), [-1])
    add_check(checks, "rejected_v2i_not_forwarded", not np.any(forwarded[rejected_v2i]),
              int(forwarded[rejected_v2i].sum()), 0)
    add_check(checks, "rejected_v2i_not_admitted", not np.any(admitted[rejected_v2i]),
              int(admitted[rejected_v2i].sum()), 0)
    add_check(checks, "nonforwarded_admitted_executes_at_ingress", np.all(
        execution[admitted & ~forwarded] == ingress[admitted & ~forwarded]), True, True)

    ingress_count = np.bincount(ingress[attempt], minlength=n_rsus).astype(np.int64)
    selected_count = np.bincount(selected[attempt], minlength=n_rsus).astype(np.int64)
    execution_count = np.bincount(execution[admitted], minlength=n_rsus).astype(np.int64)
    matrix = np.zeros((n_rsus, n_rsus), dtype=np.int64)
    np.add.at(matrix, (ingress[admitted], execution[admitted]), 1)
    admitted_n = int(admitted.sum())
    forwarded_n = int(forwarded.sum())
    shares = (execution_count / admitted_n) if admitted_n else np.zeros(n_rsus)
    metrics = summary["v2i_path_metrics"]
    exact_fields = {
        "v2i_attempts": int(attempt.sum()),
        "v2i_admitted_tasks": admitted_n,
        "ingress_count_per_rsu": ingress_count.tolist(),
        "selected_target_count_per_rsu": selected_count.tolist(),
        "actual_execution_count_per_rsu": execution_count.tolist(),
        "forwarded_admitted_task_count": forwarded_n,
        "ingress_to_execution_pair_matrix": matrix.tolist(),
    }
    for field, expected in exact_fields.items():
        add_check(checks, f"path_aggregate_{field}", metrics[field] == expected,
                  metrics[field], expected)
    float_fields = {
        "forwarded_share_of_admitted_v2i": forwarded_n / admitted_n if admitted_n else 0.0,
        "total_forwarding_latency_ms": float(forwarding_ms.sum(dtype=np.float64)),
        "mean_forwarding_latency_ms_per_admitted_v2i": (
            float(forwarding_ms[admitted].sum(dtype=np.float64)) / admitted_n if admitted_n else 0.0
        ),
        "mean_forwarding_latency_ms_per_forwarded_v2i": (
            float(forwarding_ms[forwarded].sum(dtype=np.float64)) / forwarded_n if forwarded_n else 0.0
        ),
        "maximum_execution_share": float(shares.max()),
    }
    for field, expected in float_fields.items():
        add_check(checks, f"path_aggregate_{field}", close(metrics[field], expected),
                  metrics[field], expected)
    add_check(checks, "path_aggregate_execution_share_per_rsu", np.allclose(
        metrics["execution_share_per_rsu"], shares, rtol=0.0, atol=1e-12),
        metrics["execution_share_per_rsu"], shares.tolist())
    imbalance = float(shares.max() - shares.min())
    add_check(checks, "path_aggregate_imbalance", close(
        metrics["imbalance_diagnostic"]["value"], imbalance),
        metrics["imbalance_diagnostic"]["value"], imbalance)
    return {
        "v2i_attempts": int(attempt.sum()),
        "v2i_admitted": admitted_n,
        "forwarded": forwarded_n,
        "execution_count_per_rsu": execution_count.tolist(),
        "execution_share_range": imbalance,
    }


def validate_run(run_dir: Path, *, arm: dict, manifest: dict, expected_steps: int) -> dict:
    checks: list[dict] = []
    required = ["summary.json", "per_step.npz", "per_task.npz", "command.json", "checksums.sha256"]
    for name in required:
        add_check(checks, f"artifact_{name}", (run_dir / name).is_file(),
                  str(run_dir / name), "file exists")
    if any(not item["pass"] for item in checks):
        return {"run_dir": str(run_dir), "status": "failed", "checks": checks}

    summary = json.loads((run_dir / "summary.json").read_text())
    command = json.loads((run_dir / "command.json").read_text())
    per_step = load_npz(run_dir / "per_step.npz")
    per_task = load_npz(run_dir / "per_task.npz")
    design = manifest["design"]
    expected_summary = {
        "T": expected_steps,
        "maxN": design["padded_fleet_width"],
        "rsu_max_concurrent": design["resolved_cap_tasks_per_rsu"],
        "fleet": design["fleet"],
        "fleet_seed": design["fleet_seed"],
        "obs_variant": "onehot17",
        "lambda_arrival": design["arrival_lambda"],
        "rsu_service_mult": design["rsu_service_multiplier"],
        "rsu_lb": arm["rsu_lb"],
        "rsu_backhaul_ms": design["backhaul_ms"],
        "k8s_scale": "off",
        "rsu_cap_mode": "reject",
        "substep_queue": "sequential",
        "veh_queue_mode": "conserved",
    }
    for field, expected in expected_summary.items():
        add_check(checks, f"summary_{field}", summary.get(field) == expected,
                  summary.get(field), expected)

    numeric_summary = []
    for key, value in summary.items():
        if isinstance(value, (int, float)):
            numeric_summary.append((key, float(value)))
    invalid_summary = [key for key, value in numeric_summary if not np.isfinite(value) or value < 0]
    # k8s_first_scaleup_s is the documented -1 sentinel under scaling off.
    invalid_summary = [key for key in invalid_summary if key != "k8s_first_scaleup_s"]
    add_check(checks, "summary_finite_nonnegative", not invalid_summary, invalid_summary, [])

    numeric_arrays = {
        f"per_step.{key}": value for key, value in per_step.items()
        if np.issubdtype(value.dtype, np.number)
    } | {
        f"per_task.{key}": value for key, value in per_task.items()
        if np.issubdtype(value.dtype, np.number)
    }
    invalid_arrays = [
        key for key, value in numeric_arrays.items() if not np.isfinite(value).all()
    ]
    add_check(checks, "arrays_finite", not invalid_arrays, invalid_arrays, [])

    active = per_task["task_active"].astype(bool)
    outcome = per_task["task_outcome"]
    met = per_task["task_met"].astype(bool)
    latency = per_task["task_lat_ms"]
    offered = int(active.sum())
    outcome_counts = {code: int(((outcome == code) & active).sum()) for code in range(1, 9)}
    rejected = sum(outcome_counts[code] for code in range(3, 9))
    admitted = outcome_counts[1] + outcome_counts[2]
    add_check(checks, "active_equals_offered", summary["n_offered"] == offered,
              summary["n_offered"], offered)
    add_check(checks, "terminal_outcome_unique", np.all((outcome[active] >= 1) & (outcome[active] <= 8)),
              sorted(np.unique(outcome[active]).tolist()), "codes 1..8")
    add_check(checks, "inactive_outcome_zero", np.all(outcome[~active] == 0),
              sorted(np.unique(outcome[~active]).tolist()), [0])
    add_check(checks, "task_conservation", offered == admitted + rejected,
              offered, admitted + rejected)
    add_check(checks, "summary_admitted", int(summary["n_admitted"]) == admitted,
              summary["n_admitted"], admitted)
    add_check(checks, "met_flag_equals_outcome1", np.array_equal(met, active & (outcome == 1)),
              int(met.sum()), outcome_counts[1])
    for code, field in REJECTION_FIELDS.items():
        add_check(checks, f"outcome_{code}_{field}", int(summary[field]) == outcome_counts[code],
                  summary[field], outcome_counts[code])

    action_counts = {
        "local": int(per_step["n_local"].sum(dtype=np.int64)),
        "v2i": int(per_step["n_v2i"].sum(dtype=np.int64)),
        "v2v": int(per_step["n_v2v"].sum(dtype=np.int64)),
    }
    add_check(checks, "per_step_arrivals", int(per_step["arrivals"].sum()) == offered,
              int(per_step["arrivals"].sum()), offered)
    add_check(checks, "per_step_done", int(per_step["done"].sum()) == outcome_counts[1],
              int(per_step["done"].sum()), outcome_counts[1])
    add_check(checks, "action_conservation", sum(action_counts.values()) == offered,
              sum(action_counts.values()), offered)
    v2i_admitted_count = int(per_task["task_v2i_admitted"].sum())
    v2i_terminal_count = (
        v2i_admitted_count + outcome_counts[3] + outcome_counts[4] + outcome_counts[7]
    )
    add_check(checks, "v2i_attempt_conservation",
              action_counts["v2i"] == v2i_terminal_count,
              action_counts["v2i"], v2i_terminal_count)

    completion = outcome_counts[1] / max(offered, 1)
    completion_admitted = outcome_counts[1] / max(admitted, 1)
    add_check(checks, "offered_completion_denominator", close(summary["completion"], completion),
              summary["completion"], completion)
    add_check(checks, "admitted_completion_denominator", close(
        summary["completion_admitted"], completion_admitted),
        summary["completion_admitted"], completion_admitted)
    admitted_mask = active & np.isin(outcome, (1, 2))
    latency_expectations = {
        "avg_latency_ms_per_task": float(latency[active].sum(dtype=np.float64)) / max(offered, 1),
        "avg_latency_admitted_ms": float(latency[admitted_mask].sum(dtype=np.float64)) / max(admitted, 1),
        "avg_latency_met_ms": float(latency[active & (outcome == 1)].sum(dtype=np.float64)) / max(outcome_counts[1], 1),
    }
    for field, expected in latency_expectations.items():
        add_check(checks, f"{field}_denominator", latency_close(summary[field], expected),
                  summary[field], expected)
    total_energy = summary.get("total_energy_j")
    add_check(checks, "total_energy_numerator_present", total_energy is not None,
              total_energy, "finite additive total energy numerator")
    expected_energy = float(total_energy) / max(offered, 1) if total_energy is not None else None
    add_check(checks, "energy_per_offered_denominator",
              expected_energy is not None and close(
                  summary["avg_energy_j_per_task"], expected_energy,
                  scale=expected_energy),
              summary["avg_energy_j_per_task"], expected_energy)
    for task_type, field in enumerate(("t1_completion", "t2_completion", "t3_completion")):
        type_mask = active & (per_task["task_type"] == task_type)
        expected = int((type_mask & (outcome == 1)).sum()) / max(int(type_mask.sum()), 1)
        add_check(checks, f"{field}_denominator", close(summary[field], expected),
                  summary[field], expected)
    for action, field in (("local", "p_local"), ("v2i", "p_v2i"), ("v2v", "p_v2v")):
        expected = action_counts[action] / max(offered, 1)
        add_check(checks, f"{field}_denominator", close(summary[field], expected),
                  summary[field], expected)

    work = summary["work_ms"]
    add_check(checks, "v2i_work_conservation", close(
        work["v2i_offered"], work["v2i_admitted"] + work["v2i_rejected_or_unavailable"],
        scale=work["v2i_offered"]), work["v2i_offered"],
        work["v2i_admitted"] + work["v2i_rejected_or_unavailable"])
    add_check(checks, "vehicle_work_conservation", close(
        work["veh_offered"], work["veh_admitted"] + work["veh_rejected"],
        scale=work["veh_offered"]), work["veh_offered"],
        work["veh_admitted"] + work["veh_rejected"])

    path_metrics = validate_path_arrays(
        per_step=per_step, per_task=per_task, summary=summary,
        rsu_lb=arm["rsu_lb"], n_rsus=design["rsus"], checks=checks,
    )
    actor_logits = per_step.get("veh_actor_logits")
    add_check(checks, "actor_logits_schema",
              actor_logits is not None
              and actor_logits.shape == (expected_steps, design["padded_fleet_width"], 3)
              and actor_logits.dtype == np.float32,
              array_record(actor_logits) if actor_logits is not None else None,
              {"shape": [expected_steps, design["padded_fleet_width"], 3], "dtype": "float32"})

    file_hashes = {
        name: sha256(run_dir / name) for name in required if (run_dir / name).is_file()
    }
    return {
        "run_dir": str(run_dir.resolve()),
        "arm": arm["id"],
        "status": "passed" if all(item["pass"] for item in checks) else "failed",
        "checks": checks,
        "summary": summary,
        "command": command,
        "path_metrics": path_metrics,
        "array_identities": {
            "per_step": {key: array_record(value) for key, value in per_step.items()},
            "per_task": {key: array_record(value) for key, value in per_task.items()},
        },
        "file_sha256": file_hashes,
    }


def validate_phase(manifest: dict, phase: str) -> dict:
    raw_root = Path(manifest["outputs"]["raw_root"])
    expected_steps = manifest["smoke_gate"]["steps"] if phase == "smoke" else manifest["design"]["steps"]
    repeats = manifest["smoke_gate"]["serial_repeats_per_arm"] if phase == "smoke" else 1
    runs = []
    by_arm: dict[str, list[dict]] = {}
    for arm in manifest["arms"]:
        arm_runs = []
        for repeat in range(1, repeats + 1):
            run = validate_run(
                raw_root / phase / arm["id"] / f"run_{repeat}",
                arm=arm, manifest=manifest, expected_steps=expected_steps,
            )
            runs.append(run)
            arm_runs.append(run)
        by_arm[arm["id"]] = arm_runs

    if any(run["status"] != "passed" for run in runs):
        return {
            "schema_version": "e2_native_placement_validation_v1",
            "phase": phase,
            "status": "failed",
            "statistical_status": "one-seed descriptive bounded pilot; tasks are not replicates",
            "runs": runs,
            "repeat_checks": [],
            "cross_arm_identity_checks": [],
            "failure": "one or more run-level gates failed; repeat/cross-arm comparison not attempted",
        }

    repeat_checks = []
    if phase == "smoke":
        for arm in manifest["arms"]:
            left, right = by_arm[arm["id"]]
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
                "pass": left_summary == right_summary and step_cmp["pass"] and task_cmp["pass"],
                "scientific_summary_exact_excluding_wall_s": left_summary == right_summary,
                "per_step": step_cmp,
                "per_task": task_cmp,
            })

    cross_arm_checks = []
    reference_arm = manifest["arms"][0]["id"]
    reference_run = by_arm[reference_arm][0]
    ref_step = load_npz(Path(reference_run["run_dir"]) / "per_step.npz")
    ref_task = load_npz(Path(reference_run["run_dir"]) / "per_task.npz")
    logit_contract = manifest["cross_arm_actor_stream_contract"]["logit_diagnostic"]
    for arm in manifest["arms"][1:]:
        candidate_run = by_arm[arm["id"]][0]
        step = load_npz(Path(candidate_run["run_dir"]) / "per_step.npz")
        task = load_npz(Path(candidate_run["run_dir"]) / "per_task.npz")
        reference_logits = ref_step["veh_actor_logits"]
        candidate_logits = step["veh_actor_logits"]
        logit_shape_dtype_equal = (
            reference_logits.shape == candidate_logits.shape
            and reference_logits.dtype == candidate_logits.dtype == np.float32
        )
        if logit_shape_dtype_equal:
            logit_delta = np.abs(
                reference_logits.astype(np.float64) - candidate_logits.astype(np.float64)
            )
            logit_max_abs = float(logit_delta.max(initial=0.0))
            logit_finite = bool(np.isfinite(logit_delta).all())
        else:
            logit_max_abs = float("inf")
            logit_finite = False
        logit_within_tolerance = (
            logit_finite
            and logit_max_abs <= float(logit_contract["absolute_tolerance"])
        )
        fields = {
            "offered_count": reference_run["summary"]["n_offered"] == candidate_run["summary"]["n_offered"],
            "task_active": ref_task["task_active"].tobytes() == task["task_active"].tobytes(),
            "task_type": ref_task["task_type"].tobytes() == task["task_type"].tobytes(),
            "vehicle_action": ref_step["veh_action"].tobytes() == step["veh_action"].tobytes(),
            "fleet_tier": ref_step["slot_tier"].tobytes() == step["slot_tier"].tobytes(),
            "fleet_is_ev": ref_step["slot_is_ev"].tobytes() == step["slot_is_ev"].tobytes(),
        }
        cross_arm_checks.append({
            "reference": reference_arm,
            "candidate": arm["id"],
            "pass": all(fields.values()) and logit_within_tolerance,
            "fields": fields,
            "actor_logit_diagnostic": {
                "pass": logit_within_tolerance,
                "shape_dtype_equal": logit_shape_dtype_equal,
                "byte_exact": (
                    logit_shape_dtype_equal
                    and reference_logits.tobytes() == candidate_logits.tobytes()
                ),
                "maximum_absolute_difference": logit_max_abs,
                "absolute_tolerance": float(logit_contract["absolute_tolerance"]),
                "reference_sha256": hashlib.sha256(reference_logits.tobytes()).hexdigest(),
                "candidate_sha256": hashlib.sha256(candidate_logits.tobytes()).hexdigest(),
                "interpretation": logit_contract["interpretation"],
            },
        })

    passed = (
        all(run["status"] == "passed" for run in runs)
        and all(check["pass"] for check in repeat_checks)
        and all(check["pass"] for check in cross_arm_checks)
    )
    return {
        "schema_version": "e2_native_placement_validation_v1",
        "phase": phase,
        "status": "passed" if passed else "failed",
        "statistical_status": "one-seed descriptive bounded pilot; tasks are not replicates",
        "runs": runs,
        "repeat_checks": repeat_checks,
        "cross_arm_identity_checks": cross_arm_checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    validation = validate_phase(manifest, args.phase)
    if args.output_json.exists():
        raise SystemExit(f"refusing to overwrite {args.output_json}")
    args.output_json.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": validation["status"], "output": str(args.output_json)}, indent=2))
    return 0 if validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

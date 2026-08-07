#!/usr/bin/env python3
"""Validate TrafficTwin E0 corrected-evaluator smoke and full-reference outputs.

This validator intentionally reads the evaluator's aggregate, per-step and
per-task products. It does not recalculate scientific results with an LLM and
does not treat deadline attainment as evidence of physical result return.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

REJECTION_FIELDS_BY_OUTCOME = {
    3: "v2i_gate_rejected",
    4: "v2i_cap_rejected",
    5: "local_mqd_rejected",
    6: "v2v_mqd_rejected",
    7: "v2i_unavailable",
    8: "v2v_unavailable",
}
VOLATILE_SUMMARY_FIELDS = {"wall_s"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha256(value: np.ndarray) -> str:
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def _finite_json_numbers(value: Any) -> bool:  # noqa: ANN401
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return all(_finite_json_numbers(item) for item in value)
    if isinstance(value, dict):
        return all(_finite_json_numbers(item) for item in value.values())
    return False


def _close(left: float, right: float, *, scale: float = 1.0) -> bool:
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-5 * max(scale, 1.0))


def _check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    observed: Any,  # noqa: ANN401
    expected: Any,  # noqa: ANN401
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "observed": observed,
            "expected": expected,
        }
    )


def _nonnegative_integral(value: Any) -> bool:  # noqa: ANN401
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    number = float(value)
    return math.isfinite(number) and number >= 0 and number.is_integer()


def validate_run(run_dir: Path, manifest: dict[str, Any], label: str) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    per_step_path = run_dir / "per_step.npz"
    per_task_path = run_dir / "per_task.npz"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    _check(checks, "summary_numbers_finite", _finite_json_numbers(summary), True, True)

    count_fields = [
        "total_tasks",
        "n_offered",
        "n_admitted",
        *REJECTION_FIELDS_BY_OUTCOME.values(),
        "k8s_scale_events",
    ]
    invalid_counts = [field for field in count_fields if not _nonnegative_integral(summary[field])]
    _check(checks, "aggregate_counts_nonnegative_integral", not invalid_counts, invalid_counts, [])

    config = manifest["configuration"]
    expected_summary = {
        "trace": Path(manifest["inputs"]["trace"]["path"]).name,
        "actor": Path(manifest["inputs"]["actor"]["path"]).name,
        "model": "C",
        "T": manifest["scope"]["max_steps"],
        "maxN": manifest["inputs"]["trace"]["padded_fleet_width"],
        "rsu_max_concurrent": config["cap"]["resolved_value"],
        "fleet": config["fleet"]["preset"],
        "fleet_seed": config["fleet_seed"],
        "obs_variant": "onehot17",
        "lambda_arrival": config["arrival_lambda"],
        "rsu_service_mult": config["compute"]["rsu_service_multiplier"],
        "rsu_lb": config["placement"]["mode"],
        "rsu_backhaul_ms": config["placement"]["backhaul_ms"],
        "k8s_scale": config["compute"]["scaling"],
        "k8s_mean_mult": config["compute"]["mean_multiplier_expected"],
        "rsu_cap_mode": config["rsu_admission"],
        "substep_queue": config["substep_queue"],
        "veh_queue_mode": config["vehicle_queue"],
        "enter_reset": manifest["inputs"]["trace"]["has_enter_channel"],
    }
    mismatched_config = {
        field: {"observed": summary.get(field), "expected": expected}
        for field, expected in expected_summary.items()
        if summary.get(field) != expected
    }
    _check(checks, "predeclared_configuration", not mismatched_config, mismatched_config, {})

    rejection_total = sum(float(summary[field]) for field in REJECTION_FIELDS_BY_OUTCOME.values())
    offered = float(summary["n_offered"])
    admitted = float(summary["n_admitted"])
    _check(
        checks,
        "offered_equals_admitted_plus_terminal_rejections",
        offered == admitted + rejection_total,
        offered,
        admitted + rejection_total,
    )
    _check(
        checks,
        "total_tasks_equals_offered",
        float(summary["total_tasks"]) == offered,
        summary["total_tasks"],
        offered,
    )

    work = summary.get("work_ms")
    _check(checks, "work_ledger_present", isinstance(work, dict), type(work).__name__, "dict")
    if isinstance(work, dict):
        work_values = {field: float(value) for field, value in work.items()}
        _check(
            checks,
            "work_ms_nonnegative_finite",
            all(math.isfinite(value) and value >= 0 for value in work_values.values()),
            work_values,
            "all finite and >= 0",
        )
        _check(
            checks,
            "v2i_work_ms_conserved",
            work_values["v2i_offered"]
            == work_values["v2i_admitted"] + work_values["v2i_rejected_or_unavailable"],
            work_values["v2i_offered"],
            work_values["v2i_admitted"] + work_values["v2i_rejected_or_unavailable"],
        )
        _check(
            checks,
            "vehicle_work_ms_conserved",
            work_values["veh_offered"] == work_values["veh_admitted"] + work_values["veh_rejected"],
            work_values["veh_offered"],
            work_values["veh_admitted"] + work_values["veh_rejected"],
        )

    with np.load(per_step_path, allow_pickle=False) as per_step_file:
        per_step = {key: per_step_file[key] for key in per_step_file.files}
    with np.load(per_task_path, allow_pickle=False) as per_task_file:
        per_task = {key: per_task_file[key] for key in per_task_file.files}

    numeric_arrays = {
        f"per_step.{key}": value
        for key, value in per_step.items()
        if np.issubdtype(value.dtype, np.number)
    } | {
        f"per_task.{key}": value
        for key, value in per_task.items()
        if np.issubdtype(value.dtype, np.number)
    }
    nonfinite_arrays = [
        name for name, value in numeric_arrays.items() if not np.isfinite(value).all()
    ]
    _check(checks, "instrumentation_arrays_finite", not nonfinite_arrays, nonfinite_arrays, [])

    active = per_task["task_active"].astype(bool)
    outcome = per_task["task_outcome"]
    met = per_task["task_met"].astype(bool)
    latency = per_task["task_lat_ms"]
    active_count = int(active.sum())
    outcome_counts = {str(code): int(((outcome == code) & active).sum()) for code in range(1, 9)}
    _check(checks, "active_records_equal_offered", active_count == offered, active_count, offered)
    _check(
        checks,
        "every_active_task_has_one_terminal_outcome",
        int((active & ((outcome < 1) | (outcome > 8))).sum()) == 0,
        int((active & ((outcome < 1) | (outcome > 8))).sum()),
        0,
    )
    _check(
        checks,
        "inactive_records_have_no_terminal_outcome",
        int((~active & (outcome != 0)).sum()) == 0,
        int((~active & (outcome != 0)).sum()),
        0,
    )
    _check(
        checks,
        "deadline_met_flag_matches_outcome_1",
        np.array_equal(met, active & (outcome == 1)),
        int(met.sum()),
        outcome_counts["1"],
    )
    _check(
        checks,
        "admitted_records_equal_outcomes_1_and_2",
        outcome_counts["1"] + outcome_counts["2"] == admitted,
        outcome_counts["1"] + outcome_counts["2"],
        admitted,
    )
    for code, field in REJECTION_FIELDS_BY_OUTCOME.items():
        _check(
            checks,
            f"outcome_{code}_equals_{field}",
            outcome_counts[str(code)] == summary[field],
            outcome_counts[str(code)],
            summary[field],
        )

    arrivals = int(per_step["arrivals"].sum(dtype=np.int64))
    done = int(per_step["done"].sum(dtype=np.int64))
    action_total = sum(
        int(per_step[field].sum(dtype=np.int64)) for field in ("n_local", "n_v2i", "n_v2v")
    )
    _check(checks, "per_step_arrivals_equal_offered", arrivals == offered, arrivals, offered)
    _check(
        checks,
        "per_step_done_equals_deadline_met",
        done == outcome_counts["1"],
        done,
        outcome_counts["1"],
    )
    _check(checks, "action_counts_equal_offered", action_total == offered, action_total, offered)

    nonnegative_array_names = (
        "active",
        "arrivals",
        "done",
        "n_local",
        "n_v2i",
        "n_v2v",
        "rsu_busy_ms",
        "rsu_load",
        "slot_tier",
        "task_lat_ms",
        "task_outcome",
        "task_type",
        "veh_done",
        "veh_k",
        "veh_queue_ms",
    )
    invalid_nonnegative_arrays = []
    for name in nonnegative_array_names:
        value = per_step.get(name, per_task.get(name))
        if value is not None and value.min(initial=0) < 0:
            invalid_nonnegative_arrays.append(name)
    _check(
        checks,
        "count_work_latency_arrays_nonnegative",
        not invalid_nonnegative_arrays,
        invalid_nonnegative_arrays,
        [],
    )

    deadline_met = outcome_counts["1"]
    expected_completion = deadline_met / max(active_count, 1)
    expected_completion_admitted = deadline_met / max(int(admitted), 1)
    _check(
        checks,
        "offered_completion_denominator",
        _close(float(summary["completion"]), expected_completion),
        summary["completion"],
        expected_completion,
    )
    _check(
        checks,
        "admitted_completion_denominator",
        _close(float(summary["completion_admitted"]), expected_completion_admitted),
        summary["completion_admitted"],
        expected_completion_admitted,
    )
    _check(
        checks,
        "offered_and_admitted_denominators_retained_separately",
        "completion" in summary and "completion_admitted" in summary,
        ["completion", "completion_admitted"],
        ["completion", "completion_admitted"],
    )

    active_latency_sum = float(latency[active].sum(dtype=np.float64))
    admitted_mask = active & ((outcome == 1) | (outcome == 2))
    admitted_latency_sum = float(latency[admitted_mask].sum(dtype=np.float64))
    met_latency_sum = float(latency[active & (outcome == 1)].sum(dtype=np.float64))
    latency_expectations = {
        "avg_latency_ms_per_task": active_latency_sum / max(active_count, 1),
        "avg_latency_admitted_ms": admitted_latency_sum / max(int(admitted), 1),
        "avg_latency_met_ms": met_latency_sum / max(deadline_met, 1),
    }
    for field, expected in latency_expectations.items():
        _check(
            checks,
            f"{field}_denominator",
            _close(float(summary[field]), expected, scale=expected),
            summary[field],
            expected,
        )

    completion_fields = [
        "completion",
        "completion_admitted",
        "t1_completion",
        "t2_completion",
        "t3_completion",
    ]
    invalid_fractions = [
        field for field in completion_fields if not 0.0 <= float(summary[field]) <= 1.0
    ]
    _check(
        checks,
        "completion_fractions_in_unit_interval",
        not invalid_fractions,
        invalid_fractions,
        [],
    )

    output_checksums = {
        path.name: sha256_file(path)
        for path in sorted(run_dir.iterdir())
        if path.is_file() and path.name != "checksums.sha256"
    }
    array_checksums = {
        "per_step": {key: array_sha256(value) for key, value in sorted(per_step.items())},
        "per_task": {key: array_sha256(value) for key, value in sorted(per_task.items())},
    }
    return {
        "label": label,
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "observed": {
            "n_offered": int(offered),
            "n_admitted": int(admitted),
            "deadline_met": deadline_met,
            "terminal_rejections_or_unavailability": int(rejection_total),
            "outcome_counts": outcome_counts,
            "work_unit": "milliseconds of service work",
            "completion_offered": summary["completion"],
            "completion_admitted": summary["completion_admitted"],
            "wall_s_excluded_from_repeat_verdict": summary["wall_s"],
        },
        "output_sha256": output_checksums,
        "array_sha256": array_checksums,
        "scientific_summary": {
            key: value for key, value in summary.items() if key not in VOLATILE_SUMMARY_FIELDS
        },
    }


def compare_runs(run_1: dict[str, Any], run_2: dict[str, Any]) -> dict[str, Any]:
    summary_equal = run_1["scientific_summary"] == run_2["scientific_summary"]
    array_equal = run_1["array_sha256"] == run_2["array_sha256"]
    raw_file_equality = {
        filename: digest == run_2["output_sha256"].get(filename)
        for filename, digest in run_1["output_sha256"].items()
        if filename in run_2["output_sha256"]
    }
    return {
        "passed": summary_equal and array_equal,
        "comparison_method": (
            "Exact JSON equality excluding wall_s; exact dtype/shape/byte SHA-256 "
            "equality for every NPZ array."
        ),
        "excluded_volatile_summary_fields": sorted(VOLATILE_SUMMARY_FIELDS),
        "scientific_summary_identical": summary_equal,
        "instrumentation_arrays_identical": array_equal,
        "raw_file_sha256_equal": raw_file_equality,
    }


def build_report(
    manifest_path: Path,
    run_1_dir: Path,
    run_2_dir: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_checks = {
        "manifest": sha256_file(manifest_path),
        "actor": sha256_file(actor_path),
        "trace": sha256_file(trace_path),
    }
    expected_inputs = {
        "actor": manifest["inputs"]["actor"]["sha256"],
        "trace": manifest["inputs"]["trace"]["sha256"],
    }
    input_identity_passed = all(
        input_checks[name] == digest for name, digest in expected_inputs.items()
    )
    run_1 = validate_run(run_1_dir, manifest, "run_1")
    run_2 = validate_run(run_2_dir, manifest, "run_2")
    repeat = compare_runs(run_1, run_2)
    passed = input_identity_passed and run_1["passed"] and run_2["passed"] and repeat["passed"]
    return {
        "schema_version": "traffictwin.e0-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "passed": passed,
        "decision": "bounded_e0_smoke_pass" if passed else "bounded_e0_smoke_fail",
        "input_identity": {
            "passed": input_identity_passed,
            "sha256": input_checks,
            "expected_sha256": expected_inputs,
        },
        "runs": [run_1, run_2],
        "repeat": repeat,
        "semantic_boundary": {
            "measured_outcome": "simulated deadline attainment",
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
        },
        "readiness_scope": (
            "A pass supports only a full corrected strongest-link reference run under the "
            "same provisional configuration; it does not authorize E1."
        ),
    }


def build_single_run_report(
    manifest_path: Path,
    run_dir: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    """Build a deterministic report for one post-smoke full reference."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    input_checks = {
        "manifest": sha256_file(manifest_path),
        "actor": sha256_file(actor_path),
        "trace": sha256_file(trace_path),
    }
    expected_inputs = {
        "actor": manifest["inputs"]["actor"]["sha256"],
        "trace": manifest["inputs"]["trace"]["sha256"],
    }
    input_identity_passed = all(
        input_checks[name] == digest for name, digest in expected_inputs.items()
    )
    run = validate_run(run_dir, manifest, "run_1")
    passed = input_identity_passed and run["passed"]
    return {
        "schema_version": "traffictwin.e0-full-reference-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "passed": passed,
        "decision": "full_corrected_reference_pass" if passed else "full_corrected_reference_fail",
        "input_identity": {
            "passed": input_identity_passed,
            "sha256": input_checks,
            "expected_sha256": expected_inputs,
        },
        "runs": [run],
        "repeat": {
            "requested": False,
            "reason": (
                "The predecessor bounded smoke already passed an exact repeat; this "
                "authorisation covered one full reference."
            ),
        },
        "semantic_boundary": {
            "measured_outcome": "simulated deadline attainment",
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
        },
        "readiness_scope": (
            "A pass establishes one full corrected strongest-link reference under the "
            "provisional configuration; it does not authorise E1."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--run-1", required=True, type=Path)
    parser.add_argument("--run-2", type=Path)
    parser.add_argument("--actor", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if args.run_2 is None:
        report = build_single_run_report(
            args.manifest,
            args.run_1,
            args.actor,
            args.trace,
        )
    else:
        report = build_report(args.manifest, args.run_1, args.run_2, args.actor, args.trace)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "output": str(args.output)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

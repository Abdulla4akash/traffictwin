#!/usr/bin/env python3
"""Validate the bounded E1 2.5x legacy/physical semantics pair.

The legacy snapshot/clamp path does not emit admitted-task identities, terminal
rejection outcomes, or a work ledger. This validator therefore checks every
quantity that path actually records and preserves the missing conservation
evidence as a limitation. It never turns legacy zero counters into evidence of
zero rejection and never labels deadline attainment as physical result return.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

try:
    from scripts.validate_e0_smoke import (
        VOLATILE_SUMMARY_FIELDS,
        _check,
        _close,
        _finite_json_numbers,
        _nonnegative_integral,
        array_sha256,
        sha256_file,
    )
except ModuleNotFoundError:  # direct `python scripts/validate_...py` execution
    from validate_e0_smoke import (  # type: ignore[no-redef]
        VOLATILE_SUMMARY_FIELDS,
        _check,
        _close,
        _finite_json_numbers,
        _nonnegative_integral,
        array_sha256,
        sha256_file,
    )


LEGACY_NULL_FIELDS = (
    "n_admitted",
    "completion_admitted",
    "avg_latency_admitted_ms",
    "avg_latency_met_ms",
    "work_ms",
)
LEGACY_UNOBSERVABLE_COUNTERS = (
    "v2i_gate_rejected",
    "v2i_cap_rejected",
    "local_mqd_rejected",
    "v2v_mqd_rejected",
    "v2i_unavailable",
    "v2v_unavailable",
)


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _scientific_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if key not in VOLATILE_SUMMARY_FIELDS}


def _file_hashes(run_dir: Path) -> dict[str, str]:
    names = ("summary.json", "per_step.npz", "per_task.npz", "stdout_stderr.log")
    return {name: sha256_file(run_dir / name) for name in names if (run_dir / name).is_file()}


def validate_legacy_run(
    run_dir: Path,
    manifest: dict[str, Any],
    *,
    label: str,
    expected_steps: int,
) -> dict[str, Any]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    per_step = _load_npz(run_dir / "per_step.npz")
    per_task = _load_npz(run_dir / "per_task.npz")
    checks: list[dict[str, Any]] = []

    _check(checks, "summary_numbers_finite", _finite_json_numbers(summary), True, True)
    invalid_counts = [
        field
        for field in ("total_tasks", "n_offered", "k8s_scale_events")
        if not _nonnegative_integral(summary.get(field))
    ]
    _check(checks, "aggregate_counts_nonnegative_integral", not invalid_counts, invalid_counts, [])

    controlled = manifest["controlled_configuration"]
    legacy = manifest["arms"]["legacy"]
    expected_summary = {
        "trace": Path(manifest["inputs"]["trace"]["path"]).name,
        "actor": Path(manifest["inputs"]["actor"]["path"]).name,
        "model": "C",
        "T": expected_steps,
        "maxN": manifest["inputs"]["trace"]["padded_fleet_width"],
        "rsu_max_concurrent": controlled["cap"]["resolved_value"],
        "fleet": controlled["fleet"]["preset"],
        "fleet_seed": controlled["fleet_seed"],
        "obs_variant": "onehot17",
        "lambda_arrival": controlled["arrival_lambda"],
        "rsu_service_mult": controlled["compute"]["rsu_service_multiplier"],
        "rsu_lb": controlled["placement"]["mode"],
        "rsu_backhaul_ms": controlled["placement"]["backhaul_ms"],
        "k8s_scale": controlled["compute"]["scaling"],
        "k8s_mean_mult": controlled["compute"]["mean_multiplier_expected"],
        "rsu_cap_mode": legacy["rsu_cap_mode"],
        "substep_queue": legacy["substep_queue"],
        "veh_queue_mode": legacy["vehicle_queue_effective"],
        "enter_reset": manifest["inputs"]["trace"]["has_enter_channel"],
    }
    mismatched_config = {
        field: {"observed": summary.get(field), "expected": expected}
        for field, expected in expected_summary.items()
        if summary.get(field) != expected
    }
    _check(checks, "predeclared_configuration", not mismatched_config, mismatched_config, {})

    offered = float(summary["n_offered"])
    _check(
        checks,
        "total_tasks_equals_offered",
        float(summary["total_tasks"]) == offered,
        summary["total_tasks"],
        offered,
    )
    nonnull_legacy_fields = {
        field: summary.get(field) for field in LEGACY_NULL_FIELDS if summary.get(field) is not None
    }
    _check(
        checks,
        "legacy_unavailable_fields_remain_null",
        not nonnull_legacy_fields,
        nonnull_legacy_fields,
        {},
    )
    nonzero_placeholder_counters = {
        field: summary.get(field)
        for field in LEGACY_UNOBSERVABLE_COUNTERS
        if summary.get(field) != 0.0
    }
    _check(
        checks,
        "legacy_placeholder_counters_match_source_contract",
        not nonzero_placeholder_counters,
        nonzero_placeholder_counters,
        {},
    )
    _check(
        checks,
        "legacy_task_outcome_absent",
        "task_outcome" not in per_task,
        sorted(per_task),
        "task_outcome absent",
    )

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
    met = per_task["task_met"].astype(bool)
    task_type = per_task["task_type"]
    task_latency = per_task["task_lat_ms"]
    active_count = int(active.sum())
    deadline_met = int((met & active).sum())
    _check(checks, "active_records_equal_offered", active_count == offered, active_count, offered)
    _check(
        checks,
        "inactive_records_not_deadline_met",
        int((met & ~active).sum()) == 0,
        int((met & ~active).sum()),
        0,
    )
    invalid_task_types = int((active & ((task_type < 0) | (task_type > 2))).sum())
    _check(checks, "active_task_types_in_range", invalid_task_types == 0, invalid_task_types, 0)

    arrivals = int(per_step["arrivals"].sum(dtype=np.int64))
    done = int(per_step["done"].sum(dtype=np.int64))
    action_counts = {
        field: int(per_step[field].sum(dtype=np.int64)) for field in ("n_local", "n_v2i", "n_v2v")
    }
    _check(checks, "per_step_arrivals_equal_offered", arrivals == offered, arrivals, offered)
    _check(checks, "per_step_done_equals_deadline_met", done == deadline_met, done, deadline_met)
    _check(
        checks,
        "action_counts_equal_offered",
        sum(action_counts.values()) == offered,
        sum(action_counts.values()),
        offered,
    )

    invalid_nonnegative_arrays = []
    for name in (
        "active",
        "arrivals",
        "done",
        "lat_sum",
        "n_local",
        "n_v2i",
        "n_v2v",
        "rsu_busy_ms",
        "rsu_load",
        "slot_tier",
        "task_lat_ms",
        "task_type",
        "veh_done",
        "veh_k",
        "veh_queue_ms",
    ):
        value = per_step.get(name, per_task.get(name))
        if value is not None and value.min(initial=0) < 0:
            invalid_nonnegative_arrays.append(name)
    _check(
        checks,
        "count_queue_latency_arrays_nonnegative",
        not invalid_nonnegative_arrays,
        invalid_nonnegative_arrays,
        [],
    )

    observed_completion = deadline_met / max(offered, 1.0)
    _check(
        checks,
        "offered_completion_denominator",
        _close(float(summary["completion"]), observed_completion),
        summary["completion"],
        observed_completion,
    )
    per_step_latency = float(per_step["lat_sum"].sum(dtype=np.float64)) / max(offered, 1.0)
    per_task_latency = float(task_latency[active].sum(dtype=np.float64)) / max(offered, 1.0)
    _check(
        checks,
        "penalty_inclusive_latency_per_step_denominator",
        _close(float(summary["avg_latency_ms_per_task"]), per_step_latency, scale=per_step_latency),
        summary["avg_latency_ms_per_task"],
        per_step_latency,
    )
    _check(
        checks,
        "penalty_inclusive_latency_per_task_denominator",
        _close(float(summary["avg_latency_ms_per_task"]), per_task_latency, scale=per_task_latency),
        summary["avg_latency_ms_per_task"],
        per_task_latency,
    )

    for code, field in ((0, "t1_completion"), (1, "t2_completion"), (2, "t3_completion")):
        type_total = int((active & (task_type == code)).sum())
        type_met = int((active & met & (task_type == code)).sum())
        observed = type_met / max(type_total, 1)
        _check(
            checks,
            f"{field}_denominator",
            _close(summary[field], observed),
            summary[field],
            observed,
        )

    for field, count in action_counts.items():
        probability_field = {"n_local": "p_local", "n_v2i": "p_v2i", "n_v2v": "p_v2v"}[field]
        observed = count / max(offered, 1.0)
        _check(
            checks,
            f"{probability_field}_denominator",
            _close(summary[probability_field], observed),
            summary[probability_field],
            observed,
        )

    fraction_fields = (
        "completion",
        "t1_completion",
        "t2_completion",
        "t3_completion",
        "p_local",
        "p_v2i",
        "p_v2v",
    )
    invalid_fractions = [
        field for field in fraction_fields if not 0.0 <= float(summary[field]) <= 1.0
    ]
    _check(checks, "fractions_in_unit_interval", not invalid_fractions, invalid_fractions, [])

    array_hashes = {
        "per_step": {key: array_sha256(value) for key, value in per_step.items()},
        "per_task": {key: array_sha256(value) for key, value in per_task.items()},
    }
    passed = all(check["passed"] for check in checks)
    return {
        "label": label,
        "passed": passed,
        "checks": checks,
        "observed": {
            "n_offered": int(offered),
            "deadline_met": deadline_met,
            "completion_offered": float(summary["completion"]),
            "penalty_inclusive_latency_ms_per_offered_task": float(
                summary["avg_latency_ms_per_task"]
            ),
            "n_admitted": None,
            "terminal_rejections_or_unavailability": None,
            "work_conservation": "unavailable_and_nonconserving_by_source_contract",
            "wall_s_excluded_from_repeat_verdict": summary.get("wall_s"),
        },
        "scientific_summary": _scientific_summary(summary),
        "output_sha256": _file_hashes(run_dir),
        "array_sha256": array_hashes,
    }


def _input_identity(
    manifest_path: Path,
    manifest: dict[str, Any],
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    observed = {
        "manifest": sha256_file(manifest_path),
        "actor": sha256_file(actor_path),
        "trace": sha256_file(trace_path),
    }
    expected = {
        "actor": manifest["inputs"]["actor"]["sha256"],
        "trace": manifest["inputs"]["trace"]["sha256"],
    }
    return {
        "passed": observed["actor"] == expected["actor"] and observed["trace"] == expected["trace"],
        "sha256": observed,
        "expected_sha256": expected,
    }


def build_smoke_report(
    manifest_path: Path,
    legacy_run_1: Path,
    legacy_run_2: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    steps = manifest["scope"]["legacy_smoke_steps"]
    run_1 = validate_legacy_run(
        legacy_run_1, manifest, label="legacy_smoke_run_1", expected_steps=steps
    )
    run_2 = validate_legacy_run(
        legacy_run_2, manifest, label="legacy_smoke_run_2", expected_steps=steps
    )
    identity = _input_identity(manifest_path, manifest, actor_path, trace_path)
    scientific_equal = run_1["scientific_summary"] == run_2["scientific_summary"]
    arrays_equal = run_1["array_sha256"] == run_2["array_sha256"]
    passed = (
        identity["passed"]
        and run_1["passed"]
        and run_2["passed"]
        and scientific_equal
        and arrays_equal
    )
    return {
        "schema_version": "traffictwin.e1-semantics-pair-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "phase": "legacy_smoke_repeat",
        "passed": passed,
        "decision": "legacy_smoke_repeat_pass" if passed else "stop_before_legacy_full",
        "input_identity": identity,
        "runs": [run_1, run_2],
        "repeat": {
            "scientific_summary_identical": scientific_equal,
            "instrumentation_arrays_identical": arrays_equal,
        },
        "semantic_boundary": {
            "legacy_conservation_verdict": "unavailable_and_nonconserving_by_source_contract",
            "legacy_zero_rejection_counters_interpreted_as_observed_zero": False,
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
            "measured_outcome": "simulated deadline attainment",
        },
    }


def build_full_pair_report(
    manifest_path: Path,
    legacy_full_run: Path,
    physical_run: Path,
    physical_validation_path: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    legacy = validate_legacy_run(
        legacy_full_run,
        manifest,
        label="legacy_full_run_1",
        expected_steps=manifest["scope"]["full_steps"],
    )
    identity = _input_identity(manifest_path, manifest, actor_path, trace_path)
    physical_validation = json.loads(physical_validation_path.read_text(encoding="utf-8"))
    physical_summary = json.loads((physical_run / "summary.json").read_text(encoding="utf-8"))

    expected_physical_hashes = manifest["execution"]["physical_reused_output_sha256"]
    observed_physical_hashes = {
        name: sha256_file(physical_run / name) for name in expected_physical_hashes
    }
    physical_hashes_pass = observed_physical_hashes == expected_physical_hashes
    physical_validation_hash = sha256_file(physical_validation_path)
    physical_validation_pass = (
        physical_validation_hash == manifest["arms"]["physical"]["e0_validation_sha256"]
        and physical_validation.get("passed") is True
        and physical_validation.get("decision") == "full_corrected_reference_pass"
    )

    physical_array_hashes = physical_validation["runs"][0]["array_sha256"]["per_task"]
    paired_inputs_equal = {
        "task_active": legacy["array_sha256"]["per_task"]["task_active"]
        == physical_array_hashes["task_active"],
        "task_type": legacy["array_sha256"]["per_task"]["task_type"]
        == physical_array_hashes["task_type"],
        "offered_count": legacy["observed"]["n_offered"] == int(physical_summary["n_offered"]),
    }

    physical_completion = float(physical_summary["completion"])
    legacy_completion = float(legacy["scientific_summary"]["completion"])
    physical_latency = float(physical_summary["avg_latency_ms_per_task"])
    legacy_latency = float(legacy["scientific_summary"]["avg_latency_ms_per_task"])
    passed = (
        identity["passed"]
        and legacy["passed"]
        and physical_hashes_pass
        and physical_validation_pass
        and all(paired_inputs_equal.values())
    )
    return {
        "schema_version": "traffictwin.e1-semantics-pair-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "phase": "full_2p5_pair",
        "passed": passed,
        "decision": (
            "bounded_e1_2p5_pair_valid_with_legacy_conservation_unavailable"
            if passed
            else "stop_e1_pair_invalid"
        ),
        "input_identity": identity,
        "legacy_run": legacy,
        "physical_e0_reuse": {
            "validation_passed": physical_validation_pass,
            "validation_sha256": physical_validation_hash,
            "output_hashes_passed": physical_hashes_pass,
            "output_sha256": observed_physical_hashes,
            "n_offered": int(physical_summary["n_offered"]),
            "n_admitted": int(physical_summary["n_admitted"]),
            "deadline_met": int(
                round(physical_summary["completion"] * physical_summary["n_offered"])
            ),
            "completion_offered": physical_completion,
            "completion_admitted": float(physical_summary["completion_admitted"]),
            "penalty_inclusive_latency_ms_per_offered_task": physical_latency,
            "work_conservation": "passed_in_e0_validation",
        },
        "paired_input_equality": paired_inputs_equal,
        "paired_metrics_physical_minus_legacy": {
            "completion_offered_absolute": physical_completion - legacy_completion,
            "completion_offered_percentage_points": 100.0
            * (physical_completion - legacy_completion),
            "penalty_inclusive_latency_ms_per_offered_task": physical_latency - legacy_latency,
            "completion_admitted": None,
            "rejection_fraction": None,
            "reason_null_metrics": (
                "The pinned legacy snapshot/clamp path does not emit admitted "
                "identities or terminal rejection outcomes."
            ),
        },
        "interpretation_limits": {
            "cap_effect_estimated": False,
            "multi_seed_inference_supported": False,
            "legacy_conservation_verdict": "unavailable_and_nonconserving_by_source_contract",
            "legacy_zero_rejection_counters_interpreted_as_observed_zero": False,
            "randy_reported_0_6943_reproduced": False,
        },
        "semantic_boundary": {
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
            "measured_outcome": "simulated deadline attainment",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--legacy-smoke-run-1", type=Path)
    parser.add_argument("--legacy-smoke-run-2", type=Path)
    parser.add_argument("--legacy-full-run", type=Path)
    parser.add_argument("--physical-run", type=Path)
    parser.add_argument("--physical-validation", type=Path)
    args = parser.parse_args()

    if args.phase == "smoke":
        if args.legacy_smoke_run_1 is None or args.legacy_smoke_run_2 is None:
            parser.error("smoke phase requires both --legacy-smoke-run-* paths")
        report = build_smoke_report(
            args.manifest,
            args.legacy_smoke_run_1,
            args.legacy_smoke_run_2,
            args.actor,
            args.trace,
        )
    else:
        required = (args.legacy_full_run, args.physical_run, args.physical_validation)
        if any(path is None for path in required):
            parser.error(
                "full phase requires --legacy-full-run, --physical-run and --physical-validation"
            )
        report = build_full_pair_report(
            args.manifest,
            args.legacy_full_run,
            args.physical_run,
            args.physical_validation,
            args.actor,
            args.trace,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

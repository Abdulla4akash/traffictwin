#!/usr/bin/env python3
"""Validate and compare the three seed-0 E1 waiting-room cap points."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(name: str, passed: bool, observed: object = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed}


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _direct_point(path: Path, label: str) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    return {
        "label": label,
        "validation_path": path,
        "validation_sha256": sha256_file(path),
        "report": report,
        "legacy": report.get("legacy_run", {}),
        "physical": report.get("physical_run", {}),
        "reuse_checks": [],
    }


def _reused_point(path: Path, reuse_path: Path, label: str) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    reuse_report = json.loads(reuse_path.read_text(encoding="utf-8"))
    reuse = report.get("physical_e0_reuse", {})
    reuse_sha = sha256_file(reuse_path)
    runs = reuse_report.get("runs", [])
    physical = runs[0] if len(runs) == 1 else {}
    wrapper_hashes = reuse.get("output_sha256", {})
    validated_hashes = physical.get("output_sha256", {})
    checks = [
        _check("reuse_validation_hash_matches", reuse.get("validation_sha256") == reuse_sha),
        _check("reuse_validation_passed", reuse_report.get("passed") is True),
        _check("reuse_contains_one_run", len(runs) == 1, len(runs)),
        _check("reused_physical_run_passed", physical.get("passed") is True),
        _check(
            "reused_output_hashes_match_wrapper",
            bool(wrapper_hashes)
            and all(
                validated_hashes.get(name) == digest for name, digest in wrapper_hashes.items()
            ),
            {
                "wrapper_keys": sorted(wrapper_hashes),
                "validation_extra_keys": sorted(set(validated_hashes) - set(wrapper_hashes)),
            },
        ),
    ]
    return {
        "label": label,
        "validation_path": path,
        "validation_sha256": sha256_file(path),
        "report": report,
        "legacy": report.get("legacy_run", {}),
        "physical": physical,
        "reuse_validation_path": reuse_path,
        "reuse_validation_sha256": reuse_sha,
        "reuse_checks": checks,
    }


def _physical_point(summary: dict[str, Any]) -> dict[str, Any]:
    offered = float(summary["n_offered"])
    admitted = float(summary["n_admitted"])
    rejected = offered - admitted
    return {
        "rsu_max_concurrent": int(summary["rsu_max_concurrent"]),
        "completion_offered": float(summary["completion"]),
        "completion_admitted": float(summary["completion_admitted"]),
        "penalty_inclusive_latency_ms_per_offered_task": float(summary["avg_latency_ms_per_task"]),
        "latency_ms_per_admitted_task": float(summary["avg_latency_admitted_ms"]),
        "n_offered": offered,
        "n_admitted": admitted,
        "n_rejected": rejected,
        "rejection_fraction": rejected / offered,
        "local_mqd_rejected": float(summary["local_mqd_rejected"]),
        "v2v_mqd_rejected": float(summary["v2v_mqd_rejected"]),
        "v2i_cap_rejected": float(summary["v2i_cap_rejected"]),
        "v2i_unavailable": float(summary["v2i_unavailable"]),
        "v2v_unavailable": float(summary["v2v_unavailable"]),
    }


def _legacy_point(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "rsu_max_concurrent": int(summary["rsu_max_concurrent"]),
        "completion_offered": float(summary["completion"]),
        "penalty_inclusive_latency_ms_per_offered_task": float(summary["avg_latency_ms_per_task"]),
        "n_offered": float(summary["n_offered"]),
        "admitted_and_rejection_metrics": None,
    }


def _delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, Any]:
    return {
        "cap": high["rsu_max_concurrent"] - low["rsu_max_concurrent"],
        "completion_offered_absolute": high["completion_offered"] - low["completion_offered"],
        "completion_offered_percentage_points": 100.0
        * (high["completion_offered"] - low["completion_offered"]),
        "completion_admitted_absolute": high["completion_admitted"] - low["completion_admitted"],
        "completion_admitted_percentage_points": 100.0
        * (high["completion_admitted"] - low["completion_admitted"]),
        "penalty_inclusive_latency_ms_per_offered_task": high[
            "penalty_inclusive_latency_ms_per_offered_task"
        ]
        - low["penalty_inclusive_latency_ms_per_offered_task"],
        "latency_ms_per_admitted_task": high["latency_ms_per_admitted_task"]
        - low["latency_ms_per_admitted_task"],
        "n_admitted": high["n_admitted"] - low["n_admitted"],
        "n_rejected": high["n_rejected"] - low["n_rejected"],
        "rejection_fraction": high["rejection_fraction"] - low["rejection_fraction"],
        "v2i_cap_rejected": high["v2i_cap_rejected"] - low["v2i_cap_rejected"],
    }


def _legacy_delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, Any]:
    return {
        "cap": high["rsu_max_concurrent"] - low["rsu_max_concurrent"],
        "completion_offered_absolute": high["completion_offered"] - low["completion_offered"],
        "completion_offered_percentage_points": 100.0
        * (high["completion_offered"] - low["completion_offered"]),
        "penalty_inclusive_latency_ms_per_offered_task": high[
            "penalty_inclusive_latency_ms_per_offered_task"
        ]
        - low["penalty_inclusive_latency_ms_per_offered_task"],
        "admitted_and_rejection_metrics": None,
        "reason_null_metrics": (
            "The pinned legacy path does not emit admitted identities or terminal "
            "rejection outcomes."
        ),
    }


def _report_header(
    points: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    passed: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "traffictwin.e1-cap-sweep-comparison.v1",
        "passed": passed,
        "decision": (
            "three_cap_seed0_descriptive_sweep_valid"
            if passed
            else "stop_three_cap_sweep_comparison_invalid"
        ),
        "inputs": {
            point["label"]: {
                "validation": point["validation_path"].as_posix(),
                "validation_sha256": point["validation_sha256"],
                **(
                    {
                        "physical_reuse_validation": point["reuse_validation_path"].as_posix(),
                        "physical_reuse_validation_sha256": point["reuse_validation_sha256"],
                    }
                    if "reuse_validation_path" in point
                    else {}
                ),
            }
            for point in points
        },
        "checks": checks,
        "interpretation_limits": {
            "descriptive_only": True,
            "single_evaluator_seed": 0,
            "single_fleet_seed": 0,
            "cap_points": 3,
            "multi_seed_inference_supported": False,
            "formal_tie_claim_supported": False,
            "controller_comparison_supported": False,
            "legacy_conservation_available": False,
            "confirmed_native_physical_completion": False,
            "measured_outcome": "simulated deadline attainment",
        },
    }


def build_sweep_comparison(
    low_path: Path,
    middle_path: Path,
    middle_reuse_path: Path,
    high_path: Path,
) -> dict[str, Any]:
    points = [
        _direct_point(low_path, "0p75"),
        _reused_point(middle_path, middle_reuse_path, "2p5"),
        _direct_point(high_path, "40x"),
    ]
    checks: list[dict[str, Any]] = []
    for point in points:
        label = point["label"]
        report = point["report"]
        checks.extend(
            [
                _check(f"{label}_validation_passed", report.get("passed") is True),
                _check(
                    f"{label}_input_identity_passed",
                    report.get("input_identity", {}).get("passed") is True,
                ),
                _check(f"{label}_legacy_passed", point["legacy"].get("passed") is True),
                _check(f"{label}_physical_passed", point["physical"].get("passed") is True),
                _check(
                    f"{label}_within_pair_inputs_equal",
                    bool(report.get("paired_input_equality"))
                    and all(report["paired_input_equality"].values()),
                ),
            ]
        )
        checks.extend(
            {
                **check,
                "name": f"{label}_{check['name']}",
            }
            for check in point["reuse_checks"]
        )

    physical_runs = [point["physical"] for point in points]
    legacy_runs = [point["legacy"] for point in points]
    records_present = all(
        "scientific_summary" in run and "array_sha256" in run for run in physical_runs + legacy_runs
    )
    checks.append(_check("required_run_records_present", records_present))
    if not records_present:
        return _report_header(points, checks, False)

    identities = [point["report"]["input_identity"]["sha256"] for point in points]
    physical_summaries = [run["scientific_summary"] for run in physical_runs]
    legacy_summaries = [run["scientific_summary"] for run in legacy_runs]
    common_fields = (
        "T",
        "maxN",
        "actor",
        "trace",
        "fleet",
        "fleet_seed",
        "lambda_arrival",
        "rsu_service_mult",
        "rsu_lb",
        "rsu_backhaul_ms",
        "k8s_scale",
        "substep_queue",
        "veh_queue_mode",
        "rsu_cap_mode",
    )
    checks.extend(
        [
            _check("actor_hash_equal", len({identity["actor"] for identity in identities}) == 1),
            _check("trace_hash_equal", len({identity["trace"] for identity in identities}) == 1),
            _check(
                "physical_common_configuration_equal",
                all(
                    summary.get(field) == physical_summaries[0].get(field)
                    for summary in physical_summaries[1:]
                    for field in common_fields
                ),
            ),
            _check(
                "physical_offered_count_equal",
                len({summary["n_offered"] for summary in physical_summaries}) == 1,
            ),
            _check(
                "physical_task_active_equal",
                len({run["array_sha256"]["per_task"]["task_active"] for run in physical_runs}) == 1,
            ),
            _check(
                "physical_task_type_equal",
                len({run["array_sha256"]["per_task"]["task_type"] for run in physical_runs}) == 1,
            ),
            _check(
                "legacy_task_active_equal",
                len({run["array_sha256"]["per_task"]["task_active"] for run in legacy_runs}) == 1,
            ),
            _check(
                "legacy_task_type_equal",
                len({run["array_sha256"]["per_task"]["task_type"] for run in legacy_runs}) == 1,
            ),
        ]
    )
    physical_points = [_physical_point(summary) for summary in physical_summaries]
    legacy_points = [_legacy_point(summary) for summary in legacy_summaries]
    caps = [point["rsu_max_concurrent"] for point in physical_points]
    checks.append(_check("caps_strictly_increasing", caps == sorted(set(caps)), caps))
    numeric_fields = (
        "completion_offered",
        "completion_admitted",
        "penalty_inclusive_latency_ms_per_offered_task",
        "latency_ms_per_admitted_task",
        "n_offered",
        "n_admitted",
        "n_rejected",
        "rejection_fraction",
        "v2i_cap_rejected",
    )
    checks.append(
        _check(
            "physical_comparison_values_finite",
            all(
                _finite_number(point[field])
                for point in physical_points
                for field in numeric_fields
            ),
        )
    )
    passed = all(check["passed"] for check in checks)
    report = _report_header(points, checks, passed)
    if passed:
        physical_by_label = {
            point["label"]: physical_points[index] for index, point in enumerate(points)
        }
        legacy_by_label = {
            point["label"]: legacy_points[index] for index, point in enumerate(points)
        }
        report["physical_points"] = physical_by_label
        report["legacy_points"] = legacy_by_label
        report["physical_higher_cap_minus_lower_cap"] = {
            "0p75_to_2p5": _delta(physical_by_label["2p5"], physical_by_label["0p75"]),
            "2p5_to_40x": _delta(physical_by_label["40x"], physical_by_label["2p5"]),
            "0p75_to_40x": _delta(physical_by_label["40x"], physical_by_label["0p75"]),
        }
        report["legacy_higher_cap_minus_lower_cap"] = {
            "0p75_to_2p5": _legacy_delta(legacy_by_label["2p5"], legacy_by_label["0p75"]),
            "2p5_to_40x": _legacy_delta(legacy_by_label["40x"], legacy_by_label["2p5"]),
            "0p75_to_40x": _legacy_delta(legacy_by_label["40x"], legacy_by_label["0p75"]),
        }
        completions = [point["completion_offered"] for point in physical_points]
        report["descriptive_trend_checks"] = {
            "physical_admissions_nondecreasing_with_cap": all(
                physical_points[index]["n_admitted"] <= physical_points[index + 1]["n_admitted"]
                for index in range(len(physical_points) - 1)
            ),
            "physical_cap_rejections_nonincreasing_with_cap": all(
                physical_points[index]["v2i_cap_rejected"]
                >= physical_points[index + 1]["v2i_cap_rejected"]
                for index in range(len(physical_points) - 1)
            ),
            "physical_penalty_latency_nondecreasing_with_cap": all(
                physical_points[index]["penalty_inclusive_latency_ms_per_offered_task"]
                <= physical_points[index + 1]["penalty_inclusive_latency_ms_per_offered_task"]
                for index in range(len(physical_points) - 1)
            ),
            "physical_offered_completion_range_absolute": max(completions) - min(completions),
            "physical_offered_completion_range_percentage_points": 100.0
            * (max(completions) - min(completions)),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-validation", type=Path, required=True)
    parser.add_argument("--middle-validation", type=Path, required=True)
    parser.add_argument("--middle-physical-validation", type=Path, required=True)
    parser.add_argument("--high-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_sweep_comparison(
        args.low_validation,
        args.middle_validation,
        args.middle_physical_validation,
        args.high_validation,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

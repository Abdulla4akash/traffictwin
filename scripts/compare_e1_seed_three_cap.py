#!/usr/bin/env python3
"""Validate one E1 fleet seed across all three waiting-room cap points."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

CAP_LABELS = ("0p75", "2p5", "40x")
EXPECTED_CAPS = {"0p75": 1866, "2p5": 6220, "40x": 99520}
REJECTION_FIELDS = (
    "v2i_gate_rejected",
    "v2i_cap_rejected",
    "local_mqd_rejected",
    "v2v_mqd_rejected",
    "v2i_unavailable",
    "v2v_unavailable",
)

FLEET_SEED_DIRECTORY = re.compile(r"fleet_seed_(\d+)$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _check(name: str, passed: bool, observed: object = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed}


def _finite_nonnegative(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _fleet_seed(seed_root: Path) -> int:
    match = FLEET_SEED_DIRECTORY.fullmatch(seed_root.name)
    if match is None:
        raise ValueError(f"seed root must be named fleet_seed_<integer>: {seed_root}")
    return int(match.group(1))


def _profile(values: list[float]) -> str:
    first, middle, last = values
    if first > middle and middle == last:
        return "decrease_then_plateau"
    if first < middle and middle == last:
        return "increase_then_plateau"
    if first == middle == last:
        return "constant"
    if first <= middle <= last:
        return "nondecreasing"
    if first >= middle >= last:
        return "nonincreasing"
    return "nonmonotonic"


def _trends(points: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ordered = [points[label] for label in CAP_LABELS]
    offered_deadline = [float(point["deadline_attainment_offered"]) for point in ordered]
    admitted_deadline = [float(point["deadline_attainment_admitted"]) for point in ordered]
    return {
        "admissions_nondecreasing": all(
            ordered[index]["admitted_tasks"] <= ordered[index + 1]["admitted_tasks"]
            for index in range(2)
        ),
        "total_rejections_nonincreasing": all(
            ordered[index]["rejected_or_unavailable_tasks"]
            >= ordered[index + 1]["rejected_or_unavailable_tasks"]
            for index in range(2)
        ),
        "v2i_cap_rejections_nonincreasing": all(
            ordered[index]["rejection_counts"]["v2i_cap_rejected"]
            >= ordered[index + 1]["rejection_counts"]["v2i_cap_rejected"]
            for index in range(2)
        ),
        "offered_deadline_attainment_profile": _profile(offered_deadline),
        "offered_deadline_attainment_range_absolute": max(offered_deadline) - min(offered_deadline),
        "admitted_deadline_attainment_profile": _profile(admitted_deadline),
        "penalty_inclusive_offered_latency_nondecreasing": all(
            ordered[index]["penalty_inclusive_latency_ms_per_offered_task"]
            <= ordered[index + 1]["penalty_inclusive_latency_ms_per_offered_task"]
            for index in range(2)
        ),
        "admitted_latency_nondecreasing": all(
            ordered[index]["latency_ms_per_admitted_task"]
            <= ordered[index + 1]["latency_ms_per_admitted_task"]
            for index in range(2)
        ),
    }


def _point(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "rsu_max_concurrent": int(metrics["rsu_max_concurrent"]),
        "offered_tasks": int(metrics["offered_tasks"]),
        "admitted_tasks": int(metrics["admitted_tasks"]),
        "rejected_or_unavailable_tasks": int(metrics["rejected_or_unavailable_tasks"]),
        "rejection_fraction_offered": float(metrics["rejection_fraction_offered"]),
        "rejection_counts": {
            field: int(metrics["rejection_counts"][field]) for field in REJECTION_FIELDS
        },
        "deadline_met_tasks": int(metrics["deadline_met_tasks"]),
        "deadline_attainment_offered": float(metrics["deadline_attainment_offered"]),
        "deadline_attainment_admitted": float(metrics["deadline_attainment_admitted"]),
        "penalty_inclusive_latency_ms_per_offered_task": float(
            metrics["penalty_inclusive_latency_ms_per_offered_task"]
        ),
        "latency_ms_per_admitted_task": float(metrics["latency_ms_per_admitted_task"]),
        "latency_ms_per_deadline_met_task": float(metrics["latency_ms_per_deadline_met_task"]),
        "admitted_latency_tail_ms": metrics["admitted_latency_tail_ms"],
        "deadline_met_latency_tail_ms": metrics["deadline_met_latency_tail_ms"],
        "work_ms": metrics["work_ms"],
        "evaluator_wall_s": float(metrics["wall_s"]),
    }


def _seed0_point(point: dict[str, Any]) -> dict[str, Any]:
    return {
        "admitted_tasks": int(point["n_admitted"]),
        "rejected_or_unavailable_tasks": int(point["n_rejected"]),
        "rejection_counts": {"v2i_cap_rejected": int(point["v2i_cap_rejected"])},
        "deadline_attainment_offered": float(point["completion_offered"]),
        "deadline_attainment_admitted": float(point["completion_admitted"]),
        "penalty_inclusive_latency_ms_per_offered_task": float(
            point["penalty_inclusive_latency_ms_per_offered_task"]
        ),
        "latency_ms_per_admitted_task": float(point["latency_ms_per_admitted_task"]),
    }


def _delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    return {
        "admitted_tasks": float(high["admitted_tasks"] - low["admitted_tasks"]),
        "rejected_or_unavailable_tasks": float(
            high["rejected_or_unavailable_tasks"] - low["rejected_or_unavailable_tasks"]
        ),
        "v2i_cap_rejected": float(
            high["rejection_counts"]["v2i_cap_rejected"]
            - low["rejection_counts"]["v2i_cap_rejected"]
        ),
        "deadline_attainment_offered": high["deadline_attainment_offered"]
        - low["deadline_attainment_offered"],
        "deadline_attainment_admitted": high["deadline_attainment_admitted"]
        - low["deadline_attainment_admitted"],
        "penalty_inclusive_latency_ms_per_offered_task": high[
            "penalty_inclusive_latency_ms_per_offered_task"
        ]
        - low["penalty_inclusive_latency_ms_per_offered_task"],
        "latency_ms_per_admitted_task": high["latency_ms_per_admitted_task"]
        - low["latency_ms_per_admitted_task"],
    }


def build_seed_comparison(
    manifest_path: Path,
    seed_root: Path,
    seed0_comparison_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    seed0 = json.loads(seed0_comparison_path.read_text(encoding="utf-8"))
    fleet_seed = _fleet_seed(seed_root)
    checks: list[dict[str, Any]] = [
        _check(
            "selected_backend_is_frozen_macos_cpu",
            manifest.get("backend_decision", {}).get("selected_backend")
            == "macos_arm64_cpu_jax_0_4_30",
        ),
        _check(
            "campaign_execution_allowed",
            manifest["backend_decision"]["campaign_execution_allowed"],
        ),
        _check("seed0_comparison_passed", seed0.get("passed") is True),
    ]
    manifest_caps = {
        item["label"]: int(item["resolved_tasks_per_rsu"]) for item in manifest["cap_grid"]
    }
    checks.append(_check("cap_grid_exact", manifest_caps == EXPECTED_CAPS, manifest_caps))
    logical_seed_root = f"{manifest['output']['logical_locator']}/{seed_root.name}"

    points: dict[str, dict[str, Any]] = {}
    sources: dict[str, Any] = {}
    active_hashes: set[str] = set()
    type_hashes: set[str] = set()
    offered_counts: set[int] = set()
    for label in CAP_LABELS:
        cell = seed_root / f"cap_{label}"
        metrics_path = cell / "cell_metrics.json"
        validation_path = cell / "full_validation.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        point = _point(metrics)
        points[label] = point
        sources[label] = {
            "metrics_locator": f"{logical_seed_root}/cap_{label}/cell_metrics.json",
            "metrics_sha256": sha256_file(metrics_path),
            "validation_locator": f"{logical_seed_root}/cap_{label}/full_validation.json",
            "validation_sha256": sha256_file(validation_path),
        }
        run = validation.get("run", {})
        checks.extend(
            [
                _check(f"{label}_full_validation_passed", validation.get("passed") is True),
                _check(
                    f"{label}_all_full_checks_passed",
                    bool(run.get("checks")) and all(item["passed"] for item in run["checks"]),
                ),
                _check(
                    f"{label}_cap_exact",
                    point["rsu_max_concurrent"] == EXPECTED_CAPS[label],
                    point["rsu_max_concurrent"],
                ),
                _check(
                    f"{label}_task_accounting",
                    point["offered_tasks"]
                    == point["admitted_tasks"] + point["rejected_or_unavailable_tasks"],
                ),
                _check(
                    f"{label}_rejection_reconciliation",
                    point["rejected_or_unavailable_tasks"]
                    == sum(point["rejection_counts"].values()),
                ),
                _check(
                    f"{label}_v2i_work_conservation",
                    point["work_ms"]["v2i_offered"]
                    == point["work_ms"]["v2i_admitted"]
                    + point["work_ms"]["v2i_rejected_or_unavailable"],
                ),
                _check(
                    f"{label}_vehicle_work_conservation",
                    point["work_ms"]["veh_offered"]
                    == point["work_ms"]["veh_admitted"] + point["work_ms"]["veh_rejected"],
                ),
                _check(
                    f"{label}_comparison_values_finite_nonnegative",
                    all(
                        _finite_nonnegative(value)
                        for value in (
                            point["offered_tasks"],
                            point["admitted_tasks"],
                            point["rejected_or_unavailable_tasks"],
                            point["deadline_attainment_offered"],
                            point["deadline_attainment_admitted"],
                            point["penalty_inclusive_latency_ms_per_offered_task"],
                            point["latency_ms_per_admitted_task"],
                        )
                    ),
                ),
            ]
        )
        offered_counts.add(point["offered_tasks"])
        active_hashes.add(run["array_sha256"]["per_task"]["task_active"])
        type_hashes.add(run["array_sha256"]["per_task"]["task_type"])

    checks.extend(
        [
            _check("offered_count_identical_across_caps", len(offered_counts) == 1),
            _check("task_active_identical_across_caps", len(active_hashes) == 1),
            _check("task_type_identical_across_caps", len(type_hashes) == 1),
        ]
    )
    seed_trends = _trends(points)
    seed0_points = {label: _seed0_point(seed0["physical_points"][label]) for label in CAP_LABELS}
    seed0_trends = _trends(seed0_points)
    comparable_fields = (
        "admissions_nondecreasing",
        "total_rejections_nonincreasing",
        "v2i_cap_rejections_nonincreasing",
        "offered_deadline_attainment_profile",
        "admitted_deadline_attainment_profile",
        "penalty_inclusive_offered_latency_nondecreasing",
        "admitted_latency_nondecreasing",
    )
    pattern_checks = {
        field: seed_trends[field] == seed0_trends[field] for field in comparable_fields
    }
    passed = all(item["passed"] for item in checks)
    validation_record = {
        "schema_version": "traffictwin.e1-within-seed-three-cap-validation.v1",
        "manifest_sha256": sha256_file(manifest_path),
        "fleet_seed": fleet_seed,
        "passed": passed,
        "decision": (
            "within_seed_three_cap_comparison_valid"
            if passed
            else "stop_invalid_within_seed_comparison"
        ),
        "checks": checks,
        "sources": sources,
        "task_stream_identity": {
            "task_active_sha256": next(iter(active_hashes)) if len(active_hashes) == 1 else None,
            "task_type_sha256": next(iter(type_hashes)) if len(type_hashes) == 1 else None,
        },
    }
    comparison = {
        "schema_version": "traffictwin.e1-within-seed-three-cap-comparison.v1",
        "manifest_sha256": sha256_file(manifest_path),
        "validation_passed": passed,
        "replication_unit": "fleet_seed",
        "fleet_seed": fleet_seed,
        "evaluator_seed": 0,
        "points": points,
        "higher_cap_minus_lower_cap": {
            "2p5_minus_0p75": _delta(points["2p5"], points["0p75"]),
            "40x_minus_2p5": _delta(points["40x"], points["2p5"]),
            "40x_minus_0p75": _delta(points["40x"], points["0p75"]),
        },
        "seed_descriptive_trends": seed_trends,
        "seed0_reference": {
            "comparison_sha256": sha256_file(seed0_comparison_path),
            "descriptive_trends": seed0_trends,
        },
        "qualitative_pattern_comparison": {
            "field_matches": pattern_checks,
            "all_predeclared_qualitative_fields_match": all(pattern_checks.values()),
        },
        "interpretation_limits": {
            "descriptive_single_fleet_seed_only": True,
            "five_draw_inference_calculated": False,
            "individual_tasks_used_as_independent_replicates": False,
            "formal_tie_equivalence_or_noninferiority_supported": False,
            "causality_beyond_controlled_simulator_intervention_supported": False,
            "confirmed_native_physical_completion_or_result_return": False,
            "waiting_room_cap_is_compute_power": False,
            "randy_reported_0_6943_reproduced": False,
        },
    }
    return validation_record, comparison


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--seed-root", required=True, type=Path)
    parser.add_argument("--seed0-comparison", required=True, type=Path)
    parser.add_argument("--validation-output", required=True, type=Path)
    parser.add_argument("--comparison-output", required=True, type=Path)
    args = parser.parse_args()
    validation, comparison = build_seed_comparison(
        args.manifest, args.seed_root, args.seed0_comparison
    )
    _write_json(args.validation_output, validation)
    _write_json(args.comparison_output, comparison)
    print(
        json.dumps(
            {
                "passed": validation["passed"],
                "qualitative_pattern_matches_seed0": comparison["qualitative_pattern_comparison"][
                    "all_predeclared_qualitative_fields_match"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate and analyse the five-draw physical E1 waiting-room campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np

try:
    from scripts.run_e1_multidraw_physical_campaign import _physical_manifest_view
    from scripts.validate_e0_smoke import validate_run
except ModuleNotFoundError:  # direct script execution
    from run_e1_multidraw_physical_campaign import (  # type: ignore[no-redef,import-not-found]
        _physical_manifest_view,
    )
    from validate_e0_smoke import validate_run  # type: ignore[no-redef,import-not-found]


T_CRITICAL_TWO_SIDED_95_DF4 = 2.7764451051977987
REJECTION_FIELDS = (
    "v2i_gate_rejected",
    "v2i_cap_rejected",
    "local_mqd_rejected",
    "v2v_mqd_rejected",
    "v2i_unavailable",
    "v2v_unavailable",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:  # noqa: ANN401
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _percentiles(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {"p50": None, "p95": None, "p99": None}
    result = np.percentile(values.astype(np.float64, copy=False), [50, 95, 99])
    return {"p50": float(result[0]), "p95": float(result[1]), "p99": float(result[2])}


def _metrics(run_dir: Path, validation: dict[str, Any]) -> dict[str, Any]:
    summary = validation["scientific_summary"]
    with np.load(run_dir / "per_task.npz", allow_pickle=False) as source:
        active = source["task_active"].astype(bool)
        outcome = source["task_outcome"]
        latency = source["task_lat_ms"]
        admitted = active & ((outcome == 1) | (outcome == 2))
        deadline_met = active & (outcome == 1)
        admitted_tails = _percentiles(latency[admitted])
        deadline_met_tails = _percentiles(latency[deadline_met])
    offered = int(summary["n_offered"])
    admitted_count = int(summary["n_admitted"])
    rejection_counts = {field: int(summary[field]) for field in REJECTION_FIELDS}
    rejected = sum(rejection_counts.values())
    return {
        "rsu_max_concurrent": int(summary["rsu_max_concurrent"]),
        "offered_tasks": offered,
        "admitted_tasks": admitted_count,
        "rejected_or_unavailable_tasks": rejected,
        "rejection_fraction_offered": rejected / offered,
        "rejection_counts": rejection_counts,
        "deadline_met_tasks": int(validation["observed"]["deadline_met"]),
        "deadline_attainment_offered": float(summary["completion"]),
        "deadline_attainment_admitted": float(summary["completion_admitted"]),
        "penalty_inclusive_latency_ms_per_offered_task": float(summary["avg_latency_ms_per_task"]),
        "latency_ms_per_admitted_task": float(summary["avg_latency_admitted_ms"]),
        "latency_ms_per_deadline_met_task": float(summary["avg_latency_met_ms"]),
        "admitted_latency_tail_ms": admitted_tails,
        "deadline_met_latency_tail_ms": deadline_met_tails,
        "task_class_deadline_attainment": {
            "t1": float(summary["t1_completion"]),
            "t2": float(summary["t2_completion"]),
            "t3": float(summary["t3_completion"]),
        },
        "decision_shares": {
            "local": float(summary["p_local"]),
            "v2i": float(summary["p_v2i"]),
            "v2v": float(summary["p_v2v"]),
        },
        "work_ms": summary["work_ms"],
        "wall_s": float(validation["observed"]["wall_s_excluded_from_repeat_verdict"]),
    }


def _file_evidence(run_dir: Path) -> dict[str, dict[str, int | str]]:
    return {
        path.name: {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(run_dir.iterdir())
        if path.is_file()
    }


def _paired_summary(values: list[float]) -> dict[str, Any]:
    count = len(values)
    if count != 5:
        raise ValueError(f"the predeclared paired analysis requires five draws, observed {count}")
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values)
    standard_error = standard_deviation / math.sqrt(count)
    half_width = T_CRITICAL_TWO_SIDED_95_DF4 * standard_error
    lower = mean - half_width
    upper = mean + half_width
    excludes_zero = lower > 0.0 or upper < 0.0
    return {
        "raw_paired_differences": values,
        "n_fleet_draws": count,
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "confidence_interval": {
            "method": "two-sided Student t interval",
            "confidence_level": 0.95,
            "degrees_of_freedom": 4,
            "critical_value": T_CRITICAL_TWO_SIDED_95_DF4,
            "lower": lower,
            "upper": upper,
            "excludes_zero": excludes_zero,
        },
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "decision": (
            "evidence_of_directional_difference_within_five_draw_bounded_study"
            if excludes_zero
            else "inconclusive_at_this_replication_size"
        ),
        "formal_equivalence_or_noninferiority_claim_supported": False,
    }


def _delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    return {
        "deadline_attainment_offered": high["deadline_attainment_offered"]
        - low["deadline_attainment_offered"],
        "deadline_attainment_admitted": high["deadline_attainment_admitted"]
        - low["deadline_attainment_admitted"],
        "admitted_tasks": float(high["admitted_tasks"] - low["admitted_tasks"]),
        "rejected_or_unavailable_tasks": float(
            high["rejected_or_unavailable_tasks"] - low["rejected_or_unavailable_tasks"]
        ),
        "v2i_cap_rejected": float(
            high["rejection_counts"]["v2i_cap_rejected"]
            - low["rejection_counts"]["v2i_cap_rejected"]
        ),
        "penalty_inclusive_latency_ms_per_offered_task": high[
            "penalty_inclusive_latency_ms_per_offered_task"
        ]
        - low["penalty_inclusive_latency_ms_per_offered_task"],
        "latency_ms_per_admitted_task": high["latency_ms_per_admitted_task"]
        - low["latency_ms_per_admitted_task"],
    }


def build_records(
    manifest_path: Path,
    campaign_root: Path,
    seed0_roots: dict[str, Path],
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    caps = [item["label"] for item in manifest["cap_grid"]]
    rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    campaign_checks: list[dict[str, Any]] = []

    for fleet_seed in manifest["seeds"]["fleet_seeds"]:
        seed_validations: list[dict[str, Any]] = []
        for cap_label in caps:
            if fleet_seed == 0:
                run_dir = seed0_roots[cap_label]
            else:
                run_dir = (
                    campaign_root
                    / f"fleet_seed_{fleet_seed}"
                    / f"cap_{cap_label}"
                    / "full"
                    / "run_1"
                )
            view = _physical_manifest_view(
                manifest,
                fleet_seed=fleet_seed,
                cap_label=cap_label,
                max_steps=manifest["scope"]["full_steps"],
            )
            validation = validate_run(run_dir, view, f"seed_{fleet_seed}_cap_{cap_label}")
            seed_validations.append(validation)
            validation_rows.append(
                {
                    "fleet_seed": fleet_seed,
                    "cap_label": cap_label,
                    "passed": validation["passed"],
                    "checks": validation["checks"],
                    "observed": validation["observed"],
                    "array_sha256": validation["array_sha256"],
                    "output_evidence": _file_evidence(run_dir),
                    "raw_output_locator": (
                        manifest["reused_seed0_artifacts"][cap_label]["locator"]
                        if fleet_seed == 0
                        else (
                            f"{manifest['output']['logical_locator']}/fleet_seed_{fleet_seed}/"
                            f"cap_{cap_label}/full/run_1"
                        )
                    ),
                }
            )
            rows.append(
                {
                    "fleet_seed": fleet_seed,
                    "evaluator_seed": manifest["seeds"]["evaluator_seed"],
                    "cap_label": cap_label,
                    **_metrics(run_dir, validation),
                }
            )
        offered = {item["observed"]["n_offered"] for item in seed_validations}
        active = {item["array_sha256"]["per_task"]["task_active"] for item in seed_validations}
        task_type = {item["array_sha256"]["per_task"]["task_type"] for item in seed_validations}
        campaign_checks.extend(
            [
                {
                    "name": f"seed_{fleet_seed}_all_cap_runs_valid",
                    "passed": all(item["passed"] for item in seed_validations),
                },
                {
                    "name": f"seed_{fleet_seed}_offered_count_identical_across_caps",
                    "passed": len(offered) == 1,
                },
                {
                    "name": f"seed_{fleet_seed}_task_active_identical_across_caps",
                    "passed": len(active) == 1,
                },
                {
                    "name": f"seed_{fleet_seed}_task_type_identical_across_caps",
                    "passed": len(task_type) == 1,
                },
            ]
        )

    by_seed = {
        seed: {row["cap_label"]: row for row in rows if row["fleet_seed"] == seed}
        for seed in manifest["seeds"]["fleet_seeds"]
    }
    per_seed_differences = {
        str(seed): {
            "40x_minus_0p75": _delta(points["40x"], points["0p75"]),
            "2p5_minus_0p75": _delta(points["2p5"], points["0p75"]),
            "40x_minus_2p5": _delta(points["40x"], points["2p5"]),
        }
        for seed, points in by_seed.items()
    }
    primary_values = [
        per_seed_differences[str(seed)]["40x_minus_0p75"]["deadline_attainment_offered"]
        for seed in manifest["seeds"]["fleet_seeds"]
    ]
    secondary_values = {
        contrast: [
            per_seed_differences[str(seed)][contrast]["deadline_attainment_offered"]
            for seed in manifest["seeds"]["fleet_seeds"]
        ]
        for contrast in ("2p5_minus_0p75", "40x_minus_2p5")
    }
    passed = all(check["passed"] for check in campaign_checks)
    validation_record = {
        "schema_version": "traffictwin.e1-multidraw-physical-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": sha256_file(manifest_path),
        "passed": passed,
        "decision": "campaign_valid" if passed else "campaign_invalid_stop",
        "checks": campaign_checks,
        "runs": validation_rows,
        "conservation_scope": "tasks and milliseconds of V2I and vehicle service work",
        "semantic_boundary": {
            "measured_outcome": "simulated deadline attainment",
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
        },
    }
    comparison = {
        "schema_version": "traffictwin.e1-multidraw-physical-comparison.v1",
        "manifest_id": manifest["manifest_id"],
        "validation_passed": passed,
        "replication_unit": "fleet_seed",
        "evaluator_seed_fixed": manifest["seeds"]["evaluator_seed"],
        "rows": rows,
        "per_seed_higher_cap_minus_lower_cap": per_seed_differences,
        "primary_estimand": {
            "contrast": "deadline_attainment_offered_40x_minus_0p75",
            "positive_value_favours": "40x",
            **_paired_summary(primary_values),
        },
        "secondary_deadline_attainment_contrasts": {
            contrast: _paired_summary(values) for contrast, values in secondary_values.items()
        },
        "interpretation_limits": {
            "tasks_used_as_independent_replicates": False,
            "formal_equivalence_or_noninferiority_claim_supported": False,
            "causality_beyond_controlled_simulator_intervention_supported": False,
            "real_world_optimality_supported": False,
            "ordinary_traffic_control_included": False,
            "uk2030_fleet_validated_real_world_model": False,
            "randy_reported_0_6943_reproduced": False,
        },
    }
    return validation_record, comparison


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--campaign-root", required=True, type=Path)
    parser.add_argument("--seed0-0p75", required=True, type=Path)
    parser.add_argument("--seed0-2p5", required=True, type=Path)
    parser.add_argument("--seed0-40x", required=True, type=Path)
    parser.add_argument("--validation-output", required=True, type=Path)
    parser.add_argument("--comparison-output", required=True, type=Path)
    args = parser.parse_args()
    validation, comparison = build_records(
        args.manifest,
        args.campaign_root,
        {"0p75": args.seed0_0p75, "2p5": args.seed0_2p5, "40x": args.seed0_40x},
    )
    _write_json(args.validation_output, validation)
    _write_json(args.comparison_output, comparison)
    print(
        json.dumps(
            {
                "passed": validation["passed"],
                "decision": comparison["primary_estimand"]["decision"],
            },
            indent=2,
        )
    )
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

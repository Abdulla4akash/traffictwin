#!/usr/bin/env python3
"""Compare two validated E1 cap points without recomputing evaluator metrics."""

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


def _physical_run(
    report: dict[str, Any],
    *,
    reuse_validation: dict[str, Any] | None,
    reuse_validation_sha256: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    if "physical_run" in report:
        checks.append(_check("physical_run_direct", True, True))
        return report["physical_run"], checks

    reuse = report.get("physical_e0_reuse")
    checks.append(_check("physical_run_is_documented_reuse", reuse is not None, reuse is not None))
    checks.append(
        _check(
            "reuse_validation_supplied",
            reuse_validation is not None and reuse_validation_sha256 is not None,
            reuse_validation_sha256,
        )
    )
    if reuse is None or reuse_validation is None or reuse_validation_sha256 is None:
        return {}, checks

    checks.extend(
        [
            _check(
                "reuse_validation_hash_matches",
                reuse.get("validation_sha256") == reuse_validation_sha256,
                {
                    "declared": reuse.get("validation_sha256"),
                    "observed": reuse_validation_sha256,
                },
            ),
            _check("reuse_validation_passed", reuse_validation.get("passed") is True),
            _check("reuse_contains_one_run", len(reuse_validation.get("runs", [])) == 1),
        ]
    )
    if len(reuse_validation.get("runs", [])) != 1:
        return {}, checks
    run = reuse_validation["runs"][0]
    checks.append(_check("reused_physical_run_passed", run.get("passed") is True))
    wrapper_hashes = reuse.get("output_sha256", {})
    validation_hashes = run.get("output_sha256", {})
    checks.append(
        _check(
            "reused_output_hashes_match_wrapper",
            bool(wrapper_hashes)
            and all(
                validation_hashes.get(name) == digest for name, digest in wrapper_hashes.items()
            ),
            {
                "wrapper_keys": sorted(wrapper_hashes),
                "validation_extra_keys": sorted(set(validation_hashes) - set(wrapper_hashes)),
            },
        )
    )
    return run, checks


def _delta(low: float, high: float) -> float:
    return float(low) - float(high)


def _point(summary: dict[str, Any]) -> dict[str, Any]:
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


def build_comparison(
    low_report_path: Path,
    high_report_path: Path,
    high_reuse_validation_path: Path,
) -> dict[str, Any]:
    low_report = json.loads(low_report_path.read_text(encoding="utf-8"))
    high_report = json.loads(high_report_path.read_text(encoding="utf-8"))
    high_reuse = json.loads(high_reuse_validation_path.read_text(encoding="utf-8"))
    high_reuse_sha = sha256_file(high_reuse_validation_path)

    low_physical, low_reuse_checks = _physical_run(
        low_report,
        reuse_validation=None,
        reuse_validation_sha256=None,
    )
    high_physical, high_reuse_checks = _physical_run(
        high_report,
        reuse_validation=high_reuse,
        reuse_validation_sha256=high_reuse_sha,
    )
    checks = [
        _check("low_validation_passed", low_report.get("passed") is True),
        _check("high_validation_passed", high_report.get("passed") is True),
        *low_reuse_checks,
        *high_reuse_checks,
    ]

    low_identity = low_report.get("input_identity", {})
    high_identity = high_report.get("input_identity", {})
    low_legacy = low_report.get("legacy_run", {})
    high_legacy = high_report.get("legacy_run", {})
    if low_physical and high_physical and low_legacy and high_legacy:
        low_ps = low_physical["scientific_summary"]
        high_ps = high_physical["scientific_summary"]
        low_ls = low_legacy["scientific_summary"]
        high_ls = high_legacy["scientific_summary"]
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
                _check("low_input_identity_passed", low_identity.get("passed") is True),
                _check("high_input_identity_passed", high_identity.get("passed") is True),
                _check(
                    "actor_hash_equal",
                    low_identity.get("sha256", {}).get("actor")
                    == high_identity.get("sha256", {}).get("actor"),
                ),
                _check(
                    "trace_hash_equal",
                    low_identity.get("sha256", {}).get("trace")
                    == high_identity.get("sha256", {}).get("trace"),
                ),
                _check(
                    "physical_common_configuration_equal",
                    all(low_ps.get(field) == high_ps.get(field) for field in common_fields),
                    {field: [low_ps.get(field), high_ps.get(field)] for field in common_fields},
                ),
                _check(
                    "physical_offered_count_equal",
                    low_ps.get("n_offered") == high_ps.get("n_offered"),
                ),
                _check(
                    "physical_task_active_equal",
                    low_physical["array_sha256"]["per_task"]["task_active"]
                    == high_physical["array_sha256"]["per_task"]["task_active"],
                ),
                _check(
                    "physical_task_type_equal",
                    low_physical["array_sha256"]["per_task"]["task_type"]
                    == high_physical["array_sha256"]["per_task"]["task_type"],
                ),
                _check(
                    "legacy_task_active_equal",
                    low_legacy["array_sha256"]["per_task"]["task_active"]
                    == high_legacy["array_sha256"]["per_task"]["task_active"],
                ),
                _check(
                    "legacy_task_type_equal",
                    low_legacy["array_sha256"]["per_task"]["task_type"]
                    == high_legacy["array_sha256"]["per_task"]["task_type"],
                ),
                _check(
                    "low_cap_less_than_high_cap",
                    low_ps.get("rsu_max_concurrent", math.inf)
                    < high_ps.get("rsu_max_concurrent", -math.inf),
                    [low_ps.get("rsu_max_concurrent"), high_ps.get("rsu_max_concurrent")],
                ),
            ]
        )
        numeric_fields = (
            "n_offered",
            "n_admitted",
            "completion",
            "completion_admitted",
            "avg_latency_ms_per_task",
            "avg_latency_admitted_ms",
            "local_mqd_rejected",
            "v2v_mqd_rejected",
            "v2i_cap_rejected",
            "v2i_unavailable",
            "v2v_unavailable",
        )
        checks.append(
            _check(
                "physical_comparison_values_finite",
                all(
                    _finite_number(summary.get(field))
                    for summary in (low_ps, high_ps)
                    for field in numeric_fields
                ),
            )
        )
    else:
        low_ps = high_ps = low_ls = high_ls = {}
        checks.append(_check("required_run_records_present", False))

    passed = all(check["passed"] for check in checks)
    report: dict[str, Any] = {
        "schema_version": "traffictwin.e1-cap-point-comparison.v1",
        "passed": passed,
        "decision": (
            "two_cap_seed0_descriptive_comparison_valid"
            if passed
            else "stop_cap_comparison_invalid"
        ),
        "inputs": {
            "low_validation": {
                "path": low_report_path.as_posix(),
                "sha256": sha256_file(low_report_path),
            },
            "high_validation": {
                "path": high_report_path.as_posix(),
                "sha256": sha256_file(high_report_path),
            },
            "high_physical_reuse_validation": {
                "path": high_reuse_validation_path.as_posix(),
                "sha256": high_reuse_sha,
            },
        },
        "checks": checks,
        "interpretation_limits": {
            "descriptive_only": True,
            "single_evaluator_seed": 0,
            "single_fleet_seed": 0,
            "cap_points": 2,
            "multi_seed_inference_supported": False,
            "controller_comparison_supported": False,
            "legacy_conservation_available": False,
            "confirmed_native_physical_completion": False,
            "measured_outcome": "simulated deadline attainment",
        },
    }
    if passed:
        low_point = _point(low_ps)
        high_point = _point(high_ps)
        report["physical_points"] = {"low_cap": low_point, "high_cap": high_point}
        report["physical_low_minus_high"] = {
            "completion_offered_absolute": _delta(
                low_point["completion_offered"], high_point["completion_offered"]
            ),
            "completion_offered_percentage_points": 100.0
            * _delta(low_point["completion_offered"], high_point["completion_offered"]),
            "completion_admitted_absolute": _delta(
                low_point["completion_admitted"], high_point["completion_admitted"]
            ),
            "completion_admitted_percentage_points": 100.0
            * _delta(low_point["completion_admitted"], high_point["completion_admitted"]),
            "penalty_inclusive_latency_ms_per_offered_task": _delta(
                low_point["penalty_inclusive_latency_ms_per_offered_task"],
                high_point["penalty_inclusive_latency_ms_per_offered_task"],
            ),
            "latency_ms_per_admitted_task": _delta(
                low_point["latency_ms_per_admitted_task"],
                high_point["latency_ms_per_admitted_task"],
            ),
            "n_admitted": _delta(low_point["n_admitted"], high_point["n_admitted"]),
            "n_rejected": _delta(low_point["n_rejected"], high_point["n_rejected"]),
            "rejection_fraction": _delta(
                low_point["rejection_fraction"], high_point["rejection_fraction"]
            ),
            "v2i_cap_rejected": _delta(
                low_point["v2i_cap_rejected"], high_point["v2i_cap_rejected"]
            ),
        }
        report["legacy_low_minus_high"] = {
            "completion_offered_absolute": _delta(low_ls["completion"], high_ls["completion"]),
            "completion_offered_percentage_points": 100.0
            * _delta(low_ls["completion"], high_ls["completion"]),
            "penalty_inclusive_latency_ms_per_offered_task": _delta(
                low_ls["avg_latency_ms_per_task"], high_ls["avg_latency_ms_per_task"]
            ),
            "admitted_and_rejection_metrics": None,
            "reason_null_metrics": (
                "The pinned legacy path does not emit admitted identities or terminal "
                "rejection outcomes."
            ),
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--low-validation", type=Path, required=True)
    parser.add_argument("--high-validation", type=Path, required=True)
    parser.add_argument("--high-physical-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_comparison(
        args.low_validation,
        args.high_validation,
        args.high_physical_validation,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "decision": report["decision"]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

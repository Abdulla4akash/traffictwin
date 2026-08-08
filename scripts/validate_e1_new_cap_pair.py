#!/usr/bin/env python3
"""Validate an E1 cap pair where both legacy and physical arms are new runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.validate_e0_smoke import validate_run as validate_e0_physical_run
    from scripts.validate_e1_semantics_pair import _input_identity, validate_legacy_run
except ModuleNotFoundError:  # direct `python scripts/validate_...py` execution
    from validate_e0_smoke import validate_run as validate_e0_physical_run
    from validate_e1_semantics_pair import _input_identity, validate_legacy_run


def _physical_manifest_view(manifest: dict[str, Any], expected_steps: int) -> dict[str, Any]:
    """Translate the E1 common contract into the E0 physical-validator view."""

    controlled = manifest["controlled_configuration"]
    physical = manifest["arms"]["physical"]
    return {
        "manifest_id": manifest["manifest_id"],
        "scope": {"max_steps": expected_steps},
        "inputs": manifest["inputs"],
        "configuration": {
            "fleet_seed": controlled["fleet_seed"],
            "fleet": controlled["fleet"],
            "arrival_lambda": controlled["arrival_lambda"],
            "cap": controlled["cap"],
            "compute": controlled["compute"],
            "placement": controlled["placement"],
            "rsu_admission": physical["rsu_cap_mode"],
            "substep_queue": physical["substep_queue"],
            "vehicle_queue": physical["vehicle_queue_effective"],
        },
    }


def validate_physical_run(
    run_dir: Path,
    manifest: dict[str, Any],
    *,
    label: str,
    expected_steps: int,
) -> dict[str, Any]:
    return validate_e0_physical_run(
        run_dir,
        _physical_manifest_view(manifest, expected_steps),
        label,
    )


def _repeat_comparison(run_1: dict[str, Any], run_2: dict[str, Any]) -> dict[str, bool]:
    return {
        "scientific_summary_identical": (
            run_1["scientific_summary"] == run_2["scientific_summary"]
        ),
        "instrumentation_arrays_identical": (run_1["array_sha256"] == run_2["array_sha256"]),
    }


def _paired_input_equality(legacy: dict[str, Any], physical: dict[str, Any]) -> dict[str, bool]:
    return {
        "offered_count": legacy["observed"]["n_offered"] == physical["observed"]["n_offered"],
        "task_active": legacy["array_sha256"]["per_task"]["task_active"]
        == physical["array_sha256"]["per_task"]["task_active"],
        "task_type": legacy["array_sha256"]["per_task"]["task_type"]
        == physical["array_sha256"]["per_task"]["task_type"],
    }


def build_dual_smoke_report(
    manifest_path: Path,
    legacy_run_1: Path,
    legacy_run_2: Path,
    physical_run_1: Path,
    physical_run_2: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    steps = manifest["scope"]["smoke_steps"]
    legacy_1 = validate_legacy_run(
        legacy_run_1,
        manifest,
        label="legacy_smoke_run_1",
        expected_steps=steps,
    )
    legacy_2 = validate_legacy_run(
        legacy_run_2,
        manifest,
        label="legacy_smoke_run_2",
        expected_steps=steps,
    )
    physical_1 = validate_physical_run(
        physical_run_1,
        manifest,
        label="physical_smoke_run_1",
        expected_steps=steps,
    )
    physical_2 = validate_physical_run(
        physical_run_2,
        manifest,
        label="physical_smoke_run_2",
        expected_steps=steps,
    )
    identity = _input_identity(manifest_path, manifest, actor_path, trace_path)
    legacy_repeat = _repeat_comparison(legacy_1, legacy_2)
    physical_repeat = _repeat_comparison(physical_1, physical_2)
    paired_inputs = _paired_input_equality(legacy_1, physical_1)
    passed = (
        identity["passed"]
        and legacy_1["passed"]
        and legacy_2["passed"]
        and physical_1["passed"]
        and physical_2["passed"]
        and all(legacy_repeat.values())
        and all(physical_repeat.values())
        and all(paired_inputs.values())
    )
    decisions = manifest["validation_decisions"]
    return {
        "schema_version": "traffictwin.e1-new-cap-pair-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "phase": "dual_arm_smoke_repeat",
        "passed": passed,
        "decision": decisions["smoke_pass"] if passed else decisions["stop"],
        "input_identity": identity,
        "legacy_runs": [legacy_1, legacy_2],
        "physical_runs": [physical_1, physical_2],
        "legacy_repeat": legacy_repeat,
        "physical_repeat": physical_repeat,
        "paired_input_equality": paired_inputs,
        "semantic_boundary": {
            "legacy_conservation_verdict": ("unavailable_and_nonconserving_by_source_contract"),
            "physical_conservation_verdict": "checked_per_run",
            "legacy_zero_rejection_counters_interpreted_as_observed_zero": False,
            "confirmed_native_physical_completion": False,
            "confirmed_physical_result_return": False,
            "measured_outcome": "simulated deadline attainment",
        },
    }


def build_new_full_pair_report(
    manifest_path: Path,
    legacy_run: Path,
    physical_run: Path,
    actor_path: Path,
    trace_path: Path,
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    steps = manifest["scope"]["full_steps"]
    legacy = validate_legacy_run(
        legacy_run,
        manifest,
        label="legacy_full_run_1",
        expected_steps=steps,
    )
    physical = validate_physical_run(
        physical_run,
        manifest,
        label="physical_full_run_1",
        expected_steps=steps,
    )
    identity = _input_identity(manifest_path, manifest, actor_path, trace_path)
    paired_inputs = _paired_input_equality(legacy, physical)

    legacy_completion = float(legacy["scientific_summary"]["completion"])
    physical_completion = float(physical["scientific_summary"]["completion"])
    legacy_latency = float(legacy["scientific_summary"]["avg_latency_ms_per_task"])
    physical_latency = float(physical["scientific_summary"]["avg_latency_ms_per_task"])
    passed = (
        identity["passed"]
        and legacy["passed"]
        and physical["passed"]
        and all(paired_inputs.values())
    )
    decisions = manifest["validation_decisions"]
    return {
        "schema_version": "traffictwin.e1-new-cap-pair-validation.v1",
        "manifest_id": manifest["manifest_id"],
        "phase": "new_full_pair",
        "passed": passed,
        "decision": decisions["full_pass"] if passed else decisions["stop"],
        "input_identity": identity,
        "legacy_run": legacy,
        "physical_run": physical,
        "paired_input_equality": paired_inputs,
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
            "single_cap_pair_only": True,
            "multi_seed_inference_supported": False,
            "legacy_conservation_verdict": ("unavailable_and_nonconserving_by_source_contract"),
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
    parser.add_argument("--physical-smoke-run-1", type=Path)
    parser.add_argument("--physical-smoke-run-2", type=Path)
    parser.add_argument("--legacy-full-run", type=Path)
    parser.add_argument("--physical-full-run", type=Path)
    args = parser.parse_args()

    if args.phase == "smoke":
        required = (
            args.legacy_smoke_run_1,
            args.legacy_smoke_run_2,
            args.physical_smoke_run_1,
            args.physical_smoke_run_2,
        )
        if any(path is None for path in required):
            parser.error("smoke phase requires all four arm/repeat run paths")
        report = build_dual_smoke_report(
            args.manifest,
            args.legacy_smoke_run_1,
            args.legacy_smoke_run_2,
            args.physical_smoke_run_1,
            args.physical_smoke_run_2,
            args.actor,
            args.trace,
        )
    else:
        if args.legacy_full_run is None or args.physical_full_run is None:
            parser.error("full phase requires both full arm run paths")
        report = build_new_full_pair_report(
            args.manifest,
            args.legacy_full_run,
            args.physical_full_run,
            args.actor,
            args.trace,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"passed": report["passed"], "decision": report["decision"]},
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

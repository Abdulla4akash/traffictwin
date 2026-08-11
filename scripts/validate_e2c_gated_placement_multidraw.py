#!/usr/bin/env python3
"""Fail-closed validation for the matched E2c gated-placement campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import numpy as np
from validate_e2_native_placement_pilot import (
    add_check,
    compare_array_sets,
    load_npz,
)
from validate_e2_native_placement_pilot import (
    validate_run as validate_e2_run,
)
from validate_e2b_placement_admission_factorial import (
    validate_run as validate_e2b_run,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_name(cell: dict[str, Any]) -> str:
    return f"{int(cell['cell_index']):02d}_seed_{int(cell['fleet_seed'])}_{cell['arm']}"


def cell_root(manifest: dict[str, Any], cell: dict[str, Any]) -> Path:
    return Path(manifest["outputs"]["raw_root"]) / "cells" / cell_name(cell)


def manifest_for_cell(manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    view = copy.deepcopy(manifest)
    view["design"]["fleet_seed"] = int(cell["fleet_seed"])
    return view


def arm_for_cell(manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, str]:
    arm_id = str(cell["arm"])
    return {"id": arm_id, "rsu_lb": manifest["arms"][arm_id]["rsu_lb"]}


def format_command(
    manifest: dict[str, Any],
    cell: dict[str, Any],
    run_dir: Path,
    *,
    max_steps: int,
) -> list[str]:
    values = {
        "MAX_STEPS": str(max_steps),
        "FLEET_SEED": str(int(cell["fleet_seed"])),
        "ARM": str(cell["arm"]),
        "RUN_DIR": str(run_dir.resolve()),
    }
    return [str(part).format(**values) for part in manifest["command_template"]]


def verify_checksum_ledger(run_dir: Path) -> dict[str, Any]:
    ledger = run_dir / "checksums.sha256"
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    if not ledger.is_file():
        return {"pass": False, "errors": ["checksums.sha256 missing"], "entries": []}
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            errors.append(f"malformed checksum line: {line!r}")
            continue
        expected, relative = line.split("  ", 1)
        path = run_dir / relative
        observed = sha256(path) if path.is_file() else None
        entries.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "observed_sha256": observed,
                "pass": observed == expected,
            }
        )
        if observed != expected:
            errors.append(f"checksum mismatch: {relative}")
    expected_members = {
        "command.json",
        "runner_status.json",
        "stdout.log",
        "stderr.log",
        "summary.json",
        "per_step.npz",
        "per_task.npz",
    }
    observed_members = {entry["path"] for entry in entries}
    if observed_members != expected_members:
        errors.append(
            "checksum member mismatch: "
            f"observed={sorted(observed_members)} expected={sorted(expected_members)}"
        )
    return {"pass": not errors, "errors": errors, "entries": entries}


def _add_e2c_run_checks(
    result: dict[str, Any],
    *,
    manifest: dict[str, Any],
    cell: dict[str, Any],
    run_dir: Path,
    max_steps: int,
) -> None:
    checks = result["checks"]
    command = result.get("command", {})
    expected_command = format_command(manifest, cell, run_dir, max_steps=max_steps)
    add_check(
        checks,
        "e2c_exact_command",
        command.get("argv") == expected_command,
        command.get("argv"),
        expected_command,
    )
    add_check(
        checks,
        "e2c_environment_variables",
        command.get("environment_variables") == manifest["environment"]["variables"],
        command.get("environment_variables"),
        manifest["environment"]["variables"],
    )
    add_check(
        checks,
        "e2c_cell_identity",
        command.get("cell") == cell,
        command.get("cell"),
        cell,
    )
    ledger = verify_checksum_ledger(run_dir)
    add_check(checks, "e2c_checksum_ledger", ledger["pass"], ledger, "all exact")

    if (run_dir / "per_task.npz").is_file() and (run_dir / "per_step.npz").is_file():
        task = load_npz(run_dir / "per_task.npz")
        step = load_npz(run_dir / "per_step.npz")
        active = task["task_active"].astype(bool)
        admitted = task["task_v2i_admitted"].astype(bool)
        execution = task["task_execution_rsu"]
        outcome = task["task_outcome"]
        forwarded = task["task_forwarded"].astype(bool)
        unexplained_negative = {
            "active_task_latency": int((task["task_lat_ms"][active] < 0).sum()),
            "vehicle_queue": int((step["veh_queue_ms"] < 0).sum()),
            "rsu_busy": int((step["rsu_busy_ms"] < 0).sum()),
            "rsu_load": int((step["rsu_load"] < 0).sum()),
            "forwarding_latency": int((task["task_forwarding_latency_ms"] < 0).sum()),
        }
        add_check(
            checks,
            "e2c_no_unexplained_negative_values",
            all(value == 0 for value in unexplained_negative.values()),
            unexplained_negative,
            dict.fromkeys(unexplained_negative, 0),
        )
        rejected_or_unavailable = np.isin(outcome, (3, 4, 7))
        add_check(
            checks,
            "e2c_rejected_unavailable_not_executed_or_forwarded",
            bool(
                np.all(execution[rejected_or_unavailable] == -1)
                and not np.any(forwarded[rejected_or_unavailable])
                and not np.any(admitted[rejected_or_unavailable])
            ),
            {
                "executed": int((execution[rejected_or_unavailable] >= 0).sum()),
                "forwarded": int(forwarded[rejected_or_unavailable].sum()),
                "admitted": int(admitted[rejected_or_unavailable].sum()),
            },
            {"executed": 0, "forwarded": 0, "admitted": 0},
        )

    result["checksum_verification"] = ledger
    result["status"] = "passed" if all(check["pass"] for check in checks) else "failed"


def validate_run(
    run_dir: Path,
    *,
    manifest: dict[str, Any],
    cell: dict[str, Any],
    expected_steps: int,
) -> dict[str, Any]:
    view = manifest_for_cell(manifest, cell)
    arm = arm_for_cell(manifest, cell)
    if cell["arm"] == "ingress_dla":
        result = validate_e2b_run(run_dir, arm=arm, manifest=view, expected_steps=expected_steps)
    elif cell["arm"] == "dla":
        result = validate_e2_run(run_dir, arm=arm, manifest=view, expected_steps=expected_steps)
    else:
        raise ValueError(f"unauthorised E2c arm: {cell['arm']}")
    if "checks" in result:
        _add_e2c_run_checks(
            result,
            manifest=manifest,
            cell=cell,
            run_dir=run_dir,
            max_steps=expected_steps,
        )
    result["cell"] = cell
    return cast(dict[str, Any], result)


def compare_repeats(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_summary = copy.deepcopy(left["summary"])
    right_summary = copy.deepcopy(right["summary"])
    left_summary.pop("wall_s", None)
    right_summary.pop("wall_s", None)
    left_dir = Path(left["run_dir"])
    right_dir = Path(right["run_dir"])
    per_step = compare_array_sets(
        load_npz(left_dir / "per_step.npz"), load_npz(right_dir / "per_step.npz")
    )
    per_task = compare_array_sets(
        load_npz(left_dir / "per_task.npz"), load_npz(right_dir / "per_task.npz")
    )
    passed = left_summary == right_summary and per_step["pass"] and per_task["pass"]
    return {
        "pass": passed,
        "scientific_summary_exact_excluding_wall_s": left_summary == right_summary,
        "per_step": per_step,
        "per_task": per_task,
    }


def compare_cross_arm(
    ingress_run: dict[str, Any], dla_run: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    ingress_dir = Path(ingress_run["run_dir"])
    dla_dir = Path(dla_run["run_dir"])
    ingress_step = load_npz(ingress_dir / "per_step.npz")
    dla_step = load_npz(dla_dir / "per_step.npz")
    ingress_task = load_npz(ingress_dir / "per_task.npz")
    dla_task = load_npz(dla_dir / "per_task.npz")
    exact_fields = {
        "offered_count": ingress_run["summary"]["n_offered"] == dla_run["summary"]["n_offered"],
        "task_active": np.array_equal(ingress_task["task_active"], dla_task["task_active"]),
        "task_type": np.array_equal(ingress_task["task_type"], dla_task["task_type"]),
        "fleet_tier": np.array_equal(ingress_step["slot_tier"], dla_step["slot_tier"]),
        "fleet_is_ev": np.array_equal(ingress_step["slot_is_ev"], dla_step["slot_is_ev"]),
        "vehicle_action": np.array_equal(ingress_step["veh_action"], dla_step["veh_action"]),
        "actor_action_count_local": np.array_equal(ingress_step["n_local"], dla_step["n_local"]),
        "actor_action_count_v2i": np.array_equal(ingress_step["n_v2i"], dla_step["n_v2i"]),
        "actor_action_count_v2v": np.array_equal(ingress_step["n_v2v"], dla_step["n_v2v"]),
    }
    left_logits = ingress_step["veh_actor_logits"]
    right_logits = dla_step["veh_actor_logits"]
    schema_equal = (
        left_logits.shape == right_logits.shape
        and left_logits.dtype == right_logits.dtype == np.float32
    )
    if schema_equal:
        delta = np.abs(left_logits.astype(np.float64) - right_logits.astype(np.float64))
        max_abs = float(delta.max(initial=0.0))
        finite = bool(np.isfinite(delta).all())
    else:
        max_abs = float("inf")
        finite = False
    tolerance = float(manifest["cross_arm_contract"]["logit_diagnostic"]["absolute_tolerance"])
    logit_pass = finite and max_abs <= tolerance
    return {
        "pass": all(exact_fields.values()) and logit_pass,
        "exact_fields": exact_fields,
        "actor_logit_diagnostic": {
            "pass": logit_pass,
            "shape_dtype_equal": schema_equal,
            "byte_exact": schema_equal and left_logits.tobytes() == right_logits.tobytes(),
            "maximum_absolute_difference": max_abs,
            "absolute_tolerance": tolerance,
            "relative_tolerance": 0.0,
            "ingress_dla_sha256": hashlib.sha256(left_logits.tobytes()).hexdigest(),
            "dla_sha256": hashlib.sha256(right_logits.tobytes()).hexdigest(),
            "interpretation": manifest["cross_arm_contract"]["logit_diagnostic"]["interpretation"],
        },
    }


def validate_cell(manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    root = cell_root(manifest, cell)
    smoke_runs = [
        validate_run(
            root / "smoke" / f"run_{repeat}",
            manifest=manifest,
            cell=cell,
            expected_steps=int(manifest["design"]["smoke_steps"]),
        )
        for repeat in (1, 2)
    ]
    repeat = None
    if all(run["status"] == "passed" for run in smoke_runs):
        repeat = compare_repeats(smoke_runs[0], smoke_runs[1])
    full = validate_run(
        root / "full" / "run_1",
        manifest=manifest,
        cell=cell,
        expected_steps=int(manifest["design"]["steps"]),
    )
    passed = (
        all(run["status"] == "passed" for run in smoke_runs)
        and repeat is not None
        and repeat["pass"]
        and full["status"] == "passed"
    )
    return {
        "schema_version": "e2c_cell_validation_v1",
        "status": "passed" if passed else "failed",
        "cell": cell,
        "smoke_runs": smoke_runs,
        "smoke_repeat": repeat,
        "full_run": full,
    }


def validate_pair(manifest: dict[str, Any], fleet_seed: int) -> dict[str, Any]:
    cells = [cell for cell in manifest["full_cell_order"] if int(cell["fleet_seed"]) == fleet_seed]
    if [cell["arm"] for cell in cells] != ["ingress_dla", "dla"]:
        raise ValueError(f"invalid pair order for fleet seed {fleet_seed}")
    validations = []
    for cell in cells:
        path = cell_root(manifest, cell) / "cell_validation.json"
        validations.append(json.loads(path.read_text(encoding="utf-8")))
    if any(item.get("status") != "passed" for item in validations):
        return {
            "schema_version": "e2c_pair_validation_v1",
            "status": "failed",
            "fleet_seed": fleet_seed,
            "failure": "one or more cell validations did not pass",
        }
    smoke_identity = compare_cross_arm(
        validations[0]["smoke_runs"][0], validations[1]["smoke_runs"][0], manifest
    )
    full_identity = compare_cross_arm(
        validations[0]["full_run"], validations[1]["full_run"], manifest
    )
    difference = float(
        validations[1]["full_run"]["summary"]["completion"]
        - validations[0]["full_run"]["summary"]["completion"]
    )
    passed = smoke_identity["pass"] and full_identity["pass"]
    return {
        "schema_version": "e2c_pair_validation_v1",
        "status": "passed" if passed else "failed",
        "fleet_seed": fleet_seed,
        "arms": ["ingress_dla", "dla"],
        "smoke_cross_arm_identity": smoke_identity,
        "full_cross_arm_identity": full_identity,
        "offered_deadline_attainment_dla_minus_ingress_dla": difference,
        "task_level_records_treated_as_replicates": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cell-index", required=True, type=int)
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()
    if args.output_json.exists():
        raise SystemExit(f"refusing to overwrite {args.output_json}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cells = {int(cell["cell_index"]): cell for cell in manifest["full_cell_order"]}
    if args.cell_index not in cells:
        raise SystemExit(f"undeclared cell index: {args.cell_index}")
    result = validate_cell(manifest, cells[args.cell_index])
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "output": str(args.output_json)}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

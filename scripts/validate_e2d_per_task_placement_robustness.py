#!/usr/bin/env python3
"""Fail-closed validation for the bounded E2d placement robustness study."""

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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cell_name(cell: dict[str, Any]) -> str:
    return f"{int(cell['cell_index']):02d}_seed_{int(cell['fleet_seed'])}_per_task_dla"


def cell_root(manifest: dict[str, Any], cell: dict[str, Any]) -> Path:
    return Path(manifest["outputs"]["raw_root"]) / "cells" / cell_name(cell)


def replay_name(replay: dict[str, Any]) -> str:
    return f"{int(replay['replay_index']):02d}_seed_{int(replay['fleet_seed'])}_{replay['arm']}"


def replay_root(manifest: dict[str, Any], replay: dict[str, Any]) -> Path:
    return Path(manifest["outputs"]["raw_root"]) / "existing_mode_replays" / replay_name(replay)


def manifest_for_seed(manifest: dict[str, Any], fleet_seed: int) -> dict[str, Any]:
    view = copy.deepcopy(manifest)
    view["design"]["fleet_seed"] = fleet_seed
    return view


def format_command(
    manifest: dict[str, Any],
    run: dict[str, Any],
    run_dir: Path,
    *,
    max_steps: int,
) -> list[str]:
    values = {
        "MAX_STEPS": str(max_steps),
        "FLEET_SEED": str(int(run["fleet_seed"])),
        "ARM": str(run["arm"]),
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
    observed_members = {str(entry["path"]) for entry in entries}
    if observed_members != expected_members:
        errors.append(
            "checksum member mismatch: "
            f"observed={sorted(observed_members)} expected={sorted(expected_members)}"
        )
    return {"pass": not errors, "errors": errors, "entries": entries}


def validate_run(
    run_dir: Path,
    *,
    manifest: dict[str, Any],
    run: dict[str, Any],
    expected_steps: int,
) -> dict[str, Any]:
    arm_id = str(run["arm"])
    if arm_id not in {"ingress_dla", "dla", "per_task_dla"}:
        raise ValueError(f"unauthorised E2d mode: {arm_id}")
    view = manifest_for_seed(manifest, int(run["fleet_seed"]))
    result = validate_e2_run(
        run_dir,
        arm={"id": arm_id, "rsu_lb": arm_id},
        manifest=view,
        expected_steps=expected_steps,
    )
    result["run"] = run
    if "checks" not in result:
        return cast(dict[str, Any], result)

    checks = result["checks"]
    command = result.get("command", {})
    expected_command = format_command(manifest, run, run_dir, max_steps=expected_steps)
    add_check(
        checks,
        "e2d_exact_command",
        command.get("argv") == expected_command,
        command.get("argv"),
        expected_command,
    )
    add_check(
        checks,
        "e2d_environment_variables",
        command.get("environment_variables") == manifest["environment"]["variables"],
        command.get("environment_variables"),
        manifest["environment"]["variables"],
    )
    add_check(
        checks,
        "e2d_run_identity",
        command.get("run") == run,
        command.get("run"),
        run,
    )
    ledger = verify_checksum_ledger(run_dir)
    add_check(checks, "e2d_checksum_ledger", ledger["pass"], ledger, "all exact")

    task = load_npz(run_dir / "per_task.npz")
    step = load_npz(run_dir / "per_step.npz")
    active = task["task_active"].astype(bool)
    ingress = task["task_ingress_rsu"]
    selected = task["task_selected_execution_rsu"]
    execution = task["task_execution_rsu"]
    admitted = task["task_v2i_admitted"].astype(bool)
    forwarded = task["task_forwarded"].astype(bool)
    outcome = task["task_outcome"]
    attempt = ingress >= 0
    rejected_or_unavailable = np.isin(outcome, (3, 4, 7))
    invalid_negative = {
        "active_task_latency": int((task["task_lat_ms"][active] < 0).sum()),
        "vehicle_queue": int((step["veh_queue_ms"] < 0).sum()),
        "rsu_busy": int((step["rsu_busy_ms"] < 0).sum()),
        "rsu_load": int((step["rsu_load"] < 0).sum()),
        "forwarding_latency": int((task["task_forwarding_latency_ms"] < 0).sum()),
    }
    add_check(
        checks,
        "e2d_no_unexplained_negative_values",
        all(value == 0 for value in invalid_negative.values()),
        invalid_negative,
        dict.fromkeys(invalid_negative, 0),
    )
    add_check(
        checks,
        "e2d_selected_target_valid_for_v2i_attempt",
        bool(
            np.all((selected[attempt] >= 0) & (selected[attempt] < int(manifest["design"]["rsus"])))
        ),
        sorted(np.unique(selected[attempt]).tolist()),
        f"RSU indices 0..{int(manifest['design']['rsus']) - 1}",
    )
    add_check(
        checks,
        "e2d_actual_execution_only_for_admitted_v2i",
        bool(
            np.all(execution[admitted] == selected[admitted]) and np.all(execution[~admitted] == -1)
        ),
        {
            "admitted_selected_execution_mismatches": int(
                (execution[admitted] != selected[admitted]).sum()
            ),
            "nonadmitted_execution_count": int((execution[~admitted] >= 0).sum()),
        },
        {"admitted_selected_execution_mismatches": 0, "nonadmitted_execution_count": 0},
    )
    add_check(
        checks,
        "e2d_rejected_unavailable_not_executed_or_forwarded",
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
    expected_forwarded = admitted & (execution != ingress)
    add_check(
        checks,
        "e2d_forwarding_exactly_admitted_execution_away_from_ingress",
        np.array_equal(forwarded, expected_forwarded),
        int((forwarded != expected_forwarded).sum()),
        0,
    )
    add_check(
        checks,
        "e2d_zero_forwarding_latency",
        bool(np.all(task["task_forwarding_latency_ms"] == 0.0)),
        float(task["task_forwarding_latency_ms"].sum(dtype=np.float64)),
        0.0,
    )
    if arm_id == "per_task_dla":
        gate_rejected = outcome == 3
        add_check(
            checks,
            "per_task_dla_gate_reject_retains_selection",
            bool(np.all(selected[gate_rejected] >= 0)),
            sorted(np.unique(selected[gate_rejected]).tolist()),
            "valid selected RSU for every gate rejection",
        )
    result["checksum_verification"] = ledger
    result["status"] = "passed" if all(check["pass"] for check in checks) else "failed"
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


def reference_record(
    manifest: dict[str, Any], fleet_seed: int, arm: str, phase: str
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        manifest["e2c_reuse"]["by_seed"][str(fleet_seed)][arm][phase],
    )


def verify_reference_record(record: dict[str, Any]) -> dict[str, Any]:
    root = Path(record["root"])
    observed = {
        name: sha256(root / name)
        for name in ("summary.json", "per_step.npz", "per_task.npz", "checksums.sha256")
    }
    expected = {
        "summary.json": record["summary_sha256"],
        "per_step.npz": record["per_step_sha256"],
        "per_task.npz": record["per_task_sha256"],
        "checksums.sha256": record["checksums_sha256"],
    }
    return {"pass": observed == expected, "observed": observed, "expected": expected}


def compare_exact_to_reference(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> dict[str, Any]:
    integrity = verify_reference_record(reference)
    reference_root = Path(reference["root"])
    candidate_root = Path(candidate["run_dir"])
    expected_summary = json.loads((reference_root / "summary.json").read_text(encoding="utf-8"))
    observed_summary = copy.deepcopy(candidate["summary"])
    expected_summary.pop("wall_s", None)
    observed_summary.pop("wall_s", None)
    per_step = compare_array_sets(
        load_npz(reference_root / "per_step.npz"),
        load_npz(candidate_root / "per_step.npz"),
    )
    per_task = compare_array_sets(
        load_npz(reference_root / "per_task.npz"),
        load_npz(candidate_root / "per_task.npz"),
    )
    summary_exact = expected_summary == observed_summary
    return {
        "pass": integrity["pass"] and summary_exact and per_step["pass"] and per_task["pass"],
        "reference_integrity": integrity,
        "scientific_summary_exact_excluding_wall_s": summary_exact,
        "per_step": per_step,
        "per_task": per_task,
    }


def compare_identity_to_reference(
    candidate: dict[str, Any],
    reference: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    integrity = verify_reference_record(reference)
    reference_root = Path(reference["root"])
    candidate_root = Path(candidate["run_dir"])
    reference_summary = json.loads((reference_root / "summary.json").read_text(encoding="utf-8"))
    reference_step = load_npz(reference_root / "per_step.npz")
    candidate_step = load_npz(candidate_root / "per_step.npz")
    reference_task = load_npz(reference_root / "per_task.npz")
    candidate_task = load_npz(candidate_root / "per_task.npz")
    exact = {
        "offered_count": reference_summary["n_offered"] == candidate["summary"]["n_offered"],
        "task_active": np.array_equal(reference_task["task_active"], candidate_task["task_active"]),
        "task_type": np.array_equal(reference_task["task_type"], candidate_task["task_type"]),
        "fleet_tier": np.array_equal(reference_step["slot_tier"], candidate_step["slot_tier"]),
        "fleet_is_ev": np.array_equal(reference_step["slot_is_ev"], candidate_step["slot_is_ev"]),
        "vehicle_action": np.array_equal(
            reference_step["veh_action"], candidate_step["veh_action"]
        ),
        "action_count_local": np.array_equal(reference_step["n_local"], candidate_step["n_local"]),
        "action_count_v2i": np.array_equal(reference_step["n_v2i"], candidate_step["n_v2i"]),
        "action_count_v2v": np.array_equal(reference_step["n_v2v"], candidate_step["n_v2v"]),
    }
    left = reference_step["veh_actor_logits"]
    right = candidate_step["veh_actor_logits"]
    schema_equal = left.shape == right.shape and left.dtype == right.dtype == np.float32
    if schema_equal:
        delta = np.abs(left.astype(np.float64) - right.astype(np.float64))
        max_abs = float(delta.max(initial=0.0))
        finite = bool(np.isfinite(delta).all())
    else:
        max_abs = float("inf")
        finite = False
    tolerance = float(manifest["cross_arm_contract"]["logit_diagnostic"]["absolute_tolerance"])
    logit_pass = finite and max_abs <= tolerance
    return {
        "pass": integrity["pass"] and all(exact.values()) and logit_pass,
        "reference_integrity": integrity,
        "exact_fields": exact,
        "actor_logit_diagnostic": {
            "pass": logit_pass,
            "shape_dtype_equal": schema_equal,
            "byte_exact": schema_equal and left.tobytes() == right.tobytes(),
            "maximum_absolute_difference": max_abs,
            "absolute_tolerance": tolerance,
            "relative_tolerance": 0.0,
        },
    }


def validate_cell(manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    root = cell_root(manifest, cell)
    smoke_runs = [
        validate_run(
            root / "smoke" / f"run_{repeat}",
            manifest=manifest,
            run=cell,
            expected_steps=int(manifest["design"]["smoke_steps"]),
        )
        for repeat in (1, 2)
    ]
    repeat = (
        compare_repeats(smoke_runs[0], smoke_runs[1])
        if all(run["status"] == "passed" for run in smoke_runs)
        else None
    )
    full = validate_run(
        root / "full" / "run_1",
        manifest=manifest,
        run=cell,
        expected_steps=int(manifest["design"]["steps"]),
    )
    baseline_smoke = {
        arm: compare_identity_to_reference(
            smoke_runs[0],
            reference_record(manifest, int(cell["fleet_seed"]), arm, "smoke"),
            manifest,
        )
        for arm in ("ingress_dla", "dla")
    }
    baseline_full = {
        arm: compare_identity_to_reference(
            full,
            reference_record(manifest, int(cell["fleet_seed"]), arm, "full"),
            manifest,
        )
        for arm in ("ingress_dla", "dla")
    }
    passed = (
        all(run["status"] == "passed" for run in smoke_runs)
        and repeat is not None
        and repeat["pass"]
        and full["status"] == "passed"
        and all(item["pass"] for item in baseline_smoke.values())
        and all(item["pass"] for item in baseline_full.values())
    )
    return {
        "schema_version": "e2d_cell_validation_v1",
        "status": "passed" if passed else "failed",
        "cell": cell,
        "smoke_runs": smoke_runs,
        "smoke_repeat": repeat,
        "smoke_identity_against_reused_e2c": baseline_smoke,
        "full_run": full,
        "full_identity_against_reused_e2c": baseline_full,
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
        raise SystemExit(f"undeclared E2d cell index: {args.cell_index}")
    result = validate_cell(manifest, cells[args.cell_index])
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "output": str(args.output_json)}))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

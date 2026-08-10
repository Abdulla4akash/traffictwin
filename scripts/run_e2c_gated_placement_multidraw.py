#!/usr/bin/env python3
"""No-overwrite serial runner for one predeclared E2c cell at a time."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from validate_e2c_gated_placement_multidraw import (
    cell_name,
    cell_root,
    compare_cross_arm,
    compare_repeats,
    format_command,
    sha256,
    validate_cell,
    validate_pair,
    validate_run,
)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(  # noqa: S603 - fixed Git executable
        ["/usr/bin/git", "-C", str(repo), *args], text=True
    ).strip()


def write_json_new(path: Path, payload: Any) -> None:  # noqa: ANN401
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in ("jax", "jaxlib", "numpy", "ml_dtypes", "opt_einsum", "scipy")
    }


def resolve_imported_vec_jax(manifest: dict[str, Any]) -> Path:
    entrypoint = Path(manifest["paths"]["imported_vec_jax_entrypoint"])
    environment = {
        **os.environ,
        **manifest["environment"]["variables"],
        "E2C_VEC_IMPORT_ROOT": str(entrypoint.parents[1]),
    }
    code = (
        "import os,sys; from pathlib import Path; "
        "sys.path.insert(0, os.environ['E2C_VEC_IMPORT_ROOT']); "
        "import env.vec_jax as V; print(Path(V.__file__).resolve())"
    )
    resolved = subprocess.check_output(  # noqa: S603 - manifest identity is frozen
        [manifest["environment"]["python_executable"], "-c", code],
        env=environment,
        text=True,
    ).strip()
    return Path(resolved).resolve()


def verify_checksum_ledger(root: Path, ledger: Path) -> int:
    count = 0
    for line in ledger.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"closed evidence checksum mismatch: {path}")
        count += 1
    return count


def verify_closed_prerequisites(manifest: dict[str, Any]) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    for name in ("e1", "e2", "e2b"):
        record = manifest["closed_prerequisites"][name]
        head = git(Path(record["checkout"]), "rev-parse", "HEAD")
        observed[f"{name}_head"] = head
        expected_head = record["final_commit"]
        if head != expected_head:
            raise RuntimeError(f"closed {name.upper()} commit drifted")
        manifest_digest = sha256(Path(record["manifest_path"]))
        observed[f"{name}_manifest_sha256"] = manifest_digest
        if manifest_digest != record["manifest_sha256"]:
            raise RuntimeError(f"closed {name.upper()} manifest drifted")
        if name in ("e2", "e2b"):
            ledger = Path(record["root_checksum_path"])
            ledger_digest = sha256(ledger)
            observed[f"{name}_root_checksum_sha256"] = ledger_digest
            if ledger_digest != record["root_checksum_sha256"]:
                raise RuntimeError(f"closed {name.upper()} root checksum ledger drifted")
            observed[f"{name}_root_checksum_members"] = verify_checksum_ledger(
                Path(record["raw_root"]), ledger
            )
    for evidence in manifest["seed0_reuse"]["supporting_documents"]:
        if sha256(Path(evidence["path"])) != evidence["sha256"]:
            raise RuntimeError(f"seed-0 supporting evidence drifted: {evidence['path']}")
    for arm in ("ingress_dla", "dla"):
        record = manifest["seed0_reuse"][arm]
        root = Path(record["root"])
        for field, filename in (
            ("summary_sha256", "summary.json"),
            ("per_step_sha256", "per_step.npz"),
            ("per_task_sha256", "per_task.npz"),
            ("checksums_sha256", "checksums.sha256"),
            ("command_sha256", "command.json"),
            ("run_validation_sha256", "run_validation.json"),
        ):
            if sha256(root / filename) != record[field]:
                raise RuntimeError(f"seed-0 {arm} {filename} drifted")
    return observed


def active_evaluators() -> list[str]:
    completed = subprocess.run(
        ["/usr/bin/pgrep", "-fl", "eval_sumo_stage1_mc.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def estimated_cell_bytes(manifest: dict[str, Any], arm: str) -> int:
    limits = manifest["compute_and_storage"]
    return int(limits[f"completed_seed0_{arm}_full_bytes"]) + int(
        limits[f"completed_seed0_{arm}_two_smoke_bytes"]
    )


def accepted_full_wall_seconds(
    manifest: dict[str, Any], completed_cells: list[dict[str, Any]]
) -> float:
    total = 0.0
    for cell in completed_cells:
        path = cell_root(manifest, cell) / "full" / "run_1" / "summary.json"
        total += float(json.loads(path.read_text(encoding="utf-8"))["wall_s"])
    return total


def expected_previous_cells(manifest: dict[str, Any], cell_index: int) -> list[dict[str, Any]]:
    return [cell for cell in manifest["full_cell_order"] if int(cell["cell_index"]) < cell_index]


def verify_order_and_prior_gates(
    manifest: dict[str, Any], cell: dict[str, Any]
) -> list[dict[str, Any]]:
    completed = expected_previous_cells(manifest, int(cell["cell_index"]))
    for prior in completed:
        status_path = cell_root(manifest, prior) / "cell_status.json"
        if not status_path.is_file():
            raise RuntimeError(f"prior cell status missing: {status_path}")
        status = json.loads(status_path.read_text(encoding="utf-8"))
        if status.get("status") != "passed":
            raise RuntimeError(f"prior cell did not pass: {cell_name(prior)}")
        if prior["arm"] == "dla":
            pair = (
                Path(manifest["outputs"]["raw_root"])
                / "pairs"
                / f"fleet_seed_{prior['fleet_seed']}"
                / "pair_validation.json"
            )
            if (
                not pair.is_file()
                or json.loads(pair.read_text(encoding="utf-8")).get("status") != "passed"
            ):
                raise RuntimeError(f"prior fleet-seed pair did not pass: {pair}")
    return completed


def initialise_or_verify_campaign_root(
    manifest_path: Path, manifest: dict[str, Any], cell_index: int
) -> None:
    raw_root = Path(manifest["outputs"]["raw_root"])
    snapshot = raw_root / "manifest_snapshot.json"
    sidecar_snapshot = raw_root / "manifest_snapshot.sha256"
    manifest_sha = sha256(manifest_path)
    if cell_index == 1:
        raw_root.mkdir(parents=True, exist_ok=True)
        unexpected = [path.name for path in raw_root.iterdir() if path.name != "independent_review"]
        if unexpected:
            raise RuntimeError(f"new E2c root contains undeclared pre-launch entries: {unexpected}")
        with snapshot.open("xb") as handle:
            handle.write(manifest_path.read_bytes())
        with sidecar_snapshot.open("x", encoding="utf-8") as handle:
            handle.write(f"{manifest_sha}  manifest_snapshot.json\n")
    else:
        if not snapshot.is_file() or not sidecar_snapshot.is_file():
            raise RuntimeError("campaign manifest snapshot is missing")
        if json.loads(snapshot.read_text(encoding="utf-8")) != manifest:
            raise RuntimeError("campaign manifest changed after launch")
        if (
            sidecar_snapshot.read_text(encoding="utf-8").split()[0] != manifest_sha
            or sha256(snapshot) != manifest_sha
        ):
            raise RuntimeError("campaign manifest snapshot hash changed after launch")


def preflight(
    manifest_path: Path, manifest: dict[str, Any], cell: dict[str, Any]
) -> dict[str, Any]:
    import jax

    sidecar = manifest_path.with_suffix(".sha256")
    manifest_sha = sha256(manifest_path)
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[0] != manifest_sha:
        raise RuntimeError("manifest checksum sidecar mismatch")

    cell_index = int(cell["cell_index"])
    root = cell_root(manifest, cell)
    if root.exists():
        raise RuntimeError(f"refusing to overwrite existing E2c cell: {root}")
    completed = verify_order_and_prior_gates(manifest, cell)

    paths = manifest["paths"]
    repositories = manifest["repositories"]
    tt_repo = Path(paths["traffictwin_checkout"])
    vec_repo = Path(paths["vec_env_checkout"])
    tos_repo = Path(paths["tos_data_checkout"])
    imported_vec_jax = resolve_imported_vec_jax(manifest)
    identities = {
        "manifest_sha256": manifest_sha,
        "traffictwin_branch": git(tt_repo, "branch", "--show-current"),
        "traffictwin_commit": git(tt_repo, "rev-parse", "HEAD"),
        "vec_env_commit": git(vec_repo, "rev-parse", "HEAD"),
        "tos_data_commit": git(tos_repo, "rev-parse", "HEAD"),
        "evaluator_sha256": sha256(Path(paths["evaluator"])),
        "vec_jax_sha256": sha256(Path(paths["vec_jax"])),
        "resolved_imported_vec_jax_path": str(imported_vec_jax),
        "resolved_imported_vec_jax_sha256": sha256(imported_vec_jax),
        "actor_sha256": sha256(Path(manifest["inputs"]["actor"]["path"])),
        "trace_sha256": sha256(Path(manifest["inputs"]["trace"]["path"])),
        "platform_system": platform.system(),
        "platform_machine": platform.machine(),
        "python_version": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_executable_sha256": sha256(Path(sys.executable)),
        "packages": package_versions(),
        "backend": jax.default_backend(),
        "devices": [str(device) for device in jax.devices()],
        "jax_enable_x64": bool(jax.config.jax_enable_x64),
    }
    expected = {
        "traffictwin_branch": repositories["traffictwin"]["branch"],
        "vec_env_commit": repositories["vec_env"]["commit"],
        "tos_data_commit": repositories["tos_data"]["commit"],
        "evaluator_sha256": repositories["vec_env"]["evaluator_sha256"],
        "vec_jax_sha256": repositories["vec_env"]["vec_jax_sha256"],
        "resolved_imported_vec_jax_path": str(Path(paths["resolved_imported_vec_jax"]).resolve()),
        "resolved_imported_vec_jax_sha256": repositories["vec_env"][
            "resolved_imported_vec_jax_sha256"
        ],
        "actor_sha256": manifest["inputs"]["actor"]["sha256"],
        "trace_sha256": manifest["inputs"]["trace"]["sha256"],
        "platform_system": manifest["environment"]["platform_system"],
        "platform_machine": manifest["environment"]["platform_machine"],
        "python_version": manifest["environment"]["python_version"],
        "python_executable": str(Path(manifest["environment"]["python_executable"]).resolve()),
        "python_executable_sha256": manifest["environment"]["python_executable_sha256"],
        "packages": manifest["environment"]["packages"],
        "backend": manifest["environment"]["backend"],
        "devices": manifest["environment"]["devices"],
        "jax_enable_x64": manifest["environment"]["jax_enable_x64"],
    }
    mismatches = {
        key: {"observed": identities[key], "expected": value}
        for key, value in expected.items()
        if identities[key] != value
    }
    if mismatches:
        raise RuntimeError(f"E2c identity mismatch: {json.dumps(mismatches, sort_keys=True)}")
    if git(tt_repo, "status", "--short"):
        raise RuntimeError("TrafficTwin E2c checkout is not clean")
    if git(vec_repo, "status", "--short"):
        raise RuntimeError("read-only vec_env E2c checkout is not clean")
    if git(tos_repo, "status", "--short"):
        raise RuntimeError("tos-data checkout is not clean")
    if "github.com/Abdulla4akash/traffictwin" not in git(
        tt_repo, "remote", "get-url", "--push", "origin"
    ):
        raise RuntimeError("TrafficTwin origin is not Abdulla's private mirror")
    evaluator_processes = active_evaluators()
    if evaluator_processes:
        raise RuntimeError(f"another evaluator is active: {evaluator_processes}")

    closed = verify_closed_prerequisites(manifest)
    review_path = Path(manifest["review_gate"]["verdict_path"])
    if not review_path.is_file():
        raise RuntimeError("independent Claude review evidence is missing")
    review = json.loads(review_path.read_text(encoding="utf-8"))
    review_expected = {
        "verdict": "APPROVE",
        "traffictwin_commit": identities["traffictwin_commit"],
        "vec_env_commit": identities["vec_env_commit"],
        "manifest_sha256": manifest_sha,
    }
    review_mismatches = {
        key: {"observed": review.get(key), "expected": value}
        for key, value in review_expected.items()
        if review.get(key) != value
    }
    if review_mismatches:
        raise RuntimeError(
            f"Claude APPROVE mismatch: {json.dumps(review_mismatches, sort_keys=True)}"
        )

    remaining_cells = [
        candidate
        for candidate in manifest["full_cell_order"]
        if int(candidate["cell_index"]) >= cell_index
    ]
    projected_remaining_bytes = sum(
        estimated_cell_bytes(manifest, candidate["arm"]) for candidate in remaining_cells
    )
    free_bytes = shutil.disk_usage(Path(manifest["outputs"]["raw_root"]).parent).free
    storage_required = 2 * projected_remaining_bytes
    if free_bytes < storage_required:
        raise RuntimeError(f"unsafe E2c storage: {free_bytes} free < {storage_required} required")
    actual_wall = accepted_full_wall_seconds(manifest, completed)
    estimate_remaining_wall = sum(
        float(
            manifest["compute_and_storage"][f"completed_seed0_{candidate['arm']}_full_wall_seconds"]
        )
        for candidate in remaining_cells
    )
    wall_limit = float(manifest["compute_and_storage"]["maximum_new_evaluator_wall_seconds"])
    if actual_wall + estimate_remaining_wall > wall_limit:
        raise RuntimeError("unsafe E2c evaluator wall-time projection")

    initialise_or_verify_campaign_root(manifest_path, manifest, cell_index)
    return {
        "schema_version": "e2c_cell_preflight_v1",
        "status": "passed",
        "cell": cell,
        "identities": identities,
        "closed_prerequisites": closed,
        "independent_review": {
            "path": str(review_path),
            "sha256": sha256(review_path),
            "verdict": review["verdict"],
        },
        "storage": {
            "free_bytes": free_bytes,
            "projected_remaining_output_bytes": projected_remaining_bytes,
            "required_twice_projected_remaining_bytes": storage_required,
            "pass": True,
        },
        "compute": {
            "actual_accepted_full_evaluator_wall_seconds": actual_wall,
            "estimated_remaining_full_evaluator_wall_seconds": estimate_remaining_wall,
            "maximum_new_evaluator_wall_seconds": wall_limit,
            "pass": True,
        },
        "active_evaluators_before_launch": evaluator_processes,
        "serial_concurrency": 1,
    }


def write_checksums(run_dir: Path) -> None:
    ledger = run_dir / "checksums.sha256"
    if ledger.exists():
        raise FileExistsError(f"refusing to overwrite {ledger}")
    members = sorted(
        path
        for path in run_dir.iterdir()
        if path.is_file() and path.name not in {"checksums.sha256", "run_validation.json"}
    )
    ledger.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in members),
        encoding="utf-8",
    )


def run_once(
    manifest: dict[str, Any],
    cell: dict[str, Any],
    run_dir: Path,
    *,
    max_steps: int,
    phase: str,
    repeat: int,
    identities: dict[str, Any],
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=False)
    command = format_command(manifest, cell, run_dir, max_steps=max_steps)
    write_json_new(
        run_dir / "command.json",
        {
            "argv": command,
            "environment_variables": manifest["environment"]["variables"],
            "cell": cell,
            "phase": phase,
            "repeat": repeat,
            "identities": identities,
            "permission_boundary": manifest["permission_boundaries"],
        },
    )
    started = time.monotonic()
    with (
        (run_dir / "stdout.log").open("xb") as stdout,
        (run_dir / "stderr.log").open("xb") as stderr,
    ):
        completed = subprocess.run(  # noqa: S603 - exact reviewed manifest argv
            command,
            env={**os.environ, **manifest["environment"]["variables"]},
            cwd=Path(manifest["paths"]["vec_env_checkout"]),
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    runner_wall = time.monotonic() - started
    write_json_new(
        run_dir / "runner_status.json",
        {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "runner_wall_seconds": runner_wall,
        },
    )
    write_checksums(run_dir)
    if completed.returncode != 0:
        raise RuntimeError(
            f"evaluator failed for {cell_name(cell)} {phase} repeat {repeat}; retained"
        )
    validation = validate_run(
        run_dir,
        manifest=manifest,
        cell=cell,
        expected_steps=max_steps,
    )
    write_json_new(run_dir / "run_validation.json", validation)
    if validation["status"] != "passed":
        raise RuntimeError(f"run validation failed for {cell_name(cell)} {phase} repeat {repeat}")
    return validation


def run_cell(manifest_path: Path, manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    preflight_record = preflight(manifest_path, manifest, cell)
    root = cell_root(manifest, cell)
    root.mkdir(parents=True, exist_ok=False)
    write_json_new(root / "cell_preflight.json", preflight_record)
    identities = preflight_record["identities"]

    smoke_runs = [
        run_once(
            manifest,
            cell,
            root / "smoke" / f"run_{repeat}",
            max_steps=int(manifest["design"]["smoke_steps"]),
            phase="smoke",
            repeat=repeat,
            identities=identities,
        )
        for repeat in (1, 2)
    ]
    repeat_check = compare_repeats(smoke_runs[0], smoke_runs[1])
    smoke_validation: dict[str, Any] = {
        "schema_version": "e2c_cell_smoke_validation_v1",
        "status": "passed" if repeat_check["pass"] else "failed",
        "cell": cell,
        "runs": smoke_runs,
        "repeat": repeat_check,
    }
    if cell["arm"] == "dla":
        ingress_cell = next(
            candidate
            for candidate in manifest["full_cell_order"]
            if candidate["fleet_seed"] == cell["fleet_seed"] and candidate["arm"] == "ingress_dla"
        )
        ingress_smoke = json.loads(
            (
                cell_root(manifest, ingress_cell) / "smoke" / "run_1" / "run_validation.json"
            ).read_text(encoding="utf-8")
        )
        cross_arm = compare_cross_arm(ingress_smoke, smoke_runs[0], manifest)
        smoke_validation["cross_arm_identity"] = cross_arm
        if not cross_arm["pass"]:
            smoke_validation["status"] = "failed"
    write_json_new(root / "smoke_validation.json", smoke_validation)
    if smoke_validation["status"] != "passed":
        raise RuntimeError(f"repeated/cross-arm smoke gate failed: {cell_name(cell)}")

    full_run = run_once(
        manifest,
        cell,
        root / "full" / "run_1",
        max_steps=int(manifest["design"]["steps"]),
        phase="full",
        repeat=1,
        identities=identities,
    )
    cell_validation = validate_cell(manifest, cell)
    write_json_new(root / "cell_validation.json", cell_validation)
    if cell_validation["status"] != "passed":
        raise RuntimeError(f"cell validation failed: {cell_name(cell)}")

    pair_validation = None
    if cell["arm"] == "dla":
        pair_validation = validate_pair(manifest, int(cell["fleet_seed"]))
        pair_path = (
            Path(manifest["outputs"]["raw_root"])
            / "pairs"
            / f"fleet_seed_{cell['fleet_seed']}"
            / "pair_validation.json"
        )
        write_json_new(pair_path, pair_validation)
        if pair_validation["status"] != "passed":
            raise RuntimeError(f"paired validation failed for fleet seed {cell['fleet_seed']}")

    status = {
        "schema_version": "e2c_cell_status_v1",
        "status": "passed",
        "cell": cell,
        "smoke_runs_completed": 2,
        "full_runs_completed": 1,
        "full_evaluator_wall_seconds": float(full_run["summary"]["wall_s"]),
        "cell_validation": str(root / "cell_validation.json"),
        "pair_validation": (
            None
            if pair_validation is None
            else str(
                Path(manifest["outputs"]["raw_root"])
                / "pairs"
                / f"fleet_seed_{cell['fleet_seed']}"
                / "pair_validation.json"
            )
        ),
    }
    write_json_new(root / "cell_status.json", status)
    if int(cell["cell_index"]) == len(manifest["full_cell_order"]):
        write_json_new(
            Path(manifest["outputs"]["raw_root"]) / "campaign_execution_status.json",
            {
                "schema_version": "e2c_campaign_execution_status_v1",
                "status": "all_authorised_cells_passed",
                "cells_planned": 8,
                "cells_passed": 8,
                "smoke_runs_planned": 16,
                "smoke_runs_passed": 16,
                "full_runs_planned": 8,
                "full_runs_passed": 8,
            },
        )
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--cell-index", required=True, type=int)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cells = {int(cell["cell_index"]): cell for cell in manifest["full_cell_order"]}
    if args.cell_index not in cells:
        raise SystemExit(f"undeclared E2c cell index: {args.cell_index}")
    cell = cells[args.cell_index]
    failure_path = cell_root(manifest, cell) / "cell_failure.json"
    try:
        result = run_cell(args.manifest, manifest, cell)
    except Exception as error:
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        if not failure_path.exists():
            write_json_new(
                failure_path,
                {
                    "schema_version": "e2c_cell_failure_v1",
                    "status": "stopped_on_mandatory_gate",
                    "cell": cell,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "failed_evidence_retained": True,
                    "later_cells_authorised": False,
                },
            )
        raise
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

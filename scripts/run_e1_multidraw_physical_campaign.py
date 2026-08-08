#!/usr/bin/env python3
"""Run the predeclared physical E1 multi-draw campaign without overwriting evidence.

The runner intentionally reuses the corrected E0 validator.  Each fleet-seed/cap
cell receives two ten-step runs, exact repeat comparison, and a physical-accounting
validation before its full run is allowed to start.  Raw products remain outside
the TrafficTwin repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, cast

try:
    from scripts.validate_e0_smoke import compare_runs, validate_run
except ModuleNotFoundError:  # direct script execution
    from validate_e0_smoke import (  # type: ignore[no-redef,import-not-found]
        compare_runs,
        validate_run,
    )

GIT = "/usr/bin/git"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_head(path: Path) -> str:
    result = subprocess.run(  # noqa: S603
        [GIT, "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_status(path: Path) -> str:
    result = subprocess.run(  # noqa: S603
        [GIT, "status", "--short"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _cap(manifest: dict[str, Any], label: str) -> dict[str, Any]:
    matches = [item for item in manifest["cap_grid"] if item["label"] == label]
    if len(matches) != 1:
        raise ValueError(f"manifest must contain exactly one cap labelled {label!r}")
    return cast(dict[str, Any], matches[0])


def _physical_manifest_view(
    manifest: dict[str, Any],
    *,
    fleet_seed: int,
    cap_label: str,
    max_steps: int,
) -> dict[str, Any]:
    cap = _cap(manifest, cap_label)
    config = manifest["controlled_configuration"]
    return {
        "manifest_id": manifest["manifest_id"],
        "scope": {"max_steps": max_steps},
        "inputs": manifest["inputs"],
        "configuration": {
            "fleet_seed": fleet_seed,
            "fleet": config["fleet"],
            "arrival_lambda": config["arrival_lambda"],
            "cap": {"resolved_value": cap["resolved_tasks_per_rsu"]},
            "compute": config["compute"],
            "placement": config["placement"],
            "rsu_admission": config["rsu_admission"],
            "substep_queue": config["substep_queue"],
            "vehicle_queue": config["vehicle_queue"],
        },
    }


def _format_argv(
    manifest: dict[str, Any],
    *,
    python: Path,
    vec_env: Path,
    tos_data: Path,
    run_dir: Path,
    fleet_seed: int,
    cap_label: str,
    max_steps: int,
) -> list[str]:
    cap = _cap(manifest, cap_label)
    values = {
        "PYTHON": str(python),
        "VEC_ENV": str(vec_env),
        "TOS_DATA": str(tos_data),
        "RUN_DIR": str(run_dir),
        "FLEET_SEED": str(fleet_seed),
        "CAP_RATIO": cap["ratio_cli"],
        "MAX_STEPS": str(max_steps),
    }
    return [part.format(**values) for part in manifest["execution"]["argv_template"]]


def _write_json(path: Path, value: Any) -> None:  # noqa: ANN401
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_checksums(run_dir: Path) -> dict[str, str]:
    checksum_path = run_dir / "checksums.sha256"
    if checksum_path.exists():
        raise FileExistsError(f"refusing to overwrite {checksum_path}")
    checksums = {
        path.name: sha256_file(path)
        for path in sorted(run_dir.iterdir())
        if path.is_file() and path.name != checksum_path.name
    }
    checksum_path.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()),
        encoding="utf-8",
    )
    return checksums


def _run_once(
    manifest: dict[str, Any],
    *,
    python: Path,
    vec_env: Path,
    tos_data: Path,
    run_dir: Path,
    fleet_seed: int,
    cap_label: str,
    max_steps: int,
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=False)
    argv = _format_argv(
        manifest,
        python=python,
        vec_env=vec_env,
        tos_data=tos_data,
        run_dir=run_dir,
        fleet_seed=fleet_seed,
        cap_label=cap_label,
        max_steps=max_steps,
    )
    selected_environment = manifest["execution"]["environment_variables"]
    environment = os.environ.copy()
    environment.update(selected_environment)
    command_record = {
        "argv": argv,
        "environment_variables": selected_environment,
        "fleet_seed": fleet_seed,
        "cap_label": cap_label,
        "max_steps": max_steps,
    }
    _write_json(run_dir / "command.json", command_record)
    started = time.monotonic()
    with (run_dir / "stdout_stderr.log").open("x", encoding="utf-8") as log:
        result = subprocess.run(  # noqa: S603 - argv is manifest-pinned and preflighted
            argv,
            cwd=vec_env,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
        )
    elapsed = time.monotonic() - started
    status = {
        "exit_code": result.returncode,
        "runner_wall_s": elapsed,
        "completed": result.returncode == 0,
    }
    _write_json(run_dir / "runner_status.json", status)
    checksums = _write_checksums(run_dir)
    if result.returncode != 0:
        raise RuntimeError(f"evaluator failed in {run_dir} with exit code {result.returncode}")
    return {"status": status, "sha256": checksums}


def _identity_preflight(
    manifest: dict[str, Any],
    *,
    traffic_twin: Path,
    vec_env: Path,
    tos_data: Path,
    python: Path,
    adapter_root: Path,
    output_parent: Path,
) -> dict[str, Any]:
    inputs = manifest["inputs"]
    repositories = manifest["repositories"]
    evaluator = vec_env / inputs["evaluator"]["path"]
    actor = tos_data / inputs["actor"]["path"]
    trace = tos_data / inputs["trace"]["path"]
    adapter_initializer = adapter_root / "env" / "__init__.py"
    adapter_vec = adapter_root / "env" / "vec_jax.py"
    observed = {
        "traffictwin_head": git_head(traffic_twin),
        "vec_env_head": git_head(vec_env),
        "tos_data_head": git_head(tos_data),
        "vec_env_status": git_status(vec_env),
        "tos_data_status": git_status(tos_data),
        "evaluator_sha256": sha256_file(evaluator),
        "actor_sha256": sha256_file(actor),
        "trace_sha256": sha256_file(trace),
        "adapter_initializer_sha256": sha256_file(adapter_initializer),
        "adapter_vec_jax_sha256": sha256_file(adapter_vec),
        "python_exists": python.is_file(),
        "output_parent_writable": os.access(output_parent, os.W_OK),
        "storage_available_bytes": shutil.disk_usage(output_parent).free,
    }
    parent_check = (
        subprocess.run(  # noqa: S603
            [
                GIT,
                "merge-base",
                "--is-ancestor",
                repositories["traffictwin"]["parent_commit"],
                "HEAD",
            ],
            cwd=traffic_twin,
            check=False,
        ).returncode
        == 0
    )
    checks = {
        "traffictwin_parent_is_ancestor": parent_check,
        "vec_env_commit": observed["vec_env_head"] == repositories["vec_env"]["commit"],
        "tos_data_commit": observed["tos_data_head"] == repositories["tos_data"]["commit"],
        "vec_env_clean": observed["vec_env_status"] == "",
        "tos_data_clean": observed["tos_data_status"] == "",
        "evaluator_identity": observed["evaluator_sha256"] == inputs["evaluator"]["sha256"],
        "actor_identity": observed["actor_sha256"] == inputs["actor"]["sha256"],
        "trace_identity": observed["trace_sha256"] == inputs["trace"]["sha256"],
        "adapter_initializer_identity": observed["adapter_initializer_sha256"]
        == manifest["environment"]["local_import_adapter_initializer_sha256"],
        "adapter_vec_identity": observed["adapter_vec_jax_sha256"]
        == manifest["environment"]["vec_jax_sha256"],
        "python_exists": observed["python_exists"],
        "output_parent_writable": observed["output_parent_writable"],
        "storage_gate": observed["storage_available_bytes"]
        >= manifest["compute_plan"]["minimum_free_storage_bytes"],
    }
    seed0_checks: dict[str, bool] = {}
    for cap_label, record in manifest["reused_seed0_artifacts"].items():
        run_root = output_parent.parent / record["relative_to_antigravitytest"]
        for filename, digest in record["sha256"].items():
            key = f"{cap_label}:{filename}"
            path = run_root / filename
            seed0_checks[key] = path.is_file() and sha256_file(path) == digest
    checks.update({f"reused_seed0_{name}": passed for name, passed in seed0_checks.items()})
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "observed": observed,
    }


def _validate_smoke_pair(
    manifest: dict[str, Any],
    *,
    run_1: Path,
    run_2: Path,
    fleet_seed: int,
    cap_label: str,
) -> dict[str, Any]:
    view = _physical_manifest_view(
        manifest,
        fleet_seed=fleet_seed,
        cap_label=cap_label,
        max_steps=manifest["scope"]["smoke_steps"],
    )
    first = validate_run(run_1, view, "smoke_run_1")
    second = validate_run(run_2, view, "smoke_run_2")
    repeat = compare_runs(first, second)
    passed = first["passed"] and second["passed"] and repeat["passed"]
    return {
        "schema_version": "traffictwin.e1-multidraw-cell-smoke-validation.v1",
        "passed": passed,
        "fleet_seed": fleet_seed,
        "cap_label": cap_label,
        "runs": [first, second],
        "repeat": repeat,
        "decision": "cell_full_run_authorised" if passed else "stop_campaign",
    }


def _validate_full(
    manifest: dict[str, Any],
    *,
    run_dir: Path,
    fleet_seed: int,
    cap_label: str,
) -> dict[str, Any]:
    view = _physical_manifest_view(
        manifest,
        fleet_seed=fleet_seed,
        cap_label=cap_label,
        max_steps=manifest["scope"]["full_steps"],
    )
    run = validate_run(run_dir, view, "full_run_1")
    return {
        "schema_version": "traffictwin.e1-multidraw-cell-full-validation.v1",
        "passed": run["passed"],
        "fleet_seed": fleet_seed,
        "cap_label": cap_label,
        "run": run,
        "decision": "cell_pass" if run["passed"] else "stop_campaign",
    }


def _common_stream_check(records: list[dict[str, Any]]) -> dict[str, Any]:
    offered = [record["run"]["observed"]["n_offered"] for record in records]
    active = [record["run"]["array_sha256"]["per_task"]["task_active"] for record in records]
    task_type = [record["run"]["array_sha256"]["per_task"]["task_type"] for record in records]
    checks = {
        "offered_count_identical": len(set(offered)) == 1,
        "task_active_identical": len(set(active)) == 1,
        "task_type_identical": len(set(task_type)) == 1,
    }
    return {"passed": all(checks.values()), "checks": checks}


def run_campaign(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    backend_decision = manifest.get("backend_decision", {})
    if backend_decision.get("status") != "selected":
        raise RuntimeError(
            "campaign execution is disabled until the Colab backend comparison is recorded "
            "and backend_decision.status is selected"
        )
    observed_manifest_sha = sha256_file(args.manifest)
    if observed_manifest_sha != args.manifest_sha256:
        raise ValueError(
            "manifest SHA-256 differs from the authority pointer: "
            f"observed {observed_manifest_sha}, expected {args.manifest_sha256}"
        )
    output_root = args.output_parent / manifest["output"]["directory_name"]
    if output_root.exists():
        raise FileExistsError(f"refusing to reuse or overwrite {output_root}")
    preflight = _identity_preflight(
        manifest,
        traffic_twin=args.traffic_twin,
        vec_env=args.vec_env,
        tos_data=args.tos_data,
        python=args.python,
        adapter_root=args.adapter_root,
        output_parent=args.output_parent,
    )
    if not preflight["passed"]:
        print(json.dumps(preflight, indent=2, sort_keys=True))
        return 1
    output_root.mkdir(parents=False, exist_ok=False)
    _write_json(output_root / "preflight.json", preflight)
    _write_json(output_root / "manifest_snapshot.json", manifest)

    cap_labels = [item["label"] for item in manifest["cap_grid"]]
    completed: list[dict[str, Any]] = []
    try:
        for fleet_seed in manifest["seeds"]["new_full_fleet_seeds"]:
            smoke_records: list[dict[str, Any]] = []
            for cap_label in cap_labels:
                cell_root = output_root / f"fleet_seed_{fleet_seed}" / f"cap_{cap_label}"
                run_dirs = [cell_root / "smoke" / f"run_{index}" for index in (1, 2)]
                for run_dir in run_dirs:
                    _run_once(
                        manifest,
                        python=args.python,
                        vec_env=args.vec_env,
                        tos_data=args.tos_data,
                        run_dir=run_dir,
                        fleet_seed=fleet_seed,
                        cap_label=cap_label,
                        max_steps=manifest["scope"]["smoke_steps"],
                    )
                smoke = _validate_smoke_pair(
                    manifest,
                    run_1=run_dirs[0],
                    run_2=run_dirs[1],
                    fleet_seed=fleet_seed,
                    cap_label=cap_label,
                )
                _write_json(cell_root / "smoke_validation.json", smoke)
                if not smoke["passed"]:
                    raise RuntimeError(
                        f"repeated-smoke gate failed for seed {fleet_seed} {cap_label}"
                    )
                smoke_records.append({"run": smoke["runs"][0]})
            smoke_stream = _common_stream_check(smoke_records)
            _write_json(
                output_root / f"fleet_seed_{fleet_seed}" / "smoke_stream_check.json",
                smoke_stream,
            )
            if not smoke_stream["passed"]:
                raise RuntimeError(f"cross-cap smoke stream mismatch for seed {fleet_seed}")

            full_records: list[dict[str, Any]] = []
            for cap_label in cap_labels:
                cell_root = output_root / f"fleet_seed_{fleet_seed}" / f"cap_{cap_label}"
                run_dir = cell_root / "full" / "run_1"
                _run_once(
                    manifest,
                    python=args.python,
                    vec_env=args.vec_env,
                    tos_data=args.tos_data,
                    run_dir=run_dir,
                    fleet_seed=fleet_seed,
                    cap_label=cap_label,
                    max_steps=manifest["scope"]["full_steps"],
                )
                full = _validate_full(
                    manifest,
                    run_dir=run_dir,
                    fleet_seed=fleet_seed,
                    cap_label=cap_label,
                )
                _write_json(cell_root / "full_validation.json", full)
                if not full["passed"]:
                    raise RuntimeError(f"full validation failed for seed {fleet_seed} {cap_label}")
                full_records.append(full)
                stream = _common_stream_check(full_records)
                if not stream["passed"]:
                    raise RuntimeError(f"cross-cap full stream mismatch for seed {fleet_seed}")
                completed.append({"fleet_seed": fleet_seed, "cap_label": cap_label})
            _write_json(
                output_root / f"fleet_seed_{fleet_seed}" / "full_stream_check.json",
                _common_stream_check(full_records),
            )
        _write_json(
            output_root / "campaign_status.json",
            {"status": "all_authorised_cells_passed", "completed_cells": completed},
        )
        return 0
    except Exception as error:
        _write_json(
            output_root / "campaign_status.json",
            {
                "status": "stopped_on_mandatory_gate",
                "completed_cells": completed,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--traffic-twin", required=True, type=Path)
    parser.add_argument("--vec-env", required=True, type=Path)
    parser.add_argument("--tos-data", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--adapter-root", required=True, type=Path)
    parser.add_argument("--output-parent", required=True, type=Path)
    args = parser.parse_args()
    return run_campaign(args)


if __name__ == "__main__":
    raise SystemExit(main())

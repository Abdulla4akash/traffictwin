#!/usr/bin/env python3
"""No-overwrite serial runner for the predeclared E2d campaign."""

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

from validate_e2d_per_task_placement_robustness import (
    cell_name,
    cell_root,
    compare_exact_to_reference,
    compare_identity_to_reference,
    compare_repeats,
    format_command,
    reference_record,
    replay_name,
    replay_root,
    sha256,
    validate_cell,
    validate_run,
    verify_reference_record,
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
        "E2D_VEC_IMPORT_ROOT": str(entrypoint.parents[1]),
    }
    code = (
        "import os,sys; from pathlib import Path; "
        "sys.path.insert(0, os.environ['E2D_VEC_IMPORT_ROOT']); "
        "import env.vec_jax as V; print(Path(V.__file__).resolve())"
    )
    resolved = subprocess.check_output(  # noqa: S603 - frozen interpreter and code
        [manifest["environment"]["python_executable"], "-c", code],
        env=environment,
        text=True,
    ).strip()
    return Path(resolved).resolve()


def verify_checksum_ledger(root: Path, ledger: Path) -> int:
    count = 0
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if "  " not in line:
            raise RuntimeError(f"malformed closed-evidence checksum line: {line!r}")
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"closed evidence checksum mismatch: {path}")
        count += 1
    return count


def verify_closed_prerequisites(manifest: dict[str, Any]) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    for name in ("e1", "e2", "e2b", "e2c"):
        record = manifest["closed_prerequisites"][name]
        checkout = Path(record["checkout"])
        head = git(checkout, "rev-parse", "HEAD")
        observed[f"{name}_head"] = head
        if head != record["final_commit"]:
            raise RuntimeError(f"closed {name.upper()} commit drifted")
        digest = sha256(Path(record["manifest_path"]))
        observed[f"{name}_manifest_sha256"] = digest
        if digest != record["manifest_sha256"]:
            raise RuntimeError(f"closed {name.upper()} manifest drifted")
        if "root_checksum_path" in record:
            ledger = Path(record["root_checksum_path"])
            ledger_sha = sha256(ledger)
            observed[f"{name}_root_checksum_sha256"] = ledger_sha
            if ledger_sha != record["root_checksum_sha256"]:
                raise RuntimeError(f"closed {name.upper()} root checksum ledger drifted")
            observed[f"{name}_root_checksum_members"] = verify_checksum_ledger(
                Path(record["raw_root"]), ledger
            )
    for seed in manifest["design"]["fleet_seeds"]:
        for arm in ("ingress_dla", "dla"):
            for phase in ("smoke", "full"):
                check = verify_reference_record(reference_record(manifest, int(seed), arm, phase))
                if not check["pass"]:
                    raise RuntimeError(
                        f"reused E2c reference drift: seed={seed} arm={arm} phase={phase}"
                    )
    return observed


def active_evaluators() -> list[str]:
    completed = subprocess.run(
        ["/usr/bin/pgrep", "-fl", "eval_sumo_stage1_mc.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def validate_manifest_contract(manifest: dict[str, Any]) -> None:
    cells = manifest["full_cell_order"]
    expected_cells = [
        {"cell_index": seed, "fleet_seed": seed, "arm": "per_task_dla"} for seed in (1, 2, 3, 4)
    ]
    expected_replays = [
        {"replay_index": index, "fleet_seed": seed, "arm": arm}
        for index, (seed, arm) in enumerate(
            (
                (1, "ingress_dla"),
                (1, "dla"),
                (2, "ingress_dla"),
                (2, "dla"),
                (3, "ingress_dla"),
                (3, "dla"),
                (4, "ingress_dla"),
                (4, "dla"),
            ),
            start=1,
        )
    ]
    if cells != expected_cells:
        raise RuntimeError("manifest full-cell order is not the authorised four-cell order")
    if manifest["existing_mode_replay_order"] != expected_replays:
        raise RuntimeError("manifest replay order is not the authorised eight-probe order")
    if set(manifest["arms"]) != {"ingress_dla", "dla", "per_task_dla"}:
        raise RuntimeError("manifest arm inventory changed")
    if manifest["arms"]["per_task_dla"]["rsu_lb"] != "per_task_dla":
        raise RuntimeError("new arm CLI identity changed")
    argv = " ".join(str(part) for part in manifest["command_template"])
    for forbidden in ("--k8s-scale static", "--k8s-scale reactive", "--rsu-backhaul-ms 1"):
        if forbidden in argv:
            raise RuntimeError(f"prohibited command content: {forbidden}")


def initialise_or_verify_campaign_root(
    manifest_path: Path, manifest: dict[str, Any], *, initialise: bool
) -> None:
    raw_root = Path(manifest["outputs"]["raw_root"])
    snapshot = raw_root / "manifest_snapshot.json"
    sidecar_snapshot = raw_root / "manifest_snapshot.sha256"
    manifest_sha = sha256(manifest_path)
    if initialise:
        raw_root.mkdir(parents=True, exist_ok=True)
        allowed = {"independent_review"}
        unexpected = [path.name for path in raw_root.iterdir() if path.name not in allowed]
        if unexpected:
            raise RuntimeError(f"new E2d root contains undeclared entries: {unexpected}")
        with snapshot.open("xb") as handle:
            handle.write(manifest_path.read_bytes())
        with sidecar_snapshot.open("x", encoding="utf-8") as handle:
            handle.write(f"{manifest_sha}  manifest_snapshot.json\n")
        return
    if not snapshot.is_file() or not sidecar_snapshot.is_file():
        raise RuntimeError("E2d campaign manifest snapshot is missing")
    if (
        snapshot.read_bytes() != manifest_path.read_bytes()
        or sha256(snapshot) != manifest_sha
        or sidecar_snapshot.read_text(encoding="utf-8").split()[0] != manifest_sha
        or json.loads(snapshot.read_text(encoding="utf-8")) != manifest
    ):
        raise RuntimeError("E2d manifest changed after launch")


def verify_review_gate(
    review_path: Path, identities: dict[str, Any], manifest_sha: str
) -> dict[str, Any]:
    if not review_path.is_file():
        raise RuntimeError("independent Claude review evidence is missing")
    review: dict[str, Any] = json.loads(review_path.read_text(encoding="utf-8"))
    expected = {
        "verdict": "APPROVE",
        "traffictwin_commit": identities["traffictwin_commit"],
        "vec_env_commit": identities["vec_env_commit"],
        "manifest_sha256": manifest_sha,
    }
    mismatches = {
        key: {"observed": review.get(key), "expected": value}
        for key, value in expected.items()
        if review.get(key) != value
    }
    if mismatches:
        raise RuntimeError(f"Claude APPROVE identity mismatch: {mismatches}")
    return review


def accepted_evaluator_wall_seconds(raw_root: Path) -> float:
    total = 0.0
    if not raw_root.exists():
        return total
    for path in raw_root.rglob("summary.json"):
        total += float(json.loads(path.read_text(encoding="utf-8"))["wall_s"])
    return total


def remaining_projection(
    manifest: dict[str, Any], *, phase: str, cell_index: int | None
) -> dict[str, float | int]:
    limits = manifest["compute_and_storage"]
    if phase == "replay_gate":
        replays = 8
        smokes = 8
        fulls = 4
    else:
        if cell_index is None:
            raise ValueError("cell_index required for cell projection")
        remaining_cells = 5 - cell_index
        replays = 0
        smokes = remaining_cells * 2
        fulls = remaining_cells
    wall = (
        replays * float(limits["projected_ten_step_wall_seconds"])
        + smokes * float(limits["projected_ten_step_wall_seconds"])
        + fulls * float(limits["projected_per_task_full_wall_seconds"])
    )
    output = (
        replays * int(limits["projected_ten_step_output_bytes"])
        + smokes * int(limits["projected_ten_step_output_bytes"])
        + fulls * int(limits["projected_per_task_full_output_bytes"])
    )
    return {"wall_seconds": wall, "output_bytes": output}


def required_free_bytes(projected_remaining_output_bytes: int) -> int:
    """Return the frozen twice-projected-output storage threshold."""

    return 2 * projected_remaining_output_bytes


def storage_gate_passes(free_bytes: int, projected_remaining_output_bytes: int) -> bool:
    return free_bytes >= required_free_bytes(projected_remaining_output_bytes)


def preflight(
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    phase: str,
    cell_index: int | None = None,
) -> dict[str, Any]:
    import jax

    validate_manifest_contract(manifest)
    sidecar = manifest_path.with_suffix(".sha256")
    manifest_sha = sha256(manifest_path)
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").split()[0] != manifest_sha:
        raise RuntimeError("manifest checksum sidecar mismatch")

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
        "vec_env_branch": git(vec_repo, "branch", "--show-current"),
        "vec_env_commit": git(vec_repo, "rev-parse", "HEAD"),
        "tos_data_commit": git(tos_repo, "rev-parse", "HEAD"),
        "evaluator_sha256": sha256(Path(paths["evaluator"])),
        "per_task_helper_sha256": sha256(Path(paths["per_task_placement_helper"])),
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
        "vec_env_branch": repositories["vec_env"]["branch"],
        "vec_env_commit": repositories["vec_env"]["candidate_commit"],
        "tos_data_commit": repositories["tos_data"]["commit"],
        "evaluator_sha256": repositories["vec_env"]["evaluator_sha256"],
        "per_task_helper_sha256": repositories["vec_env"]["per_task_helper_sha256"],
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
        raise RuntimeError(f"E2d identity mismatch: {json.dumps(mismatches, sort_keys=True)}")
    if git(tt_repo, "status", "--short"):
        raise RuntimeError("TrafficTwin E2d checkout is not clean")
    if git(vec_repo, "status", "--short"):
        raise RuntimeError("vec_env E2d checkout is not clean")
    if git(tos_repo, "status", "--short"):
        raise RuntimeError("tos-data checkout is not clean")
    if "github.com/Abdulla4akash/traffictwin" not in git(
        tt_repo, "remote", "get-url", "--push", "origin"
    ):
        raise RuntimeError("TrafficTwin origin is not Abdulla's private mirror")
    if "github.com/Abdulla4akash/vec_env" not in git(
        vec_repo, "remote", "get-url", "--push", "origin"
    ):
        raise RuntimeError("vec_env origin is not Abdulla's private mirror")
    evaluators = active_evaluators()
    if evaluators:
        raise RuntimeError(f"another evaluator is active: {evaluators}")

    closed = verify_closed_prerequisites(manifest)
    review_path = Path(manifest["review_gate"]["verdict_path"])
    review = verify_review_gate(review_path, identities, manifest_sha)
    raw_root = Path(manifest["outputs"]["raw_root"])
    initialise_or_verify_campaign_root(manifest_path, manifest, initialise=phase == "replay_gate")
    projection = remaining_projection(manifest, phase=phase, cell_index=cell_index)
    free_bytes = shutil.disk_usage(raw_root.parent).free
    required_bytes = required_free_bytes(int(projection["output_bytes"]))
    if not storage_gate_passes(free_bytes, int(projection["output_bytes"])):
        raise RuntimeError(f"unsafe E2d storage: {free_bytes} free < {required_bytes} required")
    actual_wall = accepted_evaluator_wall_seconds(raw_root)
    wall_limit = float(manifest["compute_and_storage"]["maximum_evaluator_wall_seconds"])
    if actual_wall + float(projection["wall_seconds"]) > wall_limit:
        raise RuntimeError("unsafe E2d evaluator wall-time projection")
    return {
        "schema_version": "e2d_preflight_v1",
        "status": "passed",
        "phase": phase,
        "cell_index": cell_index,
        "identities": identities,
        "closed_prerequisites": closed,
        "independent_review": {
            "path": str(review_path),
            "sha256": sha256(review_path),
            "verdict": review["verdict"],
        },
        "storage": {
            "free_bytes": free_bytes,
            "projected_remaining_output_bytes": int(projection["output_bytes"]),
            "required_twice_projected_remaining_bytes": required_bytes,
            "pass": True,
        },
        "compute": {
            "actual_accepted_evaluator_wall_seconds": actual_wall,
            "estimated_remaining_evaluator_wall_seconds": float(projection["wall_seconds"]),
            "maximum_evaluator_wall_seconds": wall_limit,
            "pass": True,
        },
        "active_evaluators_before_launch": evaluators,
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
    run: dict[str, Any],
    run_dir: Path,
    *,
    max_steps: int,
    phase: str,
    repeat: int,
    identities: dict[str, Any],
) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=False)
    command = format_command(manifest, run, run_dir, max_steps=max_steps)
    write_json_new(
        run_dir / "command.json",
        {
            "argv": command,
            "environment_variables": manifest["environment"]["variables"],
            "run": run,
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
    write_json_new(
        run_dir / "runner_status.json",
        {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "runner_wall_seconds": time.monotonic() - started,
        },
    )
    write_checksums(run_dir)
    if completed.returncode != 0:
        raise RuntimeError(f"evaluator failed for {phase}; evidence retained: {run_dir}")
    validation = validate_run(
        run_dir,
        manifest=manifest,
        run=run,
        expected_steps=max_steps,
    )
    write_json_new(run_dir / "run_validation.json", validation)
    if validation["status"] != "passed":
        raise RuntimeError(f"run validation failed for {phase}: {run_dir}")
    return validation


def run_replay_gate(manifest_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    status_path = Path(manifest["outputs"]["raw_root"]) / "replay_gate_status.json"
    if status_path.exists():
        raise FileExistsError(f"refusing to overwrite {status_path}")
    preflight_record = preflight(manifest_path, manifest, phase="replay_gate", cell_index=None)
    write_json_new(
        Path(manifest["outputs"]["raw_root"]) / "replay_gate_preflight.json",
        preflight_record,
    )
    records: list[dict[str, Any]] = []
    try:
        for replay in manifest["existing_mode_replay_order"]:
            root = replay_root(manifest, replay)
            validation = run_once(
                manifest,
                replay,
                root,
                max_steps=int(manifest["design"]["smoke_steps"]),
                phase="existing_mode_no_effect_replay",
                repeat=1,
                identities=preflight_record["identities"],
            )
            exact = compare_exact_to_reference(
                validation,
                reference_record(
                    manifest,
                    int(replay["fleet_seed"]),
                    str(replay["arm"]),
                    "smoke",
                ),
            )
            replay_validation = {
                "schema_version": "e2d_existing_mode_replay_validation_v1",
                "status": "passed" if exact["pass"] else "failed",
                "replay": replay,
                "parent_candidate_exact": exact,
            }
            write_json_new(root / "replay_validation.json", replay_validation)
            records.append(replay_validation)
            if not exact["pass"]:
                raise RuntimeError(f"existing-mode replay differs: {replay_name(replay)}")
    except Exception as error:
        write_json_new(
            Path(manifest["outputs"]["raw_root"]) / "replay_gate_failure.json",
            {
                "schema_version": "e2d_replay_gate_failure_v1",
                "status": "stopped_on_mandatory_gate",
                "error_type": type(error).__name__,
                "error": str(error),
                "completed_replays": len(records),
                "failed_evidence_retained": True,
                "new_arm_authorised": False,
            },
        )
        raise
    result = {
        "schema_version": "e2d_replay_gate_status_v1",
        "status": "passed",
        "replays_planned": 8,
        "replays_passed": 8,
        "records": records,
    }
    write_json_new(status_path, result)
    return result


def verify_prior_cell_order(manifest: dict[str, Any], cell_index: int) -> None:
    replay_status = Path(manifest["outputs"]["raw_root"]) / "replay_gate_status.json"
    if (
        not replay_status.is_file()
        or json.loads(replay_status.read_text(encoding="utf-8")).get("status") != "passed"
    ):
        raise RuntimeError("all eight existing-mode replay probes have not passed")
    for prior in manifest["full_cell_order"]:
        if int(prior["cell_index"]) >= cell_index:
            continue
        status_path = cell_root(manifest, prior) / "cell_status.json"
        if (
            not status_path.is_file()
            or json.loads(status_path.read_text(encoding="utf-8")).get("status") != "passed"
        ):
            raise RuntimeError(f"prior E2d cell did not pass: {cell_name(prior)}")


def run_cell(manifest_path: Path, manifest: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    cell_index = int(cell["cell_index"])
    root = cell_root(manifest, cell)
    if root.exists():
        raise FileExistsError(f"refusing to overwrite E2d cell: {root}")
    verify_prior_cell_order(manifest, cell_index)
    preflight_record = preflight(manifest_path, manifest, phase="cell", cell_index=cell_index)
    root.mkdir(parents=True, exist_ok=False)
    write_json_new(root / "cell_preflight.json", preflight_record)
    identities = preflight_record["identities"]
    try:
        smoke_runs = [
            run_once(
                manifest,
                cell,
                root / "smoke" / f"run_{repeat}",
                max_steps=int(manifest["design"]["smoke_steps"]),
                phase="new_arm_smoke",
                repeat=repeat,
                identities=identities,
            )
            for repeat in (1, 2)
        ]
        repeated = compare_repeats(smoke_runs[0], smoke_runs[1])
        baseline_identity = {
            arm: compare_identity_to_reference(
                smoke_runs[0],
                reference_record(manifest, int(cell["fleet_seed"]), arm, "smoke"),
                manifest,
            )
            for arm in ("ingress_dla", "dla")
        }
        smoke_validation = {
            "schema_version": "e2d_smoke_validation_v1",
            "status": (
                "passed"
                if repeated["pass"] and all(item["pass"] for item in baseline_identity.values())
                else "failed"
            ),
            "cell": cell,
            "repeat": repeated,
            "identity_against_reused_e2c": baseline_identity,
        }
        write_json_new(root / "smoke_validation.json", smoke_validation)
        if smoke_validation["status"] != "passed":
            raise RuntimeError(f"E2d repeated-smoke gate failed: {cell_name(cell)}")

        full = run_once(
            manifest,
            cell,
            root / "full" / "run_1",
            max_steps=int(manifest["design"]["steps"]),
            phase="new_arm_full",
            repeat=1,
            identities=identities,
        )
        full_identity = {
            arm: compare_identity_to_reference(
                full,
                reference_record(manifest, int(cell["fleet_seed"]), arm, "full"),
                manifest,
            )
            for arm in ("ingress_dla", "dla")
        }
        if not all(item["pass"] for item in full_identity.values()):
            raise RuntimeError(f"E2d full task/action identity failed: {cell_name(cell)}")
        cell_validation = validate_cell(manifest, cell)
        write_json_new(root / "cell_validation.json", cell_validation)
        if cell_validation["status"] != "passed":
            raise RuntimeError(f"E2d cell validation failed: {cell_name(cell)}")
    except Exception as error:
        write_json_new(
            root / "cell_failure.json",
            {
                "schema_version": "e2d_cell_failure_v1",
                "status": "stopped_on_mandatory_gate",
                "cell": cell,
                "error_type": type(error).__name__,
                "error": str(error),
                "failed_evidence_retained": True,
                "later_cells_authorised": False,
            },
        )
        raise

    status = {
        "schema_version": "e2d_cell_status_v1",
        "status": "passed",
        "cell": cell,
        "smoke_runs_completed": 2,
        "full_runs_completed": 1,
        "full_evaluator_wall_seconds": float(full["summary"]["wall_s"]),
        "cell_validation": str(root / "cell_validation.json"),
    }
    write_json_new(root / "cell_status.json", status)
    write_json_new(
        Path(manifest["outputs"]["raw_root"])
        / "accepted_wall_time"
        / f"after_cell_{cell_index}.json",
        {
            "schema_version": "e2d_accepted_wall_time_v1",
            "after_cell_index": cell_index,
            "accepted_evaluator_wall_seconds": accepted_evaluator_wall_seconds(
                Path(manifest["outputs"]["raw_root"])
            ),
        },
    )
    if cell_index == 4:
        write_json_new(
            Path(manifest["outputs"]["raw_root"]) / "campaign_execution_status.json",
            {
                "schema_version": "e2d_campaign_execution_status_v1",
                "status": "all_authorised_cells_passed",
                "replays_planned": 8,
                "replays_passed": 8,
                "smokes_planned": 8,
                "smokes_passed": 8,
                "full_cells_planned": 4,
                "full_cells_started": 4,
                "full_cells_passed": 4,
                "full_cells_failed": 0,
                "full_cells_stopped": 0,
            },
        )
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-replay-gate", action="store_true")
    group.add_argument("--cell-index", type=int)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.run_replay_gate:
        result = run_replay_gate(args.manifest, manifest)
    else:
        cells = {int(cell["cell_index"]): cell for cell in manifest["full_cell_order"]}
        if args.cell_index not in cells:
            raise SystemExit(f"undeclared E2d cell index: {args.cell_index}")
        result = run_cell(args.manifest, manifest, cells[args.cell_index])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

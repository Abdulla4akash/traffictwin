#!/usr/bin/env python3
"""No-overwrite serial runner for the bounded E2 native-placement pilot."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import jax

from validate_e2_native_placement_pilot import validate_phase, validate_run


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def package_versions() -> dict[str, str]:
    return {
        name: importlib.metadata.version(name)
        for name in ("jax", "jaxlib", "numpy", "ml_dtypes", "opt_einsum", "scipy")
    }


def write_checksums(run_dir: Path) -> None:
    files = sorted(
        path for path in run_dir.iterdir()
        if path.is_file() and path.name not in {"checksums.sha256", "run_validation.json"}
    )
    (run_dir / "checksums.sha256").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in files) + "\n"
    )


def preflight(manifest_path: Path, manifest: dict, phase: str) -> dict:
    manifest_sha = sha256(manifest_path)
    sidecar = manifest_path.with_suffix(".sha256")
    if not sidecar.is_file():
        raise SystemExit(f"missing manifest checksum sidecar: {sidecar}")
    expected_manifest_sha = sidecar.read_text().split()[0]
    if manifest_sha != expected_manifest_sha:
        raise SystemExit(f"manifest SHA mismatch: {manifest_sha} != {expected_manifest_sha}")

    repos = manifest["repositories"]
    paths = manifest["paths"]
    tt_repo = Path(paths["traffictwin_checkout"])
    vec_repo = Path(paths["vec_env_checkout"])
    tos_repo = Path(paths["tos_data_checkout"])
    identities = {
        "traffictwin_branch": git(tt_repo, "branch", "--show-current"),
        "traffictwin_commit": git(tt_repo, "rev-parse", "HEAD"),
        "vec_env_branch": git(vec_repo, "branch", "--show-current"),
        "vec_env_commit": git(vec_repo, "rev-parse", "HEAD"),
        "tos_data_commit": git(tos_repo, "rev-parse", "HEAD"),
        "evaluator_sha256": sha256(Path(paths["evaluator"])),
        "vec_jax_sha256": sha256(Path(paths["vec_jax"])),
        "actor_sha256": sha256(Path(manifest["inputs"]["actor"]["path"])),
        "trace_sha256": sha256(Path(manifest["inputs"]["trace"]["path"])),
        "python_version": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_executable_sha256": sha256(Path(sys.executable)),
        "packages": package_versions(),
        "backend": jax.default_backend(),
        "devices": [str(device) for device in jax.devices()],
        "manifest_sha256": manifest_sha,
    }
    expected = {
        "traffictwin_branch": repos["traffictwin"]["branch"],
        "vec_env_branch": repos["vec_env"]["branch"],
        "vec_env_commit": repos["vec_env"]["instrumentation_commit"],
        "tos_data_commit": repos["tos_data"]["commit"],
        "evaluator_sha256": repos["vec_env"]["evaluator_sha256"],
        "vec_jax_sha256": repos["vec_env"]["vec_jax_sha256"],
        "actor_sha256": manifest["inputs"]["actor"]["sha256"],
        "trace_sha256": manifest["inputs"]["trace"]["sha256"],
        "python_version": manifest["environment"]["python_version"],
        "python_executable": str(Path(manifest["environment"]["python_executable"]).resolve()),
        "python_executable_sha256": manifest["environment"]["python_executable_sha256"],
        "packages": manifest["environment"]["packages"],
        "backend": manifest["environment"]["backend"],
        "devices": manifest["environment"]["devices"],
    }
    mismatches = {
        key: {"observed": identities[key], "expected": value}
        for key, value in expected.items() if identities[key] != value
    }
    if mismatches:
        raise SystemExit(f"preflight identity mismatch: {json.dumps(mismatches, sort_keys=True)}")
    if git(tt_repo, "status", "--short"):
        raise SystemExit("TrafficTwin checkout is not clean")
    if git(vec_repo, "status", "--short"):
        raise SystemExit("vec_env checkout is not clean")
    if git(tos_repo, "status", "--short"):
        raise SystemExit("tos-data checkout is not clean")
    if "github.com/Abdulla4akash/vec_env" not in git(vec_repo, "remote", "get-url", "--push", "origin"):
        raise SystemExit("vec_env origin is not Abdulla's private mirror")

    # E1 is a closed immutable prerequisite, not an input to be regenerated.
    e1 = manifest["closed_e1_prerequisite"]
    e1_repo = Path(e1["checkout"])
    if git(e1_repo, "rev-parse", "HEAD") != e1["final_commit"]:
        raise SystemExit("closed E1 checkout commit drifted")
    if sha256(Path(e1["manifest_path"])) != e1["manifest_sha256"]:
        raise SystemExit("closed E1 manifest hash drifted")

    review_path = Path(manifest["review_gate"]["verdict_path"])
    if not review_path.is_file():
        raise SystemExit(f"independent Claude review evidence missing: {review_path}")
    review = json.loads(review_path.read_text())
    review_expected = {
        "verdict": "APPROVE",
        "traffictwin_commit": identities["traffictwin_commit"],
        "vec_env_commit": identities["vec_env_commit"],
        "manifest_sha256": manifest_sha,
    }
    review_mismatches = {
        key: {"observed": review.get(key), "expected": value}
        for key, value in review_expected.items() if review.get(key) != value
    }
    if review_mismatches:
        raise SystemExit(f"Claude approval mismatch: {json.dumps(review_mismatches, sort_keys=True)}")

    no_effect = json.loads(Path(manifest["gates"]["no_effect_validation"]).read_text())
    hand_probe = json.loads(Path(manifest["gates"]["two_rsu_validation"]).read_text())
    if no_effect.get("status") != "passed" or hand_probe.get("status") != "passed":
        raise SystemExit("instrumentation no-effect or two-RSU gate is not passed")
    if no_effect["identities"]["candidate_commit"] != identities["vec_env_commit"]:
        raise SystemExit("no-effect evidence does not cover the current vec_env commit")

    raw_root = Path(manifest["outputs"]["raw_root"])
    if not raw_root.is_dir():
        raise SystemExit(f"raw root missing: {raw_root}")
    target = raw_root / phase
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing phase output: {target}")
    if phase == "full":
        smoke_validation = raw_root / "smoke_validation.json"
        if not smoke_validation.is_file() or json.loads(smoke_validation.read_text()).get("status") != "passed":
            raise SystemExit("full phase requires a passed smoke_validation.json")
    return identities


def run_one(
    *,
    manifest: dict,
    phase: str,
    arm: dict,
    repeat: int,
    identities: dict,
) -> dict:
    raw_root = Path(manifest["outputs"]["raw_root"])
    run_dir = raw_root / phase / arm["id"] / f"run_{repeat}"
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite {run_dir}")
    run_dir.mkdir(parents=True)
    command = list(arm["full_argv"])
    if phase == "smoke":
        command[command.index("--max-steps") + 1] = str(manifest["smoke_gate"]["steps"])
        for flag, name in (("--out-json", "summary.json"),
                           ("--per-step-out", "per_step.npz"),
                           ("--per-task-out", "per_task.npz")):
            command[command.index(flag) + 1] = str(run_dir / name)
    expected_paths = {
        "summary.json": str(run_dir / "summary.json"),
        "per_step.npz": str(run_dir / "per_step.npz"),
        "per_task.npz": str(run_dir / "per_task.npz"),
    }
    for flag, name in (("--out-json", "summary.json"), ("--per-step-out", "per_step.npz"),
                       ("--per-task-out", "per_task.npz")):
        observed = command[command.index(flag) + 1]
        if observed != expected_paths[name]:
            raise SystemExit(f"manifest command path mismatch for {arm['id']} {flag}: {observed}")
    record = {
        "argv": command,
        "environment_variables": manifest["environment"]["variables"],
        "phase": phase,
        "arm": arm["id"],
        "repeat": repeat,
        "identities": identities,
        "permission_boundary": manifest["permission_boundaries"],
    }
    (run_dir / "command.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with (run_dir / "stdout.log").open("wb") as stdout, (run_dir / "stderr.log").open("wb") as stderr:
        completed = subprocess.run(
            command,
            env={**os.environ, **manifest["environment"]["variables"]},
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    if completed.returncode:
        (run_dir / "run_error.json").write_text(json.dumps({
            "returncode": completed.returncode,
            "status": "failed",
        }, indent=2) + "\n")
        raise SystemExit(f"{phase} {arm['id']} run {repeat} failed; retained {run_dir}")
    write_checksums(run_dir)
    expected_steps = (
        manifest["smoke_gate"]["steps"] if phase == "smoke" else manifest["design"]["steps"]
    )
    validation = validate_run(
        run_dir, arm=arm, manifest=manifest, expected_steps=expected_steps
    )
    (run_dir / "run_validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n"
    )
    if validation["status"] != "passed":
        raise SystemExit(f"{phase} {arm['id']} run {repeat} validation failed; retained {run_dir}")
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    identities = preflight(args.manifest, manifest, args.phase)
    repeats = manifest["smoke_gate"]["serial_repeats_per_arm"] if args.phase == "smoke" else 1
    completed = []
    for arm in manifest["arms"]:
        for repeat in range(1, repeats + 1):
            completed.append(run_one(
                manifest=manifest, phase=args.phase, arm=arm,
                repeat=repeat, identities=identities,
            ))
    phase_validation = validate_phase(manifest, args.phase)
    raw_root = Path(manifest["outputs"]["raw_root"])
    validation_path = raw_root / f"{args.phase}_validation.json"
    validation_path.write_text(json.dumps(phase_validation, indent=2, sort_keys=True) + "\n")
    status_path = raw_root / f"{args.phase}_status.json"
    status_path.write_text(json.dumps({
        "phase": args.phase,
        "status": phase_validation["status"],
        "completed_runs": [run["run_dir"] for run in completed],
        "validation": str(validation_path),
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": phase_validation["status"], "validation": str(validation_path)}, indent=2))
    return 0 if phase_validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

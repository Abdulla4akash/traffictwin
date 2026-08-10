#!/usr/bin/env python3
"""No-overwrite serial runner for the single E2b ingress-DLA cell."""
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

from validate_e2b_placement_admission_factorial import validate_phase, validate_run


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


def resolve_imported_vec_jax(manifest: dict) -> Path:
    """Resolve the module imported through the evaluator's production import root."""
    entrypoint = Path(manifest["paths"]["imported_vec_jax_entrypoint"])
    env = {
        **os.environ,
        **manifest["environment"]["variables"],
        "E2B_VEC_IMPORT_ROOT": str(entrypoint.parents[1]),
    }
    code = (
        "import os, sys; from pathlib import Path; "
        "sys.path.insert(0, os.environ['E2B_VEC_IMPORT_ROOT']); "
        "import env.vec_jax as V; "
        "print(Path(V.__file__).resolve())"
    )
    resolved = subprocess.check_output(
        [manifest["environment"]["python_executable"], "-c", code],
        env=env,
        text=True,
    ).strip()
    return Path(resolved).resolve()


def verify_checksum_ledger(root: Path, ledger: Path) -> None:
    for line in ledger.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"checksum ledger mismatch: {path}")


def write_checksums(run_dir: Path) -> None:
    files = sorted(
        path for path in run_dir.iterdir()
        if path.is_file() and path.name not in {"checksums.sha256", "run_validation.json"}
    )
    (run_dir / "checksums.sha256").write_text(
        "\n".join(f"{sha256(path)}  {path.name}" for path in files) + "\n"
    )


def preflight(manifest_path: Path, manifest: dict, phase: str) -> dict:
    import jax

    manifest_sha = sha256(manifest_path)
    sidecar = manifest_path.with_suffix(".sha256")
    if not sidecar.is_file() or sidecar.read_text().split()[0] != manifest_sha:
        raise SystemExit("manifest checksum sidecar mismatch")

    paths = manifest["paths"]
    repos = manifest["repositories"]
    tt_repo = Path(paths["traffictwin_checkout"])
    vec_repo = Path(paths["vec_env_checkout"])
    tos_repo = Path(paths["tos_data_checkout"])
    imported_vec_jax = resolve_imported_vec_jax(manifest)
    identities = {
        "traffictwin_branch": git(tt_repo, "branch", "--show-current"),
        "traffictwin_commit": git(tt_repo, "rev-parse", "HEAD"),
        "vec_env_branch": git(vec_repo, "branch", "--show-current"),
        "vec_env_commit": git(vec_repo, "rev-parse", "HEAD"),
        "tos_data_commit": git(tos_repo, "rev-parse", "HEAD"),
        "evaluator_sha256": sha256(Path(paths["evaluator"])),
        "vec_jax_sha256": sha256(Path(paths["vec_jax"])),
        "resolved_imported_vec_jax_path": str(imported_vec_jax),
        "resolved_imported_vec_jax_sha256": sha256(imported_vec_jax),
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
        "vec_env_commit": repos["vec_env"]["commit"],
        "tos_data_commit": repos["tos_data"]["commit"],
        "evaluator_sha256": repos["vec_env"]["evaluator_sha256"],
        "vec_jax_sha256": repos["vec_env"]["vec_jax_sha256"],
        "resolved_imported_vec_jax_path": str(
            Path(paths["resolved_imported_vec_jax"]).resolve()
        ),
        "resolved_imported_vec_jax_sha256": repos["vec_env"][
            "resolved_imported_vec_jax_sha256"
        ],
        "actor_sha256": manifest["inputs"]["actor"]["sha256"],
        "trace_sha256": manifest["inputs"]["trace"]["sha256"],
        "python_version": manifest["environment"]["python_version"],
        "python_executable": str(
            Path(manifest["environment"]["python_executable"]).resolve()
        ),
        "python_executable_sha256": manifest["environment"][
            "python_executable_sha256"
        ],
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
    for name, repo in (("TrafficTwin", tt_repo), ("vec_env", vec_repo), ("tos-data", tos_repo)):
        if git(repo, "status", "--short"):
            raise SystemExit(f"{name} checkout is not clean")
    if "github.com/Abdulla4akash/vec_env" not in git(
        vec_repo, "remote", "get-url", "--push", "origin"
    ):
        raise SystemExit("vec_env origin is not Abdulla's private mirror")

    e1 = manifest["closed_e1_prerequisite"]
    if git(Path(e1["checkout"]), "rev-parse", "HEAD") != e1["final_commit"]:
        raise SystemExit("closed E1 commit drifted")
    if sha256(Path(e1["manifest_path"])) != e1["manifest_sha256"]:
        raise SystemExit("closed E1 manifest drifted")

    e2 = manifest["completed_e2_reuse"]
    if git(Path(e2["checkout"]), "rev-parse", "HEAD") != e2["final_commit"]:
        raise SystemExit("completed E2 TrafficTwin commit drifted")
    if sha256(Path(e2["manifest_path"])) != e2["manifest_sha256"]:
        raise SystemExit("completed E2 manifest drifted")
    raw_root = Path(e2["raw_root"])
    raw_ledger = Path(e2["raw_checksums"]["path"])
    if sha256(raw_ledger) != e2["raw_checksums"]["sha256"]:
        raise SystemExit("completed E2 checksum ledger drifted")
    verify_checksum_ledger(raw_root, raw_ledger)
    for evidence in e2["reuse_evidence"]:
        if sha256(Path(evidence["path"])) != evidence["sha256"]:
            raise SystemExit(f"completed E2 evidence drifted: {evidence['path']}")
    for arm, hashes in e2["full_run_hashes"].items():
        run_dir = Path(e2["reference_runs"]["full"][arm])
        for key, filename in (("summary", "summary.json"),
                              ("per_step", "per_step.npz"),
                              ("per_task", "per_task.npz"),
                              ("checksums", "checksums.sha256")):
            if sha256(run_dir / filename) != hashes[key]:
                raise SystemExit(f"completed E2 {arm} {filename} drifted")

    for gate_name in ("existing_arm_no_effect", "two_rsu_production_probe"):
        gate = manifest["gates"][gate_name]
        path = Path(gate["path"])
        if sha256(path) != gate["sha256"]:
            raise SystemExit(f"{gate_name} evidence hash mismatch")
        payload = json.loads(path.read_text())
        if payload.get("status") != "passed":
            raise SystemExit(f"{gate_name} is not passed")
    no_effect = json.loads(Path(manifest["gates"]["existing_arm_no_effect"]["path"]).read_text())
    if no_effect["identities"]["candidate_commit"] != identities["vec_env_commit"]:
        raise SystemExit("no-effect evidence does not bind current vec_env commit")
    probe = json.loads(Path(manifest["gates"]["two_rsu_production_probe"]["path"]).read_text())
    if (
        probe["production_evaluator"]["candidate_commit"] != identities["vec_env_commit"]
        or probe["production_evaluator"]["sha256"] != identities["evaluator_sha256"]
    ):
        raise SystemExit("two-RSU evidence does not bind current evaluator")

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

    e2b_root = Path(manifest["outputs"]["raw_root"])
    target = e2b_root / phase
    if target.exists():
        raise SystemExit(f"refusing to overwrite existing phase output: {target}")
    for name in (f"{phase}_validation.json", f"{phase}_status.json"):
        if (e2b_root / name).exists():
            raise SystemExit(f"refusing to overwrite existing phase evidence: {name}")
    if phase == "full":
        smoke_validation = e2b_root / "smoke_validation.json"
        if (
            not smoke_validation.is_file()
            or json.loads(smoke_validation.read_text()).get("status") != "passed"
        ):
            raise SystemExit("full phase requires passed repeated-smoke evidence")
    return identities


def run_one(*, manifest: dict, phase: str, repeat: int, identities: dict) -> dict:
    arm = manifest["arms"][0]
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
    (run_dir / "command.json").write_text(json.dumps({
        "argv": command,
        "environment_variables": manifest["environment"]["variables"],
        "phase": phase,
        "arm": arm["id"],
        "repeat": repeat,
        "identities": identities,
        "permission_boundary": manifest["permission_boundaries"],
    }, indent=2, sort_keys=True) + "\n")
    with (run_dir / "stdout.log").open("wb") as stdout, \
            (run_dir / "stderr.log").open("wb") as stderr:
        completed = subprocess.run(
            command,
            env={**os.environ, **manifest["environment"]["variables"]},
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    if completed.returncode:
        (run_dir / "run_error.json").write_text(json.dumps({
            "returncode": completed.returncode, "status": "failed"
        }, indent=2) + "\n")
        raise SystemExit(f"{phase} {arm['id']} run {repeat} failed; retained {run_dir}")
    write_checksums(run_dir)
    expected_steps = (
        manifest["smoke_gate"]["steps"] if phase == "smoke"
        else manifest["design"]["steps"]
    )
    validation = validate_run(
        run_dir, arm=arm, manifest=manifest, expected_steps=expected_steps
    )
    (run_dir / "run_validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n"
    )
    if validation["status"] != "passed":
        raise SystemExit(f"{phase} run {repeat} validation failed; retained {run_dir}")
    return validation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--phase", choices=("smoke", "full"), required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    identities = preflight(args.manifest, manifest, args.phase)
    repeats = (
        manifest["smoke_gate"]["serial_repeats_per_arm"]
        if args.phase == "smoke" else 1
    )
    completed = [
        run_one(manifest=manifest, phase=args.phase, repeat=repeat, identities=identities)
        for repeat in range(1, repeats + 1)
    ]
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
    print(json.dumps({"status": phase_validation["status"],
                      "validation": str(validation_path)}, indent=2))
    return 0 if phase_validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

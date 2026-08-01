# ruff: noqa: S603
"""Resumable full-scale B-REWARD MAPPO campaign for a disposable G4 VM."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

from gpu.real_bcap.prepare_source import BASE_SOURCE_SHA256, METHOD_VERSION, sha256_file
from gpu.real_breward.evaluate_fixed_grid import CAPACITY_PER_SLOT, EVALUATION_EPISODES

CAMPAIGN_VERSION = "breward-full-training-v1"
MODEL_SEEDS = (200, 201, 202, 203, 204)
TREATMENTS = (("capacity_aware_alpha_0_7", 0.7), ("capacity_aware_alpha_1_0", 1.0))
REQUESTED_TIMESTEPS = 5_000_000
NUM_ENVS = 128
ROLLOUT_LEN = 50
EFFECTIVE_TIMESTEPS = (REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)) * (NUM_ENVS * ROLLOUT_LEN)
EXPECTED_UPDATES = REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)
PREDECLARATION_RELATIVE_PATH = "docs/evaluation/breward_training_predeclaration_20260728.md"
EXPECTED_GPU_NAME = "NVIDIA RTX PRO 6000 Blackwell Server Edition"
EXPECTED_RUNTIME = {
    "jax": "0.7.2",
    "jaxlib": "0.7.2",
    "numpy": "2.0.2",
    "flax": "0.11.2",
    "optax": "0.2.8",
    "chex": "0.1.92",
    "distrax": "0.1.9",
    "gymnax": "0.0.9",
    "brax": "0.14.2",
    "mujoco": "3.10.0",
    "mujoco-mjx": "3.10.0",
    "jaxopt": "0.8.5",
    "jaxmarl": "0.0.4",
    "glfw": "2.10.2",
    "trimesh": "4.12.2",
}


@dataclass(frozen=True)
class Job:
    treatment: str
    baseline_alpha: float
    observation_dimension: int
    model_seed: int

    @property
    def identity(self) -> str:
        return f"{self.treatment}__model-seed-{self.model_seed}"


def campaign_jobs() -> tuple[Job, ...]:
    return tuple(
        Job(treatment, alpha, 19, seed) for treatment, alpha in TREATMENTS for seed in MODEL_SEEDS
    )


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_approval(repo_root: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    predeclaration = repo_root / PREDECLARATION_RELATIVE_PATH
    if receipt.get("predeclaration_path") != PREDECLARATION_RELATIVE_PATH:
        raise ValueError("approval receipt names a different predeclaration")
    if receipt.get("predeclaration_sha256") != sha256_file(predeclaration):
        raise ValueError("predeclaration bytes changed after approval")
    if receipt.get("approved") is not True or receipt.get("held_out_authorised") is not False:
        raise ValueError("approval is not the exploratory B-REWARD authorization")
    for relative, digest in receipt.get("harness_sha256", {}).items():
        if sha256_file(repo_root / relative) != digest:
            raise ValueError(f"approved harness bytes changed: {relative}")
    return receipt


def _runtime() -> dict[str, Any]:
    import jax

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise RuntimeError("nvidia-smi is unavailable")
    gpu_name = subprocess.run(
        [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if gpu_name != EXPECTED_GPU_NAME:
        raise RuntimeError(f"expected Colab G4 {EXPECTED_GPU_NAME!r}, found {gpu_name!r}")
    if jax.default_backend() != "gpu":
        raise RuntimeError(f"GPU required, found {jax.default_backend()}")
    observed = {package: metadata.version(package) for package in EXPECTED_RUNTIME}
    if observed != EXPECTED_RUNTIME:
        raise RuntimeError(f"runtime differs from frozen Blackwell stack: {observed}")
    return {
        "python": platform.python_version(),
        **observed,
        "jax_backend": jax.default_backend(),
        "jax_device": str(jax.devices()[0]),
        "nvidia_gpu_name": gpu_name,
    }


def _job_files(output_root: Path, job: Job) -> dict[str, Path]:
    base = output_root / job.identity
    return {
        "csv": base.with_suffix(".csv"),
        "actor": Path(f"{base}_actor_params.npz"),
        "timing": Path(f"{base}_decision_ms_raw.npz"),
        "train_log": Path(f"{base}_train.log"),
        "grid_json": Path(f"{base}_fixed_grid_eval.json"),
        "grid_npz": Path(f"{base}_fixed_grid_actions.npz"),
        "eval_log": Path(f"{base}_fixed_grid_eval.log"),
        "manifest": Path(f"{base}_run_manifest.json"),
    }


def _validate_completed_job(output_root: Path, job: Job) -> dict[str, Any]:
    import numpy as np

    paths = _job_files(output_root, job)
    for key, path in paths.items():
        if key != "manifest" and not path.is_file():
            raise ValueError(f"{job.identity}: missing {key}")
    with paths["csv"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_UPDATES or int(rows[-1]["env_step"]) != EFFECTIVE_TIMESTEPS:
        raise ValueError(f"{job.identity}: incomplete curve")
    with np.load(paths["actor"], allow_pickle=False) as actor:
        actor_shape = list(actor["Dense_0.kernel"].shape)
    if actor_shape != [19, 64]:
        raise ValueError(f"{job.identity}: actor input shape mismatch")
    grid = json.loads(paths["grid_json"].read_text(encoding="utf-8"))
    if grid.get("scientific_evidence") is not False or len(grid.get("levels", [])) != 4:
        raise ValueError(f"{job.identity}: malformed fixed-grid diagnostic")
    if [level["capacity_per_slot"] for level in grid["levels"]] != list(CAPACITY_PER_SLOT):
        raise ValueError(f"{job.identity}: fixed-grid order mismatch")
    if any(level["episodes"] != EVALUATION_EPISODES for level in grid["levels"]):
        raise ValueError(f"{job.identity}: fixed-grid episode count mismatch")
    with np.load(paths["grid_npz"], allow_pickle=False) as fixed:
        action_shape = list(fixed["actions"].shape)
    if action_shape != [4, EVALUATION_EPISODES, 200, 20]:
        raise ValueError(f"{job.identity}: fixed-grid action tensor mismatch")
    return {
        "curve_rows": len(rows),
        "effective_timesteps": int(rows[-1]["env_step"]),
        "last_training_row": rows[-1],
        "actor_input_shape": actor_shape,
        "fixed_grid_action_shape": action_shape,
        "fixed_grid_diagnostic": grid,
        "files": {
            key: {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for key, path in paths.items()
            if key != "manifest"
        },
    }


def _run_job(
    repo_root: Path,
    source_root: Path,
    output_root: Path,
    job: Job,
    common_env: dict[str, str],
    traffictwin_commit: str,
) -> dict[str, Any]:
    paths = _job_files(output_root, job)
    env = dict(os.environ)
    env.pop("JAX_PLATFORMS", None)
    env.update(common_env)
    env["PYTHONPATH"] = str(source_root / "jaxmarl")
    env["VEC_JAX_BASELINE_ALPHA"] = str(job.baseline_alpha)
    train_command = [
        sys.executable,
        "scripts/train_mappo_vec.py",
        "--total-timesteps",
        str(REQUESTED_TIMESTEPS),
        "--num-envs",
        str(NUM_ENVS),
        "--rollout-len",
        str(ROLLOUT_LEN),
        "--lr",
        "3e-3",
        "--seed",
        str(job.model_seed),
        "--out-csv",
        str(paths["csv"]),
        "--tag",
        job.identity,
    ]
    eval_command = [
        sys.executable,
        str(repo_root / "gpu/real_breward/evaluate_fixed_grid.py"),
        "--source-root",
        str(source_root),
        "--actor",
        str(paths["actor"]),
        "--output-json",
        str(paths["grid_json"]),
        "--output-npz",
        str(paths["grid_npz"]),
    ]
    started = datetime.now(UTC).isoformat()
    start = time.monotonic()
    with paths["train_log"].open("w", encoding="utf-8") as log:
        log.write("COMMAND " + " ".join(train_command) + "\n")
        log.flush()
        trained = subprocess.run(
            train_command,
            cwd=source_root / "jaxmarl",
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if trained.returncode != 0:
        raise RuntimeError(f"{job.identity} training failed with exit code {trained.returncode}")
    with paths["eval_log"].open("w", encoding="utf-8") as log:
        log.write("COMMAND " + " ".join(eval_command) + "\n")
        log.flush()
        evaluated = subprocess.run(
            eval_command,
            cwd=repo_root,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if evaluated.returncode != 0:
        raise RuntimeError(
            f"{job.identity} evaluation failed with exit code {evaluated.returncode}"
        )
    validation = _validate_completed_job(output_root, job)
    manifest = {
        "campaign_version": CAMPAIGN_VERSION,
        "traffictwin_commit": traffictwin_commit,
        "job": asdict(job),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.monotonic() - start,
        "train_command": train_command,
        "eval_command": eval_command,
        "environment": {**common_env, "VEC_JAX_BASELINE_ALPHA": str(job.baseline_alpha)},
        "validation": validation,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    _atomic_json(paths["manifest"], manifest)
    return manifest


def run_campaign(
    repo_root: Path,
    source_root: Path,
    output_root: Path,
    receipt_path: Path,
    traffictwin_commit: str,
) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", traffictwin_commit) is None:
        raise ValueError("TrafficTwin source commit must be a full lowercase Git SHA")
    approval = verify_approval(repo_root, receipt_path)
    transformation = json.loads(
        (source_root / "bcap_source_transformation.json").read_text(encoding="utf-8")
    )
    if transformation.get("method_version") != METHOD_VERSION:
        raise ValueError("wrong B-CAP source transformation")
    patched_paths = {
        "jaxmarl/env/vec_jax.py": "patched_vec_jax_sha256",
        "jaxmarl/scripts/train_mappo_vec.py": "patched_train_mappo_vec_sha256",
    }
    for relative, expected in BASE_SOURCE_SHA256.items():
        observed = sha256_file(source_root / relative)
        required = (
            transformation.get(patched_paths[relative]) if relative in patched_paths else expected
        )
        if observed != required:
            raise ValueError(f"campaign source changed after preparation: {relative}")
    output_root.mkdir(parents=True, exist_ok=True)
    runtime = _runtime()
    common_env = {
        "VEC_JAX_BCAP_RANDOM_CAPACITY": "1",
        "VEC_JAX_BCAP_OBS": "1",
        "VEC_JAX_PRIORITY_ALPHA": "0",
        "VEC_JAX_MODEL_C": "1",
        "VEC_JAX_GREEDY_EVAL": "0",
        "VEC_JAX_SAVE_ACTOR_PARAMS": "1",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
    }
    design = {
        "campaign_version": CAMPAIGN_VERSION,
        "traffictwin_commit": traffictwin_commit,
        "status": "owner_approved_candidate_training_diagnostics",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "producer_data_used": False,
        "producer_code_used": True,
        "approval": approval,
        "source_transformation": transformation,
        "runtime": runtime,
        "jobs": [asdict(job) for job in campaign_jobs()],
        "requested_timesteps_per_job": REQUESTED_TIMESTEPS,
        "effective_timesteps_per_job": EFFECTIVE_TIMESTEPS,
        "num_envs": NUM_ENVS,
        "rollout_len": ROLLOUT_LEN,
        "learning_rate": 3e-3,
        "fixed_capacity_diagnostic": {
            "levels": list(CAPACITY_PER_SLOT),
            "episodes_per_level": EVALUATION_EPISODES,
        },
        "common_environment": common_env,
    }
    design_path = output_root / "campaign_design.json"
    if design_path.exists():
        existing = json.loads(design_path.read_text(encoding="utf-8"))
        for key in (
            "campaign_version",
            "traffictwin_commit",
            "jobs",
            "approval",
            "source_transformation",
            "requested_timesteps_per_job",
            "fixed_capacity_diagnostic",
        ):
            if existing.get(key) != design.get(key):
                raise ValueError(f"resume design mismatch: {key}")
    else:
        _atomic_json(design_path, design)
    progress_path = output_root / "campaign_progress.json"
    progress: dict[str, Any] = {
        "campaign_version": CAMPAIGN_VERSION,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "jobs": {},
    }
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    for job in campaign_jobs():
        manifest_path = _job_files(output_root, job)["manifest"]
        if manifest_path.is_file():
            _validate_completed_job(output_root, job)
            progress["jobs"][job.identity] = {"status": "completed", "resumed": True}
            _atomic_json(progress_path, progress)
            continue
        progress["jobs"][job.identity] = {
            "status": "running",
            "started_at_utc": datetime.now(UTC).isoformat(),
        }
        _atomic_json(progress_path, progress)
        try:
            manifest = _run_job(
                repo_root, source_root, output_root, job, common_env, traffictwin_commit
            )
        except Exception as exc:
            progress["jobs"][job.identity] = {
                "status": "failed",
                "failed_at_utc": datetime.now(UTC).isoformat(),
                "error": f"{type(exc).__name__}: {exc}",
            }
            _atomic_json(progress_path, progress)
            raise
        progress["jobs"][job.identity] = {
            "status": "completed",
            "completed_at_utc": manifest["completed_at_utc"],
            "elapsed_seconds": manifest["elapsed_seconds"],
        }
        _atomic_json(progress_path, progress)
    progress["status"] = "completed"
    progress["completed_at_utc"] = datetime.now(UTC).isoformat()
    _atomic_json(progress_path, progress)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--approval-receipt", type=Path, required=True)
    parser.add_argument("--traffictwin-commit", required=True)
    args = parser.parse_args()
    run_campaign(
        args.repo_root.resolve(),
        args.source_root.resolve(),
        args.output_root.resolve(),
        args.approval_receipt.resolve(),
        args.traffictwin_commit,
    )


if __name__ == "__main__":
    main()

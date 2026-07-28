"""Resumable full-scale B-CAP MAPPO campaign runner for a disposable GPU VM."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gpu.real_bcap.prepare_source import BASE_SOURCE_SHA256, METHOD_VERSION, sha256_file

CAMPAIGN_VERSION = "bcap-full-training-v1"
MODEL_SEEDS = (100, 101, 102, 103, 104)
TREATMENTS = (("random_capacity_hidden17", 0, 17), ("capacity_aware19", 1, 19))
REQUESTED_TIMESTEPS = 5_000_000
NUM_ENVS = 128
ROLLOUT_LEN = 50
EFFECTIVE_TIMESTEPS = (REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)) * (NUM_ENVS * ROLLOUT_LEN)
EXPECTED_UPDATES = REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)
PREDECLARATION_RELATIVE_PATH = "docs/evaluation/bcap_training_predeclaration_20260728.md"


@dataclass(frozen=True)
class Job:
    treatment: str
    observation_dimension: int
    observation_enabled: int
    model_seed: int

    @property
    def identity(self) -> str:
        return f"{self.treatment}__model-seed-{self.model_seed}"


def campaign_jobs() -> tuple[Job, ...]:
    return tuple(
        Job(treatment, dimension, enabled, seed)
        for treatment, enabled, dimension in TREATMENTS
        for seed in MODEL_SEEDS
    )


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def verify_approval(repo_root: Path, receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    predeclaration = repo_root / PREDECLARATION_RELATIVE_PATH
    digest = sha256_file(predeclaration)
    if receipt.get("predeclaration_path") != PREDECLARATION_RELATIVE_PATH:
        raise ValueError("approval receipt names a different predeclaration")
    if receipt.get("predeclaration_sha256") != digest:
        raise ValueError("predeclaration bytes changed after approval")
    if receipt.get("approved") is not True or receipt.get("held_out_authorised") is not False:
        raise ValueError("approval receipt is not the exploratory B-CAP authorization")
    return receipt


def _runtime() -> dict[str, Any]:
    import chex
    import flax
    import jax
    import jaxlib
    import jaxmarl
    import numpy
    import optax

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise RuntimeError("nvidia-smi is unavailable on the requested GPU runtime")
    gpu_name = subprocess.run(  # noqa: S603 - resolved fixed GPU diagnostic executable
        [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if jax.default_backend() != "gpu":
        raise RuntimeError(f"GPU required, found {jax.default_backend()}")
    return {
        "python": platform.python_version(),
        "jax": jax.__version__,
        "jaxlib": jaxlib.__version__,
        "jaxmarl": getattr(jaxmarl, "__version__", "0.0.4"),
        "numpy": numpy.__version__,
        "flax": flax.__version__,
        "optax": optax.__version__,
        "chex": chex.__version__,
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
        "greedy": Path(f"{base}_greedy_eval.json"),
        "log": Path(f"{base}.log"),
        "manifest": Path(f"{base}_run_manifest.json"),
    }


def _validate_completed_job(output_root: Path, job: Job) -> dict[str, Any]:
    import numpy as np

    paths = _job_files(output_root, job)
    for key in ("csv", "actor", "timing", "greedy", "log"):
        if not paths[key].is_file():
            raise ValueError(f"{job.identity}: missing {key}")
    with paths["csv"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_UPDATES or int(rows[-1]["env_step"]) != EFFECTIVE_TIMESTEPS:
        raise ValueError(f"{job.identity}: incomplete curve")
    actor = np.load(paths["actor"])
    if tuple(actor["Dense_0.kernel"].shape) != (job.observation_dimension, 64):
        raise ValueError(f"{job.identity}: actor input shape mismatch")
    greedy = json.loads(paths["greedy"].read_text(encoding="utf-8"))
    return {
        "curve_rows": len(rows),
        "effective_timesteps": int(rows[-1]["env_step"]),
        "last_training_row": rows[-1],
        "greedy_diagnostic": greedy,
        "actor_input_shape": list(actor["Dense_0.kernel"].shape),
        "files": {
            key: {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for key, path in paths.items()
            if key != "manifest"
        },
    }


def _run_job(
    source_root: Path, output_root: Path, job: Job, common_env: dict[str, str]
) -> dict[str, Any]:
    paths = _job_files(output_root, job)
    env = dict(os.environ)
    env.pop("JAX_PLATFORMS", None)
    env.update(common_env)
    env["PYTHONPATH"] = str(source_root / "jaxmarl")
    env["VEC_JAX_BCAP_OBS"] = str(job.observation_enabled)
    command = [
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
    started = datetime.now(UTC).isoformat()
    start = time.monotonic()
    with paths["log"].open("w", encoding="utf-8") as log:
        log.write("COMMAND " + " ".join(command) + "\n")
        log.flush()
        completed = subprocess.run(  # noqa: S603 - frozen argv, no shell
            command,
            cwd=source_root / "jaxmarl",
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if completed.returncode != 0:
        raise RuntimeError(f"{job.identity} failed with exit code {completed.returncode}")
    validation = _validate_completed_job(output_root, job)
    manifest = {
        "campaign_version": CAMPAIGN_VERSION,
        "job": asdict(job),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.monotonic() - start,
        "command": command,
        "environment": {**common_env, "VEC_JAX_BCAP_OBS": str(job.observation_enabled)},
        "validation": validation,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    _atomic_json(paths["manifest"], manifest)
    return manifest


def run_campaign(repo_root: Path, source_root: Path, output_root: Path, receipt_path: Path) -> None:
    receipt = verify_approval(repo_root, receipt_path)
    transformation = json.loads(
        (source_root / "bcap_source_transformation.json").read_text(encoding="utf-8")
    )
    if transformation.get("method_version") != METHOD_VERSION:
        raise ValueError("wrong B-CAP source transformation")
    for relative, expected in BASE_SOURCE_SHA256.items():
        if relative == "jaxmarl/env/vec_jax.py":
            continue
        if sha256_file(source_root / relative) != expected:
            raise ValueError(f"producer source changed after transformation: {relative}")
    output_root.mkdir(parents=True, exist_ok=True)
    runtime = _runtime()
    common_env = {
        "VEC_JAX_BCAP_RANDOM_CAPACITY": "1",
        "VEC_JAX_PRIORITY_ALPHA": "0",
        "VEC_JAX_MODEL_C": "1",
        "VEC_JAX_GREEDY_EVAL": "1",
        "VEC_JAX_GREEDY_EVAL_EPS": "20",
        "VEC_JAX_GREEDY_EVAL_NUM_ENVS": "16",
        "VEC_JAX_SAVE_ACTOR_PARAMS": "1",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
    }
    design = {
        "campaign_version": CAMPAIGN_VERSION,
        "status": "owner_approved_candidate_training_diagnostics",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "producer_data_used": False,
        "producer_code_used": True,
        "approval": receipt,
        "source_transformation": transformation,
        "runtime": runtime,
        "jobs": [asdict(job) for job in campaign_jobs()],
        "requested_timesteps_per_job": REQUESTED_TIMESTEPS,
        "effective_timesteps_per_job": EFFECTIVE_TIMESTEPS,
        "num_envs": NUM_ENVS,
        "rollout_len": ROLLOUT_LEN,
        "learning_rate": 3e-3,
        "common_environment": common_env,
    }
    design_path = output_root / "campaign_design.json"
    if design_path.exists():
        existing = json.loads(design_path.read_text(encoding="utf-8"))
        for key in (
            "campaign_version",
            "jobs",
            "requested_timesteps_per_job",
            "effective_timesteps_per_job",
            "num_envs",
            "rollout_len",
            "learning_rate",
            "approval",
            "source_transformation",
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
            manifest = _run_job(source_root, output_root, job, common_env)
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
    args = parser.parse_args()
    run_campaign(
        args.repo_root.resolve(),
        args.source_root.resolve(),
        args.output_root.resolve(),
        args.approval_receipt.resolve(),
    )


if __name__ == "__main__":
    main()

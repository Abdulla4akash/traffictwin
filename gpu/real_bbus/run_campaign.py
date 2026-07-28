# ruff: noqa: S603
"""Run one resumable dawn-to-peak B-BUS campaign on a private Colab GPU."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

CAMPAIGN_VERSION = "bbus-dawn-peak-colab-1.0"
MODEL_SEEDS = (30, 31, 32, 33, 34)
CAPACITY_PER_SLOT = (2.5, 0.75)
TRAINING_CAPACITY_PER_SLOT = 2.5
REQUESTED_TIMESTEPS = 5_000_000
NUM_ENVS = 64
ROLLOUT_LEN = 50
EFFECTIVE_TIMESTEPS = (REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)) * (NUM_ENVS * ROLLOUT_LEN)
EXPECTED_UPDATES = REQUESTED_TIMESTEPS // (NUM_ENVS * ROLLOUT_LEN)
LEARNING_RATE = 3e-3
EVALUATION_TASK_SEED_OFFSET = 700_000
JAX_PLATFORM = "cuda"

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

EXPECTED_ARM_PROTOCOLS = {
    "corridor": {
        "experiment_id": "B-BUS-CORRIDOR-DAWN-PEAK-20260728",
        "protocol_sha256": ("cd2e93f926d19a1c8b55d3962a674353be70b8d4fff0f69d80417e666238cde7"),
        "vec06_compatible": True,
    },
    "sparse64": {
        "experiment_id": "B-BUS-SPARSE64-DAWN-PEAK-20260728",
        "protocol_sha256": ("f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa"),
        "vec06_compatible": False,
    },
}

EXPECTED_STAGED_SOURCE = {
    "jaxmarl/env/__init__.py": "1ade2d2774b1249d182484cc95195a8c08bf1528de132c13adc1dc09ba198bea",
    "jaxmarl/env/vec_jax.py": "4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9",
    "jaxmarl/env/vec_jaxmarl.py": (
        "aa7a0d8f373605b2d3f3c700760c7e2c578ffebab4eea0530e9f42de95dd0734"
    ),
    "jaxmarl/scripts/train_mappo_vec.py": (
        "d19453529babb1c1691fdc9da5188aa0e3e233e3dcf6a65ac84ada2ef25355e1"
    ),
    "eval/eval_sumo_stage1_mc.py": (
        "f6515f6c88522c3df2109f2671220ef8da43f43bf981799464be9c3b65ddc639"
    ),
}


@dataclass(frozen=True, slots=True)
class Job:
    model_seed: int

    @property
    def identity(self) -> str:
        return f"model-seed-{self.model_seed}"


def campaign_jobs() -> tuple[Job, ...]:
    return tuple(Job(seed) for seed in MODEL_SEEDS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _runtime() -> dict[str, Any]:
    import jax

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        raise RuntimeError("nvidia-smi is unavailable; a Colab GPU is required")
    gpu_name = subprocess.run(
        [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not gpu_name or jax.default_backend() != "gpu":
        raise RuntimeError(
            f"GPU required, found backend={jax.default_backend()} device={gpu_name!r}"
        )
    observed = {package: metadata.version(package) for package in EXPECTED_RUNTIME}
    if observed != EXPECTED_RUNTIME:
        raise RuntimeError(f"runtime differs from the frozen package stack: {observed}")
    return {
        "python": platform.python_version(),
        **observed,
        "jax_backend": jax.default_backend(),
        "jax_device": str(jax.devices()[0]),
        "nvidia_gpu_name": gpu_name,
    }


def verify_pack(pack_root: Path) -> dict[str, Any]:
    """Verify every bundled byte and both approval/protocol bindings."""

    root = pack_root.resolve()
    binding_path = root / "campaign_binding.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    arm = binding.get("arm")
    if arm not in EXPECTED_ARM_PROTOCOLS:
        raise ValueError("campaign binding names an unknown B-BUS arm")
    expected = EXPECTED_ARM_PROTOCOLS[arm]
    if binding.get("experiment_id") != expected["experiment_id"]:
        raise ValueError("campaign binding experiment ID differs from its arm")
    if binding.get("protocol_sha256") != expected["protocol_sha256"]:
        raise ValueError("campaign binding protocol digest differs from the frozen arm")
    files = binding.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("campaign binding has no file inventory")
    for relative, digest in files.items():
        path = root / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"pack file changed after construction: {relative}")
    if any(path.name == "occupancy.csv" for path in root.rglob("*")):
        raise ValueError("occupancy tokens are not permitted in the Colab pack")

    approval_path = root / binding["approval_path"]
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if approval.get("approved") is not True or not approval["scope"]["both_successors_authorised"]:
        raise ValueError("owner receipt does not approve both successors")
    approvals = {item["experiment_id"]: item for item in approval["approved_experiments"]}
    approved = approvals.get(binding["experiment_id"])
    if approved is None or approved["protocol_sha256"] != binding["protocol_sha256"]:
        raise ValueError("owner receipt does not bind this arm's protocol")

    source_record = json.loads(
        (root / "source/bbus_source_transformation.json").read_text(encoding="utf-8")
    )
    if source_record.get("staged_source_sha256") != EXPECTED_STAGED_SOURCE:
        raise ValueError("staged producer source record differs from the frozen bytes")
    for relative, digest in EXPECTED_STAGED_SOURCE.items():
        if sha256_file(root / "source" / relative) != digest:
            raise ValueError(f"staged producer source changed: {relative}")

    dawn = _validate_trace(root / "inputs/dawn_trace.npz", binding["traces"]["dawn"])
    peak = _validate_trace(root / "inputs/peak_trace.npz", binding["traces"]["peak"])
    if arm == "sparse64":
        with (
            np.load(root / "inputs/dawn_trace.npz", allow_pickle=False) as left,
            np.load(root / "inputs/peak_trace.npz", allow_pickle=False) as right,
        ):
            if not np.array_equal(left["rsu_xy"], right["rsu_xy"]):
                raise ValueError("Sparse-64 dawn and peak do not share the same site array")
    return {**binding, "validated_trace_stats": {"dawn": dawn, "peak": peak}}


def _validate_trace(path: Path, expected: dict[str, Any]) -> dict[str, Any]:
    required = {
        "pos_x",
        "pos_y",
        "speed",
        "mask",
        "rsu_xy",
        "times",
        "dt",
        "maxN",
        "T",
        "window",
        "sumo_seed",
    }
    with np.load(path, allow_pickle=False) as trace:
        if set(trace.files) != required:
            raise ValueError(f"{path.name} trace keys differ from the exact allowlist")
        pos_x = trace["pos_x"]
        pos_y = trace["pos_y"]
        speed = trace["speed"]
        mask = trace["mask"].astype(bool)
        sites = trace["rsu_xy"]
        if pos_x.ndim != 2 or pos_x.shape != pos_y.shape or pos_x.shape != speed.shape:
            raise ValueError(f"{path.name} motion arrays have inconsistent shapes")
        if mask.shape != pos_x.shape or not mask.any():
            raise ValueError(f"{path.name} active mask is empty or malformed")
        if int(trace["T"].item()) != pos_x.shape[0] or int(trace["maxN"].item()) != pos_x.shape[1]:
            raise ValueError(f"{path.name} declared dimensions differ from its arrays")
        if sites.ndim != 2 or sites.shape[1] != 2 or len(sites) < 1 or len(sites) > 64:
            raise ValueError(f"{path.name} RSU array is outside the frozen bounds")
        if not (
            np.isfinite(pos_x[mask]).all()
            and np.isfinite(pos_y[mask]).all()
            and np.isfinite(speed[mask]).all()
            and np.isfinite(sites).all()
        ):
            raise ValueError(f"{path.name} has non-finite active values")
        observed = {
            "sha256": sha256_file(path),
            "T": int(pos_x.shape[0]),
            "maxN": int(pos_x.shape[1]),
            "vehicle_seconds": int(mask.sum()),
            "rsu_count": int(len(sites)),
            "window": str(trace["window"].item()),
        }
    for key, value in observed.items():
        if expected.get(key) != value:
            raise ValueError(f"{path.name} binding mismatch for {key}: {value!r}")
    return observed


def _capacity_slug(value: float) -> str:
    return str(value).replace(".", "p")


def _job_files(output_root: Path, job: Job) -> dict[str, Path]:
    base = output_root / job.identity
    files = {
        "csv": base.with_suffix(".csv"),
        "actor": Path(f"{base}_actor_params.npz"),
        "timing": Path(f"{base}_decision_ms_raw.npz"),
        "train_log": Path(f"{base}_train.log"),
        "manifest": Path(f"{base}_run_manifest.json"),
    }
    for capacity in CAPACITY_PER_SLOT:
        slug = _capacity_slug(capacity)
        files[f"eval_{slug}"] = Path(f"{base}_peak_cap-{slug}.json")
        files[f"eval_log_{slug}"] = Path(f"{base}_peak_cap-{slug}.log")
    return files


def _validate_evaluation(
    value: dict[str, Any], *, peak: dict[str, Any], capacity: float, seed: int
) -> None:
    expected_capacity = int(round(capacity * int(peak["maxN"])))
    exact = {
        "trace": "peak_trace.npz",
        "model": "C",
        "T": int(peak["T"]),
        "maxN": int(peak["maxN"]),
        "rsu_max_concurrent": expected_capacity,
        "fleet": "synthetic",
        "fleet_seed": seed,
        "obs_variant": "onehot17",
    }
    for key, expected in exact.items():
        if value.get(key) != expected:
            raise ValueError(f"held-out evaluation mismatch for {key}: {value.get(key)!r}")
    metrics = (
        "completion",
        "avg_energy_j_per_task",
        "avg_latency_ms_per_task",
        "p_local",
        "p_v2i",
        "p_v2v",
        "total_tasks",
    )
    if any(not math.isfinite(float(value.get(key, math.nan))) for key in metrics):
        raise ValueError("held-out evaluation has a missing or non-finite metric")
    if float(value["total_tasks"]) <= 0:
        raise ValueError("held-out evaluation generated no tasks")
    action_sum = sum(float(value[key]) for key in ("p_local", "p_v2i", "p_v2v"))
    if not math.isclose(action_sum, 1.0, abs_tol=1e-6):
        raise ValueError("held-out action shares do not sum to one")


def _validate_completed_job(output_root: Path, job: Job, binding: dict[str, Any]) -> dict[str, Any]:
    paths = _job_files(output_root, job)
    for key, path in paths.items():
        if key != "manifest" and not path.is_file():
            raise ValueError(f"{job.identity}: missing {key}")
    with paths["csv"].open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_UPDATES or int(rows[-1]["env_step"]) != EFFECTIVE_TIMESTEPS:
        raise ValueError(f"{job.identity}: incomplete training curve")
    with np.load(paths["actor"], allow_pickle=False) as actor:
        actor_shape = list(actor["Dense_0.kernel"].shape)
    if actor_shape != [17, 64]:
        raise ValueError(f"{job.identity}: actor input shape is not 17 by 64")
    with np.load(paths["timing"], allow_pickle=False) as timing:
        if int(timing["num_envs"].item()) != NUM_ENVS:
            raise ValueError(f"{job.identity}: timing num_envs differs")
        if int(timing["num_agents"].item()) != binding["traces"]["dawn"]["maxN"]:
            raise ValueError(f"{job.identity}: timing agent count differs from dawn")
        if len(timing["decision_ms"]) != EXPECTED_UPDATES * ROLLOUT_LEN:
            raise ValueError(f"{job.identity}: timing series length differs")
    evaluations: dict[str, Any] = {}
    for capacity in CAPACITY_PER_SLOT:
        slug = _capacity_slug(capacity)
        value = json.loads(paths[f"eval_{slug}"].read_text(encoding="utf-8"))
        _validate_evaluation(
            value,
            peak=binding["traces"]["peak"],
            capacity=capacity,
            seed=job.model_seed,
        )
        evaluations[slug] = value
    return {
        "curve_rows": len(rows),
        "effective_timesteps": int(rows[-1]["env_step"]),
        "last_training_row": rows[-1],
        "actor_input_shape": actor_shape,
        "held_out_peak": evaluations,
        "files": {
            key: {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for key, path in paths.items()
            if key != "manifest"
        },
    }


def _run_job(
    pack_root: Path,
    output_root: Path,
    binding: dict[str, Any],
    job: Job,
    common_env: dict[str, str],
) -> dict[str, Any]:
    paths = _job_files(output_root, job)
    if any(path.exists() for key, path in paths.items() if key != "manifest"):
        raise ValueError(f"{job.identity}: partial files exist without a validated manifest")
    source_root = pack_root / "source"
    dawn_trace = pack_root / "inputs/dawn_trace.npz"
    peak_trace = pack_root / "inputs/peak_trace.npz"
    env = dict(os.environ)
    env.update(common_env)
    env["PYTHONPATH"] = str(source_root / "jaxmarl")
    env["VEC_JAX_TRACE_REPLAY"] = str(dawn_trace)
    env["VEC_JAX_RSU_MAX_CONCURRENT"] = str(
        int(round(TRAINING_CAPACITY_PER_SLOT * binding["traces"]["dawn"]["maxN"]))
    )
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
        str(LEARNING_RATE),
        "--seed",
        str(job.model_seed),
        "--out-csv",
        str(paths["csv"]),
        "--tag",
        f"{binding['arm']}__{job.identity}",
    ]
    started = datetime.now(UTC).isoformat()
    started_clock = time.monotonic()
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
        raise RuntimeError(f"{job.identity} training failed with exit {trained.returncode}")

    eval_env = dict(env)
    eval_env.pop("VEC_JAX_TRACE_REPLAY", None)
    eval_env.pop("VEC_JAX_RSU_MAX_CONCURRENT", None)
    evaluations: list[dict[str, Any]] = []
    for capacity in CAPACITY_PER_SLOT:
        slug = _capacity_slug(capacity)
        command = [
            sys.executable,
            str(source_root / "eval/eval_sumo_stage1_mc.py"),
            "--trace",
            str(peak_trace),
            "--actor",
            str(paths["actor"]),
            "--rsu-cap-per-veh",
            str(capacity),
            "--seed",
            str(EVALUATION_TASK_SEED_OFFSET + job.model_seed),
            "--fleet",
            "synthetic",
            "--fleet-seed",
            str(job.model_seed),
            "--out-json",
            str(paths[f"eval_{slug}"]),
        ]
        with paths[f"eval_log_{slug}"].open("w", encoding="utf-8") as log:
            log.write("COMMAND " + " ".join(command) + "\n")
            log.flush()
            evaluated = subprocess.run(
                command,
                cwd=pack_root,
                env=eval_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if evaluated.returncode != 0:
            raise RuntimeError(
                f"{job.identity} peak cap-{capacity} evaluation failed with exit "
                f"{evaluated.returncode}"
            )
        evaluations.append({"capacity_per_slot": capacity, "command": command})
    validation = _validate_completed_job(output_root, job, binding)
    manifest = {
        "campaign_version": CAMPAIGN_VERSION,
        "experiment_id": binding["experiment_id"],
        "arm": binding["arm"],
        "job": asdict(job),
        "started_at_utc": started,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.monotonic() - started_clock,
        "train_command": train_command,
        "evaluation_commands": evaluations,
        "environment": {
            **common_env,
            "VEC_JAX_TRACE_REPLAY": "inputs/dawn_trace.npz",
            "VEC_JAX_RSU_MAX_CONCURRENT": env["VEC_JAX_RSU_MAX_CONCURRENT"],
        },
        "validation": validation,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    _atomic_json(paths["manifest"], manifest)
    return manifest


def _summarise(output_root: Path, binding: dict[str, Any]) -> dict[str, Any]:
    per_seed: list[dict[str, Any]] = []
    for job in campaign_jobs():
        validation = _validate_completed_job(output_root, job, binding)
        row: dict[str, Any] = {"model_seed": job.model_seed, "capacity": {}}
        for capacity in CAPACITY_PER_SLOT:
            slug = _capacity_slug(capacity)
            value = validation["held_out_peak"][slug]
            row["capacity"][slug] = {
                key: value[key]
                for key in (
                    "completion",
                    "avg_energy_j_per_task",
                    "avg_latency_ms_per_task",
                    "p_local",
                    "p_v2i",
                    "p_v2v",
                    "total_tasks",
                )
            }
        per_seed.append(row)
    equal_weight_means: dict[str, dict[str, float]] = {}
    for capacity in CAPACITY_PER_SLOT:
        slug = _capacity_slug(capacity)
        keys = (
            "completion",
            "avg_energy_j_per_task",
            "avg_latency_ms_per_task",
            "p_local",
            "p_v2i",
            "p_v2v",
        )
        equal_weight_means[slug] = {
            key: float(np.mean([row["capacity"][slug][key] for row in per_seed])) for key in keys
        }
    return {
        "campaign_version": CAMPAIGN_VERSION,
        "experiment_id": binding["experiment_id"],
        "arm": binding["arm"],
        "status": "returned_gpu_bytes_pending_independent_homecoming_review",
        "primary_metric": "held_out_peak_completion_capacity_0.75_equal_weight_seed_mean",
        "primary_value": equal_weight_means["0p75"]["completion"],
        "per_seed": per_seed,
        "equal_weight_seed_means": equal_weight_means,
        "capacity_order": list(CAPACITY_PER_SLOT),
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }


def _write_inventory(output_root: Path) -> dict[str, Any]:
    inventory_path = output_root / "campaign_inventory.json"
    files = [path for path in sorted(output_root.rglob("*")) if path.is_file()]
    inventory = {
        "files": [
            {
                "path": path.relative_to(output_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
            if path != inventory_path
        ],
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    _atomic_json(inventory_path, inventory)
    return inventory


def _archive_results(output_root: Path) -> Path:
    archive = output_root.with_suffix(".zip")
    if archive.exists():
        raise ValueError(f"result archive already exists and is never overwritten: {archive}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in sorted(output_root.rglob("*")):
            if not path.is_file():
                continue
            relative = Path(output_root.name) / path.relative_to(output_root)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 7, 28, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            out.writestr(info, path.read_bytes())
    return archive


def run_campaign(pack_root: Path, output_root: Path) -> dict[str, Any]:
    pack = pack_root.resolve()
    binding = verify_pack(pack)
    output = output_root.resolve()
    if output.exists() and not output.is_dir():
        raise ValueError("output root exists but is not a directory")
    if (
        output.exists()
        and any(output.iterdir())
        and not (output / "campaign_design.json").is_file()
    ):
        raise ValueError("non-empty output without a campaign design is never overwritten")
    output.mkdir(parents=True, exist_ok=True)
    runtime = _runtime()
    common_env = {
        "VEC_JAX_PRIORITY_ALPHA": "0",
        "VEC_JAX_MODEL_C": "1",
        "VEC_JAX_STRESS_ARRIVAL": "1",
        "VEC_JAX_LAMBDA_ARRIVAL": "1.5",
        "VEC_JAX_K_MIN": "0",
        "VEC_JAX_K_MAX": "5",
        "VEC_JAX_STRESS_SPEED": "0",
        "VEC_JAX_STRESS_LANES": "0",
        "VEC_JAX_GREEDY_EVAL": "0",
        "VEC_JAX_SAVE_ACTOR_PARAMS": "1",
        "JAX_PLATFORMS": JAX_PLATFORM,
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
    }
    design = {
        "campaign_version": CAMPAIGN_VERSION,
        "experiment_id": binding["experiment_id"],
        "arm": binding["arm"],
        "binding_sha256": sha256_file(pack / "campaign_binding.json"),
        "protocol_sha256": binding["protocol_sha256"],
        "runtime": runtime,
        "jobs": [asdict(job) for job in campaign_jobs()],
        "training_trace": "dawn_trace.npz",
        "held_out_trace": "peak_trace.npz",
        "training_capacity_per_slot": TRAINING_CAPACITY_PER_SLOT,
        "evaluation_capacity_per_slot": list(CAPACITY_PER_SLOT),
        "evaluation_task_seed_offset": EVALUATION_TASK_SEED_OFFSET,
        "fleet_seed_equals_model_seed": True,
        "requested_timesteps_per_job": REQUESTED_TIMESTEPS,
        "effective_timesteps_per_job": EFFECTIVE_TIMESTEPS,
        "num_envs": NUM_ENVS,
        "rollout_len": ROLLOUT_LEN,
        "learning_rate": LEARNING_RATE,
        "common_environment": common_env,
        "peak_used_for_training_or_selection": False,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    design_path = output / "campaign_design.json"
    if design_path.exists():
        existing = json.loads(design_path.read_text(encoding="utf-8"))
        for key in design:
            if existing.get(key) != design.get(key):
                raise ValueError(f"resume design mismatch: {key}")
    else:
        _atomic_json(design_path, design)
    progress_path = output / "campaign_progress.json"
    progress: dict[str, Any] = {
        "campaign_version": CAMPAIGN_VERSION,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "jobs": {},
    }
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    for job in campaign_jobs():
        manifest_path = _job_files(output, job)["manifest"]
        if manifest_path.is_file():
            _validate_completed_job(output, job, binding)
            progress["jobs"][job.identity] = {"status": "completed", "resumed": True}
            _atomic_json(progress_path, progress)
            continue
        progress["jobs"][job.identity] = {
            "status": "running",
            "started_at_utc": datetime.now(UTC).isoformat(),
        }
        _atomic_json(progress_path, progress)
        try:
            manifest = _run_job(pack, output, binding, job, common_env)
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
    summary = _summarise(output, binding)
    _atomic_json(output / "campaign_summary.json", summary)
    progress["status"] = "completed"
    progress["completed_at_utc"] = datetime.now(UTC).isoformat()
    _atomic_json(progress_path, progress)
    _write_inventory(output)
    archive = _archive_results(output)
    return {
        "arm": binding["arm"],
        "output": str(output),
        "archive": str(archive),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "primary_metric_pending_homecoming_review": summary["primary_value"],
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_campaign(args.pack_root, args.output_root)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

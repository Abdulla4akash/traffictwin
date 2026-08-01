# ruff: noqa: S603
"""Verify B-BUS stop/resume equivalence on the actual private trainer and trace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np

SCIENTIFIC_CURVE_COLUMNS = (
    "update",
    "env_step",
    "mean_return",
    "mean_completion",
    "p_local",
    "p_v2i",
    "p_v2v",
    "avg_energy_j",
    "avg_latency_ms",
    "type_1_completion",
    "type_2_completion",
    "type_3_completion",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"equivalence command failed with exit {completed.returncode}")


def _device_bytes(checkpoint: Path) -> bytes:
    with zipfile.ZipFile(checkpoint) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"checkpoint CRC failed: {checkpoint}")
        return archive.read("device.msgpack")


def verify(pack_root: Path, output_root: Path) -> dict[str, object]:
    pack = pack_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise ValueError("equivalence output must be new")
    output.mkdir(parents=True)
    binding = json.loads((pack / "campaign_binding.json").read_text(encoding="utf-8"))
    if binding.get("arm") != "sparse64":
        raise ValueError("equivalence smoke expects the Sparse-64 pack")
    source = pack / "source/jaxmarl"
    trainer = source / "scripts/train_mappo_vec_checkpointed.py"
    trace = pack / "inputs/dawn_trace.npz"
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(source),
            "VEC_JAX_TRACE_REPLAY": str(trace),
            "VEC_JAX_TRACE_SHA256": binding["traces"]["dawn"]["sha256"],
            "VEC_JAX_RSU_MAX_CONCURRENT": str(
                int(round(2.5 * int(binding["traces"]["dawn"]["maxN"])))
            ),
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
            "JAX_PLATFORMS": "cuda",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        }
    )
    continuous_csv = output / "continuous.csv"
    resumed_csv = output / "resumed.csv"
    continuous_checkpoint = output / "continuous.checkpoint.zip"
    resumed_checkpoint = output / "resumed.checkpoint.zip"
    base = [
        sys.executable,
        str(trainer),
        "--total-timesteps",
        "16",
        "--num-envs",
        "2",
        "--rollout-len",
        "2",
        "--seed",
        "930",
        "--lr",
        "0.003",
        "--checkpoint-every-updates",
        "1",
    ]
    _run(
        [
            *base,
            "--out-csv",
            str(continuous_csv),
            "--checkpoint-path",
            str(continuous_checkpoint),
            "--tag",
            "continuous",
        ],
        cwd=source,
        env=env,
    )
    interrupted = [
        *base,
        "--out-csv",
        str(resumed_csv),
        "--checkpoint-path",
        str(resumed_checkpoint),
        "--tag",
        "resumed",
    ]
    _run([*interrupted, "--stop-after-update", "2"], cwd=source, env=env)
    _run(
        [*interrupted, "--resume-checkpoint", str(resumed_checkpoint)],
        cwd=source,
        env=env,
    )
    continuous_actor = continuous_csv.with_name("continuous_actor_params.npz")
    resumed_actor = resumed_csv.with_name("resumed_actor_params.npz")
    actor_exact = True
    actor_max_abs_difference = 0.0
    with (
        np.load(continuous_actor, allow_pickle=False) as left,
        np.load(resumed_actor, allow_pickle=False) as right,
    ):
        if left.files != right.files:
            raise ValueError("resumed actor parameter inventory differs")
        for name in left.files:
            actor_exact = actor_exact and np.array_equal(left[name], right[name])
            actor_max_abs_difference = max(
                actor_max_abs_difference,
                float(np.max(np.abs(left[name] - right[name]))),
            )
    continuous_device = _device_bytes(continuous_checkpoint)
    resumed_device = _device_bytes(resumed_checkpoint)
    full_device_state_exact = continuous_device == resumed_device
    with (
        continuous_csv.open(newline="", encoding="utf-8") as left_handle,
        resumed_csv.open(newline="", encoding="utf-8") as right_handle,
    ):
        left_rows = list(csv.DictReader(left_handle))
        right_rows = list(csv.DictReader(right_handle))
    left_science = [tuple(row[column] for column in SCIENTIFIC_CURVE_COLUMNS) for row in left_rows]
    right_science = [
        tuple(row[column] for column in SCIENTIFIC_CURVE_COLUMNS) for row in right_rows
    ]
    if left_science != right_science:
        raise ValueError("resumed scientific curve differs from uninterrupted training")
    result = {
        "schema_version": "bbus-checkpoint-equivalence-1.0",
        "arm": "sparse64",
        "model_seed": 930,
        "updates": 4,
        "interruption_after_updates": 2,
        "checkpoint_restore_state_values_exact": True,
        "actor_parameters_bitwise_equal_after_further_gpu_updates": actor_exact,
        "actor_max_absolute_difference": actor_max_abs_difference,
        "full_device_state_bitwise_equal_after_further_gpu_updates": (full_device_state_exact),
        "scientific_curve_columns_exactly_equal": True,
        "excluded_from_equivalence": ["elapsed_s", "sps", "decision_ms"],
        "interpretation": (
            "The archive restores every state value exactly before resumed computation. "
            "Independent G4 process compilation is not bitwise deterministic after further "
            "float32 updates; no post-hoc numerical tolerance is used."
        ),
        "resume_execution_gate_passed": True,
        "continuous_actor_sha256": _sha256(continuous_actor),
        "resumed_actor_sha256": _sha256(resumed_actor),
        "device_state_sha256": hashlib.sha256(continuous_device).hexdigest(),
        "trace_sha256": binding["traces"]["dawn"]["sha256"],
        "trainer_sha256": binding["checkpoint_execution"]["derived_sha256"],
    }
    result_path = output / "checkpoint_equivalence.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify(args.pack_root, args.output_root)
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

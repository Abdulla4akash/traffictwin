"""Synthetic-only B-CAP Google Colab engineering smoke.

This module intentionally does not import or accept producer repositories, checkpoints,
traffic traces, bus artifacts, or TrafficTwin campaign outputs. It trains two small toy
contextual-bandit policies solely to prove the GPU harness, multi-seed discipline, proposed
17-D/19-D observation boundary, and artifact manifests before real-asset permissions exist.

The outputs are diagnostics, never scientific evidence or actor-admission candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Literal, NamedTuple, cast

import jax
import jax.numpy as jnp
import numpy as np
from jax import Array

METHOD_VERSION = "bcap-synthetic-colab-smoke-1.0"
SCHEMA_VERSION = "1.0"
CAPACITY_LEVELS = (2.5, 1.5, 1.0, 0.75)
DEFAULT_MODEL_SEEDS = (100, 101, 102, 103, 104)
DEFAULT_EVALUATION_SEEDS = (9000, 9001, 9002)
DEFAULT_UPDATES = 250
DEFAULT_BATCH_SIZE = 2048
DEFAULT_EVALUATION_BATCH_SIZE = 4096
ORIGINAL_VARIANT: Literal["original17"] = "original17"
CAPACITY_AWARE_VARIANT: Literal["capacity_aware19"] = "capacity_aware19"
ObservationVariant = Literal["original17", "capacity_aware19"]
VARIANTS: tuple[ObservationVariant, ...] = (ORIGINAL_VARIANT, CAPACITY_AWARE_VARIANT)
Params = dict[str, dict[str, Array]]


class SyntheticBatch(NamedTuple):
    """One generated full-information contextual-bandit batch."""

    original_obs: Array
    capacity_aware_obs: Array
    rewards_by_action: Array
    capacity_per_slot: Array
    rsu_headroom: Array


class AdamState(NamedTuple):
    """Minimal Adam state so the smoke has no Optax dependency."""

    first_moment: Params
    second_moment: Params
    step: Array


TrainStep = Callable[
    [Params, AdamState, Array],
    tuple[Params, AdamState, dict[str, Array]],
]


@dataclass(frozen=True)
class SmokeConfig:
    """Closed configuration for the synthetic Colab smoke."""

    model_seeds: tuple[int, ...] = DEFAULT_MODEL_SEEDS
    evaluation_seeds: tuple[int, ...] = DEFAULT_EVALUATION_SEEDS
    capacity_levels: tuple[float, ...] = CAPACITY_LEVELS
    updates: int = DEFAULT_UPDATES
    batch_size: int = DEFAULT_BATCH_SIZE
    evaluation_batch_size: int = DEFAULT_EVALUATION_BATCH_SIZE
    hidden_size: int = 64
    learning_rate: float = 0.003
    entropy_coefficient: float = 0.01
    require_gpu: bool = False

    def validate(self) -> None:
        """Refuse ambiguous or scientifically misleading smoke configurations."""

        if self.capacity_levels != CAPACITY_LEVELS:
            raise ValueError(f"capacity_levels must remain the pilot grid {CAPACITY_LEVELS}")
        _validate_seeds("model_seeds", self.model_seeds)
        _validate_seeds("evaluation_seeds", self.evaluation_seeds)
        if self.updates < 1:
            raise ValueError("updates must be positive")
        if self.batch_size < 1 or self.evaluation_batch_size < 1:
            raise ValueError("batch sizes must be positive")
        if self.hidden_size != 64:
            raise ValueError("hidden_size is fixed at 64 for the checkpoint-shape smoke")
        if not 0.0 < self.learning_rate <= 1.0:
            raise ValueError("learning_rate must be finite and in (0, 1]")
        if not 0.0 <= self.entropy_coefficient <= 1.0:
            raise ValueError("entropy_coefficient must be finite and in [0, 1]")


def _validate_seeds(label: str, seeds: tuple[int, ...]) -> None:
    if not seeds:
        raise ValueError(f"{label} must not be empty")
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{label} must be unique")
    if any(seed < 0 or seed > 2_147_483_647 for seed in seeds):
        raise ValueError(f"{label} must contain non-negative 32-bit integers")


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _git_value(arguments: Sequence[str]) -> str | None:
    git_executable = shutil.which("git")
    if git_executable is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed git argv, read-only repository metadata
            [git_executable, *arguments],
            cwd=_repository_root(),
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip()


def _runtime_identity(require_gpu: bool) -> dict[str, Any]:
    devices = [
        {
            "id": int(device.id),
            "platform": str(device.platform),
            "device_kind": str(device.device_kind),
        }
        for device in jax.devices()
    ]
    gpu_available = any(device["platform"] in {"gpu", "cuda", "rocm"} for device in devices)
    if require_gpu and not gpu_available:
        raise RuntimeError(
            "GPU required but JAX reports no GPU device; in Colab select Runtime > "
            "Change runtime type > GPU, then rerun from the first cell"
        )
    status = _git_value(["status", "--porcelain"])
    return {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "repository_commit": _git_value(["rev-parse", "HEAD"]),
        "repository_worktree_clean": status == "" if status is not None else None,
        "driver_sha256": _sha256_file(Path(__file__).resolve()),
        "jax_version": jax.__version__,
        "jaxlib_version": importlib.metadata.version("jaxlib"),
        "devices": devices,
        "gpu_requirement_requested": require_gpu,
        "gpu_requirement_met": gpu_available,
    }


def _prepare_output_dir(output_dir: Path) -> Path:
    expanded = output_dir.expanduser()
    if expanded.is_symlink():
        raise ValueError("output directory must not be a symlink")
    target = expanded.resolve()
    if target.exists() and not target.is_dir():
        raise ValueError("output path exists and is not a directory")
    if target.exists() and any(target.iterdir()):
        raise ValueError(
            "output directory must be absent or empty; existing files are never overwritten"
        )
    repo_root = _repository_root()
    forbidden_roots = (
        repo_root / ".demo",
        repo_root / "data" / "vec-fresh",
        repo_root.parent / "external",
    )
    if any(
        target == root.resolve() or root.resolve() in target.parents for root in forbidden_roots
    ):
        raise ValueError(
            "output directory must not be inside campaign, demo, or external-repository data"
        )
    target.mkdir(parents=True, exist_ok=True)
    return target


def _synthetic_batch(
    key: Array,
    batch_size: int,
    *,
    capacity_override: float | None = None,
) -> SyntheticBatch:
    """Generate a toy context without reading any external bytes."""

    keys = jax.random.split(key, 10)
    if capacity_override is None:
        capacity_index = jax.random.randint(
            keys[0],
            shape=(batch_size,),
            minval=0,
            maxval=len(CAPACITY_LEVELS),
        )
        capacity = jnp.asarray(CAPACITY_LEVELS, dtype=jnp.float32)[capacity_index]
    else:
        capacity = jnp.full((batch_size,), capacity_override, dtype=jnp.float32)

    task_size = jax.random.uniform(keys[1], (batch_size,), minval=0.2, maxval=1.0)
    urgency = jax.random.uniform(keys[2], (batch_size,), minval=0.0, maxval=1.0)
    local_capability = jax.random.uniform(keys[3], (batch_size,), minval=0.15, maxval=1.0)
    local_queue = jax.random.uniform(keys[4], (batch_size,), minval=0.0, maxval=1.0)
    v2i_quality = jax.random.uniform(keys[5], (batch_size,), minval=0.0, maxval=1.0)
    v2v_quality = jax.random.uniform(keys[6], (batch_size,), minval=0.0, maxval=1.0)
    v2v_available = jax.random.bernoulli(keys[7], p=0.82, shape=(batch_size,)).astype(jnp.float32)
    v2v_capability = jax.random.uniform(keys[8], (batch_size,), minval=0.1, maxval=1.0)
    nuisance = jax.random.uniform(keys[9], (batch_size, 9), minval=0.0, maxval=1.0)

    original_obs = jnp.concatenate(
        [
            jnp.stack(
                [
                    task_size,
                    urgency,
                    local_capability,
                    local_queue,
                    v2i_quality,
                    v2v_quality,
                    v2v_available,
                    v2v_capability,
                ],
                axis=1,
            ),
            nuisance,
        ],
        axis=1,
    )

    # This unobserved synthetic demand makes the original 17-D policy capacity-blind.
    # The proposed 19-D treatment receives both configured capacity and current headroom.
    demand = 0.4 + 2.8 * (0.65 * nuisance[:, 0] + 0.35 * urgency)
    raw_headroom = (capacity - demand) / capacity
    headroom = (jnp.clip(raw_headroom, -1.0, 1.0) + 1.0) / 2.0
    capacity_normalized = capacity / max(CAPACITY_LEVELS)
    capacity_aware_obs = jnp.concatenate(
        [original_obs, capacity_normalized[:, None], headroom[:, None]], axis=1
    )

    local_reward = 1.25 * local_capability - 0.95 * task_size - 0.75 * local_queue - 0.35 * urgency
    v2i_reward = (
        1.55 * v2i_quality
        - 0.55 * task_size
        + 0.65 * raw_headroom
        - 1.9 * jax.nn.relu(-raw_headroom)
        + 0.20 * urgency
    )
    v2v_reward_available = (
        1.15 * v2v_quality + 0.55 * v2v_capability - 0.65 * task_size - 0.30 * urgency
    )
    v2v_reward = jnp.where(v2v_available > 0.0, v2v_reward_available, -2.0)
    rewards = jnp.stack([local_reward, v2i_reward, v2v_reward], axis=1)
    return SyntheticBatch(original_obs, capacity_aware_obs, rewards, capacity, headroom)


def _glorot(key: Array, input_size: int, output_size: int) -> Array:
    limit = np.sqrt(6.0 / float(input_size + output_size))
    return jax.random.uniform(
        key,
        shape=(input_size, output_size),
        minval=-limit,
        maxval=limit,
        dtype=jnp.float32,
    )


def _init_params(key: Array, input_size: int, hidden_size: int) -> Params:
    first, second, third = jax.random.split(key, 3)
    return {
        "Dense_0": {
            "kernel": _glorot(first, input_size, hidden_size),
            "bias": jnp.zeros((hidden_size,), dtype=jnp.float32),
        },
        "Dense_1": {
            "kernel": _glorot(second, hidden_size, hidden_size),
            "bias": jnp.zeros((hidden_size,), dtype=jnp.float32),
        },
        "Dense_2": {
            "kernel": _glorot(third, hidden_size, 3),
            "bias": jnp.zeros((3,), dtype=jnp.float32),
        },
    }


def _actor_logits(params: Params, observations: Array) -> Array:
    hidden = jnp.tanh(observations @ params["Dense_0"]["kernel"] + params["Dense_0"]["bias"])
    hidden = jnp.tanh(hidden @ params["Dense_1"]["kernel"] + params["Dense_1"]["bias"])
    return hidden @ params["Dense_2"]["kernel"] + params["Dense_2"]["bias"]


def _adam_init(params: Params) -> AdamState:
    zeros = jax.tree_util.tree_map(jnp.zeros_like, params)
    return AdamState(zeros, zeros, jnp.asarray(0, dtype=jnp.int32))


def _adam_update(
    params: Params,
    gradients: Params,
    state: AdamState,
    learning_rate: float,
) -> tuple[Params, AdamState]:
    beta_one = 0.9
    beta_two = 0.999
    epsilon = 1e-8
    step = state.step + 1
    first_moment = jax.tree_util.tree_map(
        lambda moment, gradient: beta_one * moment + (1.0 - beta_one) * gradient,
        state.first_moment,
        gradients,
    )
    second_moment = jax.tree_util.tree_map(
        lambda moment, gradient: beta_two * moment + (1.0 - beta_two) * jnp.square(gradient),
        state.second_moment,
        gradients,
    )
    first_scale = 1.0 - beta_one**step
    second_scale = 1.0 - beta_two**step
    updated = jax.tree_util.tree_map(
        lambda parameter, first, second: (
            parameter
            - learning_rate * (first / first_scale) / (jnp.sqrt(second / second_scale) + epsilon)
        ),
        params,
        first_moment,
        second_moment,
    )
    return updated, AdamState(first_moment, second_moment, step)


def _make_train_step(config: SmokeConfig, variant: ObservationVariant) -> TrainStep:
    def loss_function(params: Params, batch: SyntheticBatch) -> tuple[Array, dict[str, Array]]:
        observations = (
            batch.original_obs if variant == ORIGINAL_VARIANT else batch.capacity_aware_obs
        )
        logits = _actor_logits(params, observations)
        probabilities = jax.nn.softmax(logits, axis=1)
        expected_reward_per_item = jnp.sum(probabilities * batch.rewards_by_action, axis=1)
        entropy_per_item = -jnp.sum(probabilities * jax.nn.log_softmax(logits, axis=1), axis=1)
        objective = expected_reward_per_item + config.entropy_coefficient * entropy_per_item
        loss = -jnp.mean(objective)
        greedy_actions = jnp.argmax(logits, axis=1)
        optimal_actions = jnp.argmax(batch.rewards_by_action, axis=1)
        return loss, {
            "loss": loss,
            "expected_reward": jnp.mean(expected_reward_per_item),
            "entropy": jnp.mean(entropy_per_item),
            "greedy_optimal_accuracy": jnp.mean(greedy_actions == optimal_actions),
        }

    def train_step_impl(
        params: Params,
        state: AdamState,
        key: Array,
    ) -> tuple[Params, AdamState, dict[str, Array]]:
        batch = _synthetic_batch(key, config.batch_size)
        (_, metrics), gradients = jax.value_and_grad(loss_function, has_aux=True)(params, batch)
        updated, updated_state = _adam_update(
            params, cast(Params, gradients), state, config.learning_rate
        )
        return updated, updated_state, cast(dict[str, Array], metrics)

    return cast(TrainStep, jax.jit(train_step_impl))


def _train_one(
    config: SmokeConfig,
    variant: ObservationVariant,
    seed: int,
    train_step: TrainStep,
) -> tuple[Params, list[dict[str, float | int]]]:
    input_size = 17 if variant == ORIGINAL_VARIANT else 19
    key = jax.random.PRNGKey(seed)
    key, init_key = jax.random.split(key)
    params = _init_params(init_key, input_size, config.hidden_size)
    adam_state = _adam_init(params)
    curve: list[dict[str, float | int]] = []
    for update in range(1, config.updates + 1):
        key, batch_key = jax.random.split(key)
        params, adam_state, metrics = train_step(params, adam_state, batch_key)
        curve.append(
            {
                "update": update,
                "loss": float(metrics["loss"]),
                "expected_reward": float(metrics["expected_reward"]),
                "entropy": float(metrics["entropy"]),
                "greedy_optimal_accuracy": float(metrics["greedy_optimal_accuracy"]),
            }
        )
    return params, curve


def _evaluate_one(
    params: Params,
    config: SmokeConfig,
    variant: ObservationVariant,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for evaluation_seed in config.evaluation_seeds:
        common_key = jax.random.PRNGKey(evaluation_seed)
        for capacity in config.capacity_levels:
            batch = _synthetic_batch(
                common_key,
                config.evaluation_batch_size,
                capacity_override=capacity,
            )
            observations = (
                batch.original_obs if variant == ORIGINAL_VARIANT else batch.capacity_aware_obs
            )
            actions = jnp.argmax(_actor_logits(params, observations), axis=1)
            chosen_rewards = jnp.take_along_axis(batch.rewards_by_action, actions[:, None], axis=1)[
                :, 0
            ]
            optimal_actions = jnp.argmax(batch.rewards_by_action, axis=1)
            shares = [jnp.mean(actions == action) for action in range(3)]
            rows.append(
                {
                    "evaluation_seed": evaluation_seed,
                    "capacity_per_slot": capacity,
                    "mean_reward": float(jnp.mean(chosen_rewards)),
                    "optimal_action_accuracy": float(jnp.mean(actions == optimal_actions)),
                    "p_local": float(shares[0]),
                    "p_v2i": float(shares[1]),
                    "p_v2v": float(shares[2]),
                }
            )
    return rows


def _save_curve(path: Path, curve: list[dict[str, float | int]]) -> None:
    fieldnames = (
        "update",
        "loss",
        "expected_reward",
        "entropy",
        "greedy_optimal_accuracy",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(curve)


def _save_params(path: Path, params: Params) -> None:
    flattened = {
        f"{layer}.{name}": np.asarray(value)
        for layer, tensors in params.items()
        for name, value in tensors.items()
    }
    np.savez_compressed(path, **flattened)


def _summarize_model(rows: list[dict[str, float | int | str]]) -> dict[str, float]:
    high_capacity = max(CAPACITY_LEVELS)
    low_capacity = min(CAPACITY_LEVELS)
    high_v2i = fmean(
        float(row["p_v2i"]) for row in rows if float(row["capacity_per_slot"]) == high_capacity
    )
    low_v2i = fmean(
        float(row["p_v2i"]) for row in rows if float(row["capacity_per_slot"]) == low_capacity
    )
    return {
        "mean_reward": fmean(float(row["mean_reward"]) for row in rows),
        "optimal_action_accuracy": fmean(float(row["optimal_action_accuracy"]) for row in rows),
        "p_v2i_high_capacity": high_v2i,
        "p_v2i_low_capacity": low_v2i,
        "p_v2i_low_minus_high": low_v2i - high_v2i,
    }


def _summarize_variant(model_summaries: list[dict[str, float]]) -> dict[str, Any]:
    metric_names = tuple(model_summaries[0])
    return {
        "model_count": len(model_summaries),
        "sample_unit": "synthetic_trained_model_seed",
        "metrics": {
            metric: {
                "mean": fmean(summary[metric] for summary in model_summaries),
                "population_sd": pstdev(summary[metric] for summary in model_summaries),
            }
            for metric in metric_names
        },
    }


def _design_manifest(config: SmokeConfig) -> dict[str, Any]:
    core = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "synthetic_engineering_diagnostic_only",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "external_assets_included": False,
        "producer_assets_used": False,
        "bus_assets_used": False,
        "input_kind": "generated_in_memory_synthetic_contexts",
        "observation_variants": {
            ORIGINAL_VARIANT: {
                "width": 17,
                "explicit_rsu_capacity": False,
                "explicit_rsu_headroom": False,
            },
            CAPACITY_AWARE_VARIANT: {
                "width": 19,
                "explicit_rsu_capacity": True,
                "explicit_rsu_headroom": True,
            },
        },
        "config": asdict(config),
        "limitations": [
            "Toy contextual bandit, not MAPPO or another TrafficTwin research algorithm.",
            "Synthetic contexts and rewards do not reproduce producer physics or traffic.",
            "Training and evaluation outputs are diagnostics, never scientific evidence.",
            "Synthetic actor parameters are permanently ineligible for PINNED_ACTORS.",
            "No external repository, checkpoint, trace, bus artifact, or campaign byte is used.",
        ],
    }
    return {**core, "design_fingerprint": _sha256_bytes(_canonical_json(core))}


def _write_inventory(output_dir: Path) -> dict[str, Any]:
    files = [path for path in sorted(output_dir.iterdir()) if path.name != "output_inventory.json"]
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "scientific_evidence": False,
        "files": [
            {
                "path": path.name,
                "sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
            if path.is_file()
        ],
    }
    _write_json(output_dir / "output_inventory.json", inventory)
    return inventory


def run_experiment(config: SmokeConfig, output_dir: str | Path) -> dict[str, Any]:
    """Run the bounded synthetic smoke and write non-admissible diagnostics."""

    config.validate()
    target = _prepare_output_dir(Path(output_dir))
    design = _design_manifest(config)
    execution = _runtime_identity(config.require_gpu)
    _write_json(target / "design_manifest.json", design)
    _write_json(target / "execution_manifest.json", execution)

    by_variant: dict[str, Any] = {}
    for variant in VARIANTS:
        train_step = _make_train_step(config, variant)
        model_summaries: list[dict[str, float]] = []
        for seed in config.model_seeds:
            params, curve = _train_one(config, variant, seed, train_step)
            prefix = f"{variant}__model-seed-{seed}"
            _save_curve(target / f"{prefix}__training_curve.csv", curve)
            _save_params(target / f"{prefix}__actor_params.npz", params)
            evaluation_rows = _evaluate_one(params, config, variant)
            model_summary = _summarize_model(evaluation_rows)
            model_summaries.append(model_summary)
            _write_json(
                target / f"{prefix}__greedy_eval.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "method_version": METHOD_VERSION,
                    "status": "synthetic_engineering_diagnostic_only",
                    "scientific_evidence": False,
                    "actor_admission_eligible": False,
                    "design_fingerprint": design["design_fingerprint"],
                    "observation_variant": variant,
                    "model_seed": seed,
                    "sample_unit": "synthetic_trained_model_seed",
                    "rows": evaluation_rows,
                    "model_summary": model_summary,
                },
            )
        by_variant[variant] = _summarize_variant(model_summaries)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "synthetic_engineering_diagnostic_only",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "design_fingerprint": design["design_fingerprint"],
        "model_seed_requirement_met": len(config.model_seeds) >= 5,
        "variants": by_variant,
        "interpretation": (
            "Harness diagnostic only. Differences show that the toy code path can condition "
            "on synthetic capacity features; they do not predict producer-policy behaviour."
        ),
    }
    _write_json(target / "summary.json", summary)
    inventory = _write_inventory(target)
    return {
        "output_dir": str(target),
        "design_fingerprint": design["design_fingerprint"],
        "summary": summary,
        "output_inventory": inventory,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the synthetic-only B-CAP Colab engineering smoke."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-seeds", type=int, nargs="+", default=list(DEFAULT_MODEL_SEEDS))
    parser.add_argument(
        "--evaluation-seeds",
        type=int,
        nargs="+",
        default=list(DEFAULT_EVALUATION_SEEDS),
    )
    parser.add_argument("--updates", type=int, default=DEFAULT_UPDATES)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--evaluation-batch-size", type=int, default=DEFAULT_EVALUATION_BATCH_SIZE)
    parser.add_argument("--require-gpu", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the local smoke and Colab notebook."""

    arguments = _parser().parse_args(argv)
    config = SmokeConfig(
        model_seeds=tuple(arguments.model_seeds),
        evaluation_seeds=tuple(arguments.evaluation_seeds),
        updates=arguments.updates,
        batch_size=arguments.batch_size,
        evaluation_batch_size=arguments.evaluation_batch_size,
        require_gpu=arguments.require_gpu,
    )
    result = run_experiment(config, arguments.output_dir)
    print(f"synthetic diagnostic complete: {result['output_dir']}")
    print(f"design fingerprint: {result['design_fingerprint']}")
    print("scientific evidence: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Synthetic-only B-BUS trace-replay engineering smoke.

No real bus observation, producer repository, checkpoint, traffic trace, campaign output,
or quarantine byte is accepted or read. The driver builds two deterministic toy motion
domains in memory, trains matched contextual-bandit actors, and cross-evaluates them only
to prove the GPU, trace packaging, seed, matrix, and return-artifact path.

Outputs are diagnostics, never scientific evidence or actor-admission candidates.
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

METHOD_VERSION = "bbus-synthetic-trace-smoke-1.0"
SCHEMA_VERSION = "1.0"
BUS_LIKE: Literal["bus_like_fixture"] = "bus_like_fixture"
GENERAL_TRAFFIC: Literal["general_traffic_fixture"] = "general_traffic_fixture"
TraceDomain = Literal["bus_like_fixture", "general_traffic_fixture"]
DOMAINS: tuple[TraceDomain, ...] = (BUS_LIKE, GENERAL_TRAFFIC)
DEFAULT_MODEL_SEEDS = (200, 201, 202, 203, 204)
DEFAULT_EVALUATION_SEEDS = (9100, 9101, 9102)
DEFAULT_UPDATES = 250
DEFAULT_BATCH_SIZE = 2048
DEFAULT_TRAINING_TRACE_SIZE = 32_768
DEFAULT_EVALUATION_TRACE_SIZE = 16_384
TRAINING_TRACE_SEED = 4242
Params = dict[str, dict[str, Array]]


class TraceBatch(NamedTuple):
    """Generated synthetic replay rows for one named domain."""

    observations: Array
    rewards_by_action: Array
    normalized_speed: Array
    dwell: Array
    route_phase: Array


class AdamState(NamedTuple):
    """Minimal Adam state, avoiding an Optax dependency."""

    first_moment: Params
    second_moment: Params
    step: Array


TrainStep = Callable[
    [Params, AdamState, Array, Array],
    tuple[Params, AdamState, dict[str, Array]],
]


@dataclass(frozen=True)
class TraceSmokeConfig:
    """Closed configuration for the synthetic B-BUS smoke."""

    model_seeds: tuple[int, ...] = DEFAULT_MODEL_SEEDS
    evaluation_seeds: tuple[int, ...] = DEFAULT_EVALUATION_SEEDS
    updates: int = DEFAULT_UPDATES
    batch_size: int = DEFAULT_BATCH_SIZE
    training_trace_size: int = DEFAULT_TRAINING_TRACE_SIZE
    evaluation_trace_size: int = DEFAULT_EVALUATION_TRACE_SIZE
    hidden_size: int = 64
    learning_rate: float = 0.003
    entropy_coefficient: float = 0.01
    require_gpu: bool = False

    def validate(self) -> None:
        """Refuse ambiguous or misleading configurations."""

        _validate_seeds("model_seeds", self.model_seeds)
        _validate_seeds("evaluation_seeds", self.evaluation_seeds)
        if self.updates < 1 or self.batch_size < 1:
            raise ValueError("updates and batch_size must be positive")
        if self.training_trace_size < self.batch_size:
            raise ValueError("training_trace_size must be at least batch_size")
        if self.evaluation_trace_size < 1:
            raise ValueError("evaluation_trace_size must be positive")
        if self.hidden_size != 64:
            raise ValueError("hidden_size is fixed at 64 for the checkpoint-shape smoke")
        if not 0.0 < self.learning_rate <= 1.0:
            raise ValueError("learning_rate must be in (0, 1]")
        if not 0.0 <= self.entropy_coefficient <= 1.0:
            raise ValueError("entropy_coefficient must be in [0, 1]")


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


def _array_sha256(array: Array) -> str:
    host = np.ascontiguousarray(np.asarray(array))
    header = f"{host.dtype.str}:{host.shape}".encode()
    return _sha256_bytes(header + host.tobytes())


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _repository_root() -> Path:
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    return resolved.parent


def _git_value(arguments: Sequence[str]) -> str | None:
    executable = shutil.which("git")
    if executable is None:
        return None
    try:
        completed = subprocess.run(  # noqa: S603 - fixed executable and read-only arguments
            [executable, *arguments],
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
    gpu_available = any(item["platform"] in {"gpu", "cuda", "rocm"} for item in devices)
    if require_gpu and not gpu_available:
        raise RuntimeError("GPU required but JAX reports no GPU device")
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
    root = _repository_root()
    forbidden = (root / ".demo", root / "data" / "vec-fresh", root.parent / "external")
    if any(target == item.resolve() or item.resolve() in target.parents for item in forbidden):
        raise ValueError("output directory must not be inside campaign, demo, or external data")
    target.mkdir(parents=True, exist_ok=True)
    return target


def _synthetic_trace(key: Array, size: int, domain: TraceDomain) -> TraceBatch:
    """Generate deterministic toy motion without reading external bytes."""

    if domain not in DOMAINS:
        raise ValueError(f"unknown synthetic domain: {domain}")
    keys = jax.random.split(key, 15)
    route_phase = jax.random.uniform(keys[0], (size,), minval=0.0, maxval=1.0)
    density_noise = jax.random.uniform(keys[1], (size,), minval=0.0, maxval=1.0)
    stop_wave = jnp.square(jnp.maximum(jnp.sin(route_phase * 8.0 * jnp.pi), 0.0))

    if domain == BUS_LIKE:
        dwell_probability = jnp.clip(0.03 + 0.62 * stop_wave, 0.0, 0.72)
        dwell = jax.random.bernoulli(keys[2], dwell_probability).astype(jnp.float32)
        cruise = 0.48 + 0.19 * jnp.sin(route_phase * 2.0 * jnp.pi)
        normalized_speed = jnp.clip(
            jnp.where(dwell > 0.0, 0.01, cruise + 0.07 * density_noise), 0.0, 1.0
        )
        schedule_pressure = jnp.clip(0.25 + route_phase + 0.35 * dwell, 0.0, 1.0)
        density = jnp.clip(0.25 + 0.32 * stop_wave + 0.20 * density_noise, 0.0, 1.0)
    else:
        dwell = jax.random.bernoulli(keys[2], 0.015, shape=(size,)).astype(jnp.float32)
        density = jnp.clip(0.15 + 0.78 * density_noise, 0.0, 1.0)
        normalized_speed = jnp.clip(
            0.92 - 0.68 * density + 0.06 * jnp.sin(route_phase * 6.0), 0.0, 1.0
        )
        schedule_pressure = jax.random.uniform(keys[3], (size,), minval=0.0, maxval=0.45)

    task_size = jax.random.uniform(keys[4], (size,), minval=0.15, maxval=1.0)
    urgency = jax.random.uniform(keys[5], (size,), minval=0.0, maxval=1.0)
    local_capability = jax.random.uniform(keys[6], (size,), minval=0.2, maxval=1.0)
    local_queue = jax.random.uniform(keys[7], (size,), minval=0.0, maxval=1.0)
    v2i_quality = jnp.clip(
        0.30 + 0.48 * (1.0 - normalized_speed) + 0.18 * jax.random.uniform(keys[8], (size,)),
        0.0,
        1.0,
    )
    v2v_quality = jnp.clip(
        0.18 + 0.58 * density + 0.20 * jax.random.uniform(keys[9], (size,)), 0.0, 1.0
    )
    v2v_available = jax.random.bernoulli(
        keys[10], jnp.clip(0.25 + 0.65 * density, 0.0, 0.95)
    ).astype(jnp.float32)
    v2v_capability = jax.random.uniform(keys[11], (size,), minval=0.1, maxval=1.0)
    signal_variability = jax.random.uniform(keys[12], (size,), minval=0.0, maxval=1.0)
    payload_age = jax.random.uniform(keys[13], (size,), minval=0.0, maxval=1.0)
    nuisance = jax.random.uniform(keys[14], (size, 3), minval=0.0, maxval=1.0)

    acceleration_proxy = jnp.clip(
        jnp.abs(normalized_speed - (0.55 + 0.15 * jnp.sin(route_phase * 2.0 * jnp.pi))),
        0.0,
        1.0,
    )
    observations = jnp.column_stack(
        [
            task_size,
            urgency,
            local_capability,
            local_queue,
            v2i_quality,
            v2v_quality,
            v2v_available,
            v2v_capability,
            normalized_speed,
            acceleration_proxy,
            density,
            dwell,
            schedule_pressure,
            signal_variability,
            payload_age,
            nuisance[:, 0],
            nuisance[:, 1],
        ]
    )

    local_reward = 1.20 * local_capability - 0.82 * task_size - 0.62 * local_queue - 0.28 * urgency
    v2i_reward = (
        1.45 * v2i_quality
        - 0.48 * task_size
        + 0.55 * dwell
        - 0.42 * normalized_speed
        + 0.18 * urgency
    )
    v2v_available_reward = (
        1.08 * v2v_quality
        + 0.52 * v2v_capability
        - 0.60 * task_size
        + 0.24 * density
        - 0.22 * schedule_pressure
    )
    v2v_reward = jnp.where(v2v_available > 0.0, v2v_available_reward, -2.0)
    rewards = jnp.column_stack([local_reward, v2i_reward, v2v_reward])
    return TraceBatch(observations, rewards, normalized_speed, dwell, route_phase)


def _glorot(key: Array, input_size: int, output_size: int) -> Array:
    limit = np.sqrt(6.0 / float(input_size + output_size))
    return jax.random.uniform(
        key,
        (input_size, output_size),
        minval=-limit,
        maxval=limit,
        dtype=jnp.float32,
    )


def _init_params(key: Array, hidden_size: int) -> Params:
    first, second, third = jax.random.split(key, 3)
    return {
        "Dense_0": {
            "kernel": _glorot(first, 17, hidden_size),
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
    zeros = cast(Params, jax.tree_util.tree_map(jnp.zeros_like, params))
    return AdamState(zeros, zeros, jnp.asarray(0, dtype=jnp.int32))


def _adam_update(
    params: Params,
    gradients: Params,
    state: AdamState,
    learning_rate: float,
) -> tuple[Params, AdamState]:
    beta_one, beta_two, epsilon = 0.9, 0.999, 1e-8
    step = state.step + 1
    first = cast(
        Params,
        jax.tree_util.tree_map(
            lambda moment, gradient: beta_one * moment + (1.0 - beta_one) * gradient,
            state.first_moment,
            gradients,
        ),
    )
    second = cast(
        Params,
        jax.tree_util.tree_map(
            lambda moment, gradient: beta_two * moment + (1.0 - beta_two) * jnp.square(gradient),
            state.second_moment,
            gradients,
        ),
    )
    first_scale, second_scale = 1.0 - beta_one**step, 1.0 - beta_two**step
    updated = cast(
        Params,
        jax.tree_util.tree_map(
            lambda parameter, m_one, m_two: (
                parameter
                - learning_rate * (m_one / first_scale) / (jnp.sqrt(m_two / second_scale) + epsilon)
            ),
            params,
            first,
            second,
        ),
    )
    return updated, AdamState(first, second, step)


def _make_train_step(config: TraceSmokeConfig) -> TrainStep:
    def loss_function(
        params: Params, observations: Array, rewards: Array
    ) -> tuple[Array, dict[str, Array]]:
        logits = _actor_logits(params, observations)
        probabilities = jax.nn.softmax(logits, axis=1)
        expected = jnp.sum(probabilities * rewards, axis=1)
        entropy = -jnp.sum(probabilities * jax.nn.log_softmax(logits, axis=1), axis=1)
        loss = -jnp.mean(expected + config.entropy_coefficient * entropy)
        return loss, {
            "loss": loss,
            "expected_reward": jnp.mean(expected),
            "entropy": jnp.mean(entropy),
            "greedy_optimal_accuracy": jnp.mean(
                jnp.argmax(logits, axis=1) == jnp.argmax(rewards, axis=1)
            ),
        }

    def step(
        params: Params,
        state: AdamState,
        observations: Array,
        rewards: Array,
    ) -> tuple[Params, AdamState, dict[str, Array]]:
        (_, metrics), gradients = jax.value_and_grad(loss_function, has_aux=True)(
            params, observations, rewards
        )
        updated, updated_state = _adam_update(
            params, cast(Params, gradients), state, config.learning_rate
        )
        return updated, updated_state, cast(dict[str, Array], metrics)

    return cast(TrainStep, jax.jit(step))


def _train_one(
    config: TraceSmokeConfig,
    trace: TraceBatch,
    model_seed: int,
    train_step: TrainStep,
) -> tuple[Params, list[dict[str, float | int]]]:
    key = jax.random.PRNGKey(model_seed)
    key, init_key = jax.random.split(key)
    params = _init_params(init_key, config.hidden_size)
    state = _adam_init(params)
    curve: list[dict[str, float | int]] = []
    for update in range(1, config.updates + 1):
        key, sample_key = jax.random.split(key)
        indices = jax.random.randint(
            sample_key, (config.batch_size,), 0, config.training_trace_size
        )
        params, state, metrics = train_step(
            params, state, trace.observations[indices], trace.rewards_by_action[indices]
        )
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
    config: TraceSmokeConfig,
    training_domain: TraceDomain,
) -> list[dict[str, float | int | str]]:
    rows: list[dict[str, float | int | str]] = []
    for evaluation_domain in DOMAINS:
        for evaluation_seed in config.evaluation_seeds:
            trace = _synthetic_trace(
                jax.random.PRNGKey(evaluation_seed),
                config.evaluation_trace_size,
                evaluation_domain,
            )
            actions = jnp.argmax(_actor_logits(params, trace.observations), axis=1)
            chosen = jnp.take_along_axis(trace.rewards_by_action, actions[:, None], axis=1)[:, 0]
            optimal = jnp.argmax(trace.rewards_by_action, axis=1)
            rows.append(
                {
                    "training_domain": training_domain,
                    "evaluation_domain": evaluation_domain,
                    "evaluation_seed": evaluation_seed,
                    "mean_reward": float(jnp.mean(chosen)),
                    "optimal_action_accuracy": float(jnp.mean(actions == optimal)),
                    "p_local": float(jnp.mean(actions == 0)),
                    "p_v2i": float(jnp.mean(actions == 1)),
                    "p_v2v": float(jnp.mean(actions == 2)),
                    "mean_normalized_speed": float(jnp.mean(trace.normalized_speed)),
                    "dwell_share": float(jnp.mean(trace.dwell)),
                }
            )
    return rows


def _save_curve(path: Path, curve: list[dict[str, float | int]]) -> None:
    fields = ("update", "loss", "expected_reward", "entropy", "greedy_optimal_accuracy")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(curve)


def _save_params(path: Path, params: Params) -> None:
    flattened = {
        f"{layer}.{name}": np.asarray(value)
        for layer, tensors in params.items()
        for name, value in tensors.items()
    }
    np.savez_compressed(path, **flattened)


def _save_trace_bundle(path: Path, traces: dict[TraceDomain, TraceBatch]) -> None:
    arrays: dict[str, Any] = {}
    for domain, trace in traces.items():
        arrays[f"{domain}.observations"] = np.asarray(trace.observations)
        arrays[f"{domain}.rewards_by_action"] = np.asarray(trace.rewards_by_action)
        arrays[f"{domain}.normalized_speed"] = np.asarray(trace.normalized_speed)
        arrays[f"{domain}.dwell"] = np.asarray(trace.dwell)
        arrays[f"{domain}.route_phase"] = np.asarray(trace.route_phase)
    np.savez_compressed(path, **arrays)


def _summarize_rows(rows: list[dict[str, float | int | str]]) -> dict[str, Any]:
    matrix: dict[str, Any] = {}
    for evaluation_domain in DOMAINS:
        selected = [row for row in rows if row["evaluation_domain"] == evaluation_domain]
        matrix[evaluation_domain] = {
            "mean_reward": fmean(float(row["mean_reward"]) for row in selected),
            "optimal_action_accuracy": fmean(
                float(row["optimal_action_accuracy"]) for row in selected
            ),
            "p_local": fmean(float(row["p_local"]) for row in selected),
            "p_v2i": fmean(float(row["p_v2i"]) for row in selected),
            "p_v2v": fmean(float(row["p_v2v"]) for row in selected),
        }
    return matrix


def _summarize_models(model_matrices: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        domain: {
            metric: {
                "mean": fmean(float(matrix[domain][metric]) for matrix in model_matrices),
                "population_sd": pstdev(float(matrix[domain][metric]) for matrix in model_matrices),
            }
            for metric in ("mean_reward", "optimal_action_accuracy", "p_local", "p_v2i", "p_v2v")
        }
        for domain in DOMAINS
    }


def _write_inventory(output_dir: Path) -> dict[str, Any]:
    files = [path for path in sorted(output_dir.iterdir()) if path.name != "output_inventory.json"]
    inventory = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "scientific_evidence": False,
        "files": [
            {"path": path.name, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
            for path in files
            if path.is_file()
        ],
    }
    _write_json(output_dir / "output_inventory.json", inventory)
    return inventory


def run_experiment(config: TraceSmokeConfig, output_dir: str | Path) -> dict[str, Any]:
    """Run the bounded synthetic trace-replay smoke."""

    config.validate()
    target = _prepare_output_dir(Path(output_dir))
    execution = _runtime_identity(config.require_gpu)
    traces: dict[TraceDomain, TraceBatch] = {
        domain: _synthetic_trace(
            jax.random.PRNGKey(TRAINING_TRACE_SEED), config.training_trace_size, domain
        )
        for domain in DOMAINS
    }
    trace_contract = {
        "generator": "deterministic_in_memory_synthetic_motion_v1",
        "training_trace_seed": TRAINING_TRACE_SEED,
        "domains": {
            domain: {
                "identity": "synthetic_fixture_not_observed_motion",
                "rows": config.training_trace_size,
                "observation_width": 17,
                "observation_sha256": _array_sha256(trace.observations),
                "rewards_sha256": _array_sha256(trace.rewards_by_action),
            }
            for domain, trace in traces.items()
        },
    }
    design_core = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "synthetic_engineering_diagnostic_only",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "external_assets_included": False,
        "producer_assets_used": False,
        "bus_assets_used": False,
        "real_motion_used": False,
        "input_kind": "generated_in_memory_synthetic_trace_fixtures",
        "training_domains": list(DOMAINS),
        "evaluation_domains": list(DOMAINS),
        "config": asdict(config),
        "trace_contract": trace_contract,
        "limitations": [
            "Toy contextual bandit, not MAPPO or a TrafficTwin research algorithm.",
            "Bus-like fixture is procedural and contains no observed or derived bus motion.",
            "Cross-domain differences are harness diagnostics, not distribution-shift evidence.",
            "Synthetic parameters are permanently ineligible for PINNED_ACTORS.",
            "No external repository, trace, checkpoint, bus artifact, or campaign byte is used.",
        ],
    }
    design = {
        **design_core,
        "design_fingerprint": _sha256_bytes(_canonical_json(design_core)),
    }
    _write_json(target / "design_manifest.json", design)
    _write_json(target / "execution_manifest.json", execution)
    _save_trace_bundle(target / "synthetic_training_trace_bundle.npz", traces)

    train_step = _make_train_step(config)
    summary_by_training_domain: dict[str, Any] = {}
    for training_domain, trace in traces.items():
        model_matrices: list[dict[str, Any]] = []
        for model_seed in config.model_seeds:
            params, curve = _train_one(config, trace, model_seed, train_step)
            prefix = f"train-{training_domain}__model-seed-{model_seed}"
            _save_curve(target / f"{prefix}__training_curve.csv", curve)
            _save_params(target / f"{prefix}__actor_params.npz", params)
            rows = _evaluate_one(params, config, training_domain)
            matrix = _summarize_rows(rows)
            model_matrices.append(matrix)
            _write_json(
                target / f"{prefix}__cross_domain_eval.json",
                {
                    "schema_version": SCHEMA_VERSION,
                    "method_version": METHOD_VERSION,
                    "status": "synthetic_engineering_diagnostic_only",
                    "scientific_evidence": False,
                    "actor_admission_eligible": False,
                    "design_fingerprint": design["design_fingerprint"],
                    "training_domain": training_domain,
                    "model_seed": model_seed,
                    "rows": rows,
                    "matrix": matrix,
                },
            )
        aggregated = _summarize_models(model_matrices)
        in_domain = aggregated[training_domain]["mean_reward"]["mean"]
        other_domain = next(domain for domain in DOMAINS if domain != training_domain)
        cross_domain = aggregated[other_domain]["mean_reward"]["mean"]
        summary_by_training_domain[training_domain] = {
            "model_count": len(config.model_seeds),
            "sample_unit": "synthetic_trained_model_seed",
            "evaluation_matrix": aggregated,
            "in_domain_minus_cross_domain_mean_reward": in_domain - cross_domain,
        }

    summary = {
        "schema_version": SCHEMA_VERSION,
        "method_version": METHOD_VERSION,
        "status": "synthetic_engineering_diagnostic_only",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "design_fingerprint": design["design_fingerprint"],
        "model_seed_requirement_met": len(config.model_seeds) >= 5,
        "training_domains": summary_by_training_domain,
        "interpretation": (
            "Harness diagnostic only. The matrix proves matched synthetic trace-replay and "
            "cross-domain evaluation; it says nothing about real buses or generalisation."
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
        description="Run the synthetic-only B-BUS Colab trace-replay smoke."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-seeds", type=int, nargs="+", default=list(DEFAULT_MODEL_SEEDS))
    parser.add_argument(
        "--evaluation-seeds", type=int, nargs="+", default=list(DEFAULT_EVALUATION_SEEDS)
    )
    parser.add_argument("--updates", type=int, default=DEFAULT_UPDATES)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--training-trace-size", type=int, default=DEFAULT_TRAINING_TRACE_SIZE)
    parser.add_argument("--evaluation-trace-size", type=int, default=DEFAULT_EVALUATION_TRACE_SIZE)
    parser.add_argument("--require-gpu", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    config = TraceSmokeConfig(
        model_seeds=tuple(arguments.model_seeds),
        evaluation_seeds=tuple(arguments.evaluation_seeds),
        updates=arguments.updates,
        batch_size=arguments.batch_size,
        training_trace_size=arguments.training_trace_size,
        evaluation_trace_size=arguments.evaluation_trace_size,
        require_gpu=arguments.require_gpu,
    )
    result = run_experiment(config, arguments.output_dir)
    print(f"synthetic B-BUS diagnostic complete: {result['output_dir']}")
    print(f"design fingerprint: {result['design_fingerprint']}")
    print("scientific evidence: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

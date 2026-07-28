# ruff: noqa: ANN001, ANN202, ANN204, S603
"""Common-key task-domain diagnostics for a returned 19-D B-DOMAIN actor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from itertools import combinations
from pathlib import Path

TASK_DOMAINS = ("default", "safety_dominant", "pilot_inspired")
TASK_PROBABILITIES = {
    "default": (0.20, 0.30, 0.50),
    "safety_dominant": (0.50, 0.25, 0.25),
    "pilot_inspired": (0.10, 0.20, 0.70),
}
CAPACITY_PER_SLOT = (2.5, 0.75)
EVALUATION_EPISODES = 32
EVALUATOR_SEED = 44_444_444


def _sha256_array(value: object) -> str:
    import numpy as np

    return hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest()


def evaluate_worker(
    actor_path: Path,
    task_domain: str,
    output_json: Path,
    output_npz: Path,
) -> dict[str, object]:
    """Evaluate one actor in one import-time task domain."""

    if task_domain not in TASK_DOMAINS:
        raise ValueError(f"undeclared task domain: {task_domain}")
    os.environ["VEC_JAX_TASK_DIST"] = task_domain
    os.environ["VEC_JAX_BCAP_RANDOM_CAPACITY"] = "1"
    os.environ["VEC_JAX_BCAP_OBS"] = "1"
    os.environ["VEC_JAX_MODEL_C"] = "1"
    os.environ["VEC_JAX_PRIORITY_ALPHA"] = "0"

    import flax.linen as nn
    import jax
    import jax.numpy as jnp
    import numpy as np
    from env.vec_jax import (
        ACT_N,
        EPISODE_LENGTH,
        N_VEHICLES,
        OBS_SIZE,
        TASK_ARRIVAL_PROBS,
    )
    from env.vec_jaxmarl import VECJaxMARL

    if jax.default_backend() != "gpu":
        raise RuntimeError(f"B-DOMAIN evaluation requires GPU, found {jax.default_backend()}")
    if OBS_SIZE != 19:
        raise RuntimeError(f"B-DOMAIN requires 19-D observations, found {OBS_SIZE}")
    observed_probabilities = tuple(float(value) for value in np.asarray(TASK_ARRIVAL_PROBS))
    if not np.allclose(observed_probabilities, TASK_PROBABILITIES[task_domain], atol=1e-7):
        raise RuntimeError(f"task probabilities differ for {task_domain}: {observed_probabilities}")

    class Actor(nn.Module):
        act_n: int
        hidden: int

        @nn.compact
        def __call__(self, x):
            hidden = nn.tanh(nn.Dense(self.hidden)(x))
            hidden = nn.tanh(nn.Dense(self.hidden)(hidden))
            return nn.Dense(self.act_n)(hidden)

    with np.load(actor_path, allow_pickle=False) as saved:
        params = {
            "params": {
                f"Dense_{index}": {
                    "kernel": jnp.asarray(saved[f"Dense_{index}.kernel"]),
                    "bias": jnp.asarray(saved[f"Dense_{index}.bias"]),
                }
                for index in range(3)
            }
        }
    if tuple(params["params"]["Dense_0"]["kernel"].shape) != (19, 64):
        raise ValueError("actor input layer is not the frozen 19x64 B-DOMAIN shape")

    actor = Actor(act_n=ACT_N, hidden=64)
    env = VECJaxMARL()
    agents = env.agents

    @jax.jit
    def reset_batch(keys):
        return jax.vmap(env.reset)(keys)

    @jax.jit
    def observe_batch(states):
        return jax.vmap(env.get_obs)(states)

    @jax.jit
    def step_batch(keys, states, action_dict):
        return jax.vmap(env.step_env)(keys, states, action_dict)

    @jax.jit
    def choose(obs_flat):
        return jnp.argmax(actor.apply(params, obs_flat), axis=-1)

    base_key = jax.random.PRNGKey(EVALUATOR_SEED)
    reset_keys = jax.random.split(jax.random.fold_in(base_key, 0), EVALUATION_EPISODES)
    step_keys = tuple(
        jax.random.split(jax.random.fold_in(base_key, step + 1), EVALUATION_EPISODES)
        for step in range(EPISODE_LENGTH)
    )
    capacity_actions: list[object] = []
    levels: list[dict[str, object]] = []
    started = time.perf_counter()

    for capacity in CAPACITY_PER_SLOT:
        _, states = reset_batch(reset_keys)
        ceiling = int(round(capacity * N_VEHICLES))
        states = states._replace(
            rsu_max_concurrent=jnp.full((EVALUATION_EPISODES,), ceiling, dtype=jnp.int32)
        )
        obs = observe_batch(states)
        action_steps = []
        tasks_total = 0
        tasks_completed = 0
        energy_total = 0.0
        latency_total = 0.0
        type_total = np.zeros(3, dtype=np.int64)
        type_completed = np.zeros(3, dtype=np.int64)
        action_hist = np.zeros(3, dtype=np.int64)
        done_seen = np.zeros(EVALUATION_EPISODES, dtype=bool)

        for keys in step_keys:
            obs_flat = jnp.stack([obs[name] for name in agents], axis=1).reshape(-1, OBS_SIZE)
            actions_flat = choose(obs_flat)
            actions = np.asarray(actions_flat).reshape(EVALUATION_EPISODES, N_VEHICLES)
            action_steps.append(actions.astype(np.int8))
            action_dict = {
                name: actions_flat.reshape(EVALUATION_EPISODES, N_VEHICLES)[:, index]
                for index, name in enumerate(agents)
            }
            obs, states, _, dones, info = step_batch(keys, states, action_dict)
            deadline_met = np.asarray(info["deadline_met"], dtype=bool)
            task_type = np.asarray(info["task_type"], dtype=np.int32)
            tasks_total += deadline_met.size
            tasks_completed += int(deadline_met.sum())
            energy_total += float(np.asarray(info["per_step_energy_j"]).sum())
            latency_total += float(np.asarray(info["step_latency_sum_ms"]).sum())
            action_hist += np.bincount(actions.reshape(-1), minlength=3)
            for type_index in range(3):
                task_mask = task_type == type_index
                type_total[type_index] += int(task_mask.sum())
                type_completed[type_index] += int((task_mask & deadline_met).sum())
            done_seen |= np.asarray(dones["__all__"], dtype=bool)

        if not bool(done_seen.all()):
            raise RuntimeError(f"not every {task_domain} episode terminated at {capacity}")
        action_array = np.stack(action_steps, axis=1)
        capacity_actions.append(action_array)
        levels.append(
            {
                "capacity_per_slot": capacity,
                "rsu_max_concurrent": ceiling,
                "episodes": EVALUATION_EPISODES,
                "episode_steps": EPISODE_LENGTH,
                "tasks_total": tasks_total,
                "realized_task_type_shares": [
                    int(value) / int(type_total.sum()) for value in type_total
                ],
                "mean_completion": tasks_completed / tasks_total,
                "type_1_completion": type_completed[0] / type_total[0],
                "type_2_completion": type_completed[1] / type_total[1],
                "type_3_completion": type_completed[2] / type_total[2],
                "p_local": action_hist[0] / action_hist.sum(),
                "p_v2i": action_hist[1] / action_hist.sum(),
                "p_v2v": action_hist[2] / action_hist.sum(),
                "avg_energy_j": energy_total / tasks_total,
                "avg_latency_ms": latency_total / tasks_total,
                "action_sha256": _sha256_array(action_array),
            }
        )

    actions_grid = np.stack(capacity_actions, axis=0)
    np.savez_compressed(
        output_npz,
        actions=actions_grid,
        capacity_per_slot=np.asarray(CAPACITY_PER_SLOT, dtype=np.float32),
        task_domain=np.asarray(task_domain),
        task_probabilities=np.asarray(TASK_PROBABILITIES[task_domain], dtype=np.float32),
        evaluator_seed=np.int64(EVALUATOR_SEED),
        evaluation_episodes=np.int32(EVALUATION_EPISODES),
    )
    result: dict[str, object] = {
        "task_domain": task_domain,
        "task_probabilities": list(TASK_PROBABILITIES[task_domain]),
        "levels": levels,
        "high_low_keyed_action_switch_rate": float(np.mean(actions_grid[0] != actions_grid[-1])),
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def evaluate(
    source_root: Path,
    actor_path: Path,
    training_domain: str,
    output_json: Path,
    output_npz: Path,
) -> dict[str, object]:
    """Run isolated import-time workers and combine the declared domain matrix."""

    if training_domain not in TASK_DOMAINS:
        raise ValueError(f"undeclared training domain: {training_domain}")
    worker_results: list[dict[str, object]] = []
    worker_actions: list[object] = []
    with tempfile.TemporaryDirectory(prefix="bdomain-eval-") as directory:
        temporary = Path(directory)
        for task_domain in TASK_DOMAINS:
            worker_json = temporary / f"{task_domain}.json"
            worker_npz = temporary / f"{task_domain}.npz"
            env = dict(os.environ)
            env.pop("JAX_PLATFORMS", None)
            env["PYTHONPATH"] = str(source_root / "jaxmarl")
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker-domain",
                task_domain,
                "--actor",
                str(actor_path),
                "--output-json",
                str(worker_json),
                "--output-npz",
                str(worker_npz),
            ]
            completed = subprocess.run(
                command,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"{task_domain} worker failed: {completed.stdout}\n{completed.stderr}"
                )
            result = json.loads(worker_json.read_text())
            with __import__("numpy").load(worker_npz, allow_pickle=False) as values:
                worker_actions.append(values["actions"])
            worker_results.append(result)

    import numpy as np

    actions = np.stack(worker_actions, axis=0)
    if actions.shape != (3, 2, EVALUATION_EPISODES, 200, 20):
        raise RuntimeError(f"unexpected B-DOMAIN action tensor: {actions.shape}")
    cross_domain_switch: dict[str, dict[str, float]] = {}
    for left_index, right_index in combinations(range(len(TASK_DOMAINS)), 2):
        pair = f"{TASK_DOMAINS[left_index]}__vs__{TASK_DOMAINS[right_index]}"
        cross_domain_switch[pair] = {
            str(capacity): float(
                np.mean(actions[left_index, cap_index] != actions[right_index, cap_index])
            )
            for cap_index, capacity in enumerate(CAPACITY_PER_SLOT)
        }
    np.savez_compressed(
        output_npz,
        actions=actions,
        evaluation_domains=np.asarray(TASK_DOMAINS),
        capacity_per_slot=np.asarray(CAPACITY_PER_SLOT, dtype=np.float32),
        evaluator_seed=np.int64(EVALUATOR_SEED),
        evaluation_episodes=np.int32(EVALUATION_EPISODES),
    )
    result: dict[str, object] = {
        "classification": "owner_approved_candidate_training_diagnostic",
        "scientific_evidence": False,
        "actor_admission_eligible": False,
        "producer_data_used": False,
        "actor_path": actor_path.name,
        "training_domain": training_domain,
        "evaluation_domains": worker_results,
        "evaluator_seed": EVALUATOR_SEED,
        "common_numeric_keys_across_domains_and_levels": True,
        "cross_domain_keyed_action_switch_rate_by_capacity": cross_domain_switch,
    }
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--training-domain", choices=TASK_DOMAINS)
    parser.add_argument("--worker-domain", choices=TASK_DOMAINS)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    args = parser.parse_args()
    if args.worker_domain is not None:
        result = evaluate_worker(
            args.actor.resolve(),
            args.worker_domain,
            args.output_json.resolve(),
            args.output_npz.resolve(),
        )
    else:
        if args.source_root is None or args.training_domain is None:
            parser.error("controller mode requires --source-root and --training-domain")
        result = evaluate(
            args.source_root.resolve(),
            args.actor.resolve(),
            args.training_domain,
            args.output_json.resolve(),
            args.output_npz.resolve(),
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

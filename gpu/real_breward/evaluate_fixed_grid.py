# ruff: noqa: ANN001, ANN202, ANN204, I001
"""Greedy fixed-capacity diagnostics for one returned 19-D B-CAP actor.

This evaluates synthetic producer-code environments only.  It is deliberately
separate from TrafficTwin admission and never labels its output as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

CAPACITY_PER_SLOT = (2.5, 1.5, 1.0, 0.75)
EVALUATION_EPISODES = 32
EVALUATOR_SEED = 42_424_242


def _sha256_array(value: object) -> str:
    import numpy as np

    return hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest()


def evaluate(actor_path: Path, output_json: Path, output_npz: Path) -> dict[str, object]:
    """Run one actor on common episode keys at every fixed capacity level."""

    os.environ["VEC_JAX_BCAP_RANDOM_CAPACITY"] = "1"
    os.environ["VEC_JAX_BCAP_OBS"] = "1"
    os.environ["VEC_JAX_MODEL_C"] = "1"
    os.environ["VEC_JAX_PRIORITY_ALPHA"] = "0"

    import flax.linen as nn
    import jax
    import jax.numpy as jnp
    import numpy as np

    from env.vec_jax import ACT_N, EPISODE_LENGTH, N_VEHICLES, OBS_SIZE
    from env.vec_jaxmarl import VECJaxMARL

    if jax.default_backend() != "gpu":
        raise RuntimeError(f"fixed-grid evaluation requires GPU, found {jax.default_backend()}")
    if OBS_SIZE != 19:
        raise RuntimeError(
            f"B-REWARD fixed-grid evaluator requires 19-D observations, found {OBS_SIZE}"
        )

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
        raise ValueError("actor input layer is not the frozen 19x64 B-REWARD shape")

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
                mask = task_type == type_index
                type_total[type_index] += int(mask.sum())
                type_completed[type_index] += int((mask & deadline_met).sum())
            done_seen |= np.asarray(dones["__all__"], dtype=bool)

        if not bool(done_seen.all()):
            raise RuntimeError(f"not every fixed-capacity episode terminated at {capacity}")
        action_array = np.stack(action_steps, axis=1)
        capacity_actions.append(action_array)
        levels.append(
            {
                "capacity_per_slot": capacity,
                "rsu_max_concurrent": ceiling,
                "episodes": EVALUATION_EPISODES,
                "episode_steps": EPISODE_LENGTH,
                "tasks_total": tasks_total,
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
    high_low_switch_rate = float(np.mean(actions_grid[0] != actions_grid[-1]))
    np.savez_compressed(
        output_npz,
        actions=actions_grid,
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
        "evaluator_seed": EVALUATOR_SEED,
        "common_episode_keys_across_levels": True,
        "levels": levels,
        "high_low_keyed_action_switch_rate": high_low_switch_rate,
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--actor", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source_root.resolve() / "jaxmarl"))
    result = evaluate(args.actor.resolve(), args.output_json.resolve(), args.output_npz.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

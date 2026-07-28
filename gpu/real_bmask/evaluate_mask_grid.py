# ruff: noqa: ANN001, ANN202, ANN204
"""Two-mode fixed-capacity diagnostics for a returned 19-D B-MASK actor.

Each checkpoint is evaluated on identical episode and step keys with deployment
masking both disabled and enabled. Outputs remain non-admitted engineering
diagnostics and never enter TrafficTwin's scientific evidence path.
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
EVALUATION_MODES = ("unmasked", "masked")
EVALUATION_EPISODES = 32
EVALUATOR_SEED = 43_434_343


def _sha256_array(value: object) -> str:
    import numpy as np

    return hashlib.sha256(np.asarray(value).tobytes(order="C")).hexdigest()


def evaluate(actor_path: Path, output_json: Path, output_npz: Path) -> dict[str, object]:
    """Evaluate one actor with both deployment modes on common capacity grids."""

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
        get_action_masks_arr,
    )
    from env.vec_jaxmarl import VECJaxMARL

    if jax.default_backend() != "gpu":
        raise RuntimeError(f"B-MASK evaluation requires GPU, found {jax.default_backend()}")
    if OBS_SIZE != 19:
        raise RuntimeError(f"B-MASK requires 19-D observations, found {OBS_SIZE}")

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
        raise ValueError("actor input layer is not the frozen 19x64 B-MASK shape")

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
    def masks_batch(states):
        return jax.vmap(
            lambda state: get_action_masks_arr(
                jax.random.PRNGKey(jnp.int32(state.step_count)), state
            )
        )(states)

    @jax.jit
    def choose_unmasked(obs_flat):
        return jnp.argmax(actor.apply(params, obs_flat), axis=-1)

    @jax.jit
    def choose_masked(obs_flat, mask_flat):
        logits = actor.apply(params, obs_flat)
        masked_logits = jnp.where(mask_flat > 0.5, logits, jnp.float32(-1e9))
        return jnp.argmax(masked_logits, axis=-1)

    base_key = jax.random.PRNGKey(EVALUATOR_SEED)
    reset_keys = jax.random.split(jax.random.fold_in(base_key, 0), EVALUATION_EPISODES)
    step_keys = tuple(
        jax.random.split(jax.random.fold_in(base_key, step + 1), EVALUATION_EPISODES)
        for step in range(EPISODE_LENGTH)
    )
    mode_actions: list[object] = []
    mode_results: list[dict[str, object]] = []
    started = time.perf_counter()

    for mode in EVALUATION_MODES:
        capacity_actions: list[object] = []
        levels: list[dict[str, object]] = []
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
            selected_infeasible = 0
            v2i_available = 0
            v2v_available = 0
            decisions_total = 0
            done_seen = np.zeros(EVALUATION_EPISODES, dtype=bool)

            for keys in step_keys:
                obs_flat = jnp.stack([obs[name] for name in agents], axis=1).reshape(-1, OBS_SIZE)
                masks = masks_batch(states)
                masks_flat = masks.reshape(-1, ACT_N)
                if mode == "masked":
                    actions_flat = choose_masked(obs_flat, masks_flat)
                else:
                    actions_flat = choose_unmasked(obs_flat)
                actions = np.asarray(actions_flat).reshape(EVALUATION_EPISODES, N_VEHICLES)
                masks_np = np.asarray(masks)
                action_steps.append(actions.astype(np.int8))
                selected = np.take_along_axis(masks_np, actions[..., None], axis=2)[..., 0]
                selected_infeasible += int((selected < 0.5).sum())
                v2i_available += int(masks_np[..., 1].sum())
                v2v_available += int(masks_np[..., 2].sum())
                decisions_total += actions.size
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
                raise RuntimeError(f"not every {mode} episode terminated at {capacity}")
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
                    "selected_infeasible_rate": selected_infeasible / decisions_total,
                    "v2i_available_rate": v2i_available / decisions_total,
                    "v2v_available_rate": v2v_available / decisions_total,
                    "action_sha256": _sha256_array(action_array),
                }
            )
        grid = np.stack(capacity_actions, axis=0)
        mode_actions.append(grid)
        mode_results.append(
            {
                "mode": mode,
                "levels": levels,
                "high_low_keyed_action_switch_rate": float(np.mean(grid[0] != grid[-1])),
            }
        )

    actions_grid = np.stack(mode_actions, axis=0)
    within_actor_switch = [
        float(np.mean(actions_grid[0, index] != actions_grid[1, index]))
        for index in range(len(CAPACITY_PER_SLOT))
    ]
    if any(level["selected_infeasible_rate"] != 0.0 for level in mode_results[1]["levels"]):
        raise RuntimeError("masked deployment selected at least one infeasible action")
    np.savez_compressed(
        output_npz,
        actions=actions_grid,
        capacity_per_slot=np.asarray(CAPACITY_PER_SLOT, dtype=np.float32),
        evaluation_modes=np.asarray(EVALUATION_MODES),
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
        "common_episode_keys_across_modes_and_levels": True,
        "evaluation_modes": mode_results,
        "within_actor_unmasked_to_masked_action_switch_rate_by_capacity": dict(
            zip((str(value) for value in CAPACITY_PER_SLOT), within_actor_switch, strict=True)
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
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

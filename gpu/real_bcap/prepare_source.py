# ruff: noqa: E501
"""Fail-closed B-CAP transformation for an uploaded copy of Randy's JAX source.

The pinned external clone is never modified.  This module accepts a disposable source
copy, verifies every producer file used by the campaign, and applies the reviewed B-CAP
state/observation change only when the base bytes match exactly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

METHOD_VERSION = "bcap-random-capacity-observation-blackwell-v2"

BASE_SOURCE_SHA256 = {
    "jaxmarl/env/__init__.py": "1ade2d2774b1249d182484cc95195a8c08bf1528de132c13adc1dc09ba198bea",
    "jaxmarl/env/vec_jax.py": "4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9",
    "jaxmarl/env/vec_jaxmarl.py": "aa7a0d8f373605b2d3f3c700760c7e2c578ffebab4eea0530e9f42de95dd0734",
    "jaxmarl/scripts/train_mappo_vec.py": "b36079f495e663353398453357b2c42c54431769dcb6d208b259a592df53de12",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one source match, found {count}")
    return source.replace(old, new, 1)


def patch_vec_jax_text(source: str) -> str:
    """Return the reviewed B-CAP variant, refusing any unexpected source layout."""

    source = _replace_once(
        source,
        """CAP_SCALAR_ENABLED = os.environ.get("VEC_JAX_CAP_SCALAR", "0") == "1"\nTIER_CAP_SCALAR = jnp.array([0.0751, 0.4847, 1.0])\nOBS_SIZE = 13 if CAP_SCALAR_ENABLED else 17\n""",
        """CAP_SCALAR_ENABLED = os.environ.get("VEC_JAX_CAP_SCALAR", "0") == "1"\nTIER_CAP_SCALAR = jnp.array([0.0751, 0.4847, 1.0])\n# TrafficTwin B-CAP v1: dynamics randomize the per-episode RSU ceiling\n# independently of whether the actor observes it. This gives the matched\n# 17-D hidden-capacity control and 19-D aware treatment the same grid.\n+BCAP_RANDOM_CAPACITY_ENABLED = os.environ.get(\n+    "VEC_JAX_BCAP_RANDOM_CAPACITY", "0") == "1"\n+BCAP_OBS_ENABLED = os.environ.get("VEC_JAX_BCAP_OBS", "0") == "1"\n+BCAP_CAPACITY_PER_SLOT_GRID = jnp.array([2.5, 1.5, 1.0, 0.75], dtype=jnp.float32)\n+if CAP_SCALAR_ENABLED and BCAP_OBS_ENABLED:\n+    raise ValueError("B-CAP observation cannot be combined with VEC_JAX_CAP_SCALAR")\n+OBS_SIZE = 19 if BCAP_OBS_ENABLED else (13 if CAP_SCALAR_ENABLED else 17)\n""".replace(
            "+", ""
        ),
        "B-CAP flags",
    )
    source = _replace_once(
        source,
        "    rsu_busy_ms: jax.Array     # float [N_RSUS]\n"
        "    rsu_load: jax.Array        # int32 [N_RSUS]\n"
        "    # Current tasks",
        "    rsu_busy_ms: jax.Array     # float [N_RSUS]\n"
        "    rsu_load: jax.Array        # int32 [N_RSUS]\n"
        "    rsu_max_concurrent: jax.Array  # int32 scalar, fixed for an episode\n"
        "    # Current tasks",
        "state field",
    )
    source = _replace_once(
        source,
        "    rsu_not_saturated = rsu_load_selected < RSU_MAX_CONCURRENT\n",
        "    rsu_not_saturated = rsu_load_selected < state.rsu_max_concurrent\n",
        "saturation predicate",
    )
    source = _replace_once(
        source,
        "        rsu_load_selected.astype(jnp.float32) / float(RSU_MAX_CONCURRENT),\n",
        "        rsu_load_selected.astype(jnp.float32)\n"
        "        / jnp.maximum(state.rsu_max_concurrent.astype(jnp.float32), 1.0),\n",
        "load normalization",
    )
    source = _replace_once(
        source,
        "    (_, v2i_q, _, _,\n"
        "     best_v2v_idx, v2v_q, _, best_v2v_ok,\n"
        "     all_v2v_q, _, _) = compute_per_vehicle_links(key, state)\n",
        "    (_, v2i_q, _, _,\n"
        "     best_v2v_idx, v2v_q, _, best_v2v_ok,\n"
        "     all_v2v_q, _, best_rsu_load_frac) = compute_per_vehicle_links(key, state)\n",
        "observation link result",
    )
    source = _replace_once(
        source,
        "    obs = jnp.concatenate([obs, v2v_tier_feat], axis=1)                   # [N, 17|13]\n"
        "    return obs\n",
        "    obs = jnp.concatenate([obs, v2v_tier_feat], axis=1)                   # [N, 17|13]\n"
        "    if BCAP_OBS_ENABLED:\n"
        "        capacity_per_slot = (\n"
        "            state.rsu_max_concurrent.astype(jnp.float32) / float(N_VEHICLES)\n"
        "        )\n"
        "        capacity_norm = jnp.clip(capacity_per_slot / 2.5, 0.0, 1.0)\n"
        "        capacity_feat = jnp.full((N_VEHICLES, 1), capacity_norm, dtype=jnp.float32)\n"
        "        # No-RSU semantics are zero; otherwise expose remaining headroom.\n"
        "        headroom = jnp.where(v2i_q > 0.0, 1.0 - best_rsu_load_frac, 0.0)\n"
        "        obs = jnp.concatenate([obs, capacity_feat, headroom[:, None]], axis=1)\n"
        "    return obs\n",
        "observation features",
    )
    source = _replace_once(
        source,
        "    k_fleet, k_pos, k_spd, k_task, k_lane, k_obs = jax.random.split(key, 6)\n",
        "    k_fleet, k_pos, k_spd, k_task, k_lane, k_obs, k_capacity = jax.random.split(key, 7)\n",
        "reset keys",
    )
    source = _replace_once(
        source,
        "    last_task_type = task_type  # Markov: prev type for first transition\n\n"
        "    state = EnvState(\n",
        "    last_task_type = task_type  # Markov: prev type for first transition\n"
        "    if BCAP_RANDOM_CAPACITY_ENABLED:\n"
        "        capacity_idx = jax.random.randint(\n"
        "            k_capacity, (), 0, BCAP_CAPACITY_PER_SLOT_GRID.shape[0])\n"
        "        capacity_per_slot = BCAP_CAPACITY_PER_SLOT_GRID[capacity_idx]\n"
        "        rsu_max_concurrent = jnp.rint(\n"
        "            capacity_per_slot * float(N_VEHICLES)).astype(jnp.int32)\n"
        "    else:\n"
        "        rsu_max_concurrent = jnp.int32(RSU_MAX_CONCURRENT)\n\n"
        "    state = EnvState(\n",
        "capacity sampling",
    )
    source = _replace_once(
        source,
        "        rsu_busy_ms=jnp.zeros(N_RSUS, dtype=jnp.float32),\n"
        "        rsu_load=jnp.zeros(N_RSUS, dtype=jnp.int32),\n"
        "        task_type=task_type,\n",
        "        rsu_busy_ms=jnp.zeros(N_RSUS, dtype=jnp.float32),\n"
        "        rsu_load=jnp.zeros(N_RSUS, dtype=jnp.int32),\n"
        "        rsu_max_concurrent=rsu_max_concurrent,\n"
        "        task_type=task_type,\n",
        "reset state",
    )
    source = source.replace(
        "    rsu_capacity = jnp.maximum(RSU_MAX_CONCURRENT - state.rsu_load, 0)\n",
        "    rsu_capacity = jnp.maximum(state.rsu_max_concurrent - state.rsu_load, 0)\n",
    )
    source = source.replace(
        "        rsu_cap = jnp.maximum(RSU_MAX_CONCURRENT - s.rsu_load, 0)\n",
        "        rsu_cap = jnp.maximum(s.rsu_max_concurrent - s.rsu_load, 0)\n",
    )
    if (
        "RSU_MAX_CONCURRENT - state.rsu_load" in source
        or "RSU_MAX_CONCURRENT - s.rsu_load" in source
    ):
        raise ValueError("dynamic-capacity replacement incomplete")
    state_block = (
        "        rsu_busy_ms=new_rsu_busy_ms,\n"
        "        rsu_load=new_rsu_load,\n"
        "        task_type=next_types,\n"
    )
    if source.count(state_block) != 2:
        raise ValueError("state propagation: expected exactly two constructors")
    source = source.replace(
        state_block,
        "        rsu_busy_ms=new_rsu_busy_ms,\n"
        "        rsu_load=new_rsu_load,\n"
        "        rsu_max_concurrent=state.rsu_max_concurrent,\n"
        "        task_type=next_types,\n",
    )
    compile(source, "vec_jax.py", "exec")
    return source


def patch_train_mappo_text(source: str) -> str:
    """Restore the removed JAX tree-map alias used by JaxMARL 0.0.4."""

    return _replace_once(
        source,
        "    import jax\n    import jax.numpy as jnp\n",
        "    import jax\n"
        "    # JaxMARL 0.0.4 calls the alias removed in JAX 0.6. The operation\n"
        "    # is unchanged; restore the name for the frozen Blackwell stack.\n"
        '    if not hasattr(jax, "tree_map"):\n'
        "        jax.tree_map = jax.tree_util.tree_map\n"
        "    import jax.numpy as jnp\n",
        "Blackwell JaxMARL compatibility alias",
    )


def prepare_source(source_root: Path) -> dict[str, object]:
    source_root = source_root.resolve()
    actual = {relative: sha256_file(source_root / relative) for relative in BASE_SOURCE_SHA256}
    if actual != BASE_SOURCE_SHA256:
        raise ValueError(f"producer source bytes do not match the audited inputs: {actual}")
    target = source_root / "jaxmarl/env/vec_jax.py"
    patched = patch_vec_jax_text(target.read_text(encoding="utf-8"))
    target.write_text(patched, encoding="utf-8")
    train_target = source_root / "jaxmarl/scripts/train_mappo_vec.py"
    patched_train = patch_train_mappo_text(train_target.read_text(encoding="utf-8"))
    train_target.write_text(patched_train, encoding="utf-8")
    record = {
        "method_version": METHOD_VERSION,
        "base_source_sha256": BASE_SOURCE_SHA256,
        "patched_vec_jax_sha256": sha256_file(target),
        "patched_train_mappo_vec_sha256": sha256_file(train_target),
        "producer_clone_modified": False,
        "disposable_copy_only": True,
    }
    (source_root / "bcap_source_transformation.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_source(args.source_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

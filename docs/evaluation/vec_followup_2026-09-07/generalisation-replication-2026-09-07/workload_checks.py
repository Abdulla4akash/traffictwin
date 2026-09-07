"""Reconstruct RSU work independently of scheduler/admission decisions."""
import hashlib
import json
from pathlib import Path
import sys

import jax
import jax.numpy as jnp
import numpy as np

ROOT = Path(__file__).resolve().parent
CODE = ROOT.parent / "vec_env-state-delay-run"
sys.path.insert(0, str(CODE / "jaxmarl/env"))
import vec_jax as V


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_reference(path, steps=10800, vehicles=215, evaluator_seed=0):
    V.N_VEHICLES = vehicles
    first, _ = jax.random.split(jax.random.PRNGKey(evaluator_seed))

    def one(key, _):
        key, kt, ka, kl, ko, kp, kslots = jax.random.split(key, 7)
        types, _ = V._sample_k_max_task_slots(kslots)
        action_keys = jax.random.split(ka, 5)

        def slot_work(k, types):
            subkeys = jax.random.split(k, vehicles)
            rsu_keys = jax.vmap(lambda sk: jax.random.split(sk, 5)[1])(subkeys)
            return jax.vmap(V.compute_time_ms, in_axes=(0, 0, None))(
                rsu_keys, types, jnp.int32(V.RSU_TIER_IDX))

        work = jax.vmap(slot_work)(action_keys, types)
        return key, (types.astype(jnp.int8), work)

    _, (types, work) = jax.jit(lambda: jax.lax.scan(one, first, None, length=steps))()
    np.savez_compressed(path, task_type=np.asarray(types), service_ms=np.asarray(work))


@jax.jit
def replay(work, admitted, target):
    rsus = 9

    def second(carry, xs):
        start, load = carry

        def slot(carry, xs):
            busy, count = carry
            cms, adm, dest = xs
            inc = jnp.zeros(rsus, jnp.float32).at[dest].add(jnp.where(adm, cms, 0))
            inc_count = jnp.zeros(rsus, jnp.int32).at[dest].add(adm.astype(jnp.int32))
            return (busy+inc, count+inc_count), (busy, inc)

        (before_drain, load), (substep_start, increments) = jax.lax.scan(slot, (start, load), xs)
        served = jnp.minimum(before_drain, jnp.float32(1000))
        remaining = before_drain-served
        fraction = jnp.where(before_drain > 0, served/jnp.maximum(before_drain, 1e-6), 0)
        departed = jnp.where(remaining <= 0, load, jnp.floor(load.astype(jnp.float32)*fraction).astype(jnp.int32))
        after_load = jnp.maximum(load-departed, 0)
        after_load = jnp.where((remaining > 0) & (after_load == 0), 1, after_load)
        return (remaining, after_load), (start, before_drain, remaining, after_load, served, substep_start, increments)

    _, values = jax.lax.scan(second, (jnp.zeros(rsus), jnp.zeros(rsus, jnp.int32)), (work, admitted, target))
    return values


def validate(directory, m, cell, steps, reference_file=None, write_to=None):
    directory = Path(directory)
    reference_file = Path(reference_file or ROOT / "service_reference.npz")
    summary = json.loads((directory / "summary.json").read_text())
    with np.load(reference_file) as z:
        work, types = z["service_ms"][:steps], z["task_type"][:steps]
    with np.load(directory / "per_task.npz") as task:
        if not np.array_equal(task["task_type"], types):
            raise RuntimeError("Task-type stream differs from independent reference")
        admitted = task["task_v2i_admitted"]
        execution = task["task_execution_rsu"]
        selected = task["task_selected_execution_rsu"]
        offered = task["task_ingress_rsu"] >= 0
    arrays = replay(jnp.asarray(work), jnp.asarray(admitted), jnp.asarray(execution))
    start, pre, remaining, load, served, substart, increments = [np.asarray(a) for a in arrays]
    tolerance = m["validation"]
    with np.load(directory / "per_step.npz") as step:
        error = float(np.max(np.abs(remaining.astype(np.float64)-step["rsu_busy_ms"])))
        if error > tolerance["queue_endpoint_atol_ms"]:
            raise RuntimeError(f"Reconstructed RSU queue endpoint differs by {error} ms")
        if not np.array_equal(load, step["rsu_load"]):
            raise RuntimeError("Reconstructed RSU task-count carry differs")
        pre_error = None
        if "rsu_pre_drain_busy_ms" in step:
            pre_error = float(np.max(np.abs(pre.astype(np.float64)-step["rsu_pre_drain_busy_ms"])))
            if pre_error > tolerance["queue_endpoint_atol_ms"]:
                raise RuntimeError(f"Reconstructed pre-drain work differs by {pre_error} ms")
    admitted_ms = float(work[admitted].sum(dtype=np.float64))
    offered_ms = float(work[offered].sum(dtype=np.float64))
    for observed, expected, name in ((admitted_ms, summary["work_ms"]["v2i_admitted"], "admitted"),
                                     (offered_ms, summary["work_ms"]["v2i_offered"], "offered")):
        if not np.isclose(observed, expected, rtol=tolerance["accumulated_work_rtol"], atol=tolerance["accumulated_work_atol_ms"]):
            raise RuntimeError(f"Reconstructed {name} RSU service-work total differs")
    served_ms = float(served.sum(dtype=np.float64))
    residual_ms = float(remaining[-1].sum(dtype=np.float64))
    balance_error = admitted_ms-served_ms-residual_ms
    if not np.isclose(admitted_ms, served_ms+residual_ms, rtol=tolerance["accumulated_work_rtol"], atol=tolerance["accumulated_work_atol_ms"]):
        raise RuntimeError("RSU admitted work is not conserved as served plus remaining")
    common_checks = None
    if cell["mode"] == "dla":
        has_target = (selected >= 0).any(axis=2)
        low = np.where(selected >= 0, selected, 32767).min(axis=2)
        high = selected.max(axis=2)
        if not np.array_equal(low[has_target], high[has_target]):
            raise RuntimeError("Common-target arm uses more than one RSU in a substep")
        target_work = np.take_along_axis(substart, np.clip(high, 0, 8)[..., None], axis=2)[..., 0]
        excess = (target_work-substart.min(axis=2))[has_target]
        if len(excess) and float(excess.max()) > tolerance["queue_endpoint_atol_ms"]:
            raise RuntimeError("Common target is not a least-workload RSU")
        common_checks = {"single_destination_per_substep": "exact", "maximum_excess_above_minimum_ms": float(excess.max()) if len(excess) else 0}
    work_rsu = increments.sum(axis=(0, 1), dtype=np.float64)
    result = {"status": "passed", "steps": steps, "service_reference_sha256": sha(reference_file),
              "workload_check_script_sha256": sha(__file__), "maximum_queue_endpoint_error_ms": error,
              "maximum_pre_drain_error_ms": pre_error, "task_count_carry": "exact",
              "offered_work_ms": offered_ms, "admitted_work_ms": admitted_ms,
              "admitted_summary_difference_ms": admitted_ms-summary["work_ms"]["v2i_admitted"],
              "served_work_ms": served_ms, "final_remaining_ms": residual_ms, "balance_error_ms": balance_error,
              "common_target_checks": common_checks,
              "admitted_work_ms_per_rsu": work_rsu.tolist(),
              "admitted_work_share_per_rsu": (work_rsu/work_rsu.sum()).tolist(),
              "mean_post_batch_workload_ms_per_rsu": pre.mean(axis=0, dtype=np.float64).tolist(),
              "p95_post_batch_workload_ms_per_rsu": np.percentile(pre, 95, axis=0).tolist(),
              "maximum_post_batch_workload_ms_per_rsu": pre.max(axis=0).tolist(),
              "service_utilisation_per_rsu": (served.sum(axis=0, dtype=np.float64)/(1000*steps)).tolist()}
    Path(write_to or directory / "workload_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    return result

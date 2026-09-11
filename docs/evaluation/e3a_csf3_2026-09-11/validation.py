"""Independent accounting for the bounded incident E3a records.

Adapted from joint_confirmation_2026-09-08/confirmation/validation.py without
changing that historical validator or its records. This validator imports no
evaluator. Incident tolerances are declared before execution: work conservation
atol=1 ms, rtol=1e-4; drain endpoints atol=0.1 ms, rtol=0. Integer, admission,
deadline, exogenous-input and carried-state identities remain exact.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

Json = dict[str, Any]
Arrays = dict[str, np.ndarray]

ARMS = ("ingress_dla", "per_task_dla", "p2c_dla")
FILES = ("summary.json", "per_step.npz", "per_task.npz")
WORK_ATOL_MS = 1.0
WORK_RTOL = 1e-4
ENDPOINT_ATOL_MS = 0.1


def sha(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_hash(array: np.ndarray) -> str:
    array = np.ascontiguousarray(array)
    digest = hashlib.sha256(str((array.shape, array.dtype.str)).encode())
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def need(condition: object, message: str) -> None:
    if not bool(condition):
        raise ValueError(message)


def exact_count(value: float, expected: int, name: str) -> None:
    need(np.isfinite(value) and value == expected, f"Integer count mismatch: {name}")


def carry_count(work: np.ndarray, count: np.ndarray) -> np.ndarray:
    drain = np.minimum(work, np.float32(1000))
    remaining = work - drain
    fraction = np.where(work > 0, drain / np.maximum(work, np.float32(1e-6)), np.float32(0))
    departed = np.where(
        remaining <= 0, count, np.floor(count.astype(np.float32) * fraction).astype(np.int32)
    )
    result = np.maximum(count - departed, 0)
    return np.where((remaining > 0) & (result == 0), 1, result)


def work_conserved(
    actual: np.ndarray, before: np.ndarray, enqueued: np.ndarray, name: str
) -> float:
    expected = before.astype(np.float64) + enqueued
    error = actual.astype(np.float64) - expected
    need(
        np.allclose(actual, expected, atol=WORK_ATOL_MS, rtol=WORK_RTOL),
        f"{name} service conservation: {np.max(np.abs(error))}",
    )
    return float(np.max(np.abs(error)))


def validate_cell(destination: str | Path, config: Json) -> Json:
    """Validate observed records; return counts and hashes, never array payloads."""
    destination = Path(destination)
    summary = json.loads((destination / "summary.json").read_text())
    with np.load(destination / "per_step.npz", allow_pickle=False) as archive:
        step = {key: archive[key] for key in archive.files}
    with np.load(destination / "per_task.npz", allow_pickle=False) as archive:
        task = {key: archive[key] for key in archive.files}
    t, n, r, kmax = config["steps"], config["n_vehicles"], config["n_rsus"], 5
    arm = config["arm"]
    need(arm in ARMS and t > 0 and n > 0 and r > 0, "Unsupported cell dimensions or arm")
    shape = (t, kmax, n)
    bools = [
        "task_active",
        "task_met",
        "task_v2i_admitted",
        "task_forwarded",
        "task_final_admitted",
    ]
    floats = [
        "task_lat_ms",
        "task_sizes_mb",
        "task_rsu_service_ms",
        "task_local_service_ms",
        "task_v2v_service_ms",
        "task_forwarding_latency_ms",
    ]
    ints = {
        "task_type": np.int8,
        "task_outcome": np.int8,
        "task_ingress_rsu": np.int16,
        "task_selected_execution_rsu": np.int16,
        "task_execution_rsu": np.int16,
    }
    for key in bools + floats + list(ints):
        need(key in task, f"Missing task field {key}")
        array = task[key]
        need(array.shape == shape, f"Task shape {key}: {array.shape}")
        dtype = bool if key in bools else np.float32 if key in floats else ints[key]
        need(array.dtype == np.dtype(dtype), f"Task dtype {key}: {array.dtype}")
        need(np.all(np.isfinite(array)), f"Nonfinite task field {key}")
    step_shapes = {
        **dict.fromkeys(
            ("arrivals", "done", "active", "n_local", "n_v2i", "n_v2v", "lat_sum"), (t,)
        ),
        "veh_action": (t, n),
        "veh_k": (t, n),
        "veh_done": (t, n),
        "veh_actor_logits": (t, n, 3),
        "veh_observations": (t, n, 17),
        "exogenous_keys": (t, 6, 2),
        "observation_task_type": (t, n),
        "observation_task_size": (t, n),
        "times": (t,),
        **dict.fromkeys(("slot_tier", "slot_is_ev", "slot_soc_initial", "slot_tx_power_w"), (n,)),
        "rr_pointer_before": (t,),
        "rr_pointer_after": (t,),
    }
    for key in (
        "rsu_start_busy_ms",
        "rsu_pre_drain_busy_ms",
        "rsu_busy_ms",
        "rsu_start_load",
        "rsu_pre_drain_load",
        "rsu_load",
    ):
        step_shapes[key] = (t, r)
    for key in (
        "veh_queue_ms",
        "veh_start_busy_ms",
        "veh_pre_drain_busy_ms",
        "veh_start_load",
        "veh_pre_drain_load",
        "veh_load",
        "veh_v2v_target",
        "veh_v2v_radio_viable",
        "veh_v2i_quality",
        "veh_v2i_capacity_mbps",
        "veh_soc_before",
        "veh_soc_after",
        "veh_energy_j",
        "veh_best_rsu",
        "veh_best_v2v",
    ):
        step_shapes[key] = (t, n)
    for key, expected_shape in step_shapes.items():
        need(key in step, f"Missing step field {key}")
        need(step[key].shape == expected_shape, f"Step shape {key}: {step[key].shape}")
        need(np.all(np.isfinite(step[key])), f"Nonfinite step field {key}")
    for key in (
        "veh_observations",
        "veh_actor_logits",
        "rsu_busy_ms",
        "rsu_start_busy_ms",
        "rsu_pre_drain_busy_ms",
        "veh_queue_ms",
        "veh_soc_before",
        "veh_soc_after",
        "veh_energy_j",
        "veh_start_busy_ms",
        "veh_pre_drain_busy_ms",
    ):
        need(step[key].dtype == np.float32, f"Float32 required: {key}")
    for key in (
        "rsu_load",
        "rsu_start_load",
        "rsu_pre_drain_load",
        "veh_load",
        "veh_start_load",
        "veh_pre_drain_load",
        "rr_pointer_before",
        "rr_pointer_after",
    ):
        need(step[key].dtype == np.int32, f"Int32 required: {key}")
    for key in ("veh_action", "veh_k", "veh_done", "veh_v2v_target", "observation_task_type"):
        need(step[key].dtype.kind in "iu", f"Integer required: {key}")
    need(step["exogenous_keys"].dtype == np.uint32, "PRNG key dtype")
    controls = {
        "T": t,
        "maxN": n,
        "rsu_max_concurrent": 6220,
        "rsu_lb": arm,
        "fleet_seed": config["fleet_seed"],
        "evaluator_seed": config["evaluator_seed"],
        "enter_reset": config["enter_reset"],
        "reset_soc_on_enter": False,
        "rsu_service_mult": 1.0,
        "rsu_backhaul_ms": 0.0,
        "k8s_scale": "off",
        "fleet": "uk2030",
        "lambda_arrival": 1.5,
        "rsu_cap_mode": "reject",
        "substep_queue": "sequential",
        "veh_queue_mode": "conserved",
        "substep_queue_iterations": 3,
        "k_max": kmax,
        "n_rsus": r,
        "obs_variant": "onehot17",
        "model": "C",
        "max_vehicle_queue_depth": 10,
    }
    for key, value in controls.items():
        need(summary.get(key) == value, f"Control mismatch: {key}: {summary.get(key)} != {value}")
    active, outcome, met, admitted = (
        task[key] for key in ("task_active", "task_outcome", "task_met", "task_final_admitted")
    )
    v2i, latency, types = (task[key] for key in ("task_v2i_admitted", "task_lat_ms", "task_type"))
    actions = step["veh_action"][:, None, :]
    need(np.all((types >= 0) & (types < 3)), "Operational type range")
    need(np.all((actions >= 0) & (actions <= 2)), "Action range")
    need(np.all((step["veh_k"] >= 0) & (step["veh_k"] <= kmax)), "Arrival count range")
    need(
        np.array_equal(active, np.arange(kmax)[None, :, None] < step["veh_k"][:, None, :]),
        "Offered mask/count mismatch",
    )
    need(
        np.array_equal(admitted, active & np.isin(outcome, [1, 2])),
        "Final admission/category mismatch",
    )
    need(np.array_equal(v2i, admitted & (actions == 1)), "V2I final admission mismatch")
    need(
        np.array_equal(met, active & (outcome == 1)) and not np.any(met & ~admitted),
        "Non-admitted success/category mismatch",
    )
    deadline = np.array([100, 500, 100], np.float32)[types]
    need(np.array_equal(met, active & (latency <= deadline)), "Inclusive latency/deadline mismatch")
    rejected = active & ~admitted
    need(
        np.all(latency[rejected] == (10 * deadline)[rejected]), "Rejected latency penalty mismatch"
    )
    need(
        np.all(latency[~active] == 0) and np.all(outcome[~active] == 0), "Inactive outcome mismatch"
    )
    need(np.all((outcome[active] >= 1) & (outcome[active] <= 8)), "Terminal outcome range")
    categories = [int(np.count_nonzero(active & (outcome == code))) for code in range(9)]
    offered, admitted_count, successes = int(active.sum()), int(admitted.sum()), int(met.sum())
    for key, value in (
        ("n_offered", offered),
        ("total_tasks", offered),
        ("n_admitted", admitted_count),
    ):
        exact_count(summary[key], value, key)
    need(offered == admitted_count + sum(categories[3:]), "Offered/admitted/terminal conservation")
    need(
        abs(summary["completion"] * max(offered, 1) - successes) < 1e-6, "Score numerator mismatch"
    )
    need(
        abs(summary["completion_admitted"] * max(admitted_count, 1) - successes) < 1e-6,
        "Admitted score numerator mismatch",
    )
    type_counts = []
    for type_index in range(3):
        count = int(np.count_nonzero(active & (types == type_index)))
        successful = int(np.count_nonzero(met & (types == type_index)))
        need(
            abs(summary[f"t{type_index + 1}_share"] * max(offered, 1) - count) < 1e-6,
            "Type offered summary mismatch",
        )
        need(
            abs(summary[f"t{type_index + 1}_completion"] * max(count, 1) - successful) < 1e-6,
            "Type success summary mismatch",
        )
        type_counts.append({"type": type_index + 1, "offered": count, "successes": successful})
    need(np.array_equal(active.sum(axis=(1, 2)), step["arrivals"]), "Step arrivals mismatch")
    need(np.array_equal(met.sum(axis=(1, 2)), step["done"]), "Step successes mismatch")
    need(np.array_equal(met.sum(axis=1), step["veh_done"]), "Vehicle successes mismatch")
    for code, key in enumerate(
        (
            "v2i_gate_rejected",
            "v2i_cap_rejected",
            "local_mqd_rejected",
            "v2v_mqd_rejected",
            "v2i_unavailable",
            "v2v_unavailable",
        ),
        3,
    ):
        exact_count(summary[key], categories[code], key)
    for index, key in enumerate(("n_local", "n_v2i", "n_v2v")):
        need(
            np.array_equal((active & (actions == index)).sum(axis=(1, 2)), step[key]),
            f"Mode offered mismatch {key}",
        )
    proposal, ingress, execution = (
        task[key]
        for key in ("task_selected_execution_rsu", "task_ingress_rsu", "task_execution_rsu")
    )
    attempts = active & (actions == 1)
    need(
        np.all((ingress[attempts] >= 0) & (ingress[attempts] < r))
        and np.all(ingress[~attempts] == -1),
        "Ingress range/mask mismatch",
    )
    if arm == "p2c_dla":
        need(
            np.all((proposal[attempts] >= -1) & (proposal[attempts] < r))
            and np.all(proposal[~attempts] == -1),
            "P2C proposal range/mask mismatch",
        )
    else:
        need(
            np.all((proposal[attempts] >= 0) & (proposal[attempts] < r))
            and np.all(proposal[~attempts] == -1),
            "Proposal range/mask mismatch",
        )
    need(np.all((execution[v2i] >= 0) & (execution[v2i] < r)), "Admitted execution range")
    need(
        np.array_equal(execution, np.where(v2i, proposal, -1)),
        "Execution/proposal/admission mismatch",
    )
    need(
        np.array_equal(task["task_forwarded"], v2i & (execution != ingress)), "Forwarding mismatch"
    )
    need(np.all(task["task_forwarding_latency_ms"] == 0), "Nonzero forwarding cost")
    if arm == "ingress_dla":
        need(np.array_equal(proposal, ingress), "Ingress policy proposal mismatch")
    radio = step["veh_v2i_quality"][:, None, :] > 0
    need(not np.any(v2i & ~radio), "Unavailable radio admitted")
    need(
        not np.any(active & np.isin(outcome, [3, 4, 7]) & (actions != 1)),
        "V2I category/mode mismatch",
    )
    need(not np.any(active & (outcome == 5) & (actions != 0)), "Local category/mode mismatch")
    need(
        not np.any(active & np.isin(outcome, [6, 8]) & (actions != 2)), "V2V category/mode mismatch"
    )
    work = task["task_rsu_service_ms"]
    for key in ("task_rsu_service_ms", "task_local_service_ms", "task_v2v_service_ms"):
        need(np.all(task[key] >= 0), f"Negative service: {key}")
    enqueued, counts = np.zeros((t, r), np.float64), np.zeros((t, r), np.int64)
    for rsu in range(r):
        mask = v2i & (execution == rsu)
        enqueued[:, rsu] = np.where(mask, work, 0).sum(axis=(1, 2), dtype=np.float64)
        counts[:, rsu] = mask.sum(axis=(1, 2))
    rsu_error = work_conserved(
        step["rsu_pre_drain_busy_ms"], step["rsu_start_busy_ms"], enqueued, "RSU"
    )
    need(
        np.array_equal(step["rsu_pre_drain_load"] - step["rsu_start_load"], counts),
        "RSU enqueue count mismatch",
    )
    need(
        np.all((step["rsu_pre_drain_load"] >= 0) & (step["rsu_pre_drain_load"] <= 6220)),
        "RSU capacity boundary",
    )
    need(
        np.allclose(
            step["rsu_busy_ms"],
            np.maximum(step["rsu_pre_drain_busy_ms"] - 1000, 0),
            atol=ENDPOINT_ATOL_MS,
            rtol=0,
        ),
        "RSU drain mismatch",
    )
    need(
        np.array_equal(
            step["rsu_load"], carry_count(step["rsu_pre_drain_busy_ms"], step["rsu_pre_drain_load"])
        ),
        "RSU task-count carry mismatch",
    )
    need(
        np.array_equal(
            step["rsu_start_busy_ms"],
            np.vstack([np.zeros((1, r), np.float32), step["rsu_busy_ms"][:-1]]),
        ),
        "RSU service carry mismatch",
    )
    need(
        np.array_equal(
            step["rsu_start_load"], np.vstack([np.zeros((1, r), np.int32), step["rsu_load"][:-1]])
        ),
        "RSU count carry mismatch",
    )
    local, peer, targets = (
        admitted & (actions == 0),
        admitted & (actions == 2),
        step["veh_v2v_target"],
    )
    need(np.all((targets >= 0) & (targets < n)), "V2V target range")
    increment = np.where(local, task["task_local_service_ms"], 0).sum(axis=1, dtype=np.float64)
    count = local.sum(axis=1, dtype=np.int64)
    peer_work = np.where(peer, task["task_v2v_service_ms"], 0).sum(axis=1, dtype=np.float64)
    peer_count = peer.sum(axis=1, dtype=np.int64)
    time_indices = np.arange(t)[:, None]
    np.add.at(increment, (time_indices, targets), peer_work)
    np.add.at(count, (time_indices, targets), peer_count)
    vehicle_error = work_conserved(
        step["veh_pre_drain_busy_ms"], step["veh_start_busy_ms"], increment, "Vehicle"
    )
    need(
        np.array_equal(step["veh_pre_drain_load"] - step["veh_start_load"], count),
        "Vehicle enqueue count mismatch",
    )
    need(
        np.all(
            (step["veh_pre_drain_load"] >= 0)
            & (step["veh_pre_drain_load"] <= summary["max_vehicle_queue_depth"])
        ),
        "Vehicle capacity boundary",
    )
    need(
        np.allclose(
            step["veh_queue_ms"],
            np.maximum(step["veh_pre_drain_busy_ms"] - 1000, 0),
            atol=ENDPOINT_ATOL_MS,
            rtol=0,
        ),
        "Vehicle drain mismatch",
    )
    need(
        np.array_equal(
            step["veh_load"], carry_count(step["veh_pre_drain_busy_ms"], step["veh_pre_drain_load"])
        ),
        "Vehicle count carry mismatch",
    )
    with np.load(config["inputs"]["trace"], allow_pickle=False) as trace:
        trace_mask = trace["mask"][:t]
        need(trace_mask.shape == (t, n), "Trace shape mismatch")
        need(
            ("enter" in trace.files) == config["enter_reset"], "Trace entry-reset contract mismatch"
        )
        keep = trace_mask & ~trace["enter"][:t] if config["enter_reset"] else trace_mask
        need(np.array_equal(step["active"], trace_mask.sum(axis=1)), "Trace active count mismatch")
        need(np.array_equal(step["times"], trace["times"][:t]), "Trace timestamp mismatch")
        need(np.all(step["veh_k"][~trace_mask] == 0), "Arrivals on inactive vehicle")
        previous = np.vstack([np.zeros((1, n), np.float32), step["veh_queue_ms"][:-1]])
        need(
            np.array_equal(step["veh_start_busy_ms"], np.where(keep, previous, 0)),
            "Vehicle queue reset/carry mismatch",
        )
        previous_count = np.vstack([np.zeros((1, n), np.int32), step["veh_load"][:-1]])
        need(
            np.array_equal(step["veh_start_load"], np.where(keep, previous_count, 0)),
            "Vehicle count reset/carry mismatch",
        )
    need(
        np.array_equal(
            step["veh_soc_before"],
            np.vstack([step["slot_soc_initial"][None, :], step["veh_soc_after"][:-1]]),
        ),
        "SoC carry/reset mismatch",
    )
    need(
        np.all(step["rr_pointer_before"] == -1) and np.all(step["rr_pointer_after"] == -1),
        "Unexpected cyclic state",
    )
    p2c_audit = validate_p2c(step, task, config) if arm == "p2c_dla" else None
    shared = {
        f"step/{key}": array_hash(step[key])
        for key in (
            "times",
            "slot_tier",
            "slot_is_ev",
            "slot_soc_initial",
            "slot_tx_power_w",
            "exogenous_keys",
            "observation_task_type",
            "observation_task_size",
            "veh_k",
        )
    }
    shared.update(
        {
            f"task/{key}": array_hash(task[key])
            for key in ("task_active", "task_type", "task_sizes_mb", "task_rsu_service_ms")
        }
    )
    return {
        "status": "passed",
        "seal_sha256": config["seal_sha256"],
        "configuration": config,
        "output_sha256": {name: sha(destination / name) for name in FILES},
        "shared_input_hashes": shared,
        "offered": offered,
        "admitted": admitted_count,
        "successes": successes,
        "terminal_failures": offered - admitted_count,
        "forwarded": int(task["task_forwarded"].sum()),
        "outcome_counts": categories,
        "type_counts": type_counts,
        "max_service_conservation_error_ms": rsu_error,
        "max_vehicle_service_conservation_error_ms": vehicle_error,
        "p2c": p2c_audit,
        "lifecycle_not_observed": ["compute_completed", "returned"],
        "field_contract": {
            kind: {
                key: {"shape": list(value.shape), "dtype": str(value.dtype)}
                for key, value in arrays.items()
            }
            for kind, arrays in (("step", step), ("task", task))
        },
        "control_interpretation": (
            "frozen weights; endogenous observations, logits and mode choices "
            "may differ across arms"
        ),
    }


def splitmix64(value: np.ndarray | np.uint64) -> np.ndarray:
    """Independent NumPy uint64 arithmetic; overflow is defined modulo 2**64."""
    with np.errstate(over="ignore"):
        value = np.asarray(value, dtype=np.uint64) + np.uint64(0x9E3779B97F4A7C15)
        value = (value ^ (value >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        value = (value ^ (value >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        return value ^ (value >> np.uint64(31))


def validate_p2c(step: Arrays, task: Arrays, config: Json) -> Json:
    """Replay within-step admissions independently, vectorized over trace seconds.

    Recompute the exact SplitMix64 pair from evaluator/fleet seed, outer tick,
    task slot and dense ordinal. Both sampled IDs must belong to the causal
    feasible set; selection minimizes raw workload with canonical ID ties.
    """
    active = task["task_active"]
    t, kmax, n = active.shape
    r = step["rsu_start_busy_ms"].shape[1]
    contracts = {
        "task_p2c_feasible_count": (np.int16, active.shape),
        "task_p2c_sampled_pair": (np.int16, (*active.shape, 2)),
        "task_p2c_feasibility_workload_checks": (np.int16, active.shape),
        "task_p2c_ranking_workload_inspections": (np.int8, active.shape),
        "task_p2c_unique_workload_values_observed": (np.int16, active.shape),
        "task_p2c_sequential_ordinal": (np.int32, active.shape),
        "task_p2c_placement_busy_ms": (np.float32, active.shape),
    }
    for name, (dtype, shape) in contracts.items():
        need(name in task, f"Missing P2C field {name}")
        need(task[name].dtype == dtype and task[name].shape == shape, f"P2C field contract: {name}")
        need(np.all(np.isfinite(task[name])), f"Nonfinite P2C field: {name}")
    ordinal = np.arange(kmax * n, dtype=np.int32).reshape(kmax, n)
    need(np.all(task["task_p2c_sequential_ordinal"] == ordinal[None, :, :]), "P2C ordinal mismatch")
    busy, load = step["rsu_start_busy_ms"].copy(), step["rsu_start_load"].copy()
    row = np.arange(t)
    seed_hash = np.uint64(0x6A09E667F3BCC909)
    for field in (config["evaluator_seed"], config["fleet_seed"]):
        seed_hash = splitmix64(seed_hash ^ np.uint64(field))
    tick_hash = splitmix64(seed_hash ^ np.arange(t, dtype=np.uint64))
    inspected = 0
    no_feasible = 0
    for substep in range(kmax):
        slot_hash = splitmix64(tick_hash ^ np.uint64(substep))
        for vehicle in range(n):
            attempted = active[:, substep, vehicle] & (step["veh_action"][:, vehicle] == 1)
            eligible = attempted & (step["veh_v2i_quality"][:, vehicle] > 0)
            deadline = np.array([100, 500, 100], np.float32)[task["task_type"][:, substep, vehicle]]
            meets_gate = busy < deadline[:, None]
            feasible = meets_gate & (load < 6220) & eligible[:, None]
            count = feasible.sum(axis=1)
            need(
                np.array_equal(task["task_p2c_feasible_count"][:, substep, vehicle], count),
                "P2C causal feasible count mismatch",
            )
            for name in (
                "task_p2c_feasibility_workload_checks",
                "task_p2c_unique_workload_values_observed",
            ):
                need(
                    np.array_equal(task[name][:, substep, vehicle], eligible.astype(np.int16) * r),
                    f"P2C workload accounting mismatch: {name}",
                )
            need(
                np.array_equal(
                    task["task_p2c_ranking_workload_inspections"][:, substep, vehicle],
                    np.minimum(count, 2),
                ),
                "P2C ranking accounting mismatch",
            )
            pair = task["task_p2c_sampled_pair"][:, substep, vehicle]
            multiple = count >= 2
            need(np.all(pair[~multiple] == -1), "P2C pair present with fewer than two candidates")
            need(
                np.all(
                    (pair[multiple, 0] >= 0)
                    & (pair[multiple, 0] < pair[multiple, 1])
                    & (pair[multiple, 1] < r)
                ),
                "P2C pair is not sorted/distinct/in range",
            )
            chosen_rows = row[multiple]
            need(
                np.all(feasible[chosen_rows, pair[multiple, 0]])
                and np.all(feasible[chosen_rows, pair[multiple, 1]]),
                "P2C sampled infeasible RSU",
            )
            hash_value = splitmix64(slot_hash[multiple] ^ np.uint64(substep * n + vehicle))
            pair_count = count[multiple].astype(np.uint64)
            first = (hash_value % pair_count).astype(np.int64)
            second = (splitmix64(hash_value) % (pair_count - np.uint64(1))).astype(np.int64)
            second += second >= first
            candidates = np.sort(np.where(feasible[multiple], np.arange(r), r), axis=1)
            pair_rows = np.arange(len(chosen_rows))
            expected_pair = np.sort(
                np.column_stack((candidates[pair_rows, first], candidates[pair_rows, second])),
                axis=1,
            )
            need(
                np.array_equal(pair[multiple], expected_pair),
                "P2C sampled pair differs from exact counter key",
            )
            selected = np.where(count == 1, feasible.argmax(axis=1), -1)
            pair_busy = busy[chosen_rows[:, None], pair[multiple]]
            selected[multiple] = np.where(
                pair_busy[:, 0] <= pair_busy[:, 1], pair[multiple, 0], pair[multiple, 1]
            )
            need(
                np.array_equal(task["task_selected_execution_rsu"][:, substep, vehicle], selected),
                "P2C selected RSU violates feasible pair/ranking/tie rule",
            )
            admitted = count > 0
            need(
                np.array_equal(task["task_v2i_admitted"][:, substep, vehicle], admitted),
                "P2C final admission differs from causal feasibility",
            )
            expected_busy = np.where(admitted, busy[row, np.maximum(selected, 0)], np.float32(-1))
            need(
                np.array_equal(
                    task["task_p2c_placement_busy_ms"][:, substep, vehicle], expected_busy
                ),
                "P2C selected raw workload differs from causal state",
            )
            outcome = task["task_outcome"][:, substep, vehicle]
            need(np.all(outcome[attempted & ~eligible] == 7), "P2C unavailable radio category")
            empty = eligible & ~admitted
            expected_failure = np.where(meets_gate.any(axis=1), 4, 3)
            need(
                np.array_equal(outcome[empty], expected_failure[empty]), "P2C N0 rejection category"
            )
            accepted_rows = row[admitted]
            accepted_rsus = selected[admitted]
            # float32 additions intentionally match the declared causal carry;
            # regrouping all same-RSU work is a different floating operation.
            busy[accepted_rows, accepted_rsus] += task["task_rsu_service_ms"][
                admitted, substep, vehicle
            ]
            load[accepted_rows, accepted_rsus] += 1
            inspected += int(eligible.sum()) * r
            no_feasible += int(empty.sum())
    need(np.array_equal(busy, step["rsu_pre_drain_busy_ms"]), "P2C causal final RSU work mismatch")
    need(np.array_equal(load, step["rsu_pre_drain_load"]), "P2C causal final RSU count mismatch")
    return {
        "status": "passed",
        "no_feasible": no_feasible,
        "workload_checks": inspected,
        "pair_sampling": (
            "exact SplitMix64 pair, causal feasibility, ranking and carry checked for every record"
        ),
    }

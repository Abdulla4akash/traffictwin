"""Small synthetic-schema TOS package used only for adapter tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from traffictwin.integration.tos.readers import EXPECTED_EVALUATION_COLUMNS


def write_tos_package(root: Path) -> Path:
    """Write a tiny deterministic package matching the evidenced source schema."""

    for directory in (
        "evals",
        "instrumented/json",
        "instrumented/perstep",
        "instrumented/pertask",
        "traces",
        "training",
        "records",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "Synthetic-schema TOS adapter test fixture.\n", encoding="utf-8"
    )
    (root / "DATA_DICTIONARY.md").write_text(
        "Synthetic-schema fixture; values are not research results.\n",
        encoding="utf-8",
    )
    rows = [_evaluation_row("baseline", 0.90), _evaluation_row("capscalar_mappo", 0.93)]
    with (root / "evals/eval_results_master.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EXPECTED_EVALUATION_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    _write_trace(root)
    _write_training(root, "baseline")
    _write_training(root, "capscalar_mappo")
    (root / "records/TRAINING_capscalar_mappo.md").write_text(
        "Manchester evaluation mobility is held out by construction.\n",
        encoding="utf-8",
    )
    _write_instrumented(root, "baseline_uk2030_wd_am_fs0", rows[0], pertask=True)
    _write_instrumented(root, "caps_mappo_uk2030_wd_am_fs0", rows[1], pertask=False)
    return root


def _write_training(root: Path, training_id: str) -> None:
    fields = [
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
        "elapsed_s",
        "sps",
    ]
    rows: list[list[object]] = [
        [0, 100, "nan", "nan", "nan", "nan", "nan", "nan", "nan", "nan", "nan", "nan", 1.0, 100],
        [1, 200, -10.0, 0.8, 0.5, 0.3, 0.2, 0.4, 60.0, 0.7, 0.9, 0.8, 2.0, 100],
        [2, 300, -8.0, 0.9, 0.4, 0.4, 0.2, 0.35, 50.0, 0.8, 0.95, 0.9, 3.0, 100],
    ]
    with (root / f"training/{training_id}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)
    greedy = {
        "mean_completion": 0.9,
        "std_completion": 0.02,
        "type_1_completion": 0.8,
        "type_2_completion": 0.95,
        "type_3_completion": 0.9,
        "p_local": 0.4,
        "p_v2i": 0.4,
        "p_v2v": 0.2,
        "avg_energy_j": 0.35,
        "avg_latency_ms": 50.0,
        "n_eval_episodes": 10,
        "elapsed_s": 1.0,
    }
    (root / f"training/{training_id}_greedy_eval.json").write_text(
        json.dumps(greedy, indent=2), encoding="utf-8"
    )


def _evaluation_row(campaign: str, completion: float) -> dict[str, object]:
    return {
        "campaign": campaign,
        "cell": "wd_am",
        "eval_fleet": "uk2030",
        "fleet_seed": 0,
        "actor": f"{campaign}_actor_params.npz",
        "obs_variant": "onehot17" if campaign == "baseline" else "capscalar13",
        "completion": completion,
        "t1_completion": completion - 0.10,
        "t2_completion": 0.98,
        "t3_completion": completion,
        "avg_energy_j_per_task": 0.4,
        "avg_latency_ms_per_task": 60.0,
        "p_local": 0.5,
        "p_v2i": 0.3,
        "p_v2v": 0.2,
        "fleet_ev_share": 0.22,
        "T": 3,
        "maxN": 2,
        "trace": "trace_wd_am_fullrsu.npz",
        "engine_version": "v2_post_nrsus_fix",
    }


def _write_trace(root: Path) -> None:
    np.savez_compressed(
        root / "traces/trace_wd_am_fullrsu.npz",
        pos_x=np.array([[0, 10], [1, 11], [2, 12]], dtype=np.float32),
        pos_y=np.array([[5, 15], [5, 15], [5, 15]], dtype=np.float32),
        speed=np.array([[1, 1], [1, 1], [1, 1]], dtype=np.float32),
        mask=np.array([[True, True], [True, False], [True, True]]),
        rsu_xy=np.array([[5, 5]], dtype=np.float32),
        times=np.array([0, 1, 2], dtype=np.float32),
        dt=np.array(1, dtype=np.float32),
        maxN=np.array(2, dtype=np.int32),
        T=np.array(3, dtype=np.int32),
        window=np.array("synthetic-schema-test"),
        sumo_seed=np.array(0, dtype=np.int32),
    )


def _write_instrumented(
    root: Path,
    key: str,
    row: dict[str, object],
    *,
    pertask: bool,
) -> None:
    np.savez_compressed(
        root / f"instrumented/perstep/{key}_perstep.npz",
        times=np.array([0, 1, 2], dtype=np.float32),
        arrivals=np.array([2, 1, 1], dtype=np.int32),
        done=np.array([2, 0, 1], dtype=np.int32),
        lat_sum=np.array([50, 700, 80], dtype=np.float32),
        active=np.array([2, 1, 2], dtype=np.int32),
        n_local=np.array([1, 1, 0], dtype=np.int32),
        n_v2i=np.array([1, 0, 1], dtype=np.int32),
        n_v2v=np.array([0, 0, 0], dtype=np.int32),
        veh_action=np.array([[0, 1], [0, 0], [1, 0]], dtype=np.int8),
        veh_k=np.array([[1, 1], [1, 0], [1, 0]], dtype=np.int8),
        veh_done=np.array([[1, 1], [0, 0], [1, 0]], dtype=np.int16),
        veh_queue_ms=np.array([[20, 30], [700, 0], [80, 0]], dtype=np.float32),
        rsu_busy_ms=np.array([[500], [1200], [700]], dtype=np.float32),
        rsu_load=np.array([[1], [2], [1]], dtype=np.int32),
    )
    summary = {
        "trace": row["trace"],
        "actor": row["actor"],
        "model": "C",
        "T": row["T"],
        "maxN": row["maxN"],
        "rsu_max_concurrent": 5,
        "fleet": row["eval_fleet"],
        "fleet_seed": row["fleet_seed"],
        "obs_variant": row["obs_variant"],
        "fleet_ev_share": row["fleet_ev_share"],
        "fleet_tier_hist": [1, 1, 0],
        "completion": row["completion"],
        "t1_completion": row["t1_completion"],
        "t2_completion": row["t2_completion"],
        "t3_completion": row["t3_completion"],
        "avg_energy_j_per_task": row["avg_energy_j_per_task"],
        "avg_latency_ms_per_task": row["avg_latency_ms_per_task"],
        "p_local": row["p_local"],
        "p_v2i": row["p_v2i"],
        "p_v2v": row["p_v2v"],
        "t1_share": 0.25,
        "t2_share": 0.25,
        "t3_share": 0.50,
        "total_tasks": 4.0,
        "wall_s": 0.1,
    }
    (root / f"instrumented/json/{key}.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    if not pertask:
        return
    shape = (3, 2, 2)
    task_type: Any = np.zeros(shape, dtype=np.int8)
    task_latency: Any = np.zeros(shape, dtype=np.float32)
    task_met: Any = np.zeros(shape, dtype=np.bool_)
    task_active: Any = np.zeros(shape, dtype=np.bool_)
    entries = [
        (0, 0, 0, 0, 50.0, True),
        (0, 0, 1, 1, 300.0, True),
        (1, 0, 0, 2, 150.0, False),
        (2, 0, 0, 0, 80.0, True),
    ]
    for time_index, task_slot, vehicle_slot, code, latency, met in entries:
        task_type[time_index, task_slot, vehicle_slot] = code
        task_latency[time_index, task_slot, vehicle_slot] = latency
        task_met[time_index, task_slot, vehicle_slot] = met
        task_active[time_index, task_slot, vehicle_slot] = True
    np.savez_compressed(
        root / f"instrumented/pertask/{key}_pertask.npz",
        task_type=task_type,
        task_lat_ms=task_latency,
        task_met=task_met,
        task_active=task_active,
    )

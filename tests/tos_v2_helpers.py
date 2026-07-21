"""Synthetic-schema golden fixtures for the audited v2 TOS/VEC contract.

Every value is synthetic and deterministic. The fixtures match the schemas,
shapes, and semantics recorded by the accepted VEC-01 audit but contain no
Randy data. Dimensions are deliberately tiny: T=6, maxN=3, n_rsu=2, K=5.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

V2_SCENARIO = "wd_am"
V2_T = 6
V2_MAX_N = 3
V2_RSU_COUNT = 2
V2_K = 5
V2_FIRST_TIME = 100.0


def build_v2_trace() -> dict[str, Any]:
    """Return a golden trace mapping matching the audited schema."""

    mask: npt.NDArray[Any] = np.zeros((V2_T, V2_MAX_N), dtype=bool)
    mask[:, 0] = True
    mask[:, 1] = True
    pos_x = np.where(mask, 10.0, 0.0).astype(np.float32)
    pos_y = np.where(mask, 20.0, 0.0).astype(np.float32)
    speed = np.where(mask, 5.0, 0.0).astype(np.float32)
    return {
        "T": np.int32(V2_T),
        "dt": np.float32(1.0),
        "mask": mask,
        "maxN": np.int32(V2_MAX_N),
        "pos_x": pos_x,
        "pos_y": pos_y,
        "rsu_xy": np.array([[0.0, 0.0], [100.0, 100.0]], dtype=np.float32),
        "speed": speed,
        "sumo_seed": np.int32(42),
        "times": (V2_FIRST_TIME + np.arange(V2_T, dtype=np.float32)),
        "window": np.str_("synthetic_window"),
    }


def build_v2_perstep() -> dict[str, Any]:
    """Return a golden per-step mapping that reconciles with the golden trace."""

    trace = build_v2_trace()
    veh_action: npt.NDArray[Any] = np.zeros((V2_T, V2_MAX_N), dtype=np.int8)
    veh_k: npt.NDArray[Any] = np.zeros((V2_T, V2_MAX_N), dtype=np.int8)
    veh_done: npt.NDArray[Any] = np.zeros((V2_T, V2_MAX_N), dtype=np.int16)
    veh_best_rsu: npt.NDArray[Any] = np.full((V2_T, V2_MAX_N), -1, dtype=np.int16)
    veh_best_v2v: npt.NDArray[Any] = np.full((V2_T, V2_MAX_N), -1, dtype=np.int16)

    veh_k[0, 0] = 2
    veh_done[0, 0] = 1
    veh_k[0, 1] = 1
    veh_action[0, 1] = 1
    veh_best_rsu[0, 1] = 1
    veh_done[0, 1] = 1

    veh_k[1, 0] = 1
    veh_action[1, 0] = 2
    veh_best_v2v[1, 0] = 1
    veh_done[1, 0] = 1

    veh_k[3, 0] = 1
    veh_k[3, 1] = 2
    veh_action[3, 1] = 1
    veh_best_rsu[3, 1] = 0
    veh_done[3, 1] = 2

    arrivals = veh_k.sum(axis=1, dtype=np.int32)
    done = veh_done.sum(axis=1, dtype=np.int32)
    n_local = (veh_k * (veh_action == 0)).sum(axis=1, dtype=np.int32)
    n_v2i = (veh_k * (veh_action == 1)).sum(axis=1, dtype=np.int32)
    n_v2v = (veh_k * (veh_action == 2)).sum(axis=1, dtype=np.int32)
    lat_sum: npt.NDArray[Any] = np.zeros(V2_T, dtype=np.float32)
    lat_sum[0] = 210.0
    lat_sum[1] = 70.0
    lat_sum[3] = 210.0
    return {
        "active": np.asarray(trace["mask"]).sum(axis=1).astype(np.int32),
        "arrivals": arrivals,
        "done": done,
        "lat_sum": lat_sum,
        "n_local": n_local,
        "n_v2i": n_v2i,
        "n_v2v": n_v2v,
        "rsu_busy_ms": np.zeros((V2_T, V2_RSU_COUNT), dtype=np.float32),
        "rsu_load": np.zeros((V2_T, V2_RSU_COUNT), dtype=np.int32),
        "slot_is_ev": np.array([False, True, False]),
        "slot_tier": np.array([0, 1, 2], dtype=np.int8),
        "times": np.asarray(trace["times"]).copy(),
        "veh_action": veh_action,
        "veh_best_rsu": veh_best_rsu,
        "veh_best_v2v": veh_best_v2v,
        "veh_done": veh_done,
        "veh_k": veh_k,
        "veh_queue_ms": np.zeros((V2_T, V2_MAX_N), dtype=np.float32),
    }


def build_v2_run_summary() -> dict[str, Any]:
    """Return the run summary that reconciles with the golden per-step arrays."""

    return {
        "avg_latency_ms_per_task": 70.0,
        "completion": 5 / 7,
        "fleet_ev_share": 1 / 3,
        "fleet_tier_hist": [1, 1, 1],
        "p_local": 3 / 7,
        "p_v2i": 3 / 7,
        "p_v2v": 1 / 7,
        "total_tasks": 7,
    }


def build_v2_pertask() -> dict[str, Any]:
    """Return golden per-task arrays consistent with the audited schema."""

    shape = (V2_T, V2_K, V2_MAX_N)
    task_active: npt.NDArray[Any] = np.zeros(shape, dtype=bool)
    task_met: npt.NDArray[Any] = np.zeros(shape, dtype=bool)
    task_type: npt.NDArray[Any] = np.zeros(shape, dtype=np.int8)
    task_lat_ms: npt.NDArray[Any] = np.zeros(shape, dtype=np.float32)

    perstep = build_v2_perstep()
    veh_k = np.asarray(perstep["veh_k"])
    veh_done = np.asarray(perstep["veh_done"])
    for time_index in range(V2_T):
        for slot in range(V2_MAX_N):
            count = int(veh_k[time_index, slot])
            met = int(veh_done[time_index, slot])
            for task_slot in range(count):
                task_active[time_index, task_slot, slot] = True
                task_met[time_index, task_slot, slot] = task_slot < met
                task_type[time_index, task_slot, slot] = task_slot % 3
                task_lat_ms[time_index, task_slot, slot] = 70.0
    return {
        "task_active": task_active,
        "task_lat_ms": task_lat_ms,
        "task_met": task_met,
        "task_type": task_type,
    }


def build_v2_occupancy_rows() -> tuple[tuple[str, ...], list[list[str]]]:
    """Return golden occupancy CSV content with inclusive integer bounds."""

    header = ("sumo_vehicle_id", "slot", "t_enter", "t_exit")
    rows = [
        ["veh_synthetic_a", "0", "0", "2"],
        ["veh_synthetic_b", "1", "0", "5"],
        ["veh_synthetic_c", "0", "3", "5"],
    ]
    return header, rows


def build_v2_tripinfo_records() -> list[dict[str, Any]]:
    """Return synthetic trip records mirroring the audited coverage cases."""

    return [
        {
            "id": "veh_synthetic_a",
            "depart": 100.0,
            "arrival": 102.9,
            "duration": 2.9,
            "routeLength": 55.0,
        },
        {
            "id": "veh_synthetic_c",
            "depart": 103.0,
            "arrival": 105.5,
            "duration": 2.5,
            "routeLength": 40.0,
        },
    ]


def write_v2_package(root: Path) -> Path:
    """Write the complete golden synthetic v2 package to disk."""

    for directory in (
        "traces",
        "occupancy",
        "instrumented/json",
        "instrumented/perstep",
        "instrumented/pertask",
        "tripinfo",
    ):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "Synthetic-schema v2 contract fixture; values are not research results.\n",
        encoding="utf-8",
    )
    np.savez(root / f"traces/trace_{V2_SCENARIO}_synthetic.npz", **build_v2_trace())
    np.savez(
        root / f"instrumented/perstep/baseline_synthetic_{V2_SCENARIO}_fs0_perstep.npz",
        **build_v2_perstep(),
    )
    np.savez(
        root / f"instrumented/pertask/baseline_synthetic_{V2_SCENARIO}_fs0_pertask.npz",
        **build_v2_pertask(),
    )
    (root / f"instrumented/json/baseline_synthetic_{V2_SCENARIO}_fs0.json").write_text(
        json.dumps(build_v2_run_summary(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    header, rows = build_v2_occupancy_rows()
    with (root / f"occupancy/occupancy_{V2_SCENARIO}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    trips = "".join(
        (
            f'    <tripinfo id="{record["id"]}" depart="{record["depart"]}" '
            f'arrival="{record["arrival"]}" duration="{record["duration"]}" '
            f'routeLength="{record["routeLength"]}"/>\n'
        )
        for record in build_v2_tripinfo_records()
    )
    payload = f"<tripinfos>\n{trips}</tripinfos>\n".encode()
    with gzip.GzipFile(
        root / f"tripinfo/tripinfo_{V2_SCENARIO}.xml.gz", mode="wb", mtime=0
    ) as handle:
        handle.write(payload)
    return root

#!/usr/bin/env python3
"""Analysis-only mining of the admitted capacity-pilot artifacts.

Three measurements the capacity programme never took, all from arrays that
already exist in admitted cells. No run executes, no claim is promoted, and
nothing here is confirmatory: the pilot is exploratory by its own
predeclaration and these are descriptive readings of it.

1. **Within-run dynamics.** Every prior analysis aggregates over all 3,600
   steps. This resolves latency, load, decision mix and queueing *through* the
   collapse hour, so the question "when does capacity bind?" gets an answer
   instead of an average.

2. **Per-vehicle heterogeneity.** The policy is capacity-invariant in aggregate;
   that says nothing about whether its costs fall evenly. This measures how
   concentrated offloading and deadline failure are across the 2,488 slots.

3. **Deadline slack by task class.** p50 latency is flat and p99 collapses. This
   splits latency by task class and by whether the deadline was met, which
   locates the implied deadline of each class empirically and shows whether the
   squeeze ever rescues a task rather than merely shortening an already-failed
   one.

Usage:
    uv run python scripts/analyse_pilot_dynamics.py [--cells cap-2.5-fs0 ...]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

PILOT_ROOT = Path("data/vec-fresh/capacity-pilot").resolve()
OUT_ROOT = Path("data/pilot-dynamics-20260728").resolve()
#: Bucket count for the within-run time series. 3,600 steps / 60 = one bucket
#: per 60 steps, which keeps the series readable without hiding the onset.
BUCKETS = 60
ACTION_NAMES = ("local", "v2i", "v2v")
TASK_CLASS_NAMES = ("T1", "T2", "T3")


def _gini(values: npt.NDArray[np.float64]) -> float:
    """Return the Gini coefficient of a non-negative vector."""

    if values.size == 0:
        return 0.0
    ordered = np.sort(values.astype(np.float64))
    total = ordered.sum()
    if total <= 0:
        return 0.0
    index = np.arange(1, ordered.size + 1, dtype=np.float64)
    return float(
        (2.0 * (index * ordered).sum()) / (ordered.size * total)
        - (ordered.size + 1.0) / ordered.size
    )


def _percentiles(values: npt.NDArray[np.floating[Any]]) -> dict[str, float | None]:
    if values.size == 0:
        return dict.fromkeys(("n", "mean", "p05", "p50", "p95", "p99", "max"))
    return {
        "n": int(values.size),
        "mean": float(values.mean()),
        "p05": float(np.percentile(values, 5)),
        "p50": float(np.percentile(values, 50)),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
        "max": float(values.max()),
    }


def analyse_cell(cell: Path) -> dict[str, Any]:
    step = np.load(cell / "per-step.npz")
    times = step["times"]
    steps = int(times.size)
    done = step["done"].astype(np.float64)
    lat_sum = step["lat_sum"].astype(np.float64)
    active = step["active"].astype(np.float64)
    n_local = step["n_local"].astype(np.float64)
    n_v2i = step["n_v2i"].astype(np.float64)
    n_v2v = step["n_v2v"].astype(np.float64)
    rsu_load = step["rsu_load"].astype(np.float64)

    # --- 1. within-run dynamics -------------------------------------------
    edges = np.linspace(0, steps, BUCKETS + 1, dtype=int)
    series: list[dict[str, Any]] = []
    for start, stop in zip(edges[:-1], edges[1:], strict=True):
        bucket_done = done[start:stop].sum()
        bucket_lat = lat_sum[start:stop].sum()
        decisions = n_local[start:stop].sum() + n_v2i[start:stop].sum() + n_v2v[start:stop].sum()
        load = rsu_load[start:stop]
        series.append(
            {
                "step_from": int(start),
                "step_to": int(stop),
                # Mean latency of tasks COMPLETING in the bucket. lat_sum is a
                # sum over completions, so the denominator must be `done`, not
                # the bucket width; a zero-completion bucket has no mean.
                "mean_latency_ms": float(bucket_lat / bucket_done) if bucket_done > 0 else None,
                "completions": int(bucket_done),
                "mean_active_vehicles": float(active[start:stop].mean()),
                "offload_share": float(
                    (n_v2i[start:stop].sum() + n_v2v[start:stop].sum()) / decisions
                )
                if decisions > 0
                else None,
                "mean_total_rsu_load": float(load.sum(axis=1).mean()),
                "mean_busiest_rsu_load": float(load.max(axis=1).mean()),
                "mean_rsu_load_gini": float(np.mean([_gini(row) for row in load])),
            }
        )

    # --- 2. per-vehicle heterogeneity -------------------------------------
    veh_action = step["veh_action"]
    veh_k = step["veh_k"]
    veh_queue = step["veh_queue_ms"]
    # A slot only decides on steps where it carries tasks; steps with veh_k == 0
    # are not "chose local", they are "not present", and counting them as local
    # would manufacture a huge inert majority.
    present = veh_k > 0
    per_vehicle_steps = present.sum(axis=0).astype(np.float64)
    offloads = ((veh_action > 0) & present).sum(axis=0).astype(np.float64)
    locals_ = ((veh_action == 0) & present).sum(axis=0).astype(np.float64)
    seen = per_vehicle_steps > 0
    offload_rate = np.divide(
        offloads, per_vehicle_steps, out=np.zeros_like(offloads), where=per_vehicle_steps > 0
    )
    mean_queue = np.divide(
        (veh_queue * present).sum(axis=0).astype(np.float64),
        per_vehicle_steps,
        out=np.zeros_like(per_vehicle_steps),
        where=per_vehicle_steps > 0,
    )
    del veh_action, veh_k, veh_queue, present

    task = np.load(cell / "per-task.npz")
    task_active = task["task_active"]
    task_met = task["task_met"]
    # Per slot: how many of its tasks met their deadline.
    per_vehicle_tasks = task_active.sum(axis=(0, 1)).astype(np.float64)
    per_vehicle_met = (task_met & task_active).sum(axis=(0, 1)).astype(np.float64)
    fail_rate = np.divide(
        per_vehicle_tasks - per_vehicle_met,
        per_vehicle_tasks,
        out=np.zeros_like(per_vehicle_tasks),
        where=per_vehicle_tasks > 0,
    )
    has_tasks = per_vehicle_tasks > 0

    ordered_fail = np.sort(fail_rate[has_tasks])[::-1]
    ordered_tasks = np.sort(per_vehicle_tasks[has_tasks])[::-1]
    top_decile = max(1, ordered_tasks.size // 10)
    failures = per_vehicle_tasks - per_vehicle_met
    ordered_failures = np.sort(failures[has_tasks])[::-1]

    heterogeneity = {
        "slots_total": int(fail_rate.size),
        "slots_with_any_task": int(has_tasks.sum()),
        "slots_ever_present": int(seen.sum()),
        "offload_rate_across_slots": _percentiles(offload_rate[seen]),
        "offload_rate_gini": _gini(offload_rate[seen]),
        "slots_never_offloading": int(((offloads == 0) & seen).sum()),
        "slots_always_offloading": int(((locals_ == 0) & seen).sum()),
        "deadline_failure_rate_across_slots": _percentiles(fail_rate[has_tasks]),
        "deadline_failure_rate_gini": _gini(fail_rate[has_tasks]),
        "slots_with_zero_failures": int(((failures == 0) & has_tasks).sum()),
        "slots_with_total_failure": int(((per_vehicle_met == 0) & has_tasks).sum()),
        "failure_share_of_worst_decile": float(
            ordered_failures[:top_decile].sum() / failures[has_tasks].sum()
        )
        if failures[has_tasks].sum() > 0
        else None,
        "task_count_gini_across_slots": _gini(per_vehicle_tasks[has_tasks]),
        "mean_queue_ms_across_slots": _percentiles(mean_queue[seen]),
        "worst_decile_failure_rate_mean": float(ordered_fail[:top_decile].mean()),
    }

    # --- 3. deadline slack by task class ----------------------------------
    task_type = task["task_type"]
    task_lat = task["task_lat_ms"]
    classes: dict[str, Any] = {}
    for code, name in enumerate(TASK_CLASS_NAMES):
        selector = task_active & (task_type == code)
        if not selector.any():
            continue
        met_sel = selector & task_met
        missed_sel = selector & ~task_met
        met_lat = task_lat[met_sel]
        missed_lat = task_lat[missed_sel]
        classes[name] = {
            "active_tasks": int(selector.sum()),
            "met": int(met_sel.sum()),
            "missed": int(missed_sel.sum()),
            "attainment": float(met_sel.sum() / selector.sum()),
            # The largest latency among MET tasks is the empirical deadline of
            # the class: the boundary is observed, never assumed from config.
            "implied_deadline_ms": float(met_lat.max()) if met_lat.size else None,
            "met_latency": _percentiles(met_lat),
            "missed_latency": _percentiles(missed_lat),
            "met_slack_ms": _percentiles(float(met_lat.max()) - met_lat) if met_lat.size else None,
        }
        del met_lat, missed_lat, met_sel, missed_sel, selector

    receipt = json.loads((cell / "execution_receipt.json").read_text())
    return {
        "cell": cell.name,
        "steps": steps,
        "max_slots": int(rsu_load.shape[0] and step["slot_tier"].size),
        "rsu_count": int(rsu_load.shape[1]),
        "receipt_fingerprint": receipt.get("receipt_fingerprint"),
        "within_run_series": series,
        "per_vehicle_heterogeneity": heterogeneity,
        "deadline_slack_by_class": classes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cells", nargs="*", default=None)
    args = parser.parse_args()

    cells = (
        [PILOT_ROOT / name for name in args.cells]
        if args.cells
        else sorted(p for p in PILOT_ROOT.iterdir() if p.is_dir())
    )
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    results = []
    for cell in cells:
        if not (cell / "per-step.npz").is_file():
            print(f"skip {cell.name}: no arrays", flush=True)
            continue
        print(f"analysing {cell.name} ...", flush=True)
        results.append(analyse_cell(cell))
        print(f"  done {cell.name}", flush=True)

    payload = {
        "record_type": "capacity_pilot_dynamics_analysis",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "analysis_only": True,
        "source": "admitted capacity-pilot cells; no run executed",
        "measurement_notes": {
            "mean_latency_denominator": (
                "lat_sum is a sum over completions, so bucket mean latency divides by "
                "completions, never by bucket width"
            ),
            "presence_rule": (
                "a slot decides only on steps where veh_k > 0; absent steps are not "
                "counted as local decisions"
            ),
            "implied_deadline": (
                "the largest latency among met tasks of a class, observed rather than "
                "read from configuration"
            ),
        },
        "cells": results,
    }
    out = OUT_ROOT / "pilot_dynamics.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

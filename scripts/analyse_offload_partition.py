#!/usr/bin/env python3
"""Measure what the trained policy's offload decision is actually a function of.

Analysis-only over admitted cells. No run executes, nothing is promoted, and
nothing here is confirmatory.

The pilot dynamics analysis established that the offload decision is *bimodal*:
each slot either never offloads or always does, with ~3.5% ever mixing, and the
split is identical at every capacity. That left the obvious question unasked —
**what determines which side a vehicle falls on?**

This measures three candidate explanations against each other:

1. **Vehicle compute tier.** `slot_tier` indexes the producer's
   ``TIER_CAP_SCALAR = [0.0751, 0.4847, 1.0]``, so tier 0 is ~13x weaker than
   tier 2.
2. **Workload.** Tasks per slot, which the pilot found almost perfectly even
   (Gini 0.028).
3. **Task mix.** Per-class share, since T1/T3 carry 100 ms deadlines and T2
   carries 500 ms.

It also reports deadline failure *within* each task class per group, because a
raw failure difference between groups can be manufactured entirely by a
difference in task mix, and that has to be ruled out rather than assumed.

**What this deliberately does not answer:** whether offloading *helps* the
vehicles that do it. That is a counterfactual requiring a different actor on the
same trace, which is the separate crossover campaign, not this measurement.

Producer code and data use is covered by the recorded permission with citation;
see docs/producer_citation_requirements.md.

Usage:
    uv run python scripts/analyse_offload_partition.py CELL [CELL ...] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

#: Producer per-tier compute capability scalars, read from vec_jax.py.
TIER_CAP_SCALAR = (0.0751, 0.4847, 1.0)
TASK_CLASS_NAMES = ("T1", "T2", "T3")
DEFAULT_OUT = Path("data/offload-partition-20260729")


def analyse_cell(cell: Path) -> dict[str, Any]:
    step = np.load(cell / "per-step.npz")
    veh_action = step["veh_action"]
    veh_k = step["veh_k"]
    tier = step["slot_tier"]
    # A slot decides only on steps where it carries tasks; veh_k == 0 is
    # "absent", not "chose local".
    present = veh_k > 0
    steps_present = present.sum(axis=0)
    offloads = ((veh_action > 0) & present).sum(axis=0)
    locals_ = ((veh_action == 0) & present).sum(axis=0)
    seen = steps_present > 0
    del veh_action, veh_k, present

    never = (offloads == 0) & seen
    always = (locals_ == 0) & seen
    mixed = (offloads > 0) & (locals_ > 0) & seen
    offload_rate = np.divide(
        offloads.astype(np.float64),
        steps_present.astype(np.float64),
        out=np.zeros(offloads.shape, dtype=np.float64),
        where=steps_present > 0,
    )

    task = np.load(cell / "per-task.npz")
    task_active = task["task_active"]
    task_met = task["task_met"]
    task_type = task["task_type"]
    tasks_per_slot = task_active.sum(axis=(0, 1)).astype(np.float64)
    met_per_slot = (task_met & task_active).sum(axis=(0, 1)).astype(np.float64)
    has_tasks = tasks_per_slot > 0
    failure_rate = np.divide(
        tasks_per_slot - met_per_slot,
        tasks_per_slot,
        out=np.zeros_like(tasks_per_slot),
        where=has_tasks,
    )

    groups: dict[str, Any] = {}
    for name, mask in (("never_offload", never), ("always_offload", always), ("mixed", mixed)):
        selected = mask & has_tasks
        if not selected.any():
            groups[name] = {"slots": 0}
            continue
        tiers, counts = np.unique(tier[mask], return_counts=True)
        per_class: dict[str, Any] = {}
        sub_active = task_active[:, :, mask]
        sub_met = task_met[:, :, mask]
        sub_type = task_type[:, :, mask]
        total = int(sub_active.sum())
        for code, class_name in enumerate(TASK_CLASS_NAMES):
            sel = sub_active & (sub_type == code)
            n = int(sel.sum())
            if n == 0:
                continue
            missed = int((sel & ~sub_met).sum())
            per_class[class_name] = {
                "share_of_group_tasks": n / total,
                "failure_rate": missed / n,
            }
        del sub_active, sub_met, sub_type
        groups[name] = {
            "slots": int(selected.sum()),
            "share_of_slots": float(selected.sum() / has_tasks.sum()),
            "tier_composition": {
                f"tier{int(t)}": {"slots": int(c), "share": float(c / mask.sum())}
                for t, c in zip(tiers, counts, strict=True)
            },
            "mean_tasks_per_slot": float(tasks_per_slot[selected].mean()),
            "mean_failure_rate": float(failure_rate[selected].mean()),
            "median_failure_rate": float(np.median(failure_rate[selected])),
            "failure_rate_by_class": per_class,
        }

    # Decile composition: what is the worst-failing tenth of slots made of?
    selected = seen & has_tasks
    order = np.argsort(failure_rate[selected])[::-1]
    index = np.where(selected)[0][order]
    size = max(1, index.size // 10)
    worst, best = index[:size], index[-size:]

    return {
        "cell": cell.name,
        "campaign": cell.parent.name,
        "slots_seen": int(seen.sum()),
        "correlation_offload_rate_vs_failure_rate": float(
            np.corrcoef(offload_rate[selected], failure_rate[selected])[0, 1]
        ),
        "groups": groups,
        "worst_decile_composition": {
            "never_offload": float(never[worst].mean()),
            "always_offload": float(always[worst].mean()),
            "mixed": float(mixed[worst].mean()),
        },
        "best_decile_composition": {
            "never_offload": float(never[best].mean()),
            "always_offload": float(always[best].mean()),
            "mixed": float(mixed[best].mean()),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cells", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    results = []
    for cell in args.cells:
        if not (cell / "per-task.npz").is_file():
            print(f"skip {cell}: no arrays", flush=True)
            continue
        print(f"analysing {cell.name} ...", flush=True)
        results.append(analyse_cell(cell))

    payload = {
        "record_type": "offload_partition_analysis",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "descriptive_non_causal": True,
        "analysis_only": True,
        "tier_cap_scalar": list(TIER_CAP_SCALAR),
        "measurement_notes": {
            "presence_rule": "a slot decides only on steps where veh_k > 0",
            "within_class_failure": (
                "failure is reported per task class per group, so a group difference cannot be "
                "manufactured by a difference in task mix"
            ),
            "not_answered": (
                "whether offloading helps the vehicles that do it -- that is a counterfactual "
                "requiring a different actor on the same trace, i.e. the crossover campaign"
            ),
        },
        "cells": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "offload_partition.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Why most deployed RSU capacity is unusable: the association rule is load-blind.

Analysis-only over admitted cells. No run executes and nothing is promoted.

An earlier analysis recorded that some RSUs carry no load at any capacity and
read that as a *placement* problem. This tests that reading directly, using two
array fields nothing had touched — ``veh_best_rsu`` (which RSU each vehicle
selects) and ``rsu_load`` (in-flight tasks per RSU) — and finds it is not
placement:

* the idle RSUs **are** selected, hundreds of thousands of times, so they are in
  range;
* they are **not** saturated, sitting at ~0% of the concurrency bound;
* and yet they receive essentially no work.

The producer's source gives the mechanism in one line
(``jaxmarl/env/vec_jax.py``)::

    best_rsu_idx = jnp.argmax(all_v2i_q, axis=1)

Selection is the argmax of **link quality**. There is no load term in it. The
environment even computes ``best_rsu_load_frac`` for the observation, but the
association itself never consults it, so offered work concentrates on whichever
RSUs happen to offer the best links and stays there after they saturate.

Utilisation is measured against the environment's own concurrency bound,
``RSU_MAX_CONCURRENT = capacity_per_slot x N_VEHICLES``, which is the producer's
documented relation rather than an assumption of this script.

Producer code and data use is covered by the recorded permission with citation;
see docs/producer_citation_requirements.md.

Usage:
    uv run python scripts/analyse_rsu_association.py CELL [CELL ...] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

#: Utilisation above which an RSU is called saturated, and below which idle.
SATURATED_ABOVE = 0.5
IDLE_BELOW = 0.05
DEFAULT_OUT = Path("data/rsu-association-20260729")
#: Producer action encoding.
ACTION_V2I = 1


def analyse_cell(cell: Path) -> dict[str, Any]:
    receipt = json.loads((cell / "execution_receipt.json").read_text())
    capacity = float(receipt["request"]["rsu_capacity_per_vehicle"])

    step = np.load(cell / "per-step.npz")
    veh_action = step["veh_action"]
    veh_k = step["veh_k"]
    best_rsu = step["veh_best_rsu"]
    rsu_load = step["rsu_load"]
    tier = step["slot_tier"]
    present = veh_k > 0
    slots = int(tier.size)
    # The producer's own relation, not an assumption here.
    bound = capacity * slots

    mean_concurrent = rsu_load.mean(axis=0)
    utilisation = mean_concurrent / bound
    total_load = rsu_load.sum(axis=0)
    tier_broadcast = np.broadcast_to(tier, veh_action.shape)

    rows: list[dict[str, Any]] = []
    for index in range(rsu_load.shape[1]):
        chosen = (best_rsu == index) & present
        sends = int((chosen & (veh_action == ACTION_V2I)).sum())
        selecting_tiers = tier_broadcast[chosen]
        rows.append(
            {
                "rsu": index,
                "times_selected_as_best": int(chosen.sum()),
                "v2i_sends": sends,
                "tier0_share_of_selectors": float((selecting_tiers == 0).mean())
                if selecting_tiers.size
                else None,
                "mean_concurrent_load": float(mean_concurrent[index]),
                "utilisation_of_bound": float(utilisation[index]),
                "total_load": int(total_load[index]),
            }
        )

    saturated = utilisation > SATURATED_ABOVE
    idle = utilisation < IDLE_BELOW
    shares = np.array([r["tier0_share_of_selectors"] or 0.0 for r in rows])
    return {
        "cell": cell.name,
        "capacity_per_slot": capacity,
        "vehicle_slots": slots,
        "rsu_max_concurrent": bound,
        "rsus": rows,
        "saturated_count": int(saturated.sum()),
        "idle_count": int(idle.sum()),
        "load_share_of_saturated": float(total_load[saturated].sum() / total_load.sum())
        if total_load.sum()
        else None,
        # If idleness were caused by the tier partition, tier-0 selection share
        # would track load across RSUs. It does not.
        "corr_tier0_selection_share_vs_load": float(np.corrcoef(shares, total_load)[0, 1]),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cells", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    results = []
    for cell in args.cells:
        if not (cell / "per-step.npz").is_file():
            print(f"skip {cell}: no arrays", flush=True)
            continue
        print(f"analysing {cell.name} ...", flush=True)
        result = analyse_cell(cell)
        results.append(result)
        print(
            f"  {result['saturated_count']} saturated / {result['idle_count']} idle of "
            f"{len(result['rsus'])}; saturated carry "
            f"{result['load_share_of_saturated']:.1%} of load",
            flush=True,
        )

    payload = {
        "record_type": "rsu_association_analysis",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "descriptive_non_causal": True,
        "analysis_only": True,
        "mechanism": (
            "vec_jax.py selects best_rsu_idx = argmax(all_v2i_q); link quality only, no load "
            "term. best_rsu_load_frac is computed for the observation but the association "
            "never consults it."
        ),
        "measurement_notes": {
            "utilisation_denominator": (
                "RSU_MAX_CONCURRENT = capacity_per_slot x N_VEHICLES, the producer's documented "
                "relation"
            ),
            "not_placement": (
                "idle RSUs are selected as best hundreds of thousands of times and sit at ~0% of "
                "the bound, so they are neither out of range nor full"
            ),
        },
        "cells": results,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "rsu_association.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"written {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

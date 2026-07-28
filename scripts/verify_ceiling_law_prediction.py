#!/usr/bin/env python3
"""Compute the pre-registered verdict on the tail-latency ceiling law.

**This file is committed before the tested data exists.** The pilot's own
methodological finding was that *a digest is only evidence if the code that
computes it is committed beside it*; the same argument applies with more force
to a pre-registered verdict. The prediction, the tolerance and the decision rule
below are transcribed from
``docs/evaluation/ceiling_law_prediction_predeclaration.md`` and the script
**refuses to run** if that document's SHA-256 has moved, so the rule cannot be
edited after the arms are seen.

The law under test, fitted on the 12 admitted pilot cells at capacities
2.5/1.5/1.0/0.75:

    L(c) = K * c,  K = 39,959 ms per unit capacity  (sigma 166, spread 0.41%)

where ``L`` is the p95 latency of *missed* tasks of a class. ``inc-deep``
extends the squeeze to 0.5/0.25/0.1 — 7.5x below the fitted floor — so this is
an extrapolation test, not a fit.

Two modes:

``selftest``
    Recompute K from the already-published pilot dynamics JSON and check the
    recipe reproduces the predeclared 39,959 / 166 / 0.41%. Reads one JSON file,
    touches no arrays, costs nothing. Run this *before* the campaign lands, to
    prove the measurement recipe here is the one that produced the law.

``verify``
    Apply the frozen rule to an admitted campaign's per-task arrays.
    **Heavy: loads ~400 MB of arrays per cell.** Campaign cells carry a 7,200 s
    timeout with ``halt_on_failure``; do not run this while a cell is in flight.

Usage:
    uv run python scripts/verify_ceiling_law_prediction.py selftest
    uv run python scripts/verify_ceiling_law_prediction.py verify \
        [--campaign data/vec-fresh/capacity-deep-inc] [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

# --- frozen inputs, transcribed from the predeclaration ----------------------

PREDECLARATION = Path("docs/evaluation/ceiling_law_prediction_predeclaration.md")
#: SHA-256 of the predeclaration as recorded when the campaign was launched.
#: A mismatch means the rule moved after the fact; the script refuses.
PREDECLARATION_SHA256 = "78dcd3ce3004d31edae87e8534a0a6e2dfb945e601649d7ac6cc26e3ffca7d4b"

#: Fitted constant of the law, ms of p95 missed-task latency per unit capacity.
K_MS_PER_UNIT_CAPACITY = 39_959.0
#: Pass band, +/-5% of the predicted ceiling (the pilot's own spread was 0.41%).
BAND_FRACTION = 0.05
#: The band as written in the predeclaration, in ms per unit capacity.
PREDECLARED_BAND_MS = (37_961.0, 41_957.0)
#: Predicted ceilings as written in the predeclaration, ms.
PREDECLARED_CEILINGS_MS = {0.5: 19_980.0, 0.25: 9_990.0, 0.1: 3_996.0}
#: The three extrapolation arms the verdict rule ranges over.
DEEP_ARMS = (0.5, 0.25, 0.1)
#: The in-range reference arm. Reported as a replication check, never as part of
#: the verdict: 2.5 is one of the capacities the law was fitted on.
REFERENCE_ARM = 2.5
#: Pilot statistics the selftest must reproduce.
PILOT_K_MEAN_MS = 39_959.0
PILOT_K_SIGMA_MS = 166.0
PILOT_K_SPREAD = 0.0041

TASK_CLASS_NAMES = ("T1", "T2", "T3")
CELL_NAME = re.compile(r"^cap-(?P<capacity>[0-9.]+)-fs(?P<seed>\d+)$")

DEFAULT_CAMPAIGN = Path("data/vec-fresh/capacity-deep-inc")
DEFAULT_OUT = Path("data/ceiling-law-verdict-20260729")


class PredeclarationMovedError(RuntimeError):
    """The frozen document backing this rule is not the one it was written for."""


def assert_predeclaration_unchanged(path: Path = PREDECLARATION) -> str:
    """Return the predeclaration digest, refusing if it has moved."""

    if not path.is_file():
        raise PredeclarationMovedError(f"PREDECLARATION_MISSING: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != PREDECLARATION_SHA256:
        raise PredeclarationMovedError(
            "PREDECLARATION_CHANGED_AFTER_APPROVAL: "
            f"{path} is {digest}, the frozen rule was written against "
            f"{PREDECLARATION_SHA256}"
        )
    return digest


def assert_constants_self_consistent() -> None:
    """Check the transcribed literals against the law they claim to encode.

    Guards against a typo in the transcription: the band and the per-arm
    ceilings are both derivable from K, so they must agree with it.
    """

    low = round(K_MS_PER_UNIT_CAPACITY * (1.0 - BAND_FRACTION))
    high = round(K_MS_PER_UNIT_CAPACITY * (1.0 + BAND_FRACTION))
    if (float(low), float(high)) != PREDECLARED_BAND_MS:
        raise PredeclarationMovedError(
            f"BAND_INCONSISTENT: K*(1+/-{BAND_FRACTION}) rounds to ({low}, {high}), "
            f"predeclaration states {PREDECLARED_BAND_MS}"
        )
    for capacity, predicted in PREDECLARED_CEILINGS_MS.items():
        derived = float(round(K_MS_PER_UNIT_CAPACITY * capacity))
        if derived != predicted:
            raise PredeclarationMovedError(
                f"CEILING_INCONSISTENT: K*{capacity} rounds to {derived}, "
                f"predeclaration states {predicted}"
            )


# --- measurement -------------------------------------------------------------


def _p95(values: npt.NDArray[np.floating[Any]]) -> float | None:
    """p95 of a non-empty vector, else None. Never substitutes a default."""

    if values.size == 0:
        return None
    return float(np.percentile(values, 95))


def parse_cell_name(name: str) -> tuple[float, int] | None:
    """Return (capacity, fleet seed) parsed from a cell directory name."""

    match = CELL_NAME.match(name)
    if match is None:
        return None
    return float(match.group("capacity")), int(match.group("seed"))


def cell_capacity(cell: Path) -> float:
    """Return the cell's requested capacity, from the receipt where possible.

    The receipt is authoritative; the directory name is a label and has been
    silently reformatted by a launcher edit before (``cap-1.0`` -> ``cap-1``).
    """

    receipt_path = cell / "execution_receipt.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        requested = receipt.get("request", {}).get("rsu_capacity_per_vehicle")
        if requested is not None:
            return float(requested)
    parsed = parse_cell_name(cell.name)
    if parsed is None:
        raise ValueError(f"CELL_CAPACITY_UNKNOWN: {cell.name} has no receipt and no parsable name")
    return parsed[0]


def measure_cell(cell: Path) -> dict[str, Any]:
    """Measure one admitted cell exactly as the pilot dynamics analysis did.

    The ceiling statistic is the p95 latency of *missed* tasks per class — the
    same expression as ``analyse_pilot_dynamics.py`` writes to
    ``deadline_slack_by_class[class].missed_latency.p95``.
    """

    capacity = cell_capacity(cell)
    task = np.load(cell / "per-task.npz")
    task_active = task["task_active"]
    task_met = task["task_met"]
    task_type = task["task_type"]
    task_lat = task["task_lat_ms"]

    classes: dict[str, Any] = {}
    for code, name in enumerate(TASK_CLASS_NAMES):
        selector = task_active & (task_type == code)
        if not selector.any():
            classes[name] = {"active_tasks": 0, "missed": 0, "p95_missed_latency_ms": None}
            continue
        missed_sel = selector & ~task_met
        met_lat = task_lat[selector & task_met]
        missed_lat = task_lat[missed_sel]
        p95 = _p95(missed_lat)
        classes[name] = {
            "active_tasks": int(selector.sum()),
            "met": int(selector.sum() - missed_sel.sum()),
            "missed": int(missed_sel.sum()),
            "attainment": float((selector.sum() - missed_sel.sum()) / selector.sum()),
            # The largest latency among met tasks is the class's empirical
            # deadline: observed, never read from configuration.
            "implied_deadline_ms": float(met_lat.max()) if met_lat.size else None,
            "p95_missed_latency_ms": p95,
            "observed_k_ms": None if p95 is None else p95 / capacity,
        }
        del selector, missed_sel, met_lat, missed_lat

    active_lat = task_lat[task_active]
    overall = {
        "active_tasks": int(task_active.sum()),
        "attainment": float((task_met & task_active).sum() / task_active.sum())
        if task_active.any()
        else None,
        # Secondary prediction 3: p50 stays ~44 ms at every arm.
        "p50_latency_ms": float(np.percentile(active_lat, 50)) if active_lat.size else None,
        "mean_latency_ms": float(active_lat.mean()) if active_lat.size else None,
    }
    del task_active, task_met, task_type, task_lat, active_lat

    # Secondary prediction 1: the never/always/mixed offload partition is
    # identical across arms within a seed. A slot decides only on steps where it
    # carries tasks; veh_k == 0 is "absent", not "chose local".
    step = np.load(cell / "per-step.npz")
    veh_action = step["veh_action"]
    veh_k = step["veh_k"]
    present = veh_k > 0
    per_slot_steps = present.sum(axis=0)
    offloads = ((veh_action > 0) & present).sum(axis=0)
    locals_ = ((veh_action == 0) & present).sum(axis=0)
    seen = per_slot_steps > 0
    partition = {
        "slots_ever_present": int(seen.sum()),
        "slots_never_offloading": int(((offloads == 0) & seen).sum()),
        "slots_always_offloading": int(((locals_ == 0) & seen).sum()),
        "slots_mixed": int(((offloads > 0) & (locals_ > 0) & seen).sum()),
    }
    del veh_action, veh_k, present, per_slot_steps, offloads, locals_, seen

    receipt_path = cell / "execution_receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else {}
    parsed = parse_cell_name(cell.name)
    return {
        "cell": cell.name,
        "capacity": capacity,
        "fleet_seed": receipt.get("request", {}).get("fleet_seed")
        or (parsed[1] if parsed else None),
        "receipt_fingerprint": receipt.get("receipt_fingerprint"),
        "elapsed_seconds": receipt.get("elapsed_seconds"),
        "by_class": classes,
        "overall": overall,
        "decision_partition": partition,
    }


# --- the frozen verdict rule -------------------------------------------------


def evaluate_verdict(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply the predeclaration's decision rule, exactly as written.

    From §3 of the predeclaration:

    - **HELD** — all three deep arms fall inside the band, for all three task
      classes.
    - **REFUTED** — any arm x class falls outside.
    - **BOUNDED** — the law holds at cap-0.5 but fails at cap-0.25 and/or
      cap-0.1; recorded as a distinct outcome, not a refutation.

    HELD and BOUNDED are both subsets of "not every pair passed", so the rule is
    applied in that precedence: HELD, else BOUNDED when cap-0.5 is clean, else
    REFUTED.

    A pair with no missed tasks has no p95 and therefore cannot be evaluated.
    The predeclared rule presumes all nine pairs exist, so rather than let a
    missing pair be read as a pass, the verdict is reported as **INCOMPLETE**
    with the gap named. This does not rescue the law: an INCOMPLETE verdict
    still lists every pair that fell outside the band.
    """

    low, high = PREDECLARED_BAND_MS
    pairs: list[dict[str, Any]] = []
    for cell in cells:
        capacity = float(cell["capacity"])
        if capacity not in DEEP_ARMS:
            continue
        for name in TASK_CLASS_NAMES:
            observed_k = cell["by_class"].get(name, {}).get("observed_k_ms")
            p95 = cell["by_class"].get(name, {}).get("p95_missed_latency_ms")
            predicted = PREDECLARED_CEILINGS_MS[capacity]
            pairs.append(
                {
                    "cell": cell["cell"],
                    "capacity": capacity,
                    "task_class": name,
                    "missed_tasks": cell["by_class"].get(name, {}).get("missed"),
                    "predicted_ceiling_ms": predicted,
                    "observed_p95_missed_ms": p95,
                    "observed_k_ms": observed_k,
                    "relative_error": None if p95 is None else (p95 - predicted) / predicted,
                    "evaluable": observed_k is not None,
                    "inside_band": None if observed_k is None else bool(low <= observed_k <= high),
                }
            )

    evaluable = [p for p in pairs if p["evaluable"]]
    non_evaluable = [p for p in pairs if not p["evaluable"]]
    outside = [p for p in evaluable if not p["inside_band"]]
    half_arm = [p for p in pairs if p["capacity"] == 0.5]
    half_arm_clean = bool(half_arm) and all(p["evaluable"] and p["inside_band"] for p in half_arm)

    expected_pairs = len(DEEP_ARMS) * len(TASK_CLASS_NAMES)
    seeds = sorted({c["fleet_seed"] for c in cells if float(c["capacity"]) in DEEP_ARMS})
    expected_total = expected_pairs * max(1, len(seeds))

    if non_evaluable or len(pairs) < expected_total:
        verdict = "INCOMPLETE"
    elif not outside:
        verdict = "HELD"
    elif half_arm_clean:
        verdict = "BOUNDED"
    else:
        verdict = "REFUTED"

    return {
        "verdict": verdict,
        "band_ms_per_unit_capacity": {"low": low, "high": high},
        "pairs_expected": expected_total,
        "pairs_evaluated": len(evaluable),
        "pairs_outside_band": len(outside),
        "pairs_not_evaluable": [
            {"cell": p["cell"], "task_class": p["task_class"], "missed_tasks": p["missed_tasks"]}
            for p in non_evaluable
        ],
        "cap_0_5_clean": half_arm_clean,
        "seeds": seeds,
        "pairs": pairs,
    }


def summarise_secondary(cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Report the three secondary predeclared predictions, without judging them.

    The predeclaration fixes them as expectations, not as pass/fail gates, so
    this reports the measurements and the one derived comparison the text names
    explicitly (partition identical across arms within a seed).
    """

    by_seed: dict[int, dict[str, Any]] = {}
    for cell in cells:
        seed = cell["fleet_seed"]
        by_seed.setdefault(seed, {})[cell["cell"]] = cell["decision_partition"]

    partition_identical: dict[str, bool] = {}
    for seed, arms in by_seed.items():
        signatures = {
            (p["slots_never_offloading"], p["slots_always_offloading"], p["slots_mixed"])
            for p in arms.values()
        }
        partition_identical[str(seed)] = len(signatures) == 1

    return {
        "prediction_1_partition_identical_within_seed": partition_identical,
        "prediction_1_partition_by_seed": {str(k): v for k, v in by_seed.items()},
        "prediction_2_attainment_by_cell": {c["cell"]: c["overall"]["attainment"] for c in cells},
        "prediction_3_p50_latency_ms_by_cell": {
            c["cell"]: c["overall"]["p50_latency_ms"] for c in cells
        },
    }


# --- selftest against the published pilot statistics -------------------------


def run_selftest(dynamics_json: Path) -> dict[str, Any]:
    """Reproduce the fitted K from the pilot dynamics JSON.

    Reads one JSON file and no arrays, so it is safe to run while campaign cells
    are timed. Its purpose is to prove that the p95-of-missed-latency expression
    used by ``measure_cell`` is the same one that produced the law.
    """

    payload = json.loads(dynamics_json.read_text())
    observed: list[float] = []
    detail: list[dict[str, Any]] = []
    for cell in payload["cells"]:
        parsed = parse_cell_name(cell["cell"])
        if parsed is None:
            continue
        capacity, _seed = parsed
        for name in TASK_CLASS_NAMES:
            block = cell.get("deadline_slack_by_class", {}).get(name)
            if not block:
                continue
            p95 = block.get("missed_latency", {}).get("p95")
            if p95 is None:
                continue
            k = float(p95) / capacity
            observed.append(k)
            detail.append(
                {"cell": cell["cell"], "task_class": name, "capacity": capacity, "observed_k_ms": k}
            )

    values: npt.NDArray[np.float64] = np.asarray(observed, dtype=np.float64)
    mean = float(values.mean())
    # Sample standard deviation (ddof=1). The published sigma of 166 ms is
    # reproduced only by the sample estimator: over these 36 pairs the
    # population estimator gives 163.4, which rounds to 163, not 166. Recorded
    # rather than reconciled away -- this selftest exists precisely to catch a
    # recipe that differs from the one that produced the law.
    sigma = float(values.std(ddof=1))
    spread = sigma / mean
    return {
        "pairs": int(values.size),
        "k_mean_ms": mean,
        "k_sigma_ms": sigma,
        "k_relative_spread": spread,
        "reproduces_predeclared_k": bool(round(mean) == round(PILOT_K_MEAN_MS)),
        "reproduces_predeclared_sigma": bool(round(sigma) == round(PILOT_K_SIGMA_MS)),
        "reproduces_predeclared_spread": bool(round(spread, 4) == round(PILOT_K_SPREAD, 4)),
        "detail": detail,
    }


# --- rendering ---------------------------------------------------------------


def render_markdown(payload: dict[str, Any]) -> str:
    verdict = payload["verdict_block"]
    lines = [
        "# Ceiling-law prediction test — computed verdict",
        "",
        "**Status: exploratory, `owner_approved_candidate`. No significance claimed, not",
        "confirmatory, not supervisor-approved. The rule below was frozen before any cell",
        f"ran; predeclaration digest `{payload['predeclaration_sha256'][:8]}…`.**",
        "",
        f"## Verdict: **{verdict['verdict']}**",
        "",
        f"Pass band {verdict['band_ms_per_unit_capacity']['low']:,.0f}–"
        f"{verdict['band_ms_per_unit_capacity']['high']:,.0f} ms per unit capacity "
        f"(K = {K_MS_PER_UNIT_CAPACITY:,.0f} ± {BAND_FRACTION:.0%}). "
        f"{verdict['pairs_evaluated']} of {verdict['pairs_expected']} predeclared "
        f"(arm × class × seed) pairs evaluated; "
        f"{verdict['pairs_outside_band']} outside the band.",
        "",
        "| Cell | Capacity | Class | Predicted (ms) | Observed p95 (ms) "
        "| Observed K | Rel. err | In band |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pair in verdict["pairs"]:
        observed = pair["observed_p95_missed_ms"]
        lines.append(
            "| {cell} | {cap} | {cls} | {pred:,.0f} | {obs} | {k} | {err} | {inband} |".format(
                cell=pair["cell"],
                cap=pair["capacity"],
                cls=pair["task_class"],
                pred=pair["predicted_ceiling_ms"],
                obs="—" if observed is None else f"{observed:,.1f}",
                k="—" if pair["observed_k_ms"] is None else f"{pair['observed_k_ms']:,.0f}",
                err="—" if pair["relative_error"] is None else f"{pair['relative_error']:+.2%}",
                inband="—"
                if pair["inside_band"] is None
                else ("yes" if pair["inside_band"] else "**NO**"),
            )
        )

    lines += [
        "",
        "## Reference arm (cap-2.5) — replication, not part of the verdict",
        "",
        "cap-2.5 is one of the capacities the law was fitted on, so it tests reproduction at",
        "fresh seeds rather than extrapolation.",
        "",
        "| Cell | Class | Observed p95 (ms) | Observed K |",
        "|---|---|---|---|",
    ]
    for cell in payload["cells"]:
        if float(cell["capacity"]) != REFERENCE_ARM:
            continue
        for name in TASK_CLASS_NAMES:
            block = cell["by_class"].get(name, {})
            p95 = block.get("p95_missed_latency_ms")
            k = block.get("observed_k_ms")
            lines.append(
                f"| {cell['cell']} | {name} | "
                f"{'—' if p95 is None else f'{p95:,.1f}'} | "
                f"{'—' if k is None else f'{k:,.0f}'} |"
            )

    secondary = payload["secondary"]
    lines += [
        "",
        "## Secondary predeclared predictions (reported, not gated)",
        "",
        "1. **Decision partition identical across arms within each seed** — "
        + ", ".join(
            f"seed {seed}: {'identical' if same else 'DIFFERS'}"
            for seed, same in secondary["prediction_1_partition_identical_within_seed"].items()
        )
        + ".",
        "2. **Deadline attainment by cell** — "
        + ", ".join(
            f"{cell} {value:.6f}" if value is not None else f"{cell} —"
            for cell, value in secondary["prediction_2_attainment_by_cell"].items()
        )
        + ".",
        "3. **p50 latency by cell (predicted ~44 ms)** — "
        + ", ".join(
            f"{cell} {value:,.1f} ms" if value is not None else f"{cell} —"
            for cell, value in secondary["prediction_3_p50_latency_ms_by_cell"].items()
        )
        + ".",
        "",
    ]
    return "\n".join(lines)


# --- entry point -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    selftest = sub.add_parser("selftest", help="reproduce K from the published pilot JSON")
    selftest.add_argument(
        "--dynamics-json",
        type=Path,
        default=Path("data/pilot-dynamics-20260728/pilot_dynamics.json"),
    )

    verify = sub.add_parser("verify", help="apply the frozen rule to an admitted campaign")
    verify.add_argument("--campaign", type=Path, default=DEFAULT_CAMPAIGN)
    verify.add_argument("--out", type=Path, default=DEFAULT_OUT)

    args = parser.parse_args()

    digest = assert_predeclaration_unchanged()
    assert_constants_self_consistent()

    if args.mode == "selftest":
        result = run_selftest(args.dynamics_json)
        print(json.dumps({k: v for k, v in result.items() if k != "detail"}, indent=2))
        ok = (
            result["reproduces_predeclared_k"]
            and result["reproduces_predeclared_sigma"]
            and result["reproduces_predeclared_spread"]
        )
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    campaign: Path = args.campaign
    cell_dirs = sorted(
        p
        for p in campaign.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / "per-task.npz").is_file()
    )
    if not cell_dirs:
        print(f"no admitted cells with arrays under {campaign}")
        return 1

    cells: list[dict[str, Any]] = []
    for cell in cell_dirs:
        print(f"measuring {cell.name} ...", flush=True)
        cells.append(measure_cell(cell))
        print(f"  done {cell.name}", flush=True)

    verdict_block = evaluate_verdict(cells)
    payload: dict[str, Any] = {
        "record_type": "ceiling_law_prediction_verdict",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "analysis_only": True,
        "campaign_dir": str(campaign),
        "predeclaration": str(PREDECLARATION),
        "predeclaration_sha256": digest,
        "law": {
            "k_ms_per_unit_capacity": K_MS_PER_UNIT_CAPACITY,
            "band_fraction": BAND_FRACTION,
            "predicted_ceilings_ms": {str(k): v for k, v in PREDECLARED_CEILINGS_MS.items()},
            "fitted_on": "12 admitted capacity-pilot cells, capacities 2.5/1.5/1.0/0.75",
        },
        "measurement_notes": {
            "ceiling_statistic": (
                "p95 latency of missed tasks per class, the same expression as "
                "analyse_pilot_dynamics.py deadline_slack_by_class[class].missed_latency.p95"
            ),
            "capacity_source": (
                "request.rsu_capacity_per_vehicle from the execution receipt; the directory "
                "name is a label and has been reformatted by a launcher edit before"
            ),
            "presence_rule": (
                "a slot decides only on steps where veh_k > 0; absent steps are not counted "
                "as local decisions"
            ),
            "reference_arm": (
                "cap-2.5 is inside the fitted range and is reported as a replication check, "
                "never as part of the extrapolation verdict"
            ),
        },
        "cells": cells,
        "verdict_block": verdict_block,
        "secondary": summarise_secondary(cells),
    }

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "ceiling_law_verdict.json").write_text(json.dumps(payload, indent=2) + "\n", "utf-8")
    (out / "ceiling_law_verdict.md").write_text(render_markdown(payload), "utf-8")
    print(f"VERDICT: {verdict_block['verdict']}")
    print(f"written {out / 'ceiling_law_verdict.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

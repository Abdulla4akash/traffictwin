#!/usr/bin/env python3
"""Produce the actor-crossover verdict for the incident trace.

The crossover rule itself lives in the accepted
``vec_campaign/slope_comparison.py`` and is applied here unchanged. What this
runner adds is the missing half: a way to actually run it over the two
campaigns, plus the decidable form of the candidate's prediction (3), fixed in
``docs/evaluation/crossover_slope_prediction_addendum.md`` before the second
actor's campaign produced a single cell.

The contrast is between two audited actors on the same trace, arms, seeds,
fleet preset and evaluator seed:

* ``ukfleettrain_mappo_model_c_17`` -- the **already admitted** capacity pilot
* ``baseline_model_c_17``          -- the ``inc-baseline`` campaign

Nothing about the pilot is re-run or altered; it is read as one arm of the
contrast.

**The fleet preset matches one actor's training distribution and not the
other's.** That asymmetry is part of the design, and it is carried into every
output here rather than left for a reader to rediscover.

Reads only campaign-analysis JSON -- no arrays, no runs -- so it is safe to run
while campaign cells are timed.

Usage:
    uv run python scripts/analyse_actor_crossover.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from traffictwin.integration.vec_campaign.analysis import VecCampaignAnalysis
from traffictwin.integration.vec_campaign.slope_comparison import (
    compare_actor_capacity_slopes,
    render_slope_comparison_markdown,
)

# --- frozen inputs -----------------------------------------------------------

#: The candidate bound into the launched inc-baseline design. Must never move.
CANDIDATE = Path("docs/evaluation/actor_crossover_candidate_inc_20260728.md")
CANDIDATE_SHA256 = "b8f0efa29f4c41210b44447595a53b2975e47af913f3057c1ac1e1540c885492"

#: The addendum making prediction (3) decidable, committed with this file.
ADDENDUM = Path("docs/evaluation/crossover_slope_prediction_addendum.md")
ADDENDUM_SHA256 = "a75f90bbc5e73a4bcab3ee179e8e08f7ae9c381d1a75fb22825d2eedb0c2af85"

PILOT_ANALYSIS = Path("data/vec-fresh/capacity-pilot/campaign_analysis.json")
BASELINE_ANALYSIS = Path("data/vec-fresh/crossover-inc-baseline/campaign_analysis.json")

PILOT_ACTOR = "ukfleettrain_mappo_model_c_17"
BASELINE_ACTOR = "baseline_model_c_17"
EXPECTED_SEED_COUNT = 3

LATENCY_METRIC = "task.latency.mean_ms"
#: Transcribed from the ceiling-law predeclaration's tolerance for the same
#: underlying quantity; not chosen for this comparison.
SLOPE_CONTRAST_BAND = 0.05

DEFAULT_OUT = Path("data/actor-crossover-verdict-20260729")

PRESET_ASYMMETRY = (
    "the uk2030 fleet preset matches ukfleettrain_mappo_model_c_17's training "
    "distribution and not baseline_model_c_17's; an actor-dependent result has at "
    "least two live explanations (policy or preset mismatch) and this comparison "
    "cannot distinguish them"
)


class PredeclarationMovedError(RuntimeError):
    """A frozen document backing this rule is not the one it was written for."""


def assert_frozen_documents() -> dict[str, str]:
    """Return both digests, refusing if either has moved."""

    digests: dict[str, str] = {}
    for path, expected in ((CANDIDATE, CANDIDATE_SHA256), (ADDENDUM, ADDENDUM_SHA256)):
        if not path.is_file():
            raise PredeclarationMovedError(f"PREDECLARATION_MISSING: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise PredeclarationMovedError(
                f"PREDECLARATION_CHANGED_AFTER_APPROVAL: {path} is {digest}, "
                f"the frozen rule was written against {expected}"
            )
        digests[str(path)] = digest
    return digests


def _ols_slope(points: list[tuple[float, float]]) -> float:
    """Least-squares slope of y over x.

    Deliberately a local reimplementation: the accepted module's OLS is private
    and applies to the primary endpoint only, and editing an accepted module to
    reach a secondary series has been rejected before.
    """

    count = len(points)
    mean_x = sum(x for x, _ in points) / count
    mean_y = sum(y for _, y in points) / count
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        raise ValueError("SLOPE_DEGENERATE: capacity levels have no spread")
    return sum((x - mean_x) * (y - mean_y) for x, y in points) / denominator


def latency_curve(analysis: VecCampaignAnalysis) -> dict[str, Any]:
    """Return the per-capacity mean latency series and its OLS slope."""

    points: list[tuple[float, float]] = []
    support: dict[float, int] = {}
    for row in analysis.secondary_descriptives:
        if row.metric_key != LATENCY_METRIC:
            continue
        if not row.arm_label.startswith("cap-"):
            raise ValueError(f"ARM_LABEL_UNPARSEABLE: {row.arm_label!r}")
        capacity = float(row.arm_label[4:])
        points.append((capacity, row.mean))
        support[capacity] = len(row.seed_values)
    points.sort()
    if len(points) < 2:
        raise ValueError(f"LATENCY_SERIES_TOO_SHORT: {LATENCY_METRIC} needs two or more levels")
    return {
        "metric_key": LATENCY_METRIC,
        "capacity_levels": [x for x, _ in points],
        "mean_by_level": [y for _, y in points],
        "seed_support_by_level": [support[x] for x, _ in points],
        "complete_support": all(value >= EXPECTED_SEED_COUNT for value in support.values()),
        "ols_slope_ms_per_capacity_unit": _ols_slope(points),
    }


def evaluate_prediction_three(pilot: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Apply the addendum's band to the relative latency-slope contrast."""

    slope_a = float(pilot["ols_slope_ms_per_capacity_unit"])
    slope_b = float(baseline["ols_slope_ms_per_capacity_unit"])
    denominator = (abs(slope_a) + abs(slope_b)) / 2.0
    contrast = None if denominator == 0 else abs(slope_a - slope_b) / denominator
    complete = bool(pilot["complete_support"] and baseline["complete_support"])
    levels_match = pilot["capacity_levels"] == baseline["capacity_levels"]

    if contrast is None or not complete or not levels_match:
        verdict = "INCOMPLETE"
    elif contrast <= SLOPE_CONTRAST_BAND:
        verdict = "HELD"
    else:
        verdict = "REFUTED"

    return {
        "prediction": (
            "the mean-latency slope over capacity is actor-independent, because the "
            "tail-latency ceiling is a property of the control rather than the policy"
        ),
        "verdict": verdict,
        "band": SLOPE_CONTRAST_BAND,
        "band_provenance": (
            "transcribed from the ceiling-law predeclaration's tolerance for the same "
            "underlying quantity; not chosen for this comparison"
        ),
        "slope_ms_per_capacity_unit": {PILOT_ACTOR: slope_a, BASELINE_ACTOR: slope_b},
        "relative_slope_contrast": contrast,
        "complete_seed_support": complete,
        "capacity_levels_match": levels_match,
        "interpretation_limit": PRESET_ASYMMETRY,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--pilot-analysis", type=Path, default=PILOT_ANALYSIS)
    parser.add_argument("--baseline-analysis", type=Path, default=BASELINE_ANALYSIS)
    args = parser.parse_args()

    digests = assert_frozen_documents()

    missing = [p for p in (args.pilot_analysis, args.baseline_analysis) if not p.is_file()]
    if missing:
        print("INCOMPLETE: campaign analysis missing for " + ", ".join(str(p) for p in missing))
        return 1

    pilot = VecCampaignAnalysis.model_validate_json(args.pilot_analysis.read_text())
    baseline = VecCampaignAnalysis.model_validate_json(args.baseline_analysis.read_text())

    # The predeclared crossover rule, applied by the accepted module unchanged.
    comparison = compare_actor_capacity_slopes(
        pilot,
        baseline,
        first_actor_id=PILOT_ACTOR,
        second_actor_id=BASELINE_ACTOR,
        expected_seed_count=EXPECTED_SEED_COUNT,
    )

    pilot_latency = latency_curve(pilot)
    baseline_latency = latency_curve(baseline)
    prediction_three = evaluate_prediction_three(pilot_latency, baseline_latency)

    payload: dict[str, Any] = {
        "record_type": "actor_crossover_verdict",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "descriptive_non_causal": True,
        "analysis_only": True,
        "predeclaration_digests": digests,
        "actors": {"first": PILOT_ACTOR, "second": BASELINE_ACTOR},
        "sources": {
            "first": str(args.pilot_analysis),
            "second": str(args.baseline_analysis),
        },
        "interpretation_limits": [
            PRESET_ASYMMETRY,
            (
                "a crossover, if found, is a statement about two audited checkpoints on one "
                "trace under one fleet preset, never about algorithm families"
            ),
            "exploratory; held-out seeds {10-14} remain spent and untouched",
        ],
        "crossover_rule": comparison.model_dump(mode="json"),
        "latency_curves": {PILOT_ACTOR: pilot_latency, BASELINE_ACTOR: baseline_latency},
        "prediction_three": prediction_three,
    }

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "actor_crossover_verdict.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", "utf-8"
    )

    contrast = prediction_three["relative_slope_contrast"]
    report = "\n".join(
        [
            render_slope_comparison_markdown(comparison).rstrip(),
            "",
            "## Prediction (3): is the latency slope actor-independent?",
            "",
            f"- Verdict: **{prediction_three['verdict']}** "
            f"(band: relative contrast ≤ {SLOPE_CONTRAST_BAND:.0%})",
            f"- `{PILOT_ACTOR}`: "
            f"{pilot_latency['ols_slope_ms_per_capacity_unit']:+,.1f} ms per capacity unit",
            f"- `{BASELINE_ACTOR}`: "
            f"{baseline_latency['ols_slope_ms_per_capacity_unit']:+,.1f} ms per capacity unit",
            "- Relative slope contrast: " + ("—" if contrast is None else f"{contrast:.2%}"),
            "",
            f"**Interpretation limit.** {PRESET_ASYMMETRY.capitalize()}.",
            "",
        ]
    )
    (out / "actor_crossover_verdict.md").write_text(report, "utf-8")

    print(
        f"CROSSOVER DETECTED: {comparison.crossover_detected} "
        f"(rule applicable: {comparison.crossover_rule_applicable})"
    )
    print(f"PREDICTION (3): {prediction_three['verdict']}")
    print(f"written {out / 'actor_crossover_verdict.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

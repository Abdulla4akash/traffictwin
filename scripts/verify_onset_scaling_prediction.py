#!/usr/bin/env python3
"""Compute the pre-registered verdict on the onset-scaling hypothesis.

Committed **before any cell of the three onset legs had run**, together with
``docs/evaluation/onset_scaling_prediction_predeclaration.md``, so neither the
onset rule nor the per-trace predictions can be adjusted once the arms are
visible. Both that addendum and the campaign-bound memo it operationalises are
re-hashed at run time and a mismatch is a refusal.

The hypothesis (``density_gap_options_20260728.md`` §"Option C"): *onset
capacity scales with concurrent density*, ``c_onset = kappa * N``. Only ``ev``
has a bracketed onset -- ``cap-0.25`` exactly identical to baseline, ``cap-0.1``
binding -- so ``c_onset(ev) in (0.1, 0.25]`` and the bracket is propagated to
the other traces rather than collapsed to a point.

Onset is defined by **exact identity**, transcribed from the committed
five-regime and deep-squeeze records: an arm is inert when every metric at every
seed equals the baseline arm's value exactly, and binds otherwise. There is no
tolerance parameter to tune.

Both modes read only campaign-analysis JSON -- no arrays, no runs -- so this is
safe to run while campaign cells are timed.

Usage:
    uv run python scripts/verify_onset_scaling_prediction.py selftest
    uv run python scripts/verify_onset_scaling_prediction.py verify [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

# --- frozen inputs -----------------------------------------------------------

#: The campaign-bound memo stating the hypothesis. Three launched designs bind
#: this digest, so it must never move.
MEMO = Path("docs/evaluation/density_gap_options_20260728.md")
MEMO_SHA256 = "00681a14efb5b7134fb81abae0f365c27148972723d6ae3140deecfd2254ef3a"

#: The addendum that operationalises it, committed with this file.
ADDENDUM = Path("docs/evaluation/onset_scaling_prediction_predeclaration.md")
ADDENDUM_SHA256 = "58a3ec628f1ec330ecbd4ebb5ed5bc52c4b4ff7b0550c8051cb2d9fb3a789cc4"

#: Maximum concurrent vehicle slots per trace, copied from the hash-bound
#: source-snapshot audit via the committed cross-regime projection evidence.
TRACE_SLOTS = {"we": 139, "wd_pm": 163, "ev": 175, "wd_am": 215, "inc": 2_488}

#: The one measured onset bracket: ev is inert at 0.25 and binds at 0.1.
EV_ONSET_BRACKET = (0.1, 0.25)
#: kappa = c_onset / N, propagated from that bracket.
KAPPA_LOW = EV_ONSET_BRACKET[0] / TRACE_SLOTS["ev"]
KAPPA_HIGH = EV_ONSET_BRACKET[1] / TRACE_SLOTS["ev"]

DEEP_ARMS = (0.5, 0.25, 0.1)
BASELINE_ARM_LABEL = "cap-2.5"

#: Campaign output directory per trace under test.
CAMPAIGN_DIRS = {
    "we": Path("data/vec-fresh/capacity-deep-we"),
    "wd_am": Path("data/vec-fresh/capacity-deep-wd-am"),
    "wd_pm": Path("data/vec-fresh/capacity-deep-wd-pm"),
    "ev": Path("data/vec-fresh/capacity-deep-ev"),
}
#: The three legs this verdict ranges over. `ev` is the source of the bracket,
#: not a test of it, and contributes only to the ordering qualifier.
TESTED_TRACES = ("we", "wd_pm", "wd_am")

Expectation = Literal["inert", "binds", "indeterminate"]

#: The prediction table as written in the addendum §3. Derived independently in
#: `derive_expectations()` and checked against these literals, so a typo here
#: cannot quietly widen or narrow what was predicted.
PREDECLARED_EXPECTATIONS: dict[tuple[str, float], Expectation] = {
    ("we", 0.5): "inert",
    ("we", 0.25): "inert",
    ("we", 0.1): "indeterminate",
    ("wd_pm", 0.5): "inert",
    ("wd_pm", 0.25): "inert",
    ("wd_pm", 0.1): "indeterminate",
    ("wd_am", 0.5): "inert",
    ("wd_am", 0.25): "indeterminate",
    ("wd_am", 0.1): "binds",
}

DEFAULT_OUT = Path("data/onset-scaling-verdict-20260729")


class PredeclarationMovedError(RuntimeError):
    """A frozen document backing this rule is not the one it was written for."""


def assert_frozen_documents() -> dict[str, str]:
    """Return both digests, refusing if either has moved."""

    digests: dict[str, str] = {}
    for path, expected in ((MEMO, MEMO_SHA256), (ADDENDUM, ADDENDUM_SHA256)):
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


def onset_band(trace: str) -> tuple[float, float]:
    """Return the predicted (exclusive low, inclusive high) onset band."""

    slots = TRACE_SLOTS[trace]
    return KAPPA_LOW * slots, KAPPA_HIGH * slots


def derive_expectations() -> dict[tuple[str, float], Expectation]:
    """Derive the prediction table from the propagated band.

    An arm binds iff its capacity is at or below the onset. With the onset known
    only to lie in ``(low, high]``, a capacity above ``high`` is certainly inert,
    a capacity at or below ``low`` certainly binds, and anything between is
    indeterminate -- the sweep resolves those cells rather than testing them.
    """

    derived: dict[tuple[str, float], Expectation] = {}
    for trace in TESTED_TRACES:
        low, high = onset_band(trace)
        for capacity in DEEP_ARMS:
            if capacity > high:
                derived[(trace, capacity)] = "inert"
            elif capacity <= low:
                derived[(trace, capacity)] = "binds"
            else:
                derived[(trace, capacity)] = "indeterminate"
    return derived


def assert_expectations_self_consistent() -> None:
    """Check the transcribed prediction table against the band it comes from."""

    derived = derive_expectations()
    if derived != PREDECLARED_EXPECTATIONS:
        differences = {
            key: (PREDECLARED_EXPECTATIONS.get(key), value)
            for key, value in derived.items()
            if PREDECLARED_EXPECTATIONS.get(key) != value
        }
        raise PredeclarationMovedError(
            f"EXPECTATIONS_INCONSISTENT: derived table disagrees with the "
            f"transcribed one at {differences}"
        )


# --- measurement -------------------------------------------------------------


def _arm_metrics(analysis: dict[str, Any]) -> dict[str, dict[str, dict[str, float]]]:
    """Return {arm_label: {metric_key: {seed: value}}} from a campaign analysis."""

    rows = list(analysis.get("primary_descriptives", [])) + list(
        analysis.get("secondary_descriptives", [])
    )
    by_arm: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        by_arm.setdefault(row["arm_label"], {})[row["metric_key"]] = row["seed_values"]
    return by_arm


def measure_trace(trace: str, campaign_dir: Path) -> dict[str, Any]:
    """Classify each deep arm as inert or binding, and locate the onset."""

    analysis_path = campaign_dir / "campaign_analysis.json"
    if not analysis_path.is_file():
        return {
            "trace": trace,
            "slots": TRACE_SLOTS[trace],
            "campaign_dir": str(campaign_dir),
            "state": "NOT_RUN",
            "arms": {},
            "measured_onset": None,
            "onset_censored_below": None,
        }

    analysis = json.loads(analysis_path.read_text())
    by_arm = _arm_metrics(analysis)
    baseline_label = analysis.get("baseline_label", BASELINE_ARM_LABEL)
    baseline = by_arm.get(baseline_label)
    if baseline is None:
        raise ValueError(f"BASELINE_ARM_MISSING: {baseline_label} not in {analysis_path}")

    paired_difference = {
        c["variation_label"]: c.get("mean_paired_difference")
        for c in analysis.get("comparisons", [])
    }

    arms: dict[str, Any] = {}
    binding: list[float] = []
    for capacity in DEEP_ARMS:
        label = next(
            (name for name in by_arm if name != baseline_label and _capacity_of(name) == capacity),
            None,
        )
        if label is None:
            arms[f"cap-{capacity:g}"] = {"state": "ARM_MISSING"}
            continue
        variation = by_arm[label]
        if set(variation) != set(baseline):
            arms[label] = {
                "state": "METRIC_SET_MISMATCH",
                "baseline_metrics": sorted(baseline),
                "variation_metrics": sorted(variation),
            }
            continue
        differing = [key for key in baseline if variation[key] != baseline[key]]
        max_abs = 0.0
        for key in baseline:
            for seed, value in baseline[key].items():
                max_abs = max(max_abs, abs(float(variation[key][seed]) - float(value)))
        inert = not differing
        arms[label] = {
            "capacity": capacity,
            "state": "inert" if inert else "binds",
            "metrics_compared": len(baseline),
            "metrics_differing": differing,
            "max_abs_difference": max_abs,
            "primary_mean_paired_difference": paired_difference.get(label),
        }
        if not inert:
            binding.append(capacity)

    measured_onset = max(binding) if binding else None
    # Non-monotone response: an arm binds while a tighter one below it does not.
    # A tighter squeeze that leaves outcomes untouched while a looser one moves
    # them contradicts the whole onset picture, so it is flagged, not smoothed.
    non_monotone = False
    if measured_onset is not None:
        non_monotone = any(
            block.get("state") == "inert" and float(block["capacity"]) < measured_onset
            for block in arms.values()
            if "capacity" in block
        )
    return {
        "trace": trace,
        "slots": TRACE_SLOTS[trace],
        "campaign_dir": str(campaign_dir),
        "state": "MEASURED",
        "design_fingerprint": analysis.get("design_fingerprint"),
        "campaign_status": analysis.get("campaign_status"),
        "arms": arms,
        "measured_onset": measured_onset,
        "onset_censored_below": None if measured_onset is not None else min(DEEP_ARMS),
        "non_monotone_response": non_monotone,
    }


def _capacity_of(arm_label: str) -> float | None:
    """Parse the capacity out of a ``cap-<value>`` arm label."""

    if not arm_label.startswith("cap-"):
        return None
    try:
        return float(arm_label[4:])
    except ValueError:
        return None


# --- the frozen verdict rule -------------------------------------------------


def evaluate_verdict(measurements: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply the addendum's rule: HELD iff all six sharp predictions hold.

    A leg with no campaign analysis makes the verdict INCOMPLETE and is named;
    missing data is never read as a passed prediction.
    """

    checks: list[dict[str, Any]] = []
    missing_legs = [t for t in TESTED_TRACES if measurements[t]["state"] != "MEASURED"]

    for (trace, capacity), expectation in sorted(PREDECLARED_EXPECTATIONS.items()):
        if expectation == "indeterminate":
            continue
        arms = measurements[trace]["arms"]
        label = next(
            (name for name, block in arms.items() if block.get("capacity") == capacity), None
        )
        observed = arms.get(label, {}).get("state") if label else None
        checks.append(
            {
                "trace": trace,
                "slots": TRACE_SLOTS[trace],
                "capacity": capacity,
                "predicted": expectation,
                "observed": observed,
                "decided": observed in {"inert", "binds"},
                "correct": None if observed not in {"inert", "binds"} else observed == expectation,
                "load_bearing": expectation == "binds",
            }
        )

    undecided = [c for c in checks if not c["decided"]]
    wrong = [c for c in checks if c["correct"] is False]

    if missing_legs or undecided:
        verdict = "INCOMPLETE"
    elif wrong:
        verdict = "REFUTED"
    else:
        verdict = "HELD"

    # Qualifier 1: are measured onsets weakly ordered by density? Censored
    # traces are tied below the floor, so they compare as a value under 0.1.
    def onset_key(trace: str) -> float:
        onset = measurements[trace]["measured_onset"]
        return float(onset) if onset is not None else 0.0

    ordered_traces = sorted(TRACE_SLOTS, key=lambda t: TRACE_SLOTS[t])
    available = [t for t in ordered_traces if measurements.get(t, {}).get("state") == "MEASURED"]
    onsets = [onset_key(t) for t in available]
    ordering_preserved = all(a <= b for a, b in zip(onsets, onsets[1:], strict=False))

    # Qualifier 2: every deep arm inert on all three tested traces.
    all_censored = bool(
        all(
            measurements[t]["state"] == "MEASURED" and measurements[t]["measured_onset"] is None
            for t in TESTED_TRACES
        )
    )

    return {
        "verdict": verdict,
        "checks": checks,
        "sharp_predictions": len(checks),
        "sharp_predictions_correct": sum(1 for c in checks if c["correct"] is True),
        "sharp_predictions_wrong": len(wrong),
        "missing_legs": missing_legs,
        "undecided": [
            {"trace": c["trace"], "capacity": c["capacity"], "observed": c["observed"]}
            for c in undecided
        ],
        "qualifiers": {
            "ordering_preserved": ordering_preserved,
            "ordering_basis": [
                {
                    "trace": t,
                    "slots": TRACE_SLOTS[t],
                    "measured_onset": measurements[t]["measured_onset"],
                }
                for t in available
            ],
            "all_censored_at_floor": all_censored,
        },
    }


# --- selftest ----------------------------------------------------------------


def run_selftest() -> dict[str, Any]:
    """Reproduce the published `ev` onset with the rule defined here.

    ``ev`` is where the bracket comes from, so if this rule does not reproduce
    the committed record -- inert at 0.5 and 0.25, binding at 0.1 -- then the
    rule is not the one the hypothesis was built on.
    """

    measured = measure_trace("ev", CAMPAIGN_DIRS["ev"])
    states = {
        block.get("capacity"): block.get("state")
        for block in measured["arms"].values()
        if "capacity" in block
    }
    expected = {0.5: "inert", 0.25: "inert", 0.1: "binds"}
    return {
        "trace": "ev",
        "observed_states": {str(k): v for k, v in states.items()},
        "expected_states": {str(k): v for k, v in expected.items()},
        "measured_onset": measured["measured_onset"],
        "reproduces_published_record": states == expected and measured["measured_onset"] == 0.1,
        "arms": measured["arms"],
    }


# --- rendering ---------------------------------------------------------------


def render_markdown(payload: dict[str, Any]) -> str:
    block = payload["verdict_block"]
    lines = [
        "# Onset-scaling prediction test — computed verdict",
        "",
        "**Status: exploratory, `owner_approved_candidate`. No significance claimed, not",
        "confirmatory, not supervisor-approved. Rule and predictions frozen before any cell of",
        "the three onset legs ran; addendum digest "
        f"`{payload['predeclaration_digests'][str(ADDENDUM)][:8]}…`.**",
        "",
        f"## Verdict: **{block['verdict']}**",
        "",
        f"{block['sharp_predictions_correct']} of {block['sharp_predictions']} sharp predictions "
        f"correct; {block['sharp_predictions_wrong']} wrong.",
        "",
        "| Trace | Slots | Arm | Predicted | Observed | Correct | Load-bearing |",
        "|---|---|---|---|---|---|---|",
    ]
    for check in block["checks"]:
        lines.append(
            "| {trace} | {slots} | cap-{cap:g} | {pred} | {obs} | {ok} | {lb} |".format(
                trace=check["trace"],
                slots=check["slots"],
                cap=check["capacity"],
                pred=check["predicted"],
                obs=check["observed"] or "—",
                ok="—" if check["correct"] is None else ("yes" if check["correct"] else "**NO**"),
                lb="**yes**" if check["load_bearing"] else "",
            )
        )

    qualifiers = block["qualifiers"]
    lines += [
        "",
        "## Measured onset by density",
        "",
        "| Trace | Slots | Predicted band | Measured onset |",
        "|---|---|---|---|",
    ]
    for entry in sorted(payload["measurements"].values(), key=lambda m: m["slots"]):
        trace = entry["trace"]
        low, high = onset_band(trace)
        onset = entry["measured_onset"]
        lines.append(
            f"| {trace} | {entry['slots']} | ({low:.4f}, {high:.4f}] | "
            + (
                "not run"
                if entry["state"] != "MEASURED"
                else (f"{onset:g}" if onset is not None else "censored < 0.1")
            )
            + " |"
        )

    lines += [
        "",
        "## Qualifiers (descriptive, reported alongside the verdict)",
        "",
        f"- `ordering_preserved`: **{qualifiers['ordering_preserved']}** — whether measured "
        "onsets are weakly ordered by density.",
        f"- `all_censored_at_floor`: **{qualifiers['all_censored_at_floor']}** — whether every "
        "deep arm was inert on all three tested traces.",
        "",
    ]
    if block["missing_legs"]:
        lines += [f"- Legs with no campaign analysis: {', '.join(block['missing_legs'])}.", ""]
    return "\n".join(lines)


# --- entry point -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("selftest", help="reproduce the published ev onset with this rule")
    verify = sub.add_parser("verify", help="apply the frozen rule to the three onset legs")
    verify.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    digests = assert_frozen_documents()
    assert_expectations_self_consistent()

    if args.mode == "selftest":
        result = run_selftest()
        print(json.dumps({k: v for k, v in result.items() if k != "arms"}, indent=2, default=str))
        ok = bool(result["reproduces_published_record"])
        print("SELFTEST", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    measurements = {
        trace: measure_trace(trace, directory) for trace, directory in CAMPAIGN_DIRS.items()
    }
    verdict_block = evaluate_verdict(measurements)
    payload: dict[str, Any] = {
        "record_type": "onset_scaling_prediction_verdict",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "confirmatory": False,
        "significance_claimed": False,
        "analysis_only": True,
        "predeclaration_digests": digests,
        "hypothesis": {
            "statement": "onset capacity scales with concurrent density, c_onset = kappa * N",
            "ev_onset_bracket": list(EV_ONSET_BRACKET),
            "kappa_band": [KAPPA_LOW, KAPPA_HIGH],
            "predicted_bands": {t: list(onset_band(t)) for t in TRACE_SLOTS},
        },
        "measurement_notes": {
            "onset_rule": (
                "an arm is inert when every metric at every seed equals the baseline arm's "
                "value exactly; onset is the largest binding arm capacity, else censored "
                "below the 0.1 grid floor"
            ),
            "rule_provenance": (
                "transcribed from the committed five-regime and deep-squeeze records, which "
                "already judge response by exact identity; no tolerance parameter exists"
            ),
            "ev_role": (
                "ev supplies the bracket and is therefore not a test of it; it contributes "
                "only to the ordering qualifier"
            ),
            "inc_role": (
                "the pilot shows cap-1.5 differs from cap-2.5, so c_onset(inc) >= 1.5, inside "
                "the predicted band; with no arm above 2.5 this is a consistency check, not a "
                "test"
            ),
        },
        "measurements": measurements,
        "verdict_block": verdict_block,
    }

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "onset_scaling_verdict.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", "utf-8"
    )
    (out / "onset_scaling_verdict.md").write_text(render_markdown(payload), "utf-8")
    print(f"VERDICT: {verdict_block['verdict']}")
    print(f"written {out / 'onset_scaling_verdict.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

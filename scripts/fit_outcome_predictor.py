#!/usr/bin/env python3
"""Fit the VEC outcome predictor and write the committed fit artifact.

Reads the thirteen registered admitted campaign analyses, the pilot-dynamics
artifact, the final ceiling-law verdict, and the committed latency-tail
record; refuses everything else by name. The self-test gate inside
``fit_outcome_predictor`` must reproduce the published constants or no
artifact is written.

Usage:
    uv run python scripts/fit_outcome_predictor.py \
        [--output docs/platform/outcome_predictor_fit.json]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.platform.outcome_predictor import (
    OutcomePredictorError,
    fit_outcome_predictor,
    load_outcome_predictor_fit,
    write_fit_artifact,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

CAMPAIGN_ANALYSIS_DIRECTORIES = (
    "capacity-pilot",
    "capacity-confirmatory",
    "capacity-deep-inc",
    "crossover-inc-baseline",
    "capacity-grid-we",
    "capacity-grid-ev",
    "capacity-grid-wd-am",
    "capacity-grid-wd-pm",
    "capacity-deep-we",
    "capacity-deep-ev",
    "capacity-deep-wd-am",
    "capacity-deep-wd-pm",
    "baseline-invariance-ev",
)

EXTRA_SOURCES = (
    "data/pilot-dynamics-20260728/pilot_dynamics.json",
    "data/ceiling-law-verdict-20260729/final/ceiling_law_verdict.json",
    "docs/evaluation/latency_tail_analysis_20260728.md",
)

DEFAULT_OUTPUT = REPO_ROOT / "docs" / "platform" / "outcome_predictor_fit.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    paths = [
        REPO_ROOT / "data" / "vec-fresh" / directory / "campaign_analysis.json"
        for directory in CAMPAIGN_ANALYSIS_DIRECTORIES
    ] + [REPO_ROOT / relative for relative in EXTRA_SOURCES]

    try:
        fit = fit_outcome_predictor(
            paths,
            repo_root=REPO_ROOT,
            generated_at_utc=datetime.now(UTC).isoformat(),
        )
    except OutcomePredictorError as error:
        print(str(error), file=sys.stderr)
        return 1

    write_fit_artifact(fit, args.output)
    loaded = load_outcome_predictor_fit(args.output)
    print(f"fit artifact written: {args.output}")
    print(f"fit digest: {loaded.digest}")
    print(f"sources accepted: {len(fit.sources)}")
    print("self-test:")
    for check in fit.self_test.checks:
        state = "ok" if check.passed else "FAILED"
        print(
            f"  {check.name}: computed {check.computed:.4f} vs published "
            f"{check.published:g} (±{check.tolerance:g}) — {state}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

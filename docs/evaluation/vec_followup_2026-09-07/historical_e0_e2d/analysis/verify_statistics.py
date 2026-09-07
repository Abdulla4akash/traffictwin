#!/usr/bin/env python3
"""Independently recompute the public E1, E2b, E2c and E2d statistics."""

from __future__ import annotations

import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from scipy.stats import t  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
ABS_TOL = 1e-11


@dataclass(frozen=True)
class PairedSummary:
    n: int
    mean: float
    sample_sd: float
    standard_error: float
    ci_lower: float
    ci_upper: float
    median: float
    minimum: float
    maximum: float
    negative: int
    zero: int
    positive: int


def read_column(path: Path, column: str) -> list[float]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [float(row[column]) for row in csv.DictReader(handle)]


def summarize(values: list[float]) -> PairedSummary:
    if len(values) < 2:
        raise ValueError("At least two paired differences are required")
    mean = statistics.fmean(values)
    sample_sd = statistics.stdev(values)
    standard_error = sample_sd / math.sqrt(len(values))
    critical = float(t.ppf(0.975, df=len(values) - 1))
    margin = critical * standard_error
    return PairedSummary(
        n=len(values),
        mean=mean,
        sample_sd=sample_sd,
        standard_error=standard_error,
        ci_lower=mean - margin,
        ci_upper=mean + margin,
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
        negative=sum(value < 0 for value in values),
        zero=sum(value == 0 for value in values),
        positive=sum(value > 0 for value in values),
    )


def assert_close(actual: float, expected: float, label: str) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=ABS_TOL):
        raise AssertionError(f"{label}: expected {expected:.15f}, got {actual:.15f}")


def verify_summary(
    label: str,
    summary: PairedSummary,
    *,
    mean: float,
    sample_sd: float,
    standard_error: float,
    ci_lower: float,
    ci_upper: float,
) -> None:
    assert_close(summary.mean, mean, f"{label} mean")
    assert_close(summary.sample_sd, sample_sd, f"{label} sample SD")
    assert_close(summary.standard_error, standard_error, f"{label} SE")
    assert_close(summary.ci_lower, ci_lower, f"{label} CI lower")
    assert_close(summary.ci_upper, ci_upper, f"{label} CI upper")


def verify_e1() -> PairedSummary:
    values = read_column(
        ROOT / "experiments/E1/data/e1_primary_paired_differences.csv",
        "cap_40x_minus_0p75_offered_deadline_attainment",
    )
    summary = summarize(values)
    verify_summary(
        "E1",
        summary,
        mean=-0.00010943517835488858,
        sample_sd=0.0001103577758810792,
        standard_error=0.000049353497743155963,
        ci_lower=-0.00024646245558826457,
        ci_upper=0.00002759209887848739,
    )
    if not summary.ci_lower <= 0 <= summary.ci_upper:
        raise AssertionError("E1 interval must include zero")
    return summary


def read_factorial() -> dict[str, float]:
    path = ROOT / "experiments/E2b/data/e2b_factorial.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["arm"]: float(row["offered_deadline_attainment"]) for row in csv.DictReader(handle)}


def verify_e2b() -> dict[str, float]:
    cells = read_factorial()
    contrasts = {
        "placement_without_gate": cells["jsq"] - cells["off"],
        "placement_with_gate": cells["dla"] - cells["ingress_dla"],
        "admission_under_strongest_link": cells["ingress_dla"] - cells["off"],
        "admission_under_least_busy": cells["dla"] - cells["jsq"],
        "interaction": cells["dla"] - cells["jsq"] - cells["ingress_dla"] + cells["off"],
    }
    expected = {
        "placement_without_gate": -0.007937453551,
        "placement_with_gate": -0.020833291910,
        "admission_under_strongest_link": 0.032153982561,
        "admission_under_least_busy": 0.019258144203,
        "interaction": -0.012895838358,
    }
    for key, value in expected.items():
        assert_close(contrasts[key], value, f"E2b {key}")
    return contrasts


def verify_e2c() -> PairedSummary:
    values = read_column(
        ROOT / "experiments/E2c/data/e2c_paired_results.csv",
        "dla_minus_ingress_dla",
    )
    summary = summarize(values)
    verify_summary(
        "E2c",
        summary,
        mean=-0.0212222609353733,
        sample_sd=0.0006994576047060331,
        standard_error=0.00034972880235301654,
        ci_lower=-0.022335254070273147,
        ci_upper=-0.02010926780047345,
    )
    if summary.negative != 4 or summary.ci_upper >= 0:
        raise AssertionError("E2c must contain four negative differences and an all-negative CI")
    return summary


def verify_e2d(column: str, expected: tuple[float, float, float, float, float]) -> PairedSummary:
    values = read_column(ROOT / "experiments/E2d/data/e2d_paired_results.csv", column)
    summary = summarize(values)
    mean, sample_sd, standard_error, ci_lower, ci_upper = expected
    verify_summary(
        f"E2d {column}",
        summary,
        mean=mean,
        sample_sd=sample_sd,
        standard_error=standard_error,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
    )
    if summary.positive != 4 or summary.ci_lower <= 0:
        raise AssertionError(f"{column} must contain four positive differences and an all-positive CI")
    return summary


def main() -> None:
    e1 = verify_e1()
    e2b = verify_e2b()
    e2c = verify_e2c()
    e2d_primary = verify_e2d(
        "per_task_minus_ingress",
        (
            0.005271433655898189,
            0.0005337338948814406,
            0.0002668669474407203,
            0.004422143925012979,
            0.0061207233867833985,
        ),
    )
    e2d_secondary = verify_e2d(
        "per_task_minus_common_target",
        (
            0.02649369459127149,
            0.00017780701588052195,
            0.00008890350794026098,
            0.026210763950900193,
            0.026776625231642783,
        ),
    )
    if not e2c.mean < 0 < e2d_primary.mean:
        raise AssertionError("The E2c-to-E2d direction reversal was not reproduced")

    print("PASS: 5 statistical checks")
    print(f"  E1 mean={e1.mean:.12f}, CI=[{e1.ci_lower:.12f}, {e1.ci_upper:.12f}]")
    print(f"  E2b interaction={e2b['interaction']:.12f}")
    print(f"  E2c mean={e2c.mean:.12f}, CI=[{e2c.ci_lower:.12f}, {e2c.ci_upper:.12f}]")
    print(
        "  E2d primary "
        f"mean={e2d_primary.mean:.12f}, "
        f"CI=[{e2d_primary.ci_lower:.12f}, {e2d_primary.ci_upper:.12f}]"
    )
    print(
        "  E2d secondary "
        f"mean={e2d_secondary.mean:.12f}, "
        f"CI=[{e2d_secondary.ci_lower:.12f}, {e2d_secondary.ci_upper:.12f}]"
    )


if __name__ == "__main__":
    main()

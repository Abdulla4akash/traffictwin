"""Deterministic statistics helpers."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def arithmetic_mean(values: Sequence[float]) -> float | None:
    """Return arithmetic mean, or None for n=0."""

    if not values:
        return None
    return statistics.fmean(values)


def sample_standard_deviation(values: Sequence[float]) -> float | None:
    """Return sample standard deviation, or None for n<2."""

    if len(values) < 2:
        return None
    return statistics.stdev(values)


def percentile_linear(values: Sequence[float], percentile: float) -> float | None:
    """Return a deterministic linear-interpolated percentile.

    The rank is `(n - 1) * percentile`, with interpolation between adjacent
    sorted values. `percentile` is expressed as a fraction in [0, 1].
    """

    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def paired_differences(
    baseline: dict[int, float],
    variation: dict[int, float],
) -> tuple[list[float], list[int], list[int]]:
    """Return paired variation-baseline differences and unmatched random seeds."""

    common = sorted(set(baseline) & set(variation))
    differences = [variation[seed] - baseline[seed] for seed in common]
    unmatched_baseline = sorted(set(baseline) - set(variation))
    unmatched_variation = sorted(set(variation) - set(baseline))
    return differences, unmatched_baseline, unmatched_variation

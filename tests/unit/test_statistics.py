from __future__ import annotations

import pytest

from traffictwin.metrics.statistics import percentile_linear, stable_float


def test_stable_float_removes_non_semantic_platform_tails() -> None:
    assert stable_float(1.9599639845400534) == stable_float(1.9599639845400536)
    assert stable_float(0.7535784406023495) == stable_float(0.7535784406023496)
    assert stable_float(0.7649999999999999) == 0.765


def test_stable_float_rejects_non_finite_values() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            stable_float(value)


def test_linear_percentile_has_explicit_empty_and_singleton_semantics() -> None:
    assert percentile_linear([], 0.99) is None
    assert percentile_linear([42.0], 0.99) == 42.0


def test_linear_p99_uses_rank_n_minus_one_interpolation() -> None:
    assert percentile_linear([180.0, 80.0, 120.0], 0.99) == 178.8


@pytest.mark.parametrize("percentile", [-0.01, 1.01])
def test_linear_percentile_rejects_out_of_range_fraction(percentile: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 1 inclusive"):
        percentile_linear([1.0, 2.0], percentile)

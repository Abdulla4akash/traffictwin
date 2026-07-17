from __future__ import annotations

from tests.helpers import fixed_clock, metric_collection
from traffictwin.metrics.aggregation import (
    aggregate_experiment,
    aggregate_metric_values,
    paired_metric_difference,
)


def test_aggregate_metric_values_handles_empty_and_singleton_samples() -> None:
    empty = aggregate_metric_values([], "task.completion.rate")
    singleton = aggregate_metric_values(
        [metric_collection("baseline_valid")], "task.completion.rate"
    )

    assert empty.status == "unavailable"
    assert empty.n == 0
    assert singleton.status == "available"
    assert singleton.n == 1
    assert singleton.mean == 1.0
    assert singleton.sample_sd is None


def test_aggregate_metric_values_reports_sample_sd_for_multiple_runs() -> None:
    summary = aggregate_metric_values(
        [metric_collection("baseline_valid"), metric_collection("variation_valid")],
        "task.completion.rate",
    )

    assert summary.n == 2
    assert summary.mean == 0.875
    assert summary.minimum == 0.75
    assert summary.maximum == 1.0
    assert summary.p50 == 0.875
    assert summary.sample_sd == 0.1767766952966369


def test_experiment_aggregation_groups_by_seed_and_algorithm() -> None:
    report = aggregate_experiment(
        [metric_collection("baseline_valid"), metric_collection("variation_valid")],
        clock=fixed_clock,
    )

    assert report.experiment_id == "exp-gridlock-001"
    assert report.condition_count == 2
    assert [condition.run_count for condition in report.conditions] == [1, 1]


def test_paired_difference_uses_common_random_seeds() -> None:
    summary = paired_metric_difference(
        [metric_collection("baseline_valid"), metric_collection("variation_valid")],
        "s1-gridlock-baseline",
        "s1-gridlock-variation",
        "task.completion.rate",
    )

    assert summary.paired_count == 1
    assert summary.mean_paired_difference == -0.25
    assert summary.sample_sd_paired_difference is None
    assert summary.unmatched_baseline_random_seeds == []
    assert summary.unmatched_variation_random_seeds == []

from __future__ import annotations

from tests.helpers import bundle_result, fixed_clock, metric_collection
from traffictwin.metrics.comparison import (
    ComparisonRequest,
    ComparisonStatus,
    compare_metric_collections,
)


def test_scalar_comparison_deltas_are_neutral_and_deterministic() -> None:
    baseline_bundle = bundle_result("baseline_valid")
    variation_bundle = bundle_result("variation_valid")
    report = compare_metric_collections(
        metric_collection("baseline_valid"),
        metric_collection("variation_valid"),
        baseline_seed=baseline_bundle.seed,
        variation_seed=variation_bundle.seed,
        clock=fixed_clock,
    )
    by_key = {metric.metric_key: metric for metric in report.comparable_metrics}

    completion = by_key["task.completion.rate"]
    assert completion.absolute_delta == -0.25
    assert completion.relative_delta == -0.25
    assert completion.direction.value == "decreased"
    assert completion.status is ComparisonStatus.AVAILABLE

    trip_duration = by_key["trip.duration.mean_s"]
    assert trip_duration.absolute_delta == 330.0
    assert trip_duration.relative_delta == 0.5238095238095238
    assert trip_duration.direction.value == "increased"


def test_relative_delta_zero_policy_never_emits_infinity() -> None:
    report = compare_metric_collections(
        metric_collection("baseline_valid"),
        metric_collection("variation_valid"),
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            requested_metric_keys=["task.incomplete.rate"],
        ),
        clock=fixed_clock,
    )
    metric = report.comparable_metrics[0]

    assert metric.absolute_delta == 0.25
    assert metric.relative_delta is None
    assert metric.status is ComparisonStatus.PARTIAL
    assert metric.reason_codes[0].value == "BASELINE_ZERO"


def test_random_seed_mismatch_marks_comparison_unavailable() -> None:
    variation = metric_collection("variation_valid")
    changed_results = [
        metric.model_copy(update={"random_seed": 99}) for metric in variation.results
    ]
    variation = variation.model_copy(update={"results": changed_results})
    report = compare_metric_collections(
        metric_collection("baseline_valid"),
        variation,
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            requested_metric_keys=["task.completion.rate"],
        ),
        clock=fixed_clock,
    )

    assert report.unavailable_comparisons[0].reason_codes[0].value == "RANDOM_SEED_MISMATCH"


def test_seed_diff_excludes_identity_fields() -> None:
    baseline_bundle = bundle_result("baseline_valid")
    variation_bundle = bundle_result("variation_valid")
    report = compare_metric_collections(
        metric_collection("baseline_valid"),
        metric_collection("variation_valid"),
        baseline_seed=baseline_bundle.seed,
        variation_seed=variation_bundle.seed,
        clock=fixed_clock,
    )

    paths = {change["path"] for change in report.changed_seed_parameters}
    assert "demand.multiplier" in paths
    assert "workload.birth_rate_multiplier" in paths
    assert "seed_id" not in paths
    assert "name" not in paths

from __future__ import annotations

from dataclasses import replace

from tests.helpers import bundle_result, fixed_clock, metric_collection
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricStatus, UnavailableReason


def test_task_metrics_from_baseline_fixture() -> None:
    metrics = metric_collection("baseline_valid").by_key()

    assert metrics["task.generated.count"].value == 3
    assert metrics["task.completed.count"].value == 3
    assert metrics["task.completion.rate"].value == 1.0
    assert metrics["task.deadline_miss.completed_observed_rate"].value == 0.0
    assert metrics["task.latency.mean_ms"].value == 126.66666666666667
    assert metrics["task.latency.p50_ms"].value == 120.0
    assert metrics["task.latency.p95_ms"].value == 174.0
    assert metrics["task.latency.p99_ms"].value == 178.8
    assert metrics["task.latency.p99_ms"].metadata == {
        "percentile_fraction": 0.99,
        "percentile_method": "linear",
        "percentile_method_version": "linear-rank-n-minus-1-v1",
        "sample_count": 3,
        "minimum_sample_size": 1,
    }
    assert metrics["task.offload.rate"].value == 2 / 3


def test_decision_shares_sum_across_recognised_decisions() -> None:
    metrics = metric_collection("variation_valid").by_key()

    share_sum = (
        metrics["task.decision_share.local"].value
        + metrics["task.decision_share.v2i"].value
        + metrics["task.decision_share.v2v"].value
    )
    assert share_sum == 1.0
    assert metrics["task.decision.counts"].value == {
        "local": 1,
        "v2i": 2,
        "v2v": 1,
        "unknown": 0,
    }


def test_task_vehicle_tier_metric_is_unavailable_without_vehicle_evidence() -> None:
    metric = metric_collection("baseline_valid").by_key()["task.completion.rate_by_vehicle_tier"]

    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.reason_codes[0].value == "VEHICLE_TIER_UNAVAILABLE"


def test_single_latency_percentiles_equal_the_observation_with_warning() -> None:
    bundle = bundle_result("baseline_valid")
    single_task_tables = bundle.canonical.model_copy(update={"tasks": bundle.canonical.tasks[:1]})
    single_task_bundle = replace(bundle, canonical=single_task_tables)

    metrics = compute_metrics_for_bundle(single_task_bundle, clock=fixed_clock).by_key()

    for key in ("task.latency.p50_ms", "task.latency.p95_ms", "task.latency.p99_ms"):
        assert metrics[key].status is MetricStatus.AVAILABLE
        assert metrics[key].value == 80.0
        assert metrics[key].warnings == [
            "Single-observation percentile equals the sole valid latency observation."
        ]


def test_configured_minimum_sample_size_makes_percentiles_explicitly_unavailable() -> None:
    metrics = compute_metrics_for_bundle(
        bundle_result("baseline_valid"),
        MetricEngineConfig(minimum_sample_size=4),
        clock=fixed_clock,
    ).by_key()

    assert metrics["task.latency.mean_ms"].status is MetricStatus.AVAILABLE
    for key in ("task.latency.p50_ms", "task.latency.p95_ms", "task.latency.p99_ms"):
        assert metrics[key].status is MetricStatus.UNAVAILABLE
        assert metrics[key].reason_codes == [UnavailableReason.INSUFFICIENT_SAMPLE_SIZE]
        assert metrics[key].metadata["sample_count"] == 3
        assert metrics[key].metadata["minimum_sample_size"] == 4

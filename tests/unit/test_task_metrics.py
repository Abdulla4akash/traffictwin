from __future__ import annotations

from tests.helpers import metric_collection
from traffictwin.metrics.results import MetricStatus


def test_task_metrics_from_baseline_fixture() -> None:
    metrics = metric_collection("baseline_valid").by_key()

    assert metrics["task.generated.count"].value == 3
    assert metrics["task.completed.count"].value == 3
    assert metrics["task.completion.rate"].value == 1.0
    assert metrics["task.deadline_miss.completed_observed_rate"].value == 0.0
    assert metrics["task.latency.mean_ms"].value == 126.66666666666667
    assert metrics["task.latency.p50_ms"].value == 120.0
    assert metrics["task.latency.p95_ms"].value == 174.0
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

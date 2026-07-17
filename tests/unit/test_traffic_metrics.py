from __future__ import annotations

from tests.helpers import metric_collection
from traffictwin.metrics.results import MetricStatus


def test_traffic_metrics_from_baseline_fixture() -> None:
    metrics = metric_collection("baseline_valid").by_key()

    assert metrics["traffic.observation.count"].value == 2
    assert metrics["traffic.count.total"].value == 40
    assert metrics["traffic.count.mean"].value == 20.0
    assert metrics["traffic.speed.mean_mps"].value == 11.75
    assert metrics["traffic.speed.p50_mps"].value == 11.75
    assert metrics["traffic.speed.p95_mps"].value == 11.975
    assert metrics["traffic.speed.min_mps"].value == 11.5
    assert metrics["traffic.time_coverage"].value == {
        "first_timestamp_s": 0.0,
        "last_timestamp_s": 300.0,
        "duration_s": 300.0,
    }
    assert metrics["traffic.sensor.count"].value == 1


def test_traffic_metrics_unavailable_for_partial_bundle() -> None:
    metric = metric_collection("partial_valid").by_key()["traffic.speed.mean_mps"]

    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.reason_codes[0].value == "REQUIRED_TABLE_UNAVAILABLE"

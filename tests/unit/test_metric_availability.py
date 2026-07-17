from __future__ import annotations

from tests.helpers import metric_collection
from traffictwin.metrics.results import MetricStatus


def test_partial_bundle_marks_missing_domains_unavailable() -> None:
    metrics = metric_collection("partial_valid").by_key()

    assert metrics["task.completion.rate"].status is MetricStatus.AVAILABLE
    assert metrics["infra.queue_length.mean"].status is MetricStatus.UNAVAILABLE
    assert metrics["trip.duration.mean_s"].status is MetricStatus.UNAVAILABLE
    assert metrics["infra.queue_length.mean"].missing_evidence == ["infrastructure"]


def test_rejected_bundle_marks_metrics_invalid() -> None:
    collection = metric_collection("invalid_rows")

    assert all(metric.status is MetricStatus.INVALID for metric in collection.results)
    assert all(
        metric.reason_codes[0].value == "INVALID_SOURCE_DATA" for metric in collection.results
    )


def test_unavailable_metrics_do_not_carry_numeric_values() -> None:
    collection = metric_collection("partial_valid")

    for metric in collection.results:
        if metric.status is MetricStatus.UNAVAILABLE:
            assert metric.value is None

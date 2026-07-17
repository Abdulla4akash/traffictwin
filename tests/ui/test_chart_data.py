from __future__ import annotations

from tests.helpers import bundle_result, metric_collection

from traffictwin.ui.charts import (
    infrastructure_series,
    metric_status_counts,
    task_event_series,
    traffic_series,
    trip_duration_rows,
)


def test_chart_data_from_baseline_bundle() -> None:
    tables = bundle_result("baseline_valid").canonical

    assert len(traffic_series(tables)) == 2
    assert len(infrastructure_series(tables)) == 4
    assert task_event_series(tables)[0] == {
        "timestamp_s": 0.0,
        "arrivals": 1,
        "completions": 0,
    }
    assert [row["duration_s"] for row in trip_duration_rows(tables)] == [600.0, 660.0]


def test_metric_status_counts_for_partial_bundle() -> None:
    counts = metric_status_counts(metric_collection("partial_valid"))

    assert counts["available"] > 0
    assert counts["unavailable"] > 0

from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import metric_collection, metric_projection

EXPECTED = Path("tests/golden/expected")
BASELINE_KEYS = [
    "task.generated.count",
    "task.completed.count",
    "task.completion.rate",
    "task.latency.p95_ms",
    "task.latency.p99_ms",
    "infra.queue_length.mean",
    "infra.utilisation.mean",
    "traffic.speed.mean_mps",
    "trip.duration.mean_s",
]
PARTIAL_KEYS = [
    "task.generated.count",
    "task.completion.rate",
    "infra.queue_length.mean",
    "traffic.speed.mean_mps",
    "trip.duration.mean_s",
]


def test_baseline_metric_golden_projection() -> None:
    expected = json.loads((EXPECTED / "baseline_metrics.json").read_text(encoding="utf-8"))

    assert metric_projection(metric_collection("baseline_valid"), BASELINE_KEYS) == expected


def test_partial_metric_golden_projection() -> None:
    expected = json.loads((EXPECTED / "partial_metrics.json").read_text(encoding="utf-8"))

    assert metric_projection(metric_collection("partial_valid"), PARTIAL_KEYS) == expected

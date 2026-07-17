from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import bundle_result, fixed_clock, metric_collection

from traffictwin.metrics.comparison import ComparisonReport, compare_metric_collections

EXPECTED = Path("tests/golden/expected")
COMPARISON_KEYS = [
    "task.completion.rate",
    "infra.queue_length.mean",
    "traffic.speed.mean_mps",
    "trip.duration.mean_s",
]


def test_baseline_vs_variation_comparison_golden_projection() -> None:
    baseline = bundle_result("baseline_valid")
    variation = bundle_result("variation_valid")
    report = compare_metric_collections(
        metric_collection("baseline_valid"),
        metric_collection("variation_valid"),
        baseline_seed=baseline.seed,
        variation_seed=variation.seed,
        clock=fixed_clock,
    )
    expected = json.loads((EXPECTED / "baseline_vs_variation.json").read_text(encoding="utf-8"))

    assert _comparison_projection(report) == expected


def _comparison_projection(report: ComparisonReport) -> dict[str, object]:
    by_key = {metric.metric_key: metric for metric in report.comparable_metrics}
    return {
        "baseline_run_id": report.baseline_context["run_id"],
        "variation_run_id": report.variation_context["run_id"],
        "metrics": {
            key: {
                "baseline": by_key[key].baseline,
                "variation": by_key[key].variation,
                "absolute_delta": by_key[key].absolute_delta,
                "relative_delta": by_key[key].relative_delta,
                "direction": by_key[key].direction.value,
                "status": by_key[key].status.value,
            }
            for key in COMPARISON_KEYS
        },
        "changed_seed_paths": [change["path"] for change in report.changed_seed_parameters],
    }

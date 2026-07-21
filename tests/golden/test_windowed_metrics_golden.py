from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from tests.format_helpers import write_equivalent_bundle
from tests.helpers import FIXTURES, fixed_clock

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.windowed import (
    WindowedMetricConfig,
    WindowedMetricSeries,
    compute_windowed_metrics_for_bundle,
)

EXPECTED = Path("tests/golden/expected/windowed_baseline.json")
SELECTED_METRICS = [
    "task.generated.count",
    "task.completion.rate",
    "infra.utilisation.mean",
    "traffic.speed.mean_mps",
    "trip.duration.mean_s",
]


def _projection(series: WindowedMetricSeries) -> dict[str, Any]:
    windows: list[dict[str, Any]] = []
    for item in series.slices:
        by_key = item.metrics.by_key() if item.metrics is not None else {}
        windows.append(
            {
                "ordinal": item.window.ordinal,
                "bounds_s": [item.window.start_s, item.window.end_s],
                "effective_bounds_s": [
                    item.window.effective_start_s,
                    item.window.effective_end_s,
                ],
                "coverage": item.window.requested_interval_coverage_fraction,
                "partial": item.window.is_partial,
                "disposition": item.disposition.value,
                "source_record_counts": item.source_record_counts,
                "metrics": {
                    key: {
                        "status": by_key[key].status.value,
                        "value": by_key[key].value,
                        "reason_codes": [reason.value for reason in by_key[key].reason_codes],
                    }
                    for key in SELECTED_METRICS
                },
            }
        )
    return {
        "schema_version": series.schema_version,
        "anchor_policy_version": series.anchor_policy_version,
        "run_id": series.run_id,
        "metric_version": series.metric_version,
        "status": series.status.value,
        "range_source": series.range_source.value,
        "analysis_range_s": [series.analysis_start_s, series.analysis_end_s],
        "source_time_range_s": [series.source_time_min_s, series.source_time_max_s],
        "boundary": series.boundary,
        "coverage_semantics": series.coverage_semantics,
        "empty_window_semantics": series.empty_window_semantics,
        "anchor_fields": series.anchor_fields,
        "applicable_metric_count": len(series.applicable_metric_keys),
        "included_window_count": series.included_window_count,
        "excluded_partial_window_count": series.excluded_partial_window_count,
        "included_empty_window_count": series.included_empty_window_count,
        "windows": windows,
    }


def test_windowed_baseline_matches_golden_contract() -> None:
    series = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "baseline_valid"),
        WindowedMetricConfig(width_s=60),
        clock=fixed_clock,
    )

    assert _projection(series) == json.loads(EXPECTED.read_text(encoding="utf-8"))


@pytest.mark.parametrize("representation", ["gzip", "parquet"])
def test_windowed_metrics_are_equivalent_across_declared_formats(
    tmp_path: Path,
    representation: str,
) -> None:
    equivalent = write_equivalent_bundle(
        FIXTURES / "baseline_valid",
        tmp_path / representation,
        representation,
    )
    expected = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "baseline_valid"),
        WindowedMetricConfig(width_s=60),
        clock=fixed_clock,
    )
    actual = compute_windowed_metrics_for_bundle(
        validate_bundle(equivalent),
        WindowedMetricConfig(width_s=60),
        clock=fixed_clock,
    )

    assert _projection(actual) == _projection(expected)

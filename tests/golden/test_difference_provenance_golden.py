from __future__ import annotations

import json
from pathlib import Path

from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.provenance.differences import build_difference_contribution_report


def test_difference_provenance_arithmetic_projection_matches_golden() -> None:
    baseline = validate_bundle("tests/fixtures/bundles/baseline_valid")
    variation = validate_bundle("tests/fixtures/bundles/variation_valid")
    report = build_difference_contribution_report(
        baseline,
        compute_metrics_for_bundle(baseline),
        variation,
        compute_metrics_for_bundle(variation),
        "task.latency.mean_ms",
    )
    actual = {
        "schema_version": report.schema_version,
        "capability_id": report.capability_id,
        "status": report.status.value,
        "metric_key": report.metric_key,
        "unit": report.unit,
        "comparison_basis": report.comparison_basis,
        "baseline_value": report.baseline_value,
        "variation_value": report.variation_value,
        "absolute_delta": report.absolute_delta,
        "decomposition_method": report.decomposition_method,
        "baseline": report.baseline.model_dump(mode="json"),
        "variation": report.variation.model_dump(mode="json"),
        "rows": [
            {
                "side": row.side.value,
                "record_id": row.record_id,
                "included": row.included,
                "run_metric_contribution": row.run_metric_contribution,
                "signed_difference_contribution": row.signed_difference_contribution,
            }
            for row in report.rows
        ],
        "arithmetic_contribution_sum": report.arithmetic_contribution_sum,
        "reconciles_to_absolute_delta": report.reconciles_to_absolute_delta,
        "non_causality_statement": report.non_causality_statement,
    }
    expected = json.loads(
        Path("tests/golden/expected/difference_provenance_latency_mean.json").read_text(
            encoding="utf-8"
        )
    )

    assert actual == expected

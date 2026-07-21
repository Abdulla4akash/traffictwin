from __future__ import annotations

from pathlib import Path

from traffictwin.diagnostics.temporal import TemporalDiagnosticAnalysis
from traffictwin.metrics.windowed import WindowedMetricSeries
from traffictwin.ui.services import (
    ServiceError,
    compute_windowed_metrics_for_ui,
    evaluate_temporal_diagnostics_for_ui,
    validate_bundle_for_ui,
)


def test_windowed_metric_ui_service_returns_typed_series() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))

    result = compute_windowed_metrics_for_ui(analysis.validation, width_s=60)

    assert isinstance(result, WindowedMetricSeries)
    assert result.included_window_count == 6
    assert result.slices[0].metrics is not None


def test_windowed_metric_ui_service_returns_typed_input_error() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))

    result = compute_windowed_metrics_for_ui(
        analysis.validation,
        width_s=60,
        analysis_start_s=0,
    )

    assert isinstance(result, ServiceError)
    assert "supplied together" in (result.detail or "")


def test_temporal_diagnostic_ui_service_returns_typed_r6_analysis() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    series = compute_windowed_metrics_for_ui(
        analysis.validation,
        width_s=1,
        analysis_start_s=0,
        analysis_end_s=10,
    )
    assert isinstance(series, WindowedMetricSeries)

    result = evaluate_temporal_diagnostics_for_ui(
        analysis.validation,
        series,
        metric_key="task.completion.rate",
    )

    assert isinstance(result, TemporalDiagnosticAnalysis)
    assert result.temporal_evidence.metric_key == "task.completion.rate"
    assert result.r6_result.rule_id == "R6"


def test_temporal_diagnostic_ui_service_rejects_inconsistent_rule_minima() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    series = compute_windowed_metrics_for_ui(analysis.validation, width_s=60)
    assert isinstance(series, WindowedMetricSeries)

    result = evaluate_temporal_diagnostics_for_ui(
        analysis.validation,
        series,
        metric_key="task.completion.rate",
        baseline_window_count=3,
        sustained_window_count=2,
        minimum_evaluable_windows=4,
    )

    assert isinstance(result, ServiceError)
    assert "cover baseline and sustained" in (result.detail or "")

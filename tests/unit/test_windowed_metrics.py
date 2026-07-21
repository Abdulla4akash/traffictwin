from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from tests.helpers import FIXTURES, fixed_clock
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.evidence.availability import EvidenceAvailability
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.catalogue import metric_catalogue, window_metric_catalogue
from traffictwin.metrics.results import MetricStatus, RunMetricContext
from traffictwin.metrics.windowed import (
    PartialWindowPolicy,
    WindowDisposition,
    WindowedMetricConfig,
    WindowLimitExceededError,
    WindowRangeSource,
    WindowSeriesStatus,
    compute_windowed_metrics,
    compute_windowed_metrics_for_bundle,
)
from traffictwin.provenance.builder import build_window_metric_trace
from traffictwin.provenance.contributions import build_window_metric_contribution_report


def test_window_config_requires_complete_ordered_explicit_range() -> None:
    with pytest.raises(ValidationError, match="must be supplied together"):
        WindowedMetricConfig(width_s=10, analysis_start_s=0)
    with pytest.raises(ValidationError, match="must be greater"):
        WindowedMetricConfig(width_s=10, analysis_start_s=5, analysis_end_s=5)
    with pytest.raises(ValidationError):
        WindowedMetricConfig(width_s=float("inf"))


def test_metric_catalogue_declares_exact_window_applicability_and_anchors() -> None:
    applicable = window_metric_catalogue()

    assert len(applicable) == len(metric_catalogue()) - 3
    assert applicable["task.completion.rate"].time_anchor == "tasks.arrival_time_s"
    assert applicable["infra.utilisation.mean"].time_anchor == "infrastructure.timestamp_s"
    assert applicable["traffic.speed.mean_mps"].time_anchor == "traffic.timestamp_s"
    assert applicable["trip.duration.mean_s"].time_anchor == "trips.departure_time_s"
    assert "comparison.absolute_delta" not in applicable


def test_half_open_boundary_assigns_exact_timestamp_to_later_window() -> None:
    result = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "baseline_valid"),
        WindowedMetricConfig(
            width_s=5,
            analysis_start_s=0,
            analysis_end_s=10,
        ),
        clock=fixed_clock,
    )

    counts = [
        item.metrics.by_key()["task.generated.count"].value
        for item in result.slices
        if item.metrics is not None
    ]
    assert counts == [1, 2]
    assert result.slices[0].source_record_counts["tasks"] == 1
    assert result.slices[1].source_record_counts["tasks"] == 2


def test_inferred_aligned_envelope_partitions_every_source_record_once() -> None:
    bundle = validate_bundle(FIXTURES / "baseline_valid")
    result = compute_windowed_metrics_for_bundle(
        bundle,
        WindowedMetricConfig(width_s=60, alignment_origin_s=0),
        clock=fixed_clock,
    )

    totals = dict.fromkeys(bundle.canonical.record_counts(), 0)
    for item in result.slices:
        for table, count in item.source_record_counts.items():
            totals[table] += count

    assert result.range_source is WindowRangeSource.INFERRED_ALIGNED_ENVELOPE
    assert (result.analysis_start_s, result.analysis_end_s) == (0.0, 360.0)
    assert totals == bundle.canonical.record_counts()
    assert result.included_empty_window_count == 4


def test_explicit_partial_windows_are_clipped_and_included_visibly() -> None:
    result = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "baseline_valid"),
        WindowedMetricConfig(
            width_s=5,
            analysis_start_s=2,
            analysis_end_s=8,
            partial_window_policy=PartialWindowPolicy.INCLUDE,
        ),
        clock=fixed_clock,
    )

    first, second = result.slices
    assert first.window.start_s == 0
    assert first.window.effective_start_s == 2
    assert first.window.requested_interval_coverage_fraction == 0.6
    assert first.window.is_partial
    assert first.metrics is not None
    assert first.metrics.by_key()["task.generated.count"].status is MetricStatus.UNAVAILABLE
    assert second.window.effective_end_s == 8
    assert second.source_record_counts["tasks"] == 1
    assert second.metrics is not None
    assert second.metrics.by_key()["task.generated.count"].value == 1


def test_explicit_partial_windows_can_be_excluded_without_hiding_them() -> None:
    result = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "baseline_valid"),
        WindowedMetricConfig(
            width_s=5,
            analysis_start_s=2,
            analysis_end_s=8,
            partial_window_policy=PartialWindowPolicy.EXCLUDE,
        ),
        clock=fixed_clock,
    )

    assert result.included_window_count == 0
    assert result.excluded_partial_window_count == 2
    assert all(item.metrics is None for item in result.slices)
    assert all(item.disposition is WindowDisposition.EXCLUDED_PARTIAL for item in result.slices)


def test_window_request_is_bounded_before_metric_computation() -> None:
    with pytest.raises(WindowLimitExceededError, match="resolves to 10 windows"):
        compute_windowed_metrics_for_bundle(
            validate_bundle(FIXTURES / "baseline_valid"),
            WindowedMetricConfig(
                width_s=1,
                analysis_start_s=0,
                analysis_end_s=10,
                max_windows=5,
            ),
            clock=fixed_clock,
        )


def test_no_timestamp_range_is_explicitly_unavailable() -> None:
    context = RunMetricContext(
        run_id="run-empty",
        experiment_id=None,
        seed_id="seed-empty",
        algorithm="none",
        random_seed=0,
        synthetic=True,
    )
    result = compute_windowed_metrics(
        CanonicalTables(),
        context,
        EvidenceAvailability(),
        WindowedMetricConfig(width_s=10),
        clock=lambda: datetime(2026, 7, 20, tzinfo=UTC),
    )

    assert result.status is WindowSeriesStatus.UNAVAILABLE
    assert result.range_source is WindowRangeSource.UNAVAILABLE
    assert result.slices == []
    assert "No canonical timestamp" in result.warnings[-1]


def test_rejected_bundle_produces_only_invalid_window_metrics() -> None:
    result = compute_windowed_metrics_for_bundle(
        validate_bundle(FIXTURES / "invalid_rows"),
        WindowedMetricConfig(width_s=60, analysis_start_s=0, analysis_end_s=60),
        clock=fixed_clock,
    )

    assert result.status is WindowSeriesStatus.INVALID
    metrics = result.slices[0].metrics
    assert metrics is not None
    assert {metric.status for metric in metrics.results} == {MetricStatus.INVALID}


def test_window_metric_provenance_and_ledger_include_only_in_window_rows() -> None:
    bundle = validate_bundle(FIXTURES / "baseline_valid")
    series = compute_windowed_metrics_for_bundle(
        bundle,
        WindowedMetricConfig(width_s=5, analysis_start_s=0, analysis_end_s=10),
        clock=fixed_clock,
    )

    trace = build_window_metric_trace("task.generated.count", bundle, series, 0, clock=fixed_clock)
    source_rows = {
        int(node.attributes["row"]) for node in trace.nodes if node.node_type.value == "source_row"
    }
    ledger = build_window_metric_contribution_report(bundle, series, 0, "task.generated.count")

    assert source_rows == {2}
    assert ledger.window.boundary == "[start,end)"
    assert ledger.contribution_report.candidate_row_count == 1
    assert ledger.contribution_report.rows[0].record_id == "t1"


def test_window_computation_is_deterministic_for_fixed_inputs_and_clock() -> None:
    bundle = validate_bundle(FIXTURES / "baseline_valid")
    config = WindowedMetricConfig(width_s=17, alignment_origin_s=3)

    first = compute_windowed_metrics_for_bundle(bundle, config, clock=fixed_clock)
    second = compute_windowed_metrics_for_bundle(bundle, config, clock=fixed_clock)

    assert first == second


@pytest.mark.parametrize(
    ("width_s", "origin_s"),
    [(1.0, 0.0), (2.5, 0.0), (2.5, 0.5), (7.0, -3.0), (17.0, 3.0)],
)
def test_aligned_window_partition_invariant_holds_across_widths_and_origins(
    width_s: float,
    origin_s: float,
) -> None:
    bundle = validate_bundle(FIXTURES / "baseline_valid")
    series = compute_windowed_metrics_for_bundle(
        bundle,
        WindowedMetricConfig(width_s=width_s, alignment_origin_s=origin_s),
        clock=fixed_clock,
    )

    partitioned = dict.fromkeys(bundle.canonical.record_counts(), 0)
    for item in series.slices:
        for table, count in item.source_record_counts.items():
            partitioned[table] += count

    assert partitioned == bundle.canonical.record_counts()
    assert all(
        left.window.end_s == right.window.start_s
        for left, right in zip(series.slices, series.slices[1:], strict=False)
    )

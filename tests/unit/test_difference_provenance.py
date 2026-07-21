from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TypeAlias

import pytest

from traffictwin.ingestion.bundle import BundleValidationResult, validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection
from traffictwin.provenance.differences import (
    ARITHMETIC_METRIC_METHODS,
    NON_CAUSALITY_STATEMENT,
    DifferenceContributionStatus,
    build_difference_contribution_report,
    difference_contribution_report_to_csv,
    difference_provenance_contract,
)
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

ComparisonInputs: TypeAlias = tuple[
    BundleValidationResult,
    MetricCollection,
    BundleValidationResult,
    MetricCollection,
]


@pytest.fixture
def comparison_inputs() -> ComparisonInputs:
    baseline = validate_bundle("tests/fixtures/bundles/baseline_valid")
    variation = validate_bundle("tests/fixtures/bundles/variation_valid")
    return (
        baseline,
        compute_metrics_for_bundle(baseline),
        variation,
        compute_metrics_for_bundle(variation),
    )


def test_arithmetic_difference_rows_reconcile_to_ordinary_delta(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs

    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        variation_metrics,
        "task.latency.mean_ms",
    )

    assert report.status is DifferenceContributionStatus.ARITHMETIC
    assert report.absolute_delta == 140.0
    assert report.arithmetic_contribution_sum == 140.0
    assert report.reconciles_to_absolute_delta is True
    assert report.baseline.included_row_count == 3
    assert report.variation.included_row_count == 3
    assert sum(row.signed_difference_contribution or 0.0 for row in report.rows) == 140.0
    assert {row.side.value for row in report.rows} == {"baseline", "variation"}
    assert report.fingerprint() == report.model_copy(deep=True).fingerprint()


def test_all_comparable_admitted_formulas_reconcile(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs
    exercised: set[str] = set()

    for metric_key in ARITHMETIC_METRIC_METHODS:
        report = build_difference_contribution_report(
            baseline,
            baseline_metrics,
            variation,
            variation_metrics,
            metric_key,
        )
        if report.status is DifferenceContributionStatus.UNAVAILABLE:
            continue
        exercised.add(metric_key)
        assert report.status is DifferenceContributionStatus.ARITHMETIC
        assert report.reconciles_to_absolute_delta is True
        assert report.arithmetic_contribution_sum == pytest.approx(report.absolute_delta)

    assert "task.completion.rate" in exercised
    assert "traffic.count.total" in exercised
    assert "trip.duration.mean_s" in exercised


@pytest.mark.parametrize(
    "metric_key",
    [
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
        "task.energy_delay_product.mean_j_ms",
    ],
)
def test_energy_formulas_reconcile_under_matching_contract(
    tmp_path: Path,
    metric_key: str,
) -> None:
    baseline = validate_bundle(
        write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    )
    variation = validate_bundle(
        write_synthetic_bundle(preset_config("stressed_demand"), tmp_path / "variation")
    )

    report = build_difference_contribution_report(
        baseline,
        compute_metrics_for_bundle(baseline),
        variation,
        compute_metrics_for_bundle(variation),
        metric_key,
    )

    assert report.status is DifferenceContributionStatus.ARITHMETIC
    assert report.reconciles_to_absolute_delta is True
    assert report.arithmetic_contribution_sum == pytest.approx(report.absolute_delta)


def test_percentile_difference_exposes_lineage_without_weights(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs

    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        variation_metrics,
        "task.latency.p95_ms",
    )

    assert report.status is DifferenceContributionStatus.LINEAGE_ONLY
    assert report.absolute_delta == 228.0
    assert report.decomposition_method is None
    assert report.arithmetic_contribution_sum is None
    assert report.reconciles_to_absolute_delta is None
    assert all(row.run_metric_contribution is None for row in report.rows)
    assert all(row.signed_difference_contribution is None for row in report.rows)
    assert report.baseline.included_row_count == 3
    assert report.variation.excluded_row_count == 1


@pytest.mark.parametrize(
    "metric_key",
    ["infra.queue_length.max", "traffic.sensor.count", "trip.duration.max_s"],
)
def test_other_non_decomposable_scalar_metrics_are_lineage_only(
    comparison_inputs: ComparisonInputs,
    metric_key: str,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs

    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        variation_metrics,
        metric_key,
    )

    assert report.status is DifferenceContributionStatus.LINEAGE_ONLY
    assert report.absolute_delta is not None
    assert all(row.signed_difference_contribution is None for row in report.rows)


def test_mapping_metric_is_unavailable_without_implicit_flattening(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs

    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        variation_metrics,
        "task.decision.counts",
    )

    assert report.status is DifferenceContributionStatus.UNAVAILABLE
    assert report.absolute_delta is None
    assert "metric value is not a comparable scalar" in report.compatibility_findings
    assert all(row.signed_difference_contribution is None for row in report.rows)


def test_incompatible_comparison_is_unavailable_not_zero(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs
    altered_results = [
        metric.model_copy(update={"random_seed": 99}) for metric in variation_metrics.results
    ]
    incompatible = variation_metrics.model_copy(update={"results": altered_results})

    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        incompatible,
        "task.completion.rate",
    )

    assert report.status is DifferenceContributionStatus.UNAVAILABLE
    assert report.absolute_delta is None
    assert "RANDOM_SEED_MISMATCH" in report.comparison_reason_codes
    assert report.arithmetic_contribution_sum is None
    assert report.rows


def test_json_and_csv_carry_non_causality_statement(
    comparison_inputs: ComparisonInputs,
) -> None:
    baseline, baseline_metrics, variation, variation_metrics = comparison_inputs
    report = build_difference_contribution_report(
        baseline,
        baseline_metrics,
        variation,
        variation_metrics,
        "task.completion.rate",
    )

    assert NON_CAUSALITY_STATEMENT in report.to_json()
    csv_rows = list(csv.DictReader(StringIO(difference_contribution_report_to_csv(report))))
    expected_rows = report.baseline.candidate_row_count + report.variation.candidate_row_count
    assert len(csv_rows) == expected_rows
    assert {row["non_causality_statement"] for row in csv_rows} == {NON_CAUSALITY_STATEMENT}


def test_contract_publishes_closed_arithmetic_registry() -> None:
    contract = difference_provenance_contract()

    assert contract.capability_id == "PRO-01"
    assert contract.arithmetic_metric_methods == dict(sorted(ARITHMETIC_METRIC_METHODS.items()))
    assert contract.complete_candidate_row_ledgers is True
    assert contract.unavailable_is_not_zero is True
    assert "caused" in contract.non_causality_statement

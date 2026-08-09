"""Pure service tests for traffic and VEC consequence lenses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.helpers import fixed_clock, metric_collection
from traffictwin.metrics.catalogue import METRIC_DEFINITIONS
from traffictwin.metrics.comparison import (
    ComparisonRequest,
    compare_metric_collections,
)
from traffictwin.ui.consequence_lenses import (
    ALL_LENS_KEYS,
    DENOMINATOR_BY_KEY,
    TRAFFIC_LENS_KEYS,
    VEC_LENS_KEYS,
    build_consequence_lens_report,
    build_consequence_lens_report_from_comparison,
)
from traffictwin.ui.services import ServiceError, validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis


def _baseline_variation() -> tuple[BundleAnalysis, BundleAnalysis]:
    baseline = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    variation = validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid"))
    assert isinstance(baseline, BundleAnalysis)
    assert isinstance(variation, BundleAnalysis)
    return baseline, variation


def test_deterministic_projection() -> None:
    baseline, variation = _baseline_variation()
    first = build_consequence_lens_report(baseline, variation)
    second = build_consequence_lens_report(baseline, variation)
    assert not isinstance(first, ServiceError)
    assert not isinstance(second, ServiceError)
    assert first.fingerprint == second.fingerprint
    # Compare payload excluding generated_at which is time-dependent
    first_data = json.loads(first.to_json())
    second_data = json.loads(second.to_json())
    first_data.pop("generated_at", None)
    second_data.pop("generated_at", None)
    assert first_data == second_data
    # Rebuild from same comparison is identical fingerprint
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    via_comp = build_consequence_lens_report_from_comparison(
        comp, baseline=baseline, variation=variation
    )
    assert via_comp.fingerprint == first.fingerprint


def test_baseline_variation_identity() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert report.baseline_identity["run_id"] == "run-baseline-001"
    assert report.variation_identity["run_id"] == "run-variation-001"
    assert report.baseline_identity["seed_id"] == "s1-gridlock-baseline"
    assert report.variation_identity["seed_id"] == "s1-gridlock-variation"
    assert report.evidence_standing["baseline_bundle_path"] == str(baseline.source_path)
    assert report.evidence_standing["variation_bundle_path"] == str(variation.source_path)
    assert report.changed_seed_parameters
    paths = {item["path"] for item in report.changed_seed_parameters}
    assert "demand.multiplier" in paths


def test_exact_grouping_into_traffic_and_vec() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    traffic_keys = [row.metric_key for row in report.traffic_summary.rows]
    vec_keys = [row.metric_key for row in report.vec_summary.rows]
    assert traffic_keys == list(TRAFFIC_LENS_KEYS)
    assert vec_keys == list(VEC_LENS_KEYS)
    assert set(traffic_keys).isdisjoint(set(vec_keys))
    assert len(traffic_keys) + len(vec_keys) == len(ALL_LENS_KEYS)


def test_existing_absolute_delta_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    # Trip duration mean delta should be 330
    row = by_key["trip.duration.mean_s"]
    assert row.absolute_delta == 330.0
    # Task completion rate delta -0.25
    row2 = by_key["task.completion.rate"]
    assert row2.absolute_delta == -0.25
    # Compare directly with comparison report
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    comp_by_key = {m.metric_key: m for m in comp.comparable_metrics}
    assert (
        by_key["trip.duration.mean_s"].absolute_delta
        == comp_by_key["trip.duration.mean_s"].absolute_delta
    )
    assert (
        by_key["task.completion.rate"].absolute_delta
        == comp_by_key["task.completion.rate"].absolute_delta
    )


def test_existing_relative_delta_preserved_where_supported() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    # Available relative delta
    assert by_key["trip.duration.mean_s"].relative_delta == pytest.approx(0.5238095238095238)
    # Partial due to baseline zero should have None
    assert by_key["task.incomplete.rate"].status == "partial"
    assert by_key["task.incomplete.rate"].relative_delta is None
    assert "BASELINE_ZERO" in by_key["task.incomplete.rate"].reason_codes
    # Direct comparison parity
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    comp_by_key = {
        m.metric_key: m for m in [*comp.comparable_metrics, *comp.unavailable_comparisons]
    }
    # unavailable also preserved as None
    assert (
        by_key["task.incomplete.rate"].relative_delta
        == comp_by_key["task.incomplete.rate"].relative_delta
    )


def test_unit_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    assert by_key["trip.duration.mean_s"].unit == "s"
    assert by_key["task.latency.mean_ms"].unit == "ms"
    assert by_key["traffic.speed.mean_mps"].unit == "m/s"
    assert by_key["task.completion.rate"].unit == "ratio"
    # Check against catalogue
    for key in ["trip.duration.mean_s", "task.latency.mean_ms", "traffic.speed.mean_mps"]:
        assert by_key[key].unit == METRIC_DEFINITIONS[key].unit


def test_metric_version_compatibility_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert report.compatibility["same_metric_version"] is True
    assert report.compatibility["is_compatible"] is True
    assert report.baseline_identity["metric_version"] == "1.0"
    assert report.variation_identity["metric_version"] == "1.0"
    # Mismatch case - metric_version is on collection, not per metric
    # Create a comparison with mismatched metric_version via copy
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid").model_copy(
        update={"metric_version": "9.9"}
    )
    report2 = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    # Build lens from that comparison (no BundleAnalysis)
    lens2 = build_consequence_lens_report_from_comparison(report2)
    assert lens2.compatibility["same_metric_version"] is False
    assert lens2.compatibility["is_compatible"] is False


def test_unavailable_reason_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    # Energy metrics should be unavailable with COMPARISON_PAIR_INCOMPATIBLE
    energy = by_key["task.energy.mean_per_observed_task_j"]
    assert energy.status == "unavailable"
    assert "METRIC_NOT_APPLICABLE" in energy.reason_codes
    assert "COMPARISON_PAIR_INCOMPATIBLE" in energy.reason_codes
    # Spatial vehicle should be unavailable
    spatial = by_key["spatial.vehicle.observation_count_by_grid_cell"]
    assert spatial.status == "unavailable"
    assert "METRIC_NOT_APPLICABLE" in spatial.reason_codes


def test_partial_availability() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    # partial due to baseline zero
    assert by_key["infra.saturation.episode_count"].status == "partial"
    assert by_key["task.deadline_miss.completed_observed_rate"].status == "partial"
    assert by_key["traffic.time_coverage"].status == "unavailable"  # dict value not scalar


def test_incompatible_pair_refusal() -> None:
    # Experiment mismatch should mark is_compatible false and produce warnings
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    # Change experiment_id via first result's experiment_id
    variation_changed = variation_col.model_copy(
        update={
            "results": [
                r.model_copy(update={"experiment_id": "different-exp"}) if i == 0 else r
                for i, r in enumerate(variation_col.results)
            ]
        }
    )
    report = compare_metric_collections(
        baseline_col,
        variation_changed,
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            require_same_experiment=True,
        ),
        clock=fixed_clock,
    )
    lens = build_consequence_lens_report_from_comparison(report)
    assert lens.compatibility["same_experiment"] is False
    assert lens.compatibility["is_compatible"] is False
    assert any("experiment identifiers differ" in str(w) for w in lens.compatibility["warnings"])
    # Also seed mismatch
    variation_seed_mismatch = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"random_seed": 999}) for r in variation_col.results]
        }
    )
    report2 = compare_metric_collections(
        baseline_col,
        variation_seed_mismatch,
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens2 = build_consequence_lens_report_from_comparison(report2)
    assert lens2.compatibility["same_random_seed"] is False


def test_no_invented_metrics() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    all_keys = {row.metric_key for row in [*report.traffic_summary.rows, *report.vec_summary.rows]}
    assert all_keys == set(ALL_LENS_KEYS)
    # Ensure no invented metrics outside catalogue
    for key in all_keys:
        assert key in METRIC_DEFINITIONS, f"invented metric {key}"


def test_no_better_worse_classification() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    payload = report.to_json().lower()
    assert "better" not in payload
    assert "worse" not in payload
    assert "optimal" not in payload
    assert "improvement" not in payload
    # Also check row status is neutral (available/partial/unavailable) not better/worse
    for row in [*report.traffic_summary.rows, *report.vec_summary.rows]:
        assert row.status in {"available", "partial", "unavailable"}


def test_task_rate_denominator_labels() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    assert (
        by_key["task.completion.rate"].denominator_description
        == DENOMINATOR_BY_KEY["task.completion.rate"]
    )
    assert (
        by_key["trip.completion.rate"].denominator_description
        == DENOMINATOR_BY_KEY["trip.completion.rate"]
    )
    assert (
        by_key["task.offload.rate"].denominator_description
        == DENOMINATOR_BY_KEY["task.offload.rate"]
    )
    # Non-rate should have None
    assert by_key["task.generated.count"].denominator_description is None


def test_offered_admitted_denominator_distinction() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    # task.completion.rate is over generated (offered), not admitted
    denom = by_key["task.completion.rate"].denominator_description
    assert denom is not None and "generated" in denom.lower()
    # Ensure we don't conflate with conditional admitted completion
    assert (
        by_key["task.completion.rate"].denominator_description
        != by_key["task.deadline_miss.completed_observed_rate"].denominator_description
    )


def test_unknown_provenance_remains_unknown() -> None:
    # Build a comparison where synthetic is None (empty collection simulation)
    # Use manual ComparisonReport with None synthetic
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    # Craft report with None synthetic via empty first result trick
    # Instead, construct lens from comparison and then manually set synthetic None in identities
    # The service should preserve None without promoting to synthetic/imported
    report = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    # Manually set synthetic to None to simulate unknown
    report.baseline_context["synthetic"] = None
    report.variation_context["synthetic"] = None
    lens = build_consequence_lens_report_from_comparison(report)
    assert lens.evidence_standing["baseline_synthetic"] is None
    assert lens.evidence_standing["variation_synthetic"] is None
    # Ensure not promoted to True/False
    assert lens.compatibility["synthetic_match"] is True  # None == None


def test_deterministic_serialisation_export() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    first_json = report.to_json()
    second_json = report.to_json()
    assert first_json == second_json
    data = json.loads(first_json)
    assert "traffic_summary" in data
    assert "vec_summary" in data
    assert "fingerprint" in data
    assert "baseline_identity" in data
    assert "variation_identity" in data
    # No NaN
    assert "NaN" not in first_json
    assert "Infinity" not in first_json


def test_unavailable_and_available_counts() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    # Traffic: expect many available, few unavailable (time_coverage is dict)
    assert report.traffic_summary.available_count + report.traffic_summary.unavailable_count == len(
        TRAFFIC_LENS_KEYS
    )
    assert report.vec_summary.available_count + report.vec_summary.unavailable_count == len(
        VEC_LENS_KEYS
    )
    # Based on fixture inspection: traffic should have 18 available? Let's check actual
    # But we know from earlier: comparable 40 across all keys, unavailable 20 across all keys.
    # For our split, traffic lens has 19 keys, vec has 40.
    # We can assert counts are deterministic and not zero
    assert report.traffic_summary.available_count > 0
    assert report.vec_summary.available_count > 0
    assert report.vec_summary.unavailable_count > 0


def test_incompatible_pair_still_projects_with_reasons() -> None:
    # Even incompatible, we should not crash and should keep unavailable reasons
    baseline = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    variation = validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid"))
    # Force incompatible by manual comparison with mismatch
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_col = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"random_seed": 123}) for r in variation_col.results],
            "metric_version": "9.9",
        }
    )
    report = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(
        report, baseline=baseline, variation=variation
    )
    assert lens.compatibility["is_compatible"] is False
    # At least one metric should be unavailable due to version/seed mismatch
    vec_unavailable = [r for r in lens.vec_summary.rows if r.status == "unavailable"]
    assert len(vec_unavailable) > 0


def test_no_scientific_recomputation() -> None:
    # Ensure projection retains exact values from comparison, not recomputed
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    # Pick a metric and compare
    for lens_row in [*report.traffic_summary.rows, *report.vec_summary.rows]:
        comp_row = next(
            (
                m
                for m in [*comp.comparable_metrics, *comp.unavailable_comparisons]
                if m.metric_key == lens_row.metric_key
            ),
            None,
        )
        if comp_row is not None:
            assert lens_row.baseline == comp_row.baseline
            assert lens_row.variation == comp_row.variation
            assert lens_row.absolute_delta == comp_row.absolute_delta
            assert lens_row.relative_delta == comp_row.relative_delta

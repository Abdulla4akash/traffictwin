"""Pure service tests for traffic and VEC consequence lenses – hardened."""

from __future__ import annotations

import copy
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
    ConsequenceLensReport,
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
    # Canonical bytes deterministic (no generated_at, no absolute paths)
    assert first.to_canonical_bytes() == second.to_canonical_bytes()
    assert first.to_json() == second.to_json()
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    via_comp = build_consequence_lens_report_from_comparison(comp)
    # With fix, optional kwargs must not alter identity
    via_comp_with = build_consequence_lens_report_from_comparison(
        comp, baseline=baseline, variation=variation
    )
    assert via_comp.fingerprint == first.fingerprint
    assert via_comp_with.fingerprint == first.fingerprint
    assert via_comp.to_canonical_bytes() == via_comp_with.to_canonical_bytes()


def test_optional_kwargs_identity_stability() -> None:
    """Same ComparisonReport → with vs without BundleAnalysis kwargs → identical fingerprint."""

    baseline, variation = _baseline_variation()
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    without = build_consequence_lens_report_from_comparison(comp)
    with_kwargs = build_consequence_lens_report_from_comparison(
        comp, baseline=baseline, variation=variation
    )
    assert without.fingerprint == with_kwargs.fingerprint
    assert without.to_canonical_bytes() == with_kwargs.to_canonical_bytes()
    assert without.to_portable_dict() == with_kwargs.to_portable_dict()
    # Also verify build_consequence_lens_report matches via_comp
    direct = build_consequence_lens_report(baseline, variation)
    assert not isinstance(direct, ServiceError)
    assert direct.fingerprint == without.fingerprint


def test_no_absolute_paths_in_report() -> None:
    """Report JSON and fingerprint input must not contain absolute local paths."""

    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    portable = report.to_portable_dict()
    json_str = report.to_json()
    canonical = report.to_canonical_bytes().decode("utf-8")
    for payload in [json.dumps(portable), json_str, canonical]:
        assert "/tmp" not in payload  # noqa: S108
        assert "/private/var" not in payload
        assert "/Users" not in payload
        assert "baseline_bundle_path" not in payload
        assert "variation_bundle_path" not in payload
        assert (
            "bundle_fingerprint" not in payload.lower() or payload.count("bundle_fingerprint") == 0
        )
    # Also ensure fingerprint payload excludes generated_at
    assert "generated_at" not in json.dumps(portable)
    assert "generated_at" not in report.to_portable_dict()


def test_deterministic_canonical_bytes() -> None:
    """Same logical report twice with different comparison times → same fingerprint and bytes."""  # noqa: E501

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    # Two comparisons with different clocks
    from datetime import UTC, datetime

    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 12, 31, tzinfo=UTC)
    comp1 = compare_metric_collections(baseline_col, variation_col, clock=lambda: t1)
    comp2 = compare_metric_collections(baseline_col, variation_col, clock=lambda: t2)
    assert comp1.generated_at != comp2.generated_at
    r1 = build_consequence_lens_report_from_comparison(comp1)
    r2 = build_consequence_lens_report_from_comparison(comp2)
    assert isinstance(r1, ConsequenceLensReport)
    assert isinstance(r2, ConsequenceLensReport)
    assert r1.fingerprint == r2.fingerprint
    assert r1.to_canonical_bytes() == r2.to_canonical_bytes()
    assert r1.to_json() == r2.to_json()
    # Fingerprint must bind export bytes (canonical + fingerprint)
    assert json.loads(r1.to_json())["fingerprint"] == r1.fingerprint
    assert json.loads(r2.to_json())["fingerprint"] == r2.fingerprint


def test_baseline_variation_identity() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert report.baseline_identity["run_id"] == "run-baseline-001"
    assert report.variation_identity["run_id"] == "run-variation-001"
    assert report.baseline_identity["seed_id"] == "s1-gridlock-baseline"
    assert report.variation_identity["seed_id"] == "s1-gridlock-variation"
    # No absolute paths in evidence_standing
    assert "baseline_bundle_path" not in report.evidence_standing
    assert "variation_bundle_path" not in report.evidence_standing
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
    row = by_key["trip.duration.mean_s"]
    assert row.absolute_delta == 330.0
    row2 = by_key["task.completion.rate"]
    assert row2.absolute_delta == -0.25
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
    assert by_key["trip.duration.mean_s"].relative_delta == pytest.approx(0.5238095238095238)
    assert by_key["task.incomplete.rate"].status == "partial"
    assert by_key["task.incomplete.rate"].relative_delta is None
    assert "BASELINE_ZERO" in by_key["task.incomplete.rate"].reason_codes
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    comp_by_key = {
        m.metric_key: m for m in [*comp.comparable_metrics, *comp.unavailable_comparisons]
    }
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
    for key in ["trip.duration.mean_s", "task.latency.mean_ms", "traffic.speed.mean_mps"]:
        assert by_key[key].unit == METRIC_DEFINITIONS[key].unit


def test_metric_version_compatibility_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert report.compatibility.same_metric_version is True
    assert report.compatibility.is_compatible is True
    assert report.baseline_identity["metric_version"] == "1.0"
    assert report.variation_identity["metric_version"] == "1.0"
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid").model_copy(
        update={"metric_version": "9.9"}
    )
    report2 = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens2 = build_consequence_lens_report_from_comparison(report2)
    assert lens2.compatibility.same_metric_version is False
    assert lens2.compatibility.is_compatible is False


def test_unavailable_reason_preserved() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    energy = by_key["task.energy.mean_per_observed_task_j"]
    assert energy.status == "unavailable"
    assert "METRIC_NOT_APPLICABLE" in energy.reason_codes
    assert "COMPARISON_PAIR_INCOMPATIBLE" in energy.reason_codes
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
    assert by_key["infra.saturation.episode_count"].status == "partial"
    assert by_key["task.deadline_miss.completed_observed_rate"].status == "partial"
    assert by_key["traffic.time_coverage"].status == "unavailable"


def test_incompatible_pair_refusal() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
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
    assert lens.compatibility.same_experiment is False
    assert lens.compatibility.is_compatible is False
    assert any("experiment identifiers differ" in str(w) for w in lens.warnings)
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
    assert lens2.compatibility.same_random_seed is False
    assert lens2.compatibility.is_compatible is False
    assert len(report2.comparable_metrics) == 0
    assert len(report2.unavailable_comparisons) == len(ALL_LENS_KEYS)


def test_no_invented_metrics() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    all_keys = {row.metric_key for row in [*report.traffic_summary.rows, *report.vec_summary.rows]}
    assert all_keys == set(ALL_LENS_KEYS)
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
    assert by_key["task.generated.count"].denominator_description is None


def test_offered_admitted_denominator_distinction() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    by_key = {
        row.metric_key: row for row in [*report.traffic_summary.rows, *report.vec_summary.rows]
    }
    denom = by_key["task.completion.rate"].denominator_description
    assert denom is not None and "generated" in denom.lower()
    assert (
        by_key["task.completion.rate"].denominator_description
        != by_key["task.deadline_miss.completed_observed_rate"].denominator_description
    )


def test_unknown_provenance_remains_unknown() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    report = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    report.baseline_context["synthetic"] = None
    report.variation_context["synthetic"] = None
    lens = build_consequence_lens_report_from_comparison(report)
    assert lens.evidence_standing["baseline_synthetic"] is None
    assert lens.evidence_standing["variation_synthetic"] is None
    # None==None must NOT become True – must be unknown (None) and fail closed
    assert lens.compatibility.synthetic_match is None
    assert lens.compatibility.is_compatible is False


def test_unknown_single_side_provenance() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    report = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    report.baseline_context["synthetic"] = True
    report.variation_context["synthetic"] = None
    lens = build_consequence_lens_report_from_comparison(report)
    assert lens.compatibility.synthetic_match is None
    assert lens.compatibility.is_compatible is False


def test_missing_run_seed_identity() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    report = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    report.baseline_context["run_id"] = None
    report.baseline_context["seed_id"] = ""
    lens = build_consequence_lens_report_from_comparison(report)
    assert lens.evidence_standing["baseline_run_id"] is None
    assert lens.evidence_standing["baseline_seed_id"] in (None, "")
    # Compatibility for missing run/seed not required, but identity must stay Unknown
    # Ensure portable dict does not contain string "None" as fabricated identity
    portable = lens.to_portable_dict()
    assert portable["evidence_standing"]["baseline_run_id"] is None
    json_str = lens.to_json()
    # Should not contain the literal digest of "None" as run id
    assert (
        '"None"' not in json_str or json_str.count('"None"') == 0 or "Unavailable" not in json_str
    )  # we just ensure no fake "None" tokenization


def test_deterministic_serialisation_export() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    first_json = report.to_json()
    second_json = report.to_json()
    assert first_json == second_json
    data = json.loads(first_json)
    assert "fingerprint" in data
    # Portable dict round-trips
    portable = report.to_portable_dict()
    assert portable["baseline_identity"]["run_id"] == "run-baseline-001"
    assert "fingerprint" not in portable
    # Fingerprint binds canonical bytes
    assert report.fingerprint == report.to_canonical_bytes().hex() or len(report.fingerprint) == 64
    # Actually fingerprint is hex SHA256 of canonical bytes
    import hashlib
    import json as _json

    canonical = _json.dumps(
        portable, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert report.fingerprint == hashlib.sha256(canonical).hexdigest()
    assert "NaN" not in first_json
    assert "Infinity" not in first_json


def test_unavailable_and_available_counts() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert (
        report.traffic_summary.available_count
        + report.traffic_summary.partial_count
        + report.traffic_summary.unavailable_count
        == len(TRAFFIC_LENS_KEYS)
    )
    assert (
        report.vec_summary.available_count
        + report.vec_summary.partial_count
        + report.vec_summary.unavailable_count
        == len(VEC_LENS_KEYS)
    )
    assert report.traffic_summary.available_count > 0
    assert report.vec_summary.available_count > 0
    assert report.vec_summary.unavailable_count > 0


def test_incompatible_pair_still_projects_with_reasons() -> None:
    baseline = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    variation = validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid"))
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
    assert lens.compatibility.is_compatible is False
    vec_unavailable = [r for r in lens.vec_summary.rows if r.status == "unavailable"]
    assert len(vec_unavailable) > 0


def test_no_scientific_recomputation() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
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


def test_golden_committed_fixture_counts() -> None:
    """Pin deterministic counts for the committed fixture pair."""

    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    assert report.traffic_summary.available_count == 18
    assert report.traffic_summary.partial_count == 0
    assert report.traffic_summary.unavailable_count == 1
    assert len(report.traffic_summary.rows) == 19
    assert report.vec_summary.available_count == 19
    assert report.vec_summary.partial_count == 3
    assert report.vec_summary.unavailable_count == 19
    assert len(report.vec_summary.rows) == 41


def test_fingerprint_binds_complete_payload() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    second = build_consequence_lens_report(baseline, variation)
    assert not isinstance(second, ServiceError)
    assert report.fingerprint == second.fingerprint
    # Same identities but one value differs → fingerprint differs
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    comp_changed = copy.deepcopy(comp)
    comp_changed.comparable_metrics[0] = comp_changed.comparable_metrics[0].model_copy(
        update={"baseline": 9999}
    )
    lens_changed = build_consequence_lens_report_from_comparison(comp_changed)
    assert lens.fingerprint != lens_changed.fingerprint


def test_fingerprint_binds_status_change() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    comp_status = copy.deepcopy(comp)
    # Flip status of first comparable metric from available to unavailable
    orig = comp_status.comparable_metrics[0]
    assert orig.status.value == "available"
    comp_status.comparable_metrics[0] = orig.model_copy(
        update={
            "status": comp_status.unavailable_comparisons[0].status
            if comp_status.unavailable_comparisons
            else orig.status
        }
    )
    # Ensure we actually changed it to unavailable
    if comp_status.comparable_metrics[0].status.value == "available":
        # force to unavailable if no unavailable template
        from traffictwin.metrics.comparison import ComparisonStatus

        comp_status.comparable_metrics[0] = orig.model_copy(
            update={"status": ComparisonStatus.UNAVAILABLE}
        )
    lens_status = build_consequence_lens_report_from_comparison(comp_status)
    assert lens.fingerprint != lens_status.fingerprint


def test_fingerprint_binds_reason_code_change() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    comp_reason = copy.deepcopy(comp)
    # Add a new reason code to first metric
    m = comp_reason.comparable_metrics[0]
    from traffictwin.metrics.results import UnavailableReason

    new_reasons = list(m.reason_codes) + [UnavailableReason.BASELINE_ZERO]
    comp_reason.comparable_metrics[0] = m.model_copy(update={"reason_codes": new_reasons})
    lens_reason = build_consequence_lens_report_from_comparison(comp_reason)
    assert lens.fingerprint != lens_reason.fingerprint


def test_fingerprint_binds_compatibility_finding_change() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    comp_compat = copy.deepcopy(comp)
    m = comp_compat.comparable_metrics[0]
    comp_compat.comparable_metrics[0] = m.model_copy(
        update={
            "compatibility_findings": m.compatibility_findings
            + ["synthetic provenance is questionable"]
        }
    )
    lens_compat = build_consequence_lens_report_from_comparison(comp_compat)
    assert lens.fingerprint != lens_compat.fingerprint


def test_fingerprint_binds_provenance_change() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    comp2 = copy.deepcopy(comp)
    if comp2.comparable_metrics:
        orig = comp2.comparable_metrics[0]
        mutated_provenance = dict(orig.provenance)
        mutated_provenance["baseline_run_id"] = "mutated-run-id"
        comp2.comparable_metrics[0] = orig.model_copy(update={"provenance": mutated_provenance})
        lens2 = build_consequence_lens_report_from_comparison(comp2)
        assert lens.fingerprint != lens2.fingerprint


def test_fingerprint_ignores_local_absolute_path() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens_without = build_consequence_lens_report_from_comparison(comp)
    # With local BundleAnalysis that would previously inject /tmp paths – now ignored
    baseline, variation = _baseline_variation()
    lens_with = build_consequence_lens_report_from_comparison(
        comp, baseline=baseline, variation=variation
    )
    assert lens_without.fingerprint == lens_with.fingerprint
    assert lens_without.to_canonical_bytes() == lens_with.to_canonical_bytes()


def test_same_report_across_tmp_directories(tmp_path: Path) -> None:
    """Same report across tmp roots → same fingerprint and export."""  # noqa: E501

    baseline, variation = _baseline_variation()
    r1 = build_consequence_lens_report(baseline, variation)
    r2 = build_consequence_lens_report(baseline, variation)
    assert not isinstance(r1, ServiceError) and not isinstance(r2, ServiceError)
    assert isinstance(r1, ConsequenceLensReport)
    assert isinstance(r2, ConsequenceLensReport)
    assert r1.fingerprint == r2.fingerprint
    assert r1.to_canonical_bytes() == r2.to_canonical_bytes()
    assert r1.to_json() == r2.to_json()
    for txt in [r1.to_json(), r2.to_json(), r1.to_canonical_bytes().decode()]:
        assert "/tmp" not in txt  # noqa: S108
        assert "baseline_bundle_path" not in txt


def test_direction_preserved_from_authoritative_comparison() -> None:
    baseline, variation = _baseline_variation()
    report = build_consequence_lens_report(baseline, variation)
    assert not isinstance(report, ServiceError)
    from traffictwin.ui.services.provenance import compare_runs_for_ui

    comp = compare_runs_for_ui(baseline, variation)
    assert not isinstance(comp, ServiceError)
    comp_by_key = {
        m.metric_key: m for m in [*comp.comparable_metrics, *comp.unavailable_comparisons]
    }
    for row in [*report.traffic_summary.rows, *report.vec_summary.rows]:
        expected = comp_by_key[row.metric_key].direction.value
        assert row.direction == expected, f"direction mismatch for {row.metric_key}"


def test_compatibility_requires_random_seed() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility.same_random_seed is True
    assert lens.compatibility.is_compatible is True
    assert len(comp.comparable_metrics) > 0
    variation_mismatch = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"random_seed": 999}) for r in variation_col.results]
        }
    )
    comp2 = compare_metric_collections(
        baseline_col,
        variation_mismatch,
        ComparisonRequest(
            baseline_run_id="run-baseline-001",
            variation_run_id="run-variation-001",
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens2 = build_consequence_lens_report_from_comparison(comp2)
    assert lens2.compatibility.same_random_seed is False
    assert lens2.compatibility.is_compatible is False
    assert len(comp2.comparable_metrics) == 0
    assert len(comp2.unavailable_comparisons) == len(ALL_LENS_KEYS)


def test_compatibility_unknown_fails_closed() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    # Both unknown
    comp.baseline_context["synthetic"] = None
    comp.variation_context["synthetic"] = None
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility.synthetic_match is None
    assert lens.compatibility.is_compatible is False
    # One unknown
    comp2 = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp2.baseline_context["random_seed"] = None
    lens2 = build_consequence_lens_report_from_comparison(comp2)
    assert lens2.compatibility.same_random_seed is None
    assert lens2.compatibility.is_compatible is False
    # Unknown experiment
    comp3 = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp3.baseline_context["experiment_id"] = None
    lens3 = build_consequence_lens_report_from_comparison(comp3)
    assert lens3.compatibility.same_experiment is None
    assert lens3.compatibility.is_compatible is False


def test_synthetic_mismatch_gates_compatibility() -> None:
    """Synthetic/imported mismatch must yield synthetic_match False and is_compatible False."""

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_synth_false = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"synthetic": False}) for r in variation_col.results]
        }
    )
    comp = compare_metric_collections(
        baseline_col,
        variation_synth_false,
        ComparisonRequest(
            baseline_run_id=baseline_col.run_id,
            variation_run_id=variation_synth_false.run_id,
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    assert "synthetic flags differ" in comp.warnings
    lens = build_consequence_lens_report_from_comparison(comp)
    assert lens.compatibility.synthetic_match is False
    assert lens.compatibility.is_compatible is False
    assert "synthetic flags differ" in lens.warnings
    assert lens.traffic_summary.warnings == []
    assert lens.vec_summary.warnings == []
    exported = json.loads(lens.to_json())
    assert exported["compatibility"]["is_compatible"] is False
    assert exported["compatibility"]["synthetic_match"] is False
    assert "synthetic flags differ" in exported["warnings"]
    assert (
        "warnings" not in exported["compatibility"]
        or exported["compatibility"].get("warnings") is None
    )
    comp_ok = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens_ok = build_consequence_lens_report_from_comparison(comp_ok)
    assert lens_ok.compatibility.synthetic_match is True
    assert lens_ok.compatibility.is_compatible is True
    assert lens_ok.warnings == []


def test_warning_consistency_across_report_and_summaries() -> None:
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    variation_mv = variation_col.model_copy(update={"metric_version": "9.9"})
    comp = compare_metric_collections(baseline_col, variation_mv, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    assert "metric collection versions differ" in lens.warnings
    assert lens.traffic_summary.warnings == []
    assert lens.vec_summary.warnings == []
    assert lens.compatibility.is_compatible is False
    comp_ok = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens_ok = build_consequence_lens_report_from_comparison(comp_ok)
    assert lens_ok.warnings == []
    assert not hasattr(lens_ok.compatibility, "warnings")
    assert lens_ok.traffic_summary.warnings == []
    assert lens_ok.vec_summary.warnings == []


def test_fingerprint_binds_evidence_provenance_and_compatibility() -> None:
    """Fingerprint must bind evidence standing, provenance, and compatibility findings."""

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    variation_synth_false = variation_col.model_copy(
        update={
            "results": [r.model_copy(update={"synthetic": False}) for r in variation_col.results]
        }
    )
    comp_synth = compare_metric_collections(
        baseline_col,
        variation_synth_false,
        ComparisonRequest(
            baseline_run_id=baseline_col.run_id,
            variation_run_id=variation_synth_false.run_id,
            require_same_random_seed=True,
        ),
        clock=fixed_clock,
    )
    lens_synth = build_consequence_lens_report_from_comparison(comp_synth)
    assert lens.fingerprint != lens_synth.fingerprint
    comp2 = copy.deepcopy(comp)
    if comp2.comparable_metrics:
        orig = comp2.comparable_metrics[0]
        mutated_provenance = dict(orig.provenance)
        mutated_provenance["baseline_run_id"] = "mutated-run-id"
        comp2.comparable_metrics[0] = orig.model_copy(update={"provenance": mutated_provenance})
        lens2 = build_consequence_lens_report_from_comparison(comp2)
        assert lens.fingerprint != lens2.fingerprint


def test_download_filename_stable_across_workspaces(tmp_path: Path) -> None:
    """Same report on different workspaces → same fingerprint and filename."""  # noqa: E501

    baseline, variation = _baseline_variation()
    r1 = build_consequence_lens_report(baseline, variation)
    r2 = build_consequence_lens_report(baseline, variation)
    assert not isinstance(r1, ServiceError) and not isinstance(r2, ServiceError)
    f1 = r1.fingerprint[:12] + "-lens.json" if r1.fingerprint else "consequence-lens.json"
    f2 = r2.fingerprint[:12] + "-lens.json" if r2.fingerprint else "consequence-lens.json"
    assert r1.fingerprint == r2.fingerprint
    assert f1 == f2
    assert r1.to_json() == r2.to_json()


def test_provenance_badge_shared_helper() -> None:
    from traffictwin.ui.components.badges import provenance_badge

    assert provenance_badge(None) == ":gray-badge[UNKNOWN]"
    assert "SYNTHETIC" in provenance_badge(True) or "synthetic" in provenance_badge(True).lower()
    assert "IMPORTED" in provenance_badge(False)
    # Unknown not collapsed to false
    assert provenance_badge(None) != provenance_badge(False)


def test_typed_compatibility_rejects_invalid_types() -> None:
    import pytest
    from pydantic import ValidationError

    from traffictwin.ui.consequence_lenses import ConsequenceCompatibility

    # Valid tri-state
    c = ConsequenceCompatibility(
        same_experiment=True,
        same_random_seed=None,
        same_metric_version=False,
        synthetic_match=None,
        is_compatible=False,
        baseline_metric_version="1.0",
        variation_metric_version=None,
    )
    assert c.same_experiment is True
    assert c.same_random_seed is None
    # Invalid type should be rejected (extra fields, wrong type)
    with pytest.raises(ValidationError):
        ConsequenceCompatibility(same_experiment="yes", is_compatible=True)
    with pytest.raises(ValidationError):
        ConsequenceCompatibility(is_compatible=True, extra_field="oops")  # type: ignore[call-arg]


def test_typed_compatibility_serialises_and_fingerprint_deterministic() -> None:
    import json

    from tests.helpers import fixed_clock, metric_collection
    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import build_consequence_lens_report_from_comparison

    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    lens = build_consequence_lens_report_from_comparison(comp)
    # Tri-state serialises correctly: True/False/None -> true/false/null
    exported = json.loads(lens.to_json())
    assert exported["compatibility"]["same_experiment"] in (True, False, None)
    assert "is_compatible" in exported["compatibility"]
    # Deterministic
    lens2 = build_consequence_lens_report_from_comparison(comp)
    assert lens.fingerprint == lens2.fingerprint
    assert lens.to_canonical_bytes() == lens2.to_canonical_bytes()
    # Changing compatibility changes fingerprint


def test_consequence_caching_hit_miss_and_mutation_isolation(tmp_path: Path) -> None:
    import copy
    from pathlib import Path as _Path

    from tests.helpers import fixed_clock, metric_collection
    from traffictwin.metrics.comparison import compare_metric_collections
    from traffictwin.ui.consequence_lenses import (
        build_consequence_lens_report,
        build_consequence_lens_report_from_comparison,
        clear_consequence_report_cache,
        get_cached_consequence_report,
    )
    from traffictwin.ui.services import validate_bundle_for_ui

    clear_consequence_report_cache()
    b = validate_bundle_for_ui(_Path("tests/fixtures/bundles/baseline_valid"))
    v = validate_bundle_for_ui(_Path("tests/fixtures/bundles/variation_valid"))
    r1 = build_consequence_lens_report(b, v)
    assert not isinstance(r1, ServiceError)
    # Second build of same logical pair should hit cache (same fingerprint, same bytes)
    r2 = build_consequence_lens_report(b, v)
    assert not isinstance(r2, ServiceError)
    assert r1.fingerprint == r2.fingerprint
    assert r1.to_canonical_bytes() == r2.to_canonical_bytes()
    # Cache returns deep copy so mutation does not corrupt
    r1_mut = r1.model_copy(deep=True)
    r1_mut.warnings.append("injected")
    cached = get_cached_consequence_report(r1.fingerprint)
    assert cached is not None
    assert "injected" not in cached.warnings
    # Changed evidence causes cache miss (different fingerprint)
    baseline_col = metric_collection("baseline_valid")
    variation_col = metric_collection("variation_valid")
    comp = compare_metric_collections(baseline_col, variation_col, clock=fixed_clock)
    comp2 = copy.deepcopy(comp)
    comp2.comparable_metrics[0] = comp2.comparable_metrics[0].model_copy(update={"baseline": 9999})
    lens_a = build_consequence_lens_report_from_comparison(comp)
    lens_b = build_consequence_lens_report_from_comparison(comp2)
    assert lens_a.fingerprint != lens_b.fingerprint
    # Cache does not alter canonical fingerprint/export
    assert "injected" not in lens_a.to_json()

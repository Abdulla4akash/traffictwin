"""Unit tests for Calibration Workbench — deterministic, pairing, coverage, units, objective, weights, exports, authority."""  # noqa: E501

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import timedelta

import pytest
from pydantic import ValidationError

from traffictwin.calibration.fixtures import (
    make_candidate_good,
    make_candidate_incompatible,
    make_candidate_missing,
    make_candidate_poor,
    make_candidate_temporal_misaligned,
    make_default_study,
    make_observed_fixture,
    make_three_candidate_study,
    synthetic_bin_width,
    synthetic_window_end,
    synthetic_window_start,
)
from traffictwin.calibration.models import (
    CalibrationAlignmentSpec,
    CalibrationBin,
    CalibrationCandidate,
    CalibrationMetricSpec,
    CalibrationObservedReference,
    CalibrationStatus,
    CalibrationStudy,
    ExclusionReasonCode,
    MissingnessPolicy,
)
from traffictwin.calibration.service import (
    EVIDENCE_BOUNDARY,
    build_calibration_report,
    calibration_report_to_json,
    export_metric_results_csv,
    export_residuals_csv,
)


def _make_study_with_candidates(
    cands: list[CalibrationCandidate],
    *,
    specs: list[CalibrationMetricSpec] | None = None,
    coverage_threshold: float = 0.0,
) -> CalibrationStudy:
    obs = make_observed_fixture()
    if specs is None:
        specs = [
            CalibrationMetricSpec(
                metric_key="flow.count",
                metric_version="1.0",
                unit="veh/h",
                denominator="per_sensor_per_hour",
                weight=0.5,
                objective_scale=100.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
            CalibrationMetricSpec(
                metric_key="traffic.speed.mean_mps",
                metric_version="1.0",
                unit="m/s",
                denominator="per_sensor_per_window",
                weight=0.5,
                objective_scale=5.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
        ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=coverage_threshold,
    )
    return CalibrationStudy(
        study_id="test_study",
        study_name="Test Study",
        description="Test",
        observed=obs,
        candidates=cands,
        metric_specs=specs,
        alignment_spec=alignment,
    )


# Determinism
def test_deterministic_report_fingerprint() -> None:
    study = make_three_candidate_study()
    r1 = build_calibration_report(study)
    r2 = build_calibration_report(study)
    assert r1.fingerprint == r2.fingerprint
    assert r1.to_canonical_bytes() == r2.to_canonical_bytes()


def test_order_independence() -> None:
    obs = make_observed_fixture()
    good = make_candidate_good()
    poor = make_candidate_poor()
    incompatible = make_candidate_incompatible()
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.6,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.4,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    s1 = CalibrationStudy(
        study_id="order_test",
        study_name="Order Test",
        observed=obs,
        candidates=[good, poor, incompatible],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    s2 = CalibrationStudy(
        study_id="order_test",
        study_name="Order Test",
        observed=obs,
        candidates=[incompatible, good, poor],
        metric_specs=list(reversed(specs)),
        alignment_spec=alignment,
    )
    r1 = build_calibration_report(s1)
    r2 = build_calibration_report(s2)
    assert r1.fingerprint == r2.fingerprint


# Unit mismatches
def test_unit_mismatch_exclusion_candidate() -> None:
    good = make_candidate_good()
    incompatible = make_candidate_incompatible()
    study = _make_study_with_candidates([good, incompatible])
    report = build_calibration_report(study)
    incompat = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_incompatible"
    )
    assert incompat.alignment_audit.unit_compatible is False
    assert incompat.alignment_audit.is_excluded is True
    assert incompat.status.value == "excluded"
    assert any(
        e.candidate_id == "candidate_incompatible" and e.reason_code == "UNIT_MISMATCH"
        for e in report.exclusions
    )


def test_observed_unit_mismatch_blocks_all() -> None:
    # spec veh/h, observed veh/min, candidate veh/h -> should be UNIT_MISMATCH
    obs = make_observed_fixture()
    # mutate observed to have veh/min for flow
    # Create new observed with wrong unit
    wrong_bins = []
    for b in obs.bins:
        unit = "veh/min" if b.metric_key == "flow.count" else b.unit
        wrong_bins.append(
            CalibrationBin(
                sensor_id=b.sensor_id,
                window_index=b.window_index,
                window_start_utc=b.window_start_utc,
                window_end_utc=b.window_end_utc,
                metric_key=b.metric_key,
                value=b.value,
                unit=unit,
            )
        )
    wrong_metric_units = dict(obs.metric_units)
    wrong_metric_units["flow.count"] = "veh/min"
    wrong_obs = CalibrationObservedReference(
        observed_id=obs.observed_id,
        fingerprint=obs.fingerprint,
        evidence_label=obs.evidence_label,
        window_start_utc=obs.window_start_utc,
        window_end_utc=obs.window_end_utc,
        bin_width_s=obs.bin_width_s,
        sensor_ids=obs.sensor_ids,
        metric_units=wrong_metric_units,
        bins=wrong_bins,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.6,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.4,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    good = make_candidate_good()
    study = CalibrationStudy(
        study_id="obs_unit_test",
        study_name="Obs Unit Test",
        observed=wrong_obs,
        candidates=[good],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.alignment_audit.unit_compatible is False
    assert summary.status.value == "excluded"
    assert any(e.reason_code == "UNIT_MISMATCH" for e in report.exclusions)
    # No numeric comparison
    assert summary.metric_results == []
    assert summary.weighted_objective is None
    assert summary.candidate_id not in report.ranking


def test_unit_mismatch_deduplication() -> None:
    # candidate has both metric_units mismatch and per-bin mismatch same issue; should appear once
    cand = make_candidate_incompatible()  # already has veh/min mismatch
    study = _make_study_with_candidates([cand])
    # Actually test candidate with explicit duplicate: metric_units says veh/min and every bin also veh/min, but should be one entry per distinct string  # noqa: E501
    report = build_calibration_report(study)
    summary = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_incompatible"
    )
    # Check deduplicated sorted
    mismatches = summary.alignment_audit.unit_mismatches
    assert len(mismatches) == len(set(mismatches))
    assert mismatches == sorted(mismatches)
    # Should be exactly one flow mismatch, not 8 duplicates
    flow_mismatches = [m for m in mismatches if "flow.count" in m]
    assert (
        len(flow_mismatches) == 1 or len(flow_mismatches) == 2
    )  # at most 2 distinct (candidate expected vs bin)
    # Ensure not 16 duplicates
    assert len(flow_mismatches) < 5


# Temporal
def test_temporal_misalignment_exclusion() -> None:
    good = make_candidate_good()
    misaligned = make_candidate_temporal_misaligned()
    study = _make_study_with_candidates([good, misaligned])
    report = build_calibration_report(study)
    mis = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_temporal_misaligned"
    )
    assert mis.alignment_audit.temporal_aligned is False
    assert mis.alignment_audit.is_excluded is True
    assert mis.status.value == "excluded"
    assert any(
        e.candidate_id == "candidate_temporal_misaligned"
        and e.reason_code == "TEMPORAL_MISALIGNMENT"
        for e in report.exclusions
    )


# Coverage
def test_missing_evidence_not_zero_filled() -> None:
    missing = make_candidate_missing()
    good = make_candidate_good()
    study = _make_study_with_candidates([good, missing])
    report = build_calibration_report(study)
    missing_sum = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_missing_evidence"
    )
    flow_res = next(m for m in missing_sum.metric_results if m.metric_key == "flow.count")
    assert flow_res.count_missing_simulation >= 7
    assert flow_res.count_paired == 1
    assert flow_res.mae is not None
    assert flow_res.mae < 5.0
    for r in missing_sum.residuals:
        if (
            r.metric_key == "flow.count"
            and r.sensor_id == "sensor_A"
            and r.window_index in (1, 2, 3)
        ):
            assert r.simulated_value is None
            assert r.signed_error is None


def test_objective_unavailable_when_one_required_component_missing() -> None:
    ws = synthetic_window_start()
    we = synthetic_window_end()
    bw = synthetic_bin_width()
    speed_vals: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    bins: list[CalibrationBin] = []
    for sensor in ["sensor_A", "sensor_B"]:
        for idx in range(4):
            start = ws + timedelta(seconds=idx * bw)
            end = start + timedelta(seconds=bw)
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=start,
                    window_end_utc=end,
                    metric_key="flow.count",
                    value=None,
                    unit="veh/h",
                )
            )
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=start,
                    window_end_utc=end,
                    metric_key="traffic.speed.mean_mps",
                    value=speed_vals[(sensor, idx)],
                    unit="m/s",
                )
            )
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_flow_all_missing",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand_all_missing = CalibrationCandidate(
        candidate_id="candidate_flow_all_missing",
        fingerprint=fp,
        label="All flow missing",
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        sensor_ids=["sensor_A", "sensor_B"],
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )
    study = _make_study_with_candidates([cand_all_missing])
    report = build_calibration_report(study)
    summary = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_flow_all_missing"
    )
    flow_res = next(m for m in summary.metric_results if m.metric_key == "flow.count")
    assert flow_res.is_available is False
    assert flow_res.count_paired == 0
    assert summary.weighted_objective is None
    assert summary.status.value == "unavailable"


# B1 coverage
def test_extra_candidate_bin_no_crash_and_no_inflation() -> None:
    good = make_candidate_good()
    # Need to make candidate that includes extra bin but also passes validation: must expand window to include extra?  # noqa: E501
    # To avoid window validation failure, create candidate with larger window
    # Instead add extra sensor not in observed: e.g., sensor_extra
    # Simpler: add extra bin for sensor that is not in observed but use valid window inside observed window but with extra metric? Let's use valid window but extra sensor  # noqa: E501
    # For extra bin to be "outside reference key set", we add a bin for sensor sensor_A with metric that is not in spec? But spec includes flow and speed only. Let's add extra sensor.  # noqa: E501
    # Create candidate with original bins plus one extra bin for new sensor
    extra_sensor = "sensor_extra"
    # Need candidate sensor_ids include extra
    bins_with_extra = list(good.bins) + [
        CalibrationBin(
            sensor_id=extra_sensor,
            window_index=0,
            window_start_utc=synthetic_window_start(),
            window_end_utc=synthetic_window_start() + timedelta(seconds=synthetic_bin_width()),
            metric_key="flow.count",
            value=500.0,
            unit="veh/h",
        )
    ]
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(
                bins_with_extra, key=lambda x: (x.sensor_id, x.window_index, x.metric_key)
            )
        ],
        "candidate_id": "candidate_with_extra",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand_extra = CalibrationCandidate(
        candidate_id="candidate_with_extra",
        fingerprint=fp,
        label="With extra sensor",
        window_start_utc=good.window_start_utc,
        window_end_utc=good.window_end_utc,
        bin_width_s=good.bin_width_s,
        sensor_ids=sorted(set(good.sensor_ids + [extra_sensor])),
        metric_units=good.metric_units,
        bins=bins_with_extra,
    )
    study = _make_study_with_candidates([good, cand_extra])
    report = build_calibration_report(study)
    good_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    extra_sum = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_with_extra"
    )
    assert extra_sum.alignment_audit.coverage_percentage <= 100.0
    # Coverage should remain 100 for both if all eligible paired
    assert good_sum.coverage_percentage == 100.0
    assert (
        extra_sum.coverage_percentage == 100.0
    )  # extra bin does not increase paired beyond eligible, not decrease
    assert extra_sum.alignment_audit.extra_candidate_bin_count == 1
    # MAE unchanged
    good_mae = next(m for m in good_sum.metric_results if m.metric_key == "flow.count").mae
    extra_mae = next(m for m in extra_sum.metric_results if m.metric_key == "flow.count").mae
    assert good_mae == extra_mae
    # Residual count same (eligible only)
    assert len(good_sum.residuals) == len(extra_sum.residuals)
    # No crash
    assert report.fingerprint is not None


def test_coverage_threshold() -> None:
    obs = make_observed_fixture()
    # Create candidate with 75% coverage (6 of 8 eligible for flow? Actually we have 16 eligible (8 per metric *2 metrics? Wait eligible is non-missing observed: 8 per metric *2 =16 total? For test we count per audit total 16.  # noqa: E501
    # Let's create candidate that has 12 paired out of 16 eligible -> 75%
    # Missing 4 bins (2 sensors *2 windows)
    flow_vals: dict[tuple[str, int], float | None] = {}
    for sensor in ["sensor_A", "sensor_B"]:
        for idx in range(4):
            if (sensor, idx) in [
                ("sensor_A", 0),
                ("sensor_A", 1),
                ("sensor_B", 0),
                ("sensor_B", 1),
            ]:
                if sensor == "sensor_A" and idx == 0:
                    flow_vals[(sensor, idx)] = 102.0
                elif sensor == "sensor_A" and idx == 1:
                    flow_vals[(sensor, idx)] = 118.0
                elif sensor == "sensor_B" and idx == 0:
                    flow_vals[(sensor, idx)] = 91.0
                elif sensor == "sensor_B" and idx == 1:
                    flow_vals[(sensor, idx)] = 88.0
                else:
                    flow_vals[(sensor, idx)] = None
            else:
                flow_vals[(sensor, idx)] = None
    # Actually we want 75% overall: 12 paired (6 missing) out of 16. Let's make flow 4 paired out of 8, speed 8 paired out of 8 => 12/16=75%  # noqa: E501
    speed_vals = {
        ("sensor_A", 0): 12.6,
        ("sensor_A", 1): 12.9,
        ("sensor_A", 2): 12.9,
        ("sensor_A", 3): 12.7,
        ("sensor_B", 0): 11.1,
        ("sensor_B", 1): 11.3,
        ("sensor_B", 2): 11.6,
        ("sensor_B", 3): 11.4,
    }
    from traffictwin.calibration.fixtures import _make_candidate_bins

    bins_75 = _make_candidate_bins(flow_values=flow_vals, speed_values=speed_vals)
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins_75, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_75pct",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand_75 = CalibrationCandidate(
        candidate_id="candidate_75pct",
        fingerprint=fp,
        label="75% coverage",
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        sensor_ids=["sensor_A", "sensor_B"],
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins_75,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.6,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.4,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment_80 = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.80,
    )
    study = CalibrationStudy(
        study_id="coverage_test",
        study_name="Coverage Test",
        observed=obs,
        candidates=[cand_75],
        metric_specs=specs,
        alignment_spec=alignment_80,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.alignment_audit.coverage_percentage == 75.0
    assert summary.alignment_audit.is_excluded is True
    assert summary.alignment_audit.exclusion_reason_code == "COVERAGE_INSUFFICIENT"
    assert summary.status.value == "excluded"

    # Now at threshold exactly 75% with threshold 0.75:  # noqa: E501
    # aggregate 12/16 =75% passes audit, but per-metric flow 4/8=50% fails gate
    alignment_75 = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.75,
    )
    study2 = CalibrationStudy(
        study_id="coverage_test2",
        study_name="Coverage Test2",
        observed=obs,
        candidates=[cand_75],
        metric_specs=specs,
        alignment_spec=alignment_75,
    )
    report2 = build_calibration_report(study2)
    summary2 = report2.candidate_summaries[0]
    # Aggregate audit passes exactly at threshold
    assert summary2.alignment_audit.coverage_percentage == 75.0
    assert summary2.alignment_audit.is_excluded is False
    # Per-metric gate must still exclude because flow.count is only 50%
    assert summary2.status == CalibrationStatus.EXCLUDED
    assert summary2.exclusion is not None
    assert summary2.exclusion.reason_code == ExclusionReasonCode.COVERAGE_INSUFFICIENT.value
    assert summary2.candidate_id not in report2.ranking
    flow_res = next(m for m in summary2.metric_results if m.metric_key == "flow.count")
    assert flow_res.coverage_percentage == 50.0
    assert flow_res.count_paired == 4
    speed_res = next(m for m in summary2.metric_results if m.metric_key == "traffic.speed.mean_mps")
    assert speed_res.coverage_percentage == 100.0
    assert speed_res.count_paired == 8


def test_compatible_candidate_ranking_with_normalization() -> None:
    good = make_candidate_good()
    poor = make_candidate_poor()
    study = _make_study_with_candidates([poor, good])
    report = build_calibration_report(study)
    good_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    poor_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_poor_fit")
    assert good_sum.weighted_objective is not None
    assert poor_sum.weighted_objective is not None
    assert good_sum.weighted_objective < poor_sum.weighted_objective
    assert report.ranking[0] == "candidate_good_fit"
    # Normalized MAE visible
    for m in good_sum.metric_results:
        assert m.normalized_mae is not None
        assert m.objective_scale is not None
        assert m.normalized_mae == m.mae / m.objective_scale  # type: ignore[operator]


def test_weight_reversal_ranking() -> None:
    # Create trade-off fixture
    # Candidate A: better flow (small error), worse speed
    # Candidate B: worse flow, better speed
    # Use explicit values to ensure trade-off
    ws = synthetic_window_start()
    we = synthetic_window_end()
    bw = synthetic_bin_width()

    # Observed flow values: as per fixture
    # We'll craft A and B
    def make_tradeoff_candidate(
        cid: str, flow_err: float, speed_err: float
    ) -> CalibrationCandidate:
        # flow_err added to observed flow, speed_err added to observed speed
        obs = make_observed_fixture()
        bins: list[CalibrationBin] = []
        for b in obs.bins:
            if b.metric_key == "flow.count":
                val = (b.value or 0) + flow_err
            else:
                val = (b.value or 0) + speed_err
            bins.append(
                CalibrationBin(
                    sensor_id=b.sensor_id,
                    window_index=b.window_index,
                    window_start_utc=b.window_start_utc,
                    window_end_utc=b.window_end_utc,
                    metric_key=b.metric_key,
                    value=val,
                    unit=b.unit,
                )
            )
        payload = {
            "bins": [
                x.canonical_dict()
                for x in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
            ],
            "candidate_id": cid,
        }
        fp = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        ).hexdigest()
        return CalibrationCandidate(
            candidate_id=cid,
            fingerprint=fp,
            label=f"Tradeoff {cid}",
            window_start_utc=ws,
            window_end_utc=we,
            bin_width_s=bw,
            sensor_ids=["sensor_A", "sensor_B"],
            metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
            bins=bins,
        )

    cand_a = make_tradeoff_candidate(
        "candidate_A", flow_err=2.0, speed_err=5.0
    )  # good flow, bad speed
    cand_b = make_tradeoff_candidate(
        "candidate_B", flow_err=15.0, speed_err=0.5
    )  # bad flow, good speed

    specs_90flow = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.9,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.1,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    specs_90speed = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.1,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.9,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    study1 = CalibrationStudy(
        study_id="tradeoff1",
        study_name="Tradeoff1",
        observed=make_observed_fixture(),
        candidates=[cand_a, cand_b],
        metric_specs=specs_90flow,
        alignment_spec=alignment,
    )
    study2 = CalibrationStudy(
        study_id="tradeoff2",
        study_name="Tradeoff2",
        observed=make_observed_fixture(),
        candidates=[cand_a, cand_b],
        metric_specs=specs_90speed,
        alignment_spec=alignment,
    )
    r1 = build_calibration_report(study1)
    r2 = build_calibration_report(study2)
    assert r1.ranking[0] == "candidate_A"
    assert r2.ranking[0] == "candidate_B"
    # Check normalized
    a_flow_norm = next(
        m
        for m in next(
            s for s in r1.candidate_summaries if s.candidate_id == "candidate_A"
        ).metric_results
        if m.metric_key == "flow.count"
    ).normalized_mae
    assert a_flow_norm == 2.0 / 100.0


def test_objective_scale_required() -> None:
    with pytest.raises(ValidationError):
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=1.0,
            objective_scale=None,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        )
    with pytest.raises(ValidationError):
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=0.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        )
    with pytest.raises(ValidationError):
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=-1.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        )
    # weight 0 may have no scale
    spec = CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        weight=0.0,
        objective_scale=None,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    )
    assert spec.weight == 0.0


def test_scale_changes_fingerprint() -> None:
    obs = make_observed_fixture()
    good = make_candidate_good()
    spec1 = CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        weight=0.5,
        objective_scale=100.0,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    )
    spec2 = CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        weight=0.5,
        objective_scale=200.0,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    )
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    s1 = CalibrationStudy(
        study_id="fp_test",
        study_name="FP",
        observed=obs,
        candidates=[good],
        metric_specs=[spec1],
        alignment_spec=alignment,
    )
    s2 = CalibrationStudy(
        study_id="fp_test",
        study_name="FP",
        observed=obs,
        candidates=[good],
        metric_specs=[spec2],
        alignment_spec=alignment,
    )
    assert s1.canonical_dict() != s2.canonical_dict()
    # Study fingerprint via report will differ
    r1 = build_calibration_report(s1)
    r2 = build_calibration_report(s2)
    assert r1.fingerprint != r2.fingerprint


def test_relative_error_zero_denominator() -> None:
    obs = make_observed_fixture()
    # Create observed with 0.0 for one flow bin
    bins = []
    for b in obs.bins:
        val = (
            0.0
            if b.metric_key == "flow.count" and b.sensor_id == "sensor_A" and b.window_index == 0
            else b.value
        )
        bins.append(
            CalibrationBin(
                sensor_id=b.sensor_id,
                window_index=b.window_index,
                window_start_utc=b.window_start_utc,
                window_end_utc=b.window_end_utc,
                metric_key=b.metric_key,
                value=val,
                unit=b.unit,
            )
        )
    payload = {
        "bins": [
            x.canonical_dict()
            for x in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "observed_id": "obs_zero",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    obs_zero = CalibrationObservedReference(
        observed_id="obs_zero",
        fingerprint=fp,
        evidence_label=obs.evidence_label,
        window_start_utc=obs.window_start_utc,
        window_end_utc=obs.window_end_utc,
        bin_width_s=obs.bin_width_s,
        sensor_ids=obs.sensor_ids,
        metric_units=obs.metric_units,
        bins=bins,
    )
    good = make_candidate_good()
    # candidate value for that bin is 5.0 (non-zero), so relative should be None due to observed 0
    study = CalibrationStudy(
        study_id="zero_denom",
        study_name="Zero Denom",
        observed=obs_zero,
        candidates=[good],
        metric_specs=[
            CalibrationMetricSpec(
                metric_key="flow.count",
                metric_version="1.0",
                unit="veh/h",
                denominator="per_sensor_per_hour",
                weight=0.5,
                objective_scale=100.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
            CalibrationMetricSpec(
                metric_key="traffic.speed.mean_mps",
                metric_version="1.0",
                unit="m/s",
                denominator="per_sensor_per_window",
                weight=0.5,
                objective_scale=5.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
        ],
        alignment_spec=CalibrationAlignmentSpec(
            window_start_utc=synthetic_window_start(),
            window_end_utc=synthetic_window_end(),
            bin_width_s=synthetic_bin_width(),
            window_semantics="[start,end)",
            temporal_tolerance_s=0.0,
            sensor_mapping={},
            coverage_threshold=0.0,
        ),
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    residual = next(
        r
        for r in summary.residuals
        if r.sensor_id == "sensor_A" and r.window_index == 0 and r.metric_key == "flow.count"
    )
    assert residual.relative_error is None
    assert residual.signed_error is not None
    assert residual.absolute_error is not None
    # If all observed denominator zero for metric, relative_error_mean None
    # Create case where all flow observed =0
    bins_all_zero = []
    for b in obs.bins:
        if b.metric_key == "flow.count":
            bins_all_zero.append(
                CalibrationBin(
                    sensor_id=b.sensor_id,
                    window_index=b.window_index,
                    window_start_utc=b.window_start_utc,
                    window_end_utc=b.window_end_utc,
                    metric_key=b.metric_key,
                    value=0.0,
                    unit=b.unit,
                )
            )
        else:
            bins_all_zero.append(b)
    payload2 = {
        "bins": [
            x.canonical_dict()
            for x in sorted(
                bins_all_zero, key=lambda x: (x.sensor_id, x.window_index, x.metric_key)
            )
        ],
        "observed_id": "obs_all_zero",
    }
    fp2 = hashlib.sha256(
        json.dumps(payload2, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    obs_all_zero = CalibrationObservedReference(
        observed_id="obs_all_zero",
        fingerprint=fp2,
        evidence_label=obs.evidence_label,
        window_start_utc=obs.window_start_utc,
        window_end_utc=obs.window_end_utc,
        bin_width_s=obs.bin_width_s,
        sensor_ids=obs.sensor_ids,
        metric_units=obs.metric_units,
        bins=bins_all_zero,
    )
    study2 = CalibrationStudy(
        study_id="zero_all",
        study_name="Zero All",
        observed=obs_all_zero,
        candidates=[good],
        metric_specs=[
            CalibrationMetricSpec(
                metric_key="flow.count",
                metric_version="1.0",
                unit="veh/h",
                denominator="per_sensor_per_hour",
                weight=1.0,
                objective_scale=100.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            )
        ],
        alignment_spec=CalibrationAlignmentSpec(
            window_start_utc=synthetic_window_start(),
            window_end_utc=synthetic_window_end(),
            bin_width_s=synthetic_bin_width(),
            window_semantics="[start,end)",
            temporal_tolerance_s=0.0,
            sensor_mapping={},
            coverage_threshold=0.0,
        ),
    )
    report2 = build_calibration_report(study2)
    flow_res = next(
        m for m in report2.candidate_summaries[0].metric_results if m.metric_key == "flow.count"
    )
    assert flow_res.relative_error_mean is None


def test_duplicate_bins_refused() -> None:
    obs = make_observed_fixture()
    # Duplicate candidate bin
    good = make_candidate_good()
    dup_bins = list(good.bins) + [good.bins[0]]
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(dup_bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_dup",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValidationError):
        CalibrationCandidate(
            candidate_id="candidate_dup",
            fingerprint=fp,
            label="dup",
            window_start_utc=good.window_start_utc,
            window_end_utc=good.window_end_utc,
            bin_width_s=good.bin_width_s,
            sensor_ids=good.sensor_ids,
            metric_units=good.metric_units,
            bins=dup_bins,
        )
    # Duplicate observed
    dup_obs_bins = list(obs.bins) + [obs.bins[0]]
    payload_obs = {
        "bins": [
            b.canonical_dict()
            for b in sorted(dup_obs_bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "observed_id": "obs_dup",
    }
    fp_obs = hashlib.sha256(
        json.dumps(payload_obs, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    with pytest.raises(ValidationError):
        CalibrationObservedReference(
            observed_id="obs_dup",
            fingerprint=fp_obs,
            evidence_label=obs.evidence_label,
            window_start_utc=obs.window_start_utc,
            window_end_utc=obs.window_end_utc,
            bin_width_s=obs.bin_width_s,
            sensor_ids=obs.sensor_ids,
            metric_units=obs.metric_units,
            bins=dup_obs_bins,
        )


def test_sensor_mapping_pairing() -> None:
    obs = make_observed_fixture()
    # Create candidate with mapped sensor link_X for observed sensor_A
    ws = synthetic_window_start()
    we = synthetic_window_end()
    bw = synthetic_bin_width()
    # Observed has sensor_A, sensor_B; mapping sensor_A->link_X, sensor_B->link_Y
    bins = []
    for b in obs.bins:
        # Map sensor_A to link_X, sensor_B to link_Y
        cand_sensor = "link_X" if b.sensor_id == "sensor_A" else "link_Y"
        bins.append(
            CalibrationBin(
                sensor_id=cand_sensor,
                window_index=b.window_index,
                window_start_utc=b.window_start_utc,
                window_end_utc=b.window_end_utc,
                metric_key=b.metric_key,
                value=(b.value or 0) + 1.0,  # small error
                unit=b.unit,
            )
        )
    payload = {
        "bins": [
            x.canonical_dict()
            for x in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_mapped",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand = CalibrationCandidate(
        candidate_id="candidate_mapped",
        fingerprint=fp,
        label="mapped",
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        sensor_ids=["link_X", "link_Y"],
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )
    alignment = CalibrationAlignmentSpec(
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={"sensor_A": "link_X", "sensor_B": "link_Y"},
        coverage_threshold=0.0,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.5,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    study = CalibrationStudy(
        study_id="mapping_test",
        study_name="Mapping Test",
        observed=obs,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.alignment_audit.sensor_mapping_complete is True
    assert summary.coverage_percentage == 100.0
    # Without mapping, coverage would be 0 because sensor names differ; with mapping it is 100
    assert summary.status.value == "available"


def test_residual_export() -> None:
    good = make_candidate_good()
    study = _make_study_with_candidates([good])
    report = build_calibration_report(study)
    csv_text = export_residuals_csv(report)
    reader = csv.DictReader(io.StringIO(csv_text))
    assert reader.fieldnames is not None
    assert "candidate_id" in reader.fieldnames
    assert "signed_error" in reader.fieldnames
    rows = list(reader)
    assert len(rows) == len(report.candidate_summaries[0].residuals)
    j1 = calibration_report_to_json(report)
    j2 = calibration_report_to_json(report)
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["fingerprint"] == report.fingerprint


def test_csv_formula_sanitization() -> None:
    from traffictwin.data_contract.fingerprint import sanitise_for_csv

    _obs = make_observed_fixture()
    # Create candidate with formula-like sensor_id and label that passes validation? Sensor_id validation allows letters numbers _- . Need a sensor_id that is formula-like but passes? Our sensor_id regex allows ^[A-Za-z][A-Za-z0-9_\-]{0,63}$ so =HYPERLINK not allowed. Instead test via label and candidate_id which are less strict? candidate_id also same pattern, not allow =. But metric_key also restricted.  # noqa: E501
    # However CSV sanitization should still be applied for those fields; we can test sanitise_for_csv directly and that export uses it  # noqa: E501
    # Test that sanitise_for_csv prefixes formula
    assert (
        sanitise_for_csv('=HYPERLINK("http://evil","click")')
        == '\'=HYPERLINK("http://evil","click")'
    )
    assert sanitise_for_csv("+cmd|'/C calc'!A0") == "'+cmd|'/C calc'!A0"
    assert sanitise_for_csv("@malicious") == "'@malicious"
    # Now test that export actually sanitizes candidate label with formula-like content
    # Create candidate with label containing formula-like text (label allows many chars)
    good = make_candidate_good()
    formula_label = "=cmd|'/C calc'!A0"
    # Need to create candidate with that label
    cand_formula = CalibrationCandidate(
        candidate_id=good.candidate_id,
        fingerprint=good.fingerprint,
        label=formula_label,
        window_start_utc=good.window_start_utc,
        window_end_utc=good.window_end_utc,
        bin_width_s=good.bin_width_s,
        sensor_ids=good.sensor_ids,
        metric_units=good.metric_units,
        bins=good.bins,
    )
    study = _make_study_with_candidates([cand_formula])
    report = build_calibration_report(study)
    _csv_summary = export_metric_results_csv(report)  # noqa: F841
    # Use candidate summary export which includes label
    from traffictwin.calibration.service import export_candidate_summary_csv

    summary_csv = export_candidate_summary_csv(report)
    # Check that label is sanitized in CSV (prefixed with ')
    assert "'=cmd" in summary_csv or "'=HYPERLINK" in summary_csv or "'=cmd|'/C calc" in summary_csv


def test_evidence_boundary() -> None:
    study = make_three_candidate_study()
    report = build_calibration_report(study)
    assert report.evidence_boundary == EVIDENCE_BOUNDARY
    canon = report.canonical_dict()
    assert canon["evidence_boundary"] == EVIDENCE_BOUNDARY
    assert "Read-only descriptive comparison" in report.evidence_boundary


def test_limitations() -> None:
    study = make_three_candidate_study()
    report = build_calibration_report(study)
    # Check substantive limitations present
    limitations_str = " ".join(report.limitations)
    assert (
        "descriptive fit only" in limitations_str.lower()
        or "Descriptive fit only" in limitations_str
    )
    assert "no parameter tuning" in limitations_str.lower()
    assert "never zero-filled" in limitations_str.lower() or "never zero-filled" in limitations_str
    assert "normalization" in limitations_str.lower()
    assert (
        "not a validated model claim" in limitations_str.lower()
        or "not a validated" in limitations_str.lower()
    )
    assert "No synthetic evidence is relabelled as observed" in limitations_str
    assert "No production-readiness" in limitations_str or "production-readiness" in limitations_str


def test_half_open_window_semantics() -> None:
    obs = make_observed_fixture()
    for sensor in ["sensor_A", "sensor_B"]:
        bins = sorted(
            [b for b in obs.bins if b.sensor_id == sensor and b.metric_key == "flow.count"],
            key=lambda x: x.window_index,
        )
        for i in range(len(bins) - 1):
            assert bins[i].window_end_utc == bins[i + 1].window_start_utc
            assert bins[i].window_end_utc > bins[i].window_start_utc


def test_no_path_wall_clock_in_identity() -> None:
    s = make_three_candidate_study()
    r1 = build_calibration_report(s)
    canon = r1.canonical_dict()
    canon_json = json.dumps(canon, sort_keys=True)
    assert "wall" not in canon_json.lower()
    r2 = build_calibration_report(s)
    assert r1.fingerprint == r2.fingerprint
    assert len(r1.fingerprint) == 64


def test_metric_spec_declares_required_fields() -> None:
    spec = CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        weight=0.6,
        objective_scale=100.0,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    )
    assert spec.metric_key == "flow.count"
    assert spec.unit == "veh/h"
    assert spec.denominator == "per_sensor_per_hour"
    assert spec.weight == 0.6
    assert spec.objective_scale == 100.0


def test_bin_outside_window_refused() -> None:
    obs = make_observed_fixture()
    # Try to create observed with bin outside window
    bad_bin = CalibrationBin(
        sensor_id="sensor_A",
        window_index=99,
        window_start_utc=synthetic_window_start() + timedelta(days=10),
        window_end_utc=synthetic_window_start() + timedelta(days=10, seconds=synthetic_bin_width()),
        metric_key="flow.count",
        value=10.0,
        unit="veh/h",
    )
    with pytest.raises(ValidationError):
        CalibrationObservedReference(
            observed_id="obs_bad",
            fingerprint=obs.fingerprint,
            evidence_label=obs.evidence_label,
            window_start_utc=obs.window_start_utc,
            window_end_utc=obs.window_end_utc,
            bin_width_s=obs.bin_width_s,
            sensor_ids=obs.sensor_ids,
            metric_units=obs.metric_units,
            bins=[bad_bin],
        )


def test_default_study_excludes_missing_evidence_and_ranks_good_fit() -> None:

    study = make_default_study()
    assert study.alignment_spec.coverage_threshold == 1.0
    report = build_calibration_report(study)
    # missing candidate should be excluded due per-metric coverage
    missing = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_missing_evidence"
    )
    assert missing.status.value == "excluded"
    assert missing.exclusion is not None
    assert missing.exclusion.reason_code == "COVERAGE_INSUFFICIENT"
    assert (
        "per-metric" in missing.exclusion.reason_detail.lower()
        or "coverage" in missing.exclusion.reason_detail.lower()
    )
    assert missing.candidate_id not in report.ranking
    # good fit available and ranked first
    good = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    assert good.status.value == "available"
    assert report.ranking[0] == "candidate_good_fit"
    # per-metric flow coverage for missing
    flow_res = next(m for m in missing.metric_results if m.metric_key == "flow.count")
    assert flow_res.count_paired == 1
    # eligible flow is 8 (observed flow non-missing 8)
    assert flow_res.count_paired + flow_res.count_missing_simulation == 8
    assert flow_res.coverage_percentage == 12.5
    # low MAE on paired bin cannot win
    assert flow_res.mae is not None
    assert flow_res.mae < 5.0


def test_per_metric_coverage_gate_enforced() -> None:
    obs = make_observed_fixture()
    # Create candidate with flow 1/8 paired, speed 8/8 -> aggregate 56% but per-metric flow fails threshold 1.0  # noqa: E501
    flow_vals: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 101.0,
        ("sensor_A", 1): None,
        ("sensor_A", 2): None,
        ("sensor_A", 3): None,
        ("sensor_B", 0): None,
        ("sensor_B", 1): None,
        ("sensor_B", 2): None,
        ("sensor_B", 3): None,
    }
    speed_vals = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    from traffictwin.calibration.fixtures import _make_candidate_bins

    bins = _make_candidate_bins(flow_values=flow_vals, speed_values=speed_vals)
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_per_metric_test",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand = CalibrationCandidate(
        candidate_id="candidate_per_metric_test",
        fingerprint=fp,
        label="per-metric test",
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        sensor_ids=["sensor_A", "sensor_B"],
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.5,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=1.0,
    )
    study = CalibrationStudy(
        study_id="per_metric_test",
        study_name="Per Metric Test",
        observed=obs,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.status.value == "excluded"
    assert summary.exclusion is not None
    assert summary.exclusion.reason_code == "COVERAGE_INSUFFICIENT"
    assert (
        "flow.count" in summary.exclusion.reason_detail
        or "coverage" in summary.exclusion.reason_detail.lower()
    )
    assert summary.candidate_id not in report.ranking
    # With threshold 0.0 it would be available
    alignment_low = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    study_low = CalibrationStudy(
        study_id="per_metric_test_low",
        study_name="Per Metric Test Low",
        observed=obs,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=alignment_low,
    )
    report_low = build_calibration_report(study_low)
    assert report_low.candidate_summaries[0].status.value == "available"
    assert report_low.candidate_summaries[0].candidate_id in report_low.ranking


def test_observed_missing_eligibility_and_diagnostic() -> None:
    obs = make_observed_fixture()
    # Make observed with one missing value
    bins_missing_obs: list[CalibrationBin] = []
    for b in obs.bins:
        if b.sensor_id == "sensor_A" and b.window_index == 0 and b.metric_key == "flow.count":
            bins_missing_obs.append(
                CalibrationBin(
                    sensor_id=b.sensor_id,
                    window_index=b.window_index,
                    window_start_utc=b.window_start_utc,
                    window_end_utc=b.window_end_utc,
                    metric_key=b.metric_key,
                    value=None,
                    unit=b.unit,
                )
            )
        else:
            bins_missing_obs.append(b)
    payload = {
        "bins": [
            x.canonical_dict()
            for x in sorted(
                bins_missing_obs, key=lambda x: (x.sensor_id, x.window_index, x.metric_key)
            )
        ],
        "observed_id": "obs_missing_one",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    obs_missing = CalibrationObservedReference(
        observed_id="obs_missing_one",
        fingerprint=fp,
        evidence_label=obs.evidence_label,
        window_start_utc=obs.window_start_utc,
        window_end_utc=obs.window_end_utc,
        bin_width_s=obs.bin_width_s,
        sensor_ids=obs.sensor_ids,
        metric_units=obs.metric_units,
        bins=bins_missing_obs,
    )
    # Candidate with matching missing (absent) for that bin, and good values for rest
    good = make_candidate_good()
    # Remove candidate bin corresponding to missing observed bin as well (make it None too) — but eligible counts 15, paired 15  # noqa: E501
    # Actually candidate still has value for that bin, but observed missing means eligible 15, paired 15 if candidate has other 15  # noqa: E501
    # Create candidate that has all except the missing observed one also missing (so not penalized)
    cand_bins = []
    for b in good.bins:
        if b.sensor_id == "sensor_A" and b.window_index == 0 and b.metric_key == "flow.count":
            # make candidate also missing for that window
            cand_bins.append(
                CalibrationBin(
                    sensor_id=b.sensor_id,
                    window_index=b.window_index,
                    window_start_utc=b.window_start_utc,
                    window_end_utc=b.window_end_utc,
                    metric_key=b.metric_key,
                    value=None,
                    unit=b.unit,
                )
            )
        else:
            cand_bins.append(b)
    payload_cand = {
        "bins": [
            x.canonical_dict()
            for x in sorted(cand_bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_observed_missing_test",
    }
    fp_cand = hashlib.sha256(
        json.dumps(payload_cand, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand = CalibrationCandidate(
        candidate_id="candidate_observed_missing_test",
        fingerprint=fp_cand,
        label="observed missing test",
        window_start_utc=good.window_start_utc,
        window_end_utc=good.window_end_utc,
        bin_width_s=good.bin_width_s,
        sensor_ids=good.sensor_ids,
        metric_units=good.metric_units,
        bins=cand_bins,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.5,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=1.0,
    )
    study = CalibrationStudy(
        study_id="obs_missing_test",
        study_name="Obs Missing Test",
        observed=obs_missing,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    # Eligible is 15 (16-1 missing observed), paired 15 (since candidate missing corresponds to observed missing, not counted as eligible, but other 15 are paired)  # noqa: E501
    # Our candidate has 15 good bins + 1 missing that aligns with observed missing (so not eligible, not paired, but not extra)  # noqa: E501
    # Actually observed missing 1 means total eligible 15, candidate missing for that same key means paired should be 15? Let's assert coverage 100%  # noqa: E501
    assert summary.alignment_audit.coverage_percentage == 100.0
    assert summary.alignment_audit.total_bins == 15
    assert summary.alignment_audit.is_excluded is False
    assert summary.status.value == "available"
    # diagnostic reports missing observed
    flow_res = next(m for m in summary.metric_results if m.metric_key == "flow.count")
    assert flow_res.count_missing_observed == 1
    assert (
        flow_res.count_paired == 7
    )  # flow has 8 originally minus 1 missing observed =7 eligible, all paired
    assert flow_res.coverage_percentage == 100.0


def test_unavailable_positive_weight_alignment_false() -> None:
    obs = make_observed_fixture()
    ws = synthetic_window_start()
    we = synthetic_window_end()
    bw = synthetic_bin_width()
    # Candidate with flow all missing, speed available
    speed_vals: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 12.5,
        ("sensor_A", 1): 13.0,
        ("sensor_A", 2): 12.8,
        ("sensor_A", 3): 12.6,
        ("sensor_B", 0): 11.0,
        ("sensor_B", 1): 11.2,
        ("sensor_B", 2): 11.5,
        ("sensor_B", 3): 11.3,
    }
    bins: list[CalibrationBin] = []
    for sensor in ["sensor_A", "sensor_B"]:
        for idx in range(4):
            start = ws + timedelta(seconds=idx * bw)
            end = start + timedelta(seconds=bw)
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=start,
                    window_end_utc=end,
                    metric_key="flow.count",
                    value=None,
                    unit="veh/h",
                )
            )
            bins.append(
                CalibrationBin(
                    sensor_id=sensor,
                    window_index=idx,
                    window_start_utc=start,
                    window_end_utc=end,
                    metric_key="traffic.speed.mean_mps",
                    value=speed_vals[(sensor, idx)],
                    unit="m/s",
                )
            )
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_flow_unavailable_align_false",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand = CalibrationCandidate(
        candidate_id="candidate_flow_unavailable_align_false",
        fingerprint=fp,
        label="flow unavailable align false",
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        sensor_ids=["sensor_A", "sensor_B"],
        metric_units={"flow.count": "veh/h", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=100.0,
            alignment_required=False,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.5,
            objective_scale=5.0,
            alignment_required=False,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    alignment = CalibrationAlignmentSpec(
        window_start_utc=ws,
        window_end_utc=we,
        bin_width_s=bw,
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={},
        coverage_threshold=0.0,
    )
    study = CalibrationStudy(
        study_id="unavailable_align_false",
        study_name="Unavailable Align False",
        observed=obs,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    # Should be UNAVAILABLE not AVAILABLE, with explicit exclusion
    assert summary.status.value == "unavailable"
    assert summary.exclusion is not None
    assert summary.exclusion.reason_code in ("OBJECTIVE_UNAVAILABLE", "MISSING_REQUIRED_METRIC")
    assert summary.weighted_objective is None
    assert summary.candidate_id not in report.ranking


def test_unit_mismatch_semantic_deduplication() -> None:
    obs = make_observed_fixture()
    # Create candidate with same wrong unit in both metric_units and every bin (veh/min for flow)
    flow_vals: dict[tuple[str, int], float | None] = {
        ("sensor_A", 0): 100.0,
        ("sensor_A", 1): 118.0,
        ("sensor_A", 2): 111.0,
        ("sensor_A", 3): 106.0,
        ("sensor_B", 0): 91.0,
        ("sensor_B", 1): 96.0,
        ("sensor_B", 2): 101.0,
        ("sensor_B", 3): 99.0,
    }
    speed_vals = {
        ("sensor_A", 0): 12.6,
        ("sensor_A", 1): 12.9,
        ("sensor_A", 2): 12.9,
        ("sensor_A", 3): 12.7,
        ("sensor_B", 0): 11.1,
        ("sensor_B", 1): 11.3,
        ("sensor_B", 2): 11.6,
        ("sensor_B", 3): 11.4,
    }
    from traffictwin.calibration.fixtures import _make_candidate_bins

    bins = _make_candidate_bins(flow_values=flow_vals, speed_values=speed_vals, flow_unit="veh/min")
    payload = {
        "bins": [
            b.canonical_dict()
            for b in sorted(bins, key=lambda x: (x.sensor_id, x.window_index, x.metric_key))
        ],
        "candidate_id": "candidate_dedup_test",
    }
    fp = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    cand = CalibrationCandidate(
        candidate_id="candidate_dedup_test",
        fingerprint=fp,
        label="dedup test",
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        sensor_ids=["sensor_A", "sensor_B"],
        metric_units={"flow.count": "veh/min", "traffic.speed.mean_mps": "m/s"},
        bins=bins,
    )
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            weight=0.5,
            objective_scale=100.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            weight=0.5,
            objective_scale=5.0,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
    ]
    study = CalibrationStudy(
        study_id="dedup_test",
        study_name="Dedup Test",
        observed=obs,
        candidates=[cand],
        metric_specs=specs,
        alignment_spec=CalibrationAlignmentSpec(
            window_start_utc=synthetic_window_start(),
            window_end_utc=synthetic_window_end(),
            bin_width_s=synthetic_bin_width(),
            window_semantics="[start,end)",
            temporal_tolerance_s=0.0,
            sensor_mapping={},
            coverage_threshold=0.0,
        ),
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.alignment_audit.unit_compatible is False
    # Should be at most 1 candidate-side message for flow.count, not duplicated per-bin
    flow_candidate_msgs = [
        m for m in summary.alignment_audit.unit_mismatches if "flow.count" in m and "candidate" in m
    ]
    assert len(flow_candidate_msgs) == 1
    # Message should list distinct units
    assert "veh/min" in flow_candidate_msgs[0]
    assert "veh/h" in flow_candidate_msgs[0]
    # No duplicate byte-identical messages
    assert len(summary.alignment_audit.unit_mismatches) == len(
        set(summary.alignment_audit.unit_mismatches)
    )


def test_weighted_mean_documentation_and_formula() -> None:
    study = make_three_candidate_study()
    report = build_calibration_report(study)
    # LIMITATIONS must describe weighted mean
    assert any("weighted mean" in lim.lower() for lim in report.limitations)
    assert any("Σ(weight" in lim or "weighted mean" in lim.lower() for lim in report.limitations)
    # Verify arithmetic: weighted_objective = Σ w·norm / Σ w
    good = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    if good.metric_results:
        # Compute expected
        specs_by_key = {s.metric_key: s for s in study.metric_specs}
        weighted_sum = sum(
            specs_by_key[m.metric_key].weight * m.normalized_mae
            for m in good.metric_results
            if m.normalized_mae is not None and specs_by_key[m.metric_key].weight > 0
        )
        total_w_float = sum(
            float(specs_by_key[m.metric_key].weight)
            for m in good.metric_results
            if specs_by_key[m.metric_key].weight > 0
        )
        expected = weighted_sum / total_w_float if total_w_float else None
        assert good.weighted_objective == expected


def test_default_study_weight_cannot_resurrect_missing() -> None:

    # Test both weight regimes: flow-heavy and speed-heavy, missing should never be in ranking
    obs = make_observed_fixture()
    missing = make_candidate_missing()
    good = make_candidate_good()
    poor = make_candidate_poor()
    for w_flow, w_speed in [(0.9, 0.1), (0.1, 0.9)]:
        specs = [
            CalibrationMetricSpec(
                metric_key="flow.count",
                metric_version="1.0",
                unit="veh/h",
                denominator="per_sensor_per_hour",
                weight=w_flow,
                objective_scale=100.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
            CalibrationMetricSpec(
                metric_key="traffic.speed.mean_mps",
                metric_version="1.0",
                unit="m/s",
                denominator="per_sensor_per_window",
                weight=w_speed,
                objective_scale=5.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            ),
        ]
        alignment = CalibrationAlignmentSpec(
            window_start_utc=synthetic_window_start(),
            window_end_utc=synthetic_window_end(),
            bin_width_s=synthetic_bin_width(),
            window_semantics="[start,end)",
            temporal_tolerance_s=0.0,
            sensor_mapping={},
            coverage_threshold=1.0,
        )
        study = CalibrationStudy(
            study_id=f"weight_resurrect_{str(w_flow).replace('.', '_')}",
            study_name="Weight Resurrect",
            observed=obs,
            candidates=[good, poor, missing],
            metric_specs=specs,
            alignment_spec=alignment,
        )
        report = build_calibration_report(study)
        assert "candidate_missing_evidence" not in report.ranking
        assert report.ranking[0] in ("candidate_good_fit", "candidate_poor_fit")

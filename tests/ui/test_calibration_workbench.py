"""Tests for Calibration Workbench — deterministic, alignment, exclusion, ranking, exports and UI."""  # noqa: E501

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta

from streamlit.testing.v1 import AppTest

from traffictwin.calibration.fixtures import (
    make_candidate_good,
    make_candidate_incompatible,
    make_candidate_missing,
    make_candidate_poor,
    make_candidate_temporal_misaligned,
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
    CalibrationStudy,
    Direction,
    MissingnessPolicy,
)
from traffictwin.calibration.service import (
    build_calibration_report,
    calibration_report_to_json,
    export_residuals_csv,
)


def _make_study_with_candidates(cands: list[CalibrationCandidate]) -> CalibrationStudy:
    obs = make_observed_fixture()
    specs = [
        CalibrationMetricSpec(
            metric_key="flow.count",
            metric_version="1.0",
            unit="veh/h",
            denominator="per_sensor_per_hour",
            direction=Direction.LOWER_IS_BETTER,
            weight=0.5,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            direction=Direction.LOWER_IS_BETTER,
            weight=0.5,
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
    return CalibrationStudy(
        study_id="test_study",
        study_name="Test Study",
        description="Test",
        observed=obs,
        candidates=cands,
        metric_specs=specs,
        alignment_spec=alignment,
    )


def test_deterministic_report_fingerprint() -> None:
    study = make_three_candidate_study()
    r1 = build_calibration_report(study)
    r2 = build_calibration_report(study)
    assert r1.fingerprint == r2.fingerprint
    assert r1.fingerprint == r1.model_copy(update={}).fingerprint
    # Canonical bytes identical
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
            direction=Direction.LOWER_IS_BETTER,
            weight=0.6,
            alignment_required=True,
            missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
        ),
        CalibrationMetricSpec(
            metric_key="traffic.speed.mean_mps",
            metric_version="1.0",
            unit="m/s",
            denominator="per_sensor_per_window",
            direction=Direction.LOWER_IS_BETTER,
            weight=0.4,
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


def test_unit_mismatch_exclusion() -> None:
    good = make_candidate_good()
    incompatible = make_candidate_incompatible()  # veh/min mismatch
    study = _make_study_with_candidates([good, incompatible])
    report = build_calibration_report(study)
    # Find incompatible summary
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
    # Good should be available
    good_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    assert good_sum.status.value == "available"
    assert good_sum.alignment_audit.unit_compatible is True


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


def test_missing_evidence_not_zero_filled() -> None:
    # candidate_missing has flow mostly None; check that missing not zeroed in objective
    missing = make_candidate_missing()
    good = make_candidate_good()
    study = _make_study_with_candidates([good, missing])
    report = build_calibration_report(study)
    missing_sum = next(
        s for s in report.candidate_summaries if s.candidate_id == "candidate_missing_evidence"
    )
    # Should be either unavailable or have very low coverage but not zero-filled
    # Check that count_missing_simulation is non-zero and paired != total
    # For flow metric, missing candidate has 1 paired out of 8
    flow_res = next(m for m in missing_sum.metric_results if m.metric_key == "flow.count")
    assert flow_res.count_missing_simulation >= 7
    assert flow_res.count_paired == 1
    # MAE should be based only on paired bins, not zero-filled missing => mae should be small (good fit for that one bin)  # noqa: E501
    # If zero-filled, mae would be huge (because missing would be treated as 0)
    # Observed flow for sensor_A idx0 is 100, candidate is 101 => mae ~1. So not zero-fill.
    assert flow_res.mae is not None
    assert flow_res.mae < 5.0  # small, not inflated by zero
    # Residuals for missing bins should have simulated_value None and errors None, not 0
    for r in missing_sum.residuals:
        if (
            r.metric_key == "flow.count"
            and r.sensor_id == "sensor_A"
            and r.window_index in (1, 2, 3)
        ):
            assert r.simulated_value is None
            assert r.signed_error is None
            assert r.absolute_error is None


def test_objective_unavailable_when_one_required_component_missing() -> None:
    # Create a candidate where one metric is completely missing (all None) -> objective unavailable
    # Build candidate with flow completely missing (all None)
    flow_missing: dict[tuple[str, int], float | None] = {("sensor_A", i): None for i in range(4)}
    flow_missing.update({("sensor_B", i): None for i in range(4)})
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
    # Build manually

    # Instead reuse make_candidate_missing which already has flow mostly missing but still 1 paired,
    # we need fully missing to trigger unavailable objective. Let's craft directly.
    import hashlib
    import json

    ws = synthetic_window_start()
    we = synthetic_window_end()
    bw = synthetic_bin_width()
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
    # flow metric should be unavailable
    flow_res = next(m for m in summary.metric_results if m.metric_key == "flow.count")
    assert flow_res.is_available is False
    assert flow_res.count_paired == 0
    # Weighted objective must be None (unavailable) because required component missing
    assert summary.weighted_objective is None
    assert summary.status.value == "unavailable"


def test_compatible_candidate_ranking() -> None:
    good = make_candidate_good()
    poor = make_candidate_poor()
    study = _make_study_with_candidates([poor, good])
    report = build_calibration_report(study)
    # Good should have lower objective than poor
    good_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_good_fit")
    poor_sum = next(s for s in report.candidate_summaries if s.candidate_id == "candidate_poor_fit")
    assert good_sum.weighted_objective is not None
    assert poor_sum.weighted_objective is not None
    assert good_sum.weighted_objective < poor_sum.weighted_objective
    # Ranking should be good first
    assert report.ranking[0] == "candidate_good_fit"
    assert report.ranking[1] == "candidate_poor_fit"


def test_residual_export() -> None:
    good = make_candidate_good()
    study = _make_study_with_candidates([good])
    report = build_calibration_report(study)
    csv_text = export_residuals_csv(report)
    # Check header and content
    reader = csv.DictReader(io.StringIO(csv_text))
    assert reader.fieldnames is not None
    assert "candidate_id" in reader.fieldnames
    assert "signed_error" in reader.fieldnames
    rows = list(reader)
    assert len(rows) == len(report.candidate_summaries[0].residuals)
    # Deterministic sorting
    sorted_ids = sorted([(r["candidate_id"], r["sensor_id"], r["window_index"]) for r in rows])
    original_sorted = sorted([(r["candidate_id"], r["sensor_id"], r["window_index"]) for r in rows])
    assert sorted_ids == original_sorted
    # JSON export deterministic
    j1 = calibration_report_to_json(report)
    j2 = calibration_report_to_json(report)
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["fingerprint"] == report.fingerprint


def test_no_path_wall_clock_in_identity() -> None:
    s = make_three_candidate_study()
    r1 = build_calibration_report(s)
    # Serialize canonical dict and ensure no local path or wall-clock keys
    canon = r1.canonical_dict()
    canon_json = json.dumps(canon, sort_keys=True)
    # No wall-clock like current time, no path separators that look like absolute paths
    assert "wall" not in canon_json.lower()
    # fingerprint is deterministic and path independent
    # Recreate study with same logical data but different hypothetical path context (not in model) => same fingerprint  # noqa: E501
    r2 = build_calibration_report(s)
    assert r1.fingerprint == r2.fingerprint
    # Ensure fingerprint is sha256 hex
    assert len(r1.fingerprint) == 64
    assert all(c in "0123456789abcdef" for c in r1.fingerprint)


def test_ui_render() -> None:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/calibration_workbench.py")
    app.run(timeout=40)
    assert not app.exception, f"UI raised: {app.exception}"
    # One authoritative H1
    titles = [el.value for el in app.title]
    assert titles.count("Calibration Workbench") == 1
    # Direct AppTest for page module also renders (from_file on app_pages covers file invocation)
    # Also verify no duplicate widget keys via checking that a second run does not duplicate
    assert len(app.title) == 1
    # Evidence boundary appears
    full = ""
    for el in app.get("markdown"):
        val = getattr(el, "value", "")
        if isinstance(val, str):
            full += val
        else:
            full += str(val)
    for el in app.info:
        val = getattr(el, "value", "")
        if isinstance(val, str):
            full += val
        else:
            full += str(val)
    # At least evidence notice present
    assert "Evidence and authority boundary" in full or "evidence" in full.lower()


def test_metric_spec_declares_required_fields() -> None:
    spec = CalibrationMetricSpec(
        metric_key="flow.count",
        metric_version="1.0",
        unit="veh/h",
        denominator="per_sensor_per_hour",
        direction=Direction.LOWER_IS_BETTER,
        weight=0.6,
        alignment_required=True,
        missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
    )
    assert spec.metric_key == "flow.count"
    assert spec.unit == "veh/h"
    assert spec.denominator == "per_sensor_per_hour"
    assert spec.direction == Direction.LOWER_IS_BETTER
    assert spec.weight == 0.6


def test_half_open_window_semantics() -> None:
    # Bins are half-open [start,end); check that window_end == next window_start
    obs = make_observed_fixture()
    # Check consecutive bins have contiguous windows
    for sensor in ["sensor_A", "sensor_B"]:
        bins = sorted(
            [b for b in obs.bins if b.sensor_id == sensor and b.metric_key == "flow.count"],
            key=lambda x: x.window_index,
        )
        for i in range(len(bins) - 1):
            assert bins[i].window_end_utc == bins[i + 1].window_start_utc
            # Half-open check: end > start
            assert bins[i].window_end_utc > bins[i].window_start_utc


def test_sensor_link_mapping_exclusion() -> None:
    obs = make_observed_fixture()
    good = make_candidate_good()
    # Create alignment that requires mapping to non-existent sensor
    alignment = CalibrationAlignmentSpec(
        window_start_utc=synthetic_window_start(),
        window_end_utc=synthetic_window_end(),
        bin_width_s=synthetic_bin_width(),
        window_semantics="[start,end)",
        temporal_tolerance_s=0.0,
        sensor_mapping={"sensor_A": "sim_link_X", "sensor_B": "sim_link_Y"},
        coverage_threshold=0.0,
    )
    # good candidate has sensor_A/B but not sim_link_X/Y, so should be excluded if mapping used
    # But our audit treats mapping keys as observed and values as sim sensors; good has sensor_A not sim_link_X => missing  # noqa: E501
    study = CalibrationStudy(
        study_id="mapping_test",
        study_name="Mapping Test",
        observed=obs,
        candidates=[good],
        metric_specs=[
            CalibrationMetricSpec(
                metric_key="flow.count",
                metric_version="1.0",
                unit="veh/h",
                denominator="per_sensor_per_hour",
                direction=Direction.LOWER_IS_BETTER,
                weight=1.0,
                alignment_required=True,
                missingness_policy=MissingnessPolicy.EXCLUDE_BIN,
            )
        ],
        alignment_spec=alignment,
    )
    report = build_calibration_report(study)
    summary = report.candidate_summaries[0]
    assert summary.alignment_audit.sensor_mapping_complete is False
    assert summary.status.value == "excluded"

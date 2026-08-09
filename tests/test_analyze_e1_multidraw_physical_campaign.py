from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scripts.analyze_e1_multidraw_physical_campaign import _delta, _metrics, _paired_summary


def test_paired_summary_uses_fleet_draws_and_t_interval() -> None:
    report = _paired_summary([0.01, 0.02, 0.03, 0.04, 0.05])
    assert report["n_fleet_draws"] == 5
    assert math.isclose(report["mean"], 0.03)
    assert report["sample_standard_deviation"] > 0.0
    assert report["confidence_interval"]["degrees_of_freedom"] == 4
    assert report["confidence_interval"]["excludes_zero"] is True
    assert report["decision"] == "evidence_of_directional_difference_within_five_draw_bounded_study"
    assert report["formal_equivalence_or_noninferiority_claim_supported"] is False


def test_zero_crossing_interval_is_inconclusive_not_equivalent() -> None:
    report = _paired_summary([-0.02, -0.01, 0.0, 0.01, 0.02])
    assert report["confidence_interval"]["excludes_zero"] is False
    assert report["decision"] == "inconclusive_at_this_replication_size"
    assert report["formal_equivalence_or_noninferiority_claim_supported"] is False


def test_delta_uses_higher_minus_lower_orientation() -> None:
    low = {
        "deadline_attainment_offered": 0.60,
        "deadline_attainment_admitted": 0.70,
        "admitted_tasks": 80,
        "rejected_or_unavailable_tasks": 20,
        "rejection_counts": {"v2i_cap_rejected": 10},
        "penalty_inclusive_latency_ms_per_offered_task": 1000.0,
        "latency_ms_per_admitted_task": 100.0,
    }
    high = {
        "deadline_attainment_offered": 0.65,
        "deadline_attainment_admitted": 0.69,
        "admitted_tasks": 90,
        "rejected_or_unavailable_tasks": 10,
        "rejection_counts": {"v2i_cap_rejected": 2},
        "penalty_inclusive_latency_ms_per_offered_task": 2000.0,
        "latency_ms_per_admitted_task": 300.0,
    }
    result = _delta(high, low)
    assert math.isclose(result["deadline_attainment_offered"], 0.05)
    assert result["admitted_tasks"] == 10.0
    assert result["v2i_cap_rejected"] == -8.0


def test_metrics_uses_observed_wall_time_excluded_from_repeat_summary(tmp_path: Path) -> None:
    np.savez(
        tmp_path / "per_task.npz",
        task_active=np.array([True, True]),
        task_outcome=np.array([1, 2]),
        task_lat_ms=np.array([10.0, 20.0]),
    )
    scientific_summary = {
        "rsu_max_concurrent": 6220,
        "n_offered": 2,
        "n_admitted": 2,
        "v2i_gate_rejected": 0,
        "v2i_cap_rejected": 0,
        "local_mqd_rejected": 0,
        "v2v_mqd_rejected": 0,
        "v2i_unavailable": 0,
        "v2v_unavailable": 0,
        "completion": 0.5,
        "completion_admitted": 0.5,
        "avg_latency_ms_per_task": 15.0,
        "avg_latency_admitted_ms": 15.0,
        "avg_latency_met_ms": 10.0,
        "t1_completion": 0.5,
        "t2_completion": 0.0,
        "t3_completion": 0.0,
        "p_local": 0.5,
        "p_v2i": 0.5,
        "p_v2v": 0.0,
        "work_ms": {},
    }
    validation = {
        "scientific_summary": scientific_summary,
        "observed": {
            "deadline_met": 1,
            "wall_s_excluded_from_repeat_verdict": 12.75,
        },
    }

    result = _metrics(tmp_path, validation)

    assert result["wall_s"] == 12.75

"""Synthetic admission and refusal tests for VEC-09."""

from __future__ import annotations

import gzip
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest

from tests.tos_v2_helpers import (
    V2_SCENARIO,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_trace,
    build_v2_tripinfo_records,
)
from traffictwin.integration.vec_identity import (
    VecIdentitySnapshot,
    build_vehicle_identity_snapshot,
)
from traffictwin.integration.vec_science import (
    VecMetricAdmissionStatus,
    VecRuleReadinessStatus,
    VecScientificAdmissionError,
    VecScientificAdmissionReport,
    build_vec_scientific_admission,
    vec_scientific_admission_contract,
)
from traffictwin.integration.vec_task_join import VecTaskJoinReport, build_task_join_report
from traffictwin.integration.vec_trip_join import VecTripJoinReport, build_trip_join_dataset
from traffictwin.metrics.results import MetricStatus

NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
REPRODUCTION_FINGERPRINT = "a" * 64


def _inputs() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    VecIdentitySnapshot,
    VecTaskJoinReport,
    VecTripJoinReport,
]:
    trace = build_v2_trace()
    perstep = build_v2_perstep()
    pertask = build_v2_pertask()
    header, rows = build_v2_occupancy_rows()
    identity = build_vehicle_identity_snapshot(trace, header, rows, scenario=V2_SCENARIO)
    task_report = build_task_join_report(
        trace, perstep, pertask, identity, run_label="synthetic_science"
    )
    xml_rows = "".join(
        (
            f'<tripinfo id="{item["id"]}" depart="{item["depart"]}" '
            f'arrival="{item["arrival"]}" duration="{item["duration"]}" '
            f'routeLength="{item["routeLength"]}"/>'
        )
        for item in build_v2_tripinfo_records()
    )
    trip = build_trip_join_dataset(
        trace,
        identity,
        gzip.compress(f"<tripinfos>{xml_rows}</tripinfos>".encode(), mtime=0),
        source_path="tripinfo/synthetic.xml.gz",
    ).report
    return trace, perstep, pertask, identity, task_report, trip


def _admission() -> VecScientificAdmissionReport:
    trace, perstep, pertask, identity, task_report, trip = _inputs()
    return build_vec_scientific_admission(
        trace,
        perstep,
        pertask,
        identity,
        task_report,
        reproduction_report_fingerprint=REPRODUCTION_FINGERPRINT,
        reproduction_grade="numerically_equivalent",
        computed_at=NOW,
        trip_report=trip,
    )


def test_admits_only_compatible_existing_and_source_specific_metrics() -> None:
    report = _admission()
    metrics = report.evidence_pack.metric_collection.by_key()

    assert metrics["task.generated.count"].value == 7
    assert metrics["task.latency.mean_ms"].value == pytest.approx(70.0)
    assert metrics["tos.task.deadline_success.rate"].value == pytest.approx(5 / 7)
    assert metrics["task.offload.rate"].value == pytest.approx(4 / 7)
    assert metrics["trip.duration.mean_s"].value == pytest.approx(2.7)
    assert metrics["task.completion.rate"].status is MetricStatus.UNAVAILABLE
    assert metrics["task.energy.per_completed_j"].status is MetricStatus.UNAVAILABLE
    decisions = {item.metric_key: item for item in report.metric_decisions}
    assert decisions["task.latency.mean_ms"].status is VecMetricAdmissionStatus.ADMITTED_EXISTING
    assert (
        decisions["tos.task.deadline_success.rate"].status
        is VecMetricAdmissionStatus.ADMITTED_SOURCE_SPECIFIC
    )
    assert report.thresholds_calibrated_on_evaluation is False


def test_rule_readiness_does_not_emit_findings_or_evaluate_thresholds() -> None:
    readiness = {item.rule_id: item for item in _admission().rule_readiness}

    assert readiness["R1"].status is VecRuleReadinessStatus.BLOCKED
    assert readiness["R2"].status is VecRuleReadinessStatus.BLOCKED
    assert readiness["R6"].status is VecRuleReadinessStatus.CONDITIONAL
    assert readiness["R7"].status is VecRuleReadinessStatus.BLOCKED
    assert all(item.threshold_evaluated is False for item in readiness.values())
    assert all(item.finding_emitted is False for item in readiness.values())


def test_slot_tier_metric_stays_operational_and_not_fairness() -> None:
    metrics = _admission().evidence_pack.metric_collection.by_key()
    source = metrics["tos.task.deadline_success.rate_by_slot_tier"]
    canonical = metrics["fairness.vehicle_tier.completion_rate.max_gap"]

    assert source.status is MetricStatus.AVAILABLE
    assert source.metadata["attribute_interpretation"] == (
        "operational_slot_assignment_not_protected_attribute"
    )
    assert canonical.status is MetricStatus.UNAVAILABLE


def test_contract_keeps_forbidden_families_unavailable() -> None:
    contract = vec_scientific_admission_contract()
    assert "per-task energy and energy-delay product" in contract.mandatory_unavailable_families
    assert "task.completion.rate" not in contract.admitted_existing_metrics
    assert contract.fingerprint() == vec_scientific_admission_contract().fingerprint()


def test_reproduction_or_task_evidence_mismatch_fails_closed() -> None:
    trace, perstep, pertask, identity, task_report, trip = _inputs()
    with pytest.raises(VecScientificAdmissionError, match="numerical equivalence"):
        build_vec_scientific_admission(
            trace,
            perstep,
            pertask,
            identity,
            task_report,
            reproduction_report_fingerprint=REPRODUCTION_FINGERPRINT,
            reproduction_grade="mismatch",
            computed_at=NOW,
            trip_report=trip,
        )
    changed = build_v2_perstep()
    changed["veh_queue_ms"] = np.asarray(changed["veh_queue_ms"]).copy()
    changed["veh_queue_ms"][0, 0] = np.float32(1.0)
    with pytest.raises(VecScientificAdmissionError, match="does not match"):
        build_vec_scientific_admission(
            trace,
            changed,
            pertask,
            identity,
            task_report,
            reproduction_report_fingerprint=REPRODUCTION_FINGERPRINT,
            reproduction_grade="numerically_equivalent",
            computed_at=NOW,
            trip_report=trip,
        )

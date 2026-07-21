"""Tests for the observed VEC-02 contract v2, golden fixtures, and negatives.

All fixture values are synthetic. The schemas and semantics under test come
from the accepted VEC-01 audit record, not from Randy's data.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from tests.tos_v2_helpers import (
    V2_MAX_N,
    V2_RSU_COUNT,
    V2_SCENARIO,
    V2_T,
    build_v2_occupancy_rows,
    build_v2_perstep,
    build_v2_pertask,
    build_v2_run_summary,
    build_v2_trace,
    build_v2_tripinfo_records,
    write_v2_package,
)
from traffictwin.domain.enums import Decision, TaskClass
from traffictwin.integration.tos.contract_v2 import (
    OCCUPANCY_HEADER,
    PERSTEP_KEYS,
    PERTASK_KEYS,
    TOS_DATA_AUDITED_COMMIT,
    VEC_ENV_AUDITED_COMMIT,
    OccupancySpan,
    TripJoinEligibility,
    V2FindingCode,
    VecTaskActionObservation,
    VecTripJoin,
    VecVehicleAttributeObservation,
    parse_occupancy_rows,
    reconcile_occupancy_spans,
    tos_source_contract_v2,
    validate_perstep_arrays,
    validate_pertask_arrays,
    validate_trace_arrays,
)


def codes(report: object) -> list[V2FindingCode]:
    return [finding.code for finding in report.findings]  # type: ignore[attr-defined]


def golden_spans() -> list[OccupancySpan]:
    header, rows = build_v2_occupancy_rows()
    spans, findings = parse_occupancy_rows(header, rows, V2_SCENARIO)
    assert findings == []
    return spans


# --- observed contract ---------------------------------------------------


def test_contract_pins_audited_commits_and_stays_fail_closed() -> None:
    contract = tos_source_contract_v2()

    assert contract.vec_env_commit == VEC_ENV_AUDITED_COMMIT
    assert contract.tos_data_commit == TOS_DATA_AUDITED_COMMIT
    assert contract.evidence_state == "audited"
    assert not any(contract.capabilities.values())
    arrays_by_artifact: dict[str, set[str]] = {}
    for item in contract.arrays:
        arrays_by_artifact.setdefault(item.artifact, set()).add(item.name)
    assert arrays_by_artifact["traces/trace_*.npz"] == {
        "T",
        "dt",
        "mask",
        "maxN",
        "pos_x",
        "pos_y",
        "rsu_xy",
        "speed",
        "sumo_seed",
        "times",
        "window",
    }
    assert arrays_by_artifact["instrumented/perstep/*_perstep.npz"] == set(PERSTEP_KEYS)
    assert arrays_by_artifact["instrumented/pertask/*_pertask.npz"] == set(PERTASK_KEYS)
    assert {item.audit_blocker_id for item in contract.unavailable_fields} == {
        "per_task_energy_absent",
        "eventual_physical_completion_absent",
        "action_is_not_transfer_proof",
    }
    assert contract.fingerprint() == tos_source_contract_v2().fingerprint()


def test_contract_cannot_enable_capabilities_or_drop_unavailable_fields() -> None:
    contract = tos_source_contract_v2()
    payload = contract.model_dump(mode="json")

    payload["capabilities"]["direct_launch"] = True
    with pytest.raises(ValidationError, match="cannot enable capabilities"):
        type(contract).model_validate(payload)

    payload["capabilities"]["direct_launch"] = False
    payload["unavailable_fields"] = [
        item for item in payload["unavailable_fields"] if item["name"] != "per_task_energy_j"
    ]
    with pytest.raises(ValidationError, match="per_task_energy_j"):
        type(contract).model_validate(payload)


def test_contract_rejects_extra_fields() -> None:
    payload = tos_source_contract_v2().model_dump(mode="json")
    payload["surprise"] = True
    with pytest.raises(ValidationError, match="surprise"):
        type(tos_source_contract_v2()).model_validate(payload)


# --- golden fixtures -----------------------------------------------------


def test_golden_trace_perstep_pertask_and_occupancy_accepted() -> None:
    trace = build_v2_trace()
    perstep = build_v2_perstep()
    pertask = build_v2_pertask()

    assert validate_trace_arrays(trace).status == "accepted"
    perstep_report = validate_perstep_arrays(perstep, trace, build_v2_run_summary())
    assert perstep_report.findings == []
    assert validate_pertask_arrays(pertask, trace).status == "accepted"

    report = reconcile_occupancy_spans(
        golden_spans(),
        t_count=V2_T,
        max_n=V2_MAX_N,
        mask_true_count=int(np.asarray(trace["mask"]).sum()),
    )
    assert report.status == "accepted"
    assert report.inclusive_visit_seconds == 12
    assert report.distinct_vehicles == 3


def test_golden_package_round_trips_through_disk(tmp_path: Path) -> None:
    root = write_v2_package(tmp_path / "v2")

    with np.load(root / f"traces/trace_{V2_SCENARIO}_synthetic.npz") as trace:
        trace_arrays = {key: trace[key] for key in trace.files}
    with np.load(
        root / f"instrumented/perstep/baseline_synthetic_{V2_SCENARIO}_fs0_perstep.npz"
    ) as perstep:
        perstep_arrays = {key: perstep[key] for key in perstep.files}
    with np.load(
        root / f"instrumented/pertask/baseline_synthetic_{V2_SCENARIO}_fs0_pertask.npz"
    ) as pertask:
        pertask_arrays = {key: pertask[key] for key in pertask.files}

    assert set(perstep_arrays) == set(PERSTEP_KEYS)
    assert set(pertask_arrays) == set(PERTASK_KEYS)
    assert validate_trace_arrays(trace_arrays).status == "accepted"
    assert (
        validate_perstep_arrays(perstep_arrays, trace_arrays, build_v2_run_summary()).status
        == "accepted"
    )
    assert validate_pertask_arrays(pertask_arrays, trace_arrays).status == "accepted"


def test_validation_reports_are_deterministic() -> None:
    trace = build_v2_trace()
    first = validate_perstep_arrays(build_v2_perstep(), trace, build_v2_run_summary())
    second = validate_perstep_arrays(build_v2_perstep(), trace, build_v2_run_summary())
    assert first.fingerprint() == second.fingerprint()


# --- perstep negatives ---------------------------------------------------


def test_perstep_missing_key_rejected() -> None:
    perstep = build_v2_perstep()
    del perstep["veh_k"]
    report = validate_perstep_arrays(perstep, build_v2_trace())
    assert codes(report) == [V2FindingCode.MISSING_KEYS]


def test_perstep_energy_and_completion_keys_get_explicit_refusals() -> None:
    perstep = build_v2_perstep()
    perstep["task_energy_j"] = np.zeros(V2_T)
    perstep["eventual_physical_completion"] = np.zeros(V2_T)
    perstep["mystery"] = np.zeros(V2_T)
    report = validate_perstep_arrays(perstep, build_v2_trace())

    assert V2FindingCode.ENERGY_FIELD_NOT_IN_CONTRACT in codes(report)
    assert V2FindingCode.COMPLETION_FIELD_NOT_IN_CONTRACT in codes(report)
    assert V2FindingCode.UNEXPECTED_KEYS in codes(report)
    energy = next(
        finding
        for finding in report.findings
        if finding.code is V2FindingCode.ENERGY_FIELD_NOT_IN_CONTRACT
    )
    assert "per_task_energy_absent" in energy.detail


@pytest.mark.parametrize(
    ("mutate_key", "value_position", "value", "expected"),
    [
        ("veh_action", (0, 0), 3, V2FindingCode.VALUE_RANGE_INVALID),
        ("veh_k", (0, 0), 6, V2FindingCode.VALUE_RANGE_INVALID),
        ("veh_done", (2, 2), 1, V2FindingCode.VALUE_RANGE_INVALID),
        ("veh_queue_ms", (0, 0), -1.0, V2FindingCode.VALUE_RANGE_INVALID),
        ("slot_tier", (0,), 3, V2FindingCode.TIER_RANGE_INVALID),
        ("veh_best_rsu", (0, 1), V2_RSU_COUNT, V2FindingCode.TARGET_RANGE_INVALID),
        ("veh_best_v2v", (1, 0), V2_MAX_N, V2FindingCode.TARGET_RANGE_INVALID),
    ],
)
def test_perstep_range_violations_rejected(
    mutate_key: str,
    value_position: tuple[int, ...],
    value: float,
    expected: V2FindingCode,
) -> None:
    perstep = build_v2_perstep()
    perstep[mutate_key] = np.array(perstep[mutate_key])
    perstep[mutate_key][value_position] = value
    report = validate_perstep_arrays(perstep, build_v2_trace())
    assert expected in codes(report)


def test_perstep_self_v2v_target_rejected() -> None:
    perstep = build_v2_perstep()
    perstep["veh_best_v2v"] = np.array(perstep["veh_best_v2v"])
    perstep["veh_best_v2v"][2, 1] = 1
    report = validate_perstep_arrays(perstep, build_v2_trace())
    assert V2FindingCode.SELF_V2V_TARGET in codes(report)


def test_perstep_time_grid_and_mask_reconciliation() -> None:
    trace = build_v2_trace()

    shifted = build_v2_perstep()
    shifted["times"] = np.asarray(shifted["times"]) + 1.0
    assert V2FindingCode.TIME_GRID_INVALID in codes(validate_perstep_arrays(shifted, trace))

    wrong_active = build_v2_perstep()
    wrong_active["active"] = np.asarray(wrong_active["active"]) + 1
    assert V2FindingCode.ACTIVE_MASK_MISMATCH in codes(validate_perstep_arrays(wrong_active, trace))


def test_perstep_internal_count_inconsistency_rejected() -> None:
    perstep = build_v2_perstep()
    perstep["done"] = np.array(perstep["done"])
    perstep["done"][0] += 1
    report = validate_perstep_arrays(perstep, build_v2_trace())
    assert V2FindingCode.INTERNAL_COUNTS_INCONSISTENT in codes(report)


def test_perstep_wrong_shape_rejected() -> None:
    perstep = build_v2_perstep()
    perstep["rsu_load"] = np.zeros((V2_T, V2_RSU_COUNT + 1), dtype=np.int32)
    report = validate_perstep_arrays(perstep, build_v2_trace())
    assert codes(report) == [V2FindingCode.SHAPE_MISMATCH]


def test_perstep_requires_every_exact_audited_dtype() -> None:
    perstep = build_v2_perstep()
    perstep["veh_action"] = np.asarray(perstep["veh_action"], dtype=np.int64)
    perstep["lat_sum"] = np.asarray(perstep["lat_sum"], dtype=np.float64)

    report = validate_perstep_arrays(perstep, build_v2_trace())

    assert codes(report) == [V2FindingCode.DTYPE_MISMATCH, V2FindingCode.DTYPE_MISMATCH]


def test_run_summary_mismatches_rejected() -> None:
    trace = build_v2_trace()

    wrong_completion = build_v2_run_summary()
    wrong_completion["completion"] = 0.99
    assert V2FindingCode.AGGREGATE_MISMATCH in codes(
        validate_perstep_arrays(build_v2_perstep(), trace, wrong_completion)
    )

    wrong_hist = build_v2_run_summary()
    wrong_hist["fleet_tier_hist"] = [3, 0, 0]
    assert V2FindingCode.TIER_HIST_INVALID in codes(
        validate_perstep_arrays(build_v2_perstep(), trace, wrong_hist)
    )

    broken_shares = build_v2_run_summary()
    broken_shares["p_local"] = 0.9
    report = validate_perstep_arrays(build_v2_perstep(), trace, broken_shares)
    assert V2FindingCode.SHARE_SUM_INVALID in codes(report)
    assert V2FindingCode.AGGREGATE_MISMATCH in codes(report)


def test_run_summary_accepts_only_float32_rounding_for_ev_share() -> None:
    trace = build_v2_trace()
    rounded = build_v2_run_summary()
    rounded["fleet_ev_share"] = float(rounded["fleet_ev_share"]) + 5e-8
    assert validate_perstep_arrays(build_v2_perstep(), trace, rounded).status == "accepted"

    wrong = build_v2_run_summary()
    wrong["fleet_ev_share"] = float(wrong["fleet_ev_share"]) + 1e-4
    assert V2FindingCode.AGGREGATE_MISMATCH in codes(
        validate_perstep_arrays(build_v2_perstep(), trace, wrong)
    )


# --- trace negatives -----------------------------------------------------


def test_trace_dt_and_time_grid_enforced() -> None:
    wrong_dt = build_v2_trace()
    wrong_dt["dt"] = np.float32(0.5)
    assert V2FindingCode.TIME_GRID_INVALID in codes(validate_trace_arrays(wrong_dt))

    gap = build_v2_trace()
    gap["times"] = np.array(gap["times"])
    gap["times"][3] += 0.5
    assert V2FindingCode.TIME_GRID_INVALID in codes(validate_trace_arrays(gap))


def test_trace_shape_and_key_violations_rejected() -> None:
    wrong_mask = build_v2_trace()
    wrong_mask["mask"] = np.zeros((V2_T, V2_MAX_N + 1), dtype=bool)
    assert V2FindingCode.SHAPE_MISMATCH in codes(validate_trace_arrays(wrong_mask))

    missing = build_v2_trace()
    del missing["rsu_xy"]
    assert codes(validate_trace_arrays(missing)) == [V2FindingCode.MISSING_KEYS]


def test_trace_requires_exact_audited_dtypes_and_finite_values() -> None:
    wrong_dtype = build_v2_trace()
    wrong_dtype["T"] = np.int64(V2_T)
    wrong_dtype["pos_x"] = np.asarray(wrong_dtype["pos_x"], dtype=np.float64)
    assert codes(validate_trace_arrays(wrong_dtype)) == [
        V2FindingCode.DTYPE_MISMATCH,
        V2FindingCode.DTYPE_MISMATCH,
    ]

    non_finite = build_v2_trace()
    non_finite["pos_x"] = np.array(non_finite["pos_x"])
    non_finite["pos_x"][0, 0] = np.nan
    assert V2FindingCode.VALUE_RANGE_INVALID in codes(validate_trace_arrays(non_finite))


def test_dependent_validators_fail_closed_on_invalid_trace() -> None:
    invalid_trace = build_v2_trace()
    del invalid_trace["T"]

    assert codes(validate_perstep_arrays(build_v2_perstep(), invalid_trace)) == [
        V2FindingCode.UPSTREAM_ARTIFACT_INVALID
    ]
    assert codes(validate_pertask_arrays(build_v2_pertask(), invalid_trace)) == [
        V2FindingCode.UPSTREAM_ARTIFACT_INVALID
    ]


# --- pertask negatives ---------------------------------------------------


def test_pertask_energy_key_refused_with_blocker_reference() -> None:
    pertask = build_v2_pertask()
    pertask["task_energy_j"] = np.zeros((V2_T, 5, V2_MAX_N), dtype=np.float32)
    report = validate_pertask_arrays(pertask, build_v2_trace())
    assert V2FindingCode.ENERGY_FIELD_NOT_IN_CONTRACT in codes(report)


def test_pertask_dtype_shape_and_range_violations() -> None:
    trace = build_v2_trace()

    wrong_dtype = build_v2_pertask()
    wrong_dtype["task_type"] = np.asarray(wrong_dtype["task_type"], dtype=np.float32)
    assert V2FindingCode.DTYPE_MISMATCH in codes(validate_pertask_arrays(wrong_dtype, trace))

    wrong_shape = build_v2_pertask()
    wrong_shape["task_met"] = np.zeros((V2_T, 4, V2_MAX_N), dtype=bool)
    assert V2FindingCode.SHAPE_MISMATCH in codes(validate_pertask_arrays(wrong_shape, trace))

    met_inactive = build_v2_pertask()
    met_inactive["task_met"] = np.array(met_inactive["task_met"])
    met_inactive["task_met"][5, 4, 2] = True
    report = validate_pertask_arrays(met_inactive, trace)
    assert V2FindingCode.VALUE_RANGE_INVALID in codes(report)
    assert "deadline success" in report.findings[0].detail

    bad_class = build_v2_pertask()
    bad_class["task_type"] = np.array(bad_class["task_type"])
    bad_class["task_type"][0, 0, 0] = 7
    assert V2FindingCode.VALUE_RANGE_INVALID in codes(validate_pertask_arrays(bad_class, trace))


# --- occupancy -----------------------------------------------------------


def test_occupancy_header_mismatch_rejected() -> None:
    _, rows = build_v2_occupancy_rows()
    spans, findings = parse_occupancy_rows(("vehicle", "slot", "start", "end"), rows, V2_SCENARIO)
    assert spans == []
    assert [finding.code for finding in findings] == [V2FindingCode.HEADER_MISMATCH]


def test_occupancy_invalid_rows_rejected() -> None:
    spans, findings = parse_occupancy_rows(
        OCCUPANCY_HEADER,
        [["veh_x", "0", "5", "3"], ["veh_y", "0", "not_int", "3"], ["veh_z", "1", "0"]],
        V2_SCENARIO,
    )
    assert spans == []
    assert [finding.code for finding in findings] == [
        V2FindingCode.SPAN_BOUNDS_INVALID,
        V2FindingCode.SPAN_BOUNDS_INVALID,
        V2FindingCode.SPAN_BOUNDS_INVALID,
    ]


def test_inclusive_boundary_sharing_is_a_conflict() -> None:
    spans = [
        OccupancySpan(sumo_vehicle_id="veh_a", slot=0, t_enter=0, t_exit=3, scenario=V2_SCENARIO),
        OccupancySpan(sumo_vehicle_id="veh_b", slot=0, t_enter=3, t_exit=5, scenario=V2_SCENARIO),
    ]
    report = reconcile_occupancy_spans(spans)
    assert report.status == "rejected"
    assert codes(report) == [V2FindingCode.SLOT_OVERLAP]


def test_vehicle_overlap_duplicates_and_trace_bounds_reported() -> None:
    base = OccupancySpan(sumo_vehicle_id="veh_a", slot=0, t_enter=0, t_exit=2, scenario=V2_SCENARIO)
    two_slots = OccupancySpan(
        sumo_vehicle_id="veh_a", slot=1, t_enter=2, t_exit=4, scenario=V2_SCENARIO
    )
    out_of_range = OccupancySpan(
        sumo_vehicle_id="veh_c", slot=9, t_enter=4, t_exit=99, scenario=V2_SCENARIO
    )
    report = reconcile_occupancy_spans(
        [base, base, two_slots, out_of_range], t_count=V2_T, max_n=V2_MAX_N
    )
    observed = codes(report)
    assert V2FindingCode.DUPLICATE_SPAN in observed
    assert V2FindingCode.VEHICLE_OVERLAP in observed
    assert observed.count(V2FindingCode.RANGE_OUT_OF_TRACE) == 2


def test_visit_seconds_must_match_mask_count() -> None:
    report = reconcile_occupancy_spans(golden_spans(), mask_true_count=11)
    assert codes(report) == [V2FindingCode.ACTIVE_MASK_MISMATCH]


def test_span_bounds_and_visit_seconds_are_inclusive() -> None:
    span = OccupancySpan(sumo_vehicle_id="veh_a", slot=0, t_enter=0, t_exit=2, scenario=V2_SCENARIO)
    assert span.visit_seconds == 3
    single = OccupancySpan(
        sumo_vehicle_id="veh_a", slot=0, t_enter=4, t_exit=4, scenario=V2_SCENARIO
    )
    assert single.visit_seconds == 1
    with pytest.raises(ValidationError, match="t_exit >= t_enter"):
        OccupancySpan(sumo_vehicle_id="veh_a", slot=0, t_enter=5, t_exit=4, scenario=V2_SCENARIO)


# --- typed row semantics -------------------------------------------------


def test_task_action_rows_keep_audited_semantics() -> None:
    row = VecTaskActionObservation(
        time_index=3,
        slot=1,
        sumo_vehicle_id="veh_synthetic_b",
        task_class=TaskClass.T2,
        deadline_met=True,
        action=Decision.V2I,
        eligible_best_rsu=-1,
    )
    assert row.eventual_completion == "unavailable"
    assert row.transfer_confirmed is False
    assert row.target_semantics == "eligible_decision_time_target"

    with pytest.raises(ValidationError, match="transfer_confirmed"):
        VecTaskActionObservation(
            time_index=3,
            slot=1,
            sumo_vehicle_id="veh_synthetic_b",
            task_class=TaskClass.T2,
            deadline_met=True,
            action=Decision.V2I,
            transfer_confirmed=True,
        )
    with pytest.raises(ValidationError, match="eventual_completion"):
        VecTaskActionObservation(
            time_index=3,
            slot=1,
            sumo_vehicle_id="veh_synthetic_b",
            task_class=TaskClass.T2,
            deadline_met=True,
            action=Decision.V2I,
            eventual_completion="completed",
        )
    with pytest.raises(ValidationError, match="never the source slot"):
        VecTaskActionObservation(
            time_index=3,
            slot=1,
            sumo_vehicle_id="veh_synthetic_b",
            task_class=TaskClass.T2,
            deadline_met=True,
            action=Decision.V2V,
            eligible_best_v2v=1,
        )


def test_attribute_rows_are_operational_only() -> None:
    row = VecVehicleAttributeObservation(
        sumo_vehicle_id="veh_synthetic_a",
        slot=0,
        t_enter=0,
        t_exit=2,
        slot_tier=2,
        slot_is_ev=False,
    )
    assert row.assignment_semantics == "fixed_per_slot_per_run"

    with pytest.raises(ValidationError, match="protected_attribute"):
        VecVehicleAttributeObservation(
            sumo_vehicle_id="veh_synthetic_a",
            slot=0,
            t_enter=0,
            t_exit=2,
            slot_tier=2,
            slot_is_ev=False,
            protected_attribute=True,
        )
    with pytest.raises(ValidationError, match="slot_tier"):
        VecVehicleAttributeObservation(
            sumo_vehicle_id="veh_synthetic_a",
            slot=0,
            t_enter=0,
            t_exit=2,
            slot_tier=3,
            slot_is_ev=False,
        )


def test_trip_joins_respect_censoring_and_no_fill() -> None:
    complete = VecTripJoin(
        sumo_vehicle_id="veh_synthetic_a",
        scenario=V2_SCENARIO,
        eligibility=TripJoinEligibility.ELIGIBLE_COMPLETE,
        depart_s=100.0,
        arrival_s=102.9,
        duration_s=2.9,
        route_length_m=55.0,
    )
    assert complete.duration_s == pytest.approx(2.9)

    censored = VecTripJoin(
        sumo_vehicle_id="veh_synthetic_b",
        scenario=V2_SCENARIO,
        eligibility=TripJoinEligibility.EXCLUDED_RIGHT_CENSORED_AT_BOUNDARY,
        depart_s=100.0,
        exclusion_reason="Vehicle is still present at the trace boundary.",
    )
    assert censored.arrival_s is None

    with pytest.raises(ValidationError, match="must not carry arrival_s"):
        VecTripJoin(
            sumo_vehicle_id="veh_synthetic_b",
            scenario=V2_SCENARIO,
            eligibility=TripJoinEligibility.EXCLUDED_RIGHT_CENSORED_AT_BOUNDARY,
            depart_s=100.0,
            arrival_s=105.0,
            exclusion_reason="Vehicle is still present at the trace boundary.",
        )
    with pytest.raises(ValidationError, match="requires an exclusion_reason"):
        VecTripJoin(
            sumo_vehicle_id="veh_synthetic_x",
            scenario=V2_SCENARIO,
            eligibility=TripJoinEligibility.EXCLUDED_UNMATCHED,
            depart_s=100.0,
        )


def test_tripinfo_fixture_parses_and_joins_to_trip_models(tmp_path: Path) -> None:
    root = write_v2_package(tmp_path / "v2")
    with gzip.open(root / f"tripinfo/tripinfo_{V2_SCENARIO}.xml.gz") as handle:
        tree = ElementTree.parse(handle)  # noqa: S314 - parses our own synthetic fixture
    records = {element.get("id"): element for element in tree.getroot().iter("tripinfo")}
    assert set(records) == {record["id"] for record in build_v2_tripinfo_records()}
    joined = [
        VecTripJoin(
            sumo_vehicle_id=str(element.get("id")),
            scenario=V2_SCENARIO,
            eligibility=TripJoinEligibility.ELIGIBLE_COMPLETE,
            depart_s=float(str(element.get("depart"))),
            arrival_s=float(str(element.get("arrival"))),
            duration_s=float(str(element.get("duration"))),
            route_length_m=float(str(element.get("routeLength"))),
        )
        for element in records.values()
    ]
    assert len(joined) == 2
    unmatched = VecTripJoin(
        sumo_vehicle_id="veh_synthetic_b",
        scenario=V2_SCENARIO,
        eligibility=TripJoinEligibility.EXCLUDED_RIGHT_CENSORED_AT_BOUNDARY,
        depart_s=100.0,
        exclusion_reason="No tripinfo record; vehicle persists to the trace boundary.",
    )
    assert unmatched.eligibility is not TripJoinEligibility.ELIGIBLE_COMPLETE

"""Reference arithmetic and fail-closed tests for the synthetic two-RSU hand check."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_task_lifecycle import (
    TwoRsuExecutionState,
    TwoRsuHandcheckCase,
    TwoRsuHandcheckError,
    VecTaskLifecycleError,
    build_two_rsu_handcheck_case,
    validate_two_rsu_handcheck,
)


def test_canonical_two_rsu_case_reconciles_hand_calculation() -> None:
    case = build_two_rsu_handcheck_case()

    report = validate_two_rsu_handcheck(case)

    assert report.case_fingerprint == case.fingerprint()
    assert report.ingress_rsu_id == "rsu-a-strong-full"
    assert report.execution_rsu_id == "rsu-b-weaker-idle"
    assert report.ingress_headroom_before == 0
    assert report.execution_headroom_before == 1
    assert report.reservation_slots == 1
    assert report.forwarding_hops == 1
    assert report.forwarding_ms == 4
    assert report.forwarding_energy_millijoules == 4 * 100
    assert report.end_to_end_ms == 2 + 4 + 2 + 10 + 5 == 23
    assert report.deadline_ms == 25
    assert report.deadline_met is True
    assert report.lifecycle_report.offered_count == 1
    assert report.lifecycle_report.returned_count == 1
    assert report.lifecycle_report.closed_task_count == 1
    assert report.lifecycle_report.deadline_met_count == 1
    assert report.task_count_conservation_holds is True


def test_case_is_deterministic_and_explicitly_non_scientific() -> None:
    first = build_two_rsu_handcheck_case()
    second = build_two_rsu_handcheck_case()

    assert first == second
    assert first.fingerprint() == second.fingerprint()
    assert validate_two_rsu_handcheck(first) == validate_two_rsu_handcheck(second)
    assert first.scheduler_included is False
    assert first.native_evaluator_validated is False
    assert first.scientific_evidence is False
    assert "not processor speed" in " ".join(first.assumptions)


def test_execution_state_refuses_over_capacity_input() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        TwoRsuExecutionState(
            rsu_id="rsu-invalid",
            link_quality_milliunits=500,
            execution_slot_limit=1,
            occupied_execution_slots=2,
        )


@pytest.mark.parametrize(
    ("rsu_index", "update", "error_code"),
    [
        (0, {"occupied_execution_slots": 0}, "TWO_RSU_INGRESS_NOT_FULL"),
        (1, {"link_quality_milliunits": 950}, "TWO_RSU_INGRESS_NOT_UNIQUE_STRONGEST"),
        (1, {"occupied_execution_slots": 1}, "TWO_RSU_EXECUTION_NOT_WEAKER_IDLE"),
    ],
)
def test_rsu_state_tampering_fails_closed(
    rsu_index: int, update: dict[str, int], error_code: str
) -> None:
    case = build_two_rsu_handcheck_case()
    states = list(case.rsus)
    states[rsu_index] = states[rsu_index].model_copy(update=update)
    changed = case.model_copy(update={"rsus": tuple(states)})

    with pytest.raises(TwoRsuHandcheckError, match=error_code):
        validate_two_rsu_handcheck(changed)


@pytest.mark.parametrize(
    ("update", "error_code"),
    [
        ({"occupied_after_creation": 0}, "TWO_RSU_RESERVATION_MISMATCH"),
        ({"occupied_after_release": 1}, "TWO_RSU_RESERVATION_MISMATCH"),
        ({"created_at_ms": 1}, "TWO_RSU_RESERVATION_TIME_MISMATCH"),
        ({"released_at_ms": 17}, "TWO_RSU_RESERVATION_TIME_MISMATCH"),
    ],
)
def test_reservation_tampering_fails_closed(update: dict[str, int], error_code: str) -> None:
    case = build_two_rsu_handcheck_case()
    changed = case.model_copy(update={"reservation": case.reservation.model_copy(update=update)})

    with pytest.raises(TwoRsuHandcheckError, match=error_code):
        validate_two_rsu_handcheck(changed)


def test_timing_forwarding_cost_and_deadline_tampering_fail_closed() -> None:
    case = build_two_rsu_handcheck_case()

    changed_events = list(case.events)
    changed_events[4] = changed_events[4].model_copy(update={"occurred_at_ms": 5.0})
    with pytest.raises(TwoRsuHandcheckError, match="TWO_RSU_TIMING_MISMATCH"):
        validate_two_rsu_handcheck(case.model_copy(update={"events": tuple(changed_events)}))

    with pytest.raises(TwoRsuHandcheckError, match="TWO_RSU_FORWARDING_COST_MISMATCH"):
        validate_two_rsu_handcheck(case.model_copy(update={"forwarding_energy_millijoules": 401}))

    changed_events = list(case.events)
    changed_events[-1] = changed_events[-1].model_copy(update={"deadline_met": False})
    with pytest.raises(TwoRsuHandcheckError, match="TWO_RSU_DEADLINE_MISMATCH"):
        validate_two_rsu_handcheck(case.model_copy(update={"events": tuple(changed_events)}))


def test_execution_path_and_event_sequence_tampering_fail_closed() -> None:
    case = build_two_rsu_handcheck_case()

    changed_events = list(case.events)
    changed_events[5] = changed_events[5].model_copy(update={"node_id": case.ingress_rsu_id})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_NODE_MISMATCH"):
        validate_two_rsu_handcheck(case.model_copy(update={"events": tuple(changed_events)}))

    changed_events = list(case.events)
    changed_events[4] = changed_events[4].model_copy(update={"sequence_index": 40})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_SEQUENCE_GAP"):
        validate_two_rsu_handcheck(case.model_copy(update={"events": tuple(changed_events)}))


def test_case_model_refuses_non_two_rsu_and_same_target_inputs() -> None:
    case = build_two_rsu_handcheck_case()
    payload = case.model_dump(mode="json")
    payload["rsus"][1]["rsu_id"] = payload["rsus"][0]["rsu_id"]
    with pytest.raises(ValidationError, match="distinct RSUs"):
        TwoRsuHandcheckCase.model_validate(payload)

    payload = case.model_dump(mode="json")
    payload["execution_rsu_id"] = payload["ingress_rsu_id"]
    with pytest.raises(ValidationError, match="forwarding hop"):
        TwoRsuHandcheckCase.model_validate(payload)

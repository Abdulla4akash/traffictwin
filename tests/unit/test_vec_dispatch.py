"""Deterministic policy, reservation and refusal tests for VEC dispatch v1."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_dispatch import (
    VecDispatchCandidate,
    VecDispatchDisposition,
    VecDispatchError,
    VecDispatchPolicy,
    VecDispatchReason,
    VecDispatchRequest,
    dispatch_vec_batch,
    dispatch_vec_task,
    vec_dispatch_contract,
)


def _candidate(
    rsu_id: str,
    *,
    link: int,
    limit: int = 1,
    occupied: int = 0,
    reserved: int = 0,
    age: int = 0,
    forwarding: int = 0,
    energy: int = 0,
    queue: int = 0,
    compute: int = 10,
    returning: int = 5,
    reachable: bool = True,
    enabled: bool = True,
) -> VecDispatchCandidate:
    return VecDispatchCandidate(
        rsu_id=rsu_id,
        reachable=reachable,
        execution_enabled=enabled,
        link_quality_milliunits=link,
        execution_slot_limit=limit,
        occupied_execution_slots=occupied,
        reserved_execution_slots=reserved,
        telemetry_age_ms=age,
        forwarding_ms=forwarding,
        forwarding_energy_millijoules=energy,
        predicted_queue_wait_ms=queue,
        predicted_compute_ms=compute,
        predicted_return_ms=returning,
    )


def _request(
    *candidates: VecDispatchCandidate,
    task_id: str = "task-1",
    decision_order: int = 0,
    snapshot_id: str = "snapshot-1",
    ingress: str = "rsu-a",
    max_age: int = 100,
) -> VecDispatchRequest:
    return VecDispatchRequest(
        snapshot_id=snapshot_id,
        task_id=task_id,
        decision_order=decision_order,
        ingress_rsu_id=ingress,
        task_execution_slots=1,
        max_telemetry_age_ms=max_age,
        candidates=candidates,
    )


def _full_ingress_idle_weaker_request(
    *, task_id: str = "task-1", decision_order: int = 0
) -> VecDispatchRequest:
    return _request(
        _candidate("rsu-a", link=900, occupied=1),
        _candidate("rsu-b", link=600, forwarding=4, energy=400, queue=2),
        task_id=task_id,
        decision_order=decision_order,
    )


def test_two_rsu_case_separates_no_forwarding_from_load_aware_policies() -> None:
    request = _full_ingress_idle_weaker_request()

    no_forwarding = dispatch_vec_task(request, VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING)
    least_loaded = dispatch_vec_task(request, VecDispatchPolicy.LEAST_LOADED)
    earliest = dispatch_vec_task(request, VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION)

    assert no_forwarding.disposition is VecDispatchDisposition.NO_EXECUTION_TARGET
    assert no_forwarding.reason is VecDispatchReason.INGRESS_NO_EXECUTION_HEADROOM
    assert no_forwarding.selected_rsu_id is None
    assert no_forwarding.eligible_candidate_ids == ("rsu-b",)

    for decision in (least_loaded, earliest):
        assert decision.disposition is VecDispatchDisposition.SELECTED
        assert decision.selected_rsu_id == "rsu-b"
        assert decision.forwarded is True
        assert decision.reservation_before == 0
        assert decision.reservation_after == 1
        assert decision.task_execution_slots == 1
        assert decision.selected_forwarding_ms == 4
        assert decision.selected_forwarding_energy_millijoules == 400
        assert decision.selected_predicted_completion_ms == 4 + 2 + 10 + 5
        assert decision.execution_confirmed is False
        assert decision.physical_return_confirmed is False


def test_all_policies_use_one_contract_but_apply_distinct_rankings() -> None:
    request = _request(
        _candidate("rsu-a", link=900, limit=4, occupied=1, queue=15),
        _candidate(
            "rsu-b",
            link=700,
            limit=4,
            occupied=2,
            forwarding=2,
            energy=20,
            queue=0,
            compute=3,
            returning=2,
        ),
    )

    no_forwarding = dispatch_vec_task(request, VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING)
    least_loaded = dispatch_vec_task(request, VecDispatchPolicy.LEAST_LOADED)
    earliest = dispatch_vec_task(request, VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION)

    assert no_forwarding.selected_rsu_id == "rsu-a"
    assert least_loaded.selected_rsu_id == "rsu-a"
    assert least_loaded.selected_projected_load_ppm == 500_000
    assert earliest.selected_rsu_id == "rsu-b"
    assert earliest.selected_predicted_completion_ms == 7


@pytest.mark.parametrize(
    "policy",
    [VecDispatchPolicy.LEAST_LOADED, VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION],
)
def test_ties_are_stable_and_candidate_input_order_independent(policy: VecDispatchPolicy) -> None:
    first = _candidate("rsu-a", link=900, limit=2, forwarding=0, energy=0)
    second = _candidate("rsu-b", link=900, limit=2, forwarding=0, energy=0)

    decision_a = dispatch_vec_task(_request(second, first, ingress="rsu-b"), policy)
    decision_b = dispatch_vec_task(_request(first, second, ingress="rsu-b"), policy)

    assert decision_a == decision_b
    assert decision_a.selected_rsu_id == "rsu-a"


@pytest.mark.parametrize(
    ("candidate_update", "expected_reason"),
    [
        ({"execution_enabled": False}, VecDispatchReason.INGRESS_EXECUTION_DISABLED),
        ({"telemetry_age_ms": 101}, VecDispatchReason.INGRESS_TELEMETRY_STALE),
        ({"occupied_execution_slots": 1}, VecDispatchReason.INGRESS_NO_EXECUTION_HEADROOM),
    ],
)
def test_no_forwarding_reports_exact_ingress_refusal(
    candidate_update: dict[str, int | bool], expected_reason: VecDispatchReason
) -> None:
    ingress = _candidate("rsu-a", link=900).model_copy(update=candidate_update)
    other = _candidate("rsu-b", link=600, forwarding=1)
    request = _request(ingress, other)

    decision = dispatch_vec_task(request, VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING)

    assert decision.disposition is VecDispatchDisposition.NO_EXECUTION_TARGET
    assert decision.reason is expected_reason
    assert decision.selected_rsu_id is None


def test_stale_disabled_and_unreachable_candidates_are_ineligible() -> None:
    request = _request(
        _candidate("rsu-a", link=900, occupied=1),
        _candidate("rsu-b", link=700, age=101, forwarding=1),
        _candidate("rsu-c", link=650, enabled=False, forwarding=1),
        _candidate("rsu-d", link=600, reachable=False, forwarding=1),
    )

    for policy in (
        VecDispatchPolicy.LEAST_LOADED,
        VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION,
    ):
        decision = dispatch_vec_task(request, policy)
        assert decision.disposition is VecDispatchDisposition.NO_EXECUTION_TARGET
        assert decision.reason is VecDispatchReason.NO_ELIGIBLE_EXECUTION_RSU
        assert decision.eligible_candidate_ids == ()


@pytest.mark.parametrize(
    "policy",
    [VecDispatchPolicy.LEAST_LOADED, VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION],
)
def test_batch_reservations_prevent_two_tasks_reusing_one_slot(
    policy: VecDispatchPolicy,
) -> None:
    first = _full_ingress_idle_weaker_request(task_id="task-a", decision_order=0)
    second = _full_ingress_idle_weaker_request(task_id="task-b", decision_order=1)

    report = dispatch_vec_batch([second, first], policy)
    reordered = dispatch_vec_batch([first, second], policy)

    assert report == reordered
    assert report.input_fingerprint == reordered.input_fingerprint
    assert report.request_count == 2
    assert report.selected_count == 1
    assert report.unavailable_count == 1
    assert report.forwarded_count == 1
    assert report.decisions[0].task_id == "task-a"
    assert report.decisions[0].selected_rsu_id == "rsu-b"
    assert report.decisions[1].task_id == "task-b"
    assert report.decisions[1].selected_rsu_id is None
    summaries = {summary.rsu_id: summary for summary in report.reservation_summaries}
    assert summaries["rsu-b"].initial_reserved_execution_slots == 0
    assert summaries["rsu-b"].final_reserved_execution_slots == 1
    assert summaries["rsu-b"].newly_reserved_execution_slots == 1
    assert report.task_count_conservation_holds is True


def test_batch_rejects_ambiguous_order_identity_and_resource_state() -> None:
    first = _full_ingress_idle_weaker_request(task_id="task-a", decision_order=0)
    second = _full_ingress_idle_weaker_request(task_id="task-b", decision_order=1)

    with pytest.raises(VecDispatchError, match="DISPATCH_BATCH_EMPTY"):
        dispatch_vec_batch([], VecDispatchPolicy.LEAST_LOADED)
    with pytest.raises(VecDispatchError, match="DISPATCH_BATCH_ORDER_INVALID"):
        dispatch_vec_batch(
            [first, second.model_copy(update={"decision_order": 2})],
            VecDispatchPolicy.LEAST_LOADED,
        )
    with pytest.raises(VecDispatchError, match="DISPATCH_BATCH_TASK_DUPLICATE"):
        dispatch_vec_batch(
            [first, second.model_copy(update={"task_id": "task-a"})],
            VecDispatchPolicy.LEAST_LOADED,
        )
    with pytest.raises(VecDispatchError, match="DISPATCH_BATCH_SNAPSHOT_MIXED"):
        dispatch_vec_batch(
            [first, second.model_copy(update={"snapshot_id": "snapshot-2"})],
            VecDispatchPolicy.LEAST_LOADED,
        )

    changed_candidates = list(second.candidates)
    changed_candidates[1] = changed_candidates[1].model_copy(update={"reserved_execution_slots": 1})
    changed = second.model_copy(update={"candidates": tuple(changed_candidates)})
    with pytest.raises(VecDispatchError, match="DISPATCH_BATCH_RESOURCE_STATE_MISMATCH"):
        dispatch_vec_batch([first, changed], VecDispatchPolicy.LEAST_LOADED)


def test_request_and_candidate_contracts_fail_closed() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        _candidate("rsu-a", link=900, limit=1, occupied=1, reserved=1)

    ingress = _candidate("rsu-a", link=900)
    other = _candidate("rsu-b", link=600, forwarding=1)
    payload = _request(ingress, other).model_dump(mode="json")
    payload["candidates"][1]["rsu_id"] = "rsu-a"
    with pytest.raises(ValidationError, match="unique"):
        VecDispatchRequest.model_validate(payload)

    with pytest.raises(ValidationError, match="zero forwarding"):
        _request(ingress.model_copy(update={"forwarding_ms": 1}), other)

    with pytest.raises(ValidationError, match="maximum link quality"):
        _request(ingress.model_copy(update={"link_quality_milliunits": 500}), other)

    payload = _request(ingress, other).model_dump(mode="json")
    payload["actor_action"] = Decision.LOCAL
    with pytest.raises(ValidationError, match="v2i"):
        VecDispatchRequest.model_validate(payload)


def test_contract_preserves_actor_and_scientific_boundaries() -> None:
    contract = vec_dispatch_contract()

    assert contract.policies == tuple(VecDispatchPolicy)
    assert contract.actor_action is Decision.V2I
    assert contract.actor_observation_changed is False
    assert contract.actor_retraining_required is False
    assert contract.native_evaluator_adapter_available is False
    assert contract.scientific_evidence is False
    assert contract.fingerprint() == vec_dispatch_contract().fingerprint()

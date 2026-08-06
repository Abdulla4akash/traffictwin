"""Matched-input, projection and refusal tests for deterministic VEC dispatch studies."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from traffictwin.integration.vec_dispatch import (
    VecDispatchCandidate,
    VecDispatchDisposition,
    VecDispatchPolicy,
    VecDispatchRequest,
)
from traffictwin.integration.vec_dispatch_study import (
    MATCHED_VEC_DISPATCH_POLICIES,
    VecDispatchStudyError,
    VecDispatchStudyPlan,
    VecDispatchStudyReport,
    compare_two_rsu_handcheck_policies,
    compare_vec_dispatch_policies,
    vec_dispatch_study_contract,
)
from traffictwin.integration.vec_task_lifecycle import build_two_rsu_handcheck_case


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
    snapshot_id: str = "snapshot-study-1",
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


def _full_ingress_idle_weaker(
    *, task_id: str = "task-1", decision_order: int = 0
) -> VecDispatchRequest:
    return _request(
        _candidate("rsu-a", link=900, occupied=1),
        _candidate("rsu-b", link=600, forwarding=4, energy=400, queue=2),
        task_id=task_id,
        decision_order=decision_order,
    )


def test_two_rsu_study_exact_matches_inputs_and_exposes_policy_divergence() -> None:
    report = compare_vec_dispatch_policies("two-rsu-matched-study", (_full_ingress_idle_weaker(),))

    assert tuple(item.policy for item in report.policy_reports) == MATCHED_VEC_DISPATCH_POLICIES
    assert {item.input_fingerprint for item in report.policy_reports} == {
        report.common_input_fingerprint
    }
    assert report.request_count == 1
    assert report.route_agreement_task_count == 0
    assert report.route_disagreement_task_count == 1
    assert report.projection_disagreement_task_count == 1
    comparison = report.task_comparisons[0]
    assert comparison.original_request_fingerprint == report.plan.requests[0].fingerprint()
    assert [item.decision.selected_rsu_id for item in comparison.outcomes] == [
        None,
        "rsu-b",
        "rsu-b",
    ]

    summaries = {summary.policy: summary for summary in report.policy_summaries}
    no_forwarding = summaries[VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING]
    assert no_forwarding.selected_count == 0
    assert no_forwarding.unavailable_count == 1
    assert no_forwarding.selected_predicted_completion_ms_sum == 0
    for policy in (
        VecDispatchPolicy.LEAST_LOADED,
        VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION,
    ):
        summary = summaries[policy]
        assert summary.selected_count == 1
        assert summary.forwarded_count == 1
        assert summary.selected_execution_slots == 1
        assert summary.selected_predicted_completion_ms_sum == 21
        assert summary.selected_forwarding_ms_sum == 4
        assert summary.selected_forwarding_energy_millijoules_sum == 400
        rsu_b = {item.rsu_id: item for item in summary.rsu_projections}["rsu-b"]
        assert rsu_b.final_reserved_execution_slots == 1
        assert rsu_b.final_projected_load_ppm == 1_000_000
        assert rsu_b.processor_utilisation is False


def test_public_two_rsu_comparison_exact_binds_the_handcheck_fixture() -> None:
    case = build_two_rsu_handcheck_case()

    report = compare_two_rsu_handcheck_policies()

    request = report.plan.requests[0]
    assert request.snapshot_id == case.run_id
    assert request.task_id == case.task_id
    assert request.ingress_rsu_id == case.ingress_rsu_id
    assert {candidate.rsu_id for candidate in request.candidates} == {
        state.rsu_id for state in case.rsus
    }
    assert report.route_disagreement_task_count == 1
    summaries = {summary.policy: summary for summary in report.policy_summaries}
    for policy in (
        VecDispatchPolicy.LEAST_LOADED,
        VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION,
    ):
        assert summaries[policy].selected_predicted_completion_ms_sum == (
            case.forwarding_ms + case.queue_wait_ms + case.compute_ms + case.return_ms
        )


def test_all_policies_can_agree_without_creating_a_winner_claim() -> None:
    request = _request(
        _candidate("rsu-a", link=900, limit=2),
        _candidate("rsu-b", link=600, reachable=False, forwarding=2),
    )

    report = compare_vec_dispatch_policies("all-policies-agree", (request,))

    assert report.route_agreement_task_count == 1
    assert report.projection_agreement_task_count == 1
    assert report.task_comparisons[0].route_agreement is True
    assert report.task_comparisons[0].projection_agreement is True
    assert report.winner_selected is False
    assert report.scientific_evidence is False
    assert all(summary.scientific_evidence is False for summary in report.policy_summaries)


def test_matched_information_preserves_distinct_policy_rankings() -> None:
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

    report = compare_vec_dispatch_policies("distinct-policy-rankings", (request,))
    selected = {
        outcome.policy: outcome.decision.selected_rsu_id
        for outcome in report.task_comparisons[0].outcomes
    }

    assert selected == {
        VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING: "rsu-a",
        VecDispatchPolicy.LEAST_LOADED: "rsu-a",
        VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION: "rsu-b",
    }
    assert report.task_comparisons[0].route_agreement is False
    assert report.predictions_are_caller_supplied is True


def test_batch_comparison_reconciles_policy_specific_reservations() -> None:
    first = _full_ingress_idle_weaker(task_id="task-a", decision_order=0)
    second = _full_ingress_idle_weaker(task_id="task-b", decision_order=1)

    report = compare_vec_dispatch_policies("reservation-batch", (first, second))
    summaries = {summary.policy: summary for summary in report.policy_summaries}

    no_forwarding = summaries[VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING]
    assert no_forwarding.selected_count == 0
    assert no_forwarding.unavailable_count == 2
    for policy in (
        VecDispatchPolicy.LEAST_LOADED,
        VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION,
    ):
        summary = summaries[policy]
        assert summary.selected_count == 1
        assert summary.unavailable_count == 1
        assert summary.selected_execution_slots == 1
        rsu_b = {item.rsu_id: item for item in summary.rsu_projections}["rsu-b"]
        assert rsu_b.selected_task_count == 1
        assert rsu_b.selected_execution_slots == 1
    assert report.route_agreement_task_count == 1
    assert report.route_disagreement_task_count == 1
    assert report.projection_agreement_task_count == 0
    assert report.projection_disagreement_task_count == 2
    assert report.reservation_conservation_holds is True


def test_plan_canonicalisation_makes_caller_input_order_irrelevant() -> None:
    first = _full_ingress_idle_weaker(task_id="task-a", decision_order=0)
    second = _full_ingress_idle_weaker(task_id="task-b", decision_order=1)

    ordered = compare_vec_dispatch_policies("canonical-order", (first, second))
    reversed_input = compare_vec_dispatch_policies("canonical-order", (second, first))

    assert ordered == reversed_input
    assert ordered.fingerprint() == reversed_input.fingerprint()


def test_invalid_plan_and_ambiguous_shared_resource_state_fail_closed() -> None:
    first = _full_ingress_idle_weaker(task_id="task-a", decision_order=0)
    second = _full_ingress_idle_weaker(task_id="task-b", decision_order=1)

    with pytest.raises(VecDispatchStudyError, match="DISPATCH_STUDY_PLAN_INVALID"):
        compare_vec_dispatch_policies(
            "mixed-snapshot",
            (first, second.model_copy(update={"snapshot_id": "snapshot-other"})),
        )
    with pytest.raises(VecDispatchStudyError, match="DISPATCH_STUDY_PLAN_INVALID"):
        compare_vec_dispatch_policies(
            "invalid-order",
            (first, second.model_copy(update={"decision_order": 2})),
        )

    candidates = list(second.candidates)
    candidates[1] = candidates[1].model_copy(update={"reserved_execution_slots": 1})
    changed = second.model_copy(update={"candidates": tuple(candidates)})
    with pytest.raises(VecDispatchStudyError, match="DISPATCH_STUDY_INPUT_INVALID"):
        compare_vec_dispatch_policies("resource-drift", (first, changed))


def test_report_contract_detects_input_summary_and_task_tampering() -> None:
    report = compare_vec_dispatch_policies("tamper-detection", (_full_ingress_idle_weaker(),))
    payload = report.model_dump(mode="json")
    payload["common_input_fingerprint"] = "f" * 64
    with pytest.raises(ValidationError, match="identical original input"):
        VecDispatchStudyReport.model_validate(payload)

    payload = report.model_dump(mode="json")
    payload["policy_summaries"][1]["selected_predicted_completion_ms_sum"] += 1
    with pytest.raises(ValidationError, match="does not reconcile"):
        VecDispatchStudyReport.model_validate(payload)

    payload = report.model_dump(mode="json")
    payload["task_comparisons"][0]["original_request_fingerprint"] = "e" * 64
    with pytest.raises(ValidationError, match="original request"):
        VecDispatchStudyReport.model_validate(payload)


def test_plan_refuses_partial_or_reordered_policy_sets() -> None:
    plan = VecDispatchStudyPlan(
        study_id="policy-set-contract", requests=(_full_ingress_idle_weaker(),)
    )
    payload = plan.model_dump(mode="json")
    payload["policies"] = payload["policies"][:2]
    with pytest.raises(ValidationError, match="all three policies"):
        VecDispatchStudyPlan.model_validate(payload)

    payload = plan.model_dump(mode="json")
    payload["policies"] = list(reversed(payload["policies"]))
    with pytest.raises(ValidationError, match="canonical order"):
        VecDispatchStudyPlan.model_validate(payload)


def test_contract_keeps_synthetic_prediction_and_learning_boundaries() -> None:
    contract = vec_dispatch_study_contract()

    assert contract.policies == MATCHED_VEC_DISPATCH_POLICIES
    assert contract.input_kind == "synthetic_fixture"
    assert contract.identical_original_input_required is True
    assert contract.reservation_aware is True
    assert contract.winner_ranking_available is False
    assert contract.actual_lifecycle_outcomes_available is False
    assert contract.native_evaluator_input_available is False
    assert contract.learned_scheduler_available is False
    assert contract.scientific_evidence is False
    assert contract.fingerprint() == vec_dispatch_study_contract().fingerprint()


def test_unavailable_decisions_remain_unavailable_not_zero_cost_successes() -> None:
    request = _request(
        _candidate("rsu-a", link=900, occupied=1),
        _candidate("rsu-b", link=600, occupied=1, forwarding=4, energy=400),
    )

    report = compare_vec_dispatch_policies("all-unavailable", (request,))

    assert all(
        outcome.decision.disposition is VecDispatchDisposition.NO_EXECUTION_TARGET
        for outcome in report.task_comparisons[0].outcomes
    )
    for summary in report.policy_summaries:
        assert summary.unavailable_count == 1
        assert summary.selected_count == 0
        assert summary.selected_predicted_completion_ms_sum == 0
        assert summary.actual_execution_count_available is False
        assert summary.measured_latency_available is False
        assert summary.measured_energy_available is False

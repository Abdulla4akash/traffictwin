"""Pure matched comparison across every deterministic VEC dispatch policy."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import ValidationError

from traffictwin.integration.vec_dispatch import (
    VecDispatchBatchReport,
    VecDispatchCandidate,
    VecDispatchDecision,
    VecDispatchDisposition,
    VecDispatchError,
    VecDispatchRequest,
    dispatch_vec_batch,
)
from traffictwin.integration.vec_dispatch_study.models import (
    MATCHED_VEC_DISPATCH_POLICIES,
    VecDispatchPolicyOutcome,
    VecDispatchPolicySummary,
    VecDispatchRsuProjection,
    VecDispatchStudyPlan,
    VecDispatchStudyReport,
    VecDispatchTaskComparison,
)
from traffictwin.integration.vec_task_lifecycle import (
    build_two_rsu_handcheck_case,
    validate_two_rsu_handcheck,
)


class VecDispatchStudyError(ValueError):
    """Typed fail-closed matched-study refusal with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def compare_two_rsu_handcheck_policies() -> VecDispatchStudyReport:
    """Replay the canonical synthetic two-RSU hand-check through all three policies."""

    case = build_two_rsu_handcheck_case()
    validate_two_rsu_handcheck(case)
    candidates = tuple(
        VecDispatchCandidate(
            rsu_id=state.rsu_id,
            link_quality_milliunits=state.link_quality_milliunits,
            execution_slot_limit=state.execution_slot_limit,
            occupied_execution_slots=state.occupied_execution_slots,
            reserved_execution_slots=0,
            telemetry_age_ms=0,
            forwarding_ms=(case.forwarding_ms if state.rsu_id == case.execution_rsu_id else 0),
            forwarding_energy_millijoules=(
                case.forwarding_energy_millijoules if state.rsu_id == case.execution_rsu_id else 0
            ),
            predicted_queue_wait_ms=(
                case.queue_wait_ms if state.rsu_id == case.execution_rsu_id else 0
            ),
            predicted_compute_ms=case.compute_ms,
            predicted_return_ms=case.return_ms,
        )
        for state in case.rsus
    )
    request = VecDispatchRequest(
        snapshot_id=case.run_id,
        task_id=case.task_id,
        decision_order=0,
        ingress_rsu_id=case.ingress_rsu_id,
        task_execution_slots=case.task_execution_slots,
        max_telemetry_age_ms=0,
        candidates=candidates,
    )
    return compare_vec_dispatch_policies("two-rsu-handcheck-dispatch-study", (request,))


def compare_vec_dispatch_policies(
    study_id: str,
    requests: Sequence[VecDispatchRequest],
) -> VecDispatchStudyReport:
    """Run all deterministic policies over one identical canonical synthetic batch."""

    try:
        plan = VecDispatchStudyPlan(study_id=study_id, requests=tuple(requests))
    except ValidationError as exc:
        raise VecDispatchStudyError(
            "DISPATCH_STUDY_PLAN_INVALID", "matched synthetic plan failed its strict contract"
        ) from exc

    reports: list[VecDispatchBatchReport] = []
    try:
        for policy in MATCHED_VEC_DISPATCH_POLICIES:
            reports.append(dispatch_vec_batch(plan.requests, policy))
    except (VecDispatchError, ValidationError) as exc:
        raise VecDispatchStudyError(
            "DISPATCH_STUDY_INPUT_INVALID",
            "the common request batch cannot be replayed deterministically",
        ) from exc
    policy_reports = tuple(reports)
    input_fingerprints = {report.input_fingerprint for report in policy_reports}
    if len(input_fingerprints) != 1:
        raise AssertionError("deterministic policies did not receive one common input")
    common_input_fingerprint = next(iter(input_fingerprints))

    resource_state = _resource_state(plan.requests)
    policy_summaries = tuple(_summarise_policy(report, resource_state) for report in policy_reports)
    task_comparisons = _compare_tasks(plan, policy_reports)
    route_agreement_count = sum(item.route_agreement for item in task_comparisons)
    projection_agreement_count = sum(item.projection_agreement for item in task_comparisons)
    try:
        return VecDispatchStudyReport(
            plan=plan,
            plan_fingerprint=plan.fingerprint(),
            common_input_fingerprint=common_input_fingerprint,
            request_count=len(plan.requests),
            policy_reports=policy_reports,
            policy_summaries=policy_summaries,
            task_comparisons=task_comparisons,
            route_agreement_task_count=route_agreement_count,
            route_disagreement_task_count=len(plan.requests) - route_agreement_count,
            projection_agreement_task_count=projection_agreement_count,
            projection_disagreement_task_count=len(plan.requests) - projection_agreement_count,
        )
    except ValidationError as exc:
        raise VecDispatchStudyError(
            "DISPATCH_STUDY_REPORT_INVALID",
            "matched policy projections failed internal reconciliation",
        ) from exc


def _summarise_policy(
    report: VecDispatchBatchReport,
    resources: dict[str, tuple[int, int, int]],
) -> VecDispatchPolicySummary:
    selected = [
        decision
        for decision in report.decisions
        if decision.disposition is VecDispatchDisposition.SELECTED
    ]
    reservations = {summary.rsu_id: summary for summary in report.reservation_summaries}
    projections: list[VecDispatchRsuProjection] = []
    for rsu_id in sorted(resources):
        limit, occupied, initial_reserved = resources[rsu_id]
        reservation = reservations[rsu_id]
        selected_here = [decision for decision in selected if decision.selected_rsu_id == rsu_id]
        final_population = occupied + reservation.final_reserved_execution_slots
        projections.append(
            VecDispatchRsuProjection(
                rsu_id=rsu_id,
                execution_slot_limit=limit,
                initial_occupied_execution_slots=occupied,
                initial_reserved_execution_slots=initial_reserved,
                newly_reserved_execution_slots=reservation.newly_reserved_execution_slots,
                final_reserved_execution_slots=reservation.final_reserved_execution_slots,
                final_occupied_plus_reserved_slots=final_population,
                final_projected_load_ppm=final_population * 1_000_000 // limit,
                selected_task_count=len(selected_here),
                selected_execution_slots=sum(
                    decision.task_execution_slots for decision in selected_here
                ),
            )
        )
    return VecDispatchPolicySummary(
        policy=report.policy,
        batch_report_fingerprint=report.fingerprint(),
        request_count=report.request_count,
        selected_count=report.selected_count,
        unavailable_count=report.unavailable_count,
        forwarded_count=report.forwarded_count,
        selected_execution_slots=sum(decision.task_execution_slots for decision in selected),
        selected_predicted_completion_ms_sum=sum(
            _required(decision.selected_predicted_completion_ms) for decision in selected
        ),
        selected_forwarding_ms_sum=sum(
            _required(decision.selected_forwarding_ms) for decision in selected
        ),
        selected_forwarding_energy_millijoules_sum=sum(
            _required(decision.selected_forwarding_energy_millijoules) for decision in selected
        ),
        rsu_projections=tuple(projections),
    )


def _compare_tasks(
    plan: VecDispatchStudyPlan,
    reports: tuple[VecDispatchBatchReport, ...],
) -> tuple[VecDispatchTaskComparison, ...]:
    comparisons: list[VecDispatchTaskComparison] = []
    for request in plan.requests:
        outcomes = tuple(
            VecDispatchPolicyOutcome(
                policy=report.policy,
                decision=report.decisions[request.decision_order],
            )
            for report in reports
        )
        route_signatures = {
            (
                outcome.decision.disposition,
                outcome.decision.selected_rsu_id,
                outcome.decision.forwarded,
            )
            for outcome in outcomes
        }
        projection_signatures = {_projection_signature(outcome.decision) for outcome in outcomes}
        comparisons.append(
            VecDispatchTaskComparison(
                task_id=request.task_id,
                decision_order=request.decision_order,
                original_request_fingerprint=request.fingerprint(),
                outcomes=outcomes,
                route_agreement=len(route_signatures) == 1,
                projection_agreement=len(projection_signatures) == 1,
            )
        )
    return tuple(comparisons)


def _resource_state(
    requests: tuple[VecDispatchRequest, ...],
) -> dict[str, tuple[int, int, int]]:
    resources: dict[str, tuple[int, int, int]] = {}
    for request in requests:
        for candidate in request.candidates:
            state = (
                candidate.execution_slot_limit,
                candidate.occupied_execution_slots,
                candidate.reserved_execution_slots,
            )
            previous = resources.setdefault(candidate.rsu_id, state)
            if previous != state:
                raise AssertionError("dispatcher accepted inconsistent shared resource state")
    return resources


def _projection_signature(decision: VecDispatchDecision) -> tuple[object, ...]:
    return (
        decision.request_fingerprint,
        decision.disposition,
        decision.reason,
        decision.eligible_candidate_ids,
        decision.selected_rsu_id,
        decision.forwarded,
        decision.reservation_before,
        decision.reservation_after,
        decision.selected_projected_load_ppm,
        decision.selected_predicted_completion_ms,
        decision.selected_forwarding_ms,
        decision.selected_forwarding_energy_millijoules,
    )


def _required(value: int | None) -> int:
    if value is None:
        raise AssertionError("selected decision is missing projection data")
    return value

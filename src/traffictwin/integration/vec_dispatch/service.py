"""Pure deterministic policies and reservation-aware batch dispatch."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from fractions import Fraction

from traffictwin.integration.vec_dispatch.models import (
    VecDispatchBatchReport,
    VecDispatchCandidate,
    VecDispatchDecision,
    VecDispatchDisposition,
    VecDispatchPolicy,
    VecDispatchReason,
    VecDispatchRequest,
    VecDispatchReservationSummary,
)

MAX_DISPATCH_BATCH_REQUESTS = 100_000


class VecDispatchError(ValueError):
    """Typed fail-closed dispatcher refusal with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def dispatch_vec_task(
    request: VecDispatchRequest,
    policy: VecDispatchPolicy,
) -> VecDispatchDecision:
    """Select and reserve one execution RSU without mutating caller state."""

    eligible = tuple(
        candidate for candidate in request.candidates if _is_eligible(candidate, request)
    )
    selected: VecDispatchCandidate | None
    reason = VecDispatchReason.SELECTED
    if policy is VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING:
        ingress = _candidate_by_id(request, request.ingress_rsu_id)
        selected = ingress if ingress in eligible else None
        if selected is None:
            reason = _ingress_refusal_reason(ingress, request)
    elif policy is VecDispatchPolicy.LEAST_LOADED:
        selected = (
            min(eligible, key=lambda candidate: _least_loaded_key(candidate, request))
            if eligible
            else None
        )
        if selected is None:
            reason = VecDispatchReason.NO_ELIGIBLE_EXECUTION_RSU
    elif policy is VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION:
        selected = (
            min(eligible, key=lambda candidate: _earliest_completion_key(candidate, request))
            if eligible
            else None
        )
        if selected is None:
            reason = VecDispatchReason.NO_ELIGIBLE_EXECUTION_RSU
    else:
        raise VecDispatchError("DISPATCH_POLICY_UNSUPPORTED", f"unsupported policy {policy!s}")

    eligible_ids = tuple(sorted(candidate.rsu_id for candidate in eligible))
    if selected is None:
        return VecDispatchDecision(
            request_fingerprint=request.fingerprint(),
            snapshot_id=request.snapshot_id,
            task_id=request.task_id,
            decision_order=request.decision_order,
            policy=policy,
            disposition=VecDispatchDisposition.NO_EXECUTION_TARGET,
            reason=reason,
            ingress_rsu_id=request.ingress_rsu_id,
            task_execution_slots=request.task_execution_slots,
            eligible_candidate_ids=eligible_ids,
            forwarded=False,
        )

    reservation_before = selected.reserved_execution_slots
    return VecDispatchDecision(
        request_fingerprint=request.fingerprint(),
        snapshot_id=request.snapshot_id,
        task_id=request.task_id,
        decision_order=request.decision_order,
        policy=policy,
        disposition=VecDispatchDisposition.SELECTED,
        reason=VecDispatchReason.SELECTED,
        ingress_rsu_id=request.ingress_rsu_id,
        task_execution_slots=request.task_execution_slots,
        eligible_candidate_ids=eligible_ids,
        selected_rsu_id=selected.rsu_id,
        forwarded=selected.rsu_id != request.ingress_rsu_id,
        reservation_before=reservation_before,
        reservation_after=reservation_before + request.task_execution_slots,
        selected_projected_load_ppm=_projected_load_ppm(selected, request),
        selected_predicted_completion_ms=selected.predicted_completion_ms,
        selected_forwarding_ms=selected.forwarding_ms,
        selected_forwarding_energy_millijoules=selected.forwarding_energy_millijoules,
    )


def dispatch_vec_batch(
    requests: Sequence[VecDispatchRequest],
    policy: VecDispatchPolicy,
) -> VecDispatchBatchReport:
    """Dispatch an explicit task order while carrying shared reservations forward."""

    if not requests:
        raise VecDispatchError("DISPATCH_BATCH_EMPTY", "at least one dispatch request is required")
    if len(requests) > MAX_DISPATCH_BATCH_REQUESTS:
        raise VecDispatchError(
            "DISPATCH_BATCH_LIMIT_EXCEEDED",
            f"request count exceeds the {MAX_DISPATCH_BATCH_REQUESTS} safety bound",
        )
    snapshot_ids = {request.snapshot_id for request in requests}
    if len(snapshot_ids) != 1:
        raise VecDispatchError(
            "DISPATCH_BATCH_SNAPSHOT_MIXED", "batch requests must bind one snapshot"
        )
    task_ids = [request.task_id for request in requests]
    if len(task_ids) != len(set(task_ids)):
        raise VecDispatchError("DISPATCH_BATCH_TASK_DUPLICATE", "batch task ids must be unique")
    ordered = tuple(sorted(requests, key=lambda request: request.decision_order))
    orders = [request.decision_order for request in ordered]
    if orders != list(range(len(ordered))):
        raise VecDispatchError(
            "DISPATCH_BATCH_ORDER_INVALID",
            "decision_order must be unique and contiguous from zero",
        )

    resource_state: dict[str, tuple[int, int, int]] = {}
    for request in ordered:
        for candidate in request.candidates:
            state = (
                candidate.execution_slot_limit,
                candidate.occupied_execution_slots,
                candidate.reserved_execution_slots,
            )
            previous = resource_state.setdefault(candidate.rsu_id, state)
            if previous != state:
                raise VecDispatchError(
                    "DISPATCH_BATCH_RESOURCE_STATE_MISMATCH",
                    f"RSU {candidate.rsu_id!r} has inconsistent shared slot state",
                )

    initial_reserved = {rsu_id: state[2] for rsu_id, state in resource_state.items()}
    current_reserved = dict(initial_reserved)
    decisions: list[VecDispatchDecision] = []
    for request in ordered:
        updated_candidates = tuple(
            candidate.model_copy(
                update={"reserved_execution_slots": current_reserved[candidate.rsu_id]}
            )
            for candidate in request.candidates
        )
        updated_request = request.model_copy(update={"candidates": updated_candidates})
        decision = dispatch_vec_task(updated_request, policy)
        decisions.append(decision)
        if decision.selected_rsu_id is not None:
            if decision.reservation_after is None:
                raise AssertionError("selected decision has no reservation result")
            current_reserved[decision.selected_rsu_id] = decision.reservation_after

    reservation_summaries = tuple(
        VecDispatchReservationSummary(
            rsu_id=rsu_id,
            initial_reserved_execution_slots=initial_reserved[rsu_id],
            final_reserved_execution_slots=current_reserved[rsu_id],
            newly_reserved_execution_slots=current_reserved[rsu_id] - initial_reserved[rsu_id],
        )
        for rsu_id in sorted(resource_state)
    )
    selected_count = sum(
        decision.disposition is VecDispatchDisposition.SELECTED for decision in decisions
    )
    return VecDispatchBatchReport(
        snapshot_id=next(iter(snapshot_ids)),
        policy=policy,
        input_fingerprint=_requests_fingerprint(ordered),
        request_count=len(decisions),
        selected_count=selected_count,
        unavailable_count=len(decisions) - selected_count,
        forwarded_count=sum(decision.forwarded for decision in decisions),
        decisions=tuple(decisions),
        reservation_summaries=reservation_summaries,
    )


def _is_eligible(candidate: VecDispatchCandidate, request: VecDispatchRequest) -> bool:
    return (
        candidate.reachable
        and candidate.execution_enabled
        and candidate.telemetry_age_ms <= request.max_telemetry_age_ms
        and candidate.execution_headroom >= request.task_execution_slots
    )


def _ingress_refusal_reason(
    ingress: VecDispatchCandidate, request: VecDispatchRequest
) -> VecDispatchReason:
    if not ingress.reachable:
        return VecDispatchReason.INGRESS_UNREACHABLE
    if not ingress.execution_enabled:
        return VecDispatchReason.INGRESS_EXECUTION_DISABLED
    if ingress.telemetry_age_ms > request.max_telemetry_age_ms:
        return VecDispatchReason.INGRESS_TELEMETRY_STALE
    return VecDispatchReason.INGRESS_NO_EXECUTION_HEADROOM


def _least_loaded_key(
    candidate: VecDispatchCandidate,
    request: VecDispatchRequest,
) -> tuple[Fraction, int, int, int, str]:
    projected_slots = (
        candidate.occupied_execution_slots
        + candidate.reserved_execution_slots
        + request.task_execution_slots
    )
    return (
        Fraction(projected_slots, candidate.execution_slot_limit),
        candidate.predicted_completion_ms,
        candidate.forwarding_energy_millijoules,
        -candidate.link_quality_milliunits,
        candidate.rsu_id,
    )


def _earliest_completion_key(
    candidate: VecDispatchCandidate,
    request: VecDispatchRequest,
) -> tuple[int, int, Fraction, int, str]:
    projected_slots = (
        candidate.occupied_execution_slots
        + candidate.reserved_execution_slots
        + request.task_execution_slots
    )
    return (
        candidate.predicted_completion_ms,
        candidate.forwarding_energy_millijoules,
        Fraction(projected_slots, candidate.execution_slot_limit),
        -candidate.link_quality_milliunits,
        candidate.rsu_id,
    )


def _projected_load_ppm(
    candidate: VecDispatchCandidate,
    request: VecDispatchRequest,
) -> int:
    projected_slots = (
        candidate.occupied_execution_slots
        + candidate.reserved_execution_slots
        + request.task_execution_slots
    )
    return projected_slots * 1_000_000 // candidate.execution_slot_limit


def _candidate_by_id(request: VecDispatchRequest, rsu_id: str) -> VecDispatchCandidate:
    for candidate in request.candidates:
        if candidate.rsu_id == rsu_id:
            return candidate
    raise AssertionError("validated ingress candidate is missing")


def _requests_fingerprint(requests: Sequence[VecDispatchRequest]) -> str:
    payload = [request.model_dump(mode="json") for request in requests]
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(material).hexdigest()

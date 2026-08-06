"""Strict contracts for matched synthetic deterministic VEC dispatch studies."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.vec_dispatch import (
    VecDispatchBatchReport,
    VecDispatchDecision,
    VecDispatchDisposition,
    VecDispatchPolicy,
    VecDispatchRequest,
)

VEC_DISPATCH_STUDY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_DISPATCH_STUDY_METHOD_VERSION: Literal["vec-matched-dispatch-study-1.0"] = (
    "vec-matched-dispatch-study-1.0"
)
VEC_DISPATCH_STUDY_RESEARCH_STATUS: Literal["synthetic_structural_comparison"] = (
    "synthetic_structural_comparison"
)
MAX_VEC_DISPATCH_STUDY_REQUESTS = 100_000
MATCHED_VEC_DISPATCH_POLICIES: tuple[VecDispatchPolicy, ...] = (
    VecDispatchPolicy.STRONGEST_LINK_NO_FORWARDING,
    VecDispatchPolicy.LEAST_LOADED,
    VecDispatchPolicy.PREDICTED_EARLIEST_COMPLETION,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class VecDispatchStudyModel(BaseModel):
    """Frozen, finite and fingerprintable base for matched-study artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VecDispatchStudyPlan(VecDispatchStudyModel):
    """One exact synthetic batch compared under the complete deterministic policy set."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_STUDY_SCHEMA_VERSION
    method_version: Literal["vec-matched-dispatch-study-1.0"] = VEC_DISPATCH_STUDY_METHOD_VERSION
    research_status: Literal["synthetic_structural_comparison"] = VEC_DISPATCH_STUDY_RESEARCH_STATUS
    study_id: str
    policies: tuple[VecDispatchPolicy, ...] = MATCHED_VEC_DISPATCH_POLICIES
    requests: tuple[VecDispatchRequest, ...] = Field(
        min_length=1, max_length=MAX_VEC_DISPATCH_STUDY_REQUESTS
    )
    synthetic_fixture: Literal[True] = True
    identical_original_input_required: Literal[True] = True
    actual_lifecycle_outcomes_available: Literal[False] = False
    actor_observation_changed: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @field_validator("study_id")
    @classmethod
    def validate_study_id(cls, value: str) -> str:
        if not _IDENTIFIER_RE.fullmatch(value):
            raise ValueError("study_id must be a bounded portable identifier")
        return value

    @field_validator("requests")
    @classmethod
    def canonicalise_request_order(
        cls, requests: tuple[VecDispatchRequest, ...]
    ) -> tuple[VecDispatchRequest, ...]:
        return tuple(sorted(requests, key=lambda request: request.decision_order))

    @model_validator(mode="after")
    def validate_matched_plan(self) -> Self:
        if self.policies != MATCHED_VEC_DISPATCH_POLICIES:
            raise ValueError("matched study must contain all three policies in canonical order")
        orders = [request.decision_order for request in self.requests]
        if orders != list(range(len(self.requests))):
            raise ValueError("request decision_order must be unique and contiguous from zero")
        task_ids = [request.task_id for request in self.requests]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("matched study task identifiers must be unique")
        if len({request.snapshot_id for request in self.requests}) != 1:
            raise ValueError("matched study requests must bind one candidate snapshot")
        return self


class VecDispatchPolicyOutcome(VecDispatchStudyModel):
    """One policy's exact deterministic decision for a matched task."""

    policy: VecDispatchPolicy
    decision: VecDispatchDecision

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.decision.policy is not self.policy:
            raise ValueError("outcome policy must match its deterministic decision")
        return self


class VecDispatchTaskComparison(VecDispatchStudyModel):
    """All three policy projections for one exact original request."""

    task_id: str
    decision_order: int = Field(ge=0)
    original_request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    outcomes: tuple[VecDispatchPolicyOutcome, ...] = Field(min_length=3, max_length=3)
    route_agreement: bool
    projection_agreement: bool
    actual_execution_outcome_available: Literal[False] = False
    physical_return_outcome_available: Literal[False] = False
    deadline_outcome_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_comparison(self) -> Self:
        if tuple(outcome.policy for outcome in self.outcomes) != MATCHED_VEC_DISPATCH_POLICIES:
            raise ValueError("task outcomes must contain all policies in canonical order")
        if any(
            outcome.decision.task_id != self.task_id
            or outcome.decision.decision_order != self.decision_order
            for outcome in self.outcomes
        ):
            raise ValueError("task outcomes must bind one task and decision order")
        route_signatures = {_route_signature(outcome.decision) for outcome in self.outcomes}
        projection_signatures = {
            _projection_signature(outcome.decision) for outcome in self.outcomes
        }
        if self.route_agreement != (len(route_signatures) == 1):
            raise ValueError("route_agreement does not reconcile with policy outcomes")
        if self.projection_agreement != (len(projection_signatures) == 1):
            raise ValueError("projection_agreement does not reconcile with policy outcomes")
        return self


class VecDispatchRsuProjection(VecDispatchStudyModel):
    """Batch-end execution-slot occupancy plus reservations for one declared RSU."""

    rsu_id: str
    execution_slot_limit: int = Field(ge=1)
    initial_occupied_execution_slots: int = Field(ge=0)
    initial_reserved_execution_slots: int = Field(ge=0)
    newly_reserved_execution_slots: int = Field(ge=0)
    final_reserved_execution_slots: int = Field(ge=0)
    final_occupied_plus_reserved_slots: int = Field(ge=0)
    final_projected_load_ppm: int = Field(ge=0, le=1_000_000)
    selected_task_count: int = Field(ge=0)
    selected_execution_slots: int = Field(ge=0)
    processor_utilisation: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> Self:
        if self.final_reserved_execution_slots != (
            self.initial_reserved_execution_slots + self.newly_reserved_execution_slots
        ):
            raise ValueError("final reservations must reconcile with initial and new slots")
        if self.selected_execution_slots != self.newly_reserved_execution_slots:
            raise ValueError("selected execution slots must equal newly reserved slots")
        if self.final_occupied_plus_reserved_slots != (
            self.initial_occupied_execution_slots + self.final_reserved_execution_slots
        ):
            raise ValueError("final slot population must reconcile")
        if self.final_occupied_plus_reserved_slots > self.execution_slot_limit:
            raise ValueError("final slot population cannot exceed the execution-slot ceiling")
        expected_ppm = (
            self.final_occupied_plus_reserved_slots * 1_000_000 // self.execution_slot_limit
        )
        if self.final_projected_load_ppm != expected_ppm:
            raise ValueError("projected load must be the exact integer slot fraction")
        return self


class VecDispatchPolicySummary(VecDispatchStudyModel):
    """Deterministic integer projections for one policy, without outcome ranking."""

    policy: VecDispatchPolicy
    batch_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_count: int = Field(ge=1)
    selected_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    forwarded_count: int = Field(ge=0)
    selected_execution_slots: int = Field(ge=0)
    selected_predicted_completion_ms_sum: int = Field(ge=0)
    selected_forwarding_ms_sum: int = Field(ge=0)
    selected_forwarding_energy_millijoules_sum: int = Field(ge=0)
    rsu_projections: tuple[VecDispatchRsuProjection, ...] = Field(min_length=1)
    measured_latency_available: Literal[False] = False
    measured_energy_available: Literal[False] = False
    actual_execution_count_available: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.request_count != self.selected_count + self.unavailable_count:
            raise ValueError("policy requests must reconcile into selected and unavailable")
        if self.forwarded_count > self.selected_count:
            raise ValueError("forwarded tasks cannot exceed selected tasks")
        ids = [projection.rsu_id for projection in self.rsu_projections]
        if ids != sorted(set(ids)):
            raise ValueError("RSU projections must be unique and canonically ordered")
        if self.selected_count != sum(
            projection.selected_task_count for projection in self.rsu_projections
        ):
            raise ValueError("selected task count must reconcile across RSUs")
        if self.selected_execution_slots != sum(
            projection.selected_execution_slots for projection in self.rsu_projections
        ):
            raise ValueError("selected execution slots must reconcile across RSUs")
        return self


class VecDispatchStudyReport(VecDispatchStudyModel):
    """Complete matched all-policy structural comparison over one synthetic batch."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_STUDY_SCHEMA_VERSION
    method_version: Literal["vec-matched-dispatch-study-1.0"] = VEC_DISPATCH_STUDY_METHOD_VERSION
    research_status: Literal["synthetic_structural_comparison"] = VEC_DISPATCH_STUDY_RESEARCH_STATUS
    plan: VecDispatchStudyPlan
    plan_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    common_input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_count: int = Field(ge=1)
    policy_reports: tuple[VecDispatchBatchReport, ...] = Field(min_length=3, max_length=3)
    policy_summaries: tuple[VecDispatchPolicySummary, ...] = Field(min_length=3, max_length=3)
    task_comparisons: tuple[VecDispatchTaskComparison, ...] = Field(min_length=1)
    route_agreement_task_count: int = Field(ge=0)
    route_disagreement_task_count: int = Field(ge=0)
    projection_agreement_task_count: int = Field(ge=0)
    projection_disagreement_task_count: int = Field(ge=0)
    identical_original_input_holds: Literal[True] = True
    reservation_conservation_holds: Literal[True] = True
    predictions_are_caller_supplied: Literal[True] = True
    winner_selected: Literal[False] = False
    native_evaluator_input: Literal[False] = False
    lifecycle_outcomes_joined: Literal[False] = False
    learned_scheduler_compared: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.plan_fingerprint != self.plan.fingerprint():
            raise ValueError("plan fingerprint mismatch")
        if self.request_count != len(self.plan.requests):
            raise ValueError("report request count does not match the plan")
        policies = tuple(report.policy for report in self.policy_reports)
        if policies != MATCHED_VEC_DISPATCH_POLICIES:
            raise ValueError("policy reports must contain all policies in canonical order")
        if tuple(summary.policy for summary in self.policy_summaries) != policies:
            raise ValueError("policy summaries must align with policy reports")
        if any(
            report.input_fingerprint != self.common_input_fingerprint
            or report.request_count != self.request_count
            for report in self.policy_reports
        ):
            raise ValueError("every policy report must bind the identical original input")
        if len(self.task_comparisons) != self.request_count:
            raise ValueError("every request must have one task comparison")
        if self.route_agreement_task_count != sum(
            comparison.route_agreement for comparison in self.task_comparisons
        ):
            raise ValueError("route agreement count does not reconcile")
        if self.route_disagreement_task_count != (
            self.request_count - self.route_agreement_task_count
        ):
            raise ValueError("route disagreement count does not reconcile")
        if self.projection_agreement_task_count != sum(
            comparison.projection_agreement for comparison in self.task_comparisons
        ):
            raise ValueError("projection agreement count does not reconcile")
        if self.projection_disagreement_task_count != (
            self.request_count - self.projection_agreement_task_count
        ):
            raise ValueError("projection disagreement count does not reconcile")
        self._validate_policy_products()
        self._validate_task_products()
        return self

    def _validate_policy_products(self) -> None:
        resources = _resource_state(self.plan.requests)
        for report, summary in zip(self.policy_reports, self.policy_summaries, strict=True):
            selected = [
                decision
                for decision in report.decisions
                if decision.disposition is VecDispatchDisposition.SELECTED
            ]
            expected_values = (
                report.fingerprint(),
                report.request_count,
                report.selected_count,
                report.unavailable_count,
                report.forwarded_count,
                sum(decision.task_execution_slots for decision in selected),
                sum(_required(decision.selected_predicted_completion_ms) for decision in selected),
                sum(_required(decision.selected_forwarding_ms) for decision in selected),
                sum(
                    _required(decision.selected_forwarding_energy_millijoules)
                    for decision in selected
                ),
            )
            actual_values = (
                summary.batch_report_fingerprint,
                summary.request_count,
                summary.selected_count,
                summary.unavailable_count,
                summary.forwarded_count,
                summary.selected_execution_slots,
                summary.selected_predicted_completion_ms_sum,
                summary.selected_forwarding_ms_sum,
                summary.selected_forwarding_energy_millijoules_sum,
            )
            if actual_values != expected_values:
                raise ValueError("policy summary does not reconcile with its batch report")
            expected_projections = _expected_rsu_projections(resources, report)
            if summary.rsu_projections != expected_projections:
                raise ValueError("RSU projections do not reconcile with plan and reservations")

    def _validate_task_products(self) -> None:
        requests = {request.decision_order: request for request in self.plan.requests}
        comparisons = {item.decision_order: item for item in self.task_comparisons}
        if set(comparisons) != set(requests):
            raise ValueError("task comparisons do not cover the planned decision orders")
        for order, request in requests.items():
            comparison = comparisons[order]
            if (
                comparison.task_id != request.task_id
                or comparison.original_request_fingerprint != request.fingerprint()
            ):
                raise ValueError("task comparison does not bind its original request")
            expected = tuple(report.decisions[order] for report in self.policy_reports)
            actual = tuple(outcome.decision for outcome in comparison.outcomes)
            if actual != expected:
                raise ValueError("task comparison decisions do not match policy reports")


class VecDispatchStudyContract(VecDispatchStudyModel):
    """Machine-readable scope and scientific boundaries for the v1 harness."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_STUDY_SCHEMA_VERSION
    method_version: Literal["vec-matched-dispatch-study-1.0"] = VEC_DISPATCH_STUDY_METHOD_VERSION
    research_status: Literal["synthetic_structural_comparison"] = VEC_DISPATCH_STUDY_RESEARCH_STATUS
    policies: tuple[VecDispatchPolicy, ...] = MATCHED_VEC_DISPATCH_POLICIES
    input_kind: Literal["synthetic_fixture"] = "synthetic_fixture"
    identical_original_input_required: Literal[True] = True
    reservation_aware: Literal[True] = True
    winner_ranking_available: Literal[False] = False
    actual_lifecycle_outcomes_available: Literal[False] = False
    native_evaluator_input_available: Literal[False] = False
    learned_scheduler_available: Literal[False] = False
    scientific_evidence: Literal[False] = False
    limitations: tuple[str, ...] = (
        "predicted completion and forwarding costs are caller-supplied projections",
        "execution-slot occupancy plus reservations is not processor utilisation or service rate",
        "selection does not prove execution, physical return or deadline attainment",
        "the v1 harness compares no learned scheduler and performs no actor retraining",
        "no policy winner or scientific benefit is inferred from structural projections",
    )


def vec_dispatch_study_contract() -> VecDispatchStudyContract:
    """Return the stable matched deterministic dispatch-study contract."""

    return VecDispatchStudyContract()


def _route_signature(decision: VecDispatchDecision) -> tuple[object, ...]:
    return decision.disposition, decision.selected_rsu_id, decision.forwarded


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
                raise ValueError("plan contains inconsistent shared RSU slot state")
    return resources


def _expected_rsu_projections(
    resources: dict[str, tuple[int, int, int]],
    report: VecDispatchBatchReport,
) -> tuple[VecDispatchRsuProjection, ...]:
    reservations = {item.rsu_id: item for item in report.reservation_summaries}
    if set(reservations) != set(resources):
        raise ValueError("reservation report does not cover the declared RSUs")
    projections: list[VecDispatchRsuProjection] = []
    for rsu_id in sorted(resources):
        limit, occupied, initial_reserved = resources[rsu_id]
        reservation = reservations[rsu_id]
        selected = [item for item in report.decisions if item.selected_rsu_id == rsu_id]
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
                selected_task_count=len(selected),
                selected_execution_slots=sum(item.task_execution_slots for item in selected),
            )
        )
    return tuple(projections)


def _required(value: int | None) -> int:
    if value is None:
        raise ValueError("selected decision is missing required projection data")
    return value

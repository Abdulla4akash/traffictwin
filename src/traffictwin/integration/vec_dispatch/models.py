"""Strict contracts for deterministic downstream V2I execution-RSU dispatch."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.enums import Decision

VEC_DISPATCH_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_DISPATCH_METHOD_VERSION: Literal["vec-deterministic-dispatch-1.0"] = (
    "vec-deterministic-dispatch-1.0"
)
VEC_DISPATCH_RESEARCH_STATUS: Literal["provisional_deterministic_software"] = (
    "provisional_deterministic_software"
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class VecDispatchModel(BaseModel):
    """Frozen, finite and deterministic base for dispatcher artifacts."""

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


class VecDispatchPolicy(StrEnum):
    """Closed deterministic policy set for the first downstream comparison."""

    STRONGEST_LINK_NO_FORWARDING = "strongest_link_no_forwarding"
    LEAST_LOADED = "least_loaded"
    PREDICTED_EARLIEST_COMPLETION = "predicted_earliest_completion"


class VecDispatchDisposition(StrEnum):
    """Whether the dispatcher created an execution reservation."""

    SELECTED = "selected"
    NO_EXECUTION_TARGET = "no_execution_target"


class VecDispatchReason(StrEnum):
    """Closed selection or refusal reasons."""

    SELECTED = "selected"
    INGRESS_UNREACHABLE = "ingress_unreachable"
    INGRESS_EXECUTION_DISABLED = "ingress_execution_disabled"
    INGRESS_TELEMETRY_STALE = "ingress_telemetry_stale"
    INGRESS_NO_EXECUTION_HEADROOM = "ingress_no_execution_headroom"
    NO_ELIGIBLE_EXECUTION_RSU = "no_eligible_execution_rsu"


class VecDispatchCandidate(VecDispatchModel):
    """One complete execution-RSU candidate under a common information budget."""

    rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    reachable: bool = True
    execution_enabled: bool = True
    link_quality_milliunits: int = Field(ge=0, le=1_000)
    execution_slot_limit: int = Field(ge=1, le=4_096)
    occupied_execution_slots: int = Field(ge=0, le=4_096)
    reserved_execution_slots: int = Field(ge=0, le=4_096)
    telemetry_age_ms: int = Field(ge=0, le=1_000_000_000)
    forwarding_ms: int = Field(ge=0, le=1_000_000_000)
    forwarding_energy_millijoules: int = Field(ge=0, le=1_000_000_000)
    predicted_queue_wait_ms: int = Field(ge=0, le=1_000_000_000)
    predicted_compute_ms: int = Field(ge=0, le=1_000_000_000)
    predicted_return_ms: int = Field(ge=0, le=1_000_000_000)

    @model_validator(mode="after")
    def validate_slot_population(self) -> Self:
        if self.occupied_execution_slots + self.reserved_execution_slots > (
            self.execution_slot_limit
        ):
            raise ValueError("occupied plus reserved execution slots cannot exceed the ceiling")
        return self

    @property
    def execution_headroom(self) -> int:
        return (
            self.execution_slot_limit
            - self.occupied_execution_slots
            - self.reserved_execution_slots
        )

    @property
    def predicted_completion_ms(self) -> int:
        return (
            self.forwarding_ms
            + self.predicted_queue_wait_ms
            + self.predicted_compute_ms
            + self.predicted_return_ms
        )


class VecDispatchRequest(VecDispatchModel):
    """One V2I task and its complete post-ingress candidate snapshot."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_SCHEMA_VERSION
    method_version: Literal["vec-deterministic-dispatch-1.0"] = VEC_DISPATCH_METHOD_VERSION
    research_status: Literal["provisional_deterministic_software"] = VEC_DISPATCH_RESEARCH_STATUS
    snapshot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    decision_order: int = Field(ge=0, le=1_000_000)
    actor_action: Literal[Decision.V2I] = Decision.V2I
    ingress_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_execution_slots: int = Field(ge=1, le=64)
    max_telemetry_age_ms: int = Field(ge=0, le=1_000_000_000)
    candidates: tuple[VecDispatchCandidate, ...] = Field(min_length=1, max_length=256)
    actor_observation_changed: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @field_validator("candidates")
    @classmethod
    def canonicalise_candidate_order(
        cls, candidates: tuple[VecDispatchCandidate, ...]
    ) -> tuple[VecDispatchCandidate, ...]:
        return tuple(sorted(candidates, key=lambda candidate: candidate.rsu_id))

    @model_validator(mode="after")
    def validate_candidate_snapshot(self) -> Self:
        by_id = {candidate.rsu_id: candidate for candidate in self.candidates}
        if len(by_id) != len(self.candidates):
            raise ValueError("candidate RSU identifiers must be unique")
        ingress = by_id.get(self.ingress_rsu_id)
        if ingress is None:
            raise ValueError("ingress RSU must be present in the candidate snapshot")
        if ingress.forwarding_ms != 0 or ingress.forwarding_energy_millijoules != 0:
            raise ValueError("ingress RSU must have zero forwarding delay and energy")
        reachable = [candidate for candidate in self.candidates if candidate.reachable]
        if not reachable:
            raise ValueError("at least one candidate, including ingress, must be reachable")
        if not ingress.reachable:
            raise ValueError("the selected ingress RSU must be reachable")
        if ingress.link_quality_milliunits != max(
            candidate.link_quality_milliunits for candidate in reachable
        ):
            raise ValueError("ingress RSU must have maximum link quality among reachable RSUs")
        return self


class VecDispatchDecision(VecDispatchModel):
    """One exact deterministic selection and projected reservation transition."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_SCHEMA_VERSION
    method_version: Literal["vec-deterministic-dispatch-1.0"] = VEC_DISPATCH_METHOD_VERSION
    research_status: Literal["provisional_deterministic_software"] = VEC_DISPATCH_RESEARCH_STATUS
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    decision_order: int = Field(ge=0)
    policy: VecDispatchPolicy
    disposition: VecDispatchDisposition
    reason: VecDispatchReason
    ingress_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_execution_slots: int = Field(ge=1, le=64)
    eligible_candidate_ids: tuple[str, ...]
    selected_rsu_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    forwarded: bool
    reservation_before: int | None = Field(default=None, ge=0)
    reservation_after: int | None = Field(default=None, ge=0)
    selected_projected_load_ppm: int | None = Field(default=None, ge=0, le=1_000_000)
    selected_predicted_completion_ms: int | None = Field(default=None, ge=0)
    selected_forwarding_ms: int | None = Field(default=None, ge=0)
    selected_forwarding_energy_millijoules: int | None = Field(default=None, ge=0)
    actor_observation_changed: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    execution_confirmed: Literal[False] = False
    physical_return_confirmed: Literal[False] = False
    deadline_outcome_available: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def validate_selection(self) -> Self:
        if self.eligible_candidate_ids != tuple(sorted(set(self.eligible_candidate_ids))):
            raise ValueError("eligible candidate ids must be unique and canonically ordered")
        metadata = (
            self.reservation_before,
            self.reservation_after,
            self.selected_projected_load_ppm,
            self.selected_predicted_completion_ms,
            self.selected_forwarding_ms,
            self.selected_forwarding_energy_millijoules,
        )
        if self.disposition is VecDispatchDisposition.SELECTED:
            if self.reason is not VecDispatchReason.SELECTED or self.selected_rsu_id is None:
                raise ValueError("a selected decision requires selected reason and RSU")
            if self.selected_rsu_id not in self.eligible_candidate_ids:
                raise ValueError("selected RSU must be in the eligible candidate set")
            if any(value is None for value in metadata):
                raise ValueError("a selected decision requires complete reservation and cost data")
            if self.reservation_after is None or self.reservation_before is None:
                raise AssertionError("validated reservation metadata is missing")
            if self.reservation_after <= self.reservation_before:
                raise ValueError("selected reservation must increase the reserved population")
            if self.reservation_after - self.reservation_before != self.task_execution_slots:
                raise ValueError("reservation increase must equal the task execution-slot demand")
            if self.forwarded != (self.selected_rsu_id != self.ingress_rsu_id):
                raise ValueError("forwarded must agree with ingress and selected RSUs")
        else:
            if self.reason is VecDispatchReason.SELECTED or self.selected_rsu_id is not None:
                raise ValueError("an unavailable decision cannot contain a selected RSU")
            if any(value is not None for value in metadata) or self.forwarded:
                raise ValueError("an unavailable decision cannot contain reservation or cost data")
        return self


class VecDispatchReservationSummary(VecDispatchModel):
    """Initial and final shared reservation population for one batch RSU."""

    rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    initial_reserved_execution_slots: int = Field(ge=0)
    final_reserved_execution_slots: int = Field(ge=0)
    newly_reserved_execution_slots: int = Field(ge=0)

    @model_validator(mode="after")
    def reconcile_reservations(self) -> Self:
        if self.final_reserved_execution_slots != (
            self.initial_reserved_execution_slots + self.newly_reserved_execution_slots
        ):
            raise ValueError("final reservations must reconcile with newly reserved slots")
        return self


class VecDispatchBatchReport(VecDispatchModel):
    """Reservation-aware deterministic results for one explicitly ordered task batch."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_SCHEMA_VERSION
    method_version: Literal["vec-deterministic-dispatch-1.0"] = VEC_DISPATCH_METHOD_VERSION
    research_status: Literal["provisional_deterministic_software"] = VEC_DISPATCH_RESEARCH_STATUS
    snapshot_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    policy: VecDispatchPolicy
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_count: int = Field(ge=1)
    selected_count: int = Field(ge=0)
    unavailable_count: int = Field(ge=0)
    forwarded_count: int = Field(ge=0)
    decisions: tuple[VecDispatchDecision, ...] = Field(min_length=1)
    reservation_summaries: tuple[VecDispatchReservationSummary, ...] = Field(min_length=1)
    task_count_conservation_holds: Literal[True] = True
    input_order_independent: Literal[True] = True
    actor_observation_changed: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    scientific_evidence: Literal[False] = False

    @model_validator(mode="after")
    def reconcile_counts(self) -> Self:
        if self.request_count != len(self.decisions):
            raise ValueError("every request must produce exactly one decision")
        if self.request_count != self.selected_count + self.unavailable_count:
            raise ValueError("requests must reconcile into selected or unavailable decisions")
        if self.selected_count != sum(
            decision.disposition is VecDispatchDisposition.SELECTED for decision in self.decisions
        ):
            raise ValueError("selected decision count does not reconcile")
        if self.forwarded_count != sum(decision.forwarded for decision in self.decisions):
            raise ValueError("forwarded decision count does not reconcile")
        if any(
            decision.snapshot_id != self.snapshot_id or decision.policy is not self.policy
            for decision in self.decisions
        ):
            raise ValueError("every decision must bind the batch snapshot and policy")
        task_ids = [decision.task_id for decision in self.decisions]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("batch decisions must bind unique tasks")
        orders = [decision.decision_order for decision in self.decisions]
        if orders != list(range(self.request_count)):
            raise ValueError("batch decisions must use contiguous deterministic order")
        summary_ids = [summary.rsu_id for summary in self.reservation_summaries]
        if summary_ids != sorted(set(summary_ids)):
            raise ValueError("reservation summaries must be unique and canonically ordered")
        reserved_slots = sum(
            decision.task_execution_slots
            for decision in self.decisions
            if decision.disposition is VecDispatchDisposition.SELECTED
        )
        if reserved_slots != sum(
            summary.newly_reserved_execution_slots for summary in self.reservation_summaries
        ):
            raise ValueError("selected task slots must reconcile with new shared reservations")
        return self


class VecDispatchContract(VecDispatchModel):
    """Machine-readable information and algorithm boundary for dispatcher v1."""

    schema_version: Literal["1.0"] = VEC_DISPATCH_SCHEMA_VERSION
    method_version: Literal["vec-deterministic-dispatch-1.0"] = VEC_DISPATCH_METHOD_VERSION
    research_status: Literal["provisional_deterministic_software"] = VEC_DISPATCH_RESEARCH_STATUS
    policies: tuple[VecDispatchPolicy, ...] = tuple(VecDispatchPolicy)
    prediction_origin: Literal["post_ingress_dispatch"] = "post_ingress_dispatch"
    load_semantics: Literal["execution_slot_occupancy_plus_reservations"] = (
        "execution_slot_occupancy_plus_reservations"
    )
    common_candidate_fields: tuple[str, ...] = (
        "reachable",
        "execution_enabled",
        "link_quality_milliunits",
        "execution_slot_limit",
        "occupied_execution_slots",
        "reserved_execution_slots",
        "telemetry_age_ms",
        "forwarding_ms",
        "forwarding_energy_millijoules",
        "predicted_queue_wait_ms",
        "predicted_compute_ms",
        "predicted_return_ms",
    )
    actor_action: Literal[Decision.V2I] = Decision.V2I
    actor_observation_changed: Literal[False] = False
    actor_retraining_required: Literal[False] = False
    native_evaluator_adapter_available: Literal[False] = False
    scientific_evidence: Literal[False] = False
    limitations: tuple[str, ...] = (
        "execution-slot ceilings and reservations are not processor speed or service rate",
        "predicted costs are caller-supplied and are not inferred from current evaluator arrays",
        "selection and reservation do not prove execution, return or deadline attainment",
        "the batch order is explicit and deterministic rather than a concurrency-time model",
        "the contract contains no learned scheduler or actor retraining",
    )


def vec_dispatch_contract() -> VecDispatchContract:
    """Return the deterministic dispatcher v1 contract."""

    return VecDispatchContract()

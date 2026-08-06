"""Deterministic synthetic two-RSU hand calculation for lifecycle validation."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_task_lifecycle.models import (
    VecTaskLifecycleEvent,
    VecTaskLifecycleEventKind,
    VecTaskLifecycleModel,
    VecTaskLifecycleReport,
    VecTaskNodeKind,
)
from traffictwin.integration.vec_task_lifecycle.service import validate_vec_task_lifecycle

TWO_RSU_HANDCHECK_SCHEMA_VERSION: Literal["1.0"] = "1.0"
TWO_RSU_HANDCHECK_METHOD_VERSION: Literal["vec-two-rsu-handcheck-1.0"] = "vec-two-rsu-handcheck-1.0"
TWO_RSU_HANDCHECK_RESEARCH_STATUS: Literal["synthetic_provisional_reference_case"] = (
    "synthetic_provisional_reference_case"
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"


class TwoRsuHandcheckError(ValueError):
    """Typed refusal for a reference case that no longer matches its hand calculation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TwoRsuExecutionState(VecTaskLifecycleModel):
    """Declared execution-slot state at the reference decision instant."""

    rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    link_quality_milliunits: int = Field(ge=0, le=1_000)
    execution_slot_limit: int = Field(ge=1, le=1_024)
    occupied_execution_slots: int = Field(ge=0, le=1_024)

    @model_validator(mode="after")
    def validate_occupancy(self) -> Self:
        if self.occupied_execution_slots > self.execution_slot_limit:
            raise ValueError("occupied execution slots cannot exceed the declared limit")
        return self

    @property
    def execution_headroom(self) -> int:
        return self.execution_slot_limit - self.occupied_execution_slots


class TwoRsuExecutionReservation(VecTaskLifecycleModel):
    """One exact execution-slot reservation and release for the reference task."""

    task_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    slots: int = Field(ge=1, le=1_024)
    created_at_ms: int = Field(ge=0)
    released_at_ms: int = Field(ge=0)
    occupied_before: int = Field(ge=0, le=1_024)
    occupied_after_creation: int = Field(ge=0, le=1_024)
    occupied_after_release: int = Field(ge=0, le=1_024)

    @model_validator(mode="after")
    def validate_times(self) -> Self:
        if self.released_at_ms < self.created_at_ms:
            raise ValueError("reservation release cannot precede creation")
        return self


class TwoRsuHandcheckCase(VecTaskLifecycleModel):
    """Frozen inputs and native-shaped events for one hand-calculated case."""

    schema_version: Literal["1.0"] = TWO_RSU_HANDCHECK_SCHEMA_VERSION
    method_version: Literal["vec-two-rsu-handcheck-1.0"] = TWO_RSU_HANDCHECK_METHOD_VERSION
    research_status: Literal["synthetic_provisional_reference_case"] = (
        TWO_RSU_HANDCHECK_RESEARCH_STATUS
    )
    run_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    origin_vehicle_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    action: Literal[Decision.V2I] = Decision.V2I
    rsus: tuple[TwoRsuExecutionState, TwoRsuExecutionState]
    ingress_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    execution_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_execution_slots: Literal[1] = 1
    ingress_transmission_ms: int = Field(ge=0)
    forwarding_ms: int = Field(ge=0)
    queue_wait_ms: int = Field(ge=0)
    compute_ms: int = Field(ge=0)
    return_ms: int = Field(ge=0)
    forwarding_energy_rate_millijoules_per_ms: int = Field(ge=0)
    forwarding_energy_millijoules: int = Field(ge=0)
    deadline_ms: int = Field(ge=0)
    reservation: TwoRsuExecutionReservation
    events: tuple[VecTaskLifecycleEvent, ...] = Field(min_length=1, max_length=32)
    scheduler_included: Literal[False] = False
    native_evaluator_validated: Literal[False] = False
    scientific_evidence: Literal[False] = False
    assumptions: tuple[str, ...] = (
        "strongest link chooses ingress only; this fixture predeclares execution at the sole "
        "RSU with slot headroom",
        "application admission at ingress and execution reservation at the destination are "
        "atomic at the admitted timestamp",
        "execution-slot occupancy is a concurrency boundary, not processor speed, worker count "
        "or service rate",
        "RSU A initial occupancy is a declared boundary condition outside the one-task "
        "validation cohort",
        "all task timings and forwarding-energy values are synthetic integer reference quantities",
    )

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        rsu_ids = {state.rsu_id for state in self.rsus}
        if len(rsu_ids) != 2:
            raise ValueError("the hand check requires exactly two distinct RSUs")
        if self.ingress_rsu_id not in rsu_ids or self.execution_rsu_id not in rsu_ids:
            raise ValueError("ingress and execution RSUs must reference the declared pair")
        if self.ingress_rsu_id == self.execution_rsu_id:
            raise ValueError("the hand check requires one explicit forwarding hop")
        if self.reservation.task_id != self.task_id:
            raise ValueError("reservation task must match the reference task")
        return self


class TwoRsuHandcheckReport(VecTaskLifecycleModel):
    """Machine-readable proof that the reference arithmetic reconciles exactly."""

    schema_version: Literal["1.0"] = TWO_RSU_HANDCHECK_SCHEMA_VERSION
    method_version: Literal["vec-two-rsu-handcheck-1.0"] = TWO_RSU_HANDCHECK_METHOD_VERSION
    research_status: Literal["synthetic_provisional_reference_case"] = (
        TWO_RSU_HANDCHECK_RESEARCH_STATUS
    )
    case_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle_report: VecTaskLifecycleReport
    ingress_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    execution_rsu_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    ingress_headroom_before: int = Field(ge=0)
    execution_headroom_before: int = Field(ge=0)
    reservation_slots: int = Field(ge=1)
    forwarding_hops: Literal[1] = 1
    forwarding_ms: int = Field(ge=0)
    forwarding_energy_millijoules: int = Field(ge=0)
    end_to_end_ms: int = Field(ge=0)
    deadline_ms: int = Field(ge=0)
    deadline_met: bool
    ingress_is_unique_strongest_link: Literal[True] = True
    ingress_execution_slots_full: Literal[True] = True
    execution_rsu_is_weaker_link_with_headroom: Literal[True] = True
    reservation_reconciles: Literal[True] = True
    timing_and_cost_reconcile: Literal[True] = True
    execution_location_reconciles: Literal[True] = True
    task_count_conservation_holds: Literal[True] = True
    scheduler_included: Literal[False] = False
    native_evaluator_validated: Literal[False] = False
    scientific_evidence: Literal[False] = False
    limitations: tuple[str, ...] = (
        "the case validates one synthetic fixture and is not a reusable scheduler",
        "the initial RSU A occupant is an external boundary condition, not a lifecycle task",
        "execution slots do not represent processor speed, service rate, workers or bandwidth",
        "passing the oracle does not validate the current evaluator or producer semantics",
    )


def build_two_rsu_handcheck_case() -> TwoRsuHandcheckCase:
    """Build the canonical integer-arithmetic strong-link-full reference case."""

    run_id = "synthetic-two-rsu-handcheck"
    task_id = "task-reference-1"
    origin = "vehicle-reference-1"
    ingress = "rsu-a-strong-full"
    execution = "rsu-b-weaker-idle"

    events = (
        _event(run_id, task_id, 0, 0, VecTaskLifecycleEventKind.OFFERED, node_id=origin),
        _event(
            run_id,
            task_id,
            1,
            0,
            VecTaskLifecycleEventKind.ACTION_SELECTED,
            action=Decision.V2I,
        ),
        _event(run_id, task_id, 2, 0, VecTaskLifecycleEventKind.INGRESS_ASSIGNED, node_id=ingress),
        _event(run_id, task_id, 3, 2, VecTaskLifecycleEventKind.ADMITTED, node_id=ingress),
        _event(
            run_id,
            task_id,
            4,
            6,
            VecTaskLifecycleEventKind.FORWARDED,
            node_id=execution,
            source_node_id=ingress,
        ),
        _event(
            run_id,
            task_id,
            5,
            8,
            VecTaskLifecycleEventKind.EXECUTION_STARTED,
            node_id=execution,
        ),
        _event(
            run_id,
            task_id,
            6,
            18,
            VecTaskLifecycleEventKind.EXECUTION_COMPLETED,
            node_id=execution,
        ),
        _event(
            run_id,
            task_id,
            7,
            23,
            VecTaskLifecycleEventKind.RESULT_RETURNED,
            node_id=origin,
            source_node_id=execution,
        ),
        _event(
            run_id,
            task_id,
            8,
            23,
            VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
            deadline_met=True,
            modelled_latency_ms=23.0,
        ),
    )
    return TwoRsuHandcheckCase(
        run_id=run_id,
        task_id=task_id,
        origin_vehicle_id=origin,
        rsus=(
            TwoRsuExecutionState(
                rsu_id=ingress,
                link_quality_milliunits=900,
                execution_slot_limit=1,
                occupied_execution_slots=1,
            ),
            TwoRsuExecutionState(
                rsu_id=execution,
                link_quality_milliunits=600,
                execution_slot_limit=1,
                occupied_execution_slots=0,
            ),
        ),
        ingress_rsu_id=ingress,
        execution_rsu_id=execution,
        ingress_transmission_ms=2,
        forwarding_ms=4,
        queue_wait_ms=2,
        compute_ms=10,
        return_ms=5,
        forwarding_energy_rate_millijoules_per_ms=100,
        forwarding_energy_millijoules=400,
        deadline_ms=25,
        reservation=TwoRsuExecutionReservation(
            task_id=task_id,
            rsu_id=execution,
            slots=1,
            created_at_ms=2,
            released_at_ms=18,
            occupied_before=0,
            occupied_after_creation=1,
            occupied_after_release=0,
        ),
        events=events,
    )


def validate_two_rsu_handcheck(case: TwoRsuHandcheckCase) -> TwoRsuHandcheckReport:
    """Recompute and verify every declared state, reservation, cost and outcome."""

    lifecycle = validate_vec_task_lifecycle(case.events)
    _require(
        lifecycle.offered_count == 1
        and lifecycle.admitted_count == 1
        and lifecycle.rejected_count == 0
        and lifecycle.returned_count == 1
        and lifecycle.closed_task_count == 1
        and lifecycle.forwarding_hop_count == 1,
        "TWO_RSU_LIFECYCLE_COUNT_MISMATCH",
        "the reference cohort must contain one admitted, forwarded, returned and closed task",
    )
    _require(
        lifecycle.run_id == case.run_id
        and {event.task_id for event in case.events} == {case.task_id},
        "TWO_RSU_TASK_MISMATCH",
        "all events must belong to the declared reference run and task",
    )

    states = {state.rsu_id: state for state in case.rsus}
    ingress = states[case.ingress_rsu_id]
    execution = states[case.execution_rsu_id]
    strongest_quality = max(state.link_quality_milliunits for state in case.rsus)
    _require(
        ingress.link_quality_milliunits == strongest_quality
        and sum(state.link_quality_milliunits == strongest_quality for state in case.rsus) == 1,
        "TWO_RSU_INGRESS_NOT_UNIQUE_STRONGEST",
        "the declared ingress must be the unique strongest-link RSU",
    )
    _require(
        ingress.execution_headroom < case.task_execution_slots,
        "TWO_RSU_INGRESS_NOT_FULL",
        "the strongest-link ingress must lack execution-slot headroom",
    )
    _require(
        execution.link_quality_milliunits < ingress.link_quality_milliunits
        and execution.execution_headroom >= case.task_execution_slots,
        "TWO_RSU_EXECUTION_NOT_WEAKER_IDLE",
        "the execution RSU must have a weaker link and sufficient slot headroom",
    )

    reservation = case.reservation
    _require(
        reservation.task_id == case.task_id
        and reservation.rsu_id == case.execution_rsu_id
        and reservation.slots == case.task_execution_slots
        and reservation.occupied_before == execution.occupied_execution_slots
        and reservation.occupied_after_creation == reservation.occupied_before + reservation.slots
        and reservation.occupied_after_creation <= execution.execution_slot_limit
        and reservation.occupied_after_release == reservation.occupied_before,
        "TWO_RSU_RESERVATION_MISMATCH",
        "execution reservation creation and release must reconcile with RSU B headroom",
    )

    expected_kinds = (
        VecTaskLifecycleEventKind.OFFERED,
        VecTaskLifecycleEventKind.ACTION_SELECTED,
        VecTaskLifecycleEventKind.INGRESS_ASSIGNED,
        VecTaskLifecycleEventKind.ADMITTED,
        VecTaskLifecycleEventKind.FORWARDED,
        VecTaskLifecycleEventKind.EXECUTION_STARTED,
        VecTaskLifecycleEventKind.EXECUTION_COMPLETED,
        VecTaskLifecycleEventKind.RESULT_RETURNED,
        VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
    )
    ordered = tuple(sorted(case.events, key=lambda event: event.sequence_index))
    _require(
        tuple(event.kind for event in ordered) == expected_kinds,
        "TWO_RSU_EVENT_SEQUENCE_MISMATCH",
        "the reference case requires exactly one event of every lifecycle kind in order",
    )
    by_kind = {event.kind: event for event in ordered}
    offered = by_kind[VecTaskLifecycleEventKind.OFFERED]
    action = by_kind[VecTaskLifecycleEventKind.ACTION_SELECTED]
    ingress_assigned = by_kind[VecTaskLifecycleEventKind.INGRESS_ASSIGNED]
    admitted = by_kind[VecTaskLifecycleEventKind.ADMITTED]
    forwarded = by_kind[VecTaskLifecycleEventKind.FORWARDED]
    started = by_kind[VecTaskLifecycleEventKind.EXECUTION_STARTED]
    completed = by_kind[VecTaskLifecycleEventKind.EXECUTION_COMPLETED]
    returned = by_kind[VecTaskLifecycleEventKind.RESULT_RETURNED]
    deadline = by_kind[VecTaskLifecycleEventKind.DEADLINE_ASSESSED]

    _require(
        case.action is Decision.V2I
        and _node(offered) == (VecTaskNodeKind.LOCAL_VEHICLE, case.origin_vehicle_id)
        and action.action is case.action
        and _node(ingress_assigned) == (VecTaskNodeKind.RSU, case.ingress_rsu_id)
        and _node(admitted) == (VecTaskNodeKind.RSU, case.ingress_rsu_id)
        and _source(forwarded) == (VecTaskNodeKind.RSU, case.ingress_rsu_id)
        and _node(forwarded) == (VecTaskNodeKind.RSU, case.execution_rsu_id)
        and _node(started) == (VecTaskNodeKind.RSU, case.execution_rsu_id)
        and _node(completed) == (VecTaskNodeKind.RSU, case.execution_rsu_id)
        and _source(returned) == (VecTaskNodeKind.RSU, case.execution_rsu_id)
        and _node(returned) == (VecTaskNodeKind.LOCAL_VEHICLE, case.origin_vehicle_id),
        "TWO_RSU_EXECUTION_PATH_MISMATCH",
        "ingress, forwarding, execution and result-return nodes must match the hand calculation",
    )

    _require(
        reservation.created_at_ms == admitted.occurred_at_ms
        and reservation.released_at_ms == completed.occurred_at_ms,
        "TWO_RSU_RESERVATION_TIME_MISMATCH",
        "reservation must be created at admission and released at execution completion",
    )
    intervals = (
        admitted.occurred_at_ms - offered.occurred_at_ms,
        forwarded.occurred_at_ms - admitted.occurred_at_ms,
        started.occurred_at_ms - forwarded.occurred_at_ms,
        completed.occurred_at_ms - started.occurred_at_ms,
        returned.occurred_at_ms - completed.occurred_at_ms,
    )
    expected_intervals = (
        case.ingress_transmission_ms,
        case.forwarding_ms,
        case.queue_wait_ms,
        case.compute_ms,
        case.return_ms,
    )
    end_to_end_ms = sum(expected_intervals)
    _require(
        intervals == expected_intervals
        and returned.occurred_at_ms - offered.occurred_at_ms == end_to_end_ms
        and deadline.occurred_at_ms == returned.occurred_at_ms
        and deadline.modelled_latency_ms == end_to_end_ms,
        "TWO_RSU_TIMING_MISMATCH",
        "event intervals and modelled latency must equal the five hand-calculated components",
    )
    _require(
        case.forwarding_energy_millijoules
        == case.forwarding_ms * case.forwarding_energy_rate_millijoules_per_ms,
        "TWO_RSU_FORWARDING_COST_MISMATCH",
        "forwarding energy must equal duration multiplied by the provisional integer rate",
    )
    expected_deadline_met = end_to_end_ms <= case.deadline_ms
    _require(
        deadline.deadline_met is expected_deadline_met,
        "TWO_RSU_DEADLINE_MISMATCH",
        "deadline outcome must follow the hand-calculated end-to-end latency",
    )

    return TwoRsuHandcheckReport(
        case_fingerprint=case.fingerprint(),
        lifecycle_report=lifecycle,
        ingress_rsu_id=case.ingress_rsu_id,
        execution_rsu_id=case.execution_rsu_id,
        ingress_headroom_before=ingress.execution_headroom,
        execution_headroom_before=execution.execution_headroom,
        reservation_slots=reservation.slots,
        forwarding_ms=case.forwarding_ms,
        forwarding_energy_millijoules=case.forwarding_energy_millijoules,
        end_to_end_ms=end_to_end_ms,
        deadline_ms=case.deadline_ms,
        deadline_met=expected_deadline_met,
    )


def _event(
    run_id: str,
    task_id: str,
    sequence_index: int,
    occurred_at_ms: int,
    kind: VecTaskLifecycleEventKind,
    *,
    node_id: str | None = None,
    source_node_id: str | None = None,
    action: Decision | None = None,
    deadline_met: bool | None = None,
    modelled_latency_ms: float | None = None,
) -> VecTaskLifecycleEvent:
    node_kind = None
    if node_id is not None:
        node_kind = (
            VecTaskNodeKind.LOCAL_VEHICLE if node_id.startswith("vehicle-") else VecTaskNodeKind.RSU
        )
    return VecTaskLifecycleEvent(
        run_id=run_id,
        task_id=task_id,
        sequence_index=sequence_index,
        occurred_at_ms=occurred_at_ms,
        kind=kind,
        action=action,
        node_kind=node_kind,
        node_id=node_id,
        source_node_kind=VecTaskNodeKind.RSU if source_node_id is not None else None,
        source_node_id=source_node_id,
        deadline_met=deadline_met,
        modelled_latency_ms=modelled_latency_ms,
    )


def _node(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind | None, str | None]:
    return event.node_kind, event.node_id


def _source(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind | None, str | None]:
    return event.source_node_kind, event.source_node_id


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise TwoRsuHandcheckError(code, message)

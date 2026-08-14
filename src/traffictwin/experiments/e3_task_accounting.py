# ruff: noqa: E501, SIM102, ANN401
"""Strict typed E3 task accounting - Lane 10 (no results, fail-closed).

Frozen source of truth is docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json
and the dormant manifest. All counts are null with reasons in NOT_EXECUTED state;
unavailable lifecycle fields never coerce to zero. Queue capacity is distinct
from compute capacity, resource cost is resource_unit_seconds. Scaling receipts,
per-RSU summaries, capacity levels, and state-age receipts are typed and remain
null with reasons before execution.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.experiments.e3_research_evidence import REJECTION_CLASSES

# ---------------------------------------------------------------------------
# Reasons - explicit unavailable with first-class null
# ---------------------------------------------------------------------------

OFFERED_REASON: str = "UNAVAILABLE - no E3 research workloads launched, research_workloads_launched = 0, evidence_state = NOT_EXECUTED, result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE"
ADMITTED_REASON: str = (
    "UNAVAILABLE - no E3 cells executed under hold BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
)
REJECTED_TOTAL_REASON: str = (
    "UNAVAILABLE - genuine rejection classes not yet observed; no synthetic counts"
)
FORWARDED_REASON: str = (
    "UNAVAILABLE - forwarding counts null before execution; not zero, not fabricated"
)
DEADLINE_SUCCESS_REASON: str = (
    "UNAVAILABLE - deadline success is simulator outcome, not yet instrumented under hold"
)

GATE_REJECTED_REASON: str = "UNAVAILABLE - v2i_gate_rejected split not yet instrumented; not zero"
CAPACITY_REJECTED_REASON: str = (
    "UNAVAILABLE - v2i_cap_rejected split not yet instrumented; not zero"
)
LOCAL_MQD_REASON: str = "UNAVAILABLE - local_mqd_rejected not yet instrumented; not zero"
V2V_MQD_REASON: str = "UNAVAILABLE - v2v_mqd_rejected not yet instrumented; not zero"
V2I_UNAVAILABLE_REASON: str = "UNAVAILABLE - v2i_unavailable not yet instrumented; not zero"
V2V_UNAVAILABLE_REASON: str = "UNAVAILABLE - v2v_unavailable not yet instrumented; not zero"

STARTED_REASON: str = (
    "UNAVAILABLE as an independently instrumented quantity - started not separately emitted"
)
COMPUTE_COMPLETED_REASON: str = "UNAVAILABLE - compute completion not distinct from deadline_success in current evaluator; not zero"
RETURNED_REASON: str = "UNAVAILABLE - physical return not distinct from deadline_success; not zero"
DROPPED_REASON: str = (
    "UNAVAILABLE - dropped cannot be derived without compute_completed/returned split; not zero"
)

RESOURCE_COST_REASON: str = (
    "UNAVAILABLE - resource_unit_seconds null before execution; not monetary, not zero"
)
SCALING_RECEIPTS_REASON: str = "UNAVAILABLE - scale-action receipts null before execution; not empty list fabricated as evidence"
PER_RSU_REASON: str = "UNAVAILABLE - per-RSU summaries null before execution; not zero"
CAPACITY_LEVELS_REASON: str = "UNAVAILABLE - capacity levels null before execution; not zero"
STATE_AGE_RECEIPTS_REASON: str = "UNAVAILABLE - state-age receipts null before execution; not zero"

CONSERVATION_REASON: str = (
    "UNAVAILABLE - conservation offered == admitted + rejected not yet verified; no E3 cells executed, "
    "research_workloads_launched = 0, evidence_state = NOT_EXECUTED"
)


class UnavailableField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(min_length=1)


class RejectionBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    v2i_gate_rejected: None = None
    v2i_cap_rejected: None = None
    local_mqd_rejected: None = None
    v2v_mqd_rejected: None = None
    v2i_unavailable: None = None
    v2v_unavailable: None = None
    reasons: dict[str, str] = Field(default_factory=dict)

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        # enforce reasons completeness
        object.__setattr__(
            self,
            "reasons",
            {
                "v2i_gate_rejected": GATE_REJECTED_REASON,
                "v2i_cap_rejected": CAPACITY_REJECTED_REASON,
                "local_mqd_rejected": LOCAL_MQD_REASON,
                "v2v_mqd_rejected": V2V_MQD_REASON,
                "v2i_unavailable": V2I_UNAVAILABLE_REASON,
                "v2v_unavailable": V2V_UNAVAILABLE_REASON,
            },
        )


class QueueVsComputeSeparation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    queue_unit: str = Field(default="waiting_room_task_slots")
    compute_unit: str = Field(default="compute_unit")
    is_separate: bool = Field(default=True)
    queue_is_not_compute: Literal[True] = Field(default=True)
    compute_is_not_queue: bool = Field(default=True)
    reason: str = Field(
        default="Queue waiting-room capacity (tasks per RSU, ceiling 6220) is strictly separate from compute service capacity (units 1..3 per RSU draining 1000 work_ms per second per unit)"
    )


class ResourceCostView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(default="resource_unit_seconds")
    monetary: bool = Field(default=False)
    formula: str = Field(
        default="sum_over_RSU sum_over_interval (active_compute_units * interval_seconds) per 1 s interval, normalized resource usage not money"
    )
    value: None = Field(default=None)
    reason: str = Field(default=RESOURCE_COST_REASON)
    is_not_money: bool = Field(default=True)


class ScalingReceiptsView(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    receipts: None = Field(default=None)
    reason: str = Field(default=SCALING_RECEIPTS_REASON)
    per_rsu: None = Field(default=None)
    per_rsu_reason: str = Field(default=PER_RSU_REASON)
    capacity_levels: None = Field(default=None)
    capacity_reason: str = Field(default=CAPACITY_LEVELS_REASON)
    state_age_receipts: None = Field(default=None)
    state_age_reason: str = Field(default=STATE_AGE_RECEIPTS_REASON)


class E3TaskAccountingView(BaseModel):
    """Typed E3 task accounting in NOT_EXECUTED state - all counts null with reasons.

    Conservation and shares are null with reasons before execution; queue and
    compute remain distinct; resource cost is resource_unit_seconds not money.
    Never coerce unavailable to zero.
    """

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    evidence_state: Literal["NOT_EXECUTED"] = Field(default="NOT_EXECUTED")
    result_availability: Literal["NO_E3_RESEARCH_RESULTS_AVAILABLE"] = Field(
        default="NO_E3_RESEARCH_RESULTS_AVAILABLE"
    )
    research_workloads_launched: int = Field(default=0, ge=0, le=0)

    offered: None = Field(default=None)
    offered_reason: str = Field(default=OFFERED_REASON)
    admitted: None = Field(default=None)
    admitted_reason: str = Field(default=ADMITTED_REASON)
    rejected_total: None = Field(default=None)
    rejected_total_reason: str = Field(default=REJECTED_TOTAL_REASON)
    rejected_breakdown: RejectionBreakdown = Field(default_factory=RejectionBreakdown)
    forwarded: None = Field(default=None)
    forwarded_reason: str = Field(default=FORWARDED_REASON)
    deadline_success: None = Field(default=None)
    deadline_success_reason: str = Field(default=DEADLINE_SUCCESS_REASON)

    started: None = Field(default=None)
    started_reason: str = Field(default=STARTED_REASON)
    compute_completed: None = Field(default=None)
    compute_completed_reason: str = Field(default=COMPUTE_COMPLETED_REASON)
    returned: None = Field(default=None)
    returned_reason: str = Field(default=RETURNED_REASON)
    dropped: None = Field(default=None)
    dropped_reason: str = Field(default=DROPPED_REASON)

    conservation_holds: None = Field(default=None)
    conservation_reason: str = Field(default=CONSERVATION_REASON)
    genuine_rejection_classes: tuple[str, ...] = Field(default=REJECTION_CLASSES)

    queue_vs_compute: QueueVsComputeSeparation = Field(default_factory=QueueVsComputeSeparation)
    resource_cost: ResourceCostView = Field(default_factory=ResourceCostView)
    scaling_receipts: ScalingReceiptsView = Field(default_factory=ScalingReceiptsView)

    unavailable: dict[str, UnavailableField] = Field(default_factory=dict)

    def __init__(self, **data: object) -> None:
        # Build unavailable map if not supplied
        if "unavailable" not in data or not isinstance(data["unavailable"], dict):
            data["unavailable"] = {
                "started": UnavailableField(reason=STARTED_REASON),
                "compute_completed": UnavailableField(reason=COMPUTE_COMPLETED_REASON),
                "returned": UnavailableField(reason=RETURNED_REASON),
                "dropped": UnavailableField(reason=DROPPED_REASON),
                "offered": UnavailableField(reason=OFFERED_REASON),
                "admitted": UnavailableField(reason=ADMITTED_REASON),
                "rejected_total": UnavailableField(reason=REJECTED_TOTAL_REASON),
                "forwarded": UnavailableField(reason=FORWARDED_REASON),
                "deadline_success": UnavailableField(reason=DEADLINE_SUCCESS_REASON),
            }
        super().__init__(**data)


def build_e3_task_accounting_view() -> E3TaskAccountingView:
    """Construct the frozen no-results accounting view."""
    return E3TaskAccountingView()


__all__ = [
    "E3TaskAccountingView",
    "RejectionBreakdown",
    "QueueVsComputeSeparation",
    "ResourceCostView",
    "ScalingReceiptsView",
    "UnavailableField",
    "build_e3_task_accounting_view",
    "REJECTION_CLASSES",
]

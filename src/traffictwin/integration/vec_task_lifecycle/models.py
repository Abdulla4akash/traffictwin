"""Strict provisional contracts for a complete VEC per-task lifecycle ledger.

The current audited evaluator does not emit these events.  These models define the
instrumentation boundary a future native producer must satisfy; they never infer
physical lifecycle events from ``task_met`` or modelled latency.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.domain.enums import Decision

VEC_TASK_LIFECYCLE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
VEC_TASK_LIFECYCLE_METHOD_VERSION: Literal["vec-task-lifecycle-1.0"] = "vec-task-lifecycle-1.0"
VEC_TASK_LIFECYCLE_RESEARCH_STATUS: Literal["provisional_instrumentation_contract"] = (
    "provisional_instrumentation_contract"
)

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
_REASON_PATTERN = r"^[A-Z][A-Z0-9_]{1,63}$"


class VecTaskLifecycleModel(BaseModel):
    """Frozen, finite and deterministic base for lifecycle artifacts."""

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


class VecTaskLifecycleEventKind(StrEnum):
    """Closed event vocabulary from offered work to deadline assessment."""

    OFFERED = "offered"
    ACTION_SELECTED = "action_selected"
    INGRESS_ASSIGNED = "ingress_assigned"
    ADMITTED = "admitted"
    REJECTED = "rejected"
    RETAINED = "retained"
    FORWARDED = "forwarded"
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    DROPPED = "dropped"
    RESULT_RETURNED = "result_returned"
    RESULT_RETURN_FAILED = "result_return_failed"
    DEADLINE_ASSESSED = "deadline_assessed"


class VecTaskNodeKind(StrEnum):
    """Execution-path node roles; identifiers remain scenario-local."""

    LOCAL_VEHICLE = "local_vehicle"
    PEER_VEHICLE = "peer_vehicle"
    RSU = "rsu"


class VecTaskLifecycleEvent(VecTaskLifecycleModel):
    """One exact event in one task's monotonically ordered lifecycle."""

    schema_version: Literal["1.0"] = VEC_TASK_LIFECYCLE_SCHEMA_VERSION
    run_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    task_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    sequence_index: int = Field(ge=0, le=1_000_000)
    occurred_at_ms: float = Field(ge=0)
    kind: VecTaskLifecycleEventKind
    action: Decision | None = None
    node_kind: VecTaskNodeKind | None = None
    node_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    source_node_kind: VecTaskNodeKind | None = None
    source_node_id: str | None = Field(default=None, pattern=_IDENTIFIER_PATTERN)
    reason_code: str | None = Field(default=None, pattern=_REASON_PATTERN)
    deadline_met: bool | None = None
    modelled_latency_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_event_payload(self) -> Self:
        if (self.node_kind is None) != (self.node_id is None):
            raise ValueError("node kind and id must be supplied together")
        if (self.source_node_kind is None) != (self.source_node_id is None):
            raise ValueError("source-node kind and id must be supplied together")

        if self.kind is VecTaskLifecycleEventKind.ACTION_SELECTED:
            if self.action not in {Decision.LOCAL, Decision.V2I, Decision.V2V}:
                raise ValueError("action_selected requires one supported local/V2I/V2V action")
        elif self.action is not None:
            raise ValueError("action is recorded only by action_selected")

        node_events = {
            VecTaskLifecycleEventKind.OFFERED,
            VecTaskLifecycleEventKind.INGRESS_ASSIGNED,
            VecTaskLifecycleEventKind.ADMITTED,
            VecTaskLifecycleEventKind.REJECTED,
            VecTaskLifecycleEventKind.RETAINED,
            VecTaskLifecycleEventKind.FORWARDED,
            VecTaskLifecycleEventKind.EXECUTION_STARTED,
            VecTaskLifecycleEventKind.EXECUTION_COMPLETED,
            VecTaskLifecycleEventKind.DROPPED,
            VecTaskLifecycleEventKind.RESULT_RETURNED,
            VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
        }
        if (self.kind in node_events) != (self.node_kind is not None):
            raise ValueError("this event kind has an exact node-payload requirement")
        if (
            self.kind is VecTaskLifecycleEventKind.OFFERED
            and self.node_kind is not VecTaskNodeKind.LOCAL_VEHICLE
        ):
            raise ValueError("offered requires the originating local vehicle")

        transport_events = {
            VecTaskLifecycleEventKind.FORWARDED,
            VecTaskLifecycleEventKind.RESULT_RETURNED,
            VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
        }
        if (self.kind in transport_events) != (self.source_node_kind is not None):
            raise ValueError("forward/return events require exact source and destination nodes")
        if self.kind is VecTaskLifecycleEventKind.FORWARDED and (
            self.source_node_kind == self.node_kind and self.source_node_id == self.node_id
        ):
            raise ValueError("forwarding source and destination must differ")

        reason_events = {
            VecTaskLifecycleEventKind.REJECTED,
            VecTaskLifecycleEventKind.DROPPED,
            VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
        }
        if (self.kind in reason_events) != (self.reason_code is not None):
            raise ValueError("rejection, drop and return-failure events require one reason code")

        if self.kind is VecTaskLifecycleEventKind.DEADLINE_ASSESSED:
            if self.deadline_met is None:
                raise ValueError("deadline assessment requires an outcome")
        elif self.deadline_met is not None or self.modelled_latency_ms is not None:
            raise ValueError("deadline fields are recorded only by deadline_assessed")
        return self


class VecTaskLifecycleReport(VecTaskLifecycleModel):
    """Complete count reconciliation over one validated native lifecycle ledger."""

    schema_version: Literal["1.0"] = VEC_TASK_LIFECYCLE_SCHEMA_VERSION
    method_version: Literal["vec-task-lifecycle-1.0"] = VEC_TASK_LIFECYCLE_METHOD_VERSION
    research_status: Literal["provisional_instrumentation_contract"] = (
        VEC_TASK_LIFECYCLE_RESEARCH_STATUS
    )
    run_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    event_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_count: int = Field(ge=1)
    offered_count: int = Field(ge=1)
    pending_admission_count: int = Field(ge=0)
    admitted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    admitted_in_progress_count: int = Field(ge=0)
    started_count: int = Field(ge=0)
    execution_completed_count: int = Field(ge=0)
    dropped_count: int = Field(ge=0)
    returned_count: int = Field(ge=0)
    return_failed_count: int = Field(ge=0)
    forwarded_task_count: int = Field(ge=0)
    forwarding_hop_count: int = Field(ge=0)
    deadline_assessed_count: int = Field(ge=0)
    deadline_met_count: int = Field(ge=0)
    modelled_latency_observed_count: int = Field(ge=0)
    closed_task_count: int = Field(ge=0)
    require_closed: bool
    closed: bool
    task_count_conservation_holds: Literal[True] = True
    physical_return_is_deadline_attainment: Literal[False] = False
    legacy_task_met_imported: Literal[False] = False
    legacy_evaluator_compatible: Literal[False] = False
    scientific_evidence: Literal[False] = False
    limitations: tuple[str, ...] = (
        "the contract does not authenticate a producer or evaluator implementation",
        "returned_count is explicit physical-result return and is not derived from task_met",
        "deadline_met_count is modelled deadline attainment and is not physical completion",
        "missing modelled latency remains missing and is never imputed from a terminal outcome",
        "task-count conservation does not establish CPU-work or service-budget conservation",
        "service, admission, rejection, forwarding and return semantics remain producer decisions",
        "validation of synthetic or future native events creates no scientific admission",
    )

    @model_validator(mode="after")
    def reconcile_counts(self) -> Self:
        if self.offered_count != (
            self.pending_admission_count + self.admitted_count + self.rejected_count
        ):
            raise ValueError("offered tasks must reconcile into pending, admitted or rejected")
        if self.admitted_count != (
            self.admitted_in_progress_count
            + self.dropped_count
            + self.returned_count
            + self.return_failed_count
        ):
            raise ValueError("admitted tasks must reconcile into in-progress or terminal outcomes")
        if self.started_count > self.admitted_count:
            raise ValueError("started tasks cannot exceed admitted tasks")
        if self.execution_completed_count > self.started_count:
            raise ValueError("execution completions cannot exceed starts")
        if self.returned_count + self.return_failed_count > self.execution_completed_count:
            raise ValueError("return outcomes require execution completion")
        if self.forwarded_task_count > self.admitted_count:
            raise ValueError("forwarded tasks cannot exceed admitted tasks")
        if self.forwarding_hop_count < self.forwarded_task_count:
            raise ValueError("each forwarded task requires at least one forwarding hop")
        if self.deadline_met_count > self.deadline_assessed_count:
            raise ValueError("deadline successes cannot exceed assessed tasks")
        if self.modelled_latency_observed_count > self.deadline_assessed_count:
            raise ValueError("modelled latency observations cannot exceed assessed tasks")
        terminal_count = (
            self.rejected_count
            + self.dropped_count
            + self.returned_count
            + self.return_failed_count
        )
        if self.closed_task_count > terminal_count:
            raise ValueError("only physically terminal tasks can be lifecycle-closed")
        expected_closed = self.closed_task_count == self.offered_count
        if self.closed != expected_closed:
            raise ValueError("closed must agree with complete per-task terminal assessment")
        if self.require_closed and not self.closed:
            raise ValueError("a closed-required report cannot contain open tasks")
        return self


class VecTaskLifecycleContract(VecTaskLifecycleModel):
    """Machine-readable boundary for native lifecycle instrumentation."""

    schema_version: Literal["1.0"] = VEC_TASK_LIFECYCLE_SCHEMA_VERSION
    method_version: Literal["vec-task-lifecycle-1.0"] = VEC_TASK_LIFECYCLE_METHOD_VERSION
    research_status: Literal["provisional_instrumentation_contract"] = (
        VEC_TASK_LIFECYCLE_RESEARCH_STATUS
    )
    event_kinds: tuple[VecTaskLifecycleEventKind, ...] = tuple(VecTaskLifecycleEventKind)
    task_count_conservation_identities: tuple[str, ...] = (
        "offered = pending_admission + admitted + rejected",
        "admitted = admitted_in_progress + dropped + returned + return_failed",
    )
    deadline_semantics: Literal["modelled_deadline_attainment"] = "modelled_deadline_attainment"
    physical_completion_semantics: Literal["explicit_result_return_only"] = (
        "explicit_result_return_only"
    )
    latency_semantics: Literal["optional_modelled_latency_never_imputed"] = (
        "optional_modelled_latency_never_imputed"
    )
    current_evaluator_adapter: Literal["unavailable_missing_native_events"] = (
        "unavailable_missing_native_events"
    )
    scheduler_included: Literal[False] = False
    producer_semantics_approved: Literal[False] = False
    scientific_evidence: Literal[False] = False


def vec_task_lifecycle_contract() -> VecTaskLifecycleContract:
    """Return the deterministic provisional v1 instrumentation contract."""

    return VecTaskLifecycleContract()

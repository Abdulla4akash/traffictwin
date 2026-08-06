"""Fail-closed validation for native VEC task-lifecycle events."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from enum import StrEnum

from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_task_lifecycle.models import (
    VecTaskLifecycleEvent,
    VecTaskLifecycleEventKind,
    VecTaskLifecycleReport,
    VecTaskNodeKind,
)

MAX_LIFECYCLE_EVENTS = 1_000_000


class VecTaskLifecycleError(ValueError):
    """Typed lifecycle refusal with a stable machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class _LifecycleState(StrEnum):
    START = "start"
    OFFERED = "offered"
    ACTION_SELECTED = "action_selected"
    INGRESS_ASSIGNED = "ingress_assigned"
    ADMITTED = "admitted"
    RETAINED = "retained"
    ROUTED = "routed"
    STARTED = "started"
    EXECUTION_COMPLETED = "execution_completed"
    PHYSICAL_TERMINAL = "physical_terminal"
    CLOSED = "closed"


class _TaskSummary:
    def __init__(self) -> None:
        self.admitted = False
        self.rejected = False
        self.started = False
        self.execution_completed = False
        self.dropped = False
        self.returned = False
        self.return_failed = False
        self.forwarding_hops = 0
        self.deadline_assessed = False
        self.deadline_met = False
        self.modelled_latency_observed = False
        self.state = _LifecycleState.START
        self.action: Decision | None = None
        self.origin_node: tuple[VecTaskNodeKind, str] | None = None
        self.current_node: tuple[VecTaskNodeKind, str] | None = None

    @property
    def physically_terminal(self) -> bool:
        return self.rejected or self.dropped or self.returned or self.return_failed

    @property
    def closed(self) -> bool:
        return self.state is _LifecycleState.CLOSED


def validate_vec_task_lifecycle(
    events: Sequence[VecTaskLifecycleEvent],
    *,
    require_closed: bool = True,
) -> VecTaskLifecycleReport:
    """Validate transitions, node continuity and task-count conservation.

    Input order is not trusted. Events are grouped by task and ordered by their
    explicit contiguous ``sequence_index``. Canonical hashing uses that same
    order, so equivalent input permutations produce the same report.
    """

    if not events:
        raise VecTaskLifecycleError("LIFECYCLE_EMPTY", "at least one lifecycle event is required")
    if len(events) > MAX_LIFECYCLE_EVENTS:
        raise VecTaskLifecycleError(
            "LIFECYCLE_EVENT_LIMIT_EXCEEDED",
            f"event count exceeds the {MAX_LIFECYCLE_EVENTS} event safety bound",
        )
    run_ids = {event.run_id for event in events}
    if len(run_ids) != 1:
        raise VecTaskLifecycleError("LIFECYCLE_RUN_MIXED", "all events must bind one run id")
    run_id = next(iter(run_ids))

    by_task: dict[str, list[VecTaskLifecycleEvent]] = defaultdict(list)
    for event in events:
        by_task[event.task_id].append(event)

    summaries: dict[str, _TaskSummary] = {}
    canonical_events: list[VecTaskLifecycleEvent] = []
    for task_id in sorted(by_task):
        ordered = sorted(by_task[task_id], key=lambda item: item.sequence_index)
        indexes = [event.sequence_index for event in ordered]
        if indexes != list(range(len(ordered))):
            code = (
                "LIFECYCLE_SEQUENCE_DUPLICATE"
                if len(indexes) != len(set(indexes))
                else "LIFECYCLE_SEQUENCE_GAP"
            )
            raise VecTaskLifecycleError(
                code, f"task {task_id!r} requires contiguous sequence indexes from zero"
            )
        times = [event.occurred_at_ms for event in ordered]
        if any(later < earlier for earlier, later in zip(times, times[1:], strict=False)):
            raise VecTaskLifecycleError(
                "LIFECYCLE_TIME_REGRESSION", f"task {task_id!r} event time moved backwards"
            )
        summary = _validate_task(task_id, ordered)
        if require_closed and not summary.closed:
            raise VecTaskLifecycleError(
                "LIFECYCLE_INCOMPLETE", f"task {task_id!r} has no closed terminal lifecycle"
            )
        summaries[task_id] = summary
        canonical_events.extend(ordered)

    offered_count = len(summaries)
    admitted_count = sum(item.admitted for item in summaries.values())
    rejected_count = sum(item.rejected for item in summaries.values())
    pending_admission_count = offered_count - admitted_count - rejected_count
    dropped_count = sum(item.dropped for item in summaries.values())
    returned_count = sum(item.returned for item in summaries.values())
    return_failed_count = sum(item.return_failed for item in summaries.values())
    admitted_in_progress_count = (
        admitted_count - dropped_count - returned_count - return_failed_count
    )
    forwarded = [item for item in summaries.values() if item.forwarding_hops]
    closed_task_count = sum(item.closed for item in summaries.values())
    deadline_assessed_count = sum(item.deadline_assessed for item in summaries.values())

    return VecTaskLifecycleReport(
        run_id=run_id,
        event_fingerprint=_events_fingerprint(canonical_events),
        event_count=len(canonical_events),
        offered_count=offered_count,
        pending_admission_count=pending_admission_count,
        admitted_count=admitted_count,
        rejected_count=rejected_count,
        admitted_in_progress_count=admitted_in_progress_count,
        started_count=sum(item.started for item in summaries.values()),
        execution_completed_count=sum(item.execution_completed for item in summaries.values()),
        dropped_count=dropped_count,
        returned_count=returned_count,
        return_failed_count=return_failed_count,
        forwarded_task_count=len(forwarded),
        forwarding_hop_count=sum(item.forwarding_hops for item in summaries.values()),
        deadline_assessed_count=deadline_assessed_count,
        deadline_met_count=sum(item.deadline_met for item in summaries.values()),
        modelled_latency_observed_count=sum(
            item.modelled_latency_observed for item in summaries.values()
        ),
        closed_task_count=closed_task_count,
        require_closed=require_closed,
        closed=closed_task_count == offered_count,
    )


def _validate_task(task_id: str, events: Sequence[VecTaskLifecycleEvent]) -> _TaskSummary:
    summary = _TaskSummary()
    for event in events:
        kind = event.kind
        if summary.state is _LifecycleState.START:
            _require_kind(task_id, kind, VecTaskLifecycleEventKind.OFFERED)
            summary.origin_node = _destination(event)
            summary.state = _LifecycleState.OFFERED
        elif summary.state is _LifecycleState.OFFERED:
            _require_kind(task_id, kind, VecTaskLifecycleEventKind.ACTION_SELECTED)
            summary.action = event.action
            summary.state = _LifecycleState.ACTION_SELECTED
        elif summary.state is _LifecycleState.ACTION_SELECTED:
            _require_kind(task_id, kind, VecTaskLifecycleEventKind.INGRESS_ASSIGNED)
            _validate_ingress_for_action(task_id, summary.action, summary.origin_node, event)
            summary.current_node = _destination(event)
            summary.state = _LifecycleState.INGRESS_ASSIGNED
        elif summary.state is _LifecycleState.INGRESS_ASSIGNED:
            if kind is VecTaskLifecycleEventKind.ADMITTED:
                _require_current_node(task_id, summary.current_node, event)
                summary.admitted = True
                summary.state = _LifecycleState.ADMITTED
            elif kind is VecTaskLifecycleEventKind.REJECTED:
                _require_current_node(task_id, summary.current_node, event)
                summary.rejected = True
                summary.state = _LifecycleState.PHYSICAL_TERMINAL
            else:
                _invalid_transition(task_id, summary.state, kind)
        elif summary.state is _LifecycleState.ADMITTED:
            if kind is VecTaskLifecycleEventKind.RETAINED:
                _require_current_node(task_id, summary.current_node, event)
                summary.state = _LifecycleState.RETAINED
            elif kind is VecTaskLifecycleEventKind.FORWARDED:
                summary.current_node = _validate_forward(task_id, summary.current_node, event)
                summary.forwarding_hops += 1
                summary.state = _LifecycleState.ROUTED
            else:
                _invalid_transition(task_id, summary.state, kind)
        elif summary.state in {_LifecycleState.RETAINED, _LifecycleState.ROUTED}:
            if (
                kind is VecTaskLifecycleEventKind.FORWARDED
                and summary.state is _LifecycleState.ROUTED
            ):
                summary.current_node = _validate_forward(task_id, summary.current_node, event)
                summary.forwarding_hops += 1
            elif kind is VecTaskLifecycleEventKind.EXECUTION_STARTED:
                _require_current_node(task_id, summary.current_node, event)
                summary.started = True
                summary.state = _LifecycleState.STARTED
            elif kind is VecTaskLifecycleEventKind.DROPPED:
                _require_current_node(task_id, summary.current_node, event)
                summary.dropped = True
                summary.state = _LifecycleState.PHYSICAL_TERMINAL
            else:
                _invalid_transition(task_id, summary.state, kind)
        elif summary.state is _LifecycleState.STARTED:
            if kind is VecTaskLifecycleEventKind.EXECUTION_COMPLETED:
                _require_current_node(task_id, summary.current_node, event)
                summary.execution_completed = True
                summary.state = _LifecycleState.EXECUTION_COMPLETED
            elif kind is VecTaskLifecycleEventKind.DROPPED:
                _require_current_node(task_id, summary.current_node, event)
                summary.dropped = True
                summary.state = _LifecycleState.PHYSICAL_TERMINAL
            else:
                _invalid_transition(task_id, summary.state, kind)
        elif summary.state is _LifecycleState.EXECUTION_COMPLETED:
            if kind is VecTaskLifecycleEventKind.RESULT_RETURNED:
                _validate_result_return(task_id, summary.current_node, summary.origin_node, event)
                summary.returned = True
                summary.state = _LifecycleState.PHYSICAL_TERMINAL
            elif kind is VecTaskLifecycleEventKind.RESULT_RETURN_FAILED:
                _validate_result_return(task_id, summary.current_node, summary.origin_node, event)
                summary.return_failed = True
                summary.state = _LifecycleState.PHYSICAL_TERMINAL
            else:
                _invalid_transition(task_id, summary.state, kind)
        elif summary.state is _LifecycleState.PHYSICAL_TERMINAL:
            _require_kind(task_id, kind, VecTaskLifecycleEventKind.DEADLINE_ASSESSED)
            summary.deadline_assessed = True
            summary.deadline_met = bool(event.deadline_met)
            summary.modelled_latency_observed = event.modelled_latency_ms is not None
            summary.state = _LifecycleState.CLOSED
        else:
            _invalid_transition(task_id, summary.state, kind)
    return summary


def _validate_ingress_for_action(
    task_id: str,
    action: Decision | None,
    origin_node: tuple[VecTaskNodeKind, str] | None,
    event: VecTaskLifecycleEvent,
) -> None:
    if action is None:
        raise VecTaskLifecycleError(
            "LIFECYCLE_ACTION_MISSING", f"task {task_id!r} has no selected action"
        )
    expected = {
        Decision.LOCAL: VecTaskNodeKind.LOCAL_VEHICLE,
        Decision.V2I: VecTaskNodeKind.RSU,
        Decision.V2V: VecTaskNodeKind.PEER_VEHICLE,
    }.get(action)
    if expected is None:
        raise VecTaskLifecycleError(
            "LIFECYCLE_ACTION_UNSUPPORTED",
            f"task {task_id!r} selected an unsupported action",
        )
    if event.node_kind is not expected:
        raise VecTaskLifecycleError(
            "LIFECYCLE_ACTION_TARGET_MISMATCH",
            f"task {task_id!r} action {action!s} cannot use ingress kind {event.node_kind!s}",
        )
    if action is Decision.LOCAL and _destination(event) != origin_node:
        raise VecTaskLifecycleError(
            "LIFECYCLE_LOCAL_ORIGIN_MISMATCH",
            f"task {task_id!r} local action must remain at its originating vehicle",
        )


def _validate_forward(
    task_id: str,
    current_node: tuple[VecTaskNodeKind, str] | None,
    event: VecTaskLifecycleEvent,
) -> tuple[VecTaskNodeKind, str]:
    if _source(event) != current_node:
        raise VecTaskLifecycleError(
            "LIFECYCLE_FORWARD_SOURCE_MISMATCH",
            f"task {task_id!r} forwarding source does not match its current node",
        )
    if event.source_node_kind is not VecTaskNodeKind.RSU:
        raise VecTaskLifecycleError(
            "LIFECYCLE_FORWARD_SOURCE_INVALID",
            f"task {task_id!r} forwarding source must be an ingress or prior RSU",
        )
    destination = _destination(event)
    if destination[0] is not VecTaskNodeKind.RSU:
        raise VecTaskLifecycleError(
            "LIFECYCLE_FORWARD_TARGET_INVALID",
            f"task {task_id!r} forwarding destination must be an RSU",
        )
    return destination


def _validate_result_return(
    task_id: str,
    current_node: tuple[VecTaskNodeKind, str] | None,
    origin_node: tuple[VecTaskNodeKind, str] | None,
    event: VecTaskLifecycleEvent,
) -> None:
    if _source(event) != current_node:
        raise VecTaskLifecycleError(
            "LIFECYCLE_RETURN_SOURCE_MISMATCH",
            f"task {task_id!r} result-return source does not match its execution node",
        )
    if _destination(event) != origin_node:
        raise VecTaskLifecycleError(
            "LIFECYCLE_RETURN_TARGET_INVALID",
            f"task {task_id!r} result return must target the originating local vehicle",
        )


def _require_current_node(
    task_id: str,
    current_node: tuple[VecTaskNodeKind, str] | None,
    event: VecTaskLifecycleEvent,
) -> None:
    if _destination(event) != current_node:
        raise VecTaskLifecycleError(
            "LIFECYCLE_NODE_MISMATCH",
            f"task {task_id!r} event node does not match its current execution-path node",
        )


def _require_kind(
    task_id: str,
    actual: VecTaskLifecycleEventKind,
    expected: VecTaskLifecycleEventKind,
) -> None:
    if actual is not expected:
        raise VecTaskLifecycleError(
            "LIFECYCLE_TRANSITION_INVALID",
            f"task {task_id!r} expected {expected.value}, got {actual.value}",
        )


def _invalid_transition(
    task_id: str, state: _LifecycleState, kind: VecTaskLifecycleEventKind
) -> None:
    raise VecTaskLifecycleError(
        "LIFECYCLE_TRANSITION_INVALID",
        f"task {task_id!r} cannot apply {kind.value} while in state {state.value}",
    )


def _destination(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind, str]:
    if event.node_kind is None or event.node_id is None:
        raise AssertionError("validated node payload is missing")
    return event.node_kind, event.node_id


def _source(event: VecTaskLifecycleEvent) -> tuple[VecTaskNodeKind, str]:
    if event.source_node_kind is None or event.source_node_id is None:
        raise AssertionError("validated source-node payload is missing")
    return event.source_node_kind, event.source_node_id


def _events_fingerprint(events: Sequence[VecTaskLifecycleEvent]) -> str:
    payload = [event.model_dump(mode="json") for event in events]
    material = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(material).hexdigest()

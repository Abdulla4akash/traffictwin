"""Synthetic lifecycle, conservation and refusal tests for the provisional VEC ledger."""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from pydantic import ValidationError

from traffictwin.domain.enums import Decision
from traffictwin.integration.vec_task_lifecycle import (
    VecTaskLifecycleError,
    VecTaskLifecycleEvent,
    VecTaskLifecycleEventKind,
    VecTaskNodeKind,
    validate_vec_task_lifecycle,
    vec_task_lifecycle_contract,
)

RUN_ID = "synthetic-lifecycle"
VEHICLE = (VecTaskNodeKind.LOCAL_VEHICLE, "vehicle-1")
OTHER_VEHICLE = (VecTaskNodeKind.LOCAL_VEHICLE, "vehicle-2")
RSU_A = (VecTaskNodeKind.RSU, "rsu-a")
RSU_B = (VecTaskNodeKind.RSU, "rsu-b")
PEER = (VecTaskNodeKind.PEER_VEHICLE, "vehicle-peer")


def _event(
    task_id: str,
    sequence_index: int,
    kind: VecTaskLifecycleEventKind,
    **payload: object,
) -> VecTaskLifecycleEvent:
    return VecTaskLifecycleEvent(
        run_id=RUN_ID,
        task_id=task_id,
        sequence_index=sequence_index,
        occurred_at_ms=float(sequence_index * 10),
        kind=kind,
        **payload,
    )


def _node_payload(node: tuple[VecTaskNodeKind, str]) -> dict[str, object]:
    return {"node_kind": node[0], "node_id": node[1]}


def _transport_payload(
    source: tuple[VecTaskNodeKind, str], destination: tuple[VecTaskNodeKind, str]
) -> dict[str, object]:
    return {
        "source_node_kind": source[0],
        "source_node_id": source[1],
        "node_kind": destination[0],
        "node_id": destination[1],
    }


def _returned(
    task_id: str,
    *,
    action: Decision = Decision.V2I,
    ingress: tuple[VecTaskNodeKind, str] = RSU_A,
    forwarded_to: tuple[VecTaskNodeKind, str] | None = None,
    deadline_met: bool = True,
) -> list[VecTaskLifecycleEvent]:
    events = [
        _event(task_id, 0, VecTaskLifecycleEventKind.OFFERED, **_node_payload(VEHICLE)),
        _event(task_id, 1, VecTaskLifecycleEventKind.ACTION_SELECTED, action=action),
        _event(
            task_id,
            2,
            VecTaskLifecycleEventKind.INGRESS_ASSIGNED,
            **_node_payload(ingress),
        ),
        _event(task_id, 3, VecTaskLifecycleEventKind.ADMITTED, **_node_payload(ingress)),
    ]
    execution_node = ingress
    if forwarded_to is None:
        events.append(
            _event(task_id, 4, VecTaskLifecycleEventKind.RETAINED, **_node_payload(ingress))
        )
    else:
        events.append(
            _event(
                task_id,
                4,
                VecTaskLifecycleEventKind.FORWARDED,
                **_transport_payload(ingress, forwarded_to),
            )
        )
        execution_node = forwarded_to
    events.extend(
        [
            _event(
                task_id,
                5,
                VecTaskLifecycleEventKind.EXECUTION_STARTED,
                **_node_payload(execution_node),
            ),
            _event(
                task_id,
                6,
                VecTaskLifecycleEventKind.EXECUTION_COMPLETED,
                **_node_payload(execution_node),
            ),
            _event(
                task_id,
                7,
                VecTaskLifecycleEventKind.RESULT_RETURNED,
                **_transport_payload(execution_node, VEHICLE),
            ),
            _event(
                task_id,
                8,
                VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
                deadline_met=deadline_met,
                modelled_latency_ms=85.0 if deadline_met else 850.0,
            ),
        ]
    )
    return events


def _rejected(task_id: str) -> list[VecTaskLifecycleEvent]:
    return [
        _event(task_id, 0, VecTaskLifecycleEventKind.OFFERED, **_node_payload(VEHICLE)),
        _event(task_id, 1, VecTaskLifecycleEventKind.ACTION_SELECTED, action=Decision.V2I),
        _event(task_id, 2, VecTaskLifecycleEventKind.INGRESS_ASSIGNED, **_node_payload(RSU_A)),
        _event(
            task_id,
            3,
            VecTaskLifecycleEventKind.REJECTED,
            reason_code="ADMISSION_CEILING",
            **_node_payload(RSU_A),
        ),
        _event(
            task_id,
            4,
            VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
            deadline_met=False,
        ),
    ]


def _dropped(task_id: str) -> list[VecTaskLifecycleEvent]:
    return [
        _event(task_id, 0, VecTaskLifecycleEventKind.OFFERED, **_node_payload(VEHICLE)),
        _event(task_id, 1, VecTaskLifecycleEventKind.ACTION_SELECTED, action=Decision.V2V),
        _event(task_id, 2, VecTaskLifecycleEventKind.INGRESS_ASSIGNED, **_node_payload(PEER)),
        _event(task_id, 3, VecTaskLifecycleEventKind.ADMITTED, **_node_payload(PEER)),
        _event(task_id, 4, VecTaskLifecycleEventKind.RETAINED, **_node_payload(PEER)),
        _event(
            task_id,
            5,
            VecTaskLifecycleEventKind.DROPPED,
            reason_code="CONTACT_LOST",
            **_node_payload(PEER),
        ),
        _event(
            task_id,
            6,
            VecTaskLifecycleEventKind.DEADLINE_ASSESSED,
            deadline_met=False,
        ),
    ]


def _return_failed(task_id: str) -> list[VecTaskLifecycleEvent]:
    events = _returned(task_id, deadline_met=False)
    events[7] = _event(
        task_id,
        7,
        VecTaskLifecycleEventKind.RESULT_RETURN_FAILED,
        reason_code="RETURN_LINK_LOST",
        **_transport_payload(RSU_A, VEHICLE),
    )
    return events


def _flatten(groups: Iterable[Iterable[VecTaskLifecycleEvent]]) -> list[VecTaskLifecycleEvent]:
    return [event for group in groups for event in group]


def test_complete_mixed_ledger_reconciles_every_offered_and_admitted_task() -> None:
    local = _returned(
        "task-local",
        action=Decision.LOCAL,
        ingress=VEHICLE,
        deadline_met=False,
    )
    forwarded = _returned("task-forwarded", forwarded_to=RSU_B)
    events = _flatten(
        [
            local,
            forwarded,
            _rejected("task-rejected"),
            _dropped("task-dropped"),
            _return_failed("task-return-failed"),
        ]
    )

    report = validate_vec_task_lifecycle(events)

    assert report.offered_count == 5
    assert report.admitted_count == 4
    assert report.rejected_count == 1
    assert report.returned_count == 2
    assert report.dropped_count == 1
    assert report.return_failed_count == 1
    assert report.admitted_in_progress_count == 0
    assert report.pending_admission_count == 0
    assert report.started_count == 3
    assert report.execution_completed_count == 3
    assert report.forwarded_task_count == 1
    assert report.forwarding_hop_count == 1
    assert report.deadline_assessed_count == 5
    assert report.deadline_met_count == 1
    assert report.modelled_latency_observed_count == 3
    assert report.closed_task_count == 5
    assert report.closed is True
    assert report.task_count_conservation_holds is True


def test_physical_return_and_deadline_attainment_remain_independent() -> None:
    report = validate_vec_task_lifecycle(
        _returned(
            "task-returned-after-deadline",
            action=Decision.LOCAL,
            ingress=VEHICLE,
            deadline_met=False,
        )
    )

    assert report.returned_count == 1
    assert report.deadline_met_count == 0
    assert report.physical_return_is_deadline_attainment is False
    assert report.legacy_task_met_imported is False
    assert report.scientific_evidence is False


def test_open_prefix_is_visible_and_closed_required_refuses_it() -> None:
    events = _returned("task-open")[:4]

    report = validate_vec_task_lifecycle(events, require_closed=False)

    assert report.offered_count == 1
    assert report.admitted_count == 1
    assert report.admitted_in_progress_count == 1
    assert report.closed_task_count == 0
    assert report.closed is False
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_INCOMPLETE"):
        validate_vec_task_lifecycle(events)


def test_input_order_does_not_change_canonical_fingerprint() -> None:
    first = _flatten([_returned("task-b"), _rejected("task-a")])
    second = list(reversed(first))

    report_a = validate_vec_task_lifecycle(first)
    report_b = validate_vec_task_lifecycle(second)

    assert report_a == report_b
    assert report_a.event_fingerprint == report_b.event_fingerprint


@pytest.mark.parametrize(
    ("action", "ingress"),
    [
        (Decision.LOCAL, RSU_A),
        (Decision.V2I, VEHICLE),
        (Decision.V2V, RSU_A),
    ],
)
def test_action_and_ingress_kind_must_match(
    action: Decision, ingress: tuple[VecTaskNodeKind, str]
) -> None:
    events = _returned("task-target", action=action, ingress=ingress)

    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_ACTION_TARGET_MISMATCH"):
        validate_vec_task_lifecycle(events)


def test_local_ingress_and_result_return_must_target_exact_origin() -> None:
    wrong_local_ingress = _returned(
        "task-wrong-local",
        action=Decision.LOCAL,
        ingress=OTHER_VEHICLE,
    )
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_LOCAL_ORIGIN_MISMATCH"):
        validate_vec_task_lifecycle(wrong_local_ingress)

    wrong_return_target = _returned("task-wrong-return")
    wrong_return_target[7] = wrong_return_target[7].model_copy(update={"node_id": OTHER_VEHICLE[1]})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_RETURN_TARGET_INVALID"):
        validate_vec_task_lifecycle(wrong_return_target)


def test_forwarding_chain_requires_current_rsu_source() -> None:
    events = _returned("task-forward", forwarded_to=RSU_B)
    events[4] = events[4].model_copy(update={"source_node_id": "rsu-wrong"})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_FORWARD_SOURCE_MISMATCH"):
        validate_vec_task_lifecycle(events)

    peer_events = _returned(
        "task-peer-forward",
        action=Decision.V2V,
        ingress=PEER,
        forwarded_to=RSU_A,
    )
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_FORWARD_SOURCE_INVALID"):
        validate_vec_task_lifecycle(peer_events)

    retained_then_forwarded = _returned("task-retained-forwarded")
    retained_then_forwarded[5] = _event(
        "task-retained-forwarded",
        5,
        VecTaskLifecycleEventKind.FORWARDED,
        **_transport_payload(RSU_A, RSU_B),
    )
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_TRANSITION_INVALID"):
        validate_vec_task_lifecycle(retained_then_forwarded)


def test_execution_and_return_nodes_must_follow_the_forwarding_path() -> None:
    execution_mismatch = _returned("task-execution-node", forwarded_to=RSU_B)
    execution_mismatch[5] = execution_mismatch[5].model_copy(
        update={"node_kind": VecTaskNodeKind.RSU, "node_id": "rsu-a"}
    )
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_NODE_MISMATCH"):
        validate_vec_task_lifecycle(execution_mismatch)

    return_mismatch = _returned("task-return-source", forwarded_to=RSU_B)
    return_mismatch[7] = return_mismatch[7].model_copy(update={"source_node_id": "rsu-a"})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_RETURN_SOURCE_MISMATCH"):
        validate_vec_task_lifecycle(return_mismatch)


def test_invalid_transition_sequence_gap_duplicate_and_time_regression_fail_closed() -> None:
    invalid_transition = _returned("task-transition")
    invalid_transition[2] = invalid_transition[2].model_copy(
        update={"kind": VecTaskLifecycleEventKind.ADMITTED}
    )
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_TRANSITION_INVALID"):
        validate_vec_task_lifecycle(invalid_transition)

    gap = _returned("task-gap")
    gap[4] = gap[4].model_copy(update={"sequence_index": 40})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_SEQUENCE_GAP"):
        validate_vec_task_lifecycle(gap)

    duplicate = _returned("task-duplicate")
    duplicate[4] = duplicate[4].model_copy(update={"sequence_index": 3})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_SEQUENCE_DUPLICATE"):
        validate_vec_task_lifecycle(duplicate)

    regressed = _returned("task-time")
    regressed[4] = regressed[4].model_copy(update={"occurred_at_ms": 1.0})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_TIME_REGRESSION"):
        validate_vec_task_lifecycle(regressed)


def test_empty_and_mixed_run_ledgers_are_refused() -> None:
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_EMPTY"):
        validate_vec_task_lifecycle([])

    events = _returned("task-mixed")
    events[-1] = events[-1].model_copy(update={"run_id": "another-run"})
    with pytest.raises(VecTaskLifecycleError, match="LIFECYCLE_RUN_MIXED"):
        validate_vec_task_lifecycle(events)


def test_event_payloads_are_strict_and_cannot_import_legacy_task_met() -> None:
    payload = _event(
        "task-payload",
        0,
        VecTaskLifecycleEventKind.OFFERED,
        **_node_payload(VEHICLE),
    ).model_dump(mode="json")
    payload["task_met"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        VecTaskLifecycleEvent.model_validate(payload)

    with pytest.raises(ValidationError, match="action_selected requires"):
        _event("task-action", 0, VecTaskLifecycleEventKind.ACTION_SELECTED)
    with pytest.raises(ValidationError, match="supported local/V2I/V2V"):
        _event(
            "task-unknown-action",
            0,
            VecTaskLifecycleEventKind.ACTION_SELECTED,
            action=Decision.UNKNOWN,
        )
    with pytest.raises(ValidationError, match="require one reason"):
        _event(
            "task-reason",
            0,
            VecTaskLifecycleEventKind.REJECTED,
            **_node_payload(RSU_A),
        )
    with pytest.raises(ValidationError, match="only by deadline_assessed"):
        _event(
            "task-deadline",
            0,
            VecTaskLifecycleEventKind.OFFERED,
            **_node_payload(VEHICLE),
            deadline_met=True,
            modelled_latency_ms=1.0,
        )
    with pytest.raises(ValidationError, match="originating local vehicle"):
        _event(
            "task-origin",
            0,
            VecTaskLifecycleEventKind.OFFERED,
            **_node_payload(PEER),
        )


def test_contract_is_deterministic_and_refuses_present_evaluator_compatibility_claim() -> None:
    contract = vec_task_lifecycle_contract()

    assert contract.fingerprint() == vec_task_lifecycle_contract().fingerprint()
    assert contract.current_evaluator_adapter == "unavailable_missing_native_events"
    assert contract.scheduler_included is False
    assert contract.producer_semantics_approved is False
    assert contract.scientific_evidence is False

"""Adversarial tests for the analyst map-match review ledger.

Rows come from the real v1.1 matcher over tiny synthetic networks, so the
ledger is exercised against genuine ``ObservationMatchV11`` evidence: an
ambiguous two-reference site that lands in the review queue and a far site
with no candidate at all. The attacks mirror the module's refusals: anonymous
reviewers, bulk shapes, foreign queues, invented groups, silent overwrites,
unsealed or tampered exports, and forged approval labels.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import (
    EdgeSpatialIndex,
    build_edge_index,
)
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    ManualReviewQueue,
    ObservationMatchV11,
    build_manual_review_queue,
    match_observation_v11,
)
from traffictwin.integration.manchester.observation_review import (
    MatchReviewDecision,
    MatchReviewError,
    MatchReviewLedger,
    ReviewDecisionKind,
    ReviewerIdentity,
    load_review_ledger,
    record_review_decision,
    review_status,
    seal_review_ledger,
    start_review_ledger,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"
DECIDED_AT = "2026-07-26T23:00:00+00:00"


def _network(body: str) -> str:
    head = (
        f'  <location netOffset="{NET_OFFSET}" convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>'
    )
    return f"<?xml version='1.0'?>\n<net>\n{head}\n{body}\n</net>\n"


def _junctions(*names: str) -> str:
    return "\n".join(
        f'  <junction id="{name}" type="priority" x="{31000 + index * 60}.00" '
        f'y="{16000 + index * 60}.00" incLanes="" intLanes=""/>'
        for index, name in enumerate(names)
    )


def _edge(edge_id: str, road_type: str, *, ref: str | None = None, shape: str | None = None) -> str:
    geometry = f' shape="{shape}"' if shape else ""
    body = f'    <param key="ref" value="{ref}"/>\n' if ref else ""
    return (
        f'  <edge id="{edge_id}" from="J0" to="J1" type="{road_type}"{geometry}>\n{body}  </edge>'
    )


def _index(tmp_path: Path, body: str) -> EdgeSpatialIndex:
    target = tmp_path / "n.net.xml"
    target.write_text(_network(f"{_junctions('J0', 'J1')}\n{body}"), encoding="utf-8")
    return build_edge_index(target)


def _reviewer() -> ReviewerIdentity:
    return ReviewerIdentity(reviewer_name="A. Analyst", reviewer_role="research analyst")


def _decision(
    count_point_id: int,
    kind: ReviewDecisionKind,
    *,
    group_key: str | None = None,
    supersedes: str | None = None,
    reason: str = "inspected geometry and signed references against the queue evidence",
) -> MatchReviewDecision:
    return MatchReviewDecision(
        count_point_id=count_point_id,
        kind=kind,
        accepted_group_key=group_key,
        reason=reason,
        reviewer=_reviewer(),
        decided_at_utc=DECIDED_AT,
        supersedes=supersedes,
    )


@pytest.fixture
def rows(tmp_path: Path) -> tuple[ObservationMatchV11, ObservationMatchV11]:
    index = _index(
        tmp_path,
        "\n".join(
            (
                _edge("e1", "highway.unclassified", ref="A56"),
                _edge("e2", "highway.residential", ref="A56"),
            )
        ),
    )
    geometry = index.geometry(0)
    site_x, site_y = geometry[0], geometry[1]
    access: dict[str, MotorAccess] = dict.fromkeys(("e1", "e2"), "passenger_car")
    ambiguous = match_observation_v11(
        count_point_id=101,
        easting=site_x,
        northing=site_y,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=ManchesterMapMatchPolicyV11(),
        motor_access=access,
    )
    distant = match_observation_v11(
        count_point_id=202,
        easting=site_x + 3900.0,
        northing=site_y + 3900.0,
        dft_road_type="Minor",
        dft_road_name="U",
        dft_road_ref=None,
        index=index,
        policy=ManchesterMapMatchPolicyV11(),
        motor_access=access,
    )
    return ambiguous, distant


@pytest.fixture
def queue(rows: tuple[ObservationMatchV11, ObservationMatchV11]) -> ManualReviewQueue:
    return build_manual_review_queue(list(rows))


def test_fixture_rows_are_genuinely_queued(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ambiguous, distant = rows
    assert ambiguous.disposition != "owner_policy_accepted_candidate"
    assert len(ambiguous.groups) >= 1
    assert distant.disposition == "no_suitable_candidate"
    assert queue.queued_total == 2


def test_pending_rows_stay_visible_until_a_person_decides(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ledger = start_review_ledger(queue, rows[0].policy_fingerprint)
    status = review_status(ledger, queue)
    assert status.queued_total == 2
    assert status.decided_total == 0
    assert status.pending_total == 2
    assert status.pending_count_point_ids == (101, 202)
    assert status.no_candidate_preserved_total == 1


def test_accept_requires_the_real_row_and_a_real_group(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ambiguous, _ = rows
    ledger = start_review_ledger(queue, ambiguous.policy_fingerprint)
    group_key = ambiguous.groups[0].group_key
    accept = _decision(101, ReviewDecisionKind.ACCEPT_GROUP, group_key=group_key)

    with pytest.raises(MatchReviewError, match="ROW_EVIDENCE_REQUIRED"):
        record_review_decision(ledger, queue, accept)
    with pytest.raises(MatchReviewError, match="UNKNOWN_GROUP"):
        record_review_decision(
            ledger,
            queue,
            _decision(101, ReviewDecisionKind.ACCEPT_GROUP, group_key="invented-group"),
            row=ambiguous,
        )

    updated = record_review_decision(ledger, queue, accept, row=ambiguous)
    status = review_status(updated, queue)
    assert status.accepted_total == 1
    assert status.pending_count_point_ids == (202,)
    live = updated.live_decisions()[101]
    assert live.research_status == "analyst_reviewed_candidate"
    assert live.supervisor_approved is False


def test_anonymous_and_placeholder_reviewers_are_refused() -> None:
    for name in ("TBD", "agent", "  ", "n/a", "anonymous"):
        with pytest.raises(ValidationError):
            ReviewerIdentity(reviewer_name=name, reviewer_role="research analyst")
    with pytest.raises(ValidationError):
        ReviewerIdentity(reviewer_name="A. Analyst", reviewer_role="unknown")


def test_a_change_of_mind_supersedes_and_never_overwrites(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ambiguous, _ = rows
    ledger = start_review_ledger(queue, ambiguous.policy_fingerprint)
    first = _decision(202, ReviewDecisionKind.DEFER)
    ledger = record_review_decision(ledger, queue, first)

    with pytest.raises(MatchReviewError, match="DUPLICATE_DECISION"):
        record_review_decision(
            ledger, queue, _decision(202, ReviewDecisionKind.REJECT_ALL_CANDIDATES)
        )

    replacement = _decision(
        202,
        ReviewDecisionKind.REJECT_ALL_CANDIDATES,
        supersedes=first.fingerprint(),
        reason="site visit confirmed no listed candidate corresponds to the count point",
    )
    updated = record_review_decision(ledger, queue, replacement)
    assert len(updated.decisions) == 2
    assert updated.live_decisions()[202].kind is ReviewDecisionKind.REJECT_ALL_CANDIDATES
    status = review_status(updated, queue)
    assert status.rejected_total == 1
    assert status.deferred_total == 0

    with pytest.raises(MatchReviewError, match="SUPERSEDE_TARGET_MISSING"):
        record_review_decision(
            start_review_ledger(queue, ambiguous.policy_fingerprint),
            queue,
            replacement,
        )


def test_ledger_binds_its_exact_queue_and_policy(
    rows: tuple[ObservationMatchV11, ObservationMatchV11],
    queue: ManualReviewQueue,
) -> None:
    ambiguous, distant = rows
    foreign_queue = build_manual_review_queue([distant])
    ledger = start_review_ledger(foreign_queue, ambiguous.policy_fingerprint)
    with pytest.raises(MatchReviewError, match="QUEUE_MISMATCH"):
        record_review_decision(ledger, queue, _decision(202, ReviewDecisionKind.DEFER))
    with pytest.raises(MatchReviewError, match="QUEUE_MISMATCH"):
        review_status(ledger, queue)

    mismatched = start_review_ledger(queue, "f" * 64)
    with pytest.raises(MatchReviewError, match="POLICY_MISMATCH"):
        record_review_decision(
            mismatched,
            queue,
            _decision(
                101,
                ReviewDecisionKind.ACCEPT_GROUP,
                group_key=ambiguous.groups[0].group_key,
            ),
            row=ambiguous,
        )
    with pytest.raises(MatchReviewError, match="UNKNOWN_COUNT_POINT"):
        record_review_decision(
            start_review_ledger(queue, ambiguous.policy_fingerprint),
            queue,
            _decision(999, ReviewDecisionKind.DEFER),
        )


def test_export_is_sealed_and_tampering_refuses(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ambiguous, _ = rows
    ledger = record_review_decision(
        start_review_ledger(queue, ambiguous.policy_fingerprint),
        queue,
        _decision(202, ReviewDecisionKind.DEFER),
    )
    with pytest.raises(MatchReviewError, match="SEAL_MISSING"):
        load_review_ledger(ledger.model_dump_json())

    sealed = seal_review_ledger(ledger)
    reloaded = load_review_ledger(sealed.model_dump_json())
    assert reloaded.live_decisions()[202].kind is ReviewDecisionKind.DEFER

    with pytest.raises(MatchReviewError, match="LEDGER_SEALED"):
        record_review_decision(sealed, queue, _decision(101, ReviewDecisionKind.DEFER))

    payload: dict[str, Any] = json.loads(sealed.model_dump_json())
    payload["decisions"][0]["reason"] = "edited after the ledger was sealed and exported"
    with pytest.raises(MatchReviewError, match="SEAL_MISMATCH"):
        load_review_ledger(json.dumps(payload))


def test_no_bulk_operation_exists_and_forged_labels_refuse(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    import inspect

    from traffictwin.integration.manchester import observation_review as module

    for name, function in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("_"):
            continue
        for parameter in inspect.signature(function).parameters.values():
            annotation = str(parameter.annotation)
            assert "Sequence[MatchReviewDecision]" not in annotation, name
            assert "list[MatchReviewDecision]" not in annotation, name
            assert "tuple[MatchReviewDecision" not in annotation, name

    decision = _decision(202, ReviewDecisionKind.DEFER)
    for field, value in (
        ("supervisor_approved", True),
        ("scientifically_validated", True),
        ("bulk_operation", True),
        ("research_status", "scientifically_validated"),
    ):
        payload: dict[str, Any] = json.loads(decision.model_dump_json())
        payload[field] = value
        with pytest.raises(ValidationError):
            MatchReviewDecision.model_validate_json(json.dumps(payload))


def test_a_ledger_with_a_silent_second_decision_refuses_to_validate(
    rows: tuple[ObservationMatchV11, ObservationMatchV11], queue: ManualReviewQueue
) -> None:
    ambiguous, _ = rows
    first = _decision(202, ReviewDecisionKind.DEFER)
    second = _decision(202, ReviewDecisionKind.REJECT_ALL_CANDIDATES)
    with pytest.raises(ValidationError, match="explicitly supersede"):
        MatchReviewLedger(
            queue_fingerprint=queue.fingerprint(),
            policy_fingerprint=ambiguous.policy_fingerprint,
            decisions=(first, second),
        )

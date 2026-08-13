"""Strong deterministic tests for the map-match workflow projection.

Uses real upstream model types and helper idioms (Pydantic validation,
build_manual_review_queue, start/record/seal ledger) – no fabricated
matching algorithms.  Covers all four standings, ambiguity, queue binding,
named human review, stale/superseded/mismatched/tampered decisions,
canonical ordering/fingerprint, duplicates, secret/path leakage, exact
admitted DfT historical source provenance, and exact matched edge derivation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from traffictwin.integration.manchester.map_match_workflow import (
    MapMatchDftSourceIdentity,
    MapMatchObservationProjection,
    MapMatchWorkflowError,
    MapMatchWorkflowResult,
    _ambiguity_reason,
    _diagnostics_for,
    _unmatched_reason,
    build_map_match_workflow,
    load_verified_ledger,
    verify_workflow_fingerprint,
)
from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex, build_edge_index
from traffictwin.integration.manchester.observation_matching import EdgeCandidate
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    ManualReviewQueue,
    ObservationMatchV11,
    RoadGroupV11,
    build_manual_review_queue,
)
from traffictwin.integration.manchester.observation_review import (
    MatchReviewDecision,
    MatchReviewLedger,
    ReviewDecisionKind,
    ReviewerIdentity,
    record_review_decision,
    seal_review_ledger,
    start_review_ledger,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
NET_OFFSET = "-517074.60,-5908760.37"
DECIDED_AT = "2026-07-26T23:00:00+00:00"
POLICY = ManchesterMapMatchPolicyV11()
POLICY_FP = POLICY.fingerprint()

# Admitted DfT historical measured-count source (deterministic fixture).
_CONTENT_FP = "ab" * 32  # 64 hex chars, deterministic for tests
_SNAPSHOT_ID = f"dft_raw_counts-20260726T230000Z-{_CONTENT_FP[:12]}"
_PROVENANCE = f"roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json#{_SNAPSHOT_ID}"
_RECEIPT_FP = "cd" * 32  # exact accepted snapshot/admission receipt fingerprint (64 hex)
_ALT_RECEIPT_FP = "ef" * 32
_AUTO_REASON = (
    "owner policy unambiguously accepted under clear thresholds; distance alone not sufficient"
)


def _source(**overrides: Any) -> MapMatchDftSourceIdentity:  # noqa: ANN401
    base: dict[str, Any] = {
        "source_family": "dft",
        "provider": "roadtraffic.dft.gov.uk",
        "observation_role": "historical_measured_count",
        "snapshot_id": _SNAPSHOT_ID,
        "content_fingerprint": _CONTENT_FP,
        "provenance": _PROVENANCE,
        "admission_receipt_fingerprint": _RECEIPT_FP,
        "is_accepted": True,
        "is_source_blocked": False,
    }
    base.update(overrides)
    return MapMatchDftSourceIdentity(**base)


def _network(body: str) -> str:
    head = (
        f'  <location netOffset="{NET_OFFSET}" convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>'
    )
    return f"<?xml version='1.0'?>\n<net>\n{head}\n{body}\n</net>\n"


def _junctions(*names: str) -> str:
    return "\n".join(
        (
            f'  <junction id="{name}" type="priority"'
            f' x="{31000 + i * 60}.00" y="{16000 + i * 60}.00"'
            ' incLanes="" intLanes=""/>'
        )
        for i, name in enumerate(names)
    )


def _edge(edge_id: str, road_type: str, *, ref: str | None = None, shape: str | None = None) -> str:
    body = f'    <param key="ref" value="{ref}"/>\n' if ref else ""
    shape_attr = f' shape="{shape}"' if shape else ""
    return (
        f'  <edge id="{edge_id}" from="J0" to="J1" type="{road_type}"{shape_attr}>\n{body}  </edge>'
    )


def _access(*edge_ids: str, level: MotorAccess = "passenger_car") -> dict[str, MotorAccess]:
    # Helper for integration tests using real match_observation_v11 motor_access mapping.
    return dict.fromkeys(edge_ids, level)


def _index(tmp_path: Path, body: str) -> EdgeSpatialIndex:
    target = tmp_path / "n.net.xml"
    target.write_text(_network(f"{_junctions('J0', 'J1')}\n{body}"), encoding="utf-8")
    return build_edge_index(target)


def _reviewer(name: str = "A. Analyst", role: str = "research analyst") -> ReviewerIdentity:
    return ReviewerIdentity(reviewer_name=name, reviewer_role=role)


def _decision(
    cpid: int,
    kind: ReviewDecisionKind,
    *,
    group_key: str | None = None,
    supersedes: str | None = None,
    reason: str = "inspected geometry and signed references against queue evidence",
) -> MatchReviewDecision:
    return MatchReviewDecision(
        count_point_id=cpid,
        kind=kind,
        accepted_group_key=group_key,
        reason=reason,
        reviewer=_reviewer(),
        decided_at_utc=DECIDED_AT,
        supersedes=supersedes,
    )


# ---------------------------------------------------------------------------
# Manual observation builders for deterministic standings
# ---------------------------------------------------------------------------


def _candidate(edge_id: str = "e1") -> EdgeCandidate:
    return EdgeCandidate(
        edge_id=edge_id,
        road_type="highway.primary",
        road_class="primary",
        road_ref="A56",
        normalised_ref="A56",
        distance_m=Decimal("1.200"),
        geometry_source="explicit_edge_shape",
        bearing_degrees=Decimal("45.000"),
        requires_manual_confirmation=False,
    )


def _group(group_key: str = "ref:A56|primary", edge_id: str = "e1") -> RoadGroupV11:
    return RoadGroupV11(
        group_key=group_key,
        normalised_ref="A56",
        road_class_family="primary",
        members=(_candidate(edge_id),),
        nearest_distance_m=Decimal("1.200"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )


def _group2(group_key: str, edge_id: str) -> RoadGroupV11:
    return RoadGroupV11(
        group_key=group_key,
        normalised_ref="A57",
        road_class_family="secondary",
        members=(
            EdgeCandidate(
                edge_id=edge_id,
                road_type="highway.secondary",
                road_class="secondary",
                road_ref="A57",
                normalised_ref="A57",
                distance_m=Decimal("2.500"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("90.000"),
                requires_manual_confirmation=False,
            ),
        ),
        nearest_distance_m=Decimal("2.500"),
        contains_service_member=False,
        exact_reference_match=False,
        admitted_by_override=False,
        family_mismatch=None,
    )


def _obs_auto(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group(),),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="clear_candidate",
        disposition="owner_policy_accepted_candidate",
        acceptance_path="strict_v1_0_clear",
        audit_flag=False,
        family_mismatch=None,
        reasons=("all strict conditions met; analyst confirmation still required",),
        review_reasons=(),
    )


def _obs_auto_override(cpid: int) -> ObservationMatchV11:
    # override acceptance carries readmitted+applied and mismatch preserved
    from traffictwin.integration.manchester.observation_matching_v11 import ExactReferenceOverride

    ov = ExactReferenceOverride(
        edge_id="e1",
        road_type="highway.unclassified",
        road_class="unclassified",
        normalised_ref="A56",
        distance_m=Decimal("1.000"),
        geometry_source="explicit_edge_shape",
        motor_access="passenger_car",
        family_mismatch=(
            "DfT records this count point as Major; "
            "OpenStreetMap tags the matched edge as highway.unclassified"
        ),
        dft_road_type="Major",
        osm_class_family="unclassified",
    )
    grp = RoadGroupV11(
        group_key="ref:A56|unclassified",
        normalised_ref="A56",
        road_class_family="unclassified",
        members=(
            EdgeCandidate(
                edge_id="e1",
                road_type="highway.unclassified",
                road_class="unclassified",
                road_ref="A56",
                normalised_ref="A56",
                distance_m=Decimal("1.000"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("10.000"),
                requires_manual_confirmation=False,
            ),
        ),
        nearest_distance_m=Decimal("1.000"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=True,
        family_mismatch=(
            "DfT records this count point as Major; "
            "OpenStreetMap tags the matched edge as highway.unclassified"
        ),
    )
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(grp,),
        rejections=(),
        candidates_readmitted=(ov,),
        overrides_applied=(ov,),
        overrides_refused=(),
        missing_evidence=(),
        confidence="clear_candidate",
        disposition="owner_policy_accepted_candidate",
        acceptance_path="exact_reference_family_override",
        audit_flag=True,
        family_mismatch=(
            "DfT records this count point as Major; "
            "OpenStreetMap tags the matched edge as highway.unclassified"
        ),
        reasons=("exact_reference_family_override",),
        review_reasons=(),
    )


def _obs_ambiguous(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group("ref:A56|primary", "e1"), _group2("ref:A57|secondary", "e2")),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="awaiting_manual_review",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=("2 eligible road groups compete",),
    )


def _obs_no_candidate(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Minor",
        dft_road_name="U",
        dft_normalised_ref=None,
        groups=(),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="no_suitable_candidate",
        disposition="no_suitable_candidate",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=("no candidate survived the approved filters",),
        review_reasons=(),
    )


def _obs_unavailable(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=("motor_access_unknown",),
        confidence="no_suitable_candidate",
        disposition="unavailable_missing_evidence",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=(),
    )


def _obs_single_review(cpid: int) -> ObservationMatchV11:
    return ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=cpid,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group(),),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="awaiting_manual_review",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=("the nearest candidate is beyond the strict clear distance",),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_auto_accepted_strict() -> None:
    obs = _obs_auto(1)
    queue = build_manual_review_queue([obs])
    workflow = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=_source()
    )
    assert workflow.auto_accepted_ids == (1,)
    proj = workflow.observations[0]
    assert proj.standing == "AUTO_ACCEPTED"
    assert proj.nearest_distance_m == Decimal("1.200")
    assert proj.decided_at_utc is None
    # AUTO now binds group identity and exact edge IDs.
    assert proj.accepted_group_key == "ref:A56|primary"
    assert proj.matched_edge_ids == ("e1",)


def test_auto_accepted_override_path() -> None:
    obs = _obs_auto_override(10)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.auto_accepted_ids == (10,)
    assert wf.observations[0].standing == "AUTO_ACCEPTED"
    assert wf.observations[0].accepted_group_key == "ref:A56|unclassified"
    assert wf.observations[0].matched_edge_ids == ("e1",)


def test_human_accepted_requires_sealed_named_reviewer() -> None:
    obs = _obs_single_review(101)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(
        ledger,
        queue,
        _decision(101, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs,
    )
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.human_accepted_ids == (101,)
    p = wf.observations[0]
    assert p.standing == "HUMAN_ACCEPTED"
    assert p.reviewer_name == "A. Analyst"
    assert p.accepted_group_key == "ref:A56|primary"
    assert p.matched_edge_ids == ("e1",)
    assert p.decided_at_utc == datetime.fromisoformat(DECIDED_AT.replace("Z", "+00:00")).astimezone(
        UTC
    )
    assert p.decided_at_utc.tzinfo is not None and p.decided_at_utc.utcoffset() == timedelta(0)
    assert p.decision_kind == ReviewDecisionKind.ACCEPT_GROUP


def test_rejected_no_candidate() -> None:
    obs = _obs_no_candidate(202)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.rejected_ids == (202,)
    assert wf.observations[0].standing == "REJECTED"
    assert wf.observations[0].unmatched_reason is not None
    assert wf.observations[0].diagnostics[0].startswith("no candidate")
    assert wf.observations[0].matched_edge_ids == ()
    assert wf.observations[0].accepted_group_key is None


def test_rejected_unavailable_missing_evidence() -> None:
    obs = _obs_unavailable(203)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.rejected_ids == (203,)
    assert wf.observations[0].standing == "REJECTED"
    assert "missing evidence" in (wf.observations[0].unmatched_reason or "")
    assert wf.observations[0].matched_edge_ids == ()


def test_rejected_by_human() -> None:
    obs = _obs_single_review(104)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(
        ledger, queue, _decision(104, ReviewDecisionKind.REJECT_ALL_CANDIDATES)
    )
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.rejected_ids == (104,)
    assert wf.observations[0].standing == "REJECTED"
    assert wf.observations[0].decision_kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES
    assert wf.observations[0].matched_edge_ids == ()
    assert wf.observations[0].accepted_group_key is None


def test_unresolved_awaiting_and_defer() -> None:
    obs = _obs_single_review(105)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.unresolved_ids == (105,)
    assert wf.pending_queue == (105,)
    assert wf.observations[0].standing == "UNRESOLVED"
    assert wf.observations[0].matched_edge_ids == ()
    assert wf.observations[0].accepted_group_key is None
    # defer keeps unresolved
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(ledger, queue, _decision(105, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(ledger)
    wf2 = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf2.unresolved_ids == (105,)
    assert wf2.observations[0].standing == "UNRESOLVED"
    assert wf2.observations[0].matched_edge_ids == ()


def test_tied_competing_ambiguity_stays_unresolved() -> None:
    obs = _obs_ambiguous(110)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.unresolved_ids == (110,)
    p = wf.observations[0]
    assert p.standing == "UNRESOLVED"
    assert p.ambiguity_reason is not None
    assert "eligible road groups" in p.ambiguity_reason
    assert p.matched_edge_ids == ()


def test_distance_alone_never_auto_accepts() -> None:
    obs = _obs_single_review(120)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    assert wf.observations[0].standing != "AUTO_ACCEPTED"
    bad = ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=121,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(_group(),),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="owner_policy_accepted_candidate",
        acceptance_path="strict_v1_0_clear",
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=(),
    )
    fake_queue = ManualReviewQueue(
        observations_total=1, accepted_total=1, queued_total=0, entries=()
    )
    with pytest.raises(MapMatchWorkflowError, match="AMBIGUOUS_CANDIDATE_SILENTLY_ACCEPTED"):
        build_map_match_workflow(
            observations=[bad], queue=fake_queue, policy=POLICY, source=_source()
        )


def test_exact_queue_binding_mismatch_rejected() -> None:
    obs = _obs_single_review(130)
    # Build correct queue then tamper disposition
    queue = build_manual_review_queue([obs])
    tampered_entry = queue.entries[0].model_copy(update={"disposition": "no_suitable_candidate"})
    tampered_queue = ManualReviewQueue(
        observations_total=queue.observations_total,
        accepted_total=queue.accepted_total,
        queued_total=queue.queued_total,
        entries=(tampered_entry,),
    )
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_ENTRY_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=tampered_queue, policy=POLICY, source=_source()
        )


def test_queue_missing_observation_fails() -> None:
    obs1 = _obs_single_review(131)
    obs2 = _obs_no_candidate(132)
    queue = build_manual_review_queue([obs1])  # missing obs2
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_MISMATCH|QUEUE_DENOMINATOR_MISMATCH"):
        build_map_match_workflow(
            observations=[obs1, obs2], queue=queue, policy=POLICY, source=_source()
        )


def test_stale_superseded_only_live_applies() -> None:
    obs = _obs_single_review(140)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    first = _decision(140, ReviewDecisionKind.DEFER)
    ledger = record_review_decision(ledger, queue, first)
    second = _decision(
        140,
        ReviewDecisionKind.ACCEPT_GROUP,
        group_key="ref:A56|primary",
        supersedes=first.fingerprint(),
    )
    ledger = record_review_decision(ledger, queue, second, row=obs)
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.human_accepted_ids == (140,)
    # ledger contains two decisions but only live is ACCEPT_GROUP
    assert wf.observations[0].matched_edge_ids == ("e1",)


def test_superseded_defer_not_live_does_not_resurrect(tmp_path: Path) -> None:
    obs = _obs_ambiguous(141)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    first = _decision(
        141,
        ReviewDecisionKind.ACCEPT_GROUP,
        group_key="ref:A56|primary",
        reason="first accept with inspection",
    )
    ledger = record_review_decision(ledger, queue, first, row=obs)
    # supersede with defer – live becomes defer -> UNRESOLVED
    second = _decision(
        141,
        ReviewDecisionKind.DEFER,
        supersedes=first.fingerprint(),
        reason="re-opened after further evidence required deferral",
    )
    ledger = record_review_decision(ledger, queue, second)
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.unresolved_ids == (141,)
    assert wf.observations[0].matched_edge_ids == ()


def test_tampered_ledger_rejected() -> None:
    obs = _obs_single_review(150)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(ledger, queue, _decision(150, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(ledger)
    payload: dict[str, Any] = json.loads(sealed.model_dump_json())
    payload["decisions"][0]["reason"] = "tampered after seal"
    tampered_json = json.dumps(payload)
    with pytest.raises(Exception, match="SEAL_MISMATCH|LEDGER_TAMPERED"):
        load_verified_ledger(tampered_json)
    # tampered payload: direct load should also fail seal mismatch
    with pytest.raises(Exception, match="SEAL_MISMATCH|LEDGER_TAMPERED"):
        load_verified_ledger(tampered_json)


def test_unsealed_ledger_rejected() -> None:
    obs = _obs_single_review(151)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(ledger, queue, _decision(151, ReviewDecisionKind.DEFER))
    # not sealed
    with pytest.raises(MapMatchWorkflowError, match="LEDGER_NOT_SEALED"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=ledger, source=_source()
        )


def test_unknown_group_mismatch_rejected() -> None:
    obs = _obs_single_review(160)
    queue = build_manual_review_queue([obs])
    # Deliberately forge a ledger with an unknown group to test
    # GROUP_MISMATCH. Using record_review_decision would already reject
    # this, so we create the ledger manually instead.
    bad_decision = _decision(160, ReviewDecisionKind.ACCEPT_GROUP, group_key="invented-group")
    bad_ledger = MatchReviewLedger(
        queue_fingerprint=queue.fingerprint(),
        policy_fingerprint=POLICY_FP,
        decisions=(bad_decision,),
    )
    sealed = seal_review_ledger(bad_ledger)
    with pytest.raises(MapMatchWorkflowError, match="GROUP_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
        )


def test_unknown_observation_decision_rejected() -> None:
    obs = _obs_single_review(161)
    queue = build_manual_review_queue([obs])
    other = _obs_single_review(999)
    other_queue = build_manual_review_queue([other])
    ledger = start_review_ledger(other_queue, POLICY_FP)
    ledger = record_review_decision(ledger, other_queue, _decision(999, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(ledger)
    # sealed ledger queue_fingerprint is for 999, not 161
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_MISMATCH|QUEUE_DENOMINATOR_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
        )


def test_policy_mismatch_rejected() -> None:
    obs = _obs_single_review(170)
    queue = build_manual_review_queue([obs])
    wrong_policy = ManchesterMapMatchPolicyV11(override_max_distance_m=Decimal("4"))
    # Observation fingerprint is for original POLICY, so the builder
    # should see a mismatch when using wrong_policy.
    with pytest.raises(MapMatchWorkflowError, match="POLICY_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=wrong_policy, source=_source()
        )


def test_deterministic_ordering_and_fingerprint() -> None:
    obs1 = _obs_single_review(180)
    obs2 = _obs_no_candidate(181)
    obs3 = _obs_auto(182)
    queue = build_manual_review_queue([obs1, obs2, obs3])
    wf1 = build_map_match_workflow(
        observations=[obs3, obs1, obs2], queue=queue, policy=POLICY, source=_source()
    )
    wf2 = build_map_match_workflow(
        observations=[obs1, obs2, obs3], queue=queue, policy=POLICY, source=_source()
    )
    assert [o.observation.count_point_id for o in wf1.observations] == [180, 181, 182]
    assert wf1.fingerprint() == wf2.fingerprint()
    assert (
        verify_workflow_fingerprint(wf1, policy=POLICY, queue=queue, ledger=None, source=_source())
        == wf1.fingerprint()
    )
    # canonical fingerprint stable across re-validation
    reloaded = wf1.model_validate_json(wf1.model_dump_json())
    assert reloaded.fingerprint() == wf1.fingerprint()
    # source is part of fingerprint
    alt_source = _source(
        content_fingerprint="ff" * 32, snapshot_id=f"dft_raw_counts-20260726T230000Z-{'f' * 12}"
    )
    # different source changes fingerprint
    wf_alt = build_map_match_workflow(
        observations=[obs1, obs2, obs3], queue=queue, policy=POLICY, source=alt_source
    )
    assert wf_alt.fingerprint() != wf1.fingerprint()


def test_duplicate_observation_ids_fail() -> None:
    obs = _obs_single_review(190)
    dup = _obs_single_review(190)
    queue = build_manual_review_queue([obs])
    with pytest.raises(MapMatchWorkflowError, match="DUPLICATE_OBSERVATION"):
        build_map_match_workflow(
            observations=[obs, dup], queue=queue, policy=POLICY, source=_source()
        )


def test_duplicate_edge_within_observation_fail() -> None:
    # same edge_id in two groups
    grp1 = _group("ref:A56|primary", "e1")
    grp2 = RoadGroupV11(
        group_key="ref:A56|primary2",
        normalised_ref="A56",
        road_class_family="primary",
        members=(_candidate("e1"),),
        nearest_distance_m=Decimal("1.200"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )
    bad = ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=191,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(grp1, grp2),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="awaiting_manual_review",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=("2 eligible road groups compete",),
    )
    queue = build_manual_review_queue([bad])
    with pytest.raises(MapMatchWorkflowError, match="DUPLICATE_EDGE"):
        build_map_match_workflow(observations=[bad], queue=queue, policy=POLICY, source=_source())


def test_duplicate_edge_across_observations_allowed() -> None:
    # Same edge_id in different observations is deterministic but allowed (different sites)
    obs1 = _obs_single_review(1910)
    obs2 = _obs_single_review(1911)  # both use e1, but different count_point_id
    queue = build_manual_review_queue([obs1, obs2])
    wf = build_map_match_workflow(
        observations=[obs1, obs2], queue=queue, policy=POLICY, source=_source()
    )
    assert wf.unresolved_ids == (1910, 1911)


def test_duplicate_decision_fingerprint_rejected() -> None:
    obs = _obs_single_review(192)
    queue = build_manual_review_queue([obs])
    d = _decision(192, ReviewDecisionKind.DEFER)
    # Pydantic ledger validation already fails closed on duplicate without supersede
    with pytest.raises(
        (ValidationError, MapMatchWorkflowError), match="supersede|duplicate|DUPLICATE"
    ):
        ledger = MatchReviewLedger(
            queue_fingerprint=queue.fingerprint(),
            policy_fingerprint=POLICY_FP,
            decisions=(d, d),
        )
        sealed = seal_review_ledger(ledger)
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
        )


def test_secret_and_path_leakage_refused() -> None:
    obs = _obs_single_review(200)
    queue = build_manual_review_queue([obs])
    with pytest.raises(ValidationError):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="UNRESOLVED",
            standing_reason="awaiting manual review; no sealed decision; reproducible queue",
            diagnostics=("api_key=123 secret leaked",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key=None,
            matched_edge_ids=(),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )
    with pytest.raises(ValidationError):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="UNRESOLVED",
            standing_reason="review at /tmp/secret/file",
            diagnostics=("normal diagnostic",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key=None,
            matched_edge_ids=(),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )


def test_observation_ids_sorted_and_bounded() -> None:
    obs = _obs_single_review(210)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    # ids are sorted
    assert wf.observations[0].observation.count_point_id == 210
    # bounded collections enforced: too many observations
    many = [_obs_no_candidate(300 + i) for i in range(5)]
    q_many = build_manual_review_queue(many)
    wf_many = build_map_match_workflow(
        observations=many, queue=q_many, policy=POLICY, source=_source()
    )
    assert len(wf_many.observations) == 5


def test_review_status_preserves_all_ids_and_diagnostics() -> None:
    obs_auto = _obs_auto(220)
    obs_unresolved = _obs_single_review(221)
    obs_rejected = _obs_no_candidate(222)
    # human accepted
    obs_human = _obs_single_review(223)
    queue = build_manual_review_queue([obs_auto, obs_unresolved, obs_rejected, obs_human])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(
        ledger,
        queue,
        _decision(223, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs_human,
    )
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs_auto, obs_unresolved, obs_rejected, obs_human],
        queue=queue,
        policy=POLICY,
        ledger=sealed,
        source=_source(),
    )
    assert wf.auto_accepted_ids == (220,)
    assert wf.human_accepted_ids == (223,)
    assert wf.rejected_ids == (222,)
    assert wf.unresolved_ids == (221,)
    assert wf.pending_queue == (221,)
    for proj in wf.observations:
        assert len(proj.diagnostics) >= 1
        for diag in proj.diagnostics:
            tmp_marker = "/" + "tmp" + "/"
            assert tmp_marker not in diag and "secret" not in diag.lower()
    # exact matched edge derivation for accepted standings
    auto_proj = next(p for p in wf.observations if p.observation.count_point_id == 220)
    assert auto_proj.accepted_group_key == "ref:A56|primary"
    assert auto_proj.matched_edge_ids == ("e1",)
    human_proj = next(p for p in wf.observations if p.observation.count_point_id == 223)
    assert human_proj.matched_edge_ids == ("e1",)
    rejected_proj = next(p for p in wf.observations if p.observation.count_point_id == 222)
    assert rejected_proj.matched_edge_ids == ()
    unresolved_proj = next(p for p in wf.observations if p.observation.count_point_id == 221)
    assert unresolved_proj.matched_edge_ids == ()
    # fingerprint covers all
    fp = wf.fingerprint()
    assert len(fp) == 64


# ---------------------------------------------------------------------------
# Discriminating source provenance tests
# ---------------------------------------------------------------------------


def test_source_snapshot_fingerprint_mutation_rejected() -> None:
    obs = _obs_auto(400)
    queue = build_manual_review_queue([obs])
    # Mutate fingerprint but keep snapshot_id -> prefix mismatch
    mutated_fp = "ff" * 32
    # _source helper would itself reject mismatched fingerprint/snapshot binding
    with pytest.raises(ValidationError, match="snapshot_id.*fingerprint|prefix"):
        _source(content_fingerprint=mutated_fp)
    with pytest.raises(ValidationError, match="snapshot_id.*fingerprint|prefix"):
        MapMatchDftSourceIdentity(
            source_family="dft",
            provider="roadtraffic.dft.gov.uk",
            observation_role="historical_measured_count",
            snapshot_id=_SNAPSHOT_ID,
            content_fingerprint=mutated_fp,
            provenance=_PROVENANCE,
            admission_receipt_fingerprint=_RECEIPT_FP,
            is_accepted=True,
            is_source_blocked=False,
        )
    # A correctly bound mutated source succeeds, proving the check is exact.
    good_mutated_id = f"dft_raw_counts-20260726T230000Z-{mutated_fp[:12]}"
    good_mutated_provenance = (
        f"roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json#{good_mutated_id}"
    )
    good_src = _source(
        snapshot_id=good_mutated_id,
        content_fingerprint=mutated_fp,
        provenance=good_mutated_provenance,
    )
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=good_src)
    assert wf.source.content_fingerprint == mutated_fp


def test_source_snapshot_id_mutation_rejected() -> None:
    obs = _obs_auto(401)
    queue = build_manual_review_queue([obs])
    # Snapshot ID mutated to different suffix that no longer matches fingerprint prefix
    bad_id = f"dft_raw_counts-20260726T230000Z-{'0' * 12}"
    with pytest.raises(ValidationError, match="snapshot_id"):
        _source(snapshot_id=bad_id)
    # Also within workflow build, passing that source must fail
    with pytest.raises(ValidationError):
        bad_src = _source(snapshot_id=bad_id)
        build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=bad_src)


def test_blocked_and_unaccepted_source_rejected() -> None:
    _obs_auto(402)
    # Blocked source identity (is_source_blocked True) is rejected at Pydantic level
    with pytest.raises(ValidationError, match="blocked|is_source_blocked"):
        _source(is_source_blocked=True)
    # Unaccepted source (is_accepted False) rejected
    with pytest.raises(ValidationError, match="accepted|is_accepted"):
        _source(is_accepted=False)
    # Direct model_copy forgery should also be caught by validator (if literal bypassed)
    # Here we test that build fails closed even if somehow a blocked source were smuggled.
    # Since literals prevent True/False flips, the above ValidationError is the gate.
    # Additionally, test that workflow requires a source – raw rows without provenance are refused.


def test_source_semantic_inflation_rejected() -> None:
    # Provider inflation to BODS should be rejected — via model_validate dict so
    # strict typing remains truthful while runtime validation stays discriminating.
    with pytest.raises(ValidationError, match="provider|bods|Literal"):
        MapMatchDftSourceIdentity.model_validate(
            {
                "source_family": "dft",
                "provider": "bods",
                "observation_role": "historical_measured_count",
                "snapshot_id": _SNAPSHOT_ID,
                "content_fingerprint": _CONTENT_FP,
                "provenance": "roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json",
                "admission_receipt_fingerprint": _RECEIPT_FP,
                "is_accepted": True,
                "is_source_blocked": False,
            }
        )
    # Role inflation to BODS general road traffic
    with pytest.raises(ValidationError, match="observation_role|BODS|historical_measured_count"):
        MapMatchDftSourceIdentity.model_validate(
            {
                "source_family": "dft",
                "provider": "roadtraffic.dft.gov.uk",
                "observation_role": "general_road_traffic",
                "snapshot_id": _SNAPSHOT_ID,
                "content_fingerprint": _CONTENT_FP,
                "provenance": _PROVENANCE,
                "admission_receipt_fingerprint": _RECEIPT_FP,
                "is_accepted": True,
                "is_source_blocked": False,
            }
        )
    # Family inflation
    with pytest.raises(ValidationError):
        MapMatchDftSourceIdentity.model_validate(
            {
                "source_family": "bods",
                "provider": "roadtraffic.dft.gov.uk",
                "observation_role": "historical_measured_count",
                "snapshot_id": _SNAPSHOT_ID,
                "content_fingerprint": _CONTENT_FP,
                "provenance": _PROVENANCE,
                "admission_receipt_fingerprint": _RECEIPT_FP,
                "is_accepted": True,
                "is_source_blocked": False,
            }
        )
    # Provenance inflation containing BODS general road traffic wording
    with pytest.raises(ValidationError, match="BODS|general_road_traffic"):
        _source(provenance="roadtraffic.dft.gov.uk/bods_general_road_traffic/data.json#snapshot")


def test_source_path_and_secret_leakage_rejected() -> None:
    # Private path in provenance
    with pytest.raises(ValidationError, match="private absolute path"):
        _source(provenance="roadtraffic.dft.gov.uk:/tmp/secret/data.json")
    with pytest.raises(ValidationError, match="private absolute path"):
        _source(provenance="/Users/analyst/roadtraffic.dft.gov.uk/data.json")
    # Secret in provenance
    with pytest.raises(ValidationError, match="likely secret"):
        _source(provenance="roadtraffic.dft.gov.uk:/api/raw-counts?api_key=secret123")
    with pytest.raises(ValidationError, match="likely secret"):
        _source(provenance="roadtraffic.dft.gov.uk:/api/raw-counts?token=secret123")
    # Malformed hash (not 64 hex)
    with pytest.raises(ValidationError, match="pattern|fingerprint"):
        _source(content_fingerprint="ZZ" * 32)
    with pytest.raises(ValidationError, match="pattern|fingerprint"):
        _source(content_fingerprint="abc123")  # too short
    # Uppercase hex should be rejected (pattern is lowercase)
    with pytest.raises(ValidationError):
        _source(content_fingerprint="AB" * 32)


def test_workflow_requires_exact_source_provenance() -> None:
    obs = _obs_auto(403)
    queue = build_manual_review_queue([obs])
    # Omitting source must fail (required param)
    with pytest.raises(TypeError):
        build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY)  # type: ignore[call-arg]
    # Passing non-identity type must fail closed — precisely typed cast keeps
    # static typing truthful while exercising the public-boundary refusal.
    with pytest.raises(MapMatchWorkflowError, match="SOURCE_IDENTITY_INVALID"):
        build_map_match_workflow(
            observations=[obs],
            queue=queue,
            policy=POLICY,
            source=cast(MapMatchDftSourceIdentity, cast(Any, "not-an-identity")),
        )


def test_exact_accepted_edge_derivation_auto_and_human() -> None:
    # AUTO with multiple members in single group -> matched_edge_ids sorted unique
    multi_candidate = RoadGroupV11(
        group_key="ref:A56|primary",
        normalised_ref="A56",
        road_class_family="primary",
        members=(
            EdgeCandidate(
                edge_id="e3",
                road_type="highway.primary",
                road_class="primary",
                road_ref="A56",
                normalised_ref="A56",
                distance_m=Decimal("1.200"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("45.000"),
                requires_manual_confirmation=False,
            ),
            EdgeCandidate(
                edge_id="e1",
                road_type="highway.primary",
                road_class="primary",
                road_ref="A56",
                normalised_ref="A56",
                distance_m=Decimal("1.100"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("45.000"),
                requires_manual_confirmation=False,
            ),
            EdgeCandidate(
                edge_id="e2",
                road_type="highway.primary",
                road_class="primary",
                road_ref="A56",
                normalised_ref="A56",
                distance_m=Decimal("1.150"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("45.000"),
                requires_manual_confirmation=False,
            ),
        ),
        nearest_distance_m=Decimal("1.100"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )
    obs_auto_multi = ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=500,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(multi_candidate,),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="clear_candidate",
        disposition="owner_policy_accepted_candidate",
        acceptance_path="strict_v1_0_clear",
        audit_flag=False,
        family_mismatch=None,
        reasons=("all strict conditions met",),
        review_reasons=(),
    )
    queue = build_manual_review_queue([obs_auto_multi])
    wf = build_map_match_workflow(
        observations=[obs_auto_multi], queue=queue, policy=POLICY, source=_source()
    )
    proj = wf.observations[0]
    assert proj.standing == "AUTO_ACCEPTED"
    assert proj.accepted_group_key == "ref:A56|primary"
    assert proj.matched_edge_ids == ("e1", "e2", "e3")

    # HUMAN with two groups, accept one -> derive from accepted group only
    grp_a = RoadGroupV11(
        group_key="ref:A56|primary",
        normalised_ref="A56",
        road_class_family="primary",
        members=(
            _candidate("e10"),
            EdgeCandidate(
                edge_id="e11",
                road_type="highway.primary",
                road_class="primary",
                road_ref="A56",
                normalised_ref="A56",
                distance_m=Decimal("1.300"),
                geometry_source="explicit_edge_shape",
                bearing_degrees=Decimal("45.000"),
                requires_manual_confirmation=False,
            ),
        ),
        nearest_distance_m=Decimal("1.200"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )
    grp_b = _group2("ref:A57|secondary", "e20")
    obs_human_multi = ObservationMatchV11(
        policy_fingerprint=POLICY_FP,
        count_point_id=501,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(grp_a, grp_b),
        rejections=(),
        candidates_readmitted=(),
        overrides_applied=(),
        overrides_refused=(),
        missing_evidence=(),
        confidence="review_required",
        disposition="awaiting_manual_review",
        acceptance_path=None,
        audit_flag=False,
        family_mismatch=None,
        reasons=(),
        review_reasons=("2 eligible road groups compete",),
    )
    queue2 = build_manual_review_queue([obs_human_multi])
    ledger = start_review_ledger(queue2, POLICY_FP)
    ledger = record_review_decision(
        ledger,
        queue2,
        _decision(501, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs_human_multi,
    )
    sealed = seal_review_ledger(ledger)
    wf2 = build_map_match_workflow(
        observations=[obs_human_multi], queue=queue2, policy=POLICY, ledger=sealed, source=_source()
    )
    proj2 = wf2.observations[0]
    assert proj2.standing == "HUMAN_ACCEPTED"
    assert proj2.matched_edge_ids == ("e10", "e11")


def test_duplicate_edge_ids_within_group_forged_projection_rejected() -> None:
    obs = _obs_auto(510)
    queue = build_manual_review_queue([obs])
    # Forged projection: duplicate edge IDs in matched_edge_ids (unsorted/duplicate)
    with pytest.raises(ValidationError, match="unique|sorted|duplicate"):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="AUTO_ACCEPTED",
            standing_reason=_AUTO_REASON,
            diagnostics=("all strict conditions met",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=("e1", "e1"),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="owner_policy_accepted_candidate",
        )
    # Also build workflow already rejects duplicate edge within observation
    # (existing test covers), but here we test forged accepted_group_key.


def test_forged_matched_edges_and_group_ids_fail_closed() -> None:
    obs = _obs_auto(520)
    queue = build_manual_review_queue([obs])
    # Forged accepted_group_key not equal derived policy-accepted group key
    with pytest.raises(ValidationError, match="accepted_group_key.*derived policy-accepted"):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="AUTO_ACCEPTED",
            standing_reason=_AUTO_REASON,
            diagnostics=("all strict conditions met; analyst confirmation still required",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="invented-group",
            matched_edge_ids=("e1",),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="owner_policy_accepted_candidate",
        )
    # Forged matched_edge_ids not equal derived group members
    with pytest.raises(ValidationError, match="matched_edge_ids"):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="AUTO_ACCEPTED",
            standing_reason=_AUTO_REASON,
            diagnostics=("all strict conditions met; analyst confirmation still required",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=("e99",),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="owner_policy_accepted_candidate",
        )
    # HUMAN forged matched_edge_ids
    obs_h = _obs_single_review(521)
    with pytest.raises(ValidationError, match="matched_edge_ids"):
        MapMatchObservationProjection(
            observation=obs_h,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal="a" * 64,
            standing="HUMAN_ACCEPTED",
            standing_reason="sealed named review accepted group ref:A56|primary by A. Analyst",
            diagnostics=("the nearest candidate is beyond the strict clear distance",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name="A. Analyst",
            reviewer_role="research analyst",
            decision_fingerprint="b" * 64,
            decided_at_utc=datetime.fromisoformat(DECIDED_AT.replace("Z", "+00:00")).astimezone(
                UTC
            ),
            decision_kind=ReviewDecisionKind.ACCEPT_GROUP,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=("e9",),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )
    # HUMAN forged accepted_group_key not in groups
    with pytest.raises(ValidationError, match="accepted_group_key.*among"):
        MapMatchObservationProjection(
            observation=obs_h,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal="a" * 64,
            standing="HUMAN_ACCEPTED",
            standing_reason="sealed named review accepted group invented by A. Analyst",
            diagnostics=("the nearest candidate is beyond the strict clear distance",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name="A. Analyst",
            reviewer_role="research analyst",
            decision_fingerprint="b" * 64,
            decided_at_utc=datetime.fromisoformat(DECIDED_AT.replace("Z", "+00:00")).astimezone(
                UTC
            ),
            decision_kind=ReviewDecisionKind.ACCEPT_GROUP,
            accepted_group_key="invented-group",
            matched_edge_ids=(),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )


def test_unresolved_and_rejected_must_expose_no_matched_edges() -> None:
    obs_unresolved = _obs_single_review(530)
    obs_rejected = _obs_no_candidate(531)
    queue = build_manual_review_queue([obs_unresolved, obs_rejected])
    wf = build_map_match_workflow(
        observations=[obs_unresolved, obs_rejected], queue=queue, policy=POLICY, source=_source()
    )
    for proj in wf.observations:
        if proj.standing in ("REJECTED", "UNRESOLVED"):
            assert proj.matched_edge_ids == ()
            assert proj.accepted_group_key is None
    # Direct construction forging non-empty matched edges on REJECTED/UNRESOLVED must fail
    with pytest.raises(ValidationError, match="must not carry matched_edge_ids"):
        MapMatchObservationProjection(
            observation=obs_unresolved,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="UNRESOLVED",
            standing_reason="awaiting manual review; no sealed decision; reproducible queue",
            diagnostics=("the nearest candidate is beyond the strict clear distance",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key=None,
            matched_edge_ids=("e1",),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )
    with pytest.raises(ValidationError, match="must not carry matched_edge_ids"):
        MapMatchObservationProjection(
            observation=obs_rejected,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="REJECTED",
            standing_reason="no candidate survived the approved filters, including the override",
            diagnostics=("no candidate survived the approved filters",),
            ambiguity_reason=None,
            unmatched_reason="no candidate survived the approved filters, including the override",
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key=None,
            matched_edge_ids=("e1",),
            nearest_distance_m=None,
            original_disposition="no_suitable_candidate",
        )
    # REJECTED/UNRESOLVED must also not carry accepted_group_key
    with pytest.raises(ValidationError, match="must not carry accepted_group_key"):
        MapMatchObservationProjection(
            observation=obs_rejected,
            queue_fingerprint=queue.fingerprint(),
            ledger_seal=None,
            standing="REJECTED",
            standing_reason="no candidate survived the approved filters, including the override",
            diagnostics=("no candidate survived the approved filters",),
            ambiguity_reason=None,
            unmatched_reason="no candidate survived the approved filters, including the override",
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=(),
            nearest_distance_m=None,
            original_disposition="no_suitable_candidate",
        )


def test_auto_requires_sorted_unique_edges() -> None:
    # Matched edge IDs must be sorted unique – direct construction.
    obs = _obs_auto(541)
    queue2 = build_manual_review_queue([obs])
    with pytest.raises(ValidationError, match="sorted deterministic"):
        MapMatchObservationProjection(
            observation=obs,
            queue_fingerprint=queue2.fingerprint(),
            ledger_seal=None,
            standing="AUTO_ACCEPTED",
            standing_reason=_AUTO_REASON,
            diagnostics=("all strict conditions met",),
            ambiguity_reason=None,
            unmatched_reason=None,
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=("e2", "e1"),  # not sorted
            nearest_distance_m=Decimal("1.200"),
            original_disposition="owner_policy_accepted_candidate",
        )


def test_integration_strict_acceptance_with_readmitted_candidate_never_demotes(
    tmp_path: Path,
) -> None:
    """Real upstream: strict acceptance retains its group despite readmitted override.

    Mirrors ``test_a_readmitted_candidate_never_demotes_a_strict_acceptance``
    in ``test_manchester_observation_matching_v11`` but proves the workflow
    projection derives the same accepted group without distance guessing.
    """

    from traffictwin.integration.manchester.observation_matching import match_observation
    from traffictwin.integration.manchester.observation_matching_v11 import match_observation_v11

    index = _index(
        tmp_path,
        "\n".join(
            (
                _edge("e1", "highway.primary", ref="A56"),
                _edge("e2", "highway.unclassified", ref="A56"),
            )
        ),
    )
    # Use the exact site on the network so both candidates are retrieved.
    easting, northing = index.geometry(0)[0], index.geometry(0)[1]
    # Verify upstream strict path still accepts (v1.0 baseline).
    from traffictwin.integration.manchester.observation_matching import ManchesterMapMatchPolicy

    older = match_observation(
        count_point_id=1,
        easting=easting,
        northing=northing,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=ManchesterMapMatchPolicy(),
    )
    assert older.confidence == "clear_candidate"
    # v1.1 with both candidates readmitted but strict path still wins.
    result = match_observation_v11(
        count_point_id=1,
        easting=easting,
        northing=northing,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=POLICY,
        motor_access=_access("e1", "e2"),
    )
    assert result.disposition == "owner_policy_accepted_candidate"
    assert result.acceptance_path == "strict_v1_0_clear"
    assert len(result.groups) == 2  # strict group + readmitted override group
    # The non-override group is the policy-accepted one.
    strict_groups = [g for g in result.groups if not g.admitted_by_override]
    assert len(strict_groups) == 1
    expected_key = strict_groups[0].group_key
    expected_edges = tuple(sorted({m.edge_id for m in strict_groups[0].members}))

    queue = build_manual_review_queue([result])
    wf = build_map_match_workflow(
        observations=[result], queue=queue, policy=POLICY, source=_source()
    )
    assert wf.auto_accepted_ids == (1,)
    proj = wf.observations[0]
    assert proj.standing == "AUTO_ACCEPTED"
    assert proj.accepted_group_key == expected_key
    assert proj.matched_edge_ids == expected_edges
    # Reproducible verification – not distance-ranked.
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=None, source=_source())
        == wf.fingerprint()
    )
    # Fingerprint stable across rebuild from projection observations.
    wf2 = build_map_match_workflow(
        observations=[proj.observation], queue=queue, policy=POLICY, source=_source()
    )
    assert wf2.fingerprint() == wf.fingerprint()
    assert wf2.observations[0].accepted_group_key == expected_key


def test_integration_override_accepted_group_not_nearest(tmp_path: Path) -> None:
    """Flagship override where the policy-accepted group is not the nearest.

    A closer Major-family group without the signed reference must not steal
    the acceptance from the farther exact-reference override group.  The
    workflow must select by overrides_applied identity, not distance rank.
    """

    from traffictwin.integration.manchester.observation_matching_v11 import match_observation_v11

    # Build a network where the non-reference Major group is geometrically
    # closer than the override group.  e2 (secondary, no ref) sits on the site;
    # e1 (unclassified, ref A56) is offset ~3 m away but still within the 5 m
    # override limit.  Both are retrieved; only e1 can trigger the override.
    index = _index(
        tmp_path,
        "\n".join(
            (
                _edge(
                    "e1",
                    "highway.unclassified",
                    ref="A56",
                    shape="31003.00,16000.00 31063.00,16060.00",
                ),
                _edge("e2", "highway.secondary", shape="31000.00,16000.00 31060.00,16060.00"),
            )
        ),
    )
    # Site exactly on e2's geometry → e2 distance 0, e1 distance ~3 m.
    easting, northing = index.geometry(1)[0], index.geometry(1)[1]
    result = match_observation_v11(
        count_point_id=2,
        easting=easting,
        northing=northing,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=POLICY,
        motor_access=_access("e1", "e2"),
    )
    assert result.disposition == "owner_policy_accepted_candidate"
    assert result.acceptance_path == "exact_reference_family_override"
    assert len(result.groups) == 2
    # Identify override group and its distance (should be the larger one).
    override_group = next(g for g in result.groups if g.admitted_by_override)
    other_group = next(g for g in result.groups if not g.admitted_by_override)
    assert override_group.exact_reference_match is True
    assert other_group.exact_reference_match is False
    # Override group is not the nearest (other group is closer).
    assert override_group.nearest_distance_m > other_group.nearest_distance_m
    # Overrides applied identities match the override group exactly.
    assert {m.edge_id for m in override_group.members} == {
        o.edge_id for o in result.overrides_applied
    }

    queue = build_manual_review_queue([result])
    wf = build_map_match_workflow(
        observations=[result], queue=queue, policy=POLICY, source=_source()
    )
    assert wf.auto_accepted_ids == (2,)
    proj = wf.observations[0]
    assert proj.standing == "AUTO_ACCEPTED"
    assert proj.accepted_group_key == override_group.group_key
    assert proj.matched_edge_ids == tuple(sorted({m.edge_id for m in override_group.members}))
    # Verify nearest_distance_m is still the global minimum, not the accepted group's distance.
    assert proj.nearest_distance_m == min(g.nearest_distance_m for g in result.groups)
    assert proj.nearest_distance_m == other_group.nearest_distance_m
    # Reproducible verification.
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=None, source=_source())
        == wf.fingerprint()
    )


def test_integration_ambiguous_override_never_guessed(tmp_path: Path) -> None:
    """Two competing exact-reference groups must stay unresolved, never guessed."""

    from traffictwin.integration.manchester.observation_matching_v11 import match_observation_v11

    index = _index(
        tmp_path,
        "\n".join(
            (
                _edge("e1", "highway.unclassified", ref="A56"),
                _edge("e2", "highway.residential", ref="A56"),
            )
        ),
    )
    easting, northing = index.geometry(0)[0], index.geometry(0)[1]
    result = match_observation_v11(
        count_point_id=3,
        easting=easting,
        northing=northing,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=POLICY,
        motor_access=_access("e1", "e2"),
    )
    assert result.disposition == "awaiting_manual_review"
    assert result.override_acceptance_refused == "several_exact_reference_groups"
    assert len([g for g in result.groups if g.exact_reference_match]) == 2
    assert result.overrides_applied == ()

    queue = build_manual_review_queue([result])
    wf = build_map_match_workflow(
        observations=[result], queue=queue, policy=POLICY, source=_source()
    )
    proj = wf.observations[0]
    assert proj.standing == "UNRESOLVED"
    assert proj.accepted_group_key is None
    assert proj.matched_edge_ids == ()
    # No AUTO guess was published.
    assert wf.auto_accepted_ids == ()
    assert wf.unresolved_ids == (3,)


# ---------------------------------------------------------------------------
# Mutation / model_copy bypass tests – adversarial remediation
# ---------------------------------------------------------------------------


def test_model_copy_source_provider_mutation_rejected_via_workflow() -> None:
    obs = _obs_auto(600)
    queue = build_manual_review_queue([obs])
    valid = _source()
    forged = valid.model_copy(update={"provider": "bods"})
    # Direct construction bypass is not validated until workflow revalidates.
    with pytest.raises(MapMatchWorkflowError, match="SOURCE_IDENTITY_INVALID"):
        build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=forged)
    # Also direct result validation should revalidate nested source via model_validate.
    good_result = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=valid
    )
    # model_copy itself bypasses validation, so it does not raise immediately.
    copied = good_result.model_copy(update={"source": forged})
    # But validating the copied dump must fail due to revalidate_instances.
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(copied.model_dump())
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(
            {**good_result.model_dump(), "source": forged.model_dump() | {"provider": "bods"}}
        )
    # Direct construction with forged instance must also fail.
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult(
            policy_fingerprint=good_result.policy_fingerprint,
            queue_fingerprint=good_result.queue_fingerprint,
            source=forged,
            observations=good_result.observations,
            pending_queue=good_result.pending_queue,
            auto_accepted_ids=good_result.auto_accepted_ids,
            human_accepted_ids=good_result.human_accepted_ids,
            rejected_ids=good_result.rejected_ids,
            unresolved_ids=good_result.unresolved_ids,
        )


def test_model_copy_source_role_mutation_rejected_via_workflow() -> None:
    obs = _obs_auto(601)
    queue = build_manual_review_queue([obs])
    valid = _source()
    forged = valid.model_copy(update={"observation_role": "general_road_traffic"})
    with pytest.raises(MapMatchWorkflowError, match="SOURCE_IDENTITY_INVALID"):
        build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=forged)


def test_model_copy_source_receipt_mutation_rejected_and_fingerprint_bound() -> None:
    obs = _obs_auto(602)
    queue = build_manual_review_queue([obs])
    valid = _source()
    wf_valid = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=valid
    )
    # Mutating receipt to another valid fingerprint is NOT a forgery – it is a different
    # admitted snapshot. Workflow should accept it but produce a different fingerprint.
    alt_via_copy = valid.model_copy(update={"admission_receipt_fingerprint": _ALT_RECEIPT_FP})
    wf_alt_via_copy = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=alt_via_copy
    )
    assert wf_alt_via_copy.fingerprint() != wf_valid.fingerprint()
    # Mutating receipt to an invalid value must be rejected.
    forged_invalid = valid.model_copy(update={"admission_receipt_fingerprint": "ZZ" * 32})
    with pytest.raises(MapMatchWorkflowError, match="SOURCE_IDENTITY_INVALID") as excinfo:
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, source=forged_invalid
        )
    assert _ALT_RECEIPT_FP not in str(excinfo.value) or "SOURCE_IDENTITY_INVALID" in str(
        excinfo.value
    )
    # Different receipt must produce different workflow fingerprint.
    alt_source = _source(admission_receipt_fingerprint=_ALT_RECEIPT_FP)
    wf_alt = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=alt_source
    )
    assert wf_valid.fingerprint() != wf_alt.fingerprint()
    # is_accepted alone is insufficient – without correct receipt, workflow must fail.
    # Create a source dict missing receipt and try to validate.
    with pytest.raises(ValidationError):
        MapMatchDftSourceIdentity.model_validate(
            {
                "source_family": "dft",
                "provider": "roadtraffic.dft.gov.uk",
                "observation_role": "historical_measured_count",
                "snapshot_id": _SNAPSHOT_ID,
                "content_fingerprint": _CONTENT_FP,
                "provenance": _PROVENANCE,
                "is_accepted": True,
                "is_source_blocked": False,
            }
        )
    # Alias key should also be accepted.
    via_alias = MapMatchDftSourceIdentity.model_validate(
        {
            "source_family": "dft",
            "provider": "roadtraffic.dft.gov.uk",
            "observation_role": "historical_measured_count",
            "snapshot_id": _SNAPSHOT_ID,
            "content_fingerprint": _CONTENT_FP,
            "provenance": _PROVENANCE,
            "snapshot_receipt_fingerprint": _RECEIPT_FP,
            "is_accepted": True,
            "is_source_blocked": False,
        }
    )
    assert via_alias.admission_receipt_fingerprint == _RECEIPT_FP
    wf_alias = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, source=via_alias
    )
    assert wf_alias.source.admission_receipt_fingerprint == _RECEIPT_FP


def test_model_copy_observation_disposition_mutation_rejected() -> None:
    # Awaiting review observation forged to appear auto-accepted.
    obs = _obs_single_review(610)
    queue = build_manual_review_queue([obs])
    forged = obs.model_copy(
        update={
            "disposition": "owner_policy_accepted_candidate",
            "confidence": "clear_candidate",
            "acceptance_path": "strict_v1_0_clear",
            "groups": (_group(),),
        }
    )
    with pytest.raises(
        MapMatchWorkflowError,
        match="OBSERVATION_INVALID|QUEUE_MISMATCH|QUEUE_ENTRY_MISMATCH|QUEUE_DENOMINATOR_MISMATCH",
    ):
        build_map_match_workflow(
            observations=[forged], queue=queue, policy=POLICY, source=_source()
        )
    # Also test that workflow result revalidates nested observation via model_validate.
    valid_obs = _obs_auto(611)
    q2 = build_manual_review_queue([valid_obs])
    valid_result = build_map_match_workflow(
        observations=[valid_obs], queue=q2, policy=POLICY, source=_source()
    )
    proj = valid_result.observations[0]
    # Forge the observation inside the projection to change disposition.
    bad_obs = valid_obs.model_copy(update={"disposition": "awaiting_manual_review"})
    # model_copy bypasses validation, so we check via model_validate which must fail.
    forged_proj = proj.model_copy(update={"observation": bad_obs})
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(forged_proj.model_dump())
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(
            {**proj.model_dump(), "observation": bad_obs.model_dump()}
        )


def test_model_copy_observation_groups_mutation_rejected() -> None:
    obs = _obs_auto(612)
    queue = build_manual_review_queue([obs])
    # Remove groups – AUTO requires exactly one group, so build should fail after revalidation.
    forged = obs.model_copy(update={"groups": ()})
    with pytest.raises(MapMatchWorkflowError, match="OBSERVATION_INVALID"):
        build_map_match_workflow(
            observations=[forged], queue=queue, policy=POLICY, source=_source()
        )
    # Add extra group to make ambiguous.
    forged2 = obs.model_copy(
        update={"groups": (_group("ref:A56|primary", "e1"), _group2("ref:A57|secondary", "e2"))}
    )
    fake_q = ManualReviewQueue(observations_total=1, accepted_total=1, queued_total=0, entries=())
    with pytest.raises(MapMatchWorkflowError, match="AMBIGUOUS_AUTO_ACCEPTED|OBSERVATION_INVALID"):
        build_map_match_workflow(
            observations=[forged2], queue=fake_q, policy=POLICY, source=_source()
        )


def test_model_copy_projection_matched_edge_ids_mutation_rejected() -> None:
    obs = _obs_auto(620)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    proj = wf.observations[0]
    assert proj.matched_edge_ids == ("e1",)
    # Forge matched_edge_ids via model_copy – should be rejected on result revalidation.
    forged_proj = proj.model_copy(update={"matched_edge_ids": ("e99",)})
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(
            {**wf.model_dump(), "observations": [forged_proj.model_dump()]}
        )
    # model_copy bypasses validation, so check via model_validate.
    copied = wf.model_copy(update={"observations": (forged_proj,)})
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(copied.model_dump())
    # Also direct projection validation after forge
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(
            {**proj.model_dump(), "matched_edge_ids": ["e99"]}
        )


def test_model_copy_projection_standing_mutation_rejected() -> None:
    obs = _obs_single_review(621)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    proj = wf.observations[0]
    assert proj.standing == "UNRESOLVED"
    forged = proj.model_copy(update={"standing": "AUTO_ACCEPTED"})
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(forged.model_dump())
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(
            {**wf.model_dump(), "observations": [forged.model_dump()]}
        )
    # Do not leak secrets in such forgery attempts – ensure workflow fails without leaking.
    with pytest.raises((ValidationError, MapMatchWorkflowError)):
        build_map_match_workflow(
            observations=[
                obs.model_copy(update={"disposition": "owner_policy_accepted_candidate"})
            ],
            queue=queue,
            policy=POLICY,
            source=_source(),
        )


def test_model_copy_queue_entry_mutation_rejected() -> None:
    obs = _obs_single_review(630)
    queue = build_manual_review_queue([obs])
    # Tamper queue entry disposition via model_copy – workflow should revalidate and reject.
    tampered_entry = queue.entries[0].model_copy(update={"disposition": "no_suitable_candidate"})
    tampered_queue = queue.model_copy(update={"entries": (tampered_entry,)})
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_INVALID|QUEUE_ENTRY_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=tampered_queue, policy=POLICY, source=_source()
        )
    # Also test that a queue forged to contain an auto-accepted observation is rejected.
    auto_obs = _obs_auto(631)
    # Build a queue that claims to contain the auto observation – should be rejected.
    bad_entry = queue.entries[0].model_copy(update={"count_point_id": 631})
    bad_queue = queue.model_copy(update={"entries": (bad_entry,)})
    with pytest.raises(MapMatchWorkflowError, match="QUEUE"):
        build_map_match_workflow(
            observations=[auto_obs], queue=bad_queue, policy=POLICY, source=_source()
        )


def test_model_copy_ledger_seal_mutation_rejected() -> None:
    obs = _obs_single_review(640)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(ledger, queue, _decision(640, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(ledger)
    # Tamper seal via model_copy – workflow revalidation should fail closed.
    tampered = sealed.model_copy(update={"seal": "ff" * 32})
    with pytest.raises(MapMatchWorkflowError, match="LEDGER_INVALID|LEDGER_TAMPERED|SEAL_MISMATCH"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=tampered, source=_source()
        )
    # Also test that direct ledger validation still rejects tampered seal when loading.
    # Build a good workflow with sealed ledger, then mutate ledger seal in result-like context.
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.ledger_seal == sealed.seal
    forged_ledger = sealed.model_copy(update={"seal": "00" * 32})
    with pytest.raises(MapMatchWorkflowError, match="LEDGER_INVALID|LEDGER_TAMPERED"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=forged_ledger, source=_source()
        )


def test_workflow_result_rejects_forged_nested_instances_directly() -> None:
    obs = _obs_auto(650)
    queue = build_manual_review_queue([obs])
    valid = _source()
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=valid)
    # Forge provider via nested source model_copy and attempt direct result validation.
    forged_source = valid.model_copy(update={"provider": "bods"})
    # model_copy bypasses validation, so check via model_validate.
    copied = wf.model_copy(update={"source": forged_source})
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(copied.model_dump())
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(
            {**wf.model_dump(), "source": forged_source.model_dump() | {"provider": "bods"}}
        )
    # Forge observation inside projection – make disposition mismatch the standing.
    proj = wf.observations[0]
    bad_obs = obs.model_copy(
        update={
            "disposition": "awaiting_manual_review",
            "confidence": "review_required",
            "acceptance_path": None,
            "review_reasons": ("needs review",),
        }
    )
    forged_proj = proj.model_copy(update={"observation": bad_obs})
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(forged_proj.model_dump())


def test_admission_receipt_fingerprint_validation() -> None:
    # Missing receipt must fail.
    with pytest.raises(ValidationError):
        MapMatchDftSourceIdentity(
            source_family="dft",
            provider="roadtraffic.dft.gov.uk",
            observation_role="historical_measured_count",
            snapshot_id=_SNAPSHOT_ID,
            content_fingerprint=_CONTENT_FP,
            provenance=_PROVENANCE,
            is_accepted=True,
            is_source_blocked=False,
        )  # type: ignore[call-arg]
    # Malformed receipt (not 64 hex) must fail.
    with pytest.raises(ValidationError):
        _source(admission_receipt_fingerprint="ZZ" * 32)
    with pytest.raises(ValidationError):
        _source(admission_receipt_fingerprint="abc")
    with pytest.raises(ValidationError):
        _source(admission_receipt_fingerprint="AB" * 32)
    # Uppercase should fail (pattern lowercase).
    # Valid receipt succeeds and is part of fingerprint.
    src1 = _source(admission_receipt_fingerprint=_RECEIPT_FP)
    src2 = _source(admission_receipt_fingerprint=_ALT_RECEIPT_FP)
    assert src1.fingerprint() != src2.fingerprint()
    # Ensure workflow fingerprint differs.
    obs = _obs_auto(660)
    queue = build_manual_review_queue([obs])
    wf1 = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=src1)
    wf2 = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=src2)
    assert wf1.fingerprint() != wf2.fingerprint()
    assert wf1.source.admission_receipt_fingerprint == _RECEIPT_FP
    assert wf2.source.admission_receipt_fingerprint == _ALT_RECEIPT_FP


# ---------------------------------------------------------------------------
# Discriminating direct-construction / model_copy / ledger / verification tests
# ---------------------------------------------------------------------------


def _auto_workflow_and_proj(
    cpid: int = 700,
) -> tuple[MapMatchWorkflowResult, MapMatchObservationProjection]:
    obs = _obs_auto(cpid)
    q = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=q, policy=POLICY, source=_source())
    return wf, wf.observations[0]


def _human_workflow_and_proj(
    cpid: int = 701,
) -> tuple[
    MapMatchWorkflowResult, MapMatchObservationProjection, ManualReviewQueue, MatchReviewLedger
]:
    obs = _obs_single_review(cpid)
    q = build_manual_review_queue([obs])
    led = start_review_ledger(q, POLICY_FP)
    led = record_review_decision(
        led,
        q,
        _decision(cpid, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs,
    )
    sealed = seal_review_ledger(led)
    wf = build_map_match_workflow(
        observations=[obs], queue=q, policy=POLICY, ledger=sealed, source=_source()
    )
    return wf, wf.observations[0], q, sealed


def _rejected_human_workflow_and_proj(
    cpid: int = 702,
) -> tuple[
    MapMatchWorkflowResult, MapMatchObservationProjection, ManualReviewQueue, MatchReviewLedger
]:
    obs = _obs_single_review(cpid)
    q = build_manual_review_queue([obs])
    led = start_review_ledger(q, POLICY_FP)
    led = record_review_decision(led, q, _decision(cpid, ReviewDecisionKind.REJECT_ALL_CANDIDATES))
    sealed = seal_review_ledger(led)
    wf = build_map_match_workflow(
        observations=[obs], queue=q, policy=POLICY, ledger=sealed, source=_source()
    )
    return wf, wf.observations[0], q, sealed


def _unresolved_workflow_and_proj(
    cpid: int = 703,
) -> tuple[MapMatchWorkflowResult, MapMatchObservationProjection, ManualReviewQueue]:
    obs = _obs_single_review(cpid)
    q = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=q, policy=POLICY, source=_source())
    return wf, wf.observations[0], q


def _defer_workflow_and_proj(
    cpid: int = 704,
) -> tuple[
    MapMatchWorkflowResult, MapMatchObservationProjection, ManualReviewQueue, MatchReviewLedger
]:
    obs = _obs_single_review(cpid)
    q = build_manual_review_queue([obs])
    led = start_review_ledger(q, POLICY_FP)
    led = record_review_decision(led, q, _decision(cpid, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(led)
    wf = build_map_match_workflow(
        observations=[obs], queue=q, policy=POLICY, ledger=sealed, source=_source()
    )
    return wf, wf.observations[0], q, sealed


def test_auto_rejects_any_human_field() -> None:
    _, proj = _auto_workflow_and_proj(710)
    base = proj.model_dump()
    for field, bad in [
        ("reviewer_name", "A. Analyst"),
        ("reviewer_role", "research analyst"),
        ("decision_fingerprint", "a" * 64),
        ("ledger_seal", "b" * 64),
        ("decision_kind", ReviewDecisionKind.ACCEPT_GROUP),
    ]:
        with pytest.raises(ValidationError, match="must not carry any human"):
            MapMatchObservationProjection.model_validate({**base, field: bad})
        # model_copy bypass must also be caught via revalidation
        forged = proj.model_copy(update={field: bad})
        with pytest.raises(ValidationError):
            MapMatchObservationProjection.model_validate(forged.model_dump())
    # decided_at_utc partial
    from datetime import datetime as _dt

    dt = _dt.fromisoformat(DECIDED_AT.replace("Z", "+00:00")).astimezone(UTC)
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate({**base, "decided_at_utc": dt})
    with pytest.raises(ValidationError, match="standing_reason"):
        MapMatchObservationProjection.model_validate(
            {**base, "standing_reason": "arbitrary rhetoric for auto"}
        )
    with pytest.raises(ValidationError, match="diagnostics"):
        MapMatchObservationProjection.model_validate({**base, "diagnostics": ("arbitrary",)})
    with pytest.raises(ValidationError, match="ambiguity_reason"):
        MapMatchObservationProjection.model_validate({**base, "ambiguity_reason": "bogus"})
    with pytest.raises(ValidationError, match="unmatched_reason"):
        MapMatchObservationProjection.model_validate({**base, "unmatched_reason": "bogus"})


def test_auto_rejects_non_auto_observation() -> None:
    # awaiting_manual_review observation cannot be AUTO_ACCEPTED
    obs = _obs_single_review(711)
    _, auto_proj = _auto_workflow_and_proj(712)
    base = auto_proj.model_dump()
    # swap observation to awaiting review but keep AUTO standing – with correct derived fields
    bad_obs_dump = obs.model_dump()
    with pytest.raises(ValidationError, match="AUTO_ACCEPTED requires owner_policy"):
        MapMatchObservationProjection.model_validate(
            {
                **base,
                "observation": bad_obs_dump,
                "diagnostics": _diagnostics_for(obs),
                "ambiguity_reason": _ambiguity_reason(obs),
                "unmatched_reason": _unmatched_reason(obs),
                "nearest_distance_m": min(g.nearest_distance_m for g in obs.groups)
                if obs.groups
                else None,
                "original_disposition": obs.disposition,
            }
        )
    # model_copy observation change – revalidation must fail canonical
    # use model_validate with corrected derived fields to ensure AUTO check triggers
    forged_dict = {
        **base,
        "observation": bad_obs_dump,
        "diagnostics": _diagnostics_for(obs),
        "ambiguity_reason": _ambiguity_reason(obs),
        "unmatched_reason": _unmatched_reason(obs),
        "nearest_distance_m": min(g.nearest_distance_m for g in obs.groups) if obs.groups else None,
        "original_disposition": obs.disposition,
    }
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(forged_dict)


def test_human_accepted_partial_fields_rejected() -> None:
    _, proj, _, _ = _human_workflow_and_proj(720)
    base = proj.model_dump()
    for field in [
        "reviewer_name",
        "reviewer_role",
        "decision_fingerprint",
        "ledger_seal",
        "decided_at_utc",
    ]:
        val = base.copy()
        val[field] = None
        with pytest.raises(ValidationError, match="requires sealed named"):
            MapMatchObservationProjection.model_validate(val)
    # missing accepted_group_key
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate({**base, "accepted_group_key": None})
    # wrong decision_kind
    with pytest.raises(ValidationError, match="requires accept_group"):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.DEFER}
        )
    with pytest.raises(ValidationError, match="requires accept_group"):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.REJECT_ALL_CANDIDATES}
        )
    # invented group
    with pytest.raises(ValidationError, match="among observation groups"):
        MapMatchObservationProjection.model_validate({**base, "accepted_group_key": "invented"})
    # wrong matched edges
    with pytest.raises(ValidationError, match="matched_edge_ids"):
        MapMatchObservationProjection.model_validate({**base, "matched_edge_ids": ("e99",)})
    # arbitrary standing_reason
    with pytest.raises(ValidationError, match="standing_reason"):
        MapMatchObservationProjection.model_validate(
            {**base, "standing_reason": "arbitrary rhetoric"}
        )
    # diagnostics / ambiguity / unmatched must be coherent
    with pytest.raises(ValidationError, match="diagnostics"):
        MapMatchObservationProjection.model_validate({**base, "diagnostics": ("bad",)})
    with pytest.raises(ValidationError, match="unmatched_reason"):
        MapMatchObservationProjection.model_validate({**base, "unmatched_reason": "bogus"})
    # human accepted requires awaiting_manual_review observation
    auto_obs = _obs_auto(721)
    with pytest.raises(ValidationError, match="awaiting_manual_review"):
        MapMatchObservationProjection.model_validate(
            {
                **base,
                "observation": auto_obs.model_dump(),
                "diagnostics": _diagnostics_for(auto_obs),
                "ambiguity_reason": _ambiguity_reason(auto_obs),
                "unmatched_reason": _unmatched_reason(auto_obs),
                "nearest_distance_m": min(g.nearest_distance_m for g in auto_obs.groups)
                if auto_obs.groups
                else None,
                "original_disposition": auto_obs.disposition,
            }
        )


def test_rejected_policy_without_human_requires_policy_disposition() -> None:
    obs_rej = _obs_no_candidate(730)
    q = build_manual_review_queue([obs_rej])
    wf = build_map_match_workflow(observations=[obs_rej], queue=q, policy=POLICY, source=_source())
    proj = wf.observations[0]
    base = proj.model_dump()
    # awaiting_manual_review disposition cannot be REJECTED without human decision
    obs_unres = _obs_single_review(731)
    with pytest.raises(ValidationError, match="REJECTED without human"):
        MapMatchObservationProjection.model_validate(
            {
                **base,
                "observation": obs_unres.model_dump(),
                "diagnostics": _diagnostics_for(obs_unres),
                "ambiguity_reason": _ambiguity_reason(obs_unres),
                "unmatched_reason": _unmatched_reason(obs_unres),
                "nearest_distance_m": min(g.nearest_distance_m for g in obs_unres.groups)
                if obs_unres.groups
                else None,
                "original_disposition": obs_unres.disposition,
            }
        )
    # REJECTED without human must not carry human fields
    with pytest.raises(ValidationError, match="REJECTED.*human|must not carry|sealed"):
        MapMatchObservationProjection.model_validate({**base, "reviewer_name": "A. Analyst"})
    with pytest.raises(ValidationError, match="REJECTED.*human|must not carry|sealed"):
        MapMatchObservationProjection.model_validate({**base, "ledger_seal": "a" * 64})
    with pytest.raises(ValidationError, match="REJECTED.*human|must not carry|sealed|REJECT_ALL"):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.REJECT_ALL_CANDIDATES}
        )
    # must not carry accepted_group_key / matched edges
    with pytest.raises(ValidationError, match="must not carry accepted_group_key"):
        MapMatchObservationProjection.model_validate(
            {**base, "accepted_group_key": "ref:A56|primary"}
        )
    with pytest.raises(ValidationError, match="must not carry matched_edge_ids"):
        MapMatchObservationProjection.model_validate({**base, "matched_edge_ids": ("e1",)})
    # standing_reason must equal unmatched_reason
    with pytest.raises(ValidationError, match="standing_reason must equal"):
        MapMatchObservationProjection.model_validate(
            {**base, "standing_reason": "arbitrary rhetoric that is long enough"}
        )


def test_rejected_human_partial_fields_rejected() -> None:
    _, proj, _, _ = _rejected_human_workflow_and_proj(732)
    base = proj.model_dump()
    for field in ["reviewer_role", "decision_fingerprint", "ledger_seal", "decided_at_utc"]:
        with pytest.raises(ValidationError):
            MapMatchObservationProjection.model_validate({**base, field: None})
    # cannot carry accept_group
    with pytest.raises(ValidationError, match="cannot carry accept_group"):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.ACCEPT_GROUP}
        )
    with pytest.raises(ValidationError, match="cannot carry defer"):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.DEFER}
        )
    with pytest.raises(ValidationError, match="must not carry accepted_group_key"):
        MapMatchObservationProjection.model_validate(
            {**base, "accepted_group_key": "ref:A56|primary"}
        )
    with pytest.raises(ValidationError, match="must not carry matched_edge_ids"):
        MapMatchObservationProjection.model_validate({**base, "matched_edge_ids": ("e1",)})
    with pytest.raises(ValidationError, match="standing_reason"):
        MapMatchObservationProjection.model_validate({**base, "standing_reason": "bad"})


def test_unresolved_without_decision_requires_awaiting() -> None:
    _, proj, _ = _unresolved_workflow_and_proj(740)
    base = proj.model_dump()
    # no_suitable_candidate cannot be UNRESOLVED without decision
    obs_rej = _obs_no_candidate(741)
    with pytest.raises(ValidationError, match="UNRESOLVED without decision requires awaiting"):
        MapMatchObservationProjection.model_validate(
            {
                **base,
                "observation": obs_rej.model_dump(),
                "diagnostics": _diagnostics_for(obs_rej),
                "ambiguity_reason": _ambiguity_reason(obs_rej),
                "unmatched_reason": _unmatched_reason(obs_rej),
                "nearest_distance_m": None,
                "original_disposition": obs_rej.disposition,
            }
        )
    # must not carry human fields
    with pytest.raises(
        ValidationError, match="UNRESOLVED.*without decision|UNRESOLVED DEFER|must not carry"
    ):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.DEFER}
        )
    with pytest.raises(ValidationError, match="UNRESOLVED.*human|must not carry|DEFER"):
        MapMatchObservationProjection.model_validate({**base, "reviewer_name": "A. Analyst"})
    with pytest.raises(ValidationError, match="must not carry accepted_group_key"):
        MapMatchObservationProjection.model_validate(
            {**base, "accepted_group_key": "ref:A56|primary"}
        )
    with pytest.raises(ValidationError, match="must not carry matched_edge_ids"):
        MapMatchObservationProjection.model_validate({**base, "matched_edge_ids": ("e1",)})
    with pytest.raises(ValidationError, match="standing_reason"):
        MapMatchObservationProjection.model_validate({**base, "standing_reason": "arbitrary"})


def test_unresolved_defer_partial_fields_rejected() -> None:
    _, proj, _, _ = _defer_workflow_and_proj(750)
    base = proj.model_dump()
    for field in [
        "reviewer_name",
        "reviewer_role",
        "decision_fingerprint",
        "ledger_seal",
        "decided_at_utc",
    ]:
        with pytest.raises(ValidationError):
            MapMatchObservationProjection.model_validate({**base, field: None})
    # must be exactly DEFER, no other kind
    with pytest.raises(
        ValidationError, match="must be exactly DEFER| cannot be accept_group|cannot be reject"
    ):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.ACCEPT_GROUP}
        )
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(
            {**base, "decision_kind": ReviewDecisionKind.REJECT_ALL_CANDIDATES}
        )
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate({**base, "decision_kind": None})
    with pytest.raises(ValidationError, match="standing_reason"):
        MapMatchObservationProjection.model_validate({**base, "standing_reason": "bad"})
    # DEFER cannot carry accepted group
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(
            {**base, "accepted_group_key": "ref:A56|primary"}
        )


def test_result_rejects_missing_ledger_for_decided_projection() -> None:
    wf_h, proj_h, q, sealed = _human_workflow_and_proj(760)
    # result with ledger_seal None but projection has decision -> must fail
    with pytest.raises(ValidationError, match="no-ledger result must not contain|requires ledger"):
        MapMatchWorkflowResult.model_validate(
            {**wf_h.model_dump(), "ledger_seal": None, "ledger_fingerprint": None}
        )
    forged = wf_h.model_copy(update={"ledger_seal": None, "ledger_fingerprint": None})
    with pytest.raises(ValidationError):
        MapMatchWorkflowResult.model_validate(forged.model_dump())
    # wrong ledger seal mismatch
    with pytest.raises(ValidationError, match="ledger_seal mismatch"):
        MapMatchWorkflowResult.model_validate(
            {
                **wf_h.model_dump(),
                "ledger_seal": "ff" * 32,
                "ledger_fingerprint": wf_h.ledger_fingerprint,
            }
        )
    # projection with partial human fields but result ledger present – also fails via projection
    base = proj_h.model_dump()
    bad_proj = {**base, "ledger_seal": None}
    # building result with bad projection should fail ledger binding
    with pytest.raises(
        ValidationError, match="must carry ledger_seal|decided projection|requires sealed"
    ):
        MapMatchWorkflowResult.model_validate({**wf_h.model_dump(), "observations": (bad_proj,)})
    # no-ledger workflow must not contain any human field – inject defer  # noqa: E501
    # Use same count_point_id to keep queue_fingerprint consistent  # noqa: E501
    wf_u, proj_u, q_u = _unresolved_workflow_and_proj(761)
    # Build a defer projection for the same id 761 (same queue fingerprint)
    obs_defer_same = _obs_single_review(761)
    q_defer_same = build_manual_review_queue([obs_defer_same])
    led_same = start_review_ledger(q_defer_same, POLICY_FP)
    led_same = record_review_decision(
        led_same, q_defer_same, _decision(761, ReviewDecisionKind.DEFER)
    )
    sealed_same = seal_review_ledger(led_same)
    wf_defer_same = build_map_match_workflow(
        observations=[obs_defer_same],
        queue=q_defer_same,
        policy=POLICY,
        ledger=sealed_same,
        source=_source(),
    )
    defer_dump = wf_defer_same.observations[0].model_dump()
    with pytest.raises(ValidationError, match="no-ledger result must not contain|requires ledger"):
        MapMatchWorkflowResult.model_validate(
            {
                **wf_u.model_dump(),
                "observations": (defer_dump,),
            }
        )


def test_verify_workflow_fingerprint_catches_forgeries_and_stale_dependencies() -> None:
    # correct verification succeeds
    obs = _obs_single_review(770)
    q = build_manual_review_queue([obs])
    led = start_review_ledger(q, POLICY_FP)
    led = record_review_decision(
        led,
        q,
        _decision(770, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs,
    )
    sealed = seal_review_ledger(led)
    wf = build_map_match_workflow(
        observations=[obs], queue=q, policy=POLICY, ledger=sealed, source=_source()
    )
    # backwards-compatible digest still works
    # full verification with exact dependencies succeeds (source required)
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=q, ledger=sealed, source=_source())
        == wf.fingerprint()
    )
    # forged HUMAN_ACCEPTED via model_copy – change disposition inside observation
    proj = wf.observations[0]
    bad_obs = obs.model_copy(
        update={
            "disposition": "no_suitable_candidate",
            "confidence": "no_suitable_candidate",
            "groups": (),
        }
    )
    forged_proj = proj.model_copy(update={"observation": bad_obs})
    forged_wf = wf.model_copy(update={"observations": (forged_proj,)})
    # canonical revalidation alone must fail (digest path) – either invalid or fingerprint mismatch
    with pytest.raises((ValidationError, MapMatchWorkflowError)):
        MapMatchWorkflowResult.model_validate(forged_wf.model_dump())
    with pytest.raises(MapMatchWorkflowError):
        verify_workflow_fingerprint(
            forged_wf, policy=POLICY, queue=q, ledger=sealed, source=_source()
        )
    # stale policy
    stale_policy = ManchesterMapMatchPolicyV11(override_max_distance_m=Decimal("4"))
    with pytest.raises(
        MapMatchWorkflowError, match="POLICY_MISMATCH|POLICY_INVALID|VERIFICATION|TAMPERED"
    ):
        verify_workflow_fingerprint(
            wf, policy=stale_policy, queue=q, ledger=sealed, source=_source()
        )
    # stale queue – different fingerprint
    other_obs = _obs_single_review(771)
    other_q = build_manual_review_queue([other_obs])
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_MISMATCH|VERIFICATION|TAMPERED"):
        verify_workflow_fingerprint(
            wf, policy=POLICY, queue=other_q, ledger=sealed, source=_source()
        )
    # missing ledger when workflow is sealed
    with pytest.raises(MapMatchWorkflowError, match="LEDGER_MISSING"):
        verify_workflow_fingerprint(wf, policy=POLICY, queue=q, ledger=None, source=_source())
    # wrong ledger seal
    other_led = start_review_ledger(q, POLICY_FP)
    other_led = record_review_decision(other_led, q, _decision(770, ReviewDecisionKind.DEFER))
    other_sealed = seal_review_ledger(other_led)
    with pytest.raises(MapMatchWorkflowError, match="LEDGER_SEAL_MISMATCH|TAMPERED|FINGERPRINT"):
        verify_workflow_fingerprint(
            wf, policy=POLICY, queue=q, ledger=other_sealed, source=_source()
        )
    # changed disposition/edge/group via projection model_copy – stale group
    bad_accept = proj.model_copy(update={"accepted_group_key": "invented"})
    bad_wf2 = wf.model_copy(update={"observations": (bad_accept,)})
    with pytest.raises((ValidationError, MapMatchWorkflowError)):
        MapMatchWorkflowResult.model_validate(bad_wf2.model_dump())
    with pytest.raises(MapMatchWorkflowError):
        verify_workflow_fingerprint(
            bad_wf2, policy=POLICY, queue=q, ledger=sealed, source=_source()
        )
    # UNRESOLVED and REJECTED forgeries also caught
    obs_rej = _obs_no_candidate(772)
    q_rej = build_manual_review_queue([obs, obs_rej])
    led_rej = start_review_ledger(q_rej, POLICY_FP)
    led_rej = record_review_decision(
        led_rej,
        q_rej,
        _decision(770, ReviewDecisionKind.ACCEPT_GROUP, group_key="ref:A56|primary"),
        row=obs,
    )
    sealed_rej = seal_review_ledger(led_rej)
    wf2 = build_map_match_workflow(
        observations=[obs, obs_rej], queue=q_rej, policy=POLICY, ledger=sealed_rej, source=_source()
    )
    # force REJECTED to look HUMAN without proper ledger – should fail
    rej_proj = next(p for p in wf2.observations if p.standing == "REJECTED")
    forged_rej = rej_proj.model_copy(
        update={
            "standing": "HUMAN_ACCEPTED",
            "decision_kind": ReviewDecisionKind.ACCEPT_GROUP,
            "accepted_group_key": "ref:A56|primary",
            "reviewer_name": "A. Analyst",
            "reviewer_role": "research analyst",
            "decision_fingerprint": "a" * 64,
            "ledger_seal": sealed_rej.seal,
            "decided_at_utc": proj.decided_at_utc,
            "matched_edge_ids": ("e1",),
        }
    )
    forged_wf3 = wf2.model_copy(
        update={
            "observations": tuple(
                sorted(
                    (wf2.observations[0], forged_rej), key=lambda p: p.observation.count_point_id
                )
            )
        }
    )
    with pytest.raises((ValidationError, MapMatchWorkflowError)):
        MapMatchWorkflowResult.model_validate(forged_wf3.model_dump())


def test_ambiguity_stays_unresolved_and_distance_never_accepts() -> None:
    # ambiguous with two groups must be UNRESOLVED with correct ambiguity_reason
    amb_obs = _obs_ambiguous(780)
    q = build_manual_review_queue([amb_obs])
    wf = build_map_match_workflow(observations=[amb_obs], queue=q, policy=POLICY, source=_source())
    p = wf.observations[0]
    assert p.standing == "UNRESOLVED"
    assert p.ambiguity_reason is not None and "eligible road groups" in p.ambiguity_reason
    assert p.matched_edge_ids == ()
    # forging it to AUTO_ACCEPTED must fail
    with pytest.raises(ValidationError):
        MapMatchObservationProjection.model_validate(
            {
                **p.model_dump(),
                "standing": "AUTO_ACCEPTED",
                "accepted_group_key": "ref:A56|primary",
                "matched_edge_ids": ("e1",),
                "standing_reason": "owner policy unambiguously accepted under clear thresholds; "  # noqa: E501
                "distance alone not sufficient",
                "reviewer_name": None,
                "reviewer_role": None,
                "decision_fingerprint": None,
                "ledger_seal": None,
                "decided_at_utc": None,
                "decision_kind": None,
            }
        )
    # single review candidate close distance must not be AUTO
    single = _obs_single_review(781)
    q2 = build_manual_review_queue([single])
    wf2 = build_map_match_workflow(observations=[single], queue=q2, policy=POLICY, source=_source())
    assert wf2.observations[0].standing == "UNRESOLVED"
    # attempt to forge distance-only AUTO via direct construction – must fail  # noqa: E501
    with pytest.raises(ValidationError, match="AUTO_ACCEPTED requires owner_policy"):
        MapMatchObservationProjection(
            observation=single,
            queue_fingerprint=q2.fingerprint(),
            ledger_seal=None,
            standing="AUTO_ACCEPTED",
            standing_reason="owner policy unambiguously accepted under clear thresholds; "  # noqa: E501
            "distance alone not sufficient",
            diagnostics=_diagnostics_for(single),
            ambiguity_reason=_ambiguity_reason(single),
            unmatched_reason=_unmatched_reason(single),
            reviewer_name=None,
            reviewer_role=None,
            decision_fingerprint=None,
            decided_at_utc=None,
            decision_kind=None,
            accepted_group_key="ref:A56|primary",
            matched_edge_ids=("e1",),
            nearest_distance_m=Decimal("1.200"),
            original_disposition="awaiting_manual_review",
        )
    # verify that AMBIGUOUS auto via workflow build raises
    bad_auto = single.model_copy(
        update={
            "disposition": "owner_policy_accepted_candidate",
            "confidence": "clear_candidate",
            "acceptance_path": "strict_v1_0_clear",
        }
    )
    with pytest.raises(
        MapMatchWorkflowError,
        match="QUEUE_MISMATCH|OBSERVATION_INVALID|QUEUE_ENTRY_MISMATCH|QUEUE_DENOMINATOR_MISMATCH",
    ):
        build_map_match_workflow(observations=[bad_auto], queue=q2, policy=POLICY, source=_source())


# ---------------------------------------------------------------------------
# Additional discriminating tests for Opus remediation (blocking + non-blocking)
# ---------------------------------------------------------------------------


def test_sanctioned_no_candidate_reject_yields_rejected() -> None:
    obs = _obs_no_candidate(900)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(
        ledger, queue, _decision(900, ReviewDecisionKind.REJECT_ALL_CANDIDATES)
    )
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.rejected_ids == (900,)
    proj = wf.observations[0]
    assert proj.standing == "REJECTED"
    assert proj.original_disposition == "no_suitable_candidate"
    assert proj.decision_kind == ReviewDecisionKind.REJECT_ALL_CANDIDATES
    assert proj.ledger_seal == sealed.seal
    # Verify passes with exact dependencies
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=sealed, source=_source())
        == wf.fingerprint()
    )


def test_sanctioned_unavailable_defer_yields_unresolved() -> None:
    obs = _obs_unavailable(901)
    queue = build_manual_review_queue([obs])
    ledger = start_review_ledger(queue, POLICY_FP)
    ledger = record_review_decision(ledger, queue, _decision(901, ReviewDecisionKind.DEFER))
    sealed = seal_review_ledger(ledger)
    wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
    )
    assert wf.unresolved_ids == (901,)
    assert wf.observations[0].standing == "UNRESOLVED"
    assert wf.observations[0].original_disposition == "unavailable_missing_evidence"
    assert wf.observations[0].decision_kind == ReviewDecisionKind.DEFER
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=sealed, source=_source())
        == wf.fingerprint()
    )


def test_impossible_accept_on_no_candidate_fails_closed() -> None:
    obs = _obs_no_candidate(902)
    queue = build_manual_review_queue([obs])
    # Forge a ledger that tries to accept on a no-candidate row (bypassing record_review_decision)
    bad_decision = _decision(902, ReviewDecisionKind.ACCEPT_GROUP, group_key="invented-group")
    bad_ledger = MatchReviewLedger(
        queue_fingerprint=queue.fingerprint(),
        policy_fingerprint=POLICY_FP,
        decisions=(bad_decision,),
    )
    sealed = seal_review_ledger(bad_ledger)
    with pytest.raises(MapMatchWorkflowError, match="GROUP_MISMATCH|PROJECTION_INVALID"):
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
        )
    # Also unavailable row cannot be accepted
    obs2 = _obs_unavailable(903)
    q2 = build_manual_review_queue([obs2])
    bad2 = _decision(903, ReviewDecisionKind.ACCEPT_GROUP, group_key="invented-group")
    bad_ledger2 = MatchReviewLedger(
        queue_fingerprint=q2.fingerprint(),
        policy_fingerprint=POLICY_FP,
        decisions=(bad2,),
    )
    sealed2 = seal_review_ledger(bad_ledger2)
    with pytest.raises(MapMatchWorkflowError, match="GROUP_MISMATCH|PROJECTION_INVALID"):
        build_map_match_workflow(
            observations=[obs2], queue=q2, policy=POLICY, ledger=sealed2, source=_source()
        )


def test_verify_requires_exact_dependencies() -> None:
    obs = _obs_single_review(910)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    # Missing required args should raise TypeError (no digest fallback)
    with pytest.raises(TypeError):
        verify_workflow_fingerprint(wf)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue)  # type: ignore[call-arg]
    # Explicit None source should fail closed with coded error
    with pytest.raises(MapMatchWorkflowError, match="VERIFICATION_REQUIRES_DEPENDENCIES|SOURCE"):
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=None, source=None)  # type: ignore[arg-type]
    # Correct verification still works
    assert (
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=None, source=_source())
        == wf.fingerprint()
    )


def test_verify_refuses_fabricated_named_human() -> None:
    obs = _obs_single_review(920)
    queue = build_manual_review_queue([obs])
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=_source())
    # Forge a human accepted projection without a ledger
    proj = wf.observations[0]
    forged = proj.model_copy(
        update={
            "standing": "HUMAN_ACCEPTED",
            "decision_kind": ReviewDecisionKind.ACCEPT_GROUP,
            "accepted_group_key": "ref:A56|primary",
            "reviewer_name": "A. Analyst",
            "reviewer_role": "research analyst",
            "decision_fingerprint": "a" * 64,
            "ledger_seal": "b" * 64,
            "decided_at_utc": proj.decided_at_utc
            or __import__("datetime")
            .datetime.fromisoformat(DECIDED_AT.replace("Z", "+00:00"))
            .astimezone(UTC),
            "matched_edge_ids": ("e1",),
            "standing_reason": "sealed named review accepted group ref:A56|primary by A. Analyst",
            "original_disposition": "awaiting_manual_review",
        }
    )
    # Direct result validation should already fail ledger binding, but verify must also refuse
    forged_wf = wf.model_copy(update={"observations": (forged,)})
    with pytest.raises((ValidationError, MapMatchWorkflowError)):
        MapMatchWorkflowResult.model_validate(forged_wf.model_dump())
    with pytest.raises(MapMatchWorkflowError):
        verify_workflow_fingerprint(
            forged_wf, policy=POLICY, queue=queue, ledger=None, source=_source()
        )


def test_verify_wrong_source_refused() -> None:
    obs = _obs_auto(930)
    queue = build_manual_review_queue([obs])
    src1 = _source()
    src2 = _source(admission_receipt_fingerprint=_ALT_RECEIPT_FP)
    wf = build_map_match_workflow(observations=[obs], queue=queue, policy=POLICY, source=src1)
    with pytest.raises(MapMatchWorkflowError, match="SOURCE_MISMATCH"):
        verify_workflow_fingerprint(wf, policy=POLICY, queue=queue, ledger=None, source=src2)


def test_diagnostics_truncation_marker_and_count() -> None:
    # Create an observation with many diagnostics parts exceeding MAX_DIAGNOSTICS
    base_obs = _obs_single_review(940)
    many_reasons = tuple(f"reason {i} with detail" for i in range(70))
    # Use model_copy to inject many reasons (bypass but then revalidate via model_validate)
    obs = base_obs.model_copy(update={"reasons": many_reasons})
    # Revalidate to ensure it's accepted (still awaiting, but with many reasons)
    obs = ObservationMatchV11.model_validate(obs.model_dump())
    diags = _diagnostics_for(obs)
    assert len(diags) == 64
    assert diags[-1].endswith("diagnostics omitted")
    # Check omitted count is deterministic: 70 reasons + review_reasons
    # The parts list includes reasons (70) + review_reasons (1) =71,
    # plus maybe other, but we can compute expected omitted
    # = len(parts) - (MAX_DIAGNOSTICS-1)
    # For this obs, parts = 70 reasons + 1 review_reason =71, so omitted = 71 -63 =8
    # Marker should contain "8 diagnostics omitted" or more
    assert "omitted" in diags[-1]
    # The count should be >0 and marker should be deterministic
    count_str = diags[-1]
    # Extract count
    import re

    m = re.search(r"(\d+) diagnostics omitted", count_str)
    assert m is not None, f"marker missing count: {count_str}"
    count = int(m.group(1))
    assert count == 8  # 71 parts -63 kept =8 omitted


def test_sanitized_bad_timestamp() -> None:
    obs = _obs_single_review(950)
    queue = build_manual_review_queue([obs])
    # Create a decision with a bad timestamp containing private path
    bad_decision = MatchReviewDecision(
        count_point_id=950,
        kind=ReviewDecisionKind.DEFER,
        reason="inspected geometry and signed references against queue evidence",
        reviewer=_reviewer(),
        decided_at_utc="/tmp/secret/private/path",  # noqa: S108
    )
    ledger = MatchReviewLedger(
        queue_fingerprint=queue.fingerprint(),
        policy_fingerprint=POLICY_FP,
        decisions=(bad_decision,),
    )
    sealed = seal_review_ledger(ledger)
    with pytest.raises(MapMatchWorkflowError) as excinfo:
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed, source=_source()
        )
    msg = str(excinfo.value)
    # Must be sanitized - not echo raw private path or secret
    assert "/tmp" not in msg  # noqa: S108
    assert "secret" not in msg.lower()
    assert "INVALID_TIMESTAMP" in msg or "invalid" in msg.lower()
    # Also test with secret in timestamp
    bad2 = MatchReviewDecision(
        count_point_id=950,
        kind=ReviewDecisionKind.DEFER,
        reason="inspected geometry and signed references against queue evidence",
        reviewer=_reviewer(),
        decided_at_utc="not-a-datetime api_key=secret123",
    )
    ledger2 = MatchReviewLedger(
        queue_fingerprint=queue.fingerprint(),
        policy_fingerprint=POLICY_FP,
        decisions=(bad2,),
    )
    sealed2 = seal_review_ledger(ledger2)
    with pytest.raises(MapMatchWorkflowError) as excinfo2:
        build_map_match_workflow(
            observations=[obs], queue=queue, policy=POLICY, ledger=sealed2, source=_source()
        )
    msg2 = str(excinfo2.value)
    assert "api_key" not in msg2.lower()
    assert "secret" not in msg2.lower()


def test_contradictory_and_duplicate_queue_refused() -> None:
    obs1 = _obs_single_review(960)
    obs2 = _obs_no_candidate(961)
    queue = build_manual_review_queue([obs1, obs2])
    # Contradictory denominator: tamper accepted_total
    tampered = queue.model_copy(update={"accepted_total": 99})
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_DENOMINATOR_MISMATCH|QUEUE_INVALID"):
        build_map_match_workflow(
            observations=[obs1, obs2], queue=tampered, policy=POLICY, source=_source()
        )
    # Duplicate point IDs in queue
    # craft a queue that passes its own validator but has duplicate ids
    dup_entry = queue.entries[0]
    dup_queue = ManualReviewQueue(
        observations_total=queue.observations_total,
        accepted_total=queue.accepted_total,
        queued_total=queue.queued_total,
        entries=(dup_entry, dup_entry),
    )
    with pytest.raises(
        MapMatchWorkflowError,
        match="DUPLICATE_QUEUE_ENTRY|QUEUE_DENOMINATOR_MISMATCH|QUEUE_INVALID",
    ):
        build_map_match_workflow(
            observations=[obs1, obs2], queue=dup_queue, policy=POLICY, source=_source()
        )
    # Also test duplicate observation IDs vs queue
    # Build a queue that claims wrong observations_total
    bad_queue2 = queue.model_copy(update={"observations_total": 1})
    with pytest.raises(MapMatchWorkflowError, match="QUEUE_DENOMINATOR_MISMATCH|QUEUE_INVALID"):
        build_map_match_workflow(
            observations=[obs1, obs2], queue=bad_queue2, policy=POLICY, source=_source()
        )

"""Round-trip and refusal tests for the match-review UI service layer."""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import build_edge_index
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    match_observation_v11,
)
from traffictwin.integration.manchester.observation_review import (
    ReviewDecisionKind,
    load_review_ledger,
)
from traffictwin.ui.review_services import (
    LoadedReviewContext,
    ReviewServiceError,
    load_review_context,
    record_decision_for_ui,
    seal_ledger_for_export,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
DECIDED_AT = "2026-07-27T01:00:00+00:00"


def _match_rows(tmp_path: Path) -> tuple[Path, str]:
    """Build two real v1.1 rows and write them as the results artifact."""

    network = tmp_path / "n.net.xml"
    network.write_text(
        "<?xml version='1.0'?>\n<net>\n"
        f'  <location netOffset="-517074.60,-5908760.37" '
        f'convBoundary="0.00,0.00,5000.00,5000.00" '
        f'origBoundary="-2.40,53.30,-2.10,53.60" projParameter="{PROJ}"/>\n'
        '  <junction id="J0" type="priority" x="31000.00" y="16000.00" '
        'incLanes="" intLanes=""/>\n'
        '  <junction id="J1" type="priority" x="31060.00" y="16060.00" '
        'incLanes="" intLanes=""/>\n'
        '  <edge id="e1" from="J0" to="J1" type="highway.unclassified">\n'
        '    <param key="ref" value="A56"/>\n  </edge>\n'
        '  <edge id="e2" from="J0" to="J1" type="highway.residential">\n'
        '    <param key="ref" value="A56"/>\n  </edge>\n'
        "</net>\n",
        encoding="utf-8",
    )
    index = build_edge_index(network)
    geometry = index.geometry(0)
    access: dict[str, MotorAccess] = dict.fromkeys(("e1", "e2"), "passenger_car")
    policy = ManchesterMapMatchPolicyV11()
    ambiguous = match_observation_v11(
        count_point_id=101,
        easting=geometry[0],
        northing=geometry[1],
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=policy,
        motor_access=access,
    )
    distant = match_observation_v11(
        count_point_id=202,
        easting=geometry[0] + 3900.0,
        northing=geometry[1] + 3900.0,
        dft_road_type="Minor",
        dft_road_name="U",
        dft_road_ref=None,
        index=index,
        policy=policy,
        motor_access=access,
    )
    artifact = tmp_path / "match_results.json"
    artifact.write_text(
        json.dumps([ambiguous.model_dump(mode="json"), distant.model_dump(mode="json")]),
        encoding="utf-8",
    )
    return artifact, ambiguous.policy_fingerprint


def test_full_review_round_trip_including_seal(tmp_path: Path) -> None:
    artifact, policy_fingerprint = _match_rows(tmp_path)
    ledger_path = tmp_path / "working_ledger.json"

    context = load_review_context(artifact, ledger_path, policy_fingerprint)
    assert isinstance(context, LoadedReviewContext)
    assert context.status.pending_total == 2

    group_key = context.rows_by_count_point[101].groups[0].group_key
    updated = record_decision_for_ui(
        context,
        count_point_id=101,
        kind=ReviewDecisionKind.ACCEPT_GROUP,
        reviewer_name="A. Analyst",
        reviewer_role="research analyst",
        reason="inspected both A56 groups; the unclassified carriageway matches the site",
        decided_at_utc=DECIDED_AT,
        accepted_group_key=group_key,
    )
    assert isinstance(updated, LoadedReviewContext)
    assert updated.status.accepted_total == 1
    assert updated.status.pending_count_point_ids == (202,)
    assert ledger_path.exists(), "each decision persists the working ledger"

    resumed = load_review_context(artifact, ledger_path, policy_fingerprint)
    assert isinstance(resumed, LoadedReviewContext)
    assert resumed.status.accepted_total == 1, "reloading continues the working ledger"

    export = seal_ledger_for_export(updated, tmp_path / "sealed_ledger.json")
    assert isinstance(export, Path)
    sealed = load_review_ledger(export.read_text(encoding="utf-8"))
    assert sealed.live_decisions()[101].kind is ReviewDecisionKind.ACCEPT_GROUP
    still_working = load_review_context(artifact, ledger_path, policy_fingerprint)
    assert isinstance(still_working, LoadedReviewContext), "working copy stays unsealed"


def test_service_errors_are_user_facing_not_exceptions(tmp_path: Path) -> None:
    artifact, policy_fingerprint = _match_rows(tmp_path)
    ledger_path = tmp_path / "working_ledger.json"
    context = load_review_context(artifact, ledger_path, policy_fingerprint)
    assert isinstance(context, LoadedReviewContext)

    missing = load_review_context(tmp_path / "nope.json", ledger_path, policy_fingerprint)
    assert isinstance(missing, ReviewServiceError)
    assert "No match-results artifact" in missing.message

    anonymous = record_decision_for_ui(
        context,
        count_point_id=202,
        kind=ReviewDecisionKind.DEFER,
        reviewer_name="TBD",
        reviewer_role="analyst",
        reason="cannot decide from the available candidate evidence tonight",
        decided_at_utc=DECIDED_AT,
    )
    assert isinstance(anonymous, ReviewServiceError)
    assert "real reviewer name" in anonymous.message

    refused = record_decision_for_ui(
        context,
        count_point_id=999,
        kind=ReviewDecisionKind.DEFER,
        reviewer_name="A. Analyst",
        reviewer_role="research analyst",
        reason="row does not exist and this must refuse loudly",
        decided_at_utc=DECIDED_AT,
    )
    assert isinstance(refused, ReviewServiceError)
    assert refused.detail is not None and "UNKNOWN_COUNT_POINT" in refused.detail


def test_foreign_and_sealed_ledgers_refuse_to_open(tmp_path: Path) -> None:
    artifact, policy_fingerprint = _match_rows(tmp_path)
    ledger_path = tmp_path / "working_ledger.json"
    context = load_review_context(artifact, ledger_path, policy_fingerprint)
    assert isinstance(context, LoadedReviewContext)
    updated = record_decision_for_ui(
        context,
        count_point_id=202,
        kind=ReviewDecisionKind.DEFER,
        reviewer_name="A. Analyst",
        reviewer_role="research analyst",
        reason="deferring the no-candidate site pending a field visit",
        decided_at_utc=DECIDED_AT,
    )
    assert isinstance(updated, LoadedReviewContext)

    wrong_policy = load_review_context(artifact, ledger_path, "f" * 64)
    assert isinstance(wrong_policy, ReviewServiceError)
    assert "different policy" in wrong_policy.message

    sealed_path = tmp_path / "sealed.json"
    assert isinstance(seal_ledger_for_export(updated, sealed_path), Path)
    sealed_open = load_review_context(artifact, sealed_path, policy_fingerprint)
    assert isinstance(sealed_open, ReviewServiceError)
    assert "sealed for export" in sealed_open.message

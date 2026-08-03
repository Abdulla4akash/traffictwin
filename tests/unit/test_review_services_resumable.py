from __future__ import annotations

import json
import stat
from hashlib import sha256
from pathlib import Path

import pytest

import traffictwin.ui.review_services as services
from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import build_edge_index
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    ObservationMatchV11,
    match_observation_v11,
)
from traffictwin.integration.manchester.observation_review import (
    ReviewDecisionKind,
    load_review_ledger,
)
from traffictwin.release.compatibility import initialise_v07_workspace
from traffictwin.ui.review_services import (
    LoadedReviewContext,
    RegisteredReviewArtifact,
    ReviewArtifactRegistration,
    ReviewServiceError,
    changed_decision_count,
    discover_registered_review_artifacts,
    filtered_review_rows,
    load_review_context,
    record_decision_for_ui,
    review_ledger_path,
    seal_ledger_for_export,
)

PROJ = "+proj=utm +zone=30 +ellps=WGS84 +datum=WGS84 +units=m +no_defs"
DECIDED = "2026-08-03T12:00:00+00:00"


def _rows(tmp_path: Path) -> tuple[ObservationMatchV11, ObservationMatchV11]:
    network = tmp_path / "review.net.xml"
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
    x, y = index.geometry(0)[:2]
    access: dict[str, MotorAccess] = dict.fromkeys(("e1", "e2"), "passenger_car")
    policy = ManchesterMapMatchPolicyV11()
    ambiguous = match_observation_v11(
        count_point_id=101,
        easting=x,
        northing=y,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_road_ref="A56",
        index=index,
        policy=policy,
        motor_access=access,
    )
    distant = match_observation_v11(
        count_point_id=202,
        easting=x + 3900,
        northing=y + 3900,
        dft_road_type="Minor",
        dft_road_name="U",
        dft_road_ref=None,
        index=index,
        policy=policy,
        motor_access=access,
    )
    return ambiguous, distant


def _artifact(tmp_path: Path, rows: tuple[ObservationMatchV11, ...]) -> Path:
    artifact = tmp_path / "match-results.json"
    artifact.write_text(json.dumps([row.model_dump(mode="json") for row in rows]), encoding="utf-8")
    return artifact


def _context(tmp_path: Path) -> LoadedReviewContext:
    rows = _rows(tmp_path)
    loaded = load_review_context(
        _artifact(tmp_path, rows), tmp_path / "private" / "review.working.json"
    )
    assert isinstance(loaded, LoadedReviewContext)
    return loaded


def _defer(
    context: LoadedReviewContext, count_point_id: int
) -> LoadedReviewContext | ReviewServiceError:
    return record_decision_for_ui(
        context,
        count_point_id=count_point_id,
        kind=ReviewDecisionKind.DEFER,
        reviewer_name="A. Analyst",
        reviewer_role="research analyst",
        reason="deferred pending an authorised inspection of the complete evidence",
        decided_at_utc=DECIDED,
    )


def test_atomic_readback_and_concurrent_editor_refusal(tmp_path: Path) -> None:
    first_editor = _context(tmp_path)
    second_editor = load_review_context(tmp_path / "match-results.json", first_editor.ledger_path)
    assert isinstance(second_editor, LoadedReviewContext)

    saved = _defer(first_editor, 202)

    assert isinstance(saved, LoadedReviewContext)
    assert saved.status.deferred_total == 1
    assert stat.S_IMODE(saved.ledger_path.stat().st_mode) == 0o600
    assert saved.loaded_ledger_sha256 == sha256(saved.ledger_path.read_bytes()).hexdigest()
    refused = _defer(second_editor, 101)
    assert isinstance(refused, ReviewServiceError)
    assert refused.code == "LEDGER_CHANGED"
    persisted = load_review_context(tmp_path / "match-results.json", saved.ledger_path)
    assert isinstance(persisted, LoadedReviewContext)
    assert persisted.status.deferred_total == 1
    assert persisted.status.pending_count_point_ids == (101,)


def test_atomic_replace_interruption_preserves_previous_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    saved = _defer(_context(tmp_path), 202)
    assert isinstance(saved, LoadedReviewContext)
    before = saved.ledger_path.read_bytes()

    def fail_replace(_source: Path, _target: Path) -> None:
        raise OSError("injected interruption")

    monkeypatch.setattr("traffictwin.ui.review_services.os.replace", fail_replace)
    refused = _defer(saved, 101)

    assert isinstance(refused, ReviewServiceError)
    assert refused.code == "LEDGER_WRITE_FAILED"
    assert saved.ledger_path.read_bytes() == before
    siblings = tuple(saved.ledger_path.parent.glob(f".{saved.ledger_path.name}.*"))
    assert [item.name for item in siblings] == [f".{saved.ledger_path.name}.lock"]


def test_filters_bookkeeping_and_supersession_preserve_prior_decision(tmp_path: Path) -> None:
    saved = _defer(_context(tmp_path), 202)
    assert isinstance(saved, LoadedReviewContext)
    prior = saved.ledger.live_decisions()[202]
    revised = record_decision_for_ui(
        saved,
        count_point_id=202,
        kind=ReviewDecisionKind.REJECT_ALL_CANDIDATES,
        reviewer_name="A. Analyst",
        reviewer_role="research analyst",
        reason="inspection found that no candidate group represents this count point",
        decided_at_utc="2026-08-03T12:05:00+00:00",
        supersedes=prior.fingerprint(),
    )
    assert isinstance(revised, LoadedReviewContext)

    rejected = filtered_review_rows(revised, decision_states=("rejected",))
    no_candidates = filtered_review_rows(revised, candidate_buckets=("none",))
    signed_reference = filtered_review_rows(revised, query="A56")
    assert [view.entry.count_point_id for view in rejected] == [202]
    assert rejected[0].revision_count == 1
    assert [view.entry.count_point_id for view in no_candidates] == [202]
    assert [view.entry.count_point_id for view in signed_reference] == [101]
    assert changed_decision_count(revised) == 1
    assert len(revised.ledger.decisions) == 2
    assert revised.ledger.decisions[0] == prior


def test_content_addressed_seal_is_exact_retry_and_keeps_working_copy(tmp_path: Path) -> None:
    saved = _defer(_context(tmp_path), 202)
    assert isinstance(saved, LoadedReviewContext)
    before = saved.ledger_path.read_bytes()

    first = seal_ledger_for_export(saved)
    second = seal_ledger_for_export(saved)

    assert isinstance(first, Path)
    assert second == first
    assert saved.ledger_path.read_bytes() == before
    sealed = load_review_ledger(first.read_text(encoding="utf-8"))
    assert sealed.live_decisions()[202].kind is ReviewDecisionKind.DEFER
    assert stat.S_IMODE(first.stat().st_mode) == 0o600


def test_registered_discovery_binds_digest_rows_queue_policy_and_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = initialise_v07_workspace(tmp_path / "workspace-v0.7").path
    rows = _rows(tmp_path)
    artifact = workspace / "manchester" / "test-match-results.json"
    artifact.write_text(json.dumps([row.model_dump(mode="json") for row in rows]), encoding="utf-8")
    payload = artifact.read_bytes()
    registration = ReviewArtifactRegistration(
        artifact_id="test-registration",
        label="Test registration",
        relative_path=artifact.relative_to(workspace),
        artifact_sha256=sha256(payload).hexdigest(),
        rows_total=2,
        queued_total=2,
        policy_fingerprint=rows[0].policy_fingerprint,
    )
    monkeypatch.setattr(services, "REGISTERED_REVIEW_ARTIFACTS", (registration,))

    discovered = discover_registered_review_artifacts(workspace)

    assert isinstance(discovered, tuple) and len(discovered) == 1
    option = discovered[0]
    assert isinstance(option, RegisteredReviewArtifact)
    assert review_ledger_path(workspace, option).is_relative_to(workspace)
    artifact.write_bytes(payload + b" ")
    refused = discover_registered_review_artifacts(workspace)
    assert isinstance(refused, ReviewServiceError)
    assert refused.code == "ARTIFACT_DIGEST_MISMATCH"
    assert str(workspace) not in refused.message
    assert str(workspace) not in (refused.detail or "")


def test_full_174_row_synthetic_session_resumes_without_bulk_action(tmp_path: Path) -> None:
    base = _rows(tmp_path)[1]
    rows = tuple(base.model_copy(update={"count_point_id": 10_000 + index}) for index in range(174))
    artifact = _artifact(tmp_path, rows)
    ledger = tmp_path / "private" / "full-session.working.json"
    loaded = load_review_context(artifact, ledger)
    assert isinstance(loaded, LoadedReviewContext)
    assert loaded.status.pending_total == 174

    context = loaded
    for count_point_id in context.status.pending_count_point_ids[:87]:
        outcome = _defer(context, count_point_id)
        assert isinstance(outcome, LoadedReviewContext)
        context = outcome
    resumed = load_review_context(artifact, ledger)
    assert isinstance(resumed, LoadedReviewContext)
    assert resumed.status.pending_total == 87
    for count_point_id in resumed.status.pending_count_point_ids:
        outcome = _defer(resumed, count_point_id)
        assert isinstance(outcome, LoadedReviewContext)
        resumed = outcome

    assert resumed.status.queued_total == 174
    assert resumed.status.pending_total == 0
    assert resumed.status.deferred_total == 174
    assert len(resumed.ledger.decisions) == 174
    assert all(not decision.bulk_operation for decision in resumed.ledger.decisions)

"""Scenario and run registry (post-v1 R-1, design §8 state-machine list).

The registry records lifecycle; it decides nothing. Tested: valid and
invalid event orders, stale-prior conflicts, changed-draft approval
mismatch, agent-approval refusal, execution-without-authority refusal,
deviation persistence, non-admitted separation, deterministic replay from
the log bytes, idempotent re-appends, and privacy screening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.platform.scenario_registry import (
    EventReceipt,
    RegistryEvent,
    ScenarioRecord,
    ScenarioRegistryError,
    ScenarioRunRegistry,
    scenario_record_from_draft,
)

NOW = "2026-08-01T22:00:00+00:00"
APPROVAL_ARTIFACT_DIGEST = "d" * 64
ADMISSION_ARTIFACT_DIGEST = "e" * 64


def _approval_validator(record: ScenarioRecord, payload: dict[str, str]) -> bool:
    return (
        payload.get("approval_artifact_digest") == APPROVAL_ARTIFACT_DIGEST
        and payload.get("draft_design_digest") == record.draft_design_digest
    )


def _admission_validator(record: ScenarioRecord, payload: dict[str, str]) -> bool:
    del record
    return payload.get("admission_artifact_digest") == ADMISSION_ARTIFACT_DIGEST


def _record() -> ScenarioRecord:
    return scenario_record_from_draft(
        draft_design_json='{"experiment_id": "vec-whatif-inc-cap0p75"}',
        predeclaration_markdown="# draft predeclaration",
        trace="inc",
        actor="ukfleettrain_mappo_model_c_17",
        capacity=0.75,
        fleet_preset="uk2030",
        seed_proposal=(30, 31, 32),
        prediction_digest="a" * 64,
        prediction_available=True,
        created_at_utc=NOW,
        creator_class="composer_template",
    )


def _registry(tmp_path: Path) -> tuple[ScenarioRunRegistry, ScenarioRecord, str]:
    registry = ScenarioRunRegistry(
        tmp_path / "registry.jsonl",
        approval_validator=_approval_validator,
        admission_validator=_admission_validator,
    )
    record = _record()
    receipt = registry.register_scenario(record)
    return registry, record, receipt.event_digest


def _event(
    record: ScenarioRecord,
    event_type: str,
    prior: str,
    payload: dict[str, str],
) -> RegistryEvent:
    return RegistryEvent(
        scenario_id=record.scenario_id,
        event_type=event_type,  # type: ignore[arg-type]
        recorded_at_utc=NOW,
        prior_digest=prior,
        payload=payload,
    )


def _approval(record: ScenarioRecord, prior: str) -> RegistryEvent:
    return _event(
        record,
        "approval_bound",
        prior,
        {
            "approved_by": "Abdulla (repository owner)",
            "draft_design_digest": record.draft_design_digest,
            "approval_artifact_digest": APPROVAL_ARTIFACT_DIGEST,
        },
    )


def test_registration_is_idempotent_and_conflicts_are_typed(tmp_path: Path) -> None:
    registry, record, _ = _registry(tmp_path)
    replay = registry.register_scenario(record)
    assert replay.idempotent_replay
    changed = record.model_copy(update={"capacity": 1.0})
    with pytest.raises(ScenarioRegistryError) as excinfo:
        registry.register_scenario(changed)
    assert excinfo.value.code == "SCENARIO_DIGEST_CONFLICT"


def test_the_happy_path_keeps_every_standing_distinct(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    r1 = registry.append_event(_approval(record, genesis))
    r2 = registry.append_event(
        _event(
            record,
            "execution_receipted",
            r1.event_digest,
            {
                "design_fingerprint": record.draft_design_digest,
                "receipt_digest": "b" * 64,
            },
        )
    )
    r3 = registry.append_event(
        _event(record, "deviation_recorded", r2.event_digest, {"deviation": "cell retried"})
    )
    r4 = registry.append_event(
        _event(record, "analysis_bound", r3.event_digest, {"analysis_digest": "c" * 64})
    )
    registry.append_event(
        _event(
            record,
            "admission_recorded",
            r4.event_digest,
            {
                "record_kind": "vec_fresh_admission_record",
                "status": "admitted",
                "admission_artifact_digest": ADMISSION_ARTIFACT_DIGEST,
            },
        )
    )
    timeline = registry.get_timeline(record.scenario_id)
    assert timeline.approved and timeline.executed and timeline.analysed
    assert timeline.admission_status == "admitted"
    # Deviations stay visible after admission, and the prediction stays
    # evidence: false whatever happened later.
    assert timeline.deviations == ("cell retried",)
    assert timeline.scenario.evidence is False
    assert timeline.scenario.prediction is True
    assert registry.require_admitted(record.scenario_id).in_admitted_view


def test_agent_identities_can_never_approve_or_close(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    for identity in ("agent", "TBD", "codex run", "Claude", "auto-approver"):
        with pytest.raises(ScenarioRegistryError) as excinfo:
            registry.append_event(
                _event(
                    record,
                    "approval_bound",
                    genesis,
                    {
                        "approved_by": identity,
                        "draft_design_digest": record.draft_design_digest,
                    },
                )
            )
        assert excinfo.value.code == "AGENT_APPROVAL_FORBIDDEN"
    with pytest.raises(ScenarioRegistryError) as closed:
        registry.append_event(
            _event(record, "scenario_closed", genesis, {"closed_by": "agent", "reason": "x"})
        )
    assert closed.value.code == "AGENT_APPROVAL_FORBIDDEN"


def test_changed_draft_approval_and_stale_priors_refuse(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    with pytest.raises(ScenarioRegistryError) as mismatch:
        registry.append_event(
            _event(
                record,
                "approval_bound",
                genesis,
                {"approved_by": "Abdulla (owner)", "draft_design_digest": "0" * 64},
            )
        )
    assert mismatch.value.code == "APPROVAL_DIGEST_MISMATCH"
    receipt = registry.append_event(_approval(record, genesis))
    # An IDENTICAL event replays idempotently rather than conflicting …
    assert registry.append_event(_approval(record, genesis)).idempotent_replay
    # … but a DIFFERENT event chained on the stale genesis digest refuses.
    with pytest.raises(ScenarioRegistryError) as stale:
        registry.append_event(
            _event(
                record,
                "scenario_closed",
                genesis,
                {"closed_by": "Abdulla (owner)", "reason": "stale-prior probe"},
            )
        )
    assert stale.value.code == "PRIOR_EVENT_MISMATCH"
    assert isinstance(receipt, EventReceipt)


def test_execution_needs_authority_and_matching_fingerprint(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    with pytest.raises(ScenarioRegistryError) as unauthorised:
        registry.append_event(
            _event(
                record,
                "execution_receipted",
                genesis,
                {"design_fingerprint": record.draft_design_digest},
            )
        )
    assert unauthorised.value.code == "INVALID_TRANSITION"
    approved = registry.append_event(_approval(record, genesis))
    with pytest.raises(ScenarioRegistryError) as drifted:
        registry.append_event(
            _event(
                record,
                "execution_receipted",
                approved.event_digest,
                {"design_fingerprint": "f" * 64},
            )
        )
    assert drifted.value.code == "DESIGN_FINGERPRINT_MISMATCH"


def test_admission_is_copied_from_authoritative_records_only(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    approved = registry.append_event(_approval(record, genesis))
    executed = registry.append_event(
        _event(
            record,
            "execution_receipted",
            approved.event_digest,
            {"design_fingerprint": record.draft_design_digest},
        )
    )
    with pytest.raises(ScenarioRegistryError) as excinfo:
        registry.append_event(
            _event(
                record,
                "admission_recorded",
                executed.event_digest,
                {"record_kind": "dashboard_click", "status": "admitted"},
            )
        )
    assert excinfo.value.code == "ADMISSION_RECORD_UNAUTHORISED"
    registry.append_event(
        _event(
            record,
            "admission_recorded",
            executed.event_digest,
            {
                "record_kind": "evidence_record",
                "status": "non_admitted",
                "admission_artifact_digest": ADMISSION_ARTIFACT_DIGEST,
            },
        )
    )
    timeline = registry.get_timeline(record.scenario_id)
    # Execution success is not admission: the timeline is complete but stays
    # outside every admitted view, and promotion is a typed refusal.
    assert timeline.executed
    assert timeline.admission_status == "non_admitted"
    assert registry.admitted_view() == ()
    with pytest.raises(ScenarioRegistryError) as promoted:
        registry.require_admitted(record.scenario_id)
    assert promoted.value.code == "NON_ADMITTED_PROMOTION"


def test_asserted_approval_or_admission_kind_is_not_proof(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    forged_approval = _approval(record, genesis).model_copy(
        update={
            "payload": {
                "approved_by": "Abdulla (repository owner)",
                "draft_design_digest": record.draft_design_digest,
                "approval_artifact_digest": "f" * 64,
            }
        }
    )
    with pytest.raises(ScenarioRegistryError) as approval:
        registry.append_event(forged_approval)
    assert approval.value.code == "APPROVAL_DIGEST_MISMATCH"

    approved = registry.append_event(_approval(record, genesis))
    executed = registry.append_event(
        _event(
            record,
            "execution_receipted",
            approved.event_digest,
            {"design_fingerprint": record.draft_design_digest},
        )
    )
    with pytest.raises(ScenarioRegistryError) as admission:
        registry.append_event(
            _event(
                record,
                "admission_recorded",
                executed.event_digest,
                {
                    "record_kind": "evidence_record",
                    "status": "admitted",
                    "admission_artifact_digest": "f" * 64,
                },
            )
        )
    assert admission.value.code == "ADMISSION_RECORD_UNAUTHORISED"


def test_replay_rebuilds_identical_timelines_from_log_bytes(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    approved = registry.append_event(_approval(record, genesis))
    registry.append_event(
        _event(
            record,
            "execution_receipted",
            approved.event_digest,
            {"design_fingerprint": record.draft_design_digest},
        )
    )
    reloaded = ScenarioRunRegistry(
        tmp_path / "registry.jsonl",
        approval_validator=_approval_validator,
        admission_validator=_admission_validator,
    )
    original = registry.get_timeline(record.scenario_id)
    replayed = reloaded.get_timeline(record.scenario_id)
    assert replayed.head_digest == original.head_digest
    assert replayed.events == original.events
    # And an identical re-append after reload is an idempotent replay.
    replay = reloaded.append_event(_approval(record, genesis))
    assert replay.idempotent_replay


def test_private_content_is_screened_everywhere(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    with pytest.raises(ScenarioRegistryError) as excinfo:
        registry.append_event(
            _event(
                record,
                "approval_bound",
                genesis,
                {
                    "approved_by": "Abdulla (owner)",
                    "draft_design_digest": record.draft_design_digest,
                    "note": "stored at /Users/someone/private.txt",
                },
            )
        )
    assert excinfo.value.code == "PRIVATE_CONTENT_DETECTED"


def test_no_run_surface_exists() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "traffictwin"
        / "platform"
        / "scenario_registry.py"
    ).read_text(encoding="utf-8")
    assert "execute_campaign" not in source
    assert "subprocess" not in source
    forbidden_methods = ("def run(", "def launch(", "def execute(")
    assert not any(marker in source for marker in forbidden_methods)


def test_closed_scenarios_are_terminal(tmp_path: Path) -> None:
    registry, record, genesis = _registry(tmp_path)
    closed = registry.append_event(
        _event(
            record,
            "scenario_closed",
            genesis,
            {"closed_by": "Abdulla (owner)", "reason": "superseded by a new revision"},
        )
    )
    with pytest.raises(ScenarioRegistryError) as excinfo:
        registry.append_event(_approval(record, closed.event_digest))
    assert excinfo.value.code == "INVALID_TRANSITION"
    timeline = registry.get_timeline(record.scenario_id)
    assert timeline.closed
    assert timeline.closure_reason == "superseded by a new revision"

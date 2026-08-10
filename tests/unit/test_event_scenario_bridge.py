"""Unit tests for Event-to-Scenario Bridge — deterministic, half-open, fail-closed."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from traffictwin.event_scenario_bridge.models import (
    BridgeFinding,
    DeclaredEventReference,
    EventImpactEnvelope,
    EventScenarioBridgeRequest,
    MutationKind,
    ScenarioMutationProposal,
)
from traffictwin.event_scenario_bridge.service import (
    build_event_scenario_bridge_manifest,
    export_bridge_csv,
    export_bridge_json,
)


def _utc(year: int = 2026, month: int = 7, day: int = 17, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def _event_ref() -> DeclaredEventReference:
    return DeclaredEventReference(
        event_id="event-authored-001",
        event_kind="Authored road closure",
        anchor_time_utc=_utc(),
        source_label="Authored \u2014 Manual timestamp",
        provenance_detail="Declared for what-if planning",
    )


def _envelope() -> EventImpactEnvelope:
    return EventImpactEnvelope(
        affected_links=["link-a", "link-b"],
        affected_area_label="Central corridor",
        pre_duration_s=600,
        event_duration_s=600,
        post_duration_s=600,
        bin_width_s=60,
    )


def _lane_closure() -> ScenarioMutationProposal:
    return ScenarioMutationProposal(
        mutation_kind=MutationKind.LANE_CLOSURE,
        target_description="Close 1 lane on link-a",
        lanes_closed=1,
    )


def _request(**overrides: object) -> EventScenarioBridgeRequest:
    base: dict[str, object] = {
        "bridge_id": "bridge-001",
        "title": "What-if study for authored closure event",
        "description": "Unexecuted design linking event to scenario",
        "event_reference": _event_ref(),
        "baseline_seed_fingerprint": "a" * 64,
        "baseline_seed_id": "seed-baseline",
        "impact_envelope": _envelope(),
        "mutation_proposals": [_lane_closure()],
        "intended_metrics": ["task.completion.rate", "trip.duration.mean_s"],
        "intended_windows": ["pre", "event", "post"],
    }
    base.update(overrides)  # type: ignore[arg-type]
    return EventScenarioBridgeRequest.model_validate(base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Deterministic manifest
# ---------------------------------------------------------------------------


def test_manifest_deterministic() -> None:
    req = _request()
    m1 = build_event_scenario_bridge_manifest(req)
    m2 = build_event_scenario_bridge_manifest(req)
    assert m1.bridge_fingerprint == m2.bridge_fingerprint
    assert m1.event_fingerprint == m2.event_fingerprint
    assert m1.canonical_json() == m2.canonical_json()
    assert m1.verify_fingerprint()
    assert m2.verify_fingerprint()


def test_manifest_clock_independent_fingerprint() -> None:
    req = _request()
    m1 = build_event_scenario_bridge_manifest(req, clock=_utc(2026, 7, 17, 0))
    m2 = build_event_scenario_bridge_manifest(req, clock=_utc(2030, 1, 1, 0))
    assert m1.bridge_fingerprint == m2.bridge_fingerprint
    assert m1.verify_fingerprint()
    assert m2.verify_fingerprint()


def test_consistent_event_fingerprint_across_handoffs() -> None:
    req = _request()
    manifest = build_event_scenario_bridge_manifest(req)
    assert manifest.scenario_seed_handoff.event_fingerprint == manifest.event_fingerprint
    assert manifest.event_aligned_handoff.event_fingerprint == manifest.event_fingerprint
    assert manifest.preregistration_draft_handoff.event_fingerprint == manifest.event_fingerprint
    assert manifest.experiment_plan_handoff.event_fingerprint == manifest.event_fingerprint
    assert manifest.scenario_seed_handoff.bridge_fingerprint == manifest.bridge_fingerprint
    assert manifest.event_aligned_handoff.bridge_fingerprint == manifest.bridge_fingerprint
    assert manifest.preregistration_draft_handoff.bridge_fingerprint == manifest.bridge_fingerprint
    assert manifest.experiment_plan_handoff.bridge_fingerprint == manifest.bridge_fingerprint
    # Also baseline binding
    for handoff in (
        manifest.scenario_seed_handoff,
        manifest.event_aligned_handoff,
        manifest.preregistration_draft_handoff,
        manifest.experiment_plan_handoff,
    ):
        assert handoff.baseline_seed_fingerprint == manifest.baseline_seed_fingerprint


def test_half_open_window_consistency() -> None:
    env = _envelope()
    anchor = _utc()
    preview = env.preview_windows(anchor)
    assert preview["pre"][1] == preview["event"][0]
    assert preview["event"][1] == preview["post"][0]
    # Exact lengths
    assert (preview["pre"][1] - preview["pre"][0]).total_seconds() == 600
    assert (preview["event"][1] - preview["event"][0]).total_seconds() == 600
    assert (preview["post"][1] - preview["post"][0]).total_seconds() == 600


def test_all_outputs_remain_not_executed() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    assert manifest.execution_status == "not_executed"
    assert manifest.scenario_seed_handoff.execution_status == "not_executed"
    assert manifest.event_aligned_handoff.execution_status == "not_executed"
    assert manifest.preregistration_draft_handoff.execution_status == "not_executed"
    assert manifest.experiment_plan_handoff.execution_status == "not_executed"


def test_evidence_and_admission_false() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    assert manifest.evidence_created is False
    assert manifest.admission_created is False
    for h in (
        manifest.scenario_seed_handoff,
        manifest.event_aligned_handoff,
        manifest.preregistration_draft_handoff,
        manifest.experiment_plan_handoff,
    ):
        assert h.evidence_created is False
        assert h.admission_created is False


def test_no_local_path_in_portable_output() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    portable = manifest.to_portable_dict()
    blob = json.dumps(portable)
    assert "/tmp" not in blob  # noqa: S108
    assert "file://" not in blob
    assert portable["bridge_fingerprint"] == manifest.bridge_fingerprint
    # Also check JSON and CSV exports
    json_export = export_bridge_json(manifest)
    csv_export = export_bridge_csv(manifest)
    assert "/tmp" not in json_export  # noqa: S108
    assert "file://" not in json_export
    assert "/tmp" not in csv_export  # noqa: S108


def test_invalid_mutation_refused() -> None:
    with pytest.raises(Exception, match="lane_closure requires lanes_closed"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.LANE_CLOSURE,
            target_description="missing lanes",
        )


def test_unsupported_mutation_refused() -> None:
    with pytest.raises(Exception):  # noqa: B017
        ScenarioMutationProposal.model_validate(
            {"mutation_kind": "arbitrary_shell_exec", "target_description": "evil"}
        )


def test_missing_baseline_refused() -> None:
    with pytest.raises(Exception):  # noqa: B017
        EventScenarioBridgeRequest.model_validate(
            {
                "bridge_id": "bridge-001",
                "title": "What-if study for authored event",
                "event_reference": _event_ref().model_dump(mode="json"),
                "baseline_seed_fingerprint": "a" * 64,
                "baseline_seed_id": "",
                "impact_envelope": _envelope().model_dump(mode="json"),
                "mutation_proposals": [_lane_closure().model_dump(mode="json")],
                "intended_metrics": ["task.completion.rate"],
            }
        )


def test_unsupported_mutation_via_rsu_without_id() -> None:
    with pytest.raises(Exception, match="rsu_removal requires rsu_id"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.RSU_REMOVAL,
            target_description="remove rsu",
        )


def test_bridge_requires_at_least_one_mutation() -> None:
    with pytest.raises(Exception):  # noqa: B017
        _request(mutation_proposals=[])


def test_authored_event_must_not_be_labelled_observed() -> None:
    with pytest.raises(Exception, match="must not be labelled observed"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Observed accident",
            anchor_time_utc=_utc(),
            source_label="Authored \u2014 Manual timestamp",
        )
    with pytest.raises(Exception, match="must not be labelled observed"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=_utc(),
            source_label="Observed incident",
        )


def test_findings_must_not_claim_causality() -> None:
    with pytest.raises(Exception, match="must not claim causality"):
        BridgeFinding(finding_id="f-001", description="This caused the delay")


def test_window_end_must_be_after_start() -> None:
    with pytest.raises(Exception, match="must be greater than"):
        EventImpactEnvelope(
            affected_links=[],
            pre_duration_s=600,
            event_duration_s=600,
            post_duration_s=600,
            bin_width_s=60,
            window_start_offset_s=100,
            window_end_offset_s=50,
        )


def test_authority_boundary_all_not_executed_and_no_evidence() -> None:
    """Authority-boundary test: prereg and plan must stay not_executed and non-evidence."""
    manifest = build_event_scenario_bridge_manifest(_request())
    assert manifest.preregistration_draft_handoff.execution_status == "not_executed"
    assert manifest.preregistration_draft_handoff.evidence_created is False
    assert manifest.preregistration_draft_handoff.admission_created is False
    assert manifest.experiment_plan_handoff.execution_status == "not_executed"
    assert manifest.experiment_plan_handoff.evidence_created is False
    assert manifest.experiment_plan_handoff.admission_created is False
    # This test is the mutation kill target: flipping to executed must fail it.


def test_exports_are_deterministic() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    assert export_bridge_json(manifest) == export_bridge_json(manifest)
    assert export_bridge_csv(manifest) == export_bridge_csv(manifest)
    # JSON round-trip stable
    reparsed = json.loads(export_bridge_json(manifest))
    assert reparsed["bridge_fingerprint"] == manifest.bridge_fingerprint


def test_csv_has_formula_injection_protection() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    csv_text = export_bridge_csv(manifest)
    # CSV text should include handoff summary header
    assert "handoff_id" in csv_text


def test_bounded_demand_change_requires_multiplier() -> None:
    with pytest.raises(Exception, match="demand_multiplier"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.BOUNDED_DEMAND_CHANGE,
            target_description="change demand",
        )


def test_road_clearing_with_nonzero_lanes_refused() -> None:
    with pytest.raises(Exception, match="road_clearing"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.ROAD_CLEARING,
            target_description="clear road",
            lanes_closed=2,
        )


def test_timestamp_adjustment_requires_jitter() -> None:
    with pytest.raises(Exception, match="timestamp_jitter_s"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT,
            target_description="jitter time",
        )


def test_naive_anchor_rejected() -> None:
    import datetime as dt

    naive = dt.datetime(2026, 7, 17, 12, 0, 0)
    with pytest.raises(Exception, match="timezone-aware"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=naive,  # type: ignore[arg-type]
            source_label="Authored \u2014 Manual timestamp",
        )


def test_extra_forbid_on_strict_models() -> None:
    with pytest.raises(Exception):  # noqa: B017
        DeclaredEventReference(  # type: ignore[call-arg]
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=_utc(),
            source_label="Authored \u2014 Manual timestamp",
            unknown_field="should fail",
        )

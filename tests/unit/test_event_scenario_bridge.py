"""Unit tests for Event-to-Scenario Bridge — deterministic, half-open, fail-closed."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from traffictwin.event_scenario_bridge.models import (
    BridgeFinding,
    DeclaredEventReference,
    EventImpactEnvelope,
    EventScenarioBridgeRequest,
    MutationKind,
    ScenarioMutationProposal,
)
from traffictwin.event_scenario_bridge.service import (
    EventScenarioBridgeError,
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
    base.update(overrides)
    return EventScenarioBridgeRequest.model_validate(base)


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
    with pytest.raises(ValidationError, match="lane_closure requires lanes_closed"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.LANE_CLOSURE,
            target_description="missing lanes",
        )


def test_unsupported_mutation_refused() -> None:
    with pytest.raises(ValidationError):
        ScenarioMutationProposal.model_validate(
            {"mutation_kind": "arbitrary_shell_exec", "target_description": "evil"}
        )


def test_missing_baseline_refused() -> None:
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError, match="rsu_removal requires rsu_id"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.RSU_REMOVAL,
            target_description="remove rsu",
        )


def test_bridge_requires_at_least_one_mutation() -> None:
    with pytest.raises(ValidationError):
        _request(mutation_proposals=[])


def test_authored_event_must_not_be_labelled_observed() -> None:
    with pytest.raises(ValidationError, match="must not be labelled observed"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Observed accident",
            anchor_time_utc=_utc(),
            source_label="Authored \u2014 Manual timestamp",
        )
    with pytest.raises(ValidationError, match="must not be labelled observed"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=_utc(),
            source_label="Observed incident",
        )


def test_findings_must_not_claim_causality() -> None:
    with pytest.raises(ValidationError, match="must not claim causality"):
        BridgeFinding(finding_id="f-001", description="This caused the delay")


def test_event_impact_envelope_rejects_unknown_window_offsets() -> None:
    # Window offsets were removed; extra fields must be rejected via strict extra=forbid  # noqa: E501
    with pytest.raises(ValidationError):
        EventImpactEnvelope.model_validate(
            {
                "affected_links": [],
                "pre_duration_s": 600,
                "event_duration_s": 600,
                "post_duration_s": 600,
                "bin_width_s": 60,
                "window_start_offset_s": -300,
            }
        )
    with pytest.raises(ValidationError):
        EventImpactEnvelope.model_validate(
            {
                "affected_links": [],
                "pre_duration_s": 600,
                "event_duration_s": 600,
                "post_duration_s": 600,
                "bin_width_s": 60,
                "window_end_offset_s": 300,
            }
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
    with pytest.raises(ValidationError, match="demand_multiplier"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.BOUNDED_DEMAND_CHANGE,
            target_description="change demand",
        )


def test_road_clearing_with_nonzero_lanes_refused() -> None:
    with pytest.raises(ValidationError, match="road_clearing"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.ROAD_CLEARING,
            target_description="clear road",
            lanes_closed=2,
        )


def test_timestamp_adjustment_requires_jitter() -> None:
    with pytest.raises(ValidationError, match="timestamp_jitter_s"):
        ScenarioMutationProposal(
            mutation_kind=MutationKind.TIMESTAMP_EVENT_WINDOW_ADJUSTMENT,
            target_description="jitter time",
        )


def test_naive_anchor_rejected() -> None:
    import datetime as dt

    naive = dt.datetime(2026, 7, 17, 12, 0, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        DeclaredEventReference(
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=naive,
            source_label="Authored \u2014 Manual timestamp",
        )


def test_extra_forbid_on_strict_models() -> None:
    with pytest.raises(ValidationError):
        DeclaredEventReference(  # type: ignore[call-arg]
            event_id="event-001",
            event_kind="Authored closure",
            anchor_time_utc=_utc(),
            source_label="Authored \u2014 Manual timestamp",
            unknown_field="should fail",
        )


def test_b1_embedded_posix_paths_refused_on_multiple_surfaces() -> None:
    hostile = "baseline sourced from /Users/akashx/AntigravityTest/diss/net.xml"
    # title
    with pytest.raises(EventScenarioBridgeError):
        build_event_scenario_bridge_manifest(_request(title=hostile))
    # description
    with pytest.raises(EventScenarioBridgeError):
        build_event_scenario_bridge_manifest(_request(description=hostile))
    # event provenance_detail
    ref = _event_ref().model_copy(update={"provenance_detail": hostile})
    with pytest.raises(EventScenarioBridgeError):
        build_event_scenario_bridge_manifest(_request(event_reference=ref))
    # affected_area_label
    env = EventImpactEnvelope(
        affected_links=["link-a"],
        affected_area_label=hostile,
        pre_duration_s=600,
        event_duration_s=600,
        post_duration_s=600,
        bin_width_s=60,
    )
    with pytest.raises(EventScenarioBridgeError):
        build_event_scenario_bridge_manifest(_request(impact_envelope=env))
    # mutation target_description
    hostile_proposal = ScenarioMutationProposal(
        mutation_kind=MutationKind.LANE_CLOSURE,
        target_description=hostile,
        lanes_closed=1,
    )
    with pytest.raises(EventScenarioBridgeError):
        build_event_scenario_bridge_manifest(_request(mutation_proposals=[hostile_proposal]))


def test_b1_other_path_forms_refused() -> None:
    for hostile, _field in [
        ("see ~/secret file", "description"),
        ("load file:///tmp/file", "description"),
        (r"C:\Users\foo\bar.xml", "description"),
    ]:
        with pytest.raises(EventScenarioBridgeError):
            build_event_scenario_bridge_manifest(_request(description=hostile))
    # Also via mutation table_kind
    for hostile in ["~/secret", "file:///tmp/file", r"C:\Users\foo"]:
        proposal = ScenarioMutationProposal(
            mutation_kind=MutationKind.LANE_CLOSURE,
            target_description="ok target",
            lanes_closed=1,
            table_kind=hostile,
        )
        with pytest.raises(EventScenarioBridgeError):
            build_event_scenario_bridge_manifest(_request(mutation_proposals=[proposal]))


def test_csv_sanitizes_formula_like_text_cells() -> None:
    manifest = build_event_scenario_bridge_manifest(_request())
    # Create hostile finding via model copy
    hostile_desc = '=HYPERLINK("http://evil","click")'
    # Build a hostile manifest by copying and adding finding
    # Use the service's findings builder indirectly: create a copy with extra finding
    from traffictwin.event_scenario_bridge.models import BridgeFinding

    hostile_finding = BridgeFinding(
        finding_id="finding-hostile",
        description=hostile_desc,
        severity="info",
    )
    # Create a new manifest with hostile finding via model_copy
    hostile_manifest = manifest.model_copy(
        update={"findings": [*manifest.findings, hostile_finding]}
    )
    csv_text = export_bridge_csv(hostile_manifest)
    # Raw formula must not appear as cell start, sanitized with leading '
    assert hostile_desc not in csv_text
    assert "'=HYPERLINK" in csv_text
    # Also test other prefixes
    for prefix, fid in [("+cmd", "find-plus"), ("-evil", "find-minus"), ("@evil", "find-at")]:
        f = BridgeFinding(finding_id=fid, description=prefix + " payload", severity="info")
        m2 = manifest.model_copy(update={"findings": [*manifest.findings, f]})
        csv2 = export_bridge_csv(m2)
        assert f"'{prefix}" in csv2
    # Safe ordinary text unchanged
    safe_f = BridgeFinding(
        finding_id="safe-001", description="Normal finding text", severity="info"
    )
    m3 = manifest.model_copy(update={"findings": [*manifest.findings, safe_f]})
    csv3 = export_bridge_csv(m3)
    assert "Normal finding text" in csv3
    assert "'Normal finding text" not in csv3


def test_title_must_not_claim_causality() -> None:
    with pytest.raises(ValidationError, match="must not claim causality"):
        _request(title="Causal analysis of authored closure event")
    with pytest.raises(ValidationError, match="must not claim causality"):
        _request(title="This caused the outage")
    with pytest.raises(ValidationError, match="must not claim causality"):
        _request(title="Study proves the effect")
    # Non-causal title should pass
    req = _request(title="What-if study for authored closure — unexecuted design")
    manifest = build_event_scenario_bridge_manifest(req)
    assert manifest.request.title == "What-if study for authored closure — unexecuted design"


def test_unknown_metric_produces_advisory_warning_and_preserved() -> None:
    req = _request(intended_metrics=["task.completion.rate", "unknown.custom.metric"])
    manifest = build_event_scenario_bridge_manifest(req)
    # Advisory warning about bounded reference catalogue
    assert any(
        "bounded reference catalogue" in w.lower() or "not in the bounded" in w.lower()
        for w in manifest.warnings
    )
    assert "unknown.custom.metric" in manifest.request.intended_metrics
    # Manifest still OK
    assert manifest.verify_fingerprint()
    # Unknown metric preserved as authored label
    assert "unknown.custom.metric" in manifest.request.intended_metrics


def test_unknown_window_produces_advisory_warning_and_preserved() -> None:
    req = _request(intended_windows=["pre", "event", "custom_window"])
    manifest = build_event_scenario_bridge_manifest(req)
    assert any(
        "non-standard" in w.lower() or "authored scope" in w.lower() for w in manifest.warnings
    )
    assert "custom_window" in manifest.request.intended_windows
    assert manifest.verify_fingerprint()


def test_half_open_windows_exact_boundaries() -> None:
    env = EventImpactEnvelope(
        affected_links=[],
        pre_duration_s=600,
        event_duration_s=600,
        post_duration_s=600,
        bin_width_s=60,
    )
    anchor = _utc()
    windows = env.preview_windows(anchor)
    assert windows["pre"][1] == windows["event"][0]
    assert windows["event"][1] == windows["post"][0]
    # Durations exact
    assert (windows["pre"][1] - windows["pre"][0]).total_seconds() == 600
    assert (windows["event"][1] - windows["event"][0]).total_seconds() == 600
    assert (windows["post"][1] - windows["post"][0]).total_seconds() == 600

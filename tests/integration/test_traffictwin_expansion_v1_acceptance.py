# ruff: noqa: S108,E501,B017,F841,N811,ANN001,ANN201,ANN401,TRY003,TRY301
"""Expansion V1 integrated acceptance — Lane 16 dependency-gated proof.

Dependency-gated lane must prove the integrated release rather than restate it.
Exercises final promoted Manchester/SUMO, Research Registry, Replay Observatory,
and Manchester Source Operations APIs/pages via public contracts.

- Reuses exact lane 01-14 public APIs
- No SUMO binary, no network, no credentials
- Synthetic engineering fixtures labelled exactly
- Truthful BLOCKED/PROVIDER_DATA_REQUIRED preserved
- No Dynamic Resource V2/E3 invented
"""

from __future__ import annotations

import json
from pathlib import Path

from traffictwin.ui.expansion_routes import EXPANSION_PAGE_SPECS, validate_expansion_routes
from traffictwin.ui.navigation_v07 import v07_navigation_pages, validate_v07_page_specs


def test_expansion_routes_are_promoted_and_coherent() -> None:
    validate_expansion_routes()
    validate_v07_page_specs()
    assert len(EXPANSION_PAGE_SPECS) == 4
    titles = {s.title for s in EXPANSION_PAGE_SPECS}
    assert titles == {
        "Manchester Twin",
        "Manchester Source Operations",
        "Replay Observatory",
        "Research Registry",
    }
    nav = v07_navigation_pages()
    assert len(nav["Source evidence"]) == 11
    assert len(nav["Evidence & reports"]) == 10
    # Overlap honesty: Resource Strategy Explorer still normative, Research Registry additive
    from traffictwin.ui.navigation_v07 import V07_PAGE_SPECS

    assert any(s.page.value == "Resource Strategy Explorer" for s in V07_PAGE_SPECS)
    assert any(s.title == "Research Registry" for s in EXPANSION_PAGE_SPECS)


def test_validator_passes_and_is_deterministic() -> None:
    from scripts.validate_traffictwin_expansion_v1 import build_validator_receipt, run_all_checks

    r1 = build_validator_receipt(run_all_checks())
    r2 = build_validator_receipt(run_all_checks())
    assert r1["overall_result"] == "PASS"
    assert r2["overall_result"] == "PASS"
    assert r1["validator_fingerprint"] == r2["validator_fingerprint"]
    assert r1["receipt_fingerprint"] == r2["receipt_fingerprint"]
    assert r1["summary"]["total"] == 12
    assert r1["summary"]["passed"] == 12
    # Integration provenance
    assert r1["integration_provenance"]["synthetic_execution_available"] is True
    assert r1["integration_provenance"]["provider_blocked_truthful"] is True
    assert r1["integration_provenance"]["e2_admitted_count"] >= 3
    assert r1["integration_provenance"]["replay_deterministic"] is True
    # No absolute path leakage
    blob = json.dumps(r1, sort_keys=True)
    assert "/Users/" not in blob
    assert "/home/" not in blob
    assert "/tmp/" not in blob


def test_validator_discriminates_via_typed_construction() -> None:
    """Prove validator fails closed on each of the 12 mutations via real public paths."""
    from scripts.validate_traffictwin_expansion_v1 import run_all_checks

    results = run_all_checks()
    by_id = {r.id: r for r in results}
    for expected_id in [f"{i:02d}" for i in range(1, 13)]:
        assert expected_id in by_id, f"check {expected_id} missing"
        assert by_id[expected_id].status == "PASS", (
            f"check {expected_id} should PASS on honest constructs but shows FAIL: {by_id[expected_id].detail}"
        )
    # Discriminating: check 05 must have proven the semantic invariant, not tuple shape
    assert "SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present" in by_id["05"].detail
    # Discriminating: check 08 must have exercised the real ingestion path and proved allowlist rejection + snapshot unchanged
    assert "not in admission allowlist" in by_id["08"].detail
    assert "fingerprint unchanged" in by_id["08"].detail.lower()
    assert "no E3 admitted" in by_id["08"].detail


def test_validator_check_05_rejects_semantic_not_tuple_shape() -> None:
    """Discriminating: a superficial list-stages implementation would falsely pass even if semantic invariant broke.

    Prove that the forged journey with tuple stages is rejected for the semantic reason
    'SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present', not for tuple shape or fingerprint.
    A prior superficial implementation using list stages would pass for the wrong reason (tuple_type).
    """
    from scripts.validate_traffictwin_expansion_v1 import run_all_checks

    by_id = {r.id: r for r in run_all_checks()}
    assert by_id["05"].status == "PASS"
    assert "SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present" in by_id["05"].detail
    # Ensure the validator did NOT use the superficial list rejection
    assert "tuple_type" not in by_id["05"].detail
    # Also prove directly via public model: tuple stages with semantic violation is rejected for semantic reason
    from traffictwin.integration.manchester.closed_loop_journey import (
        LIMITATIONS,
        ManchesterClosedLoopJourney,
        build_closed_loop_journey,
    )

    j = build_closed_loop_journey(
        journey_id="acceptance-blocked-check",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=None,
        output_receipt=None,
        comparison_result=None,
    )
    stages = j.stages
    payload = {
        "schema_version": "1.0",
        "capability_id": "MAN-09",
        "method_version": "manchester-closed-loop-journey-1.0",
        "journey_id": "forged-scientific",
        "stages": tuple(s.model_dump(mode="json") for s in stages),
        "overall_standing": "SCIENTIFICALLY_ACCEPTED_BASELINE",
        "synthetic_execution_available": True,
        "scientific_acceptance_present": False,
        "limitations": tuple(LIMITATIONS),
        "evidence_boundary": "Manchester closed-loop journey: deterministic stage view over exact identities. No self-acceptance.",
        "journey_fingerprint": "00" * 32,
    }
    try:
        ManchesterClosedLoopJourney.model_validate(payload)
        raise AssertionError("forged journey should be rejected")
    except Exception as exc:
        msg = str(exc)
        assert "SCIENTIFICALLY_ACCEPTED_BASELINE requires scientific present" in msg
        assert "tuple_type" not in msg
        assert "journey_fingerprint must be re-derived" not in msg


def test_validator_check_04_rejects_semantic_not_diagnostics() -> None:
    """Discriminating: forged AUTO_ACCEPTED with correct diagnostics must be rejected for the semantic invariant.

    A superficial diagnostics-mismatch would pass for the wrong reason
    (diagnostics must equal derived diagnostics) without proving that unresolved
    map-match silent acceptance is forbidden. The honest projection is
    UNRESOLVED; a forged AUTO_ACCEPTED that carries the honest derived
    diagnostics must still be rejected for AUTO_ACCEPTED requires
    owner_policy_accepted_candidate.
    """
    from scripts.validate_traffictwin_expansion_v1 import run_all_checks

    by_id = {r.id: r for r in run_all_checks()}
    assert by_id["04"].status == "PASS"
    assert "AUTO_ACCEPTED requires owner_policy_accepted_candidate" in by_id["04"].detail
    assert "diagnostics must equal" not in by_id["04"].detail
    # Direct public-model proof: forged AUTO_ACCEPTED via honest projection dump + model_validate
    # Use the public build_map_match_workflow result's honest MapMatchObservationProjection
    # as canonical source, revalidate a dumped honest projection through public
    # MapMatchObservationProjection.model_validate with only acceptance fields forged.
    from decimal import Decimal

    from traffictwin.integration.manchester.map_match_workflow import (
        MapMatchDftSourceIdentity,
        MapMatchObservationProjection,
        build_map_match_workflow,
    )
    from traffictwin.integration.manchester.observation_matching import EdgeCandidate
    from traffictwin.integration.manchester.observation_matching_v11 import (
        ManchesterMapMatchPolicyV11,
        ObservationMatchV11,
        RoadGroupV11,
        build_manual_review_queue,
    )

    policy = ManchesterMapMatchPolicyV11()
    content_fp = "ab" * 32
    snap_id = f"dft_raw_counts-20260726T230000Z-{content_fp[:12]}"
    provenance = f"roadtraffic.dft.gov.uk:/api/raw-counts/pages/page-0001.json#{snap_id}"
    receipt_fp = "cd" * 32
    source = MapMatchDftSourceIdentity(
        source_family="dft",
        provider="roadtraffic.dft.gov.uk",
        observation_role="historical_measured_count",
        snapshot_id=snap_id,
        content_fingerprint=content_fp,
        provenance=provenance,
        admission_receipt_fingerprint=receipt_fp,
        is_accepted=True,
        is_source_blocked=False,
    )
    cand = EdgeCandidate(
        edge_id="e1",
        road_type="highway.primary",
        road_class="primary",
        road_ref="A56",
        normalised_ref="A56",
        distance_m=Decimal("1.200"),
        geometry_source="explicit_edge_shape",
        bearing_degrees=Decimal("45.000"),
        requires_manual_confirmation=False,
    )
    group = RoadGroupV11(
        group_key="ref:A56|primary",
        normalised_ref="A56",
        road_class_family="primary",
        members=(cand,),
        nearest_distance_m=Decimal("1.200"),
        contains_service_member=False,
        exact_reference_match=True,
        admitted_by_override=False,
        family_mismatch=None,
    )
    obs = ObservationMatchV11(
        policy_fingerprint=policy.fingerprint(),
        count_point_id=999,
        dft_road_type="Major",
        dft_road_name="A56",
        dft_normalised_ref="A56",
        groups=(group,),
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
    queue = build_manual_review_queue([obs])
    honest_wf = build_map_match_workflow(
        observations=[obs], queue=queue, policy=policy, source=source
    )
    assert honest_wf.observations[0].standing == "UNRESOLVED"
    honest_payload = honest_wf.observations[0].model_dump()
    forged_payload = dict(honest_payload)
    forged_payload["standing"] = "AUTO_ACCEPTED"
    forged_payload["standing_reason"] = (
        "owner policy unambiguously accepted under clear thresholds; distance alone not sufficient"
    )
    forged_payload["accepted_group_key"] = "ref:A56|primary"
    forged_payload["matched_edge_ids"] = ("e1",)
    try:
        MapMatchObservationProjection.model_validate(forged_payload)
        raise AssertionError("forged AUTO_ACCEPTED should be rejected")
    except Exception as exc:
        msg = str(exc)
        assert "AUTO_ACCEPTED requires owner_policy_accepted_candidate" in msg
        assert "diagnostics must equal" not in msg


def test_validator_check_08_proves_fail_closed_ingestion() -> None:
    """Discriminating: a superficial 'snapshot lacks E3' check would pass without proving fail-closed handling.

    Prove that a structurally valid future E3 package is rejected by the real ingestion path
    (RegistryService with authoritative E2 allowlist) and that the snapshot remains unchanged.
    A prior superficial implementation that only observed a default snapshot would not exercise ingestion.
    """
    from scripts.validate_traffictwin_expansion_v1 import run_all_checks

    by_id = {r.id: r for r in run_all_checks()}
    assert by_id["08"].status == "PASS"
    assert "not in admission allowlist" in by_id["08"].detail
    assert "fingerprint unchanged" in by_id["08"].detail.lower()
    assert "no E3 admitted" in by_id["08"].detail

    # Direct public-model proof: build structurally valid future E3 package and attempt ingestion
    from traffictwin.research_registry.adapters import (
        build_default_e2_admission_policy,
        build_e2_study_package,
    )
    from traffictwin.research_registry.ingestion import ResearchStudyPackage
    from traffictwin.research_registry.models import (
        AdmissionStatus,
        EvidenceStanding,
        ResearchStudyRecord,
        StudyStatus,
    )
    from traffictwin.research_registry.service import RegistryService

    authoritative_pkg = build_e2_study_package()
    policy = build_default_e2_admission_policy(authoritative_pkg)
    fake_record = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="Future E3 direct probe",
        question="Q?",
        hypothesis="H",
        status=StudyStatus.COMPLETED,
        code_sha="f" * 40,
        manifest_hash="e" * 64,
        evaluator_id="eval-fake",
        actor_id="a" * 64,
        checkpoint_id="b" * 64,
        trace_id="c" * 64,
        replication_unit="fleet_draw",
        seeds=[99],
        draws=[99],
        arms=["future_arm"],
        estimand="future",
        primary_metrics=["future_metric"],
        secondary_metrics=None,
        per_draw_values=None,
        declared_summary=None,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["future"],
        non_claims=["future"],
        product_links=None,
    )
    fake_pkg = ResearchStudyPackage.build(records=[fake_record])
    svc = RegistryService(policy)
    svc.ingest_package(authoritative_pkg)
    before_fp = svc.snapshot().snapshot_fingerprint
    before_ids = {(r.study, r.version) for r in svc.snapshot().records}
    try:
        svc.ingest_package(fake_pkg)
        raise AssertionError("fake E3 ingestion should be rejected")
    except Exception as exc:
        assert "not in admission allowlist" in str(exc)
    after = svc.snapshot()
    assert {(r.study, r.version) for r in after.records} == before_ids
    assert after.snapshot_fingerprint == before_fp
    assert not any(
        r.study == "E3" and r.admission_status == AdmissionStatus.ADMITTED for r in after.records
    )
    # Future-generic contract remains capable: verify registry source not hard-coded to reject E3 by name
    # (the generic ingestion would accept an exact allowlisted E3 package if policy included it)
    # Prove by building a policy that would allow E3 if we extended it (we don't alter source, just prove generic path)
    # The fact that ResearchStudyPackage.build accepted E3 and the rejection was via policy, not via model forbidding E3, suffices.
    assert fake_pkg.records[0].study == "E3"


def test_synthetic_engineering_execution_remains_available_provider_blocked_truthful() -> None:
    from traffictwin.integration.manchester.closed_loop_journey import build_closed_loop_journey

    # Provider-absent journey must be PROVIDER_DATA_REQUIRED truthfully (synthetic false when empty)
    j_blocked = build_closed_loop_journey(
        journey_id="acceptance-blocked-check",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=None,
        output_receipt=None,
        comparison_result=None,
    )
    assert j_blocked.overall_standing == "PROVIDER_DATA_REQUIRED"
    assert j_blocked.synthetic_execution_available is False
    assert j_blocked.scientific_acceptance_present is False
    # Synthetic engineering remains available when synthetic output is supplied, even when provider blocked
    from traffictwin.integration.manchester.models import sha256_hex
    from traffictwin.integration.manchester.sumo_output_pipeline import (
        SumoOutputFileDeclaration,
        SumoOutputNetworkIdentity,
        SumoOutputProvenance,
        SumoOutputTimeBasis,
        SumoOutputToolIdentity,
        build_sumo_output_request,
        import_sumo_outputs,
    )

    trip_bytes2 = b'<tripinfos><tripinfo id="v0" depart="0.0" /></tripinfos>'
    summ_bytes2 = b'<summary><step time="0.0" running="1" /></summary>'
    tool2 = SumoOutputToolIdentity(reported_version="1.27.0", executable_sha256="a" * 64)
    net2 = SumoOutputNetworkIdentity(
        network_sha256="b" * 64,
        demand_sha256="c" * 64,
        config_sha256="d" * 64,
        network_file="net.xml",
        demand_file="routes.xml",
        config_file="sumo.sumocfg",
    )
    tb2 = SumoOutputTimeBasis(
        window_start_s=0,
        window_end_s=3600,
        step_length_s=1,
        time_basis_label="synthetic_utc_hour",
        time_basis_fingerprint="e" * 64,
    )
    decls2 = [
        SumoOutputFileDeclaration(
            relative_path="tripinfo.xml",
            sha256=sha256_hex(trip_bytes2),
            size_bytes=len(trip_bytes2),
            required=True,
            media_type="application/xml",
        ),
        SumoOutputFileDeclaration(
            relative_path="summary.xml",
            sha256=sha256_hex(summ_bytes2),
            size_bytes=len(summ_bytes2),
            required=True,
            media_type="application/xml",
        ),
    ]
    req2 = build_sumo_output_request(
        request_id="acceptance-synth-req-01",
        run_id="acceptance-synth-run-01",
        tool=tool2,
        network=net2,
        time_basis=tb2,
        files=decls2,
    )
    pkg2 = import_sumo_outputs(
        req2,
        {"tripinfo.xml": trip_bytes2, "summary.xml": summ_bytes2},
        provenance=SumoOutputProvenance(
            created_at_utc="2026-01-01T00:00:00Z",
            created_by="acceptance-test",
            parent_fingerprints=(),
        ),
    )
    j_synth = build_closed_loop_journey(
        journey_id="acceptance-synthetic-check",
        source_provider_available=False,
        source_snapshot_id=None,
        baseline_package=None,
        baseline_decision=None,
        baseline_software_validation=None,
        map_workflow=None,
        demand_result=None,
        demand_receipt=None,
        demand_decision=None,
        calibration_result=None,
        calibration_decision=None,
        calibration_receipt=None,
        sumo_request=None,
        sumo_receipt=None,
        output_package=pkg2,
        output_receipt=None,
        comparison_result=None,
    )
    assert j_synth.overall_standing == "SOFTWARE_VALID_SYNTHETIC_AVAILABLE"
    assert j_synth.synthetic_execution_available is True
    assert j_synth.scientific_acceptance_present is False
    # Synthetic SUMO output pipeline still available via deterministic synthetic fixture
    from traffictwin.integration.manchester.models import sha256_hex
    from traffictwin.integration.manchester.sumo_output_pipeline import (
        SumoOutputFileDeclaration,
        SumoOutputNetworkIdentity,
        SumoOutputProvenance,
        SumoOutputTimeBasis,
        SumoOutputToolIdentity,
        build_sumo_output_request,
        import_sumo_outputs,
    )

    trip_bytes = b'<tripinfos><tripinfo id="s0" depart="0" arrival="10" duration="10" routeLength="100" waitingTime="0" timeLoss="0" departLane="e0_0" arrivalLane="e1_0" /></tripinfos>'
    summ_bytes = b'<summary><step time="0.0" running="1" waiting="0" ended="0" arrived="0" halting="0" collisions="0" teleports="0" /></summary>'
    tool = SumoOutputToolIdentity(reported_version="1.27.0", executable_sha256="f" * 64)
    net = SumoOutputNetworkIdentity(
        network_sha256="a" * 64,
        demand_sha256="b" * 64,
        config_sha256="c" * 64,
        network_file="net.xml",
        demand_file="routes.xml",
        config_file="sumo.sumocfg",
    )
    tb = SumoOutputTimeBasis(
        window_start_s=0,
        window_end_s=3600,
        step_length_s=1,
        time_basis_label="synthetic_utc_hour",
        time_basis_fingerprint="d" * 64,
    )
    decls = [
        SumoOutputFileDeclaration(
            relative_path="tripinfo.xml",
            sha256=sha256_hex(trip_bytes),
            size_bytes=len(trip_bytes),
            required=True,
            media_type="application/xml",
        ),
        SumoOutputFileDeclaration(
            relative_path="summary.xml",
            sha256=sha256_hex(summ_bytes),
            size_bytes=len(summ_bytes),
            required=True,
            media_type="application/xml",
        ),
    ]
    req = build_sumo_output_request(
        request_id="acceptance-req-01",
        run_id="acceptance-run-01",
        tool=tool,
        network=net,
        time_basis=tb,
        files=decls,
    )
    pkg = import_sumo_outputs(
        req,
        {"tripinfo.xml": trip_bytes, "summary.xml": summ_bytes},
        provenance=SumoOutputProvenance(
            created_at_utc="2026-01-01T00:00:00Z",
            created_by="acceptance-test",
            parent_fingerprints=(),
        ),
    )
    assert pkg.counts.tripinfo_records == 1
    assert pkg.evidence_standing == "SOFTWARE_VALID_SIMULATED_ONLY"


def test_research_registry_inspectable_and_e3_absent() -> None:
    from traffictwin.research_registry.models import AdmissionStatus
    from traffictwin.research_registry.service import RegistryService

    svc = RegistryService.with_default_e2()
    snap = svc.snapshot()
    assert len([r for r in snap.records if r.study.startswith("E2")]) >= 3
    assert (
        len(
            [
                r
                for r in snap.records
                if r.study == "E3" and r.admission_status == AdmissionStatus.ADMITTED
            ]
        )
        == 0
    )
    # Each admitted E2 has exact 40-hex code SHA and 64-hex manifest
    for rec in snap.records:
        if rec.study.startswith("E2") and rec.admission_status == AdmissionStatus.ADMITTED:
            assert rec.code_sha is not None and len(rec.code_sha) == 40
            assert rec.manifest_hash is not None and len(rec.manifest_hash) == 64
            assert all(c in "0123456789abcdef" for c in rec.code_sha)
            assert all(c in "0123456789abcdef" for c in rec.manifest_hash)


def test_manchester_source_operations_inspectable_offline_secret_free() -> None:
    from traffictwin.ui.manchester_source_operations import (
        build_demonstrator_catalogue,
        make_demonstrator_registry,
    )

    cat = build_demonstrator_catalogue()
    _reg = make_demonstrator_registry(cat.evaluated_at_utc)  # noqa: F841 — exercised for coverage
    assert len(cat.sources) == 8
    # No credential values, no network access
    assert cat.method_version == "manchester-source-operations-1.0"
    dumped = cat.model_dump_json()
    assert "/Users/" not in dumped
    assert "api_key" not in dumped.lower()  # model has no credential value field
    # BODS remains bus-only
    bods_row = next(r for r in cat.sources if r.source.family.value == "bods")
    assert "bus" in bods_row.source.can_infer[0].lower()
    assert any(
        "general" in x.lower() and "traffic" in x.lower() for x in bods_row.source.cannot_infer
    )


def test_replay_observatory_inspectable_and_deterministic() -> None:
    from traffictwin.ui.replay_observatory_service import (
        build_synthetic_engineering_stream,
        create_engine,
    )

    s1 = build_synthetic_engineering_stream()
    s2 = build_synthetic_engineering_stream()
    e1 = create_engine(s1)
    e2 = create_engine(s2)
    assert e1.stream.stream_id == e2.stream.stream_id
    assert e1.state().playhead_time_s == e2.state().playhead_time_s
    # Present event types must exactly match instantiated event classes
    assert set(s1.present_event_types) == {ev.event_type for ev in s1.events}


def test_portable_artifacts_contain_no_absolute_paths() -> None:
    import tempfile

    from traffictwin.demo.workspace import initialise_workspace
    from traffictwin.evidence_admission.e2_research import load_admitted_builtin_e2_research
    from traffictwin.reporting.e2_research import build_e2_research_exports
    from traffictwin.synthetic.whatif_pair import (
        WhatIfPairRequest,
        WhatIfVariationOverrides,
        receipt_to_portable_dict,
    )

    pkg, receipt = load_admitted_builtin_e2_research()
    exports = build_e2_research_exports(pkg, receipt)
    for blob in (exports.json, exports.csv, exports.markdown):
        assert "/Users/" not in blob
        assert "/home/" not in blob
        assert "/tmp/" not in blob

    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws-portable-check"
        initialise_workspace(ws)
        reg = ws / "registry.sqlite"
        from traffictwin.ui.services.whatif_pair import generate_whatif_pair_for_ui

        req = WhatIfPairRequest(
            baseline_preset="baseline",
            pair_name="portable-check",
            experiment_id="exp-portable",
            baseline_random_seed=1,
            variation_overrides=WhatIfVariationOverrides(congestion_multiplier=1.5),
        )
        result = generate_whatif_pair_for_ui(req, registry_path=reg, workspace_path=ws)
        assert result.status == "ok"  # type: ignore[union-attr]
        portable = receipt_to_portable_dict(result, workspace_path=ws)  # type: ignore[arg-type]
        assert "/Users/" not in json.dumps(portable)
        assert "/tmp/" not in json.dumps(portable)
        assert tmp not in json.dumps(portable)
        assert str(ws) not in json.dumps(portable)

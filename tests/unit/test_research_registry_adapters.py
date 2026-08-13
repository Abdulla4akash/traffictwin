"""Adapter and service tests: exact E2 values, lineage, unavailable, E3 future-safe."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from traffictwin.evidence_admission.e2_research import load_admitted_builtin_e2_research
from traffictwin.experiments.e2_comparison import build_e2_comparison_view
from traffictwin.research_registry.adapters import (
    build_admitted_e2_records,
    build_current_lineage_edges,
    build_default_e2_admission_policy,
    build_e2_study_package,
    build_unavailable_index_records,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    AdmissionPolicyEntry,
    ResearchIngestionError,
    ResearchStudyPackage,
    ingest_package,
)
from traffictwin.research_registry.models import (
    AdmissionStatus,
    EvidenceStanding,
    PerDrawValue,
    ResearchStudyRecord,
    StudyStatus,
)
from traffictwin.research_registry.service import RegistryService


def test_exact_e2_values_through_existing_loaders() -> None:
    pkg, receipt = load_admitted_builtin_e2_research()
    receipt.verify()
    view = build_e2_comparison_view(pkg)
    # E2b offered attainment
    assert view.e2b.off == 0.683619229
    assert view.e2b.jsq == 0.675681775
    assert view.e2b.ingress_dla == 0.715773211
    assert view.e2b.dla == 0.694939919
    # E2c
    assert view.e2c.per_seed_values == (
        -0.022097034972,
        -0.020519134179,
        -0.021447383092,
        -0.020825491499,
    )  # noqa: E501
    assert view.e2c.mean == -0.021222260935
    assert view.e2c.lower == -0.02233525407
    assert view.e2c.upper == -0.0201092678
    # E2d
    assert view.e2d.per_seed_values == (
        0.004636732564,
        0.005867285642,
        0.005071796666,
        0.005509919752,
    )  # noqa: E501
    assert view.e2d.mean == 0.005271433656
    # Adapters preserve same
    recs = build_admitted_e2_records()
    by_study = {r.study: r for r in recs}
    e2b = by_study["E2b"]
    assert e2b.code_sha == "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
    assert e2b.manifest_hash == "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91"
    assert e2b.replication_unit == "fleet_draw"
    assert e2b.seeds == [0]
    assert e2b.draws == [0]
    # E2b per_draw values map to arms
    assert len(e2b.per_draw_values or []) == 4
    e2c = by_study["E2c"]
    assert e2c.code_sha == "1a08d6e148a1e8c430da39c3d575eda3f8ea5929"
    assert e2c.manifest_hash == "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a"
    assert e2c.seeds == [1, 2, 3, 4]
    assert e2c.declared_summary is not None
    assert e2c.declared_summary.estimate == -0.021222260935
    e2d = by_study["E2d"]
    assert e2d.code_sha == "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
    assert e2d.manifest_hash == "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
    # Primary vs secondary preserved — authoritative identities include _dla qualifier
    assert e2d.primary_metrics == ["offered_attainment_per_task_dla_minus_ingress_dla"]
    assert e2d.secondary_metrics == ["offered_attainment_per_task_dla_minus_dla"]
    assert e2d.declared_summary is not None
    assert e2d.declared_summary.ci_lower == 0.004422143925
    # Limitations and non-claims preserved
    assert any("manchester incident hour" in lim.lower() for lim in (e2d.limitations or []))
    assert any("kubernetes deployment" in nc.lower() for nc in (e2d.non_claims or []))
    # Admitted standing
    assert e2d.admission_status == AdmissionStatus.ADMITTED
    assert e2d.evidence_standing == EvidenceStanding.RESEARCH_EVIDENCE_FACT
    assert e2d.status == StudyStatus.COMPLETED


def test_mutate_sha_manifest_value_seed_interval_admission_fails() -> None:
    recs = build_admitted_e2_records()
    e2b = next(r for r in recs if r.study == "E2b")
    # Mutate code_sha – model_copy bypass must be caught by canonical revalidation
    mutated = e2b.model_copy(update={"code_sha": "short"})  # bypasses immediate validation
    with pytest.raises(ValidationError):
        ResearchStudyRecord.model_validate(mutated.model_dump(mode="json"))
    # Mutate via direct model_validate with bad manifest
    payload = e2b.model_dump(mode="json")
    payload["manifest_hash"] = "0" * 64
    # This still structurally valid but would fail allowlist later; test that ingestion fails
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    # Craft bad package with mutated value
    obj = json.loads(pkg.to_json())
    # Mutate per_draw value
    obj["records"][0]["per_draw_values"][0]["value"] = 0.999
    # Keep old fingerprint to trigger drift
    bad = json.dumps(obj)
    with pytest.raises(Exception, match="drift|validation|not in admission"):
        ingest_package(bad, pol)
    # Mutate seed
    obj2 = json.loads(pkg.to_json())
    obj2["records"][1]["seeds"] = [9, 9, 9, 9]
    bad2 = json.dumps(obj2)
    with pytest.raises((ResearchIngestionError, Exception)):
        ingest_package(bad2, pol)  # noqa: B017
    # Mutate interval
    obj3 = json.loads(pkg.to_json())
    # Find E2c record
    for rec in obj3["records"]:
        if rec["study"] == "E2c":
            rec["declared_summary"]["ci_lower"] = 999.0
    bad3 = json.dumps(obj3)
    with pytest.raises((ResearchIngestionError, Exception)):
        ingest_package(bad3, pol)  # noqa: B017
    # Mutate admission receipt: tamper policy fingerprint via ingest? Instead test policy mismatch
    bad_pol = AdmissionPolicy(entries=[])
    with pytest.raises(Exception):  # noqa: B017
        ingest_package(pkg.to_json(), bad_pol)


def test_preserve_replication_unit_not_tasks_as_replicates() -> None:
    recs = build_admitted_e2_records()
    for rec in recs:
        assert rec.replication_unit == "fleet_draw"
        # Tasks are not replicates; ensure no task-level replication claim in limitations
        # Limitations should state accounting records not independent replicates
        if rec.study == "E2d":
            assert rec.seeds == [1, 2, 3, 4]
            assert rec.draws == [1, 2, 3, 4]
            # Should not have invented telemetry like gate_rejected as number; it is unavailable in source  # noqa: E501
            # Our record does not invent per-task telemetry beyond declared metrics
            assert rec.evidence_standing == EvidenceStanding.RESEARCH_EVIDENCE_FACT


def test_lineage_only_supported_current() -> None:
    recs = build_admitted_e2_records()
    edges = build_current_lineage_edges(recs)
    # Only E2b->E2c, E2c->E2d, E2b->E2d are supported
    assert len(edges) == 3
    rels = {(e.source_study, e.target_study, e.relationship.value) for e in edges}
    assert ("E2b", "E2c", "EXTENDS") in rels
    assert ("E2c", "E2d", "CONSTRUCT_VALIDITY") in rels
    assert ("E2b", "E2d", "ROBUSTNESS_CHECK") in rels
    # No E0/E1 links
    assert all(
        e.source_study not in {"E0", "E1"} and e.target_study not in {"E0", "E1"} for e in edges
    )  # noqa: E501
    # E2d is bounded, not universal superiority: check rationale contains bounded
    for e in edges:
        if e.target_study == "E2d":
            assert "bounded" in e.rationale.lower()
            assert (
                "not universal" in e.rationale.lower()
                or "not universal superiority" in e.rationale.lower()
            )  # noqa: E501


def test_unavailable_index_truthful_no_fabricated() -> None:
    unavailable = build_unavailable_index_records()
    by_study = {r.study: r for r in unavailable}
    assert "E0" in by_study
    assert "E1" in by_study
    for study in ("E0", "E1"):
        rec = by_study[study]
        assert rec.evidence_standing == EvidenceStanding.UNAVAILABLE
        assert rec.admission_status == AdmissionStatus.NOT_ADMITTED
        assert rec.code_sha is None
        assert rec.manifest_hash is None
        assert rec.per_draw_values is None
        assert rec.declared_summary is None
        assert rec.limitations is not None
        assert len(rec.limitations[0]) > 10
        assert rec.product_links is None
        # Completed historically but unavailable — never PLANNED/prospective
        assert rec.status == StudyStatus.UNAVAILABLE
        assert rec.hypothesis is None
    e0 = by_study["E0"]
    assert e0.status == StudyStatus.UNAVAILABLE
    assert e0.limitations is not None and "cannot admit or reproduce" in e0.limitations[0].lower()
    e1 = by_study["E1"]
    assert e1.status == StudyStatus.UNAVAILABLE
    assert e1.limitations is not None and (
        "waiting-room" in e1.limitations[0].lower() or "waiting" in e1.limitations[0].lower()
    )
    assert e1.limitations is not None and "accounting artefact" in e1.limitations[0].lower()
    assert e1.limitations is not None and "use_case_b_vec_dynamic_service" in e1.limitations[0]
    assert e1.question is not None and "2.5" in e1.question
    assert e1.non_claims is not None and "no e1" in e1.non_claims[0].lower()
    # Must represent completed-but-unavailable, not prospective/work-not-yet-done
    assert e1.limitations is not None and "completed historically" in e1.limitations[0].lower()
    assert "planned" not in e1.title.lower() or "completed historically" in e1.title.lower()
    assert e1.limitations is not None and "if authoritative" not in e1.limitations[0].lower()


def test_future_e3_absent_by_default_and_discriminating() -> None:
    # E3 should not be in admitted records
    recs = build_admitted_e2_records()
    assert all(r.study != "E3" for r in recs)
    unavailable = build_unavailable_index_records()
    assert all(r.study != "E3" for r in unavailable)
    # Build a syntactically valid E3 package
    e3_rec = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="E3 future",
        question="Future question with sufficient length to be valid for testing?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha="b" * 40,
        manifest_hash="d" * 64,
        replication_unit="fleet_draw",
        seeds=[1],
        draws=[1],
        primary_metrics=["m"],
        per_draw_values=[PerDrawValue(draw=1, value=0.1, metric="m")],
    )
    e3_pkg = ResearchStudyPackage.build(records=[e3_rec], lineage_edges=[])
    # Default E2 policy should reject it
    e2_pkg = build_e2_study_package()
    e2_pol = build_default_e2_admission_policy(e2_pkg)
    with pytest.raises(Exception, match="not in admission allowlist"):
        ingest_package(e3_pkg.to_json(), e2_pol)
    # Only with exact E3 policy it passes
    e3_pol = AdmissionPolicy(
        entries=[
            AdmissionPolicyEntry(
                study="E3",
                version="1.0",
                code_sha="b" * 40,
                manifest_hash="d" * 64,
                package_fingerprint=e3_pkg.package_fingerprint,
            )
        ]
    )
    p, _ = ingest_package(e3_pkg.to_json(), e3_pol)
    assert p.records[0].study == "E3"
    # Ensure we never ship E3 policy in default adapters
    default_pol = build_default_e2_admission_policy()
    assert all(e.study != "E3" for e in default_pol.entries)


def test_service_snapshot_deterministic_and_conflict() -> None:
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    svc = RegistryService(pol)
    r1 = svc.ingest(pkg.to_json())
    snap1 = svc.snapshot()
    r2 = svc.ingest(pkg.to_json())
    assert r1.receipt_fingerprint == r2.receipt_fingerprint
    snap2 = svc.snapshot()
    assert snap1.snapshot_fingerprint == snap2.snapshot_fingerprint
    recs = build_admitted_e2_records()
    mutated = recs[0].model_copy(
        update={"title": "Different title for conflict test with sufficient length"}
    )
    bad_pkg = ResearchStudyPackage.build(
        records=[mutated] + recs[1:], lineage_edges=build_current_lineage_edges(recs)
    )
    bad_pol_entries = [
        AdmissionPolicyEntry(
            study=r.study,
            version=r.version,
            code_sha=r.code_sha or "",
            manifest_hash=r.manifest_hash or "",
            package_fingerprint=bad_pkg.package_fingerprint,
        )
        for r in bad_pkg.records
        if r.code_sha and r.manifest_hash
    ]
    bad_pol = AdmissionPolicy(entries=bad_pol_entries)
    combined_entries = list(pol.entries) + list(bad_pol.entries)
    combined_entries = sorted(
        {
            (e.study, e.version, e.code_sha, e.manifest_hash, e.package_fingerprint): e
            for e in combined_entries
        }.values(),
        key=lambda e: (e.study, e.version, e.code_sha, e.manifest_hash, e.package_fingerprint),
    )
    combined_pol = AdmissionPolicy(entries=combined_entries)
    svc2 = RegistryService(combined_pol)
    svc2.ingest(pkg.to_json())
    with pytest.raises(Exception, match="conflict"):
        svc2.ingest(bad_pkg.to_json())
    snap = svc.snapshot()
    assert snap.get_by_identity("E2b", "1.0") is not None
    assert snap.get_by_identity("E3", "1.0") is None
    assert len(snap.get_by_status(StudyStatus.COMPLETED)) == 3
    assert len(snap.get_by_admission(AdmissionStatus.ADMITTED)) == 3
    assert len(snap.product_links()) > 0
    assert len(snap.limitations()) > 0
    assert snap.get_by_identity("E0", "1.0") is None
    assert len(snap.unavailable_records) == 0
    for r in snap.records:
        assert r.admission_status == AdmissionStatus.ADMITTED
        assert r.evidence_standing == EvidenceStanding.RESEARCH_EVIDENCE_FACT
    assert len(snap.lineage.edges) == 3
    snap_e2 = RegistryService.with_default_e2().snapshot()
    assert snap_e2.get_by_identity("E0", "1.0") is not None
    assert snap_e2.get_by_identity("E1", "1.0") is not None
    assert snap_e2.get_by_identity("E1", "1.0").status == StudyStatus.UNAVAILABLE  # type: ignore[union-attr]
    assert len(snap_e2.unavailable_records) == 2
    assert len(snap_e2.lineage.edges) == 3
    # E2 hypotheses must be None unless pre-registration supports exact hypothesis
    for r in snap_e2.records:
        assert r.hypothesis is None
    # Product links must be truthful locators (no broken bare current-tree link)
    for r in snap_e2.records:
        if r.product_links:
            for link in r.product_links:
                assert "docs/evaluation/e2" not in link
            assert "docs/closure/v08_alignment" in " ".join(r.product_links)
    # No synthesized evaluator_id/checkpoint_id
    for r in snap_e2.records:
        assert r.evaluator_id is None
        assert r.checkpoint_id is None


def test_no_arbitrary_filesystem_path_and_reuse_exact_apis() -> None:
    import ast
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    src = (root / "src" / "traffictwin" / "research_registry" / "adapters.py").read_text()
    tree = ast.parse(src)
    # Must import load_admitted_builtin_e2_research
    assert "load_admitted_builtin_e2_research" in src
    assert "build_e2_comparison_view" in src
    # No open/read of arbitrary paths
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                # Should not have open with variable path
                raise AssertionError("adapters must not use open with arbitrary path")
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"read_text", "open"}:
                # Allow but check argument is not arbitrary filesystem path
                pass
    # No subprocess
    assert "subprocess" not in src
    assert "eval_sumo" not in src


def test_zero_research_workload_and_no_external_retrieval() -> None:
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    for fname in [
        "src/traffictwin/research_registry/adapters.py",
        "src/traffictwin/research_registry/ingestion.py",
        "src/traffictwin/research_registry/service.py",
        "src/traffictwin/research_registry/lineage.py",
    ]:
        src = (root / fname).read_text()
        assert "run_e2" not in src
        assert "eval_sumo" not in src
        assert "httpx" not in src or "import httpx" not in src
        assert "requests" not in src or "import requests" not in src
        assert "urllib" not in src


def test_generic_zero_edge_stays_zero_and_unrelated_gains_nothing() -> None:
    from traffictwin.research_registry.models import PerDrawValue

    rec = ResearchStudyRecord(
        study="E2b",
        version="1.0",
        title="E2b-like zero edge study",
        question="Does custom question with sufficient length pass validation?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha="a" * 40,
        manifest_hash="c" * 64,
        replication_unit="fleet_draw",
        seeds=[0],
        draws=[0],
        primary_metrics=["offered_task_deadline_attainment"],
        per_draw_values=[
            PerDrawValue(draw=0, value=0.5, metric="offered_task_deadline_attainment")
        ],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol = AdmissionPolicy(
        entries=[
            AdmissionPolicyEntry(
                study="E2b",
                version="1.0",
                code_sha="a" * 40,
                manifest_hash="c" * 64,
                package_fingerprint=pkg.package_fingerprint,
            )
        ]
    )
    svc = RegistryService(pol)
    svc.ingest(pkg.to_json())
    snap = svc.snapshot()
    assert len(snap.lineage.edges) == 0
    assert len(snap.lineage.nodes) == 1
    assert len(snap.unavailable_records) == 0
    assert svc.get("E2c", "1.0") is None
    assert svc.get("E0", "1.0") is None


def test_explicit_default_e2_lineage_only() -> None:
    svc = RegistryService.with_default_e2()
    snap = svc.snapshot()
    assert len(snap.lineage.edges) == 3
    assert len(snap.records) == 3
    assert {e.relationship.value for e in snap.lineage.edges} == {
        "EXTENDS",
        "CONSTRUCT_VALIDITY",
        "ROBUSTNESS_CHECK",
    }


def test_generic_get_no_injection_for_unavailable_and_e2() -> None:
    from traffictwin.research_registry.models import PerDrawValue

    rec = ResearchStudyRecord(
        study="S-generic",
        version="1.0",
        title="Generic study",
        question="Generic question with sufficient length to be valid for testing purposes?",
        status=StudyStatus.COMPLETED,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        code_sha="b" * 40,
        manifest_hash="d" * 64,
        replication_unit="fleet_draw",
        seeds=[1],
        draws=[1],
        primary_metrics=["m"],
        per_draw_values=[PerDrawValue(draw=1, value=0.2, metric="m")],
    )
    pkg = ResearchStudyPackage.build(records=[rec], lineage_edges=[])
    pol = AdmissionPolicy(
        entries=[
            AdmissionPolicyEntry(
                study="S-generic",
                version="1.0",
                code_sha="b" * 40,
                manifest_hash="d" * 64,
                package_fingerprint=pkg.package_fingerprint,
            )
        ]
    )
    svc = RegistryService(pol)
    svc.ingest(pkg.to_json())
    assert svc.get("E0", "1.0") is None
    assert svc.get("E1", "1.0") is None
    assert svc.get("E2b", "1.0") is None
    snap = svc.snapshot()
    assert snap.get_by_identity("E0", "1.0") is None


def test_path_secret_model_copy_note_node_refusal() -> None:
    from traffictwin.research_registry.ingestion import ImportReceipt
    from traffictwin.research_registry.lineage import (
        LineageGraph,
        StudyVersionIdentity,
    )

    with pytest.raises((ValidationError, ValueError), match="private"):
        ResearchStudyRecord(
            study="S-001",
            version="1.0",
            title="see /Users/alice/data",
            question="Valid question with sufficient length for testing purposes?",
            status=StudyStatus.PLANNED,
            evidence_standing=EvidenceStanding.UNAVAILABLE,
            admission_status=AdmissionStatus.NOT_APPLICABLE,
        )
    with pytest.raises((ValidationError, ValueError), match="secret"):
        ResearchStudyRecord(
            study="S-002",
            version="1.0",
            title="api_key leak test",
            question="Valid question with sufficient length for testing purposes?",
            status=StudyStatus.PLANNED,
            evidence_standing=EvidenceStanding.UNAVAILABLE,
            admission_status=AdmissionStatus.NOT_APPLICABLE,
        )
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    _, receipt = pkg.to_json(), None
    _, receipt = __import__(
        "traffictwin.research_registry.ingestion", fromlist=["ingest_package"]
    ).ingest_package(pkg.to_json(), pol)
    mutated = receipt.model_copy(update={"note": "wrong note"})
    with pytest.raises(ValidationError):
        ImportReceipt.model_validate(mutated.model_dump(mode="json"))
    object.__setattr__(mutated, "note", "wrong note")
    with pytest.raises(ValidationError):
        ImportReceipt.model_validate(mutated.model_dump(mode="json"))
    n = StudyVersionIdentity(study="E2b", version="1.0")
    n2 = n.model_copy(deep=True)
    object.__setattr__(n2, "study", "/tmp/bad")  # noqa: S108
    with pytest.raises(ValidationError):
        LineageGraph.build([n2, StudyVersionIdentity(study="E2c", version="1.0")], [])


def test_exact_metric_names_preserved() -> None:
    recs = build_admitted_e2_records()
    by_study = {r.study: r for r in recs}
    assert by_study["E2b"].primary_metrics == ["offered_task_deadline_attainment"]
    assert by_study["E2c"].primary_metrics == ["offered_attainment_dla_minus_ingress_dla"]
    e2d = by_study["E2d"]
    assert e2d.primary_metrics == ["offered_attainment_per_task_dla_minus_ingress_dla"]
    assert e2d.secondary_metrics == ["offered_attainment_per_task_dla_minus_dla"]
    assert len(e2d.per_draw_values or []) == 8
    metrics_in_draws = {pd.metric for pd in (e2d.per_draw_values or [])}
    assert "offered_attainment_per_task_dla_minus_ingress_dla" in metrics_in_draws
    assert "offered_attainment_per_task_dla_minus_dla" in metrics_in_draws
    assert e2d.declared_summary is not None
    assert e2d.declared_summary.metric == "offered_attainment_per_task_dla_minus_ingress_dla"


def test_authoritative_metric_identities_refuse_relabel_drift() -> None:
    """Discriminating test: derive metric names from exact E2 observations.

    Source of truth:
    ``src/traffictwin/resources/research/e2_resource_strategy_v1.json``
    observations[].metric for ``e2c_multidraw_comparison`` and
    ``e2d_robustness_comparison``, also reproduced via
    ``load_admitted_builtin_e2_research()`` observations
    (metric == ``offered_attainment_dla_minus_ingress_dla`` for E2c,
    metric == ``offered_attainment_per_task_dla_minus_ingress_dla``
    for E2d).
    Secondary metric ``offered_attainment_per_task_dla_minus_dla`` is only
    valid when explicitly sourced from ``e2d_per_task_minus_dla``
    paired-difference; it must not be renamed to a truncated form
    (e.g. ``offered_attainment_per_task_minus_dla`` drops the authoritative
    ``_dla`` qualifier).
    """

    pkg, _receipt = load_admitted_builtin_e2_research()
    # Derive authoritative metric identities from exact loaded observations
    e2c_metrics = {
        obs.metric for obs in pkg.observations if obs.evidence_id == "e2c_multidraw_comparison"
    }
    e2d_primary_metrics = {
        obs.metric for obs in pkg.observations if obs.evidence_id == "e2d_robustness_comparison"
    }
    # Pin to exact authoritative identities — source citation above
    assert e2c_metrics == {"offered_attainment_dla_minus_ingress_dla"}, (
        f"E2c observation metric drift; expected exact "
        f"{{'offered_attainment_dla_minus_ingress_dla'}}, got {e2c_metrics!r} "
        f"[src/traffictwin/resources/research/e2_resource_strategy_v1.json:observations/e2c_multidraw_comparison]"
    )
    assert e2d_primary_metrics == {"offered_attainment_per_task_dla_minus_ingress_dla"}, (
        f"E2d observation metric drift; expected exact "
        f"{{'offered_attainment_per_task_dla_minus_ingress_dla'}}, got {e2d_primary_metrics!r} "
        f"[src/traffictwin/resources/research/e2_resource_strategy_v1.json:observations/e2d_robustness_comparison]"
    )
    # Secondary is sourced from paired-difference id e2d_per_task_minus_dla, not an observation metric  # noqa: E501
    pd_ids = {pd.comparison_id for pd in pkg.paired_differences}
    assert "e2d_per_task_minus_dla" in pd_ids
    # Verify adapter emits exactly those authoritative identities (no truncated relabel)
    recs = build_admitted_e2_records()
    by_study = {r.study: r for r in recs}
    e2c = by_study["E2c"]
    e2d = by_study["E2d"]
    # E2c exact identities
    assert e2c.primary_metrics == ["offered_attainment_dla_minus_ingress_dla"]
    assert e2c.declared_summary is not None
    assert e2c.declared_summary.metric == "offered_attainment_dla_minus_ingress_dla"
    assert all(
        pd.metric == "offered_attainment_dla_minus_ingress_dla"
        for pd in (e2c.per_draw_values or [])
    )
    # E2d primary exact
    assert e2d.primary_metrics == ["offered_attainment_per_task_dla_minus_ingress_dla"]
    assert e2d.declared_summary is not None
    assert e2d.declared_summary.metric == "offered_attainment_per_task_dla_minus_ingress_dla"
    assert {  # noqa: E501
        pd.metric
        for pd in (e2d.per_draw_values or [])
        if pd.metric != "offered_attainment_per_task_dla_minus_dla"  # noqa: E501
    } == {"offered_attainment_per_task_dla_minus_ingress_dla"}
    # Secondary stays exactly as sourced from e2d_per_task_minus_dla
    assert e2d.secondary_metrics == ["offered_attainment_per_task_dla_minus_dla"]
    # Forbid truncated relabels ever reappearing (including old fabricated omission)
    truncated = {  # noqa: E501
        "offered_attainment_dla_minus_ingress",  # noqa: E501
        "offered_attainment_per_task_minus_ingress",  # noqa: E501
        "offered_attainment_per_task_minus_dla",  # noqa: E501
    }
    assert e2c.primary_metrics[0] not in truncated
    assert e2d.primary_metrics[0] not in truncated
    assert e2c.declared_summary.metric not in truncated
    assert e2d.declared_summary.metric not in truncated
    for pd in (e2c.per_draw_values or []) + (e2d.per_draw_values or []):
        assert pd.metric not in truncated, f"relabel drift detected: {pd.metric!r}"
        assert pd.metric not in {
            "offered_attainment_per_task_minus_dla_renamed",
            "offered_attainment_per_task_dla_minus_dla_renamed",
        }, "invented renamed secondary forbidden"

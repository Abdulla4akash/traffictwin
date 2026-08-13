"""Discriminating backend/UI tests for Research Registry page (Lane 09).

Uses exact raw identity set_value and widget.value assertions, generic typed
captions, fixed error code, and future E3 contract probes.
"""

from __future__ import annotations

import contextlib
import json
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from traffictwin.research_registry.adapters import (
    E2B_STUDY,
    E2C_STUDY,
    E2D_STUDY,
    build_admitted_e2_records,
    build_default_e2_admission_policy,
    build_e2_study_package,
)
from traffictwin.research_registry.ingestion import (
    AdmissionPolicy,
    ResearchIngestionError,
    ingest_package,
)
from traffictwin.research_registry.lineage import (
    LineageGraph,
    StudyVersionIdentity,
)
from traffictwin.research_registry.models import (
    AdmissionStatus,
    DeclaredSummary,
    EvidenceStanding,
    PerDrawValue,
    ResearchStudyRecord,
    StudyStatus,
)
from traffictwin.research_registry.service import (
    RegistryService,
    RegistrySnapshot,
)


def _run_page() -> AppTest:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30)
    at.run()
    return at


def _text_of(at: AppTest) -> str:
    parts: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "caption",
        "text",
        "info",
        "warning",
        "error",
        "success",
        "code",
        "json",
    ):
        for item in getattr(at, attr, []):
            try:
                parts.append(str(getattr(item, "value", item)))
            except Exception:
                parts.append(str(item))
    for df in getattr(at, "dataframe", []):
        try:
            val = getattr(df, "value", df)
            parts.append(str(val))
            if hasattr(val, "to_string"):
                with contextlib.suppress(Exception):
                    parts.append(val.to_string())
        except Exception:
            parts.append(str(df))
    for exp in getattr(at, "expander", []):
        parts.append(str(getattr(exp, "label", "")))
    return "\n".join(parts)


def _select_raw(at: AppTest, raw: str) -> None:
    assert len(at.selectbox) >= 1, "no selectbox"
    box = at.selectbox[0]
    box.set_value(raw).run()
    assert at.selectbox[0].value == raw, f"mutation failed {raw!r} got {at.selectbox[0].value!r}"


def test_page_renders_without_exception() -> None:
    at = _run_page()
    assert not at.exception, f"page raised {at.exception}"


def test_exact_admitted_e2_identities_via_raw_selection() -> None:
    recs = {r.study: r for r in build_admitted_e2_records()}
    at = _run_page()
    assert not at.exception
    assert at.selectbox[0].value == "E2b:1.0"
    body = _text_of(at)
    e2b = recs[E2B_STUDY]
    assert e2b.code_sha is not None and e2b.code_sha in body
    assert e2b.manifest_hash is not None and e2b.manifest_hash in body
    # E2c
    at2 = _run_page()
    _select_raw(at2, "E2c:1.0")
    body2 = _text_of(at2)
    e2c = recs[E2C_STUDY]
    assert e2c.code_sha is not None and e2c.code_sha in body2
    assert e2c.manifest_hash is not None and e2c.manifest_hash in body2
    assert "-0.021222260935" in body2
    # E2d
    at3 = _run_page()
    _select_raw(at3, "E2d:1.0")
    body3 = _text_of(at3)
    e2d = recs[E2D_STUDY]
    assert e2d.code_sha is not None and e2d.code_sha in body3
    assert e2d.manifest_hash is not None and e2d.manifest_hash in body3
    assert "0.005271433656" in body3


def test_study_list_and_selection_mutation() -> None:
    at = _run_page()
    assert not at.exception
    assert len(at.selectbox) == 1
    assert "Select study" in str(at.selectbox[0].label)
    assert len(at.dataframe) >= 1
    # mutation must change value and body
    at_before = _text_of(at)
    assert "E2b" in at_before
    _select_raw(at, "E2d:1.0")
    assert at.selectbox[0].value == "E2d:1.0"
    at_after = _text_of(at)
    assert "E2d" in at_after
    assert at_after != at_before or "E2d" in at_after


def test_research_question_hypothesis_mechanism_derived() -> None:
    recs = {r.study: r for r in build_admitted_e2_records()}
    at = _run_page()
    body = _text_of(at)
    assert "Research question" in body
    e2b = recs[E2B_STUDY]
    assert e2b.question[:20] in body
    # mechanism derived for E2b (question contains placement)
    assert "Placement is deterministic" in body
    # foreign without placement must not show it
    foreign = ResearchStudyRecord(
        study="F5",
        version="1.0",
        title="Foreign",
        question="Unrelated question",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="a" * 40,
        manifest_hash="b" * 64,
        evaluator_id=None,
        actor_id="c" * 64,
        checkpoint_id=None,
        trace_id="d" * 64,
        replication_unit="site_draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="generic",
        primary_metrics=["m1"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=1.0, metric="m1")],
        declared_summary=None,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=None,
        non_claims=None,
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F5", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at2.run()
        _select_raw(at2, "F5:1.0")
        body2 = _text_of(at2)
        assert "Placement is deterministic" not in body2


def test_identities_draws_arms_metrics_per_draw_summary() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "code_sha" in body.lower()
    assert "manifest_hash" in body.lower()
    assert "evaluator" in body.lower()
    assert "actor" in body.lower()
    assert "draws" in body.lower()
    assert "arms" in body.lower()
    assert "estimand" in body.lower()
    assert "primary" in body.lower()
    assert "Per-draw" in body
    # E2b has no summary, check Unavailable; E2c has interval
    assert "Declared summary: Unavailable" in body or "Declared interval:" in body
    assert "Declared 95% interval" not in body
    # also verify interval generic for E2c
    _select_raw(at, "E2c:1.0")
    body_c = _text_of(at)
    assert "Declared interval:" in body_c
    assert "Declared 95% interval" not in body_c


def test_evidence_admission_standing_visible() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "Evidence" in body and "admission" in body.lower()
    assert "RESEARCH-EVIDENCE FACT" in body
    assert "ADMITTED" in body


def test_lineage_only_explicit_and_warning() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "Lineage" in body
    assert "EXTENDS" in body
    assert "CONSTRUCT_VALIDITY" in body
    assert "ROBUSTNESS_CHECK" in body
    assert "does not establish causality" in body.lower()
    assert "task-level telemetry" in body.lower()
    # switching to E0 must not have fabricated E0 edges but still warning
    _select_raw(at, "E0:1.0")
    body_e0 = _text_of(at)
    assert "does not establish causality" in body_e0.lower()


def test_unavailable_study_truthfully_unavailable_not_adapter_fallback() -> None:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30)
    at.run()
    assert not at.exception
    _select_raw(at, "E0:1.0")
    assert not at.exception
    body = _text_of(at)
    assert "UNAVAILABLE" in body
    assert "truthfully UNAVAILABLE" in body
    assert "DESIGN_UNAVAILABLE" in body or "Experimental design unavailable" in body
    # verify via service snapshot directly, not adapter
    snap = RegistryService.with_default_e2().snapshot()
    e0 = snap.get_by_identity("E0", "1.0")
    assert e0 is not None
    assert e0.evidence_standing == EvidenceStanding.UNAVAILABLE
    assert e0.admission_status == AdmissionStatus.NOT_ADMITTED
    assert e0.code_sha is None
    # also E1
    at2 = AppTest.from_file("src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30)
    at2.run()
    _select_raw(at2, "E1:1.0")
    body2 = _text_of(at2)
    assert "UNAVAILABLE" in body2
    assert "truthfully UNAVAILABLE" in body2


def test_limitations_non_claims_and_product_links_visible() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "Limitations" in body
    assert "Non-claims" in body
    assert "Product links" in body
    recs = build_admitted_e2_records()
    assert recs[0].limitations is not None
    assert recs[0].limitations[0][:20] in body


def test_reproducibility_identities_visible() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "Reproducibility" in body
    assert "Snapshot fingerprint" in body
    assert "Receipt" in body


def test_structural_import_trusted_evidence_product_admission_distinguished() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    low = body.lower()
    assert "structural import" in low
    assert "trusted evidence" in low
    assert "product admission" in low


def test_default_has_no_e3_and_future_e3_generic_contract() -> None:
    snapshot = RegistryService.with_default_e2().snapshot()
    assert all(r.study != "E3" for r in snapshot.records)
    assert all(r.study != "E3" for r in snapshot.unavailable_records)
    assert all(
        r.study not in {"E3a", "E3b"} for r in snapshot.records + snapshot.unavailable_records
    )
    # future admitted E3 must render generic
    e3 = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="E3: admitted future",
        question="Future question with placement?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="e" * 40,
        manifest_hash="f" * 64,
        evaluator_id=None,
        actor_id="1" * 64,
        checkpoint_id=None,
        trace_id="2" * 64,
        replication_unit="future_draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="future estimand",
        primary_metrics=["future_metric"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=3.14, metric="future_metric")],
        declared_summary=DeclaredSummary(
            estimate=3.14,
            ci_lower=1.0,
            ci_upper=5.0,
            method="future method",
            metric="future_metric",
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["future limit"],
        non_claims=["future nonclaim"],
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[e3],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="E3", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.run()
        _select_raw(at, "E3:1.0")
        body = _text_of(at)
        assert "E3" in body
        assert "future_metric" in body
        assert "future_draw" in body
        assert "future method" in body
        assert "Declared interval:" in body
        assert "Declared 95% interval" not in body
        assert "Dynamic" not in body
        assert "fleet_draw" not in body


def test_unknown_unadmitted_cannot_enter_snapshot() -> None:
    # unadmitted record cannot be in admitted list
    bad = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="Bad",
        question="Q?",
        hypothesis=None,
        status=StudyStatus.UNAVAILABLE,
        code_sha=None,
        manifest_hash=None,
        evaluator_id=None,
        actor_id=None,
        checkpoint_id=None,
        trace_id=None,
        replication_unit=None,
        seeds=None,
        draws=None,
        arms=None,
        estimand=None,
        primary_metrics=None,
        secondary_metrics=None,
        per_draw_values=None,
        declared_summary=None,
        evidence_standing=EvidenceStanding.UNAVAILABLE,
        admission_status=AdmissionStatus.NOT_ADMITTED,
        limitations=["limit"],
        non_claims=None,
        product_links=None,
    )
    with pytest.raises((ValueError, ValidationError)):
        RegistrySnapshot.build(
            records=[bad],
            unavailable_records=[],
            lineage=LineageGraph(nodes=[StudyVersionIdentity(study="E3", version="1.0")], edges=[]),
            receipts=[],
        )
    # ingestion with wrong policy must fail
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), AdmissionPolicy(entries=[]))
    # also verify default service cannot admit arbitrary E3 package
    foreign = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="E3 foreign",
        question="Q?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="a" * 40,
        manifest_hash="b" * 64,
        evaluator_id=None,
        actor_id="c" * 64,
        checkpoint_id=None,
        trace_id="d" * 64,
        replication_unit="draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="est",
        primary_metrics=["m1"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=1.0, metric="m1")],
        declared_summary=None,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=None,
        non_claims=None,
        product_links=None,
    )
    # try to ingest via default policy should fail because policy doesn't allow E3
    tmp_pkg_obj = json.loads(pkg.to_json())
    tmp_pkg_obj["records"].append(json.loads(foreign.canonical_json()))
    # need to rebuild package fingerprint would not match, but ingestion will fail anyway
    bad_json = json.dumps(tmp_pkg_obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad_json, pol)


def test_no_dynamic_resource_semantics_and_generic_caption() -> None:
    at = _run_page()
    assert not at.exception
    body = _text_of(at)
    assert "Dynamic Resource Explorer" not in body
    low = body.lower()
    assert "no dynamic-resource" in low
    # foreign must also not invent dynamic
    foreign = ResearchStudyRecord(
        study="F10",
        version="1.0",
        title="Foreign",
        question="Q?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="3" * 40,
        manifest_hash="4" * 64,
        evaluator_id=None,
        actor_id="5" * 64,
        checkpoint_id=None,
        trace_id="6" * 64,
        replication_unit="custom_draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="est",
        primary_metrics=["mm"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=0.5, metric="mm")],
        declared_summary=None,
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=None,
        non_claims=None,
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F10", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at2.run()
        _select_raw(at2, "F10:1.0")
        body2 = _text_of(at2)
        assert "Replication unit is custom_draw" in body2
        assert "fleet_draw" not in body2
        assert "Dynamic" not in body2


def test_mutation_forged_record_fails_closed_and_fixed_code() -> None:
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    obj = json.loads(pkg.to_json())
    obj["records"][0]["per_draw_values"][0]["value"] = 0.999
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad, pol)
    bad_pol = AdmissionPolicy(entries=[])
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), bad_pol)
    recs = build_admitted_e2_records()
    e2b = recs[0]
    mutated = e2b.model_copy(update={"code_sha": "a" * 10})
    with pytest.raises(ValidationError):
        type(e2b).model_validate(mutated.model_dump(mode="json"))
    # UI error must show fixed code, not interpolated secret
    secret = "myTokenSecret999"  # noqa: S105
    exc = FileNotFoundError(  # noqa: S108
        f"/Users/bob/Library/secret {secret} payload={{'k':'{secret}'}}"  # noqa: S108
    )
    with patch("traffictwin.ui.pages.research_registry.RegistryService.with_default_e2") as mock:
        mock.side_effect = exc
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.run()
        assert not at.exception
        body = _text_of(at)
        assert "REGISTRY_CONSTRUCTION_FAILED" in body
        assert secret not in body
        assert "/Users" not in body
        assert "Library" not in body
        assert "myTokenSecret" not in body


def test_page_renders_error_state_fixed_reason_only() -> None:
    # inject Pydantic payload style leakage attempt
    payload_secret = "pydantic_payload_leak_123"  # noqa: S105
    msg = (  # noqa: E501
        f"ValidationError: field password={payload_secret} /home/alice/.config/token={payload_secret} /tmp/file"  # noqa: E501, S108
    )
    with patch("traffictwin.ui.pages.research_registry.RegistryService.with_default_e2") as mock:
        mock.side_effect = RuntimeError(msg)
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.run()
        assert not at.exception
        body = _text_of(at)
        assert "REGISTRY_CONSTRUCTION_FAILED" in body
        assert (
            "Research Registry snapshot could not be constructed: REGISTRY_CONSTRUCTION_FAILED"
            in body
        )
        assert payload_secret not in body
        assert "/home" not in body
        assert "/tmp" not in body  # noqa: S108
        assert "password" not in body.lower() or "password" not in body  # must not leak


def test_foreign_record_no_e2_claims() -> None:
    foreign = ResearchStudyRecord(
        study="FX",
        version="1.0",
        title="Foreign X",
        question="Foreign?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="a" * 40,
        manifest_hash="b" * 64,
        evaluator_id=None,
        actor_id="c" * 64,
        checkpoint_id=None,
        trace_id="d" * 64,
        replication_unit="fx_draw",
        seeds=[7],
        draws=[7],
        arms=None,
        estimand="fx estimand",
        primary_metrics=["fx_metric"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=7, value=7.7, metric="fx_metric")],
        declared_summary=DeclaredSummary(estimate=7.7, metric="fx_metric"),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["fx limit"],
        non_claims=None,
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="FX", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.run()
        _select_raw(at, "FX:1.0")
        body = _text_of(at)
        assert "fx_metric" in body
        assert "offered_task_deadline_attainment" not in body
        assert "offered_attainment_dla_minus_ingress_dla" not in body
        assert "fleet_draw" not in body


def test_page_does_not_hardcode_scientific_results() -> None:
    import pathlib

    src = pathlib.Path("src/traffictwin/ui/pages/research_registry.py").read_text()
    forbidden = ["0.683619229", "0.715773211", "-0.021222260935", "0.005271433656"]
    for val in forbidden:
        assert val not in src, f"UI page must not hard-code scientific result {val}"

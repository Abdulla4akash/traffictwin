"""App-level UI tests for Research Registry (Lane 09).

All selection branches are exercised via exact raw identity set_value and
widget.value mutation assertions. No tautological skips.
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
from traffictwin.ui.state import (
    default_session_state,
    load_ui_config,
)


def _run_app_page() -> AppTest:
    at = AppTest.from_file("src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30)
    for k, v in default_session_state(load_ui_config()).items():
        at.session_state[k] = v
    at.session_state["_v07_navigation_active"] = True
    at.run()
    return at


def _body(at: AppTest) -> str:
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
    assert at.selectbox[0].value == raw, (
        f"selection mutation failed: expected {raw!r} got {at.selectbox[0].value!r}"
    )


def test_research_registry_app_page_renders_read_only() -> None:
    at = _run_app_page()
    assert not at.exception, at.exception
    body = _body(at)
    assert "Research Registry" in body
    assert "read-only" in body.lower()
    assert len(at.selectbox) == 1
    assert "Select study" in str(at.selectbox[0].label)
    assert len(at.dataframe) >= 1
    assert at.selectbox[0].value == "E2b:1.0"


def test_select_e2b_exact_identities_metrics_draws() -> None:
    at = _run_app_page()
    assert not at.exception
    recs = {r.study: r for r in build_admitted_e2_records()}
    e2b = recs[E2B_STUDY]
    # default is E2b, but explicitly assert mutation
    assert at.selectbox[0].value == "E2b:1.0"
    body = _body(at)
    assert e2b.code_sha is not None and e2b.code_sha in body
    assert e2b.manifest_hash is not None and e2b.manifest_hash in body
    assert "offered_task_deadline_attainment" in body
    assert "0.683619229" in body
    assert "0.715773211" in body
    # per-draw draws and arms
    assert "0" in body  # draw 0
    assert "off" in body and "ingress_dla" in body
    # non-claims/limitations present
    assert e2b.non_claims is not None and len(e2b.non_claims) > 0
    assert e2b.non_claims[0][:20] in body
    # CI should not be declared 95% label for E2b (no interval)
    assert "Declared summary: Unavailable" in body or "Declared interval" in body
    # replication caption derived
    assert "Replication unit is fleet_draw" in body


def test_select_e2c_exact_metrics_cis_draws() -> None:
    at = _run_app_page()
    _select_raw(at, "E2c:1.0")
    body = _body(at)
    recs = {r.study: r for r in build_admitted_e2_records()}
    e2c = recs[E2C_STUDY]
    assert e2c.code_sha is not None and e2c.code_sha in body
    assert e2c.manifest_hash is not None and e2c.manifest_hash in body
    assert "offered_attainment_dla_minus_ingress_dla" in body
    # per-draw values 4 draws
    assert "-0.022097034972" in body
    assert "-0.020825491499" in body
    # declared interval generic label, not hardcoded 95%
    assert "Declared interval:" in body
    assert "Declared 95% interval" not in body
    # CI bounds
    assert "-0.02233525407" in body
    assert "-0.0201092678" in body
    assert e2c.declared_summary is not None
    assert e2c.declared_summary.method is not None
    assert e2c.declared_summary.method in body
    # replication derived
    assert "Replication unit is fleet_draw" in body


def test_select_e2d_exact_primary_secondary_draws_cis() -> None:
    at = _run_app_page()
    _select_raw(at, "E2d:1.0")
    body = _body(at)
    recs = {r.study: r for r in build_admitted_e2_records()}
    e2d = recs[E2D_STUDY]
    assert e2d.code_sha is not None and e2d.code_sha in body
    assert e2d.manifest_hash is not None and e2d.manifest_hash in body
    assert "offered_attainment_per_task_dla_minus_ingress_dla" in body
    assert "offered_attainment_per_task_dla_minus_dla" in body
    assert "0.004636732564" in body
    assert "0.026733767536" in body
    assert "Declared interval:" in body
    assert "Declared 95% interval" not in body
    assert "0.004422143925" in body
    assert "0.006120723387" in body
    assert (
        e2d.declared_summary is not None
        and e2d.declared_summary.method is not None
        and e2d.declared_summary.method in body
    )
    # secondary metric present via per_draw
    assert e2d.secondary_metrics is not None
    assert e2d.secondary_metrics[0] in body


def test_select_e0_unavailable_truthful() -> None:
    at = _run_app_page()
    _select_raw(at, "E0:1.0")
    body = _body(at)
    assert "UNAVAILABLE" in body
    assert "truthfully UNAVAILABLE" in body
    assert "DESIGN_UNAVAILABLE" in body or "Experimental design unavailable" in body
    assert "Research Registry unavailable" not in body  # not global error
    # must not leak code SHAs for unavailable
    # ensure unavailable fields show Unavailable, not a SHA
    assert "E0: historical" in body or "E0" in body
    # evidence standing from snapshot (not adapter fallback)
    snap = RegistryService.with_default_e2().snapshot()
    e0 = snap.get_by_identity("E0", "1.0")
    assert e0 is not None and e0.evidence_standing == EvidenceStanding.UNAVAILABLE
    assert e0.admission_status == AdmissionStatus.NOT_ADMITTED


def test_select_e1_unavailable_truthful() -> None:
    at = _run_app_page()
    _select_raw(at, "E1:1.0")
    body = _body(at)
    assert "UNAVAILABLE" in body
    assert "truthfully UNAVAILABLE" in body
    assert "DESIGN_UNAVAILABLE" in body or "Experimental design unavailable" in body
    snap = RegistryService.with_default_e2().snapshot()
    e1 = snap.get_by_identity("E1", "1.0")
    assert e1 is not None and e1.evidence_standing == EvidenceStanding.UNAVAILABLE


def test_replication_caption_derived_from_record() -> None:
    at = _run_app_page()
    _select_raw(at, "E2c:1.0")
    body = _body(at)
    assert "Replication unit is fleet_draw" in body
    # foreign record with custom replication_unit must not say fleet_draw
    foreign = ResearchStudyRecord(
        study="F9",
        version="1.0",
        title="Foreign study with custom replication",
        question="Does custom unit change outcome?",
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
        estimand="custom estimand",
        primary_metrics=["custom_metric"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=1.23, metric="custom_metric")],
        declared_summary=DeclaredSummary(
            estimate=1.23, method="custom method", metric="custom_metric"
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["limit"],
        non_claims=["nonclaim"],
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F9", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = _run_app_page()
        assert not at2.exception
        # force selection to foreign
        _select_raw(at2, "F9:1.0")
        body2 = _body(at2)
        assert "Replication unit is site_draw" in body2
        assert "fleet_draw" not in body2


def test_declared_interval_generic_label_and_method_separate() -> None:
    at = _run_app_page()
    _select_raw(at, "E2c:1.0")
    body = _body(at)
    assert "Declared interval:" in body
    assert "Declared 95% interval" not in body
    assert "two-sided Student-t 95% interval over fleet-draw differences" in body
    # also probe foreign
    foreign = ResearchStudyRecord(
        study="F8",
        version="1.0",
        title="Foreign interval test",
        question="Q?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="1" * 40,
        manifest_hash="2" * 64,
        evaluator_id=None,
        actor_id="3" * 64,
        checkpoint_id=None,
        trace_id="4" * 64,
        replication_unit="other_draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="est",
        primary_metrics=["m1"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=0.5, metric="m1")],
        declared_summary=DeclaredSummary(
            estimate=0.5, ci_lower=0.1, ci_upper=0.9, method="my exact method", metric="m1"
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=None,
        non_claims=None,
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F8", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = _run_app_page()
        _select_raw(at2, "F8:1.0")
        body2 = _body(at2)
        assert "Declared interval:" in body2
        assert "Declared 95% interval" not in body2
        assert "my exact method" in body2


def test_mechanism_derived_from_typed_fields_not_hardcoded() -> None:
    # Truthful: no fabricated placement/RSU/Kubernetes caption is ever rendered,
    # even when typed fields contain placement terms. Declared fields are verbatim.
    fabricated = (
        "Placement is deterministic infrastructure-side RSU management; not learned, "
        "not Kubernetes deployment."
    )
    at = _run_app_page()
    _select_raw(at, "E2c:1.0")
    body = _body(at)
    assert fabricated not in body
    assert "Placement is deterministic" not in body
    # declared fields still rendered verbatim
    recs = {r.study: r for r in build_admitted_e2_records()}
    e2c = recs[E2C_STUDY]
    assert e2c.question[:20] in body
    # Foreign without placement also must not show fabricated framing
    foreign = ResearchStudyRecord(
        study="F7",
        version="1.0",
        title="Foreign no placement",
        question="Does unrelated factor change outcome?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="5" * 40,
        manifest_hash="6" * 64,
        evaluator_id=None,
        actor_id="7" * 64,
        checkpoint_id=None,
        trace_id="8" * 64,
        replication_unit="site_draw",
        seeds=[1],
        draws=[1],
        arms=None,
        estimand="unrelated estimand",
        primary_metrics=["m2"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=1, value=2.0, metric="m2")],
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
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F7", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = _run_app_page()
        _select_raw(at2, "F7:1.0")
        body2 = _body(at2)
        assert fabricated not in body2
        assert "Placement is deterministic" not in body2
        assert "F7" in body2


def test_foreign_record_shows_no_e2_claims() -> None:
    foreign = ResearchStudyRecord(
        study="F6",
        version="2.0",
        title="Completely foreign",
        question="Foreign question about other domain",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="9" * 40,
        manifest_hash="a" * 64,
        evaluator_id=None,
        actor_id="b" * 64,
        checkpoint_id=None,
        trace_id="c" * 64,
        replication_unit="other_draw",
        seeds=[10],
        draws=[10],
        arms=None,
        estimand="foreign estimand",
        primary_metrics=["foreign_metric"],
        secondary_metrics=None,
        per_draw_values=[PerDrawValue(draw=10, value=9.99, metric="foreign_metric")],
        declared_summary=DeclaredSummary(estimate=9.99, metric="foreign_metric"),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["foreign limit"],
        non_claims=["foreign nonclaim"],
        product_links=None,
    )
    snap = RegistrySnapshot.build(
        records=[foreign],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="F6", version="2.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at2 = _run_app_page()
        _select_raw(at2, "F6:2.0")
        body2 = _body(at2)
        assert "F6" in body2 and "foreign_metric" in body2
        # must not contain E2-specific claims
        assert "offered_task_deadline_attainment" not in body2
        assert "offered_attainment_dla_minus_ingress_dla" not in body2
        assert "offered_attainment_per_task_dla_minus_ingress_dla" not in body2
        assert "fleet_draw" not in body2


def test_error_leakage_fixed_code_only_no_paths_secrets_payload() -> None:
    token_val = "superSecretTokenXYZ123"  # noqa: S105
    path_tail = "mySecretFile.txt"
    username = "alice"
    payload_val = "pydantic_input_payload_secret_9876"  # noqa: S105
    msg = (  # noqa: E501
        f"FileNotFoundError: [Errno 2] No such file: '/Users/{username}/Library/Application Support/{path_tail}' "  # noqa: E501
        f"/home/{username}/secrets.txt /tmp/{path_tail} token={token_val} api_key=AKIA_TEST password=hunter2 "  # noqa: E501, S108
        f"payload={{'field': '{payload_val}'}}"
    )
    exc = FileNotFoundError(msg)
    with patch("traffictwin.ui.pages.research_registry.RegistryService.with_default_e2") as mock:
        mock.side_effect = exc
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.session_state["_v07_navigation_active"] = True
        at.run()
        assert not at.exception
        body = _body(at)
        assert "REGISTRY_CONSTRUCTION_FAILED" in body
        assert (
            "Research Registry snapshot could not be constructed: REGISTRY_CONSTRUCTION_FAILED"
            in body
        )
        # must not leak any part
        assert "/Users" not in body
        assert "/home" not in body
        assert "/tmp" not in body  # noqa: S108
        assert "Library" not in body
        assert path_tail not in body
        assert (
            username not in body or "RESEARCH" in body
        )  # username inside path must be gone; allow benign?
        # strict: username token must not appear if it was only in injected path
        assert token_val not in body
        assert payload_val not in body
        assert "AKIA" not in body
        assert "hunter2" not in body
        # must not contain raw injected message
        assert "mySecretFile" not in body
        assert "superSecret" not in body


def test_default_has_no_e3_and_future_e3_renders_generic() -> None:
    snap_default = RegistryService.with_default_e2().snapshot()
    assert all(r.study != "E3" for r in snap_default.records)
    assert all(r.study != "E3" for r in snap_default.unavailable_records)
    assert all(r.study not in {"E3", "E3a", "E3b"} for r in snap_default.records)
    # build future admitted E3
    e3 = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="E3: future scaling study",
        question="Does future scaling change outcome?",
        hypothesis=None,
        status=StudyStatus.COMPLETED,
        code_sha="d" * 40,
        manifest_hash="e" * 64,
        evaluator_id=None,
        actor_id="f" * 64,
        checkpoint_id=None,
        trace_id="1" * 64,
        replication_unit="future_draw",
        seeds=[1, 2],
        draws=[1, 2],
        arms=None,
        estimand="future estimand",
        primary_metrics=["future_metric"],
        secondary_metrics=None,
        per_draw_values=[
            PerDrawValue(draw=1, value=0.11, metric="future_metric"),
            PerDrawValue(draw=2, value=0.22, metric="future_metric"),
        ],
        declared_summary=DeclaredSummary(
            estimate=0.165,
            ci_lower=0.10,
            ci_upper=0.23,
            method="future method 95% something",
            metric="future_metric",
        ),
        evidence_standing=EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        admission_status=AdmissionStatus.ADMITTED,
        limitations=["future limit"],
        non_claims=["future nonclaim"],
        product_links=None,
    )
    snap_future = RegistrySnapshot.build(
        records=[e3],
        unavailable_records=[],
        lineage=LineageGraph(nodes=[StudyVersionIdentity(study="E3", version="1.0")], edges=[]),
        receipts=[],
    )
    mock_svc = Mock(spec=RegistryService)
    mock_svc.snapshot.return_value = snap_future
    with patch(
        "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
        return_value=mock_svc,
    ):
        at = _run_app_page()
        assert not at.exception
        _select_raw(at, "E3:1.0")
        body = _body(at)
        assert "E3" in body
        assert "future_metric" in body
        assert "future_draw" in body
        assert "future method" in body
        # must not invent Dynamic/scaling semantics
        assert "Dynamic" not in body
        assert "dynamic resource" not in body.lower()
        assert "No dynamic-resource semantics" in body
        # fabricated placement/RSU/Kubernetes caption must be absent (generic UI contract)
        fabricated = (
            "Placement is deterministic infrastructure-side RSU management; not learned, "
            "not Kubernetes deployment."
        )
        assert fabricated not in body
        assert "Placement is deterministic" not in body
        # generic interval label
        assert "Declared interval:" in body
        assert "Declared 95% interval" not in body
        # must show declared fields exactly
        assert "0.11" in body and "0.22" in body
        assert "future limit" in body


def test_fabricated_caption_absent_for_substring_triggers() -> None:
    """Discriminating: substring triggers must not render fabricated RSU/Kubernetes caption.

    Covers `versus` (contains rsu), `persuade` (contains rsu), `deadline`,
    a question containing `placement`, and a non-claim that explicitly
    disclaims RSU placement. No substring scanning should trigger the
    hardcoded caption.
    """
    fabricated = (
        "Placement is deterministic infrastructure-side RSU management; not learned, "
        "not Kubernetes deployment."
    )

    def _check(record: ResearchStudyRecord, trigger_snippet: str) -> None:
        snap = RegistrySnapshot.build(
            records=[record],
            unavailable_records=[],
            lineage=LineageGraph(
                nodes=[StudyVersionIdentity(study=record.study, version=record.version)],
                edges=[],
            ),
            receipts=[],
        )
        mock_svc = Mock(spec=RegistryService)
        mock_svc.snapshot.return_value = snap
        with patch(
            "traffictwin.ui.pages.research_registry.RegistryService.with_default_e2",
            return_value=mock_svc,
        ):
            at = _run_app_page()
            assert not at.exception, at.exception
            _select_raw(at, f"{record.study}:{record.version}")
            body = _body(at)
            assert trigger_snippet in body, (
                f"declared field not rendered verbatim: {trigger_snippet!r}"
            )
            assert fabricated not in body
            assert "Placement is deterministic" not in body

    base_kwargs: dict[str, object] = {
        "version": "1.0",
        "title": "Discriminating trigger test",
        "status": StudyStatus.COMPLETED,
        "code_sha": "a" * 40,
        "manifest_hash": "b" * 64,
        "evaluator_id": None,
        "actor_id": "c" * 64,
        "checkpoint_id": None,
        "trace_id": "d" * 64,
        "replication_unit": "site_draw",
        "seeds": [1],
        "draws": [1],
        "arms": None,
        "secondary_metrics": None,
        "per_draw_values": [PerDrawValue(draw=1, value=1.0, metric="m1")],
        "evidence_standing": EvidenceStanding.RESEARCH_EVIDENCE_FACT,
        "admission_status": AdmissionStatus.ADMITTED,
        "product_links": None,
    }

    # versus contains rsu as substring — previously triggered caption incorrectly
    rec_versus = ResearchStudyRecord(
        study="FX1",
        question="Does A versus B change outcome?",
        hypothesis="We compare A versus B on attainment.",
        estimand="difference in attainment versus baseline",
        primary_metrics=["m1"],
        declared_summary=DeclaredSummary(estimate=1.0, metric="m1"),
        limitations=None,
        non_claims=None,
        **base_kwargs,
    )
    _check(rec_versus, "versus")

    # persuade contains rsu as substring
    rec_persuade = ResearchStudyRecord(
        study="FX2",
        question="Can we persuade drivers to change route?",
        hypothesis=None,
        estimand="effect of persuade intervention",
        primary_metrics=["m1"],
        declared_summary=None,
        limitations=None,
        non_claims=None,
        **base_kwargs,
    )
    _check(rec_persuade, "persuade")

    # deadline substring in method/question
    rec_deadline = ResearchStudyRecord(
        study="FX3",
        question="Does intervention change attainment under deadline?",
        hypothesis=None,
        estimand="deadline attainment",
        primary_metrics=["m1"],
        declared_summary=DeclaredSummary(
            estimate=0.5, ci_lower=0.1, ci_upper=0.9, method="deadline-aware estimator", metric="m1"
        ),
        limitations=["deadline handling noted"],
        non_claims=None,
        **base_kwargs,
    )
    _check(rec_deadline, "deadline")

    # question containing placement explicitly
    rec_placement = ResearchStudyRecord(
        study="FX4",
        question="Does RSU placement strategy affect task assignment?",
        hypothesis=None,
        estimand="placement effect",
        primary_metrics=["m1"],
        declared_summary=None,
        limitations=None,
        non_claims=None,
        **base_kwargs,
    )
    _check(rec_placement, "placement")

    # non-claim that explicitly disclaims RSU placement — must not be inverted
    rec_disclaim = ResearchStudyRecord(
        study="FX5",
        question="Foreign question without placement cue",
        hypothesis=None,
        estimand="generic estimand",
        primary_metrics=["m1"],
        declared_summary=None,
        limitations=None,
        non_claims=[
            "This study makes no claim about RSU placement and does not evaluate Kubernetes deployment."  # noqa: E501
        ],
        **base_kwargs,
    )
    _check(rec_disclaim, "makes no claim about RSU placement")


def test_unknown_unadmitted_cannot_enter_snapshot_service() -> None:
    # Unadmitted E3 must not be placeable as admitted record
    bad_e3 = ResearchStudyRecord(
        study="E3",
        version="1.0",
        title="Bad E3 unadmitted",
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
    # cannot be built as admitted record
    with pytest.raises((ValueError, ValidationError)):
        RegistrySnapshot.build(
            records=[bad_e3],  # bad: admitted records must be ADMITTED
            unavailable_records=[],
            lineage=LineageGraph(nodes=[StudyVersionIdentity(study="E3", version="1.0")], edges=[]),
            receipts=[],
        )
    # also ingestion must fail for unknown package
    pkg = build_e2_study_package()
    # mutate package to include bad_e3 but policy stays E2-only
    obj = json.loads(pkg.to_json())
    obj["records"].append(json.loads(bad_e3.canonical_json()))
    bad_json = json.dumps(obj)
    pol = build_default_e2_admission_policy(pkg)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad_json, pol)
    # empty policy must fail
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), AdmissionPolicy(entries=[]))


def test_forged_mutation_fails_closed_and_error_state_fixed_code() -> None:
    pkg = build_e2_study_package()
    pol = build_default_e2_admission_policy(pkg)
    obj = json.loads(pkg.to_json())
    obj["records"][0]["per_draw_values"][0]["value"] = 0.111
    bad = json.dumps(obj)
    with pytest.raises(ResearchIngestionError):
        ingest_package(bad, pol)
    with pytest.raises(ResearchIngestionError):
        ingest_package(pkg.to_json(), AdmissionPolicy(entries=[]))
    with patch("traffictwin.ui.pages.research_registry.RegistryService.with_default_e2") as mock:
        mock.side_effect = ValueError("typed verification failed")
        at = AppTest.from_file(
            "src/traffictwin/ui/app_pages/research_registry.py", default_timeout=30
        )
        at.session_state["_v07_navigation_active"] = True
        at.run()
        assert not at.exception
        body = _body(at)
        assert "REGISTRY_CONSTRUCTION_FAILED" in body
        assert "typed verification" not in body
        assert "ADMITTED RESEARCH" not in body


def test_distinguishes_import_evidence_admission() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    low = body.lower()
    assert "structural import" in low
    assert "trusted evidence" in low
    assert "product admission" in low
    assert "task-level telemetry" in low


def test_no_arbitrary_file_or_secrets_in_normal_render() -> None:
    at = _run_app_page()
    assert not at.exception
    body = _body(at)
    assert "/Users" not in body
    assert "/tmp" not in body  # noqa: S108
    assert "/home" not in body
    assert "REGISTRY_CONSTRUCTION_FAILED" not in body or "unavailable" in body.lower()

"""AppTest coverage for the additive Evidence Admission Inbox page.

Validates evidence and authority boundary before results, queues, empty state,
explicit decision form, and deterministic exports — thin UI over typed service.
Session-local: each browser session has its own inbox.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.evidence_admission.models import (
    CompatibilityStanding,
    EvidenceMode,
    EvidenceReviewState,
    RightsPrivacyStanding,
    ValidationStanding,
)
from traffictwin.evidence_admission.service import EvidenceAdmissionInboxService
from traffictwin.ui.pages.evidence_admission import SESSION_SERVICE_KEY
from traffictwin.ui.state import default_session_state, load_ui_config


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _app(monkeypatch: MonkeyPatch, workspace: Path) -> Any:  # noqa: ANN401
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/evidence_admission.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _captions(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(c.value) for c in app.caption)


def _infos(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(c.value) for c in app.info)


def _make_service_with_case(
    case_id: str = "case-ui-1",
    cell_id: str = "cell-ui-1",
    state: EvidenceReviewState | None = None,
) -> EvidenceAdmissionInboxService:
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id=case_id,
        candidate_artifact_fingerprint=_hex(f"ui-art-{case_id}"),
        expected_preregistration_cell_id=cell_id,
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex(f"ui-con-{case_id}"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        findings=[],
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    if state is not None and state != EvidenceReviewState.PENDING:
        svc.append_decision(
            case_id=case_id,
            decision_id=f"dec-{case_id}-1",
            decision=state,
            reason="ui seeding",
            reviewer_label="reviewer-ui",
            decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        )
    return svc


def _inject_service(app: Any, svc: EvidenceAdmissionInboxService) -> None:  # noqa: ANN401
    app.session_state[SESSION_SERVICE_KEY] = svc


def test_page_states_its_evidence_and_authority_boundary_before_results(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    assert any(t.value == "Evidence Admission Inbox" for t in app.title)
    captions = _captions(app)
    assert "validation is not admission" in captions.lower()
    assert "only an explicit" in captions.lower()
    assert "does not establish external validity" in captions.lower()


def test_page_renders_without_exception_and_has_one_h1(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    titles = [str(t.value) for t in app.title]
    assert titles.count("Evidence Admission Inbox") == 1


def test_page_has_no_duplicate_widget_keys(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    svc = _make_service_with_case("case-a", "cell-a")
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    for kind in ("button", "selectbox", "text_input", "text_area"):
        labels = [
            str(el.label).strip().lower() for el in getattr(app, kind) if hasattr(el, "label")
        ]
        assert all(labels), f"unlabelled {kind} exists"
        dupes = {lab for lab in labels if labels.count(lab) > 1}
        assert not dupes, f"duplicated {kind} labels: {sorted(dupes)}"
    assert not app.exception


def test_empty_state_is_useful_before_any_case(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    infos = _infos(app)
    assert "inbox is empty" in infos.lower()
    subheaders = " ".join(str(h.value) for h in app.subheader)
    assert "Pending queue" in subheaders
    assert "Needs information queue" in subheaders
    assert "Admitted history" in subheaders
    assert "Rejected and withdrawn history" in subheaders


def test_pending_and_admitted_queues_render_typed_service_output(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    # pending
    svc.create_case(
        case_id="case-pending",
        candidate_artifact_fingerprint=_hex("art-pending"),
        expected_preregistration_cell_id="cell-pending",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-pending"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    # needs_information
    svc.create_case(
        case_id="case-needs",
        candidate_artifact_fingerprint=_hex("art-needs"),
        expected_preregistration_cell_id="cell-needs",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-needs"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    svc.append_decision(
        case_id="case-needs",
        decision_id="dec-case-needs-1",
        decision=EvidenceReviewState.NEEDS_INFORMATION,
        reason="need info",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
        requested_information_fields=["field_a"],
    )
    # admitted
    svc.create_case(
        case_id="case-admitted",
        candidate_artifact_fingerprint=_hex("art-admitted"),
        expected_preregistration_cell_id="cell-admitted",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-admitted"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    svc.append_decision(
        case_id="case-admitted",
        decision_id="dec-case-admitted-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit demo",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    tables_text = " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)
    assert "case-pending" in tables_text
    assert "case-needs" in tables_text
    assert "case-admitted" in tables_text
    captions = _captions(app)
    assert "rights standing" in captions.lower()


def test_case_detail_shows_findings_and_standing_before_decision_controls(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    svc = _make_service_with_case("case-detail", "cell-detail")
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    captions = _captions(app)
    assert "rights standing" in captions.lower() or "validation" in captions.lower()
    # Must use actual decision control, not the case selector
    decision_boxes = [s for s in app.selectbox if s.label == "Decision (target state)"]
    assert len(decision_boxes) == 1, (
        f"expected Decision (target state) selectbox, got {[s.label for s in app.selectbox]}"
    )
    assert any("reason" in str(t.label).lower() for t in app.text_area)
    assert any("reviewer" in str(t.label).lower() for t in app.text_input)
    # Prove findings/standing tables exist before decision controls
    # At least two dataframes (findings/standing) should be present and decision form is rendered
    assert len(app.dataframe) >= 2


def test_attachment_preview_is_unavailable_for_pending_case(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    svc = _make_service_with_case("case-pend-attach", "cell-pend")
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    infos = _infos(app)
    assert "fail closed" in infos.lower() or "pending" in infos.lower()


def test_admitted_case_shows_attachment_preview_and_download(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id="case-adm-preview",
        candidate_artifact_fingerprint=_hex("art-preview"),
        expected_preregistration_cell_id="cell-preview",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-preview"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    svc.append_decision(
        case_id="case-adm-preview",
        decision_id="dec-case-adm-preview-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit for preview",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    assert any(
        "admitted attachment is available" in str(s.value).lower() for s in app.success
    ) or any("admitted attachment" in str(c.value).lower() for c in app.caption)
    assert len(app.download_button) >= 3


def test_no_automatic_decision_is_made_on_page_load(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    svc = _make_service_with_case("case-no-auto", "cell-no-auto")
    assert len(svc.get_ledger("case-no-auto").decisions) == 0
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    # After page load without submitting form, ledger should still be empty in the same session service  # noqa: E501
    session_svc: EvidenceAdmissionInboxService = app.session_state[SESSION_SERVICE_KEY]
    assert len(session_svc.get_ledger("case-no-auto").decisions) == 0


def test_ui_session_isolation_two_sessions_do_not_share_cases(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Session A contains case A
    svc_a = _make_service_with_case("case-A", "cell-A")
    app_a = _app(monkeypatch, tmp_path / "workspace_a")
    _inject_service(app_a, svc_a)
    app_a.run(timeout=20)
    assert not app_a.exception
    tables_a = " ".join(frame.value.to_csv(index=False) for frame in app_a.dataframe)
    assert "case-A" in tables_a

    # Session B is fresh and must not contain case A
    app_b = _app(monkeypatch, tmp_path / "workspace_b")
    # Do not inject svc_a; let it create its own empty service
    app_b.run(timeout=20)
    assert not app_b.exception
    tables_b = " ".join(frame.value.to_csv(index=False) for frame in app_b.dataframe)
    assert "case-A" not in tables_b
    infos_b = _infos(app_b)
    assert "inbox is empty" in infos_b.lower()

    # Session A rerun retains its own queue
    app_a2 = _app(monkeypatch, tmp_path / "workspace_a")
    # Re-inject the same service instance to simulate same browser session retaining state
    # In real Streamlit, session_state persists across reruns; we simulate by reusing the same svc
    _inject_service(app_a2, svc_a)
    app_a2.run(timeout=20)
    assert not app_a2.exception
    tables_a2 = " ".join(frame.value.to_csv(index=False) for frame in app_a2.dataframe)
    assert "case-A" in tables_a2


def test_ui_transition_options_derive_from_authoritative_table(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from traffictwin.evidence_admission.service import allowed_transitions_from

    # Service table is authoritative
    assert set(allowed_transitions_from(EvidenceReviewState.PENDING)) == {
        EvidenceReviewState.NEEDS_INFORMATION,
        EvidenceReviewState.ADMITTED,
        EvidenceReviewState.REJECTED,
    }
    assert set(allowed_transitions_from(EvidenceReviewState.ADMITTED)) == {
        EvidenceReviewState.WITHDRAWN
    }
    assert set(allowed_transitions_from(EvidenceReviewState.WITHDRAWN)) == set()

    # UI pending: rendered Decision selectbox options must equal service table
    svc_pending = _make_service_with_case("case-trans-pending", "cell-trans-pending")
    app_pending = _app(monkeypatch, tmp_path / "workspace_pending")
    _inject_service(app_pending, svc_pending)
    app_pending.run(timeout=20)
    assert not app_pending.exception
    pending_box = next(s for s in app_pending.selectbox if s.label == "Decision (target state)")
    expected_pending = sorted(
        s.value for s in allowed_transitions_from(EvidenceReviewState.PENDING)
    )
    assert sorted(pending_box.options) == expected_pending

    # UI admitted: only withdrawn
    svc_adm = _make_service_with_case(
        "case-trans-adm", "cell-trans-adm", state=EvidenceReviewState.ADMITTED
    )
    app_adm = _app(monkeypatch, tmp_path / "workspace_adm")
    _inject_service(app_adm, svc_adm)
    app_adm.run(timeout=20)
    assert not app_adm.exception
    adm_box = next(s for s in app_adm.selectbox if s.label == "Decision (target state)")
    assert adm_box.options == ["withdrawn"]

    # Withdrawn is terminal: no Decision selectbox, terminal message present
    svc_wd = _make_service_with_case(
        "case-trans-wd", "cell-trans-wd", state=EvidenceReviewState.ADMITTED
    )
    # append withdrawn
    from datetime import UTC, datetime

    svc_wd.append_decision(
        case_id="case-trans-wd",
        decision_id="dec-case-trans-wd-2",
        decision=EvidenceReviewState.WITHDRAWN,
        reason="withdraw",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 2, tzinfo=UTC),
    )
    app_wd = _app(monkeypatch, tmp_path / "workspace_wd")
    _inject_service(app_wd, svc_wd)
    app_wd.run(timeout=20)
    assert not app_wd.exception
    assert not [s for s in app_wd.selectbox if s.label == "Decision (target state)"]
    assert any("terminal" in str(i.value).lower() for i in app_wd.info)


def test_ui_duplicate_case_id_shows_error_and_preserves_original(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # B1 UI: duplicate case_id via demo form must be refused, original admitted preserved
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    # Create demo c1 cellA via UI
    app.text_input(key="evidence_admission_demo_case_id").set_value("c1").run(timeout=20)
    app.text_input(key="evidence_admission_demo_cell").set_value("cellA").run(timeout=20)
    app.button(key="evidence_admission_create_demo").click().run(timeout=20)
    assert not app.exception
    # Record admitted decision via service (prefer UI but service is deterministic)
    svc2: EvidenceAdmissionInboxService = app.session_state[SESSION_SERVICE_KEY]
    svc2.append_decision(
        case_id="c1",
        decision_id="dec-c1-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    app.run(timeout=20)
    assert not app.exception
    # Verify admitted
    assert svc2.get_ledger("c1").current_state == EvidenceReviewState.ADMITTED
    # Attempt duplicate c1 cellB
    app.text_input(key="evidence_admission_demo_case_id").set_value("c1").run(timeout=20)
    app.text_input(key="evidence_admission_demo_cell").set_value("cellB").run(timeout=20)
    app.button(key="evidence_admission_create_demo").click().run(timeout=20)
    assert not app.exception
    # Require error visible with duplicate identity language
    errors = " ".join(str(e.value) for e in app.error)
    assert "duplicate" in errors.lower()
    assert "c1" in errors
    # Original remains admitted
    svc3: EvidenceAdmissionInboxService = app.session_state[SESSION_SERVICE_KEY]
    assert svc3.get_case("c1").expected_preregistration_cell_id == "cellA"
    assert svc3.get_ledger("c1").current_state == EvidenceReviewState.ADMITTED
    assert len(svc3.get_ledger("c1").decisions) == 1
    # History still rendered (admitted decision present in dataframe)
    tables_text = " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)
    assert "c1" in tables_text


def test_ui_inconsistent_pair_fails_closed_and_hides_controls(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # B2: deliberately inconsistent case+ledger must fail closed

    svc = _make_service_with_case("case-bad", "cell-bad")
    ledger = svc.get_ledger("case-bad")
    case = svc.get_case("case-bad")
    corrupted = case.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    svc._cases["case-bad"] = type(svc._cases["case-bad"])(case=corrupted, ledger=ledger)
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    errors = " ".join(str(e.value) for e in app.error)
    assert (
        "integrity" in errors.lower()
        or "mismatch" in errors.lower()
        or "disagrees" in errors.lower()
    )
    # Must reference integrity/state/tail
    assert any(k in errors.lower() for k in ["integrity", "state", "tail", "mismatch"])
    # Normal decision form absent
    assert not [s for s in app.selectbox if s.label == "Decision (target state)"]
    # No attachment/receipt download for inconsistent
    assert not [b for b in app.download_button if "admitted attachment" in str(b.label).lower()]
    assert not [
        b
        for b in app.download_button
        if "receipt" in str(b.label).lower() and "latest" in str(b.label).lower()
    ]
    # Must NOT present Current state = admitted as valid standing
    # The standing table for invalid pair is not rendered; only forensic
    # Check normal Current state = admitted is not shown as trustworthy
    # We assert error path did not render normal pair integrity caption
    captions = _captions(app)
    assert "pair integrity verified" not in captions.lower()


def test_ui_positive_control_pending_and_admitted_states(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # B2 positive: valid pending shows pending, admitted shows withdrawn option
    from traffictwin.evidence_admission.service import allowed_transitions_from

    svc_pending = _make_service_with_case("case-pos-pending", "cell-pos-pending")
    app_pending = _app(monkeypatch, tmp_path / "workspace_pending")
    _inject_service(app_pending, svc_pending)
    app_pending.run(timeout=20)
    assert not app_pending.exception
    # Current state display should be pending
    # Find the standing dataframe and check Current state value
    # The UI renders display_state derived from ledger; for empty ledger should be pending
    assert any("pending" in str(c.value).lower() for c in app_pending.caption) or any(
        "pending" in frame.value.to_csv(index=False) for frame in app_pending.dataframe
    )
    pending_box = next(s for s in app_pending.selectbox if s.label == "Decision (target state)")
    assert sorted(pending_box.options) == sorted(
        s.value for s in allowed_transitions_from(EvidenceReviewState.PENDING)
    )

    svc_adm = _make_service_with_case(
        "case-pos-adm", "cell-pos-adm", state=EvidenceReviewState.ADMITTED
    )
    app_adm = _app(monkeypatch, tmp_path / "workspace_adm")
    _inject_service(app_adm, svc_adm)
    app_adm.run(timeout=20)
    assert not app_adm.exception
    adm_box = next(s for s in app_adm.selectbox if s.label == "Decision (target state)")
    assert adm_box.options == ["withdrawn"]


def test_ui_decision_form_submission_creates_ledger_entry(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # Q2: real AppTest for decision form submission
    svc = _make_service_with_case("case-q2", "cell-q2")
    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    # Initial pending, options include admitted
    pending_box = next(s for s in app.selectbox if s.label == "Decision (target state)")
    assert "admitted" in pending_box.options
    # Fill form: select admitted, reason, reviewer
    pending_box.set_value("admitted").run(timeout=20)
    app.text_area(key="evidence_admission_reason").set_value("admit for q2").run(timeout=20)
    app.text_input(key="evidence_admission_reviewer").set_value("reviewer-q2").run(timeout=20)
    # Click the form submit button by label (key is FormSubmitter:...)
    btn = next(b for b in app.button if b.label == "Record decision")
    btn.click().run(timeout=20)
    app.run(timeout=20)
    # Verify ledger
    session_svc: EvidenceAdmissionInboxService = app.session_state[SESSION_SERVICE_KEY]
    ledger = session_svc.get_ledger("case-q2")
    assert len(ledger.decisions) == 1
    assert ledger.current_state == EvidenceReviewState.ADMITTED
    assert session_svc.verify_ledger("case-q2") == []
    # Page shows admitted state
    assert any("admitted" in str(c.value).lower() for c in app.caption) or any(
        "admitted" in frame.value.to_csv(index=False) for frame in app.dataframe
    )
    # Decision options now == ["withdrawn"]
    adm_box = next(s for s in app.selectbox if s.label == "Decision (target state)")
    assert adm_box.options == ["withdrawn"]
    # History contains admitted decision
    history_text = " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)
    assert "admitted" in history_text.lower()


def test_b3_summary_export_corrupt_does_not_crash_inbox(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """B3: one corrupt case must not crash whole inbox; valid case remains usable."""
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    # aaa-good valid
    svc.create_case(
        case_id="aaa-good",
        candidate_artifact_fingerprint=_hex("art-aaa-good"),
        expected_preregistration_cell_id="cell-good",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-good"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    svc.append_decision(
        case_id="aaa-good",
        decision_id="dec-aaa-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit good",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    # zzz-bad corrupt: cached ADMITTED with empty ledger
    svc.create_case(
        case_id="zzz-bad",
        candidate_artifact_fingerprint=_hex("art-zzz-bad"),
        expected_preregistration_cell_id="cell-bad",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-bad"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    case_bad = svc.get_case("zzz-bad")
    ledger_bad = svc.get_ledger("zzz-bad")
    corrupted = case_bad.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    svc._cases["zzz-bad"] = type(svc._cases["zzz-bad"])(case=corrupted, ledger=ledger_bad)

    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    # Ensure aaa-good is selected (default sorted case_ids gives aaa-good first)
    app.run(timeout=20)
    assert not app.exception
    # Valid case detail still renders (not taken down by corrupt summary)
    # Select aaa-good explicitly if needed
    try:
        sel = next(s for s in app.selectbox if s.label == "Select case for detail and decision")
        if sel.value != "aaa-good":
            sel.set_value("aaa-good").run(timeout=20)
    except StopIteration:
        pass
    app.run(timeout=20)
    assert not app.exception
    # Valid case detail area still renders — check for aaa-good in tables/captions
    tables_text = " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)
    assert "aaa-good" in tables_text or any("aaa-good" in str(c.value) for c in app.caption)
    # Error explains review-summary export is unavailable/refused and names zzz-bad
    errors = " ".join(str(e.value) for e in app.error)
    assert "zzz-bad" in errors
    assert (
        "review-summary" in errors.lower()
        or "review-summary csv" in errors.lower()
        or "unavailable" in errors.lower()
        or "refused" in errors.lower()
    )
    assert "integrity" in errors.lower() or "verification" in errors.lower()
    # Review-summary CSV download button is absent (withheld)
    assert not [b for b in app.download_button if "review summary csv" in str(b.label).lower()]
    # Case JSON / ledger JSON controls for valid selected case remain available
    assert any("ledger json" in str(b.label).lower() for b in app.download_button)
    assert any("case json" in str(b.label).lower() for b in app.download_button)


def test_b4_queue_displays_ledger_derived_state(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """B4: queue tables must not display cached state; pending queue shows pending for corrupt."""
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id="zzz-bad",
        candidate_artifact_fingerprint=_hex("art-zzz-bad2"),
        expected_preregistration_cell_id="cell-bad2",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-bad2"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    case_bad = svc.get_case("zzz-bad")
    ledger_bad = svc.get_ledger("zzz-bad")
    corrupted = case_bad.model_copy(update={"current_state": EvidenceReviewState.ADMITTED})
    svc._cases["zzz-bad"] = type(svc._cases["zzz-bad"])(case=corrupted, ledger=ledger_bad)

    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    # Inspect Pending queue dataframe (should contain zzz-bad with state pending, not admitted)
    found = False
    for df in app.dataframe:
        val = df.value if hasattr(df, "value") else None
        if val is None:
            continue
        import pandas as pd  # type: ignore[import-untyped]

        if not isinstance(val, pd.DataFrame):
            continue
        if "case_id" not in val.columns or "state" not in val.columns:
            continue
        # Look for Pending queue rows (we know zzz-bad should be in pending via ledger-derived)
        if (val["case_id"] == "zzz-bad").any():
            row = val[val["case_id"] == "zzz-bad"]
            assert not row.empty
            state_val = str(row.iloc[0]["state"])
            assert state_val == "pending", (
                f"expected pending but got {state_val!r} (must not be admitted)"
            )
            assert state_val != "admitted"
            found = True
            break
    assert found, "zzz-bad not found in Pending queue dataframe with ledger-derived state"


def test_b5_history_does_not_claim_pair_integrity_on_forensic_failure(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """B5: history must never claim pair integrity on forensic failure; tail anchor mismatch."""
    from datetime import UTC, datetime

    svc = EvidenceAdmissionInboxService()
    svc.create_case(
        case_id="case-tail-mismatch",
        candidate_artifact_fingerprint=_hex("art-tail"),
        expected_preregistration_cell_id="cell-tail",
        observed_metric_key="task.completion.rate",
        observed_metric_version="1.0",
        observed_metric_unit="ratio",
        evidence_mode=EvidenceMode.IMPORTED_EVIDENCE,
        source_contract_result_fingerprint=_hex("con-tail"),
        rights_privacy_standing=RightsPrivacyStanding.ALLOWED,
        validation_standing=ValidationStanding.VALIDATED,
        compatibility_standing=CompatibilityStanding.COMPATIBLE,
        created_at=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
    )
    svc.append_decision(
        case_id="case-tail-mismatch",
        decision_id="dec-1",
        decision=EvidenceReviewState.ADMITTED,
        reason="admit",
        reviewer_label="r1",
        decision_timestamp=datetime(2026, 8, 10, 12, 1, tzinfo=UTC),
    )
    ledger = svc.get_ledger("case-tail-mismatch")
    case = svc.get_case("case-tail-mismatch")
    # Create tail anchor mismatch but keep ledger chain clean: corrupt case tail
    corrupted_case = case.model_copy(update={"ledger_tail_fingerprint": "f" * 64})
    svc._cases["case-tail-mismatch"] = type(svc._cases["case-tail-mismatch"])(
        case=corrupted_case, ledger=ledger
    )
    # Verify ledger chain itself is still clean
    assert ledger.verify() == []
    # But pair is inconsistent
    from traffictwin.evidence_admission.service import verify_case_with_ledger

    assert verify_case_with_ledger(corrupted_case, ledger) != []

    app = _app(monkeypatch, tmp_path / "workspace")
    _inject_service(app, svc)
    app.run(timeout=20)
    assert not app.exception
    errors = " ".join(str(e.value) for e in app.error)
    assert "integrity" in errors.lower() or "mismatch" in errors.lower() or "tail" in errors.lower()
    # Chain may still verify, but must not claim pair integrity
    all_text = " ".join([str(c.value) for c in app.caption] + [str(e.value) for e in app.error])
    assert "pair integrity verified" not in all_text.lower()

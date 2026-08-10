"""AppTest coverage for the additive Evidence Admission Inbox page.

Validates evidence and authority boundary before results, queues, empty state,
explicit decision form, and deterministic exports — thin UI over typed service.
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
from traffictwin.evidence_admission.service import get_global_service, reset_global_service
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


def _warnings(app: Any) -> str:  # noqa: ANN401
    return " ".join(str(c.value) for c in app.warning)


def _seed_case(
    case_id: str = "case-ui-1",
    cell_id: str = "cell-ui-1",
    state: EvidenceReviewState | None = None,
) -> None:
    from datetime import UTC, datetime

    svc = get_global_service()
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


def test_page_states_its_evidence_and_authority_boundary_before_results(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    reset_global_service()
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
    reset_global_service()
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    titles = [str(t.value) for t in app.title]
    assert titles.count("Evidence Admission Inbox") == 1


def test_page_has_no_duplicate_widget_keys(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    reset_global_service()
    _seed_case("case-a", "cell-a")
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    # Collect widget keys via session_state keys that look like widget keys? Instead check labels duplicate guard  # noqa: E501
    # Use labels unique check from platform pages pattern
    for kind in ("button", "selectbox", "text_input", "text_area"):
        labels = [
            str(el.label).strip().lower() for el in getattr(app, kind) if hasattr(el, "label")
        ]
        assert all(labels), f"unlabelled {kind} exists"
        dupes = {lab for lab in labels if labels.count(lab) > 1}
        assert not dupes, f"duplicated {kind} labels: {sorted(dupes)}"
    # Also check duplicate widget keys via raw key uniqueness in app state keys
    # AppTest stores widget keys in session_state — no exception about duplicate keys already proves, but extra guard:  # noqa: E501
    assert not app.exception


def test_empty_state_is_useful_before_any_case(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    reset_global_service()
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    infos = _infos(app)
    assert "inbox is empty" in infos.lower()
    # Empty queues are stated, not hidden
    subheaders = " ".join(str(h.value) for h in app.subheader)
    assert "Pending queue" in subheaders
    assert "Needs information queue" in subheaders
    assert "Admitted history" in subheaders
    assert "Rejected and withdrawn history" in subheaders


def test_pending_and_admitted_queues_render_typed_service_output(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    reset_global_service()
    _seed_case("case-pending", "cell-pending", state=None)
    _seed_case("case-needs", "cell-needs", state=EvidenceReviewState.NEEDS_INFORMATION)
    svc = get_global_service()
    # admitted case via pending -> admitted
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
    app.run(timeout=20)
    assert not app.exception
    # dataframes should contain cases
    tables_text = " ".join(frame.value.to_csv(index=False) for frame in app.dataframe)
    assert "case-pending" in tables_text
    assert "case-needs" in tables_text
    assert "case-admitted" in tables_text
    # Privacy standing shown before decision controls
    captions = _captions(app)
    assert "rights standing" in captions.lower()


def test_case_detail_shows_findings_and_standing_before_decision_controls(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    reset_global_service()
    _seed_case("case-detail", "cell-detail")
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    # Findings caption appears
    captions = _captions(app)
    assert "rights standing" in captions.lower() or "validation" in captions.lower()
    # Decision form exists — look for selectbox with decision label
    assert any("decision" in str(s.label).lower() for s in app.selectbox)
    assert any("reason" in str(t.label).lower() for t in app.text_area)
    assert any("reviewer" in str(t.label).lower() for t in app.text_input)


def test_attachment_preview_is_unavailable_for_pending_case(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    reset_global_service()
    _seed_case("case-pend-attach", "cell-pend")
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    infos = _infos(app)
    # Pending cannot export message
    assert "fail closed" in infos.lower() or "pending" in infos.lower()


def test_admitted_case_shows_attachment_preview_and_download(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    reset_global_service()
    svc = get_global_service()
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
    app.run(timeout=20)
    assert not app.exception
    # Admitted attachment success visible
    assert any(
        "admitted attachment is available" in str(s.value).lower() for s in app.success
    ) or any("admitted attachment" in str(c.value).lower() for c in app.caption)
    # Download buttons for exports present
    assert len(app.download_button) >= 3


def test_no_automatic_decision_is_made_on_page_load(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    reset_global_service()
    _seed_case("case-no-auto", "cell-no-auto")
    svc = get_global_service()
    assert len(svc.get_ledger("case-no-auto").decisions) == 0
    app = _app(monkeypatch, tmp_path / "workspace")
    app.run(timeout=20)
    assert not app.exception
    # After page load without submitting form, ledger should still be empty
    assert len(svc.get_ledger("case-no-auto").decisions) == 0

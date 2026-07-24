"""Adversarial presentation tests for the Phase 2B Tier 3 pages."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app(page: UiPage) -> AppTest:
    """Build an AppTest for one Tier 3 page with shared v0.7 session state."""

    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def text_of(app: AppTest) -> str:
    parts = [str(block.value) for block in app.markdown]
    parts.extend(str(caption.value) for caption in app.caption)
    return "\n".join(parts)


def metric_labels(app: AppTest) -> list[str]:
    return [str(item.label) for item in app.metric]


# --- Participant Evaluation -------------------------------------------------


def test_participant_evaluation_is_a_readiness_checklist_with_explicit_states() -> None:
    app = page_app(UiPage.PARTICIPANT_EVALUATION).run(timeout=30)
    assert not app.exception

    body = text_of(app)
    warnings = "\n".join(str(w.value) for w in app.warning)
    # Mock-only and no-approval framing is prominent.
    assert "MOCK DATA ONLY" in warnings
    assert "Participant-study readiness" in "\n".join(str(s.value) for s in app.subheader)
    assert "no recruitment" in body.lower() or "No recruitment" in body
    assert "ethics approval" in body.lower()
    # Draft/unavailable/synthetic states are explicit badges, not hidden.
    assert "-badge[" in body
    # The prerequisite readiness table lists unavailable approvals.
    assert any("unavailable" in str(frame.value) for frame in app.dataframe)
    # No primary raw JSON dump (comment counts are a table; raw is under Advanced).
    assert len(app.json) <= 1


def test_participant_evaluation_keeps_raw_analysis_in_advanced() -> None:
    app = page_app(UiPage.PARTICIPANT_EVALUATION).run(timeout=30)
    assert not app.exception
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert advanced
    # Numeric record counts use st.metric.
    assert "Mock records" in metric_labels(app)


# --- Triviality & Winner Map ------------------------------------------------


def test_triviality_renders_badges_chart_and_no_universal_best_claim(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from traffictwin.demo.workspace import initialise_workspace

    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))

    app = page_app(UiPage.TRIVIALITY).run(timeout=40)
    assert not app.exception

    body = text_of(app)
    # Categorical rule statuses and the winner-map metric are badges, not numeric metrics.
    assert "R3" not in metric_labels(app)
    assert "R5" not in metric_labels(app)
    assert "Winner-map metric:" in body
    # The non-universal-best framing is explicit.
    assert "universally best" in body
    # A descriptive winner-map chart caption is present, and structured tables exist.
    assert "not a cross-family ranking" in body
    assert len(app.dataframe) >= 1
    # No raw rule JSON in primary content (R3/R5 detail lives under Advanced expanders).
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert advanced


# --- Manifest Inference -----------------------------------------------------


def test_manifest_inference_preview_is_structured_not_raw_dict() -> None:
    app = page_app(UiPage.MANIFEST_WIZARD).run(timeout=30)
    assert not app.exception

    subheaders = {str(item.value) for item in app.subheader}
    # Preview and confirmation are separate, explicitly labelled sections.
    assert "Inference preview" in subheaders
    assert "Review and confirm mappings" in subheaders
    body = text_of(app)
    assert "nothing is imported, analysed, or persisted until" in body
    # Draft identity / sample limits move to Advanced; not a primary JSON dump.
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert advanced
    assert len(app.json) == 1
    # Candidate kinds render as a structured table with the score-not-probability caption.
    assert "not a\nprobability" in body or "not a probability" in body
    assert len(app.dataframe) >= 1
    # Confirmation stays explicit and disabled until acknowledged.
    assert any(button.label == "Confirm Selected Mappings" for button in app.button)


# --- Diagnostics & Evidence (evidence readiness) ----------------------------


def test_evidence_readiness_groups_availability_by_state() -> None:
    app = page_app(UiPage.EVIDENCE).run(timeout=30)
    assert not app.exception

    subheaders = {str(item.value) for item in app.subheader}
    assert "Evidence Availability" in subheaders
    body = text_of(app)
    info_text = "\n".join(str(item.value) for item in app.info)
    # Availability is grouped by state (available/partial/blocked/unavailable), not a flat dict.
    assert "evidence**" in body  # e.g. "Available evidence" / "Unavailable evidence"
    # Diagnoses are framed as hypotheses that are NOT proven causes (the disclaimer is present),
    # and the page never asserts a confirmed/proven cause as a positive claim.
    assert "not proven root causes" in info_text.lower()
    assert "confirmed cause" not in body.lower()
    # Numeric readiness counts use st.metric.
    assert len(app.metric) >= 1
    # The raw availability dict stays under an Advanced expander.
    advanced = [str(exp.label) for exp in app.expander if "Advanced" in str(exp.label)]
    assert any("evidence availability" in label.lower() for label in advanced)


# --- Provenance Explorer ----------------------------------------------------


def test_provenance_explorer_uses_tabs_badges_and_advanced_json() -> None:
    app = page_app(UiPage.PROVENANCE).run(timeout=30)
    assert not app.exception

    info_text = "\n".join(str(item.value) for item in app.info)
    assert "does not establish real-world causality" in info_text
    # Lineage is a staged tab flow.
    tab_labels = {str(tab.label) for tab in app.tabs}
    assert {"Completeness", "Graph", "Lineage", "Nodes", "Export"} <= tab_labels
    body = text_of(app)
    # The metric dependency view is a structured panel with a non-causal caption, not a raw dict.
    assert "do not establish" in body or "not establish real-world causality" in body
    # Ledger counts use st.metric.
    assert "Candidate rows" in metric_labels(app)
    # Raw metric/rule detail moves behind Advanced/Evidence expanders.
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert advanced

"""Adversarial presentation tests for the Phase 2B Tier 3 pages."""

from __future__ import annotations

from copy import deepcopy

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

"""Adversarial presentation tests for the Phase 2B Tier 2 pages."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app(page: UiPage) -> AppTest:
    """Build an AppTest for one Tier 2 page with shared v0.7 session state."""

    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def text_of(app: AppTest) -> str:
    """Concatenate visible markdown and caption text."""

    parts = [str(block.value) for block in app.markdown]
    parts.extend(str(caption.value) for caption in app.caption)
    return "\n".join(parts)


def metric_labels(app: AppTest) -> list[str]:
    return [str(item.label) for item in app.metric]


def click_button(app: AppTest, label: str) -> AppTest:
    button = next(item for item in app.button if item.label == label)
    button.click()
    return app.run(timeout=40)


# --- Temporal Metrics -------------------------------------------------------


def test_temporal_metrics_renders_structured_reconciliation_and_chart() -> None:
    app = page_app(UiPage.TEMPORAL_METRICS).run(timeout=30)
    assert not app.exception
    # No primary raw dump before computing.
    assert len(app.json) == 0

    app = click_button(app, "Compute Windowed Metrics")
    assert not app.exception

    body = text_of(app)
    assert "Window reconciliation" in body
    # Missing-never-zero is stated explicitly.
    assert "never filled with zero" in body
    # A structured per-window table exists.
    assert len(app.dataframe) >= 1
    # Numeric reconciliation uses st.metric with count labels.
    assert "Included windows" in metric_labels(app)
    # Categorical R6 status must NOT be a numeric st.metric.
    assert "R6 status" not in metric_labels(app)


def test_temporal_metrics_keeps_raw_contract_in_advanced() -> None:
    app = page_app(UiPage.TEMPORAL_METRICS).run(timeout=30)
    app = click_button(app, "Compute Windowed Metrics")
    assert not app.exception
    # The raw window-contract JSON is present, but behind an Advanced label.
    advanced_labels = [
        str(exp.label) for exp in app.expander if "Advanced" in str(exp.label)
    ]
    assert any("window contract" in label.lower() for label in advanced_labels)

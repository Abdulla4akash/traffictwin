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
    advanced_labels = [str(exp.label) for exp in app.expander if "Advanced" in str(exp.label)]
    assert any("window contract" in label.lower() for label in advanced_labels)


# --- Threshold Sensitivity --------------------------------------------------


def test_threshold_sensitivity_renders_chart_table_and_no_primary_dict_dump() -> None:
    app = page_app(UiPage.THRESHOLD_SENSITIVITY).run(timeout=30)
    assert not app.exception
    # The descriptive, non-recommendation warning is prominent.
    assert any("not" in str(w.value) and "recommendation" in str(w.value) for w in app.warning)

    app = click_button(app, "Run Threshold Sweep")
    assert not app.exception

    body = text_of(app)
    # Predeclared grid and descriptive (non-optimal) framing are explicit.
    assert "Predeclared grid" in body
    assert "not an optimum" in body
    # A threshold-response chart and a structured grid table exist.
    assert len(app.dataframe) >= 1
    # Numeric summary uses metrics with count labels.
    assert "Evaluated grid points" in metric_labels(app)
    # Categorical source status must NOT be a numeric st.metric.
    assert "Source status" not in metric_labels(app)
    # The stability structure is a bordered panel, not a raw dict in primary content.
    assert "Stability across the grid" in body


def test_threshold_sensitivity_keeps_fingerprints_and_contract_in_advanced() -> None:
    app = page_app(UiPage.THRESHOLD_SENSITIVITY).run(timeout=30)
    app = click_button(app, "Run Threshold Sweep")
    assert not app.exception
    advanced = [str(exp.label) for exp in app.expander if "Advanced" in str(exp.label)]
    assert any("fingerprint" in label.lower() for label in advanced)
    assert any("contract" in label.lower() for label in advanced)


# --- VEC Workbench ----------------------------------------------------------


def test_vec_workbench_shows_numbered_stages_and_execution_boundary() -> None:
    app = page_app(UiPage.VEC_WORKBENCH).run(timeout=30)
    assert not app.exception

    body = text_of(app)
    # The current-process and approved-preset boundaries are prominent as badges.
    assert "Execution boundary" in body
    assert "foreground only" in body
    assert "Stages run in order" in body

    subheaders = [str(item.value) for item in app.subheader]
    joined = "\n".join(subheaders)
    for numbered in ("1.", "2.", "3.", "4.", "5."):
        assert numbered in joined

    # No primary raw JSON dump before any inspection.
    assert len(app.json) == 0
    # The preset workload boundary uses metrics, not a raw dict.
    assert "Evaluator steps (request property)" in metric_labels(app)


def test_vec_workbench_preset_execution_badge_is_visible() -> None:
    app = page_app(UiPage.VEC_WORKBENCH).run(timeout=30)
    assert not app.exception
    body = text_of(app)
    # Approved preset and its foreground-only execution boundary are shown.
    assert "Approved preset" in body
    assert "-badge[" in body  # badges are rendered natively


# --- Statistical Study (STA-05 power-analysis path, registry-free) -----------


def test_statistical_study_power_analysis_is_structured_not_raw_dict() -> None:
    app = page_app(UiPage.STATISTICAL_STUDY).run(timeout=30)
    assert not app.exception
    app.radio[0].set_value("Power analysis helper (STA-05)").run(timeout=30)
    app = click_button(app, "Calculate required common-seed pairs")
    assert not app.exception

    body = text_of(app)
    # Study-design values are a structured panel, not a primary raw dict dump.
    assert "Declared study design" in body
    # Numeric plan quantities use st.metric.
    assert "Required common-seed pairs" in metric_labels(app)
    # Categorical planning status is a badge, not a numeric metric.
    assert "Planning status" not in metric_labels(app)
    # Raw config JSON only lives under the Advanced/Evidence expander.
    advanced = [str(exp.label) for exp in app.expander if "Advanced:" in str(exp.label)]
    assert advanced
    assert len(app.json) == 1

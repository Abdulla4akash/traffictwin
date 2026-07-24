"""Adversarial presentation tests for the Phase 2B Tier 4 analysis-evidence pages."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app(page: UiPage) -> AppTest:
    """Build an AppTest for one Tier 4 page with shared v0.7 session state."""

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


def subheaders(app: AppTest) -> set[str]:
    return {str(item.value) for item in app.subheader}


# --- Energy Evidence --------------------------------------------------------


def test_energy_evidence_is_coverage_first_with_family_states() -> None:
    app = page_app(UiPage.ENERGY).run(timeout=40)
    assert not app.exception

    labels = metric_labels(app)
    # Coverage-first KPI row uses numeric-with-units metrics.
    assert "Available (metrics)" in labels
    assert "Completed-task coverage (%)" in labels
    # Every energy card carries an explicit unit.
    assert "Observed-task energy (J)" in labels
    assert "Completed-task energy (J)" in labels
    assert "Energy-delay product (J·ms)" in labels

    body = text_of(app)
    # Families are separated by evidence state, with badges rather than a flat dump.
    assert "Energy Families By Evidence State" in subheaders(app)
    assert "-badge[" in body
    # Efficiency/superiority is explicitly never inferred from a lower energy value.
    assert "efficiency" in body.lower()
    assert "superior" in body.lower()
    # The Randy/TOS physical-energy limitation stays visible.
    assert "Randy/TOS" in body
    # The categorical R8 status is a badge, not a numeric st.metric.
    assert "R8 status" not in labels
    assert "R8 status:" in body


def test_energy_evidence_keeps_r8_raw_in_advanced() -> None:
    app = page_app(UiPage.ENERGY).run(timeout=40)
    assert not app.exception
    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert any("R8" in label for label in advanced)
    # The numeric observed energy stays a units-labelled metric.
    assert "Observed completed-task energy (J/task)" in metric_labels(app)
    # Any raw R8 dict/JSON is confined to the Advanced/Evidence expander, not primary content.
    assert advanced

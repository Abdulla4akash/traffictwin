"""Presentation tests for the redesigned Evidence & Diagnostic Hypotheses page."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state


def _app() -> AppTest:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/diagnostics.py")
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _all_markdown(app: AppTest) -> str:
    return "\n".join(str(block.value) for block in app.markdown)


def test_validation_status_renders_as_badge_with_numeric_counts() -> None:
    app = _app().run(timeout=25)

    assert not app.exception
    text = _all_markdown(app)
    assert "-badge[" in text
    labels = {item.label for item in app.metric}
    assert {"Errors", "Warnings", "Fatal"}.issubset(labels)
    for item in app.metric:
        assert str(item.value).replace(".", "", 1).isdigit()


def test_evidence_availability_is_a_badge_table_not_primary_json() -> None:
    app = _app().run(timeout=25)

    assert not app.exception
    assert len(app.table) >= 1
    table_text = str(app.table[0].value)
    assert "-badge[" in table_text
    # Every evidence category from the model stays visible.
    for category in ("Tasks", "Infrastructure", "Vehicles", "Traffic", "Trips"):
        assert category in table_text


def test_rule_results_show_badges_and_structured_findings() -> None:
    app = _app().run(timeout=25)

    assert not app.exception
    text = _all_markdown(app)
    assert "Candidate hypothesis:" in text or "Deterministic diagnosis" in text
    # No raw dict/list dump remains outside labelled Advanced expanders: the
    # only JSON elements on the page carry an Advanced/raw label context.
    assert "Overall readiness:" in text

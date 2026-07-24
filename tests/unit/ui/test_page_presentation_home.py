"""Presentation tests for the redesigned Home page."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.state import default_session_state

HERO = "Model a traffic scenario. Run or import it. Compare the evidence."


def _home_app(*, v07_active: bool) -> AppTest:
    app = AppTest.from_file("src/traffictwin/ui/app_pages/home.py")
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = v07_active
    return app


def test_v07_home_leads_with_a_single_task_oriented_title() -> None:
    app = _home_app(v07_active=True).run(timeout=25)

    assert not app.exception
    assert any(HERO in item.value for item in app.title)
    # No stacked title + header pair remains.
    assert not any(HERO in item.value for item in app.header)


def test_v07_home_shows_evidence_state_as_badge_not_text_metric() -> None:
    app = _home_app(v07_active=True).run(timeout=25)

    assert not app.exception
    assert not any(item.label == "Manchester evidence" for item in app.metric)
    assert any("Manchester evidence" in caption.value for caption in app.caption)
    # Remaining KPI metrics hold numeric values only.
    for item in app.metric:
        assert str(item.value).replace(".", "", 1).isdigit()


def test_legacy_home_keeps_information_without_raw_list_dump() -> None:
    app = _home_app(v07_active=False).run(timeout=25)

    assert not app.exception
    assert len(app.json) == 0
    text = "\n".join(str(block.value) for block in app.markdown)
    assert "Direct simulator launch is unavailable" in text
    assert "Implementation phase:" in text
    # String facts no longer render inside st.metric cards.
    for item in app.metric:
        assert str(item.value).replace(".", "", 1).isdigit()

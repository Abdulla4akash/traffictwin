"""UI tests for Event-to-Scenario Bridge page."""

from __future__ import annotations

from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

_ENV_CLEAR = [
    "TRAFFICTWIN_WORKSPACE_PATH",
    "TRAFFICTWIN_REGISTRY_PATH",
    "TRAFFICTWIN_TOS_DATA_PATH",
    "TRAFFICTWIN_FIXTURE_PATH",
    "TRAFFICTWIN_RANDY_PACK_PATH",
    "TRAFFICTWIN_BODS_BOUNDING_BOX",
    "BODS_API_KEY",
    "NATIONAL_HIGHWAYS_API_KEY",
]


def _run_page(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    for key in _ENV_CLEAR:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_file("src/traffictwin/ui/app_pages/event_scenario_bridge.py")
    from traffictwin.ui.state import default_session_state

    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    for k, v in state.items():
        app.session_state[k] = v  # type: ignore[index]
    app.run(timeout=30)
    return app


def test_event_scenario_bridge_page_has_exactly_one_title(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    assert len(app.title) == 1
    assert app.title[0].value == "Event-to-Scenario Bridge"


def test_event_scenario_bridge_page_shows_evidence_boundary_before_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Evidence boundary must appear before any results: warning or caption with unexecuted
    all_text = " ".join(
        [c.value for c in app.caption]
        + [w.value for w in app.warning]
        + [i.value for i in app.info]
    ).lower()
    assert "unexecuted" in all_text
    assert (
        "does not run sumo" in all_text
        or "does not represent" in all_text
        or "not represent" in all_text
    )


def test_event_scenario_bridge_page_preview_and_export(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Click Preview bridge handoffs
    preview_btn = next(b for b in app.button if b.label == "Preview bridge handoffs")
    preview_btn.click().run(timeout=30)
    assert not app.exception
    # After preview, should have handoff preview subheader and download buttons
    subheaders = [s.value for s in app.subheader]
    assert any("Bridge handoff preview" in s for s in subheaders)
    # Download buttons
    labels = [b.label for b in app.download_button]
    assert any("Download bridge JSON" in lbl for lbl in labels)
    assert any("Download handoff summary CSV" in lbl for lbl in labels)


def test_event_scenario_bridge_page_no_run_button(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    labels = [b.label for b in app.button]
    for lbl in labels:
        assert "run" not in lbl.lower() or "preview" in lbl.lower(), f"Unexpected Run button: {lbl}"


def test_event_scenario_bridge_page_has_useful_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Before preview, should not have handoff preview; empty state is the boundary text
    subheaders_before = [s.value for s in app.subheader]
    assert not any("Bridge handoff preview" in s for s in subheaders_before)
    # But should have the form headers
    assert any("Declare event" in s for s in subheaders_before)


def test_event_scenario_bridge_page_widget_keys_unique(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _run_page(monkeypatch)
    assert not app.exception
    # Collect widget keys from session stateKeys — run twice to ensure no duplicate key error
    app.run(timeout=30)
    assert not app.exception

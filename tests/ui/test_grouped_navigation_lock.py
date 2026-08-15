from __future__ import annotations

from importlib import import_module

import pytest

from traffictwin.ui.labels import UiPage


def test_supported_launch_lock_overrides_stale_legacy_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRAFFICTWIN_V07_NAVIGATION", "legacy")
    monkeypatch.setenv("TRAFFICTWIN_GROUPED_NAVIGATION_LOCK", "1")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]

    app = app_test.from_file("src/traffictwin/ui/app.py").run(timeout=20)

    assert not app.exception
    assert not app.radio
    assert app.session_state["_v07_navigation_active"] is True
    assert app.session_state["_active_ui_page"] is UiPage.HOME

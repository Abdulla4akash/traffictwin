"""Cross-page session-state evidence for the v0.7 page set (UX-01).

Streamlit keeps one session-state dict per user session and re-executes the
selected page script on every switch. These tests model that exact contract:
each page runs as its direct script over the carried shared state, so a
selection made on one page must stay authoritative on pages in other
navigation groups, and no page may silently reset shared keys. The legacy
compatibility router is exercised end-to-end through its real radio control.
This is automated candidate evidence only and does not accept `UX-01`.
"""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state

_APP_ROOT = "src/traffictwin/ui/app.py"
_VARIATION_BUNDLE = "tests/fixtures/bundles/variation_valid"
_SHARED_KEYS = tuple(default_session_state()) + ("_v07_navigation_active",)


def _run_page(page: UiPage, state: dict[str, object], *, timeout: int = 25) -> AppTest:
    """Run one direct page script over the carried shared session state."""

    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in state.items():
        app.session_state[key] = value
    app.run(timeout=timeout)
    assert not app.exception
    return app


def _carried_state(app: AppTest) -> dict[str, object]:
    """Capture the shared per-session dict exactly as a page switch would."""

    return {key: app.session_state[key] for key in _SHARED_KEYS}


def _initial_state() -> dict[str, object]:
    state = deepcopy(default_session_state())
    state["_v07_navigation_active"] = True
    return state


def test_bundle_selection_survives_group_navigation() -> None:
    # Build & run group: choose a different bundle on the import page.
    app = _run_page(UiPage.BUNDLE_IMPORT, _initial_state())
    bundle_input = app.text_input[0]
    assert "Bundle" in bundle_input.label
    bundle_input.set_value(_VARIATION_BUNDLE)
    app.run(timeout=25)
    assert not app.exception
    assert str(app.session_state["selected_bundle_path"]) == _VARIATION_BUNDLE

    # Analyse group: the selection stays authoritative without re-selection.
    app = _run_page(UiPage.RUN_OVERVIEW, _carried_state(app))
    assert str(app.session_state["selected_bundle_path"]) == _VARIATION_BUNDLE
    captions = "\n".join(str(item.value) for item in app.caption)
    assert _VARIATION_BUNDLE in captions


def test_analysis_state_remains_available_after_switching_groups() -> None:
    app = _run_page(UiPage.RUN_OVERVIEW, _initial_state())
    assert app.session_state["latest_evidence_pack"] is not None
    assert app.session_state["latest_metric_collection"] is not None

    # Evidence group: the computed evidence pack survives the group switch.
    app = _run_page(UiPage.EVIDENCE, _carried_state(app))
    assert app.session_state["latest_evidence_pack"] is not None

    # Advanced group: shared state also survives a switch into a third group.
    app = _run_page(UiPage.ABOUT, _carried_state(app), timeout=20)
    assert str(app.session_state["selected_bundle_path"]).endswith("baseline_valid")
    assert app.session_state["latest_evidence_pack"] is not None


def test_no_page_resets_the_shared_bundle_selection() -> None:
    """Every analysis-consuming page preserves an explicit prior selection."""

    state = _initial_state()
    state["selected_bundle_path"] = _VARIATION_BUNDLE
    for page in (
        UiPage.RUN_OVERVIEW,
        UiPage.TEMPORAL_METRICS,
        UiPage.EVIDENCE,
        UiPage.STATISTICAL_STUDY,
        UiPage.PROVENANCE,
        UiPage.SEARCH,
        UiPage.ABOUT,
    ):
        app = _run_page(page, state)
        assert str(app.session_state["selected_bundle_path"]) == _VARIATION_BUNDLE, page
        state = _carried_state(app)


def test_legacy_compatibility_router_preserves_cross_page_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRAFFICTWIN_V07_NAVIGATION", "legacy")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(_APP_ROOT)
    app.run(timeout=20)
    assert not app.exception

    app.radio[0].set_value(UiPage.BUNDLE_IMPORT.value)
    app.run(timeout=25)
    assert not app.exception
    bundle_input = app.text_input[0]
    assert "Bundle" in bundle_input.label
    bundle_input.set_value(_VARIATION_BUNDLE)
    app.run(timeout=25)
    assert not app.exception
    assert str(app.session_state["selected_bundle_path"]) == _VARIATION_BUNDLE

    app.radio[0].set_value(UiPage.RUN_OVERVIEW.value)
    app.run(timeout=25)
    assert not app.exception
    assert str(app.session_state["selected_bundle_path"]) == _VARIATION_BUNDLE
    captions = "\n".join(str(item.value) for item in app.caption)
    assert _VARIATION_BUNDLE in captions

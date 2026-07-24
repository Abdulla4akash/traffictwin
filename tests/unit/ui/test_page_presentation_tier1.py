"""Presentation tests for the Phase 2B Tier 1 pages."""

from __future__ import annotations

from copy import deepcopy

from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config

FULL_BASELINE_FINGERPRINT_PREFIX = "b778c4c3"


def _page_app(page: UiPage) -> AppTest:
    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _text(app: AppTest) -> str:
    parts = [str(block.value) for block in app.markdown]
    parts.extend(str(caption.value) for caption in app.caption)
    return "\n".join(parts)


def _code_text(app: AppTest) -> str:
    return "\n".join(str(block.value) for block in app.code)


def test_source_caption_truncates_fingerprint_with_full_value_advanced() -> None:
    app = _page_app(UiPage.RUN_OVERVIEW).run(timeout=25)

    assert not app.exception
    captions = "\n".join(str(caption.value) for caption in app.caption)
    assert f"{FULL_BASELINE_FINGERPRINT_PREFIX}" in captions
    assert "…" in captions
    # No caption carries a full 64-hex fingerprint any more.
    for caption in app.caption:
        for token in str(caption.value).replace("`", " ").split():
            assert not (len(token) == 64 and all(c in "0123456789abcdef" for c in token))
    # The complete value stays reachable in the Advanced identity expander.
    assert "fingerprint:" in _code_text(app)


def test_sumo_import_page_has_no_primary_json_and_uses_badges() -> None:
    app = _page_app(UiPage.SUMO_IMPORT).run(timeout=30)

    assert not app.exception
    assert len(app.json) == 0
    text = _text(app)
    assert "-badge[" in text
    assert "SUMO runtime" in text
    assert "Simulated window:" in text
    # Source-contract identifiers moved to an Advanced code block.
    assert "bundle_id:" in _code_text(app)
    assert any(button.label == "Import SUMO Results" for button in app.button)


def test_bundle_import_page_renders_badge_evidence_table() -> None:
    app = _page_app(UiPage.BUNDLE_IMPORT).run(timeout=30)

    assert not app.exception
    assert len(app.table) >= 1
    assert "-badge[" in str(app.table[0].value)
    assert "Environment:" in _text(app)
    assert "run_id:" in _code_text(app)
    # Raw JSON payloads exist only under labelled Advanced expanders.
    assert len(app.json) == 2


def test_compare_page_renders_structured_compatibility_and_tables() -> None:
    app = _page_app(UiPage.COMPARE).run(timeout=30)

    assert not app.exception
    text = _text(app)
    assert "Same experiment:" in text
    assert "Same random seed:" in text
    assert len(app.json) == 1  # advanced compatibility context only
    assert len(app.dataframe) >= 2
    assert any(item.label == "Baseline eligible rows" for item in app.metric)
    for item in app.metric:
        value = str(item.value)
        assert value == "Unavailable" or value.replace(".", "", 1).replace("%", "").isdigit()


def test_about_page_moves_contracts_to_advanced_expanders() -> None:
    app = _page_app(UiPage.ABOUT).run(timeout=25)

    assert not app.exception
    text = _text(app)
    assert "Trusted local metric plugins register" in text
    assert "closed grammar" in text
    assert len(app.json) == 2  # both raw contracts live in Advanced expanders


def test_experiment_manager_renders_without_raw_list_dump() -> None:
    app = _page_app(UiPage.EXPERIMENT_MANAGER).run(timeout=30)

    assert not app.exception
    assert len(app.json) == 0
    for item in app.metric:
        assert str(item.value).replace(".", "", 1).isdigit()


def test_tos_import_page_smokes_without_package() -> None:
    app = _page_app(UiPage.TOS_DATA).run(timeout=30)

    assert not app.exception
    assert len(app.json) == 0

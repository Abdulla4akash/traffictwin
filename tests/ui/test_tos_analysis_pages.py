from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

import pytest
from tests.tos_helpers import write_tos_package

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


@pytest.mark.parametrize(
    "page",
    ["TOS Results", "TOS Mobility & RSU Replay", "TOS Training & Audit"],
)
def test_tos_analysis_pages_render_from_selected_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    page: str,
) -> None:
    package = write_tos_package(tmp_path / "tos")
    monkeypatch.setenv("TRAFFICTWIN_TOS_DATA_PATH", str(package))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage(page))}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=15)

    assert not app.exception
    assert any("IMPORTED SIMULATION" in item.value for item in app.markdown)


def test_tos_results_page_exposes_paired_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = write_tos_package(tmp_path / "tos")
    monkeypatch.setenv("TRAFFICTWIN_TOS_DATA_PATH", str(package))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.TOS_RESULTS)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=15)

    assert not app.exception
    assert any(item.value == "Paired campaign comparison" for item in app.subheader)
    assert any("does not establish" in item.value for item in app.info)

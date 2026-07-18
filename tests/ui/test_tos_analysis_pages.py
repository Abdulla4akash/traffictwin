from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from tests.tos_helpers import write_tos_package


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
    app = app_test.from_file("src/traffictwin/ui/app.py")

    app.run(timeout=10)
    app.radio[0].set_value(page).run(timeout=15)

    assert not app.exception
    assert any("IMPORTED SIMULATION" in item.value for item in app.markdown)


def test_tos_results_page_exposes_paired_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = write_tos_package(tmp_path / "tos")
    monkeypatch.setenv("TRAFFICTWIN_TOS_DATA_PATH", str(package))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")

    app.run(timeout=10)
    app.radio[0].set_value("TOS Results").run(timeout=15)

    assert not app.exception
    assert any(item.value == "Paired Campaign Comparison" for item in app.subheader)
    assert any("does not establish" in item.value for item in app.info)

from __future__ import annotations

from importlib import import_module

from traffictwin.experiments.power_analysis import PowerAnalysis, PowerAnalysisStatus
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for


def test_streamlit_statistical_page_runs_power_analysis() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    # v0.7 grouped navigation is the default: route to the direct Statistical Study page rather
    # than the removed legacy sidebar radio.
    app.switch_page(page_script_for(UiPage.STATISTICAL_STUDY)).run(timeout=10)
    next(radio for radio in app.radio if radio.label == "Study type").set_value(
        "Power analysis helper (STA-05)"
    ).run(timeout=10)
    next(
        button for button in app.button if button.label == "Calculate required common-seed pairs"
    ).click().run(timeout=10)

    result = app.session_state["power_analysis"]
    assert not app.exception
    assert isinstance(result, PowerAnalysis)
    assert result.status is PowerAnalysisStatus.AVAILABLE
    assert result.calculation.required_common_seed_replicates == 8
    assert any(
        heading.value == "Prospective paired common-seed power plan" for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download PowerAnalysis JSON",
        "Download PowerAnalysis Markdown",
        "Download PowerAnalysis CSV",
    }

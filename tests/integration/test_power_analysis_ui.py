from __future__ import annotations

from importlib import import_module

from traffictwin.experiments.power_analysis import PowerAnalysis, PowerAnalysisStatus


def test_streamlit_statistical_page_runs_power_analysis() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Statistical Study").run(timeout=10)
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
        heading.value == "Prospective Paired Common-Seed Power Plan" for heading in app.subheader
    )
    assert {button.label for button in app.download_button} >= {
        "Download PowerAnalysis JSON",
        "Download PowerAnalysis Markdown",
        "Download PowerAnalysis CSV",
    }

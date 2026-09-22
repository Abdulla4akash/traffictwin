"""Study selection must retain the actual follow-up effects and reused controls."""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest

from traffictwin.integration.dissertation_results import ResultsImportError


def _app() -> Any:  # noqa: ANN401 — Streamlit AppTest is dynamically imported
    return (
        vars(import_module("streamlit.testing.v1"))["AppTest"]
        .from_file("src/traffictwin/ui/app_pages/experimental_results.py")
        .run()
    )


def test_default_latest_study_shows_actual_two_choice_results() -> None:
    app = _app()
    assert not app.exception and not app.error
    assert [m.value for m in app.metric] == ["72", "32", "8", "3"]
    comparisons = app.dataframe[0].value.to_csv(index=False)
    for value in ("+0.649", "[+0.517, +0.781]", "+3.488", "-0.018"):
        assert value in comparisons
    table = app.dataframe[2].value
    assert len(table) == 32
    assert sum(table["Run source"] == "Reused original-speed control") == 24
    captions = " ".join(str(item.value) for item in app.caption)
    for value in (
        "15 September",
        "same eight",
        "all ten",
        "not statistical replicates",
        "Raw simulation arrays are not rechecked",
        "not evidence of equivalence",
    ):
        assert value in captions


@pytest.mark.parametrize(
    ("study", "expected"),
    [
        ("08_half_speed", ("+4.215", "-3.396", "+0.824", "+0.193", "[+0.034, +0.352]")),
        ("09_second_actor", ("+3.539", "-3.440", "+0.550", "[+0.432, +0.668]")),
    ],
)
def test_experiment_selector_displays_saved_comparisons(
    study: str, expected: tuple[str, ...]
) -> None:
    app = _app()
    app.selectbox(key="followup_experiment").select(study).run()
    assert not app.exception and not app.error
    table = app.dataframe[0].value.to_csv(index=False)
    for value in expected:
        assert value in table
    assert len(app.dataframe[2].value) == 32
    assert set(app.dataframe[2].value["Run source"]) == {"New follow-up"}
    if study == "08_half_speed":
        assert "not another policy" in app.info[0].value
        assert len(app.dataframe[3].value) == 16


def test_filter_and_original_study_switch_do_not_mix_results() -> None:
    app = _app()
    comparison = app.dataframe[0].value.to_csv(index=False)
    app.selectbox(key="followup_block").select("3").run()
    assert len(app.dataframe[2].value) == 4
    assert set(app.dataframe[2].value["Fleet seed"]) == {103}
    assert app.dataframe[0].value.to_csv(index=False) == comparison
    app.selectbox(key="experimental_results_study").select(
        "Original confirmation · 8 September 2026"
    ).run()
    assert [m.value for m in app.metric] == ["8", "32", "4", "32"]
    assert "+4.137" in app.dataframe[0].value.to_csv(index=False)
    app.selectbox(key="experimental_results_study").select(
        "Latest follow-ups · 15 September 2026"
    ).run()
    assert not app.exception
    assert app.dataframe[0].value.to_csv(index=False) == comparison


def test_missing_latest_evidence_drops_previous_results(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app()
    assert app.metric

    def unavailable() -> None:
        raise ResultsImportError("Changed follow-up source evidence")

    monkeypatch.setattr(
        "traffictwin.ui.components.followup_results.load_followup_results", unavailable
    )
    app.run()
    assert not app.exception
    assert "Changed follow-up source evidence" in app.error[0].value
    assert not app.metric and not app.dataframe

"""Real-study UI coverage: paired units, filters, downloads, and refusal states."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pytest import MonkeyPatch

from traffictwin.integration.dissertation_results import ResultsImportError
from traffictwin.ui.navigation_v07 import (
    EXPERIMENTAL_RESULTS_PAGE_SPEC,
    v07_navigation_pages,
    validate_v07_page_specs,
)

SCRIPT = "src/traffictwin/ui/app_pages/experimental_results.py"


def _app() -> Any:  # noqa: ANN401 - Streamlit AppTest is dynamically imported
    app = vars(import_module("streamlit.testing.v1"))["AppTest"].from_file(SCRIPT).run()
    return (
        app.selectbox(key="experimental_results_study")
        .select("Original confirmation · 8 September 2026")
        .run()
    )


def test_builtin_study_shows_original_effects_and_truth_boundaries() -> None:
    app = _app()
    assert not app.exception
    assert [metric.value for metric in app.metric] == ["8", "32", "4", "32"]
    table = app.dataframe[0].value.to_csv(index=False)
    for expected in ("+4.137", "-3.504", "+0.631", "[+0.511, +0.750]"):
        assert expected in table
    captions = " ".join(str(item.value) for item in app.caption)
    for expected in (
        "Workflow demonstration",
        "completed simulation evidence",
        "raw simulation arrays are not rechecked",
        "individual tasks are not statistical replicates",
        "Bonferroni simultaneous 95%",
        "results are not pooled",
    ):
        assert expected in captions
    assert len(app.dataframe[1].value) == 32


def test_block_filter_preserves_primary_analysis() -> None:
    app = _app()
    before = app.dataframe[0].value.to_csv(index=False)
    app.selectbox[1].select("3").run()
    assert not app.exception
    table = app.dataframe[1].value
    assert len(table) == 4
    assert set(table["Block"]) == {3}
    assert set(table["Fleet seed"]) == {103}
    assert set(table["Evaluator seed"]) == {203}
    assert app.dataframe[0].value.to_csv(index=False) == before


def test_empty_upload_hides_previous_builtin_results() -> None:
    app = _app()
    app.radio[0].set_value("Upload evidence ZIP").run()
    assert not app.exception
    assert not app.metric
    assert not app.dataframe
    assert "Choose the study evidence ZIP" in app.info[0].value


def test_directory_import_then_missing_file_refuses_without_stale_results(tmp_path: Path) -> None:
    from traffictwin.integration.dissertation_results import load_builtin_results

    for name, data in load_builtin_results().files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    app = _app()
    app.radio[0].set_value("Local evidence folder").run()
    assert not app.metric
    app.text_input[0].set_value(str(tmp_path)).run()
    assert not app.exception
    assert len(app.metric) == 4
    (tmp_path / "evidence/CELL_RESULTS.csv").unlink()
    app.run()
    assert not app.exception
    assert app.error
    assert "Evidence import refused" in app.error[0].value
    assert not app.dataframe
    assert not app.metric


def test_builtin_failure_does_not_render_results(monkeypatch: MonkeyPatch) -> None:
    def refuse() -> None:
        raise ResultsImportError("Changed source evidence")

    monkeypatch.setattr("traffictwin.ui.pages.experimental_results.load_builtin_results", refuse)
    app = _app()
    assert not app.exception
    assert "Changed source evidence" in app.error[0].value
    assert not app.metric


def test_results_route_is_additive_and_first_in_results_group(monkeypatch: MonkeyPatch) -> None:
    def page(_script: object, **kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(**kwargs)

    monkeypatch.setattr("traffictwin.ui.navigation_v07.st.Page", page)
    validate_v07_page_specs()
    pages = v07_navigation_pages()
    assert EXPERIMENTAL_RESULTS_PAGE_SPEC.url_path == "experimental-results"
    assert pages["Results"][0].title == "Experimental Results"  # type: ignore[attr-defined]
    assert (
        sum(
            page.title == "Experimental Results"  # type: ignore[attr-defined]
            for group in pages.values()
            for page in group
        )
        == 1
    )

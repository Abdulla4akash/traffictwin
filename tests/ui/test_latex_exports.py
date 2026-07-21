from __future__ import annotations

from importlib import import_module
from pathlib import Path

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)

from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study
from traffictwin.ui.services import ServiceError, generate_research_export_for_ui

BASELINE = Path("tests/fixtures/bundles/baseline_valid")


def test_ui_service_generates_metric_table_and_figure(tmp_path: Path) -> None:
    table = tmp_path / "metrics.tex"
    figure = tmp_path / "metrics.svg"

    receipt = generate_research_export_for_ui(
        "metrics",
        BASELINE,
        table,
        figure_output_path=figure,
    )

    assert not isinstance(receipt, ServiceError)
    assert [item.format for item in receipt.files] == ["tex", "svg"]
    assert table.exists()
    assert figure.exists()


def test_ui_service_generates_saved_statistical_study_and_reports_errors(
    tmp_path: Path,
) -> None:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    source = tmp_path / "study.json"
    source.write_text(study.model_dump_json(indent=2), encoding="utf-8")

    receipt = generate_research_export_for_ui(
        "statistical_study",
        source,
        tmp_path / "study.tex",
        figure_output_path=tmp_path / "study.pdf",
    )
    missing_pair = generate_research_export_for_ui(
        "comparison",
        BASELINE,
        tmp_path / "comparison.tex",
    )

    assert not isinstance(receipt, ServiceError)
    assert receipt.files[-1].format == "pdf"
    assert isinstance(missing_pair, ServiceError)
    assert "second bundle" in missing_pair.message


def test_reports_page_exposes_latex_and_static_figure_controls() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Reports").run(timeout=10)

    assert not app.exception
    assert any(title.value == "Reports" for title in app.title)
    assert any(
        item.label == "Research artifact" and "statistical_study" in item.options
        for item in app.selectbox
    )
    assert any(item.label == "Static figure" and "svg" in item.options for item in app.selectbox)
    assert any(button.label == "Generate LaTeX Research Export" for button in app.button)

    artifact = next(item for item in app.selectbox if item.label == "Research artifact")
    artifact.set_value("comparison").run(timeout=10)
    assert not app.exception
    table_outputs = [item for item in app.text_input if item.label == "LaTeX table output"]
    assert len(table_outputs) == 1
    assert table_outputs[0].value.endswith("research_comparison.tex")

    figure = next(item for item in app.selectbox if item.label == "Static figure")
    figure.set_value("pdf").run(timeout=10)
    assert not app.exception
    figure_outputs = [item for item in app.text_input if item.label == "Figure output"]
    assert len(figure_outputs) == 1
    assert figure_outputs[0].value.endswith("research_comparison.pdf")

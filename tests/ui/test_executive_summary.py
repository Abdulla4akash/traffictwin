from __future__ import annotations

from importlib import import_module
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from traffictwin.ui.services import (
    ServiceError,
    build_executive_summary_for_ui,
    regenerate_report_for_ui,
)

BASELINE = Path("tests/fixtures/bundles/baseline_valid")


def test_executive_summary_ui_service_returns_complete_downloads(tmp_path: Path) -> None:
    source = tmp_path / "baseline.json"
    generated = regenerate_report_for_ui("run", BASELINE, source)
    result = build_executive_summary_for_ui(source)

    assert not isinstance(generated, ServiceError)
    assert not isinstance(result, ServiceError)
    assert result.summary.availability.total_claims == 33
    assert len(result.summary.warnings) == 3
    assert '"contract_version": "executive-summary-v1"' in result.json_payload
    assert "Warnings - All Retained" in result.markdown_payload
    assert "Provenance links" in result.html_payload
    assert len(PdfReader(BytesIO(result.pdf_payload)).pages) == 1


def test_reports_page_exposes_executive_summary_controls() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Reports").run(timeout=10)

    assert not app.exception
    assert any(item.label == "Executive summary source report JSON" for item in app.text_input)
    assert any(button.label == "Generate One-page Executive Summary" for button in app.button)
    assert any("every warning and limitation" in item.value for item in app.info)

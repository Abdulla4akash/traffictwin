from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from traffictwin.reporting.diffing import ReportDiffClassification, StructuredReportDiffStatus
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    compare_structured_reports_for_ui,
    regenerate_report_for_ui,
)
from traffictwin.ui.state import default_session_state, load_ui_config

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")


def test_report_diff_ui_service_uses_saved_structured_payloads(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    variation_path = tmp_path / "variation.json"
    baseline = regenerate_report_for_ui("run", BASELINE, baseline_path)
    variation = regenerate_report_for_ui("run", VARIATION, variation_path)
    result = compare_structured_reports_for_ui(baseline_path, variation_path)

    assert not isinstance(baseline, ServiceError)
    assert not isinstance(variation, ServiceError)
    assert not isinstance(result, ServiceError)
    assert result.report.status is StructuredReportDiffStatus.AVAILABLE
    assert any(
        item.section == "Metrics" and item.classification is ReportDiffClassification.CHANGED
        for item in result.report.sections
    )
    assert '"status": "available"' in result.json_payload
    assert "rendered prose" in result.markdown_payload


def test_reports_page_exposes_structured_report_diff_controls() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.REPORTS)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=10)

    assert not app.exception
    assert any(item.label == "Baseline structured report JSON" for item in app.text_input)
    assert any(item.label == "Variation structured report JSON" for item in app.text_input)
    assert any(button.label == "Compare Structured Reports" for button in app.button)
    assert any(
        "typed metric, rule, and comparison claim snapshots" in item.value for item in app.info
    )

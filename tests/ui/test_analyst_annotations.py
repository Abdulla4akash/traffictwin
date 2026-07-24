from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    append_analyst_annotation_for_ui,
    list_analyst_annotations_for_ui,
    regenerate_report_for_ui,
    safe_import_bundle_for_ui,
)
from traffictwin.ui.state import default_session_state, load_ui_config

BASELINE = Path("tests/fixtures/bundles/baseline_valid")


def test_annotation_ui_services_append_history_and_render_report(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    imported = safe_import_bundle_for_ui(BASELINE, registry)
    appended = append_analyst_annotation_for_ui(
        registry,
        target_kind="run",
        target_id="run-baseline-001",
        author_label="Akash",
        note="Retain the synthetic-data limitation in the final discussion.",
        decision_label="accepted",
    )
    history = list_analyst_annotations_for_ui(
        registry,
        target_kind="run",
        target_id="run-baseline-001",
    )
    output = tmp_path / "report.html"
    generated = regenerate_report_for_ui(
        "run",
        BASELINE,
        output,
        annotation_registry_path=registry,
    )

    assert not isinstance(imported, ServiceError)
    assert not isinstance(appended, ServiceError)
    assert appended.sequence == 1
    assert not isinstance(history, ServiceError)
    assert history.annotations == [appended]
    assert not isinstance(generated, ServiceError)
    html = output.read_text(encoding="utf-8")
    assert "Analyst Annotations" in html
    assert "synthetic-data limitation" in html


def test_reports_page_exposes_append_only_annotation_controls() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.REPORTS)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=10)

    assert not app.exception
    assert any(
        item.label == "Annotation target type" and "research_report" in item.options
        for item in app.selectbox
    )
    assert any(item.label == "Analyst decision label" for item in app.selectbox)
    assert any(item.label == "Analyst note" for item in app.text_area)
    assert any(button.label == "Append Analyst Annotation" for button in app.button)
    assert any(
        item.label == "Include matching append-only analyst annotations" for item in app.checkbox
    )

from __future__ import annotations

from importlib import import_module
from pathlib import Path

from traffictwin.integration.sumo import SumoAnalysis
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import page_options
from traffictwin.ui.services import ServiceError, import_sumo_for_ui, validate_sumo_for_ui

FIXTURE = Path("tests/fixtures/sumo/square_public")


def test_sumo_page_and_services_expose_validated_import_only_analysis(tmp_path: Path) -> None:
    analysis = validate_sumo_for_ui(FIXTURE)

    assert not isinstance(analysis, ServiceError)
    assert isinstance(analysis, SumoAnalysis)
    assert analysis.validation.report.may_import
    assert analysis.metrics is not None
    assert UiPage.SUMO_IMPORT.value in page_options()
    imported = import_sumo_for_ui(FIXTURE, tmp_path / "registry.sqlite", analysis)
    assert not isinstance(imported, ServiceError)
    assert imported.created


def test_sumo_output_page_renders_public_fixture() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=15)
    app.radio[0].set_value(UiPage.SUMO_IMPORT.value).run(timeout=15)

    assert not app.exception
    assert any(title.value == UiPage.SUMO_IMPORT.value for title in app.title)
    assert any(button.label == "Import SUMO Results" for button in app.button)

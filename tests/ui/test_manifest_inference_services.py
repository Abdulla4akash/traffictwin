from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path

from traffictwin.ingestion.manifest_inference import (
    ConfirmationMode,
    FileSelection,
    ManifestInferenceSelections,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.services import (
    ServiceError,
    apply_manifest_inference_for_ui,
    confirm_manifest_inference_for_ui,
    infer_manifest_for_ui,
    manifest_file_fragment_for_ui,
)
from traffictwin.ui.state import default_session_state, load_ui_config

FIXTURE = Path("tests/fixtures/manifest_inference/value_patterns")


def test_manifest_inference_ui_services_keep_confirmation_explicit() -> None:
    draft = infer_manifest_for_ui(FIXTURE)

    assert not isinstance(draft, ServiceError)
    assert not draft.analysis_ready
    confirmed = confirm_manifest_inference_for_ui(
        draft,
        FIXTURE,
        confirmed_by="ui-test",
        selections=ManifestInferenceSelections(files={"external_tasks.csv": FileSelection()}),
    )

    assert not isinstance(confirmed, ServiceError)
    assert confirmed.confirmation_state is ConfirmationMode.ACCEPTED_SUGGESTIONS
    fragment = manifest_file_fragment_for_ui(confirmed)
    assert "external_tasks.csv" in fragment
    rendered = apply_manifest_inference_for_ui(confirmed, FIXTURE / "manifest-template.yaml")
    assert not isinstance(rendered, ServiceError)
    assert "canonicalisation:" in rendered
    assert "confirmation_state: accepted_suggestions" in rendered


def test_manifest_inference_page_renders_non_executable_draft() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(UiPage.MANIFEST_WIZARD)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    app.run(timeout=15)

    assert not app.exception
    assert any(title.value == UiPage.MANIFEST_WIZARD.value for title in app.title)
    assert any(button.label == "Confirm Selected Mappings" for button in app.button)
    assert any("Suggestions are deterministic drafts" in warning.value for warning in app.warning)

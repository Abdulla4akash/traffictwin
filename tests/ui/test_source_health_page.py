"""AppTest coverage for the additive read-only Source Health route."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.release.durable_workspace import (
    create_durable_v07_workspace,
    preview_durable_v07_workspace,
)
from traffictwin.ui.navigation_v07 import SOURCE_HEALTH_PAGE_SPEC, validate_v07_page_specs
from traffictwin.ui.state import default_session_state, load_ui_config


def _workspace(tmp_path: Path) -> Path:
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    workspace = parent / "workspace-v0.7"
    preview = preview_durable_v07_workspace(workspace)
    create_durable_v07_workspace(
        workspace,
        expected_plan_fingerprint=preview.confirmation_fingerprint(),
    )
    return workspace


def _app(monkeypatch: MonkeyPatch, workspace: Path) -> Any:  # noqa: ANN401
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("BODS_API_KEY", "page-secret-bods")
    monkeypatch.setenv("TRAFFICTWIN_BODS_BOUNDING_BOX", "-2.60,53.30,-1.90,53.70")
    monkeypatch.setenv("NATIONAL_HIGHWAYS_API_KEY", "page-secret-highways")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/source_health.py")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app.run(timeout=25)


def test_source_health_route_is_additive_and_registered() -> None:
    validate_v07_page_specs()
    assert SOURCE_HEALTH_PAGE_SPEC.group == "Overview"
    assert SOURCE_HEALTH_PAGE_SPEC.url_path == "source-health"
    assert SOURCE_HEALTH_PAGE_SPEC.script == "app_pages/source_health.py"


def test_source_health_page_shows_semantic_local_states_without_secrets(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    workspace = _workspace(tmp_path)
    app = _app(monkeypatch, workspace)

    assert not app.exception
    assert app.session_state["_active_ui_route"] == "source-health"
    assert any(item.value == "Source Health" for item in app.title)
    assert {item.value for item in app.subheader} >= {
        "BODS",
        "National Highways",
        "Aggregate operational history",
    }
    assert {item.label for item in app.metric} >= {
        "Hot history",
        "Long-term records",
        "Local interval",
        "Journal records",
        "Journal integrity",
        "Provider quota",
    }
    assert len(app.download_button) == 1
    rendered = " ".join(
        str(item.value)
        for kind in ("caption", "markdown", "dataframe", "info", "warning")
        for item in getattr(app, kind)
    )
    assert "page-secret-bods" not in rendered
    assert "page-secret-highways" not in rendered
    assert str(workspace) not in rendered
    assert "PROVIDER REQUEST" in rendered


def test_source_health_empty_configuration_is_explicit(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app_pages/source_health.py").run(timeout=25)

    assert not app.exception
    assert any("verified durable" in item.value for item in app.info)
    assert not app.download_button

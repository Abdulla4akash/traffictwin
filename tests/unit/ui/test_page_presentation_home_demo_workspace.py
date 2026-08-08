"""AppTest coverage for the in-UI demo-workspace creation."""

from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.state import default_session_state


@pytest.fixture(autouse=True)
def _isolate_traffictwin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep AppTests hermetic when a host TRAFFICTWIN_WORKSPACE_PATH is set."""

    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_TOS_DATA_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_FIXTURE_PATH", raising=False)


HOME_APP = "src/traffictwin/ui/app_pages/home.py"
BUNDLE_APP = "src/traffictwin/ui/app_pages/bundle_import.py"


def _home_app() -> AppTest:
    app = AppTest.from_file(HOME_APP)
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def _bundle_import_app() -> AppTest:
    app = AppTest.from_file(BUNDLE_APP)
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_home_empty_state_offers_create_demo_workspace() -> None:
    app = _home_app().run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Create demo workspace" in labels
    text = " ".join(str(markdown.value) for markdown in app.markdown)
    caption = " ".join(str(item.value) for item in app.caption)
    warning = " ".join(str(item.value) for item in app.warning)
    combined = (text + " " + caption + " " + warning).lower()
    assert "synthetic" in combined
    assert "manchester" in combined


def test_home_create_demo_workspace_creates_and_shows_success() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "home-demo"
        app = _home_app().run(timeout=30)
        assert not app.exception
        # Set the path via the text_input widget
        input_widget = next(
            widget for widget in app.text_input if widget.label == "Demo workspace path"
        )
        input_widget.set_value(str(workspace)).run(timeout=30)
        assert not app.exception

        app.button(key="home_create_demo_workspace").click().run(timeout=30)
        assert not app.exception
        success = " ".join(str(item.value) for item in app.success)
        info = " ".join(str(item.value) for item in app.info)
        assert "62" in success
        assert "synthetic" in success.lower()
        assert "Manchester" in info
        assert (workspace / "workspace.yaml").exists()
        assert (workspace / "registry.sqlite").exists()


def test_home_create_demo_workspace_shows_already_exists_on_rerun() -> None:
    # After creation the effective workspace hides the create card, so the
    # already_exists path is exercised via the service directly rather than
    # through a second in-UI click (which would have no button to click).
    from traffictwin.ui.demo_workspace_service import ensure_demo_workspace

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "home-rerun-demo"
        first = ensure_demo_workspace(workspace)
        assert first.status == "created"

        second = ensure_demo_workspace(workspace)
        assert second.status == "already_exists"
        assert "already exists" in second.message.lower()


def test_home_effective_workspace_hides_create_after_session_creation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "session-demo"
        initialise_workspace(workspace)
        app = _home_app()
        app.session_state["_active_demo_workspace_path"] = str(workspace)
        app.session_state["active_registry_path"] = str(workspace / "registry.sqlite")
        app.run(timeout=30)

        assert not app.exception
        labels = [button.label for button in app.button]
        assert "Create demo workspace" not in labels


def test_home_create_demo_workspace_updates_kpis_in_one_click() -> None:
    """One click must create the workspace and immediately show 62/3 KPIs."""

    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "kpi-demo"
        app = _home_app().run(timeout=30)
        assert not app.exception

        input_widget = next(
            widget for widget in app.text_input if widget.label == "Demo workspace path"
        )
        input_widget.set_value(str(workspace)).run(timeout=30)
        assert not app.exception

        app.button(key="home_create_demo_workspace").click().run(timeout=30)
        assert not app.exception

        # Flash message survives the rerun
        success = " ".join(str(item.value) for item in app.success)
        assert "62" in success

        # KPIs update without a manual reload (AppTest's button list is stale after st.rerun,
        # but metrics and flash correctly reflect the rerun).
        metric_labels = [str(metric.label) for metric in app.metric]
        metric_values = [str(metric.value) for metric in app.metric]
        paired = dict(zip(metric_labels, metric_values, strict=False))
        assert paired.get("Registered runs") == "62"
        assert paired.get("Comparisons") == "3"


def test_bundle_import_shows_example_shortcuts() -> None:
    app = _bundle_import_app().run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Open example baseline" in labels
    assert "Open example variation" in labels
    caption = " ".join(str(item.value) for item in app.caption)
    assert "synthetic" in caption.lower()


def test_bundle_import_example_baseline_sets_selected_path() -> None:
    app = _bundle_import_app().run(timeout=30)
    assert not app.exception

    app.button(key="bundle_import_example_baseline").click().run(timeout=30)
    assert not app.exception
    assert "baseline_valid" in str(app.session_state["selected_bundle_path"])


def test_bundle_import_example_variation_sets_selected_path() -> None:
    app = _bundle_import_app().run(timeout=30)
    assert not app.exception

    app.button(key="bundle_import_example_variation").click().run(timeout=30)
    assert not app.exception
    assert "variation_valid" in str(app.session_state["selected_bundle_path"])

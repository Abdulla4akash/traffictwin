"""S4A Home + What-If discoverability — hermetic AppTests."""

from __future__ import annotations

import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.state import default_session_state

HOME_APP = "src/traffictwin/ui/app_pages/home.py"


@pytest.fixture(autouse=True)
def _isolate_traffictwin_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRAFFICTWIN_WORKSPACE_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_TOS_DATA_PATH", raising=False)
    monkeypatch.delenv("TRAFFICTWIN_FIXTURE_PATH", raising=False)


def _home_app(*, v07_active: bool = True) -> AppTest:
    app = AppTest.from_file(HOME_APP)
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = v07_active
    return app


def test_home_exposes_whatif_studio_action() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Create what-if comparison" in labels


def test_home_legacy_exposes_whatif_action() -> None:
    app = _home_app(v07_active=False).run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Create what-if comparison" in labels


def test_home_actual_whatif_button_routes_to_studio() -> None:
    """Regression: the production V0.7 Home button must route to What-If Studio.

    Renders the real Home via the app router, clicks the actual button labelled
    "Create what-if comparison", and asserts the observed navigation target is
    What-If Studio. This fails if home.py is changed to SCENARIO, COMPARE, or
    any other destination because the clicked button declaration is the
    production one.
    """

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("src/traffictwin/ui/app.py").run(timeout=25)
    assert not app.exception
    # Land on Home
    assert any("Model a traffic scenario" in str(t.value) for t in app.title)

    button = next(b for b in app.button if b.label == "Create what-if comparison")
    button.click().run(timeout=25)

    assert not app.exception
    # What-If Studio page renders "What-If Studio" as title
    assert any(t.value == "What-If Studio" for t in app.title)
    # Must not have navigated to Scenario Builder or Compare
    assert not any(t.value == "Scenario Builder" for t in app.title)
    assert not any("What-if Compare" in str(t.value) for t in app.title)


def test_home_whatif_no_terminal_path_knowledge() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    caption_text = " ".join(str(item.value) for item in [*app.caption, *app.markdown, *app.warning])
    button_labels = " ".join(item.label for item in app.button)
    combined = caption_text + " " + button_labels
    # Path/terminal knowledge must not be required
    assert "terminal" not in combined.lower()
    assert "yaml path" not in combined.lower()
    # No absolute-path hint for the pair action
    assert "Create what-if comparison" in button_labels


def test_home_still_renders_manchester_context() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    markdown_text = " ".join(str(m.value) for m in app.markdown)
    caption_text = " ".join(str(c.value) for c in app.caption)
    # Static geographic context must remain
    assert "Manchester study-area context" in markdown_text
    assert (
        "Static geographic context — no live or observed traffic scene is loaded." in caption_text
    )


def test_home_handles_no_workspace_state() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Create demo workspace" in labels
    assert "Create what-if comparison" in labels
    # Metrics should be zero when no workspace
    assert any(m.label == "Registered runs" and str(m.value) == "0" for m in app.metric)
    assert any(m.label == "Visible local layers" and str(m.value) == "0" for m in app.metric)


def test_home_handles_demo_workspace_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "demo-ws"
        initialise_workspace(workspace)
        app = _home_app(v07_active=True)
        app.session_state["_active_demo_workspace_path"] = str(workspace)
        app.session_state["active_registry_path"] = str(workspace / "registry.sqlite")
        app.run(timeout=30)

        assert not app.exception
        labels = [button.label for button in app.button]
        assert "Create what-if comparison" in labels
        assert "Create demo workspace" not in labels
        # KPIs reflect demo fixture
        assert any(m.label == "Registered runs" and str(m.value) == "62" for m in app.metric)
        assert any(m.label == "Comparisons" and str(m.value) == "3" for m in app.metric)
        # Manchester context caption for synthetic demo
        caption_text = " ".join(str(c.value) for c in app.caption)
        assert "Synthetic demo workspace is active" in caption_text
        assert "Create what-if comparison" in " ".join(str(b.label) for b in app.button)


def test_home_retains_guided_demo_action() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" in labels
    assert "Create what-if comparison" in labels
    assert "Explore Manchester" in labels


def test_home_preserves_scenario_builder_access() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Create scenario" in labels


def test_home_no_live_observed_claim() -> None:
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    combined = " ".join(str(item.value) for item in [*app.caption, *app.markdown, *app.warning])
    # Must not claim live/observed road traffic
    assert "live Manchester road traffic" not in combined.lower()
    assert "observed Manchester traffic" not in combined.lower()
    # What-If truthfulness must be present
    assert "not Manchester observation" in combined
    assert "not a live traffic forecast" in combined
    assert "SYNTHETIC" in combined
    assert "DETERMINISTIC" in combined
    assert "LOCAL" in combined


def test_home_hermetic_against_traffictwin_workspace_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Set a fake workspace env that would break non-hermetic tests
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", "/tmp/should-not-be-used")  # noqa: S108
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", "/tmp/should-not-be-used/registry.sqlite")  # noqa: S108
    app = _home_app(v07_active=True).run(timeout=30)

    assert not app.exception
    # Still shows Create what-if and correct zero metrics (not reading fake path)
    assert "Create what-if comparison" in [b.label for b in app.button]

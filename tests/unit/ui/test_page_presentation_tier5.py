"""Adversarial presentation tests for the Phase 2B Tier 5 research-workflow pages."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def page_app(page: UiPage) -> AppTest:
    """Build an AppTest for one Tier 5 page with shared v0.7 session state."""

    app = AppTest.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def text_of(app: AppTest) -> str:
    parts = [str(block.value) for block in app.markdown]
    parts.extend(str(caption.value) for caption in app.caption)
    return "\n".join(parts)


def subheaders(app: AppTest) -> set[str]:
    return {str(item.value) for item in app.subheader}


def click(app: AppTest, label: str, timeout: int = 20) -> AppTest:
    next(button for button in app.button if button.label == label).click()
    return app.run(timeout=timeout)


# --- Scenario Mutations -----------------------------------------------------


def test_scenario_mutation_shows_three_stages_and_before_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "exports").mkdir(parents=True)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))

    app = page_app(UiPage.SCENARIO_MUTATION)
    app.session_state["selected_bundle_path"] = "tests/fixtures/bundles/baseline_valid"
    app.run(timeout=15)
    assert not app.exception

    # The ordered three-stage workflow indicator and no-simulator framing are present up front.
    body = text_of(app)
    assert "1 Source scenario" in body
    assert "2 Requested mutation" in body
    assert "3 Resulting candidate" in body
    assert "never executes or validates a simulator" in body

    app = click(app, "Build Mutated Copy")
    assert not app.exception

    heads = subheaders(app)
    assert "Mutation Result" in heads
    assert "Before / After Field Changes" in heads
    body = text_of(app)
    # Source, mutation, and candidate render as three distinct stages with badges.
    assert "Stage 1 · Source scenario" in body
    assert "Stage 2 · Requested mutation" in body
    assert "Stage 3 · Resulting candidate" in body
    assert "-badge[" in body
    # Import validation is explicitly not simulation.
    assert "Import validation is not simulation" in body


def test_scenario_mutation_keeps_fingerprints_and_manifest_in_advanced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "exports").mkdir(parents=True)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))

    app = page_app(UiPage.SCENARIO_MUTATION)
    app.session_state["selected_bundle_path"] = "tests/fixtures/bundles/baseline_valid"
    app.run(timeout=15)
    app = click(app, "Build Mutated Copy")
    assert not app.exception

    advanced = [str(exp.label) for exp in app.expander if "Advanced/Evidence" in str(exp.label)]
    assert any("fingerprints" in label.lower() for label in advanced)
    # The manifest download stays under Advanced/Evidence, not in primary content.
    assert any(
        button.label == "Download Mutation Manifest JSON" for button in app.download_button
    )

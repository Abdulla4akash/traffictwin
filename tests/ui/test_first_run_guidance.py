"""First-run guidance appears on empty workspaces and never hides real states."""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from traffictwin.storage.registry import Registry
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import page_script_for
from traffictwin.ui.state import default_session_state, load_ui_config


def _page(monkeypatch: MonkeyPatch, tmp_path: Path, page: UiPage) -> Any:  # noqa: ANN401 - AppTest is loaded dynamically
    registry_path = tmp_path / "registry.sqlite"
    Registry(registry_path).initialize()
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path / "workspace"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{page_script_for(page)}")
    for key, value in deepcopy(default_session_state(load_ui_config())).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True
    return app


def test_experiment_manager_offers_directions_on_an_empty_workspace(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.EXPERIMENT_MANAGER)
    app.run(timeout=15)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" in labels
    assert "Import a Run Bundle" in labels
    # The honest empty states stay visible beside the guidance.
    info_values = " ".join(str(info.value) for info in app.info)
    assert "No bundle imports are registered." in info_values
    # Guidance never duplicates the page's existing planner action.
    assert labels.count("Create Experiment Plan") == 1
    assert len(labels) == len(set(labels)), "guidance must not duplicate button labels"


def test_run_overview_offers_directions_when_nothing_is_selected(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.RUN_OVERVIEW)
    app.session_state["selected_bundle_path"] = str(tmp_path / "does-not-exist")
    app.run(timeout=15)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" in labels
    assert "Import a Run Bundle" in labels
    # The explicit missing-path error is not replaced by the guidance.
    assert any("does not exist" in str(error.value) for error in app.error)


def test_run_overview_shows_no_guidance_for_a_rejected_existing_bundle(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    bundle_dir = tmp_path / "broken-bundle"
    bundle_dir.mkdir()
    (bundle_dir / "manifest.json").write_text("{}", encoding="utf-8")
    app = _page(monkeypatch, tmp_path, UiPage.RUN_OVERVIEW)
    app.session_state["selected_bundle_path"] = str(bundle_dir)
    app.run(timeout=15)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" not in labels, (
        "a rejected bundle is a validation finding, not a first-run state"
    )


def test_compare_offers_directions_when_bundle_paths_are_missing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.COMPARE)
    app.session_state["selected_baseline_run"] = str(tmp_path / "missing-baseline")
    app.session_state["selected_variation_run"] = str(tmp_path / "missing-variation")
    app.run(timeout=15)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" in labels
    assert "Import a Run Bundle" in labels
    assert any("must exist" in str(error.value) for error in app.error)


def test_compare_offers_directions_when_only_baseline_missing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.COMPARE)
    app.session_state["selected_baseline_run"] = "tests/fixtures/bundles/baseline_valid"
    app.session_state["selected_variation_run"] = "tests/fixtures/bundles/variation_valid"
    app.run(timeout=15)
    assert not app.exception
    baseline_w = next(w for w in app.text_input if w.label == "Baseline bundle path")
    baseline_w.set_value(str(tmp_path / "missing-baseline-only")).run(timeout=15)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Start Guided Demo" in labels
    assert "Import a Run Bundle" in labels
    assert any("must exist" in str(e.value) for e in app.error)
    combined = (
        " ".join(str(e.value) for e in app.error)
        + " "
        + " ".join(
            str(i.value)
            for i in app.info  # noqa: E501
        )
    )
    assert "Baseline" in combined

    def _get(k: str) -> str:
        try:
            return str(app.session_state[k])
        except KeyError:
            return str(app.session_state._state[k])

    assert _get("selected_baseline_run") == "tests/fixtures/bundles/baseline_valid"
    assert _get("selected_variation_run") == "tests/fixtures/bundles/variation_valid"
    assert _get("selected_baseline_run") != "."
    assert _get("selected_variation_run") != "."


def test_compare_offers_directions_when_only_variation_missing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.COMPARE)
    app.session_state["selected_baseline_run"] = "tests/fixtures/bundles/baseline_valid"
    app.session_state["selected_variation_run"] = "tests/fixtures/bundles/variation_valid"
    app.run(timeout=15)
    assert not app.exception
    variation_w = next(w for w in app.text_input if w.label == "Variation bundle path")
    variation_w.set_value(str(tmp_path / "missing-variation-only")).run(timeout=15)
    assert not app.exception
    labels = [b.label for b in app.button]
    assert "Start Guided Demo" in labels
    assert "Import a Run Bundle" in labels
    assert any("must exist" in str(e.value) for e in app.error)
    combined = (
        " ".join(str(e.value) for e in app.error)
        + " "
        + " ".join(
            str(i.value)
            for i in app.info  # noqa: E501
        )
    )
    assert "Variation" in combined

    def _get(k: str) -> str:
        try:
            return str(app.session_state[k])
        except KeyError:
            return str(app.session_state._state[k])

    assert _get("selected_baseline_run") == "tests/fixtures/bundles/baseline_valid"
    assert _get("selected_variation_run") == "tests/fixtures/bundles/variation_valid"
    assert _get("selected_baseline_run") != "."
    assert _get("selected_variation_run") != "."


def test_compare_invalid_baseline_preserves_authoritative(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    invalid = tmp_path / "invalid-baseline"
    invalid.mkdir()
    (invalid / "manifest.json").write_text("{}", encoding="utf-8")
    app = _page(monkeypatch, tmp_path, UiPage.COMPARE)
    app.session_state["selected_baseline_run"] = "tests/fixtures/bundles/baseline_valid"
    app.session_state["selected_variation_run"] = "tests/fixtures/bundles/variation_valid"
    app.run(timeout=15)
    baseline_w = next(w for w in app.text_input if w.label == "Baseline bundle path")
    baseline_w.set_value(str(invalid)).run(timeout=15)
    assert not app.exception

    def _get(k: str) -> str:
        try:
            return str(app.session_state[k])
        except KeyError:
            return str(app.session_state._state[k])

    assert _get("selected_baseline_run") == "tests/fixtures/bundles/baseline_valid"
    assert _get("selected_variation_run") == "tests/fixtures/bundles/variation_valid"
    assert _get("selected_baseline_run") != "."
    assert any("invalid" in str(e.value).lower() for e in app.error)


def test_compare_invalid_variation_preserves_authoritative(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    invalid = tmp_path / "invalid-variation"
    invalid.mkdir()
    (invalid / "manifest.json").write_text("{}", encoding="utf-8")
    app = _page(monkeypatch, tmp_path, UiPage.COMPARE)
    app.session_state["selected_baseline_run"] = "tests/fixtures/bundles/baseline_valid"
    app.session_state["selected_variation_run"] = "tests/fixtures/bundles/variation_valid"
    app.run(timeout=15)
    variation_w = next(w for w in app.text_input if w.label == "Variation bundle path")
    variation_w.set_value(str(invalid)).run(timeout=15)
    assert not app.exception

    def _get(k: str) -> str:
        try:
            return str(app.session_state[k])
        except KeyError:
            return str(app.session_state._state[k])

    assert _get("selected_baseline_run") == "tests/fixtures/bundles/baseline_valid"
    assert _get("selected_variation_run") == "tests/fixtures/bundles/variation_valid"
    assert any("invalid" in str(e.value).lower() for e in app.error)


def test_statistical_study_offers_directions_without_registered_experiments(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    app = _page(monkeypatch, tmp_path, UiPage.STATISTICAL_STUDY)
    app.run(timeout=15)

    assert not app.exception
    labels = [button.label for button in app.button]
    assert "Start Guided Demo" in labels
    assert "Plan an Experiment" in labels
    info_values = " ".join(str(info.value) for info in app.info)
    assert "No registered experiment" in info_values

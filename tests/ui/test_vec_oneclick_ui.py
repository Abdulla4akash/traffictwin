"""Regression tests for configured-registry session state and one-click UI gating."""

from __future__ import annotations

from pathlib import Path

from traffictwin.integration.vec_orchestration import VecExecutionPreset
from traffictwin.ui.pages.vec_workbench import one_click_ready
from traffictwin.ui.state import UiConfig, default_session_state, ensure_session_state


def demo_config() -> UiConfig:
    return UiConfig(
        registry_path=Path(".demo/registry.sqlite"),
        default_fixture_path=Path("tests/fixtures/bundles"),
        tos_data_path=Path(".demo/tos-data"),
    )


def test_configured_registry_seeds_session_state() -> None:
    state: dict[str, object] = {}

    ensure_session_state(state, demo_config())

    assert state["active_registry_path"] == ".demo/registry.sqlite"
    assert state["selected_tos_data_path"] == ".demo/tos-data"


def test_intentional_user_registry_selection_is_never_overwritten() -> None:
    state: dict[str, object] = {"active_registry_path": "custom/registry.sqlite"}

    ensure_session_state(state, demo_config())

    assert state["active_registry_path"] == "custom/registry.sqlite"


def test_without_configuration_the_legacy_default_remains() -> None:
    state: dict[str, object] = {}

    ensure_session_state(state)

    assert state["active_registry_path"] == "data/registry/traffictwin.sqlite"


def test_default_session_state_without_tos_path_keeps_static_default() -> None:
    config = UiConfig(registry_path=Path(".demo/registry.sqlite"))

    defaults = default_session_state(config)

    assert defaults["active_registry_path"] == ".demo/registry.sqlite"
    assert defaults["selected_tos_data_path"] == ""


def test_one_click_gating_requires_complete_inputs() -> None:
    assert one_click_ready("root", "out", "reg", VecExecutionPreset.SMOKE_TWO_STEP, False)
    assert not one_click_ready("", "out", "reg", VecExecutionPreset.SMOKE_TWO_STEP, True)
    assert not one_click_ready("root", " ", "reg", VecExecutionPreset.SMOKE_TWO_STEP, True)
    assert not one_click_ready("root", "out", "", VecExecutionPreset.SMOKE_TWO_STEP, True)


def test_one_click_full_reproduction_requires_explicit_confirmation() -> None:
    assert not one_click_ready("root", "out", "reg", VecExecutionPreset.FULL_REPRODUCTION, False)
    assert one_click_ready("root", "out", "reg", VecExecutionPreset.FULL_REPRODUCTION, True)

from __future__ import annotations

from copy import deepcopy
from importlib import import_module

import pytest
import streamlit as st

import traffictwin.ui.navigation as legacy_navigation
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import (
    PLATFORM_ANALYTICS_PAGE_SPEC,
    PLATFORM_COMPOSER_PAGE_SPEC,
    PLATFORM_DECISION_SAFETY_PAGE_SPEC,
    PLATFORM_EVIDENCE_MATRIX_PAGE_SPEC,
    PLATFORM_FORECASTS_PAGE_SPEC,
    PLATFORM_INVENTORY_PAGE_SPEC,
    PLATFORM_OBSERVATORY_PAGE_SPEC,
    PLATFORM_XAI_AUDIT_PAGE_SPEC,
    V07_NAVIGATION_ENV,
    V07_NAVIGATION_GROUPS,
    V07_NORMATIVE_GROUPS,
    V07_PAGE_SPECS,
    V07PageSpec,
    legacy_navigation_requested,
    page_script_for,
    v07_navigation_requested,
    validate_v07_page_specs,
)
from traffictwin.ui.page_runtime import PAGE_RENDERERS
from traffictwin.ui.state import default_session_state


def test_candidate_inventory_covers_every_current_page_once() -> None:
    validate_v07_page_specs()

    assert len(V07_PAGE_SPECS) == 34 == len(UiPage)
    assert {spec.page for spec in V07_PAGE_SPECS} == set(UiPage)
    assert len({spec.script for spec in V07_PAGE_SPECS}) == 34
    assert len({spec.url_path for spec in V07_PAGE_SPECS}) == 34
    assert tuple(dict.fromkeys(spec.group for spec in V07_PAGE_SPECS)) == V07_NORMATIVE_GROUPS
    assert set(PAGE_RENDERERS) == set(UiPage)


def test_platform_group_is_appended_after_the_seven_normative_groups() -> None:
    # The platform dashboard adds ONE group at the end; the seven normative
    # groups and every existing route are unchanged (dashboard design §4).
    assert (*V07_NORMATIVE_GROUPS, "Platform") == V07_NAVIGATION_GROUPS
    assert len(V07_NORMATIVE_GROUPS) == 7
    platform_specs = (
        PLATFORM_INVENTORY_PAGE_SPEC,
        PLATFORM_FORECASTS_PAGE_SPEC,
        PLATFORM_COMPOSER_PAGE_SPEC,
        PLATFORM_ANALYTICS_PAGE_SPEC,
        PLATFORM_EVIDENCE_MATRIX_PAGE_SPEC,
        PLATFORM_OBSERVATORY_PAGE_SPEC,
        PLATFORM_DECISION_SAFETY_PAGE_SPEC,
        PLATFORM_XAI_AUDIT_PAGE_SPEC,
    )
    assert [spec.title for spec in platform_specs] == [
        "Data Inventory",
        "Forecasts",
        "What-If Composer",
        "Analytics Quality",
        "Evidence Matrix",
        "Mechanism Observatory",
        "Decision Safety",
        "Decision Audit",
    ]
    assert all(spec.group == "Platform" for spec in platform_specs)
    normative_paths = {spec.url_path for spec in V07_PAGE_SPECS}
    normative_scripts = {spec.script for spec in V07_PAGE_SPECS}
    for spec in platform_specs:
        assert spec.url_path not in normative_paths
        assert spec.script not in normative_scripts


def test_candidate_inventory_matches_normative_routes_and_groups() -> None:
    expected = {
        UiPage.HOME: ("Overview", "home"),
        UiPage.GUIDED_DEMO: ("Overview", "guided-workflow"),
        UiPage.SEARCH: ("Overview", "search"),
        UiPage.EXPERIMENT_PLANNER: ("Build & run", "experiment-planner"),
        UiPage.PARAMETER_SWEEP: ("Build & run", "parameter-sweep"),
        UiPage.SCENARIO_MUTATION: ("Build & run", "scenario-mutations"),
        UiPage.SCENARIO: ("Build & run", "scenario-builder"),
        UiPage.BUNDLE_IMPORT: ("Build & run", "bundle-import"),
        UiPage.SUMO_IMPORT: ("Build & run", "sumo"),
        UiPage.TOS_DATA: ("Build & run", "tos-import"),
        UiPage.VEC_WORKBENCH: ("Build & run", "vec"),
        UiPage.EXPERIMENT_MANAGER: ("Build & run", "experiments"),
        UiPage.RUN_OVERVIEW: ("Results", "run-overview"),
        UiPage.JOURNEY_TIME: ("Results", "journey-time"),
        UiPage.TEMPORAL_METRICS: ("Results", "temporal-metrics"),
        UiPage.ENERGY: ("Results", "energy"),
        UiPage.FAIRNESS: ("Results", "fairness"),
        UiPage.INFRASTRUCTURE: ("Results", "infrastructure"),
        UiPage.SPATIAL_RSU: ("Results", "spatial-rsu"),
        UiPage.COMPARE: ("Compare & test", "compare"),
        UiPage.STATISTICAL_STUDY: ("Compare & test", "statistics"),
        UiPage.THRESHOLD_SENSITIVITY: ("Compare & test", "threshold-sensitivity"),
        UiPage.TRIVIALITY: ("Compare & test", "triviality"),
        UiPage.TOS_RESULTS: ("Source evidence", "tos-results"),
        UiPage.TOS_REPLAY: ("Source evidence", "tos-replay"),
        UiPage.TOS_TRAINING: ("Source evidence", "tos-training"),
        UiPage.OPERATIONS: ("Source evidence", "replay"),
        UiPage.EVIDENCE: ("Evidence & reports", "diagnostics"),
        UiPage.PROVENANCE: ("Evidence & reports", "provenance"),
        UiPage.REPORTS: ("Evidence & reports", "reports"),
        UiPage.PARTICIPANT_EVALUATION: ("Evidence & reports", "mock-evaluation"),
        UiPage.MANIFEST_WIZARD: ("Advanced", "manifest-inference"),
        UiPage.SETTINGS: ("Advanced", "settings"),
        UiPage.ABOUT: ("Advanced", "about"),
    }

    assert {spec.page: (spec.group, spec.url_path) for spec in V07_PAGE_SPECS} == expected


def test_grouped_router_is_default_with_explicit_legacy_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(V07_NAVIGATION_ENV, raising=False)
    assert v07_navigation_requested() is True
    assert legacy_navigation_requested() is False

    monkeypatch.setenv(V07_NAVIGATION_ENV, "1")
    assert v07_navigation_requested() is True

    for legacy_value in ("0", "false", "no", "legacy", " LEGACY "):
        monkeypatch.setenv(V07_NAVIGATION_ENV, legacy_value)
        assert legacy_navigation_requested() is True
        assert v07_navigation_requested() is False


def test_page_script_lookup_is_exact() -> None:
    assert page_script_for(UiPage.HOME) == "app_pages/home.py"
    assert page_script_for(UiPage.VEC_WORKBENCH) == "app_pages/vec.py"
    assert page_script_for(UiPage.ABOUT) == "app_pages/about.py"


def test_cross_page_callback_uses_registered_script_under_candidate_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"_v07_navigation_active": True}
    monkeypatch.setattr(st, "session_state", state)

    legacy_navigation.activate_page(UiPage.ABOUT)

    assert state[legacy_navigation.V07_PENDING_PAGE_KEY] == UiPage.ABOUT.value
    assert "active_page" not in state


def test_candidate_runtime_consumes_callback_route_outside_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {
        "_v07_navigation_active": True,
        legacy_navigation.V07_PENDING_PAGE_KEY: UiPage.ABOUT.value,
    }
    switched: list[str] = []
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "switch_page", switched.append)

    legacy_navigation.redirect_pending_v07_page(UiPage.HOME)

    assert switched == ["app_pages/about.py"]
    assert legacy_navigation.V07_PENDING_PAGE_KEY not in state


def test_candidate_runtime_discards_same_page_callback_route(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {
        "_v07_navigation_active": True,
        legacy_navigation.V07_PENDING_PAGE_KEY: UiPage.HOME.value,
    }
    switched: list[str] = []
    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "switch_page", switched.append)

    legacy_navigation.redirect_pending_v07_page(UiPage.HOME)

    assert switched == []
    assert legacy_navigation.V07_PENDING_PAGE_KEY not in state


def test_candidate_navigation_button_switches_from_top_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"_v07_navigation_active": True}
    calls: list[tuple[str, dict[str, object]]] = []
    switched: list[str] = []

    def pressed(label: str, **kwargs: object) -> bool:
        calls.append((label, kwargs))
        return True

    monkeypatch.setattr(st, "session_state", state)
    monkeypatch.setattr(st, "switch_page", switched.append)

    legacy_navigation.navigation_button(
        pressed,
        "Open About",
        UiPage.ABOUT,
        kind="primary",
        width="stretch",
    )

    assert calls == [("Open About", {"width": "stretch", "type": "primary"})]
    assert switched == ["app_pages/about.py"]


def test_legacy_navigation_button_preserves_callback_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"_v07_navigation_active": False}
    calls: list[tuple[str, dict[str, object]]] = []

    def idle(label: str, **kwargs: object) -> bool:
        calls.append((label, kwargs))
        return False

    monkeypatch.setattr(st, "session_state", state)

    legacy_navigation.navigation_button(idle, "Open About", UiPage.ABOUT)

    assert calls == [
        (
            "Open About",
            {
                "width": "content",
                "on_click": legacy_navigation.activate_page,
                "args": (UiPage.ABOUT,),
            },
        )
    ]


def test_grouped_router_renders_hidden_root_home_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(V07_NAVIGATION_ENV, raising=False)
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]

    app = app_test.from_file("src/traffictwin/ui/app.py").run(timeout=20)

    assert not app.exception
    assert not app.radio
    assert app.session_state["_v07_navigation_active"] is True
    assert app.session_state["_active_ui_page"] is UiPage.HOME
    assert any("Workspace status" in caption.value for caption in app.sidebar.caption)
    assert any(
        "Model a traffic scenario. Run or import it. Compare the evidence." in item.value
        for item in app.title
    )
    assert {"Explore Manchester", "Create scenario", "Open latest run"}.issubset(
        {button.label for button in app.button}
    )
    # The Manchester evidence state renders as a badge, never a text metric.
    assert not any(item.label == "Manchester evidence" for item in app.metric)
    assert any("Manchester evidence" in caption.value for caption in app.caption)
    assert not any(item.value == "Capability Manifest" for item in app.subheader)


def test_explicit_compatibility_route_keeps_complete_legacy_navigation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(V07_NAVIGATION_ENV, "legacy")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]

    app = app_test.from_file("src/traffictwin/ui/app.py").run(timeout=20)

    assert not app.exception
    assert len(app.radio) == 1
    assert app.session_state["_v07_navigation_active"] is False
    assert len(app.radio[0].options) == len(UiPage)


@pytest.mark.parametrize("spec", V07_PAGE_SPECS, ids=lambda spec: spec.page.name.lower())
def test_every_direct_page_script_smoke_renders_with_shared_state(spec: V07PageSpec) -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file(f"src/traffictwin/ui/{spec.script}")
    for key, value in deepcopy(default_session_state()).items():
        app.session_state[key] = value
    app.session_state["_v07_navigation_active"] = True

    app.run(timeout=25)

    assert not app.exception
    assert app.session_state["_active_ui_page"] is spec.page

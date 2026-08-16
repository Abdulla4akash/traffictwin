from __future__ import annotations

from copy import deepcopy
from importlib import import_module

import pytest
import streamlit as st

import traffictwin.ui.navigation as legacy_navigation
from traffictwin.ui.expansion_routes import (
    EXPANSION_PAGE_SPECS,
    MANCHESTER_SOURCE_OPERATIONS_EXPANSION_SPEC,
    MANCHESTER_TWIN_EXPANSION_SPEC,
    NAVIGATION_OVERLAP_NOTE,
    REPLAY_OBSERVATORY_EXPANSION_SPEC,
    RESEARCH_REGISTRY_EXPANSION_SPEC,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation_v07 import (
    ANALYST_PAGE_SPEC,
    MANCHESTER_GATE_D_PAGE_SPEC,
    NEXT_INVESTIGATION_PAGE_SPEC,
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
    WHATIF_CHALLENGE_PAGE_SPEC,
    V07PageSpec,
    legacy_navigation_requested,
    page_script_for,
    v07_navigation_pages,
    v07_navigation_requested,
    validate_v07_page_specs,
)
from traffictwin.ui.page_runtime import PAGE_RENDERERS
from traffictwin.ui.state import default_session_state


def test_candidate_inventory_covers_every_current_page_once() -> None:
    validate_v07_page_specs()

    assert len(V07_PAGE_SPECS) == len(UiPage)
    assert {spec.page for spec in V07_PAGE_SPECS} == set(UiPage)
    assert len({spec.script for spec in V07_PAGE_SPECS}) == len(V07_PAGE_SPECS)
    assert len({spec.url_path for spec in V07_PAGE_SPECS}) == len(V07_PAGE_SPECS)
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
        ANALYST_PAGE_SPEC,
        NEXT_INVESTIGATION_PAGE_SPEC,
        WHATIF_CHALLENGE_PAGE_SPEC,
        MANCHESTER_GATE_D_PAGE_SPEC,
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
        "Analyst",
        "Next Investigation",
        "What-If Challenge",
        "Manchester Gate-D",
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
        UiPage.WHATIF_STUDIO: ("Build & run", "whatif-studio"),
        UiPage.SCENARIO: ("Build & run", "scenario-builder"),
        UiPage.DATA_CONTRACT_WORKBENCH: ("Build & run", "data-contract"),
        UiPage.BUNDLE_IMPORT: ("Build & run", "bundle-import"),
        UiPage.SUMO_IMPORT: ("Build & run", "sumo"),
        UiPage.TOS_DATA: ("Build & run", "tos-import"),
        UiPage.VEC_WORKBENCH: ("Build & run", "vec"),
        UiPage.EXPERIMENT_MANAGER: ("Build & run", "experiments"),
        UiPage.RUN_OVERVIEW: ("Results", "run-overview"),
        UiPage.JOURNEY_TIME: ("Results", "journey-time"),
        UiPage.CONSEQUENCE_LENSES: ("Results", "consequence-lenses"),
        UiPage.TEMPORAL_METRICS: ("Results", "temporal-metrics"),
        UiPage.EVENT_ALIGNED_ANALYSIS: ("Results", "event-aligned-analysis"),
        UiPage.ENERGY: ("Results", "energy"),
        UiPage.FAIRNESS: ("Results", "fairness"),
        UiPage.INFRASTRUCTURE: ("Results", "infrastructure"),
        UiPage.SPATIAL_RSU: ("Results", "spatial-rsu"),
        UiPage.PORTFOLIO_EXPLORER: ("Results", "portfolio-explorer"),
        UiPage.MANCHESTER_EVIDENCE_HUB: ("Evidence & reports", "manchester-evidence-hub"),
        UiPage.COMPARE: ("Compare & test", "compare"),
        UiPage.STATISTICAL_STUDY: ("Compare & test", "statistics"),
        UiPage.THRESHOLD_SENSITIVITY: ("Compare & test", "threshold-sensitivity"),
        UiPage.TRIVIALITY: ("Compare & test", "triviality"),
        UiPage.PREREGISTRATION_STUDIO: ("Compare & test", "preregistration"),
        UiPage.TOS_RESULTS: ("Source evidence", "tos-results"),
        UiPage.TOS_REPLAY: ("Source evidence", "tos-replay"),
        UiPage.TOS_TRAINING: ("Source evidence", "tos-training"),
        UiPage.OPERATIONS: ("Source evidence", "replay"),
        UiPage.EVIDENCE: ("Evidence & reports", "diagnostics"),
        UiPage.PROVENANCE: ("Evidence & reports", "provenance"),
        UiPage.REPORTS: ("Evidence & reports", "reports"),
        UiPage.STUDY_CAPSULE: ("Evidence & reports", "study-capsule"),
        UiPage.PARTICIPANT_EVALUATION: ("Evidence & reports", "mock-evaluation"),
        UiPage.MANIFEST_WIZARD: ("Advanced", "manifest-inference"),
        UiPage.SETTINGS: ("Advanced", "settings"),
        UiPage.ABOUT: ("Advanced", "about"),
        UiPage.RESOURCE_STRATEGY_EXPLORER: ("Compare & test", "resource-strategy"),
        UiPage.STUDY_WORKSPACE: ("Build & run", "study-workspace"),
        UiPage.METRIC_CONTRACT_REGISTRY: ("Build & run", "metric-contracts"),
        UiPage.CONTRACT_DRAFTING_ASSISTANT: ("Build & run", "contract-drafting"),
        UiPage.EVENT_SCENARIO_BRIDGE: ("Build & run", "event-scenario-bridge"),
        UiPage.STUDY_ACCRUAL_MONITOR: ("Results", "study-accrual"),
        UiPage.CALIBRATION_WORKBENCH: ("Compare & test", "calibration"),
        UiPage.MULTIOBJECTIVE_TRADEOFF: ("Compare & test", "tradeoff-explorer"),
        UiPage.EVIDENCE_ADMISSION_INBOX: ("Evidence & reports", "evidence-admission"),
        UiPage.BASELINE_REGISTRY: ("Evidence & reports", "baseline-registry"),
        UiPage.REPRODUCIBILITY_REPLAY: ("Evidence & reports", "reproducibility-replay"),
        UiPage.WORKSPACE_ACTIVATION: ("Advanced", "workspace-activation"),
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


# ---------------------------------------------------------------------------
# Lane 16 expansion routes — additive, coherent, overlap-honest
# ---------------------------------------------------------------------------


def test_expansion_routes_are_additive_and_coherent() -> None:
    # Expansion specs are additive only — outside the 34-page normative inventory.
    assert len(EXPANSION_PAGE_SPECS) == 4
    assert {s.title for s in EXPANSION_PAGE_SPECS} == {
        "Manchester Twin",
        "Manchester Source Operations",
        "Replay Observatory",
        "Research Registry",
    }
    assert [s.url_path for s in EXPANSION_PAGE_SPECS] == [
        "manchester-twin",
        "manchester-source-operations",
        "replay-observatory",
        "research-registry",
    ]
    assert [s.script for s in EXPANSION_PAGE_SPECS] == [
        "app_pages/manchester_twin.py",
        "app_pages/manchester_source_operations.py",
        "app_pages/replay_observatory.py",
        "app_pages/research_registry.py",
    ]
    # Coherent grouping: Manchester + Replay in Source evidence, Registry in Evidence & reports.
    assert MANCHESTER_TWIN_EXPANSION_SPEC.group == "Source evidence"
    assert MANCHESTER_SOURCE_OPERATIONS_EXPANSION_SPEC.group == "Source evidence"
    assert REPLAY_OBSERVATORY_EXPANSION_SPEC.group == "Source evidence"
    assert RESEARCH_REGISTRY_EXPANSION_SPEC.group == "Evidence & reports"
    # No collision with normative or other additive routes.
    validate_v07_page_specs()
    # Navigation composition actually exposes them — proven via group counts and validation.
    nav = v07_navigation_pages()
    # Source evidence grows from 8 (4 normative + 4 existing additive) to 11 with 3 expansion pages.
    assert len(nav["Source evidence"]) == 11, (
        f"expected 11 Source evidence pages, got {len(nav['Source evidence'])}"
    )
    # Evidence & reports grows from 9 to 10 with Research Registry.
    assert len(nav["Evidence & reports"]) == 10, (
        f"expected 10 Evidence & reports pages, got {len(nav['Evidence & reports'])}"
    )
    # Total pages: normative 54 + additive 15 + expansion 4 = 73 plus hidden root = 74.
    # Normative 54 + 15 existing additive + 4 expansion + hidden root
    # validated via validate_v07_page_specs().
    validate_v07_page_specs()
    # Resource Strategy untouched.
    assert any(s.page.value == "Resource Strategy Explorer" for s in V07_PAGE_SPECS)
    rs_spec = next(s for s in V07_PAGE_SPECS if s.page.value == "Resource Strategy Explorer")
    assert rs_spec.group == "Compare & test"
    assert rs_spec.url_path == "resource-strategy"


def test_expansion_routes_preserve_normative_inventory_and_validation() -> None:
    # Normative inventory remains exactly the counted 34-page set; expansion does not replace.
    from traffictwin.ui.navigation_v07 import V07_PAGE_SPECS as V07_SPECS_IMPORTED  # noqa: N811

    assert len(V07_SPECS_IMPORTED) == len(UiPage)
    # Overlap note is honest and non-empty.
    assert "Resource Strategy Explorer" in NAVIGATION_OVERLAP_NOTE
    assert "Research Registry" in NAVIGATION_OVERLAP_NOTE
    assert "Manchester Operations" in NAVIGATION_OVERLAP_NOTE
    # No duplicate scripts or paths across expansion.
    assert len({s.script for s in EXPANSION_PAGE_SPECS}) == 4
    assert len({s.url_path for s in EXPANSION_PAGE_SPECS}) == 4
    # File existence already covered by validate_v07_page_specs, but double-check expansion helper.
    from traffictwin.ui.expansion_routes import validate_expansion_routes

    validate_expansion_routes()


def test_expansion_additive_pages_smoke_render() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    for spec in EXPANSION_PAGE_SPECS:
        app = app_test.from_file(f"src/traffictwin/ui/{spec.script}")
        for key, value in deepcopy(default_session_state()).items():
            app.session_state[key] = value
        app.session_state["_v07_navigation_active"] = True
        app.run(timeout=25)
        assert not app.exception, f"expansion page {spec.title} failed: {app.exception}"
        # Page must render a title or meaningful marker.
        assert any(len(x) >= 1 for x in (app.title, app.markdown, app.caption))


def test_navigation_expansion_import_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lane 16 remediation: expansion import/defect must not be swallowed as empty."""
    import sys

    import traffictwin.ui.expansion_routes as er
    import traffictwin.ui.navigation_v07 as nav

    original = er.EXPANSION_PAGE_SPECS
    # Empty via safe monkeypatch — must raise, not validate as empty
    monkeypatch.setattr(er, "EXPANSION_PAGE_SPECS", (), raising=False)
    with pytest.raises(ValueError, match="expansion routes must contain exactly 4"):
        nav.validate_v07_page_specs()
    with pytest.raises(ValueError, match="expansion routes must contain exactly 4"):
        nav.v07_navigation_pages()
    # Restore and prove honest PASS
    monkeypatch.setattr(er, "EXPANSION_PAGE_SPECS", original, raising=False)
    nav.validate_v07_page_specs()
    pages = nav.v07_navigation_pages()
    assert len(pages["Source evidence"]) == 11
    assert len(pages["Evidence & reports"]) == 10

    # Import failure via sys.modules — must propagate, not fallback to empty
    class _BrokenModule:
        pass

    monkeypatch.setitem(sys.modules, "traffictwin.ui.expansion_routes", _BrokenModule())
    with pytest.raises((ImportError, AttributeError)):
        nav.validate_v07_page_specs()
    with pytest.raises((ImportError, AttributeError)):
        nav.v07_navigation_pages()
    # Restore sets back
    monkeypatch.setitem(sys.modules, "traffictwin.ui.expansion_routes", er)
    nav.validate_v07_page_specs()

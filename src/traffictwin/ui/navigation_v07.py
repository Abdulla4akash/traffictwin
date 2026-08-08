"""Task-oriented grouped Streamlit navigation for the v0.7 shell."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from traffictwin.ui.labels import UiPage

V07_NAVIGATION_ENV = "TRAFFICTWIN_V07_NAVIGATION"
V07_LEGACY_ROUTER_VALUES = frozenset({"0", "false", "no", "legacy"})
#: Task-oriented groups, each answering one question a researcher actually has.
#: The earlier five-group split put 14 of the 34 pages in a single "Analyse"
#: group that mixed three unrelated concerns — imported source material, per-run
#: metrics, and comparison testing — so a reader hunting for journey time had to
#: scan past replay and training pages to find it. Splitting by question keeps
#: every group scannable and puts configuration last, where it is reached
#: deliberately rather than stumbled into.
V07_NORMATIVE_GROUPS: tuple[str, ...] = (
    "Overview",
    "Build & run",
    "Results",
    "Compare & test",
    "Source evidence",
    "Evidence & reports",
    "Advanced",
)
#: The platform dashboard (P-3) appends ONE additive group after the seven
#: normative groups; every normative group and route is unchanged.
V07_NAVIGATION_GROUPS: tuple[str, ...] = (*V07_NORMATIVE_GROUPS, "Platform")


@dataclass(frozen=True)
class V07PageSpec:
    """One normative visible-page route in the candidate navigation."""

    page: UiPage
    group: str
    script: str
    url_path: str
    icon: str


@dataclass(frozen=True)
class V07AdditivePageSpec:
    """One v0.7-only route outside the normative 34-page migration inventory."""

    title: str
    group: str
    script: str
    url_path: str
    icon: str


MATCH_REVIEW_PAGE_SPEC = V07AdditivePageSpec(
    title="Match Review",
    group="Source evidence",
    script="app_pages/match_review.py",
    url_path="match-review",
    icon=":material/checklist:",
)

BUS_SESSIONS_PAGE_SPEC = V07AdditivePageSpec(
    title="Bus Sessions",
    group="Source evidence",
    script="app_pages/bus_sessions.py",
    url_path="bus-sessions",
    icon=":material/directions_bus:",
)

RSU_MONITOR_PAGE_SPEC = V07AdditivePageSpec(
    title="RSU Monitor",
    group="Source evidence",
    script="app_pages/rsu_monitor.py",
    url_path="rsu-monitor",
    icon=":material/cell_tower:",
)

CAMPAIGNS_PAGE_SPEC = V07AdditivePageSpec(
    title="Campaigns",
    group="Source evidence",
    script="app_pages/campaigns.py",
    url_path="campaigns",
    icon=":material/inventory_2:",
)

PLATFORM_INVENTORY_PAGE_SPEC = V07AdditivePageSpec(
    title="Data Inventory",
    group="Platform",
    script="app_pages/platform_inventory.py",
    url_path="platform-inventory",
    icon=":material/inventory:",
)

PLATFORM_FORECASTS_PAGE_SPEC = V07AdditivePageSpec(
    title="Forecasts",
    group="Platform",
    script="app_pages/platform_forecasts.py",
    url_path="platform-forecasts",
    icon=":material/timeline:",
)

PLATFORM_COMPOSER_PAGE_SPEC = V07AdditivePageSpec(
    title="What-If Composer",
    group="Platform",
    script="app_pages/platform_composer.py",
    url_path="platform-composer",
    icon=":material/tune:",
)

PLATFORM_ANALYTICS_PAGE_SPEC = V07AdditivePageSpec(
    title="Analytics Quality",
    group="Platform",
    script="app_pages/platform_analytics.py",
    url_path="platform-analytics-quality",
    icon=":material/monitoring:",
)

PLATFORM_EVIDENCE_MATRIX_PAGE_SPEC = V07AdditivePageSpec(
    title="Evidence Matrix",
    group="Platform",
    script="app_pages/platform_evidence_matrix.py",
    url_path="platform-evidence-matrix",
    icon=":material/grid_view:",
)

PLATFORM_OBSERVATORY_PAGE_SPEC = V07AdditivePageSpec(
    title="Mechanism Observatory",
    group="Platform",
    script="app_pages/platform_observatory.py",
    url_path="platform-mechanism-observatory",
    icon=":material/account_tree:",
)

PLATFORM_DECISION_SAFETY_PAGE_SPEC = V07AdditivePageSpec(
    title="Decision Safety",
    group="Platform",
    script="app_pages/platform_decision_safety.py",
    url_path="platform-decision-safety",
    icon=":material/policy:",
)

PLATFORM_XAI_AUDIT_PAGE_SPEC = V07AdditivePageSpec(
    title="Decision Audit",
    group="Platform",
    script="app_pages/platform_xai_audit.py",
    url_path="platform-xai-audit",
    icon=":material/troubleshoot:",
)

MANCHESTER_GATE_D_PAGE_SPEC = V07AdditivePageSpec(
    title="Manchester Gate-D",
    group="Platform",
    script="app_pages/manchester_gate_d.py",
    url_path="manchester-gate-d",
    icon=":material/route:",
)

MANCHESTER_PAGE_SPEC = V07AdditivePageSpec(
    title="Manchester Operations",
    group="Overview",
    script="app_pages/manchester.py",
    url_path="manchester",
    icon=":material/map:",
)

SOURCE_HEALTH_PAGE_SPEC = V07AdditivePageSpec(
    title="Source Health",
    group="Overview",
    script="app_pages/source_health.py",
    url_path="source-health",
    icon=":material/health_and_safety:",
)


V07_PAGE_SPECS: tuple[V07PageSpec, ...] = (
    V07PageSpec(
        UiPage.HOME,
        "Overview",
        "app_pages/home.py",
        "home",
        ":material/home:",
    ),
    V07PageSpec(
        UiPage.GUIDED_DEMO,
        "Overview",
        "app_pages/guided_demo.py",
        "guided-workflow",
        ":material/route:",
    ),
    V07PageSpec(
        UiPage.SEARCH,
        "Overview",
        "app_pages/search.py",
        "search",
        ":material/search:",
    ),
    V07PageSpec(
        UiPage.EXPERIMENT_PLANNER,
        "Build & run",
        "app_pages/experiment_planner.py",
        "experiment-planner",
        ":material/science:",
    ),
    V07PageSpec(
        UiPage.PARAMETER_SWEEP,
        "Build & run",
        "app_pages/parameter_sweep.py",
        "parameter-sweep",
        ":material/tune:",
    ),
    V07PageSpec(
        UiPage.SCENARIO_MUTATION,
        "Build & run",
        "app_pages/scenario_mutations.py",
        "scenario-mutations",
        ":material/experiment:",
    ),
    V07PageSpec(
        UiPage.WHATIF_STUDIO,
        "Build & run",
        "app_pages/whatif_studio.py",
        "whatif-studio",
        ":material/compare:",
    ),
    V07PageSpec(
        UiPage.SCENARIO,
        "Build & run",
        "app_pages/scenario_builder.py",
        "scenario-builder",
        ":material/edit_road:",
    ),
    V07PageSpec(
        UiPage.BUNDLE_IMPORT,
        "Build & run",
        "app_pages/bundle_import.py",
        "bundle-import",
        ":material/upload_file:",
    ),
    V07PageSpec(
        UiPage.SUMO_IMPORT,
        "Build & run",
        "app_pages/sumo.py",
        "sumo",
        ":material/traffic:",
    ),
    V07PageSpec(
        UiPage.TOS_DATA,
        "Build & run",
        "app_pages/tos_import.py",
        "tos-import",
        ":material/database:",
    ),
    V07PageSpec(
        UiPage.VEC_WORKBENCH,
        "Build & run",
        "app_pages/vec.py",
        "vec",
        ":material/memory:",
    ),
    V07PageSpec(
        UiPage.EXPERIMENT_MANAGER,
        "Build & run",
        "app_pages/experiments.py",
        "experiments",
        ":material/folder_managed:",
    ),
    V07PageSpec(
        UiPage.RUN_OVERVIEW,
        "Results",
        "app_pages/run_overview.py",
        "run-overview",
        ":material/dashboard:",
    ),
    V07PageSpec(
        UiPage.JOURNEY_TIME,
        "Results",
        "app_pages/journey_time.py",
        "journey-time",
        ":material/schedule:",
    ),
    V07PageSpec(
        UiPage.TEMPORAL_METRICS,
        "Results",
        "app_pages/temporal_metrics.py",
        "temporal-metrics",
        ":material/timeline:",
    ),
    V07PageSpec(
        UiPage.ENERGY,
        "Results",
        "app_pages/energy.py",
        "energy",
        ":material/bolt:",
    ),
    V07PageSpec(
        UiPage.FAIRNESS,
        "Results",
        "app_pages/fairness.py",
        "fairness",
        ":material/balance:",
    ),
    V07PageSpec(
        UiPage.INFRASTRUCTURE,
        "Results",
        "app_pages/infrastructure.py",
        "infrastructure",
        ":material/cell_tower:",
    ),
    V07PageSpec(
        UiPage.SPATIAL_RSU,
        "Results",
        "app_pages/spatial_rsu.py",
        "spatial-rsu",
        ":material/map:",
    ),
    V07PageSpec(
        UiPage.COMPARE,
        "Compare & test",
        "app_pages/compare.py",
        "compare",
        ":material/compare_arrows:",
    ),
    V07PageSpec(
        UiPage.STATISTICAL_STUDY,
        "Compare & test",
        "app_pages/statistics.py",
        "statistics",
        ":material/query_stats:",
    ),
    V07PageSpec(
        UiPage.THRESHOLD_SENSITIVITY,
        "Compare & test",
        "app_pages/threshold_sensitivity.py",
        "threshold-sensitivity",
        ":material/linear_scale:",
    ),
    V07PageSpec(
        UiPage.TRIVIALITY,
        "Compare & test",
        "app_pages/triviality.py",
        "triviality",
        ":material/emoji_events:",
    ),
    V07PageSpec(
        UiPage.TOS_RESULTS,
        "Source evidence",
        "app_pages/tos_results.py",
        "tos-results",
        ":material/analytics:",
    ),
    V07PageSpec(
        UiPage.TOS_REPLAY,
        "Source evidence",
        "app_pages/tos_replay.py",
        "tos-replay",
        ":material/play_circle:",
    ),
    V07PageSpec(
        UiPage.TOS_TRAINING,
        "Source evidence",
        "app_pages/tos_training.py",
        "tos-training",
        ":material/model_training:",
    ),
    V07PageSpec(
        UiPage.OPERATIONS,
        "Source evidence",
        "app_pages/replay.py",
        "replay",
        ":material/replay:",
    ),
    V07PageSpec(
        UiPage.EVIDENCE,
        "Evidence & reports",
        "app_pages/diagnostics.py",
        "diagnostics",
        ":material/fact_check:",
    ),
    V07PageSpec(
        UiPage.PROVENANCE,
        "Evidence & reports",
        "app_pages/provenance.py",
        "provenance",
        ":material/account_tree:",
    ),
    V07PageSpec(
        UiPage.REPORTS,
        "Evidence & reports",
        "app_pages/reports.py",
        "reports",
        ":material/article:",
    ),
    V07PageSpec(
        UiPage.PARTICIPANT_EVALUATION,
        "Evidence & reports",
        "app_pages/mock_evaluation.py",
        "mock-evaluation",
        ":material/assignment_ind:",
    ),
    V07PageSpec(
        UiPage.MANIFEST_WIZARD,
        "Advanced",
        "app_pages/manifest_inference.py",
        "manifest-inference",
        ":material/schema:",
    ),
    V07PageSpec(
        UiPage.SETTINGS,
        "Advanced",
        "app_pages/settings.py",
        "settings",
        ":material/settings:",
    ),
    V07PageSpec(
        UiPage.ABOUT,
        "Advanced",
        "app_pages/about.py",
        "about",
        ":material/info:",
    ),
)

_SPEC_BY_PAGE = {spec.page: spec for spec in V07_PAGE_SPECS}


def legacy_navigation_requested() -> bool:
    """Return whether the preserved legacy compatibility router was requested.

    Setting ``TRAFFICTWIN_V07_NAVIGATION`` to ``0``, ``false``, ``no``, or
    ``legacy`` keeps the complete v0.6 flat-radio router available as an
    explicit, tested compatibility route.
    """

    return os.getenv(V07_NAVIGATION_ENV, "").strip().lower() in V07_LEGACY_ROUTER_VALUES


def v07_navigation_requested() -> bool:
    """Return whether the grouped v0.7 router should run.

    The grouped ``st.navigation`` router is the normal route; only an
    explicit legacy request selects the compatibility router. This changes
    presentation routing only and does not accept `UX-01` or alter any
    capability status.
    """

    return not legacy_navigation_requested()


def page_script_for(page: UiPage) -> str:
    """Return the direct script path registered for one page."""

    return _SPEC_BY_PAGE[page].script


def validate_v07_page_specs(base: Path | None = None) -> None:
    """Fail when the candidate inventory is incomplete, duplicated, or missing files."""

    if len(V07_PAGE_SPECS) != len(UiPage):
        raise ValueError("v0.7 navigation must contain exactly one row for every UiPage")
    pages = [spec.page for spec in V07_PAGE_SPECS]
    paths = [spec.url_path for spec in V07_PAGE_SPECS]
    scripts = [spec.script for spec in V07_PAGE_SPECS]
    if set(pages) != set(UiPage) or len(set(pages)) != len(pages):
        raise ValueError("v0.7 navigation page membership is incomplete or duplicated")
    if len(set(paths)) != len(paths) or len(set(scripts)) != len(scripts):
        raise ValueError("v0.7 navigation paths and scripts must be unique")
    if tuple(dict.fromkeys(spec.group for spec in V07_PAGE_SPECS)) != V07_NORMATIVE_GROUPS:
        raise ValueError("v0.7 navigation groups or ordering do not match the design")
    if V07_NAVIGATION_GROUPS[: len(V07_NORMATIVE_GROUPS)] != V07_NORMATIVE_GROUPS:
        raise ValueError("additive groups may only be appended after the normative seven")
    source_root = base or Path(__file__).parent
    missing = [spec.script for spec in V07_PAGE_SPECS if not (source_root / spec.script).is_file()]
    additive_specs = (
        MANCHESTER_PAGE_SPEC,
        SOURCE_HEALTH_PAGE_SPEC,
        MATCH_REVIEW_PAGE_SPEC,
        RSU_MONITOR_PAGE_SPEC,
        BUS_SESSIONS_PAGE_SPEC,
        CAMPAIGNS_PAGE_SPEC,
        PLATFORM_INVENTORY_PAGE_SPEC,
        PLATFORM_FORECASTS_PAGE_SPEC,
        PLATFORM_COMPOSER_PAGE_SPEC,
        PLATFORM_ANALYTICS_PAGE_SPEC,
        PLATFORM_EVIDENCE_MATRIX_PAGE_SPEC,
        PLATFORM_OBSERVATORY_PAGE_SPEC,
        PLATFORM_DECISION_SAFETY_PAGE_SPEC,
        PLATFORM_XAI_AUDIT_PAGE_SPEC,
        MANCHESTER_GATE_D_PAGE_SPEC,
    )
    additive_paths = [spec.url_path for spec in additive_specs]
    additive_scripts = [spec.script for spec in additive_specs]
    if len(set(additive_paths)) != len(additive_paths) or len(set(additive_scripts)) != len(
        additive_scripts
    ):
        raise ValueError("additive routes must not collide with each other")
    for spec in additive_specs:
        if spec.group not in V07_NAVIGATION_GROUPS:
            raise ValueError("an additive page must use a registered navigation group")
        if spec.url_path in paths or spec.script in scripts:
            raise ValueError("an additive route must not replace a v0.6 destination")
        if not (source_root / spec.script).is_file():
            missing.append(spec.script)
    if missing:
        raise ValueError(f"v0.7 navigation page scripts are missing: {sorted(missing)}")


def _render_root_home() -> None:
    """Render Home at the root URL while preserving the explicit ``/home`` route."""

    from traffictwin.ui.page_runtime import run_page_script

    run_page_script(UiPage.HOME)


def v07_navigation_pages() -> dict[str, list[object]]:
    """Build the hidden root plus task-oriented navigation groups."""

    validate_v07_page_specs()
    pages: dict[str, list[object]] = {
        "": [st.Page(_render_root_home, title="Home", default=True, visibility="hidden")]
    }
    for group in V07_NAVIGATION_GROUPS:
        group_pages: list[object] = []
        for spec in V07_PAGE_SPECS:
            if spec.group != group:
                continue
            group_pages.append(
                st.Page(
                    spec.script,
                    title=spec.page.value,
                    icon=spec.icon,
                    url_path=spec.url_path,
                )
            )
            if spec.page is UiPage.HOME and group == MANCHESTER_PAGE_SPEC.group:
                group_pages.append(
                    st.Page(
                        MANCHESTER_PAGE_SPEC.script,
                        title=MANCHESTER_PAGE_SPEC.title,
                        icon=MANCHESTER_PAGE_SPEC.icon,
                        url_path=MANCHESTER_PAGE_SPEC.url_path,
                    )
                )
                group_pages.append(
                    st.Page(
                        SOURCE_HEALTH_PAGE_SPEC.script,
                        title=SOURCE_HEALTH_PAGE_SPEC.title,
                        icon=SOURCE_HEALTH_PAGE_SPEC.icon,
                        url_path=SOURCE_HEALTH_PAGE_SPEC.url_path,
                    )
                )
        if group == MATCH_REVIEW_PAGE_SPEC.group:
            group_pages.append(
                st.Page(
                    MATCH_REVIEW_PAGE_SPEC.script,
                    title=MATCH_REVIEW_PAGE_SPEC.title,
                    icon=MATCH_REVIEW_PAGE_SPEC.icon,
                    url_path=MATCH_REVIEW_PAGE_SPEC.url_path,
                )
            )
        if group == RSU_MONITOR_PAGE_SPEC.group:
            group_pages.append(
                st.Page(
                    RSU_MONITOR_PAGE_SPEC.script,
                    title=RSU_MONITOR_PAGE_SPEC.title,
                    icon=RSU_MONITOR_PAGE_SPEC.icon,
                    url_path=RSU_MONITOR_PAGE_SPEC.url_path,
                )
            )
        if group == BUS_SESSIONS_PAGE_SPEC.group:
            group_pages.append(
                st.Page(
                    BUS_SESSIONS_PAGE_SPEC.script,
                    title=BUS_SESSIONS_PAGE_SPEC.title,
                    icon=BUS_SESSIONS_PAGE_SPEC.icon,
                    url_path=BUS_SESSIONS_PAGE_SPEC.url_path,
                )
            )
        if group == CAMPAIGNS_PAGE_SPEC.group:
            group_pages.append(
                st.Page(
                    CAMPAIGNS_PAGE_SPEC.script,
                    title=CAMPAIGNS_PAGE_SPEC.title,
                    icon=CAMPAIGNS_PAGE_SPEC.icon,
                    url_path=CAMPAIGNS_PAGE_SPEC.url_path,
                )
            )
        if group == "Platform":
            for platform_spec in (
                PLATFORM_INVENTORY_PAGE_SPEC,
                PLATFORM_FORECASTS_PAGE_SPEC,
                PLATFORM_COMPOSER_PAGE_SPEC,
                PLATFORM_ANALYTICS_PAGE_SPEC,
                PLATFORM_EVIDENCE_MATRIX_PAGE_SPEC,
                PLATFORM_OBSERVATORY_PAGE_SPEC,
                PLATFORM_DECISION_SAFETY_PAGE_SPEC,
                PLATFORM_XAI_AUDIT_PAGE_SPEC,
                MANCHESTER_GATE_D_PAGE_SPEC,
            ):
                group_pages.append(
                    st.Page(
                        platform_spec.script,
                        title=platform_spec.title,
                        icon=platform_spec.icon,
                        url_path=platform_spec.url_path,
                    )
                )
        pages[group] = group_pages
    return pages

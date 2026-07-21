from __future__ import annotations

from pathlib import Path

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.components.badges import STATUS_STYLE
from traffictwin.ui.guided import DemoTrack, bounded_step, steps_for_track
from traffictwin.ui.labels import PAGE_DESCRIPTIONS, UiPage
from traffictwin.ui.navigation import page_options
from traffictwin.ui.pages.run_overview import ENERGY_KPI_KEYS, KPI_KEYS
from traffictwin.ui.services import (
    ServiceError,
    about_info_for_ui,
    build_synthetic_config_from_form,
    generate_synthetic_bundle_for_ui,
    list_workspace_reports,
    load_experiment_manager_view,
    load_research_analysis_view,
    preview_synthetic_scenario,
    regenerate_report_for_ui,
    search_for_ui,
    synthetic_preset_names_for_ui,
)
from traffictwin.ui.state import ReplayFilters, replay_filter_options, replay_window_counts


def _scenario_form() -> dict[str, object]:
    return {
        "scenario_id": "ui-polish-demo",
        "name": "UI polish demo",
        "description": "Synthetic scenario for UI polish tests.",
        "experiment_id": "exp-ui-polish",
        "baseline_seed_id": "",
        "random_seed": 11,
        "duration_s": 120.0,
        "sampling_interval_s": 30.0,
        "vehicle_count": 6,
        "vehicle_low_share": 0.4,
        "vehicle_medium_share": 0.4,
        "vehicle_high_share": 0.2,
        "task_arrival_rate": 0.08,
        "task_mix_t1": 0.3,
        "task_mix_t2": 0.4,
        "task_mix_t3": 0.3,
        "rsu_count": 2,
        "rsu_capacity": 20.0,
        "baseline_network_delay_ms": 45.0,
        "congestion_multiplier": 1.0,
        "policy_behavior": "synthetic-balanced",
        "trip_count": 3,
        "synthetic_faults": "",
        "include_infrastructure": True,
        "include_vehicles": True,
        "include_traffic": True,
        "include_trips": True,
        "include_incidents": True,
    }


def test_navigation_descriptions_cover_all_pages() -> None:
    options = page_options()

    assert UiPage.SCENARIO.value == "Scenario Builder"
    assert UiPage.REPORTS.value in options
    assert UiPage.ABOUT.value in options
    assert set(PAGE_DESCRIPTIONS) == set(UiPage)
    assert STATUS_STYLE["unknown"] == "UNKNOWN"
    assert "baseline" in synthetic_preset_names_for_ui()
    assert "s5_stadium_event_siting" in synthetic_preset_names_for_ui()
    assert UiPage.TRIVIALITY.value in options
    assert KPI_KEYS["Latency P99"] == "task.latency.p99_ms"
    assert set(ENERGY_KPI_KEYS.values()) == {
        "task.energy.mean_per_observed_task_j",
        "task.energy.per_completed_j",
        "task.energy_delay_product.mean_j_ms",
    }


def test_guided_demo_tracks_have_stable_distinct_stages() -> None:
    standalone = steps_for_track(DemoTrack.STANDALONE)
    tos = steps_for_track(DemoTrack.TOS)

    assert standalone[0].target_page is UiPage.EXPERIMENT_PLANNER
    assert standalone[-1].target_page is UiPage.REPORTS
    assert tos[0].target_page is UiPage.TOS_DATA
    assert tos[-1].target_page is UiPage.TOS_TRAINING
    assert len({step.key for step in standalone + tos}) == len(standalone + tos)
    assert all(step.boundary for step in standalone + tos)


def test_guided_demo_stage_index_is_bounded() -> None:
    assert bounded_step(-1, 8) == 0
    assert bounded_step(3, 8) == 3
    assert bounded_step(99, 8) == 7
    assert bounded_step(1, 0) == 0


def test_scenario_builder_preview_and_generation(tmp_path: Path) -> None:
    config = build_synthetic_config_from_form(_scenario_form())

    assert not isinstance(config, ServiceError)
    preview = preview_synthetic_scenario(config)
    assert preview.expected_run_id == "run-ui-polish-demo-11"
    assert "tasks.csv" in preview.expected_files

    generated = generate_synthetic_bundle_for_ui(config, tmp_path / "bundle")
    assert not isinstance(generated, ServiceError)
    assert generated.analysis.analysis_ready
    assert generated.analysis.validation.report.may_import


def test_scenario_builder_rejects_invalid_mix() -> None:
    form = _scenario_form()
    form["task_mix_t1"] = 0.9

    result = build_synthetic_config_from_form(form)

    assert isinstance(result, ServiceError)
    assert "shares must sum" in (result.detail or "")


def test_replay_filter_options_and_filtered_counts(tmp_path: Path) -> None:
    config = build_synthetic_config_from_form(_scenario_form())
    assert not isinstance(config, ServiceError)
    generated = generate_synthetic_bundle_for_ui(config, tmp_path / "replay-bundle")
    assert not isinstance(generated, ServiceError)
    tables = generated.analysis.validation.canonical
    options = replay_filter_options(tables)

    assert options["vehicles"]
    first_vehicle = options["vehicles"][0]
    filtered = replay_window_counts(
        tables,
        90.0,
        filters=ReplayFilters(vehicle_id=first_vehicle),
    )
    unfiltered = replay_window_counts(tables, 90.0)
    assert filtered["task_arrivals"] <= unfiltered["task_arrivals"]


def test_experiment_manager_reports_search_and_about(tmp_path: Path) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    registry = workspace / "registry.sqlite"

    view = load_experiment_manager_view(registry, workspace)
    assert len(view.experiments) >= 2
    assert len(view.runs) == 62
    assert view.bundle_imports
    research = load_research_analysis_view(registry, "exp-standalone-trivial")
    assert not isinstance(research, ServiceError)
    assert "R3" in research.diagnostic_report.triggered_rule_ids
    assert len(research.winner_map.entries) == 1
    assert list_workspace_reports(workspace)
    assert search_for_ui("completion", registry, workspace)

    output = workspace / "reports" / "manual_run.md"
    regenerated = regenerate_report_for_ui("run", workspace / "bundles" / "baseline", output)
    assert isinstance(regenerated, Path)
    assert output.exists()

    about = about_info_for_ui()
    assert about.package_version
    assert about.licence == "Licence not yet specified."
    assert about.generator_version == "1.0"

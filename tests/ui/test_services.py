from __future__ import annotations

from pathlib import Path

from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config
from traffictwin.ui.services import (
    ServiceError,
    build_seed_from_form,
    compare_runs_for_ui,
    default_seed_form_data,
    evaluate_energy_diagnostic_for_ui,
    evaluate_fairness_diagnostic_for_ui,
    list_replay_bundles_for_ui,
    load_project_status,
    validate_bundle_for_ui,
)


def test_validate_bundle_for_ui_computes_existing_library_artifacts() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))

    assert analysis.analysis_ready
    assert analysis.metrics is not None
    assert analysis.metrics.by_key()["task.completion.rate"].value == 1.0
    assert analysis.evidence_pack is not None


def test_rejected_bundle_is_not_analysis_ready() -> None:
    analysis = validate_bundle_for_ui(Path("tests/fixtures/bundles/invalid_manifest"))

    assert not analysis.analysis_ready
    assert analysis.metrics is None
    assert analysis.evidence_pack is None


def test_compare_service_matches_phase3_delta() -> None:
    report = compare_runs_for_ui(
        validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid")),
        validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid")),
    )

    assert isinstance(report, ComparisonReport)
    by_key = {metric.metric_key: metric for metric in report.comparable_metrics}
    assert by_key["task.completion.rate"].absolute_delta == -0.25


def test_seed_form_conversion_validates_with_pydantic() -> None:
    seed = build_seed_from_form(default_seed_form_data())

    assert not isinstance(seed, ServiceError)
    assert seed.seed_id == "s1-ui-demo"


def test_project_status_handles_missing_registry(tmp_path: Path) -> None:
    status = load_project_status(tmp_path / "missing.sqlite")

    assert not status.registry_exists
    assert status.registry_summary is None
    assert status.latest_runs == []
    assert status.canonical_design_version == "TrafficTwin v0.5"


def test_replay_bundle_catalog_reports_vehicle_and_incident_evidence(tmp_path: Path) -> None:
    root = tmp_path / "bundles"
    baseline = write_synthetic_bundle(preset_config("baseline"), root / "baseline")
    stressed = write_synthetic_bundle(
        preset_config("stressed_demand"),
        root / "stressed_demand",
    )

    choices = list_replay_bundles_for_ui(root, current_path=baseline)
    by_path = {choice.path: choice for choice in choices}

    assert by_path[baseline].vehicle_count == 20
    assert by_path[baseline].incident_count == 0
    assert by_path[stressed].incident_count == 1
    assert by_path[stressed].incident_types == ("synthetic_congestion_pulse",)


def test_fairness_diagnostic_service_delegates_to_r7_library(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    analysis = validate_bundle_for_ui(bundle)
    assert analysis.evidence_pack is not None

    result = evaluate_fairness_diagnostic_for_ui(
        analysis.evidence_pack,
        minimum_outcome_gap=0.1,
    )
    invalid = evaluate_fairness_diagnostic_for_ui(
        analysis.evidence_pack,
        dimension="invented",
    )

    assert not isinstance(result, ServiceError)
    assert result.rule_id == "R7"
    assert result.status.value == "triggered"
    assert result.metadata["r7_dimension"] == "vehicle_tier_completion"
    assert isinstance(invalid, ServiceError)


def test_energy_diagnostic_service_delegates_to_r8_library(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(
        preset_config("infrastructure_bottleneck"),
        tmp_path / "energy-candidate",
    )
    analysis = validate_bundle_for_ui(bundle)
    assert analysis.evidence_pack is not None

    result = evaluate_energy_diagnostic_for_ui(analysis.evidence_pack)
    invalid = evaluate_energy_diagnostic_for_ui(
        analysis.evidence_pack,
        minimum_completed_tasks=0,
    )

    assert not isinstance(result, ServiceError)
    assert result.rule_id == "R8"
    assert result.status.value == "triggered"
    assert result.metadata["r8_completed_task_count"] == 10
    assert isinstance(invalid, ServiceError)

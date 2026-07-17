from __future__ import annotations

from pathlib import Path

from traffictwin.metrics.comparison import ComparisonReport
from traffictwin.ui.services import (
    ServiceError,
    build_seed_from_form,
    compare_runs_for_ui,
    default_seed_form_data,
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

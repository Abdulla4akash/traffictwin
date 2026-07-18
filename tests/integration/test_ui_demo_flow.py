from __future__ import annotations

from importlib import import_module
from pathlib import Path

from traffictwin.ui.services import (
    ServiceError,
    compare_runs_for_ui,
    safe_import_bundle_for_ui,
    store_evidence_for_ui,
    store_metrics_for_ui,
    validate_bundle_for_ui,
)


def test_ui_demo_flow_services(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    baseline = validate_bundle_for_ui(Path("tests/fixtures/bundles/baseline_valid"))
    variation = validate_bundle_for_ui(Path("tests/fixtures/bundles/variation_valid"))

    assert baseline.analysis_ready
    assert variation.analysis_ready
    baseline_import = safe_import_bundle_for_ui(baseline.source_path, registry)
    variation_import = safe_import_bundle_for_ui(variation.source_path, registry)
    assert not isinstance(baseline_import, ServiceError)
    assert not isinstance(variation_import, ServiceError)
    assert baseline_import.run_id == "run-baseline-001"
    assert variation_import.run_id == "run-variation-001"
    assert baseline.metrics is not None
    assert variation.metrics is not None
    assert baseline.evidence_pack is not None
    assert variation.evidence_pack is not None
    store_metrics_for_ui(registry, baseline.metrics)
    store_metrics_for_ui(registry, variation.metrics)
    store_evidence_for_ui(registry, baseline.evidence_pack)
    report = compare_runs_for_ui(baseline, variation)

    assert not isinstance(report, ServiceError)
    by_key = {metric.metric_key: metric for metric in report.comparable_metrics}
    assert by_key["task.completion.rate"].absolute_delta == -0.25
    assert by_key["trip.duration.mean_s"].absolute_delta == 330.0


def test_streamlit_app_starts_with_apptest() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)

    assert not app.exception


def test_streamlit_provenance_page_renders_with_apptest() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Provenance Explorer").run(timeout=10)

    assert not app.exception


def test_home_starts_and_advances_guided_demo() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    next(button for button in app.button if button.label == "Start Guided Demo").click().run(
        timeout=10
    )

    assert not app.exception
    assert any(title.value == "Guided Demo" for title in app.title)
    assert any(
        heading.value == "Stage 1 of 8: Frame a reproducible experiment"
        for heading in app.subheader
    )

    next(button for button in app.button if button.label == "Next stage").click().run(timeout=10)

    assert not app.exception
    assert any(heading.value == "Stage 2 of 8: Validate a run bundle" for heading in app.subheader)


def test_guided_demo_tos_track_has_honest_empty_state() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Guided Demo").run(timeout=10)
    next(radio for radio in app.radio if radio.label == "Evidence track").set_value(
        "Randy/TOS imported simulation"
    ).run(timeout=10)

    assert not app.exception
    assert any(
        heading.value == "Stage 1 of 4: Inspect Randy's artifact package"
        for heading in app.subheader
    )
    assert any(button.label == "Open TOS Data Import" for button in app.button)

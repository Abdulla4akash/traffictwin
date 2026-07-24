from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest

from traffictwin.demo.workspace import initialise_workspace
from traffictwin.diagnostics.temporal import TemporalDiagnosticAnalysis
from traffictwin.diagnostics.threshold_sweep import ThresholdSensitivityReport
from traffictwin.ingestion.batch import BatchBundleSummary
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config
from traffictwin.ui.services import (
    ServiceError,
    compare_runs_for_ui,
    safe_import_bundle_for_ui,
    store_evidence_for_ui,
    store_metrics_for_ui,
    validate_bundle_for_ui,
)


@pytest.fixture(autouse=True)
def _use_legacy_router_for_navigation_integration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the radio-driven integration suite through its explicit legacy router."""

    monkeypatch.setenv("TRAFFICTWIN_V07_NAVIGATION", "legacy")


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
    assert by_key["task.latency.p99_ms"].absolute_delta == pytest.approx(237.6)
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
    assert any(tab.label == "Graph" for tab in app.tabs)
    assert any(item.label == "Inspect graph node" for item in app.selectbox)
    assert any(button.label == "Download bounded graph DOT" for button in app.download_button)
    assert any(button.label == "Download bounded graph GraphML" for button in app.download_button)
    assert any(
        item.label == "Completeness report template" and item.value == "run"
        for item in app.selectbox
    )
    assert any(button.label == "Download completeness JSON" for button in app.download_button)
    assert any(button.label == "Download completeness CSV" for button in app.download_button)


def test_streamlit_comparison_page_renders_difference_provenance() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Comparison").run(timeout=10)

    assert not app.exception
    assert any(heading.value == "Difference provenance" for heading in app.subheader)
    selector = next(item for item in app.selectbox if item.label == "Difference provenance metric")
    assert selector.value == "task.completion.rate"
    assert any(button.label == "Download difference lineage JSON" for button in app.download_button)
    assert any(button.label == "Download difference lineage CSV" for button in app.download_button)
    assert any(heading.value == "Comparison provenance completeness" for heading in app.subheader)
    assert any(
        button.label == "Download comparison completeness JSON" for button in app.download_button
    )
    assert any(
        button.label == "Download comparison completeness CSV" for button in app.download_button
    )


def test_streamlit_diagnostics_page_retains_results_and_renders_cross_rule_analysis() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Diagnostics & Evidence").run(timeout=10)

    assert not app.exception
    assert any(heading.value == "Cross-Rule Relationships" for heading in app.subheader)
    assert any(heading.value == "Original Rule Results" for heading in app.subheader)
    assert any(metric.label == "Retained results" and metric.value == "9" for metric in app.metric)
    assert any(
        button.label == "Download CrossRuleReasoningReport JSON" for button in app.download_button
    )


def test_streamlit_temporal_metrics_page_computes_series_with_apptest() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Temporal Metrics").run(timeout=10)
    next(button for button in app.button if button.label == "Compute Windowed Metrics").click().run(
        timeout=10
    )

    series = app.session_state["windowed_metric_series"]
    assert not app.exception
    assert series.included_window_count == 6
    assert series.included_empty_window_count == 4
    assert any(item.label == "Applicable metrics" and item.value == "60" for item in app.metric)
    assert len(app.dataframe) == 1

    next(button for button in app.button if button.label == "Evaluate R6").click().run(timeout=10)
    diagnosis = app.session_state["temporal_diagnostic_analysis"]
    assert not app.exception
    assert isinstance(diagnosis, TemporalDiagnosticAnalysis)
    assert diagnosis.r6_result.rule_id == "R6"
    assert any(item.label == "R6 status" for item in app.metric)


def test_streamlit_spatial_rsu_page_renders_contracted_synthetic_evidence(
    tmp_path: Path,
) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.session_state["selected_bundle_path"] = str(bundle)
    app.radio[0].set_value("Spatial & RSU Evidence").run(timeout=10)

    assert not app.exception
    assert any(
        heading.value == "Task Outcomes By Execution-Target RSU" for heading in app.subheader
    )
    assert any(heading.value == "Vehicle Source-Frame Grid" for heading in app.subheader)
    assert len(app.dataframe) == 2


def test_streamlit_batch_bundle_controls_validate_mixed_input() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Bundle Import & Validation").run(timeout=10)
    batch_inputs = next(
        item for item in app.text_area if item.label == "Bundle paths or glob patterns"
    )
    batch_inputs.set_value(
        "tests/fixtures/bundles/baseline_valid\ntests/fixtures/bundles/invalid_manifest"
    ).run(timeout=10)
    next(button for button in app.button if button.label == "Validate Batch").click().run(
        timeout=10
    )

    summary = app.session_state["bundle_batch_summary"]
    assert not app.exception
    assert isinstance(summary, BatchBundleSummary)
    assert summary.accepted_count == 1
    assert summary.rejected_count == 1
    assert any(heading.value == "Per-bundle outcomes" for heading in app.subheader)


def test_streamlit_chunked_bundle_controls_render_validation() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Bundle Import & Validation").run(timeout=10)
    next(
        toggle
        for toggle in app.toggle
        if toggle.label == "Use chunked canonicalisation for a large bundle"
    ).set_value(True).run(timeout=10)
    next(button for button in app.button if button.label == "Stream Validate").click().run(
        timeout=10
    )

    assert not app.exception
    assert any(heading.value == "Chunked canonicalisation" for heading in app.subheader)
    result = app.session_state["streaming_bundle_result"]
    assert result.report.may_import
    assert result.streaming.canonical_record_counts["tasks"] == 3


def test_streamlit_replay_filters_are_selectable_and_persist(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.session_state["selected_bundle_path"] = str(bundle)
    app.radio[0].set_value("Replay").run(timeout=10)

    next(button for button in app.button if button.label == "veh-002").click().run(timeout=10)
    next(item for item in app.selectbox if item.label == "RSU").set_value("rsu-2").run(timeout=10)
    next(item for item in app.selectbox if item.label == "Task class").set_value("T2").run(
        timeout=10
    )

    assert not app.exception
    assert app.session_state["replay_filter_vehicle"] == "veh-002"
    assert next(item for item in app.selectbox if item.label == "RSU").value == "rsu-2"
    assert next(item for item in app.selectbox if item.label == "Task class").value == "T2"

    next(button for button in app.button if button.label == "Next").click().run(timeout=10)
    assert app.session_state["replay_filter_vehicle"] == "veh-003"
    next(button for button in app.button if button.label == "Previous").click().run(timeout=10)
    assert app.session_state["replay_filter_vehicle"] == "veh-002"

    app.radio[0].set_value("Home").run(timeout=10)
    app.radio[0].set_value("Replay").run(timeout=10)

    assert app.session_state["replay_filter_vehicle"] == "veh-002"
    assert next(item for item in app.selectbox if item.label == "RSU").value == "rsu-2"
    assert next(item for item in app.selectbox if item.label == "Task class").value == "T2"


def test_streamlit_replay_opens_with_selectable_incident_demo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = tmp_path / "bundles"
    write_synthetic_bundle(preset_config("baseline"), bundle_root / "baseline")
    stressed = write_synthetic_bundle(
        preset_config("stressed_demand"),
        bundle_root / "stressed_demand",
    )
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(bundle_root))
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(tmp_path))

    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Replay").run(timeout=10)

    source = next(item for item in app.selectbox if item.label == "Replay dataset")
    incident = next(item for item in app.selectbox if item.label == "Incident")

    assert not app.exception
    assert source.value == str(stressed)
    assert any(button.label == "veh-001" for button in app.button)
    assert not incident.disabled
    assert "synthetic_congestion_pulse" in incident.options

    next(button for button in app.button if button.label == "veh-002").click().run(timeout=10)
    next(item for item in app.selectbox if item.label == "Incident").set_value(
        "synthetic_congestion_pulse"
    ).run(timeout=10)

    assert app.session_state["replay_filter_vehicle"] == "veh-002"
    assert (
        next(item for item in app.selectbox if item.label == "Incident").value
        == "synthetic_congestion_pulse"
    )


def test_streamlit_triviality_page_renders_demo_analysis(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Triviality & Winner Map").run(timeout=10)

    assert not app.exception
    assert any(title.value == "Triviality & Winner Map" for title in app.title)
    assert any(heading.value == "Per-Seed Winner Map" for heading in app.subheader)


def test_streamlit_run_overview_renders_contract_gated_energy_family(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Run Overview").run(timeout=10)

    energy_cards = {
        item.label: item.value
        for item in app.metric
        if item.label
        in {
            "Observed-task energy (J)",
            "Completed-task energy (J)",
            "Energy-delay product (J·ms)",
        }
    }
    assert not app.exception
    assert any(heading.value == "Energy Evidence" for heading in app.subheader)
    assert set(energy_cards) == {
        "Observed-task energy (J)",
        "Completed-task energy (J)",
        "Energy-delay product (J·ms)",
    }
    assert all(value != "Unavailable" for value in energy_cards.values())
    assert any(
        "d71e4d10bb37…" in caption.value and "Observed-task energy: 31/33" in caption.value
        for caption in app.caption
    )


def test_streamlit_fairness_page_renders_supported_groups_and_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Fairness Evidence").run(timeout=10)

    expected_cards = {
        "Vehicle-tier completion gap",
        "Vehicle-tier completion Jain index",
        "RSU normalised-load gap",
        "RSU normalised-load Jain index",
    }
    assert not app.exception
    assert any(title.value == "Fairness Evidence" for title in app.title)
    assert expected_cards <= {metric.label for metric in app.metric}
    assert len(app.dataframe) == 2
    assert next(metric for metric in app.metric if metric.label == "R7 status").value
    dimension = next(item for item in app.selectbox if item.label == "R7 dimension")
    assert dimension.value == "Vehicle-tier completion"
    assert any(
        "7518652f882ea2928b4fcc6c500af9fa81e2bf6d88fcb0ed655d7be46ede0e6e" in caption.value
        for caption in app.caption
    )

    dimension.set_value("Exact target-RSU completion").run(timeout=10)

    assert not app.exception
    assert next(metric for metric in app.metric if metric.label == "Selected dimension").value == (
        "target_rsu_completion"
    )


def test_streamlit_energy_page_renders_r8_controls_and_reacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(workspace / "registry.sqlite"))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Energy Evidence").run(timeout=10)

    assert not app.exception
    assert any(title.value == "Energy Evidence" for title in app.title)
    assert next(metric for metric in app.metric if metric.label == "R8 status").value == (
        "not_triggered"
    )
    assert any(button.label == "Download R8 result (JSON)" for button in app.download_button)
    threshold = next(
        item
        for item in app.number_input
        if item.label == "Minimum energy per completed task (J/task)"
    )
    threshold.set_value(0.9).run(timeout=10)

    assert not app.exception
    assert next(metric for metric in app.metric if metric.label == "R8 status").value == "triggered"


def test_streamlit_threshold_sensitivity_runs_full_r8_grid_without_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "demo"
    initialise_workspace(workspace)
    registry = workspace / "registry.sqlite"
    registry_before = registry.read_bytes()
    monkeypatch.setenv("TRAFFICTWIN_WORKSPACE_PATH", str(workspace))
    monkeypatch.setenv("TRAFFICTWIN_REGISTRY_PATH", str(registry))
    monkeypatch.setenv("TRAFFICTWIN_FIXTURE_PATH", str(workspace / "bundles"))
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("Threshold Sensitivity").run(timeout=10)
    rule = next(item for item in app.selectbox if item.label == "Rule threshold")
    rule.set_value("R8 — completed-task energy").run(timeout=10)
    next(button for button in app.button if button.label == "Run Threshold Sweep").click().run(
        timeout=10
    )

    report = app.session_state["threshold_sensitivity_report"]
    assert not app.exception
    assert isinstance(report, ThresholdSensitivityReport)
    assert report.capability == "DIA-06"
    assert report.rule_id == "R8"
    assert report.evaluated_point_count == 11
    assert any(metric.label == "Triggered points" for metric in app.metric)
    assert len(app.dataframe) >= 1
    assert any(
        button.label == "Export selected point as complete RuleSetConfig JSON"
        for button in app.download_button
    )
    assert any(
        button.label == "Download complete threshold-sensitivity report (JSON)"
        for button in app.download_button
    )
    assert registry.read_bytes() == registry_before


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

    next(button for button in app.button if button.label == "Start guided workflow").click().run(
        timeout=10
    )

    assert not app.exception
    assert any(title.value == "Experiment Planner" for title in app.title)
    assert any(button.label == "Waiting for task" for button in app.button)
    assert any("stage 1 of 8" in caption.value for caption in app.caption)

    next(button for button in app.button if button.label == "Skip").click().run(timeout=10)

    assert not app.exception
    assert any(title.value == "Bundle Import & Validation" for title in app.title)
    assert any(button.label == "Reviewed — continue" for button in app.button)
    assert any("stage 2 of 8" in caption.value for caption in app.caption)

    next(button for button in app.button if button.label == "Reviewed — continue").click().run(
        timeout=10
    )

    assert not app.exception
    assert any(title.value == "Run Overview" for title in app.title)
    assert any("stage 3 of 8" in caption.value for caption in app.caption)


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
    next(button for button in app.button if button.label == "Start guided workflow").click().run(
        timeout=10
    )

    assert not app.exception
    assert any(title.value == "TOS Data Import" for title in app.title)
    assert any(button.label == "Reviewed — continue" for button in app.button)
    assert any("stage 1 of 4" in caption.value for caption in app.caption)


def test_streamlit_about_page_exposes_safe_extension_boundaries() -> None:
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app = app_test.from_file("src/traffictwin/ui/app.py")
    app.run(timeout=10)
    app.radio[0].set_value("About").run(timeout=10)

    assert not app.exception
    assert any(heading.value == "Trusted Metric Extensions" for heading in app.subheader)
    assert any(heading.value == "Trusted Declarative Rules" for heading in app.subheader)
    assert any(
        "does not upload" in warning.value and "not a sandbox" in warning.value
        for warning in app.warning
    )
    assert any(
        "There is no YAML upload" in warning.value and "not a sandbox" in warning.value
        for warning in app.warning
    )

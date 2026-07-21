"""Real-report, CLI, source snapshot, and UI acceptance for VEC-10."""

from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path

import pytest
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.vec_interface import (
    compare_vec_admissions,
    export_vec_admission,
    inspect_vec_artifact,
    inspect_vec_interface,
    load_scientific_admission,
    vec_interface_contract,
)
from traffictwin.ui.labels import UiPage
from traffictwin.ui.navigation import page_options

ROOT = Path(__file__).parents[2]
REPORT = ROOT / "docs/reference/generated/vec_scientific_admission_report.json"
CONTRACT = ROOT / "docs/reference/generated/vec_interface_contract.json"
VERIFICATION = ROOT / "docs/reference/generated/vec_interface_verification.json"
VEC_REPO = ROOT.parent / "external/vec_env"
TOS_REPO = ROOT.parent / "external/tos-data"


def test_real_admission_inspect_compare_and_exports_are_non_causal() -> None:
    report = load_scientific_admission(REPORT)
    inspection = inspect_vec_artifact(REPORT)
    comparison = compare_vec_admissions(report, report)

    assert inspection.artifact_type == "scientific_admission_report"
    assert inspection.summary["metric_count"] == 26
    assert len(comparison.comparable_metrics) == 16
    assert len(comparison.unavailable_or_incompatible_metrics) == 10
    assert all(item.variation_minus_baseline == 0 for item in comparison.comparable_metrics)
    assert comparison.causal_interpretation is False
    assert export_vec_admission(report, "json").endswith("\n")
    assert export_vec_admission(report, "csv").count("\n") == 27
    markdown = export_vec_admission(report, "markdown")
    assert "Deadline success is not physical completion" in markdown
    assert "R6**: conditional" in markdown


def test_generated_contract_and_real_verification_match_the_library() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    verification = json.loads(VERIFICATION.read_text(encoding="utf-8"))

    assert contract == vec_interface_contract().model_dump(mode="json")
    assert verification["status"] == "accepted"
    assert verification["contract_fingerprint"] == vec_interface_contract().fingerprint()
    assert verification["self_comparison"]["comparable_metric_count"] == 16
    assert verification["direct_launch"] == "conditional_on_request_specific_preflight"
    assert verification["persistent_async_queue"] is False
    assert verification["external_source_unchanged"] is True
    raw = VERIFICATION.read_text(encoding="utf-8")
    assert "/Users/" not in raw
    assert "/private/" not in raw
    assert "akash" not in raw.lower()


def test_cli_contract_inspect_compare_export_and_monitor(tmp_path: Path) -> None:
    runner = CliRunner()
    contract_result = runner.invoke(app, ["integration", "vec", "contract", "--format", "json"])
    inspect_result = runner.invoke(app, ["integration", "vec", "inspect", str(REPORT)])
    monitor_result = runner.invoke(app, ["integration", "vec", "monitor-current"])
    comparison = tmp_path / "comparison.json"
    compare_result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "compare",
            str(REPORT),
            str(REPORT),
            "--output",
            str(comparison),
        ],
    )
    exported = tmp_path / "metrics.csv"
    export_result = runner.invoke(
        app,
        [
            "integration",
            "vec",
            "export",
            str(REPORT),
            "--format",
            "csv",
            "--output",
            str(exported),
        ],
    )

    assert contract_result.exit_code == 0
    assert json.loads(contract_result.output) == vec_interface_contract().model_dump(mode="json")
    assert inspect_result.exit_code == 0
    assert '"artifact_type": "scientific_admission_report"' in inspect_result.output
    assert monitor_result.exit_code == 0
    assert "persistent_async_queue: false" in monitor_result.output
    assert compare_result.exit_code == 0
    assert comparison.is_file()
    assert export_result.exit_code == 0
    assert exported.read_text(encoding="utf-8").startswith("metric_key,status,value")


def test_real_source_snapshot_is_read_only_and_ready_when_repositories_exist() -> None:
    if not VEC_REPO.is_dir() or not TOS_REPO.is_dir():
        pytest.skip("reviewed external repositories are not available")
    snapshot = inspect_vec_interface(VEC_REPO, TOS_REPO)

    assert all(item.ready_for_exact_blob_access for item in snapshot.repositories)
    operations = {item.operation: item for item in snapshot.operations}
    assert operations["run"].availability.value == "conditional"
    assert snapshot.persistent_async_queue is False


def test_vec_workbench_renders_with_execution_gated() -> None:
    assert UiPage.VEC_WORKBENCH.value in page_options()
    app_test = vars(import_module("streamlit.testing.v1"))["AppTest"]
    app_state = app_test.from_file("src/traffictwin/ui/app.py")
    app_state.run(timeout=15)
    app_state.radio[0].set_value(UiPage.VEC_WORKBENCH.value).run(timeout=15)

    assert not app_state.exception
    assert any(title.value == UiPage.VEC_WORKBENCH.value for title in app_state.title)
    assert any(button.label == "Validate typed request" for button in app_state.button)
    execute = [
        button
        for button in app_state.button
        if button.label in {"Execute preprocessing", "Run evaluator in foreground"}
    ]
    assert len(execute) == 1
    assert execute[0].disabled

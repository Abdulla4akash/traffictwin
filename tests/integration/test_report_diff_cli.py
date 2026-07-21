from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")


def test_report_diff_cli_generates_structured_json_and_markdown(tmp_path: Path) -> None:
    baseline_report = tmp_path / "baseline.json"
    variation_report = tmp_path / "variation.json"
    baseline = CliRunner().invoke(
        app,
        ["report", "run", str(BASELINE), "--output", str(baseline_report)],
    )
    variation = CliRunner().invoke(
        app,
        ["report", "run", str(VARIATION), "--output", str(variation_report)],
    )
    json_output = tmp_path / "diff.json"
    json_result = CliRunner().invoke(
        app,
        [
            "report",
            "diff",
            str(baseline_report),
            str(variation_report),
            "--output",
            str(json_output),
        ],
    )
    markdown_output = tmp_path / "diff.md"
    markdown_result = CliRunner().invoke(
        app,
        [
            "report",
            "diff",
            str(baseline_report),
            str(variation_report),
            "--output",
            str(markdown_output),
        ],
    )

    assert baseline.exit_code == 0, baseline.output
    assert variation.exit_code == 0, variation.output
    assert json_result.exit_code == 0, json_result.output
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["status"] == "available"
    assert payload["classification_counts"]["changed"] >= 1
    metrics = next(item for item in payload["sections"] if item["section"] == "Metrics")
    assert metrics["classification"] == "changed"
    assert markdown_result.exit_code == 0, markdown_result.output
    markdown = markdown_output.read_text(encoding="utf-8")
    assert "Structured Report Diff" in markdown
    assert "descriptive and non-causal" in markdown
    assert "analyst_annotations" in markdown


def test_report_diff_cli_contract_and_incompatible_payload(tmp_path: Path) -> None:
    contract = CliRunner().invoke(app, ["report", "diff-contract", "--format", "json"])
    run_path = tmp_path / "run.json"
    diagnostic_path = tmp_path / "diagnostics.json"
    CliRunner().invoke(
        app,
        ["report", "run", str(BASELINE), "--output", str(run_path)],
    )
    CliRunner().invoke(
        app,
        ["report", "diagnostics", str(BASELINE), "--output", str(diagnostic_path)],
    )
    output = tmp_path / "unavailable.json"
    result = CliRunner().invoke(
        app,
        [
            "report",
            "diff",
            str(run_path),
            str(diagnostic_path),
            "--output",
            str(output),
        ],
    )

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["contract_version"] == "structured-report-diff-v1"
    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "unavailable"
    assert "REPORT_TYPE_MISMATCH" in payload["compatibility_codes"]

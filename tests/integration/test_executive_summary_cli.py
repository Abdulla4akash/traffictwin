from __future__ import annotations

import json
from pathlib import Path

from pypdf import PdfReader
from typer.testing import CliRunner

from traffictwin.cli import app

BASELINE = Path("tests/fixtures/bundles/baseline_valid")


def test_executive_summary_cli_exports_all_formats(tmp_path: Path) -> None:
    source = tmp_path / "source-report.json"
    source_result = CliRunner().invoke(
        app,
        ["report", "run", str(BASELINE), "--output", str(source)],
    )
    outputs = {
        suffix: tmp_path / f"executive{suffix}" for suffix in (".json", ".md", ".html", ".pdf")
    }
    results = {
        suffix: CliRunner().invoke(
            app,
            ["report", "executive", str(source), "--output", str(output)],
        )
        for suffix, output in outputs.items()
    }

    assert source_result.exit_code == 0, source_result.output
    assert all(result.exit_code == 0 for result in results.values())
    payload = json.loads(outputs[".json"].read_text(encoding="utf-8"))
    assert payload["contract_version"] == "executive-summary-v1"
    assert payload["source_mode"] == "synthetic"
    assert payload["availability"]["total_claims"] == 33
    assert payload["mandatory_warning_count"] == 3
    assert len(payload["warnings"]) == 3
    assert "Warnings - All Retained" in outputs[".md"].read_text(encoding="utf-8")
    assert "Warnings - all retained" in outputs[".html"].read_text(encoding="utf-8")
    assert len(PdfReader(outputs[".pdf"]).pages) == 1
    assert "warnings_retained: 3" in results[".pdf"].output


def test_executive_summary_cli_contract_and_invalid_suffix(tmp_path: Path) -> None:
    contract = CliRunner().invoke(app, ["report", "executive-contract", "--format", "json"])
    source = tmp_path / "source-report.json"
    CliRunner().invoke(
        app,
        ["report", "run", str(BASELINE), "--output", str(source)],
    )
    invalid = CliRunner().invoke(
        app,
        ["report", "executive", str(source), "--output", str(tmp_path / "summary.txt")],
    )

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["pdf_overflow_policy"] == "fail_closed"
    assert invalid.exit_code == 1
    assert "must use .json" in invalid.output

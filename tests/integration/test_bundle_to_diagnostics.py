from __future__ import annotations

from typer.testing import CliRunner

from traffictwin.cli import app

runner = CliRunner()


def test_cli_diagnose_report_for_bundle_outputs_json() -> None:
    result = runner.invoke(
        app,
        [
            "diagnose",
            "report",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    assert '"evidence_pack_id"' in result.output
    assert '"triggered_rule_ids": []' in result.output


def test_cli_diagnose_bundle_rejects_invalid_bundle() -> None:
    result = runner.invoke(app, ["diagnose", "bundle", "tests/fixtures/bundles/invalid_rows"])

    assert result.exit_code == 1
    assert "ordinary hypotheses are suppressed" in result.output

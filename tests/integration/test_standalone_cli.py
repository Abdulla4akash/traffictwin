from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app


def test_standalone_cli_workspace_report_and_provenance(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "demo"

    init = runner.invoke(app, ["demo", "initialise", str(workspace)])
    assert init.exit_code == 0, init.output

    status = runner.invoke(app, ["demo", "status", str(workspace)])
    assert status.exit_code == 0, status.output
    assert "synthetic: true" in status.output

    report = runner.invoke(
        app,
        [
            "report",
            "run",
            str(workspace / "bundles" / "baseline"),
            "--output",
            str(workspace / "reports" / "cli_report.md"),
        ],
    )
    assert report.exit_code == 0, report.output

    provenance = runner.invoke(
        app,
        [
            "provenance",
            "export",
            str(workspace / "bundles" / "baseline"),
            "--root-type",
            "metric",
            "--root-id",
            "task.completion.rate",
            "--format",
            "json",
            "--output",
            str(workspace / "exports" / "cli_trace.json"),
        ],
    )
    assert provenance.exit_code == 0, provenance.output
    assert (workspace / "exports" / "cli_trace.json").exists()


def test_demo_launch_dry_run(tmp_path: Path) -> None:
    runner = CliRunner()
    workspace = tmp_path / "demo"

    result = runner.invoke(app, ["demo", "launch", str(workspace), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "streamlit run" in result.output
    assert "dry_run: true" in result.output

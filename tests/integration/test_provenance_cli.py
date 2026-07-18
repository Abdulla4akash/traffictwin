from __future__ import annotations

import json

from typer.testing import CliRunner

from traffictwin.cli import app


def test_provenance_cli_exports_metric_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "metric",
            "tests/fixtures/bundles/baseline_valid",
            "task.completion.rate",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root_node_id"] == "metric_result:run-baseline-001:task.completion.rate"


def test_provenance_cli_source_preview_text() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "source",
            "tests/fixtures/bundles/baseline_valid",
            "tasks.csv",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "source: tasks.csv:2" in result.output
    assert "canonical_record_type: TaskRecord" in result.output

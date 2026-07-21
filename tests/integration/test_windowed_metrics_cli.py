from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app


def test_windowed_metrics_cli_emits_complete_json_contract() -> None:
    result = CliRunner().invoke(
        app,
        [
            "metrics",
            "windows",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "60",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["boundary"] == "[start,end)"
    assert payload["range_source"] == "inferred_aligned_envelope"
    assert payload["included_window_count"] == 6
    assert payload["included_empty_window_count"] == 4
    assert len(payload["slices"][0]["metrics"]["results"]) == 60
    first_window_metrics = {
        item["metric_key"]: item for item in payload["slices"][0]["metrics"]["results"]
    }
    assert first_window_metrics["task.latency.p99_ms"]["value"] == 178.8


def test_windowed_metrics_cli_records_excluded_partial_windows() -> None:
    result = CliRunner().invoke(
        app,
        [
            "metrics",
            "windows",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "5",
            "--start-s",
            "2",
            "--end-s",
            "8",
            "--partial-windows",
            "exclude",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["included_window_count"] == 0
    assert payload["excluded_partial_window_count"] == 2
    assert all(item["metrics"] is None for item in payload["slices"])


def test_windowed_metrics_cli_rejects_incomplete_range() -> None:
    result = CliRunner().invoke(
        app,
        [
            "metrics",
            "windows",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "60",
            "--start-s",
            "0",
        ],
    )

    assert result.exit_code == 1
    assert "invalid window configuration" in result.stderr


def test_windowed_metrics_cli_writes_json(tmp_path: Path) -> None:
    output = tmp_path / "windows.json"
    result = CliRunner().invoke(
        app,
        [
            "metrics",
            "windows",
            "tests/fixtures/bundles/baseline_valid",
            "--width-s",
            "60",
            "--format",
            "json",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "windowed metric series written" in result.stdout
    assert json.loads(output.read_text(encoding="utf-8"))["included_window_count"] == 6


def test_window_metric_provenance_cli_filters_source_rows() -> None:
    result = CliRunner().invoke(
        app,
        [
            "provenance",
            "window-metric",
            "tests/fixtures/bundles/baseline_valid",
            "task.generated.count",
            "--width-s",
            "5",
            "--window-ordinal",
            "0",
            "--start-s",
            "0",
            "--end-s",
            "10",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    rows = {
        node["attributes"]["row"] for node in payload["nodes"] if node["node_type"] == "source_row"
    }
    assert rows == {2}


def test_window_metric_contributors_cli_exports_complete_filtered_ledger() -> None:
    result = CliRunner().invoke(
        app,
        [
            "provenance",
            "window-contributors",
            "tests/fixtures/bundles/baseline_valid",
            "task.generated.count",
            "--width-s",
            "5",
            "--window-ordinal",
            "0",
            "--start-s",
            "0",
            "--end-s",
            "10",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["window"]["boundary"] == "[start,end)"
    ledger = payload["contribution_report"]
    assert ledger["complete_row_ledger"] is True
    assert ledger["candidate_row_count"] == 1
    assert ledger["rows"][0]["record_id"] == "t1"

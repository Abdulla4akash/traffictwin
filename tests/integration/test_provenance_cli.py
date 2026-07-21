from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

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


def test_provenance_cli_contributors_csv(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "contributors.csv"
    result = runner.invoke(
        app,
        [
            "provenance",
            "contributors",
            "tests/fixtures/bundles/baseline_valid",
            "task.latency.mean_ms",
            "--format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8").startswith("metric_key,canonical_table")


def test_provenance_cli_exports_arithmetic_difference_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "difference-contributors",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/variation_valid",
            "task.completion.rate",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capability_id"] == "PRO-01"
    assert payload["status"] == "arithmetic"
    assert payload["absolute_delta"] == -0.25
    assert payload["reconciles_to_absolute_delta"] is True
    assert "does not establish" in payload["non_causality_statement"]


def test_provenance_cli_exports_lineage_only_csv(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "difference.csv"
    result = runner.invoke(
        app,
        [
            "provenance",
            "difference-contributors",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/variation_valid",
            "task.latency.p95_ms",
            "--format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = output.read_text(encoding="utf-8")
    assert "lineage_only" in payload
    assert "does not establish" in payload


def test_provenance_difference_contract_is_public() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["provenance", "difference-contract"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capability_id"] == "PRO-01"
    assert payload["unavailable_is_not_zero"] is True


def test_provenance_graph_contract_is_public() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["provenance", "graph-contract"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capability_id"] == "PRO-02"
    assert payload["formats"] == ["dot", "graphml"]
    assert payload["default_redaction_mode"] == "safe"


def test_provenance_completeness_contract_is_public() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["provenance", "completeness-contract"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capability_id"] == "PRO-03"
    assert payload["supported_report_types"] == ["run", "diagnostics", "comparison", "full"]
    assert payload["unavailable_is_not_zero"] is True


def test_provenance_cli_exports_complete_run_claim_inventory() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "completeness",
            "tests/fixtures/bundles/baseline_valid",
            "--report-type",
            "run",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capability_id"] == "PRO-03"
    assert payload["denominator_count"] == 33
    assert payload["source_row_complete_count"] == 12
    assert payload["aggregate_only_count"] == 1
    assert payload["unavailable_count"] == 20
    assert len(payload["claims"]) == 33


def test_provenance_cli_writes_completeness_csv_without_dropping_unavailable(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    output = tmp_path / "completeness.csv"
    result = runner.invoke(
        app,
        [
            "provenance",
            "completeness",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "csv",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    rows = output.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 34
    assert any(",unavailable," in row for row in rows[1:])


def test_provenance_cli_exports_comparison_completeness_text() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "comparison-completeness",
            "tests/fixtures/bundles/baseline_valid",
            "tests/fixtures/bundles/variation_valid",
            "--format",
            "text",
        ],
    )

    assert result.exit_code == 0
    assert "report_type: comparison" in result.output
    assert "score: 0.500000" in result.output
    assert "denominator: 14" in result.output


def test_provenance_cli_rejects_unknown_completeness_report_type() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "provenance",
            "completeness",
            "tests/fixtures/bundles/baseline_valid",
            "--report-type",
            "external",
        ],
    )

    assert result.exit_code == 1
    assert "use the comparison completeness query" in result.output


def test_provenance_cli_exports_bounded_dot(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "metric.dot"
    result = runner.invoke(
        app,
        [
            "provenance",
            "export",
            "tests/fixtures/bundles/baseline_valid",
            "--root-type",
            "metric",
            "--root-id",
            "task.completion.rate",
            "--format",
            "dot",
            "--max-nodes",
            "8",
            "--max-edges",
            "10",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    payload = output.read_text(encoding="utf-8")
    assert payload.startswith("digraph TrafficTwinProvenance")
    assert payload.count("[label=") <= 18
    assert str(tmp_path) not in payload


def test_provenance_cli_exports_structure_only_graphml(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "metric.graphml"
    result = runner.invoke(
        app,
        [
            "provenance",
            "export",
            "tests/fixtures/bundles/baseline_valid",
            "--root-type",
            "metric",
            "--root-id",
            "task.completion.rate",
            "--format",
            "graphml",
            "--redaction",
            "structure_only",
            "--max-nodes",
            "9",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    root = ElementTree.fromstring(  # noqa: S314 - parses local serializer output
        output.read_text(encoding="utf-8")
    )
    namespace = {"g": "http://graphml.graphdrawing.org/xmlns"}
    assert len(root.findall(".//g:node", namespace)) == 9
    attribute_values = [
        element.text for element in root.findall(".//g:data[@key='n_attributes']", namespace)
    ]
    assert set(attribute_values) == {"{}"}

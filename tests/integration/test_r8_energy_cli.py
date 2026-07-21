from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config


def test_r8_energy_cli_exposes_threshold_support_and_provenance(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(
        preset_config("infrastructure_bottleneck"),
        tmp_path / "energy-candidate",
    )

    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "energy",
            str(bundle),
            "--minimum-energy-per-completed-task-j",
            "1.5",
            "--minimum-completed-tasks",
            "10",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["rule_id"] == "R8"
    assert payload["status"] == "triggered"
    assert payload["metadata"]["r8_minimum_energy_per_completed_task_j"] == 1.5
    assert payload["metadata"]["r8_minimum_completed_tasks"] == 10
    assert payload["metadata"]["r8_completed_task_count"] == 10
    assert payload["metadata"]["r8_energy_contract_fingerprint"]

    provenance = CliRunner().invoke(
        app,
        ["provenance", "rule", str(bundle), "R8", "--format", "json"],
    )
    assert provenance.exit_code == 0
    trace = json.loads(provenance.stdout)
    rule_node = next(node for node in trace["nodes"] if node["node_id"] == "rule_result:R8")
    assert rule_node["attributes"]["result_metadata"]["r8_energy_contract_fingerprint"]
    assert any(node["node_type"] == "metric_result" for node in trace["nodes"])
    assert any(node["node_type"] == "source_row" for node in trace["nodes"])


def test_r8_energy_cli_reports_explicit_insufficiency_without_contract() -> None:
    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "energy",
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "insufficient_evidence"
    assert any("metric status is unavailable" in item for item in payload["missing_evidence"])


def test_r8_energy_cli_rejects_invalid_configuration(tmp_path: Path) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "energy",
            str(bundle),
            "--minimum-completed-tasks",
            "0",
        ],
    )

    assert result.exit_code != 0

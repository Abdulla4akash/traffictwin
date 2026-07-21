from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config

LOCAL_RULE = """
schema_version: "1.0"
grammar_version: "1.0"
rule_id: LOCAL_COMPLETION
rule_version: "1.0"
title: Local completion threshold
purpose: Check an already-computed completion metric.
condition: all
predicates:
  - kind: numeric_threshold
    predicate_id: COMPLETION
    metric_key: task.completion.rate
    reducer: scalar
    operator: gte
    threshold: 0.5
    expected_unit: ratio
    statement: Completion meets the local threshold.
triggered_hypothesis: The declared completion threshold is met.
limitations:
  - This threshold is local configuration and not a performance standard.
""".strip()


def test_declarative_rule_contract_validate_and_evaluate_cli(tmp_path: Path) -> None:
    rule = tmp_path / "local-rule.yaml"
    rule.write_text(LOCAL_RULE, encoding="utf-8")

    contract = CliRunner().invoke(app, ["diagnose", "rule-contract", "--format", "json"])
    validated = CliRunner().invoke(
        app,
        ["diagnose", "rule-validate", str(rule), "--format", "json"],
    )
    evaluated = CliRunner().invoke(
        app,
        [
            "diagnose",
            "rule-evaluate",
            str(rule),
            "tests/fixtures/bundles/baseline_valid",
            "--format",
            "json",
        ],
    )

    assert contract.exit_code == 0
    assert json.loads(contract.stdout)["capability"] == "DIA-04"
    assert validated.exit_code == 0
    assert json.loads(validated.stdout)["valid"] is True
    assert evaluated.exit_code == 0
    payload = json.loads(evaluated.stdout)
    assert payload["rule_id"] == "LOCAL_COMPLETION"
    assert payload["status"] == "triggered"
    assert payload["evidence_keys"] == ["task.completion.rate"]


def test_declarative_rule_validate_cli_rejects_reserved_core_id(tmp_path: Path) -> None:
    rule = tmp_path / "reserved.yaml"
    rule.write_text(LOCAL_RULE.replace("LOCAL_COMPLETION", "R7"), encoding="utf-8")

    result = CliRunner().invoke(app, ["diagnose", "rule-validate", str(rule)])

    assert result.exit_code == 1
    assert "reserved core rule identifier" in result.stderr


def test_r7_fairness_cli_exposes_selected_dimension_and_provisional_threshold(
    tmp_path: Path,
) -> None:
    bundle = write_synthetic_bundle(preset_config("baseline"), tmp_path / "baseline")

    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "fairness",
            str(bundle),
            "--dimension",
            "vehicle_tier_completion",
            "--minimum-outcome-gap",
            "0.1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["rule_id"] == "R7"
    assert payload["status"] == "triggered"
    assert payload["metadata"]["r7_dimension"] == "vehicle_tier_completion"
    assert payload["metadata"]["r7_minimum_outcome_gap"] == 0.1
    assert "protected or demographic" in payload["limitations"][0]

    provenance = CliRunner().invoke(
        app,
        ["provenance", "rule", str(bundle), "R7", "--format", "json"],
    )
    assert provenance.exit_code == 0
    trace = json.loads(provenance.stdout)
    rule_node = next(node for node in trace["nodes"] if node["node_id"] == "rule_result:R7")
    assert rule_node["attributes"]["result_metadata"]["declarative_definition_fingerprint"]
    assert any(node["node_type"] == "source_row" for node in trace["nodes"])


def test_r7_fairness_cli_rejects_unknown_dimension() -> None:
    result = CliRunner().invoke(
        app,
        [
            "diagnose",
            "fairness",
            "tests/fixtures/bundles/baseline_valid",
            "--dimension",
            "invented_group",
        ],
    )

    assert result.exit_code == 1
    assert "fairness diagnosis could not be evaluated" in result.stderr

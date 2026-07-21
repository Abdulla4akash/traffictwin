from __future__ import annotations

import json
from pathlib import Path

from tests.helpers import diagnostic_case, fixed_clock
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.rules.evaluation import evidence_pack_from_case

runner = CliRunner()


def test_cross_rule_contract_cli_publishes_closed_policy() -> None:
    result = runner.invoke(app, ["diagnose", "cross-rule-contract", "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["policy_version"] == "1.0"
    assert [policy["relation_type"] for policy in payload["policies"]] == [
        "conflict",
        "corroboration",
        "suppression",
    ]
    assert payload["precedence_tiers"] == {"data_readiness": 100, "ordinary_diagnostic": 50}


def test_cross_rule_cli_emits_mixed_fault_relationship_and_retained_results(
    tmp_path: Path,
) -> None:
    evidence = evidence_pack_from_case(diagnostic_case("mixed_fault"), clock=fixed_clock)
    path = tmp_path / "mixed-evidence.json"
    path.write_text(evidence.to_json(), encoding="utf-8")

    result = runner.invoke(app, ["diagnose", "cross-rule", str(path), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["counts_by_type"] == {
        "conflict": 1,
        "corroboration": 0,
        "suppression": 0,
    }
    assert payload["relationships"][0]["shared_evidence_keys"] == ["task.generated.count"]
    assert payload["retained_rule_ids"] == [f"R{index}" for index in range(9)]


def test_complete_diagnostic_report_embeds_cross_rule_artifact() -> None:
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
    payload = json.loads(result.output)
    assert payload["cross_rule_analysis"]["policy_version"] == "1.0"
    assert len(payload["cross_rule_analysis"]["retained_rule_ids"]) == 9

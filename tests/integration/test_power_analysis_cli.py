from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app


def _args(output_format: str = "json") -> list[str]:
    return [
        "experiment",
        "power-analysis",
        "--metric",
        "task.completion.rate",
        "--unit",
        "ratio",
        "--target-effect",
        "0.5",
        "--paired-difference-variance",
        "1.0",
        "--effect-basis",
        "practical_threshold",
        "--effect-justification",
        "A predeclared practically meaningful difference",
        "--variance-basis",
        "provisional_design",
        "--variance-justification",
        "A predeclared conservative planning variance",
        "--format",
        output_format,
    ]


def test_power_contract_and_known_plan_json_cli() -> None:
    contract = CliRunner().invoke(
        app,
        ["experiment", "power-contract", "--format", "json"],
    )
    result = CliRunner().invoke(app, _args())

    assert contract.exit_code == 0, contract.output
    contract_payload = json.loads(contract.output)
    assert contract_payload["method"] == "two_sided_paired_mean_normal_approximation_v1"
    assert contract_payload["replicate_bounds"] == {"minimum": 3, "maximum": 1_000_000}
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "available"
    assert payload["calculation"]["required_common_seed_replicates"] == 32
    assert payload["calculation"]["required_total_policy_runs"] == 64


def test_power_analysis_cli_exports_markdown_and_csv(tmp_path: Path) -> None:
    markdown_path = tmp_path / "power.md"
    markdown = CliRunner().invoke(
        app,
        [*_args("markdown"), "--output", str(markdown_path)],
    )
    csv_result = CliRunner().invoke(app, _args("csv"))

    assert markdown.exit_code == 0, markdown.output
    assert "# TrafficTwin Paired Common-Seed Power Analysis" in markdown_path.read_text(
        encoding="utf-8"
    )
    assert csv_result.exit_code == 0, csv_result.output
    row = list(csv.DictReader(io.StringIO(csv_result.output)))[0]
    assert row["required_common_seed_replicates"] == "32"
    assert row["status"] == "available"


def test_power_analysis_cli_returns_typed_unavailable_with_exit_two() -> None:
    args = _args()
    args[args.index("0.5")] = "0"
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["status"] == "unavailable"
    assert payload["calculation"]["reason_code"] == "ZERO_TARGET_EFFECT"


def test_power_analysis_cli_rejects_unlabelled_synthetic_basis() -> None:
    args = _args()
    args[args.index("provisional_design")] = "synthetic"
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 2
    assert "synthetic must be true" in result.output

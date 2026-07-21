from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app

BASELINE = Path("tests/fixtures/bundles/baseline_valid")


def test_annotation_cli_appends_lists_and_renders_report_history(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    imported = CliRunner().invoke(
        app,
        ["bundle", "import", str(BASELINE), "--registry", str(registry)],
    )
    added = CliRunner().invoke(
        app,
        [
            "registry",
            "annotation-add",
            "--registry",
            str(registry),
            "--target-kind",
            "run",
            "--target-id",
            "run-baseline-001",
            "--author",
            "Akash",
            "--decision-label",
            "follow_up",
            "--note",
            "Verify this synthetic result before dissertation use.",
        ],
    )
    listed = CliRunner().invoke(
        app,
        [
            "registry",
            "annotation-list",
            "--registry",
            str(registry),
            "--target-kind",
            "run",
            "--target-id",
            "run-baseline-001",
            "--format",
            "json",
        ],
    )
    output = tmp_path / "annotated.md"
    rendered = CliRunner().invoke(
        app,
        [
            "report",
            "run",
            str(BASELINE),
            "--output",
            str(output),
            "--registry",
            str(registry),
        ],
    )

    assert imported.exit_code == 0, imported.output
    assert added.exit_code == 0, added.output
    assert "sequence: 1" in added.output
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    assert payload["annotations"][0]["decision_label"] == "follow_up"
    assert payload["annotations"][0]["note"].startswith("Verify this synthetic")
    assert rendered.exit_code == 0, rendered.output
    markdown = output.read_text(encoding="utf-8")
    assert "Analyst Annotations — Non-computed" in markdown
    assert "Verify this synthetic result" in markdown


def test_annotation_cli_contract_and_target_validation(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    initialised = CliRunner().invoke(app, ["registry", "init", str(registry)])
    contract = CliRunner().invoke(
        app,
        ["registry", "annotation-contract", "--format", "json"],
    )
    missing_target = CliRunner().invoke(
        app,
        [
            "registry",
            "annotation-add",
            "--registry",
            str(registry),
            "--target-kind",
            "run",
            "--target-id",
            "missing-run",
            "--author",
            "Akash",
            "--note",
            "This must fail.",
        ],
    )

    assert initialised.exit_code == 0
    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["contract_version"] == "analyst-annotations-v1"
    assert missing_target.exit_code == 1
    assert "annotation target not found" in missing_target.output

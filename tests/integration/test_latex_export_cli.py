from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import (
    fixed_study_clock,
    paired_study_config,
    study_collections,
)
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.experiments.statistical_study import evaluate_paired_statistical_study

BASELINE = Path("tests/fixtures/bundles/baseline_valid")
VARIATION = Path("tests/fixtures/bundles/variation_valid")


def test_latex_contract_and_metric_svg_cli(tmp_path: Path) -> None:
    contract = CliRunner().invoke(app, ["report", "latex-contract", "--format", "json"])
    table = tmp_path / "metrics.tex"
    figure = tmp_path / "metrics.svg"
    result = CliRunner().invoke(
        app,
        [
            "report",
            "latex-metrics",
            str(BASELINE),
            "--output",
            str(table),
            "--figure",
            str(figure),
        ],
    )

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["supported_artifacts"] == [
        "metrics",
        "comparison",
        "statistical_study",
        "rules",
    ]
    assert result.exit_code == 0, result.output
    assert table.exists()
    assert figure.exists()
    assert "file: metrics.tex format=tex sha256=" in result.output
    assert "file: metrics.svg format=svg sha256=" in result.output
    assert " bytes=" in result.output
    assert str(tmp_path) not in result.output.split("file: metrics.tex", 1)[1]
    assert "Source mode: synthetic" in table.read_text(encoding="utf-8")
    assert str(tmp_path) not in table.read_text(encoding="utf-8")
    assert str(tmp_path) not in figure.read_text(encoding="utf-8")


def test_comparison_and_rules_cli_emit_pdf_and_tex(tmp_path: Path) -> None:
    comparison_table = tmp_path / "comparison.tex"
    comparison_figure = tmp_path / "comparison.pdf"
    comparison = CliRunner().invoke(
        app,
        [
            "report",
            "latex-comparison",
            str(BASELINE),
            str(VARIATION),
            "--output",
            str(comparison_table),
            "--figure",
            str(comparison_figure),
        ],
    )
    rules_table = tmp_path / "rules.tex"
    rules_figure = tmp_path / "rules.svg"
    rules = CliRunner().invoke(
        app,
        [
            "report",
            "latex-rules",
            str(BASELINE),
            "--output",
            str(rules_table),
            "--figure",
            str(rules_figure),
        ],
    )

    assert comparison.exit_code == 0, comparison.output
    assert comparison_figure.read_bytes().startswith(b"%PDF")
    assert "Delta" in comparison_table.read_text(encoding="utf-8")
    assert rules.exit_code == 0, rules.output
    assert "Categorical rule status" in rules_figure.read_text(encoding="utf-8")
    assert r"insufficient\_evidence" in rules_table.read_text(encoding="utf-8")


def test_statistical_study_cli_uses_strict_saved_artifact(tmp_path: Path) -> None:
    study = evaluate_paired_statistical_study(
        study_collections([1.0, 2.0, 3.0]),
        paired_study_config(),
        clock=fixed_study_clock,
    )
    study_path = tmp_path / "study.json"
    study_path.write_text(study.model_dump_json(indent=2), encoding="utf-8")
    table = tmp_path / "study.tex"
    figure = tmp_path / "study.svg"

    result = CliRunner().invoke(
        app,
        [
            "report",
            "latex-study",
            str(study_path),
            "--output",
            str(table),
            "--figure",
            str(figure),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Mean paired difference" in table.read_text(encoding="utf-8")
    assert "seed 1" in figure.read_text(encoding="utf-8")


def test_latex_cli_requires_explicit_overwrite_and_valid_suffixes(tmp_path: Path) -> None:
    table = tmp_path / "metrics.tex"
    first = CliRunner().invoke(
        app,
        ["report", "latex-metrics", str(BASELINE), "--output", str(table)],
    )
    refused = CliRunner().invoke(
        app,
        ["report", "latex-metrics", str(BASELINE), "--output", str(table)],
    )
    overwritten = CliRunner().invoke(
        app,
        [
            "report",
            "latex-metrics",
            str(BASELINE),
            "--output",
            str(table),
            "--overwrite",
        ],
    )
    bad_suffix = CliRunner().invoke(
        app,
        [
            "report",
            "latex-metrics",
            str(BASELINE),
            "--output",
            str(tmp_path / "metrics.txt"),
        ],
    )

    assert first.exit_code == 0, first.output
    assert refused.exit_code == 1
    assert overwritten.exit_code == 0, overwritten.output
    assert bad_suffix.exit_code == 1
    assert ".tex" in bad_suffix.output

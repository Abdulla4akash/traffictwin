from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.tos_helpers import write_tos_package
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.tos import (
    import_evaluation_summaries,
    validate_tos_package,
)
from traffictwin.storage.registry import Registry


def test_tos_registry_import_is_persistent_and_idempotent(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    registry_path = tmp_path / "registry.sqlite"
    report = validate_tos_package(package, deep=True)

    first = import_evaluation_summaries(
        package,
        registry_path,
        validation_report=report,
    )
    second = import_evaluation_summaries(
        package,
        registry_path,
        validation_report=report,
    )
    summary = Registry(registry_path).inspect()

    assert first.experiments_created == 1
    assert first.runs_created == 2
    assert first.metric_collections_stored == 2
    assert second.experiments_existing == 1
    assert second.runs_existing == 2
    assert second.metric_collections_stored == 0
    assert second.evidence_packs_stored == 0
    assert summary.experiment_count == 1
    assert summary.run_count == 2
    assert summary.metric_collection_count == 2
    assert summary.evidence_pack_count == 2


def test_tos_cli_inspect_replay_and_provenance(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    runner = CliRunner()

    inspect_result = runner.invoke(
        app,
        ["integration", "tos", "inspect", str(package), "--format", "json"],
    )
    replay_result = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "replay",
            str(package),
            "baseline_uk2030_wd_am_fs0",
            "--index",
            "1",
            "--format",
            "json",
        ],
    )
    provenance_result = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "provenance",
            str(package),
            "tos:baseline:wd_am:uk2030:fs0",
            "--root-id",
            "tos.task.deadline_success.rate",
            "--format",
            "json",
        ],
    )
    contract_result = runner.invoke(
        app,
        ["integration", "tos", "contract", "--format", "json"],
    )
    runs_result = runner.invoke(
        app,
        ["integration", "tos", "runs", str(package), "--limit", "1"],
    )
    rsu_result = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "rsu-series",
            str(package),
            "baseline_uk2030_wd_am_fs0",
            "--limit",
            "2",
            "--format",
            "json",
        ],
    )

    assert inspect_result.exit_code == 0
    assert json.loads(inspect_result.output)["inventory"]["evaluation_rows"] == 2
    assert replay_result.exit_code == 0
    assert json.loads(replay_result.output)["point"]["index"] == 1
    assert provenance_result.exit_code == 0
    assert json.loads(provenance_result.output)["completeness"]["overall"] == "partial"
    assert contract_result.exit_code == 0
    assert json.loads(contract_result.output)["execution"]["direct_launch"] == "false"
    assert runs_result.exit_code == 0
    assert "instrumented_key=baseline_uk2030_wd_am_fs0" in runs_result.output
    assert rsu_result.exit_code == 0
    assert json.loads(rsu_result.output)[0]["concurrency_pressure_fraction"] == 0.2


def test_tos_cli_import_is_idempotent(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    registry = tmp_path / "registry.sqlite"
    runner = CliRunner()
    arguments = [
        "integration",
        "tos",
        "import",
        str(package),
        "--registry",
        str(registry),
    ]

    first = runner.invoke(app, arguments)
    second = runner.invoke(app, arguments)

    assert first.exit_code == 0
    assert "runs_created: 2" in first.output
    assert second.exit_code == 0
    assert "runs_existing: 2" in second.output


def test_tos_workbench_cli_and_exports(tmp_path: Path) -> None:
    package = write_tos_package(tmp_path / "tos")
    runner = CliRunner()
    matrix = runner.invoke(
        app,
        ["integration", "tos", "matrix", str(package), "--format", "json"],
    )
    comparison = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "compare-campaigns",
            str(package),
            "baseline",
            "capscalar_mappo",
            "--format",
            "json",
        ],
    )
    training = runner.invoke(
        app,
        ["integration", "tos", "training", str(package), "baseline", "--format", "json"],
    )
    task = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "task-summary",
            str(package),
            "baseline_uk2030_wd_am_fs0",
            "--format",
            "json",
        ],
    )
    audit = runner.invoke(
        app,
        ["integration", "tos", "audit", str(package), "--format", "json"],
    )
    atlas_path = tmp_path / "atlas.html"
    atlas = runner.invoke(
        app,
        ["integration", "tos", "atlas", str(package), "--output", str(atlas_path)],
    )
    pack_path = tmp_path / "pack"
    pack = runner.invoke(
        app,
        [
            "integration",
            "tos",
            "results-pack",
            str(package),
            "--variation",
            "capscalar_mappo",
            "--output",
            str(pack_path),
        ],
    )

    assert matrix.exit_code == 0, matrix.output
    assert len(json.loads(matrix.output)["entries"]) == 2
    assert comparison.exit_code == 0, comparison.output
    assert json.loads(comparison.output)["comparisons"][0]["observations"][0][
        "absolute_delta"
    ] == pytest.approx(0.03)
    assert training.exit_code == 0, training.output
    assert json.loads(training.output)["points"][0]["mean_completion"] is None
    assert task.exit_code == 0, task.output
    assert json.loads(task.output)["task_count"] == 4
    assert audit.exit_code == 0, audit.output
    assert json.loads(audit.output)["evaluation_run_count"] == 2
    assert atlas.exit_code == 0, atlas.output
    assert pack.exit_code == 0, pack.output
    assert atlas_path.is_file()
    assert (pack_path / "research-report.md").is_file()
    exported = atlas_path.read_text(encoding="utf-8") + (
        pack_path / "research-report.md"
    ).read_text(encoding="utf-8")
    assert "/Users/" not in exported
    assert "NaN" not in exported

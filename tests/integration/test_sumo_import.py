from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.integration.sumo import import_sumo_results, validate_sumo_results
from traffictwin.storage.registry import Registry

FIXTURE = Path("tests/fixtures/sumo/square_public")


def test_sumo_registry_import_is_idempotent_and_stores_metrics(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    validation = validate_sumo_results(FIXTURE)

    first = import_sumo_results(
        FIXTURE,
        registry_path,
        validation_result=validation,
    )
    second = import_sumo_results(FIXTURE, registry_path)
    summary = Registry(registry_path).inspect()

    assert first.created
    assert first.metrics_stored
    assert second.idempotent
    assert not second.metrics_stored
    assert summary.run_count == 1
    assert summary.bundle_import_count == 1
    assert summary.metric_collection_count == 1


def test_sumo_cli_contract_validation_metrics_and_import(tmp_path: Path) -> None:
    runner = CliRunner()
    registry = tmp_path / "registry.sqlite"

    contract = runner.invoke(app, ["integration", "sumo", "contract", "--format", "json"])
    validation = runner.invoke(
        app,
        ["integration", "sumo", "validate", str(FIXTURE), "--format", "json"],
    )
    metrics = runner.invoke(
        app,
        ["integration", "sumo", "metrics", str(FIXTURE), "--format", "json"],
    )
    imported = runner.invoke(
        app,
        ["integration", "sumo", "import", str(FIXTURE), "--registry", str(registry)],
    )
    repeated = runner.invoke(
        app,
        ["integration", "sumo", "import", str(FIXTURE), "--registry", str(registry)],
    )

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["capabilities"]["supports"]["direct_launch"] == "false"
    assert validation.exit_code == 0, validation.output
    assert len(json.loads(validation.output)["summary_steps"]) == 1800
    assert metrics.exit_code == 0, metrics.output
    by_key = {item["metric_key"]: item for item in json.loads(metrics.output)["results"]}
    assert by_key["trip.completed.count"]["value"] == 41
    assert imported.exit_code == 0, imported.output
    assert "created: True" in imported.output
    assert "metrics_stored: True" in imported.output
    assert repeated.exit_code == 0, repeated.output
    assert "idempotent: True" in repeated.output

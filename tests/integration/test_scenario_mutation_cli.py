from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.experiments.scenario_mutation import (
    MutationTableKind,
    RowDropoutMutation,
    ScenarioMutationRequest,
    scenario_mutation_request_to_yaml,
)
from traffictwin.ingestion.bundle import validate_bundle

FIXTURE = Path("tests/fixtures/bundles/baseline_valid")


def _request_file(path: Path) -> Path:
    request = ScenarioMutationRequest(
        mutation_id="mutation-cli",
        title="CLI task dropout",
        mutation=RowDropoutMutation(
            table_kind=MutationTableKind.TASKS,
            drop_fraction=0.25,
            random_seed=17,
        ),
    )
    path.write_text(scenario_mutation_request_to_yaml(request), encoding="utf-8")
    return path


def test_scenario_mutation_contract_is_public_cli() -> None:
    result = CliRunner().invoke(app, ["experiment", "mutation-contract"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["supported_operators"] == [
        "row_dropout",
        "timestamp_jitter",
        "rsu_removal",
    ]
    assert payload["max_changed_rows"] == 20_000
    assert payload["raw_source_mutation_supported"] is False
    assert payload["direct_launch_supported"] is False


def test_scenario_mutation_cli_writes_valid_derived_bundle(tmp_path: Path) -> None:
    request = _request_file(tmp_path / "request.yaml")
    output = tmp_path / "mutation"

    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "mutate-scenario",
            "--bundle",
            str(FIXTURE),
            "--request",
            str(request),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "operator: row_dropout" in result.output
    assert "status: validated_mutated_bundle" in result.output
    assert "changed_rows: 1" in result.output
    assert "raw_source_mutated: false" in result.output
    assert "direct_launch_supported: false" in result.output
    manifest = json.loads((output / "mutation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic_evaluation"] is True
    assert manifest["parent_bundle_fingerprint"] == validate_bundle(FIXTURE).fingerprint
    assert validate_bundle(output / "bundle").report.may_import


def test_scenario_mutation_cli_rejects_existing_destination(tmp_path: Path) -> None:
    request = _request_file(tmp_path / "request.yaml")
    output = tmp_path / "mutation"
    output.mkdir()

    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "mutate-scenario",
            "--bundle",
            str(FIXTURE),
            "--request",
            str(request),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "destination already exists" in result.output

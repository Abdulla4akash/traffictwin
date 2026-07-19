from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.domain.experiment import Experiment
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.storage.registry import Registry


def test_cli_exports_protocol_and_matches_completed_bundle(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    bundle_path = Path("tests/fixtures/bundles/baseline_valid")
    validation = validate_bundle(bundle_path)
    assert validation.manifest is not None
    assert validation.seed is not None
    manifest = validation.manifest
    registry = Registry(registry_path)
    registry.add_seed(validation.seed)
    registry.add_experiment(
        Experiment(
            experiment_id=manifest.run.experiment_id,
            research_question="Can this bundle be matched to a planned slot?",
            baseline_seed_id=manifest.run.seed_id,
            algorithms=[manifest.run.algorithm],
            common_random_seed_set=[manifest.run.random_seed],
            planned_replicates=1,
        )
    )
    runner = CliRunner()

    yaml_output = tmp_path / "exports" / "protocol.yaml"
    export = runner.invoke(
        app,
        [
            "experiment",
            "protocol",
            "--registry",
            str(registry_path),
            "--experiment-id",
            manifest.run.experiment_id,
            "--format",
            "yaml",
            "--output",
            str(yaml_output),
        ],
    )
    assert export.exit_code == 0, export.output
    assert yaml.safe_load(yaml_output.read_text(encoding="utf-8"))["slots"][0]["random_seed"] == 7

    csv_export = runner.invoke(
        app,
        [
            "experiment",
            "protocol",
            "--registry",
            str(registry_path),
            "--experiment-id",
            manifest.run.experiment_id,
            "--format",
            "csv",
        ],
    )
    assert csv_export.exit_code == 0, csv_export.output
    assert len(list(csv.DictReader(io.StringIO(csv_export.output)))) == 1

    matched = runner.invoke(
        app,
        [
            "experiment",
            "match-bundle",
            str(bundle_path),
            "--registry",
            str(registry_path),
            "--experiment-id",
            manifest.run.experiment_id,
            "--format",
            "json",
        ],
    )
    assert matched.exit_code == 0, matched.output
    assert json.loads(matched.output)["status"] == "compatible"


def test_cli_rejects_invalid_bundle_before_protocol_matching(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.sqlite"
    valid = validate_bundle("tests/fixtures/bundles/baseline_valid")
    assert valid.manifest is not None
    assert valid.seed is not None
    registry = Registry(registry_path)
    registry.add_seed(valid.seed)
    registry.add_experiment(
        Experiment(
            experiment_id=valid.manifest.run.experiment_id,
            research_question="Can this bundle be matched?",
            baseline_seed_id=valid.seed.seed_id,
            algorithms=[valid.manifest.run.algorithm],
            common_random_seed_set=[valid.manifest.run.random_seed],
            planned_replicates=1,
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "experiment",
            "match-bundle",
            "tests/fixtures/bundles/invalid_manifest",
            "--registry",
            str(registry_path),
            "--experiment-id",
            valid.manifest.run.experiment_id,
        ],
    )

    assert result.exit_code == 1
    assert "bundle rejected" in result.output

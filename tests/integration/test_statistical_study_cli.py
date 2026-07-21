from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import study_collection, study_collections
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.domain.experiment import Experiment
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import Registry


def _registry(tmp_path: Path, collections: list[MetricCollection]) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Does the variation change completion under common seeds?",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
        )
    )
    for collection in collections:
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    return path


def _args(registry: Path, output_format: str = "json") -> list[str]:
    return [
        "experiment",
        "statistical-study",
        "--registry",
        str(registry),
        "--experiment-id",
        "exp-paired",
        "--baseline-seed",
        "seed-baseline",
        "--variation-seed",
        "seed-variation",
        "--algorithm",
        "policy-a",
        "--bootstrap-repetitions",
        "1000",
        "--randomisation-repetitions",
        "1000",
        "--resampling-seed",
        "77",
        "--format",
        output_format,
    ]


def test_statistical_study_contract_and_json_cli(tmp_path: Path) -> None:
    contract = CliRunner().invoke(
        app,
        ["experiment", "study-contract", "--format", "json"],
    )
    registry = _registry(tmp_path, study_collections([1.0, 2.0, 3.0]))
    result = CliRunner().invoke(app, _args(registry))

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["minimum_pairs"] == 3
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "available"
    assert payload["pairing_audit"]["eligible_random_seeds"] == [1, 2, 3]
    assert payload["estimate"]["mean_paired_difference"] == 2.0
    assert payload["randomisation_test"]["p_value"] == 0.25


def test_statistical_study_markdown_and_csv_exports(tmp_path: Path) -> None:
    registry = _registry(tmp_path, study_collections([1.0, 2.0, 3.0]))
    markdown_path = tmp_path / "study.md"
    markdown = CliRunner().invoke(
        app,
        [*_args(registry, "markdown"), "--output", str(markdown_path)],
    )
    csv_result = CliRunner().invoke(app, _args(registry, "csv"))

    assert markdown.exit_code == 0, markdown.output
    assert "# TrafficTwin Paired Statistical Study" in markdown_path.read_text(encoding="utf-8")
    assert csv_result.exit_code == 0, csv_result.output
    assert csv_result.output.count("eligible_pair") == 3


def test_statistical_study_cli_returns_typed_insufficient_artifact(tmp_path: Path) -> None:
    registry = _registry(
        tmp_path,
        [
            study_collection("baseline", 1, 10.0),
            study_collection("variation", 1, 11.0),
        ],
    )
    result = CliRunner().invoke(app, _args(registry))

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "insufficient"
    assert payload["pairing_audit"]["missing_expected_random_seeds"] == [2, 3]
    assert payload["randomisation_test"]["mode"] == "not_run"


def test_statistical_study_cli_rejects_selection_outside_registered_plan(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path, study_collections([1.0, 2.0, 3.0]))
    args = _args(registry)
    args[args.index("seed-variation")] = "seed-unplanned"
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 1
    assert "variation seed is not declared" in result.output


def test_pair_audit_csv_retains_source_fingerprint_lineage(tmp_path: Path) -> None:
    registry = _registry(tmp_path, study_collections([1.0, 2.0, 3.0]))
    result = CliRunner().invoke(app, _args(registry, "csv"))

    assert result.exit_code == 0, result.output
    header = result.output.splitlines()[0]
    assert "baseline_input_fingerprint" in header
    assert "variation_collection_fingerprint" in header
    assert "fingerprint-run-baseline-1" in result.output

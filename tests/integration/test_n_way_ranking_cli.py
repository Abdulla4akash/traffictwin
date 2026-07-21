from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import study_collection
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.domain.experiment import Experiment
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import Registry


def _collection(algorithm: str, random_seed: int, value: float) -> MetricCollection:
    collection = study_collection(
        "baseline",
        random_seed,
        value,
        run_id=f"run-{algorithm}-{random_seed}",
        experiment_id="exp-nway",
        algorithm=algorithm,
    )
    return collection.model_copy(
        update={
            "results": [
                metric.model_copy(update={"seed_id": "seed-family"})
                for metric in collection.results
            ]
        }
    )


def _registry(tmp_path: Path, seeds: tuple[int, ...] = (1, 2, 3)) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-nway",
            research_question="Which policy ranks highest over common seeds?",
            baseline_seed_id="seed-family",
            algorithms=["policy-a", "policy-b", "policy-c"],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
        )
    )
    for seed in seeds:
        for algorithm, value in {
            "policy-a": 0.9,
            "policy-b": 0.7,
            "policy-c": 0.5,
        }.items():
            collection = _collection(algorithm, seed, value + seed * 0.01)
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
        "n-way-ranking",
        "--registry",
        str(registry),
        "--experiment-id",
        "exp-nway",
        "--bootstrap-repetitions",
        "1000",
        "--resampling-seed",
        "91",
        "--format",
        output_format,
    ]


def test_n_way_contract_and_json_cli_rank_registered_policies(tmp_path: Path) -> None:
    contract = CliRunner().invoke(app, ["experiment", "n-way-contract", "--format", "json"])
    result = CliRunner().invoke(app, _args(_registry(tmp_path)))

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["minimum_complete_seeds"] == 3
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "available"
    assert payload["entries"][0]["winner_algorithms"] == ["policy-a"]
    assert payload["entries"][0]["audit"]["complete_random_seeds"] == [1, 2, 3]
    assert [row["rank"] for row in payload["entries"][0]["policy_ranks"]] == [1, 2, 3]


def test_n_way_cli_exports_markdown_and_audit_csv(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    markdown_path = tmp_path / "n-way.md"
    markdown = CliRunner().invoke(
        app,
        [*_args(registry, "markdown"), "--output", str(markdown_path)],
    )
    csv_result = CliRunner().invoke(app, _args(registry, "csv"))

    assert markdown.exit_code == 0, markdown.output
    assert "# TrafficTwin N-Way Policy Ranking" in markdown_path.read_text(encoding="utf-8")
    assert csv_result.exit_code == 0, csv_result.output
    assert csv_result.output.count("policy_rank") == 3
    assert csv_result.output.count("complete_observation") == 9


def test_n_way_cli_returns_typed_insufficient_artifact(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, _args(_registry(tmp_path, seeds=(1, 2))))

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "insufficient"
    assert payload["entries"][0]["bootstrap"]["status"] == "unavailable"
    assert payload["entries"][0]["audit"]["missing_expected_random_seeds"] == [3]


def test_n_way_cli_rejects_unregistered_policy_selection(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [*_args(_registry(tmp_path)), "--algorithm", "policy-x", "--algorithm", "policy-a"],
    )

    assert result.exit_code == 1
    assert "unregistered policies" in result.output

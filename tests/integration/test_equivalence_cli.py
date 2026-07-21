from __future__ import annotations

import json
from pathlib import Path

from tests.statistical_helpers import study_collections
from typer.testing import CliRunner

from traffictwin.cli import app
from traffictwin.domain.experiment import Experiment
from traffictwin.storage.registry import Registry


def _registry(tmp_path: Path, differences: list[float]) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    common_seeds = list(range(1, len(differences) + 1))
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Are the conditions practically equivalent?",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=common_seeds,
            planned_replicates=len(common_seeds),
        )
    )
    for collection in study_collections(differences):
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
        "equivalence-study",
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
        "--equivalence-margin",
        "0.2",
        "--margin-basis",
        "provisional_design",
        "--margin-justification",
        "Synthetic CLI method-test margin",
        "--format",
        output_format,
    ]


def test_equivalence_contract_and_known_equivalent_json_cli(tmp_path: Path) -> None:
    contract = CliRunner().invoke(
        app,
        ["experiment", "equivalence-contract", "--format", "json"],
    )
    registry = _registry(tmp_path, [-0.05, 0.0, 0.05, 0.02, -0.02])
    result = CliRunner().invoke(app, _args(registry))

    assert contract.exit_code == 0, contract.output
    assert json.loads(contract.output)["method"] == "paired_mean_tost_v1"
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "available"
    assert payload["tost"]["conclusion"] == "equivalence_demonstrated"
    assert payload["pairing_audit"]["eligible_random_seeds"] == [1, 2, 3, 4, 5]


def test_equivalence_cli_exports_markdown_and_audit_csv(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [-0.05, 0.0, 0.05, 0.02, -0.02])
    markdown_path = tmp_path / "equivalence.md"
    markdown = CliRunner().invoke(
        app,
        [*_args(registry, "markdown"), "--output", str(markdown_path)],
    )
    csv_result = CliRunner().invoke(app, _args(registry, "csv"))

    assert markdown.exit_code == 0, markdown.output
    assert "# TrafficTwin Paired Equivalence Study" in markdown_path.read_text(encoding="utf-8")
    assert csv_result.exit_code == 0, csv_result.output
    assert csv_result.output.count("eligible_pair") == 5
    assert csv_result.output.count("one_sided_test") == 2


def test_equivalence_cli_returns_typed_insufficient_artifact(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [0.01, -0.01])
    result = CliRunner().invoke(app, _args(registry))

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "insufficient"
    assert payload["tost"]["conclusion"] == "unavailable"


def test_equivalence_cli_rejects_unjustified_literature_margin(tmp_path: Path) -> None:
    registry = _registry(tmp_path, [-0.05, 0.0, 0.05, 0.02, -0.02])
    args = _args(registry)
    args[args.index("provisional_design")] = "literature"
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 1
    assert "margin_reference is required" in result.output

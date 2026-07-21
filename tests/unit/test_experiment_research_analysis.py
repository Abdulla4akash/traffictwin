from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import fixed_clock
from traffictwin.experiments.evidence import (
    ExperimentEvidenceOptions,
    PairedMetricEndpoint,
    TrainingValidationObservation,
    build_experiment_evidence_pack,
)
from traffictwin.experiments.portfolio import (
    default_synthetic_portfolio_rules,
    evaluate_portfolio,
    evaluate_portfolio_study,
    portfolio_study_to_csv,
    portfolio_study_to_markdown,
)
from traffictwin.experiments.winner_map import build_winner_map
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.metrics.results import MetricCollection
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.models import RuleStatus
from traffictwin.synthetic.experiments import (
    generate_synthetic_portfolio_study,
    generate_trivial_multi_algorithm_experiment,
)
from traffictwin.synthetic.generator import generate_run_data
from traffictwin.synthetic.scenarios import preset_config


def _trivial_collections(tmp_path: Path) -> tuple[list[MetricCollection], dict[str, str]]:
    paths = generate_trivial_multi_algorithm_experiment(tmp_path / "trivial")
    collections = []
    aliases: dict[str, str] = {}
    for path in paths:
        validation = validate_bundle(path)
        assert validation.seed is not None
        aliases[validation.seed.seed_id] = validation.seed.parent_seed_id or validation.seed.seed_id
        collections.append(compute_metrics_for_bundle(validation, clock=fixed_clock))
    return collections, aliases


def test_experiment_evidence_supports_r3_and_explicit_r5_pairs(tmp_path: Path) -> None:
    collections, _ = _trivial_collections(tmp_path)
    options = ExperimentEvidenceOptions(experiment_id="exp-standalone-trivial")

    r3_pack = build_experiment_evidence_pack(collections, options, clock=fixed_clock)
    r3_report = evaluate_rules(r3_pack, clock=fixed_clock)

    assert "R3" in r3_report.triggered_rule_ids
    assert next(result for result in r3_report.results if result.rule_id == "R5").status is (
        RuleStatus.INSUFFICIENT_EVIDENCE
    )

    pairs = [
        TrainingValidationObservation(
            training=PairedMetricEndpoint(
                run_id=f"training-{seed}",
                experiment_id="exp-standalone-trivial",
                seed_id=f"training-seed-{seed}",
                algorithm="synthetic-selective",
                random_seed=seed,
                metric_key="task.completion.rate",
                metric_version="1.0",
                unit="ratio",
                environment="synthetic-light",
                value=0.95,
            ),
            validation=PairedMetricEndpoint(
                run_id=f"validation-{seed}",
                experiment_id="exp-standalone-trivial",
                seed_id=f"validation-seed-{seed}",
                algorithm="synthetic-selective",
                random_seed=seed,
                metric_key="task.completion.rate",
                metric_version="1.0",
                unit="ratio",
                environment="synthetic-validation",
                value=0.70,
            ),
        )
        for seed in (1, 2)
    ]
    r5_pack = build_experiment_evidence_pack(
        collections,
        options,
        training_validation=pairs,
        clock=fixed_clock,
    )
    r5_report = evaluate_rules(r5_pack, clock=fixed_clock)

    assert "R5" in r5_report.triggered_rule_ids


def test_winner_map_and_portfolio_are_deterministic_synthetic_outputs(tmp_path: Path) -> None:
    collections, aliases = _trivial_collections(tmp_path)

    winner_map = build_winner_map(collections, seed_aliases=aliases, clock=fixed_clock)
    base_seed = generate_run_data(preset_config("trivial_multi_algorithm")).seed
    portfolio = evaluate_portfolio(
        winner_map,
        {base_seed.seed_id: base_seed},
        default_synthetic_portfolio_rules(),
        clock=fixed_clock,
    )

    assert winner_map.synthetic_only
    assert len(winner_map.entries) == 1
    assert len(winner_map.entries[0].policy_scores) == 3
    assert portfolio.available_seed_count == 1
    assert portfolio.rows[0].selected_algorithm == "synthetic-always-local"
    assert "trained algorithms" in " ".join(winner_map.warnings)


def test_training_validation_pairs_reject_incompatible_provenance() -> None:
    training = PairedMetricEndpoint(
        run_id="training-1",
        experiment_id="exp-controlled",
        seed_id="seed-training",
        algorithm="policy-a",
        checkpoint="checkpoint-1",
        random_seed=1,
        metric_key="task.completion.rate",
        metric_version="1.0",
        unit="ratio",
        environment="training",
        value=0.9,
    )
    validation = training.model_copy(
        update={
            "run_id": "validation-1",
            "seed_id": "seed-validation",
            "unit": "percent",
            "environment": "validation",
        }
    )

    with pytest.raises(ValueError, match="unit"):
        TrainingValidationObservation(training=training, validation=validation)


def test_r5_pair_set_rejects_reused_random_seed(tmp_path: Path) -> None:
    collections, _ = _trivial_collections(tmp_path)
    training = PairedMetricEndpoint(
        run_id="training-1",
        experiment_id="exp-standalone-trivial",
        seed_id="seed-training",
        algorithm="policy-a",
        checkpoint="checkpoint-1",
        random_seed=1,
        metric_key="task.completion.rate",
        metric_version="1.0",
        unit="ratio",
        environment="training",
        value=0.9,
    )
    validation = training.model_copy(
        update={
            "run_id": "validation-1",
            "seed_id": "seed-validation",
            "environment": "validation",
            "value": 0.7,
        }
    )
    first = TrainingValidationObservation(training=training, validation=validation)
    second = TrainingValidationObservation(
        training=training.model_copy(update={"run_id": "training-2"}),
        validation=validation.model_copy(update={"run_id": "validation-2"}),
    )

    with pytest.raises(ValueError, match="reuse random seeds"):
        build_experiment_evidence_pack(
            collections,
            ExperimentEvidenceOptions(experiment_id="exp-standalone-trivial"),
            training_validation=[first, second],
            clock=fixed_clock,
        )


def test_winner_map_excludes_incompatible_seed_observations(tmp_path: Path) -> None:
    collections, aliases = _trivial_collections(tmp_path)
    first = collections[0]
    changed_results = [
        metric.model_copy(update={"unit": "percent"})
        if metric.metric_key == "task.completion.rate"
        else metric
        for metric in first.results
    ]
    incompatible = first.model_copy(update={"results": changed_results})

    winner_map = build_winner_map(
        [incompatible, *collections[1:]],
        seed_aliases=aliases,
        clock=fixed_clock,
    )

    assert winner_map.entries == []
    assert "incompatible" in " ".join(winner_map.warnings)


def test_portfolio_study_uses_disjoint_multi_seed_split(tmp_path: Path) -> None:
    fixture = generate_synthetic_portfolio_study(tmp_path / "portfolio-study")
    collections: list[MetricCollection] = []
    aliases: dict[str, str] = {}
    for path in fixture.bundle_paths:
        validation = validate_bundle(path)
        assert validation.seed is not None
        aliases[validation.seed.seed_id] = validation.seed.parent_seed_id or validation.seed.seed_id
        collections.append(compute_metrics_for_bundle(validation, clock=fixed_clock))
    winner_map = build_winner_map(collections, seed_aliases=aliases, clock=fixed_clock)

    report = evaluate_portfolio_study(
        winner_map,
        fixture.base_seeds,
        default_synthetic_portfolio_rules(),
        development_seed_ids=fixture.development_seed_ids,
        held_out_seed_ids=fixture.held_out_seed_ids,
        clock=fixed_clock,
    )

    assert len(winner_map.entries) == 5
    assert {entry.random_seed_count for entry in winner_map.entries} == {3}
    assert report.development_evaluation.evaluated_seed_count == 3
    assert report.held_out_evaluation.evaluated_seed_count == 2
    assert len(report.held_out_constituents) == 3
    assert len(report.dominance_matrix) == 6
    assert report.held_out_evaluation.selected_score_standard_deviation is not None
    assert report.held_out_evaluation.regret_standard_deviation is not None
    assert "record_type" in portfolio_study_to_csv(report)
    assert "Held-out constituents" in portfolio_study_to_markdown(report)
    assert set(report.development_seed_ids).isdisjoint(report.held_out_seed_ids)

from __future__ import annotations

import pytest

from tests.unit.test_registry import make_seed
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.experiments.planning import summarise_experiment_plan


def _seeds() -> dict[str, ScenarioSeed]:
    baseline = make_seed()
    variation = baseline.model_copy(
        update={
            "seed_id": "s1-gridlock-x3",
            "name": "Gridlock triple demand",
            "demand": baseline.demand.model_copy(update={"multiplier": 3.0}),
        }
    )
    return {baseline.seed_id: baseline, variation.seed_id: variation}


def _experiment() -> Experiment:
    return Experiment(
        experiment_id="exp-planner",
        research_question="How does demand change the imported outcomes?",
        hypothesis="The stressed condition may reduce completion.",
        baseline_seed_id="s1-gridlock-x2",
        variation_seed_ids=["s1-gridlock-x3"],
        algorithms=["synthetic-balanced", "synthetic-selective"],
        common_random_seed_set=[7, 8],
        planned_replicates=2,
    )


def test_experiment_plan_summary_is_deterministic() -> None:
    seeds = _seeds()
    summary = summarise_experiment_plan(_experiment(), seeds)

    assert summary.condition_count == 2
    assert summary.algorithm_count == 2
    assert summary.replicate_count == 2
    assert summary.planned_run_count == 8
    assert [cell.as_row() for cell in summary.preview_cells[:2]] == [
        {
            "role": "baseline",
            "seed_id": "s1-gridlock-x2",
            "algorithm": "synthetic-balanced",
            "random_seed": 7,
        },
        {
            "role": "baseline",
            "seed_id": "s1-gridlock-x2",
            "algorithm": "synthetic-balanced",
            "random_seed": 8,
        },
    ]
    assert summary.seed_differences["s1-gridlock-x3"] == (
        {"path": "demand.multiplier", "baseline": 2.0, "variation": 3.0},
    )


def test_experiment_plan_rejects_unregistered_seed() -> None:
    experiment = _experiment().model_copy(update={"variation_seed_ids": ["missing-seed"]})

    with pytest.raises(ValueError, match="unregistered scenario seeds: missing-seed"):
        summarise_experiment_plan(experiment, _seeds())


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"algorithms": []}, "at least one policy"),
        ({"common_random_seed_set": []}, "at least one common random seed"),
        ({"planned_replicates": 1}, "planned_replicates must match"),
        ({"variation_seed_ids": ["s1-gridlock-x2"]}, "baseline seed must not"),
    ],
)
def test_experiment_plan_rejects_incomplete_design(
    updates: dict[str, object],
    message: str,
) -> None:
    experiment = _experiment().model_copy(update=updates)

    with pytest.raises(ValueError, match=message):
        summarise_experiment_plan(experiment, _seeds())


def test_experiment_plan_bounds_preview_and_warns_for_single_design() -> None:
    experiment = _experiment().model_copy(
        update={
            "variation_seed_ids": [],
            "algorithms": ["synthetic-balanced"],
        }
    )
    summary = summarise_experiment_plan(experiment, _seeds(), preview_limit=1)

    assert summary.planned_run_count == 2
    assert summary.preview_truncated
    assert len(summary.preview_cells) == 1
    assert any("does not define a comparison" in warning for warning in summary.warnings)
    assert any("limited to 1 of 2" in warning for warning in summary.warnings)

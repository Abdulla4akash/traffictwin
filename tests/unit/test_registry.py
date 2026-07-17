from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.test_scenario import valid_seed_payload
from traffictwin.domain.enums import ExperimentStatus, RunStatus
from traffictwin.domain.experiment import Experiment
from traffictwin.domain.run import Run
from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.storage.registry import (
    DuplicateIdentifierError,
    InvalidStatusTransitionError,
    Registry,
)


def make_seed() -> ScenarioSeed:
    return ScenarioSeed.model_validate(valid_seed_payload())


def make_experiment() -> Experiment:
    return Experiment(
        experiment_id="exp-001",
        research_question="Does doubled demand reduce task completion?",
        hypothesis="Variation will increase queueing and lower completion.",
        baseline_seed_id="s1-gridlock",
        variation_seed_ids=["s1-gridlock-x2"],
        algorithms=["MAPPO"],
        common_random_seed_set=[7],
        planned_replicates=1,
    )


def make_run() -> Run:
    return Run(
        run_id="run-001",
        experiment_id="exp-001",
        seed_id="s1-gridlock-x2",
        algorithm="MAPPO",
        random_seed=7,
    )


def test_registry_create_read_update_operations(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    seed = make_seed()
    experiment = make_experiment()
    run = make_run()

    registry.add_seed(seed)
    registry.add_experiment(experiment)
    registry.add_run(run)

    assert registry.get_seed(seed.seed_id) == seed
    assert registry.get_experiment(experiment.experiment_id).status is ExperimentStatus.PLANNED
    assert registry.get_run(run.run_id).status is RunStatus.REGISTERED

    updated_experiment = registry.update_experiment_status("exp-001", ExperimentStatus.RUNNING)
    updated_run = registry.update_run_status("run-001", RunStatus.EXPORTED)

    assert updated_experiment.status is ExperimentStatus.RUNNING
    assert updated_experiment.created_at == experiment.created_at
    assert updated_experiment.updated_at >= experiment.updated_at
    assert updated_run.status is RunStatus.EXPORTED


def test_duplicate_identifiers_are_rejected(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    seed = make_seed()
    registry.add_seed(seed)

    with pytest.raises(DuplicateIdentifierError):
        registry.add_seed(seed)


def test_registry_persists_across_instances(tmp_path: Path) -> None:
    path = tmp_path / "registry.sqlite"
    first = Registry(path)
    first.add_seed(make_seed())
    first.add_experiment(make_experiment())
    first.add_run(make_run())

    second = Registry(path)
    summary = second.inspect()

    assert summary.seed_count == 1
    assert summary.experiment_count == 1
    assert summary.run_count == 1
    assert second.get_run("run-001").seed_id == "s1-gridlock-x2"


def test_invalid_experiment_status_transition_rejected(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.add_experiment(make_experiment())

    with pytest.raises(InvalidStatusTransitionError, match="planned -> completed"):
        registry.update_experiment_status("exp-001", ExperimentStatus.COMPLETED)


def test_invalid_run_status_transition_rejected(tmp_path: Path) -> None:
    registry = Registry(tmp_path / "registry.sqlite")
    registry.add_run(make_run())

    with pytest.raises(InvalidStatusTransitionError, match="registered -> completed"):
        registry.update_run_status("run-001", RunStatus.COMPLETED)

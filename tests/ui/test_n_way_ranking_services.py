from __future__ import annotations

from pathlib import Path

from tests.statistical_helpers import study_collection

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.n_way_ranking import (
    NWayRankingConfig,
    NWayRankingStatus,
    NWayRankingStudy,
)
from traffictwin.metrics.results import MetricCollection
from traffictwin.storage.registry import Registry
from traffictwin.ui.services import ServiceError, evaluate_n_way_ranking_for_ui


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


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-nway",
            research_question="N-way registered service",
            baseline_seed_id="seed-family",
            algorithms=["policy-a", "policy-b", "policy-c"],
            common_random_seed_set=[3, 1, 2],
            planned_replicates=3,
        )
    )
    for seed in (1, 2, 3):
        for algorithm, value in {
            "policy-a": 0.9,
            "policy-b": 0.7,
            "policy-c": 0.5,
        }.items():
            collection = _collection(algorithm, seed, value)
            registry.store_metric_collection(
                run_id=collection.run_id,
                metric_version=collection.metric_version,
                source_fingerprint=collection.input_fingerprint,
                payload_json=collection.model_dump_json(),
            )
    return path


def _config(**updates: object) -> NWayRankingConfig:
    payload: dict[str, object] = {
        "experiment_id": "exp-nway",
        "seed_ids": ["seed-family"],
        "algorithms": ["policy-a", "policy-b", "policy-c"],
        "metric_key": "task.completion.rate",
        "expected_random_seeds": [1, 2, 3],
        "bootstrap_repetitions": 1_000,
    }
    payload.update(updates)
    return NWayRankingConfig.model_validate(payload)


def test_n_way_ui_service_delegates_registered_plan(tmp_path: Path) -> None:
    result = evaluate_n_way_ranking_for_ui(_registry(tmp_path), _config())

    assert isinstance(result, NWayRankingStudy)
    assert result.status is NWayRankingStatus.AVAILABLE
    assert result.entries[0].winner_algorithms == ["policy-a"]


def test_n_way_ui_service_rejects_changed_registered_plan(tmp_path: Path) -> None:
    path = _registry(tmp_path)
    unplanned_policy = evaluate_n_way_ranking_for_ui(
        path,
        _config(algorithms=["policy-a", "policy-x"]),
    )
    changed_seeds = evaluate_n_way_ranking_for_ui(
        path,
        _config(expected_random_seeds=[1, 2, 4]),
    )

    assert isinstance(unplanned_policy, ServiceError)
    assert "not declared" in (unplanned_policy.detail or "")
    assert isinstance(changed_seeds, ServiceError)
    assert "common random-seed set" in (changed_seeds.detail or "")

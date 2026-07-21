from __future__ import annotations

from pathlib import Path

from tests.statistical_helpers import study_collections

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.equivalence_testing import (
    EquivalenceConclusion,
    EquivalenceMarginBasis,
    EquivalenceStudy,
    EquivalenceStudyConfig,
)
from traffictwin.storage.registry import Registry
from traffictwin.ui.services import ServiceError, evaluate_equivalence_study_for_ui


def _config(**updates: object) -> EquivalenceStudyConfig:
    payload: dict[str, object] = {
        "experiment_id": "exp-paired",
        "baseline_seed_id": "seed-baseline",
        "variation_seed_id": "seed-variation",
        "algorithm": "policy-a",
        "metric_key": "task.completion.rate",
        "equivalence_margin": 0.2,
        "margin_basis": EquivalenceMarginBasis.PROVISIONAL_DESIGN,
        "margin_justification": "Synthetic service-test margin only",
        "expected_random_seeds": [1, 2, 3, 4, 5],
    }
    payload.update(updates)
    return EquivalenceStudyConfig.model_validate(payload)


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Equivalence service plan",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[1, 2, 3, 4, 5],
            planned_replicates=5,
        )
    )
    for collection in study_collections([-0.05, 0.0, 0.05, 0.02, -0.02]):
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    return path


def test_equivalence_ui_service_delegates_registered_plan(tmp_path: Path) -> None:
    result = evaluate_equivalence_study_for_ui(_registry(tmp_path), _config())

    assert isinstance(result, EquivalenceStudy)
    assert result.tost.conclusion is EquivalenceConclusion.DEMONSTRATED


def test_equivalence_ui_service_rejects_changed_registered_plan(tmp_path: Path) -> None:
    path = _registry(tmp_path)
    unplanned_policy = evaluate_equivalence_study_for_ui(
        path,
        _config(algorithm="policy-x"),
    )
    changed_seeds = evaluate_equivalence_study_for_ui(
        path,
        _config(expected_random_seeds=[1, 2, 3, 4, 6]),
    )

    assert isinstance(unplanned_policy, ServiceError)
    assert "algorithm is not declared" in (unplanned_policy.detail or "")
    assert isinstance(changed_seeds, ServiceError)
    assert "common random-seed set" in (changed_seeds.detail or "")

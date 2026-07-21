from __future__ import annotations

from pathlib import Path

from tests.statistical_helpers import paired_study_config, study_collections

from traffictwin.domain.experiment import Experiment
from traffictwin.experiments.statistical_study import (
    StatisticalStudy,
    StatisticalStudyStatus,
)
from traffictwin.storage.registry import Registry
from traffictwin.ui.services import (
    ServiceError,
    evaluate_statistical_study_for_ui,
    load_statistical_study_catalog,
    statistical_study_experiments_for_ui,
)


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Common-seed comparison",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[1, 2, 3],
            planned_replicates=3,
        )
    )
    for collection in study_collections([1.0, 2.0, 3.0]):
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )
    return path


def test_ui_catalog_and_service_delegate_registered_plan(tmp_path: Path) -> None:
    path = _registry(tmp_path)
    experiments = statistical_study_experiments_for_ui(path)
    catalog = load_statistical_study_catalog(path, "exp-paired")
    study = evaluate_statistical_study_for_ui(path, paired_study_config())

    assert experiments == ["exp-paired"]
    assert not isinstance(catalog, ServiceError)
    assert catalog.baseline_seed_id == "seed-baseline"
    assert catalog.variation_seed_ids == ["seed-variation"]
    assert catalog.expected_random_seeds == [1, 2, 3]
    assert "task.completion.rate" in catalog.metric_keys
    assert isinstance(study, StatisticalStudy)
    assert study.status is StatisticalStudyStatus.AVAILABLE
    assert study.estimate.mean_paired_difference == 2.0


def test_ui_service_rejects_config_that_changes_registered_seed_plan(tmp_path: Path) -> None:
    path = _registry(tmp_path)
    result = evaluate_statistical_study_for_ui(
        path,
        paired_study_config(expected_random_seeds=[1, 2, 4]),
    )

    assert isinstance(result, ServiceError)
    assert "common random-seed set" in (result.detail or "")


def test_ui_service_treats_registered_common_seeds_as_a_set(tmp_path: Path) -> None:
    path = tmp_path / "unsorted.sqlite"
    registry = Registry(path)
    registry.add_experiment(
        Experiment(
            experiment_id="exp-paired",
            research_question="Common-seed comparison",
            baseline_seed_id="seed-baseline",
            variation_seed_ids=["seed-variation"],
            algorithms=["policy-a"],
            common_random_seed_set=[3, 1, 2],
            planned_replicates=3,
        )
    )
    for collection in study_collections([1.0, 2.0, 3.0]):
        registry.store_metric_collection(
            run_id=collection.run_id,
            metric_version=collection.metric_version,
            source_fingerprint=collection.input_fingerprint,
            payload_json=collection.model_dump_json(),
        )

    catalog = load_statistical_study_catalog(path, "exp-paired")
    result = evaluate_statistical_study_for_ui(path, paired_study_config())

    assert not isinstance(catalog, ServiceError)
    assert catalog.expected_random_seeds == [1, 2, 3]
    assert isinstance(result, StatisticalStudy)


def test_ui_catalog_reports_absent_registry_evidence_without_fabrication(tmp_path: Path) -> None:
    path = tmp_path / "empty.sqlite"
    experiments = statistical_study_experiments_for_ui(path)

    assert experiments == []

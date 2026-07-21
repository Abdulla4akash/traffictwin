from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from traffictwin.experiments.statistical_study import PairedStudyConfig
from traffictwin.metrics.results import MetricCollection, MetricStatus, MetricValue

FIXED_STUDY_TIME = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)


def fixed_study_clock() -> datetime:
    return FIXED_STUDY_TIME


def paired_study_config(**updates: object) -> PairedStudyConfig:
    payload: dict[str, object] = {
        "experiment_id": "exp-paired",
        "baseline_seed_id": "seed-baseline",
        "variation_seed_id": "seed-variation",
        "algorithm": "policy-a",
        "metric_key": "task.completion.rate",
        "expected_random_seeds": [1, 2, 3],
        "bootstrap_repetitions": 1_000,
        "randomisation_repetitions": 1_000,
        "resampling_seed": 77,
    }
    payload.update(updates)
    return PairedStudyConfig.model_validate(payload)


def study_collection(
    role: str,
    random_seed: int,
    value: object,
    *,
    run_id: str | None = None,
    metric_key: str = "task.completion.rate",
    metric_status: MetricStatus = MetricStatus.AVAILABLE,
    unit: str = "fraction",
    metric_version: str = "1.0",
    implementation_version: str = "1.0",
    algorithm: str = "policy-a",
    checkpoint: str | None = None,
    experiment_id: str = "exp-paired",
    environment: str | None = "synthetic-test",
    environment_version: str | None = "1.0",
    environment_commit: str | None = None,
    synthetic: bool = True,
    input_fingerprint: str | None = None,
    metadata: Mapping[str, object] | None = None,
    generated_at: datetime = FIXED_STUDY_TIME,
) -> MetricCollection:
    seed_id = "seed-baseline" if role == "baseline" else "seed-variation"
    resolved_run_id = run_id or f"run-{role}-{random_seed}"
    metric = MetricValue(
        metric_key=metric_key,
        status=metric_status,
        value=value,
        unit=unit,
        scope="run",
        implementation_version=implementation_version,
        run_id=resolved_run_id,
        experiment_id=experiment_id,
        seed_id=seed_id,
        algorithm=algorithm,
        checkpoint=checkpoint,
        random_seed=random_seed,
        synthetic=synthetic,
        environment=environment,
        environment_version=environment_version,
        environment_commit=environment_commit,
        computed_at=generated_at,
        metadata=dict(metadata or {}),
    )
    return MetricCollection(
        run_id=resolved_run_id,
        metric_version=metric_version,
        results=[metric],
        unavailable_count=int(metric_status is not MetricStatus.AVAILABLE),
        partial_count=int(metric_status is MetricStatus.PARTIAL),
        generated_at=generated_at,
        input_fingerprint=input_fingerprint or f"fingerprint-{resolved_run_id}",
    )


def study_collections(
    differences: list[float],
    *,
    baseline_value: float = 10.0,
) -> list[MetricCollection]:
    collections: list[MetricCollection] = []
    for seed, difference in enumerate(differences, start=1):
        collections.extend(
            [
                study_collection("baseline", seed, baseline_value),
                study_collection("variation", seed, baseline_value + difference),
            ]
        )
    return collections

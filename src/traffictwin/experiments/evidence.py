"""Deterministic experiment-level EvidencePack construction."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.evidence.pack import EvidencePack
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonScalar, MetricCollection, MetricStatus, MetricValue


class ObjectiveDirection(StrEnum):
    """Direction used when ranking a scalar experiment metric."""

    MAXIMISE = "maximise"
    MINIMISE = "minimise"


class PairedMetricEndpoint(BaseModel):
    """One fully identified endpoint in a training-validation pair."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    seed_id: str = Field(min_length=1)
    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None
    random_seed: int = Field(ge=0)
    metric_key: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    unit: str
    environment: str = Field(min_length=1)
    environment_version: str | None = None
    environment_commit: str | None = None
    value: float


class TrainingValidationObservation(BaseModel):
    """One explicit, compatibility-checked training-versus-validation pair."""

    model_config = ConfigDict(extra="forbid")

    training: PairedMetricEndpoint
    validation: PairedMetricEndpoint

    @model_validator(mode="after")
    def validate_compatibility(self) -> TrainingValidationObservation:
        """Reject pairings that cannot support a controlled scalar gap."""

        if self.training.run_id == self.validation.run_id:
            raise ValueError("training and validation run IDs must differ")
        matching_fields = (
            "algorithm",
            "experiment_id",
            "checkpoint",
            "random_seed",
            "metric_key",
            "metric_version",
            "unit",
        )
        mismatches = [
            field
            for field in matching_fields
            if getattr(self.training, field) != getattr(self.validation, field)
        ]
        if mismatches:
            raise ValueError("training-validation pair mismatch: " + ", ".join(sorted(mismatches)))
        return self

    @property
    def algorithm(self) -> str:
        return self.validation.algorithm

    @property
    def random_seed(self) -> int:
        return self.validation.random_seed

    @property
    def metric_key(self) -> str:
        return self.validation.metric_key

    @property
    def unit(self) -> str:
        return self.validation.unit

    @property
    def training_value(self) -> float:
        return self.training.value

    @property
    def validation_value(self) -> float:
        return self.validation.value


class ExperimentEvidenceOptions(BaseModel):
    """Configuration for reusable experiment-level evidence."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(min_length=1)
    primary_metric_key: str = "task.completion.rate"
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE
    always_local_algorithm: str = "synthetic-always-local"
    pressure_metric_keys: list[str] = Field(
        default_factory=lambda: ["task.incomplete.rate", "infra.utilisation.mean"]
    )


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_experiment_evidence_pack(
    collections: list[MetricCollection],
    options: ExperimentEvidenceOptions,
    *,
    training_validation: list[TrainingValidationObservation] | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> EvidencePack:
    """Build experiment evidence without inventing unavailable observations."""

    if not collections:
        raise ValueError("at least one MetricCollection is required")
    generated_at = clock()
    config = MetricEngineConfig()
    observations = training_validation or []
    algorithm_values: dict[str, list[float]] = defaultdict(list)
    pressure_values: list[float] = []
    random_seeds: set[int] = set()
    source_run_ids: list[str] = []
    source_fingerprints: list[str] = []
    synthetic_flags: set[bool] = set()

    for collection in collections:
        source_run_ids.append(collection.run_id)
        if collection.input_fingerprint:
            source_fingerprints.append(collection.input_fingerprint)
        run_metric = collection.results[0] if collection.results else None
        if run_metric is None:
            continue
        synthetic_flags.add(run_metric.synthetic)
        random_seeds.add(run_metric.random_seed)
        primary = _numeric_metric(collection, options.primary_metric_key)
        if primary is not None:
            algorithm_values[run_metric.algorithm].append(primary)
        for key in options.pressure_metric_keys:
            if (value := _numeric_metric(collection, key)) is not None:
                pressure_values.append(value)

    _validate_collection_compatibility(collections, options)
    _validate_training_validation_observations(observations, options)

    algorithm_means = {
        algorithm: sum(values) / len(values)
        for algorithm, values in sorted(algorithm_values.items())
        if values
    }
    best = _best_value(list(algorithm_means.values()), options.objective)
    worst = _worst_value(list(algorithm_means.values()), options.objective)
    dispersion = abs(best - worst) if best is not None and worst is not None else None
    local_value = algorithm_means.get(options.always_local_algorithm)
    local_gap = (
        _regret(local_value, best, options.objective)
        if local_value is not None and best is not None
        else None
    )
    absolute_gaps = [abs(row.validation_value - row.training_value) for row in observations]
    signed_gaps = [row.validation_value - row.training_value for row in observations]
    experiment_context: dict[str, JsonScalar] = {
        "run_id": f"experiment-{options.experiment_id}",
        "experiment_id": options.experiment_id,
        "seed_id": "multiple",
        "algorithm": "multiple",
        "checkpoint": None,
        "random_seed": 0,
        "synthetic": bool(synthetic_flags) and synthetic_flags == {True},
        "environment": "experiment_aggregation",
        "environment_version": "1.0",
        "environment_commit": None,
    }
    metrics = [
        _metric(
            "experiment.algorithm.count",
            len(algorithm_means),
            "count",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.cross_algorithm_dispersion",
            dispersion,
            "ratio",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.always_local_gap_from_best",
            local_gap,
            "ratio",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.pressure.indicator",
            sum(pressure_values) / len(pressure_values) if pressure_values else None,
            "ratio",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.training_validation.pair_count",
            len(observations),
            "count",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.training_validation.max_absolute_gap",
            max(absolute_gaps) if absolute_gaps else None,
            observations[0].unit if observations else "unknown",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.training_validation.mean_absolute_gap",
            sum(absolute_gaps) / len(absolute_gaps) if absolute_gaps else None,
            observations[0].unit if observations else "unknown",
            experiment_context,
            generated_at,
            config,
        ),
        _metric(
            "experiment.training_validation.mean_signed_gap",
            sum(signed_gaps) / len(signed_gaps) if signed_gaps else None,
            observations[0].unit if observations else "unknown",
            experiment_context,
            generated_at,
            config,
        ),
    ]
    fingerprint = _fingerprint(
        {
            "options": options.model_dump(mode="json"),
            "run_ids": sorted(source_run_ids),
            "source_fingerprints": sorted(source_fingerprints),
            "training_validation": [
                row.model_dump(mode="json")
                for row in sorted(
                    observations,
                    key=lambda item: (item.algorithm, item.random_seed, item.metric_key),
                )
            ],
        }
    )
    collection = MetricCollection(
        run_id=str(experiment_context["run_id"]),
        metric_version=f"{config.metric_version}+experiment.1",
        results=metrics,
        unavailable_count=sum(metric.status is MetricStatus.UNAVAILABLE for metric in metrics),
        partial_count=0,
        generated_at=generated_at,
        input_fingerprint=fingerprint,
    )
    warnings = ["Experiment metrics are descriptive aggregates and do not establish causality."]
    if synthetic_flags == {True}:
        warnings.append(
            "All source collections are synthetic software demonstrations, not calibrated runs."
        )
    elif len(synthetic_flags) > 1:
        warnings.append("Synthetic and non-synthetic collections are mixed in this evidence pack.")
    if not observations:
        warnings.append(
            "No explicit training-validation pairs were supplied; R5 remains unavailable."
        )
    return EvidencePack(
        pack_id=f"evidence-experiment-{options.experiment_id}-{fingerprint[:12]}",
        generated_at=generated_at,
        synthetic=bool(experiment_context["synthetic"]),
        run_context={
            **{key: value for key, value in experiment_context.items() if key != "synthetic"},
        },
        source_bundle_fingerprint=fingerprint,
        validation_summary={
            "status": "accepted",
            "may_import": True,
            "finding_count": 0,
            "counts_by_severity": {},
            "validator_version": "experiment-evidence.1",
        },
        evidence_availability=EvidenceAvailability(
            tasks=EvidenceStatus.PARTIAL,
            infrastructure=EvidenceStatus.PARTIAL,
            vehicles=EvidenceStatus.UNAVAILABLE,
            traffic=EvidenceStatus.PARTIAL,
            trips=EvidenceStatus.PARTIAL,
            incidents=EvidenceStatus.UNAVAILABLE,
            diagnosis=EvidenceStatus.AVAILABLE,
        ),
        metric_engine_config=config,
        metric_collection=collection,
        excluded_record_counts={},
        warnings=warnings,
        provenance={
            "source": "TrafficTwin experiment aggregation",
            "source_run_count": len(collections),
            "source_run_ids": ",".join(sorted(source_run_ids)),
            "random_seed_count": len(random_seeds),
            "primary_metric_key": options.primary_metric_key,
            "objective": options.objective.value,
            "training_validation_pair_count": len(observations),
            "training_environments": ",".join(
                sorted({row.training.environment for row in observations})
            ),
            "validation_environments": ",".join(
                sorted({row.validation.environment for row in observations})
            ),
        },
    )


def training_validation_observation_from_collections(
    training: MetricCollection,
    validation: MetricCollection,
    metric_key: str,
) -> TrainingValidationObservation:
    """Build one explicit pair from compatible stored metric collections."""

    training_metric = _available_scalar_metric(training, metric_key)
    validation_metric = _available_scalar_metric(validation, metric_key)
    return TrainingValidationObservation(
        training=_endpoint(training, training_metric),
        validation=_endpoint(validation, validation_metric),
    )


def _endpoint(collection: MetricCollection, metric: MetricValue) -> PairedMetricEndpoint:
    if metric.experiment_id is None:
        raise ValueError(f"run {collection.run_id!r} has no experiment provenance")
    if metric.environment is None:
        raise ValueError(f"run {collection.run_id!r} has no environment provenance")
    return PairedMetricEndpoint(
        run_id=collection.run_id,
        experiment_id=metric.experiment_id,
        seed_id=metric.seed_id,
        algorithm=metric.algorithm,
        checkpoint=metric.checkpoint,
        random_seed=metric.random_seed,
        metric_key=metric.metric_key,
        metric_version=collection.metric_version,
        unit=metric.unit,
        environment=metric.environment,
        environment_version=metric.environment_version,
        environment_commit=metric.environment_commit,
        value=float(metric.value),
    )


def _available_scalar_metric(collection: MetricCollection, key: str) -> MetricValue:
    metric = collection.by_key().get(key)
    if metric is None or metric.status is not MetricStatus.AVAILABLE:
        raise ValueError(f"paired metric is unavailable: {collection.run_id}/{key}")
    if not isinstance(metric.value, int | float) or isinstance(metric.value, bool):
        raise ValueError(f"paired metric is non-scalar: {collection.run_id}/{key}")
    if not math.isfinite(float(metric.value)):
        raise ValueError(f"paired metric is non-finite: {collection.run_id}/{key}")
    return metric


def _validate_collection_compatibility(
    collections: list[MetricCollection],
    options: ExperimentEvidenceOptions,
) -> None:
    observations = [
        (collection, metric)
        for collection in collections
        if (metric := collection.by_key().get(options.primary_metric_key)) is not None
        and metric.status is MetricStatus.AVAILABLE
    ]
    if not observations:
        return
    units = {metric.unit for _, metric in observations}
    metric_versions = {collection.metric_version for collection, _ in observations}
    implementations = {metric.implementation_version for _, metric in observations}
    environments = {
        (metric.environment, metric.environment_version, metric.environment_commit)
        for _, metric in observations
    }
    experiments = {metric.experiment_id for _, metric in observations}
    if any(metric.environment is None for _, metric in observations):
        raise ValueError(f"environment provenance is required for {options.primary_metric_key}")
    for label, values in (
        ("unit", units),
        ("metric version", metric_versions),
        ("metric implementation", implementations),
        ("environment", environments),
    ):
        if len(values) > 1:
            raise ValueError(
                f"incompatible {label} values for {options.primary_metric_key}: "
                f"{sorted(str(value) for value in values)}"
            )
    if experiments != {options.experiment_id}:
        raise ValueError(
            f"metric collections do not all belong to experiment {options.experiment_id!r}"
        )
    checkpoints: dict[str, set[str | None]] = defaultdict(set)
    for _, metric in observations:
        checkpoints[metric.algorithm].add(metric.checkpoint)
    inconsistent = sorted(algorithm for algorithm, values in checkpoints.items() if len(values) > 1)
    if inconsistent:
        raise ValueError("algorithms use multiple checkpoints: " + ", ".join(inconsistent))


def _validate_training_validation_observations(
    observations: list[TrainingValidationObservation],
    options: ExperimentEvidenceOptions,
) -> None:
    if not observations:
        return
    wrong_keys = sorted({row.metric_key for row in observations} - {options.primary_metric_key})
    if wrong_keys:
        raise ValueError(
            "training-validation metric does not match primary metric: " + ", ".join(wrong_keys)
        )
    experiments = {row.training.experiment_id for row in observations}
    if experiments != {options.experiment_id}:
        raise ValueError(
            f"training-validation pairs do not all belong to experiment {options.experiment_id!r}"
        )
    units = {row.unit for row in observations}
    versions = {row.training.metric_version for row in observations}
    if len(units) > 1:
        raise ValueError("training-validation pairs use incompatible units")
    if len(versions) > 1:
        raise ValueError("training-validation pairs use incompatible metric versions")
    algorithms = {row.algorithm for row in observations}
    if len(algorithms) > 1:
        raise ValueError("training-validation pairs use multiple algorithms")
    checkpoints = {row.training.checkpoint for row in observations}
    if len(checkpoints) > 1:
        raise ValueError("training-validation pairs use multiple checkpoints")
    training_environments = {
        (
            row.training.environment,
            row.training.environment_version,
            row.training.environment_commit,
        )
        for row in observations
    }
    validation_environments = {
        (
            row.validation.environment,
            row.validation.environment_version,
            row.validation.environment_commit,
        )
        for row in observations
    }
    if len(training_environments) > 1:
        raise ValueError("training-validation pairs use multiple training environments")
    if len(validation_environments) > 1:
        raise ValueError("training-validation pairs use multiple validation environments")
    random_seeds = [row.random_seed for row in observations]
    if len(set(random_seeds)) != len(random_seeds):
        raise ValueError("training-validation pairs reuse random seeds")
    training_run_ids = [row.training.run_id for row in observations]
    validation_run_ids = [row.validation.run_id for row in observations]
    if len(set(training_run_ids)) != len(training_run_ids) or len(set(validation_run_ids)) != len(
        validation_run_ids
    ):
        raise ValueError("training-validation pairs reuse run IDs")


def _numeric_metric(collection: MetricCollection, key: str) -> float | None:
    metric = collection.by_key().get(key)
    if metric is None or metric.status is not MetricStatus.AVAILABLE:
        return None
    value = metric.value
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _metric(
    key: str,
    value: float | int | None,
    unit: str,
    context: dict[str, JsonScalar],
    computed_at: datetime,
    config: MetricEngineConfig,
) -> MetricValue:
    available = value is not None
    return MetricValue(
        metric_key=key,
        status=MetricStatus.AVAILABLE if available else MetricStatus.UNAVAILABLE,
        value=value,
        unit=unit,
        scope="experiment",
        dimensions={},
        required_evidence=["metric_collections", "experiment_aggregation"],
        missing_evidence=[] if available else ["compatible scalar observations"],
        reason_codes=[],
        warnings=[],
        implementation_version=f"{config.metric_version}+experiment.1",
        run_id=str(context["run_id"]),
        experiment_id=str(context["experiment_id"]),
        seed_id=str(context["seed_id"]),
        algorithm=str(context["algorithm"]),
        checkpoint=None,
        random_seed=0,
        synthetic=bool(context["synthetic"]),
        environment=str(context["environment"]),
        environment_version=str(context["environment_version"]),
        environment_commit=None,
        computed_at=computed_at,
        metadata={"source": "deterministic experiment aggregation"},
    )


def _best_value(values: list[float], objective: ObjectiveDirection) -> float | None:
    if not values:
        return None
    return max(values) if objective is ObjectiveDirection.MAXIMISE else min(values)


def _worst_value(values: list[float], objective: ObjectiveDirection) -> float | None:
    if not values:
        return None
    return min(values) if objective is ObjectiveDirection.MAXIMISE else max(values)


def _regret(value: float, best: float, objective: ObjectiveDirection) -> float:
    return best - value if objective is ObjectiveDirection.MAXIMISE else value - best


def _fingerprint(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

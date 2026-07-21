"""Deterministic per-seed policy winner maps and regret summaries."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.experiments.evidence import ObjectiveDirection
from traffictwin.metrics.results import MetricCollection, MetricStatus


class PolicyScore(BaseModel):
    """One policy's descriptive score within a seed family."""

    model_config = ConfigDict(extra="forbid")

    algorithm: str
    observation_count: int = Field(ge=1)
    mean: float
    standard_deviation: float = Field(ge=0.0)
    minimum: float
    maximum: float
    rank: int = Field(ge=1)
    regret: float = Field(ge=0.0)
    winner: bool


class WinnerMapEntry(BaseModel):
    """Winner-map result for one seed identifier."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str
    metric_key: str
    unit: str
    objective: ObjectiveDirection
    winner_algorithms: list[str]
    policy_scores: list[PolicyScore]
    random_seed_count: int = Field(ge=0)


class WinnerMapReport(BaseModel):
    """Versioned deterministic winner-map report."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    generated_at: datetime
    metric_key: str
    objective: ObjectiveDirection
    metric_versions: list[str]
    synthetic_only: bool
    entries: list[WinnerMapEntry]
    warnings: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        """Return machine-readable JSON."""

        return self.model_dump_json(indent=2)


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def build_winner_map(
    collections: list[MetricCollection],
    *,
    metric_key: str = "task.completion.rate",
    objective: ObjectiveDirection = ObjectiveDirection.MAXIMISE,
    tie_tolerance: float = 1e-12,
    seed_aliases: Mapping[str, str] | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> WinnerMapReport:
    """Rank policies independently for every seed using available scalar metrics."""

    if tie_tolerance < 0:
        raise ValueError("tie_tolerance must be non-negative")
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    units: dict[str, set[str]] = defaultdict(set)
    metric_versions: dict[str, set[str]] = defaultdict(set)
    implementation_versions: dict[str, set[str]] = defaultdict(set)
    environments: dict[str, set[tuple[str | None, str | None, str | None]]] = defaultdict(set)
    checkpoints: dict[tuple[str, str], set[str | None]] = defaultdict(set)
    random_seeds: dict[str, set[int]] = defaultdict(set)
    synthetic_flags: set[bool] = set()
    for collection in collections:
        if not collection.results:
            continue
        context = collection.results[0]
        synthetic_flags.add(context.synthetic)
        metric = collection.by_key().get(metric_key)
        if metric is None or metric.status is not MetricStatus.AVAILABLE:
            continue
        if not isinstance(metric.value, int | float) or isinstance(metric.value, bool):
            continue
        value = float(metric.value)
        if not math.isfinite(value):
            continue
        seed_id = (
            seed_aliases.get(context.seed_id, context.seed_id) if seed_aliases else context.seed_id
        )
        grouped[(seed_id, context.algorithm)].append(value)
        units[seed_id].add(metric.unit)
        metric_versions[seed_id].add(collection.metric_version)
        implementation_versions[seed_id].add(metric.implementation_version)
        environments[seed_id].add(
            (metric.environment, metric.environment_version, metric.environment_commit)
        )
        checkpoints[(seed_id, context.algorithm)].add(metric.checkpoint)
        random_seeds[seed_id].add(context.random_seed)

    entries: list[WinnerMapEntry] = []
    warnings: list[str] = []
    for seed_id in sorted({seed for seed, _ in grouped}):
        algorithms = {
            algorithm: values
            for (seed, algorithm), values in grouped.items()
            if seed == seed_id and values
        }
        means = {algorithm: sum(values) / len(values) for algorithm, values in algorithms.items()}
        if not means:
            continue
        incompatibilities: list[str] = []
        if len(units[seed_id]) > 1:
            incompatibilities.append(f"units={sorted(units[seed_id])}")
        if len(metric_versions[seed_id]) > 1:
            incompatibilities.append(f"metric_versions={sorted(metric_versions[seed_id])}")
        if len(implementation_versions[seed_id]) > 1:
            incompatibilities.append(f"implementations={sorted(implementation_versions[seed_id])}")
        if len(environments[seed_id]) > 1:
            incompatibilities.append(
                "environments=" + str(sorted(str(value) for value in environments[seed_id]))
            )
        elif any(value[0] is None for value in environments[seed_id]):
            incompatibilities.append("environment provenance is missing")
        inconsistent_algorithms = sorted(
            algorithm for algorithm in algorithms if len(checkpoints[(seed_id, algorithm)]) > 1
        )
        if inconsistent_algorithms:
            incompatibilities.append(f"checkpoint_algorithms={inconsistent_algorithms}")
        if incompatibilities:
            warnings.append(
                f"Seed {seed_id!r} was excluded because observations are incompatible: "
                + "; ".join(incompatibilities)
                + "."
            )
            continue
        best = (
            max(means.values()) if objective is ObjectiveDirection.MAXIMISE else min(means.values())
        )
        ordered = sorted(
            means,
            key=lambda algorithm: (
                -means[algorithm] if objective is ObjectiveDirection.MAXIMISE else means[algorithm],
                algorithm,
            ),
        )
        rank_by_algorithm: dict[str, int] = {}
        last_value: float | None = None
        last_rank = 0
        for position, algorithm in enumerate(ordered, start=1):
            value = means[algorithm]
            if last_value is None or abs(value - last_value) > tie_tolerance:
                last_rank = position
                last_value = value
            rank_by_algorithm[algorithm] = last_rank
        scores = [
            PolicyScore(
                algorithm=algorithm,
                observation_count=len(algorithms[algorithm]),
                mean=means[algorithm],
                standard_deviation=(
                    statistics.pstdev(algorithms[algorithm])
                    if len(algorithms[algorithm]) > 1
                    else 0.0
                ),
                minimum=min(algorithms[algorithm]),
                maximum=max(algorithms[algorithm]),
                rank=rank_by_algorithm[algorithm],
                regret=max(
                    0.0,
                    best - means[algorithm]
                    if objective is ObjectiveDirection.MAXIMISE
                    else means[algorithm] - best,
                ),
                winner=abs(means[algorithm] - best) <= tie_tolerance,
            )
            for algorithm in ordered
        ]
        seed_units = sorted(units[seed_id])
        entries.append(
            WinnerMapEntry(
                seed_id=seed_id,
                metric_key=metric_key,
                unit=seed_units[0],
                objective=objective,
                winner_algorithms=sorted(score.algorithm for score in scores if score.winner),
                policy_scores=scores,
                random_seed_count=len(random_seeds[seed_id]),
            )
        )
    if synthetic_flags == {True}:
        warnings.append(
            "Winner-map results use synthetic policy profiles and do not compare trained "
            "algorithms."
        )
    if not entries:
        warnings.append(f"No available scalar observations were found for {metric_key}.")
    return WinnerMapReport(
        generated_at=clock(),
        metric_key=metric_key,
        objective=objective,
        metric_versions=sorted({collection.metric_version for collection in collections}),
        synthetic_only=bool(synthetic_flags) and synthetic_flags == {True},
        entries=entries,
        warnings=warnings,
    )

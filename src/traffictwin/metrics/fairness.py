"""Evidence-gated operational vehicle-tier and RSU fairness metrics."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime

from traffictwin.canonical.records import InfrastructureRecord
from traffictwin.canonical.tables import CanonicalTables
from traffictwin.domain.fairness import (
    DEFAULT_OPERATIONAL_FAIRNESS_POLICY,
    OperationalFairnessPolicy,
)
from traffictwin.evidence.availability import EvidenceAvailability, EvidenceStatus
from traffictwin.metrics.availability import available_metric, unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import JsonObject, MetricValue, RunMetricContext, UnavailableReason
from traffictwin.metrics.statistics import arithmetic_mean

VEHICLE_TIER_FAIRNESS_KEYS = (
    "task.completion.rate_by_vehicle_tier",
    "fairness.vehicle_tier.completion_rate.max_gap",
    "fairness.vehicle_tier.completion_rate.jain",
)
RSU_FAIRNESS_KEYS = (
    "fairness.rsu.capacity_normalised_load.by_group",
    "fairness.rsu.capacity_normalised_load.max_gap",
    "infra.load_balance.jain_capacity_normalised",
)
FAIRNESS_KEYS = (*VEHICLE_TIER_FAIRNESS_KEYS, *RSU_FAIRNESS_KEYS)


def fairness_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
    policy: OperationalFairnessPolicy = DEFAULT_OPERATIONAL_FAIRNESS_POLICY,
) -> list[MetricValue]:
    """Compute the complete evidence-gated operational fairness family."""

    return [
        *_vehicle_tier_metrics(tables, context, evidence, config, computed_at, policy),
        *_rsu_metrics(tables, context, evidence, config, computed_at, policy),
    ]


def stable_vehicle_tiers(tables: CanonicalTables) -> dict[str, str]:
    """Return exact vehicle-tier mappings that are non-empty and stable in scope."""

    observed: dict[str, set[str]] = defaultdict(set)
    for vehicle in tables.vehicles:
        if vehicle.tier:
            observed[vehicle.vehicle_id].add(vehicle.tier)
    return {
        vehicle_id: next(iter(tiers)) for vehicle_id, tiers in observed.items() if len(tiers) == 1
    }


def capacity_normalised_load(record: InfrastructureRecord) -> float | None:
    """Return one admitted RSU load observation under the v1.0 policy."""

    if (
        record.capacity is None
        or record.capacity <= 0
        or record.active_tasks is None
        or record.active_tasks < 0
    ):
        return None
    return record.active_tasks / record.capacity


def _vehicle_tier_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
    policy: OperationalFairnessPolicy,
) -> list[MetricValue]:
    base_metadata = _base_metadata(policy, "vehicle_tier")
    if evidence.tasks is not EvidenceStatus.AVAILABLE:
        return _unavailable_family(
            VEHICLE_TIER_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            ["tasks"],
            base_metadata,
        )
    if evidence.vehicles is not EvidenceStatus.AVAILABLE or not tables.vehicles:
        return _unavailable_family(
            VEHICLE_TIER_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.VEHICLE_TIER_UNAVAILABLE],
            ["vehicles.tier"],
            base_metadata,
        )
    if not tables.tasks:
        return _unavailable_family(
            VEHICLE_TIER_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.NO_VALID_ROWS],
            ["tasks"],
            base_metadata,
        )

    tiers = stable_vehicle_tiers(tables)
    all_tier_observations: dict[str, set[str]] = defaultdict(set)
    for vehicle in tables.vehicles:
        if vehicle.tier:
            all_tier_observations[vehicle.vehicle_id].add(vehicle.tier)
    if not all_tier_observations:
        return _unavailable_family(
            VEHICLE_TIER_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.VEHICLE_TIER_UNAVAILABLE],
            ["vehicles.tier"],
            base_metadata,
        )
    conflicting_ids = {
        vehicle_id for vehicle_id, values in all_tier_observations.items() if len(values) > 1
    }
    grouped: dict[str, list[float]] = defaultdict(list)
    for task in tables.tasks:
        tier = tiers.get(task.vehicle_id)
        if tier is not None:
            grouped[tier].append(float(task.completed))
    metadata = _group_metadata(
        policy,
        "vehicle_tier",
        grouped,
        population_count=len(tables.tasks),
        extra={"conflicting_vehicle_count": len(conflicting_ids)},
    )
    rejection = _admission_rejection(grouped, metadata, policy)
    if rejection is not None:
        reasons, missing, warning = rejection
        return _unavailable_family(
            VEHICLE_TIER_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            reasons,
            missing,
            metadata,
            warnings=[warning],
        )

    group_means = _group_means(grouped)
    return [
        available_metric(
            "task.completion.rate_by_vehicle_tier",
            group_means,
            context,
            config,
            computed_at,
            metadata=metadata,
        ),
        available_metric(
            "fairness.vehicle_tier.completion_rate.max_gap",
            _max_gap(group_means),
            context,
            config,
            computed_at,
            warnings=[
                "A small group gap does not imply a high overall completion rate or protected-"
                "attribute fairness."
            ],
            metadata=metadata,
        ),
        _jain_metric(
            "fairness.vehicle_tier.completion_rate.jain",
            group_means,
            context,
            config,
            computed_at,
            metadata,
        ),
    ]


def _rsu_metrics(
    tables: CanonicalTables,
    context: RunMetricContext,
    evidence: EvidenceAvailability,
    config: MetricEngineConfig,
    computed_at: datetime,
    policy: OperationalFairnessPolicy,
) -> list[MetricValue]:
    base_metadata = _base_metadata(policy, "rsu")
    if evidence.infrastructure is not EvidenceStatus.AVAILABLE:
        return _unavailable_family(
            RSU_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.REQUIRED_TABLE_UNAVAILABLE],
            ["infrastructure"],
            base_metadata,
        )
    if not tables.infrastructure:
        return _unavailable_family(
            RSU_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [UnavailableReason.NO_VALID_ROWS],
            ["infrastructure"],
            base_metadata,
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    observed_group_support: dict[str, int] = defaultdict(int)
    for record in tables.infrastructure:
        observed_group_support[record.rsu_id] += 1
        load = capacity_normalised_load(record)
        if load is not None:
            grouped[record.rsu_id].append(load)
    for rsu_id in observed_group_support:
        grouped.setdefault(rsu_id, [])
    metadata = _group_metadata(
        policy,
        "rsu",
        grouped,
        population_count=len(tables.infrastructure),
    )
    if not any(grouped.values()):
        return _unavailable_family(
            RSU_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            [
                UnavailableReason.CAPACITY_UNAVAILABLE,
                UnavailableReason.REQUIRED_FIELD_UNAVAILABLE,
            ],
            ["infrastructure.active_tasks", "infrastructure.capacity"],
            metadata,
            warnings=[
                "No canonical RSU row has both non-negative active tasks and positive capacity."
            ],
        )
    rejection = _admission_rejection(grouped, metadata, policy)
    if rejection is not None:
        reasons, missing, warning = rejection
        return _unavailable_family(
            RSU_FAIRNESS_KEYS,
            context,
            config,
            computed_at,
            reasons,
            missing,
            metadata,
            warnings=[warning],
        )

    group_means = _group_means(grouped)
    return [
        available_metric(
            "fairness.rsu.capacity_normalised_load.by_group",
            group_means,
            context,
            config,
            computed_at,
            metadata=metadata,
        ),
        available_metric(
            "fairness.rsu.capacity_normalised_load.max_gap",
            _max_gap(group_means),
            context,
            config,
            computed_at,
            warnings=[
                "Capacity-normalised load equality is operational balance evidence, not task-"
                "outcome equality or causal attribution."
            ],
            metadata=metadata,
        ),
        _jain_metric(
            "infra.load_balance.jain_capacity_normalised",
            group_means,
            context,
            config,
            computed_at,
            metadata,
        ),
    ]


def _admission_rejection(
    grouped: dict[str, list[float]],
    metadata: JsonObject,
    policy: OperationalFairnessPolicy,
) -> tuple[list[UnavailableReason], list[str], str] | None:
    coverage = metadata["coverage_fraction"]
    if not isinstance(coverage, int | float) or coverage < policy.minimum_coverage_fraction:
        return (
            [UnavailableReason.GROUP_COVERAGE_INSUFFICIENT],
            ["complete stable group membership and eligible values"],
            "Group coverage is below the fixed v1.0 complete-coverage requirement.",
        )
    if len(grouped) < policy.minimum_group_count:
        return (
            [UnavailableReason.INSUFFICIENT_GROUP_COUNT],
            [f"at least {policy.minimum_group_count} operational groups"],
            "Fewer than two operational groups are present; disparity is not defined.",
        )
    undersupported = [
        group
        for group, values in sorted(grouped.items())
        if len(values) < policy.minimum_group_support
    ]
    if undersupported:
        return (
            [UnavailableReason.INSUFFICIENT_GROUP_SUPPORT],
            [f"minimum support for groups: {', '.join(undersupported)}"],
            "At least one operational group has fewer than two eligible observations.",
        )
    return None


def _base_metadata(policy: OperationalFairnessPolicy, dimension: str) -> JsonObject:
    semantics = (
        policy.vehicle_tier_semantics if dimension == "vehicle_tier" else policy.rsu_group_semantics
    )
    return {
        "fairness_policy_version": policy.schema_version,
        "fairness_policy_fingerprint": policy.fingerprint(),
        "group_dimension": dimension,
        "group_semantics": semantics,
        "minimum_group_count": policy.minimum_group_count,
        "minimum_group_support": policy.minimum_group_support,
        "minimum_coverage_fraction": policy.minimum_coverage_fraction,
        "attribute_interpretation": policy.attribute_interpretation,
    }


def _group_metadata(
    policy: OperationalFairnessPolicy,
    dimension: str,
    grouped: dict[str, list[float]],
    *,
    population_count: int,
    extra: JsonObject | None = None,
) -> JsonObject:
    eligible_count = sum(len(values) for values in grouped.values())
    groups = sorted(grouped)
    metadata: JsonObject = {
        **_base_metadata(policy, dimension),
        "group_set_fingerprint": _group_set_fingerprint(dimension, groups),
        "group_count": len(groups),
        "group_support_counts": {group: len(grouped[group]) for group in groups},
        "eligible_count": eligible_count,
        "population_count": population_count,
        "coverage_fraction": eligible_count / population_count if population_count else None,
    }
    if extra:
        metadata.update(extra)
    return metadata


def _group_set_fingerprint(dimension: str, groups: list[str]) -> str:
    encoded = json.dumps(
        {"group_dimension": dimension, "groups": groups},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _group_means(grouped: dict[str, list[float]]) -> dict[str, float]:
    return {
        group: mean
        for group, values in sorted(grouped.items())
        if (mean := arithmetic_mean(values)) is not None
    }


def _max_gap(group_means: dict[str, float]) -> float:
    values = list(group_means.values())
    return max(values) - min(values)


def _jain_metric(
    key: str,
    group_means: dict[str, float],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    metadata: JsonObject,
) -> MetricValue:
    values = list(group_means.values())
    denominator = len(values) * sum(value * value for value in values)
    if denominator == 0:
        return unavailable_metric(
            key,
            context,
            config,
            computed_at,
            [UnavailableReason.METRIC_NOT_APPLICABLE],
            ["at least one non-zero admitted group mean"],
            warnings=["The Jain index is undefined when every admitted group mean is zero."],
            metadata=metadata,
        )
    return available_metric(
        key,
        sum(values) ** 2 / denominator,
        context,
        config,
        computed_at,
        warnings=[
            "A high Jain index can coexist with uniformly poor outcomes and does not establish "
            "protected-attribute fairness."
        ],
        metadata=metadata,
    )


def _unavailable_family(
    keys: tuple[str, ...],
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
    reasons: list[UnavailableReason],
    missing: list[str],
    metadata: JsonObject,
    *,
    warnings: list[str] | None = None,
) -> list[MetricValue]:
    return [
        unavailable_metric(
            key,
            context,
            config,
            computed_at,
            reasons,
            missing,
            warnings=warnings,
            metadata=metadata,
        )
        for key in keys
    ]

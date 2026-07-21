"""Baseline-versus-variation metric comparison."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.scenario import ScenarioSeed
from traffictwin.metrics.availability import unavailable_metric
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import (
    JsonScalar,
    MetricCollection,
    MetricStatus,
    MetricValue,
    RunMetricContext,
    UnavailableReason,
)

COMPARISON_DEFINITION_KEYS = [
    "comparison.absolute_delta",
    "comparison.relative_delta",
    "comparison.seed_aligned_difference",
]


class ComparisonStatus(StrEnum):
    """Comparison status."""

    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    INCOMPATIBLE = "incompatible"


class ComparisonDirection(StrEnum):
    """Neutral comparison direction."""

    INCREASED = "increased"
    DECREASED = "decreased"
    UNCHANGED = "unchanged"
    UNAVAILABLE = "unavailable"


class ComparisonRequest(BaseModel):
    """Request for a pairwise comparison."""

    model_config = ConfigDict(extra="forbid")

    baseline_run_id: str
    variation_run_id: str
    requested_metric_keys: list[str] | None = None
    require_same_experiment: bool = True
    require_same_random_seed: bool = True


class MetricComparison(BaseModel):
    """Comparison for one metric key."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    baseline: JsonScalar
    variation: JsonScalar
    unit: str | None = None
    absolute_delta: float | None = None
    relative_delta: float | None = None
    direction: ComparisonDirection
    status: ComparisonStatus
    reason_codes: list[UnavailableReason] = Field(default_factory=list)
    compatibility_findings: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)


class ComparisonReport(BaseModel):
    """Baseline-versus-variation comparison report."""

    model_config = ConfigDict(extra="forbid")

    baseline_context: dict[str, JsonScalar]
    variation_context: dict[str, JsonScalar]
    changed_seed_parameters: list[dict[str, JsonScalar]] = Field(default_factory=list)
    comparable_metrics: list[MetricComparison] = Field(default_factory=list)
    unavailable_comparisons: list[MetricComparison] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime
    comparison_version: str = "1.0"

    def to_json(self) -> str:
        """Return JSON output."""

        return self.model_dump_json(indent=2)


def comparison_placeholder_metrics(
    context: RunMetricContext,
    config: MetricEngineConfig,
    computed_at: datetime,
) -> list[MetricValue]:
    """Return single-run placeholders for comparison-only metric definitions."""

    return [
        unavailable_metric(
            key,
            context,
            config,
            computed_at,
            [UnavailableReason.METRIC_NOT_APPLICABLE],
            ["baseline_metric_collection", "variation_metric_collection"],
        )
        for key in COMPARISON_DEFINITION_KEYS
    ]


def compare_metric_collections(
    baseline: MetricCollection,
    variation: MetricCollection,
    request: ComparisonRequest | None = None,
    *,
    baseline_seed: ScenarioSeed | None = None,
    variation_seed: ScenarioSeed | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ComparisonReport:
    """Compare two metric collections with explicit compatibility checks."""

    requested = request or ComparisonRequest(
        baseline_run_id=baseline.run_id,
        variation_run_id=variation.run_id,
    )
    generated_at = clock() if clock is not None else datetime.now(UTC)
    baseline_by_key = baseline.by_key()
    variation_by_key = variation.by_key()
    keys = requested.requested_metric_keys or sorted(
        key
        for key in baseline_by_key
        if key in variation_by_key and not key.startswith("comparison.")
    )
    warnings = _collection_compatibility_warnings(baseline, variation, requested)

    comparable: list[MetricComparison] = []
    unavailable: list[MetricComparison] = []
    for key in keys:
        comparison = _compare_metric(
            key,
            baseline_by_key.get(key),
            variation_by_key.get(key),
            baseline,
            variation,
            warnings,
        )
        if comparison.status in {ComparisonStatus.AVAILABLE, ComparisonStatus.PARTIAL}:
            comparable.append(comparison)
        else:
            unavailable.append(comparison)

    return ComparisonReport(
        baseline_context=_collection_context(baseline),
        variation_context=_collection_context(variation),
        changed_seed_parameters=diff_seed_parameters(baseline_seed, variation_seed),
        comparable_metrics=sorted(comparable, key=lambda item: item.metric_key),
        unavailable_comparisons=sorted(unavailable, key=lambda item: item.metric_key),
        warnings=warnings,
        generated_at=generated_at,
    )


def diff_seed_parameters(
    baseline_seed: ScenarioSeed | None,
    variation_seed: ScenarioSeed | None,
) -> list[dict[str, JsonScalar]]:
    """Return deterministic seed parameter differences, excluding provenance."""

    if baseline_seed is None or variation_seed is None:
        return []
    excluded = {
        "schema_version",
        "seed_id",
        "name",
        "description",
        "parent_seed_id",
        "compare_against",
        "provenance",
    }
    baseline_data = baseline_seed.model_dump(mode="json", exclude=excluded)
    variation_data = variation_seed.model_dump(mode="json", exclude=excluded)
    changes: list[dict[str, JsonScalar]] = []
    _diff_mapping("", baseline_data, variation_data, changes)
    return changes


def _diff_mapping(
    prefix: str,
    baseline: object,
    variation: object,
    changes: list[dict[str, JsonScalar]],
) -> None:
    if isinstance(baseline, dict) and isinstance(variation, dict):
        for key in sorted(set(baseline) | set(variation)):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _diff_mapping(child_prefix, baseline.get(key), variation.get(key), changes)
        return
    if baseline != variation:
        changes.append(
            {
                "path": prefix,
                "baseline": _as_scalar(baseline),
                "variation": _as_scalar(variation),
            }
        )


def _compare_metric(
    key: str,
    baseline: MetricValue | None,
    variation: MetricValue | None,
    baseline_collection: MetricCollection,
    variation_collection: MetricCollection,
    collection_warnings: list[str],
) -> MetricComparison:
    if baseline is None or variation is None:
        return _unavailable_comparison(
            key,
            baseline,
            variation,
            [UnavailableReason.METRIC_NOT_APPLICABLE],
            ["metric is missing from one collection"],
        )
    compatibility = list(collection_warnings)
    reasons: list[UnavailableReason] = []
    if "experiment identifiers differ" in collection_warnings:
        reasons.append(UnavailableReason.EXPERIMENT_MISMATCH)
    if "random seeds differ" in collection_warnings:
        reasons.append(UnavailableReason.RANDOM_SEED_MISMATCH)
    if baseline_collection.metric_version != variation_collection.metric_version:
        reasons.append(UnavailableReason.METRIC_VERSION_MISMATCH)
        compatibility.append("metric collection versions differ")
    if baseline.unit != variation.unit:
        reasons.append(UnavailableReason.UNIT_MISMATCH)
        compatibility.append("metric units differ")
    if _is_energy_metric_key(key):
        baseline_contract = baseline.metadata.get("energy_contract_fingerprint")
        variation_contract = variation.metadata.get("energy_contract_fingerprint")
        if (
            not isinstance(baseline_contract, str)
            or not isinstance(variation_contract, str)
            or baseline_contract != variation_contract
        ):
            reasons.append(UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE)
            compatibility.append("task-energy evidence contracts are absent or incompatible")
    if _is_fairness_metric_key(key):
        baseline_policy = baseline.metadata.get("fairness_policy_fingerprint")
        variation_policy = variation.metadata.get("fairness_policy_fingerprint")
        baseline_groups = baseline.metadata.get("group_set_fingerprint")
        variation_groups = variation.metadata.get("group_set_fingerprint")
        if (
            not isinstance(baseline_policy, str)
            or not isinstance(variation_policy, str)
            or baseline_policy != variation_policy
            or not isinstance(baseline_groups, str)
            or not isinstance(variation_groups, str)
            or baseline_groups != variation_groups
        ):
            reasons.append(UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE)
            compatibility.append(
                "operational fairness policies or admitted group sets are absent or incompatible"
            )
    if key.startswith("plugin."):
        baseline_contract = baseline.metadata.get("plugin_contract_fingerprint")
        variation_contract = variation.metadata.get("plugin_contract_fingerprint")
        if (
            not isinstance(baseline_contract, str)
            or not isinstance(variation_contract, str)
            or baseline_contract != variation_contract
        ):
            reasons.append(UnavailableReason.COMPARISON_PAIR_INCOMPATIBLE)
            compatibility.append("custom metric plugin contracts are absent or incompatible")
    if (
        baseline.status is not MetricStatus.AVAILABLE
        or variation.status is not MetricStatus.AVAILABLE
    ):
        reasons.append(UnavailableReason.METRIC_NOT_APPLICABLE)
        compatibility.append("baseline or variation metric is unavailable")
    if not _is_numeric(baseline.value) or not _is_numeric(variation.value):
        reasons.append(UnavailableReason.METRIC_NOT_APPLICABLE)
        compatibility.append("metric value is not a comparable scalar")
    if reasons:
        return _unavailable_comparison(key, baseline, variation, reasons, compatibility)

    baseline_value = cast(float | int, baseline.value)
    variation_value = cast(float | int, variation.value)
    absolute_delta = float(variation_value) - float(baseline_value)
    relative_delta: float | None
    status = ComparisonStatus.AVAILABLE
    if baseline_value == 0:
        if variation_value == 0:
            relative_delta = 0.0
        else:
            relative_delta = None
            status = ComparisonStatus.PARTIAL
            reasons.append(UnavailableReason.BASELINE_ZERO)
            compatibility.append("relative delta unavailable because baseline is zero")
    else:
        relative_delta = absolute_delta / abs(float(baseline_value))

    return MetricComparison(
        metric_key=key,
        baseline=baseline_value,
        variation=variation_value,
        unit=baseline.unit,
        absolute_delta=absolute_delta,
        relative_delta=relative_delta,
        direction=_direction(absolute_delta),
        status=status,
        reason_codes=reasons,
        compatibility_findings=compatibility,
        provenance={
            "baseline_run_id": baseline.run_id,
            "variation_run_id": variation.run_id,
            "baseline_seed_id": baseline.seed_id,
            "variation_seed_id": variation.seed_id,
            "baseline_checkpoint": baseline.checkpoint,
            "variation_checkpoint": variation.checkpoint,
            "baseline_random_seed": baseline.random_seed,
            "variation_random_seed": variation.random_seed,
            "energy_contract_fingerprint": _metadata_scalar(baseline, "energy_contract_fingerprint")
            if _is_energy_metric_key(key)
            else None,
            "fairness_policy_fingerprint": _metadata_scalar(baseline, "fairness_policy_fingerprint")
            if _is_fairness_metric_key(key)
            else None,
            "group_set_fingerprint": _metadata_scalar(baseline, "group_set_fingerprint")
            if _is_fairness_metric_key(key)
            else None,
            "plugin_contract_fingerprint": _metadata_scalar(baseline, "plugin_contract_fingerprint")
            if key.startswith("plugin.")
            else None,
        },
    )


def _unavailable_comparison(
    key: str,
    baseline: MetricValue | None,
    variation: MetricValue | None,
    reasons: list[UnavailableReason],
    findings: list[str],
) -> MetricComparison:
    return MetricComparison(
        metric_key=key,
        baseline=_as_scalar(baseline.value if baseline is not None else None),
        variation=_as_scalar(variation.value if variation is not None else None),
        unit=baseline.unit
        if baseline is not None
        else variation.unit
        if variation is not None
        else None,
        direction=ComparisonDirection.UNAVAILABLE,
        status=ComparisonStatus.UNAVAILABLE,
        reason_codes=sorted(set(reasons), key=lambda item: item.value),
        compatibility_findings=sorted(set(findings)),
    )


def _collection_compatibility_warnings(
    baseline: MetricCollection,
    variation: MetricCollection,
    request: ComparisonRequest,
) -> list[str]:
    warnings: list[str] = []
    base_context = _collection_context(baseline)
    var_context = _collection_context(variation)
    if (
        request.require_same_experiment
        and base_context["experiment_id"] != var_context["experiment_id"]
    ):
        warnings.append("experiment identifiers differ")
    if (
        request.require_same_random_seed
        and base_context["random_seed"] != var_context["random_seed"]
    ):
        warnings.append("random seeds differ")
    if base_context["synthetic"] != var_context["synthetic"]:
        warnings.append("synthetic flags differ")
    return warnings


def _collection_context(collection: MetricCollection) -> dict[str, JsonScalar]:
    first = collection.results[0] if collection.results else None
    return {
        "run_id": collection.run_id,
        "metric_version": collection.metric_version,
        "experiment_id": first.experiment_id if first else None,
        "seed_id": first.seed_id if first else None,
        "algorithm": first.algorithm if first else None,
        "checkpoint": first.checkpoint if first else None,
        "random_seed": first.random_seed if first else None,
        "synthetic": first.synthetic if first else None,
        "input_fingerprint": collection.input_fingerprint,
    }


def _direction(delta: float) -> ComparisonDirection:
    if delta > 0:
        return ComparisonDirection.INCREASED
    if delta < 0:
        return ComparisonDirection.DECREASED
    return ComparisonDirection.UNCHANGED


def _is_numeric(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_energy_metric_key(metric_key: str) -> bool:
    return metric_key.startswith(("task.energy.", "task.energy_delay_product."))


def _is_fairness_metric_key(metric_key: str) -> bool:
    return metric_key.startswith("fairness.") or metric_key in {
        "task.completion.rate_by_vehicle_tier",
        "infra.load_balance.jain_capacity_normalised",
    }


def _metadata_scalar(metric: MetricValue, key: str) -> JsonScalar:
    value = metric.metadata.get(key)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _as_scalar(value: object) -> JsonScalar:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)

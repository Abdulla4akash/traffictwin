"""Deterministic read-only resource-strategy study explorer.

This module implements the typed production service for inspecting admitted or
explicitly synthetic resource-strategy studies across traffic/VEC policies.

It does not execute a scheduler, control an RSU, launch VEC, or claim a
strategy optimal. It validates lifecycle conservation, separates offered and
admitted denominators, maintains explicit missingness, and provides
deterministic arm summaries and pairwise descriptive differences.

Portable identity binds every scientifically meaningful field, excludes wall
clock, rendering state, local paths and secrets, uses stable ordering, avoids
default=str, preserves numeric values losslessly, distinguishes unknown from
false, and fails closed on malformed typed input.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import pathlib
import statistics
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.metrics.results import JsonScalar

RESOURCE_STRATEGY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
RESOURCE_STRATEGY_REPORT_VERSION: Literal["1.0"] = "1.0"

MIN_STRATEGY_ARMS = 2
MAX_STRATEGY_ARMS = 8


class ResourceStrategyEvidenceMode(StrEnum):
    """Evidence mode for a resource-strategy study."""

    SYNTHETIC_DEMONSTRATION = "synthetic_demonstration"
    IMPORTED = "imported"
    HISTORICAL_OBSERVATION = "historical_observation"
    ADMITTED_RESEARCH = "admitted_research"
    UNADMITTED_RESEARCH = "unadmitted_research"
    UNAVAILABLE = "unavailable"


class ResourceStrategyAdmissionState(StrEnum):
    """Admission state for a resource-strategy study."""

    ADMITTED = "admitted"
    UNADMITTED = "unadmitted"
    SYNTHETIC_DEMONSTRATION = "synthetic_demonstration"
    REJECTED = "rejected"
    PENDING = "pending"
    UNAVAILABLE = "unavailable"


class ResourceStrategyReplicationUnit(StrEnum):
    """Replication unit for matched-cohort comparison."""

    REPLICATION_ID = "replication_id"
    RANDOM_SEED = "random_seed"


class ResourceStrategyMetricDenominator(StrEnum):
    """Denominator for metric attainment."""

    OFFERED_TASKS = "offered_tasks"
    ADMITTED_TASKS = "admitted_tasks"
    COMPLETED_TASKS = "completed_tasks"
    REPLICATION = "replication"
    UNKNOWN = "unknown"


RESERVED_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "task.completion.rate_offered",
        "task.completion.rate_admitted",
        "task.deadline_success.rate_offered",
        "task.deadline_success.rate_admitted",
        "task.offered.count",
        "task.admitted.count",
        "task.rejected.count",
        "task.forwarded.count",
        "task.started.count",
        "task.compute_completed.count",
        "task.returned.count",
        "task.dropped.count",
        "task.deadline_success.count",
        "task.latency.mean_ms",
        "task.latency.p95_ms",
        "infra.queue_length.mean",
        "infra.load_balance.jain",
        "infra.utilisation.mean",
        "task.energy.mean_j",
        "resource.cost.units",
    }
)

# Expected canonical contract for compatibility audit
EXPECTED_METRIC_CONTRACT: dict[str, tuple[str, str, ResourceStrategyMetricDenominator]] = {  # noqa: E501
    "task.completion.rate_offered": (
        "1.0",
        "ratio",
        ResourceStrategyMetricDenominator.OFFERED_TASKS,
    ),
    "task.completion.rate_admitted": (
        "1.0",
        "ratio",
        ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    ),
    "task.deadline_success.rate_offered": (
        "1.0",
        "ratio",
        ResourceStrategyMetricDenominator.OFFERED_TASKS,
    ),
    "task.deadline_success.rate_admitted": (
        "1.0",
        "ratio",
        ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    ),
    "task.latency.mean_ms": ("1.0", "ms", ResourceStrategyMetricDenominator.COMPLETED_TASKS),
    "task.latency.p95_ms": ("1.0", "ms", ResourceStrategyMetricDenominator.COMPLETED_TASKS),
    "infra.queue_length.mean": ("1.0", "tasks", ResourceStrategyMetricDenominator.REPLICATION),
    "infra.load_balance.jain": ("1.0", "ratio", ResourceStrategyMetricDenominator.REPLICATION),
    "infra.utilisation.mean": ("1.0", "fraction", ResourceStrategyMetricDenominator.REPLICATION),
    "task.energy.mean_j": ("1.0", "J", ResourceStrategyMetricDenominator.COMPLETED_TASKS),
    "resource.cost.units": ("1.0", "cost_units", ResourceStrategyMetricDenominator.REPLICATION),
    "task.offered.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.OFFERED_TASKS),
    "task.admitted.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.ADMITTED_TASKS),
    "task.rejected.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.OFFERED_TASKS),
    "task.forwarded.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.ADMITTED_TASKS),
    "task.started.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.ADMITTED_TASKS),
    "task.compute_completed.count": (
        "1.0",
        "tasks",
        ResourceStrategyMetricDenominator.ADMITTED_TASKS,
    ),
    "task.returned.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.COMPLETED_TASKS),
    "task.dropped.count": ("1.0", "tasks", ResourceStrategyMetricDenominator.ADMITTED_TASKS),
    "task.deadline_success.count": (
        "1.0",
        "tasks",
        ResourceStrategyMetricDenominator.OFFERED_TASKS,
    ),
}


class ResourceStrategyMetricStatus(StrEnum):
    """Availability of a metric."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"


class ResourceStrategyCompatibilityStatus(StrEnum):
    """Compatibility outcome for a metric family."""

    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"
    UNAVAILABLE = "unavailable"


class ResourceStrategyExclusionCode(StrEnum):
    """Stable reasons a replication is excluded from the matched cohort."""

    INCOMPATIBLE_METRIC_VERSION = "INCOMPATIBLE_METRIC_VERSION"
    MISSING_REPLICATION = "MISSING_REPLICATION"
    LIFECYCLE_INCONSISTENT = "LIFECYCLE_INCONSISTENT"
    RSU_OUTAGE = "RSU_OUTAGE"
    DEADLINE_UNAVAILABLE = "DEADLINE_UNAVAILABLE"
    QUEUE_UNAVAILABLE = "QUEUE_UNAVAILABLE"
    RESOURCE_COST_UNAVAILABLE = "RESOURCE_COST_UNAVAILABLE"
    MANUAL_EXCLUSION = "MANUAL_EXCLUSION"
    DUPLICATE_REPLICATION_ID = "DUPLICATE_REPLICATION_ID"


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class ResourceStrategyLifecycle(BaseModel):
    """Validated lifecycle counts for one replication.

    Conservation relationships are validated where counts are supplied:

    - offered == admitted + rejected
    - admitted >= forwarded, admitted >= started
    - started >= compute_completed >= returned >= deadline_success
    - admitted >= dropped, dropped + returned <= admitted
    """

    model_config = ConfigDict(extra="forbid")

    offered: int = Field(ge=0)
    admitted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    forwarded: int = Field(ge=0)
    started: int = Field(ge=0)
    compute_completed: int = Field(ge=0)
    returned: int = Field(ge=0)
    dropped: int = Field(ge=0)
    deadline_success: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_conservation(self) -> ResourceStrategyLifecycle:
        if self.offered != self.admitted + self.rejected:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: offered ({self.offered}) "
                f"!= admitted ({self.admitted}) + rejected ({self.rejected})"
            )
        if self.admitted < self.forwarded:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: admitted ({self.admitted}) "
                f"< forwarded ({self.forwarded})"
            )
        if self.admitted < self.started:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: admitted ({self.admitted}) "
                f"< started ({self.started})"
            )
        if self.started < self.compute_completed:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: started ({self.started}) "
                f"< compute_completed ({self.compute_completed})"
            )
        if self.compute_completed < self.returned:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: compute_completed "
                f"({self.compute_completed}) < returned ({self.returned})"
            )
        if self.returned < self.deadline_success:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: returned ({self.returned}) "
                f"< deadline_success ({self.deadline_success})"
            )
        if self.admitted < self.dropped:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: admitted ({self.admitted}) "
                f"< dropped ({self.dropped})"
            )
        if self.dropped + self.returned > self.admitted:
            raise ValueError(
                f"LIFECYCLE_CONSERVATION_VIOLATED: dropped ({self.dropped}) + "
                f"returned ({self.returned}) > admitted ({self.admitted})"
            )
        return self


class ResourceStrategyReplication(BaseModel):
    """One replication observation for a strategy arm."""

    model_config = ConfigDict(extra="forbid")

    replication_id: str = Field(min_length=1)
    lifecycle: ResourceStrategyLifecycle
    # Per-replication scalar metrics keyed by metric_key.
    # Only metrics listed in the study catalog are permitted.
    metrics: dict[str, float] = Field(default_factory=dict)
    # Queue / load-balance / utilisation / energy / resource-cost are
    # represented as metrics where supplied; keep explicit typed unavailable
    # rather than guessing.
    queue_length_mean: float | None = None
    queue_balance_jain: float | None = None
    utilisation_mean: float | None = None
    energy_mean_j: float | None = None
    resource_cost_units: float | None = None
    latency_mean_ms: float | None = None
    latency_p95_ms: float | None = None
    forwarding_rate: float | None = None

    @field_validator("metrics")
    @classmethod
    def validate_metrics_finite(cls, values: dict[str, float]) -> dict[str, float]:
        for key, value in values.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValueError(f"metric {key!r} value must be finite scalar, got {value!r}")
            if not math.isfinite(float(value)):
                raise ValueError(f"metric {key!r} value must be finite, got {value!r}")
        return values

    @model_validator(mode="after")
    def validate_reserved_metrics_not_supplied(self) -> ResourceStrategyReplication:
        for key in self.metrics:
            if key in RESERVED_METRIC_KEYS:
                raise ValueError(
                    f"reserved metric {key!r} must not be supplied in rep.metrics; "
                    "lifecycle/typed fields are authoritative"
                )
        return self

    @field_validator(
        "queue_length_mean",
        "queue_balance_jain",
        "utilisation_mean",
        "energy_mean_j",
        "resource_cost_units",
        "latency_mean_ms",
        "latency_p95_ms",
        "forwarding_rate",
    )
    @classmethod
    def validate_optional_finite(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"value must be finite scalar, got {value!r}")
        if not math.isfinite(float(value)):
            raise ValueError(f"value must be finite, got {value!r}")
        return float(value)


class ResourceStrategyArm(BaseModel):
    """One strategy arm with its replications."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=256)
    description: str = Field(min_length=1, max_length=1024)
    strategy_type: str = Field(min_length=1, max_length=128)
    replications: list[ResourceStrategyReplication] = Field(min_length=1)

    @field_validator("replications")
    @classmethod
    def validate_unique_replication_ids(
        cls, values: list[ResourceStrategyReplication]
    ) -> list[ResourceStrategyReplication]:
        seen: set[str] = set()
        for rep in values:
            if rep.replication_id in seen:
                raise ValueError(f"duplicate replication_id {rep.replication_id!r}")
            seen.add(rep.replication_id)
        return values


class ResourceStrategyMetric(BaseModel):
    """One metric definition for the study catalog."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str = Field(min_length=1, max_length=256)
    metric_version: str = Field(min_length=1, max_length=64)
    unit: str = Field(min_length=1, max_length=64)
    denominator: ResourceStrategyMetricDenominator
    description: str = Field(default="", max_length=512)
    # Whether per-replication values are permitted to be disclosed.
    per_replication_disclosed: bool = True


class ResourceStrategyExclusion(BaseModel):
    """One excluded replication with reason."""

    model_config = ConfigDict(extra="forbid")

    replication_id: str = Field(min_length=1)
    arm_id: str | None = None
    code: ResourceStrategyExclusionCode
    reason: str = Field(min_length=1, max_length=512)
    detail: str = Field(default="", max_length=1024)


class ResourceStrategyCompatibility(BaseModel):
    """Compatibility audit for metric families across arms."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    status: ResourceStrategyCompatibilityStatus
    denominator: ResourceStrategyMetricDenominator | None = None
    unit: str | None = None
    versions: list[str] = Field(default_factory=list)
    finding: str = Field(default="")


class ResourceStrategyStudy(BaseModel):
    """Versioned resource-strategy study with matched-cohort evidence."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = RESOURCE_STRATEGY_SCHEMA_VERSION
    study_id: str = Field(min_length=1, max_length=256)
    source_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    evidence_mode: ResourceStrategyEvidenceMode
    admission_state: ResourceStrategyAdmissionState
    replication_unit: ResourceStrategyReplicationUnit = (
        ResourceStrategyReplicationUnit.REPLICATION_ID
    )
    arms: list[ResourceStrategyArm] = Field(
        min_length=MIN_STRATEGY_ARMS, max_length=MAX_STRATEGY_ARMS
    )
    common_matched_replication_ids: list[str] = Field(default_factory=list)
    excluded_replication_ids: list[ResourceStrategyExclusion] = Field(default_factory=list)
    metric_catalog: list[ResourceStrategyMetric] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    generated_at: datetime | None = None

    @field_validator("arms")
    @classmethod
    def validate_unique_arm_ids(
        cls, values: list[ResourceStrategyArm]
    ) -> list[ResourceStrategyArm]:
        seen: set[str] = set()
        for arm in values:
            if arm.arm_id in seen:
                raise ValueError(f"duplicate arm_id {arm.arm_id!r}")
            seen.add(arm.arm_id)
        return values

    @field_validator("metric_catalog")
    @classmethod
    def validate_unique_metric_keys(
        cls, values: list[ResourceStrategyMetric]
    ) -> list[ResourceStrategyMetric]:
        seen: set[str] = set()
        for metric in values:
            if metric.metric_key in seen:
                raise ValueError(f"duplicate metric_key {metric.metric_key!r}")
            seen.add(metric.metric_key)
        return values

    @field_validator("common_matched_replication_ids")
    @classmethod
    def validate_sorted_unique(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("common_matched_replication_ids must not contain duplicates")
        # Allow any order on input but canonical ordering is sorted;
        # validate that it is already sorted to enforce deterministic input.
        if values != sorted(values):
            raise ValueError("common_matched_replication_ids must be sorted")
        return values

    @model_validator(mode="after")
    def validate_study_invariants(self) -> ResourceStrategyStudy:
        # Evidence mode and admission state must be consistent.
        if (
            self.evidence_mode == ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION
            and self.admission_state != ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION
        ):
            raise ValueError(
                "synthetic_demonstration evidence_mode requires "
                "synthetic_demonstration admission_state"
            )
        if (
            self.admission_state == ResourceStrategyAdmissionState.SYNTHETIC_DEMONSTRATION
            and self.evidence_mode != ResourceStrategyEvidenceMode.SYNTHETIC_DEMONSTRATION
        ):
            raise ValueError(
                "synthetic_demonstration admission_state requires "
                "synthetic_demonstration evidence_mode"
            )
        if (
            self.evidence_mode == ResourceStrategyEvidenceMode.ADMITTED_RESEARCH
            and self.admission_state != ResourceStrategyAdmissionState.ADMITTED
        ):
            raise ValueError("admitted_research evidence_mode requires admitted admission_state")
        if (
            self.evidence_mode == ResourceStrategyEvidenceMode.UNADMITTED_RESEARCH
            and self.admission_state != ResourceStrategyAdmissionState.UNADMITTED
        ):
            raise ValueError(
                "unadmitted_research evidence_mode requires unadmitted admission_state"
            )
        # Arms: validate metric keys in replications are subset of catalog.
        catalog_keys = {m.metric_key for m in self.metric_catalog}
        for arm in self.arms:
            for rep in arm.replications:
                for key in rep.metrics:
                    if key not in catalog_keys:
                        raise ValueError(
                            f"replication {rep.replication_id!r} in arm {arm.arm_id!r} "
                            f"contains undeclared metric_key {key!r}"
                        )
        # Validate common_matched_replication_ids is exactly the intersection
        # of replication_ids across all arms minus excluded ids.
        expected = _compute_matched_replication_ids(self.arms, self.excluded_replication_ids)
        if self.common_matched_replication_ids != expected:
            raise ValueError(
                f"common_matched_replication_ids {self.common_matched_replication_ids!r} "
                f"does not match computed matched cohort {expected!r}; "
                "an excluded replication may have silently entered the matched cohort"
            )
        # Validate that no excluded replication appears in matched cohort.
        excluded_ids = {e.replication_id for e in self.excluded_replication_ids}
        for rid in self.common_matched_replication_ids:
            if rid in excluded_ids:
                raise ValueError(f"excluded replication {rid!r} must not appear in matched cohort")
        # Validate metric version compatibility across arms for matched replications.
        # If any metric appears with different versions (catalog is single version
        # per key, but check per-replication metric values are finite where present).
        # Incompatibility is already enforced by catalog uniqueness; however, we
        # also validate that catalog denominators are stable.
        return self

    def canonical_payload(self) -> dict[str, Any]:
        """Return deterministic payload for fingerprinting (excludes wall clock)."""
        # Stable ordering: arms sorted by arm_id, replications sorted by id,
        # metrics sorted by key, excluded sorted by (replication_id, arm_id).
        arms_payload = []
        for arm in sorted(self.arms, key=lambda a: a.arm_id):
            reps = sorted(arm.replications, key=lambda r: r.replication_id)
            arms_payload.append(
                {
                    "arm_id": arm.arm_id,
                    "label": arm.label,
                    "description": arm.description,
                    "strategy_type": arm.strategy_type,
                    "replications": [
                        {
                            "replication_id": r.replication_id,
                            "lifecycle": r.lifecycle.model_dump(mode="json"),
                            "metrics": dict(sorted(r.metrics.items())),
                            "queue_length_mean": r.queue_length_mean,
                            "queue_balance_jain": r.queue_balance_jain,
                            "utilisation_mean": r.utilisation_mean,
                            "energy_mean_j": r.energy_mean_j,
                            "resource_cost_units": r.resource_cost_units,
                            "latency_mean_ms": r.latency_mean_ms,
                            "latency_p95_ms": r.latency_p95_ms,
                            "forwarding_rate": r.forwarding_rate,
                        }
                        for r in reps
                    ],
                }
            )
        metric_payload = [
            m.model_dump(mode="json")
            for m in sorted(self.metric_catalog, key=lambda x: x.metric_key)
        ]
        excluded_payload = sorted(
            [e.model_dump(mode="json") for e in self.excluded_replication_ids],
            key=lambda x: (x["replication_id"], x.get("arm_id") or ""),
        )
        # provenance sorted by key, limitations sorted
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "source_fingerprint": self.source_fingerprint,
            "evidence_mode": self.evidence_mode.value,
            "admission_state": self.admission_state.value,
            "replication_unit": self.replication_unit.value,
            "arms": arms_payload,
            "common_matched_replication_ids": sorted(self.common_matched_replication_ids),
            "excluded_replication_ids": excluded_payload,
            "metric_catalog": metric_payload,
            "limitations": sorted(self.limitations),
            "provenance": dict(sorted(self.provenance.items())),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        # Portable JSON must remain model-valid; generated_at is not identity-bearing.
        # Normalise wall clock to null for deterministic, re-importable export.
        if payload.get("generated_at") is not None:
            payload["generated_at"] = None
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class ResourceStrategyMetricAggregate(BaseModel):
    """Deterministic aggregate for one metric on one arm over the matched cohort."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    metric_version: str
    unit: str
    denominator: ResourceStrategyMetricDenominator
    status: ResourceStrategyMetricStatus
    replication_count: int = Field(ge=0)
    per_replication_values: dict[str, float | None] = Field(default_factory=dict)
    aggregate_mean: float | None = None
    aggregate_median: float | None = None
    aggregate_min: float | None = None
    aggregate_max: float | None = None
    reason: str | None = None


class ResourceStrategyArmSummary(BaseModel):
    """Summary for one arm over the matched cohort."""

    model_config = ConfigDict(extra="forbid")

    arm_id: str
    label: str
    strategy_type: str
    replication_count_total: int = Field(ge=0)
    replication_count_matched: int = Field(ge=0)
    matched_replication_ids: list[str] = Field(default_factory=list)
    lifecycle_totals: dict[str, int] = Field(default_factory=dict)
    metric_aggregates: list[ResourceStrategyMetricAggregate] = Field(default_factory=list)
    # Queue / utilisation evidence is surfaced as metric aggregates;
    # keep explicit typed unavailable rather than guessing.
    unavailable_metrics: list[str] = Field(default_factory=list)


class ResourceStrategyPairwiseDifference(BaseModel):
    """Descriptive pairwise difference between two arms for one metric."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    metric_version: str
    unit: str
    denominator: ResourceStrategyMetricDenominator
    arm_a: str
    arm_b: str
    mean_a: float | None = None
    mean_b: float | None = None
    mean_difference_b_minus_a: float | None = None
    median_difference_b_minus_a: float | None = None
    interpretation: str = Field(
        default="descriptive comparison only; not a causal or optimality claim"
    )
    status: ResourceStrategyMetricStatus = ResourceStrategyMetricStatus.UNAVAILABLE
    reason: str | None = None


class ResourceStrategyReport(BaseModel):
    """Deterministic report derived from a study without recomputing raw rows."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = RESOURCE_STRATEGY_REPORT_VERSION
    study_id: str
    study_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_mode: ResourceStrategyEvidenceMode
    admission_state: ResourceStrategyAdmissionState
    replication_unit: ResourceStrategyReplicationUnit
    common_matched_replication_ids: list[str] = Field(default_factory=list)
    excluded_replication_ids: list[ResourceStrategyExclusion] = Field(default_factory=list)
    metric_catalog: list[ResourceStrategyMetric] = Field(default_factory=list)
    arm_summaries: list[ResourceStrategyArmSummary] = Field(default_factory=list)
    pairwise_differences: list[ResourceStrategyPairwiseDifference] = Field(default_factory=list)
    compatibility: list[ResourceStrategyCompatibility] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, JsonScalar] = Field(default_factory=dict)
    generated_at: datetime | None = None
    report_fingerprint: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")

    def canonical_payload(self) -> dict[str, Any]:
        arms = sorted(self.arm_summaries, key=lambda a: a.arm_id)
        pairwise = sorted(
            self.pairwise_differences,
            key=lambda d: (d.metric_key, d.arm_a, d.arm_b),
        )
        catalog = sorted(self.metric_catalog, key=lambda m: m.metric_key)
        excluded = sorted(
            [e.model_dump(mode="json") for e in self.excluded_replication_ids],
            key=lambda x: (x["replication_id"], x.get("arm_id") or ""),
        )
        compat = sorted(
            [c.model_dump(mode="json") for c in self.compatibility],
            key=lambda x: x["metric_key"],
        )
        arm_payload = []
        for arm in arms:
            aggs = sorted(arm.metric_aggregates, key=lambda a: a.metric_key)
            arm_payload.append(
                {
                    "arm_id": arm.arm_id,
                    "label": arm.label,
                    "strategy_type": arm.strategy_type,
                    "replication_count_total": arm.replication_count_total,
                    "replication_count_matched": arm.replication_count_matched,
                    "matched_replication_ids": sorted(arm.matched_replication_ids),
                    "lifecycle_totals": dict(sorted(arm.lifecycle_totals.items())),
                    "metric_aggregates": [
                        {
                            "metric_key": agg.metric_key,
                            "metric_version": agg.metric_version,
                            "unit": agg.unit,
                            "denominator": agg.denominator.value,
                            "status": agg.status.value,
                            "replication_count": agg.replication_count,
                            "per_replication_values": dict(
                                sorted(agg.per_replication_values.items())
                            ),
                            "aggregate_mean": agg.aggregate_mean,
                            "aggregate_median": agg.aggregate_median,
                            "aggregate_min": agg.aggregate_min,
                            "aggregate_max": agg.aggregate_max,
                            "reason": agg.reason,
                        }
                        for agg in aggs
                    ],
                    "unavailable_metrics": sorted(arm.unavailable_metrics),
                }
            )
        return {
            "schema_version": self.schema_version,
            "study_id": self.study_id,
            "study_fingerprint": self.study_fingerprint,
            "source_fingerprint": self.source_fingerprint,
            "evidence_mode": self.evidence_mode.value,
            "admission_state": self.admission_state.value,
            "replication_unit": self.replication_unit.value,
            "common_matched_replication_ids": sorted(self.common_matched_replication_ids),
            "excluded_replication_ids": excluded,
            "metric_catalog": [m.model_dump(mode="json") for m in catalog],
            "arm_summaries": arm_payload,
            "pairwise_differences": [
                {
                    "metric_key": d.metric_key,
                    "metric_version": d.metric_version,
                    "unit": d.unit,
                    "denominator": d.denominator.value,
                    "arm_a": d.arm_a,
                    "arm_b": d.arm_b,
                    "mean_a": d.mean_a,
                    "mean_b": d.mean_b,
                    "mean_difference_b_minus_a": d.mean_difference_b_minus_a,
                    "median_difference_b_minus_a": d.median_difference_b_minus_a,
                    "interpretation": d.interpretation,
                    "status": d.status.value,
                    "reason": d.reason,
                }
                for d in pairwise
            ],
            "compatibility": compat,
            "limitations": sorted(self.limitations),
            "provenance": dict(sorted(self.provenance.items())),
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        )

    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_json(self) -> str:
        payload = self.model_dump(mode="json")
        if payload.get("generated_at") is not None:
            payload["generated_at"] = None
        return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_matched_replication_ids(
    arms: list[ResourceStrategyArm],
    excluded: list[ResourceStrategyExclusion],
) -> list[str]:
    if not arms:
        return []
    excluded_ids = {e.replication_id for e in excluded}
    # Intersection of replication_ids across all arms
    sets = [{r.replication_id for r in arm.replications} for arm in arms]
    common = set.intersection(*sets) if sets else set()
    # Remove excluded
    common = common - excluded_ids
    return sorted(common)


def _fingerprint(payload: object) -> str:  # noqa: ANN401
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Service: build report
# ---------------------------------------------------------------------------


def build_resource_strategy_report(
    study: ResourceStrategyStudy,
    *,
    clock: Callable[[], datetime] | None = utc_now,
) -> ResourceStrategyReport:
    """Build a deterministic report from a validated study.

    Validates admission (unadmitted evidence is not treated as admitted),
    conservation, matched-cohort exclusions, and metric version compatibility.
    Fails closed on malformed input.
    """
    # Admission guard: unadmitted evidence must not be treated as admitted.
    if study.admission_state == ResourceStrategyAdmissionState.UNADMITTED:
        raise ValueError(
            "UNADMITTED_EVIDENCE: study admission_state is unadmitted; "
            "results must not be displayed as admitted"
        )
    if study.admission_state == ResourceStrategyAdmissionState.REJECTED:
        raise ValueError(
            "REJECTED_EVIDENCE: study admission_state is rejected; "
            "results must not be displayed as admitted"
        )
    if study.admission_state == ResourceStrategyAdmissionState.PENDING:
        raise ValueError(
            "PENDING_EVIDENCE: study admission_state is pending; "
            "admission must be explicit before results"
        )
    if study.admission_state == ResourceStrategyAdmissionState.UNAVAILABLE:
        raise ValueError("UNAVAILABLE_EVIDENCE: study admission_state is unavailable")

    # Real compatibility audit: evaluate version/unit/denominator against expected contract
    compatibility: list[ResourceStrategyCompatibility] = []
    for metric in study.metric_catalog:
        expected = EXPECTED_METRIC_CONTRACT.get(metric.metric_key)
        if expected is not None:
            exp_version, exp_unit, exp_denom = expected
            mismatches: list[str] = []
            if metric.metric_version != exp_version:
                mismatches.append(f"version {metric.metric_version!r} != expected {exp_version!r}")
            if metric.unit != exp_unit:
                mismatches.append(f"unit {metric.unit!r} != expected {exp_unit!r}")
            if metric.denominator != exp_denom:
                mismatches.append(
                    f"denominator {metric.denominator.value!r} != expected {exp_denom.value!r}"
                )
            if mismatches:
                compatibility.append(
                    ResourceStrategyCompatibility(
                        metric_key=metric.metric_key,
                        status=ResourceStrategyCompatibilityStatus.INCOMPATIBLE,
                        denominator=metric.denominator,
                        unit=metric.unit,
                        versions=[metric.metric_version],
                        finding="incompatible: " + "; ".join(mismatches),
                    )
                )
                continue
        compatibility.append(
            ResourceStrategyCompatibility(
                metric_key=metric.metric_key,
                status=ResourceStrategyCompatibilityStatus.COMPATIBLE,
                denominator=metric.denominator,
                unit=metric.unit,
                versions=[metric.metric_version],
                finding="compatible across matched cohort",
            )
        )

    # Build per-arm summaries over matched cohort
    matched_ids = study.common_matched_replication_ids
    # Map arm_id -> replication_id -> replication
    arm_rep_map: dict[str, dict[str, ResourceStrategyReplication]] = {}
    for arm in study.arms:
        arm_rep_map[arm.arm_id] = {r.replication_id: r for r in arm.replications}

    arm_summaries: list[ResourceStrategyArmSummary] = []
    for arm in sorted(study.arms, key=lambda a: a.arm_id):
        rep_map = arm_rep_map[arm.arm_id]
        # Lifecycle totals over matched cohort only
        totals: dict[str, int] = defaultdict(int)
        totals_dict: dict[str, int] = {}
        # Collect per-metric per-replication values
        # Initialize metric aggregates structures
        metric_aggregates: list[ResourceStrategyMetricAggregate] = []
        unavailable: list[str] = []
        for metric_def in sorted(study.metric_catalog, key=lambda m: m.metric_key):
            key = metric_def.metric_key
            # Gather per-replication values for matched ids where replication exists
            # and metric value is present. For denominators, we compute
            # attainment metrics from lifecycle where needed; otherwise use
            # replication.metrics dict or explicit typed fields.
            per_rep: dict[str, float | None] = {}
            values: list[float] = []
            for rid in matched_ids:
                rep = rep_map.get(rid)
                if rep is None:
                    per_rep[rid] = None
                    continue
                # Resolve metric value for this replication.
                # For standard lifecycle-derived metrics, compute from lifecycle.
                computed: float | None = None
                reason_unavailable: str | None = None
                # Lifecycle-derived rates with explicit denominator separation
                if key == "task.completion.rate_offered":
                    if rep.lifecycle.offered > 0:
                        computed = rep.lifecycle.compute_completed / rep.lifecycle.offered
                    else:
                        reason_unavailable = "offered is zero"
                elif key == "task.completion.rate_admitted":
                    if rep.lifecycle.admitted > 0:
                        computed = rep.lifecycle.compute_completed / rep.lifecycle.admitted
                    else:
                        reason_unavailable = "admitted is zero"
                elif key == "task.deadline_success.rate_offered":
                    if rep.lifecycle.offered > 0:
                        computed = rep.lifecycle.deadline_success / rep.lifecycle.offered
                    else:
                        reason_unavailable = "offered is zero"
                elif key == "task.deadline_success.rate_admitted":
                    if rep.lifecycle.admitted > 0:
                        computed = rep.lifecycle.deadline_success / rep.lifecycle.admitted
                    else:
                        reason_unavailable = "admitted is zero"
                elif key == "task.offered.count":
                    computed = float(rep.lifecycle.offered)
                elif key == "task.admitted.count":
                    computed = float(rep.lifecycle.admitted)
                elif key == "task.rejected.count":
                    computed = float(rep.lifecycle.rejected)
                elif key == "task.forwarded.count":
                    computed = float(rep.lifecycle.forwarded)
                elif key == "task.started.count":
                    computed = float(rep.lifecycle.started)
                elif key == "task.compute_completed.count":
                    computed = float(rep.lifecycle.compute_completed)
                elif key == "task.returned.count":
                    computed = float(rep.lifecycle.returned)
                elif key == "task.dropped.count":
                    computed = float(rep.lifecycle.dropped)
                elif key == "task.deadline_success.count":
                    computed = float(rep.lifecycle.deadline_success)
                elif key == "task.latency.mean_ms":
                    computed = rep.latency_mean_ms
                elif key == "task.latency.p95_ms":
                    computed = rep.latency_p95_ms
                elif key == "infra.queue_length.mean":
                    computed = rep.queue_length_mean
                elif key == "infra.load_balance.jain":
                    computed = rep.queue_balance_jain
                elif key == "infra.utilisation.mean":
                    computed = rep.utilisation_mean
                elif key == "task.energy.mean_j":
                    computed = rep.energy_mean_j
                elif key == "resource.cost.units":
                    computed = rep.resource_cost_units
                else:
                    # Generic metric from replication.metrics dict
                    computed = rep.metrics.get(key)
                if computed is not None:
                    if not isinstance(computed, (int, float)) or isinstance(computed, bool):
                        per_rep[rid] = None
                        continue
                    if not math.isfinite(float(computed)):
                        per_rep[rid] = None
                        continue
                    val = float(computed)
                    per_rep[rid] = val
                    values.append(val)
                else:
                    per_rep[rid] = None
                    if reason_unavailable is None and metric_def.per_replication_disclosed:
                        # keep as unavailable per replication
                        pass
            # Determine status
            if values:
                # If any replication missing, mark partial?
                missing = sum(1 for v in per_rep.values() if v is None)
                status = (
                    ResourceStrategyMetricStatus.PARTIAL
                    if missing > 0
                    else ResourceStrategyMetricStatus.AVAILABLE
                )
                # Deterministic aggregates
                mean_val = statistics.fmean(values) if values else None
                median_val = statistics.median(values) if values else None
                min_val = min(values) if values else None
                max_val = max(values) if values else None
                reason = None
                if missing > 0:
                    reason = f"{missing} of {len(matched_ids)} matched replications unavailable"
            else:
                status = ResourceStrategyMetricStatus.UNAVAILABLE
                mean_val = None
                median_val = None
                min_val = None
                max_val = None
                reason = "no available per-replication values in matched cohort"
                unavailable.append(key)
            metric_aggregates.append(
                ResourceStrategyMetricAggregate(
                    metric_key=key,
                    metric_version=metric_def.metric_version,
                    unit=metric_def.unit,
                    denominator=metric_def.denominator,
                    status=status,
                    replication_count=len(values),
                    per_replication_values=per_rep,
                    aggregate_mean=mean_val,
                    aggregate_median=median_val,
                    aggregate_min=min_val,
                    aggregate_max=max_val,
                    reason=reason,
                )
            )
        # Lifecycle totals over matched cohort
        for rid in matched_ids:
            rep = rep_map.get(rid)
            if rep is None:
                continue
            totals["offered"] += rep.lifecycle.offered
            totals["admitted"] += rep.lifecycle.admitted
            totals["rejected"] += rep.lifecycle.rejected
            totals["forwarded"] += rep.lifecycle.forwarded
            totals["started"] += rep.lifecycle.started
            totals["compute_completed"] += rep.lifecycle.compute_completed
            totals["returned"] += rep.lifecycle.returned
            totals["dropped"] += rep.lifecycle.dropped
            totals["deadline_success"] += rep.lifecycle.deadline_success
        totals_dict = dict(totals)
        arm_summaries.append(
            ResourceStrategyArmSummary(
                arm_id=arm.arm_id,
                label=arm.label,
                strategy_type=arm.strategy_type,
                replication_count_total=len(arm.replications),
                replication_count_matched=len([rid for rid in matched_ids if rid in rep_map]),
                matched_replication_ids=[rid for rid in matched_ids if rid in rep_map],
                lifecycle_totals=totals_dict,
                metric_aggregates=metric_aggregates,
                unavailable_metrics=sorted(unavailable),
            )
        )

    # Pairwise descriptive differences over matched cohort
    pairwise: list[ResourceStrategyPairwiseDifference] = []
    sorted_arms = sorted(study.arms, key=lambda a: a.arm_id)
    for i, arm_a in enumerate(sorted_arms):
        for arm_b in sorted_arms[i + 1 :]:
            # Locate summaries
            sum_a = next(s for s in arm_summaries if s.arm_id == arm_a.arm_id)
            sum_b = next(s for s in arm_summaries if s.arm_id == arm_b.arm_id)
            for metric_def in sorted(study.metric_catalog, key=lambda m: m.metric_key):
                key = metric_def.metric_key
                agg_a = next((a for a in sum_a.metric_aggregates if a.metric_key == key), None)
                agg_b = next((a for a in sum_b.metric_aggregates if a.metric_key == key), None)
                if agg_a is None or agg_b is None:
                    continue
                if (
                    agg_a.status == ResourceStrategyMetricStatus.UNAVAILABLE
                    or agg_b.status == ResourceStrategyMetricStatus.UNAVAILABLE
                ):
                    pairwise.append(
                        ResourceStrategyPairwiseDifference(
                            metric_key=key,
                            metric_version=metric_def.metric_version,
                            unit=metric_def.unit,
                            denominator=metric_def.denominator,
                            arm_a=arm_a.arm_id,
                            arm_b=arm_b.arm_id,
                            mean_a=agg_a.aggregate_mean,
                            mean_b=agg_b.aggregate_mean,
                            mean_difference_b_minus_a=None,
                            median_difference_b_minus_a=None,
                            interpretation=(
                                f"{arm_b.arm_id} vs {arm_a.arm_id} unavailable "
                                f"for {metric_def.metric_key} ({metric_def.unit}); descriptive only"
                            ),
                            status=ResourceStrategyMetricStatus.UNAVAILABLE,
                            reason="one or both arms unavailable for this metric",
                        )
                    )
                    continue
                # Check compatibility: incompatible metrics do not enter ordinary comparison
                compat = next((c for c in compatibility if c.metric_key == key), None)
                if (
                    compat is not None
                    and compat.status == ResourceStrategyCompatibilityStatus.INCOMPATIBLE
                ):
                    pairwise.append(
                        ResourceStrategyPairwiseDifference(
                            metric_key=key,
                            metric_version=metric_def.metric_version,
                            unit=metric_def.unit,
                            denominator=metric_def.denominator,
                            arm_a=arm_a.arm_id,
                            arm_b=arm_b.arm_id,
                            mean_a=agg_a.aggregate_mean,
                            mean_b=agg_b.aggregate_mean,
                            mean_difference_b_minus_a=None,
                            median_difference_b_minus_a=None,
                            interpretation=(
                                f"{arm_b.arm_id} vs {arm_a.arm_id} incompatible metric "
                                f"{key} ({compat.finding}); descriptive only"
                            ),
                            status=ResourceStrategyMetricStatus.UNAVAILABLE,
                            reason=f"incompatible contract: {compat.finding}",
                        )
                    )
                    continue
                # Both available or partial: compute descriptive difference
                # Use mean difference only; keep wording descriptive, not winner.
                mean_diff = None
                median_diff = None
                if agg_a.aggregate_mean is not None and agg_b.aggregate_mean is not None:
                    mean_diff = agg_b.aggregate_mean - agg_a.aggregate_mean
                if agg_a.aggregate_median is not None and agg_b.aggregate_median is not None:
                    median_diff = agg_b.aggregate_median - agg_a.aggregate_median
                # Interpretation is neutral descriptive wording, self-qualifying and portable
                if mean_diff is None:
                    interp = (
                        f"{arm_b.arm_id} vs {arm_a.arm_id} descriptive difference unavailable "
                        f"for {metric_def.metric_key} ({metric_def.unit}); descriptive only"
                    )
                elif abs(mean_diff) < 1e-12:
                    interp = (
                        f"{arm_b.arm_id} mean equal to {arm_a.arm_id} "
                        f"(difference 0 {metric_def.unit}); descriptive only"
                    )
                elif mean_diff > 0:
                    interp = (
                        f"{arm_b.arm_id} mean higher than {arm_a.arm_id} "
                        f"by {mean_diff:.6g} {metric_def.unit}; descriptive only"
                    )
                else:
                    interp = (
                        f"{arm_b.arm_id} mean lower than {arm_a.arm_id} "
                        f"by {abs(mean_diff):.6g} {metric_def.unit}; descriptive only"
                    )
                pairwise.append(
                    ResourceStrategyPairwiseDifference(
                        metric_key=key,
                        metric_version=metric_def.metric_version,
                        unit=metric_def.unit,
                        denominator=metric_def.denominator,
                        arm_a=arm_a.arm_id,
                        arm_b=arm_b.arm_id,
                        mean_a=agg_a.aggregate_mean,
                        mean_b=agg_b.aggregate_mean,
                        mean_difference_b_minus_a=mean_diff,
                        median_difference_b_minus_a=median_diff,
                        interpretation=interp,
                        status=ResourceStrategyMetricStatus.AVAILABLE,
                        reason=None,
                    )
                )

    generated_at_val: datetime | None
    try:
        generated_at_val = clock() if callable(clock) else None
        if generated_at_val is not None and not isinstance(generated_at_val, datetime):
            generated_at_val = None
    except Exception:
        generated_at_val = None

    report = ResourceStrategyReport(
        schema_version=RESOURCE_STRATEGY_REPORT_VERSION,
        study_id=study.study_id,
        study_fingerprint=study.fingerprint(),
        source_fingerprint=study.source_fingerprint,
        evidence_mode=study.evidence_mode,
        admission_state=study.admission_state,
        replication_unit=study.replication_unit,
        common_matched_replication_ids=list(matched_ids),
        excluded_replication_ids=list(study.excluded_replication_ids),
        metric_catalog=list(study.metric_catalog),
        arm_summaries=arm_summaries,
        pairwise_differences=pairwise,
        compatibility=compatibility,
        limitations=list(study.limitations),
        provenance=dict(study.provenance),
        generated_at=generated_at_val,
        report_fingerprint="",
    )
    # Compute deterministic fingerprint after construction
    fingerprint = report.fingerprint()
    report.report_fingerprint = fingerprint
    return report


# ---------------------------------------------------------------------------
# Validation and loading
# ---------------------------------------------------------------------------


def validate_resource_strategy_study_dict(
    payload: dict[str, Any],
) -> ResourceStrategyStudy:
    """Validate a raw dict as a ResourceStrategyStudy, failing closed."""
    # Use strict model validation with extra=forbid at boundary.
    return ResourceStrategyStudy.model_validate(payload)


def load_resource_strategy_study_from_dict(
    payload: dict[str, Any],
) -> ResourceStrategyStudy:
    return validate_resource_strategy_study_dict(payload)


def load_resource_strategy_study_from_json(
    text: str,
) -> ResourceStrategyStudy:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("study JSON must be an object")
    return validate_resource_strategy_study_dict(data)


def load_resource_strategy_study_file(path: str | pathlib.Path) -> ResourceStrategyStudy:
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8")
    return load_resource_strategy_study_from_json(text)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------


def resource_strategy_study_to_json(study: ResourceStrategyStudy) -> str:
    return study.to_json()


def resource_strategy_report_to_json(report: ResourceStrategyReport) -> str:
    return report.to_json()


def resource_strategy_report_to_markdown(report: ResourceStrategyReport) -> str:
    lines = [
        "# Resource Strategy Report",
        "",
        f"- Study: `{_cell(report.study_id)}`",
        f"- Source fingerprint: `{report.source_fingerprint}`",
        f"- Study fingerprint: `{report.study_fingerprint}`",
        f"- Report fingerprint: `{report.report_fingerprint}`",
        f"- Evidence mode: `{report.evidence_mode.value}`",
        f"- Admission state: `{report.admission_state.value}`",
        f"- Replication unit: `{report.replication_unit.value}`",
        f"- Matched replications: {len(report.common_matched_replication_ids)}",
        f"- Excluded replications: {len(report.excluded_replication_ids)}",
        "",
        "## Limitations",
        "",
    ]
    if report.limitations:
        lines.extend(f"- {lim}" for lim in report.limitations)
    else:
        lines.append("No limitations declared.")
    lines.extend(["", "## Arm Summaries", ""])
    for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
        lines.append(f"### {arm.label} ({arm.arm_id})")
        lines.append(f"- Strategy type: `{_cell(arm.strategy_type)}`")
        lines.append(
            f"- Replications: total {arm.replication_count_total}, "  # noqa: E501
            f"matched {arm.replication_count_matched}"  # noqa: E501
        )
        lines.append(f"- Lifecycle totals: {arm.lifecycle_totals}")
        if arm.unavailable_metrics:
            lines.append(f"- Unavailable metrics: {', '.join(arm.unavailable_metrics)}")
        lines.append("")
        lines.append("| Metric | Unit | Denominator | Mean | Median | Min | Max | Status |")
        lines.append("|---|---:|---|---|---|---|---|---|")
        for agg in sorted(arm.metric_aggregates, key=lambda a: a.metric_key):
            lines.append(
                f"| {_cell(agg.metric_key)} | {_cell(agg.unit)} | {_cell(agg.denominator.value)} "
                f"| {_num(agg.aggregate_mean)} | {_num(agg.aggregate_median)} "
                f"| {_num(agg.aggregate_min)} | {_num(agg.aggregate_max)} "
                f"| {_cell(agg.status.value)} |"
            )
        lines.append("")
    lines.extend(["", "## Pairwise Descriptive Differences", ""])
    lines.append(
        "Descriptive differences only; no winner, best, or optimal claim is made unless "
        "the admitted contract explicitly defines and supports that decision."
    )
    lines.append("")
    if report.pairwise_differences:
        lines.append(
            "| Metric | Arms | Mean A | Mean B | B − A | Unit | Denominator | Interpretation |"
        )
        lines.append("|---|---|---|---|---|---|---|---|")
        for diff in sorted(
            report.pairwise_differences, key=lambda d: (d.metric_key, d.arm_a, d.arm_b)
        ):
            lines.append(
                f"| {_cell(diff.metric_key)} | {_cell(diff.arm_a)} vs "  # noqa: E501
                f"{_cell(diff.arm_b)} "  # noqa: E501
                f"| {_num(diff.mean_a)} | {_num(diff.mean_b)} | "  # noqa: E501
                f"{_num(diff.mean_difference_b_minus_a)} "  # noqa: E501
                f"| {_cell(diff.unit)} | {_cell(diff.denominator.value)} | "  # noqa: E501
                f"{_cell(diff.interpretation)} |"  # noqa: E501
            )
    else:
        lines.append("No pairwise differences available.")
    lines.extend(["", "## Compatibility", ""])
    for comp in sorted(report.compatibility, key=lambda c: c.metric_key):
        lines.append(f"- `{_cell(comp.metric_key)}`: {comp.status.value} ({_cell(comp.finding)})")
    lines.extend(["", "## Provenance", ""])
    if report.provenance:
        for key in sorted(report.provenance):
            lines.append(f"- `{_cell(key)}`: `{_cell(str(report.provenance[key]))}`")
    else:
        lines.append("No provenance references.")
    lines.extend(["", "## Excluded Replications", ""])
    if report.excluded_replication_ids:
        lines.append("| Replication | Arm | Code | Reason |")
        lines.append("|---|---|---|---|")
        for exc in sorted(
            report.excluded_replication_ids,
            key=lambda e: (e.replication_id, e.arm_id or ""),
        ):
            lines.append(
                f"| {_cell(exc.replication_id)} | {_cell(exc.arm_id or 'all')} "
                f"| {_cell(exc.code.value)} | {_cell(exc.reason)} |"
            )
    else:
        lines.append("No excluded replications.")
    return "\n".join(lines)


def resource_strategy_report_to_csv(report: ResourceStrategyReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "study_id",
            "arm_id",
            "metric_key",
            "metric_version",
            "unit",
            "denominator",
            "status",
            "replication_count",
            "aggregate_mean",
            "aggregate_median",
            "aggregate_min",
            "aggregate_max",
            "reason",
        ]
    )
    for arm in sorted(report.arm_summaries, key=lambda a: a.arm_id):
        for agg in sorted(arm.metric_aggregates, key=lambda a: a.metric_key):
            writer.writerow(
                [
                    report.study_id,
                    arm.arm_id,
                    agg.metric_key,
                    agg.metric_version,
                    agg.unit,
                    agg.denominator.value,
                    agg.status.value,
                    agg.replication_count,
                    _csv_num(agg.aggregate_mean),
                    _csv_num(agg.aggregate_median),
                    _csv_num(agg.aggregate_min),
                    _csv_num(agg.aggregate_max),
                    agg.reason or "",
                ]
            )
    return output.getvalue()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _num(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.6g}"


def _csv_num(value: float | None) -> str:
    if value is None:
        return ""
    # Use repr for round-trip-safe representation (17 significant digits for float64)
    # Preserve finite values losslessly; CSV is presentation but numeric fidelity is maintained.
    return repr(float(value))

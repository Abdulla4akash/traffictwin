"""Metric result models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.domain.energy import TaskEnergyContract
from traffictwin.domain.spatial import TaskRsuTargetContract, VehicleSpatialGridContract

JsonScalar: TypeAlias = str | int | float | bool | None
JsonObject: TypeAlias = dict[str, Any]
JsonValue: TypeAlias = Any


class MetricStatus(StrEnum):
    """Metric computation status."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    INVALID = "invalid"


class UnavailableReason(StrEnum):
    """Stable reason codes for unavailable or invalid metrics."""

    REQUIRED_TABLE_UNAVAILABLE = "REQUIRED_TABLE_UNAVAILABLE"
    REQUIRED_FIELD_UNAVAILABLE = "REQUIRED_FIELD_UNAVAILABLE"
    NO_VALID_ROWS = "NO_VALID_ROWS"
    INSUFFICIENT_SAMPLE_SIZE = "INSUFFICIENT_SAMPLE_SIZE"
    INVALID_SOURCE_DATA = "INVALID_SOURCE_DATA"
    UNIT_UNKNOWN = "UNIT_UNKNOWN"
    CAPACITY_UNAVAILABLE = "CAPACITY_UNAVAILABLE"
    TASK_CLASS_UNAVAILABLE = "TASK_CLASS_UNAVAILABLE"
    VEHICLE_TIER_UNAVAILABLE = "VEHICLE_TIER_UNAVAILABLE"
    NO_COMPLETED_TRIPS = "NO_COMPLETED_TRIPS"
    NO_LATENCY_VALUES = "NO_LATENCY_VALUES"
    ENERGY_CONTRACT_UNAVAILABLE = "ENERGY_CONTRACT_UNAVAILABLE"
    TASK_RSU_TARGET_CONTRACT_UNAVAILABLE = "TASK_RSU_TARGET_CONTRACT_UNAVAILABLE"
    VEHICLE_SPATIAL_GRID_CONTRACT_UNAVAILABLE = "VEHICLE_SPATIAL_GRID_CONTRACT_UNAVAILABLE"
    TARGET_COVERAGE_INSUFFICIENT = "TARGET_COVERAGE_INSUFFICIENT"
    TARGET_JOIN_INCOMPATIBLE = "TARGET_JOIN_INCOMPATIBLE"
    COORDINATE_COVERAGE_INSUFFICIENT = "COORDINATE_COVERAGE_INSUFFICIENT"
    GROUP_COVERAGE_INSUFFICIENT = "GROUP_COVERAGE_INSUFFICIENT"
    INSUFFICIENT_GROUP_COUNT = "INSUFFICIENT_GROUP_COUNT"
    INSUFFICIENT_GROUP_SUPPORT = "INSUFFICIENT_GROUP_SUPPORT"
    COMPARISON_PAIR_INCOMPATIBLE = "COMPARISON_PAIR_INCOMPATIBLE"
    RANDOM_SEED_MISMATCH = "RANDOM_SEED_MISMATCH"
    BASELINE_ZERO = "BASELINE_ZERO"
    METRIC_NOT_APPLICABLE = "METRIC_NOT_APPLICABLE"
    METRIC_VERSION_MISMATCH = "METRIC_VERSION_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    EXPERIMENT_MISMATCH = "EXPERIMENT_MISMATCH"
    SEED_RELATIONSHIP_UNKNOWN = "SEED_RELATIONSHIP_UNKNOWN"
    PLUGIN_AVAILABILITY_REQUIREMENT_UNMET = "PLUGIN_AVAILABILITY_REQUIREMENT_UNMET"
    PLUGIN_EXECUTION_FAILED = "PLUGIN_EXECUTION_FAILED"
    PLUGIN_NONDETERMINISTIC = "PLUGIN_NONDETERMINISTIC"
    PLUGIN_OUTPUT_INVALID = "PLUGIN_OUTPUT_INVALID"
    PLUGIN_DECLARED_UNAVAILABLE = "PLUGIN_DECLARED_UNAVAILABLE"


class RunMetricContext(BaseModel):
    """Run provenance carried by every metric."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    experiment_id: str | None
    seed_id: str
    algorithm: str
    checkpoint: str | None = None
    random_seed: int
    synthetic: bool
    environment: str | None = None
    environment_version: str | None = None
    environment_commit: str | None = None
    source_bundle_fingerprint: str | None = None
    energy_contract: TaskEnergyContract | None = None
    task_rsu_target_contract: TaskRsuTargetContract | None = None
    vehicle_spatial_grid_contract: VehicleSpatialGridContract | None = None
    validation_may_import: bool = True


class MetricValue(BaseModel):
    """One metric result."""

    model_config = ConfigDict(extra="forbid")

    metric_key: str
    status: MetricStatus
    value: JsonValue = None
    unit: str
    scope: str
    dimensions: dict[str, JsonScalar] = Field(default_factory=dict)
    required_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    reason_codes: list[UnavailableReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    implementation_version: str
    run_id: str
    experiment_id: str | None
    seed_id: str
    algorithm: str
    checkpoint: str | None = None
    random_seed: int
    synthetic: bool
    environment: str | None = None
    environment_version: str | None = None
    environment_commit: str | None = None
    computed_at: datetime
    metadata: JsonObject = Field(default_factory=dict)


class MetricCollection(BaseModel):
    """Ordered metric collection for one run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    metric_version: str
    results: list[MetricValue]
    unavailable_count: int
    partial_count: int
    generated_at: datetime
    input_fingerprint: str | None = None

    def by_key(self) -> dict[str, MetricValue]:
        """Return metric results by key."""

        return {metric.metric_key: metric for metric in self.results}

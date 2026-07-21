"""Configuration models for deterministic synthetic run generation."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from traffictwin.domain.enums import TaskClass
from traffictwin.domain.measurement import (
    MeasurementTableKind,
    SyntheticMeasurementImpairmentConfig,
)

SYNTHETIC_GENERATOR_VERSION = "1.0"
MAX_SYNTHETIC_CONFIG_BYTES = 1_000_000
MixKey = TypeVar("MixKey", str, TaskClass)


class SyntheticPolicyProfile(StrEnum):
    """Documented synthetic policy profiles.

    These labels describe deterministic workload-generation behavior only. They
    do not claim to implement learned policies or real algorithms.
    """

    ALWAYS_LOCAL = "synthetic-always-local"
    ALWAYS_V2I = "synthetic-always-v2i"
    RANDOM = "synthetic-random"
    SELECTIVE = "synthetic-selective"
    BALANCED = "synthetic-balanced"
    LOW_OFFLOAD = "synthetic-low-offload"


class IncidentSpec(BaseModel):
    """Synthetic incident marker."""

    model_config = ConfigDict(extra="forbid")

    timestamp_s: float = Field(ge=0)
    incident_type: str = Field(min_length=1)
    location: str | None = None
    severity: str | None = None
    duration_s: float = Field(default=60.0, gt=0)
    lanes_closed: int | None = Field(default=None, ge=0)
    demand_multiplier: float = Field(default=1.0, gt=0)
    vehicles_involved: list[str] = Field(default_factory=list)


class SyntheticScenarioConfig(BaseModel):
    """Versioned configuration for one generated TrafficTwin bundle."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    experiment_id: str = "exp-standalone-demo"
    baseline_seed_id: str | None = None
    random_seed: int = Field(default=7, ge=0)
    duration_s: float = Field(default=300.0, gt=0)
    sampling_interval_s: float = Field(default=30.0, gt=0)
    vehicle_count: int = Field(default=20, ge=1)
    vehicle_tier_mix: dict[str, float] = Field(
        default_factory=lambda: {"low": 0.3, "medium": 0.5, "high": 0.2}
    )
    task_arrival_rate: float = Field(default=0.10, gt=0)
    task_class_mix: dict[TaskClass, float] = Field(
        default_factory=lambda: {TaskClass.T1: 0.3, TaskClass.T2: 0.4, TaskClass.T3: 0.3}
    )
    local_capacity_by_tier: dict[str, float] = Field(
        default_factory=lambda: {"low": 0.55, "medium": 0.75, "high": 0.9}
    )
    rsu_count: int = Field(default=2, ge=1)
    rsu_capacity: float = Field(default=35.0, gt=0)
    baseline_network_delay_ms: float = Field(default=45.0, ge=0)
    congestion_multiplier: float = Field(default=1.0, gt=0)
    policy_behavior: SyntheticPolicyProfile = SyntheticPolicyProfile.BALANCED
    trip_count: int = Field(default=12, ge=0)
    incident_schedule: list[IncidentSpec] = Field(default_factory=list)
    synthetic_faults: list[str] = Field(default_factory=list)
    include_infrastructure: bool = True
    include_vehicles: bool = True
    include_traffic: bool = True
    include_trips: bool = True
    include_incidents: bool = True
    measurement_imperfections: SyntheticMeasurementImpairmentConfig | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    provenance: dict[str, str] = Field(
        default_factory=lambda: {
            "producer": "TrafficTwin standalone synthetic generator",
            "notes": "Synthetic workload for software demonstration; not a calibrated simulator.",
        }
    )

    @field_validator("vehicle_tier_mix")
    @classmethod
    def validate_tier_mix(cls, value: dict[str, float]) -> dict[str, float]:
        """Validate vehicle-tier shares."""

        return _validate_mix(value, "vehicle_tier_mix", allowed={"low", "medium", "high"})

    @field_validator("task_class_mix")
    @classmethod
    def validate_task_class_mix(cls, value: dict[TaskClass, float]) -> dict[TaskClass, float]:
        """Validate task-class shares."""

        return _validate_mix(value, "task_class_mix")

    @model_validator(mode="after")
    def validate_measurement_stream_availability(self) -> SyntheticScenarioConfig:
        """Reject impairment settings whose generated observation stream is disabled."""

        impairment = self.measurement_imperfections
        if impairment is None:
            return self
        required: set[MeasurementTableKind] = set(impairment.row_dropout_fraction_by_table)
        if (
            impairment.vehicle_position_max_error_m > 0
            or impairment.vehicle_speed_max_error_mps > 0
        ):
            required.add(MeasurementTableKind.VEHICLE_STATE)
        if impairment.traffic_speed_max_error_mps > 0 or impairment.traffic_count_max_error > 0:
            required.add(MeasurementTableKind.TRAFFIC_OBS)
        if (
            impairment.infrastructure_utilisation_max_error > 0
            or impairment.infrastructure_queue_max_error > 0
        ):
            required.add(MeasurementTableKind.INFRA_STATE)
        enabled = {
            MeasurementTableKind.INFRA_STATE: self.include_infrastructure,
            MeasurementTableKind.VEHICLE_STATE: self.include_vehicles,
            MeasurementTableKind.TRAFFIC_OBS: self.include_traffic,
        }
        missing = sorted(table.value for table in required if not enabled[table])
        if missing:
            raise ValueError(
                "measurement impairments require enabled generated streams: " + ", ".join(missing)
            )
        return self


def load_synthetic_scenario_config(path: str | Path) -> SyntheticScenarioConfig:
    """Load one strict bounded YAML/JSON generator configuration."""

    source = Path(path)
    try:
        if source.stat().st_size > MAX_SYNTHETIC_CONFIG_BYTES:
            raise ValueError(
                f"synthetic configuration exceeds {MAX_SYNTHETIC_CONFIG_BYTES:,} bytes"
            )
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read synthetic configuration: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid synthetic configuration YAML: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("synthetic configuration must be a mapping")
    try:
        return SyntheticScenarioConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"invalid synthetic configuration: {exc}") from exc


def synthetic_scenario_config_to_yaml(config: SyntheticScenarioConfig) -> str:
    """Serialise a complete explicit generator configuration."""

    return yaml.safe_dump(
        config.model_dump(mode="json", exclude_none=True),
        sort_keys=False,
        allow_unicode=False,
    )


def _validate_mix(
    value: dict[MixKey, float],
    field_name: str,
    *,
    allowed: set[str] | None = None,
) -> dict[MixKey, float]:
    if not value:
        msg = f"{field_name} must not be empty"
        raise ValueError(msg)
    if allowed is not None:
        unsupported = sorted(str(key) for key in value if str(key) not in allowed)
        if unsupported:
            msg = f"{field_name} contains unsupported values: {', '.join(unsupported)}"
            raise ValueError(msg)
    if any(share < 0 for share in value.values()):
        msg = f"{field_name} shares must be non-negative"
        raise ValueError(msg)
    total = sum(value.values())
    if abs(total - 1.0) > 1e-6:
        msg = f"{field_name} shares must sum to 1.0; got {total:.6f}"
        raise ValueError(msg)
    return value

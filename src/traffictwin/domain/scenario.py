"""Scenario seed domain model."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.domain.enums import (
    Decision,
    FleetTierMix,
    RsuCapacityMode,
    TaskClass,
    WorkloadOrdering,
)

SUPPORTED_SEED_SCHEMA_VERSION: Literal["1.0"] = "1.0"
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")


def _validate_identifier(value: str | None, field_name: str) -> str | None:
    if value is None:
        return value
    if not _IDENTIFIER_RE.fullmatch(value):
        msg = (
            f"{field_name} must start with an alphanumeric character and contain only "
            "letters, numbers, dots, underscores, colons, or hyphens"
        )
        raise ValueError(msg)
    return value


class StrictModel(BaseModel):
    """Base model that rejects fields not in the documented Phase 1 contract."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class TrafficSettings(StrictModel):
    """Traffic-side scenario settings supported by the seed schema."""

    event_type: str | None = None
    location: str | None = None
    lanes_closed: int | None = Field(default=None, ge=0)
    duration_min: float | None = Field(default=None, ge=0)
    demand_profile: str | None = None


class DemandSettings(StrictModel):
    """Demand multiplier settings."""

    multiplier: float = Field(default=1.0, gt=0)


class WorkloadSettings(StrictModel):
    """Workload settings for task generation."""

    birth_rate_multiplier: float = Field(default=1.0, gt=0)
    class_mix: dict[TaskClass, float] = Field(default_factory=dict)
    ordering: WorkloadOrdering = WorkloadOrdering.MIXED

    @field_validator("class_mix")
    @classmethod
    def validate_class_mix(cls, value: dict[TaskClass, float]) -> dict[TaskClass, float]:
        if not value:
            return value
        invalid = [task_class.value for task_class, share in value.items() if share < 0]
        if invalid:
            msg = f"class_mix shares must be non-negative; invalid classes: {', '.join(invalid)}"
            raise ValueError(msg)
        total = sum(value.values())
        if abs(total - 1.0) > 1e-6:
            msg = f"class_mix shares must sum to 1.0; got {total:.6f}"
            raise ValueError(msg)
        return value


class FleetSettings(StrictModel):
    """Fleet settings for a scenario seed."""

    count: int | None = Field(default=None, ge=0)
    tier_mix: FleetTierMix = FleetTierMix.MIXED


class InfrastructureSettings(StrictModel):
    """Infrastructure settings for a scenario seed."""

    rsu_count: int | None = Field(default=None, ge=0)
    rsu_capacity_mode: RsuCapacityMode = RsuCapacityMode.STANDARD
    failed_rsus: list[str] = Field(default_factory=list)

    @field_validator("failed_rsus")
    @classmethod
    def validate_failed_rsus(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("failed_rsus must not contain duplicates")
        for rsu_id in value:
            _validate_identifier(rsu_id, "failed_rsus item")
        return value


class PolicySettings(StrictModel):
    """Policy/checkpoint settings for scenario evaluation."""

    algorithm: str = Field(min_length=1)
    checkpoint: str | None = None


class EvaluationSettings(StrictModel):
    """Evaluation reproducibility settings."""

    random_seed: int = Field(ge=0)


class Provenance(StrictModel):
    """Seed provenance metadata."""

    created_by: str = Field(min_length=1)
    source: str = Field(min_length=1)


class ScenarioSeed(StrictModel):
    """Versioned TrafficTwin what-if scenario seed."""

    schema_version: Literal["1.0"] = SUPPORTED_SEED_SCHEMA_VERSION
    seed_id: str = Field(alias="id")
    name: str = Field(min_length=1)
    description: str = ""
    parent_seed_id: str | None = Field(default=None, alias="base")
    preset_id: str | None = None
    traffic: TrafficSettings = Field(default_factory=TrafficSettings)
    demand: DemandSettings = Field(default_factory=DemandSettings)
    workload: WorkloadSettings
    fleet: FleetSettings = Field(default_factory=FleetSettings)
    infrastructure: InfrastructureSettings = Field(default_factory=InfrastructureSettings)
    allowed_decisions: list[Decision]
    policy: PolicySettings
    evaluation: EvaluationSettings
    compare_against: str | None = None
    provenance: Provenance

    @field_validator("seed_id", "parent_seed_id", "preset_id", "compare_against")
    @classmethod
    def validate_identifiers(cls, value: str | None, info: object) -> str | None:
        field_name = getattr(info, "field_name", "identifier")
        return _validate_identifier(value, field_name)

    @field_validator("allowed_decisions")
    @classmethod
    def validate_allowed_decisions(cls, value: list[Decision]) -> list[Decision]:
        if not value:
            raise ValueError("allowed_decisions must include at least one decision")
        if len(set(value)) != len(value):
            raise ValueError("allowed_decisions must not contain duplicates")
        return value


class SeedDocument(StrictModel):
    """Top-level YAML document for a scenario seed."""

    schema_version: Literal["1.0"]
    seed: ScenarioSeed

    @model_validator(mode="after")
    def validate_schema_versions_match(self) -> SeedDocument:
        if self.seed.schema_version != self.schema_version:
            msg = (
                "top-level schema_version must match seed.schema_version "
                f"({self.schema_version!r} != {self.seed.schema_version!r})"
            )
            raise ValueError(msg)
        return self

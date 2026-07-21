"""Versioned diagnostic rule configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class R0Config(BaseModel):
    """R0 configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True


class R1Config(BaseModel):
    """Under-offloading candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    t1_miss_rate_min: float = Field(default=0.20, ge=0.0, le=1.0)
    low_tier_t1_miss_rate_min: float = Field(default=0.20, ge=0.0, le=1.0)
    rsu_utilisation_max: float = Field(default=0.60, ge=0.0, le=1.0)
    offload_rate_max: float = Field(default=0.20, ge=0.0, le=1.0)
    minimum_task_count: int = Field(default=20, ge=1)


class R2Config(BaseModel):
    """Infrastructure-bottleneck candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    saturation_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    minimum_saturation_duration_s: float = Field(default=30.0, ge=0.0)
    queue_growth_required: bool = True
    minimum_missed_tasks: int = Field(default=1, ge=0)
    queue_length_high_min: float = Field(default=5.0, ge=0.0)


class R3Config(BaseModel):
    """Scenario-triviality candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    maximum_cross_algorithm_dispersion: float = Field(default=0.02, ge=0.0)
    maximum_local_gap_from_best: float = Field(default=0.02, ge=0.0)
    maximum_pressure_indicator: float | None = Field(default=None, ge=0.0)
    minimum_algorithms: int = Field(default=2, ge=2)


class R4Config(BaseModel):
    """Load-imbalance candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    maximum_jain_index: float = Field(default=0.80, ge=0.0, le=1.0)
    maximum_mean_utilisation: float = Field(default=0.80, ge=0.0, le=1.0)
    minimum_rsu_count: int = Field(default=2, ge=2)


class R5Config(BaseModel):
    """Training-to-validation drift candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    minimum_pair_count: int = Field(default=2, ge=1)
    maximum_absolute_gap: float = Field(default=0.10, ge=0.0)


class R6Config(BaseModel):
    """Temporal degradation and recovery candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    baseline_window_count: int = Field(default=2, ge=1, le=100)
    minimum_evaluable_windows: int = Field(default=4, ge=2, le=10_000)
    minimum_deterioration_delta: float = Field(
        default=0.10,
        gt=0.0,
        allow_inf_nan=False,
    )
    sustained_window_count: int = Field(default=2, ge=1, le=100)
    recovery_tolerance: float = Field(default=0.05, ge=0.0, allow_inf_nan=False)
    recovery_horizon_windows: int = Field(default=4, ge=1, le=1_000)

    @model_validator(mode="after")
    def validate_window_requirements(self) -> R6Config:
        required = self.baseline_window_count + self.sustained_window_count
        if self.minimum_evaluable_windows < required:
            raise ValueError("minimum_evaluable_windows must cover baseline and sustained windows")
        if self.recovery_horizon_windows < self.sustained_window_count:
            raise ValueError(
                "recovery_horizon_windows must cover the sustained deterioration window count"
            )
        return self


class R7Config(BaseModel):
    """Operational tier/target outcome-disparity candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    dimension: Literal["vehicle_tier_completion", "target_rsu_completion"] = (
        "vehicle_tier_completion"
    )
    minimum_outcome_gap: float = Field(default=0.20, ge=0.0, le=1.0, allow_inf_nan=False)
    minimum_group_support: int = Field(default=2, ge=1, le=1_000_000)


class R8Config(BaseModel):
    """Completed-task energy anomaly candidate configuration."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    minimum_energy_per_completed_task_j: float = Field(
        default=1.50,
        ge=0.0,
        allow_inf_nan=False,
    )
    minimum_completed_tasks: int = Field(default=10, ge=1, le=1_000_000)


class RuleSetConfig(BaseModel):
    """Versioned rule-set configuration.

    Defaults are provisional synthetic-evaluation thresholds, not validated
    research thresholds.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    ruleset_version: str = "1.3"
    r0: R0Config = Field(default_factory=R0Config)
    r1: R1Config = Field(default_factory=R1Config)
    r2: R2Config = Field(default_factory=R2Config)
    r3: R3Config = Field(default_factory=R3Config)
    r4: R4Config = Field(default_factory=R4Config)
    r5: R5Config = Field(default_factory=R5Config)
    r6: R6Config = Field(default_factory=R6Config)
    r7: R7Config = Field(default_factory=R7Config)
    r8: R8Config = Field(default_factory=R8Config)

    def enabled_rule_ids(self) -> list[str]:
        """Return enabled rule identifiers in deterministic order."""

        enabled: list[str] = []
        for rule_id in ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"):
            section = getattr(self, rule_id.lower())
            if section.enabled:
                enabled.append(rule_id)
        return enabled

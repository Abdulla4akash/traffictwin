"""Versioned diagnostic rule configuration."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


class RuleSetConfig(BaseModel):
    """Versioned rule-set configuration.

    Defaults are provisional synthetic-evaluation thresholds, not validated
    research thresholds.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    ruleset_version: str = "1.0"
    r0: R0Config = Field(default_factory=R0Config)
    r1: R1Config = Field(default_factory=R1Config)
    r2: R2Config = Field(default_factory=R2Config)
    r3: R3Config = Field(default_factory=R3Config)

    def enabled_rule_ids(self) -> list[str]:
        """Return enabled rule identifiers in deterministic order."""

        enabled: list[str] = []
        for rule_id in ("R0", "R1", "R2", "R3"):
            section = getattr(self, rule_id.lower())
            if section.enabled:
                enabled.append(rule_id)
        return enabled

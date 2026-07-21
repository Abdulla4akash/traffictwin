"""Metric definition models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class MetricDomain(StrEnum):
    """Metric domains."""

    TASK = "task"
    FAIRNESS = "fairness"
    INFRASTRUCTURE = "infrastructure"
    SPATIAL = "spatial"
    TRAFFIC = "traffic"
    TRIP = "trip"
    COMPARISON = "comparison"
    DATA_QUALITY = "data_quality"
    CUSTOM = "custom"


class AggregationScope(StrEnum):
    """Metric aggregation scopes."""

    RUN = "run"
    TASK_CLASS = "task_class"
    VEHICLE_TIER = "vehicle_tier"
    RSU = "RSU"
    SPATIAL_CELL = "spatial_cell"
    TIME_WINDOW = "time_window"
    EXPERIMENT = "experiment"
    SEED_PAIR = "seed_pair"


class MetricDefinition(BaseModel):
    """Versioned metric definition."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    human_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    domain: MetricDomain
    unit: str
    aggregation_scope: AggregationScope
    required_tables: list[str] = Field(default_factory=list)
    required_fields: dict[str, list[str]] = Field(default_factory=dict)
    optional_fields: dict[str, list[str]] = Field(default_factory=dict)
    implementation_version: str = "1.0"
    higher_is_better: bool | None = None
    time_window_applicable: bool = False
    time_anchor: str | None = None
    limitations: list[str] = Field(default_factory=list)

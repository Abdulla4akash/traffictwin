"""Metric engine configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from traffictwin.metrics.catalogue import METRIC_VERSION


class MetricEngineConfig(BaseModel):
    """Configuration for deterministic metric computation."""

    model_config = ConfigDict(extra="forbid")

    saturation_threshold: float = Field(default=0.90, ge=0, le=1)
    saturation_max_gap_s: float | None = Field(default=None, gt=0)
    percentile_method: Literal["linear"] = "linear"
    relative_delta_zero_policy: str = "zero_if_both_zero_else_unavailable"
    minimum_sample_size: int = Field(default=1, ge=1)
    metric_version: str = METRIC_VERSION

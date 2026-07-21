"""Versioned evidence contracts for per-RSU attribution and spatial grids."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SPATIAL_CONTRACT_VERSION: Literal["1.0"] = "1.0"


class TaskRsuTargetContract(BaseModel):
    """Exact semantics required for per-RSU task-outcome metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = SPATIAL_CONTRACT_VERSION
    eligible_decision: Literal["v2i"] = "v2i"
    target_semantics: Literal["executing_rsu_id"] = "executing_rsu_id"
    join_method: Literal["exact_task_target_id_to_infrastructure_rsu_id"] = (
        "exact_task_target_id_to_infrastructure_rsu_id"
    )
    non_v2i_policy: Literal["excluded_from_per_rsu_task_outcomes"] = (
        "excluded_from_per_rsu_task_outcomes"
    )
    minimum_target_coverage_fraction: float = Field(default=1.0, ge=1.0, le=1.0)
    attribution_interpretation: Literal["observed_execution_target_not_causal_assignment"] = (
        "observed_execution_target_not_causal_assignment"
    )

    def fingerprint(self) -> str:
        """Return the stable task-to-RSU semantic fingerprint."""

        return _fingerprint(self)


class VehicleSpatialGridContract(BaseModel):
    """Exact coordinate-frame and grid semantics for vehicle spatial summaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = SPATIAL_CONTRACT_VERSION
    position_semantics: Literal["vehicle_position_at_observation_timestamp"] = (
        "vehicle_position_at_observation_timestamp"
    )
    coordinate_frame_id: str = Field(min_length=1, max_length=128)
    canonical_coordinate_unit: Literal["m"] = "m"
    origin_x_m: float = 0.0
    origin_y_m: float = 0.0
    cell_width_m: float = Field(default=100.0, gt=0)
    cell_height_m: float = Field(default=100.0, gt=0)
    assignment_method: Literal["axis_aligned_floor_from_fixed_origin"] = (
        "axis_aligned_floor_from_fixed_origin"
    )
    minimum_coordinate_coverage_fraction: float = Field(default=1.0, ge=1.0, le=1.0)
    geographic_interpretation: Literal[
        "source_coordinate_frame_only_not_geographic_without_separate_crs_evidence"
    ] = "source_coordinate_frame_only_not_geographic_without_separate_crs_evidence"

    @field_validator("origin_x_m", "origin_y_m", "cell_width_m", "cell_height_m")
    @classmethod
    def validate_finite_grid_values(cls, value: float) -> float:
        """Reject non-finite grid geometry."""

        if not math.isfinite(value):
            raise ValueError("spatial grid values must be finite")
        return value

    def fingerprint(self) -> str:
        """Return the stable coordinate/grid semantic fingerprint."""

        return _fingerprint(self)


DEFAULT_TASK_RSU_TARGET_CONTRACT = TaskRsuTargetContract()
DEFAULT_SYNTHETIC_SPATIAL_GRID_CONTRACT = VehicleSpatialGridContract(
    coordinate_frame_id="synthetic-corridor-coordinate-frame-v1",
)


def _fingerprint(contract: BaseModel) -> str:
    encoded = json.dumps(
        contract.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(encoded).hexdigest()

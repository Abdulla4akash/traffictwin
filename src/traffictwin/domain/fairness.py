"""Versioned policy for operational-group fairness metrics."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FAIRNESS_POLICY_VERSION: Literal["1.0"] = "1.0"


class OperationalFairnessPolicy(BaseModel):
    """Exact evidence admission policy for vehicle-tier and RSU disparity metrics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = FAIRNESS_POLICY_VERSION
    minimum_group_count: Literal[2] = 2
    minimum_group_support: Literal[2] = 2
    minimum_coverage_fraction: float = Field(default=1.0, ge=1.0, le=1.0)
    vehicle_tier_semantics: Literal["stable_non_empty_tier_per_vehicle_over_metric_scope"] = (
        "stable_non_empty_tier_per_vehicle_over_metric_scope"
    )
    vehicle_task_join: Literal["exact_task_vehicle_id"] = "exact_task_vehicle_id"
    rsu_group_semantics: Literal["canonical_infrastructure_rsu_id"] = (
        "canonical_infrastructure_rsu_id"
    )
    rsu_load_eligibility: Literal["non_negative_active_tasks_divided_by_positive_capacity"] = (
        "non_negative_active_tasks_divided_by_positive_capacity"
    )
    disparity_method: Literal["maximum_group_mean_minus_minimum_group_mean"] = (
        "maximum_group_mean_minus_minimum_group_mean"
    )
    jain_method: Literal["square_of_sum_divided_by_n_times_sum_of_squares"] = (
        "square_of_sum_divided_by_n_times_sum_of_squares"
    )
    attribute_interpretation: Literal["operational_groups_only_not_protected_attributes"] = (
        "operational_groups_only_not_protected_attributes"
    )

    def fingerprint(self) -> str:
        """Return the stable policy fingerprint used by metrics and comparisons."""

        encoded = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


DEFAULT_OPERATIONAL_FAIRNESS_POLICY = OperationalFairnessPolicy()

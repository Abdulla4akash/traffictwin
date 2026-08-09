"""Authoritative control contract for What-If Studio (shared with challenge bridge).

This module is the single source of truth for What-If widget limits.
Both the Studio page and the Challenge→What-If bridge reuse these specs,
so range validation is fail-closed and not duplicated.
"""

from __future__ import annotations

from typing import Any

# Spec per What-If variation field. Only fields with existing UI limits are
# enumerated. Text/select fields have no numeric range but may have allowed
# choices.
# Each entry: {"min": ..., "max": ..., "type": ..., "step": ...}
# Missing min/max means unbounded in that direction (existing UI shows no limit).

WHATIF_CONTROL_SPEC: dict[str, dict[str, Any]] = {
    # demand / congestion
    "congestion_multiplier": {"min": 0.25, "max": 3.0, "type": float, "step": 0.05},
    "vehicle_count": {"min": 1, "type": int},
    "task_arrival_rate": {"min": 0.001, "type": float, "step": 0.01},
    # task mix shares
    "task_mix_t1": {"min": 0.0, "max": 1.0, "type": float, "step": 0.05},
    "task_mix_t2": {"min": 0.0, "max": 1.0, "type": float, "step": 0.05},
    "task_mix_t3": {"min": 0.0, "max": 1.0, "type": float, "step": 0.05},
    # infra
    "rsu_count": {"min": 1, "type": int},
    "rsu_capacity": {"min": 1.0, "type": float},
    # incident
    "incident_start_s": {"min": 0.0, "type": float},
    "incident_duration_s": {"min": 1.0, "type": float},
    "lanes_closed": {"min": 0, "type": int},
    "event_demand_multiplier": {"min": 0.1, "type": float, "step": 0.1},
    # seed
    "random_seed": {"min": 0, "type": int},
    # baseline seed (separate from variation override but also challenge-mappable)
    "baseline_random_seed": {"min": 0, "type": int},
}

# Widget key mapping: whatif_field -> session_state key
WHATIF_WIDGET_KEYS: dict[str, str] = {
    "congestion_multiplier": "whatif_congestion_multiplier",
    "vehicle_count": "whatif_vehicle_count",
    "task_arrival_rate": "whatif_task_arrival_rate",
    "task_mix_t1": "whatif_task_mix_t1",
    "task_mix_t2": "whatif_task_mix_t2",
    "task_mix_t3": "whatif_task_mix_t3",
    "rsu_count": "whatif_rsu_count",
    "rsu_capacity": "whatif_rsu_capacity",
    "random_seed": "whatif_random_seed",
    "incident_enabled": "whatif_incident_enabled",
    "incident_type": "whatif_incident_type",
    "incident_location": "whatif_incident_location",
    "incident_severity": "whatif_incident_severity",
    "incident_start_s": "whatif_incident_start_s",
    "incident_duration_s": "whatif_incident_duration_s",
    "lanes_closed": "whatif_lanes_closed",
    "event_demand_multiplier": "whatif_event_demand_multiplier",
    # form identity fields also keyed for completeness (not challenge-prefilled except seed)
    "baseline_preset": "whatif_baseline_preset",
    "pair_name": "whatif_pair_name",
    "experiment_id": "whatif_experiment_id",
    "baseline_random_seed": "whatif_baseline_random_seed",
    "policy_profile": "whatif_policy_profile",
}

DEFAULT_WHATIF_WIDGET_VALUES: dict[str, Any] = {
    "whatif_incident_enabled": True,
    "whatif_incident_type": "synthetic_congestion_pulse",
    "whatif_incident_location": "synthetic-corridor-a",
    "whatif_incident_severity": "moderate",
    "whatif_incident_start_s": 120.0,
    "whatif_incident_duration_s": 60.0,
    "whatif_lanes_closed": 1,
    "whatif_event_demand_multiplier": 1.3,
    "whatif_congestion_multiplier": 1.65,
    "whatif_vehicle_count": 20,
    "whatif_task_arrival_rate": 0.18,
    "whatif_task_mix_t1": 0.30,
    "whatif_task_mix_t2": 0.40,
    "whatif_task_mix_t3": 0.30,
    "whatif_rsu_count": 2,
    "whatif_rsu_capacity": 22.0,
    "whatif_random_seed": 7,
    "whatif_baseline_random_seed": 7,
    "whatif_baseline_preset": "baseline",
    "whatif_pair_name": "congestion-pulse",
    "whatif_experiment_id": "exp-whatif-demo",
    "whatif_policy_profile": "synthetic-balanced",
}


def is_value_representable(field: str, value: Any) -> tuple[bool, str | None]:  # noqa: ANN401
    """Check if a mapped value is representable by current What-If control.

    Returns (True, None) if representable, else (False, reason).
    """
    spec = WHATIF_CONTROL_SPEC.get(field)
    if spec is None:
        # No numeric spec — text/select fields are always representable if non-empty
        if isinstance(value, str):
            if not value.strip():
                return False, "outside current What-If control range — empty string not allowed"
            return True, None
        if isinstance(value, bool):
            return True, None
        # Fallback: allow if not numeric
        return True, None
    # Numeric check
    if not isinstance(value, (int, float, bool)):
        return False, f"outside current What-If control range — expected numeric for {field!r}"
    if isinstance(value, bool):
        return False, f"outside current What-If control range — boolean not valid for {field!r}"
    fv = float(value)
    # Check type expectation but allow int->float promotion
    if spec.get("type") is int and not isinstance(value, int) and abs(fv - round(fv)) > 1e-9:
        return False, f"outside current What-If control range — {field!r} expects integer"
    min_v = spec.get("min")
    max_v = spec.get("max")
    if min_v is not None and fv < float(min_v) - 1e-9:
        return (
            False,
            f"outside current What-If control range — {field!r}={value} below minimum {min_v}",
        )
    if max_v is not None and fv > float(max_v) + 1e-9:
        return (
            False,
            f"outside current What-If control range — {field!r}={value} above maximum {max_v}",
        )
    return True, None

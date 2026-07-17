"""Capability manifest models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CapabilitySupport(StrEnum):
    """Three-valued capability support state."""

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    def to_manifest_value(self) -> bool | str:
        """Return a YAML-friendly representation."""

        if self is CapabilitySupport.TRUE:
            return True
        if self is CapabilitySupport.FALSE:
            return False
        return "unknown"


def _coerce_capability(value: object) -> CapabilitySupport:
    if isinstance(value, CapabilitySupport):
        return value
    if isinstance(value, bool):
        return CapabilitySupport.TRUE if value else CapabilitySupport.FALSE
    if isinstance(value, str):
        normalised = value.lower()
        if normalised in {"true", "supported"}:
            return CapabilitySupport.TRUE
        if normalised in {"false", "unsupported"}:
            return CapabilitySupport.FALSE
        if normalised == "unknown":
            return CapabilitySupport.UNKNOWN
    msg = f"capability must be true, false, or unknown; got {value!r}"
    raise ValueError(msg)


class CapabilitySet(BaseModel):
    """Supported actions and controls for an environment adapter."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    seed_import: CapabilitySupport = CapabilitySupport.TRUE
    seed_export: CapabilitySupport = CapabilitySupport.TRUE
    run_bundle_import: CapabilitySupport = CapabilitySupport.TRUE
    direct_launch: CapabilitySupport = CapabilitySupport.FALSE
    asynchronous_launch: CapabilitySupport = CapabilitySupport.FALSE
    task_arrival_multiplier: CapabilitySupport = CapabilitySupport.UNKNOWN
    workload_class_mix: CapabilitySupport = CapabilitySupport.UNKNOWN
    workload_ordering: CapabilitySupport = CapabilitySupport.UNKNOWN
    vehicle_count: CapabilitySupport = CapabilitySupport.UNKNOWN
    vehicle_tier_mix: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_count: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_capacity: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_placement: CapabilitySupport = CapabilitySupport.UNKNOWN
    rsu_failure: CapabilitySupport = CapabilitySupport.UNKNOWN
    action_toggles: CapabilitySupport = CapabilitySupport.UNKNOWN
    signal_timing: CapabilitySupport = CapabilitySupport.UNKNOWN
    lane_closure: CapabilitySupport = CapabilitySupport.UNKNOWN

    @field_validator("*", mode="before")
    @classmethod
    def validate_capability(cls, value: object) -> CapabilitySupport:
        return _coerce_capability(value)

    def as_manifest_dict(self) -> dict[str, bool | str]:
        """Return a serialisable dictionary using booleans and `unknown`."""

        return {key: getattr(self, key).to_manifest_value() for key in type(self).model_fields}


class CapabilityManifest(BaseModel):
    """Environment capability manifest."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    adapter: str = Field(min_length=1)
    supports: CapabilitySet = Field(default_factory=CapabilitySet)

    def as_manifest_dict(self) -> dict[str, dict[str, str | dict[str, bool | str]]]:
        """Return the documented manifest shape."""

        return {
            "environment": {
                "adapter": self.adapter,
                "supports": self.supports.as_manifest_dict(),
            }
        }


RANDY_ENVIRONMENT_CAPABILITIES = (
    "direct_launch",
    "asynchronous_launch",
    "task_arrival_multiplier",
    "workload_class_mix",
    "workload_ordering",
    "vehicle_count",
    "vehicle_tier_mix",
    "rsu_count",
    "rsu_capacity",
    "rsu_placement",
    "rsu_failure",
    "action_toggles",
    "signal_timing",
    "lane_closure",
)


def default_export_import_manifest() -> CapabilityManifest:
    """Return the safe default manifest for import/export-only work."""

    return CapabilityManifest(adapter="generic_csv")


def manifest_to_plain_dict(manifest: CapabilityManifest) -> dict[str, Any]:
    """Return a plain dictionary suitable for YAML dumping."""

    return manifest.as_manifest_dict()

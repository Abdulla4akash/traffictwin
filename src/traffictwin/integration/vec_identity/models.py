"""Strict models for occupancy-bounded VEC vehicle identity (VEC-03)."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from traffictwin.integration.tos.contract_v2 import (
    TOS_DATA_AUDITED_COMMIT,
    OccupancySpan,
)

VEC_IDENTITY_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class VecIdentityModel(BaseModel):
    """Strict, immutable and deterministically fingerprinted identity model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class VecIdentityFindingCode(StrEnum):
    """Stable failure codes for identity construction and use."""

    UPSTREAM_TRACE_INVALID = "upstream_trace_invalid"
    OCCUPANCY_INVALID = "occupancy_invalid"
    ACTIVE_CELL_WITHOUT_IDENTITY = "active_cell_without_identity"
    INACTIVE_CELL_WITH_IDENTITY = "inactive_cell_with_identity"
    TRACE_BINDING_MISMATCH = "trace_binding_mismatch"
    CELL_OUT_OF_RANGE = "cell_out_of_range"
    CELL_NOT_OCCUPIED = "cell_not_occupied"


class VecIdentityFinding(VecIdentityModel):
    code: VecIdentityFindingCode
    detail: str = Field(min_length=1, max_length=1_000)

    @field_validator("detail")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("detail must not contain control characters")
        return value


class VecIdentityCoverageReport(VecIdentityModel):
    """Complete reconciliation of occupancy identities against a trace mask."""

    schema_version: Literal["1.0"] = VEC_IDENTITY_SCHEMA_VERSION
    scenario: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    status: Literal["accepted", "rejected"]
    trace_steps: int = Field(ge=0)
    max_slots: int = Field(ge=0)
    span_count: int = Field(ge=0)
    distinct_vehicle_count: int = Field(ge=0)
    active_trace_cells: int = Field(ge=0)
    identity_cells: int = Field(ge=0)
    missing_identity_cells: int = Field(ge=0)
    inactive_identity_cells: int = Field(ge=0)
    trace_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    occupancy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    interval_semantics: Literal["inclusive"] = "inclusive"
    slot_semantics: Literal["reusable_not_vehicle_identity"] = "reusable_not_vehicle_identity"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    findings: tuple[VecIdentityFinding, ...] = ()

    @model_validator(mode="after")
    def reconcile_status(self) -> Self:
        accepted = (
            not self.findings
            and self.missing_identity_cells == 0
            and self.inactive_identity_cells == 0
            and self.active_trace_cells == self.identity_cells
        )
        if (self.status == "accepted") != accepted:
            raise ValueError("status must exactly reflect complete identity reconciliation")
        return self


class VecIdentitySnapshot(VecIdentityModel):
    """An exact, trace-bound span index safe for downstream joins."""

    report: VecIdentityCoverageReport
    spans: tuple[OccupancySpan, ...]

    @model_validator(mode="after")
    def require_accepted_report(self) -> Self:
        if self.report.status != "accepted":
            raise ValueError("an identity snapshot requires an accepted coverage report")
        if len(self.spans) != self.report.span_count:
            raise ValueError("snapshot span count must match its coverage report")
        if any(span.scenario != self.report.scenario for span in self.spans):
            raise ValueError("every span must match the report scenario")
        return self


class VecVehicleMobilityObservation(VecIdentityModel):
    """One mobility cell attributed only inside its audited occupancy span."""

    scenario: str
    time_index: int = Field(ge=0)
    trace_time_s: float
    slot: int = Field(ge=0)
    sumo_vehicle_id: str = Field(min_length=1, max_length=256)
    pos_x_m: float
    pos_y_m: float
    speed_mps: float = Field(ge=0)
    identity_semantics: Literal["occupancy_bounded_inclusive"] = "occupancy_bounded_inclusive"

    @model_validator(mode="after")
    def require_finite_values(self) -> Self:
        values = (self.trace_time_s, self.pos_x_m, self.pos_y_m, self.speed_mps)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("mobility values must be finite")
        return self


class VecIdentityContract(VecIdentityModel):
    """Public method boundary for VEC-03."""

    schema_version: Literal["1.0"] = VEC_IDENTITY_SCHEMA_VERSION
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    occupancy_header: tuple[str, str, str, str] = (
        "sumo_vehicle_id",
        "slot",
        "t_enter",
        "t_exit",
    )
    interval_semantics: Literal["inclusive"] = "inclusive"
    required_reconciliation: tuple[str, ...] = (
        "one identity for every active trace cell",
        "no identity for an inactive trace cell",
        "no overlapping slot spans",
        "no simultaneous multi-slot vehicle identity",
        "exact trace fingerprint before every join",
    )
    unavailable_claims: tuple[str, ...] = (
        "slot as persistent vehicle identity",
        "identity outside an admitted occupancy span",
        "filled or inferred vehicle identity",
    )


def vec_identity_contract() -> VecIdentityContract:
    """Return the frozen VEC-03 identity contract."""

    return VecIdentityContract()

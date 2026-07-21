"""Strict source-specific tripinfo join models (VEC-05)."""

from __future__ import annotations

import hashlib
import json
import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from traffictwin.integration.tos.contract_v2 import TOS_DATA_AUDITED_COMMIT


class VecTripModel(BaseModel):
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


class VecTripExclusionKind(StrEnum):
    RIGHT_CENSORED_AT_TRACE_BOUNDARY = "right_censored_at_trace_boundary"
    MISSING_BEFORE_TRACE_BOUNDARY = "missing_before_trace_boundary"


class VecMatchedTrip(VecTripModel):
    """One exact-ID occupancy vehicle with complete source tripinfo evidence."""

    scenario: str
    source_record: int = Field(ge=1)
    sumo_vehicle_id: str = Field(min_length=1, max_length=256)
    depart_s: float = Field(ge=0)
    arrival_s: float = Field(ge=0)
    duration_s: float = Field(ge=0)
    route_length_m: float = Field(ge=0)
    time_semantics: Literal["full_day_sumo_clock"] = "full_day_sumo_clock"
    eligibility: Literal["eligible_complete"] = "eligible_complete"

    @model_validator(mode="after")
    def validate_trip(self) -> Self:
        values = (self.depart_s, self.arrival_s, self.duration_s, self.route_length_m)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("trip values must be finite")
        if self.arrival_s < self.depart_s:
            raise ValueError("arrival must not precede departure")
        if not math.isclose(
            self.duration_s,
            self.arrival_s - self.depart_s,
            rel_tol=0,
            abs_tol=1e-6,
        ):
            raise ValueError("duration must equal arrival minus departure")
        return self


class VecTripExclusion(VecTripModel):
    """An occupancy vehicle with no exact tripinfo record and no filled values."""

    scenario: str
    sumo_vehicle_id: str = Field(min_length=1, max_length=256)
    kind: VecTripExclusionKind
    reason: str = Field(min_length=1, max_length=500)
    depart_s: Literal[None] = None
    arrival_s: Literal[None] = None
    duration_s: Literal[None] = None
    route_length_m: Literal[None] = None
    cause: Literal["unavailable"] = "unavailable"


class VecJourneyDurationSummary(VecTripModel):
    """Deterministic duration statistics over the exact matched cohort only."""

    eligible_count: int = Field(ge=1)
    mean_s: float = Field(ge=0)
    p50_s: float = Field(ge=0)
    p95_s: float = Field(ge=0)
    min_s: float = Field(ge=0)
    max_s: float = Field(ge=0)
    compatible_existing_metric_ids: tuple[str, ...] = (
        "trip.duration.count",
        "trip.duration.mean_s",
        "trip.duration.p50_s",
        "trip.duration.p95_s",
        "trip.duration.min_s",
        "trip.duration.max_s",
    )
    incompatible_existing_metric_ids: tuple[str, ...] = (
        "trip.records.count",
        "trip.completed.count",
        "trip.incomplete.count",
        "trip.completion.rate",
    )
    cohort_semantics: Literal["exact_id_matched_complete_occupancy_vehicles"] = (
        "exact_id_matched_complete_occupancy_vehicles"
    )

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if not self.min_s <= self.p50_s <= self.p95_s <= self.max_s:
            raise ValueError("duration statistics must be ordered")
        return self


class VecTripJoinReport(VecTripModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["accepted"] = "accepted"
    scenario: str
    source_path: str
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    identity_snapshot_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    compressed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    compressed_size_bytes: int = Field(ge=1)
    uncompressed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    uncompressed_size_bytes: int = Field(ge=1)
    source_trip_count: int = Field(ge=0)
    source_noncohort_trip_count: int = Field(ge=0)
    occupancy_vehicle_count: int = Field(ge=0)
    matched_vehicle_count: int = Field(ge=0)
    right_censored_count: int = Field(ge=0)
    missing_before_boundary_count: int = Field(ge=0)
    full_day_clock_preserved: Literal[True] = True
    raw_source_unchanged: Literal[True] = True
    duration_summary: VecJourneyDurationSummary

    @model_validator(mode="after")
    def reconcile_counts(self) -> Self:
        excluded = self.right_censored_count + self.missing_before_boundary_count
        if self.matched_vehicle_count + excluded != self.occupancy_vehicle_count:
            raise ValueError("matched and excluded vehicles must reconcile to occupancy")
        if self.matched_vehicle_count + self.source_noncohort_trip_count != self.source_trip_count:
            raise ValueError("matched and non-cohort trips must reconcile to source trips")
        if self.duration_summary.eligible_count != self.matched_vehicle_count:
            raise ValueError("duration cohort must equal matched vehicle count")
        return self


class VecTripJoinDataset(VecTripModel):
    report: VecTripJoinReport
    matched: tuple[VecMatchedTrip, ...]
    exclusions: tuple[VecTripExclusion, ...]

    @model_validator(mode="after")
    def reconcile_rows(self) -> Self:
        if len(self.matched) != self.report.matched_vehicle_count:
            raise ValueError("matched rows must reconcile to the report")
        if len(self.exclusions) != (
            self.report.right_censored_count + self.report.missing_before_boundary_count
        ):
            raise ValueError("exclusion rows must reconcile to the report")
        return self


class VecTripJoinContract(VecTripModel):
    schema_version: Literal["1.0"] = "1.0"
    source_commit: str = Field(default=TOS_DATA_AUDITED_COMMIT, pattern=r"^[0-9a-f]{40}$")
    join_key: Literal["exact_sumo_vehicle_id"] = "exact_sumo_vehicle_id"
    source_clock: Literal["full_day_sumo_seconds_preserved"] = "full_day_sumo_seconds_preserved"
    maximum_compressed_bytes: int = 20_000_000
    maximum_uncompressed_bytes: int = 32_000_000
    metric_boundary: str = (
        "Only duration statistics over exact-ID matched complete trips are compatible with the "
        "existing trip.duration.* definitions; completion metrics are cohort-incompatible."
    )
    unavailable_claims: tuple[str, ...] = (
        "filled trip values for excluded vehicles",
        "cause of a missing trip record",
        "completion rate over the full occupancy cohort",
        "clock alignment inferred between tripinfo and trace-relative indices",
    )


def vec_trip_join_contract() -> VecTripJoinContract:
    return VecTripJoinContract()

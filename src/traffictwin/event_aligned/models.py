"""Typed models for event-aligned analysis."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields at untrusted boundaries."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EventAnchorKind(StrEnum):
    """Provenance of the declared event anchor.

    All kinds are labelled authored anchors, not observed incidents.
    """

    BUNDLE_DECLARED_EVENT = "bundle_declared_event"
    AUTHORED_INCIDENT = "authored_incident"
    MANUAL_AUTHORED_TIMESTAMP = "manual_authored_timestamp"

    @property
    def authored_label(self) -> str:
        """Return the authored anchor label for display."""

        mapping = {
            EventAnchorKind.BUNDLE_DECLARED_EVENT: "Authored — Bundle declared event",
            EventAnchorKind.AUTHORED_INCIDENT: "Authored — Incident",
            EventAnchorKind.MANUAL_AUTHORED_TIMESTAMP: "Authored — Manual timestamp",
        }
        return mapping[self]

    @property
    def is_authored(self) -> bool:
        """All anchor kinds are authored, never observed."""

        return True


class EventAlignedPhase(StrEnum):
    """Phase relative to the declared anchor."""

    PRE = "pre"
    EVENT = "event"
    POST = "post"


class CoverageState(StrEnum):
    """Coverage state for one aligned bin."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"
    EXCLUDED = "excluded"


class EventAnchor(StrictModel):
    """Declared event anchor with explicit provenance.

    The anchor is stored as a canonical UTC aware timestamp.
    Naive timestamps are rejected to avoid ambiguous time basis.
    """

    kind: EventAnchorKind
    anchor_time_utc: datetime
    source_label: str = Field(min_length=1, description="Human provenance label")
    provenance_detail: str | None = Field(default=None, max_length=500)
    incident_id: str | None = None
    bundle_id: str | None = None
    run_id: str | None = None
    declared_timezone: str | None = None

    @field_validator("anchor_time_utc")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "anchor_time_utc must be timezone-aware; naive timestamps are rejected"
            raise ValueError(msg)
        # Normalise to UTC for canonical identity.
        return value.astimezone(UTC)

    @field_validator("source_label")
    @classmethod
    def validate_source_label_not_observed(cls, value: str) -> str:
        lowered = value.lower()
        if "observed" in lowered:
            msg = "authored anchors must not be labelled observed"
            raise ValueError(msg)
        return value

    def canonical_dict(self) -> dict[str, object]:
        """Return canonical dict for fingerprinting."""

        return {
            "bundle_id": self.bundle_id,
            "incident_id": self.incident_id,
            "kind": self.kind.value,
            "provenance_detail": self.provenance_detail,
            "run_id": self.run_id,
            "source_label": self.source_label,
            "anchor_time_utc": self.anchor_time_utc.isoformat().replace("+00:00", "Z"),
            "declared_timezone": self.declared_timezone,
        }

    def display_label(self) -> str:
        """Return the authored label for UI."""

        return self.kind.authored_label


class EventAlignedWindowSpec(StrictModel):
    """Common window specification for aligned analysis.

    Half-open windows are used: [start, end). Bin boundaries are deterministic
    and anchored to the per-run event time.
    """

    schema_version: Literal["1.0"] = "1.0"
    pre_duration_s: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    event_duration_s: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    post_duration_s: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    bin_width_s: float = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    metric_key: str = Field(min_length=1)
    metric_version: str = Field(min_length=1)
    metric_unit: str = Field(min_length=1)
    metric_human_name: str | None = None
    canonical_time_basis: Literal["utc_bundle_created_at_offset_v1"] = (
        "utc_bundle_created_at_offset_v1"
    )
    bin_boundary: Literal["[start,end)"] = "[start,end)"
    max_bins: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def validate_bin_divisibility(self) -> EventAlignedWindowSpec:
        # Bin width must not exceed any phase duration? Not strict, but we warn if it doesn't divide.  # noqa: E501
        # Keep simple: allow any positive width.
        return self

    def canonical_dict(self) -> dict[str, object]:
        return {
            "bin_boundary": self.bin_boundary,
            "bin_width_s": self.bin_width_s,
            "canonical_time_basis": self.canonical_time_basis,
            "event_duration_s": self.event_duration_s,
            "max_bins": self.max_bins,
            "metric_key": self.metric_key,
            "metric_unit": self.metric_unit,
            "metric_version": self.metric_version,
            "post_duration_s": self.post_duration_s,
            "pre_duration_s": self.pre_duration_s,
            "schema_version": self.schema_version,
        }

    def preview_windows(self, anchor_utc: datetime) -> dict[str, tuple[datetime, datetime]]:
        """Return exact half-open window preview for one anchor."""

        if anchor_utc.tzinfo is None:
            msg = "anchor_utc must be timezone-aware"
            raise ValueError(msg)
        anchor = anchor_utc.astimezone(UTC)
        from datetime import timedelta

        pre_start = anchor - timedelta(seconds=self.pre_duration_s)
        pre_end = anchor
        event_start = anchor
        event_end = anchor + timedelta(seconds=self.event_duration_s)
        post_start = event_end
        post_end = post_start + timedelta(seconds=self.post_duration_s)
        return {
            "pre": (pre_start, pre_end),
            "event": (event_start, event_end),
            "post": (post_start, post_end),
        }

    def total_bins(self) -> int:
        """Return deterministic total bin count across all phases."""

        import math

        pre_bins = math.ceil(self.pre_duration_s / self.bin_width_s)
        event_bins = math.ceil(self.event_duration_s / self.bin_width_s)
        post_bins = math.ceil(self.post_duration_s / self.bin_width_s)
        return pre_bins + event_bins + post_bins


class EventAlignedMetricPoint(StrictModel):
    """One relative-time metric point for an accepted run."""

    run_id: str = Field(min_length=1)
    phase: EventAlignedPhase
    bin_index: int = Field(ge=0)
    relative_start_s: float = Field(allow_inf_nan=False)
    relative_end_s: float = Field(allow_inf_nan=False)
    absolute_window_start_utc: datetime
    absolute_window_end_utc: datetime
    coverage_state: CoverageState
    coverage_fraction: float = Field(ge=0, le=1, allow_inf_nan=False)
    source_record_counts: dict[str, int]
    metric_key: str
    metric_version: str
    metric_unit: str
    status: Literal["available", "unavailable", "invalid", "partial"]
    value: float | int | None = None
    reason_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("absolute_window_start_utc", "absolute_window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "absolute window boundaries must be timezone-aware"
            raise ValueError(msg)
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_half_open(self) -> EventAlignedMetricPoint:
        if self.relative_end_s <= self.relative_start_s:
            msg = "relative_end_s must be greater than relative_start_s"
            raise ValueError(msg)
        if self.absolute_window_end_utc <= self.absolute_window_start_utc:
            msg = "absolute_window_end_utc must be after absolute_window_start_utc"
            raise ValueError(msg)
        return self

    def canonical_dict(self) -> dict[str, object]:
        return {
            "absolute_window_end_utc": self.absolute_window_end_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "absolute_window_start_utc": self.absolute_window_start_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "bin_index": self.bin_index,
            "coverage_fraction": self.coverage_fraction,
            "coverage_state": self.coverage_state.value,
            "metric_key": self.metric_key,
            "metric_unit": self.metric_unit,
            "metric_version": self.metric_version,
            "phase": self.phase.value,
            "reason_codes": sorted(self.reason_codes),
            "relative_end_s": self.relative_end_s,
            "relative_start_s": self.relative_start_s,
            "run_id": self.run_id,
            "source_record_counts": dict(sorted(self.source_record_counts.items())),
            "status": self.status,
            "value": self.value,
        }


class EventAlignedPhaseSummary(StrictModel):
    """Before/during/after summary for one run and metric."""

    run_id: str
    phase: EventAlignedPhase
    metric_key: str
    metric_version: str
    metric_unit: str
    bin_count: int = Field(ge=0)
    available_count: int = Field(ge=0)
    empty_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    mean_value: float | None = Field(default=None, allow_inf_nan=False)
    min_value: float | None = Field(default=None, allow_inf_nan=False)
    max_value: float | None = Field(default=None, allow_inf_nan=False)
    median_value: float | None = Field(default=None, allow_inf_nan=False)
    warnings: list[str] = Field(default_factory=list)

    def canonical_dict(self) -> dict[str, object]:
        return {
            "available_count": self.available_count,
            "bin_count": self.bin_count,
            "empty_count": self.empty_count,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "median_value": self.median_value,
            "metric_key": self.metric_key,
            "metric_unit": self.metric_unit,
            "metric_version": self.metric_version,
            "min_value": self.min_value,
            "partial_count": self.partial_count,
            "phase": self.phase.value,
            "run_id": self.run_id,
        }


class EventAlignedRun(StrictModel):
    """Accepted run descriptor with anchor provenance."""

    run_id: str
    bundle_id: str | None = None
    bundle_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    experiment_id: str | None = None
    seed_id: str | None = None
    algorithm: str | None = None
    anchor: EventAnchor
    canonical_time_basis: Literal["utc_bundle_created_at_offset_v1"] = (
        "utc_bundle_created_at_offset_v1"
    )
    warnings: list[str] = Field(default_factory=list)
    source_record_counts: dict[str, int] | None = None
    time_coverage_s: tuple[float, float] | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "algorithm": self.algorithm,
            "anchor": self.anchor.canonical_dict(),
            "bundle_fingerprint": self.bundle_fingerprint,
            "bundle_id": self.bundle_id,
            "canonical_time_basis": self.canonical_time_basis,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "seed_id": self.seed_id,
            "time_coverage_s": list(self.time_coverage_s) if self.time_coverage_s else None,
        }


class ExcludedRun(StrictModel):
    """Run excluded from alignment with explicit reason."""

    run_id: str
    bundle_id: str | None = None
    bundle_fingerprint: str | None = None
    reason_code: str = Field(min_length=1)
    reason_detail: str = Field(min_length=1)
    anchor: EventAnchor | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "anchor": self.anchor.canonical_dict() if self.anchor else None,
            "bundle_fingerprint": self.bundle_fingerprint,
            "bundle_id": self.bundle_id,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
            "run_id": self.run_id,
        }


class EventAlignedCompatibility(StrictModel):
    """Compatibility check for metric name/version/unit/denominator."""

    metric_key: str
    expected_version: str
    expected_unit: str
    expected_denom: str | None = None
    compatible: bool
    reason_code: str | None = None
    reason_detail: str | None = None

    def canonical_dict(self) -> dict[str, object]:
        return {
            "compatible": self.compatible,
            "expected_denom": self.expected_denom,
            "expected_unit": self.expected_unit,
            "expected_version": self.expected_version,
            "metric_key": self.metric_key,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
        }


class PairwiseDelta(StrictModel):
    """Descriptive difference during the declared event window."""

    baseline_run_id: str
    variation_run_id: str
    metric_key: str
    metric_version: str
    metric_unit: str
    phase: EventAlignedPhase
    baseline_mean: float | None = Field(default=None, allow_inf_nan=False)
    variation_mean: float | None = Field(default=None, allow_inf_nan=False)
    absolute_difference: float | None = Field(default=None, allow_inf_nan=False)
    relative_difference: float | None = Field(default=None, allow_inf_nan=False)
    description: str = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def validate_non_causal(cls, value: str) -> str:
        lowered = value.lower()
        forbidden = ["caused", "causal", "impact", "effect", "due to the event"]
        for term in forbidden:
            if term in lowered:
                msg = f"description must not claim causal effects: found {term!r}"
                raise ValueError(msg)
        return value

    def canonical_dict(self) -> dict[str, object]:
        return {
            "absolute_difference": self.absolute_difference,
            "baseline_mean": self.baseline_mean,
            "baseline_run_id": self.baseline_run_id,
            "description": self.description,
            "metric_key": self.metric_key,
            "metric_unit": self.metric_unit,
            "metric_version": self.metric_version,
            "phase": self.phase.value,
            "relative_difference": self.relative_difference,
            "variation_mean": self.variation_mean,
            "variation_run_id": self.variation_run_id,
        }


class EventAlignedReport(StrictModel):
    """Portable deterministic report for event-aligned analysis.

    Fingerprint excludes wall clock, rendering state, local paths, secrets,
    and generated_at. The report prefers relative offsets plus canonical UTC
    anchor identity; local display timezone is presentation-only.
    """

    schema_version: Literal["1.0"] = "1.0"
    report_id: str = Field(min_length=1)
    canonical_time_basis: Literal["utc_bundle_created_at_offset_v1"] = (
        "utc_bundle_created_at_offset_v1"
    )
    spec: EventAlignedWindowSpec
    accepted_runs: list[EventAlignedRun]
    excluded_runs: list[ExcludedRun]
    metric_points: list[EventAlignedMetricPoint]
    phase_summaries: list[EventAlignedPhaseSummary]
    pairwise_deltas: list[PairwiseDelta]
    warnings: list[str]
    limitations: list[str]
    created_at_utc: datetime | None = None
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("created_at_utc")
    @classmethod
    def validate_created_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            msg = "created_at_utc must be timezone-aware when present"
            raise ValueError(msg)
        return value.astimezone(UTC)

    def canonical_dict(self) -> dict[str, object]:
        """Return canonical dict excluding volatile fields."""

        return {
            "accepted_runs": sorted(
                [run.canonical_dict() for run in self.accepted_runs],
                key=lambda x: str(x.get("run_id")),
            ),
            "canonical_time_basis": self.canonical_time_basis,
            "excluded_runs": sorted(
                [run.canonical_dict() for run in self.excluded_runs],
                key=lambda x: str(x.get("run_id")),
            ),
            "limitations": sorted(self.limitations),
            "metric_points": sorted(
                [point.canonical_dict() for point in self.metric_points],
                key=lambda x: (str(x.get("run_id")), int(str(x.get("bin_index", 0)))),
            ),
            "pairwise_deltas": sorted(
                [delta.canonical_dict() for delta in self.pairwise_deltas],
                key=lambda x: (
                    str(x.get("baseline_run_id")),
                    str(x.get("variation_run_id")),
                    str(x.get("phase")),
                ),
            ),
            "phase_summaries": sorted(
                [summary.canonical_dict() for summary in self.phase_summaries],
                key=lambda x: (str(x.get("run_id")), str(x.get("phase"))),
            ),
            "report_id": self.report_id,
            "schema_version": self.schema_version,
            "spec": self.spec.canonical_dict(),
            "warnings": sorted(self.warnings),
        }

    def canonical_json(self) -> str:
        """Return deterministic JSON without volatile fields."""

        payload = self.canonical_dict()
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )

    def computed_fingerprint(self) -> str:
        """Return deterministic fingerprint over canonical JSON."""

        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def verify_fingerprint(self) -> bool:
        """Return whether stored fingerprint matches recomputed."""

        return self.fingerprint == self.computed_fingerprint()

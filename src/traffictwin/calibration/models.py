"""Strict typed models for Observed-to-Simulation Calibration Workbench.

Portable identity excludes wall clock, local paths, and secrets.
All models use extra="forbid" and are immutable where appropriate.
Fingerprinting uses deterministic canonical JSON with sorted keys.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class FrozenStrictModel(BaseModel):
    """Immutable strict model."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        validate_assignment=True,
        frozen=True,
        str_strip_whitespace=True,
    )


_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,63}$")
_METRIC_KEY_RE = re.compile(r"^[a-z][a-z0-9_\.\-]{0,127}$")


def _validate_identifier(value: str, label: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{label} must be non-empty")
    v = value.strip()
    if not _IDENTIFIER_RE.fullmatch(v):
        raise ValueError(f"{label} must match identifier pattern {_IDENTIFIER_RE.pattern}")
    return v


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CalibrationStatus(StrEnum):
    """Calibration availability status for a candidate."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    EXCLUDED = "excluded"


class Direction(StrEnum):
    """Declared optimisation direction for a metric."""

    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    NEUTRAL = "neutral"


class MissingnessPolicy(StrEnum):
    """How missing evidence is handled — never zero-filled."""

    EXCLUDE_BIN = "exclude_bin"
    UNAVAILABLE_OBJECTIVE = "unavailable_objective"


class ExclusionReasonCode(StrEnum):
    """Stable exclusion reason codes."""

    UNIT_MISMATCH = "UNIT_MISMATCH"
    TEMPORAL_MISALIGNMENT = "TEMPORAL_MISALIGNMENT"
    SENSOR_MAPPING_INCOMPLETE = "SENSOR_MAPPING_INCOMPLETE"
    COVERAGE_INSUFFICIENT = "COVERAGE_INSUFFICIENT"
    MISSING_REQUIRED_METRIC = "MISSING_REQUIRED_METRIC"
    INSUFFICIENT_PAIRED_BINS = "INSUFFICIENT_PAIRED_BINS"
    METRIC_NOT_FOUND = "METRIC_NOT_FOUND"


# ---------------------------------------------------------------------------
# Metric spec
# ---------------------------------------------------------------------------


class CalibrationMetricSpec(FrozenStrictModel):
    """Declarative spec for one calibration metric."""

    metric_key: str = Field(min_length=1, max_length=128)
    metric_version: str = Field(min_length=1, max_length=32)
    unit: str = Field(min_length=1, max_length=64)
    denominator: str | None = Field(default=None, max_length=128)
    direction: Direction = Direction.LOWER_IS_BETTER
    weight: float = Field(ge=0, le=10, allow_inf_nan=False)
    alignment_required: bool = True
    missingness_policy: MissingnessPolicy = MissingnessPolicy.EXCLUDE_BIN

    @field_validator("metric_key")
    @classmethod
    def validate_metric_key(cls, value: str) -> str:
        v = value.strip()
        if not _METRIC_KEY_RE.fullmatch(v):
            raise ValueError("metric_key must be lower-case with dots/underscores/hyphens")
        return v

    @field_validator("unit", "metric_version", "denominator")
    @classmethod
    def validate_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("unit/metric_version/denominator must be non-empty when provided")
        return value.strip()

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "alignment_required": self.alignment_required,
            "denominator": self.denominator,
            "direction": self.direction.value,
            "metric_key": self.metric_key,
            "metric_version": self.metric_version,
            "missingness_policy": self.missingness_policy.value,
            "unit": self.unit,
            "weight": self.weight,
        }


# ---------------------------------------------------------------------------
# Alignment spec
# ---------------------------------------------------------------------------


class CalibrationAlignmentSpec(FrozenStrictModel):
    """Alignment contract for the calibration study."""

    window_start_utc: datetime
    window_end_utc: datetime
    bin_width_s: float = Field(gt=0, le=86400 * 30, allow_inf_nan=False)
    window_semantics: Literal["[start,end)"] = "[start,end)"
    temporal_tolerance_s: float = Field(default=0.0, ge=0, le=3600, allow_inf_nan=False)
    sensor_mapping: dict[str, str] = Field(default_factory=dict)
    coverage_threshold: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    max_bins: int = Field(default=10000, ge=1, le=100000)

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("window boundaries must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_window(self) -> CalibrationAlignmentSpec:
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("window_end_utc must be after window_start_utc")
        # sensor_mapping keys/values must be non-empty identifiers
        for k, v in self.sensor_mapping.items():
            if not k.strip() or not v.strip():
                raise ValueError("sensor_mapping keys and values must be non-empty")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "bin_width_s": self.bin_width_s,
            "coverage_threshold": self.coverage_threshold,
            "max_bins": self.max_bins,
            "sensor_mapping": dict(sorted(self.sensor_mapping.items())),
            "temporal_tolerance_s": self.temporal_tolerance_s,
            "window_end_utc": self.window_end_utc.isoformat().replace("+00:00", "Z"),
            "window_semantics": self.window_semantics,
            "window_start_utc": self.window_start_utc.isoformat().replace("+00:00", "Z"),
        }

    def total_bins(self) -> int:
        import math

        duration = (self.window_end_utc - self.window_start_utc).total_seconds()
        return math.ceil(duration / self.bin_width_s)


# ---------------------------------------------------------------------------
# Bin
# ---------------------------------------------------------------------------


class CalibrationBin(FrozenStrictModel):
    """One windowed observation for a sensor/metric."""

    sensor_id: str = Field(min_length=1, max_length=128)
    window_index: int = Field(ge=0)
    window_start_utc: datetime
    window_end_utc: datetime
    metric_key: str = Field(min_length=1, max_length=128)
    value: float | None = Field(default=None, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=64)

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("bin window boundaries must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("sensor_id", "metric_key", "unit")
    @classmethod
    def validate_strip(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must be non-empty")
        return value.strip()

    @model_validator(mode="after")
    def validate_half_open(self) -> CalibrationBin:
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("window_end must be after window_start")
        if "observed" in self.sensor_id.lower():
            # sensor_id is just an identifier; allow observed prefix but not label
            pass
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "sensor_id": self.sensor_id,
            "unit": self.unit,
            "value": self.value,
            "window_end_utc": self.window_end_utc.isoformat().replace("+00:00", "Z"),
            "window_index": self.window_index,
            "window_start_utc": self.window_start_utc.isoformat().replace("+00:00", "Z"),
        }


# ---------------------------------------------------------------------------
# Observed reference
# ---------------------------------------------------------------------------


class CalibrationObservedReference(FrozenStrictModel):
    """Admitted observed evidence reference bound by fingerprint."""

    observed_id: str = Field(min_length=1, max_length=128)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_label: str = Field(min_length=1, max_length=512)
    window_start_utc: datetime
    window_end_utc: datetime
    bin_width_s: float = Field(gt=0, le=86400 * 30, allow_inf_nan=False)
    sensor_ids: list[str] = Field(min_length=1)
    metric_units: dict[str, str] = Field(default_factory=dict)
    bins: list[CalibrationBin] = Field(default_factory=list)

    @field_validator("observed_id")
    @classmethod
    def validate_observed_id(cls, value: str) -> str:
        return _validate_identifier(value.strip(), "observed_id")

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed window boundaries must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("sensor_ids")
    @classmethod
    def validate_sensor_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sensor_ids must be non-empty")
        cleaned = [v.strip() for v in value]
        for v in cleaned:
            if not v:
                raise ValueError("sensor_id must be non-empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("sensor_ids must be unique")
        return sorted(cleaned)

    @model_validator(mode="after")
    def validate_window_and_bins(self) -> CalibrationObservedReference:
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("observed window_end must be after window_start")
        # bins must be within window and half-open aligned
        for b in self.bins:
            if b.sensor_id not in self.sensor_ids:
                raise ValueError(f"bin sensor_id {b.sensor_id!r} not in sensor_ids")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "bin_width_s": self.bin_width_s,
            "bins": sorted(
                [b.canonical_dict() for b in self.bins],
                key=lambda x: (x["sensor_id"], x["window_index"], x["metric_key"]),
            ),
            "evidence_label": self.evidence_label,
            "fingerprint": self.fingerprint,
            "metric_units": dict(sorted(self.metric_units.items())),
            "observed_id": self.observed_id,
            "sensor_ids": sorted(self.sensor_ids),
            "window_end_utc": self.window_end_utc.isoformat().replace("+00:00", "Z"),
            "window_start_utc": self.window_start_utc.isoformat().replace("+00:00", "Z"),
        }


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


class CalibrationCandidate(FrozenStrictModel):
    """One simulation candidate bound by fingerprint."""

    candidate_id: str = Field(min_length=1, max_length=128)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: str = Field(min_length=1, max_length=256)
    window_start_utc: datetime
    window_end_utc: datetime
    bin_width_s: float = Field(gt=0, le=86400 * 30, allow_inf_nan=False)
    sensor_ids: list[str] = Field(min_length=1)
    metric_units: dict[str, str] = Field(default_factory=dict)
    bins: list[CalibrationBin] = Field(default_factory=list)

    @field_validator("candidate_id")
    @classmethod
    def validate_candidate_id(cls, value: str) -> str:
        return _validate_identifier(value.strip(), "candidate_id")

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("candidate window boundaries must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("sensor_ids")
    @classmethod
    def validate_sensor_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sensor_ids must be non-empty")
        cleaned = [v.strip() for v in value]
        for v in cleaned:
            if not v:
                raise ValueError("sensor_id must be non-empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("sensor_ids must be unique")
        return sorted(cleaned)

    @model_validator(mode="after")
    def validate_window(self) -> CalibrationCandidate:
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("candidate window_end must be after window_start")
        for b in self.bins:
            if b.sensor_id not in self.sensor_ids:
                raise ValueError(f"bin sensor_id {b.sensor_id!r} not in sensor_ids")
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "bins": sorted(
                [b.canonical_dict() for b in self.bins],
                key=lambda x: (x["sensor_id"], x["window_index"], x["metric_key"]),
            ),
            "bin_width_s": self.bin_width_s,
            "candidate_id": self.candidate_id,
            "fingerprint": self.fingerprint,
            "label": self.label,
            "metric_units": dict(sorted(self.metric_units.items())),
            "sensor_ids": sorted(self.sensor_ids),
            "window_end_utc": self.window_end_utc.isoformat().replace("+00:00", "Z"),
            "window_start_utc": self.window_start_utc.isoformat().replace("+00:00", "Z"),
        }


# ---------------------------------------------------------------------------
# Study
# ---------------------------------------------------------------------------


class CalibrationStudy(FrozenStrictModel):
    """Complete calibration study inputs."""

    study_id: str = Field(min_length=1, max_length=128)
    study_name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    observed: CalibrationObservedReference
    candidates: list[CalibrationCandidate] = Field(min_length=1, max_length=32)
    metric_specs: list[CalibrationMetricSpec] = Field(min_length=1, max_length=16)
    alignment_spec: CalibrationAlignmentSpec

    @field_validator("study_id")
    @classmethod
    def validate_study_id(cls, value: str) -> str:
        return _validate_identifier(value.strip(), "study_id")

    @model_validator(mode="after")
    def validate_study(self) -> CalibrationStudy:
        # candidate ids unique
        ids = [c.candidate_id for c in self.candidates]
        if len(set(ids)) != len(ids):
            raise ValueError("candidate_id must be unique within study")
        keys = [m.metric_key for m in self.metric_specs]
        if len(set(keys)) != len(keys):
            raise ValueError("metric_key must be unique within metric_specs")
        # fingerprint binding: observed and candidates must have fingerprints
        # alignment window should match observed window within tolerance or study is still buildable but audit will exclude  # noqa: E501
        return self

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "alignment_spec": self.alignment_spec.canonical_dict(),
            "candidates": sorted(
                [c.canonical_dict() for c in self.candidates],
                key=lambda x: x["candidate_id"],
            ),
            "description": self.description,
            "metric_specs": sorted(
                [m.canonical_dict() for m in self.metric_specs],
                key=lambda x: x["metric_key"],
            ),
            "observed": self.observed.canonical_dict(),
            "study_id": self.study_id,
            "study_name": self.study_name,
        }


# ---------------------------------------------------------------------------
# Alignment audit
# ---------------------------------------------------------------------------


class CalibrationAlignmentAudit(FrozenStrictModel):
    """Alignment and coverage audit for one candidate."""

    candidate_id: str
    temporal_aligned: bool
    temporal_reason: str | None = None
    unit_compatible: bool
    unit_mismatches: list[str] = Field(default_factory=list)
    sensor_mapping_complete: bool
    missing_sensor_ids: list[str] = Field(default_factory=list)
    coverage_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    total_bins: int = Field(ge=0)
    available_bins: int = Field(ge=0)
    missing_bins: int = Field(ge=0)
    is_excluded: bool
    exclusion_reason_code: str | None = None
    exclusion_detail: str | None = None

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "available_bins": self.available_bins,
            "candidate_id": self.candidate_id,
            "coverage_percentage": self.coverage_percentage,
            "exclusion_detail": self.exclusion_detail,
            "exclusion_reason_code": self.exclusion_reason_code,
            "is_excluded": self.is_excluded,
            "missing_bins": self.missing_bins,
            "missing_sensor_ids": sorted(self.missing_sensor_ids),
            "sensor_mapping_complete": self.sensor_mapping_complete,
            "temporal_aligned": self.temporal_aligned,
            "temporal_reason": self.temporal_reason,
            "total_bins": self.total_bins,
            "unit_compatible": self.unit_compatible,
            "unit_mismatches": sorted(self.unit_mismatches),
        }


# ---------------------------------------------------------------------------
# Metric result & residual
# ---------------------------------------------------------------------------


class CalibrationMetricResult(FrozenStrictModel):
    """Descriptive fit for one metric and one candidate."""

    metric_key: str
    metric_version: str
    unit: str
    count_paired: int = Field(ge=0)
    count_missing_observed: int = Field(ge=0)
    count_missing_simulation: int = Field(ge=0)
    mae: float | None = Field(default=None, allow_inf_nan=False)
    rmse: float | None = Field(default=None, allow_inf_nan=False)
    mean_signed_error: float | None = Field(default=None, allow_inf_nan=False)
    relative_error_mean: float | None = Field(default=None, allow_inf_nan=False)
    coverage_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    is_available: bool

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "count_missing_observed": self.count_missing_observed,
            "count_missing_simulation": self.count_missing_simulation,
            "count_paired": self.count_paired,
            "coverage_percentage": self.coverage_percentage,
            "is_available": self.is_available,
            "mae": self.mae,
            "mean_signed_error": self.mean_signed_error,
            "metric_key": self.metric_key,
            "metric_version": self.metric_version,
            "relative_error_mean": self.relative_error_mean,
            "rmse": self.rmse,
            "unit": self.unit,
        }


class CalibrationResidual(FrozenStrictModel):
    """Per-window, per-sensor residual."""

    sensor_id: str
    window_index: int = Field(ge=0)
    window_start_utc: datetime
    window_end_utc: datetime
    metric_key: str
    observed_value: float | None = Field(default=None, allow_inf_nan=False)
    simulated_value: float | None = Field(default=None, allow_inf_nan=False)
    signed_error: float | None = Field(default=None, allow_inf_nan=False)
    absolute_error: float | None = Field(default=None, allow_inf_nan=False)
    relative_error: float | None = Field(default=None, allow_inf_nan=False)

    @field_validator("window_start_utc", "window_end_utc")
    @classmethod
    def validate_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("residual window must be timezone-aware")
        return value.astimezone(UTC)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "absolute_error": self.absolute_error,
            "metric_key": self.metric_key,
            "observed_value": self.observed_value,
            "relative_error": self.relative_error,
            "sensor_id": self.sensor_id,
            "signed_error": self.signed_error,
            "simulated_value": self.simulated_value,
            "window_end_utc": self.window_end_utc.isoformat().replace("+00:00", "Z"),
            "window_index": self.window_index,
            "window_start_utc": self.window_start_utc.isoformat().replace("+00:00", "Z"),
        }


# ---------------------------------------------------------------------------
# Exclusion & Candidate Summary & Report
# ---------------------------------------------------------------------------


class CalibrationExclusion(FrozenStrictModel):
    """Exclusion record for a candidate."""

    candidate_id: str
    reason_code: str = Field(min_length=1, max_length=64)
    reason_detail: str = Field(min_length=1, max_length=1024)
    failing_metric: str | None = Field(default=None, max_length=128)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "failing_metric": self.failing_metric,
            "reason_code": self.reason_code,
            "reason_detail": self.reason_detail,
        }


class CalibrationCandidateSummary(FrozenStrictModel):
    """Summary for one candidate within a report."""

    candidate_id: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    label: str
    status: CalibrationStatus
    alignment_audit: CalibrationAlignmentAudit
    metric_results: list[CalibrationMetricResult] = Field(default_factory=list)
    residuals: list[CalibrationResidual] = Field(default_factory=list)
    coverage_percentage: float = Field(ge=0, le=100, allow_inf_nan=False)
    weighted_objective: float | None = Field(default=None, allow_inf_nan=False)
    exclusion: CalibrationExclusion | None = None

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "alignment_audit": self.alignment_audit.canonical_dict(),
            "candidate_id": self.candidate_id,
            "coverage_percentage": self.coverage_percentage,
            "exclusion": self.exclusion.canonical_dict() if self.exclusion else None,
            "fingerprint": self.fingerprint,
            "label": self.label,
            "metric_results": sorted(
                [m.canonical_dict() for m in self.metric_results],
                key=lambda x: x["metric_key"],
            ),
            "residuals": sorted(
                [r.canonical_dict() for r in self.residuals],
                key=lambda x: (x["sensor_id"], x["window_index"], x["metric_key"]),
            ),
            "status": self.status.value,
            "weighted_objective": self.weighted_objective,
        }


class CalibrationReport(FrozenStrictModel):
    """Deterministic calibration report — descriptive only, not validation."""

    report_id: str = Field(min_length=1, max_length=128)
    study_id: str = Field(min_length=1, max_length=128)
    study_name: str = Field(min_length=1, max_length=256)
    observed_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_fingerprints: list[str] = Field(default_factory=list)
    metric_specs: list[CalibrationMetricSpec] = Field(default_factory=list)
    alignment_spec: CalibrationAlignmentSpec
    candidate_summaries: list[CalibrationCandidateSummary] = Field(default_factory=list)
    exclusions: list[CalibrationExclusion] = Field(default_factory=list)
    ranking: list[str] = Field(default_factory=list)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    limitations: list[str] = Field(default_factory=list)
    evidence_boundary: str = Field(min_length=1, max_length=1024)

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "alignment_spec": self.alignment_spec.canonical_dict(),
            "candidate_fingerprints": sorted(self.candidate_fingerprints),
            "candidate_summaries": sorted(
                [c.canonical_dict() for c in self.candidate_summaries],
                key=lambda x: x["candidate_id"],
            ),
            "evidence_boundary": self.evidence_boundary,
            "exclusions": sorted(
                [e.canonical_dict() for e in self.exclusions],
                key=lambda x: x["candidate_id"],
            ),
            "limitations": sorted(self.limitations),
            "metric_specs": sorted(
                [m.canonical_dict() for m in self.metric_specs],
                key=lambda x: x["metric_key"],
            ),
            "observed_fingerprint": self.observed_fingerprint,
            "ranking": list(self.ranking),
            "report_id": self.report_id,
            "study_id": self.study_id,
            "study_name": self.study_name,
        }

    def to_canonical_bytes(self) -> bytes:
        payload = self.canonical_dict()
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")

    def to_canonical_json(self) -> str:
        return json.dumps(
            self.canonical_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            indent=2,
        )


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_for_canonical(value: dict[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(value))

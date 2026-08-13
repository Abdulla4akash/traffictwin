"""Transparent, typed data-quality and coverage diagnostics.

The diagnostics are pure, offline, and deterministic. They report only
precisely defined quantities from explicit typed inputs: missingness,
duplicate rate, interval gaps, spatial coverage, timestamp range,
freshness delay, rejected-row counts, parser warnings, row counts and
explicit limitations. No composite or scientific quality score is
computed or implied.

No network access, filesystem discovery, credential probing, or private
persistence is performed. All free-text values are screened for secret
values and private absolute paths.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Self

from pydantic import Field, field_validator, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.source_operations_models import (
    SourceFamily,
    SourceFreshnessStanding,
)

_SAFE_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$"
_PRIVATE_PATH_RE = re.compile(r"(/Users/|/home/|/private/|/var/|/tmp/|/etc/|~/|[A-Za-z]:\\)")
_SECRET_VALUE_RE = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]{8,}|sk-[A-Za-z0-9_-]{8,}|"
    r"(?:api[_-]?key|password|secret|token)\s*[:=]\s*[^\s,;]{4,})"
)


def _screen_portable_text(value: str, label: str) -> str:
    if _PRIVATE_PATH_RE.search(value):
        raise ValueError(f"{label} must not contain a private absolute path")
    if _SECRET_VALUE_RE.search(value):
        raise ValueError(f"{label} must not contain a credential or secret value")
    return value


def _require_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError(f"{label} must be timezone-aware UTC")
    return value


class SourceQualityModel(ManchesterSnapshotModel):
    """Frozen, privacy-screened base for quality diagnostics."""

    @model_validator(mode="after")
    def _reject_nonportable(self) -> Self:
        def visit(v: object) -> None:
            if isinstance(v, str):
                _screen_portable_text(v, "source quality metadata")
            elif isinstance(v, dict):
                for k, it in v.items():
                    visit(k)
                    visit(it)
            elif isinstance(v, (list, tuple, set, frozenset)):
                for it in v:
                    visit(it)

        visit(self.model_dump(mode="python"))
        return self


class IntervalGap(SourceQualityModel):
    """One detected interval gap between consecutive observed timestamps."""

    gap_start_utc: datetime
    gap_end_utc: datetime
    gap_seconds: int = Field(ge=1)
    expected_interval_seconds: int = Field(gt=0)

    @field_validator("gap_start_utc", "gap_end_utc")
    @classmethod
    def _validate_gap_time(cls, value: datetime) -> datetime:
        return _require_utc(value, "gap time")

    @model_validator(mode="after")
    def _validate_gap(self) -> Self:
        if self.gap_end_utc <= self.gap_start_utc:
            raise ValueError("gap end must be after gap start")
        expected = (self.gap_end_utc - self.gap_start_utc).total_seconds()
        if int(expected) != self.gap_seconds:
            raise ValueError("gap seconds must equal observed interval")
        if self.gap_seconds <= self.expected_interval_seconds:
            raise ValueError("gap must exceed expected interval")
        return self


class SourceQualityInput(SourceQualityModel):
    """Explicit, typed inputs for one source-family quality assessment.

    All counts are caller-supplied; no filesystem or network is consulted.
    Timestamp values are timezone-aware UTC and ordered where applicable.
    """

    source_family: SourceFamily
    evaluated_at_utc: datetime
    total_expected_rows: int = Field(ge=0)
    present_rows: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    parser_warnings: tuple[str, ...] = ()
    expected_interval_seconds: int | None = Field(default=None, gt=0)
    observed_timestamps_utc: tuple[datetime, ...] = ()
    spatial_cells_total: int | None = Field(default=None, ge=0)
    spatial_cells_covered: int | None = Field(default=None, ge=0)
    timestamp_start_utc: datetime | None = None
    timestamp_end_utc: datetime | None = None
    latest_retrieved_at_utc: datetime | None = None
    freshness: SourceFreshnessStanding | None = None
    limitations: tuple[str, ...] = ()
    schema_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)
    coverage_summary: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("evaluated_at_utc")
    @classmethod
    def _validate_evaluated(cls, value: datetime) -> datetime:
        return _require_utc(value, "evaluated time")

    @field_validator("timestamp_start_utc", "timestamp_end_utc", "latest_retrieved_at_utc")
    @classmethod
    def _validate_opt_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        return _require_utc(value, "timestamp")

    @model_validator(mode="after")
    def _validate_counts(self) -> Self:
        if self.missing_rows > self.total_expected_rows:
            raise ValueError("missing rows must not exceed total expected rows")
        if (
            self.present_rows > self.total_expected_rows
            and self.total_expected_rows != 0
            and self.present_rows != 0
        ):
            raise ValueError("present rows must not exceed total expected when total known")
        if self.duplicate_rows > self.present_rows:
            raise ValueError("duplicate rows must not exceed present rows")
        if (
            self.accepted_rows + self.rejected_rows > self.total_expected_rows
            and self.total_expected_rows != 0
        ):
            # accepted+rejected is a subset of ingestion; allow but not exceed total
            raise ValueError("accepted+rejected must not exceed total expected")
        if (
            self.spatial_cells_total is not None
            and self.spatial_cells_covered is not None
            and self.spatial_cells_covered > self.spatial_cells_total
        ):
            raise ValueError("covered cells must not exceed total cells")
        if (self.spatial_cells_total is None) != (self.spatial_cells_covered is None):
            raise ValueError("spatial coverage requires both total and covered")
        if (
            self.timestamp_start_utc is not None
            and self.timestamp_end_utc is not None
            and self.timestamp_start_utc > self.timestamp_end_utc
        ):
            raise ValueError("timestamp start must not be after timestamp end")
        if (
            self.latest_retrieved_at_utc is not None
            and self.latest_retrieved_at_utc > self.evaluated_at_utc
        ):
            raise ValueError("latest retrieval must not be after evaluated time")
        # observed timestamps must be UTC, sorted ascending, unique
        for ts in self.observed_timestamps_utc:
            _require_utc(ts, "observed timestamp")
        if self.observed_timestamps_utc != tuple(sorted(self.observed_timestamps_utc)):
            raise ValueError("observed timestamps must be sorted ascending")
        if len(self.observed_timestamps_utc) != len(set(self.observed_timestamps_utc)):
            raise ValueError("observed timestamps must be unique")
        if self.observed_timestamps_utc and self.expected_interval_seconds is None:
            # gaps cannot be computed without expectation; keep but gap calc will be empty
            pass
        # coverage summary must not contain private paths/secrets (handled by base)
        return self


class SourceQualityDiagnostics(SourceQualityModel):
    """Transparent, typed quality diagnostics with precisely defined math.

    No composite or scientific quality score is present. Every rate uses an
    explicit denominator and returns ``None`` when that denominator is zero
    or the prerequisite input is absent, never a synthetic default.
    """

    source_family: SourceFamily
    evaluated_at_utc: datetime
    total_expected_rows: int = Field(ge=0)
    present_rows: int = Field(ge=0)
    missing_rows: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    accepted_rows: int = Field(ge=0)
    rejected_rows: int = Field(ge=0)
    missingness: float | None = Field(default=None, ge=0.0, le=1.0)
    duplicate_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    rejected_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    spatial_coverage_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp_range_seconds: int | None = Field(default=None, ge=0)
    freshness_delay_seconds: int | None = Field(default=None, ge=0)
    interval_gap_count: int = Field(ge=0)
    interval_gaps: tuple[IntervalGap, ...] = ()
    parser_warning_count: int = Field(ge=0)
    parser_warnings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    freshness: SourceFreshnessStanding | None = None
    schema_version: str | None = Field(default=None, pattern=_SAFE_LABEL_PATTERN)
    coverage_summary: str | None = Field(default=None, min_length=1, max_length=300)

    @field_validator("evaluated_at_utc")
    @classmethod
    def _validate_evaluated(cls, value: datetime) -> datetime:
        return _require_utc(value, "evaluated time")

    @model_validator(mode="after")
    def _validate_diagnostics(self) -> Self:
        # Canonical revalidation of nested gaps
        for gap in self.interval_gaps:
            try:
                IntervalGap.model_validate(gap.model_dump(mode="python"))
            except Exception as exc:
                raise ValueError("interval gap failed canonical revalidation") from exc
        if self.interval_gap_count != len(self.interval_gaps):
            raise ValueError("gap count must equal gaps length")
        # No quality score field may exist (structural guarantee via extra=forbid)
        # Rates already range-checked
        return self


def _compute_missingness(total: int, missing: int) -> float | None:
    if total == 0:
        return None
    return missing / total


def _compute_duplicate_rate(present: int, duplicate: int) -> float | None:
    if present == 0:
        return None
    return duplicate / present


def _compute_rejected_rate(accepted: int, rejected: int) -> float | None:
    denom = accepted + rejected
    if denom == 0:
        return None
    return rejected / denom


def _compute_spatial_coverage(total: int | None, covered: int | None) -> float | None:
    if total is None or covered is None:
        return None
    if total == 0:
        return None
    return covered / total


def _compute_timestamp_range(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return int((end - start).total_seconds())


def _compute_freshness_delay(evaluated: datetime, latest: datetime | None) -> int | None:
    if latest is None:
        return None
    return int((evaluated - latest).total_seconds())


def _detect_interval_gaps(
    timestamps: tuple[datetime, ...],
    expected_interval_seconds: int | None,
) -> tuple[IntervalGap, ...]:
    if expected_interval_seconds is None or len(timestamps) < 2:
        return ()
    gaps: list[IntervalGap] = []
    for a, b in zip(timestamps, timestamps[1:], strict=False):
        diff = int((b - a).total_seconds())
        if diff > expected_interval_seconds:
            gaps.append(
                IntervalGap(
                    gap_start_utc=a,
                    gap_end_utc=b,
                    gap_seconds=diff,
                    expected_interval_seconds=expected_interval_seconds,
                )
            )
    return tuple(gaps)


def compute_source_quality_diagnostics(
    quality_input: SourceQualityInput,
) -> SourceQualityDiagnostics:
    """Compute transparent diagnostics from explicit typed inputs.

    The input is canonically revalidated from its dump to close
    ``model_copy`` mutation bypass. All rates return ``None`` on zero
    denominators rather than raising or defaulting.
    """

    # Canonical revalidation at the persistence boundary to defeat model_copy bypass
    try:
        quality_input = SourceQualityInput.model_validate(quality_input.model_dump(mode="python"))
    except Exception as exc:
        raise ValueError("source quality input failed canonical revalidation") from exc

    missingness = _compute_missingness(
        quality_input.total_expected_rows, quality_input.missing_rows
    )
    duplicate_rate = _compute_duplicate_rate(
        quality_input.present_rows, quality_input.duplicate_rows
    )
    rejected_rate = _compute_rejected_rate(quality_input.accepted_rows, quality_input.rejected_rows)
    spatial_coverage = _compute_spatial_coverage(
        quality_input.spatial_cells_total, quality_input.spatial_cells_covered
    )
    timestamp_range = _compute_timestamp_range(
        quality_input.timestamp_start_utc, quality_input.timestamp_end_utc
    )
    freshness_delay = _compute_freshness_delay(
        quality_input.evaluated_at_utc, quality_input.latest_retrieved_at_utc
    )
    gaps = _detect_interval_gaps(
        quality_input.observed_timestamps_utc, quality_input.expected_interval_seconds
    )

    diagnostics = SourceQualityDiagnostics(
        source_family=quality_input.source_family,
        evaluated_at_utc=quality_input.evaluated_at_utc,
        total_expected_rows=quality_input.total_expected_rows,
        present_rows=quality_input.present_rows,
        missing_rows=quality_input.missing_rows,
        duplicate_rows=quality_input.duplicate_rows,
        accepted_rows=quality_input.accepted_rows,
        rejected_rows=quality_input.rejected_rows,
        missingness=missingness,
        duplicate_rate=duplicate_rate,
        rejected_rate=rejected_rate,
        spatial_coverage_rate=spatial_coverage,
        timestamp_range_seconds=timestamp_range,
        freshness_delay_seconds=freshness_delay,
        interval_gap_count=len(gaps),
        interval_gaps=gaps,
        parser_warning_count=len(quality_input.parser_warnings),
        parser_warnings=quality_input.parser_warnings,
        limitations=quality_input.limitations,
        freshness=quality_input.freshness,
        schema_version=quality_input.schema_version,
        coverage_summary=quality_input.coverage_summary,
    )
    # Final canonical revalidation
    try:
        diagnostics = SourceQualityDiagnostics.model_validate(diagnostics.model_dump(mode="python"))
    except Exception as exc:
        raise ValueError("source quality diagnostics failed canonical revalidation") from exc
    return diagnostics


__all__ = [
    "IntervalGap",
    "SourceQualityDiagnostics",
    "SourceQualityInput",
    "SourceQualityModel",
    "compute_source_quality_diagnostics",
]

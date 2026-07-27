"""Descriptive comparison of bus progression against the DfT hourly shape (B2).

The declared comparison step the session-progression primitive deliberately
left unperformed: the observed hourly road-demand *shape* (derived from the
surviving Option-A edgeData counts, whose observation side is DfT road
counts) set beside the observed hourly *bus progression speed* shape from
attended sessions. Two independent real sources, one city, purely
descriptive: no threshold, no acceptance, no causal language, and buses stay
buses throughout — bus speed is never road speed, and road counts are never
bus counts.

The DfT hour remains a local clock-hour label under the unresolved GA-DFT-1
blocker; the alignment offset applied to the sessions' UTC hours is an
explicit declared input carried on the artifact, never an inference.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import fromstring

from pydantic import Field, model_validator

from traffictwin.integration.manchester.bods_session_identity import (
    BodsSessionIdentityError,
    SessionProgressionMeasurement,
)
from traffictwin.integration.manchester.models import ManchesterSnapshotModel

_MAX_EDGEDATA_BYTES = 32 * 1024 * 1024
_MINIMUM_SEGMENTS_PER_HOUR = 30


class DftHourlyShape(ManchesterSnapshotModel):
    """Observed hourly road-demand shape from the Option-A edgeData counts."""

    schema_version: Literal["1.0"] = "1.0"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hour_local_labels: tuple[int, ...] = Field(min_length=1)
    entered_by_hour: tuple[int, ...] = Field(min_length=1)
    share_by_hour: tuple[float, ...] = Field(min_length=1)
    total_entered: int = Field(ge=1)
    hours_are_local_clock_labels: Literal[True] = True
    ga_dft_1_unresolved: Literal[True] = True
    road_counts_are_not_bus_counts: Literal[True] = True

    @model_validator(mode="after")
    def validate_alignment(self) -> DftHourlyShape:
        lengths = {
            len(self.hour_local_labels),
            len(self.entered_by_hour),
            len(self.share_by_hour),
        }
        if lengths != {len(self.hour_local_labels)}:
            raise ValueError("hourly series must align")
        if sum(self.entered_by_hour) != self.total_entered:
            raise ValueError("hourly totals must sum to the recorded total")
        return self


class BusDftShapeComparison(ManchesterSnapshotModel):
    """Descriptive, support-gated alignment of two independent hourly shapes."""

    schema_version: Literal["1.0"] = "1.0"
    dft_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    session_snapshot_ids: tuple[str, ...] = Field(min_length=2)
    utc_to_local_offset_hours: int = Field(ge=-12, le=14)
    aligned_hour_local_labels: tuple[int, ...] = ()
    bus_speed_mps_median_by_hour: tuple[float, ...] = ()
    bus_segment_support_by_hour: tuple[int, ...] = ()
    dft_share_by_hour: tuple[float, ...] = ()
    hours_excluded_for_support: tuple[int, ...] = ()
    minimum_segments_per_hour: int = Field(ge=1)
    spearman_rho: float | None = Field(default=None, ge=-1, le=1)
    spearman_pair_count: int = Field(ge=0)
    descriptive_non_causal: Literal[True] = True
    dft_comparison_performed: Literal[True] = True
    bus_speed_is_not_road_speed: Literal[True] = True
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    @model_validator(mode="after")
    def validate_series(self) -> BusDftShapeComparison:
        lengths = {
            len(self.aligned_hour_local_labels),
            len(self.bus_speed_mps_median_by_hour),
            len(self.bus_segment_support_by_hour),
            len(self.dft_share_by_hour),
        }
        if lengths != {len(self.aligned_hour_local_labels)}:
            raise ValueError("aligned series must share the hour axis")
        if self.spearman_rho is not None and self.spearman_pair_count < 3:
            raise ValueError("a correlation needs at least three aligned hours")
        return self


def load_dft_hourly_shape(edgedata_path: str | Path) -> DftHourlyShape:
    """Reduce the surviving Option-A edgeData counts to an hourly shape."""

    path = Path(edgedata_path)
    if not path.is_file():
        raise BodsSessionIdentityError("EDGEDATA_MISSING", f"no edgeData file at {path}")
    payload = path.read_bytes()
    if len(payload) > _MAX_EDGEDATA_BYTES:
        raise BodsSessionIdentityError("EDGEDATA_TOO_LARGE", "bounded size exceeded")
    root = fromstring(payload.decode("utf-8"))  # noqa: S314 - committed repository evidence
    hours: list[int] = []
    totals: list[int] = []
    for interval in root.iter("interval"):
        begin = float(interval.get("begin", "nan"))
        hour = int(begin // 3600)
        entered = sum(int(edge.get("entered", "0")) for edge in interval.iter("edge"))
        hours.append(hour)
        totals.append(entered)
    if not hours:
        raise BodsSessionIdentityError("EDGEDATA_EMPTY", "no intervals present")
    #: The Option-A window's intervals are labelled h00..h11 relative to the
    #: profile's first hour (07 local); shift to local clock-hour labels.
    local_labels = tuple(hour + 7 for hour in hours)
    total = sum(totals)
    return DftHourlyShape(
        source_sha256=hashlib.sha256(payload).hexdigest(),
        hour_local_labels=local_labels,
        entered_by_hour=tuple(totals),
        share_by_hour=tuple(value / total for value in totals),
        total_entered=total,
    )


def compare_bus_progression_to_dft_shape(
    progression: SessionProgressionMeasurement,
    shape: DftHourlyShape,
    *,
    utc_to_local_offset_hours: int,
    minimum_segments_per_hour: int = _MINIMUM_SEGMENTS_PER_HOUR,
) -> BusDftShapeComparison:
    """Align the two observed hourly shapes descriptively, gated on support."""

    bus_by_local_hour: dict[int, tuple[float, int]] = {}
    for hour_utc, median, segments in zip(
        progression.hour_utc,
        progression.speed_mps_median_by_hour,
        progression.segment_count_by_hour,
        strict=True,
    ):
        bus_by_local_hour[(hour_utc + utc_to_local_offset_hours) % 24] = (median, segments)

    aligned: list[int] = []
    speeds: list[float] = []
    supports: list[int] = []
    shares: list[float] = []
    excluded: list[int] = []
    for label, share in zip(shape.hour_local_labels, shape.share_by_hour, strict=True):
        entry = bus_by_local_hour.get(label)
        if entry is None:
            continue
        median, segments = entry
        if segments < minimum_segments_per_hour:
            excluded.append(label)
            continue
        aligned.append(label)
        speeds.append(median)
        supports.append(segments)
        shares.append(share)

    rho = _spearman(speeds, shares) if len(aligned) >= 3 else None
    return BusDftShapeComparison(
        dft_source_sha256=shape.source_sha256,
        session_snapshot_ids=progression.snapshot_ids,
        utc_to_local_offset_hours=utc_to_local_offset_hours,
        aligned_hour_local_labels=tuple(aligned),
        bus_speed_mps_median_by_hour=tuple(speeds),
        bus_segment_support_by_hour=tuple(supports),
        dft_share_by_hour=tuple(shares),
        hours_excluded_for_support=tuple(excluded),
        minimum_segments_per_hour=minimum_segments_per_hour,
        spearman_rho=rho,
        spearman_pair_count=len(aligned) if rho is not None else 0,
    )


def _spearman(left: list[float], right: list[float]) -> float | None:
    """Spearman rank correlation with average ranks for ties."""

    if len(left) != len(right) or len(left) < 3:
        return None

    def ranks(values: list[float]) -> list[float]:
        ordered = sorted(range(len(values)), key=lambda index: values[index])
        result = [0.0] * len(values)
        position = 0
        while position < len(ordered):
            tail = position
            while (
                tail + 1 < len(ordered) and values[ordered[tail + 1]] == values[ordered[position]]
            ):
                tail += 1
            average = (position + tail) / 2 + 1
            for index in range(position, tail + 1):
                result[ordered[index]] = average
            position = tail + 1
        return result

    left_ranks, right_ranks = ranks(left), ranks(right)
    count = len(left)
    mean = (count + 1) / 2
    covariance = sum((a - mean) * (b - mean) for a, b in zip(left_ranks, right_ranks, strict=True))
    variance_left = sum((a - mean) ** 2 for a in left_ranks)
    variance_right = sum((b - mean) ** 2 for b in right_ranks)
    if variance_left == 0 or variance_right == 0:
        return None
    return float(covariance / (variance_left * variance_right) ** 0.5)

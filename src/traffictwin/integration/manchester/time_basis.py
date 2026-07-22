"""MAN-07 candidate time-basis and UTC projection primitives.

The module implements ADR-055 without source acquisition or wall-clock reads.
Only documented UTC instants can enter a UTC analysis window. Date-only,
undocumented local/source strings, and simulation clocks remain typed evidence
and fail closed instead of receiving fabricated absolute timestamps.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias, cast
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

MANCHESTER_TIME_SCHEMA_VERSION = "1.0"
MANCHESTER_TIME_METHOD_VERSION = "manchester-time-basis-1.0"
MANCHESTER_TIME_CAPABILITY_ID = "MAN-07"
LONDON_TIMEZONE = "Europe/London"


class ManchesterTimeError(ValueError):
    """Raised when a caller supplies a contradictory time declaration."""


class ManchesterTimeModel(ManchesterSnapshotModel):
    """Strict frozen base for deterministic MAN-07 time artifacts."""


class UtcInstantTime(ManchesterTimeModel):
    """A source instant whose UTC basis is documented."""

    kind: Literal["utc_instant"] = "utc_instant"
    observed_at_utc: datetime
    timezone_basis: Literal["documented_utc"] = "documented_utc"

    @model_validator(mode="after")
    def validate_utc(self) -> UtcInstantTime:
        _require_utc(self.observed_at_utc, "observed_at_utc")
        return self


class LocalClockHourTime(ManchesterTimeModel):
    """DfT date/hour evidence with an unresolved timezone basis."""

    kind: Literal["local_clock_hour"] = "local_clock_hour"
    source_date: date
    hour_label: int = Field(ge=0, le=23)
    timezone_basis: Literal["undocumented_ga_dft_1"] = "undocumented_ga_dft_1"
    utc_projection_available: Literal[False] = False


class UndeclaredSourceStringTime(ManchesterTimeModel):
    """WebTRIS source date/time strings retained without timezone invention."""

    kind: Literal["source_string_undeclared"] = "source_string_undeclared"
    source_date_raw: str = Field(min_length=1, max_length=100)
    source_time_raw: str = Field(min_length=1, max_length=100)
    timezone_basis: Literal["undocumented_ga_wt_1"] = "undocumented_ga_wt_1"
    utc_projection_available: Literal[False] = False


class DateOnlyTime(ManchesterTimeModel):
    """A calendar date that cannot be converted to a midnight instant."""

    kind: Literal["date_only"] = "date_only"
    source_date: date
    granularity: Literal["calendar_date"] = "calendar_date"
    utc_projection_available: Literal[False] = False


class SimulationClockTime(ManchesterTimeModel):
    """A relative simulation clock kept separate from wall-clock evidence."""

    kind: Literal["simulation_clock"] = "simulation_clock"
    timestamp_s: Decimal = Field(ge=0)
    clock_domain: str = Field(min_length=1, max_length=100)
    wall_clock_projection_available: Literal[False] = False


ManchesterSourceTime: TypeAlias = Annotated[
    UtcInstantTime
    | LocalClockHourTime
    | UndeclaredSourceStringTime
    | DateOnlyTime
    | SimulationClockTime,
    Field(discriminator="kind"),
]


class ManchesterTimeBasis(ManchesterTimeModel):
    """One explicit half-open UTC analysis window and canonical anchor."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-time-basis-1.0"] = "manchester-time-basis-1.0"
    analysis_anchor_utc: datetime
    window_start_utc: datetime
    window_end_utc: datetime
    interval_semantics: Literal["half_open_start_inclusive_end_exclusive"] = (
        "half_open_start_inclusive_end_exclusive"
    )
    display_timezone: Literal["Europe/London"] = "Europe/London"
    source_anchor_inferred: Literal[False] = False
    retrieval_clock_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_window(self) -> ManchesterTimeBasis:
        for field_name, value in (
            ("analysis_anchor_utc", self.analysis_anchor_utc),
            ("window_start_utc", self.window_start_utc),
            ("window_end_utc", self.window_end_utc),
        ):
            _require_utc(value, field_name)
        if self.analysis_anchor_utc != self.window_start_utc:
            raise ValueError("analysis anchor must equal the requested window start")
        if self.window_end_utc <= self.window_start_utc:
            raise ValueError("analysis window must have positive duration")
        return self


ProjectionStatus = Literal["admitted", "excluded"]
ProjectionReason = Literal[
    "utc_instant_in_window",
    "outside_half_open_window",
    "undocumented_source_timezone_ga_dft_1",
    "undocumented_source_timezone_ga_wt_1",
    "date_only_has_no_instant",
    "simulation_clock_is_not_wall_clock",
]


class ManchesterTimeProjection(ManchesterTimeModel):
    """Deterministic admission/refusal result for one source time value."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-07"] = "MAN-07"
    method_version: Literal["manchester-time-basis-1.0"] = "manchester-time-basis-1.0"
    source_kind: Literal[
        "utc_instant",
        "local_clock_hour",
        "source_string_undeclared",
        "date_only",
        "simulation_clock",
    ]
    time_basis_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: ProjectionStatus
    reason: ProjectionReason
    timestamp_s: Decimal | None = Field(default=None, ge=0)
    observed_at_utc: datetime | None = None
    source_value_preserved: Literal[True] = True
    fabricated_instant: Literal[False] = False

    @model_validator(mode="after")
    def validate_projection(self) -> ManchesterTimeProjection:
        admitted = self.status == "admitted"
        if admitted != (self.reason == "utc_instant_in_window"):
            raise ValueError("only an in-window UTC instant can be admitted")
        if admitted != (self.timestamp_s is not None and self.observed_at_utc is not None):
            raise ValueError("admitted projection needs UTC and relative seconds")
        if self.observed_at_utc is not None:
            _require_utc(self.observed_at_utc, "observed_at_utc")
        return self


class LondonUtcCandidate(ManchesterTimeModel):
    """One valid UTC interpretation of a London local wall time."""

    fold: Literal[0, 1]
    offset_seconds: int = Field(ge=-86_400, le=86_400)
    utc_instant: datetime

    @model_validator(mode="after")
    def validate_utc(self) -> LondonUtcCandidate:
        _require_utc(self.utc_instant, "utc_instant")
        return self


class LondonLocalTimeResolution(ManchesterTimeModel):
    """Unique, ambiguous, or nonexistent status for one naive London wall time."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-london-dst-1.0"] = "manchester-london-dst-1.0"
    local_wall_time: datetime
    timezone: Literal["Europe/London"] = "Europe/London"
    status: Literal["unique", "ambiguous", "nonexistent"]
    candidates: tuple[LondonUtcCandidate, ...]
    selected_utc: datetime | None = None
    selected_fold: Literal[0, 1] | None = None
    fabricated_instant: Literal[False] = False

    @model_validator(mode="after")
    def validate_resolution(self) -> LondonLocalTimeResolution:
        if self.local_wall_time.tzinfo is not None:
            raise ValueError("local_wall_time must remain naive source wall time")
        expected_count = {"unique": 1, "ambiguous": 2, "nonexistent": 0}[self.status]
        if len(self.candidates) != expected_count:
            raise ValueError("DST status does not reconcile to candidate count")
        if tuple(candidate.utc_instant for candidate in self.candidates) != tuple(
            sorted(candidate.utc_instant for candidate in self.candidates)
        ):
            raise ValueError("UTC candidates must be sorted")
        if self.status == "unique":
            candidate = self.candidates[0]
            if self.selected_utc != candidate.utc_instant or self.selected_fold != candidate.fold:
                raise ValueError("unique local time must select its only candidate")
        elif self.status == "nonexistent":
            if self.selected_utc is not None or self.selected_fold is not None:
                raise ValueError("nonexistent local time cannot select an instant")
        elif self.selected_fold is None:
            if self.selected_utc is not None:
                raise ValueError("ambiguous selection requires a fold")
        else:
            match = next(
                (
                    candidate
                    for candidate in self.candidates
                    if candidate.fold == self.selected_fold
                ),
                None,
            )
            if match is None or self.selected_utc != match.utc_instant:
                raise ValueError("selected fold must bind an ambiguous UTC candidate")
        return self


class LondonDisplayTime(ManchesterTimeModel):
    """A display-only Europe/London conversion that retains its UTC source."""

    observed_at_utc: datetime
    timezone: Literal["Europe/London"] = "Europe/London"
    local_datetime: datetime
    fold: Literal[0, 1]
    utc_offset_seconds: int = Field(ge=-86_400, le=86_400)
    storage_rewritten: Literal[False] = False

    @model_validator(mode="after")
    def validate_conversion(self) -> LondonDisplayTime:
        _require_utc(self.observed_at_utc, "observed_at_utc")
        expected = self.observed_at_utc.astimezone(ZoneInfo(LONDON_TIMEZONE))
        if self.local_datetime != expected or self.fold != expected.fold:
            raise ValueError("London display value does not match its UTC source")
        offset = expected.utcoffset()
        if offset is None or self.utc_offset_seconds != int(offset.total_seconds()):
            raise ValueError("London display offset does not match timezone rules")
        return self


def project_source_time(
    source_time: ManchesterSourceTime,
    time_basis: ManchesterTimeBasis,
) -> ManchesterTimeProjection:
    """Project documented UTC only; return typed exclusions for every other basis."""

    if isinstance(source_time, UtcInstantTime):
        instant = source_time.observed_at_utc
        if time_basis.window_start_utc <= instant < time_basis.window_end_utc:
            return ManchesterTimeProjection(
                source_kind=source_time.kind,
                time_basis_fingerprint=time_basis.fingerprint(),
                status="admitted",
                reason="utc_instant_in_window",
                timestamp_s=_timedelta_seconds(instant - time_basis.analysis_anchor_utc),
                observed_at_utc=instant,
            )
        return ManchesterTimeProjection(
            source_kind=source_time.kind,
            time_basis_fingerprint=time_basis.fingerprint(),
            status="excluded",
            reason="outside_half_open_window",
        )
    reasons: dict[str, ProjectionReason] = {
        "local_clock_hour": "undocumented_source_timezone_ga_dft_1",
        "source_string_undeclared": "undocumented_source_timezone_ga_wt_1",
        "date_only": "date_only_has_no_instant",
        "simulation_clock": "simulation_clock_is_not_wall_clock",
    }
    return ManchesterTimeProjection(
        source_kind=source_time.kind,
        time_basis_fingerprint=time_basis.fingerprint(),
        status="excluded",
        reason=reasons[source_time.kind],
    )


def resolve_london_local(
    local_wall_time: datetime,
    *,
    fold: Literal[0, 1] | None = None,
) -> LondonLocalTimeResolution:
    """Resolve a naive London wall time without inventing missing/ambiguous instants."""

    if local_wall_time.tzinfo is not None:
        raise ManchesterTimeError("local wall time must be naive")
    london = ZoneInfo(LONDON_TIMEZONE)
    candidates_by_utc: dict[datetime, LondonUtcCandidate] = {}
    for candidate_fold in (0, 1):
        aware = local_wall_time.replace(tzinfo=london, fold=candidate_fold)
        utc_instant = aware.astimezone(UTC)
        round_trip = utc_instant.astimezone(london)
        if round_trip.replace(tzinfo=None) != local_wall_time or round_trip.fold != candidate_fold:
            continue
        offset = aware.utcoffset()
        if offset is None:
            continue
        candidates_by_utc[utc_instant] = LondonUtcCandidate(
            fold=candidate_fold,
            offset_seconds=int(offset.total_seconds()),
            utc_instant=utc_instant,
        )
    candidates = tuple(
        sorted(candidates_by_utc.values(), key=lambda candidate: candidate.utc_instant)
    )
    if not candidates:
        return LondonLocalTimeResolution(
            local_wall_time=local_wall_time,
            status="nonexistent",
            candidates=(),
        )
    if len(candidates) == 1:
        candidate = candidates[0]
        return LondonLocalTimeResolution(
            local_wall_time=local_wall_time,
            status="unique",
            candidates=candidates,
            selected_utc=candidate.utc_instant,
            selected_fold=candidate.fold,
        )
    selected = next((candidate for candidate in candidates if candidate.fold == fold), None)
    return LondonLocalTimeResolution(
        local_wall_time=local_wall_time,
        status="ambiguous",
        candidates=candidates,
        selected_utc=None if selected is None else selected.utc_instant,
        selected_fold=None if selected is None else selected.fold,
    )


def to_london_display(observed_at_utc: datetime) -> LondonDisplayTime:
    """Convert one UTC instant for display without rewriting stored evidence."""

    _require_utc(observed_at_utc, "observed_at_utc")
    local = observed_at_utc.astimezone(ZoneInfo(LONDON_TIMEZONE))
    offset = local.utcoffset()
    if offset is None:  # pragma: no cover - ZoneInfo always supplies this for a valid instant
        raise ManchesterTimeError("Europe/London supplied no UTC offset")
    return LondonDisplayTime(
        observed_at_utc=observed_at_utc,
        local_datetime=local,
        fold=cast(Literal[0, 1], local.fold),
        utc_offset_seconds=int(offset.total_seconds()),
    )


def _require_utc(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{label} must be explicitly UTC")


def _timedelta_seconds(value: timedelta) -> Decimal:
    return (
        Decimal(value.days * 86_400 + value.seconds)
        + Decimal(value.microseconds) / Decimal(1_000_000)
    )

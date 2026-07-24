"""MAN-09 candidate: deterministic day-type/time-of-day temporal profiles.

The module is a pure evidence transformation over caller-supplied, already
parsed source-specific observations. One versioned policy binds one observed
source, measure, unit, time basis, exact inclusive analysis window, exact
expected slot-label grid, day-type rule, season rule, caller-declared excluded
dates, and a minimum per-cell observation count. Every report embeds its exact
inputs and re-derives its complete cell partition during validation.

Hard boundaries:

- no network, filesystem discovery, wall clock, database, UI, LLM, SUMO
  launch, or subprocess use — observations arrive as completed typed evidence;
- a missing observation is never zero: unobserved cells stay visible with the
  explicit ``no_observations`` state and no value;
- no interpolation, resampling, or filling of unobserved intervals exists;
- source-local clock labels are never promoted to UTC: DfT and WebTRIS
  evidence must declare ``source_local_clock_undeclared`` while their source
  timezone blockers remain open, and a date plus slot label never becomes a
  fabricated instant;
- excluded dates are caller-declared with a reason label — the builder never
  infers a public holiday, event, or school term from the calendar;
- null values stay separate from zero and are retained as typed exclusions;
- no demand synthesis: profile cells never become SUMO vehicle-generation
  rates, and baseline acceptance is structurally unavailable here; and
- production profile use stays unavailable until a lead-reviewed policy
  fingerprint enters the frozen-empty registry below, so ``MAN-09`` remains
  ``planned``.

Self-consistency is tamper evidence, not cryptographic authenticity: an actor
who rebuilds an internally consistent artifact has created new evidence and
still needs the upstream acceptance and publication gates.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

MANCHESTER_TEMPORAL_PROFILE_SCHEMA_VERSION = "1.0"
MANCHESTER_TEMPORAL_PROFILE_METHOD_VERSION = "manchester-temporal-profile-1.0"
MANCHESTER_TEMPORAL_PROFILE_CAPABILITY_ID = "MAN-09"

# A production entry requires a reviewed, predeclared profile-policy design
# (source timezone semantics included). Keeping this registry empty keeps real
# calibration-profile use unavailable while MAN-09 remains planned.
APPROVED_PRODUCTION_PROFILE_POLICY_FINGERPRINTS: frozenset[str] = frozenset()

PROFILE_VALUE_QUANTUM = Decimal("0.001")
_DECIMAL_PRECISION = 28
_MAX_ABSOLUTE_VALUE = Decimal("1000000000")
MAX_PROFILE_OBSERVATIONS = 50_000
MAX_PROFILE_SLOT_LABELS = 288
MAX_ANALYSIS_WINDOW_DAYS = 400
MAX_DECLARED_EXCLUDED_DATES = 64

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}$"
_LABEL_PATTERN = r"^[a-z0-9][a-z0-9_-]{0,63}$"
_SLOT_LABEL_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,63}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"

ProfileSource: TypeAlias = Literal["dft_raw_count", "webtris_daily", "synthetic_utc_road"]
ProfileMeasure: TypeAlias = Literal["vehicle_count", "average_speed_mps"]
ProfileUnit: TypeAlias = Literal["vehicles_per_interval", "m/s"]
ProfileTimeBasis: TypeAlias = Literal["source_local_clock_undeclared", "utc"]
DayType: TypeAlias = Literal["weekday", "saturday", "sunday"]
Season: TypeAlias = Literal["all_year", "winter", "spring", "summer", "autumn"]
CellState: TypeAlias = Literal["available", "insufficient_observations", "no_observations"]
ProfileAdmission: TypeAlias = Literal[
    "synthetic_development_inputs",
    "approved_production_policy",
    "not_admitted_production_unapproved",
]
ProfileExclusionReason: TypeAlias = Literal[
    "outside_analysis_window",
    "unknown_slot_label",
    "declared_excluded_date",
    "null_value_retained",
    "duplicate_identical_row",
    "conflicting_duplicate_rows",
]

_MEASURE_UNITS: dict[ProfileMeasure, ProfileUnit] = {
    "vehicle_count": "vehicles_per_interval",
    "average_speed_mps": "m/s",
}

# DfT raw-count hours and WebTRIS clock strings have unresolved source
# timezones (GA-DFT-1 and the WebTRIS timezone blocker), so their profile time
# basis is structurally source-local; only the labelled synthetic fixture may
# declare UTC.
_SOURCE_TIME_BASES: dict[ProfileSource, ProfileTimeBasis] = {
    "dft_raw_count": "source_local_clock_undeclared",
    "webtris_daily": "source_local_clock_undeclared",
    "synthetic_utc_road": "utc",
}

_MONTH_SEASONS: dict[int, Season] = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}


class ManchesterTemporalProfileError(ValueError):
    """Typed caller-side misuse of the temporal-profile boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ManchesterTemporalProfileModel(ManchesterSnapshotModel):
    """Strict frozen base for deterministic temporal-profile artifacts."""


class DeclaredExcludedDate(ManchesterTemporalProfileModel):
    """One caller-declared excluded survey date with its explicit reason."""

    date: dt.date
    reason_label: str = Field(pattern=_LABEL_PATTERN)


class TemporalProfilePolicy(ManchesterTemporalProfileModel):
    """Versioned policy binding one source-specific profile construction."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-temporal-profile-1.0"] = "manchester-temporal-profile-1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    policy_label: str = Field(pattern=_LABEL_PATTERN)
    source: ProfileSource
    measure: ProfileMeasure
    unit: ProfileUnit
    time_basis: ProfileTimeBasis
    day_type_rule: Literal["iso_weekday_saturday_sunday_v1"] = "iso_weekday_saturday_sunday_v1"
    season_rule: Literal["none", "meteorological_month_v1"]
    window_start_date: dt.date
    window_end_date: dt.date
    expected_slot_labels: tuple[str, ...] = Field(min_length=1)
    declared_excluded_dates: tuple[DeclaredExcludedDate, ...] = ()
    minimum_cell_observations: int = Field(ge=1, le=1000)
    holiday_inference: Literal["unavailable"] = "unavailable"
    missing_as_zero: Literal[False] = False
    interpolation: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def validate_window_grid_and_exclusions(self) -> TemporalProfilePolicy:
        """Keep the window, slot grid, and declared exclusions exact and bounded."""

        if self.window_end_date < self.window_start_date:
            raise ValueError("window_end_date must not precede window_start_date")
        window_days = (self.window_end_date - self.window_start_date).days + 1
        if window_days > MAX_ANALYSIS_WINDOW_DAYS:
            raise ValueError(
                f"analysis window exceeds {MAX_ANALYSIS_WINDOW_DAYS} days: {window_days}"
            )
        if len(self.expected_slot_labels) > MAX_PROFILE_SLOT_LABELS:
            raise ValueError("expected_slot_labels exceeds the bounded grid size")
        if list(self.expected_slot_labels) != sorted(set(self.expected_slot_labels)):
            raise ValueError("expected_slot_labels must be sorted and unique")
        for label in self.expected_slot_labels:
            if re.fullmatch(_SLOT_LABEL_PATTERN, label) is None:
                raise ValueError(f"invalid slot label: {label!r}")
        if len(self.declared_excluded_dates) > MAX_DECLARED_EXCLUDED_DATES:
            raise ValueError("declared_excluded_dates exceeds the bounded size")
        excluded_dates = [item.date for item in self.declared_excluded_dates]
        if excluded_dates != sorted(set(excluded_dates)):
            raise ValueError("declared_excluded_dates must be sorted and unique by date")
        for item in self.declared_excluded_dates:
            if not (self.window_start_date <= item.date <= self.window_end_date):
                raise ValueError(f"declared excluded date outside window: {item.date}")
        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("unit does not match the declared measure")
        if self.time_basis != _SOURCE_TIME_BASES[self.source]:
            raise ValueError("time_basis does not match the structural source clock semantics")
        return self


class TemporalProfileObservation(ManchesterTemporalProfileModel):
    """One source-specific observation offered to the profile builder."""

    source: ProfileSource
    source_record_id: str = Field(pattern=_IDENTIFIER_PATTERN)
    source_date: dt.date
    slot_label: str = Field(pattern=_SLOT_LABEL_PATTERN)
    measure: ProfileMeasure
    unit: ProfileUnit
    value: Decimal | None
    snapshot_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    parser_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def validate_value(self) -> TemporalProfileObservation:
        """Keep values finite, bounded, and unit-consistent."""

        if self.unit != _MEASURE_UNITS[self.measure]:
            raise ValueError("unit does not match the declared measure")
        if self.value is not None:
            if not self.value.is_finite():
                raise ValueError("value must be finite")
            if self.value < 0 or abs(self.value) > _MAX_ABSOLUTE_VALUE:
                raise ValueError("value is negative or outside the bounded range")
        return self


class ExcludedProfileObservation(ManchesterTemporalProfileModel):
    """One observation excluded from the profile with its exact typed reason."""

    reason: ProfileExclusionReason
    observation: TemporalProfileObservation


class TemporalProfileCell(ManchesterTemporalProfileModel):
    """One (season, day-type, slot) cell with complete availability truth."""

    season: Season
    day_type: DayType
    slot_label: str = Field(pattern=_SLOT_LABEL_PATTERN)
    state: CellState
    observation_count: int = Field(ge=0)
    contributing_dates: tuple[dt.date, ...]
    mean_value: Decimal | None
    minimum_value: Decimal | None
    maximum_value: Decimal | None

    @model_validator(mode="after")
    def validate_state_consistency(self) -> TemporalProfileCell:
        """Keep counts, dates, values, and state mutually consistent."""

        if len(self.contributing_dates) != len(set(self.contributing_dates)):
            raise ValueError("contributing_dates must be unique")
        if list(self.contributing_dates) != sorted(self.contributing_dates):
            raise ValueError("contributing_dates must be sorted")
        has_values = self.mean_value is not None
        if self.state == "available":
            if self.observation_count == 0 or not has_values:
                raise ValueError("available cells need observations and values")
        elif self.state == "insufficient_observations":
            if self.observation_count == 0 or has_values:
                raise ValueError("insufficient cells need observations and must not publish values")
        else:
            if self.observation_count != 0 or self.contributing_dates or has_values:
                raise ValueError("no_observations cells must stay empty and value-free")
        if (self.minimum_value is None) != (self.mean_value is None) or (
            self.maximum_value is None
        ) != (self.mean_value is None):
            raise ValueError("mean, minimum, and maximum availability must agree")
        return self


class ManchesterTemporalProfileReport(ManchesterTemporalProfileModel):
    """Complete deterministic profile report re-derived on every reload."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["manchester-temporal-profile-1.0"] = "manchester-temporal-profile-1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    capability_status: Literal["planned"] = "planned"
    policy: TemporalProfilePolicy
    policy_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    admission: ProfileAdmission
    admitted_observations: tuple[TemporalProfileObservation, ...]
    excluded_observations: tuple[ExcludedProfileObservation, ...]
    cells: tuple[TemporalProfileCell, ...]
    offered_observation_count: int = Field(ge=0)
    admitted_observation_count: int = Field(ge=0)
    excluded_observation_count: int = Field(ge=0)
    collapsed_duplicate_count: int = Field(ge=0)
    utc_projection_available: bool
    calibration_use_available: Literal[False] = False
    sumo_demand_available: Literal[False] = False
    baseline_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_complete_re_derivation(self) -> ManchesterTemporalProfileReport:
        """Re-derive the complete partition so stored reports stay tamper-evident."""

        if self.policy_fingerprint != self.policy.fingerprint():
            raise ValueError("policy fingerprint does not match the embedded policy")
        excluded_dates = {item.date for item in self.policy.declared_excluded_dates}
        for row in self.admitted_observations:
            in_window = (
                self.policy.window_start_date <= row.source_date <= self.policy.window_end_date
            )
            if (
                not in_window
                or row.slot_label not in self.policy.expected_slot_labels
                or row.source_date in excluded_dates
                or row.value is None
            ):
                raise ValueError("an embedded admitted observation fails policy admission")
        for item in self.excluded_observations:
            row = item.observation
            if item.reason == "outside_analysis_window":
                in_window = (
                    self.policy.window_start_date <= row.source_date <= self.policy.window_end_date
                )
                if in_window:
                    raise ValueError("an outside-window exclusion is inside the window")
            elif item.reason == "unknown_slot_label":
                if row.slot_label in self.policy.expected_slot_labels:
                    raise ValueError("an unknown-slot exclusion uses a known slot label")
            elif item.reason == "declared_excluded_date":
                if row.source_date not in excluded_dates:
                    raise ValueError("a declared-date exclusion uses an undeclared date")
            elif item.reason == "null_value_retained":
                if row.value is not None:
                    raise ValueError("a null-value exclusion carries a present value")
        derived = _derive(self.policy, self.admitted_observations)
        if derived.admission != self.admission:
            raise ValueError("admission does not re-derive from the embedded policy")
        if derived.cells != self.cells:
            raise ValueError("cells do not re-derive from the embedded observations")
        expected_offered = (
            self.admitted_observation_count
            + self.excluded_observation_count
            + self.collapsed_duplicate_count
        )
        if self.offered_observation_count != expected_offered:
            raise ValueError("offered observations do not reconcile with the partition")
        if self.admitted_observation_count != len(self.admitted_observations):
            raise ValueError("admitted count does not match the embedded observations")
        if self.excluded_observation_count != len(self.excluded_observations):
            raise ValueError("excluded count does not match the embedded exclusions")
        if self.utc_projection_available != (self.policy.time_basis == "utc"):
            raise ValueError("utc_projection_available must follow the policy time basis")
        return self

    def cells_by_state(self) -> dict[CellState, int]:
        """Return the visible cell-state inventory."""

        counts: dict[CellState, int] = {
            "available": 0,
            "insufficient_observations": 0,
            "no_observations": 0,
        }
        for cell in self.cells:
            counts[cell.state] += 1
        return counts


class _Derived:
    __slots__ = ("admission", "cells")

    def __init__(self, admission: ProfileAdmission, cells: tuple[TemporalProfileCell, ...]) -> None:
        self.admission = admission
        self.cells = cells


def day_type_for(date: dt.date) -> DayType:
    """Classify one exact date with the fixed v1 ISO weekday rule."""

    weekday = date.isoweekday()
    if weekday <= 5:
        return "weekday"
    return "saturday" if weekday == 6 else "sunday"


def season_for(date: dt.date, season_rule: str) -> Season:
    """Classify one exact date under the versioned season rule."""

    if season_rule == "none":
        return "all_year"
    return _MONTH_SEASONS[date.month]


def build_temporal_profile(
    policy: TemporalProfilePolicy,
    observations: Sequence[TemporalProfileObservation],
) -> ManchesterTemporalProfileReport:
    """Partition observations into a complete, re-derivable temporal profile."""

    if len(observations) > MAX_PROFILE_OBSERVATIONS:
        raise ManchesterTemporalProfileError(
            "OBSERVATIONS_OVERSIZED",
            f"more than {MAX_PROFILE_OBSERVATIONS} observations were offered",
        )
    for observation in observations:
        if observation.source != policy.source:
            raise ManchesterTemporalProfileError(
                "SOURCE_MISMATCH",
                "observation source does not match the profile policy source",
            )
        if observation.measure != policy.measure or observation.unit != policy.unit:
            raise ManchesterTemporalProfileError(
                "MEASURE_MISMATCH",
                "observation measure/unit does not match the profile policy",
            )

    excluded_dates = {item.date: item for item in policy.declared_excluded_dates}
    admitted: list[TemporalProfileObservation] = []
    excluded: list[ExcludedProfileObservation] = []
    collapsed_duplicates = 0

    def _identity(row: TemporalProfileObservation) -> tuple[object, ...]:
        return (row.source_record_id, row.source_date, row.slot_label)

    ordered = sorted(
        observations,
        key=lambda row: (
            row.source_date.isoformat(),
            row.slot_label,
            row.source_record_id,
            "" if row.value is None else str(row.value),
        ),
    )
    by_identity: dict[tuple[object, ...], list[TemporalProfileObservation]] = {}
    for row in ordered:
        by_identity.setdefault(_identity(row), []).append(row)

    for rows in by_identity.values():
        distinct = sorted(
            {row.canonical_json() for row in rows},
        )
        if len(distinct) > 1:
            excluded.extend(
                ExcludedProfileObservation(reason="conflicting_duplicate_rows", observation=row)
                for row in rows
            )
            continue
        collapsed_duplicates += len(rows) - 1
        row = rows[0]
        if not (policy.window_start_date <= row.source_date <= policy.window_end_date):
            excluded.append(
                ExcludedProfileObservation(reason="outside_analysis_window", observation=row)
            )
        elif row.slot_label not in policy.expected_slot_labels:
            excluded.append(
                ExcludedProfileObservation(reason="unknown_slot_label", observation=row)
            )
        elif row.source_date in excluded_dates:
            excluded.append(
                ExcludedProfileObservation(reason="declared_excluded_date", observation=row)
            )
        elif row.value is None:
            excluded.append(
                ExcludedProfileObservation(reason="null_value_retained", observation=row)
            )
        else:
            admitted.append(row)

    admitted_tuple = tuple(
        sorted(
            admitted,
            key=lambda row: (row.source_date.isoformat(), row.slot_label, row.source_record_id),
        )
    )
    excluded_tuple = tuple(
        sorted(
            excluded,
            key=lambda item: (
                item.reason,
                item.observation.source_date.isoformat(),
                item.observation.slot_label,
                item.observation.source_record_id,
                "" if item.observation.value is None else str(item.observation.value),
            ),
        )
    )
    derived = _derive(policy, admitted_tuple)
    return ManchesterTemporalProfileReport(
        policy=policy,
        policy_fingerprint=policy.fingerprint(),
        admission=derived.admission,
        admitted_observations=admitted_tuple,
        excluded_observations=excluded_tuple,
        cells=derived.cells,
        offered_observation_count=len(observations),
        admitted_observation_count=len(admitted_tuple),
        excluded_observation_count=len(excluded_tuple),
        collapsed_duplicate_count=collapsed_duplicates,
        utc_projection_available=policy.time_basis == "utc",
    )


def _derive(
    policy: TemporalProfilePolicy,
    admitted: Sequence[TemporalProfileObservation],
) -> _Derived:
    if policy.source == "synthetic_utc_road":
        admission: ProfileAdmission = "synthetic_development_inputs"
    elif policy.fingerprint() in APPROVED_PRODUCTION_PROFILE_POLICY_FINGERPRINTS:
        admission = "approved_production_policy"
    else:
        admission = "not_admitted_production_unapproved"

    expected_keys: list[tuple[Season, DayType]] = []
    seen: set[tuple[Season, DayType]] = set()
    current = policy.window_start_date
    while current <= policy.window_end_date:
        key = (season_for(current, policy.season_rule), day_type_for(current))
        if key not in seen:
            seen.add(key)
            expected_keys.append(key)
        current += dt.timedelta(days=1)
    expected_keys.sort()

    grouped: dict[tuple[Season, DayType, str], list[TemporalProfileObservation]] = {}
    for row in admitted:
        cell_key = (
            season_for(row.source_date, policy.season_rule),
            day_type_for(row.source_date),
            row.slot_label,
        )
        grouped.setdefault(cell_key, []).append(row)

    cells: list[TemporalProfileCell] = []
    for season, day_type in expected_keys:
        for slot_label in policy.expected_slot_labels:
            rows = grouped.get((season, day_type, slot_label), [])
            values = [row.value for row in rows if row.value is not None]
            dates = tuple(sorted({row.source_date for row in rows}))
            if not rows:
                cells.append(
                    TemporalProfileCell(
                        season=season,
                        day_type=day_type,
                        slot_label=slot_label,
                        state="no_observations",
                        observation_count=0,
                        contributing_dates=(),
                        mean_value=None,
                        minimum_value=None,
                        maximum_value=None,
                    )
                )
            elif len(rows) < policy.minimum_cell_observations:
                cells.append(
                    TemporalProfileCell(
                        season=season,
                        day_type=day_type,
                        slot_label=slot_label,
                        state="insufficient_observations",
                        observation_count=len(rows),
                        contributing_dates=dates,
                        mean_value=None,
                        minimum_value=None,
                        maximum_value=None,
                    )
                )
            else:
                with localcontext() as context:
                    context.prec = _DECIMAL_PRECISION
                    total = sum(values, start=Decimal(0))
                    mean = (total / Decimal(len(values))).quantize(
                        PROFILE_VALUE_QUANTUM, rounding=ROUND_HALF_EVEN
                    )
                cells.append(
                    TemporalProfileCell(
                        season=season,
                        day_type=day_type,
                        slot_label=slot_label,
                        state="available",
                        observation_count=len(rows),
                        contributing_dates=dates,
                        mean_value=mean,
                        minimum_value=min(values),
                        maximum_value=max(values),
                    )
                )
    return _Derived(admission, tuple(cells))

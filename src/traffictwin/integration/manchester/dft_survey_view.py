"""Deterministic source-specific views over accepted DfT survey-hour records.

This candidate MAN-02/MAN-08 boundary filters an already parsed DfT raw-count
report. It deliberately does not promote DfT's local clock-hour label to UTC,
aggregate survey days, convert AADF values into demand, fill null counts with
zero, or derive speed. The result is suitable for a thin historical evidence
view, not for canonical replay or SUMO calibration.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, Self, TypeAlias, cast

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.dft import (
    VEHICLE_CLASS_FIELDS,
    DftParseCounts,
    DftRawCountParseReport,
    DftRawCountRecord,
    DirectionCode,
)
from traffictwin.integration.manchester.dft_acquisition import (
    DftAcquisitionError,
    DftAcquisitionResult,
    load_accepted_dft_report,
    open_accepted_dft_snapshot,
)
from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    ManchesterValidationState,
)

DFT_SURVEY_VIEW_SCHEMA_VERSION = "1.0"
DFT_SURVEY_VIEW_METHOD_VERSION = "manchester-dft-survey-view-1.0"
DFT_SURVEY_VIEW_CAPABILITY_ID = "MAN-02"
DFT_SURVEY_VIEW_MAX_ROWS = 100_000

DftVehicleClass: TypeAlias = Literal[
    "pedal_cycles",
    "two_wheeled_motor_vehicles",
    "cars_and_taxis",
    "buses_and_coaches",
    "lgvs",
    "hgvs_2_rigid_axle",
    "hgvs_3_rigid_axle",
    "hgvs_4_or_more_rigid_axle",
    "hgvs_3_or_4_articulated_axle",
    "hgvs_5_articulated_axle",
    "hgvs_6_articulated_axle",
    "all_hgvs",
    "all_motor_vehicles",
]


class DftSurveyViewError(RuntimeError):
    """Display-safe refusal from the historical survey-view boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DftSurveyViewModel(ManchesterSnapshotModel):
    """Strict frozen base for source-specific DfT view artifacts."""


class DftSurveyFilterOptions(DftSurveyViewModel):
    """Exact filter values evidenced by one accepted parser report."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-dft-survey-view-1.0"] = "manchester-dft-survey-view-1.0"
    source_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_status: ManchesterValidationState
    source_record_count: int = Field(ge=0)
    count_point_ids: tuple[int, ...]
    directions: tuple[DirectionCode, ...]
    count_dates: tuple[date, ...]
    hours: tuple[int, ...]
    vehicle_classes_with_any_value: tuple[DftVehicleClass, ...]
    vehicle_classes_complete: tuple[DftVehicleClass, ...]
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    utc_timestamps_available: Literal[False] = False
    measured_speed_available: Literal[False] = False
    aadf_included: Literal[False] = False

    @model_validator(mode="after")
    def validate_options(self) -> Self:
        _require_sorted_unique(
            "count-point IDs", self.count_point_ids, tuple(sorted(self.count_point_ids))
        )
        _require_sorted_unique("directions", self.directions, tuple(sorted(self.directions)))
        _require_sorted_unique("count dates", self.count_dates, tuple(sorted(self.count_dates)))
        _require_sorted_unique("hours", self.hours, tuple(sorted(self.hours)))
        if any(hour < 0 or hour > 23 for hour in self.hours):
            raise ValueError("filter-option hours must be between 0 and 23")
        _require_vehicle_class_order(self.vehicle_classes_with_any_value)
        _require_vehicle_class_order(self.vehicle_classes_complete)
        if not set(self.vehicle_classes_complete).issubset(self.vehicle_classes_with_any_value):
            raise ValueError("complete vehicle classes must be available")
        if self.source_status is ManchesterValidationState.REJECTED:
            raise ValueError("rejected DfT reports cannot provide filter options")
        return self


class DftSurveyViewQuery(DftSurveyViewModel):
    """One explicit bounded selection over DfT historical survey records."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-dft-survey-view-1.0"] = "manchester-dft-survey-view-1.0"
    source_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    count_point_ids: tuple[int, ...] = Field(min_length=1, max_length=512)
    directions: tuple[DirectionCode, ...] = Field(min_length=1, max_length=5)
    count_dates: tuple[date, ...] = Field(min_length=1, max_length=4096)
    hours: tuple[int, ...] = Field(min_length=1, max_length=24)
    vehicle_class: DftVehicleClass
    aggregation_policy: Literal["none_one_source_row_per_output"] = "none_one_source_row_per_output"
    missing_value_policy: Literal["preserve_null_never_zero"] = "preserve_null_never_zero"
    timezone_policy: Literal["retain_undocumented_local_clock_hour"] = (
        "retain_undocumented_local_clock_hour"
    )

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        _require_sorted_unique(
            "count-point IDs", self.count_point_ids, tuple(sorted(self.count_point_ids))
        )
        _require_sorted_unique("directions", self.directions, tuple(sorted(self.directions)))
        _require_sorted_unique("count dates", self.count_dates, tuple(sorted(self.count_dates)))
        _require_sorted_unique("hours", self.hours, tuple(sorted(self.hours)))
        if any(hour < 0 or hour > 23 for hour in self.hours):
            raise ValueError("query hours must be between 0 and 23")
        return self


class DftSurveyObservation(DftSurveyViewModel):
    """One selected source row and one exact source vehicle-class field."""

    source_record_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(min_length=1, max_length=128)
    source_member_path: str = Field(min_length=1, max_length=1000)
    source_member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_row_index: int = Field(ge=0)
    count_point_id: int = Field(ge=1)
    direction: DirectionCode
    count_date: date
    hour: int = Field(ge=0, le=23)
    road_name: str | None = Field(default=None, max_length=200)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    vehicle_class: DftVehicleClass
    count: int | None = Field(default=None, ge=0)
    source_total_motor_vehicles: int | None = Field(default=None, ge=0)
    selected_value_missing: bool
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    source_timezone: None = None
    observed_at_utc: None = None
    interval_seconds: None = None
    measured_speed_mps: None = None
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["survey_hour_raw_count"] = "survey_hour_raw_count"
    missing_filled_with_zero: Literal[False] = False
    aggregation_performed: Literal[False] = False
    aadf_value_used: Literal[False] = False

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.selected_value_missing != (self.count is None):
            raise ValueError("selected-value missingness must match the source count")
        if (
            self.vehicle_class == "all_motor_vehicles"
            and self.count != self.source_total_motor_vehicles
        ):
            raise ValueError("all-motor-vehicles selection must retain its exact source value")
        return self


class DftSurveyViewCounts(DftSurveyViewModel):
    """Complete source-to-selection-to-value reconciliation."""

    source_records: int = Field(ge=0)
    selected_records: int = Field(ge=0)
    records_outside_selection: int = Field(ge=0)
    values_present: int = Field(ge=0)
    values_missing: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.source_records != self.selected_records + self.records_outside_selection:
            raise ValueError("source records must reconcile the exact selection")
        if self.selected_records != self.values_present + self.values_missing:
            raise ValueError("selected records must reconcile present and missing values")
        return self


class DftSurveyView(DftSurveyViewModel):
    """Deterministic non-aggregated historical view bound to its parser report."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    operations_capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-dft-survey-view-1.0"] = "manchester-dft-survey-view-1.0"
    source_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_status: ManchesterValidationState
    source_parse_counts: DftParseCounts
    query: DftSurveyViewQuery
    query_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows: tuple[DftSurveyObservation, ...]
    row_fingerprints: tuple[str, ...]
    counts: DftSurveyViewCounts
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    continuous_time_series_available: Literal[False] = False
    utc_timestamps_available: Literal[False] = False
    measured_speed_available: Literal[False] = False
    aggregation_performed: Literal[False] = False
    missing_filled_with_zero: Literal[False] = False
    aadf_included: Literal[False] = False
    canonical_projection_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_view(self) -> Self:
        if self.source_status is ManchesterValidationState.REJECTED:
            raise ValueError("rejected DfT reports cannot produce a survey view")
        if self.source_report_fingerprint != self.query.source_report_fingerprint:
            raise ValueError("query must bind the exact source report")
        if self.query_fingerprint != self.query.fingerprint():
            raise ValueError("query fingerprint must match the embedded query")
        if self.source_parse_counts.records_accepted != self.counts.source_records:
            raise ValueError("source parse counts must bind the source-record denominator")
        expected_fingerprints = tuple(row.fingerprint() for row in self.rows)
        if self.row_fingerprints != expected_fingerprints:
            raise ValueError("row fingerprints must bind every selected output row")
        keys = tuple(
            (row.count_point_id, row.direction, row.count_date, row.hour) for row in self.rows
        )
        if keys != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("survey-view rows must have sorted unique source keys")
        selections = _selection_sets(self.query)
        if any(not _row_matches_query(row, self.query, selections) for row in self.rows):
            raise ValueError("every survey-view row must match the exact query")
        expected_counts = DftSurveyViewCounts(
            source_records=self.counts.source_records,
            selected_records=len(self.rows),
            records_outside_selection=self.counts.source_records - len(self.rows),
            values_present=sum(row.count is not None for row in self.rows),
            values_missing=sum(row.count is None for row in self.rows),
        )
        if self.counts != expected_counts:
            raise ValueError("survey-view counts must be re-derived from the rows")
        return self


def dft_survey_filter_options(
    report: DftRawCountParseReport,
) -> DftSurveyFilterOptions:
    """Derive exact stable filter values from one non-rejected raw-count report."""

    accepted = _validated_report(report)
    return _filter_options_from_validated(accepted)


def dft_survey_filter_options_from_accepted(
    workspace_root: str | Path,
    acquisition: DftAcquisitionResult,
) -> DftSurveyFilterOptions:
    """Load one accepted local raw-count snapshot and derive its exact filters."""

    return _filter_options_from_validated(_accepted_raw_count_report(workspace_root, acquisition))


def dft_survey_filter_options_from_snapshot(
    workspace_root: str | Path,
    snapshot_id: str,
) -> DftSurveyFilterOptions:
    """Derive filters from one verified accepted local snapshot ID."""

    return _filter_options_from_validated(
        _accepted_raw_count_report_by_id(workspace_root, snapshot_id)
    )


def _filter_options_from_validated(
    accepted: DftRawCountParseReport,
) -> DftSurveyFilterOptions:
    records = accepted.records
    available = tuple(
        cast(DftVehicleClass, name)
        for name in VEHICLE_CLASS_FIELDS
        if any(getattr(record.counts, name) is not None for record in records)
    )
    complete = tuple(
        cast(DftVehicleClass, name)
        for name in VEHICLE_CLASS_FIELDS
        if records and all(getattr(record.counts, name) is not None for record in records)
    )
    return DftSurveyFilterOptions(
        source_report_fingerprint=accepted.fingerprint(),
        source_status=accepted.status,
        source_record_count=len(records),
        count_point_ids=tuple(sorted({record.count_point_id for record in records})),
        directions=tuple(sorted({record.direction_of_travel for record in records})),
        count_dates=tuple(sorted({record.count_date for record in records})),
        hours=tuple(sorted({record.hour for record in records})),
        vehicle_classes_with_any_value=available,
        vehicle_classes_complete=complete,
    )


def build_dft_survey_view(
    report: DftRawCountParseReport,
    query: DftSurveyViewQuery,
) -> DftSurveyView:
    """Filter exact source rows without aggregation, UTC promotion, or null filling."""

    accepted = _validated_report(report)
    request = _validated_query(query)
    options = _filter_options_from_validated(accepted)
    if request.source_report_fingerprint != accepted.fingerprint():
        raise DftSurveyViewError(
            "SOURCE_REPORT_MISMATCH",
            "the filter query does not bind the supplied DfT parser report",
        )
    _require_selected_values("count-point IDs", request.count_point_ids, options.count_point_ids)
    _require_selected_values("directions", request.directions, options.directions)
    _require_selected_values("count dates", request.count_dates, options.count_dates)
    _require_selected_values("hours", request.hours, options.hours)
    if request.vehicle_class not in options.vehicle_classes_with_any_value:
        raise DftSurveyViewError(
            "VEHICLE_CLASS_UNAVAILABLE",
            "the selected vehicle-class field has no value in this DfT report",
        )

    selections = _selection_sets(request)
    selected_rows: list[DftRawCountRecord] = []
    for record in accepted.records:
        if not _source_row_matches_query(record, selections):
            continue
        if len(selected_rows) == DFT_SURVEY_VIEW_MAX_ROWS:
            raise DftSurveyViewError(
                "VIEW_TOO_LARGE",
                "the exact selection exceeds the bounded DfT survey-view row limit",
            )
        selected_rows.append(record)
    selected_source_rows = tuple(selected_rows)
    rows = tuple(_observation(record, request.vehicle_class) for record in selected_source_rows)
    counts = DftSurveyViewCounts(
        source_records=len(accepted.records),
        selected_records=len(rows),
        records_outside_selection=len(accepted.records) - len(rows),
        values_present=sum(row.count is not None for row in rows),
        values_missing=sum(row.count is None for row in rows),
    )
    return DftSurveyView(
        source_report_fingerprint=accepted.fingerprint(),
        source_status=accepted.status,
        source_parse_counts=accepted.counts,
        query=request,
        query_fingerprint=request.fingerprint(),
        rows=rows,
        row_fingerprints=tuple(row.fingerprint() for row in rows),
        counts=counts,
    )


def build_dft_survey_view_from_accepted(
    workspace_root: str | Path,
    acquisition: DftAcquisitionResult,
    query: DftSurveyViewQuery,
) -> DftSurveyView:
    """Build a view from a verified accepted local snapshot without network I/O."""

    return build_dft_survey_view(
        _accepted_raw_count_report(workspace_root, acquisition),
        query,
    )


def build_dft_survey_view_from_snapshot(
    workspace_root: str | Path,
    snapshot_id: str,
    query: DftSurveyViewQuery,
) -> DftSurveyView:
    """Build a survey view from a verified accepted local snapshot ID."""

    return build_dft_survey_view(
        _accepted_raw_count_report_by_id(workspace_root, snapshot_id),
        query,
    )


def validate_dft_survey_view(
    report: DftRawCountParseReport,
    view: DftSurveyView,
) -> DftSurveyView:
    """Re-derive a persisted view from its exact source report and query."""

    try:
        supplied = DftSurveyView.model_validate_json(view.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise DftSurveyViewError(
            "VIEW_INVALID",
            "the supplied DfT survey view failed internal validation",
        ) from exc
    expected = build_dft_survey_view(report, supplied.query)
    if supplied != expected:
        raise DftSurveyViewError(
            "VIEW_SOURCE_MISMATCH",
            "the DfT survey view is not exactly reproducible from its source report",
        )
    return supplied


def _validated_report(report: DftRawCountParseReport) -> DftRawCountParseReport:
    try:
        accepted = DftRawCountParseReport.model_validate_json(report.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise DftSurveyViewError(
            "SOURCE_REPORT_INVALID",
            "the DfT raw-count report failed internal validation",
        ) from exc
    if accepted.status is ManchesterValidationState.REJECTED:
        raise DftSurveyViewError(
            "SOURCE_REPORT_REJECTED",
            "a rejected DfT raw-count report cannot produce historical observations",
        )
    return accepted


def _accepted_raw_count_report(
    workspace_root: str | Path,
    acquisition: DftAcquisitionResult,
) -> DftRawCountParseReport:
    try:
        report = load_accepted_dft_report(workspace_root, acquisition)
    except DftAcquisitionError as exc:
        code = "WORKSPACE_INVALID" if exc.code == "WORKSPACE_INVALID" else "ACCEPTED_SOURCE_INVALID"
        raise DftSurveyViewError(
            code,
            f"the accepted local DfT source could not be reproduced ({exc.code})",
        ) from exc
    if not isinstance(report, DftRawCountParseReport):
        raise DftSurveyViewError(
            "DATASET_REFUSED",
            "the survey view accepts only a DfT raw-count acquisition",
        )
    return _validated_report(report)


def _accepted_raw_count_report_by_id(
    workspace_root: str | Path,
    snapshot_id: str,
) -> DftRawCountParseReport:
    try:
        report = open_accepted_dft_snapshot(workspace_root, snapshot_id).report
    except DftAcquisitionError as exc:
        code = "WORKSPACE_INVALID" if exc.code == "WORKSPACE_INVALID" else "ACCEPTED_SOURCE_INVALID"
        raise DftSurveyViewError(
            code,
            f"the accepted local DfT source could not be reproduced ({exc.code})",
        ) from exc
    if not isinstance(report, DftRawCountParseReport):
        raise DftSurveyViewError(
            "DATASET_REFUSED",
            "the survey view accepts only a DfT raw-count acquisition",
        )
    return _validated_report(report)


def _validated_query(query: DftSurveyViewQuery) -> DftSurveyViewQuery:
    try:
        return DftSurveyViewQuery.model_validate_json(query.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise DftSurveyViewError(
            "QUERY_INVALID",
            "the DfT survey-view query failed internal validation",
        ) from exc


def _source_row_matches_query(
    record: DftRawCountRecord,
    selections: tuple[
        frozenset[int],
        frozenset[DirectionCode],
        frozenset[date],
        frozenset[int],
    ],
) -> bool:
    count_point_ids, directions, count_dates, hours = selections
    return (
        record.count_point_id in count_point_ids
        and record.direction_of_travel in directions
        and record.count_date in count_dates
        and record.hour in hours
    )


def _row_matches_query(
    row: DftSurveyObservation,
    query: DftSurveyViewQuery,
    selections: tuple[
        frozenset[int],
        frozenset[DirectionCode],
        frozenset[date],
        frozenset[int],
    ],
) -> bool:
    count_point_ids, directions, count_dates, hours = selections
    return (
        row.count_point_id in count_point_ids
        and row.direction in directions
        and row.count_date in count_dates
        and row.hour in hours
        and row.vehicle_class == query.vehicle_class
    )


def _selection_sets(
    query: DftSurveyViewQuery,
) -> tuple[
    frozenset[int],
    frozenset[DirectionCode],
    frozenset[date],
    frozenset[int],
]:
    return (
        frozenset(query.count_point_ids),
        frozenset(query.directions),
        frozenset(query.count_dates),
        frozenset(query.hours),
    )


def _observation(
    record: DftRawCountRecord,
    vehicle_class: DftVehicleClass,
) -> DftSurveyObservation:
    value = cast(int | None, getattr(record.counts, vehicle_class))
    return DftSurveyObservation(
        source_record_fingerprint=record.fingerprint(),
        source_snapshot_id=record.source.snapshot_id,
        source_member_path=record.source.member_path,
        source_member_sha256=record.source.member_sha256,
        source_row_index=record.row_index,
        count_point_id=record.count_point_id,
        direction=record.direction_of_travel,
        count_date=record.count_date,
        hour=record.hour,
        road_name=record.location.road_name,
        latitude=record.location.latitude,
        longitude=record.location.longitude,
        vehicle_class=vehicle_class,
        count=value,
        source_total_motor_vehicles=record.counts.all_motor_vehicles,
        selected_value_missing=value is None,
    )


def _require_sorted_unique(
    label: str,
    values: tuple[object, ...],
    expected_order: tuple[object, ...],
) -> None:
    if values != expected_order or len(set(values)) != len(values):
        raise ValueError(f"{label} must be sorted and unique")


def _require_vehicle_class_order(values: tuple[DftVehicleClass, ...]) -> None:
    expected = tuple(name for name in VEHICLE_CLASS_FIELDS if name in set(values))
    if values != expected or len(set(values)) != len(values):
        raise ValueError("vehicle classes must follow the audited source-field order")


def _require_selected_values(
    label: str,
    selected: tuple[object, ...],
    available: tuple[object, ...],
) -> None:
    available_values = set(available)
    unknown = tuple(str(value) for value in selected if value not in available_values)
    if unknown:
        raise DftSurveyViewError(
            "FILTER_VALUE_UNAVAILABLE",
            f"selected {label} are unavailable in the source report: {unknown}",
        )

"""MAN-02 candidate: strict offline parser for audited DfT Manchester road-count evidence.

This module implements only the DfT historical road-count adapter *library*.
It is pure and offline: it consumes exact raw bytes plus snapshot/member
provenance produced by the candidate MAN-01 quarantine/snapshot boundary, and it
performs no network access, no snapshot publication, no freshness computation,
and no SUMO demand conversion. ``MAN-01`` and ``MAN-02`` remain ``planned``.

The implemented schema combines the Gate A audited contract with the bounded
Gate B official fixtures retained under ``tests/fixtures/manchester/dft``
(``docs/integration/manchester-source-gate-a-audit-v0_7.md`` §2, frozen from
the official API documentation, the official "Road Traffic Statistics
Metadata" PDF, and live anonymous samples on 2026-07-22):

- host ``roadtraffic.dft.gov.uk``; endpoints ``/api/raw-counts``,
  ``/api/count-points``, ``/api/average-annual-daily-flow``;
- a Laravel-style pagination envelope (``current_page``, ``per_page``,
  ``total``, ``last_page``, ``next_page_url``, ``data``, …);
- the observed raw-count, count-point, and AADF field sets, including the
  thirteen vehicle-class count columns from ``pedal_cycles`` through
  ``all_motor_vehicles``;
- ``count_date`` as a date-only value and ``hour`` as a local clock-hour label
  with an undocumented timezone (ADR-055 ``local_clock_hour``: never promoted
  to a UTC instant while blocker ``GA-DFT-1`` is open); and
- no measured-speed field anywhere: speed is structurally unavailable here and
  is never derived from road type or speed limits.

Raw survey counts and AADF statistical values are separate record families and
cannot be emitted through each other's parser.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, Self, TypeVar

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterFindingSeverity,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)

DFT_ADAPTER_SCHEMA_VERSION = "1.0"
DFT_ADAPTER_METHOD_VERSION = "manchester-dft-adapter-1.0"
DFT_ADAPTER_CAPABILITY_ID = "MAN-02"
DFT_SOURCE_HOST = "roadtraffic.dft.gov.uk"
DFT_RAW_COUNTS_PATH = "/api/raw-counts"
DFT_COUNT_POINTS_PATH = "/api/count-points"
DFT_AADF_PATH = "/api/average-annual-daily-flow"
MANCHESTER_ONS_CODE = "E08000003"
MANCHESTER_LOCAL_AUTHORITY_ID = 85

MAX_MEMBER_JSON_BYTES = 64_000_000
MAX_PAGES = 10_000
MAX_ROWS = 2_000_000

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"

DirectionCode = Literal["C", "E", "N", "S", "W"]
RoadCategory = Literal["M", "MB", "MCU", "PA", "PM", "TA", "TM"]
RoadType = Literal["Major", "Minor"]

DIRECTION_CODES: tuple[DirectionCode, ...] = ("C", "E", "N", "S", "W")
ROAD_CATEGORIES: tuple[RoadCategory, ...] = ("M", "MB", "MCU", "PA", "PM", "TA", "TM")
ROAD_TYPES: tuple[RoadType, ...] = ("Major", "Minor")

VEHICLE_CLASS_FIELDS = (
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
)
_HGV_COMPONENT_FIELDS = (
    "hgvs_2_rigid_axle",
    "hgvs_3_rigid_axle",
    "hgvs_4_or_more_rigid_axle",
    "hgvs_3_or_4_articulated_axle",
    "hgvs_5_articulated_axle",
    "hgvs_6_articulated_axle",
)
_MOTOR_COMPONENT_FIELDS = (
    "two_wheeled_motor_vehicles",
    "cars_and_taxis",
    "buses_and_coaches",
    "lgvs",
    "all_hgvs",
)

_ENVELOPE_REQUIRED_KEYS = frozenset({"current_page", "per_page", "total", "last_page", "data"})
_ENVELOPE_ALLOWED_KEYS = _ENVELOPE_REQUIRED_KEYS | {
    "from",
    "to",
    "path",
    "first_page_url",
    "last_page_url",
    "next_page_url",
    "prev_page_url",
    "links",
}

_RAW_COUNT_REQUIRED_NON_NULL = (
    "id",
    "count_point_id",
    "direction_of_travel",
    "year",
    "count_date",
    "hour",
    "region_id",
    "local_authority_id",
    "road_category",
    "road_type",
)
_RAW_COUNT_NULLABLE = (
    "road_name",
    "start_junction_road_name",
    "end_junction_road_name",
    "easting",
    "northing",
    "latitude",
    "longitude",
    "link_length_km",
    "link_length_miles",
    *VEHICLE_CLASS_FIELDS,
)
_RAW_COUNT_ALLOWED = frozenset(_RAW_COUNT_REQUIRED_NON_NULL) | frozenset(_RAW_COUNT_NULLABLE)

_COUNT_POINT_REQUIRED_NON_NULL = (
    "id",
    "count_point_id",
    "aadf_year",
    "region_id",
    "local_authority_id",
    "road_category",
    "road_type",
)
_COUNT_POINT_NULLABLE = (
    "road_name",
    "start_junction_road_name",
    "end_junction_road_name",
    "easting",
    "northing",
    "latitude",
    "longitude",
    "link_length_km",
    "link_length_miles",
)
_COUNT_POINT_ALLOWED = frozenset(_COUNT_POINT_REQUIRED_NON_NULL) | frozenset(_COUNT_POINT_NULLABLE)

_AADF_REQUIRED_NON_NULL = (
    "id",
    "count_point_id",
    "year",
    "region_id",
    "local_authority_id",
    "road_category",
    "road_type",
    "estimation_method",
)
_AADF_NULLABLE = (
    "estimation_method_detailed",
    "road_name",
    "start_junction_road_name",
    "end_junction_road_name",
    "easting",
    "northing",
    "latitude",
    "longitude",
    "link_length_km",
    "link_length_miles",
    *VEHICLE_CLASS_FIELDS,
)
_AADF_ALLOWED = frozenset(_AADF_REQUIRED_NON_NULL) | frozenset(_AADF_NULLABLE)


class DftAdapterError(RuntimeError):
    """Caller-side misuse of the adapter (broken lineage, unusable input set)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DftModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-02 artifacts (inherits canonical fingerprints)."""


class DftFinding(DftModel):
    """One typed refusal or observation from deterministic DfT parsing."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=96)
    severity: ManchesterFindingSeverity
    message: str = Field(min_length=1, max_length=500)
    member_path: str | None = Field(default=None, pattern=_MEMBER_PATH_PATTERN)
    row_index: int | None = Field(default=None, ge=0)


class DftMemberRef(DftModel):
    """Exact lineage of one raw snapshot member consumed by the parser."""

    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool


class DftManchesterScope(DftModel):
    """Audited Manchester local-authority scope contract.

    The official DfT local-authorities contract binds Manchester's ONS code
    ``E08000003`` to numeric API identifier ``85``. Both are literals so a
    caller cannot redefine Manchester's boundary.
    """

    ons_code: Literal["E08000003"] = "E08000003"
    local_authority_id: Literal[85] = 85
    binding_basis: Literal["dft-local-authorities-2026-07-22"] = "dft-local-authorities-2026-07-22"


class DftVehicleClassCounts(DftModel):
    """The thirteen audited vehicle-class count columns; null means suppressed/missing."""

    pedal_cycles: int | None = Field(default=None, ge=0)
    two_wheeled_motor_vehicles: int | None = Field(default=None, ge=0)
    cars_and_taxis: int | None = Field(default=None, ge=0)
    buses_and_coaches: int | None = Field(default=None, ge=0)
    lgvs: int | None = Field(default=None, ge=0)
    hgvs_2_rigid_axle: int | None = Field(default=None, ge=0)
    hgvs_3_rigid_axle: int | None = Field(default=None, ge=0)
    hgvs_4_or_more_rigid_axle: int | None = Field(default=None, ge=0)
    hgvs_3_or_4_articulated_axle: int | None = Field(default=None, ge=0)
    hgvs_5_articulated_axle: int | None = Field(default=None, ge=0)
    hgvs_6_articulated_axle: int | None = Field(default=None, ge=0)
    all_hgvs: int | None = Field(default=None, ge=0)
    all_motor_vehicles: int | None = Field(default=None, ge=0)

    def is_complete(self) -> bool:
        """Return True when every audited class column carries a value."""

        return all(getattr(self, name) is not None for name in VEHICLE_CLASS_FIELDS)


class DftRoadLocation(DftModel):
    """Audited road/location descriptors shared by the three record families."""

    road_name: str | None = Field(default=None, max_length=200)
    road_category: RoadCategory
    road_type: RoadType
    start_junction_road_name: str | None = Field(default=None, max_length=200)
    end_junction_road_name: str | None = Field(default=None, max_length=200)
    easting: Decimal | None = Field(default=None, ge=0)
    northing: Decimal | None = Field(default=None, ge=0)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    link_length_km: Decimal | None = Field(default=None, ge=0)
    link_length_miles: Decimal | None = Field(default=None, ge=0)


class DftRawCountRecord(DftModel):
    """One audited survey-hour raw count. Historical evidence only.

    ``hour`` is a local clock-hour label (ADR-055 ``local_clock_hour``); it is
    never a UTC instant while ``GA-DFT-1`` is open. There is no measured-speed
    field in the audited source schema, so speed is structurally unavailable.
    """

    source: DftMemberRef
    row_index: int = Field(ge=0)
    source_row_id: int = Field(ge=0)
    count_point_id: int = Field(ge=1)
    direction_of_travel: DirectionCode
    year: int = Field(ge=1990, le=2100)
    count_date: date
    hour: int = Field(ge=0, le=23)
    time_basis: Literal["local_clock_hour"] = "local_clock_hour"
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["survey_hour_raw_count"] = "survey_hour_raw_count"
    measured_speed_available: Literal[False] = False
    region_id: int = Field(ge=1)
    local_authority_id: int = Field(ge=1)
    ons_code: Literal["E08000003"]
    location: DftRoadLocation
    counts: DftVehicleClassCounts

    @model_validator(mode="after")
    def validate_year_consistency(self) -> Self:
        if self.count_date.year != self.year:
            raise ValueError("count_date and year must agree")
        return self


class DftCountPointRecord(DftModel):
    """One audited Manchester count-point reference row (survey infrastructure)."""

    source: DftMemberRef
    row_index: int = Field(ge=0)
    source_row_id: int = Field(ge=0)
    count_point_id: int = Field(ge=1)
    aadf_year: int = Field(ge=1990, le=2100)
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["count_point_reference"] = "count_point_reference"
    region_id: int = Field(ge=1)
    local_authority_id: int = Field(ge=1)
    ons_code: Literal["E08000003"]
    location: DftRoadLocation


class DftAadfRecord(DftModel):
    """One audited annual-average-daily-flow row.

    This is a statistical estimate, never a survey-hour observation and never
    an instantaneous or SUMO demand value.
    """

    source: DftMemberRef
    row_index: int = Field(ge=0)
    source_row_id: int = Field(ge=0)
    count_point_id: int = Field(ge=1)
    year: int = Field(ge=1990, le=2100)
    time_basis: Literal["date_only"] = "date_only"
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["annual_average_daily_flow"] = "annual_average_daily_flow"
    statistical_not_survey: Literal[True] = True
    measured_speed_available: Literal[False] = False
    estimation_method: str = Field(min_length=1, max_length=200)
    estimation_method_detailed: str | None = Field(default=None, max_length=500)
    region_id: int = Field(ge=1)
    local_authority_id: int = Field(ge=1)
    ons_code: Literal["E08000003"]
    location: DftRoadLocation
    counts: DftVehicleClassCounts


class DftParseCounts(DftModel):
    """Complete deterministic accounting for one parse run."""

    pages: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    rows_excluded_malformed: int = Field(ge=0)
    rows_excluded_out_of_scope: int = Field(ge=0)
    rows_excluded_conflicting: int = Field(ge=0)
    duplicate_rows_collapsed: int = Field(ge=0)
    records_with_incomplete_counts: int = Field(ge=0)


_RecordT = TypeVar("_RecordT", DftRawCountRecord, DftCountPointRecord, DftAadfRecord)


class _DftReportBase(DftModel):
    """Shared strict report envelope for the three DfT record families."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-dft-adapter-1.0"] = "manchester-dft-adapter-1.0"
    source_host: Literal["roadtraffic.dft.gov.uk"] = "roadtraffic.dft.gov.uk"
    scope: DftManchesterScope
    sources: tuple[DftMemberRef, ...] = Field(min_length=1)
    synthetic: bool
    status: ManchesterValidationState
    findings: tuple[DftFinding, ...] = ()
    counts: DftParseCounts

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        keys = [(ref.snapshot_id, ref.member_path) for ref in self.sources]
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError("sources must be sorted and unique")
        if self.synthetic != any(ref.synthetic for ref in self.sources):
            raise ValueError("synthetic must reflect the source snapshots")
        errors = any(f.severity is ManchesterFindingSeverity.ERROR for f in self.findings)
        warnings = any(f.severity is ManchesterFindingSeverity.WARNING for f in self.findings)
        if self.status is ManchesterValidationState.ACCEPTED and (errors or warnings):
            raise ValueError("an accepted report cannot carry warnings or errors")
        if self.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and (
            errors or not warnings
        ):
            raise ValueError("a warning-accepted report requires warnings and no errors")
        if self.status is ManchesterValidationState.REJECTED and not errors:
            raise ValueError("a rejected report requires at least one error finding")
        return self


class DftRawCountParseReport(_DftReportBase):
    """Deterministic result of parsing audited raw-count pages."""

    endpoint_path: Literal["/api/raw-counts"] = "/api/raw-counts"
    records: tuple[DftRawCountRecord, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("counts.records_accepted must equal the record inventory")
        return self


class DftCountPointParseReport(_DftReportBase):
    """Deterministic result of parsing audited count-point pages."""

    endpoint_path: Literal["/api/count-points"] = "/api/count-points"
    records: tuple[DftCountPointRecord, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("counts.records_accepted must equal the record inventory")
        return self


class DftAadfParseReport(_DftReportBase):
    """Deterministic result of parsing audited AADF pages (statistical evidence)."""

    endpoint_path: Literal["/api/average-annual-daily-flow"] = "/api/average-annual-daily-flow"
    records: tuple[DftAadfRecord, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> Self:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("counts.records_accepted must equal the record inventory")
        return self


@dataclass
class _PageMeta:
    current_page: int
    per_page: int
    total: int
    last_page: int
    row_count: int
    member_path: str


@dataclass
class _ParseContext:
    """Mutable per-parse collector; findings become deterministic via final sorting."""

    findings: list[DftFinding] = field(default_factory=list)
    malformed: int = 0
    out_of_scope: int = 0
    conflicting: int = 0
    duplicates_collapsed: int = 0
    incomplete_counts: int = 0

    def add(
        self,
        code: str,
        severity: ManchesterFindingSeverity,
        message: str,
        member_path: str | None = None,
        row_index: int | None = None,
    ) -> None:
        self.findings.append(
            DftFinding(
                code=code,
                severity=severity,
                message=message,
                member_path=member_path,
                row_index=row_index,
            )
        )


def parse_dft_raw_counts(
    members: Sequence[tuple[DftMemberRef, bytes]],
    scope: DftManchesterScope,
) -> DftRawCountParseReport:
    """Parse audited raw-count pages into strict historical survey records."""

    rows, rows_seen, context, refs, pages = _load_pages(members)
    keyed: list[tuple[str, DftRawCountRecord]] = []
    for ref, row_index, row in rows:
        record = _parse_raw_count_row(ref, row_index, row, scope, context)
        if record is not None:
            key = (
                f"{record.count_point_id:012d}|{record.direction_of_travel}"
                f"|{record.count_date.isoformat()}|{record.hour:02d}"
            )
            keyed.append((key, record))
    records = _deduplicate(keyed, context, "raw count")
    records.sort(key=lambda r: (r.count_point_id, r.direction_of_travel, r.count_date, r.hour))
    _flag_incomplete_counts(records, context)
    return DftRawCountParseReport(
        scope=scope,
        sources=refs,
        synthetic=any(ref.synthetic for ref in refs),
        status=_status(context),
        findings=_sorted_findings(context),
        counts=_counts(pages, rows_seen, len(records), context),
        records=tuple(records),
    )


def parse_dft_count_points(
    members: Sequence[tuple[DftMemberRef, bytes]],
    scope: DftManchesterScope,
) -> DftCountPointParseReport:
    """Parse audited count-point pages into strict reference records."""

    rows, rows_seen, context, refs, pages = _load_pages(members)
    keyed: list[tuple[str, DftCountPointRecord]] = []
    for ref, row_index, row in rows:
        record = _parse_count_point_row(ref, row_index, row, scope, context)
        if record is not None:
            keyed.append((f"{record.count_point_id:012d}|{record.aadf_year:04d}", record))
    records = _deduplicate(keyed, context, "count point")
    records.sort(key=lambda r: (r.count_point_id, r.aadf_year))
    return DftCountPointParseReport(
        scope=scope,
        sources=refs,
        synthetic=any(ref.synthetic for ref in refs),
        status=_status(context),
        findings=_sorted_findings(context),
        counts=_counts(pages, rows_seen, len(records), context),
        records=tuple(records),
    )


def parse_dft_aadf(
    members: Sequence[tuple[DftMemberRef, bytes]],
    scope: DftManchesterScope,
) -> DftAadfParseReport:
    """Parse audited AADF pages into strict statistical (non-survey) records."""

    rows, rows_seen, context, refs, pages = _load_pages(members)
    keyed: list[tuple[str, DftAadfRecord]] = []
    for ref, row_index, row in rows:
        record = _parse_aadf_row(ref, row_index, row, scope, context)
        if record is not None:
            keyed.append((f"{record.count_point_id:012d}|{record.year:04d}", record))
    records = _deduplicate(keyed, context, "AADF")
    records.sort(key=lambda r: (r.count_point_id, r.year))
    _flag_incomplete_counts(records, context)
    return DftAadfParseReport(
        scope=scope,
        sources=refs,
        synthetic=any(ref.synthetic for ref in refs),
        status=_status(context),
        findings=_sorted_findings(context),
        counts=_counts(pages, rows_seen, len(records), context),
        records=tuple(records),
    )


def _flag_incomplete_counts(
    records: Sequence[DftRawCountRecord] | Sequence[DftAadfRecord],
    context: _ParseContext,
) -> None:
    for record in records:
        if not record.counts.is_complete():
            context.incomplete_counts += 1
            context.add(
                "COUNTS_INCOMPLETE",
                ManchesterFindingSeverity.WARNING,
                "one or more vehicle-class columns are null; reconciliation unavailable",
                record.source.member_path,
                record.row_index,
            )


def _load_pages(
    members: Sequence[tuple[DftMemberRef, bytes]],
) -> tuple[
    list[tuple[DftMemberRef, int, Mapping[str, object]]],
    int,
    _ParseContext,
    tuple[DftMemberRef, ...],
    int,
]:
    """Verify lineage, decode pages, validate the audited envelope, and order rows."""

    if not members:
        raise DftAdapterError("NO_MEMBERS", "at least one snapshot member is required")
    if len(members) > MAX_PAGES:
        raise DftAdapterError("TOO_MANY_PAGES", f"more than {MAX_PAGES} pages supplied")
    snapshot_ids = {ref.snapshot_id for ref, _payload in members}
    if len(snapshot_ids) != 1:
        raise DftAdapterError(
            "MIXED_SNAPSHOTS", "one parse run cannot combine members from different snapshots"
        )
    synthetic_states = {ref.synthetic for ref, _payload in members}
    if len(synthetic_states) != 1:
        raise DftAdapterError(
            "MIXED_EVIDENCE_CLASS",
            "one parse run cannot combine synthetic and real-source members",
        )
    seen: set[tuple[str, str]] = set()
    for ref, payload in members:
        key = (ref.snapshot_id, ref.member_path)
        if key in seen:
            raise DftAdapterError("DUPLICATE_MEMBER", f"member {ref.member_path!r} supplied twice")
        seen.add(key)
        if len(payload) > MAX_MEMBER_JSON_BYTES:
            raise DftAdapterError(
                "MEMBER_TOO_LARGE", f"member {ref.member_path!r} exceeds the JSON byte bound"
            )
        if sha256_hex(payload) != ref.member_sha256:
            raise DftAdapterError(
                "MEMBER_HASH_MISMATCH",
                f"member {ref.member_path!r} bytes do not match the declared snapshot hash",
            )

    context = _ParseContext()
    pages: list[tuple[_PageMeta, DftMemberRef, list[object]]] = []
    for ref, payload in members:
        decoded = _decode_envelope(ref, payload, context)
        if decoded is not None:
            pages.append((decoded[0], ref, decoded[1]))

    ordered_rows: list[tuple[DftMemberRef, int, Mapping[str, object]]] = []
    rows_seen = 0
    if pages:
        _validate_page_set([meta for meta, _ref, _data in pages], context)
        for _meta, ref, data in sorted(pages, key=lambda item: item[0].current_page):
            for row_index, row in enumerate(data):
                rows_seen += 1
                if isinstance(row, dict):
                    ordered_rows.append((ref, row_index, row))
                else:
                    context.malformed += 1
                    context.add(
                        "MALFORMED_ROW",
                        ManchesterFindingSeverity.ERROR,
                        "data row is not a JSON object",
                        ref.member_path,
                        row_index,
                    )
    if rows_seen > MAX_ROWS:
        raise DftAdapterError("TOO_MANY_ROWS", f"more than {MAX_ROWS} rows supplied")
    refs = tuple(sorted((ref for ref, _p in members), key=lambda r: (r.snapshot_id, r.member_path)))
    return ordered_rows, rows_seen, context, refs, len(members)


def _decode_envelope(
    ref: DftMemberRef, payload: bytes, context: _ParseContext
) -> tuple[_PageMeta, list[object]] | None:
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant {value!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        context.add(
            "MALFORMED_JSON",
            ManchesterFindingSeverity.ERROR,
            "member is not valid UTF-8 JSON",
            ref.member_path,
        )
        return None
    if not isinstance(decoded, dict):
        context.add(
            "MALFORMED_ENVELOPE",
            ManchesterFindingSeverity.ERROR,
            "top-level JSON value is not the audited pagination envelope",
            ref.member_path,
        )
        return None
    keys = set(decoded)
    if keys - _ENVELOPE_ALLOWED_KEYS:
        context.add(
            "UNEXPECTED_ENVELOPE_FIELD",
            ManchesterFindingSeverity.ERROR,
            f"envelope carries {len(keys - _ENVELOPE_ALLOWED_KEYS)} field(s) "
            "outside the audited contract",
            ref.member_path,
        )
        return None
    if _ENVELOPE_REQUIRED_KEYS - keys:
        context.add(
            "MISSING_ENVELOPE_FIELD",
            ManchesterFindingSeverity.ERROR,
            f"envelope is missing {len(_ENVELOPE_REQUIRED_KEYS - keys)} audited field(s)",
            ref.member_path,
        )
        return None
    current_page = decoded["current_page"]
    per_page = decoded["per_page"]
    total = decoded["total"]
    last_page = decoded["last_page"]
    data = decoded["data"]
    if (
        not isinstance(current_page, int)
        or isinstance(current_page, bool)
        or not isinstance(per_page, int)
        or isinstance(per_page, bool)
        or not isinstance(total, int)
        or isinstance(total, bool)
        or not isinstance(last_page, int)
        or isinstance(last_page, bool)
        or not isinstance(data, list)
        or current_page < 1
        or per_page < 1
        or total < 0
        or last_page < 1
        or len(data) > per_page
    ):
        context.add(
            "MALFORMED_ENVELOPE",
            ManchesterFindingSeverity.ERROR,
            "envelope pagination fields violate the audited contract",
            ref.member_path,
        )
        return None
    meta = _PageMeta(current_page, per_page, total, last_page, len(data), ref.member_path)
    return meta, data


def _validate_page_set(metas: list[_PageMeta], context: _ParseContext) -> None:
    if len({(m.per_page, m.total, m.last_page) for m in metas}) != 1:
        context.add(
            "INCONSISTENT_PAGE_SET",
            ManchesterFindingSeverity.ERROR,
            "pages disagree on per_page, total, or last_page",
        )
        return
    page_numbers = sorted(meta.current_page for meta in metas)
    if page_numbers != list(range(1, metas[0].last_page + 1)):
        context.add(
            "INCOMPLETE_PAGE_SET",
            ManchesterFindingSeverity.ERROR,
            "supplied pages are not exactly pages 1..last_page",
        )
        return
    if sum(meta.row_count for meta in metas) != metas[0].total:
        context.add(
            "ROW_TOTAL_MISMATCH",
            ManchesterFindingSeverity.ERROR,
            "combined row count does not equal the envelope total",
        )


def _parse_raw_count_row(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    scope: DftManchesterScope,
    context: _ParseContext,
) -> DftRawCountRecord | None:
    if not _check_row_shape(
        ref, row_index, row, _RAW_COUNT_ALLOWED, _RAW_COUNT_REQUIRED_NON_NULL, context
    ):
        return None
    local_authority_id = _plain_int(row.get("local_authority_id"))
    if local_authority_id is None:
        _malformed(ref, row_index, context, "local_authority_id is not an integer")
        return None
    if local_authority_id != scope.local_authority_id:
        context.out_of_scope += 1
        context.add(
            "OUT_OF_SCOPE_RECORD",
            ManchesterFindingSeverity.ERROR,
            "row local_authority_id is outside the declared Manchester scope",
            ref.member_path,
            row_index,
        )
        return None
    count_date = _parse_count_date(row.get("count_date"))
    if count_date is None:
        context.malformed += 1
        context.add(
            "MALFORMED_DATE",
            ManchesterFindingSeverity.ERROR,
            "count_date is not an audited YYYY-MM-DD calendar date",
            ref.member_path,
            row_index,
        )
        return None
    hour = _plain_int(row.get("hour"))
    if hour is None or not 0 <= hour <= 23:
        context.malformed += 1
        context.add(
            "MALFORMED_HOUR",
            ManchesterFindingSeverity.ERROR,
            "hour is not an audited clock-hour label between 0 and 23",
            ref.member_path,
            row_index,
        )
        return None
    counts = _parse_counts(ref, row_index, row, context)
    if counts is None:
        return None
    location = _parse_location(ref, row_index, row, context)
    if location is None:
        return None
    try:
        return DftRawCountRecord(
            source=ref,
            row_index=row_index,
            source_row_id=_required_int(row, "id"),
            count_point_id=_required_int(row, "count_point_id"),
            direction_of_travel=_direction(row),
            year=_required_int(row, "year"),
            count_date=count_date,
            hour=hour,
            region_id=_required_int(row, "region_id"),
            local_authority_id=local_authority_id,
            ons_code=scope.ons_code,
            location=location,
            counts=counts,
        )
    except (ValueError, TypeError):
        _malformed(ref, row_index, context, "row values violate the audited contract")
        return None


def _parse_count_point_row(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    scope: DftManchesterScope,
    context: _ParseContext,
) -> DftCountPointRecord | None:
    if not _check_row_shape(
        ref, row_index, row, _COUNT_POINT_ALLOWED, _COUNT_POINT_REQUIRED_NON_NULL, context
    ):
        return None
    local_authority_id = _plain_int(row.get("local_authority_id"))
    if local_authority_id is None:
        _malformed(ref, row_index, context, "local_authority_id is not an integer")
        return None
    if local_authority_id != scope.local_authority_id:
        context.out_of_scope += 1
        context.add(
            "OUT_OF_SCOPE_RECORD",
            ManchesterFindingSeverity.ERROR,
            "row local_authority_id is outside the declared Manchester scope",
            ref.member_path,
            row_index,
        )
        return None
    location = _parse_location(ref, row_index, row, context)
    if location is None:
        return None
    try:
        return DftCountPointRecord(
            source=ref,
            row_index=row_index,
            source_row_id=_required_int(row, "id"),
            count_point_id=_required_int(row, "count_point_id"),
            aadf_year=_required_int(row, "aadf_year"),
            region_id=_required_int(row, "region_id"),
            local_authority_id=local_authority_id,
            ons_code=scope.ons_code,
            location=location,
        )
    except (ValueError, TypeError):
        _malformed(ref, row_index, context, "row values violate the audited contract")
        return None


def _parse_aadf_row(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    scope: DftManchesterScope,
    context: _ParseContext,
) -> DftAadfRecord | None:
    if not _check_row_shape(
        ref,
        row_index,
        row,
        _AADF_ALLOWED,
        _AADF_REQUIRED_NON_NULL,
        context,
    ):
        return None
    local_authority_id = _plain_int(row.get("local_authority_id"))
    if local_authority_id is None:
        _malformed(ref, row_index, context, "local_authority_id is not an integer")
        return None
    if local_authority_id != scope.local_authority_id:
        context.out_of_scope += 1
        context.add(
            "OUT_OF_SCOPE_RECORD",
            ManchesterFindingSeverity.ERROR,
            "row local_authority_id is outside the declared Manchester scope",
            ref.member_path,
            row_index,
        )
        return None
    counts = _parse_counts(ref, row_index, row, context)
    if counts is None:
        return None
    location = _parse_location(ref, row_index, row, context)
    if location is None:
        return None
    estimation_method = row.get("estimation_method")
    detailed = row.get("estimation_method_detailed")
    if not isinstance(estimation_method, str) or not (
        detailed is None or isinstance(detailed, str)
    ):
        _malformed(ref, row_index, context, "estimation method fields must be strings")
        return None
    try:
        return DftAadfRecord(
            source=ref,
            row_index=row_index,
            source_row_id=_required_int(row, "id"),
            count_point_id=_required_int(row, "count_point_id"),
            year=_required_int(row, "year"),
            estimation_method=estimation_method,
            estimation_method_detailed=detailed,
            region_id=_required_int(row, "region_id"),
            local_authority_id=local_authority_id,
            ons_code=scope.ons_code,
            location=location,
            counts=counts,
        )
    except (ValueError, TypeError):
        _malformed(ref, row_index, context, "row values violate the audited contract")
        return None


def _malformed(ref: DftMemberRef, row_index: int, context: _ParseContext, message: str) -> None:
    context.malformed += 1
    context.add(
        "MALFORMED_ROW",
        ManchesterFindingSeverity.ERROR,
        message,
        ref.member_path,
        row_index,
    )
    return None


def _check_row_shape(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    allowed: frozenset[str],
    required_non_null: tuple[str, ...],
    context: _ParseContext,
    optional_presence: frozenset[str] = frozenset(),
) -> bool:
    keys = set(row)
    if keys - allowed:
        context.malformed += 1
        context.add(
            "UNEXPECTED_FIELD",
            ManchesterFindingSeverity.ERROR,
            f"row carries {len(keys - allowed)} field(s) outside the audited contract",
            ref.member_path,
            row_index,
        )
        return False
    missing = (allowed - optional_presence) - keys
    if missing:
        context.malformed += 1
        context.add(
            "MISSING_FIELD",
            ManchesterFindingSeverity.ERROR,
            f"row is missing {len(missing)} audited field(s)",
            ref.member_path,
            row_index,
        )
        return False
    null_required = [name for name in required_non_null if row.get(name) is None]
    if null_required:
        context.malformed += 1
        context.add(
            "NULL_REQUIRED_FIELD",
            ManchesterFindingSeverity.ERROR,
            f"{len(null_required)} required field(s) are null",
            ref.member_path,
            row_index,
        )
        return False
    return True


def _parse_counts(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    context: _ParseContext,
) -> DftVehicleClassCounts | None:
    values: dict[str, int | None] = {}
    for name in VEHICLE_CLASS_FIELDS:
        value = row.get(name)
        if value is None:
            values[name] = None
            continue
        parsed = _plain_int(value)
        if parsed is None or parsed < 0:
            context.malformed += 1
            context.add(
                "MALFORMED_COUNT",
                ManchesterFindingSeverity.ERROR,
                f"vehicle-class column {name} is not a non-negative integer or null",
                ref.member_path,
                row_index,
            )
            return None
        values[name] = parsed
    counts = DftVehicleClassCounts.model_validate(values)
    hgv_components = [values[name] for name in _HGV_COMPONENT_FIELDS]
    if (
        counts.all_hgvs is not None
        and all(value is not None for value in hgv_components)
        and sum(value for value in hgv_components if value is not None) != counts.all_hgvs
    ):
        context.malformed += 1
        context.add(
            "INCONSISTENT_HGV_TOTAL",
            ManchesterFindingSeverity.ERROR,
            "all_hgvs does not equal the sum of the six audited HGV columns",
            ref.member_path,
            row_index,
        )
        return None
    motor_components = [values[name] for name in _MOTOR_COMPONENT_FIELDS]
    if (
        counts.all_motor_vehicles is not None
        and all(value is not None for value in motor_components)
        and sum(value for value in motor_components if value is not None)
        != counts.all_motor_vehicles
    ):
        context.malformed += 1
        context.add(
            "INCONSISTENT_MOTOR_TOTAL",
            ManchesterFindingSeverity.ERROR,
            "all_motor_vehicles does not equal the sum of the audited motor classes",
            ref.member_path,
            row_index,
        )
        return None
    return counts


def _parse_location(
    ref: DftMemberRef,
    row_index: int,
    row: Mapping[str, object],
    context: _ParseContext,
) -> DftRoadLocation | None:
    road_category = row.get("road_category")
    road_type = row.get("road_type")
    if road_category not in ROAD_CATEGORIES or road_type not in ROAD_TYPES:
        context.malformed += 1
        context.add(
            "MALFORMED_LOCATION",
            ManchesterFindingSeverity.ERROR,
            "road_category or road_type is outside the audited code lists",
            ref.member_path,
            row_index,
        )
        return None
    try:
        return DftRoadLocation(
            road_name=_optional_str(row, "road_name"),
            road_category=road_category,
            road_type=road_type,
            start_junction_road_name=_optional_str(row, "start_junction_road_name"),
            end_junction_road_name=_optional_str(row, "end_junction_road_name"),
            easting=_optional_decimal(row, "easting"),
            northing=_optional_decimal(row, "northing"),
            latitude=_optional_decimal(row, "latitude"),
            longitude=_optional_decimal(row, "longitude"),
            link_length_km=_optional_decimal(row, "link_length_km"),
            link_length_miles=_optional_decimal(row, "link_length_miles"),
        )
    except (ValueError, TypeError):
        context.malformed += 1
        context.add(
            "MALFORMED_LOCATION",
            ManchesterFindingSeverity.ERROR,
            "road or coordinate values violate the audited contract",
            ref.member_path,
            row_index,
        )
        return None


def _deduplicate(
    keyed: list[tuple[str, _RecordT]],
    context: _ParseContext,
    label: str,
) -> list[_RecordT]:
    by_key: dict[str, list[_RecordT]] = {}
    for key, record in keyed:
        by_key.setdefault(key, []).append(record)
    accepted: list[_RecordT] = []
    for key in sorted(by_key):
        group = by_key[key]
        if len(group) == 1:
            accepted.append(group[0])
            continue
        neutral = {
            record.model_copy(
                update={"source": group[0].source, "row_index": 0, "source_row_id": 0}
            ).fingerprint()
            for record in group
        }
        if len(neutral) == 1:
            accepted.append(group[0])
            context.duplicates_collapsed += len(group) - 1
            context.add(
                "DUPLICATE_ROW",
                ManchesterFindingSeverity.WARNING,
                f"identical duplicate {label} rows collapsed to one",
                group[0].source.member_path,
                group[0].row_index,
            )
        else:
            context.conflicting += len(group)
            context.add(
                "CONFLICTING_DUPLICATE",
                ManchesterFindingSeverity.ERROR,
                f"conflicting {label} rows share one identity key; all are excluded",
                group[0].source.member_path,
                group[0].row_index,
            )
    return accepted


def _counts(pages: int, rows_seen: int, accepted: int, context: _ParseContext) -> DftParseCounts:
    return DftParseCounts(
        pages=pages,
        rows_seen=rows_seen,
        records_accepted=accepted,
        rows_excluded_malformed=context.malformed,
        rows_excluded_out_of_scope=context.out_of_scope,
        rows_excluded_conflicting=context.conflicting,
        duplicate_rows_collapsed=context.duplicates_collapsed,
        records_with_incomplete_counts=context.incomplete_counts,
    )


def _status(context: _ParseContext) -> ManchesterValidationState:
    if any(f.severity is ManchesterFindingSeverity.ERROR for f in context.findings):
        return ManchesterValidationState.REJECTED
    if any(f.severity is ManchesterFindingSeverity.WARNING for f in context.findings):
        return ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    return ManchesterValidationState.ACCEPTED


def _sorted_findings(context: _ParseContext) -> tuple[DftFinding, ...]:
    return tuple(
        sorted(
            context.findings,
            key=lambda f: (
                f.member_path or "",
                -1 if f.row_index is None else f.row_index,
                f.code,
                f.message,
            ),
        )
    )


def _plain_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _required_int(row: Mapping[str, object], name: str) -> int:
    value = _plain_int(row[name])
    if value is None:
        raise ValueError(f"{name} must be an integer")
    return value


def _direction(row: Mapping[str, object]) -> DirectionCode:
    value = row["direction_of_travel"]
    if not isinstance(value, str) or value not in DIRECTION_CODES:
        raise ValueError("direction_of_travel must be one of the audited codes")
    return value


def _optional_str(row: Mapping[str, object], name: str) -> str | None:
    value = row.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string or null")
    return value


def _optional_decimal(row: Mapping[str, object], name: str) -> Decimal | None:
    value = row.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError(f"{name} must be a finite decimal value or null")
    if isinstance(value, str) and (not value or value.strip() != value):
        raise ValueError(f"{name} must be a finite decimal value or null")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a finite decimal value or null") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be a finite decimal value or null")
    return parsed


def _parse_count_date(value: object) -> date | None:
    if not isinstance(value, str) or len(value) != 10:
        return None
    parts = value.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    try:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None

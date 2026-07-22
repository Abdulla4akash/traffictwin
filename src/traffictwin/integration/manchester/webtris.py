"""MAN-03 candidate: strict offline parser for WebTRIS strategic-road evidence.

The parser consumes immutable snapshot members only. It performs no network
access, does not calculate freshness, does not map observations to SUMO, and
never interprets WebTRIS source strings as UTC instants. The supported report
surface is intentionally narrow: one site's complete one-day daily report.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal, cast

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterFindingSeverity,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)

WEBTRIS_ADAPTER_SCHEMA_VERSION = "1.0"
WEBTRIS_ADAPTER_METHOD_VERSION = "manchester-webtris-adapter-1.0"
WEBTRIS_ADAPTER_CAPABILITY_ID = "MAN-03"
WEBTRIS_SOURCE_HOST = "webtris.nationalhighways.co.uk"
WEBTRIS_SITES_PATH = "/api/v1.0/sites/{site_id}"
WEBTRIS_DAILY_REPORT_PATH = "/api/v1.0/reports/daily"
WEBTRIS_DAILY_QUALITY_PATH = "/api/v1.0/quality/daily"
MPH_TO_MPS = Decimal("0.44704")
EXPECTED_DAILY_INTERVALS = 96
MAX_MEMBER_BYTES = 16_000_000
MAX_REPORT_PAGES = 100

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"
_SITE_ID_PATTERN = r"^[1-9][0-9]{0,9}$"
_REPORT_DATE_PATTERN = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T00:00:00$")
_CLOCK_PATTERN = re.compile(r"^(\d{2}):(\d{2}):(\d{2})$")

LENGTH_BIN_FIELDS = (
    "0 - 520 cm",
    "521 - 660 cm",
    "661 - 1160 cm",
    "1160+ cm",
)
SPEED_BIN_FIELDS = (
    "0 - 10 mph",
    "11 - 15 mph",
    "16 - 20 mph",
    "21 - 25 mph",
    "26 - 30 mph",
    "31 - 35 mph",
    "36 - 40 mph",
    "41 - 45 mph",
    "46 - 50 mph",
    "51 - 55 mph",
    "56 - 60 mph",
    "61 - 70 mph",
    "71 - 80 mph",
    "80+ mph",
)
_DAILY_ROW_FIELDS = frozenset(
    {
        "Site Name",
        "Report Date",
        "Time Period Ending",
        "Time Interval",
        "Avg mph",
        "Total Volume",
        *LENGTH_BIN_FIELDS,
        *SPEED_BIN_FIELDS,
    }
)
_SITE_FIELDS = frozenset({"Id", "Name", "Description", "Longitude", "Latitude", "Status"})


class WebtrisAdapterError(RuntimeError):
    """Caller-side misuse or broken snapshot lineage."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class WebtrisModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-03 candidate artifacts."""


class WebtrisMemberRef(WebtrisModel):
    """Exact immutable member lineage consumed by the offline parser."""

    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    member_role: Literal["site", "daily_report", "daily_quality"]
    page_number: int = Field(default=1, ge=1, le=MAX_REPORT_PAGES)
    synthetic: bool


class WebtrisFinding(WebtrisModel):
    """One deterministic parser finding."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=96)
    severity: ManchesterFindingSeverity
    message: str = Field(min_length=1, max_length=500)
    member_path: str | None = Field(default=None, pattern=_MEMBER_PATH_PATTERN)
    row_index: int | None = Field(default=None, ge=0)


class WebtrisDailyScope(WebtrisModel):
    """One bounded site-day report request, without a timezone claim."""

    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str = Field(min_length=1, max_length=120)
    report_date: date
    expected_intervals: Literal[96] = 96
    time_basis: Literal["source_string_undeclared"] = "source_string_undeclared"
    road_domain: Literal["national_highways_strategic_road"] = "national_highways_strategic_road"


class WebtrisSiteRecord(WebtrisModel):
    """One WebTRIS strategic-road measurement-site reference."""

    source: WebtrisMemberRef
    row_index: int = Field(ge=0)
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    name: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=1, max_length=200)
    longitude: Decimal = Field(ge=-180, le=180)
    latitude: Decimal = Field(ge=-90, le=90)
    source_status: Literal["Active", "Inactive"]
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["strategic_road_site_reference"] = "strategic_road_site_reference"
    road_domain: Literal["national_highways_strategic_road"] = "national_highways_strategic_road"


class WebtrisLengthCounts(WebtrisModel):
    """Source vehicle-length bins; null means the API supplied an empty string."""

    cm_0_520: int | None = Field(default=None, ge=0)
    cm_521_660: int | None = Field(default=None, ge=0)
    cm_661_1160: int | None = Field(default=None, ge=0)
    cm_1160_plus: int | None = Field(default=None, ge=0)

    def values(self) -> tuple[int | None, ...]:
        return (self.cm_0_520, self.cm_521_660, self.cm_661_1160, self.cm_1160_plus)


class WebtrisSpeedCounts(WebtrisModel):
    """Exact observed WebTRIS speed-bin contract; null is never zero."""

    mph_0_10: int | None = Field(default=None, ge=0)
    mph_11_15: int | None = Field(default=None, ge=0)
    mph_16_20: int | None = Field(default=None, ge=0)
    mph_21_25: int | None = Field(default=None, ge=0)
    mph_26_30: int | None = Field(default=None, ge=0)
    mph_31_35: int | None = Field(default=None, ge=0)
    mph_36_40: int | None = Field(default=None, ge=0)
    mph_41_45: int | None = Field(default=None, ge=0)
    mph_46_50: int | None = Field(default=None, ge=0)
    mph_51_55: int | None = Field(default=None, ge=0)
    mph_56_60: int | None = Field(default=None, ge=0)
    mph_61_70: int | None = Field(default=None, ge=0)
    mph_71_80: int | None = Field(default=None, ge=0)
    mph_80_plus: int | None = Field(default=None, ge=0)

    def values(self) -> tuple[int | None, ...]:
        return tuple(getattr(self, name) for name in type(self).model_fields)


class WebtrisDailyObservation(WebtrisModel):
    """One source interval, including explicit missing intervals."""

    source: WebtrisMemberRef
    row_index: int = Field(ge=0)
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str = Field(min_length=1, max_length=120)
    report_date_raw: str = Field(min_length=19, max_length=19)
    report_date: date
    time_period_ending_raw: str = Field(min_length=8, max_length=8)
    interval_index: int = Field(ge=0, le=95)
    nominal_interval_seconds: Literal[900] = 900
    time_basis: Literal["source_string_undeclared"] = "source_string_undeclared"
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["strategic_road_interval"] = "strategic_road_interval"
    road_domain: Literal["national_highways_strategic_road"] = "national_highways_strategic_road"
    measurement_state: Literal["observed", "missing"]
    length_counts: WebtrisLengthCounts
    speed_counts: WebtrisSpeedCounts
    average_speed_mph: Decimal | None = Field(default=None, ge=0)
    average_speed_mps: Decimal | None = Field(default=None, ge=0)
    total_volume: int | None = Field(default=None, ge=0)
    length_total_reconciled: bool | None
    speed_total_reconciled: bool | None

    @model_validator(mode="after")
    def validate_measurement(self) -> WebtrisDailyObservation:
        measurements: tuple[object | None, ...] = (
            *self.length_counts.values(),
            *self.speed_counts.values(),
            self.average_speed_mph,
            self.total_volume,
        )
        missing = all(value is None for value in measurements)
        if missing != (self.measurement_state == "missing"):
            raise ValueError("measurement_state must reflect all source measurements")
        if (self.average_speed_mph is None) != (self.average_speed_mps is None):
            raise ValueError("mph and m/s availability must match")
        if self.average_speed_mph is not None and self.average_speed_mps != (
            self.average_speed_mph * MPH_TO_MPS
        ):
            raise ValueError("average_speed_mps must be the exact mph conversion")
        length_values = self.length_counts.values()
        expected_length_reconciliation = (
            None
            if self.total_volume is None or any(value is None for value in length_values)
            else sum(value for value in length_values if value is not None) == self.total_volume
        )
        speed_values = self.speed_counts.values()
        expected_speed_reconciliation = (
            None
            if self.total_volume is None or any(value is None for value in speed_values)
            else sum(value for value in speed_values if value is not None) == self.total_volume
        )
        if self.length_total_reconciled is not expected_length_reconciliation:
            raise ValueError("length_total_reconciled does not reflect source values")
        if self.speed_total_reconciled is not expected_speed_reconciliation:
            raise ValueError("speed_total_reconciled does not reflect source values")
        return self


class WebtrisDailyQuality(WebtrisModel):
    """Published availability percentage, explicitly not an accuracy score."""

    source: WebtrisMemberRef
    row_index: int = Field(ge=0)
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    date_raw: str = Field(min_length=19, max_length=19)
    report_date: date
    availability_percent: int = Field(ge=0, le=100)
    interpretation: Literal["data_availability_percentage"] = "data_availability_percentage"
    sensor_accuracy_claim_available: Literal[False] = False
    traffic_validity_claim_available: Literal[False] = False
    evidence_status: Literal["historical"] = "historical"


class WebtrisParseCounts(WebtrisModel):
    """Complete deterministic accounting for one parser invocation."""

    members: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    rows_malformed: int = Field(ge=0)
    intervals_missing: int = Field(default=0, ge=0)


class _WebtrisReport(WebtrisModel):
    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-adapter-1.0"] = "manchester-webtris-adapter-1.0"
    source_host: Literal["webtris.nationalhighways.co.uk"] = "webtris.nationalhighways.co.uk"
    sources: tuple[WebtrisMemberRef, ...] = Field(min_length=1)
    synthetic: bool
    status: ManchesterValidationState
    findings: tuple[WebtrisFinding, ...] = ()
    counts: WebtrisParseCounts

    @model_validator(mode="after")
    def validate_report(self) -> _WebtrisReport:
        keys = [(ref.snapshot_id, ref.member_path) for ref in self.sources]
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ValueError("sources must be sorted and unique")
        if self.synthetic != self.sources[0].synthetic:
            raise ValueError("synthetic must match the single evidence class")
        has_error = any(f.severity is ManchesterFindingSeverity.ERROR for f in self.findings)
        has_warning = any(f.severity is ManchesterFindingSeverity.WARNING for f in self.findings)
        if self.status is ManchesterValidationState.ACCEPTED and (has_error or has_warning):
            raise ValueError("accepted reports cannot carry findings")
        if self.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and (
            has_error or not has_warning
        ):
            raise ValueError("warning acceptance requires warnings and no errors")
        if self.status is ManchesterValidationState.REJECTED and not has_error:
            raise ValueError("rejected reports require an error")
        return self


class WebtrisSiteParseReport(_WebtrisReport):
    records: tuple[WebtrisSiteRecord, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> WebtrisSiteParseReport:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("records_accepted must match records")
        return self


class WebtrisDailyParseReport(_WebtrisReport):
    scope: WebtrisDailyScope
    records: tuple[WebtrisDailyObservation, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> WebtrisDailyParseReport:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("records_accepted must match records")
        if self.counts.intervals_missing != sum(
            record.measurement_state == "missing" for record in self.records
        ):
            raise ValueError("intervals_missing must match records")
        return self


class WebtrisQualityParseReport(_WebtrisReport):
    scope: WebtrisDailyScope
    records: tuple[WebtrisDailyQuality, ...] = ()

    @model_validator(mode="after")
    def validate_records(self) -> WebtrisQualityParseReport:
        if self.counts.records_accepted != len(self.records):
            raise ValueError("records_accepted must match records")
        return self


def parse_webtris_site(member: tuple[WebtrisMemberRef, bytes]) -> WebtrisSiteParseReport:
    """Parse one exact WebTRIS site response without network access."""

    ref, payload = member
    _verify_members((member,), "site")
    findings: list[WebtrisFinding] = []
    decoded = _decode_object(ref, payload, findings)
    records: list[WebtrisSiteRecord] = []
    rows_seen = 0
    malformed = 0
    if decoded is not None:
        if set(decoded) != {"row_count", "sites"} or not isinstance(decoded.get("sites"), list):
            _add(findings, "MALFORMED_ENVELOPE", "site envelope does not match the contract", ref)
        else:
            rows = cast(list[object], decoded["sites"])
            rows_seen = len(rows)
            if _plain_int(decoded.get("row_count")) != rows_seen:
                _add(findings, "ROW_COUNT_MISMATCH", "site row_count does not match sites", ref)
            for index, row in enumerate(rows):
                record = _parse_site_row(ref, index, row, findings)
                if record is None:
                    malformed += 1
                else:
                    records.append(record)
    if len({record.site_id for record in records}) != len(records):
        _add(findings, "DUPLICATE_SITE", "site response contains duplicate identifiers", ref)
        records = []
    return WebtrisSiteParseReport(
        sources=(ref,),
        synthetic=ref.synthetic,
        status=_status(findings),
        findings=_sorted_findings(findings),
        counts=WebtrisParseCounts(
            members=1,
            rows_seen=rows_seen,
            records_accepted=len(records),
            rows_malformed=malformed,
        ),
        records=tuple(sorted(records, key=lambda record: record.site_id)),
    )


def parse_webtris_daily_report(
    members: Sequence[tuple[WebtrisMemberRef, bytes]],
    scope: WebtrisDailyScope,
) -> WebtrisDailyParseReport:
    """Parse a complete one-site, one-day daily report page set."""

    refs = _verify_members(members, "daily_report")
    findings: list[WebtrisFinding] = []
    records: list[WebtrisDailyObservation] = []
    rows_seen = 0
    malformed = 0
    declared_counts: set[int] = set()
    pages = {ref.page_number for ref in refs}
    expected_pages = set(range(1, max(pages) + 1))
    if pages != expected_pages:
        _add(findings, "INCOMPLETE_PAGE_SET", "report pages must be contiguous from page 1")
    for ref, payload in sorted(members, key=lambda item: item[0].page_number):
        decoded = _decode_object(ref, payload, findings)
        if decoded is None:
            continue
        if set(decoded) != {"Header", "Rows"}:
            _add(findings, "MALFORMED_ENVELOPE", "daily envelope keys do not match", ref)
            continue
        header = decoded.get("Header")
        rows = decoded.get("Rows")
        if not isinstance(header, dict) or not isinstance(rows, list):
            _add(findings, "MALFORMED_ENVELOPE", "Header or Rows has the wrong type", ref)
            continue
        if set(header) != {"row_count", "start_date", "end_date", "links"}:
            _add(findings, "MALFORMED_HEADER", "daily Header keys do not match", ref)
            continue
        count = _plain_int(header.get("row_count"))
        if count is None:
            _add(findings, "MALFORMED_HEADER", "row_count is not an integer", ref)
        else:
            declared_counts.add(count)
        expected_request_date = scope.report_date.strftime("%d%m%Y")
        if (
            header.get("start_date") != expected_request_date
            or header.get("end_date") != expected_request_date
        ):
            _add(findings, "DATE_SCOPE_MISMATCH", "header dates do not match scope", ref)
        if not isinstance(header.get("links"), list):
            _add(findings, "MALFORMED_HEADER", "links is not a list", ref)
        elif not _valid_report_links(header["links"]):
            _add(findings, "MALFORMED_HEADER", "links do not match the ignored link schema", ref)
        for index, row in enumerate(rows):
            rows_seen += 1
            record = _parse_daily_row(ref, index, row, scope, findings)
            if record is None:
                malformed += 1
            else:
                records.append(record)
    if declared_counts != {scope.expected_intervals}:
        _add(findings, "ROW_COUNT_MISMATCH", "daily row_count must be exactly 96")
    interval_ids = [record.interval_index for record in records]
    if len(interval_ids) != len(set(interval_ids)):
        _add(findings, "DUPLICATE_INTERVAL", "daily report contains duplicate intervals")
        records = []
    elif set(interval_ids) != set(range(scope.expected_intervals)):
        _add(findings, "INCOMPLETE_INTERVAL_SET", "daily report must contain intervals 0..95")
    missing = sum(record.measurement_state == "missing" for record in records)
    if missing:
        _add(
            findings,
            "MISSING_INTERVAL_MEASUREMENTS",
            f"{missing} interval(s) contain only source empty strings",
            severity=ManchesterFindingSeverity.WARNING,
        )
    return WebtrisDailyParseReport(
        scope=scope,
        sources=refs,
        synthetic=refs[0].synthetic,
        status=_status(findings),
        findings=_sorted_findings(findings),
        counts=WebtrisParseCounts(
            members=len(refs),
            rows_seen=rows_seen,
            records_accepted=len(records),
            rows_malformed=malformed,
            intervals_missing=missing,
        ),
        records=tuple(sorted(records, key=lambda record: record.interval_index)),
    )


def parse_webtris_daily_quality(
    member: tuple[WebtrisMemberRef, bytes], scope: WebtrisDailyScope
) -> WebtrisQualityParseReport:
    """Parse the source availability percentage for the scoped site-day."""

    ref, payload = member
    _verify_members((member,), "daily_quality")
    findings: list[WebtrisFinding] = []
    decoded = _decode_object(ref, payload, findings)
    records: list[WebtrisDailyQuality] = []
    rows_seen = 0
    malformed = 0
    if decoded is not None:
        if set(decoded) != {"row_count", "Qualities"} or not isinstance(
            decoded.get("Qualities"), list
        ):
            _add(
                findings,
                "MALFORMED_ENVELOPE",
                "quality envelope does not match the contract",
                ref,
            )
        else:
            rows = cast(list[object], decoded["Qualities"])
            rows_seen = len(rows)
            if _plain_int(decoded.get("row_count")) != rows_seen:
                _add(findings, "ROW_COUNT_MISMATCH", "quality row_count mismatch", ref)
            for index, row in enumerate(rows):
                record = _parse_quality_row(ref, index, row, scope, findings)
                if record is None:
                    malformed += 1
                else:
                    records.append(record)
    if len(records) != 1:
        _add(findings, "QUALITY_CARDINALITY", "one quality row is required for one site-day", ref)
    return WebtrisQualityParseReport(
        scope=scope,
        sources=(ref,),
        synthetic=ref.synthetic,
        status=_status(findings),
        findings=_sorted_findings(findings),
        counts=WebtrisParseCounts(
            members=1,
            rows_seen=rows_seen,
            records_accepted=len(records),
            rows_malformed=malformed,
        ),
        records=tuple(records),
    )


def _verify_members(
    members: Sequence[tuple[WebtrisMemberRef, bytes]],
    role: Literal["site", "daily_report", "daily_quality"],
) -> tuple[WebtrisMemberRef, ...]:
    if not members:
        raise WebtrisAdapterError("NO_MEMBERS", "at least one member is required")
    if len(members) > MAX_REPORT_PAGES:
        raise WebtrisAdapterError("TOO_MANY_PAGES", "page bound exceeded")
    refs = tuple(sorted((ref for ref, _payload in members), key=lambda ref: ref.member_path))
    if any(ref.member_role != role for ref in refs):
        raise WebtrisAdapterError("WRONG_MEMBER_ROLE", f"expected {role!r} members")
    if len({ref.snapshot_id for ref in refs}) != 1:
        raise WebtrisAdapterError("MIXED_SNAPSHOTS", "members must come from one snapshot")
    if len({ref.synthetic for ref in refs}) != 1:
        raise WebtrisAdapterError(
            "MIXED_EVIDENCE_CLASS", "synthetic and real-source members cannot be mixed"
        )
    if len({ref.member_path for ref in refs}) != len(refs):
        raise WebtrisAdapterError("DUPLICATE_MEMBER", "member paths must be unique")
    if role == "daily_report" and len({ref.page_number for ref in refs}) != len(refs):
        raise WebtrisAdapterError("DUPLICATE_PAGE", "page numbers must be unique")
    for ref, payload in members:
        if len(payload) > MAX_MEMBER_BYTES:
            raise WebtrisAdapterError("MEMBER_TOO_LARGE", "member byte bound exceeded")
        if sha256_hex(payload) != ref.member_sha256:
            raise WebtrisAdapterError("MEMBER_HASH_MISMATCH", "member bytes changed")
    return refs


def _decode_object(
    ref: WebtrisMemberRef, payload: bytes, findings: list[WebtrisFinding]
) -> Mapping[str, object] | None:
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-standard JSON constant {value!r}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        _add(findings, "MALFORMED_JSON", "member is not strict UTF-8 JSON", ref)
        return None
    if not isinstance(decoded, dict):
        _add(findings, "MALFORMED_ENVELOPE", "top-level JSON must be an object", ref)
        return None
    return decoded


def _parse_site_row(
    ref: WebtrisMemberRef,
    index: int,
    row: object,
    findings: list[WebtrisFinding],
) -> WebtrisSiteRecord | None:
    if not isinstance(row, dict) or set(row) != _SITE_FIELDS:
        _row_error(findings, "SITE_SCHEMA_DRIFT", "site row keys do not match", ref, index)
        return None
    try:
        site_id = row["Id"]
        if not isinstance(site_id, str) or re.fullmatch(_SITE_ID_PATTERN, site_id) is None:
            raise ValueError
        name = _required_text(row["Name"])
        description = _required_text(row["Description"])
        status = row["Status"]
        if status not in ("Active", "Inactive"):
            raise ValueError
        return WebtrisSiteRecord(
            source=ref,
            row_index=index,
            site_id=site_id,
            name=name,
            description=description,
            longitude=_decimal(row["Longitude"]),
            latitude=_decimal(row["Latitude"]),
            source_status=status,
        )
    except (ValueError, TypeError, InvalidOperation):
        _row_error(findings, "MALFORMED_SITE", "site values violate the contract", ref, index)
        return None


def _parse_daily_row(
    ref: WebtrisMemberRef,
    index: int,
    row: object,
    scope: WebtrisDailyScope,
    findings: list[WebtrisFinding],
) -> WebtrisDailyObservation | None:
    if not isinstance(row, dict) or set(row) != _DAILY_ROW_FIELDS:
        _row_error(findings, "DAILY_SCHEMA_DRIFT", "daily row keys do not match", ref, index)
        return None
    try:
        site_name = _required_text(row["Site Name"])
        if site_name != scope.site_name:
            _row_error(
                findings, "SITE_SCOPE_MISMATCH", "row site name is outside scope", ref, index
            )
            return None
        report_date_raw = _required_text(row["Report Date"])
        parsed_date = _source_date(report_date_raw)
        if parsed_date != scope.report_date:
            _row_error(findings, "DATE_SCOPE_MISMATCH", "row date is outside scope", ref, index)
            return None
        ending = _required_text(row["Time Period Ending"])
        _validate_clock(ending)
        interval = _integer_string(row["Time Interval"])
        length_values = [_optional_integer_string(row[name]) for name in LENGTH_BIN_FIELDS]
        speed_values = [_optional_integer_string(row[name]) for name in SPEED_BIN_FIELDS]
        average_mph = _optional_decimal_string(row["Avg mph"])
        total_volume = _optional_integer_string(row["Total Volume"])
        length_counts = WebtrisLengthCounts(
            cm_0_520=length_values[0],
            cm_521_660=length_values[1],
            cm_661_1160=length_values[2],
            cm_1160_plus=length_values[3],
        )
        speed_counts = WebtrisSpeedCounts(
            **dict(zip(WebtrisSpeedCounts.model_fields, speed_values, strict=True))
        )
        length_reconciled = (
            None
            if total_volume is None or any(value is None for value in length_values)
            else sum(value for value in length_values if value is not None) == total_volume
        )
        speed_reconciled = (
            None
            if total_volume is None or any(value is None for value in speed_values)
            else sum(value for value in speed_values if value is not None) == total_volume
        )
        if length_reconciled is False:
            _add(
                findings,
                "LENGTH_TOTAL_MISMATCH",
                "Total Volume does not equal the four length bins",
                ref,
                index,
                ManchesterFindingSeverity.WARNING,
            )
        if speed_reconciled is False:
            _add(
                findings,
                "SPEED_TOTAL_MISMATCH",
                "Total Volume does not equal the speed bins",
                ref,
                index,
                ManchesterFindingSeverity.WARNING,
            )
        measurements = (*length_values, *speed_values, average_mph, total_volume)
        state: Literal["observed", "missing"] = (
            "missing" if all(value is None for value in measurements) else "observed"
        )
        return WebtrisDailyObservation(
            source=ref,
            row_index=index,
            site_id=scope.site_id,
            site_name=site_name,
            report_date_raw=report_date_raw,
            report_date=parsed_date,
            time_period_ending_raw=ending,
            interval_index=interval,
            measurement_state=state,
            length_counts=length_counts,
            speed_counts=speed_counts,
            average_speed_mph=average_mph,
            average_speed_mps=None if average_mph is None else average_mph * MPH_TO_MPS,
            total_volume=total_volume,
            length_total_reconciled=length_reconciled,
            speed_total_reconciled=speed_reconciled,
        )
    except (ValueError, TypeError, InvalidOperation):
        _row_error(findings, "MALFORMED_DAILY_ROW", "daily values violate contract", ref, index)
        return None


def _parse_quality_row(
    ref: WebtrisMemberRef,
    index: int,
    row: object,
    scope: WebtrisDailyScope,
    findings: list[WebtrisFinding],
) -> WebtrisDailyQuality | None:
    if not isinstance(row, dict) or set(row) != {"Date", "Quality"}:
        _row_error(findings, "QUALITY_SCHEMA_DRIFT", "quality row keys do not match", ref, index)
        return None
    try:
        date_raw = _required_text(row["Date"])
        parsed = _source_date(date_raw)
        quality = _plain_int(row["Quality"])
        if parsed != scope.report_date or quality is None:
            raise ValueError
        return WebtrisDailyQuality(
            source=ref,
            row_index=index,
            site_id=scope.site_id,
            date_raw=date_raw,
            report_date=parsed,
            availability_percent=quality,
        )
    except (ValueError, TypeError):
        _row_error(findings, "MALFORMED_QUALITY_ROW", "quality values violate contract", ref, index)
        return None


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("required source text is invalid")
    return value


def _plain_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _integer_string(value: object) -> int:
    parsed = _optional_integer_string(value)
    if parsed is None:
        raise ValueError("required integer string is empty")
    return parsed


def _optional_integer_string(value: object) -> int | None:
    if value == "":
        return None
    if not isinstance(value, str) or not value.isdigit():
        raise ValueError("value is not an integer string or empty")
    return int(value)


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise ValueError("value is not decimal-compatible")
    parsed = Decimal(str(value))
    if not parsed.is_finite():
        raise ValueError("decimal must be finite")
    return parsed


def _optional_decimal_string(value: object) -> Decimal | None:
    if value == "":
        return None
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("value is not a decimal string or empty")
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("decimal must be non-negative and finite")
    return parsed


def _source_date(value: str) -> date:
    matched = _REPORT_DATE_PATTERN.fullmatch(value)
    if matched is None:
        raise ValueError("report date format is invalid")
    return date(*(int(part) for part in matched.groups()))


def _validate_clock(value: str) -> None:
    matched = _CLOCK_PATTERN.fullmatch(value)
    if matched is None:
        raise ValueError("clock format is invalid")
    hour, minute, second = (int(part) for part in matched.groups())
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("clock value is invalid")


def _valid_report_links(value: object) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict) or set(item) != {"href", "rel"}:
            return False
        href = item.get("href")
        relation = item.get("rel")
        if not isinstance(href, str) or not href or len(href) > 2_000:
            return False
        if relation not in ("prevPage", "nextPage"):
            return False
    return True


def _add(
    findings: list[WebtrisFinding],
    code: str,
    message: str,
    ref: WebtrisMemberRef | None = None,
    row_index: int | None = None,
    severity: ManchesterFindingSeverity = ManchesterFindingSeverity.ERROR,
) -> None:
    findings.append(
        WebtrisFinding(
            code=code,
            severity=severity,
            message=message,
            member_path=None if ref is None else ref.member_path,
            row_index=row_index,
        )
    )


def _row_error(
    findings: list[WebtrisFinding],
    code: str,
    message: str,
    ref: WebtrisMemberRef,
    row_index: int,
) -> None:
    _add(findings, code, message, ref, row_index)


def _status(findings: Sequence[WebtrisFinding]) -> ManchesterValidationState:
    if any(f.severity is ManchesterFindingSeverity.ERROR for f in findings):
        return ManchesterValidationState.REJECTED
    if findings:
        return ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    return ManchesterValidationState.ACCEPTED


def _sorted_findings(findings: Sequence[WebtrisFinding]) -> tuple[WebtrisFinding, ...]:
    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.code,
                item.member_path or "",
                -1 if item.row_index is None else item.row_index,
                item.message,
            ),
        )
    )

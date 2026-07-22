"""MAN-04 candidate: strict offline TfGM traffic-signal reference parser.

The parser consumes the exact CSV member extracted from an immutable TfGM
snapshot, or a clearly marked attributed derived sample. It emits static
infrastructure records only: no phase, timing, queue, count, incident, or live
state is representable.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pyproj import Transformer

from traffictwin.integration.manchester.models import (
    ManchesterFindingSeverity,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    sha256_hex,
)

TFGM_SIGNALS_SCHEMA_VERSION = "1.0"
TFGM_SIGNALS_METHOD_VERSION = "manchester-tfgm-signals-1.0"
TFGM_SIGNALS_CAPABILITY_ID = "MAN-04"
TFGM_SIGNALS_DATASET_VERSION = "nov-2025-jan-2026-release"
TFGM_SIGNALS_ARCHIVE_SHA256 = "85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa"
TFGM_SIGNALS_CSV_SHA256 = "c45ad8439c9058a239f7e0ad33f39e2da8d79a80194229ad3b67a50f12fc3a81"
TFGM_SIGNALS_FULL_ROW_COUNT = 2529
TFGM_SIGNALS_ATTRIBUTION = (
    "Contains Transport for Greater Manchester data. Contains OS data © Crown copyright "
    "and database right 2026."
)
TFGM_SIGNALS_OGL_URI = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
MAX_CSV_BYTES = 4_000_000
MAX_SIGNAL_ROWS = 3_000
COORDINATE_TOLERANCE_METRES = 2.5

TFGM_SIGNAL_HEADER = (
    "FRAS_ref",
    "Description",
    "Type",
    "Controller",
    "BUS_GATE",
    "Easting",
    "Northing",
    "Type_Of_Control",
    "Authority",
    "HA_AGENCY_MAINTAINED",
    "Longitude",
    "Latitude",
    "NIS_node",
    "COMMENTS",
    "KRN",
)

SignalType = Literal[
    "Junction", "PCAT", "Pedex", "Pegasus", "Pelican", "Puffin", "Sparrow", "Toucan", "Wig Wag"
]
ControlType = Literal["MOVA", "RMS", "SCOOT", "UTC"]
Authority = Literal[
    "Bolton",
    "Bury",
    "Manchester",
    "Oldham",
    "Rochdale",
    "Salford",
    "Stockport",
    "Tameside",
    "Trafford",
    "Wigan",
]
TfgmAttribution = Literal[
    "Contains Transport for Greater Manchester data. Contains OS data © Crown "
    "copyright and database right 2026."
]

SIGNAL_TYPES: tuple[SignalType, ...] = (
    "Junction",
    "PCAT",
    "Pedex",
    "Pegasus",
    "Pelican",
    "Puffin",
    "Sparrow",
    "Toucan",
    "Wig Wag",
)
CONTROL_TYPES: tuple[ControlType, ...] = ("MOVA", "RMS", "SCOOT", "UTC")
AUTHORITIES: tuple[Authority, ...] = (
    "Bolton",
    "Bury",
    "Manchester",
    "Oldham",
    "Rochdale",
    "Salford",
    "Stockport",
    "Tameside",
    "Trafford",
    "Wigan",
)

_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"
_FRAS_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9/._-]{0,39}$"


class TfgmSignalAdapterError(RuntimeError):
    """Broken lineage or unsupported parser invocation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class TfgmSignalModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-04 candidate artifacts."""


class TfgmSignalMemberRef(TfgmSignalModel):
    """Exact lineage and publication class of the consumed CSV bytes."""

    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    member_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_class: Literal["full_official_csv", "redistributable_derived_sample"]
    source_archive_sha256: Literal[
        "85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa"
    ] = "85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa"
    synthetic: bool

    @model_validator(mode="after")
    def validate_evidence_class(self) -> TfgmSignalMemberRef:
        if self.evidence_class == "full_official_csv" and self.synthetic:
            raise ValueError("the exact official CSV cannot be labelled synthetic")
        return self


class TfgmSignalFinding(TfgmSignalModel):
    """One deterministic parser finding."""

    code: str = Field(pattern=r"^[A-Z0-9_]+$", max_length=96)
    severity: ManchesterFindingSeverity
    message: str = Field(min_length=1, max_length=500)
    row_number: int | None = Field(default=None, ge=2)


class TfgmSignalLocation(TfgmSignalModel):
    """One static TfGM signal-controlled infrastructure location."""

    source: TfgmSignalMemberRef
    row_number: int = Field(ge=2)
    fras_ref: str = Field(pattern=_FRAS_PATTERN)
    description: str = Field(min_length=1, max_length=500)
    signal_type: SignalType
    controller: str | None = Field(default=None, max_length=100)
    bus_gate: str | None = Field(default=None, max_length=100)
    easting_epsg27700: int = Field(ge=0, le=1_000_000)
    northing_epsg27700: int = Field(ge=0, le=2_000_000)
    control_type: ControlType
    authority: Authority
    highways_agency_maintained: str | None = Field(default=None, max_length=100)
    longitude_epsg4326: Decimal = Field(ge=-180, le=180)
    latitude_epsg4326: Decimal = Field(ge=-90, le=90)
    nis_node: int = Field(ge=0)
    comments: str | None = Field(default=None, max_length=500)
    key_route_network: bool | None
    coordinate_crosscheck_passed: Literal[True] = True
    evidence_status: Literal["static_reference"] = "static_reference"
    evidence_kind: Literal["traffic_signal_location"] = "traffic_signal_location"
    live_state_available: Literal[False] = False
    phase_available: Literal[False] = False
    timing_available: Literal[False] = False
    queue_available: Literal[False] = False
    traffic_count_available: Literal[False] = False
    incident_available: Literal[False] = False


class TfgmSignalParseCounts(TfgmSignalModel):
    """Complete accounting for one CSV parse."""

    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    rows_malformed: int = Field(ge=0)
    rows_with_unknown_krn: int = Field(ge=0)
    authorities_present: int = Field(ge=0, le=10)


class TfgmSignalParseReport(TfgmSignalModel):
    """Deterministic parse result for an official CSV or admitted derived sample."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-04"] = "MAN-04"
    method_version: Literal["manchester-tfgm-signals-1.0"] = "manchester-tfgm-signals-1.0"
    dataset_version: Literal["nov-2025-jan-2026-release"] = "nov-2025-jan-2026-release"
    source: TfgmSignalMemberRef
    complete_dataset: bool
    publication_class: Literal["workspace_only_raw", "redistributable_derived"]
    attribution: TfgmAttribution = (
        "Contains Transport for Greater Manchester data. Contains OS data © Crown "
        "copyright and database right 2026."
    )
    ogl_uri: Literal[
        "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
    ] = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
    status: ManchesterValidationState
    findings: tuple[TfgmSignalFinding, ...] = ()
    counts: TfgmSignalParseCounts
    records: tuple[TfgmSignalLocation, ...] = ()

    @model_validator(mode="after")
    def validate_report(self) -> TfgmSignalParseReport:
        expected_complete = self.source.evidence_class == "full_official_csv"
        if self.complete_dataset != expected_complete:
            raise ValueError("complete_dataset must reflect evidence_class")
        expected_publication = (
            "workspace_only_raw" if expected_complete else "redistributable_derived"
        )
        if self.publication_class != expected_publication:
            raise ValueError("publication_class must reflect evidence_class")
        if self.counts.records_accepted != len(self.records):
            raise ValueError("records_accepted must match records")
        if self.counts.authorities_present != len({record.authority for record in self.records}):
            raise ValueError("authorities_present must match records")
        errors = any(f.severity is ManchesterFindingSeverity.ERROR for f in self.findings)
        warnings = any(f.severity is ManchesterFindingSeverity.WARNING for f in self.findings)
        if self.status is ManchesterValidationState.ACCEPTED and (errors or warnings):
            raise ValueError("accepted reports cannot carry findings")
        if self.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and (
            errors or not warnings
        ):
            raise ValueError("warning acceptance requires warnings and no errors")
        if self.status is ManchesterValidationState.REJECTED and not errors:
            raise ValueError("rejected reports require errors")
        return self


def parse_tfgm_signal_csv(
    member: tuple[TfgmSignalMemberRef, bytes],
) -> TfgmSignalParseReport:
    """Parse an exact UTF-8-BOM TfGM signal CSV member without network access."""

    ref, payload = member
    if len(payload) > MAX_CSV_BYTES:
        raise TfgmSignalAdapterError("MEMBER_TOO_LARGE", "CSV byte bound exceeded")
    if sha256_hex(payload) != ref.member_sha256:
        raise TfgmSignalAdapterError("MEMBER_HASH_MISMATCH", "CSV bytes changed")
    if ref.evidence_class == "full_official_csv" and ref.member_sha256 != TFGM_SIGNALS_CSV_SHA256:
        raise TfgmSignalAdapterError(
            "OFFICIAL_CSV_IDENTITY_MISMATCH", "full official CSV hash is not the audited release"
        )

    findings: list[TfgmSignalFinding] = []
    records: list[TfgmSignalLocation] = []
    malformed = 0
    rows_seen = 0
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        _add(findings, "MALFORMED_CSV", "CSV is not UTF-8")
        text = ""
    if payload and not payload.startswith(b"\xef\xbb\xbf"):
        _add(findings, "MISSING_UTF8_BOM", "official CSV header must carry its UTF-8 BOM")
    if "\x00" in text:
        _add(findings, "MALFORMED_CSV", "CSV contains a NUL byte")
        text = ""

    parsed_rows: list[list[str]] = []
    if text:
        try:
            parsed_rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
        except csv.Error:
            _add(findings, "MALFORMED_CSV", "CSV syntax is invalid")
    if not parsed_rows or tuple(parsed_rows[0]) != TFGM_SIGNAL_HEADER:
        _add(findings, "HEADER_MISMATCH", "CSV header does not match the 15-field contract")
    else:
        data_rows = parsed_rows[1:]
        rows_seen = len(data_rows)
        if rows_seen > MAX_SIGNAL_ROWS:
            raise TfgmSignalAdapterError("TOO_MANY_ROWS", "signal row bound exceeded")
        for row_number, values in enumerate(data_rows, start=2):
            record = _parse_row(ref, row_number, values, findings)
            if record is None:
                malformed += 1
            else:
                records.append(record)

    identifiers = [record.fras_ref for record in records]
    if len(identifiers) != len(set(identifiers)):
        _add(findings, "DUPLICATE_FRAS_REF", "FRAS_ref values must be unique")
        records = []
    if ref.evidence_class == "full_official_csv":
        if rows_seen != TFGM_SIGNALS_FULL_ROW_COUNT:
            _add(findings, "FULL_ROW_COUNT_MISMATCH", "official release must contain 2529 rows")
        if {record.authority for record in records} != set(AUTHORITIES):
            _add(findings, "INCOMPLETE_AUTHORITY_SET", "official release must contain all boroughs")
    unknown_krn = sum(record.key_route_network is None for record in records)
    if unknown_krn:
        _add(
            findings,
            "KRN_MISSING",
            f"{unknown_krn} row(s) have an empty KRN value",
            severity=ManchesterFindingSeverity.WARNING,
        )

    status = _status(findings)
    records.sort(key=lambda record: record.fras_ref)
    return TfgmSignalParseReport(
        source=ref,
        complete_dataset=ref.evidence_class == "full_official_csv",
        publication_class=(
            "workspace_only_raw"
            if ref.evidence_class == "full_official_csv"
            else "redistributable_derived"
        ),
        status=status,
        findings=tuple(
            sorted(
                findings,
                key=lambda finding: (
                    finding.code,
                    -1 if finding.row_number is None else finding.row_number,
                    finding.message,
                ),
            )
        ),
        counts=TfgmSignalParseCounts(
            rows_seen=rows_seen,
            records_accepted=len(records),
            rows_malformed=malformed,
            rows_with_unknown_krn=unknown_krn,
            authorities_present=len({record.authority for record in records}),
        ),
        records=tuple(records),
    )


def _parse_row(
    ref: TfgmSignalMemberRef,
    row_number: int,
    values: Sequence[str],
    findings: list[TfgmSignalFinding],
) -> TfgmSignalLocation | None:
    if len(values) != len(TFGM_SIGNAL_HEADER):
        _add(findings, "COLUMN_COUNT_MISMATCH", "row does not contain 15 columns", row_number)
        return None
    row = dict(zip(TFGM_SIGNAL_HEADER, values, strict=True))
    try:
        fras_ref = _required_text(row["FRAS_ref"])
        description = _required_text(row["Description"])
        signal_type = row["Type"]
        control_type = row["Type_Of_Control"]
        authority = row["Authority"]
        if signal_type not in SIGNAL_TYPES:
            raise ValueError("unknown signal type")
        if control_type not in CONTROL_TYPES:
            raise ValueError("unknown control type")
        if authority not in AUTHORITIES:
            raise ValueError("unknown authority")
        easting = _integer(row["Easting"])
        northing = _integer(row["Northing"])
        longitude = _decimal(row["Longitude"])
        latitude = _decimal(row["Latitude"])
        if not _coordinates_reconcile(easting, northing, longitude, latitude):
            _add(
                findings,
                "COORDINATE_MISMATCH",
                "EPSG:27700 and EPSG:4326 coordinates differ by more than 2.5 m",
                row_number,
            )
            return None
        krn = _optional_yes_no(row["KRN"])
        return TfgmSignalLocation(
            source=ref,
            row_number=row_number,
            fras_ref=fras_ref,
            description=description,
            signal_type=signal_type,
            controller=_optional_text(row["Controller"]),
            bus_gate=_optional_text(row["BUS_GATE"]),
            easting_epsg27700=easting,
            northing_epsg27700=northing,
            control_type=control_type,
            authority=authority,
            highways_agency_maintained=_optional_text(row["HA_AGENCY_MAINTAINED"]),
            longitude_epsg4326=longitude,
            latitude_epsg4326=latitude,
            nis_node=_integer(row["NIS_node"]),
            comments=_optional_text(row["COMMENTS"]),
            key_route_network=krn,
        )
    except (ValueError, TypeError, InvalidOperation):
        _add(findings, "MALFORMED_ROW", "row values violate the audited contract", row_number)
        return None


def _coordinates_reconcile(
    easting: int, northing: int, longitude: Decimal, latitude: Decimal
) -> bool:
    calculated_longitude, calculated_latitude = _osgb_to_wgs84().transform(easting, northing)
    latitude_float = float(latitude)
    east_west_metres = (
        (calculated_longitude - float(longitude))
        * 111_320
        * math.cos(math.radians(calculated_latitude))
    )
    north_south_metres = (calculated_latitude - latitude_float) * 110_540
    return math.hypot(east_west_metres, north_south_metres) <= COORDINATE_TOLERANCE_METRES


@lru_cache(maxsize=1)
def _osgb_to_wgs84() -> Transformer:
    return Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def _required_text(value: str) -> str:
    if not value or value.strip() != value:
        raise ValueError("required text is empty or padded")
    return value


def _optional_text(value: str) -> str | None:
    if value == "":
        return None
    return _required_text(value)


def _integer(value: str) -> int:
    if not value.isdigit():
        raise ValueError("integer field is malformed")
    return int(value)


def _decimal(value: str) -> Decimal:
    if not value or value.strip() != value:
        raise ValueError("decimal field is malformed")
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise ValueError("decimal field is not finite")
    return parsed


def _optional_yes_no(value: str) -> bool | None:
    if value == "":
        return None
    if value == "Yes":
        return True
    if value == "No":
        return False
    raise ValueError("KRN must be Yes, No, or empty")


def _add(
    findings: list[TfgmSignalFinding],
    code: str,
    message: str,
    row_number: int | None = None,
    severity: ManchesterFindingSeverity = ManchesterFindingSeverity.ERROR,
) -> None:
    findings.append(
        TfgmSignalFinding(
            code=code,
            severity=severity,
            message=message,
            row_number=row_number,
        )
    )


def _status(findings: Sequence[TfgmSignalFinding]) -> ManchesterValidationState:
    if any(finding.severity is ManchesterFindingSeverity.ERROR for finding in findings):
        return ManchesterValidationState.REJECTED
    if findings:
        return ManchesterValidationState.ACCEPTED_WITH_WARNINGS
    return ManchesterValidationState.ACCEPTED

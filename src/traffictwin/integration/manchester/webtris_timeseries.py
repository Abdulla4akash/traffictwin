"""Accepted/replayed WebTRIS daily evidence to bounded MAN-08 historical interval rows.

This module is an offline filter/chart-data boundary. It re-verifies already
accepted or already quarantined-and-replayed MAN-03 daily-report and
daily-quality artifacts, replays the exact MAN-03 parser over the re-read and
re-hashed immutable bytes, and produces deterministic source-specific
historical interval rows for one strict typed filter. It performs no
acquisition, network access, map association, cross-source fusion, cross-site
aggregation, interpolation, resampling, or publication-class upgrade.

Evidence semantics are inherited unchanged from the MAN-03 contracts: WebTRIS
is historical strategic-road evidence; source date/time strings stay verbatim
under time basis ``source_string_undeclared`` while blocker ``GA-WT-1`` is
open and are never promoted to UTC instants; retrieval time never becomes
observation time; source-empty intervals stay ``missing`` and are never filled
with zero; the daily quality percentage remains a data-availability marker and
never becomes a sensor-accuracy or traffic-validity score. Direction and
carriageway exist only as the per-carriageway WebTRIS site identity, so site
selection is the only admitted direction dimension and nothing is decoded from
site names. ``MAN-03`` and ``MAN-08`` remain planned.
"""

from __future__ import annotations

import os
import re
import stat
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    QUARANTINE_MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterSnapshotManifest,
    ManchesterSnapshotModel,
    ManchesterValidationState,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    QUARANTINE_DIRECTORY_NAME,
    ManchesterSnapshotError,
    read_manchester_member,
    verify_manchester_snapshot,
)
from traffictwin.integration.manchester.webtris import (
    EXPECTED_DAILY_INTERVALS,
    MAX_MEMBER_BYTES,
    MAX_REPORT_PAGES,
    MPH_TO_MPS,
    WebtrisAdapterError,
    WebtrisDailyObservation,
    WebtrisDailyParseReport,
    WebtrisDailyScope,
    WebtrisMemberRef,
    WebtrisQualityParseReport,
    parse_webtris_daily_quality,
    parse_webtris_daily_report,
)
from traffictwin.integration.manchester.webtris_acquisition import (
    MAX_QUARANTINE_MANIFEST_BYTES,
    WEBTRIS_ATTRIBUTION_TEXT,
    WEBTRIS_LICENCE_ID,
    WebtrisAcceptedSnapshotLoad,
    WebtrisAcquisitionError,
    WebtrisAcquisitionResult,
    WebtrisReplayResult,
    decode_webtris_http_payload,
    open_accepted_webtris_snapshot,
    replay_webtris_quarantine,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

WEBTRIS_TIMESERIES_SCHEMA_VERSION = "1.0"
WEBTRIS_TIMESERIES_METHOD_VERSION = "manchester-webtris-timeseries-1.0"
WEBTRIS_TIMESERIES_CAPABILITY_ID = "MAN-08"
WEBTRIS_TIMESERIES_SOURCE_CAPABILITY_ID = "MAN-03"

MAX_TIMESERIES_EVIDENCE_ENTRIES = 32
MAX_TIMESERIES_ROWS = MAX_TIMESERIES_EVIDENCE_ENTRIES * EXPECTED_DAILY_INTERVALS
# Daily-report pages plus one quality member per site-day.
MAX_TIMESERIES_INPUT_PAGES = MAX_TIMESERIES_EVIDENCE_ENTRIES * (MAX_REPORT_PAGES + 1)
MAX_FILTER_SITE_IDS = MAX_TIMESERIES_EVIDENCE_ENTRIES
# Inclusive source calendar days; no timezone or UTC projection is implied.
MAX_FILTER_RANGE_DAYS = 366

_SITE_ID_PATTERN = r"^[1-9][0-9]{0,9}$"
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_SHA256_PATTERN = r"^[0-9a-f]{64}$"
_MEMBER_PATH_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}(/[A-Za-z0-9][A-Za-z0-9._-]{0,99}){0,9}$"
_PAGE_MEMBER_PATTERN = re.compile(r"^pages/page-(\d{4})\.json$")
_QUALITY_MEMBER_PATH = "quality/daily-quality.json"
_SOURCE_CLOCK_PATTERN = r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"

WebtrisMeasurementState: TypeAlias = Literal["observed", "missing"]
WebtrisStorageArea: TypeAlias = Literal["accepted", "quarantine"]
WebtrisRowExclusionReason: TypeAlias = Literal[
    "availability_below_minimum",
    "availability_unreported",
    "measurement_state_filtered",
    "outside_date_range",
    "site_not_selected",
]


class WebtrisTimeseriesError(RuntimeError):
    """Display-safe refusal from the WebTRIS historical interval service."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class WebtrisTimeseriesModel(ManchesterSnapshotModel):
    """Strict frozen base for MAN-08 candidate timeseries artifacts."""


class WebtrisTimeseriesFilter(WebtrisTimeseriesModel):
    """Strict typed filter over evidenced dimensions only.

    Every WebTRIS site is a per-carriageway identity, so ``site_ids`` is the
    only admitted direction/carriageway dimension; no letter decoding rule
    exists in any audited contract. UTC windows, vehicle classes, and any
    other dimension without source evidence are structurally unavailable.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-webtris-timeseries-1.0"] = (
        "manchester-webtris-timeseries-1.0"
    )
    site_ids: tuple[str, ...] = Field(min_length=1, max_length=MAX_FILTER_SITE_IDS)
    start_date: date
    end_date: date
    measurement_states: tuple[WebtrisMeasurementState, ...] = Field(min_length=1, max_length=2)
    min_availability_percent: int | None = Field(default=None, ge=0, le=100)
    carriageway_direction_dimension_available: Literal[False] = False
    vehicle_class_dimension_available: Literal[False] = False
    utc_window_dimension_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_filter(self) -> WebtrisTimeseriesFilter:
        if list(self.site_ids) != sorted(set(self.site_ids), key=_site_sort_key):
            raise ValueError("site_ids must be unique and in canonical site order")
        if any(re.fullmatch(_SITE_ID_PATTERN, site_id) is None for site_id in self.site_ids):
            raise ValueError("site_ids must be canonical WebTRIS site identifiers")
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if (self.end_date - self.start_date).days + 1 > MAX_FILTER_RANGE_DAYS:
            raise ValueError("source date range exceeds the filter bound")
        if list(self.measurement_states) != sorted(set(self.measurement_states)):
            raise ValueError("measurement_states must be sorted and unique")
        return self


class WebtrisTimeseriesEvidence(WebtrisTimeseriesModel):
    """One site-day of accepted or replayed WebTRIS acquisition artifacts.

    Exactly one daily-report receipt is required: an acquisition receipt for a
    promoted accepted snapshot, or an offline replay receipt for quarantined
    bytes. A daily-quality receipt is optional and must bind the same site,
    date, site name, and evidence class.
    """

    daily_acquisition: WebtrisAcquisitionResult | None = None
    daily_replay: WebtrisReplayResult | None = None
    quality_acquisition: WebtrisAcquisitionResult | None = None
    quality_replay: WebtrisReplayResult | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> WebtrisTimeseriesEvidence:
        if (self.daily_acquisition is None) == (self.daily_replay is None):
            raise ValueError("exactly one daily-report receipt is required")
        if self.quality_acquisition is not None and self.quality_replay is not None:
            raise ValueError("at most one daily-quality receipt is allowed")
        if self.daily_product() != "daily_report":
            raise ValueError("the daily receipt must be a WebTRIS daily_report product")
        if self.daily_parser_status() is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected daily parse cannot back timeseries evidence")
        if self.quality_supplied():
            if self.quality_product() != "daily_quality":
                raise ValueError("the quality receipt must be a WebTRIS daily_quality product")
            if self.quality_parser_status() is ManchesterValidationState.REJECTED:
                raise ValueError("a rejected quality parse cannot back timeseries evidence")
            if (
                self.quality_site_id() != self.site_id()
                or self.quality_report_date() != self.report_date()
                or self.quality_site_name() != self.site_name()
            ):
                raise ValueError("quality evidence must bind the daily site, name, and date")
            if self.quality_synthetic() != self.synthetic():
                raise ValueError("quality and daily evidence classes must match")
        return self

    def daily_product(self) -> str:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.product
        return _required_replay(self.daily_replay).product

    def quality_supplied(self) -> bool:
        return self.quality_acquisition is not None or self.quality_replay is not None

    def quality_product(self) -> str:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.product
        return _required_replay(self.quality_replay).product

    def site_id(self) -> str:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.request.site_id
        return _required_replay(self.daily_replay).request.site_id

    def site_name(self) -> str:
        if self.daily_acquisition is not None:
            return _required_scope_text(self.daily_acquisition.request.site_name)
        return _required_scope_text(_required_replay(self.daily_replay).request.site_name)

    def report_date(self) -> date:
        if self.daily_acquisition is not None:
            return _required_scope_date(self.daily_acquisition.request.report_date)
        return _required_scope_date(_required_replay(self.daily_replay).request.report_date)

    def synthetic(self) -> bool:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.synthetic
        return _required_replay(self.daily_replay).synthetic

    def daily_storage_area(self) -> WebtrisStorageArea:
        return "accepted" if self.daily_acquisition is not None else "quarantine"

    def daily_snapshot_id(self) -> str:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.snapshot_id
        return _required_replay(self.daily_replay).snapshot_id

    def daily_raw_fingerprint(self) -> str:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.raw_fingerprint
        return _required_replay(self.daily_replay).raw_fingerprint

    def daily_parser_report_fingerprint(self) -> str:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.parser_report_fingerprint
        return _required_replay(self.daily_replay).parser_report_fingerprint

    def daily_parser_status(self) -> ManchesterValidationState:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.parser_status
        return _required_replay(self.daily_replay).parser_status

    def daily_pages(self) -> int:
        if self.daily_acquisition is not None:
            return self.daily_acquisition.pages
        return _required_replay(self.daily_replay).pages

    def quality_storage_area(self) -> WebtrisStorageArea | None:
        if not self.quality_supplied():
            return None
        return "accepted" if self.quality_acquisition is not None else "quarantine"

    def quality_site_id(self) -> str:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.request.site_id
        return _required_replay(self.quality_replay).request.site_id

    def quality_site_name(self) -> str:
        if self.quality_acquisition is not None:
            return _required_scope_text(self.quality_acquisition.request.site_name)
        return _required_scope_text(_required_replay(self.quality_replay).request.site_name)

    def quality_report_date(self) -> date:
        if self.quality_acquisition is not None:
            return _required_scope_date(self.quality_acquisition.request.report_date)
        return _required_scope_date(_required_replay(self.quality_replay).request.report_date)

    def quality_synthetic(self) -> bool:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.synthetic
        return _required_replay(self.quality_replay).synthetic

    def quality_snapshot_id(self) -> str | None:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.snapshot_id
        if self.quality_replay is not None:
            return self.quality_replay.snapshot_id
        return None

    def quality_raw_fingerprint(self) -> str | None:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.raw_fingerprint
        if self.quality_replay is not None:
            return self.quality_replay.raw_fingerprint
        return None

    def quality_parser_report_fingerprint(self) -> str | None:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.parser_report_fingerprint
        if self.quality_replay is not None:
            return self.quality_replay.parser_report_fingerprint
        return None

    def quality_parser_status(self) -> ManchesterValidationState:
        if self.quality_acquisition is not None:
            return self.quality_acquisition.parser_status
        return _required_replay(self.quality_replay).parser_status

    def identity(self) -> tuple[str, ...]:
        """Content identity used for duplicate collapse; storage area excluded."""

        return (
            self.daily_snapshot_id(),
            self.daily_raw_fingerprint(),
            self.daily_parser_report_fingerprint(),
            self.quality_snapshot_id() or "",
            self.quality_raw_fingerprint() or "",
            self.quality_parser_report_fingerprint() or "",
        )


class WebtrisTimeseriesInput(WebtrisTimeseriesModel):
    """Verified per-site-day lineage retained inside the result."""

    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str = Field(min_length=1, max_length=120)
    report_date: date
    synthetic: bool
    publication_class: ManchesterPublicationClass
    daily_storage_area: WebtrisStorageArea
    daily_snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    daily_raw_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    daily_parser_report_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    daily_parser_status: ManchesterValidationState
    daily_pages: int = Field(ge=1, le=MAX_REPORT_PAGES)
    daily_records_accepted: Literal[96] = 96
    daily_intervals_missing: int = Field(ge=0, le=EXPECTED_DAILY_INTERVALS)
    quality_storage_area: WebtrisStorageArea | None = None
    quality_snapshot_id: str | None = Field(default=None, pattern=_SNAPSHOT_ID_PATTERN)
    quality_raw_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    quality_parser_report_fingerprint: str | None = Field(default=None, pattern=_SHA256_PATTERN)
    quality_publication_class: ManchesterPublicationClass | None = None
    availability_percent: int | None = Field(default=None, ge=0, le=100)
    availability_interpretation: Literal["data_availability_percentage"] = (
        "data_availability_percentage"
    )
    sensor_accuracy_claim_available: Literal[False] = False
    traffic_validity_claim_available: Literal[False] = False
    identical_duplicates_collapsed: int = Field(ge=0, le=MAX_TIMESERIES_EVIDENCE_ENTRIES)

    @model_validator(mode="after")
    def validate_input(self) -> WebtrisTimeseriesInput:
        if self.daily_parser_status is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected daily parse cannot be a timeseries input")
        if (
            self.daily_intervals_missing > 0
            and self.daily_parser_status is not ManchesterValidationState.ACCEPTED_WITH_WARNINGS
        ):
            raise ValueError("missing intervals always ride a warning-accepted parse")
        quality_fields = (
            self.quality_storage_area,
            self.quality_snapshot_id,
            self.quality_raw_fingerprint,
            self.quality_parser_report_fingerprint,
            self.quality_publication_class,
            self.availability_percent,
        )
        present = [value is not None for value in quality_fields]
        if any(present) != all(present):
            raise ValueError("quality lineage and availability must be present together")
        return self


class WebtrisIntervalRow(WebtrisTimeseriesModel):
    """One historical WebTRIS source interval prepared for filters and charts."""

    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str = Field(min_length=1, max_length=120)
    report_date: date
    report_date_raw: str = Field(min_length=19, max_length=19)
    time_period_ending_raw: str = Field(pattern=_SOURCE_CLOCK_PATTERN)
    interval_index: int = Field(ge=0, le=95)
    nominal_interval_seconds: Literal[900] = 900
    time_basis: Literal["source_string_undeclared"] = "source_string_undeclared"
    utc_projection_available: Literal[False] = False
    evidence_status: Literal["historical"] = "historical"
    evidence_kind: Literal["strategic_road_interval"] = "strategic_road_interval"
    road_domain: Literal["national_highways_strategic_road"] = "national_highways_strategic_road"
    measurement_state: WebtrisMeasurementState
    total_volume: int | None = Field(default=None, ge=0)
    volume_unit: Literal["vehicles_per_reported_interval"] = "vehicles_per_reported_interval"
    average_speed_mph: Decimal | None = Field(default=None, ge=0)
    average_speed_mps: Decimal | None = Field(default=None, ge=0)
    speed_source_unit: Literal["mph"] = "mph"
    speed_derived_unit: Literal["m_per_s"] = "m_per_s"
    missing_filled_with_zero: Literal[False] = False
    availability_percent: int | None = Field(default=None, ge=0, le=100)
    availability_interpretation: Literal["data_availability_percentage"] = (
        "data_availability_percentage"
    )
    sensor_accuracy_claim_available: Literal[False] = False
    daily_snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    daily_member_path: str = Field(pattern=_MEMBER_PATH_PATTERN)
    daily_member_sha256: str = Field(pattern=_SHA256_PATTERN)
    daily_page_number: int = Field(ge=1, le=MAX_REPORT_PAGES)
    daily_row_index: int = Field(ge=0, le=EXPECTED_DAILY_INTERVALS - 1)
    quality_snapshot_id: str | None = Field(default=None, pattern=_SNAPSHOT_ID_PATTERN)
    synthetic: bool

    @model_validator(mode="after")
    def validate_row(self) -> WebtrisIntervalRow:
        if self.report_date_raw != f"{self.report_date.isoformat()}T00:00:00":
            raise ValueError("report_date_raw must be the exact source string for report_date")
        page_match = _PAGE_MEMBER_PATTERN.fullmatch(self.daily_member_path)
        if page_match is None or int(page_match.group(1)) != self.daily_page_number:
            raise ValueError("daily_member_path must be the page member for daily_page_number")
        if (self.average_speed_mph is None) != (self.average_speed_mps is None):
            raise ValueError("mph and m/s availability must match")
        if self.average_speed_mph is not None and self.average_speed_mps != (
            self.average_speed_mph * MPH_TO_MPS
        ):
            raise ValueError("average_speed_mps must be the exact mph conversion")
        if self.measurement_state == "missing" and (
            self.total_volume is not None or self.average_speed_mph is not None
        ):
            raise ValueError("a missing interval cannot carry volume or speed values")
        if (self.availability_percent is None) != (self.quality_snapshot_id is None):
            raise ValueError("availability must carry its quality snapshot lineage")
        return self


class WebtrisIntervalExclusion(WebtrisTimeseriesModel):
    """One filtered-out source interval with its deterministic reason."""

    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    report_date: date
    interval_index: int = Field(ge=0, le=95)
    reason: WebtrisRowExclusionReason
    excluded_value_replaced_with_zero: Literal[False] = False


class WebtrisExclusionReasonCount(WebtrisTimeseriesModel):
    """Count of excluded rows for one deterministic exclusion reason."""

    reason: WebtrisRowExclusionReason
    rows: int = Field(ge=1, le=MAX_TIMESERIES_ROWS)


class WebtrisTimeseriesCounts(WebtrisTimeseriesModel):
    """Complete reconciliation accounting for one timeseries build."""

    evidence_supplied: int = Field(ge=1, le=MAX_TIMESERIES_EVIDENCE_ENTRIES)
    evidence_admitted: int = Field(ge=1, le=MAX_TIMESERIES_EVIDENCE_ENTRIES)
    identical_duplicates_collapsed: int = Field(ge=0, le=MAX_TIMESERIES_EVIDENCE_ENTRIES)
    input_pages_total: int = Field(ge=1, le=MAX_TIMESERIES_INPUT_PAGES)
    intervals_expected: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    rows_seen: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    rows_admitted: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    rows_excluded: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    intervals_missing_measurement_seen: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    rows_missing_measurement_admitted: int = Field(ge=0, le=MAX_TIMESERIES_ROWS)
    exclusion_reasons: tuple[WebtrisExclusionReasonCount, ...] = ()

    @model_validator(mode="after")
    def validate_counts(self) -> WebtrisTimeseriesCounts:
        if self.evidence_supplied != self.evidence_admitted + self.identical_duplicates_collapsed:
            raise ValueError("supplied evidence must reconcile admitted plus collapsed entries")
        if self.rows_seen != self.intervals_expected:
            raise ValueError("an admitted daily report always contributes 96 intervals")
        if self.rows_seen != self.rows_admitted + self.rows_excluded:
            raise ValueError("every seen row must be admitted or excluded exactly once")
        if self.rows_missing_measurement_admitted > self.intervals_missing_measurement_seen:
            raise ValueError("admitted missing intervals cannot exceed missing intervals seen")
        reasons = [item.reason for item in self.exclusion_reasons]
        if reasons != sorted(set(reasons)):
            raise ValueError("exclusion reasons must be sorted and unique")
        if sum(item.rows for item in self.exclusion_reasons) != self.rows_excluded:
            raise ValueError("exclusion reason counts must reconcile excluded rows")
        return self


class WebtrisTimeseriesResult(WebtrisTimeseriesModel):
    """Deterministic, self-revalidating historical interval result."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    source_capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-timeseries-1.0"] = (
        "manchester-webtris-timeseries-1.0"
    )
    source_host: Literal["webtris.nationalhighways.co.uk"] = "webtris.nationalhighways.co.uk"
    interval_filter: WebtrisTimeseriesFilter
    filter_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    inputs: tuple[WebtrisTimeseriesInput, ...] = Field(
        min_length=1, max_length=MAX_TIMESERIES_EVIDENCE_ENTRIES
    )
    inputs_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    rows: tuple[WebtrisIntervalRow, ...] = Field(default=(), max_length=MAX_TIMESERIES_ROWS)
    rows_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    exclusions: tuple[WebtrisIntervalExclusion, ...] = Field(
        default=(), max_length=MAX_TIMESERIES_ROWS
    )
    counts: WebtrisTimeseriesCounts
    result_state: Literal["rows_available", "empty_after_filters"]
    licence_id: str
    attribution_text: str
    synthetic: bool
    evidence_status: Literal["historical"] = "historical"
    time_basis: Literal["source_string_undeclared"] = "source_string_undeclared"
    utc_timestamps_available: Literal[False] = False
    retrieval_time_used_as_observation_time: Literal[False] = False
    missing_filled_with_zero: Literal[False] = False
    quality_is_accuracy_score: Literal[False] = False
    live_road_traffic_available: Literal[False] = False
    cross_source_fusion_performed: Literal[False] = False
    cross_site_aggregation_performed: Literal[False] = False
    resampling_or_interpolation_performed: Literal[False] = False
    map_association_performed: Literal[False] = False
    city_road_coverage_claimed: Literal[False] = False
    causal_interpretation_available: Literal[False] = False
    carriageway_direction_decoded: Literal[False] = False
    public_export_available: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> WebtrisTimeseriesResult:
        if self.licence_id != WEBTRIS_LICENCE_ID:
            raise ValueError("licence_id must be the audited WebTRIS licence identifier")
        if self.attribution_text != WEBTRIS_ATTRIBUTION_TEXT:
            raise ValueError("attribution_text must be the audited WebTRIS attribution")
        if self.filter_fingerprint != self.interval_filter.fingerprint():
            raise ValueError("filter_fingerprint must bind the embedded filter")
        input_keys = [(item.site_id, item.report_date) for item in self.inputs]
        if input_keys != sorted(set(input_keys), key=_site_day_sort_key):
            raise ValueError("inputs must be unique and in canonical site-day order")
        if self.inputs_fingerprint != _fingerprint_items(self.inputs):
            raise ValueError("inputs_fingerprint must bind the embedded inputs")
        if self.rows_fingerprint != _fingerprint_items(self.rows):
            raise ValueError("rows_fingerprint must bind the embedded rows")
        if any(item.synthetic != self.synthetic for item in self.inputs):
            raise ValueError("inputs must share the result evidence class")
        row_keys = [(row.site_id, row.report_date, row.interval_index) for row in self.rows]
        if row_keys != sorted(set(row_keys), key=_interval_sort_key):
            raise ValueError("rows must be unique and in canonical interval order")
        exclusion_keys = [
            (item.site_id, item.report_date, item.interval_index) for item in self.exclusions
        ]
        if exclusion_keys != sorted(set(exclusion_keys), key=_interval_sort_key):
            raise ValueError("exclusions must be unique and in canonical interval order")
        self._validate_partitions()
        expected_counts = _derive_counts(
            supplied=self.counts.evidence_supplied,
            inputs=self.inputs,
            rows=self.rows,
            exclusions=self.exclusions,
        )
        if self.counts != expected_counts:
            raise ValueError("counts must be re-derived from the embedded inventories")
        expected_state: Literal["rows_available", "empty_after_filters"] = (
            "rows_available" if self.rows else "empty_after_filters"
        )
        if self.result_state != expected_state:
            raise ValueError("result_state must reconcile the admitted row inventory")
        return self

    def _validate_partitions(self) -> None:
        inputs_by_key = {(item.site_id, item.report_date): item for item in self.inputs}
        rows_by_key: dict[tuple[str, date], list[WebtrisIntervalRow]] = {
            key: [] for key in inputs_by_key
        }
        exclusions_by_key: dict[tuple[str, date], list[WebtrisIntervalExclusion]] = {
            key: [] for key in inputs_by_key
        }
        for row in self.rows:
            key = (row.site_id, row.report_date)
            if key not in rows_by_key:
                raise ValueError("every row must belong to exactly one embedded input")
            rows_by_key[key].append(row)
        for exclusion in self.exclusions:
            key = (exclusion.site_id, exclusion.report_date)
            if key not in exclusions_by_key:
                raise ValueError("every exclusion must belong to exactly one embedded input")
            exclusions_by_key[key].append(exclusion)
        for key, input_item in inputs_by_key.items():
            day_rows = rows_by_key[key]
            day_exclusions = exclusions_by_key[key]
            intervals = sorted(
                [row.interval_index for row in day_rows]
                + [item.interval_index for item in day_exclusions]
            )
            if intervals != list(range(EXPECTED_DAILY_INTERVALS)):
                raise ValueError("rows and exclusions must partition intervals 0..95")
            reason, admitted_states = _input_admission(self.interval_filter, input_item)
            if reason is not None:
                if day_rows or {item.reason for item in day_exclusions} != {reason}:
                    raise ValueError("whole-day exclusions must carry the derived reason")
                continue
            if any(item.reason != "measurement_state_filtered" for item in day_exclusions):
                raise ValueError("interval exclusions must carry the derived state reason")
            missing = input_item.daily_intervals_missing
            expected_missing = missing if "missing" in admitted_states else 0
            expected_observed = (
                EXPECTED_DAILY_INTERVALS - missing if "observed" in admitted_states else 0
            )
            admitted_missing = sum(row.measurement_state == "missing" for row in day_rows)
            if (
                len(day_rows) != expected_missing + expected_observed
                or admitted_missing != expected_missing
            ):
                raise ValueError("admitted rows must re-derive from the filter and input")
            for row in day_rows:
                if row.measurement_state not in admitted_states:
                    raise ValueError("admitted rows must satisfy the measurement-state filter")
                if (
                    row.site_name != input_item.site_name
                    or row.synthetic != input_item.synthetic
                    or row.daily_snapshot_id != input_item.daily_snapshot_id
                    or row.daily_page_number > input_item.daily_pages
                    or row.availability_percent != input_item.availability_percent
                    or row.quality_snapshot_id != input_item.quality_snapshot_id
                ):
                    raise ValueError("rows must bind the lineage of their embedded input")


class WebtrisChartPoint(WebtrisTimeseriesModel):
    """One chart point; missing measurements stay gaps, never zero."""

    report_date: date
    report_date_raw: str = Field(min_length=19, max_length=19)
    time_period_ending_raw: str = Field(pattern=_SOURCE_CLOCK_PATTERN)
    interval_index: int = Field(ge=0, le=95)
    measurement_state: WebtrisMeasurementState
    total_volume: int | None = Field(default=None, ge=0)
    average_speed_mph: Decimal | None = Field(default=None, ge=0)
    average_speed_mps: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_point(self) -> WebtrisChartPoint:
        if (self.average_speed_mph is None) != (self.average_speed_mps is None):
            raise ValueError("mph and m/s availability must match")
        if self.average_speed_mph is not None and self.average_speed_mps != (
            self.average_speed_mph * MPH_TO_MPS
        ):
            raise ValueError("average_speed_mps must be the exact mph conversion")
        if self.measurement_state == "missing" and (
            self.total_volume is not None or self.average_speed_mph is not None
        ):
            raise ValueError("a missing point cannot carry volume or speed values")
        return self


class WebtrisChartSeries(WebtrisTimeseriesModel):
    """Per-site chart data with explicit source-local axis semantics."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-08"] = "MAN-08"
    method_version: Literal["manchester-webtris-timeseries-1.0"] = (
        "manchester-webtris-timeseries-1.0"
    )
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str = Field(min_length=1, max_length=120)
    result_fingerprint: str = Field(pattern=_SHA256_PATTERN)
    time_axis_basis: Literal["source_string_undeclared"] = "source_string_undeclared"
    utc_timestamps_available: Literal[False] = False
    evidence_status: Literal["historical"] = "historical"
    volume_unit: Literal["vehicles_per_reported_interval"] = "vehicles_per_reported_interval"
    speed_source_unit: Literal["mph"] = "mph"
    speed_derived_unit: Literal["m_per_s"] = "m_per_s"
    missing_filled_with_zero: Literal[False] = False
    synthetic: bool
    points: tuple[WebtrisChartPoint, ...] = Field(min_length=1, max_length=MAX_TIMESERIES_ROWS)

    @model_validator(mode="after")
    def validate_series(self) -> WebtrisChartSeries:
        keys = [(point.report_date, point.interval_index) for point in self.points]
        if keys != sorted(set(keys)):
            raise ValueError("points must be unique and in source interval order")
        return self


def build_webtris_timeseries(
    workspace_root: str | Path,
    evidence: Sequence[WebtrisTimeseriesEvidence],
    *,
    interval_filter: WebtrisTimeseriesFilter,
) -> WebtrisTimeseriesResult:
    """Re-verify accepted/replayed WebTRIS site-days and build filtered rows.

    The fixed sequence per retained site-day is: re-validate every receipt,
    re-verify the immutable stored bytes and receipt bindings, replay the
    exact MAN-03 parser over the re-read and re-hashed members, compare the
    parser report fingerprint and counts against the receipt, and only then
    emit interval rows. Missing intervals stay missing; conflicting duplicate
    evidence is refused; identical duplicates collapse with their surplus
    reported.
    """

    if not evidence:
        raise WebtrisTimeseriesError("NO_EVIDENCE", "at least one site-day of evidence is required")
    if len(evidence) > MAX_TIMESERIES_EVIDENCE_ENTRIES:
        raise WebtrisTimeseriesError(
            "EVIDENCE_BOUND_EXCEEDED",
            f"at most {MAX_TIMESERIES_EVIDENCE_ENTRIES} evidence entries are admitted",
        )
    workspace = _validated_v07_workspace(workspace_root)
    admitted_filter = _validated_filter(interval_filter)
    validated = tuple(_validated_evidence(entry) for entry in evidence)
    if len({entry.synthetic() for entry in validated}) != 1:
        raise WebtrisTimeseriesError(
            "MIXED_EVIDENCE_CLASS", "synthetic and real-source evidence cannot be mixed"
        )
    retained, collapsed_by_key = _collapse_duplicates(validated)
    total_pages = sum(entry.daily_pages() for entry in retained) + sum(
        1 for entry in retained if entry.quality_supplied()
    )
    if total_pages > MAX_TIMESERIES_INPUT_PAGES:
        raise WebtrisTimeseriesError(
            "INPUT_PAGE_BOUND_EXCEEDED", "combined evidence pages exceed the input bound"
        )
    verified: list[tuple[WebtrisTimeseriesInput, WebtrisDailyParseReport]] = []
    for entry in retained:
        key = (entry.site_id(), entry.report_date())
        input_item, day_report = _verified_input(workspace, entry, collapsed_by_key[key])
        verified.append((input_item, day_report))
    return _assemble_timeseries(
        admitted_filter,
        verified,
        supplied=len(validated),
    )


def build_webtris_timeseries_from_accepted_snapshots(
    workspace_root: str | Path,
    daily_snapshot_ids: Sequence[str],
    *,
    interval_filter: WebtrisTimeseriesFilter,
) -> WebtrisTimeseriesResult:
    """Build historical rows from receipt-free accepted daily snapshots.

    Every ID is reopened through the MAN-03 accepted-snapshot verifier and
    exact daily parser replay. Only ``daily_report`` products are admitted.
    The accepted quality product cannot join here because its stored contract
    lacks the caller-supplied site name required for exact parser replay, so
    availability remains explicitly unreported rather than being inferred.
    """

    if not daily_snapshot_ids:
        raise WebtrisTimeseriesError(
            "NO_EVIDENCE", "at least one accepted daily snapshot ID is required"
        )
    if len(daily_snapshot_ids) > MAX_TIMESERIES_EVIDENCE_ENTRIES:
        raise WebtrisTimeseriesError(
            "EVIDENCE_BOUND_EXCEEDED",
            f"at most {MAX_TIMESERIES_EVIDENCE_ENTRIES} accepted snapshot IDs are admitted",
        )
    workspace = _validated_v07_workspace(workspace_root)
    admitted_filter = _validated_filter(interval_filter)
    supplied_ids = tuple(daily_snapshot_ids)
    if any(not isinstance(snapshot_id, str) for snapshot_id in supplied_ids):
        raise WebtrisTimeseriesError(
            "SNAPSHOT_ID_INVALID", "accepted WebTRIS snapshot IDs must be strings"
        )

    opened_by_id: dict[str, WebtrisAcceptedSnapshotLoad] = {}
    for snapshot_id in sorted(set(supplied_ids)):
        try:
            opened_by_id[snapshot_id] = open_accepted_webtris_snapshot(workspace, snapshot_id)
        except WebtrisAcquisitionError as exc:
            raise WebtrisTimeseriesError(
                exc.code,
                "an accepted WebTRIS snapshot could not be reopened and verified",
            ) from exc

    opened = tuple(opened_by_id[snapshot_id] for snapshot_id in sorted(opened_by_id))
    if any(item.summary.product != "daily_report" for item in opened):
        raise WebtrisTimeseriesError(
            "PRODUCT_NOT_ADMITTED",
            "only accepted WebTRIS daily-report snapshots can build historical rows",
        )
    if len({item.summary.synthetic for item in opened}) != 1:
        raise WebtrisTimeseriesError(
            "MIXED_EVIDENCE_CLASS", "synthetic and real-source evidence cannot be mixed"
        )

    grouped: dict[tuple[str, date], list[WebtrisAcceptedSnapshotLoad]] = {}
    for item in opened:
        report_date = _required_accepted_report_date(item)
        grouped.setdefault((item.summary.site_id, report_date), []).append(item)
    conflicts = tuple(key for key, items in grouped.items() if len(items) != 1)
    if conflicts:
        key = min(conflicts, key=_site_day_sort_key)
        raise WebtrisTimeseriesError(
            "CONFLICTING_DUPLICATE_EVIDENCE",
            f"site {key[0]} on {key[1].isoformat()} has conflicting accepted snapshots",
        )

    total_pages = sum(item.summary.pages for item in opened)
    if total_pages > MAX_TIMESERIES_INPUT_PAGES:
        raise WebtrisTimeseriesError(
            "INPUT_PAGE_BOUND_EXCEEDED", "combined accepted snapshot pages exceed the input bound"
        )
    supplied_counts = {
        snapshot_id: supplied_ids.count(snapshot_id) for snapshot_id in set(supplied_ids)
    }
    verified: list[tuple[WebtrisTimeseriesInput, WebtrisDailyParseReport]] = []
    for key in sorted(grouped, key=_site_day_sort_key):
        item = grouped[key][0]
        summary = item.summary
        report = _required_accepted_daily_report(item)
        parser_fingerprint = _required_accepted_parser_fingerprint(item)
        site_name = _required_accepted_site_name(item)
        verified.append(
            (
                WebtrisTimeseriesInput(
                    site_id=summary.site_id,
                    site_name=site_name,
                    report_date=key[1],
                    synthetic=summary.synthetic,
                    publication_class=summary.publication_class,
                    daily_storage_area="accepted",
                    daily_snapshot_id=summary.snapshot_id,
                    daily_raw_fingerprint=summary.raw_fingerprint,
                    daily_parser_report_fingerprint=parser_fingerprint,
                    daily_parser_status=summary.stored_validation_state,
                    daily_pages=summary.pages,
                    daily_intervals_missing=report.counts.intervals_missing,
                    identical_duplicates_collapsed=supplied_counts[summary.snapshot_id] - 1,
                ),
                report,
            )
        )
    return _assemble_timeseries(
        admitted_filter,
        verified,
        supplied=len(supplied_ids),
    )


def _assemble_timeseries(
    admitted_filter: WebtrisTimeseriesFilter,
    verified: Sequence[tuple[WebtrisTimeseriesInput, WebtrisDailyParseReport]],
    *,
    supplied: int,
) -> WebtrisTimeseriesResult:
    """Assemble one self-validating result from already verified daily reports."""

    inputs: list[WebtrisTimeseriesInput] = []
    rows: list[WebtrisIntervalRow] = []
    exclusions: list[WebtrisIntervalExclusion] = []
    for input_item, day_report in verified:
        inputs.append(input_item)
        reason, admitted_states = _input_admission(admitted_filter, input_item)
        for record in day_report.records:
            if reason is not None:
                exclusions.append(_interval_exclusion(record, reason))
            elif record.measurement_state in admitted_states:
                rows.append(_interval_row(record, input_item))
            else:
                exclusions.append(_interval_exclusion(record, "measurement_state_filtered"))
    sorted_rows = tuple(sorted(rows, key=_row_sort_key))
    sorted_exclusions = tuple(sorted(exclusions, key=_exclusion_sort_key))
    sorted_inputs = tuple(sorted(inputs, key=_input_sort_key))
    counts = _derive_counts(
        supplied=supplied,
        inputs=sorted_inputs,
        rows=sorted_rows,
        exclusions=sorted_exclusions,
    )
    try:
        return WebtrisTimeseriesResult(
            interval_filter=admitted_filter,
            filter_fingerprint=admitted_filter.fingerprint(),
            inputs=sorted_inputs,
            inputs_fingerprint=_fingerprint_items(sorted_inputs),
            rows=sorted_rows,
            rows_fingerprint=_fingerprint_items(sorted_rows),
            exclusions=sorted_exclusions,
            counts=counts,
            result_state="rows_available" if sorted_rows else "empty_after_filters",
            licence_id=WEBTRIS_LICENCE_ID,
            attribution_text=WEBTRIS_ATTRIBUTION_TEXT,
            synthetic=sorted_inputs[0].synthetic,
        )
    except ValidationError as exc:  # pragma: no cover - shared derivation prevents this
        raise WebtrisTimeseriesError(
            "RESULT_ASSEMBLY_FAILED", "the assembled result failed its own re-derivation"
        ) from exc


def build_webtris_chart_series(
    result: WebtrisTimeseriesResult,
) -> tuple[WebtrisChartSeries, ...]:
    """Derive chart series from admitted rows without any aggregation.

    One series is emitted per verified (site ID, site name) identity, so a
    site renamed between source days never has earlier rows relabelled with a
    name their evidence did not assert.
    """

    result_fingerprint = result.fingerprint()
    groups: dict[tuple[str, str], list[WebtrisIntervalRow]] = {}
    for row in result.rows:
        groups.setdefault((row.site_id, row.site_name), []).append(row)
    series: list[WebtrisChartSeries] = []
    for site_id, site_name in sorted(groups, key=_series_sort_key):
        points = tuple(
            WebtrisChartPoint(
                report_date=row.report_date,
                report_date_raw=row.report_date_raw,
                time_period_ending_raw=row.time_period_ending_raw,
                interval_index=row.interval_index,
                measurement_state=row.measurement_state,
                total_volume=row.total_volume,
                average_speed_mph=row.average_speed_mph,
                average_speed_mps=row.average_speed_mps,
            )
            for row in groups[(site_id, site_name)]
        )
        series.append(
            WebtrisChartSeries(
                site_id=site_id,
                site_name=site_name,
                result_fingerprint=result_fingerprint,
                synthetic=result.synthetic,
                points=points,
            )
        )
    return tuple(series)


def verify_webtris_timeseries(
    workspace_root: str | Path,
    evidence: Sequence[WebtrisTimeseriesEvidence],
    result: WebtrisTimeseriesResult,
) -> WebtrisTimeseriesResult:
    """Rebuild a persisted result from immutable evidence and require equality.

    Pydantic reload validation proves internal structure and reconciliation;
    it is not a signature over upstream bytes. This verifier closes that
    boundary by repeating the complete accepted/quarantine verification and
    parser replay, then comparing the rebuilt artifact with the supplied
    result. The verified rebuild is returned on success.
    """

    try:
        admitted_result = WebtrisTimeseriesResult.model_validate_json(result.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise WebtrisTimeseriesError(
            "RESULT_INVALID", "the supplied timeseries result failed internal validation"
        ) from exc
    rebuilt = build_webtris_timeseries(
        workspace_root,
        evidence,
        interval_filter=admitted_result.interval_filter,
    )
    if rebuilt != admitted_result:
        raise WebtrisTimeseriesError(
            "RESULT_VERIFICATION_MISMATCH",
            "the persisted timeseries result does not reproduce from its immutable evidence",
        )
    return rebuilt


def verify_webtris_timeseries_from_accepted_snapshots(
    workspace_root: str | Path,
    daily_snapshot_ids: Sequence[str],
    result: WebtrisTimeseriesResult,
) -> WebtrisTimeseriesResult:
    """Rebuild a persisted result from accepted snapshot IDs and require equality."""

    try:
        admitted_result = WebtrisTimeseriesResult.model_validate_json(result.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise WebtrisTimeseriesError(
            "RESULT_INVALID", "the supplied timeseries result failed internal validation"
        ) from exc
    rebuilt = build_webtris_timeseries_from_accepted_snapshots(
        workspace_root,
        daily_snapshot_ids,
        interval_filter=admitted_result.interval_filter,
    )
    if rebuilt != admitted_result:
        raise WebtrisTimeseriesError(
            "RESULT_VERIFICATION_MISMATCH",
            "the persisted timeseries result does not reproduce from accepted snapshots",
        )
    return rebuilt


def _site_sort_key(site_id: str) -> tuple[int, str]:
    return (len(site_id), site_id)


def _series_sort_key(key: tuple[str, str]) -> tuple[int, str, str]:
    site_id, site_name = key
    return (*_site_sort_key(site_id), site_name)


def _site_day_sort_key(key: tuple[str, date]) -> tuple[int, str, date]:
    site_id, report_date = key
    return (*_site_sort_key(site_id), report_date)


def _interval_sort_key(key: tuple[str, date, int]) -> tuple[int, str, date, int]:
    site_id, report_date, interval_index = key
    return (*_site_sort_key(site_id), report_date, interval_index)


def _row_sort_key(row: WebtrisIntervalRow) -> tuple[int, str, date, int]:
    return _interval_sort_key((row.site_id, row.report_date, row.interval_index))


def _exclusion_sort_key(item: WebtrisIntervalExclusion) -> tuple[int, str, date, int]:
    return _interval_sort_key((item.site_id, item.report_date, item.interval_index))


def _input_sort_key(item: WebtrisTimeseriesInput) -> tuple[int, str, date]:
    return _site_day_sort_key((item.site_id, item.report_date))


def _fingerprint_items(items: Sequence[ManchesterSnapshotModel]) -> str:
    return sha256_hex(canonical_json([item.fingerprint() for item in items]).encode("utf-8"))


def _input_admission(
    interval_filter: WebtrisTimeseriesFilter,
    input_item: WebtrisTimeseriesInput,
) -> tuple[WebtrisRowExclusionReason | None, frozenset[str]]:
    """Shared build/reload derivation of one site-day's filter outcome."""

    if input_item.site_id not in interval_filter.site_ids:
        return "site_not_selected", frozenset()
    if not interval_filter.start_date <= input_item.report_date <= interval_filter.end_date:
        return "outside_date_range", frozenset()
    if interval_filter.min_availability_percent is not None:
        if input_item.availability_percent is None:
            return "availability_unreported", frozenset()
        if input_item.availability_percent < interval_filter.min_availability_percent:
            return "availability_below_minimum", frozenset()
    return None, frozenset(interval_filter.measurement_states)


def _derive_counts(
    *,
    supplied: int,
    inputs: Sequence[WebtrisTimeseriesInput],
    rows: Sequence[WebtrisIntervalRow],
    exclusions: Sequence[WebtrisIntervalExclusion],
) -> WebtrisTimeseriesCounts:
    reason_counts: dict[WebtrisRowExclusionReason, int] = {}
    for exclusion in exclusions:
        reason_counts[exclusion.reason] = reason_counts.get(exclusion.reason, 0) + 1
    return WebtrisTimeseriesCounts(
        evidence_supplied=supplied,
        evidence_admitted=len(inputs),
        identical_duplicates_collapsed=sum(item.identical_duplicates_collapsed for item in inputs),
        input_pages_total=sum(item.daily_pages for item in inputs)
        + sum(1 for item in inputs if item.quality_snapshot_id is not None),
        intervals_expected=EXPECTED_DAILY_INTERVALS * len(inputs),
        rows_seen=sum(item.daily_records_accepted for item in inputs),
        rows_admitted=len(rows),
        rows_excluded=len(exclusions),
        intervals_missing_measurement_seen=sum(item.daily_intervals_missing for item in inputs),
        rows_missing_measurement_admitted=sum(row.measurement_state == "missing" for row in rows),
        exclusion_reasons=tuple(
            WebtrisExclusionReasonCount(reason=reason, rows=count)
            for reason, count in sorted(reason_counts.items())
        ),
    )


def _interval_row(
    record: WebtrisDailyObservation, input_item: WebtrisTimeseriesInput
) -> WebtrisIntervalRow:
    return WebtrisIntervalRow(
        site_id=record.site_id,
        site_name=record.site_name,
        report_date=record.report_date,
        report_date_raw=record.report_date_raw,
        time_period_ending_raw=record.time_period_ending_raw,
        interval_index=record.interval_index,
        measurement_state=record.measurement_state,
        total_volume=record.total_volume,
        average_speed_mph=record.average_speed_mph,
        average_speed_mps=record.average_speed_mps,
        availability_percent=input_item.availability_percent,
        daily_snapshot_id=record.source.snapshot_id,
        daily_member_path=record.source.member_path,
        daily_member_sha256=record.source.member_sha256,
        daily_page_number=record.source.page_number,
        daily_row_index=record.row_index,
        quality_snapshot_id=input_item.quality_snapshot_id,
        synthetic=record.source.synthetic,
    )


def _interval_exclusion(
    record: WebtrisDailyObservation, reason: WebtrisRowExclusionReason
) -> WebtrisIntervalExclusion:
    return WebtrisIntervalExclusion(
        site_id=record.site_id,
        report_date=record.report_date,
        interval_index=record.interval_index,
        reason=reason,
    )


def _required_replay(receipt: WebtrisReplayResult | None) -> WebtrisReplayResult:
    if receipt is None:  # pragma: no cover - guarded by the evidence validator
        raise WebtrisTimeseriesError("EVIDENCE_INVALID", "a required replay receipt is missing")
    return receipt


def _required_scope_text(value: str | None) -> str:
    if value is None:  # pragma: no cover - guarded by the receipt validators
        raise WebtrisTimeseriesError("EVIDENCE_INVALID", "daily scope site name is missing")
    return value


def _required_scope_date(value: date | None) -> date:
    if value is None:  # pragma: no cover - guarded by the receipt validators
        raise WebtrisTimeseriesError("EVIDENCE_INVALID", "daily scope report date is missing")
    return value


def _required_accepted_report_date(item: WebtrisAcceptedSnapshotLoad) -> date:
    value = item.summary.report_date
    if value is None:
        raise WebtrisTimeseriesError(
            "ACCEPTED_SCOPE_MISMATCH",
            "an accepted daily-report snapshot is missing its report date",
        )
    return value


def _required_accepted_site_name(item: WebtrisAcceptedSnapshotLoad) -> str:
    value = item.summary.site_name
    if value is None:
        raise WebtrisTimeseriesError(
            "ACCEPTED_SCOPE_MISMATCH",
            "an accepted daily-report snapshot is missing its source site name",
        )
    return value


def _required_accepted_parser_fingerprint(item: WebtrisAcceptedSnapshotLoad) -> str:
    value = item.summary.parser_report_fingerprint
    if value is None:
        raise WebtrisTimeseriesError(
            "ACCEPTED_PARSER_INTEGRITY",
            "an accepted daily-report snapshot has no reproduced parser fingerprint",
        )
    return value


def _required_accepted_daily_report(
    item: WebtrisAcceptedSnapshotLoad,
) -> WebtrisDailyParseReport:
    report = item.report
    if not isinstance(report, WebtrisDailyParseReport):
        raise WebtrisTimeseriesError(
            "ACCEPTED_PARSER_INTEGRITY",
            "an accepted daily-report snapshot has no exact parser replay",
        )
    return report


def _validated_v07_workspace(workspace_root: str | Path) -> Path:
    workspace = Path(workspace_root)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise WebtrisTimeseriesError(
            "WORKSPACE_INVALID",
            "configure a valid isolated v0.7 workspace before building timeseries rows",
        ) from exc
    return workspace.resolve(strict=True)


def _validated_evidence(entry: WebtrisTimeseriesEvidence) -> WebtrisTimeseriesEvidence:
    try:
        return WebtrisTimeseriesEvidence.model_validate_json(entry.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise WebtrisTimeseriesError(
            "EVIDENCE_INVALID", "a supplied evidence entry failed internal validation"
        ) from exc


def _validated_filter(interval_filter: WebtrisTimeseriesFilter) -> WebtrisTimeseriesFilter:
    try:
        return WebtrisTimeseriesFilter.model_validate_json(interval_filter.model_dump_json())
    except (ValidationError, ValueError) as exc:
        raise WebtrisTimeseriesError(
            "FILTER_INVALID", "the supplied interval filter failed internal validation"
        ) from exc


def _collapse_duplicates(
    validated: Sequence[WebtrisTimeseriesEvidence],
) -> tuple[tuple[WebtrisTimeseriesEvidence, ...], dict[tuple[str, date], int]]:
    grouped: dict[tuple[str, date], list[WebtrisTimeseriesEvidence]] = {}
    for entry in validated:
        grouped.setdefault((entry.site_id(), entry.report_date()), []).append(entry)
    retained: list[WebtrisTimeseriesEvidence] = []
    collapsed_by_key: dict[tuple[str, date], int] = {}
    for key in sorted(grouped, key=_site_day_sort_key):
        entries = grouped[key]
        identities = {entry.identity() for entry in entries}
        if len(identities) != 1:
            raise WebtrisTimeseriesError(
                "CONFLICTING_DUPLICATE_EVIDENCE",
                f"site {key[0]} on {key[1].isoformat()} has conflicting duplicate evidence",
            )
        representative = min(entries, key=_representative_rank)
        retained.append(representative)
        collapsed_by_key[key] = len(entries) - 1
    return tuple(retained), collapsed_by_key


def _representative_rank(entry: WebtrisTimeseriesEvidence) -> tuple[int, int, str]:
    """Order-invariant representative choice: accepted receipts win, then bytes."""

    daily_rank = 0 if entry.daily_acquisition is not None else 1
    quality_rank = 0 if entry.quality_acquisition is not None or not entry.quality_supplied() else 1
    return (daily_rank, quality_rank, entry.fingerprint())


def _verified_input(
    workspace: Path,
    entry: WebtrisTimeseriesEvidence,
    identical_duplicates_collapsed: int,
) -> tuple[WebtrisTimeseriesInput, WebtrisDailyParseReport]:
    if entry.daily_acquisition is not None:
        day_report, publication_class = _read_and_parse_accepted_daily(
            workspace, entry.daily_acquisition
        )
    else:
        day_report, publication_class = _replay_and_parse_quarantined_daily(
            workspace, _required_replay(entry.daily_replay)
        )
    availability: int | None = None
    quality_publication_class: ManchesterPublicationClass | None = None
    if entry.quality_supplied():
        availability, quality_publication_class = _verified_availability(workspace, entry)
    input_item = WebtrisTimeseriesInput(
        site_id=entry.site_id(),
        site_name=entry.site_name(),
        report_date=entry.report_date(),
        synthetic=entry.synthetic(),
        publication_class=publication_class,
        daily_storage_area=entry.daily_storage_area(),
        daily_snapshot_id=entry.daily_snapshot_id(),
        daily_raw_fingerprint=entry.daily_raw_fingerprint(),
        daily_parser_report_fingerprint=entry.daily_parser_report_fingerprint(),
        daily_parser_status=entry.daily_parser_status(),
        daily_pages=entry.daily_pages(),
        daily_intervals_missing=day_report.counts.intervals_missing,
        quality_storage_area=entry.quality_storage_area(),
        quality_snapshot_id=entry.quality_snapshot_id(),
        quality_raw_fingerprint=entry.quality_raw_fingerprint(),
        quality_parser_report_fingerprint=entry.quality_parser_report_fingerprint(),
        quality_publication_class=quality_publication_class,
        availability_percent=availability,
        identical_duplicates_collapsed=identical_duplicates_collapsed,
    )
    return input_item, day_report


def _daily_scope(site_id: str, site_name: str, report_date: date) -> WebtrisDailyScope:
    return WebtrisDailyScope(site_id=site_id, site_name=site_name, report_date=report_date)


def _read_and_parse_accepted_daily(
    workspace: Path, acquisition: WebtrisAcquisitionResult
) -> tuple[WebtrisDailyParseReport, ManchesterPublicationClass]:
    members = _read_accepted_members(workspace, acquisition)
    scope = _daily_scope(
        acquisition.request.site_id,
        _required_scope_text(acquisition.request.site_name),
        _required_scope_date(acquisition.request.report_date),
    )
    try:
        report = parse_webtris_daily_report(members, scope)
    except WebtrisAdapterError as exc:
        raise WebtrisTimeseriesError(
            "PARSER_REPLAY_FAILED",
            "the accepted WebTRIS daily pages no longer pass the admitted parser contract",
        ) from exc
    _bind_parser_report(
        report_fingerprint=report.fingerprint(),
        report_status=report.status,
        expected_fingerprint=acquisition.parser_report_fingerprint,
        expected_status=acquisition.parser_status,
        rows_match=(
            report.counts.rows_seen == acquisition.rows_seen
            and report.counts.records_accepted == acquisition.records_accepted
            and report.counts.intervals_missing == acquisition.intervals_missing
        ),
    )
    return report, acquisition.request.publication_class


def _verified_availability(
    workspace: Path, entry: WebtrisTimeseriesEvidence
) -> tuple[int, ManchesterPublicationClass]:
    if entry.quality_acquisition is not None:
        members = _read_accepted_members(workspace, entry.quality_acquisition)
        expected_fingerprint = entry.quality_acquisition.parser_report_fingerprint
        expected_status = entry.quality_acquisition.parser_status
        publication_class = entry.quality_acquisition.request.publication_class
    else:
        quality_replay = _required_replay(entry.quality_replay)
        members, publication_class = _replay_quarantined_members(workspace, quality_replay)
        expected_fingerprint = quality_replay.parser_report_fingerprint
        expected_status = quality_replay.parser_status
    scope = _daily_scope(
        entry.quality_site_id(), entry.quality_site_name(), entry.quality_report_date()
    )
    try:
        report: WebtrisQualityParseReport = parse_webtris_daily_quality(members[0], scope)
    except WebtrisAdapterError as exc:
        raise WebtrisTimeseriesError(
            "PARSER_REPLAY_FAILED",
            "the stored WebTRIS quality member no longer passes the admitted parser contract",
        ) from exc
    _bind_parser_report(
        report_fingerprint=report.fingerprint(),
        report_status=report.status,
        expected_fingerprint=expected_fingerprint,
        expected_status=expected_status,
        rows_match=len(report.records) == 1,
    )
    return report.records[0].availability_percent, publication_class


def _replay_and_parse_quarantined_daily(
    workspace: Path, replay_receipt: WebtrisReplayResult
) -> tuple[WebtrisDailyParseReport, ManchesterPublicationClass]:
    members, publication_class = _replay_quarantined_members(workspace, replay_receipt)
    scope = _daily_scope(
        replay_receipt.request.site_id,
        _required_scope_text(replay_receipt.request.site_name),
        _required_scope_date(replay_receipt.request.report_date),
    )
    try:
        report = parse_webtris_daily_report(members, scope)
    except WebtrisAdapterError as exc:
        raise WebtrisTimeseriesError(
            "PARSER_REPLAY_FAILED",
            "the quarantined WebTRIS daily pages no longer pass the admitted parser contract",
        ) from exc
    _bind_parser_report(
        report_fingerprint=report.fingerprint(),
        report_status=report.status,
        expected_fingerprint=replay_receipt.parser_report_fingerprint,
        expected_status=replay_receipt.parser_status,
        rows_match=(
            report.counts.rows_seen == replay_receipt.rows_seen
            and report.counts.records_accepted == replay_receipt.records_accepted
            and report.counts.intervals_missing == replay_receipt.intervals_missing
        ),
    )
    return report, publication_class


def _bind_parser_report(
    *,
    report_fingerprint: str,
    report_status: ManchesterValidationState,
    expected_fingerprint: str,
    expected_status: ManchesterValidationState,
    rows_match: bool,
) -> None:
    if report_fingerprint != expected_fingerprint or not rows_match:
        raise WebtrisTimeseriesError(
            "PARSER_REPORT_MISMATCH",
            "the stored bytes do not reproduce the receipt's parser report",
        )
    if report_status is not expected_status:
        raise WebtrisTimeseriesError(
            "PARSER_REPORT_MISMATCH",
            "the replayed parser status does not match the receipt",
        )
    if report_status is ManchesterValidationState.REJECTED:
        raise WebtrisTimeseriesError(
            "PARSER_REPLAY_REJECTED",
            "a rejected WebTRIS parser report cannot produce timeseries rows",
        )


def _read_accepted_members(
    workspace: Path, acquisition: WebtrisAcquisitionResult
) -> tuple[tuple[WebtrisMemberRef, bytes], ...]:
    accepted = workspace / ACCEPTED_DIRECTORY_NAME / acquisition.snapshot_id
    try:
        snapshot_receipt = verify_manchester_snapshot(accepted)
        snapshot_manifest = ManchesterSnapshotManifest.model_validate_json(
            _read_bounded_regular_file(
                accepted / MANIFEST_FILE_NAME,
                max_bytes=MAX_QUARANTINE_MANIFEST_BYTES,
                code="ACCEPTED_SNAPSHOT_INVALID",
                description="accepted snapshot manifest",
            )
        )
        payloads = tuple(
            read_manchester_member(accepted, member.relative_path) for member in acquisition.members
        )
    except (ManchesterSnapshotError, ValidationError, OSError) as exc:
        raise WebtrisTimeseriesError(
            "ACCEPTED_SNAPSHOT_INVALID",
            "the accepted WebTRIS snapshot could not be re-verified",
        ) from exc
    if (
        snapshot_receipt.fingerprint() != acquisition.snapshot_receipt_fingerprint
        or snapshot_manifest.snapshot_id != acquisition.snapshot_id
        or snapshot_manifest.source.source_id != acquisition.source_id
        or snapshot_manifest.raw_fingerprint != acquisition.raw_fingerprint
        or snapshot_manifest.members != acquisition.members
        or snapshot_manifest.publication_class != acquisition.request.publication_class
        or snapshot_manifest.licence_id != WEBTRIS_LICENCE_ID
        or snapshot_manifest.attribution_text != WEBTRIS_ATTRIBUTION_TEXT
        or snapshot_manifest.synthetic != acquisition.synthetic
        or snapshot_manifest.request.host != acquisition.endpoint_host
        or snapshot_manifest.request.path != acquisition.endpoint_path
        or tuple(snapshot_manifest.request.parameters) != _expected_accepted_parameters(acquisition)
    ):
        raise WebtrisTimeseriesError(
            "ACCEPTED_SNAPSHOT_MISMATCH",
            "the accepted snapshot does not match the acquisition receipt",
        )
    content_encoding = (
        None if snapshot_manifest.http is None else snapshot_manifest.http.response_content_encoding
    )
    parsed_members: list[tuple[WebtrisMemberRef, bytes]] = []
    for member, payload in zip(acquisition.members, payloads, strict=True):
        parser_payload = decode_webtris_http_payload(
            payload,
            content_encoding=content_encoding,
        )
        parsed_members.append(
            (
                _member_reference(
                    acquisition.snapshot_id,
                    member.relative_path,
                    member.sha256,
                    acquisition.synthetic,
                    content_encoding=content_encoding,
                    parser_payload=parser_payload,
                ),
                parser_payload,
            )
        )
    return tuple(parsed_members)


def _expected_accepted_parameters(
    acquisition: WebtrisAcquisitionResult,
) -> tuple[tuple[str, str], ...]:
    """Rebuild the exact stored request scope so bytes cannot be relabelled."""

    request_date = _required_scope_date(acquisition.request.report_date).strftime("%d%m%Y")
    if acquisition.product == "daily_quality":
        parameters = {
            "siteId": acquisition.request.site_id,
            "start_date": request_date,
            "end_date": request_date,
        }
    else:
        page_size = acquisition.request.page_size
        if page_size is None:  # pragma: no cover - guarded by the receipt validators
            raise WebtrisTimeseriesError("EVIDENCE_INVALID", "daily scope page size is missing")
        parameters = {
            "sites": acquisition.request.site_id,
            "start_date": request_date,
            "end_date": request_date,
            "page": "1",
            "page_size": str(page_size),
        }
    return tuple(sorted(parameters.items()))


def _replay_quarantined_members(
    workspace: Path, replay_receipt: WebtrisReplayResult
) -> tuple[tuple[tuple[WebtrisMemberRef, bytes], ...], ManchesterPublicationClass]:
    try:
        fresh = replay_webtris_quarantine(
            workspace, replay_receipt.snapshot_id, replay_receipt.request
        )
    except (
        WebtrisAcquisitionError,
        ManchesterSnapshotError,
        ValidationError,
        OSError,
    ) as exc:
        raise WebtrisTimeseriesError(
            "QUARANTINE_REPLAY_INVALID",
            "the quarantined WebTRIS snapshot could not be re-replayed offline",
        ) from exc
    if fresh.fingerprint() != replay_receipt.fingerprint():
        raise WebtrisTimeseriesError(
            "QUARANTINE_REPLAY_MISMATCH",
            "the offline replay does not reproduce the supplied replay receipt",
        )
    quarantine_dir = workspace / QUARANTINE_DIRECTORY_NAME / replay_receipt.snapshot_id
    manifest_path = quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME
    try:
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise WebtrisTimeseriesError(
                "QUARANTINE_REPLAY_INVALID", "the quarantine manifest is missing or unsafe"
            )
        if manifest_path.stat().st_size > MAX_QUARANTINE_MANIFEST_BYTES:
            raise WebtrisTimeseriesError(
                "QUARANTINE_REPLAY_INVALID", "the quarantine manifest exceeds its byte bound"
            )
        manifest = ManchesterQuarantineManifest.model_validate_json(
            _read_bounded_regular_file(
                manifest_path,
                max_bytes=MAX_QUARANTINE_MANIFEST_BYTES,
                code="QUARANTINE_REPLAY_INVALID",
                description="quarantine manifest",
            )
        )
        content_encoding = (
            None if manifest.http is None else manifest.http.response_content_encoding
        )
        parsed_members: list[tuple[WebtrisMemberRef, bytes]] = []
        for member in manifest.members:
            raw_payload = _read_quarantined_member(
                quarantine_dir, member.relative_path, member.byte_size
            )
            parser_payload = decode_webtris_http_payload(
                raw_payload,
                content_encoding=content_encoding,
            )
            parsed_members.append(
                (
                    _member_reference(
                        manifest.snapshot_id,
                        member.relative_path,
                        member.sha256,
                        manifest.synthetic,
                        content_encoding=content_encoding,
                        parser_payload=parser_payload,
                    ),
                    parser_payload,
                )
            )
        members = tuple(parsed_members)
    except (ValidationError, OSError) as exc:
        raise WebtrisTimeseriesError(
            "QUARANTINE_REPLAY_INVALID",
            "the quarantined WebTRIS members could not be re-read",
        ) from exc
    return members, manifest.publication_class


def _read_quarantined_member(quarantine_dir: Path, relative_path: str, byte_size: int) -> bytes:
    target = quarantine_dir / RAW_DIRECTORY_NAME / relative_path
    return _read_bounded_regular_file(
        target,
        max_bytes=MAX_MEMBER_BYTES,
        expected_size=byte_size,
        code="QUARANTINE_REPLAY_INVALID",
        description=f"quarantined member {relative_path!r}",
    )


def _read_bounded_regular_file(
    target: Path,
    *,
    max_bytes: int,
    code: str,
    description: str,
    expected_size: int | None = None,
) -> bytes:
    """Read one regular file through its opened descriptor with a hard cap."""

    if target.is_symlink():
        raise WebtrisTimeseriesError(code, f"the {description} is missing or unsafe")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(target, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise WebtrisTimeseriesError(code, f"the {description} is not a regular file")
        if opened.st_size > max_bytes:
            raise WebtrisTimeseriesError(code, f"the {description} exceeds its byte bound")
        if expected_size is not None and opened.st_size != expected_size:
            raise WebtrisTimeseriesError(code, f"the {description} size drifted")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise WebtrisTimeseriesError(code, f"the {description} exceeds its byte bound")
        if expected_size is not None and len(payload) != expected_size:
            raise WebtrisTimeseriesError(code, f"the {description} size drifted")
        return payload
    except WebtrisTimeseriesError:
        raise
    except OSError as exc:
        raise WebtrisTimeseriesError(code, f"the {description} is missing or unsafe") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _member_reference(
    snapshot_id: str,
    relative_path: str,
    member_sha256: str,
    synthetic: bool,
    *,
    content_encoding: Literal["gzip", "deflate"] | None = None,
    parser_payload: bytes | None = None,
) -> WebtrisMemberRef:
    if relative_path == _QUALITY_MEMBER_PATH:
        role: Literal["daily_report", "daily_quality"] = "daily_quality"
        page_number = 1
    else:
        matched = _PAGE_MEMBER_PATTERN.fullmatch(relative_path)
        if matched is None:
            raise WebtrisTimeseriesError(
                "MEMBER_ROLE_UNKNOWN",
                f"stored member {relative_path!r} has no admitted WebTRIS daily role",
            )
        role = "daily_report"
        page_number = int(matched.group(1))
    if content_encoding == "gzip" and parser_payload is None:
        raise WebtrisTimeseriesError(
            "CONTENT_DECODING_FAILED", "gzip members require bounded parser bytes"
        )
    parser_payload_sha256 = (
        sha256_hex(parser_payload)
        if content_encoding == "gzip" and parser_payload is not None
        else None
    )
    return WebtrisMemberRef(
        snapshot_id=snapshot_id,
        member_path=relative_path,
        member_sha256=member_sha256,
        content_encoding="gzip" if content_encoding == "gzip" else "identity",
        parser_payload_sha256=parser_payload_sha256,
        member_role=role,
        page_number=page_number,
        synthetic=synthetic,
    )

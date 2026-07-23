"""Controlled WebTRIS acquisition: bounded transport → quarantine → parse → promote.

This module wires the three audited WebTRIS products (single-site reference,
one-site one-day daily report, one-site one-day daily quality) through the
existing MAN-01 boundaries in a fixed order: the shared
:class:`BoundedHttpClient` fetches each response, every exact body is
preserved in MAN-01 quarantine, the existing MAN-03 parser validates the
re-read and re-hashed quarantined bytes, and only an explicitly admitted parse
promotes the bytes to accepted storage.

It adds no second HTTP, hashing, quarantine, or promotion implementation and
changes no capability state: ``MAN-01`` and ``MAN-03`` remain ``planned``.

Evidence semantics are inherited unchanged from the MAN-03 parser: WebTRIS is
historical strategic-road evidence; source timestamps stay verbatim
(``source_string_undeclared``, blocker ``GA-WT-1``) and are never promoted to
UTC; retrieval time never becomes observation time or freshness; quality is a
data-availability percentage, not sensor accuracy or traffic validity; missing
measurements remain missing, never zero; and a service interruption or
transport failure is a typed failure, never zero traffic.

Pagination control for the daily report performs a bounded, read-only *peek*
of the audited ``Header.row_count`` integer on each already-size-bounded body,
solely because iteration requires the page count. The peek creates no records
and every peeked value is revalidated from quarantined bytes by the full
MAN-03 parser before anything is promoted. The single-response site and
quality products are fetched without any peek.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Self, TypeAlias

import httpx
from pydantic import Field, ValidationError, model_validator

from traffictwin.integration.manchester.acquisition import (
    ManchesterHttpSnapshotParts,
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.archive import (
    ArchivePolicy,
    ManchesterArchiveError,
    decompress_gzip,
)
from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    QUARANTINE_MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterRawMember,
    ManchesterRetrievalWindow,
    ManchesterSnapshotFinding,
    ManchesterSnapshotManifest,
    ManchesterSnapshotModel,
    ManchesterSnapshotPolicy,
    ManchesterSnapshotReceipt,
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    MAX_MANIFEST_FILE_BYTES,
    QUARANTINE_DIRECTORY_NAME,
    ManchesterSnapshotError,
    quarantine_validate_and_promote,
    verify_manchester_quarantine,
    verify_manchester_snapshot,
)
from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)
from traffictwin.integration.manchester.webtris import (
    MAX_MEMBER_BYTES,
    MAX_REPORT_PAGES,
    WEBTRIS_DAILY_QUALITY_PATH,
    WEBTRIS_DAILY_REPORT_PATH,
    WEBTRIS_SOURCE_HOST,
    WebtrisAdapterError,
    WebtrisDailyParseReport,
    WebtrisDailyScope,
    WebtrisMemberRef,
    WebtrisQualityParseReport,
    WebtrisSiteParseReport,
    parse_webtris_daily_quality,
    parse_webtris_daily_report,
    parse_webtris_site,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

WEBTRIS_ACQUISITION_SCHEMA_VERSION = "1.0"
WEBTRIS_ACQUISITION_METHOD_VERSION = "manchester-webtris-acquisition-1.0"
WEBTRIS_ACCEPTED_CATALOGUE_SCHEMA_VERSION = "1.0"
WEBTRIS_ACCEPTED_CATALOGUE_METHOD_VERSION = "manchester-webtris-accepted-catalogue-1.0"
WEBTRIS_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS = 512
WEBTRIS_SITES_PATH_PREFIX = "/api/v1.0/sites"

# The WebTRIS privacy-policy page names the Open Government Licence without a
# version. The accepted Gate-A audit requires the provider statement and the
# official OGL v3.0 URI to be retained together in snapshot provenance.
WEBTRIS_LICENCE_ID = "OGL"
WEBTRIS_LICENCE_URI = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
WEBTRIS_ATTRIBUTION_TEXT = (
    "Contains National Highways WebTRIS data, re-used under the Open Government "
    "Licence as named on the WebTRIS privacy-policy page (logos excluded). "
    f"Official licence text: {WEBTRIS_LICENCE_URI}"
)
WEBTRIS_FRESHNESS_POLICY_VERSION = "webtris-historical-1.0"

MAX_QUARANTINE_MANIFEST_BYTES = 8_000_000
MAX_ADMITTED_WARNING_CODES = 8
_SITE_ID_PATTERN = r"^[1-9][0-9]{0,9}$"
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"
_WARNING_CODE_PATTERN = re.compile(r"^[A-Z0-9_]{1,96}$")
_PAGE_MEMBER_PATTERN = re.compile(r"^pages/page-(\d{4})\.json$")

WebtrisProduct: TypeAlias = Literal["site", "daily_report", "daily_quality"]
WebtrisSourceId: TypeAlias = Literal[
    "webtris_site",
    "webtris_daily_report",
    "webtris_daily_quality",
]
WebtrisAnyParseReport: TypeAlias = (
    WebtrisSiteParseReport | WebtrisDailyParseReport | WebtrisQualityParseReport
)

_PRODUCT_SOURCE_IDS: dict[WebtrisProduct, WebtrisSourceId] = {
    "site": "webtris_site",
    "daily_report": "webtris_daily_report",
    "daily_quality": "webtris_daily_quality",
}
_SINGLE_MEMBER_PATHS: dict[WebtrisProduct, str] = {
    "site": "site/site.json",
    "daily_quality": "quality/daily-quality.json",
}

WEBTRIS_ENDPOINT_POLICY = EndpointPolicy(
    endpoint_id="webtris-road-traffic",
    host=WEBTRIS_SOURCE_HOST,
    path_prefixes=(
        WEBTRIS_DAILY_QUALITY_PATH,
        WEBTRIS_DAILY_REPORT_PATH,
        WEBTRIS_SITES_PATH_PREFIX,
    ),
    query_parameter_names=("end_date", "page", "page_size", "siteId", "sites", "start_date"),
)

# Conservative self-imposed transport limits: the audit found no published
# WebTRIS rate limits (GA-WT-5) and a 3-6 month 2026 service interruption is
# announced, so failures must stay cheap, bounded, and typed.
_CONNECT_TIMEOUT_S = 10.0
_READ_TIMEOUT_S = 30.0
_WRITE_TIMEOUT_S = 10.0
_POOL_TIMEOUT_S = 10.0
_TOTAL_DEADLINE_S = 120.0
_MAX_REDIRECTS = 2
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.2
_BACKOFF_MAX_S = 2.0
_ALLOWED_MEDIA_TYPES = ("application/json",)

_WEBTRIS_GZIP_POLICY = ArchivePolicy(
    max_compressed_bytes=MAX_MEMBER_BYTES,
    max_decompressed_bytes=MAX_MEMBER_BYTES,
    max_member_bytes=MAX_MEMBER_BYTES,
    max_members=1,
    max_compression_ratio=200.0,
)

_EARLIEST_REPORT_DATE = date(1990, 1, 1)
_LATEST_REPORT_DATE = date(2100, 12, 31)


class WebtrisAcquisitionError(RuntimeError):
    """Typed deterministic acquisition/replay failure.

    ``quarantine_snapshot_id`` is set when complete raw evidence exists in
    quarantine (rejected parse, refused warnings, replay mismatch).
    ``accepted_snapshot_id`` is set only for a refusal while reopening
    promoted evidence. Both are ``None`` when acquisition never became
    complete, in which case nothing durable was published.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        quarantine_snapshot_id: str | None = None,
        accepted_snapshot_id: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        if quarantine_snapshot_id is not None and accepted_snapshot_id is not None:
            raise ValueError("an acquisition error cannot label one snapshot twice")
        self.code = code
        self.quarantine_snapshot_id = quarantine_snapshot_id
        self.accepted_snapshot_id = accepted_snapshot_id


class WebtrisAcquisitionRequest(ManchesterSnapshotModel):
    """Strict typed request; no host, URL, free path, free query, or date strings."""

    product: WebtrisProduct
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str | None = Field(default=None, min_length=1, max_length=120)
    report_date: date | None = None
    page_size: int | None = Field(default=None, ge=1, le=96)
    max_pages: int = Field(ge=1, le=MAX_REPORT_PAGES)
    policy: ManchesterSnapshotPolicy
    publication_class: ManchesterPublicationClass
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    admitted_warning_codes: tuple[str, ...] = ()
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> WebtrisAcquisitionRequest:
        if self.product == "site":
            if (
                self.site_name is not None
                or self.report_date is not None
                or self.page_size is not None
            ):
                raise ValueError("the site product takes no scope name, date, or page size")
        else:
            if self.site_name is None or self.report_date is None:
                raise ValueError("daily products require site_name and report_date")
            if not _EARLIEST_REPORT_DATE <= self.report_date <= _LATEST_REPORT_DATE:
                raise ValueError("report_date is outside the supported bound")
            if self.product == "daily_report" and self.page_size is None:
                raise ValueError("daily_report requires an explicit page_size")
            if self.product == "daily_quality" and self.page_size is not None:
                raise ValueError("daily_quality is a single response; page_size is not used")
        if self.max_pages > self.policy.max_member_count:
            raise ValueError("max_pages cannot exceed the snapshot policy member bound")
        if len(self.admitted_warning_codes) > MAX_ADMITTED_WARNING_CODES:
            raise ValueError("admitted warning codes are bounded")
        if list(self.admitted_warning_codes) != sorted(set(self.admitted_warning_codes)):
            raise ValueError("admitted warning codes must be sorted and unique")
        if any(
            _WARNING_CODE_PATTERN.fullmatch(code) is None for code in self.admitted_warning_codes
        ):
            raise ValueError("admitted warning codes must be canonical finding codes")
        return self


class WebtrisReplayRequest(ManchesterSnapshotModel):
    """Offline replay binding: the caller's claimed product/scope, verified strictly."""

    product: WebtrisProduct
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str | None = Field(default=None, min_length=1, max_length=120)
    report_date: date | None = None
    page_size: int | None = Field(default=None, ge=1, le=96)
    expected_synthetic: bool | None = None

    @model_validator(mode="after")
    def validate_request(self) -> WebtrisReplayRequest:
        if self.product == "site":
            if (
                self.site_name is not None
                or self.report_date is not None
                or self.page_size is not None
            ):
                raise ValueError("the site product takes no scope name, date, or page size")
        else:
            if self.site_name is None or self.report_date is None:
                raise ValueError("daily products require site_name and report_date")
            if self.product == "daily_report" and self.page_size is None:
                raise ValueError("daily_report replay requires the acquisition page_size")
            if self.product == "daily_quality" and self.page_size is not None:
                raise ValueError("daily_quality is a single response; page_size is not used")
        return self


class WebtrisAcquisitionResult(ManchesterSnapshotModel):
    """Strict frozen receipt for one promoted WebTRIS acquisition."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-acquisition-1.0"] = (
        "manchester-webtris-acquisition-1.0"
    )
    product: WebtrisProduct
    source_id: WebtrisSourceId
    endpoint_host: Literal["webtris.nationalhighways.co.uk"] = "webtris.nationalhighways.co.uk"
    endpoint_path: str
    request: WebtrisAcquisitionRequest
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1)
    pages: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    intervals_missing: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    quarantine_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool
    promoted: Literal[True] = True

    @model_validator(mode="after")
    def validate_result(self) -> WebtrisAcquisitionResult:
        if self.product != self.request.product:
            raise ValueError("result product must match the acquisition request")
        if self.source_id != _PRODUCT_SOURCE_IDS[self.product]:
            raise ValueError("source ID must match the selected WebTRIS product")
        if self.synthetic != self.request.synthetic:
            raise ValueError("result evidence class must match the acquisition request")
        if self.parser_status is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected parse can never produce a promoted result")
        expected_path = _endpoint_path(self.product, self.request.site_id)
        if self.endpoint_path != expected_path:
            raise ValueError("endpoint path must match the audited product endpoint")
        if self.pages != len(self.members):
            raise ValueError("page count must match the member inventory")
        member_paths = [member.relative_path for member in self.members]
        if member_paths != sorted(member_paths) or len(set(member_paths)) != len(member_paths):
            raise ValueError("result members must be sorted and unique")
        if self.product == "daily_report":
            expected_paths = [
                f"pages/page-{page_number:04d}.json" for page_number in range(1, self.pages + 1)
            ]
        else:
            expected_paths = [_SINGLE_MEMBER_PATHS[self.product]]
        if member_paths != expected_paths or any(
            member.media_type != "application/json" for member in self.members
        ):
            raise ValueError("result members must match the exact product inventory")
        if self.raw_fingerprint != build_raw_fingerprint(self.members):
            raise ValueError("result raw fingerprint must bind the member inventory")
        if self.records_accepted > self.rows_seen:
            raise ValueError("accepted records cannot exceed rows seen")
        if self.intervals_missing > self.records_accepted:
            raise ValueError("missing intervals cannot exceed accepted records")
        if self.product != "daily_report" and self.intervals_missing != 0:
            raise ValueError("only daily reports may carry missing intervals")
        return self


class WebtrisReplayResult(ManchesterSnapshotModel):
    """Offline re-validation of quarantined WebTRIS bytes; no network, no promotion."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-acquisition-1.0"] = (
        "manchester-webtris-acquisition-1.0"
    )
    product: WebtrisProduct
    source_id: WebtrisSourceId
    endpoint_path: str
    request: WebtrisReplayRequest
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    intervals_missing: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool
    replayed_offline: Literal[True] = True

    @model_validator(mode="after")
    def validate_result(self) -> WebtrisReplayResult:
        if self.product != self.request.product:
            raise ValueError("replay product must match the replay request")
        if self.source_id != _PRODUCT_SOURCE_IDS[self.product]:
            raise ValueError("replay source ID must match the selected WebTRIS product")
        if self.endpoint_path != _endpoint_path(self.product, self.request.site_id):
            raise ValueError("replay endpoint must match the requested product/site")
        if self.product != "daily_report" and self.pages != 1:
            raise ValueError("single-response products must replay exactly one member")
        if self.records_accepted > self.rows_seen:
            raise ValueError("accepted records cannot exceed rows seen")
        if self.intervals_missing > self.records_accepted:
            raise ValueError("missing intervals cannot exceed accepted records")
        if self.product != "daily_report" and self.intervals_missing != 0:
            raise ValueError("only daily reports may carry missing intervals")
        if (
            self.request.expected_synthetic is not None
            and self.synthetic != self.request.expected_synthetic
        ):
            raise ValueError("replay evidence class must match the explicit request")
        return self


class WebtrisAcceptedProductCounts(ManchesterSnapshotModel):
    """Exact product inventory for one verified local WebTRIS catalogue."""

    site: int = Field(ge=0)
    daily_report: int = Field(ge=0)
    daily_quality: int = Field(ge=0)
    parser_reproduced: int = Field(ge=0)
    parser_scope_unavailable: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.site + self.daily_report + self.daily_quality

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.total != self.parser_reproduced + self.parser_scope_unavailable:
            raise ValueError("product totals must reconcile parser replay availability")
        return self


class WebtrisAcceptedSnapshotSummary(ManchesterSnapshotModel):
    """Verified local identity and replay state of one accepted WebTRIS snapshot."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-accepted-catalogue-1.0"] = (
        "manchester-webtris-accepted-catalogue-1.0"
    )
    product: WebtrisProduct
    source_id: WebtrisSourceId
    endpoint_path: str
    site_id: str = Field(pattern=_SITE_ID_PATTERN)
    site_name: str | None = Field(default=None, min_length=1, max_length=500)
    site_name_basis: Literal["source_record", "not_present_in_product"]
    report_date: date | None = None
    page_size: int | None = Field(default=None, ge=1, le=96)
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_started_at_utc: datetime
    retrieval_completed_at_utc: datetime
    pages: int = Field(ge=1, le=MAX_REPORT_PAGES)
    total_bytes: int = Field(ge=0)
    stored_validation_state: ManchesterValidationState
    parser_replay_state: Literal["reproduced", "scope_unavailable"]
    parser_report_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    rows_seen: int | None = Field(default=None, ge=0)
    records_accepted: int | None = Field(default=None, ge=0)
    intervals_missing: int | None = Field(default=None, ge=0)
    publication_class: ManchesterPublicationClass
    licence_id: Literal["OGL"] = "OGL"
    attribution_text: str
    synthetic: bool
    opened_offline: Literal[True] = True
    observation_time_from_retrieval: Literal[False] = False

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.source_id != _PRODUCT_SOURCE_IDS[self.product]:
            raise ValueError("accepted summary source ID must match its WebTRIS product")
        if self.endpoint_path != _endpoint_path(self.product, self.site_id):
            raise ValueError("accepted summary endpoint must match its product and site")
        if not self.snapshot_id.startswith(f"{self.source_id}-") or not self.snapshot_id.endswith(
            f"-{self.raw_fingerprint[:12]}"
        ):
            raise ValueError("accepted summary snapshot ID must bind source and raw fingerprint")
        if self.stored_validation_state is ManchesterValidationState.REJECTED:
            raise ValueError("rejected validation state cannot enter the accepted catalogue")
        if self.attribution_text != WEBTRIS_ATTRIBUTION_TEXT:
            raise ValueError("accepted summary must retain the audited WebTRIS attribution")
        parser_values = (
            self.parser_report_fingerprint,
            self.rows_seen,
            self.records_accepted,
            self.intervals_missing,
        )
        if self.parser_replay_state == "reproduced":
            if not all(value is not None for value in parser_values):
                raise ValueError("reproduced parser summaries require complete parser counts")
        elif any(value is not None for value in parser_values):
            raise ValueError("scope-unavailable summaries cannot claim a parser replay")
        if (
            self.records_accepted is not None
            and self.rows_seen is not None
            and self.records_accepted > self.rows_seen
        ):
            raise ValueError("accepted records cannot exceed parser rows seen")
        if (
            self.intervals_missing is not None
            and self.records_accepted is not None
            and self.intervals_missing > self.records_accepted
        ):
            raise ValueError("missing intervals cannot exceed accepted records")
        if self.product == "site":
            if (
                self.site_name is None
                or self.site_name_basis != "source_record"
                or self.report_date is not None
                or self.page_size is not None
                or self.parser_replay_state != "reproduced"
            ):
                raise ValueError("site summaries must bind one source record and no daily scope")
        elif self.product == "daily_report":
            if (
                self.site_name is None
                or self.site_name_basis != "source_record"
                or self.report_date is None
                or self.page_size is None
                or self.parser_replay_state != "reproduced"
            ):
                raise ValueError("daily-report summaries require complete source scope")
        elif (
            self.site_name is not None
            or self.site_name_basis != "not_present_in_product"
            or self.report_date is None
            or self.page_size is not None
            or self.parser_replay_state != "scope_unavailable"
        ):
            raise ValueError("daily-quality summaries must expose their missing name scope")
        return self


class WebtrisAcceptedSnapshotCatalogue(ManchesterSnapshotModel):
    """Bounded deterministic inventory of verified accepted WebTRIS snapshots."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-03"] = "MAN-03"
    method_version: Literal["manchester-webtris-accepted-catalogue-1.0"] = (
        "manchester-webtris-accepted-catalogue-1.0"
    )
    snapshots: tuple[WebtrisAcceptedSnapshotSummary, ...]
    counts: WebtrisAcceptedProductCounts
    maximum_snapshots: Literal[512] = 512
    network_access_performed: Literal[False] = False

    @model_validator(mode="after")
    def validate_catalogue(self) -> Self:
        keys = tuple(
            (item.retrieval_started_at_utc, item.product, item.snapshot_id)
            for item in self.snapshots
        )
        if keys != tuple(sorted(keys)) or len({item.snapshot_id for item in self.snapshots}) != len(
            self.snapshots
        ):
            raise ValueError("accepted WebTRIS snapshots must be sorted with unique IDs")
        expected = _accepted_product_counts(self.snapshots)
        if self.counts != expected:
            raise ValueError("catalogue counts must reconcile every accepted WebTRIS snapshot")
        return self


@dataclass(frozen=True, slots=True)
class WebtrisAcceptedSnapshotLoad:
    """Runtime-only verified accepted snapshot plus an available parser replay."""

    summary: WebtrisAcceptedSnapshotSummary
    manifest: ManchesterSnapshotManifest
    receipt: ManchesterSnapshotReceipt
    report: WebtrisSiteParseReport | WebtrisDailyParseReport | None


def acquire_webtris_snapshot(
    workspace_root: str | Path,
    request: WebtrisAcquisitionRequest,
    *,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> WebtrisAcquisitionResult:
    """Acquire one audited WebTRIS product through quarantine into accepted storage."""

    endpoint_path = _endpoint_path(request.product, request.site_id)
    transport_policy = TransportPolicy(
        connect_timeout_s=_CONNECT_TIMEOUT_S,
        read_timeout_s=_READ_TIMEOUT_S,
        write_timeout_s=_WRITE_TIMEOUT_S,
        pool_timeout_s=_POOL_TIMEOUT_S,
        total_deadline_s=_TOTAL_DEADLINE_S,
        max_response_bytes=request.policy.max_member_bytes,
        max_redirects=_MAX_REDIRECTS,
        max_attempts=_MAX_ATTEMPTS,
        backoff_base_s=_BACKOFF_BASE_S,
        backoff_max_s=_BACKOFF_MAX_S,
        allowed_media_types=_ALLOWED_MEDIA_TYPES,
    )
    pages: list[ManchesterHttpSnapshotParts] = []
    total_bytes = 0
    with BoundedHttpClient(
        endpoint=WEBTRIS_ENDPOINT_POLICY,
        policy=transport_policy,
        client=http_client,
        utc_now=utc_now,
    ) as client:
        if request.product == "daily_report":
            expected_pages: int | None = None
            first_row_count: int | None = None
            first_content_encoding: Literal["gzip", "deflate"] | None = None
            page_number = 1
            while True:
                parts = _fetch(
                    client,
                    endpoint_path,
                    _daily_report_query(request, page_number),
                    f"pages/page-{page_number:04d}.json",
                    page_number,
                )
                content_encoding = parts.http.response_content_encoding
                if page_number == 1:
                    first_content_encoding = content_encoding
                elif content_encoding != first_content_encoding:
                    raise WebtrisAcquisitionError(
                        "PAGINATION_DRIFT",
                        f"page {page_number} content encoding disagrees with page 1",
                    )
                peek_payload = decode_webtris_http_payload(
                    parts.payload,
                    content_encoding=content_encoding,
                )
                row_count = _peek_daily_row_count(peek_payload, page_number)
                if expected_pages is None:
                    first_row_count = row_count
                    page_size = request.page_size
                    if page_size is None:  # pragma: no cover - model invariant
                        raise WebtrisAcquisitionError(
                            "PAGINATION_PEEK_FAILED", "daily_report requires a page size"
                        )
                    expected_pages = max(1, math.ceil(row_count / page_size))
                    if expected_pages > request.max_pages:
                        raise WebtrisAcquisitionError(
                            "PAGE_LIMIT_EXCEEDED",
                            f"source reports {expected_pages} pages; bound is {request.max_pages}",
                        )
                elif row_count != first_row_count:
                    raise WebtrisAcquisitionError(
                        "PAGINATION_DRIFT",
                        f"page {page_number} row_count disagrees with page 1",
                    )
                total_bytes += len(parts.payload)
                if total_bytes > request.policy.max_total_bytes:
                    raise WebtrisAcquisitionError(
                        "TOTAL_BYTES_EXCEEDED",
                        "combined page bytes exceed the snapshot policy bound",
                    )
                pages.append(parts)
                if page_number >= expected_pages:
                    break
                page_number += 1
        else:
            member_path = _SINGLE_MEMBER_PATHS[request.product]
            parts = _fetch(
                client,
                endpoint_path,
                _single_query(request),
                member_path,
                1,
            )
            total_bytes = len(parts.payload)
            if total_bytes > request.policy.max_total_bytes:
                raise WebtrisAcquisitionError(
                    "TOTAL_BYTES_EXCEEDED",
                    "response bytes exceed the snapshot policy bound",
                )
            pages.append(parts)

    members = {parts.member.relative_path: parts.payload for parts in pages}
    inventory = tuple(sorted((p.member for p in pages), key=lambda m: m.relative_path))
    raw_fingerprint = build_raw_fingerprint(inventory)
    source = _source_identity(request.product)
    retrieval = ManchesterRetrievalWindow(
        started_at_utc=pages[0].retrieval.started_at_utc,
        completed_at_utc=pages[-1].retrieval.completed_at_utc,
    )
    quarantine_manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(source.source_id, retrieval.started_at_utc, raw_fingerprint),
        source=source,
        request=pages[0].request,
        retrieval=retrieval,
        http=pages[0].http,
        members=inventory,
        member_count=len(inventory),
        total_bytes=sum(member.byte_size for member in inventory),
        raw_fingerprint=raw_fingerprint,
        publication_class=request.publication_class,
        licence_id=WEBTRIS_LICENCE_ID,
        attribution_text=WEBTRIS_ATTRIBUTION_TEXT,
        access_date=retrieval.started_at_utc.date(),
        synthetic=request.synthetic,
    )

    captured: dict[str, WebtrisAnyParseReport] = {}

    def validator(
        quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        report = _parse_quarantined(
            quarantine_dir,
            manifest,
            request.product,
            request.site_id,
            request.site_name,
            request.report_date,
        )
        captured["report"] = report
        _admit_or_raise(report, request.admitted_warning_codes, manifest.snapshot_id)
        return ManchesterSnapshotManifest(
            snapshot_id=manifest.snapshot_id,
            source=manifest.source,
            request=manifest.request,
            retrieval=manifest.retrieval,
            http=manifest.http,
            members=manifest.members,
            member_count=manifest.member_count,
            total_bytes=manifest.total_bytes,
            raw_fingerprint=manifest.raw_fingerprint,
            validation_state=report.status,
            findings=tuple(
                ManchesterSnapshotFinding(
                    code=finding.code,
                    severity=finding.severity,
                    message=(
                        finding.message
                        if finding.row_index is None
                        else f"{finding.message} (row {finding.row_index})"
                    ),
                    artifact=finding.member_path,
                )
                for finding in report.findings
            ),
            prior=request.prior,
            publication_class=manifest.publication_class,
            licence_id=manifest.licence_id,
            attribution_text=manifest.attribution_text,
            access_date=manifest.access_date,
            synthetic=manifest.synthetic,
        )

    snapshot_receipt = quarantine_validate_and_promote(
        workspace_root,
        quarantine_manifest,
        members,
        request.policy,
        validator,
    )
    quarantine_receipt = verify_manchester_quarantine(
        Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / quarantine_manifest.snapshot_id
    )
    report = captured["report"]
    return WebtrisAcquisitionResult(
        product=request.product,
        source_id=_PRODUCT_SOURCE_IDS[request.product],
        endpoint_path=endpoint_path,
        request=request,
        snapshot_id=quarantine_manifest.snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=inventory,
        pages=len(inventory),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        intervals_missing=report.counts.intervals_missing,
        parser_status=report.status,
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
        synthetic=request.synthetic,
    )


def replay_webtris_quarantine(
    workspace_root: str | Path,
    snapshot_id: str,
    request: WebtrisReplayRequest,
) -> WebtrisReplayResult:
    """Re-validate quarantined WebTRIS bytes offline against a bound product claim.

    The caller's product/scope claim is verified against the quarantine
    manifest's source identity, audited endpoint, stored request parameters,
    member-role inventory, adapter/schema versions, and licence before any
    byte is parsed, so valid bytes can never be relabelled as another WebTRIS
    product or scope. No network access and no promotion occur.
    """

    quarantine_dir = Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    verify_manchester_quarantine(quarantine_dir)
    manifest = _load_quarantine_manifest(quarantine_dir)
    if manifest.snapshot_id != snapshot_id:
        raise WebtrisAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest does not match the requested id"
        )
    _bind_replay_claim(manifest, request)
    if request.expected_synthetic is not None and manifest.synthetic != request.expected_synthetic:
        raise WebtrisAcquisitionError(
            "SYNTHETIC_MISMATCH",
            "quarantined evidence class does not match the caller's declaration",
            quarantine_snapshot_id=snapshot_id,
        )
    report = _parse_quarantined(
        quarantine_dir,
        manifest,
        request.product,
        request.site_id,
        request.site_name,
        request.report_date,
    )
    return WebtrisReplayResult(
        product=request.product,
        source_id=_PRODUCT_SOURCE_IDS[request.product],
        endpoint_path=_endpoint_path(request.product, request.site_id),
        request=request,
        snapshot_id=snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        pages=manifest.member_count,
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        intervals_missing=report.counts.intervals_missing,
        parser_status=report.status,
        parser_report_fingerprint=report.fingerprint(),
        synthetic=manifest.synthetic,
    )


def open_accepted_webtris_snapshot(
    workspace_root: str | Path,
    snapshot_id: str,
) -> WebtrisAcceptedSnapshotLoad:
    """Open accepted WebTRIS evidence by safe ID without an ephemeral receipt.

    Site and daily-report products are replayed completely. The quality
    product is still inventoried and byte-verified, but its parser replay is
    honestly unavailable because the accepted generic manifest does not
    persist the ``site_name`` scope required by the current MAN-03 report
    fingerprint and the quality response itself contains no site name.
    """

    workspace = _validated_accepted_workspace(workspace_root)
    return _open_accepted_webtris_snapshot(workspace, snapshot_id)


def catalogue_accepted_webtris_snapshots(
    workspace_root: str | Path,
) -> WebtrisAcceptedSnapshotCatalogue:
    """Return a bounded offline inventory of accepted WebTRIS snapshots."""

    workspace = _validated_accepted_workspace(workspace_root)
    accepted_root = workspace / ACCEPTED_DIRECTORY_NAME
    if not accepted_root.exists():
        return WebtrisAcceptedSnapshotCatalogue(
            snapshots=(),
            counts=WebtrisAcceptedProductCounts(
                site=0,
                daily_report=0,
                daily_quality=0,
                parser_reproduced=0,
                parser_scope_unavailable=0,
            ),
        )
    if accepted_root.is_symlink() or not accepted_root.is_dir():
        raise WebtrisAcquisitionError(
            "ACCEPTED_CATALOGUE_INVALID",
            "the accepted snapshot root is not a safe local directory",
        )
    try:
        candidates = tuple(
            sorted(
                entry
                for entry in accepted_root.iterdir()
                if entry.name.startswith(
                    ("webtris_site-", "webtris_daily_report-", "webtris_daily_quality-")
                )
            )
        )
    except OSError as exc:
        raise WebtrisAcquisitionError(
            "ACCEPTED_CATALOGUE_INVALID",
            "the accepted snapshot root could not be inspected safely",
        ) from exc
    if len(candidates) > WEBTRIS_ACCEPTED_CATALOGUE_MAX_SNAPSHOTS:
        raise WebtrisAcquisitionError(
            "ACCEPTED_CATALOGUE_LIMIT",
            "the number of local WebTRIS snapshots exceeds the fixed catalogue bound",
        )
    opened = tuple(_open_accepted_webtris_snapshot(workspace, entry.name) for entry in candidates)
    snapshots = tuple(
        sorted(
            (item.summary for item in opened),
            key=lambda item: (
                item.retrieval_started_at_utc,
                item.product,
                item.snapshot_id,
            ),
        )
    )
    return WebtrisAcceptedSnapshotCatalogue(
        snapshots=snapshots,
        counts=_accepted_product_counts(snapshots),
    )


def _accepted_product_counts(
    snapshots: tuple[WebtrisAcceptedSnapshotSummary, ...],
) -> WebtrisAcceptedProductCounts:
    return WebtrisAcceptedProductCounts(
        site=sum(item.product == "site" for item in snapshots),
        daily_report=sum(item.product == "daily_report" for item in snapshots),
        daily_quality=sum(item.product == "daily_quality" for item in snapshots),
        parser_reproduced=sum(item.parser_replay_state == "reproduced" for item in snapshots),
        parser_scope_unavailable=sum(
            item.parser_replay_state == "scope_unavailable" for item in snapshots
        ),
    )


def _validated_accepted_workspace(workspace_root: str | Path) -> Path:
    try:
        inspect_v07_workspace(workspace_root)
    except V07WorkspaceError as exc:
        raise WebtrisAcquisitionError(
            "WORKSPACE_INVALID",
            "accepted WebTRIS replay requires a valid isolated v0.7 workspace",
        ) from exc
    return Path(workspace_root).resolve(strict=True)


def _open_accepted_webtris_snapshot(
    workspace: Path,
    snapshot_id: str,
) -> WebtrisAcceptedSnapshotLoad:
    if re.fullmatch(_SNAPSHOT_ID_PATTERN, snapshot_id) is None:
        raise WebtrisAcquisitionError(
            "SNAPSHOT_ID_INVALID",
            "accepted WebTRIS snapshot ID has an invalid or unsafe shape",
        )
    accepted_dir = workspace / ACCEPTED_DIRECTORY_NAME / snapshot_id
    try:
        receipt = verify_manchester_snapshot(accepted_dir)
        manifest = ManchesterSnapshotManifest.model_validate_json(
            _read_bounded_regular_file(
                accepted_dir / MANIFEST_FILE_NAME,
                max_bytes=MAX_MANIFEST_FILE_BYTES,
                code="ACCEPTED_SNAPSHOT_INVALID",
                description="accepted WebTRIS manifest",
                accepted_snapshot_id=snapshot_id,
            )
        )
    except WebtrisAcquisitionError:
        raise
    except (ManchesterSnapshotError, ValidationError, OSError) as exc:
        raise WebtrisAcquisitionError(
            "ACCEPTED_SNAPSHOT_INVALID",
            "the accepted WebTRIS snapshot could not be re-verified",
            accepted_snapshot_id=snapshot_id,
        ) from exc

    product = _accepted_product_from_source_id(manifest.source.source_id, snapshot_id)
    site_id, report_date, page_size = _validate_accepted_manifest_contract(manifest, product)
    members = _read_accepted_webtris_members(
        accepted_dir,
        manifest,
        max_member_bytes=receipt.policy.max_member_bytes,
    )
    report: WebtrisSiteParseReport | WebtrisDailyParseReport | None
    site_name: str | None
    site_name_basis: Literal["source_record", "not_present_in_product"]
    if product == "site":
        try:
            parsed_site = parse_webtris_site(members[0])
        except WebtrisAdapterError as exc:
            raise WebtrisAcquisitionError(
                "ACCEPTED_PARSER_INTEGRITY",
                "the accepted WebTRIS site bytes no longer pass the MAN-03 parser",
                accepted_snapshot_id=snapshot_id,
            ) from exc
        if len(parsed_site.records) != 1 or parsed_site.records[0].site_id != site_id:
            raise WebtrisAcquisitionError(
                "ACCEPTED_SCOPE_MISMATCH",
                "the accepted WebTRIS site response does not match its selected endpoint ID",
                accepted_snapshot_id=snapshot_id,
            )
        report = parsed_site
        site_name = parsed_site.records[0].name
        site_name_basis = "source_record"
    elif product == "daily_report":
        if report_date is None:  # pragma: no cover - manifest contract invariant
            raise WebtrisAcquisitionError(
                "ACCEPTED_SCOPE_MISMATCH",
                "the accepted daily-report scope is incomplete",
                accepted_snapshot_id=snapshot_id,
            )
        site_name = _discover_daily_report_site_name(members, snapshot_id)
        scope = WebtrisDailyScope(
            site_id=site_id,
            site_name=site_name,
            report_date=report_date,
        )
        try:
            report = parse_webtris_daily_report(members, scope)
        except WebtrisAdapterError as exc:
            raise WebtrisAcquisitionError(
                "ACCEPTED_PARSER_INTEGRITY",
                "the accepted WebTRIS daily pages no longer pass the MAN-03 parser",
                accepted_snapshot_id=snapshot_id,
            ) from exc
        site_name_basis = "source_record"
    else:
        report = None
        site_name = None
        site_name_basis = "not_present_in_product"

    if report is not None:
        if report.status is ManchesterValidationState.REJECTED:
            raise WebtrisAcquisitionError(
                "ACCEPTED_PARSER_REJECTED",
                "a rejected WebTRIS parser report cannot be consumed as accepted evidence",
                accepted_snapshot_id=snapshot_id,
            )
        findings_match = manifest.findings == _snapshot_findings(report)
        if manifest.validation_state is not report.status or not findings_match:
            raise WebtrisAcquisitionError(
                "ACCEPTED_VALIDATION_MISMATCH",
                "the accepted manifest does not reproduce the current WebTRIS validation result",
                accepted_snapshot_id=snapshot_id,
            )

    summary = WebtrisAcceptedSnapshotSummary(
        product=product,
        source_id=_PRODUCT_SOURCE_IDS[product],
        endpoint_path=_endpoint_path(product, site_id),
        site_id=site_id,
        site_name=site_name,
        site_name_basis=site_name_basis,
        report_date=report_date,
        page_size=page_size,
        snapshot_id=snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        manifest_fingerprint=manifest.fingerprint(),
        snapshot_receipt_fingerprint=receipt.fingerprint(),
        retrieval_started_at_utc=manifest.retrieval.started_at_utc,
        retrieval_completed_at_utc=manifest.retrieval.completed_at_utc,
        pages=manifest.member_count,
        total_bytes=manifest.total_bytes,
        stored_validation_state=manifest.validation_state,
        parser_replay_state="scope_unavailable" if report is None else "reproduced",
        parser_report_fingerprint=None if report is None else report.fingerprint(),
        rows_seen=None if report is None else report.counts.rows_seen,
        records_accepted=None if report is None else report.counts.records_accepted,
        intervals_missing=None if report is None else report.counts.intervals_missing,
        publication_class=manifest.publication_class,
        attribution_text=manifest.attribution_text,
        synthetic=manifest.synthetic,
    )
    return WebtrisAcceptedSnapshotLoad(
        summary=summary,
        manifest=manifest,
        receipt=receipt,
        report=report,
    )


def _accepted_product_from_source_id(source_id: str, snapshot_id: str) -> WebtrisProduct:
    for product, accepted_source_id in _PRODUCT_SOURCE_IDS.items():
        if source_id == accepted_source_id:
            return product
    raise WebtrisAcquisitionError(
        "PRODUCT_MISMATCH",
        "the accepted snapshot is not one of the audited WebTRIS products",
        accepted_snapshot_id=snapshot_id,
    )


def _validate_accepted_manifest_contract(
    manifest: ManchesterSnapshotManifest,
    product: WebtrisProduct,
) -> tuple[str, date | None, int | None]:
    snapshot_id = manifest.snapshot_id
    source = manifest.source
    if (
        source.source_id != _PRODUCT_SOURCE_IDS[product]
        or source.adapter_version != WEBTRIS_ACQUISITION_METHOD_VERSION
        or source.source_schema_version != WEBTRIS_ACQUISITION_SCHEMA_VERSION
        or source.freshness_policy_version != WEBTRIS_FRESHNESS_POLICY_VERSION
        or manifest.request.host != WEBTRIS_SOURCE_HOST
        or manifest.request.redacted_parameter_names
        or manifest.licence_id != WEBTRIS_LICENCE_ID
        or manifest.attribution_text != WEBTRIS_ATTRIBUTION_TEXT
    ):
        raise WebtrisAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "the accepted snapshot does not bind the audited WebTRIS source contract",
            accepted_snapshot_id=snapshot_id,
        )
    if any(member.media_type != "application/json" for member in manifest.members):
        raise WebtrisAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "accepted WebTRIS members must retain their JSON media type",
            accepted_snapshot_id=snapshot_id,
        )

    parameters = dict(manifest.request.parameters)
    report_date: date | None = None
    page_size: int | None = None
    expected_paths: tuple[str, ...]
    if product == "site":
        matched = re.fullmatch(r"/api/v1\.0/sites/([1-9][0-9]{0,9})", manifest.request.path)
        if matched is None or parameters:
            raise WebtrisAcquisitionError(
                "SCOPE_MISMATCH",
                "accepted WebTRIS site scope does not match the audited endpoint",
                accepted_snapshot_id=snapshot_id,
            )
        site_id = matched.group(1)
        expected_paths = (_SINGLE_MEMBER_PATHS["site"],)
    elif product == "daily_report":
        if manifest.request.path != WEBTRIS_DAILY_REPORT_PATH or set(parameters) != {
            "sites",
            "start_date",
            "end_date",
            "page",
            "page_size",
        }:
            raise WebtrisAcquisitionError(
                "SCOPE_MISMATCH",
                "accepted WebTRIS daily-report request scope is not exact",
                accepted_snapshot_id=snapshot_id,
            )
        site_id = _accepted_site_id(parameters.get("sites"), snapshot_id)
        report_date = _accepted_report_date(parameters, snapshot_id)
        if parameters.get("page") != "1":
            raise WebtrisAcquisitionError(
                "SCOPE_MISMATCH",
                "accepted WebTRIS daily-report pagination must start at page one",
                accepted_snapshot_id=snapshot_id,
            )
        page_size = _bounded_decimal_parameter(
            parameters.get("page_size"), 1, 96, snapshot_id, "page_size"
        )
        expected_paths = tuple(
            f"pages/page-{page_number:04d}.json"
            for page_number in range(1, manifest.member_count + 1)
        )
    else:
        if manifest.request.path != WEBTRIS_DAILY_QUALITY_PATH or set(parameters) != {
            "siteId",
            "start_date",
            "end_date",
        }:
            raise WebtrisAcquisitionError(
                "SCOPE_MISMATCH",
                "accepted WebTRIS daily-quality request scope is not exact",
                accepted_snapshot_id=snapshot_id,
            )
        site_id = _accepted_site_id(parameters.get("siteId"), snapshot_id)
        report_date = _accepted_report_date(parameters, snapshot_id)
        expected_paths = (_SINGLE_MEMBER_PATHS["daily_quality"],)

    if tuple(member.relative_path for member in manifest.members) != expected_paths:
        raise WebtrisAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "accepted WebTRIS member inventory does not match its product",
            accepted_snapshot_id=snapshot_id,
        )
    return site_id, report_date, page_size


def _accepted_site_id(value: object, snapshot_id: str) -> str:
    if not isinstance(value, str) or re.fullmatch(_SITE_ID_PATTERN, value) is None:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "accepted WebTRIS request carries an invalid site ID",
            accepted_snapshot_id=snapshot_id,
        )
    return value


def _accepted_report_date(parameters: Mapping[str, object], snapshot_id: str) -> date:
    start = parameters.get("start_date")
    end = parameters.get("end_date")
    if start != end or not isinstance(start, str) or re.fullmatch(r"[0-9]{8}", start) is None:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "accepted WebTRIS daily request must bind one exact source date",
            accepted_snapshot_id=snapshot_id,
        )
    try:
        parsed = datetime.strptime(start, "%d%m%Y").date()
    except ValueError as exc:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "accepted WebTRIS daily request date is invalid",
            accepted_snapshot_id=snapshot_id,
        ) from exc
    if parsed.strftime("%d%m%Y") != start:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "accepted WebTRIS daily request date is not canonical",
            accepted_snapshot_id=snapshot_id,
        )
    return parsed


def _bounded_decimal_parameter(
    value: object,
    minimum: int,
    maximum: int,
    snapshot_id: str,
    name: str,
) -> int:
    parsed = -1 if not isinstance(value, str) or not value.isdigit() else int(value)
    if not minimum <= parsed <= maximum:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            f"accepted WebTRIS request parameter {name!r} is outside its bound",
            accepted_snapshot_id=snapshot_id,
        )
    return parsed


def _read_accepted_webtris_members(
    accepted_dir: Path,
    manifest: ManchesterSnapshotManifest,
    *,
    max_member_bytes: int,
) -> tuple[tuple[WebtrisMemberRef, bytes], ...]:
    members: list[tuple[WebtrisMemberRef, bytes]] = []
    for member in manifest.members:
        payload = _read_bounded_regular_file(
            accepted_dir / RAW_DIRECTORY_NAME / member.relative_path,
            max_bytes=max_member_bytes,
            expected_size=member.byte_size,
            code="ACCEPTED_SNAPSHOT_INVALID",
            description=f"accepted WebTRIS member {member.relative_path!r}",
            accepted_snapshot_id=manifest.snapshot_id,
        )
        if sha256_hex(payload) != member.sha256:
            raise WebtrisAcquisitionError(
                "ACCEPTED_SNAPSHOT_INVALID",
                f"accepted WebTRIS member {member.relative_path!r} changed after verification",
                accepted_snapshot_id=manifest.snapshot_id,
            )
        parser_payload = decode_webtris_http_payload(
            payload,
            content_encoding=_manifest_content_encoding(manifest),
        )
        members.append(
            (
                _member_ref(
                    manifest,
                    member.relative_path,
                    member.sha256,
                    parser_payload=parser_payload,
                ),
                parser_payload,
            )
        )
    return tuple(members)


def _discover_daily_report_site_name(
    members: tuple[tuple[WebtrisMemberRef, bytes], ...],
    snapshot_id: str,
) -> str:
    """Discover only the source-reported name needed to replay the full parser."""

    names: set[str] = set()
    try:
        for _reference, payload in members:
            decoded = json.loads(
                payload.decode("utf-8"),
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-standard JSON constant {value!r}")
                ),
            )
            if not isinstance(decoded, dict) or not isinstance(decoded.get("Rows"), list):
                raise ValueError("daily envelope is not an object with Rows")
            for row in decoded["Rows"]:
                if not isinstance(row, dict):
                    raise ValueError("daily row is not an object")
                name = row.get("Site Name")
                if not isinstance(name, str) or not name or name.strip() != name or len(name) > 120:
                    raise ValueError("daily Site Name is invalid")
                names.add(name)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise WebtrisAcquisitionError(
            "ACCEPTED_SCOPE_MISMATCH",
            "the accepted daily report cannot reproduce one source-reported site name",
            accepted_snapshot_id=snapshot_id,
        ) from exc
    if len(names) != 1:
        raise WebtrisAcquisitionError(
            "ACCEPTED_SCOPE_MISMATCH",
            "the accepted daily report does not contain one source-reported site name",
            accepted_snapshot_id=snapshot_id,
        )
    return next(iter(names))


def _snapshot_findings(
    report: WebtrisSiteParseReport | WebtrisDailyParseReport,
) -> tuple[ManchesterSnapshotFinding, ...]:
    return tuple(
        ManchesterSnapshotFinding(
            code=finding.code,
            severity=finding.severity,
            message=(
                finding.message
                if finding.row_index is None
                else f"{finding.message} (row {finding.row_index})"
            ),
            artifact=finding.member_path,
        )
        for finding in report.findings
    )


def _endpoint_path(product: WebtrisProduct, site_id: str) -> str:
    if product == "site":
        return f"{WEBTRIS_SITES_PATH_PREFIX}/{site_id}"
    if product == "daily_report":
        return WEBTRIS_DAILY_REPORT_PATH
    return WEBTRIS_DAILY_QUALITY_PATH


def _daily_report_query(
    request: WebtrisAcquisitionRequest, page_number: int
) -> dict[str, int | str]:
    if request.report_date is None or request.page_size is None:  # pragma: no cover
        raise WebtrisAcquisitionError("PAGINATION_PEEK_FAILED", "invalid daily request")
    request_date = request.report_date.strftime("%d%m%Y")
    return {
        "sites": request.site_id,
        "start_date": request_date,
        "end_date": request_date,
        "page": page_number,
        "page_size": request.page_size,
    }


def _single_query(request: WebtrisAcquisitionRequest) -> dict[str, int | str]:
    if request.product == "site":
        return {}
    if request.report_date is None:  # pragma: no cover - model invariant
        raise WebtrisAcquisitionError("QUARANTINE_INVALID", "invalid quality request")
    request_date = request.report_date.strftime("%d%m%Y")
    return {"siteId": request.site_id, "start_date": request_date, "end_date": request_date}


def _fetch(
    client: BoundedHttpClient,
    path: str,
    query: dict[str, int | str],
    member_path: str,
    page_number: int,
) -> ManchesterHttpSnapshotParts:
    try:
        response = client.fetch(path, query=query)
    except ManchesterTransportError as exc:
        raise WebtrisAcquisitionError(
            "TRANSPORT_FAILURE",
            f"bounded transport failed on page {page_number} ({exc.code}); "
            "WebTRIS unavailability is a typed failure, never zero traffic",
        ) from exc
    return snapshot_parts_from_http_response(
        response,
        relative_path=member_path,
        media_type="application/json",
    )


def _peek_daily_row_count(payload: bytes, page_number: int) -> int:
    """Read only Header.row_count to size the page loop; no records are created."""

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebtrisAcquisitionError(
            "PAGINATION_PEEK_FAILED", f"page {page_number} is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(decoded, dict) or not isinstance(decoded.get("Header"), dict):
        raise WebtrisAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} is not the audited daily-report envelope",
        )
    row_count = decoded["Header"].get("row_count")
    if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0:
        raise WebtrisAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} Header.row_count is not a valid integer",
        )
    return row_count


def _source_identity(product: WebtrisProduct) -> ManchesterSourceIdentity:
    return ManchesterSourceIdentity(
        source_id=_PRODUCT_SOURCE_IDS[product],
        source_name=f"National Highways WebTRIS {product.replace('_', ' ')}",
        adapter_version=WEBTRIS_ACQUISITION_METHOD_VERSION,
        source_schema_version=WEBTRIS_ACQUISITION_SCHEMA_VERSION,
        freshness_policy_version=WEBTRIS_FRESHNESS_POLICY_VERSION,
    )


def _admit_or_raise(
    report: WebtrisAnyParseReport,
    admitted_warning_codes: tuple[str, ...],
    snapshot_id: str,
) -> None:
    if report.status is ManchesterValidationState.REJECTED:
        raise WebtrisAcquisitionError(
            "PARSE_REJECTED",
            "the MAN-03 parser rejected the quarantined evidence",
            quarantine_snapshot_id=snapshot_id,
        )
    if report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS:
        observed = sorted({finding.code for finding in report.findings})
        unapproved = [code for code in observed if code not in admitted_warning_codes]
        if unapproved:
            raise WebtrisAcquisitionError(
                "WARNINGS_REFUSED",
                f"{len(unapproved)} warning code(s) are not in the admitted set: "
                + ", ".join(unapproved),
                quarantine_snapshot_id=snapshot_id,
            )


def _load_quarantine_manifest(quarantine_dir: Path) -> ManchesterQuarantineManifest:
    manifest_path = quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME
    return ManchesterQuarantineManifest.model_validate_json(
        _read_bounded_regular_file(
            manifest_path,
            max_bytes=MAX_QUARANTINE_MANIFEST_BYTES,
            code="QUARANTINE_INVALID",
            description="quarantine manifest",
            quarantine_snapshot_id=quarantine_dir.name,
        )
    )


def _bind_replay_claim(
    manifest: ManchesterQuarantineManifest, request: WebtrisReplayRequest
) -> None:
    snapshot_id = manifest.snapshot_id
    if manifest.source.source_id != _PRODUCT_SOURCE_IDS[request.product]:
        raise WebtrisAcquisitionError(
            "PRODUCT_MISMATCH",
            "quarantined source id does not match the claimed WebTRIS product",
            quarantine_snapshot_id=snapshot_id,
        )
    if (
        manifest.source.adapter_version != WEBTRIS_ACQUISITION_METHOD_VERSION
        or manifest.source.source_schema_version != WEBTRIS_ACQUISITION_SCHEMA_VERSION
        or manifest.source.freshness_policy_version != WEBTRIS_FRESHNESS_POLICY_VERSION
        or manifest.licence_id != WEBTRIS_LICENCE_ID
        or manifest.attribution_text != WEBTRIS_ATTRIBUTION_TEXT
        or manifest.request.host != WEBTRIS_SOURCE_HOST
    ):
        raise WebtrisAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined source contract does not match this adapter version",
            quarantine_snapshot_id=snapshot_id,
        )
    if manifest.request.path != _endpoint_path(request.product, request.site_id):
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "quarantined request path does not match the claimed product/site",
            quarantine_snapshot_id=snapshot_id,
        )
    expected_parameters = _expected_stored_parameters(request)
    if tuple(manifest.request.parameters) != expected_parameters:
        raise WebtrisAcquisitionError(
            "SCOPE_MISMATCH",
            "quarantined request parameters do not match the claimed scope",
            quarantine_snapshot_id=snapshot_id,
        )
    paths = [member.relative_path for member in manifest.members]
    if request.product == "daily_report":
        expected_paths = [f"pages/page-{index:04d}.json" for index in range(1, len(paths) + 1)]
        if paths != expected_paths:
            raise WebtrisAcquisitionError(
                "SOURCE_CONTRACT_MISMATCH",
                "quarantined member inventory is not a sequential daily-report page set",
                quarantine_snapshot_id=snapshot_id,
            )
    elif paths != [_SINGLE_MEMBER_PATHS[request.product]]:
        raise WebtrisAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined member inventory does not match the claimed product role",
            quarantine_snapshot_id=snapshot_id,
        )


def _expected_stored_parameters(
    request: WebtrisReplayRequest,
) -> tuple[tuple[str, str], ...]:
    if request.product == "site":
        return ()
    if request.report_date is None:  # pragma: no cover - model invariant
        raise WebtrisAcquisitionError("SCOPE_MISMATCH", "replay scope is incomplete")
    request_date = request.report_date.strftime("%d%m%Y")
    if request.product == "daily_quality":
        parameters = {
            "siteId": request.site_id,
            "start_date": request_date,
            "end_date": request_date,
        }
    else:
        if request.page_size is None:  # pragma: no cover - model invariant
            raise WebtrisAcquisitionError("SCOPE_MISMATCH", "replay scope is incomplete")
        parameters = {
            "sites": request.site_id,
            "start_date": request_date,
            "end_date": request_date,
            "page": "1",
            "page_size": str(request.page_size),
        }
    return tuple(sorted(parameters.items()))


def _parse_quarantined(
    quarantine_dir: Path,
    manifest: ManchesterQuarantineManifest,
    product: WebtrisProduct,
    site_id: str,
    site_name: str | None,
    report_date: date | None,
) -> WebtrisAnyParseReport:
    members: list[tuple[WebtrisMemberRef, bytes]] = []
    for member in manifest.members:
        target = quarantine_dir / RAW_DIRECTORY_NAME / member.relative_path
        payload = _read_bounded_regular_file(
            target,
            max_bytes=MAX_MEMBER_BYTES,
            expected_size=member.byte_size,
            code="QUARANTINE_INVALID",
            description=f"quarantined member {member.relative_path!r}",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
        if sha256_hex(payload) != member.sha256:
            raise WebtrisAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} hash drifted",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        parser_payload = decode_webtris_http_payload(
            payload,
            content_encoding=_manifest_content_encoding(manifest),
        )
        members.append(
            (
                _member_ref(
                    manifest,
                    member.relative_path,
                    member.sha256,
                    parser_payload=parser_payload,
                ),
                parser_payload,
            )
        )
    try:
        if product == "site":
            if len(members) != 1:  # pragma: no cover - bound by replay binding
                raise WebtrisAdapterError("NO_MEMBERS", "one site member is required")
            return parse_webtris_site(members[0])
        if site_name is None or report_date is None:  # pragma: no cover - model invariant
            raise WebtrisAdapterError("NO_MEMBERS", "daily scope is incomplete")
        scope = WebtrisDailyScope(site_id=site_id, site_name=site_name, report_date=report_date)
        if product == "daily_quality":
            if len(members) != 1:  # pragma: no cover - bound by replay binding
                raise WebtrisAdapterError("NO_MEMBERS", "one quality member is required")
            return parse_webtris_daily_quality(members[0], scope)
        return parse_webtris_daily_report(members, scope)
    except WebtrisAdapterError as exc:
        raise WebtrisAcquisitionError(
            "PARSE_INTEGRITY",
            f"the MAN-03 parser refused the quarantined member set ({exc.code})",
            quarantine_snapshot_id=manifest.snapshot_id,
        ) from exc


def _member_ref(
    manifest: ManchesterQuarantineManifest | ManchesterSnapshotManifest,
    relative_path: str,
    member_sha256: str,
    *,
    parser_payload: bytes,
) -> WebtrisMemberRef:
    if relative_path == _SINGLE_MEMBER_PATHS["site"]:
        role: Literal["site", "daily_report", "daily_quality"] = "site"
        page_number = 1
    elif relative_path == _SINGLE_MEMBER_PATHS["daily_quality"]:
        role = "daily_quality"
        page_number = 1
    else:
        matched = _PAGE_MEMBER_PATTERN.fullmatch(relative_path)
        if matched is None:
            raise WebtrisAcquisitionError(
                "SOURCE_CONTRACT_MISMATCH",
                f"quarantined member {relative_path!r} has no admitted WebTRIS role",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        role = "daily_report"
        page_number = int(matched.group(1))
    content_encoding = _manifest_content_encoding(manifest)
    return WebtrisMemberRef(
        snapshot_id=manifest.snapshot_id,
        member_path=relative_path,
        member_sha256=member_sha256,
        content_encoding="gzip" if content_encoding == "gzip" else "identity",
        parser_payload_sha256=(sha256_hex(parser_payload) if content_encoding == "gzip" else None),
        member_role=role,
        page_number=page_number,
        synthetic=manifest.synthetic,
    )


def decode_webtris_http_payload(
    payload: bytes,
    *,
    content_encoding: Literal["gzip", "deflate"] | None,
) -> bytes:
    """Decode verified WebTRIS wire bytes only after quarantine.

    The bounded transport preserves the exact HTTP entity.  The official service
    currently returns gzip content, so parser bytes are derived under a separate
    decompression bound and bound into ``WebtrisMemberRef``.  Deflate remains
    unaudited for this adapter and therefore fails closed.
    """

    if content_encoding is None:
        return payload
    if content_encoding != "gzip":
        raise WebtrisAcquisitionError(
            "CONTENT_ENCODING_REJECTED",
            "the WebTRIS adapter admits identity or bounded gzip content only",
        )
    try:
        return decompress_gzip(payload, policy=_WEBTRIS_GZIP_POLICY)
    except ManchesterArchiveError as exc:
        raise WebtrisAcquisitionError(
            "CONTENT_DECODING_FAILED",
            "the quarantined WebTRIS gzip response failed bounded decoding",
        ) from exc


def _manifest_content_encoding(
    manifest: ManchesterQuarantineManifest | ManchesterSnapshotManifest,
) -> Literal["gzip", "deflate"] | None:
    # Retained, directly published official fixtures predate HTTP metadata and
    # contain identity JSON bytes. Controlled network acquisitions always carry
    # ``http`` and therefore retain their observed wire encoding explicitly.
    return None if manifest.http is None else manifest.http.response_content_encoding


def _read_bounded_regular_file(
    target: Path,
    *,
    max_bytes: int,
    code: str,
    description: str,
    expected_size: int | None = None,
    quarantine_snapshot_id: str | None = None,
    accepted_snapshot_id: str | None = None,
) -> bytes:
    """Read one regular file from its opened descriptor with a hard cap."""

    if target.is_symlink():
        raise WebtrisAcquisitionError(
            code,
            f"the {description} is missing or unsafe",
            quarantine_snapshot_id=quarantine_snapshot_id,
            accepted_snapshot_id=accepted_snapshot_id,
        )
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(target, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise WebtrisAcquisitionError(
                code,
                f"the {description} is not a regular file",
                quarantine_snapshot_id=quarantine_snapshot_id,
                accepted_snapshot_id=accepted_snapshot_id,
            )
        if opened.st_size > max_bytes:
            raise WebtrisAcquisitionError(
                code,
                f"the {description} exceeds its byte bound",
                quarantine_snapshot_id=quarantine_snapshot_id,
                accepted_snapshot_id=accepted_snapshot_id,
            )
        if expected_size is not None and opened.st_size != expected_size:
            raise WebtrisAcquisitionError(
                code,
                f"the {description} size drifted",
                quarantine_snapshot_id=quarantine_snapshot_id,
                accepted_snapshot_id=accepted_snapshot_id,
            )
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            payload = handle.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise WebtrisAcquisitionError(
                code,
                f"the {description} exceeds its byte bound",
                quarantine_snapshot_id=quarantine_snapshot_id,
                accepted_snapshot_id=accepted_snapshot_id,
            )
        if expected_size is not None and len(payload) != expected_size:
            raise WebtrisAcquisitionError(
                code,
                f"the {description} size drifted",
                quarantine_snapshot_id=quarantine_snapshot_id,
                accepted_snapshot_id=accepted_snapshot_id,
            )
        return payload
    except WebtrisAcquisitionError:
        raise
    except OSError as exc:
        raise WebtrisAcquisitionError(
            code,
            f"the {description} is missing or unsafe",
            quarantine_snapshot_id=quarantine_snapshot_id,
            accepted_snapshot_id=accepted_snapshot_id,
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)

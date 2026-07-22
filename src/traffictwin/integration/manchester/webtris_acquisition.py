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
import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Literal, TypeAlias

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import (
    ManchesterHttpSnapshotParts,
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.models import (
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
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    QUARANTINE_DIRECTORY_NAME,
    quarantine_validate_and_promote,
    verify_manchester_quarantine,
)
from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)
from traffictwin.integration.manchester.webtris import (
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

WEBTRIS_ACQUISITION_SCHEMA_VERSION = "1.0"
WEBTRIS_ACQUISITION_METHOD_VERSION = "manchester-webtris-acquisition-1.0"
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

_EARLIEST_REPORT_DATE = date(1990, 1, 1)
_LATEST_REPORT_DATE = date(2100, 12, 31)


class WebtrisAcquisitionError(RuntimeError):
    """Typed deterministic acquisition/replay failure.

    ``quarantine_snapshot_id`` is set when complete raw evidence exists in
    quarantine (rejected parse, refused warnings, replay mismatch); it is
    ``None`` when the acquisition never became complete, in which case nothing
    durable was published.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        quarantine_snapshot_id: str | None = None,
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.quarantine_snapshot_id = quarantine_snapshot_id


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
            page_number = 1
            while True:
                parts = _fetch(
                    client,
                    endpoint_path,
                    _daily_report_query(request, page_number),
                    f"pages/page-{page_number:04d}.json",
                    page_number,
                )
                row_count = _peek_daily_row_count(parts.payload, page_number)
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
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise WebtrisAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest is missing or unsafe"
        )
    if manifest_path.stat().st_size > MAX_QUARANTINE_MANIFEST_BYTES:
        raise WebtrisAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest exceeds its byte bound"
        )
    return ManchesterQuarantineManifest.model_validate_json(manifest_path.read_bytes())


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
        if target.is_symlink() or not target.is_file():
            raise WebtrisAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} is missing or unsafe",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        if target.stat().st_size != member.byte_size:
            raise WebtrisAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} size drifted",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        payload = target.read_bytes()
        if sha256_hex(payload) != member.sha256:
            raise WebtrisAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} hash drifted",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        members.append((_member_ref(manifest, member.relative_path, member.sha256), payload))
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
    manifest: ManchesterQuarantineManifest, relative_path: str, member_sha256: str
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
    return WebtrisMemberRef(
        snapshot_id=manifest.snapshot_id,
        member_path=relative_path,
        member_sha256=member_sha256,
        member_role=role,
        page_number=page_number,
        synthetic=manifest.synthetic,
    )

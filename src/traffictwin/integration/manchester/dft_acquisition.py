"""Controlled DfT acquisition: bounded transport → quarantine → parse → promote.

This module wires the three audited DfT endpoints through the existing MAN-01
boundaries in a fixed order: the shared :class:`BoundedHttpClient` fetches each
page, every exact response body is preserved in MAN-01 quarantine, the MAN-02
parser validates the quarantined bytes, and only an accepted (or explicitly
policy-admitted warning-accepted) parse promotes the bytes to accepted storage.

It adds no second HTTP, hashing, or publication implementation, makes no
freshness claim beyond the parser's ``historical`` labels, performs no SUMO
conversion, and changes no capability state: ``MAN-01`` and ``MAN-02`` remain
``planned`` until lead acceptance.

Pagination control performs a bounded, read-only *peek* of the audited envelope
integers (``current_page``, ``per_page``, ``total``, ``last_page``) on each
already-size-bounded body solely to drive page iteration and limits. That peek
produces no records and is re-verified from quarantined bytes by the full
MAN-02 parser before anything is promoted.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal, TypeAlias

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import (
    ManchesterHttpSnapshotParts,
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.dft import (
    DFT_AADF_PATH,
    DFT_COUNT_POINTS_PATH,
    DFT_RAW_COUNTS_PATH,
    DFT_SOURCE_HOST,
    DftAadfParseReport,
    DftAdapterError,
    DftCountPointParseReport,
    DftManchesterScope,
    DftMemberRef,
    DftRawCountParseReport,
    parse_dft_aadf,
    parse_dft_count_points,
    parse_dft_raw_counts,
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

DFT_ACQUISITION_SCHEMA_VERSION = "1.0"
DFT_ACQUISITION_METHOD_VERSION = "manchester-dft-acquisition-1.0"
DFT_ACQUISITION_CAPABILITY_ID = "MAN-02"

DFT_LICENCE_ID = "OGL-v3.0"
DFT_ATTRIBUTION_TEXT = (
    "Contains public sector information from the Department for Transport Road "
    "Traffic Statistics service, licensed under the Open Government Licence v3.0."
)
DFT_FRESHNESS_POLICY_VERSION = "dft-historical-1.0"

MAX_QUARANTINE_MANIFEST_BYTES = 8_000_000
_SNAPSHOT_ID_PATTERN = r"^[a-z0-9][a-z0-9_.-]{0,95}-\d{8}T\d{6}Z-[0-9a-f]{12}$"

DftDataset: TypeAlias = Literal["raw_counts", "count_points", "aadf"]
DftSourceId: TypeAlias = Literal["dft_raw_counts", "dft_count_points", "dft_aadf"]
DftAnyParseReport: TypeAlias = (
    DftRawCountParseReport | DftCountPointParseReport | DftAadfParseReport
)

_DATASET_PATHS: dict[DftDataset, str] = {
    "raw_counts": DFT_RAW_COUNTS_PATH,
    "count_points": DFT_COUNT_POINTS_PATH,
    "aadf": DFT_AADF_PATH,
}
_DATASET_SOURCE_IDS: dict[DftDataset, DftSourceId] = {
    "raw_counts": "dft_raw_counts",
    "count_points": "dft_count_points",
    "aadf": "dft_aadf",
}

DFT_ENDPOINT_POLICY = EndpointPolicy(
    endpoint_id="dft-road-traffic",
    host=DFT_SOURCE_HOST,
    path_prefixes=(DFT_AADF_PATH, DFT_COUNT_POINTS_PATH, DFT_RAW_COUNTS_PATH),
    query_parameter_names=(
        "filter[id]",
        "filter[local_authority_id]",
        "filter[year]",
        "page[number]",
        "page[size]",
    ),
)

# Conservative self-imposed transport limits (the audit found no published DfT
# rate limits or SLAs; blockers GA-DFT-2/GA-DFT-3).
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


class DftAcquisitionError(RuntimeError):
    """Typed deterministic acquisition failure.

    ``quarantine_snapshot_id`` is set when complete raw evidence was preserved
    in quarantine before the failure (schema drift, rejected parse, refused
    warnings); it is ``None`` when the acquisition never became complete and
    therefore nothing durable was published.
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


class DftAcquisitionRequest(ManchesterSnapshotModel):
    """Strict typed acquisition request; no host, path, URL, or free query fields."""

    dataset: DftDataset
    scope: DftManchesterScope = DftManchesterScope()
    filter_id: int | None = Field(default=None, ge=1)
    year: int | None = Field(default=None, ge=1990, le=2100)
    page_size: int = Field(ge=1, le=500)
    max_pages: int = Field(ge=1, le=500)
    max_rows: int = Field(ge=1, le=200_000)
    policy: ManchesterSnapshotPolicy
    publication_class: ManchesterPublicationClass
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    accept_with_warnings: bool
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> DftAcquisitionRequest:
        if self.year is not None and self.dataset == "count_points":
            raise ValueError(
                "year filtering of count points is not an audited request shape; "
                "count-point rows carry aadf_year only"
            )
        if self.max_pages > self.policy.max_member_count:
            raise ValueError("max_pages cannot exceed the snapshot policy member bound")
        return self


class DftAcquisitionResult(ManchesterSnapshotModel):
    """Strict frozen receipt for one promoted DfT acquisition."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-dft-acquisition-1.0"] = "manchester-dft-acquisition-1.0"
    dataset: DftDataset
    endpoint_host: Literal["roadtraffic.dft.gov.uk"] = "roadtraffic.dft.gov.uk"
    endpoint_path: str
    request: DftAcquisitionRequest
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1)
    pages: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    quarantine_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool
    promoted: Literal[True] = True

    @model_validator(mode="after")
    def validate_result(self) -> DftAcquisitionResult:
        if self.endpoint_path != _DATASET_PATHS[self.dataset]:
            raise ValueError("endpoint path must match the selected DfT dataset")
        if self.request.dataset != self.dataset:
            raise ValueError("result dataset must match the acquisition request")
        if self.synthetic != self.request.synthetic:
            raise ValueError("result evidence class must match the acquisition request")
        if self.pages != len(self.members):
            raise ValueError("page count must match the member inventory")
        member_paths = [member.relative_path for member in self.members]
        if member_paths != sorted(member_paths) or len(set(member_paths)) != len(member_paths):
            raise ValueError("result members must be sorted and unique")
        expected_paths = [
            f"pages/page-{page_number:04d}.json" for page_number in range(1, self.pages + 1)
        ]
        if member_paths != expected_paths or any(
            member.media_type != "application/json" for member in self.members
        ):
            raise ValueError("result members must be exact sequential JSON pages")
        if self.raw_fingerprint != build_raw_fingerprint(self.members):
            raise ValueError("result raw fingerprint must bind the member inventory")
        if self.parser_status is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected parse can never produce a promoted result")
        if (
            self.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
            and not self.request.accept_with_warnings
        ):
            raise ValueError("warning-accepted result requires explicit request admission")
        return self


class DftReplayResult(ManchesterSnapshotModel):
    """Offline re-validation of already-quarantined bytes; no network, no promotion."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-02"] = "MAN-02"
    method_version: Literal["manchester-dft-acquisition-1.0"] = "manchester-dft-acquisition-1.0"
    dataset: DftDataset
    source_id: DftSourceId
    endpoint_path: str
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    pages: int = Field(ge=1)
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool
    replayed_offline: Literal[True] = True

    @model_validator(mode="after")
    def validate_binding(self) -> DftReplayResult:
        if self.source_id != _DATASET_SOURCE_IDS[self.dataset]:
            raise ValueError("replay source ID must match the selected DfT dataset")
        if self.endpoint_path != _DATASET_PATHS[self.dataset]:
            raise ValueError("replay endpoint must match the selected DfT dataset")
        return self


def acquire_dft_snapshot(
    workspace_root: str | Path,
    request: DftAcquisitionRequest,
    *,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> DftAcquisitionResult:
    """Acquire one audited DfT dataset window through quarantine into accepted storage.

    Order is fixed: fetch all pages under bounds, publish the complete raw set
    to MAN-01 quarantine, verify the quarantine, run the MAN-02 parser over the
    quarantined bytes, and promote only an accepted (or explicitly admitted
    warning-accepted) result. Every failure path publishes no accepted snapshot
    and never touches an existing one.
    """

    endpoint_path = _DATASET_PATHS[request.dataset]
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
    base_query: dict[str, int] = {
        "filter[local_authority_id]": request.scope.local_authority_id,
    }
    if request.filter_id is not None:
        base_query["filter[id]"] = request.filter_id
    if request.year is not None:
        base_query["filter[year]"] = request.year

    pages: list[ManchesterHttpSnapshotParts] = []
    total_bytes = 0
    first_peek: _EnvelopePeek | None = None
    with BoundedHttpClient(
        endpoint=DFT_ENDPOINT_POLICY,
        policy=transport_policy,
        client=http_client,
        utc_now=utc_now,
    ) as client:
        page_number = 1
        while True:
            query = dict(base_query)
            query["page[number]"] = page_number
            query["page[size]"] = request.page_size
            try:
                response = client.fetch(endpoint_path, query=query)
            except ManchesterTransportError as exc:
                raise DftAcquisitionError(
                    "TRANSPORT_FAILURE",
                    f"bounded transport failed on page {page_number} ({exc.code})",
                ) from exc
            parts = snapshot_parts_from_http_response(
                response,
                relative_path=f"pages/page-{page_number:04d}.json",
                media_type="application/json",
            )
            peek = _peek_envelope(parts.payload, page_number)
            if first_peek is None:
                if peek.current_page != 1:
                    raise DftAcquisitionError("PAGINATION_DRIFT", "first response is not page 1")
                if peek.per_page != request.page_size:
                    raise DftAcquisitionError(
                        "PAGINATION_DRIFT",
                        "source per_page does not match the requested page size",
                    )
                if peek.last_page > request.max_pages:
                    raise DftAcquisitionError(
                        "PAGE_LIMIT_EXCEEDED",
                        f"source reports {peek.last_page} pages; bound is {request.max_pages}",
                    )
                if peek.total > request.max_rows:
                    raise DftAcquisitionError(
                        "ROW_LIMIT_EXCEEDED",
                        f"source reports {peek.total} rows; bound is {request.max_rows}",
                    )
                first_peek = peek
            elif (
                peek.current_page != page_number
                or peek.per_page != first_peek.per_page
                or peek.total != first_peek.total
                or peek.last_page != first_peek.last_page
            ):
                raise DftAcquisitionError(
                    "PAGINATION_DRIFT",
                    f"page {page_number} envelope disagrees with page 1",
                )
            total_bytes += len(parts.payload)
            if total_bytes > request.policy.max_total_bytes:
                raise DftAcquisitionError(
                    "TOTAL_BYTES_EXCEEDED",
                    "combined page bytes exceed the snapshot policy bound",
                )
            pages.append(parts)
            if page_number >= first_peek.last_page:
                break
            page_number += 1

    members = {parts.member.relative_path: parts.payload for parts in pages}
    inventory = tuple(sorted((p.member for p in pages), key=lambda m: m.relative_path))
    raw_fingerprint = build_raw_fingerprint(inventory)
    source = ManchesterSourceIdentity(
        source_id=_DATASET_SOURCE_IDS[request.dataset],
        source_name=f"DfT Road Traffic Statistics {endpoint_path}",
        adapter_version=DFT_ACQUISITION_METHOD_VERSION,
        source_schema_version=DFT_ACQUISITION_SCHEMA_VERSION,
        freshness_policy_version=DFT_FRESHNESS_POLICY_VERSION,
    )
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
        licence_id=DFT_LICENCE_ID,
        attribution_text=DFT_ATTRIBUTION_TEXT,
        access_date=retrieval.started_at_utc.date(),
        synthetic=request.synthetic,
    )

    captured: dict[str, DftAnyParseReport] = {}

    def validator(
        quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        report = _parse_quarantined(quarantine_dir, manifest, request.scope, request.dataset)
        captured["report"] = report
        if report.status is ManchesterValidationState.REJECTED:
            raise DftAcquisitionError(
                "PARSE_REJECTED",
                "the MAN-02 parser rejected the quarantined evidence",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        if (
            report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS
            and not request.accept_with_warnings
        ):
            raise DftAcquisitionError(
                "WARNINGS_REFUSED",
                "warning-accepted evidence requires accept_with_warnings=True",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
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
    return DftAcquisitionResult(
        dataset=request.dataset,
        endpoint_path=endpoint_path,
        request=request,
        snapshot_id=quarantine_manifest.snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=inventory,
        pages=len(inventory),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        parser_status=report.status,
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
        synthetic=request.synthetic,
    )


def replay_dft_quarantine(
    workspace_root: str | Path,
    snapshot_id: str,
    dataset: DftDataset,
    *,
    scope: DftManchesterScope | None = None,
    expected_synthetic: bool | None = None,
) -> DftReplayResult:
    """Re-validate already-quarantined bytes offline; no network, no promotion."""

    quarantine_dir = Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    verify_manchester_quarantine(quarantine_dir)
    manifest = _load_quarantine_manifest(quarantine_dir)
    if manifest.snapshot_id != snapshot_id:
        raise DftAcquisitionError(
            "SNAPSHOT_ID_MISMATCH", "quarantine manifest does not match the requested id"
        )
    if expected_synthetic is not None and manifest.synthetic != expected_synthetic:
        raise DftAcquisitionError(
            "SYNTHETIC_MISMATCH",
            "quarantined evidence class does not match the caller's declaration",
            quarantine_snapshot_id=snapshot_id,
        )
    _validate_manifest_dataset(manifest, dataset)
    report = _parse_quarantined(quarantine_dir, manifest, scope or DftManchesterScope(), dataset)
    return DftReplayResult(
        dataset=dataset,
        source_id=_DATASET_SOURCE_IDS[dataset],
        endpoint_path=_DATASET_PATHS[dataset],
        snapshot_id=snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        pages=manifest.member_count,
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        parser_status=report.status,
        parser_report_fingerprint=report.fingerprint(),
        synthetic=manifest.synthetic,
    )


class _EnvelopePeek:
    def __init__(self, current_page: int, per_page: int, total: int, last_page: int) -> None:
        self.current_page = current_page
        self.per_page = per_page
        self.total = total
        self.last_page = last_page


def _peek_envelope(payload: bytes, page_number: int) -> _EnvelopePeek:
    """Read only the audited pagination integers to drive iteration bounds."""

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DftAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} is not valid UTF-8 JSON",
        ) from exc
    if not isinstance(decoded, dict):
        raise DftAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} is not the audited pagination envelope",
        )
    values: list[int] = []
    for key in ("current_page", "per_page", "total", "last_page"):
        value = decoded.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DftAcquisitionError(
                "PAGINATION_PEEK_FAILED",
                f"page {page_number} envelope field {key} is not a valid integer",
            )
        values.append(value)
    current_page, per_page, total, last_page = values
    if current_page < 1 or per_page < 1 or last_page < 1:
        raise DftAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} envelope pagination values are out of range",
        )
    expected_last_page = max(1, (total + per_page - 1) // per_page)
    if last_page != expected_last_page:
        raise DftAcquisitionError(
            "PAGINATION_PEEK_FAILED",
            f"page {page_number} last_page does not reconcile to total and per_page",
        )
    return _EnvelopePeek(current_page, per_page, total, last_page)


def _validate_manifest_dataset(
    manifest: ManchesterQuarantineManifest,
    dataset: DftDataset,
) -> None:
    """Bind offline replay to the exact acquired DfT source and request contract."""

    expected_source_id = _DATASET_SOURCE_IDS[dataset]
    expected_path = _DATASET_PATHS[dataset]
    source = manifest.source
    if source.source_id != expected_source_id or manifest.request.path != expected_path:
        raise DftAcquisitionError(
            "DATASET_MISMATCH",
            "quarantine source identity or endpoint does not match the requested dataset",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if (
        source.adapter_version != DFT_ACQUISITION_METHOD_VERSION
        or source.source_schema_version != DFT_ACQUISITION_SCHEMA_VERSION
        or source.freshness_policy_version != DFT_FRESHNESS_POLICY_VERSION
        or manifest.request.host != DFT_SOURCE_HOST
        or manifest.licence_id != DFT_LICENCE_ID
        or manifest.attribution_text != DFT_ATTRIBUTION_TEXT
    ):
        raise DftAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantine does not bind the accepted DfT source contract",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if manifest.request.redacted_parameter_names:
        raise DftAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "anonymous DfT request unexpectedly records redacted parameters",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    parameters = dict(manifest.request.parameters)
    allowed_parameters = set(DFT_ENDPOINT_POLICY.query_parameter_names)
    if (
        set(parameters) - allowed_parameters
        or _parameter_int(parameters, "filter[local_authority_id]") != 85
        or _parameter_int(parameters, "page[number]") != 1
        or not 1 <= _parameter_int(parameters, "page[size]") <= 500
        or (dataset == "count_points" and "filter[year]" in parameters)
    ):
        raise DftAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantine request parameters do not match the audited DfT request contract",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    filter_id = _optional_parameter_int(parameters, "filter[id]")
    year = _optional_parameter_int(parameters, "filter[year]")
    if (filter_id is not None and filter_id < 1) or (year is not None and not 1990 <= year <= 2100):
        raise DftAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantine filter values are outside the audited DfT request contract",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    expected_paths = tuple(
        f"pages/page-{page_number:04d}.json" for page_number in range(1, manifest.member_count + 1)
    )
    if tuple(member.relative_path for member in manifest.members) != expected_paths:
        raise DftAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantine page-member inventory is not exact and sequential",
            quarantine_snapshot_id=manifest.snapshot_id,
        )


def _parameter_int(
    parameters: dict[str, str | int | float | bool],
    name: str,
) -> int:
    value = parameters.get(name)
    if isinstance(value, bool):
        return -1
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return -1


def _optional_parameter_int(
    parameters: dict[str, str | int | float | bool],
    name: str,
) -> int | None:
    if name not in parameters:
        return None
    return _parameter_int(parameters, name)


def _load_quarantine_manifest(quarantine_dir: Path) -> ManchesterQuarantineManifest:
    manifest_path = quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise DftAcquisitionError("QUARANTINE_INVALID", "quarantine manifest is missing or unsafe")
    if manifest_path.stat().st_size > MAX_QUARANTINE_MANIFEST_BYTES:
        raise DftAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest exceeds its byte bound"
        )
    return ManchesterQuarantineManifest.model_validate_json(manifest_path.read_bytes())


def _parse_quarantined(
    quarantine_dir: Path,
    manifest: ManchesterQuarantineManifest,
    scope: DftManchesterScope,
    dataset: DftDataset,
) -> DftAnyParseReport:
    """Parse quarantined bytes with the existing MAN-02 parser; lineage re-checked."""

    members: list[tuple[DftMemberRef, bytes]] = []
    for page_number, member in enumerate(manifest.members, start=1):
        target = quarantine_dir / RAW_DIRECTORY_NAME / member.relative_path
        if target.is_symlink() or not target.is_file():
            raise DftAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} is missing or unsafe",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        if target.stat().st_size != member.byte_size:
            raise DftAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} size drifted",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        payload = target.read_bytes()
        if sha256_hex(payload) != member.sha256:
            raise DftAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} hash drifted",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        if _peek_envelope(payload, page_number).current_page != page_number:
            raise DftAcquisitionError(
                "QUARANTINE_INVALID",
                f"quarantined member {member.relative_path!r} carries the wrong page number",
                quarantine_snapshot_id=manifest.snapshot_id,
            )
        ref = DftMemberRef(
            snapshot_id=manifest.snapshot_id,
            member_path=member.relative_path,
            member_sha256=member.sha256,
            synthetic=manifest.synthetic,
        )
        members.append((ref, payload))
    try:
        if dataset == "raw_counts":
            return parse_dft_raw_counts(members, scope)
        if dataset == "count_points":
            return parse_dft_count_points(members, scope)
        return parse_dft_aadf(members, scope)
    except DftAdapterError as exc:
        raise DftAcquisitionError(
            "PARSE_INTEGRITY",
            f"the MAN-02 parser refused the quarantined member set ({exc.code})",
            quarantine_snapshot_id=manifest.snapshot_id,
        ) from exc

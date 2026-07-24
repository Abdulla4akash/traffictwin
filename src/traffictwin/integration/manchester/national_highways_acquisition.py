"""Bounded National Highways REST acquisition and immutable offline replay."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal, cast

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import snapshot_parts_from_http_response
from traffictwin.integration.manchester.archive import (
    ArchivePolicy,
    ManchesterArchiveError,
    decompress_gzip,
)
from traffictwin.integration.manchester.models import (
    MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
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
from traffictwin.integration.manchester.national_highways import (
    MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
    NATIONAL_HIGHWAYS_ATTRIBUTION,
    NATIONAL_HIGHWAYS_LICENCE_ID,
    NATIONAL_HIGHWAYS_SCHEMA_VERSION,
    NATIONAL_HIGHWAYS_SOURCE_HOST,
    NationalHighwaysEnvelope,
    NationalHighwaysError,
    NationalHighwaysEventType,
    NationalHighwaysParseReport,
    NationalHighwaysProduct,
    parse_national_highways_payload,
)
from traffictwin.integration.manchester.snapshots import (
    ACCEPTED_DIRECTORY_NAME,
    ManchesterSnapshotError,
    quarantine_validate_and_promote,
    read_manchester_member,
    verify_manchester_snapshot,
)
from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)
from traffictwin.release.compatibility import V07WorkspaceError, inspect_v07_workspace

NATIONAL_HIGHWAYS_ACQUISITION_VERSION = "national-highways-acquisition-1.0"
NATIONAL_HIGHWAYS_SECRET_HEADER = "Ocp-Apim-Subscription-Key"  # noqa: S105
NATIONAL_HIGHWAYS_MEDIA_HEADER = "X-Response-MediaType"
NATIONAL_HIGHWAYS_FORMAT_HEADER = "X-Data-Format"
NATIONAL_HIGHWAYS_MEMBER_PATH = "feed/datex-ii.json"
NATIONAL_HIGHWAYS_SNAPSHOT_POLICY = ManchesterSnapshotPolicy(
    max_member_count=1,
    max_member_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
    max_total_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
)
_GZIP_POLICY = ArchivePolicy(
    max_compressed_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
    max_decompressed_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
    max_member_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
    max_members=1,
    max_compression_ratio=200.0,
)

_PATHS: dict[NationalHighwaysProduct, str] = {
    "closures": "/roads/v2.0/closures",
    "speed_limits": "/sma/v1.0/speedManagedAreas",
    "vms": "/dvms/v1.0/vms",
}
_SOURCE_IDS: dict[NationalHighwaysProduct, str] = {
    "closures": "national_highways_closures",
    "speed_limits": "national_highways_speed_limits",
    "vms": "national_highways_vms",
}
_QUERY_NAMES: dict[NationalHighwaysProduct, tuple[str, ...]] = {
    "closures": ("closureType", "endDateTime", "startDateTime"),
    "speed_limits": ("endDateTime", "speedRestrictionType", "startDateTime"),
    "vms": ("bBox",),
}


class NationalHighwaysAcquisitionError(RuntimeError):
    """Display-safe acquisition refusal without a URL, key, body, or path."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NationalHighwaysAcquisitionRequest(ManchesterSnapshotModel):
    """Strict product request with no host, URL, header, or credential field."""

    product: NationalHighwaysProduct
    envelope: NationalHighwaysEnvelope
    event_type: NationalHighwaysEventType | None = None
    window_start_utc: datetime | None = None
    window_end_utc: datetime | None = None
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> NationalHighwaysAcquisitionRequest:
        is_vms = self.product == "vms"
        window_values = (self.window_start_utc, self.window_end_utc)
        if is_vms:
            if self.event_type is not None or any(value is not None for value in window_values):
                raise ValueError("Digital VMS accepts only the explicit envelope")
            return self
        if self.event_type is None or any(value is None for value in window_values):
            raise ValueError("closure and speed requests require type and UTC window")
        start = cast(datetime, self.window_start_utc)
        end = cast(datetime, self.window_end_utc)
        if start.tzinfo is None or start.utcoffset() != timedelta(0):
            raise ValueError("window start must be UTC")
        if end.tzinfo is None or end.utcoffset() != timedelta(0):
            raise ValueError("window end must be UTC")
        if start >= end or end - start > timedelta(hours=24):
            raise ValueError("window must be increasing and no longer than 24 hours")
        return self


class NationalHighwaysAcquisitionResult(ManchesterSnapshotModel):
    """Secret-free immutable receipt for one promoted operational snapshot."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-01"] = "MAN-01"
    method_version: Literal["national-highways-acquisition-1.0"] = (
        "national-highways-acquisition-1.0"
    )
    request: NationalHighwaysAcquisitionRequest
    source_id: Literal[
        "national_highways_closures",
        "national_highways_speed_limits",
        "national_highways_vms",
    ]
    endpoint_path: Literal[
        "/roads/v2.0/closures",
        "/sma/v1.0/speedManagedAreas",
        "/dvms/v1.0/vms",
    ]
    snapshot_id: str
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    parser_payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_time_utc: datetime
    source_items_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    outside_envelope: int = Field(ge=0)
    coordinates_missing: int = Field(ge=0)
    exact_duplicates_collapsed: int = Field(ge=0)
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_class: Literal["private"] = "private"
    licence_id: Literal["NH-Transport-Data-Feeds"] = "NH-Transport-Data-Feeds"
    attribution_text: Literal["Powered by National Highways’ Transport Data Feeds"] = (
        "Powered by National Highways’ Transport Data Feeds"
    )
    subscription_key_persisted: Literal[False] = False
    source_scope: Literal["strategic_road_network"] = "strategic_road_network"
    complete_manchester_coverage: Literal[False] = False
    synthetic: bool

    @model_validator(mode="after")
    def validate_result(self) -> NationalHighwaysAcquisitionResult:
        if self.source_id != _SOURCE_IDS[self.request.product]:
            raise ValueError("acquisition source must match the product")
        if self.endpoint_path != _PATHS[self.request.product]:
            raise ValueError("acquisition endpoint must match the product")
        if self.synthetic != self.request.synthetic:
            raise ValueError("acquisition evidence class must match its request")
        if self.source_items_seen != (
            self.records_accepted
            + self.outside_envelope
            + self.coordinates_missing
            + self.exact_duplicates_collapsed
        ):
            raise ValueError("acquisition counts must reconcile")
        return self


@dataclass(frozen=True, slots=True)
class NationalHighwaysAcquisition:
    """Runtime result containing both the compact receipt and projected records."""

    result: NationalHighwaysAcquisitionResult
    report: NationalHighwaysParseReport


def acquire_national_highways_snapshot(
    workspace_root: str | Path,
    request: NationalHighwaysAcquisitionRequest,
    *,
    subscription_key: str,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> NationalHighwaysAcquisition:
    """Fetch one product through bounded transport, quarantine, parser, and promotion."""

    workspace = _workspace(workspace_root)
    if (
        not subscription_key
        or len(subscription_key) > 4096
        or any(character in subscription_key for character in "\r\n")
    ):
        raise NationalHighwaysAcquisitionError("CREDENTIAL_INVALID", "subscription key withheld")
    if not request.synthetic and (http_client is not None or utc_now is not None):
        raise NationalHighwaysAcquisitionError(
            "REAL_SOURCE_SEAM_REFUSED",
            "real acquisition requires the module-owned transport and UTC clock",
        )
    endpoint = EndpointPolicy(
        endpoint_id=f"national-highways-{request.product.replace('_', '-')}",
        host=NATIONAL_HIGHWAYS_SOURCE_HOST,
        path_prefixes=(_PATHS[request.product],),
        query_parameter_names=_QUERY_NAMES[request.product],
        secret_header_names=(NATIONAL_HIGHWAYS_SECRET_HEADER,),
        fixed_request_headers=(
            (NATIONAL_HIGHWAYS_FORMAT_HEADER, "DATEXII"),
            (NATIONAL_HIGHWAYS_MEDIA_HEADER, "application/json"),
        ),
    )
    policy = TransportPolicy(
        connect_timeout_s=10.0,
        read_timeout_s=45.0,
        write_timeout_s=10.0,
        pool_timeout_s=10.0,
        total_deadline_s=90.0,
        max_response_bytes=MAX_NATIONAL_HIGHWAYS_RESPONSE_BYTES,
        max_redirects=1,
        max_attempts=2,
        backoff_base_s=0.2,
        backoff_max_s=1.0,
        allowed_media_types=("application/json", "text/json"),
    )
    try:
        with BoundedHttpClient(
            endpoint=endpoint,
            policy=policy,
            client=http_client,
            utc_now=utc_now,
        ) as client:
            response = client.fetch(
                _PATHS[request.product],
                query=_query(request),
                secret_headers={NATIONAL_HIGHWAYS_SECRET_HEADER: subscription_key},
            )
    except ManchesterTransportError as exc:
        raise NationalHighwaysAcquisitionError(
            "TRANSPORT_FAILURE",
            f"bounded National Highways request failed ({exc.code}); cached evidence is unchanged",
        ) from exc
    parts = snapshot_parts_from_http_response(
        response,
        relative_path=NATIONAL_HIGHWAYS_MEMBER_PATH,
        media_type=_response_media_type(response),
    )
    raw_fingerprint = build_raw_fingerprint((parts.member,))
    source_id = _SOURCE_IDS[request.product]
    source = ManchesterSourceIdentity(
        source_id=source_id,
        source_name=_source_name(request.product),
        adapter_version=NATIONAL_HIGHWAYS_ACQUISITION_VERSION,
        source_schema_version=NATIONAL_HIGHWAYS_SCHEMA_VERSION,
        freshness_policy_version="manchester-freshness-v1",
    )
    quarantine = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(
            source_id,
            parts.retrieval.started_at_utc,
            raw_fingerprint,
        ),
        source=source,
        request=parts.request,
        retrieval=parts.retrieval,
        http=parts.http,
        members=(parts.member,),
        member_count=1,
        total_bytes=parts.member.byte_size,
        raw_fingerprint=raw_fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=NATIONAL_HIGHWAYS_LICENCE_ID,
        attribution_text=NATIONAL_HIGHWAYS_ATTRIBUTION,
        access_date=parts.retrieval.started_at_utc.date(),
        synthetic=request.synthetic,
    )
    captured: list[NationalHighwaysParseReport] = []

    def validator(
        quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        raw_payload = _verified_member(quarantine_dir, manifest)
        payload = _decode_http_payload(raw_payload, manifest)
        report = parse_national_highways_payload(
            payload,
            product=request.product,
            envelope=request.envelope,
            synthetic=request.synthetic,
        )
        captured.append(report)
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
            validation_state=ManchesterValidationState.ACCEPTED,
            prior=request.prior,
            publication_class=manifest.publication_class,
            licence_id=manifest.licence_id,
            attribution_text=manifest.attribution_text,
            access_date=manifest.access_date,
            synthetic=manifest.synthetic,
        )

    try:
        receipt = quarantine_validate_and_promote(
            workspace,
            quarantine,
            {NATIONAL_HIGHWAYS_MEMBER_PATH: parts.payload},
            NATIONAL_HIGHWAYS_SNAPSHOT_POLICY,
            validator,
        )
    except (ManchesterSnapshotError, NationalHighwaysError) as exc:
        code = getattr(exc, "code", "SNAPSHOT_REJECTED")
        raise NationalHighwaysAcquisitionError(
            code, "National Highways response was quarantined but not accepted"
        ) from exc
    report = captured[0]
    result = _result(request, quarantine, receipt, report)
    return NationalHighwaysAcquisition(result=result, report=report)


def replay_national_highways_snapshot(
    workspace_root: str | Path,
    snapshot_id: str,
    request: NationalHighwaysAcquisitionRequest,
) -> NationalHighwaysParseReport:
    """Re-verify and reparse one accepted snapshot without network access."""

    workspace = _workspace(workspace_root)
    directory = workspace / ACCEPTED_DIRECTORY_NAME / snapshot_id
    verify_manchester_snapshot(directory)
    manifest = ManchesterSnapshotManifest.model_validate_json(
        (directory / MANIFEST_FILE_NAME).read_bytes()
    )
    _bind_manifest(manifest, request)
    raw_payload = read_manchester_member(directory, NATIONAL_HIGHWAYS_MEMBER_PATH)
    payload = _decode_http_payload(raw_payload, manifest)
    report = parse_national_highways_payload(
        payload,
        product=request.product,
        envelope=request.envelope,
        synthetic=request.synthetic,
    )
    if sha256_hex(raw_payload) != manifest.members[0].sha256:
        raise NationalHighwaysAcquisitionError(
            "REPLAY_HASH_MISMATCH", "offline replay did not reproduce the accepted raw hash"
        )
    return report


def _result(
    request: NationalHighwaysAcquisitionRequest,
    manifest: ManchesterQuarantineManifest,
    receipt: ManchesterSnapshotReceipt,
    report: NationalHighwaysParseReport,
) -> NationalHighwaysAcquisitionResult:
    counts = report.counts
    return NationalHighwaysAcquisitionResult(
        request=request,
        source_id=cast(
            Literal[
                "national_highways_closures",
                "national_highways_speed_limits",
                "national_highways_vms",
            ],
            _SOURCE_IDS[request.product],
        ),
        endpoint_path=cast(
            Literal[
                "/roads/v2.0/closures",
                "/sma/v1.0/speedManagedAreas",
                "/dvms/v1.0/vms",
            ],
            _PATHS[request.product],
        ),
        snapshot_id=manifest.snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        raw_sha256=manifest.members[0].sha256,
        parser_payload_sha256=report.raw_sha256,
        publication_time_utc=report.publication_time_utc,
        source_items_seen=counts.source_items_seen,
        records_accepted=counts.records_accepted,
        outside_envelope=counts.outside_envelope,
        coordinates_missing=counts.coordinates_missing,
        exact_duplicates_collapsed=counts.exact_duplicates_collapsed,
        parser_report_fingerprint=report.fingerprint(),
        snapshot_receipt_fingerprint=receipt.fingerprint(),
        synthetic=request.synthetic,
    )


def _query(request: NationalHighwaysAcquisitionRequest) -> dict[str, str]:
    if request.product == "vms":
        return {"bBox": request.envelope.query_value()}
    start = cast(datetime, request.window_start_utc)
    end = cast(datetime, request.window_end_utc)
    type_key = "closureType" if request.product == "closures" else "speedRestrictionType"
    return {
        type_key: cast(str, request.event_type),
        "startDateTime": _api_time(start),
        "endDateTime": _api_time(end),
    }


def _api_time(value: datetime) -> str:
    """Render the exact UTC-naive ISO form required by the observed REST contract."""

    return value.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def _verified_member(quarantine_dir: Path, manifest: ManchesterQuarantineManifest) -> bytes:
    target = quarantine_dir / RAW_DIRECTORY_NAME / NATIONAL_HIGHWAYS_MEMBER_PATH
    if target.is_symlink() or not target.is_file():
        raise NationalHighwaysAcquisitionError(
            "QUARANTINE_INVALID", "quarantined response member is missing or unsafe"
        )
    payload = target.read_bytes()
    member = manifest.members[0]
    if len(payload) != member.byte_size or sha256_hex(payload) != member.sha256:
        raise NationalHighwaysAcquisitionError(
            "QUARANTINE_INVALID", "quarantined response member failed hash verification"
        )
    return payload


def _decode_http_payload(
    payload: bytes,
    manifest: ManchesterQuarantineManifest | ManchesterSnapshotManifest,
) -> bytes:
    encoding = None if manifest.http is None else manifest.http.response_content_encoding
    if encoding is None:
        return payload
    if encoding != "gzip":
        raise NationalHighwaysAcquisitionError(
            "CONTENT_ENCODING_REJECTED",
            "National Highways admits identity or bounded gzip JSON only",
        )
    try:
        return decompress_gzip(payload, policy=_GZIP_POLICY)
    except ManchesterArchiveError as exc:
        raise NationalHighwaysAcquisitionError(
            "CONTENT_DECODING_FAILED",
            "the quarantined gzip response failed bounded decoding",
        ) from exc


def _bind_manifest(
    manifest: ManchesterSnapshotManifest,
    request: NationalHighwaysAcquisitionRequest,
) -> None:
    if (
        manifest.source.source_id != _SOURCE_IDS[request.product]
        or manifest.source.adapter_version != NATIONAL_HIGHWAYS_ACQUISITION_VERSION
        or manifest.source.source_schema_version != NATIONAL_HIGHWAYS_SCHEMA_VERSION
        or manifest.request.host != NATIONAL_HIGHWAYS_SOURCE_HOST
        or manifest.request.path != _PATHS[request.product]
        or manifest.request.redacted_parameter_names != (NATIONAL_HIGHWAYS_SECRET_HEADER,)
        or manifest.publication_class is not ManchesterPublicationClass.PRIVATE
        or manifest.licence_id != NATIONAL_HIGHWAYS_LICENCE_ID
        or manifest.attribution_text != NATIONAL_HIGHWAYS_ATTRIBUTION
        or manifest.synthetic != request.synthetic
        or manifest.request.parameters != tuple(sorted(_query(request).items()))
    ):
        raise NationalHighwaysAcquisitionError(
            "REPLAY_CONTRACT_MISMATCH", "accepted snapshot does not match the replay request"
        )


def _response_media_type(response: object) -> str:
    from traffictwin.integration.manchester.transport import BoundedHttpResponse

    bounded = cast(BoundedHttpResponse, response)
    headers = dict(bounded.metadata.response_headers)
    value = headers.get("content-type", "application/json")
    return value.split(";", 1)[0].strip().lower()


def _source_name(product: NationalHighwaysProduct) -> str:
    return {
        "closures": "National Highways Road and Lane Closures v2",
        "speed_limits": "National Highways Speed Managed Areas v1",
        "vms": "National Highways Digital VMS v1",
    }[product]


def _workspace(value: str | Path) -> Path:
    workspace = Path(value)
    try:
        inspect_v07_workspace(workspace)
    except V07WorkspaceError as exc:
        raise NationalHighwaysAcquisitionError(
            "WORKSPACE_INVALID", "an isolated TrafficTwin v0.7 workspace is required"
        ) from exc
    return workspace.resolve(strict=True)

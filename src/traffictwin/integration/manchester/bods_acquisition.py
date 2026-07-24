"""Controlled BODS SIRI-VM acquisition: authenticated fetch → quarantine → parse → promote.

This module wires the single audited BODS bus-location endpoint through the
existing MAN-01 boundaries in a fixed order: the shared
:class:`BoundedHttpClient` fetches one bounded SIRI-VM response with the API
key confined to the transport's secret-query channel, the exact response bytes
are preserved in MAN-01 quarantine, the quarantined bytes are re-read and
re-hashed, the existing MAN-05 parser validates them through the hardened XML
boundary, and only an explicitly admitted result promotes to accepted storage.

Credential handling is structural: the API key is a transient function
argument, never a model field; it is sent only through the transport's secret
query channel, whose persisted metadata records the parameter *name* under
``redacted_parameter_names`` and never the value; no error message, receipt,
manifest, or log line can carry it.

Privacy and claim limits are inherited unchanged from the MAN-05 parser:
records are bus/transit vehicle positions only (never road counts,
private-vehicle flow, congestion, or a complete-fleet claim); raw
``VehicleRef`` values are replaced by snapshot-scoped tokens before any output
exists; ``retention_policy`` stays ``unapproved``; public export remains
unavailable, and membership is deliberately left to the separate versioned
identifier projection. No BN* operator code is activated or hard-coded here.

``MAN-01`` and ``MAN-05`` remain ``planned``; this is candidate Gate-B library
evidence only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Literal

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import (
    ManchesterHttpSnapshotParts,
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.archive import (
    ArchivePolicy,
    ManchesterArchiveError,
    decompress_gzip,
)
from traffictwin.integration.manchester.bods import (
    MAX_SIRI_BYTES,
    BodsAdapterError,
    BodsBoundingBox,
    BodsMemberRef,
    BodsParseReport,
    BodsParseScope,
    parse_bods_siri_vm,
)
from traffictwin.integration.manchester.models import (
    QUARANTINE_MANIFEST_FILE_NAME,
    RAW_DIRECTORY_NAME,
    ManchesterFindingSeverity,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterQuarantineReceipt,
    ManchesterRawMember,
    ManchesterRequestIdentity,
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
    QUARANTINE_DIRECTORY_NAME,
    quarantine_validate_and_promote,
    verify_manchester_quarantine,
)
from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    BoundedHttpResponse,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)

BODS_ACQUISITION_SCHEMA_VERSION = "1.0"
BODS_ACQUISITION_METHOD_VERSION = "manchester-bods-acquisition-1.0"
BODS_SOURCE_ID = "bods_siri_vm"
BODS_SOURCE_HOST = "data.bus-data.dft.gov.uk"
BODS_DATAFEED_PATH = "/api/v1/datafeed/"
BODS_FEED_MEMBER_PATH = "feed/siri-vm.xml"
BODS_LICENCE_ID = "OGL-v3.0"
BODS_FRESHNESS_POLICY_VERSION = "manchester-freshness-v1"
BODS_ATTRIBUTION_TEXT = (
    "Contains public sector information licensed under the Open Government Licence "
    "v3.0, retrieved from the DfT Bus Open Data Service (BODS)."
)

MAX_QUARANTINE_MANIFEST_BYTES = 8_000_000
MAX_ADMITTED_WARNING_CODES = 8
MAX_API_KEY_CHARACTERS = 4_096
_WARNING_CODE_PATTERN = re.compile(r"^[A-Z0-9_]{1,96}$")
_FILTER_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9:._-]{1,64}$")

BODS_ENDPOINT_POLICY = EndpointPolicy(
    endpoint_id="bods-bus-location",
    host=BODS_SOURCE_HOST,
    path_prefixes=(BODS_DATAFEED_PATH,),
    query_parameter_names=("boundingBox", "lineRef", "operatorRef", "producerRef"),
    secret_query_parameter_names=("api_key",),
)

# Conservative self-imposed transport limits: the audit found no general BODS
# consumer rate-limit policy (GA-BODS-3) and the consumer cache refreshes
# every ten seconds, so one bounded poll per acquisition is the only shape.
_CONNECT_TIMEOUT_S = 10.0
_READ_TIMEOUT_S = 30.0
_WRITE_TIMEOUT_S = 10.0
_POOL_TIMEOUT_S = 10.0
_TOTAL_DEADLINE_S = 120.0
_MAX_REDIRECTS = 1
_MAX_ATTEMPTS = 2
_BACKOFF_BASE_S = 0.2
_BACKOFF_MAX_S = 1.0
_ALLOWED_MEDIA_TYPES = ("application/xml", "text/xml")
_AUTHENTICATED_FETCH_LOCK = RLock()
_BODS_GZIP_POLICY = ArchivePolicy(
    max_compressed_bytes=MAX_SIRI_BYTES,
    max_decompressed_bytes=MAX_SIRI_BYTES,
    max_member_bytes=MAX_SIRI_BYTES,
    max_members=1,
    max_compression_ratio=200.0,
)


class BodsAcquisitionError(RuntimeError):
    """Typed deterministic acquisition/replay failure; never carries credentials.

    ``quarantine_snapshot_id`` is set when the complete response is preserved
    in quarantine (rejected parse, refused warnings, replay mismatch); it is
    ``None`` when the acquisition never became complete.
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


class BodsAcquisitionRequest(ManchesterSnapshotModel):
    """Strict typed request; endpoint and publication class are fixed.

    There is deliberately no API-key, host, URL, path, free-query, parser,
    timeout, byte-limit, or publication-class field. The key is a transient
    call argument only, and the raw response is always ``private``.
    """

    bounding_box: BodsBoundingBox
    operator_ref: str | None = Field(default=None)
    line_ref: str | None = Field(default=None)
    producer_ref: str | None = Field(default=None)
    policy: ManchesterSnapshotPolicy
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    admitted_warning_codes: tuple[str, ...] = ()
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> BodsAcquisitionRequest:
        for label, value in (
            ("operator_ref", self.operator_ref),
            ("line_ref", self.line_ref),
            ("producer_ref", self.producer_ref),
        ):
            if value is not None and _FILTER_VALUE_PATTERN.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded documented identifier")
        if len(self.admitted_warning_codes) > MAX_ADMITTED_WARNING_CODES:
            raise ValueError("admitted warning codes are bounded")
        if list(self.admitted_warning_codes) != sorted(set(self.admitted_warning_codes)):
            raise ValueError("admitted warning codes must be sorted and unique")
        if any(
            _WARNING_CODE_PATTERN.fullmatch(code) is None for code in self.admitted_warning_codes
        ):
            raise ValueError("admitted warning codes must be canonical finding codes")
        return self


class BodsReplayRequest(ManchesterSnapshotModel):
    """Offline replay claim; bound against the quarantine manifest before parsing."""

    bounding_box: BodsBoundingBox
    operator_ref: str | None = None
    line_ref: str | None = None
    producer_ref: str | None = None
    expected_synthetic: bool | None = None

    @model_validator(mode="after")
    def validate_request(self) -> BodsReplayRequest:
        for label, value in (
            ("operator_ref", self.operator_ref),
            ("line_ref", self.line_ref),
            ("producer_ref", self.producer_ref),
        ):
            if value is not None and _FILTER_VALUE_PATTERN.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded documented identifier")
        return self


class _BodsReceiptBase(ManchesterSnapshotModel):
    """Shared receipt provenance with exact internal reconciliation.

    ``parser_report_fingerprint`` is an externally fingerprinted reference to
    the full MAN-05 parse report; offline replay recomputes it from
    quarantined bytes. Every other claim below is re-derived on validation.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-05"] = "MAN-05"
    method_version: Literal["manchester-bods-acquisition-1.0"] = "manchester-bods-acquisition-1.0"
    source_id: Literal["bods_siri_vm"] = "bods_siri_vm"
    endpoint_host: Literal["data.bus-data.dft.gov.uk"] = "data.bus-data.dft.gov.uk"
    endpoint_path: Literal["/api/v1/datafeed/"] = "/api/v1/datafeed/"
    licence_id: Literal["OGL-v3.0"] = "OGL-v3.0"
    attribution_text: Literal[
        "Contains public sector information licensed under the Open Government Licence "
        "v3.0, retrieved from the DfT Bus Open Data Service (BODS)."
    ] = (
        "Contains public sector information licensed under the Open Government Licence "
        "v3.0, retrieved from the DfT Bus Open Data Service (BODS)."
    )
    publication_class: Literal["private"] = "private"
    retention_policy: Literal["unapproved"] = "unapproved"
    public_export_available: Literal[False] = False
    bee_network_membership_available: Literal[False] = False
    transit_vehicle_only: Literal[True] = True
    road_traffic_volume_available: Literal[False] = False
    raw_vehicle_identifiers_in_receipt: Literal[False] = False
    snapshot_id: str = Field(pattern=r"^bods_siri_vm-\d{8}T\d{6}Z-[0-9a-f]{12}$")
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1, max_length=1)
    feed_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_identity: ManchesterRequestIdentity
    evaluated_at_utc: datetime
    activities_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    malformed: int = Field(ge=0)
    outside_bounds: int = Field(ge=0)
    duplicate_collapsed: int = Field(ge=0)
    conflicting_duplicates: int = Field(ge=0)
    live_vehicle: int = Field(ge=0)
    stale: int = Field(ge=0)
    historical: int = Field(ge=0)
    synthetic_records: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_warning_codes: tuple[str, ...] = ()
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    quarantine_receipt: ManchesterQuarantineReceipt
    quarantine_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    quarantine_manifest: ManchesterQuarantineManifest
    synthetic: bool

    @model_validator(mode="after")
    def validate_receipt(self) -> _BodsReceiptBase:
        member = self.members[0]
        if member.relative_path != BODS_FEED_MEMBER_PATH:
            raise ValueError("the quarantine inventory must be the single SIRI-VM member")
        if member.sha256 != self.feed_sha256:
            raise ValueError("feed_sha256 must bind the quarantined SIRI-VM member")
        if self.raw_fingerprint != build_raw_fingerprint(self.members):
            raise ValueError("raw fingerprint must bind the member inventory")
        if not self.snapshot_id.endswith(self.raw_fingerprint[:12]):
            raise ValueError("snapshot_id must end with the raw-fingerprint prefix")
        if self.parser_status is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected parse can never produce an admitted receipt")
        if self.malformed != 0 or self.conflicting_duplicates != 0:
            raise ValueError("an admitted SIRI-VM parse cannot contain error activities")
        expected_records = self.activities_seen - self.outside_bounds - self.duplicate_collapsed
        if self.records_accepted != expected_records:
            raise ValueError("an admitted SIRI-VM parse must reconcile every activity")
        freshness_total = self.live_vehicle + self.stale + self.historical + self.synthetic_records
        if freshness_total != self.records_accepted:
            raise ValueError("freshness counts must partition the accepted records")
        if self.synthetic:
            if self.synthetic_records != self.records_accepted:
                raise ValueError("synthetic evidence must yield synthetic freshness only")
        elif self.synthetic_records != 0:
            raise ValueError("real evidence can never carry synthetic freshness")
        codes = list(self.parser_warning_codes)
        if codes != sorted(set(codes)):
            raise ValueError("parser warning codes must be sorted and unique")
        if any(_WARNING_CODE_PATTERN.fullmatch(code) is None for code in codes):
            raise ValueError("parser warning codes must be canonical finding codes")
        if self.parser_status is ManchesterValidationState.ACCEPTED and codes:
            raise ValueError("an accepted parse cannot carry warning codes")
        if self.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and not codes:
            raise ValueError("a warning-accepted parse must record its warning codes")
        identity = self.request_identity
        if identity.host != BODS_SOURCE_HOST or identity.path != BODS_DATAFEED_PATH:
            raise ValueError("the persisted request identity must be the audited endpoint")
        if identity.redacted_parameter_names != ("api_key",):
            raise ValueError("the persisted request identity must redact exactly the api_key name")
        visible_names = {name for name, _value in identity.parameters}
        if not visible_names <= {"boundingBox", "lineRef", "operatorRef", "producerRef"}:
            raise ValueError("the persisted request identity carries an unaudited parameter")
        if "boundingBox" not in visible_names:
            raise ValueError("the persisted request identity must carry the bounding box")
        if self.quarantine_receipt.snapshot_id != self.snapshot_id:
            raise ValueError("the embedded quarantine receipt must bind this snapshot")
        if self.quarantine_receipt.raw_fingerprint != self.raw_fingerprint:
            raise ValueError("the embedded quarantine receipt must bind the raw fingerprint")
        if self.quarantine_receipt.verified_member_count != 1:
            raise ValueError("the quarantine receipt must verify exactly one member")
        if self.quarantine_receipt.verified_total_bytes != member.byte_size:
            raise ValueError("the quarantine receipt byte total must bind the feed member")
        if self.quarantine_receipt_fingerprint != self.quarantine_receipt.fingerprint():
            raise ValueError("quarantine_receipt_fingerprint must match the embedded receipt")
        manifest = self.quarantine_manifest
        manifest_bytes = manifest.canonical_json().encode("utf-8")
        if self.quarantine_receipt.manifest_fingerprint != manifest.fingerprint():
            raise ValueError("the quarantine receipt must bind the embedded manifest")
        if self.quarantine_receipt.manifest_file_sha256 != sha256_hex(manifest_bytes):
            raise ValueError("the quarantine receipt must bind the embedded manifest bytes")
        if (
            manifest.snapshot_id != self.snapshot_id
            or manifest.raw_fingerprint != self.raw_fingerprint
            or manifest.members != self.members
            or manifest.request != self.request_identity
            or manifest.synthetic != self.synthetic
        ):
            raise ValueError("the embedded quarantine manifest must bind this receipt")
        if manifest.retrieval.completed_at_utc != self.evaluated_at_utc:
            raise ValueError("evaluation time must equal the bound retrieval completion time")
        if (
            manifest.source.source_id != BODS_SOURCE_ID
            or manifest.source.adapter_version != BODS_ACQUISITION_METHOD_VERSION
            or manifest.source.source_schema_version != BODS_ACQUISITION_SCHEMA_VERSION
            or manifest.source.freshness_policy_version != BODS_FRESHNESS_POLICY_VERSION
        ):
            raise ValueError("the embedded manifest must carry the exact BODS source contract")
        if (
            manifest.licence_id != BODS_LICENCE_ID
            or manifest.attribution_text != BODS_ATTRIBUTION_TEXT
            or manifest.publication_class is not ManchesterPublicationClass.PRIVATE
        ):
            raise ValueError("the embedded manifest must carry the exact publication contract")
        return self


class BodsAcquisitionResult(_BodsReceiptBase):
    """Receipt for one promoted BODS acquisition, with embedded typed sub-receipts."""

    request: BodsAcquisitionRequest
    snapshot_receipt: ManchesterSnapshotReceipt
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    promoted: Literal[True] = True

    @model_validator(mode="after")
    def validate_acquisition(self) -> BodsAcquisitionResult:
        if self.synthetic != self.request.synthetic:
            raise ValueError("result evidence class must match the acquisition request")
        if not self.synthetic and self.historical != 0:
            raise ValueError("a live acquisition cannot label records historical")
        unadmitted = set(self.parser_warning_codes) - set(self.request.admitted_warning_codes)
        if unadmitted:
            raise ValueError("every observed warning code must be admitted by the embedded request")
        expected = dict(_visible_parameters(self.request))
        observed = {name: str(value) for name, value in self.request_identity.parameters}
        if observed != expected:
            raise ValueError("the persisted request identity must match the embedded typed request")
        if self.snapshot_receipt.snapshot_id != self.snapshot_id:
            raise ValueError("the embedded snapshot receipt must bind this snapshot")
        if self.snapshot_receipt.raw_fingerprint != self.raw_fingerprint:
            raise ValueError("the embedded snapshot receipt must bind the raw fingerprint")
        if self.snapshot_receipt_fingerprint != self.snapshot_receipt.fingerprint():
            raise ValueError("snapshot_receipt_fingerprint must match the embedded receipt")
        if (
            self.quarantine_receipt.policy != self.request.policy
            or self.snapshot_receipt.policy != self.request.policy
        ):
            raise ValueError("embedded receipts must carry the requested snapshot policy")
        return self


class BodsReplayResult(_BodsReceiptBase):
    """Offline replay receipt bound to the verified quarantine; no promotion."""

    request: BodsReplayRequest
    replayed_offline: Literal[True] = True

    @model_validator(mode="after")
    def validate_replay(self) -> BodsReplayResult:
        if not self.synthetic and (self.live_vehicle != 0 or self.stale != 0):
            raise ValueError("offline replay can never relabel records live or stale")
        expected = dict(_visible_parameters(self.request))
        observed = {name: str(value) for name, value in self.request_identity.parameters}
        if observed != expected:
            raise ValueError("the persisted request identity must match the replay request")
        if (
            self.request.expected_synthetic is not None
            and self.request.expected_synthetic != self.synthetic
        ):
            raise ValueError("the replay evidence class must match the replay request")
        return self


def acquire_bods_snapshot(
    workspace_root: str | Path,
    request: BodsAcquisitionRequest,
    *,
    api_key: str,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> BodsAcquisitionResult:
    """Acquire one bounded SIRI-VM response through quarantine into accepted storage.

    The API key is transient: it exists only as this argument and inside the
    transport's secret-query channel for the single request. It is never
    stored, logged, fingerprinted, or echoed into any error.
    """

    if (
        not api_key
        or api_key.strip() != api_key
        or len(api_key) > MAX_API_KEY_CHARACTERS
        or any(character in api_key for character in "\r\n")
    ):
        raise BodsAcquisitionError(
            "API_KEY_INVALID", "the supplied credential is unusable (value withheld)"
        )
    if not request.synthetic and (http_client is not None or utc_now is not None):
        raise BodsAcquisitionError(
            "UNTRUSTED_REAL_SOURCE_BOUNDARY",
            "real-source acquisition requires the module-owned HTTPS transport and UTC clock",
        )
    transport_policy = TransportPolicy(
        connect_timeout_s=_CONNECT_TIMEOUT_S,
        read_timeout_s=_READ_TIMEOUT_S,
        write_timeout_s=_WRITE_TIMEOUT_S,
        pool_timeout_s=_POOL_TIMEOUT_S,
        total_deadline_s=_TOTAL_DEADLINE_S,
        max_response_bytes=min(request.policy.max_member_bytes, MAX_SIRI_BYTES),
        max_redirects=_MAX_REDIRECTS,
        max_attempts=_MAX_ATTEMPTS,
        backoff_base_s=_BACKOFF_BASE_S,
        backoff_max_s=_BACKOFF_MAX_S,
        allowed_media_types=_ALLOWED_MEDIA_TYPES,
    )
    with BoundedHttpClient(
        endpoint=BODS_ENDPOINT_POLICY,
        policy=transport_policy,
        client=http_client,
        utc_now=utc_now,
    ) as client:
        try:
            with _suppressed_url_logging():
                response = client.fetch(
                    BODS_DATAFEED_PATH,
                    query=dict(_visible_parameters(request)),
                    secret_query={"api_key": api_key},
                )
        except ManchesterTransportError as exc:
            raise BodsAcquisitionError(
                "TRANSPORT_FAILURE",
                f"bounded transport failed ({exc.code}); BODS unavailability is a typed "
                "failure and never becomes zero buses or stale-as-live evidence",
            ) from exc
    parts = _snapshot_parts(response)
    if len(parts.payload) > request.policy.max_total_bytes:
        raise BodsAcquisitionError(
            "TOTAL_BYTES_EXCEEDED", "response bytes exceed the snapshot policy bound"
        )

    inventory = (parts.member,)
    raw_fingerprint = build_raw_fingerprint(inventory)
    source = ManchesterSourceIdentity(
        source_id=BODS_SOURCE_ID,
        source_name="DfT Bus Open Data Service SIRI-VM bus locations",
        adapter_version=BODS_ACQUISITION_METHOD_VERSION,
        source_schema_version=BODS_ACQUISITION_SCHEMA_VERSION,
        freshness_policy_version=BODS_FRESHNESS_POLICY_VERSION,
    )
    quarantine_manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(
            BODS_SOURCE_ID, parts.retrieval.started_at_utc, raw_fingerprint
        ),
        source=source,
        request=parts.request,
        retrieval=parts.retrieval,
        http=parts.http,
        members=inventory,
        member_count=1,
        total_bytes=parts.member.byte_size,
        raw_fingerprint=raw_fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=BODS_LICENCE_ID,
        attribution_text=BODS_ATTRIBUTION_TEXT,
        access_date=parts.retrieval.started_at_utc.date(),
        synthetic=request.synthetic,
    )

    captured_reports: list[BodsParseReport] = []

    def validator(
        quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        report = _parse_quarantined_feed(
            quarantine_dir,
            manifest,
            request.bounding_box,
            mode="live",
        )
        captured_reports.append(report)
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
                        if finding.activity_index is None
                        else f"{finding.message} (activity {finding.activity_index})"
                    ),
                    artifact=BODS_FEED_MEMBER_PATH,
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
        {BODS_FEED_MEMBER_PATH: parts.payload},
        request.policy,
        validator,
    )
    quarantine_receipt = verify_manchester_quarantine(
        Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / quarantine_manifest.snapshot_id
    )
    report = captured_reports[0]
    return BodsAcquisitionResult(
        request=request,
        snapshot_id=quarantine_manifest.snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=inventory,
        feed_sha256=parts.member.sha256,
        request_identity=quarantine_manifest.request,
        evaluated_at_utc=quarantine_manifest.retrieval.completed_at_utc,
        activities_seen=report.counts.activities_seen,
        records_accepted=report.counts.records_accepted,
        malformed=report.counts.malformed,
        outside_bounds=report.counts.outside_bounds,
        duplicate_collapsed=report.counts.duplicate_collapsed,
        conflicting_duplicates=report.counts.conflicting_duplicates,
        live_vehicle=report.counts.live_vehicle,
        stale=report.counts.stale,
        historical=report.counts.historical,
        synthetic_records=report.counts.synthetic,
        parser_status=report.status,
        parser_warning_codes=_warning_codes(report),
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        quarantine_manifest=quarantine_manifest,
        snapshot_receipt=snapshot_receipt,
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
        synthetic=request.synthetic,
    )


def replay_bods_quarantine(
    workspace_root: str | Path,
    snapshot_id: str,
    request: BodsReplayRequest,
) -> BodsReplayResult:
    """Re-validate quarantined SIRI-VM bytes offline; no network, no promotion.

    The manifest's source contract, audited endpoint, visible parameters,
    ``api_key``-only redaction contract, publication class, and single-member
    inventory are bound before any byte is parsed, so quarantined bytes can
    never be relabelled to another source, scope, or publication class.
    """

    quarantine_dir = Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    quarantine_receipt = verify_manchester_quarantine(quarantine_dir)
    manifest = _load_quarantine_manifest(quarantine_dir)
    if manifest.snapshot_id != snapshot_id:
        raise BodsAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest does not match the requested id"
        )
    _bind_replay_claim(manifest, request)
    if request.expected_synthetic is not None and manifest.synthetic != request.expected_synthetic:
        raise BodsAcquisitionError(
            "SYNTHETIC_MISMATCH",
            "quarantined evidence class does not match the caller's declaration",
            quarantine_snapshot_id=snapshot_id,
        )
    report = _parse_quarantined_feed(
        quarantine_dir,
        manifest,
        request.bounding_box,
        mode="offline_replay",
    )
    if report.status is ManchesterValidationState.REJECTED:
        raise BodsAcquisitionError(
            "PARSE_REJECTED",
            "the MAN-05 parser rejected the quarantined SIRI-VM feed during replay",
            quarantine_snapshot_id=snapshot_id,
        )
    return BodsReplayResult(
        request=request,
        snapshot_id=snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        members=manifest.members,
        feed_sha256=manifest.members[0].sha256,
        request_identity=manifest.request,
        evaluated_at_utc=manifest.retrieval.completed_at_utc,
        activities_seen=report.counts.activities_seen,
        records_accepted=report.counts.records_accepted,
        malformed=report.counts.malformed,
        outside_bounds=report.counts.outside_bounds,
        duplicate_collapsed=report.counts.duplicate_collapsed,
        conflicting_duplicates=report.counts.conflicting_duplicates,
        live_vehicle=report.counts.live_vehicle,
        stale=report.counts.stale,
        historical=report.counts.historical,
        synthetic_records=report.counts.synthetic,
        parser_status=report.status,
        parser_warning_codes=_warning_codes(report),
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        quarantine_manifest=manifest,
        synthetic=manifest.synthetic,
    )


@contextmanager
def _suppressed_url_logging() -> Iterator[None]:
    """Silence HTTP-library URL logging for the single authenticated request.

    BODS transmits the API key as a query parameter, and httpx/httpcore log
    full request URLs at INFO level when application logging is configured.
    ADR-054 forbids logging credential-bearing URLs, so both loggers are
    raised above INFO for exactly the duration of the fetch and then restored.
    """

    with _AUTHENTICATED_FETCH_LOCK:
        loggers = [logging.getLogger("httpx"), logging.getLogger("httpcore")]
        previous_levels = [item.level for item in loggers]
        for item in loggers:
            item.setLevel(max(item.level, logging.WARNING))
        try:
            yield
        finally:
            for item, level in zip(loggers, previous_levels, strict=True):
                item.setLevel(level)


def _visible_parameters(
    request: BodsAcquisitionRequest | BodsReplayRequest,
) -> tuple[tuple[str, str], ...]:
    box = request.bounding_box
    parameters: dict[str, str] = {
        "boundingBox": (
            f"{box.min_longitude},{box.min_latitude},{box.max_longitude},{box.max_latitude}"
        )
    }
    if request.line_ref is not None:
        parameters["lineRef"] = request.line_ref
    if request.operator_ref is not None:
        parameters["operatorRef"] = request.operator_ref
    if request.producer_ref is not None:
        parameters["producerRef"] = request.producer_ref
    return tuple(sorted(parameters.items()))


def _snapshot_parts(response: BoundedHttpResponse) -> ManchesterHttpSnapshotParts:
    headers = dict(response.metadata.response_headers)
    content_type = headers.get("content-type", _ALLOWED_MEDIA_TYPES[0])
    media_type = content_type.split(";", 1)[0].strip().lower()
    return snapshot_parts_from_http_response(
        response,
        relative_path=BODS_FEED_MEMBER_PATH,
        media_type=media_type,
    )


def _warning_codes(report: BodsParseReport) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                finding.code
                for finding in report.findings
                if finding.severity is ManchesterFindingSeverity.WARNING
            }
        )
    )


def _admit_or_raise(
    report: BodsParseReport,
    admitted_warning_codes: tuple[str, ...],
    snapshot_id: str,
) -> None:
    if report.status is ManchesterValidationState.REJECTED:
        raise BodsAcquisitionError(
            "PARSE_REJECTED",
            "the MAN-05 parser rejected the quarantined SIRI-VM feed",
            quarantine_snapshot_id=snapshot_id,
        )
    if report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS:
        observed = sorted({finding.code for finding in report.findings})
        unapproved = [code for code in observed if code not in admitted_warning_codes]
        if unapproved:
            raise BodsAcquisitionError(
                "WARNINGS_REFUSED",
                f"{len(unapproved)} warning code(s) are not in the admitted set: "
                + ", ".join(unapproved),
                quarantine_snapshot_id=snapshot_id,
            )


def _load_quarantine_manifest(quarantine_dir: Path) -> ManchesterQuarantineManifest:
    manifest_path = quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise BodsAcquisitionError("QUARANTINE_INVALID", "quarantine manifest is missing or unsafe")
    if manifest_path.stat().st_size > MAX_QUARANTINE_MANIFEST_BYTES:
        raise BodsAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest exceeds its byte bound"
        )
    return ManchesterQuarantineManifest.model_validate_json(manifest_path.read_bytes())


def _bind_replay_claim(manifest: ManchesterQuarantineManifest, request: BodsReplayRequest) -> None:
    snapshot_id = manifest.snapshot_id
    if manifest.source.source_id != BODS_SOURCE_ID:
        raise BodsAcquisitionError(
            "PRODUCT_MISMATCH",
            "quarantined source id is not the BODS SIRI-VM source",
            quarantine_snapshot_id=snapshot_id,
        )
    if (
        manifest.source.adapter_version != BODS_ACQUISITION_METHOD_VERSION
        or manifest.source.source_schema_version != BODS_ACQUISITION_SCHEMA_VERSION
        or manifest.source.freshness_policy_version != BODS_FRESHNESS_POLICY_VERSION
        or manifest.licence_id != BODS_LICENCE_ID
        or manifest.attribution_text != BODS_ATTRIBUTION_TEXT
        or manifest.publication_class is not ManchesterPublicationClass.PRIVATE
        or manifest.request.host != BODS_SOURCE_HOST
        or manifest.request.path != BODS_DATAFEED_PATH
    ):
        raise BodsAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined source contract does not match this adapter version",
            quarantine_snapshot_id=snapshot_id,
        )
    if manifest.request.redacted_parameter_names != ("api_key",):
        raise BodsAcquisitionError(
            "REDACTION_CONTRACT_MISMATCH",
            "the quarantined request identity must redact exactly the api_key name",
            quarantine_snapshot_id=snapshot_id,
        )
    expected = dict(_visible_parameters(request))
    observed = {name: str(value) for name, value in manifest.request.parameters}
    if observed != expected:
        raise BodsAcquisitionError(
            "SCOPE_MISMATCH",
            "quarantined request parameters do not match the claimed scope",
            quarantine_snapshot_id=snapshot_id,
        )
    if [member.relative_path for member in manifest.members] != [BODS_FEED_MEMBER_PATH]:
        raise BodsAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined member inventory is not the single SIRI-VM feed member",
            quarantine_snapshot_id=snapshot_id,
        )


def _parse_quarantined_feed(
    quarantine_dir: Path,
    manifest: ManchesterQuarantineManifest,
    bounding_box: BodsBoundingBox,
    *,
    mode: Literal["live", "offline_replay"],
) -> BodsParseReport:
    member = manifest.members[0]
    target = quarantine_dir / RAW_DIRECTORY_NAME / member.relative_path
    if target.is_symlink() or not target.is_file():
        raise BodsAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined SIRI-VM member is missing or unsafe",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if target.stat().st_size != member.byte_size:
        raise BodsAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined SIRI-VM member size drifted",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    payload = target.read_bytes()
    if sha256_hex(payload) != member.sha256:
        raise BodsAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined SIRI-VM member hash drifted",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if manifest.http is None:
        raise BodsAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "the BODS snapshot requires bounded HTTP metadata",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    content_encoding = manifest.http.response_content_encoding
    parser_payload = decode_bods_http_payload(
        payload,
        content_encoding=content_encoding,
    )
    ref = BodsMemberRef(
        snapshot_id=manifest.snapshot_id,
        member_path=member.relative_path,
        member_sha256=member.sha256,
        content_encoding="gzip" if content_encoding == "gzip" else "identity",
        parser_payload_sha256=(sha256_hex(parser_payload) if content_encoding == "gzip" else None),
        synthetic=manifest.synthetic,
    )
    scope = BodsParseScope(
        evaluated_at_utc=manifest.retrieval.completed_at_utc,
        mode=mode,
        bounding_box=bounding_box,
    )
    try:
        return parse_bods_siri_vm((ref, parser_payload), scope)
    except BodsAdapterError as exc:
        raise BodsAcquisitionError(
            "PARSE_INTEGRITY",
            f"the MAN-05 parser refused the quarantined member ({exc.code})",
            quarantine_snapshot_id=manifest.snapshot_id,
        ) from exc


def decode_bods_http_payload(
    payload: bytes,
    *,
    content_encoding: Literal["gzip", "deflate"] | None,
) -> bytes:
    """Decode verified HTTP content only after its raw bytes are quarantined.

    The bounded transport validates the encoded stream while retaining the
    exact wire bytes. BODS currently returns gzip content, so the adapter must
    preserve those bytes as raw evidence and separately produce bounded XML
    bytes for the parser. Deflate is not part of the audited BODS fixture and
    therefore fails closed rather than gaining an unaudited decoder here.
    """

    if content_encoding is None:
        return payload
    if content_encoding != "gzip":
        raise BodsAcquisitionError(
            "CONTENT_ENCODING_REJECTED",
            "the BODS adapter admits identity or bounded gzip content only",
        )
    try:
        return decompress_gzip(payload, policy=_BODS_GZIP_POLICY)
    except ManchesterArchiveError as exc:
        raise BodsAcquisitionError(
            "CONTENT_DECODING_FAILED",
            "the quarantined BODS gzip response failed bounded decoding",
        ) from exc

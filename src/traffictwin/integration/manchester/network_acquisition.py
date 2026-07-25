"""Operator-invoked bounded acquisition of the Greater Manchester OSM extract.

ADR-059 pins OpenStreetMap via Geofabrik, reference date 25 July 2026, licence
ODbL 1.0.  This module acquires that extract under the existing MAN-01
contracts: bounded allowlisted transport, quarantine before parse, immutable
hashing, receipts, and atomic promotion into accepted storage.

Boundaries enforced here:

*   **Operator-invoked only.**  Every entry point requires an explicit typed
    :class:`OperatorAuthorisation` whose ``confirmed_by_operator`` flag is
    ``True``.  Nothing in this module is reachable from a Streamlit rerun, and
    no default argument performs network access.
*   **No caller-supplied network identity.**  Host, path family, media types,
    and byte bounds are frozen.  There is no URL, host, path, mirror, or
    parser field on any request model.
*   **Raw inputs are preserved unchanged.**  The downloaded bytes are hashed
    before parsing, stored byte-for-byte, and never rewritten.  Accepted
    extracts are ``private`` workspace artifacts and are excluded from Git.
*   **Identity drift fails closed.**  The provider's published MD5 companion is
    verified against the downloaded bytes; a mismatch quarantines and refuses.

The module performs no network build, no matching, and no calibration.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import (
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.models import (
    RAW_DIRECTORY_NAME,
    ManchesterFindingSeverity,
    ManchesterHttpMetadata,
    ManchesterPriorRelation,
    ManchesterPriorSnapshotLink,
    ManchesterPublicationClass,
    ManchesterQuarantineManifest,
    ManchesterQuarantineReceipt,
    ManchesterRawMember,
    ManchesterRequestIdentity,
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

OSM_ACQUISITION_SCHEMA_VERSION: Literal["1.0"] = "1.0"
OSM_ACQUISITION_METHOD_VERSION: Literal["manchester-osm-extract-acquisition-1.0"] = (
    "manchester-osm-extract-acquisition-1.0"
)
OSM_SOURCE_ID: Literal["osm_greater_manchester"] = "osm_greater_manchester"
OSM_SOURCE_HOST: Literal["download.geofabrik.de"] = "download.geofabrik.de"
OSM_EXTRACT_PATH: Literal["/europe/united-kingdom/england/greater-manchester-latest.osm.pbf"] = (
    "/europe/united-kingdom/england/greater-manchester-latest.osm.pbf"
)
OSM_CHECKSUM_PATH: Literal[
    "/europe/united-kingdom/england/greater-manchester-latest.osm.pbf.md5"
] = "/europe/united-kingdom/england/greater-manchester-latest.osm.pbf.md5"

OSM_EXTRACT_MEMBER_PATH: Literal["osm/greater-manchester-latest.osm.pbf"] = (
    "osm/greater-manchester-latest.osm.pbf"
)
OSM_CHECKSUM_MEMBER_PATH: Literal["osm/greater-manchester-latest.osm.pbf.md5"] = (
    "osm/greater-manchester-latest.osm.pbf.md5"
)

OSM_LICENCE_ID: Literal["ODbL-1.0"] = "ODbL-1.0"
OSM_LICENCE_URI: Literal["https://opendatacommons.org/licenses/odbl/1-0/"] = (
    "https://opendatacommons.org/licenses/odbl/1-0/"
)
OSM_ATTRIBUTION: Literal["© OpenStreetMap contributors, ODbL 1.0"] = (
    "© OpenStreetMap contributors, ODbL 1.0"
)
OSM_FRESHNESS_POLICY_VERSION: Literal["osm-dated-extract-1.0"] = "osm-dated-extract-1.0"

#: The ADR-059 pinned reference date for the accepted extract.
OSM_REFERENCE_DATE: date = date(2026, 7, 25)

#: Hard ceiling for the extract read.  The Greater Manchester extract is on the
#: order of tens of megabytes; this bound is far above it and still finite.
OSM_MAX_EXTRACT_BYTES = 512_000_000
OSM_MAX_CHECKSUM_BYTES = 4_096
#: Refuse an implausibly small extract rather than build an empty network.
OSM_MIN_EXTRACT_BYTES = 1_000_000

# The reviewed TransportPolicy caps read_timeout_s at 300 s and
# total_deadline_s at 600 s; this adapter stays inside those existing bounds
# rather than widening a shared reviewed contract for a large download.
_CONNECT_TIMEOUT_S = 10.0
_READ_TIMEOUT_S = 300.0
_WRITE_TIMEOUT_S = 10.0
_POOL_TIMEOUT_S = 10.0
_TOTAL_DEADLINE_S = 600.0
_MAX_REDIRECTS = 0
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.5
_BACKOFF_MAX_S = 5.0

_EXTRACT_MEDIA_TYPES = ("application/octet-stream", "application/x-protobuf")
_CHECKSUM_MEDIA_TYPES = ("application/octet-stream", "text/plain")

#: PBF framing: a 4-byte big-endian BlobHeader length, then a protobuf whose
#: field 1 is the blob type.  The first blob of a valid file is ``OSMHeader``.
_PBF_HEADER_MARKER = b"\x0a\x09OSMHeader"
_PBF_MAX_HEADER_PREFIX = 64
_MD5_LINE = re.compile(rb"^([0-9a-fA-F]{32})\s+(\S+)\s*$")

OSM_ENDPOINT_POLICY = EndpointPolicy(
    endpoint_id="geofabrik-osm-extract",
    host=OSM_SOURCE_HOST,
    path_prefixes=("/europe/united-kingdom/england",),
)


class OsmAcquisitionError(RuntimeError):
    """Typed deterministic acquisition or replay failure.

    ``quarantine_snapshot_id`` is set when the complete download was preserved
    in quarantine before refusal; it is ``None`` when nothing durable was
    published.
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


class OperatorAuthorisation(ManchesterSnapshotModel):
    """Explicit operator consent for one bounded acquisition.

    Acquisition is never implicit.  A Streamlit rerun cannot construct this
    with ``confirmed_by_operator`` set, because the UI layer does not call
    acquisition at all; the CLI supplies it from an explicit flag.
    """

    confirmed_by_operator: Literal[True]
    invoked_via: Literal["cli", "test_harness"]
    reason: str = Field(min_length=1, max_length=200)


class OsmExtractAcquisitionRequest(ManchesterSnapshotModel):
    """Strict typed request; endpoint, bounds, and publication class are fixed.

    There is deliberately no host, URL, path, mirror, query, parser, or
    byte-limit field: none of those are caller decisions.
    """

    authorisation: OperatorAuthorisation
    policy: ManchesterSnapshotPolicy
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    expected_reference_date: date = OSM_REFERENCE_DATE
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> OsmExtractAcquisitionRequest:
        if self.policy.max_member_bytes > OSM_MAX_EXTRACT_BYTES:
            raise ValueError("snapshot policy exceeds the reviewed OSM extract bound")
        return self


class LocalOsmExtractImportRequest(ManchesterSnapshotModel):
    """Import an operator-supplied local extract without any network access.

    This is the offline path.  The bytes are still quarantined, hashed,
    validated, and promoted through the identical contract; only the transport
    differs.  ``expected_sha256`` lets an operator bind a known-good extract.
    """

    authorisation: OperatorAuthorisation
    policy: ManchesterSnapshotPolicy
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    expected_reference_date: date = OSM_REFERENCE_DATE
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    expected_md5: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> LocalOsmExtractImportRequest:
        if self.policy.max_member_bytes > OSM_MAX_EXTRACT_BYTES:
            raise ValueError("snapshot policy exceeds the reviewed OSM extract bound")
        return self


class OsmExtractIdentity(ManchesterSnapshotModel):
    """Immutable identity of one accepted OSM extract."""

    schema_version: Literal["1.0"] = "1.0"
    source_id: Literal["osm_greater_manchester"] = OSM_SOURCE_ID
    extract_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extract_md5: str = Field(pattern=r"^[0-9a-f]{32}$")
    extract_bytes: int = Field(ge=OSM_MIN_EXTRACT_BYTES)
    reference_date: date
    provider_checksum_verified: bool
    provider_checksum_source: Literal["provider_md5_companion", "operator_declared", "absent"]
    licence_id: Literal["ODbL-1.0"] = OSM_LICENCE_ID
    licence_uri: Literal["https://opendatacommons.org/licenses/odbl/1-0/"] = OSM_LICENCE_URI
    attribution_text: Literal["© OpenStreetMap contributors, ODbL 1.0"] = OSM_ATTRIBUTION
    publication_class: Literal["private"] = "private"
    synthetic: bool


class OsmExtractAcquisitionResult(ManchesterSnapshotModel):
    """Complete receipt for one accepted extract acquisition or import."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-osm-extract-acquisition-1.0"] = (
        OSM_ACQUISITION_METHOD_VERSION
    )
    acquisition_mode: Literal["bounded_http", "local_import", "offline_replay"]
    snapshot_id: str
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1)
    identity: OsmExtractIdentity
    quarantine_receipt: ManchesterQuarantineReceipt
    quarantine_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_receipt: ManchesterSnapshotReceipt
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_build_performed: Literal[False] = False
    calibration_performed: Literal[False] = False
    capability_status: Literal["planned"] = "planned"


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    value = (clock or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None:
        raise OsmAcquisitionError("CLOCK_NAIVE", "acquisition clock must be timezone aware")
    return value.astimezone(UTC)


def _md5_hex(payload: bytes) -> str:
    # MD5 is used only to verify the provider's published companion checksum.
    # Integrity of record is SHA-256; this is provider-identity reconciliation.
    return hashlib.md5(payload, usedforsecurity=False).hexdigest()


def check_pbf_framing(payload: bytes) -> None:
    """Reject a payload that is not a plausible OSM PBF, without parsing it."""

    if len(payload) < OSM_MIN_EXTRACT_BYTES:
        raise OsmAcquisitionError(
            "EXTRACT_TOO_SMALL",
            "the extract is implausibly small for Greater Manchester; "
            "an empty or truncated extract never becomes a network",
        )
    prefix = payload[:_PBF_MAX_HEADER_PREFIX]
    if _PBF_HEADER_MARKER not in prefix:
        raise OsmAcquisitionError(
            "EXTRACT_NOT_PBF",
            "the downloaded bytes do not begin with an OSM PBF header blob",
        )


def parse_provider_md5(payload: bytes) -> str:
    """Extract the single provider MD5 digest from its companion file."""

    if not payload or len(payload) > OSM_MAX_CHECKSUM_BYTES:
        raise OsmAcquisitionError(
            "CHECKSUM_FILE_REFUSED", "the provider checksum companion is empty or oversized"
        )
    lines = [line for line in payload.splitlines() if line.strip()]
    if len(lines) != 1:
        raise OsmAcquisitionError(
            "CHECKSUM_FILE_MALFORMED",
            "the provider checksum companion must contain exactly one digest line",
        )
    match = _MD5_LINE.match(lines[0])
    if match is None:
        raise OsmAcquisitionError(
            "CHECKSUM_FILE_MALFORMED", "the provider checksum line is not a digest/filename pair"
        )
    return match.group(1).decode("ascii").lower()


def _source_identity() -> ManchesterSourceIdentity:
    return ManchesterSourceIdentity(
        source_id=OSM_SOURCE_ID,
        source_name="OpenStreetMap Greater Manchester extract (Geofabrik)",
        adapter_version=OSM_ACQUISITION_METHOD_VERSION,
        source_schema_version=OSM_ACQUISITION_SCHEMA_VERSION,
        freshness_policy_version=OSM_FRESHNESS_POLICY_VERSION,
    )


def _transport_policy(max_bytes: int, media_types: tuple[str, ...]) -> TransportPolicy:
    return TransportPolicy(
        connect_timeout_s=_CONNECT_TIMEOUT_S,
        read_timeout_s=_READ_TIMEOUT_S,
        write_timeout_s=_WRITE_TIMEOUT_S,
        pool_timeout_s=_POOL_TIMEOUT_S,
        total_deadline_s=_TOTAL_DEADLINE_S,
        max_response_bytes=max_bytes,
        max_redirects=_MAX_REDIRECTS,
        max_attempts=_MAX_ATTEMPTS,
        backoff_base_s=_BACKOFF_BASE_S,
        backoff_max_s=_BACKOFF_MAX_S,
        allowed_media_types=media_types,
    )


def _fetch(
    path: str,
    *,
    max_bytes: int,
    media_types: tuple[str, ...],
    http_client: httpx.Client | None,
    utc_now: Callable[[], datetime] | None,
) -> BoundedHttpResponse:
    with BoundedHttpClient(
        endpoint=OSM_ENDPOINT_POLICY,
        policy=_transport_policy(max_bytes, media_types),
        client=http_client,
        utc_now=utc_now,
    ) as client:
        try:
            return client.fetch(path)
        except ManchesterTransportError as exc:
            raise OsmAcquisitionError(
                "TRANSPORT_FAILURE",
                f"bounded transport failed ({exc.code}); provider unavailability is a typed "
                "failure and never substitutes a cached or synthetic extract",
            ) from exc


def _identity(
    *,
    extract: bytes,
    md5_digest: str,
    checksum_source: Literal["provider_md5_companion", "operator_declared", "absent"],
    verified: bool,
    reference_date: date,
    synthetic: bool,
) -> OsmExtractIdentity:
    return OsmExtractIdentity(
        extract_sha256=sha256_hex(extract),
        extract_md5=md5_digest,
        extract_bytes=len(extract),
        reference_date=reference_date,
        provider_checksum_verified=verified,
        provider_checksum_source=checksum_source,
        synthetic=synthetic,
    )


def _promote(
    workspace_root: str | Path,
    *,
    members: dict[str, bytes],
    inventory: tuple[ManchesterRawMember, ...],
    request_identity: ManchesterRequestIdentity,
    retrieval: ManchesterRetrievalWindow,
    http_metadata: ManchesterHttpMetadata | None,
    policy: ManchesterSnapshotPolicy,
    prior: ManchesterPriorSnapshotLink,
    findings: tuple[ManchesterSnapshotFinding, ...],
    synthetic: bool,
    validate_payload: Callable[[dict[str, bytes]], None],
) -> tuple[str, ManchesterQuarantineReceipt, ManchesterSnapshotReceipt, str]:
    raw_fingerprint = build_raw_fingerprint(inventory)
    snapshot_id = build_snapshot_id(OSM_SOURCE_ID, retrieval.started_at_utc, raw_fingerprint)
    quarantine_manifest = ManchesterQuarantineManifest(
        snapshot_id=snapshot_id,
        source=_source_identity(),
        request=request_identity,
        retrieval=retrieval,
        http=http_metadata,
        members=inventory,
        member_count=len(inventory),
        total_bytes=sum(member.byte_size for member in inventory),
        raw_fingerprint=raw_fingerprint,
        publication_class=ManchesterPublicationClass.PRIVATE,
        licence_id=OSM_LICENCE_ID,
        attribution_text=OSM_ATTRIBUTION,
        access_date=retrieval.started_at_utc.date(),
        synthetic=synthetic,
    )

    def validator(
        _quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        validate_payload(members)
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
            findings=findings,
            prior=prior,
            publication_class=manifest.publication_class,
            licence_id=manifest.licence_id,
            attribution_text=manifest.attribution_text,
            access_date=manifest.access_date,
            synthetic=manifest.synthetic,
        )

    snapshot_receipt = quarantine_validate_and_promote(
        workspace_root, quarantine_manifest, members, policy, validator
    )
    quarantine_receipt = verify_manchester_quarantine(
        Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    )
    return snapshot_id, quarantine_receipt, snapshot_receipt, raw_fingerprint


def acquire_osm_extract_snapshot(
    workspace_root: str | Path,
    request: OsmExtractAcquisitionRequest,
    *,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> OsmExtractAcquisitionResult:
    """Acquire the pinned Geofabrik extract and its checksum through quarantine.

    Both the extract and the provider's published MD5 companion are fetched
    under the frozen endpoint policy.  The companion is verified against the
    downloaded bytes before promotion; drift fails closed.
    """

    if request.authorisation.confirmed_by_operator is not True:  # pragma: no cover - typed
        raise OsmAcquisitionError(
            "OPERATOR_AUTHORISATION_REQUIRED", "acquisition requires explicit operator confirmation"
        )
    extract_response = _fetch(
        OSM_EXTRACT_PATH,
        max_bytes=min(request.policy.max_member_bytes, OSM_MAX_EXTRACT_BYTES),
        media_types=_EXTRACT_MEDIA_TYPES,
        http_client=http_client,
        utc_now=utc_now,
    )
    checksum_response = _fetch(
        OSM_CHECKSUM_PATH,
        max_bytes=OSM_MAX_CHECKSUM_BYTES,
        media_types=_CHECKSUM_MEDIA_TYPES,
        http_client=http_client,
        utc_now=utc_now,
    )
    extract_parts = snapshot_parts_from_http_response(
        extract_response,
        relative_path=OSM_EXTRACT_MEMBER_PATH,
        media_type="application/octet-stream",
    )
    checksum_parts = snapshot_parts_from_http_response(
        checksum_response,
        relative_path=OSM_CHECKSUM_MEMBER_PATH,
        media_type="text/plain",
    )
    total = extract_parts.member.byte_size + checksum_parts.member.byte_size
    if total > request.policy.max_total_bytes:
        raise OsmAcquisitionError(
            "TOTAL_BYTES_EXCEEDED", "downloaded bytes exceed the snapshot policy bound"
        )
    published_md5 = parse_provider_md5(checksum_parts.payload)
    observed_md5 = _md5_hex(extract_parts.payload)

    def validate_payload(_members: dict[str, bytes]) -> None:
        check_pbf_framing(extract_parts.payload)
        if observed_md5 != published_md5:
            raise OsmAcquisitionError(
                "CHECKSUM_IDENTITY_DRIFT",
                "the downloaded extract does not match the provider's published MD5; "
                "the bytes stay quarantined and are never promoted",
            )

    members = {
        OSM_EXTRACT_MEMBER_PATH: extract_parts.payload,
        OSM_CHECKSUM_MEMBER_PATH: checksum_parts.payload,
    }
    inventory = (extract_parts.member, checksum_parts.member)
    snapshot_id, quarantine_receipt, snapshot_receipt, raw_fingerprint = _promote(
        workspace_root,
        members=members,
        inventory=inventory,
        request_identity=extract_parts.request,
        retrieval=extract_parts.retrieval,
        http_metadata=extract_parts.http,
        policy=request.policy,
        prior=request.prior,
        findings=(),
        synthetic=request.synthetic,
        validate_payload=validate_payload,
    )
    return OsmExtractAcquisitionResult(
        acquisition_mode="bounded_http",
        snapshot_id=snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=inventory,
        identity=_identity(
            extract=extract_parts.payload,
            md5_digest=observed_md5,
            checksum_source="provider_md5_companion",
            verified=True,
            reference_date=request.expected_reference_date,
            synthetic=request.synthetic,
        ),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        snapshot_receipt=snapshot_receipt,
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
    )


def import_local_osm_extract(
    workspace_root: str | Path,
    extract_path: str | Path,
    request: LocalOsmExtractImportRequest,
    *,
    utc_now: Callable[[], datetime] | None = None,
) -> OsmExtractAcquisitionResult:
    """Import an operator-supplied local extract with no network access at all.

    The offline path.  Bytes are read once, hashed, quarantined, validated, and
    promoted through the same contract as the network path.
    """

    if request.authorisation.confirmed_by_operator is not True:  # pragma: no cover - typed
        raise OsmAcquisitionError(
            "OPERATOR_AUTHORISATION_REQUIRED", "import requires explicit operator confirmation"
        )
    source = Path(extract_path)
    if source.is_symlink() or not source.is_file():
        raise OsmAcquisitionError(
            "EXTRACT_PATH_REFUSED", "the extract path must be an existing non-symlink regular file"
        )
    size = source.stat().st_size
    if size > min(request.policy.max_member_bytes, OSM_MAX_EXTRACT_BYTES):
        raise OsmAcquisitionError(
            "EXTRACT_TOO_LARGE", "the supplied extract exceeds the reviewed byte bound"
        )
    payload = source.read_bytes()
    observed_sha = sha256_hex(payload)
    observed_md5 = _md5_hex(payload)
    if request.expected_sha256 is not None and observed_sha != request.expected_sha256:
        raise OsmAcquisitionError(
            "EXTRACT_IDENTITY_DRIFT",
            "the supplied extract does not match the operator-declared SHA-256",
        )
    if request.expected_md5 is not None and observed_md5 != request.expected_md5:
        raise OsmAcquisitionError(
            "CHECKSUM_IDENTITY_DRIFT",
            "the supplied extract does not match the operator-declared MD5",
        )
    started = _utc_now(utc_now)
    retrieval = ManchesterRetrievalWindow(started_at_utc=started, completed_at_utc=started)
    request_identity = ManchesterRequestIdentity(
        host=OSM_SOURCE_HOST,
        path=OSM_EXTRACT_PATH,
        parameters=(),
        redacted_parameter_names=(),
    )
    member = ManchesterRawMember(
        relative_path=OSM_EXTRACT_MEMBER_PATH,
        byte_size=len(payload),
        media_type="application/octet-stream",
        sha256=observed_sha,
    )

    def validate_payload(_members: dict[str, bytes]) -> None:
        check_pbf_framing(payload)

    declared = request.expected_md5 is not None or request.expected_sha256 is not None
    snapshot_id, quarantine_receipt, snapshot_receipt, raw_fingerprint = _promote(
        workspace_root,
        members={OSM_EXTRACT_MEMBER_PATH: payload},
        inventory=(member,),
        request_identity=request_identity,
        retrieval=retrieval,
        http_metadata=None,
        policy=request.policy,
        prior=request.prior,
        findings=(
            ManchesterSnapshotFinding(
                code="LOCAL_IMPORT_NO_PROVIDER_CHECKSUM",
                severity=ManchesterFindingSeverity.INFO,
                message="imported from a local file; the provider MD5 companion was not fetched",
                artifact=OSM_EXTRACT_MEMBER_PATH,
            ),
        )
        if not declared
        else (),
        synthetic=request.synthetic,
        validate_payload=validate_payload,
    )
    return OsmExtractAcquisitionResult(
        acquisition_mode="local_import",
        snapshot_id=snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=(member,),
        identity=_identity(
            extract=payload,
            md5_digest=observed_md5,
            checksum_source="operator_declared" if declared else "absent",
            verified=declared,
            reference_date=request.expected_reference_date,
            synthetic=request.synthetic,
        ),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        snapshot_receipt=snapshot_receipt,
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
    )


def read_accepted_extract(snapshot_dir: str | Path) -> bytes:
    """Read the accepted extract bytes back for deterministic offline replay."""

    directory = Path(snapshot_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise OsmAcquisitionError(
            "SNAPSHOT_INVALID", "accepted snapshot path must be an existing non-symlink directory"
        )
    member = directory / RAW_DIRECTORY_NAME / OSM_EXTRACT_MEMBER_PATH
    resolved = member.resolve()
    if not resolved.is_relative_to(directory.resolve()):
        raise OsmAcquisitionError(
            "UNSAFE_MEMBER_PATH", "the accepted extract member escapes its snapshot directory"
        )
    if member.is_symlink() or not member.is_file():
        raise OsmAcquisitionError(
            "EXTRACT_MEMBER_MISSING", "the accepted snapshot has no readable extract member"
        )
    return member.read_bytes()

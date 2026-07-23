"""Controlled TfGM traffic-signals acquisition: download → quarantine → parse → promote.

This module wires the single audited TfGM static ZIP endpoint through the
existing MAN-01 boundaries in a fixed order: the shared
:class:`BoundedHttpClient` downloads the exact allowlisted ZIP, the exact ZIP
bytes are preserved in MAN-01 quarantine, the quarantined bytes are re-read
and re-hashed, the bounded archive boundary validates the ZIP and selects only
the two allowlisted members, the existing MAN-04 parser validates the signal
CSV, and only an explicitly admitted result promotes to accepted storage.

It adds no second HTTP, hashing, ZIP-extraction, snapshot, or promotion
implementation and changes no capability state: ``MAN-01`` and ``MAN-04``
remain ``planned``.

Semantic limits are inherited unchanged from the MAN-04 parser: TfGM signals
are static infrastructure reference data only — no traffic volume, signal
phase, cycle, queue, operational state, or SUMO programme is representable;
the dataset version date never becomes a live timestamp; retrieval time never
becomes observation time; and geography never establishes a SUMO, DfT, or
WebTRIS identity.

The full official ZIP remains workspace-only: this workflow hard-codes the
``private`` publication class. The separately reviewed three-row derived
sample is the only ``redistributable_derived`` artifact, and it is not
produced here. Attribution uses the exact wording shipped inside the acquired
ZIP (``…database right 2026.``); the Gate-A audit records that the supporting
PDF still says 2025, and a shipped attribution that differs from the audited
ZIP wording is a typed refusal, never a silent rewrite.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Literal

import httpx
from pydantic import Field, model_validator

from traffictwin.integration.manchester.acquisition import (
    ManchesterHttpSnapshotParts,
    snapshot_parts_from_http_response,
)
from traffictwin.integration.manchester.archive import (
    ArchiveMember,
    ArchivePolicy,
    BoundedZipContents,
    ManchesterArchiveError,
    read_bounded_zip,
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
    ManchesterSnapshotFinding,
    ManchesterSnapshotManifest,
    ManchesterSnapshotModel,
    ManchesterSnapshotPolicy,
    ManchesterSnapshotReceipt,
    ManchesterSourceIdentity,
    ManchesterValidationState,
    build_raw_fingerprint,
    build_snapshot_id,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.snapshots import (
    QUARANTINE_DIRECTORY_NAME,
    quarantine_validate_and_promote,
    verify_manchester_quarantine,
)
from traffictwin.integration.manchester.tfgm_signals import (
    TFGM_SIGNALS_ARCHIVE_SHA256,
    TFGM_SIGNALS_ATTRIBUTION,
    TFGM_SIGNALS_CSV_SHA256,
    TfgmSignalAdapterError,
    TfgmSignalMemberRef,
    TfgmSignalParseReport,
    parse_tfgm_signal_csv,
)
from traffictwin.integration.manchester.transport import (
    BoundedHttpClient,
    BoundedHttpResponse,
    EndpointPolicy,
    ManchesterTransportError,
    TransportPolicy,
)

TFGM_ACQUISITION_SCHEMA_VERSION = "1.0"
TFGM_ACQUISITION_METHOD_VERSION = "manchester-tfgm-acquisition-1.0"
TFGM_SOURCE_ID = "tfgm_traffic_signals"
TFGM_SOURCE_HOST = "odata.tfgm.com"
TFGM_ZIP_PATH = "/opendata/downloads/TrafficSignals/TrafficSignals_OpenData.zip"
TFGM_ZIP_MEMBER_PATH = "archive/traffic-signals.zip"
TFGM_CSV_ARCHIVE_MEMBER = "CSV-format/TrafficSignals.csv"
TFGM_OGL_ARCHIVE_MEMBER = "TFGM_OGL.txt"
TFGM_LICENCE_ID = "OGL-v3.0"
TFGM_FRESHNESS_POLICY_VERSION = "tfgm-static-reference-1.0"

MAX_QUARANTINE_MANIFEST_BYTES = 8_000_000
MAX_ADMITTED_WARNING_CODES = 8
MAX_OGL_MEMBER_BYTES = 100_000
_WARNING_CODE_PATTERN = re.compile(r"^[A-Z0-9_]{1,96}$")
_EXECUTABLE_SUFFIXES = frozenset(
    {".bat", ".cmd", ".com", ".dll", ".exe", ".js", ".msi", ".ps1", ".scr", ".sh"}
)

TFGM_ENDPOINT_POLICY = EndpointPolicy(
    endpoint_id="tfgm-open-data",
    host=TFGM_SOURCE_HOST,
    path_prefixes=("/opendata/downloads/TrafficSignals",),
)

# Fixed, non-caller-adjustable archive bounds for the ~1.2 MB audited ZIP.
TFGM_ARCHIVE_POLICY = ArchivePolicy(
    max_compressed_bytes=32_000_000,
    max_decompressed_bytes=128_000_000,
    max_member_bytes=16_000_000,
    max_members=64,
    max_compression_ratio=200.0,
)

# Conservative self-imposed transport limits; the audit found no TfGM
# rate-limit or SLA statement for the static download.
_CONNECT_TIMEOUT_S = 10.0
_READ_TIMEOUT_S = 60.0
_WRITE_TIMEOUT_S = 10.0
_POOL_TIMEOUT_S = 10.0
_TOTAL_DEADLINE_S = 180.0
_MAX_REDIRECTS = 2
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_S = 0.2
_BACKOFF_MAX_S = 2.0
_ALLOWED_MEDIA_TYPES = ("application/x-zip-compressed", "application/zip")


class TfgmAcquisitionError(RuntimeError):
    """Typed deterministic acquisition/replay failure.

    ``quarantine_snapshot_id`` is set when the complete ZIP is preserved in
    quarantine (archive refusal, attribution drift, rejected parse, refused
    warnings, replay mismatch); it is ``None`` when the download never became
    complete, in which case nothing durable was published.
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


class TfgmAcquisitionRequest(ManchesterSnapshotModel):
    """Strict typed request; the endpoint, archive bounds, and publication class are fixed.

    There is deliberately no host, URL, path, query, parser, executable, or
    archive-limit field, and no publication-class choice: the full official
    ZIP is always ``private``/workspace-only at this boundary.
    """

    policy: ManchesterSnapshotPolicy
    prior: ManchesterPriorSnapshotLink = ManchesterPriorSnapshotLink(
        relation=ManchesterPriorRelation.FIRST_SNAPSHOT
    )
    admitted_warning_codes: tuple[str, ...] = ()
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> TfgmAcquisitionRequest:
        if len(self.admitted_warning_codes) > MAX_ADMITTED_WARNING_CODES:
            raise ValueError("admitted warning codes are bounded")
        if list(self.admitted_warning_codes) != sorted(set(self.admitted_warning_codes)):
            raise ValueError("admitted warning codes must be sorted and unique")
        if any(
            _WARNING_CODE_PATTERN.fullmatch(code) is None for code in self.admitted_warning_codes
        ):
            raise ValueError("admitted warning codes must be canonical finding codes")
        return self


class TfgmReplayRequest(ManchesterSnapshotModel):
    """Offline replay claim; source/version/publication bindings are structural."""

    expected_synthetic: bool | None = None


class TfgmSelectedMemberEvidence(ManchesterSnapshotModel):
    """Typed hash/size evidence for one selected archive member."""

    path: Literal["CSV-format/TrafficSignals.csv", "TFGM_OGL.txt"]
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=0)


def build_zip_inventory_fingerprint(
    members: Sequence[ArchiveMember],
    selected_members: Sequence[TfgmSelectedMemberEvidence],
) -> str:
    """Fingerprint ZIP metadata and the selected members' content evidence."""

    inventory = [
        {
            "path": member.path,
            "compressed_bytes": member.compressed_bytes,
            "decompressed_bytes": member.decompressed_bytes,
            "compression_ratio": member.compression_ratio,
        }
        for member in sorted(members, key=lambda item: item.path)
    ]
    selected = [
        {
            "path": member.path,
            "sha256": member.sha256,
            "byte_size": member.byte_size,
        }
        for member in sorted(selected_members, key=lambda item: item.path)
    ]
    evidence = {"members": inventory, "selected_members": selected}
    return sha256_hex(canonical_json(evidence).encode("utf-8"))


def _expected_compression_ratio(member: ArchiveMember) -> float:
    if member.decompressed_bytes == 0:
        return 0.0
    if member.compressed_bytes == 0:
        raise ValueError("a non-empty ZIP member cannot have zero compressed bytes")
    return member.decompressed_bytes / member.compressed_bytes


class _TfgmReceiptBase(ManchesterSnapshotModel):
    """Shared receipt provenance with exact internal reconciliation.

    Every field that can be re-derived from the receipt's own typed evidence
    is re-derived on validation. ``parser_report_fingerprint`` is deliberately
    an externally fingerprinted reference: it is bound to the exact parser
    report by offline replay, which recomputes it from quarantined bytes.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-04"] = "MAN-04"
    method_version: Literal["manchester-tfgm-acquisition-1.0"] = "manchester-tfgm-acquisition-1.0"
    source_id: Literal["tfgm_traffic_signals"] = "tfgm_traffic_signals"
    endpoint_host: Literal["odata.tfgm.com"] = "odata.tfgm.com"
    endpoint_path: Literal["/opendata/downloads/TrafficSignals/TrafficSignals_OpenData.zip"] = (
        "/opendata/downloads/TrafficSignals/TrafficSignals_OpenData.zip"
    )
    dataset_version: Literal["nov-2025-jan-2026-release"] = "nov-2025-jan-2026-release"
    licence_id: Literal["OGL-v3.0"] = "OGL-v3.0"
    attribution_text: Literal[
        "Contains Transport for Greater Manchester data.  Contains OS data © Crown "
        "copyright and database right 2026."
    ] = (
        "Contains Transport for Greater Manchester data.  Contains OS data © Crown "
        "copyright and database right 2026."
    )
    publication_class: Literal["private"] = "private"
    snapshot_id: str = Field(pattern=r"^tfgm_traffic_signals-\d{8}T\d{6}Z-[0-9a-f]{12}$")
    raw_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    members: tuple[ManchesterRawMember, ...] = Field(min_length=1, max_length=1)
    zip_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    csv_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    csv_member: TfgmSelectedMemberEvidence
    attribution_member: TfgmSelectedMemberEvidence
    zip_members: tuple[ArchiveMember, ...] = Field(
        min_length=1, max_length=TFGM_ARCHIVE_POLICY.max_members
    )
    zip_inventory_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    rows_seen: int = Field(ge=0)
    records_accepted: int = Field(ge=0)
    rows_malformed: int = Field(ge=0)
    parser_status: ManchesterValidationState
    parser_warning_codes: tuple[str, ...] = ()
    parser_report_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    quarantine_receipt: ManchesterQuarantineReceipt
    quarantine_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    synthetic: bool

    @model_validator(mode="after")
    def validate_receipt(self) -> _TfgmReceiptBase:
        member = self.members[0]
        if member.relative_path != TFGM_ZIP_MEMBER_PATH:
            raise ValueError("the quarantine inventory must be the single official ZIP member")
        if member.sha256 != self.zip_sha256:
            raise ValueError("zip_sha256 must bind the quarantined ZIP member")
        if self.raw_fingerprint != build_raw_fingerprint(self.members):
            raise ValueError("raw fingerprint must bind the member inventory")
        if not self.snapshot_id.endswith(self.raw_fingerprint[:12]):
            raise ValueError("snapshot_id must end with the raw-fingerprint prefix")
        if self.parser_status is ManchesterValidationState.REJECTED:
            raise ValueError("a rejected parse can never produce an admitted receipt")
        if self.rows_malformed != 0:
            raise ValueError("an admitted TfGM parse cannot contain malformed rows")
        if self.records_accepted != self.rows_seen:
            raise ValueError("an admitted TfGM parse must reconcile every row")
        codes = list(self.parser_warning_codes)
        if codes != sorted(set(codes)):
            raise ValueError("parser warning codes must be sorted and unique")
        if any(_WARNING_CODE_PATTERN.fullmatch(code) is None for code in codes):
            raise ValueError("parser warning codes must be canonical finding codes")
        if self.parser_status is ManchesterValidationState.ACCEPTED and codes:
            raise ValueError("an accepted parse cannot carry warning codes")
        if self.parser_status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS and not codes:
            raise ValueError("a warning-accepted parse must record its warning codes")
        archive_paths = [entry.path for entry in self.zip_members]
        if archive_paths != sorted(archive_paths) or len(set(archive_paths)) != len(archive_paths):
            raise ValueError("zip member inventory must be sorted and unique")
        for entry in self.zip_members:
            if entry.compression_ratio != _expected_compression_ratio(entry):
                raise ValueError(
                    f"ZIP member {entry.path!r} compression ratio does not match its sizes"
                )
        by_path = {entry.path: entry for entry in self.zip_members}
        if self.csv_member.path != TFGM_CSV_ARCHIVE_MEMBER:
            raise ValueError("csv_member must describe the signal CSV member")
        if self.attribution_member.path != TFGM_OGL_ARCHIVE_MEMBER:
            raise ValueError("attribution_member must describe the shipped OGL member")
        for evidence in (self.csv_member, self.attribution_member):
            inventory_entry = by_path.get(evidence.path)
            if inventory_entry is None:
                raise ValueError(f"selected member {evidence.path!r} is absent from the inventory")
            if inventory_entry.decompressed_bytes != evidence.byte_size:
                raise ValueError(
                    f"selected member {evidence.path!r} size does not match the inventory"
                )
        if self.csv_sha256 != self.csv_member.sha256:
            raise ValueError("csv_sha256 must bind the selected CSV member evidence")
        if self.zip_inventory_fingerprint != build_zip_inventory_fingerprint(
            self.zip_members, (self.csv_member, self.attribution_member)
        ):
            raise ValueError(
                "zip inventory fingerprint must bind the complete inventory and selected hashes"
            )
        if self.quarantine_receipt.snapshot_id != self.snapshot_id:
            raise ValueError("the embedded quarantine receipt must bind this snapshot")
        if self.quarantine_receipt.raw_fingerprint != self.raw_fingerprint:
            raise ValueError("the embedded quarantine receipt must bind the raw fingerprint")
        if self.quarantine_receipt.verified_member_count != 1:
            raise ValueError("the quarantine receipt must verify exactly one member")
        if self.quarantine_receipt.verified_total_bytes != member.byte_size:
            raise ValueError("the quarantine receipt byte total must bind the ZIP member")
        if self.quarantine_receipt_fingerprint != self.quarantine_receipt.fingerprint():
            raise ValueError("quarantine_receipt_fingerprint must match the embedded receipt")
        if not self.synthetic:
            if self.zip_sha256 != TFGM_SIGNALS_ARCHIVE_SHA256:
                raise ValueError("a real receipt must bind the audited official ZIP hash")
            if self.csv_sha256 != TFGM_SIGNALS_CSV_SHA256:
                raise ValueError("a real receipt must bind the audited official CSV hash")
        return self


class TfgmAcquisitionResult(_TfgmReceiptBase):
    """Receipt for one promoted TfGM acquisition, with embedded typed sub-receipts."""

    request: TfgmAcquisitionRequest
    snapshot_receipt: ManchesterSnapshotReceipt
    snapshot_receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    promoted: Literal[True] = True

    @model_validator(mode="after")
    def validate_acquisition(self) -> TfgmAcquisitionResult:
        if self.synthetic != self.request.synthetic:
            raise ValueError("result evidence class must match the acquisition request")
        unadmitted = set(self.parser_warning_codes) - set(self.request.admitted_warning_codes)
        if unadmitted:
            raise ValueError("every observed warning code must be admitted by the embedded request")
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


class TfgmReplayResult(_TfgmReceiptBase):
    """Offline replay receipt bound to the verified quarantine; no promotion."""

    replayed_offline: Literal[True] = True


def acquire_tfgm_signals_snapshot(
    workspace_root: str | Path,
    request: TfgmAcquisitionRequest,
    *,
    http_client: httpx.Client | None = None,
    utc_now: Callable[[], datetime] | None = None,
) -> TfgmAcquisitionResult:
    """Acquire the audited TfGM signals ZIP through quarantine into accepted storage."""

    transport_policy = TransportPolicy(
        connect_timeout_s=_CONNECT_TIMEOUT_S,
        read_timeout_s=_READ_TIMEOUT_S,
        write_timeout_s=_WRITE_TIMEOUT_S,
        pool_timeout_s=_POOL_TIMEOUT_S,
        total_deadline_s=_TOTAL_DEADLINE_S,
        max_response_bytes=min(
            request.policy.max_member_bytes, TFGM_ARCHIVE_POLICY.max_compressed_bytes
        ),
        max_redirects=_MAX_REDIRECTS,
        max_attempts=_MAX_ATTEMPTS,
        backoff_base_s=_BACKOFF_BASE_S,
        backoff_max_s=_BACKOFF_MAX_S,
        allowed_media_types=_ALLOWED_MEDIA_TYPES,
    )
    with BoundedHttpClient(
        endpoint=TFGM_ENDPOINT_POLICY,
        policy=transport_policy,
        client=http_client,
        utc_now=utc_now,
    ) as client:
        try:
            response = client.fetch(TFGM_ZIP_PATH)
        except ManchesterTransportError as exc:
            raise TfgmAcquisitionError(
                "TRANSPORT_FAILURE",
                f"bounded transport failed ({exc.code}); TfGM unavailability is a "
                "typed failure and never substitutes reference data",
            ) from exc
    parts = _snapshot_parts(response)
    if len(parts.payload) > request.policy.max_total_bytes:
        raise TfgmAcquisitionError(
            "TOTAL_BYTES_EXCEEDED", "ZIP bytes exceed the snapshot policy bound"
        )

    inventory = (parts.member,)
    raw_fingerprint = build_raw_fingerprint(inventory)
    source = ManchesterSourceIdentity(
        source_id=TFGM_SOURCE_ID,
        source_name="TfGM traffic-signal locations open-data ZIP",
        adapter_version=TFGM_ACQUISITION_METHOD_VERSION,
        source_schema_version=TFGM_ACQUISITION_SCHEMA_VERSION,
        freshness_policy_version=TFGM_FRESHNESS_POLICY_VERSION,
    )
    quarantine_manifest = ManchesterQuarantineManifest(
        snapshot_id=build_snapshot_id(
            TFGM_SOURCE_ID, parts.retrieval.started_at_utc, raw_fingerprint
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
        licence_id=TFGM_LICENCE_ID,
        attribution_text=TFGM_SIGNALS_ATTRIBUTION,
        access_date=parts.retrieval.started_at_utc.date(),
        synthetic=request.synthetic,
    )

    captured_reports: list[TfgmSignalParseReport] = []
    captured_contents: list[BoundedZipContents] = []

    def validator(
        quarantine_dir: Path, manifest: ManchesterQuarantineManifest
    ) -> ManchesterSnapshotManifest:
        report, contents = _validate_quarantined_zip(quarantine_dir, manifest)
        captured_reports.append(report)
        captured_contents.append(contents)
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
                        if finding.row_number is None
                        else f"{finding.message} (row {finding.row_number})"
                    ),
                    artifact=TFGM_CSV_ARCHIVE_MEMBER,
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
        {TFGM_ZIP_MEMBER_PATH: parts.payload},
        request.policy,
        validator,
    )
    quarantine_receipt = verify_manchester_quarantine(
        Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / quarantine_manifest.snapshot_id
    )
    report = captured_reports[0]
    contents = captured_contents[0]
    csv_member = _selected_evidence(contents, TFGM_CSV_ARCHIVE_MEMBER)
    attribution_member = _selected_evidence(contents, TFGM_OGL_ARCHIVE_MEMBER)
    return TfgmAcquisitionResult(
        request=request,
        snapshot_id=quarantine_manifest.snapshot_id,
        raw_fingerprint=raw_fingerprint,
        members=inventory,
        zip_sha256=parts.member.sha256,
        csv_sha256=sha256_hex(contents.selected[TFGM_CSV_ARCHIVE_MEMBER]),
        csv_member=csv_member,
        attribution_member=attribution_member,
        zip_members=contents.members,
        zip_inventory_fingerprint=build_zip_inventory_fingerprint(
            contents.members, (csv_member, attribution_member)
        ),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        rows_malformed=report.counts.rows_malformed,
        parser_status=report.status,
        parser_warning_codes=_warning_codes(report),
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        snapshot_receipt=snapshot_receipt,
        snapshot_receipt_fingerprint=snapshot_receipt.fingerprint(),
        synthetic=request.synthetic,
    )


def replay_tfgm_quarantine(
    workspace_root: str | Path,
    snapshot_id: str,
    request: TfgmReplayRequest,
) -> TfgmReplayResult:
    """Re-validate the quarantined TfGM ZIP offline; no network, no promotion.

    The manifest's source identity, endpoint, licence, attribution, dataset
    contract, publication class, and single-member inventory are bound before
    any byte is decompressed, so quarantined bytes can never be relabelled as
    another source, version, or publication class.
    """

    quarantine_dir = Path(workspace_root) / QUARANTINE_DIRECTORY_NAME / snapshot_id
    quarantine_receipt = verify_manchester_quarantine(quarantine_dir)
    manifest = _load_quarantine_manifest(quarantine_dir)
    if manifest.snapshot_id != snapshot_id:
        raise TfgmAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest does not match the requested id"
        )
    _bind_replay_claim(manifest)
    if request.expected_synthetic is not None and manifest.synthetic != request.expected_synthetic:
        raise TfgmAcquisitionError(
            "SYNTHETIC_MISMATCH",
            "quarantined evidence class does not match the caller's declaration",
            quarantine_snapshot_id=snapshot_id,
        )
    report, contents = _validate_quarantined_zip(quarantine_dir, manifest)
    if report.status is ManchesterValidationState.REJECTED:
        raise TfgmAcquisitionError(
            "PARSE_REJECTED",
            "the MAN-04 parser rejected the quarantined signal CSV during replay",
            quarantine_snapshot_id=snapshot_id,
        )
    csv_member = _selected_evidence(contents, TFGM_CSV_ARCHIVE_MEMBER)
    attribution_member = _selected_evidence(contents, TFGM_OGL_ARCHIVE_MEMBER)
    return TfgmReplayResult(
        snapshot_id=snapshot_id,
        raw_fingerprint=manifest.raw_fingerprint,
        members=manifest.members,
        zip_sha256=manifest.members[0].sha256,
        csv_sha256=sha256_hex(contents.selected[TFGM_CSV_ARCHIVE_MEMBER]),
        csv_member=csv_member,
        attribution_member=attribution_member,
        zip_members=contents.members,
        zip_inventory_fingerprint=build_zip_inventory_fingerprint(
            contents.members, (csv_member, attribution_member)
        ),
        rows_seen=report.counts.rows_seen,
        records_accepted=report.counts.records_accepted,
        rows_malformed=report.counts.rows_malformed,
        parser_status=report.status,
        parser_warning_codes=_warning_codes(report),
        parser_report_fingerprint=report.fingerprint(),
        quarantine_receipt=quarantine_receipt,
        quarantine_receipt_fingerprint=quarantine_receipt.fingerprint(),
        synthetic=manifest.synthetic,
    )


def _selected_evidence(contents: BoundedZipContents, path: str) -> TfgmSelectedMemberEvidence:
    payload = contents.selected[path]
    if path == TFGM_CSV_ARCHIVE_MEMBER:
        return TfgmSelectedMemberEvidence(
            path="CSV-format/TrafficSignals.csv",
            sha256=sha256_hex(payload),
            byte_size=len(payload),
        )
    return TfgmSelectedMemberEvidence(
        path="TFGM_OGL.txt",
        sha256=sha256_hex(payload),
        byte_size=len(payload),
    )


def _warning_codes(report: TfgmSignalParseReport) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                finding.code
                for finding in report.findings
                if finding.severity is ManchesterFindingSeverity.WARNING
            }
        )
    )


def _snapshot_parts(response: BoundedHttpResponse) -> ManchesterHttpSnapshotParts:
    headers = dict(response.metadata.response_headers)
    content_type = headers.get("content-type", _ALLOWED_MEDIA_TYPES[0])
    media_type = content_type.split(";", 1)[0].strip().lower()
    return snapshot_parts_from_http_response(
        response,
        relative_path=TFGM_ZIP_MEMBER_PATH,
        media_type=media_type,
    )


def _admit_or_raise(
    report: TfgmSignalParseReport,
    admitted_warning_codes: tuple[str, ...],
    snapshot_id: str,
) -> None:
    if report.status is ManchesterValidationState.REJECTED:
        raise TfgmAcquisitionError(
            "PARSE_REJECTED",
            "the MAN-04 parser rejected the quarantined signal CSV",
            quarantine_snapshot_id=snapshot_id,
        )
    if report.status is ManchesterValidationState.ACCEPTED_WITH_WARNINGS:
        observed = sorted({finding.code for finding in report.findings})
        unapproved = [code for code in observed if code not in admitted_warning_codes]
        if unapproved:
            raise TfgmAcquisitionError(
                "WARNINGS_REFUSED",
                f"{len(unapproved)} warning code(s) are not in the admitted set: "
                + ", ".join(unapproved),
                quarantine_snapshot_id=snapshot_id,
            )


def _load_quarantine_manifest(quarantine_dir: Path) -> ManchesterQuarantineManifest:
    manifest_path = quarantine_dir / QUARANTINE_MANIFEST_FILE_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise TfgmAcquisitionError("QUARANTINE_INVALID", "quarantine manifest is missing or unsafe")
    if manifest_path.stat().st_size > MAX_QUARANTINE_MANIFEST_BYTES:
        raise TfgmAcquisitionError(
            "QUARANTINE_INVALID", "quarantine manifest exceeds its byte bound"
        )
    return ManchesterQuarantineManifest.model_validate_json(manifest_path.read_bytes())


def _bind_replay_claim(manifest: ManchesterQuarantineManifest) -> None:
    snapshot_id = manifest.snapshot_id
    if manifest.source.source_id != TFGM_SOURCE_ID:
        raise TfgmAcquisitionError(
            "PRODUCT_MISMATCH",
            "quarantined source id is not the TfGM traffic-signals source",
            quarantine_snapshot_id=snapshot_id,
        )
    if (
        manifest.source.adapter_version != TFGM_ACQUISITION_METHOD_VERSION
        or manifest.source.source_schema_version != TFGM_ACQUISITION_SCHEMA_VERSION
        or manifest.source.freshness_policy_version != TFGM_FRESHNESS_POLICY_VERSION
        or manifest.licence_id != TFGM_LICENCE_ID
        or manifest.attribution_text != TFGM_SIGNALS_ATTRIBUTION
        or manifest.publication_class is not ManchesterPublicationClass.PRIVATE
        or manifest.request.host != TFGM_SOURCE_HOST
        or manifest.request.path != TFGM_ZIP_PATH
        or tuple(manifest.request.parameters) != ()
        or tuple(manifest.request.redacted_parameter_names) != ()
    ):
        raise TfgmAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined source contract does not match this adapter version",
            quarantine_snapshot_id=snapshot_id,
        )
    if [member.relative_path for member in manifest.members] != [TFGM_ZIP_MEMBER_PATH]:
        raise TfgmAcquisitionError(
            "SOURCE_CONTRACT_MISMATCH",
            "quarantined member inventory is not the single official ZIP member",
            quarantine_snapshot_id=snapshot_id,
        )


def _validate_quarantined_zip(
    quarantine_dir: Path,
    manifest: ManchesterQuarantineManifest,
) -> tuple[TfgmSignalParseReport, BoundedZipContents]:
    member = manifest.members[0]
    target = quarantine_dir / RAW_DIRECTORY_NAME / member.relative_path
    if target.is_symlink() or not target.is_file():
        raise TfgmAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined ZIP member is missing or unsafe",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if target.stat().st_size != member.byte_size:
        raise TfgmAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined ZIP member size drifted",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    payload = target.read_bytes()
    if sha256_hex(payload) != member.sha256:
        raise TfgmAcquisitionError(
            "QUARANTINE_INVALID",
            "quarantined ZIP member hash drifted",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    if not manifest.synthetic and member.sha256 != TFGM_SIGNALS_ARCHIVE_SHA256:
        raise TfgmAcquisitionError(
            "OFFICIAL_ARCHIVE_IDENTITY_MISMATCH",
            "the downloaded ZIP is not the audited release; the in-place TfGM URL "
            "has been overwritten and requires re-audit before acceptance",
            quarantine_snapshot_id=manifest.snapshot_id,
        )
    try:
        contents = read_bounded_zip(
            payload,
            policy=TFGM_ARCHIVE_POLICY,
            selected_members=(TFGM_CSV_ARCHIVE_MEMBER, TFGM_OGL_ARCHIVE_MEMBER),
        )
    except ManchesterArchiveError as exc:
        raise TfgmAcquisitionError(
            "ARCHIVE_REJECTED",
            f"bounded ZIP validation refused the quarantined archive: {exc}",
            quarantine_snapshot_id=manifest.snapshot_id,
        ) from exc
    _reject_executable_members(contents, manifest.snapshot_id)
    _verify_shipped_attribution(contents, manifest.snapshot_id)

    csv_payload = contents.selected[TFGM_CSV_ARCHIVE_MEMBER]
    evidence_class: Literal["full_official_csv", "redistributable_derived_sample"] = (
        "redistributable_derived_sample" if manifest.synthetic else "full_official_csv"
    )
    ref = TfgmSignalMemberRef(
        snapshot_id=manifest.snapshot_id,
        member_path=TFGM_CSV_ARCHIVE_MEMBER,
        member_sha256=sha256_hex(csv_payload),
        evidence_class=evidence_class,
        synthetic=manifest.synthetic,
    )
    try:
        report = parse_tfgm_signal_csv((ref, csv_payload))
    except TfgmSignalAdapterError as exc:
        raise TfgmAcquisitionError(
            "PARSE_INTEGRITY",
            f"the MAN-04 parser refused the selected CSV member ({exc.code})",
            quarantine_snapshot_id=manifest.snapshot_id,
        ) from exc
    return report, contents


def _reject_executable_members(contents: BoundedZipContents, snapshot_id: str) -> None:
    for entry in contents.members:
        suffix = PurePosixPath(entry.path).suffix.lower()
        if suffix in _EXECUTABLE_SUFFIXES:
            raise TfgmAcquisitionError(
                "UNEXPECTED_MEMBER",
                f"the archive contains a disallowed member type ({suffix})",
                quarantine_snapshot_id=snapshot_id,
            )


def _verify_shipped_attribution(contents: BoundedZipContents, snapshot_id: str) -> None:
    payload = contents.selected[TFGM_OGL_ARCHIVE_MEMBER]
    if len(payload) > MAX_OGL_MEMBER_BYTES:
        raise TfgmAcquisitionError(
            "ATTRIBUTION_DRIFT",
            "the shipped attribution member exceeds its byte bound",
            quarantine_snapshot_id=snapshot_id,
        )
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TfgmAcquisitionError(
            "ATTRIBUTION_DRIFT",
            "the shipped attribution member is not UTF-8 text",
            quarantine_snapshot_id=snapshot_id,
        ) from exc
    if TFGM_SIGNALS_ATTRIBUTION not in text:
        raise TfgmAcquisitionError(
            "ATTRIBUTION_DRIFT",
            "the shipped attribution wording differs from the audited ZIP wording; "
            "attribution is never silently rewritten and the release needs re-audit",
            quarantine_snapshot_id=snapshot_id,
        )

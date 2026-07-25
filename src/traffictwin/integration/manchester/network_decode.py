"""Controlled `osmium` PBF-to-OSM-XML decode for the baseline-network build.

`netconvert` 1.27.1 as built in the reviewed environment reads OSM **XML** only
and exits 1 on a PBF container, which previously blocked the Greater Manchester
build on ``OSM_PBF_DECODE_UNAVAILABLE``.  The repository owner approved
``osmium-tool`` as the controlled decoder for this workflow.

``osmium`` is treated exactly like the existing SUMO toolchain: an optional
audited external runtime discovered on ``PATH``, version-probed, and invoked
through a frozen argument vector with no shell.  It is never imported into
Python scientific code and is not a project dependency.

The single most important boundary here is that **the decode is a format
conversion and never a content selection**.  It applies no tag filter, no
bounding-box clip, no simplification, and no road-class choice.  Deciding which
OSM ways become SUMO edges stays entirely inside the already-frozen
``netconvert`` recipe; a decode that changed which objects survive would move a
scientific decision into a conversion step where nobody would look for it.

The module performs no acquisition, no network build, and no calibration.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.network_acquisition import (
    OSM_EXTRACT_DATA_CUTOFF_DATE,
    OSM_EXTRACT_FILENAME,
    OSM_REFERENCE_DATE,
)

NETWORK_DECODE_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NETWORK_DECODE_METHOD_VERSION: Literal["manchester-osm-pbf-decode-1.0"] = (
    "manchester-osm-pbf-decode-1.0"
)
NETWORK_DECODE_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

OSMIUM_EXECUTABLE_NAME: Literal["osmium"] = "osmium"
#: Reviewed minimum. ``osmium cat`` format conversion has been stable across
#: 1.x; the observed runtime is pinned in the receipt so drift stays visible.
SUPPORTED_OSMIUM_MAJOR: Literal["1."] = "1."

#: The complete frozen decoder.  ``<input>`` and ``<output>`` are substituted
#: with private paths at run time and never appear in evidence.  There is
#: deliberately no filter, bbox, tag, or format-option element: adding one
#: would turn a conversion into a content decision.
OSMIUM_FIXED_ARGUMENTS: tuple[str, ...] = (
    "cat",
    "--output-format",
    "osm",
    "--output",
    "<output>",
    "--no-progress",
    "<input>",
)

_VERSION_PROBE_TIMEOUT_S = 20
_DECODE_TIMEOUT_S = 1_800
_OSMIUM_VERSION_PATTERN = re.compile(r"osmium version\s+(\d+\.\d+\.\d+)")
_LIBOSMIUM_VERSION_PATTERN = re.compile(r"libosmium version\s+(\d+\.\d+\.\d+)")

#: PBF framing marker: a 4-byte big-endian BlobHeader length followed by a
#: protobuf whose field 1 is the blob type ``OSMHeader``.
PBF_HEADER_MARKER = b"\x0a\x09OSMHeader"

#: ADR-059 pinned identity, measured on 25 July 2026.  Recorded here so the
#: decode can refuse an extract that is not the reviewed one.
PINNED_EXTRACT_SHA256 = "38f18e98441e89f7376678eab72d1245454547ffad4df80b76a5ac1c9ccfef3e"
PINNED_PROVIDER_MD5 = "c73b16ec7da303c1dfd331dc914bd5bc"
PINNED_PROVIDER_LAST_MODIFIED = "Sat, 25 Jul 2026 00:29:36 GMT"

#: Receipt filename written beside a promoted decoded artifact.
#: Placeholder used only while a receipt is being sealed in two passes: the first pass
#: validates the payload so pydantic fills every default, the second seals the result.
#: A persisted receipt carrying this value is rejected on load.
UNSEALED_FINGERPRINT = "0" * 64
DECODE_RECEIPT_SUFFIX = ".receipt.json"
MAX_RECEIPT_BYTES = 200_000

#: Structural validation reads a bounded prefix; an OSM XML document declares
#: its root and first elements immediately.
MAX_STRUCTURE_PREFIX_BYTES = 64 * 1024
ALLOWED_OSM_ROOT: Literal["osm"] = "osm"
_ROOT_ELEMENT = re.compile(rb"<\s*([A-Za-z_][\w.:-]*)")
_OSM_CONTENT_PATTERNS = (
    re.compile(rb"<node\b"),
    re.compile(rb"<way\b"),
    re.compile(rb"<relation\b"),
)
_PBF_SNIFF_BYTES = 64

#: A ~50 MB Greater Manchester PBF decodes to roughly 1 GB of XML (measured:
#: 50,502,348 -> 996,913,352 bytes, about 19.7x).  These bounds sit above that
#: with headroom while staying finite.
MAX_PBF_INPUT_BYTES = 512_000_000
MAX_DECODED_BYTES = 16_000_000_000
MIN_DECODED_BYTES = 1_000
#: Refuse to start when free disk cannot plausibly hold the decode.
DECODE_EXPANSION_HEADROOM = 30

DecodeBlocker: TypeAlias = Literal[
    "OSMIUM_TOOLCHAIN_UNAVAILABLE",
    "OSMIUM_VERSION_DRIFT",
]


class NetworkDecodeError(RuntimeError):
    """Typed deterministic decode refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NetworkDecodeModel(ManchesterSnapshotModel):
    """Strict frozen base for decode artifacts."""


class OsmiumToolIdentity(NetworkDecodeModel):
    """Observed decoder identity, probed rather than assumed."""

    executable_name: Literal["osmium"] = OSMIUM_EXECUTABLE_NAME
    reported_version: str = Field(min_length=1, max_length=64)
    libosmium_version: str | None = Field(default=None, max_length=64)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_major_prefix: Literal["1."] = SUPPORTED_OSMIUM_MAJOR
    licence_note: Literal["osmium-tool is GPL-3.0-or-later; executed, never linked"] = (
        "osmium-tool is GPL-3.0-or-later; executed, never linked"
    )

    @model_validator(mode="after")
    def validate_version(self) -> OsmiumToolIdentity:
        if not self.reported_version.startswith(SUPPORTED_OSMIUM_MAJOR):
            raise ValueError("osmium version must match the reviewed 1.x decoder")
        return self


class OsmSourceHeader(NetworkDecodeModel):
    """Provenance read from the PBF header itself, not from the filename.

    ``replication_timestamp`` is the authoritative OSM data-cutoff instant.  It
    is recorded separately from the provider's publication time and from the
    operator's retrieval date; the three are never collapsed.
    """

    replication_timestamp: str | None = Field(default=None, max_length=64)
    replication_sequence_number: int | None = Field(default=None, ge=0)
    generator: str | None = Field(default=None, max_length=128)
    header_min_longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    header_min_latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    header_max_longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    header_max_latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    read_from_source_header: Literal[True] = True


class DecodeSourceExpectation(NetworkDecodeModel):
    """Caller-declared source identity the decode verifies before executing.

    The decode refuses to run on anything but the exact pinned extract, so an
    unrelated or drifted PBF cannot silently become the baseline input.  The
    three provider time facts are separate fields and are never collapsed.
    """

    expected_filename: str = Field(min_length=1, max_length=128)
    expected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_md5: str = Field(pattern=r"^[0-9a-f]{32}$")
    expected_data_cutoff_date: date
    expected_retrieval_date: date
    expected_provider_last_modified: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_expectation(self) -> DecodeSourceExpectation:
        if self.expected_data_cutoff_date == self.expected_retrieval_date:
            raise ValueError(
                "the data-cutoff and retrieval dates must stay distinct; "
                "collapsing them would misrepresent when the data was observed"
            )
        return self


def pinned_source_expectation() -> DecodeSourceExpectation:
    """Return the ADR-059 pinned Greater Manchester extract expectation."""

    return DecodeSourceExpectation(
        expected_filename=OSM_EXTRACT_FILENAME,
        expected_sha256=PINNED_EXTRACT_SHA256,
        expected_md5=PINNED_PROVIDER_MD5,
        expected_data_cutoff_date=OSM_EXTRACT_DATA_CUTOFF_DATE,
        expected_retrieval_date=OSM_REFERENCE_DATE,
        expected_provider_last_modified=PINNED_PROVIDER_LAST_MODIFIED,
    )


class NetworkDecodeCommandReceipt(NetworkDecodeModel):
    """Exactly what ran, with no private path in any recorded field."""

    schema_version: Literal["1.0"] = "1.0"
    executable_name: Literal["osmium"] = OSMIUM_EXECUTABLE_NAME
    reported_version: str = Field(min_length=1, max_length=64)
    argument_shape: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    started_at_utc: datetime
    completed_at_utc: datetime
    duration_s: Decimal = Field(ge=0)
    warning_lines: tuple[str, ...] = ()
    error_lines: tuple[str, ...] = ()
    shell_used: Literal[False] = False
    caller_supplied_arguments: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> NetworkDecodeCommandReceipt:
        if self.argument_shape != OSMIUM_FIXED_ARGUMENTS:
            raise ValueError("the decode receipt must record the exact frozen decoder")
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError("decode receipt times must not run backwards")
        for line in (*self.warning_lines, *self.error_lines):
            if "/Users/" in line or "/home/" in line or "/private/" in line:
                raise ValueError("decode receipt lines must not contain private paths")
        return self


class OsmDecodeReceipt(NetworkDecodeModel):
    """Complete immutable receipt for one PBF-to-XML decode."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-osm-pbf-decode-1.0"] = NETWORK_DECODE_METHOD_VERSION
    decision_record: Literal["ADR-059"] = "ADR-059"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_bytes: int = Field(ge=1)
    decoded_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    decoded_bytes: int = Field(ge=MIN_DECODED_BYTES)
    source_filename: str = Field(min_length=1, max_length=128)
    decoded_filename: str = Field(min_length=1, max_length=128)
    provider_md5: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    #: Three distinct provider/operator time facts, never collapsed into one.
    data_cutoff_date: date | None = None
    retrieval_date: date | None = None
    provider_last_modified: str | None = Field(default=None, max_length=64)
    source_identity_verified: bool
    source_pinned_by_default: bool
    accepted_snapshot_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    osm_root_element: Literal["osm"] = ALLOWED_OSM_ROOT
    structural_validation_passed: Literal[True] = True
    structural_elements_observed: int = Field(ge=1)
    #: Workspace name plus a digest of its resolved path; never the path.
    workspace_identity: str = Field(min_length=1, max_length=128)
    #: Digest of the frozen argument vector, so a changed builder is visible.
    argument_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    licence_id: Literal["ODbL-1.0"] = "ODbL-1.0"
    attribution_text: Literal["© OpenStreetMap contributors, ODbL 1.0"] = (
        "© OpenStreetMap contributors, ODbL 1.0"
    )
    refusal_codes: tuple[str, ...] = ()
    synthetic: bool
    source_header: OsmSourceHeader
    tool: OsmiumToolIdentity
    command: NetworkDecodeCommandReceipt
    #: Structural guarantees about what the decode is allowed to be.
    conversion_only: Literal[True] = True
    content_filtered: Literal[False] = False
    bounding_box_clipped: Literal[False] = False
    simplified: Literal[False] = False
    road_classes_selected: Literal[False] = False
    publication_class: Literal["private"] = "private"
    committed_to_git: Literal[False] = False
    capability_status: Literal["planned"] = "planned"
    #: Stored so a reloaded receipt proves it was not edited in place.
    receipt_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_receipt(self) -> OsmDecodeReceipt:
        if self.argument_fingerprint != argument_fingerprint():
            raise ValueError("the decode receipt must record the exact frozen argument vector")
        if (
            self.receipt_fingerprint != UNSEALED_FINGERPRINT
            and self.receipt_fingerprint != self._expected_fingerprint()
        ):
            raise ValueError("the decode receipt fingerprint does not match its own content")
        if not self.synthetic and not self.source_identity_verified:
            raise ValueError("real evidence must have a verified pinned source identity")
        return self

    def _expected_fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("receipt_fingerprint", None)
        return sha256_hex(canonical_json(payload).encode("utf-8"))


def build_receipt_fingerprint(values: dict[str, object]) -> str:
    """Fingerprint a receipt payload that does not yet carry its own digest."""

    payload = dict(values)
    payload.pop("receipt_fingerprint", None)
    return sha256_hex(canonical_json(payload).encode("utf-8"))


def argument_fingerprint() -> str:
    """Digest of the frozen decoder vector, so a changed builder is visible."""

    return sha256_hex(canonical_json(list(OSMIUM_FIXED_ARGUMENTS)).encode("utf-8"))


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    value = (clock or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None:
        raise NetworkDecodeError("CLOCK_NAIVE", "decode clock must be timezone aware")
    return value.astimezone(UTC)


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def is_pbf(path: Path) -> bool:
    """Report whether a file opens with OSM PBF framing."""

    with path.open("rb") as handle:
        return PBF_HEADER_MARKER in handle.read(_PBF_SNIFF_BYTES)


def discover_osmium() -> Path | None:
    """Controlled discovery: the PATH-resolved ``osmium`` binary only."""

    located = shutil.which(OSMIUM_EXECUTABLE_NAME)
    if located is None:
        return None
    return Path(located)


def _probe_versions(executable: Path) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    combined = f"{result.stdout}\n{result.stderr}"
    tool = _OSMIUM_VERSION_PATTERN.search(combined)
    library = _LIBOSMIUM_VERSION_PATTERN.search(combined)
    return (
        tool.group(1) if tool is not None else None,
        library.group(1) if library is not None else None,
    )


def osmium_identity() -> OsmiumToolIdentity:
    """Probe the installed decoder and refuse anything but the reviewed one."""

    executable = discover_osmium()
    if executable is None:
        raise NetworkDecodeError(
            "OSMIUM_TOOLCHAIN_UNAVAILABLE",
            "no `osmium` executable was found on PATH; install osmium-tool "
            f"{SUPPORTED_OSMIUM_MAJOR}x to decode a PBF extract",
        )
    resolved = executable.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise NetworkDecodeError(
            "OSMIUM_TOOLCHAIN_UNAVAILABLE", "the discovered `osmium` path is not a regular file"
        )
    version, library = _probe_versions(resolved)
    if version is None:
        raise NetworkDecodeError(
            "OSMIUM_TOOLCHAIN_UNAVAILABLE",
            "the discovered `osmium` executable did not report a parseable version",
        )
    if not version.startswith(SUPPORTED_OSMIUM_MAJOR):
        raise NetworkDecodeError(
            "OSMIUM_VERSION_DRIFT",
            f"observed osmium {version}; the reviewed decoder requires "
            f"{SUPPORTED_OSMIUM_MAJOR}x and the decode fails closed",
        )
    digest, _size = _sha256_file(resolved)
    return OsmiumToolIdentity(
        reported_version=version,
        libosmium_version=library,
        executable_sha256=digest,
    )


def _classify_output(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    warnings: list[str] = []
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > 400:
            continue
        if "/Users/" in line or "/home/" in line or "/private/" in line:
            # Never persist a private path into evidence.
            continue
        lowered = line.lower()
        if lowered.startswith("error") or "error:" in lowered:
            errors.append(line)
        elif lowered.startswith("warning") or "warning:" in lowered:
            warnings.append(line)
    return tuple(warnings[:64]), tuple(errors[:64])


def read_source_header(executable: Path, source: Path) -> OsmSourceHeader:
    """Read PBF header provenance through ``osmium fileinfo``.

    The replication timestamp is the authoritative data-cutoff instant and is
    recorded separately from provider publication time and retrieval date.
    """

    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [str(executable), "fileinfo", str(source)],
            check=False,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return OsmSourceHeader()
    if result.returncode != 0:
        return OsmSourceHeader()
    text = result.stdout
    timestamp = re.search(r"osmosis_replication_timestamp=(\S+)", text)
    sequence = re.search(r"osmosis_replication_sequence_number=(\d+)", text)
    generator = re.search(r"generator=(\S+)", text)
    box = re.search(
        r"\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)",
        text,
    )
    values: list[Decimal] = []
    if box is not None:
        try:
            values = [Decimal(box.group(index)) for index in (1, 2, 3, 4)]
        except ArithmeticError:
            values = []
    complete = len(values) == 4
    return OsmSourceHeader(
        replication_timestamp=timestamp.group(1) if timestamp is not None else None,
        replication_sequence_number=int(sequence.group(1)) if sequence is not None else None,
        generator=generator.group(1) if generator is not None else None,
        header_min_longitude=values[0] if complete else None,
        header_min_latitude=values[1] if complete else None,
        header_max_longitude=values[2] if complete else None,
        header_max_latitude=values[3] if complete else None,
    )


def decode_pbf_to_osm_xml(
    source_path: str | Path,
    destination_path: str | Path,
    *,
    workspace_root: str | Path | None = None,
    expectation: DecodeSourceExpectation | None = None,
    allow_unpinned_source: bool = False,
    accepted_snapshot_dir: str | Path | None = None,
    synthetic: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> OsmDecodeReceipt:
    """Decode one PBF extract to OSM XML through the frozen ``osmium`` vector.

    The pinned source identity is verified **by default**: the ADR-059
    expectation applies unless the caller passes ``allow_unpinned_source``,
    which exists only for clearly-labelled synthetic fixtures and is recorded
    on the receipt.  ``workspace_root`` confines both staging and the
    destination; a destination that escapes it is refused.

    The decode writes to a private staging file and is renamed into place only
    after the output is verified, so a failed decode leaves no partial
    artifact.  The result is a private workspace intermediate and is never
    committed.
    """

    source = Path(source_path)
    destination = Path(destination_path)
    refusal_codes: list[str] = []
    if expectation is None and not allow_unpinned_source:
        expectation = pinned_source_expectation()
    if expectation is None and allow_unpinned_source and not synthetic:
        raise NetworkDecodeError(
            "UNPINNED_SOURCE_REFUSED",
            "an unpinned source is admitted only for clearly-labelled synthetic evidence; "
            "pass synthetic=True or supply the pinned expectation",
        )
    if source.is_symlink() or not source.is_file():
        raise NetworkDecodeError(
            "SOURCE_PATH_REFUSED", "the extract path must be an existing non-symlink regular file"
        )
    if not is_pbf(source):
        raise NetworkDecodeError(
            "SOURCE_NOT_PBF", "the source does not open with OSM PBF framing; nothing to decode"
        )
    source_size = source.stat().st_size
    if source_size > MAX_PBF_INPUT_BYTES:
        raise NetworkDecodeError(
            "SOURCE_TOO_LARGE", "the extract exceeds the reviewed PBF input bound"
        )
    if destination.exists() or destination.is_symlink():
        raise NetworkDecodeError(
            "DESTINATION_EXISTS",
            "the decode destination already exists; decoded artifacts are never replaced in place",
        )
    parent = destination.parent
    if parent.is_symlink() or not parent.is_dir():
        raise NetworkDecodeError(
            "DESTINATION_INVALID",
            "the decode destination directory must exist and not be a symlink",
        )
    workspace = _validated_workspace(workspace_root, parent)
    snapshot_fingerprint = (
        verify_accepted_snapshot(accepted_snapshot_dir)
        if accepted_snapshot_dir is not None
        else None
    )
    if snapshot_fingerprint is None:
        refusal_codes.append("ACCEPTED_SNAPSHOT_NOT_SUPPLIED")
    if expectation is not None:
        observed_sha, _ = _sha256_file(source)
        if observed_sha != expectation.expected_sha256:
            raise NetworkDecodeError(
                "SOURCE_IDENTITY_MISMATCH",
                "the extract does not match the expected pinned SHA-256; an unrelated or "
                "drifted extract never becomes the baseline input",
            )
        if _md5_file(source) != expectation.expected_md5:
            raise NetworkDecodeError(
                "PROVIDER_MD5_MISMATCH",
                "the extract does not match the provider's published MD5",
            )
        if source.name != expectation.expected_filename:
            raise NetworkDecodeError(
                "SOURCE_FILENAME_MISMATCH",
                "the extract filename does not match the pinned dated provider file",
            )
    free_bytes = shutil.disk_usage(parent).free
    if free_bytes < source_size * DECODE_EXPANSION_HEADROOM:
        raise NetworkDecodeError(
            "INSUFFICIENT_DISK_SPACE",
            "free space is below the reviewed decode headroom; the decode is refused "
            "rather than started and truncated",
        )

    tool = osmium_identity()
    executable = discover_osmium()
    if executable is None:  # pragma: no cover - osmium_identity already refused
        raise NetworkDecodeError("OSMIUM_TOOLCHAIN_UNAVAILABLE", "osmium disappeared mid-decode")
    header = read_source_header(executable, source)

    staging_dir = Path(tempfile.mkdtemp(prefix=".osm-decode-", dir=parent))
    try:
        staged = staging_dir / "decoded.osm.xml"
        substitutions = {"<input>": str(source), "<output>": str(staged)}
        argv = [str(executable)]
        argv.extend(substitutions.get(argument, argument) for argument in OSMIUM_FIXED_ARGUMENTS)

        started = _utc_now(clock)
        try:
            completed = subprocess.run(  # noqa: S603 - frozen argv, never a shell
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=_DECODE_TIMEOUT_S,
                cwd=str(staging_dir),
            )
        except subprocess.TimeoutExpired as exc:
            raise NetworkDecodeError(
                "DECODE_TIMEOUT", "the bounded osmium decode exceeded its reviewed deadline"
            ) from exc
        except OSError as exc:
            raise NetworkDecodeError(
                "DECODE_FAILED", "the bounded osmium decode could not be started"
            ) from exc
        finished = _utc_now(clock)
        warnings, errors = _classify_output(f"{completed.stdout}\n{completed.stderr}")
        receipt_command = NetworkDecodeCommandReceipt(
            reported_version=tool.reported_version,
            argument_shape=OSMIUM_FIXED_ARGUMENTS,
            exit_code=completed.returncode,
            started_at_utc=started,
            completed_at_utc=finished,
            duration_s=Decimal(str(round((finished - started).total_seconds(), 3))),
            warning_lines=warnings,
            error_lines=errors,
        )
        if completed.returncode != 0:
            raise NetworkDecodeError(
                "DECODE_FAILED",
                f"osmium exited with status {completed.returncode}; no decoded artifact is kept",
            )
        if not staged.is_file():
            raise NetworkDecodeError(
                "DECODE_PRODUCED_NO_OUTPUT", "osmium reported success but wrote no output"
            )
        decoded_size = staged.stat().st_size
        if decoded_size > MAX_DECODED_BYTES:
            raise NetworkDecodeError(
                "DECODED_TOO_LARGE", "the decoded XML exceeds the reviewed byte bound"
            )
        if decoded_size < MIN_DECODED_BYTES:
            raise NetworkDecodeError(
                "DECODED_EMPTY", "the decoded XML is empty or truncated and is never accepted"
            )
        _root, structural_elements = validate_osm_xml_structure(staged)
        source_digest, _ = _sha256_file(source)
        decoded_digest, verified_size = _sha256_file(staged)
        if verified_size != decoded_size:
            raise NetworkDecodeError(
                "DECODED_SIZE_MISMATCH", "the decoded artifact changed size during verification"
            )
        if destination.exists() or destination.is_symlink():
            raise NetworkDecodeError(
                "DESTINATION_EXISTS", "the decode destination appeared during staging"
            )
        os.replace(staged, destination)
        values: dict[str, object] = {
            "source_sha256": source_digest,
            "source_bytes": source_size,
            "decoded_sha256": decoded_digest,
            "decoded_bytes": decoded_size,
            "source_filename": source.name,
            "decoded_filename": destination.name,
            "provider_md5": expectation.expected_md5 if expectation is not None else None,
            "data_cutoff_date": (
                expectation.expected_data_cutoff_date if expectation is not None else None
            ),
            "retrieval_date": (
                expectation.expected_retrieval_date if expectation is not None else None
            ),
            "provider_last_modified": (
                expectation.expected_provider_last_modified if expectation is not None else None
            ),
            "source_identity_verified": expectation is not None,
            "source_pinned_by_default": not allow_unpinned_source,
            "accepted_snapshot_fingerprint": snapshot_fingerprint,
            "structural_elements_observed": structural_elements,
            "workspace_identity": workspace,
            "argument_fingerprint": argument_fingerprint(),
            "refusal_codes": tuple(refusal_codes),
            "synthetic": synthetic,
            "source_header": header.model_dump(mode="json"),
            "tool": tool.model_dump(mode="json"),
            "command": receipt_command.model_dump(mode="json"),
        }
        # Strict mode rejects the coercions a plain dict would need (str->datetime,
        # str->Decimal, list->tuple), so rebuild through the JSON boundary instead.
        # Seal in two passes so the digest covers the defaulted fields as well: the
        # draft exists only to let pydantic materialise the complete payload.
        draft = OsmDecodeReceipt.model_validate_json(
            json.dumps({**values, "receipt_fingerprint": UNSEALED_FINGERPRINT})
        )
        sealed = draft.model_dump(mode="json")
        receipt = OsmDecodeReceipt.model_validate_json(
            json.dumps({**sealed, "receipt_fingerprint": build_receipt_fingerprint(sealed)})
        )
        _receipt_path(destination).write_text(receipt.canonical_json() + "\n", encoding="utf-8")
        return receipt
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def _md5_file(path: Path) -> str:
    """Stream the provider-comparison MD5 without loading the file."""

    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt_path(destination: Path) -> Path:
    return destination.with_name(destination.name + DECODE_RECEIPT_SUFFIX)


def verify_decoded_artifact(destination_path: str | Path) -> OsmDecodeReceipt:
    """Revalidate a promoted decoded artifact entirely offline.

    Calls neither the provider nor the decoder: it reloads the persisted
    receipt, re-hashes the artifact by streaming, and reconciles size, digest,
    and structural framing.  A mutated receipt or a mutated artifact fails.
    """

    destination = Path(destination_path)
    if destination.is_symlink() or not destination.is_file():
        raise NetworkDecodeError(
            "DECODED_ARTIFACT_MISSING",
            "the decoded artifact path must be an existing non-symlink regular file",
        )
    receipt_file = _receipt_path(destination)
    if receipt_file.is_symlink() or not receipt_file.is_file():
        raise NetworkDecodeError(
            "DECODE_RECEIPT_MISSING", "the decoded artifact has no persisted receipt"
        )
    if receipt_file.stat().st_size > MAX_RECEIPT_BYTES:
        raise NetworkDecodeError(
            "DECODE_RECEIPT_REFUSED", "the persisted decode receipt exceeds its bounded size"
        )
    try:
        receipt = OsmDecodeReceipt.model_validate_json(receipt_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise NetworkDecodeError(
            "DECODE_RECEIPT_INVALID", "the persisted decode receipt is malformed or mutated"
        ) from exc
    if receipt.receipt_fingerprint == UNSEALED_FINGERPRINT:
        raise NetworkDecodeError(
            "DECODE_RECEIPT_INVALID", "the persisted decode receipt was never sealed"
        )
    if receipt.decoded_filename != destination.name:
        raise NetworkDecodeError(
            "DECODE_RECEIPT_MISMATCH", "the receipt does not describe this decoded artifact"
        )
    observed_size = destination.stat().st_size
    if observed_size != receipt.decoded_bytes:
        raise NetworkDecodeError(
            "DECODED_ARTIFACT_MUTATED", "the decoded artifact no longer matches its recorded size"
        )
    observed_digest, _ = _sha256_file(destination)
    if observed_digest != receipt.decoded_sha256:
        raise NetworkDecodeError(
            "DECODED_ARTIFACT_MUTATED",
            "the decoded artifact no longer matches its recorded SHA-256",
        )
    with destination.open("rb") as handle:
        prefix = handle.read(512)
    if b"<osm" not in prefix:
        raise NetworkDecodeError(
            "DECODED_NOT_OSM_XML", "the decoded artifact no longer opens as an OSM XML document"
        )
    return receipt


def _validated_workspace(workspace_root: str | Path | None, parent: Path) -> str:
    """Confine the decode to one workspace and refuse traversal or escape.

    Returns a short workspace identity for the receipt.  The identity is the
    workspace directory *name* plus a digest of its resolved path, never the
    path itself, so a receipt can bind a workspace without disclosing where the
    operator keeps it.
    """

    resolved_parent = parent.resolve()
    if workspace_root is None:
        return _workspace_identity(resolved_parent)
    root = Path(workspace_root)
    if root.is_symlink() or not root.is_dir():
        raise NetworkDecodeError(
            "WORKSPACE_INVALID", "the workspace root must be an existing non-symlink directory"
        )
    resolved_root = root.resolve()
    if not resolved_parent.is_relative_to(resolved_root):
        raise NetworkDecodeError(
            "WORKSPACE_ESCAPE_REFUSED",
            "the decode destination resolves outside the declared workspace; traversal and "
            "workspace escape are refused rather than followed",
        )
    return _workspace_identity(resolved_root)


def _workspace_identity(resolved: Path) -> str:
    """Bind a workspace without disclosing a private absolute path."""

    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]
    return f"{resolved.name}:{digest}"


def validate_osm_xml_structure(path: Path) -> tuple[str, int]:
    """Confirm an allowed root element and expected structural content.

    Reads a bounded prefix rather than parsing a gigabyte document: an OSM XML
    file declares its root and first elements at the very start, so a wrong
    root or an element-free document is detectable without a full parse.
    """

    with path.open("rb") as handle:
        prefix = handle.read(MAX_STRUCTURE_PREFIX_BYTES)
    root_match = _ROOT_ELEMENT.search(prefix)
    if root_match is None:
        raise NetworkDecodeError(
            "DECODED_NOT_OSM_XML", "the decoded output declares no XML root element"
        )
    root = root_match.group(1).decode("ascii", "replace")
    if root != ALLOWED_OSM_ROOT:
        raise NetworkDecodeError(
            "DECODED_WRONG_XML_ROOT",
            f"the decoded output has root element {root!r}; only {ALLOWED_OSM_ROOT!r} is admitted",
        )
    elements = sum(len(pattern.findall(prefix)) for pattern in _OSM_CONTENT_PATTERNS)
    if elements == 0:
        raise NetworkDecodeError(
            "DECODED_OSM_XML_EMPTY",
            "the decoded output declares an <osm> root but contains no node, way, or relation",
        )
    return root, elements


def verify_accepted_snapshot(snapshot_dir: str | Path) -> str:
    """Re-verify a promoted MAN-01 snapshot before its bytes are decoded.

    Reuses the existing snapshot service rather than reimplementing hashing, so
    a decode can only consume evidence that already passed acquisition.
    """

    from traffictwin.integration.manchester.snapshots import (
        ManchesterSnapshotError,
        verify_manchester_snapshot,
    )

    try:
        receipt = verify_manchester_snapshot(snapshot_dir)
    except ManchesterSnapshotError as exc:
        raise NetworkDecodeError(
            "SNAPSHOT_RECEIPT_INVALID",
            f"the accepted snapshot did not re-verify ({exc.code}); its bytes are not decoded",
        ) from exc
    return receipt.raw_fingerprint

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
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel

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
    clock: Callable[[], datetime] | None = None,
) -> OsmDecodeReceipt:
    """Decode one PBF extract to OSM XML through the frozen ``osmium`` vector.

    The decode writes to a private staging file and is renamed into place only
    after the output is verified, so a failed decode leaves no partial
    artifact.  The result is a private workspace intermediate and is never
    committed.
    """

    source = Path(source_path)
    destination = Path(destination_path)
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
        with staged.open("rb") as handle:
            prefix = handle.read(512)
        if b"<osm" not in prefix:
            raise NetworkDecodeError(
                "DECODED_NOT_OSM_XML", "the decoded output does not open as an OSM XML document"
            )
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
        return OsmDecodeReceipt(
            source_sha256=source_digest,
            source_bytes=source_size,
            decoded_sha256=decoded_digest,
            decoded_bytes=decoded_size,
            source_header=header,
            tool=tool,
            command=receipt_command,
        )
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

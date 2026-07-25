"""Deterministic SUMO 1.27.1 baseline-network build from an accepted OSM extract.

This is design Gate-D step 1 ("Bind one reviewed Manchester SUMO network and
licence") and nothing beyond it.  A built network is geometry: it is not
calibration, not validation, not live traffic, and not VEC execution.

Controls enforced here:

*   **One fixed reviewed builder.**  :data:`NETCONVERT_FIXED_ARGUMENTS` is
    frozen.  The operator supplies no argument, flag, executable name, tool
    path, typemap, or option string, and no shell is ever used.
*   **Tool-version drift fails closed.**  ``netconvert`` must report
    ``1.27.x``; anything else refuses with ``SUMO_VERSION_DRIFT``.
*   **Isolated workspace and atomic promotion.**  Every build runs in a private
    temporary directory and is renamed into place only after the output is
    verified.  A failed build leaves no partial accepted artifact.
*   **Honest determinism.**  ``netconvert`` writes a generation banner
    containing a timestamp and the echoed output filename, so raw bytes differ
    between runs.  The build records both the raw digest and a canonical
    identity digest computed with comments removed; only the canonical digest
    is claimed reproducible.
*   **No private paths in evidence.**  The command receipt records the argument
    *shape* with ``<input>``/``<output>`` placeholders, never absolute paths.

The module performs no acquisition, no map matching, and no calibration.
"""

from __future__ import annotations

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

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    sha256_hex,
)
from traffictwin.integration.manchester.network_acquisition import (
    OSM_ATTRIBUTION,
    OSM_EXTRACT_DATA_CUTOFF_DATE,
    OSM_LICENCE_ID,
    OSM_REFERENCE_DATE,
    OsmExtractIdentity,
)
from traffictwin.integration.manchester.network_scope import (
    BaselineScopeDecision,
    GeographicPoint,
    baseline_scope_decision,
)

NETWORK_BUILD_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NETWORK_BUILD_METHOD_VERSION: Literal["manchester-baseline-network-build-1.0"] = (
    "manchester-baseline-network-build-1.0"
)
NETWORK_BUILD_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

#: Required exact toolchain.  ``sumo_execution`` already pins this prefix for
#: controlled runs; the baseline build uses the same reviewed boundary.
SUPPORTED_SUMO_VERSION_PREFIX: Literal["1.27."] = "1.27."
NETCONVERT_EXECUTABLE_NAME: Literal["netconvert"] = "netconvert"

#: The complete frozen builder.  ``<input>`` and ``<output>`` are substituted
#: with private temporary paths at run time and never appear in evidence.
#: There is deliberately no mechanism for a caller to add, remove, or reorder
#: any element of this vector.
NETCONVERT_FIXED_ARGUMENTS: tuple[str, ...] = (
    "--osm-files",
    "<input>",
    "--output-file",
    "<output>",
    "--osm.bike-access",
    "false",
    "--osm.sidewalks",
    "false",
    "--geometry.remove",
    "--ramps.guess",
    "--junctions.join",
    "--tls.guess-signals",
    "--tls.discard-simple",
    "--tls.join",
    "--no-turnarounds",
    "--numerical-ids",
    "--seed",
    "42",
    "--xml-validation",
    "never",
)

_VERSION_PROBE_TIMEOUT_S = 20
_BUILD_TIMEOUT_S = 3_600
_SUMO_VERSION_PATTERN = re.compile(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b")
_XML_COMMENT = re.compile(rb"<!--.*?-->", re.DOTALL)
_LOCATION_ELEMENT = re.compile(rb"<location\b[^>]*/>")
_ATTRIBUTE = re.compile(rb'(\w+)="([^"]*)"')
_COUNT_PATTERNS: dict[str, re.Pattern[bytes]] = {
    "edge": re.compile(rb"<edge\b"),
    "junction": re.compile(rb"<junction\b"),
    "connection": re.compile(rb"<connection\b"),
    "lane": re.compile(rb"<lane\b"),
    "tl_logic": re.compile(rb"<tlLogic\b"),
}

#: Bound the produced network so a runaway build cannot exhaust the host.
MAX_NETWORK_BYTES = 4_000_000_000
MIN_NETWORK_BYTES = 1_000

#: PBF framing marker, used only to refuse PBF input with a clear reason.
#: Measured on 25 July 2026: ``netconvert`` 1.27.1 as built in the reviewed
#: environment reads OSM **XML** only.  Handed the pinned ``.osm.pbf`` it exits
#: 1 with ``Error: invalid byte '' at position 2 of a 2-byte sequence``, i.e. it
#: tries to parse the binary container as XML.  The reviewed build features
#: (``Proj GUI FMT Intl SWIG Parquet Eigen GDAL GL2PS JuPedSim``) list no PBF
#: reader.  Rather than surface that confusing XML error, the builder refuses
#: PBF explicitly and names the missing decode step.
_PBF_HEADER_MARKER = b"\x0a\x09OSMHeader"
_PBF_SNIFF_BYTES = 64

BuildBlocker: TypeAlias = Literal[
    "OSM_PBF_DECODE_UNAVAILABLE",
    "SUMO_TOOLCHAIN_UNAVAILABLE",
    "SUMO_VERSION_DRIFT",
]


class NetworkBuildError(RuntimeError):
    """Typed deterministic build or validation refusal."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NetworkBuildModel(ManchesterSnapshotModel):
    """Strict frozen base for baseline-network build artifacts."""


class NetconvertToolIdentity(NetworkBuildModel):
    """Observed toolchain identity, probed rather than assumed."""

    executable_name: Literal["netconvert"] = NETCONVERT_EXECUTABLE_NAME
    reported_version: str = Field(min_length=1, max_length=64)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supported_version_prefix: Literal["1.27."] = SUPPORTED_SUMO_VERSION_PREFIX

    @model_validator(mode="after")
    def validate_version(self) -> NetconvertToolIdentity:
        if not self.reported_version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
            raise ValueError("netconvert version must match the reviewed 1.27.x toolchain")
        return self


class NetworkBuildInputManifest(NetworkBuildModel):
    """Immutable identity of everything that determines the produced network."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-baseline-network-build-1.0"] = NETWORK_BUILD_METHOD_VERSION
    decision_record: Literal["ADR-059"] = "ADR-059"
    extract: OsmExtractIdentity
    scope: BaselineScopeDecision
    tool: NetconvertToolIdentity
    argument_shape: tuple[str, ...] = Field(min_length=1)
    licence_id: Literal["ODbL-1.0"] = OSM_LICENCE_ID
    attribution_text: Literal["© OpenStreetMap contributors, ODbL 1.0"] = OSM_ATTRIBUTION

    @model_validator(mode="after")
    def validate_manifest(self) -> NetworkBuildInputManifest:
        if self.argument_shape != NETCONVERT_FIXED_ARGUMENTS:
            raise ValueError("the input manifest must record the exact frozen builder")
        return self


class NetworkBuildCommandReceipt(NetworkBuildModel):
    """Exactly what ran, with no private path in any recorded field."""

    schema_version: Literal["1.0"] = "1.0"
    executable_name: Literal["netconvert"] = NETCONVERT_EXECUTABLE_NAME
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
    def validate_receipt(self) -> NetworkBuildCommandReceipt:
        if self.argument_shape != NETCONVERT_FIXED_ARGUMENTS:
            raise ValueError("the command receipt must record the exact frozen builder")
        if self.completed_at_utc < self.started_at_utc:
            raise ValueError("command receipt times must not run backwards")
        for line in (*self.warning_lines, *self.error_lines):
            if "/" in line and ("/Users/" in line or "/home/" in line or "/private/" in line):
                raise ValueError("command receipt lines must not contain private paths")
        return self


class SumoNetworkLocation(NetworkBuildModel):
    """The projection metadata read verbatim from the produced network.

    TrafficTwin does not choose or re-derive these values; ``netconvert``
    writes them and they are copied unchanged.
    """

    proj_parameter: str = Field(min_length=1, max_length=400)
    net_offset: str = Field(min_length=1, max_length=120)
    conv_boundary: str = Field(min_length=1, max_length=200)
    orig_boundary: str = Field(min_length=1, max_length=200)
    read_from_network: Literal[True] = True
    rederived_by_traffictwin: Literal[False] = False


class NetworkExtent(NetworkBuildModel):
    """The produced network's own WGS84 extent, read from ``origBoundary``.

    This is deliberately a distinct type from
    :class:`~traffictwin.integration.manchester.network_scope.ExtractEnvelope`.
    The envelope is derived from generalised ONS display geometry with a
    declared margin; this is measured from the network itself and carries no
    margin and no display-geometry derivation.  Conflating the two would
    misattribute where the numbers came from.
    """

    derivation: Literal["read_from_produced_network"] = "read_from_produced_network"
    min_longitude: Decimal = Field(ge=-180, le=180)
    min_latitude: Decimal = Field(ge=-90, le=90)
    max_longitude: Decimal = Field(ge=-180, le=180)
    max_latitude: Decimal = Field(ge=-90, le=90)
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    administrative_boundary: Literal[False] = False

    @model_validator(mode="after")
    def validate_extent(self) -> NetworkExtent:
        if self.min_longitude >= self.max_longitude:
            raise ValueError("network extent longitude range must be increasing")
        if self.min_latitude >= self.max_latitude:
            raise ValueError("network extent latitude range must be increasing")
        return self

    def contains(self, point: GeographicPoint) -> bool:
        """Report containment without altering the point."""

        return (
            self.min_longitude <= point.longitude <= self.max_longitude
            and self.min_latitude <= point.latitude <= self.max_latitude
        )


class SumoNetworkStructure(NetworkBuildModel):
    """Deterministic structural counts for the produced network."""

    edge_count: int = Field(ge=0)
    junction_count: int = Field(ge=0)
    connection_count: int = Field(ge=0)
    lane_count: int = Field(ge=0)
    traffic_light_count: int = Field(ge=0)


class RequiredAreaCoverage(NetworkBuildModel):
    """Whether an approved required area lies inside the produced network."""

    area: str = Field(min_length=1, max_length=64)
    inside_network_boundary: bool
    evaluation_frame: Literal["EPSG:4326"] = "EPSG:4326"


class SumoNetworkValidation(NetworkBuildModel):
    """Structural and geographic admission of one produced network."""

    schema_version: Literal["1.0"] = "1.0"
    status: Literal["accepted", "rejected"]
    structure: SumoNetworkStructure
    location: SumoNetworkLocation
    network_extent_wgs84: NetworkExtent | None
    required_areas: tuple[RequiredAreaCoverage, ...]
    findings: tuple[str, ...] = ()
    calibration_performed: Literal[False] = False
    validated_against_observations: Literal[False] = False

    @model_validator(mode="after")
    def validate_result(self) -> SumoNetworkValidation:
        if self.status == "accepted":
            if self.structure.edge_count <= 0 or self.structure.junction_count <= 0:
                raise ValueError("an accepted network must contain edges and junctions")
            missing = tuple(
                area.area for area in self.required_areas if not area.inside_network_boundary
            )
            if missing:
                raise ValueError(
                    "an accepted network must cover every required area; "
                    f"missing: {', '.join(sorted(missing))}"
                )
        return self


class ManchesterBaselineNetworkBinding(NetworkBuildModel):
    """The bound Greater Manchester baseline network.

    This is Gate-D step 1 evidence only.  It deliberately does not set the
    map-matching acceptance flags: lifting those additionally requires an
    approved matching policy and accepted Gate-B real-source evidence.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-baseline-network-build-1.0"] = NETWORK_BUILD_METHOD_VERSION
    decision_record: Literal["ADR-059"] = "ADR-059"
    network_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    #: Raw bytes of the produced file.  Not stable across runs; see identity.
    network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: Canonical form with the generation banner removed.  Stable across runs.
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_bytes: int = Field(ge=MIN_NETWORK_BYTES)
    byte_reproducible: Literal[False] = False
    semantically_reproducible: Literal[True] = True
    inputs: NetworkBuildInputManifest
    command: NetworkBuildCommandReceipt
    validation: SumoNetworkValidation
    baseline_scope: Literal["greater_manchester_combined_authority"] = (
        "greater_manchester_combined_authority"
    )
    sub_area_filter_scope: Literal["manchester_local_authority"] = "manchester_local_authority"
    licence_id: Literal["ODbL-1.0"] = OSM_LICENCE_ID
    attribution_text: Literal["© OpenStreetMap contributors, ODbL 1.0"] = OSM_ATTRIBUTION
    publication_class: Literal["redistributable_derived"] = "redistributable_derived"
    capability_status: Literal["planned"] = "planned"
    gate_d_step: Literal["network_binding_only"] = "network_binding_only"
    reviewed_manchester_network: Literal[True] = True
    accepted_for_real_matching: Literal[False] = False
    calibration_performed: Literal[False] = False
    comparison_performed: Literal[False] = False
    vec_execution_performed: Literal[False] = False
    live_traffic_claim: Literal[False] = False


class NetworkBuildRequest(NetworkBuildModel):
    """Strict typed build request.

    There is deliberately no executable, argument, flag, typemap, option, or
    tool-path field: the builder is frozen and the operator selects none of it.
    """

    network_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")
    extract: OsmExtractIdentity
    synthetic: bool

    @model_validator(mode="after")
    def validate_request(self) -> NetworkBuildRequest:
        if self.extract.reference_date != OSM_REFERENCE_DATE:
            raise ValueError("the build request must bind the reviewed extract reference date")
        if self.extract.extract_data_cutoff_date != OSM_EXTRACT_DATA_CUTOFF_DATE:
            raise ValueError("the build request must bind the reviewed extract data cutoff")
        return self


def _utc_now(clock: Callable[[], datetime] | None) -> datetime:
    value = (clock or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None:
        raise NetworkBuildError("CLOCK_NAIVE", "build clock must be timezone aware")
    return value.astimezone(UTC)


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_network_bytes(payload: bytes) -> bytes:
    """Return the network with its volatile generation banner removed.

    ``netconvert`` writes a leading XML comment containing a wall-clock
    timestamp and the echoed output filename.  Those two values are the only
    observed difference between runs over identical inputs, and they carry no
    network semantics, so the identity digest is computed without them.
    """

    without_comments = _XML_COMMENT.sub(b"", payload)
    return b"\n".join(line.rstrip() for line in without_comments.split(b"\n") if line.strip())


def check_builder_input_format(extract_path: Path) -> None:
    """Refuse an input format the reviewed toolchain cannot actually read.

    ``netconvert`` 1.27.1 reads OSM XML.  Handed a PBF container it fails with
    an XML parse error that says nothing useful, so the builder detects PBF
    framing first and names the missing decode step instead.
    """

    with extract_path.open("rb") as handle:
        prefix = handle.read(_PBF_SNIFF_BYTES)
    if _PBF_HEADER_MARKER in prefix:
        raise NetworkBuildError(
            "OSM_PBF_DECODE_UNAVAILABLE",
            "the reviewed netconvert 1.27.1 build reads OSM XML and cannot read a PBF "
            "container; a PBF-to-XML decode step is required and no approved decoder is "
            "available in this environment. The extract stays accepted and unchanged",
        )


def discover_netconvert() -> Path | None:
    """Controlled discovery: the PATH-resolved ``netconvert`` binary only."""

    located = shutil.which(NETCONVERT_EXECUTABLE_NAME)
    if located is None:
        return None
    return Path(located)


def _probe_version(executable: Path) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed read-only argv, never a shell
            [str(executable), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=_VERSION_PROBE_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    for source in (result.stdout, result.stderr):
        for line in source.splitlines():
            if "netconvert" not in line.lower():
                continue
            match = _SUMO_VERSION_PATTERN.search(line)
            if match is not None:
                return match.group(1)
    return None


def netconvert_identity() -> NetconvertToolIdentity:
    """Probe the installed toolchain and refuse anything but the reviewed one."""

    executable = discover_netconvert()
    if executable is None:
        raise NetworkBuildError(
            "SUMO_TOOLCHAIN_UNAVAILABLE",
            "no `netconvert` executable was found on PATH; install Eclipse SUMO "
            f"{SUPPORTED_SUMO_VERSION_PREFIX}x to build a baseline network",
        )
    resolved = executable.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise NetworkBuildError(
            "SUMO_TOOLCHAIN_UNAVAILABLE", "the discovered `netconvert` path is not a regular file"
        )
    version = _probe_version(resolved)
    if version is None:
        raise NetworkBuildError(
            "SUMO_TOOLCHAIN_UNAVAILABLE",
            "the discovered `netconvert` executable did not report a parseable version",
        )
    if not version.startswith(SUPPORTED_SUMO_VERSION_PREFIX):
        raise NetworkBuildError(
            "SUMO_VERSION_DRIFT",
            f"observed netconvert {version}; the reviewed baseline requires "
            f"{SUPPORTED_SUMO_VERSION_PREFIX}x and the build fails closed",
        )
    return NetconvertToolIdentity(
        reported_version=version,
        executable_sha256=_sha256_file(resolved),
    )


def _classify_output(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    warnings: list[str] = []
    errors: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or len(line) > 400:
            continue
        lowered = line.lower()
        if lowered.startswith("error") or "error:" in lowered:
            errors.append(line)
        elif lowered.startswith("warning") or "cannot find" in lowered:
            warnings.append(line)
    return tuple(warnings[:64]), tuple(errors[:64])


def _parse_location(payload: bytes) -> SumoNetworkLocation:
    match = _LOCATION_ELEMENT.search(payload)
    if match is None:
        raise NetworkBuildError(
            "NETWORK_LOCATION_MISSING",
            "the produced network has no <location> element; its projection is unknown "
            "and is never guessed",
        )
    attributes = {
        name.decode("ascii"): value.decode("utf-8", "replace")
        for name, value in _ATTRIBUTE.findall(match.group(0))
    }
    try:
        return SumoNetworkLocation(
            proj_parameter=attributes["projParameter"],
            net_offset=attributes["netOffset"],
            conv_boundary=attributes["convBoundary"],
            orig_boundary=attributes["origBoundary"],
        )
    except KeyError as exc:
        raise NetworkBuildError(
            "NETWORK_LOCATION_INCOMPLETE",
            "the produced network's <location> element is missing required projection metadata",
        ) from exc


def _parse_extent(location: SumoNetworkLocation) -> NetworkExtent | None:
    """Read the network's own WGS84 extent from ``origBoundary``."""

    parts = location.orig_boundary.split(",")
    if len(parts) != 4:
        return None
    try:
        values = [Decimal(part.strip()) for part in parts]
    except ArithmeticError:
        return None
    min_longitude, min_latitude, max_longitude, max_latitude = values
    if min_longitude >= max_longitude or min_latitude >= max_latitude:
        return None
    quantum = Decimal("0.000001")
    return NetworkExtent(
        min_longitude=min_longitude.quantize(quantum),
        min_latitude=min_latitude.quantize(quantum),
        max_longitude=max_longitude.quantize(quantum),
        max_latitude=max_latitude.quantize(quantum),
    )


def _structure(payload: bytes) -> SumoNetworkStructure:
    counts = {name: len(pattern.findall(payload)) for name, pattern in _COUNT_PATTERNS.items()}
    return SumoNetworkStructure(
        edge_count=counts["edge"],
        junction_count=counts["junction"],
        connection_count=counts["connection"],
        lane_count=counts["lane"],
        traffic_light_count=counts["tl_logic"],
    )


def validate_network_bytes(
    payload: bytes,
    *,
    scope: BaselineScopeDecision,
) -> SumoNetworkValidation:
    """Validate a produced network's structure, projection, and area coverage."""

    if len(payload) < MIN_NETWORK_BYTES:
        raise NetworkBuildError(
            "NETWORK_EMPTY", "the produced network is empty or truncated and is never accepted"
        )
    if b"<net" not in payload[:4096]:
        raise NetworkBuildError(
            "NETWORK_CORRUPT", "the produced file does not open as a SUMO network document"
        )
    location = _parse_location(payload)
    structure = _structure(payload)
    extent = _parse_extent(location)
    findings: list[str] = []
    coverage: list[RequiredAreaCoverage] = []
    for probe in scope.required_areas:
        point = GeographicPoint(longitude=probe.point.longitude, latitude=probe.point.latitude)
        inside = extent.contains(point) if extent is not None else False
        coverage.append(RequiredAreaCoverage(area=probe.area, inside_network_boundary=inside))
    if extent is None:
        findings.append("NETWORK_EXTENT_UNREADABLE")
    if structure.edge_count == 0:
        findings.append("NETWORK_HAS_NO_EDGES")
    if structure.junction_count == 0:
        findings.append("NETWORK_HAS_NO_JUNCTIONS")
    if structure.connection_count == 0:
        findings.append("NETWORK_HAS_NO_CONNECTIONS")
    missing = [item.area for item in coverage if not item.inside_network_boundary]
    findings.extend(f"REQUIRED_AREA_OUTSIDE_NETWORK:{area}" for area in sorted(missing))
    status: Literal["accepted", "rejected"] = (
        "accepted"
        if not findings and structure.edge_count > 0 and structure.junction_count > 0
        else "rejected"
    )
    return SumoNetworkValidation(
        status=status,
        structure=structure,
        location=location,
        network_extent_wgs84=extent,
        required_areas=tuple(coverage),
        findings=tuple(findings),
    )


def build_baseline_network(
    output_root: str | Path,
    extract_path: str | Path,
    request: NetworkBuildRequest,
    *,
    scope: BaselineScopeDecision | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ManchesterBaselineNetworkBinding:
    """Build one Greater Manchester baseline network deterministically.

    The build runs in a private temporary directory and is renamed into
    ``<output_root>/<network_id>`` only after the produced network validates.
    A failed build leaves no accepted artifact behind.
    """

    root = Path(output_root)
    if root.is_symlink() or not root.is_dir():
        raise NetworkBuildError(
            "OUTPUT_ROOT_INVALID", "output root must be an existing non-symlink directory"
        )
    source = Path(extract_path)
    if source.is_symlink() or not source.is_file():
        raise NetworkBuildError(
            "EXTRACT_PATH_REFUSED", "the extract path must be an existing non-symlink regular file"
        )
    check_builder_input_format(source)
    destination = root / request.network_id
    if destination.exists() or destination.is_symlink():
        raise NetworkBuildError(
            "DESTINATION_EXISTS",
            f"network destination {request.network_id!r} already exists; "
            "accepted networks are never replaced in place",
        )
    tool = netconvert_identity()
    resolved_scope = scope if scope is not None else baseline_scope_decision()
    executable = discover_netconvert()
    if executable is None:  # pragma: no cover - netconvert_identity already refused
        raise NetworkBuildError("SUMO_TOOLCHAIN_UNAVAILABLE", "netconvert disappeared mid-build")

    staging = Path(tempfile.mkdtemp(prefix=f".{request.network_id}-build-", dir=root))
    try:
        payload_dir = staging / "payload"
        payload_dir.mkdir()
        network_path = payload_dir / f"{request.network_id}.net.xml"
        substitutions = {"<input>": str(source), "<output>": str(network_path)}
        argv = [str(executable)]
        argv.extend(
            substitutions.get(argument, argument) for argument in NETCONVERT_FIXED_ARGUMENTS
        )

        started = _utc_now(clock)
        try:
            completed = subprocess.run(  # noqa: S603 - frozen argv, never a shell
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=_BUILD_TIMEOUT_S,
                cwd=str(payload_dir),
            )
        except subprocess.TimeoutExpired as exc:
            raise NetworkBuildError(
                "BUILD_TIMEOUT", "the bounded netconvert build exceeded its reviewed deadline"
            ) from exc
        except OSError as exc:
            raise NetworkBuildError(
                "BUILD_FAILED", "the bounded netconvert build could not be started"
            ) from exc
        finished = _utc_now(clock)
        warnings, errors = _classify_output(f"{completed.stdout}\n{completed.stderr}")
        receipt = NetworkBuildCommandReceipt(
            reported_version=tool.reported_version,
            argument_shape=NETCONVERT_FIXED_ARGUMENTS,
            exit_code=completed.returncode,
            started_at_utc=started,
            completed_at_utc=finished,
            duration_s=Decimal(str(round((finished - started).total_seconds(), 3))),
            warning_lines=warnings,
            error_lines=errors,
        )
        if completed.returncode != 0:
            raise NetworkBuildError(
                "BUILD_FAILED",
                f"netconvert exited with status {completed.returncode}; no network is accepted",
            )
        if not network_path.is_file():
            raise NetworkBuildError(
                "BUILD_PRODUCED_NO_OUTPUT", "netconvert reported success but wrote no network"
            )
        size = network_path.stat().st_size
        if size > MAX_NETWORK_BYTES:
            raise NetworkBuildError(
                "NETWORK_TOO_LARGE", "the produced network exceeds the reviewed byte bound"
            )
        payload = network_path.read_bytes()
        validation = validate_network_bytes(payload, scope=resolved_scope)
        if validation.status != "accepted":
            raise NetworkBuildError(
                "NETWORK_VALIDATION_REJECTED",
                "the produced network failed validation: " + ", ".join(validation.findings),
            )
        binding = ManchesterBaselineNetworkBinding(
            network_id=request.network_id,
            network_sha256=sha256_hex(payload),
            network_identity_sha256=sha256_hex(canonical_network_bytes(payload)),
            network_bytes=size,
            inputs=NetworkBuildInputManifest(
                extract=request.extract,
                scope=resolved_scope,
                tool=tool,
                argument_shape=NETCONVERT_FIXED_ARGUMENTS,
            ),
            command=receipt,
            validation=validation,
        )
        (payload_dir / "binding.json").write_text(binding.canonical_json() + "\n", encoding="utf-8")
        if destination.exists() or destination.is_symlink():
            raise NetworkBuildError(
                "DESTINATION_EXISTS", "the network destination appeared during staging"
            )
        payload_dir.rename(destination)
        return binding
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def load_binding(network_dir: str | Path) -> ManchesterBaselineNetworkBinding:
    """Reopen an accepted network binding and re-verify its recorded digests."""

    directory = Path(network_dir)
    if directory.is_symlink() or not directory.is_dir():
        raise NetworkBuildError(
            "NETWORK_DIR_INVALID", "network path must be an existing non-symlink directory"
        )
    binding_path = directory / "binding.json"
    if binding_path.is_symlink() or not binding_path.is_file():
        raise NetworkBuildError("BINDING_MISSING", "the network directory has no binding record")
    binding = ManchesterBaselineNetworkBinding.model_validate_json(
        binding_path.read_text(encoding="utf-8")
    )
    network_path = directory / f"{binding.network_id}.net.xml"
    if network_path.is_symlink() or not network_path.is_file():
        raise NetworkBuildError("NETWORK_MISSING", "the bound network file is absent")
    payload = network_path.read_bytes()
    if sha256_hex(payload) != binding.network_sha256:
        raise NetworkBuildError(
            "NETWORK_MUTATED", "the bound network file no longer matches its recorded digest"
        )
    if sha256_hex(canonical_network_bytes(payload)) != binding.network_identity_sha256:
        raise NetworkBuildError(
            "NETWORK_IDENTITY_MUTATED",
            "the bound network no longer matches its recorded semantic identity",
        )
    return binding

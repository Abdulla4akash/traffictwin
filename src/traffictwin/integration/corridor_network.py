"""Region-neutral corridor network-build contract (Bangladesh tier 2, optional).

Implements the REVIEWED ``docs/platform/dhaka_corridor_design.md``: the
generic half of a corridor network build — scope, pinned-extract identity,
bounded tool invocation, measured extent/landmark reconciliation, and
deterministic receipts — in a module deliberately DISJOINT from every
Manchester binding. The Manchester contract hard-codes Greater Manchester,
local-authority code E08000003 and its own method version; passing Dhaka
bytes through it would create false provenance, so this module refuses
Manchester literals in a corridor scope outright.

The honest artifact is a *network-build feasibility result*, never a twin:
the receipt's role is capped at ``corridor_network_candidate``, whether it
contains its requested corridor is a MEASURED field, observation status is
the type-level literal ``"unavailable"`` (never zero), and the excluded
claims are stated in the receipt itself. A failed or incomplete build yields
a typed feasibility-gap report — it is not silently repaired.

Authority is not code's to grant: BD-D1 (the frozen corridor) and BD-D2
(the pinned dated extract) are genuine owner decisions, and a real
download/build additionally requires an explicit network confirmation.
Everything in this module is offline-testable without either.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

METHOD_VERSION: Literal["corridor-network-build-1.0"] = "corridor-network-build-1.0"
DESIGN_REFERENCE: Literal["docs/platform/dhaka_corridor_design.md"] = (
    "docs/platform/dhaka_corridor_design.md"
)

OSM_LICENCE: Literal["ODbL-1.0"] = "ODbL-1.0"
OSM_ATTRIBUTION: Literal["© OpenStreetMap contributors, ODbL 1.0"] = (
    "© OpenStreetMap contributors, ODbL 1.0"
)

#: Statements every receipt carries verbatim (design §4).
EXCLUDED_CLAIMS: tuple[str, ...] = (
    "no observations, demand, routes, calibration, behavioural model, VEC "
    "execution or scientific validation are carried by this artifact",
    "this is a network-layer engineering feasibility artifact, not a twin",
    "the corridor role never implies a city baseline",
)

#: Manchester identity literals whose presence in a corridor scope would
#: create false provenance; the scope validator refuses them by name.
MANCHESTER_LITERALS: tuple[str, ...] = (
    "E08000003",
    "manchester",
    "gm-baseline",
    "greater-manchester",
)

_PRIVATE_PATH_MARKERS = ("/Users/", "/home/", "\\Users\\")
_MINIMUM_LANDMARKS = 4
_EARTH_RADIUS_M = 6_371_008.8

_OSMIUM_EXECUTABLE = "osmium"
_NETCONVERT_EXECUTABLE = "netconvert"


class CorridorNetworkError(RuntimeError):
    """Typed refusal; the corridor contract fails closed, never silently."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class CorridorModel(BaseModel):
    """Strict, frozen, finite base for corridor artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _refuse_private_text(value: str, field_name: str) -> str:
    for marker in _PRIVATE_PATH_MARKERS:
        if marker in value:
            raise ValueError(f"{field_name} carries a private absolute path marker")
    return value


class CorridorLandmark(CorridorModel):
    """One owner-approved landmark the built network must reconcile against."""

    name: str = Field(min_length=1, max_length=120)
    longitude: float = Field(ge=-180.0, le=180.0)
    latitude: float = Field(ge=-90.0, le=90.0)


class ExtractPin(CorridorModel):
    """BD-D2: one dated provider artifact, pinned by exact identity.

    A ``-latest`` redirect is refused: the Manchester programme measured that
    dated files are the only stable identity (N1 taught the cost of citing
    anything else), and the pin must record what was actually retrieved.
    """

    url: str = Field(min_length=1, max_length=1_000)
    reference_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    byte_size: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_checksum: str | None = None
    retrieved_at_utc: str = Field(min_length=1, max_length=64)
    licence: Literal["ODbL-1.0"] = OSM_LICENCE
    attribution: Literal["© OpenStreetMap contributors, ODbL 1.0"] = OSM_ATTRIBUTION

    @model_validator(mode="after")
    def validate_pin(self) -> ExtractPin:
        if "latest" in self.url.lower():
            raise ValueError(
                "the extract must be a dated provider artifact, never a -latest redirect"
            )
        _refuse_private_text(self.url, "url")
        return self


class CorridorScope(CorridorModel):
    """BD-D1: one frozen corridor — region, bbox polygon, and landmarks."""

    region: str = Field(min_length=1, max_length=80)
    corridor_name: str = Field(min_length=1, max_length=120)
    min_longitude: float = Field(ge=-180.0, le=180.0)
    min_latitude: float = Field(ge=-90.0, le=90.0)
    max_longitude: float = Field(ge=-180.0, le=180.0)
    max_latitude: float = Field(ge=-90.0, le=90.0)
    landmarks: tuple[CorridorLandmark, ...] = Field(min_length=_MINIMUM_LANDMARKS)
    decided_by: str = Field(min_length=1, max_length=300)
    decision_provenance: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_scope(self) -> CorridorScope:
        lowered = " ".join(
            (
                self.region.lower(),
                self.corridor_name.lower(),
                self.decided_by.lower(),
                self.decision_provenance.lower(),
            )
        )
        for literal in MANCHESTER_LITERALS:
            if literal.lower() in lowered:
                raise ValueError(
                    f"corridor scopes must not carry the Manchester literal '{literal}': "
                    "reusing the Manchester identity would create false provenance"
                )
        if not (self.min_longitude < self.max_longitude):
            raise ValueError("the corridor bbox must have min_longitude < max_longitude")
        if not (self.min_latitude < self.max_latitude):
            raise ValueError("the corridor bbox must have min_latitude < max_latitude")
        for landmark in self.landmarks:
            if not (
                self.min_longitude <= landmark.longitude <= self.max_longitude
                and self.min_latitude <= landmark.latitude <= self.max_latitude
            ):
                raise ValueError(
                    f"landmark '{landmark.name}' lies outside the frozen corridor bbox"
                )
        names = [landmark.name for landmark in self.landmarks]
        if len(set(names)) != len(names):
            raise ValueError("landmark names must be unique")
        _refuse_private_text(self.decision_provenance, "decision_provenance")
        return self

    def bbox_argument(self) -> str:
        return f"{self.min_longitude},{self.min_latitude},{self.max_longitude},{self.max_latitude}"


def load_corridor_scope(path: Path) -> CorridorScope:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorridorNetworkError(
            "SCOPE_UNREADABLE", f"corridor scope {path.name} could not be read"
        ) from exc
    try:
        return CorridorScope.model_validate_json(raw)
    except ValidationError as exc:
        raise CorridorNetworkError(
            "SCOPE_INVALID",
            f"corridor scope {path.name} failed validation: {exc.errors()[0]['msg']}",
        ) from exc


# --- extract identity --------------------------------------------------------


def verify_extract(path: Path, pin: ExtractPin) -> None:
    """Verify the on-disk extract against its pin; any drift refuses."""

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorridorNetworkError(
            "EXTRACT_UNREADABLE", f"extract {path.name} could not be read"
        ) from exc
    if len(raw) != pin.byte_size:
        raise CorridorNetworkError(
            "EXTRACT_CHECKSUM_DRIFT",
            f"extract {path.name} is {len(raw)} bytes but the pin records "
            f"{pin.byte_size}; the pinned identity does not match what is on disk",
        )
    digest = hashlib.sha256(raw).hexdigest()
    if digest != pin.sha256:
        raise CorridorNetworkError(
            "EXTRACT_CHECKSUM_DRIFT",
            f"extract {path.name} sha256 {digest[:12]}… does not match the pinned "
            f"{pin.sha256[:12]}…",
        )


# --- containment and bounded tools ------------------------------------------


def contained_destination(workspace_root: Path, relative: str) -> Path:
    """Resolve a destination inside the workspace; escapes refuse."""

    _refuse_destination_text(relative)
    root = workspace_root.resolve()
    destination = (root / relative).resolve()
    if root != destination and root not in destination.parents:
        raise CorridorNetworkError(
            "WORKSPACE_ESCAPE_REFUSED",
            f"destination '{relative}' resolves outside the declared workspace",
        )
    return destination


def _refuse_destination_text(relative: str) -> None:
    if Path(relative).is_absolute() or relative.startswith(("/", "\\")):
        raise CorridorNetworkError(
            "WORKSPACE_ESCAPE_REFUSED", "destinations must be workspace-relative"
        )
    for marker in _PRIVATE_PATH_MARKERS:
        if marker in relative:
            raise CorridorNetworkError(
                "WORKSPACE_ESCAPE_REFUSED", "destinations must not carry private path markers"
            )


def osmium_clip_arguments(scope: CorridorScope, source: Path, destination: Path) -> list[str]:
    """The exact bounded ``osmium extract`` argv — fixed executable, no shell."""

    return [
        _OSMIUM_EXECUTABLE,
        "extract",
        "--bbox",
        scope.bbox_argument(),
        "--set-bounds",
        "--overwrite",
        "-o",
        str(destination),
        str(source),
    ]


def osmium_export_arguments(source: Path, destination: Path) -> list[str]:
    """The exact bounded PBF→XML decode argv (netconvert reads XML only)."""

    return [
        _OSMIUM_EXECUTABLE,
        "cat",
        "--overwrite",
        "-o",
        str(destination),
        str(source),
    ]


def netconvert_arguments(source: Path, destination: Path) -> list[str]:
    """The exact bounded ``netconvert`` argv for a corridor build."""

    return [
        _NETCONVERT_EXECUTABLE,
        "--osm-files",
        str(source),
        "--output-file",
        str(destination),
        "--geometry.remove",
        "--remove-edges.isolated",
        "--junctions.join",
        "--tls.discard-simple",
    ]


# --- measured classification -------------------------------------------------


class LandmarkReconciliation(CorridorModel):
    """One landmark against the built network's own inverse projection."""

    name: str
    nearest_junction_distance_m: float = Field(ge=0.0)


class ExtentClassification(CorridorModel):
    """What was MEASURED about the built network's extent and containment."""

    proj_parameter: str
    net_offset: str
    conv_boundary: str
    network_min_longitude: float
    network_min_latitude: float
    network_max_longitude: float
    network_max_latitude: float
    requested_corridor_contained: bool
    landmark_reconciliation: tuple[LandmarkReconciliation, ...]
    landmark_tolerance_m: float


def haversine_m(
    longitude_a: float, latitude_a: float, longitude_b: float, latitude_b: float
) -> float:
    phi_a = math.radians(latitude_a)
    phi_b = math.radians(latitude_b)
    delta_phi = math.radians(latitude_b - latitude_a)
    delta_lambda = math.radians(longitude_b - longitude_a)
    inner = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi_a) * math.cos(phi_b) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * _EARTH_RADIUS_M * math.asin(math.sqrt(inner))


def classify_extent(
    scope: CorridorScope,
    *,
    proj_parameter: str,
    net_offset: str,
    conv_boundary: str,
    junctions_lonlat: Sequence[tuple[float, float]],
    landmark_tolerance_m: float = 150.0,
) -> ExtentClassification:
    """Measure containment and landmark distances; never assume either.

    ``junctions_lonlat`` are junction coordinates already inverse-projected
    through the network's OWN ``projParameter`` with ``netOffset`` removed —
    the Manchester lesson that ``origBoundary`` is the input bbox and only the
    network's own projection describes the real extent.
    """

    if not junctions_lonlat:
        raise CorridorNetworkError(
            "NETWORK_EMPTY", "no junction survived the build; there is no extent to measure"
        )
    lons = [lon for lon, _ in junctions_lonlat]
    lats = [lat for _, lat in junctions_lonlat]
    network_min_lon, network_max_lon = min(lons), max(lons)
    network_min_lat, network_max_lat = min(lats), max(lats)
    # Containment is measured against the LANDMARK HULL — the corridor as the
    # owner froze it — not the clip bbox: a clipped network never touches the
    # bbox corners, so bbox-superset would fail every honest build.
    landmark_min_lon = min(landmark.longitude for landmark in scope.landmarks)
    landmark_max_lon = max(landmark.longitude for landmark in scope.landmarks)
    landmark_min_lat = min(landmark.latitude for landmark in scope.landmarks)
    landmark_max_lat = max(landmark.latitude for landmark in scope.landmarks)
    contained = (
        network_min_lon <= landmark_min_lon
        and network_max_lon >= landmark_max_lon
        and network_min_lat <= landmark_min_lat
        and network_max_lat >= landmark_max_lat
    )
    reconciliation = []
    for landmark in scope.landmarks:
        nearest = min(
            haversine_m(landmark.longitude, landmark.latitude, lon, lat)
            for lon, lat in junctions_lonlat
        )
        reconciliation.append(
            LandmarkReconciliation(name=landmark.name, nearest_junction_distance_m=nearest)
        )
    return ExtentClassification(
        proj_parameter=proj_parameter,
        net_offset=net_offset,
        conv_boundary=conv_boundary,
        network_min_longitude=network_min_lon,
        network_min_latitude=network_min_lat,
        network_max_longitude=network_max_lon,
        network_max_latitude=network_max_lat,
        requested_corridor_contained=contained,
        landmark_reconciliation=tuple(reconciliation),
        landmark_tolerance_m=landmark_tolerance_m,
    )


# --- the receipt -------------------------------------------------------------


class NetworkStructure(CorridorModel):
    """Streaming-measured structural facts; comparison context only."""

    edge_count_total: int = Field(ge=0)
    edge_count_internal: int = Field(ge=0)
    edge_count_real: int = Field(ge=0)
    junction_count: int = Field(ge=0)
    no_shape_edge_share: float = Field(ge=0.0, le=1.0)


class CorridorBuildReceipt(CorridorModel):
    """The deterministic feasibility receipt; no private path, no claim creep."""

    schema_version: Literal["1.0"] = "1.0"
    method_version: Literal["corridor-network-build-1.0"] = METHOD_VERSION
    design_reference: Literal["docs/platform/dhaka_corridor_design.md"] = DESIGN_REFERENCE
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"
    role: Literal["corridor_network_candidate"] = "corridor_network_candidate"
    observation_status: Literal["unavailable"] = "unavailable"
    scope: CorridorScope
    extract_pin: ExtractPin
    extract_verified: bool
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_network_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_canonical_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    tool_versions: dict[str, str]
    stage_durations_seconds: dict[str, float]
    structure: NetworkStructure
    extent: ExtentClassification
    network_artifact_name: str
    feasibility_gaps: tuple[str, ...]
    accepted: bool
    excluded_claims: tuple[str, ...] = EXCLUDED_CLAIMS
    licence: Literal["ODbL-1.0"] = OSM_LICENCE
    attribution: Literal["© OpenStreetMap contributors, ODbL 1.0"] = OSM_ATTRIBUTION
    generated_at_utc: str

    @model_validator(mode="after")
    def validate_receipt(self) -> CorridorBuildReceipt:
        if self.source_sha256 == self.derived_network_sha256:
            raise ValueError(
                "source and derived identities must differ; a build that returns its "
                "input is recording the wrong artifact"
            )
        for field_name, value in (
            ("network_artifact_name", self.network_artifact_name),
            *((f"tool_versions[{key}]", text) for key, text in self.tool_versions.items()),
        ):
            _refuse_private_text(value, field_name)
        if Path(self.network_artifact_name).is_absolute():
            raise ValueError("the receipt records the artifact's name, never its absolute path")
        if self.accepted and self.feasibility_gaps:
            raise ValueError("an accepted receipt cannot carry feasibility gaps")
        return self


def assess_feasibility(
    structure: NetworkStructure, extent: ExtentClassification
) -> tuple[str, ...]:
    """The typed feasibility-gap list; empty means the build is acceptable."""

    gaps: list[str] = []
    if structure.edge_count_real == 0:
        gaps.append("NETWORK_EMPTY: no real (non-internal) edge survived the build")
    if not extent.requested_corridor_contained:
        gaps.append(
            "CORRIDOR_NOT_CONTAINED: the built extent does not contain the frozen "
            "corridor bbox — measured, not assumed"
        )
    for row in extent.landmark_reconciliation:
        if row.nearest_junction_distance_m > extent.landmark_tolerance_m:
            gaps.append(
                f"LANDMARK_UNRECONCILED: '{row.name}' is "
                f"{row.nearest_junction_distance_m:.0f} m from the nearest junction "
                f"(tolerance {extent.landmark_tolerance_m:.0f} m) — projection or "
                "coverage must be reviewed"
            )
    return tuple(gaps)


def receipt_to_json(receipt: CorridorBuildReceipt) -> str:
    return json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True, allow_nan=False)


def canonical_network_identity(path: Path) -> str:
    """Digest with XML comment BLOCKS stripped — the netconvert-banner lesson.

    ``netconvert`` embeds a timestamped banner (and absolute input paths) in
    a MULTI-LINE XML comment, so raw bytes differ across identical builds and
    carry private paths; identity is the digest of every line outside a
    comment block. A single-line matcher missed the block entirely — caught
    on the first real Dhaka build when canonical equalled the raw digest.
    """

    digest = hashlib.sha256()
    inside_comment = False
    with path.open("rb") as handle:
        for line in handle:
            stripped = line.strip()
            if inside_comment:
                if b"-->" in stripped:
                    inside_comment = False
                continue
            if stripped.startswith(b"<!--"):
                if b"-->" not in stripped:
                    inside_comment = True
                continue
            digest.update(line)
    return digest.hexdigest()

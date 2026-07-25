"""Real directed edge geometry read from an accepted baseline SUMO network.

This is a **prerequisite for** design Gate-D step 2 (site-to-edge map-match
candidates), not that step itself.  Matching an observation to a road needs the
road's geometry; nothing in the repository could read it.  The lead's
:mod:`~traffictwin.integration.manchester.map_matching` harness models only
``SyntheticSumoEdgeGeometry`` — capped at 64 coordinates and fixed
``synthetic: Literal[True]`` — so it cannot describe a real 804,611-edge network.
This module fills exactly that gap and stops there.

What this module deliberately does **not** do:

*   It chooses **no threshold**.  Open question 6 ("which map-matching distance,
    direction, road-class, and confidence rules are scientifically acceptable")
    is unanswered, so no snap radius, bearing tolerance, road-class rule,
    confidence category, or acceptance criterion is defined here — not even as a
    default.  :func:`real_match_candidates` fails closed on
    ``MAP_MATCH_POLICY_UNAPPROVED`` until that decision exists.
*   It selects nothing and ranks nothing.  Reading geometry is not matching.
*   It filters no road class.  Which classes may carry a motor-traffic count is
    a scientific decision, so the reader stays complete and neutral and records
    the class it observed.

Two measured properties of a real network drive the design, both established on
the accepted Greater Manchester build rather than assumed:

1.  **Most edges are not roads.**  Of 2,106,404 ``<edge>`` elements, 1,301,793
    are junction-internal connector edges and only 804,611 are real road edges.
    Internal edges are excluded and counted, never silently dropped.
2.  **36% of real edges carry no shape.**  288,151 real edges have no ``shape``
    attribute; SUMO leaves their geometry implied by their two junctions.  Those
    can only be reconstructed as a **straight line**, which is not the true road
    shape.  Distance-based matching is sensitive to that difference, so every
    edge records which source produced its geometry and the two are never
    averaged into one fidelity claim.

Coordinates are projected back through the network's *own* ``projParameter``
after removing its ``netOffset``, exactly as :mod:`network_build` derives the
network extent.  TrafficTwin never assumes a projection.  The convention
(``utm = network − netOffset``) was validated against four independent
Manchester landmarks, each resolving to a junction 11–33 m away.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError

from traffictwin.integration.manchester.models import ManchesterSnapshotModel, sha256_hex
from traffictwin.integration.manchester.network_build import (
    SumoNetworkLocation,
    read_network_prefix,
)
from traffictwin.integration.manchester.network_scope import GeographicPoint

NETWORK_GEOMETRY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NETWORK_GEOMETRY_METHOD_VERSION: Literal["manchester-network-geometry-1.0"] = (
    "manchester-network-geometry-1.0"
)
NETWORK_GEOMETRY_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

#: Junction-internal edges carry this id prefix and/or ``function="internal"``.
#: They are connectors inside an intersection, not roads, and an observation can
#: never legitimately be attributed to one.
INTERNAL_EDGE_PREFIX = b":"

#: Bound on one edge's shape.  The largest observed on the Greater Manchester
#: network is 187 points; this leaves headroom while staying finite.
MAX_SHAPE_POINTS = 512

#: Bound on the junction table so a malformed or hostile file cannot exhaust
#: memory.  The accepted network holds 468,442.
MAX_JUNCTIONS = 5_000_000

#: Bound on the edge population for the same reason.
MAX_EDGES = 10_000_000

#: Bound on one line, so a file that is not line-oriented refuses instead of
#: being read into memory.  The longest line measured in the 1.25 GB Greater
#: Manchester network is 5,331 bytes.
MAX_LINE_BYTES = 1_000_000

_TARGET_CRS = "EPSG:4326"
_COORDINATE_QUANTUM = Decimal("0.000001")

_EDGE_ELEMENT = re.compile(rb"<edge id=\"([^\"]+)\"([^>]*)>")
_JUNCTION_ELEMENT = re.compile(
    rb"<junction id=\"([^\"]+)\"[^>]*?\bx=\"([-0-9.eE]+)\" y=\"([-0-9.eE]+)\""
)
_ATTRIBUTE = re.compile(rb"(\w+)=\"([^\"]*)\"")
_LOCATION_ELEMENT = re.compile(rb"<location\b[^>]*/>")

#: ``ref`` is the signed road number (``A6``, ``B5461``).  It is read because it
#: exists in the data, never because a rule was invented for using it.
_EDGE_REF_PARAM = re.compile(rb"<param key=\"ref\" value=\"([^\"]*)\"/>")

GeometrySource: TypeAlias = Literal["explicit_edge_shape", "junction_endpoints"]

#: A plain, model-free edge record for the bulk path.  804,611 strict models
#: with 2.2 million quantised coordinates would cost far more than the work
#: itself; strict models are built at the evidence boundary, for the small
#: number of edges an analyst actually reviews.
RawEdge: TypeAlias = tuple[str, str, str, str | None, str | None, GeometrySource, tuple[float, ...]]


class NetworkGeometryError(ValueError):
    """Typed refusal for unreadable or inconsistent network geometry."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NetworkGeometryModel(ManchesterSnapshotModel):
    """Strict frozen base for real network-geometry artifacts."""


class RealNetworkEdge(NetworkGeometryModel):
    """One real directed road edge with its geometry provenance recorded.

    This is deliberately a different type from the lead's
    ``SyntheticSumoEdgeGeometry``.  That model fixes ``synthetic: Literal[True]``
    and a 64-coordinate cap; conflating the two would let synthetic fixture
    geometry and real network geometry be mistaken for each other.
    """

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-network-geometry-1.0"] = NETWORK_GEOMETRY_METHOD_VERSION
    edge_id: str = Field(min_length=1, max_length=200)
    from_junction: str = Field(min_length=1, max_length=200)
    to_junction: str = Field(min_length=1, max_length=200)
    #: The network's own ``type`` (``highway.secondary``).  Recorded, not judged.
    road_type: str | None = Field(default=None, max_length=100)
    #: The signed road number from ``<param key="ref">`` when present.
    road_ref: str | None = Field(default=None, max_length=100)
    shape: tuple[GeographicPoint, ...] = Field(min_length=2, max_length=MAX_SHAPE_POINTS)
    geometry_source: GeometrySource
    #: A straight line between two junctions is not the true road shape.
    geometry_is_true_road_shape: bool
    directed: Literal[True] = True
    coordinate_reference_system: Literal["EPSG:4326"] = "EPSG:4326"
    synthetic: Literal[False] = False
    #: Reading geometry is not matching, and matching is not acceptance.
    reviewed_for_matching: Literal[False] = False
    matched_to_observation: Literal[False] = False

    @model_validator(mode="after")
    def validate_edge(self) -> RealNetworkEdge:
        expected = self.geometry_source == "explicit_edge_shape"
        if self.geometry_is_true_road_shape != expected:
            raise ValueError("geometry fidelity must follow from the recorded geometry source")
        if self.geometry_source == "junction_endpoints" and len(self.shape) != 2:
            raise ValueError("junction-derived geometry is exactly two endpoints")
        return self


class EdgeGeometrySummary(NetworkGeometryModel):
    """Counts over one network's edge population, with fidelity kept separate."""

    schema_version: Literal["1.0"] = "1.0"
    total_edge_elements: int = Field(ge=0)
    internal_edges_excluded: int = Field(ge=0)
    real_edges: int = Field(ge=0)
    #: Real geometry read straight from the network.
    edges_with_explicit_shape: int = Field(ge=0)
    #: Straight lines reconstructed from two junctions: lower fidelity.
    edges_from_junction_endpoints: int = Field(ge=0)
    #: Real edges whose geometry could not be established at all.
    edges_unresolvable: int = Field(ge=0)
    shape_points_total: int = Field(ge=0)
    max_shape_points: int = Field(ge=0)
    junctions_available: int = Field(ge=0)
    #: Guards against a summary that quietly reports a fidelity average.
    fidelity_reported_separately: Literal[True] = True

    @model_validator(mode="after")
    def validate_summary(self) -> EdgeGeometrySummary:
        if self.internal_edges_excluded + self.real_edges != self.total_edge_elements:
            raise ValueError("internal and real edges must account for every edge element")
        resolved = self.edges_with_explicit_shape + self.edges_from_junction_endpoints
        if resolved + self.edges_unresolvable != self.real_edges:
            raise ValueError("every real edge must be resolved, derived, or counted unresolvable")
        return self

    @property
    def true_shape_fraction(self) -> Decimal:
        """Share of real edges whose geometry is the actual road shape."""

        if self.real_edges == 0:
            return Decimal("0")
        return Decimal(self.edges_with_explicit_shape) / Decimal(self.real_edges)


def read_network_location(path: str | Path) -> SumoNetworkLocation:
    """Read the network's own projection metadata from its bounded prefix."""

    prefix = read_network_prefix(path)
    match = _LOCATION_ELEMENT.search(prefix)
    if match is None:
        raise NetworkGeometryError(
            "NETWORK_LOCATION_UNREADABLE",
            "the network declares no <location> element, so its projection is unknown",
        )
    attributes = {
        key.decode("ascii"): value.decode("utf-8", "replace")
        for key, value in _ATTRIBUTE.findall(match.group(0))
    }
    required = ("netOffset", "convBoundary", "origBoundary", "projParameter")
    if any(name not in attributes for name in required):
        raise NetworkGeometryError(
            "NETWORK_LOCATION_INCOMPLETE",
            "the network's <location> element is missing a required attribute",
        )
    return SumoNetworkLocation(
        net_offset=attributes["netOffset"],
        conv_boundary=attributes["convBoundary"],
        orig_boundary=attributes["origBoundary"],
        proj_parameter=attributes["projParameter"],
    )


def _network_transformer(location: SumoNetworkLocation) -> tuple[Transformer, float, float]:
    """Build the network's own inverse projection and its offset.

    ``netconvert`` writes ``network = utm + netOffset``, so the offset is
    *removed* before projecting back.  Validated against four Manchester
    landmarks; getting the sign wrong puts the network thousands of kilometres
    away, which is silent rather than loud.
    """

    parts = location.net_offset.split(",")
    if len(parts) != 2:
        raise NetworkGeometryError("NETWORK_OFFSET_UNREADABLE", "netOffset must be an x,y pair")
    try:
        offset_x, offset_y = (float(value) for value in parts)
    except ValueError as exc:
        raise NetworkGeometryError(
            "NETWORK_OFFSET_UNREADABLE", "netOffset must be a numeric x,y pair"
        ) from exc
    try:
        transformer = Transformer.from_crs(
            CRS.from_proj4(location.proj_parameter), _TARGET_CRS, always_xy=True
        )
    except (CRSError, ProjError, ValueError) as exc:
        raise NetworkGeometryError(
            "NETWORK_PROJECTION_UNSUPPORTED",
            "the network's own projParameter could not be interpreted",
        ) from exc
    return transformer, offset_x, offset_y


def _iter_lines(path: Path) -> Iterator[bytes]:
    """Stream a network line by line, refusing any implausibly long line.

    ``netconvert`` writes one element per line: every ``<edge id=...>`` and
    ``<junction id=.../>`` opening tag is complete on a single line.  Iterating
    lines is therefore both correct and inherently memory-bounded — the measured
    longest line in the 1.25 GB Greater Manchester network is 5,331 bytes.

    An earlier chunk-and-carry scanner was replaced here after measurement: once
    the scan passed the final anchor, its carry grew without bound and peak RSS
    reached 7.8 GB on that same network.  A bound that only holds while the
    anchor keeps reappearing is not a bound.
    """

    with path.open("rb") as handle:
        for line in handle:
            if len(line) > MAX_LINE_BYTES:
                raise NetworkGeometryError(
                    "NETWORK_LINE_UNBOUNDED",
                    "the network contains a line longer than the reviewed bound admits",
                )
            yield line


def read_junction_coordinates(path: str | Path) -> dict[bytes, tuple[float, float]]:
    """Collect every junction's network-coordinate position.

    Needed because 36% of real edges carry no shape of their own.  Bounded by
    :data:`MAX_JUNCTIONS` so a malformed file cannot exhaust memory.
    """

    junctions: dict[bytes, tuple[float, float]] = {}
    for line in _iter_lines(Path(path)):
        if b"<junction " not in line:
            continue
        match = _JUNCTION_ELEMENT.search(line)
        if match is None:
            continue
        if len(junctions) >= MAX_JUNCTIONS:
            raise NetworkGeometryError(
                "NETWORK_JUNCTIONS_UNBOUNDED",
                "the network declares more junctions than the reviewed bound admits",
            )
        try:
            junctions[match.group(1)] = (float(match.group(2)), float(match.group(3)))
        except ValueError:
            continue
    return junctions


def stream_raw_edges(
    path: str | Path,
    *,
    location: SumoNetworkLocation | None = None,
    junctions: dict[bytes, tuple[float, float]] | None = None,
) -> Iterator[RawEdge]:
    """Stream every real road edge with WGS84 geometry and its provenance.

    Yields plain tuples rather than models: at 804,611 edges and 2.2 million
    coordinates the model construction would dominate. Internal edges are
    skipped here and counted by :func:`summarise_edge_geometry`.
    """

    source = Path(path)
    resolved_location = location if location is not None else read_network_location(source)
    transformer, offset_x, offset_y = _network_transformer(resolved_location)
    table = junctions if junctions is not None else read_junction_coordinates(source)
    emitted = 0

    for emitted, (edge_id, attributes, ref) in enumerate(_iter_edge_elements(source), start=1):
        if emitted > MAX_EDGES:
            raise NetworkGeometryError(
                "NETWORK_EDGES_UNBOUNDED",
                "the network declares more edges than the reviewed bound admits",
            )
        record = _build_raw_edge(
            edge_id=edge_id,
            attributes=attributes,
            road_ref=ref,
            transformer=transformer,
            offset_x=offset_x,
            offset_y=offset_y,
            junctions=table,
        )
        if record is not None:
            yield record


def _iter_edge_elements(path: Path) -> Iterator[tuple[bytes, bytes, bytes | None]]:
    """Yield each real edge's id, attributes, and road ref.

    The signed road number lives in a ``<param key="ref">`` child line, so the
    opening tag is held until the element closes.  Internal edges are skipped.
    """

    pending_id: bytes | None = None
    pending_attributes = b""
    pending_ref: bytes | None = None

    for line in _iter_lines(path):
        if b"<edge " in line:
            if pending_id is not None:
                yield pending_id, pending_attributes, pending_ref
                pending_id = None
            match = _EDGE_ELEMENT.search(line)
            if match is None:
                continue
            edge_id, attributes = match.group(1), match.group(2)
            if edge_id.startswith(INTERNAL_EDGE_PREFIX) or b'function="internal"' in attributes:
                continue
            if line.rstrip().endswith(b"/>"):
                yield edge_id, attributes, None
                continue
            pending_id, pending_attributes, pending_ref = edge_id, attributes, None
        elif pending_id is not None:
            if b"</edge>" in line:
                yield pending_id, pending_attributes, pending_ref
                pending_id = None
            elif pending_ref is None and b'key="ref"' in line:
                ref_match = _EDGE_REF_PARAM.search(line)
                if ref_match is not None:
                    pending_ref = ref_match.group(1)
    if pending_id is not None:
        yield pending_id, pending_attributes, pending_ref


def _build_raw_edge(
    *,
    edge_id: bytes,
    attributes: bytes,
    road_ref: bytes | None,
    transformer: Transformer,
    offset_x: float,
    offset_y: float,
    junctions: dict[bytes, tuple[float, float]],
) -> RawEdge | None:
    """Resolve one edge's geometry, or ``None`` when it cannot be established."""

    parsed = dict(_ATTRIBUTE.findall(attributes))
    from_junction = parsed.get(b"from")
    to_junction = parsed.get(b"to")
    if from_junction is None or to_junction is None:
        return None

    raw_shape = parsed.get(b"shape")
    source: GeometrySource
    if raw_shape:
        points = _parse_shape(raw_shape)
        source = "explicit_edge_shape"
    else:
        start = junctions.get(from_junction)
        end = junctions.get(to_junction)
        if start is None or end is None or start == end:
            return None
        points = [start, end]
        source = "junction_endpoints"
    if len(points) < 2 or len(points) > MAX_SHAPE_POINTS:
        return None

    flat: list[float] = []
    for x, y in points:
        try:
            longitude, latitude = transformer.transform(x - offset_x, y - offset_y)
        except (ProjError, ValueError):
            return None
        if not (-180.0 <= longitude <= 180.0 and -90.0 <= latitude <= 90.0):
            return None
        flat.extend((longitude, latitude))

    road_type = parsed.get(b"type")
    return (
        edge_id.decode("utf-8", "replace"),
        from_junction.decode("utf-8", "replace"),
        to_junction.decode("utf-8", "replace"),
        road_type.decode("utf-8", "replace") if road_type else None,
        road_ref.decode("utf-8", "replace") if road_ref else None,
        source,
        tuple(flat),
    )


def _parse_shape(raw: bytes) -> list[tuple[float, float]]:
    """Parse a SUMO ``shape`` attribute into network-coordinate pairs."""

    points: list[tuple[float, float]] = []
    for token in raw.split(b" "):
        if not token:
            continue
        parts = token.split(b",")
        if len(parts) < 2:
            return []
        try:
            points.append((float(parts[0]), float(parts[1])))
        except ValueError:
            return []
        if len(points) > MAX_SHAPE_POINTS:
            return []
    return points


def to_real_network_edge(record: RawEdge) -> RealNetworkEdge:
    """Promote one bulk record to a strict evidence-boundary model."""

    edge_id, from_junction, to_junction, road_type, road_ref, source, flat = record
    shape = tuple(
        GeographicPoint(
            longitude=Decimal(repr(flat[index])).quantize(_COORDINATE_QUANTUM),
            latitude=Decimal(repr(flat[index + 1])).quantize(_COORDINATE_QUANTUM),
        )
        for index in range(0, len(flat), 2)
    )
    return RealNetworkEdge(
        edge_id=edge_id,
        from_junction=from_junction,
        to_junction=to_junction,
        road_type=road_type,
        road_ref=road_ref,
        shape=shape,
        geometry_source=source,
        geometry_is_true_road_shape=source == "explicit_edge_shape",
    )


def summarise_edge_geometry(path: str | Path) -> EdgeGeometrySummary:
    """Count the edge population without materialising it.

    Internal edges, explicit shapes, junction-derived straight lines, and
    unresolvable edges are counted separately so no fidelity claim is averaged.
    """

    source = Path(path)
    location = read_network_location(source)
    transformer, offset_x, offset_y = _network_transformer(location)
    junctions = read_junction_coordinates(source)

    total = internal = real = explicit = derived = unresolvable = 0
    shape_points = 0
    max_points = 0

    for line in _iter_lines(source):
        if b"<edge " not in line:
            continue
        match = _EDGE_ELEMENT.search(line)
        if match is None:
            continue
        total += 1
        edge_id, attributes = match.group(1), match.group(2)
        if edge_id.startswith(INTERNAL_EDGE_PREFIX) or b'function="internal"' in attributes:
            internal += 1
            continue
        real += 1
        record = _build_raw_edge(
            edge_id=edge_id,
            attributes=attributes,
            road_ref=None,
            transformer=transformer,
            offset_x=offset_x,
            offset_y=offset_y,
            junctions=junctions,
        )
        if record is None:
            unresolvable += 1
            continue
        if record[5] == "explicit_edge_shape":
            explicit += 1
        else:
            derived += 1
        count = len(record[6]) // 2
        shape_points += count
        max_points = max(max_points, count)

    return EdgeGeometrySummary(
        total_edge_elements=total,
        internal_edges_excluded=internal,
        real_edges=real,
        edges_with_explicit_shape=explicit,
        edges_from_junction_endpoints=derived,
        edges_unresolvable=unresolvable,
        shape_points_total=shape_points,
        max_shape_points=max_points,
        junctions_available=len(junctions),
    )


def geometry_fingerprint(summary: EdgeGeometrySummary, network_identity_sha256: str) -> str:
    """Bind a geometry reading to the exact network identity it came from."""

    return sha256_hex(f"{network_identity_sha256}:{summary.canonical_json()}".encode())

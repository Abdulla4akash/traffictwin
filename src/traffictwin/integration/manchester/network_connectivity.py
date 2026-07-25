"""Motor-eligible connectivity and bounded routability review of a baseline network.

This is a **review** of an already-accepted baseline network (ADR-059/060), not a
new scientific decision.  It answers one question a demand model cannot avoid:
*which parts of this network can a motor vehicle actually reach?*  Nothing here
matches, calibrates, or accepts anything.

Three measured properties of the real network drive the design.  Each was
established on the accepted Greater Manchester build, not assumed.

1.  **Permissions are always explicit.**  Of 2,157,380 ``<lane>`` elements, every
    one carries exactly one of ``allow`` or ``disallow`` — never both, never
    neither.  The fallbacks below therefore never fire on this network; they
    exist so a differently built network refuses to be misread rather than being
    silently treated as open or closed.

2.  **"Permits a motor vehicle" and "permits a car" are different networks.**
    ``netconvert`` 1.27.1 builds ``highway.service`` with
    ``allow="pedestrian delivery bicycle"``: 126,991 service lanes admit a
    delivery van and exclude a private car.  Collapsing the two would overstate
    the drivable network by every driveway, alley, and parking aisle in Greater
    Manchester.  Both subgraphs are therefore computed and both are published;
    the reader chooses, and the difference stays visible rather than implied.

3.  **Most edges are not roads.**  1,301,793 of 2,106,404 ``<edge>`` elements are
    junction-internal connectors.  They are excluded and counted, exactly as
    :mod:`network_geometry` excludes them, never silently dropped.

**Bounded probes do not prove universal routability.**  A probe that succeeds
proves one origin reached one destination.  It does not prove every origin
reaches every destination, and no number of probes can: that claim needs the
complete pairwise reachability of a 468,442-junction graph.  The report carries
the refusal structurally in
:attr:`ManchesterNetworkConnectivityReport.proves_universal_routability`, not
only in prose, so a consumer cannot read past it.

Every summary is bound to the exact ``network_identity_sha256`` it was computed
from, so a connectivity claim can never drift onto a different network.
"""

from __future__ import annotations

from array import array
from collections.abc import Iterator, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Literal, NamedTuple, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import ManchesterSnapshotModel
from traffictwin.integration.manchester.network_build import (
    ManchesterBaselineNetworkBinding,
    load_binding,
)
from traffictwin.integration.manchester.network_geometry import (
    INTERNAL_EDGE_PREFIX,
    MAX_EDGES,
    MAX_JUNCTIONS,
    MAX_LINE_BYTES,
)

NETWORK_CONNECTIVITY_SCHEMA_VERSION: Literal["1.0"] = "1.0"
NETWORK_CONNECTIVITY_METHOD_VERSION: Literal["manchester-network-connectivity-1.0"] = (
    "manchester-network-connectivity-1.0"
)
NETWORK_CONNECTIVITY_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

#: SUMO vehicle classes that are road motor vehicles.  ``custom1``/``custom2``
#: are deliberately **absent**: they are unnamed placeholders with no defined
#: meaning, so admitting an edge on their evidence alone would be a guess.  The
#: exclusion is published in the report rather than left implicit.
MOTOR_VEHICLE_CLASSES: frozenset[str] = frozenset(
    {
        "private",
        "emergency",
        "authority",
        "army",
        "vip",
        "passenger",
        "hov",
        "taxi",
        "bus",
        "coach",
        "delivery",
        "truck",
        "trailer",
        "motorcycle",
        "moped",
        "evehicle",
    }
)

#: Classes named in the network that carry no defined motor meaning.
UNDEFINED_VEHICLE_CLASSES: frozenset[str] = frozenset({"custom1", "custom2"})

#: The private car.  This single class separates a drivable road from a
#: delivery-only service way, which is why it is named rather than inferred.
PASSENGER_CAR_CLASS: Literal["passenger"] = "passenger"

_INTERNAL_PREFIX = INTERNAL_EDGE_PREFIX.decode("ascii")

MotorAccess: TypeAlias = Literal[
    "passenger_car",
    "motor_vehicle_no_car",
    "no_motor_vehicle",
    "permissions_unreadable",
]

#: Which subgraph a summary describes.  Both are published; neither is "the"
#: motor network, because the network itself does not make that choice.
Eligibility: TypeAlias = Literal["any_motor_vehicle", "passenger_car"]

ELIGIBILITIES: tuple[Eligibility, ...] = ("any_motor_vehicle", "passenger_car")

ComponentKind: TypeAlias = Literal["weak", "strong"]

COMPONENT_KINDS: tuple[ComponentKind, ...] = ("weak", "strong")

ProbeOutcome: TypeAlias = Literal[
    "routed",
    "unreachable",
    "probe_limit_reached",
    "endpoint_not_eligible",
]

#: How a probe pair was chosen.  Recorded because a probe set drawn only from
#: the dominant component would succeed every time and read as evidence that
#: the network is routable.  ``largest_to_fragment`` pairs deliberately target
#: components outside the largest one, so the probe set demonstrates that it
#: can detect unreachability instead of only ever confirming success.
ProbeSelection: TypeAlias = Literal["deterministic_spread", "largest_to_fragment"]

#: Bounds.  A malformed or hostile network must refuse rather than exhaust
#: memory, and a review must terminate.
MAX_LISTED_COMPONENTS = 50
MAX_LISTED_EXAMPLE_EDGES = 5
MAX_ROUTE_PROBES = 200
DEFAULT_ROUTE_PROBES = 32
#: Probes aimed deliberately outside the largest component.
DEFAULT_CONTRAST_PROBES = 8
MAX_PROBE_EXPANSION = 2_000_000
DEFAULT_PROBE_EXPANSION = 400_000

#: A component this small is an isolated fragment by inspection, not a network.
ISOLATED_COMPONENT_MAX_EDGES = 4

_SHARE_QUANTUM = Decimal("0.000001")


class StreamedEdge(NamedTuple):
    """One ``<edge>`` element as read, including the ones that cannot be used.

    Junction-internal elements and edges missing an endpoint are **yielded and
    flagged**, never skipped inside the reader.  A reader that silently drops
    them forces every later count to be recovered by subtraction, and a
    subtracted count cannot distinguish an internal connector from a malformed
    road.  Yielding them keeps the accounting additive and auditable.
    """

    edge_id: str
    from_junction: str | None
    to_junction: str | None
    road_type: str | None
    access: MotorAccess
    length_m: float
    internal: bool
    lane_count: int


class NetworkConnectivityError(ValueError):
    """Typed refusal for an unreadable or unreviewable network."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class NetworkConnectivityModel(ManchesterSnapshotModel):
    """Strict frozen base for connectivity-review artifacts."""


def classify_lane_access(allow: str | None, disallow: str | None) -> MotorAccess:
    """Classify one lane's motor-vehicle access from its permission attributes.

    SUMO writes ``allow`` (a closed permit list) or ``disallow`` (a deny list
    over everything else), never both.  A lane carrying neither permits every
    class.  A lane carrying **both** is contradictory and is reported unreadable
    rather than resolved by preferring one of them, because preferring one would
    be an invented rule about a network the author did not build.
    """

    if allow is not None and disallow is not None:
        return "permissions_unreadable"
    if allow is not None:
        permitted = {token for token in allow.split() if token}
        if PASSENGER_CAR_CLASS in permitted:
            return "passenger_car"
        return "motor_vehicle_no_car" if permitted & MOTOR_VEHICLE_CLASSES else "no_motor_vehicle"
    denied = {token for token in disallow.split() if token} if disallow is not None else set()
    if PASSENGER_CAR_CLASS not in denied:
        return "passenger_car"
    return "motor_vehicle_no_car" if MOTOR_VEHICLE_CLASSES - denied else "no_motor_vehicle"


def combine_lane_access(levels: Sequence[MotorAccess]) -> MotorAccess:
    """Reduce an edge's lanes to the best access any single lane offers.

    An edge is drivable when *some* lane admits the vehicle: a bus lane beside a
    general lane does not close the road.  An unreadable lane never upgrades an
    edge, and an edge with no lanes at all stays unreadable rather than being
    assumed open.
    """

    if not levels:
        return "permissions_unreadable"
    if "passenger_car" in levels:
        return "passenger_car"
    if "motor_vehicle_no_car" in levels:
        return "motor_vehicle_no_car"
    if "no_motor_vehicle" in levels:
        return "no_motor_vehicle"
    return "permissions_unreadable"


def _iter_bounded_lines(path: Path) -> Iterator[bytes]:
    """Stream a network line by line, refusing any implausibly long line.

    ``netconvert`` writes one element per line, so line iteration is both
    correct and inherently memory-bounded.  The bound is the one
    :mod:`network_geometry` already reviewed; the refusal is typed to this
    module so a connectivity failure never surfaces as a geometry failure.
    """

    with path.open("rb") as handle:
        for line in handle:
            if len(line) > MAX_LINE_BYTES:
                raise NetworkConnectivityError(
                    "NETWORK_LINE_UNBOUNDED",
                    "the network contains a line longer than the reviewed bound admits",
                )
            yield line


def _attribute(line: bytes, name: bytes) -> str | None:
    """Read one XML attribute value from a single element line."""

    marker = b" " + name + b'="'
    start = line.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = line.find(b'"', start)
    if end < 0:
        return None
    return line[start:end].decode("utf-8", "replace")


def stream_network_edges(path: str | Path) -> Iterator[StreamedEdge]:
    """Stream every ``<edge>`` element with its topology, access, and length.

    Deliberately independent of :func:`network_geometry.stream_raw_edges`: that
    reader projects all 2.2 million coordinates through ``pyproj`` because
    matching needs metres, and connectivity needs none of it.  Reading topology
    and permissions only keeps a full-network review to one linear pass.

    Internal connectors are yielded with ``internal=True`` rather than being
    filtered out here, so the caller can count them directly instead of
    recovering them by subtracting from a total it did not measure.
    """

    source = Path(path)
    pending: StreamedEdge | None = None
    pending_levels: list[MotorAccess] = []
    pending_length = 0.0
    emitted = 0

    def _finalise(edge: StreamedEdge) -> StreamedEdge:
        return edge._replace(
            access=combine_lane_access(pending_levels),
            length_m=pending_length,
            lane_count=len(pending_levels),
        )

    for line in _iter_bounded_lines(source):
        if b"<edge " in line:
            if pending is not None:
                yield _finalise(pending)
            pending = None
            pending_levels = []
            pending_length = 0.0
            emitted += 1
            if emitted > MAX_EDGES:
                raise NetworkConnectivityError(
                    "NETWORK_EDGES_UNBOUNDED",
                    "the network declares more edges than the reviewed bound admits",
                )
            edge_id = _attribute(line, b"id")
            if edge_id is None:
                # An element with no id cannot be audited by identity, so it
                # cannot be excluded honestly either: calling it internal would
                # claim to know what it is. Fail closed instead.
                raise NetworkConnectivityError(
                    "NETWORK_EDGE_ID_MISSING",
                    "an <edge> element declares no id, so it can be neither "
                    "identified nor excluded by identity and no connectivity "
                    "claim is made from this network",
                )
            if edge_id.startswith(_INTERNAL_PREFIX) or b'function="internal"' in line:
                yield StreamedEdge(
                    edge_id, None, None, None, "permissions_unreadable", 0.0, True, 0
                )
                continue
            pending = StreamedEdge(
                edge_id,
                _attribute(line, b"from"),
                _attribute(line, b"to"),
                _attribute(line, b"type"),
                "permissions_unreadable",
                0.0,
                False,
                0,
            )
        elif pending is not None and b"<lane " in line:
            pending_levels.append(
                classify_lane_access(_attribute(line, b"allow"), _attribute(line, b"disallow"))
            )
            raw_length = _attribute(line, b"length")
            if raw_length is not None:
                try:
                    pending_length = max(pending_length, float(raw_length))
                except ValueError:
                    continue

    if pending is not None:
        yield _finalise(pending)


_ACCESS_CODES: dict[MotorAccess, int] = {
    "passenger_car": 0,
    "motor_vehicle_no_car": 1,
    "no_motor_vehicle": 2,
    "permissions_unreadable": 3,
}
_ACCESS_NAMES: tuple[MotorAccess, ...] = (
    "passenger_car",
    "motor_vehicle_no_car",
    "no_motor_vehicle",
    "permissions_unreadable",
)


class MotorNetworkGraph:
    """Directed junction graph over real road edges, with access per edge.

    A plain data structure rather than a frozen model: it holds hundreds of
    thousands of edges and exists to make a graph question answerable, not to be
    published.  The published artifact is
    :class:`ManchesterNetworkConnectivityReport`.

    Junction identifiers are interned to integers in first-seen order.  That
    order is an implementation detail and never reaches the report: components
    are ranked canonically before they are described, so one network always
    produces one summary.
    """

    __slots__ = (
        "_access",
        "_edge_ids",
        "_from",
        "_junction_ids",
        "_junction_index",
        "_length",
        "_road_type_index",
        "_road_type_of",
        "_road_types",
        "_to",
        "dangling_edges_excluded",
        "internal_edges_excluded",
        "no_lane_edges",
        "real_edges_read",
        "self_loop_edges",
        "total_edge_elements_read",
    )

    def __init__(self) -> None:
        self._junction_index: dict[str, int] = {}
        self._junction_ids: list[str] = []
        self._edge_ids: list[str] = []
        self._from = array("i")
        self._to = array("i")
        self._length = array("f")
        self._access = array("b")
        self._road_types: list[str | None] = []
        self._road_type_index: dict[str | None, int] = {}
        self._road_type_of = array("i")
        self.total_edge_elements_read = 0
        self.internal_edges_excluded = 0
        self.real_edges_read = 0
        self.dangling_edges_excluded = 0
        self.no_lane_edges = 0
        self.self_loop_edges = 0

    def __len__(self) -> int:
        return len(self._edge_ids)

    @property
    def junction_count(self) -> int:
        return len(self._junction_ids)

    def _intern(self, junction_id: str) -> int:
        ordinal = self._junction_index.get(junction_id)
        if ordinal is None:
            if len(self._junction_ids) >= MAX_JUNCTIONS:
                raise NetworkConnectivityError(
                    "NETWORK_JUNCTIONS_UNBOUNDED",
                    "the network declares more junctions than the reviewed bound admits",
                )
            ordinal = len(self._junction_ids)
            self._junction_index[junction_id] = ordinal
            self._junction_ids.append(junction_id)
        return ordinal

    def add(self, record: StreamedEdge) -> None:
        """Account for one streamed edge, admitting it only if it can be used.

        Every element increments exactly one accounting path, so
        ``total = internal + real`` and ``real = graph + dangling`` hold by
        construction rather than by subtraction.  An edge missing an endpoint
        cannot join a graph, but dropping it silently would make it disappear
        from the reconciliation, so it is counted here and published.
        """

        self.total_edge_elements_read += 1
        if record.internal:
            self.internal_edges_excluded += 1
            return
        self.real_edges_read += 1
        if record.lane_count == 0:
            self.no_lane_edges += 1
        if record.from_junction is None or record.to_junction is None:
            self.dangling_edges_excluded += 1
            return
        edge_id, road_type, access, length = (
            record.edge_id,
            record.road_type,
            record.access,
            record.length_m,
        )
        source = self._intern(record.from_junction)
        target = self._intern(record.to_junction)
        if source == target:
            self.self_loop_edges += 1
        type_ordinal = self._road_type_index.get(road_type)
        if type_ordinal is None:
            type_ordinal = len(self._road_types)
            self._road_type_index[road_type] = type_ordinal
            self._road_types.append(road_type)
        self._edge_ids.append(edge_id)
        self._from.append(source)
        self._to.append(target)
        self._length.append(length)
        self._access.append(_ACCESS_CODES[access])
        self._road_type_of.append(type_ordinal)

    def edge_id(self, ordinal: int) -> str:
        return self._edge_ids[ordinal]

    def endpoints(self, ordinal: int) -> tuple[int, int]:
        return self._from[ordinal], self._to[ordinal]

    def length_m(self, ordinal: int) -> float:
        return self._length[ordinal]

    def road_type(self, ordinal: int) -> str | None:
        return self._road_types[self._road_type_of[ordinal]]

    def access(self, ordinal: int) -> MotorAccess:
        return _ACCESS_NAMES[self._access[ordinal]]

    def junction_id(self, ordinal: int) -> str:
        return self._junction_ids[ordinal]

    def eligible(self, ordinal: int, eligibility: Eligibility) -> bool:
        """Whether one edge belongs to the requested motor subgraph."""

        code = self._access[ordinal]
        if eligibility == "passenger_car":
            return code == 0
        return code in (0, 1)

    def eligible_ordinals(self, eligibility: Eligibility) -> list[int]:
        return [index for index in range(len(self._edge_ids)) if self.eligible(index, eligibility)]

    def access_counts(self) -> dict[MotorAccess, int]:
        counts: dict[MotorAccess, int] = dict.fromkeys(_ACCESS_NAMES, 0)
        for code in self._access:
            counts[_ACCESS_NAMES[code]] += 1
        return counts

    def outgoing(self, eligibility: Eligibility) -> tuple[array[int], array[int]]:
        """Build a CSR adjacency over the eligible subgraph.

        Returned as (start offsets, edge ordinals).  Ordinals inside each
        junction's slice stay ascending, so traversal order is fixed by the
        network's own edge order rather than by dictionary iteration.
        """

        junctions = self.junction_count
        starts = array("i", bytes(4 * (junctions + 1)))
        eligible = self.eligible_ordinals(eligibility)
        for ordinal in eligible:
            starts[self._from[ordinal] + 1] += 1
        for index in range(1, junctions + 1):
            starts[index] += starts[index - 1]
        cursor = array("i", starts[:junctions])
        targets = array("i", bytes(4 * len(eligible)))
        for ordinal in eligible:
            source = self._from[ordinal]
            targets[cursor[source]] = ordinal
            cursor[source] += 1
        return starts, targets


def build_motor_network_graph(path: str | Path) -> MotorNetworkGraph:
    """Read one network into a motor-access graph in a single streaming pass."""

    graph = MotorNetworkGraph()
    for record in stream_network_edges(path):
        graph.add(record)
    return graph


def weak_component_labels(graph: MotorNetworkGraph, eligibility: Eligibility) -> list[int]:
    """Label every junction with its weakly connected component.

    Union-find with path halving and union by size.  A junction touched by no
    eligible edge stays its own singleton; it is excluded from the published
    component counts rather than reported as a one-junction road network.
    """

    parent = list(range(graph.junction_count))
    size = [1] * graph.junction_count

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for ordinal in graph.eligible_ordinals(eligibility):
        source, target = graph.endpoints(ordinal)
        left, right = find(source), find(target)
        if left == right:
            continue
        if size[left] < size[right]:
            left, right = right, left
        parent[right] = left
        size[left] += size[right]

    return [find(node) for node in range(graph.junction_count)]


def strong_component_labels(graph: MotorNetworkGraph, eligibility: Eligibility) -> list[int]:
    """Label every junction with its strongly connected component.

    Iterative Tarjan.  Recursion is not an option at 468,442 junctions, and a
    recursion-limit crash midway through a review would be a silent partial
    answer rather than a refusal.
    """

    total = graph.junction_count
    starts, targets = graph.outgoing(eligibility)
    index_of = [-1] * total
    low = [0] * total
    on_stack = bytearray(total)
    component = [-1] * total
    stack: list[int] = []
    counter = 0
    assigned = 0

    for root in range(total):
        if index_of[root] != -1:
            continue
        index_of[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack[root] = 1
        work: list[list[int]] = [[root, starts[root]]]
        while work:
            frame = work[-1]
            node, cursor = frame[0], frame[1]
            if cursor < starts[node + 1]:
                frame[1] = cursor + 1
                neighbour = graph.endpoints(targets[cursor])[1]
                if index_of[neighbour] == -1:
                    index_of[neighbour] = low[neighbour] = counter
                    counter += 1
                    stack.append(neighbour)
                    on_stack[neighbour] = 1
                    work.append([neighbour, starts[neighbour]])
                elif on_stack[neighbour]:
                    low[node] = min(low[node], index_of[neighbour])
                continue
            work.pop()
            if work:
                parent_node = work[-1][0]
                low[parent_node] = min(low[parent_node], low[node])
            if low[node] == index_of[node]:
                while True:
                    member = stack.pop()
                    on_stack[member] = 0
                    component[member] = assigned
                    if member == node:
                        break
                assigned += 1

    return component


class ComponentInventoryEntry(NetworkConnectivityModel):
    """One component below the largest, kept rather than summarised away."""

    rank: int = Field(ge=2)
    junction_count: int = Field(ge=1)
    edge_count: int = Field(ge=0)
    total_length_m: Decimal = Field(ge=0)
    example_edge_ids: tuple[str, ...] = Field(max_length=MAX_LISTED_EXAMPLE_EDGES)


class IsolatedFragmentInventory(NetworkConnectivityModel):
    """Complete totals for the tiny fragments, plus a bounded sample of them.

    A size-descending list of runner-up components can never show these: an
    isolated fragment is by definition among the *smallest*, so it sorts last
    and falls off the end of any top-N.  The totals here are therefore computed
    over every fragment, not over the sample, and the sample is drawn from the
    smallest end so it shows what the ranked inventory structurally cannot.
    """

    #: A component at or below this edge count is an isolated fragment.
    max_edges_per_fragment: int = Field(ge=1)
    fragment_components: int = Field(ge=0)
    fragment_edges: int = Field(ge=0)
    fragment_junctions: int = Field(ge=0)
    fragment_length_m: Decimal = Field(ge=0)
    singleton_junction_components: int = Field(ge=0)
    #: Components holding exactly one eligible edge: the smallest real island.
    single_edge_components: int = Field(ge=0)
    #: Edges that start and end at the same junction. Real in SUMO, and never
    #: evidence that anywhere else is reachable.
    self_loop_edges: int = Field(ge=0)
    examples: tuple[ComponentInventoryEntry, ...] = Field(max_length=MAX_LISTED_EXAMPLE_EDGES)
    examples_truncated: bool

    @model_validator(mode="after")
    def validate_fragment_accounting(self) -> IsolatedFragmentInventory:
        if self.fragment_components == 0 and (self.fragment_edges or self.fragment_junctions):
            raise ValueError("fragment edges or junctions cannot exist without a fragment")
        if self.single_edge_components > self.fragment_components:
            raise ValueError("single-edge components are a subset of the fragments")
        if len(self.examples) > self.fragment_components:
            raise ValueError("more fragment examples than fragments exist")
        return self


class ComponentSummary(NetworkConnectivityModel):
    """Connected-component structure of one motor subgraph."""

    kind: ComponentKind
    eligibility: Eligibility
    eligible_edges: int = Field(ge=0)
    eligible_edge_length_m: Decimal = Field(ge=0)
    junctions_touched: int = Field(ge=0)
    junctions_untouched: int = Field(ge=0)
    component_count: int = Field(ge=0)
    largest_component_junctions: int = Field(ge=0)
    largest_component_edges: int = Field(ge=0)
    largest_component_length_m: Decimal = Field(ge=0)
    #: Unrounded to six places on purpose: a coverage figure that rounds up to
    #: 1 would read as complete coverage of a network that is not complete.
    largest_component_edge_share: Decimal = Field(ge=0, le=1)
    largest_component_length_share: Decimal = Field(ge=0, le=1)
    edges_outside_largest_component: int = Field(ge=0)
    length_outside_largest_component_m: Decimal = Field(ge=0)
    #: Edges whose two endpoints fall in different components.  Only a strong
    #: summary can have these, and they belong to neither side.
    edges_between_components: int = Field(ge=0)
    #: Their length, named rather than absorbed into the "outside" figure.
    #: Without this field an inter-component edge's metres would silently
    #: inflate the length attributed to the other components.
    length_between_components_m: Decimal = Field(ge=0)
    #: The runner-up components, largest first: this answers "is there a second
    #: substantial island?".
    inventory: tuple[ComponentInventoryEntry, ...] = Field(max_length=MAX_LISTED_COMPONENTS)
    inventory_truncated: bool
    #: The small end, which the ranked inventory above structurally cannot show.
    isolated: IsolatedFragmentInventory

    @model_validator(mode="after")
    def validate_component_accounting(self) -> ComponentSummary:
        inside = self.largest_component_edges + self.edges_outside_largest_component
        if inside + self.edges_between_components != self.eligible_edges:
            raise ValueError(
                "largest-component, other-component, and between-component edges "
                "must account for every eligible edge"
            )
        metres = (
            self.largest_component_length_m
            + self.length_outside_largest_component_m
            + self.length_between_components_m
        )
        if metres != self.eligible_edge_length_m:
            raise ValueError(
                "largest-component, other-component, and between-component length "
                "must account for every eligible metre"
            )
        if self.component_count == 0 and self.eligible_edges:
            raise ValueError("eligible edges cannot exist without a component")
        if self.largest_component_edges > self.eligible_edges:
            raise ValueError("the largest component cannot exceed the eligible population")
        if self.kind == "weak" and self.edges_between_components:
            raise ValueError("a weakly connected component cannot have edges leaving it")
        return self


class RouteProbe(NetworkConnectivityModel):
    """One bounded origin-to-destination reachability probe.

    A probe is evidence about **this pair**.  It is never evidence that the
    network is routable, which is why the outcome, the expansion bound, and both
    component memberships are published together.
    """

    probe_index: int = Field(ge=0)
    eligibility: Eligibility
    #: Deliberately required rather than defaulted. A default silently labelled
    #: a contrast probe as a spread probe on every branch that forgot to pass
    #: it, and the mislabel was invisible for the spread probes themselves.
    selection: ProbeSelection
    origin_edge_id: str = Field(min_length=1, max_length=200)
    destination_edge_id: str = Field(min_length=1, max_length=200)
    outcome: ProbeOutcome
    hops: int | None = Field(default=None, ge=0)
    junctions_expanded: int = Field(ge=0)
    expansion_limit: int = Field(ge=1)
    origin_strong_component_rank: int | None = Field(default=None, ge=1)
    destination_strong_component_rank: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_probe(self) -> RouteProbe:
        if self.outcome == "routed" and self.hops is None:
            raise ValueError("a routed probe must report its hop count")
        if self.outcome != "routed" and self.hops is not None:
            raise ValueError("only a routed probe may report a hop count")
        if self.junctions_expanded > self.expansion_limit:
            raise ValueError("a probe cannot expand beyond its own bound")
        return self


class MotorAccessSummary(NetworkConnectivityModel):
    """How the real edge population divides by motor-vehicle access."""

    total_edge_elements: int = Field(ge=0)
    internal_edges_excluded: int = Field(ge=0)
    real_edges: int = Field(ge=0)
    dangling_edges_excluded: int = Field(ge=0)
    #: Real edges declaring no lane at all. Their permissions are unreadable
    #: rather than open, so they are reported here as well as in that class.
    no_lane_edges: int = Field(ge=0)
    graph_edges: int = Field(ge=0)
    passenger_car_edges: int = Field(ge=0)
    motor_vehicle_no_car_edges: int = Field(ge=0)
    no_motor_vehicle_edges: int = Field(ge=0)
    permissions_unreadable_edges: int = Field(ge=0)
    self_loop_edges: int = Field(ge=0)
    junctions: int = Field(ge=0)
    #: Named so the gap between the two subgraphs cannot be read as rounding.
    motor_but_not_car_note: str = Field(min_length=1, max_length=500)
    undefined_classes_excluded: tuple[str, ...]

    @model_validator(mode="after")
    def validate_access_accounting(self) -> MotorAccessSummary:
        parts = (
            self.passenger_car_edges
            + self.motor_vehicle_no_car_edges
            + self.no_motor_vehicle_edges
            + self.permissions_unreadable_edges
        )
        if parts != self.graph_edges:
            raise ValueError("every graph edge must fall in exactly one access class")
        if self.graph_edges + self.dangling_edges_excluded != self.real_edges:
            raise ValueError("graph and dangling edges must account for every real edge")
        if self.internal_edges_excluded + self.real_edges != self.total_edge_elements:
            raise ValueError("internal and real edges must account for every edge element")
        if self.no_lane_edges > self.real_edges:
            raise ValueError("lane-free edges are a subset of the real edges")
        return self


class ManchesterNetworkConnectivityReport(NetworkConnectivityModel):
    """Complete motor-eligible connectivity review of one bound network."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-network-connectivity-1.0"] = (
        NETWORK_CONNECTIVITY_METHOD_VERSION
    )
    capability_status: Literal["planned"] = "planned"
    gate: Literal["Gate-D step 1 review (network binding), no matching or calibration"] = (
        "Gate-D step 1 review (network binding), no matching or calibration"
    )
    research_status: Literal["owner_approved_candidate"] = "owner_approved_candidate"

    #: Every claim below belongs to exactly this network and no other.
    network_id: str = Field(min_length=1, max_length=64)
    network_identity_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    access: MotorAccessSummary
    components: tuple[ComponentSummary, ...] = Field(min_length=1)
    probe_eligibility: Eligibility
    probes: tuple[RouteProbe, ...]
    exclusion_notes: tuple[str, ...] = Field(min_length=1)

    #: A bounded probe cannot establish this, and no number of probes can.
    proves_universal_routability: Literal[False] = False
    calibration_performed: Literal[False] = False
    matching_performed: Literal[False] = False
    accepted_for_real_matching: Literal[False] = False

    @model_validator(mode="after")
    def validate_report(self) -> ManchesterNetworkConnectivityReport:
        seen = {(item.kind, item.eligibility) for item in self.components}
        if len(seen) != len(self.components):
            raise ValueError("each (kind, eligibility) summary may appear at most once")
        summarised = {item.eligibility for item in self.components}
        if self.probe_eligibility not in summarised:
            raise ValueError("probes must describe a summarised subgraph")
        for probe in self.probes:
            if probe.eligibility != self.probe_eligibility:
                raise ValueError("every probe must use the report's declared probe subgraph")
        return self

    def summary_for(self, kind: ComponentKind, eligibility: Eligibility) -> ComponentSummary:
        """Return one summary, refusing rather than returning a wrong one."""

        for item in self.components:
            if item.kind == kind and item.eligibility == eligibility:
                return item
        raise NetworkConnectivityError(
            "COMPONENT_SUMMARY_ABSENT", f"no {kind} summary exists for {eligibility}"
        )


def _decimal(value: float) -> Decimal:
    return Decimal(f"{value:.3f}")


def _share(part: float, whole: float) -> Decimal:
    if whole <= 0:
        return Decimal("0")
    ratio = (Decimal(repr(part)) / Decimal(repr(whole))).quantize(_SHARE_QUANTUM)
    return min(ratio, Decimal("1"))


def _share_decimal(part: Decimal, whole: Decimal) -> Decimal:
    if whole <= 0:
        return Decimal("0")
    return min((part / whole).quantize(_SHARE_QUANTUM), Decimal("1"))


def summarise_components(
    graph: MotorNetworkGraph,
    *,
    kind: ComponentKind,
    eligibility: Eligibility,
) -> tuple[ComponentSummary, list[int], dict[int, int]]:
    """Summarise one subgraph's components and rank them canonically.

    Returns the summary, the per-junction labels, and a label-to-rank map.
    Ranking by (edges, junctions, smallest junction id) rather than by internal
    label makes the report a property of the network rather than of the order
    the file happened to be streamed in.
    """

    labels = (
        weak_component_labels(graph, eligibility)
        if kind == "weak"
        else strong_component_labels(graph, eligibility)
    )
    eligible = graph.eligible_ordinals(eligibility)

    edge_counts: dict[int, int] = {}
    lengths: dict[int, float] = {}
    examples: dict[int, list[str]] = {}
    touched: set[int] = set()
    between = 0
    between_length = 0.0
    for ordinal in eligible:
        source, target = graph.endpoints(ordinal)
        touched.add(source)
        touched.add(target)
        if labels[source] != labels[target]:
            # Only reachable for the strong summary: a directed edge between two
            # strongly connected components is real and belongs to neither. Its
            # metres are held separately so they never inflate another
            # component's length.
            between += 1
            between_length += graph.length_m(ordinal)
            continue
        label = labels[source]
        edge_counts[label] = edge_counts.get(label, 0) + 1
        lengths[label] = lengths.get(label, 0.0) + graph.length_m(ordinal)
        bucket = examples.setdefault(label, [])
        if len(bucket) < MAX_LISTED_EXAMPLE_EDGES:
            bucket.append(graph.edge_id(ordinal))

    junction_counts: dict[int, int] = {}
    smallest_junction: dict[int, str] = {}
    self_loops: dict[int, int] = {}
    for ordinal in eligible:
        source, target = graph.endpoints(ordinal)
        if source == target:
            self_loops[labels[source]] = self_loops.get(labels[source], 0) + 1
    for node in sorted(touched):
        label = labels[node]
        junction_counts[label] = junction_counts.get(label, 0) + 1
        identifier = graph.junction_id(node)
        if label not in smallest_junction or identifier < smallest_junction[label]:
            smallest_junction[label] = identifier

    ranked = sorted(
        junction_counts,
        key=lambda label: (
            -edge_counts.get(label, 0),
            -junction_counts[label],
            smallest_junction[label],
        ),
    )
    ranks = {label: position + 1 for position, label in enumerate(ranked)}

    largest = ranked[0] if ranked else None
    largest_edges = edge_counts.get(largest, 0) if largest is not None else 0
    largest_junctions = junction_counts.get(largest, 0) if largest is not None else 0

    # Each bucket is quantised from its own sum and the published total is their
    # sum, so the reconciliation is exact by construction. Quantising an
    # independently accumulated total instead would leave a sub-millimetre
    # rounding residue that an exact equality check would then reject.
    largest_length_m = _decimal(lengths.get(largest, 0.0) if largest is not None else 0.0)
    outside_length_m = _decimal(sum(value for label, value in lengths.items() if label != largest))
    between_length_m = _decimal(between_length)
    total_length_m = largest_length_m + outside_length_m + between_length_m

    def _entry(label: int) -> ComponentInventoryEntry:
        return ComponentInventoryEntry(
            rank=ranks[label],
            junction_count=junction_counts[label],
            edge_count=edge_counts.get(label, 0),
            total_length_m=_decimal(lengths.get(label, 0.0)),
            example_edge_ids=tuple(examples.get(label, ())),
        )

    inventory = tuple(_entry(label) for label in ranked[1 : 1 + MAX_LISTED_COMPONENTS])

    # Fragments are counted over every runner-up component, then sampled from
    # the smallest end. Sampling first would make the totals a property of the
    # sample size rather than of the network.
    fragments = [
        label for label in ranked[1:] if edge_counts.get(label, 0) <= ISOLATED_COMPONENT_MAX_EDGES
    ]
    fragment_order = sorted(
        fragments,
        key=lambda label: (
            edge_counts.get(label, 0),
            junction_counts[label],
            smallest_junction[label],
        ),
    )
    isolated = IsolatedFragmentInventory(
        max_edges_per_fragment=ISOLATED_COMPONENT_MAX_EDGES,
        fragment_components=len(fragments),
        fragment_edges=sum(edge_counts.get(label, 0) for label in fragments),
        fragment_junctions=sum(junction_counts[label] for label in fragments),
        fragment_length_m=_decimal(sum(lengths.get(label, 0.0) for label in fragments)),
        singleton_junction_components=sum(1 for label in ranked[1:] if junction_counts[label] == 1),
        single_edge_components=sum(1 for label in fragments if edge_counts.get(label, 0) == 1),
        self_loop_edges=sum(self_loops.values()),
        examples=tuple(_entry(label) for label in fragment_order[:MAX_LISTED_EXAMPLE_EDGES]),
        examples_truncated=len(fragment_order) > MAX_LISTED_EXAMPLE_EDGES,
    )

    summary = ComponentSummary(
        kind=kind,
        eligibility=eligibility,
        eligible_edges=len(eligible),
        eligible_edge_length_m=total_length_m,
        junctions_touched=len(touched),
        junctions_untouched=graph.junction_count - len(touched),
        component_count=len(ranked),
        largest_component_junctions=largest_junctions,
        largest_component_edges=largest_edges,
        largest_component_length_m=largest_length_m,
        largest_component_edge_share=_share(largest_edges, len(eligible)),
        largest_component_length_share=_share_decimal(largest_length_m, total_length_m),
        edges_outside_largest_component=len(eligible) - largest_edges - between,
        length_outside_largest_component_m=outside_length_m,
        edges_between_components=between,
        length_between_components_m=between_length_m,
        inventory=inventory,
        inventory_truncated=len(ranked) - 1 > MAX_LISTED_COMPONENTS,
        isolated=isolated,
    )
    return summary, labels, ranks


def select_probe_pairs(
    graph: MotorNetworkGraph,
    eligibility: Eligibility,
    *,
    count: int = DEFAULT_ROUTE_PROBES,
) -> tuple[tuple[int, int], ...]:
    """Choose probe pairs deterministically, spread across the eligible edges.

    Sorting by edge id first makes the selection a property of the network
    rather than of the order it was streamed.  Origin and destination are taken
    half a population apart so a pair is unlikely to be two fragments of one
    street, which would make a successful probe uninformative.
    """

    if count < 1 or count > MAX_ROUTE_PROBES:
        raise NetworkConnectivityError(
            "PROBE_COUNT_REFUSED",
            f"probe count must be between 1 and {MAX_ROUTE_PROBES}",
        )
    eligible = sorted(graph.eligible_ordinals(eligibility), key=graph.edge_id)
    if not eligible:
        return ()
    total = len(eligible)
    stride = max(1, total // count)
    return tuple(
        (eligible[(index * stride) % total], eligible[((index * stride) + total // 2) % total])
        for index in range(count)
    )


def select_contrast_probe_pairs(
    graph: MotorNetworkGraph,
    eligibility: Eligibility,
    *,
    labels: Sequence[int],
    ranks: dict[int, int],
    count: int,
) -> tuple[tuple[int, int], ...]:
    """Pair the largest component with components outside it, deterministically.

    A uniformly spread probe set over a network whose largest component holds
    99.7% of edges will route every time, and a report of unbroken successes
    invites exactly the universal-routability reading this module refuses.
    These pairs target the components that a spread sample almost never reaches,
    so the probe set has to demonstrate that it can fail.
    """

    if count < 1 or count > MAX_ROUTE_PROBES:
        raise NetworkConnectivityError(
            "PROBE_COUNT_REFUSED", f"probe count must be between 1 and {MAX_ROUTE_PROBES}"
        )
    representative: dict[int, int] = {}
    for ordinal in graph.eligible_ordinals(eligibility):
        source, target = graph.endpoints(ordinal)
        if labels[source] != labels[target]:
            continue
        label = labels[source]
        current = representative.get(label)
        if current is None or graph.edge_id(ordinal) < graph.edge_id(current):
            representative[label] = ordinal
    ranked = sorted(representative, key=lambda label: ranks.get(label, 0))
    if not ranked:
        return ()
    origin = representative[ranked[0]]
    return tuple((origin, representative[label]) for label in ranked[1 : 1 + count])


def run_route_probe(
    graph: MotorNetworkGraph,
    eligibility: Eligibility,
    *,
    probe_index: int,
    origin_edge: int,
    destination_edge: int,
    selection: ProbeSelection = "deterministic_spread",
    expansion_limit: int = DEFAULT_PROBE_EXPANSION,
    adjacency: tuple[array[int], array[int]] | None = None,
    strong_labels: Sequence[int] | None = None,
    strong_ranks: dict[int, int] | None = None,
) -> RouteProbe:
    """Run one bounded breadth-first reachability probe over the subgraph.

    Breadth-first because hop count is then the true minimum and needs no
    weighting decision; a shortest-*distance* probe would need a travel-cost
    model, and no cost contract is approved.  The expansion bound guarantees the
    probe terminates, and reaching it is its own outcome rather than being
    folded into ``unreachable`` — failing to find a path is not the same as
    proving none exists.
    """

    if expansion_limit < 1 or expansion_limit > MAX_PROBE_EXPANSION:
        raise NetworkConnectivityError(
            "PROBE_EXPANSION_REFUSED",
            f"probe expansion must be between 1 and {MAX_PROBE_EXPANSION}",
        )
    origin_id = graph.edge_id(origin_edge)
    destination_id = graph.edge_id(destination_edge)

    def _rank(node: int) -> int | None:
        if strong_labels is None or strong_ranks is None:
            return None
        return strong_ranks.get(strong_labels[node])

    if not graph.eligible(origin_edge, eligibility) or not graph.eligible(
        destination_edge, eligibility
    ):
        return RouteProbe(
            probe_index=probe_index,
            eligibility=eligibility,
            selection=selection,
            origin_edge_id=origin_id,
            destination_edge_id=destination_id,
            outcome="endpoint_not_eligible",
            junctions_expanded=0,
            expansion_limit=expansion_limit,
        )

    starts, targets = adjacency if adjacency is not None else graph.outgoing(eligibility)
    start_node = graph.endpoints(origin_edge)[1]
    goal_node = graph.endpoints(destination_edge)[0]
    origin_rank = _rank(start_node)
    destination_rank = _rank(goal_node)

    if start_node == goal_node:
        return RouteProbe(
            probe_index=probe_index,
            eligibility=eligibility,
            selection=selection,
            origin_edge_id=origin_id,
            destination_edge_id=destination_id,
            outcome="routed",
            hops=0,
            junctions_expanded=1,
            expansion_limit=expansion_limit,
            origin_strong_component_rank=origin_rank,
            destination_strong_component_rank=destination_rank,
        )

    visited = bytearray(graph.junction_count)
    visited[start_node] = 1
    frontier = [start_node]
    expanded = 0
    hops = 0
    while frontier:
        hops += 1
        following: list[int] = []
        for node in frontier:
            expanded += 1
            if expanded > expansion_limit:
                return RouteProbe(
                    probe_index=probe_index,
                    eligibility=eligibility,
                    selection=selection,
                    origin_edge_id=origin_id,
                    destination_edge_id=destination_id,
                    outcome="probe_limit_reached",
                    junctions_expanded=expansion_limit,
                    expansion_limit=expansion_limit,
                    origin_strong_component_rank=origin_rank,
                    destination_strong_component_rank=destination_rank,
                )
            for cursor in range(starts[node], starts[node + 1]):
                neighbour = graph.endpoints(targets[cursor])[1]
                if visited[neighbour]:
                    continue
                if neighbour == goal_node:
                    return RouteProbe(
                        probe_index=probe_index,
                        eligibility=eligibility,
                        selection=selection,
                        origin_edge_id=origin_id,
                        destination_edge_id=destination_id,
                        outcome="routed",
                        hops=hops,
                        junctions_expanded=expanded,
                        expansion_limit=expansion_limit,
                        origin_strong_component_rank=origin_rank,
                        destination_strong_component_rank=destination_rank,
                    )
                visited[neighbour] = 1
                following.append(neighbour)
        frontier = following

    return RouteProbe(
        probe_index=probe_index,
        eligibility=eligibility,
        selection=selection,
        origin_edge_id=origin_id,
        destination_edge_id=destination_id,
        outcome="unreachable",
        junctions_expanded=expanded,
        expansion_limit=expansion_limit,
        origin_strong_component_rank=origin_rank,
        destination_strong_component_rank=destination_rank,
    )


EXCLUSION_NOTES: tuple[str, ...] = (
    "Junction-internal edges are excluded, exactly as the geometry reader excludes them.",
    "An edge missing a from/to junction cannot join a graph; it is counted dangling, not dropped.",
    "An edge whose lanes carry contradictory permissions is counted permissions_unreadable "
    "and joins no motor subgraph.",
    "custom1 and custom2 carry no defined motor meaning and never admit an edge on their own.",
    "A junction touched by no eligible edge is excluded from the component counts and reported "
    "separately as untouched; it is unreachable by that vehicle class, not missing data.",
    "A directed edge between two strongly connected components is real and belongs to neither.",
    "Bounded probes establish reachability for the pairs they ran. They are not evidence of "
    "universal routability, and no number of them would be.",
)

MOTOR_BUT_NOT_CAR_NOTE = (
    "Edges counted as motor_vehicle_no_car permit some motor vehicle but not a private car. "
    "In this network that population is dominated by highway.service, which netconvert builds "
    "as allow='pedestrian delivery bicycle'. The two subgraphs are reported separately and are "
    "never added together."
)


def review_network_file(
    network_path: str | Path,
    *,
    network_id: str,
    network_identity_sha256: str,
    total_edge_elements: int,
    probe_count: int = DEFAULT_ROUTE_PROBES,
    contrast_probe_count: int = DEFAULT_CONTRAST_PROBES,
    expansion_limit: int = DEFAULT_PROBE_EXPANSION,
    probe_eligibility: Eligibility = "passenger_car",
) -> ManchesterNetworkConnectivityReport:
    """Review one network file whose identity the caller has already verified."""

    graph = build_motor_network_graph(network_path)
    counts = graph.access_counts()
    # The recorded total is *checked*, not used to derive the internal count.
    # Deriving it by subtraction would make any reader defect look like a
    # different number of connectors, which is exactly the confusion the
    # additive accounting above exists to prevent.
    if graph.total_edge_elements_read != total_edge_elements:
        raise NetworkConnectivityError(
            "NETWORK_EDGE_COUNTS_INCONSISTENT",
            f"read {graph.total_edge_elements_read} edge elements but the accepted binding "
            f"records {total_edge_elements}; the network or the reader disagrees with the "
            "validated structure and no connectivity claim is made from it",
        )

    summaries: list[ComponentSummary] = []
    strong_state: dict[Eligibility, tuple[list[int], dict[int, int]]] = {}
    for eligibility in ELIGIBILITIES:
        for kind in COMPONENT_KINDS:
            summary, labels, ranks = summarise_components(graph, kind=kind, eligibility=eligibility)
            summaries.append(summary)
            if kind == "strong":
                strong_state[eligibility] = (labels, ranks)

    labels, ranks = strong_state[probe_eligibility]
    adjacency = graph.outgoing(probe_eligibility)
    selected: list[tuple[tuple[int, int], ProbeSelection]] = [
        (pair, "deterministic_spread")
        for pair in select_probe_pairs(graph, probe_eligibility, count=probe_count)
    ]
    if contrast_probe_count:
        selected.extend(
            (pair, "largest_to_fragment")
            for pair in select_contrast_probe_pairs(
                graph,
                probe_eligibility,
                labels=labels,
                ranks=ranks,
                count=contrast_probe_count,
            )
        )
    probes = tuple(
        run_route_probe(
            graph,
            probe_eligibility,
            probe_index=index,
            origin_edge=origin,
            destination_edge=destination,
            selection=selection,
            expansion_limit=expansion_limit,
            adjacency=adjacency,
            strong_labels=labels,
            strong_ranks=ranks,
        )
        for index, ((origin, destination), selection) in enumerate(selected)
    )

    access = MotorAccessSummary(
        total_edge_elements=graph.total_edge_elements_read,
        internal_edges_excluded=graph.internal_edges_excluded,
        real_edges=graph.real_edges_read,
        dangling_edges_excluded=graph.dangling_edges_excluded,
        no_lane_edges=graph.no_lane_edges,
        graph_edges=len(graph),
        passenger_car_edges=counts["passenger_car"],
        motor_vehicle_no_car_edges=counts["motor_vehicle_no_car"],
        no_motor_vehicle_edges=counts["no_motor_vehicle"],
        permissions_unreadable_edges=counts["permissions_unreadable"],
        self_loop_edges=graph.self_loop_edges,
        junctions=graph.junction_count,
        motor_but_not_car_note=MOTOR_BUT_NOT_CAR_NOTE,
        undefined_classes_excluded=tuple(sorted(UNDEFINED_VEHICLE_CLASSES)),
    )

    return ManchesterNetworkConnectivityReport(
        network_id=network_id,
        network_identity_sha256=network_identity_sha256,
        access=access,
        components=tuple(summaries),
        probe_eligibility=probe_eligibility,
        probes=probes,
        exclusion_notes=EXCLUSION_NOTES,
    )


def review_network_connectivity(
    network_dir: str | Path,
    *,
    probe_count: int = DEFAULT_ROUTE_PROBES,
    contrast_probe_count: int = DEFAULT_CONTRAST_PROBES,
    expansion_limit: int = DEFAULT_PROBE_EXPANSION,
    probe_eligibility: Eligibility = "passenger_car",
) -> ManchesterNetworkConnectivityReport:
    """Review one accepted baseline network's motor-eligible connectivity.

    Reopening the binding through :func:`load_binding` re-verifies both recorded
    digests first, so a connectivity claim is bound to a network that still is
    what it said it was.
    """

    binding: ManchesterBaselineNetworkBinding = load_binding(network_dir)
    return review_network_file(
        Path(network_dir) / f"{binding.network_id}.net.xml",
        network_id=binding.network_id,
        network_identity_sha256=binding.network_identity_sha256,
        total_edge_elements=binding.validation.structure.edge_count,
        probe_count=probe_count,
        contrast_probe_count=contrast_probe_count,
        expansion_limit=expansion_limit,
        probe_eligibility=probe_eligibility,
    )


__all__ = [
    "DEFAULT_CONTRAST_PROBES",
    "DEFAULT_PROBE_EXPANSION",
    "DEFAULT_ROUTE_PROBES",
    "ELIGIBILITIES",
    "MAX_ROUTE_PROBES",
    "MOTOR_VEHICLE_CLASSES",
    "PASSENGER_CAR_CLASS",
    "UNDEFINED_VEHICLE_CLASSES",
    "ComponentInventoryEntry",
    "ComponentSummary",
    "Eligibility",
    "IsolatedFragmentInventory",
    "ManchesterNetworkConnectivityReport",
    "MotorAccess",
    "MotorAccessSummary",
    "MotorNetworkGraph",
    "NetworkConnectivityError",
    "RouteProbe",
    "StreamedEdge",
    "build_motor_network_graph",
    "classify_lane_access",
    "combine_lane_access",
    "review_network_connectivity",
    "review_network_file",
    "run_route_probe",
    "select_contrast_probe_pairs",
    "select_probe_pairs",
    "stream_network_edges",
    "strong_component_labels",
    "summarise_components",
    "weak_component_labels",
]

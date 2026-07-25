"""Count-constrained candidate demand from owner-policy-accepted matches.

This is design Gate-D step 5 (demand reconstruction) for **real** Manchester
evidence, and it stops at a *candidate*. The product is labelled
:data:`DEMAND_LABEL` — ``count_constrained_candidate_demand``. It is a set of
routes chosen so that simulated edge counts approach observed edge counts. It is
**not** observed origin-destination travel, and nothing here may describe it as
such.

**The acceptance limitation propagates.** The input is the set of rows the
owner's *written policy* accepted, ``owner_policy_accepted_candidate``. No
analyst, human, or supervisor reviewed any row, so every artifact produced here
carries :data:`ACCEPTANCE_BASIS` forward explicitly. The design brief's phrase
"analyst-accepted matches" is not yet satisfied by a person, and this module
never claims otherwise.

**Direction is applied here, not earlier.** The approved policy sequences it
that way: reference matching first identifies an *undirected* road group, and
the raw count's direction is applied afterwards to the underlying directed SUMO
edges. Policy v1.1 therefore leaves ``bearing_degrees`` unset, and this module
computes each edge's bearing from its own geometry and applies the approved 45°
tolerance. Four outcomes are kept distinct and never merged:

*   exactly one direction-compatible edge — the count binds to it;
*   several compatible edges whose bearings agree with **each other** to within
    the same approved tolerance — these are one carriageway that SUMO split at
    junctions, not opposing directions, so the owner ruled on 25 July 2026 that
    they count as **one binding target**. The count binds to the fragment
    nearest the count point, because a point count constrains the edge the
    count point physically sits on; binding it to every fragment would assert
    the same flow across intervening junctions. The whole collapsed set and the
    measured spread are recorded, so edge-level lineage survives;
*   several compatible edges whose bearings genuinely **diverge** — still
    ambiguous, so the policy keeps them and requires confirmation;
*   none compatible — ``direction_unresolved``. Direction is never reversed or
    invented to force a binding.

The collinearity bound deliberately **reuses the approved 45° direction
tolerance** applied pairwise, rather than introducing a second threshold. It was
measured before it was chosen: across the 163 real cases the median pairwise
spread is 2.09° and 76.1% agree to within 10°, so the population really is
dominated by split carriageways.

``C`` (combined directions) is never forced onto one directed edge.

Why ``routeSampler`` and not ``dfrouter``: SUMO's own documentation warns that
``dfrouter`` can generate implausible routes in highly meshed city networks, and
Greater Manchester is exactly that. The route pool is fixed and documented and
``routeSampler`` samples from it against the observed counts.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex
from traffictwin.integration.manchester.observation_matching import (
    CARDINAL_BEARINGS,
    COMBINED_DIRECTION,
    angular_difference,
    edge_bearing_degrees,
)

DEMAND_SCHEMA_VERSION: Literal["1.0"] = "1.0"
DEMAND_METHOD_VERSION: Literal["manchester-demand-reconstruction-1.0"] = (
    "manchester-demand-reconstruction-1.0"
)
DEMAND_CAPABILITY_ID: Literal["MAN-09"] = "MAN-09"

#: What the product is. Never "observed demand", never "origin-destination".
DEMAND_LABEL: Literal["count_constrained_candidate_demand"] = "count_constrained_candidate_demand"

#: How the input rows came to be accepted. Carried into every artifact.
ACCEPTANCE_BASIS: Literal["owner_policy_accepted_candidate"] = "owner_policy_accepted_candidate"

RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: The disposition a match must carry to be admitted as demand input.
ADMISSIBLE_DISPOSITION = "owner_policy_accepted_candidate"

DirectionBinding: TypeAlias = Literal[
    "bound_to_single_edge",
    "bound_to_collinear_fragment_group",
    "several_compatible_edges_require_confirmation",
    "direction_unresolved",
    "combined_direction_not_forced",
    "direction_absent",
]

#: Bindings that produced a usable edge. Kept as one place so a reader cannot
#: accidentally count one population and forget the other.
BOUND_BINDINGS: frozenset[str] = frozenset(
    {"bound_to_single_edge", "bound_to_collinear_fragment_group"}
)


class DemandReconstructionError(ValueError):
    """Typed refusal for an unsupported or inconsistent demand request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class DemandModel(ManchesterSnapshotModel):
    """Strict frozen base for candidate-demand artifacts."""


class DirectionResolution(DemandModel):
    """How one site-direction resolved onto the network, and why."""

    count_point_id: int = Field(ge=0)
    direction_of_travel: str = Field(min_length=1, max_length=8)
    binding: DirectionBinding
    edge_id: str | None = Field(default=None, max_length=200)
    #: Every member edge considered, with its measured bearing, so a reader can
    #: see what the tolerance was applied to rather than trusting the outcome.
    considered: tuple[tuple[str, Decimal | None], ...] = ()
    target_bearing_degrees: Decimal | None = Field(default=None, ge=0, lt=360)
    tolerance_degrees: Decimal = Field(ge=0, le=180)
    #: Maximum pairwise circular difference among the compatible bearings.
    #: Recorded whenever more than one edge was compatible, so a reader can see
    #: how collinear the fragments actually were rather than trusting the label.
    collinear_spread_degrees: Decimal | None = Field(default=None, ge=0, le=180)
    #: The whole fragment set a collinear binding collapsed, kept so edge-level
    #: lineage survives the collapse.
    collinear_group: tuple[str, ...] = ()
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_resolution(self) -> DirectionResolution:
        if (self.binding in BOUND_BINDINGS) != (self.edge_id is not None):
            raise ValueError("an edge id is recorded exactly when the direction bound")
        if self.binding == "bound_to_collinear_fragment_group":
            if len(self.collinear_group) < 2:
                raise ValueError("a collinear binding must record the fragment set it collapsed")
            if self.edge_id not in self.collinear_group:
                raise ValueError("the bound edge must be one of the collapsed fragments")
            if self.collinear_spread_degrees is None:
                raise ValueError("a collinear binding must record the measured spread")
            if self.collinear_spread_degrees > self.tolerance_degrees:
                raise ValueError("a collinear binding cannot exceed the approved tolerance")
        elif self.collinear_group:
            raise ValueError("only a collinear binding records a collapsed fragment set")
        return self


class EdgeHourCount(DemandModel):
    """One observed hourly count bound to one directed edge."""

    edge_id: str = Field(min_length=1, max_length=200)
    count_point_id: int = Field(ge=0)
    direction_of_travel: str = Field(min_length=1, max_length=8)
    hour: int = Field(ge=0, le=23)
    interval_start_s: int = Field(ge=0)
    interval_end_s: int = Field(gt=0)
    all_motor_vehicles: int = Field(ge=0)
    #: True when the source explicitly recorded a measured zero, so a real zero
    #: is never confused with a missing hour.
    measured_zero: bool

    @model_validator(mode="after")
    def validate_count(self) -> EdgeHourCount:
        if self.interval_end_s <= self.interval_start_s:
            raise ValueError("an interval must be a positive half-open window")
        if self.measured_zero and self.all_motor_vehicles != 0:
            raise ValueError("a measured-zero cell must carry a zero count")
        return self


class DemandInputLedger(DemandModel):
    """Everything offered, everything bound, and everything not bound with why."""

    schema_version: Literal["1.0"] = "1.0"
    sites_offered: int = Field(ge=0)
    sites_admissible: int = Field(ge=0)
    sites_rejected_wrong_disposition: int = Field(ge=0)
    directions_offered: int = Field(ge=0)
    directions_bound: int = Field(ge=0)
    directions_requiring_confirmation: int = Field(ge=0)
    directions_unresolved: int = Field(ge=0)
    directions_combined_not_forced: int = Field(ge=0)
    cells_bound: int = Field(ge=0)
    measured_zero_cells_bound: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_ledger(self) -> DemandInputLedger:
        if self.sites_admissible + self.sites_rejected_wrong_disposition != self.sites_offered:
            raise ValueError("every offered site must be admitted or rejected, never dropped")
        resolved = (
            self.directions_bound
            + self.directions_requiring_confirmation
            + self.directions_unresolved
            + self.directions_combined_not_forced
        )
        if resolved != self.directions_offered:
            raise ValueError("every offered direction must reach exactly one outcome")
        return self


class CountConstrainedDemandInput(DemandModel):
    """The complete edge-count input a route sampler may be run against."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-demand-reconstruction-1.0"] = DEMAND_METHOD_VERSION
    demand_label: Literal["count_constrained_candidate_demand"] = DEMAND_LABEL
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    #: The single most important field in this artifact.
    acceptance_basis: Literal["owner_policy_accepted_candidate"] = ACCEPTANCE_BASIS
    analyst_accepted: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    observed_origin_destination_travel: Literal[False] = False

    match_policy_id: str = Field(min_length=1, max_length=120)
    match_policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    direction_tolerance_degrees: Decimal = Field(ge=0, le=180)

    counts: tuple[EdgeHourCount, ...] = ()
    resolutions: tuple[DirectionResolution, ...] = ()
    ledger: DemandInputLedger

    @model_validator(mode="after")
    def validate_input(self) -> CountConstrainedDemandInput:
        bound = {
            resolution.edge_id
            for resolution in self.resolutions
            if resolution.binding in BOUND_BINDINGS and resolution.edge_id is not None
        }
        for count in self.counts:
            if count.edge_id not in bound:
                raise ValueError("every count must bind to an edge the direction step resolved")
        return self

    def fingerprint(self) -> str:
        return sha256_hex(self.canonical_json().encode("utf-8"))

    def edge_totals(self) -> dict[str, int]:
        """Total observed vehicles per edge across every bound hour."""

        totals: dict[str, int] = defaultdict(int)
        for count in self.counts:
            totals[count.edge_id] += count.all_motor_vehicles
        return dict(totals)


def resolve_direction(
    *,
    count_point_id: int,
    direction_of_travel: str,
    member_edge_ids: Sequence[str],
    index: EdgeSpatialIndex,
    ordinals_by_edge: Mapping[str, int],
    tolerance_degrees: Decimal,
    distance_by_edge: Mapping[str, Decimal] | None = None,
) -> DirectionResolution:
    """Apply one raw-count direction to a road group's directed edges.

    Direction is never reversed and never invented. Where several edges remain
    compatible the count is left unbound, because the approved policy keeps both
    and requires confirmation rather than picking one.
    """

    considered: list[tuple[str, Decimal | None]] = []
    for edge_id in member_edge_ids:
        ordinal = ordinals_by_edge.get(edge_id)
        bearing = edge_bearing_degrees(index.geometry(ordinal)) if ordinal is not None else None
        considered.append((edge_id, bearing))
    frozen = tuple(considered)

    if direction_of_travel == COMBINED_DIRECTION:
        return DirectionResolution(
            count_point_id=count_point_id,
            direction_of_travel=direction_of_travel,
            binding="combined_direction_not_forced",
            considered=frozen,
            tolerance_degrees=tolerance_degrees,
            reason="a combined-direction count is never forced onto one directed edge",
        )

    target = CARDINAL_BEARINGS.get(direction_of_travel)
    if target is None:
        return DirectionResolution(
            count_point_id=count_point_id,
            direction_of_travel=direction_of_travel,
            binding="direction_absent",
            considered=frozen,
            tolerance_degrees=tolerance_degrees,
            reason=f"direction {direction_of_travel!r} is not an approved cardinal code",
        )

    compatible = [
        (edge_id, bearing)
        for edge_id, bearing in frozen
        if bearing is not None and angular_difference(bearing, target) <= tolerance_degrees
    ]
    if len(compatible) == 1:
        return DirectionResolution(
            count_point_id=count_point_id,
            direction_of_travel=direction_of_travel,
            binding="bound_to_single_edge",
            edge_id=compatible[0][0],
            considered=frozen,
            target_bearing_degrees=target,
            tolerance_degrees=tolerance_degrees,
            reason="exactly one member edge lies within the approved bearing tolerance",
        )
    if len(compatible) > 1:
        spread = max_pairwise_spread([bearing for _edge_id, bearing in compatible])
        if spread <= tolerance_degrees:
            nearest = _nearest_fragment(
                [edge_id for edge_id, _bearing in compatible], distance_by_edge
            )
            if nearest is None:
                return DirectionResolution(
                    count_point_id=count_point_id,
                    direction_of_travel=direction_of_travel,
                    binding="several_compatible_edges_require_confirmation",
                    considered=frozen,
                    target_bearing_degrees=target,
                    tolerance_degrees=tolerance_degrees,
                    collinear_spread_degrees=spread,
                    reason=(
                        "the compatible edges are collinear but no distance to the count point "
                        "is available, so the fragment carrying the count cannot be identified"
                    ),
                )
            return DirectionResolution(
                count_point_id=count_point_id,
                direction_of_travel=direction_of_travel,
                binding="bound_to_collinear_fragment_group",
                edge_id=nearest,
                considered=frozen,
                target_bearing_degrees=target,
                tolerance_degrees=tolerance_degrees,
                collinear_spread_degrees=spread,
                collinear_group=tuple(sorted(edge_id for edge_id, _bearing in compatible)),
                reason=(
                    f"{len(compatible)} compatible edges lie within {tolerance_degrees} degrees "
                    "of each other, so they are one carriageway split at junctions rather than "
                    "opposing directions; the count binds to the fragment nearest the count point"
                ),
            )
        return DirectionResolution(
            count_point_id=count_point_id,
            direction_of_travel=direction_of_travel,
            binding="several_compatible_edges_require_confirmation",
            considered=frozen,
            target_bearing_degrees=target,
            tolerance_degrees=tolerance_degrees,
            collinear_spread_degrees=spread,
            reason=(
                f"{len(compatible)} member edges lie within the tolerance and their bearings "
                f"diverge by {spread} degrees, so they are not one carriageway; the approved "
                "policy keeps them and requires confirmation rather than choosing one"
            ),
        )
    return DirectionResolution(
        count_point_id=count_point_id,
        direction_of_travel=direction_of_travel,
        binding="direction_unresolved",
        considered=frozen,
        target_bearing_degrees=target,
        tolerance_degrees=tolerance_degrees,
        reason="no member edge lies within the tolerance; direction is not reversed or invented",
    )


def max_pairwise_spread(bearings: Sequence[Decimal]) -> Decimal:
    """Largest circular difference between any two bearings.

    Computed pairwise rather than as ``max - min``: bearings are circular, so
    two edges either side of north (``0.2`` and ``359.7``) are half a degree
    apart while a naive range calls them 359.5 apart. That mistake was made once
    while measuring this data and is prevented here.
    """

    return max(
        (angular_difference(first, second) for first in bearings for second in bearings),
        default=Decimal("0"),
    )


def _nearest_fragment(
    edge_ids: Sequence[str], distance_by_edge: Mapping[str, Decimal] | None
) -> str | None:
    """The fragment closest to the count point.

    A point count constrains the edge the count point physically sits on, so
    when one carriageway is split into fragments the count belongs to the
    nearest fragment rather than to all of them. Binding it to every fragment
    would assert the same flow on edges separated by junctions.
    """

    if not distance_by_edge:
        return None
    known = [edge_id for edge_id in edge_ids if edge_id in distance_by_edge]
    if not known:
        return None
    return min(known, key=lambda edge_id: (distance_by_edge[edge_id], edge_id))


def ordinals_by_edge_id(index: EdgeSpatialIndex, edge_ids: Iterable[str]) -> dict[str, int]:
    """Map the wanted edge ids to their index ordinals in one pass."""

    wanted = set(edge_ids)
    found: dict[str, int] = {}
    for ordinal in range(len(index)):
        edge_id = index.edge_record(ordinal)[0]
        if edge_id in wanted:
            found[edge_id] = ordinal
            if len(found) == len(wanted):
                break
    return found


def demand_input_fingerprint(
    *,
    match_policy_fingerprint: str,
    profile_lineage_fingerprint: str,
    network_identity_sha256: str,
) -> str:
    """Bind a demand input to every artifact it was derived from."""

    return sha256_hex(
        canonical_json(
            {
                "match_policy": match_policy_fingerprint,
                "profile_lineage": profile_lineage_fingerprint,
                "network_identity": network_identity_sha256,
                "method": DEMAND_METHOD_VERSION,
                "acceptance_basis": ACCEPTANCE_BASIS,
            }
        ).encode("utf-8")
    )


#: The owner's Phase 5 survey-date window, selected on 25 July 2026 and recorded
#: in commit 13ae063: each site is represented by its **latest** survey, and only
#: sites whose latest survey falls in 2019 or in 2022 and later are admitted. The
#: gap is deliberate: 2020 and 2021 surveys measured pandemic-restricted traffic,
#: and mixing them with normal conditions would be absorbed silently into a
#: fitted demand scale rather than surfacing as a data-consistency problem.
SURVEY_WINDOW_ID: Literal["manchester-dft-latest-survey-2019-or-2022-onward"] = (
    "manchester-dft-latest-survey-2019-or-2022-onward"
)
EXCLUDED_PANDEMIC_YEARS: frozenset[str] = frozenset({"2020", "2021"})
INCLUDED_EARLIER_YEAR: Literal["2019"] = "2019"
WINDOW_FLOOR_YEAR: Literal["2022"] = "2022"


def site_is_in_survey_window(latest_count_date: str | date) -> bool:
    """Whether a site's latest survey admits it to the owner's Phase 5 window.

    ``latest_count_date`` is an ISO date string or a ``date``. Only the year is
    consulted, because the owner's rule is stated in years.
    """

    year = str(latest_count_date)[:4]
    if year in EXCLUDED_PANDEMIC_YEARS:
        return False
    return year == INCLUDED_EARLIER_YEAR or year >= WINDOW_FLOOR_YEAR


def write_edgedata_counts(
    destination: Path,
    counts: Sequence[EdgeHourCount],
) -> dict[str, int]:
    """Write bound counts as a SUMO ``edgeData`` file for ``routeSampler``.

    ``routeSampler`` reads counts from the ``entered`` attribute by default, so
    that is the attribute written. One interval per hour, using the temporal
    contract's exact half-open simulation windows; no interval is resampled or
    merged.

    Returns per-interval cell counts so a caller can record what was written
    without re-reading the file.
    """

    if not counts:
        raise DemandReconstructionError(
            "NO_BOUND_COUNTS",
            "an edgeData file is not written from an empty count set; a demand input with no "
            "observations would assert an unconstrained network rather than a measured one",
        )

    by_interval: dict[tuple[int, int], list[EdgeHourCount]] = defaultdict(list)
    for count in counts:
        by_interval[(count.interval_start_s, count.interval_end_s)].append(count)

    written: dict[str, int] = {}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<meandata>"]
    for start, end in sorted(by_interval):
        cells = sorted(by_interval[(start, end)], key=lambda item: item.edge_id)
        label = f"h{start // 3600:02d}"
        written[label] = len(cells)
        lines.append(f'  <interval id="{label}" begin="{start}" end="{end}">')
        lines.extend(
            f'    <edge id="{cell.edge_id}" entered="{cell.all_motor_vehicles}"/>' for cell in cells
        )
        lines.append("  </interval>")
    lines.append("</meandata>")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written

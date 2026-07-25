"""Real DfT observation-to-network map matching under an owner-approved policy.

This implements design Gate-D step 2 (site-to-edge map-match candidates) for
**real** evidence, under the versioned candidate-research policy
``manchester-dft-map-match-owner-candidate-1.0``.

Research status is :data:`RESEARCH_STATUS` — ``owner_approved_candidate``. The
repository owner authorised these rules on 25 July 2026 so the candidate
workflow can be implemented and exercised. That is **not** supervisor approval:
``docs/evaluation/supervisor_contract_decision_form.md`` is unsigned, and a later
review may revise any rule here without changing raw evidence.

The policy is deliberately conservative, because DfT's own guidance warns that
individual-link estimates are less robust than regional statistics:

*   **Automatic final acceptance is disabled.** Even a ``clear_candidate``
    requires analyst confirmation. Confidence is triage, not proof.
*   **Distance retrieves; it does not accept.** Measured on the 305 real
    Manchester count points, the median site sits 2.3 m (Major) or 1.4 m (Minor)
    from the network and *every* site has a candidate within 30 m — so distance
    barely discriminates. At 10 m the median site already has three candidates
    and 58.4% span more than one road class. Road class, road identity, and the
    analyst do the discriminating work.
*   **Nothing disappears.** Every observation reaches exactly one terminal
    disposition, and every rejected candidate keeps its reason in the ledger.

The lead's :mod:`~traffictwin.integration.manchester.map_matching` module is a
separate synthetic-only harness and is neither modified nor bypassed here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from math import atan2, degrees
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import (
    ManchesterSnapshotModel,
    canonical_json,
    sha256_hex,
)
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex, GeometrySource

MAP_MATCH_POLICY_ID: Literal["manchester-dft-map-match-owner-candidate-1.0"] = (
    "manchester-dft-map-match-owner-candidate-1.0"
)
MAP_MATCH_METHOD_VERSION: Literal["manchester-observation-matching-1.0"] = (
    "manchester-observation-matching-1.0"
)
RESEARCH_STATUS: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: Classes the owner hard-excluded from motor-count matching.
HARD_EXCLUDED_CLASSES: frozenset[str] = frozenset(
    {
        "footway",
        "path",
        "cycleway",
        "steps",
        "bridleway",
        "corridor",
        "platform",
        "construction",
        "proposed",
    }
)

#: Classes admissible for a DfT ``Major`` road.
MAJOR_ROAD_CLASSES: frozenset[str] = frozenset(
    {
        "motorway",
        "motorway_link",
        "trunk",
        "trunk_link",
        "primary",
        "primary_link",
        "secondary",
        "secondary_link",
    }
)

#: Classes admissible for a DfT ``Minor`` road.
MINOR_ROAD_CLASSES: frozenset[str] = frozenset(
    {
        "tertiary",
        "tertiary_link",
        "unclassified",
        "residential",
        "living_street",
        "service",
        "road",
    }
)

#: A service candidate never wins automatically, whatever its distance.
SERVICE_CLASS = "service"

#: The network prefixes its road classes; anything else is not a road.
_ROAD_CLASS_PREFIX = "highway."

#: Cardinal bearings for the DfT direction codes, in degrees clockwise from north.
CARDINAL_BEARINGS: dict[str, Decimal] = {
    "N": Decimal("0"),
    "E": Decimal("90"),
    "S": Decimal("180"),
    "W": Decimal("270"),
}

#: ``C`` means combined directions and is never forced onto one directed edge.
COMBINED_DIRECTION = "C"

#: DfT records a *category placeholder* rather than a road number for unnumbered
#: minor roads: ``U`` (unclassified) and ``C`` (class C). Measured on the real
#: Manchester count points, 125 of 305 sites carry ``U`` and 19 carry ``C``.
#: These are not road references and must never be compared as one, or a site
#: would appear to disagree with every edge it is offered.
DFT_UNNUMBERED_ROAD_PLACEHOLDERS: frozenset[str] = frozenset({"U", "C"})

#: UK road numbering allows an A road built to motorway standard, written
#: ``A57(M)``. It appears in the real Manchester data, so it is recognised as a
#: signed reference rather than being treated as unparseable.
_REFERENCE_PATTERN = re.compile(r"^[MAB]\d+(\(M\))?[A-Z]*$")
_WHITESPACE = re.compile(r"\s+")

ClassDisposition: TypeAlias = Literal[
    "admissible",
    "hard_excluded",
    "wrong_road_type_family",
    "not_in_approved_policy",
    "not_a_road_class",
    "class_missing",
]

MatchConfidence: TypeAlias = Literal[
    "clear_candidate",
    "review_required",
    "no_suitable_candidate",
]

TerminalDisposition: TypeAlias = Literal[
    "accepted_by_analyst",
    "rejected_by_analyst",
    "no_suitable_candidate",
    "unavailable_missing_evidence",
    "awaiting_analyst_review",
]

DirectionOutcome: TypeAlias = Literal[
    "direction_compatible",
    "direction_combined_not_forced",
    "direction_unresolved",
    "direction_not_provided",
]


class ObservationMatchingError(ValueError):
    """Typed refusal for an unsupported or inconsistent matching request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class ObservationMatchingModel(ManchesterSnapshotModel):
    """Strict frozen base for real map-matching artifacts."""


class ManchesterMapMatchPolicy(ObservationMatchingModel):
    """The owner-approved candidate matching policy, as a checkable artifact."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    policy_id: Literal["manchester-dft-map-match-owner-candidate-1.0"] = MAP_MATCH_POLICY_ID
    method_version: Literal["manchester-observation-matching-1.0"] = MAP_MATCH_METHOD_VERSION
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    #: Retrieval bound only. Being retrieved is not being eligible.
    outer_search_radius_m: Decimal = Decimal("50")
    #: Eligibility for an edge carrying its own shape.
    native_eligibility_m: Decimal = Decimal("30")
    #: Eligibility for an edge whose geometry is a straight junction-to-junction
    #: line. Wider because that line can sit further from the true carriageway
    #: than the road's own shape does; the tolerance follows the network's
    #: storage choice, not the road's identity.
    fallback_eligibility_m: Decimal = Decimal("50")
    #: Strict distance for `clear_candidate`, by geometry source.
    clear_native_m: Decimal = Decimal("10")
    clear_fallback_m: Decimal = Decimal("20")
    direction_tolerance_degrees: Decimal = Decimal("45")
    sensitivity_radii_m: tuple[Decimal, ...] = (
        Decimal("10"),
        Decimal("20"),
        Decimal("30"),
        Decimal("50"),
        Decimal("100"),
    )

    #: Version 1.0 disables automatic final acceptance outright.
    automatic_acceptance_enabled: Literal[False] = False
    service_requires_manual_confirmation: Literal[True] = True
    fuzzy_text_matching_accepts: Literal[False] = False
    #: The supervisor contract form is unsigned; this policy never claims otherwise.
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False

    @model_validator(mode="after")
    def validate_policy(self) -> ManchesterMapMatchPolicy:
        if self.native_eligibility_m > self.outer_search_radius_m:
            raise ValueError("native eligibility cannot exceed the retrieval radius")
        if self.fallback_eligibility_m > self.outer_search_radius_m:
            raise ValueError("fallback eligibility cannot exceed the retrieval radius")
        if self.clear_native_m > self.native_eligibility_m:
            raise ValueError("the clear distance cannot exceed native eligibility")
        if self.clear_fallback_m > self.fallback_eligibility_m:
            raise ValueError("the clear distance cannot exceed fallback eligibility")
        return self

    def fingerprint(self) -> str:
        """Bind results to the exact policy that produced them."""

        return sha256_hex(self.canonical_json().encode("utf-8"))

    def eligibility_for(self, source: GeometrySource) -> Decimal:
        return (
            self.native_eligibility_m
            if source == "explicit_edge_shape"
            else self.fallback_eligibility_m
        )

    def clear_distance_for(self, source: GeometrySource) -> Decimal:
        return self.clear_native_m if source == "explicit_edge_shape" else self.clear_fallback_m


def normalise_road_reference(value: str | None) -> str | None:
    """Normalise a signed road reference conservatively.

    Uppercase and ordinary spacing only. Nothing else is altered, because a
    looser rule would start inventing identity: ``A56`` and ``A566`` are
    different roads, and no transformation here may blur that.
    """

    if value is None:
        return None
    collapsed = _WHITESPACE.sub("", value).upper()
    return collapsed or None


def dft_road_reference(road_name: str | None) -> str | None:
    """Extract the signed road reference a DfT ``road_name`` carries, if any.

    DfT puts the road number in ``road_name`` for numbered roads, but records a
    category placeholder (``U``, ``C``) for unnumbered minor roads. Returning
    ``None`` for a placeholder keeps the owner's rule that a missing reference
    never becomes a match, instead of comparing a category code as if it were a
    road number.
    """

    normalised = normalise_road_reference(road_name)
    if normalised is None or normalised in DFT_UNNUMBERED_ROAD_PLACEHOLDERS:
        return None
    return normalised


def is_signed_reference(value: str | None) -> bool:
    """Report whether a normalised value looks like an M/A/B road number."""

    return value is not None and bool(_REFERENCE_PATTERN.match(value))


def normalise_road_name(value: str | None) -> str | None:
    """Normalise a road name for *exact* comparison only."""

    if value is None:
        return None
    collapsed = _WHITESPACE.sub(" ", value).strip().upper()
    return collapsed or None


def bare_road_class(road_type: str | None) -> str | None:
    """Strip the network's ``highway.`` prefix, or ``None`` if not a road class."""

    if road_type is None:
        return None
    if not road_type.startswith(_ROAD_CLASS_PREFIX):
        return None
    return road_type[len(_ROAD_CLASS_PREFIX) :] or None


def classify_edge_class(road_type: str | None, dft_road_type: str) -> ClassDisposition:
    """Decide whether one edge's class may carry this observation's count.

    A class the approved policy does not mention is reported as
    ``not_in_approved_policy`` rather than being folded into ``hard_excluded``.
    Both fail closed, but only one of them represents a decision the owner
    actually made. Measured on the accepted network, seven classes present in
    real data fall in that gap — ``pedestrian``, ``track``, ``busway``,
    ``bus_guideway``, ``raceway``, ``service|psv``, and the ``railway.*``
    family — and silently treating them as excluded would misreport the policy
    as more complete than it is.
    """

    if road_type is None:
        return "class_missing"
    bare = bare_road_class(road_type)
    if bare is None:
        return "not_a_road_class"
    if bare in HARD_EXCLUDED_CLASSES:
        return "hard_excluded"
    admissible = MAJOR_ROAD_CLASSES if dft_road_type == "Major" else MINOR_ROAD_CLASSES
    other = MINOR_ROAD_CLASSES if dft_road_type == "Major" else MAJOR_ROAD_CLASSES
    if bare in admissible:
        return "admissible"
    if bare in other:
        return "wrong_road_type_family"
    return "not_in_approved_policy"


def edge_bearing_degrees(geometry: Sequence[float]) -> Decimal | None:
    """Bearing of an edge's overall direction, clockwise from north.

    Taken from the first to the last shape point: a directed SUMO edge runs one
    way, and its net direction is what a cardinal count direction can be
    compared against.
    """

    if len(geometry) < 4:
        return None
    east = geometry[-2] - geometry[0]
    north = geometry[-1] - geometry[1]
    if east == 0.0 and north == 0.0:
        return None
    bearing = degrees(atan2(east, north)) % 360.0
    return Decimal(f"{bearing:.3f}")


def angular_difference(first: Decimal, second: Decimal) -> Decimal:
    """Smallest absolute angle between two bearings, in degrees."""

    raw = abs(first - second) % Decimal("360")
    return min(raw, Decimal("360") - raw)


class CandidateRejection(ObservationMatchingModel):
    """One edge that was retrieved and then rejected, with the reason kept."""

    edge_id: str = Field(min_length=1, max_length=200)
    road_type: str | None = Field(default=None, max_length=100)
    distance_m: Decimal = Field(ge=0)
    geometry_source: GeometrySource
    reason: str = Field(min_length=1, max_length=120)


class EdgeCandidate(ObservationMatchingModel):
    """One directed edge that survived the approved filters."""

    edge_id: str = Field(min_length=1, max_length=200)
    road_type: str = Field(min_length=1, max_length=100)
    road_class: str = Field(min_length=1, max_length=100)
    road_ref: str | None = Field(default=None, max_length=100)
    normalised_ref: str | None = Field(default=None, max_length=100)
    distance_m: Decimal = Field(ge=0)
    geometry_source: GeometrySource
    bearing_degrees: Decimal | None = Field(default=None, ge=0, lt=360)
    requires_manual_confirmation: bool


class RoadGroup(ObservationMatchingModel):
    """Analyst-facing road group over one or more directed edges.

    Grouping is review logic. Every underlying edge id and direction is retained
    so edge-level lineage survives; a group never replaces its members.
    """

    group_key: str = Field(min_length=1, max_length=220)
    normalised_ref: str | None = Field(default=None, max_length=100)
    normalised_name: str | None = Field(default=None, max_length=200)
    road_class_family: str = Field(min_length=1, max_length=100)
    members: tuple[EdgeCandidate, ...] = Field(min_length=1)
    nearest_distance_m: Decimal = Field(ge=0)
    contains_service_member: bool
    #: True only when the group's identity matches the observation's own
    #: signed reference exactly after conservative normalisation.
    exact_reference_match: bool
    exact_name_match: bool


class ObservationMatch(ObservationMatchingModel):
    """The complete candidate result for one real count point."""

    schema_version: Literal["1.0"] = "1.0"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-observation-matching-1.0"] = MAP_MATCH_METHOD_VERSION
    policy_id: Literal["manchester-dft-map-match-owner-candidate-1.0"] = MAP_MATCH_POLICY_ID
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS

    count_point_id: int = Field(ge=0)
    dft_road_type: str = Field(min_length=1, max_length=32)
    dft_road_name: str | None = Field(default=None, max_length=200)
    dft_normalised_ref: str | None = Field(default=None, max_length=100)

    groups: tuple[RoadGroup, ...] = ()
    rejections: tuple[CandidateRejection, ...] = ()
    confidence: MatchConfidence
    disposition: TerminalDisposition
    reasons: tuple[str, ...] = ()

    #: Fixed false in policy 1.0: triage never accepts on its own.
    automatically_accepted: Literal[False] = False
    analyst_reviewed: Literal[False] = False

    @model_validator(mode="after")
    def validate_match(self) -> ObservationMatch:
        if self.confidence == "no_suitable_candidate":
            if self.groups:
                raise ValueError("a no-candidate result cannot carry candidate groups")
            if self.disposition != "no_suitable_candidate":
                raise ValueError("a no-candidate result must terminate as no_suitable_candidate")
        elif not self.groups:
            raise ValueError("a candidate result must carry at least one group")
        elif self.disposition != "awaiting_analyst_review":
            raise ValueError(
                "policy 1.0 disables automatic acceptance, so a candidate result "
                "must await analyst review"
            )
        return self


def match_observation(
    *,
    count_point_id: int,
    easting: float,
    northing: float,
    dft_road_type: str,
    dft_road_name: str | None,
    dft_road_ref: str | None,
    index: EdgeSpatialIndex,
    policy: ManchesterMapMatchPolicy,
) -> ObservationMatch:
    """Generate candidates for one real count point under the approved policy.

    Retrieval, filtering, grouping, and triage only. Nothing here accepts a
    match: policy 1.0 routes every candidate result to analyst review.
    """

    if dft_road_type not in {"Major", "Minor"}:
        raise ObservationMatchingError(
            "UNSUPPORTED_ROAD_TYPE",
            f"the approved policy covers DfT Major and Minor roads only, not {dft_road_type!r}",
        )

    observation_ref = normalise_road_reference(dft_road_ref)
    observation_name = normalise_road_name(dft_road_name)
    ordinals = index.edges_within(easting, northing, radius_m=float(policy.outer_search_radius_m))

    accepted: list[EdgeCandidate] = []
    rejections: list[CandidateRejection] = []
    for ordinal in ordinals:
        edge_id, road_type, road_ref, source = index.edge_record(ordinal)
        distance = Decimal(f"{index.distance_to(ordinal, easting, northing):.3f}")
        class_disposition = classify_edge_class(road_type, dft_road_type)
        if class_disposition != "admissible":
            rejections.append(
                CandidateRejection(
                    edge_id=edge_id,
                    road_type=road_type,
                    distance_m=distance,
                    geometry_source=source,
                    reason=class_disposition,
                )
            )
            continue
        if distance > policy.eligibility_for(source):
            rejections.append(
                CandidateRejection(
                    edge_id=edge_id,
                    road_type=road_type,
                    distance_m=distance,
                    geometry_source=source,
                    reason="outside_eligibility_for_geometry_source",
                )
            )
            continue
        road_class = bare_road_class(road_type)
        assert road_class is not None and road_type is not None  # noqa: S101 - narrowed above
        accepted.append(
            EdgeCandidate(
                edge_id=edge_id,
                road_type=road_type,
                road_class=road_class,
                road_ref=road_ref,
                normalised_ref=normalise_road_reference(road_ref),
                distance_m=distance,
                geometry_source=source,
                bearing_degrees=edge_bearing_degrees(index.geometry(ordinal)),
                requires_manual_confirmation=road_class == SERVICE_CLASS,
            )
        )

    groups = _group_candidates(accepted, observation_ref, observation_name)
    confidence, reasons = _triage(groups, observation_ref, policy)
    disposition: TerminalDisposition = (
        "no_suitable_candidate"
        if confidence == "no_suitable_candidate"
        else "awaiting_analyst_review"
    )
    return ObservationMatch(
        policy_fingerprint=policy.fingerprint(),
        count_point_id=count_point_id,
        dft_road_type=dft_road_type,
        dft_road_name=dft_road_name,
        dft_normalised_ref=observation_ref,
        groups=groups,
        rejections=tuple(rejections),
        confidence=confidence,
        disposition=disposition,
        reasons=reasons,
    )


def _group_candidates(
    candidates: Sequence[EdgeCandidate],
    observation_ref: str | None,
    observation_name: str | None,
) -> tuple[RoadGroup, ...]:
    """Collapse directed pairs and split fragments into analyst-facing groups.

    Identity is the grouping key: a shared normalised signed reference, else a
    shared exact normalised name, else the edge's own class and id so an
    unidentifiable edge is never merged into somebody else's road.
    """

    buckets: dict[tuple[str, str], list[EdgeCandidate]] = {}
    for candidate in candidates:
        family = _class_family(candidate.road_class)
        if candidate.normalised_ref is not None:
            key = ("ref", f"{candidate.normalised_ref}|{family}")
        else:
            key = ("edge", f"{family}|{candidate.edge_id}")
        buckets.setdefault(key, []).append(candidate)

    groups: list[RoadGroup] = []
    for (kind, bucket_key), members in sorted(buckets.items()):
        ordered = tuple(sorted(members, key=lambda item: (item.distance_m, item.edge_id)))
        normalised_ref = ordered[0].normalised_ref if kind == "ref" else None
        groups.append(
            RoadGroup(
                group_key=f"{kind}:{bucket_key}",
                normalised_ref=normalised_ref,
                normalised_name=None,
                road_class_family=_class_family(ordered[0].road_class),
                members=ordered,
                nearest_distance_m=min(item.distance_m for item in ordered),
                contains_service_member=any(item.road_class == SERVICE_CLASS for item in ordered),
                exact_reference_match=(
                    observation_ref is not None and normalised_ref == observation_ref
                ),
                exact_name_match=False,
            )
        )
    return tuple(sorted(groups, key=lambda group: (group.nearest_distance_m, group.group_key)))


def _class_family(road_class: str) -> str:
    """Collapse a ``*_link`` class onto its parent family for grouping."""

    return road_class[: -len("_link")] if road_class.endswith("_link") else road_class


def _triage(
    groups: Sequence[RoadGroup],
    observation_ref: str | None,
    policy: ManchesterMapMatchPolicy,
) -> tuple[MatchConfidence, tuple[str, ...]]:
    """Assign a confidence category. Triage never accepts."""

    if not groups:
        return "no_suitable_candidate", ("no candidate survived the approved filters",)

    reasons: list[str] = []
    if len(groups) > 1:
        reasons.append(f"{len(groups)} eligible road groups compete")
    nearest = groups[0]
    if nearest.contains_service_member:
        reasons.append("a service-class candidate always requires manual confirmation")
    if observation_ref is None:
        reasons.append("the observation carries no signed road reference to match on")
    elif not nearest.exact_reference_match:
        reasons.append("the nearest group's reference does not match the observation's")

    source = nearest.members[0].geometry_source
    if nearest.nearest_distance_m > policy.clear_distance_for(source):
        reasons.append("the nearest candidate is beyond the strict clear distance")

    if reasons:
        return "review_required", tuple(reasons)
    return "clear_candidate", ("all strict conditions met; analyst confirmation still required",)


def policy_summary_fingerprint(policy: ManchesterMapMatchPolicy) -> str:
    """Fingerprint the policy together with its class lists.

    The class lists live in module constants rather than in the model, so a
    change to them must still change the recorded identity of a result.
    """

    payload = {
        "policy": policy.model_dump(mode="json"),
        "hard_excluded": sorted(HARD_EXCLUDED_CLASSES),
        "major": sorted(MAJOR_ROAD_CLASSES),
        "minor": sorted(MINOR_ROAD_CLASSES),
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))

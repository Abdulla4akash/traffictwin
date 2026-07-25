"""Exploratory owner-policy v1.1 for real DfT observation-to-network matching.

Policy ``manchester-dft-map-match-owner-policy-1.1`` revises the owner-approved
candidate policy v1.0 in :mod:`observation_matching`.  That module is **frozen
and imported, never rewritten**: the v1.0-versus-v1.1 reconciliation below has to
compare two implementations to be exact, and mutating v1.0 in place would leave
nothing to compare against.

**This is exploratory candidate software evidence.**  It is not supervisor
approval and not scientific validation.
``docs/evaluation/supervisor_contract_decision_form.md`` remains unsigned, and a
later review may revise every rule here without changing any raw evidence.

What v1.1 changes, and why
==========================

Running v1.0 over the 305 real Manchester count points left 21 sites with no
suitable candidate.  Several sit on the **A56** and the **A6042** with a rejected
edge less than a metre away — the nearest for one A56 site is 0.880 m — because
DfT calls the count point ``Major`` while OpenStreetMap tags that stretch of the
numbered A road as a minor class.  The hard family split rejected an edge whose
*road identity matched exactly*.

DfT ``road_type`` and the OSM ``highway`` class are independent classifications,
so they disagree without either being wrong.  v1.1 therefore lets an **exact
normalised signed-road-reference match** override the family split alone, under
guards that are all required together:

*   the candidate must **permit motor vehicles**;
*   the distance must be **at most 5 m**, far tighter than v1.0's eligibility;
*   the signed reference must identify **exactly one** nearby *exact-reference*
    road group — nearby groups carrying no reference cannot make it non-unique;
*   the family mismatch is **preserved and displayed**, never repaired away;
*   the reason ``exact_reference_family_override`` is recorded on the row.

Readmission is not application
==============================

A candidate that passes every per-candidate guard is **readmitted** past the
family filter and becomes visible for review.  That is audit evidence.  The
override is **applied** only on a row it actually accepts, and the two are
counted separately throughout: a strict-path row and a review row may both carry
readmitted candidates while applying nothing.

Missing evidence is not absence
===============================

A candidate that satisfies every other guard but whose motor-vehicle access the
network cannot supply leaves its site ``unavailable_missing_evidence``, never
``no_suitable_candidate``.  The first is a gap in what we know; the second is a
statement about the road, and reporting one as the other would be a false claim.

What the override never does
============================

*   It never uses a fuzzy name.  Only an exact normalised reference qualifies:
    ``A56`` and ``A566`` are different roads and no transformation here may blur
    that.
*   It never fires when several exact-reference groups remain — competing
    identities are ambiguity, and ambiguity goes to review.
*   It relaxes the **family split only**.  A hard-excluded class, a class outside
    the approved lists, a non-road class, and a candidate beyond the override
    distance all stay rejected exactly as in v1.0.
*   It never overrides v1.0's standing service-road rule: a group containing a
    ``service`` member still requires manual confirmation and can never be
    accepted by policy.

Acceptance vocabulary
=====================

v1.1 may mark a row ``owner_policy_accepted_candidate``.  That label means the
owner's written policy accepted it.  It is **not** human acceptance, **not**
analyst acceptance, and **not** supervisor approval; the artifact fixes all three
to false structurally so no consumer can read it otherwise.  A manual review
queue is preserved for everything the policy did not accept.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal, TypeAlias

from pydantic import Field, model_validator

from traffictwin.integration.manchester.models import canonical_json, sha256_hex
from traffictwin.integration.manchester.network_connectivity import MotorAccess
from traffictwin.integration.manchester.network_geometry import EdgeSpatialIndex, GeometrySource
from traffictwin.integration.manchester.observation_matching import (
    SERVICE_CLASS,
    CandidateRejection,
    EdgeCandidate,
    ManchesterMapMatchPolicy,
    MatchConfidence,
    ObservationMatch,
    ObservationMatchingError,
    ObservationMatchingModel,
    bare_road_class,
    classify_edge_class,
    is_signed_reference,
    match_observation,
    normalise_road_reference,
)

MAP_MATCH_POLICY_V11_ID: Literal["manchester-dft-map-match-owner-policy-1.1"] = (
    "manchester-dft-map-match-owner-policy-1.1"
)
MAP_MATCH_METHOD_V11: Literal["manchester-observation-matching-1.1"] = (
    "manchester-observation-matching-1.1"
)
RESEARCH_STATUS_V11: Literal["owner_approved_candidate"] = "owner_approved_candidate"

#: The only rejection reason the override may reverse.  Naming it as a constant
#: keeps the narrowness of the override checkable rather than conventional.
OVERRIDABLE_REJECTION_REASON: Literal["wrong_road_type_family"] = "wrong_road_type_family"

#: Access levels that count as permitting a motor vehicle.
MOTOR_PERMITTING_ACCESS: frozenset[str] = frozenset({"passenger_car", "motor_vehicle_no_car"})

AcceptancePath: TypeAlias = Literal["strict_v1_0_clear", "exact_reference_family_override"]

TerminalDispositionV11: TypeAlias = Literal[
    "owner_policy_accepted_candidate",
    "awaiting_manual_review",
    "no_suitable_candidate",
    "unavailable_missing_evidence",
]

OverrideRefusal: TypeAlias = Literal[
    "reference_absent",
    "reference_not_signed",
    "reference_not_exact",
    "class_not_family_mismatch",
    "beyond_override_distance",
    "motor_access_unknown",
    "does_not_permit_motor_vehicles",
    "several_exact_reference_groups",
    "service_class_requires_manual_confirmation",
    "strict_path_already_accepted",
]

#: The only refusal that means *we could not find out*, as opposed to *we found
#: out and the answer was no*.  Typed separately so a row can never claim to be
#: unavailable through missing evidence on the strength of a refusal that
#: actually settled the question.
MissingEvidence: TypeAlias = Literal["motor_access_unknown"]


def permits_motor_vehicles(access: MotorAccess | None) -> bool:
    """Whether an access level admits a motor vehicle.

    ``None`` means the network could not tell us, and an unknown is never an
    assumed yes: the override fails closed instead.
    """

    return access is not None and access in MOTOR_PERMITTING_ACCESS


class ManchesterMapMatchPolicyV11(ObservationMatchingModel):
    """The exploratory owner policy v1.1, as a checkable artifact."""

    schema_version: Literal["1.1"] = "1.1"
    capability_id: Literal["MAN-09"] = "MAN-09"
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    method_version: Literal["manchester-observation-matching-1.1"] = MAP_MATCH_METHOD_V11
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS_V11
    supersedes_policy_id: Literal["manchester-dft-map-match-owner-candidate-1.0"] = (
        "manchester-dft-map-match-owner-candidate-1.0"
    )

    #: v1.1 inherits every v1.0 search and eligibility value unchanged; only the
    #: override below is new, so a difference between the two runs can only come
    #: from the override.
    base: ManchesterMapMatchPolicy = ManchesterMapMatchPolicy()

    exact_reference_family_override_enabled: Literal[True] = True
    #: Deliberately far tighter than v1.0 eligibility. The override trades a
    #: class disagreement against physical proximity, so the proximity has to be
    #: strong enough that the trade is not a guess.
    override_max_distance_m: Decimal = Decimal("5")
    override_requires_motor_vehicle_access: Literal[True] = True
    #: The match must be on a **signed** M/A/B road reference, not merely on
    #: identical text. Two identical road names are not road identity in the way
    #: a road number is, and normalisation alone cannot tell them apart.
    override_requires_signed_reference: Literal[True] = True
    #: The authorised uniqueness guard, and the only one: the signed reference
    #: must identify exactly one nearby **exact-reference** road group. Nearby
    #: groups that do not carry the reference do not make it non-unique; they
    #: are preserved on the row for review and audit, never used to block.
    override_requires_unique_reference_group: Literal[True] = True
    override_uses_fuzzy_names: Literal[False] = False
    #: The override relaxes the family split and nothing else.
    override_relaxes_only: Literal["wrong_road_type_family"] = OVERRIDABLE_REJECTION_REASON
    #: v1.0's standing rule survives v1.1 unchanged.
    service_requires_manual_confirmation: Literal[True] = True

    #: Owner policy may accept a row. A human never did.
    owner_policy_acceptance_enabled: Literal[True] = True
    analyst_accepted: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    exploratory_candidate_software_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> ManchesterMapMatchPolicyV11:
        if self.override_max_distance_m <= 0:
            raise ValueError("the override distance must be a positive distance")
        if self.override_max_distance_m > self.base.clear_native_m:
            raise ValueError(
                "the override distance must not exceed the strict clear distance; "
                "an override is a tighter claim than a clear match, never a looser one"
            )
        return self

    def fingerprint(self) -> str:
        """Bind results to the exact policy that produced them."""

        return sha256_hex(self.canonical_json().encode("utf-8"))


class ExactReferenceOverride(ObservationMatchingModel):
    """One candidate readmitted by the exact-reference override.

    The family mismatch that v1.0 rejected on is **kept on the record**. The
    override is a decision to proceed despite a disagreement, not a finding that
    the disagreement was not real, and a row that hid it would misrepresent
    which of the two classifications was trusted.
    """

    edge_id: str = Field(min_length=1, max_length=200)
    road_type: str = Field(min_length=1, max_length=100)
    road_class: str = Field(min_length=1, max_length=100)
    normalised_ref: str = Field(min_length=1, max_length=100)
    distance_m: Decimal = Field(ge=0)
    geometry_source: GeometrySource
    motor_access: MotorAccess
    #: The preserved disagreement, in words, for display.
    family_mismatch: str = Field(min_length=1, max_length=300)
    dft_road_type: str = Field(min_length=1, max_length=32)
    osm_class_family: str = Field(min_length=1, max_length=100)
    reason: Literal["exact_reference_family_override"] = "exact_reference_family_override"
    matched_on_exact_reference: Literal[True] = True
    matched_on_fuzzy_name: Literal[False] = False


class OverrideConsidered(ObservationMatchingModel):
    """One family-rejected candidate the override examined and refused.

    Refusals are published as well as acceptances, so the override's narrowness
    is auditable rather than asserted.
    """

    edge_id: str = Field(min_length=1, max_length=200)
    road_type: str | None = Field(default=None, max_length=100)
    distance_m: Decimal = Field(ge=0)
    refusal: OverrideRefusal


class RoadGroupV11(ObservationMatchingModel):
    """Analyst-facing road group, which may contain override-readmitted members."""

    group_key: str = Field(min_length=1, max_length=220)
    normalised_ref: str | None = Field(default=None, max_length=100)
    road_class_family: str = Field(min_length=1, max_length=100)
    members: tuple[EdgeCandidate, ...] = Field(min_length=1)
    nearest_distance_m: Decimal = Field(ge=0)
    contains_service_member: bool
    exact_reference_match: bool
    #: True when every member entered through the override.
    admitted_by_override: bool
    family_mismatch: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_group(self) -> RoadGroupV11:
        if self.admitted_by_override and self.family_mismatch is None:
            raise ValueError("an override group must preserve the family mismatch it overrode")
        if self.admitted_by_override and not self.exact_reference_match:
            raise ValueError("the override exists only for an exact signed-reference match")
        return self


class ObservationMatchV11(ObservationMatchingModel):
    """The complete v1.1 result for one real count point."""

    schema_version: Literal["1.1"] = "1.1"
    capability_id: Literal["MAN-09"] = "MAN-09"
    method_version: Literal["manchester-observation-matching-1.1"] = MAP_MATCH_METHOD_V11
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    policy_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    research_status: Literal["owner_approved_candidate"] = RESEARCH_STATUS_V11

    count_point_id: int = Field(ge=0)
    dft_road_type: str = Field(min_length=1, max_length=32)
    dft_road_name: str | None = Field(default=None, max_length=200)
    dft_normalised_ref: str | None = Field(default=None, max_length=100)

    groups: tuple[RoadGroupV11, ...] = ()
    #: The complete v1.0 rejection ledger, kept whole. An override readmits a
    #: candidate without erasing the record that it was rejected first.
    rejections: tuple[CandidateRejection, ...] = ()
    #: Candidates that passed every per-candidate override guard and were
    #: readmitted past the v1.0 family filter. Readmission is **audit
    #: evidence**: it makes a candidate visible for review. It is not an
    #: applied override, and counting it as one would overstate how often the
    #: override actually decided anything.
    candidates_readmitted: tuple[ExactReferenceOverride, ...] = ()
    #: The override as *applied*: populated only on a row this override
    #: actually accepted. Empty on every strict-path row and every review row.
    overrides_applied: tuple[ExactReferenceOverride, ...] = ()
    overrides_refused: tuple[OverrideConsidered, ...] = ()
    #: Why the override readmitted candidates but was not allowed to accept any
    #: of them. Recorded at row level because the reason is about the row's
    #: ambiguity, not about any single candidate.
    override_acceptance_refused: OverrideRefusal | None = None
    #: Evidence the network could not supply, which is why this row is
    #: unavailable rather than simply having no candidate. Missing evidence and
    #: absent evidence are different findings and never collapse together.
    missing_evidence: tuple[MissingEvidence, ...] = ()

    confidence: MatchConfidence
    disposition: TerminalDispositionV11
    acceptance_path: AcceptancePath | None = None
    #: Set whenever acceptance came through the override, so a downstream reader
    #: can separate the two acceptance populations without re-deriving them.
    audit_flag: bool = False
    family_mismatch: str | None = Field(default=None, max_length=300)
    reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()

    #: The owner's policy accepted this. No person did.
    analyst_accepted: Literal[False] = False
    human_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    exploratory_candidate_software_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_match(self) -> ObservationMatchV11:
        if self.disposition == "owner_policy_accepted_candidate":
            if self.acceptance_path is None:
                raise ValueError("an accepted row must record which path accepted it")
            if not self.groups:
                raise ValueError("an accepted row must carry the group it accepted")
        elif self.acceptance_path is not None:
            raise ValueError("only an accepted row may record an acceptance path")
        if self.audit_flag != (self.acceptance_path == "exact_reference_family_override"):
            raise ValueError("the audit flag marks exactly the override acceptances")
        if self.acceptance_path == "exact_reference_family_override":
            if self.family_mismatch is None:
                raise ValueError("an override acceptance must display the family mismatch")
            if not self.overrides_applied:
                raise ValueError("an override acceptance must record the override it applied")
        if self.confidence == "no_suitable_candidate":
            if self.groups:
                raise ValueError("a no-candidate result cannot carry candidate groups")
            if self.disposition not in {"no_suitable_candidate", "unavailable_missing_evidence"}:
                raise ValueError(
                    "a no-candidate result terminates as no_suitable_candidate, or as "
                    "unavailable_missing_evidence when evidence was missing rather than absent"
                )
        if (self.disposition == "unavailable_missing_evidence") != bool(self.missing_evidence):
            # Strictly biconditional: an unavailable row must name what was
            # missing, and no other disposition may claim missing evidence.
            raise ValueError(
                "an unavailable row must name the evidence that was missing, and only "
                "an unavailable row may name it; missing evidence is not the same as "
                "no candidate"
            )
        if self.disposition == "awaiting_manual_review" and not self.review_reasons:
            raise ValueError("a row sent to manual review must say why")
        if bool(self.overrides_applied) != (
            self.acceptance_path == "exact_reference_family_override"
        ):
            # Readmission is audit evidence; only an acceptance is an applied
            # override. Conflating them overstates how often the override
            # actually decided anything.
            raise ValueError(
                "overrides_applied is populated on exactly the rows the override accepted"
            )
        for applied in self.overrides_applied:
            if applied not in self.candidates_readmitted:
                raise ValueError("an applied override must also appear as a readmitted candidate")
        if (
            self.candidates_readmitted
            and self.acceptance_path != "exact_reference_family_override"
            and self.override_acceptance_refused is None
            and self.disposition != "unavailable_missing_evidence"
        ):
            raise ValueError(
                "a row that readmitted candidates without accepting one must record "
                "why the override was not allowed to accept"
            )
        if (
            self.override_acceptance_refused is not None
            and self.acceptance_path == "exact_reference_family_override"
        ):
            raise ValueError("an override acceptance cannot also record an acceptance refusal")
        return self


def _class_family(road_class: str) -> str:
    """Collapse a ``*_link`` class onto its parent family, as v1.0 does."""

    return road_class[: -len("_link")] if road_class.endswith("_link") else road_class


def _describe_mismatch(dft_road_type: str, road_class: str) -> str:
    other = "Minor" if dft_road_type == "Major" else "Major"
    return (
        f"DfT records this count point as {dft_road_type}; OpenStreetMap tags the matched "
        f"edge as highway.{road_class}, which the approved policy admits for {other} roads. "
        "The two classifications are independent and this disagreement is preserved, not repaired."
    )


def match_observation_v11(
    *,
    count_point_id: int,
    easting: float,
    northing: float,
    dft_road_type: str,
    dft_road_name: str | None,
    dft_road_ref: str | None,
    index: EdgeSpatialIndex,
    policy: ManchesterMapMatchPolicyV11,
    motor_access: Mapping[str, MotorAccess] | None = None,
) -> ObservationMatchV11:
    """Match one real count point under exploratory owner policy v1.1.

    ``motor_access`` maps edge id to the access level read from the network. It
    is required for the override: an edge whose access is unknown can never be
    overridden onto, because "we could not tell" is not "it permits traffic".
    """

    base_result = match_observation(
        count_point_id=count_point_id,
        easting=easting,
        northing=northing,
        dft_road_type=dft_road_type,
        dft_road_name=dft_road_name,
        dft_road_ref=dft_road_ref,
        index=index,
        policy=policy.base,
    )
    observation_ref = normalise_road_reference(dft_road_ref)
    lookup = motor_access if motor_access is not None else {}

    readmitted, refusals = _consider_overrides(
        rejections=base_result.rejections,
        observation_ref=observation_ref,
        dft_road_type=dft_road_type,
        policy=policy,
        index=index,
        lookup=lookup,
        easting=easting,
        northing=northing,
    )
    groups = _build_groups(base_result, readmitted, observation_ref, dft_road_type)

    return _decide(
        base_result=base_result,
        policy=policy,
        groups=groups,
        readmitted=readmitted,
        refusals=refusals,
        observation_ref=observation_ref,
        dft_road_type=dft_road_type,
        dft_road_name=dft_road_name,
    )


def _consider_overrides(
    *,
    rejections: Sequence[CandidateRejection],
    observation_ref: str | None,
    dft_road_type: str,
    policy: ManchesterMapMatchPolicyV11,
    index: EdgeSpatialIndex,
    lookup: Mapping[str, MotorAccess],
    easting: float,
    northing: float,
) -> tuple[tuple[ExactReferenceOverride, ...], tuple[OverrideConsidered, ...]]:
    """Examine every family-rejected candidate, publishing refusals too.

    Candidates that pass every per-candidate guard are **readmitted**, not
    applied. Whether the override goes on to accept the row is decided later,
    over the whole group set.
    """

    readmitted: list[ExactReferenceOverride] = []
    refused: list[OverrideConsidered] = []
    ordinals = _ordinals_by_edge_id(index, easting, northing, policy)

    for rejection in rejections:
        if rejection.reason != OVERRIDABLE_REJECTION_REASON:
            # Hard exclusions, unapproved classes, non-road classes, and
            # distance failures are outside the override entirely.
            continue
        refusal = _refuse_override(
            rejection=rejection,
            observation_ref=observation_ref,
            dft_road_type=dft_road_type,
            policy=policy,
            lookup=lookup,
            ordinals=ordinals,
            index=index,
        )
        if refusal is not None:
            refused.append(
                OverrideConsidered(
                    edge_id=rejection.edge_id,
                    road_type=rejection.road_type,
                    distance_m=rejection.distance_m,
                    refusal=refusal,
                )
            )
            continue
        road_class = bare_road_class(rejection.road_type)
        assert road_class is not None and rejection.road_type is not None  # noqa: S101
        assert observation_ref is not None  # noqa: S101 - narrowed by the refusal checks
        readmitted.append(
            ExactReferenceOverride(
                edge_id=rejection.edge_id,
                road_type=rejection.road_type,
                road_class=road_class,
                normalised_ref=observation_ref,
                distance_m=rejection.distance_m,
                geometry_source=rejection.geometry_source,
                motor_access=lookup[rejection.edge_id],
                family_mismatch=_describe_mismatch(dft_road_type, road_class),
                dft_road_type=dft_road_type,
                osm_class_family=_class_family(road_class),
            )
        )
    return (
        tuple(sorted(readmitted, key=lambda item: (item.distance_m, item.edge_id))),
        tuple(sorted(refused, key=lambda item: (item.distance_m, item.edge_id))),
    )


def _refuse_override(
    *,
    rejection: CandidateRejection,
    observation_ref: str | None,
    dft_road_type: str,
    policy: ManchesterMapMatchPolicyV11,
    lookup: Mapping[str, MotorAccess],
    ordinals: Mapping[str, int],
    index: EdgeSpatialIndex,
) -> OverrideRefusal | None:
    """Return the reason this candidate may not be overridden, or ``None``."""

    if observation_ref is None:
        return "reference_absent"
    if not is_signed_reference(observation_ref):
        # The authorised rule is a *signed road reference* match, not a text
        # match. Normalisation alone would happily equate two identical road
        # names, and "CHESTER ROAD" appearing on both sides is not evidence of
        # road identity in the way an M/A/B number is. A57(M) stays valid.
        return "reference_not_signed"
    if classify_edge_class(rejection.road_type, dft_road_type) != OVERRIDABLE_REJECTION_REASON:
        return "class_not_family_mismatch"
    ordinal = ordinals.get(rejection.edge_id)
    edge_ref = None if ordinal is None else index.edge_record(ordinal)[2]
    if normalise_road_reference(edge_ref) != observation_ref:
        # Exact normalised reference only. A fuzzy or partial name match never
        # qualifies: A56 and A566 are different roads.
        return "reference_not_exact"
    if rejection.distance_m > policy.override_max_distance_m:
        return "beyond_override_distance"
    access = lookup.get(rejection.edge_id)
    if access is None:
        return "motor_access_unknown"
    if not permits_motor_vehicles(access):
        return "does_not_permit_motor_vehicles"
    road_class = bare_road_class(rejection.road_type)
    if road_class == SERVICE_CLASS:
        # v1.0's standing rule survives: a nearby service road is never
        # automatically treated as the counted road.
        return "service_class_requires_manual_confirmation"
    return None


def _ordinals_by_edge_id(
    index: EdgeSpatialIndex,
    easting: float,
    northing: float,
    policy: ManchesterMapMatchPolicyV11,
) -> dict[str, int]:
    """Re-retrieve the same neighbourhood so an edge's own ``ref`` is readable."""

    found: dict[str, int] = {}
    for ordinal in index.edges_within(
        easting, northing, radius_m=float(policy.base.outer_search_radius_m)
    ):
        found.setdefault(index.edge_record(ordinal)[0], ordinal)
    return found


def _build_groups(
    base_result: ObservationMatch,
    overrides: Sequence[ExactReferenceOverride],
    observation_ref: str | None,
    dft_road_type: str,
) -> tuple[RoadGroupV11, ...]:
    """Rebuild analyst-facing groups, including any override-readmitted members."""

    groups: list[RoadGroupV11] = [
        RoadGroupV11(
            group_key=group.group_key,
            normalised_ref=group.normalised_ref,
            road_class_family=group.road_class_family,
            members=group.members,
            nearest_distance_m=group.nearest_distance_m,
            contains_service_member=group.contains_service_member,
            exact_reference_match=group.exact_reference_match,
            admitted_by_override=False,
            family_mismatch=None,
        )
        for group in base_result.groups
    ]

    buckets: dict[str, list[ExactReferenceOverride]] = {}
    for override in overrides:
        buckets.setdefault(f"{override.normalised_ref}|{override.osm_class_family}", []).append(
            override
        )
    for key, members in sorted(buckets.items()):
        ordered = sorted(members, key=lambda item: (item.distance_m, item.edge_id))
        groups.append(
            RoadGroupV11(
                group_key=f"override:{key}",
                normalised_ref=ordered[0].normalised_ref,
                road_class_family=ordered[0].osm_class_family,
                members=tuple(
                    EdgeCandidate(
                        edge_id=item.edge_id,
                        road_type=item.road_type,
                        road_class=item.road_class,
                        road_ref=item.normalised_ref,
                        normalised_ref=item.normalised_ref,
                        distance_m=item.distance_m,
                        geometry_source=item.geometry_source,
                        bearing_degrees=None,
                        requires_manual_confirmation=False,
                    )
                    for item in ordered
                ),
                nearest_distance_m=min(item.distance_m for item in ordered),
                contains_service_member=False,
                exact_reference_match=(
                    observation_ref is not None and ordered[0].normalised_ref == observation_ref
                ),
                admitted_by_override=True,
                family_mismatch=_describe_mismatch(dft_road_type, ordered[0].road_class),
            )
        )
    return tuple(sorted(groups, key=lambda group: (group.nearest_distance_m, group.group_key)))


def _decide(
    *,
    base_result: ObservationMatch,
    policy: ManchesterMapMatchPolicyV11,
    groups: tuple[RoadGroupV11, ...],
    readmitted: tuple[ExactReferenceOverride, ...],
    refusals: tuple[OverrideConsidered, ...],
    observation_ref: str | None,
    dft_road_type: str,
    dft_road_name: str | None,
) -> ObservationMatchV11:
    """Assign the v1.1 confidence, disposition, and acceptance path."""

    def build(
        *,
        acceptance_refused: OverrideRefusal | None = None,
        groups: tuple[RoadGroupV11, ...],
        confidence: MatchConfidence,
        disposition: TerminalDispositionV11,
        acceptance_path: AcceptancePath | None = None,
        applied: tuple[ExactReferenceOverride, ...] = (),
        missing_evidence: tuple[MissingEvidence, ...] = (),
        audit_flag: bool = False,
        family_mismatch: str | None = None,
        reasons: tuple[str, ...],
        review_reasons: tuple[str, ...],
    ) -> ObservationMatchV11:
        """Assemble one result, keeping every shared field in one place."""

        return ObservationMatchV11(
            override_acceptance_refused=acceptance_refused,
            policy_fingerprint=policy.fingerprint(),
            count_point_id=base_result.count_point_id,
            dft_road_type=dft_road_type,
            dft_road_name=dft_road_name,
            dft_normalised_ref=observation_ref,
            rejections=base_result.rejections,
            candidates_readmitted=readmitted,
            overrides_applied=applied,
            overrides_refused=refusals,
            missing_evidence=missing_evidence,
            groups=groups,
            confidence=confidence,
            disposition=disposition,
            acceptance_path=acceptance_path,
            audit_flag=audit_flag,
            family_mismatch=family_mismatch,
            reasons=reasons,
            review_reasons=review_reasons,
        )

    if not groups:
        # Missing evidence is not the same finding as absent evidence. A
        # candidate that satisfied every other override guard and failed only
        # because the network could not tell us whether it admits a motor
        # vehicle leaves this site *unavailable*, not candidate-free. Collapsing
        # the two would report a gap in our knowledge as a fact about the road.
        missing: tuple[MissingEvidence, ...] = (
            ("motor_access_unknown",)
            if any(item.refusal == "motor_access_unknown" for item in refusals)
            else ()
        )
        if missing:
            return build(
                acceptance_refused=None,
                groups=(),
                confidence="no_suitable_candidate",
                disposition="unavailable_missing_evidence",
                missing_evidence=missing,
                reasons=(
                    "a candidate met every other override guard but the network supplied no "
                    "motor-vehicle access for it, so this site is unavailable through missing "
                    "evidence rather than through having no candidate.",
                ),
                review_reasons=(),
            )
        return build(
            acceptance_refused=None,
            groups=(),
            confidence="no_suitable_candidate",
            disposition="no_suitable_candidate",
            reasons=("no candidate survived the approved filters, including the override",),
            review_reasons=(),
        )

    # Path 1: the strict v1.0 conditions were met on their own. This is checked
    # first and unconditionally. A candidate the override merely readmitted for
    # review must never demote a row that v1.0 already accepted strictly, or
    # v1.1 would accept less than v1.0 and the revision would be a regression.
    if base_result.confidence == "clear_candidate":
        return build(
            acceptance_refused=("strict_path_already_accepted" if readmitted else None),
            groups=groups,
            confidence="clear_candidate",
            disposition="owner_policy_accepted_candidate",
            acceptance_path="strict_v1_0_clear",
            audit_flag=False,
            reasons=(
                "every strict v1.0 condition was met; owner policy v1.1 accepts this candidate. "
                "No analyst, human, or supervisor has reviewed it.",
            ),
            review_reasons=(),
        )

    # Path 2: the override applied, and every one of its guards held. The
    # authorised uniqueness guard is that the signed reference identifies exactly
    # one nearby **exact-reference** road group. Nearby groups that do not carry
    # the reference do not make it non-unique, so they never block; they stay on
    # the row for review and audit.
    exact_groups = [group for group in groups if group.exact_reference_match]
    override_group = next((group for group in groups if group.admitted_by_override), None)
    if (
        readmitted
        and override_group is not None
        and len(exact_groups) == 1
        and exact_groups[0] is override_group
        and not override_group.contains_service_member
        and override_group.nearest_distance_m <= policy.override_max_distance_m
    ):
        return build(
            acceptance_refused=None,
            groups=groups,
            confidence="clear_candidate",
            disposition="owner_policy_accepted_candidate",
            acceptance_path="exact_reference_family_override",
            applied=tuple(
                item
                for item in readmitted
                if item.edge_id in {member.edge_id for member in override_group.members}
            ),
            audit_flag=True,
            family_mismatch=override_group.family_mismatch,
            reasons=(
                "an exact normalised signed-reference match overrode the DfT/OSM road-class "
                "family split, within the override distance and on a motor-permitting edge. "
                "The family mismatch is preserved above and this row carries an audit flag.",
            ),
            review_reasons=(),
        )

    # Reaching here means candidates were readmitted but no acceptance path
    # held. Name which guard stopped it, so the refusal is auditable.
    refused: OverrideRefusal | None = (
        "several_exact_reference_groups" if readmitted and len(exact_groups) != 1 else None
    )
    review = _review_reasons(base_result, groups, readmitted, observation_ref, refused)
    return build(
        acceptance_refused=refused,
        groups=groups,
        confidence="review_required",
        disposition="awaiting_manual_review",
        reasons=base_result.reasons,
        review_reasons=review,
    )


def _review_reasons(
    base_result: ObservationMatch,
    groups: Sequence[RoadGroupV11],
    readmitted: Sequence[ExactReferenceOverride],
    observation_ref: str | None,
    acceptance_refused: OverrideRefusal | None,
) -> tuple[str, ...]:
    """Say exactly why a row still needs a person.

    v1.0's own reasons come first and are not restated: it already reports how
    many eligible groups compete, so repeating that here would give a reviewer
    the same fact twice in slightly different words.
    """

    reasons: list[str] = list(base_result.reasons)
    if acceptance_refused == "several_exact_reference_groups":
        reasons.append(
            "several road groups carry the same exact signed reference, so the override "
            "readmitted them for review but may not accept any of them"
        )
    if readmitted and any(group.contains_service_member for group in groups):
        reasons.append("a service-class candidate always requires manual confirmation")
    if observation_ref is None:
        reasons.append("the observation carries no signed road reference, so no override applies")
    if not reasons:
        reasons.append("owner policy v1.1 did not accept this row automatically")
    ordered: list[str] = []
    for reason in reasons:
        if reason not in ordered:
            ordered.append(reason)
    return tuple(ordered)


class ManualReviewEntry(ObservationMatchingModel):
    """One observation the policy did not accept, kept in an explicit queue."""

    count_point_id: int = Field(ge=0)
    dft_road_type: str = Field(min_length=1, max_length=32)
    dft_normalised_ref: str | None = Field(default=None, max_length=100)
    confidence: MatchConfidence
    disposition: TerminalDispositionV11
    eligible_group_count: int = Field(ge=0)
    nearest_distance_m: Decimal | None = Field(default=None, ge=0)
    review_reasons: tuple[str, ...] = Field(min_length=1)
    #: The evidence the network could not supply, carried into the queue so a
    #: reviewer sees what to go and obtain rather than a generic no-candidate.
    missing_evidence: tuple[MissingEvidence, ...] = ()

    @model_validator(mode="after")
    def validate_entry(self) -> ManualReviewEntry:
        if self.disposition == "owner_policy_accepted_candidate":
            raise ValueError("an accepted row does not belong in the manual review queue")
        if (self.disposition == "unavailable_missing_evidence") != bool(self.missing_evidence):
            raise ValueError(
                "an unavailable-through-missing-evidence entry names what was missing, "
                "and only such an entry does"
            )
        return self


class ManualReviewQueue(ObservationMatchingModel):
    """Everything owner policy v1.1 declined to accept, with denominators."""

    schema_version: Literal["1.1"] = "1.1"
    policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    observations_total: int = Field(ge=0)
    accepted_total: int = Field(ge=0)
    queued_total: int = Field(ge=0)
    entries: tuple[ManualReviewEntry, ...] = ()
    #: The queue is preserved rather than emptied by policy acceptance.
    queue_preserved: Literal[True] = True

    @model_validator(mode="after")
    def validate_queue(self) -> ManualReviewQueue:
        if self.accepted_total + self.queued_total != self.observations_total:
            raise ValueError("accepted and queued rows must account for every observation")
        if len(self.entries) != self.queued_total:
            raise ValueError("the queue must list every row it counts")
        return self


def _queue_reasons(result: ObservationMatchV11) -> tuple[str, ...]:
    """Say why one row is in the queue, naming missing evidence specifically.

    A row that is unavailable because the network could not tell us something
    needs a different action from a row that genuinely has no candidate, so the
    generic no-candidate wording must never stand in for it.
    """

    if result.review_reasons:
        return result.review_reasons
    if result.disposition == "unavailable_missing_evidence":
        return tuple(
            f"unavailable through missing evidence: {reason}" for reason in result.missing_evidence
        )
    return ("no candidate survived the approved filters, including the override",)


def build_manual_review_queue(
    results: Sequence[ObservationMatchV11],
) -> ManualReviewQueue:
    """Collect every unaccepted observation into an explicit review queue."""

    entries = tuple(
        ManualReviewEntry(
            count_point_id=result.count_point_id,
            dft_road_type=result.dft_road_type,
            dft_normalised_ref=result.dft_normalised_ref,
            confidence=result.confidence,
            disposition=result.disposition,
            eligible_group_count=len(result.groups),
            nearest_distance_m=(
                min(group.nearest_distance_m for group in result.groups) if result.groups else None
            ),
            review_reasons=_queue_reasons(result),
            missing_evidence=result.missing_evidence,
        )
        for result in results
        if result.disposition != "owner_policy_accepted_candidate"
    )
    accepted = sum(
        1 for result in results if result.disposition == "owner_policy_accepted_candidate"
    )
    return ManualReviewQueue(
        observations_total=len(results),
        accepted_total=accepted,
        queued_total=len(entries),
        entries=entries,
    )


class ReconciliationTransition(ObservationMatchingModel):
    """One exact v1.0-to-v1.1 transition, with its population count."""

    v1_0_confidence: MatchConfidence
    v1_0_disposition: str = Field(min_length=1, max_length=64)
    v1_1_confidence: MatchConfidence
    v1_1_disposition: TerminalDispositionV11
    acceptance_path: AcceptancePath | None = None
    observations: int = Field(ge=1)


class ChangedObservation(ObservationMatchingModel):
    """One observation whose outcome differs between the two policies."""

    count_point_id: int = Field(ge=0)
    dft_road_type: str = Field(min_length=1, max_length=32)
    dft_normalised_ref: str | None = Field(default=None, max_length=100)
    v1_0_confidence: MatchConfidence
    v1_1_disposition: TerminalDispositionV11
    acceptance_path: AcceptancePath | None = None
    override_edge_ids: tuple[str, ...] = ()
    nearest_override_distance_m: Decimal | None = Field(default=None, ge=0)
    family_mismatch: str | None = Field(default=None, max_length=300)


class PolicyReconciliation(ObservationMatchingModel):
    """The exact v1.0-versus-v1.1 comparison, published rather than summarised."""

    schema_version: Literal["1.1"] = "1.1"
    capability_id: Literal["MAN-09"] = "MAN-09"
    from_policy_id: Literal["manchester-dft-map-match-owner-candidate-1.0"] = (
        "manchester-dft-map-match-owner-candidate-1.0"
    )
    to_policy_id: Literal["manchester-dft-map-match-owner-policy-1.1"] = MAP_MATCH_POLICY_V11_ID
    observations_total: int = Field(ge=0)

    v1_0_clear_candidate: int = Field(ge=0)
    v1_0_review_required: int = Field(ge=0)
    v1_0_no_suitable_candidate: int = Field(ge=0)

    v1_1_owner_policy_accepted: int = Field(ge=0)
    v1_1_awaiting_manual_review: int = Field(ge=0)
    v1_1_no_suitable_candidate: int = Field(ge=0)
    #: Rows unavailable because evidence was missing, not because no candidate
    #: existed. Its own denominator, so the two never blur together.
    v1_1_unavailable_missing_evidence: int = Field(ge=0)

    accepted_by_strict_path: int = Field(ge=0)
    accepted_by_override_path: int = Field(ge=0)

    # Override denominators. Row counts and edge counts are named separately and
    # never share a field: "applied total" that silently switches between rows
    # and edges would make the override look larger or smaller than it is.
    #: ROWS the override accepted.
    override_accepted_rows: int = Field(ge=0)
    #: EDGES carried by those accepted rows.
    override_applied_candidate_edges: int = Field(ge=0)
    #: EDGES readmitted past the family filter, accepted or not: audit evidence.
    candidates_readmitted_edges: int = Field(ge=0)
    #: EDGES the override examined and refused, with their reasons on the rows.
    candidates_refused_edges: int = Field(ge=0)

    transitions: tuple[ReconciliationTransition, ...] = ()
    changed_observations: tuple[ChangedObservation, ...] = ()

    #: Neither policy has been reviewed by a person.
    analyst_accepted: Literal[False] = False
    supervisor_approved: Literal[False] = False
    scientifically_validated: Literal[False] = False
    exploratory_candidate_software_evidence: Literal[True] = True

    @model_validator(mode="after")
    def validate_reconciliation(self) -> PolicyReconciliation:
        if (
            self.v1_0_clear_candidate + self.v1_0_review_required + self.v1_0_no_suitable_candidate
            != self.observations_total
        ):
            raise ValueError("the v1.0 populations must account for every observation")
        if (
            self.v1_1_owner_policy_accepted
            + self.v1_1_awaiting_manual_review
            + self.v1_1_no_suitable_candidate
            + self.v1_1_unavailable_missing_evidence
            != self.observations_total
        ):
            raise ValueError("the v1.1 populations must account for every observation")
        if self.override_applied_candidate_edges > self.candidates_readmitted_edges:
            raise ValueError("an applied candidate edge is always a readmitted candidate edge")
        if self.override_accepted_rows != self.accepted_by_override_path:
            raise ValueError(
                "override_accepted_rows counts rows, so it must equal the override acceptance path"
            )
        if self.override_accepted_rows > self.override_applied_candidate_edges:
            raise ValueError("an accepted row carries at least one applied candidate edge")
        if (
            self.accepted_by_strict_path + self.accepted_by_override_path
            != self.v1_1_owner_policy_accepted
        ):
            raise ValueError("the two acceptance paths must account for every acceptance")
        if sum(item.observations for item in self.transitions) != self.observations_total:
            raise ValueError("the transitions must account for every observation")
        return self


def reconcile_policies(
    v1_0_results: Sequence[ObservationMatch],
    v1_1_results: Sequence[ObservationMatchV11],
) -> PolicyReconciliation:
    """Compare the two policies exactly, observation by observation."""

    if len(v1_0_results) != len(v1_1_results):
        raise ObservationMatchingError(
            "RECONCILIATION_POPULATION_MISMATCH",
            "both policies must be run over the same observations",
        )
    pairs = list(zip(v1_0_results, v1_1_results, strict=True))
    for older, newer in pairs:
        if older.count_point_id != newer.count_point_id:
            raise ObservationMatchingError(
                "RECONCILIATION_ORDER_MISMATCH",
                "the two result sequences must describe the same observations in the same order",
            )

    buckets: dict[tuple[str, str, str, str, str | None], int] = {}
    for older, newer in pairs:
        key = (
            older.confidence,
            older.disposition,
            newer.confidence,
            newer.disposition,
            newer.acceptance_path,
        )
        buckets[key] = buckets.get(key, 0) + 1

    transitions = tuple(
        ReconciliationTransition(
            v1_0_confidence=_confidence(key[0]),
            v1_0_disposition=key[1],
            v1_1_confidence=_confidence(key[2]),
            v1_1_disposition=_disposition(key[3]),
            acceptance_path=_acceptance_path(key[4]),
            observations=count,
        )
        for key, count in sorted(buckets.items(), key=lambda item: item[0])
    )

    changed = tuple(
        ChangedObservation(
            count_point_id=newer.count_point_id,
            dft_road_type=newer.dft_road_type,
            dft_normalised_ref=newer.dft_normalised_ref,
            v1_0_confidence=older.confidence,
            v1_1_disposition=newer.disposition,
            acceptance_path=newer.acceptance_path,
            override_edge_ids=tuple(item.edge_id for item in newer.overrides_applied),
            nearest_override_distance_m=(
                min(item.distance_m for item in newer.overrides_applied)
                if newer.overrides_applied
                else None
            ),
            family_mismatch=newer.family_mismatch,
        )
        for older, newer in pairs
        if _outcome_changed(older, newer)
    )

    return PolicyReconciliation(
        observations_total=len(pairs),
        v1_0_clear_candidate=sum(1 for older, _ in pairs if older.confidence == "clear_candidate"),
        v1_0_review_required=sum(1 for older, _ in pairs if older.confidence == "review_required"),
        v1_0_no_suitable_candidate=sum(
            1 for older, _ in pairs if older.confidence == "no_suitable_candidate"
        ),
        v1_1_owner_policy_accepted=sum(
            1 for _, newer in pairs if newer.disposition == "owner_policy_accepted_candidate"
        ),
        v1_1_awaiting_manual_review=sum(
            1 for _, newer in pairs if newer.disposition == "awaiting_manual_review"
        ),
        v1_1_no_suitable_candidate=sum(
            1 for _, newer in pairs if newer.disposition == "no_suitable_candidate"
        ),
        v1_1_unavailable_missing_evidence=sum(
            1 for _, newer in pairs if newer.disposition == "unavailable_missing_evidence"
        ),
        accepted_by_strict_path=sum(
            1 for _, newer in pairs if newer.acceptance_path == "strict_v1_0_clear"
        ),
        accepted_by_override_path=sum(
            1 for _, newer in pairs if newer.acceptance_path == "exact_reference_family_override"
        ),
        override_accepted_rows=sum(1 for _, newer in pairs if newer.overrides_applied),
        override_applied_candidate_edges=sum(len(newer.overrides_applied) for _, newer in pairs),
        candidates_readmitted_edges=sum(len(newer.candidates_readmitted) for _, newer in pairs),
        candidates_refused_edges=sum(len(newer.overrides_refused) for _, newer in pairs),
        transitions=transitions,
        changed_observations=changed,
    )


def _outcome_changed(older: ObservationMatch, newer: ObservationMatchV11) -> bool:
    """Whether v1.1 reached a materially different outcome for one observation.

    Confidence alone is not enough. A site that moves from *no suitable
    candidate* to *unavailable through missing evidence* keeps the same
    confidence but changes what it is telling the reader, so it counts as
    changed.
    """

    if newer.disposition == "owner_policy_accepted_candidate":
        return True
    if newer.disposition == "unavailable_missing_evidence":
        return True
    return older.confidence != newer.confidence


def _confidence(value: str) -> MatchConfidence:
    for candidate in ("clear_candidate", "review_required", "no_suitable_candidate"):
        if candidate == value:
            return candidate
    raise ObservationMatchingError("UNKNOWN_CONFIDENCE", f"unrecognised confidence {value!r}")


def _disposition(value: str) -> TerminalDispositionV11:
    for candidate in (
        "owner_policy_accepted_candidate",
        "awaiting_manual_review",
        "no_suitable_candidate",
        "unavailable_missing_evidence",
    ):
        if candidate == value:
            return candidate
    raise ObservationMatchingError("UNKNOWN_DISPOSITION", f"unrecognised disposition {value!r}")


def _acceptance_path(value: str | None) -> AcceptancePath | None:
    if value is None:
        return None
    for candidate in ("strict_v1_0_clear", "exact_reference_family_override"):
        if candidate == value:
            return candidate
    raise ObservationMatchingError("UNKNOWN_ACCEPTANCE_PATH", f"unrecognised path {value!r}")


def policy_v11_summary_fingerprint(policy: ManchesterMapMatchPolicyV11) -> str:
    """Fingerprint v1.1 together with the v1.0 class lists it inherits."""

    from traffictwin.integration.manchester.observation_matching import (
        HARD_EXCLUDED_CLASSES,
        MAJOR_ROAD_CLASSES,
        MINOR_ROAD_CLASSES,
    )

    payload = {
        "policy": policy.model_dump(mode="json"),
        "hard_excluded": sorted(HARD_EXCLUDED_CLASSES),
        "major": sorted(MAJOR_ROAD_CLASSES),
        "minor": sorted(MINOR_ROAD_CLASSES),
        "motor_permitting_access": sorted(MOTOR_PERMITTING_ACCESS),
    }
    return sha256_hex(canonical_json(payload).encode("utf-8"))


__all__ = [
    "MAP_MATCH_METHOD_V11",
    "MAP_MATCH_POLICY_V11_ID",
    "MOTOR_PERMITTING_ACCESS",
    "OVERRIDABLE_REJECTION_REASON",
    "AcceptancePath",
    "ChangedObservation",
    "ExactReferenceOverride",
    "ManchesterMapMatchPolicyV11",
    "ManualReviewEntry",
    "ManualReviewQueue",
    "ObservationMatchV11",
    "OverrideConsidered",
    "OverrideRefusal",
    "PolicyReconciliation",
    "ReconciliationTransition",
    "RoadGroupV11",
    "TerminalDispositionV11",
    "build_manual_review_queue",
    "match_observation_v11",
    "permits_motor_vehicles",
    "policy_v11_summary_fingerprint",
    "reconcile_policies",
]

"""Deterministic What-If Challenge planning over the recommendation.

Third stage of the bounded chain: the Analyst interprets evidence, Next
Investigation selects a bounded recommendation, and this planner converts
that recommendation into a controlled, reviewable What-If challenge
specification. The specification is a plan, never a result: it carries no
execution authority, creates no evidence, and claims no cause.

Capability awareness: a challenge may only vary dimensions the existing
What-If contract can represent (``WHATIF_CONTROL_SPEC`` bounds and the
registered ``SyntheticPolicyProfile`` values). Where a required magnitude
or choice is unknown, the challenge exposes a typed user input rather
than guessing; where the product cannot represent the recommended
mechanism at all, the challenge says so (``NOT_REPRESENTABLE``) instead
of faking support. TrafficTwin's What-If contract exposes one capacity
dimension (``rsu_capacity``, service/compute concurrency); waiting-room
or queue capacity is not separately controllable, and no
placement/load-management mode dimension exists — both limitations are
stated, never papered over.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.models import (
    AnalystEvidencePacket,
    AnalystModel,
    AnalystRefusalCode,
    AnalystRefusalError,
)
from traffictwin.analyst.packet import (
    ANALYST_INFRASTRUCTURE_KEYS,
    ANALYST_TRAFFIC_KEYS,
    ANALYST_VEC_KEYS,
)
from traffictwin.analyst.recommendation import (
    RecommendationCategory,
    RecommendationEvidencePacket,
)
from traffictwin.synthetic.config import SyntheticPolicyProfile
from traffictwin.ui.challenge_whatif_bridge import (
    ChallengeWhatIfDraft,
    ChallengeWhatIfMappedField,
    ChallengeWhatIfMappingStatus,
)
from traffictwin.ui.whatif_controls import (
    DEFAULT_WHATIF_WIDGET_VALUES,
    WHATIF_CONTROL_SPEC,
    is_value_representable,
)

CHALLENGE_SCHEMA_VERSION: Literal["whatif-challenge-1.0"] = "whatif-challenge-1.0"
CHALLENGE_PLANNER_VERSION: Literal["challenge-planner-1.0"] = "challenge-planner-1.0"

REGISTERED_POLICY_PROFILES: tuple[str, ...] = tuple(
    profile.value for profile in SyntheticPolicyProfile
)

# Scenario-side dimensions the existing What-If contract bounds numerically.
SCENARIO_DIMENSION_FIELDS: tuple[str, ...] = (
    "congestion_multiplier",
    "event_demand_multiplier",
    "task_arrival_rate",
    "incident_duration_s",
    "lanes_closed",
)

_MODEL_FIELDS: tuple[str, ...] = ("policy_profile",)
_INFRASTRUCTURE_FIELDS: tuple[str, ...] = ("rsu_count", "rsu_capacity")
_SCENARIO_FIELDS: tuple[str, ...] = (
    "incident_enabled",
    "incident_type",
    "incident_location",
    "incident_start_s",
    "incident_duration_s",
    "incident_severity",
    "lanes_closed",
    "event_demand_multiplier",
    "congestion_multiplier",
    "vehicle_count",
    "task_arrival_rate",
    "task_mix_t1",
    "task_mix_t2",
    "task_mix_t3",
    "duration_s",
    "trip_count",
)
_IDENTITY_FIELDS: tuple[str, ...] = ("baseline_preset", "random_seed", "experiment_id")

QUEUE_CAPACITY_LIMITATION = (
    "TrafficTwin's What-If contract exposes one capacity dimension: "
    "rsu_capacity (service/compute concurrency capacity). Waiting-room or "
    "queue capacity is not separately controllable, and the two must not "
    "be conflated."
)
PLACEMENT_LIMITATION = (
    "TrafficTwin's What-If contract exposes no infrastructure-side "
    "placement or load-management mode dimension. The registered "
    "infrastructure dimensions (rsu_count, rsu_capacity) vary "
    "capacity/resources, which does not isolate load management."
)


class ChallengeCategory(StrEnum):
    """The bounded challenge vocabulary, one per recommendation category."""

    MODEL_BEHAVIOUR_CHALLENGE = "MODEL_BEHAVIOUR_CHALLENGE"
    RSU_LOAD_MANAGEMENT_CHALLENGE = "RSU_LOAD_MANAGEMENT_CHALLENGE"
    INFRASTRUCTURE_CAPACITY_CHALLENGE = "INFRASTRUCTURE_CAPACITY_CHALLENGE"
    SCENARIO_CONTROL_CHALLENGE = "SCENARIO_CONTROL_CHALLENGE"
    MIXED_MECHANISM_CHALLENGE = "MIXED_MECHANISM_CHALLENGE"
    NO_ACTIONABLE_CHALLENGE = "NO_ACTIONABLE_CHALLENGE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


CHALLENGE_DISPLAY_NAMES: dict[ChallengeCategory, str] = {
    ChallengeCategory.MODEL_BEHAVIOUR_CHALLENGE: (
        "Compare registered offloading-policy profiles under fixed infrastructure and scenario"
    ),
    ChallengeCategory.RSU_LOAD_MANAGEMENT_CHALLENGE: (
        "Load-management challenge (not currently representable)"
    ),
    ChallengeCategory.INFRASTRUCTURE_CAPACITY_CHALLENGE: (
        "Vary service capacity under a fixed model and scenario"
    ),
    ChallengeCategory.SCENARIO_CONTROL_CHALLENGE: (
        "Vary one scenario dimension under a fixed model and infrastructure"
    ),
    ChallengeCategory.MIXED_MECHANISM_CHALLENGE: (
        "Two controlled tracks: mechanism-separating comparisons"
    ),
    ChallengeCategory.NO_ACTIONABLE_CHALLENGE: ("No actionable What-If challenge is justified"),
    ChallengeCategory.INSUFFICIENT_EVIDENCE: (
        "A controlled What-If challenge cannot yet be prepared"
    ),
}


class ChallengeReadiness(StrEnum):
    """Typed readiness of a challenge or track — never a bare boolean."""

    READY = "READY"
    NEEDS_USER_INPUT = "NEEDS_USER_INPUT"
    NOT_REPRESENTABLE = "NOT_REPRESENTABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_ACTIONABLE_CHALLENGE = "NO_ACTIONABLE_CHALLENGE"


class ChallengeUserInput(AnalystModel):
    """One unresolved, constrained input the user must supply."""

    input_id: str
    prompt: str
    whatif_field: str
    kind: Literal["choice", "bounded_number"]
    allowed_choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    value_type: Literal["int", "float", "str"] = "str"
    provenance: str


class HeldFixedControl(AnalystModel):
    """One dimension the challenge deliberately holds unchanged."""

    dimension: str
    group: Literal["model", "infrastructure", "scenario", "identity", "evidence"]
    basis: str


class ChallengeTrack(AnalystModel):
    """One controlled comparison; mixed challenges carry two."""

    track_id: str
    title: str
    readiness: ChallengeReadiness
    variable_under_investigation: str | None = None
    whatif_field: str | None = None
    research_question: str
    comparison_structure: str
    held_fixed: tuple[HeldFixedControl, ...] = ()
    required_user_inputs: tuple[ChallengeUserInput, ...] = ()
    unsupported_dimensions: tuple[str, ...] = ()
    expected_observables: tuple[str, ...] = ()
    could_support: str
    cannot_establish: str


class WhatIfChallengeSpec(AnalystModel):
    """The reviewable, deterministic challenge specification.

    Carries no wall-clock field, no local path, and no random identifier;
    identical validated inputs produce byte-equivalent canonical content
    and an identical fingerprint.
    """

    schema_version: Literal["whatif-challenge-1.0"] = CHALLENGE_SCHEMA_VERSION
    planner_version: Literal["challenge-planner-1.0"] = CHALLENGE_PLANNER_VERSION
    source_recommendation_fingerprint: str
    source_analyst_fingerprint: str
    recommendation_category: str
    analyst_signal: str
    evidence_standing: str
    confidence: str
    category: ChallengeCategory
    headline: str
    statement: str
    tracks: tuple[ChallengeTrack, ...] = ()
    readiness: ChallengeReadiness
    missing_evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    execution_authority: Literal[False] = False
    creates_new_evidence: Literal[False] = False
    causal_claim_supported: Literal[False] = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _held_fixed(*, exclude: tuple[str, ...], evidence_basis: str) -> tuple[HeldFixedControl, ...]:
    controls: list[HeldFixedControl] = []
    groups: tuple[
        tuple[tuple[str, ...], Literal["model", "infrastructure", "scenario", "identity"]],
        ...,
    ] = (
        (_MODEL_FIELDS, "model"),
        (_INFRASTRUCTURE_FIELDS, "infrastructure"),
        (_SCENARIO_FIELDS, "scenario"),
        (_IDENTITY_FIELDS, "identity"),
    )
    for fields, group in groups:
        for field in fields:
            if field in exclude:
                continue
            controls.append(
                HeldFixedControl(
                    dimension=field,
                    group=group,
                    basis=(
                        "The What-If pair generator only changes explicitly "
                        "overridden fields; this field stays at its baseline "
                        "value by construction."
                    ),
                )
            )
    controls.append(
        HeldFixedControl(
            dimension="metric contract (metric_version, comparison contract)",
            group="evidence",
            basis=evidence_basis,
        )
    )
    return tuple(controls)


_METRIC_CONTRACT_BASIS = (
    "Both arms are validated by the same metric engine and compared under "
    "the existing comparison contract; metric definitions never vary."
)


def _observables(groups: tuple[str, ...]) -> tuple[str, ...]:
    keys: list[str] = []
    if "vec" in groups:
        keys.extend(ANALYST_VEC_KEYS)
    if "infrastructure" in groups:
        keys.extend(ANALYST_INFRASTRUCTURE_KEYS)
    if "traffic" in groups:
        keys.extend(ANALYST_TRAFFIC_KEYS)
    return tuple(keys)


def _capacity_input() -> ChallengeUserInput:
    spec = WHATIF_CONTROL_SPEC["rsu_capacity"]
    return ChallengeUserInput(
        input_id="comparison_rsu_capacity",
        prompt=(
            "Select the comparison service-capacity level for the variation "
            "arm (the baseline arm keeps the preset value)."
        ),
        whatif_field="rsu_capacity",
        kind="bounded_number",
        minimum=float(spec["min"]),
        maximum=float(spec["max"]) if "max" in spec else None,
        value_type="float",
        provenance=(
            "Bounds come from the existing What-If control contract "
            "(WHATIF_CONTROL_SPEC); the registered product default is "
            f"{DEFAULT_WHATIF_WIDGET_VALUES['whatif_rsu_capacity']}."
        ),
    )


def _profile_input() -> ChallengeUserInput:
    return ChallengeUserInput(
        input_id="comparison_policy_profile",
        prompt=(
            "Select the registered offloading-policy profile for the "
            "variation arm (the baseline arm keeps the preset profile)."
        ),
        whatif_field="policy_profile",
        kind="choice",
        allowed_choices=REGISTERED_POLICY_PROFILES,
        value_type="str",
        provenance=(
            "Choices are the registered SyntheticPolicyProfile values; no "
            "profile is invented and nothing is trained or retrained."
        ),
    )


def _scenario_dimension_input() -> ChallengeUserInput:
    return ChallengeUserInput(
        input_id="scenario_dimension",
        prompt="Select which supported scenario dimension the comparison varies.",
        whatif_field="scenario_dimension",
        kind="choice",
        allowed_choices=SCENARIO_DIMENSION_FIELDS,
        value_type="str",
        provenance=(
            "Choices are the scenario dimensions bounded by the existing What-If control contract."
        ),
    )


def _scenario_value_input(field: str) -> ChallengeUserInput:
    spec = WHATIF_CONTROL_SPEC[field]
    return ChallengeUserInput(
        input_id=f"comparison_{field}",
        prompt=f"Select the comparison value for {field} in the variation arm.",
        whatif_field=field,
        kind="bounded_number",
        minimum=float(spec["min"]) if "min" in spec else None,
        maximum=float(spec["max"]) if "max" in spec else None,
        value_type="int" if spec.get("type") is int else "float",
        provenance=(
            "Bounds come from the existing What-If control contract (WHATIF_CONTROL_SPEC)."
        ),
    )


def _model_track(observables: tuple[str, ...]) -> ChallengeTrack:
    return ChallengeTrack(
        track_id="model-behaviour",
        title="Vary the registered offloading-policy profile",
        readiness=ChallengeReadiness.NEEDS_USER_INPUT,
        variable_under_investigation=(
            "Registered synthetic offloading-policy profile (policy_profile)"
        ),
        whatif_field="policy_profile",
        research_question=(
            "Would a different registered offloading-policy profile change "
            "the relevant task outcomes while infrastructure and scenario "
            "conditions remain fixed?"
        ),
        comparison_structure=(
            "One baseline arm (preset profile) versus one variation arm "
            "(selected registered profile); same preset, same seed, same "
            "infrastructure, same scenario inputs."
        ),
        held_fixed=_held_fixed(exclude=("policy_profile",), evidence_basis=_METRIC_CONTRACT_BASIS),
        required_user_inputs=(_profile_input(),),
        expected_observables=observables,
        could_support=(
            "Whether the observed task behaviour changes under a controlled "
            "policy-profile variation — a candidate-mechanism check, not a "
            "verdict on the learned actor."
        ),
        cannot_establish=(
            "It does not train or evaluate a learned model, does not "
            "establish a causal mechanism, and does not rank profiles as "
            "generally better or worse."
        ),
    )


def _capacity_track(observables: tuple[str, ...]) -> ChallengeTrack:
    return ChallengeTrack(
        track_id="infrastructure-capacity",
        title="Vary service/compute capacity (rsu_capacity)",
        readiness=ChallengeReadiness.NEEDS_USER_INPUT,
        variable_under_investigation=("RSU service/compute concurrency capacity (rsu_capacity)"),
        whatif_field="rsu_capacity",
        research_question=(
            "Would a different service-capacity level change the relevant "
            "outcomes while the model profile and scenario conditions remain "
            "fixed?"
        ),
        comparison_structure=(
            "One baseline arm (preset capacity) versus one variation arm "
            "(selected capacity level); same preset, same seed, same "
            "policy profile, same scenario inputs."
        ),
        held_fixed=_held_fixed(exclude=("rsu_capacity",), evidence_basis=_METRIC_CONTRACT_BASIS),
        required_user_inputs=(_capacity_input(),),
        unsupported_dimensions=("waiting-room/queue capacity (not separately exposed)",),
        expected_observables=observables,
        could_support=(
            "Whether the observed pressure and task outcomes change under a "
            "controlled service-capacity variation."
        ),
        cannot_establish=(
            "It does not establish that capacity is the causal mechanism and "
            "does not show that capacity must be expanded; queue capacity is "
            "not varied."
        ),
    )


def _scenario_track(observables: tuple[str, ...]) -> ChallengeTrack:
    return ChallengeTrack(
        track_id="scenario-control",
        title="Vary one supported scenario dimension",
        readiness=ChallengeReadiness.NEEDS_USER_INPUT,
        variable_under_investigation="One supported scenario dimension (user-selected)",
        whatif_field=None,
        research_question=(
            "Would a controlled change in one supported scenario dimension "
            "reproduce or remove the observed candidate signal while the "
            "model profile and infrastructure remain fixed?"
        ),
        comparison_structure=(
            "One baseline arm versus one variation arm differing in exactly "
            "one supported scenario dimension; same preset, same seed, same "
            "policy profile, same infrastructure."
        ),
        held_fixed=_held_fixed(exclude=(), evidence_basis=_METRIC_CONTRACT_BASIS),
        required_user_inputs=(_scenario_dimension_input(),),
        expected_observables=observables,
        could_support=(
            "Whether the candidate signal follows the varied scenario "
            "dimension — evidence that could help distinguish scenario "
            "conditions from mechanism-side explanations."
        ),
        cannot_establish=(
            "It does not attribute the signal to the model or the "
            "infrastructure and does not establish a causal mechanism."
        ),
    )


def _load_management_track() -> ChallengeTrack:
    return ChallengeTrack(
        track_id="rsu-load-management",
        title="Infrastructure-side load management (not representable)",
        readiness=ChallengeReadiness.NOT_REPRESENTABLE,
        variable_under_investigation=None,
        whatif_field=None,
        research_question=(
            "Would a supported alternative infrastructure-side "
            "placement/load-management configuration change the relevant "
            "outcome while the model and scenario remain fixed?"
        ),
        comparison_structure=(
            "Not currently constructible: no registered What-If dimension "
            "varies placement/load management in isolation."
        ),
        unsupported_dimensions=("infrastructure-side placement/load-management mode",),
        could_support=(
            "Nothing yet — the recommendation stays supported, but the "
            "challenge is not currently representable in What-If Studio."
        ),
        cannot_establish=(
            "No conclusion is available; preparing this challenge first "
            "requires a registered load-management dimension in the What-If "
            "contract."
        ),
    )


def plan_challenge(
    recommendation: RecommendationEvidencePacket,
    analyst_packet: AnalystEvidencePacket,
) -> WhatIfChallengeSpec:
    """Deterministically convert the recommendation into a challenge spec.

    The recommendation must belong to the supplied Analyst packet; a
    mismatched pairing is a typed refusal, never a silent re-derivation.
    """

    if recommendation.analyst_packet_fingerprint != analyst_packet.fingerprint():
        raise AnalystRefusalError(
            AnalystRefusalCode.PROVENANCE_INCOMPLETE,
            "The recommendation does not belong to the supplied Analyst "
            "packet, so no challenge is derivable from this pairing.",
        )

    category = ChallengeCategory.INSUFFICIENT_EVIDENCE
    readiness = ChallengeReadiness.INSUFFICIENT_EVIDENCE
    tracks: tuple[ChallengeTrack, ...] = ()
    statement = (
        "A controlled What-If challenge cannot yet be prepared because the "
        "evidence is insufficient."
    )
    limitations: list[str] = list(recommendation.limitations)

    rec_category = RecommendationCategory(recommendation.category)
    if rec_category is RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING:
        category = ChallengeCategory.MODEL_BEHAVIOUR_CHALLENGE
        tracks = (_model_track(_observables(("vec",))),)
        readiness = ChallengeReadiness.NEEDS_USER_INPUT
        statement = (
            "Prepare a controlled comparison in which the registered "
            "offloading-policy profile changes while infrastructure, "
            "scenario, seed and metric definitions remain fixed."
        )
        limitations.append(
            "Registered profiles are deterministic synthetic behaviours, "
            "not learned actors; this challenge does not train or retrain "
            "anything, and training evidence remains a separate need."
        )
    elif rec_category is RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT:
        category = ChallengeCategory.RSU_LOAD_MANAGEMENT_CHALLENGE
        tracks = (_load_management_track(),)
        readiness = ChallengeReadiness.NOT_REPRESENTABLE
        statement = (
            "The recommendation is supported, but the challenge is not "
            "currently representable: no registered What-If dimension "
            "varies infrastructure-side load management in isolation."
        )
        limitations.extend((PLACEMENT_LIMITATION, QUEUE_CAPACITY_LIMITATION))
    elif rec_category is RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY:
        category = ChallengeCategory.INFRASTRUCTURE_CAPACITY_CHALLENGE
        tracks = (_capacity_track(_observables(("vec", "infrastructure"))),)
        readiness = ChallengeReadiness.NEEDS_USER_INPUT
        statement = (
            "Prepare a controlled comparison in which the service/compute "
            "capacity level changes while the model profile, scenario, seed "
            "and metric definitions remain fixed."
        )
        limitations.append(QUEUE_CAPACITY_LIMITATION)
    elif rec_category is RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL:
        category = ChallengeCategory.SCENARIO_CONTROL_CHALLENGE
        tracks = (_scenario_track(_observables(("vec", "traffic"))),)
        readiness = ChallengeReadiness.NEEDS_USER_INPUT
        statement = (
            "Prepare a controlled comparison between supported scenario "
            "conditions while the model profile and infrastructure remain "
            "fixed."
        )
    elif rec_category is RecommendationCategory.MIXED_INVESTIGATION:
        category = ChallengeCategory.MIXED_MECHANISM_CHALLENGE
        tracks = (
            _capacity_track(_observables(("vec", "infrastructure"))),
            _model_track(_observables(("vec",))),
        )
        readiness = ChallengeReadiness.NEEDS_USER_INPUT
        statement = (
            "The current evidence supports both model-side and "
            "infrastructure-side investigation, so two mechanism-separating "
            "tracks are prepared. The evidence does not justify calling "
            "either track the sole mechanism, and the tracks are not "
            "executed together or automatically."
        )
        limitations.append(PLACEMENT_LIMITATION)
    elif rec_category is RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED:
        category = ChallengeCategory.NO_ACTIONABLE_CHALLENGE
        readiness = ChallengeReadiness.NO_ACTIONABLE_CHALLENGE
        statement = (
            "No actionable What-If challenge is justified by the current "
            "deterministic evidence; no study is manufactured."
        )

    return WhatIfChallengeSpec(
        source_recommendation_fingerprint=recommendation.fingerprint(),
        source_analyst_fingerprint=recommendation.analyst_packet_fingerprint,
        recommendation_category=recommendation.category.value,
        analyst_signal=recommendation.analyst_signal,
        evidence_standing=recommendation.evidence_standing,
        confidence=recommendation.confidence,
        category=category,
        headline=CHALLENGE_DISPLAY_NAMES[category],
        statement=statement,
        tracks=tracks,
        readiness=readiness,
        missing_evidence=recommendation.missing_evidence,
        limitations=tuple(limitations),
        provenance_refs=(
            *recommendation.provenance_refs,
            f"recommendation_packet:{recommendation.fingerprint()[:16]}",
        ),
    )


def resolve_scenario_track(spec: WhatIfChallengeSpec, dimension: str) -> ChallengeTrack:
    """Return the scenario track re-planned for one chosen dimension."""

    if dimension not in SCENARIO_DIMENSION_FIELDS:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            f"{dimension!r} is not a supported scenario dimension.",
        )
    track = next((item for item in spec.tracks if item.track_id == "scenario-control"), None)
    if track is None:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            "This challenge has no scenario-control track.",
        )
    return track.model_copy(
        update={
            "variable_under_investigation": f"Scenario dimension {dimension}",
            "whatif_field": dimension,
            "held_fixed": _held_fixed(exclude=(dimension,), evidence_basis=_METRIC_CONTRACT_BASIS),
            "required_user_inputs": (_scenario_value_input(dimension),),
        }
    )


def build_challenge_prefill(
    spec: WhatIfChallengeSpec,
    track: ChallengeTrack,
    resolved_inputs: Mapping[str, str | int | float],
) -> ChallengeWhatIfDraft:
    """Convert one resolved track into the existing Studio handoff payload.

    Pure function: it mutates nothing, executes nothing, and returns a
    reviewable draft the user must still apply and confirm inside What-If
    Studio. Every value is validated against the registered choices or the
    existing What-If control bounds; nothing is guessed.
    """

    if track.readiness is ChallengeReadiness.NOT_REPRESENTABLE:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            "This track is not representable in the current What-If contract.",
        )
    if spec.readiness in (
        ChallengeReadiness.INSUFFICIENT_EVIDENCE,
        ChallengeReadiness.NO_ACTIONABLE_CHALLENGE,
    ):
        raise AnalystRefusalError(
            AnalystRefusalCode.INSUFFICIENT_EVIDENCE,
            "No prefill is derivable: the challenge has no actionable content.",
        )

    overrides: dict[str, str | int | float] = {}
    mapped: list[ChallengeWhatIfMappedField] = []
    for user_input in track.required_user_inputs:
        if user_input.input_id not in resolved_inputs:
            raise AnalystRefusalError(
                AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                f"Required input {user_input.input_id!r} is unresolved; the "
                "prefill stays blocked rather than guessing a value.",
            )
        value = resolved_inputs[user_input.input_id]
        if user_input.kind == "choice":
            if not isinstance(value, str) or value not in user_input.allowed_choices:
                raise AnalystRefusalError(
                    AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                    f"{value!r} is not a registered choice for {user_input.input_id!r}.",
                )
        else:
            representable, reason = is_value_representable(user_input.whatif_field, value)
            if not representable:
                raise AnalystRefusalError(
                    AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                    f"{value!r} is not representable for {user_input.whatif_field!r}: {reason}",
                )
        overrides[user_input.whatif_field] = value
        mapped.append(
            ChallengeWhatIfMappedField(
                challenge_path=f"challenge.{track.track_id}.{user_input.input_id}",
                challenge_value=value,
                whatif_field=user_input.whatif_field,
                mapped_value=value,
                rationale=(
                    f"User-resolved input for the {track.track_id} track; {user_input.provenance}"
                ),
            )
        )

    identity = json.dumps(
        {
            "challenge_fingerprint": spec.fingerprint(),
            "track_id": track.track_id,
            "overrides": {key: overrides[key] for key in sorted(overrides)},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return ChallengeWhatIfDraft(
        challenge_id=f"whatif-challenge-{spec.fingerprint()[:12]}",
        challenge_title=track.title,
        mapping_status=ChallengeWhatIfMappingStatus.FULLY_MAPPABLE,
        supported_fields=mapped,
        whatif_overrides=dict(overrides),
        warnings=[
            "Prepared from a What-If Challenge specification; review the "
            "prefill in What-If Studio and generate the pair explicitly. "
            "Nothing has been executed.",
        ],
        fingerprint=sha256(identity.encode("utf-8")).hexdigest(),
    )

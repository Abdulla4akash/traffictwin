"""Deterministic challenge-candidate design over the What-If contract.

The Challenge Designer answers one bounded product question: "What
scenario should I test next if I want to expose meaningful differences
between competing strategies rather than producing an obvious result?"
It proposes up to three structured candidate scenarios per request, in
three modes (make the current scenario harder, test a bounded
hypothesis, or a deterministic surprise trio), and it hands a selected
candidate to What-If Studio through the existing pending-draft contract.

Boundaries, stated once and enforced throughout:

* Every candidate varies only fields the existing What-If contract
  bounds (``WHATIF_CONTROL_SPEC``) plus the registered
  ``SyntheticPolicyProfile`` values. No knob is invented.
* Mechanisms the contract cannot represent (placement/load management,
  admission policy, queue capacity, fleet capability mix, task
  ordering) are refused by name, never approximated with a different
  parameter.
* "Challenging" never means "maximal": proposed magnitudes take one
  bounded step of the remaining headroom and never sit on a registered
  bound. The step fraction is a reviewable product design constant, not
  a scientific threshold; the human adjusts every value in What-If
  Studio before anything is generated.
* No candidate predicts a winner. TrafficTwin has no deterministic
  predictor for unexecuted scenarios — the winner map and the R3
  scenario-triviality rule assess executed evidence only — so every
  candidate carries ``PREDICTION_UNAVAILABLE`` rather than an LLM guess.
* An optional LLM may PROPOSE candidate payloads; deterministic
  validation decides. A proposal with an unknown parameter, an
  out-of-bounds value, a winner claim, or fabricated evidence language
  is refused with a typed code. Nothing here executes anything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.challenge import (
    PLACEMENT_LIMITATION,
    QUEUE_CAPACITY_LIMITATION,
    REGISTERED_POLICY_PROFILES,
    HeldFixedControl,
)
from traffictwin.analyst.models import (
    AnalystModel,
    AnalystRefusalCode,
    AnalystRefusalError,
)
from traffictwin.analyst.packet import (
    ANALYST_INFRASTRUCTURE_KEYS,
    ANALYST_TRAFFIC_KEYS,
    ANALYST_VEC_KEYS,
)
from traffictwin.analyst.prose import (
    ANALYST_DEEPSEEK_API_URL,
    ANALYST_DEEPSEEK_MODEL,
    ANALYST_TIMEOUT_SECONDS,
    AnalystProseError,
    AnalystTransport,
    default_deepseek_transport,
    parse_deepseek_response_content,
    screen_prose_payload,
)
from traffictwin.analyst.recommendation import RecommendationCategory
from traffictwin.ui.challenge_whatif_bridge import (
    ChallengeWhatIfDraft,
    ChallengeWhatIfMappedField,
    ChallengeWhatIfMappingStatus,
    ChallengeWhatIfUnsupportedField,
)
from traffictwin.ui.whatif_controls import (
    DEFAULT_WHATIF_WIDGET_VALUES,
    WHATIF_CONTROL_SPEC,
    is_value_representable,
)

CANDIDATE_SCHEMA_VERSION: Literal["challenge-candidates-1.0"] = "challenge-candidates-1.0"
CANDIDATE_DESIGNER_VERSION: Literal["challenge-designer-1.0"] = "challenge-designer-1.0"

# One bounded step of the remaining headroom toward (never onto) a bound.
# This is a reviewable product design constant with no scientific meaning;
# the user edits every proposed value in What-If Studio before generation.
HARDER_STEP_FRACTION = 0.25

MAX_CANDIDATES = 3

CandidateValue = str | int | float | bool

DERIVED_SCENARIO_STANDING: Literal[
    "synthetic what-if proposal (derived scenario; not an observation)"
] = "synthetic what-if proposal (derived scenario; not an observation)"

PREDICTION_UNAVAILABLE_REASON = (
    "OUTSIDE_SUPPORTED_ENVELOPE: TrafficTwin has no deterministic predictor "
    "for unexecuted scenarios. The winner map and the R3 scenario-triviality "
    "rule assess executed evidence only, and LLM intuition is never used as "
    "an outcome prediction."
)

TRIVIALITY_BASIS = (
    "Design-time triviality is assessed structurally only: no proposed value "
    "may sit on a registered bound, and broad same-direction escalation "
    "across many dimensions is flagged as maximal stress. Outcome-level "
    "triviality remains assessable only after execution, by the existing "
    "deterministic machinery (rule R3 scenario-triviality over winner-map "
    "evidence)."
)

ADMISSION_LIMITATION = (
    "TrafficTwin's What-If contract exposes no admission-policy dimension. "
    "Admission is not the same as placement, and neither is currently "
    "representable; no other parameter is substituted for it."
)
FLEET_CAPABILITY_LIMITATION = (
    "Fleet capability/tier mix has no What-If control: the generator derives "
    "tier mix internally and the challenge bridge records that no defensible "
    "reverse mapping exists. Vehicle-capability stress is therefore not "
    "representable."
)
TASK_ORDERING_LIMITATION = (
    "Workload ordering has no What-If control; the generator hardcodes MIXED "
    "ordering, so task-ordering stress is not representable."
)

# The mutable candidate surface, grouped the same way the merged challenge
# planner groups held-fixed controls.
CANDIDATE_MODEL_FIELDS: tuple[str, ...] = ("policy_profile",)
CANDIDATE_INFRASTRUCTURE_FIELDS: tuple[str, ...] = ("rsu_count", "rsu_capacity")
CANDIDATE_TASK_FIELDS: tuple[str, ...] = (
    "task_arrival_rate",
    "task_mix_t1",
    "task_mix_t2",
    "task_mix_t3",
)
CANDIDATE_TRAFFIC_FIELDS: tuple[str, ...] = ("congestion_multiplier", "vehicle_count")
CANDIDATE_INCIDENT_FIELDS: tuple[str, ...] = (
    "incident_enabled",
    "incident_type",
    "incident_location",
    "incident_severity",
    "incident_start_s",
    "incident_duration_s",
    "lanes_closed",
    "event_demand_multiplier",
)
CANDIDATE_IDENTITY_FIELDS: tuple[str, ...] = (
    "baseline_preset",
    "random_seed",
    "baseline_random_seed",
)

SUPPORTED_CANDIDATE_FIELDS: tuple[str, ...] = (
    *CANDIDATE_MODEL_FIELDS,
    *CANDIDATE_INFRASTRUCTURE_FIELDS,
    *CANDIDATE_TASK_FIELDS,
    *CANDIDATE_TRAFFIC_FIELDS,
    *CANDIDATE_INCIDENT_FIELDS,
)

_FIELD_GROUPS: dict[str, Literal["model", "infrastructure", "scenario", "identity"]] = {
    **dict.fromkeys(CANDIDATE_MODEL_FIELDS, "model"),
    **dict.fromkeys(CANDIDATE_INFRASTRUCTURE_FIELDS, "infrastructure"),
    **dict.fromkeys(CANDIDATE_TASK_FIELDS, "scenario"),
    **dict.fromkeys(CANDIDATE_TRAFFIC_FIELDS, "scenario"),
    **dict.fromkeys(CANDIDATE_INCIDENT_FIELDS, "scenario"),
    **dict.fromkeys(CANDIDATE_IDENTITY_FIELDS, "identity"),
}

_WINNER_CLAIM_MARKERS: tuple[str, ...] = (
    "will win",
    "will outperform",
    "will beat",
    "will dominate",
    "always wins",
    "guaranteed to",
    "certain to win",
    "predicted winner",
    "proves",
    "will be superior",
)
_EVIDENCE_CLAIM_MARKERS: tuple[str, ...] = (
    "evidence shows",
    "results show",
    "data shows",
    "we observed",
    "we measured",
    "experiment showed",
    "statistically significant",
    "p <",
    "p<",
)
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


class ChallengeFamily(StrEnum):
    """Challenge families the current What-If contract can represent."""

    TASK_PRESSURE = "TASK_PRESSURE"
    TASK_MIX_SHIFT = "TASK_MIX_SHIFT"
    TRAFFIC_DEMAND_PRESSURE = "TRAFFIC_DEMAND_PRESSURE"
    INCIDENT_PRESSURE = "INCIDENT_PRESSURE"
    INFRASTRUCTURE_CAPACITY_PRESSURE = "INFRASTRUCTURE_CAPACITY_PRESSURE"
    MODEL_INFRASTRUCTURE_INTERACTION = "MODEL_INFRASTRUCTURE_INTERACTION"


class CandidateGenerationMode(StrEnum):
    """The three product modes plus the validated external-proposal path."""

    MAKE_HARDER = "MAKE_HARDER"
    TEST_HYPOTHESIS = "TEST_HYPOTHESIS"
    SURPRISE_ME = "SURPRISE_ME"
    EXTERNAL_PROPOSAL = "EXTERNAL_PROPOSAL"


class CandidateValidationStatus(StrEnum):
    """Deterministic validation outcome; an LLM cannot override it."""

    VALID_CHALLENGE = "VALID_CHALLENGE"
    VALID_BUT_TRIVIAL = "VALID_BUT_TRIVIAL"
    VALID_BUT_REDUNDANT = "VALID_BUT_REDUNDANT"
    PARTIALLY_REPRESENTABLE = "PARTIALLY_REPRESENTABLE"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


class ChallengeHypothesis(StrEnum):
    """The bounded hypothesis vocabulary for TEST_HYPOTHESIS mode."""

    INFRASTRUCTURE_CAPACITY = "INFRASTRUCTURE_CAPACITY"
    INFRASTRUCTURE_PLACEMENT = "INFRASTRUCTURE_PLACEMENT"
    ADMISSION_POLICY = "ADMISSION_POLICY"
    QUEUE_CAPACITY = "QUEUE_CAPACITY"
    LOCAL_COMPUTE_CAPABILITY = "LOCAL_COMPUTE_CAPABILITY"
    TASK_ORDERING = "TASK_ORDERING"
    TASK_PRIORITY_PRESSURE = "TASK_PRIORITY_PRESSURE"
    TRAFFIC_DEMAND = "TRAFFIC_DEMAND"
    INCIDENT_DISRUPTION = "INCIDENT_DISRUPTION"
    MODEL_INFRASTRUCTURE_INTERACTION = "MODEL_INFRASTRUCTURE_INTERACTION"


UNREPRESENTABLE_HYPOTHESES: dict[ChallengeHypothesis, str] = {
    ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT: PLACEMENT_LIMITATION,
    ChallengeHypothesis.ADMISSION_POLICY: ADMISSION_LIMITATION,
    ChallengeHypothesis.QUEUE_CAPACITY: QUEUE_CAPACITY_LIMITATION,
    ChallengeHypothesis.LOCAL_COMPUTE_CAPABILITY: FLEET_CAPABILITY_LIMITATION,
    ChallengeHypothesis.TASK_ORDERING: TASK_ORDERING_LIMITATION,
}

# Ordered phrase table: the first matching phrase decides, so specific
# unrepresentable mechanisms are recognised before generic pressure words.
_HYPOTHESIS_PHRASES: tuple[tuple[str, ChallengeHypothesis], ...] = (
    ("placement", ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT),
    ("load balanc", ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT),
    ("redistribut", ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT),
    ("load management", ChallengeHypothesis.INFRASTRUCTURE_PLACEMENT),
    ("admission", ChallengeHypothesis.ADMISSION_POLICY),
    ("reject", ChallengeHypothesis.ADMISSION_POLICY),
    ("queue", ChallengeHypothesis.QUEUE_CAPACITY),
    ("waiting", ChallengeHypothesis.QUEUE_CAPACITY),
    ("ordering", ChallengeHypothesis.TASK_ORDERING),
    ("local comput", ChallengeHypothesis.LOCAL_COMPUTE_CAPABILITY),
    ("onboard", ChallengeHypothesis.LOCAL_COMPUTE_CAPABILITY),
    ("capabilit", ChallengeHypothesis.LOCAL_COMPUTE_CAPABILITY),
    ("interaction", ChallengeHypothesis.MODEL_INFRASTRUCTURE_INTERACTION),
    ("both layers", ChallengeHypothesis.MODEL_INFRASTRUCTURE_INTERACTION),
    ("model and infrastructure", ChallengeHypothesis.MODEL_INFRASTRUCTURE_INTERACTION),
    ("policy and infrastructure", ChallengeHypothesis.MODEL_INFRASTRUCTURE_INTERACTION),
    ("incident", ChallengeHypothesis.INCIDENT_DISRUPTION),
    ("disruption", ChallengeHypothesis.INCIDENT_DISRUPTION),
    ("closure", ChallengeHypothesis.INCIDENT_DISRUPTION),
    ("capacity", ChallengeHypothesis.INFRASTRUCTURE_CAPACITY),
    ("service", ChallengeHypothesis.INFRASTRUCTURE_CAPACITY),
    ("provision", ChallengeHypothesis.INFRASTRUCTURE_CAPACITY),
    ("rsu", ChallengeHypothesis.INFRASTRUCTURE_CAPACITY),
    ("priority", ChallengeHypothesis.TASK_PRIORITY_PRESSURE),
    ("deadline", ChallengeHypothesis.TASK_PRIORITY_PRESSURE),
    ("task mix", ChallengeHypothesis.TASK_PRIORITY_PRESSURE),
    ("demanding task", ChallengeHypothesis.TASK_PRIORITY_PRESSURE),
    ("congestion", ChallengeHypothesis.TRAFFIC_DEMAND),
    ("demand", ChallengeHypothesis.TRAFFIC_DEMAND),
    ("traffic", ChallengeHypothesis.TRAFFIC_DEMAND),
)

_HYPOTHESIS_FAMILIES: dict[ChallengeHypothesis, tuple[ChallengeFamily, ...]] = {
    ChallengeHypothesis.INFRASTRUCTURE_CAPACITY: (
        ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE,
        ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
        ChallengeFamily.INCIDENT_PRESSURE,
    ),
    ChallengeHypothesis.TASK_PRIORITY_PRESSURE: (
        ChallengeFamily.TASK_MIX_SHIFT,
        ChallengeFamily.TASK_PRESSURE,
    ),
    ChallengeHypothesis.TRAFFIC_DEMAND: (
        ChallengeFamily.TRAFFIC_DEMAND_PRESSURE,
        ChallengeFamily.INCIDENT_PRESSURE,
    ),
    ChallengeHypothesis.INCIDENT_DISRUPTION: (
        ChallengeFamily.INCIDENT_PRESSURE,
        ChallengeFamily.TRAFFIC_DEMAND_PRESSURE,
    ),
    ChallengeHypothesis.MODEL_INFRASTRUCTURE_INTERACTION: (
        ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
        ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE,
        ChallengeFamily.TASK_MIX_SHIFT,
    ),
}

_MAKE_HARDER_FAMILIES: tuple[ChallengeFamily, ...] = (
    ChallengeFamily.TASK_PRESSURE,
    ChallengeFamily.TRAFFIC_DEMAND_PRESSURE,
    ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE,
)
_SURPRISE_FAMILIES: tuple[ChallengeFamily, ...] = (
    ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
    ChallengeFamily.INCIDENT_PRESSURE,
    ChallengeFamily.TASK_MIX_SHIFT,
)

_RECOMMENDATION_FAMILY_BIAS: dict[RecommendationCategory, tuple[ChallengeFamily, ...]] = {
    RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY: (
        ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE,
        ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
    ),
    RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING: (
        ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
        ChallengeFamily.TASK_MIX_SHIFT,
    ),
    RecommendationCategory.MIXED_INVESTIGATION: (ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,),
    RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL: (
        ChallengeFamily.INCIDENT_PRESSURE,
        ChallengeFamily.TRAFFIC_DEMAND_PRESSURE,
    ),
}

_DISTINGUISHING_NOTE = (
    "These candidates are intended to distinguish competing explanations; "
    "no candidate proves which explanation is correct."
)


class ProposedParameterChange(AnalystModel):
    """One exact ledger entry: a supported field, its baseline, its proposal."""

    whatif_field: str
    baseline_value: CandidateValue
    proposed_value: CandidateValue
    direction: Literal["increase", "decrease", "switch", "enable"]
    basis: str


class UnsupportedChallengeIdea(AnalystModel):
    """One idea a candidate names but the contract cannot represent."""

    idea: str
    reason: str


class ChallengeScenarioProposal(AnalystModel):
    """One structured, validated, non-executing candidate scenario."""

    schema_version: Literal["challenge-candidates-1.0"] = CANDIDATE_SCHEMA_VERSION
    designer_version: Literal["challenge-designer-1.0"] = CANDIDATE_DESIGNER_VERSION
    proposal_id: str
    title: str
    short_description: str
    family: ChallengeFamily
    generation_mode: CandidateGenerationMode
    baseline_preset: str
    baseline_digest: str
    evidence_standing: Literal[
        "synthetic what-if proposal (derived scenario; not an observation)"
    ] = DERIVED_SCENARIO_STANDING
    intended_mechanism: str
    changed_parameters: tuple[ProposedParameterChange, ...]
    held_constant: tuple[HeldFixedControl, ...]
    unsupported_ideas: tuple[UnsupportedChallengeIdea, ...] = ()
    primary_observation_targets: tuple[str, ...]
    secondary_observation_targets: tuple[str, ...] = ()
    why_informative: str
    not_maximal_basis: str
    cannot_establish: str
    validation_status: CandidateValidationStatus
    validation_reasons: tuple[str, ...] = ()
    triviality_basis: str = TRIVIALITY_BASIS
    prediction_status: Literal["PREDICTION_UNAVAILABLE"] = "PREDICTION_UNAVAILABLE"
    prediction_reason: str = PREDICTION_UNAVAILABLE_REASON
    limitations: tuple[str, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    generated_by: Literal["deterministic_template", "llm_proposal_validated"]
    llm_used: bool = False
    llm_evidence: Literal[False] = False
    approval: Literal[False] = False
    execution_authority: Literal[False] = False
    creates_new_evidence: Literal[False] = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def mechanism_fingerprint(self) -> str:
        """Novelty identity: family + changed field names + baseline."""

        identity = json.dumps(
            {
                "family": self.family.value,
                "changed_fields": sorted(change.whatif_field for change in self.changed_parameters),
                "baseline_digest": self.baseline_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(identity.encode("utf-8")).hexdigest()


class ChallengeCandidateSet(AnalystModel):
    """The reviewable result of one design request."""

    schema_version: Literal["challenge-candidates-1.0"] = CANDIDATE_SCHEMA_VERSION
    designer_version: Literal["challenge-designer-1.0"] = CANDIDATE_DESIGNER_VERSION
    mode: CandidateGenerationMode
    requested_hypothesis: ChallengeHypothesis | None = None
    recommendation_category: str | None = None
    baseline_preset: str
    baseline_digest: str
    outcome: Literal[
        "CANDIDATES_PREPARED",
        "HYPOTHESIS_NOT_REPRESENTABLE",
        "INSUFFICIENT_CONTEXT",
    ]
    candidates: tuple[ChallengeScenarioProposal, ...] = ()
    unrepresentable_reasons: tuple[UnsupportedChallengeIdea, ...] = ()
    designer_notes: tuple[str, ...] = ()
    execution_authority: Literal[False] = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


class ExternalChallengeProposal(AnalystModel):
    """The only payload shape an external (LLM) proposer may submit."""

    title: str
    family: str
    intended_mechanism: str
    rationale: str
    changed_parameters: dict[str, CandidateValue]
    unsupported_ideas: tuple[str, ...] = ()


class FieldBound(AnalystModel):
    """One supported field with its registered numeric bounds."""

    whatif_field: str
    minimum: float | None = None
    maximum: float | None = None
    value_type: str


class CandidateProposalRequest(AnalystModel):
    """The compact capability schema an LLM proposer receives — nothing else."""

    schema_version: Literal["challenge-candidates-1.0"] = CANDIDATE_SCHEMA_VERSION
    mode: CandidateGenerationMode
    requested_hypothesis: ChallengeHypothesis | None = None
    family_vocabulary: tuple[str, ...]
    supported_fields: tuple[FieldBound, ...]
    registered_policy_profiles: tuple[str, ...]
    baseline: dict[str, CandidateValue]
    known_unrepresentable: tuple[str, ...]
    instruction: str

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def default_candidate_baseline() -> dict[str, CandidateValue]:
    """The registered What-If baseline as the candidate design surface."""

    baseline: dict[str, CandidateValue] = {}
    for field in (*SUPPORTED_CANDIDATE_FIELDS, *CANDIDATE_IDENTITY_FIELDS):
        widget_key = f"whatif_{field}"
        if widget_key in DEFAULT_WHATIF_WIDGET_VALUES:
            baseline[field] = DEFAULT_WHATIF_WIDGET_VALUES[widget_key]
    return baseline


def _baseline_digest(baseline: Mapping[str, CandidateValue]) -> str:
    serialised = json.dumps(
        {key: baseline[key] for key in sorted(baseline)},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return sha256(serialised.encode("utf-8")).hexdigest()


def _require_baseline(baseline: Mapping[str, CandidateValue] | None) -> dict[str, CandidateValue]:
    resolved = dict(baseline) if baseline is not None else default_candidate_baseline()
    missing = [field for field in SUPPORTED_CANDIDATE_FIELDS if field not in resolved]
    if missing:
        raise AnalystRefusalError(
            AnalystRefusalCode.INSUFFICIENT_EVIDENCE,
            "The candidate baseline is incomplete; missing supported fields: "
            + ", ".join(sorted(missing)),
        )
    for field, value in resolved.items():
        if field == "policy_profile":
            if value not in REGISTERED_POLICY_PROFILES:
                raise AnalystRefusalError(
                    AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                    f"baseline policy_profile {value!r} is not a registered profile",
                )
            continue
        representable, reason = is_value_representable(field, value)
        if not representable:
            raise AnalystRefusalError(
                AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                f"baseline value for {field!r} is not representable: {reason}",
            )
    return resolved


def _step_up(field: str, current: float) -> float:
    spec = WHATIF_CONTROL_SPEC[field]
    maximum = spec.get("max")
    if maximum is not None:
        proposed = current + HARDER_STEP_FRACTION * (float(maximum) - current)
    else:
        proposed = current * (1.0 + HARDER_STEP_FRACTION)
    return round(proposed, 6)


def _step_down(field: str, current: float) -> float:
    spec = WHATIF_CONTROL_SPEC[field]
    minimum = float(spec["min"])
    proposed = current - HARDER_STEP_FRACTION * (current - minimum)
    return round(proposed, 6)


_STEP_BASIS = (
    "One bounded step of the remaining headroom "
    f"(HARDER_STEP_FRACTION={HARDER_STEP_FRACTION}); a reviewable design "
    "suggestion inside the registered What-If bounds, not a scientific "
    "threshold. Adjust it in What-If Studio."
)


def _change(
    field: str,
    baseline: Mapping[str, CandidateValue],
    proposed: CandidateValue,
    direction: Literal["increase", "decrease", "switch", "enable"],
) -> ProposedParameterChange:
    return ProposedParameterChange(
        whatif_field=field,
        baseline_value=baseline[field],
        proposed_value=proposed,
        direction=direction,
        basis=_STEP_BASIS
        if direction in ("increase", "decrease")
        else ("Registered choice from the existing What-If contract."),
    )


def _held_constant(
    baseline: Mapping[str, CandidateValue], changed_fields: tuple[str, ...]
) -> tuple[HeldFixedControl, ...]:
    controls: list[HeldFixedControl] = []
    for field in (*SUPPORTED_CANDIDATE_FIELDS, *CANDIDATE_IDENTITY_FIELDS):
        if field in changed_fields or field not in baseline:
            continue
        controls.append(
            HeldFixedControl(
                dimension=field,
                group=_FIELD_GROUPS[field],
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
            basis=(
                "Both arms are validated by the same metric engine and "
                "compared under the existing comparison contract; metric "
                "definitions never vary."
            ),
        )
    )
    return tuple(controls)


def _structural_triviality_reasons(
    changed: tuple[ProposedParameterChange, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    for change in changed:
        spec = WHATIF_CONTROL_SPEC.get(change.whatif_field)
        if spec is None or not isinstance(change.proposed_value, (int, float)):
            continue
        if isinstance(change.proposed_value, bool):
            continue
        value = float(change.proposed_value)
        minimum = spec.get("min")
        maximum = spec.get("max")
        if minimum is not None and abs(value - float(minimum)) <= 1e-9:
            reasons.append(
                f"{change.whatif_field} sits exactly on its registered minimum "
                f"({minimum}); bound-saturated values resemble maximal stress."
            )
        if maximum is not None and abs(value - float(maximum)) <= 1e-9:
            reasons.append(
                f"{change.whatif_field} sits exactly on its registered maximum "
                f"({maximum}); bound-saturated values resemble maximal stress."
            )
    escalations = [change for change in changed if change.direction == "increase"]
    if len(changed) >= 4 and len(escalations) == len(changed):
        reasons.append(
            "Every changed dimension escalates in the same direction across "
            "four or more fields; broad same-direction escalation is "
            "maximal-stress design, which rarely distinguishes mechanisms."
        )
    return tuple(reasons)


def _cross_field_reasons(
    baseline: Mapping[str, CandidateValue],
    changed: tuple[ProposedParameterChange, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    effective: dict[str, CandidateValue] = dict(baseline)
    for change in changed:
        effective[change.whatif_field] = change.proposed_value
    mix_fields = ("task_mix_t1", "task_mix_t2", "task_mix_t3")
    if any(change.whatif_field in mix_fields for change in changed):
        total = sum(float(effective[field]) for field in mix_fields)
        if abs(total - 1.0) > 1e-6:
            reasons.append(f"task mix shares must sum to 1.0; the proposal sums to {total:.6f}.")
    incident_value_fields = (
        "incident_type",
        "incident_location",
        "incident_severity",
        "incident_start_s",
        "incident_duration_s",
        "lanes_closed",
        "event_demand_multiplier",
    )
    touches_incident = any(change.whatif_field in incident_value_fields for change in changed)
    if touches_incident and effective.get("incident_enabled") is not True:
        reasons.append(
            "incident fields are varied while incident_enabled is False; the "
            "variation would silently ignore them."
        )
    return tuple(reasons)


def _finalise_proposal(
    *,
    title: str,
    short_description: str,
    family: ChallengeFamily,
    mode: CandidateGenerationMode,
    baseline: Mapping[str, CandidateValue],
    changed: tuple[ProposedParameterChange, ...],
    intended_mechanism: str,
    primary_targets: tuple[str, ...],
    secondary_targets: tuple[str, ...],
    why_informative: str,
    cannot_establish: str,
    unsupported_ideas: tuple[UnsupportedChallengeIdea, ...] = (),
    limitations: tuple[str, ...] = (),
    generated_by: Literal["deterministic_template", "llm_proposal_validated"],
    llm_used: bool = False,
) -> ChallengeScenarioProposal:
    """Shared deterministic validation and construction for every source."""

    if not changed:
        raise AnalystRefusalError(
            AnalystRefusalCode.INSUFFICIENT_EVIDENCE,
            "A candidate must change at least one supported parameter.",
        )
    for change in changed:
        if change.whatif_field not in SUPPORTED_CANDIDATE_FIELDS:
            raise AnalystRefusalError(
                AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                f"{change.whatif_field!r} is not a supported What-If field.",
            )
        if change.whatif_field == "policy_profile":
            if change.proposed_value not in REGISTERED_POLICY_PROFILES:
                raise AnalystRefusalError(
                    AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                    f"{change.proposed_value!r} is not a registered policy profile.",
                )
        else:
            representable, reason = is_value_representable(
                change.whatif_field, change.proposed_value
            )
            if not representable:
                raise AnalystRefusalError(
                    AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                    f"proposed value for {change.whatif_field!r} is not representable: {reason}",
                )
    cross_field = _cross_field_reasons(baseline, changed)
    if cross_field:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            "cross-field consistency failed: " + " ".join(cross_field),
        )

    triviality_reasons = _structural_triviality_reasons(changed)
    if unsupported_ideas:
        status = CandidateValidationStatus.PARTIALLY_REPRESENTABLE
        reasons: tuple[str, ...] = tuple(
            f"unsupported idea retained visibly (never transferred): {idea.idea}"
            for idea in unsupported_ideas
        )
    elif triviality_reasons:
        status = CandidateValidationStatus.VALID_BUT_TRIVIAL
        reasons = triviality_reasons
    else:
        status = CandidateValidationStatus.VALID_CHALLENGE
        reasons = ()

    changed_sorted = tuple(sorted(changed, key=lambda item: item.whatif_field))
    baseline_digest = _baseline_digest(baseline)
    identity = json.dumps(
        {
            "family": family.value,
            "changed": [(item.whatif_field, str(item.proposed_value)) for item in changed_sorted],
            "baseline_digest": baseline_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    identity_digest = sha256(identity.encode("utf-8")).hexdigest()[:8]
    proposal_id = f"{family.value.lower().replace('_', '-')}-{identity_digest}"
    return ChallengeScenarioProposal(
        proposal_id=proposal_id,
        title=title,
        short_description=short_description,
        family=family,
        generation_mode=mode,
        baseline_preset=str(baseline.get("baseline_preset", "baseline")),
        baseline_digest=baseline_digest,
        intended_mechanism=intended_mechanism,
        changed_parameters=changed_sorted,
        held_constant=_held_constant(baseline, tuple(item.whatif_field for item in changed_sorted)),
        unsupported_ideas=unsupported_ideas,
        primary_observation_targets=primary_targets,
        secondary_observation_targets=secondary_targets,
        why_informative=why_informative,
        not_maximal_basis=(
            "Magnitudes take one bounded step of the remaining headroom and "
            "never sit on a registered bound; a single mechanism is pressured "
            "while every other dimension is held at baseline, so measurable "
            "headroom remains."
        ),
        cannot_establish=cannot_establish,
        validation_status=status,
        validation_reasons=reasons,
        limitations=(
            *limitations,
            "The candidate is bounded to the registered What-If contract and "
            "the selected synthetic baseline; it is a design proposal, not "
            "evidence, and it makes no real-world or causal claim.",
        ),
        provenance_refs=(
            f"baseline:{baseline_digest[:16]}",
            "bounds:WHATIF_CONTROL_SPEC",
            "profiles:SyntheticPolicyProfile",
        ),
        generated_by=generated_by,
        llm_used=llm_used,
    )


def _task_pressure_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    rate = _step_up("task_arrival_rate", float(baseline["task_arrival_rate"]))
    return _finalise_proposal(
        title="Task-arrival pressure",
        short_description=(
            "Raise task arrival pressure one bounded step while every other "
            "dimension stays at baseline."
        ),
        family=ChallengeFamily.TASK_PRESSURE,
        mode=mode,
        baseline=baseline,
        changed=(_change("task_arrival_rate", baseline, rate, "increase"),),
        intended_mechanism=(
            "Task arrival pressure: more work per unit time contends for the "
            "same vehicle and RSU service capacity."
        ),
        primary_targets=ANALYST_VEC_KEYS,
        secondary_targets=ANALYST_INFRASTRUCTURE_KEYS,
        why_informative=(
            "A single bounded arrival-rate step pressures offloading and "
            "service capacity together without touching the network or the "
            "policy, so strategy differences in handling contention have room "
            "to appear before saturation."
        ),
        cannot_establish=(
            "It cannot attribute outcome changes to the policy or the "
            "infrastructure, and it does not establish a causal mechanism."
        ),
        generated_by="deterministic_template",
    )


def _task_mix_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    t1 = float(baseline["task_mix_t1"])
    t2 = float(baseline["task_mix_t2"])
    t3 = float(baseline["task_mix_t3"])
    new_t1 = round(t1 + HARDER_STEP_FRACTION * (1.0 - t1), 6)
    remaining = 1.0 - new_t1
    share_basis = t2 + t3
    new_t2 = round(remaining * (t2 / share_basis), 6)
    new_t3 = round(1.0 - new_t1 - new_t2, 6)
    return _finalise_proposal(
        title="Demanding task-mix shift",
        short_description=(
            "Shift the task mix toward the T1 class one bounded step, "
            "rescaling the remaining classes so shares still sum to one."
        ),
        family=ChallengeFamily.TASK_MIX_SHIFT,
        mode=mode,
        baseline=baseline,
        changed=(
            _change("task_mix_t1", baseline, new_t1, "increase"),
            _change("task_mix_t2", baseline, new_t2, "decrease"),
            _change("task_mix_t3", baseline, new_t3, "decrease"),
        ),
        intended_mechanism=(
            "Task composition: a heavier share of the most demanding task "
            "class changes what a good offloading decision looks like without "
            "changing total arrival volume."
        ),
        primary_targets=ANALYST_VEC_KEYS,
        secondary_targets=ANALYST_INFRASTRUCTURE_KEYS,
        why_informative=(
            "Composition stress gives the offloading decision a meaningful "
            "role: strategies that treat all tasks alike and strategies that "
            "differentiate by class face different trade-offs at the same "
            "total load."
        ),
        cannot_establish=(
            "It cannot show that any policy handles the mix better in "
            "general, and it does not establish a causal mechanism."
        ),
        generated_by="deterministic_template",
    )


def _traffic_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    congestion = _step_up("congestion_multiplier", float(baseline["congestion_multiplier"]))
    return _finalise_proposal(
        title="Traffic-demand pressure",
        short_description=(
            "Raise the congestion multiplier one bounded step while tasks, "
            "infrastructure and the policy stay at baseline."
        ),
        family=ChallengeFamily.TRAFFIC_DEMAND_PRESSURE,
        mode=mode,
        baseline=baseline,
        changed=(_change("congestion_multiplier", baseline, congestion, "increase"),),
        intended_mechanism=(
            "Traffic demand: denser traffic changes trip conditions and the "
            "context in which offloading decisions are made."
        ),
        primary_targets=ANALYST_TRAFFIC_KEYS,
        secondary_targets=ANALYST_VEC_KEYS,
        why_informative=(
            "A bounded congestion step pressures the traffic layer without "
            "touching task workload or capacity, so traffic-sensitive and "
            "traffic-insensitive strategies can separate while completion "
            "remains measurable."
        ),
        cannot_establish=(
            "It cannot attribute task-outcome changes to the traffic layer "
            "alone and does not establish a causal mechanism."
        ),
        generated_by="deterministic_template",
    )


def _incident_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    duration = _step_up("incident_duration_s", float(baseline["incident_duration_s"]))
    event_demand = _step_up("event_demand_multiplier", float(baseline["event_demand_multiplier"]))
    return _finalise_proposal(
        title="Localised incident pressure",
        short_description=(
            "Lengthen the registered incident and raise its local demand one "
            "bounded step each — local pressure, not universal collapse."
        ),
        family=ChallengeFamily.INCIDENT_PRESSURE,
        mode=mode,
        baseline=baseline,
        changed=(
            _change("incident_duration_s", baseline, duration, "increase"),
            _change("event_demand_multiplier", baseline, event_demand, "increase"),
        ),
        intended_mechanism=(
            "Localised disturbance: a longer, locally heavier incident "
            "produces concentrated pressure at the registered incident "
            "location while the rest of the scene stays at baseline."
        ),
        primary_targets=ANALYST_TRAFFIC_KEYS,
        secondary_targets=(*ANALYST_VEC_KEYS, *ANALYST_INFRASTRUCTURE_KEYS),
        why_informative=(
            "Concentrated local pressure is the honest representable "
            "counterpart of demand concentration: it can reveal uneven "
            "pressure and recovery behaviour that a uniform global increase "
            "would hide."
        ),
        cannot_establish=(
            "It cannot isolate infrastructure placement (no placement "
            "dimension exists) and does not establish a causal mechanism."
        ),
        generated_by="deterministic_template",
    )


def _capacity_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    capacity = _step_down("rsu_capacity", float(baseline["rsu_capacity"]))
    return _finalise_proposal(
        title="Service-capacity pressure",
        short_description=(
            "Lower RSU service/compute capacity one bounded step while the "
            "policy, tasks and traffic stay at baseline."
        ),
        family=ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE,
        mode=mode,
        baseline=baseline,
        changed=(_change("rsu_capacity", baseline, capacity, "decrease"),),
        intended_mechanism=(
            "Infrastructure service capacity: reduced service/compute "
            "concurrency makes offloading capacity scarcer without changing "
            "demand or the policy. Queue capacity is a different dimension "
            "and is not varied."
        ),
        primary_targets=ANALYST_INFRASTRUCTURE_KEYS,
        secondary_targets=ANALYST_VEC_KEYS,
        why_informative=(
            "A bounded capacity reduction pressures exactly one resource, so "
            "capacity-sensitive behaviour becomes visible while headroom "
            "remains — the informative middle ground between slack and "
            "saturation."
        ),
        cannot_establish=(
            "It cannot show that capacity must be expanded, does not vary "
            "queue capacity, and does not establish a causal mechanism."
        ),
        limitations=(QUEUE_CAPACITY_LIMITATION,),
        generated_by="deterministic_template",
    )


def _interaction_candidate(
    baseline: Mapping[str, CandidateValue], mode: CandidateGenerationMode
) -> ChallengeScenarioProposal:
    current_profile = str(baseline["policy_profile"])
    alternative = next(
        profile for profile in sorted(REGISTERED_POLICY_PROFILES) if profile != current_profile
    )
    capacity = _step_down("rsu_capacity", float(baseline["rsu_capacity"]))
    return _finalise_proposal(
        title="Policy/infrastructure interaction stress",
        short_description=(
            "Switch to a different registered policy profile under one "
            "bounded step of service-capacity pressure — a deliberate "
            "two-layer stress scene."
        ),
        family=ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION,
        mode=mode,
        baseline=baseline,
        changed=(
            _change("policy_profile", baseline, alternative, "switch"),
            _change("rsu_capacity", baseline, capacity, "decrease"),
        ),
        intended_mechanism=(
            "Model/infrastructure interaction: the offloading-policy "
            "dimension and the service-capacity dimension are varied "
            "together so their combined behaviour can be observed."
        ),
        primary_targets=ANALYST_VEC_KEYS,
        secondary_targets=ANALYST_INFRASTRUCTURE_KEYS,
        why_informative=(
            "Vehicle-side offloading decisions and infrastructure-side "
            "capacity are separate mechanisms; observing them under joint, "
            "bounded pressure can surface interaction behaviour that "
            "single-dimension comparisons hide."
        ),
        cannot_establish=(
            "A two-dimension variation cannot attribute the outcome to "
            "either dimension alone. It is a stress scene for observing "
            "interaction; single-dimension What-If Challenge comparisons "
            "remain the attribution instrument."
        ),
        generated_by="deterministic_template",
    )


_FAMILY_BUILDERS = {
    ChallengeFamily.TASK_PRESSURE: _task_pressure_candidate,
    ChallengeFamily.TASK_MIX_SHIFT: _task_mix_candidate,
    ChallengeFamily.TRAFFIC_DEMAND_PRESSURE: _traffic_candidate,
    ChallengeFamily.INCIDENT_PRESSURE: _incident_candidate,
    ChallengeFamily.INFRASTRUCTURE_CAPACITY_PRESSURE: _capacity_candidate,
    ChallengeFamily.MODEL_INFRASTRUCTURE_INTERACTION: _interaction_candidate,
}


def dedupe_candidates(
    candidates: tuple[ChallengeScenarioProposal, ...],
) -> tuple[ChallengeScenarioProposal, ...]:
    """Collapse near-duplicates (same family, changed fields, baseline)."""

    seen: set[str] = set()
    kept: list[ChallengeScenarioProposal] = []
    for candidate in candidates:
        key = candidate.mechanism_fingerprint()
        if key in seen:
            continue
        seen.add(key)
        kept.append(candidate)
    return tuple(kept)


def match_hypothesis(free_text: str) -> ChallengeHypothesis | None:
    """Map bounded free text onto the hypothesis vocabulary, or None."""

    lowered = free_text.lower()
    for phrase, hypothesis in _HYPOTHESIS_PHRASES:
        if phrase in lowered:
            return hypothesis
    return None


def _families_for_request(
    mode: CandidateGenerationMode,
    hypothesis: ChallengeHypothesis | None,
    recommendation: RecommendationCategory | None,
) -> tuple[ChallengeFamily, ...]:
    if mode is CandidateGenerationMode.MAKE_HARDER:
        families = _MAKE_HARDER_FAMILIES
    elif mode is CandidateGenerationMode.SURPRISE_ME:
        families = _SURPRISE_FAMILIES
    else:
        assert hypothesis is not None
        families = _HYPOTHESIS_FAMILIES[hypothesis]
    if recommendation is None:
        return families
    preferred = _RECOMMENDATION_FAMILY_BIAS.get(recommendation, ())
    reordered = [family for family in preferred if family in families]
    reordered.extend(family for family in families if family not in reordered)
    return tuple(reordered)


def design_candidates(
    mode: CandidateGenerationMode,
    *,
    baseline: Mapping[str, CandidateValue] | None = None,
    hypothesis: ChallengeHypothesis | None = None,
    free_text: str | None = None,
    recommendation_category: str | None = None,
) -> ChallengeCandidateSet:
    """Deterministically design up to three distinct candidate scenarios.

    Works with no LLM, no evidence bundle and no prior recommendation;
    the optional recommendation category only reorders families.
    """

    if mode is CandidateGenerationMode.EXTERNAL_PROPOSAL:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            "EXTERNAL_PROPOSAL payloads go through validate_external_proposal.",
        )
    resolved_baseline = _require_baseline(baseline)
    digest = _baseline_digest(resolved_baseline)
    preset = str(resolved_baseline.get("baseline_preset", "baseline"))

    recommendation: RecommendationCategory | None = None
    notes: list[str] = []
    if recommendation_category is not None:
        try:
            recommendation = RecommendationCategory(recommendation_category)
        except ValueError as error:
            raise AnalystRefusalError(
                AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
                f"{recommendation_category!r} is not a recommendation category.",
            ) from error
        if recommendation in (
            RecommendationCategory.INSUFFICIENT_EVIDENCE,
            RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL,
        ):
            notes.append(_DISTINGUISHING_NOTE)
        if recommendation is RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT:
            notes.append(PLACEMENT_LIMITATION)

    if mode is CandidateGenerationMode.TEST_HYPOTHESIS:
        if hypothesis is None and free_text is not None:
            hypothesis = match_hypothesis(free_text)
        if hypothesis is None:
            return ChallengeCandidateSet(
                mode=mode,
                recommendation_category=recommendation_category,
                baseline_preset=preset,
                baseline_digest=digest,
                outcome="INSUFFICIENT_CONTEXT",
                designer_notes=(
                    "The request did not match the bounded hypothesis "
                    "vocabulary: "
                    + ", ".join(sorted(item.value for item in ChallengeHypothesis))
                    + ".",
                    *notes,
                ),
            )
        if hypothesis in UNREPRESENTABLE_HYPOTHESES:
            return ChallengeCandidateSet(
                mode=mode,
                requested_hypothesis=hypothesis,
                recommendation_category=recommendation_category,
                baseline_preset=preset,
                baseline_digest=digest,
                outcome="HYPOTHESIS_NOT_REPRESENTABLE",
                unrepresentable_reasons=(
                    UnsupportedChallengeIdea(
                        idea=hypothesis.value,
                        reason=UNREPRESENTABLE_HYPOTHESES[hypothesis],
                    ),
                ),
                designer_notes=(
                    "No supported parameter is substituted for the requested "
                    "mechanism; substituting a different parameter would "
                    "change the scientific meaning of the test.",
                    *notes,
                ),
            )

    families = _families_for_request(mode, hypothesis, recommendation)
    candidates = tuple(_FAMILY_BUILDERS[family](resolved_baseline, mode) for family in families)
    candidates = dedupe_candidates(candidates)[:MAX_CANDIDATES]
    return ChallengeCandidateSet(
        mode=mode,
        requested_hypothesis=hypothesis,
        recommendation_category=recommendation_category,
        baseline_preset=preset,
        baseline_digest=digest,
        outcome="CANDIDATES_PREPARED",
        candidates=candidates,
        designer_notes=tuple(notes),
    )


def _guard_external_text(proposal: ExternalChallengeProposal) -> None:
    joined = " ".join((proposal.title, proposal.intended_mechanism, proposal.rationale)).lower()
    for marker in _WINNER_CLAIM_MARKERS:
        if marker in joined:
            raise AnalystProseError(
                "LLM_WINNER_CLAIM_REFUSED",
                f"the proposal predicts a winner ({marker!r}); scenario design "
                "may target mechanisms, never outcomes",
            )
    for marker in _EVIDENCE_CLAIM_MARKERS:
        if marker in joined:
            raise AnalystProseError(
                "LLM_EVIDENCE_FABRICATED",
                f"the proposal claims evidence ({marker!r}); an unexecuted scenario has no results",
            )
    allowed_numbers = set(
        _NUMBER_PATTERN.findall(
            json.dumps(proposal.changed_parameters, sort_keys=True, default=str)
        )
    )
    invented = [
        token
        for token in _NUMBER_PATTERN.findall(
            " ".join((proposal.intended_mechanism, proposal.rationale))
        )
        if token not in allowed_numbers
    ]
    if invented:
        raise AnalystProseError(
            "LLM_EVIDENCE_FABRICATED",
            "the proposal introduces numbers that are not proposed parameter "
            "values: " + ", ".join(sorted(set(invented))[:5]),
        )


def validate_external_proposal(
    payload: Mapping[str, object],
    *,
    baseline: Mapping[str, CandidateValue] | None = None,
) -> ChallengeScenarioProposal:
    """Deterministically validate one externally proposed candidate.

    The external proposer (typically an LLM) may only suggest; this
    function decides. Unknown parameters, out-of-bounds values, winner
    claims and fabricated evidence language are typed refusals.
    """

    resolved_baseline = _require_baseline(baseline)
    try:
        proposal = ExternalChallengeProposal.model_validate(dict(payload))
    except Exception as error:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            f"the proposal payload does not match the required schema: {error}",
        ) from error
    try:
        family = ChallengeFamily(proposal.family)
    except ValueError as error:
        raise AnalystProseError(
            "LLM_UNKNOWN_PARAMETER",
            f"{proposal.family!r} is not a registered challenge family",
        ) from error
    for field in proposal.changed_parameters:
        if field not in SUPPORTED_CANDIDATE_FIELDS:
            raise AnalystProseError(
                "LLM_UNKNOWN_PARAMETER",
                f"{field!r} is not a supported What-If field; parameters cannot be invented",
            )
    _guard_external_text(proposal)

    changed: list[ProposedParameterChange] = []
    for field in sorted(proposal.changed_parameters):
        value = proposal.changed_parameters[field]
        if field == "policy_profile":
            if value not in REGISTERED_POLICY_PROFILES:
                raise AnalystProseError(
                    "LLM_BOUNDS_VIOLATION",
                    f"{value!r} is not a registered policy profile",
                )
            direction: Literal["increase", "decrease", "switch", "enable"] = "switch"
        elif isinstance(value, bool):
            direction = "enable"
        else:
            representable, reason = is_value_representable(field, value)
            if not representable:
                raise AnalystProseError(
                    "LLM_BOUNDS_VIOLATION",
                    f"proposed value for {field!r} is outside the registered bounds: {reason}",
                )
            baseline_value = resolved_baseline[field]
            if isinstance(value, str) or isinstance(baseline_value, str):
                direction = "switch"
            else:
                direction = "increase" if float(value) > float(baseline_value) else "decrease"
        changed.append(
            ProposedParameterChange(
                whatif_field=field,
                baseline_value=resolved_baseline[field],
                proposed_value=value,
                direction=direction,
                basis=(
                    "Externally proposed value validated against the "
                    "registered What-If bounds; deterministic validation "
                    "decides, the proposer does not."
                ),
            )
        )
    unsupported = tuple(
        UnsupportedChallengeIdea(
            idea=idea,
            reason=(
                "Named by the proposer but not representable by any "
                "registered What-If dimension; shown separately and never "
                "transferred or approximated."
            ),
        )
        for idea in proposal.unsupported_ideas
    )
    candidate = _finalise_proposal(
        title=proposal.title,
        short_description=proposal.rationale,
        family=family,
        mode=CandidateGenerationMode.EXTERNAL_PROPOSAL,
        baseline=resolved_baseline,
        changed=tuple(changed),
        intended_mechanism=proposal.intended_mechanism,
        primary_targets=ANALYST_VEC_KEYS,
        secondary_targets=(*ANALYST_INFRASTRUCTURE_KEYS, *ANALYST_TRAFFIC_KEYS),
        why_informative=proposal.rationale,
        cannot_establish=(
            "It cannot predict or establish outcomes; an unexecuted scenario "
            "has no results and no causal standing."
        ),
        unsupported_ideas=unsupported,
        generated_by="llm_proposal_validated",
        llm_used=True,
    )
    template_fingerprints = {
        item.mechanism_fingerprint()
        for item in design_candidates(
            CandidateGenerationMode.SURPRISE_ME, baseline=resolved_baseline
        ).candidates
    } | {
        item.mechanism_fingerprint()
        for item in design_candidates(
            CandidateGenerationMode.MAKE_HARDER, baseline=resolved_baseline
        ).candidates
    }
    if (
        candidate.validation_status is CandidateValidationStatus.VALID_CHALLENGE
        and candidate.mechanism_fingerprint() in template_fingerprints
    ):
        candidate = candidate.model_copy(
            update={
                "validation_status": CandidateValidationStatus.VALID_BUT_REDUNDANT,
                "validation_reasons": (
                    "The proposal duplicates a deterministic template "
                    "candidate (same family, changed fields and baseline).",
                ),
            }
        )
    return candidate


_PROPOSER_INSTRUCTION = (
    "Propose up to three candidate what-if scenarios as JSON: "
    '{"proposals": [{"title": str, "family": one of the family vocabulary, '
    '"intended_mechanism": str, "rationale": str, "changed_parameters": '
    '{supported field: value}, "unsupported_ideas": [str]}]}. Use only the '
    "supported fields inside their bounds and the registered policy "
    "profiles. Vary different mechanisms across proposals. Never predict a "
    "winner, never claim evidence or results, never invent parameters, and "
    "put any idea the fields cannot express into unsupported_ideas instead "
    "of approximating it."
)


def build_candidate_proposal_request(
    mode: CandidateGenerationMode,
    *,
    baseline: Mapping[str, CandidateValue] | None = None,
    hypothesis: ChallengeHypothesis | None = None,
) -> CandidateProposalRequest:
    """Build the compact, credential-free capability schema for the LLM."""

    resolved_baseline = _require_baseline(baseline)
    bounds: list[FieldBound] = []
    for field in SUPPORTED_CANDIDATE_FIELDS:
        spec = WHATIF_CONTROL_SPEC.get(field)
        if spec is None:
            bounds.append(FieldBound(whatif_field=field, value_type="str"))
            continue
        bounds.append(
            FieldBound(
                whatif_field=field,
                minimum=float(spec["min"]) if "min" in spec else None,
                maximum=float(spec["max"]) if "max" in spec else None,
                value_type="int" if spec.get("type") is int else "float",
            )
        )
    return CandidateProposalRequest(
        mode=mode,
        requested_hypothesis=hypothesis,
        family_vocabulary=tuple(item.value for item in ChallengeFamily),
        supported_fields=tuple(bounds),
        registered_policy_profiles=REGISTERED_POLICY_PROFILES,
        baseline={field: resolved_baseline[field] for field in SUPPORTED_CANDIDATE_FIELDS},
        known_unrepresentable=(
            PLACEMENT_LIMITATION,
            ADMISSION_LIMITATION,
            QUEUE_CAPACITY_LIMITATION,
            FLEET_CAPABILITY_LIMITATION,
            TASK_ORDERING_LIMITATION,
        ),
        instruction=_PROPOSER_INSTRUCTION,
    )


def propose_candidates_with_llm(
    request: CandidateProposalRequest,
    *,
    api_key: str | None = None,
    transport: AnalystTransport = default_deepseek_transport,
) -> tuple[ChallengeScenarioProposal, ...]:
    """Ask the LLM to PROPOSE; validate every proposal deterministically.

    Without a configured key this raises ``LLM_NOT_CONFIGURED`` and the
    deterministic modes remain complete; the LLM is an optional composer,
    never a dependency and never a validator.
    """

    import os

    serialised = request.canonical_json()
    screen_prose_payload(serialised)
    key = api_key or os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise AnalystProseError(
            "LLM_NOT_CONFIGURED", "DEEPSEEK_API_KEY is unavailable in this process"
        )
    body = json.dumps(
        {
            "model": ANALYST_DEEPSEEK_MODEL,
            "messages": (
                {"role": "system", "content": _PROPOSER_INSTRUCTION},
                {"role": "user", "content": serialised},
            ),
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "temperature": 0,
            "max_tokens": 900,
            "stream": False,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    raw = transport(ANALYST_DEEPSEEK_API_URL, headers, body, ANALYST_TIMEOUT_SECONDS)
    content = parse_deepseek_response_content(raw)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as error:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE", "DeepSeek content is not valid JSON"
        ) from error
    if not isinstance(parsed, dict) or set(parsed) != {"proposals"}:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            'DeepSeek content must contain exactly a "proposals" list',
        )
    proposals = parsed["proposals"]
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= MAX_CANDIDATES:
        raise AnalystProseError(
            "LLM_MALFORMED_RESPONSE",
            f"proposals must be a list of 1..{MAX_CANDIDATES} items",
        )
    validated = tuple(
        validate_external_proposal(item, baseline=dict(request.baseline)) for item in proposals
    )
    return dedupe_candidates(validated)[:MAX_CANDIDATES]


_HANDOFF_ALLOWED_STATUSES = frozenset(
    {
        CandidateValidationStatus.VALID_CHALLENGE,
        CandidateValidationStatus.VALID_BUT_TRIVIAL,
        CandidateValidationStatus.VALID_BUT_REDUNDANT,
        CandidateValidationStatus.PARTIALLY_REPRESENTABLE,
    }
)


def candidate_to_whatif_draft(proposal: ChallengeScenarioProposal) -> ChallengeWhatIfDraft:
    """Convert one selected candidate into the existing Studio handoff draft.

    Pure function: mutates nothing, executes nothing. The user still
    reviews and applies the draft inside What-If Studio, where generation
    remains an explicit human act.
    """

    if proposal.validation_status not in _HANDOFF_ALLOWED_STATUSES:
        raise AnalystRefusalError(
            AnalystRefusalCode.UNSUPPORTED_RECOMMENDATION,
            f"a {proposal.validation_status.value} candidate cannot be handed to What-If Studio",
        )
    overrides: dict[str, CandidateValue] = {
        change.whatif_field: change.proposed_value for change in proposal.changed_parameters
    }
    incident_value_fields = {
        "incident_type",
        "incident_location",
        "incident_severity",
        "incident_start_s",
        "incident_duration_s",
        "lanes_closed",
        "event_demand_multiplier",
    }
    if incident_value_fields & overrides.keys() and "incident_enabled" not in overrides:
        overrides["incident_enabled"] = True
    mapped = [
        ChallengeWhatIfMappedField(
            challenge_path=f"candidate.{proposal.proposal_id}.{change.whatif_field}",
            challenge_value=change.proposed_value,
            whatif_field=change.whatif_field,
            mapped_value=change.proposed_value,
            rationale=change.basis,
        )
        for change in proposal.changed_parameters
    ]
    unsupported = [
        ChallengeWhatIfUnsupportedField(
            challenge_path=f"candidate.{proposal.proposal_id}.unsupported",
            challenge_value=idea.idea,
            reason=idea.reason,
        )
        for idea in proposal.unsupported_ideas
    ]
    warnings = [
        "Prepared from a Challenge Designer candidate; review the prefill in "
        "What-If Studio and generate the pair explicitly. Nothing has been "
        "executed.",
    ]
    if proposal.validation_status is CandidateValidationStatus.VALID_BUT_TRIVIAL:
        warnings.append(
            "Deterministic validation flagged this candidate as structurally "
            "trivial: " + " ".join(proposal.validation_reasons)
        )
    if unsupported:
        warnings.append(
            "Only the supported subset is prefilled; the unsupported ideas "
            "listed are not transferred and not approximated."
        )
    identity = json.dumps(
        {
            "proposal_fingerprint": proposal.fingerprint(),
            "overrides": {key: overrides[key] for key in sorted(overrides)},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return ChallengeWhatIfDraft(
        challenge_id=f"challenge-candidate-{proposal.fingerprint()[:12]}",
        challenge_title=proposal.title,
        mapping_status=(
            ChallengeWhatIfMappingStatus.PARTIALLY_MAPPABLE
            if unsupported
            else ChallengeWhatIfMappingStatus.FULLY_MAPPABLE
        ),
        supported_fields=mapped,
        unsupported_fields=unsupported,
        whatif_overrides=dict(overrides),
        warnings=warnings,
        fingerprint=sha256(identity.encode("utf-8")).hexdigest(),
        evidence_standing=proposal.evidence_standing,
        source_status=proposal.validation_status.value,
    )

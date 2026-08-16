"""Deterministic next-investigation selection over the Analyst result.

The Analyst answers "what does the evidence indicate"; this layer answers
"given that, what is the most defensible next investigation". Selection is
a pure mapping over the Analyst classification and the typed rule
outcomes already inside the Analyst Evidence Packet. It introduces no
thresholds and authors no advice: every suggested action quotes an
existing conditional ``Recommendation`` emitted by a deterministic rule.
The LLM (see ``recommendation_prose``) only explains the already-decided
result and is structurally unable to change it.

Category derivation:

- Model-side signal (R1/R5 triggered) → investigate the learned policy or
  its training conditions.
- Infrastructure-side signal: R4 (load imbalance) triggered → investigate
  RSU load management first — the project direction is to examine
  deterministic infrastructure-side load management while keeping the
  trained policy unchanged; R2-only → investigate capacity constraints
  under a controlled variation (R2's own recommendation).
- Mixed signal → both tracks, explicitly, with no winner.
- Insufficient signal with a side-less triggered candidate (R3/R6/R7/R8)
  and no readiness gate → a controlled scenario comparison, quoting those
  rules' own comparison recommendations.
- No material problem → no intervention is fabricated.
- Everything else stays insufficient: a first-class successful outcome.
"""

from __future__ import annotations

import json
from enum import StrEnum
from hashlib import sha256
from typing import Literal

from traffictwin.analyst.models import (
    INFRASTRUCTURE_SIDE_RULE_IDS,
    MODEL_SIDE_RULE_IDS,
    AnalystClassification,
    AnalystEvidencePacket,
    AnalystModel,
    AnalystRefusalCode,
    AnalystRefusalError,
    AnalystRuleFact,
    AnalystSignal,
)

RECOMMENDATION_PACKET_SCHEMA_VERSION: Literal["recommendation-packet-1.0"] = (
    "recommendation-packet-1.0"
)
RECOMMENDATION_SELECTOR_VERSION: Literal["recommendation-selector-1.0"] = (
    "recommendation-selector-1.0"
)

_TRIGGERED = "triggered"
_SIDELESS_CANDIDATE_RULE_IDS: tuple[str, ...] = ("R3", "R6", "R7", "R8")

WHATIF_PREFILL_DEFERRED_REASON = (
    "Deferred: existing deterministic recommendations name a direction but "
    "no parameter magnitude, so any prefilled What-If value would be an "
    "invented threshold; and the existing prefill contract is "
    "challenge-typed, so a recommendation handoff would mislabel "
    "provenance. Open What-If Studio and choose values explicitly."
)


class RecommendationCategory(StrEnum):
    """The bounded next-investigation vocabulary."""

    INVESTIGATE_MODEL_OR_TRAINING = "INVESTIGATE_MODEL_OR_TRAINING"
    INVESTIGATE_RSU_LOAD_MANAGEMENT = "INVESTIGATE_RSU_LOAD_MANAGEMENT"
    INVESTIGATE_INFRASTRUCTURE_CAPACITY = "INVESTIGATE_INFRASTRUCTURE_CAPACITY"
    INVESTIGATE_SCENARIO_OR_CONTROL = "INVESTIGATE_SCENARIO_OR_CONTROL"
    MIXED_INVESTIGATION = "MIXED_INVESTIGATION"
    NO_ACTIONABLE_PROBLEM_DETECTED = "NO_ACTIONABLE_PROBLEM_DETECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


CATEGORY_DISPLAY_NAMES: dict[RecommendationCategory, str] = {
    RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING: (
        "Investigate the learned offloading policy or its training conditions"
    ),
    RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT: ("Investigate RSU load management"),
    RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY: (
        "Investigate infrastructure capacity constraints under a controlled variation"
    ),
    RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL: (
        "Investigate via a controlled scenario comparison"
    ),
    RecommendationCategory.MIXED_INVESTIGATION: (
        "Two investigation tracks: model-side and infrastructure-side"
    ),
    RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED: ("No actionable problem detected"),
    RecommendationCategory.INSUFFICIENT_EVIDENCE: (
        "Insufficient evidence to recommend a direction"
    ),
}

_CATEGORY_RATIONALES: dict[RecommendationCategory, str] = {
    RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING: (
        "The current evidence supports investigating whether the learned "
        "offloading policy or its training conditions are contributing to "
        "the observed signal. The available infrastructure-side checks did "
        "not trigger."
    ),
    RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT: (
        "The current evidence supports investigating infrastructure-side "
        "RSU load management before attributing the result to the learned "
        "offloading policy: work appears unevenly distributed while "
        "aggregate capacity remains."
    ),
    RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY: (
        "The current evidence supports investigating infrastructure-side "
        "capacity or placement constraints before attributing the result "
        "to the learned offloading policy."
    ),
    RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL: (
        "A material problem candidate is present, but the current evidence "
        "does not distinguish a model-side from an infrastructure-side "
        "explanation. A controlled scenario comparison is the most "
        "defensible next investigation."
    ),
    RecommendationCategory.MIXED_INVESTIGATION: (
        "The current evidence supports both model-side and "
        "infrastructure-side investigation. It does not justify choosing "
        "one as the sole mechanism; both tracks are laid out separately."
    ),
    RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED: (
        "No deterministic diagnostic rule triggered on the selected "
        "evidence, so no intervention is recommended. This does not prove "
        "the absence of problems outside the evaluated rules' scope."
    ),
    RecommendationCategory.INSUFFICIENT_EVIDENCE: (
        "TrafficTwin does not currently have enough evidence to recommend "
        "a model-side or infrastructure-side investigation."
    ),
}

_TRACK_BY_RULE: dict[str, Literal["model", "infrastructure", "scenario"]] = {
    "R1": "model",
    "R5": "model",
    "R2": "infrastructure",
    "R4": "infrastructure",
    "R3": "scenario",
    "R6": "scenario",
    "R7": "scenario",
    "R8": "scenario",
}


class RecommendationSource(AnalystModel):
    """One existing conditional rule recommendation, quoted verbatim."""

    rule_id: str
    rule_title: str
    rule_status: Literal["triggered"]
    track: Literal["model", "infrastructure", "scenario"]
    action: str
    rationale: str
    expected_direction: str
    prerequisite: str
    verification_step: str
    conditional: Literal[True] = True


class RecommendationEvidencePacket(AnalystModel):
    """The deterministic recommendation with its complete evidence chain.

    Carries no wall-clock field and only rebuild-stable digests, so
    identical inputs produce byte-equivalent canonical content.
    """

    schema_version: Literal["recommendation-packet-1.0"] = RECOMMENDATION_PACKET_SCHEMA_VERSION
    selector_version: Literal["recommendation-selector-1.0"] = RECOMMENDATION_SELECTOR_VERSION
    analyst_packet_fingerprint: str
    analyst_signal: str
    analyst_statement: str
    subject_kind: Literal["single_run", "comparison"]
    evidence_standing: str
    confidence: str
    confidence_basis: str
    category: RecommendationCategory
    headline: str
    rationale: str
    alternative_category: RecommendationCategory | None = None
    alternative_reason: str | None = None
    contributing_rule_ids: tuple[str, ...] = ()
    rule_statuses: tuple[tuple[str, str], ...] = ()
    supported_facts: tuple[str, ...] = ()
    not_established: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    unavailable_metric_keys: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    source_recommendations: tuple[RecommendationSource, ...] = ()
    provenance_refs: tuple[str, ...] = ()
    whatif_prefill_available: Literal[False] = False
    whatif_prefill_deferred_reason: str = WHATIF_PREFILL_DEFERRED_REASON
    creates_new_evidence: Literal[False] = False
    execution_authority: Literal[False] = False
    causal_claim_supported: Literal[False] = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _rules_by_id(packet: AnalystEvidencePacket) -> dict[str, AnalystRuleFact]:
    return {rule.rule_id: rule for rule in packet.diagnostics.subject_rules}


def _triggered_ids(rules: dict[str, AnalystRuleFact], rule_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        rule_id for rule_id in rule_ids if rule_id in rules and rules[rule_id].status == _TRIGGERED
    )


def _sources(
    rules: dict[str, AnalystRuleFact], rule_ids: tuple[str, ...]
) -> tuple[RecommendationSource, ...]:
    sources: list[RecommendationSource] = []
    for rule_id in sorted(rule_ids):
        rule = rules[rule_id]
        for item in rule.recommendations:
            sources.append(
                RecommendationSource(
                    rule_id=rule.rule_id,
                    rule_title=rule.title,
                    rule_status="triggered",
                    track=_TRACK_BY_RULE.get(rule.rule_id, "scenario"),
                    action=item.action,
                    rationale=item.rationale,
                    expected_direction=item.expected_direction,
                    prerequisite=item.prerequisite,
                    verification_step=item.verification_step,
                )
            )
    return tuple(sources)


def _standing(packet: AnalystEvidencePacket) -> str:
    standing: str = packet.identity.baseline_standing
    if packet.identity.variation_standing not in (None, standing):
        return "MIXED"
    return standing


def _stable_provenance_refs(packet: AnalystEvidencePacket) -> tuple[str, ...]:
    """Rebuild-stable digest prefixes only (no diagnostic-report identity)."""

    refs = [f"analyst_packet:{packet.fingerprint()[:16]}"]
    for name, value in (
        ("baseline_bundle", packet.provenance.baseline_bundle_fingerprint),
        ("variation_bundle", packet.provenance.variation_bundle_fingerprint),
        ("consequence_lens", packet.provenance.consequence_lens_fingerprint),
    ):
        if value is not None:
            refs.append(f"{name}:{value[:16]}")
    return tuple(refs)


def _not_established(category: RecommendationCategory) -> tuple[str, ...]:
    lines = [
        "A triggered rule is a deterministic candidate, not a proven root cause.",
        "The evidence describes differences and pressure signals; it does "
        "not establish a causal mechanism.",
    ]
    if category is RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING:
        lines.append(
            "The evidence does not establish that the learned policy is "
            "defective, and it does not establish that retraining is required."
        )
    if category in (
        RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT,
        RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY,
    ):
        lines.append(
            "The evidence does not establish that infrastructure is the "
            "causal mechanism, and it does not establish that capacity must "
            "be expanded."
        )
    return tuple(lines)


def select_recommendation(
    packet: AnalystEvidencePacket, classification: AnalystClassification
) -> RecommendationEvidencePacket:
    """Deterministically select the bounded next-investigation category.

    The classification must belong to the packet; a mismatched pair is a
    typed refusal, never a silent re-derivation.
    """

    if classification.packet_fingerprint != packet.fingerprint():
        raise AnalystRefusalError(
            AnalystRefusalCode.PROVENANCE_INCOMPLETE,
            "The classification does not belong to the supplied Analyst "
            "packet, so no recommendation is derivable from this pairing.",
        )

    rules = _rules_by_id(packet)
    infra = _triggered_ids(rules, INFRASTRUCTURE_SIDE_RULE_IDS)
    model = _triggered_ids(rules, MODEL_SIDE_RULE_IDS)
    sideless = _triggered_ids(rules, _SIDELESS_CANDIDATE_RULE_IDS)
    r0 = rules.get("R0")
    gate = packet.diagnostics.subject_readiness == "invalid" or (
        r0 is not None and r0.status == _TRIGGERED
    )

    category = RecommendationCategory.INSUFFICIENT_EVIDENCE
    contributing: tuple[str, ...] = ()
    alternative: RecommendationCategory | None = None
    alternative_reason: str | None = None

    signal = classification.signal
    if signal is AnalystSignal.MODEL_SIDE_SIGNAL and model:
        category = RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING
        contributing = model
    elif signal is AnalystSignal.INFRASTRUCTURE_SIDE_SIGNAL and infra:
        if "R4" in infra:
            category = RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT
            contributing = infra
            if "R2" in infra:
                alternative = RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY
                alternative_reason = (
                    "The infrastructure-bottleneck candidate (R2) also "
                    "triggered, so a capacity-focused investigation is a "
                    "deterministically supported alternative track."
                )
        else:
            category = RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY
            contributing = infra
    elif signal is AnalystSignal.MIXED_SIGNAL and (infra or model):
        category = RecommendationCategory.MIXED_INVESTIGATION
        contributing = (*model, *infra)
    elif signal is AnalystSignal.NO_MATERIAL_PROBLEM_DETECTED:
        category = RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED
    elif signal is AnalystSignal.INSUFFICIENT_EVIDENCE and not gate and sideless:
        category = RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL
        contributing = sideless

    sources = _sources(rules, contributing) if contributing else ()

    return RecommendationEvidencePacket(
        analyst_packet_fingerprint=classification.packet_fingerprint,
        analyst_signal=signal.value,
        analyst_statement=classification.statement,
        subject_kind=packet.identity.subject_kind,
        evidence_standing=_standing(packet),
        confidence=classification.confidence,
        confidence_basis=classification.confidence_basis,
        category=category,
        headline=CATEGORY_DISPLAY_NAMES[category],
        rationale=_CATEGORY_RATIONALES[category],
        alternative_category=alternative,
        alternative_reason=alternative_reason,
        contributing_rule_ids=tuple(sorted(contributing)),
        rule_statuses=tuple(
            sorted((rule.rule_id, rule.status) for rule in packet.diagnostics.subject_rules)
        ),
        supported_facts=classification.supported_facts,
        not_established=_not_established(category),
        missing_evidence=classification.not_supported,
        unavailable_metric_keys=packet.unavailable_metric_keys,
        limitations=packet.limitations,
        source_recommendations=sources,
        provenance_refs=_stable_provenance_refs(packet),
    )

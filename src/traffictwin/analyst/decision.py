"""Deterministic Recommendation Agent decision over the merged chain.

Fourth stage of the bounded chain: the Analyst interprets evidence,
Next Investigation selects a bounded category, and this layer answers the
narrow decision-support question "what should the analyst investigate
next: the model/policy, the infrastructure/resource configuration, both,
nothing, or is the evidence insufficient?" — with every candidate
investigation retained alongside its deterministic eligibility or
exclusion reasons.

The decision is a pure mapping over the three already-validated inputs
(:class:`AnalystEvidencePacket`, :class:`AnalystClassification`,
:class:`RecommendationEvidencePacket`). It introduces no thresholds,
computes no metrics, and authors no advice: candidate eligibility
restates the statuses the deterministic diagnostic rules already
produced, and every "why"/"why not" line quotes existing rule outcomes
or typed identity facts. ADR-005 order is preserved: the optional LLM
(see ``decision_prose``) only explains the already-decided result.

Ranking follows the Decision Safety layer's presentation contract
(``ranked_*_ids`` plus per-option ``exclusions`` with typed reason
codes, non-executable throughout) rather than inventing a scoring
framework. Decision Safety's ``assess()`` itself is not called here
because its ``DecisionOption`` contract requires metric-valued,
policy-bound options; investigation candidates carry no primary metric
value, and fabricating one is forbidden.

Retraining is modelled as a LAST-RESORT candidate behind an explicit
typed gate. A poor outcome alone never satisfies the gate, and
infrastructure saturation alone never satisfies the gate; even a
satisfied gate yields an investigation proposal, never a claim that
retraining will help.
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
)
from traffictwin.analyst.recommendation import (
    RecommendationCategory,
    RecommendationEvidencePacket,
)

DECISION_SCHEMA_VERSION: Literal["recommendation-decision-1.0"] = "recommendation-decision-1.0"
DECISION_ENGINE_VERSION: Literal["recommendation-decision-engine-1.0"] = (
    "recommendation-decision-engine-1.0"
)

_TRIGGERED = "triggered"
_NOT_TRIGGERED = "not_triggered"
_SIDELESS_RULE_IDS: tuple[str, ...] = ("R3", "R6", "R7", "R8")

CandidateTrack = Literal["model", "infrastructure", "scenario", "none"]


class RecommendationDirection(StrEnum):
    """The bounded top-level answer vocabulary."""

    MODEL_INVESTIGATION = "MODEL_INVESTIGATION"
    INFRASTRUCTURE_INVESTIGATION = "INFRASTRUCTURE_INVESTIGATION"
    JOINT_INVESTIGATION = "JOINT_INVESTIGATION"
    NO_INTERVENTION_SIGNAL = "NO_INTERVENTION_SIGNAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


DIRECTION_DISPLAY_NAMES: dict[RecommendationDirection, str] = {
    RecommendationDirection.MODEL_INVESTIGATION: "Model/policy-side investigation",
    RecommendationDirection.INFRASTRUCTURE_INVESTIGATION: (
        "Infrastructure/resource-side investigation"
    ),
    RecommendationDirection.JOINT_INVESTIGATION: (
        "Joint model-and-infrastructure interaction investigation"
    ),
    RecommendationDirection.NO_INTERVENTION_SIGNAL: "No intervention signal",
    RecommendationDirection.INSUFFICIENT_EVIDENCE: "Insufficient evidence",
}

_DIRECTION_BY_CATEGORY: dict[RecommendationCategory, RecommendationDirection] = {
    RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING: (
        RecommendationDirection.MODEL_INVESTIGATION
    ),
    RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT: (
        RecommendationDirection.INFRASTRUCTURE_INVESTIGATION
    ),
    RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY: (
        RecommendationDirection.INFRASTRUCTURE_INVESTIGATION
    ),
    RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL: (
        RecommendationDirection.INSUFFICIENT_EVIDENCE
    ),
    RecommendationCategory.MIXED_INVESTIGATION: RecommendationDirection.JOINT_INVESTIGATION,
    RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED: (
        RecommendationDirection.NO_INTERVENTION_SIGNAL
    ),
    RecommendationCategory.INSUFFICIENT_EVIDENCE: RecommendationDirection.INSUFFICIENT_EVIDENCE,
}


class InvestigationCandidateId(StrEnum):
    """The fixed candidate-investigation roster.

    Definition order is the documented precedence order inside each
    track; R4-before-R2 restates the recorded project direction of
    examining deterministic infrastructure-side load management before
    capacity.
    """

    INVESTIGATE_RSU_LOAD_MANAGEMENT = "INVESTIGATE_RSU_LOAD_MANAGEMENT"
    INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION = "INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION"
    INSPECT_ADMISSION_OR_REJECTION_EVIDENCE = "INSPECT_ADMISSION_OR_REJECTION_EVIDENCE"
    INSPECT_POLICY_DECISION_DISTRIBUTION = "INSPECT_POLICY_DECISION_DISTRIBUTION"
    COMPARE_POLICY_WITH_BASELINES = "COMPARE_POLICY_WITH_BASELINES"
    INVESTIGATE_TRAINING_CONDITIONS = "INVESTIGATE_TRAINING_CONDITIONS"
    INVESTIGATE_RETRAINING = "INVESTIGATE_RETRAINING"
    RUN_CONTROLLED_SCENARIO_COMPARISON = "RUN_CONTROLLED_SCENARIO_COMPARISON"
    NO_INTERVENTION = "NO_INTERVENTION"


CANDIDATE_DISPLAY_NAMES: dict[InvestigationCandidateId, str] = {
    InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT: (
        "Investigate infrastructure-side RSU load management"
    ),
    InvestigationCandidateId.INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION: (
        "Investigate capacity or service provision under a controlled variation"
    ),
    InvestigationCandidateId.INSPECT_ADMISSION_OR_REJECTION_EVIDENCE: (
        "Inspect admission/rejection lifecycle evidence"
    ),
    InvestigationCandidateId.INSPECT_POLICY_DECISION_DISTRIBUTION: (
        "Inspect the policy's offloading decision distribution"
    ),
    InvestigationCandidateId.COMPARE_POLICY_WITH_BASELINES: (
        "Compare the policy against registered baseline profiles"
    ),
    InvestigationCandidateId.INVESTIGATE_TRAINING_CONDITIONS: (
        "Investigate training-to-validation conditions"
    ),
    InvestigationCandidateId.INVESTIGATE_RETRAINING: (
        "Investigate whether retraining is worth proposing (last resort)"
    ),
    InvestigationCandidateId.RUN_CONTROLLED_SCENARIO_COMPARISON: (
        "Run a controlled scenario comparison"
    ),
    InvestigationCandidateId.NO_INTERVENTION: "No change: no intervention is indicated",
}

_CANDIDATE_TRACKS: dict[InvestigationCandidateId, CandidateTrack] = {
    InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT: "infrastructure",
    InvestigationCandidateId.INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION: "infrastructure",
    InvestigationCandidateId.INSPECT_ADMISSION_OR_REJECTION_EVIDENCE: "infrastructure",
    InvestigationCandidateId.INSPECT_POLICY_DECISION_DISTRIBUTION: "model",
    InvestigationCandidateId.COMPARE_POLICY_WITH_BASELINES: "model",
    InvestigationCandidateId.INVESTIGATE_TRAINING_CONDITIONS: "model",
    InvestigationCandidateId.INVESTIGATE_RETRAINING: "model",
    InvestigationCandidateId.RUN_CONTROLLED_SCENARIO_COMPARISON: "scenario",
    InvestigationCandidateId.NO_INTERVENTION: "none",
}

_RULE_BACKED_CANDIDATES: dict[InvestigationCandidateId, str] = {
    InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT: "R4",
    InvestigationCandidateId.INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION: "R2",
    InvestigationCandidateId.INSPECT_POLICY_DECISION_DISTRIBUTION: "R1",
    InvestigationCandidateId.INVESTIGATE_TRAINING_CONDITIONS: "R5",
}

ADMISSION_EVIDENCE_SCOPE_STATEMENT = (
    "Run-bundle evidence carries no admission or rejection accounting: "
    "offered/admitted/rejected lifecycle counts exist only in admitted "
    "Resource Strategy studies (task.offered.count, task.admitted.count, "
    "task.rejected.count), which are outside the selected evidence. The "
    "Resource Strategy Explorer is the surface for that evidence, and the "
    "gate-versus-capacity rejection split is recorded there as not "
    "separately instrumented."
)

RETRAINING_PROPOSAL_NOTE = (
    "Even with every gate requirement satisfied, this remains an "
    "investigation proposal bounded to the selected evidence. It is not a "
    "claim that retraining will help, and nothing here trains, retrains, "
    "or modifies any model."
)

JOINT_ORDER_NOTE = (
    "Within a joint recommendation the two tracks are listed in fixed "
    "roster order; the ordering between tracks carries no evidential "
    "weight and neither layer is asserted to be the sole mechanism."
)


class CandidateStatus(StrEnum):
    """Typed eligibility outcome for one roster candidate."""

    RECOMMENDED = "RECOMMENDED"
    SUPPORTED_ALTERNATIVE = "SUPPORTED_ALTERNATIVE"
    ELIGIBLE_LAST_RESORT = "ELIGIBLE_LAST_RESORT"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class CandidateExclusionCode(StrEnum):
    """Typed reason codes, following the Decision Safety exclusion style."""

    RULE_NOT_TRIGGERED = "RULE_NOT_TRIGGERED"
    RULE_UNEVALUABLE = "RULE_UNEVALUABLE"
    READINESS_GATE_REFUSED = "READINESS_GATE_REFUSED"
    EVIDENCE_NOT_IN_SELECTED_SCOPE = "EVIDENCE_NOT_IN_SELECTED_SCOPE"
    MATERIAL_PROBLEM_PRESENT = "MATERIAL_PROBLEM_PRESENT"
    NO_ESTABLISHED_SIGNAL_TO_COMPARE = "NO_ESTABLISHED_SIGNAL_TO_COMPARE"
    RETRAINING_GATE_UNSATISFIED = "RETRAINING_GATE_UNSATISFIED"


class CandidateAssessment(AnalystModel):
    """One roster candidate with its complete eligibility ledger."""

    candidate_id: InvestigationCandidateId
    title: str
    track: CandidateTrack
    status: CandidateStatus
    rank: int | None = None
    evidence_support: tuple[str, ...] = ()
    exclusion_codes: tuple[CandidateExclusionCode, ...] = ()
    exclusion_reasons: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    unavailable_evidence: tuple[str, ...] = ()
    executable: Literal[False] = False
    execution_authority: Literal[False] = False


class RetrainingGateRequirement(AnalystModel):
    """One typed requirement of the retraining gate, with its evidence."""

    requirement_id: str
    description: str
    satisfied: bool
    evidence: str


class RetrainingGate(AnalystModel):
    """The strict last-resort gate for the retraining candidate."""

    satisfied: bool
    requirements: tuple[RetrainingGateRequirement, ...]
    proposal_only: Literal[True] = True
    note: str = RETRAINING_PROPOSAL_NOTE


class RecommendationDecision(AnalystModel):
    """The complete bounded decision the Recommendation Agent presents.

    Carries no wall-clock field and only rebuild-stable digests, so
    identical inputs produce byte-equivalent canonical content.
    """

    schema_version: Literal["recommendation-decision-1.0"] = DECISION_SCHEMA_VERSION
    engine_version: Literal["recommendation-decision-engine-1.0"] = DECISION_ENGINE_VERSION
    direction: RecommendationDirection
    direction_display: str
    headline: str
    statement: str
    analyst_signal: str
    underlying_category: str
    subject_kind: Literal["single_run", "comparison"]
    evidence_standing: str
    confidence: str
    confidence_basis: str
    candidates: tuple[CandidateAssessment, ...]
    ranked_candidate_ids: tuple[InvestigationCandidateId, ...]
    exclusions: tuple[tuple[str, str], ...] = ()
    next_investigation_candidate_id: InvestigationCandidateId | None = None
    retraining_gate: RetrainingGate
    supported_facts: tuple[str, ...] = ()
    not_established: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    unavailable_metric_keys: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    analyst_packet_fingerprint: str
    recommendation_fingerprint: str
    provenance_refs: tuple[str, ...] = ()
    advisory_only: Literal[True] = True
    creates_new_evidence: Literal[False] = False
    execution_authority: Literal[False] = False
    causal_claim_supported: Literal[False] = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def fingerprint(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


def _assessment(
    candidate_id: InvestigationCandidateId,
    status: CandidateStatus,
    *,
    evidence_support: tuple[str, ...] = (),
    exclusion_codes: tuple[CandidateExclusionCode, ...] = (),
    exclusion_reasons: tuple[str, ...] = (),
    required_evidence: tuple[str, ...] = (),
    unavailable_evidence: tuple[str, ...] = (),
) -> CandidateAssessment:
    return CandidateAssessment(
        candidate_id=candidate_id,
        title=CANDIDATE_DISPLAY_NAMES[candidate_id],
        track=_CANDIDATE_TRACKS[candidate_id],
        status=status,
        evidence_support=evidence_support,
        exclusion_codes=exclusion_codes,
        exclusion_reasons=exclusion_reasons,
        required_evidence=required_evidence,
        unavailable_evidence=unavailable_evidence,
    )


def _rules_by_id(packet: AnalystEvidencePacket) -> dict[str, AnalystRuleFact]:
    return {rule.rule_id: rule for rule in packet.diagnostics.subject_rules}


def _support_lines(rule: AnalystRuleFact) -> tuple[str, ...]:
    lines = [
        f"{finding.finding_id}: {finding.statement}"
        for finding in rule.findings
        if finding.support == "supports"
    ]
    lines.extend(
        f"{rule.rule_id} recommendation: {item.action} — {item.rationale} "
        f"(conditional; prerequisite: {item.prerequisite})"
        for item in rule.recommendations
    )
    return tuple(lines)


def _rule_unavailable(rule: AnalystRuleFact | None, rule_id: str) -> tuple[str, ...]:
    if rule is None:
        return (f"{rule_id}: this check is absent from the diagnostic report.",)
    return tuple(f"{rule_id}: missing evidence — {item}" for item in rule.missing_evidence) or (
        f"{rule_id}: this check could not evaluate on the selected evidence "
        f"(status: {rule.status}).",
    )


def _gate_refused(packet: AnalystEvidencePacket, rules: dict[str, AnalystRuleFact]) -> bool:
    r0 = rules.get("R0")
    return packet.diagnostics.subject_readiness == "invalid" or (
        r0 is not None and r0.status == _TRIGGERED
    )


def _triggered_ids(rules: dict[str, AnalystRuleFact], rule_ids: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        rule_id for rule_id in rule_ids if rule_id in rules and rules[rule_id].status == _TRIGGERED
    )


def _evaluated_not_triggered_ids(
    rules: dict[str, AnalystRuleFact], rule_ids: tuple[str, ...]
) -> tuple[str, ...]:
    return tuple(
        rule_id
        for rule_id in rule_ids
        if rule_id in rules and rules[rule_id].status == _NOT_TRIGGERED
    )


def _rule_backed_assessment(
    candidate_id: InvestigationCandidateId,
    rule_id: str,
    rules: dict[str, AnalystRuleFact],
    *,
    gate: bool,
) -> CandidateAssessment:
    rule = rules.get(rule_id)
    required = (f"A deterministic evaluation of {rule_id} on the selected evidence.",)
    if gate:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_EVALUABLE,
            exclusion_codes=(CandidateExclusionCode.READINESS_GATE_REFUSED,),
            exclusion_reasons=(
                "The evidence readiness gate refused diagnosis, so this "
                "candidate cannot be evaluated on the selected evidence.",
            ),
            required_evidence=required,
            unavailable_evidence=_rule_unavailable(rule, rule_id),
        )
    if rule is None or rule.status not in (_TRIGGERED, _NOT_TRIGGERED):
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_EVALUABLE,
            exclusion_codes=(CandidateExclusionCode.RULE_UNEVALUABLE,),
            exclusion_reasons=(
                f"The {rule_id} check could not evaluate on the selected "
                "evidence, so this candidate is neither supported nor "
                "excluded.",
            ),
            required_evidence=required,
            unavailable_evidence=_rule_unavailable(rule, rule_id),
        )
    if rule.status == _NOT_TRIGGERED:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_RECOMMENDED,
            exclusion_codes=(CandidateExclusionCode.RULE_NOT_TRIGGERED,),
            exclusion_reasons=(
                f"The {rule.title} check ({rule_id}) evaluated on the "
                "selected evidence and did not trigger.",
            ),
            required_evidence=required,
        )
    return _assessment(
        candidate_id,
        CandidateStatus.RECOMMENDED,
        evidence_support=_support_lines(rule),
        required_evidence=required,
    )


def _admission_assessment() -> CandidateAssessment:
    return _assessment(
        InvestigationCandidateId.INSPECT_ADMISSION_OR_REJECTION_EVIDENCE,
        CandidateStatus.NOT_EVALUABLE,
        exclusion_codes=(CandidateExclusionCode.EVIDENCE_NOT_IN_SELECTED_SCOPE,),
        exclusion_reasons=(ADMISSION_EVIDENCE_SCOPE_STATEMENT,),
        required_evidence=(
            "Admitted Resource Strategy lifecycle evidence (offered, "
            "admitted, rejected task counts with their declared "
            "denominators).",
        ),
        unavailable_evidence=(
            "task.offered.count / task.admitted.count / task.rejected.count "
            "are not part of run-bundle metric collections.",
        ),
    )


def _compare_baselines_assessment(
    rules: dict[str, AnalystRuleFact], *, gate: bool
) -> CandidateAssessment:
    candidate_id = InvestigationCandidateId.COMPARE_POLICY_WITH_BASELINES
    required = (
        "A triggered model-side check (R1 or R5), plus the registered "
        "synthetic policy profiles as compatible comparators via the "
        "existing What-If contract.",
    )
    if gate:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_EVALUABLE,
            exclusion_codes=(CandidateExclusionCode.READINESS_GATE_REFUSED,),
            exclusion_reasons=(
                "The evidence readiness gate refused diagnosis, so no "
                "model-side signal is available to compare against baselines.",
            ),
            required_evidence=required,
        )
    triggered = _triggered_ids(rules, MODEL_SIDE_RULE_IDS)
    if triggered:
        support: list[str] = []
        for rule_id in sorted(triggered):
            support.extend(_support_lines(rules[rule_id]))
        support.append(
            "Registered synthetic policy profiles provide compatible "
            "comparators through the existing What-If contract; nothing is "
            "trained or retrained."
        )
        return _assessment(
            candidate_id,
            CandidateStatus.RECOMMENDED,
            evidence_support=tuple(support),
            required_evidence=required,
        )
    evaluated = _evaluated_not_triggered_ids(rules, MODEL_SIDE_RULE_IDS)
    unavailable = tuple(
        line
        for rule_id in MODEL_SIDE_RULE_IDS
        if rule_id not in evaluated
        for line in _rule_unavailable(rules.get(rule_id), rule_id)
    )
    if evaluated:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_RECOMMENDED,
            exclusion_codes=(CandidateExclusionCode.NO_ESTABLISHED_SIGNAL_TO_COMPARE,),
            exclusion_reasons=(
                "No model-side check triggered on the selected evidence, so "
                "a baseline comparison would not be investigating an "
                "established signal.",
            ),
            required_evidence=required,
            unavailable_evidence=unavailable,
        )
    return _assessment(
        candidate_id,
        CandidateStatus.NOT_EVALUABLE,
        exclusion_codes=(CandidateExclusionCode.RULE_UNEVALUABLE,),
        exclusion_reasons=("Neither model-side check could evaluate on the selected evidence.",),
        required_evidence=required,
        unavailable_evidence=unavailable,
    )


def _scenario_assessment(rules: dict[str, AnalystRuleFact], *, gate: bool) -> CandidateAssessment:
    candidate_id = InvestigationCandidateId.RUN_CONTROLLED_SCENARIO_COMPARISON
    required = (
        "A triggered side-less material-problem candidate (R3, R6, R7 or "
        "R8) with the readiness gate passed.",
    )
    if gate:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_EVALUABLE,
            exclusion_codes=(CandidateExclusionCode.READINESS_GATE_REFUSED,),
            exclusion_reasons=(
                "The evidence readiness gate refused diagnosis, so no "
                "controlled comparison target is established.",
            ),
            required_evidence=required,
        )
    triggered = _triggered_ids(rules, _SIDELESS_RULE_IDS)
    if triggered:
        support: list[str] = []
        for rule_id in sorted(triggered):
            support.extend(_support_lines(rules[rule_id]))
        return _assessment(
            candidate_id,
            CandidateStatus.RECOMMENDED,
            evidence_support=tuple(support),
            required_evidence=required,
        )
    evaluated = _evaluated_not_triggered_ids(rules, _SIDELESS_RULE_IDS)
    unavailable = tuple(
        line
        for rule_id in _SIDELESS_RULE_IDS
        if rule_id not in evaluated
        for line in _rule_unavailable(rules.get(rule_id), rule_id)
    )
    if evaluated:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_RECOMMENDED,
            exclusion_codes=(CandidateExclusionCode.RULE_NOT_TRIGGERED,),
            exclusion_reasons=(
                "No side-less material-problem candidate triggered on the selected evidence.",
            ),
            required_evidence=required,
            unavailable_evidence=unavailable,
        )
    return _assessment(
        candidate_id,
        CandidateStatus.NOT_EVALUABLE,
        exclusion_codes=(CandidateExclusionCode.RULE_UNEVALUABLE,),
        exclusion_reasons=(
            "No side-less material-problem check could evaluate on the selected evidence.",
        ),
        required_evidence=required,
        unavailable_evidence=unavailable,
    )


def _no_intervention_assessment(
    direction: RecommendationDirection,
    rules: dict[str, AnalystRuleFact],
    *,
    gate: bool,
) -> CandidateAssessment:
    candidate_id = InvestigationCandidateId.NO_INTERVENTION
    required = ("The primary deterministic checks evaluated with none triggered.",)
    if direction is RecommendationDirection.NO_INTERVENTION_SIGNAL:
        return _assessment(
            candidate_id,
            CandidateStatus.RECOMMENDED,
            evidence_support=(
                "No deterministic diagnostic rule triggered on the selected "
                "evidence; no intervention is fabricated. This does not "
                "prove the absence of problems outside the evaluated rules' "
                "scope.",
            ),
            required_evidence=required,
        )
    triggered = sorted(rule.rule_id for rule in rules.values() if rule.status == _TRIGGERED)
    if triggered and not gate:
        return _assessment(
            candidate_id,
            CandidateStatus.NOT_RECOMMENDED,
            exclusion_codes=(CandidateExclusionCode.MATERIAL_PROBLEM_PRESENT,),
            exclusion_reasons=(
                "A material problem candidate is present (triggered: "
                f"{', '.join(triggered)}), so 'no change' is not the "
                "supported reading of this evidence.",
            ),
            required_evidence=required,
        )
    return _assessment(
        candidate_id,
        CandidateStatus.NOT_EVALUABLE,
        exclusion_codes=(CandidateExclusionCode.READINESS_GATE_REFUSED,),
        exclusion_reasons=(
            "The evidence is insufficient to assert that nothing needs "
            "attention; 'no change' also requires evidence.",
        ),
        required_evidence=required,
    )


def _changed_paths(packet: AnalystEvidencePacket, prefix: str) -> tuple[str, ...]:
    paths: list[str] = []
    for entry in packet.changed_parameters:
        path = str(entry.get("path", ""))
        if path == prefix or path.startswith(f"{prefix}."):
            paths.append(path)
    return tuple(sorted(paths))


def evaluate_retraining_gate(packet: AnalystEvidencePacket) -> RetrainingGate:
    """Evaluate the strict, typed last-resort gate for retraining.

    Every requirement restates existing typed facts (rule statuses,
    comparison compatibility, changed seed-parameter paths, evidence
    standing); nothing is measured or estimated here.
    """

    rules = _rules_by_id(packet)
    gate = _gate_refused(packet, rules)
    model_triggered = sorted(_triggered_ids(rules, MODEL_SIDE_RULE_IDS))
    infra_statuses = {
        rule_id: (rules[rule_id].status if rule_id in rules else "absent")
        for rule_id in INFRASTRUCTURE_SIDE_RULE_IDS
    }
    infra_triggered = sorted(
        rule_id for rule_id, status in infra_statuses.items() if status == _TRIGGERED
    )
    infra_excluded = all(status == _NOT_TRIGGERED for status in infra_statuses.values())
    policy_paths = _changed_paths(packet, "policy")
    confound_paths = tuple(
        sorted(
            str(entry.get("path", ""))
            for entry in packet.changed_parameters
            if not (
                str(entry.get("path", "")) == "policy"
                or str(entry.get("path", "")).startswith("policy.")
            )
        )
    )
    identity = packet.identity
    is_compatible_comparison = (
        identity.subject_kind == "comparison" and identity.comparison_compatible is True
    )
    standings = [identity.baseline_standing]
    if identity.subject_kind == "comparison":
        standings.append(identity.variation_standing or "UNKNOWN")
    standing_known = all(standing != "UNKNOWN" for standing in standings)

    if infra_triggered:
        infra_evidence = (
            "Infrastructure-side checks triggered "
            f"({', '.join(infra_triggered)}): infrastructure pressure "
            "provides a supported alternative explanation."
        )
    elif infra_excluded:
        infra_evidence = "Both infrastructure-side checks (R2, R4) evaluated and did not trigger."
    else:
        infra_evidence = (
            "An infrastructure-side check could not evaluate "
            f"({', '.join(f'{key}:{value}' for key, value in sorted(infra_statuses.items()))}), "
            "so an infrastructure-side explanation cannot be excluded."
        )

    if policy_paths and is_compatible_comparison:
        comparator_evidence = (
            "A compatible comparison in which the policy identity differs "
            f"is selected (changed: {', '.join(policy_paths)}); the changed "
            "entries name both actor identities."
        )
    elif not is_compatible_comparison:
        comparator_evidence = (
            "The selected evidence is not a compatible comparison, so no "
            "policy comparator establishes that the actor is the "
            "distinguishing factor."
        )
    else:
        comparator_evidence = (
            "The selected compatible comparison does not vary any policy "
            "identity parameter, so it cannot attribute the outcome to the "
            "actor."
        )

    requirements = (
        RetrainingGateRequirement(
            requirement_id="readiness_gate_passed",
            description=(
                "The evidence readiness gate (R0 and overall readiness) did not refuse diagnosis."
            ),
            satisfied=not gate,
            evidence=(
                "The readiness gate passed on the selected evidence."
                if not gate
                else "The readiness gate refused diagnosis, so no "
                "retraining-supporting interpretation exists."
            ),
        ),
        RetrainingGateRequirement(
            requirement_id="model_side_behaviour_implicated",
            description=(
                "A deterministic model-side check (R1 or R5) triggered on the selected evidence."
            ),
            satisfied=bool(model_triggered),
            evidence=(
                f"Triggered model-side checks: {', '.join(model_triggered)}."
                if model_triggered
                else "Neither model-side check (R1, R5) triggered; a poor "
                "outcome alone never implicates the model."
            ),
        ),
        RetrainingGateRequirement(
            requirement_id="infrastructure_explanation_excluded",
            description=(
                "Both infrastructure-side checks (R2, R4) evaluated and did "
                "not trigger, so infrastructure alone does not provide a "
                "supported alternative explanation."
            ),
            satisfied=infra_excluded,
            evidence=infra_evidence,
        ),
        RetrainingGateRequirement(
            requirement_id="compatible_policy_comparator_present",
            description=(
                "A compatible comparison exists in which the policy/actor "
                "identity (a policy.* parameter) is a changed parameter, so "
                "the actor identities are known and distinguishable."
            ),
            satisfied=bool(policy_paths) and is_compatible_comparison,
            evidence=comparator_evidence,
        ),
        RetrainingGateRequirement(
            requirement_id="policy_identity_isolated",
            description=(
                "The policy identity is the only changed parameter between "
                "the compared arms: infrastructure, scenario, workload and "
                "demand are the same, so the comparison is not confounded."
            ),
            satisfied=is_compatible_comparison and bool(policy_paths) and not confound_paths,
            evidence=(
                "Only policy identity parameters differ between the arms."
                if is_compatible_comparison and bool(policy_paths) and not confound_paths
                else (
                    "Non-policy parameters also differ between the arms "
                    f"({', '.join(confound_paths)}), so the outcome cannot "
                    "be attributed to the policy identity alone."
                    if confound_paths
                    else "There is no compatible comparison isolating the policy identity."
                )
            ),
        ),
        RetrainingGateRequirement(
            requirement_id="evidence_standing_known",
            description="The standing of every selected bundle is known.",
            satisfied=standing_known,
            evidence=f"Evidence standing: {', '.join(standings)}.",
        ),
    )
    return RetrainingGate(
        satisfied=all(item.satisfied for item in requirements),
        requirements=requirements,
    )


def _retraining_assessment(gate_result: RetrainingGate) -> CandidateAssessment:
    candidate_id = InvestigationCandidateId.INVESTIGATE_RETRAINING
    required = tuple(item.description for item in gate_result.requirements)
    if gate_result.satisfied:
        return _assessment(
            candidate_id,
            CandidateStatus.ELIGIBLE_LAST_RESORT,
            evidence_support=(
                *(item.evidence for item in gate_result.requirements),
                RETRAINING_PROPOSAL_NOTE,
            ),
            required_evidence=required,
        )
    unsatisfied = tuple(item for item in gate_result.requirements if not item.satisfied)
    return _assessment(
        candidate_id,
        CandidateStatus.NOT_RECOMMENDED,
        exclusion_codes=(CandidateExclusionCode.RETRAINING_GATE_UNSATISFIED,),
        exclusion_reasons=tuple(item.evidence for item in unsatisfied),
        required_evidence=required,
        unavailable_evidence=tuple(item.description for item in unsatisfied),
    )


_ELIGIBLE_STATUSES = (
    CandidateStatus.RECOMMENDED,
    CandidateStatus.SUPPORTED_ALTERNATIVE,
    CandidateStatus.ELIGIBLE_LAST_RESORT,
)

_PRIMARY_TRACKS_BY_CATEGORY: dict[RecommendationCategory, tuple[str, ...]] = {
    RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING: ("model",),
    RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT: ("infrastructure",),
    RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY: ("infrastructure",),
    RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL: ("scenario",),
    RecommendationCategory.MIXED_INVESTIGATION: ("infrastructure", "model"),
    RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED: ("none",),
    RecommendationCategory.INSUFFICIENT_EVIDENCE: (),
}


def _rank_candidates(
    assessments: dict[InvestigationCandidateId, CandidateAssessment],
    category: RecommendationCategory,
) -> tuple[CandidateAssessment, ...]:
    """Assign ranks deterministically.

    Primary-track eligible candidates come first in roster order, then
    other eligible tracks in roster order, and the retraining candidate
    is always last. Input order cannot influence the result because the
    roster enum order is fixed and eligibility is per-candidate.
    """

    primary_tracks = _PRIMARY_TRACKS_BY_CATEGORY[category]
    eligible = [
        candidate_id
        for candidate_id in InvestigationCandidateId
        if assessments[candidate_id].status in _ELIGIBLE_STATUSES
    ]
    retraining = InvestigationCandidateId.INVESTIGATE_RETRAINING
    ordered = (
        [
            candidate_id
            for candidate_id in eligible
            if candidate_id is not retraining and assessments[candidate_id].track in primary_tracks
        ]
        + [
            candidate_id
            for candidate_id in eligible
            if candidate_id is not retraining
            and assessments[candidate_id].track not in primary_tracks
        ]
        + [candidate_id for candidate_id in eligible if candidate_id is retraining]
    )
    ranked: dict[InvestigationCandidateId, CandidateAssessment] = {}
    for position, candidate_id in enumerate(ordered, start=1):
        assessment = assessments[candidate_id]
        status = assessment.status
        if status is not CandidateStatus.ELIGIBLE_LAST_RESORT:
            status = (
                CandidateStatus.RECOMMENDED
                if position == 1
                else CandidateStatus.SUPPORTED_ALTERNATIVE
            )
        ranked[candidate_id] = assessment.model_copy(update={"rank": position, "status": status})
    return tuple(
        ranked.get(candidate_id, assessments[candidate_id])
        for candidate_id in InvestigationCandidateId
    )


def decide_recommendation(
    packet: AnalystEvidencePacket,
    classification: AnalystClassification,
    recommendation: RecommendationEvidencePacket,
) -> RecommendationDecision:
    """Deterministically derive the bounded Recommendation Agent decision.

    All three inputs must belong to the same chain; a mismatched pairing
    is a typed refusal, never a silent re-derivation.
    """

    packet_fingerprint = packet.fingerprint()
    if classification.packet_fingerprint != packet_fingerprint:
        raise AnalystRefusalError(
            AnalystRefusalCode.PROVENANCE_INCOMPLETE,
            "The classification does not belong to the supplied Analyst "
            "packet, so no decision is derivable from this pairing.",
        )
    if recommendation.analyst_packet_fingerprint != packet_fingerprint:
        raise AnalystRefusalError(
            AnalystRefusalCode.PROVENANCE_INCOMPLETE,
            "The recommendation does not belong to the supplied Analyst "
            "packet, so no decision is derivable from this pairing.",
        )

    rules = _rules_by_id(packet)
    gate = _gate_refused(packet, rules)
    category = RecommendationCategory(recommendation.category)
    direction = _DIRECTION_BY_CATEGORY[category]
    gate_result = evaluate_retraining_gate(packet)

    assessments: dict[InvestigationCandidateId, CandidateAssessment] = {}
    for candidate_id, rule_id in _RULE_BACKED_CANDIDATES.items():
        assessments[candidate_id] = _rule_backed_assessment(candidate_id, rule_id, rules, gate=gate)
    assessments[InvestigationCandidateId.INSPECT_ADMISSION_OR_REJECTION_EVIDENCE] = (
        _admission_assessment()
    )
    assessments[InvestigationCandidateId.COMPARE_POLICY_WITH_BASELINES] = (
        _compare_baselines_assessment(rules, gate=gate)
    )
    assessments[InvestigationCandidateId.RUN_CONTROLLED_SCENARIO_COMPARISON] = _scenario_assessment(
        rules, gate=gate
    )
    assessments[InvestigationCandidateId.NO_INTERVENTION] = _no_intervention_assessment(
        direction, rules, gate=gate
    )
    assessments[InvestigationCandidateId.INVESTIGATE_RETRAINING] = _retraining_assessment(
        gate_result
    )

    candidates = _rank_candidates(assessments, category)
    ranked_ids = tuple(
        item.candidate_id
        for item in sorted(
            (item for item in candidates if item.rank is not None),
            key=lambda item: item.rank or 0,
        )
    )
    exclusions = tuple(
        sorted(
            (item.candidate_id.value, code.value)
            for item in candidates
            if item.rank is None
            for code in item.exclusion_codes
        )
    )

    limitations = list(recommendation.limitations)
    if category is RecommendationCategory.MIXED_INVESTIGATION:
        limitations.append(JOINT_ORDER_NOTE)

    return RecommendationDecision(
        direction=direction,
        direction_display=DIRECTION_DISPLAY_NAMES[direction],
        headline=recommendation.headline,
        statement=recommendation.rationale,
        analyst_signal=recommendation.analyst_signal,
        underlying_category=category.value,
        subject_kind=recommendation.subject_kind,
        evidence_standing=recommendation.evidence_standing,
        confidence=recommendation.confidence,
        confidence_basis=recommendation.confidence_basis,
        candidates=candidates,
        ranked_candidate_ids=ranked_ids,
        exclusions=exclusions,
        next_investigation_candidate_id=(ranked_ids[0] if ranked_ids else None),
        retraining_gate=gate_result,
        supported_facts=recommendation.supported_facts,
        not_established=recommendation.not_established,
        missing_evidence=recommendation.missing_evidence,
        unavailable_metric_keys=recommendation.unavailable_metric_keys,
        limitations=tuple(limitations),
        analyst_packet_fingerprint=packet_fingerprint,
        recommendation_fingerprint=recommendation.fingerprint(),
        provenance_refs=(
            *recommendation.provenance_refs,
            f"recommendation_packet:{recommendation.fingerprint()[:16]}",
        ),
    )

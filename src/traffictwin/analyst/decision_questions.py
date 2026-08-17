"""Bounded analyst questions over an already-decided recommendation.

This is deliberately not a chatbot. A fixed roster of analyst questions
maps deterministically onto typed queries over the
:class:`RecommendationDecision`; every answer quotes fields the decision
already carries, and an unrecognised question is a typed refusal that
lists the supported questions instead of guessing. Free text never
reaches an LLM from here.
"""

from __future__ import annotations

from enum import StrEnum

from traffictwin.analyst.decision import (
    CANDIDATE_DISPLAY_NAMES,
    CandidateAssessment,
    CandidateStatus,
    InvestigationCandidateId,
    RecommendationDecision,
    RecommendationDirection,
)
from traffictwin.analyst.models import AnalystModel

ANSWER_BOUNDARY_STATEMENT = (
    "Advisory only: this answer is bounded to the selected evidence, "
    "makes no causal claim, and carries no execution authority."
)


class BoundedQuestionId(StrEnum):
    """The fixed question roster."""

    WHAT_NEXT = "WHAT_NEXT"
    SHOULD_I_RETRAIN = "SHOULD_I_RETRAIN"
    WHY_NOT_RETRAIN = "WHY_NOT_RETRAIN"
    IS_INFRASTRUCTURE_PROBLEM = "IS_INFRASTRUCTURE_PROBLEM"
    IS_MODEL_PROBLEM = "IS_MODEL_PROBLEM"
    IS_REDISTRIBUTION_WORTH_TESTING = "IS_REDISTRIBUTION_WORTH_TESTING"
    WHAT_EVIDENCE_IS_MISSING = "WHAT_EVIDENCE_IS_MISSING"
    WHY_NOT_CANDIDATE = "WHY_NOT_CANDIDATE"


BOUNDED_QUESTIONS: dict[BoundedQuestionId, str] = {
    BoundedQuestionId.WHAT_NEXT: "What should I investigate next?",
    BoundedQuestionId.SHOULD_I_RETRAIN: "Should I retrain the model?",
    BoundedQuestionId.WHY_NOT_RETRAIN: "Why aren't you recommending retraining?",
    BoundedQuestionId.IS_INFRASTRUCTURE_PROBLEM: "Does this look like an infrastructure problem?",
    BoundedQuestionId.IS_MODEL_PROBLEM: "Does this look like a model/policy problem?",
    BoundedQuestionId.IS_REDISTRIBUTION_WORTH_TESTING: (
        "Would load redistribution be worth testing?"
    ),
    BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING: "What evidence is missing before we decide?",
}


class UnrecognisedQuestionError(RuntimeError):
    """Typed refusal: the question is outside the bounded roster."""

    def __init__(self, text: str) -> None:
        supported = "; ".join(BOUNDED_QUESTIONS.values())
        super().__init__(
            "UNRECOGNISED_QUESTION: TrafficTwin only answers the bounded "
            f"recommendation questions ({supported}). The question "
            f"{text!r} was not mapped to any of them, and nothing is guessed."
        )
        self.supported_questions = tuple(BOUNDED_QUESTIONS.values())


class BoundedAnswer(AnalystModel):
    """One deterministic answer, quoting only decision fields."""

    question_id: BoundedQuestionId
    question: str
    answer: str
    supporting_lines: tuple[str, ...] = ()
    decision_fingerprint: str
    boundary: str = ANSWER_BOUNDARY_STATEMENT
    llm_output: bool = False


# Ordered, first-match-wins keyword patterns. Every term set is checked
# against the lowercased question; a pattern matches when all of its
# required groups are present (any term within a group suffices).
_QUESTION_PATTERNS: tuple[tuple[BoundedQuestionId, tuple[tuple[str, ...], ...]], ...] = (
    (BoundedQuestionId.WHY_NOT_RETRAIN, (("why",), ("retrain", "retraining"))),
    (BoundedQuestionId.SHOULD_I_RETRAIN, (("retrain", "retraining"),)),
    (
        BoundedQuestionId.IS_REDISTRIBUTION_WORTH_TESTING,
        (("redistribution", "redistribute", "rebalanc", "load management", "load-management"),),
    ),
    (
        BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING,
        (("missing", "before we decide", "what evidence"),),
    ),
    (
        BoundedQuestionId.IS_INFRASTRUCTURE_PROBLEM,
        (("infrastructure", "rsu", "capacity"), ("problem", "look like", "issue", "cause")),
    ),
    (
        BoundedQuestionId.IS_MODEL_PROBLEM,
        (("model", "policy", "actor"), ("problem", "look like", "issue", "cause")),
    ),
    (
        BoundedQuestionId.WHAT_NEXT,
        (("next", "investigate", "what should"),),
    ),
)


def match_question(text: str) -> BoundedQuestionId | None:
    """Deterministically map free text onto the bounded roster, or None."""

    lowered = text.strip().lower()
    if not lowered:
        return None
    for question_id, groups in _QUESTION_PATTERNS:
        if all(any(term in lowered for term in group) for group in groups):
            return question_id
    return None


def _candidate(
    decision: RecommendationDecision, candidate_id: InvestigationCandidateId
) -> CandidateAssessment:
    for item in decision.candidates:
        if item.candidate_id is candidate_id:
            return item
    raise UnrecognisedQuestionError(candidate_id.value)


def answer_why_not(
    decision: RecommendationDecision, candidate_id: InvestigationCandidateId
) -> BoundedAnswer:
    """The deterministic exclusion ledger for one roster candidate."""

    item = _candidate(decision, candidate_id)
    title = CANDIDATE_DISPLAY_NAMES[candidate_id]
    if item.rank is not None:
        answer = f"{title} is not excluded: it is ranked #{item.rank} ({item.status.value})."
        supporting = item.evidence_support
    else:
        answer = f"{title} — status: {item.status.value}."
        supporting = (
            *item.exclusion_reasons,
            *(f"Required evidence: {line}" for line in item.required_evidence),
            *(f"Unavailable: {line}" for line in item.unavailable_evidence),
        )
    return BoundedAnswer(
        question_id=BoundedQuestionId.WHY_NOT_RETRAIN
        if candidate_id is InvestigationCandidateId.INVESTIGATE_RETRAINING
        else BoundedQuestionId.WHY_NOT_CANDIDATE,
        question=f"Why not: {title}?",
        answer=answer,
        supporting_lines=supporting,
        decision_fingerprint=decision.fingerprint(),
    )


def _answer_what_next(decision: RecommendationDecision) -> tuple[str, tuple[str, ...]]:
    if decision.next_investigation_candidate_id is None:
        return (
            f"{decision.headline} {decision.statement}",
            (*decision.missing_evidence,),
        )
    top = _candidate(decision, decision.next_investigation_candidate_id)
    return (
        f"{decision.direction_display}: {top.title}. {decision.statement}",
        (*decision.supported_facts,),
    )


def _answer_should_retrain(decision: RecommendationDecision) -> tuple[str, tuple[str, ...]]:
    item = _candidate(decision, InvestigationCandidateId.INVESTIGATE_RETRAINING)
    if item.status is CandidateStatus.ELIGIBLE_LAST_RESORT:
        return (
            "The strict retraining gate is satisfied on this evidence, but "
            "retraining stays a last-resort investigation proposal ranked "
            f"#{item.rank}: it is a proposal to investigate, not a claim "
            "that retraining will help.",
            item.evidence_support,
        )
    return (
        "Not on the current evidence: the strict retraining gate is not "
        "satisfied, so TrafficTwin does not recommend investigating "
        "retraining yet.",
        item.exclusion_reasons,
    )


def _answer_why_not_retrain(decision: RecommendationDecision) -> tuple[str, tuple[str, ...]]:
    gate = decision.retraining_gate
    if gate.satisfied:
        return (
            "Retraining is not excluded on this evidence: every gate "
            "requirement is satisfied. It is still ranked last because it "
            "remains an investigation proposal, never a first step.",
            (*(item.evidence for item in gate.requirements), gate.note),
        )
    unsatisfied = tuple(item for item in gate.requirements if not item.satisfied)
    return (
        "The strict retraining gate is not satisfied. Unsatisfied "
        f"requirements: {len(unsatisfied)} of {len(gate.requirements)}.",
        tuple(f"{item.requirement_id}: {item.evidence}" for item in unsatisfied),
    )


def _side_answer(
    decision: RecommendationDecision, track: str, side_display: str
) -> tuple[str, tuple[str, ...]]:
    side_candidates = tuple(item for item in decision.candidates if item.track == track)
    ranked = tuple(item for item in side_candidates if item.rank is not None)
    joint = decision.direction is RecommendationDirection.JOINT_INVESTIGATION
    if ranked:
        prefix = (
            f"The current evidence supports a {side_display} investigation"
            + (" as part of a joint investigation" if joint else "")
            + ": "
        )
        answer = prefix + "; ".join(f"#{item.rank} {item.title}" for item in ranked) + "."
        supporting = tuple(line for item in ranked for line in item.evidence_support)
    else:
        answer = (
            f"The current evidence does not establish a {side_display} "
            "problem: no candidate on that side is eligible."
        )
        supporting = tuple(
            f"{item.title}: {reason}"
            for item in side_candidates
            for reason in item.exclusion_reasons
        )
    return answer, supporting


def _answer_redistribution(decision: RecommendationDecision) -> tuple[str, tuple[str, ...]]:
    item = _candidate(decision, InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT)
    if item.rank is not None:
        return (
            f"Yes, on this evidence it is ranked #{item.rank}: {item.title}.",
            item.evidence_support,
        )
    return (
        f"Not on this evidence — status: {item.status.value}.",
        item.exclusion_reasons,
    )


def _answer_missing(decision: RecommendationDecision) -> tuple[str, tuple[str, ...]]:
    lines: list[str] = list(decision.missing_evidence)
    lines.extend(f"Unavailable metric: {key}" for key in decision.unavailable_metric_keys)
    for item in decision.candidates:
        if item.status is CandidateStatus.NOT_EVALUABLE:
            lines.extend(f"{item.title}: {line}" for line in item.unavailable_evidence)
    if not lines:
        return (
            "No missing evidence was recorded for this selection; the "
            "decision above is bounded to the evaluated rules' scope.",
            (),
        )
    return (
        "The following evidence is missing or unavailable for this "
        "selection; nothing was estimated in its place.",
        tuple(lines),
    )


def answer_question(
    decision: RecommendationDecision, question_id: BoundedQuestionId
) -> BoundedAnswer:
    """Answer one bounded question deterministically from the decision."""

    if question_id is BoundedQuestionId.WHAT_NEXT:
        answer, supporting = _answer_what_next(decision)
    elif question_id is BoundedQuestionId.SHOULD_I_RETRAIN:
        answer, supporting = _answer_should_retrain(decision)
    elif question_id is BoundedQuestionId.WHY_NOT_RETRAIN:
        answer, supporting = _answer_why_not_retrain(decision)
    elif question_id is BoundedQuestionId.IS_INFRASTRUCTURE_PROBLEM:
        answer, supporting = _side_answer(decision, "infrastructure", "infrastructure-side")
    elif question_id is BoundedQuestionId.IS_MODEL_PROBLEM:
        answer, supporting = _side_answer(decision, "model", "model/policy-side")
    elif question_id is BoundedQuestionId.IS_REDISTRIBUTION_WORTH_TESTING:
        answer, supporting = _answer_redistribution(decision)
    elif question_id is BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING:
        answer, supporting = _answer_missing(decision)
    else:
        raise UnrecognisedQuestionError(question_id.value)
    return BoundedAnswer(
        question_id=question_id,
        question=BOUNDED_QUESTIONS[question_id],
        answer=answer,
        supporting_lines=supporting,
        decision_fingerprint=decision.fingerprint(),
    )


def answer_free_text(decision: RecommendationDecision, text: str) -> BoundedAnswer:
    """Map free text to a bounded question and answer it, or refuse."""

    question_id = match_question(text)
    if question_id is None:
        raise UnrecognisedQuestionError(text)
    return answer_question(decision, question_id)

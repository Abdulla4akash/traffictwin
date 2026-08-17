"""Bounded questions map deterministically and refuse the unrecognised."""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.analyst import (
    BoundedQuestionId,
    InvestigationCandidateId,
    RecommendationDecision,
    UnrecognisedQuestionError,
    answer_free_text,
    answer_question,
    answer_why_not,
    build_analyst_packet,
    classify_packet,
    decide_recommendation,
    match_question,
    select_recommendation,
)
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.services.bundles import validate_bundle_for_ui


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("decision-questions") / "demo"
    initialise_workspace(workspace)
    return workspace


def _decision(workspace: Path, variation: str | None) -> RecommendationDecision:
    baseline = validate_bundle_for_ui(workspace / "bundles" / "baseline")
    packet = build_analyst_packet(
        baseline,
        validate_bundle_for_ui(workspace / "bundles" / variation) if variation else None,
    )
    classification = classify_packet(packet)
    recommendation = select_recommendation(packet, classification)
    return decide_recommendation(packet, classification, recommendation)


class TestMatching:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("What should I investigate next?", BoundedQuestionId.WHAT_NEXT),
            ("Should we retrain MAPPO?", BoundedQuestionId.SHOULD_I_RETRAIN),
            ("Should I retrain the model?", BoundedQuestionId.SHOULD_I_RETRAIN),
            (
                "Why aren't you recommending retraining?",
                BoundedQuestionId.WHY_NOT_RETRAIN,
            ),
            (
                "Does this look like an infrastructure problem?",
                BoundedQuestionId.IS_INFRASTRUCTURE_PROBLEM,
            ),
            (
                "Is this a policy problem rather than anything else?",
                BoundedQuestionId.IS_MODEL_PROBLEM,
            ),
            (
                "Would load redistribution be worth testing?",
                BoundedQuestionId.IS_REDISTRIBUTION_WORTH_TESTING,
            ),
            (
                "What evidence is missing before we decide?",
                BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING,
            ),
        ],
    )
    def test_known_phrasings_map_deterministically(
        self, text: str, expected: BoundedQuestionId
    ) -> None:
        assert match_question(text) is expected

    def test_unrelated_text_maps_to_nothing(self) -> None:
        assert match_question("please deploy this to kubernetes") is None
        assert match_question("") is None

    def test_unrecognised_free_text_is_a_typed_refusal(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, None)
        with pytest.raises(UnrecognisedQuestionError) as error:
            answer_free_text(decision, "please deploy this to kubernetes")
        assert "UNRECOGNISED_QUESTION" in str(error.value)
        assert error.value.supported_questions


class TestAnswers:
    def test_should_retrain_answers_no_on_saturation(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "infrastructure_bottleneck")
        answer = answer_question(decision, BoundedQuestionId.SHOULD_I_RETRAIN)
        assert "Not on the current evidence" in answer.answer
        assert answer.llm_output is False
        assert answer.decision_fingerprint == decision.fingerprint()

    def test_why_not_retrain_quotes_the_gate(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "infrastructure_bottleneck")
        answer = answer_question(decision, BoundedQuestionId.WHY_NOT_RETRAIN)
        assert "not satisfied" in answer.answer
        assert any(
            "infrastructure_explanation_excluded" in line for line in answer.supporting_lines
        )

    def test_infrastructure_question_reflects_the_direction(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "infrastructure_bottleneck")
        answer = answer_question(decision, BoundedQuestionId.IS_INFRASTRUCTURE_PROBLEM)
        assert "supports a" in answer.answer
        negative = answer_question(decision, BoundedQuestionId.IS_MODEL_PROBLEM)
        assert "does not establish" in negative.answer

    def test_redistribution_answer_uses_the_candidate_ledger(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "infrastructure_bottleneck")
        answer = answer_question(decision, BoundedQuestionId.IS_REDISTRIBUTION_WORTH_TESTING)
        assert "Not on this evidence" in answer.answer
        assert answer.supporting_lines

    def test_missing_evidence_answer_collects_the_gaps(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "under_offloading")
        answer = answer_question(decision, BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING)
        assert answer.supporting_lines
        assert any("R5" in line for line in answer.supporting_lines)

    def test_what_next_names_the_top_candidate(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "under_offloading")
        answer = answer_question(decision, BoundedQuestionId.WHAT_NEXT)
        assert "offloading decision distribution" in answer.answer

    def test_why_not_covers_every_candidate(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, "infrastructure_bottleneck")
        for candidate_id in InvestigationCandidateId:
            answer = answer_why_not(decision, candidate_id)
            assert answer.answer
        ranked = answer_why_not(
            decision, InvestigationCandidateId.INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION
        )
        assert "not excluded" in ranked.answer

    def test_the_generic_why_not_id_is_not_directly_answerable(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, None)
        with pytest.raises(UnrecognisedQuestionError):
            answer_question(decision, BoundedQuestionId.WHY_NOT_CANDIDATE)

    def test_every_answer_carries_the_advisory_boundary(self, demo_workspace: Path) -> None:
        decision = _decision(demo_workspace, None)
        for question_id in (
            BoundedQuestionId.WHAT_NEXT,
            BoundedQuestionId.SHOULD_I_RETRAIN,
            BoundedQuestionId.WHAT_EVIDENCE_IS_MISSING,
        ):
            answer = answer_question(decision, question_id)
            assert "no execution authority" in answer.boundary

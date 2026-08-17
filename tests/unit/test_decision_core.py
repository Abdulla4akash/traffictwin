"""The Recommendation Agent decision engine is deterministic and fail-closed."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pytest

from traffictwin.analyst import (
    AnalystRefusalError,
    CandidateStatus,
    ChallengeReadiness,
    InvestigationCandidateId,
    RecommendationDecision,
    RecommendationDirection,
    build_analyst_packet,
    build_challenge_prefill,
    classify_packet,
    decide_recommendation,
    evaluate_retraining_gate,
    plan_challenge,
    select_recommendation,
)
from traffictwin.analyst.challenge import ChallengeTrack
from traffictwin.analyst.decision import (
    ADMISSION_EVIDENCE_SCOPE_STATEMENT,
    JOINT_ORDER_NOTE,
    CandidateExclusionCode,
)
from traffictwin.analyst.models import (
    AnalystDiagnostics,
    AnalystEvidencePacket,
    AnalystIdentity,
    AnalystProvenance,
    AnalystRecommendationFact,
    AnalystRuleFact,
    JsonScalar,
)
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("decision") / "demo"
    initialise_workspace(workspace)
    return workspace


def _analysis(workspace: Path, name: str) -> BundleAnalysis:
    return validate_bundle_for_ui(workspace / "bundles" / name)


def _fixture_packet(
    rules: dict[str, tuple[str, str]],
    *,
    subject_kind: Literal["single_run", "comparison"] = "single_run",
    changed_paths: tuple[str, ...] = (),
    comparison_compatible: bool | None = None,
    baseline_standing: Literal["SYNTHETIC", "IMPORTED", "UNKNOWN"] = "SYNTHETIC",
    variation_standing: Literal["SYNTHETIC", "IMPORTED", "UNKNOWN"] | None = None,
    readiness: str = "partially_ready",
) -> AnalystEvidencePacket:
    changed: tuple[dict[str, JsonScalar], ...] = tuple(
        {"path": path, "baseline": "a", "variation": "b"} for path in changed_paths
    )
    return AnalystEvidencePacket(
        identity=AnalystIdentity(
            subject_kind=subject_kind,
            baseline_standing=baseline_standing,
            variation_standing=variation_standing,
            comparison_compatible=comparison_compatible,
        ),
        changed_parameters=changed,
        diagnostics=AnalystDiagnostics(
            subject_side="variation" if subject_kind == "comparison" else "single_run",
            subject_readiness=readiness,
            subject_ruleset_version="1.3",
            subject_rules=tuple(
                AnalystRuleFact(
                    rule_id=rule_id,
                    title=f"{rule_id} fixture",
                    status=status,
                    confidence=confidence,
                    recommendations=(
                        (
                            AnalystRecommendationFact(
                                action=f"{rule_id} fixture action",
                                rationale=f"{rule_id} fixture rationale",
                                expected_direction="fixture direction",
                                prerequisite="fixture prerequisite",
                                verification_step="fixture verification",
                            ),
                        )
                        if status == "triggered"
                        else ()
                    ),
                )
                for rule_id, (status, confidence) in rules.items()
            ),
        ),
        provenance=AnalystProvenance(),
    )


def _decide(packet: AnalystEvidencePacket) -> RecommendationDecision:
    classification = classify_packet(packet)
    recommendation = select_recommendation(packet, classification)
    return decide_recommendation(packet, classification, recommendation)


_EVALUATED_QUIET = {
    "R0": ("not_triggered", "unavailable"),
    "R1": ("not_triggered", "unavailable"),
    "R2": ("not_triggered", "unavailable"),
    "R4": ("not_triggered", "unavailable"),
}


class TestDirections:
    def test_infrastructure_imbalance_recommends_load_management_first(self) -> None:
        packet = _fixture_packet({**_EVALUATED_QUIET, "R4": ("triggered", "moderate")})
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.INFRASTRUCTURE_INVESTIGATION
        assert decision.ranked_candidate_ids[0] is (
            InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT
        )
        top = decision.candidates[0]
        assert top.candidate_id is InvestigationCandidateId.INVESTIGATE_RSU_LOAD_MANAGEMENT
        assert top.status is CandidateStatus.RECOMMENDED
        assert top.evidence_support, "the winner must quote R4's own evidence"

    def test_demo_infrastructure_case_recommends_capacity(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.INFRASTRUCTURE_INVESTIGATION
        assert decision.next_investigation_candidate_id is (
            InvestigationCandidateId.INVESTIGATE_CAPACITY_OR_SERVICE_PROVISION
        )

    def test_demo_model_case_recommends_policy_inspection_first(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.MODEL_INVESTIGATION
        assert decision.ranked_candidate_ids[0] is (
            InvestigationCandidateId.INSPECT_POLICY_DECISION_DISTRIBUTION
        )
        assert (
            InvestigationCandidateId.COMPARE_POLICY_WITH_BASELINES in decision.ranked_candidate_ids
        )

    def test_mixed_evidence_becomes_a_joint_investigation(self) -> None:
        packet = _fixture_packet(
            {
                **_EVALUATED_QUIET,
                "R1": ("triggered", "moderate"),
                "R2": ("triggered", "high"),
            }
        )
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.JOINT_INVESTIGATION
        ranked_tracks = {item.track for item in decision.candidates if item.rank is not None}
        assert {"model", "infrastructure"} <= ranked_tracks
        assert JOINT_ORDER_NOTE in decision.limitations

    def test_no_material_problem_recommends_no_intervention(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.NO_INTERVENTION_SIGNAL
        assert decision.ranked_candidate_ids == (InvestigationCandidateId.NO_INTERVENTION,)

    def test_unevaluable_side_rules_yield_insufficient_with_nothing_ranked(self) -> None:
        packet = _fixture_packet({"R0": ("not_triggered", "unavailable")})
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.INSUFFICIENT_EVIDENCE
        assert decision.ranked_candidate_ids == ()
        assert decision.next_investigation_candidate_id is None

    def test_sideless_candidate_maps_to_a_controlled_comparison(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        decision = _decide(packet)
        assert decision.direction is RecommendationDirection.INSUFFICIENT_EVIDENCE
        assert decision.ranked_candidate_ids[0] is (
            InvestigationCandidateId.RUN_CONTROLLED_SCENARIO_COMPARISON
        )


class TestRetrainingGate:
    def test_poor_outcome_alone_does_not_trigger_retraining(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        decision = _decide(packet)
        retraining = next(
            item
            for item in decision.candidates
            if item.candidate_id is InvestigationCandidateId.INVESTIGATE_RETRAINING
        )
        assert retraining.status is CandidateStatus.NOT_RECOMMENDED
        assert retraining.rank is None
        assert any("poor outcome alone" in reason for reason in retraining.exclusion_reasons)

    def test_infrastructure_saturation_does_not_trigger_retraining(
        self, demo_workspace: Path
    ) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        decision = _decide(packet)
        retraining = next(
            item
            for item in decision.candidates
            if item.candidate_id is InvestigationCandidateId.INVESTIGATE_RETRAINING
        )
        assert retraining.status is CandidateStatus.NOT_RECOMMENDED
        gate = decision.retraining_gate
        infra = next(
            item
            for item in gate.requirements
            if item.requirement_id == "infrastructure_explanation_excluded"
        )
        assert not infra.satisfied
        assert "alternative explanation" in infra.evidence

    def test_retraining_requires_an_isolated_policy_comparator(self) -> None:
        rules = {**_EVALUATED_QUIET, "R1": ("triggered", "moderate")}
        satisfied = _decide(
            _fixture_packet(
                rules,
                subject_kind="comparison",
                changed_paths=("policy.algorithm",),
                comparison_compatible=True,
                variation_standing="SYNTHETIC",
            )
        )
        retraining = next(
            item
            for item in satisfied.candidates
            if item.candidate_id is InvestigationCandidateId.INVESTIGATE_RETRAINING
        )
        assert satisfied.retraining_gate.satisfied
        assert retraining.status is CandidateStatus.ELIGIBLE_LAST_RESORT
        assert satisfied.ranked_candidate_ids[-1] is (
            InvestigationCandidateId.INVESTIGATE_RETRAINING
        )

    def test_a_confounded_policy_comparison_fails_the_gate(self) -> None:
        rules = {**_EVALUATED_QUIET, "R1": ("triggered", "moderate")}
        decision = _decide(
            _fixture_packet(
                rules,
                subject_kind="comparison",
                changed_paths=("policy.algorithm", "workload.birth_rate_multiplier"),
                comparison_compatible=True,
                variation_standing="SYNTHETIC",
            )
        )
        isolated = next(
            item
            for item in decision.retraining_gate.requirements
            if item.requirement_id == "policy_identity_isolated"
        )
        assert not isolated.satisfied
        assert "workload.birth_rate_multiplier" in isolated.evidence
        assert not decision.retraining_gate.satisfied

    def test_a_missing_comparator_is_a_clear_exclusion(self) -> None:
        rules = {**_EVALUATED_QUIET, "R1": ("triggered", "moderate")}
        decision = _decide(_fixture_packet(rules))
        comparator = next(
            item
            for item in decision.retraining_gate.requirements
            if item.requirement_id == "compatible_policy_comparator_present"
        )
        assert not comparator.satisfied
        assert "not a compatible comparison" in comparator.evidence

    def test_unknown_standing_fails_the_gate(self) -> None:
        rules = {**_EVALUATED_QUIET, "R1": ("triggered", "moderate")}
        gate = evaluate_retraining_gate(
            _fixture_packet(
                rules,
                subject_kind="comparison",
                changed_paths=("policy.algorithm",),
                comparison_compatible=True,
                baseline_standing="UNKNOWN",
                variation_standing="SYNTHETIC",
            )
        )
        standing = next(
            item for item in gate.requirements if item.requirement_id == "evidence_standing_known"
        )
        assert not standing.satisfied
        assert not gate.satisfied

    def test_even_a_satisfied_gate_stays_a_proposal(self) -> None:
        rules = {**_EVALUATED_QUIET, "R1": ("triggered", "moderate")}
        gate = evaluate_retraining_gate(
            _fixture_packet(
                rules,
                subject_kind="comparison",
                changed_paths=("policy.algorithm",),
                comparison_compatible=True,
                variation_standing="SYNTHETIC",
            )
        )
        assert gate.satisfied
        assert gate.proposal_only is True
        assert "not a claim that retraining will help" in gate.note


class TestLedgerAndProvenance:
    def test_every_roster_candidate_is_always_assessed(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        decision = _decide(packet)
        assert tuple(item.candidate_id for item in decision.candidates) == tuple(
            InvestigationCandidateId
        )
        for item in decision.candidates:
            assert item.executable is False
            assert item.execution_authority is False

    def test_every_excluded_candidate_carries_typed_exclusions(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        decision = _decide(packet)
        for item in decision.candidates:
            if item.rank is None:
                assert item.exclusion_codes, item.candidate_id
                assert item.exclusion_reasons, item.candidate_id
        assert decision.exclusions
        codes = {code for _, code in decision.exclusions}
        assert codes <= {code.value for code in CandidateExclusionCode}

    def test_admission_evidence_stays_out_of_scope_with_a_pointer(
        self, demo_workspace: Path
    ) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        decision = _decide(packet)
        admission = next(
            item
            for item in decision.candidates
            if item.candidate_id is InvestigationCandidateId.INSPECT_ADMISSION_OR_REJECTION_EVIDENCE
        )
        assert admission.status is CandidateStatus.NOT_EVALUABLE
        assert admission.exclusion_reasons == (ADMISSION_EVIDENCE_SCOPE_STATEMENT,)

    def test_unavailable_evidence_stays_unavailable(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        decision = _decide(packet)
        training = next(
            item
            for item in decision.candidates
            if item.candidate_id is InvestigationCandidateId.INVESTIGATE_TRAINING_CONDITIONS
        )
        assert training.status is CandidateStatus.NOT_EVALUABLE
        assert training.unavailable_evidence
        assert decision.unavailable_metric_keys == packet.unavailable_metric_keys

    def test_provenance_refs_bind_the_whole_chain(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        decision = _decide(packet)
        joined = " ".join(decision.provenance_refs)
        assert "analyst_packet:" in joined
        assert "recommendation_packet:" in joined
        assert decision.analyst_packet_fingerprint == packet.fingerprint()

    def test_a_mismatched_chain_is_a_typed_refusal(self, demo_workspace: Path) -> None:
        packet_a = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        packet_b = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        classification_b = classify_packet(packet_b)
        recommendation_b = select_recommendation(packet_b, classification_b)
        with pytest.raises(AnalystRefusalError) as error:
            decide_recommendation(packet_a, classification_b, recommendation_b)
        assert "PROVENANCE_INCOMPLETE" in str(error.value)


class TestDeterminism:
    def test_ranking_is_input_order_independent(self) -> None:
        rules = {
            "R0": ("not_triggered", "unavailable"),
            "R1": ("triggered", "moderate"),
            "R2": ("triggered", "high"),
            "R4": ("triggered", "low"),
        }
        forward = _decide(_fixture_packet(rules))
        backward = _decide(_fixture_packet(dict(reversed(list(rules.items())))))
        assert forward.ranked_candidate_ids == backward.ranked_candidate_ids
        assert [item.status for item in forward.candidates] == [
            item.status for item in backward.candidates
        ]

    def test_identical_inputs_produce_identical_decisions(self, demo_workspace: Path) -> None:
        def build() -> RecommendationDecision:
            packet = build_analyst_packet(
                _analysis(demo_workspace, "baseline"),
                _analysis(demo_workspace, "infrastructure_bottleneck"),
            )
            return _decide(packet)

        first, second = build(), build()
        assert first.canonical_json() == second.canonical_json()
        assert first.fingerprint() == second.fingerprint()

    def test_the_engine_introduces_no_numeric_thresholds(self) -> None:
        source = (
            Path(__file__).resolve().parents[2] / "src" / "traffictwin" / "analyst" / "decision.py"
        ).read_text(encoding="utf-8")
        assert not re.search(r"[<>]=?\s*\d", source), (
            "decision.py must not compare against numeric literals"
        )


class TestEvidenceStanding:
    def test_synthetic_evidence_stays_synthetic(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        decision = _decide(packet)
        assert decision.evidence_standing == "SYNTHETIC"
        assert any("synthetic" in item.lower() for item in decision.limitations)

    def test_imported_evidence_stays_imported(self) -> None:
        decision = _decide(
            _fixture_packet(
                {**_EVALUATED_QUIET, "R2": ("triggered", "moderate")},
                baseline_standing="IMPORTED",
            )
        )
        assert decision.evidence_standing == "IMPORTED"

    def test_boundaries_are_type_level(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        decision = _decide(packet)
        assert decision.advisory_only is True
        assert decision.creates_new_evidence is False
        assert decision.execution_authority is False
        assert decision.causal_claim_supported is False


class TestWhatIfBoundary:
    def test_load_management_challenge_is_honestly_not_representable(self) -> None:
        packet = _fixture_packet({**_EVALUATED_QUIET, "R4": ("triggered", "moderate")})
        classification = classify_packet(packet)
        recommendation = select_recommendation(packet, classification)
        challenge = plan_challenge(recommendation, packet)
        assert challenge.readiness is ChallengeReadiness.NOT_REPRESENTABLE
        with pytest.raises(AnalystRefusalError):
            build_challenge_prefill(challenge, challenge.tracks[0], {})

    def test_no_intervention_yields_no_challenge_parameters(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        classification = classify_packet(packet)
        recommendation = select_recommendation(packet, classification)
        challenge = plan_challenge(recommendation, packet)
        assert challenge.readiness is ChallengeReadiness.NO_ACTIONABLE_CHALLENGE
        assert challenge.tracks == ()
        with pytest.raises(AnalystRefusalError):
            build_challenge_prefill(challenge, _fixture_track(), {})


def _fixture_track() -> ChallengeTrack:
    return ChallengeTrack(
        track_id="fixture",
        title="fixture",
        readiness=ChallengeReadiness.NEEDS_USER_INPUT,
        research_question="fixture",
        comparison_structure="fixture",
        could_support="fixture",
        cannot_establish="fixture",
    )

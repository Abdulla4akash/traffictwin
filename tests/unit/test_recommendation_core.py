"""The recommendation selector is deterministic, traceable, and fail-closed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from traffictwin.analyst import (
    AnalystRefusalError,
    RecommendationCategory,
    RecommendationEvidencePacket,
    build_analyst_packet,
    classify_packet,
    select_recommendation,
)
from traffictwin.analyst.models import (
    AnalystClassification,
    AnalystDiagnostics,
    AnalystEvidencePacket,
    AnalystIdentity,
    AnalystProvenance,
    AnalystRecommendationFact,
    AnalystRuleFact,
    AnalystSignal,
)
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("recommendation") / "demo"
    initialise_workspace(workspace)
    return workspace


def _analysis(workspace: Path, name: str) -> BundleAnalysis:
    return validate_bundle_for_ui(workspace / "bundles" / name)


def _fixture_packet(rules: dict[str, tuple[str, str]]) -> AnalystEvidencePacket:
    return AnalystEvidencePacket(
        identity=AnalystIdentity(subject_kind="single_run", baseline_standing="SYNTHETIC"),
        diagnostics=AnalystDiagnostics(
            subject_side="single_run",
            subject_readiness="partially_ready",
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


def _recommend(
    packet: AnalystEvidencePacket,
) -> tuple[AnalystClassification, RecommendationEvidencePacket]:
    classification = classify_packet(packet)
    return classification, select_recommendation(packet, classification)


class TestRealBundleSelection:
    def test_model_side_evidence_selects_model_investigation(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INVESTIGATE_MODEL_OR_TRAINING
        assert recommendation.contributing_rule_ids == ("R1",)
        assert all(s.track == "model" for s in recommendation.source_recommendations)
        assert recommendation.source_recommendations, "must quote existing R1 recommendations"

    def test_infrastructure_evidence_selects_capacity_investigation(
        self, demo_workspace: Path
    ) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY
        assert recommendation.contributing_rule_ids == ("R2",)
        assert all(s.track == "infrastructure" for s in recommendation.source_recommendations)

    def test_unattributed_candidate_selects_controlled_comparison(
        self, demo_workspace: Path
    ) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        classification, recommendation = _recommend(packet)
        assert classification.signal is AnalystSignal.INSUFFICIENT_EVIDENCE
        assert recommendation.category is RecommendationCategory.INVESTIGATE_SCENARIO_OR_CONTROL
        assert recommendation.contributing_rule_ids == ("R7",)

    def test_no_material_problem_fabricates_no_intervention(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.NO_ACTIONABLE_PROBLEM_DETECTED
        assert recommendation.source_recommendations == ()
        assert recommendation.contributing_rule_ids == ()

    def test_unevaluable_training_evidence_stays_visible(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        _, recommendation = _recommend(packet)
        assert any("R5" in item for item in recommendation.missing_evidence)

    def test_identical_inputs_produce_identical_packets(self, demo_workspace: Path) -> None:
        def build() -> RecommendationEvidencePacket:
            packet = build_analyst_packet(
                _analysis(demo_workspace, "baseline"),
                _analysis(demo_workspace, "infrastructure_bottleneck"),
            )
            classification = classify_packet(packet)
            return select_recommendation(packet, classification)

        first, second = build(), build()
        assert first.canonical_json() == second.canonical_json()
        assert first.fingerprint() == second.fingerprint()


class TestFixtureSelection:
    def test_mixed_evidence_preserves_both_tracks(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("triggered", "moderate"),
                "R2": ("triggered", "high"),
            }
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.MIXED_INVESTIGATION
        tracks = {s.track for s in recommendation.source_recommendations}
        assert tracks == {"model", "infrastructure"}

    def test_load_imbalance_selects_rsu_load_management(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("not_triggered", "unavailable"),
                "R2": ("not_triggered", "unavailable"),
                "R4": ("triggered", "moderate"),
            }
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT
        assert recommendation.alternative_category is None

    def test_imbalance_with_bottleneck_keeps_capacity_as_alternative(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("not_triggered", "unavailable"),
                "R2": ("triggered", "moderate"),
                "R4": ("triggered", "moderate"),
            }
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INVESTIGATE_RSU_LOAD_MANAGEMENT
        assert (
            recommendation.alternative_category
            is RecommendationCategory.INVESTIGATE_INFRASTRUCTURE_CAPACITY
        )
        assert recommendation.alternative_reason is not None

    def test_the_readiness_gate_stays_insufficient(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("triggered", "high"),
                "R2": ("triggered", "high"),
                "R7": ("triggered", "high"),
            }
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INSUFFICIENT_EVIDENCE
        assert recommendation.source_recommendations == ()

    def test_unevaluable_side_rules_stay_insufficient(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("insufficient_evidence", "unavailable"),
                "R2": ("insufficient_evidence", "unavailable"),
            }
        )
        _, recommendation = _recommend(packet)
        assert recommendation.category is RecommendationCategory.INSUFFICIENT_EVIDENCE


class TestTraceabilityAndFailClosed:
    def test_every_source_traces_to_a_triggered_contributing_rule(
        self, demo_workspace: Path
    ) -> None:
        for name in ("under_offloading", "infrastructure_bottleneck", "stressed_demand"):
            packet = build_analyst_packet(
                _analysis(demo_workspace, "baseline"), _analysis(demo_workspace, name)
            )
            _, recommendation = _recommend(packet)
            statuses = dict(recommendation.rule_statuses)
            for source in recommendation.source_recommendations:
                assert source.rule_id in recommendation.contributing_rule_ids
                assert statuses[source.rule_id] == "triggered"
                assert source.conditional is True

    def test_a_mismatched_classification_is_refused(self, demo_workspace: Path) -> None:
        packet_a = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        packet_b = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        classification_b = classify_packet(packet_b)
        with pytest.raises(AnalystRefusalError) as excinfo:
            select_recommendation(packet_a, classification_b)
        assert excinfo.value.code.value == "PROVENANCE_INCOMPLETE"

    def test_an_incompatible_pair_fails_closed_upstream(
        self, demo_workspace: Path, tmp_path: Path
    ) -> None:
        from traffictwin.synthetic.bundles import write_synthetic_bundle
        from traffictwin.synthetic.scenarios import preset_config

        other = write_synthetic_bundle(
            preset_config("baseline", random_seed=11), tmp_path / "baseline-seed11"
        )
        with pytest.raises(AnalystRefusalError) as excinfo:
            build_analyst_packet(
                _analysis(demo_workspace, "baseline"), validate_bundle_for_ui(other)
            )
        assert excinfo.value.code.value == "INCOMPATIBLE_PAIR"

    def test_the_selector_encodes_no_numeric_thresholds(self) -> None:
        source = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "traffictwin"
            / "analyst"
            / "recommendation.py"
        ).read_text(encoding="utf-8")
        assert not re.search(r"\d+\.\d+(?!\")", source.replace("1.0", "")), (
            "the selector must not encode numeric thresholds"
        )
        for forbidden in ("0.9", "0.8", "0.6", "0.2", ">=", "<="):
            assert forbidden not in source, f"threshold-like token {forbidden!r} found"

    def test_the_packet_never_claims_authority(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        _, recommendation = _recommend(packet)
        assert recommendation.creates_new_evidence is False
        assert recommendation.execution_authority is False
        assert recommendation.causal_claim_supported is False
        assert recommendation.whatif_prefill_available is False
        assert "Deferred" in recommendation.whatif_prefill_deferred_reason

"""The challenge planner is deterministic, capability-aware, and fail-closed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from traffictwin.analyst import (
    AnalystRefusalError,
    ChallengeCategory,
    ChallengeReadiness,
    build_analyst_packet,
    build_challenge_prefill,
    classify_packet,
    plan_challenge,
    resolve_scenario_track,
    select_recommendation,
)
from traffictwin.analyst.challenge import (
    REGISTERED_POLICY_PROFILES,
    SCENARIO_DIMENSION_FIELDS,
    WhatIfChallengeSpec,
)
from traffictwin.analyst.models import (
    AnalystDiagnostics,
    AnalystEvidencePacket,
    AnalystIdentity,
    AnalystProvenance,
    AnalystRecommendationFact,
    AnalystRuleFact,
)
from traffictwin.analyst.recommendation import RecommendationEvidencePacket
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.ui.challenge_whatif_bridge import (
    draft_to_handoff_dict,
    is_valid_handoff_dict,
)
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("challenge") / "demo"
    initialise_workspace(workspace)
    return workspace


def _analysis(workspace: Path, name: str) -> BundleAnalysis:
    return validate_bundle_for_ui(workspace / "bundles" / name)


def _chain(
    workspace: Path, name: str | None
) -> tuple[AnalystEvidencePacket, RecommendationEvidencePacket, WhatIfChallengeSpec]:
    baseline = _analysis(workspace, "baseline")
    variation = _analysis(workspace, name) if name else None
    packet = build_analyst_packet(baseline, variation)
    recommendation = select_recommendation(packet, classify_packet(packet))
    return packet, recommendation, plan_challenge(recommendation, packet)


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


def _fixture_chain(
    rules: dict[str, tuple[str, str]],
) -> tuple[AnalystEvidencePacket, RecommendationEvidencePacket, WhatIfChallengeSpec]:
    packet = _fixture_packet(rules)
    recommendation = select_recommendation(packet, classify_packet(packet))
    return packet, recommendation, plan_challenge(recommendation, packet)


class TestDeterministicMapping:
    def test_capacity_recommendation_yields_a_capacity_challenge(
        self, demo_workspace: Path
    ) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        assert spec.category is ChallengeCategory.INFRASTRUCTURE_CAPACITY_CHALLENGE
        assert spec.readiness is ChallengeReadiness.NEEDS_USER_INPUT
        track = spec.tracks[0]
        assert track.whatif_field == "rsu_capacity"
        assert "service/compute" in (track.variable_under_investigation or "")
        assert any("queue capacity" in item for item in track.unsupported_dimensions)
        held = {control.dimension for control in track.held_fixed}
        assert "policy_profile" in held
        assert "congestion_multiplier" in held
        assert "rsu_capacity" not in held

    def test_queue_and_service_capacity_are_never_conflated(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        assert any(
            "must not\nbe conflated" in item
            or "not\nbe conflated" in item
            or "not be conflated" in item
            for item in spec.limitations
        )

    def test_model_recommendation_yields_a_profile_challenge_not_retraining(
        self, demo_workspace: Path
    ) -> None:
        _, _, spec = _chain(demo_workspace, "under_offloading")
        assert spec.category is ChallengeCategory.MODEL_BEHAVIOUR_CHALLENGE
        track = spec.tracks[0]
        assert track.whatif_field == "policy_profile"
        assert track.required_user_inputs[0].allowed_choices == REGISTERED_POLICY_PROFILES
        held = {control.dimension for control in track.held_fixed}
        assert "rsu_capacity" in held
        assert "rsu_count" in held
        text = spec.canonical_json().lower()
        for command in ("must retrain", "should be retrained", "retraining is required"):
            assert command not in text
        assert "does not train or retrain" in text

    def test_scenario_recommendation_yields_a_scenario_challenge(
        self, demo_workspace: Path
    ) -> None:
        _, _, spec = _chain(demo_workspace, "stressed_demand")
        assert spec.category is ChallengeCategory.SCENARIO_CONTROL_CHALLENGE
        track = spec.tracks[0]
        assert track.required_user_inputs[0].allowed_choices == SCENARIO_DIMENSION_FIELDS

    def test_no_actionable_problem_manufactures_no_challenge(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, None)
        assert spec.category is ChallengeCategory.NO_ACTIONABLE_CHALLENGE
        assert spec.readiness is ChallengeReadiness.NO_ACTIONABLE_CHALLENGE
        assert spec.tracks == ()

    def test_rsu_load_management_is_honestly_not_representable(self) -> None:
        _, _, spec = _fixture_chain(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("not_triggered", "unavailable"),
                "R2": ("not_triggered", "unavailable"),
                "R4": ("triggered", "moderate"),
            }
        )
        assert spec.category is ChallengeCategory.RSU_LOAD_MANAGEMENT_CHALLENGE
        assert spec.readiness is ChallengeReadiness.NOT_REPRESENTABLE
        assert spec.tracks[0].readiness is ChallengeReadiness.NOT_REPRESENTABLE
        assert any("placement" in item for item in spec.limitations)

    def test_mixed_preserves_two_mechanism_tracks(self) -> None:
        _, _, spec = _fixture_chain(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("triggered", "moderate"),
                "R2": ("triggered", "moderate"),
            }
        )
        assert spec.category is ChallengeCategory.MIXED_MECHANISM_CHALLENGE
        assert {track.track_id for track in spec.tracks} == {
            "infrastructure-capacity",
            "model-behaviour",
        }
        assert "does not justify calling" in spec.statement

    def test_insufficient_evidence_fails_closed(self) -> None:
        _, _, spec = _fixture_chain(
            {
                "R0": ("triggered", "high"),
                "R2": ("triggered", "high"),
            }
        )
        assert spec.category is ChallengeCategory.INSUFFICIENT_EVIDENCE
        assert spec.readiness is ChallengeReadiness.INSUFFICIENT_EVIDENCE
        assert spec.tracks == ()

    def test_unevaluable_evidence_stays_visible(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        assert any("R5" in item for item in spec.missing_evidence)


class TestDeterminismAndProvenance:
    def test_identical_inputs_produce_identical_specs(self, demo_workspace: Path) -> None:
        first = _chain(demo_workspace, "infrastructure_bottleneck")[2]
        second = _chain(demo_workspace, "infrastructure_bottleneck")[2]
        assert first.canonical_json() == second.canonical_json()
        assert first.fingerprint() == second.fingerprint()

    def test_the_provenance_chain_is_complete(self, demo_workspace: Path) -> None:
        packet, recommendation, spec = _chain(demo_workspace, "under_offloading")
        assert spec.source_analyst_fingerprint == packet.fingerprint()
        assert spec.source_recommendation_fingerprint == recommendation.fingerprint()
        assert any(ref.startswith("recommendation_packet:") for ref in spec.provenance_refs)
        assert any(ref.startswith("analyst_packet:") for ref in spec.provenance_refs)

    def test_a_mismatched_pairing_is_refused(self, demo_workspace: Path) -> None:
        packet_a, recommendation_a, _ = _chain(demo_workspace, "under_offloading")
        packet_b, _, _ = _chain(demo_workspace, "infrastructure_bottleneck")
        with pytest.raises(AnalystRefusalError) as excinfo:
            plan_challenge(recommendation_a, packet_b)
        assert excinfo.value.code.value == "PROVENANCE_INCOMPLETE"

    def test_the_planner_encodes_no_numeric_thresholds(self) -> None:
        source = (
            Path(__file__).resolve().parents[2] / "src" / "traffictwin" / "analyst" / "challenge.py"
        ).read_text(encoding="utf-8")
        cleaned = source.replace("1.0", "")
        assert not re.search(r"\d+\.\d+", cleaned), (
            "the planner must not encode numeric values or thresholds"
        )

    def test_the_spec_never_claims_authority(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        assert spec.execution_authority is False
        assert spec.creates_new_evidence is False
        assert spec.causal_claim_supported is False


class TestPrefillBoundary:
    def test_a_resolved_capacity_track_converts_to_a_valid_prefill(
        self, demo_workspace: Path
    ) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        draft = build_challenge_prefill(spec, spec.tracks[0], {"comparison_rsu_capacity": 30.0})
        assert draft.whatif_overrides == {"rsu_capacity": 30.0}
        assert draft.challenge_id.startswith("whatif-challenge-")
        assert draft.mapping_status.value == "FULLY_MAPPABLE"
        assert is_valid_handoff_dict(draft_to_handoff_dict(draft))
        assert all("challenge." in field.challenge_path for field in draft.supported_fields)
        assert any("Nothing has been executed" in warning for warning in draft.warnings)

    def test_the_prefill_fingerprint_is_deterministic_and_order_independent(
        self, demo_workspace: Path
    ) -> None:
        _, _, spec = _chain(demo_workspace, "under_offloading")
        track = spec.tracks[0]
        first = build_challenge_prefill(
            spec, track, {"comparison_policy_profile": "synthetic-always-local"}
        )
        second = build_challenge_prefill(
            spec,
            track,
            dict(reversed(list({"comparison_policy_profile": "synthetic-always-local"}.items()))),
        )
        assert first.fingerprint == second.fingerprint

    def test_an_unresolved_input_blocks_the_prefill(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        with pytest.raises(AnalystRefusalError) as excinfo:
            build_challenge_prefill(spec, spec.tracks[0], {})
        assert "unresolved" in str(excinfo.value)

    def test_an_unregistered_profile_fails_closed(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "under_offloading")
        with pytest.raises(AnalystRefusalError):
            build_challenge_prefill(
                spec, spec.tracks[0], {"comparison_policy_profile": "invented-profile"}
            )

    def test_an_out_of_range_value_fails_closed(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "infrastructure_bottleneck")
        with pytest.raises(AnalystRefusalError):
            build_challenge_prefill(spec, spec.tracks[0], {"comparison_rsu_capacity": 0.25})

    def test_a_not_representable_track_cannot_create_a_prefill(self) -> None:
        _, _, spec = _fixture_chain(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("not_triggered", "unavailable"),
                "R2": ("not_triggered", "unavailable"),
                "R4": ("triggered", "moderate"),
            }
        )
        with pytest.raises(AnalystRefusalError):
            build_challenge_prefill(spec, spec.tracks[0], {})

    def test_scenario_resolution_pins_the_chosen_dimension(self, demo_workspace: Path) -> None:
        _, _, spec = _chain(demo_workspace, "stressed_demand")
        track = resolve_scenario_track(spec, "congestion_multiplier")
        assert track.whatif_field == "congestion_multiplier"
        held = {control.dimension for control in track.held_fixed}
        assert "congestion_multiplier" not in held
        assert "policy_profile" in held
        with pytest.raises(AnalystRefusalError):
            resolve_scenario_track(spec, "rsu_capacity")

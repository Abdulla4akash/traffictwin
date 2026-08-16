"""The Analyst packet and classification are deterministic and fail closed."""

from __future__ import annotations

from pathlib import Path

import pytest

from traffictwin.analyst import (
    AnalystRefusalError,
    AnalystSignal,
    build_analyst_packet,
    classify_packet,
)
from traffictwin.analyst.models import (
    AnalystDiagnostics,
    AnalystEvidencePacket,
    AnalystIdentity,
    AnalystProvenance,
    AnalystRuleFact,
)
from traffictwin.demo.workspace import initialise_workspace
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.scenarios import preset_config
from traffictwin.ui.services.bundles import validate_bundle_for_ui
from traffictwin.ui.services.models import BundleAnalysis


@pytest.fixture(scope="module")
def demo_workspace(tmp_path_factory: pytest.TempPathFactory) -> Path:
    workspace = tmp_path_factory.mktemp("analyst") / "demo"
    initialise_workspace(workspace)
    return workspace


def _analysis(workspace: Path, name: str) -> BundleAnalysis:
    return validate_bundle_for_ui(workspace / "bundles" / name)


def _fixture_packet(rules: dict[str, tuple[str, str]]) -> AnalystEvidencePacket:
    """A minimal packet whose rule statuses drive the classifier directly."""

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
                )
                for rule_id, (status, confidence) in rules.items()
            ),
        ),
        provenance=AnalystProvenance(),
    )


class TestPacketDeterminism:
    def test_identical_inputs_produce_an_identical_fingerprint(self, demo_workspace: Path) -> None:
        first = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        second = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        assert first.fingerprint() == second.fingerprint()
        assert first.canonical_json() == second.canonical_json()

    def test_classification_is_stable_for_identical_packets(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        assert classify_packet(packet) == classify_packet(packet)


class TestRealBundleClassification:
    def test_infrastructure_bottleneck_yields_the_infrastructure_signal(
        self, demo_workspace: Path
    ) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "infrastructure_bottleneck"),
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.INFRASTRUCTURE_SIDE_SIGNAL
        assert "R2:triggered" in classification.rule_basis
        assert classification.supported_facts
        assert classification.next_investigation is not None
        assert "conditional" in classification.next_investigation

    def test_under_offloading_yields_the_model_signal(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "under_offloading"),
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.MODEL_SIDE_SIGNAL
        assert "R1:triggered" in classification.rule_basis

    def test_an_unattributed_candidate_stays_insufficient(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.INSUFFICIENT_EVIDENCE
        assert "cannot distinguish" in classification.statement

    def test_a_clean_single_run_reports_no_material_problem(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(_analysis(demo_workspace, "baseline"))
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.NO_MATERIAL_PROBLEM_DETECTED
        assert "does not prove the absence" in classification.statement
        assert classification.next_investigation is None


class TestFixtureClassification:
    def test_both_sides_triggered_is_mixed(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("triggered", "moderate"),
                "R2": ("triggered", "high"),
                "R4": ("not_triggered", "unavailable"),
                "R5": ("not_triggered", "unavailable"),
            }
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.MIXED_SIGNAL
        assert classification.confidence == "moderate"

    def test_the_readiness_gate_refuses_first(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("triggered", "high"),
                "R1": ("triggered", "high"),
                "R2": ("triggered", "high"),
            }
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.INSUFFICIENT_EVIDENCE
        assert "readiness gate" in classification.statement

    def test_unevaluable_side_rules_stay_insufficient_not_guessed(self) -> None:
        packet = _fixture_packet(
            {
                "R0": ("not_triggered", "unavailable"),
                "R1": ("insufficient_evidence", "unavailable"),
                "R2": ("insufficient_evidence", "unavailable"),
            }
        )
        classification = classify_packet(packet)
        assert classification.signal is AnalystSignal.INSUFFICIENT_EVIDENCE
        assert classification.confidence == "unavailable"


class TestFailClosedRefusals:
    def test_an_incompatible_pair_is_refused(self, demo_workspace: Path, tmp_path: Path) -> None:
        other_seed = write_synthetic_bundle(
            preset_config("baseline", random_seed=8), tmp_path / "baseline-seed8"
        )
        with pytest.raises(AnalystRefusalError) as excinfo:
            build_analyst_packet(
                _analysis(demo_workspace, "baseline"),
                validate_bundle_for_ui(other_seed),
            )
        assert excinfo.value.code.value == "INCOMPATIBLE_PAIR"

    def test_a_rejected_bundle_is_refused_as_too_weak(self, demo_workspace: Path) -> None:
        rejected = validate_bundle_for_ui(Path("tests/fixtures/bundles/invalid_manifest"))
        with pytest.raises(AnalystRefusalError) as excinfo:
            build_analyst_packet(rejected)
        assert excinfo.value.code.value == "EVIDENCE_STANDING_TOO_WEAK"


class TestEvidenceHonesty:
    def test_unavailable_metrics_stay_unavailable(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        facts = (*packet.traffic_facts, *packet.vec_facts, *packet.infrastructure_facts)
        for fact in facts:
            if fact.status != "available":
                assert fact.metric_key in packet.unavailable_metric_keys
                assert fact.absolute_delta is None
                assert fact.relative_delta is None

    def test_synthetic_evidence_stays_explicitly_synthetic(self, demo_workspace: Path) -> None:
        packet = build_analyst_packet(
            _analysis(demo_workspace, "baseline"),
            _analysis(demo_workspace, "stressed_demand"),
        )
        assert packet.identity.baseline_standing == "SYNTHETIC"
        assert packet.identity.variation_standing == "SYNTHETIC"
        assert any("synthetic" in item.lower() for item in packet.limitations)
        assert packet.creates_new_evidence is False
        assert packet.scientific_recomputation_performed is False
        assert packet.causal_claim_supported is False

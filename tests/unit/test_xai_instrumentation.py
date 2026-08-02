"""Fenced XAI instrumentation, integrity and language-boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.xai_instrumentation import (
    ACTION_VOCABULARY_DIGEST,
    OBSERVATION_CONTRACT_DIGEST,
    SYNTHETIC_ACTOR_CONTRACT_DIGEST,
    SYNTHETIC_CHECKPOINT_DIGEST,
    AlwaysLocalReplay,
    AttributionArtifact,
    CounterfactualReplayResult,
    DecisionTimeSnapshot,
    ExplanationClaimSupport,
    FingerprintBin,
    LyapunovQueueAwareReplay,
    PolicyDisagreementRow,
    SnapshotFeature,
    SourceSupport,
    XaiAuditBundle,
    XaiInstrumentationError,
    browse_disagreements,
    build_behavioural_fingerprints,
    build_disagreement_rows,
    build_policy_decisions,
    build_synthetic_xai_audit_bundle,
    replay_counterfactuals,
    validate_explanation_language,
)
from traffictwin.ui.xai_services import XaiConsoleError, load_xai_console

REPO_ROOT = Path(__file__).resolve().parents[2]


def _bundle() -> XaiAuditBundle:
    return build_synthetic_xai_audit_bundle(
        research_directions_digest="a" * 64,
        producer_citation_digest="b" * 64,
    )


def test_bundle_is_deterministic_complete_and_explicitly_not_real_xai() -> None:
    bundle = _bundle()
    assert bundle.digest() == _bundle().digest()
    assert len(bundle.snapshots) == 12
    assert len(bundle.replay_manifests) == 2
    assert len(bundle.replay_results) == 24
    assert len(bundle.disagreement_rows) == 24
    assert len(bundle.fingerprints) == 3
    assert len(bundle.attribution_artifacts) == 2
    assert bundle.synthetic_fixture is True
    assert bundle.real_attribution_available is False
    assert bundle.causal is False
    assert bundle.faithfulness_validated is False
    assert bundle.scientific_evidence is False
    assert bundle.execution_authority is False


def test_source_support_separates_context_methods_fixture_and_missing_requirements() -> None:
    supports = _bundle().source_support
    roles = {item.role for item in supports}
    assert roles == {
        "project_context",
        "method_reference",
        "synthetic_fixture",
        "unavailable_requirement",
    }
    assert all(item.llm_output is False for item in supports)
    assert all(
        item.evidence is False
        for item in supports
        if item.role in {"project_context", "synthetic_fixture", "unavailable_requirement"}
    )
    method_supports = [item for item in supports if item.role == "method_reference"]
    assert len(method_supports) == 2
    assert all(item.binding_kind == "citation_metadata_only" for item in method_supports)
    assert all("does not validate" in item.limitation.lower() for item in method_supports)


def test_snapshots_bind_exact_source_actor_checkpoint_and_pre_action_features() -> None:
    snapshots = _bundle().snapshots
    assert len({item.digest() for item in snapshots}) == 12
    assert len({item.source_record_digest for item in snapshots}) == 12
    for snapshot in snapshots:
        assert snapshot.actor_contract_digest == SYNTHETIC_ACTOR_CONTRACT_DIGEST
        assert snapshot.checkpoint_digest == SYNTHETIC_CHECKPOINT_DIGEST
        assert snapshot.observation_contract_digest == OBSERVATION_CONTRACT_DIGEST
        assert snapshot.action_vocabulary_digest == ACTION_VOCABULARY_DIGEST
        assert tuple(feature.name for feature in snapshot.features) == (
            "declared_load",
            "queue_fraction",
            "deadline_pressure",
        )
        assert all(feature.visible_before_action for feature in snapshot.features)
        assert snapshot.real_actor is False
        assert snapshot.evidence is False


def test_snapshot_refuses_changed_contract_order_nonfinite_and_extra_identifier() -> None:
    snapshot = _bundle().snapshots[0]
    payload = snapshot.model_dump(mode="python")
    payload["features"] = tuple(reversed(snapshot.features))
    with pytest.raises(ValidationError, match="OBSERVATION_CONTRACT_MISMATCH"):
        DecisionTimeSnapshot.model_validate(payload)
    payload = snapshot.model_dump(mode="python")
    payload["checkpoint_digest"] = "0" * 64
    with pytest.raises(ValidationError, match="CHECKPOINT_DIGEST_MISMATCH"):
        DecisionTimeSnapshot.model_validate(payload)
    with pytest.raises(ValidationError):
        SnapshotFeature(name="declared_load", value=float("nan"))
    payload = snapshot.model_dump(mode="python")
    payload["vehicle_id"] = "synthetic-vehicle"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DecisionTimeSnapshot.model_validate(payload)


def test_private_source_support_refuses_without_echo_contract() -> None:
    with pytest.raises(ValidationError, match="PRIVATE_CONTENT_DETECTED"):
        SourceSupport(
            support_id="unsafe-source",
            role="synthetic_fixture",
            source_ref="/Users/private/source.json",
            source_digest="a" * 64,
            binding_kind="contract_record",
            support_scope="Synthetic contract fixture for one schema test only.",
            limitation="Not a real actor explanation and not scientific evidence.",
            evidence=False,
        )


def test_both_counterfactual_adapters_are_pure_digest_bound_and_non_optimal() -> None:
    bundle = _bundle()
    snapshots = bundle.snapshots
    adapters = (AlwaysLocalReplay(), LyapunovQueueAwareReplay())
    before = tuple(item.digest() for item in snapshots)
    results = replay_counterfactuals(snapshots, adapters)
    after = tuple(item.digest() for item in snapshots)
    assert before == after
    assert len(results) == 24
    assert {item.adapter_id for item in results} == {"always_local", "lyapunov_queue_aware"}
    assert all(item.mutates_snapshot is False for item in results)
    assert all(item.causal is False and item.optimality_supported is False for item in results)
    assert {item.replay_action for item in results if item.adapter_id == "always_local"} == {
        "local"
    }


def test_replay_result_and_bundle_refuse_changed_output_or_binding_digests() -> None:
    bundle = _bundle()
    replay = bundle.replay_results[0]
    payload = replay.model_dump(mode="python")
    payload["replay_action"] = "v2v"
    with pytest.raises(ValidationError, match="REPLAY_OUTPUT_DIGEST_MISMATCH"):
        CounterfactualReplayResult.model_validate(payload)
    changed = replay.model_copy(update={"snapshot_digest": "0" * 64})
    payload = bundle.model_dump(mode="python")
    payload["replay_results"] = (changed,) + bundle.replay_results[1:]
    with pytest.raises(ValidationError, match="REPLAY_BINDING_MISMATCH"):
        XaiAuditBundle.model_validate(payload)


def test_disagreement_rows_are_exact_descriptive_comparisons_and_browser_filters() -> None:
    bundle = _bundle()
    rows = build_disagreement_rows(bundle.snapshots, bundle.replay_results)
    assert rows == bundle.disagreement_rows
    assert all(row.correct_action_identified is False for row in rows)
    assert all(row.interpretation == "descriptive_action_difference_only" for row in rows)
    disagreements = browse_disagreements(rows, disagreement_only=True)
    assert disagreements.total_rows == disagreements.disagreement_rows
    assert 0 < disagreements.total_rows < len(rows)
    local = browse_disagreements(rows, recorded_action="local")
    assert all(row.recorded_action == "local" for row in local.rows)
    assert local.changes_standing is False
    assert local.evidence is False


def test_disagreement_row_and_bundle_refuse_mutated_comparison() -> None:
    bundle = _bundle()
    row = bundle.disagreement_rows[0]
    payload = row.model_dump(mode="python")
    payload["disagreement"] = not row.disagreement
    with pytest.raises(ValidationError, match="DISAGREEMENT_DIGEST_MISMATCH"):
        PolicyDisagreementRow.model_validate(payload)
    changed = row.model_copy(update={"replay_action": "v2v"})
    payload = bundle.model_dump(mode="python")
    payload["disagreement_rows"] = (changed,) + bundle.disagreement_rows[1:]
    with pytest.raises(ValidationError):
        XaiAuditBundle.model_validate(payload)


def test_behavioural_fingerprints_reconcile_support_shares_and_exact_decisions() -> None:
    bundle = _bundle()
    decisions = build_policy_decisions(bundle.snapshots, bundle.replay_results)
    repeated = build_behavioural_fingerprints(decisions)
    assert repeated == bundle.fingerprints
    assert tuple(item.policy_id for item in repeated) == (
        "synthetic_policy_fixture",
        "always_local",
        "lyapunov_queue_aware",
    )
    for fingerprint in repeated:
        assert fingerprint.total_support == 12
        assert sum(row.support for row in fingerprint.bins) == 12
        assert fingerprint.generalisation_supported is False
        assert fingerprint.causal is False
        assert fingerprint.evidence is False
        for row in fingerprint.bins:
            if row.support:
                assert row.local_share is not None
                assert row.v2i_share is not None
                assert row.v2v_share is not None
                assert row.local_share + row.v2i_share + row.v2v_share == pytest.approx(1.0)


def test_empty_fingerprint_bins_are_unavailable_not_zero_filled() -> None:
    empty = FingerprintBin(
        label="low",
        lower_inclusive=0.0,
        upper_exclusive=0.34,
        support=0,
        availability="unavailable_no_support",
    )
    assert empty.local_share is None
    with pytest.raises(ValidationError, match="EMPTY_BIN_MUST_BE_UNAVAILABLE"):
        FingerprintBin(
            label="low",
            lower_inclusive=0.0,
            upper_exclusive=0.34,
            support=0,
            local_share=0.0,
            v2i_share=0.0,
            v2v_share=0.0,
            availability="unavailable_no_support",
        )


def test_attribution_artifacts_are_synthetic_shapes_with_integrity_metadata_only() -> None:
    artifacts = _bundle().attribution_artifacts
    assert tuple(item.method for item in artifacts) == (
        "shap_shaped_synthetic_fixture",
        "integrated_gradients_shaped_synthetic_fixture",
    )
    for artifact in artifacts:
        assert artifact.availability == "synthetic_shape_only"
        assert artifact.real_actor is False
        assert artifact.causal is False
        assert artifact.faithfulness_validated is False
        assert artifact.optimality_supported is False
        assert artifact.scientific_evidence is False
        assert artifact.quality.integrity_check_only is True
        assert artifact.quality.application_validation == "unavailable"
        assert artifact.quality.fidelity_value == 0.0
        assert artifact.quality.stability_value == 0.0


def test_attribution_artifact_and_bundle_refuse_changed_reconstruction_or_binding() -> None:
    bundle = _bundle()
    artifact = bundle.attribution_artifacts[0]
    payload = artifact.model_dump(mode="python")
    payload["output_value"] = artifact.output_value + 1.0
    with pytest.raises(ValidationError, match="ATTRIBUTION_RECONSTRUCTION_MISMATCH"):
        AttributionArtifact.model_validate(payload)
    changed = artifact.model_copy(update={"checkpoint_digest": "0" * 64})
    payload = bundle.model_dump(mode="python")
    payload["attribution_artifacts"] = (changed,) + bundle.attribution_artifacts[1:]
    with pytest.raises(ValidationError):
        XaiAuditBundle.model_validate(payload)


def test_real_attribution_capabilities_are_unavailable_without_zero_substitution() -> None:
    capabilities = _bundle().attribution_capabilities
    assert tuple(item.method for item in capabilities) == ("shap", "integrated_gradients")
    for item in capabilities:
        assert item.status == "unavailable"
        assert item.missing_requirements == (
            "producer_snapshot_hook",
            "authorised_model_access",
            "validated_application_method",
        )
        assert item.zero_substituted is False
        assert item.evidence is False


@pytest.mark.parametrize(
    ("claim", "code"),
    [
        ("Capacity caused the action.", "CAUSAL_SUPPORT_MISSING"),
        ("This proves that the policy is right.", "PROOF_SUPPORT_MISSING"),
        ("This faithfully explains the decision.", "FAITHFULNESS_SUPPORT_MISSING"),
        ("This is a validated explanation.", "VALIDATION_SUPPORT_MISSING"),
        ("This is globally optimal.", "OPTIMALITY_SUPPORT_MISSING"),
        ("This is the safest action.", "SAFETY_SUPPORT_MISSING"),
        ("This solves the problem.", "SOLUTION_SUPPORT_MISSING"),
        ("This guarantees the outcome.", "GUARANTEE_SUPPORT_MISSING"),
    ],
)
def test_language_gate_refuses_unsupported_xai_overclaims(claim: str, code: str) -> None:
    with pytest.raises(XaiInstrumentationError) as refused:
        validate_explanation_language(claim)
    assert refused.value.code == code


def test_language_gate_allows_explicit_boundaries_and_has_no_boolean_override() -> None:
    validate_explanation_language(
        "Synthetic disagreement is descriptive and not causal; faithfulness is unavailable."
    )
    with pytest.raises(ValidationError):
        ExplanationClaimSupport.model_validate({"application_validated": True})


def test_bundle_refuses_private_or_overclaiming_notice() -> None:
    bundle = _bundle()
    for notice, reason in (
        ("Read /Users/private/checkpoint", "PRIVATE_CONTENT_DETECTED"),
        ("This faithfully explains the actor.", "FAITHFULNESS_SUPPORT_MISSING"),
    ):
        payload = bundle.model_dump(mode="python")
        payload["notices"] = bundle.notices + (notice,)
        with pytest.raises((ValidationError, XaiInstrumentationError), match=reason):
            XaiAuditBundle.model_validate(payload)


def test_fixed_source_console_hashes_only_allowlisted_repository_files(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "research_directions_v2.md").write_text("proposal-only context", encoding="utf-8")
    (docs / "producer_citation_requirements.md").write_text("citation contract", encoding="utf-8")
    console = load_xai_console(tmp_path)
    assert len(console.source_links) == 2
    assert console.read_only is True
    assert console.external_requests is False
    assert console.creates_evidence is False
    assert str(tmp_path) not in console.model_dump_json()


def test_fixed_source_console_refuses_symlink_and_oversized_sources(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (docs / "research_directions_v2.md").symlink_to(outside)
    (docs / "producer_citation_requirements.md").write_text("citation", encoding="utf-8")
    with pytest.raises(XaiConsoleError, match="SOURCE_UNAVAILABLE"):
        load_xai_console(tmp_path)


def test_xai_sources_have_no_model_loader_network_execution_or_write_surface() -> None:
    paths = (
        REPO_ROOT / "src" / "traffictwin" / "platform" / "xai_instrumentation.py",
        REPO_ROOT / "src" / "traffictwin" / "ui" / "xai_services.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "import requests",
        "import httpx",
        "import shap",
        "import captum",
        "torch.load",
        "jax.numpy",
        "importlib.import_module",
        "subprocess",
        ".write_text(",
        ".write_bytes(",
        "def execute(",
        "def admit(",
    ):
        assert forbidden not in source

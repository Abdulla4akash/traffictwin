"""Maximum-coverage benchmark protocol, dry-run and governance tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.benchmark_protocol import (
    ACTION_TRACKS,
    CAPACITY_REPRESENTATIONS,
    DOMAIN_IDS,
    EVALUATION_ONLY_ALGORITHMS,
    REQUIRED_ENDPOINT_SET,
    RESEARCH_QUESTIONS,
    REWARD_TRACKS,
    TRAINING_ALGORITHMS,
    BenchmarkProtocol,
    BenchmarkProtocolError,
    CampaignAnalysisReceipt,
    PairedSyntheticResult,
    SignedPredeclaration,
    account_matched_budget,
    analyse_benchmark,
    assess_admission_eligibility,
    build_factorial_plan,
    build_owner_selected_protocol,
    check_compatibility,
    construct_capacity_feature,
    freeze_predeclaration,
    render_predeclaration_draft,
    request_execution,
    synthetic_dry_run,
    validate_resource_estimate,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_PREDECLARATION = (
    REPO_ROOT / "docs/evaluation/capacity_multi_algorithm_benchmark_predeclaration_20260802.md"
)


def _protocol_payload() -> dict[str, object]:
    return build_owner_selected_protocol().model_dump(mode="python")


def _signature(protocol: BenchmarkProtocol) -> SignedPredeclaration:
    artifact = freeze_predeclaration(protocol)
    return SignedPredeclaration(
        protocol_digest=protocol.digest(),
        final_markdown_sha256=artifact.markdown_sha256,
        signer_role="human_owner",
        signature_digest=hashlib.sha256(b"synthetic owner signature fixture").hexdigest(),
        signed_at_utc=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        scope_and_budget_unchanged=True,
        policy_validated=True,
    )


def _receipt(protocol: BenchmarkProtocol, **overrides: object) -> CampaignAnalysisReceipt:
    artifact = freeze_predeclaration(protocol)
    payload: dict[str, object] = {
        "protocol_digest": protocol.digest(),
        "predeclaration_digest": artifact.markdown_sha256,
        "successful_pairs": 20,
        "frozen_analysis_complete": True,
        "multiplicity_complete": True,
        "domains_separate": True,
        "seed_namespaces_unchanged": True,
        "checkpoint_rule_followed": True,
        "deviations": (),
        "deviations_predeclared_acceptable": True,
    }
    payload.update(overrides)
    return CampaignAnalysisReceipt.model_validate(payload)


def test_owner_selected_protocol_is_complete_deterministic_and_not_evidence() -> None:
    protocol = build_owner_selected_protocol()
    assert protocol.digest() == build_owner_selected_protocol().digest()
    assert protocol.research_questions == RESEARCH_QUESTIONS
    assert protocol.owner_decisions_open == ()
    assert protocol.research_status == "owner_approved_candidate"
    assert protocol.predeclaration_status == "proposed_unsigned"
    assert protocol.evidence is False
    assert protocol.creates_new_evidence is False


def test_all_selected_algorithms_representations_domains_and_contracts_are_frozen() -> None:
    protocol = build_owner_selected_protocol()
    assert tuple(item.family for item in protocol.algorithms) == (
        TRAINING_ALGORITHMS + EVALUATION_ONLY_ALGORITHMS
    )
    assert tuple(item.kind for item in protocol.capacity_representations) == (
        CAPACITY_REPRESENTATIONS
    )
    assert tuple(item.domain_id for item in protocol.domains) == DOMAIN_IDS
    assert all(domain.evidence_pool == "separate" for domain in protocol.domains)
    assert protocol.contracts.observation_tracks == CAPACITY_REPRESENTATIONS
    assert protocol.contracts.action_tracks == ACTION_TRACKS
    assert protocol.contracts.reward_tracks == REWARD_TRACKS


def test_factorial_has_exactly_240_cells_and_2400_matched_training_jobs() -> None:
    protocol = build_owner_selected_protocol()
    plan = build_factorial_plan(protocol)
    assert len(plan.cells) == 240
    assert plan.compatible_training_cells == 240
    assert plan.training_jobs == 2400
    assert len({cell.cell_id for cell in plan.cells}) == 240
    assert {cell.algorithm for cell in plan.cells} == set(TRAINING_ALGORITHMS)
    assert all(cell.training_seed_count == 10 for cell in plan.cells)
    assert all(
        cell.matched_interactions_per_seed == protocol.training_interactions_per_seed
        for cell in plan.cells
    )
    assert tuple(item.algorithm for item in plan.evaluation_only_controls) == (
        EVALUATION_ONLY_ALGORITHMS
    )
    assert all(item.training_jobs == 0 for item in plan.evaluation_only_controls)


def test_seed_namespaces_have_exact_counts_and_are_pairwise_disjoint() -> None:
    seeds = build_owner_selected_protocol().seeds
    assert tuple(map(len, (seeds.engineering, seeds.training, seeds.tuning, seeds.evaluation))) == (
        3,
        10,
        5,
        20,
    )
    namespaces = tuple(
        map(set, (seeds.engineering, seeds.training, seeds.tuning, seeds.evaluation))
    )
    assert all(
        not first.intersection(second)
        for index, first in enumerate(namespaces)
        for second in namespaces[index + 1 :]
    )


def test_seed_reuse_and_registered_heldout_seeds_refuse() -> None:
    payload = _protocol_payload()
    seeds = dict(payload["seeds"])  # type: ignore[arg-type]
    seeds["evaluation"] = tuple(range(2300, 2319)) + (2100,)
    payload["seeds"] = seeds
    with pytest.raises(ValidationError, match="SEED_NAMESPACE_CONTAMINATED"):
        BenchmarkProtocol.model_validate(payload)

    payload = _protocol_payload()
    seeds = dict(payload["seeds"])  # type: ignore[arg-type]
    seeds["engineering"] = (0, 1, 2)
    payload["seeds"] = seeds
    with pytest.raises(ValidationError, match="SEED_NAMESPACE_CONTAMINATED"):
        BenchmarkProtocol.model_validate(payload)


def test_capacity_feature_construction_covers_all_six_representations() -> None:
    representations = {
        item.kind: item for item in build_owner_selected_protocol().capacity_representations
    }
    blind = construct_capacity_feature(representations["capacity_blind"])
    scalar = construct_capacity_feature(
        representations["global_scalar"], provisioned_values=(1.25,)
    )
    per_rsu = construct_capacity_feature(
        representations["per_rsu_vector"], provisioned_values=(2.5,) * 10
    )
    local = construct_capacity_feature(
        representations["local_observable"], provisioned_values=(0.75,)
    )
    provisioned_remaining = construct_capacity_feature(
        representations["provisioned_remaining"],
        provisioned_values=(2.5,) * 10,
        remaining_values=(1.25,) * 10,
    )
    utilisation_queue = construct_capacity_feature(
        representations["local_utilisation_queue"],
        utilisation_values=(0.5,),
        queue_values=(2.0,),
    )
    assert blind.values == () and blind.visible_before_action is False
    assert scalar.values == (0.5,)
    assert per_rsu.values == (1.0,) * 10
    assert local.values == (0.3,)
    assert provisioned_remaining.values == (1.0,) * 10 + (0.5,) * 10
    assert utilisation_queue.values == (0.2, 0.8)


def test_capacity_feature_dimension_and_envelope_refusals_are_typed() -> None:
    representation = build_owner_selected_protocol().capacity_representations[2]
    with pytest.raises(BenchmarkProtocolError) as dimension:
        construct_capacity_feature(representation, provisioned_values=(1.0,))
    assert dimension.value.code == "OBSERVATION_DIMENSION_MISMATCH"
    with pytest.raises(BenchmarkProtocolError) as envelope:
        construct_capacity_feature(representation, provisioned_values=(3.0,) * 10)
    assert envelope.value.code == "CAPACITY_REPRESENTATION_UNFROZEN"


def test_primary_and_companion_endpoints_are_mandatory() -> None:
    protocol = build_owner_selected_protocol()
    assert protocol.primary_endpoint == "equal_weight_task_class_deadline_completion"
    assert protocol.reported_endpoints == REQUIRED_ENDPOINT_SET
    payload = _protocol_payload()
    payload["reported_endpoints"] = REQUIRED_ENDPOINT_SET[:-1]
    with pytest.raises(ValidationError, match="PRIMARY_ENDPOINT_MISSING"):
        BenchmarkProtocol.model_validate(payload)


def test_practical_thresholds_and_statistics_are_explicit() -> None:
    statistics = build_owner_selected_protocol().statistics
    assert statistics.paired_bootstrap_confidence == 0.95
    assert statistics.exact_sign_test is True
    assert statistics.paired_permutation_test is True
    assert statistics.confirmatory_multiplicity == "holm_fwer_0.05"
    assert statistics.exploratory_multiplicity == "benjamini_hochberg_fdr_0.05"
    assert statistics.minimum_successful_pairs == 18
    assert statistics.planned_pairs == 20
    assert statistics.practical_thresholds.deadline_completion_absolute == 0.01
    assert statistics.practical_thresholds.mean_latency_ms == 100.0
    assert statistics.post_hoc_seed_expansion_allowed is False


def test_checkpoint_selection_is_terminal_and_never_heldout_selected() -> None:
    protocol = build_owner_selected_protocol()
    assert protocol.checkpoint_policy.primary == "terminal_checkpoint"
    assert protocol.checkpoint_policy.robustness_milestones_percent == (25, 50, 75, 100)
    assert protocol.checkpoint_policy.heldout_selection_allowed is False
    payload = protocol.algorithms[0].model_dump(mode="python")
    payload["checkpoint_selection_rule"] = "best on evaluation return"
    with pytest.raises(ValidationError, match="CHECKPOINT_SELECTION_LEAKAGE"):
        type(protocol.algorithms[0]).model_validate(payload)


def test_nonadmitted_records_may_motivate_but_cannot_be_evidence_inputs() -> None:
    protocol = build_owner_selected_protocol()
    assert any("B-CAP" in item for item in protocol.motivating_context)
    payload = _protocol_payload()
    payload["evidence_inputs"] = ("147-repeat diagnostic",)
    with pytest.raises(ValidationError, match="EXISTING_NON_ADMITTED_REUSE"):
        BenchmarkProtocol.model_validate(payload)

    payload = _protocol_payload()
    payload["evidence_inputs"] = ("clean Sparse64 admitted rerun",)
    with pytest.raises(ValidationError, match="EXISTING_RESULT_REUSE"):
        BenchmarkProtocol.model_validate(payload)


def test_private_paths_are_refused() -> None:
    payload = _protocol_payload()
    payload["evidence_inputs"] = ("/Users/private/result.json",)
    with pytest.raises(ValidationError, match="PRIVATE_CONTENT_DETECTED"):
        BenchmarkProtocol.model_validate(payload)


def test_compatible_training_contracts_compare_and_controls_do_not() -> None:
    algorithms = build_owner_selected_protocol().algorithms
    assert check_compatibility(algorithms[0], algorithms[2]) == "comparable"
    assert check_compatibility(algorithms[0], algorithms[-1]) == "INCOMPATIBLE"


def test_matched_budget_is_complete_but_never_compute_authority() -> None:
    account = account_matched_budget(build_owner_selected_protocol())
    assert account.compatible_training_cells == 240
    assert account.training_jobs == 2400
    assert account.training_interactions_per_job == 5_000_000
    assert account.total_training_interactions == 12_000_000_000
    assert account.gpu_ceiling_hours_estimate == 5000.0
    assert account.cost_ceiling_gbp_estimate == 5000.0
    assert account.estimate_only is True
    assert account.authority is False


def test_cloud_and_accelerator_values_are_estimates_only() -> None:
    compute = build_owner_selected_protocol().compute
    assert compute.primary_scheduler == "gcp_batch"
    assert compute.failover_scheduler == "aws_batch"
    assert compute.accelerator_calibration == ("l4", "a100", "h100")
    assert compute.scientific_cross_accelerator_reproducibility is True
    assert compute.maximum_gpu_hours_estimate == 5000.0
    assert compute.maximum_cost_gbp_estimate == 5000.0
    assert compute.estimate_only is True
    assert compute.authority is False


def test_resource_estimate_ceiling_is_enforced_without_allocation() -> None:
    protocol = build_owner_selected_protocol()
    eligibility = validate_resource_estimate(protocol, gpu_hours=5000.0, cost_gbp=5000.0)
    assert eligibility.within_estimated_ceiling is True
    assert eligibility.allocation_created is False
    assert eligibility.authority is False
    with pytest.raises(BenchmarkProtocolError) as exceeded:
        validate_resource_estimate(protocol, gpu_hours=5000.1, cost_gbp=5000.0)
    assert exceeded.value.code == "RESOURCE_BUDGET_EXCEEDED"


def test_synthetic_dry_run_is_a_publishable_null_and_not_evidence() -> None:
    analysis = synthetic_dry_run(build_owner_selected_protocol())
    assert analysis.evaluated_pairs == 3
    assert analysis.mean_paired_difference == 0.0
    assert analysis.paired_bootstrap_interval_95 == (0.0, 0.0)
    assert analysis.exact_sign_test_p == 1.0
    assert analysis.exact_paired_permutation_p == 1.0
    assert analysis.holm_adjusted_p == (1.0, 1.0)
    assert analysis.benjamini_hochberg_adjusted_p == (1.0, 1.0)
    assert analysis.verdict == "PUBLISHABLE_NULL"
    assert analysis.evidence is False
    assert analysis.confirmatory is False
    assert analysis.synthetic_dry_run is True
    assert "paired_permutation" in analysis.methods_exercised
    assert analysis.deviations == ("synthetic fixture deviation retained",)


def test_synthetic_analysis_refuses_any_other_seed_namespace() -> None:
    protocol = build_owner_selected_protocol()
    results = tuple(
        PairedSyntheticResult(seed=seed, reference_value=1.0, candidate_value=1.0)
        for seed in (9000, 9001, 9002)
    )
    with pytest.raises(BenchmarkProtocolError) as error:
        analyse_benchmark(protocol, results, deviations=(), synthetic=True)
    assert error.value.code == "SEED_NAMESPACE_CONTAMINATED"


def test_predeclaration_is_deterministic_digest_bound_and_unsigned() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    assert artifact.markdown == render_predeclaration_draft(protocol)
    assert artifact.protocol_digest == protocol.digest()
    assert artifact.markdown_sha256 == hashlib.sha256(artifact.markdown.encode()).hexdigest()
    assert artifact.status == "proposed_unsigned"
    assert artifact.signature_present is False
    assert artifact.evidence is False
    assert "2400" in artifact.markdown.replace(",", "")
    assert "## Sign-off (EMPTY)" in artifact.markdown


def test_committed_predeclaration_exactly_matches_the_renderer() -> None:
    assert COMMITTED_PREDECLARATION.read_text(encoding="utf-8") == render_predeclaration_draft(
        build_owner_selected_protocol()
    )


def test_execution_requires_an_exact_human_owner_signature() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    with pytest.raises(BenchmarkProtocolError) as unsigned:
        request_execution(protocol, artifact=artifact)
    assert unsigned.value.code == "PREDECLARATION_UNSIGNED"

    signature = _signature(protocol)
    mismatched = signature.model_copy(update={"final_markdown_sha256": "0" * 64})
    with pytest.raises(BenchmarkProtocolError) as mismatch:
        request_execution(protocol, artifact=artifact, signature=mismatched)
    assert mismatch.value.code == "PREDECLARATION_DIGEST_MISMATCH"


def test_exact_signature_only_returns_eligibility_and_starts_nothing() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    eligibility = request_execution(protocol, artifact=artifact, signature=_signature(protocol))
    assert eligibility.eligible is True
    assert eligibility.automatic_within_signed_scope is True
    assert eligibility.external_scheduler_required is True
    assert eligibility.execution_started is False
    assert eligibility.evidence is False


def test_signature_time_must_be_timezone_aware() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    with pytest.raises(ValidationError, match="timezone-aware"):
        SignedPredeclaration(
            protocol_digest=protocol.digest(),
            final_markdown_sha256=artifact.markdown_sha256,
            signer_role="human_owner",
            signature_digest="a" * 64,
            signed_at_utc=datetime(2026, 8, 2, 12, 0),
            scope_and_budget_unchanged=True,
            policy_validated=True,
        )


def test_rule_based_admission_eligibility_binds_every_required_condition() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    eligibility = assess_admission_eligibility(
        protocol, artifact, _signature(protocol), _receipt(protocol)
    )
    assert eligibility.eligible is True
    assert eligibility.reasons == ()
    assert eligibility.automatic_rule_evaluation is True
    assert eligibility.admission_created is False
    assert eligibility.evidence_created is False


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"successful_pairs": 17}, "MINIMUM_SUCCESSFUL_PAIRS_NOT_MET"),
        ({"frozen_analysis_complete": False}, "FROZEN_ANALYSIS_INCOMPLETE"),
        ({"multiplicity_complete": False}, "MULTIPLICITY_INCOMPLETE"),
        ({"domains_separate": False}, "INCOMPATIBLE_DOMAIN_POOLING"),
        ({"seed_namespaces_unchanged": False}, "SEED_NAMESPACE_CHANGED"),
        ({"checkpoint_rule_followed": False}, "CHECKPOINT_SELECTION_DEVIATION"),
        (
            {"deviations_predeclared_acceptable": False},
            "EXECUTION_DEVIATION_OUTSIDE_RULE",
        ),
    ],
)
def test_admission_ineligibility_preserves_each_rule(
    overrides: dict[str, object], reason: str
) -> None:
    protocol = build_owner_selected_protocol()
    eligibility = assess_admission_eligibility(
        protocol,
        freeze_predeclaration(protocol),
        _signature(protocol),
        _receipt(protocol, **overrides),
    )
    assert eligibility.eligible is False
    assert reason in eligibility.reasons


def test_admission_refuses_a_mismatched_predeclaration_digest() -> None:
    protocol = build_owner_selected_protocol()
    artifact = freeze_predeclaration(protocol)
    eligibility = assess_admission_eligibility(
        protocol,
        artifact,
        _signature(protocol),
        _receipt(protocol, predeclaration_digest="0" * 64),
    )
    assert eligibility.eligible is False
    assert "PREDECLARATION_DIGEST_MISMATCH" in eligibility.reasons


def test_module_contains_no_training_or_external_submission_client() -> None:
    source = (REPO_ROOT / "src/traffictwin/platform/benchmark_protocol.py").read_text(
        encoding="utf-8"
    )
    for forbidden in (
        "subprocess",
        "requests.",
        "urllib",
        "boto3",
        "google.cloud",
        "Popen",
        "ssh ",
        "torch.optim",
        "optimizer.step",
    ):
        assert forbidden not in source

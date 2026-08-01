"""Capacity-aware benchmark tooling (post-v1 B-1, design §9 pre-execution list).

Gates 1-2 only: feature/dimension checks, compatibility, seed-partition
hygiene against the registered ledger, matched budgets, selection-leakage
refusal, endpoint completeness, non-admitted-reuse refusal, the synthetic
dry run producing a publishable null with deviations retained, and the
structural absence of any execution path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from traffictwin.platform.benchmark_protocol import (
    REQUIRED_ENDPOINT_SET,
    ActorCompatibilityRecord,
    BenchmarkProtocol,
    BenchmarkProtocolError,
    check_compatibility,
    render_predeclaration_draft,
    request_execution,
    synthetic_dry_run,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _reference(**overrides: object) -> ActorCompatibilityRecord:
    payload: dict[str, object] = {
        "family": "ukfleettrain_mappo",
        "implementation": "producer vec_env (cited)",
        "action_support": "discrete",
        "observation_dimensions": 17,
        "reward_contract": "producer reward v2_post_nrsus_fix",
        "checkpoint_selection_rule": "fixed pre-hoc: final checkpoint of the frozen budget",
        "training_interaction_budget": 300_000,
    }
    payload.update(overrides)
    return ActorCompatibilityRecord.model_validate(payload)


def _protocol(**overrides: object) -> BenchmarkProtocol:
    payload: dict[str, object] = {
        "traces": ("inc",),
        "fleet_preset": "uk2030",
        "capacity_arms": ("cap-2.5", "cap-0.75"),
        "reference_actor": _reference(),
        "candidate_actor": _reference(observation_dimensions=19),
        "capacity_representation": {
            "kind": "per_rsu_vector",
            "units": "normalised provisioned compute per RSU",
            "normalisation_source": "training_design",
            "missing_value_behaviour": "refuse the step; never impute zero",
            "represents": "provisioned",
            "visibility_timing_rule": "capacity visible before each action, same tick",
            "added_dimensions": 2,
        },
        "single_intended_difference": (
            "one reviewed capacity feature added to the observation; everything else matched"
        ),
        "seeds": {
            "training": (100, 101, 102),
            "tuning": (110, 111),
            "dry_run": (120, 121, 122),
            "evaluation": (130, 131, 132, 133, 134),
        },
        "primary_endpoint": "outcome_coherence_composite",
        "reported_endpoints": REQUIRED_ENDPOINT_SET,
        "exact_test_note": (
            "five paired evaluation seeds carry an exact two-sided sign-test floor of "
            "p=0.0625; more seeds are a design decision, not a post-hoc repair"
        ),
        "minimum_successful_pairs": 3,
        "publishable_null": (
            "the capacity-aware actor does not differ from the reference on the "
            "coherence composite — a complete outcome"
        ),
        "wall_clock_ceiling_hours": 24.0,
        "gpu_ceiling_hours": 12.0,
        "stop_rule": "halt on first failed cell; never retry with altered controls",
        "motivating_context": ("B-CAP 17D/19D smoke motivated the feature shape",),
        "owner_decisions_open": (
            "actor families",
            "seed count and compute budget",
            "hardware source",
        ),
    }
    payload.update(overrides)
    return BenchmarkProtocol.model_validate(payload)


def test_a_valid_protocol_freezes_and_digests() -> None:
    protocol = _protocol()
    assert protocol.evidence is False
    assert protocol.digest() == _protocol().digest()


def test_latency_alone_is_refused_as_primary() -> None:
    with pytest.raises(ValidationError, match="PRIMARY_ENDPOINT_MISSING"):
        _protocol(primary_endpoint="task.latency.mean_ms")
    with pytest.raises(ValidationError, match="PRIMARY_ENDPOINT_MISSING"):
        _protocol(reported_endpoints=("task.latency.mean_ms",))


def test_dimension_and_budget_matching_are_structural() -> None:
    with pytest.raises(ValidationError, match="OBSERVATION_DIMENSION_MISMATCH"):
        _protocol(candidate_actor=_reference(observation_dimensions=17))
    with pytest.raises(ValidationError, match="TRAINING_BUDGET_UNMATCHED"):
        _protocol(
            candidate_actor=_reference(
                observation_dimensions=19, training_interaction_budget=200_000
            )
        )


def test_capacity_representation_freezes_from_training_design_only() -> None:
    with pytest.raises(ValidationError):
        _protocol(
            capacity_representation={
                "kind": "scalar_total",
                "units": "x",
                "normalisation_source": "evaluation_arm",
                "missing_value_behaviour": "refuse",
                "represents": "provisioned",
                "visibility_timing_rule": "before each action",
                "added_dimensions": 1,
            }
        )


def test_seed_namespaces_must_be_disjoint_and_clean() -> None:
    with pytest.raises(ValidationError, match="SEED_NAMESPACE_CONTAMINATED"):
        _protocol(
            seeds={
                "training": (100, 101),
                "tuning": (101, 102),
                "dry_run": (120,),
                "evaluation": (130, 131, 132),
            }
        )
    # Spent held-out seeds {10-14} and every registered cohort refuse.
    with pytest.raises(ValidationError, match="SEED_NAMESPACE_CONTAMINATED"):
        _protocol(
            seeds={
                "training": (100,),
                "tuning": (110,),
                "dry_run": (120,),
                "evaluation": (10, 11, 12),
            }
        )
    with pytest.raises(ValidationError, match="SEED_NAMESPACE_CONTAMINATED"):
        _protocol(
            seeds={
                "training": (0, 1, 2),
                "tuning": (110,),
                "dry_run": (120,),
                "evaluation": (130, 131, 132),
            }
        )


def test_checkpoint_selection_leakage_refuses() -> None:
    with pytest.raises(ValidationError, match="CHECKPOINT_SELECTION_LEAKAGE"):
        _reference(checkpoint_selection_rule="take the best on evaluation seeds")


def test_non_admitted_diagnostics_motivate_but_never_evidence() -> None:
    protocol = _protocol()
    assert protocol.motivating_context
    with pytest.raises(ValidationError, match="EXISTING_NON_ADMITTED_REUSE"):
        _protocol(evidence_inputs=("sparse64 homecoming peak completions",))


def test_five_evaluation_seeds_force_the_sign_test_floor_statement() -> None:
    with pytest.raises(ValidationError, match="p=0.0625"):
        _protocol(exact_test_note="we will look at the pairs")


def test_incompatible_contracts_are_reported_not_ranked() -> None:
    reference = _reference()
    continuous = _reference(action_support="continuous")
    assert check_compatibility(reference, continuous) == "INCOMPATIBLE"
    assert check_compatibility(reference, _reference()) == "comparable"


def test_the_synthetic_dry_run_yields_a_publishable_null_with_deviations() -> None:
    analysis = synthetic_dry_run(_protocol())
    assert analysis.synthetic_dry_run
    assert analysis.verdict == "PUBLISHABLE_NULL"
    assert analysis.mean_paired_difference == 0.0
    assert analysis.deviations
    assert analysis.evidence is False
    assert analysis.confirmatory is False


def test_execution_refuses_at_every_gate() -> None:
    protocol = _protocol()
    with pytest.raises(BenchmarkProtocolError) as decisions:
        request_execution(protocol)
    assert decisions.value.code == "OWNER_DECISION_MISSING"
    closed = _protocol(owner_decisions_open=())
    with pytest.raises(BenchmarkProtocolError) as unsigned:
        request_execution(closed)
    assert unsigned.value.code == "PREDECLARATION_UNSIGNED"
    with pytest.raises(BenchmarkProtocolError) as unauthorised:
        request_execution(closed, predeclaration_signed=True)
    assert unauthorised.value.code == "COMPUTE_AUTHORITY_MISSING"
    # Even with every flag raised, this tooling has no execution path at all.
    with pytest.raises(BenchmarkProtocolError) as never:
        request_execution(closed, predeclaration_signed=True, compute_authorised=True)
    assert never.value.code == "COMPUTE_AUTHORITY_MISSING"


def test_the_draft_is_unsigned_and_the_module_has_no_compute_surface() -> None:
    draft = render_predeclaration_draft(_protocol())
    assert "DRAFT — UNSIGNED" in draft
    assert "p=0.0625" in draft
    assert "| approved_by | |" in draft
    assert "publishable null" in draft.lower()
    source = (REPO_ROOT / "src" / "traffictwin" / "platform" / "benchmark_protocol.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("subprocess", "urllib", "requests", "Popen", "colab", "ssh"):
        assert forbidden not in source

# ruff: noqa: E501
"""Unit tests for Lane 06 matched-draw uncertainty service.

Strict typed-package builder — fails closed on any drift.
Validates exact committed E2b/E2c/E2d view and kills:
sign reversal, wrong draw, wrong mean/CI, wrong replication unit,
task-as-replicate, wrong E2b draw standing, secondary-summary drift.
No p-values or task-level N.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from traffictwin.experiments.e2_comparison import (
    ACTOR_SHA256,
    DECLARED_MEAN_TOLERANCE,
    E2B_DLA,
    E2B_INGRESS_DLA,
    E2B_JSQ,
    E2B_OFF,
    E2C_LOWER,
    E2C_MEAN,
    E2C_PER_SEED,
    E2C_UPPER,
    E2D_LOWER,
    E2D_MEAN,
    E2D_PER_SEED,
    E2D_UPPER,
    E2D_VS_DLA_LOWER,
    E2D_VS_DLA_MEAN,
    E2D_VS_DLA_UPPER,
    TRACE_SHA256,
    E2ResearchComparisonView,
    build_e2_comparison_view,
)
from traffictwin.experiments.e2_research_evidence import (
    E2ResearchEvidencePackage,
    load_e2_research_evidence_json,
)


def _valid_payload() -> dict[str, Any]:
    return {
        "schema_version": "v08_e2_research_evidence_v1",
        "campaign": "v08-requirements-closure",
        "source_identities": {
            "base_sha": "bd4570fd54ffd4e1eb21fc1d8e959190fbb103a6",
            "actor": {
                "sha256": "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208",
                "training_seed": 100,
                "observes_current_rsu_load": False,
                "selects_execution_rsu": False,
            },
            "trace": {"sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"},
            "research_heads": {
                "e2b": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "e2c": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "e2d": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
            },
            "manifest_sha256_by_study": {
                "e2b": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "e2c": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "e2d": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
            },
        },
        "replication_unit": "fleet_draw",
        "evaluator_seed": 0,
        "strategies": [
            {
                "strategy_id": "off",
                "human_label": "Strongest-link off",
                "placement": "strongest-link",
                "admission_gate": "none",
            },
            {
                "strategy_id": "jsq",
                "human_label": "JSQ without gate",
                "placement": "jsq least-busy",
                "admission_gate": "none",
            },
            {
                "strategy_id": "ingress_dla",
                "human_label": "Ingress DLA",
                "placement": "strongest-link",
                "admission_gate": "deadline-aware",
            },
            {
                "strategy_id": "dla",
                "human_label": "Common-target DLA",
                "placement": "common-target jsq",
                "admission_gate": "deadline-aware",
            },
            {
                "strategy_id": "per_task_dla",
                "human_label": "Per-task DLA",
                "placement": "per-task least-busy",
                "admission_gate": "deadline-aware",
            },
        ],
        "observations": [
            {
                "figure_id": "fig1_e2b_offered_attainment_off",
                "evidence_id": "e2b_factorial_comparison",
                "metric": "offered_task_deadline_attainment",
                "arm": "off",
                "value": 0.683619229,
                "manifest_sha256": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "code_commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "fleet_seed": 0,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig1_e2b_offered_attainment_jsq",
                "evidence_id": "e2b_factorial_comparison",
                "metric": "offered_task_deadline_attainment",
                "arm": "jsq",
                "value": 0.675681775,
                "manifest_sha256": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "code_commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "fleet_seed": 0,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig1_e2b_offered_attainment_dla",
                "evidence_id": "e2b_factorial_comparison",
                "metric": "offered_task_deadline_attainment",
                "arm": "dla",
                "value": 0.694939919,
                "manifest_sha256": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "code_commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "fleet_seed": 0,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig1_e2b_offered_attainment_ingress_dla",
                "evidence_id": "e2b_factorial_comparison",
                "metric": "offered_task_deadline_attainment",
                "arm": "ingress_dla",
                "value": 0.715773211,
                "manifest_sha256": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "code_commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "fleet_seed": 0,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig2_e2c_dla_minus_ingress_seed1",
                "evidence_id": "e2c_multidraw_comparison",
                "metric": "offered_attainment_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": -0.022097034972,
                "manifest_sha256": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "code_commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "fleet_seed": 1,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig2_e2c_dla_minus_ingress_seed2",
                "evidence_id": "e2c_multidraw_comparison",
                "metric": "offered_attainment_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": -0.020519134179,
                "manifest_sha256": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "code_commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "fleet_seed": 2,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig2_e2c_dla_minus_ingress_seed3",
                "evidence_id": "e2c_multidraw_comparison",
                "metric": "offered_attainment_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": -0.021447383092,
                "manifest_sha256": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "code_commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "fleet_seed": 3,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig2_e2c_dla_minus_ingress_seed4",
                "evidence_id": "e2c_multidraw_comparison",
                "metric": "offered_attainment_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": -0.020825491499,
                "manifest_sha256": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "code_commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "fleet_seed": 4,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig3_e2d_per_task_minus_ingress_seed1",
                "evidence_id": "e2d_robustness_comparison",
                "metric": "offered_attainment_per_task_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": 0.004636732564,
                "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
                "code_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
                "fleet_seed": 1,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig3_e2d_per_task_minus_ingress_seed2",
                "evidence_id": "e2d_robustness_comparison",
                "metric": "offered_attainment_per_task_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": 0.005867285642,
                "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
                "code_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
                "fleet_seed": 2,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig3_e2d_per_task_minus_ingress_seed3",
                "evidence_id": "e2d_robustness_comparison",
                "metric": "offered_attainment_per_task_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": 0.005071796666,
                "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
                "code_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
                "fleet_seed": 3,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "figure_id": "fig3_e2d_per_task_minus_ingress_seed4",
                "evidence_id": "e2d_robustness_comparison",
                "metric": "offered_attainment_per_task_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": 0.005509919752,
                "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
                "code_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
                "fleet_seed": 4,
                "evaluator_seed": 0,
                "replication_unit": "fleet_draw",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
        ],
        "fleet_draw_sets": [
            {
                "study": "e2b",
                "fleet_seeds": [0],
                "replication_unit": "fleet_draw",
                "evaluator_seed": 0,
            },
            {
                "study": "e2c",
                "fleet_seeds": [1, 2, 3, 4],
                "replication_unit": "fleet_draw",
                "evaluator_seed": 0,
            },
            {
                "study": "e2d",
                "fleet_seeds": [1, 2, 3, 4],
                "replication_unit": "fleet_draw",
                "evaluator_seed": 0,
            },
        ],
        "paired_differences": [
            {
                "comparison_id": "e2c_dla_minus_ingress",
                "fleet_seeds": [1, 2, 3, 4],
                "per_seed_values": [
                    -0.022097034972,
                    -0.020519134179,
                    -0.021447383092,
                    -0.020825491499,
                ],
                "replication_unit": "fleet_draw",
            },
            {
                "comparison_id": "e2d_per_task_minus_ingress",
                "fleet_seeds": [1, 2, 3, 4],
                "per_seed_values": [0.004636732564, 0.005867285642, 0.005071796666, 0.005509919752],
                "replication_unit": "fleet_draw",
            },
            {
                "comparison_id": "e2d_per_task_minus_dla",
                "fleet_seeds": [1, 2, 3, 4],
                "per_seed_values": [0.026733767536, 0.026386419821, 0.026519179758, 0.026335411251],
                "replication_unit": "fleet_draw",
            },
        ],
        "declared_summaries": [
            {
                "comparison_id": "e2c_dla_minus_ingress",
                "mean": -0.021222260935,
                "lower": -0.02233525407,
                "upper": -0.0201092678,
                "sample_sd": 0.000699457605,
                "standard_error": 0.000349728802,
                "degrees_of_freedom": 3,
                "method": "two-sided Student-t 95% interval over fleet-draw differences",
                "includes_zero": False,
                "decision": "evidence_of_directional_difference_within_bounded_four_draw_replication",
            },
            {
                "comparison_id": "e2d_per_task_minus_ingress",
                "mean": 0.005271433656,
                "lower": 0.004422143925,
                "upper": 0.006120723387,
                "sample_sd": 0.000533733895,
                "standard_error": 0.000266866947,
                "degrees_of_freedom": 3,
                "method": "two-sided Student-t 95% interval over fleet-draw differences",
                "includes_zero": False,
                "decision": "directional_advantage_for_per_task_placement_within_bounded_draws",
            },
            {
                "comparison_id": "e2d_per_task_minus_dla",
                "mean": 0.026493694591,
                "lower": 0.026210763951,
                "upper": 0.026776625232,
                "sample_sd": None,
                "standard_error": None,
                "degrees_of_freedom": 3,
                "method": "two-sided Student-t 95% interval over fleet-draw differences",
                "includes_zero": False,
                "decision": "directional_advantage_for_per_task_vs_common_target",
            },
        ],
        "provenance": [
            {
                "artifact": "e2b_factorial_manifest",
                "manifest_sha256": "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91",
                "code_commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "artifact": "e2c_multidraw_manifest",
                "manifest_sha256": "fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a",
                "code_commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
            {
                "artifact": "e2d_robustness_manifest",
                "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
                "code_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
                "standing": "RESEARCH-EVIDENCE FACT",
            },
        ],
        "missingness": [
            {
                "field": "gate_rejected",
                "reason": "evaluator reports combined rejected without stable gate vs capacity split; split unavailable without additional instrumentation",
            },
            {
                "field": "capacity_rejected",
                "reason": "same as gate_rejected; combined rejected only",
            },
            {
                "field": "started",
                "reason": "UNAVAILABLE as an independently instrumented quantity",
            },
            {
                "field": "compute_completed",
                "reason": "not separately emitted; deadline flag conflates execution/return/deadline",
            },
            {
                "field": "returned",
                "reason": "physical return not distinct from deadline_success; marked unavailable",
            },
            {
                "field": "dropped",
                "reason": "cannot derive without compute_completed/returned split",
            },
        ],
        "task_lifecycle": {
            "offered": 13076234,
            "admitted": 10594205,
            "rejected_total": 2482029,
            "forwarded": 600885,
            "deadline_success": 9475948,
            "gate_rejected": None,
            "capacity_rejected": None,
            "started": None,
            "compute_completed": None,
            "returned": None,
            "dropped": None,
            "unavailable_reasons": {
                "gate_rejected": "split unavailable without additional instrumentation",
                "capacity_rejected": "split unavailable without additional instrumentation",
                "started": "UNAVAILABLE as an independently instrumented quantity",
                "compute_completed": "not separately emitted; evaluator conflates execution/return",
                "returned": "physical return not distinct from deadline_success",
                "dropped": "cannot derive without compute_completed/returned split",
            },
        },
        "limitations": [
            "Bounded to one Manchester incident hour 2024-03-15 20:00-21:00 Europe/London",
            "Four matched provisional uk2030 fleet draws seeds 1-4; evaluator seed 0 fixed",
            "Fixed 1x service, zero backhaul, waiting-room cap 2.5x (6220 tasks/RSU)",
            "Frozen 17-dim MAPPO actor does not observe RSU load and does not select execution RSU",
            "E2b one-draw descriptive; no population inference; tasks are accounting records not replicates",
        ],
        "non_claims": [
            "No Kubernetes deployment or cluster orchestration",
            "No learned placement/scheduler; not autonomous infrastructure control",
            "No MAPPO execution-RSU choice or load observation",
            "No Manchester-wide or population-wide performance claim",
            "No physical deployment/return verification; no universal superiority",
            "No free-flow validation; no independent held-out E2d replication",
        ],
    }


def _load_valid() -> E2ResearchEvidencePackage:
    return load_e2_research_evidence_json(json.dumps(_valid_payload()))


# ---------------------------------------------------------------------------
# Happy path — exact committed values from typed package
# ---------------------------------------------------------------------------


def test_build_from_valid_package_matches_committed_e2b() -> None:
    pkg = _load_valid()
    view = build_e2_comparison_view(pkg)
    assert view.e2b.off == pytest.approx(E2B_OFF, abs=1e-12)
    assert view.e2b.jsq == pytest.approx(E2B_JSQ, abs=1e-12)
    assert view.e2b.ingress_dla == pytest.approx(E2B_INGRESS_DLA, abs=1e-12)
    assert view.e2b.dla == pytest.approx(E2B_DLA, abs=1e-12)
    assert view.e2b.replication_unit == "fleet_draw"
    assert view.e2b.n == 1
    assert view.e2b.fleet_seed == 0
    assert view.e2b.evaluator_seed == 0
    assert view.e2b.interval is None
    assert view.e2b.uncertainty == "one_draw_descriptive_no_interval"
    assert (
        view.e2b.manifest_sha256
        == "9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91"
    )
    assert view.e2b.code_commit == "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
    assert view.e2b.actor_sha256 == ACTOR_SHA256
    assert view.e2b.trace_sha256 == TRACE_SHA256


def test_e2c_four_matched_draws_exact() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert view.e2c.n_fleet_draws == 4
    assert view.e2c.fleet_seeds == (1, 2, 3, 4)
    assert view.e2c.seed0_excluded is True
    assert view.e2c.evaluator_seed == 0
    assert view.e2c.replication_unit == "fleet_draw"
    assert view.e2c.degrees_of_freedom == 3
    assert view.e2c.method == "two-sided Student-t 95% interval over fleet-draw differences"
    assert view.e2c.per_seed_values == pytest.approx(E2C_PER_SEED, abs=1e-12)
    assert view.e2c.mean == pytest.approx(E2C_MEAN, abs=1e-12)
    assert view.e2c.lower == pytest.approx(E2C_LOWER, abs=1e-12)
    assert view.e2c.upper == pytest.approx(E2C_UPPER, abs=1e-12)
    assert view.e2c.includes_zero is False
    assert view.e2c.all_negative is True
    assert all(v < 0 for v in view.e2c.per_seed_values)
    assert view.e2c.critical_value == pytest.approx(3.182446305284263, abs=1e-12)


def test_e2d_four_matched_draws_exact() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert view.e2d.n_fleet_draws == 4
    assert view.e2d.fleet_seeds == (1, 2, 3, 4)
    assert view.e2d.replication_unit == "fleet_draw"
    assert view.e2d.degrees_of_freedom == 3
    assert view.e2d.method == "two-sided Student-t 95% interval over fleet-draw differences"
    assert view.e2d.per_seed_values == pytest.approx(E2D_PER_SEED, abs=1e-12)
    assert view.e2d.mean == pytest.approx(E2D_MEAN, abs=1e-12)
    assert view.e2d.lower == pytest.approx(E2D_LOWER, abs=1e-12)
    assert view.e2d.upper == pytest.approx(E2D_UPPER, abs=1e-12)
    assert view.e2d.includes_zero is False
    assert view.e2d.all_positive is True
    assert all(v > 0 for v in view.e2d.per_seed_values)


def test_e2d_vs_common_target_exact() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert view.e2d_vs_common_target.mean == pytest.approx(E2D_VS_DLA_MEAN, abs=1e-12)
    assert view.e2d_vs_common_target.lower == pytest.approx(E2D_VS_DLA_LOWER, abs=1e-12)
    assert view.e2d_vs_common_target.upper == pytest.approx(E2D_VS_DLA_UPPER, abs=1e-12)
    assert (
        view.e2d_vs_common_target.method
        == "two-sided Student-t 95% interval over fleet-draw differences"
    )
    assert view.e2d_vs_common_target.n_fleet_draws == 4
    assert view.e2d_vs_common_target.fleet_seeds == (1, 2, 3, 4)
    assert view.e2d_vs_common_target.includes_zero is False


def test_deterministic_mean_reconciliation_strict_tolerance() -> None:
    view = build_e2_comparison_view(_load_valid())
    calc_c = sum(view.e2c.per_seed_values) / len(view.e2c.per_seed_values)
    calc_d = sum(view.e2d.per_seed_values) / len(view.e2d.per_seed_values)
    assert abs(calc_c - view.e2c.mean) < DECLARED_MEAN_TOLERANCE
    assert abs(calc_d - view.e2d.mean) < DECLARED_MEAN_TOLERANCE
    assert view.e2c.lower < view.e2c.upper
    assert view.e2d.lower < view.e2d.upper


def test_direction_reversal_present() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert view.direction_reversal.reversed is True
    assert view.direction_reversal.e2c_direction == "negative"
    assert view.direction_reversal.e2d_direction == "positive"
    assert "common target per substep" in view.direction_reversal.statement
    assert "per-task" in view.direction_reversal.statement.lower()
    assert "Never claim universal superiority" in view.direction_reversal.statement
    assert view.e2c.mean < 0
    assert view.e2d.mean > 0


def test_per_task_vs_common_target_summary_present() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert "0.026493694591" in view.per_task_vs_common_target_summary
    assert "0.026210763951" in view.per_task_vs_common_target_summary
    assert "0.026776625232" in view.per_task_vs_common_target_summary
    assert "common-target" in view.per_task_vs_common_target_summary
    assert "per_task" in view.per_task_vs_common_target_summary.lower()


def test_replication_note_and_limitations() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert "fleet_draw" in view.replication_note
    assert "never statistical replications" in view.replication_note
    assert "Manchester incident hour" in view.limitations
    assert "evaluator_seed 0" in view.limitations
    assert "does not observe RSU load" in view.limitations


def test_no_pvalues_or_fake_million_n() -> None:
    view = build_e2_comparison_view(_load_valid())
    dumped = view.model_dump()
    assert "p_value" not in dumped
    assert "pvalue" not in dumped
    assert "p-value" not in json.dumps(dumped)
    assert view.e2c.n_fleet_draws == 4
    assert view.e2d.n_fleet_draws == 4
    assert view.e2b.n == 1
    raw = json.dumps(dumped)
    assert '"n": 13076234' not in raw
    assert '"n_fleet_draws": 13076234' not in raw


def test_typed_view_is_pydantic_and_frozen() -> None:
    view = build_e2_comparison_view(_load_valid())
    assert isinstance(view, E2ResearchComparisonView)
    with pytest.raises(Exception):  # noqa: B017
        view.e2b.off = 0.0  # type: ignore[misc]


def test_api_existence() -> None:
    from traffictwin.experiments import e2_comparison as mod

    assert hasattr(mod, "E2ResearchComparisonView")
    assert hasattr(mod, "build_e2_comparison_view")
    assert callable(mod.build_e2_comparison_view)


# ---------------------------------------------------------------------------
# Fail-closed: builder requires typed package, no fallback
# ---------------------------------------------------------------------------


def test_builder_requires_typed_package_no_optional() -> None:
    with pytest.raises(TypeError):
        build_e2_comparison_view()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        build_e2_comparison_view(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        build_e2_comparison_view({})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        build_e2_comparison_view("not a package")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Mutation killers — all must raise, never silently normalize
# ---------------------------------------------------------------------------


def test_kills_sign_reversal_e2c() -> None:
    pkg = _load_valid()
    # Flip sign of E2c per_seed and keep declared mean consistent — committed direction check kills it
    pkg.paired_differences[0].per_seed_values = [
        -v for v in pkg.paired_differences[0].per_seed_values
    ]
    # Also flip declared mean to keep internal reconciliation passing (tests committed direction)
    pkg.declared_summaries[0].mean = -pkg.declared_summaries[0].mean
    # CI must also flip sign to stay internally consistent; even if we fix CI, committed value check kills
    pkg.declared_summaries[0].lower = -pkg.declared_summaries[0].lower
    pkg.declared_summaries[0].upper = -pkg.declared_summaries[0].upper
    # Need to swap lower/upper after sign flip to keep ordering
    lo = pkg.declared_summaries[0].lower
    up = pkg.declared_summaries[0].upper
    if lo > up:
        pkg.declared_summaries[0].lower, pkg.declared_summaries[0].upper = up, lo
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_sign_reversal_e2d() -> None:
    pkg = _load_valid()
    pkg.paired_differences[1].per_seed_values = [
        -v for v in pkg.paired_differences[1].per_seed_values
    ]
    pkg.declared_summaries[1].mean = -pkg.declared_summaries[1].mean
    lo = -pkg.declared_summaries[1].lower
    up = -pkg.declared_summaries[1].upper
    # After flipping sign, lower/upper swap
    pkg.declared_summaries[1].lower = min(lo, up)
    pkg.declared_summaries[1].upper = max(lo, up)
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_draw() -> None:
    pkg = _load_valid()
    # Wrong fleet seeds — not [1,2,3,4]
    pkg.paired_differences[0].fleet_seeds = [0, 1, 2, 3]
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_draw_seed0_in_c_draws() -> None:
    pkg = _load_valid()
    pkg.paired_differences[1].fleet_seeds = [1, 2, 3, 5]
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_mean_and_ci_tight_tolerance() -> None:
    pkg = _load_valid()
    # Drift mean beyond 1e-12 — deterministic reconciliation must raise
    pkg.declared_summaries[0].mean += 1e-9
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_ci_bounds() -> None:
    pkg = _load_valid()
    pkg.declared_summaries[1].lower += 1e-9
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_replication_unit() -> None:
    pkg = _load_valid()
    object.__setattr__(pkg, "replication_unit", "fleet_draw_wrong")
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_replication_unit_task() -> None:
    pkg = _load_valid()
    object.__setattr__(pkg, "replication_unit", "task")
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_task_as_replicate() -> None:
    pkg = _load_valid()
    # Simulate task-as-replicate by claiming replication_unit task on paired diff
    pkg.paired_differences[0].replication_unit = "task"  # type: ignore[assignment]
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_task_as_replicate_via_large_n_hidden() -> None:
    pkg = _load_valid()
    # Builder must never produce large task N; view n_fleet_draws is fixed 4, so this checks builder doesn't accept task replication
    pkg.paired_differences[1].replication_unit = "task"  # type: ignore[assignment]
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_e2b_draw_standing() -> None:
    pkg = _load_valid()
    # E2b must be one-draw descriptive; mutate an E2b observation to wrong fleet_seed
    pkg.observations[0].fleet_seed = 1
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_e2b_draw_standing_interval() -> None:
    pkg = _load_valid()
    pkg.observations[0].standing = "INFERENCE"
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_e2b_value_drift() -> None:
    pkg = _load_valid()
    pkg.observations[0].value += 1e-6
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_secondary_summary_drift() -> None:
    pkg = _load_valid()
    pkg.declared_summaries[2].mean += 1e-9
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_secondary_summary_ci_drift() -> None:
    pkg = _load_valid()
    pkg.declared_summaries[2].lower += 1e-9
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_secondary_summary_fabricated_sd_se() -> None:
    pkg = _load_valid()
    pkg.declared_summaries[2].sample_sd = 0.0002
    pkg.declared_summaries[2].standard_error = 0.0001
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_identity() -> None:
    pkg = _load_valid()
    pkg.source_identities.actor.sha256 = "0" * 64
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_evaluator_seed() -> None:
    pkg = _load_valid()
    object.__setattr__(pkg, "evaluator_seed", 1)
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_kills_wrong_per_draw_value() -> None:
    pkg = _load_valid()
    # Wrong per-draw value not sign-reversed but offset
    vals = list(pkg.paired_differences[0].per_seed_values)
    vals[0] += 1e-6
    pkg.paired_differences[0].per_seed_values = vals
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg)


def test_declared_ci_method_preserved_not_swapped() -> None:
    pkg = _load_valid()
    # Correct method must be preserved; builder must not substitute another CI method
    assert (
        pkg.declared_summaries[0].method
        == "two-sided Student-t 95% interval over fleet-draw differences"
    )
    view = build_e2_comparison_view(pkg)
    assert view.e2c.method == "two-sided Student-t 95% interval over fleet-draw differences"
    assert view.e2d.method == "two-sided Student-t 95% interval over fleet-draw differences"
    assert (
        view.e2d_vs_common_target.method
        == "two-sided Student-t 95% interval over fleet-draw differences"
    )
    # Mutating method should fail closed
    pkg2 = _load_valid()
    pkg2.declared_summaries[0].method = "normal approximation 95%"
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg2)


def test_kills_wrong_seed_and_draw() -> None:
    pkg = _load_valid()
    view = build_e2_comparison_view(pkg)
    assert view.e2b.fleet_seed == 0
    assert view.e2c.fleet_seeds == (1, 2, 3, 4)
    assert view.e2d.fleet_seeds == (1, 2, 3, 4)
    assert 0 not in view.e2c.fleet_seeds
    assert view.e2c.n_fleet_draws == 4

    # Now mutate to include seed 0 — must raise
    pkg2 = _load_valid()
    pkg2.paired_differences[0].fleet_seeds = [0, 1, 2, 3]
    with pytest.raises((ValueError, Exception)):
        build_e2_comparison_view(pkg2)


def test_kills_task_as_replicate_view() -> None:
    pkg = _load_valid()
    view = build_e2_comparison_view(pkg)
    assert view.e2c.replication_unit == "fleet_draw"
    assert view.e2d.replication_unit == "fleet_draw"
    assert view.e2b.replication_unit == "fleet_draw"
    assert view.e2c.n_fleet_draws == 4
    assert view.e2d.n_fleet_draws == 4
    # Verify fleet-draw replication, not task count (avoid Literal comparison-overlap)
    dumped = view.model_dump()
    assert dumped["e2c"]["n_fleet_draws"] == 4
    assert dumped["e2d"]["n_fleet_draws"] == 4
    assert "13076234" not in json.dumps(dumped)


def test_kills_e2b_as_multidraw() -> None:
    pkg = _load_valid()
    view = build_e2_comparison_view(pkg)
    assert view.e2b.n == 1
    assert view.e2b.interval is None
    assert view.e2b.uncertainty == "one_draw_descriptive_no_interval"
    assert view.e2c.n_fleet_draws == 4
    assert view.e2b.n == 1
    assert view.e2c.n_fleet_draws == 4
    # Type-independent serialized check avoids Literal comparison-overlap
    dumped2 = view.model_dump()
    assert dumped2["e2b"]["n"] != dumped2["e2c"]["n_fleet_draws"]

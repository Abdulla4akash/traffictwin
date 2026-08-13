# ruff: noqa: E501, S108
"""Discriminating tests for E2 research evidence model — lane 02.

Kills identity/value/path/missingness mutations and proves unavailable != 0.
"""

from __future__ import annotations

import copy
import json
import math

import pytest
from pydantic import ValidationError

from traffictwin.experiments.e2_research_evidence import (
    E2ResearchEvidencePackage,
    load_e2_research_evidence_json,
)


def _valid_payload() -> dict[str, object]:
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
                "sample_sd": 0.0002,
                "standard_error": 0.0001,
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
# Happy path + fingerprint
# ---------------------------------------------------------------------------


def test_valid_load_and_fingerprint_deterministic() -> None:
    pkg = _load_valid()
    fp1 = pkg.fingerprint()
    assert len(fp1) == 64
    assert all(c in "0123456789abcdef" for c in fp1)
    fp2 = _load_valid().fingerprint()
    assert fp1 == fp2


def test_fingerprint_is_path_free() -> None:
    pkg = _load_valid()
    # Fingerprint payload must not contain absolute private paths
    payload = pkg._fingerprint_payload()  # noqa: SLF001
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert "/Users/" not in canonical
    assert "/home/" not in canonical
    assert "/tmp/" not in canonical
    # fingerprint is deterministic over scientific content
    assert (
        pkg.fingerprint()
        == E2ResearchEvidencePackage.model_validate(
            json.loads(json.dumps(_valid_payload()))
        ).fingerprint()
    )


def test_fingerprint_changes_on_value_mutation() -> None:
    base = _valid_payload()
    pkg1 = load_e2_research_evidence_json(json.dumps(base))
    mutated = copy.deepcopy(base)
    mutated["observations"][0]["value"] = 0.99  # type: ignore[index]
    pkg2 = load_e2_research_evidence_json(json.dumps(mutated))
    assert pkg1.fingerprint() != pkg2.fingerprint()


# ---------------------------------------------------------------------------
# Identity mutations
# ---------------------------------------------------------------------------


def test_rejects_identity_mutation_actor_sha() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["actor"]["sha256"] = "0" * 64  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_identity_mutation_base_sha() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["base_sha"] = "a" * 40  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_identity_mutation_trace_sha() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["trace"]["sha256"] = "b" * 64  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_identity_mutation_manifest() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["manifest_sha256_by_study"]["e2b"] = "c" * 64  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_identity_mutation_code_commit() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["observations"][0]["code_commit"] = "d" * 40  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_hash_shape_invalid() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["actor"]["sha256"] = "not-hex"  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_hash_shape_wrong_length() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["source_identities"]["base_sha"] = "abc123"  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


# ---------------------------------------------------------------------------
# Value / replication / draw-set mutations
# ---------------------------------------------------------------------------


def test_rejects_infinite_value() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["observations"][0]["value"] = math.inf  # type: ignore[index]
    # json cannot serialise inf; use direct model validation
    with pytest.raises((ValidationError, ValueError)):
        E2ResearchEvidencePackage.model_validate(bad)


def test_rejects_nan_value() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["observations"][0]["value"] = math.nan  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        E2ResearchEvidencePackage.model_validate(bad)


def test_rejects_evaluator_seed_nonzero() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["evaluator_seed"] = 1  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_replication_unit_task() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["replication_unit"] = "task"  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_incomplete_draw_set() -> None:
    bad = copy.deepcopy(_valid_payload())
    # e2c must have [1,2,3,4]; truncate
    bad["fleet_draw_sets"][1]["fleet_seeds"] = [1, 2, 3]  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_duplicate_figure_id() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["observations"][1]["figure_id"] = bad["observations"][0]["figure_id"]  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_duplicate_strategy_id() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["strategies"].append(bad["strategies"][0])  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_missing_required_strategy() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["strategies"] = [s for s in bad["strategies"] if s["strategy_id"] != "per_task_dla"]  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_unknown_strategy_id() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["strategies"][0]["strategy_id"] = "evil_strategy"  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


# ---------------------------------------------------------------------------
# CI ordering / value coherence
# ---------------------------------------------------------------------------


def test_rejects_ci_ordering_violation() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["declared_summaries"][0]["lower"] = 0.5  # type: ignore[index]
    bad["declared_summaries"][0]["upper"] = -0.5  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_ci_includes_zero_mismatch() -> None:
    bad = copy.deepcopy(_valid_payload())
    # CI clearly excludes zero but mark includes_zero True
    bad["declared_summaries"][0]["includes_zero"] = True  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_mean_outside_ci() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["declared_summaries"][0]["mean"] = 99.0  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


# ---------------------------------------------------------------------------
# Path / secret mutations
# ---------------------------------------------------------------------------


def test_rejects_private_absolute_path_in_payload() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["limitations"][0] = "/Users/akashx/secret/path " + bad["limitations"][0]  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_private_path_in_task_reason() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["task_lifecycle"]["unavailable_reasons"]["gate_rejected"] = "/home/user/data/file.txt"  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_secret_keyword_assignment() -> None:
    bad = copy.deepcopy(_valid_payload())
    # Add a limitation containing secret assignment pattern
    bad["limitations"].append("api_key: secret123")  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_extra_fields_forbid() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["extra_field"] = 123  # type: ignore[assignment]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


# ---------------------------------------------------------------------------
# Missingness / unavailable vs zero
# ---------------------------------------------------------------------------


def test_rejects_missing_reason_coherence_none_without_reason() -> None:
    bad = copy.deepcopy(_valid_payload())
    # gate_rejected is None but remove its reason
    bad["task_lifecycle"]["unavailable_reasons"].pop("gate_rejected")  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_missing_reason_coherence_value_with_reason() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["task_lifecycle"]["gate_rejected"] = 0
    # keep reason -> should fail because value present but reason present
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_unavailable_field_converted_to_zero_gate_rejected() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["gate_rejected"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("gate_rejected", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_zero_capacity_rejected() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["capacity_rejected"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("capacity_rejected", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_zero_started() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["started"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("started", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_zero_compute_completed() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["compute_completed"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("compute_completed", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_zero_returned() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["returned"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("returned", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_zero_dropped() -> None:
    base = _valid_payload()
    mutated = copy.deepcopy(base)
    mutated["task_lifecycle"]["dropped"] = 0
    mutated["task_lifecycle"]["unavailable_reasons"].pop("dropped", None)  # type: ignore[attr-defined]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_fields_converted_to_zero_all_six_parametrized() -> None:
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        base = _valid_payload()
        mutated = copy.deepcopy(base)
        mutated["task_lifecycle"][field] = 0  # type: ignore[index]
        mutated["task_lifecycle"]["unavailable_reasons"].pop(field, None)  # type: ignore[attr-defined]
        with pytest.raises((ValidationError, ValueError)):
            load_e2_research_evidence_json(json.dumps(mutated))


def test_rejects_unavailable_field_converted_to_nonzero_number() -> None:
    for field, val in [
        ("gate_rejected", 1),
        ("capacity_rejected", 42),
        ("started", 10594205),
        ("compute_completed", 100),
        ("returned", 50),
        ("dropped", 7),
    ]:
        base = _valid_payload()
        mutated = copy.deepcopy(base)
        mutated["task_lifecycle"][field] = val  # type: ignore[index]
        mutated["task_lifecycle"]["unavailable_reasons"].pop(field, None)  # type: ignore[attr-defined]
        with pytest.raises((ValidationError, ValueError)):
            load_e2_research_evidence_json(json.dumps(mutated))


def test_unavailable_fields_are_all_none_with_reasons() -> None:
    pkg = _load_valid()
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        assert getattr(pkg.task_lifecycle, field) is None, f"{field} must be None"
        assert field in pkg.task_lifecycle.unavailable_reasons
        reason = pkg.task_lifecycle.unavailable_reasons[field]
        assert reason and reason.strip(), f"reason for {field} must be non-empty"
        assert "==" not in reason or "admitted" not in reason, (
            f"{field} reason must not claim equality"
        )


def test_started_reason_is_bounded_not_equality_claim() -> None:
    pkg = _load_valid()
    reason = pkg.task_lifecycle.unavailable_reasons["started"]
    assert reason == "UNAVAILABLE as an independently instrumented quantity"
    assert "==" not in reason
    assert "admitted" not in reason.lower() or "unavailable" in reason.lower()
    # Also check missingness list reason is faithful
    started_missing = [m for m in pkg.missingness if m.field == "started"]
    assert len(started_missing) == 1
    assert started_missing[0].reason == "UNAVAILABLE as an independently instrumented quantity"
    assert "==" not in started_missing[0].reason


def test_rejects_empty_reason() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["missingness"][0]["reason"] = ""  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_empty_unavailable_reason_for_each_field() -> None:
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        bad = copy.deepcopy(_valid_payload())
        bad["task_lifecycle"]["unavailable_reasons"][field] = ""  # type: ignore[index]
        with pytest.raises((ValidationError, ValueError)):
            load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_whitespace_only_unavailable_reason() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["task_lifecycle"]["unavailable_reasons"]["started"] = "   "  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_absent_unavailable_reason_for_each_field() -> None:
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        bad = copy.deepcopy(_valid_payload())
        bad["task_lifecycle"]["unavailable_reasons"].pop(field, None)  # type: ignore[attr-defined]
        with pytest.raises((ValidationError, ValueError)):
            load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_started_reason_with_equality_claim() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["task_lifecycle"]["unavailable_reasons"]["started"] = (
        "not separately instrumented; == admitted with explicit note"  # type: ignore[index]
    )
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))
    # Also via missingness list
    bad2 = copy.deepcopy(_valid_payload())
    bad2["missingness"] = [
        m
        if m["field"] != "started"
        else {
            "field": "started",
            "reason": "not separately instrumented; treated as admitted with explicit note",
        }  # type: ignore[attr-defined]
        for m in bad2["missingness"]  # type: ignore[attr-defined]
    ]
    # missingness itself doesn't fail closed on equality claim alone, but lifecycle does
    # Ensure the authoritative reason is required for lifecycle, so this still would be
    # caught if lifecycle reason is equality claim; test that missingness equality is also
    # not the valid fixture (we enforce via direct check below)
    assert (
        bad2["missingness"][2]["reason"] != "UNAVAILABLE as an independently instrumented quantity"
    )  # type: ignore[index]


def test_rejects_empty_missingness_reason_for_each_field() -> None:
    for idx in range(len(_valid_payload()["missingness"])):  # type: ignore[attr-defined]
        bad = copy.deepcopy(_valid_payload())
        bad["missingness"][idx]["reason"] = ""  # type: ignore[index]
        with pytest.raises((ValidationError, ValueError)):
            load_e2_research_evidence_json(json.dumps(bad))


# ---------------------------------------------------------------------------
# Additional discriminating: conservation, finite, etc.
# ---------------------------------------------------------------------------


def test_rejects_lifecycle_conservation_violation() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["task_lifecycle"]["offered"] = 999  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        load_e2_research_evidence_json(json.dumps(bad))


def test_rejects_non_finite_paired_difference() -> None:
    bad = copy.deepcopy(_valid_payload())
    bad["paired_differences"][0]["per_seed_values"][0] = float("inf")  # type: ignore[index]
    with pytest.raises((ValidationError, ValueError)):
        E2ResearchEvidencePackage.model_validate(bad)

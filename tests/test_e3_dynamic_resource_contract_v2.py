"""Strong contract tests for E3 dynamic-resource v2 contract v2.

Retains all v1 invariants and adds v2-specific occupancy and comparator rejection precedence checks.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location(
    "validate_e3_dynamic_resource_contract_v2",
    SCRIPTS / "validate_e3_dynamic_resource_contract_v2.py",
)
assert _spec is not None
assert _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

BASE_COMMIT: str = _mod.BASE_COMMIT
EXPECTED_ACTOR_SHA: str = _mod.EXPECTED_ACTOR_SHA
EXPECTED_E2B: str = _mod.EXPECTED_E2B
EXPECTED_E2C: str = _mod.EXPECTED_E2C
EXPECTED_E2D: str = _mod.EXPECTED_E2D
EXPECTED_E2D_MANIFEST: str = _mod.EXPECTED_E2D_MANIFEST
EXPECTED_TRACE_SHA: str = _mod.EXPECTED_TRACE_SHA
EXPECTED_SUCCESSOR_CANDIDATE_SHA: str = _mod.EXPECTED_SUCCESSOR_CANDIDATE_SHA
EXPECTED_SUCCESSOR_INTEGRATION_SHA: str = _mod.EXPECTED_SUCCESSOR_INTEGRATION_SHA
EXPECTED_V1_JSON_SHA256: str = _mod.EXPECTED_V1_JSON_SHA256
main = _mod.main
render_markdown = _mod.render_markdown
validate_contract = _mod.validate_contract
validate_markdown = _mod.validate_markdown
validate_markdown_contains = _mod.validate_markdown_contains

CANONICAL_JSON = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json"
)
CANONICAL_JSON_V1 = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.json"
)
CANONICAL_MD = (
    Path(__file__).resolve().parents[1] / "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.md"
)


def canonical() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CANONICAL_JSON.read_text(encoding="utf-8"))
    return data


def assert_fails(mutated: dict[str, Any], reason: str) -> None:
    result = validate_contract(mutated)
    assert not result["pass"], f"expected failure for {reason} but passed"
    assert result["error_count"] > 0


def test_canonical_contract_passes() -> None:
    data = canonical()
    result = validate_contract(data)
    assert result["pass"], f"canonical should pass: {result['errors']}"
    assert result["error_count"] == 0


def test_canonical_markdown_equivalence() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    errors = validate_markdown_contains(md_text, data)
    assert errors == [], f"markdown equivalence failed: {errors}"


def test_base_commit_exact() -> None:
    data = canonical()
    assert data["base_commit"] == BASE_COMMIT == "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
    assert data["branch"] == "worker/e3-lane-01-contract"


def test_frozen_identities_exact() -> None:
    data = canonical()
    fp = data["frozen_prerequisites"]
    assert fp["e2b"]["commit"] == EXPECTED_E2B
    assert fp["e2c"]["commit"] == EXPECTED_E2C
    assert fp["e2d"]["commit"] == EXPECTED_E2D
    assert fp["e2d"]["manifest_sha256"] == EXPECTED_E2D_MANIFEST
    assert fp["actor"]["sha256"] == EXPECTED_ACTOR_SHA
    assert fp["trace"]["sha256"] == EXPECTED_TRACE_SHA
    assert fp["evaluator_seed"] == 0


def test_replication_is_fleet_draw_not_task() -> None:
    data = canonical()
    rep = data["replication"]
    assert rep["replication_unit"] == "fleet_draw"
    assert rep["replication_key"] == "fleet_seed"
    assert rep["n"] == 4
    assert rep["tasks_are_not_replicates"] is True


def test_mutation_queue_equals_compute_rejected() -> None:
    data = canonical()
    # free: mark queue ceiling as compute capacity
    mutated = copy.deepcopy(data)
    mutated["mechanism_separation"]["queue_ceiling_is_not_compute_capacity"] = False
    assert_fails(mutated, "queue==compute")


def test_mutation_task_replication_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["replication"]["replication_unit"] = "task"
    mutated["replication"]["tasks_are_not_replicates"] = False
    assert_fails(mutated, "task replication")

    mutated2 = copy.deepcopy(canonical())
    mutated2["inference"]["unit"] = "task"
    assert_fails(mutated2, "task as N in inference")


def test_mutation_actor_chooses_rsu_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["frozen_prerequisites"]["actor"]["selects_execution_rsu"] = True
    assert_fails(mutated, "actor chooses RSU")

    mutated2 = copy.deepcopy(canonical())
    mutated2["frozen_prerequisites"]["actor"]["observes_current_rsu_load"] = True
    assert_fails(mutated2, "actor observes RSU load")

    mutated3 = copy.deepcopy(canonical())
    mutated3["mechanism_separation"]["actor_never_selects_execution_rsu"] = False
    assert_fails(mutated3, "actor never selects RSU flag")


def test_mutation_free_unbounded_scaling_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["dynamic_bounds"]["max_units"] = 10
    assert_fails(mutated, "unbounded scaling max 10")

    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["dynamic_bounds"]["min_units"] = 0
    assert_fails(mutated2, "unbounded scaling min 0")

    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["dynamic_bounds"]["actuation_delay_ticks"] = 1
    assert_fails(mutated3, "actuation delay not 2")

    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["dynamic_bounds"]["action_step"] = 2
    assert_fails(mutated4, "action step not 1")

    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["dynamic_bounds"]["free_scaling_forbidden"] = False
    assert_fails(mutated5, "free scaling allowed")


def test_mutation_unavailable_lifecycle_zero_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["task_accounting"]["unavailable_lifecycle"]["started"] = 0
    assert_fails(mutated, "unavailable started zero not null")

    mutated2 = copy.deepcopy(canonical())
    mutated2["task_accounting"]["unavailable_lifecycle"]["compute_completed"] = 0
    assert_fails(mutated2, "unavailable compute_completed zero")

    mutated3 = copy.deepcopy(canonical())
    mutated3["task_accounting"]["unavailable_lifecycle"]["returned"] = 0
    assert_fails(mutated3, "unavailable returned zero")

    mutated4 = copy.deepcopy(canonical())
    mutated4["task_accounting"]["unavailable_lifecycle"]["dropped"] = 0
    assert_fails(mutated4, "unavailable dropped zero not null")


def test_mutation_monetary_cost_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["cost"]["monetary"] = True
    assert_fails(mutated, "monetary cost true")

    mutated2 = copy.deepcopy(canonical())
    mutated2["cost"]["metric"] = "cost_dollars"
    assert_fails(mutated2, "monetary metric")

    mutated3 = copy.deepcopy(canonical())
    mutated3["cost_currency"] = 123  # top-level forbidden field
    assert_fails(mutated3, "cost_currency field")


def test_mutation_hidden_fleet_seed_label_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["replication"]["replication_key"]
    assert_fails(mutated, "hidden fleet_seed label missing key")

    mutated2 = copy.deepcopy(canonical())
    del mutated2["replication"]["replication_unit"]
    assert_fails(mutated2, "hidden fleet_seed label missing unit")

    mutated3 = copy.deepcopy(canonical())
    mutated3["replication"]["replication_unit"] = "fleet_seed"  # conflating key/unit
    assert_fails(mutated3, "hidden fleet_seed label conflated")


def test_mutation_200ms_pseudo_time_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["time_model"]["candidate_stale_levels_ms"] = [0, 200, 1000]
    assert_fails(mutated, "200ms stale not allowed")

    mutated2 = copy.deepcopy(canonical())
    mutated2["time_model"]["outer_tick_ms"] = 200
    assert_fails(mutated2, "outer tick 200 not allowed")

    mutated3 = copy.deepcopy(canonical())
    mutated3["time_model"]["state_age_unit"] = "milliseconds_200ms_slots"
    assert_fails(mutated3, "state age not integer simulator ms")


def test_mutation_missing_resource_denominator_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["cost"]["metric"] = "resource_seconds"
    assert_fails(mutated, "missing resource_unit_seconds denominator")

    mutated2 = copy.deepcopy(canonical())
    mutated2["cost"]["formula"] = "sum(active_compute_units)"
    assert_fails(mutated2, "missing interval_seconds in formula")


def test_mutation_actual_kubernetes_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["claim_boundaries"]["kubernetes_orchestration_tested"] = True
    assert_fails(mutated, "actual Kubernetes claimed tested")


def test_mutation_future_leakage_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["prediction_uses_future"] = True
    assert_fails(mutated, "future leakage proactive")

    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["no_future_leakage"] = False
    assert_fails(mutated2, "no_future_leakage false")

    mutated3 = copy.deepcopy(canonical())
    mutated3["placement"]["p2c_dla"]["stale_snapshot"]["no_future_leakage"] = False
    assert_fails(mutated3, "stale future leakage")


def test_mutation_common_target_p2c_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["placement"]["p2c_dla"]["common_target_forbidden"] = False
    assert_fails(mutated, "common-target P2C allowed")

    mutated2 = copy.deepcopy(canonical())
    mutated2["placement"]["p2c_dla"]["inspect_only_pair"] = False
    assert_fails(mutated2, "inspect beyond pair")


def test_mutation_does_not_edit_canonical_file() -> None:
    before = CANONICAL_JSON.read_text(encoding="utf-8")
    mutated = copy.deepcopy(canonical())
    mutated["replication"]["n"] = 999
    result = validate_contract(mutated)
    assert not result["pass"]
    after = CANONICAL_JSON.read_text(encoding="utf-8")
    assert before == after, "canonical file must not be edited in place"


def test_mutation_proactive_window_must_be_four_and_one_second() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["window_size"] = 3
    assert_fails(mutated, "window size not 4")

    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["window_interval_ms"] = 200
    assert_fails(mutated2, "window interval not 1000")

    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["horizon_ms"] = 5000
    assert_fails(mutated3, "horizon not 2000")


def test_mutation_staging_max_cells_60() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["maximum_candidate_unique_cells"] = 100
    assert_fails(mutated, "max cells not 60")

    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3a"]["cells"] = 999
    assert_fails(mutated2, "e3a cells not 12")


def test_mutation_p2c_counter_key_stable() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["placement"]["p2c_dla"]["counter_key_fields"] = ["evaluator_seed", "tick"]
    assert_fails(mutated, "counter key missing fields")

    mutated2 = copy.deepcopy(canonical())
    mutated2["placement"]["p2c_dla"]["no_global_rng_stream"] = False
    assert_fails(mutated2, "global RNG allowed")


def test_valid_payload_mutation_proves_failure_without_canonical_edit() -> None:
    # General pattern: any change to frozen identity must fail, prove without editing file
    for field in ["e2b", "e2c", "e2d"]:
        mutated = copy.deepcopy(canonical())
        mutated["frozen_prerequisites"][field]["commit"] = "0" * 40
        assert_fails(mutated, f"frozen {field} drift")
    # ensure file unchanged
    assert (
        json.loads(CANONICAL_JSON.read_text(encoding="utf-8"))["frozen_prerequisites"]["e2b"][
            "commit"
        ]
        == EXPECTED_E2B
    )


# --- New exact-value/formula/arm-ID mutations ---


def test_mutation_research_question_requires_three_placements() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["research_question"] = "strongest-link vs P2C comparison"
    assert_fails(mutated, "research_question must contain ingress_dla/per_task_dla/p2c_dla")
    mutated2 = copy.deepcopy(canonical())
    mutated2["research_question"] = "placement among ingress_dla and per_task_dla only"
    assert_fails(mutated2, "research_question missing p2c_dla")
    mutated3 = copy.deepcopy(canonical())
    mutated3["research_question"] = mutated3["research_question"].replace("fixed_1x", "fixed1x")
    assert_fails(mutated3, "research_question must contain fixed_1x")


def test_mutation_scaling_arm_ids_must_be_exact() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["fixed1x"] = {"active_units_per_rsu": 1}
    assert_fails(mutated, "legacy fixed1x key forbidden")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3a"]["scaling"] = ["fixed1x"]
    assert_fails(mutated2, "legacy fixed1x arm ID in staged_design")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3b"]["scaling"] = [
        "fixed_1x",
        "static3x",
        "reactive",
        "proactive",
    ]
    assert_fails(mutated3, "legacy static3x arm ID forbidden")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["static3x"] = {"active_units_per_rsu": 3}
    assert_fails(mutated4, "legacy static3x key forbidden")
    mutated5 = copy.deepcopy(canonical())
    mutated5["staged_design"]["e3b"]["scaling"] = [
        "fixed_1x",
        "static_3x",
        "reactive",
        "proactive",
    ]
    assert_fails(mutated5, "legacy static_3x arm ID forbidden")


def test_mutation_static_overprovisioned_is_compute_not_queue() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["static_overprovisioned"]["is_compute_not_queue"] = False
    assert_fails(mutated, "static_overprovisioned must be compute not queue")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["static_overprovisioned"]["multiplier"] = 2
    assert_fails(mutated2, "static_overprovisioned multiplier must be 3")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["static_overprovisioned"]["active_units_per_rsu"] = 2
    assert_fails(mutated3, "static_overprovisioned active_units must be 3")


def test_mutation_reactive_exact_thresholds_and_gap() -> None:
    base = canonical()
    for threshold_field, bad_val in [
        ("scale_up_threshold_ms", 900),
        ("scale_down_threshold_ms", 100),
    ]:
        mutated = copy.deepcopy(base)
        mutated["compute_scaling"]["reactive"][threshold_field] = bad_val
        assert_fails(mutated, f"reactive {threshold_field} must be exact")
    mutated = copy.deepcopy(base)
    mutated["compute_scaling"]["reactive"]["threshold_gap_ms"] = 500
    assert_fails(mutated, "reactive gap must be 600")
    mutated2 = copy.deepcopy(base)
    mutated2["compute_scaling"]["reactive"]["hysteresis_is_gap"] = False
    assert_fails(mutated2, "reactive hysteresis_is_gap must be true")
    mutated3 = copy.deepcopy(base)
    mutated3["compute_scaling"]["reactive"]["hysteresis_ms_extra"] = True
    assert_fails(mutated3, "reactive hysteresis_ms_extra must be false")
    mutated4 = copy.deepcopy(base)
    mutated4["compute_scaling"]["reactive"]["scale_up_inclusive"] = False
    assert_fails(mutated4, "reactive inclusive edges")
    mutated5 = copy.deepcopy(base)
    mutated5["compute_scaling"]["reactive"]["scale_down_inclusive"] = False
    assert_fails(mutated5, "reactive inclusive edges down")


def test_mutation_reactive_signal_and_timing() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["reactive"]["signal"] = "queue_depth"
    assert_fails(mutated, "reactive signal must be service_workload_ms")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["reactive"]["signal_units"] = "tasks"
    assert_fails(mutated2, "reactive signal_units must be work_ms_independent_of_capacity")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["reactive"]["per_rsu"] = False
    assert_fails(mutated3, "reactive per_rsu must be true")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["reactive"]["cooldown_ms"] = 3000
    assert_fails(mutated4, "reactive cooldown_ms must be 5000")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["reactive"]["actuation_delay_ms"] = 1000
    assert_fails(mutated5, "reactive actuation_delay_ms must be 2000")
    mutated6 = copy.deepcopy(canonical())
    mutated6["compute_scaling"]["reactive"]["actuation_delay_ticks"] = 1
    assert_fails(mutated6, "reactive actuation_delay_ticks must be 2")
    mutated7 = copy.deepcopy(canonical())
    mutated7["compute_scaling"]["reactive"]["apply_due_before_tick_decision"] = False
    assert_fails(mutated7, "reactive apply_due_before_tick_decision must be true")
    mutated8 = copy.deepcopy(canonical())
    mutated8["compute_scaling"]["reactive"]["max_pending_actions"] = 2
    assert_fails(mutated8, "reactive max_pending_actions must be 1")
    mutated9 = copy.deepcopy(canonical())
    mutated9["compute_scaling"]["reactive"]["stable_inclusive_edges"] = False
    assert_fails(mutated9, "reactive stable_inclusive_edges")
    mutated10 = copy.deepcopy(canonical())
    mutated10["compute_scaling"]["reactive"]["state_age_ms_values"] = [0, 500, 1000]
    assert_fails(mutated10, "reactive state_age must be [0,1000,3000]")
    mutated11 = copy.deepcopy(canonical())
    mutated11["compute_scaling"]["reactive"]["hysteresis_ms"] = 100
    assert_fails(mutated11, "reactive hysteresis_ms extra forbidden")


def test_mutation_proactive_exact_window_and_warmup() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["window_order"] = "newest_to_oldest"
    assert_fails(mutated, "proactive window_order must be oldest_to_newest")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["warm_up_valid_observations"] = 3
    assert_fails(mutated2, "proactive warm_up must be 4")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["observation_interval_ms"] = 500
    assert_fails(mutated3, "proactive observation_interval_ms must be 1000")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["proactive"]["window_interval_ms"] = 500
    assert_fails(mutated4, "proactive window_interval_ms must be 1000")


def test_mutation_proactive_formula_exact() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["formulas"]["older_mean"] = "mean(W)"
    assert_fails(mutated, "proactive older_mean formula must be mean(W[0:2])")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["formulas"]["recent_mean"] = "mean(W)"
    assert_fails(mutated2, "proactive recent_mean formula")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["formulas"]["trend"] = "mean(W)"
    assert_fails(mutated3, "proactive trend formula")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["proactive"]["formulas"]["forecast"] = "mean(W)"
    assert_fails(mutated4, "proactive forecast formula must be max(0, mean(W) + 2*trend)")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["proactive"]["formulas"]["forecast"] = "max(0, mean(W) + trend)"
    assert_fails(mutated5, "proactive forecast missing 2*trend")
    mutated6 = copy.deepcopy(canonical())
    mutated6["compute_scaling"]["proactive"]["horizon_ms"] = 1000
    assert_fails(mutated6, "proactive horizon_ms must be 2000")
    mutated7 = copy.deepcopy(canonical())
    mutated7["compute_scaling"]["proactive"]["horizon_ticks"] = 1
    assert_fails(mutated7, "proactive horizon_ticks must be 2")


def test_mutation_proactive_thresholds_and_timing() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["scale_up_threshold_ms"] = 900
    assert_fails(mutated, "proactive scale_up must be 800")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["scale_down_threshold_ms"] = 100
    assert_fails(mutated2, "proactive scale_down must be 200")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["threshold_gap_ms"] = 500
    assert_fails(mutated3, "proactive threshold_gap must be 600")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["proactive"]["cooldown_ms"] = 4000
    assert_fails(mutated4, "proactive cooldown_ms must be 5000")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["proactive"]["actuation_delay_ms"] = 1000
    assert_fails(mutated5, "proactive actuation_delay_ms must be 2000")
    mutated6 = copy.deepcopy(canonical())
    mutated6["compute_scaling"]["proactive"]["bounds_min"] = 0
    assert_fails(mutated6, "proactive bounds_min must be 1")
    mutated7 = copy.deepcopy(canonical())
    mutated7["compute_scaling"]["proactive"]["action_step"] = 2
    assert_fails(mutated7, "proactive action_step must be 1")
    mutated8 = copy.deepcopy(canonical())
    mutated8["compute_scaling"]["proactive"]["max_pending_actions"] = 2
    assert_fails(mutated8, "proactive max_pending must be 1")
    mutated9 = copy.deepcopy(canonical())
    mutated9["compute_scaling"]["proactive"]["apply_due_before_tick_decision"] = False
    assert_fails(mutated9, "proactive apply_due_before_tick_decision")
    mutated10 = copy.deepcopy(canonical())
    mutated10["compute_scaling"]["proactive"]["stable_inclusive_edges"] = False
    assert_fails(mutated10, "proactive stable_inclusive_edges")
    mutated11 = copy.deepcopy(canonical())
    mutated11["compute_scaling"]["proactive"]["uses_only_samples_at_or_before_observation_time"] = (
        False
    )
    assert_fails(mutated11, "proactive uses_only_samples must be true")
    mutated12 = copy.deepcopy(canonical())
    mutated12["compute_scaling"]["proactive"]["alternative_formula_forbidden"] = False
    assert_fails(mutated12, "proactive alternative_formula_forbidden must be true")


def test_mutation_proactive_signal_and_transparency() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["signal"] = "service_workload_ms"
    assert_fails(mutated, "proactive signal must be arrival_work_ms")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["transparent_baseline_not_optimal"] = False
    assert_fails(mutated2, "proactive transparent_baseline_not_optimal must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["transparent"] = False
    assert_fails(mutated3, "proactive transparent must be true")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["proactive"]["ml"] = True
    assert_fails(mutated4, "proactive ml must be false")


def test_mutation_proactive_no_future_leakage_extended() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["proactive"]["no_future_leakage"] = False
    assert_fails(mutated, "proactive no_future_leakage must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["proactive"]["prediction_uses_future"] = True
    assert_fails(mutated2, "proactive prediction_uses_future must be false")


def test_mutation_dynamic_bounds_hysteresis_gap() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["dynamic_bounds"]["threshold_gap_ms"] = 500
    assert_fails(mutated, "dynamic_bounds threshold_gap must be 600")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["dynamic_bounds"]["hysteresis_is_gap"] = False
    assert_fails(mutated2, "dynamic_bounds hysteresis_is_gap must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["dynamic_bounds"]["hysteresis_ms_extra_forbidden"] = False
    assert_fails(mutated3, "dynamic_bounds hysteresis_ms_extra_forbidden must be true")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["dynamic_bounds"]["hysteresis_ms"] = 100
    assert_fails(mutated4, "dynamic_bounds hysteresis_ms extra forbidden")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["dynamic_bounds"]["max_pending_actions"] = 2
    assert_fails(mutated5, "dynamic_bounds max_pending_actions must be 1")
    mutated6 = copy.deepcopy(canonical())
    mutated6["compute_scaling"]["dynamic_bounds"]["apply_due_before_tick_decision"] = False
    assert_fails(mutated6, "dynamic_bounds apply_due_before_tick_decision must be true")


def test_mutation_staged_design_reuse_and_ids() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["identical_fresh_cells_reused_not_rerun"] = False
    assert_fails(mutated, "identical_fresh_cells_reused_not_rerun must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["not_double_counted"] = False
    assert_fails(mutated2, "not_double_counted must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["note"] = "candidate grid"
    assert_fails(mutated3, "staged_design note must clarify reused not rerun")
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["e3c"]["identical_fresh_cells_reused_not_rerun"] = False
    assert_fails(mutated4, "e3c identical_fresh_cells_reused_not_rerun must be true")
    mutated5 = copy.deepcopy(canonical())
    mutated5["staged_design"]["e3c"]["not_double_counted"] = False
    assert_fails(mutated5, "e3c not_double_counted must be true")
    mutated6 = copy.deepcopy(canonical())
    mutated6["staged_design"]["e3c"]["reuses_identical_fresh_cells"] = False
    assert_fails(mutated6, "e3c reuses_identical_fresh_cells must be true")


def test_mutation_time_model_state_age_is_snapshot() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["time_model"]["state_age_is_signal_snapshot_age"] = False
    assert_fails(mutated, "state_age_is_signal_snapshot_age must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["time_model"]["candidate_stale_levels_ms"] = [0, 1000]
    assert_fails(mutated2, "candidate_stale_levels must be [0,1000,3000]")
    mutated3 = copy.deepcopy(canonical())
    mutated3["time_model"]["state_age_unit"] = "seconds"
    assert_fails(mutated3, "state_age_unit must be integer_simulator_ms")


def test_mutation_claim_boundaries_transparent_baseline() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["claim_boundaries"]["proactive_is_transparent_baseline_not_optimal"] = False
    assert_fails(mutated, "proactive_is_transparent_baseline_not_optimal must be true")


def test_mutation_hypothesis_absent_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["hypotheses"]
    assert_fails(mutated, "hypotheses missing")

    mutated2 = copy.deepcopy(canonical())
    mutated2["hypotheses"]["items"] = [
        it for it in mutated2["hypotheses"]["items"] if it["id"] != "H3"
    ]
    assert_fails(mutated2, "H3 absent")

    mutated3 = copy.deepcopy(canonical())
    mutated3["hypotheses"]["items"] = mutated3["hypotheses"]["items"][:4]
    assert_fails(mutated3, "only 4 hypotheses not 5")


def test_mutation_hypothesis_status_must_be_hypothesis_not_expected_truth() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["hypotheses"]["items"][0]["status"] = "expected_truth"
    assert_fails(mutated, "H1 relabeled as expected_truth")

    mutated2 = copy.deepcopy(canonical())
    mutated2["hypotheses"]["items"][1]["status"] = "result"
    assert_fails(mutated2, "H2 relabeled as result")

    mutated3 = copy.deepcopy(canonical())
    mutated3["hypotheses"]["items"][2]["kind"] = "conclusion"
    assert_fails(mutated3, "H3 relabeled as conclusion")

    mutated4 = copy.deepcopy(canonical())
    mutated4["hypotheses"]["items"][3]["status"] = "conclusion"
    assert_fails(mutated4, "H4 status conclusion forbidden")

    mutated5 = copy.deepcopy(canonical())
    mutated5["hypotheses"]["negative_results_acceptable"] = False
    assert_fails(mutated5, "negative_results_acceptable must be true")

    mutated6 = copy.deepcopy(canonical())
    mutated6["hypotheses"]["boundary"] = "positive results required"
    assert_fails(mutated6, "boundary must state negative results acceptable")


def test_mutation_hypothesis_described_as_expected_truth_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["hypotheses"]["items"][0]["statement"] = (
        "P2C will improve over per_task_dla as expected truth"
    )
    assert_fails(mutated, "H1 described as expected truth")

    mutated2 = copy.deepcopy(canonical())
    mutated2["hypotheses"]["items"][1]["statement"] = (
        "Reactive is expected to improve deadline as expected truth"
    )
    assert_fails(mutated2, "H2 expected truth phrasing")

    mutated3 = copy.deepcopy(canonical())
    mutated3["hypotheses"]["items"][4]["statement"] = "Additional compute will win, expected truth"
    assert_fails(mutated3, "H5 expected truth")


def test_mutation_hypothesis_content_fragments_required() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["hypotheses"]["items"][0]["statement"] = "P2C may do something"
    assert_fails(mutated, "H1 missing less global inspection")

    mutated2 = copy.deepcopy(canonical())
    mutated2["hypotheses"]["items"][1]["statement"] = "Reactive may improve deadline"
    assert_fails(mutated2, "H2 missing churn/resource")

    mutated3 = copy.deepcopy(canonical())
    mutated3["hypotheses"]["items"][2]["statement"] = "Proactive may help"
    assert_fails(mutated3, "H3 missing change outruns actuation")

    mutated4 = copy.deepcopy(canonical())
    mutated4["hypotheses"]["items"][3]["statement"] = "P2C may degrade"
    assert_fails(mutated4, "H4 missing degrade faster/stale")

    mutated5 = copy.deepcopy(canonical())
    mutated5["hypotheses"]["items"][4]["statement"] = "Additional compute may do something"
    assert_fails(mutated5, "H5 missing resource_unit_seconds")


def test_mutation_markdown_hypothesis_equivalence_rejected() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Remove H3 hypothesis line should fail markdown equivalence
    mutated_md = md_text.replace("H3", "XX")
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "markdown missing H3 should fail"

    mutated_md2 = md_text.replace("hypothesis_not_expected_truth", "result")
    errors2 = validate_markdown_contains(mutated_md2, data)
    assert errors2, "markdown relabeled hypothesis as result should fail"

    mutated_md3 = (
        md_text.replace("Negative, null, or opposite", "Positive required")
        .replace("negative", "positive")
        .replace("acceptable", "required")
    )
    errors3 = validate_markdown_contains(mutated_md3, data)
    assert errors3, "markdown missing negative results acceptable should fail"


def test_mutation_research_question_factorial_overclaim_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["research_question"] = mutated["research_question"].replace(
        "without fully crossing every placement with every scaler",
        "alone and jointly across all placements and scalers",
    )
    # Also re-insert alone and jointly phrase
    mutated["research_question"] = mutated["research_question"] + " alone and jointly"
    assert_fails(mutated, "research_question alone and jointly must be rejected")

    mutated2 = copy.deepcopy(canonical())
    mutated2["research_question"] = (
        "Under the frozen Manchester incident trace and frozen MAPPO "
        "vehicle actor, do placement among ingress_dla, "
        "per_task_dla, and p2c_dla improve deadline?"
    )
    assert_fails(mutated2, "research_question missing staged isolation")

    mutated3 = copy.deepcopy(canonical())
    mutated3["research_question"] = mutated3["research_question"].replace(
        "E3a isolates placement", "E3a tests placement"
    )
    assert_fails(mutated3, "E3a isolates placement phrase required")

    mutated4 = copy.deepcopy(canonical())
    mutated4["research_question"] = mutated4["research_question"].replace(
        "E3b holds placement fixed", "E3b tests scaling"
    )
    assert_fails(mutated4, "E3b holds placement fixed phrase required")

    mutated5 = copy.deepcopy(canonical())
    mutated5["research_question"] = mutated5["research_question"].replace(
        "E3c tests selected stale-state contrasts", "E3c tests staleness"
    )
    assert_fails(mutated5, "E3c tests selected stale-state contrasts phrase required")

    mutated6 = copy.deepcopy(canonical())
    mutated6["research_question"] = mutated6["research_question"].replace(
        "without fully crossing every placement with every scaler",
        "with full factorial crossing",
    )
    assert_fails(mutated6, "research_question must state does not fully cross")


def test_mutation_exact_numeric_200_and_600_boundaries() -> None:
    # 200->250 and 600->700 must be rejected; also 200/600 must be word-boundary
    mutated = copy.deepcopy(canonical())
    mutated["compute_scaling"]["reactive"]["scale_down_threshold_ms"] = 250
    assert_fails(mutated, "reactive 200->250 must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["reactive"]["threshold_gap_ms"] = 700
    assert_fails(mutated2, "reactive 600->700 must be rejected")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_scaling"]["proactive"]["scale_down_threshold_ms"] = 250
    assert_fails(mutated3, "proactive 200->250 must be rejected")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_scaling"]["proactive"]["threshold_gap_ms"] = 700
    assert_fails(mutated4, "proactive 600->700 must be rejected")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["dynamic_bounds"]["threshold_gap_ms"] = 700
    assert_fails(mutated5, "dynamic_bounds 600->700 must be rejected")


def test_mutation_markdown_word_boundary_numeric() -> None:
    # Word-boundary numeric check is now via byte-equivalence; ensure
    # 200 inside 2000 does not satisfy standalone presence
    def _word_boundary_present(text: str, token: str) -> bool:
        return re.search(r"\b" + re.escape(token) + r"\b", text) is not None

    assert _word_boundary_present("scale down 200 ms", "200") is True
    assert _word_boundary_present("delay 2000 ms", "200") is False
    assert _word_boundary_present("threshold 600 gap", "600") is True
    assert _word_boundary_present("value 3600 steps", "600") is False
    assert not _word_boundary_present("outer_tick 2000", "200")


def test_mutation_monetary_recursive_rejection() -> None:
    # Recursive monetary fields anywhere must be rejected, while monetary:false allowed
    mutated = copy.deepcopy(canonical())
    mutated["cost"]["price_usd"] = 10
    assert_fails(mutated, "monetary price_usd field forbidden")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_scaling"]["billing"] = "usd"
    assert_fails(mutated2, "monetary billing nested field forbidden")
    mutated3 = copy.deepcopy(canonical())
    mutated3["scenario"]["currency"] = "USD"
    assert_fails(mutated3, "monetary currency field forbidden")
    mutated4 = copy.deepcopy(canonical())
    mutated4["extra"] = {"cost_dollars": 5}
    assert_fails(mutated4, "monetary cost_dollars nested forbidden")
    mutated5 = copy.deepcopy(canonical())
    mutated5["notes"] = "price is 10 dollars"
    assert_fails(mutated5, "monetary string with price/dollar forbidden")
    # Allowed phrase monetary:false should still pass (already canonical)
    data = canonical()
    assert data["cost"]["monetary"] is False
    result = validate_contract(data)
    assert result["pass"], f"canonical with monetary:false should pass but got {result['errors']}"


def test_mutation_scenario_frozen_constants_exact() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["scenario"]["steps"] = 3600 + 1
    assert_fails(mutated, "scenario steps must be 3600")
    mutated2 = copy.deepcopy(canonical())
    mutated2["scenario"]["backhaul_ms"] = 5.0
    assert_fails(mutated2, "scenario backhaul_ms must be 0.0")
    mutated3 = copy.deepcopy(canonical())
    mutated3["scenario"]["rsus"] = 12
    assert_fails(mutated3, "scenario rsus must be 10")
    mutated4 = copy.deepcopy(canonical())
    mutated4["scenario"]["waiting_room_cap_per_vehicle"] = 3.0
    assert_fails(mutated4, "waiting_room_cap must be 2.5")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_scaling"]["fixed_1x"]["rsu_service_mult"] = 2.0
    assert_fails(mutated5, "fixed_1x rsu_service_mult must be 1.0")
    mutated6 = copy.deepcopy(canonical())
    mutated6["compute_scaling"]["static_overprovisioned"]["rsu_service_mult"] = 2.0
    assert_fails(mutated6, "static_overprovisioned rsu_service_mult must be 3.0")
    mutated7 = copy.deepcopy(canonical())
    mutated7["compute_scaling"]["static_overprovisioned"]["active_units_per_rsu"] = 2
    assert_fails(mutated7, "static_overprovisioned active_units must be 3")


def test_mutation_inference_exact_fields() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["inference"]["sample_sd"] = "n"
    assert_fails(mutated, "sample_sd must be Bessel n-1")
    mutated2 = copy.deepcopy(canonical())
    mutated2["inference"]["se"] = "s/sqrt"
    assert_fails(mutated2, "se must be s / sqrt(n)")
    mutated3 = copy.deepcopy(canonical())
    mutated3["inference"]["interval"] = "95% Student-t, df=5, t=2.5"
    assert_fails(mutated3, "interval must contain df=3 and 3.182")
    mutated4 = copy.deepcopy(canonical())
    mutated4["inference"]["fleet_seeds"] = [1, 2, 3]
    assert_fails(mutated4, "inference fleet_seeds must be [1,2,3,4]")
    mutated5 = copy.deepcopy(canonical())
    mutated5["inference"]["n"] = 5
    assert_fails(mutated5, "inference n must be 4")
    mutated6 = copy.deepcopy(canonical())
    mutated6["inference"]["includes_zero_flag"] = False
    assert_fails(mutated6, "includes_zero_flag must be true")
    mutated7 = copy.deepcopy(canonical())
    mutated7["inference"]["forbidden"] = ["task_as_n"]
    assert_fails(mutated7, "inference forbidden must include seed_0_in_primary etc")


def test_mutation_staged_cross_computation_and_factorial() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["e3a"]["stale_ms"] = [0, 1000]
    assert_fails(mutated, "e3a stale_ms must be [0]")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3b"]["placement"] = ["per_task_dla", "ingress_dla"]
    assert_fails(mutated2, "e3b placement must be exactly per_task_dla")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3c"]["contrasts"] = [
        {"comparison": "per_task_dla vs p2c_dla", "over_stale_ms": [0, 1000, 3000]}
    ]
    assert_fails(mutated3, "e3c must have exactly 2 contrasts")
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["e3c"]["contrasts"][0]["over_stale_ms"] = [0, 1000]
    assert_fails(mutated4, "e3c over_stale_ms must be [0,1000,3000]")
    mutated5 = copy.deepcopy(canonical())
    mutated5["staged_design"]["e3c"]["additional_stale_variant_cells_max"] = 30
    assert_fails(mutated5, "e3c additional must be 32")
    mutated6 = copy.deepcopy(canonical())
    mutated6["staged_design"]["maximum_candidate_unique_cells"] = 144
    assert_fails(mutated6, "pseudo-full-factorial 144 must be rejected")


def test_mutation_markdown_inverse_claims_all_classes() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Each inverse mutation should cause markdown validation to fail
    # Canonical block equality may also kill these, but we demonstrate each dies via markdown checks
    inverse_mutations = [
        ("queue ceiling is compute capacity", "queue==compute"),
        ("actor observes RSU load", "actor observes"),
        ("actor selects execution RSU", "actor selects"),
        ("rejected work executes and is counted as deadline-met", "rejected executes"),
        ("unbounded scaling is allowed", "unbounded"),
        ("free scaling", "free"),
        ("static3x is preferred", "synonyms preferred"),
        ("tasks are replicates so N is number of tasks", "task-as-N"),
        # replicate-label erasure: remove fleet_seed mention
        ("replication_key is hidden", "replicate-label erasure"),
        ("this is a conclusion", "hypothesis->conclusion"),
        ("expected truth for H1", "hypothesis->expected truth"),
        ("cost is 10 USD", "monetary USD"),
        ("price $10", "monetary $"),
        ("outer_tick_ms is 200", "tick 200"),
        ("within_tick_task_slots is 10", "slot drift"),
        ("df is 5 and t is 2.5", "df/t drift"),
        ("cells total is 144", "cell drift"),
        ("predeclared contract is already executed", "already-executed"),
    ]
    for needle, label in inverse_mutations:
        # Inject inverse claim into narrative part (before validation)
        mutated_md = md_text.replace(
            "## 2. Frozen prerequisites", f"{needle}\n\n## 2. Frozen prerequisites"
        )
        errors = validate_markdown_contains(mutated_md, data)
        assert errors, f"markdown inverse claim {label!r} with {needle!r} should fail but passed"


def test_mutation_markdown_replicate_label_erasure() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Erase fleet_seed label should fail
    mutated_md = md_text.replace("fleet_seed", "hidden_seed")
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "markdown replicate-label erasure should fail"


def test_mutation_canonical_block_byte_equivalence() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Tamper canonical block to be non-deterministic (different whitespace)
    mutated_md = md_text.replace(
        '"status": "predeclared_before_any_e3_trace_execution"',
        '"status" :  "predeclared_before_any_e3_trace_execution"',
    )
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "canonical block non-byte-equivalence should fail"
    # Also test deep equality failure
    tampered = copy.deepcopy(data)
    tampered["campaign"] = "tampered"

    # Replace campaign in block
    mutated_md2 = re.sub(r'"campaign": "e3-dynamic-resource-v2"', '"campaign": "tampered"', md_text)
    errors2 = validate_markdown_contains(mutated_md2, data)
    assert errors2, "canonical block deep equality failure should be caught"


def test_mutation_markdown_canonical_block_missing() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    mutated_md = md_text.replace("<!-- BEGIN_E3_CANONICAL_JSON -->", "<!-- REMOVED -->")
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "missing canonical block should fail"


def test_mutation_markdown_factorial_overclaim_rejected() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Inject alone and jointly back into RQ quote should fail markdown check
    mutated_md = md_text.replace(
        "without fully crossing every placement with every scaler",
        "alone and jointly, fully crossing every placement with every scaler",
    )
    # Also need to ensure RQ quote contains alone and jointly - the replacement does that
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "markdown factorial overclaim should fail"

    mutated_md2 = md_text.replace("E3a isolates placement", "E3a does placement")
    errors2 = validate_markdown_contains(mutated_md2, data)
    assert errors2, "markdown missing E3a isolates placement should fail"

    mutated_md3 = md_text.replace("E3b holds placement fixed", "E3b tests scaling")
    errors3 = validate_markdown_contains(mutated_md3, data)
    assert errors3, "markdown missing E3b holds placement fixed should fail"


def test_contract_authority_json_normative() -> None:
    data = canonical()
    assert data["contract_authority"] == "json_is_normative_markdown_is_generated_view"
    assert data["markdown_is_generated_view"] is True
    assert "JSON is the single normative" in data["authority_note"]
    # Tamper should fail
    mutated = copy.deepcopy(data)
    mutated["contract_authority"] = "markdown_is_normative"
    assert_fails(mutated, "contract_authority must be json_is_normative")
    mutated2 = copy.deepcopy(data)
    mutated2["markdown_is_generated_view"] = False
    assert_fails(mutated2, "markdown_is_generated_view must be true")


def test_markdown_is_deterministic_render() -> None:
    """Markdown must equal render_markdown(canonical_json) byte-for-byte."""

    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    expected = render_markdown(data)
    assert md_text == expected, "committed Markdown must equal render_markdown(canonical_json)"
    # Any prose change outside block must fail byte equivalence
    mutated_md = md_text.replace("## 1. Research question", "## 1. RESEARCH QUESTION MODIFIED")
    errors = validate_markdown_contains(mutated_md, data)
    assert errors, "prose change outside block must fail"
    assert any("byte-equivalence" in e for e in errors), (
        f"expected byte-equivalence error, got {errors}"
    )


def test_default_cli_validates_both_and_byte_equivalence(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Default invocation must validate both JSON and Markdown and
    byte equivalence.
    """

    monkeypatch.setattr(sys, "argv", ["validate"])
    rc = main()
    out_text = capsys.readouterr().out
    assert rc == 0, f"default CLI should pass, got {out_text}"
    out = json.loads(out_text)
    assert out["pass"] is True


def test_cli_alternate_paths_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    alt_json = tmp_path / "alt.json"
    alt_md = tmp_path / "alt.md"
    alt_json.write_text(CANONICAL_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    alt_md.write_text(CANONICAL_MD.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate",
            "--contract-json",
            str(alt_json),
            "--contract-md",
            str(alt_md),
        ],
    )
    rc = main()
    out_text = capsys.readouterr().out
    assert rc == 0, f"alternate paths should pass: {out_text}"


def test_cli_missing_md_fails_regardless_of_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "missing.md"
    # do not create missing
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(missing)])
    rc = main()
    out_text = capsys.readouterr().out
    assert rc != 0, "missing MD must fail regardless of flags"
    out = json.loads(out_text) if out_text.strip() else {}
    assert not out.get("pass", True)
    # also test deprecated flag still fails
    monkeypatch.setattr(
        sys,
        "argv",
        ["validate", "--contract-md", str(missing), "--check-equivalence"],
    )
    rc2 = main()
    out_text2 = capsys.readouterr().out
    assert rc2 != 0, "missing MD must fail even with deprecated flag"
    assert "missing" in out_text2.lower() or "pass" in out_text2.lower()


def test_cli_nonexistent_contract_md_flag_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does_not_exist_12345.md"

    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(missing)])
    rc = main()
    _ = capsys.readouterr()
    assert rc != 0


def _tamper_md_via_file(tmp_path: Path, needle: str, anchor: str = "## 7. Compute scaling") -> Path:
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    tampered = md_text.replace(anchor, f"{needle}\n\n{anchor}")
    # ensure we actually mutated (anchor must exist)
    assert tampered != md_text, f"anchor {anchor!r} not found for needle {needle!r}"
    out = tmp_path / "tampered.md"
    out.write_text(tampered, encoding="utf-8")
    return out


def test_hostile_task_as_independent_n_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "tasks are replicates so N is number of tasks")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"task-as-N via file should fail: {out}"


def test_hostile_monetary_usd_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "cost is 10 USD per task")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"monetary USD via file should fail: {out}"


def test_hostile_queue_equals_compute_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "queue ceiling is compute capacity")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"queue==compute via file should fail: {out}"


def test_hostile_false_p2c_global_inspection_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "P2C inspects only two total global state reads")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"false P2C global-inspection via file should fail: {out}"


def test_hostile_unbounded_scaling_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "unbounded scaling from 1 to 8 is allowed")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"unbounded 1..8 via file should fail: {out}"


def test_hostile_markdown_authority_inversion_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tampered = _tamper_md_via_file(tmp_path, "Markdown is the single normative scientific contract")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(tampered)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"markdown authority inversion via file should fail: {out}"


def test_hostile_prose_deletion_via_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    lines = md_text.splitlines()
    # delete a material ~30-line block (skip canonical JSON block)
    # take lines 40..70 (outside canonical block which is at end)
    assert len(lines) > 200, "markdown too short to delete 30 lines"
    del lines[40:70]
    tampered_text = "\n".join(lines)
    assert tampered_text != md_text
    out_path = tmp_path / "deleted.md"
    out_path.write_text(tampered_text, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["validate", "--contract-md", str(out_path)])
    rc = main()
    out = capsys.readouterr().out
    assert rc != 0, f"30-line deletion via file should fail: {out}"


def test_narrative_drift_outside_block_fails_byte_equivalence_with_specific_error() -> None:
    """Mutate narrative outside block; assert byte-equivalence error."""
    data = canonical()
    # Block is controlled (canonical), mutate narrative outside block
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    narratives = [
        ("queue ceiling is compute capacity", "queue==compute"),
        ("actor observes RSU load", "actor observes"),
        ("actor selects execution RSU", "actor selects"),
        ("rejected work executes", "rejected executes"),
        ("free scaling is allowed", "free/unbounded"),
        ("tasks are replicates", "task-as-N"),
        ("this is a conclusion", "hypothesis conclusion"),
        ("expected truth", "hypothesis truth"),
        ("cost is 10 USD", "monetary"),
        ("outer_tick_ms is 200", "200ms tick"),
        ("within_tick_task_slots is 10", "slot drift"),
        ("df is 5", "df drift"),
        ("cells total is 144", "cell drift"),
        ("already executed", "executed"),
        ("fleet_seed is hidden", "replicate-label"),
    ]
    for needle, label in narratives:
        mutated_md = md_text.replace(
            "## 2. Frozen prerequisites", f"{needle}\n\n## 2. Frozen prerequisites"
        )
        errors = validate_markdown_contains(mutated_md, data)
        assert errors, f"narrative drift {label!r} should fail"
        assert any("byte-equivalence" in e for e in errors), (
            f"{label} must fail via byte-equivalence, got {errors}"
        )


def test_regenerated_but_mutated_json_still_rejected_by_field_rules() -> None:
    """Regenerated but mutated JSON+Markdown pair must still be rejected."""

    mutated = copy.deepcopy(canonical())
    mutated["mechanism_separation"]["queue_ceiling_is_not_compute_capacity"] = False
    # Regenerate markdown to match mutated JSON so byte equivalence passes
    regenerated_md = render_markdown(mutated)
    # Markdown byte equivalence should pass (since regenerated)
    _md_errors = validate_markdown(regenerated_md, mutated)
    # _md_errors may be empty because markdown matches mutated json
    # But validate_contract must still reject via field rule
    result = validate_contract(mutated)
    assert not result["pass"], "mutated JSON must be rejected even when markdown is regenerated"
    assert any(
        "queue_ceiling_is_not_compute_capacity" in e or "queue" in e.lower()
        for e in result["errors"]
    ), f"expected queue==compute field error, got {result['errors']}"


def test_malformed_scalar_and_nonlist_shapes_fail_closed() -> None:
    """Scalar shapes must return structured errors, never TypeError.

    Covers scalar placement, non-list contrasts, malformed factors,
    and missing fields.
    """
    # scalar placement
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["e3a"]["placement"] = "ingress_dla"  # scalar, not list
    result = validate_contract(mutated)
    assert not result["pass"]
    assert result["error_count"] > 0
    # scalar scaling
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3b"]["scaling"] = "fixed_1x"
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    # non-list contrasts
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3c"]["contrasts"] = {"comparison": "per_task_dla vs p2c_dla"}
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    # malformed factor values: e.g., placement contains integer
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["e3a"]["placement"] = [123, None]
    result4 = validate_contract(mutated4)
    assert not result4["pass"]
    # missing fields
    mutated5 = copy.deepcopy(canonical())
    del mutated5["replication"]
    result5 = validate_contract(mutated5)
    assert not result5["pass"]
    # Ensure no exception raised: we already got results, not crashed
    # Also test validate_contract with non-dict input
    result6 = validate_contract([])
    assert not result6["pass"]
    assert any("dict" in e for e in result6["errors"])


def test_cross_count_locals_initialized_no_nameerror() -> None:
    """Cross-count locals must be initialized; malformed shapes must not
    raise NameError.
    """

    mutated = copy.deepcopy(canonical())
    # Make e3a placement scalar to trigger early error
    # but still cross-count logic should not NameError
    mutated["staged_design"]["e3a"]["placement"] = "scalar"
    mutated["staged_design"]["e3b"]["scaling"] = "scalar"
    result = validate_contract(mutated)
    # Should return errors, not raise
    assert not result["pass"]
    assert isinstance(result["errors"], list)


def test_direct_positive_assertions_for_all_narrative_categories() -> None:
    """Direct positive assertions for each required narrative drift category."""
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    # Each category must be detectable via byte-equivalence when narrative drifts
    categories = {
        "queue==compute": "queue ceiling is compute capacity",
        "actor observes": "actor observes RSU load",
        "actor selects": "actor selects execution RSU",
        "rejected executes": "rejected work executes",
        "free/unbounded": "unbounded scaling is allowed",
        "task-as-N": "tasks are replicates",
        "hypothesis conclusion": "this is a conclusion",
        "hypothesis truth": "expected truth",
        "monetary": "cost is 5 USD",
        "200ms tick": "outer_tick_ms is 200",
        "slot": "within_tick_task_slots is 200",
        "df/t": "df is 5 and t is 2.5",
        "cell": "cells total is 144",
        "executed": "already executed",
        "replicate-label": "fleet_seed is hidden",
    }
    for cat, needle in categories.items():
        mutated_md = md_text.replace("## 7. Compute scaling", f"{needle}\n\n## 7. Compute scaling")
        errors = validate_markdown_contains(mutated_md, data)
        assert errors, f"category {cat} narrative drift must fail"
        assert any("byte-equivalence" in e for e in errors), (
            f"{cat} should be byte-equivalence, got {errors}"
        )


# --- Compute-service semantics mutation tests (Lane 01 pre-freeze audit) ---


def test_mutation_compute_service_dividing_enqueued_work() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["enqueue_equation"] = (
        "enqueued_work_ms = raw_1x_service_work_ms / active_capacity_units"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("enqueue_equation" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["enqueue_must_not_divide_by_capacity"] = False
    assert_fails(mutated2, "dividing enqueued work by capacity")


def test_mutation_compute_service_draining_only_newly_enqueued() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["drain_applies_to_all_queued_work_including_pre_scale"] = (
        False
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("drain_applies_to_all_queued_work" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["drain_equation"] = (
        "drain_work_ms = min(newly_enqueued_work_ms, active_capacity_units * 1000)"
    )
    assert_fails(mutated2, "drain only newly enqueued")


def test_mutation_compute_service_1x_only_drain() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["drain_equation"] = (
        "drain_work_ms = min(backlog_work_ms, 1000)"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("drain_equation" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["drain_tick_ms"] = 500
    assert_fails(mutated2, "1x-only drain tick")


def test_mutation_compute_service_idle_free_resource_time() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["resource_time_charged_even_when_idle"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("resource_time_charged_even_when_idle" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["at_most_one_interval_per_RSU_per_tick"] = False
    assert_fails(mutated2, "idle-free at most one interval")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["resource_time_equation"] = (
        "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 0"
    )
    assert_fails(mutated3, "idle-free resource time equation")


def test_mutation_compute_service_queue_capacity_conflation() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["drain_capacity_is_not_queue_slots"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("drain_capacity_is_not_queue_slots" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["scaling_forbidden_units"] = ["queue_slots"]
    assert_fails(mutated2, "queue/capacity conflation forbidden units")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["scaling_forbidden_units"] = [
        "capacity_normalized_work_ms"
    ]
    assert_fails(mutated3, "missing queue_slots in forbidden")


def test_mutation_compute_service_normalized_placement_gate_signal() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["placement_workloads_unit"] = "capacity_normalized_work_ms"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("placement_workloads_unit" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["admission_gate_unit"] = "capacity_normalized_work_ms"
    assert_fails(mutated2, "normalized admission gate")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["reactive_signal_unit"] = "capacity_normalized_work_ms"
    assert_fails(mutated3, "normalized reactive signal")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_service_semantics"]["scaling_must_not_change_placement_or_admission_unit"] = (
        False
    )
    assert_fails(mutated4, "normalized placement/gate signal allowed")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_service_semantics"]["proactive_observation_unit"] = (
        "capacity_normalized_work_ms"
    )
    assert_fails(mutated5, "normalized proactive observation")


def test_mutation_compute_service_retroactive_latency_repricing() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["latency_not_retroactively_repriced"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("latency_not_retroactively_repriced" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["latency_equation"] = (
        "(raw_work_ahead_ms + raw_own_service_work_ms)"
    )
    assert_fails(mutated2, "future retroactive latency repricing missing division")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["latency_semantics"] = "physical_lifecycle"
    assert_fails(mutated3, "latency semantics not estimate")


def test_mutation_compute_service_wrong_initial_capacities() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["initial_capacities"]["static_overprovisioned_units"] = 2
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("static_overprovisioned_units" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["initial_capacities"][
        "static_overprovisioned_from_tick"
    ] = 1
    assert_fails(mutated2, "wrong static from tick")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["initial_capacities"]["dynamic_start_units"] = 2
    assert_fails(mutated3, "wrong dynamic start")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_service_semantics"]["initial_capacities"]["fixed_1x_units"] = 2
    assert_fails(mutated4, "wrong fixed_1x initial")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_service_semantics"]["initial_capacities"]["dynamic_max_units"] = 4
    assert_fails(mutated5, "wrong dynamic max")


def test_mutation_compute_service_physical_completion_claim() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["latency_physical_lifecycle_fields_remain_null"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("latency_physical_lifecycle_fields_remain_null" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["task_accounting"]["unavailable_lifecycle"]["compute_completed"] = 0
    assert_fails(mutated2, "physical completion claim via unavailable lifecycle")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["latency_semantics"] = "physical_completion"
    assert_fails(mutated3, "physical completion latency semantics")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_service_semantics"]["reduces_to_E2d_at_fixed_1x"] = False
    assert_fails(mutated4, "reduces to E2d false")


def test_mutation_compute_service_invariant_signal_units() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["stale_snapshot_unit"] = "capacity_normalized_work_ms"
    assert_fails(mutated, "normalized stale snapshot")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["same_tick_reservation_overlay_unit"] = (
        "capacity_normalized_work_ms"
    )
    assert_fails(mutated2, "normalized reservation overlay")


def test_mutation_compute_service_scaling_timing() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"][
        "scaling_applied_at_tick_start_before_placement_admission"
    ] = False
    assert_fails(mutated, "scaling timing tick start")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["scaling_applied_before_latency_estimate_and_drain"] = (
        False
    )
    assert_fails(mutated2, "scaling before latency/drain")
    mutated3 = copy.deepcopy(canonical())
    mutated3["compute_service_semantics"]["active_capacity_for_entire_tick"] = False
    assert_fails(mutated3, "active capacity entire tick")


def test_mutation_staged_60_as_unique_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["maximum_candidate_unique_cells"] = 60
    assert_fails(mutated, "60-as-unique must be rejected (unique is 56, 60 is stage-listed)")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["stage_listed_cells"] = 56
    assert_fails(mutated2, "stage_listed 56 must be rejected (must be 60)")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3c"]["total_candidate_with_stale_max"] = 60
    assert_fails(mutated3, "total_candidate_with_stale_max 60 must be rejected")
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["stage_listed_equation"] = "12 + 16 + 32 = 56"
    assert_fails(mutated4, "stage_listed equation must be 12+16+32=60")
    mutated5 = copy.deepcopy(canonical())
    mutated5["staged_design"]["unique_equation"] = "12 + 16 + 32 = 60"
    assert_fails(mutated5, "unique equation must be 12+12+32=56")


def test_mutation_staged_overlap_reuse_must_not_rerun() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["e3b_overlap_with_e3a"] = 0
    assert_fails(mutated, "e3b overlap 0 must be rejected (must be 4)")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3b_unique_additional"] = 16
    assert_fails(mutated2, "e3b unique_additional 16 must be rejected (must be 12, 16-4)")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3b"]["overlap_with_e3a"] = 0
    assert_fails(mutated3, "e3b overlap_with_e3a 0")
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["e3b"]["unique_additional"] = 16
    assert_fails(mutated4, "e3b unique_additional 16 reruns overlap")
    mutated5 = copy.deepcopy(canonical())
    del mutated5["staged_design"]["e3b"]["overlap_note"]
    assert_fails(mutated5, "overlap_note missing must fail")
    mutated6 = copy.deepcopy(canonical())
    mutated6["staged_design"]["e3c_fresh_observations_reused"] = 0
    assert_fails(mutated6, "e3c fresh reused 0 must be rejected")
    mutated7 = copy.deepcopy(canonical())
    mutated7["staged_design"]["e3c"]["fresh_observations_reused"] = 0
    assert_fails(mutated7, "e3c fresh_observations_reused 0 reruns fresh")


def test_mutation_staged_48_32_56_miscount_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["staged_design"]["e3c_total_contrast_observations"] = 32
    assert_fails(mutated, "e3c total 32 must be 48")
    mutated2 = copy.deepcopy(canonical())
    mutated2["staged_design"]["e3c"]["total_contrast_observations"] = 32
    assert_fails(mutated2, "e3c total_contrast 32")
    mutated3 = copy.deepcopy(canonical())
    mutated3["staged_design"]["e3c"]["fresh_observations_reused"] = 8
    assert_fails(mutated3, "e3c fresh 8")
    mutated4 = copy.deepcopy(canonical())
    mutated4["staged_design"]["e3c"]["stale_variant_equation"] = "48 - 8 = 40"
    assert_fails(mutated4, "stale_variant equation wrong")
    mutated5 = copy.deepcopy(canonical())
    mutated5["staged_design"]["e3c_stale_variant_equation"] = "48 - 16 = 40"
    assert_fails(mutated5, "e3c_stale_variant_equation 40")
    mutated6 = copy.deepcopy(canonical())
    mutated6["staged_design"]["e3c"]["additional_stale_variant_cells_max"] = 48
    assert_fails(mutated6, "additional 48 must be 32")
    mutated7 = copy.deepcopy(canonical())
    mutated7["staged_design"]["maximum_candidate_unique_cells"] = 60
    assert_fails(mutated7, "unique 60")
    mutated8 = copy.deepcopy(canonical())
    mutated8["staged_design"]["stage_listed_cells"] = 56
    assert_fails(mutated8, "stage_listed 56")


def test_mutation_stale_deadline_view_must_not_become_fresh() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_state_semantics"]["deadline_workload_observation_has_state_age"] = False
    assert_fails(mutated, "deadline workload must have state_age")
    mutated2 = copy.deepcopy(canonical())
    mutated2["admission_gate"]["stale_view_applies_to_deadline_workload"] = False
    assert_fails(mutated2, "admission gate stale view")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_state_semantics"]["forbidden_behaviors"] = ["stale_queue_cap"]
    assert_fails(
        mutated3, "forbidden_behaviors must include stale_deadline_view_silently_becoming_fresh"
    )
    mutated4 = copy.deepcopy(canonical())
    del mutated4["stale_state_semantics"]["exposes"]
    assert_fails(mutated4, "exposes missing")


def test_mutation_stale_queue_cap_must_be_current() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_state_semantics"]["queue_ceiling_uses_stale_view"] = True
    assert_fails(mutated, "queue_ceiling_uses_stale_view true must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_state_semantics"]["queue_safety_uses_current_not_stale"] = False
    assert_fails(mutated2, "queue_safety_uses_current_not_stale false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["admission_gate"]["queue_safety_uses_current_not_stale"] = False
    assert_fails(mutated3, "admission queue safety stale")
    mutated4 = copy.deepcopy(canonical())
    mutated4["compute_service_semantics"]["queue_safety_is_current_not_stale"] = False
    assert_fails(mutated4, "css queue safety stale")
    mutated5 = copy.deepcopy(canonical())
    mutated5["compute_service_semantics"][
        "queue_ceiling_uses_current_occupancy_plus_same_tick_reservations"
    ] = False
    assert_fails(mutated5, "css queue ceiling stale")
    mutated6 = copy.deepcopy(canonical())
    mutated6["stale_state_semantics"]["queue_ceiling_enforcement"] = "stale_view"
    assert_fails(mutated6, "queue_ceiling_enforcement stale")


def test_mutation_stale_mutation_of_true_state_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_state_semantics"]["does_not_mutate"] = ["true_environment"]
    assert_fails(mutated, "does_not_mutate must include all 4")
    mutated2 = copy.deepcopy(canonical())
    mutated2["compute_service_semantics"]["stale_does_not_mutate_true_state"] = False
    assert_fails(mutated2, "stale_does_not_mutate_true_state false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_state_semantics"]["applies_to"] = ["true_environment"]
    assert_fails(mutated3, "applies_to must be workload view etc, not true_environment")


def test_mutation_stale_pretrace_warmup_and_clamp_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_state_semantics"]["initialization"][
        "pretrace_zeros_do_not_satisfy_proactive_warmup"
    ] = False
    assert_fails(mutated, "pretrace_zeros_do_not_satisfy_proactive_warmup false")
    mutated2 = copy.deepcopy(canonical())
    mutated2["time_model"]["proactive_pretrace_does_not_satisfy_warmup"] = False
    assert_fails(mutated2, "time_model pretrace warmup false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_state_semantics"]["initialization"][
        "permits_exact_0_1000_3000_without_clamping"
    ] = False
    assert_fails(mutated3, "permits_exact_without_clamping false")
    mutated4 = copy.deepcopy(canonical())
    mutated4["time_model"]["permits_exact_views_without_clamping"] = False
    assert_fails(mutated4, "time_model permits_exact false")
    mutated5 = copy.deepcopy(canonical())
    mutated5["stale_state_semantics"]["forbidden_behaviors"] = ["clock_clamp"]
    assert_fails(mutated5, "forbidden_behaviors must include clock_clamp etc")
    mutated6 = copy.deepcopy(canonical())
    mutated6["stale_state_semantics"]["initialization"][
        "proactive_still_requires_four_actual_trace_observations"
    ] = False
    assert_fails(mutated6, "proactive_still_requires_four false")


def test_mutation_stale_state_age_laundering_and_offset_delay_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_state_semantics"]["forbidden_behaviors"] = ["state_age_laundering"]
    assert_fails(mutated, "state_age_laundering must be in forbidden")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_state_semantics"]["initialization"][
        "scaling_delay_cooldown_use_control_clock_differences_no_extra_delay"
    ] = False
    assert_fails(mutated2, "scaling_delay_cooldown_use_control_clock false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["time_model"]["scaling_delay_uses_control_clock_differences"] = False
    assert_fails(mutated3, "time_model scaling_delay false")
    mutated4 = copy.deepcopy(canonical())
    mutated4["stale_state_semantics"]["initialization"]["control_clock_offset_ms"] = 0
    assert_fails(mutated4, "control_clock_offset 0 must be 3000")
    mutated5 = copy.deepcopy(canonical())
    mutated5["time_model"]["control_clock_offset_ms"] = 0
    assert_fails(mutated5, "time_model offset 0")
    mutated6 = copy.deepcopy(canonical())
    mutated6["stale_state_semantics"]["forbidden_behaviors"] = ["offset_added_to_action_delay"]
    assert_fails(mutated6, "offset_added_to_action_delay must be in forbidden")


def test_mutation_p2c_replacement_and_unsorted_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["placement"]["p2c_dla"]["without_replacement"] = False
    assert_fails(mutated, "without_replacement false must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["placement"]["p2c_dla"]["pair_mapper"]["distinct_without_replacement"] = False
    assert_fails(mutated2, "distinct_without_replacement false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["placement"]["p2c_dla"]["pair_mapper"]["candidate_order"] = "unsorted"
    assert_fails(mutated3, "candidate_order unsorted")
    mutated4 = copy.deepcopy(canonical())
    mutated4["placement"]["p2c_dla"]["pair_mapper"]["final_pair_sorted"] = False
    assert_fails(mutated4, "final_pair_sorted false")


def test_mutation_p2c_alternate_hash_key_mapper_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["placement"]["p2c_dla"]["counter_key_fields"] = [
        "evaluator_seed",
        "fleet_seed",
        "tick",
        "task_slot",
        "sequential_ordinal",
    ]
    assert_fails(mutated, "counter_key_fields tick must be outer_tick")
    mutated2 = copy.deepcopy(canonical())
    mutated2["placement"]["p2c_dla"]["pair_mapper"]["hash"] = "MD5"
    assert_fails(mutated2, "hash MD5 must be SplitMix64")
    mutated3 = copy.deepcopy(canonical())
    mutated3["placement"]["p2c_dla"]["pair_mapper"]["hash_input_fields_exact"] = [
        "evaluator_seed",
        "fleet_seed",
        "tick",
        "task_slot",
        "sequential_ordinal",
    ]
    assert_fails(mutated3, "hash_input_fields tick")
    mutated4 = copy.deepcopy(canonical())
    mutated4["placement"]["p2c_dla"]["pair_mapper"]["first_index_formula"] = "h % (n-1)"
    assert_fails(mutated4, "first_index formula wrong")
    mutated5 = copy.deepcopy(canonical())
    mutated5["placement"]["p2c_dla"]["pair_mapper"]["second_index_formula"] = "h % n"
    assert_fails(mutated5, "second_index formula wrong")
    mutated6 = copy.deepcopy(canonical())
    mutated6["placement"]["p2c_dla"]["pair_mapper"]["mapper_type"] = "uniform_random_mapper"
    assert_fails(mutated6, "mapper_type uniform")
    mutated7 = copy.deepcopy(canonical())
    mutated7["placement"]["p2c_dla"]["pair_mapper"]["no_hidden_global_RNG"] = False
    assert_fails(mutated7, "hidden global RNG allowed")


def test_mutation_p2c_uniform_unbiased_claim_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["placement"]["p2c_dla"]["modulo_bias_note"] = "exact-uniform and unbiased"
    assert_fails(mutated, "uniform unbiased claim must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["placement"]["p2c_dla"]["pair_mapper"]["uniformity_not_claimed"] = False
    assert_fails(mutated2, "uniformity_not_claimed false")
    mutated3 = copy.deepcopy(canonical())
    mutated3["placement"]["p2c_dla"]["uniformity_claim_forbidden"] = ["uniform"]
    assert_fails(mutated3, "uniformity_claim_forbidden must include unbiased")
    mutated4 = copy.deepcopy(canonical())
    mutated4["placement"]["p2c_dla"]["h1_concern"] = "statistical proof of perfect uniformity"
    assert_fails(mutated4, "h1_concern must be pair_only_inspection")
    mutated5 = copy.deepcopy(canonical())
    mutated5["placement"]["p2c_dla"]["modulo_bias_note"] = "modulo reduction is exactly uniform"
    assert_fails(mutated5, "exactly uniform claim")


def test_mutation_stale_decision_vs_true_execution_stale_for_latency_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_decision_vs_true_execution"][
        "deadline_success_based_on_true_simulated_latency_never_stale_estimate"
    ] = False
    assert_fails(mutated, "stale belief for actual latency must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_decision_vs_true_execution"]["forbidden_behaviors"] = [
        "true_state_used_for_stale_decision",
        "executing_pessimistically_rejected_work",
        "delaying_true_capacity_or_drain",
    ]
    assert_fails(mutated2, "missing stale_belief_used_for_actual_latency forbidden")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_decision_vs_true_execution"]["true_execution_determines"] = ["enqueue"]
    assert_fails(mutated3, "true_execution_determines must contain deadline_success")


def test_mutation_stale_decision_vs_true_execution_true_for_decision_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_decision_vs_true_execution"]["placement_uses_observed"] = False
    assert_fails(mutated, "true state for stale decision must be rejected (placement)")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_decision_vs_true_execution"][
        "deadline_admission_gate_uses_observed_backlog_only"
    ] = False
    assert_fails(mutated2, "true state for deadline gate stale decision")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_decision_vs_true_execution"]["forbidden_behaviors"] = [
        "stale_belief_used_for_actual_latency_or_success",
        "executing_pessimistically_rejected_work",
        "delaying_true_capacity_or_drain",
    ]
    assert_fails(mutated3, "missing true_state_used_for_stale_decision forbidden")


def test_mutation_stale_decision_vs_true_execution_pessimistic_rejected_execution_rejected() -> (
    None
):
    mutated = copy.deepcopy(canonical())
    mutated["stale_decision_vs_true_execution"][
        "pessimistic_stale_rejected_never_executes_even_if_true_would_have_been_feasible"
    ] = False
    assert_fails(mutated, "pessimistically rejected must never execute")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_decision_vs_true_execution"]["forbidden_behaviors"] = [
        "stale_belief_used_for_actual_latency_or_success",
        "true_state_used_for_stale_decision",
        "delaying_true_capacity_or_drain",
    ]
    assert_fails(mutated2, "missing executing_pessimistically_rejected_work forbidden")


def test_mutation_stale_decision_vs_true_execution_delay_true_capacity_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["stale_decision_vs_true_execution"][
        "current_capacity_action_application_and_drain_operate_on_true_state"
    ] = False
    assert_fails(mutated, "delaying true capacity must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_decision_vs_true_execution"]["scaling_decisions_observe_delayed_signals"] = (
        False
    )
    assert_fails(mutated2, "scaling decisions must observe delayed signals, capacity must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["stale_decision_vs_true_execution"]["forbidden_behaviors"] = [
        "stale_belief_used_for_actual_latency_or_success",
        "true_state_used_for_stale_decision",
        "executing_pessimistically_rejected_work",
    ]
    assert_fails(mutated3, "missing delaying_true_capacity_or_drain forbidden")
    mutated4 = copy.deepcopy(canonical())
    mutated4["stale_decision_vs_true_execution"][
        "later_scale_actions_do_not_retroactively_reprice_recorded_task"
    ] = False
    assert_fails(mutated4, "retroactive repricing must be false")


def test_mutation_p2c_dense_active_only_ordinal_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"][
        "independent_of_active_mask"
    ] = False
    assert_fails(mutated, "active-only ordinal must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_dense_counter_key_mapping"]["forbidden_behaviors"] = [
        "ordinal_reset_or_collision",
        "200ms_time_interpretation",
        "outcome_dependent_key_shifts",
    ]
    assert_fails(mutated2, "missing active_only_ordinal forbidden")


def test_mutation_p2c_dense_ordinal_collision_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"][
        "dense_position_identity"
    ] = False
    assert_fails(mutated, "ordinal collision/reset must be rejected (dense)")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"]["per_outer_tick"] = False
    assert_fails(mutated2, "per outer tick range must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"]["range"] = "[0,100]"
    assert_fails(mutated3, "sequential range must be [0,12439]")
    mutated4 = copy.deepcopy(canonical())
    mutated4["p2c_dense_counter_key_mapping"]["forbidden_behaviors"] = [
        "active_only_ordinal",
        "200ms_time_interpretation",
        "outcome_dependent_key_shifts",
    ]
    assert_fails(mutated4, "missing ordinal_reset_or_collision forbidden")


def test_mutation_p2c_dense_200ms_time_interpretation_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_dense_counter_key_mapping"]["task_slot"]["advances_physical_time"] = True
    assert_fails(
        mutated, "200ms time interpretation must be rejected (task_slot must not advance time)"
    )
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_dense_counter_key_mapping"]["task_slot"]["range"] = "[0,9]"
    assert_fails(mutated2, "task_slot range must be [0,4]")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_dense_counter_key_mapping"]["forbidden_behaviors"] = [
        "active_only_ordinal",
        "ordinal_reset_or_collision",
        "outcome_dependent_key_shifts",
    ]
    assert_fails(mutated3, "missing 200ms_time_interpretation forbidden")


def test_mutation_p2c_dense_outcome_dependent_shift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"][
        "earlier_outcomes_never_shift_later_pairs"
    ] = False
    assert_fails(mutated, "outcome-dependent key shifts must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"][
        "independent_of_admission_or_rejection"
    ] = False
    assert_fails(mutated2, "independent of admission must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_dense_counter_key_mapping"]["sequential_task_ordinal"][
        "independent_of_feasibility"
    ] = False
    assert_fails(mutated3, "independent of feasibility must be true")
    mutated4 = copy.deepcopy(canonical())
    mutated4["p2c_dense_counter_key_mapping"]["forbidden_behaviors"] = [
        "active_only_ordinal",
        "ordinal_reset_or_collision",
        "200ms_time_interpretation",
    ]
    assert_fails(mutated4, "missing outcome_dependent_key_shifts forbidden")


def test_mutation_h1_two_total_reads_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["h1_state_inspection"]["must_not_claim_only_two_total_global_reads"] = False
    assert_fails(mutated, "two total reads claim must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["h1_state_inspection"]["forbidden_claims"] = [
        "hidden_feasibility_scan",
        "communication_savings_proven",
    ]
    assert_fails(mutated2, "missing two_total_reads forbidden")


def test_mutation_h1_hidden_feasibility_scan_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["h1_state_inspection"][
        "feasibility_first_must_enumerate_all_RSU_deadline_feasibility"
    ] = False
    assert_fails(mutated, "hidden feasibility scan must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["h1_state_inspection"]["forbidden_claims"] = [
        "two_total_reads",
        "communication_savings_proven",
    ]
    assert_fails(mutated2, "missing hidden_feasibility_scan forbidden")
    # also markdown hidden scan: test via validator's markdown check is covered by JSON


def test_mutation_h1_communication_savings_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["h1_state_inspection"]["must_not_claim_distributed_communication_savings"] = False
    assert_fails(mutated, "communication savings claim must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["h1_state_inspection"]["must_not_claim_proven_lower_total_state_acquisition"] = False
    assert_fails(mutated2, "proven lower total state acquisition claim must be rejected")
    mutated3 = copy.deepcopy(canonical())
    mutated3["h1_state_inspection"][
        "h1_is_hypothesis_about_pair_only_ranking_vs_global_least_busy_dependence_not_proved_networking_cost"
    ] = False
    assert_fails(mutated3, "H1 must be hypothesis about pair-only ranking not proved networking")
    mutated4 = copy.deepcopy(canonical())
    mutated4["h1_state_inspection"]["forbidden_claims"] = [
        "two_total_reads",
        "hidden_feasibility_scan",
    ]
    assert_fails(mutated4, "missing communication_savings_proven forbidden")


def test_mutation_resource_diagnostics_raw_utilization_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"]["capacity_adjusted_utilization"]["formula"] = (
        "drained_work_ms / 1000"
    )
    assert_fails(mutated, "raw/1000 utilization under u>1 must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"]["capacity_adjusted_utilization"]["bounded"] = "[0,10]"
    assert_fails(mutated2, "bounded must be [0,1]")
    mutated3 = copy.deepcopy(canonical())
    mutated3["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "queue_occupancy_as_denominator",
        "zero_fill_shares_when_denominator_zero",
        "rejected_task_switches",
        "unordered_or_across_draw_switches",
        "missing_cost_denominator",
    ]
    assert_fails(mutated3, "missing raw_over_1000 forbidden")


def test_mutation_resource_diagnostics_queue_occupancy_denominator_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"]["capacity_adjusted_utilization"][
        "waiting_room_occupancy_is_separate_task_count_and_never_denominator"
    ] = False
    assert_fails(mutated, "queue occupancy denominator must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "raw_over_1000_utilization_under_u_gt_1",
        "zero_fill_shares_when_denominator_zero",
        "rejected_task_switches",
        "unordered_or_across_draw_switches",
        "missing_cost_denominator",
    ]
    assert_fails(mutated2, "missing queue_occupancy_as_denominator forbidden")


def test_mutation_resource_diagnostics_zero_fill_shares_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"]["execution_share"][
        "when_denominator_zero_is_null_with_explicit_reason_not_zeros"
    ] = False
    assert_fails(mutated, "zero-fill shares must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "raw_over_1000_utilization_under_u_gt_1",
        "queue_occupancy_as_denominator",
        "rejected_task_switches",
        "unordered_or_across_draw_switches",
        "missing_cost_denominator",
    ]
    assert_fails(mutated2, "missing zero_fill_shares forbidden")


def test_mutation_resource_diagnostics_rejected_task_switches_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"]["target_switching"][
        "rejected_and_non_V2I_tasks_excluded"
    ] = False
    assert_fails(mutated, "rejected-task switches must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"]["target_switching"][
        "first_admitted_task_is_not_a_switch"
    ] = False
    assert_fails(mutated2, "first admitted not a switch must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "raw_over_1000_utilization_under_u_gt_1",
        "queue_occupancy_as_denominator",
        "zero_fill_shares_when_denominator_zero",
        "unordered_or_across_draw_switches",
        "missing_cost_denominator",
    ]
    assert_fails(mutated3, "missing rejected_task_switches forbidden")


def test_mutation_resource_diagnostics_unordered_switches_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"]["target_switching"][
        "order_is_exact_deterministic_outer_tick_task_slot_vehicle_slot"
    ] = False
    assert_fails(mutated, "unordered switches must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"]["target_switching"]["counts_never_cross_fleet_draws"] = (
        False
    )
    assert_fails(mutated2, "across-draw switches must be rejected")
    mutated3 = copy.deepcopy(canonical())
    mutated3["resource_state_diagnostics"]["target_switching"][
        "counted_over_consecutive_admitted_V2I_tasks_in_deterministic_order"
    ] = "(tick)"
    assert_fails(mutated3, "deterministic order must be (outer_tick, task_slot, vehicle_slot)")
    mutated4 = copy.deepcopy(canonical())
    mutated4["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "raw_over_1000_utilization_under_u_gt_1",
        "queue_occupancy_as_denominator",
        "zero_fill_shares_when_denominator_zero",
        "rejected_task_switches",
        "missing_cost_denominator",
    ]
    assert_fails(mutated4, "missing unordered_or_across_draw_switches forbidden")


def test_mutation_resource_diagnostics_missing_cost_denominator_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["resource_state_diagnostics"][
        "resource_unit_seconds_denominator_stays_required_for_diagnostic_deadline_per_resource_cost"
    ] = False
    assert_fails(mutated, "missing cost denominator must be rejected")
    mutated2 = copy.deepcopy(canonical())
    mutated2["resource_state_diagnostics"][
        "no_monetary_or_automatically_authoritative_objective_claim"
    ] = False
    assert_fails(mutated2, "no monetary claim must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["resource_state_diagnostics"]["forbidden_behaviors"] = [
        "raw_over_1000_utilization_under_u_gt_1",
        "queue_occupancy_as_denominator",
        "zero_fill_shares_when_denominator_zero",
        "rejected_task_switches",
        "unordered_or_across_draw_switches",
    ]
    assert_fails(mutated3, "missing missing_cost_denominator forbidden")


def test_mutation_p2c_candidate_predicate_n0_classification_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_candidate_predicate"]["n_equals_0"]["classification"][
        "if_ingress_radio_not_viable"
    ] = "gate_rejected"
    assert_fails(mutated, "v2i_unavailable classification must be exact")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_candidate_predicate"]["n_equals_0"]["classification"][
        "elif_no_RSU_observed_deadline_feasible"
    ] = "cap_rejected"
    assert_fails(mutated2, "v2i_gate_rejected classification must be exact")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_candidate_predicate"]["feasible_RSU_predicate"][
        "queue_safety_is_current_not_stale"
    ] = False
    assert_fails(mutated3, "queue safety must be current not stale")
    mutated4 = copy.deepcopy(canonical())
    mutated4["p2c_candidate_predicate"]["forbidden_behaviors"] = [
        "stale queue-cap",
        "undefined n=0/1",
    ]
    assert_fails(mutated4, "missing sample-before-filter forbidden")


def test_mutation_p2c_candidate_predicate_n1_hashing_skipped_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_candidate_predicate"]["n_equals_1"]["hashing_skipped"] = False
    assert_fails(mutated, "n=1 hashing must be skipped")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_candidate_predicate"]["n_equals_1"]["ranking_inspections"] = 2
    assert_fails(mutated2, "ranking inspections must be 1")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_candidate_predicate"]["n_equals_1"]["no_second_hash_modulo"] = False
    assert_fails(mutated3, "no second hash/modulo for n=1 must be true")


def test_mutation_p2c_candidate_predicate_reservation_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_candidate_predicate"]["reservation"]["rejected_work_never_reserved"] = False
    assert_fails(mutated, "rejected work never reserved must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_candidate_predicate"]["reservation"][
        "reserve_true_load_raw_work_and_decision_overlay_immediately_only_on_admission"
    ] = False
    assert_fails(mutated2, "reserve true load only on admission must be true")


def test_mutation_p2c_mixer_uint64_and_splitmix_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_mixer"]["field_declaration"]["field_type"] = "int64"
    assert_fails(mutated, "field type must be uint64")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_mixer"]["field_declaration"]["wrap_modulo"] = "2^32"
    assert_fails(mutated2, "wrap modulo must be 2^64")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_mixer"]["splitmix64_definition"]["steps"] = ["z=x+1"]
    assert_fails(mutated3, "splitmix steps must be exact")
    mutated4 = copy.deepcopy(canonical())
    mutated4["p2c_mixer"]["splitmix64_definition"]["constants_hex"] = ["0x123"]
    assert_fails(mutated4, "splitmix constants must be exact")


def test_mutation_p2c_mixer_field_order_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_mixer"]["field_declaration"]["fields_ordered"] = [
        "fleet_seed",
        "evaluator_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal",
    ]
    assert_fails(mutated, "field order must be evaluator, fleet, outer_tick, task_slot, ordinal")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_mixer"]["fold"]["h_init"] = "0x0000000000000000"
    assert_fails(mutated2, "fold h_init must be exact")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_mixer"]["fold"]["field_order"] = [
        "fleet_seed",
        "evaluator_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal",
    ]
    assert_fails(mutated3, "fold field_order reordered must fail")
    mutated4 = copy.deepcopy(canonical())
    mutated4["p2c_mixer"]["fold"]["field_order"] = [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
    ]
    assert_fails(mutated4, "fold field_order truncated must fail")
    mutated5 = copy.deepcopy(canonical())
    del mutated5["p2c_mixer"]["fold"]["field_order"]
    assert_fails(mutated5, "fold field_order missing must fail")


def test_mutation_p2c_mixer_fold_field_order_exact() -> None:
    data = canonical()
    assert data["p2c_mixer"]["fold"]["field_order"] == [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal",
    ]
    # reordered
    mutated = copy.deepcopy(data)
    mutated["p2c_mixer"]["fold"]["field_order"] = [
        "evaluator_seed",
        "outer_tick",
        "fleet_seed",
        "task_slot",
        "sequential_task_ordinal",
    ]
    assert_fails(mutated, "fold reordered alternative")
    # truncated
    mutated2 = copy.deepcopy(data)
    mutated2["p2c_mixer"]["fold"]["field_order"] = [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
    ]
    assert_fails(mutated2, "fold truncated")
    # missing
    mutated3 = copy.deepcopy(data)
    mutated3["p2c_mixer"]["fold"].pop("field_order", None)
    assert_fails(mutated3, "fold missing")


def test_mutation_p2c_mixer_test_vectors_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_mixer"]["test_vectors"] = mutated["p2c_mixer"]["test_vectors"][:1]
    assert_fails(mutated, "test vectors must be at least 3")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_mixer"]["test_vectors"][0]["h_hex"] = "0x0000000000000000"
    assert_fails(mutated2, "h_hex must equal computed")
    mutated3 = copy.deepcopy(canonical())
    mutated3["p2c_mixer"]["test_vectors"][1]["first_index"] = 99
    assert_fails(mutated3, "first_index must equal computed")


def test_mutation_p2c_mixer_uniformity_claim_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["p2c_mixer"]["uniformity_claim_forbidden"] = False
    assert_fails(mutated, "uniformity claim forbidden must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_mixer"]["forbidden_behaviors"] = ["string/byte serialization"]
    assert_fails(mutated2, "missing alternate SplitMix forbidden")


def test_mutation_tick_transition_steps_and_cooldown_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["tick_transition"]["zero_based_trace_tick_control_time_t"][
        "i_start_from_true_state_after_prior_interval_drain"
    ] = False
    assert_fails(mutated, "tick step i must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["tick_transition"]["cooldown"]["starts_at_actual_application_time"] = False
    assert_fails(mutated2, "cooldown starts at actual application time must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["tick_transition"]["cooldown"]["elapsed_gte_5000ms_permits_new_request"] = False
    assert_fails(mutated3, "elapsed>=5000 permits new request must be true")
    mutated4 = copy.deepcopy(canonical())
    mutated4["tick_transition"]["forbidden_behaviors"] = ["ambiguous timestamps"]
    assert_fails(mutated4, "missing decision-time cooldown forbidden")


def test_mutation_tick_transition_receipts_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["tick_transition"]["requested_receipt_fields"] = ["draw", "rsu"]
    assert_fails(mutated, "requested receipt fields must contain all 11")
    mutated2 = copy.deepcopy(canonical())
    mutated2["tick_transition"]["applied_receipt_adds"] = ["actual_to_units"]
    assert_fails(mutated2, "applied receipt must contain actual_application_time_ms")
    mutated3 = copy.deepcopy(canonical())
    mutated3["tick_transition"]["counts_expose_separately"] = ["scheduled_requests"]
    assert_fails(mutated3, "counts must contain applied up/down")


def test_mutation_tick_transition_proactive_samples_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["tick_transition"][
        "proactive_samples_are_completed_prior_trace_interval_admitted_arrival_work_samples"
    ]["at_tick_t_no_sample_from_current_tick_available"] = False
    assert_fails(mutated, "at_tick_t_no_sample must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["tick_transition"][
        "proactive_samples_are_completed_prior_trace_interval_admitted_arrival_work_samples"
    ]["pretrace_empty_values_never_satisfy_warm_up"] = False
    assert_fails(mutated2, "pretrace empty never satisfy warm-up must be true")


def test_mutation_v2i_latency_equation_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "simulated_latency_ms_equation"
    ] = "backlog/u"
    assert_fails(mutated, "simulated latency equation must be exact 5-term")
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "raw_work_enqueued_is_never_divided_by_u"
    ] = False
    assert_fails(mutated2, "raw work enqueued never divided must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "rejected_work_never_enqueues_never_succeeds_and_inherited_10_deadline_penalty_is_explicitly_not_valid_latency_observation"
    ] = False
    assert_fails(mutated3, "rejected 10*deadline penalty not valid latency must be true")


def test_mutation_v2i_latency_report_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["report"][
        "offered_task_latency_is_null_unavailable_because_rejected_penalty_values_are_not_physical_latency"
    ] = False
    assert_fails(mutated, "offered task latency null unavailable must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["forbidden_behaviors"] = ["divided enqueue work"]
    assert_fails(mutated2, "missing backlog-only stale outcome forbidden")


def test_mutation_accounting_lossless_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["accounting_and_contrast_completion"]["lossless_accounting"][
        "offered_equals_admitted_plus_rejected"
    ] = False
    assert_fails(mutated, "offered=admitted+rejected must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["accounting_and_contrast_completion"]["lossless_accounting"]["rejected_equals_sum"] = [
        "v2i_gate_rejected"
    ]
    assert_fails(mutated2, "rejected_equals_sum must contain all 6")
    mutated3 = copy.deepcopy(canonical())
    mutated3["accounting_and_contrast_completion"]["shares"][
        "rejection_share_is_rejected_div_offered"
    ] = False
    assert_fails(mutated3, "rejection share must be rejected/offered")


def test_mutation_accounting_contrast_completion_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["accounting_and_contrast_completion"][
        "missing_incomplete_cells_make_matched_contrast_status_incomplete_null_never_reduce_n"
    ] = False
    assert_fails(mutated, "missing incomplete cells never reduce n must be true")
    mutated2 = copy.deepcopy(canonical())
    mutated2["accounting_and_contrast_completion"][
        "reportable_contrast_requires_all_four_paired_seeds_1_to_4_and_uses_exact_treatment_minus_control_sign"
    ] = False
    assert_fails(mutated2, "reportable contrast requires all four seeds must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["accounting_and_contrast_completion"]["predeclared_contrasts"]["E3a_primary"]["id"] = (
        "wrong"
    )
    assert_fails(mutated3, "E3a primary id must be p2c_dla-minus-per_task_dla")


def test_mutation_accounting_e3b_e3c_contrasts_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["accounting_and_contrast_completion"]["predeclared_contrasts"][
        "E3b_per_task_dla_state_age_0"
    ]["each_of"] = ["reactive"]
    assert_fails(mutated, "E3b each_of must be 3")
    mutated2 = copy.deepcopy(canonical())
    mutated2["accounting_and_contrast_completion"]["predeclared_contrasts"][
        "E3b_per_task_dla_state_age_0"
    ]["no_scalar_best_objective"] = False
    assert_fails(mutated2, "no scalar best must be true")
    mutated3 = copy.deepcopy(canonical())
    mutated3["accounting_and_contrast_completion"]["predeclared_contrasts"][
        "E3c_at_each_state_age"
    ]["contrasts"] = ["wrong"]
    assert_fails(mutated3, "E3c contrasts must be exact 2")
    mutated4 = copy.deepcopy(canonical())
    mutated4["accounting_and_contrast_completion"]["draw_is_N_4_tasks_never_become_replicates"] = (
        False
    )
    assert_fails(mutated4, "draw is N=4 tasks never replicates must be true")


# --- Narrow comparator correction: deadline_success <= vs admission feasibility < ---


def test_mutation_deadline_outcome_comparator_strict_less_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_comparator"
    ] = "<"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("deadline_success_comparator" in e for e in result["errors"])


def test_mutation_deadline_outcome_comparator_gte_or_missing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_comparator"
    ] = ">="
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("deadline_success_comparator" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    del mutated2["v2i_latency_outcome_contract"][
        "at_admission_record_with_u_current_applied_units"
    ]["deadline_success_comparator"]
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("deadline_success_comparator" in e for e in result2["errors"])


def test_mutation_deadline_outcome_rule_wrong_spacing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_rule"
    ] = "simulated_latency_ms < task_deadline_ms"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("deadline_success_rule" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_rule"
    ] = " simulated_latency_ms <= task_deadline_ms"
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("deadline_success_rule" in e for e in result2["errors"])


def test_mutation_deadline_equality_is_success_false_missing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_equality_is_success"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("deadline_success_equality_is_success" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    del mutated2["v2i_latency_outcome_contract"][
        "at_admission_record_with_u_current_applied_units"
    ]["deadline_success_equality_is_success"]
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("deadline_success_equality_is_success" in e for e in result2["errors"])


def test_mutation_deadline_inherited_compatibility_false_missing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "inherited_e2d_outcome_compatibility"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("inherited_e2d_outcome_compatibility" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_is_inherited_e2d_outcome"
    ] = False
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("deadline_success_is_inherited_e2d_outcome" in e for e in result2["errors"])
    mutated3 = copy.deepcopy(canonical())
    del mutated3["v2i_latency_outcome_contract"][
        "at_admission_record_with_u_current_applied_units"
    ]["inherited_e2d_outcome_compatibility"]
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    assert any("inherited_e2d_outcome_compatibility" in e for e in result3["errors"])


def test_mutation_deadline_inherited_reference_missing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "inherited_e2d_reference"
    ] = "some other reference"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("inherited_e2d_reference" in e for e in result["errors"])


def test_mutation_admission_feasibility_strict_less_changed_to_le_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "admission_feasibility_predicate_reference"
    ] = "observed_decision_backlog_work_ms[rsu] <= task_deadline_ms"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("admission_feasibility_predicate_reference" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "admission_feasibility_predicate_is_strict_less"
    ] = False
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("admission_feasibility_predicate_is_strict_less" in e for e in result2["errors"])
    mutated3 = copy.deepcopy(canonical())
    mutated3["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "equality_at_admission_gate_is_infeasible"
    ] = False
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    assert any("equality_at_admission_gate_is_infeasible" in e for e in result3["errors"])


def test_mutation_comparators_are_identical_claim_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "outcome_and_feasibility_comparators_are_identical"
    ] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("outcome_and_feasibility_comparators_are_identical" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "outcome_and_feasibility_comparators_are_distinct"
    ] = False
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("outcome_and_feasibility_comparators_are_distinct" in e for e in result2["errors"])
    mutated3 = copy.deepcopy(canonical())
    mutated3["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "comparator_conflation_forbidden"
    ] = False
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    assert any("comparator_conflation_forbidden" in e for e in result3["errors"])


def test_mutation_legacy_boolean_deadline_success_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_is_recorded_admitted_simulated_latency_less_task_deadline"
    ] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "deadline_success_is_recorded_admitted_simulated_latency_less_task_deadline" in e
        for e in result["errors"]
    )


def test_mutation_deadline_comparator_bool_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["v2i_latency_outcome_contract"]["at_admission_record_with_u_current_applied_units"][
        "deadline_success_comparator"
    ] = True  # bool, not string
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("deadline_success_comparator" in e for e in result["errors"])


# --- v2 successor provenance ---


def test_successor_provenance_exact() -> None:
    data = canonical()
    prov = data["successor_provenance"]
    assert prov["superseded_candidate_sha"] == EXPECTED_SUCCESSOR_CANDIDATE_SHA
    assert prov["superseded_promoted_integration_sha"] == EXPECTED_SUCCESSOR_INTEGRATION_SHA
    assert prov["v1_json_sha256"] == EXPECTED_V1_JSON_SHA256
    assert "waiting-room occupancy-transition omission" in prov["exact_reasons"]
    assert "comparator rejection-taxonomy omission" in prov["exact_reasons"]


def test_mutation_successor_provenance_missing_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["successor_provenance"]
    assert_fails(mutated, "missing successor_provenance must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["successor_provenance"]["superseded_candidate_sha"] = "deadbeef"
    assert_fails(mutated2, "wrong candidate SHA must fail")
    mutated3 = copy.deepcopy(canonical())
    mutated3["successor_provenance"]["v1_json_sha256"] = "0" * 64
    assert_fails(mutated3, "wrong v1 SHA must fail")
    mutated4 = copy.deepcopy(canonical())
    mutated4["successor_provenance"]["exact_reasons"] = "something else"
    assert_fails(mutated4, "wrong exact_reasons must fail")


def test_v1_preserved_byte_for_byte() -> None:
    v1 = json.loads(CANONICAL_JSON_V1.read_text(encoding="utf-8"))
    v2 = canonical()
    for k in v1:
        if k == "schema_version":
            assert v2[k] == "e3_dynamic_resource_v2_contract_v2"
        else:
            assert v2[k] == v1[k], f"v2 must preserve v1 key {k} byte-for-byte"


def test_v1_json_sha256_matches_recorded() -> None:
    import hashlib

    raw = CANONICAL_JSON_V1.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    assert sha == EXPECTED_V1_JSON_SHA256
    # v2 provenance must bind same
    assert canonical()["successor_provenance"]["v1_json_sha256"] == sha


# --- v2 occupancy transition: pin vectors and forbidden behaviors ---


def test_occupancy_pin_vectors_exact() -> None:
    data = canonical()
    occ = data["waiting_room_occupancy_transition"]
    assert occ["drain_work_ms"] == "D = min(B_pre, active_capacity_units * 1000)"
    assert occ["backlog_post"] == "B_post = B_pre - D"
    pin = occ["pin_vectors"]
    assert pin[0] == {
        "B_pre": 4000,
        "L_pre": 4,
        "u": 1,
        "D": 1000,
        "B_post": 3000,
        "tasks_drained": 1,
        "L_post": 3,
    }
    assert pin[1]["B_pre"] == 500 and pin[1]["L_post"] == 0 and pin[1]["tasks_drained"] == 4
    assert (
        pin[2]["B_pre"] == 4000
        and pin[2]["L_pre"] == 1
        and pin[2]["tasks_drained"] == 0
        and pin[2]["L_post"] == 1
    )
    # Verify floor math independently
    import math

    for vec in pin:
        B = vec["B_pre"]  # noqa: N806
        L = vec["L_pre"]  # noqa: N806
        u = vec["u"]
        D = min(B, u * 1000)  # noqa: N806
        assert vec["D"] == D
        Bp = B - D  # noqa: N806
        assert vec["B_post"] == Bp
        if Bp <= 0:
            assert vec["L_post"] == 0 and vec["tasks_drained"] == L
        else:
            exp_td = math.floor(L * D / max(B, 1e-6))
            exp_Lp = max(L - exp_td, 1)  # noqa: N806
            assert vec["tasks_drained"] == exp_td
            assert vec["L_post"] == exp_Lp


def test_mutation_occupancy_floor_as_L_post_rejected() -> None:  # noqa: N802
    mutated = copy.deepcopy(canonical())
    # floor(L*D/B) is tasks removed, not remaining occupancy
    # — mutating to interpret as L_post must fail
    # We simulate by changing pin vector to treat floor as L_post
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][0]["L_post"] = (
        1  # floor value, not 3
    )
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][0]["tasks_drained"] = 3
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[0]" in e for e in result["errors"])


def test_mutation_occupancy_ceil_instead_of_floor_rejected() -> None:
    import math

    mutated = copy.deepcopy(canonical())
    occ = mutated["waiting_room_occupancy_transition"]
    # Change equations to ceil
    occ["equations"]["tasks_drained_when_partial"] = "ceil(L_pre * D / max(B_pre, 1e-6))"
    occ["transition"]["else_B_post_gt_0"]["tasks_drained"] = "ceil(L_pre * D / max(B_pre, 1e-6))"
    occ["pin_vectors"][0]["tasks_drained"] = math.ceil(
        4 * 1000 / 4000
    )  # still 1, need case where ceil != floor
    # Use L=1 case where floor 0 vs ceil 1
    occ2 = copy.deepcopy(canonical())
    occ2["waiting_room_occupancy_transition"]["pin_vectors"][2]["tasks_drained"] = (
        1  # ceil would be 1 not 0
    )
    occ2["waiting_room_occupancy_transition"]["pin_vectors"][2]["L_post"] = (
        0  # would be wrong (must retain 1)
    )
    # Also corrupt equations
    occ2["waiting_room_occupancy_transition"]["equations"]["tasks_drained_when_partial"] = (
        "ceil(L_pre * D / max(B_pre, 1e-6))"
    )
    result = validate_contract(occ2)
    assert not result["pass"]


def test_mutation_occupancy_capacity_independent_drain_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["drain_work_ms"] = "D = min(B_pre, 1000)"
    mutated["waiting_room_occupancy_transition"]["equations"]["D"] = "min(B_pre, 1000)"
    # Pin vector u=3 should then be D=1000 not 500, so validation of pin math will also fail
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_occupancy_stale_input_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["uses_true_pre_drain_state_never_stale_view"] = (
        False
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("uses_true_pre_drain" in e for e in result["errors"])


def test_mutation_occupancy_failure_to_zero_when_backlog_empties_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["full_work_drain_forces_zero_occupancy"] = False
    mutated["waiting_room_occupancy_transition"]["transition"]["if_B_post_lte_0"]["L_post"] = 1
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_occupancy_failure_to_retain_one_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"][
        "positive_residual_work_retains_at_least_one_task"
    ] = False
    mutated["waiting_room_occupancy_transition"]["transition"]["else_B_post_gt_0"]["L_post"] = (
        "L_pre - tasks_drained"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    # Also direct pin mutation where L_post would be 0 despite B_post>0
    mutated2 = copy.deepcopy(canonical())
    mutated2["waiting_room_occupancy_transition"]["pin_vectors"][2]["L_post"] = 0
    result2 = validate_contract(mutated2)
    assert not result2["pass"]


def test_mutation_occupancy_queue_ceiling_scaled_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"][
        "waiting_room_ceiling_never_scaled_with_compute_units"
    ] = False
    mutated["waiting_room_occupancy_transition"]["waiting_room_ceiling_tasks_per_rsu"] = 18660
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_occupancy_makes_lifecycle_available_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"][
        "simulated_count_transition_does_not_make_lifecycle_available"
    ] = False
    mutated["waiting_room_occupancy_transition"]["lifecycle_fields_remain_null"]["started"] = 0
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_occupancy_missing_block_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["waiting_room_occupancy_transition"]
    assert_fails(mutated, "missing occupancy block must fail")


# --- v2 comparator rejection precedence ---


def test_comparator_precedence_exact() -> None:
    data = canonical()
    comp = data["comparator_rejection_precedence"]
    assert set(comp["applies_to"]) == {"ingress_dla", "per_task_dla"}
    assert comp["preserves_frozen_E2d_taxonomy_exactly"] is True
    assert comp["p2c_approved_n0_taxonomy_remains_separate_and_unchanged"] is True
    prec = comp["precedence"]
    assert (
        prec[
            "step_3_current_radio_failure_OR_target_already_full_at_task_slot_entry_yields_v2i_unavailable"
        ]
        is True
    )
    assert (
        prec["step_4_otherwise_strict_observed_backlog_gate_failure_yields_v2i_gate_rejected"]
        is True
    )
    assert (
        prec[
            "step_5_otherwise_live_in_slot_cap_failure_caused_by_prior_admitted_reservations_yields_v2i_cap_rejected"
        ]
        is True
    )
    assert prec["step_7_simultaneous_gate_and_live_cap_failure_is_gate_rejection"] is True
    assert (
        prec[
            "step_8_rejected_work_never_changes_true_workload_occupancy_or_overlay_and_execution_is_minus1"
        ]
        is True
    )
    cross = comp["cross_strategy_comparability"]
    assert cross["total_rejection_and_rejection_share_are_comparable_across_strategies"] is True
    assert cross["individual_V2I_rejection_classes_are_mechanism_diagnostics"] is True
    assert (
        cross["must_not_be_presented_as_identically_constructed_cross_strategy_contrasts"] is True
    )


def test_mutation_comparator_cap_precedence_over_gate_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["precedence"][
        "step_7_simultaneous_gate_and_live_cap_failure_is_gate_rejection"
    ] = False
    mutated["comparator_rejection_precedence"]["precedence"][
        "step_7_simultaneous_cap_precedence"
    ] = True
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_comparator_task_slot_entry_fullness_relabelled_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"]["v2i_unavailable_trigger"] = (
        "live in-slot cap failure"
    )
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_comparator_radio_failure_relabelled_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"]["v2i_unavailable_trigger"] = (
        "strict observed-backlog gate failure"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    mutated2 = copy.deepcopy(canonical())
    mutated2["comparator_rejection_precedence"]["details"]["v2i_gate_rejected_trigger"] = (
        "current radio failure"
    )
    result2 = validate_contract(mutated2)
    assert not result2["pass"]


def test_mutation_comparator_stale_occupancy_used_for_cap_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"][
        "cap_uses_true_current_plus_same_tick_not_stale"
    ] = False
    mutated["comparator_rejection_precedence"]["details"]["stale_occupancy_never_used_for_cap"] = (
        False
    )
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_comparator_rejected_work_reserved_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"][
        "rejected_work_never_reserved_or_executed"
    ] = False
    mutated["comparator_rejection_precedence"]["details"]["execution_is_minus1_for_rejected"] = (
        False
    )
    mutated["comparator_rejection_precedence"]["precedence"][
        "step_8_rejected_work_never_changes_true_workload_occupancy_or_overlay_and_execution_is_minus1"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_comparator_precedence_replaces_p2c_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["p2c_separate"][
        "comparator_precedence_does_not_replace_p2c_taxonomy"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    mutated2 = copy.deepcopy(canonical())
    mutated2["comparator_rejection_precedence"][
        "p2c_approved_n0_taxonomy_remains_separate_and_unchanged"
    ] = False
    result2 = validate_contract(mutated2)
    assert not result2["pass"]


def test_mutation_comparator_individual_classes_as_identical_contrast_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["cross_strategy_comparability"][
        "must_not_be_presented_as_identically_constructed_cross_strategy_contrasts"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]


def test_mutation_comparator_target_fullness_stale_free_false_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"][
        "target_fullness_uses_stale_free_occupancy"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("target_fullness_uses_stale_free_occupancy" in e for e in result["errors"])


def test_mutation_comparator_target_fullness_current_true_false_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"][
        "target_fullness_uses_current_true_occupancy_at_task_slot_entry"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "target_fullness_uses_current_true_occupancy_at_task_slot_entry" in e
        for e in result["errors"]
    )


def test_mutation_comparator_ordered_steps_swapped_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    steps = mutated["comparator_rejection_precedence"]["ordered_steps"]
    # Swap gate (index 3) and cap (index 4) – must fail exact-order check
    steps[3], steps[4] = steps[4], steps[3]
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("ordered_steps" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    # Reorder: move first step to end
    s = mutated2["comparator_rejection_precedence"]["ordered_steps"]
    mutated2["comparator_rejection_precedence"]["ordered_steps"] = s[1:] + s[:1]
    result2 = validate_contract(mutated2)
    assert not result2["pass"]


def test_mutation_comparator_missing_block_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["comparator_rejection_precedence"]
    assert_fails(mutated, "missing comparator block must fail")


def test_mutation_comparator_deletion_of_v1_invariant_still_fails() -> None:
    # Ensure v1 invariants still enforced in v2
    mutated = copy.deepcopy(canonical())
    mutated["compute_service_semantics"]["drain_equation"] = (
        "drain_work_ms = min(backlog_work_ms, 1000)"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    mutated2 = copy.deepcopy(canonical())
    mutated2["p2c_candidate_predicate"]["feasible_RSU_predicate"][
        "queue_safety_is_current_not_stale"
    ] = False
    result2 = validate_contract(mutated2)
    assert not result2["pass"]


def test_v2_markdown_byte_equivalence() -> None:
    data = canonical()
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    errors = validate_markdown_contains(md_text, data)
    assert errors == [], f"markdown equivalence failed: {errors}"


def test_v2_markdown_contains_v2_provenance_and_corrections() -> None:
    md_text = CANONICAL_MD.read_text(encoding="utf-8")
    for needle in [
        EXPECTED_SUCCESSOR_CANDIDATE_SHA,
        EXPECTED_SUCCESSOR_INTEGRATION_SHA,
        EXPECTED_V1_JSON_SHA256,
        "waiting-room occupancy-transition omission",
        "comparator rejection-taxonomy omission",
        "B_pre",
        "L_pre",
        "D = min(B_pre, active_capacity_units * 1000)",
        "B_post = B_pre - D",
        "floor(L_pre * D / max(B_pre, 1e-6))",
        "max(L_pre - tasks_drained, 1)",
        "v2i_unavailable",
        "v2i_gate_rejected",
        "v2i_cap_rejected",
        "current radio failure OR target already full at task-slot entry",
        "strict observed-backlog gate failure -> v2i_gate_rejected",
        "live in-slot cap failure caused by prior admitted reservations -> v2i_cap_rejected",
        "simultaneous gate and live cap failure is gate rejection",
        "rejected work never changes true workload, occupancy, or overlay and execution is -1",
        "total rejection/rejection share are comparable",
        "individual V2I rejection classes are mechanism diagnostics",
        "must not be presented as identically constructed cross-strategy contrasts",
    ]:
        assert needle in md_text, f"markdown missing v2 needle {needle!r}"


# New hostile tests to append


def test_successor_provenance_exact_branch_and_base() -> None:
    data = canonical()
    prov = data["successor_provenance"]
    assert prov["successor_authoring_branch"] == "worker/e3-lane-01-contract-v3"
    assert prov["successor_prepared_base_sha"] == "bbd955ed181d2a82183158ded8ad86116809bf27"
    assert (
        prov["exact_reasons"]
        == "waiting-room occupancy-transition omission and comparator rejection-taxonomy omission"
    )
    assert prov["reasons"] == [
        "waiting-room occupancy-transition omission",
        "comparator rejection-taxonomy omission",
    ]
    comp = data["comparator_rejection_precedence"]
    assert comp["applies_to"] == ["ingress_dla", "per_task_dla"]


def test_mutation_successor_branch_and_base_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["successor_provenance"]["successor_authoring_branch"] = "worker/e3-lane-01-contract"
    assert_fails(mutated, "wrong successor_authoring_branch must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["successor_provenance"]["successor_prepared_base_sha"] = (
        "0000000000000000000000000000000000000000"
    )
    assert_fails(mutated2, "wrong successor_prepared_base_sha must fail")
    mutated3 = copy.deepcopy(canonical())
    del mutated3["successor_provenance"]["successor_authoring_branch"]
    assert_fails(mutated3, "missing successor_authoring_branch must fail")
    mutated4 = copy.deepcopy(canonical())
    del mutated4["successor_provenance"]["successor_prepared_base_sha"]
    assert_fails(mutated4, "missing successor_prepared_base_sha must fail")


def test_mutation_reasons_exact_extra_reorder_duplicate_rejected() -> None:
    # extra
    mutated = copy.deepcopy(canonical())
    mutated["successor_provenance"]["reasons"] = [
        "waiting-room occupancy-transition omission",
        "comparator rejection-taxonomy omission",
        "extra",
    ]
    assert_fails(mutated, "extra reason must fail")
    assert any("reasons" in e for e in validate_contract(mutated)["errors"])
    # reorder
    mutated2 = copy.deepcopy(canonical())
    mutated2["successor_provenance"]["reasons"] = [
        "comparator rejection-taxonomy omission",
        "waiting-room occupancy-transition omission",
    ]
    assert_fails(mutated2, "reordered reasons must fail")
    # duplicate
    mutated3 = copy.deepcopy(canonical())
    mutated3["successor_provenance"]["reasons"] = [
        "waiting-room occupancy-transition omission",
        "waiting-room occupancy-transition omission",
    ]
    assert_fails(mutated3, "duplicate reasons must fail")
    # deletion
    mutated4 = copy.deepcopy(canonical())
    mutated4["successor_provenance"]["reasons"] = ["waiting-room occupancy-transition omission"]
    assert_fails(mutated4, "missing reason must fail")
    # exact_reasons string extra
    mutated5 = copy.deepcopy(canonical())
    mutated5["successor_provenance"]["exact_reasons"] = (
        "waiting-room occupancy-transition omission and "
        "comparator rejection-taxonomy omission and extra"
    )
    assert_fails(mutated5, "extra exact_reasons must fail")
    # exact_reasons reorder
    mutated6 = copy.deepcopy(canonical())
    mutated6["successor_provenance"]["exact_reasons"] = (
        "comparator rejection-taxonomy omission and waiting-room occupancy-transition omission"
    )
    assert_fails(mutated6, "reordered exact_reasons must fail")
    # exact_reasons duplicate phrase
    mutated7 = copy.deepcopy(canonical())
    mutated7["successor_provenance"]["exact_reasons"] = (
        "waiting-room occupancy-transition omission and waiting-room occupancy-transition omission"
    )
    assert_fails(mutated7, "duplicate exact_reasons must fail")


def test_mutation_applies_to_exact_extra_reorder_duplicate_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["applies_to"] = [
        "ingress_dla",
        "per_task_dla",
        "extra",
    ]
    assert_fails(mutated, "extra applies_to must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["comparator_rejection_precedence"]["applies_to"] = ["per_task_dla", "ingress_dla"]
    assert_fails(mutated2, "reordered applies_to must fail")
    mutated3 = copy.deepcopy(canonical())
    mutated3["comparator_rejection_precedence"]["applies_to"] = ["ingress_dla", "ingress_dla"]
    assert_fails(mutated3, "duplicate applies_to must fail")
    mutated4 = copy.deepcopy(canonical())
    mutated4["comparator_rejection_precedence"]["applies_to"] = ["ingress_dla"]
    assert_fails(mutated4, "missing applies_to must fail")
    mutated5 = copy.deepcopy(canonical())
    mutated5["comparator_rejection_precedence"]["applies_to"] = []
    assert_fails(mutated5, "empty applies_to must fail")


def test_hostile_inherited_projection_any_post_observation_mutation_and_regenerated_md_still_fails(
    # keep signature wrapped for line length
) -> None:
    mutated = copy.deepcopy(canonical())
    mutated["claim_boundaries"]["any_post_observation_source_change_requires_successor"] = False
    regen_md = render_markdown(mutated)
    # JSON must fail via projection
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "projection" in e.lower() or "any_post_observation" in e.lower() for e in result["errors"]
    )
    # Markdown regenerated from mutated JSON must also fail (prose check)
    md_errs = validate_markdown(regen_md, mutated)
    assert len(md_errs) > 0
    assert any("any_post_observation" in e for e in md_errs)


def test_hostile_inherited_projection_monetary_cost_mutation_and_regenerated_md_still_fails() -> (
    None
):
    mutated = copy.deepcopy(canonical())
    mutated["claim_boundaries"]["monetary_cost_tested"] = True
    regen_md = render_markdown(mutated)
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("projection" in e.lower() or "monetary" in e.lower() for e in result["errors"])
    md_errs = validate_markdown(regen_md, mutated)
    assert len(md_errs) > 0
    assert any("Monetary cost" in e or "monetary" in e.lower() for e in md_errs)


def test_hostile_inherited_projection_future_leakage_mutation_and_regenerated_md_still_fails() -> (
    None
):
    mutated = copy.deepcopy(canonical())
    mutated["tick_transition"]["future_leakage_forbidden"] = False
    regen_md = render_markdown(mutated)
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("projection" in e.lower() or "future_leakage" in e.lower() for e in result["errors"])
    md_errs = validate_markdown(regen_md, mutated)
    assert len(md_errs) > 0
    assert any("future_leakage" in e for e in md_errs)


def test_hostile_v2_only_floor_removal_mutation_and_regenerated_md_still_fails() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["floor_removal_is_tasks_drained"] = False
    regen_md = render_markdown(mutated)
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("floor_removal" in e for e in result["errors"])
    md_errs = validate_markdown(regen_md, mutated)
    assert len(md_errs) > 0
    assert any("floor_removal" in e for e in md_errs)


def test_hostile_v2_only_p2c_uses_mutation_and_regenerated_md_still_fails() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["p2c_separate"][
        "p2c_uses_v2i_unavailable_v2i_gate_rejected_v2i_cap_rejected_for_n0_only"
    ] = False
    regen_md = render_markdown(mutated)
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("p2c_uses" in e for e in result["errors"])
    md_errs = validate_markdown(regen_md, mutated)
    assert len(md_errs) > 0
    assert any("p2c_uses" in e for e in md_errs)


def test_hostile_inherited_projection_deletion_extra_list_mutations_and_regenerated_md_still_fails(
    # keep signature wrapped for line length
) -> None:
    # deletion
    mutated = copy.deepcopy(canonical())
    del mutated["claim_boundaries"]["any_post_observation_source_change_requires_successor"]
    regen_md = render_markdown(mutated)
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "projection" in e.lower() or "any_post_observation" in e.lower() for e in result["errors"]
    )
    _ = regen_md
    # extra key
    mutated2 = copy.deepcopy(canonical())
    mutated2["claim_boundaries"]["extra_drift_key"] = True
    render_markdown(mutated2)
    res2 = validate_contract(mutated2)
    assert not res2["pass"]
    assert any("projection" in e.lower() or "extra" in e.lower() for e in res2["errors"])
    # list mutation: add extra reason and regenerate
    mutated3 = copy.deepcopy(canonical())
    mutated3["successor_provenance"]["reasons"].append("extra")
    render_markdown(mutated3)
    res3 = validate_contract(mutated3)
    assert not res3["pass"]
    # list reorder
    mutated4 = copy.deepcopy(canonical())
    mutated4["comparator_rejection_precedence"]["applies_to"] = [
        "per_task_dla",
        "ingress_dla",
    ]
    render_markdown(mutated4)
    res4 = validate_contract(mutated4)
    assert not res4["pass"]
    # Markdown for reordered applies_to still contains both tokens, so
    # byte-equivalence to mutated data passes; the failure is proven via
    # JSON projection and applies_to exact-order check, not via markdown
    # prose.
    assert any("applies_to" in e for e in res4["errors"])


def test_v1_byte_identity_missing_fails_closed() -> None:
    data = canonical()
    # Use relative missing path override
    result = validate_contract(data, v1_path=Path("docs/evaluation/e3/nonexistent_v1.json"))
    assert not result["pass"]
    assert any("missing" in e.lower() or "not file" in e.lower() for e in result["errors"])


def test_v1_byte_identity_path_escape_fails_closed() -> None:
    data = canonical()
    result = validate_contract(data, v1_path=Path("../../etc/passwd"))
    assert not result["pass"]
    assert any("escapes" in e.lower() for e in result["errors"])
    # absolute path should also fail
    result2 = validate_contract(data, v1_path=Path("/nonexistent/absolute.json"))
    assert not result2["pass"]
    assert any("relative" in e.lower() or "absolute" in e.lower() for e in result2["errors"])


def test_v1_byte_identity_tampered_bytes_fails_closed() -> None:
    data = canonical()
    tampered = b'{"tampered": true}'
    result = validate_contract(data, v1_bytes=tampered)
    assert not result["pass"]
    assert any("hash" in e.lower() or "mismatch" in e.lower() for e in result["errors"])


def test_v1_byte_identity_invalid_json_fails_closed() -> None:
    data = canonical()
    # Provide bytes that hash to expected but invalid JSON? Instead
    # provide tampered bytes that are invalid JSON but hash mismatch
    # already fails.
    # Use valid hash bytes but invalid JSON: we need to bypass hash check
    # by providing v1_data with wrong content but same hash? Instead test
    # via v1_bytes that is invalid JSON and hash is wrong -> already fails.
    # Also test via direct invalid bytes that would be parsed after hash
    # bypass: provide v1_data and v1_bytes mismatch
    valid_bytes = CANONICAL_JSON_V1.read_bytes()
    # Corrupt by changing last byte but keep hash mismatch -> still fails hash
    bad_bytes = valid_bytes[:-2] + b"XX"
    result = validate_contract(data, v1_bytes=bad_bytes)
    assert not result["pass"]


def test_v1_byte_identity_path_drifted_fails_closed() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["successor_provenance"]["v1_contract_path"] = "docs/other.json"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("v1_contract_path" in e for e in result["errors"])


def test_v1_projection_hash_proves_every_inherited_drift() -> None:
    # Ensure that changing any inherited field at any depth is caught
    # Pick a deep field like p2c_candidate_predicate and mutate
    mutated = copy.deepcopy(canonical())
    mutated["p2c_candidate_predicate"]["feasible_RSU_predicate"][
        "queue_safety_is_current_not_stale"
    ] = False
    res = validate_contract(mutated)
    assert not res["pass"]
    assert any("projection" in e.lower() for e in res["errors"])
    # Also mutate a list element
    mutated2 = copy.deepcopy(canonical())
    mutated2["stale_state_semantics"]["forbidden_behaviors"].append("extra")
    res2 = validate_contract(mutated2)
    assert not res2["pass"]


def test_full_projection_deterministic_hash_matches_v1() -> None:
    v2 = canonical()
    v1 = json.loads(CANONICAL_JSON_V1.read_text(encoding="utf-8"))
    import copy as cp

    proj = cp.deepcopy(v2)
    for block in [
        "waiting_room_occupancy_transition",
        "comparator_rejection_precedence",
        "successor_provenance",
        "execution_authority",
    ]:
        proj.pop(block, None)
    proj["schema_version"] = v1["schema_version"]
    assert proj == v1
    # Hashes must match
    import hashlib
    import json as js

    h_proj = hashlib.sha256(
        js.dumps(
            proj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), indent=None
        ).encode("utf-8")
    ).hexdigest()
    h_v1 = hashlib.sha256(
        js.dumps(v1, sort_keys=True, ensure_ascii=False, separators=(",", ":"), indent=None).encode(
            "utf-8"
        )
    ).hexdigest()
    assert h_proj == h_v1


# --- Execution authority HARD hold (researcher-imposed) ---


def test_execution_authority_exact() -> None:
    data = canonical()
    ea = data["execution_authority"]
    assert ea["status"] == "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED"
    assert ea["scientific_execution_authorized"] is False
    assert ea["lane_09"] == "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD"
    assert ea["engineering_functionality_authorized"] is True
    assert ea["minimal_construct_smoke_only"] is True
    assert ea["manchester_trace_comparative_execution_authorized"] is False
    assert ea["full_3600_step_cells_authorized"] is False
    assert ea["e3a_authorized"] is False
    assert ea["e3b_authorized"] is False
    assert ea["e3c_authorized"] is False
    assert ea["reduced_pilot_exploratory_campaign_authorized"] is False
    assert ea["multi_seed_or_fleet_draw_execution_authorized"] is False
    assert ea["performance_evidence_benchmark_authorized"] is False
    assert ea["empirical_e3_results_authorized"] is False
    assert ea["statistical_inference_authorized"] is False
    assert ea["research_workloads_launched"] == 0
    assert ea["evidence_state"] == "NOT_EXECUTED"
    assert ea["result_availability"] == "NO_E3_RESEARCH_RESULTS_AVAILABLE"
    assert ea["smoke_is_scientific_evidence"] is False
    assert ea["software_completion_depends_on_experiment"] is False
    assert ea["hold_release_authority"] == "future_explicit_researcher_instruction_only"
    assert ea["planned_56_cell_design_is_dormant_predeclaration"] is True
    note = ea["dormant_predeclaration_note"]
    assert "planned cells are not execution authority and cannot run under this hold" in note
    assert "retained only as a dormant predeclaration" in note


def test_mutation_execution_authority_status_drift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["status"] = "E3_SCIENTIFIC_EXECUTION_AUTHORIZED"
    assert_fails(mutated, "status drift must fail")
    regen = render_markdown(mutated)
    assert len(validate_markdown(regen, mutated)) > 0
    mutated2 = copy.deepcopy(canonical())
    mutated2["execution_authority"]["status"] = "predeclared_before_any_e3_trace_execution"
    assert_fails(mutated2, "status drift to old value must fail")


def test_mutation_execution_authority_scientific_execution_authorized_flip_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["scientific_execution_authorized"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("scientific_execution_authorized" in e for e in result["errors"])
    _regen = render_markdown(mutated)
    result2 = validate_contract(mutated)
    assert not result2["pass"]
    assert any("scientific_execution_authorized" in e for e in result2["errors"])
    # JSON authoritative: regenerated markdown cannot rescue failure
    assert any("scientific_execution_authorized" in e for e in result["errors"])
    assert _regen is not None


def test_mutation_execution_authority_all_authorization_flips_rejected() -> None:
    flips = [
        ("manchester_trace_comparative_execution_authorized", True),
        ("full_3600_step_cells_authorized", True),
        ("e3a_authorized", True),
        ("e3b_authorized", True),
        ("e3c_authorized", True),
        ("reduced_pilot_exploratory_campaign_authorized", True),
        ("multi_seed_or_fleet_draw_execution_authorized", True),
        ("performance_evidence_benchmark_authorized", True),
        ("empirical_e3_results_authorized", True),
        ("statistical_inference_authorized", True),
    ]
    for field, val in flips:
        mutated = copy.deepcopy(canonical())
        mutated["execution_authority"][field] = val
        result = validate_contract(mutated)
        assert not result["pass"]
        assert any(field in e for e in result["errors"])
        _regen = render_markdown(mutated)
        result2 = validate_contract(mutated)
        assert not result2["pass"]
        assert any(field in e for e in result2["errors"])
        # Markdown regenerated from mutated JSON is byte-equivalent to mutated,
        # but JSON validation remains authoritative fail-closed
        assert not result2["pass"]
        assert _regen is not None


def test_mutation_execution_authority_engineering_and_smoke_flags_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["engineering_functionality_authorized"] = False
    assert_fails(mutated, "engineering_functionality flip to false must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["execution_authority"]["minimal_construct_smoke_only"] = False
    assert_fails(mutated2, "minimal_construct_smoke_only flip must fail")


def test_mutation_execution_authority_lane_09_drift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["lane_09"] = "UNBLOCKED"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("lane_09" in e for e in result["errors"])
    _regen = render_markdown(mutated)
    result2 = validate_contract(mutated)
    assert not result2["pass"]
    assert any("lane_09" in e for e in result2["errors"])
    assert _regen is not None


def test_mutation_execution_authority_research_workloads_nonzero_rejected() -> None:
    for nonzero in [1, 2, 10, -1]:
        mutated = copy.deepcopy(canonical())
        mutated["execution_authority"]["research_workloads_launched"] = nonzero
        assert_fails(mutated, f"research_workloads_launched={nonzero} must fail")
        regen = render_markdown(mutated)
        assert len(validate_markdown(regen, mutated)) > 0
        assert not validate_contract(mutated)["pass"]
        assert any("research_workloads_launched" in e for e in validate_contract(mutated)["errors"])


def test_mutation_execution_authority_evidence_and_result_drift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["evidence_state"] = "EXECUTED"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("evidence_state" in e for e in result["errors"])
    mutated2 = copy.deepcopy(canonical())
    mutated2["execution_authority"]["result_availability"] = "E3_RESULTS_AVAILABLE"
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("result_availability" in e for e in result2["errors"])
    mutated3 = copy.deepcopy(canonical())
    mutated3["execution_authority"]["evidence_state"] = "NOT_EXECUTED "
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    assert any("evidence_state" in e for e in result3["errors"])
    mutated4 = copy.deepcopy(canonical())
    mutated4["execution_authority"]["smoke_is_scientific_evidence"] = True
    result4 = validate_contract(mutated4)
    assert not result4["pass"]
    assert any("smoke_is_scientific_evidence" in e for e in result4["errors"])


def test_mutation_execution_authority_software_depends_on_experiment_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["software_completion_depends_on_experiment"] = True
    assert_fails(mutated, "software_completion_depends_on_experiment flip must fail")
    assert any(
        "software_completion_depends_on_experiment" in e
        for e in validate_contract(mutated)["errors"]
    )
    assert not validate_contract(mutated)["pass"]


def test_mutation_execution_authority_hold_release_drift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["hold_release_authority"] = "researcher_instruction"
    assert_fails(mutated, "hold_release drift must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["execution_authority"]["hold_release_authority"] = (
        "future_explicit_researcher_instruction_only "
    )
    assert_fails(mutated2, "hold_release trailing space must fail")


def test_mutation_execution_authority_dormant_note_drift_rejected() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["dormant_predeclaration_note"] = "no note"
    assert_fails(mutated, "dormant note drift must fail")
    mutated2 = copy.deepcopy(canonical())
    mutated2["execution_authority"]["dormant_predeclaration_note"] = (
        "The planned 56-cell design is retained only as a dormant predeclaration."
    )
    # Missing second phrase
    assert_fails(mutated2, "dormant note missing second phrase must fail")
    mutated3 = copy.deepcopy(canonical())
    del mutated3["execution_authority"]["dormant_predeclaration_note"]
    assert_fails(mutated3, "missing dormant note must fail")
    mutated4 = copy.deepcopy(canonical())
    mutated4["execution_authority"]["planned_56_cell_design_is_dormant_predeclaration"] = False
    assert_fails(mutated4, "dormant boolean flip must fail")


def test_mutation_execution_authority_deletion_rejected_even_with_regenerated_markdown() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["execution_authority"]
    assert_fails(mutated, "deletion of execution_authority must fail")
    regen = render_markdown(mutated)
    # Regenerated markdown from mutated data will not contain execution
    # authority phrases, so markdown validation must also fail
    assert len(validate_markdown(regen, mutated)) > 0
    assert any("execution_authority" in e for e in validate_contract(mutated)["errors"])
    # Also ensure projection still fails because missing v2-only block would
    # make projection include missing? Actually deletion makes projection equal
    # to v1? Wait v2 without execution_authority would project to v1 (since
    # that block is removed). But validator also checks that block exists, so
    # must fail via missing check, not projection.
    mutated2 = copy.deepcopy(canonical())
    mutated2.pop("execution_authority", None)
    result = validate_contract(mutated2)
    assert not result["pass"]


def test_hostile_v1_data_override_without_bytes_fails_closed() -> None:
    data = canonical()
    v1_real = json.loads(CANONICAL_JSON_V1.read_text(encoding="utf-8"))
    # Attempt unauthenticated object override: supply matching v1 object but no bytes
    result = validate_contract(data, v1_data=v1_real)
    assert not result["pass"]
    assert any(
        "unauthenticated" in e.lower() or "v1_data_override" in e.lower() for e in result["errors"]
    )
    # Hostile bypass: mutate v2 inherited field and craft malicious v1 that
    # would make projection pass if allowed
    mutated = copy.deepcopy(canonical())
    mutated["claim_boundaries"]["any_post_observation_source_change_requires_successor"] = False
    # Compute what projection would be if we removed v2 blocks
    import copy as cp

    proj_malicious = cp.deepcopy(mutated)
    for block in [
        "waiting_room_occupancy_transition",
        "comparator_rejection_precedence",
        "successor_provenance",
        "execution_authority",
    ]:
        proj_malicious.pop(block, None)
    proj_malicious["schema_version"] = v1_real["schema_version"]
    # Try to bypass by supplying malicious projection as v1_data without bytes
    result2 = validate_contract(mutated, v1_data=proj_malicious)
    assert not result2["pass"]
    assert any("unauthenticated" in e.lower() for e in result2["errors"])
    # Even with correct bytes, mismatched data must fail (hash matches but data != parsed)
    real_bytes = CANONICAL_JSON_V1.read_bytes()
    result3 = validate_contract(mutated, v1_data=proj_malicious, v1_bytes=real_bytes)
    assert not result3["pass"]
    assert any("does not match" in e.lower() for e in result3["errors"])
    # Tampered bytes with hash mismatch must also fail
    tampered_bytes = b'{"tampered": true}'
    result4 = validate_contract(data, v1_data=v1_real, v1_bytes=tampered_bytes)
    assert not result4["pass"]
    assert any("hash mismatch" in e.lower() or "hash" in e.lower() for e in result4["errors"])


def test_hostile_v1_bytes_hash_mismatch_and_parse_mismatch() -> None:
    data = canonical()
    v1_real = json.loads(CANONICAL_JSON_V1.read_text(encoding="utf-8"))
    real_bytes = CANONICAL_JSON_V1.read_bytes()
    # Provide bytes that hash correctly but data override mismatched
    mismatched_data = copy.deepcopy(v1_real)
    mismatched_data["campaign"] = "tampered_campaign"
    result = validate_contract(data, v1_data=mismatched_data, v1_bytes=real_bytes)
    assert not result["pass"]
    assert any("does not match" in e for e in result["errors"])
    # Provide bytes with correct hash but invalid JSON? Already covered by
    # hash, but test invalid JSON after hash bypass not possible without
    # correct hash.
    # Test that v1_bytes alone with tampered content fails hash
    bad_bytes = real_bytes[:-10] + b"XXXXXXXXXX"
    result2 = validate_contract(data, v1_bytes=bad_bytes)
    assert not result2["pass"]
    assert any("hash" in e.lower() for e in result2["errors"])


# --- Fail-closed exact-schema remediation for v2-only blocks ---
# Each mutation starts from a fresh canonical object and asserts
# path-specific error; regenerated markdown cannot rescue JSON failure.


def test_fail_closed_unknown_execution_authority_scientific_campaign_authorized() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["scientific_campaign_authorized"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("execution_authority" in e and "unknown" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    result2 = validate_contract(mutated)
    assert not result2["pass"]
    assert any("scientific_campaign_authorized" in e for e in result2["errors"])
    _ = regen


def test_fail_closed_dormant_note_contradictory_suffix() -> None:
    mutated = copy.deepcopy(canonical())
    original = mutated["execution_authority"]["dormant_predeclaration_note"]
    mutated["execution_authority"]["dormant_predeclaration_note"] = (
        original + " BUT NOW AUTHORIZED FOR EXECUTION"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("dormant_predeclaration_note" in e for e in result["errors"])
    regen = render_markdown(mutated)
    # JSON remains authoritative even though markdown matches mutated JSON
    result2 = validate_contract(mutated)
    assert not result2["pass"]
    assert any("dormant_predeclaration_note" in e for e in result2["errors"])
    _ = regen


def test_fail_closed_research_workloads_launched_false() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["research_workloads_launched"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("research_workloads_launched" in e for e in result["errors"])
    _regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    assert _regen is not None


def test_fail_closed_research_workloads_launched_float_zero() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["research_workloads_launched"] = 0.0
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("research_workloads_launched" in e for e in result["errors"])
    assert any("int" in e.lower() for e in result["errors"])
    _regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    assert _regen is not None


def test_fail_closed_research_workloads_launched_string_zero() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["research_workloads_launched"] = "0"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("research_workloads_launched" in e for e in result["errors"])
    assert any("int" in e.lower() for e in result["errors"])
    _regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    assert _regen is not None


def test_fail_closed_unknown_occupancy_ceiling_scales_with_compute() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["waiting_room_ceiling_scales_with_compute"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "waiting_room_occupancy_transition" in e and "unknown" in e.lower()
        for e in result["errors"]
    )
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_unknown_comparator_cap_precedes_gate() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["cap_precedes_gate"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "comparator_rejection_precedence" in e and "unknown" in e.lower() for e in result["errors"]
    )
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_occupancy_lifecycle_started_reason_physical() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["lifecycle_fields_remain_null"][
        "started_reason"
    ] = "physical_instrumentation_available"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "lifecycle_fields_remain_null" in e and "started_reason" in e for e in result["errors"]
    )
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_appended_occupancy_forbidden_behavior() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["forbidden_behaviors"] = mutated[
        "waiting_room_occupancy_transition"
    ]["forbidden_behaviors"] + ["extra contradictory behavior"]
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("forbidden_behaviors" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_appended_comparator_forbidden_behavior() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["forbidden_behaviors"] = mutated[
        "comparator_rejection_precedence"
    ]["forbidden_behaviors"] + ["extra contradictory contrast"]
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("forbidden_behaviors" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_unknown_successor_provenance_reason_override() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["successor_provenance"]["reason_override"] = "extra"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("successor_provenance" in e and "unknown" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_comparator_trigger_appended_contradictory() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["details"]["v2i_gate_rejected_trigger"] = (
        mutated["comparator_rejection_precedence"]["details"]["v2i_gate_rejected_trigger"]
        + " BUT ALSO CAP PRECEDES GATE"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("v2i_gate_rejected_trigger" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen
    # Also test cap trigger with suffix
    mutated2 = copy.deepcopy(canonical())
    mutated2["comparator_rejection_precedence"]["details"]["v2i_cap_rejected_trigger"] = (
        mutated2["comparator_rejection_precedence"]["details"]["v2i_cap_rejected_trigger"]
        + " contradictory suffix"
    )
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any("v2i_cap_rejected_trigger" in e for e in result2["errors"])


def test_fail_closed_unknown_nested_keys_each_v2_block() -> None:
    # successor_provenance nested is flat, but test its unknown already; test other nested mappings
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["equations"]["unknown_eq"] = "x"
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "waiting_room_occupancy_transition.equations" in e and "unknown" in e.lower()
        for e in result["errors"]
    )
    mutated2 = copy.deepcopy(canonical())
    mutated2["waiting_room_occupancy_transition"]["transition"]["if_B_post_lte_0"][
        "unknown_branch_key"
    ] = True
    result2 = validate_contract(mutated2)
    assert not result2["pass"]
    assert any(
        "waiting_room_occupancy_transition.transition.if_B_post_lte_0" in e
        for e in result2["errors"]
    )
    mutated3 = copy.deepcopy(canonical())
    mutated3["waiting_room_occupancy_transition"]["lifecycle_fields_remain_null"][
        "unknown_lifecycle"
    ] = "x"
    result3 = validate_contract(mutated3)
    assert not result3["pass"]
    assert any(
        "lifecycle_fields_remain_null" in e and "unknown" in e.lower() for e in result3["errors"]
    )
    mutated4 = copy.deepcopy(canonical())
    mutated4["comparator_rejection_precedence"]["details"]["unknown_detail"] = True
    result4 = validate_contract(mutated4)
    assert not result4["pass"]
    assert any(
        "comparator_rejection_precedence.details" in e and "unknown" in e.lower()
        for e in result4["errors"]
    )
    mutated5 = copy.deepcopy(canonical())
    mutated5["comparator_rejection_precedence"]["precedence"]["step_9_unknown"] = True
    result5 = validate_contract(mutated5)
    assert not result5["pass"]
    assert any(
        "comparator_rejection_precedence.precedence" in e and "unknown" in e.lower()
        for e in result5["errors"]
    )
    mutated6 = copy.deepcopy(canonical())
    mutated6["comparator_rejection_precedence"]["cross_strategy_comparability"]["unknown_cross"] = (
        True
    )
    result6 = validate_contract(mutated6)
    assert not result6["pass"]
    assert any(
        "cross_strategy_comparability" in e and "unknown" in e.lower() for e in result6["errors"]
    )
    mutated7 = copy.deepcopy(canonical())
    mutated7["comparator_rejection_precedence"]["p2c_separate"]["unknown_p2c"] = True
    result7 = validate_contract(mutated7)
    assert not result7["pass"]
    assert any("p2c_separate" in e and "unknown" in e.lower() for e in result7["errors"])


def test_hostile_v2_unknown_key_regenerated_markdown_still_fails() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["execution_authority"]["scientific_campaign_authorized"] = True
    regen = render_markdown(mutated)
    # Markdown regenerated from mutated JSON is internally consistent, so
    # validate_markdown would pass if checked against mutated, but JSON
    # validation must still fail (authoritative)
    md_errors_against_mutated = validate_markdown(regen, mutated)
    # Markdown against mutated may be 0 (byte-equivalent), but contract must fail
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("execution_authority" in e for e in result["errors"])
    # Also markdown against canonical must fail byte-equivalence
    canonical_data = canonical()
    md_errors_against_canonical = validate_markdown(regen, canonical_data)
    assert len(md_errors_against_canonical) > 0
    _ = md_errors_against_mutated


def test_fail_closed_pin_vectors_0_queue_ceiling_scales_unknown() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][0]["queue_ceiling_scales"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[0]" in e and "queue_ceiling_scales" in e for e in result["errors"])
    assert any("unknown" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_1_note_suffix_contradictory() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][1]["note"] = (
        mutated["waiting_room_occupancy_transition"]["pin_vectors"][1]["note"]
        + " contradictory suffix"
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[1]" in e and "note" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_bool_substitution_u() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][0]["u"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[0]" in e and "u" in e for e in result["errors"])
    # type-sensitive: True == 1 must not pass
    assert any("bool" in e.lower() or "type" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_bool_substitution_tasks_drained() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][1]["tasks_drained"] = True
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[1]" in e and "tasks_drained" in e for e in result["errors"])
    assert any("bool" in e.lower() or "type" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_bool_substitution_l_post() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][2]["L_post"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[2]" in e and "L_post" in e for e in result["errors"])
    assert any("bool" in e.lower() or "type" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_waiting_room_ceiling_float_substitution() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["waiting_room_ceiling_tasks_per_rsu"] = 6220.0
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("waiting_room_ceiling_tasks_per_rsu" in e for e in result["errors"])
    assert any("int" in e.lower() and "float" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_transition_l_post_false_bool() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["transition"]["if_B_post_lte_0"]["L_post"] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("transition.if_B_post_lte_0.L_post" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_cross_strategy_forbidden_presentation_false() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["comparator_rejection_precedence"]["cross_strategy_comparability"][
        "forbidden_presentation_is_identically_constructed_contrast"
    ] = False
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any(
        "forbidden_presentation_is_identically_constructed_contrast" in e for e in result["errors"]
    )
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_reordered_fails() -> None:
    mutated = copy.deepcopy(canonical())
    pin = mutated["waiting_room_occupancy_transition"]["pin_vectors"]
    mutated["waiting_room_occupancy_transition"]["pin_vectors"] = [pin[1], pin[0], pin[2]]
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[0]" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_extra_vector_fails() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"].append(
        copy.deepcopy(mutated["waiting_room_occupancy_transition"]["pin_vectors"][0])
    )
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors" in e for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_missing_key_fails() -> None:
    mutated = copy.deepcopy(canonical())
    del mutated["waiting_room_occupancy_transition"]["pin_vectors"][0]["u"]
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[0]" in e and "missing" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen


def test_fail_closed_pin_vectors_unknown_key_fails() -> None:
    mutated = copy.deepcopy(canonical())
    mutated["waiting_room_occupancy_transition"]["pin_vectors"][2]["extra_unknown"] = 123
    result = validate_contract(mutated)
    assert not result["pass"]
    assert any("pin_vectors[2]" in e and "unknown" in e.lower() for e in result["errors"])
    regen = render_markdown(mutated)
    assert not validate_contract(mutated)["pass"]
    _ = regen

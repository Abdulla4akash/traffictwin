"""Strong contract tests for E3 dynamic-resource v2 contract v1."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_e3_dynamic_resource_contract import (  # noqa: E402
    BASE_COMMIT,
    EXPECTED_ACTOR_SHA,
    EXPECTED_E2B,
    EXPECTED_E2C,
    EXPECTED_E2D,
    EXPECTED_E2D_MANIFEST,
    EXPECTED_TRACE_SHA,
    validate_contract,
    validate_markdown_contains,
)

CANONICAL_JSON = (
    Path(__file__).resolve().parents[1]
    / "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.json"
)
CANONICAL_MD = (
    Path(__file__).resolve().parents[1] / "docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.md"
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
    mutated2["research_question"] = (  # noqa: E501
        "Under the frozen Manchester incident trace and frozen MAPPO vehicle "
        "actor, do placement among ingress_dla, per_task_dla, and p2c_dla "
        "improve deadline?"
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

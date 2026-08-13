# E3 Dynamic Resource v2 — Scientific Contract v1

**Campaign:** `e3-dynamic-resource-v2`
**Contract version:** `e3_dynamic_resource_v2_contract_v1`
**Status:** `predeclared_before_any_e3_trace_execution`
**Created:** `2026-08-13`
**Base commit (exact):** `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`
**Lane:** `01` (`worker/e3-lane-01-contract`)

JSON is the single normative scientific contract (`e3_dynamic_resource_v2_contract_v1.json`). Markdown is a deterministic generated view via `render_markdown(data)` and must byte-equal its output; byte mismatch is authoritative.

Authority note: JSON is the single normative scientific contract; Markdown is a deterministic generated view via render_markdown and must byte-equal its output (byte mismatch is authoritative).

---

## 1. Research question

> Under the frozen Manchester incident trace and frozen MAPPO vehicle actor, do infrastructure-side placement among ingress_dla, per_task_dla, and p2c_dla and dynamic compute-resource scaling among fixed_1x, static_overprovisioned, reactive, and proactive improve offered-task deadline attainment and its trade-off with rejection and resource cost, when evaluated as paired fleet-draw differences over four matched draws within the bounded staged grid where E3a isolates placement at fixed_1x, E3b holds placement fixed at per_task_dla for scaling contrasts, and E3c tests selected stale-state contrasts (0/1000/3000 ms), without fully crossing every placement with every scaler?

Three orthogonal control dimensions — placement, admission, scaling — are isolated. E3a isolates placement at fixed_1x, E3b holds placement fixed at per_task_dla for scaling contrasts, E3c tests selected stale-state contrasts (0/1000/3000 ms), without fully crossing every placement with every scaler.

---

## 2. Frozen prerequisites and provenance

- E2b commit: `fe2ed4e9bd9043b19b96a5f179390db629b01ccb`
- E2c commit: `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`
- E2d commit: `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`
- E2d manifest SHA-256: `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`
- Actor path: `checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz`
- Actor SHA-256: `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`
- Trace path: `traces/trace_inc_fullrsu.npz`
- Trace SHA-256: `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`
- Evaluator seed: `0`
- Scenario: Manchester incident trace
- Steps: 3600; smoke steps: 10
- RSUs: 10; padded_fleet_width: 2488
- Outer tick: 1000 ms; task slots: 5
- Candidate stale levels: [0, 1000, 3000]

---

## 3. Replication — fleet_draw via fleet_seed

- Replication unit: `fleet_draw`
- Replication key: `fleet_seed` (integer 1..4)
- N: `4` fleet draws (tasks are not replicates)
- Fleet seeds: `[1, 2, 3, 4]`
- Note: One fleet_draw is one fixed padded-slot assignment for the trace, not a new draw per unique SUMO vehicle.

---

## 4. Hypotheses H1–H5 (hypothesis_not_expected_truth)

All hypotheses have status `hypothesis_not_expected_truth` and kind `hypothesis`;
negative, null, or opposite results are acceptable and remain valid.

- **H1** `hypothesis_not_expected_truth` — P2C (p2c_dla) may approach per_task_dla offered deadline attainment with less global inspection, but may not exceed it.
- **H2** `hypothesis_not_expected_truth` — Reactive scaling may improve deadline attainment or reduce rejection relative to fixed_1x, but may increase resource_unit_seconds and churn (scale actions).
- **H3** `hypothesis_not_expected_truth` — Proactive scaling may help relative to reactive when load change outruns the 2s actuation delay, but may not otherwise.
- **H4** `hypothesis_not_expected_truth` — Global least-busy placement (per_task_dla) may degrade faster than P2C (p2c_dla) under stale state (1000/3000 ms).
- **H5** `hypothesis_not_expected_truth` — Additional compute (static_overprovisioned or scaling-up policies) may not win once resource_unit_seconds is considered in the deadline–cost trade-off.

H1: P2C may approach per_task_dla with less global inspection; H2: reactive may improve with churn;
H3: proactive may help when load change outruns actuation; H4: per_task_dla may degrade faster than P2C under stale state;
H5: additional compute (static_overprovisioned) may not win once resource_unit_seconds is considered.
Hypotheses are not expected truths; negative results acceptable.

---

## 5. Mechanism separation

| Mechanism | Controls | Does not control |
|---|---|---|
| Placement | Which RSU executes an admitted V2I task | admission; compute capacity |
| Admission | Whether an offered V2I task is admitted (deadline feasibility gate) | where it executes; compute capacity |
| Scaling | How many compute units (1-3) are active per RSU over time | which RSU chosen; admission decision |

- Queue ceiling is not compute capacity: queue_ceiling_is_not_compute_capacity must be true.
- Actor never observes RSU load and never selects execution RSU.
- Rejected work never executes.

---

## 6. Placement — p2c_dla, ingress_dla, per_task_dla

- Feasibility first; two distinct feasible candidates.
- Counter key fields: ['evaluator_seed', 'fleet_seed', 'outer_tick', 'task_slot', 'sequential_task_ordinal'] (stable counter-based key; no global RNG).
- Field declaration ordered: ['evaluator_seed', 'fleet_seed', 'outer_tick', 'task_slot', 'sequential_task_ordinal']
- Fold field_order: ['evaluator_seed', 'fleet_seed', 'outer_tick', 'task_slot', 'sequential_task_ordinal']
- Inspect only pair; lower effective_busy_ms wins; tie by lowest RSU id; immediate reservation; one candidate per task; common target forbidden.
- Stale: immutable delayed view; same_tick_reservation_overlay; no future leakage; exposes state_age_ms.
- Pair mapper: sorted ascending unique feasible RSU IDs; SplitMix64 over ordered fields; final pair sorted.
- Modulo bias note: modulo reduction has negligible bias not mathematically exact-uniform; H1 is pair-only ranking vs global least-busy dependence not statistical uniformity proof.

---

## 7. Compute scaling

- fixed_1x: active_units_per_rsu=1 multiplier=1 rsu_service_mult=1.0
- static_overprovisioned: active_units_per_rsu=3 multiplier=3 rsu_service_mult=3.0 (fixed 3x compute, never queue capacity)
- Dynamic bounds: 1--3 units; actuation_delay 2000 ms / 2 ticks; one level per action; one pending; apply due before tick; free_scaling_forbidden and unbounded_scaling_forbidden.
- Reactive: signal service_workload_ms (work_ms_independent_of_capacity) per RSU; thresholds up >= 800 inclusive, down <= 200 inclusive; gap 600 is hysteresis; cooldown 5000 ms; actuation 2000 ms; bounds 1..3; one level; one pending; stable inclusive edges; prediction false; state_age 0/1000/3000.
- Reactive signal units: work-ms, independent of capacity
- Proactive: transparent baseline, not optimal predictor; signal arrival_work_ms per-RSU at 1000 ms ticks; window 4 observations oldest_to_newest at 1000 ms; warm_up 4 valid; formulas older_mean=mean(W[0:2]), recent_mean=mean(W[2:4]), trend=recent_mean - older_mean, forecast=max(0, mean(W) + 2*trend); horizon 2000 ms (2 ticks); same 800/200 thresholds gap 600 hysteresis inclusive; cooldown 5000; delay 2000; bounds 1..3; one level/pending; no future leakage.
- Hysteresis is gap (600) — no extra hysteresis_ms excursion beyond thresholds.

---

## 8. Time model

- outer_tick_ms: 1000 (1000 ms = 1 second, advances physical time)
- within_tick_task_slots: 5 (do NOT advance physical time)
- state_age_unit: integer_simulator_ms (signal snapshot age)
- candidate_stale_levels_ms: [0, 1000, 3000]
- control_clock_offset_ms: 3000; prepopulate [0, 1000, 2000] with empty_initial_infrastructure_state; trace tick 0 maps to control 3000.
- Stale 200ms is forbidden; stale levels are candidate values; permits exact 0/1000/3000 without clamping.

---

## 9. Cost — resource_unit_seconds

- Metric: `resource_unit_seconds`
- Formula: `sum_over_RSU sum_over_interval (active_compute_units * interval_seconds)`
- Monetary is false (never monetary): no currency, price, billing, USD, dollar claims.
- Cost per RSU per tick: active_compute_units * 1 second; charged even when idle; at most one interval per RSU per tick.

---

## 10. Task accounting

- Required: ['offered', 'admitted', 'rejected', 'genuine_classes', 'forwarded', 'deadline_success']
- Unavailable lifecycle must remain null: started=None, compute_completed=None, returned=None, dropped=None (null means unmodelled not zero).
- Forbidden to fabricate physical started/completed/returned lifecycle.

---

## 11. Compute-service semantics

- Enqueue: enqueued_work_ms = raw_1x_service_work_ms (must not divide by capacity)
- Drain: drain_work_ms = min(backlog_work_ms, active_capacity_units * 1000) per 1000 ms tick for all queued work
- Backlog: backlog_work_ms[t+1] = backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms (invariant baseline, work_ms storage)
- Resource time: resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1 even when idle; at_most_one_interval
- Latency: (raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units admission-time estimate not physical lifecycle; physical lifecycle fields remain null; not repriced.
- Placement/admission/stale/reactive use raw_backlog_work_ms; proactive uses raw_admitted_arrival_work_ms; queue safety uses current occupancy plus same-tick reservations.
- Scaling applied at tick start before placement/admission and before latency estimate/drain; active capacity for entire tick; reduces to E2d at fixed_1x.

---

## 12. Stale decision vs true execution

- observed_decision_backlog_work_ms: fresh_or_delayed_immutable_backlog_work_ms_plus_decision_overlay_plus_same_tick_reservation_overlay
- true_execution_backlog_work_ms: current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU
- optimistic stale admitted executes and may miss per true latency; pessimistic stale rejected never executes.
- deadline_success is based on true simulated latency, never the controller's stale estimate.
- not evidence of physical started/completed/returned lifecycle; do not retroactively reprice.
- deadline_success_comparator: "<=" (typed string, not bool; exactly "<="; equality is success)
- deadline_success_rule: "simulated_latency_ms <= task_deadline_ms" (exactly "simulated_latency_ms <= task_deadline_ms"; inherited E2d outcome compatibility)
- equality is success for deadline_success (simulated_latency_ms == task_deadline_ms is success)
- inherited E2d outcome compatibility: vec_env 2f63706f46319433a2ba3af1df97afd0e56a95d1 jaxmarl/env/vec_jax.py:736 deadline_met = latency <= deadline
- admission feasibility predicate (strict): "observed_decision_backlog_work_ms[rsu] < task_deadline_ms" (strict "<"; equality at the backlog gate remains infeasible)
- outcome and feasibility comparators are distinct and not interchangeable; comparator conflation is forbidden
- cross-reference: strict feasibility lives in p2c_candidate_predicate.feasible_RSU_predicate.conditions_both, stale_state_semantics.deadline_formula_unchanged, and admission_gate.formula; outcome uses "<=" at admission while feasibility uses "<"

---

## 13. Dense position and diagnostics

- Sequential task ordinal: task_slot * padded_fleet_width + vehicle_slot (dense position identity, independent of active mask; range [0,12439]).
- Outer tick, task_slot, vehicle_slot, sequential_task_ordinal are all required counter key fields.
- P2C mixer: field_declaration fields_ordered must equal fold field_order and equal expected counter fields; splitmix64 definition with wrap 2^64; fold h_init 0x6A09E667F3BCC909 for_each_ordered_field h=splitmix64(h xor uint64(field)).
- Diagnostic coverage: feasibility_workload_checks, ranking_workload_inspections, unique_workload_values_observed; MUST NOT claim only two total global state reads or proven lower total state acquisition.
- Resource diagnostics: drained_work_ms / (active_capacity_units * 1000 work_ms) bounded [0,1]; waiting-room occupancy is a separate task count; execution share is actual admitted V2I execution count / total admitted V2I execution count; when denominator is zero it is null with reason.
- Target switching is counted over consecutive admitted V2I tasks in exact deterministic (outer_tick, task_slot, vehicle_slot) order; first admitted task is not a switch; resource_unit_seconds denominator stays required for diagnostic deadline per resource cost.
- Pair-only ranking; H1 concern is pair-only inspection/global-state dependence not statistical uniformity proof.

---

## 14. Staged design — candidate grid

- stage_listed_cells: 60; maximum_candidate_unique_cells: 56
- Equations: stage_listed 12 + 16 + 32 = 60; unique 12 + 12 + 32 = 56
- E3a (isolates placement): ['ingress_dla', 'per_task_dla', 'p2c_dla'] x ['fixed_1x'] x staleness [0] x 4 draws = 12 cells
- E3b (holds per_task_dla, scaling contrasts): ['per_task_dla'] x ['fixed_1x', 'static_overprovisioned', 'reactive', 'proactive'] x staleness [0] x 4 draws = 16 stage-listed; overlap_with_e3a 4 reused not rerun; unique_additional 12
- E3c (stale-state contrasts): 48 total contrast observations; 16 fresh reused; equation 2 contrasts * 2 arms * 3 staleness * 4 draws = 48 observations; 48 - 16 = 32 stale variants ; stale_variant 48 - 16 = 32 ; additional stale variant cells max 32
- Note: Candidate grid before benchmark reduction; final machine plan must be reduced if representative benchmark projects unreasonable bounded local budget. Identical fresh cells are reused across stage summaries rather than rerun and counted twice. Stage-listed base/additional entries = 60 (12 E3a + 16 E3b stage-listed + 32 E3c stale variants); unique planned executions = 56 (12 + 12 + 32) after reusing 4 E3a/E3b overlaps and 16 E3c fresh observations. Equations: 12+16+32=60 stage-listed; 12+12+32=56 unique; 48 total E3c contrast observations -16 fresh reused =32 stale variants. Equations with spaces: 12 + 16 + 32 = 60 stage-listed; 12 + 12 + 32 = 56 unique.
- E3c reuses identical fresh cells; not double-counted;
  depends_on fresh construct gates.
- Maximum candidate is 56 unique cells (60 stage-listed): 12 + 12 + 32 unique; 12 + 16 + 32 stage-listed.

---

## 15. Inference

- Unit: fleet_draw keyed by fleet_seed N=4 seeds [1, 2, 3, 4]
- Interval: two-sided 95% Student-t, df=3, t_0.975,3 = 3.182
- Sample SD: Bessel n-1; SE: s / sqrt(n)
- Paired differences per fleet_seed; reportable contrast requires all four paired seeds 1..4.
- Forbidden: task_as_n, p_value_as_primary, citywide_generalisation, population_claim, equivalence_without_margin, seed_0_in_primary.

---

## 16. Claim boundaries and limitations

- Any post-observation source change requires successor: True
- Monetary cost tested: False (false — resource_unit_seconds only; not monetary)
- Kubernetes orchestration tested: False; learned controller: False; Manchester-wide: False; physical return: False
- Proactive is transparent baseline, not an optimal predictor; transparent baseline not optimal.
- Work-ms, independent of capacity; optimistic stale admitted executes and may miss per true latency; pessimistic stale rejected never executes; deadline_success based on true simulated latency never stale estimate; not evidence of physical started/completed/returned; do not retroactively reprice.

---

## 17. Validation and byte-equivalence

The entire Markdown bytes must equal `render_markdown(canonical_json)`. Any addition, deletion, or reordering outside the canonical block fails byte-equivalence. Validator compares supplied Markdown bytes with pure render; byte mismatch is authoritative.

---

<!-- BEGIN_E3_CANONICAL_JSON -->
```json
{
  "accounting_and_contrast_completion": {
    "draw_is_N_4_tasks_never_become_replicates": true,
    "lossless_accounting": {
      "deadline_success_between_0_and_admitted": true,
      "forwarded_between_0_and_admitted_v2i_between_0_and_admitted": true,
      "offered_equals_admitted_plus_rejected": true,
      "rejected_equals_sum": [
        "v2i_gate_rejected",
        "v2i_cap_rejected",
        "local_mqd_rejected",
        "v2v_mqd_rejected",
        "v2i_unavailable",
        "v2v_unavailable"
      ]
    },
    "missing_incomplete_cells_make_matched_contrast_status_incomplete_null_never_reduce_n": true,
    "predeclared_contrasts": {
      "E3a_primary": {
        "for": "offered deadline attainment at fixed_1x/state_age=0",
        "id": "p2c_dla-minus-per_task_dla",
        "secondary": "p2c_dla-minus-ingress_dla"
      },
      "E3b_per_task_dla_state_age_0": {
        "each_of": [
          "static_overprovisioned",
          "reactive",
          "proactive"
        ],
        "for_co_primary_family": [
          "offered deadline attainment",
          "rejection_share",
          "resource_unit_seconds"
        ],
        "minus": "fixed_1x",
        "no_scalar_best_objective": true,
        "plus_proactive_minus_reactive_as_declared_diagnostic": true
      },
      "E3c_at_each_state_age": {
        "contrasts": [
          "p2c_dla-minus-per_task_dla under fixed_1x",
          "proactive-minus-reactive under per_task_dla"
        ],
        "for": [
          "offered deadline attainment",
          "rejection_share",
          "resource_unit_seconds"
        ],
        "plus_declared_imbalance_action_diagnostics": true
      }
    },
    "reportable_contrast_requires_all_four_paired_seeds_1_to_4_and_uses_exact_treatment_minus_control_sign": true,
    "shares": {
      "deadline_per_normalized_cost_is_offered_deadline_attainment_div_resource_unit_seconds_and_null_reason_if_cost_zero": true,
      "forwarding_share_is_forwarded_div_admitted_v2i_and_null_reason_if_denominator_zero": true,
      "rejection_share_is_rejected_div_offered": true
    },
    "unavailable_V2V_work_has_no_destination_service_work_and_remains_explicit_count_rather_than_fabricated_zero_work": true,
    "work_ms_conservation_where_instrumented_separately_for_V2I_and_vehicle_queues": true
  },
  "admission_gate": {
    "excludes": [
      "own_compute",
      "radio_transfer",
      "return_transfer",
      "forwarding_latency"
    ],
    "formula": "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]",
    "never_selects_target": true,
    "queue_safety_uses_current_not_stale": true,
    "radio_viability_is_current": true,
    "stale_view_applies_to_deadline_workload": true,
    "state_units": "milliseconds_of_remaining_service_workload"
  },
  "authority_note": "JSON is the single normative scientific contract; Markdown is a deterministic generated view via render_markdown and must byte-equal its output (byte mismatch is authoritative).",
  "base_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
  "branch": "worker/e3-lane-01-contract",
  "campaign": "e3-dynamic-resource-v2",
  "claim_boundaries": {
    "any_post_observation_source_change_requires_successor": true,
    "kubernetes_orchestration_tested": false,
    "learned_controller_tested": false,
    "manchester_wide_deployment_tested": false,
    "monetary_cost_tested": false,
    "physical_result_return_tested": false,
    "proactive_is_transparent_baseline_not_optimal": true
  },
  "compute_scaling": {
    "dynamic_bounds": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "apply_due_before_tick_decision": true,
      "free_scaling_forbidden": true,
      "hysteresis_is_gap": true,
      "hysteresis_ms_extra_forbidden": true,
      "max_pending_actions": 1,
      "max_units": 3,
      "min_units": 1,
      "one_level_per_action": true,
      "threshold_gap_ms": 600,
      "unbounded_scaling_forbidden": true
    },
    "fixed_1x": {
      "active_units_per_rsu": 1,
      "multiplier": 1,
      "rsu_service_mult": 1.0,
      "scaling": "off"
    },
    "proactive": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "alternative_formula_forbidden": true,
      "apply_due_before_tick_decision": true,
      "bounds_max": 3,
      "bounds_min": 1,
      "cooldown_ms": 5000,
      "formula_declared": true,
      "formulas": {
        "forecast": "max(0, mean(W) + 2*trend)",
        "older_mean": "mean(W[0:2])",
        "recent_mean": "mean(W[2:4])",
        "trend": "recent_mean - older_mean"
      },
      "horizon_ms": 2000,
      "horizon_ticks": 2,
      "hysteresis_is_gap": true,
      "max_pending_actions": 1,
      "ml": false,
      "no_decisions_during_warm_up": true,
      "no_future_leakage": true,
      "observation_interval_ms": 1000,
      "per_rsu": true,
      "prediction_uses_future": false,
      "scale_down_inclusive": true,
      "scale_down_threshold_ms": 200,
      "scale_up_inclusive": true,
      "scale_up_threshold_ms": 800,
      "signal": "arrival_work_ms",
      "stable_inclusive_edges": true,
      "threshold_gap_ms": 600,
      "transparent": true,
      "transparent_baseline_not_optimal": true,
      "uses_only_samples_at_or_before_observation_time": true,
      "warm_up_ticks_declared": true,
      "warm_up_valid_observations": 4,
      "window_interval_ms": 1000,
      "window_order": "oldest_to_newest",
      "window_size": 4
    },
    "reactive": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "apply_due_before_tick_decision": true,
      "cooldown_ms": 5000,
      "hysteresis_is_gap": true,
      "hysteresis_ms_extra": false,
      "max_pending_actions": 1,
      "max_units": 3,
      "min_units": 1,
      "per_rsu": true,
      "prediction": false,
      "scale_down_inclusive": true,
      "scale_down_threshold_ms": 200,
      "scale_up_inclusive": true,
      "scale_up_threshold_ms": 800,
      "signal": "service_workload_ms",
      "signal_units": "work_ms_independent_of_capacity",
      "stable_inclusive_edges": true,
      "state_age_ms_values": [
        0,
        1000,
        3000
      ],
      "threshold_gap_ms": 600
    },
    "static_overprovisioned": {
      "active_units_per_rsu": 3,
      "forbidden_synonyms_rejected": [
        "static3x",
        "static_3x"
      ],
      "is_compute_not_queue": true,
      "multiplier": 3,
      "rsu_service_mult": 3.0,
      "scaling": "off"
    },
    "unit": "compute_unit (service capacity, not queue slots)"
  },
  "compute_service_semantics": {
    "active_capacity_for_entire_tick": true,
    "admission_gate_unit": "raw_backlog_work_ms",
    "at_most_one_interval_per_RSU_per_tick": true,
    "backlog_equation": "backlog_work_ms[t+1] = backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms",
    "backlog_is_invariant_baseline": true,
    "backlog_storage_unit": "work_ms",
    "drain_applies_to_all_queued_work_including_pre_scale": true,
    "drain_capacity_is_not_queue_slots": true,
    "drain_equation": "drain_work_ms = min(backlog_work_ms, active_capacity_units * 1000)",
    "drain_tick_ms": 1000,
    "enqueue_adds_raw_1x_work_ms": true,
    "enqueue_equation": "enqueued_work_ms = raw_1x_service_work_ms",
    "enqueue_forbidden_division": "enqueued_work_ms != raw_1x_service_work_ms / active_capacity_units",
    "enqueue_must_not_divide_by_capacity": true,
    "initial_capacities": {
      "dynamic_max_units": 3,
      "dynamic_min_units": 1,
      "dynamic_start_units": 1,
      "fixed_1x_units": 1,
      "static_overprovisioned_from_tick": 0,
      "static_overprovisioned_units": 3
    },
    "latency_equation": "(raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units",
    "latency_not_retroactively_repriced": true,
    "latency_physical_lifecycle_fields_remain_null": true,
    "latency_radio_forwarding_unchanged": true,
    "latency_semantics": "admission_time_estimate_not_physical_lifecycle",
    "placement_workloads_unit": "raw_backlog_work_ms",
    "proactive_observation_unit": "raw_admitted_arrival_work_ms",
    "queue_ceiling_uses_current_occupancy_plus_same_tick_reservations": true,
    "queue_safety_is_current_not_stale": true,
    "reactive_signal_unit": "raw_backlog_work_ms",
    "reduces_to_E2d_at_fixed_1x": true,
    "reduction_equation": "at fixed_1x (u=1): drain = min(backlog_work_ms, 1000) and latency = raw_work_ahead_ms + raw_own_service_work_ms",
    "resource_time_charged_even_when_idle": true,
    "resource_time_equation": "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1",
    "same_tick_reservation_overlay_unit": "raw_task_work_ms",
    "scaling_applied_at_tick_start_before_placement_admission": true,
    "scaling_applied_before_latency_estimate_and_drain": true,
    "scaling_forbidden_units": [
      "queue_slots",
      "capacity_normalized_work_ms"
    ],
    "scaling_must_not_change_placement_or_admission_unit": true,
    "stale_does_not_mutate_true_state": true,
    "stale_snapshot_unit": "raw_backlog_work_ms"
  },
  "contract_authority": "json_is_normative_markdown_is_generated_view",
  "cost": {
    "forbidden_fields": [
      "cost_currency",
      "cost_dollars",
      "cost_price",
      "cost_billing"
    ],
    "formula": "sum_over_RSU sum_over_interval (active_compute_units * interval_seconds)",
    "interval_seconds": 1,
    "metric": "resource_unit_seconds",
    "monetary": false
  },
  "created": "2026-08-13",
  "execution_preconditions": {
    "before_any_full_cell": [
      "unit_tests_pass",
      "construct_tests_pass",
      "tiny_smoke_10step_per_new_arm",
      "representative_benchmark_3600_per_arm_type",
      "runtime_storage_projection",
      "machine_plan_with_exact_cells_and_order",
      "independent_review_APPROVE_exact_HEAD_and_manifest_SHA",
      "immutable_manifest_before_first_replay"
    ],
    "stop_rules": [
      "identity_mismatch",
      "offered_or_fleet_mismatch_across_matched_draws",
      "task_accounting_or_conservation_failure",
      "rejected_work_executes_or_forwards",
      "non_finite_or_negative_or_monetary_cost",
      "future_leakage",
      "common_target_p2c",
      "budget_or_storage_gate_violation",
      "unpredeclared_arm_or_code_change"
    ]
  },
  "frozen_prerequisites": {
    "actor": {
      "frozen": true,
      "observes_current_rsu_load": false,
      "path": "checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz",
      "selects_execution_rsu": false,
      "sha256": "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    },
    "e2b": {
      "commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
      "status": "closed"
    },
    "e2c": {
      "commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
      "status": "closed"
    },
    "e2d": {
      "commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
      "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
      "status": "closed"
    },
    "evaluator_seed": 0,
    "trace": {
      "path": "traces/trace_inc_fullrsu.npz",
      "sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
    }
  },
  "h1_state_inspection": {
    "any_duplicated_reads_remain_visible": true,
    "common_feasibility_decision_observation_cost_remains_visible": true,
    "feasibility_first_must_enumerate_all_RSU_deadline_feasibility": true,
    "forbidden_claims": [
      "two_total_reads",
      "hidden_feasibility_scan",
      "communication_savings_proven"
    ],
    "h1_is_hypothesis_about_pair_only_ranking_vs_global_least_busy_dependence_not_proved_networking_cost": true,
    "h1_remains_hypothesis_allowed_to_fail": true,
    "must_not_claim_distributed_communication_savings": true,
    "must_not_claim_only_two_total_global_reads": true,
    "must_not_claim_proven_lower_total_state_acquisition": true,
    "p2c_ranking_inspection_is_0_1_2_according_to_feasible_count": true,
    "per_task_dla_global_argmin_ranks_all_R": true,
    "separately_record": [
      "feasibility_workload_checks",
      "ranking_workload_inspections",
      "unique_workload_values_observed"
    ]
  },
  "hypotheses": {
    "boundary": "negative, null, or opposite results acceptable; hypotheses are not expected truths",
    "hypotheses_are_not_expected_truths": true,
    "items": [
      {
        "compares": [
          "p2c_dla",
          "per_task_dla"
        ],
        "id": "H1",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "offered_deadline_attainment",
        "statement": "P2C (p2c_dla) may approach per_task_dla offered deadline attainment with less global inspection, but may not exceed it.",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "reactive",
          "fixed_1x"
        ],
        "id": "H2",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "deadline_attainment_rejection_resource_tradeoff",
        "statement": "Reactive scaling may improve deadline attainment or reduce rejection relative to fixed_1x, but may increase resource_unit_seconds and churn (scale actions).",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "proactive",
          "reactive"
        ],
        "id": "H3",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "deadline_attainment",
        "statement": "Proactive scaling may help relative to reactive when load change outruns the 2s actuation delay, but may not otherwise.",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "per_task_dla",
          "p2c_dla"
        ],
        "id": "H4",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "offered_deadline_attainment_under_staleness",
        "statement": "Global least-busy placement (per_task_dla) may degrade faster than P2C (p2c_dla) under stale state (1000/3000 ms).",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "static_overprovisioned",
          "fixed_1x"
        ],
        "id": "H5",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "resource_unit_seconds_tradeoff",
        "statement": "Additional compute (static_overprovisioned or scaling-up policies) may not win once resource_unit_seconds is considered in the deadline–cost trade-off.",
        "status": "hypothesis_not_expected_truth"
      }
    ],
    "negative_results_acceptable": true,
    "note": "All hypotheses are predeclared as hypotheses_not_expected_truths; negative, null, or opposite results are acceptable and remain valid. No hypothesis is an expected truth or guaranteed result."
  },
  "inference": {
    "compatible_with_e2_unless_predeclared": true,
    "decisions": {
      "interval_above_zero": "directional_advantage_for_treatment_within_bounded_draws",
      "interval_below_zero": "directional_deficit_for_treatment_within_bounded_draws",
      "interval_includes_zero": "inconclusive_at_this_replication_size"
    },
    "fleet_seeds": [
      1,
      2,
      3,
      4
    ],
    "forbidden": [
      "task_as_n",
      "p_value_as_primary",
      "citywide_generalisation",
      "population_claim",
      "equivalence_without_margin",
      "seed_0_in_primary"
    ],
    "includes_zero_flag": true,
    "interval": "two-sided 95% Student-t, df=3, t_0.975,3 = 3.182",
    "key": "fleet_seed",
    "mean_difference": "d_bar = mean(d_i)",
    "n": 4,
    "paired_differences": "d_i = metric(treatment, draw_i) - metric(control, draw_i) matched on fleet_seed",
    "per_draw_values_required": true,
    "sample_sd": "Bessel n-1",
    "se": "s / sqrt(n)",
    "unit": "fleet_draw"
  },
  "lane": "01",
  "markdown_is_generated_view": true,
  "mechanism_separation": {
    "actor_never_observes_rsu_load": true,
    "actor_never_selects_execution_rsu": true,
    "admission": "Whether an offered V2I task is admitted (deadline feasibility gate)",
    "placement": "Which RSU executes an admitted V2I task",
    "queue_ceiling_is_not_compute_capacity": true,
    "rejected_work_never_executes": true,
    "scaling": "How many compute units (1-3) are active per RSU over time"
  },
  "p2c_candidate_predicate": {
    "admission_requires": "active frozen-actor V2I attempt and ingress radio currently viable",
    "feasible_RSU_predicate": {
      "candidate_order": "sorted ascending unique feasible RSU IDs",
      "conditions_both": [
        "observed_decision_backlog_work_ms[rsu] < task_deadline_ms",
        "true_current_waiting_room_occupancy[rsu] + prior same-tick admitted reservations < queue_ceiling"
      ],
      "only_backlog_deadline_belief_is_aged": true,
      "queue_safety_is_current_not_stale": true,
      "radio_is_current": true
    },
    "forbidden_behaviors": [
      "sample-before-filter",
      "stale queue-cap",
      "undefined n=0/1",
      "rejection ambiguity",
      "rejected-work reservation"
    ],
    "n_equals_0": {
      "classification": {
        "elif_no_RSU_observed_deadline_feasible": "v2i_gate_rejected",
        "else_deadline_feasible_exist_but_all_full": "v2i_cap_rejected",
        "if_ingress_radio_not_viable": "v2i_unavailable"
      },
      "reject_without_execution": true,
      "select_no_target": true
    },
    "n_equals_1": {
      "hashing_skipped": true,
      "no_second_hash_modulo": true,
      "ranking_inspections": 1,
      "select_sole_feasible_RSU": true
    },
    "n_gte_2": {
      "deterministic_distinct_pair": true,
      "selection": "lower observed backlog",
      "tie_break": "stable lowest-ID",
      "without_replacement": true
    },
    "reservation": {
      "rejected_work_never_reserved": true,
      "reserve_true_load_raw_work_and_decision_overlay_immediately_only_on_admission": true
    }
  },
  "p2c_dense_counter_key_mapping": {
    "declared_mixer_fields_remain_exactly_five": [
      "evaluator_seed",
      "fleet_seed",
      "outer_tick",
      "task_slot",
      "sequential_task_ordinal"
    ],
    "forbidden_behaviors": [
      "active_only_ordinal",
      "ordinal_reset_or_collision",
      "200ms_time_interpretation",
      "outcome_dependent_key_shifts"
    ],
    "outer_tick": {
      "advances_physical_time": "per_outer_tick_1000ms",
      "definition": "zero_based_trace_tick",
      "range": "[0,3599]"
    },
    "outer_tick_is_zero_based": true,
    "padded_fleet_width": 2488,
    "per_outer_tick_range": "[0,12439]",
    "sequential_task_ordinal": {
      "dense_position_identity": true,
      "earlier_outcomes_never_shift_later_pairs": true,
      "formula": "task_slot * padded_fleet_width + vehicle_slot",
      "independent_of_active_mask": true,
      "independent_of_actor_choice": true,
      "independent_of_admission_or_rejection": true,
      "independent_of_feasibility": true,
      "per_outer_tick": true,
      "range": "[0,12439]"
    },
    "task_slot": {
      "advances_physical_time": false,
      "definition": "zero_based_within_tick_substep",
      "note": "does not advance physical time",
      "range": "[0,4]"
    },
    "task_slot_is_zero_based": true,
    "vehicle_slot": {
      "definition": "zero_based_padded_fleet_slot",
      "padded_fleet_width": 2488,
      "range": "[0,2487]"
    },
    "vehicle_slot_is_provenance_but_not_mixer_field": true,
    "vehicle_slot_is_zero_based": true
  },
  "p2c_mixer": {
    "field_declaration": {
      "bounds": {
        "evaluator_seed": "[0, 2^64-1] actual 0",
        "fleet_seed": "[0, 2^64-1] actual [1,4] for primary draws",
        "outer_tick": "[0, 3599]",
        "sequential_task_ordinal": "[0, 12439]",
        "task_slot": "[0, 4]"
      },
      "field_type": "non-negative unsigned 64-bit (uint64)",
      "fields_ordered": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "wrap_modulo": "2^64 after every operation"
    },
    "fold": {
      "field_order": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "for_each_ordered_field": "h=splitmix64(h xor uint64(field))",
      "h_init": "0x6A09E667F3BCC909"
    },
    "forbidden_behaviors": [
      "alternate SplitMix variants",
      "string/byte serialization",
      "signed overflow",
      "field reordering",
      "missing vectors",
      "claim modulo exact uniformity"
    ],
    "modulo_bias_note": "modulo reduction has negligible bias not mathematically exact-uniform",
    "pair_indices": {
      "for_n_equals_0_no_indices": true,
      "for_n_equals_1_hashing_skipped": true,
      "for_n_gte_2": {
        "candidate_order_is_ascending_unique_RSU_ID": true,
        "first_index": "h % n",
        "j": "splitmix64(h) % (n-1)",
        "second_index": "j if j<first_index else j+1",
        "sort_resulting_pair_only_for_telemetry_not_before_indexing": true
      }
    },
    "splitmix64_definition": {
      "constants_hex": [
        "0x9E3779B97F4A7C15",
        "0xBF58476D1CE4E5B9",
        "0x94D049BB133111EB"
      ],
      "steps": [
        "z=(x+0x9E3779B97F4A7C15) mod 2^64",
        "z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64",
        "z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64",
        "return z xor (z>>31)"
      ],
      "wrap_modulo_2_64_after_every_operation": true
    },
    "test_vectors": [
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 0,
          "outer_tick": 0,
          "sequential_task_ordinal": 0,
          "task_slot": 0
        },
        "first_index": 9,
        "h_dec": 9014450953278226949,
        "h_hex": "0x7d19c361a3548205",
        "n": 10,
        "note": "all-zero fields",
        "second_index": 1,
        "sorted_pair": [
          1,
          9
        ]
      },
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 1,
          "outer_tick": 3599,
          "sequential_task_ordinal": 12439,
          "task_slot": 4
        },
        "first_index": 2,
        "h_dec": 2980351793025054512,
        "h_hex": "0x295c562a48f4f730",
        "n": 10,
        "note": "boundary outer_tick=3599/task_slot=4/ordinal=12439",
        "second_index": 7,
        "sorted_pair": [
          2,
          7
        ]
      },
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 2,
          "outer_tick": 1234,
          "sequential_task_ordinal": 5678,
          "task_slot": 2
        },
        "first_index": 2,
        "h_dec": 3823313609874163032,
        "h_hex": "0x350f2378ad774558",
        "n": 10,
        "note": "mid vector",
        "second_index": 8,
        "sorted_pair": [
          2,
          8
        ]
      }
    ],
    "uniformity_claim_forbidden": true
  },
  "permission_boundaries": {
    "authorised_after_exact_approval": "bounded fresh E3a/E3b/E3c cells as reduced machine plan, matched analysis, private branches",
    "forbidden": [
      "trace_run_before_exact_approval",
      "seed_0_in_primary",
      "new_ingress_dla_dla_without_fresh",
      "nonzero_backhaul",
      "scaling_outside_1_3",
      "learning_retraining",
      "actor_observes_rsu_load"
    ]
  },
  "placement": {
    "ingress_dla": {
      "admission": "inherited_deadline_aware_gate",
      "mechanism": "strongest-link ingress execution"
    },
    "p2c_dla": {
      "candidates": 2,
      "common_target_forbidden": true,
      "counter_key_fields": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "counter_key_stable": true,
      "distinct_feasible_only": true,
      "feasibility_first": true,
      "h1_concern": "pair_only_inspection_global_state_dependence_not_statistical_uniformity_proof",
      "immediate_reservation": true,
      "inspect_only_pair": true,
      "mechanism": "power-of-two-choices with feasibility-first",
      "modulo_bias_note": "modulo reduction has negligible bias not mathematically exact-uniform",
      "no_global_rng_stream": true,
      "one_candidate_per_task": true,
      "pair_mapper": {
        "candidate_order": "sorted_ascending_unique_feasible_RSU_IDs",
        "distinct_without_replacement": true,
        "final_pair_sorted": true,
        "first_index_formula": "h % n",
        "hash": "SplitMix64",
        "hash_input_fields_exact": [
          "evaluator_seed",
          "fleet_seed",
          "outer_tick",
          "task_slot",
          "sequential_task_ordinal"
        ],
        "mapper_type": "deterministic_pseudo_random_modulo_mapper",
        "no_hidden_global_RNG": true,
        "second_index_formula": "splitmix64(h) % (n-1) adjusted around first",
        "uniformity_not_claimed": true
      },
      "selection": "lower effective_busy_ms",
      "stale_snapshot": {
        "delay_ms_field": "state_age_ms",
        "exposes_state_age_ms": true,
        "immutable_delayed_view": true,
        "no_future_leakage": true,
        "same_tick_reservation_overlay": true
      },
      "tie_break": "lowest RSU id (stable)",
      "uniformity_claim_forbidden": [
        "uniform",
        "unbiased",
        "exact-uniform",
        "exact_uniform"
      ],
      "without_replacement": true
    },
    "per_task_dla": {
      "gate": "same inherited deadline gate applied causally per candidate",
      "mechanism": "per-task sequential least-busy placement",
      "order": "ascending task-substep then padded-slot index",
      "reservation": "add service work to effective vectors only on admission",
      "rng": "none",
      "state": "effective_busy_ms (remaining service workload)",
      "tie_break": "lowest RSU index (jnp.argmin)"
    }
  },
  "replication": {
    "fleet_draw_note": "One fleet_draw is one fixed padded-slot assignment for the trace, not a new draw per unique SUMO vehicle.",
    "fleet_seeds": [
      1,
      2,
      3,
      4
    ],
    "n": 4,
    "replication_key": "fleet_seed",
    "replication_unit": "fleet_draw",
    "seed_0_in_primary": false,
    "tasks_are_not_replicates": true
  },
  "research_question": "Under the frozen Manchester incident trace and frozen MAPPO vehicle actor, do infrastructure-side placement among ingress_dla, per_task_dla, and p2c_dla and dynamic compute-resource scaling among fixed_1x, static_overprovisioned, reactive, and proactive improve offered-task deadline attainment and its trade-off with rejection and resource cost, when evaluated as paired fleet-draw differences over four matched draws within the bounded staged grid where E3a isolates placement at fixed_1x, E3b holds placement fixed at per_task_dla for scaling contrasts, and E3c tests selected stale-state contrasts (0/1000/3000 ms), without fully crossing every placement with every scaler?",
  "resource_state_diagnostics": {
    "capacity_adjusted_utilization": {
      "bounded": "[0,1]",
      "formula": "drained_work_ms / (active_capacity_units * 1000 work_ms)",
      "utilization_is_per_RSU_per_tick": true,
      "waiting_room_occupancy_is_separate_task_count_and_never_denominator": true
    },
    "execution_share": {
      "formula": "actual_admitted_V2I_execution_count_at_RSU / total_admitted_V2I_execution_count",
      "when_denominator_zero_is_null_with_explicit_reason_not_zeros": true
    },
    "forbidden_behaviors": [
      "raw_over_1000_utilization_under_u_gt_1",
      "queue_occupancy_as_denominator",
      "zero_fill_shares_when_denominator_zero",
      "rejected_task_switches",
      "unordered_or_across_draw_switches",
      "missing_cost_denominator"
    ],
    "no_monetary_or_automatically_authoritative_objective_claim": true,
    "resource_unit_seconds_denominator_stays_required_for_diagnostic_deadline_per_resource_cost": true,
    "target_switching": {
      "counted_over_consecutive_admitted_V2I_tasks_in_deterministic_order": "(outer_tick, task_slot, vehicle_slot)",
      "counts_never_cross_fleet_draws": true,
      "first_admitted_task_is_not_a_switch": true,
      "order_is_exact_deterministic_outer_tick_task_slot_vehicle_slot": true,
      "rejected_and_non_V2I_tasks_excluded": true
    }
  },
  "scenario": {
    "arrival_lambda": 1.5,
    "backhaul_ms": 0.0,
    "date": "2024-03-15",
    "fleet": "uk2030",
    "fleet_status": "provisional",
    "padded_fleet_width": 2488,
    "resolved_cap_tasks_per_rsu": 6220,
    "rsu_admission": "reject",
    "rsu_cap_mode": "reject",
    "rsus": 10,
    "scenario": "Manchester incident trace",
    "smoke_steps": 10,
    "steps": 3600,
    "substep_queue": "sequential",
    "substep_queue_iterations": 3,
    "vehicle_queue": "conserved",
    "waiting_room_cap_per_vehicle": 2.5,
    "window_local": "20:00-21:00 Europe/London"
  },
  "schema_version": "e3_dynamic_resource_v2_contract_v1",
  "staged_design": {
    "budget_reduction_required_if_unreasonable": true,
    "e3a": {
      "cells": 12,
      "equation": "3 placements * 1 scaling * 1 stale * 4 draws = 12",
      "fleet_seeds": [
        1,
        2,
        3,
        4
      ],
      "fresh": true,
      "label": "P2C placement under fixed 1x",
      "placement": [
        "ingress_dla",
        "per_task_dla",
        "p2c_dla"
      ],
      "primary_estimand": "p2c_dla minus per_task_dla offered deadline attainment at fixed_1x stale=0",
      "scaling": [
        "fixed_1x"
      ],
      "scaling_ids_exact": [
        "fixed_1x"
      ],
      "stage_listed_cells": 12,
      "stale_ms": [
        0
      ],
      "unique_cells": 12
    },
    "e3a_stage_listed_cells": 12,
    "e3a_unique_cells": 12,
    "e3b": {
      "cells": 16,
      "co_primary_family": [
        "offered_deadline_attainment",
        "rejection_rate",
        "resource_unit_seconds"
      ],
      "co_primary_note": "Trade-off family, no single metric dominates",
      "equation": "4 scalers * 1 placement * 1 stale * 4 draws = 16 stage-listed; 16 - 4 overlap = 12 unique",
      "fleet_seeds": [
        1,
        2,
        3,
        4
      ],
      "fresh": true,
      "label": "Scaling trade-off family at fixed per-task placement",
      "overlap_note": "per_task_dla/fixed_1x/state_age_ms=0 byte-identical to E3a reused not rerun",
      "overlap_with_e3a": 4,
      "placement": [
        "per_task_dla"
      ],
      "scaling": [
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive"
      ],
      "scaling_ids_exact": [
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive"
      ],
      "stage_listed_cells": 16,
      "stale_ms": [
        0
      ],
      "unique_additional": 12,
      "unique_cells": 12
    },
    "e3b_overlap_with_e3a": 4,
    "e3b_stage_listed_cells": 16,
    "e3b_unique_additional": 12,
    "e3b_unique_equation": "16 - 4 = 12",
    "e3c": {
      "additional_stale_variant_cells_max": 32,
      "contrasts": [
        {
          "comparison": "per_task_dla vs p2c_dla",
          "fixed": "fixed_1x",
          "over_stale_ms": [
            0,
            1000,
            3000
          ]
        },
        {
          "comparison": "reactive vs proactive",
          "fixed_placement": "per_task_dla",
          "over_stale_ms": [
            0,
            1000,
            3000
          ]
        }
      ],
      "depends_on": "fresh construct gates (unit, construct, tiny smoke)",
      "equation": "2 contrasts * 2 arms * 3 staleness * 4 draws = 48 observations; 48 - 16 = 32 stale variants",
      "fresh_observations_reused": 16,
      "identical_fresh_cells_reused_not_rerun": true,
      "label": "Staleness sensitivity (reuses identical fresh cells)",
      "not_double_counted": true,
      "reuses_identical_fresh_cells": true,
      "stale_is_view_parameter": true,
      "stale_variant_equation": "48 - 16 = 32",
      "total_contrast_observations": 48
    },
    "e3c_fresh_observations_reused": 16,
    "e3c_stale_variant_equation": "48 - 16 = 32",
    "e3c_total_contrast_observations": 48,
    "identical_fresh_cells_reused_not_rerun": true,
    "maximum_candidate_unique_cells": 56,
    "not_double_counted": true,
    "note": "Candidate grid before benchmark reduction; final machine plan must be reduced if representative benchmark projects unreasonable bounded local budget. Identical fresh cells are reused across stage summaries rather than rerun and counted twice. Stage-listed base/additional entries = 60 (12 E3a + 16 E3b stage-listed + 32 E3c stale variants); unique planned executions = 56 (12 + 12 + 32) after reusing 4 E3a/E3b overlaps and 16 E3c fresh observations. Equations: 12+16+32=60 stage-listed; 12+12+32=56 unique; 48 total E3c contrast observations -16 fresh reused =32 stale variants. Equations with spaces: 12 + 16 + 32 = 60 stage-listed; 12 + 12 + 32 = 56 unique.",
    "stage_listed_cells": 60,
    "stage_listed_equation": "12 + 16 + 32 = 60",
    "unique_equation": "12 + 12 + 32 = 56"
  },
  "stale_decision_vs_true_execution": {
    "current_capacity_action_application_and_drain_operate_on_true_state": true,
    "deadline_admission_gate_uses_observed_backlog_only": true,
    "deadline_success_based_on_true_simulated_latency_never_stale_estimate": true,
    "deadline_success_is_simulator_outcome_not_physical_lifecycle_evidence": true,
    "forbidden_behaviors": [
      "stale_belief_used_for_actual_latency_or_success",
      "true_state_used_for_stale_decision",
      "executing_pessimistically_rejected_work",
      "delaying_true_capacity_or_drain"
    ],
    "later_scale_actions_do_not_retroactively_reprice_recorded_task": true,
    "observed_decision_backlog_work_ms": "fresh_or_delayed_immutable_backlog_work_ms_plus_decision_overlay_plus_same_tick_reservation_overlay",
    "observed_decision_definition": "fresh/delayed immutable workload plus the decision overlay (stale view plus same-tick reservation overlay); placement and the backlog-only deadline admission gate use this observed value",
    "optimistic_stale_admitted_executes_and_may_miss_per_true_latency": true,
    "pessimistic_stale_rejected_never_executes_even_if_true_would_have_been_feasible": true,
    "physical_started_completed_returned_remain_null": true,
    "placement_uses_observed": true,
    "queue_cap_safety_still_wins_current_not_stale": true,
    "scaling_decisions_observe_delayed_signals": true,
    "true_execution_backlog_work_ms": "current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU",
    "true_execution_determines": [
      "simulated_queue_wait",
      "task_latency",
      "deadline_success",
      "enqueue",
      "subsequent_true_drain"
    ]
  },
  "stale_state_semantics": {
    "applies_to": [
      "invariant_raw_backlog_work_ms_view_for_placement",
      "inherited_backlog_only_deadline_gate",
      "reactive_signal",
      "proactive_signal"
    ],
    "deadline_formula_unchanged": "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]",
    "deadline_workload_observation_has_state_age": true,
    "does_not_mutate": [
      "true_environment",
      "current_active_capacity",
      "pending_actions",
      "current_queue_safety_state"
    ],
    "exposes": [
      "requested_state_age_ms",
      "actual_state_age_ms",
      "observation_time_ms",
      "control_time_ms"
    ],
    "forbidden_behaviors": [
      "stale_deadline_view_silently_becoming_fresh",
      "stale_queue_cap",
      "mutation_of_true_state",
      "pretrace_values_counted_as_proactive_warmup",
      "clock_clamp",
      "state_age_laundering",
      "offset_added_to_action_delay"
    ],
    "fresh_cells_reusable_because": {
      "formulas_use_elapsed_differences": true,
      "offset_does_not_enter_p2c_key_outer_tick_does": true,
      "state_age_0_views_identical": true
    },
    "initialization": {
      "applies_when": "when_stale_robustness_evaluated_all_arms",
      "control_clock_offset_ms": 3000,
      "infrastructure_backlog_and_admitted_arrival_history": "inherited_empty_initial_state",
      "is_declared_simulator_initial_condition": true,
      "not_observed_pretrace_manchester_traffic": true,
      "not_real_world_historical_claim": true,
      "permits_exact_0_1000_3000_without_clamping": true,
      "permits_no_future_leakage": true,
      "permits_no_unavailable_age_laundering": true,
      "prepopulate_control_times_ms": [
        0,
        1000,
        2000
      ],
      "prepopulate_value": "empty_initial_infrastructure_state",
      "pretrace_zeros_do_not_satisfy_proactive_warmup": true,
      "proactive_still_requires_four_actual_trace_observations": true,
      "scaling_delay_cooldown_use_control_clock_differences_no_extra_delay": true,
      "trace_tick_0_maps_to_control_time_ms": 3000
    },
    "queue_ceiling_enforcement": "true_current_waiting_room_occupancy_plus_same_tick_admitted_reservations",
    "queue_ceiling_uses_stale_view": false,
    "queue_safety_invariant_is_current": true,
    "queue_safety_uses_current_not_stale": true,
    "radio_viability_is_current_frozen_channel": true
  },
  "status": "predeclared_before_any_e3_trace_execution",
  "task_accounting": {
    "genuine_classes_dimension": "task_type",
    "outcome_hierarchy": {
      "diagnostic": "admitted_deadline_attainment = deadline_success / admitted (conditional)",
      "headline": "offered_deadline_attainment = deadline_success / offered",
      "headline_is_offered": true
    },
    "rejected_never_executes": true,
    "rejection_breakdown": [
      "gate_rejected",
      "cap_rejected",
      "unavailable"
    ],
    "required": [
      "offered",
      "admitted",
      "rejected",
      "genuine_classes",
      "forwarded",
      "deadline_success"
    ],
    "unavailable_lifecycle": {
      "compute_completed": null,
      "compute_completed_reason": "physical_execution_not_modelled",
      "dropped": null,
      "dropped_reason": "physical_drop_not_modelled",
      "null_means_unmodelled_not_zero": true,
      "returned": null,
      "returned_reason": "result_return_not_modelled",
      "started": null,
      "started_reason": "physical_execution_not_modelled"
    }
  },
  "tick_transition": {
    "applied_receipt_adds": [
      "actual_application_time_ms",
      "actual_to_units"
    ],
    "control_clock_offset_ms": 3000,
    "cooldown": {
      "any_pending_action_blocks_all_new_directions": true,
      "elapsed_gte_5000ms_permits_new_request": true,
      "just_applied_action_starts_cooldown_so_cannot_request_again_that_tick": true,
      "starts_at_actual_application_time": true
    },
    "counts_expose_separately": [
      "scheduled_requests",
      "applied_up_actions",
      "applied_down_actions"
    ],
    "forbidden_behaviors": [
      "decision-time cooldown",
      "same-tick post-apply request",
      "action-count conflation",
      "ambiguous timestamps"
    ],
    "future_leakage_forbidden": true,
    "proactive_samples_are_completed_prior_trace_interval_admitted_arrival_work_samples": {
      "aged_arm_uses_only_samples_present_in_selected_snapshot": true,
      "at_tick_t_no_sample_from_current_tick_available": true,
      "four_actual_trace_intervals_must_have_completed": true,
      "pretrace_empty_values_never_satisfy_warm_up": true
    },
    "reactive_tick_entry_signal_is_aged_raw_service_backlog_snapshot": true,
    "requested_receipt_fields": [
      "draw",
      "rsu",
      "direction",
      "from_units",
      "requested_to_units",
      "decision_time_ms",
      "due_time_ms",
      "observed_state_time_ms",
      "state_age_ms",
      "signal_name",
      "signal_value"
    ],
    "resource_cost_follows_applied_capacity_only": true,
    "reused_state_age_0_cell_bytes_truly_identical": true,
    "telemetry_schema_same_for_E3a_b_c_including_fresh_cells": true,
    "zero_based_trace_tick_control_time_t": {
      "i_start_from_true_state_after_prior_interval_drain": true,
      "ii_apply_one_pending_action_if_due_emit_applied_receipt_clear_pending": true,
      "iii_capture_immutable_tick_entry_infrastructure_snapshot_after_due_action_before_current_tick_placement_admission": true,
      "iv_select_exact_t_state_age_snapshot_for_decision_signals": true,
      "v_if_no_pending_and_cooldown_permits_make_at_most_one_scaler_decision_per_RSU_and_possibly_emit_schedule_one_requested_action": true,
      "vi_process_all_five_task_slots_sequentially_without_advancing_time": true,
      "vii_drain_true_raw_backlog_once_by_min_backlog_u_times_1000_work_ms": true,
      "viii_charge_post_due_action_capacity_u_for_interval_t_t_plus_1000ms": true
    }
  },
  "time_model": {
    "candidate_stale_levels_ms": [
      0,
      1000,
      3000
    ],
    "control_clock_applies_when": "when_stale_robustness_evaluated_all_arms",
    "control_clock_offset_ms": 3000,
    "is_declared_simulator_initial_condition_not_observed_traffic": true,
    "outer_tick_ms": 1000,
    "permits_exact_views_without_clamping": true,
    "prepopulate_control_times_ms": [
      0,
      1000,
      2000
    ],
    "prepopulate_value": "empty_initial_infrastructure_state",
    "proactive_pretrace_does_not_satisfy_warmup": true,
    "scaling_delay_uses_control_clock_differences": true,
    "stale_levels_are_candidate_values": true,
    "state_age_is_signal_snapshot_age": true,
    "state_age_unit": "integer_simulator_ms",
    "trace_tick_0_maps_to_control_time_ms": 3000,
    "within_tick_slots_advance_physical_time": false,
    "within_tick_task_slots": 5
  },
  "v2i_latency_outcome_contract": {
    "admission_feasibility_predicate_is_strict_less": true,
    "admission_feasibility_predicate_reference": "observed_decision_backlog_work_ms[rsu] < task_deadline_ms",
    "at_admission_record_with_u_current_applied_units": {
      "admission_feasibility_predicate_is_strict_less": true,
      "admission_feasibility_predicate_reference": "observed_decision_backlog_work_ms[rsu] < task_deadline_ms",
      "backlog_still_evolves_thereafter_under_actual_capacity": true,
      "comparator_conflation_forbidden": true,
      "deadline_success_comparator": "<=",
      "deadline_success_equality_is_success": true,
      "deadline_success_is_inherited_e2d_outcome": true,
      "deadline_success_rule": "simulated_latency_ms <= task_deadline_ms",
      "equality_at_admission_gate_is_infeasible": true,
      "inherited_e2d_outcome_compatibility": true,
      "inherited_e2d_reference": "vec_env 2f63706f46319433a2ba3af1df97afd0e56a95d1 jaxmarl/env/vec_jax.py:736 deadline_met = latency <= deadline",
      "later_scaling_does_not_recompute_latency": true,
      "outcome_and_feasibility_comparators_are_distinct": true,
      "radio_forward_return_formulas_and_random_raw_service_draw_remain_inherited": true,
      "raw_work_enqueued_is_never_divided_by_u": true,
      "rejected_work_never_enqueues_never_succeeds_and_inherited_10_deadline_penalty_is_explicitly_not_valid_latency_observation": true,
      "simulated_latency_ms_equation": "current_ingress_tx_ms + forwarding_ms + true_execution_backlog_work_ms/u + raw_task_service_work_ms/u + current_return_tx_ms"
    },
    "forbidden_behaviors": [
      "backlog-only/stale outcome latency",
      "divided enqueue work",
      "later repricing",
      "rejected penalty in latency mean"
    ],
    "report": {
      "admitted_task_latency_only_and_any_declared_deadline_met_diagnostic": true,
      "offered_task_latency_is_null_unavailable_because_rejected_penalty_values_are_not_physical_latency": true,
      "started_compute_completed_returned_dropped_remain_null_with_reasons": true
    }
  }
}
```
<!-- END_E3_CANONICAL_JSON -->

*End of normative contract v1 — Markdown is generated view; JSON is authoritative.*

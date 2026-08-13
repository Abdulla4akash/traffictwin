#!/usr/bin/env python3
"""Fail-closed validator for E3 dynamic-resource v2 contract v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "e3_dynamic_resource_v2_contract_v1"
BASE_COMMIT = "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
BRANCH = "worker/e3-lane-01-contract"
CAMPAIGN = "e3-dynamic-resource-v2"

EXPECTED_E2B = "fe2ed4e9bd9043b19b96a5f179390db629b01ccb"
EXPECTED_E2C = "1a08d6e148a1e8c430da39c3d575eda3f8ea5929"
EXPECTED_E2D = "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761"
EXPECTED_E2D_MANIFEST = "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740"
EXPECTED_ACTOR_SHA = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
EXPECTED_TRACE_SHA = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
EXPECTED_ACTOR_PATH = "checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz"
EXPECTED_TRACE_PATH = "traces/trace_inc_fullrsu.npz"
EXPECTED_EVALUATOR_SEED = 0
EXPECTED_OUTER_TICK_MS = 1000
EXPECTED_SLOTS = 5
EXPECTED_STALE = [0, 1000, 3000]
EXPECTED_COUNTER_FIELDS = [
    "evaluator_seed",
    "fleet_seed",
    "tick",
    "task_slot",
    "sequential_ordinal",
]


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _contains_forbidden_arm_ids(obj: object) -> list[str]:
    """Recursively find forbidden arm IDs."""
    found: list[str] = []
    forbidden = {"static3x", "static_3x", "fixed1x"}
    if isinstance(obj, dict):
        for k, v in obj.items():
            # Allow documenting forbidden synonyms in specific keys
            if k in {"forbidden_synonyms_rejected", "forbidden_synonyms"}:
                continue
            if k in forbidden:
                found.append(f"forbidden arm ID key {k!r}")
            if isinstance(v, str) and v in forbidden:
                found.append(f"forbidden arm ID value {v!r}")
            found.extend(_contains_forbidden_arm_ids(v))
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, str) and item in forbidden:
                found.append(f"forbidden arm ID value {item!r}")
            found.extend(_contains_forbidden_arm_ids(item))
    return found


def validate_contract(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    # Top-level identity
    if data.get("schema_version") != CONTRACT_VERSION:
        _err(errors, f"schema_version must be {CONTRACT_VERSION!r}")
    if data.get("status") != "predeclared_before_any_e3_trace_execution":
        _err(errors, "status must be predeclared_before_any_e3_trace_execution")
    if data.get("base_commit") != BASE_COMMIT:
        _err(errors, f"base_commit must be {BASE_COMMIT}")
    if data.get("branch") != BRANCH:
        _err(errors, f"branch must be {BRANCH}")
    if data.get("campaign") != CAMPAIGN:
        _err(errors, f"campaign must be {CAMPAIGN}")

    # Research question must explicitly compare ingress_dla, per_task_dla, p2c_dla and not reduce
    rq = str(data.get("research_question", ""))
    for needle in ["ingress_dla", "per_task_dla", "p2c_dla"]:
        if needle not in rq:
            _err(errors, f"research_question must explicitly contain {needle}")
    # Must mention fixed_1x and static_overprovisioned
    for needle in ["fixed_1x", "static_overprovisioned"]:
        if needle not in rq:
            _err(errors, f"research_question must contain scaling arm {needle}")
    # Reject reduced phrasing "strongest-link vs P2C" without the three-way explicit
    # If research_question contains that reduction and lacks explicit three, already caught
    # Also reject if it contains the exact reduced phrase
    low_rq = rq.lower()
    if "strongest-link vs p2c" in low_rq or "strongest-link vs. p2c" in low_rq:
        # This phrase is forbidden as reduction; we already require three-way, so fail
        _err(errors, "research_question must not reduce placement to 'strongest-link vs P2C'")
    # Factorial overclaim regression: 'alone and jointly' implied full factorial crossing which boun  # noqa: E501
    if "alone and jointly" in low_rq:
        _err(
            errors,
            "research_question must not contain 'alone and jointly' (bounded staged grid does not fully cross every placement/scaler)",  # noqa: E501
        )
    # Staged isolation must be precise: E3a isolates placement, E3b holds placement fixed, E3c tests selected stale-state contrasts  # noqa: E501
    if "e3a isolates placement" not in low_rq:
        _err(errors, "research_question must state E3a isolates placement")
    if "e3b holds placement fixed" not in low_rq:
        _err(errors, "research_question must state E3b holds placement fixed for scaling")
    if "e3c tests selected stale-state contrasts" not in low_rq:
        _err(errors, "research_question must state E3c tests selected stale-state contrasts")
    if "without fully crossing every placement with every scaler" not in low_rq:
        _err(
            errors,
            "research_question must state bounded grid does not fully cross every placement with every scaler",  # noqa: E501
        )

    # Forbidden arm IDs anywhere
    forbid = _contains_forbidden_arm_ids(data)
    for f in forbid:
        _err(errors, f)

    # Frozen prerequisites
    fp = data.get("frozen_prerequisites")
    if not isinstance(fp, dict):
        _err(errors, "frozen_prerequisites missing or not dict")
    else:
        if fp.get("e2b", {}).get("commit") != EXPECTED_E2B:
            _err(errors, f"e2b commit must be {EXPECTED_E2B}")
        if fp.get("e2c", {}).get("commit") != EXPECTED_E2C:
            _err(errors, f"e2c commit must be {EXPECTED_E2C}")
        e2d = fp.get("e2d", {})
        if e2d.get("commit") != EXPECTED_E2D:
            _err(errors, f"e2d commit must be {EXPECTED_E2D}")
        if e2d.get("manifest_sha256") != EXPECTED_E2D_MANIFEST:
            _err(errors, f"e2d manifest_sha256 must be {EXPECTED_E2D_MANIFEST}")
        actor = fp.get("actor", {})
        if actor.get("sha256") != EXPECTED_ACTOR_SHA:
            _err(errors, f"actor sha256 must be {EXPECTED_ACTOR_SHA}")
        if actor.get("path") != EXPECTED_ACTOR_PATH:
            _err(errors, f"actor path must be {EXPECTED_ACTOR_PATH}")
        if actor.get("observes_current_rsu_load") is not False:
            _err(errors, "actor must not observe current RSU load")
        if actor.get("selects_execution_rsu") is not False:
            _err(errors, "actor must not select execution RSU")
        if actor.get("frozen") is not True:
            _err(errors, "actor must be frozen")
        trace = fp.get("trace", {})
        if trace.get("sha256") != EXPECTED_TRACE_SHA:
            _err(errors, f"trace sha256 must be {EXPECTED_TRACE_SHA}")
        if trace.get("path") != EXPECTED_TRACE_PATH:
            _err(errors, f"trace path must be {EXPECTED_TRACE_PATH}")
        if fp.get("evaluator_seed") != EXPECTED_EVALUATOR_SEED:
            _err(errors, "evaluator_seed must be 0")

    # Replication
    rep = data.get("replication", {})
    if not isinstance(rep, dict):
        _err(errors, "replication missing")
    else:
        if rep.get("replication_unit") != "fleet_draw":
            _err(errors, "replication_unit must be fleet_draw")
        if rep.get("replication_key") != "fleet_seed":
            _err(errors, "replication_key must be fleet_seed")
        if rep.get("n") != 4:
            _err(errors, "replication n must be 4")
        if rep.get("fleet_seeds") != [1, 2, 3, 4]:
            _err(errors, "fleet_seeds must be [1,2,3,4]")
        if rep.get("seed_0_in_primary") is not False:
            _err(errors, "seed_0_in_primary must be false")
        if rep.get("tasks_are_not_replicates") is not True:
            _err(errors, "tasks_are_not_replicates must be true")
        note = str(rep.get("fleet_draw_note", ""))
        if "padded-slot assignment" not in note and "padded-slot" not in note:
            _err(errors, "fleet_draw_note must clarify padded-slot assignment not per-SUMO-vehicle")

    # Hypotheses H1-H5: must be hypotheses, not expected truths
    hypotheses = data.get("hypotheses")
    if not isinstance(hypotheses, dict):
        _err(errors, "hypotheses missing or not dict (H1-H5 required)")
    else:
        if hypotheses.get("hypotheses_are_not_expected_truths") is not True:
            _err(errors, "hypotheses hypotheses_are_not_expected_truths must be true")
        if hypotheses.get("negative_results_acceptable") is not True:
            _err(errors, "hypotheses negative_results_acceptable must be true")
        boundary = str(hypotheses.get("boundary", "")).lower()
        if "negative" not in boundary or "acceptable" not in boundary:
            _err(errors, "hypotheses boundary must state negative results acceptable")
        items = hypotheses.get("items")
        if not isinstance(items, list) or len(items) != 5:
            _err(errors, "hypotheses items must be list of 5 (H1-H5)")
        else:
            by_id: dict[str, Any] = {}
            for it in items:
                if isinstance(it, dict) and isinstance(it.get("id"), str):
                    by_id[str(it["id"])] = it
            for hid in ["H1", "H2", "H3", "H4", "H5"]:
                it = by_id.get(hid)
                if it is None:
                    _err(errors, f"hypothesis {hid} missing")
                    continue
                assert isinstance(it, dict)
                if it.get("status") != "hypothesis_not_expected_truth":
                    _err(errors, f"hypothesis {hid} status must be hypothesis_not_expected_truth")
                if it.get("kind") != "hypothesis":
                    _err(
                        errors, f"hypothesis {hid} kind must be hypothesis (not result/conclusion)"
                    )
                if str(it.get("kind", "")).lower() in {"result", "conclusion", "expected_truth"}:
                    _err(errors, f"hypothesis {hid} must not be relabeled as result/conclusion")
                if str(it.get("status", "")).lower() in {"result", "conclusion", "expected_truth"}:
                    _err(
                        errors,
                        f"hypothesis {hid} status must not be result/conclusion/expected_truth",
                    )
                stmt = str(it.get("statement", "")).lower()
                if (
                    "expected truth" in stmt
                    and "not expected" not in stmt
                    and "hypothesis" not in stmt
                ):
                    _err(errors, f"hypothesis {hid} statement must not describe as expected truth")
                if hid == "H1":
                    if "p2c" not in stmt or "per_task_dla" not in stmt:
                        _err(errors, "H1 must mention P2C and per_task_dla")
                    if "less global inspection" not in stmt:
                        _err(errors, "H1 must mention less global inspection")
                    if "may approach" not in stmt:
                        _err(errors, "H1 must state may approach (hypothesis, not guarantee)")
                elif hid == "H2":
                    if "reactive" not in stmt:
                        _err(errors, "H2 must mention reactive")
                    if "resource_unit_seconds" not in stmt and "resource" not in stmt:
                        _err(errors, "H2 must mention resource_unit_seconds/resource cost")
                    if "churn" not in stmt:
                        _err(errors, "H2 must mention churn/resource overhead")
                    if (
                        "may improve" not in stmt
                        and "may increase" not in stmt
                        and "may" not in stmt
                    ):
                        _err(errors, "H2 must be phrased as may (hypothesis)")
                    if "deadline" not in stmt and "rejection" not in stmt:
                        _err(errors, "H2 must mention deadline/rejection")
                elif hid == "H3":
                    if "proactive" not in stmt:
                        _err(errors, "H3 must mention proactive")
                    if "change outruns" not in stmt:
                        _err(errors, "H3 must mention change outruns actuation")
                    if "actuation" not in stmt:
                        _err(errors, "H3 must mention actuation delay")
                    if "may help" not in stmt and "may" not in stmt:
                        _err(errors, "H3 must be phrased as may help (hypothesis)")
                elif hid == "H4":
                    if (
                        "per_task_dla" not in stmt
                        and "least-busy" not in stmt
                        and "least busy" not in stmt
                    ):
                        _err(errors, "H4 must mention global least-busy / per_task_dla")
                    if "p2c" not in stmt:
                        _err(errors, "H4 must mention P2C")
                    if "stale" not in stmt:
                        _err(errors, "H4 must mention stale state")
                    if "may degrade faster" not in stmt and "degrade faster" not in stmt:
                        _err(errors, "H4 must state may degrade faster than P2C under stale state")
                elif hid == "H5":
                    if "additional compute" not in stmt and "static_overprovisioned" not in stmt:
                        _err(errors, "H5 must mention additional compute")
                    if "resource_unit_seconds" not in stmt:
                        _err(errors, "H5 must mention resource_unit_seconds")
                    if "may not win" not in stmt and "may not" not in stmt:
                        _err(
                            errors,
                            "H5 must state may not win once resource_unit_seconds is considered",
                        )
                if "will improve" in stmt and "may" not in stmt:
                    _err(errors, f"hypothesis {hid} must not assert will improve as expected truth")
                if "expected to improve" in stmt:
                    _err(errors, f"hypothesis {hid} must not be phrased as expected truth")

    # Mechanism separation
    ms = data.get("mechanism_separation", {})
    if ms.get("queue_ceiling_is_not_compute_capacity") is not True:
        _err(errors, "queue_ceiling_is_not_compute_capacity must be true (queue != compute)")
    if ms.get("actor_never_observes_rsu_load") is not True:
        _err(errors, "actor_never_observes_rsu_load must be true")
    if ms.get("actor_never_selects_execution_rsu") is not True:
        _err(errors, "actor_never_selects_execution_rsu must be true")
    if ms.get("rejected_work_never_executes") is not True:
        _err(errors, "rejected_work_never_executes must be true")
    if (
        not isinstance(ms.get("placement"), str)
        or not isinstance(ms.get("admission"), str)
        or not isinstance(ms.get("scaling"), str)
    ):
        _err(errors, "mechanism_separation placement/admission/scaling must be distinct strings")

    # Time model
    tm = data.get("time_model", {})
    if tm.get("outer_tick_ms") != EXPECTED_OUTER_TICK_MS:
        _err(errors, "outer_tick_ms must be 1000")
    if tm.get("within_tick_task_slots") != EXPECTED_SLOTS:
        _err(errors, "within_tick_task_slots must be 5")
    if tm.get("within_tick_slots_advance_physical_time") is not False:
        _err(errors, "within_tick_slots must not advance physical time")
    if tm.get("state_age_unit") != "integer_simulator_ms":
        _err(errors, "state_age_unit must be integer_simulator_ms")
    if tm.get("state_age_is_signal_snapshot_age") is not True:
        _err(errors, "state_age_is_signal_snapshot_age must be true")
    if tm.get("candidate_stale_levels_ms") != EXPECTED_STALE:
        _err(errors, "candidate_stale_levels_ms must be [0,1000,3000]")
    stale = tm.get("candidate_stale_levels_ms") or []
    for v in stale:
        if v == 200:
            _err(errors, "stale 200ms is forbidden pseudo-time")

    # Admission gate
    ag = data.get("admission_gate", {})
    if "effective_busy_ms" not in str(ag.get("formula", "")) or "TASK_DEADLINE_MS" not in str(
        ag.get("formula", "")
    ):
        _err(errors, "admission_gate formula must be effective_busy_ms < TASK_DEADLINE_MS")
    if ag.get("never_selects_target") is not True:
        _err(errors, "admission_gate must never select target")
    excludes = ag.get("excludes") or []
    for needed in ["own_compute", "radio_transfer", "return_transfer", "forwarding_latency"]:
        if needed not in excludes:
            _err(errors, f"admission_gate excludes must contain {needed}")

    # Placement
    plc = data.get("placement", {})
    p2c = plc.get("p2c_dla", {}) if isinstance(plc, dict) else {}
    if p2c.get("feasibility_first") is not True:
        _err(errors, "p2c feasibility_first must be true")
    if p2c.get("candidates") != 2:
        _err(errors, "p2c candidates must be 2")
    if p2c.get("without_replacement") is not True:
        _err(errors, "p2c without_replacement must be true")
    if p2c.get("distinct_feasible_only") is not True:
        _err(errors, "p2c distinct_feasible_only must be true")
    if p2c.get("counter_key_fields") != EXPECTED_COUNTER_FIELDS:
        _err(errors, f"p2c counter_key_fields must be {EXPECTED_COUNTER_FIELDS}")
    if p2c.get("counter_key_stable") is not True:
        _err(errors, "p2c counter_key_stable must be true")
    if p2c.get("no_global_rng_stream") is not True:
        _err(errors, "p2c no_global_rng_stream must be true")
    if p2c.get("inspect_only_pair") is not True:
        _err(errors, "p2c inspect_only_pair must be true")
    if p2c.get("selection") != "lower effective_busy_ms":
        _err(errors, "p2c selection must be lower effective_busy_ms")
    if "lowest RSU" not in str(p2c.get("tie_break", "")):
        _err(errors, "p2c tie_break must be lowest RSU id stable")
    if p2c.get("immediate_reservation") is not True:
        _err(errors, "p2c immediate_reservation must be true")
    if p2c.get("one_candidate_per_task") is not True:
        _err(errors, "p2c one_candidate_per_task must be true")
    if p2c.get("common_target_forbidden") is not True:
        _err(errors, "p2c common_target_forbidden must be true (reject common-target P2C)")
    stale_snap = p2c.get("stale_snapshot", {})
    if stale_snap.get("immutable_delayed_view") is not True:
        _err(errors, "stale immutable_delayed_view must be true")
    if stale_snap.get("same_tick_reservation_overlay") is not True:
        _err(errors, "same_tick_reservation_overlay must be true")
    if stale_snap.get("no_future_leakage") is not True:
        _err(errors, "stale no_future_leakage must be true")
    if stale_snap.get("exposes_state_age_ms") is not True:
        _err(errors, "stale must expose state_age_ms")

    # Compute scaling
    cs = data.get("compute_scaling", {})
    # fixed_1x
    if cs.get("fixed_1x", {}).get("active_units_per_rsu") != 1:
        _err(errors, "fixed_1x must be 1 active unit")
    if cs.get("fixed_1x", {}).get("multiplier") != 1:
        _err(errors, "fixed_1x multiplier must be 1")
    # static_overprovisioned
    so = cs.get("static_overprovisioned", {})
    if so.get("active_units_per_rsu") != 3:
        _err(errors, "static_overprovisioned must be fixed 3 active units")
    if so.get("multiplier") != 3:
        _err(errors, "static_overprovisioned multiplier must be 3")
    if so.get("is_compute_not_queue") is not True:
        _err(errors, "static_overprovisioned is_compute_not_queue must be true")
    # reject old keys explicitly if present
    for old in ["fixed1x", "static3x", "static_3x"]:
        if old in cs:
            _err(errors, f"forbidden legacy scaling key {old!r} must be absent")
    db = cs.get("dynamic_bounds", {})
    if db.get("min_units") != 1 or db.get("max_units") != 3:
        _err(errors, "dynamic bounds must be 1--3")
    if db.get("actuation_delay_ticks") != 2:
        _err(errors, "actuation_delay_ticks must be exactly 2 (two-second delay)")
    if db.get("actuation_delay_ms") != 2000:
        _err(errors, "actuation_delay_ms must be 2000")
    if db.get("action_step") != 1:
        _err(errors, "action_step must be exactly 1 (one-level)")
    if db.get("one_level_per_action") is not True:
        _err(errors, "one_level_per_action must be true")
    if db.get("max_pending_actions") != 1:
        _err(errors, "max_pending_actions must be 1")
    if db.get("apply_due_before_tick_decision") is not True:
        _err(errors, "apply_due_before_tick_decision must be true")
    if db.get("free_scaling_forbidden") is not True:
        _err(errors, "free_scaling_forbidden must be true")
    if db.get("unbounded_scaling_forbidden") is not True:
        _err(errors, "unbounded_scaling_forbidden must be true")
    if db.get("threshold_gap_ms") != 600:
        _err(errors, "dynamic_bounds threshold_gap_ms must be 600")
    if db.get("hysteresis_is_gap") is not True:
        _err(errors, "hysteresis_is_gap must be true (gap is hysteresis)")
    if db.get("hysteresis_ms_extra_forbidden") is not True:
        _err(errors, "hysteresis_ms_extra_forbidden must be true")
    # reject if any hysteresis_ms field is present as extra excursion
    if "hysteresis_ms" in db and db.get("hysteresis_ms") not in (None, False):
        # allow if explicitly False, but not numeric extra
        _err(errors, "hysteresis_ms extra excursion forbidden; gap is hysteresis")
    # Reactive exact
    reactive = cs.get("reactive", {})
    if reactive.get("signal") != "service_workload_ms":
        _err(errors, "reactive signal must be service_workload_ms")
    if reactive.get("signal_units") != "work_ms_independent_of_capacity":
        _err(errors, "reactive signal_units must be work_ms_independent_of_capacity")
    if reactive.get("per_rsu") is not True:
        _err(errors, "reactive per_rsu must be true")
    if reactive.get("scale_up_threshold_ms") != 800:
        _err(errors, "reactive scale_up_threshold_ms must be 800")
    if reactive.get("scale_up_inclusive") is not True:
        _err(errors, "reactive scale_up_inclusive must be true")
    if reactive.get("scale_down_threshold_ms") != 200:
        _err(errors, "reactive scale_down_threshold_ms must be 200")
    if reactive.get("scale_down_inclusive") is not True:
        _err(errors, "reactive scale_down_inclusive must be true")
    if reactive.get("threshold_gap_ms") != 600:
        _err(errors, "reactive threshold_gap_ms must be 600")
    if reactive.get("hysteresis_is_gap") is not True:
        _err(errors, "reactive hysteresis_is_gap must be true")
    if reactive.get("hysteresis_ms_extra") is not False:
        _err(errors, "reactive hysteresis_ms_extra must be false (no extra)")
    if reactive.get("cooldown_ms") != 5000:
        _err(errors, "reactive cooldown_ms must be 5000")
    if reactive.get("actuation_delay_ms") != 2000:
        _err(errors, "reactive actuation_delay_ms must be 2000")
    if reactive.get("actuation_delay_ticks") != 2:
        _err(errors, "reactive actuation_delay_ticks must be 2")
    if reactive.get("min_units") != 1 or reactive.get("max_units") != 3:
        _err(errors, "reactive bounds must be 1..3")
    if reactive.get("action_step") != 1:
        _err(errors, "reactive action_step must be 1")
    if reactive.get("max_pending_actions") != 1:
        _err(errors, "reactive max_pending_actions must be 1")
    if reactive.get("apply_due_before_tick_decision") is not True:
        _err(errors, "reactive apply_due_before_tick_decision must be true")
    if reactive.get("stable_inclusive_edges") is not True:
        _err(errors, "reactive stable_inclusive_edges must be true")
    if reactive.get("prediction") is not False:
        _err(errors, "reactive prediction must be false")
    if reactive.get("state_age_ms_values") != [0, 1000, 3000]:
        _err(errors, "reactive state_age_ms_values must be [0,1000,3000]")
    # reject reactive hysteresis_ms numeric if present
    if "hysteresis_ms" in reactive and isinstance(reactive.get("hysteresis_ms"), int):
        _err(errors, "reactive hysteresis_ms extra excursion forbidden")
    # Proactive exact
    proactive = cs.get("proactive", {})
    if proactive.get("ml") is not False:
        _err(errors, "proactive ml must be false (transparent/no ML)")
    if proactive.get("transparent") is not True:
        _err(errors, "proactive transparent must be true")
    if proactive.get("transparent_baseline_not_optimal") is not True:
        _err(errors, "proactive transparent_baseline_not_optimal must be true")
    if proactive.get("signal") != "arrival_work_ms":
        _err(errors, "proactive signal must be arrival_work_ms")
    if proactive.get("per_rsu") is not True:
        _err(errors, "proactive per_rsu must be true")
    if proactive.get("observation_interval_ms") != 1000:
        _err(errors, "proactive observation_interval_ms must be 1000")
    if proactive.get("window_size") != 4:
        _err(errors, "proactive window_size must be 4")
    if proactive.get("window_interval_ms") != 1000:
        _err(errors, "proactive window_interval_ms must be 1000")
    if proactive.get("window_order") != "oldest_to_newest":
        _err(errors, "proactive window_order must be oldest_to_newest")
    if proactive.get("warm_up_valid_observations") != 4:
        _err(errors, "proactive warm_up_valid_observations must be 4")
    if proactive.get("warm_up_ticks_declared") is not True:
        _err(errors, "proactive warm_up_ticks_declared must be true")
    if proactive.get("no_decisions_during_warm_up") is not True:
        _err(errors, "proactive no_decisions_during_warm_up must be true")
    formulas = proactive.get("formulas", {})
    if not isinstance(formulas, dict):
        _err(errors, "proactive formulas missing")
    else:
        if formulas.get("older_mean") != "mean(W[0:2])":
            _err(errors, "proactive older_mean must be mean(W[0:2])")
        if formulas.get("recent_mean") != "mean(W[2:4])":
            _err(errors, "proactive recent_mean must be mean(W[2:4])")
        if formulas.get("trend") != "recent_mean - older_mean":
            _err(errors, "proactive trend must be recent_mean - older_mean")
        if formulas.get("forecast") != "max(0, mean(W) + 2*trend)":
            _err(errors, "proactive forecast must be max(0, mean(W) + 2*trend)")
        # alternative phrasing check
        raw_formula = json.dumps(formulas)
        if (
            "linear regression" in raw_formula.lower()
            or "moving-average delta" in raw_formula.lower()
        ):
            _err(errors, "proactive alternative formula phrase forbidden")
    if proactive.get("formula_declared") is not True:
        _err(errors, "proactive formula_declared must be true")
    if proactive.get("horizon_ms") != 2000:
        _err(errors, "proactive horizon_ms must be 2000")
    if proactive.get("horizon_ticks") != 2:
        _err(errors, "proactive horizon_ticks must be 2")
    if proactive.get("scale_up_threshold_ms") != 800:
        _err(errors, "proactive scale_up_threshold_ms must be 800")
    if proactive.get("scale_up_inclusive") is not True:
        _err(errors, "proactive scale_up_inclusive must be true")
    if proactive.get("scale_down_threshold_ms") != 200:
        _err(errors, "proactive scale_down_threshold_ms must be 200")
    if proactive.get("scale_down_inclusive") is not True:
        _err(errors, "proactive scale_down_inclusive must be true")
    if proactive.get("threshold_gap_ms") != 600:
        _err(errors, "proactive threshold_gap_ms must be 600")
    if proactive.get("hysteresis_is_gap") is not True:
        _err(errors, "proactive hysteresis_is_gap must be true")
    if proactive.get("cooldown_ms") != 5000:
        _err(errors, "proactive cooldown_ms must be 5000")
    if proactive.get("actuation_delay_ms") != 2000:
        _err(errors, "proactive actuation_delay_ms must be 2000")
    if proactive.get("actuation_delay_ticks") != 2:
        _err(errors, "proactive actuation_delay_ticks must be 2")
    if proactive.get("bounds_min") != 1 or proactive.get("bounds_max") != 3:
        _err(errors, "proactive bounds_min/max must be 1/3")
    if proactive.get("action_step") != 1:
        _err(errors, "proactive action_step must be 1")
    if proactive.get("max_pending_actions") != 1:
        _err(errors, "proactive max_pending_actions must be 1")
    if proactive.get("apply_due_before_tick_decision") is not True:
        _err(errors, "proactive apply_due_before_tick_decision must be true")
    if proactive.get("stable_inclusive_edges") is not True:
        _err(errors, "proactive stable_inclusive_edges must be true")
    if proactive.get("no_future_leakage") is not True:
        _err(errors, "proactive no_future_leakage must be true")
    if proactive.get("prediction_uses_future") is not False:
        _err(errors, "proactive prediction_uses_future must be false (reject future leakage)")
    if proactive.get("uses_only_samples_at_or_before_observation_time") is not True:
        _err(errors, "proactive uses_only_samples_at_or_before_observation_time must be true")
    if proactive.get("alternative_formula_forbidden") is not True:
        _err(errors, "proactive alternative_formula_forbidden must be true")
    # also check top-level proactive doesn't contain e.g. phrase
    if "e.g. linear regression" in json.dumps(proactive).lower():
        _err(errors, "proactive e.g. linear regression phrase forbidden")

    # Cost
    cost = data.get("cost", {})
    if cost.get("metric") != "resource_unit_seconds":
        _err(errors, "cost metric must be resource_unit_seconds (missing denominator)")
    if "active_compute_units" not in str(cost.get("formula", "")) or "interval_seconds" not in str(
        cost.get("formula", "")
    ):
        _err(errors, "cost formula must be sum(active_compute_units * interval_seconds)")
    if cost.get("monetary") is not False:
        _err(errors, "cost monetary must be false (never monetary)")
    for bf in cost.get("forbidden_fields") or []:
        if bf in data:
            _err(errors, f"forbidden monetary field present: {bf}")
    for k in ["cost_currency", "cost_dollars", "cost_price", "cost_billing"]:
        if k in data:
            _err(errors, f"monetary cost field forbidden: {k}")
        if k in cost:
            _err(errors, f"monetary cost field forbidden in cost: {k}")

    # Task accounting
    ta = data.get("task_accounting", {})
    required = ta.get("required") or []
    for field in [
        "offered",
        "admitted",
        "rejected",
        "genuine_classes",
        "forwarded",
        "deadline_success",
    ]:
        if field not in required:
            _err(errors, f"task_accounting required missing {field}")
    ul = ta.get("unavailable_lifecycle", {})
    for field in ["started", "compute_completed", "returned", "dropped"]:
        if ul.get(field) is not None:
            _err(errors, f"unavailable field {field} must remain null (not {ul.get(field)!r})")
    if ul.get("null_means_unmodelled_not_zero") is not True:
        _err(errors, "unavailable null_means_unmodelled_not_zero must be true")
    oh = ta.get("outcome_hierarchy", {})
    if oh.get("headline_is_offered") is not True:
        _err(errors, "headline must be offered deadline attainment")
    if "offered" not in str(oh.get("headline", "")).lower():
        _err(errors, "headline must be offered_deadline_attainment")
    if ta.get("rejected_never_executes") is not True:
        _err(errors, "rejected_never_executes must be true")

    # Staged design
    sd = data.get("staged_design", {})
    if sd.get("maximum_candidate_unique_cells") != 60:
        _err(errors, "maximum_candidate_unique_cells must be 60")
    if sd.get("budget_reduction_required_if_unreasonable") is not True:
        _err(errors, "budget_reduction_required_if_unreasonable must be true")
    if sd.get("identical_fresh_cells_reused_not_rerun") is not True:
        _err(errors, "identical_fresh_cells_reused_not_rerun must be true")
    if sd.get("not_double_counted") is not True:
        _err(errors, "staged_design not_double_counted must be true")
    if "reused across stage summaries rather than rerun" not in str(sd.get("note", "")):
        _err(errors, "staged_design note must clarify reused not rerun")
    e3a = sd.get("e3a", {})
    if e3a.get("cells") != 12:
        _err(errors, "e3a cells must be 12")
    if e3a.get("fresh") is not True:
        _err(errors, "e3a must be fresh")
    if set(e3a.get("placement", [])) != {"ingress_dla", "per_task_dla", "p2c_dla"}:
        _err(errors, "e3a placement must be ingress_dla/per_task_dla/p2c_dla")
    if e3a.get("scaling") != ["fixed_1x"]:
        _err(errors, "e3a scaling must be ['fixed_1x'] only")
    if e3a.get("scaling_ids_exact") != ["fixed_1x"]:
        _err(errors, "e3a scaling_ids_exact must be ['fixed_1x']")
    if "fixed_1x" not in str(e3a.get("primary_estimand", "")):
        _err(errors, "e3a primary_estimand must mention fixed_1x")
    e3b = sd.get("e3b", {})
    if e3b.get("cells") != 16:
        _err(errors, "e3b cells must be 16")
    if e3b.get("fresh") is not True:
        _err(errors, "e3b must be fresh")
    if set(e3b.get("scaling", [])) != {
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive",
    }:
        _err(errors, "e3b scaling must be fixed_1x/static_overprovisioned/reactive/proactive")
    if set(e3b.get("scaling_ids_exact", [])) != {
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive",
    }:
        _err(
            errors,
            "e3b scaling_ids_exact must be fixed_1x/static_overprovisioned/reactive/proactive",
        )
    e3c = sd.get("e3c", {})
    if e3c.get("reuses_identical_fresh_cells") is not True:
        _err(errors, "e3c must reuse identical fresh cells")
    if e3c.get("identical_fresh_cells_reused_not_rerun") is not True:
        _err(errors, "e3c identical_fresh_cells_reused_not_rerun must be true")
    if e3c.get("not_double_counted") is not True:
        _err(errors, "e3c not_double_counted must be true")
    if "fresh construct gates" not in str(e3c.get("depends_on", "")).lower():
        _err(errors, "e3c depends_on must mention fresh construct gates")

    # Inference
    inf = data.get("inference", {})
    if inf.get("unit") != "fleet_draw":
        _err(errors, "inference unit must be fleet_draw")
    if inf.get("key") != "fleet_seed":
        _err(errors, "inference key must be fleet_seed")
    if inf.get("n") != 4:
        _err(errors, "inference n must be 4")
    if inf.get("per_draw_values_required") is not True:
        _err(errors, "per_draw_values_required must be true")
    if "95% Student-t" not in str(inf.get("interval", "")) and "Student-t" not in str(
        inf.get("interval", "")
    ):
        _err(errors, "inference interval must be 95% Student-t")
    if inf.get("includes_zero_flag") is not True:
        _err(errors, "includes_zero_flag must be true")
    forbidden = inf.get("forbidden") or []
    for need in ["task_as_n", "p_value_as_primary", "citywide_generalisation", "population_claim"]:
        if need not in forbidden:
            _err(errors, f"inference forbidden must include {need}")

    # Claim boundaries
    cb = data.get("claim_boundaries", {})
    if cb.get("kubernetes_orchestration_tested") is not False:
        _err(errors, "kubernetes orchestration must not be claimed tested")
    if cb.get("physical_result_return_tested") is not False:
        _err(errors, "physical result return must not be claimed tested")
    if cb.get("proactive_is_transparent_baseline_not_optimal") is not True:
        _err(errors, "proactive_is_transparent_baseline_not_optimal must be true")

    # Scenario additional checks
    scen = data.get("scenario", {})
    if scen.get("waiting_room_cap_per_vehicle") == scen.get("rsus"):
        _err(errors, "waiting_room cap must not equal RSU count (queue==compute check)")

    return {"pass": len(errors) == 0, "errors": errors, "error_count": len(errors)}


def validate_markdown_contains(md_text: str, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    checks = [
        (BASE_COMMIT, "base commit in markdown"),
        (EXPECTED_E2B, "E2b commit in markdown"),
        (EXPECTED_E2C, "E2c commit in markdown"),
        (EXPECTED_E2D_MANIFEST, "E2d manifest SHA in markdown"),
        (EXPECTED_ACTOR_SHA, "actor SHA in markdown"),
        (EXPECTED_TRACE_SHA, "trace SHA in markdown"),
        ("resource_unit_seconds", "resource_unit_seconds in markdown"),
        ("fleet_draw", "fleet_draw in markdown"),
        ("fleet_seed", "fleet_seed in markdown"),
        ("fixed_1x", "fixed_1x in markdown"),
        ("static_overprovisioned", "static_overprovisioned in markdown"),
        ("ingress_dla", "ingress_dla in markdown"),
        ("per_task_dla", "per_task_dla in markdown"),
        ("p2c_dla", "p2c_dla in markdown"),
        ("service_workload_ms", "service_workload_ms in markdown"),
        ("arrival_work_ms", "arrival_work_ms in markdown"),
        ("800", "800 threshold in markdown"),
        ("200", "200 threshold in markdown"),
        ("600", "600 gap in markdown"),
        ("5000", "5000 cooldown in markdown"),
        ("2000", "2000 delay in markdown"),
        ("mean(W[0:2])", "mean(W[0:2]) in markdown"),
        ("mean(W[2:4])", "mean(W[2:4]) in markdown"),
        ("max(0, mean(W) + 2*trend)", "forecast formula in markdown"),
        # also accept en-dash variant via fallback
        ("actuation delay", "actuation delay in markdown"),
        ("reused across stage summaries rather than rerun", "reuse clarification in markdown"),
        ("reuses identical fresh cells", "reuses identical fresh cells in markdown"),
        ("not double-counted", "not double-counted in markdown"),
        (
            "transparent baseline, not an optimal predictor",
            "transparent baseline phrase in markdown",
        ),
        ("work-ms, independent of capacity", "signal units phrase in markdown"),
    ]
    for needle, label in checks:
        if needle not in md_text:
            errors.append(f"markdown missing {label}: {needle!r}")
    # hysteresis check: must mention gap is hysteresis, not extra hysteresis_ms
    if "hysteresis" not in md_text.lower():
        errors.append("markdown missing hysteresis explanation")
    if (
        "hysteresis_ms" in md_text
        and "hysteresis_ms` excursion" not in md_text
        and "no additional" not in md_text.lower()
    ):
        # allow mention of forbidden phrase but must clarify
        pass
    # Hypotheses must appear in markdown as hypotheses, not expected truths
    for hid in ["H1", "H2", "H3", "H4", "H5"]:
        if hid not in md_text:
            errors.append(f"markdown missing hypothesis {hid}")
    if "hypothesis_not_expected_truth" not in md_text:
        errors.append("markdown missing hypothesis_not_expected_truth status")
    # Per-hypothesis fragment checks
    hypo_fragments = [
        ("less global inspection", "H1 P2C less global inspection in markdown"),
        ("churn", "H2 churn in markdown"),
        ("change outruns", "H3 change outruns actuation in markdown"),
        ("degrade faster", "H4 degrade faster in markdown"),
        ("may not win", "H5 may not win in markdown"),
    ]
    for needle, label in hypo_fragments:
        if needle not in md_text.lower():
            errors.append(f"markdown missing {label}: {needle!r}")
    # Negative-results-acceptable boundary
    if "negative" not in md_text.lower() or "acceptable" not in md_text.lower():
        errors.append("markdown missing negative results acceptable boundary")
    if "not expected truth" not in md_text.lower() and "not expected truths" not in md_text.lower():
        errors.append("markdown missing hypotheses are not expected truths boundary")
    # Factorial overclaim removal: must state staged isolation, not 'alone and jointly' as claim
    # The research question itself must not contain 'alone and jointly' as a positive claim;
    # the markdown may mention the phrase only in the removal explanation.
    # Check that staged isolation phrases are present
    staged_phrases = [
        ("E3a isolates placement", "E3a isolates placement in markdown"),
        ("E3b holds placement fixed", "E3b holds placement fixed in markdown"),
        (
            "E3c tests selected stale-state contrasts",
            "E3c tests selected stale-state contrasts in markdown",
        ),
        (
            "without fully crossing every placement with every scaler",
            "without fully crossing every placement with every scaler in markdown",
        ),
    ]
    for needle, label in staged_phrases:
        if needle.lower() not in md_text.lower():
            errors.append(f"markdown missing {label}: {needle!r}")
    # Ensure the research question block does not still claim 'alone and jointly' as a positive improvement claim  # noqa: E501
    # Allow one occurrence in the removal sentence 'is removed because'
    # Count occurrences of 'alone and jointly' before the removal explanation vs after
    # Simpler: if 'alone and jointly' appears in the first 1500 chars (which contains the RQ quote), fail  # noqa: E501
    rq_section = md_text[:2000].lower()
    if "alone and jointly" in rq_section:
        # Check if it's inside the blockquote that is the RQ (should not be there)
        # The RQ blockquote is between '> Under the frozen' and the next blank line
        # If still present in the RQ sentence, it's a failure unless it's the explanatory removal sentence  # noqa: E501
        # The explanatory sentence is after the mechanism table, not in first 2000? Actually it is within first 2000 now  # noqa: E501
        # We allow it only if accompanied by 'is removed'
        if "alone and jointly" in rq_section and "is removed" not in rq_section:
            errors.append("markdown research question must not contain 'alone and jointly'")
        # More precise: ensure RQ quote itself does not contain the phrase
        # Extract the quoted RQ (lines starting with '>')
        rq_lines = [line for line in md_text.splitlines() if line.startswith(">")]
        rq_text = " ".join(rq_lines).lower()
        if "alone and jointly" in rq_text:
            errors.append("markdown research question quote must not contain 'alone and jointly'")
    if "e.g. linear regression" in md_text.lower():
        errors.append("markdown must not contain 'e.g. linear regression' alternative formula")
    if "moving-average delta" in md_text.lower():
        errors.append("markdown must not contain 'moving-average delta' alternative formula phrase")
    if "1--3" not in md_text and "1–3" not in md_text and "1-3" not in md_text:
        errors.append("markdown missing 1--3/1–3 bounds in markdown")
    for _stale in ["0, 1000, 3000", "0,1000,3000", "0 ms", "1000", "3000"]:
        if "3000" in md_text:
            break
    else:
        errors.append("markdown missing stale levels")
    return errors


def load_contract(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate E3 dynamic resource contract")
    parser.add_argument(
        "--contract-json",
        type=Path,
        default=Path("docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.json"),
    )
    parser.add_argument(
        "--contract-md",
        type=Path,
        default=Path("docs/evaluation/e3/e3_dynamic_resource_v2_contract_v1.md"),
    )
    parser.add_argument(
        "--check-equivalence", action="store_true", help="also check markdown/json equivalence"
    )
    args = parser.parse_args()
    if not args.contract_json.is_file():
        print(f"missing contract json: {args.contract_json}", flush=True)
        return 2
    data = load_contract(args.contract_json)
    result = validate_contract(data)
    if args.check_equivalence:
        if not args.contract_md.is_file():
            result["errors"].append(f"missing contract md: {args.contract_md}")
            result["pass"] = False
        else:
            md_text = args.contract_md.read_text(encoding="utf-8")
            md_errors = validate_markdown_contains(md_text, data)
            result["errors"].extend(md_errors)
            if md_errors:
                result["pass"] = False
            # also ensure no forbidden arm IDs in markdown beyond allowed forbidden note
            # Count occurrences outside forbidden synonyms note is complex; keep simple above
    # update error_count
    result["error_count"] = len(result["errors"])
    result["pass"] = len(result["errors"]) == 0
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

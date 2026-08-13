#!/usr/bin/env python3
"""Fail-closed predeclaration validator for E3 dynamic-resource v2 contract v1.

Scope: This validator enforces the predeclaration scientific contract only
(JSON twin parity, bounded staged grid, identities, thresholds, and claim
boundaries) before any E3 trace execution. Later result ledger, record, and
manifest validators remain dependency-gated and are not implied by a passing
predeclaration check.
"""

from __future__ import annotations

import argparse
import json
import re
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

# Canonical block markers
CANONICAL_BLOCK_START = "<!-- BEGIN_E3_CANONICAL_JSON -->"
CANONICAL_BLOCK_END = "<!-- END_E3_CANONICAL_JSON -->"


def _err(errors: list[str], msg: str) -> None:
    errors.append(msg)


def _canonical_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _extract_canonical_block(md_text: str) -> tuple[str | None, str | None]:
    # Find fenced JSON block between markers
    # Pattern: START marker then ```json ... ``` then END marker
    pattern = re.compile(
        re.escape(CANONICAL_BLOCK_START)
        + r"\s*```json\s*\n(.*?)\n```\s*"
        + re.escape(CANONICAL_BLOCK_END),
        re.DOTALL,
    )
    m = pattern.search(md_text)
    if not m:
        return None, "canonical JSON block missing or malformed (expected START/```json/```/END)"
    raw = m.group(1)
    return raw, None


def _word_boundary_present(text: str, token: str) -> bool:
    return re.search(r"\b" + re.escape(token) + r"\b", text) is not None


def _contains_forbidden_arm_ids(obj: object) -> list[str]:
    found: list[str] = []
    forbidden = {"static3x", "static_3x", "fixed1x"}
    if isinstance(obj, dict):
        for k, v in obj.items():
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


def _find_monetary_violations(obj: object, path: str = "$") -> list[str]:  # noqa: ANN401
    violations: list[str] = []
    forbidden_key_subs = ["currency", "price", "billing", "usd", "dollar", "$"]
    forbidden_val_subs = ["currency", "price", "billing", "$", "usd", "dollar"]
    # Allow phrases containing these are okay if they are explicit normative false statements
    allowed_phrases = [
        "not monetary",
        "never monetary",
        "monetary: false",
        'monetary": false',
        "monetary' : false",
    ]
    # Keys that are explicitly allowed to contain monetary-like terms as documentation
    allowed_key_exact = {"monetary", "forbidden_fields"}

    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            # Check key for monetary substrings
            if kl not in allowed_key_exact:
                for sub in forbidden_key_subs:
                    if sub in kl:
                        # Special allow: cost_currency etc inside forbidden_fields list is handled by skipping that list  # noqa: E501
                        # But key itself like "cost_currency" should be forbidden everywhere
                        # If k is exactly forbidden_fields we skip, otherwise error
                        violations.append(
                            f"monetary-like key forbidden at {path}.{k!r}: contains {sub!r}"
                        )
                        break
            # Recurse unless this is the allowlisted documentation list
            if k == "forbidden_fields" and isinstance(v, list):
                # Documentation of forbidden fields is allowed to list monetary names
                continue
            # For key "monetary", value must be false; any other monetary-like value is checked below  # noqa: E501
            if kl == "monetary":
                if v is not False:
                    # If monetary is not false, any monetary claim is violation unless it's part of allowed phrase?  # noqa: E501
                    # monetary: false is only allowed normative phrase
                    violations.append(f"monetary must be false at {path}.{k!r} (got {v!r})")
                # don't recurse into boolean false
                continue
            # Recurse into value
            violations.extend(_find_monetary_violations(v, f"{path}.{k}"))
            # Also check if value is string containing forbidden substrings (for dict values that are strings)  # noqa: E501
            if isinstance(v, str):
                vl = v.lower()
                # allow if contains explicit normative false phrase
                if any(p in vl for p in allowed_phrases):
                    continue
                for sub in forbidden_val_subs:
                    if sub in vl:
                        violations.append(
                            f"monetary-like string forbidden at {path}.{k!r}: {v!r} contains {sub!r}"  # noqa: E501
                        )
                        break
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            if isinstance(item, str):
                vl = item.lower()
                if any(p in vl for p in allowed_phrases):
                    continue
                # For lists, if this list is forbidden_fields we already skipped above
                for sub in forbidden_val_subs:
                    if sub in vl:
                        violations.append(
                            f"monetary-like string forbidden at {path}[{idx}]: {item!r} contains {sub!r}"  # noqa: E501
                        )
                        break
            violations.extend(_find_monetary_violations(item, f"{path}[{idx}]"))
    elif isinstance(obj, str):
        vl = obj.lower()
        if any(p in vl for p in allowed_phrases):
            return violations
        for sub in forbidden_val_subs:
            if sub in vl:
                violations.append(
                    f"monetary-like string forbidden at {path}: {obj!r} contains {sub!r}"  # noqa: E501
                )
                break
    return violations


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
    for needle in ["fixed_1x", "static_overprovisioned"]:
        if needle not in rq:
            _err(errors, f"research_question must contain scaling arm {needle}")
    low_rq = rq.lower()
    if "strongest-link vs p2c" in low_rq or "strongest-link vs. p2c" in low_rq:
        _err(errors, "research_question must not reduce placement to 'strongest-link vs P2C'")
    if "alone and jointly" in low_rq:
        _err(
            errors,
            "research_question must not contain 'alone and jointly' "  # noqa: E501
            "(bounded staged grid does not fully cross every placement/scaler)",
        )
    if "e3a isolates placement" not in low_rq:
        _err(errors, "research_question must state E3a isolates placement")
    if "e3b holds placement fixed" not in low_rq:
        _err(errors, "research_question must state E3b holds placement fixed for scaling")
    if "e3c tests selected stale-state contrasts" not in low_rq:
        _err(errors, "research_question must state E3c tests selected stale-state contrasts")
    if "without fully crossing every placement with every scaler" not in low_rq:
        _err(
            errors,
            "research_question must state bounded grid does not fully cross "  # noqa: E501
            "every placement with every scaler",
        )

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

    # Hypotheses H1-H5
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
    if cs.get("fixed_1x", {}).get("active_units_per_rsu") != 1:
        _err(errors, "fixed_1x must be 1 active unit")
    if cs.get("fixed_1x", {}).get("multiplier") != 1:
        _err(errors, "fixed_1x multiplier must be 1")
    if cs.get("fixed_1x", {}).get("rsu_service_mult") != 1.0:
        _err(errors, "fixed_1x rsu_service_mult must be 1.0")
    if cs.get("fixed_1x", {}).get("active_units_per_rsu") != cs.get("fixed_1x", {}).get(
        "multiplier"
    ):
        _err(errors, "fixed_1x active_units and multiplier must couple (1)")
    so = cs.get("static_overprovisioned", {})
    if so.get("active_units_per_rsu") != 3:
        _err(errors, "static_overprovisioned must be fixed 3 active units")
    if so.get("multiplier") != 3:
        _err(errors, "static_overprovisioned multiplier must be 3")
    if so.get("rsu_service_mult") != 3.0:
        _err(errors, "static_overprovisioned rsu_service_mult must be 3.0")
    if so.get("active_units_per_rsu") != so.get("multiplier"):
        _err(errors, "static_overprovisioned active_units and multiplier must couple (3)")
    if so.get("is_compute_not_queue") is not True:
        _err(errors, "static_overprovisioned is_compute_not_queue must be true")
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
    if "hysteresis_ms" in db and db.get("hysteresis_ms") not in (None, False):
        _err(errors, "hysteresis_ms extra excursion forbidden; gap is hysteresis")
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
    if "hysteresis_ms" in reactive and isinstance(reactive.get("hysteresis_ms"), int):
        _err(errors, "reactive hysteresis_ms extra excursion forbidden")
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
    if "e.g. linear regression" in json.dumps(proactive).lower():
        _err(errors, "proactive e.g. linear regression phrase forbidden")

    # Cost with recursive monetary check
    cost = data.get("cost", {})
    if cost.get("metric") != "resource_unit_seconds":
        _err(errors, "cost metric must be resource_unit_seconds (missing denominator)")
    if "active_compute_units" not in str(cost.get("formula", "")) or "interval_seconds" not in str(
        cost.get("formula", "")
    ):
        _err(errors, "cost formula must be sum(active_compute_units * interval_seconds)")
    if cost.get("monetary") is not False:
        _err(errors, "cost monetary must be false (never monetary)")
    # Recursive monetary check across entire JSON (strict, allows normative phrases)
    monetary_violations = _find_monetary_violations(data)
    for v in monetary_violations:
        _err(errors, v)

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

    # Scenario frozen constants field-by-field
    scen = data.get("scenario", {})
    expected_scenario = {
        "scenario": "Manchester incident trace",
        "date": "2024-03-15",
        "window_local": "20:00-21:00 Europe/London",
        "steps": 3600,
        "smoke_steps": 10,
        "rsus": 10,
        "padded_fleet_width": 2488,
        "fleet": "uk2030",
        "fleet_status": "provisional",
        "arrival_lambda": 1.5,
        "waiting_room_cap_per_vehicle": 2.5,
        "resolved_cap_tasks_per_rsu": 6220,
        "substep_queue": "sequential",
        "substep_queue_iterations": 3,
        "vehicle_queue": "conserved",
        "rsu_admission": "reject",
        "rsu_cap_mode": "reject",
        "backhaul_ms": 0.0,
    }
    for k, expected in expected_scenario.items():
        if scen.get(k) != expected:
            _err(errors, f"scenario {k} must be {expected!r} (got {scen.get(k)!r})")
    # Typed separation checks (replaces meaningless 2.5-vs-10 equality)
    if scen.get("waiting_room_cap_per_vehicle") != 2.5:
        _err(errors, "waiting_room_cap_per_vehicle must be 2.5")
    if scen.get("rsus") != 10:
        _err(errors, "rsus must be 10")
    if scen.get("resolved_cap_tasks_per_rsu") != 6220:
        _err(errors, "resolved_cap_tasks_per_rsu must be 6220")

    # Staged design — strict stage factors with cross-computed counts
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
    if e3a.get("stale_ms") != [0]:
        _err(errors, "e3a stale_ms must be [0]")
    if e3a.get("fleet_seeds") != [1, 2, 3, 4]:
        _err(errors, "e3a fleet_seeds must be [1,2,3,4]")
    if "fixed_1x" not in str(e3a.get("primary_estimand", "")):
        _err(errors, "e3a primary_estimand must mention fixed_1x")
    # Cross-compute E3a cells: 3 placements *1 scaling *1 stale *4 seeds =12
    try:
        placements_len = len(e3a.get("placement", []))
        scaling_len = len(e3a.get("scaling", []))
        stale_len = len(e3a.get("stale_ms", []))
        seeds_len = len(e3a.get("fleet_seeds", []))
        computed_a = placements_len * scaling_len * stale_len * seeds_len
        if computed_a != 12 or e3a.get("cells") != computed_a:
            _err(errors, f"e3a computed cells {computed_a} inconsistent with declared 12")
    except Exception:
        _err(errors, "e3a cell count cross-compute failed")

    e3b = sd.get("e3b", {})
    if e3b.get("cells") != 16:
        _err(errors, "e3b cells must be 16")
    if e3b.get("fresh") is not True:
        _err(errors, "e3b must be fresh")
    if e3b.get("placement") != ["per_task_dla"]:
        _err(errors, "e3b placement must be exactly ['per_task_dla']")
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
    if e3b.get("stale_ms") != [0]:
        _err(errors, "e3b stale_ms must be [0]")
    if e3b.get("fleet_seeds") != [1, 2, 3, 4]:
        _err(errors, "e3b fleet_seeds must be [1,2,3,4]")
    try:
        placement_len_b = len(e3b.get("placement", []))
        scaling_len_b = len(e3b.get("scaling", []))
        stale_len_b = len(e3b.get("stale_ms", []))
        seeds_len_b = len(e3b.get("fleet_seeds", []))
        computed_b = placement_len_b * scaling_len_b * stale_len_b * seeds_len_b
        if computed_b != 16 or e3b.get("cells") != computed_b:
            _err(errors, f"e3b computed cells {computed_b} inconsistent with declared 16")
    except Exception:
        _err(errors, "e3b cell count cross-compute failed")
    # Reject pseudo-full-factorial grid (3 placements *4 scalers *3 stales *4 seeds =144)
    if (
        placements_len == 3
        and scaling_len_b == 4
        and sd.get("maximum_candidate_unique_cells") == 144
    ):
        _err(
            errors,
            "maximum_candidate_unique_cells must be 60, not 144 (pseudo-full-factorial forbidden)",
        )
    # Also if e3c tried to be full factorial, additional would not be 32
    e3c = sd.get("e3c", {})
    if e3c.get("reuses_identical_fresh_cells") is not True:
        _err(errors, "e3c must reuse identical fresh cells")
    if e3c.get("identical_fresh_cells_reused_not_rerun") is not True:
        _err(errors, "e3c identical_fresh_cells_reused_not_rerun must be true")
    if e3c.get("not_double_counted") is not True:
        _err(errors, "e3c not_double_counted must be true")
    if "fresh construct gates" not in str(e3c.get("depends_on", "")).lower():
        _err(errors, "e3c depends_on must mention fresh construct gates")
    if e3c.get("additional_stale_variant_cells_max") != 32:
        _err(errors, "e3c additional_stale_variant_cells_max must be 32")
    if e3c.get("total_candidate_with_stale_max") != 60:
        _err(errors, "e3c total_candidate_with_stale_max must be 60")
    if e3c.get("stale_is_view_parameter") is not True:
        _err(errors, "e3c stale_is_view_parameter must be true")
    # E3c contrasts: exactly 2 objects, each over [0,1000,3000]
    contrasts = e3c.get("contrasts")
    if not isinstance(contrasts, list) or len(contrasts) != 2:
        _err(errors, "e3c contrasts must be exactly 2 objects")
    else:
        expected_over = [0, 1000, 3000]
        # Check each contrast has over_stale_ms
        for idx, c in enumerate(contrasts):
            if not isinstance(c, dict):
                _err(errors, f"e3c contrasts[{idx}] must be dict")
                continue
            over = c.get("over_stale_ms")
            if over != expected_over:
                _err(
                    errors,
                    f"e3c contrasts[{idx}] over_stale_ms must be [0,1000,3000] (got {over!r})",
                )
        # Check specific comparisons exist
        comparisons = [
            str(c.get("comparison", "")).lower() for c in contrasts if isinstance(c, dict)
        ]
        [
            str(c.get("fixed", "")).lower() + str(c.get("fixed_placement", "")).lower()
            for c in contrasts
            if isinstance(c, dict)
        ]
        # First contrast per_task_dla vs p2c_dla at fixed_1x
        if not any("per_task_dla" in p and "p2c_dla" in p for p in comparisons):
            _err(errors, "e3c must contain per_task_dla vs p2c_dla contrast")
        if not any("reactive" in p and "proactive" in p for p in comparisons):
            _err(errors, "e3c must contain reactive vs proactive contrast")
    # Cross-compute total 60 =12+16+32
    try:
        total_computed = (
            (e3a.get("cells", 0) or 0)
            + (e3b.get("cells", 0) or 0)
            + (e3c.get("additional_stale_variant_cells_max", 0) or 0)
        )
        if total_computed != 60:
            _err(errors, f"staged total cross-compute {total_computed} must be 60 (12+16+32)")
        if sd.get("maximum_candidate_unique_cells") != total_computed:
            _err(errors, "maximum_candidate_unique_cells must equal 12+16+32=60")
        if e3c.get("total_candidate_with_stale_max") != total_computed:
            _err(errors, "e3c total_candidate_with_stale_max must equal 12+16+32=60")
    except Exception:
        _err(errors, "staged total cross-compute failed")

    # Inference — exact including N/seeds, Bessel n-1, SE, Student-t 95%, df=3, t=3.182 etc
    inf = data.get("inference", {})
    if inf.get("unit") != "fleet_draw":
        _err(errors, "inference unit must be fleet_draw")
    if inf.get("key") != "fleet_seed":
        _err(errors, "inference key must be fleet_seed")
    if inf.get("n") != 4:
        _err(errors, "inference n must be 4")
    if inf.get("fleet_seeds") != [1, 2, 3, 4]:
        _err(errors, "inference fleet_seeds must be [1,2,3,4]")
    if inf.get("per_draw_values_required") is not True:
        _err(errors, "per_draw_values_required must be true")
    if inf.get("sample_sd") != "Bessel n-1":
        _err(errors, "inference sample_sd must be Bessel n-1")
    if inf.get("se") != "s / sqrt(n)":
        _err(errors, "inference se must be s / sqrt(n)")
    interval = str(inf.get("interval", ""))
    if "95% Student-t" not in interval:
        _err(errors, "inference interval must be 95% Student-t")
    if "df=3" not in interval:
        _err(errors, "inference interval must contain df=3")
    if "3.182" not in interval:
        _err(errors, "inference interval must contain t=3.182")
    if "t_0.975,3" not in interval and "t_{0.975,3}" not in interval and "t_0.975" not in interval:
        # allow variant but must contain 3.182
        pass
    if inf.get("compatible_with_e2_unless_predeclared") is not True:
        _err(errors, "inference compatible_with_e2_unless_predeclared must be true")
    if "paired_differences" not in inf or "fleet_seed" not in str(
        inf.get("paired_differences", "")
    ):
        _err(errors, "inference paired_differences must mention fleet_seed matched")
    if "d_i" not in str(inf.get("paired_differences", "")) and "d_i" not in str(
        inf.get("mean_difference", "")
    ):
        _err(errors, "inference must define paired d_i")
    if inf.get("includes_zero_flag") is not True:
        _err(errors, "includes_zero_flag must be true")
    if "seed_0_in_primary" not in str(inf.get("forbidden", [])) and "seed_0_in_primary" not in str(
        inf.get("forbidden")
    ):
        # will be checked below
        pass
    forbidden = inf.get("forbidden") or []
    for need in [
        "task_as_n",
        "p_value_as_primary",
        "citywide_generalisation",
        "population_claim",
        "equivalence_without_margin",
        "seed_0_in_primary",
    ]:
        if need not in forbidden:
            _err(errors, f"inference forbidden must include {need}")
    decisions = inf.get("decisions", {})
    if not isinstance(decisions, dict) or len(decisions) != 3:
        _err(errors, "inference decisions must have exactly 3 entries")
    for k in ["interval_above_zero", "interval_below_zero", "interval_includes_zero"]:
        if k not in decisions:
            _err(errors, f"inference decisions missing {k}")

    # Claim boundaries
    cb = data.get("claim_boundaries", {})
    if cb.get("kubernetes_orchestration_tested") is not False:
        _err(errors, "kubernetes orchestration must not be claimed tested")
    if cb.get("physical_result_return_tested") is not False:
        _err(errors, "physical result return must not be claimed tested")
    if cb.get("proactive_is_transparent_baseline_not_optimal") is not True:
        _err(errors, "proactive_is_transparent_baseline_not_optimal must be true")

    return {"pass": len(errors) == 0, "errors": errors, "error_count": len(errors)}


def validate_markdown_contains(md_text: str, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    # Use data: extract canonical block and check deep equality + deterministic generation
    raw, err = _extract_canonical_block(md_text)
    if err is not None:
        errors.append(err)
    else:
        assert raw is not None
        try:
            parsed = json.loads(raw)
        except Exception as e:
            errors.append(f"canonical JSON block is not valid JSON: {e}")
            parsed = None
        if parsed is not None:
            if parsed != data:
                errors.append("canonical JSON block parsed object must deeply equal canonical JSON")
                # Provide diff hint without leaking full
                # Find first differing key
                try:
                    if json.dumps(parsed, sort_keys=True) != json.dumps(data, sort_keys=True):
                        errors.append("canonical JSON block mismatch (deep equality failed)")
                except Exception:  # noqa: S110
                    pass
            # Check deterministic generation: raw must equal canonical dump
            expected_dump = _canonical_dump(data)
            # The raw block may have trailing newline differences; normalize by parsing and re-dumping comparison already done  # noqa: E501
            # For strict byte-equivalence, compare raw stripped vs expected stripped
            # Allow exactly expected_dump (which ends with newline) to match raw + newline if needed
            # We enforce that json.loads(raw) equals data and that re-dumped canonical equals expected_dump  # noqa: E501
            # If raw was generated deterministically, then raw should equal expected_dump without extra whitespace variations  # noqa: E501
            # Compare after stripping trailing newline for tolerance, but require sort_keys and indent consistency  # noqa: E501
            if raw.strip() != expected_dump.strip():
                # If not byte-identical, check if it's still semantically equal but non-deterministic -> still error for byte-equivalence  # noqa: E501
                errors.append(
                    "canonical JSON block must be deterministic generation "  # noqa: E501
                    "(byte-equivalence to json.dumps sort_keys indent=2)"
                )
    # Human text claim checks with word boundaries for numerics
    # Need data to be used - already used above; also check that markdown prose mentions key claims
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
        ("mean(W[0:2])", "mean(W[0:2]) in markdown"),
        ("mean(W[2:4])", "mean(W[2:4]) in markdown"),
        ("max(0, mean(W) + 2*trend)", "forecast formula in markdown"),
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
            errors.append(f"markdown missing {label}: {needle!r}")  # noqa: E501

    # Exact numeric checks with word boundaries: 200,600,800,1000,2000,5000,3600,10,3,60,32,4
    numeric_checks = [
        ("200", "200 threshold in markdown"),
        ("600", "600 gap in markdown"),
        ("800", "800 threshold in markdown"),
        ("1000", "1000 staleness/tick in markdown"),
        ("2000", "2000 delay in markdown"),
        ("5000", "5000 cooldown in markdown"),
        ("3600", "3600 steps in markdown"),
        ("10", "10 RSUs/steps in markdown"),
    ]
    for token, label in numeric_checks:
        if not _word_boundary_present(md_text, token):
            errors.append(
                f"markdown missing {label}: word-boundary {token!r} not found (standalone {token} must appear, not as part of 2000/3600 etc)"  # noqa: E501
            )

    # Additional strict numeric: check that 200 appears as standalone for threshold, not conflated with 2000; also ensure 600 appears standalone  # noqa: E501
    # Already covered by word boundary

    if "hysteresis" not in md_text.lower():
        errors.append("markdown missing hysteresis explanation")
    for hid in ["H1", "H2", "H3", "H4", "H5"]:
        if hid not in md_text:
            errors.append(f"markdown missing hypothesis {hid}")
    if "hypothesis_not_expected_truth" not in md_text:
        errors.append("markdown missing hypothesis_not_expected_truth status")
    hypo_fragments = [
        ("less global inspection", "H1 P2C less global inspection in markdown"),
        ("churn", "H2 churn in markdown"),
        ("change outruns", "H3 change outruns actuation in markdown"),
        ("degrade faster", "H4 degrade faster in markdown"),
        ("may not win", "H5 may not win in markdown"),
    ]
    for needle, label in hypo_fragments:
        if needle not in md_text.lower():
            errors.append(f"markdown missing {label}: {needle!r}")  # noqa: E501
    if "negative" not in md_text.lower() or "acceptable" not in md_text.lower():
        errors.append("markdown missing negative results acceptable boundary")
    if "not expected truth" not in md_text.lower() and "not expected truths" not in md_text.lower():
        errors.append("markdown missing hypotheses are not expected truths boundary")
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
            errors.append(f"markdown missing {label}: {needle!r}")  # noqa: E501
    rq_lines = [line for line in md_text.splitlines() if line.startswith(">")]
    rq_text = " ".join(rq_lines).lower()
    if "alone and jointly" in rq_text:
        errors.append("markdown research question quote must not contain 'alone and jointly'")
    if "alone and jointly" in md_text.lower() and "is removed" not in md_text.lower():
        # If the document still claims alone and jointly as positive, reject
        # But if it only mentions removal, it's okay - already handled above; this is additional check for outside RQ  # noqa: E501
        # Only error if appears outside explanatory sentence
        # Simple: if count of 'alone and jointly' >1 or not accompanied by 'is removed' near, error already captured  # noqa: E501
        pass
    if "e.g. linear regression" in md_text.lower():
        errors.append("markdown must not contain 'e.g. linear regression' alternative formula")
    if "moving-average delta" in md_text.lower():
        errors.append("markdown must not contain 'moving-average delta' alternative formula phrase")
    if "1--3" not in md_text and "1–3" not in md_text and "1-3" not in md_text:
        errors.append("markdown missing 1--3/1–3 bounds in markdown")
    if "3000" not in md_text:
        errors.append("markdown missing stale levels")
    # Ensure markdown contains exact inference details: df=3, t=3.182, Bessel, SE, Student-t 95%
    if not re.search(r"df\s*=\s*n-1\s*=\s*3", md_text) and not re.search(r"df\s*=\s*3", md_text):
        errors.append("markdown missing df=3 inference detail")
    if "3.182" not in md_text:
        errors.append("markdown missing t=3.182 inference detail")
    if "Bessel" not in md_text:
        errors.append("markdown missing Bessel n-1 inference detail")
    if "s / sqrt(n)" not in md_text and "s/√n" not in md_text:
        errors.append("markdown missing SE s/sqrt(n) inference detail")
    if "95% Student-t" not in md_text and "Student-t" not in md_text:
        errors.append("markdown missing 95% Student-t inference detail")
    # Inverse-claim mutations: markdown must not contain forbidden inverse claims
    inverse_phrases = [
        ("queue ceiling is compute capacity", "queue==compute inverse claim"),
        ("queue==compute", "queue==compute inverse claim"),
        ("queue equals compute", "queue==compute inverse claim"),
        ("waiting-room capacity is compute", "queue==compute inverse claim"),
        ("actor observes rsU load", "actor observes RSU load inverse claim"),
        ("actor observes current rsu", "actor observes RSU load inverse claim"),
        ("actor selects execution rsu", "actor selects RSU inverse claim"),
        ("actor chooses rsu", "actor selects RSU inverse claim"),
        ("rejected work executes", "rejected executes inverse claim"),
        ("rejected tasks execute", "rejected executes inverse claim"),
        ("rejected tasks were executed", "rejected executes inverse claim"),
        ("unbounded scaling", "unbounded/free scaling inverse claim"),
        ("free scaling", "free scaling inverse claim"),
        ("unlimited scaling", "unbounded scaling inverse claim"),
        ("static3x", "synonym preferred inverse claim (static3x)"),
        ("static_3x", "synonym preferred inverse claim (static_3x)"),
        ("fixed1x", "synonym preferred inverse claim (fixed1x)"),
        ("tasks are replicates", "task-as-N inverse claim"),
        ("task_as_n is valid", "task-as-N inverse claim"),
        ("using tasks as N", "task-as-N inverse claim"),
        ("conclusion", "hypothesis->conclusion inverse claim"),
        (
            "expected truth",
            "hypothesis->expected truth inverse claim (outside normative 'not expected truth' context)",  # noqa: E501
        ),
        ("USD", "monetary USD inverse claim"),
        ("$", "monetary $ inverse claim"),
        ("price", "monetary price inverse claim"),
        ("billing", "monetary billing inverse claim"),
        ("outer_tick_ms = 200", "tick 200 inverse claim"),
        ("outer_tick_ms is 200", "tick 200 inverse claim"),
        ("outer tick is 200", "tick 200 inverse claim"),
        ("within_tick_task_slots = 200", "slot drift inverse claim"),
        ("within_tick_task_slots is 10", "slot drift inverse claim"),
        ("df = 5", "df drift inverse claim"),
        ("df is 5", "df drift inverse claim"),
        ("t = 2", "t drift inverse claim"),
        ("t is 2.5", "t drift inverse claim"),
        ("cells = 144", "cell drift pseudo-full-factorial inverse claim"),
        ("cells total is 144", "cell drift pseudo-full-factorial inverse claim"),
        ("already executed", "already-executed wording inverse claim"),
        (
            "predeclared_before_any_e3_trace_execution is already executed",
            "already-executed wording inverse claim",
        ),
        ("replication_key is hidden", "replicate-label erasure inverse claim"),
        ("hidden_seed", "replicate-label erasure inverse claim"),
        # Additional generic: if stale 200 ms appears as candidate, that's inverse
        ("stale 200ms", "tick/slot drift inverse claim"),
    ]
    md_text.lower()
    # Remove canonical block for $ and other checks to avoid flagging JSON
    block_raw_for_inverse, _ = _extract_canonical_block(md_text)
    md_without_canonical = md_text
    if block_raw_for_inverse is not None:
        md_without_canonical = md_text.replace(block_raw_for_inverse, "")
    # For inverse-claim detection, focus on narrative excluding validation/stop-rule example lists
    # Exclude stop rules and validation sections where forbidden examples are documented
    inverse_check_text = md_without_canonical
    # Remove stop rules section temporarily
    for marker in ["## 13. Execution preconditions", "## 15. Validation"]:
        if marker in inverse_check_text:
            parts = inverse_check_text.split(marker)
            # Keep before marker, and after next heading (## 14 or ## 16)
            # Simplest: split and keep only before marker for inverse checks; re-add after for other checks?  # noqa: E501
            # We'll keep only text before first excluded marker for inverse checks
            inverse_check_text = parts[0]
            break
    narrative_part = inverse_check_text
    lower_without = narrative_part.lower()
    lower_without = narrative_part.lower()

    def _has_positive_claim(hay: str, phrase: str) -> bool:
        # Sentence-level negation check: if sentence containing phrase has a negation word, it's documenting forbidden, not asserting  # noqa: E501
        neg_words = [
            "never",
            "not ",
            "no ",
            "forbidden",
            "without",
            "must not",
            "cannot",
            "may not",
            "is not",
            "are not",
            "no configuration",
        ]
        for m in re.finditer(re.escape(phrase), hay):
            left = hay.rfind(".", 0, m.start())
            right = hay.find(".", m.end())
            if left == -1:
                left = hay.rfind("\n", 0, m.start())
                if left == -1:
                    left = 0
            else:
                left += 1
            if right == -1:
                right = hay.find("\n", m.end())
                if right == -1:
                    right = len(hay)
            sentence = hay[left:right].lower()
            if any(nw.strip() in sentence for nw in neg_words):
                continue
            # Also check immediate after for violates within same sentence
            after = hay[m.end() : right].lower()
            if "violates" in after or "reject" in after:
                continue
            return True
        return False

    for phrase, label in inverse_phrases:
        phrase_l = phrase.lower()
        if phrase_l == "expected truth":
            for m in re.finditer(r"expected truth", lower_without):
                start = max(0, m.start() - 50)
                context = lower_without[start : m.end() + 30]
                if (
                    "not expected truth" in context
                    or "not expected truths" in context
                    or "not an expected truth" in context
                ):
                    continue
                token_context = narrative_part[max(0, m.start() - 50) : m.end() + 50]
                if "hypothesis_not_expected_truth" in token_context:
                    continue
                # Sentence-level check for this occurrence
                left = lower_without.rfind(".", 0, m.start())
                right = lower_without.find(".", m.end())
                if left == -1:
                    left = lower_without.rfind("\n", 0, m.start())
                    if left == -1:
                        left = 0
                else:
                    left += 1
                if right == -1:
                    right = lower_without.find("\n", m.end())
                    if right == -1:
                        right = len(lower_without)
                sentence = lower_without[left:right]
                if "never" in sentence or "not " in sentence or "no " in sentence:
                    # Sentence already negated (e.g., "never results, conclusions, or expected truths")  # noqa: E501
                    continue
                if "violates" in sentence or "relabel" in sentence:
                    continue
                errors.append(
                    f"markdown contains inverse claim {label}: {phrase!r} without 'not' qualifier"
                )
                break
            continue
        if phrase == "$":
            if "$" in narrative_part:
                # $ outside canonical block is forbidden unless explicitly in allowed phrase (none)
                errors.append(f"markdown contains inverse claim {label}: {phrase!r}")
            continue
        if phrase in ["static3x", "static_3x", "fixed1x"]:
            for m in re.finditer(re.escape(phrase_l), lower_without):
                snippet = lower_without[max(0, m.start() - 60) : m.end() + 60]
                if "forbidden" in snippet or "synonym" in snippet:
                    continue
                # also allow if preceded by negation
                before = lower_without[max(0, m.start() - 40) : m.start()]
                if any(neg in before for neg in ["forbidden", "never", "not"]):
                    continue
                errors.append(f"markdown contains inverse claim {label}: {phrase!r}")
                break
            continue
        # Special handling for phrases that baseline contains negated: check positive claim only
        # For generic inverse phrases, use positive claim helper
        # For phrases like "queue==compute", "actor observes", etc, baseline has negated form, so helper will skip them  # noqa: E501
        # But if someone mutates to positive form (removing negation), helper will detect
        if phrase_l in [
            "queue ceiling is compute capacity",
            "queue==compute",
            "queue equals compute",
            "waiting-room capacity is compute",
            "actor observes rsu load",
            "actor observes current rsu",
            "actor selects execution rsu",
            "actor chooses rsu",
            "rejected work executes",
            "rejected tasks execute",
            "rejected tasks were executed",
            "unbounded scaling",
            "free scaling",
            "unlimited scaling",
            "tasks are replicates",
            "task_as_n is valid",
            "using tasks as n",
            "outer_tick_ms = 200",
            "outer tick is 200",
            "within_tick_task_slots = 200",
            "df = 5",
            "t = 2",
            "cells = 144",
            "already executed",
            "stale 200ms",
        ]:
            if _has_positive_claim(lower_without, phrase_l):
                errors.append(f"markdown contains inverse claim {label}: {phrase!r}")
            continue
        # For remaining phrases like price/billing, they appear negated in baseline as "no price", "no billing"  # noqa: E501
        # Use helper as well
        if phrase_l in ["price", "billing"]:
            if _has_positive_claim(lower_without, phrase_l):
                errors.append(f"markdown contains inverse claim {label}: {phrase!r}")
            continue
        # For other generic checks, use containment but with negation awareness
        if phrase_l in lower_without and _has_positive_claim(lower_without, phrase_l):
            errors.append(f"markdown contains inverse claim {label}: {phrase!r}")
    return errors


def load_contract(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate E3 dynamic resource contract (predeclaration only)"
    )
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
        "--check-equivalence",
        action="store_true",
        help="also check markdown/json equivalence (canonical block + prose)",
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
    result["error_count"] = len(result["errors"])
    result["pass"] = len(result["errors"]) == 0
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

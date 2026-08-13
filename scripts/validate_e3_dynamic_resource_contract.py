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
    "outer_tick",
    "task_slot",
    "sequential_task_ordinal",
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


def _find_monetary_violations(obj: object, path: str = "$") -> list[str]:
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
    allowed_key_exact = {
        "monetary",
        "forbidden_fields",
        "latency_not_retroactively_repriced",
        "later_scale_actions_do_not_retroactively_reprice_recorded_task",
        "no_monetary_or_automatically_authoritative_objective_claim",
        "forbidden_behaviors",
        "resource_unit_seconds_denominator_stays_required_for_diagnostic_deadline_per_resource_cost",
    }

    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            # Check key for monetary substrings
            if kl not in allowed_key_exact:
                for sub in forbidden_key_subs:
                    if sub in kl:
                        # Special allow: cost_currency etc inside
                        # forbidden_fields list is handled by skipping
                        # that list
                        # But key itself like "cost_currency" should be
                        # forbidden everywhere
                        # If k is exactly forbidden_fields we skip,
                        # otherwise error
                        violations.append(
                            f"monetary-like key forbidden at {path}.{k!r}: contains {sub!r}"
                        )
                        break
            # Recurse unless this is the allowlisted documentation list
            if k == "forbidden_fields" and isinstance(v, list):
                # Documentation of forbidden fields is allowed to list monetary names
                continue
            # For key "monetary", value must be false; any other
            # monetary-like value is checked below
            if kl == "monetary":
                if v is not False:
                    # If monetary is not false, any monetary claim is
                    # violation unless it's part of allowed phrase?
                    # monetary: false is only allowed normative phrase
                    violations.append(f"monetary must be false at {path}.{k!r} (got {v!r})")
                # don't recurse into boolean false
                continue
            # Recurse into value
            violations.extend(_find_monetary_violations(v, f"{path}.{k}"))
            # Also check if value is string containing forbidden substrings
            # (for dict values that are strings)
            if isinstance(v, str):
                vl = v.lower()
                # allow if contains explicit normative false phrase
                if any(p in vl for p in allowed_phrases):
                    continue
                for sub in forbidden_val_subs:
                    if sub in vl:
                        violations.append(
                            f"monetary-like string forbidden at "
                            f"{path}.{k!r}: {v!r} contains {sub!r}"
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
                            f"monetary-like string forbidden at "
                            f"{path}[{idx}]: {item!r} contains {sub!r}"
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
                    f"monetary-like string forbidden at {path}: {obj!r} contains {sub!r}"
                )
                break
    return violations


def validate_contract(data: object) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {
            "pass": False,
            "errors": ["contract must be dict (non-dict input forbidden)"],
            "error_count": 1,
        }

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

    # Contract authority — JSON normative, Markdown generated view
    if data.get("contract_authority") != "json_is_normative_markdown_is_generated_view":
        _err(errors, "contract_authority must be json_is_normative_markdown_is_generated_view")
    if data.get("markdown_is_generated_view") is not True:
        _err(errors, "markdown_is_generated_view must be true")
    if "JSON is the single normative" not in str(data.get("authority_note", "")):
        _err(errors, "authority_note must contain 'JSON is the single normative'")
    if "Markdown is a deterministic generated view via render_markdown" not in str(
        data.get("authority_note", "")
    ):
        _err(
            errors,
            "authority_note must state Markdown is "
            "deterministic generated view via render_markdown",
        )
    if "byte mismatch is authoritative" not in str(data.get("authority_note", "")):
        _err(errors, "authority_note must state byte mismatch is authoritative")

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
            "research_question must not contain 'alone and jointly' "
            "(bounded staged grid does not fully cross every "
            "placement/scaler)",
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
            "research_question must state bounded grid does not fully cross "
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
    # Stale-state initialization exact semantics (control-clock offset)
    if tm.get("control_clock_offset_ms") != 3000:
        _err(
            errors,
            "time_model control_clock_offset_ms must be "
            "3000 (declared simulator initial condition)",
        )
    if tm.get("control_clock_applies_when") != "when_stale_robustness_evaluated_all_arms":
        _err(
            errors,
            "time_model control_clock_applies_when must "
            "be when_stale_robustness_evaluated_all_arms",
        )
    if tm.get("prepopulate_control_times_ms") != [0, 1000, 2000]:
        _err(
            errors,
            "time_model prepopulate_control_times_ms must be [0,1000,2000] empty initial state",
        )
    if tm.get("prepopulate_value") != "empty_initial_infrastructure_state":
        _err(errors, "time_model prepopulate_value must be empty_initial_infrastructure_state")
    if tm.get("trace_tick_0_maps_to_control_time_ms") != 3000:
        _err(
            errors,
            "time_model trace_tick_0_maps_to_control_time_ms "
            "must be 3000 (outer_tick 0 -> control 3000)",
        )
    if tm.get("is_declared_simulator_initial_condition_not_observed_traffic") is not True:
        _err(
            errors,
            "time_model is_declared_simulator_initial_condition_not_observed_traffic "
            "must be true (not real Manchester traffic claim)",
        )
    if tm.get("permits_exact_views_without_clamping") is not True:
        _err(errors, "time_model permits_exact_views_without_clamping must be true (no clamping)")
    if tm.get("proactive_pretrace_does_not_satisfy_warmup") is not True:
        _err(
            errors,
            "time_model proactive_pretrace_does_not_satisfy_warmup "
            "must be true (pretrace zeros not warmup)",
        )
    if tm.get("scaling_delay_uses_control_clock_differences") is not True:
        _err(
            errors,
            "time_model scaling_delay_uses_control_clock_differences "
            "must be true (no extra actuation delay)",
        )

    # Admission gate
    ag = data.get("admission_gate", {})
    if "effective_busy_ms" not in str(ag.get("formula", "")) or "TASK_DEADLINE_MS" not in str(
        ag.get("formula", "")
    ):
        _err(errors, "admission_gate formula must be effective_busy_ms < TASK_DEADLINE_MS")
    if ag.get("never_selects_target") is not True:
        _err(errors, "admission_gate must never select target")
    if ag.get("stale_view_applies_to_deadline_workload") is not True:
        _err(
            errors,
            "admission_gate stale_view_applies_to_deadline_workload "
            "must be true (deadline gate uses stale workload view)",
        )
    if ag.get("queue_safety_uses_current_not_stale") is not True:
        _err(
            errors,
            "admission_gate queue_safety_uses_current_not_stale "
            "must be true (queue cap uses true current occupancy)",
        )
    if ag.get("radio_viability_is_current") is not True:
        _err(
            errors,
            "admission_gate radio_viability_is_current must "
            "be true (radio remains current/frozen channel)",
        )
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
    # P2C exact pair mapper: sorted feasible IDs, SplitMix64 over outer_tick etc.
    pair_mapper = p2c.get("pair_mapper")
    if not isinstance(pair_mapper, dict):
        _err(errors, "p2c pair_mapper missing or not dict (exact SplitMix64 mapper required)")
    else:
        if pair_mapper.get("candidate_order") != "sorted_ascending_unique_feasible_RSU_IDs":
            _err(
                errors,
                "pair_mapper candidate_order must be sorted_ascending_unique_feasible_RSU_IDs",
            )
        if pair_mapper.get("hash") != "SplitMix64":
            _err(errors, "pair_mapper hash must be SplitMix64")
        expected_hash_fields = [
            "evaluator_seed",
            "fleet_seed",
            "outer_tick",
            "task_slot",
            "sequential_task_ordinal",
        ]
        if pair_mapper.get("hash_input_fields_exact") != expected_hash_fields:
            _err(errors, f"pair_mapper hash_input_fields_exact must be {expected_hash_fields}")
        if pair_mapper.get("first_index_formula") != "h % n":
            _err(errors, "pair_mapper first_index_formula must be h % n")
        if pair_mapper.get("second_index_formula") != "splitmix64(h) % (n-1) adjusted around first":
            _err(
                errors,
                "pair_mapper second_index_formula must be "
                "splitmix64(h) % (n-1) adjusted around first",
            )
        if pair_mapper.get("final_pair_sorted") is not True:
            _err(errors, "pair_mapper final_pair_sorted must be true")
        if pair_mapper.get("distinct_without_replacement") is not True:
            _err(errors, "pair_mapper distinct_without_replacement must be true")
        if pair_mapper.get("mapper_type") != "deterministic_pseudo_random_modulo_mapper":
            _err(
                errors, "pair_mapper mapper_type must be deterministic_pseudo_random_modulo_mapper"
            )
        if pair_mapper.get("no_hidden_global_RNG") is not True:
            _err(errors, "pair_mapper no_hidden_global_RNG must be true")
        if pair_mapper.get("uniformity_not_claimed") is not True:
            _err(
                errors, "pair_mapper uniformity_not_claimed must be true (modulo bias not uniform)"
            )
    bias_note = p2c.get("modulo_bias_note")
    if (
        not isinstance(bias_note, str)
        or "negligible bias" not in bias_note.lower()
        or "not mathematically exact-uniform" not in bias_note
    ):
        _err(
            errors,
            "p2c modulo_bias_note must state modulo reduction has "
            "negligible bias not mathematically exact-uniform",
        )
    uniformity_forbidden = p2c.get("uniformity_claim_forbidden")
    if not isinstance(uniformity_forbidden, list) or not all(
        x in uniformity_forbidden for x in ["uniform", "unbiased"]
    ):
        _err(errors, "p2c uniformity_claim_forbidden must include uniform and unbiased")
    if (
        p2c.get("h1_concern")
        != "pair_only_inspection_global_state_dependence_not_statistical_uniformity_proof"
    ):
        _err(
            errors,
            "p2c h1_concern must be "
            "pair_only_inspection_global_state_dependence_not_statistical_uniformity_proof",
        )

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

    # Staged design — strict stage factors with cross-computed counts, fail-closed type checks
    sd = data.get("staged_design")
    if not isinstance(sd, dict):
        _err(errors, "staged_design missing or not dict")
        return {"pass": len(errors) == 0, "errors": errors, "error_count": len(errors)}
    # Stage-listed vs unique accounting: 60 stage-listed (12+16+32) but 56 unique (12+12+32)
    if sd.get("stage_listed_cells") != 60:
        _err(errors, "stage_listed_cells must be 60 (12+16+32 stage-listed)")
    if sd.get("maximum_candidate_unique_cells") != 56:
        _err(errors, "maximum_candidate_unique_cells must be 56 (12+12+32 unique, not 60)")
    # Reject 60-as-unique claim
    if sd.get("maximum_candidate_unique_cells") == 60:
        _err(
            errors,
            "maximum_candidate_unique_cells must not be 60 (60 is stage-listed, unique is 56)",
        )
    # Equations must be present and exact
    if sd.get("stage_listed_equation") != "12 + 16 + 32 = 60":
        _err(errors, "stage_listed_equation must be '12 + 16 + 32 = 60'")
    if sd.get("unique_equation") != "12 + 12 + 32 = 56":
        _err(errors, "unique_equation must be '12 + 12 + 32 = 56'")
    if sd.get("e3b_overlap_with_e3a") != 4:
        _err(errors, "e3b_overlap_with_e3a must be 4 (per_task_dla/fixed_1x/0 overlap)")
    if sd.get("e3b_unique_additional") != 12:
        _err(errors, "e3b_unique_additional must be 12 (16 -4)")
    if sd.get("e3c_total_contrast_observations") != 48:
        _err(
            errors,
            "e3c_total_contrast_observations must be 48 "
            "(2 contrasts *3 staleness *2 arms *4 draws)",
        )
    if sd.get("e3c_fresh_observations_reused") != 16:
        _err(
            errors, "e3c_fresh_observations_reused must be 16 (fresh observations reused not rerun)"
        )
    if sd.get("e3c_stale_variant_equation") != "48 - 16 = 32":
        _err(errors, "e3c_stale_variant_equation must be '48 - 16 = 32'")
    if sd.get("budget_reduction_required_if_unreasonable") is not True:
        _err(errors, "budget_reduction_required_if_unreasonable must be true")
    if sd.get("identical_fresh_cells_reused_not_rerun") is not True:
        _err(errors, "identical_fresh_cells_reused_not_rerun must be true")
    if sd.get("not_double_counted") is not True:
        _err(errors, "staged_design not_double_counted must be true")
    note_val = sd.get("note")
    if (
        not isinstance(note_val, str)
        or "reused across stage summaries rather than rerun" not in note_val
    ):
        _err(errors, "staged_design note must clarify reused not rerun")
    if "12 + 12 + 32 = 56" not in str(note_val):
        _err(errors, "staged_design note must contain unique equation 12+12+32=56")
    if "12 + 16 + 32 = 60" not in str(note_val):
        _err(errors, "staged_design note must contain stage-listed equation 12+16+32=60")
    e3a = sd.get("e3a")
    if not isinstance(e3a, dict):
        _err(errors, "e3a missing or not dict")
        e3a = {}
    else:
        if e3a.get("cells") != 12:
            _err(errors, "e3a cells must be 12")
        if e3a.get("stage_listed_cells") != 12:
            _err(errors, "e3a stage_listed_cells must be 12")
        if e3a.get("unique_cells") != 12:
            _err(errors, "e3a unique_cells must be 12")
        if e3a.get("fresh") is not True:
            _err(errors, "e3a must be fresh")
        placement_a = e3a.get("placement")
        if not isinstance(placement_a, list):
            _err(errors, "e3a placement must be list (scalar forbidden)")
            placement_a = []
        elif set(placement_a) != {"ingress_dla", "per_task_dla", "p2c_dla"}:
            _err(errors, "e3a placement must be ingress_dla/per_task_dla/p2c_dla")
        scaling_a = e3a.get("scaling")
        if not isinstance(scaling_a, list):
            _err(errors, "e3a scaling must be list (scalar forbidden)")
            scaling_a = []
        elif scaling_a != ["fixed_1x"]:
            _err(errors, "e3a scaling must be ['fixed_1x'] only")
        if e3a.get("scaling_ids_exact") != ["fixed_1x"]:
            _err(errors, "e3a scaling_ids_exact must be ['fixed_1x']")
        stale_a = e3a.get("stale_ms")
        if not isinstance(stale_a, list):
            _err(errors, "e3a stale_ms must be list")
            stale_a = []
        elif stale_a != [0]:
            _err(errors, "e3a stale_ms must be [0]")
        seeds_a = e3a.get("fleet_seeds")
        if not isinstance(seeds_a, list):
            _err(errors, "e3a fleet_seeds must be list")
            seeds_a = []
        elif seeds_a != [1, 2, 3, 4]:
            _err(errors, "e3a fleet_seeds must be [1,2,3,4]")
        primary_est = e3a.get("primary_estimand")
        if not isinstance(primary_est, str) or "fixed_1x" not in primary_est:
            _err(errors, "e3a primary_estimand must mention fixed_1x")
        # Cross-compute E3a cells only after type narrowing
        if (
            isinstance(placement_a, list)
            and isinstance(scaling_a, list)
            and isinstance(stale_a, list)
            and isinstance(seeds_a, list)
        ):
            computed_a = len(placement_a) * len(scaling_a) * len(stale_a) * len(seeds_a)
            if computed_a != 12 or e3a.get("cells") != computed_a:
                _err(errors, f"e3a computed cells {computed_a} inconsistent with declared 12")
        else:
            _err(errors, "e3a cell count cross-compute failed due to non-list factors")

    e3b = sd.get("e3b")
    placement_b: list[Any] = []
    scaling_b: list[Any] = []
    stale_b: list[Any] = []
    seeds_b: list[Any] = []
    if not isinstance(e3b, dict):
        _err(errors, "e3b missing or not dict")
        e3b = {}
    else:
        if e3b.get("cells") != 16:
            _err(errors, "e3b cells must be 16")
        if e3b.get("stage_listed_cells") != 16:
            _err(errors, "e3b stage_listed_cells must be 16")
        if e3b.get("overlap_with_e3a") != 4:
            _err(errors, "e3b overlap_with_e3a must be 4")
        if e3b.get("unique_additional") != 12:
            _err(errors, "e3b unique_additional must be 12")
        if e3b.get("unique_cells") != 12:
            _err(errors, "e3b unique_cells must be 12")
        if e3b.get("fresh") is not True:
            _err(errors, "e3b must be fresh")
        placement_raw = e3b.get("placement")
        if not isinstance(placement_raw, list):
            _err(errors, "e3b placement must be list (scalar forbidden)")
            placement_b = []
        elif placement_raw != ["per_task_dla"]:
            _err(errors, "e3b placement must be exactly ['per_task_dla']")
            placement_b = placement_raw
        else:
            placement_b = placement_raw
        scaling_raw = e3b.get("scaling")
        if not isinstance(scaling_raw, list):
            _err(errors, "e3b scaling must be list (scalar forbidden)")
            scaling_b = []
        elif set(scaling_raw) != {
            "fixed_1x",
            "static_overprovisioned",
            "reactive",
            "proactive",
        }:
            _err(
                errors,
                "e3b scaling must be fixed_1x/static_overprovisioned/reactive/proactive",
            )
            scaling_b = scaling_raw
        else:
            scaling_b = scaling_raw
        scaling_ids = e3b.get("scaling_ids_exact")
        if not isinstance(scaling_ids, list) or set(scaling_ids) != {
            "fixed_1x",
            "static_overprovisioned",
            "reactive",
            "proactive",
        }:
            _err(
                errors,
                "e3b scaling_ids_exact must be fixed_1x/static_overprovisioned/reactive/proactive",
            )
        stale_raw = e3b.get("stale_ms")
        if not isinstance(stale_raw, list):
            _err(errors, "e3b stale_ms must be list")
            stale_b = []
        elif stale_raw != [0]:
            _err(errors, "e3b stale_ms must be [0]")
            stale_b = stale_raw
        else:
            stale_b = stale_raw
        seeds_raw = e3b.get("fleet_seeds")
        if not isinstance(seeds_raw, list):
            _err(errors, "e3b fleet_seeds must be list")
            seeds_b = []
        elif seeds_raw != [1, 2, 3, 4]:
            _err(errors, "e3b fleet_seeds must be [1,2,3,4]")
            seeds_b = seeds_raw
        else:
            seeds_b = seeds_raw
        if (
            isinstance(placement_b, list)
            and isinstance(scaling_b, list)
            and isinstance(stale_b, list)
            and isinstance(seeds_b, list)
        ):
            computed_b = len(placement_b) * len(scaling_b) * len(stale_b) * len(seeds_b)
            if computed_b != 16 or e3b.get("cells") != computed_b:
                _err(errors, f"e3b computed cells {computed_b} inconsistent with declared 16")
            if computed_b != 16 or e3b.get("stage_listed_cells") != computed_b:
                _err(errors, f"e3b stage_listed_cells inconsistent with computed {computed_b}")
        else:
            _err(errors, "e3b cell count cross-compute failed due to non-list factors")
        # Overlap reuse must be declared
        overlap_note = e3b.get("overlap_note")
        if not isinstance(overlap_note, str) or "reused not rerun" not in overlap_note.lower():
            _err(errors, "e3b overlap_note must clarify byte-identical reused not rerun")

    # Also check pseudo-full-factorial via combined
    placements_len_a = (
        len(e3a.get("placement", [])) if isinstance(e3a.get("placement"), list) else 0
    )
    scaling_len_b = len(scaling_b) if isinstance(scaling_b, list) else 0
    if (
        placements_len_a == 3
        and scaling_len_b == 4
        and sd.get("maximum_candidate_unique_cells") == 144
    ):
        _err(
            errors,
            "maximum_candidate_unique_cells must be 56, not 144 (pseudo-full-factorial forbidden)",
        )
    e3c = sd.get("e3c")
    if not isinstance(e3c, dict):
        _err(errors, "e3c missing or not dict")
        e3c = {}
    else:
        if e3c.get("reuses_identical_fresh_cells") is not True:
            _err(errors, "e3c must reuse identical fresh cells")
        if e3c.get("identical_fresh_cells_reused_not_rerun") is not True:
            _err(errors, "e3c identical_fresh_cells_reused_not_rerun must be true")
        if e3c.get("not_double_counted") is not True:
            _err(errors, "e3c not_double_counted must be true")
        depends_val = e3c.get("depends_on")
        if not isinstance(depends_val, str) or "fresh construct gates" not in depends_val.lower():
            _err(errors, "e3c depends_on must mention fresh construct gates")
        if e3c.get("additional_stale_variant_cells_max") != 32:
            _err(errors, "e3c additional_stale_variant_cells_max must be 32")
        if e3c.get("total_contrast_observations") != 48:
            _err(errors, "e3c total_contrast_observations must be 48 (2*3*2*4)")
        if e3c.get("fresh_observations_reused") != 16:
            _err(errors, "e3c fresh_observations_reused must be 16")
        if e3c.get("stale_variant_equation") != "48 - 16 = 32":
            _err(errors, "e3c stale_variant_equation must be '48 - 16 = 32'")
        expected_e3c_eq = (
            "2 contrasts * 2 arms * 3 staleness * 4 draws = 48 observations; "
            "48 - 16 = 32 stale variants"
        )
        if e3c.get("equation") != expected_e3c_eq:
            _err(
                errors,
                f"e3c equation must be {expected_e3c_eq!r} (got {e3c.get('equation')!r})",
            )
        if e3c.get("stale_is_view_parameter") is not True:
            _err(errors, "e3c stale_is_view_parameter must be true")
        # Reject old total_candidate_with_stale_max ==60
        if e3c.get("total_candidate_with_stale_max") == 60:
            _err(
                errors,
                "e3c total_candidate_with_stale_max must not be 60 (unique is 56, stage-listed 60)",
            )
        # Also reject if stagedesign claims total_candidate_with_stale_max 60 at top? Already
        # handled
        # via maximum_candidate
        contrasts = e3c.get("contrasts")
        if not isinstance(contrasts, list) or len(contrasts) != 2:
            _err(errors, "e3c contrasts must be exactly 2 objects (list)")
        else:
            expected_over = [0, 1000, 3000]
            for idx, c in enumerate(contrasts):
                if not isinstance(c, dict):
                    _err(errors, f"e3c contrasts[{idx}] must be dict")
                    continue
                over = c.get("over_stale_ms")
                if not isinstance(over, list):
                    _err(errors, f"e3c contrasts[{idx}] over_stale_ms must be list")
                elif over != expected_over:
                    _err(
                        errors,
                        f"e3c contrasts[{idx}] over_stale_ms must be [0,1000,3000] (got {over!r})",
                    )
            comparisons = [
                str(c.get("comparison", "")).lower() for c in contrasts if isinstance(c, dict)
            ]
            if not any("per_task_dla" in p and "p2c_dla" in p for p in comparisons):
                _err(errors, "e3c must contain per_task_dla vs p2c_dla contrast")
            if not any("reactive" in p and "proactive" in p for p in comparisons):
                _err(errors, "e3c must contain reactive vs proactive contrast")
    # Cross-compute stage-listed vs unique: 12+16+32=60 stage, 12+12+32=56 unique
    cells_a_raw = e3a.get("cells")
    total_cells_a: int = cells_a_raw if isinstance(cells_a_raw, int) else 0
    cells_b_raw = e3b.get("cells")
    total_cells_b: int = cells_b_raw if isinstance(cells_b_raw, int) else 0
    add_raw = e3c.get("additional_stale_variant_cells_max")
    total_add: int = add_raw if isinstance(add_raw, int) else 0
    stage_computed = total_cells_a + total_cells_b + total_add
    if stage_computed != 60:
        _err(errors, f"staged stage-listed cross-compute {stage_computed} must be 60 (12+16+32)")
    if sd.get("stage_listed_cells") != stage_computed:
        _err(errors, "stage_listed_cells must equal 12+16+32=60")
    # Unique is stage minus overlaps: 60 -4 (E3b overlap) -? Actually fresh reused 16 already
    # accounted?
    # Unique =12+12+32
    unique_computed = 12 + 12 + 32  # 56
    if sd.get("maximum_candidate_unique_cells") != unique_computed:
        _err(errors, "maximum_candidate_unique_cells must equal 12+12+32=56")
    # Validate e3c total observations 48 vs stale 32
    total_obs = e3c.get("total_contrast_observations")
    fresh_reused = e3c.get("fresh_observations_reused")
    if isinstance(total_obs, int) and isinstance(fresh_reused, int):
        if total_obs - fresh_reused != 32:
            _err(errors, "e3c 48-16 must be 32 stale variants")
        if total_obs != 48:
            _err(errors, "e3c total_contrast_observations must be 48")

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

    # Compute-service semantics — invariant work, drain, latency (including stale queue safety)
    css = data.get("compute_service_semantics", {})
    if not isinstance(css, dict):
        _err(errors, "compute_service_semantics missing or not dict")
        css = {}
    else:
        if css.get("queue_ceiling_uses_current_occupancy_plus_same_tick_reservations") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "queue_ceiling_uses_current_occupancy_plus_same_tick_reservations "
                "must be true (stale never overfills waiting room)",
            )
        if css.get("queue_safety_is_current_not_stale") is not True:
            _err(errors, "compute_service_semantics queue_safety_is_current_not_stale must be true")
        if css.get("stale_does_not_mutate_true_state") is not True:
            _err(
                errors,
                "compute_service_semantics stale_does_not_mutate_true_state must be true "
                "(staleness does not mutate true environment/capacity/pending/queue)",
            )
        if css.get("enqueue_equation") != "enqueued_work_ms = raw_1x_service_work_ms":
            _err(
                errors,
                "compute_service_semantics enqueue_equation must "
                "be enqueued_work_ms = raw_1x_service_work_ms",
            )
        if css.get("enqueue_must_not_divide_by_capacity") is not True:
            _err(
                errors, "compute_service_semantics enqueue_must_not_divide_by_capacity must be true"
            )
        if (
            str(css.get("enqueue_forbidden_division", ""))
            != "enqueued_work_ms != raw_1x_service_work_ms / active_capacity_units"
        ):
            _err(
                errors,
                "compute_service_semantics enqueue_forbidden_division must be "
                "enqueued_work_ms != raw_1x_service_work_ms / active_capacity_units",
            )
        if css.get("enqueue_adds_raw_1x_work_ms") is not True:
            _err(errors, "compute_service_semantics enqueue_adds_raw_1x_work_ms must be true")
        if css.get("drain_applies_to_all_queued_work_including_pre_scale") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "drain_applies_to_all_queued_work_including_pre_scale must be true",
            )
        if (
            css.get("drain_equation")
            != "drain_work_ms = min(backlog_work_ms, active_capacity_units * 1000)"
        ):
            _err(
                errors,
                "compute_service_semantics drain_equation must be drain_work_ms "
                "= min(backlog_work_ms, active_capacity_units * 1000)",
            )
        if css.get("drain_tick_ms") != 1000:
            _err(errors, "compute_service_semantics drain_tick_ms must be 1000")
        if (
            css.get("backlog_equation")
            != "backlog_work_ms[t+1] = backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms"
        ):
            _err(
                errors,
                "compute_service_semantics backlog_equation must be backlog_work_ms[t+1] "
                "= backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms",
            )
        if css.get("backlog_is_invariant_baseline") is not True:
            _err(errors, "compute_service_semantics backlog_is_invariant_baseline must be true")
        if css.get("backlog_storage_unit") != "work_ms":
            _err(errors, "compute_service_semantics backlog_storage_unit must be work_ms")
        if css.get("resource_time_charged_even_when_idle") is not True:
            _err(
                errors,
                "compute_service_semantics resource_time_charged_even_when_idle must be true",
            )
        if css.get("at_most_one_interval_per_RSU_per_tick") is not True:
            _err(
                errors,
                "compute_service_semantics at_most_one_interval_per_RSU_per_tick must be true",
            )
        if (
            css.get("resource_time_equation")
            != "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1"
        ):
            _err(
                errors,
                "compute_service_semantics resource_time_equation must be "
                "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1",
            )
        if css.get("drain_capacity_is_not_queue_slots") is not True:
            _err(errors, "compute_service_semantics drain_capacity_is_not_queue_slots must be true")
        forbidden_units = css.get("scaling_forbidden_units")
        if not isinstance(forbidden_units, list) or set(forbidden_units) != {
            "queue_slots",
            "capacity_normalized_work_ms",
        }:
            _err(
                errors,
                "compute_service_semantics scaling_forbidden_units "
                "must be [queue_slots, capacity_normalized_work_ms]",
            )
        if css.get("placement_workloads_unit") != "raw_backlog_work_ms":
            _err(
                errors,
                "compute_service_semantics placement_workloads_unit must be raw_backlog_work_ms",
            )
        if css.get("admission_gate_unit") != "raw_backlog_work_ms":
            _err(
                errors, "compute_service_semantics admission_gate_unit must be raw_backlog_work_ms"
            )
        if css.get("reactive_signal_unit") != "raw_backlog_work_ms":
            _err(
                errors, "compute_service_semantics reactive_signal_unit must be raw_backlog_work_ms"
            )
        if css.get("proactive_observation_unit") != "raw_admitted_arrival_work_ms":
            _err(
                errors,
                "compute_service_semantics proactive_observation_unit "
                "must be raw_admitted_arrival_work_ms",
            )
        if css.get("stale_snapshot_unit") != "raw_backlog_work_ms":
            _err(
                errors, "compute_service_semantics stale_snapshot_unit must be raw_backlog_work_ms"
            )
        if css.get("same_tick_reservation_overlay_unit") != "raw_task_work_ms":
            _err(
                errors,
                "compute_service_semantics "
                "same_tick_reservation_overlay_unit must be raw_task_work_ms",
            )
        if css.get("scaling_must_not_change_placement_or_admission_unit") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "scaling_must_not_change_placement_or_admission_unit must be true",
            )
        if css.get("latency_not_retroactively_repriced") is not True:
            _err(
                errors, "compute_service_semantics latency_not_retroactively_repriced must be true"
            )
        if (
            css.get("latency_equation")
            != "(raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units"
        ):
            _err(
                errors,
                "compute_service_semantics latency_equation must be (raw_work_ahead_ms "
                "+ raw_own_service_work_ms) / active_capacity_units",
            )
        if css.get("latency_semantics") != "admission_time_estimate_not_physical_lifecycle":
            _err(
                errors,
                "compute_service_semantics latency_semantics must "
                "be admission_time_estimate_not_physical_lifecycle",
            )
        if css.get("latency_radio_forwarding_unchanged") is not True:
            _err(
                errors, "compute_service_semantics latency_radio_forwarding_unchanged must be true"
            )
        if css.get("latency_physical_lifecycle_fields_remain_null") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "latency_physical_lifecycle_fields_remain_null must be true",
            )
        if css.get("reduces_to_E2d_at_fixed_1x") is not True:
            _err(errors, "compute_service_semantics reduces_to_E2d_at_fixed_1x must be true")
        if "at fixed_1x (u=1): drain = min(backlog_work_ms, 1000)" not in str(
            css.get("reduction_equation", "")
        ):
            _err(
                errors,
                "compute_service_semantics reduction_equation must state "
                "at fixed_1x drain = min(backlog,1000) and latency = raw",
            )
        if css.get("scaling_applied_at_tick_start_before_placement_admission") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "scaling_applied_at_tick_start_before_placement_admission must be true",
            )
        if css.get("scaling_applied_before_latency_estimate_and_drain") is not True:
            _err(
                errors,
                "compute_service_semantics "
                "scaling_applied_before_latency_estimate_and_drain must be true",
            )
        if css.get("active_capacity_for_entire_tick") is not True:
            _err(errors, "compute_service_semantics active_capacity_for_entire_tick must be true")
        init_cap = css.get("initial_capacities", {})
        if not isinstance(init_cap, dict):
            _err(errors, "compute_service_semantics initial_capacities missing or not dict")
        else:
            if init_cap.get("static_overprovisioned_units") != 3:
                _err(
                    errors,
                    "compute_service_semantics initial_capacities "
                    "static_overprovisioned_units must be 3",
                )
            if init_cap.get("static_overprovisioned_from_tick") != 0:
                _err(
                    errors,
                    "compute_service_semantics initial_capacities "
                    "static_overprovisioned_from_tick must be 0",
                )
            if init_cap.get("dynamic_start_units") != 1:
                _err(
                    errors,
                    "compute_service_semantics initial_capacities dynamic_start_units must be 1",
                )
            if init_cap.get("fixed_1x_units") != 1:
                _err(
                    errors, "compute_service_semantics initial_capacities fixed_1x_units must be 1"
                )
            if init_cap.get("dynamic_max_units") != 3:
                _err(
                    errors,
                    "compute_service_semantics initial_capacities dynamic_max_units must be 3",
                )
            if init_cap.get("dynamic_min_units") != 1:
                _err(
                    errors,
                    "compute_service_semantics initial_capacities dynamic_min_units must be 1",
                )

    # Stale-state semantics exact (initialization, admission/safety)
    sss = data.get("stale_state_semantics")
    if not isinstance(sss, dict):
        _err(errors, "stale_state_semantics missing or not dict (stale initialization required)")
        sss = {}
    else:
        applies = sss.get("applies_to")
        if not isinstance(applies, list) or set(applies) != {
            "invariant_raw_backlog_work_ms_view_for_placement",
            "inherited_backlog_only_deadline_gate",
            "reactive_signal",
            "proactive_signal",
        }:
            expected = {
                "invariant_raw_backlog_work_ms_view_for_placement",
                "inherited_backlog_only_deadline_gate",
                "reactive_signal",
                "proactive_signal",
            }
            if not isinstance(applies, list) or set(applies) != expected:
                _err(
                    errors,
                    "stale_state_semantics applies_to must be invariant raw backlog "
                    "view for placement, deadline gate, reactive and proactive signals",
                )
        does_not = sss.get("does_not_mutate")
        expected_not = {
            "true_environment",
            "current_active_capacity",
            "pending_actions",
            "current_queue_safety_state",
        }
        if not isinstance(does_not, list) or set(does_not) != expected_not:
            _err(
                errors,
                "stale_state_semantics does_not_mutate must be true_environment, "
                "current_active_capacity, pending_actions, current_queue_safety_state",
            )
        if (
            sss.get("queue_ceiling_enforcement")
            != "true_current_waiting_room_occupancy_plus_same_tick_admitted_reservations"
        ):
            _err(
                errors,
                "stale_state_semantics queue_ceiling_enforcement must be "
                "true_current_waiting_room_occupancy_plus_same_tick_admitted_reservations",
            )
        if sss.get("queue_ceiling_uses_stale_view") is not False:
            _err(
                errors,
                "stale_state_semantics queue_ceiling_uses_stale_view must be false (never stale)",
            )
        if sss.get("queue_safety_invariant_is_current") is not True:
            _err(errors, "stale_state_semantics queue_safety_invariant_is_current must be true")
        if sss.get("radio_viability_is_current_frozen_channel") is not True:
            _err(
                errors,
                "stale_state_semantics radio_viability_is_current_frozen_channel must be true",
            )
        if (
            sss.get("deadline_formula_unchanged")
            != "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]"
        ):
            _err(
                errors,
                "stale_state_semantics deadline_formula_unchanged "
                "must be effective_busy_ms < TASK_DEADLINE_MS",
            )
        if sss.get("deadline_workload_observation_has_state_age") is not True:
            _err(
                errors,
                "stale_state_semantics deadline_workload_observation_has_state_age must be true",
            )
        if sss.get("queue_safety_uses_current_not_stale") is not True:
            _err(errors, "stale_state_semantics queue_safety_uses_current_not_stale must be true")
        init = sss.get("initialization")
        if not isinstance(init, dict):
            _err(errors, "stale_state_semantics initialization missing or not dict")
            init = {}
        else:
            if (
                init.get("infrastructure_backlog_and_admitted_arrival_history")
                != "inherited_empty_initial_state"
            ):
                _err(
                    errors,
                    "stale initialization infrastructure_backlog_and_admitted_arrival_history "
                    "must be inherited_empty_initial_state",
                )
            if init.get("control_clock_offset_ms") != 3000:
                _err(errors, "stale initialization control_clock_offset_ms must be 3000")
            if init.get("applies_when") != "when_stale_robustness_evaluated_all_arms":
                _err(
                    errors,
                    "stale initialization applies_when must be "
                    "when_stale_robustness_evaluated_all_arms",
                )
            if init.get("prepopulate_control_times_ms") != [0, 1000, 2000]:
                _err(
                    errors,
                    "stale initialization prepopulate_control_times_ms must be [0,1000,2000]",
                )
            if init.get("prepopulate_value") != "empty_initial_infrastructure_state":
                _err(
                    errors,
                    "stale initialization prepopulate_value "
                    "must be empty_initial_infrastructure_state",
                )
            if init.get("trace_tick_0_maps_to_control_time_ms") != 3000:
                _err(
                    errors, "stale initialization trace_tick_0_maps_to_control_time_ms must be 3000"
                )
            if init.get("is_declared_simulator_initial_condition") is not True:
                _err(
                    errors,
                    "stale initialization is_declared_simulator_initial_condition must be true",
                )
            if init.get("not_observed_pretrace_manchester_traffic") is not True:
                _err(
                    errors,
                    "stale initialization not_observed_pretrace_manchester_traffic must be true",
                )
            if init.get("not_real_world_historical_claim") is not True:
                _err(errors, "stale initialization not_real_world_historical_claim must be true")
            if init.get("permits_exact_0_1000_3000_without_clamping") is not True:
                _err(
                    errors,
                    "stale initialization permits_exact_0_1000_3000_without_clamping must be true",
                )
            if init.get("permits_no_future_leakage") is not True:
                _err(errors, "stale initialization permits_no_future_leakage must be true")
            if init.get("permits_no_unavailable_age_laundering") is not True:
                _err(
                    errors,
                    "stale initialization permits_no_unavailable_age_laundering must be true",
                )
            if init.get("proactive_still_requires_four_actual_trace_observations") is not True:
                _err(
                    errors,
                    "stale initialization "
                    "proactive_still_requires_four_actual_trace_observations must be true",
                )
            if init.get("pretrace_zeros_do_not_satisfy_proactive_warmup") is not True:
                _err(
                    errors,
                    "stale initialization "
                    "pretrace_zeros_do_not_satisfy_proactive_warmup must be true",
                )
            if (
                init.get("scaling_delay_cooldown_use_control_clock_differences_no_extra_delay")
                is not True
            ):
                _err(
                    errors,
                    "stale initialization "
                    "scaling_delay_cooldown_use_control_clock_differences_no_extra_delay "
                    "must be true",
                )
        fresh = sss.get("fresh_cells_reusable_because")
        if not isinstance(fresh, dict):
            _err(errors, "stale_state_semantics fresh_cells_reusable_because missing or not dict")
        else:
            if fresh.get("offset_does_not_enter_p2c_key_outer_tick_does") is not True:
                _err(
                    errors,
                    "fresh_cells_reusable_because "
                    "offset_does_not_enter_p2c_key_outer_tick_does must be true",
                )
            if fresh.get("formulas_use_elapsed_differences") is not True:
                _err(
                    errors,
                    "fresh_cells_reusable_because formulas_use_elapsed_differences must be true",
                )
            if fresh.get("state_age_0_views_identical") is not True:
                _err(
                    errors, "fresh_cells_reusable_because state_age_0_views_identical must be true"
                )
        exposes = sss.get("exposes")
        if not isinstance(exposes, list) or set(exposes) != {
            "requested_state_age_ms",
            "actual_state_age_ms",
            "observation_time_ms",
            "control_time_ms",
        }:
            _err(
                errors,
                "stale_state_semantics exposes must be requested_state_age_ms, "
                "actual_state_age_ms, observation_time_ms, control_time_ms",
            )
        forbidden = sss.get("forbidden_behaviors")
        expected_forbidden = {
            "stale_deadline_view_silently_becoming_fresh",
            "stale_queue_cap",
            "mutation_of_true_state",
            "pretrace_values_counted_as_proactive_warmup",
            "clock_clamp",
            "state_age_laundering",
            "offset_added_to_action_delay",
        }
        if not isinstance(forbidden, list) or set(forbidden) != expected_forbidden:
            _err(
                errors,
                "stale_state_semantics forbidden_behaviors "
                "must be exact list of 7 forbidden behaviors",
            )

    # Claim boundaries
    cb = data.get("claim_boundaries", {})
    if cb.get("kubernetes_orchestration_tested") is not False:
        _err(errors, "kubernetes orchestration must not be claimed tested")
    if cb.get("physical_result_return_tested") is not False:
        _err(errors, "physical result return must not be claimed tested")
    if cb.get("proactive_is_transparent_baseline_not_optimal") is not True:
        _err(errors, "proactive_is_transparent_baseline_not_optimal must be true")

    # Stale decision vs true execution decoupling — exact semantics
    sdt = data.get("stale_decision_vs_true_execution")
    if not isinstance(sdt, dict):
        _err(errors, "stale_decision_vs_true_execution missing or not dict")
    else:
        if sdt.get("observed_decision_backlog_work_ms") != (
            "fresh_or_delayed_immutable_backlog_work_ms_plus_"
            "decision_overlay_plus_same_tick_reservation_overlay"
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution observed_decision_backlog_work_ms must be "
                "fresh_or_delayed_immutable_backlog_work_ms_plus_decision_overlay_plus_same_tick_reservation_overlay",
            )
        if "fresh/delayed immutable workload plus the decision overlay" not in str(
            sdt.get("observed_decision_definition", "")
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution observed_decision_definition "
                "must state fresh/delayed immutable workload plus decision overlay",
            )
        if sdt.get("true_execution_backlog_work_ms") != (
            "current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU"
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution true_execution_backlog_work_ms must be "
                "current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU",
            )
        if sdt.get("placement_uses_observed") is not True:
            _err(errors, "stale_decision_vs_true_execution placement_uses_observed must be true")
        if sdt.get("deadline_admission_gate_uses_observed_backlog_only") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "deadline_admission_gate_uses_observed_backlog_only must be true",
            )
        true_det = sdt.get("true_execution_determines") or []
        for need in [
            "simulated_queue_wait",
            "task_latency",
            "deadline_success",
            "enqueue",
            "subsequent_true_drain",
        ]:
            if need not in true_det:
                _err(
                    errors,
                    f"stale_decision_vs_true_execution "
                    f"true_execution_determines must contain {need}",
                )
        if sdt.get("optimistic_stale_admitted_executes_and_may_miss_per_true_latency") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "optimistic_stale_admitted_executes_and_may_miss_per_true_latency must be true",
            )
        if (
            sdt.get(
                "pessimistic_stale_rejected_never_executes_even_if_true_would_have_been_feasible"
            )
            is not True
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "pessimistic_stale_rejected_never_executes_even_if_true_would_have_been_feasible "
                "must be true",
            )
        if sdt.get("queue_cap_safety_still_wins_current_not_stale") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "queue_cap_safety_still_wins_current_not_stale must be true",
            )
        if sdt.get("scaling_decisions_observe_delayed_signals") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "scaling_decisions_observe_delayed_signals must be true",
            )
        if (
            sdt.get("current_capacity_action_application_and_drain_operate_on_true_state")
            is not True
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "current_capacity_action_application_and_drain_operate_on_true_state must be true",
            )
        if (
            sdt.get("deadline_success_based_on_true_simulated_latency_never_stale_estimate")
            is not True
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "deadline_success_based_on_true_simulated_latency_never_stale_estimate "
                "must be true",
            )
        if (
            sdt.get("deadline_success_is_simulator_outcome_not_physical_lifecycle_evidence")
            is not True
        ):
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "deadline_success_is_simulator_outcome_not_physical_lifecycle_evidence "
                "must be true",
            )
        if sdt.get("physical_started_completed_returned_remain_null") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "physical_started_completed_returned_remain_null must be true",
            )
        if sdt.get("later_scale_actions_do_not_retroactively_reprice_recorded_task") is not True:
            _err(
                errors,
                "stale_decision_vs_true_execution "
                "later_scale_actions_do_not_retroactively_reprice_recorded_task must be true",
            )
        fb = sdt.get("forbidden_behaviors") or []
        for need in [
            "stale_belief_used_for_actual_latency_or_success",
            "true_state_used_for_stale_decision",
            "executing_pessimistically_rejected_work",
            "delaying_true_capacity_or_drain",
        ]:
            if need not in fb:
                _err(
                    errors,
                    f"stale_decision_vs_true_execution forbidden_behaviors must contain {need}",
                )

    # P2C dense counter-key mapping — exact semantics
    p2ccm = data.get("p2c_dense_counter_key_mapping")
    if not isinstance(p2ccm, dict):
        _err(errors, "p2c_dense_counter_key_mapping missing or not dict")
    else:
        outer = p2ccm.get("outer_tick", {})
        if not isinstance(outer, dict) or outer.get("definition") != "zero_based_trace_tick":
            _err(
                errors,
                "p2c_dense_counter_key_mapping outer_tick definition must be zero_based_trace_tick",
            )
        if outer.get("range") != "[0,3599]":
            _err(errors, "p2c_dense_counter_key_mapping outer_tick range must be [0,3599]")
        task = p2ccm.get("task_slot", {})
        if not isinstance(task, dict) or task.get("definition") != "zero_based_within_tick_substep":
            _err(
                errors,
                "p2c_dense_counter_key_mapping task_slot "
                "definition must be zero_based_within_tick_substep",
            )
        if task.get("range") != "[0,4]":
            _err(errors, "p2c_dense_counter_key_mapping task_slot range must be [0,4]")
        if task.get("advances_physical_time") is not False:
            _err(
                errors,
                "p2c_dense_counter_key_mapping task_slot advances_physical_time must be false",
            )
        vehicle = p2ccm.get("vehicle_slot", {})
        if (
            not isinstance(vehicle, dict)
            or vehicle.get("definition") != "zero_based_padded_fleet_slot"
        ):
            _err(
                errors,
                "p2c_dense_counter_key_mapping vehicle_slot "
                "definition must be zero_based_padded_fleet_slot",
            )
        if vehicle.get("range") != "[0,2487]":
            _err(errors, "p2c_dense_counter_key_mapping vehicle_slot range must be [0,2487]")
        if vehicle.get("padded_fleet_width") != 2488:
            _err(
                errors, "p2c_dense_counter_key_mapping vehicle_slot padded_fleet_width must be 2488"
            )
        seq = p2ccm.get("sequential_task_ordinal", {})
        if not isinstance(seq, dict):
            _err(
                errors, "p2c_dense_counter_key_mapping sequential_task_ordinal missing or not dict"
            )
        else:
            if seq.get("formula") != "task_slot * padded_fleet_width + vehicle_slot":
                _err(
                    errors,
                    "p2c_dense_counter_key_mapping sequential_task_ordinal "
                    "formula must be task_slot * padded_fleet_width + vehicle_slot",
                )
            if seq.get("range") != "[0,12439]":
                _err(
                    errors,
                    "p2c_dense_counter_key_mapping sequential_task_ordinal range must be [0,12439]",
                )
            if seq.get("per_outer_tick") is not True:
                _err(
                    errors,
                    "p2c_dense_counter_key_mapping "
                    "sequential_task_ordinal per_outer_tick must be true",
                )
            if seq.get("dense_position_identity") is not True:
                _err(
                    errors,
                    "p2c_dense_counter_key_mapping sequential_task_ordinal "
                    "dense_position_identity must be true",
                )
            for flag in [
                "independent_of_active_mask",
                "independent_of_actor_choice",
                "independent_of_feasibility",
                "independent_of_admission_or_rejection",
                "earlier_outcomes_never_shift_later_pairs",
            ]:
                if seq.get(flag) is not True:
                    _err(
                        errors,
                        f"p2c_dense_counter_key_mapping "
                        f"sequential_task_ordinal {flag} must be true",
                    )
        if p2ccm.get("vehicle_slot_is_provenance_but_not_mixer_field") is not True:
            _err(
                errors,
                "p2c_dense_counter_key_mapping "
                "vehicle_slot_is_provenance_but_not_mixer_field must be true",
            )
        if p2ccm.get("declared_mixer_fields_remain_exactly_five") != [
            "evaluator_seed",
            "fleet_seed",
            "outer_tick",
            "task_slot",
            "sequential_task_ordinal",
        ]:
            _err(
                errors,
                "p2c_dense_counter_key_mapping declared_mixer_fields_remain_exactly_five "
                "must be exactly five specified",
            )
        if p2ccm.get("padded_fleet_width") != 2488:
            _err(errors, "p2c_dense_counter_key_mapping padded_fleet_width must be 2488")
        if p2ccm.get("per_outer_tick_range") != "[0,12439]":
            _err(errors, "p2c_dense_counter_key_mapping per_outer_tick_range must be [0,12439]")
        if p2ccm.get("outer_tick_is_zero_based") is not True:
            _err(errors, "p2c_dense_counter_key_mapping outer_tick_is_zero_based must be true")
        if p2ccm.get("task_slot_is_zero_based") is not True:
            _err(errors, "p2c_dense_counter_key_mapping task_slot_is_zero_based must be true")
        if p2ccm.get("vehicle_slot_is_zero_based") is not True:
            _err(errors, "p2c_dense_counter_key_mapping vehicle_slot_is_zero_based must be true")
        fb2 = p2ccm.get("forbidden_behaviors") or []
        for need in [
            "active_only_ordinal",
            "ordinal_reset_or_collision",
            "200ms_time_interpretation",
            "outcome_dependent_key_shifts",
        ]:
            if need not in fb2:
                _err(
                    errors, f"p2c_dense_counter_key_mapping forbidden_behaviors must contain {need}"
                )

    # H1 state-inspection honest estimands
    h1s = data.get("h1_state_inspection")
    if not isinstance(h1s, dict):
        _err(errors, "h1_state_inspection missing or not dict")
    else:
        if h1s.get("feasibility_first_must_enumerate_all_RSU_deadline_feasibility") is not True:
            _err(
                errors,
                "h1_state_inspection "
                "feasibility_first_must_enumerate_all_RSU_deadline_feasibility must be true",
            )
        if h1s.get("must_not_claim_only_two_total_global_reads") is not True:
            _err(
                errors,
                "h1_state_inspection must_not_claim_only_two_total_global_reads must be true",
            )
        if h1s.get("must_not_claim_distributed_communication_savings") is not True:
            _err(
                errors,
                "h1_state_inspection must_not_claim_distributed_communication_savings must be true",
            )
        if h1s.get("must_not_claim_proven_lower_total_state_acquisition") is not True:
            _err(
                errors,
                "h1_state_inspection "
                "must_not_claim_proven_lower_total_state_acquisition must be true",
            )
        sep = h1s.get("separately_record") or []
        for need in [
            "feasibility_workload_checks",
            "ranking_workload_inspections",
            "unique_workload_values_observed",
        ]:
            if need not in sep:
                _err(errors, f"h1_state_inspection separately_record must contain {need}")
        if h1s.get("p2c_ranking_inspection_is_0_1_2_according_to_feasible_count") is not True:
            _err(
                errors,
                "h1_state_inspection "
                "p2c_ranking_inspection_is_0_1_2_according_to_feasible_count must be true",
            )
        if h1s.get("per_task_dla_global_argmin_ranks_all_R") is not True:
            _err(errors, "h1_state_inspection per_task_dla_global_argmin_ranks_all_R must be true")
        if h1s.get("common_feasibility_decision_observation_cost_remains_visible") is not True:
            _err(
                errors,
                "h1_state_inspection "
                "common_feasibility_decision_observation_cost_remains_visible must be true",
            )
        if h1s.get("any_duplicated_reads_remain_visible") is not True:
            _err(errors, "h1_state_inspection any_duplicated_reads_remain_visible must be true")
        if (
            h1s.get(
                "h1_is_hypothesis_about_pair_only_ranking_vs_global_least_busy_dependence_not_proved_networking_cost"
            )
            is not True
        ):
            _err(
                errors,
                "h1_state_inspection "
                "h1_is_hypothesis_about_pair_only_ranking_vs_global_"
                "least_busy_dependence_not_proved_networking_cost "
                "must be true",
            )
        if h1s.get("h1_remains_hypothesis_allowed_to_fail") is not True:
            _err(errors, "h1_state_inspection h1_remains_hypothesis_allowed_to_fail must be true")
        fc = h1s.get("forbidden_claims") or []
        for need in ["two_total_reads", "hidden_feasibility_scan", "communication_savings_proven"]:
            if need not in fc:
                _err(errors, f"h1_state_inspection forbidden_claims must contain {need}")

    # Resource-state diagnostics — exact
    rsd = data.get("resource_state_diagnostics")
    if not isinstance(rsd, dict):
        _err(errors, "resource_state_diagnostics missing or not dict")
    else:
        cap = rsd.get("capacity_adjusted_utilization", {})
        if (
            not isinstance(cap, dict)
            or cap.get("formula") != "drained_work_ms / (active_capacity_units * 1000 work_ms)"
        ):
            _err(
                errors,
                "resource_state_diagnostics capacity_adjusted_utilization formula "
                "must be drained_work_ms / (active_capacity_units * 1000 work_ms)",
            )
        if cap.get("bounded") != "[0,1]":
            _err(
                errors,
                "resource_state_diagnostics capacity_adjusted_utilization bounded must be [0,1]",
            )
        if (
            cap.get("waiting_room_occupancy_is_separate_task_count_and_never_denominator")
            is not True
        ):
            _err(
                errors,
                "resource_state_diagnostics capacity_adjusted_utilization "
                "waiting_room_occupancy_is_separate_task_count_and_never_denominator must be true",
            )
        if cap.get("utilization_is_per_RSU_per_tick") is not True:
            _err(
                errors,
                "resource_state_diagnostics capacity_adjusted_utilization "
                "utilization_is_per_RSU_per_tick must be true",
            )
        share = rsd.get("execution_share", {})
        if (
            not isinstance(share, dict)
            or share.get("formula")
            != "actual_admitted_V2I_execution_count_at_RSU / total_admitted_V2I_execution_count"
        ):
            _err(
                errors,
                "resource_state_diagnostics execution_share formula must be "
                "actual_admitted_V2I_execution_count_at_RSU / total_admitted_V2I_execution_count",
            )
        if share.get("when_denominator_zero_is_null_with_explicit_reason_not_zeros") is not True:
            _err(
                errors,
                "resource_state_diagnostics execution_share "
                "when_denominator_zero_is_null_with_explicit_reason_not_zeros must be true",
            )
        tgt = rsd.get("target_switching", {})
        if not isinstance(tgt, dict):
            _err(errors, "resource_state_diagnostics target_switching missing or not dict")
        else:
            if (
                tgt.get("counted_over_consecutive_admitted_V2I_tasks_in_deterministic_order")
                != "(outer_tick, task_slot, vehicle_slot)"
            ):
                _err(
                    errors,
                    "resource_state_diagnostics target_switching "
                    "counted_over_consecutive_admitted_V2I_tasks_in_deterministic_order "
                    "must be (outer_tick, task_slot, vehicle_slot)",
                )
            if tgt.get("first_admitted_task_is_not_a_switch") is not True:
                _err(
                    errors,
                    "resource_state_diagnostics target_switching "
                    "first_admitted_task_is_not_a_switch must be true",
                )
            if tgt.get("rejected_and_non_V2I_tasks_excluded") is not True:
                _err(
                    errors,
                    "resource_state_diagnostics target_switching "
                    "rejected_and_non_V2I_tasks_excluded must be true",
                )
            if tgt.get("counts_never_cross_fleet_draws") is not True:
                _err(
                    errors,
                    "resource_state_diagnostics target_switching "
                    "counts_never_cross_fleet_draws must be true",
                )
            if (
                tgt.get("order_is_exact_deterministic_outer_tick_task_slot_vehicle_slot")
                is not True
            ):
                _err(
                    errors,
                    "resource_state_diagnostics target_switching "
                    "order_is_exact_deterministic_outer_tick_task_slot_vehicle_slot must be true",
                )
        if (
            rsd.get(
                "resource_unit_seconds_denominator_stays_required_for_diagnostic_deadline_per_resource_cost"
            )
            is not True
        ):
            _err(
                errors,
                "resource_state_diagnostics "
                "resource_unit_seconds_denominator_stays_required_"
                "for_diagnostic_deadline_per_resource_cost "
                "must be true",
            )
        if rsd.get("no_monetary_or_automatically_authoritative_objective_claim") is not True:
            _err(
                errors,
                "resource_state_diagnostics "
                "no_monetary_or_automatically_authoritative_objective_claim must be true",
            )
        fb3 = rsd.get("forbidden_behaviors") or []
        for need in [
            "raw_over_1000_utilization_under_u_gt_1",
            "queue_occupancy_as_denominator",
            "zero_fill_shares_when_denominator_zero",
            "rejected_task_switches",
            "unordered_or_across_draw_switches",
            "missing_cost_denominator",
        ]:
            if need not in fb3:
                _err(errors, f"resource_state_diagnostics forbidden_behaviors must contain {need}")

    # E2d-lineage audit items 1-5: p2c_candidate_predicate, p2c_mixer, tick_transition,
    # v2i_latency_outcome_contract, accounting_and_contrast_completion

    # 1. P2C candidate predicate and low-cardinality behavior
    pcp = data.get("p2c_candidate_predicate")
    if not isinstance(pcp, dict):
        _err(errors, "p2c_candidate_predicate missing or not dict")
    else:
        if (
            pcp.get("admission_requires")
            != "active frozen-actor V2I attempt and ingress radio currently viable"
        ):
            _err(
                errors,
                "p2c_candidate_predicate admission_requires must be active "
                "frozen-actor V2I attempt and ingress radio currently viable",
            )
        feas = pcp.get("feasible_RSU_predicate", {})
        if not isinstance(feas, dict):
            _err(errors, "p2c_candidate_predicate feasible_RSU_predicate missing or not dict")
        else:
            if feas.get("candidate_order") != "sorted ascending unique feasible RSU IDs":
                _err(
                    errors,
                    "feasible_RSU_predicate candidate_order must "
                    "be sorted ascending unique feasible RSU IDs",
                )
            conds = feas.get("conditions_both")
            if (
                not isinstance(conds, list)
                or "observed_decision_backlog_work_ms[rsu] < task_deadline_ms" not in conds
                or "true_current_waiting_room_occupancy[rsu] + prior "
                "same-tick admitted reservations < queue_ceiling"
                not in conds
            ):
                _err(
                    errors,
                    "feasible_RSU_predicate conditions_both must contain both "
                    "backlog<deadline and true_current_waiting_room+same_tick < ceiling",
                )
            if feas.get("radio_is_current") is not True:
                _err(errors, "feasible_RSU_predicate radio_is_current must be true")
            if feas.get("queue_safety_is_current_not_stale") is not True:
                _err(
                    errors, "feasible_RSU_predicate queue_safety_is_current_not_stale must be true"
                )
            if feas.get("only_backlog_deadline_belief_is_aged") is not True:
                _err(
                    errors,
                    "feasible_RSU_predicate only_backlog_deadline_belief_is_aged must be true",
                )
        n0 = pcp.get("n_equals_0", {})
        if (
            not isinstance(n0, dict)
            or n0.get("select_no_target") is not True
            or n0.get("reject_without_execution") is not True
        ):
            _err(
                errors,
                "p2c_candidate_predicate n_equals_0 must "
                "select_no_target and reject_without_execution",
            )
        else:
            clas = n0.get("classification", {})
            if (
                not isinstance(clas, dict)
                or clas.get("if_ingress_radio_not_viable") != "v2i_unavailable"
                or clas.get("elif_no_RSU_observed_deadline_feasible") != "v2i_gate_rejected"
                or clas.get("else_deadline_feasible_exist_but_all_full") != "v2i_cap_rejected"
            ):
                _err(
                    errors,
                    "p2c_candidate_predicate n_equals_0 classification must be "
                    "v2i_unavailable / v2i_gate_rejected / v2i_cap_rejected",
                )
        n1 = pcp.get("n_equals_1", {})
        if (
            not isinstance(n1, dict)
            or n1.get("select_sole_feasible_RSU") is not True
            or n1.get("hashing_skipped") is not True
            or n1.get("no_second_hash_modulo") is not True
            or n1.get("ranking_inspections") != 1
        ):
            _err(
                errors,
                "p2c_candidate_predicate n_equals_1 must select sole feasible "
                "without second hash/modulo and ranking_inspections=1",
            )
        n2 = pcp.get("n_gte_2", {})
        if (
            not isinstance(n2, dict)
            or n2.get("deterministic_distinct_pair") is not True
            or n2.get("selection") != "lower observed backlog"
            or n2.get("tie_break") != "stable lowest-ID"
            or n2.get("without_replacement") is not True
        ):
            _err(
                errors,
                "p2c_candidate_predicate n_gte_2 must be deterministic distinct pair "
                "lower observed backlog stable lowest-ID tie without replacement",
            )
        res = pcp.get("reservation", {})
        if (
            not isinstance(res, dict)
            or res.get(
                "reserve_true_load_raw_work_and_decision_overlay_immediately_only_on_admission"
            )
            is not True
            or res.get("rejected_work_never_reserved") is not True
        ):
            _err(
                errors,
                "p2c_candidate_predicate reservation must reserve true load/raw work and "
                "decision overlay immediately only on admission and rejected never reserved",
            )
        fb = pcp.get("forbidden_behaviors") or []
        for need in [
            "sample-before-filter",
            "stale queue-cap",
            "undefined n=0/1",
            "rejection ambiguity",
            "rejected-work reservation",
        ]:
            if need not in fb:
                _err(errors, f"p2c_candidate_predicate forbidden_behaviors must contain {need}")

    # 2. P2C mixer — uint64, SplitMix exact, test vectors
    pm = data.get("p2c_mixer")
    if not isinstance(pm, dict):
        _err(errors, "p2c_mixer missing or not dict")
    else:
        fd = pm.get("field_declaration", {})
        if not isinstance(fd, dict) or fd.get("fields_ordered") != [
            "evaluator_seed",
            "fleet_seed",
            "outer_tick",
            "task_slot",
            "sequential_task_ordinal",
        ]:
            _err(
                errors,
                "p2c_mixer field_declaration fields_ordered must be exactly "
                "evaluator_seed,fleet_seed,outer_tick,task_slot,sequential_task_ordinal",
            )
        if fd.get("field_type") != "non-negative unsigned 64-bit (uint64)":
            _err(
                errors,
                "p2c_mixer field_declaration field_type must "
                "be non-negative unsigned 64-bit (uint64)",
            )
        if fd.get("wrap_modulo") != "2^64 after every operation":
            _err(
                errors, "p2c_mixer field_declaration wrap_modulo must be 2^64 after every operation"
            )
        bounds = fd.get("bounds", {})
        if (
            not isinstance(bounds, dict)
            or bounds.get("outer_tick") != "[0, 3599]"
            or bounds.get("task_slot") != "[0, 4]"
            or bounds.get("sequential_task_ordinal") != "[0, 12439]"
        ):
            _err(
                errors,
                "p2c_mixer field_declaration bounds must be [0,3599] "
                "outer_tick, [0,4] task_slot, [0,12439] ordinal",
            )
        sdef = pm.get("splitmix64_definition", {})
        if not isinstance(sdef, dict):
            _err(errors, "p2c_mixer splitmix64_definition missing or not dict")
        else:
            steps = sdef.get("steps") or []
            if "z=(x+0x9E3779B97F4A7C15) mod 2^64" not in steps:
                _err(
                    errors,
                    "p2c_mixer splitmix64_definition steps must "
                    "contain z=(x+0x9E3779B97F4A7C15) mod 2^64",
                )
            if "z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64" not in steps:
                _err(
                    errors,
                    "p2c_mixer splitmix64_definition steps must contain "
                    "z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64",
                )
            if "z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64" not in steps:
                _err(
                    errors,
                    "p2c_mixer splitmix64_definition steps must contain "
                    "z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64",
                )
            if "return z xor (z>>31)" not in steps:
                _err(
                    errors,
                    "p2c_mixer splitmix64_definition steps must contain return z xor (z>>31)",
                )
            if sdef.get("wrap_modulo_2_64_after_every_operation") is not True:
                _err(
                    errors,
                    "p2c_mixer splitmix64_definition "
                    "wrap_modulo_2_64_after_every_operation must be true",
                )
            consts = sdef.get("constants_hex") or []
            for need in ["0x9E3779B97F4A7C15", "0xBF58476D1CE4E5B9", "0x94D049BB133111EB"]:
                if need not in consts:
                    _err(
                        errors, f"p2c_mixer splitmix64_definition constants_hex must contain {need}"
                    )
        fold = pm.get("fold", {})
        if (
            not isinstance(fold, dict)
            or fold.get("h_init") != "0x6A09E667F3BCC909"
            or fold.get("for_each_ordered_field") != "h=splitmix64(h xor uint64(field))"
        ):
            _err(
                errors,
                "p2c_mixer fold must be h_init 0x6A09E667F3BCC909 and "
                "for_each_ordered_field h=splitmix64(h xor uint64(field))",
            )
        expected_order = EXPECTED_COUNTER_FIELDS
        fold_order = fold.get("field_order") if isinstance(fold, dict) else None
        if fold_order != expected_order:
            _err(
                errors,
                f"p2c_mixer fold field_order must exactly equal "
                f"{expected_order} (got {fold_order!r})",
            )
        fd_order = fd.get("fields_ordered") if isinstance(fd, dict) else None
        if fd_order != expected_order:
            _err(
                errors,
                "p2c_mixer field_declaration fields_ordered must "
                f"exactly equal {expected_order} (got {fd_order!r})",
            )
        if isinstance(fold_order, list) and isinstance(fd_order, list) and fold_order != fd_order:
            _err(
                errors,
                "p2c_mixer fold field_order must exactly equal "
                "field_declaration fields_ordered "
                f"(fold {fold_order!r} != declaration {fd_order!r})",
            )
        pidx = pm.get("pair_indices", {})
        if not isinstance(pidx, dict):
            _err(errors, "p2c_mixer pair_indices missing or not dict")
        else:
            gte2 = pidx.get("for_n_gte_2", {})
            if (
                not isinstance(gte2, dict)
                or gte2.get("first_index") != "h % n"
                or gte2.get("j") != "splitmix64(h) % (n-1)"
                or gte2.get("second_index") != "j if j<first_index else j+1"
            ):
                _err(
                    errors,
                    "p2c_mixer pair_indices for_n_gte_2 must be first h % "
                    "n, j splitmix64(h)%(n-1), second j if j<first else j+1",
                )
            if gte2.get("candidate_order_is_ascending_unique_RSU_ID") is not True:
                _err(
                    errors,
                    "p2c_mixer pair_indices "
                    "candidate_order_is_ascending_unique_RSU_ID must be true",
                )
            if gte2.get("sort_resulting_pair_only_for_telemetry_not_before_indexing") is not True:
                _err(
                    errors,
                    "p2c_mixer pair_indices "
                    "sort_resulting_pair_only_for_telemetry_not_before_indexing must be true",
                )
            if pidx.get("for_n_equals_1_hashing_skipped") is not True:
                _err(errors, "p2c_mixer pair_indices for_n_equals_1_hashing_skipped must be true")
        tv = pm.get("test_vectors")
        if not isinstance(tv, list) or len(tv) < 3:
            _err(errors, "p2c_mixer test_vectors must be list of at least 3")
        else:
            # Verify deterministic computation of vectors using Python reference
            mask64 = (1 << 64) - 1
            c1 = 0x9E3779B97F4A7C15
            c2 = 0xBF58476D1CE4E5B9
            c3 = 0x94D049BB133111EB
            h0 = 0x6A09E667F3BCC909

            def _sm(x: int) -> int:
                z: int = (x + c1) & mask64
                z = ((z ^ (z >> 30)) * c2) & mask64
                z = ((z ^ (z >> 27)) * c3) & mask64
                return (z ^ (z >> 31)) & mask64

            def _fold(fields: list[int]) -> int:
                h: int = h0
                for f in fields:
                    if not isinstance(f, int):
                        _err(
                            errors,
                            f"p2c_mixer test_vectors field {f!r} must be int",
                        )
                        return h
                    if f < 0 or f > mask64:
                        _err(
                            errors,
                            f"p2c_mixer test_vectors field {f} out of uint64 range",
                        )
                        return h
                    h = _sm((h ^ (f & mask64)) & mask64)
                return h

            # Check all-zero vector present
            has_zero = any(
                str(v.get("h_hex", "")).lower() == "0x7d19c361a3548205"
                and v.get("note") == "all-zero fields"
                for v in tv
            )
            if not has_zero:
                _err(
                    errors,
                    "p2c_mixer test_vectors must contain "
                    "all-zero fields vector h=0x7d19c361a3548205",
                )
            has_boundary = any(
                str(v.get("h_hex", "")).lower() == "0x295c562a48f4f730"
                and "3599" in str(v.get("note", ""))
                for v in tv
            )
            if not has_boundary:
                _err(
                    errors,
                    "p2c_mixer test_vectors must contain boundary "
                    "outer_tick=3599/task_slot=4/ordinal=12439 vector h=0x295c562a48f4f730",
                )
            for v in tv:
                if not isinstance(v, dict):
                    _err(errors, "p2c_mixer test_vectors entry must be dict")
                    continue
                fields = v.get("fields")
                h_hex = str(v.get("h_hex", "")).lower()
                h_dec = v.get("h_dec")
                n = v.get("n")
                first = v.get("first_index")
                second = v.get("second_index")
                sorted_pair = v.get("sorted_pair")
                if not isinstance(fields, dict):
                    _err(errors, "p2c_mixer test_vectors fields must be dict")
                    continue
                ordered = [
                    fields.get(k)
                    for k in [
                        "evaluator_seed",
                        "fleet_seed",
                        "outer_tick",
                        "task_slot",
                        "sequential_task_ordinal",
                    ]
                ]
                if any(x is None for x in ordered):
                    _err(
                        errors,
                        "p2c_mixer test_vectors fields must contain "
                        "evaluator_seed,fleet_seed,outer_tick,task_slot,sequential_task_ordinal",
                    )
                    continue
                narrowed: list[int] = []
                for x in ordered:
                    if not isinstance(x, int):
                        _err(
                            errors,
                            f"p2c_mixer test_vectors field {x!r} must be int",
                        )
                        narrowed = []
                        break
                    if x < 0 or x > mask64:
                        _err(
                            errors,
                            f"p2c_mixer test_vectors field {x} out of uint64 range",
                        )
                        narrowed = []
                        break
                    narrowed.append(x)
                if len(narrowed) != 5:
                    continue
                exp_h = _fold(narrowed)
                exp_hex = f"0x{exp_h:016x}"
                if h_hex != exp_hex.lower():
                    _err(
                        errors,
                        f"p2c_mixer test_vectors h_hex {h_hex} must "
                        f"equal computed {exp_hex} for fields {ordered}",
                    )
                if h_dec is not None and int(h_dec) != exp_h:
                    _err(errors, f"p2c_mixer test_vectors h_dec {h_dec} must equal {exp_h}")
                if isinstance(n, int) and n >= 2:
                    exp_first = exp_h % n
                    j = _sm(exp_h) % (n - 1)
                    exp_second = j if j < exp_first else j + 1
                    if first is not None and int(first) != exp_first:
                        _err(
                            errors,
                            f"p2c_mixer test_vectors first_index "
                            f"{first} must equal {exp_first} for n={n}",
                        )
                    if second is not None and int(second) != exp_second:
                        _err(
                            errors,
                            f"p2c_mixer test_vectors second_index "
                            f"{second} must equal {exp_second} for n={n}",
                        )
                    if sorted_pair is not None:
                        exp_sorted = sorted([exp_first, exp_second])
                        if list(sorted_pair) != exp_sorted:
                            _err(
                                errors,
                                f"p2c_mixer test_vectors sorted_pair "
                                f"{sorted_pair} must equal {exp_sorted}",
                            )
        if pm.get("uniformity_claim_forbidden") is not True:
            _err(errors, "p2c_mixer uniformity_claim_forbidden must be true")
        if "negligible bias not mathematically exact-uniform" not in str(
            pm.get("modulo_bias_note", "")
        ):
            _err(
                errors,
                "p2c_mixer modulo_bias_note must state negligible "
                "bias not mathematically exact-uniform",
            )
        fb = pm.get("forbidden_behaviors") or []
        for need in [
            "alternate SplitMix variants",
            "string/byte serialization",
            "signed overflow",
            "field reordering",
            "missing vectors",
            "claim modulo exact uniformity",
        ]:
            if need not in fb:
                _err(errors, f"p2c_mixer forbidden_behaviors must contain {need}")

    # 3. Tick transition
    tt = data.get("tick_transition")
    if not isinstance(tt, dict):
        _err(errors, "tick_transition missing or not dict")
    else:
        if tt.get("control_clock_offset_ms") != 3000:
            _err(errors, "tick_transition control_clock_offset_ms must be 3000")
        if tt.get("telemetry_schema_same_for_E3a_b_c_including_fresh_cells") is not True:
            _err(
                errors,
                "tick_transition "
                "telemetry_schema_same_for_E3a_b_c_including_fresh_cells must be true",
            )
        steps = tt.get("zero_based_trace_tick_control_time_t", {})
        if not isinstance(steps, dict) or len(steps) < 8:
            _err(errors, "tick_transition zero_based_trace_tick_control_time_t must have 8 steps")
        else:
            expected_keys = [
                "i_start_from_true_state_after_prior_interval_drain",
                "ii_apply_one_pending_action_if_due_emit_applied_receipt_clear_pending",
                "iii_capture_immutable_tick_entry_infrastructure_snapshot_after_due_action_before_current_tick_placement_admission",
                "iv_select_exact_t_state_age_snapshot_for_decision_signals",
                "v_if_no_pending_and_cooldown_permits_make_at_most_one_scaler_decision_per_RSU_and_possibly_emit_schedule_one_requested_action",
                "vi_process_all_five_task_slots_sequentially_without_advancing_time",
                "vii_drain_true_raw_backlog_once_by_min_backlog_u_times_1000_work_ms",
                "viii_charge_post_due_action_capacity_u_for_interval_t_t_plus_1000ms",
            ]
            for k in expected_keys:
                if steps.get(k) is not True:
                    _err(errors, f"tick_transition step {k} must be true")
        cd = tt.get("cooldown", {})
        if (
            not isinstance(cd, dict)
            or cd.get("starts_at_actual_application_time") is not True
            or cd.get("elapsed_gte_5000ms_permits_new_request") is not True
            or cd.get("just_applied_action_starts_cooldown_so_cannot_request_again_that_tick")
            is not True
            or cd.get("any_pending_action_blocks_all_new_directions") is not True
        ):
            _err(
                errors,
                "tick_transition cooldown must have starts_at_actual, elapsed>=5000, "
                "just_applied blocks that tick, any pending blocks all",
            )
        req_fields = tt.get("requested_receipt_fields") or []
        for need in [
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
            "signal_value",
        ]:
            if need not in req_fields:
                _err(errors, f"tick_transition requested_receipt_fields must contain {need}")
        app_adds = tt.get("applied_receipt_adds") or []
        for need in ["actual_application_time_ms", "actual_to_units"]:
            if need not in app_adds:
                _err(errors, f"tick_transition applied_receipt_adds must contain {need}")
        counts = tt.get("counts_expose_separately") or []
        for need in ["scheduled_requests", "applied_up_actions", "applied_down_actions"]:
            if need not in counts:
                _err(errors, f"tick_transition counts_expose_separately must contain {need}")
        if tt.get("resource_cost_follows_applied_capacity_only") is not True:
            _err(errors, "tick_transition resource_cost_follows_applied_capacity_only must be true")
        if tt.get("reactive_tick_entry_signal_is_aged_raw_service_backlog_snapshot") is not True:
            _err(
                errors,
                "tick_transition "
                "reactive_tick_entry_signal_is_aged_raw_service_backlog_snapshot must be true",
            )
        pro = tt.get(
            "proactive_samples_are_completed_prior_trace_interval_admitted_arrival_work_samples", {}
        )
        if (
            not isinstance(pro, dict)
            or pro.get("at_tick_t_no_sample_from_current_tick_available") is not True
            or pro.get("four_actual_trace_intervals_must_have_completed") is not True
            or pro.get("aged_arm_uses_only_samples_present_in_selected_snapshot") is not True
            or pro.get("pretrace_empty_values_never_satisfy_warm_up") is not True
        ):
            _err(
                errors,
                "tick_transition "
                "proactive_samples_are_completed_prior_trace_"
                "interval_admitted_arrival_work_samples "
                "must have 4 flags true",
            )
        if tt.get("reused_state_age_0_cell_bytes_truly_identical") is not True:
            _err(
                errors, "tick_transition reused_state_age_0_cell_bytes_truly_identical must be true"
            )
        fb = tt.get("forbidden_behaviors") or []
        for need in [
            "decision-time cooldown",
            "same-tick post-apply request",
            "action-count conflation",
            "ambiguous timestamps",
        ]:
            if need not in fb:
                _err(errors, f"tick_transition forbidden_behaviors must contain {need}")

    # 4. V2I latency/outcome contract
    vl = data.get("v2i_latency_outcome_contract")
    if not isinstance(vl, dict):
        _err(errors, "v2i_latency_outcome_contract missing or not dict")
    else:
        adm = vl.get("at_admission_record_with_u_current_applied_units", {})
        if not isinstance(adm, dict) or adm.get("simulated_latency_ms_equation") != (
            "current_ingress_tx_ms + forwarding_ms + true_execution_backlog_work_ms/u "
            "+ raw_task_service_work_ms/u + current_return_tx_ms"
        ):
            _err(
                errors,
                "v2i_latency_outcome_contract at_admission "
                "simulated_latency_ms_equation must be current_ingress_tx_ms "
                "+ forwarding_ms + true_execution_backlog_work_ms/u "
                "+ raw_task_service_work_ms/u + current_return_tx_ms",
            )
        if adm.get("raw_work_enqueued_is_never_divided_by_u") is not True:
            _err(
                errors,
                "v2i_latency_outcome_contract raw_work_enqueued_is_never_divided_by_u must be true",
            )
        if (
            adm.get("deadline_success_is_recorded_admitted_simulated_latency_less_task_deadline")
            is not True
        ):
            _err(
                errors,
                "v2i_latency_outcome_contract "
                "deadline_success_is_recorded_admitted_simulated_latency_less_task_deadline "
                "must be true",
            )
        if (
            adm.get("later_scaling_does_not_recompute_latency") is not True
            and adm.get("later_scaling_does_not_reprice_it") is not True
        ):
            _err(
                errors, "v2i_latency_outcome_contract later_scaling_does_not_recompute must be true"
            )
        if (
            adm.get(
                "rejected_work_never_enqueues_never_succeeds_and_inherited_10_deadline_penalty_is_explicitly_not_valid_latency_observation"
            )
            is not True
        ):
            _err(
                errors,
                "v2i_latency_outcome_contract rejected 10*deadline "
                "penalty not valid latency must be true",
            )
        rep = vl.get("report", {})
        if (
            not isinstance(rep, dict)
            or rep.get("admitted_task_latency_only_and_any_declared_deadline_met_diagnostic")
            is not True
            or rep.get(
                "offered_task_latency_is_null_unavailable_because_rejected_penalty_values_are_not_physical_latency"
            )
            is not True
            or rep.get("started_compute_completed_returned_dropped_remain_null_with_reasons")
            is not True
        ):
            _err(
                errors,
                "v2i_latency_outcome_contract report must have admitted_task_latency_only, "
                "offered_task_latency null, lifecycle remains null",
            )
        fb = vl.get("forbidden_behaviors") or []
        for need in [
            "backlog-only/stale outcome latency",
            "divided enqueue work",
            "later repricing",
            "rejected penalty in latency mean",
        ]:
            if need not in fb:
                _err(
                    errors, f"v2i_latency_outcome_contract forbidden_behaviors must contain {need}"
                )

    # 5. Accounting and contrast completion
    acc = data.get("accounting_and_contrast_completion")
    if not isinstance(acc, dict):
        _err(errors, "accounting_and_contrast_completion missing or not dict")
    else:
        loss = acc.get("lossless_accounting", {})
        if (
            not isinstance(loss, dict)
            or loss.get("offered_equals_admitted_plus_rejected") is not True
            or loss.get("deadline_success_between_0_and_admitted") is not True
            or loss.get("forwarded_between_0_and_admitted_v2i_between_0_and_admitted") is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion lossless_accounting must have "
                "offered=admitted+rejected, deadline_success 0..admitted, forwarded checks",
            )
        rej = loss.get("rejected_equals_sum") or []
        for need in [
            "v2i_gate_rejected",
            "v2i_cap_rejected",
            "local_mqd_rejected",
            "v2v_mqd_rejected",
            "v2i_unavailable",
            "v2v_unavailable",
        ]:
            if need not in rej:
                _err(
                    errors,
                    f"accounting_and_contrast_completion lossless_accounting "
                    f"rejected_equals_sum must contain {need}",
                )
        shares = acc.get("shares", {})
        if (
            not isinstance(shares, dict)
            or shares.get("rejection_share_is_rejected_div_offered") is not True
            or shares.get(
                "forwarding_share_is_forwarded_div_admitted_v2i_and_null_reason_if_denominator_zero"
            )
            is not True
            or shares.get(
                "deadline_per_normalized_cost_is_offered_deadline_attainment_div_resource_unit_seconds_and_null_reason_if_cost_zero"
            )
            is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion shares must have "
                "rejection, forwarding, deadline per cost with null+reason",
            )
        if (
            acc.get("work_ms_conservation_where_instrumented_separately_for_V2I_and_vehicle_queues")
            is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion work_ms_conservation "
                "separately for V2I and vehicle queues must be true",
            )
        if (
            acc.get(
                "unavailable_V2V_work_has_no_destination_service_work_and_remains_explicit_count_rather_than_fabricated_zero_work"
            )
            is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion unavailable V2V work has "
                "no destination work and remains explicit count must be true",
            )
        if (
            acc.get(
                "missing_incomplete_cells_make_matched_contrast_status_incomplete_null_never_reduce_n"
            )
            is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion missing/incomplete cells make "
                "matched contrast incomplete/null never reduce n must be true",
            )
        if (
            acc.get(
                "reportable_contrast_requires_all_four_paired_seeds_1_to_4_and_uses_exact_treatment_minus_control_sign"
            )
            is not True
        ):
            _err(
                errors,
                "accounting_and_contrast_completion reportable contrast requires all "
                "four paired seeds 1..4 exact treatment-minus-control must be true",
            )
        pre = acc.get("predeclared_contrasts", {})
        if not isinstance(pre, dict):
            _err(
                errors,
                "accounting_and_contrast_completion predeclared_contrasts missing or not dict",
            )
        else:
            e3a = pre.get("E3a_primary", {})
            if (
                not isinstance(e3a, dict)
                or e3a.get("id") != "p2c_dla-minus-per_task_dla"
                or "fixed_1x/state_age=0" not in str(e3a.get("for", ""))
            ):
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts E3a_primary must "
                    "be p2c_dla-minus-per_task_dla for offered deadline at fixed_1x/state_age=0",
                )
            if e3a.get("secondary") != "p2c_dla-minus-ingress_dla":
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts "
                    "E3a secondary must be p2c_dla-minus-ingress_dla",
                )
            e3b = pre.get("E3b_per_task_dla_state_age_0", {})
            if (
                not isinstance(e3b, dict)
                or set(e3b.get("each_of", []))
                != {"static_overprovisioned", "reactive", "proactive"}
                or e3b.get("minus") != "fixed_1x"
            ):
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts E3b each_of "
                    "must be static_overprovisioned/reactive/proactive minus fixed_1x",
                )
            if set(e3b.get("for_co_primary_family", [])) != {
                "offered deadline attainment",
                "rejection_share",
                "resource_unit_seconds",
            }:
                _err(
                    errors,
                    "accounting_and_contrast_completion "
                    "predeclared_contrasts E3b for_co_primary_family "
                    "must be offered deadline/rejection_share/resource_unit_seconds",
                )
            if (
                e3b.get("plus_proactive_minus_reactive_as_declared_diagnostic") is not True
                or e3b.get("no_scalar_best_objective") is not True
            ):
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts E3b must "
                    "have plus_proactive_minus_reactive diagnostic and no_scalar_best",
                )
            e3c = pre.get("E3c_at_each_state_age", {})
            if not isinstance(e3c, dict) or set(e3c.get("contrasts", [])) != {
                "p2c_dla-minus-per_task_dla under fixed_1x",
                "proactive-minus-reactive under per_task_dla",
            }:
                _err(
                    errors,
                    "accounting_and_contrast_completion "
                    "predeclared_contrasts E3c contrasts must be "
                    "p2c_dla-minus-per_task_dla under fixed_1x and "
                    "proactive-minus-reactive under per_task_dla",
                )
            if set(e3c.get("for", [])) != {
                "offered deadline attainment",
                "rejection_share",
                "resource_unit_seconds",
            }:
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts E3c for "
                    "must be offered deadline/rejection_share/resource_unit_seconds",
                )
            if e3c.get("plus_declared_imbalance_action_diagnostics") is not True:
                _err(
                    errors,
                    "accounting_and_contrast_completion predeclared_contrasts "
                    "E3c plus_declared_imbalance_action_diagnostics must be true",
                )
        if acc.get("draw_is_N_4_tasks_never_become_replicates") is not True:
            _err(
                errors,
                "accounting_and_contrast_completion "
                "draw_is_N_4_tasks_never_become_replicates must be true",
            )

    return {"pass": len(errors) == 0, "errors": errors, "error_count": len(errors)}


def render_markdown(data: dict[str, Any]) -> str:
    """Pure deterministic markdown from JSON fields only.

    No filesystem reads. Static headings fixed; scientific values from data.
    Output is fully determined by data.
    """

    def _get(path: list[str], default: object = "") -> object:
        cur: object = data
        for key in path:
            if isinstance(cur, dict):
                cur = cur.get(key, default)
            else:
                return default
        return cur if cur is not None else default

    def _s(val: object) -> str:
        return str(val) if val is not None else ""

    base_commit = _s(_get(["base_commit"], BASE_COMMIT))
    campaign = _s(_get(["campaign"], CAMPAIGN))
    version = _s(_get(["schema_version"], CONTRACT_VERSION))
    rq = _s(_get(["research_question"], ""))
    auth = _s(_get(["authority_note"], ""))

    fp_raw = _get(["frozen_prerequisites"], {})
    fp: dict[str, Any] = fp_raw if isinstance(fp_raw, dict) else {}
    e2b = fp.get("e2b", {}) if isinstance(fp.get("e2b"), dict) else {}
    e2c = fp.get("e2c", {}) if isinstance(fp.get("e2c"), dict) else {}
    e2d = fp.get("e2d", {}) if isinstance(fp.get("e2d"), dict) else {}
    actor = fp.get("actor", {}) if isinstance(fp.get("actor"), dict) else {}
    trace = fp.get("trace", {}) if isinstance(fp.get("trace"), dict) else {}
    eval_seed = fp.get("evaluator_seed", EXPECTED_EVALUATOR_SEED)

    rep_raw = _get(["replication"], {})
    rep: dict[str, Any] = rep_raw if isinstance(rep_raw, dict) else {}

    hyps_raw = _get(["hypotheses"], {})
    hyps: dict[str, Any] = hyps_raw if isinstance(hyps_raw, dict) else {}
    hyp_items = hyps.get("items", [])

    cs_raw = _get(["compute_scaling"], {})
    cs: dict[str, Any] = cs_raw if isinstance(cs_raw, dict) else {}
    reactive = cs.get("reactive", {})
    if not isinstance(reactive, dict):
        reactive = {}
    proactive = cs.get("proactive", {})
    if not isinstance(proactive, dict):
        proactive = {}
    dyn_bounds = cs.get("dynamic_bounds", {})
    if not isinstance(dyn_bounds, dict):
        dyn_bounds = {}
    fixed_1x = cs.get("fixed_1x", {})
    if not isinstance(fixed_1x, dict):
        fixed_1x = {}
    static_over = cs.get("static_overprovisioned", {})
    if not isinstance(static_over, dict):
        static_over = {}

    tm_raw = _get(["time_model"], {})
    tm: dict[str, Any] = tm_raw if isinstance(tm_raw, dict) else {}
    scen_raw = _get(["scenario"], {})
    scen: dict[str, Any] = scen_raw if isinstance(scen_raw, dict) else {}
    sd_raw = _get(["staged_design"], {})
    sd: dict[str, Any] = sd_raw if isinstance(sd_raw, dict) else {}
    inf_raw = _get(["inference"], {})
    inf: dict[str, Any] = inf_raw if isinstance(inf_raw, dict) else {}
    cost_raw = _get(["cost"], {})
    cost: dict[str, Any] = cost_raw if isinstance(cost_raw, dict) else {}
    ta_raw = _get(["task_accounting"], {})
    ta: dict[str, Any] = ta_raw if isinstance(ta_raw, dict) else {}
    cb_raw = _get(["claim_boundaries"], {})
    cb: dict[str, Any] = cb_raw if isinstance(cb_raw, dict) else {}
    ms_raw = _get(["mechanism_separation"], {})
    ms: dict[str, Any] = ms_raw if isinstance(ms_raw, dict) else {}
    pm_raw = _get(["p2c_mixer"], {})
    pm: dict[str, Any] = pm_raw if isinstance(pm_raw, dict) else {}
    fd = pm.get("field_declaration", {})
    if not isinstance(fd, dict):
        fd = {}
    fold = pm.get("fold", {})
    if not isinstance(fold, dict):
        fold = {}

    out: list[str] = []
    out.append("# E3 Dynamic Resource v2 — Scientific Contract v1")
    out.append("")
    out.append(f"**Campaign:** `{campaign}`")
    out.append(f"**Contract version:** `{version}`")
    out.append("**Status:** `predeclared_before_any_e3_trace_execution`")
    out.append("**Created:** `2026-08-13`")
    out.append(f"**Base commit (exact):** `{base_commit}`")
    out.append(f"**Lane:** `01` (`{BRANCH}`)")
    out.append("")
    out.append(
        "JSON is the single normative scientific contract "
        "(`e3_dynamic_resource_v2_contract_v1.json`). "
        "Markdown is a deterministic generated view via "
        "`render_markdown(data)` and must byte-equal its output; "
        "byte mismatch is authoritative."
    )
    if auth:
        out.append("")
        out.append(f"Authority note: {auth}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 1. Research question")
    out.append("")
    if rq:
        out.append(f"> {rq}")
        out.append("")
    out.append(
        "Three orthogonal control dimensions — placement, admission, "
        "scaling — are isolated. E3a isolates placement at fixed_1x, "
        "E3b holds placement fixed at per_task_dla for scaling "
        "contrasts, E3c tests selected stale-state contrasts "
        "(0/1000/3000 ms), without fully crossing every placement "
        "with every scaler."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 2. Frozen prerequisites and provenance")
    out.append("")
    out.append(f"- E2b commit: `{e2b.get('commit', EXPECTED_E2B)}`")
    out.append(f"- E2c commit: `{e2c.get('commit', EXPECTED_E2C)}`")
    out.append(f"- E2d commit: `{e2d.get('commit', EXPECTED_E2D)}`")
    out.append(f"- E2d manifest SHA-256: `{e2d.get('manifest_sha256', EXPECTED_E2D_MANIFEST)}`")
    out.append(f"- Actor path: `{actor.get('path', EXPECTED_ACTOR_PATH)}`")
    out.append(f"- Actor SHA-256: `{actor.get('sha256', EXPECTED_ACTOR_SHA)}`")
    out.append(f"- Trace path: `{trace.get('path', EXPECTED_TRACE_PATH)}`")
    out.append(f"- Trace SHA-256: `{trace.get('sha256', EXPECTED_TRACE_SHA)}`")
    out.append(f"- Evaluator seed: `{eval_seed}`")
    out.append(f"- Scenario: {scen.get('scenario', 'Manchester incident trace')}")
    scen_steps = scen.get("steps", 3600)
    scen_smoke = scen.get("smoke_steps", 10)
    out.append(f"- Steps: {scen_steps}; smoke steps: {scen_smoke}")
    scen_rsus = scen.get("rsus", 10)
    scen_width = scen.get("padded_fleet_width", 2488)
    out.append(f"- RSUs: {scen_rsus}; padded_fleet_width: {scen_width}")
    tm_tick = tm.get("outer_tick_ms", 1000)
    tm_slots = tm.get("within_tick_task_slots", 5)
    out.append(f"- Outer tick: {tm_tick} ms; task slots: {tm_slots}")
    tm_stale = tm.get("candidate_stale_levels_ms", [0, 1000, 3000])
    out.append(f"- Candidate stale levels: {tm_stale}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 3. Replication — fleet_draw via fleet_seed")
    out.append("")
    out.append(f"- Replication unit: `{rep.get('replication_unit', 'fleet_draw')}`")
    rep_key = rep.get("replication_key", "fleet_seed")
    out.append(f"- Replication key: `{rep_key}` (integer 1..4)")
    out.append(f"- N: `{rep.get('n', 4)}` fleet draws (tasks are not replicates)")
    out.append(f"- Fleet seeds: `{rep.get('fleet_seeds', [1, 2, 3, 4])}`")
    out.append(f"- Note: {rep.get('fleet_draw_note', 'padded-slot assignment')}")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 4. Hypotheses H1–H5 (hypothesis_not_expected_truth)")
    out.append("")
    out.append("All hypotheses have status `hypothesis_not_expected_truth` and kind `hypothesis`;")
    out.append("negative, null, or opposite results are acceptable and remain valid.")
    out.append("")
    if isinstance(hyp_items, list):
        for item in hyp_items:
            if isinstance(item, dict):
                hid = item.get("id", "")
                stmt = item.get("statement", "")
                status = item.get("status", "hypothesis_not_expected_truth")
                out.append(f"- **{hid}** `{status}` — {stmt}")
    out.append("")
    out.append(
        "H1: P2C may approach per_task_dla with less global inspection; "
        "H2: reactive may improve with churn;"
    )
    out.append(
        "H3: proactive may help when load change outruns actuation; "
        "H4: per_task_dla may degrade faster than P2C under stale state;"
    )
    out.append(
        "H5: additional compute (static_overprovisioned) may not win "
        "once resource_unit_seconds is considered."
    )
    out.append("Hypotheses are not expected truths; negative results acceptable.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 5. Mechanism separation")
    out.append("")
    out.append("| Mechanism | Controls | Does not control |")
    out.append("|---|---|---|")
    ms_place = ms.get("placement", "which RSU executes admitted V2I task")
    out.append(f"| Placement | {ms_place} | admission; compute capacity |")
    ms_adm = ms.get("admission", "whether task admitted via deadline gate")
    out.append(f"| Admission | {ms_adm} | where it executes; compute capacity |")
    ms_scale = ms.get("scaling", "how many compute units active per RSU")
    out.append(f"| Scaling | {ms_scale} | which RSU chosen; admission decision |")
    out.append("")
    out.append(
        "- Queue ceiling is not compute capacity: "
        "queue_ceiling_is_not_compute_capacity must be true."
    )
    out.append("- Actor never observes RSU load and never selects execution RSU.")
    out.append("- Rejected work never executes.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 6. Placement — p2c_dla, ingress_dla, per_task_dla")
    out.append("")
    out.append("- Feasibility first; two distinct feasible candidates.")
    out.append(
        f"- Counter key fields: {EXPECTED_COUNTER_FIELDS} "
        "(stable counter-based key; no global RNG)."
    )
    fd_ordered = fd.get("fields_ordered", EXPECTED_COUNTER_FIELDS)
    out.append(f"- Field declaration ordered: {fd_ordered}")
    fold_order = fold.get("field_order", EXPECTED_COUNTER_FIELDS)
    out.append(f"- Fold field_order: {fold_order}")
    out.append(
        "- Inspect only pair; lower effective_busy_ms wins; "
        "tie by lowest RSU id; immediate reservation; "
        "one candidate per task; common target forbidden."
    )
    out.append(
        "- Stale: immutable delayed view; "
        "same_tick_reservation_overlay; no future leakage; "
        "exposes state_age_ms."
    )
    out.append(
        "- Pair mapper: sorted ascending unique feasible RSU IDs; "
        "SplitMix64 over ordered fields; final pair sorted."
    )
    out.append(
        "- Modulo bias note: modulo reduction has negligible bias "
        "not mathematically exact-uniform; H1 is pair-only ranking vs "
        "global least-busy dependence not statistical uniformity proof."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 7. Compute scaling")
    out.append("")
    f1_units = fixed_1x.get("active_units_per_rsu", 1)
    f1_mult = fixed_1x.get("multiplier", 1)
    f1_svc = fixed_1x.get("rsu_service_mult", 1.0)
    out.append(
        f"- fixed_1x: active_units_per_rsu={f1_units} "
        f"multiplier={f1_mult} rsu_service_mult={f1_svc}"
    )
    so_units = static_over.get("active_units_per_rsu", 3)
    so_mult = static_over.get("multiplier", 3)
    so_svc = static_over.get("rsu_service_mult", 3.0)
    out.append(
        f"- static_overprovisioned: active_units_per_rsu={so_units} "
        f"multiplier={so_mult} rsu_service_mult={so_svc} "
        "(fixed 3x compute, never queue capacity)"
    )
    db_min = dyn_bounds.get("min_units", 1)
    db_max = dyn_bounds.get("max_units", 3)
    db_delay = dyn_bounds.get("actuation_delay_ms", 2000)
    db_ticks = dyn_bounds.get("actuation_delay_ticks", 2)
    out.append(
        f"- Dynamic bounds: {db_min}--{db_max} units; "
        f"actuation_delay {db_delay} ms / {db_ticks} ticks; "
        "one level per action; one pending; apply due before tick; "
        "free_scaling_forbidden and unbounded_scaling_forbidden."
    )
    r_sig = reactive.get("signal", "service_workload_ms")
    r_units = reactive.get("signal_units", "work_ms_independent_of_capacity")
    r_up = reactive.get("scale_up_threshold_ms", 800)
    r_down = reactive.get("scale_down_threshold_ms", 200)
    r_gap = reactive.get("threshold_gap_ms", 600)
    r_cool = reactive.get("cooldown_ms", 5000)
    r_delay = reactive.get("actuation_delay_ms", 2000)
    out.append(
        f"- Reactive: signal {r_sig} ({r_units}) per RSU; "
        f"thresholds up >= {r_up} inclusive, down <= {r_down} inclusive; "
        f"gap {r_gap} is hysteresis; cooldown {r_cool} ms; "
        f"actuation {r_delay} ms; bounds 1..3; one level; one pending; "
        "stable inclusive edges; prediction false; state_age 0/1000/3000."
    )
    out.append("- Reactive signal units: work-ms, independent of capacity")
    p_formulas = proactive.get("formulas", {})
    if not isinstance(p_formulas, dict):
        p_formulas = {}
    older = p_formulas.get("older_mean", "mean(W[0:2])")
    recent = p_formulas.get("recent_mean", "mean(W[2:4])")
    trend = p_formulas.get("trend", "recent_mean - older_mean")
    forecast = p_formulas.get("forecast", "max(0, mean(W) + 2*trend)")
    out.append(
        f"- Proactive: transparent baseline, not optimal predictor; "
        f"signal arrival_work_ms per-RSU at 1000 ms ticks; "
        f"window 4 observations oldest_to_newest at 1000 ms; "
        f"warm_up 4 valid; formulas older_mean={older}, "
        f"recent_mean={recent}, trend={trend}, forecast={forecast}; "
        "horizon 2000 ms (2 ticks); same 800/200 thresholds gap 600 "
        "hysteresis inclusive; cooldown 5000; delay 2000; "
        "bounds 1..3; one level/pending; no future leakage."
    )
    out.append("- Hysteresis is gap (600) — no extra hysteresis_ms excursion beyond thresholds.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 8. Time model")
    out.append("")
    out.append(
        f"- outer_tick_ms: {tm.get('outer_tick_ms', 1000)} "
        "(1000 ms = 1 second, advances physical time)"
    )
    out.append(
        f"- within_tick_task_slots: {tm.get('within_tick_task_slots', 5)} "
        "(do NOT advance physical time)"
    )
    out.append(
        f"- state_age_unit: {tm.get('state_age_unit', 'integer_simulator_ms')} "
        "(signal snapshot age)"
    )
    tm_stale2 = tm.get("candidate_stale_levels_ms", [0, 1000, 3000])
    out.append(f"- candidate_stale_levels_ms: {tm_stale2}")
    cc_off = tm.get("control_clock_offset_ms", 3000)
    cc_pre = tm.get("prepopulate_control_times_ms", [0, 1000, 2000])
    out.append(
        f"- control_clock_offset_ms: {cc_off}; "
        f"prepopulate {cc_pre} with empty_initial_infrastructure_state; "
        "trace tick 0 maps to control 3000."
    )
    out.append(
        "- Stale 200ms is forbidden; stale levels are candidate values; "
        "permits exact 0/1000/3000 without clamping."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 9. Cost — resource_unit_seconds")
    out.append("")
    out.append(f"- Metric: `{cost.get('metric', 'resource_unit_seconds')}`")
    cost_form = cost.get("formula", "sum(active_compute_units * interval_seconds)")
    out.append(f"- Formula: `{cost_form}`")
    out.append(
        "- Monetary is false (never monetary): no currency, price, billing, USD, dollar claims."
    )
    out.append(
        "- Cost per RSU per tick: active_compute_units * 1 second; "
        "charged even when idle; at most one interval per RSU per tick."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 10. Task accounting")
    out.append("")
    ta_req = ta.get("required", [])
    out.append(f"- Required: {ta_req}")
    ul = ta.get("unavailable_lifecycle", {})
    if not isinstance(ul, dict):
        ul = {}
    out.append(
        f"- Unavailable lifecycle must remain null: "
        f"started={ul.get('started')}, "
        f"compute_completed={ul.get('compute_completed')}, "
        f"returned={ul.get('returned')}, dropped={ul.get('dropped')} "
        "(null means unmodelled not zero)."
    )
    out.append("- Forbidden to fabricate physical started/completed/returned lifecycle.")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 11. Compute-service semantics")
    out.append("")
    css_raw = _get(["compute_service_semantics"], {})
    css: dict[str, Any] = css_raw if isinstance(css_raw, dict) else {}
    css_enq = css.get("enqueue_equation", "enqueued_work_ms = raw_1x_service_work_ms")
    out.append(f"- Enqueue: {css_enq} (must not divide by capacity)")
    css_drain = css.get(
        "drain_equation",
        "drain_work_ms = min(backlog_work_ms, active_capacity_units * 1000)",
    )
    out.append(f"- Drain: {css_drain} per 1000 ms tick for all queued work")
    css_back = css.get(
        "backlog_equation",
        "backlog_work_ms[t+1] = backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms",
    )
    out.append(f"- Backlog: {css_back} (invariant baseline, work_ms storage)")
    css_res = css.get(
        "resource_time_equation",
        "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1",
    )
    out.append(f"- Resource time: {css_res} even when idle; at_most_one_interval")
    css_lat = css.get(
        "latency_equation",
        "(raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units",
    )
    out.append(
        f"- Latency: {css_lat} admission-time estimate not physical "
        "lifecycle; physical lifecycle fields remain null; not repriced."
    )
    out.append(
        "- Placement/admission/stale/reactive use raw_backlog_work_ms; "
        "proactive uses raw_admitted_arrival_work_ms; "
        "queue safety uses current occupancy plus same-tick reservations."
    )
    out.append(
        "- Scaling applied at tick start before placement/admission "
        "and before latency estimate/drain; active capacity for entire tick; "
        "reduces to E2d at fixed_1x."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 12. Stale decision vs true execution")
    out.append("")
    sdt_raw = _get(["stale_decision_vs_true_execution"], {})
    sdt: dict[str, Any] = sdt_raw if isinstance(sdt_raw, dict) else {}
    obs = sdt.get(
        "observed_decision_backlog_work_ms",
        "fresh_or_delayed_immutable_backlog_work_ms_plus_decision_overlay_"
        "plus_same_tick_reservation_overlay",
    )
    out.append(f"- observed_decision_backlog_work_ms: {obs}")
    true_b = sdt.get(
        "true_execution_backlog_work_ms",
        "current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU",
    )
    out.append(f"- true_execution_backlog_work_ms: {true_b}")
    out.append(
        "- optimistic stale admitted executes and may miss per true latency; "
        "pessimistic stale rejected never executes."
    )
    out.append(
        "- deadline_success is based on true simulated latency, "
        "never the controller's stale estimate."
    )
    out.append(
        "- not evidence of physical started/completed/returned lifecycle; "
        "do not retroactively reprice."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 13. Dense position and diagnostics")
    out.append("")
    out.append(
        "- Sequential task ordinal: task_slot * padded_fleet_width + "
        "vehicle_slot (dense position identity, independent of active mask; "
        "range [0,12439])."
    )
    out.append(
        "- Outer tick, task_slot, vehicle_slot, sequential_task_ordinal "
        "are all required counter key fields."
    )
    out.append(
        "- P2C mixer: field_declaration fields_ordered must equal "
        "fold field_order and equal expected counter fields; "
        "splitmix64 definition with wrap 2^64; fold h_init 0x6A09E667F3BCC909 "
        "for_each_ordered_field h=splitmix64(h xor uint64(field))."
    )
    out.append(
        "- Diagnostic coverage: feasibility_workload_checks, "
        "ranking_workload_inspections, unique_workload_values_observed; "
        "MUST NOT claim only two total global state reads or "
        "proven lower total state acquisition."
    )
    out.append(
        "- Resource diagnostics: drained_work_ms / "
        "(active_capacity_units * 1000 work_ms) bounded [0,1]; "
        "waiting-room occupancy is a separate task count; "
        "execution share is actual admitted V2I execution count / "
        "total admitted V2I execution count; when denominator is zero "
        "it is null with reason."
    )
    out.append(
        "- Target switching is counted over consecutive admitted V2I tasks "
        "in exact deterministic (outer_tick, task_slot, vehicle_slot) "
        "order; first admitted task is not a switch; "
        "resource_unit_seconds denominator stays required for diagnostic "
        "deadline per resource cost."
    )
    out.append(
        "- Pair-only ranking; H1 concern is pair-only inspection/"
        "global-state dependence not statistical uniformity proof."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 14. Staged design — candidate grid")
    out.append("")
    out.append(
        f"- stage_listed_cells: {sd.get('stage_listed_cells', 60)}; "
        f"maximum_candidate_unique_cells: "
        f"{sd.get('maximum_candidate_unique_cells', 56)}"
    )
    out.append(
        f"- Equations: stage_listed "
        f"{sd.get('stage_listed_equation', '12 + 16 + 32 = 60')}; "
        f"unique {sd.get('unique_equation', '12 + 12 + 32 = 56')}"
    )
    e3a = sd.get("e3a", {})
    if not isinstance(e3a, dict):
        e3a = {}
    e3b = sd.get("e3b", {})
    if not isinstance(e3b, dict):
        e3b = {}
    e3c = sd.get("e3c", {})
    if not isinstance(e3c, dict):
        e3c = {}
    e3a_place = e3a.get("placement", ["ingress_dla", "per_task_dla", "p2c_dla"])
    e3a_scale = e3a.get("scaling", ["fixed_1x"])
    e3a_stale = e3a.get("stale_ms", [0])
    e3a_cells = e3a.get("cells", 12)
    out.append(
        f"- E3a (isolates placement): {e3a_place} x {e3a_scale} x "
        f"staleness {e3a_stale} x 4 draws = {e3a_cells} cells"
    )
    e3b_place = e3b.get("placement", ["per_task_dla"])
    e3b_scale = e3b.get(
        "scaling",
        ["fixed_1x", "static_overprovisioned", "reactive", "proactive"],
    )
    e3b_stale = e3b.get("stale_ms", [0])
    e3b_cells = e3b.get("cells", 16)
    e3b_over = e3b.get("overlap_with_e3a", 4)
    e3b_add = e3b.get("unique_additional", 12)
    out.append(
        f"- E3b (holds per_task_dla, scaling contrasts): {e3b_place} x "
        f"{e3b_scale} x staleness {e3b_stale} x 4 draws = {e3b_cells} "
        f"stage-listed; overlap_with_e3a {e3b_over} reused not rerun; "
        f"unique_additional {e3b_add}"
    )
    e3c_obs = e3c.get("total_contrast_observations", 48)
    e3c_reused = e3c.get("fresh_observations_reused", 16)
    e3c_eq = e3c.get(
        "equation",
        "2 contrasts * 2 arms * 3 staleness * 4 draws = 48 observations; "
        "48 - 16 = 32 stale variants",
    )
    e3c_stale_eq = e3c.get("stale_variant_equation", "48 - 16 = 32")
    e3c_add = e3c.get("additional_stale_variant_cells_max", 32)
    out.append(
        f"- E3c (stale-state contrasts): {e3c_obs} total contrast "
        f"observations; {e3c_reused} fresh reused; "
        f"equation {e3c_eq} ; stale_variant {e3c_stale_eq} ; "
        f"additional stale variant cells max {e3c_add}"
    )
    sd_note = sd.get("note", "reused across stage summaries rather than rerun")
    out.append(f"- Note: {sd_note}")
    out.append("- E3c reuses identical fresh cells; not double-counted;")
    out.append("  depends_on fresh construct gates.")
    out.append(
        "- Maximum candidate is 56 unique cells (60 stage-listed): "
        "12 + 12 + 32 unique; 12 + 16 + 32 stage-listed."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 15. Inference")
    out.append("")
    inf_unit = inf.get("unit", "fleet_draw")
    inf_key = inf.get("key", "fleet_seed")
    inf_n = inf.get("n", 4)
    inf_seeds = inf.get("fleet_seeds", [1, 2, 3, 4])
    out.append(f"- Unit: {inf_unit} keyed by {inf_key} N={inf_n} seeds {inf_seeds}")
    inf_interval = inf.get(
        "interval",
        "95% Student-t; df=n-1=3; t_0.975,3=3.182; mean +- t*s/sqrt(n)",
    )
    out.append(f"- Interval: {inf_interval}")
    out.append(
        f"- Sample SD: {inf.get('sample_sd', 'Bessel n-1')}; SE: {inf.get('se', 's / sqrt(n)')}"
    )
    out.append(
        "- Paired differences per fleet_seed; reportable contrast "
        "requires all four paired seeds 1..4."
    )
    out.append(
        "- Forbidden: task_as_n, p_value_as_primary, "
        "citywide_generalisation, population_claim, "
        "equivalence_without_margin, seed_0_in_primary."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 16. Claim boundaries and limitations")
    out.append("")
    out.append(
        f"- Any post-observation source change requires successor: "
        f"{cb.get('any_post_observation_source_change_requires_successor', True)}"
    )
    out.append(
        f"- Monetary cost tested: "
        f"{cb.get('monetary_cost_tested', False)} "
        "(false — resource_unit_seconds only; not monetary)"
    )
    out.append(
        f"- Kubernetes orchestration tested: "
        f"{cb.get('kubernetes_orchestration_tested', False)}; "
        f"learned controller: {cb.get('learned_controller_tested', False)}; "
        f"Manchester-wide: {cb.get('manchester_wide_deployment_tested', False)}; "
        f"physical return: {cb.get('physical_result_return_tested', False)}"
    )
    out.append(
        "- Proactive is transparent baseline, not an optimal predictor; "
        "transparent baseline not optimal."
    )
    out.append(
        "- Work-ms, independent of capacity; optimistic stale admitted "
        "executes and may miss per true latency; pessimistic stale "
        "rejected never executes; deadline_success based on true "
        "simulated latency never stale estimate; not evidence of "
        "physical started/completed/returned; do not retroactively reprice."
    )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## 17. Validation and byte-equivalence")
    out.append("")
    out.append(
        "The entire Markdown bytes must equal "
        "`render_markdown(canonical_json)`. Any addition, deletion, "
        "or reordering outside the canonical block fails byte-equivalence. "
        "Validator compares supplied Markdown bytes with pure render; "
        "byte mismatch is authoritative."
    )
    out.append("")
    out.append("---")
    out.append("")
    canonical_block = (
        f"{CANONICAL_BLOCK_START}\n```json\n{_canonical_dump(data)}```\n{CANONICAL_BLOCK_END}"
    )
    out.append(canonical_block)
    out.append("")
    out.append(
        "*End of normative contract v1 — Markdown is generated view; JSON is authoritative.*"
    )
    out.append("")
    return "\n".join(out)


def validate_markdown(md_text: str, data: dict[str, Any]) -> list[str]:
    """Alias for validate_markdown_contains for backward compatibility."""
    return validate_markdown_contains(md_text, data)


def validate_markdown_contains(md_text: str, data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    # Whole-file byte-equivalence to deterministic render
    try:
        expected_md = render_markdown(data)
        if md_text != expected_md:
            errors.append(
                "markdown byte-equivalence to render_markdown failed "
                "(byte-equivalence mismatch is authoritative)"
            )
    except Exception as e:
        errors.append(f"render_markdown failed: {e}")
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
                except (TypeError, ValueError) as exc:
                    errors.append(f"canonical JSON block comparison failed: {exc}")
            # Check deterministic generation: raw must equal canonical dump
            expected_dump = _canonical_dump(data)
            # The raw block may have trailing newline differences;
            # normalize by parsing and re-dumping comparison already done.
            # For strict byte-equivalence, compare raw stripped vs
            # expected stripped.
            # Allow exactly expected_dump (which ends with newline) to
            # match raw + newline if needed.
            # We enforce that json.loads(raw) equals data and that
            # re-dumped canonical equals expected_dump.
            # If raw was generated deterministically, then raw should
            # equal expected_dump without extra whitespace variations.
            # Compare after stripping trailing newline for tolerance, but
            # require sort_keys and indent consistency.
            if raw.strip() != expected_dump.strip():
                # If not byte-identical, check if it's still semantically
                # equal but non-deterministic -> still error for
                # byte-equivalence.
                errors.append(
                    "canonical JSON block must be deterministic "
                    "generation (byte-equivalence to json.dumps "
                    "sort_keys indent=2)"
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
            errors.append(f"markdown missing {label}: {needle!r}")

    # Exact numeric checks with word boundaries:
    # 200,600,800,1000,2000,5000,3600,10,3,60,32,4
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
                f"markdown missing {label}: word-boundary {token!r} "
                f"not found (standalone {token} must appear, "
                "not as part of 2000/3600 etc)"
            )

    # Additional strict numeric: check that 200 appears as standalone
    # for threshold, not conflated with 2000; also ensure 600 appears
    # standalone
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
            errors.append(f"markdown missing {label}: {needle!r}")
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
            errors.append(f"markdown missing {label}: {needle!r}")
    # New normative distinctions — must be present in markdown prose
    new_distinction_checks = [
        ("observed_decision_backlog_work_ms", "observed_decision_backlog_work_ms in markdown"),
        ("true_execution_backlog_work_ms", "true_execution_backlog_work_ms in markdown"),
        ("optimistic stale", "optimistic stale in markdown"),
        ("pessimistic stale", "pessimistic stale in markdown"),
        (
            "deadline_success is based on true simulated latency",
            "deadline_success true latency in markdown",
        ),
        ("never the controller's stale estimate", "never stale estimate in markdown"),
        (
            "not evidence of physical started/completed/returned",
            "not physical lifecycle in markdown",
        ),
        ("do not retroactively reprice", "do not retroactively reprice in markdown"),
        ("outer_tick", "outer_tick in markdown"),
        ("task_slot", "task_slot in markdown"),
        ("vehicle_slot", "vehicle_slot in markdown"),
        ("sequential_task_ordinal", "sequential_task_ordinal in markdown"),
        ("task_slot * padded_fleet_width + vehicle_slot", "sequential ordinal formula in markdown"),
        ("[0,12439]", "[0,12439] range in markdown"),
        ("dense position identity", "dense position identity in markdown"),
        ("independent of active mask", "independent of active mask in markdown"),
        ("feasibility_workload_checks", "feasibility_workload_checks in markdown"),
        ("ranking_workload_inspections", "ranking_workload_inspections in markdown"),
        ("unique_workload_values_observed", "unique_workload_values_observed in markdown"),
        (
            "only two total global state reads",
            "only two total global reads phrase (must be negated) in markdown",
        ),
        (
            "proven lower total state acquisition",
            "proven lower total state acquisition in markdown",
        ),
        ("pair-only ranking", "pair-only ranking in markdown"),
        (
            "drained_work_ms / (active_capacity_units * 1000",
            "capacity-adjusted utilization formula in markdown",
        ),
        (
            "waiting-room occupancy is a separate task count",
            "waiting-room occupancy separate in markdown",
        ),
        ("actual admitted V2I execution count", "execution share formula in markdown"),
        ("when denominator is zero it is null", "execution share null when zero in markdown"),
        (
            "Target switching is counted over consecutive admitted V2I",
            "target switching deterministic order in markdown",
        ),
        ("first admitted task is not a switch", "first admitted not a switch in markdown"),
        (
            "resource_unit_seconds denominator stays required",
            "resource_unit_seconds denominator stays required in markdown",
        ),
    ]
    for needle, label in new_distinction_checks:
        if needle not in md_text:
            # For the "only two total..." phrase, we require it appears
            # negated (MUST NOT claim); check that the phrase exists with
            # MUST NOT nearby
            if (
                needle == "only two total global state reads"
                and "MUST NOT claim only two total" in md_text
            ):
                continue
            errors.append(f"markdown missing {label}: {needle!r}")
    rq_lines = [line for line in md_text.splitlines() if line.startswith(">")]
    rq_text = " ".join(rq_lines).lower()
    if "alone and jointly" in rq_text:
        errors.append("markdown research question quote must not contain 'alone and jointly'")
    if "alone and jointly" in md_text.lower() and "is removed" not in md_text.lower():
        # If the document still claims alone and jointly as positive, reject.
        # But if it only mentions removal, it's okay - already handled
        # above; this is additional check for outside RQ.
        # Only error if appears outside explanatory sentence.
        # Simple: if count of 'alone and jointly' >1 or not accompanied
        # by 'is removed' near, error already captured.
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
            "hypothesis->expected truth inverse claim "
            "(outside normative 'not expected truth' context)",
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
            # Simplest: split and keep only before marker for
            # inverse checks; re-add after for other checks?
            # We'll keep only text before first excluded marker for
            # inverse checks
            inverse_check_text = parts[0]
            break
    narrative_part = inverse_check_text
    lower_without = narrative_part.lower()
    lower_without = narrative_part.lower()

    def _has_positive_claim(hay: str, phrase: str) -> bool:
        # Sentence-level negation check: if sentence containing phrase
        # has a negation word, it's documenting forbidden, not asserting
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
                    # Sentence already negated
                    # (e.g., "never results, conclusions, or expected truths")
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
                # $ outside canonical block is forbidden unless
                # explicitly in allowed phrase (none)
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
        # Special handling for phrases that baseline contains negated:
        # check positive claim only
        # For generic inverse phrases, use positive claim helper
        # For phrases like "queue==compute", "actor observes", etc,
        # baseline has negated form, so helper will skip them
        # But if someone mutates to positive form (removing negation),
        # helper will detect
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
        # For remaining phrases like price/billing, they appear negated
        # in baseline as "no price", "no billing"
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
    # Default behavior: always validate both JSON and Markdown and byte-equivalence.
    # The deprecated --check-equivalence flag is retained for compatibility but does not gate
    # validation.
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

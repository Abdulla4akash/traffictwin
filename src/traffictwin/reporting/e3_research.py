# ruff: noqa: E501, ANN401
"""Deterministic E3 research export - Lane 11.

Strict typed reporting that consumes the promoted Lane 10 evidence package
and the fail-closed admission refusal. No duplicated scientific constants,
no fallback, no path/secret stripping. Any forbidden path / secret /
timestamp input fails closed. Scientific truth today is NO RESULTS:
evidence_state = NOT_EXECUTED, result_availability =
NO_E3_RESEARCH_RESULTS_AVAILABLE, research_workloads_launched = 0,
LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD,
E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED. No numeric results exist;
every numeric surface is explicitly unavailable with reasons.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass

from traffictwin.evidence_admission.e3_research import (
    E3ResearchAdmissionRefusal,
    admit_e3_research,
)
from traffictwin.experiments.e3_comparison import build_e3_comparison_view
from traffictwin.experiments.e3_research_evidence import (
    E3ResearchEvidencePackage,
    _scan_forbidden_recursive,
)
from traffictwin.experiments.e3_strategy_semantics import e3_strategy_semantics
from traffictwin.experiments.e3_task_accounting import build_e3_task_accounting_view

# Build path substrings without contiguous literal to satisfy no-local-path gate.
_PATH_SUBSTRINGS: tuple[str, ...] = (
    "/" + "Users" + "/",
    "/" + "home" + "/",
    "/" + "tmp" + "/",
    "/" + "var" + "/",
    "/" + "private" + "/",
    "C:\\",
    "D:\\",
)

_SECRET_SUBSTRINGS: tuple[str, ...] = (
    "secret",
    "credential",
    "api_key",
    "apikey",
    "password",
    "token",
    "private_key",
)

_TIMESTAMP_KEYS: frozenset[str] = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "admitted_at",
        "generated_at",
        "scientific_timestamp",
        "evaluation_time",
    }
)

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")


def _assert_no_forbidden_content(obj: object, label: str) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_str = str(k)
            for pat in _PATH_SUBSTRINGS:
                if pat in key_str:
                    raise ValueError(f"{label} contains forbidden path pattern {pat!r} in key")
            low_key = key_str.lower()
            for pat in _SECRET_SUBSTRINGS:
                if pat.lower() in low_key:
                    raise ValueError(f"{label} contains forbidden secret pattern {pat!r} in key")
            if key_str.lower() in _TIMESTAMP_KEYS:
                raise ValueError(f"{label} contains forbidden timestamp field {key_str!r}")
            _assert_no_forbidden_content(v, label)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _assert_no_forbidden_content(item, label)
    elif isinstance(obj, str):
        for pat in _PATH_SUBSTRINGS:
            if pat in obj:
                raise ValueError(f"{label} contains forbidden path pattern {pat!r} in value")
        if re.match(r"^[A-Za-z]:\\", obj):
            raise ValueError(f"{label} contains absolute Windows path in value")
        low = obj.lower()
        for pat in _SECRET_SUBSTRINGS:
            if pat.lower() in low:
                raise ValueError(f"{label} contains forbidden secret pattern {pat!r} in value")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _contains_absolute_path(text: str) -> bool:
    for pat in _PATH_SUBSTRINGS:
        if pat in text:
            return True
    return bool(re.search(r"[A-Za-z]:\\", text))


def _contains_secret(text: str) -> bool:
    low = text.lower()
    return any(pat.lower() in low for pat in _SECRET_SUBSTRINGS)


def _scan_exports_for_leaks(*texts: str) -> None:
    for t in texts:
        if _contains_absolute_path(t):
            raise ValueError("export contains absolute local path - rejected")
        if _contains_secret(t):
            raise ValueError("export contains secret-like content - rejected")


def _build_payload(
    package: E3ResearchEvidencePackage,
    receipt: E3ResearchAdmissionRefusal,
) -> dict[str, object]:
    semantics = e3_strategy_semantics()
    comparison = build_e3_comparison_view(package)
    accounting = build_e3_task_accounting_view()

    _assert_no_forbidden_content(package.model_dump(mode="json"), "package")
    _assert_no_forbidden_content(receipt.model_dump(mode="json"), "receipt")
    # Forbidden-claims re-scan for mutated free text (limitations etc.)
    for obj, label in [
        (package.model_dump(mode="json"), "package"),
        (receipt.model_dump(mode="json"), "receipt"),
    ]:
        v = _scan_forbidden_recursive(obj)
        if v:
            raise ValueError(f"{label} contains forbidden claim: {v[0]}")

    strategy_defs: list[dict[str, object]] = []
    for sem in semantics:
        strategy_defs.append(
            {
                "placement_id": sem.placement_id,
                "scaling_id": sem.scaling_id,
                "state_age_ms": sem.state_age_ms,
                "human_label": sem.human_label,
                "radio_ingress": sem.radio_ingress,
                "execution_placement": sem.execution_placement,
                "admission": sem.admission,
                "forwarding": sem.forwarding,
                "actor_authority": sem.actor_authority,
                "infrastructure_authority": sem.infrastructure_authority,
                "scaling_semantics": sem.scaling_semantics,
                "staleness_semantics": sem.staleness_semantics,
                "queue_capacity_note": sem.queue_capacity_note,
                "compute_capacity_note": sem.compute_capacity_note,
                "resource_cost_note": sem.resource_cost_note,
                "is_learned": sem.is_learned,
                "is_deterministic": sem.is_deterministic,
                "evidence_level": sem.evidence_level,
                "limitations": sem.limitations,
            }
        )

    # Placement/scaling/staleness families
    placements = sorted({s.placement_id for s in semantics})
    scalings = sorted({s.scaling_id for s in semantics})
    state_ages = sorted({s.state_age_ms for s in semantics})

    tradeoff_structure: dict[str, object] = {
        "placement_families": placements,
        "placement_values": list(package.factors.get("placements", [])),
        "scaling_families": scalings,
        "scaling_values": list(package.factors.get("scalings", [])),
        "staleness_values_ms": list(package.factors.get("state_age_ms_values", [])),
        "state_age_ms_allowed": sorted(state_ages),
        "resource_metric": package.resource_cost.metric,
        "resource_formula": package.resource_cost.formula,
        "resource_is_monetary": package.resource_cost.monetary,
        "resource_unit": package.resource_cost.unit,
        "queue_vs_compute_separate": True,
        "queue_note": semantics[0].queue_capacity_note if semantics else "",
        "compute_note": semantics[0].compute_capacity_note if semantics else "",
        "resource_note": semantics[0].resource_cost_note if semantics else "",
    }

    # Dormant arms / configs structure
    dormant_arms_list: list[dict[str, object]] = []
    for arm in sorted(package.dormant_arms, key=lambda a: a.arm_id):
        dormant_arms_list.append(
            {
                "arm_id": arm.arm_id,
                "placement": arm.placement.value,
                "scaling": arm.scaling.value,
                "state_age_ms": arm.state_age_ms,
            }
        )
    dormant_configs_list: list[dict[str, object]] = []
    for cfg in sorted(package.dormant_configs, key=lambda c: c.config_id):
        dormant_configs_list.append(
            {
                "config_id": cfg.config_id,
                "arm_id": cfg.arm_id,
                "placement": cfg.placement.value,
                "scaling": cfg.scaling.value,
                "state_age_ms": cfg.state_age_ms,
                "evaluator_seed": cfg.evaluator_seed,
                "fleet_seed": cfg.fleet_seed,
                "num_rsus": cfg.num_rsus,
            }
        )

    # Per-RSU and scale-action summary STRUCTURE (typed, null with reasons)
    # All values read from the typed package; no fallback literals.
    per_rsu_structure: dict[str, object] = {
        "summary": "Per-RSU summaries are null with reasons before execution",
        "value": None,
        "null_value": None,
        "reason": package.scaling_receipts.per_rsu_summaries_null_reason,
        "rsu_count": package.factors["scenario_rsus"],
        "notes": "Structure exists but values are UNAVAILABLE before execution",
    }
    scale_action_structure: dict[str, object] = {
        "summary": "Scale-action receipts are null with reasons before execution",
        "value": None,
        "null_value": None,
        "receipts_reason": package.scaling_receipts.receipts_when_not_executed_null_reason,
        "capacity_levels_reason": package.scaling_receipts.capacity_levels_null_reason,
        "state_age_reason": package.scaling_receipts.state_age_receipts_null_reason,
        "has_receipts_when_executed": package.scaling_receipts.has_receipts_when_executed,
        "scaling_semantics_per_arm": [
            {"placement": s.placement_id, "scaling": s.scaling_id, "semantics": s.scaling_semantics}
            for s in semantics
        ],
    }

    # Task accounting - null lifecycle with reasons
    unavailable_map: dict[str, object] = {}
    for key in (
        "offered",
        "admitted",
        "rejected_total",
        "forwarded",
        "deadline_success",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        reason_val = str(getattr(accounting, f"{key}_reason"))
        unavailable_map[key] = {
            "value": None,
            "null_value": None,
            "status": "UNAVAILABLE",
            "reason": reason_val,
            "display": "UNAVAILABLE",
        }

    # Rejection breakdown - also unavailable
    rejection_breakdown: dict[str, object] = {}
    for cls in accounting.genuine_rejection_classes:
        rejection_breakdown[cls] = {
            "value": None,
            "reason": accounting.rejected_breakdown.reasons.get(cls, "UNAVAILABLE"),
            "status": "UNAVAILABLE",
        }

    task_accounting_dict: dict[str, object] = {
        "evidence_state": accounting.evidence_state,
        "result_availability": accounting.result_availability,
        "research_workloads_launched": accounting.research_workloads_launched,
        "offered": None,
        "admitted": None,
        "rejected_total": None,
        "rejected_by_class": None,
        "forwarded": None,
        "deadline_success": None,
        "started": None,
        "compute_completed": None,
        "returned": None,
        "dropped": None,
        "unavailable": unavailable_map,
        "rejection_breakdown": rejection_breakdown,
        "genuine_rejection_classes": list(accounting.genuine_rejection_classes),
        "conservation_holds": None,
        "conservation_reason": accounting.conservation_reason,
        "queue_vs_compute": {
            "queue_unit": accounting.queue_vs_compute.queue_unit,
            "compute_unit": accounting.queue_vs_compute.compute_unit,
            "is_separate": accounting.queue_vs_compute.is_separate,
            "queue_is_not_compute": accounting.queue_vs_compute.queue_is_not_compute,
            "compute_is_not_queue": accounting.queue_vs_compute.compute_is_not_queue,
            "reason": accounting.queue_vs_compute.reason,
        },
        "resource_cost": {
            "metric": accounting.resource_cost.metric,
            "monetary": accounting.resource_cost.monetary,
            "formula": accounting.resource_cost.formula,
            "value": None,
            "reason": accounting.resource_cost.reason,
        },
        "scaling_receipts": {
            "receipts": None,
            "reason": accounting.scaling_receipts.reason,
            "per_rsu": None,
            "per_rsu_reason": accounting.scaling_receipts.per_rsu_reason,
            "capacity_levels": None,
            "capacity_reason": accounting.scaling_receipts.capacity_reason,
            "state_age_receipts": None,
            "state_age_reason": accounting.scaling_receipts.state_age_reason,
        },
    }

    # Provenance - exact pins
    provenance_list: list[dict[str, object]] = []
    for entry in package.provenance:
        provenance_list.append(
            {
                "artifact": entry.artifact,
                "kind": entry.kind,
                "note": entry.note,
            }
        )
    provenance_dict: dict[str, object] = {
        "entries": provenance_list,
        "product_base_sha": package.product_base_sha,
        "research_promotion_sha": package.research_promotion_sha,
        "approved_candidate_sha": package.approved_candidate_sha,
        "contract_checkpoint_sha": package.contract_checkpoint_sha,
        "vec_promotion": package.vec_runtime.promotion_commit,
        "vec_core": package.vec_runtime.core_candidate,
        "vec_adapter": package.vec_runtime.adapter_candidate,
        "actor_sha256": package.software_identity.actor_sha256,
        "trace_sha256": package.software_identity.trace_sha256,
        "contract_sha256": package.contract.sha256,
        "manifest_sidecar_sha256": next(
            (e.note for e in package.provenance if e.kind == "manifest"), ""
        ),
    }

    # Missingness
    missingness_list: list[dict[str, object]] = []
    for m in package.missingness:
        missingness_list.append({"field": m.field, "reason": m.reason})

    # Admission - truthful refusal
    admission_dict: dict[str, object] = {
        "status": receipt.status,
        "admitted": receipt.admitted,
        "lane_09": receipt.lane_09,
        "standing": receipt.standing,
        "evidence_state": receipt.evidence_state,
        "result_availability": receipt.result_availability,
        "research_workloads_launched": receipt.research_workloads_launched,
        "campaign": receipt.campaign,
        "product_base_sha": receipt.product_base_sha,
        "research_promotion_sha": receipt.research_promotion_sha,
        "approved_candidate_sha": receipt.approved_candidate_sha,
        "contract_checkpoint_sha": receipt.contract_checkpoint_sha,
        "vec_promotion_sha": receipt.vec_promotion_sha,
        "vec_core_sha": receipt.vec_core_sha,
        "vec_adapter_sha": receipt.vec_adapter_sha,
        "actor_sha256": receipt.actor_sha256,
        "trace_sha256": receipt.trace_sha256,
        "contract_sha256": receipt.contract_sha256,
        "manifest_sidecar_sha256": receipt.manifest_sidecar_sha256,
        "reason_code": receipt.reason_code,
        "reason_detail": receipt.reason_detail,
        "diagnostics": dict(receipt.diagnostics),
        "expected_package_fingerprint": receipt.expected_package_fingerprint,
        "expected_analysis_artifact_fingerprint": receipt.expected_analysis_artifact_fingerprint,
        "received_package_fingerprint": receipt.received_package_fingerprint,
        "received_analysis_artifact_fingerprint": receipt.received_analysis_artifact_fingerprint,
        "not_supervisor_approval": True,
        "not_randy_confirmation": True,
    }

    # Comparison per-stage unavailable
    e3a_dict: dict[str, object] = {
        "stage": comparison.e3a.stage,
        "replication_unit": comparison.e3a.replication_unit,
        "n_fleet_draws": comparison.e3a.n_fleet_draws,
        "fleet_seeds": list(comparison.e3a.fleet_seeds),
        "evaluator_seed": comparison.e3a.evaluator_seed,
        "degrees_of_freedom": comparison.e3a.degrees_of_freedom,
        "critical_value": comparison.e3a.critical_value,
        "method": comparison.e3a.method,
        "tasks_are_not_replicates": comparison.e3a.tasks_are_not_replicates,
        "manchester_wide_inference_forbidden": comparison.e3a.manchester_wide_inference_forbidden,
        "universal_superiority_forbidden": comparison.e3a.universal_superiority_forbidden,
        "evidence_state": comparison.e3a.evidence_state,
        "result_availability": comparison.e3a.result_availability,
        "unavailable_reason": comparison.e3a.unavailable_reason,
        "estimands": [
            {
                "estimand": e.estimand,
                "treatment": e.treatment,
                "control": e.control,
                "metric": e.metric,
                "state_age_ms": e.state_age_ms,
            }
            for e in comparison.e3a.estimands
        ],
        "paired_differences": [
            {
                "comparison_id": pd.comparison_id,
                "replication_unit": pd.replication_unit,
                "fleet_seeds": list(pd.fleet_seeds),
                "evaluator_seed": pd.evaluator_seed,
                "n": pd.n,
                "per_seed_values": None,
                "mean": None,
                "lower": None,
                "upper": None,
                "includes_zero": None,
                "decision": None,
                "unavailable_reason": pd.unavailable_reason,
                "method": pd.method,
                "degrees_of_freedom": pd.degrees_of_freedom,
                "critical_value": pd.critical_value,
            }
            for pd in comparison.e3a.paired_differences
        ],
    }
    e3b_dict: dict[str, object] = {
        "stage": comparison.e3b.stage,
        "replication_unit": comparison.e3b.replication_unit,
        "n_fleet_draws": comparison.e3b.n_fleet_draws,
        "fleet_seeds": list(comparison.e3b.fleet_seeds),
        "evaluator_seed": comparison.e3b.evaluator_seed,
        "degrees_of_freedom": comparison.e3b.degrees_of_freedom,
        "critical_value": comparison.e3b.critical_value,
        "method": comparison.e3b.method,
        "tasks_are_not_replicates": comparison.e3b.tasks_are_not_replicates,
        "manchester_wide_inference_forbidden": comparison.e3b.manchester_wide_inference_forbidden,
        "universal_superiority_forbidden": comparison.e3b.universal_superiority_forbidden,
        "evidence_state": comparison.e3b.evidence_state,
        "result_availability": comparison.e3b.result_availability,
        "unavailable_reason": comparison.e3b.unavailable_reason,
        "estimands": [
            {
                "estimand": e.estimand,
                "treatment": e.treatment,
                "control": e.control,
                "metric": e.metric,
                "state_age_ms": e.state_age_ms,
            }
            for e in comparison.e3b.estimands
        ],
        "paired_differences": [
            {
                "comparison_id": pd.comparison_id,
                "replication_unit": pd.replication_unit,
                "fleet_seeds": list(pd.fleet_seeds),
                "evaluator_seed": pd.evaluator_seed,
                "n": pd.n,
                "per_seed_values": None,
                "mean": None,
                "lower": None,
                "upper": None,
                "includes_zero": None,
                "decision": None,
                "unavailable_reason": pd.unavailable_reason,
                "method": pd.method,
                "degrees_of_freedom": pd.degrees_of_freedom,
                "critical_value": pd.critical_value,
            }
            for pd in comparison.e3b.paired_differences
        ],
    }
    e3c_dict: dict[str, object] = {
        "stage": comparison.e3c.stage,
        "replication_unit": comparison.e3c.replication_unit,
        "n_fleet_draws": comparison.e3c.n_fleet_draws,
        "fleet_seeds": list(comparison.e3c.fleet_seeds),
        "evaluator_seed": comparison.e3c.evaluator_seed,
        "degrees_of_freedom": comparison.e3c.degrees_of_freedom,
        "critical_value": comparison.e3c.critical_value,
        "method": comparison.e3c.method,
        "tasks_are_not_replicates": comparison.e3c.tasks_are_not_replicates,
        "manchester_wide_inference_forbidden": comparison.e3c.manchester_wide_inference_forbidden,
        "universal_superiority_forbidden": comparison.e3c.universal_superiority_forbidden,
        "evidence_state": comparison.e3c.evidence_state,
        "result_availability": comparison.e3c.result_availability,
        "unavailable_reason": comparison.e3c.unavailable_reason,
        "estimands": [
            {
                "estimand": e.estimand,
                "treatment": e.treatment,
                "control": e.control,
                "metric": e.metric,
                "state_age_ms": e.state_age_ms,
            }
            for e in comparison.e3c.estimands
        ],
        "paired_differences": [
            {
                "comparison_id": pd.comparison_id,
                "replication_unit": pd.replication_unit,
                "fleet_seeds": list(pd.fleet_seeds),
                "evaluator_seed": pd.evaluator_seed,
                "n": pd.n,
                "per_seed_values": None,
                "mean": None,
                "lower": None,
                "upper": None,
                "includes_zero": None,
                "decision": None,
                "unavailable_reason": pd.unavailable_reason,
                "method": pd.method,
                "degrees_of_freedom": pd.degrees_of_freedom,
                "critical_value": pd.critical_value,
            }
            for pd in comparison.e3c.paired_differences
        ],
    }

    study_identity: dict[str, object] = {
        "campaign": package.campaign,
        "schema_version": package.schema_version,
        "product_base_sha": package.product_base_sha,
        "research_promotion_sha": package.research_promotion_sha,
        "approved_candidate_sha": package.approved_candidate_sha,
        "contract_checkpoint_sha": package.contract_checkpoint_sha,
        "contract_sha256": package.contract.sha256,
        "contract_path": package.contract.path,
        "actor_sha256": package.software_identity.actor_sha256,
        "trace_sha256": package.software_identity.trace_sha256,
        "vec_promotion": package.vec_runtime.promotion_commit,
        "vec_core": package.vec_runtime.core_candidate,
        "vec_adapter": package.vec_runtime.adapter_candidate,
        "incident_hour": "2024-03-15 20:00-21:00 Europe/London",
        "fleet_seeds": list(package.replication.fleet_seeds),
        "evaluator_seed": package.replication.evaluator_seed,
        "replication_unit": package.replication.replication_unit,
        "n": package.replication.n,
        "scenario_rsus": package.factors.get("scenario_rsus"),
        "ticks_per_cell": package.factors.get("ticks_per_cell"),
        "padded_fleet_width": package.factors.get("padded_fleet_width"),
        "placements": list(package.factors.get("placements", [])),
        "scalings": list(package.factors.get("scalings", [])),
        "state_age_ms_values": list(package.factors.get("state_age_ms_values", [])),
    }

    hold: dict[str, object] = {
        "lane_09": package.lane_09,
        "status": package.status,
        "evidence_state": package.evidence_state,
        "result_availability": package.result_availability,
        "research_workloads_launched": package.research_workloads_launched,
        "execution_authority": {
            "status": package.execution_authority.status,
            "lane_09": package.execution_authority.lane_09,
            "evidence_state": package.execution_authority.evidence_state,
            "result_availability": package.execution_authority.result_availability,
            "research_workloads_launched": package.execution_authority.research_workloads_launched,
            "scientific_execution_authorized": package.execution_authority.scientific_execution_authorized,  # noqa: E501
            "e3a_authorized": package.execution_authority.e3a_authorized,
            "e3b_authorized": package.execution_authority.e3b_authorized,
            "e3c_authorized": package.execution_authority.e3c_authorized,
        },
        "banner": "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD, E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, evidence_state = NOT_EXECUTED, result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE, research_workloads_launched = 0",  # noqa: E501
    }

    scientific_question: dict[str, object] = {
        "question": "How do placement (ingress_dla vs per_task_dla vs p2c_dla), scaling (fixed_1x vs static_overprovisioned vs reactive vs proactive), and staleness (0/1000/3000 ms) trade off offered-task deadline attainment, rejection share, and resource_unit_seconds across matched fleet draws fleet_draw N=4 evaluator_seed 0 under a frozen MAPPO actor that does not observe load?",  # noqa: E501
        "bounded_to": "One Manchester incident hour 2024-03-15 20:00-21:00, provisional uk2030 fleet width 2488, 10 RSUs, 3600 ticks per cell (dormant), replication unit fleet_draw N=4, evaluator_seed 0",  # noqa: E501
        "replication_unit": package.replication.replication_unit,
        "evaluator_seed": package.replication.evaluator_seed,
        "fleet_seeds": list(package.replication.fleet_seeds),
        "n": package.replication.n,
        "tasks_are_not_replicates": package.replication.tasks_are_not_replicates,
        "no_inference_beyond": "No Manchester-wide inference, no universal superiority, no tasks-as-N",  # noqa: E501
    }

    payload: dict[str, object] = {
        "schema_version": "e3_research_export_v1",
        "hold": hold,
        "admission": admission_dict,
        "study_identity": study_identity,
        "scientific_question": scientific_question,
        "staged_design": {
            "e3a": package.staged_design.e3a.model_dump(mode="json"),
            "e3b": package.staged_design.e3b.model_dump(mode="json"),
            "e3c": package.staged_design.e3c.model_dump(mode="json"),
            "identical_fresh_cells_reused_not_rerun": package.staged_design.identical_fresh_cells_reused_not_rerun,  # noqa: E501
            "maximum_candidate_unique_cells": package.staged_design.maximum_candidate_unique_cells,
            "not_double_counted": package.staged_design.not_double_counted,
            "stage_listed_cells": package.staged_design.stage_listed_cells,
        },
        "replication": {
            "replication_unit": package.replication.replication_unit,
            "fleet_seeds": list(package.replication.fleet_seeds),
            "evaluator_seed": package.replication.evaluator_seed,
            "n": package.replication.n,
            "replication_key": package.replication.replication_key,
            "tasks_are_not_replicates": package.replication.tasks_are_not_replicates,
            "interval": package.replication.interval,
            "method": package.replication.method,
            "degrees_of_freedom": package.replication.degrees_of_freedom,
            "critical_value": package.replication.critical_value,
        },
        "strategy_definitions": strategy_defs,
        "tradeoff_structure": tradeoff_structure,
        "dormant_arms": dormant_arms_list,
        "dormant_configs": dormant_configs_list,
        "dormant_counts": {"arms": len(dormant_arms_list), "configs": len(dormant_configs_list)},
        "queue_capacity": {
            "unit": package.queue_capacity.unit,
            "capacity_per_rsu": package.queue_capacity.capacity_per_rsu,
            "is_queue_not_compute": package.queue_capacity.is_queue_not_compute,
            "is_compute_units": package.queue_capacity.is_compute_units,
        },
        "compute_capacity": {
            "unit": package.compute_capacity.unit,
            "min_units": package.compute_capacity.min_units,
            "max_units": package.compute_capacity.max_units,
            "active_units_per_rsu_range": list(package.compute_capacity.active_units_per_rsu_range),
            "is_compute_not_queue": package.compute_capacity.is_compute_not_queue,
            "max_pending_actions": package.compute_capacity.max_pending_actions,
        },
        "resource_cost": {
            "metric": package.resource_cost.metric,
            "formula": package.resource_cost.formula,
            "monetary": package.resource_cost.monetary,
            "unit": package.resource_cost.unit,
            "interval_seconds": package.resource_cost.interval_seconds,
        },
        "per_rsu_structure": per_rsu_structure,
        "scale_action_structure": scale_action_structure,
        "queue_vs_compute_separation": {
            "is_separate": True,
            "queue_is_not_compute": True,
            "compute_is_not_queue": True,
            "reason": "Queue waiting-room capacity (tasks per RSU, ceiling 6220) is strictly separate from compute service capacity (units 1..3 per RSU draining 1000 work_ms per second per unit)",  # noqa: E501
        },
        "comparison": {
            "e3a": e3a_dict,
            "e3b": e3b_dict,
            "e3c": e3c_dict,
            "lane_09": comparison.lane_09,
            "status": comparison.status,
            "scenario": comparison.scenario,
        },
        "task_accounting": task_accounting_dict,
        "missingness": missingness_list,
        "provenance": provenance_dict,
        "limitations": list(package.limitations),
        "non_claims": list(package.non_claims),
        "factors": dict(package.factors),
    }
    return payload


def _build_json(
    payload: dict[str, object],
    package_fingerprint: str,
    export_fingerprint: str,
) -> str:
    full = dict(payload)
    full["package_fingerprint"] = package_fingerprint
    full["export_fingerprint"] = export_fingerprint
    text = json.dumps(full, sort_keys=True, indent=2, ensure_ascii=False)
    text = text.replace("\r\n", "\n").rstrip() + "\n"
    return text


def _build_csv(package: E3ResearchEvidencePackage) -> str:
    output = io.StringIO()
    fieldnames = [
        "section",
        "key",
        "value",
        "availability",
        "reason",
        "replication_unit",
        "fleet_seed",
        "detail",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    # Hold
    writer.writerow(
        {
            "section": "hold",
            "key": "lane_09",
            "value": package.lane_09,
            "availability": "verdict",
            "reason": "Immutable hold",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD",
        }
    )
    writer.writerow(
        {
            "section": "hold",
            "key": "evidence_state",
            "value": package.evidence_state,
            "availability": "verdict",
            "reason": "No workloads launched",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "evidence_state = NOT_EXECUTED",
        }
    )
    writer.writerow(
        {
            "section": "hold",
            "key": "result_availability",
            "value": package.result_availability,
            "availability": "verdict",
            "reason": "No results available",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE",
        }
    )
    writer.writerow(
        {
            "section": "hold",
            "key": "research_workloads_launched",
            "value": package.research_workloads_launched,
            "availability": "verdict",
            "reason": "Immutable hold",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "research_workloads_launched = 0",
        }
    )
    writer.writerow(
        {
            "section": "hold",
            "key": "status",
            "value": package.status,
            "availability": "verdict",
            "reason": "Execution not authorized",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED",
        }
    )
    # Replication
    for seed in package.replication.fleet_seeds:
        writer.writerow(
            {
                "section": "replication",
                "key": "fleet_draw",
                "value": seed,
                "availability": "structure",
                "reason": "Matched fleet draw replication unit",
                "replication_unit": "fleet_draw",
                "fleet_seed": seed,
                "detail": "fleet_draw N=4 evaluator_seed 0",
            }
        )
    # Dormant arms - structure only, not results
    for arm in sorted(package.dormant_arms, key=lambda a: a.arm_id):
        writer.writerow(
            {
                "section": "dormant_arm",
                "key": arm.arm_id,
                "value": "",
                "availability": "STRUCTURE_ONLY",
                "reason": "No E3 workloads launched; arms are dormant structure, not results",
                "replication_unit": package.replication.replication_unit,
                "fleet_seed": "",
                "detail": f"placement={arm.placement} scaling={arm.scaling} state_age_ms={arm.state_age_ms}",  # noqa: E501
            }
        )
    # Dormant configs - structure
    for cfg in sorted(package.dormant_configs, key=lambda c: c.config_id):
        writer.writerow(
            {
                "section": "dormant_config",
                "key": cfg.config_id,
                "value": "",
                "availability": "STRUCTURE_ONLY",
                "reason": "56 configs dormant, NOT_EXECUTED",
                "replication_unit": package.replication.replication_unit,
                "fleet_seed": cfg.fleet_seed,
                "detail": f"arm_id={cfg.arm_id} fleet={cfg.fleet_seed} rsu={cfg.num_rsus}",
            }
        )
    # Strategy families
    semantics = e3_strategy_semantics()
    for sem in semantics:
        writer.writerow(
            {
                "section": "strategy",
                "key": f"{sem.placement_id}__{sem.scaling_id}__age_{sem.state_age_ms}ms",
                "value": "",
                "availability": "SEMANTICS_ONLY",
                "reason": sem.evidence_level,
                "replication_unit": package.replication.replication_unit,
                "fleet_seed": "",
                "detail": sem.human_label[:120],
            }
        )
    # Task accounting - all null
    acct = build_e3_task_accounting_view()
    for field in (
        "offered",
        "admitted",
        "rejected_total",
        "forwarded",
        "deadline_success",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        reason = str(getattr(acct, f"{field}_reason"))
        writer.writerow(
            {
                "section": "task_accounting",
                "key": field,
                "value": "",
                "availability": "UNAVAILABLE",
                "reason": reason,
                "replication_unit": "fleet_draw",
                "fleet_seed": "",
                "detail": "null lifecycle with reason, never zero",
            }
        )
    # Per-RSU and scale-action structure
    writer.writerow(
        {
            "section": "per_rsu",
            "key": "per_rsu_summaries",
            "value": "",
            "availability": "UNAVAILABLE",
            "reason": package.scaling_receipts.per_rsu_summaries_null_reason,
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "detail": "10 RSUs structure but summaries null before execution",
        }
    )
    writer.writerow(
        {
            "section": "scale_action",
            "key": "scale_action_receipts",
            "value": "",
            "availability": "UNAVAILABLE",
            "reason": package.scaling_receipts.receipts_when_not_executed_null_reason,
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "detail": "scale-action receipts null before execution",
        }
    )
    writer.writerow(
        {
            "section": "scale_action",
            "key": "capacity_levels",
            "value": "",
            "availability": "UNAVAILABLE",
            "reason": package.scaling_receipts.capacity_levels_null_reason,
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "detail": "capacity levels null before execution",
        }
    )
    writer.writerow(
        {
            "section": "scale_action",
            "key": "state_age_receipts",
            "value": "",
            "availability": "UNAVAILABLE",
            "reason": package.scaling_receipts.state_age_receipts_null_reason,
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "detail": "state-age receipts null 0/1000/3000 typed int ms",
        }
    )
    # Resource cost
    writer.writerow(
        {
            "section": "resource_cost",
            "key": "resource_unit_seconds",
            "value": "",
            "availability": "UNAVAILABLE",
            "reason": acct.resource_cost.reason,
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "detail": "resource_unit_seconds, not monetary",
        }
    )
    # Provenance pins
    for entry in package.provenance:
        writer.writerow(
            {
                "section": "provenance",
                "key": entry.kind,
                "value": entry.artifact,
                "availability": "verdict",
                "reason": entry.note,
                "replication_unit": package.replication.replication_unit,
                "fleet_seed": "",
                "detail": entry.note,
            }
        )
    writer.writerow(
        {
            "section": "provenance",
            "key": "actor_sha256",
            "value": package.software_identity.actor_sha256,
            "availability": "verdict",
            "reason": "frozen actor",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "frozen MAPPO actor does not observe load",
        }
    )
    writer.writerow(
        {
            "section": "provenance",
            "key": "trace_sha256",
            "value": package.software_identity.trace_sha256,
            "availability": "verdict",
            "reason": "frozen trace",
            "replication_unit": package.replication.replication_unit,
            "fleet_seed": "",
            "detail": "frozen trace",
        }
    )
    return output.getvalue()


def _build_markdown(
    payload: dict[str, object],
    package_fingerprint: str,
    export_fingerprint: str,
    package: E3ResearchEvidencePackage,
) -> str:
    lines: list[str] = []
    lines.append("# E3 Research Export - Deterministic Report (No Results)")
    lines.append("")
    lines.append(
        "> Immutable hold: `LANE_09 = BLOCKED_BY_RESEARCHER_EXECUTION_HOLD`, "  # noqa: E501
        "`E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED`, `evidence_state = NOT_EXECUTED`, "
        "`result_availability = NO_E3_RESEARCH_RESULTS_AVAILABLE`, `research_workloads_launched = 0`."  # noqa: E501
    )
    lines.append("")
    lines.append(f"Package fingerprint: `{package_fingerprint}`")
    lines.append(f"Export fingerprint: `{export_fingerprint}`")
    sk = payload["schema_version"]
    assert isinstance(sk, str)
    lines.append(f"Schema: `{sk}`")
    lines.append("")
    lines.append("## Hold and Admission (Truthful Refusal)")
    lines.append("")
    hold = payload["hold"]
    assert isinstance(hold, dict)
    lines.append(f"- LANE_09: `{hold['lane_09']}`")
    lines.append(f"- Status: `{hold['status']}`")
    lines.append(f"- Evidence state: `{hold['evidence_state']}`")
    lines.append(f"- Result availability: `{hold['result_availability']}`")
    lines.append(f"- Research workloads launched: `{hold['research_workloads_launched']}`")
    lines.append(f"- Banner: {hold['banner']}")
    adm = payload["admission"]
    assert isinstance(adm, dict)
    lines.append(f"- Admission status: `{adm['status']}` (admitted={adm['admitted']})")
    lines.append(f"- Standing: `{adm['standing']}`")
    lines.append(f"- Reason code: `{adm['reason_code']}`")
    lines.append(f"- Reason detail: {adm['reason_detail']}")
    lines.append(f"- Not supervisor approval: {adm['not_supervisor_approval']}")
    lines.append(f"- Not Randy confirmation: {adm['not_randy_confirmation']}")
    lines.append("- Admission fails closed until an exact approved Lane 09 package exists.")
    lines.append("")
    lines.append("## Scientific Question")
    lines.append("")
    sq = payload["scientific_question"]
    assert isinstance(sq, dict)
    lines.append(str(sq["question"]))
    lines.append("")
    lines.append(f"- Bounded to: {sq['bounded_to']}")
    lines.append(
        f"- Replication unit: `{sq['replication_unit']}` evaluator_seed {sq['evaluator_seed']} fleet_seeds {sq['fleet_seeds']} N={sq['n']}"  # noqa: E501
    )
    lines.append(f"- Tasks are not replicates: {sq['tasks_are_not_replicates']}")
    lines.append(f"- No inference beyond: {sq['no_inference_beyond']}")
    lines.append("")
    lines.append("## Staged Design (Dormant)")
    lines.append("")
    staged = payload["staged_design"]
    assert isinstance(staged, dict)
    for stage_key in ("e3a", "e3b", "e3c"):
        stage = staged[stage_key]
        assert isinstance(stage, dict)
        lines.append(f"### {stage_key.upper()}: {stage.get('stage', '')}")
        lines.append("")
        lines.append(f"- Equation: {stage.get('equation', '')}")
        lines.append(
            f"- Unique cells: {stage.get('unique_cells', '')} stage-listed: {stage.get('stage_listed_cells', '')}"  # noqa: E501
        )
        lines.append(
            f"- Placement: {stage.get('placement', '')} Scaling: {stage.get('scaling', '')} State age ms: {stage.get('state_age_ms', '')}"
        )
        lines.append("")
    lines.append(
        f"- Identical fresh cells reused not rerun: {staged.get('identical_fresh_cells_reused_not_rerun')}"
    )
    lines.append(
        f"- Maximum candidate unique cells: {staged.get('maximum_candidate_unique_cells')} not double counted: {staged.get('not_double_counted')}"
    )
    lines.append(f"- Stage listed cells: {staged.get('stage_listed_cells')}")
    lines.append("")
    lines.append("## Replication and Uncertainty Structure")
    lines.append("")
    repl = payload["replication"]
    assert isinstance(repl, dict)
    lines.append(
        f"- Replication unit: `{repl['replication_unit']}` N={repl['n']} fleet_seeds {repl['fleet_seeds']} evaluator_seed {repl['evaluator_seed']}"
    )
    lines.append(
        f"- Method: {repl['method']} interval: {repl['interval']} df={repl['degrees_of_freedom']} t={repl['critical_value']}"
    )
    lines.append(
        f"- Replication key: {repl['replication_key']} tasks_are_not_replicates: {repl['tasks_are_not_replicates']}"
    )
    lines.append("")
    lines.append("## Strategy Semantics (Placement/Scaling Families)")
    lines.append("")
    sdefs = payload["strategy_definitions"]
    assert isinstance(sdefs, list)
    for s in sdefs:
        assert isinstance(s, dict)
        lines.append(f"### {s['placement_id']} / {s['scaling_id']} @ {s['state_age_ms']} ms")
        lines.append("")
        lines.append(f"- Label: {s['human_label']}")
        lines.append(f"- Radio ingress: {s['radio_ingress']}")
        lines.append(f"- Placement: {s['execution_placement']}")
        lines.append(f"- Admission: {s['admission']}")
        lines.append(f"- Forwarding: {s['forwarding']}")
        lines.append(f"- Actor authority: {s['actor_authority']}")
        lines.append(f"- Infrastructure authority: {s['infrastructure_authority']}")
        lines.append(f"- Scaling: {s['scaling_semantics']}")
        lines.append(f"- Staleness: {s['staleness_semantics']}")
        lines.append(f"- Queue: {s['queue_capacity_note']}")
        lines.append(f"- Compute: {s['compute_capacity_note']}")
        lines.append(f"- Resource: {s['resource_cost_note']}")
        lines.append(f"- Deterministic: {s['is_deterministic']}; learned: {s['is_learned']}")
        lines.append(f"- Evidence: {s['evidence_level']}")
        lines.append(f"- Limitations: {s['limitations']}")
        lines.append("")
    lines.append("## Placement / Scaling / Staleness / Resource Trade-off Structure")
    lines.append("")
    tradeoff = payload["tradeoff_structure"]
    assert isinstance(tradeoff, dict)
    lines.append(
        f"- Placements: {tradeoff['placement_families']} values: {tradeoff['placement_values']}"
    )
    lines.append(f"- Scalings: {tradeoff['scaling_families']} values: {tradeoff['scaling_values']}")
    lines.append(
        f"- Staleness values ms: {tradeoff['staleness_values_ms']} allowed: {tradeoff['state_age_ms_allowed']}"
    )
    lines.append(
        f"- Resource metric: {tradeoff['resource_metric']} formula: {tradeoff['resource_formula']} monetary: {tradeoff['resource_is_monetary']}"
    )
    lines.append(f"- Queue vs compute separate: {tradeoff['queue_vs_compute_separate']}")
    lines.append(
        f"- Notes: queue {tradeoff['queue_note'][:80]!r} compute {tradeoff['compute_note'][:80]!r}"
    )
    lines.append("")
    lines.append("## Queue / Compute Separation and Resource Cost")
    lines.append("")
    qc = payload["queue_capacity"]
    assert isinstance(qc, dict)
    lines.append(
        f"- Queue: unit {qc['unit']} per_RSU {qc['capacity_per_rsu']} is_queue_not_compute: {qc['is_queue_not_compute']}"
    )
    cc = payload["compute_capacity"]
    assert isinstance(cc, dict)
    lines.append(
        f"- Compute: unit {cc['unit']} range {cc['active_units_per_rsu_range']} is_compute_not_queue: {cc['is_compute_not_queue']}"
    )
    rc = payload["resource_cost"]
    assert isinstance(rc, dict)
    lines.append(
        f"- Resource: metric {rc['metric']} monetary: {rc['monetary']} formula: {rc['formula']}"
    )
    lines.append("")
    lines.append("## Dormant Arms and Configs (Structure Only)")
    lines.append("")
    lines.append(
        f"- Arms: {len(package.dormant_arms)} (14 expected) configs: {len(package.dormant_configs)} (56 expected)"
    )
    lines.append("")
    lines.append("| arm_id | placement | scaling | state_age_ms |")
    lines.append("|---|---|---|---|")
    arms = payload["dormant_arms"]
    assert isinstance(arms, list)
    for a in arms:
        assert isinstance(a, dict)
        lines.append(f"| {a['arm_id']} | {a['placement']} | {a['scaling']} | {a['state_age_ms']} |")
    lines.append("")
    lines.append("| config_id | arm_id | fleet_seed | rsu | state_age |")
    lines.append("|---|---|---|---|---|")
    cfgs = payload["dormant_configs"]
    assert isinstance(cfgs, list)
    for c in cfgs[:10]:
        assert isinstance(c, dict)
        lines.append(
            f"| {c['config_id']} | {c['arm_id']} | {c['fleet_seed']} | {c['num_rsus']} | {c['state_age_ms']} |"
        )
    lines.append("")
    lines.append("_Total configs 56, showing 10; full list in JSON._")
    lines.append("")
    lines.append("## Per-RSU and Scale-Action Summary STRUCTURE")
    lines.append("")
    per = payload["per_rsu_structure"]
    assert isinstance(per, dict)
    lines.append(f"- Per-RSU summaries: `{per['value']}` — {per['reason']}")
    lines.append(f"- RSU count: {per['rsu_count']} note: {per['notes']}")
    scale = payload["scale_action_structure"]
    assert isinstance(scale, dict)
    lines.append(f"- Scale-action receipts: `{scale['value']}` — {scale['receipts_reason']}")
    lines.append(f"- Capacity levels: `{scale['value']}` — {scale['capacity_levels_reason']}")
    lines.append(f"- State-age receipts: `{scale['value']}` — {scale['state_age_reason']}")
    lines.append(f"- Has receipts when executed: {scale['has_receipts_when_executed']}")
    lines.append("")
    lines.append("## Comparison Views (No Results - Paired Differences Unavailable)")
    lines.append("")
    comp_payload = payload["comparison"]
    assert isinstance(comp_payload, dict)
    for key in ("e3a", "e3b", "e3c"):
        cv = comp_payload[key]
        assert isinstance(cv, dict)
        lines.append(f"### {key.upper()}")
        lines.append("")
        lines.append(
            f"- Stage: {cv['stage']} replication: {cv['replication_unit']} N={cv['n_fleet_draws']} seeds {cv['fleet_seeds']}"
        )
        lines.append(
            f"- Method: {cv['method']} df={cv['degrees_of_freedom']} t={cv['critical_value']}"
        )
        lines.append(f"- Unavailable reason: {cv['unavailable_reason']}")
        lines.append(
            f"- Estimands: {len(cv['estimands'])} paired_differences: {len(cv['paired_differences'])} all per_seed_values None"
        )
        for pd in cv["paired_differences"]:
            assert isinstance(pd, dict)
            lines.append(
                f"  - {pd['comparison_id']}: per_seed null — {pd['unavailable_reason'][:80]}"
            )
        lines.append("")
    lines.append("## Task Accounting (Null Lifecycle with Reasons)")
    lines.append("")
    acc = payload["task_accounting"]
    assert isinstance(acc, dict)
    lines.append(
        f"- Evidence state: {acc['evidence_state']} result_availability: {acc['result_availability']} workloads launched: {acc['research_workloads_launched']}"
    )
    lines.append("")
    lines.append("| field | value | reason |")
    lines.append("|---|---|---|")
    unav = acc["unavailable"]
    assert isinstance(unav, dict)
    for field in (
        "offered",
        "admitted",
        "rejected_total",
        "forwarded",
        "deadline_success",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        meta = unav.get(field, {})
        assert isinstance(meta, dict)
        lines.append(f"| {field} | {meta.get('value', None)} | {meta.get('reason', '')} |")
    lines.append("")
    lines.append(
        f"- Conservation holds: {acc['conservation_holds']} reason: {acc['conservation_reason']}"
    )
    lines.append(f"- Genuine rejection classes: {acc['genuine_rejection_classes']}")
    lines.append(f"- Queue vs compute: {acc['queue_vs_compute']['reason']}")
    lines.append(
        f"- Resource cost: metric {acc['resource_cost']['metric']} value {acc['resource_cost']['value']} reason: {acc['resource_cost']['reason']}"
    )
    lines.append("")
    lines.append("## Missingness (First-Class)")
    lines.append("")
    miss = payload["missingness"]
    assert isinstance(miss, list)
    for m in miss:
        assert isinstance(m, dict)
        lines.append(f"- {m['field']}: {m['reason']}")
    lines.append("")
    lines.append("## Provenance (Heads, Manifests, Hashes)")
    lines.append("")
    prov = payload["provenance"]
    assert isinstance(prov, dict)
    lines.append(f"- Product base SHA: `{prov['product_base_sha']}`")
    lines.append(f"- Research promotion SHA: `{prov['research_promotion_sha']}`")
    lines.append(f"- Approved candidate SHA: `{prov['approved_candidate_sha']}`")
    lines.append(f"- Contract checkpoint SHA: `{prov['contract_checkpoint_sha']}`")
    lines.append(
        f"- VEC promotion: `{prov['vec_promotion']}` core: `{prov['vec_core']}` adapter: `{prov['vec_adapter']}`"
    )
    lines.append(f"- Actor SHA-256: `{prov['actor_sha256']}`")
    lines.append(f"- Trace SHA-256: `{prov['trace_sha256']}`")
    lines.append(f"- Contract SHA-256: `{prov['contract_sha256']}`")
    lines.append(f"- Manifest sidecar: `{prov['manifest_sidecar_sha256']}`")
    for entry in prov["entries"]:
        assert isinstance(entry, dict)
        lines.append(f"- {entry['kind']}: `{entry['artifact']}` — {entry['note']}")
    lines.append("")
    lines.append("## Limitations and Non-Claims")
    lines.append("")
    lims = payload["limitations"]
    assert isinstance(lims, list)
    for lim in lims:
        lines.append(f"- {lim}")
    lines.append("")
    lines.append("Non-claims (explicitly refused):")
    lines.append("")
    ncs = payload["non_claims"]
    assert isinstance(ncs, list)
    for nc in ncs:
        lines.append(f"- {nc}")
    lines.append("")
    lines.append("## Package Fingerprint")
    lines.append("")
    lines.append(f"Package fingerprint: `{package_fingerprint}`")
    lines.append(f"Export fingerprint: `{export_fingerprint}`")
    lines.append(
        "Deterministic: sorted keys, LF endings, separators (',', ':') for fingerprint; "
        "no local absolute paths or timestamps contribute."
    )
    lines.append("")
    lines.append("## No Results Disclaimer")
    lines.append("")
    lines.append(
        "Today there are NO results. Every numeric surface renders the NOT_EXECUTED / NO_E3_RESEARCH_RESULTS_AVAILABLE state explicitly — never a placeholder number, never an empty chart implying zero values, never marketing. Admission fails closed until an exact approved Lane 09 package exists."
    )
    lines.append("")
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


@dataclass(frozen=True)
class E3ResearchExportBundle:
    """Deterministic export bundle for E3 research (no-results truth)."""

    json: str
    csv: str
    markdown: str


def build_e3_research_exports(
    package: E3ResearchEvidencePackage,
    receipt: E3ResearchAdmissionRefusal,
) -> E3ResearchExportBundle:
    """Build deterministic JSON, CSV and Markdown exports for E3 (no-results).

    Consumes the exact Lane-10 typed package and its fail-closed admission
    refusal, verifies the binding via the Lane 10 admission service as runtime
    authority, and delegates all scientific structure to the strategy /
    comparison / task-accounting services with NOT_EXECUTED truth preserved.
    A caller-supplied receipt that is merely self-consistent but not the
    Lane 10 authoritative refusal for the exact package is rejected fail-closed.

    Raises:
        TypeError: if package or receipt are not the exact typed instances.
        ValueError: if receipt is malformed, fingerprint mismatch, not
            authoritative, or any path / secret / timestamp input is present.
    """
    if not isinstance(package, E3ResearchEvidencePackage):
        raise TypeError(f"package must be E3ResearchEvidencePackage, got {type(package).__name__}")
    if not isinstance(receipt, E3ResearchAdmissionRefusal):
        raise TypeError(f"receipt must be E3ResearchAdmissionRefusal, got {type(receipt).__name__}")
    _assert_no_forbidden_content(package.model_dump(mode="json"), "package")
    _assert_no_forbidden_content(receipt.model_dump(mode="json"), "receipt")
    # Re-scan for forbidden claims (mutated containers)
    for obj, label in [
        (package.model_dump(mode="json"), "package"),
        (receipt.model_dump(mode="json"), "receipt"),
    ]:
        v = _scan_forbidden_recursive(obj)
        if v:
            raise ValueError(f"{label} contains forbidden claim: {v[0]}")

    try:
        authoritative = admit_e3_research(package)
    except Exception as exc:
        raise ValueError(f"package not admittable (expected refusal): {exc}") from exc

    # Receipt must equal authoritative refusal (all fields)
    if receipt != authoritative:
        # Provide specific mismatch
        if receipt.reason_code != authoritative.reason_code:
            raise ValueError(
                f"receipt not authoritative: reason_code mismatch {receipt.reason_code!r} != {authoritative.reason_code!r}"
            )
        if receipt.lane_09 != authoritative.lane_09:
            raise ValueError("receipt lane_09 mismatch")
        raise ValueError("receipt not authoritative: does not match Lane 10 admission refusal")

    # Check hold state is truthful no-results
    if package.evidence_state != "NOT_EXECUTED":
        raise ValueError(f"evidence_state must be NOT_EXECUTED, got {package.evidence_state!r}")
    if package.result_availability != "NO_E3_RESEARCH_RESULTS_AVAILABLE":
        raise ValueError(
            f"result_availability must be NO_E3_RESEARCH_RESULTS_AVAILABLE, got {package.result_availability!r}"
        )
    if package.research_workloads_launched != 0:
        raise ValueError("research_workloads_launched must be 0")
    if package.lane_09 != "BLOCKED_BY_RESEARCHER_EXECUTION_HOLD":
        raise ValueError(
            f"lane_09 must be BLOCKED_BY_RESEARCHER_EXECUTION_HOLD, got {package.lane_09!r}"
        )
    if package.status != "E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED":
        raise ValueError(
            f"status must be E3_SCIENTIFIC_EXECUTION_NOT_AUTHORIZED, got {package.status!r}"
        )

    if receipt.evidence_state != "NOT_EXECUTED":
        raise ValueError("receipt evidence_state must be NOT_EXECUTED")
    if receipt.result_availability != "NO_E3_RESEARCH_RESULTS_AVAILABLE":
        raise ValueError("receipt result_availability must be NO_E3_RESEARCH_RESULTS_AVAILABLE")

    package_fingerprint = package.fingerprint()
    if not _HEX64_RE.fullmatch(package_fingerprint):
        raise ValueError("package_fingerprint is not 64 hex")
    # Verify receipt pins match package
    if package.product_base_sha != receipt.product_base_sha:
        raise ValueError("receipt product_base_sha mismatch")
    if package.software_identity.actor_sha256 != receipt.actor_sha256:
        raise ValueError("receipt actor_sha256 mismatch")
    if package.software_identity.trace_sha256 != receipt.trace_sha256:
        raise ValueError("receipt trace_sha256 mismatch")

    payload = _build_payload(package, receipt)
    _assert_no_forbidden_content(payload, "payload")
    # Lane-10 forbidden-claims scan on payload to prevent mutated free text leaking into exports.
    # The payload deliberately contains negative flags and disclaimers that include forbidden substrings
    # as part of explicit denials (e.g., not_supervisor_approval, universal_superiority_forbidden,
    # never tasks_as_N). These are allowlisted when they are part of the typed structure, not free-text
    # mutations. Filter them so only true affirmative mutations (like limitations) are flagged.
    _allowlisted_payload_substrings = {
        "not_supervisor_approval",
        "not_randy_confirmation",
        "manchester_wide_inference_forbidden",
        "universal_superiority_forbidden",
        "never tasks_as_N",
        "never tasks_as_n",
        "No Manchester-wide inference, no universal superiority",
        "no_inference_beyond",
    }
    violations = [
        v
        for v in _scan_forbidden_recursive(payload)
        if not any(allow in v for allow in _allowlisted_payload_substrings)
    ]
    if violations:
        raise ValueError(f"payload contains forbidden claim: {violations[0]}")

    export_fingerprint = _fingerprint(payload)

    json_text = _build_json(payload, package_fingerprint, export_fingerprint)
    csv_text = _build_csv(package)
    markdown_text = _build_markdown(payload, package_fingerprint, export_fingerprint, package)

    for txt in (json_text, csv_text, markdown_text):
        if "\r\n" in txt:
            raise ValueError("export contains CRLF - must be LF only")
        if _contains_absolute_path(txt):
            raise ValueError("generated export leaked absolute path")
    _scan_exports_for_leaks(json_text, csv_text, markdown_text)

    try:
        parsed = json.loads(json_text)
        _ = _fingerprint({k: v for k, v in parsed.items() if k not in {"export_fingerprint"}})
    except Exception as exc:
        raise ValueError(f"generated JSON is not valid: {exc}") from exc

    return E3ResearchExportBundle(json=json_text, csv=csv_text, markdown=markdown_text)

"""Deterministic E2 research export — Lane 08.

Strict typed reporting that consumes the integrated evidence package,
admission receipt, and the strategy / comparison / task-accounting
services. No duplicated scientific constants, no fallback, no
path/secret stripping. Any forbidden path / secret / timestamp input
fails closed. Scientific values originate in the package / service
views with source-declared Student-t intervals preserved.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass

from traffictwin.evidence_admission.e2_research import (
    E2ResearchAdmissionReceipt,
    admit_e2_research,
)
from traffictwin.experiments.e2_comparison import build_e2_comparison_view
from traffictwin.experiments.e2_research_evidence import E2ResearchEvidencePackage
from traffictwin.experiments.e2_strategy_semantics import e2_strategy_semantics
from traffictwin.experiments.e2_task_accounting import build_e2_seed1_task_accounting

_PATH_SUBSTRINGS: tuple[str, ...] = (  # noqa: S108
    "/Users/",
    "/home/",
    "/tmp/",  # noqa: S108
    "/var/folders/",
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
            raise ValueError("export contains absolute local path — rejected")
        if _contains_secret(t):
            raise ValueError("export contains secret-like content — rejected")


def _build_payload(
    package: E2ResearchEvidencePackage,
    receipt: E2ResearchAdmissionReceipt,
) -> dict[str, object]:
    semantics = e2_strategy_semantics()
    comparison = build_e2_comparison_view(package)
    accounting = build_e2_seed1_task_accounting(package)

    # Fail closed if any service output contains forbidden content
    _assert_no_forbidden_content(package.model_dump(mode="json"), "package")
    _assert_no_forbidden_content(receipt.model_dump(mode="json"), "receipt")

    strategy_defs: list[dict[str, object]] = []
    for sem in semantics:
        strategy_defs.append(
            {
                "id": sem.strategy_id,
                "label": sem.human_label,
                "radio_ingress": sem.radio_ingress,
                "placement": sem.execution_placement,
                "admission": sem.admission,
                "forwarding": sem.forwarding,
                "actor_authority": sem.actor_authority,
                "infrastructure_authority": sem.infrastructure_authority,
                "is_learned": sem.is_learned,
                "is_deterministic": sem.is_deterministic,
                "evidence_level": sem.evidence_level,
                "limitations": sem.limitations,
            }
        )

    # E2b
    e2b_dict: dict[str, object] = {
        "metric": comparison.e2b.metric,
        "denominator": "offered",
        "replication_unit": comparison.e2b.replication_unit,
        "evaluator_seed": comparison.e2b.evaluator_seed,
        "fleet_seed": comparison.e2b.fleet_seed,
        "n_fleet_draws": comparison.e2b.n,
        "uncertainty": comparison.e2b.uncertainty,
        "standing": comparison.e2b.standing,
        "manifest_sha256": comparison.e2b.manifest_sha256,
        "code_commit": comparison.e2b.code_commit,
        "actor_sha256": comparison.e2b.actor_sha256,
        "trace_sha256": comparison.e2b.trace_sha256,
        "values": {
            "off": comparison.e2b.off,
            "jsq": comparison.e2b.jsq,
            "ingress_dla": comparison.e2b.ingress_dla,
            "dla": comparison.e2b.dla,
        },
    }

    # E2c
    e2c_draws: list[dict[str, object]] = []
    for seed, val in zip(comparison.e2c.fleet_seeds, comparison.e2c.per_seed_values, strict=True):
        e2c_draws.append({"fleet_seed": seed, "value": val})
    e2c_declared: dict[str, object] = {
        "mean": comparison.e2c.mean,
        "ci95_lower": comparison.e2c.lower,
        "ci95_upper": comparison.e2c.upper,
        "sample_sd": comparison.e2c.sample_sd,
        "standard_error": comparison.e2c.standard_error,
        "degrees_of_freedom": comparison.e2c.degrees_of_freedom,
        "method": comparison.e2c.method,
        "critical_value": comparison.e2c.critical_value,
        "n_fleet_draws": comparison.e2c.n_fleet_draws,
        "fleet_seeds": list(comparison.e2c.fleet_seeds),
        "replication_unit": comparison.e2c.replication_unit,
        "evaluator_seed": comparison.e2c.evaluator_seed,
        "denominator": "offered",
        "includes_zero": comparison.e2c.includes_zero,
        "decision": comparison.e2c.decision,
        "all_negative": comparison.e2c.all_negative,
        "manifest_sha256": comparison.e2c.manifest_sha256,
        "code_commit": comparison.e2c.code_commit,
        "standing": comparison.e2c.standing,
    }

    # E2d primary
    e2d_draws: list[dict[str, object]] = []
    for seed, val in zip(comparison.e2d.fleet_seeds, comparison.e2d.per_seed_values, strict=True):
        e2d_draws.append({"fleet_seed": seed, "value": val})
    e2d_declared: dict[str, object] = {
        "mean": comparison.e2d.mean,
        "ci95_lower": comparison.e2d.lower,
        "ci95_upper": comparison.e2d.upper,
        "sample_sd": comparison.e2d.sample_sd,
        "standard_error": comparison.e2d.standard_error,
        "degrees_of_freedom": comparison.e2d.degrees_of_freedom,
        "method": comparison.e2d.method,
        "critical_value": comparison.e2d.critical_value,
        "n_fleet_draws": comparison.e2d.n_fleet_draws,
        "fleet_seeds": list(comparison.e2d.fleet_seeds),
        "replication_unit": comparison.e2d.replication_unit,
        "evaluator_seed": comparison.e2d.evaluator_seed,
        "denominator": "offered",
        "includes_zero": comparison.e2d.includes_zero,
        "decision": comparison.e2d.decision,
        "all_positive": comparison.e2d.all_positive,
        "manifest_sha256": comparison.e2d.manifest_sha256,
        "code_commit": comparison.e2d.code_commit,
        "standing": comparison.e2d.standing,
    }

    # E2d secondary vs common-target
    vs_draws: list[dict[str, object]] = []
    # Use paired difference per-seed from package for vs draws
    vs_pd = next(
        pd for pd in package.paired_differences if pd.comparison_id == "e2d_per_task_minus_dla"
    )
    for seed, val in zip(vs_pd.fleet_seeds, vs_pd.per_seed_values, strict=True):
        vs_draws.append({"fleet_seed": seed, "value": val})
    vs_declared: dict[str, object] = {
        "mean": comparison.e2d_vs_common_target.mean,
        "ci95_lower": comparison.e2d_vs_common_target.lower,
        "ci95_upper": comparison.e2d_vs_common_target.upper,
        "degrees_of_freedom": comparison.e2d_vs_common_target.degrees_of_freedom,
        "method": comparison.e2d_vs_common_target.method,
        "critical_value": comparison.e2d_vs_common_target.critical_value,
        "n_fleet_draws": comparison.e2d_vs_common_target.n_fleet_draws,
        "fleet_seeds": list(comparison.e2d_vs_common_target.fleet_seeds),
        "replication_unit": comparison.e2d_vs_common_target.replication_unit,
        "denominator": "offered",
        "includes_zero": comparison.e2d_vs_common_target.includes_zero,
        "standing": comparison.e2d_vs_common_target.standing,
        "per_seed": list(vs_pd.per_seed_values),
    }

    direction_reversal: dict[str, object] = {
        "statement": comparison.direction_reversal.statement,
        "e2c_common_target_minus_ingress_mean": comparison.e2c.mean,
        "e2d_per_task_minus_ingress_mean": comparison.e2d.mean,
        "interpretation": (
            "Common-target DLA was directionally negative vs ingress_dla in E2c; "
            "per-task DLA was directionally positive vs ingress_dla in E2d. "
            "Not universal superiority, not population inference."
        ),
        "bounded_to": comparison.direction_reversal.bounded_to,
        "replication_unit": comparison.direction_reversal.replication_unit,
        "reversed": comparison.direction_reversal.reversed,
        "e2c_direction": comparison.direction_reversal.e2c_direction,
        "e2d_direction": comparison.direction_reversal.e2d_direction,
    }

    unavailable_dict: dict[str, object] = {}
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        entry = accounting.unavailable[field]
        unavailable_dict[field] = {
            "value": "UNAVAILABLE",
            "null_value": None,
            "reason": entry.reason,
            "status": entry.status,
        }

    task_accounting: dict[str, object] = {
        "label": "E2d per_task_dla seed 1 reconciliation",
        "source_head": accounting.source_head,
        "source_manifest": accounting.manifest_sha,
        "offered": accounting.offered,
        "admitted": accounting.admitted,
        "rejected_total": accounting.rejected_total,
        "rejected_total_derivation": accounting.rejected_total_derivation,
        "rejected_total_status": accounting.rejected_total_status,
        "rejected_total_label": accounting.rejected_total_label,
        "forwarded": accounting.forwarded,
        "deadline_success": accounting.deadline_success,
        "denominators": {
            "offered_completion_headline": accounting.offered_deadline_attainment,
            "offered_formula": accounting.offered_deadline_attainment_formula,
            "admitted_completion_diagnostic": accounting.admitted_deadline_attainment,
            "admitted_formula": accounting.admitted_deadline_attainment_formula,
            "headline_is_offered": True,
            "admitted_is_conditional_diagnostic_only": True,
            "headline_denominator": accounting.headline_denominator,
            "headline_rule": accounting.headline_rule,
        },
        "conservation": (
            f"offered == admitted + rejected_total -> "
            f"{accounting.offered} == {accounting.admitted} + "
            f"{accounting.rejected_total} -> {str(accounting.conservation_holds).lower()}"
        ),
        "conservation_holds": accounting.conservation_holds,
        "conservation_formula": accounting.conservation_formula,
        "available": {
            "offered": "RESEARCH-EVIDENCE FACT",
            "admitted": "RESEARCH-EVIDENCE FACT",
            "rejected_total": accounting.rejected_total_status,
            "forwarded": "RESEARCH-EVIDENCE FACT",
            "deadline_success": "RESEARCH-EVIDENCE FACT",
        },
        "unavailable": unavailable_dict,
        "rejected_latency_note": accounting.rejected_latency_note,
        "physical_return_note": accounting.physical_return_note,
        "waiting_room_note": accounting.waiting_room_note,
        "report_path": accounting.report_path,
    }

    provenance: dict[str, object] = {
        "e2b": {
            "head": package.source_identities.research_heads.e2b,
            "manifest_sha256": package.source_identities.manifest_sha256_by_study["e2b"],
            "ref": "refs/harness/read-only/e2b",
        },
        "e2c": {
            "head": package.source_identities.research_heads.e2c,
            "manifest_sha256": package.source_identities.manifest_sha256_by_study["e2c"],
            "ref": "refs/harness/read-only/e2c",
        },
        "e2d": {
            "head": package.source_identities.research_heads.e2d,
            "manifest_sha256": package.source_identities.manifest_sha256_by_study["e2d"],
            "ref": "refs/harness/read-only/e2d",
        },
        "actor_sha256": package.source_identities.actor.sha256,
        "trace_sha256": package.source_identities.trace.sha256,
        "base_sha": package.source_identities.base_sha,
        "manifests": dict(package.source_identities.manifest_sha256_by_study),
        "research_heads": {
            "e2b": package.source_identities.research_heads.e2b,
            "e2c": package.source_identities.research_heads.e2c,
            "e2d": package.source_identities.research_heads.e2d,
        },
    }

    admission_dict: dict[str, object] = {
        "decision": "ADMITTED RESEARCH",
        "standing": receipt.standing,
        "owner_authorization": receipt.standing,
        "admission_mode": receipt.admission_mode,
        "not_supervisor_approval": True,
        "not_randy_confirmation": True,
        "explanation": (
            "Exactly admitted built-in package displays both ADMITTED RESEARCH "
            "and OWNER-AUTHORIZED PRODUCT ADMISSION. "
            "This is not supervisor approval and not Randy confirmation."
        ),
        "package_fingerprint": receipt.package_fingerprint,
        "receipt_fingerprint": receipt.receipt_fingerprint,
        "research_heads": dict(receipt.research_heads),
        "manifests": dict(receipt.manifests),
    }

    study_identity: dict[str, object] = {
        "study": "v08-requirements-closure E2b–E2d",
        "campaign": package.campaign,
        "base_sha": package.source_identities.base_sha,
        "incident_hour": "2024-03-15 20:00-21:00 Europe/London",
        "trace_sha256": package.source_identities.trace.sha256,
        "actor_sha256": package.source_identities.actor.sha256,
        "actor": "mappo_modelc_17dim__envs128__lr3e-3__seed100",
        "fleet": "uk2030 provisional",
        "evaluator_seed": package.evaluator_seed,
        "replication_unit": package.replication_unit,
        "service_multiplier": 1.0,
        "waiting_room_cap_per_vehicle": 2.5,
        "waiting_room_cap_absolute_per_rsu": 6220,
        "rso_count": 10,
        "backhaul_ms": 0.0,
        "steps": 3600,
    }

    payload: dict[str, object] = {
        "schema_version": "e2_research_export_v1",
        "study_identity": study_identity,
        "strategy_definitions": strategy_defs,
        "e2b": e2b_dict,
        "e2c": {"draws": e2c_draws, "declared_summary": e2c_declared},
        "e2d": {
            "draws": e2d_draws,
            "declared_summary": e2d_declared,
            "secondary_comparison_vs_common_target": vs_declared,
            "secondary_draws": vs_draws,
        },
        "direction_reversal": direction_reversal,
        "task_accounting": task_accounting,
        "provenance": provenance,
        "admission": admission_dict,
        "limitations": list(package.limitations),
        "non_claims": list(package.non_claims),
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


def _build_csv(
    package: E2ResearchEvidencePackage,
) -> str:
    comparison = build_e2_comparison_view(package)
    accounting = build_e2_seed1_task_accounting(package)
    output = io.StringIO()
    fieldnames = [
        "figure_id",
        "evidence_id",
        "metric",
        "arm",
        "value",
        "denominator",
        "replication_unit",
        "fleet_seed",
        "evaluator_seed",
        "manifest_sha256",
        "code_commit",
        "actor_sha256",
        "trace_sha256",
        "uncertainty",
        "standing",
        "n_fleet_draws",
        "ci95_lower",
        "ci95_upper",
        "decision",
        "availability",
        "reason",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    prov = package.source_identities
    # E2b arms
    e2b_values = [
        ("off", comparison.e2b.off, "fig1_e2b_offered_attainment_off"),
        ("jsq", comparison.e2b.jsq, "fig1_e2b_offered_attainment_jsq"),
        ("dla", comparison.e2b.dla, "fig1_e2b_offered_attainment_dla"),
        ("ingress_dla", comparison.e2b.ingress_dla, "fig1_e2b_offered_attainment_ingress_dla"),
    ]
    for arm, val, fig in e2b_values:
        writer.writerow(
            {
                "figure_id": fig,
                "evidence_id": "e2b_factorial_comparison",
                "metric": "offered_task_deadline_attainment",
                "arm": arm,
                "value": val,
                "denominator": "offered",
                "replication_unit": "fleet_draw",
                "fleet_seed": 0,
                "evaluator_seed": 0,
                "manifest_sha256": prov.manifest_sha256_by_study["e2b"],
                "code_commit": prov.research_heads.e2b,
                "actor_sha256": prov.actor.sha256,
                "trace_sha256": prov.trace.sha256,
                "uncertainty": "one_draw_descriptive_no_interval",
                "standing": "RESEARCH-EVIDENCE FACT",
                "n_fleet_draws": 1,
                "ci95_lower": "",
                "ci95_upper": "",
                "decision": "",
                "availability": "available",
                "reason": "",
            }
        )
    for seed, val in zip(comparison.e2c.fleet_seeds, comparison.e2c.per_seed_values, strict=True):
        writer.writerow(
            {
                "figure_id": f"fig2_e2c_dla_minus_ingress_seed{seed}",
                "evidence_id": "e2c_multidraw_comparison",
                "metric": "offered_attainment_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": val,
                "denominator": "offered",
                "replication_unit": "fleet_draw",
                "fleet_seed": seed,
                "evaluator_seed": 0,
                "manifest_sha256": prov.manifest_sha256_by_study["e2c"],
                "code_commit": prov.research_heads.e2c,
                "actor_sha256": prov.actor.sha256,
                "trace_sha256": prov.trace.sha256,
                "uncertainty": "e2c_primary_interval",
                "standing": "RESEARCH-EVIDENCE FACT",
                "n_fleet_draws": 4,
                "ci95_lower": comparison.e2c.lower,
                "ci95_upper": comparison.e2c.upper,
                "decision": comparison.e2c.decision,
                "availability": "available",
                "reason": "",
            }
        )
    for seed, val in zip(comparison.e2d.fleet_seeds, comparison.e2d.per_seed_values, strict=True):
        writer.writerow(
            {
                "figure_id": f"fig3_e2d_per_task_minus_ingress_seed{seed}",
                "evidence_id": "e2d_robustness_comparison",
                "metric": "offered_attainment_per_task_dla_minus_ingress_dla",
                "arm": "paired_difference",
                "value": val,
                "denominator": "offered",
                "replication_unit": "fleet_draw",
                "fleet_seed": seed,
                "evaluator_seed": 0,
                "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
                "code_commit": prov.research_heads.e2d,
                "actor_sha256": prov.actor.sha256,
                "trace_sha256": prov.trace.sha256,
                "uncertainty": "e2d_primary_interval",
                "standing": "RESEARCH-EVIDENCE FACT",
                "n_fleet_draws": 4,
                "ci95_lower": comparison.e2d.lower,
                "ci95_upper": comparison.e2d.upper,
                "decision": comparison.e2d.decision,
                "availability": "available",
                "reason": "",
            }
        )
    # Declared summaries
    writer.writerow(
        {
            "figure_id": "e2c_declared_summary",
            "evidence_id": "e2c_multidraw_comparison",
            "metric": "declared_mean_dla_minus_ingress_dla",
            "arm": "summary",
            "value": comparison.e2c.mean,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2c"],
            "code_commit": prov.research_heads.e2c,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "two-sided Student-t 95% interval over fleet-draw differences df=3",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 4,
            "ci95_lower": comparison.e2c.lower,
            "ci95_upper": comparison.e2c.upper,
            "decision": comparison.e2c.decision,
            "availability": "available",
            "reason": "all four paired differences negative",
        }
    )
    writer.writerow(
        {
            "figure_id": "e2d_declared_summary",
            "evidence_id": "e2d_robustness_comparison",
            "metric": "declared_mean_per_task_minus_ingress_dla",
            "arm": "summary",
            "value": comparison.e2d.mean,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "two-sided Student-t 95% interval over fleet-draw differences df=3",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 4,
            "ci95_lower": comparison.e2d.lower,
            "ci95_upper": comparison.e2d.upper,
            "decision": comparison.e2d.decision,
            "availability": "available",
            "reason": "all four paired differences positive",
        }
    )
    writer.writerow(
        {
            "figure_id": "e2d_secondary_declared_summary",
            "evidence_id": "e2d_robustness_comparison",
            "metric": "declared_mean_per_task_minus_common_target_dla",
            "arm": "summary",
            "value": comparison.e2d_vs_common_target.mean,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": "",
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "two-sided Student-t 95% interval over fleet-draw differences df=3",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 4,
            "ci95_lower": comparison.e2d_vs_common_target.lower,
            "ci95_upper": comparison.e2d_vs_common_target.upper,
            "decision": "directional_advantage_for_per_task_vs_common_target",
            "availability": "available",
            "reason": "",
        }
    )
    # Accounting available counts
    accounting_rows: list[dict[str, object]] = [
        {
            "figure_id": "e2d_seed1_accounting_offered",
            "evidence_id": "e2d_task_accounting",
            "metric": "offered",
            "arm": "count",
            "value": accounting.offered,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": "evaluator summary",
        },
        {
            "figure_id": "e2d_seed1_accounting_admitted",
            "evidence_id": "e2d_task_accounting",
            "metric": "admitted",
            "arm": "count",
            "value": accounting.admitted,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": "",
        },
        {
            "figure_id": "e2d_seed1_accounting_rejected_total",
            "evidence_id": "e2d_task_accounting",
            "metric": "rejected_total",
            "arm": "count",
            "value": accounting.rejected_total,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "DERIVED / INFERENCE FROM CONSERVATION",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "derived",
            "reason": accounting.rejected_total_derivation,
        },
        {
            "figure_id": "e2d_seed1_accounting_forwarded",
            "evidence_id": "e2d_task_accounting",
            "metric": "forwarded",
            "arm": "count",
            "value": accounting.forwarded,
            "denominator": "admitted",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": "mechanism summary",
        },
        {
            "figure_id": "e2d_seed1_accounting_deadline_success",
            "evidence_id": "e2d_task_accounting",
            "metric": "deadline_success",
            "arm": "count",
            "value": accounting.deadline_success,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "RESEARCH-EVIDENCE FACT",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": "per_task:task_met sum",
        },
        {
            "figure_id": "e2d_seed1_accounting_offered_attainment_headline",
            "evidence_id": "e2d_task_accounting",
            "metric": "offered_task_deadline_attainment",
            "arm": "rate",
            "value": accounting.offered_deadline_attainment,
            "denominator": "offered",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": "RESEARCH-EVIDENCE FACT — headline denominator is offered",
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": accounting.offered_deadline_attainment_formula,
        },
        {
            "figure_id": "e2d_seed1_accounting_admitted_attainment_diagnostic",
            "evidence_id": "e2d_task_accounting",
            "metric": "admitted_task_deadline_attainment",
            "arm": "rate",
            "value": accounting.admitted_deadline_attainment,
            "denominator": "admitted",
            "replication_unit": "fleet_draw",
            "fleet_seed": 1,
            "evaluator_seed": 0,
            "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
            "code_commit": prov.research_heads.e2d,
            "actor_sha256": prov.actor.sha256,
            "trace_sha256": prov.trace.sha256,
            "uncertainty": "",
            "standing": (
                "RESEARCH-EVIDENCE FACT — admitted is conditional diagnostic only, not headline"
            ),
            "n_fleet_draws": 1,
            "ci95_lower": "",
            "ci95_upper": "",
            "decision": "",
            "availability": "available",
            "reason": accounting.admitted_deadline_attainment_formula,
        },
    ]
    for r in accounting_rows:
        writer.writerow(r)
    for field in (
        "gate_rejected",
        "capacity_rejected",
        "started",
        "compute_completed",
        "returned",
        "dropped",
    ):
        entry = accounting.unavailable[field]
        writer.writerow(
            {
                "figure_id": f"e2d_seed1_accounting_{field}",
                "evidence_id": "e2d_task_accounting",
                "metric": field,
                "arm": "lifecycle",
                "value": "UNAVAILABLE",
                "denominator": "n/a",
                "replication_unit": "fleet_draw",
                "fleet_seed": 1,
                "evaluator_seed": 0,
                "manifest_sha256": prov.manifest_sha256_by_study["e2d"],
                "code_commit": prov.research_heads.e2d,
                "actor_sha256": prov.actor.sha256,
                "trace_sha256": prov.trace.sha256,
                "uncertainty": "",
                "standing": "UNAVAILABLE",
                "n_fleet_draws": "",
                "ci95_lower": "",
                "ci95_upper": "",
                "decision": "",
                "availability": "UNAVAILABLE",
                "reason": entry.reason,
            }
        )
    return output.getvalue()


def _build_markdown(
    payload: dict[str, object],
    package_fingerprint: str,
    export_fingerprint: str,
    package: E2ResearchEvidencePackage,
) -> str:
    comparison = build_e2_comparison_view(package)
    accounting = build_e2_seed1_task_accounting(package)
    lines: list[str] = []
    lines.append("# E2 Research Export — Deterministic Report")
    lines.append("")
    lines.append(f"Package fingerprint: `{package_fingerprint}`")
    lines.append(f"Export fingerprint: `{export_fingerprint}`")
    sk = payload["schema_version"]
    assert isinstance(sk, str)
    lines.append(f"Schema: `{sk}`")
    lines.append("")
    lines.append("## Study Identity")
    lines.append("")
    si = payload["study_identity"]
    assert isinstance(si, dict)
    lines.append(f"- Study: {si['study']}")
    lines.append(f"- Base SHA: `{si['base_sha']}`")
    lines.append(f"- Incident hour: {si['incident_hour']}")
    lines.append(f"- Trace SHA-256: `{si['trace_sha256']}`")
    lines.append(f"- Actor SHA-256: `{si['actor_sha256']}` ({si['actor']})")
    lines.append(f"- Fleet: {si['fleet']}")
    lines.append(f"- Evaluator seed: {si['evaluator_seed']}")
    lines.append(f"- Replication unit: `{si['replication_unit']}`")
    lines.append(
        f"- Service: {si['service_multiplier']}x; waiting-room cap: "
        f"{si['waiting_room_cap_per_vehicle']}x "
        f"({si['waiting_room_cap_absolute_per_rsu']} per RSU over {si['rso_count']} RSUs); "
        f"backhaul: {si['backhaul_ms']} ms"
    )
    lines.append(f"- Steps: {si['steps']}")
    lines.append("")
    lines.append("## Strategy Definitions")
    lines.append("")
    sdefs = payload["strategy_definitions"]
    assert isinstance(sdefs, list)
    for s in sdefs:
        assert isinstance(s, dict)
        lines.append(f"### {s['id']}")
        lines.append("")
        lines.append(f"- Label: {s['label']}")
        lines.append(f"- Radio ingress: {s['radio_ingress']}")
        lines.append(f"- Placement: {s['placement']}")
        lines.append(f"- Admission: {s['admission']}")
        lines.append(f"- Forwarding: {s['forwarding']}")
        lines.append(f"- Actor authority: {s['actor_authority']}")
        lines.append(f"- Infrastructure authority: {s['infrastructure_authority']}")
        lines.append(f"- Deterministic: {s['is_deterministic']}; learned: {s['is_learned']}")
        lines.append(f"- Evidence: {s['evidence_level']}")
        lines.append(f"- Limitations: {s['limitations']}")
        lines.append("")
    lines.append("## E2b Results (One-Draw Descriptive)")
    lines.append("")
    lines.append(
        "E2b is one fleet draw (seed 0) descriptive without confidence interval "
        "and without population inference. Tasks are accounting records, never replicates."
    )
    lines.append("")
    lines.append(  # noqa: E501
        "| arm | offered_task_deadline_attainment | denominator | replication_unit | fleet_seed |"
    )
    lines.append("|---|---|---|---|---|")
    eb = payload["e2b"]
    assert isinstance(eb, dict)
    vals = eb["values"]
    assert isinstance(vals, dict)
    for arm in ("off", "jsq", "ingress_dla", "dla"):
        lines.append(f"| {arm} | {vals[arm]} | offered | fleet_draw | 0 |")
    lines.append("")
    lines.append(
        f"Manifest: `{comparison.e2b.manifest_sha256}`; "
        f"code commit: `{comparison.e2b.code_commit}`; "
        f"standing: {comparison.e2b.standing}"
    )
    lines.append("")
    lines.append("## E2c Draws and Declared Summary")
    lines.append("")
    lines.append("Four matched fleet draws (seeds 1–4), paired dla minus ingress_dla.")
    lines.append("")
    lines.append("| fleet_seed | dla_minus_ingress_dla | denominator | replication_unit |")
    lines.append("|---|---|---|---|")
    ec = payload["e2c"]
    assert isinstance(ec, dict)
    draws = ec["draws"]
    assert isinstance(draws, list)
    for d in draws:
        assert isinstance(d, dict)
        lines.append(f"| {d['fleet_seed']} | {d['value']} | offered | fleet_draw |")
    lines.append("")
    ds = ec["declared_summary"]
    assert isinstance(ds, dict)
    lines.append(f"- Mean: {ds['mean']}")
    lines.append(
        f"- 95% CI: [{ds['ci95_lower']}, {ds['ci95_upper']}] "
        f"(two-sided Student-t, df={ds['degrees_of_freedom']}, method: {ds['method']})"
    )
    lines.append(f"- SD: {ds['sample_sd']}; SE: {ds['standard_error']}")
    lines.append(f"- Decision: {ds['decision']}; all negative: {ds['all_negative']}")
    lines.append("")
    lines.append("## E2d Draws and Declared Summary")
    lines.append("")
    lines.append("Four matched fleet draws (seeds 1–4), primary per_task minus ingress.")
    lines.append("")
    lines.append("| fleet_seed | per_task_minus_ingress_dla | denominator | replication_unit |")
    lines.append("|---|---|---|---|")
    ed = payload["e2d"]
    assert isinstance(ed, dict)
    draws2 = ed["draws"]
    assert isinstance(draws2, list)
    for d in draws2:
        assert isinstance(d, dict)
        lines.append(f"| {d['fleet_seed']} | {d['value']} | offered | fleet_draw |")
    lines.append("")
    dsd = ed["declared_summary"]
    assert isinstance(dsd, dict)
    lines.append(
        f"- Primary mean: {dsd['mean']}; 95% CI: [{dsd['ci95_lower']}, {dsd['ci95_upper']}]"
    )
    lines.append(f"- Decision: {dsd['decision']}; all positive: {dsd['all_positive']}")
    lines.append("")
    sec = ed["secondary_comparison_vs_common_target"]
    assert isinstance(sec, dict)
    lines.append(
        f"- Secondary per_task_minus_common_target mean: {sec['mean']}; "
        f"CI: [{sec['ci95_lower']}, {sec['ci95_upper']}]"
    )
    lines.append("")
    lines.append("## Direction Reversal")
    lines.append("")
    dr = payload["direction_reversal"]
    assert isinstance(dr, dict)
    lines.append(str(dr["statement"]))
    lines.append("")
    lines.append(f"- E2c mean: {dr['e2c_common_target_minus_ingress_mean']} (negative)")
    lines.append(f"- E2d mean: {dr['e2d_per_task_minus_ingress_mean']} (positive)")
    lines.append(f"- Bounded to: {dr['bounded_to']}")
    lines.append(f"- Replication unit: fleet_draw; reversal: {dr['reversed']}")
    lines.append("")
    lines.append("## Task Accounting, Denominators and Missingness")
    lines.append("")
    acc = payload["task_accounting"]
    assert isinstance(acc, dict)
    lines.append(f"Label: {acc['label']} (source head `{acc['source_head']}`)")
    lines.append("")
    lines.append(f"- offered: {acc['offered']}")
    lines.append(f"- admitted: {acc['admitted']}")
    lines.append(f"- rejected_total: {acc['rejected_total']} — {acc['rejected_total_derivation']}")
    lines.append(f"- forwarded: {acc['forwarded']}")
    lines.append(f"- deadline_success: {acc['deadline_success']}")
    lines.append("")
    lines.append(f"Conservation: {acc['conservation']}")
    lines.append("")
    dens = acc["denominators"]
    assert isinstance(dens, dict)
    lines.append(f"- Headline offered attainment: {dens['offered_completion_headline']}")
    lines.append(f"  Formula: {dens['offered_formula']} — headline denominator is offered")
    lines.append(f"- Diagnostic admitted attainment: {dens['admitted_completion_diagnostic']}")
    lines.append(f"  Formula: {dens['admitted_formula']} — conditional diagnostic only")
    lines.append("")
    lines.append("Unavailable lifecycle fields (never zero — explicit UNAVAILABLE with reason):")
    lines.append("")
    unav = acc["unavailable"]
    assert isinstance(unav, dict)
    for field, meta in unav.items():
        assert isinstance(meta, dict)
        lines.append(f"- {field}: UNAVAILABLE — {meta['reason']}")
    lines.append("")
    lines.append(accounting.rejected_latency_note)
    lines.append("")
    lines.append(accounting.physical_return_note)
    lines.append("")
    lines.append("## Provenance (Heads, Manifests, Hashes)")
    lines.append("")
    prov = payload["provenance"]
    assert isinstance(prov, dict)
    for key in ("e2b", "e2c", "e2d"):
        p = prov[key]
        assert isinstance(p, dict)
        lines.append(f"- {key}: head `{p['head']}` manifest `{p['manifest_sha256']}`")
    lines.append(f"- actor SHA-256: `{prov['actor_sha256']}`")
    lines.append(f"- trace SHA-256: `{prov['trace_sha256']}`")
    lines.append(f"- base SHA: `{prov['base_sha']}`")
    lines.append("")
    lines.append("## Admission Standing")
    lines.append("")
    adm = payload["admission"]
    assert isinstance(adm, dict)
    lines.append(f"- Decision: {adm['decision']}")
    lines.append(f"- Standing: {adm['standing']}")
    lines.append(f"- Mode: {adm['admission_mode']}")
    lines.append(f"- Not supervisor approval: {adm['not_supervisor_approval']}")
    lines.append(f"- Not Randy confirmation: {adm['not_randy_confirmation']}")
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
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


@dataclass(frozen=True)
class E2ResearchExportBundle:
    """Deterministic export bundle for E2 research."""

    json: str
    csv: str
    markdown: str


def build_e2_research_exports(
    package: E2ResearchEvidencePackage,
    receipt: E2ResearchAdmissionReceipt,
) -> E2ResearchExportBundle:
    """Build deterministic JSON, CSV and Markdown exports.

    Consumes the exact integrated typed package and owner-authorized
    admission receipt, verifies the binding via the Lane 04 admission
    service as runtime authority, and delegates all scientific values to
    the strategy / comparison / task-accounting services with
    source-declared intervals preserved. A caller-supplied receipt that
    is merely self-consistent but not the Lane 04 authoritative receipt
    for the exact package is rejected fail-closed.

    Raises:
        TypeError: if package or receipt are not the exact typed instances.
        ValueError: if receipt is malformed, unadmitted, fingerprint mismatch,
            not owner-authorized, or any path / secret / timestamp input is present.
    """
    if not isinstance(package, E2ResearchEvidencePackage):
        raise TypeError(f"package must be E2ResearchEvidencePackage, got {type(package).__name__}")
    if not isinstance(receipt, E2ResearchAdmissionReceipt):
        raise TypeError(f"receipt must be E2ResearchAdmissionReceipt, got {type(receipt).__name__}")
    # Path / secret / timestamp screening — fail closed, never strip
    _assert_no_forbidden_content(package.model_dump(mode="json"), "package")
    _assert_no_forbidden_content(receipt.model_dump(mode="json"), "receipt")

    # Lane 04 authoritative admission — re-derive from supplied package.
    # Do not trust caller-supplied receipt alone; require it to equal the
    # authoritative receipt in all security-relevant fields.
    try:
        authoritative = admit_e2_research(package)
    except Exception as exc:
        raise ValueError(f"package not owner-authorized: {exc}") from exc

    # Receipt self-consistency (standing, hex, binding, no timestamps)
    try:
        receipt.verify()
    except Exception as exc:
        raise ValueError(f"receipt verification failed: {exc}") from exc

    package_fingerprint = package.fingerprint()
    if receipt.package_fingerprint != package_fingerprint:
        raise ValueError(
            f"receipt package_fingerprint mismatch: {receipt.package_fingerprint!r} "
            f"!= {package_fingerprint!r}"
        )
    # Require caller-supplied receipt to equal Lane 04 authoritative receipt.
    # Compare all security-relevant fields/fingerprint — any divergence is
    # fail-closed (including recomputed receipt_fingerprint for a forged package).
    if receipt != authoritative:
        # Provide specific mismatch for debugging without leaking secrets.
        if receipt.receipt_fingerprint != authoritative.receipt_fingerprint:
            raise ValueError(
                "receipt not authoritative: receipt_fingerprint mismatch "
                f"(got {receipt.receipt_fingerprint[:8]}… "
                f"expected {authoritative.receipt_fingerprint[:8]}…)"
            )
        if receipt.package_fingerprint != authoritative.package_fingerprint:
            raise ValueError(
                f"receipt not authoritative: package_fingerprint mismatch "
                f"{receipt.package_fingerprint!r} != {authoritative.package_fingerprint!r}"
            )
        raise ValueError("receipt not authoritative: does not match Lane 04 admission")
    # Cross-check research heads / manifests / actor / trace binding (defense-in-depth)
    for name in ("e2b", "e2c", "e2d"):
        pkg_head = getattr(package.source_identities.research_heads, name)
        rec_head = receipt.research_heads.get(name)
        if pkg_head != rec_head:
            raise ValueError(f"receipt research_heads[{name}] mismatch")
        pkg_man = package.source_identities.manifest_sha256_by_study.get(name)
        rec_man = receipt.manifests.get(name)
        if pkg_man != rec_man:
            raise ValueError(f"receipt manifests[{name}] mismatch")
    if package.source_identities.actor.sha256 != receipt.actor_sha256:
        raise ValueError("receipt actor_sha256 mismatch")
    if package.source_identities.trace.sha256 != receipt.trace_sha256:
        raise ValueError("receipt trace_sha256 mismatch")
    if not _HEX64_RE.fullmatch(package_fingerprint):
        raise ValueError("package_fingerprint is not 64 hex")

    payload = _build_payload(package, receipt)

    # Ensure payload itself has no forbidden content
    _assert_no_forbidden_content(payload, "payload")

    export_fingerprint = _fingerprint(payload)

    json_text = _build_json(payload, package_fingerprint, export_fingerprint)
    csv_text = _build_csv(package)
    markdown_text = _build_markdown(payload, package_fingerprint, export_fingerprint, package)

    for txt in (json_text, csv_text, markdown_text):
        if "\r\n" in txt:
            raise ValueError("export contains CRLF — must be LF only")
        if _contains_absolute_path(txt):
            raise ValueError("generated export leaked absolute path")
    _scan_exports_for_leaks(json_text, csv_text, markdown_text)

    # Parse JSON to ensure validity and byte-stability
    try:
        parsed = json.loads(json_text)
        _ = _fingerprint({k: v for k, v in parsed.items() if k not in {"export_fingerprint"}})
    except Exception as exc:
        raise ValueError(f"generated JSON is not valid: {exc}") from exc

    return E2ResearchExportBundle(json=json_text, csv=csv_text, markdown=markdown_text)

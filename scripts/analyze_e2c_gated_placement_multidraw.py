#!/usr/bin/env python3
"""Deterministic paired and mechanism analysis for completed E2c evidence."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from analyze_e2_native_placement_pilot import arm_record
from validate_e2c_gated_placement_multidraw import cell_name, cell_root, sha256

T_CRITICAL_TWO_SIDED_95_DF3 = 3.182446305284263

SECONDARY_PATHS: dict[str, tuple[str, ...]] = {
    "admitted_task_deadline_attainment": ("admitted_task_deadline_attainment",),
    "deadline_met_task_count": ("deadline_met_tasks",),
    "admitted_task_count": ("admitted_tasks",),
    "v2i_admitted_count": ("v2i_path_metrics", "v2i_admitted_tasks"),
    "gate_rejected_count": (
        "rejection_and_unavailability",
        "v2i_gate_rejected",
    ),
    "cap_rejected_count": ("rejection_and_unavailability", "v2i_cap_rejected"),
    "offered_task_latency_ms": ("latency_ms_per_offered_task",),
    "admitted_task_latency_ms": ("latency_ms_per_admitted_task",),
    "deadline_met_latency_ms": ("deadline_met_latency_mean_ms",),
    "energy_j_per_offered_task": ("energy_j_per_offered_task",),
    "forwarded_count": ("v2i_path_metrics", "forwarded_admitted_task_count"),
    "forwarded_share": (
        "v2i_path_metrics",
        "forwarded_share_of_admitted_v2i",
    ),
    "execution_share_range": (
        "v2i_path_metrics",
        "imbalance_diagnostic",
        "value",
    ),
    "maximum_execution_share": ("v2i_path_metrics", "maximum_execution_share"),
}


def at(record: dict[str, Any], path: tuple[str, ...]) -> float:
    value: Any = record
    for key in path:
        value = value[key]
    return float(value)


def sign_counts(values: list[float]) -> dict[str, int]:
    return {
        "negative": sum(value < 0.0 for value in values),
        "zero": sum(value == 0.0 for value in values),
        "positive": sum(value > 0.0 for value in values),
    }


def sign_consistency(values: list[float]) -> str:
    counts = sign_counts(values)
    if counts["negative"] == len(values):
        return "all_negative"
    if counts["positive"] == len(values):
        return "all_positive"
    if counts["zero"] == len(values):
        return "all_numerically_zero_without_equivalence_claim"
    return "mixed"


def primary_summary(values: list[float]) -> dict[str, Any]:
    if len(values) != 4:
        raise ValueError("the E2c primary sample requires exactly four new fleet draws")
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values)
    standard_error = standard_deviation / math.sqrt(len(values))
    half_width = T_CRITICAL_TWO_SIDED_95_DF3 * standard_error
    lower, upper = mean - half_width, mean + half_width
    excludes_zero = lower > 0.0 or upper < 0.0
    return {
        "raw_paired_differences": values,
        "n_fleet_draws": 4,
        "replication_unit": "fleet_seed",
        "sign_counts": sign_counts(values),
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "confidence_interval": {
            "method": "two-sided Student t interval over fleet-draw differences",
            "confidence_level": 0.95,
            "degrees_of_freedom": 3,
            "critical_value": T_CRITICAL_TWO_SIDED_95_DF3,
            "lower": lower,
            "upper": upper,
            "excludes_zero": excludes_zero,
        },
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "decision": (
            "evidence_of_directional_difference_within_bounded_four_draw_replication"
            if excludes_zero
            else "inconclusive_at_this_replication_size"
        ),
        "seed0_included": False,
        "tasks_used_as_independent_replicates": False,
        "equivalence_or_noninferiority_claim_supported": False,
    }


def descriptive_summary(values: list[float]) -> dict[str, Any]:
    return {
        "raw_values": values,
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "sign_counts": sign_counts(values),
        "sign_consistency": sign_consistency(values),
    }


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def mechanism_record(run_dir: Path, n_rsus: int) -> dict[str, Any]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    task = load_npz(run_dir / "per_task.npz")
    ingress = task["task_ingress_rsu"]
    selected = task["task_selected_execution_rsu"]
    execution = task["task_execution_rsu"]
    admitted = task["task_v2i_admitted"].astype(bool)
    forwarded = task["task_forwarded"].astype(bool)
    met = task["task_met"].astype(bool)
    outcome = task["task_outcome"]
    latency = task["task_lat_ms"]
    attempt = ingress >= 0
    gate_rejected = outcome == 3
    selected_counts = np.bincount(selected[attempt], minlength=n_rsus).astype(np.int64)
    execution_counts = np.bincount(execution[admitted], minlength=n_rsus).astype(np.int64)
    gate_counts = np.bincount(selected[gate_rejected], minlength=n_rsus).astype(np.int64)
    met_counts = np.bincount(execution[admitted & met], minlength=n_rsus).astype(np.int64)
    mean_latency: list[float | None] = []
    attainment: list[float | None] = []
    for rsu in range(n_rsus):
        mask = admitted & (execution == rsu)
        count = int(mask.sum())
        mean_latency.append(float(latency[mask].sum(dtype=np.float64) / count) if count else None)
        attainment.append(float((met & mask).sum() / count) if count else None)
    path = summary["v2i_path_metrics"]
    if selected_counts.tolist() != path["selected_target_count_per_rsu"]:
        raise ValueError(f"selected-target mechanism count mismatch: {run_dir}")
    if execution_counts.tolist() != path["actual_execution_count_per_rsu"]:
        raise ValueError(f"execution mechanism count mismatch: {run_dir}")
    if int(forwarded.sum()) != path["forwarded_admitted_task_count"]:
        raise ValueError(f"forwarding mechanism count mismatch: {run_dir}")
    return {
        "raw_output": str(run_dir.resolve()),
        "selected_target_count_by_rsu": selected_counts.tolist(),
        "actual_execution_count_by_rsu": execution_counts.tolist(),
        "admitted_v2i_count_by_execution_rsu": execution_counts.tolist(),
        "gate_rejected_v2i_count_by_selected_rsu": gate_counts.tolist(),
        "deadline_met_admitted_v2i_count_by_execution_rsu": met_counts.tolist(),
        "mean_admitted_v2i_latency_ms_by_execution_rsu": mean_latency,
        "deadline_attainment_among_admitted_v2i_by_execution_rsu": attainment,
        "forwarded_admitted_task_count": int(forwarded.sum()),
        "forwarded_share_of_admitted_v2i": float(
            forwarded.sum() / admitted.sum() if admitted.any() else 0.0
        ),
        "execution_share_range": float(path["imbalance_diagnostic"]["value"]),
        "maximum_execution_share": float(path["maximum_execution_share"]),
        "ingress_to_execution_matrix": path["ingress_to_execution_pair_matrix"],
        "recorded_backlog_inferred": False,
    }


def verify_seed0_reuse(manifest: dict[str, Any]) -> None:
    for arm in ("ingress_dla", "dla"):
        record = manifest["seed0_reuse"][arm]
        root = Path(record["root"])
        for field, filename in (
            ("summary_sha256", "summary.json"),
            ("per_step_sha256", "per_step.npz"),
            ("per_task_sha256", "per_task.npz"),
            ("checksums_sha256", "checksums.sha256"),
            ("command_sha256", "command.json"),
            ("run_validation_sha256", "run_validation.json"),
        ):
            if sha256(root / filename) != record[field]:
                raise RuntimeError(f"seed-0 {arm} reuse drift: {filename}")


def write_raw_evidence_index(raw_root: Path) -> tuple[Path, Path, int]:
    index_path = raw_root / "raw_evidence_index.json"
    ledger_path = raw_root / "checksums.sha256"
    if index_path.exists() or ledger_path.exists():
        raise FileExistsError("refusing to overwrite E2c root evidence index/checksums")
    files = sorted(
        path
        for path in raw_root.rglob("*")
        if path.is_file() and path not in {index_path, ledger_path}
    )
    total_bytes = sum(path.stat().st_size for path in files)
    payload = {
        "schema_version": "e2c_raw_evidence_index_v1",
        "root": str(raw_root.resolve()),
        "files": [
            {
                "path": str(path.relative_to(raw_root)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
        "file_count_before_root_index": len(files),
        "bytes_before_root_index": total_bytes,
    }
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger_members = files + [index_path]
    ledger_path.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(raw_root)}\n" for path in ledger_members),
        encoding="utf-8",
    )
    return index_path, ledger_path, total_bytes


def markdown_number(value: float) -> str:
    return f"{value:+.9f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--docs-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw_root = Path(manifest["outputs"]["raw_root"])
    campaign_status = raw_root / "campaign_execution_status.json"
    if (
        not campaign_status.is_file()
        or json.loads(campaign_status.read_text(encoding="utf-8")).get("status")
        != "all_authorised_cells_passed"
    ):
        raise RuntimeError("all eight authorised E2c cells have not passed")
    verify_seed0_reuse(manifest)

    outputs = {
        "validation": args.docs_dir / "e2c_gated_placement_multidraw_validation_v1.json",
        "comparison": args.docs_dir / "e2c_gated_placement_multidraw_comparison_v1.json",
        "mechanism": args.docs_dir / "e2c_gated_placement_mechanism_summary_v1.json",
        "evidence": args.docs_dir / "e2c_gated_placement_multidraw_evidence_index_v1.json",
        "report": args.docs_dir / "e2c_gated_placement_multidraw_report_2026-08-10.md",
        "supervisor": args.docs_dir / "e2c_gated_placement_supervisor_summary_2026-08-10.md",
    }
    collisions = [path for path in outputs.values() if path.exists()]
    if (
        collisions
        or (raw_root / "raw_evidence_index.json").exists()
        or (raw_root / "checksums.sha256").exists()
    ):
        raise FileExistsError(f"refusing to overwrite E2c analysis: {collisions}")
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    records: dict[int, dict[str, dict[str, Any]]] = {}
    mechanism: dict[str, Any] = {}
    compact_cells: list[dict[str, Any]] = []
    full_wall_seconds = 0.0
    for seed in manifest["design"]["fleet_seeds"]:
        records[int(seed)] = {}
        mechanism[str(seed)] = {}
        for cell in manifest["full_cell_order"]:
            if int(cell["fleet_seed"]) != int(seed):
                continue
            root = cell_root(manifest, cell)
            validation_path = root / "cell_validation.json"
            status_path = root / "cell_status.json"
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if validation.get("status") != "passed" or status.get("status") != "passed":
                raise RuntimeError(f"E2c cell is not passed: {cell_name(cell)}")
            run_dir = root / "full" / "run_1"
            record = arm_record(run_dir)
            records[int(seed)][cell["arm"]] = record
            mechanism[str(seed)][cell["arm"]] = mechanism_record(
                run_dir, int(manifest["design"]["rsus"])
            )
            full_wall_seconds += float(
                json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["wall_s"]
            )
            compact_cells.append(
                {
                    "cell": cell,
                    "status": "passed",
                    "cell_validation_path": str(validation_path.resolve()),
                    "cell_validation_sha256": sha256(validation_path),
                    "cell_status_sha256": sha256(status_path),
                    "full_summary_sha256": sha256(run_dir / "summary.json"),
                    "full_per_step_sha256": sha256(run_dir / "per_step.npz"),
                    "full_per_task_sha256": sha256(run_dir / "per_task.npz"),
                    "full_checksums_sha256": sha256(run_dir / "checksums.sha256"),
                    "full_evaluator_wall_seconds": float(
                        json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))["wall_s"]
                    ),
                }
            )
        pair_path = raw_root / "pairs" / f"fleet_seed_{seed}" / "pair_validation.json"
        pair = json.loads(pair_path.read_text(encoding="utf-8"))
        if pair.get("status") != "passed":
            raise RuntimeError(f"E2c pair is not passed: fleet seed {seed}")

    seed0_records = {
        arm: arm_record(Path(manifest["seed0_reuse"][arm]["root"]))
        for arm in ("ingress_dla", "dla")
    }
    primary_by_seed = {
        str(seed): float(
            records[seed]["dla"]["offered_task_deadline_attainment"]
            - records[seed]["ingress_dla"]["offered_task_deadline_attainment"]
        )
        for seed in sorted(records)
    }
    primary_values = [primary_by_seed[str(seed)] for seed in sorted(records)]
    primary = primary_summary(primary_values)
    seed0_difference = float(
        seed0_records["dla"]["offered_task_deadline_attainment"]
        - seed0_records["ingress_dla"]["offered_task_deadline_attainment"]
    )
    combined_values = [seed0_difference, *primary_values]

    secondary: dict[str, Any] = {}
    for metric, path in SECONDARY_PATHS.items():
        raw = {
            str(seed): at(records[seed]["dla"], path) - at(records[seed]["ingress_dla"], path)
            for seed in sorted(records)
        }
        secondary[metric] = {
            "direction": "dla_minus_ingress_dla",
            "raw_paired_differences_by_fleet_seed": raw,
            "descriptive_summary": descriptive_summary(list(raw.values())),
        }

    comparison = {
        "schema_version": "e2c_gated_placement_multidraw_comparison_v1",
        "statistical_status": "matched four-new-fleet-draw replication",
        "primary_outcome": "offered-task deadline attainment",
        "primary_estimand": "dla - ingress_dla",
        "primary_replication_sample": {
            "fleet_seeds": [1, 2, 3, 4],
            "per_seed_differences": primary_by_seed,
            "summary": primary,
        },
        "combined_descriptive_pilot_plus_replication_summary": {
            "label": "combined descriptive pilot-plus-replication summary",
            "fleet_seeds": [0, 1, 2, 3, 4],
            "per_seed_differences": {
                "0": seed0_difference,
                **primary_by_seed,
            },
            "summary": descriptive_summary(combined_values),
            "held_out_confirmatory_test": False,
        },
        "new_arm_records_by_seed": {str(key): value for key, value in records.items()},
        "reused_seed0_arm_records": seed0_records,
        "secondary_paired_outcomes": secondary,
        "interpretation_limits": {
            "seed0_used_in_primary_interval": False,
            "tasks_used_as_independent_replicates": False,
            "equivalence_or_noninferiority_claim_supported": False,
            "general_controller_superiority_supported": False,
            "population_wide_performance_supported": False,
            "physical_or_kubernetes_deployment_tested": False,
        },
    }
    mechanism_payload = {
        "schema_version": "e2c_gated_placement_mechanism_summary_v1",
        "question": (
            "Does JSQ placement consistently alter which RSUs execute or reject gated "
            "work, and is that associated with the paired deadline-attainment direction?"
        ),
        "new_fleet_seeds": mechanism,
        "seed0_prior_descriptive": {
            arm: mechanism_record(
                Path(manifest["seed0_reuse"][arm]["root"]),
                int(manifest["design"]["rsus"]),
            )
            for arm in ("ingress_dla", "dla")
        },
        "causal_language_beyond_controlled_simulator_intervention_used": False,
        "unrecorded_backlog_inferred": False,
    }
    validation_payload = {
        "schema_version": "e2c_gated_placement_multidraw_validation_v1",
        "status": "passed",
        "manifest_sha256": sha256(args.manifest),
        "closed_prerequisites_verified": True,
        "seed0_reuse_verified": True,
        "cells_planned": 8,
        "cells_started": 8,
        "cells_passed": 8,
        "cells_failed": 0,
        "cells_stopped": 0,
        "smoke_runs_planned": 16,
        "smoke_runs_passed": 16,
        "full_runs_planned": 8,
        "full_runs_passed": 8,
        "pairs_passed": 4,
        "cell_evidence": compact_cells,
        "task_accounting_passed": True,
        "v2i_work_conservation_passed": True,
        "vehicle_work_conservation_passed": True,
        "path_reconciliation_passed": True,
        "cross_arm_task_fleet_action_identity_passed": True,
    }
    outputs["validation"].write_text(
        json.dumps(validation_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    outputs["comparison"].write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    outputs["mechanism"].write_text(
        json.dumps(mechanism_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    new_rows = []
    for seed in sorted(records):
        for arm in ("ingress_dla", "dla"):
            record = records[seed][arm]
            new_rows.append(
                f"| {seed} | `{arm}` | {record['offered_tasks']:,} | "
                f"{record['admitted_tasks']:,} | {record['deadline_met_tasks']:,} | "
                f"{record['offered_task_deadline_attainment']:.9f} | "
                f"{record['admitted_task_deadline_attainment']:.9f} | "
                f"{record['latency_ms_per_offered_task']:.3f} | "
                f"{record['v2i_path_metrics']['v2i_admitted_tasks']:,} | "
                f"{record['v2i_path_metrics']['forwarded_admitted_task_count']:,} |"
            )
    paired_rows = [
        f"| {seed} | {records[seed]['ingress_dla']['offered_task_deadline_attainment']:.9f} | "
        f"{records[seed]['dla']['offered_task_deadline_attainment']:.9f} | "
        f"{markdown_number(primary_by_seed[str(seed)])} |"
        for seed in sorted(records)
    ]
    secondary_rows = []
    for metric, item in secondary.items():
        values = item["raw_paired_differences_by_fleet_seed"]
        summary = item["descriptive_summary"]
        secondary_rows.append(
            f"| `{metric}` | "
            + " | ".join(f"{float(values[str(seed)]):+.9g}" for seed in sorted(records))
            + f" | {summary['mean']:+.9g} |"
        )
    new_table_header = (
        "| Fleet seed | Arm | Offered | Admitted | Deadline met | Offered attainment | "
        "Admitted attainment | Latency/offered (ms) | V2I admitted | Forwarded |"
    )
    primary_signs = (
        f"{primary['sign_counts']['negative']} / {primary['sign_counts']['zero']} / "
        f"{primary['sign_counts']['positive']}"
    )
    primary_ci = (
        f"[{primary['confidence_interval']['lower']:.12f}, "
        f"{primary['confidence_interval']['upper']:.12f}]"
    )
    primary_extrema = (
        f"{primary['median']:+.12f} / {primary['minimum']:+.12f} / {primary['maximum']:+.12f}"
    )
    report = f"""# E2c gated-placement matched multi-draw report — 10 August 2026

## Status and evidence boundary

All 16 predeclared ten-step smokes and all eight new 3,600-step cells passed. The primary
replication sample is the four new matched fleet draws 1–4. Seed 0 is prior pilot evidence and was
excluded from the primary interval. Individual tasks were not treated as independent replicates.

## New full-cell observations

{new_table_header}
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(new_rows)}

## Primary matched replication

The estimand is `dla - ingress_dla`, holding the live deadline-aware admission gate fixed.

| Fleet seed | ingress_dla | dla | Paired difference |
|---:|---:|---:|---:|
{chr(10).join(paired_rows)}

- Negative / zero / positive draws: {primary_signs}.
- Mean: `{primary["mean"]:+.12f}`.
- Sample SD: `{primary["sample_standard_deviation"]:.12f}`.
- Standard error: `{primary["standard_error"]:.12f}`.
- Two-sided 95% Student-t interval, df=3: `{primary_ci}`.
- Median / minimum / maximum: `{primary_extrema}`.
- Predeclared decision: `{primary["decision"]}`.

This decision applies only to the bounded four-draw replication. It is not an equivalence,
non-inferiority, population-wide or general controller-superiority claim.

## Combined descriptive pilot-plus-replication summary

This separately labelled description includes seeds 0–4 and is not a held-out confirmatory test.
The five raw differences are `{", ".join(f"{value:+.12f}" for value in combined_values)}`; their
descriptive mean is `{statistics.fmean(combined_values):+.12f}`, median
`{statistics.median(combined_values):+.12f}`, range
`[{min(combined_values):+.12f}, {max(combined_values):+.12f}]`, and sign consistency is
`{sign_consistency(combined_values)}`.

## Secondary paired outcomes (`dla - ingress_dla`)

Raw fleet-seed differences precede the descriptive mean.

| Outcome | Seed 1 | Seed 2 | Seed 3 | Seed 4 | Mean |
|---|---:|---:|---:|---:|---:|
{chr(10).join(secondary_rows)}

## Mechanism and conservation

The machine-readable mechanism summary reports, by arm and fleet seed, selected targets, actual
execution, gate rejection, deadline-met admitted V2I tasks, admitted-V2I latency and attainment by
execution RSU, forwarding, execution imbalance and the complete ingress-to-execution matrix.
Observed redistribution is described only as associated with the paired deadline direction. No
unrecorded decision-time backlog was inferred.

Every cell passed task accounting, task-outcome reconciliation, native path consistency, V2I
service-work conservation and vehicle service-work conservation. `ingress_dla` selected and
executed only at ingress, forwarded zero tasks and charged zero forwarding latency. `dla` recorded
forwarding only for admitted tasks whose execution differed from ingress; rejected work was never
executed or forwarded. Backhaul latency was zero by design.

## Limitations and stop

- Four new provisional fleet draws, one fixed evaluator seed and one Manchester incident hour.
- One cap, fixed 1x service, ideal zero-cost backhaul and no ordinary-traffic control.
- The frozen actor does not observe current RSU load or select an execution RSU.
- Deadline attainment is evaluator success, not confirmed physical task-result return.
- No physical deployment, Kubernetes execution, scaling, P2C, learning, prediction or retraining.
- The controlled simulator intervention does not establish real-world causality or
  Manchester-wide generalisation.
- Close numerical values are not equivalence.

E2c stops here. The exact next gate is researcher review.
"""
    outputs["report"].write_text(report, encoding="utf-8")
    outputs["supervisor"].write_text(
        f"""# Supervisor-facing E2c summary — 10 August 2026

The four-new-draw matched E2c replication completed all 16 smoke and eight full-cell gates. The
four `dla - ingress_dla` offered-attainment differences were
`{", ".join(f"{value:+.9f}" for value in primary_values)}`. Their mean was
`{primary["mean"]:+.9f}` and the two-sided 95% Student-t interval with three degrees of freedom was
`[{primary["confidence_interval"]["lower"]:+.9f}, {primary["confidence_interval"]["upper"]:+.9f}]`,
yielding `{primary["decision"]}`. Seed 0 was excluded from that interval and appears only in the
separately labelled combined descriptive pilot-plus-replication summary. Researcher review is the
next decision gate; no further experiment is authorised.
""",
        encoding="utf-8",
    )

    raw_index, raw_checksums, raw_bytes = write_raw_evidence_index(raw_root)
    evidence_payload = {
        "schema_version": "e2c_gated_placement_multidraw_evidence_index_v1",
        "manifest": {"path": str(args.manifest.resolve()), "sha256": sha256(args.manifest)},
        "raw_root": str(raw_root.resolve()),
        "raw_evidence_index": {"path": str(raw_index), "sha256": sha256(raw_index)},
        "raw_checksums": {"path": str(raw_checksums), "sha256": sha256(raw_checksums)},
        "raw_bytes_before_root_index": raw_bytes,
        "new_full_evaluator_wall_seconds": full_wall_seconds,
        "new_full_evaluator_wall_hours": full_wall_seconds / 3600.0,
        "cells": compact_cells,
        "documents": [
            {"path": str(outputs[key].resolve()), "sha256": sha256(outputs[key])}
            for key in ("validation", "comparison", "mechanism", "report", "supervisor")
        ],
        "failed_or_stopped_cells": [],
    }
    outputs["evidence"].write_text(
        json.dumps(evidence_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "primary_decision": primary["decision"],
                "comparison": str(outputs["comparison"]),
                "report": str(outputs["report"]),
                "evidence_index": str(outputs["evidence"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

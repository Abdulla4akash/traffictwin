#!/usr/bin/env python3
"""Deterministic paired and mechanism analysis for completed E2d evidence."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from analyze_e2_native_placement_pilot import arm_record
from numpy.typing import NDArray
from validate_e2d_per_task_placement_robustness import (
    cell_name,
    cell_root,
    reference_record,
    sha256,
    verify_reference_record,
)

T_CRITICAL_TWO_SIDED_95_DF3 = 3.182446305284263

SECONDARY_PATHS: dict[str, tuple[str, ...]] = {
    "offered_deadline_attainment": ("offered_task_deadline_attainment",),
    "admitted_deadline_attainment": ("admitted_task_deadline_attainment",),
    "deadline_met_count": ("deadline_met_tasks",),
    "total_admitted_tasks": ("admitted_tasks",),
    "admitted_v2i_tasks": ("v2i_path_metrics", "v2i_admitted_tasks"),
    "gate_rejected_tasks": ("rejection_and_unavailability", "v2i_gate_rejected"),
    "cap_rejected_tasks": ("rejection_and_unavailability", "v2i_cap_rejected"),
    "v2i_unavailable_tasks": ("rejection_and_unavailability", "v2i_unavailable"),
    "offered_task_mean_latency_ms": ("latency_ms_per_offered_task",),
    "admitted_task_mean_latency_ms": ("latency_ms_per_admitted_task",),
    "deadline_met_mean_latency_ms": ("deadline_met_latency_mean_ms",),
    "energy_j_per_offered_task": ("energy_j_per_offered_task",),
    "forwarded_count": ("v2i_path_metrics", "forwarded_admitted_task_count"),
    "forwarded_share_of_admitted_v2i": (
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


def paired_summary(values: list[float], *, primary: bool) -> dict[str, Any]:
    if len(values) != 4:
        raise ValueError("E2d requires exactly four fleet-draw differences")
    mean = statistics.fmean(values)
    standard_deviation = statistics.stdev(values)
    standard_error = standard_deviation / math.sqrt(4)
    half_width = T_CRITICAL_TWO_SIDED_95_DF3 * standard_error
    lower, upper = mean - half_width, mean + half_width
    if primary and upper < 0.0:
        decision = "directional_deficit_persists_under_per_task_placement_within_bounded_draws"
    elif primary and lower > 0.0:
        decision = "directional_advantage_for_per_task_placement_within_bounded_draws"
    elif primary:
        decision = "inconclusive_at_this_replication_size"
    elif upper < 0.0:
        decision = "secondary_interval_entirely_below_zero"
    elif lower > 0.0:
        decision = "secondary_interval_entirely_above_zero"
    else:
        decision = "secondary_interval_includes_zero"
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
            "includes_zero": lower <= 0.0 <= upper,
        },
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "decision": decision,
        "seed0_included": False,
        "tasks_used_as_independent_replicates": False,
        "equivalence_claim_supported": False,
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
    }


def paired_differences(
    records: dict[int, dict[str, dict[str, Any]]],
    *,
    left: str,
    right: str,
    path: tuple[str, ...],
) -> dict[str, float]:
    return {
        str(seed): at(records[seed][left], path) - at(records[seed][right], path)
        for seed in sorted(records)
    }


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def substep_mechanism(task: dict[str, np.ndarray]) -> dict[str, Any]:
    ingress = task["task_ingress_rsu"]
    selected = task["task_selected_execution_rsu"]
    counts: list[int] = []
    unique_counts: list[int] = []
    switches: list[int] = []
    maxima: list[int] = []
    for time_index in range(ingress.shape[0]):
        for substep_index in range(ingress.shape[1]):
            attempt = ingress[time_index, substep_index] >= 0
            targets = selected[time_index, substep_index][attempt]
            count = int(targets.size)
            counts.append(count)
            if count:
                unique_counts.append(int(np.unique(targets).size))
                switches.append(int(np.sum(targets[1:] != targets[:-1])))
                maxima.append(int(np.bincount(targets).max()))
            else:
                unique_counts.append(0)
                switches.append(0)
                maxima.append(0)
    counts_array: NDArray[np.int64] = np.asarray(counts, dtype=np.int64)
    unique_array: NDArray[np.int64] = np.asarray(unique_counts, dtype=np.int64)
    switches_array: NDArray[np.int64] = np.asarray(switches, dtype=np.int64)
    maxima_array: NDArray[np.int64] = np.asarray(maxima, dtype=np.int64)
    active_substeps = counts_array > 0
    return {
        "candidate_order": "ascending padded vehicle-slot index within each ascending task substep",
        "total_task_substeps": int(counts_array.size),
        "task_substeps_with_active_v2i_candidates": int(active_substeps.sum()),
        "total_active_v2i_candidates": int(counts_array.sum()),
        "task_substeps_with_more_than_one_selected_target": int((unique_array > 1).sum()),
        "task_substeps_using_only_one_selected_target": int((unique_array == 1).sum()),
        "task_substeps_with_no_v2i_candidate": int((unique_array == 0).sum()),
        "total_target_switches_in_candidate_order": int(switches_array.sum()),
        "maximum_target_switches_in_one_substep": int(switches_array.max(initial=0)),
        "maximum_unique_selected_targets_in_one_substep": int(unique_array.max(initial=0)),
        "maximum_candidates_sent_to_one_target_in_one_substep": int(maxima_array.max(initial=0)),
        "mean_active_v2i_candidates_per_nonempty_substep": (
            float(counts_array[active_substeps].mean()) if active_substeps.any() else 0.0
        ),
    }


def mechanism_record(run_dir: Path, n_rsus: int) -> dict[str, Any]:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    task = load_npz(run_dir / "per_task.npz")
    ingress = task["task_ingress_rsu"]
    selected = task["task_selected_execution_rsu"]
    execution = task["task_execution_rsu"]
    admitted: NDArray[np.bool_] = task["task_v2i_admitted"].astype(bool)
    forwarded: NDArray[np.bool_] = task["task_forwarded"].astype(bool)
    outcome = task["task_outcome"]
    attempt = ingress >= 0
    gate_rejected = outcome == 3
    selected_counts: NDArray[np.int64] = np.bincount(selected[attempt], minlength=n_rsus).astype(
        np.int64
    )
    execution_counts: NDArray[np.int64] = np.bincount(execution[admitted], minlength=n_rsus).astype(
        np.int64
    )
    gate_counts: NDArray[np.int64] = np.bincount(selected[gate_rejected], minlength=n_rsus).astype(
        np.int64
    )
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
        "gate_rejected_v2i_count_by_selected_rsu": gate_counts.tolist(),
        "forwarded_admitted_task_count": int(forwarded.sum()),
        "forwarded_share_of_admitted_v2i": float(
            forwarded.sum() / admitted.sum() if admitted.any() else 0.0
        ),
        "execution_share_range": float(path["imbalance_diagnostic"]["value"]),
        "maximum_execution_share": float(path["maximum_execution_share"]),
        "rsus_with_positive_execution": int((execution_counts > 0).sum()),
        "ingress_to_execution_matrix": path["ingress_to_execution_pair_matrix"],
        "per_substep": substep_mechanism(task),
        "unrecorded_backlog_inferred": False,
    }


def verify_manifest_snapshot(manifest_path: Path, manifest: dict[str, Any], raw_root: Path) -> None:
    snapshot = raw_root / "manifest_snapshot.json"
    sidecar = raw_root / "manifest_snapshot.sha256"
    manifest_sha = sha256(manifest_path)
    if (
        not snapshot.is_file()
        or not sidecar.is_file()
        or snapshot.read_bytes() != manifest_path.read_bytes()
        or sha256(snapshot) != manifest_sha
        or sidecar.read_text(encoding="utf-8").split()[0] != manifest_sha
        or json.loads(snapshot.read_text(encoding="utf-8")) != manifest
    ):
        raise RuntimeError("E2d campaign manifest snapshot differs at analysis")


def verify_all_reuse(manifest: dict[str, Any]) -> None:
    root = Path(manifest["e2c_reuse"]["raw_root"])
    ledger = Path(manifest["e2c_reuse"]["root_checksum_path"])
    if sha256(ledger) != manifest["e2c_reuse"]["root_checksum_sha256"]:
        raise RuntimeError("E2c root checksum ledger drifted")
    members = 0
    for line in ledger.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError(f"E2c reused evidence drifted: {path}")
        members += 1
    if members != int(manifest["e2c_reuse"]["root_checksum_members"]):
        raise RuntimeError("E2c root checksum member count changed")
    for seed in manifest["design"]["fleet_seeds"]:
        for arm in ("ingress_dla", "dla"):
            for phase in ("smoke", "full"):
                check = verify_reference_record(reference_record(manifest, int(seed), arm, phase))
                if not check["pass"]:
                    raise RuntimeError(f"E2c reference drift: seed={seed} arm={arm} phase={phase}")


def json_bytes(payload: Any) -> bytes:  # noqa: ANN401
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def write_raw_evidence_index(raw_root: Path) -> tuple[Path, Path, int, int]:
    index_path = raw_root / "raw_evidence_index.json"
    ledger_path = raw_root / "checksums.sha256"
    if index_path.exists() or ledger_path.exists():
        raise FileExistsError("refusing to overwrite E2d root evidence index/checksums")
    files = sorted(
        path
        for path in raw_root.rglob("*")
        if path.is_file() and path not in {index_path, ledger_path}
    )
    total_bytes = sum(path.stat().st_size for path in files)
    payload = {
        "schema_version": "e2d_raw_evidence_index_v1",
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
    index_path.write_bytes(json_bytes(payload))
    members = [*files, index_path]
    ledger_path.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(raw_root)}\n" for path in members),
        encoding="utf-8",
    )
    return index_path, ledger_path, len(members), total_bytes


def render_records(
    manifest: dict[str, Any],
    records: dict[int, dict[str, dict[str, Any]]],
    mechanisms: dict[str, Any],
    cells: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str]:
    primary_by_seed = paired_differences(
        records,
        left="per_task_dla",
        right="ingress_dla",
        path=("offered_task_deadline_attainment",),
    )
    batching_by_seed = paired_differences(
        records,
        left="per_task_dla",
        right="dla",
        path=("offered_task_deadline_attainment",),
    )
    primary = paired_summary(list(primary_by_seed.values()), primary=True)
    batching = paired_summary(list(batching_by_seed.values()), primary=False)
    secondary: dict[str, Any] = {}
    for metric, path in SECONDARY_PATHS.items():
        against_ingress = paired_differences(
            records, left="per_task_dla", right="ingress_dla", path=path
        )
        against_common = paired_differences(records, left="per_task_dla", right="dla", path=path)
        secondary[metric] = {
            "per_task_dla_minus_ingress_dla": {
                "per_seed": against_ingress,
                "descriptive": descriptive_summary(list(against_ingress.values())),
            },
            "per_task_dla_minus_dla": {
                "per_seed": against_common,
                "descriptive": descriptive_summary(list(against_common.values())),
            },
        }
    comparison = {
        "schema_version": "e2d_per_task_placement_robustness_comparison_v1",
        "statistical_status": "predeclared matched four-draw construct-validity robustness study",
        "primary": {
            "estimand": "per_task_dla - ingress_dla offered-task deadline attainment",
            "per_seed": primary_by_seed,
            "summary": primary,
        },
        "secondary_batching": {
            "estimand": "per_task_dla - dla offered-task deadline attainment",
            "per_seed": batching_by_seed,
            "summary": batching,
        },
        "secondary_outcomes": secondary,
        "records_by_seed": {str(seed): arms for seed, arms in records.items()},
        "claim_boundaries": manifest["claim_boundaries"],
    }
    mechanism = {
        "schema_version": "e2d_per_task_placement_mechanism_summary_v1",
        "question": (
            "Does per-task sequential least-busy placement alter RSU execution/rejection "
            "and substep target switching, and is that associated with the paired "
            "deadline direction?"
        ),
        "by_fleet_seed": mechanisms,
        "unrecorded_queue_state_inferred": False,
    }
    validation = {
        "schema_version": "e2d_per_task_placement_robustness_validation_v1",
        "status": "passed",
        "replay_probes_planned": 8,
        "replay_probes_passed": 8,
        "smokes_planned": 8,
        "smokes_passed": 8,
        "full_cells_planned": 4,
        "full_cells_started": 4,
        "full_cells_passed": 4,
        "full_cells_failed": 0,
        "full_cells_stopped": 0,
        "cell_evidence": cells,
        "task_accounting_passed": True,
        "v2i_work_conservation_passed": True,
        "vehicle_work_conservation_passed": True,
        "task_fleet_actor_identity_passed": True,
        "path_reconciliation_passed": True,
        "deterministic_second_render_passed": True,
    }
    rows = []
    paired_rows = []
    for seed in sorted(records):
        for arm in ("ingress_dla", "dla", "per_task_dla"):
            record = records[seed][arm]
            rows.append(
                f"| {seed} | `{arm}` | {record['offered_tasks']:,} | "
                f"{record['admitted_tasks']:,} | {record['deadline_met_tasks']:,} | "
                f"{record['offered_task_deadline_attainment']:.9f} | "
                f"{record['v2i_path_metrics']['v2i_admitted_tasks']:,} | "
                f"{record['v2i_path_metrics']['forwarded_admitted_task_count']:,} |"
            )
        paired_rows.append(
            f"| {seed} | {primary_by_seed[str(seed)]:+.12f} | {batching_by_seed[str(seed)]:+.12f} |"
        )
    primary_ci = primary["confidence_interval"]
    batching_ci = batching["confidence_interval"]
    report = f"""# E2d per-task placement robustness report — 11 August 2026

## Status

All eight existing-mode replay probes, eight new-arm smokes and four ordered 3,600-step
`per_task_dla` cells passed. The replication unit is fleet seed; tasks are not independent
replicates. E2c `ingress_dla` and common-target `dla` records were reused by exact hash.

## Per-seed observations

| Seed | Arm | Offered | Admitted | Deadline met | Offered attainment | V2I admitted | Forwarded |
|---:|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

| Seed | per_task_dla - ingress_dla | per_task_dla - dla |
|---:|---:|---:|
{chr(10).join(paired_rows)}

## Primary strongest-link comparison

- Mean: `{primary["mean"]:+.12f}`; sample SD: `{primary["sample_standard_deviation"]:.12f}`;
  SE: `{primary["standard_error"]:.12f}`.
- Two-sided 95% Student-t interval, df=3:
  `[{primary_ci["lower"]:+.12f}, {primary_ci["upper"]:+.12f}]`.
- Median: `{primary["median"]:+.12f}`; range:
  `[{primary["minimum"]:+.12f}, {primary["maximum"]:+.12f}]`.
- Decision: `{primary["decision"]}`.

## Secondary common-target comparison

- Mean: `{batching["mean"]:+.12f}`; sample SD: `{batching["sample_standard_deviation"]:.12f}`;
  SE: `{batching["standard_error"]:.12f}`.
- Separately labelled two-sided 95% Student-t interval, df=3:
  `[{batching_ci["lower"]:+.12f}, {batching_ci["upper"]:+.12f}]`.
- Median: `{batching["median"]:+.12f}`; range:
  `[{batching["minimum"]:+.12f}, {batching["maximum"]:+.12f}]`.

## Mechanism, conservation and limitations

The mechanism record reports per-RSU selected targets, actual execution, gate rejection,
forwarding and ingress-to-execution matrices, plus deterministic per-substep candidate counts,
unique targets, target switches and maximum target concentration. No unrecorded backlog was
inferred. All task, path, V2I-work and vehicle-work ledgers passed.

This is four matched provisional `uk2030` fleet draws, fixed evaluator seed 0, one Manchester
incident hour, one 2.5x/6,220-task cap, fixed 1x service and zero-cost backhaul. The frozen actor
does not observe RSU load or select execution RSUs. The inherited gate is a backlog-only
simulator rule; deadline attainment is not confirmed physical result return. There is no
ordinary-traffic control, physical/Kubernetes deployment, task-level inference, equivalence,
population-wide or Manchester-wide claim. E2d stops for independent post-run review.
"""
    supervisor = f"""# Supervisor-facing E2d summary — 11 August 2026

E2d completed the four predeclared matched `per_task_dla` cells after exact no-effect and smoke
gates. The primary `per_task_dla - ingress_dla` differences were
{", ".join(f"seed {seed} `{primary_by_seed[str(seed)]:+.12f}`" for seed in sorted(records))}.
Their mean was `{primary["mean"]:+.12f}` and the two-sided 95% Student-t interval with df=3 was
`[{primary_ci["lower"]:+.12f}, {primary_ci["upper"]:+.12f}]`; the predeclared decision was
`{primary["decision"]}`. The secondary per-task-minus-common-target mean was
`{batching["mean"]:+.12f}` with interval
`[{batching_ci["lower"]:+.12f}, {batching_ci["upper"]:+.12f}]`.

This bounded construct-validity study covers four matched provisional fleet draws (seeds 1–4),
fixed evaluator seed 0, one Manchester incident hour, one 2.5x/6,220-task cap, fixed 1x service,
zero-cost backhaul and a frozen actor that neither observes RSU load nor chooses execution RSUs.
The new deterministic mode recomputes the least remaining-service-work target per task in padded
vehicle-slot order; the inherited deadline gate remains a backlog-only simulator rule. There was
no ordinary-traffic control, physical task-result-return confirmation, physical/Kubernetes
deployment or task-level inference. The evidence does not establish equivalence, universal
least-busy superiority/inferiority, general controller superiority, or Manchester-wide or
population-wide performance. E2d is closed pending independent post-run review, with no automatic
follow-on authority.
"""
    return validation, comparison, mechanism, report, supervisor


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--docs-dir", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    raw_root = Path(manifest["outputs"]["raw_root"])
    verify_manifest_snapshot(args.manifest, manifest, raw_root)
    verify_all_reuse(manifest)
    campaign = raw_root / "campaign_execution_status.json"
    if (
        not campaign.is_file()
        or json.loads(campaign.read_text(encoding="utf-8")).get("status")
        != "all_authorised_cells_passed"
    ):
        raise RuntimeError("all four E2d cells have not passed")

    outputs = {
        "validation": args.docs_dir / "e2d_per_task_placement_robustness_validation_v1.json",
        "comparison": args.docs_dir / "e2d_per_task_placement_robustness_comparison_v1.json",
        "mechanism": args.docs_dir / "e2d_per_task_placement_mechanism_summary_v1.json",
        "evidence": args.docs_dir / "e2d_per_task_placement_evidence_index_v1.json",
        "report": args.docs_dir / "e2d_per_task_placement_report_2026-08-11.md",
        "supervisor": args.docs_dir / "e2d_per_task_placement_supervisor_summary_2026-08-11.md",
    }
    collisions = [path for path in outputs.values() if path.exists()]
    if collisions or (raw_root / "checksums.sha256").exists():
        raise FileExistsError(f"refusing to overwrite E2d analysis: {collisions}")

    records: dict[int, dict[str, dict[str, Any]]] = {}
    mechanisms: dict[str, Any] = {}
    compact_cells: list[dict[str, Any]] = []
    for seed in manifest["design"]["fleet_seeds"]:
        seed_i = int(seed)
        cell = next(
            item for item in manifest["full_cell_order"] if int(item["fleet_seed"]) == seed_i
        )
        root = cell_root(manifest, cell)
        validation_path = root / "cell_validation.json"
        status_path = root / "cell_status.json"
        if (
            json.loads(validation_path.read_text(encoding="utf-8")).get("status") != "passed"
            or json.loads(status_path.read_text(encoding="utf-8")).get("status") != "passed"
        ):
            raise RuntimeError(f"E2d cell is not passed: {cell_name(cell)}")
        new_root = root / "full" / "run_1"
        records[seed_i] = {"per_task_dla": arm_record(new_root)}
        mechanisms[str(seed_i)] = {
            "per_task_dla": mechanism_record(new_root, int(manifest["design"]["rsus"]))
        }
        for arm in ("ingress_dla", "dla"):
            reference = reference_record(manifest, seed_i, arm, "full")
            reference_root = Path(reference["root"])
            records[seed_i][arm] = arm_record(reference_root)
            mechanisms[str(seed_i)][arm] = mechanism_record(
                reference_root, int(manifest["design"]["rsus"])
            )
        compact_cells.append(
            {
                "cell": cell,
                "status": "passed",
                "cell_validation_path": str(validation_path.resolve()),
                "cell_validation_sha256": sha256(validation_path),
                "cell_status_sha256": sha256(status_path),
                "full_summary_sha256": sha256(new_root / "summary.json"),
                "full_per_step_sha256": sha256(new_root / "per_step.npz"),
                "full_per_task_sha256": sha256(new_root / "per_task.npz"),
                "full_checksums_sha256": sha256(new_root / "checksums.sha256"),
            }
        )

    validation, comparison, mechanism, report, supervisor = render_records(
        manifest, records, mechanisms, compact_cells
    )
    with tempfile.TemporaryDirectory(prefix="e2d-analysis-") as temporary:
        temporary_path = Path(temporary)
        first = [
            json_bytes(validation),
            json_bytes(comparison),
            json_bytes(mechanism),
            report.encode(),
            supervisor.encode(),
        ]
        (
            validation_second,
            comparison_second,
            mechanism_second,
            report_second,
            supervisor_second,
        ) = render_records(manifest, records, mechanisms, compact_cells)
        second = [
            json_bytes(validation_second),
            json_bytes(comparison_second),
            json_bytes(mechanism_second),
            report_second.encode(),
            supervisor_second.encode(),
        ]
        for index, (left, right) in enumerate(zip(first, second, strict=True)):
            (temporary_path / f"record_{index}").write_bytes(right)
            if left != right:
                raise RuntimeError(f"nondeterministic E2d analysis rendering: record {index}")

    args.docs_dir.mkdir(parents=True, exist_ok=True)
    outputs["validation"].write_bytes(json_bytes(validation))
    outputs["comparison"].write_bytes(json_bytes(comparison))
    outputs["mechanism"].write_bytes(json_bytes(mechanism))
    outputs["report"].write_text(report, encoding="utf-8")
    outputs["supervisor"].write_text(supervisor, encoding="utf-8")

    raw_index, raw_ledger, ledger_members, raw_bytes = write_raw_evidence_index(raw_root)
    evidence = {
        "schema_version": "e2d_per_task_placement_evidence_index_v1",
        "manifest": {"path": str(args.manifest.resolve()), "sha256": sha256(args.manifest)},
        "raw_root": str(raw_root.resolve()),
        "raw_evidence_index": {"path": str(raw_index), "sha256": sha256(raw_index)},
        "raw_checksum_ledger": {
            "path": str(raw_ledger),
            "sha256": sha256(raw_ledger),
            "member_count": ledger_members,
        },
        "raw_bytes_before_root_index": raw_bytes,
        "documents": [
            {"path": str(outputs[key].resolve()), "sha256": sha256(outputs[key])}
            for key in ("validation", "comparison", "mechanism", "report", "supervisor")
        ],
        "failed_retries_or_discarded_evidence": [],
    }
    outputs["evidence"].write_bytes(json_bytes(evidence))
    print(
        json.dumps(
            {
                "status": "completed",
                "primary_decision": comparison["primary"]["summary"]["decision"],
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

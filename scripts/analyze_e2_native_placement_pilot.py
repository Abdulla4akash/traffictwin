#!/usr/bin/env python3
"""Deterministic descriptive analysis for the one-seed E2 pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def q(values: np.ndarray, percentile: float) -> float:
    return float(np.percentile(values.astype(np.float64), percentile)) if values.size else 0.0


def arm_record(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text())
    step = load_npz(run_dir / "per_step.npz")
    task = load_npz(run_dir / "per_task.npz")
    active = task["task_active"].astype(bool)
    outcome = task["task_outcome"]
    latency = task["task_lat_ms"]
    admitted = active & np.isin(outcome, (1, 2))
    met = active & (outcome == 1)
    path = summary["v2i_path_metrics"]
    return {
        "raw_output": str(run_dir.resolve()),
        "offered_tasks": int(summary["n_offered"]),
        "admitted_tasks": int(summary["n_admitted"]),
        "deadline_met_tasks": int(met.sum()),
        "offered_task_deadline_attainment": float(summary["completion"]),
        "admitted_task_deadline_attainment": float(summary["completion_admitted"]),
        "latency_ms_per_offered_task": float(summary["avg_latency_ms_per_task"]),
        "latency_ms_per_admitted_task": float(summary["avg_latency_admitted_ms"]),
        "deadline_met_latency_mean_ms": float(summary["avg_latency_met_ms"]),
        "latency_percentiles_ms": {
            "offered_p50": q(latency[active], 50),
            "offered_p95": q(latency[active], 95),
            "offered_p99": q(latency[active], 99),
            "admitted_p50": q(latency[admitted], 50),
            "admitted_p95": q(latency[admitted], 95),
            "admitted_p99": q(latency[admitted], 99),
            "deadline_met_p50": q(latency[met], 50),
            "deadline_met_p95": q(latency[met], 95),
            "deadline_met_p99": q(latency[met], 99),
        },
        "rejection_and_unavailability": {
            "v2i_gate_rejected": int(summary["v2i_gate_rejected"]),
            "v2i_cap_rejected": int(summary["v2i_cap_rejected"]),
            "local_mqd_rejected": int(summary["local_mqd_rejected"]),
            "v2v_mqd_rejected": int(summary["v2v_mqd_rejected"]),
            "v2i_unavailable": int(summary["v2i_unavailable"]),
            "v2v_unavailable": int(summary["v2v_unavailable"]),
        },
        "task_class_completion": {
            "t1": float(summary["t1_completion"]),
            "t2": float(summary["t2_completion"]),
            "t3": float(summary["t3_completion"]),
        },
        "action_shares_per_offered_task": {
            "local": float(summary["p_local"]),
            "v2i": float(summary["p_v2i"]),
            "v2v": float(summary["p_v2v"]),
        },
        "energy_j_per_offered_task": float(summary["avg_energy_j_per_task"]),
        "v2i_work_ms": summary["work_ms"],
        "v2i_path_metrics": path,
        "actor_stream_sha256": {
            "veh_action": hashlib.sha256(step["veh_action"].tobytes()).hexdigest(),
            "veh_actor_logits": hashlib.sha256(step["veh_actor_logits"].tobytes()).hexdigest(),
        },
        "task_stream_sha256": {
            "task_active": hashlib.sha256(task["task_active"].tobytes()).hexdigest(),
            "task_type": hashlib.sha256(task["task_type"].tobytes()).hexdigest(),
        },
    }


SCALAR_PATHS = {
    "offered_task_deadline_attainment": ("offered_task_deadline_attainment",),
    "admitted_task_deadline_attainment": ("admitted_task_deadline_attainment",),
    "admitted_tasks": ("admitted_tasks",),
    "latency_ms_per_offered_task": ("latency_ms_per_offered_task",),
    "latency_ms_per_admitted_task": ("latency_ms_per_admitted_task",),
    "deadline_met_latency_mean_ms": ("deadline_met_latency_mean_ms",),
    "energy_j_per_offered_task": ("energy_j_per_offered_task",),
    "v2i_gate_rejected": ("rejection_and_unavailability", "v2i_gate_rejected"),
    "v2i_cap_rejected": ("rejection_and_unavailability", "v2i_cap_rejected"),
    "v2i_unavailable": ("rejection_and_unavailability", "v2i_unavailable"),
    "v2i_admitted_tasks": ("v2i_path_metrics", "v2i_admitted_tasks"),
    "forwarded_admitted_task_count": ("v2i_path_metrics", "forwarded_admitted_task_count"),
    "forwarded_share_of_admitted_v2i": ("v2i_path_metrics", "forwarded_share_of_admitted_v2i"),
    "maximum_execution_share": ("v2i_path_metrics", "maximum_execution_share"),
    "execution_share_range": ("v2i_path_metrics", "imbalance_diagnostic", "value"),
}


def at(record: dict, path: tuple[str, ...]):
    value = record
    for part in path:
        value = value[part]
    return value


def contrast(records: dict[str, dict], candidate: str, reference: str, meaning: str) -> dict:
    differences = {
        name: float(at(records[candidate], path) - at(records[reference], path))
        for name, path in SCALAR_PATHS.items()
    }
    differences["task_class_completion"] = {
        task: records[candidate]["task_class_completion"][task]
        - records[reference]["task_class_completion"][task]
        for task in ("t1", "t2", "t3")
    }
    differences["actual_execution_count_per_rsu"] = [
        int(a - b) for a, b in zip(
            records[candidate]["v2i_path_metrics"]["actual_execution_count_per_rsu"],
            records[reference]["v2i_path_metrics"]["actual_execution_count_per_rsu"],
        )
    ]
    primary = differences["offered_task_deadline_attainment"]
    observation = (
        "numerical tie" if primary == 0.0 else
        "higher observed offered-task attainment" if primary > 0.0 else
        "lower observed offered-task attainment"
    )
    return {
        "candidate": candidate,
        "reference": reference,
        "meaning": meaning,
        "differences_candidate_minus_reference": differences,
        "direct_primary_observation": observation,
        "statistical_interpretation": (
            "Raw one-draw difference only; no fleet-seed confidence interval, "
            "population generalisation, equivalence, or controller-superiority claim."
        ),
    }


def write_raw_evidence_index(raw_root: Path) -> tuple[Path, Path]:
    index_path = raw_root / "raw_evidence_index.json"
    checksum_path = raw_root / "checksums.sha256"
    if index_path.exists() or checksum_path.exists():
        raise SystemExit("refusing to overwrite root raw evidence index/checksums")
    raw_files = sorted(
        path for path in raw_root.rglob("*")
        if path.is_file() and path not in {index_path, checksum_path}
    )
    index = {
        "schema_version": "e2_raw_evidence_index_v1",
        "root": str(raw_root.resolve()),
        "files": [
            {"path": str(path.relative_to(raw_root)), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in raw_files
        ],
    }
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    checksum_files = raw_files + [index_path]
    checksum_path.write_text("\n".join(
        f"{sha256(path)}  {path.relative_to(raw_root)}" for path in checksum_files
    ) + "\n")
    return index_path, checksum_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--docs-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    raw_root = Path(manifest["outputs"]["raw_root"])
    full_validation_path = raw_root / "full_validation.json"
    if not full_validation_path.is_file():
        raise SystemExit("full_validation.json is missing")
    full_validation = json.loads(full_validation_path.read_text())
    if full_validation.get("status") != "passed":
        raise SystemExit("full validation did not pass")
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    records = {
        arm["id"]: arm_record(raw_root / "full" / arm["id"] / "run_1")
        for arm in manifest["arms"]
    }
    comparisons = {
        "schema_version": "e2_native_placement_comparison_v1",
        "statistical_status": "one-seed descriptive bounded pilot",
        "primary_outcome": "offered-task deadline attainment",
        "arms": records,
        "contrasts": {
            "off_vs_jsq_placement": contrast(
                records, "jsq", "off", "JSQ placement minus strongest-link/off"
            ),
            "jsq_vs_dla_admission": contrast(
                records, "dla", "jsq", "DLA minus JSQ: added deadline-aware admission under JSQ placement"
            ),
            "off_vs_dla_joint": contrast(
                records, "dla", "off", "DLA minus off: joint placement-plus-admission contrast"
            ),
        },
        "limitations": [
            "One evaluator seed and one fleet draw; no fleet-seed confidence interval or population inference.",
            "Tasks are accounting records, not independent statistical replicates.",
            "The frozen 17-dimensional vehicle actor does not observe current RSU load.",
            "Zero backhaul represents ideal fibre; nonzero forwarding cost is deferred to an unauthorised later E3 gate.",
            "The current evaluator reports deadline success, not physical task-return completion.",
            "No ordinary-traffic control, scaling, P2C, learning, retraining, or Kubernetes deployment was tested.",
        ],
    }

    validation_doc = args.docs_dir / "e2_native_placement_pilot_validation_v1.json"
    comparison_doc = args.docs_dir / "e2_native_placement_pilot_comparison_v1.json"
    path_doc = args.docs_dir / "e2_native_placement_path_forwarding_summary_v1.json"
    report_doc = args.docs_dir / "e2_native_placement_pilot_report_2026-08-09.md"
    supervisor_doc = args.docs_dir / "e2_native_placement_supervisor_summary_2026-08-09.md"
    evidence_doc = args.docs_dir / "e2_native_placement_evidence_index_v1.json"
    for path in (validation_doc, comparison_doc, path_doc, report_doc, supervisor_doc, evidence_doc):
        if path.exists():
            raise SystemExit(f"refusing to overwrite {path}")

    validation_payload = {
        "schema_version": "e2_native_placement_pilot_validation_v1",
        "status": "passed",
        "manifest_sha256": sha256(args.manifest),
        "smoke_validation": json.loads((raw_root / "smoke_validation.json").read_text()),
        "full_validation": full_validation,
    }
    path_payload = {
        "schema_version": "e2_native_placement_path_forwarding_summary_v1",
        "arms": {arm: record["v2i_path_metrics"] for arm, record in records.items()},
        "definitions": {
            "forwarded": "admitted V2I with actual execution RSU different from strongest-link ingress",
            "forwarding_share": "forwarded admitted V2I / admitted V2I",
            "execution_share_range": "max(per-RSU execution share) - min(per-RSU execution share)",
        },
    }
    validation_doc.write_text(json.dumps(validation_payload, indent=2, sort_keys=True) + "\n")
    comparison_doc.write_text(json.dumps(comparisons, indent=2, sort_keys=True) + "\n")
    path_doc.write_text(json.dumps(path_payload, indent=2, sort_keys=True) + "\n")

    placement = comparisons["contrasts"]["off_vs_jsq_placement"]
    admission = comparisons["contrasts"]["jsq_vs_dla_admission"]
    report = f"""# E2 native-placement pilot report — 9 August 2026

## Status

The bounded one-seed E2 pilot completed all declared instrumentation, review,
repeat-smoke, path, accounting, and conservation gates. This is descriptive
pilot evidence only, not confirmatory or multi-seed evidence.

## Direct arm observations

| Arm | Offered | Admitted | Offered attainment | Admitted attainment | Mean latency / offered (ms) | V2I admitted | Forwarded share | Execution-share range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
"""
    for arm in ("off", "jsq", "dla"):
        r = records[arm]
        report += (
            f"| `{arm}` | {r['offered_tasks']:,} | {r['admitted_tasks']:,} | "
            f"{r['offered_task_deadline_attainment']:.9f} | "
            f"{r['admitted_task_deadline_attainment']:.9f} | "
            f"{r['latency_ms_per_offered_task']:.3f} | "
            f"{r['v2i_path_metrics']['v2i_admitted_tasks']:,} | "
            f"{r['v2i_path_metrics']['forwarded_share_of_admitted_v2i']:.9f} | "
            f"{r['v2i_path_metrics']['imbalance_diagnostic']['value']:.9f} |\n"
        )
    report += f"""

## Declared contrasts

- Placement contrast, JSQ minus off: offered-task attainment difference
  `{placement['differences_candidate_minus_reference']['offered_task_deadline_attainment']:+.9f}`;
  direct observation: {placement['direct_primary_observation']}.
- Admission contrast, DLA minus JSQ: offered-task attainment difference
  `{admission['differences_candidate_minus_reference']['offered_task_deadline_attainment']:+.9f}`;
  direct observation: {admission['direct_primary_observation']}. `dla` is JSQ
  placement plus deadline-aware admission, not deadline-aware placement alone.
- The DLA-minus-off row in the comparison JSON is a joint
  placement-plus-admission contrast.

Queue balance and deadline attainment are reported separately; a reduction in
imbalance is not treated as proof of better deadlines.

## Validity and limitations

""" + "\n".join(f"- {item}" for item in comparisons["limitations"]) + "\n"
    report_doc.write_text(report)

    supervisor = f"""# Supervisor-facing E2 pilot summary — 9 August 2026

E1 remains closed. The single authorised E2 fleet draw completed all gates.
JSQ-minus-off changed offered-task deadline attainment by
`{placement['differences_candidate_minus_reference']['offered_task_deadline_attainment']:+.9f}`.
DLA-minus-JSQ, which isolates added deadline-aware admission under JSQ,
changed it by `{admission['differences_candidate_minus_reference']['offered_task_deadline_attainment']:+.9f}`.
These are raw one-draw observations only. Researcher review is required before
any additional E2 seed or E3/backhaul/scaling/learning work.
"""
    supervisor_doc.write_text(supervisor)

    raw_index, raw_checksums = write_raw_evidence_index(raw_root)
    evidence = {
        "schema_version": "e2_native_placement_evidence_index_v1",
        "manifest": {"path": str(args.manifest.resolve()), "sha256": sha256(args.manifest)},
        "raw_root": str(raw_root.resolve()),
        "raw_index": {"path": str(raw_index), "sha256": sha256(raw_index)},
        "raw_checksums": {"path": str(raw_checksums), "sha256": sha256(raw_checksums)},
        "documents": [
            {"path": str(path.resolve()), "sha256": sha256(path)}
            for path in (validation_doc, comparison_doc, path_doc, report_doc, supervisor_doc)
        ],
        "full_run_locators": {
            arm: records[arm]["raw_output"] for arm in ("off", "jsq", "dla")
        },
    }
    evidence_doc.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": "completed",
        "comparison": str(comparison_doc),
        "report": str(report_doc),
        "evidence_index": str(evidence_doc),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

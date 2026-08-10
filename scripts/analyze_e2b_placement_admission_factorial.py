#!/usr/bin/env python3
"""Deterministic four-cell E2b mechanism-decomposition analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analyze_e2_native_placement_pilot import SCALAR_PATHS, arm_record, at, contrast


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum_ledger(root: Path, ledger: Path) -> None:
    for line in ledger.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            raise SystemExit(f"completed E2 checksum mismatch: {path}")


def interaction(records: dict[str, dict]) -> dict:
    values = {
        name: float(
            at(records["dla"], path)
            - at(records["jsq"], path)
            - at(records["ingress_dla"], path)
            + at(records["off"], path)
        )
        for name, path in SCALAR_PATHS.items()
    }
    return {
        "formula": "DLA - JSQ - ingress_dla + off",
        "differences": values,
        "statistical_interpretation": (
            "Raw one-draw placement-by-admission interaction only; no confidence "
            "interval, task-level replication, population inference, or superiority claim."
        ),
    }


def observation(value: float) -> str:
    if value == 0.0:
        return "numerical equality in this draw; no equivalence claim"
    return "higher observed value" if value > 0.0 else "lower observed value"


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
        "schema_version": "e2b_raw_evidence_index_v1",
        "root": str(raw_root.resolve()),
        "files": [
            {"path": str(path.relative_to(raw_root)), "bytes": path.stat().st_size,
             "sha256": sha256(path)}
            for path in raw_files
        ],
    }
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    checksum_path.write_text("\n".join(
        f"{sha256(path)}  {path.relative_to(raw_root)}"
        for path in raw_files + [index_path]
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

    e2 = manifest["completed_e2_reuse"]
    e2_ledger = Path(e2["raw_checksums"]["path"])
    if sha256(e2_ledger) != e2["raw_checksums"]["sha256"]:
        raise SystemExit("completed E2 root ledger hash drifted")
    verify_checksum_ledger(Path(e2["raw_root"]), e2_ledger)
    completed_comparison_path = Path(e2["comparison"]["path"])
    if sha256(completed_comparison_path) != e2["comparison"]["sha256"]:
        raise SystemExit("completed E2 comparison hash drifted")
    completed = json.loads(completed_comparison_path.read_text())

    outputs = {
        "validation": args.docs_dir / "e2b_placement_admission_factorial_validation_v1.json",
        "comparison": args.docs_dir / "e2b_placement_admission_factorial_comparison_v1.json",
        "path": args.docs_dir / "e2b_placement_admission_path_summary_v1.json",
        "report": args.docs_dir / "e2b_placement_admission_factorial_report_2026-08-10.md",
        "supervisor": args.docs_dir / "e2b_placement_admission_supervisor_summary_2026-08-10.md",
        "evidence": args.docs_dir / "e2b_placement_admission_evidence_index_v1.json",
    }
    collisions = [path for path in outputs.values() if path.exists()]
    if collisions or (raw_root / "raw_evidence_index.json").exists() \
            or (raw_root / "checksums.sha256").exists():
        raise SystemExit(f"refusing to overwrite analysis evidence: {collisions}")
    args.docs_dir.mkdir(parents=True, exist_ok=True)

    records = {name: completed["arms"][name] for name in ("off", "jsq", "dla")}
    records["ingress_dla"] = arm_record(
        raw_root / "full" / "ingress_dla" / "run_1"
    )
    contrasts = {
        "placement_without_gate": contrast(
            records, "jsq", "off", "JSQ minus strongest-link with ordinary admission"
        ),
        "placement_with_gate": contrast(
            records, "dla", "ingress_dla",
            "JSQ-DLA minus strongest-link ingress-DLA with the same deadline gate",
        ),
        "admission_under_strongest_link": contrast(
            records, "ingress_dla", "off",
            "deadline-aware admission minus ordinary admission under strongest-link execution",
        ),
        "admission_under_jsq": contrast(
            records, "dla", "jsq",
            "deadline-aware admission minus ordinary admission under JSQ placement",
        ),
    }
    interaction_record = interaction(records)
    comparison = {
        "schema_version": "e2b_placement_admission_factorial_comparison_v1",
        "statistical_status": "one-seed descriptive mechanism-decomposition pilot",
        "primary_outcome": "offered-task deadline attainment",
        "factorial_table": {
            "strongest_link": {"gate_off": "off", "gate_on": "ingress_dla"},
            "jsq": {"gate_off": "jsq", "gate_on": "dla"},
        },
        "arms": records,
        "contrasts": contrasts,
        "interaction": interaction_record,
        "limitations": [
            "One evaluator seed and one fleet draw; no confidence interval or population inference.",
            "Tasks are accounting records, not independent statistical replicates.",
            "Three cells are immutable completed E2 outputs reused by exact hash; only ingress_dla is new.",
            "The frozen 17-dimensional actor does not observe current RSU load.",
            "Zero backhaul represents ideal fibre and ingress_dla performs no forwarding.",
            "One Manchester incident hour, one provisional UK-2030 fleet, one cap and fixed 1x service were tested.",
            "Deadline success is evaluator success, not confirmed physical task return.",
            "No ordinary-traffic control, scaling, P2C, learning, retraining, deployment, or Kubernetes execution was tested.",
        ],
    }
    validation = {
        "schema_version": "e2b_placement_admission_factorial_validation_v1",
        "status": "passed",
        "manifest_sha256": sha256(args.manifest),
        "existing_arm_no_effect": json.loads(Path(
            manifest["gates"]["existing_arm_no_effect"]["path"]
        ).read_text()),
        "two_rsu_production_probe": json.loads(Path(
            manifest["gates"]["two_rsu_production_probe"]["path"]
        ).read_text()),
        "smoke_validation": json.loads((raw_root / "smoke_validation.json").read_text()),
        "full_validation": full_validation,
        "completed_e2_root_checksums_verified": True,
    }
    ingress_record = records["ingress_dla"]
    gate_by_ingress = full_validation["runs"][0][
        "gate_rejection_count_by_ingress_rsu"
    ]
    path_summary = {
        "schema_version": "e2b_placement_admission_path_summary_v1",
        "ingress_dla": ingress_record["v2i_path_metrics"],
        "gate_rejection_count_by_ingress_rsu": gate_by_ingress,
        "completed_e2_paths_reused": {
            arm: records[arm]["v2i_path_metrics"] for arm in ("off", "jsq", "dla")
        },
        "definitions": {
            "ingress_dla": "strongest-link execution plus the same deadline-aware admission gate used by dla",
            "forwarded": "admitted V2I with execution RSU different from strongest-link ingress",
            "execution_share_range": "max(per-RSU execution share) - min(per-RSU execution share)",
        },
    }
    outputs["validation"].write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n")
    outputs["comparison"].write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    outputs["path"].write_text(json.dumps(path_summary, indent=2, sort_keys=True) + "\n")

    primary = {
        name: item["differences_candidate_minus_reference"][
            "offered_task_deadline_attainment"
        ]
        for name, item in contrasts.items()
    }
    primary["interaction"] = interaction_record["differences"][
        "offered_task_deadline_attainment"
    ]
    report = f"""# E2b placement × admission factorial report — 10 August 2026

## Status and evidence boundary

The one authorised `ingress_dla` arm completed the predeclared review, repeated-smoke,
path, accounting and conservation gates. The completed E2 `off`, `jsq` and `dla` cells were
reused only after exact checksum verification. This is one-draw descriptive evidence, not
confirmatory or multi-seed evidence.

## Four-cell observations

| Placement | Gate off | Gate on |
|---|---:|---:|
| Strongest-link | `off` {records['off']['offered_task_deadline_attainment']:.9f} | `ingress_dla` {records['ingress_dla']['offered_task_deadline_attainment']:.9f} |
| JSQ | `jsq` {records['jsq']['offered_task_deadline_attainment']:.9f} | `dla` {records['dla']['offered_task_deadline_attainment']:.9f} |

`ingress_dla` offered {ingress_record['offered_tasks']:,} tasks, admitted
{ingress_record['admitted_tasks']:,}, met {ingress_record['deadline_met_tasks']:,} deadlines,
and admitted {ingress_record['v2i_path_metrics']['v2i_admitted_tasks']:,} V2I tasks. Its offered
attainment was {ingress_record['offered_task_deadline_attainment']:.9f}; admitted attainment was
{ingress_record['admitted_task_deadline_attainment']:.9f}.

## Declared offered-attainment contrasts

- Placement without gate, JSQ minus off: `{primary['placement_without_gate']:+.9f}`.
- Placement with gate, DLA minus ingress-DLA: `{primary['placement_with_gate']:+.9f}`.
- Admission under strongest-link, ingress-DLA minus off: `{primary['admission_under_strongest_link']:+.9f}`.
- Admission under JSQ, DLA minus JSQ: `{primary['admission_under_jsq']:+.9f}`.
- Placement × admission interaction, DLA - JSQ - ingress-DLA + off: `{primary['interaction']:+.9f}`.

For the primary placement-with-gate question, the direct observation is
{observation(primary['placement_with_gate'])}. Close values are not treated as equivalent.
The JSON comparison repeats all contrasts for admitted attainment, offered/admitted latency,
admitted tasks, admitted V2I, gate and cap rejection, execution imbalance and energy per offered task.

## Path, forwarding and conservation

`ingress_dla` selected strongest-link ingress for every V2I attempt. It forwarded
{ingress_record['v2i_path_metrics']['forwarded_admitted_task_count']} tasks, charged
{ingress_record['v2i_path_metrics']['total_forwarding_latency_ms']:.1f} ms total forwarding
latency, and all admitted execution lay on the ingress-to-ingress matrix diagonal. Gate-rejected
tasks retained their selected ingress, had actual execution `-1`, and were not enqueued. Task,
V2I-work and vehicle-work conservation passed.

## Limitations

""" + "\n".join(f"- {item}" for item in comparison["limitations"]) + "\n"
    outputs["report"].write_text(report)
    outputs["supervisor"].write_text(f"""# Supervisor-facing E2b summary — 10 August 2026

The single missing strongest-link-plus-deadline-gate cell completed all gates. DLA minus
ingress-DLA changed offered-task deadline attainment by `{primary['placement_with_gate']:+.9f}`;
ingress-DLA minus off changed it by `{primary['admission_under_strongest_link']:+.9f}`; and the
placement × admission interaction was `{primary['interaction']:+.9f}`. These are raw one-draw
mechanism observations only. Researcher review is the next decision gate.
""")

    raw_index, raw_checksums = write_raw_evidence_index(raw_root)
    evidence = {
        "schema_version": "e2b_placement_admission_evidence_index_v1",
        "manifest": {"path": str(args.manifest.resolve()), "sha256": sha256(args.manifest)},
        "raw_root": str(raw_root.resolve()),
        "raw_index": {"path": str(raw_index), "sha256": sha256(raw_index)},
        "raw_checksums": {"path": str(raw_checksums), "sha256": sha256(raw_checksums)},
        "new_full_run": ingress_record["raw_output"],
        "completed_e2_full_runs": {
            arm: records[arm]["raw_output"] for arm in ("off", "jsq", "dla")
        },
        "documents": [
            {"path": str(outputs[name].resolve()), "sha256": sha256(outputs[name])}
            for name in ("validation", "comparison", "path", "report", "supervisor")
        ],
    }
    outputs["evidence"].write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "status": "completed",
        "comparison": str(outputs["comparison"]),
        "report": str(outputs["report"]),
        "evidence_index": str(outputs["evidence"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

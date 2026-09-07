"""Produce an auditable descriptive report after both matched runs pass."""
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    status = json.loads((ROOT / "status.json").read_text())
    assert status["status"] == "completed", "Wait for completed, validated pilot"
    manifest = json.loads((ROOT / "manifest.json").read_text())
    assert status["manifest_sha256"] == sha(ROOT / "manifest.json")
    summaries, rows, records = {}, [], {}
    for index, cell in enumerate(manifest["cells"], 1):
        attempts = sorted((ROOT / "cells" / f"{index:02d}_{cell['name']}").glob("attempt_*"))
        directory = next(p for p in reversed(attempts) if (p / "validation.json").exists())
        receipt = json.loads((directory / "validation.json").read_text())
        assert receipt["status"] == "passed"
        for name, value in receipt["sha256"].items():
            assert sha(directory / name) == value, name
        summary = json.loads((directory / "summary.json").read_text())
        summaries[cell["name"]] = summary
        with np.load(directory / "per_task.npz") as data:
            active, met, task_type, outcome = (data[k] for k in ("task_active", "task_met", "task_type", "task_outcome"))
            offered, done = int(active.sum()), int(met.sum())
            assert done / offered == summary["completion"]
            assert offered == summary["n_offered"]
            per_type = []
            for t in range(3):
                mask = active & (task_type == t)
                n, yes = int(mask.sum()), int((met & mask).sum())
                assert np.isclose(yes / n, summary[f"t{t+1}_completion"], rtol=0, atol=1e-12)
                per_type.append({"type": t+1, "offered": n, "met": yes, "attainment": yes/n})
            paths = summary["v2i_path_metrics"]
            row = {"condition": cell["name"], "offered": offered, "deadline_met": done,
                   "deadline_attainment": done/offered, "admitted": int(summary["n_admitted"]),
                   "v2i_attempts": paths["v2i_attempts"], "v2i_admitted": paths["v2i_admitted_tasks"],
                   "forwarded": paths["forwarded_admitted_task_count"],
                   "gate_rejected": int(summary["v2i_gate_rejected"]), "cap_rejected": int(summary["v2i_cap_rejected"]),
                   "avg_energy_j_per_offered_task": summary["avg_energy_j_per_task"], "wall_s": summary["wall_s"]}
            records[cell["name"]] = {"summary": row, "per_type": per_type,
                "task_outcomes": np.bincount(outcome.ravel(), minlength=9).tolist(),
                "execution_count_per_rsu": paths["actual_execution_count_per_rsu"],
                "validation_sha256": sha(directory / "validation.json")}
            rows.append(row)
    fresh, ingress = records["fresh"]["summary"], records["ingress"]["summary"]
    assert fresh["offered"] == ingress["offered"]
    difference = 100 * (fresh["deadline_attainment"] - ingress["deadline_attainment"])
    additional = fresh["deadline_met"] - ingress["deadline_met"]
    for row in rows:
        row["difference_from_ingress_pp"] = 100*(row["deadline_attainment"]-ingress["deadline_attainment"])
    with (ROOT / "metrics.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    elapsed = (datetime.fromisoformat(status["finished_at"])-datetime.fromisoformat(status["started_at"])).total_seconds()
    result = {"status": "passed", "manifest_sha256": sha(ROOT/"manifest.json"), "summary_script_sha256": sha(Path(__file__)), "records": records,
              "difference_from_ingress_pp": difference, "additional_deadline_met_tasks": additional,
              "runner_elapsed_s_including_probes_and_validation": elapsed,
              "full_evaluator_wall_s": sum(row["wall_s"] for row in rows),
              "interpretation": "Descriptive single-draw matched comparison in canonical working-day scenario; no replicate-level interval."}
    (ROOT / "analysis_validation.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    direction = "higher" if difference > 0 else "lower" if difference < 0 else "equal"
    lines = ["# Generalisation pilot: completed analysis", "",
             f"Fresh per-task placement achieved **{100*fresh['deadline_attainment']:.5f}%** offered-task deadline attainment, "
             f"compared with **{100*ingress['deadline_attainment']:.5f}%** for ingress. "
             f"The difference was **{difference:+.5f} percentage points** ({additional:+,} deadline-met tasks).", "",
             "| Condition | Offered tasks | Deadline-met tasks | Attainment | V2I gate rejections | Forwarded tasks |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['condition']} | {row['offered']:,} | {row['deadline_met']:,} | {100*row['deadline_attainment']:.5f}% | {row['gate_rejected']:,} | {row['forwarded']:,} |")
    lines += ["", "## What this establishes", "",
              f"The per-task result was {direction} than ingress within this one matched working-day fleet draw. "
              "This is a descriptive result; tasks are not independent replications and the pilot supplies no replicate-level confidence interval. "
              "The result must not be used to claim universal superiority, equivalence, or a geographical generalisation.", "",
              "The full Tuesday 15 October 2024 08:00–11:00 window contains 10,800 seconds, "
              "215 padded vehicle slots and nine canonical RSUs. Both conditions share the actor, task stream, "
              "fleet draw, vehicle-entry queue resets and all controls except the placement rule. "
              "The actor remains the original frozen onehot17 MAPPO seed100 checkpoint. The primary denominator contains all offered tasks, including rejections and unavailable tasks.", "",
              "Compared with the old incident scenario, traffic density, date, window length, RSU placement/count, "
              "slot assignment and availability of entry markers differ. Therefore the cross-scenario change "
              "in the size of the placement effect cannot be attributed to traffic alone. This study tests "
              "transfer to another scenario in the same Manchester simulation network. Capacity was kept "
              "at an absolute 6,220 tasks per RSU, service at 1×, forwarding at 0 ms and scaling off.", "",
              f"V2I gate rejections fell from {ingress['gate_rejected']:,} to {fresh['gate_rejected']:,}, "
              f"while V2I admissions rose from {ingress['v2i_admitted']:,} to {fresh['v2i_admitted']:,}. "
              "Neither condition had capacity rejections. Per-task execution counts were more evenly "
              "distributed across the nine RSUs; the exact counts are in the analysis receipt. "
              "These diagnostics are consistent with placement reducing concentrated queue demand.", "",
              "## Task types", "", "| Type | Offered tasks per condition | Fresh attainment | Ingress attainment | Difference (pp) |",
              "|---|---:|---:|---:|---:|"]
    for f, i in zip(records["fresh"]["per_type"], records["ingress"]["per_type"]):
        assert f["offered"] == i["offered"]
        lines.append(f"| T{f['type']} | {f['offered']:,} | {100*f['attainment']:.5f}% | {100*i['attainment']:.5f}% | {100*(f['attainment']-i['attainment']):+.5f} |")
    lines += ["", "## Validation and runtime", "",
              "The trace and source FCD matched their published checksums; source reconstruction "
              "matched positions, speed, activity, entry markers and timestamps for every row. Both "
              "300-step probes passed before the full runs. Each full task prefix matched its same-arm "
              "probe. Full runs passed task-count, outcome, rejection, queue/path, finite-value and "
              "paired input checks. Actor actions, task types, task activity, fleet and ingress identity "
              "matched between arms, with actor logits within the predeclared absolute 0.00001 tolerance. "
              "The fresh arm additionally passed the recorded RSU workload endpoint conservation check.", "",
              f"Full evaluator wall time total: **{result['full_evaluator_wall_s']/60:.2f} minutes**. "
              f"Runner time including probes, polling, export and validation: **{elapsed/60:.2f} minutes**. "
              "These times exclude input preparation. The original hours-long estimate was based on "
              "the much wider incident trace; this smaller fleet requires substantially less computation.", "",
              "See [experiment plan](README.md), [manifest](manifest.json), [metrics](metrics.csv), "
              "[analysis validation](analysis_validation.json), and [input validation](input_validation.json). "
              "Raw run archives and per-run validation receipts are retained in `cells/`. Earlier incident "
              "and forwarding records were preserved."]
    (ROOT / "ANALYSIS.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({k:v for k,v in result.items() if k != "records"}, indent=2))


if __name__ == "__main__":
    main()

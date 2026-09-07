"""Prespecified draw-level three-arm analysis; no task-level inference."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import t

CONTRASTS = (("per_task", "ingress"), ("common_target", "ingress"), ("per_task", "common_target"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8*1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows):
    with Path(path).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def paired_interval(values):
    x = np.asarray(values, dtype=np.float64)
    assert len(x) == 4 and np.isfinite(x).all()
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    se = sd / np.sqrt(len(x))
    margin = float(t.ppf(.975, 3)) * se
    simultaneous_margin = float(t.ppf(1-.05/(2*3), 3)) * se
    return {"mean_pp": mean, "sd_pp": sd, "min_pp": float(x.min()), "max_pp": float(x.max()),
            "ci95_low_pp": mean-margin, "ci95_high_pp": mean+margin,
            "family95_low_pp": mean-simultaneous_margin, "family95_high_pp": mean+simultaneous_margin}


def verify_receipt(directory):
    receipt = json.loads((directory/"validation.json").read_text())
    assert receipt["status"] == "passed"
    for name, expected in receipt["sha256"].items():
        assert sha(directory/name) == expected, f"Changed output: {directory/name}"
    return receipt


def analyze(root, m, completed):
    root = Path(root)
    assert set(completed) == {c["id"] for c in m["cells"]}
    assert sha(root/"analysis.py") == m["analysis_sha256"]
    rows, workloads, types = [], [], []
    summaries = {}
    for cell in m["cells"]:
        directory = Path(completed[cell["id"]])
        receipt = verify_receipt(directory)
        s = json.loads((directory/"summary.json").read_text())
        w = json.loads((directory/"workload_validation.json").read_text())
        assert w["status"] == "passed" and s["fleet_seed"] == cell["fleet_seed"]
        with np.load(directory/"per_task.npz") as task:
            active, met, kind = task["task_active"], task["task_met"], task["task_type"]
            offered, successes = int(active.sum()), int(met.sum())
            assert offered == s["n_offered"] and successes/offered == s["completion"]
            for task_type in range(3):
                chosen = active & (kind == task_type)
                n, done = int(chosen.sum()), int((chosen & met).sum())
                assert abs(done/n - s[f"t{task_type+1}_completion"]) < 1e-12
                types.append({"fleet_seed": cell["fleet_seed"], "arm": cell["name"], "task_type": task_type+1,
                              "offered": n, "deadline_met": done, "deadline_attainment": done/n})
        row = {"fleet_seed": cell["fleet_seed"], "arm": cell["name"], "mode": cell["mode"],
               "offered": offered, "deadline_met": successes, "attainment_pct": 100*s["completion"],
               "admitted": int(s["n_admitted"]), "gate_rejected": int(s["v2i_gate_rejected"]),
               "cap_rejected": int(s["v2i_cap_rejected"]), "local_mqd_rejected": int(s["local_mqd_rejected"]),
               "v2v_mqd_rejected": int(s["v2v_mqd_rejected"]), "v2i_unavailable": int(s["v2i_unavailable"]),
               "v2v_unavailable": int(s["v2v_unavailable"]), "forwarded": s["v2i_path_metrics"]["forwarded_admitted_task_count"],
               "energy_j_per_offered_task": s["avg_energy_j_per_task"], "wall_s": s["wall_s"],
               "validation_sha256": sha(directory/"validation.json")}
        rows.append(row); summaries[(cell["fleet_seed"], cell["name"])] = row
        for rsu in range(m["rsus"]):
            workloads.append({"fleet_seed": cell["fleet_seed"], "arm": cell["name"], "rsu": rsu,
                "executed_tasks": s["v2i_path_metrics"]["actual_execution_count_per_rsu"][rsu],
                **{key:w[key][rsu] for key in ("admitted_work_ms_per_rsu", "admitted_work_share_per_rsu",
                   "mean_post_batch_workload_ms_per_rsu", "p95_post_batch_workload_ms_per_rsu",
                   "maximum_post_batch_workload_ms_per_rsu", "service_utilisation_per_rsu")}})
    paired = []
    for seed in m["primary_fleet_seeds"]:
        entries = [summaries[(seed, arm)] for arm in ("ingress", "common_target", "per_task")]
        assert len({r["offered"] for r in entries}) == 1
        row = {"fleet_seed": seed, **{r["arm"]+"_pct": r["attainment_pct"] for r in entries}}
        for left, right in CONTRASTS:
            row[f"{left}_minus_{right}_pp"] = summaries[(seed,left)]["attainment_pct"]-summaries[(seed,right)]["attainment_pct"]
        row["historical_reversal_order"] = row["common_target_pct"] < row["ingress_pct"] < row["per_task_pct"]
        paired.append(row)
    contrasts = []
    for left, right in CONTRASTS:
        contrasts.append({"contrast":f"{left}_minus_{right}", "n_fleet_draws":4,
                          **paired_interval([r[f"{left}_minus_{right}_pp"] for r in paired])})
    arm_summary = [{"arm": arm, "n_fleet_draws":4,
                    "mean_attainment_pct":float(np.mean([summaries[(seed,arm)]["attainment_pct"] for seed in m["primary_fleet_seeds"]])),
                    "sd_attainment_pct":float(np.std([summaries[(seed,arm)]["attainment_pct"] for seed in m["primary_fleet_seeds"]],ddof=1))}
                   for arm in ("ingress", "common_target", "per_task")]
    # The pilot contributes solely to a separately labelled two-arm summary.
    pilot = Path(m["pilot_directory"])
    pilot_values = {}
    for arm, folder in (("per_task","01_fresh"),("ingress","02_ingress")):
        directory = pilot/"cells"/folder/"attempt_001"
        verify_receipt(directory)
        s = json.loads((directory/"summary.json").read_text())
        assert s["fleet_seed"] == 1 and s["T"] == m["steps"] and s["rsu_max_concurrent"] == m["rsu_capacity_tasks"]
        pilot_values[arm] = s["completion"]*100
    supplementary = []
    for seed in range(5):
        vals = pilot_values if seed == 1 else {arm:summaries[(seed,arm)]["attainment_pct"] for arm in ("ingress","per_task")}
        supplementary.append({"fleet_seed":seed, "role":"already inspected exploratory pilot" if seed==1 else "new primary draw",
                              "ingress_pct":vals["ingress"], "per_task_pct":vals["per_task"],
                              "difference_pp":vals["per_task"]-vals["ingress"]})
    sup_values = [r["difference_pp"] for r in supplementary]
    mean_reversal = contrasts[0]["mean_pp"] > 0 and contrasts[1]["mean_pp"] < 0
    supported = contrasts[0]["family95_low_pp"] > 0 and contrasts[1]["family95_high_pp"] < 0
    result = {"status":"passed", "manifest_sha256":sha(root/"manifest.json"), "analysis_script_sha256":sha(__file__),
              "primary_seeds":m["primary_fleet_seeds"], "primary_arm_summary":arm_summary, "primary_paired":paired,
              "primary_contrasts":contrasts, "historical_reversal_in_arm_means":bool(mean_reversal),
              "historical_reversal_in_individual_draws":int(sum(r["historical_reversal_order"] for r in paired)),
              "historical_reversal_supported_by_simultaneous_intervals":bool(supported),
              "supplementary_including_pilot":{"rows":supplementary, "mean_difference_pp":float(np.mean(sup_values)),
                                               "minimum_pp":min(sup_values), "maximum_pp":max(sup_values)},
              "full_evaluator_wall_s":sum(r["wall_s"] for r in rows),
              "limits":"Four fleet draws; paired t intervals conditional on distributional assumptions, fixed task seed and canonical Manchester morning scenario. Pilot excluded from primary."}
    for name, data in (("runs",rows),("paired_differences",paired),("paired_intervals",contrasts),("arm_summary",arm_summary),
                       ("rsu_workload_distribution",workloads),("task_types",types),("supplementary_five_draws",supplementary)):
        write_csv(root/f"{name}.csv",data)
    (root/"analysis_validation.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    lines = ["# Three-arm morning replication: results", "",
             "Primary analysis uses only the four new fleet draws: **0, 2, 3 and 4**. "
             "All twelve full runs passed the declared validation. The earlier seed-1 pilot is kept in a separate supplementary summary.", "",
             "| Arm | Mean deadline attainment | SD across fleet draws |", "|---|---:|---:|"]
    for row in arm_summary:
        lines.append(f"| {row['arm']} | {row['mean_attainment_pct']:.5f}% | {row['sd_attainment_pct']:.5f} pp |")
    lines += ["", "## Paired primary comparisons", "",
              "| Contrast | Mean difference (pp) | Paired 95% t interval | Simultaneous 95% family interval |",
              "|---|---:|---:|---:|"]
    for r in contrasts:
        lines.append(f"| {r['contrast']} | {r['mean_pp']:+.5f} | [{r['ci95_low_pp']:+.5f}, {r['ci95_high_pp']:+.5f}] | [{r['family95_low_pp']:+.5f}, {r['family95_high_pp']:+.5f}] |")
    lines += ["", "The intervals use paired fleet-draw differences (n=4, df=3), never individual tasks. "
              "Family intervals use the predeclared Bonferroni correction across the three contrasts. "
              "These small-sample parametric intervals depend on assumptions about the draw-level distribution; "
              "they do not represent uncertainty across traffic dates, task seeds or geographic settings.", "",
              "## Each new draw", "",
              "| Fleet seed | Ingress | Common-target | Per-task | Per-task − ingress (pp) | Common − ingress (pp) | Per-task − common (pp) |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for r in paired:
        lines.append(f"| {r['fleet_seed']} | {r['ingress_pct']:.5f}% | {r['common_target_pct']:.5f}% | {r['per_task_pct']:.5f}% | {r['per_task_minus_ingress_pp']:+.5f} | {r['common_target_minus_ingress_pp']:+.5f} | {r['per_task_minus_common_target_pp']:+.5f} |")
    lines += ["", "## Ranking question", "",
              f"The historical ordering **common-target < ingress < per-task** occurred in "
              f"**{result['historical_reversal_in_individual_draws']} of 4** new draws. "
              f"It {'did' if mean_reversal else 'did not'} hold for the arm means. "
              f"The simultaneous-interval criterion for that reversal {'was' if supported else 'was not'} met.", "",
              "A different ordering is retained as evidence about the scope of the implementation effect. "
              "Cross-scenario changes in that ordering cannot identify which difference caused them: "
              "the morning and incident cases also differ in density, date/window, RSU layout/count, and slot/entry conventions.", "",
              "## Supplementary five-draw two-arm summary", "",
              "This table includes the already inspected pilot, which influenced the decision to replicate. "
              "It is descriptive and is not five previously unseen confirmation draws. No pilot common-target cell was added or imputed.", "",
              "| Seed | Role | Ingress | Per-task | Difference (pp) |", "|---|---|---:|---:|---:|"]
    for r in supplementary:
        lines.append(f"| {r['fleet_seed']} | {r['role']} | {r['ingress_pct']:.5f}% | {r['per_task_pct']:.5f}% | {r['difference_pp']:+.5f} |")
    lines += ["", f"Descriptive five-draw mean difference: **{np.mean(sup_values):+.5f} pp**; range **[{min(sup_values):+.5f}, {max(sup_values):+.5f}] pp**.", "",
              "## Controls, diagnostics and reproducibility", "",
              "All arms used the same canonical 10,800-second morning trace, nine RSUs, frozen actor, "
              "absolute 6,220-task RSU capacity, 1× service, zero forwarding cost and per-visit vehicle queue resets. "
              "The three arms retained their frozen admission implementations and three reconciliation passes. "
              "This tests fleet variability within another Manchester scenario, not independent geographic generalisation.", "",
              "All arms passed matched input/action checks, exact task accounting and RSU workload reconstruction, "
              "including service-work conservation and per-second task-count carry. Common-target broadcast and "
              "least-workload selection were checked. Exact errors and input/output hashes are retained with each run.", "",
              f"Total full-evaluator wall time: **{result['full_evaluator_wall_s']/60:.2f} minutes**, excluding probes, export and validation.", "",
              "See [prespecified protocol](PROTOCOL.md), [manifest](manifest.json), [per-run metrics](runs.csv), "
              "[rejection counts](runs.csv), [RSU workload distribution](rsu_workload_distribution.csv), "
              "[task-type outcomes](task_types.csv), and [analysis receipt](analysis_validation.json)."]
    (root/"RESULTS.md").write_text("\n".join(lines)+"\n")
    return result

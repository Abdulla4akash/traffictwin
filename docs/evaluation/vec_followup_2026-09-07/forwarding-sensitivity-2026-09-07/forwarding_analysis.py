"""Qualify and apply fixed forwarding costs to immutable pilot task records."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
DEADLINES = np.array([100., 500., 100.], dtype=np.float32)
CHANGED_STEP_FIELDS = {"done", "lat_sum", "veh_done"}
CHANGED_TASK_FIELDS = {"task_lat_ms", "task_met", "task_outcome", "task_forwarding_latency_ms"}


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def require(condition, message):
    if not bool(condition):
        raise RuntimeError(message)


def exact(a, b):
    return a.shape == b.shape and a.dtype == b.dtype and a.tobytes() == b.tobytes()


def transform(task, cost):
    """Float32 addition, restricted to admitted forwarded tasks.

    Archived penalty-equal latencies are ambiguous for point-latency recovery.
    At positive cost return NaN for those latency points. They were already
    misses and remain misses under either interpretation at nonnegative cost.
    Thus deadline outcomes are identifiable without claiming a latency value.
    """
    require(np.isfinite(cost) and 0 <= cost <= 10, "Cost outside qualified 0..10ms domain")
    active = task["task_active"]
    old_outcome = task["task_outcome"]
    admitted = (old_outcome == 1) | (old_outcome == 2)
    forwarded = task["task_forwarded"]
    lat = task["task_lat_ms"]
    deadlines = DEADLINES[task["task_type"]]
    require(lat.dtype == np.float32 and np.isfinite(lat).all(), "Expected finite float32 latencies")
    require(np.all(~forwarded | (active & admitted & task["task_v2i_admitted"])), "Forwarding includes rejected/non-V2I work")
    require(np.all(task["task_forwarding_latency_ms"] == 0), "Input already includes forwarding costs")
    ambiguous = forwarded & (lat == 10 * deadlines)
    require(not np.any(ambiguous & task["task_met"]), "Penalty-like task marked successful")
    require(not np.any(forwarded & (lat >= 1e8 - 16)), "Forwarded latency near clipping threshold")
    derived_lat = lat.copy()
    derived_lat[forwarded] = np.add(lat[forwarded], np.float32(cost), dtype=np.float32)
    if cost > 0:
        derived_lat[ambiguous] = np.nan
    met = active & (derived_lat <= deadlines)
    require(not np.any(met & ~admitted), "Rejected task reconstructed as successful")
    outcome = old_outcome.copy()
    outcome[admitted] = np.where(met[admitted], 1, 2).astype(np.int8)
    return {"task_lat_ms":derived_lat, "task_met":met, "task_outcome":outcome,
            "task_forwarding_latency_ms":np.where(forwarded, np.float32(cost), np.float32(0)),
            "point_latency_ambiguous":ambiguous & (cost > 0)}


def verify_receipt(directory, receipt_name="validation.json", aliases=None):
    directory = Path(directory)
    receipt = json.loads((directory / receipt_name).read_text())
    require(receipt["status"] == "passed", f"Validation not passed: {directory}")
    for name, expected in receipt["sha256"].items():
        require(sha(directory / name) == expected, f"Archive changed: {directory/name}")
    return receipt


def verify_identity(m):
    require(sha(__file__) == m["analysis_script_sha256"], "Analysis script changed")
    code = Path(m["code_checkout"])
    head = subprocess.check_output(["git","-C",str(code),"rev-parse","HEAD"],text=True).strip()
    require(head == m["code_commit"], "Evaluator commit changed")
    for name, expected in m["source_sha256"].items():
        require(sha(code/name) == expected, f"Source changed: {name}")
    for name in ("trace","actor"):
        require(sha(m[name]["path"]) == m[name]["sha256"], f"Input changed: {name}")
    require(platform.python_version() == m["runtime"]["python"], "Python version differs")
    for package, version in m["runtime"]["packages"].items():
        require(importlib.metadata.version(package) == version, f"Package differs: {package}")


def qualify(m):
    verify_identity(m)
    target = ROOT / "qualification"
    target.mkdir()
    fresh = Path(m["fresh_input"])
    base_smoke = Path(m["zero_smoke"])
    verify_receipt(fresh)
    verify_receipt(m["ingress_input"])
    old_receipt = json.loads(Path(m["zero_smoke_receipt"]).read_text())
    require(old_receipt["status"] == "passed", "Zero smoke receipt failed")
    for name in ("step.npz", "task.npz", "summary.json"):
        require(sha(base_smoke/name) == old_receipt["raw_artifact_sha256"][f"0/{name}"], f"Zero smoke changed: {name}")
    with np.load(base_smoke/"task.npz") as z, np.load(base_smoke/"step.npz") as zs:
        zero_task, zero_step = dict(z), dict(zs)
    zero_summary = json.loads((base_smoke/"summary.json").read_text())
    baseline = transform(zero_task, 0)
    require(all(exact(baseline[k], zero_task[k]) for k in CHANGED_TASK_FIELDS), "Zero smoke reconstruction failed")
    # T=10 versus T=3600 can compile separately: bind prefix arrays explicitly.
    for file, prefix in (("per_task.npz",zero_task),("per_step.npz",zero_step)):
        with np.load(fresh/file) as full:
            for name, expected in prefix.items():
                actual = full[name]
                actual = actual if name in ("slot_tier","slot_is_ev") else actual[:10]
                require(exact(actual, expected), f"Full-run prefix differs: {name}")
    records = []
    env = {k:v for k,v in os.environ.items() if not k.startswith(("VEC_JAX_","JAX_","XLA_"))}
    env.update(m["environment"])
    for cost in m["costs_ms"][1:]:
        case = target / f"cost_{str(cost).replace('.', 'p')}"
        case.mkdir()
        command = [sys.executable,"-u",str(Path(m["code_checkout"])/"eval/eval_sumo_stage1_mc.py"),
                   "--trace",m["trace"]["path"],"--actor",m["actor"]["path"],
                   "--max-steps","10","--seed","0","--fleet","uk2030","--fleet-seed","1",
                   "--rsu-cap-per-veh","2.5","--lambda-arrival","1.5","--rsu-service-mult","1",
                   "--rsu-lb","per_task_dla","--rsu-state-delay-ms","0","--rsu-backhaul-ms",str(cost),
                   "--k8s-scale","off","--substep-queue","sequential","--substep-queue-iters","3",
                   "--rsu-cap-mode","reject","--veh-queue","conserved",
                   "--out-json",str(case/"summary.json"),"--per-step-out",str(case/"per_step.npz"),
                   "--per-task-out",str(case/"per_task.npz")]
        write_json(case/"command.json", {"argv":command,"environment":m["environment"]})
        print(f"Running direct 10-step forwarding probe: {cost} ms",flush=True)
        with (case/"stdout.log").open("w") as out, (case/"stderr.log").open("w") as err:
            finished = subprocess.run(command,env=env,stdout=out,stderr=err,timeout=180)
        require(finished.returncode == 0, f"Direct probe failed; see {case}")
        derived = transform(zero_task, cost)
        require(not derived["point_latency_ambiguous"].any(), "Direct probe needs identifiable point latencies for byte comparison")
        with np.load(case/"per_task.npz") as actual:
            require(set(actual.files) == set(zero_task), "Task schema differs")
            for name in actual.files:
                expected = derived[name] if name in CHANGED_TASK_FIELDS else zero_task[name]
                require(exact(actual[name],expected), f"Direct versus transformed task mismatch: {cost}ms {name}")
        with np.load(case/"per_step.npz") as actual:
            require(set(actual.files) == set(zero_step), "Step schema differs")
            for name in actual.files:
                if name not in CHANGED_STEP_FIELDS:
                    require(exact(actual[name],zero_step[name]), f"Feedback into step state: {cost}ms {name}")
            require(np.array_equal(actual["done"],derived["task_met"].sum(axis=(1,2))), "Step success count differs")
            require(np.array_equal(actual["veh_done"],derived["task_met"].sum(axis=1)), "Vehicle success count differs")
        summary = json.loads((case/"summary.json").read_text())
        for name in ("n_offered","n_admitted","total_energy_j","avg_energy_j_per_task",
                     "p_local","p_v2i","p_v2v","v2i_gate_rejected","v2i_cap_rejected",
                     "v2i_unavailable","v2v_unavailable","local_mqd_rejected","v2v_mqd_rejected","work_ms"):
            require(summary[name] == zero_summary[name], f"Feedback into summary: {name}")
        n_met = int(derived["task_met"].sum())
        require(summary["completion"] == n_met/summary["n_offered"], "Direct deadline attainment differs")
        records.append({"cost_ms":cost,"status":"passed","latency_and_outcomes":"shape_dtype_bytes_exact",
                        "unchanged_state_fields":"all_existing_fields_except_done_veh_done_lat_sum_exact",
                        "deadline_met":n_met,"evaluator_wall_s":summary["wall_s"],
                        "files_sha256":{p.name:sha(p) for p in case.iterdir() if p.is_file()}})
        print(f"Exact agreement passed: {cost} ms",flush=True)
    result = {"status":"passed","created_at_utc":datetime.now(timezone.utc).isoformat(),
              "manifest_sha256":sha(ROOT/"manifest.json"),"script_sha256":sha(__file__),
              "zero_reconstruction":"exact","full_run_prefix":"exact","direct_probes":records}
    write_json(ROOT/"qualification.json",result)


def analyze(m):
    verify_identity(m)
    qualification = json.loads((ROOT/"qualification.json").read_text())
    require(qualification["status"] == "passed" and qualification["manifest_sha256"] == sha(ROOT/"manifest.json"),
            "Qualification missing or not bound to this manifest")
    fresh = Path(m["fresh_input"])
    ingress = Path(m["ingress_input"])
    s = json.loads((fresh/"summary.json").read_text())
    si = json.loads((ingress/"summary.json").read_text())
    verify_receipt(fresh)
    verify_receipt(ingress)
    with np.load(ingress/"per_task.npz") as a:
        require(not a["task_forwarded"].any(), "Ingress baseline forwards tasks")
        ref_met = int(a["task_met"].sum(dtype=np.int64))
        require(si["completion"] == ref_met/si["n_offered"], "Ingress success reconstruction failed")
    with np.load(fresh/"per_task.npz") as a:
        task = {name:a[name] for name in ("task_active","task_type","task_outcome","task_forwarded",
                                        "task_lat_ms","task_met","task_v2i_admitted","task_forwarding_latency_ms")}
    baseline = transform(task, 0)
    require(all(exact(baseline[k],task[k]) for k in CHANGED_TASK_FIELDS), "Full zero reconstruction failed")
    offered = int(task["task_active"].sum(dtype=np.int64))
    zero_met = int(task["task_met"].sum(dtype=np.int64))
    require(offered == s["n_offered"] == si["n_offered"], "Offered denominators differ")
    require(s["completion"] == zero_met/offered, "Full fresh completion reconstruction failed")
    old_outcome = task["task_outcome"]
    counts = np.bincount(old_outcome.reshape(-1),minlength=9)
    require(int(counts[1]+counts[2]) == s["n_admitted"], "Admitted reconstruction failed")
    for code,name in ((3,"v2i_gate_rejected"),(4,"v2i_cap_rejected"),(5,"local_mqd_rejected"),
                      (6,"v2v_mqd_rejected"),(7,"v2i_unavailable"),(8,"v2v_unavailable")):
        require(int(counts[code]) == s[name], f"Zero rejection reconstruction failed: {name}")
    previous = zero_met
    rows=[]
    for cost in m["costs_ms"]:
        derived=baseline if cost==0 else transform(task,cost)
        new_met=derived["task_met"]
        met=int(new_met.sum(dtype=np.int64))
        require(met<=previous,"Forwarding-cost response is not non-increasing")
        require(not np.any(new_met & ~task["task_met"]),"Positive cost creates new successes")
        require(np.array_equal(derived["task_outcome"][old_outcome>=3],old_outcome[old_outcome>=3]),"Rejections changed")
        require(np.array_equal(derived["task_lat_ms"][~task["task_forwarded"]],task["task_lat_ms"][~task["task_forwarded"]]),"Non-forwarded latency changed")
        row={"forwarding_ms":cost,"n_offered":offered,"n_admitted":int(s["n_admitted"]),
             "deadline_met":met,"deadline_attainment":met/offered,"ingress_deadline_met":ref_met,
             "ingress_deadline_attainment":ref_met/offered,"difference_from_ingress_pp":100*(met-ref_met)/offered,
             "difference_from_zero_pp":100*(met-zero_met)/offered,"additional_deadline_misses":zero_met-met,
             "forwarded_admitted_tasks":int(task["task_forwarded"].sum(dtype=np.int64)),
             "ambiguous_point_latencies":int(derived["point_latency_ambiguous"].sum(dtype=np.int64)),
             "v2i_gate_rejected":int(s["v2i_gate_rejected"]),"v2i_cap_rejected":int(s["v2i_cap_rejected"]),
             "avg_energy_j_per_task":s["avg_energy_j_per_task"]}
        for index in range(3):
            mask=task["task_active"] & (task["task_type"]==index)
            n=int(mask.sum(dtype=np.int64));ndone=int((mask & new_met).sum(dtype=np.int64))
            row[f"t{index+1}_offered"]=n;row[f"t{index+1}_deadline_met"]=ndone
            row[f"t{index+1}_deadline_attainment"]=ndone/n
            if cost==0:require(s[f"t{index+1}_completion"]==ndone/n,"Task-type zero reconstruction failed")
        rows.append(row);previous=met
        print(f"{cost} ms: {100*row['deadline_attainment']:.6f}% attainment; advantage {row['difference_from_ingress_pp']:+.6f} pp",flush=True)
    with (ROOT/"forwarding_sensitivity.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    output={"status":"passed","created_at_utc":datetime.now(timezone.utc).isoformat(),
            "manifest_sha256":sha(ROOT/"manifest.json"),"qualification_sha256":sha(ROOT/"qualification.json"),
            "analysis_script_sha256":sha(__file__),"zero_counts_and_outcomes":"exact",
            "rows":rows,"scope":"single fleet draw; exact qualified fixed-overhead counterfactual under frozen evaluator semantics",
            "new_full_simulations":0,"new_short_direct_simulations":4}
    write_json(ROOT/"analysis_validation.json",output)


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("phase",choices=["qualify","analyze"])
    args=parser.parse_args();manifest=json.loads((ROOT/"manifest.json").read_text())
    (qualify if args.phase=="qualify" else analyze)(manifest)

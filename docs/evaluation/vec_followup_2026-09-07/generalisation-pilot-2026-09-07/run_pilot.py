#!/usr/bin/env python3
"""Matched canonical working-day pilot; frozen evaluator and absolute capacity."""
import argparse
import csv
import datetime as dt
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback

import numpy as np

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for part in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def write_json(path, payload):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def array_hash(a):
    h = hashlib.sha256()
    h.update(str(a.dtype).encode())
    h.update(json.dumps(a.shape).encode())
    h.update(memoryview(np.ascontiguousarray(a)).cast("B"))
    return h.hexdigest()


def require(value, message):
    if not bool(value):
        raise RuntimeError(message)


def verify_identity(m):
    repo = Path(m["code_checkout"])
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    require(head == m["code_commit"], "Code commit changed")
    dirty = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True)
    require(not dirty, "Tracked code files changed")
    for name, expected in m["source_sha256"].items():
        require(sha(repo / name) == expected, f"Source hash changed: {name}")
    for key in ("trace", "actor"):
        require(sha(m[key]["path"]) == m[key]["sha256"], f"Input changed: {key}")
    require(sha(__file__) == m["runner_sha256"], "Pilot runner changed")
    require(platform.python_version() == m["runtime"]["python"], "Python version changed")
    require(platform.machine() == m["runtime"]["machine"], "Machine architecture changed")
    for package, version in m["runtime"]["packages"].items():
        require(importlib.metadata.version(package) == version, f"Package changed: {package}")
    require(sha(ROOT / "input_validation.json") == m["input_validation_sha256"], "Input audit changed")
    require(json.loads((ROOT / "input_validation.json").read_text())["status"] == "passed", "Input audit failed")
    import jax
    require(jax.default_backend() == "cpu" and not jax.config.jax_enable_x64,
            "Expected CPU and float32 JAX configuration")


def command_for(m, cell, directory, steps):
    command = [m["python"], "-u", str(Path(m["code_checkout"]) / "eval/eval_sumo_stage1_mc.py"),
               "--trace", m["trace"]["path"], "--actor", m["actor"]["path"],
               "--max-steps", str(steps), "--seed", str(m["evaluator_seed"]), "--fleet", m["fleet"],
               "--fleet-seed", str(m["fleet_seed"]), "--rsu-cap-abs", str(m["rsu_capacity_tasks"]),
               "--lambda-arrival", "1.5", "--rsu-service-mult", "1.0",
               "--rsu-lb", cell["mode"], "--rsu-backhaul-ms", "0",
               "--k8s-scale", "off", "--substep-queue", "sequential",
               "--substep-queue-iters", "3", "--rsu-cap-mode", "reject",
               "--veh-queue", "conserved", "--out-json", str(directory / "summary.json"),
               "--per-step-out", str(directory / "per_step.npz"),
               "--per-task-out", str(directory / "per_task.npz")]
    if cell["delay_ms"] is not None:
        command += ["--rsu-state-delay-ms", str(cell["delay_ms"])]
    return command


def validate(directory, m, cell, steps, reference=None):
    """Check independent task counts, paths, workload endpoints and inputs."""
    s = json.loads((directory / "summary.json").read_text())
    N, R, cap = m["maxN"], m["rsus"], m["rsu_capacity_tasks"]
    require(s["T"] == steps and s["maxN"] == N, "Trace dimensions mismatch")
    require(s["enter_reset"] is True and s["reset_soc_on_enter"] is False, "Per-visit reset configuration changed")
    require(s["engine_version"] == "v3_enter_reset", "Canonical entry markers not used")
    require(s["obs_variant"] == "onehot17", "Actor observation variant changed")
    require(s["fleet_seed"] == m["fleet_seed"] and s["fleet"] == m["fleet"], "Fleet mismatch")
    require(s["rsu_lb"] == cell["mode"], "Mode mismatch")
    require(s["rsu_max_concurrent"] == cap and s["rsu_backhaul_ms"] == 0,
            "Cap or forwarding changed")
    require(s["rsu_cap_mode"] == "reject" and s["substep_queue"] == "sequential"
            and s["veh_queue_mode"] == "conserved" and s["k8s_scale"] == "off"
            and s["rsu_service_mult"] == 1 and s["lambda_arrival"] == 1.5,
            "Queue/service controls changed")
    identities = {}
    with np.load(directory / "per_step.npz") as step:
        for name in step.files:
            a = step[name]
            require(np.isfinite(a).all(), f"Nonfinite per-step values: {name}")
            if name in ("veh_action", "veh_k", "slot_tier", "slot_is_ev"):
                identities[name] = array_hash(a)
        require(int(step["arrivals"].sum(dtype=np.int64)) == s["n_offered"], "Arrival count mismatch")
        done = int(step["done"].sum(dtype=np.int64))
        require(np.isclose(done / s["n_offered"], s["completion"], rtol=0, atol=1e-12), "Completion mismatch")
        load, busy = step["rsu_load"], step["rsu_busy_ms"]
        require(load.shape == busy.shape == (steps, R), "RSU dimensions mismatch")
        with np.load(m["trace"]["path"]) as trace:
            require(np.array_equal(step["times"], trace["times"][:steps]), "Trace timestamps mismatch")
            require(np.array_equal(step["active"], trace["mask"][:steps].sum(axis=1)), "Active vehicle count mismatch")
        require((load >= 0).all() and (load <= cap).all() and (busy >= 0).all(), "Invalid live queue")
        if cell["delay_ms"] is not None:
            delay = cell["delay_ms"]
            require(s["rsu_state_delay"]["requested_ms"] == delay, "Delay summary mismatch")
            expected_age = np.full(steps, delay, dtype=np.int32)
            expected_age[0] = 0
            require(np.array_equal(step["state_actual_age_ms"], expected_age), "Incorrect actual report age")
            require(np.array_equal(step["state_observed_at_ms"], np.arange(steps)*1000), "Incorrect observation clock")
            require(np.array_equal(step["state_captured_at_ms"], np.arange(steps)*1000-expected_age), "Incorrect capture clock")
            pre, start = step["rsu_pre_drain_busy_ms"], step["rsu_start_busy_ms"]
            require(np.array_equal(busy, np.maximum(pre-1000, 0)), "Drain mismatch")
            require(np.array_equal(start[1:], busy[:-1]), "Queue carry mismatch")
            observed = step["rsu_report_busy_ms"]
            expected = np.maximum(pre[:-1] - (1000-delay), 0) if delay else start[1:]
            require(np.array_equal(observed[1:], expected), "Historical report mismatch")
            added = float((pre.astype(np.float64) - start).sum())
            served = float(np.minimum(pre, 1000).astype(np.float64).sum())
            remaining = float(busy[-1].astype(np.float64).sum())
            require(np.isclose(added, served+remaining, rtol=0, atol=.1), "Queue work is not conserved")
            require(np.isclose(added, s["work_ms"]["v2i_admitted"],
                               rtol=m["validation"]["accumulated_work_rtol"], atol=1),
                    "Admitted-work accumulator mismatch")
        if reference:
            with np.load(reference / "per_step.npz") as old:
                require(np.allclose(step["veh_actor_logits"], old["veh_actor_logits"], rtol=0, atol=1e-5),
                        "Actor logits differ beyond the predeclared tolerance")

    with np.load(directory / "per_task.npz") as task:
        for name in task.files:
            a = task[name]
            require(a.shape == (steps, 5, N), f"Unexpected task shape: {name}")
            require(np.isfinite(a).all(), f"Nonfinite per-task values: {name}")
            if name in ("task_active", "task_type", "task_ingress_rsu"):
                identities[name] = array_hash(a)
        active, outcome = task["task_active"], task["task_outcome"]
        counts = np.bincount(outcome.reshape(-1), minlength=9)
        require(int(active.sum(dtype=np.int64)) == s["n_offered"], "Per-task offered mismatch")
        require(np.array_equal(outcome == 0, ~active), "Inactive outcomes mismatch")
        require(len(counts) == 9 and int(counts[1]+counts[2]) == s["n_admitted"], "Admitted count mismatch")
        require(int(counts[1]) == done, "Deadline-met count mismatch")
        require(np.array_equal(task["task_met"], outcome == 1), "Task deadline outcomes mismatch")
        for code, key in ((3,"v2i_gate_rejected"),(4,"v2i_cap_rejected"),
                          (5,"local_mqd_rejected"),(6,"v2v_mqd_rejected"),
                          (7,"v2i_unavailable"),(8,"v2v_unavailable")):
            require(int(counts[code]) == s[key], f"Rejection count mismatch: {key}")
        admitted = task["task_v2i_admitted"]
        execution, selected, ingress = task["task_execution_rsu"], task["task_selected_execution_rsu"], task["task_ingress_rsu"]
        require(np.array_equal(admitted, (ingress >= 0) & ((outcome == 1) | (outcome == 2))), "V2I admission taxonomy mismatch")
        require((execution[~admitted] == -1).all(), "Rejected task executes")
        require(np.array_equal(execution[admitted], selected[admitted]), "Execution differs from selected target")
        require(np.array_equal(task["task_forwarded"], admitted & (execution != ingress)), "Forwarding mismatch")
        require((task["task_forwarding_latency_ms"] == 0).all(), "Forwarding delay changed")
        require(((execution[admitted] >= 0) & (execution[admitted] < R)).all(), "Invalid execution RSU")
        if cell["mode"] == "ingress_dla":
            require(np.array_equal(selected[ingress >= 0], ingress[ingress >= 0]), "Ingress control forwards")

    require(s["n_offered"] == s["n_admitted"] + sum(s[k] for k in ("v2i_gate_rejected", "v2i_cap_rejected", "local_mqd_rejected", "v2v_mqd_rejected", "v2i_unavailable", "v2v_unavailable")), "Task conservation failed")
    require(np.isclose(s["total_energy_j"] / s["n_offered"], s["avg_energy_j_per_task"], rtol=0, atol=1e-12), "Energy denominator mismatch")
    ledger = s["work_ms"]
    for family, rejected_key in (("v2i", "v2i_rejected_or_unavailable"), ("veh", "veh_rejected")):
        require(ledger[rejected_key] >= 0 and ledger[family+"_admitted"] >= 0, "Negative service-work ledger")
        require(np.isclose(ledger[family+"_offered"], ledger[family+"_admitted"] + ledger[rejected_key], rtol=0, atol=1e-6), "Service-work ledger identity failed")
    if reference:
        old = json.loads((reference / "validation.json").read_text())
        require(identities == old["input_identity"], "Task/fleet/action identity changed across conditions")
    checksums = {p.name: sha(p) for p in directory.iterdir() if p.is_file()
                 and p.name not in ("validation.json",)}
    result = {"status":"passed", "validated_at":now(), "steps":steps,
              "condition":cell, "input_identity":identities, "sha256":checksums,
              "reference":str(reference) if reference else None}
    write_json(directory / "validation.json", result)
    return result


def analyze(completed):
    rows = []
    for name, directory in completed.items():
        s = json.loads((directory / "summary.json").read_text())
        rows.append({"condition":name, "fleet_seed":1, "n_offered":int(s["n_offered"]),
                     "n_admitted":int(s["n_admitted"]), "deadline_attainment":s["completion"],
                     "v2i_gate_rejected":s["v2i_gate_rejected"], "v2i_cap_rejected":s["v2i_cap_rejected"],
                     "v2i_unavailable":s["v2i_unavailable"], "avg_latency_met_ms":s["avg_latency_met_ms"],
                     "avg_energy_j_per_task":s["avg_energy_j_per_task"], "wall_s":s["wall_s"]})
    fresh = next(r["deadline_attainment"] for r in rows if r["condition"] == "fresh")
    ingress = next(r["deadline_attainment"] for r in rows if r["condition"] == "ingress")
    for row in rows:
        row["difference_from_fresh_pp"] = 100*(row["deadline_attainment"]-fresh)
        row["difference_from_ingress_pp"] = 100*(row["deadline_attainment"]-ingress)
    with (ROOT/"comparison.csv").open("w", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines = ["# Working-day generalisation pilot results", "", "Single matched fleet draw (seed 1), Manchester working day, 15 October 2024 08:00–11:00; 10,800 simulated seconds per condition.", "", "| Condition | Offered-task deadline attainment | Change from fresh (pp) | Change from ingress (pp) |", "|---|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['condition']} | {100*row['deadline_attainment']:.5f}% | {row['difference_from_fresh_pp']:+.5f} | {row['difference_from_ingress_pp']:+.5f} |")
    lines += ["", "This is a single-draw pilot, so these are descriptive comparisons without replicate-level confidence intervals.", "Fresh workload, live admission, 6,220 tasks per RSU, service 1x, forwarding 0 ms, no scaling. Nine canonical RSUs and per-visit vehicle-queue resets are shared by both arms. The geography remains Manchester; this is scenario transfer, not an independent geographical dataset or a traffic-only intervention relative to the old incident trace.", "", "All cells passed their recorded validation. Full metrics are in comparison.csv and each cell's summary.json."]
    (ROOT/"RESULTS.md").write_text("\n".join(lines)+"\n")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true")
    args=parser.parse_args()
    lock=(ROOT/"runner.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    m=json.loads(MANIFEST.read_text())
    if (ROOT/"status.json").exists():
        require(args.resume, "Pilot already has status; use --resume to retain completed cells")
        old_status=json.loads((ROOT/"status.json").read_text())
        require(old_status["manifest_sha256"] == sha(MANIFEST), "Manifest changed since launch")
    env={k:v for k,v in os.environ.items() if not k.startswith(("VEC_JAX_","JAX_","XLA_"))}
    env.update(m["environment"])
    os.environ.update(m["environment"])
    verify_identity(m)
    completed={}
    status={"status":"starting", "pid":os.getpid(), "started_at":now(),
            "manifest_sha256":sha(MANIFEST), "completed":[], "conditions":len(m["cells"])}
    write_json(ROOT/"status.json",status)
    child=None

    def run(cell, parent, steps, reference=None):
        nonlocal child
        parent.mkdir(parents=True,exist_ok=True)
        if args.resume:
            for attempt in sorted(parent.glob("attempt_*")):
                v=attempt/"validation.json"
                if v.exists():
                    receipt=json.loads(v.read_text())
                    if receipt["status"]=="passed":
                        require(all(sha(attempt/name)==value for name,value in receipt["sha256"].items()), "Completed output checksum changed")
                        return attempt
        directory=parent/f"attempt_{len(list(parent.glob('attempt_*')))+1:03d}"
        directory.mkdir()
        verify_identity(m)
        require(shutil.disk_usage(ROOT).free >= m["minimum_free_bytes"], "Insufficient free disk space")
        command=command_for(m,cell,directory,steps)
        write_json(directory/"command.json", {"argv":command,"environment":m["environment"],"manifest_sha256":sha(MANIFEST)})
        start=time.monotonic()
        print(f"{now()} Starting {cell['name']} ({steps} simulated seconds): {directory}",flush=True)
        with (directory/"stdout.log").open("w") as out, (directory/"stderr.log").open("w") as err:
            child=subprocess.Popen(command,env=env,cwd=m["code_checkout"],stdout=out,stderr=err,start_new_session=True)
            status.update(status="running",current=cell["name"],steps=steps,cell_pid=child.pid,
                          current_output=str(directory),cell_started_at=now())
            while child.poll() is None:
                status.update(updated_at=now(),cell_elapsed_s=round(time.monotonic()-start,1))
                write_json(ROOT/"status.json",status)
                require(time.monotonic()-start < m["max_cell_wall_seconds"],"Cell exceeded time limit")
                time.sleep(15)
        code=child.returncode
        child=None
        require(code==0, f"Evaluator exited {code}; see {directory/'stderr.log'}")
        status.update(status="validating",updated_at=now())
        write_json(ROOT/"status.json",status)
        verify_identity(m)
        validate(directory,m,cell,steps,reference)
        print(f"{now()} Validated {cell['name']} ({steps} simulated seconds)",flush=True)
        return directory

    def stop(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}")
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    try:
        smoke_reference = None
        smokes = {}
        for cell in m["cells"]:
            smoke = run(cell, ROOT/"preflight"/cell["name"], m["preflight_steps"], smoke_reference)
            smokes[cell["name"]] = smoke
            if cell["name"] == "fresh":
                smoke_reference = smoke
        timings = {name: json.loads((directory/"summary.json").read_text())["wall_s"] for name, directory in smokes.items()}
        write_json(ROOT/"benchmark.json", {"preflight_steps": m["preflight_steps"], "wall_s_by_condition": timings,
                   "linear_upper_estimate_total_full_simulation_s": sum(timings.values()) * m["steps"] / m["preflight_steps"],
                   "note": "Short-run wall time includes JIT compilation; linear extrapolation is conservative, not a measured full-run runtime."})
        for index,cell in enumerate(m["cells"],1):
            reference=completed.get("fresh")
            directory=run(cell,ROOT/"cells"/f"{index:02d}_{cell['name']}",m["steps"],reference)
            with np.load(smokes[cell["name"]]/"per_task.npz") as smoke_task, np.load(directory/"per_task.npz") as full_task:
                for field in ("task_type", "task_active", "task_outcome", "task_met", "task_ingress_rsu", "task_execution_rsu", "task_lat_ms"):
                    require(np.array_equal(full_task[field][:m["preflight_steps"]], smoke_task[field]), f"Full-run prefix differs from smoke: {field}")
            completed[cell["name"]]=directory
            status["completed"]=list(completed)
            write_json(ROOT/"status.json",status)
        analyze(completed)
        status.update(status="completed",finished_at=now(),current=None,cell_pid=None,
                      report=str(ROOT/"RESULTS.md"))
    except BaseException as error:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait()
        status.update(status="stopped" if isinstance(error,KeyboardInterrupt) else "failed",
                      error=str(error),finished_at=now(),cell_pid=None)
        traceback.print_exc()
        write_json(ROOT/"status.json",status)
        return 1
    write_json(ROOT/"status.json",status)
    print(f"{now()} Completed pilot. Report: {ROOT/'RESULTS.md'}",flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Sealed, fail-closed execution of the twelve predeclared incident E3a cells.

Every invocation needs an independently supplied manifest SHA-256. Qualifying
runs are separate engineering records and never become study observations.
This module does not submit Slurm jobs, retry attempts, or change tolerances.
"""

import argparse
import contextlib
import datetime as dt
import fcntl
import importlib.metadata
import json
import math
import os
import platform
import re
import resource
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, TextIO

import numpy as np
from validation import ARMS, FILES, need, sha, validate_cell

Json = dict[str, Any]

ROOT = Path(__file__).resolve().parent
TRACE_SHA256 = "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
ACTOR_SHA256 = "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
STEPS, VEHICLES, RSUS = 3600, 2488, 10
FLEET_SEEDS = (1, 2, 3, 4)
T_CRITICAL_3 = 3.182446305284263
GIB = 1 << 30
MAX_SECONDS = 6 * 3600
EXPECTED_VERSIONS = {"jax": "0.4.30", "jaxlib": "0.4.30", "numpy": "1.26.4"}
ENVIRONMENT = {
    "JAX_ENABLE_X64": "false",
    "JAX_PLATFORMS": "cpu",
    "PYTHONHASHSEED": "0",
    "VEC_JAX_K_MAX": "5",
    "VEC_JAX_K_MIN": "0",
    "VEC_JAX_LAMBDA_ARRIVAL": "1.5",
    "VEC_JAX_MODEL_C": "1",
    "VEC_JAX_PRIORITY_ALPHA": "0",
    "VEC_JAX_RSU_SERVICE_MULT": "1.0",
    "VEC_JAX_STRESS_ARRIVAL": "1",
    "VEC_JAX_STRESS_LANES": "0",
    "VEC_JAX_STRESS_SPEED": "0",
    "OMP_NUM_THREADS": "4",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
}


def now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def read_json(path: Path) -> Json:
    return json.loads(Path(path).read_text())


def write_once(path: Path, payload: Json) -> None:
    with Path(path).open("x") as stream:
        json.dump(payload, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def contained(root: Path, relative: str | Path) -> Path:
    relative = Path(relative)
    need(not relative.is_absolute() and ".." not in relative.parts, "Nonrelative sealed path")
    result = root / relative
    need(result.resolve().is_relative_to(root.resolve()), "Sealed path escapes bundle")
    return result


def verify_bundle(root: Path, expected_sha256: str) -> Json:
    need(
        bool(re.fullmatch(r"[a-f0-9]{64}", expected_sha256 or "")),
        "External manifest SHA-256 required",
    )
    need(sha(root / "manifest.json") == expected_sha256, "Manifest differs from external seal")
    manifest = read_json(root / "manifest.json")
    need(manifest["schema"] == "e3a_csf3_bundle_v1", "Bundle schema mismatch")
    need(
        bool(re.fullmatch(r"[a-f0-9]{40}", manifest["source_commit"])),
        "Exact source commit required",
    )
    files = manifest["files"]
    required = {
        "campaign.py",
        "validation.py",
        "qualification_reference.py",
        "protocol.json",
        "experimental/evaluator_v3.py",
        "campaign.sbatch",
        "qualify.sbatch",
        "reduce.sbatch",
        "inputs/trace_inc_fullrsu.npz",
        "inputs/actor.npz",
    }
    need(required <= set(files), "Required source/input absent from seal")
    for name, digest in files.items():
        path = contained(root, name)
        need(path.is_file() and sha(path) == digest, f"Sealed file changed: {name}")
    # A new local import must not silently bypass the source manifest.
    for directory in (root, root / "experimental"):
        paths = directory.glob("*.py") if directory == root else directory.rglob("*.py")
        for path in paths:
            need(str(path.relative_to(root)) in files, f"Unsealed Python source: {path}")
    need(files["inputs/trace_inc_fullrsu.npz"] == TRACE_SHA256, "Wrong incident trace")
    need(files["inputs/actor.npz"] == ACTOR_SHA256, "Wrong frozen actor")
    need(manifest["protocol_sha256"] == files["protocol.json"], "Protocol binding mismatch")
    protocol = read_json(root / "protocol.json")
    expected = {
        "schema": "e3a_csf3_protocol_v1",
        "arms": list(ARMS),
        "fleet_seeds": list(FLEET_SEEDS),
        "evaluator_seed": 0,
        "steps": STEPS,
        "trace_sha256": TRACE_SHA256,
        "actor_sha256": ACTOR_SHA256,
    }
    for name, value in expected.items():
        need(protocol.get(name) == value, f"Protocol mismatch: {name}")
    return manifest


def external_gates(root: Path, manifest: Json, seal: str) -> str:
    path = root / "EXTERNAL_GATES.json"
    gates = read_json(path)
    need(
        gates["status"] == "passed" and gates["manifest_sha256"] == seal,
        "Source/construct gate is missing or bound to another bundle",
    )
    need(gates["source_commit"] == manifest["source_commit"], "Source approval commit mismatch")
    need(
        gates["gates"] == {"unit_construct": "passed", "independent_review": "passed"},
        "Required independent gates did not pass",
    )
    need(
        gates["review_verdict"] == f"VERDICT: APPROVE exact SHA {manifest['source_commit']}",
        "Exact-source approval missing",
    )
    return sha(path)


def runtime_info() -> Json:
    need(bool(os.environ.get("SLURM_JOB_ID")), "Use a Slurm compute allocation")
    need(platform.system() == "Linux", "Qualified Linux CPU backend required")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    available = sorted(os.sched_getaffinity(0))
    need(allocated in (4, 8) and len(available) >= 4, "Expected four or eight allocated CPUs")
    os.sched_setaffinity(0, available[:4])
    versions = {name: importlib.metadata.version(name) for name in (*EXPECTED_VERSIONS, "scipy")}
    need(platform.python_version() == "3.11.15", "Python version differs from preregistration")
    need(
        all(versions[key] == value for key, value in EXPECTED_VERSIONS.items()),
        "Pinned package mismatch",
    )
    cpu_model = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "unknown",
    )
    need(cpu_model != "unknown", "CPU identity unavailable")
    return {
        "at": now(),
        "python": platform.python_version(),
        "packages": versions,
        "cpu_model": cpu_model,
        "machine": platform.machine(),
        "platform": platform.platform(),
        "host": socket.gethostname(),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
        "allocated_cpu_count": allocated,
        "effective_cpu_count": 4,
        "slurm_job_id": os.environ["SLURM_JOB_ID"],
        "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
        "environment": ENVIRONMENT,
    }


def runtime_identity(runtime: Json) -> Json:
    return {key: runtime[key] for key in ("python", "packages", "machine", "environment")}


def cell_config(index: int, seal: str, steps: int = STEPS, phase: str = "campaign") -> Json:
    need(isinstance(index, int) and 0 <= index < 12, "Cell index must be 0..11")
    fleet_seed, arm = FLEET_SEEDS[index // len(ARMS)], ARMS[index % len(ARMS)]
    return {
        "cell_index": index,
        "phase": phase,
        "arm": arm,
        "fleet_seed": fleet_seed,
        "evaluator_seed": 0,
        "steps": steps,
        "n_vehicles": VEHICLES,
        "n_rsus": RSUS,
        "enter_reset": False,
        "seal_sha256": seal,
    }


def cell_directory(root: Path, config: Json) -> Path:
    if config["phase"] == "campaign":
        return (
            root / "campaign" / f"cell_{config['cell_index']:02d}_{config['arm']}" / "attempt_001"
        )
    return root / "qualification" / config["phase"] / config["arm"] / "attempt_001"


def command_for(root: Path, destination: Path, config: Json) -> list[str]:
    command = [
        sys.executable,
        "-u",
        str(root / "experimental/evaluator_v3.py"),
        "--trace",
        str(root / "inputs/trace_inc_fullrsu.npz"),
        "--actor",
        str(root / "inputs/actor.npz"),
        "--max-steps",
        str(config["steps"]),
        "--seed",
        "0",
        "--fleet",
        "uk2030",
        "--fleet-seed",
        str(config["fleet_seed"]),
        "--rsu-cap-abs",
        "6220",
        "--lambda-arrival",
        "1.5",
        "--rsu-service-mult",
        "1.0",
        "--rsu-lb",
        config["arm"],
        "--rsu-backhaul-ms",
        "0",
        "--k8s-scale",
        "off",
        "--substep-queue",
        "sequential",
        "--substep-queue-iters",
        "3",
        "--rsu-cap-mode",
        "reject",
        "--veh-queue",
        "conserved",
        "--out-json",
        str(destination / "summary.json"),
        "--per-step-out",
        str(destination / "per_step.npz"),
        "--per-task-out",
        str(destination / "per_task.npz"),
    ]
    if config["arm"] == "per_task_dla":
        # Exact archived full comparator used explicit fresh-state diagnostics.
        command.extend(["--rsu-state-delay-ms", "0"])
    return command


def stop_campaign(root: Path, error: BaseException) -> None:
    with contextlib.suppress(FileExistsError):
        write_once(
            root / "STOPPED.json",
            {"at": now(), "error": str(error), "status": "stopped", "retries": 0},
        )


def require_not_stopped(root: Path) -> None:
    need(not (root / "STOPPED.json").exists(), "A prior failure stopped this sealed campaign")


def run_child(
    command: list[str], root: Path, stdout: TextIO, stderr: TextIO, seconds: float
) -> None:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("VEC_JAX_", "JAX_", "XLA_"))
        and key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE")
    }
    environment.update(ENVIRONMENT)
    deadline = time.monotonic() + seconds
    # The executable, evaluator, flags and data paths are built from the verified bundle.
    with subprocess.Popen(command, env=environment, stdout=stdout, stderr=stderr) as process:  # noqa: S603
        try:
            while True:
                require_not_stopped(root)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Predeclared attempt time budget exhausted")
                try:
                    status = process.wait(timeout=min(5.0, remaining))
                    if status:
                        raise subprocess.CalledProcessError(status, command)
                    return
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            process.kill()
            process.wait()
            raise


def attempt(
    root: Path, manifest: Json, config: Json, runtime: Json, timeout_seconds: float
) -> Json:
    seal = config["seal_sha256"]
    verify_bundle(root, seal)
    require_not_stopped(root)
    destination = cell_directory(root, config)
    destination.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    config = config | {
        "inputs": {
            "trace": str(root / "inputs/trace_inc_fullrsu.npz"),
            "actor": str(root / "inputs/actor.npz"),
            "trace_sha256": TRACE_SHA256,
            "actor_sha256": ACTOR_SHA256,
        }
    }
    command = command_for(root, destination, config)
    config["command"] = command
    try:
        need(shutil.disk_usage(root).free >= 20 * GIB, "Less than 20 GiB free")
        need(timeout_seconds > 0, "Qualification deadline exhausted before attempt")
        write_once(destination / "COMMAND.json", config)
        write_once(destination / "RUNTIME.json", runtime)
        write_once(destination / "STARTED.json", {"at": now(), "timeout_seconds": timeout_seconds})
        with (
            (destination / "stdout.log").open("x") as stdout,
            (destination / "stderr.log").open("x") as stderr,
        ):
            run_child(command, root, stdout, stderr, timeout_seconds)
        require_not_stopped(root)
        receipt = validate_cell(destination, config)
        if config["phase"] == "campaign" and config["fleet_seed"] == 1:
            reference = reference_gate(root, manifest, "benchmark", config["arm"], destination)
            if reference is not None:
                receipt["reference_comparison_sha256"] = reference
        receipt.update(
            elapsed_seconds=time.monotonic() - started,
            raw_bytes=sum((destination / name).stat().st_size for name in FILES),
            peak_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            peak_validator_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            source_commit=manifest["source_commit"],
            runtime_sha256=sha(destination / "RUNTIME.json"),
            cpu_model=runtime["cpu_model"],
            allocated_cpu_count=runtime["allocated_cpu_count"],
            effective_cpu_count=runtime["effective_cpu_count"],
        )
        write_once(destination / "VALIDATED.json", receipt)
        print(
            f"VALIDATED {config['phase']} {config['arm']} fleet={config['fleet_seed']}", flush=True
        )
        return receipt
    except BaseException as error:
        write_once(
            destination / "FAILED.json",
            {
                "at": now(),
                "error": str(error),
                "retained": True,
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        stop_campaign(root, error)
        raise


def reference_gate(
    root: Path, manifest: Json, phase: str, arm: str, destination: Path
) -> str | None:
    reference_names = {
        ("smoke", "ingress_dla"): "incident-short-ingress",
        ("benchmark", "ingress_dla"): "incident-full-ingress",
        ("benchmark", "per_task_dla"): "incident-full-per-task",
    }
    name = reference_names.get((phase, arm))
    if name is None:
        return None
    reference = root / "references" / name
    need(reference.is_dir(), f"Missing archived qualification reference {name}")
    for path in reference.rglob("*"):
        if path.is_file():
            need(
                str(path.relative_to(root)) in manifest["files"], f"Unsealed reference file {path}"
            )
    from qualification_reference import compare_reference

    comparison = compare_reference(reference, destination)
    write_once(destination / "REFERENCE_COMPARISON.json", comparison)
    need(
        comparison.get("status") == "passed" or comparison.get("passed") is True,
        "Archived reference comparison did not pass",
    )
    return sha(destination / "REFERENCE_COMPARISON.json")


def check_shared(records: list[Json]) -> None:
    need(
        len(records) == 3 and {record["configuration"]["arm"] for record in records} == set(ARMS),
        "Matched block requires all three distinct arms",
    )
    shared = records[0]["shared_input_hashes"]
    need(
        shared and all(record["shared_input_hashes"] == shared for record in records),
        "Exogenous inputs differ within a matched fleet draw",
    )


def qualification_budget(benchmarks: list[Json], free_bytes: int) -> Json:
    need(len(benchmarks) == 3, "All three full benchmarks required")
    seconds = [record["elapsed_seconds"] for record in benchmarks]
    need(all(0 < value < MAX_SECONDS for value in seconds), "Benchmark exceeds per-cell budget")
    projected_raw = sum(record["raw_bytes"] for record in benchmarks) * len(FLEET_SEEDS)
    # Four simultaneous array tasks; each fleet reproduces the three arms.
    projected_elapsed = sum(seconds) * len(FLEET_SEEDS) / 4
    peak_gib = max(
        (record["peak_child_rss_kib"] + record["peak_validator_rss_kib"]) * 1024 / GIB
        for record in benchmarks
    )
    required_free = 20 * GIB + 2 * projected_raw
    need(projected_elapsed <= 24 * 3600, "Projected campaign exceeds 24 active hours")
    need(peak_gib < 28, "Observed conservative process RSS bound exceeds 28 GiB")
    need(free_bytes >= required_free, "Insufficient space for retained campaign and safety copy")
    return {
        "projected_raw_bytes": projected_raw,
        "required_free_bytes": required_free,
        "observed_free_bytes": free_bytes,
        "projected_elapsed_seconds_at_four_concurrent": projected_elapsed,
        "conservative_peak_rss_gib": peak_gib,
        "per_cell_limit_seconds": MAX_SECONDS,
        "maximum_concurrent_cells": 4,
        "memory_gib_per_cell": 32,
        "estimates": (
            "qualification measurements; queue delays and CPU-dependent runtime variation excluded"
        ),
    }


def qualify(root: Path, manifest: Json, seal: str, runtime: Json) -> Json:
    external_sha = external_gates(root, manifest, seal)
    require_not_stopped(root)
    qualification = root / "qualification"
    qualification.mkdir(exist_ok=False)
    write_once(
        qualification / "STARTED.json", {"at": now(), "seal_sha256": seal, "runtime": runtime}
    )
    deadline = time.monotonic() + MAX_SECONDS - 60
    validation_hashes, comparison_hashes, benchmarks = {}, {}, []
    try:
        for phase, steps in (("smoke", 10), ("benchmark", STEPS)):
            records = []
            for index, arm in enumerate(ARMS):
                config = cell_config(index, seal, steps=steps, phase=phase)
                receipt = attempt(root, manifest, config, runtime, deadline - time.monotonic())
                destination = cell_directory(root, config)
                key = str(destination.relative_to(root))
                validation_hashes[key] = sha(destination / "VALIDATED.json")
                comparison = reference_gate(root, manifest, phase, arm, destination)
                if comparison is not None:
                    comparison_hashes[key] = comparison
                records.append(receipt)
            check_shared(records)
            if phase == "benchmark":
                benchmarks = records
        need(time.monotonic() < deadline, "Total qualification time budget exhausted")
        budget = qualification_budget(benchmarks, shutil.disk_usage(root).free)
        receipt = {
            "status": "passed",
            "at": now(),
            "seal_sha256": seal,
            "source_commit": manifest["source_commit"],
            "external_gates_sha256": external_sha,
            "runtime_identity": runtime_identity(runtime),
            "cpu_model": runtime["cpu_model"],
            "validated_attempt_sha256": validation_hashes,
            "reference_comparison_sha256": comparison_hashes,
            "budget": budget,
            "study_cells": 0,
            "scope": "three 10-step smokes and three 3600-step benchmarks",
        }
        write_once(root / "QUALIFIED.json", receipt)
        return receipt
    except BaseException as error:
        write_once(
            qualification / "FAILED.json", {"at": now(), "error": str(error), "retained": True}
        )
        stop_campaign(root, error)
        raise


def qualified_gate(root: Path, manifest: Json, seal: str, runtime: Json) -> Json:
    require_not_stopped(root)
    qualified = read_json(root / "QUALIFIED.json")
    need(
        qualified["status"] == "passed" and qualified["seal_sha256"] == seal,
        "This exact bundle has not qualified",
    )
    need(qualified["source_commit"] == manifest["source_commit"], "Qualification source mismatch")
    need(
        qualified["external_gates_sha256"] == external_gates(root, manifest, seal),
        "Approval receipt changed",
    )
    need(
        qualified["runtime_identity"] == runtime_identity(runtime),
        "Runtime differs from qualified backend",
    )
    expected = {
        str(
            cell_directory(root, cell_config(index, seal, steps=steps, phase=phase)).relative_to(
                root
            )
        )
        for phase, steps in (("smoke", 10), ("benchmark", STEPS))
        for index in range(3)
    }
    need(
        set(qualified["validated_attempt_sha256"]) == expected,
        "Incomplete qualification attempt set",
    )
    for relative, digest in qualified["validated_attempt_sha256"].items():
        destination = contained(root, relative)
        need(not (destination / "FAILED.json").exists(), "Failed qualification attempt")
        need(sha(destination / "VALIDATED.json") == digest, "Qualification validation changed")
        receipt = read_json(destination / "VALIDATED.json")
        need(
            receipt["status"] == "passed" and receipt["seal_sha256"] == seal,
            "Invalid qualification receipt",
        )
        need(set(receipt["output_sha256"]) == set(FILES), "Incomplete qualification outputs")
        for name, expected_hash in receipt["output_sha256"].items():
            need(sha(destination / name) == expected_hash, "Qualification output changed")
    expected_comparisons = {
        "qualification/smoke/ingress_dla/attempt_001",
        "qualification/benchmark/ingress_dla/attempt_001",
        "qualification/benchmark/per_task_dla/attempt_001",
    }
    need(
        set(qualified["reference_comparison_sha256"]) == expected_comparisons,
        "Missing archived reference gate",
    )
    for relative, digest in qualified["reference_comparison_sha256"].items():
        need(
            sha(contained(root, relative) / "REFERENCE_COMPARISON.json") == digest,
            "Reference gate changed",
        )
    need(
        shutil.disk_usage(root).free >= 20 * GIB + qualified["budget"]["projected_raw_bytes"],
        "Campaign storage reserve no longer available",
    )
    return qualified


def paired_statistics(differences_pp: list[float]) -> Json:
    values = np.asarray(differences_pp, np.float64)
    need(
        values.shape == (4,) and np.all(np.isfinite(values)),
        "Exactly four finite paired fleet differences required",
    )
    mean = float(values.mean())
    standard_deviation = float(values.std(ddof=1))
    standard_error = standard_deviation / math.sqrt(4)
    margin = T_CRITICAL_3 * standard_error
    return {
        "n": 4,
        "per_fleet_difference_pp": values.tolist(),
        "mean_difference_pp": mean,
        "sample_sd_pp": standard_deviation,
        "standard_error_pp": standard_error,
        "descriptive_t_interval_95_pp": [mean - margin, mean + margin],
        "t_critical": T_CRITICAL_3,
        "statistical_unit": "matched fleet draw",
        "evaluator_seed": 0,
        "interpretation": (
            "descriptive four-fleet interval conditional on evaluator seed 0; "
            "no joint-seed independence"
        ),
    }


def reduce_records(records: list[Json]) -> Json:
    need(len(records) == 12, "Reduction requires all twelve cells")
    identities = {
        (record["configuration"]["fleet_seed"], record["configuration"]["arm"])
        for record in records
    }
    need(
        identities == {(seed, arm) for seed in FLEET_SEEDS for arm in ARMS},
        "Missing/duplicate cell identity",
    )
    for record in records:
        config = record["configuration"]
        need(
            record["status"] == "passed"
            and config["phase"] == "campaign"
            and config["steps"] == STEPS
            and config["evaluator_seed"] == 0,
            "Noncampaign or invalid record in reduction",
        )
        need(
            record["offered"] > 0
            and 0 <= record["successes"] <= record["admitted"] <= record["offered"],
            "Invalid all-offered outcome denominator",
        )
    rows, primary, secondary = [], [], []
    for seed in FLEET_SEEDS:
        block = [record for record in records if record["configuration"]["fleet_seed"] == seed]
        check_shared(block)
        need(
            len({record["cpu_model"] for record in block}) == 1,
            "CPU model differs within a matched fleet draw",
        )
        by_arm = {record["configuration"]["arm"]: record for record in block}
        rates = {arm: record["successes"] / record["offered"] for arm, record in by_arm.items()}
        primary.append(100 * (rates["p2c_dla"] - rates["per_task_dla"]))
        secondary.append(100 * (rates["p2c_dla"] - rates["ingress_dla"]))
        rows.append(
            {
                "fleet_seed": seed,
                "evaluator_seed": 0,
                "cpu_model": block[0]["cpu_model"],
                "arms": {
                    arm: {
                        key: record[key]
                        for key in (
                            "offered",
                            "admitted",
                            "successes",
                            "terminal_failures",
                            "forwarded",
                        )
                    }
                    | {"offered_deadline_success_rate": rates[arm]}
                    for arm, record in by_arm.items()
                },
            }
        )
    return {
        "status": "complete",
        "study_cells": 12,
        "matched_fleet_draws": 4,
        "rows": rows,
        "primary": dict(contrast="p2c_dla minus per_task_dla", **paired_statistics(primary)),
        "secondary": dict(contrast="p2c_dla minus ingress_dla", **paired_statistics(secondary)),
        "outcome": "deadline successes divided by all offered tasks in each arm and fleet draw",
        "exclusions": [],
        "qualification_records_included": 0,
        "limitations": [
            "single Manchester incident trace",
            "fixed evaluator seed 0",
            "four fleet draws",
            "frozen actor weights with endogenous mode choices",
            "zero inter-RSU forwarding latency",
            "mask-only vehicle queue reset because incident trace lacks enter channel",
            "compute completion and return events are not independently recorded",
        ],
    }


def reduce_campaign(root: Path, manifest: Json, seal: str, runtime: Json) -> Json:
    qualified_gate(root, manifest, seal, runtime)
    records, receipts = [], {}
    for index in range(12):
        expected = cell_config(index, seal)
        destination = cell_directory(root, expected)
        need(not (destination / "FAILED.json").exists(), "Failed study cell")
        stored = read_json(destination / "VALIDATED.json")
        config = read_json(destination / "COMMAND.json")
        need(
            all(config.get(key) == value for key, value in expected.items()),
            "Study configuration mismatch",
        )
        need(
            stored["configuration"] == config
            and stored["source_commit"] == manifest["source_commit"],
            "Study receipt/source mismatch",
        )
        current = validate_cell(destination, config)
        need(
            all(stored.get(key) == value for key, value in current.items()),
            "Study validation or raw outputs changed",
        )
        need(
            sha(destination / "RUNTIME.json") == stored["runtime_sha256"], "Runtime receipt changed"
        )
        cell_runtime = read_json(destination / "RUNTIME.json")
        need(
            cell_runtime["cpu_model"] == stored["cpu_model"]
            and runtime_identity(cell_runtime) == runtime_identity(runtime),
            "Cell backend identity mismatch",
        )
        if index in (0, 1):
            need(
                sha(destination / "REFERENCE_COMPARISON.json")
                == stored["reference_comparison_sha256"],
                "First-fleet archived comparator gate changed",
            )
        if config["arm"] == "p2c_dla":
            verify_cross_cpu_receipt(root, seal, cell_runtime)
        records.append(current | {"cpu_model": cell_runtime["cpu_model"]})
        receipts[str(destination.relative_to(root))] = sha(destination / "VALIDATED.json")
    reduction = reduce_records(records)
    reduction.update(
        seal_sha256=seal,
        source_commit=manifest["source_commit"],
        at=now(),
        qualified_sha256=sha(root / "QUALIFIED.json"),
        cell_receipt_sha256=receipts,
    )
    destination = root / "reduction"
    destination.mkdir(exist_ok=False)
    write_once(destination / "REDUCED.json", reduction)
    return reduction


def verify_cross_cpu_receipt(root: Path, seal: str, runtime: Json) -> Json:
    receipt = read_json(root / "P2C_CROSS_CPU_QUALIFIED.json")
    need(
        receipt["status"] == "passed" and receipt["seal_sha256"] == seal,
        "Cross-CPU P2C qualification missing or stale",
    )
    need(receipt["cpu_model"] == runtime["cpu_model"], "Cross-CPU P2C qualified another CPU model")
    destination = cell_directory(root, cell_config(2, seal, steps=10, phase="intel-smoke"))
    need(not (destination / "FAILED.json").exists(), "Failed cross-CPU P2C smoke")
    need(
        sha(destination / "VALIDATED.json") == receipt["validated_sha256"],
        "Cross-CPU validation changed",
    )
    need(
        sha(destination / "CROSS_CPU_COMPARISON.json") == receipt["comparison_sha256"],
        "Cross-CPU comparison changed",
    )
    validated = read_json(destination / "VALIDATED.json")
    need(
        validated["seal_sha256"] == seal and validated["status"] == "passed",
        "Invalid cross-CPU accounting receipt",
    )
    need(
        sha(destination / "RUNTIME.json") == validated["runtime_sha256"],
        "Cross-CPU runtime receipt changed",
    )
    reference = cell_directory(root, cell_config(2, seal, steps=10, phase="smoke"))
    need(
        sha(reference / "VALIDATED.json") == receipt["reference_validated_sha256"],
        "Cross-CPU reference accounting changed",
    )
    for name in FILES:
        need(
            sha(destination / name) == validated["output_sha256"][name],
            "Cross-CPU smoke output changed",
        )
    return receipt


def cross_cpu_gate(root: Path, manifest: Json, seal: str, runtime: Json, deadline: float) -> Json:
    """Exactly one first-fleet P2C smoke on the campaign CPU; later cells verify it."""
    with (root / "CROSS_CPU.lock").open("a+") as lock:
        while True:
            require_not_stopped(root)
            need(time.monotonic() < deadline, "Time budget exhausted waiting for cross-CPU gate")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(1)
        if (root / "P2C_CROSS_CPU_QUALIFIED.json").exists():
            return verify_cross_cpu_receipt(root, seal, runtime)
        try:
            config = cell_config(2, seal, steps=10, phase="intel-smoke")
            attempt(root, manifest, config, runtime, min(1800, deadline - time.monotonic()))
            destination = cell_directory(root, config)
            reference = cell_directory(root, cell_config(2, seal, steps=10, phase="smoke"))
            from qualification_reference import compare_cross_cpu

            comparison = compare_cross_cpu(reference, destination)
            write_once(destination / "CROSS_CPU_COMPARISON.json", comparison)
            need(comparison.get("passed") is True, "P2C cross-CPU comparison failed")
            receipt = {
                "status": "passed",
                "at": now(),
                "seal_sha256": seal,
                "cpu_model": runtime["cpu_model"],
                "validated_sha256": sha(destination / "VALIDATED.json"),
                "comparison_sha256": sha(destination / "CROSS_CPU_COMPARISON.json"),
                "reference_validated_sha256": sha(reference / "VALIDATED.json"),
                "study_cells": 0,
            }
            write_once(root / "P2C_CROSS_CPU_QUALIFIED.json", receipt)
            return receipt
        except BaseException as error:
            stop_campaign(root, error)
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "qualify", "execute-cell", "reduce"))
    parser.add_argument("index", type=int, nargs="?")
    parser.add_argument("--manifest-sha256", default=os.environ.get("E3A_MANIFEST_SHA256"))
    args = parser.parse_args()
    manifest = verify_bundle(ROOT, args.manifest_sha256)
    if args.mode == "check":
        print("SEALED BUNDLE VERIFIED")
        return
    runtime = runtime_info()
    if args.mode == "execute-cell":
        need(args.index is not None, "execute-cell requires an index")
        qualified_gate(ROOT, manifest, args.manifest_sha256, runtime)
        deadline = time.monotonic() + MAX_SECONDS - 60
        if cell_config(args.index, args.manifest_sha256)["arm"] == "p2c_dla":
            cross_cpu_gate(ROOT, manifest, args.manifest_sha256, runtime, deadline)
        attempt(
            ROOT,
            manifest,
            cell_config(args.index, args.manifest_sha256),
            runtime,
            deadline - time.monotonic(),
        )
    else:
        with (ROOT / "CONTROLLER.lock").open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.mode == "qualify":
                qualify(ROOT, manifest, args.manifest_sha256, runtime)
            else:
                reduce_campaign(ROOT, manifest, args.manifest_sha256, runtime)


if __name__ == "__main__":
    main()

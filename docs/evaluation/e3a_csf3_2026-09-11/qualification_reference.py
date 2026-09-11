"""Compare new comparator outputs with authenticated September incident archives.

Read-only; never imports the evaluator. New instrumentation is checked by the
campaign validator. All archived fields must remain present and preserve dtype.
Tolerances are fixed before qualification, independent of observed differences.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_reference(reference_dir, actual_dir, manifest=None):
    reference_dir, actual_dir = Path(reference_dir), Path(actual_dir)
    receipt = json.loads((reference_dir / "validation.json").read_text())
    if receipt["status"] != "passed":
        raise ValueError("Archived reference did not pass original validation")
    rows = []
    for archive in ("per_step.npz", "per_task.npz", "summary.json", "command.json"):
        if sha(reference_dir / archive) != receipt["sha256"][archive]:
            raise ValueError(f"Archived reference hash changed: {archive}")
    for archive in ("per_step.npz", "per_task.npz"):
        with np.load(reference_dir / archive, allow_pickle=False) as ref, np.load(
            actual_dir / archive, allow_pickle=False
        ) as got:
            if not set(ref.files).issubset(got.files):
                raise ValueError(f"Missing inherited output fields: {archive}")
            for field in ref.files:
                expected, actual = ref[field], got[field]
                if expected.shape != actual.shape or expected.dtype != actual.dtype:
                    raise ValueError(f"Shape/dtype changed: {archive}/{field}")
                if not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected)):
                    raise ValueError(f"Nonfinite reference comparison: {archive}/{field}")
                exact_required = expected.dtype.kind not in "fc" or field in {
                    "times", "task_forwarding_latency_ms"
                }
                if field == "veh_actor_logits":
                    atol, rtol = 1e-5, 0.0
                elif field == "lat_sum":
                    atol, rtol = 1.0, 1e-4
                elif field in {"veh_queue_ms", "rsu_busy_ms"}:
                    atol, rtol = 0.1, 0.0
                else:
                    atol, rtol = 0.001, 1e-6
                exact = bool(np.array_equal(actual, expected))
                passed = exact if exact_required else bool(np.allclose(
                    actual, expected, atol=atol, rtol=rtol, equal_nan=False
                ))
                delta = np.abs(actual.astype(np.float64) - expected.astype(np.float64))
                rows.append(dict(archive=archive, field=field, passed=passed,
                                 exact=exact, exact_required=exact_required,
                                 atol=0.0 if exact_required else atol,
                                 rtol=0.0 if exact_required else rtol,
                                 max_abs=float(delta.max(initial=0)),
                                 different_elements=int(np.count_nonzero(actual != expected))))
    ref_summary = json.loads((reference_dir / "summary.json").read_text())
    got_summary = json.loads((actual_dir / "summary.json").read_text())
    # Path basenames and evaluator instrumentation metadata may differ. These
    # controls and count/ratio outcomes must reproduce exactly on the same input.
    keys = ["model", "T", "maxN", "rsu_max_concurrent", "fleet", "fleet_seed",
            "obs_variant", "lambda_arrival", "rsu_service_mult", "rsu_lb",
            "rsu_backhaul_ms", "k8s_scale", "rsu_cap_mode", "substep_queue",
            "veh_queue_mode", "enter_reset", "reset_soc_on_enter", "fleet_tier_hist",
            "n_offered", "n_admitted", "total_tasks", "completion", "completion_admitted",
            "v2i_gate_rejected", "v2i_cap_rejected", "local_mqd_rejected",
            "v2v_mqd_rejected", "v2i_unavailable", "v2v_unavailable",
            "t1_completion", "t2_completion", "t3_completion", "t1_share", "t2_share", "t3_share"]
    for key in keys:
        rows.append(dict(archive="summary.json", field=key,
                         passed=got_summary.get(key) == ref_summary[key], exact_required=True))
    return dict(passed=all(row["passed"] for row in rows), fields=rows,
                failed_fields=[row for row in rows if not row["passed"]],
                reference_validation_sha256=sha(reference_dir / "validation.json"),
                scope="All inherited arrays; exact discrete outcomes and controls; new fields independently validated")


def compare_cross_cpu(reference_dir, actual_dir):
    """Authenticated ten-step P2C prefix agreement, not full-backend equivalence."""
    reference_dir, actual_dir = Path(reference_dir), Path(actual_dir)
    receipts = []
    for directory in (reference_dir, actual_dir):
        receipt = json.loads((directory / "VALIDATED.json").read_text())
        if receipt["status"] != "passed" or (directory / "FAILED.json").exists():
            raise ValueError("CPU comparison requires successful independent accounting")
        if set(receipt["output_sha256"]) != {"summary.json", "per_step.npz", "per_task.npz"}:
            raise ValueError("Incomplete CPU comparison output seal")
        for name, expected in receipt["output_sha256"].items():
            if sha(directory / name) != expected:
                raise ValueError(f"CPU comparison output changed: {name}")
        if sha(directory / "RUNTIME.json") != receipt["runtime_sha256"]:
            raise ValueError("CPU comparison runtime receipt changed")
        config = receipt["configuration"]
        if config["arm"] != "p2c_dla" or config["steps"] != 10 or config["fleet_seed"] != 1 or config["evaluator_seed"] != 0:
            raise ValueError("CPU comparison must use the declared P2C prefix")
        if config != json.loads((directory / "COMMAND.json").read_text()):
            raise ValueError("CPU comparison command changed")
        receipts.append(receipt)
    first, second = receipts
    for key in ("seal_sha256", "source_commit", "shared_input_hashes"):
        if first[key] != second[key]:
            raise ValueError(f"CPU comparison identity differs: {key}")
    for key in ("n_vehicles", "n_rsus", "enter_reset", "inputs"):
        if first["configuration"][key] != second["configuration"][key]:
            raise ValueError(f"CPU comparison configuration differs: {key}")
    # Output paths differ; every computational command argument must agree.
    def command_identity(argv):
        result = []
        index = 0
        while index < len(argv):
            if argv[index] in {"--out-json", "--per-step-out", "--per-task-out"}:
                index += 2
            else:
                result.append(argv[index]); index += 1
        return result
    if command_identity(first["configuration"]["command"]) != command_identity(second["configuration"]["command"]):
        raise ValueError("CPU comparison computational command differs")
    runtimes = [json.loads((directory / "RUNTIME.json").read_text())
                for directory in (reference_dir, actual_dir)]
    for key in ("python", "packages", "machine", "environment"):
        if runtimes[0][key] != runtimes[1][key]:
            raise ValueError(f"CPU comparison software/thread environment differs: {key}")
    if any(len(runtime["cpu_affinity"]) != 4 for runtime in runtimes):
        raise ValueError("CPU comparison requires four effective CPUs")
    rows = []
    exact_float_fields = {"times", "slot_soc_initial", "slot_tx_power_w", "observation_task_size",
                          "task_sizes_mb", "task_rsu_service_ms", "task_forwarding_latency_ms"}
    for name in ("per_step.npz", "per_task.npz"):
        with np.load(reference_dir / name, allow_pickle=False) as ref, np.load(actual_dir / name, allow_pickle=False) as got:
            if set(ref.files) != set(got.files):
                raise ValueError(f"CPU comparison field set differs: {name}")
            for field in ref.files:
                expected, actual = ref[field], got[field]
                if expected.shape != actual.shape or expected.dtype != actual.dtype:
                    raise ValueError(f"CPU comparison shape/dtype differs: {name}/{field}")
                if not np.all(np.isfinite(expected)) or not np.all(np.isfinite(actual)):
                    raise ValueError(f"CPU comparison nonfinite data: {name}/{field}")
                exact_required = expected.dtype.kind not in "fc" or field in exact_float_fields
                if field == "veh_actor_logits":
                    atol, rtol = 1e-5, 0.0
                elif field == "lat_sum":
                    atol, rtol = 1.0, 1e-4
                elif field in {"veh_queue_ms", "rsu_busy_ms"}:
                    atol, rtol = 0.1, 0.0
                else:
                    atol, rtol = 0.001, 1e-6
                exact = bool(np.array_equal(actual, expected))
                passed = exact if exact_required else bool(np.allclose(actual, expected, atol=atol, rtol=rtol))
                rows.append(dict(archive=name, field=field, passed=passed, exact=exact,
                                 exact_required=exact_required, atol=0 if exact_required else atol,
                                 rtol=0 if exact_required else rtol,
                                 max_abs=float(np.abs(actual.astype(np.float64) - expected.astype(np.float64)).max(initial=0))))
    for key in ("offered", "admitted", "successes", "terminal_failures", "forwarded", "outcome_counts", "type_counts"):
        rows.append(dict(archive="VALIDATED.json", field=key, passed=first[key] == second[key], exact_required=True))
    summaries = [json.loads((directory / "summary.json").read_text()) for directory in (reference_dir, actual_dir)]
    exact_summary = ["completion", "completion_admitted", "n_offered", "n_admitted", "total_tasks",
                     "t1_completion", "t2_completion", "t3_completion", "t1_share", "t2_share", "t3_share",
                     "v2i_gate_rejected", "v2i_cap_rejected", "local_mqd_rejected", "v2v_mqd_rejected",
                     "v2i_unavailable", "v2v_unavailable"]
    for key in exact_summary:
        rows.append(dict(archive="summary.json", field=key,
                         passed=summaries[0][key] == summaries[1][key], exact_required=True))
    return dict(passed=all(row["passed"] for row in rows), fields=rows,
                failed_fields=[row for row in rows if not row["passed"]],
                reference_validation_sha256=sha(reference_dir / "VALIDATED.json"),
                actual_validation_sha256=sha(actual_dir / "VALIDATED.json"),
                reference_cpu=runtimes[0]["cpu_model"], actual_cpu=runtimes[1]["cpu_model"],
                scope="Ten-step P2C prefix portability only; full P2C cross-CPU equivalence is not established")

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

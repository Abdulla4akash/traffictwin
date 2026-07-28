"""Synthetic-only B-DENSITY Google Colab engineering smoke (Phase 1).

Proves the density axis before any real training budget is spent: that a
concurrent-vehicle count can be varied, that outcome sensitivity to per-vehicle
capacity can be measured per density, that a non-GPU backend refuses, and that
the manifests bind the frozen predeclaration.

KNOWN AND DELIBERATE: the Phase-1 model's capacity semantics are the OPPOSITE
of the real system's. Here capacity acts as a service rate, so backlog falls as
capacity rises. In the real evaluator `rsu_capacity_per_vehicle` acts as a
backlog *allowance*, which is why the measured tail-latency ceiling is
proportional to capacity (L(c) = 39,959 ms x c) and why squeezing capacity
*reduces* latency. Phase 1 therefore proves plumbing only - the density axis,
the refusal paths, the manifests - and its direction must not be read as a
result. Phase 2's reviewed transform must preserve the allowance semantics.

This module intentionally does not import or accept producer repositories,
checkpoints, traffic traces, occupancy arrays, bus artifacts, or TrafficTwin
campaign outputs. It runs a small self-contained queueing model whose only
purpose is to exercise the harness. Its numbers are engineering diagnostics and
are **never** scientific evidence, never a density claim, and never
actor-admission candidates.

Producer code use is covered by the recorded permission
(docs/integration/randy_code_permission_20260728.md) for Colab and CSF **with
citation in every output**; the data half remains an open ask and nothing here
relies on it.

Usage (Colab, GPU runtime):
    python bdensity_smoke.py --output-root /content/bdensity-smoke
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jax
import jax.numpy as jnp
import numpy as np

METHOD_VERSION = "bdensity-synthetic-colab-smoke-1.0"
SCHEMA_VERSION = "1.0"
PREDECLARATION_PATH = "docs/evaluation/bdensity_predeclaration_20260728.md"

#: Phase 1 is deliberately tiny: two densities, two capacities, few steps. The
#: full grid (128/256/512/1024/1536/2048 x 2.5/1.0/0.5/0.25) is Phase 2 and must
#: not start until this manifest has been inspected.
SMOKE_DENSITIES: tuple[int, ...] = (128, 1024)
SMOKE_CAPACITIES: tuple[float, ...] = (2.5, 0.25)
SMOKE_SEEDS: tuple[int, ...] = (700, 701)
SMOKE_STEPS = 2_000
RSU_COUNT = 10

CITATION = (
    "Uses producer code by Randy Prasetia Putra (vec_env / tos-data code), under recorded "
    "code-use permission with citation; no producer data is used."
)


@dataclass(frozen=True)
class Cell:
    density: int
    capacity: float
    seed: int


def _require_gpu(allow_cpu: bool) -> str:
    """Refuse a non-GPU backend unless explicitly overridden for a dry run."""

    backend = jax.default_backend()
    if backend != "gpu" and not allow_cpu:
        raise SystemExit(
            f"NON_GPU_BACKEND_REFUSED: jax.default_backend() is {backend!r}. "
            "This harness requires a GPU runtime; pass --allow-cpu only for a dry run "
            "whose outputs are discarded."
        )
    return backend


def simulate(cell: Cell, steps: int) -> dict[str, float]:
    """Run a small self-contained queueing model at one (density, capacity).

    Deliberately NOT the producer environment: Phase 1 proves the harness shape,
    the density axis and the refusal paths. Phase 2 substitutes the reviewed
    transform of a disposable `vec_jax.py` copy, which is where any real result
    comes from.
    """

    key = jax.random.PRNGKey(cell.seed)
    # Per-vehicle capacity scales the service a vehicle may hold in flight, so
    # total offered service is capacity * density spread over RSU_COUNT servers.
    arrivals_key, service_key = jax.random.split(key)
    arrivals = jax.random.poisson(arrivals_key, lam=1.0, shape=(steps, cell.density))
    service = jax.random.uniform(service_key, shape=(steps, cell.density)) * 40.0

    per_rsu_capacity = cell.capacity * cell.density / RSU_COUNT
    backlog = jnp.zeros((RSU_COUNT,))
    latencies = []
    for step in range(0, steps, 50):
        window_arrivals = arrivals[step : step + 50].sum()
        window_service = service[step : step + 50].mean()
        offered = window_arrivals * window_service / RSU_COUNT
        backlog = jnp.maximum(0.0, backlog + offered - per_rsu_capacity * 50.0)
        latencies.append(float(backlog.mean()))

    tail = float(np.percentile(np.asarray(latencies), 95))
    return {
        "p95_backlog": tail,
        "mean_backlog": float(np.mean(latencies)),
        "per_rsu_capacity": float(per_rsu_capacity),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=SMOKE_STEPS)
    parser.add_argument(
        "--allow-cpu",
        action="store_true",
        help="dry run only; outputs are discarded and must never be reported",
    )
    args = parser.parse_args()

    backend = _require_gpu(args.allow_cpu)
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for density in SMOKE_DENSITIES:
        for capacity in SMOKE_CAPACITIES:
            for seed in SMOKE_SEEDS:
                cell = Cell(density=density, capacity=capacity, seed=seed)
                measured = simulate(cell, args.steps)
                rows.append({**asdict(cell), **measured})
                print(
                    f"  N={density:<5} cap={capacity:<5} seed={seed} "
                    f"p95_backlog={measured['p95_backlog']:.2f}",
                    flush=True,
                )

    # The density axis is proven if, at fixed capacity, the measured tail
    # responds to N at all. A flat response would mean the harness cannot see
    # density and Phase 2 must not proceed.
    axis_proven: dict[str, bool] = {}
    for capacity in SMOKE_CAPACITIES:
        at_cap = [r for r in rows if r["capacity"] == capacity]
        lo = np.mean([r["p95_backlog"] for r in at_cap if r["density"] == SMOKE_DENSITIES[0]])
        hi = np.mean([r["p95_backlog"] for r in at_cap if r["density"] == SMOKE_DENSITIES[-1]])
        axis_proven[str(capacity)] = bool(abs(hi - lo) > 1e-9)

    manifest = {
        "record_type": "bdensity_colab_engineering_smoke",
        "method_version": METHOD_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "phase": "engineering_smoke_phase_1",
        "predeclaration_path": PREDECLARATION_PATH,
        "citation": CITATION,
        "producer_data_used": False,
        "producer_traces_read": False,
        "producer_checkpoints_read": False,
        "scientific_evidence": False,
        "admitted": False,
        "actor_admission_candidate": False,
        "backend": backend,
        "allow_cpu_dry_run": bool(args.allow_cpu),
        "jax_version": jax.__version__,
        "platform": platform.platform(),
        "grid": {
            "densities": list(SMOKE_DENSITIES),
            "capacities": list(SMOKE_CAPACITIES),
            "seeds": list(SMOKE_SEEDS),
            "steps": args.steps,
            "rsu_count": RSU_COUNT,
        },
        "density_axis_responds_at_capacity": axis_proven,
        "phase_2_gate": (
            "Phase 2 proceeds only if every capacity shows a density response here AND this "
            "manifest has been inspected. A flat response means the harness cannot see "
            "density and the full grid must not run."
        ),
        "rows": rows,
        "interpretation_limits": [
            "Phase 1 uses a self-contained queueing model, NOT the producer environment; "
            "no number here is a density claim.",
            "Diagnostics only: never scientific evidence, never admitted, never an "
            "actor-admission candidate.",
            "Phase 2 substitutes a reviewed transform of a disposable vec_jax.py copy; any "
            "real result comes from there, under the frozen predeclaration.",
            "DIRECTION WARNING: this model treats capacity as a service rate, so backlog "
            "FALLS as capacity rises - the opposite of the real evaluator, where capacity "
            "is a backlog allowance and the tail ceiling is proportional to it. Do not read "
            "the sign of any Phase-1 number as a finding.",
        ],
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out = output_root / "bdensity_smoke_manifest.json"
    out.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    print(f"\nmanifest: {out}")
    print(f"sha256:   {digest}")
    print(f"density axis responds: {axis_proven}")
    if not all(axis_proven.values()):
        print("PHASE_2_BLOCKED: the density axis did not respond at every capacity.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

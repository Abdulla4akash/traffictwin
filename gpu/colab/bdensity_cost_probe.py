"""B-DENSITY Phase 2 cost probe — what does each density in the frozen grid cost?

Runs on a Colab GPU VM against an uploaded **code-only** copy of the producer
source. Answers the one question that gates the full grid: the frozen densities
run to 2,048 concurrent vehicles against a producer default of 20, and
``compute_per_vehicle_links`` is all-pairs, so per-step cost is expected to grow
super-linearly in ``N``. An 18-job grid must not be launched before the cost per
density is measured.

**No source transform.** Phase 1 established that the density and capacity axes
are already documented producer knobs, so this sets them directly:

    VEC_JAX_N_VEHICLES         = N
    VEC_JAX_RSU_MAX_CONCURRENT = round(capacity * N)

which is the producer's own documented relation ("match the eval engine's
per-RSU concurrency scaling, 2.5 x fleet"), i.e. the backlog **allowance**
semantics the frozen design requires. The producer clone is never modified and
never fetched; only a disposable copy is used.

Producer **code** use is covered by the recorded permission for Colab and CSF
**with citation in every output**; the data half remains an open ask and nothing
here relies on it. No producer trace, occupancy array, checkpoint-as-data, bus
artifact or campaign output is read or uploaded.

Diagnostics only: never scientific evidence, never admitted, never an
actor-admission candidate. Timings are engineering costs, not results.

Usage (on the VM):
    python bdensity_cost_probe.py --source-root /content/vec_src \
        --output-root /content/bdensity-cost
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

METHOD_VERSION = "bdensity-phase2-cost-probe-1.0"
PREDECLARATION_PATH = "docs/evaluation/bdensity_predeclaration_20260728.md"

#: The frozen Phase 2 density grid, probed cheapest first so a failure at the
#: top still leaves every affordable density measured.
GRID_DENSITIES: tuple[int, ...] = (128, 256, 512, 1024, 1536, 2048)
#: Training capacity. The full grid evaluates 2.5/1.0/0.5/0.25; cost is a
#: property of density and env shape, so the probe holds capacity at the top of
#: the grid where the concurrency bound is loosest.
PROBE_CAPACITY = 2.5
#: Matches the B-BUS campaign's rollout shape, which is known to run on this GPU.
NUM_ENVS = 64
ROLLOUT_LEN = 50
#: Two optimiser updates: enough to separate compile cost from per-update cost.
PROBE_UPDATES = 2
PROBE_TIMESTEPS = NUM_ENVS * ROLLOUT_LEN * PROBE_UPDATES
#: A single density must not be allowed to consume the whole session.
PER_DENSITY_TIMEOUT_S = 1_800

#: Producer files whose bytes are verified before anything runs. Same set the
#: B-CAP harness pins, minus nothing: an unexpected layout is a refusal.
BASE_SOURCE_SHA256 = {
    "jaxmarl/env/__init__.py": "1ade2d2774b1249d182484cc95195a8c08bf1528de132c13adc1dc09ba198bea",
    "jaxmarl/env/vec_jax.py": "4eed6b61f157b9a1ba203d0095acdecb0741f2da8d7fc4f411b6ee16a0bdd4f9",
    "jaxmarl/env/vec_jaxmarl.py": (
        "aa7a0d8f373605b2d3f3c700760c7e2c578ffebab4eea0530e9f42de95dd0734"
    ),
    "jaxmarl/scripts/train_mappo_vec.py": (
        "b36079f495e663353398453357b2c42c54431769dcb6d208b259a592df53de12"
    ),
}

CITATION = (
    "Uses producer code by Randy Prasetia Putra (vec_env), under recorded code-use "
    "permission with citation; no producer data is used."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_source(source_root: Path) -> dict[str, str]:
    """Refuse unless every pinned producer file matches the audited bytes."""

    actual = {rel: sha256_file(source_root / rel) for rel in BASE_SOURCE_SHA256}
    if actual != BASE_SOURCE_SHA256:
        raise SystemExit(f"PRODUCER_SOURCE_MISMATCH: {actual}")
    return actual


def require_gpu(allow_cpu: bool) -> str:
    import jax

    backend = jax.default_backend()
    if backend != "gpu" and not allow_cpu:
        raise SystemExit(
            f"NON_GPU_BACKEND_REFUSED: jax.default_backend() is {backend!r}; "
            "pass --allow-cpu only for a dry run whose outputs are discarded."
        )
    return backend


def gpu_name() -> str:
    """Return the VM's GPU name, resolving the executable rather than trusting PATH."""

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return "nvidia-smi unavailable"
    probe = subprocess.run(  # noqa: S603 - resolved fixed GPU diagnostic executable
        [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return probe.stdout.strip() or probe.stderr.strip()


def probe_density(source_root: Path, output_root: Path, density: int) -> dict[str, Any]:
    """Time a two-update training run at one density."""

    env = dict(os.environ)
    env.pop("JAX_PLATFORMS", None)
    env.update(
        {
            # The two axes, set directly -- no source transform (Phase 1 finding).
            "VEC_JAX_N_VEHICLES": str(density),
            "VEC_JAX_RSU_MAX_CONCURRENT": str(round(PROBE_CAPACITY * density)),
            # Held identical to the B-CAP/B-BUS campaigns so cost is comparable.
            "VEC_JAX_PRIORITY_ALPHA": "0",
            "VEC_JAX_MODEL_C": "1",
            "VEC_JAX_GREEDY_EVAL": "0",
            "VEC_JAX_SAVE_ACTOR_PARAMS": "0",
            "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
            "PYTHONPATH": str(source_root / "jaxmarl"),
        }
    )
    log_path = output_root / f"train_N{density}.log"
    command = [
        sys.executable,
        "scripts/train_mappo_vec.py",
        "--total-timesteps",
        str(PROBE_TIMESTEPS),
        "--num-envs",
        str(NUM_ENVS),
        "--rollout-len",
        str(ROLLOUT_LEN),
        "--lr",
        "3e-3",
        "--seed",
        "700",
        "--out-csv",
        str(output_root / f"curve_N{density}.csv"),
        "--tag",
        f"bdensity-cost-N{density}",
    ]
    start = time.monotonic()
    timed_out = False
    with log_path.open("w", encoding="utf-8") as log:
        log.write("COMMAND " + " ".join(command) + "\n")
        log.write(
            f"VEC_JAX_N_VEHICLES={density} "
            f"VEC_JAX_RSU_MAX_CONCURRENT={round(PROBE_CAPACITY * density)}\n"
        )
        log.flush()
        try:
            completed = subprocess.run(  # noqa: S603 - frozen argv, no shell
                command,
                cwd=source_root / "jaxmarl",
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=PER_DENSITY_TIMEOUT_S,
            )
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = None
    elapsed = time.monotonic() - start

    tail = ""
    if returncode not in (0,):
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = "\n".join(lines[-12:])

    return {
        "density": density,
        "rsu_max_concurrent": round(PROBE_CAPACITY * density),
        "capacity_per_slot": PROBE_CAPACITY,
        "num_envs": NUM_ENVS,
        "rollout_len": ROLLOUT_LEN,
        "updates": PROBE_UPDATES,
        "timesteps": PROBE_TIMESTEPS,
        "elapsed_seconds": elapsed,
        "seconds_per_update": elapsed / PROBE_UPDATES,
        "returncode": returncode,
        "timed_out": timed_out,
        "succeeded": returncode == 0,
        "failure_tail": tail,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--allow-cpu", action="store_true")
    parser.add_argument("--densities", type=int, nargs="*", default=None)
    args = parser.parse_args()

    source_root = args.source_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    source_digests = verify_source(source_root)
    backend = require_gpu(args.allow_cpu)
    import jax

    densities = tuple(args.densities) if args.densities else GRID_DENSITIES
    rows: list[dict[str, Any]] = []
    for density in densities:
        print(f"probing N={density} ...", flush=True)
        row = probe_density(source_root, output_root, density)
        rows.append(row)
        state = "ok" if row["succeeded"] else ("TIMEOUT" if row["timed_out"] else "FAILED")
        print(
            f"  N={density:<5} {state:<8} {row['elapsed_seconds']:8.1f}s "
            f"({row['seconds_per_update']:.1f}s/update)",
            flush=True,
        )
        # Cheapest-first ordering means a failure bounds the affordable grid
        # rather than losing the densities already measured.
        if not row["succeeded"]:
            print(
                f"  stopping: N={density} did not complete; higher densities are not attempted",
                flush=True,
            )
            break

    manifest = {
        "record_type": "bdensity_phase2_cost_probe",
        "method_version": METHOD_VERSION,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "predeclaration_path": PREDECLARATION_PATH,
        "citation": CITATION,
        "producer_data_used": False,
        "producer_code_used": True,
        "source_transform_applied": False,
        "source_transform_note": (
            "Phase 1 established that VEC_JAX_N_VEHICLES and VEC_JAX_RSU_MAX_CONCURRENT are "
            "documented producer knobs, so the frozen design's 'reviewed transform of a "
            "disposable vec_jax.py copy' is unnecessary; the environment runs unpatched."
        ),
        "producer_source_sha256": source_digests,
        "scientific_evidence": False,
        "admitted": False,
        "actor_admission_candidate": False,
        "backend": backend,
        "allow_cpu_dry_run": bool(args.allow_cpu),
        "jax_version": jax.__version__,
        "gpu": gpu_name(),
        "platform": platform.platform(),
        "grid_probed": list(densities),
        "rows": rows,
        "interpretation_limits": [
            "Wall-clock engineering costs on one GPU, not a scientific result.",
            "Two updates per density: separates compile cost from steady-state per-update "
            "cost only coarsely, and does not measure convergence.",
            "N_RSUS is 2 and not environment-overridable, on a 2,000 m corridor, so high "
            "densities are dense beyond anything the Manchester traces represent.",
        ],
    }
    payload = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    out = output_root / "bdensity_cost_probe.json"
    out.write_text(payload, encoding="utf-8")
    print(f"\nmanifest: {out}")
    print(f"sha256:   {hashlib.sha256(payload.encode('utf-8')).hexdigest()}")
    completed = [r for r in rows if r["succeeded"]]
    if completed:
        print(
            "affordable densities measured: "
            + ", ".join(
                f"N={r['density']}@{r['seconds_per_update']:.1f}s/update" for r in completed
            )
        )
    return 0 if completed else 1


if __name__ == "__main__":
    raise SystemExit(main())

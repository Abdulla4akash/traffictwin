#!/usr/bin/env python3
"""Single ev-trace timing probe — the measurement ADR-065 records as its open risk.

Runs EXACTLY ONE full-length ev execution through the accepted library runner and
records wall-clock seconds, output bytes, the request fingerprint, and the margin
against the 7,200-second request ceiling. Timing evidence only: no admission, no
registry write, no metric claim. A ceiling breach is the finding, not a failure.

Usage:
    uv run python scripts/ev_timing_probe.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from traffictwin.integration.vec_runner.models import VecFleet, VecRunRequest
from traffictwin.integration.vec_runner.service import run_vec_evaluator

INPUT_ROOT = "../external/tos-data"
VEC_REPO = "../external/vec_env"
TOS_DATA_REPO = "../external/tos-data"
OUTPUT_DIR = Path("data/vec-fresh/ev-timing-probe")
EVIDENCE_PATH = Path("docs/integration/evidence/vec_ev_timing_probe_20260728.json")
CEILING_SECONDS = 7_200


def main() -> int:
    request = VecRunRequest(
        run_id="evprobe_cap2_5_fs0",
        trace_file="traces/trace_ev_fullrsu.npz",
        trace_sha256="70d6d12f3004b08c8a17e450df04ea70e74723c7a25149d3f5e1629903d01208",
        actor_id="ukfleettrain_mappo_model_c_17",
        evaluator_seed=0,
        fleet=VecFleet.UK_2030,
        fleet_seed=0,
        rsu_capacity_per_vehicle=2.5,
        max_steps=23_400,
        timeout_seconds=CEILING_SECONDS,
    )
    if OUTPUT_DIR.exists():
        raise SystemExit(f"refusing: {OUTPUT_DIR} already exists (VEC-07 creates it)")
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    receipt = run_vec_evaluator(INPUT_ROOT, VEC_REPO, TOS_DATA_REPO, OUTPUT_DIR, request)
    wall = time.perf_counter() - started

    output_bytes = sum(
        p.stat().st_size for p in OUTPUT_DIR.rglob("*") if p.is_file()
    )
    evidence = {
        "schema_version": "1.0",
        "probe": "vec-ev-timing-probe",
        "date": "2026-07-28",
        "purpose": (
            "Measure the first full-length ev execution against the 7,200 s request "
            "ceiling (the open risk recorded in ADR-065). Timing evidence only: no "
            "admission, no registry write, no metric claim."
        ),
        "request_fingerprint": request.fingerprint(),
        "receipt_status": receipt.status.value,
        "receipt_fingerprint": receipt.fingerprint(),
        "measured": {
            "wall_clock_seconds": round(wall, 1),
            "receipt_elapsed_seconds": round(receipt.elapsed_seconds, 1),
            "output_bytes": output_bytes,
            "ceiling_seconds": CEILING_SECONDS,
            "ceiling_margin_seconds": round(CEILING_SECONDS - receipt.elapsed_seconds, 1),
        },
        "interpretation_limits": [
            "One execution at one capacity and one fleet seed; a timing measurement, never a scientific result.",
            "Outputs remain unadmitted; any scientific use of ev requires a predeclared, approved design.",
        ],
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence["measured"], indent=2))
    print("status:", receipt.status.value)
    print("evidence written to", EVIDENCE_PATH)
    return 0 if receipt.status.value == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the BETA-D-02 §2 diagnosis over the restored study subnetwork.

The demand-rebuild predeclaration requires four measurements *before* any
variant runs, published regardless of what they show: the route-length and
edge-count distributions, expected free-flow network residence, counted-edge
multiplicity, and the fringe share. This script reproduces the alpha.7 route
pool from its recorded seed and envelope, then measures the pool and the
sampled demand with the Phase-41 diagnosis library.

Nothing here selects a variant, applies a viability threshold, or reaches a
verdict: `RoutePoolDiagnosis` refuses to carry one, and the selection rule
lives in the predeclaration and is applied by a person.

Stages are resumable — an existing intact output is reused rather than
regenerated, so an interrupted run does not restart the hours-scale work.

Usage:
    uv run python scripts/run_demand_diagnosis.py [--skip-demand]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.manchester.artifact_integrity import (
    refuse_ephemeral_dependency,
    sha256_file,
)
from traffictwin.integration.manchester.demand_diagnosis import (
    EdgeAttributes,
    diagnose_route_pool,
    iter_route_pool,
    render_diagnosis_markdown,
)

BUILD_ROOT = Path("data/network-build").resolve()
STUDY_ID = "gm-study-manchester-la-20260728"
STUDY_DIR = BUILD_ROOT / STUDY_ID
STUDY_PATH = STUDY_DIR / f"{STUDY_ID}.net.xml"
CLIP_RECEIPT = STUDY_DIR / "clip_receipt.json"

WORK_ROOT = Path("data/demand-diagnosis-20260728").resolve()
TRIPS_PATH = WORK_ROOT / "pool.trips.xml"
POOL_PATH = WORK_ROOT / "pool.rou.xml"
DEMAND_PATH = WORK_ROOT / "demand.rou.xml"
MISMATCH_PATH = WORK_ROOT / "demand_mismatch.xml"
RECEIPT_PATH = WORK_ROOT / "diagnosis_receipt.json"
REPORT_PATH = WORK_ROOT / "diagnosis_report.md"

COUNTS_PATH = Path("docs/integration/evidence/manchester_edgedata_counts_option_a.xml").resolve()

# The recorded alpha.7 envelope, reproduced rather than re-chosen.
SEED = "42"
WINDOW_END_S = "43200"
RECORDED_TRIPS = 43_200
RECORDED_POOL_ROUTES = 43_200
RECORDED_DEMAND_VEHICLES = 746_440

_EDGE_ID = re.compile(rb'<edge id="([^"]+)"')


def _sumo_tools() -> Path:
    home = os.environ.get("SUMO_HOME")
    if not home:
        raise SystemExit("SUMO_HOME is not set")
    tools = Path(home) / "tools"
    if not tools.is_dir():
        raise SystemExit(f"SUMO tools directory not found at {tools}")
    return tools


def _sumo_bin(name: str) -> Path:
    home = os.environ.get("SUMO_HOME")
    if not home:
        raise SystemExit("SUMO_HOME is not set")
    executable = Path(home) / "bin" / name
    if not executable.is_file():
        raise SystemExit(f"{name} not found at {executable}")
    return executable


def _run(label: str, command: list[str]) -> float:
    print(f"[{label}] {' '.join(command[:3])} ...", flush=True)
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - frozen argv, never a shell
        command, capture_output=True, text=True, check=False
    )
    duration = time.monotonic() - started
    if completed.returncode != 0:
        raise SystemExit(
            f"{label.upper()}_FAILED (exit {completed.returncode}) after {duration:.1f} s:\n"
            f"{completed.stderr[-4000:]}"
        )
    print(f"[{label}] finished in {duration:.1f} s", flush=True)
    return duration


def _xml_is_complete(path: Path) -> bool:
    """Return whether the file closes its root element.

    The 25-July pool was silently truncated by an interrupted invocation, and
    the truncated bytes were nearly reused. A reuse decision therefore checks
    completeness rather than mere existence.
    """

    if not path.is_file() or path.stat().st_size == 0:
        return False
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 4096))
        return b"</routes>" in handle.read() or b"</meandata>" in handle.read()


def _done_marker(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".done")


def _stage_is_reusable(path: Path) -> bool:
    """Return whether a stage output may be reused on a resume.

    Completeness alone is not enough. ``randomTrips --validate`` writes an
    unvalidated trips file first and rewrites it after routing, so an
    interrupted run can leave a file that closes its root element and is still
    the wrong artifact. A stage is reusable only when the writer itself
    finished and dropped its marker.
    """

    return _done_marker(path).is_file() and _xml_is_complete(path)


def _mark_done(path: Path) -> None:
    _done_marker(path).write_text(
        f"{datetime.now(UTC).isoformat()} {path.stat().st_size}\n", encoding="utf-8"
    )


_EDGE_OPEN = re.compile(rb'<edge id="([^"]+)"([^>]*)>')
_EDGE_FROM = re.compile(rb'\sfrom="([^"]+)"')
_EDGE_TO = re.compile(rb'\sto="([^"]+)"')
_LANE_LENGTH = re.compile(rb'\slength="([^"]+)"')
_LANE_SPEED = re.compile(rb'\sspeed="([^"]+)"')


def read_edge_attributes_streaming(
    path: Path,
) -> tuple[dict[str, EdgeAttributes], dict[str, int]]:
    """Stream the network once, collecting per-edge geometry and topology.

    netconvert writes one element per line, so line iteration is correct and
    bounded; a DOM parse of a 425 MB network is not.
    """

    lengths: dict[str, float] = {}
    speeds: dict[str, float] = {}
    from_junction: dict[str, str] = {}
    junctions_with_inflow: set[str] = set()
    stats = {
        "edges_seen": 0,
        "edges_without_lane_geometry": 0,
        "edges_without_junctions": 0,
        "edges_with_nonpositive_speed": 0,
    }

    current: str | None = None
    with path.open("rb") as handle:
        for line in handle:
            stripped = line.lstrip()
            if stripped.startswith(b"<edge "):
                match = _EDGE_OPEN.search(line)
                if match is None:
                    current = None
                    continue
                edge_id = match.group(1).decode()
                attributes = match.group(2)
                if edge_id.startswith(":"):
                    current = None
                    continue
                current = edge_id
                stats["edges_seen"] += 1
                source = _EDGE_FROM.search(attributes)
                target = _EDGE_TO.search(attributes)
                if source is None or target is None:
                    stats["edges_without_junctions"] += 1
                    continue
                from_junction[edge_id] = source.group(1).decode()
                junctions_with_inflow.add(target.group(1).decode())
            elif stripped.startswith(b"<lane ") and current is not None:
                length = _LANE_LENGTH.search(line)
                speed = _LANE_SPEED.search(line)
                if length is not None:
                    lengths[current] = max(lengths.get(current, 0.0), float(length.group(1)))
                if speed is not None:
                    speeds[current] = max(speeds.get(current, 0.0), float(speed.group(1)))

    edges: dict[str, EdgeAttributes] = {}
    for edge_id, source in from_junction.items():
        length = lengths.get(edge_id)
        speed = speeds.get(edge_id)
        if length is None or speed is None or length <= 0:
            stats["edges_without_lane_geometry"] += 1
            continue
        if speed <= 0:
            # A zero free-flow speed makes residence time undefined; the edge is
            # left out and counted rather than given an invented floor.
            stats["edges_with_nonpositive_speed"] += 1
            continue
        edges[edge_id] = EdgeAttributes(
            length_m=length,
            free_flow_speed_mps=speed,
            is_boundary=source not in junctions_with_inflow,
        )
    stats["entry_fringe_edges"] = sum(1 for item in edges.values() if item.is_boundary)
    stats["edges_measured"] = len(edges)
    return edges, stats


def counted_edge_ids() -> list[str]:
    return sorted(
        {match.group(1).decode() for match in _EDGE_ID.finditer(COUNTS_PATH.read_bytes())}
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-demand",
        action="store_true",
        help="measure the pool only; do not run routeSampler",
    )
    args = parser.parse_args()

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    refuse_ephemeral_dependency(WORK_ROOT)
    if not STUDY_PATH.is_file():
        raise SystemExit(f"study subnetwork missing: {STUDY_PATH} (run clip_study_subnetwork.py)")
    clip_receipt = json.loads(CLIP_RECEIPT.read_text())
    print(f"study subnetwork: {STUDY_PATH}", flush=True)
    print(f"clip raw sha256:  {clip_receipt['study_network']['raw_sha256']}", flush=True)

    tools = _sumo_tools()
    durations: dict[str, float] = {}
    reused: dict[str, bool] = {}

    trips_argv = [
        sys.executable,
        str(tools / "randomTrips.py"),
        "-n",
        str(STUDY_PATH),
        "-o",
        str(TRIPS_PATH),
        "-b",
        "0",
        "-e",
        WINDOW_END_S,
        "-p",
        "1.0",
        "--seed",
        SEED,
        "--fringe-factor",
        "5",
        "--min-distance",
        "300",
        "--validate",
        "--vehicle-class",
        "passenger",
    ]
    if _stage_is_reusable(TRIPS_PATH):
        print("[trips] reusing the existing completed trips file", flush=True)
        reused["trips"] = True
    else:
        # Deliberately generated WITHOUT -r: the 25-July combined generate+route
        # invocation was interrupted and left a truncated pool.
        durations["trips_s"] = _run("trips", trips_argv)
        _mark_done(TRIPS_PATH)
        reused["trips"] = False

    pool_argv = [
        str(_sumo_bin("duarouter")),
        "-n",
        str(STUDY_PATH),
        "-r",
        str(TRIPS_PATH),
        "-o",
        str(POOL_PATH),
        "--seed",
        SEED,
        "--ignore-errors",
        "--no-step-log",
        "--xml-validation",
        "never",
    ]
    if _stage_is_reusable(POOL_PATH):
        print("[pool] reusing the existing completed pool", flush=True)
        reused["pool"] = True
    else:
        durations["pool_s"] = _run("pool", pool_argv)
        _mark_done(POOL_PATH)
        reused["pool"] = False

    print("reading edge attributes from the study subnetwork ...", flush=True)
    started = time.monotonic()
    edges, edge_stats = read_edge_attributes_streaming(STUDY_PATH)
    durations["edge_attributes_s"] = time.monotonic() - started
    print(f"edges measured: {edge_stats['edges_measured']} of {edge_stats['edges_seen']}")
    print(f"entry-fringe edges: {edge_stats['entry_fringe_edges']}", flush=True)

    counted = counted_edge_ids()
    print(f"counted edges: {len(counted)}", flush=True)

    print("diagnosing the route pool ...", flush=True)
    started = time.monotonic()
    pool_diagnosis = diagnose_route_pool(
        iter_route_pool(POOL_PATH), edges, counted, pool_label="alpha7_pool_reproduced_seed42"
    )
    durations["pool_diagnosis_s"] = time.monotonic() - started
    print(f"pool routes: {pool_diagnosis.route_count}", flush=True)

    demand_diagnosis = None
    if not args.skip_demand:
        sampler_argv = [
            sys.executable,
            str(tools / "routeSampler.py"),
            "-r",
            str(POOL_PATH),
            "-d",
            str(COUNTS_PATH),
            "-o",
            str(DEMAND_PATH),
            "--mismatch-output",
            str(MISMATCH_PATH),
            "--seed",
            SEED,
            "--verbose",
        ]
        if _stage_is_reusable(DEMAND_PATH):
            print("[demand] reusing the existing completed demand", flush=True)
            reused["demand"] = True
        else:
            durations["demand_s"] = _run("demand", sampler_argv)
            _mark_done(DEMAND_PATH)
            reused["demand"] = False
        print("diagnosing the sampled demand ...", flush=True)
        started = time.monotonic()
        demand_diagnosis = diagnose_route_pool(
            iter_route_pool(DEMAND_PATH),
            edges,
            counted,
            pool_label="alpha7_sampled_demand_reproduced_seed42",
        )
        durations["demand_diagnosis_s"] = time.monotonic() - started
        print(f"demand vehicles: {demand_diagnosis.route_count}", flush=True)

    report = ["# BETA-D-02 §2 diagnosis — measurements only\n"]
    report.append(
        "Predeclared in `docs/evaluation/demand_rebuild_predeclaration.md` §2 and published "
        "regardless of what it shows. No variant is selected, no threshold applied, and no "
        "viability verdict is reached here.\n"
    )
    report.append(render_diagnosis_markdown(pool_diagnosis))
    if demand_diagnosis is not None:
        report.append("\n")
        report.append(render_diagnosis_markdown(demand_diagnosis))
    REPORT_PATH.write_text("".join(report), encoding="utf-8")

    receipt = {
        "record_type": "manchester_demand_diagnosis_section_2",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "capability_id": "MAN-09",
        "predeclaration": (
            "docs/evaluation/demand_rebuild_predeclaration.md "
            "(unsigned; §2 publishes regardless of outcome)"
        ),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "purpose": "measurements_only",
        "study_network": {
            "network_id": STUDY_ID,
            "path": str(STUDY_PATH),
            "raw_sha256": clip_receipt["study_network"]["raw_sha256"],
            "canonical_sha256": clip_receipt["study_network"]["canonical_sha256"],
            "real_edges": clip_receipt["edge_id_preservation"]["study_real_edges"],
        },
        "edge_attributes": {
            **edge_stats,
            "length_rule": "maximum lane length on the edge",
            "speed_rule": "maximum lane free-flow speed on the edge",
            "entry_fringe_rule": (
                "an edge whose from-junction receives no real edge, so a route starting "
                "there entered at the clip boundary rather than from modelled upstream traffic"
            ),
        },
        "counted_edges": {"source": str(COUNTS_PATH), "count": len(counted)},
        "envelope_reproduced": {
            "seed": SEED,
            "window_s": [0, int(WINDOW_END_S)],
            "trips_argv": trips_argv[1:],
            "pool_argv": pool_argv[1:],
            "recorded_trips_20260725": RECORDED_TRIPS,
            "recorded_pool_routes_20260725": RECORDED_POOL_ROUTES,
            "recorded_demand_vehicles_20260725": RECORDED_DEMAND_VEHICLES,
            "note": (
                "trip generation and routing are separate invocations: the 25-July combined "
                "call was interrupted and left a truncated pool"
            ),
        },
        "artifacts": {
            "trips": {"path": str(TRIPS_PATH), "bytes": TRIPS_PATH.stat().st_size},
            "pool": {
                "path": str(POOL_PATH),
                "bytes": POOL_PATH.stat().st_size,
                "sha256": sha256_file(POOL_PATH),
            },
            "demand": (
                {
                    "path": str(DEMAND_PATH),
                    "bytes": DEMAND_PATH.stat().st_size,
                }
                if DEMAND_PATH.is_file()
                else None
            ),
            "storage_note": "private workspace only; never committed",
        },
        "stage_reuse": reused,
        "durations_s": {key: round(value, 2) for key, value in durations.items()},
        "pool_diagnosis": pool_diagnosis.model_dump(mode="json"),
        "demand_diagnosis": (
            demand_diagnosis.model_dump(mode="json") if demand_diagnosis is not None else None
        ),
        "explicit_non_claims": [
            "no variant is selected and no viability threshold is applied here",
            "a reproduced pool is not a calibrated or validated demand",
            "reconstructed routes are never observed journeys",
        ],
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"receipt: {RECEIPT_PATH}")
    print(f"report:  {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Build both approved B-BUS successors from the existing private traces only."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from traffictwin.integration.manchester.bbus_successors import (
    MAX_OCCUPIED_CELLS,
    METHOD_VERSION,
    PLACEMENT_CELL_M,
    PLACEMENT_RADIUS_M,
    SPARSE_SITE_COUNT,
    BBusSuccessorError,
    attach_sites,
    build_corridor_trace,
    exact_coverage,
    select_sparse64_sites,
)
from traffictwin.integration.manchester.bus_vec_bridge import OCCUPANCY_HEADER, OccupancySpan

PARENT_ROOT = "data/bbus-dawn-peak-20260728-rerun1"
PARENT_MANIFEST_SHA256 = "032696ea05f47edbb4e264bdc498bb41f1d08e7958bb143278cecea70cbfa193"
DEFAULT_OUTPUT = "data/bbus-successors-20260728"

CORRIDOR_PROTOCOL_PATH = "docs/evaluation/bbus_corridor_dawn_peak_protocol_20260728.md"
CORRIDOR_PROTOCOL_SHA256 = "cd2e93f926d19a1c8b55d3962a674353be70b8d4fff0f69d80417e666238cde7"
SPARSE_PROTOCOL_PATH = "docs/evaluation/bbus_sparse64_dawn_peak_protocol_20260728.md"
SPARSE_PROTOCOL_SHA256 = "f366f3ba886287150eefcf64268e38df4e2a488372ed738dbbc712573c221efa"
APPROVAL_PATH = "docs/integration/evidence/bbus_dual_successor_owner_approval_20260728.json"
APPROVAL_SHA256 = "e165619566249c9b7f6cb2a531e486cfda3e61e306ab6b2d6821577432dd3764"
PLACEMENT_SCRIPT_SHA256 = "33928f4113988ee39f75ff06d99f2c01061182f9d0f17092e051a159a42840a0"

SESSION_INPUTS = {
    "dawn-20260728": {
        "motion_sha256": "38371ea6d7bc0f6752fb40de31767f4d49c234b517f3046145b11f12e07e9ae8",
        "occupancy_sha256": "83e32a09c73ed2d77cfffc08340aac44c48b3666c80f0cb93d44c1bc871f56be",
    },
    "peak-20260728": {
        "motion_sha256": "4a0573192c2b6cd9a498fe414c8b3158954046ccf9194cdab53aa9ace9130eb0",
        "occupancy_sha256": "809645fc7ca6d8fe5a7b915a68fecf6ea2d4fbe0b5ca5deedde89a4beb650d5a",
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(PARENT_ROOT))
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument(
        "--placement-script",
        type=Path,
        default=Path("../external/vec_env/eval/place_rsus_cover.py"),
    )
    args = parser.parse_args(argv)
    try:
        result = prepare_successors(
            source_root=args.source,
            output_root=args.output,
            placement_script=args.placement_script,
        )
    except BBusSuccessorError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def prepare_successors(
    *, source_root: Path, output_root: Path, placement_script: Path
) -> dict[str, Any]:
    repo = _repository_root()
    _verify_protocols(repo)
    source = _resolve_existing(repo, source_root)
    output = _new_private_output(repo, output_root)
    placement = _resolve_existing(repo, placement_script)
    if _sha256_file(placement) != PLACEMENT_SCRIPT_SHA256:
        raise BBusSuccessorError("the pinned full-coverage placement script changed identity")
    parent_manifest = source / "preparation_manifest.json"
    if _sha256_file(parent_manifest) != PARENT_MANIFEST_SHA256:
        raise BBusSuccessorError("the successful parent preparation manifest changed identity")

    traces: dict[str, dict[str, Any]] = {}
    spans: dict[str, tuple[OccupancySpan, ...]] = {}
    for label, identities in SESSION_INPUTS.items():
        motion = source / label / "motion_trace.npz"
        occupancy = source / label / "occupancy.csv"
        if _sha256_file(motion) != identities["motion_sha256"]:
            raise BBusSuccessorError(f"{label} parent motion trace changed identity")
        if _sha256_file(occupancy) != identities["occupancy_sha256"]:
            raise BBusSuccessorError(f"{label} parent occupancy changed identity")
        traces[label] = _read_npz(motion)
        spans[label] = _read_spans(occupancy)

    corridor_reports: dict[str, Any] = {}
    for label in SESSION_INPUTS:
        result = build_corridor_trace(traces[label], spans[label])
        if result.occupied_cells > MAX_OCCUPIED_CELLS:
            raise BBusSuccessorError(
                f"{label} corridor has {result.occupied_cells} occupied cells; "
                f"the frozen bound is {MAX_OCCUPIED_CELLS}"
            )
        session_dir = output / "corridor" / label
        session_dir.mkdir(parents=True)
        unplaced = session_dir / "motion_unplaced.npz"
        placed = session_dir / "trace.npz"
        _write_npz(unplaced, result.arrays)
        _write_spans(session_dir / "occupancy.csv", result.spans)
        completed = subprocess.run(  # noqa: S603 - exact pinned local interpreter and script
            [
                sys.executable,
                str(placement),
                "--in",
                str(unplaced),
                "--out",
                str(placed),
                "--radius",
                str(PLACEMENT_RADIUS_M),
                "--cell",
                str(PLACEMENT_CELL_M),
                "--max-rsus",
                "64",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        (session_dir / "placement.stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (session_dir / "placement.stderr.txt").write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0 or not placed.is_file():
            raise BBusSuccessorError(
                f"{label} corridor full-coverage placement refused with exit {completed.returncode}"
            )
        placed_trace = _read_npz(placed)
        sites = np.asarray(placed_trace.get("rsu_xy"), dtype=np.float32)
        coverage = exact_coverage(result.arrays, sites)
        if coverage.covered_share != 1.0 or len(sites) > 64:
            raise BBusSuccessorError(f"{label} corridor did not pass exact full coverage")
        corridor_reports[label] = {
            "source_vehicle_seconds": result.source_vehicle_seconds,
            "retained_vehicle_seconds": result.retained_vehicle_seconds,
            "excluded_vehicle_seconds": result.excluded_vehicle_seconds,
            "retained_share": result.retained_vehicle_seconds / result.source_vehicle_seconds,
            "source_occupancy_spans": result.source_occupancy_spans,
            "retained_occupancy_spans": result.retained_occupancy_spans,
            "retained_session_tokens": result.retained_session_tokens,
            "peak_concurrent_vehicles": result.peak_concurrent_vehicles,
            "occupied_cells": result.occupied_cells,
            "rsu_count": len(sites),
            "exact_coverage": asdict(coverage),
            "unplaced_trace_sha256": _sha256_file(unplaced),
            "trace_sha256": _sha256_file(placed),
            "occupancy_sha256": _sha256_file(session_dir / "occupancy.csv"),
            "placement_stdout_sha256": _sha256_file(session_dir / "placement.stdout.txt"),
            "placement_stderr_sha256": _sha256_file(session_dir / "placement.stderr.txt"),
            "vec06_placement_contract_compatible": True,
            "vec06_receipt_created": False,
        }

    sparse = select_sparse64_sites(traces["dawn-20260728"])
    sparse_reports: dict[str, Any] = {}
    for label in SESSION_INPUTS:
        session_dir = output / "sparse64" / label
        session_dir.mkdir(parents=True)
        attached = attach_sites(traces[label], sparse.rsu_xy)
        trace_path = session_dir / "trace.npz"
        occupancy_path = session_dir / "occupancy.csv"
        _write_npz(trace_path, attached)
        _write_spans(occupancy_path, spans[label])
        coverage = exact_coverage(traces[label], sparse.rsu_xy)
        sparse_reports[label] = {
            "vehicle_seconds": coverage.total_vehicle_seconds,
            "peak_concurrent_vehicles": int(np.asarray(traces[label]["maxN"]).item()),
            "exact_coverage": asdict(coverage),
            "trace_sha256": _sha256_file(trace_path),
            "occupancy_sha256": _sha256_file(occupancy_path),
        }

    site_path = output / "sparse64" / "rsu_xy.npy"
    np.save(site_path, sparse.rsu_xy, allow_pickle=False)
    manifest = {
        "schema_version": "1.0",
        "method_version": METHOD_VERSION,
        "date": "2026-07-28",
        "research_status": "owner_approved_candidate",
        "acquisition_performed": False,
        "raw_bods_material_included": False,
        "raw_identifiers_included": False,
        "session_salts_included": False,
        "cross_session_linkage_performed": False,
        "parent_manifest_sha256": PARENT_MANIFEST_SHA256,
        "approval_sha256": APPROVAL_SHA256,
        "corridor": {
            "experiment_id": "B-BUS-CORRIDOR-DAWN-PEAK-20260728",
            "protocol_sha256": CORRIDOR_PROTOCOL_SHA256,
            "full_coverage_required": True,
            "vec06_receipt_created": False,
            "sessions": corridor_reports,
        },
        "sparse64": {
            "experiment_id": "B-BUS-SPARSE64-DAWN-PEAK-20260728",
            "protocol_sha256": SPARSE_PROTOCOL_SHA256,
            "site_selection_session": "dawn-20260728",
            "peak_influenced_site_selection": False,
            "site_count": SPARSE_SITE_COUNT,
            "site_array_sha256": _sha256_file(site_path),
            "selection": {
                "occupied_cells": sparse.occupied_cells,
                "total_vehicle_seconds": sparse.total_vehicle_seconds,
                "safely_covered_cells": sparse.safely_covered_cells,
                "safely_covered_vehicle_seconds": sparse.safely_covered_vehicle_seconds,
                "iteration_gains": list(sparse.iteration_gains),
                "remaining_uncovered_cells": sparse.remaining_uncovered_cells,
            },
            "vec06_compatible": False,
            "sessions": sparse_reports,
        },
        "colab_pack_created": False,
        "gpu_execution_performed": False,
        "scientific_evidence": False,
        "actor_admission_eligible": False,
    }
    manifest_path = output / "successor_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _scan_private_text(output)
    return {
        "output": str(output),
        "manifest_sha256": _sha256_file(manifest_path),
        "corridor_ready": True,
        "sparse64_ready": True,
    }


def _read_npz(path: Path) -> dict[str, Any]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            return {key: archive[key] for key in archive.files}
    except (OSError, ValueError) as exc:
        raise BBusSuccessorError(f"cannot read derived trace {path.name}") from exc


def _write_npz(path: Path, arrays: dict[str, Any]) -> None:
    np.savez_compressed(path, **arrays)


def _read_spans(path: Path) -> tuple[OccupancySpan, ...]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != OCCUPANCY_HEADER:
                raise BBusSuccessorError("occupancy header changed")
            return tuple(
                OccupancySpan(
                    sumo_vehicle_id=row["sumo_vehicle_id"],
                    slot=int(row["slot"]),
                    t_enter=int(row["t_enter"]),
                    t_exit=int(row["t_exit"]),
                )
                for row in reader
            )
    except (OSError, KeyError, ValueError) as exc:
        if isinstance(exc, BBusSuccessorError):
            raise
        raise BBusSuccessorError(f"cannot read derived occupancy {path.name}") from exc


def _write_spans(path: Path, spans: tuple[OccupancySpan, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OCCUPANCY_HEADER)
        writer.writerows(span.as_row() for span in spans)


def _verify_protocols(repo: Path) -> None:
    expected = {
        CORRIDOR_PROTOCOL_PATH: CORRIDOR_PROTOCOL_SHA256,
        SPARSE_PROTOCOL_PATH: SPARSE_PROTOCOL_SHA256,
        APPROVAL_PATH: APPROVAL_SHA256,
    }
    for relative, digest in expected.items():
        if _sha256_file(repo / relative) != digest:
            raise BBusSuccessorError(f"protocol binding changed: {relative}")
    approval = json.loads((repo / APPROVAL_PATH).read_text(encoding="utf-8"))
    if approval.get("approved") is not True or not approval["scope"]["both_successors_authorised"]:
        raise BBusSuccessorError("owner approval does not authorise both successors")


def _repository_root() -> Path:
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise BBusSuccessorError("repository root could not be resolved")


def _resolve_existing(repo: Path, requested: Path) -> Path:
    path = requested.expanduser()
    path = (repo / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.exists():
        raise BBusSuccessorError(f"required path does not exist: {requested}")
    return path


def _new_private_output(repo: Path, requested: Path) -> Path:
    output = requested.expanduser()
    output = (repo / output).resolve() if not output.is_absolute() else output.resolve()
    data = (repo / "data").resolve()
    if output == data or not output.is_relative_to(data):
        raise BBusSuccessorError("output must be a named child of the private data tree")
    if output.exists():
        raise BBusSuccessorError("private successor output is new-only and never overwritten")
    output.mkdir(parents=True)
    return output


def _scan_private_text(root: Path) -> None:
    forbidden = ("operatorref", "vehicleref", '"session_salt"', '"raw_reference"')
    for path in root.rglob("*"):
        if path.suffix not in {".csv", ".json", ".txt"}:
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        if any(marker in lowered for marker in forbidden):
            raise BBusSuccessorError(f"forbidden raw-identity marker in {path.name}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BBusSuccessorError(f"cannot hash required file: {path}") from exc
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

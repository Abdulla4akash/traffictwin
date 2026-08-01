#!/usr/bin/env python3
"""Dhaka corridor network build (owner-authorised; feasibility artifact only).

Runs the corridor contract end to end AFTER the owner has answered BD-D1
(the frozen corridor scope JSON) and BD-D2 (the pinned dated extract), and
ONLY with ``--confirm-network`` for the acquisition stage. A download is not
authorised merely because this script exists.

Stages (each resumable via a writer-written ``.done`` marker):
    acquire  — download the pinned dated extract (needs --confirm-network),
               verify byte size + sha256 against the pin before promotion
    clip     — bounded ``osmium extract`` to the frozen corridor bbox
    decode   — bounded ``osmium cat`` PBF→XML (netconvert reads XML only)
    build    — pinned ``netconvert`` corridor build
    validate — streaming structure scan, extent through the network's OWN
               projParameter, landmark reconciliation, receipt + acceptance

The result is a receipted network-build feasibility artifact: role
``corridor_network_candidate``, ``observation_status: unavailable``, ODbL
attribution carried, no traffic/VEC claim of any kind. Stop rule: one
corridor, one pinned extract; nothing here expands to a city-wide build.

Usage:
    uv run python scripts/build_dhaka_corridor_network.py \
        --workspace <workspace> --scope <scope.json> --pin <pin.json> \
        [--confirm-network] [--landmark-tolerance-m 150]
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from pyproj import CRS, Transformer

from traffictwin.integration.corridor_network import (
    CorridorBuildReceipt,
    CorridorNetworkError,
    ExtractPin,
    NetworkStructure,
    assess_feasibility,
    canonical_network_identity,
    classify_extent,
    contained_destination,
    load_corridor_scope,
    netconvert_arguments,
    osmium_clip_arguments,
    osmium_export_arguments,
    receipt_to_json,
    verify_extract,
)

_EDGE_RE = re.compile(rb"<edge id=\"([^\"]+)\"")
_SHAPE_RE = re.compile(rb"\bshape=\"")
_JUNCTION_RE = re.compile(rb"<junction id=\"[^\"]+\"[^>]*\bx=\"([-0-9.]+)\" y=\"([-0-9.]+)\"")
_LOCATION_RE = re.compile(
    rb"<location netOffset=\"([^\"]+)\" convBoundary=\"([^\"]+)\""
    rb"[^>]*projParameter=\"([^\"]+)\""
)
_MAX_LINE_BYTES = 65_536


def _stage_done(marker: Path) -> bool:
    return marker.exists()


def _mark_done(marker: Path) -> None:
    marker.write_text(datetime.now(UTC).isoformat() + "\n", encoding="utf-8")


def _run_bounded(argv: list[str], log_path: Path) -> float:
    started = time.monotonic()
    with log_path.open("ab") as log_file:
        completed = subprocess.run(  # noqa: S603 - fixed argv from the contract, never a shell
            argv, stdout=log_file, stderr=subprocess.STDOUT, check=False
        )
    if completed.returncode != 0:
        raise CorridorNetworkError(
            "TOOL_FAILED",
            f"{argv[0]} exited {completed.returncode}; see {log_path.name}",
        )
    return time.monotonic() - started


def _tool_version(executable: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed argv, version probe only
        [executable, "--version"], capture_output=True, text=True, check=False
    )
    first_line = (completed.stdout or completed.stderr or "unknown").splitlines()[0]
    return first_line.strip()[:120]


def _acquire(pin: ExtractPin, destination: Path, *, confirmed: bool) -> None:
    if not confirmed:
        raise CorridorNetworkError(
            "NETWORK_NOT_CONFIRMED",
            "acquiring the extract needs --confirm-network; a download is not "
            "authorised merely because this script exists (BD-D2)",
        )
    print(f"downloading pinned extract ({pin.byte_size} bytes) …", flush=True)
    with urllib.request.urlopen(pin.url, timeout=600) as response:  # noqa: S310 - pinned https URL from the owner's BD-D2 answer
        raw = response.read(pin.byte_size + 1)
    if len(raw) != pin.byte_size:
        raise CorridorNetworkError(
            "EXTRACT_CHECKSUM_DRIFT",
            f"provider returned {len(raw)} bytes; the pin records {pin.byte_size}",
        )
    digest = hashlib.sha256(raw).hexdigest()
    if digest != pin.sha256:
        raise CorridorNetworkError(
            "EXTRACT_CHECKSUM_DRIFT",
            f"downloaded sha256 {digest[:12]}… does not match the pin",
        )
    destination.write_bytes(raw)


def _scan_network(
    path: Path,
) -> tuple[NetworkStructure, list[tuple[float, float]], tuple[str, str, str]]:
    """Streaming one-pass scan: structure counts, junctions, location header."""

    edge_total = edge_internal = edges_with_shape = junction_count = 0
    junctions_xy: list[tuple[float, float]] = []
    location: tuple[str, str, str] | None = None
    with path.open("rb") as handle:
        for line in handle:
            if len(line) > _MAX_LINE_BYTES:
                raise CorridorNetworkError(
                    "NETWORK_LINE_UNBOUNDED", "a network line exceeds the reviewed bound"
                )
            edge_match = _EDGE_RE.search(line)
            if edge_match is not None:
                edge_total += 1
                if edge_match.group(1).startswith(b":"):
                    edge_internal += 1
                elif _SHAPE_RE.search(line):
                    edges_with_shape += 1
                continue
            junction_match = _JUNCTION_RE.search(line)
            if junction_match is not None:
                junction_count += 1
                junctions_xy.append(
                    (float(junction_match.group(1)), float(junction_match.group(2)))
                )
                continue
            location_match = _LOCATION_RE.search(line)
            if location_match is not None:
                location = (
                    location_match.group(1).decode(),
                    location_match.group(2).decode(),
                    location_match.group(3).decode(),
                )
    if location is None:
        raise CorridorNetworkError("NETWORK_LOCATION_MISSING", "no <location> header found")
    real_edges = edge_total - edge_internal
    structure = NetworkStructure(
        edge_count_total=edge_total,
        edge_count_internal=edge_internal,
        edge_count_real=real_edges,
        junction_count=junction_count,
        no_shape_edge_share=(0.0 if real_edges == 0 else 1.0 - (edges_with_shape / real_edges)),
    )
    return structure, junctions_xy, location


def _junctions_lonlat(
    junctions_xy: list[tuple[float, float]], net_offset: str, proj_parameter: str
) -> list[tuple[float, float]]:
    """network = utm + netOffset, inverse-projected via the network's OWN CRS."""

    offset_x, offset_y = (float(value) for value in net_offset.split(","))
    transformer = Transformer.from_crs(CRS.from_proj4(proj_parameter), "EPSG:4326", always_xy=True)
    return [transformer.transform(x - offset_x, y - offset_y) for x, y in junctions_xy]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--scope", required=True, type=Path, help="BD-D1 frozen scope JSON")
    parser.add_argument("--pin", required=True, type=Path, help="BD-D2 extract pin JSON")
    parser.add_argument("--confirm-network", action="store_true")
    parser.add_argument("--landmark-tolerance-m", type=float, default=150.0)
    args = parser.parse_args()

    try:
        scope = load_corridor_scope(args.scope)
        pin = ExtractPin.model_validate_json(args.pin.read_text(encoding="utf-8"))
        workspace = args.workspace.expanduser().resolve()
        build_root = contained_destination(workspace, "network-build/dhaka-corridor")
        build_root.mkdir(parents=True, exist_ok=True)
        log_path = build_root / "build.log"
        durations: dict[str, float] = {}

        extract_path = build_root / Path(pin.url).name
        if not _stage_done(build_root / "acquire.done"):
            started = time.monotonic()
            _acquire(pin, extract_path, confirmed=args.confirm_network)
            durations["acquire"] = time.monotonic() - started
            _mark_done(build_root / "acquire.done")
        verify_extract(extract_path, pin)
        source_sha = pin.sha256

        clipped_path = build_root / "corridor.osm.pbf"
        if not _stage_done(build_root / "clip.done"):
            durations["clip"] = _run_bounded(
                osmium_clip_arguments(scope, extract_path, clipped_path), log_path
            )
            _mark_done(build_root / "clip.done")

        decoded_path = build_root / "corridor.osm"
        if not _stage_done(build_root / "decode.done"):
            durations["decode"] = _run_bounded(
                osmium_export_arguments(clipped_path, decoded_path), log_path
            )
            _mark_done(build_root / "decode.done")

        network_path = build_root / "dhaka-corridor.net.xml"
        if not _stage_done(build_root / "build.done"):
            durations["build"] = _run_bounded(
                netconvert_arguments(decoded_path, network_path), log_path
            )
            _mark_done(build_root / "build.done")

        started = time.monotonic()
        structure, junctions_xy, (net_offset, conv_boundary, proj_parameter) = _scan_network(
            network_path
        )
        extent = classify_extent(
            scope,
            proj_parameter=proj_parameter,
            net_offset=net_offset,
            conv_boundary=conv_boundary,
            junctions_lonlat=_junctions_lonlat(junctions_xy, net_offset, proj_parameter),
            landmark_tolerance_m=args.landmark_tolerance_m,
        )
        gaps = assess_feasibility(structure, extent)
        durations["validate"] = time.monotonic() - started
        receipt = CorridorBuildReceipt(
            scope=scope,
            extract_pin=pin,
            extract_verified=True,
            source_sha256=source_sha,
            derived_network_sha256=hashlib.sha256(network_path.read_bytes()).hexdigest(),
            derived_canonical_identity=canonical_network_identity(network_path),
            tool_versions={
                "osmium": _tool_version("osmium"),
                "netconvert": _tool_version("netconvert"),
            },
            stage_durations_seconds=durations,
            structure=structure,
            extent=extent,
            network_artifact_name=network_path.name,
            feasibility_gaps=gaps,
            accepted=not gaps,
            generated_at_utc=datetime.now(UTC).isoformat(),
        )
        receipt_path = build_root / "corridor_build_receipt.json"
        receipt_path.write_text(receipt_to_json(receipt) + "\n", encoding="utf-8")
    except CorridorNetworkError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"receipt: {receipt_path}", flush=True)
    print(
        f"accepted: {receipt.accepted}; real edges {structure.edge_count_real}; "
        f"junctions {structure.junction_count}; corridor contained: "
        f"{extent.requested_corridor_contained}",
        flush=True,
    )
    for gap in gaps:
        print(f"  feasibility gap: {gap}", flush=True)
    return 0 if receipt.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())

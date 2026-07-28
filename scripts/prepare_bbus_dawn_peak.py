#!/usr/bin/env python3
"""Derive the two captured B-BUS motion bundles without acquiring anything.

The command verifies and reprocesses the exact dawn and peak quarantines,
matches fixes against the rebuilt Greater Manchester network, delegates route
search to SUMO's ``duarouter``, applies the owner-approved drop rules, and
writes only private derived artifacts below the repository's gitignored
``data/`` tree.  Raw BODS bytes, raw identifiers and session salts never enter
an output.

The current approved full-fleet design is expected to fail the accepted
VEC-06 placement bound.  That refusal is an output, not an exception and not a
reason to trim the fleet.  No Colab-ready archive is produced while the
placement gate is false.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, ElementTree, SubElement, iterparse

import numpy as np
from pyproj import Transformer

from traffictwin.integration.manchester.bods_session_identity import (
    SessionObservation,
    extract_session_observations,
)
from traffictwin.integration.manchester.bus_trace_campaign import (
    DWELL_RADIUS_M,
    GAP_CEILING_S,
    CampaignFix,
    ProjectedCandidate,
    build_vehicle_observation,
    derive_approved_campaign_trace,
    routed_path,
    select_position_candidate,
)
from traffictwin.integration.manchester.bus_trajectory import MatchedPath
from traffictwin.integration.manchester.bus_vec_bridge import (
    OCCUPANCY_HEADER,
    build_vec06_inputs,
    reconcile_spans_with_mask,
)
from traffictwin.integration.manchester.network_geometry import (
    INTERNAL_EDGE_PREFIX,
    EdgeSpatialIndex,
    build_edge_index,
)

METHOD_VERSION = "bbus-dawn-peak-private-preparation-1.0"
EXPERIMENT_ID = "B-BUS-DAWN-PEAK-20260728"
PROTOCOL_PATH = "docs/evaluation/bbus_dawn_peak_protocol_20260728.md"
PROTOCOL_SHA256 = "b0b3522481076e2dfdc7668a34a9e07146a3de78f60e740b49ebf2dce23ce65c"
APPROVAL_PATH = "docs/integration/evidence/bbus_dawn_peak_owner_approval_20260728.json"
NETWORK_RELATIVE_PATH = "data/network-build/gm-baseline-20260728/gm-baseline-20260728.net.xml"
NETWORK_SHA256 = "59e4c22daa81cdaa8aa4ed6a93a2485f586f03afc4fc5a9779365ad8bef0c25c"
NETWORK_IDENTITY_SHA256 = "ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577"
NETWORK_ACCEPTED_FOR_REAL_MATCHING = False
DEFAULT_OUTPUT = "data/bbus-dawn-peak-20260728"
DUAROUTER_TIMEOUT_S = 900
PLACEMENT_CELL_M = 50.0
PLACEMENT_RADIUS_M = 500.0
PLACEMENT_MAX_RSUS = 64
PLACEMENT_MAX_OCCUPIED_CELLS = 2_000

_ATTRIBUTE = re.compile(rb"\b([A-Za-z_:][A-Za-z0-9_.:-]*)=\"([^\"]*)\"")
_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "operatorref",
        "vehicleref",
        "operator_ref",
        "vehicle_ref",
        "session_salt",
        "raw_reference",
        "line_ref",
        "journey_ref",
    }
)


@dataclass(frozen=True)
class SessionSpec:
    label: str
    first_snapshot_id: str
    last_snapshot_id: str
    window_start_utc: str
    window_end_utc: str
    expected_snapshot_count: int
    cadence_sha256: str

    @property
    def start(self) -> datetime:
        return datetime.fromisoformat(self.window_start_utc.replace("Z", "+00:00"))

    @property
    def end(self) -> datetime:
        return datetime.fromisoformat(self.window_end_utc.replace("Z", "+00:00"))


SESSIONS = (
    SessionSpec(
        label="dawn-20260728",
        first_snapshot_id="bods_siri_vm-20260728T051226Z-6ab218c0feb8",
        last_snapshot_id="bods_siri_vm-20260728T060933Z-47704edbb02e",
        window_start_utc="2026-07-28T05:12:26Z",
        window_end_utc="2026-07-28T06:09:33Z",
        expected_snapshot_count=52,
        cadence_sha256="ed06e52eac23bd8fc25c62b7c3870b06ec3a50088450d53c2dff80daa8656220",
    ),
    SessionSpec(
        label="peak-20260728",
        first_snapshot_id="bods_siri_vm-20260728T070223Z-56c2ffcd4e18",
        last_snapshot_id="bods_siri_vm-20260728T075851Z-57bf1f00cfa6",
        window_start_utc="2026-07-28T07:02:23Z",
        window_end_utc="2026-07-28T07:58:51Z",
        expected_snapshot_count=52,
        cadence_sha256="aeb282d7be9d20e2d32fd9586f973a191a6a6a188316818bed309779878e2756",
    ),
)


@dataclass(frozen=True, slots=True)
class RouteRequest:
    route_id: str
    vehicle_key: str
    segment_index: int
    start: ProjectedCandidate
    end: ProjectedCandidate


class BBusPreparationError(RuntimeError):
    """Raised when private preparation cannot continue without changing design."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    parser.add_argument("--network", type=Path, default=Path(NETWORK_RELATIVE_PATH))
    parser.add_argument("--duarouter", type=Path, default=None)
    arguments = parser.parse_args(argv)
    try:
        result = prepare_bbus_sessions(
            arguments.workspace,
            output_root=arguments.output,
            network_path=arguments.network,
            duarouter_path=arguments.duarouter,
        )
    except BBusPreparationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def prepare_bbus_sessions(
    workspace: Path,
    *,
    output_root: Path,
    network_path: Path,
    duarouter_path: Path | None = None,
) -> dict[str, Any]:
    """Prepare both fixed sessions into a new private output directory."""

    repo = _repository_root()
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise BBusPreparationError(f"workspace does not exist: {workspace}")
    output = _new_private_output(repo, output_root)
    network = network_path.expanduser().resolve()
    if not network.is_file() or _sha256_file(network) != NETWORK_SHA256:
        raise BBusPreparationError("rebuilt network is absent or has changed identity")
    _verify_protocol_and_approval(repo)
    duarouter = _resolve_duarouter(duarouter_path)

    started = time.perf_counter()
    index = build_edge_index(network)
    edge_ordinals = {index.edge_record(ordinal)[0]: ordinal for ordinal in range(len(index))}
    bus_edges = bus_eligible_edge_ids(network)
    projection = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)

    session_results: list[dict[str, Any]] = []
    try:
        for spec in SESSIONS:
            session_results.append(
                _prepare_session(
                    workspace=workspace,
                    output=output,
                    network=network,
                    duarouter=duarouter,
                    spec=spec,
                    index=index,
                    edge_ordinals=edge_ordinals,
                    bus_edges=bus_edges,
                    projection=projection,
                )
            )
        combined = {
            "schema_version": "1.0",
            "method_version": METHOD_VERSION,
            "experiment_id": EXPERIMENT_ID,
            "research_status": "owner_approved_candidate",
            "scientific_evidence": False,
            "actor_admission_eligible": False,
            "acquisition_performed": False,
            "raw_bods_material_included": False,
            "raw_identifiers_included": False,
            "session_salts_persisted": False,
            "cross_session_linkage_performed": False,
            "derived_scenario": True,
            "observed_fcd": False,
            "buses_only": True,
            "network_sha256": NETWORK_SHA256,
            "network_identity_sha256": NETWORK_IDENTITY_SHA256,
            "network_accepted_for_real_matching": NETWORK_ACCEPTED_FOR_REAL_MATCHING,
            "protocol_path": PROTOCOL_PATH,
            "protocol_sha256": PROTOCOL_SHA256,
            "approval_path": APPROVAL_PATH,
            "sessions": session_results,
            "colab_ready": all(item["colab_ready"] for item in session_results),
            "elapsed_seconds": time.perf_counter() - started,
        }
        combined_path = output / "preparation_manifest.json"
        _write_json(combined_path, combined)
        _assert_private_output(combined_path)
        return {
            "output": str(output),
            "manifest_sha256": _sha256_file(combined_path),
            "colab_ready": combined["colab_ready"],
            "session_count": len(session_results),
        }
    except Exception:
        # The output is private and new-only.  Preserve partial diagnostics for
        # inspection rather than deleting or overwriting them on a retry.
        raise


def _prepare_session(
    *,
    workspace: Path,
    output: Path,
    network: Path,
    duarouter: Path,
    spec: SessionSpec,
    index: EdgeSpatialIndex,
    edge_ordinals: Mapping[str, int],
    bus_edges: frozenset[str],
    projection: Transformer,
) -> dict[str, Any]:
    session_dir = output / spec.label
    session_dir.mkdir()
    snapshot_ids = _select_snapshot_ids(
        workspace / "quarantine",
        first_snapshot_id=spec.first_snapshot_id,
        last_snapshot_id=spec.last_snapshot_id,
    )
    if len(snapshot_ids) != spec.expected_snapshot_count:
        raise BBusPreparationError(f"{spec.label}: snapshot count changed")

    salt = secrets.token_bytes(32)
    grouped: dict[str, list[SessionObservation]] = defaultdict(list)
    activities_seen = malformed = extracted = 0
    member_hashes: list[str] = []
    for snapshot_id in snapshot_ids:
        result = extract_session_observations(workspace, snapshot_id, session_salt=salt)
        activities_seen += result.activities_seen
        malformed += result.malformed_skipped
        extracted += result.observations_extracted
        member_hashes.append(result.member_sha256)
        for observation in result.observations:
            grouped[observation.session_token].append(observation)
    # Do not retain the salt beyond extraction.  Overwriting the local name is
    # not a claim about Python memory erasure; it ensures no later output code
    # has a reference it could serialize.
    salt = b""

    vehicles, matching = _match_session(
        grouped,
        spec=spec,
        index=index,
        bus_edges=bus_edges,
        projection=projection,
    )
    requests = _route_requests(vehicles)
    request_path = session_dir / "route_requests.xml"
    route_path = session_dir / "routed_edges.xml"
    _write_route_requests(request_path, requests)
    router = _run_duarouter(
        duarouter=duarouter,
        network=network,
        route_requests=request_path,
        output=route_path,
        log_path=session_dir / "duarouter.log",
    )
    route_edges = _read_routed_edges(route_path)
    paths_by_vehicle: dict[str, dict[int, MatchedPath | None]] = defaultdict(dict)
    paths_constructed = 0
    for request in requests:
        edges = route_edges.get(request.route_id)
        path = (
            None
            if edges is None
            else routed_path(
                route_edge_ids=edges,
                start=request.start,
                end=request.end,
                index=index,
                edge_ordinals=edge_ordinals,
            )
        )
        paths_by_vehicle[request.vehicle_key][request.segment_index] = path
        paths_constructed += path is not None

    observations = tuple(
        build_vehicle_observation(
            vehicle_key=vehicle_key,
            fixes=fixes,
            routes_by_segment=paths_by_vehicle.get(vehicle_key, {}),
        )
        for vehicle_key, fixes in sorted(vehicles.items())
    )
    approved = derive_approved_campaign_trace(observations, trace_label=spec.label)
    bridge = build_vec06_inputs(
        approved.derivation,
        input_id=f"bbus-{spec.label}",
        scenario_day="2026-07-28",
        window_label=spec.label,
        sumo_seed=42,
    )
    reconcile_spans_with_mask(bridge.spans, bridge.arrays.mask)

    motion_path = session_dir / "motion_trace.npz"
    motion = bridge.arrays.as_npz_mapping()
    motion["window"] = np.asarray(spec.label)
    motion["sumo_seed"] = np.int32(42)
    np.savez_compressed(motion_path, **motion)
    occupancy_path = session_dir / "occupancy.csv"
    _write_occupancy(occupancy_path, bridge.occupancy_rows())

    placement = _placement_preflight(bridge.arrays.pos_x, bridge.arrays.pos_y, bridge.arrays.mask)
    report = {
        "schema_version": "1.0",
        "method_version": METHOD_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "session": asdict(spec),
        "research_status": "owner_approved_candidate",
        "scientific_evidence": False,
        "network_accepted_for_real_matching": False,
        "derived_scenario": True,
        "observed_fcd": False,
        "buses_only": True,
        "acquisition_performed": False,
        "raw_identifiers_published": False,
        "session_salt_persisted": False,
        "source_accounting": {
            "snapshot_count": len(snapshot_ids),
            "activities_seen": activities_seen,
            "observations_extracted": extracted,
            "malformed_skipped": malformed,
            "member_set_sha256": _sha256_json(sorted(member_hashes)),
        },
        "matching": matching,
        "routing": {
            **router,
            "requests": len(requests),
            "routes_returned": len(route_edges),
            "paths_constructed": paths_constructed,
            "path_construction_refusals": len(requests) - paths_constructed,
        },
        "trajectory": approved.report.model_dump(mode="json"),
        "bridge": {
            **bridge.request_draft.model_dump(mode="json"),
            "motion_trace_sha256": _sha256_file(motion_path),
            "occupancy_sha256": _sha256_file(occupancy_path),
            "mask_active_cells": int(bridge.arrays.mask.sum()),
            "span_mask_reconciled": True,
        },
        "placement_preflight": placement,
        "vec06_admitted": False,
        "colab_ready": placement["status"] == "passed",
        "limitations": [
            "The network is reviewed but not accepted for real matching.",
            "The trace is a derived bus-only scenario, not observed FCD or general traffic.",
            "A false placement gate blocks a Colab-ready archive; it is never bypassed.",
        ],
    }
    report_path = session_dir / "trace_preparation_report.json"
    _write_json(report_path, report)
    for path in (motion_path, occupancy_path, request_path, route_path, report_path):
        _assert_private_output(path)
    return {
        "label": spec.label,
        "report_path": f"{spec.label}/{report_path.name}",
        "report_sha256": _sha256_file(report_path),
        "motion_trace_sha256": _sha256_file(motion_path),
        "occupancy_sha256": _sha256_file(occupancy_path),
        "colab_ready": report["colab_ready"],
        "placement_status": placement["status"],
        "placement_refusal_code": placement.get("refusal_code"),
    }


def _match_session(
    grouped: Mapping[str, Sequence[SessionObservation]],
    *,
    spec: SessionSpec,
    index: EdgeSpatialIndex,
    bus_edges: frozenset[str],
    projection: Transformer,
) -> tuple[dict[str, tuple[CampaignFix, ...]], dict[str, Any]]:
    vehicles: dict[str, tuple[CampaignFix, ...]] = {}
    total_rows = repeated_rows = out_of_window = matched = tied = 0
    sources: dict[str, int] = defaultdict(int)
    distances: list[float] = []
    for vehicle_key, observations in grouped.items():
        total_rows += len(observations)
        by_time: dict[datetime, tuple[float, float]] = {}
        for observation in observations:
            position = (float(observation.longitude), float(observation.latitude))
            prior = by_time.get(observation.recorded_at_utc)
            if prior is not None and prior != position:
                raise BBusPreparationError(
                    f"{spec.label}: one session token has conflicting positions at one time"
                )
            if prior is not None:
                repeated_rows += 1
            by_time[observation.recorded_at_utc] = position
        fixes: list[CampaignFix] = []
        for timestamp, (longitude, latitude) in sorted(by_time.items()):
            if timestamp < spec.start or timestamp > spec.end:
                out_of_window += 1
                continue
            epoch = timestamp.timestamp()
            if epoch != int(epoch):
                raise BBusPreparationError(f"{spec.label}: a fix is not on a whole second")
            x_m, y_m = projection.transform(longitude, latitude)
            candidate, exact_tie = select_position_candidate(
                index=index,
                x_m=x_m,
                y_m=y_m,
                bus_eligible_edge_ids=bus_edges,
            )
            if candidate is not None:
                matched += 1
                distances.append(candidate.distance_m)
                sources[candidate.geometry_source] += 1
            tied += exact_tie
            fixes.append(
                CampaignFix(
                    timestamp_s=int(epoch),
                    projected_x_m=x_m,
                    projected_y_m=y_m,
                    candidate=candidate,
                )
            )
        if fixes:
            vehicles[vehicle_key] = tuple(fixes)
    fix_count = sum(len(fixes) for fixes in vehicles.values())
    shares = [
        sum(fix.candidate is not None for fix in fixes) / len(fixes) for fixes in vehicles.values()
    ]
    ordered_distances = sorted(distances)
    return vehicles, {
        "rows_extracted": total_rows,
        "repeated_rows_deduplicated": repeated_rows,
        "distinct_fixes_outside_declared_observation_window": out_of_window,
        "distinct_fixes_in_window": fix_count,
        "vehicles_with_in_window_fix": len(vehicles),
        "matched_fixes": matched,
        "matched_fix_share": matched / fix_count if fix_count else None,
        "vehicles_at_or_above_80pct_matched_share": sum(share >= 0.8 for share in shares),
        "exact_distance_ties_settled_by_edge_id": tied,
        "selected_geometry_sources": dict(sorted(sources.items())),
        "selected_distance_m_p50": _percentile(ordered_distances, 0.5),
        "selected_distance_m_p90": _percentile(ordered_distances, 0.9),
        "selected_distance_m_max": max(ordered_distances) if ordered_distances else None,
    }


def _select_snapshot_ids(
    quarantine: Path, *, first_snapshot_id: str, last_snapshot_id: str
) -> tuple[str, ...]:
    """Select the same exact inclusive quarantine range as the post-hoc pass."""

    prefix = "bods_siri_vm-"
    if not quarantine.is_dir():
        raise BBusPreparationError("quarantine directory is unavailable")
    for value in (first_snapshot_id, last_snapshot_id):
        if not value.startswith(prefix) or "/" in value or "\\" in value:
            raise BBusPreparationError("an exact snapshot bound is unsafe")
    if first_snapshot_id > last_snapshot_id:
        raise BBusPreparationError("snapshot bounds are reversed")
    available = tuple(
        sorted(
            path.name
            for path in quarantine.iterdir()
            if path.is_dir() and path.name.startswith(prefix)
        )
    )
    if first_snapshot_id not in available or last_snapshot_id not in available:
        raise BBusPreparationError("both exact snapshot bounds must exist")
    selected = tuple(item for item in available if first_snapshot_id <= item <= last_snapshot_id)
    if len(selected) < 2:
        raise BBusPreparationError("a session requires at least two snapshots")
    return selected


def _route_requests(
    vehicles: Mapping[str, Sequence[CampaignFix]],
) -> tuple[RouteRequest, ...]:
    requests: list[RouteRequest] = []
    for vehicle_key, fixes in sorted(vehicles.items()):
        for segment_index, (start, end) in enumerate(zip(fixes, fixes[1:], strict=False)):
            elapsed = end.timestamp_s - start.timestamp_s
            if elapsed <= 0:
                raise BBusPreparationError("deduplicated fixes are not strictly increasing")
            if elapsed > GAP_CEILING_S or start.candidate is None or end.candidate is None:
                continue
            displacement = math.hypot(
                end.candidate.snapped_x_m - start.candidate.snapped_x_m,
                end.candidate.snapped_y_m - start.candidate.snapped_y_m,
            )
            if displacement <= DWELL_RADIUS_M:
                continue
            requests.append(
                RouteRequest(
                    route_id=f"segment-{len(requests):07d}",
                    vehicle_key=vehicle_key,
                    segment_index=segment_index,
                    start=start.candidate,
                    end=end.candidate,
                )
            )
    return tuple(requests)


def bus_eligible_edge_ids(network: Path) -> frozenset[str]:
    """Return real edges for which at least one lane explicitly permits a bus."""

    allowed: set[str] = set()
    pending_id: str | None = None
    pending_allows_bus = False
    with network.open("rb") as handle:
        for line in handle:
            if b"<edge " in line:
                if pending_id is not None and pending_allows_bus:
                    allowed.add(pending_id)
                attributes = _attributes(line)
                edge_id = attributes.get("id")
                internal = (
                    edge_id is None
                    or edge_id.startswith(INTERNAL_EDGE_PREFIX.decode("ascii"))
                    or attributes.get("function") == "internal"
                )
                pending_id = None if internal else edge_id
                pending_allows_bus = False
                if line.rstrip().endswith(b"/>"):
                    pending_id = None
            elif pending_id is not None and b"<lane " in line:
                attributes = _attributes(line)
                if _lane_allows_bus(attributes.get("allow"), attributes.get("disallow")):
                    pending_allows_bus = True
        if pending_id is not None and pending_allows_bus:
            allowed.add(pending_id)
    return frozenset(allowed)


def _lane_allows_bus(allow: str | None, disallow: str | None) -> bool:
    if allow is not None and disallow is not None:
        return False
    if allow is not None:
        return "bus" in allow.split()
    if disallow is not None:
        return "bus" not in disallow.split()
    return True


def _attributes(line: bytes) -> dict[str, str]:
    return {
        key.decode("utf-8", "replace"): value.decode("utf-8", "replace")
        for key, value in _ATTRIBUTE.findall(line)
    }


def _write_route_requests(path: Path, requests: Sequence[RouteRequest]) -> None:
    root = Element("routes")
    SubElement(root, "vType", {"id": "bbus", "vClass": "bus"})
    for request in requests:
        SubElement(
            root,
            "trip",
            {
                "id": request.route_id,
                "type": "bbus",
                "depart": "0",
                "from": request.start.edge_id,
                "to": request.end.edge_id,
            },
        )
    ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _run_duarouter(
    *,
    duarouter: Path,
    network: Path,
    route_requests: Path,
    output: Path,
    log_path: Path,
) -> dict[str, Any]:
    command = [
        str(duarouter),
        "--net-file",
        str(network),
        "--route-files",
        str(route_requests),
        "--output-file",
        str(output),
        "--ignore-errors",
        "true",
        "--no-warnings",
        "true",
        "--routing-algorithm",
        "astar",
        "--seed",
        "42",
    ]
    started = time.perf_counter()
    completed = subprocess.run(  # noqa: S603 - resolved executable and fixed argv shape
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=DUAROUTER_TIMEOUT_S,
    )
    elapsed = time.perf_counter() - started
    bounded = (completed.stdout + "\n" + completed.stderr)[-100_000:]
    log_path.write_text(bounded, encoding="utf-8")
    if completed.returncode != 0 or not output.is_file():
        raise BBusPreparationError(
            f"duarouter failed with exit code {completed.returncode}; see private log"
        )
    return {
        "duarouter_sha256": _sha256_file(duarouter),
        "routing_algorithm": "astar",
        "routing_seed": 42,
        "exit_code": completed.returncode,
        "elapsed_seconds": elapsed,
        "log_sha256": _sha256_file(log_path),
    }


def _read_routed_edges(path: Path) -> dict[str, tuple[str, ...]]:
    routes: dict[str, tuple[str, ...]] = {}
    # This XML is the just-generated output of the resolved local duarouter
    # executable, not an external or caller-supplied document.
    for _, element in iterparse(path, events=("end",)):  # noqa: S314
        if element.tag != "vehicle":
            continue
        route_id = element.attrib.get("id")
        route = next((child for child in element if child.tag == "route"), None)
        if route_id is not None and route is not None:
            edges = tuple(route.attrib.get("edges", "").split())
            if edges:
                routes[route_id] = edges
        element.clear()
    return routes


def _write_occupancy(path: Path, rows: Iterable[Sequence[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(OCCUPANCY_HEADER)
        writer.writerows(rows)


def _placement_preflight(
    pos_x: np.ndarray[Any, Any],
    pos_y: np.ndarray[Any, Any],
    mask: np.ndarray[Any, Any],
) -> dict[str, Any]:
    points = np.stack((pos_x[mask], pos_y[mask]), axis=1)
    cells = np.unique(np.floor(points / PLACEMENT_CELL_M).astype(np.int64), axis=0)
    result: dict[str, Any] = {
        "strategy": "greedy_urban_cover",
        "radius_m": PLACEMENT_RADIUS_M,
        "cell_m": PLACEMENT_CELL_M,
        "max_rsus": PLACEMENT_MAX_RSUS,
        "max_occupied_cells": PLACEMENT_MAX_OCCUPIED_CELLS,
        "occupied_cells": len(cells),
        "placement_executed": False,
        "rsu_positions_generated": False,
    }
    if len(cells) > PLACEMENT_MAX_OCCUPIED_CELLS:
        result.update(
            {
                "status": "refused",
                "refusal_code": "OCCUPIED_PLACEMENT_CELLS_EXCEEDED",
                "reason": (
                    "the full-fleet trace exceeds the accepted safe set-cover cell bound; "
                    "the fleet is not trimmed and the bound is not raised"
                ),
            }
        )
        return result
    result.update({"status": "eligible_for_placement", "refusal_code": None})
    return result


def _verify_protocol_and_approval(repo: Path) -> None:
    protocol = repo / PROTOCOL_PATH
    approval = repo / APPROVAL_PATH
    if _sha256_file(protocol) != PROTOCOL_SHA256:
        raise BBusPreparationError("approved protocol bytes changed")
    try:
        receipt = json.loads(approval.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BBusPreparationError("owner approval receipt is unreadable") from exc
    if (
        receipt.get("approved") is not True
        or receipt.get("predeclaration_sha256") != PROTOCOL_SHA256
        or receipt.get("raw_bods_upload_authorised") is not False
    ):
        raise BBusPreparationError("owner approval receipt does not bind this protocol")


def _repository_root() -> Path:
    source = Path(__file__).resolve()
    for parent in source.parents:
        if (parent / "AGENTS.md").is_file():
            return parent
    raise BBusPreparationError("repository root could not be resolved")


def _new_private_output(repo: Path, requested: Path) -> Path:
    output = requested.expanduser()
    output = (repo / output).resolve() if not output.is_absolute() else output.resolve()
    data_root = (repo / "data").resolve()
    if output == data_root or not output.is_relative_to(data_root):
        raise BBusPreparationError("output must be a named child of the gitignored data tree")
    if output.is_symlink():
        raise BBusPreparationError("output must not be a symlink")
    if output.exists():
        raise BBusPreparationError("output already exists and is never overwritten")
    output.mkdir(parents=True)
    return output


def _resolve_duarouter(requested: Path | None) -> Path:
    candidate = (
        requested.expanduser().resolve()
        if requested is not None
        else Path(shutil.which("duarouter") or "")
    )
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise BBusPreparationError("duarouter executable is unavailable")
    return candidate


def _assert_private_output(path: Path) -> None:
    if path.suffix.lower() not in {".json", ".csv", ".xml", ".npz", ".log"}:
        raise BBusPreparationError(f"unexpected private output type: {path.name}")
    if path.suffix.lower() == ".npz":
        return
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    for marker in _FORBIDDEN_OUTPUT_KEYS:
        if marker in text:
            raise BBusPreparationError(f"forbidden raw-identity marker reached {path.name}")


def _percentile(values: Sequence[float], probability: float) -> float | None:
    if not values:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must lie in [0, 1]")
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())

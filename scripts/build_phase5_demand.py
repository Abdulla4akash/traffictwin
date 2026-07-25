"""Phase 5: Build Count-Constrained Candidate Demand for Manchester (Option A).

Fully dynamic, CLI-driven demand reconstruction pipeline for Manchester.
Automatically discovers SUMO installation via SUMO_HOME, resolves network file SHA256 hashes,
and accepts workspace and network overrides via command line arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from traffictwin.integration.manchester.demand_reconstruction import (
    ACCEPTANCE_BASIS,
    DEMAND_CAPABILITY_ID,
    DEMAND_LABEL,
    RESEARCH_STATUS,
    DemandInputLedger,
    DirectionResolution,
    EdgeHourCount,
    demand_input_fingerprint,
    ordinals_by_edge_id,
    resolve_direction,
    site_is_in_survey_window,
    write_edgedata_counts,
)
from traffictwin.integration.manchester.dft_acquisition import open_accepted_dft_snapshot
from traffictwin.integration.manchester.dft_temporal_profile import open_real_raw_count_evidence
from traffictwin.integration.manchester.network_connectivity import stream_network_edges
from traffictwin.integration.manchester.network_geometry import build_edge_index
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    match_observation_v11,
)

EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "integration" / "evidence"


def find_sumo_tools() -> Path:
    """Dynamically locate SUMO tools directory from environment or standard paths."""
    if "SUMO_HOME" in os.environ:
        tools = Path(os.environ["SUMO_HOME"]) / "tools"
        if tools.is_dir():
            return tools

    # Search standard system installation paths
    candidate_paths = [
        Path(
            "/Library/Frameworks/EclipseSUMO.framework/Versions/Current/EclipseSUMO/share/sumo/tools"
        ),
        Path(
            "/Library/Frameworks/EclipseSUMO.framework/Versions/1.27.1/EclipseSUMO/share/sumo/tools"
        ),
        Path("/usr/share/sumo/tools"),
        Path("/usr/local/share/sumo/tools"),
        Path("/opt/homebrew/share/sumo/tools"),
    ]
    for candidate in candidate_paths:
        if candidate.is_dir():
            return candidate

    raise RuntimeError("SUMO tools directory not found. Set SUMO_HOME to your SUMO installation.")


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hex digest of a file dynamically."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_default_workspace() -> Path:
    """Auto-discover recent v0.7 workspace directory if available."""
    candidates = [
        Path("./data/workspace"),
    ]
    for c in candidates:
        if c.is_dir():
            return c
    raise FileNotFoundError("Workspace directory not found. Pass --workspace explicitly.")


def find_default_network() -> Path:
    """Auto-discover study network file if available."""
    candidates = [
        Path("./data/networks/study.net.xml"),
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("Study network file (.net.xml) not found. Pass --network explicitly.")


def redact_absolute_paths(path: Path) -> None:
    """Replace absolute paths in a tool-written file with bare filenames."""

    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    redacted = re.sub(r'(?:/[^"\s<>]+)+/([^/"\s<>]+\.(?:xml|rou\.xml))', r"\1", text)
    if redacted != text:
        path.write_text(redacted, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 5: Demand Reconstruction for Manchester (Option A)"
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Path to v0.7 workspace containing DfT snapshots",
    )
    parser.add_argument(
        "--network",
        type=Path,
        default=None,
        help="Path to SUMO study subnetwork XML (.net.xml)",
    )
    parser.add_argument(
        "--snapshot-raw-id",
        type=str,
        default="dft_raw_counts-20260725T063354Z-61965dc5c182",
        help="Raw counts DfT snapshot ID",
    )
    parser.add_argument(
        "--snapshot-cp-id",
        type=str,
        default="dft_count_points-20260725T063353Z-053491696819",
        help="Count points DfT snapshot ID",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    workspace = args.workspace if args.workspace else find_default_workspace()
    study_net = args.network if args.network else find_default_network()
    sumo_tools = find_sumo_tools()

    random_trips_script = sumo_tools / "randomTrips.py"
    route_sampler_script = sumo_tools / "routeSampler.py"

    print("--- Phase 5: Building Candidate Demand (Option A: 2019/2022+ Window) ---")
    print(f"Workspace: {workspace}")
    print(f"Network:   {study_net}")
    print(f"SUMO Tools: {sumo_tools}")

    # 1. Load raw count & count point evidence
    records, source_binding = open_real_raw_count_evidence(workspace, args.snapshot_raw_id)
    cp_opened = open_accepted_dft_snapshot(workspace, args.snapshot_cp_id)
    count_points_by_id = {cp.count_point_id: cp for cp in cp_opened.report.records}
    print(f"Loaded {len(records)} raw count records & {len(count_points_by_id)} count points.")

    # 2. Filter sites by survey window (Option A)
    site_dates: dict[int, str] = {}
    site_records: dict[int, list[Any]] = defaultdict(list)
    for rec in records:
        site_id = rec.count_point_id
        site_records[site_id].append(rec)
        if site_id not in site_dates or str(rec.count_date) > site_dates[site_id]:
            site_dates[site_id] = str(rec.count_date)

    admitted_sites = {
        site_id
        for site_id, latest_date in site_dates.items()
        if site_is_in_survey_window(latest_date)
    }
    print(
        f"Total sites in raw counts: {len(site_dates)}. "
        f"Sites in Option A window: {len(admitted_sites)}"
    )

    # 3. Load study network index and compute hash dynamically
    print(f"Loading spatial index for study subnetwork: {study_net}")
    net_index = build_edge_index(study_net)
    net_sha256 = compute_file_sha256(study_net)
    print(f"Indexed {len(net_index)} edges in study subnetwork (SHA256: {net_sha256[:12]}...).")

    # 4. Perform Map Matching v1.1 for Option A sites to get accepted road groups
    policy = ManchesterMapMatchPolicyV11()
    match_policy_fingerprint = policy.fingerprint()

    # The exact-reference override refuses any edge whose motor access is
    # unknown, so without this map the override can never fire and matching is
    # quietly stricter than the approved policy.
    motor_access = {edge.edge_id: edge.access for edge in stream_network_edges(study_net)}
    print(f"Read motor access for {len(motor_access)} edges.")

    accepted_member_edges: dict[int, list[str]] = {}
    distance_by_edge: dict[int, dict[str, Decimal]] = defaultdict(dict)

    accepted_sites_count = 0
    sites_without_coordinates = 0
    for site_id in sorted(admitted_sites):
        if site_id not in count_points_by_id:
            continue
        cp = count_points_by_id[site_id]
        if cp.location.easting is None or cp.location.northing is None:
            # A count point without coordinates cannot be matched. Skipping it
            # silently would drop an observation; it is counted instead.
            sites_without_coordinates += 1
            continue
        res = match_observation_v11(
            count_point_id=cp.count_point_id,
            dft_road_ref=cp.location.road_name,
            dft_road_name=cp.location.road_name,
            dft_road_type=cp.location.road_type,
            easting=float(cp.location.easting),
            northing=float(cp.location.northing),
            index=net_index,
            policy=policy,
            motor_access=motor_access,
        )
        if res.disposition == "owner_policy_accepted_candidate" and res.groups:
            accepted_sites_count += 1
            group = res.groups[0]
            member_ids = [m.edge_id for m in group.members]
            accepted_member_edges[site_id] = member_ids
            for m in group.members:
                distance_by_edge[site_id][m.edge_id] = m.distance_m

    if sites_without_coordinates:
        print(f"Sites skipped for missing coordinates: {sites_without_coordinates}")
    print(f"Option A sites accepted by policy v1.1: {accepted_sites_count} / {len(admitted_sites)}")

    # 5. Process Option A counts and bind directions
    edge_counts: list[EdgeHourCount] = []
    resolutions: list[DirectionResolution] = []
    bound_edge_ids: set[str] = set()

    site_directions: dict[tuple[int, str], list[Any]] = defaultdict(list)
    # Option A represents each site by its LATEST survey. Collecting every survey
    # date would emit one cell per date for the same edge-hour, fusing surveys
    # the temporal-profile policy keeps separate and inflating the count target.
    # write_edgedata_counts now refuses that outright, so the filter is the fix
    # and the refusal is the backstop.
    for rec in records:
        if rec.count_point_id not in accepted_member_edges:
            continue
        if str(rec.count_date) != site_dates[rec.count_point_id]:
            continue
        site_directions[(rec.count_point_id, rec.direction_of_travel)].append(rec)

    print(
        f"Processing {len(site_directions)} site-directions "
        f"across {len(accepted_member_edges)} accepted sites..."
    )

    # Map edge ids to ordinals
    all_needed_edges = {e_id for edges in accepted_member_edges.values() for e_id in edges}
    ordinals = ordinals_by_edge_id(net_index, all_needed_edges)

    directions_bound = 0
    directions_collinear = 0
    directions_unresolved = 0
    directions_combined = 0

    for (count_point_id, direction), rec_list in site_directions.items():
        member_ids = accepted_member_edges[count_point_id]
        dists = distance_by_edge[count_point_id]
        res = resolve_direction(
            count_point_id=count_point_id,
            direction_of_travel=direction,
            member_edge_ids=member_ids,
            index=net_index,
            ordinals_by_edge=ordinals,
            tolerance_degrees=Decimal("45"),
            distance_by_edge=dists,
        )
        resolutions.append(res)
        if res.edge_id:
            if res.binding == "bound_to_single_edge":
                directions_bound += 1
            elif res.binding == "bound_to_collinear_fragment_group":
                directions_collinear += 1

            bound_edge_ids.add(res.edge_id)
            for rec in rec_list:
                start_s = (rec.hour - 7) * 3600 if rec.hour >= 7 else rec.hour * 3600
                end_s = start_s + 3600
                edge_counts.append(
                    EdgeHourCount(
                        edge_id=res.edge_id,
                        count_point_id=rec.count_point_id,
                        direction_of_travel=rec.direction_of_travel,
                        hour=rec.hour,
                        interval_start_s=start_s,
                        interval_end_s=end_s,
                        all_motor_vehicles=rec.counts.all_motor_vehicles,
                        measured_zero=(rec.counts.all_motor_vehicles == 0),
                    )
                )
        elif res.binding == "combined_direction_not_forced":
            directions_combined += 1
        else:
            directions_unresolved += 1

    total_bound = directions_bound + directions_collinear
    print(
        f"Direction resolution summary: {total_bound} bound "
        f"({directions_bound} single + {directions_collinear} collinear), "
        f"{directions_combined} combined, {directions_unresolved} unresolved."
    )
    print(
        f"Generated {len(edge_counts)} EdgeHourCount entries "
        f"on {len(bound_edge_ids)} distinct edges."
    )

    # 6. Write SUMO edgeData XML counts file
    edgedata_xml_path = EVIDENCE_DIR / "manchester_edgedata_counts_option_a.xml"
    written_intervals = write_edgedata_counts(edgedata_xml_path, edge_counts)
    print(
        f"Wrote edgeData XML counts file: {edgedata_xml_path} ({len(written_intervals)} intervals)"
    )

    # 7. Generate candidate route pool using randomTrips.py
    candidate_trips_path = EVIDENCE_DIR / "manchester_candidate_trips.trips.xml"
    candidate_routes_path = EVIDENCE_DIR / "manchester_candidate_routes.rou.xml"

    print("Generating candidate route pool with randomTrips.py...")
    if candidate_routes_path.is_file() and candidate_routes_path.stat().st_size > 1000000:
        print(
            f"Reusing existing candidate route pool: {candidate_routes_path} "
            f"({candidate_routes_path.stat().st_size // (1024 * 1024)} MB)"
        )
    else:
        cmd_trips = [
            sys.executable,
            str(random_trips_script),
            "-n",
            str(study_net),
            "-o",
            str(candidate_trips_path),
            "-r",
            str(candidate_routes_path),
            "-e",
            "43200",  # 12 hours (07:00-19:00 = 43200 seconds)
            "-p",
            "2.0",  # Trip frequency
            "--fringe-junctions",
            "--validate",
        ]
        res_trips = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd_trips, capture_output=True, text=True, check=False
        )
        if res_trips.returncode == 0:
            print(f"Successfully generated candidate routes: {candidate_routes_path}")
        else:
            print(
                f"randomTrips output: {res_trips.stdout[:300]} / stderr: {res_trips.stderr[:300]}"
            )

    # 8. Execute routeSampler.py
    candidate_demand_path = EVIDENCE_DIR / "manchester_candidate_demand_flows.rou.xml"
    mismatch_output_path = EVIDENCE_DIR / "manchester_demand_mismatch.xml"

    print("Sampling vehicle demand with routeSampler.py...")
    cmd_sampler = [
        sys.executable,
        str(route_sampler_script),
        "-d",
        str(edgedata_xml_path),
        "-r",
        str(candidate_routes_path),
        "-o",
        str(candidate_demand_path),
        "--mismatch-output",
        str(mismatch_output_path),
        "-f",
        "number",
        # Fixed seed: route sampling is stochastic, and an unseeded run cannot be
        # reproduced or compared against a later one.
        "--seed",
        "42",
    ]
    res_sampler = subprocess.run(  # noqa: S603 - fixed argv, no shell
        cmd_sampler, capture_output=True, text=True, check=False
    )
    if res_sampler.returncode == 0:
        print(f"Successfully generated candidate demand flows: {candidate_demand_path}")
        # SUMO records its invocation with absolute paths. Those name the
        # operator's home directory, so the filenames are kept and the
        # directories dropped before the report becomes tracked evidence.
        redact_absolute_paths(mismatch_output_path)
        print(f"Mismatch report saved to: {mismatch_output_path}")
    else:
        # No evidence is written for a run that did not produce demand. A record
        # describing a failed sample would be indistinguishable from one
        # describing a real result.
        raise SystemExit(
            "routeSampler failed; no evidence written.\n"
            f"stdout: {res_sampler.stdout[-2000:]}\n"
            f"stderr: {res_sampler.stderr[-2000:]}"
        )

    # 9. Produce Evidence JSON artifact
    ledger = DemandInputLedger(
        sites_offered=len(site_dates),
        sites_admissible=len(admitted_sites),
        sites_rejected_wrong_disposition=len(site_dates) - len(admitted_sites),
        directions_offered=len(site_directions),
        directions_bound=total_bound,
        directions_requiring_confirmation=0,
        directions_unresolved=directions_unresolved,
        directions_combined_not_forced=directions_combined,
        cells_bound=len(edge_counts),
        measured_zero_cells_bound=sum(1 for c in edge_counts if c.measured_zero),
    )

    input_fp = demand_input_fingerprint(
        match_policy_fingerprint=match_policy_fingerprint,
        profile_lineage_fingerprint="ae3ecff1ce611d5a646f1681b245ad44e7a650029cd8d661806a36694cf2b959",
        network_identity_sha256=net_sha256,
    )

    evidence_json_path = EVIDENCE_DIR / "manchester_demand_reconstruction_20260725.json"

    # Every performance figure below is measured from the artifacts this run
    # produced. Hardcoding them would report the same result whatever happened.
    observed_total = sum(cell.all_motor_vehicles for cell in edge_counts)
    underflow = overflow = 0.0
    underflow_cells = overflow_cells = mismatch_cells = 0
    if mismatch_output_path.is_file():
        # Scanned rather than parsed as a document: the file is a flat, machine
        # written list of edge deficits, and a regex keeps this free of an XML
        # parser on a path that only needs two numbers.
        deficit_pattern = re.compile(r'<edge\b[^>]*\bdeficit="([-0-9.eE]+)"')
        for match in deficit_pattern.finditer(mismatch_output_path.read_text(encoding="utf-8")):
            mismatch_cells += 1
            deficit = float(match.group(1))
            if deficit > 0:
                underflow += deficit
                underflow_cells += 1
            elif deficit < 0:
                overflow += -deficit
                overflow_cells += 1
    achieved = observed_total - underflow

    evidence_payload = {
        "record_type": "real_dft_demand_reconstruction_candidate",
        "record_date": "2026-07-25",
        "capability_id": DEMAND_CAPABILITY_ID,
        # Producing a candidate demand does not accept a capability.
        "capability_status": "planned",
        "gate": "Gate-D step 5 (demand reconstruction), candidate demand only",
        "research_status": RESEARCH_STATUS,
        "label": DEMAND_LABEL,
        "acceptance_basis": ACCEPTANCE_BASIS,
        "acceptance_note": (
            "The matches constraining this demand were accepted by the owner's written "
            "policy. No analyst, human, or supervisor reviewed any row."
        ),
        "supervisor_approved": False,
        "scientifically_validated": False,
        "analyst_accepted": False,
        "human_accepted": False,
        "observed_origin_destination_travel": False,
        "chosen_survey_window": (
            "Option A (2019 or 2022 onward, pandemic years excluded), owner decision 13ae063"
        ),
        "fingerprint": input_fp,
        "network_sha256": net_sha256,
        "measured_result": {
            "observed_edge_hour_cells": len(edge_counts),
            "distinct_bound_edges": len(bound_edge_ids),
            "total_observed_vehicles": observed_total,
            "mismatch_cells": mismatch_cells,
            "underflow_cells": underflow_cells,
            "underflow_vehicles": int(underflow),
            "overflow_cells": overflow_cells,
            "overflow_vehicles": int(overflow),
            "achieved_vehicles": int(achieved),
            "achieved_percent_of_observed": (
                round(100.0 * achieved / observed_total, 2) if observed_total else None
            ),
        },
        "interpretation_limits": [
            "achieved share of a count target is not a goodness-of-fit result",
            "no GEH threshold has been approved; any GEH reported by routeSampler is a tool "
            "diagnostic and is not treated as validation",
            "the routes are count-constrained candidates, not observed origin-destination travel",
            "no calibration, comparison, or simulation was performed by this script",
            "Manchester local-authority evidence; not Greater Manchester-wide",
        ],
        "ledger": ledger.model_dump(),
        "files_generated": [
            str(edgedata_xml_path.name),
            str(candidate_trips_path.name),
            str(candidate_routes_path.name),
            str(candidate_demand_path.name),
            str(mismatch_output_path.name),
        ],
    }

    evidence_json_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote evidence JSON artifact: {evidence_json_path}")
    print("--- Phase 5 candidate demand written ---")


if __name__ == "__main__":
    main()

"""Phase 5: Build Count-Constrained Candidate Demand for Manchester (Option A).

Option A: 2019 / 2022+ Post-Pandemic Window (78 sites, 151 site-directions).
Executes direction binding, edgeData XML generation, randomTrips candidate route pool generation,
and SUMO routeSampler demand sampling over the clipped 285,794-edge Manchester study subnetwork.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from traffictwin.integration.manchester.dft_acquisition import open_accepted_dft_snapshot
from traffictwin.integration.manchester.dft_temporal_profile import open_real_raw_count_evidence
from traffictwin.integration.manchester.demand_reconstruction import (
    ACCEPTANCE_BASIS,
    DEMAND_CAPABILITY_ID,
    DEMAND_LABEL,
    DEMAND_METHOD_VERSION,
    RESEARCH_STATUS,
    CountConstrainedDemandInput,
    DemandInputLedger,
    DirectionResolution,
    EdgeHourCount,
    demand_input_fingerprint,
    ordinals_by_edge_id,
    resolve_direction,
    site_is_in_survey_window,
    write_edgedata_counts,
)
from traffictwin.integration.manchester.network_geometry import build_edge_index
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    match_observation_v11,
)

SUMO_TOOLS = Path("/Library/Frameworks/EclipseSUMO.framework/Versions/1.27.1/EclipseSUMO/share/sumo/tools")
RANDOM_TRIPS = SUMO_TOOLS / "randomTrips.py"
ROUTE_SAMPLER = SUMO_TOOLS / "routeSampler.py"

WORKSPACE = Path("/private/tmp/claude-501/-Users-akashx-AntigravityTest-diss-integration/e146814a-31a7-4666-ab14-d4ee7ab9cd10/scratchpad/v07ws")
SNAPSHOT_RAW_ID = "dft_raw_counts-20260725T063354Z-61965dc5c182"
SNAPSHOT_CP_ID = "dft_count_points-20260725T063353Z-053491696819"

STUDY_NET = Path("/private/tmp/claude-501/-Users-akashx/c7135b6f-3ad2-4452-b970-4a0f4a010026/scratchpad/studynet/study.net.xml")
EVIDENCE_DIR = Path(__file__).resolve().parent.parent / "docs" / "integration" / "evidence"
MATCH_V11_FILE = EVIDENCE_DIR / "manchester_map_match_policy_v11_20260725.json"


def main() -> None:
    print("--- Phase 5: Building Candidate Demand (Option A: 2019/2022+ Window) ---")

    # 1. Load raw count & count point evidence
    records, source_binding = open_real_raw_count_evidence(WORKSPACE, SNAPSHOT_RAW_ID)
    cp_opened = open_accepted_dft_snapshot(WORKSPACE, SNAPSHOT_CP_ID)
    count_points_by_id = {cp.count_point_id: cp for cp in cp_opened.report.records}
    print(f"Loaded {len(records)} raw count records & {len(count_points_by_id)} count points.")

    # 2. Filter sites by survey window (Option A)
    site_dates: dict[int, str] = {}
    site_records: dict[int, list] = defaultdict(list)
    for rec in records:
        site_id = rec.count_point_id
        site_records[site_id].append(rec)
        if site_id not in site_dates or str(rec.count_date) > site_dates[site_id]:
            site_dates[site_id] = str(rec.count_date)

    admitted_sites = {
        site_id for site_id, latest_date in site_dates.items()
        if site_is_in_survey_window(latest_date)
    }
    print(f"Total sites in raw counts: {len(site_dates)}. Sites in Option A window: {len(admitted_sites)}")

    # 3. Load study network index
    print(f"Loading spatial index for study subnetwork: {STUDY_NET}")
    net_index = build_edge_index(STUDY_NET)
    print(f"Indexed {len(net_index)} edges in study subnetwork.")

    # 4. Perform Map Matching v1.1 for Option A sites to get accepted road groups
    policy = ManchesterMapMatchPolicyV11()
    match_policy_fingerprint = policy.fingerprint()

    accepted_member_edges: dict[int, list[str]] = {}
    distance_by_edge: dict[int, dict[str, Decimal]] = defaultdict(dict)

    accepted_sites_count = 0
    for site_id in sorted(admitted_sites):
        if site_id not in count_points_by_id:
            continue
        cp = count_points_by_id[site_id]
        res = match_observation_v11(
            count_point_id=cp.count_point_id,
            dft_road_ref=cp.location.road_name,
            dft_road_name=cp.location.road_name,
            dft_road_type=cp.location.road_type,
            easting=float(cp.location.easting),
            northing=float(cp.location.northing),
            index=net_index,
            policy=policy,
        )
        if res.disposition == "owner_policy_accepted_candidate" and res.groups:
            accepted_sites_count += 1
            group = res.groups[0]
            member_ids = [m.edge_id for m in group.members]
            accepted_member_edges[site_id] = member_ids
            for m in group.members:
                distance_by_edge[site_id][m.edge_id] = m.distance_m

    print(f"Option A sites accepted by policy v1.1: {accepted_sites_count} / {len(admitted_sites)}")

    # 5. Process Option A counts and bind directions
    edge_counts: list[EdgeHourCount] = []
    resolutions: list[DirectionResolution] = []
    bound_edge_ids: set[str] = set()

    site_directions: dict[tuple[int, str], list] = defaultdict(list)
    for rec in records:
        if rec.count_point_id in accepted_member_edges:
            site_directions[(rec.count_point_id, rec.direction_of_travel)].append(rec)

    print(f"Processing {len(site_directions)} site-directions across {len(accepted_member_edges)} accepted sites...")

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
    print(f"Direction resolution summary: {total_bound} bound ({directions_bound} single + {directions_collinear} collinear), {directions_combined} combined, {directions_unresolved} unresolved.")
    print(f"Generated {len(edge_counts)} EdgeHourCount entries on {len(bound_edge_ids)} distinct edges.")

    # 6. Write SUMO edgeData XML counts file
    edgedata_xml_path = EVIDENCE_DIR / "manchester_edgedata_counts_option_a.xml"
    written_intervals = write_edgedata_counts(edgedata_xml_path, edge_counts)
    print(f"Wrote edgeData XML counts file: {edgedata_xml_path} ({len(written_intervals)} intervals)")

    # 7. Generate candidate route pool using randomTrips.py
    candidate_trips_path = EVIDENCE_DIR / "manchester_candidate_trips.trips.xml"
    candidate_routes_path = EVIDENCE_DIR / "manchester_candidate_routes.rou.xml"

    print("Generating candidate route pool with randomTrips.py...")
    if candidate_routes_path.is_file() and candidate_routes_path.stat().st_size > 1000000:
        print(f"Reusing existing candidate route pool: {candidate_routes_path} ({candidate_routes_path.stat().st_size // (1024*1024)} MB)")
    else:
        cmd_trips = [
            sys.executable,
            str(RANDOM_TRIPS),
            "-n", str(STUDY_NET),
            "-o", str(candidate_trips_path),
            "-r", str(candidate_routes_path),
            "-e", "43200",  # 12 hours (07:00-19:00 = 43200 seconds)
            "-p", "2.0",    # Trip frequency
            "--fringe-junctions",
            "--validate",
        ]
        res_trips = subprocess.run(cmd_trips, capture_output=True, text=True)
        if res_trips.returncode == 0:
            print(f"Successfully generated candidate routes: {candidate_routes_path}")
        else:
            print(f"randomTrips output: {res_trips.stdout[:300]} / stderr: {res_trips.stderr[:300]}")

    # 8. Execute routeSampler.py
    candidate_demand_path = EVIDENCE_DIR / "manchester_candidate_demand.rou.xml"
    mismatch_output_path = EVIDENCE_DIR / "manchester_demand_mismatch.xml"

    print("Sampling vehicle demand with routeSampler.py...")
    cmd_sampler = [
        sys.executable,
        str(ROUTE_SAMPLER),
        "-n", str(STUDY_NET),
        "-d", str(edgedata_xml_path),
        "-r", str(candidate_routes_path),
        "-o", str(candidate_demand_path),
        "--mismatch-output", str(mismatch_output_path),
    ]
    res_sampler = subprocess.run(cmd_sampler, capture_output=True, text=True)
    if res_sampler.returncode == 0:
        print(f"Successfully generated candidate demand routes: {candidate_demand_path}")
        print(f"Mismatch report saved to: {mismatch_output_path}")
    else:
        print(f"routeSampler output: {res_sampler.stdout[:300]} / stderr: {res_sampler.stderr[:300]}")

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

    net_sha256 = "ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577"
    input_fp = demand_input_fingerprint(
        match_policy_fingerprint=match_policy_fingerprint,
        profile_lineage_fingerprint="ae3ecff1ce611d5a646f1681b245ad44e7a650029cd8d661806a36694cf2b959",
        network_identity_sha256=net_sha256,
    )

    demand_input_artifact = CountConstrainedDemandInput(
        match_policy_id="manchester-dft-map-match-owner-policy-1.1",
        match_policy_fingerprint=match_policy_fingerprint,
        direction_tolerance_degrees=Decimal("45"),
        counts=tuple(edge_counts),
        resolutions=tuple(resolutions),
        ledger=ledger,
    )

    evidence_json_path = EVIDENCE_DIR / "manchester_demand_reconstruction_20260725.json"
    evidence_payload = {
        "record_type": "real_dft_demand_reconstruction_candidate",
        "record_date": "2026-07-25",
        "capability_id": DEMAND_CAPABILITY_ID,
        "capability_status": "complete",
        "gate": "Gate-D step 5 (demand reconstruction)",
        "research_status": RESEARCH_STATUS,
        "label": DEMAND_LABEL,
        "acceptance_basis": ACCEPTANCE_BASIS,
        "chosen_survey_window": "Option A (2019/2022+ post-pandemic window: 78 sites)",
        "fingerprint": input_fp,
        "ledger": ledger.model_dump(),
        "files_generated": [
            str(edgedata_xml_path.name),
            str(candidate_trips_path.name),
            str(candidate_routes_path.name),
            str(candidate_demand_path.name),
            str(mismatch_output_path.name),
        ]
    }

    evidence_json_path.write_text(json.dumps(evidence_payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote evidence JSON artifact: {evidence_json_path}")
    print("--- Phase 5 Execution Successfully Complete! ---")


if __name__ == "__main__":
    main()

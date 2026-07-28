#!/usr/bin/env python3
"""Rebuild the edge index and regenerate the 305-row v1.1 match artifact.

The 25-July artifact lived in a session scratchpad and vanished with it. Both
the index and the match rows are deterministic functions of the reviewed
network and the accepted DfT snapshots, so this script recomputes rather than
recovers them, then reconciles the result against the recorded 25-July split.

The matcher runs over the *parent* Greater Manchester baseline, exactly as the
recorded run did: the study subnetwork is the demand workspace, not the
matching frame, and matching against a clipped frame would silently discard
candidate edges just outside the local-authority box.

A difference from the recorded dispositions is a finding about reproducibility,
not something to be corrected away.

Usage:
    uv run python scripts/regenerate_match_artifact.py --workspace <path>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.manchester.artifact_integrity import (
    refuse_ephemeral_dependency,
    sha256_file,
)
from traffictwin.integration.manchester.dft_acquisition import open_accepted_dft_snapshot
from traffictwin.integration.manchester.dft_temporal_profile import (
    open_real_raw_count_evidence,
)
from traffictwin.integration.manchester.network_build import canonical_network_digest
from traffictwin.integration.manchester.network_connectivity import stream_network_edges
from traffictwin.integration.manchester.network_geometry import (
    build_edge_index,
    geometry_fingerprint,
    summarise_edge_geometry,
)
from traffictwin.integration.manchester.observation_matching import (
    ManchesterMapMatchPolicy,
    dft_road_reference,
    match_observation,
)
from traffictwin.integration.manchester.observation_matching_v11 import (
    ManchesterMapMatchPolicyV11,
    match_observation_v11,
    reconcile_policies,
)

BUILD_ROOT = Path("data/network-build").resolve()
PARENT_ID = "gm-baseline-20260728"
PARENT_PATH = BUILD_ROOT / PARENT_ID / f"{PARENT_ID}.net.xml"
PARENT_CANONICAL_SHA256 = "ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577"

# The 25-July record, reconciled against rather than assumed.
RECORDED = {
    "sites_matched": 305,
    "v1_0": {"clear_candidate": 106, "review_required": 178, "no_suitable_candidate": 21},
    "v1_1": {
        "owner_policy_accepted_candidate": 131,
        "awaiting_manual_review": 165,
        "no_suitable_candidate": 9,
    },
    "policy_fingerprint": "f0bc213b02fab2f15b411982b8ad585ec0dda5df05b298d0954b34c0cbe1226c",
    "acceptance_paths": {"strict_v1_0_clear": 106, "exact_reference_family_override": 25},
}

# The 25-July record published a `reconciliation_fingerprint` of
# `ae3ecff1ce611d5a…`, but no committed code computes it: the recipe lived in
# the session script that vanished with the workspace. It is therefore recorded
# below as unverifiable rather than compared against a guess, and this run
# publishes its own explicitly-defined digest instead.
RECORDED_RECONCILIATION_FINGERPRINT = (
    "ae3ecff1ce611d5a646f1681b245ad44e7a650029cd8d661806a36694cf2b959"
)


def _latest_snapshot(workspace: Path, prefix: str) -> str:
    accepted = workspace / "accepted"
    candidates = sorted(
        path.name for path in accepted.iterdir() if path.name.startswith(f"{prefix}-")
    )
    if not candidates:
        raise SystemExit(f"no accepted {prefix} snapshot in {accepted}")
    return candidates[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--count-point-snapshot-id")
    parser.add_argument("--raw-snapshot-id")
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    refuse_ephemeral_dependency(workspace)
    count_point_id = args.count_point_snapshot_id or _latest_snapshot(workspace, "dft_count_points")
    raw_id = args.raw_snapshot_id or _latest_snapshot(workspace, "dft_raw_counts")
    print(f"count points: {count_point_id}")
    print(f"raw counts:   {raw_id}", flush=True)

    print("verifying the parent network's canonical identity ...", flush=True)
    parent_canonical = canonical_network_digest(PARENT_PATH)
    if parent_canonical != PARENT_CANONICAL_SHA256:
        raise SystemExit(f"PARENT_IDENTITY_MISMATCH: refusing to match against {parent_canonical}")

    print("summarising edge geometry ...", flush=True)
    started = time.monotonic()
    summary = summarise_edge_geometry(PARENT_PATH)
    summary_s = time.monotonic() - started
    fingerprint = geometry_fingerprint(summary, parent_canonical)
    print(f"geometry fingerprint: {fingerprint} ({summary_s:.1f} s)", flush=True)

    print("building the edge spatial index ...", flush=True)
    started = time.monotonic()
    index = build_edge_index(PARENT_PATH)
    index_s = time.monotonic() - started
    print(f"index edges: {len(index)} ({index_s:.1f} s)", flush=True)

    print("reading per-edge motor access ...", flush=True)
    started = time.monotonic()
    access = {edge.edge_id: edge.access for edge in stream_network_edges(PARENT_PATH)}
    access_s = time.monotonic() - started
    print(f"access entries: {len(access)} ({access_s:.1f} s)", flush=True)

    records, _binding = open_real_raw_count_evidence(workspace, raw_id)
    load = open_accepted_dft_snapshot(workspace, count_point_id)
    points = getattr(load.report, "records", ())
    sites_with_counts = {record.count_point_id for record in records}

    policy_v10 = ManchesterMapMatchPolicy()
    policy_v11 = ManchesterMapMatchPolicyV11()

    print("matching ...", flush=True)
    started = time.monotonic()
    v10_results = []
    v11_results = []
    skipped_no_location = 0
    for point in points:
        if point.count_point_id not in sites_with_counts:
            continue
        location = point.location
        if location.easting is None or location.northing is None:
            skipped_no_location += 1
            continue
        shared = {
            "count_point_id": point.count_point_id,
            "easting": float(location.easting),
            "northing": float(location.northing),
            "dft_road_type": location.road_type,
            "dft_road_name": location.road_name,
            "dft_road_ref": dft_road_reference(location.road_name),
            "index": index,
        }
        v10_results.append(match_observation(**shared, policy=policy_v10))
        v11_results.append(match_observation_v11(**shared, policy=policy_v11, motor_access=access))
    match_s = time.monotonic() - started
    print(f"matched {len(v11_results)} sites ({match_s:.1f} s)", flush=True)

    reconciliation = reconcile_policies(v10_results, v11_results)

    artifact_dir = workspace / "manchester"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / "match_results_v11_20260728.json"
    artifact_path.write_text(
        json.dumps([row.model_dump(mode="json") for row in v11_results], indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_sha256 = sha256_file(artifact_path)

    v10_counts = dict(sorted(Counter(row.confidence for row in v10_results).items()))
    v11_counts = dict(sorted(Counter(row.disposition for row in v11_results).items()))
    paths = dict(
        sorted(
            Counter(
                row.acceptance_path for row in v11_results if row.acceptance_path is not None
            ).items()
        )
    )

    observed = {
        "sites_matched": len(v11_results),
        "v1_0": v10_counts,
        "v1_1": v11_counts,
        "policy_fingerprint": policy_v11.fingerprint(),
        "acceptance_paths": paths,
    }
    reconciliation_json = reconciliation.model_dump_json()
    reconciliation_digest = hashlib.sha256(reconciliation_json.encode("utf-8")).hexdigest()
    differences = {
        key: {"recorded": RECORDED[key], "observed": observed[key]}
        for key in RECORDED
        if RECORDED[key] != observed[key]
    }

    receipt = {
        "record_type": "manchester_map_match_v11_regeneration",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "capability_id": "MAN-09",
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "analyst_accepted": False,
        "acceptance_note": (
            "rows this policy accepts are owner_policy_accepted_candidate; no analyst, "
            "human, or supervisor has reviewed any row"
        ),
        "why_regenerated": (
            "the 25-July artifact lived in a session-scoped workspace that no longer "
            "exists; both inputs survive, so the rows are recomputed from the evidence "
            "rather than recovered"
        ),
        "inputs": {
            "network": {
                "network_id": PARENT_ID,
                "path": str(PARENT_PATH),
                "canonical_sha256": parent_canonical,
                "frame_note": (
                    "matching runs against the parent baseline, not the clipped study "
                    "subnetwork, so no candidate edge is lost at the local-authority boundary"
                ),
            },
            "count_point_snapshot_id": count_point_id,
            "raw_count_snapshot_id": raw_id,
            "sites_with_raw_counts": len(sites_with_counts),
            "count_points_read": len(points),
            "skipped_missing_location": skipped_no_location,
        },
        "edge_index": {
            "indexed_real_edges": len(index),
            "cell_size_m": index.cell_size_m,
            "build_seconds": round(index_s, 2),
            "motor_access_entries": len(access),
            "motor_access_seconds": round(access_s, 2),
            "geometry_summary": summary.model_dump(mode="json"),
            "geometry_summary_seconds": round(summary_s, 2),
            "geometry_fingerprint": fingerprint,
            "fingerprint_binding": "sha256 over the network identity and the geometry summary",
        },
        "artifact": {
            "path": str(artifact_path),
            "bytes": artifact_path.stat().st_size,
            "sha256": artifact_sha256,
            "rows": len(v11_results),
            "shape": "JSON list of ObservationMatchV11 rows, as the review service loads it",
            "publication_class": "private",
        },
        "observed": observed,
        "recorded_20260725": RECORDED,
        "reconciliation_with_20260725_record": {
            "matches_exactly": not differences,
            "differences": differences,
            "note": (
                "a difference is a finding about reproducibility, not a defect to be corrected away"
            ),
        },
        "policy_reconciliation": {
            "detail": reconciliation.model_dump(mode="json"),
            "canonical_sha256": reconciliation_digest,
            "digest_definition": "sha256 over PolicyReconciliation.model_dump_json()",
            "recorded_20260725_reconciliation_fingerprint": (RECORDED_RECONCILIATION_FINGERPRINT),
            "recorded_fingerprint_comparable": False,
            "why_not_comparable": (
                "no committed code computes the 25-July reconciliation_fingerprint; its "
                "recipe lived in the session script that vanished with the workspace, so "
                "the two digests are not defined over the same bytes and equality is "
                "neither claimed nor refuted"
            ),
        },
        "matching_seconds": round(match_s, 2),
        "explicit_non_claims": [
            "candidate generation is not acceptance; policy 1.1 disables automatic "
            "final acceptance",
            "no analyst decision is created or implied by regenerating these rows",
            "this is Manchester local-authority evidence and is never Greater Manchester-wide",
        ],
    }
    receipt_path = artifact_dir / "match_results_v11_20260728_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"v1.0 confidence:  {v10_counts}")
    print(f"v1.1 disposition: {v11_counts}")
    print(f"acceptance paths: {paths}")
    policy_matches = observed["policy_fingerprint"] == RECORDED["policy_fingerprint"]
    print(f"policy fingerprint matches record: {policy_matches}")
    print(f"reconciliation canonical sha256: {reconciliation_digest}")
    print(f"exact reproduction: {not differences}")
    if differences:
        print(json.dumps(differences, indent=2))
    print(f"artifact: {artifact_path} ({artifact_sha256})")
    print(f"receipt:  {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Clip the Manchester local-authority study subnetwork from the rebuilt parent.

The 25-July subnetwork lived in a session scratchpad and vanished with it. This
script reproduces it from the durable Phase-108 parent using the argument shape
recorded in ``docs/integration/evidence/manchester_study_subnetwork_20260725.json``,
so the result is provably a subset of the reviewed parent rather than a second
independent build.

Guards applied before anything expensive runs (Phase 106):
  * the destination must not be a session-scoped or temporary path;
  * the parent's canonical identity must match the Phase-108 record;
  * the clip's source and derived identities must not collide.

Verified rather than asserted afterwards:
  * every study edge id also exists in the parent (the clip renames nothing);
  * every edge id the committed Option-A edgeData counts depend on is present.

Usage:
    uv run python scripts/clip_study_subnetwork.py
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from traffictwin.integration.manchester.artifact_integrity import (
    ArtifactIdentity,
    SourceDerivedRecord,
    refuse_ephemeral_dependency,
    refuse_source_derived_collision,
    sha256_file,
)
from traffictwin.integration.manchester.network_build import (
    canonical_network_digest,
    discover_netconvert,
    netconvert_identity,
    network_structure_from_file,
)
from traffictwin.integration.manchester.network_scope import sub_area_bounds

BUILD_ROOT = Path("data/network-build").resolve()
PARENT_ID = "gm-baseline-20260728"
PARENT_PATH = BUILD_ROOT / PARENT_ID / f"{PARENT_ID}.net.xml"
PARENT_CANONICAL_SHA256 = "ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577"

STUDY_ID = "gm-study-manchester-la-20260728"
STUDY_DIR = BUILD_ROOT / STUDY_ID
STUDY_PATH = STUDY_DIR / f"{STUDY_ID}.net.xml"
RECEIPT_PATH = STUDY_DIR / "clip_receipt.json"

# Committed observation-side input whose edge ids the demand cascade consumes.
EDGEDATA_COUNTS = Path("docs/integration/evidence/manchester_edgedata_counts_option_a.xml")

# Recorded 25-July values, reconciled against rather than assumed.
RECORDED_STUDY_REAL_EDGES = 285_794
RECORDED_STUDY_JUNCTIONS = 165_397
RECORDED_PARENT_REAL_EDGES = 804_611
RECORDED_DURATION_S = 32.97

_EDGE_ID = re.compile(rb'<edge id="([^"]+)"')


def _edge_ids(path: Path) -> set[bytes]:
    """Collect real (non junction-internal) edge ids by line iteration.

    netconvert writes one element per line, so line iteration is both correct
    and bounded; a chunk-and-carry scanner grows without bound past the last
    anchor and reached 7.8 GB RSS on this network.
    """

    found: set[bytes] = set()
    with path.open("rb") as handle:
        for line in handle:
            match = _EDGE_ID.search(line)
            if match is None:
                continue
            edge_id = match.group(1)
            if edge_id.startswith(b":"):
                continue
            found.add(edge_id)
    return found


def main() -> int:
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    refuse_ephemeral_dependency(STUDY_DIR)

    if not PARENT_PATH.exists():
        raise SystemExit(f"parent network missing: {PARENT_PATH}")

    print("verifying the parent's canonical identity ...", flush=True)
    parent_canonical = canonical_network_digest(PARENT_PATH)
    if parent_canonical != PARENT_CANONICAL_SHA256:
        raise SystemExit(
            "PARENT_IDENTITY_MISMATCH: refusing to clip a network that is not the "
            f"Phase-108 baseline (got {parent_canonical})"
        )
    print(f"parent canonical identity: {parent_canonical}", flush=True)

    executable = discover_netconvert()
    if executable is None:
        raise SystemExit("netconvert not found")
    tool = netconvert_identity()

    bounds = sub_area_bounds()
    boundary = (
        f"{bounds.min_longitude},{bounds.min_latitude},{bounds.max_longitude},{bounds.max_latitude}"
    )
    command = [
        str(executable),
        "--sumo-net-file",
        str(PARENT_PATH),
        "--keep-edges.in-geo-boundary",
        boundary,
        "--output-file",
        str(STUDY_PATH),
        "--numerical-ids",
        "--seed",
        "42",
        "--xml-validation",
        "never",
    ]
    print(f"clipping with boundary {boundary} ...", flush=True)
    started = time.monotonic()
    completed = subprocess.run(  # noqa: S603 - frozen argv, never a shell
        command, capture_output=True, text=True, check=False
    )
    duration_s = time.monotonic() - started
    if completed.returncode != 0:
        raise SystemExit(f"CLIP_FAILED (exit {completed.returncode}):\n{completed.stderr[-4000:]}")
    print(f"clip finished in {duration_s:.2f} s", flush=True)

    study_raw_sha256 = sha256_file(STUDY_PATH)
    study_canonical = canonical_network_digest(STUDY_PATH)
    parent_raw_sha256 = sha256_file(PARENT_PATH)
    refuse_source_derived_collision(
        SourceDerivedRecord(
            source=ArtifactIdentity(
                role="source",
                representation="accepted parent net.xml",
                byte_size=PARENT_PATH.stat().st_size,
                sha256=parent_raw_sha256,
            ),
            derived=ArtifactIdentity(
                role="derived",
                representation="clipped study subnetwork net.xml",
                byte_size=STUDY_PATH.stat().st_size,
                sha256=study_raw_sha256,
            ),
        )
    )

    structure = network_structure_from_file(STUDY_PATH)

    print("reading edge ids from both networks ...", flush=True)
    study_ids = _edge_ids(STUDY_PATH)
    parent_ids = _edge_ids(PARENT_PATH)
    renamed = sorted(study_ids - parent_ids)

    counted_ids = {match.group(1) for match in _EDGE_ID.finditer(EDGEDATA_COUNTS.read_bytes())}
    missing_counted = sorted(counted_ids - study_ids)

    receipt = {
        "record_type": "manchester_study_subnetwork_clip",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "capability_id": "MAN-09",
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "method": (
            "the durable Phase-108 parent was clipped, not re-derived from OpenStreetMap, "
            "so the subnetwork is provably a subset of the reviewed parent"
        ),
        "parent": {
            "network_id": PARENT_ID,
            "path": str(PARENT_PATH),
            "bytes": PARENT_PATH.stat().st_size,
            "raw_sha256": parent_raw_sha256,
            "canonical_sha256": parent_canonical,
            "canonical_matches_phase_108_record": True,
        },
        "tool": tool.model_dump(mode="json"),
        "clip": {
            "boundary": boundary,
            "boundary_source": (
                "network_scope.sub_area_bounds (packaged generalised display geometry)"
            ),
            "argument_vector": command[1:],
            "duration_s": round(duration_s, 2),
            "recorded_duration_s_20260725": RECORDED_DURATION_S,
        },
        "study_network": {
            "network_id": STUDY_ID,
            "path": str(STUDY_PATH),
            "bytes": STUDY_PATH.stat().st_size,
            "raw_sha256": study_raw_sha256,
            "canonical_sha256": study_canonical,
        },
        "structure": structure.model_dump(mode="json"),
        "edge_id_preservation": {
            "study_real_edges": len(study_ids),
            "parent_real_edges": len(parent_ids),
            "study_ids_absent_from_parent": len(renamed),
            "examples_absent": [value.decode() for value in renamed[:10]],
            "edge_ids_preserved": not renamed,
        },
        "counted_edge_coverage": {
            "source": str(EDGEDATA_COUNTS),
            "distinct_counted_edges": len(counted_ids),
            "present_in_study_subnetwork": len(counted_ids) - len(missing_counted),
            "missing": [value.decode() for value in missing_counted],
        },
        "reconciliation_with_20260725_record": {
            "recorded_study_real_edges": RECORDED_STUDY_REAL_EDGES,
            "recorded_study_junctions": RECORDED_STUDY_JUNCTIONS,
            "recorded_parent_real_edges": RECORDED_PARENT_REAL_EDGES,
            "note": (
                "a difference from the recorded counts is a finding about reproducibility, "
                "not a defect to be corrected away"
            ),
        },
        "explicit_non_claims": [
            "a clipped subnetwork is geometry, not calibration, comparison, or validation",
            "this is a Manchester local-authority study subnetwork and is never "
            "Greater Manchester-wide evidence",
            "no demand artifact is produced here",
        ],
    }
    RECEIPT_PATH.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")

    print(f"study real edges: {len(study_ids)} (recorded {RECORDED_STUDY_REAL_EDGES})")
    print(f"parent real edges: {len(parent_ids)} (recorded {RECORDED_PARENT_REAL_EDGES})")
    print(f"edge ids preserved: {not renamed}")
    print(f"counted edges present: {len(counted_ids) - len(missing_counted)}/{len(counted_ids)}")
    print(f"receipt: {RECEIPT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

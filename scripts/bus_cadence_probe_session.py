#!/usr/bin/env python3
"""Attended BODS cadence-probe session (bus options decision F1).

Runs one human-attended observation session: N receipted snapshot acquisitions
through the accepted controlled-refresh boundary (>= 60 s apart, one at a
time), then measures per-vehicle update cadence under the owner-approved
session-scoped identity policy (F0) and writes the aggregate-only measurement.

The API key is read from ``BODS_API_KEY`` and never echoed. The session salt
is generated in process and dies with it: linkage exists only inside this
session, and the written measurement contains aggregates only — no tokens, no
raw references, no per-vehicle rows.

Usage (owner attends for the whole session):
    export BODS_API_KEY='...'
    uv run python scripts/bus_cadence_probe_session.py \
        --workspace <v0.7-workspace> --snapshots 15
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
import time
from decimal import Decimal
from pathlib import Path

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_live_control import (
    BodsLiveControlError,
    coordinated_bods_live_refresh,
)
from traffictwin.integration.manchester.bods_session_identity import (
    SessionExtractionResult,
    extract_session_observations,
    measure_session_cadence,
    measurement_to_json,
)

#: The Greater Manchester box recorded in the accepted Bee Network probe.
GREATER_MANCHESTER_BOX = BodsBoundingBox(
    min_longitude=Decimal("-2.7304178"),
    min_latitude=Decimal("53.3273147"),
    max_longitude=Decimal("-1.9096224"),
    max_latitude=Decimal("53.6857188"),
)
_MINIMUM_INTERVAL_SECONDS = 61


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--snapshots", type=int, default=15)
    parser.add_argument("--interval-seconds", type=int, default=65)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="aggregate measurement JSON (default: <workspace>/manchester/"
        "bus_cadence_probe_measurement.json)",
    )
    args = parser.parse_args()
    if args.snapshots < 2 or args.snapshots > 120:
        print("snapshots must be between 2 and 120", file=sys.stderr)
        return 2
    if args.interval_seconds < _MINIMUM_INTERVAL_SECONDS:
        print(
            f"interval must be at least {_MINIMUM_INTERVAL_SECONDS} s; the accepted "
            "boundary enforces 60 s and one second of slack avoids refusals",
            file=sys.stderr,
        )
        return 2
    api_key = os.environ.get("BODS_API_KEY")
    if not api_key:
        print(
            "BODS_API_KEY is not configured in this environment; set it and re-run. "
            "Nothing was acquired.",
            file=sys.stderr,
        )
        return 2

    session_salt = secrets.token_bytes(32)
    snapshot_ids: list[str] = []
    print(
        f"attended session: {args.snapshots} snapshots at >= {args.interval_seconds} s; "
        "stay present until it completes"
    )
    for index in range(args.snapshots):
        try:
            refresh = coordinated_bods_live_refresh(
                args.workspace, GREATER_MANCHESTER_BOX, api_key=api_key
            )
        except BodsLiveControlError as error:
            if error.code == "REFRESH_TOO_SOON":
                print("  interval not yet elapsed; waiting 30 s and retrying once")
                time.sleep(30)
                refresh = coordinated_bods_live_refresh(
                    args.workspace, GREATER_MANCHESTER_BOX, api_key=api_key
                )
            else:
                print(f"session halted at snapshot {index + 1}: {error}", file=sys.stderr)
                break
        summary = refresh.refresh.summary
        snapshot_ids.append(summary.snapshot_id)
        print(
            f"  [{index + 1}/{args.snapshots}] {summary.snapshot_id} "
            f"(accepted={summary.records_accepted}, live={summary.live_vehicle})"
        )
        if index + 1 < args.snapshots:
            time.sleep(args.interval_seconds)

    if len(snapshot_ids) < 2:
        print("fewer than two snapshots acquired; no cadence measurement", file=sys.stderr)
        return 1

    results: list[SessionExtractionResult] = []
    for snapshot_id in snapshot_ids:
        result = extract_session_observations(
            args.workspace, snapshot_id, session_salt=session_salt
        )
        results.append(result)
        print(
            f"  extracted {result.observations_extracted}/{result.activities_seen} "
            f"({result.malformed_skipped} malformed) from {snapshot_id}"
        )
    measurement = measure_session_cadence(results)
    output = args.output or (args.workspace / "manchester" / "bus_cadence_probe_measurement.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(measurement_to_json(measurement) + "\n", encoding="utf-8")
    print("--- aggregate cadence measurement (no identifiers) ---")
    print(measurement_to_json(measurement))
    print(f"written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

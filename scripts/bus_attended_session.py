#!/usr/bin/env python3
"""Attended BODS observation session that survives a single-snapshot refusal.

`bus_cadence_probe_session.py` ends the whole session when the MAN-05 parser
refuses one snapshot. That refusal is correct and stays untouched here — the
rejected feed is never promoted and its bytes stay in quarantine — but on
28 July it ended an attended rush-hour window after two snapshots, and a
90-minute owner-attended window is not reproducible on demand.

This runner keeps the acquisition boundary exactly as accepted (>= 60 s apart,
one at a time, human-triggered, Greater Manchester box) and changes only what
happens *after* a fail-closed refusal: it records the refusal as a data-quality
observation and continues the session instead of discarding the window.

Nothing about the parser, the promotion rule, or the evidence boundary moves.
A refused snapshot is still refused, is still never measured, and is counted
separately from accepted ones so the two can never blur.

The API key is read from ``BODS_API_KEY`` and never echoed. The session salt is
generated in process and dies with it; the measurement written is
aggregate-only — no tokens, no raw references, no per-vehicle rows.

Usage (owner attends for the whole session):
    uv run python scripts/bus_attended_session.py \
        --workspace <v0.7-workspace> --snapshots 85 --label evening_peak
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from traffictwin.integration.manchester.bods import BodsBoundingBox
from traffictwin.integration.manchester.bods_acquisition import BodsAcquisitionError
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
#: Consecutive refusals that end the session. A feed that refuses this many
#: times in a row is not a transient shape problem and the window is over.
_CONSECUTIVE_REFUSAL_LIMIT = 8


def _quarantine_ids(workspace: Path) -> set[str]:
    directory = workspace / "quarantine"
    if not directory.is_dir():
        return set()
    return {path.name for path in directory.iterdir() if path.name.startswith("bods_siri_vm-")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--snapshots", type=int, default=85)
    parser.add_argument("--interval-seconds", type=int, default=65)
    parser.add_argument("--label", required=True, help="session label, e.g. evening_peak")
    parser.add_argument("--output", type=Path, default=None)
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
        print("BODS_API_KEY is not configured; nothing was acquired.", file=sys.stderr)
        return 2

    workspace = args.workspace.expanduser().resolve()
    session_salt = secrets.token_bytes(32)
    snapshot_ids: list[str] = []
    refusals: list[dict[str, object]] = []
    consecutive = 0
    started_at = datetime.now(UTC).isoformat()

    print(
        f"attended session '{args.label}': {args.snapshots} snapshots at "
        f">= {args.interval_seconds} s; stay present until it completes",
        flush=True,
    )

    for index in range(args.snapshots):
        before = _quarantine_ids(workspace)
        attempted_at = datetime.now(UTC).isoformat()
        try:
            refresh = coordinated_bods_live_refresh(
                workspace, GREATER_MANCHESTER_BOX, api_key=api_key
            )
        except BodsLiveControlError as error:
            if error.code == "REFRESH_TOO_SOON":
                print("  interval not yet elapsed; waiting 30 s and retrying once", flush=True)
                time.sleep(30)
                try:
                    refresh = coordinated_bods_live_refresh(
                        workspace, GREATER_MANCHESTER_BOX, api_key=api_key
                    )
                except (BodsLiveControlError, BodsAcquisitionError) as retry_error:
                    consecutive += 1
                    appeared = sorted(_quarantine_ids(workspace) - before)
                    refusals.append(
                        {
                            "attempt": index + 1,
                            "attempted_at_utc": attempted_at,
                            "error": str(retry_error)[:300],
                            "quarantined_but_not_promoted": appeared,
                        }
                    )
                    print(f"  [{index + 1}] refused: {retry_error}", flush=True)
                    if consecutive >= _CONSECUTIVE_REFUSAL_LIMIT:
                        print("  refusal limit reached; ending session", flush=True)
                        break
                    if index + 1 < args.snapshots:
                        time.sleep(args.interval_seconds)
                    continue
            else:
                consecutive += 1
                refusals.append(
                    {
                        "attempt": index + 1,
                        "attempted_at_utc": attempted_at,
                        "error": str(error)[:300],
                        "quarantined_but_not_promoted": sorted(_quarantine_ids(workspace) - before),
                    }
                )
                print(f"  [{index + 1}] refused: {error}", flush=True)
                if consecutive >= _CONSECUTIVE_REFUSAL_LIMIT:
                    print("  refusal limit reached; ending session", flush=True)
                    break
                if index + 1 < args.snapshots:
                    time.sleep(args.interval_seconds)
                continue
        except BodsAcquisitionError as error:
            # A fail-closed parser or validation refusal. The snapshot is not
            # promoted and its bytes stay in quarantine; the session continues.
            consecutive += 1
            appeared = sorted(_quarantine_ids(workspace) - before)
            refusals.append(
                {
                    "attempt": index + 1,
                    "attempted_at_utc": attempted_at,
                    "error": str(error)[:300],
                    "quarantined_but_not_promoted": appeared,
                }
            )
            print(f"  [{index + 1}] refused: {error}", flush=True)
            if consecutive >= _CONSECUTIVE_REFUSAL_LIMIT:
                print("  refusal limit reached; ending session", flush=True)
                break
            if index + 1 < args.snapshots:
                time.sleep(args.interval_seconds)
            continue

        consecutive = 0
        summary = refresh.refresh.summary
        snapshot_ids.append(summary.snapshot_id)
        print(
            f"  [{index + 1}/{args.snapshots}] {summary.snapshot_id} "
            f"(accepted={summary.records_accepted}, live={summary.live_vehicle})",
            flush=True,
        )
        if index + 1 < args.snapshots:
            time.sleep(args.interval_seconds)

    finished_at = datetime.now(UTC).isoformat()
    print(
        f"session complete: {len(snapshot_ids)} accepted, {len(refusals)} refused",
        flush=True,
    )

    output = args.output or (
        workspace / "manchester" / f"bus_session_{args.label}_measurement.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    ledger_path = output.with_name(output.stem + "_refusals.json")
    ledger_path.write_text(
        json.dumps(
            {
                "record_type": "attended_bods_session_refusal_ledger",
                "label": args.label,
                "started_at_utc": started_at,
                "finished_at_utc": finished_at,
                "snapshots_requested": args.snapshots,
                "snapshots_accepted": len(snapshot_ids),
                "snapshots_refused": len(refusals),
                "accepted_snapshot_ids": snapshot_ids,
                "refusals": refusals,
                "refusal_semantics": (
                    "every refusal is fail-closed: the feed was never promoted and its "
                    "bytes stay in quarantine. This runner continues the attended window "
                    "instead of discarding it; it does not weaken, retry, or bypass the "
                    "MAN-05 parser, which is lead-owned and untouched."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"refusal ledger: {ledger_path}", flush=True)

    if len(snapshot_ids) < 2:
        print("fewer than two accepted snapshots; no cadence measurement", file=sys.stderr)
        return 1

    results: list[SessionExtractionResult] = []
    for snapshot_id in snapshot_ids:
        result = extract_session_observations(workspace, snapshot_id, session_salt=session_salt)
        results.append(result)
        print(
            f"  extracted {result.observations_extracted}/{result.activities_seen} "
            f"({result.malformed_skipped} malformed) from {snapshot_id}",
            flush=True,
        )
    measurement = measure_session_cadence(results)
    output.write_text(measurement_to_json(measurement) + "\n", encoding="utf-8")
    print("--- aggregate cadence measurement (no identifiers) ---", flush=True)
    print(measurement_to_json(measurement), flush=True)
    print(f"written to {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

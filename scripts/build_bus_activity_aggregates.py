#!/usr/bin/env python3
"""Build a session activity aggregate post-hoc from stored quarantine (owner-run).

The bus-prediction layer consumes ``bods_session_activity_aggregate``
artifacts only. Scheduled sessions write them at capture time (Phase 143);
this script produces the SAME artifact for a stored attended session, so the
four attended windows can join the forecaster's dataset without any schema
fork.

The reviewed boundary applies verbatim: quarantine is reopened only through
the accepted session-identity library, one fresh in-process salt is created
for the whole pass and dies with it, and the output is aggregate-only —
per-snapshot counts and hourly progression, no identifiers, no raw bytes.
Because attended cadence measurements do not store per-snapshot parser
counts, concurrency here is the extracted observation count per snapshot and
is labelled ``extracted_observation_count``.

Usage (attended, owner present):
    uv run python scripts/build_bus_activity_aggregates.py \
        --workspace <v0.7-workspace> \
        --ledger <refusal ledger or completion marker JSON with accepted_snapshot_ids> \
        --label evening_peak --session-date 2026-07-28 --utc-offset-seconds 3600 \
        --output-dir <owner-selected directory>
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from pathlib import Path

from traffictwin.integration.manchester.bods_session_identity import (
    BodsSessionIdentityError,
    SessionExtractionResult,
    extract_session_observations,
    measure_session_progression,
)

_ERROR_TEXT_LIMIT = 300


def _snapshot_hour_utc(snapshot_id: str) -> int | None:
    parts = snapshot_id.split("-")
    if len(parts) < 2 or len(parts[1]) < 11 or "T" not in parts[1]:
        return None
    try:
        hour = int(parts[1][9:11])
    except ValueError:
        return None
    return hour if 0 <= hour <= 23 else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument(
        "--ledger",
        required=True,
        type=Path,
        help="JSON carrying accepted_snapshot_ids (refusal ledger or completion marker)",
    )
    parser.add_argument("--label", required=True)
    parser.add_argument("--session-date", required=True, help="local service date, YYYY-MM-DD")
    parser.add_argument(
        "--utc-offset-seconds",
        required=True,
        type=int,
        help="the session's local UTC offset (3600 for BST, 0 for GMT) — stated, not guessed",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    workspace = args.workspace.expanduser().resolve()
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    snapshot_ids = list(ledger.get("accepted_snapshot_ids", []))
    if len(snapshot_ids) < 2:
        print("the ledger names fewer than two accepted snapshots", file=sys.stderr)
        return 1

    session_salt = secrets.token_bytes(32)
    results: list[SessionExtractionResult] = []
    per_snapshot: list[dict[str, object]] = []
    offset = args.utc_offset_seconds
    for snapshot_id in snapshot_ids:
        result = extract_session_observations(workspace, snapshot_id, session_salt=session_salt)
        results.append(result)
        hour_utc = _snapshot_hour_utc(snapshot_id)
        per_snapshot.append(
            {
                "snapshot_id": snapshot_id,
                "hour_utc": hour_utc,
                "hour_local": None if hour_utc is None else (hour_utc + offset // 3600) % 24,
                "live_vehicle": result.observations_extracted,
            }
        )
        print(
            f"  extracted {result.observations_extracted}/{result.activities_seen} "
            f"from {snapshot_id}",
            flush=True,
        )

    progression_rows: list[dict[str, object]] = []
    progression_available = False
    progression_unavailable_reason: str | None = None
    try:
        progression = measure_session_progression(results)
    except BodsSessionIdentityError as error:
        progression_unavailable_reason = str(error)[:_ERROR_TEXT_LIMIT]
    else:
        progression_available = True
        for index, hour_utc in enumerate(progression.hour_utc):
            progression_rows.append(
                {
                    "hour_utc": hour_utc,
                    "hour_local": (hour_utc + offset // 3600) % 24,
                    "segment_count": progression.segment_count_by_hour[index],
                    "speed_mps_median": progression.speed_mps_median_by_hour[index],
                    "speed_mps_p90": progression.speed_mps_p90_by_hour[index],
                    "vehicles_contributing": progression.vehicles_contributing_by_hour[index],
                }
            )

    payload = {
        "record_type": "bods_session_activity_aggregate",
        "schema_version": "1.0",
        "design_reference": "docs/platform/bus_prediction_design.md",
        "session_kind": "attended",
        "label": args.label,
        "session_date_local": args.session_date,
        "utc_offset_seconds_applied": offset,
        "timezone_note": (
            "session_date_local and hour_local use the owner-stated UTC offset for "
            "the session's local service date (Europe/London)"
        ),
        "schedule_digest": None,
        "snapshot_count": len(snapshot_ids),
        "concurrency_source": "extracted_observation_count",
        "per_snapshot_live_vehicle": per_snapshot,
        "progression_available": progression_available,
        "progression_unavailable_reason": progression_unavailable_reason,
        "hourly_progression": progression_rows,
        "aggregates_only": True,
        "raw_identifiers_published": False,
        "bus_progression_only": True,
        "road_traffic_speed_available": False,
        "session_salt_discarded": True,
    }
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"activity_aggregate_{args.session_date}_{args.label}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"aggregate written: {output}", flush=True)
    print(
        f"progression: {'available' if progression_available else 'unavailable'} "
        f"({len(progression_rows)} hourly row(s))",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

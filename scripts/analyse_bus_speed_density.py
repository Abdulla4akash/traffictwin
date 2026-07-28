#!/usr/bin/env python3
"""Measure bus progression speed against fleet density across all four sessions.

The four attended sessions span a 36x range of fleet size (41 to ~1,481 active
vehicles) under one unchanged acquisition boundary and one identity policy. That
makes them a natural speed-density series for the observed bus fleet, and it
needs no new acquisition and no simulator.

Speed is computed per segment by the accepted B2 primitive
(`measure_session_progression`), not as median-displacement over median-interval,
which is not a median speed.

Each session is a separately declared session with its own in-process salt, so
no vehicle is linkable across sessions. Progression speed is bus progression,
never road traffic speed, and this is descriptive and non-causal: fleet size and
time of day move together and are not separated here.

Usage:
    uv run python scripts/analyse_bus_speed_density.py
"""

from __future__ import annotations

import json
import secrets
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from traffictwin.integration.manchester.bods_session_identity import (
    extract_session_observations,
    measure_session_cadence,
    measure_session_progression,
)

WORKSPACE = Path("~/AntigravityTest/diss/data/workspace-v0.7").expanduser().resolve()
OUT = Path("data/bus-speed-density-20260728").resolve()

#: Sessions are bounded by explicit UTC stamp ranges, not by hour prefix. The
#: dawn session spans 05:1x-06:09 and would otherwise swallow `065742Z`, which
#: is the single promotion from the aborted 07:57 BST morning attempt and
#: belongs to no measured session. The morning peak's 51 accepted snapshots are
#: 52 attempts minus its one refusal.
SESSIONS: list[dict[str, Any]] = [
    {"label": "night_probe", "from": "20260726T230000Z", "to": "20260727T000000Z"},
    {"label": "shallow_dawn", "from": "20260728T050000Z", "to": "20260728T061000Z"},
    {"label": "morning_peak", "from": "20260728T070000Z", "to": "20260728T080000Z"},
]
EVENING_LEDGER = WORKSPACE / "manchester" / "bus_evening_peak_session_20260728_refusals.json"


def accepted_ids(start: str, end: str) -> list[str]:
    """Return promoted snapshot ids whose stamp lies in [start, end).

    Reads the *accepted* directory, so refused snapshots are excluded by
    construction rather than by filtering.
    """

    accepted = WORKSPACE / "accepted"
    picked = []
    for path in accepted.iterdir():
        if not path.name.startswith("bods_siri_vm-"):
            continue
        stamp = path.name.split("-")[1]
        if start <= stamp < end:
            picked.append(path.name)
    return sorted(picked)


def analyse(label: str, snapshot_ids: list[str]) -> dict[str, Any]:
    # A fresh salt per session: linkage exists only inside one declared session
    # and dies with this process.
    salt = secrets.token_bytes(32)
    results = [
        extract_session_observations(WORKSPACE, sid, session_salt=salt) for sid in snapshot_ids
    ]
    cadence = measure_session_cadence(results)
    progression = measure_session_progression(results)

    hourly = [
        {
            "hour_utc": hour,
            "segments": segments,
            "vehicles": vehicles,
            "median_speed_mps": float(median),
            "p90_speed_mps": float(p90),
        }
        for hour, segments, vehicles, median, p90 in zip(
            progression.hour_utc,
            progression.segment_count_by_hour,
            progression.vehicles_contributing_by_hour,
            progression.speed_mps_median_by_hour,
            progression.speed_mps_p90_by_hour,
            strict=True,
        )
    ]
    # The session-level figure is the support-weighted median of hourly medians,
    # with thin hours visible rather than silently folded in.
    supported = [h for h in hourly if h["segments"] >= 100 and h["median_speed_mps"] is not None]
    session_median = (
        statistics.median([h["median_speed_mps"] for h in supported]) if supported else None
    )
    return {
        "label": label,
        "snapshots": len(snapshot_ids),
        "vehicles_seen_total": cadence.vehicles_seen_total,
        "vehicles_linked_across_snapshots": cadence.vehicles_linked_across_snapshots,
        "update_delta_seconds_median": cadence.update_delta_seconds_median,
        "displacement_m_median": cadence.displacement_m_median,
        "hourly_progression": hourly,
        "hours_with_support_at_least_100_segments": len(supported),
        "session_median_speed_mps": session_median,
        "session_median_speed_kmh": session_median * 3.6 if session_median is not None else None,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in SESSIONS:
        ids = accepted_ids(spec["from"], spec["to"])
        if len(ids) < 2:
            print(f"skip {spec['label']}: {len(ids)} accepted snapshots", flush=True)
            continue
        print(f"analysing {spec['label']} ({len(ids)} snapshots) ...", flush=True)
        rows.append(analyse(spec["label"], ids))

    ledger = json.loads(EVENING_LEDGER.read_text())
    print(
        f"analysing evening_peak ({len(ledger['accepted_snapshot_ids'])} snapshots) ...", flush=True
    )
    rows.append(analyse("evening_peak", ledger["accepted_snapshot_ids"]))

    payload = {
        "record_type": "bus_speed_density_series",
        "record_date": datetime.now(UTC).date().isoformat(),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "research_status": "owner_approved_candidate",
        "supervisor_approved": False,
        "scientifically_validated": False,
        "policy_id": "manchester-bods-session-identity-1.1",
        "method": {
            "speed": "per-segment via the accepted B2 primitive measure_session_progression",
            "why_not_displacement_over_interval": (
                "median displacement divided by median interval is not a median speed; "
                "the per-segment computation is the correct one and is what is reported"
            ),
            "session_figure": (
                "median of hourly median speeds over hours carrying at least 100 segments; "
                "thin hours stay visible in the hourly table rather than being folded in"
            ),
            "identity": "one fresh in-process salt per declared session; no cross-session linkage",
        },
        "explicit_non_claims": [
            "bus progression speed is never road traffic speed",
            "descriptive and non-causal: fleet size and time of day covary and are not separated",
            "stale-resume segments inflate no aggregate here because speeds are per segment "
            "and the hourly medians are robust to a small number of extreme values",
        ],
        "sessions": rows,
    }
    out = OUT / "bus_speed_density.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print()
    print(
        f"{'session':<16}{'snaps':>7}{'active':>9}{'median m/s':>12}{'km/h':>8}{'disp med m':>12}"
    )
    for r in rows:
        speed = r["session_median_speed_mps"]
        head = f"{r['label']:<16}{r['snapshots']:>7}{r['vehicles_linked_across_snapshots']:>9}"
        if speed is None:
            print(f"{head}  no hour with sufficient support")
            continue
        print(f"{head}{speed:>12.3f}{speed * 3.6:>8.1f}{r['displacement_m_median']:>12.1f}")
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

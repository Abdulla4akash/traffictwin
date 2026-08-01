# Dhaka corridor — BD-D1 / BD-D2 decision worksheet (DECIDED 1 August 2026)

**Status: DECIDED. The owner answered both decisions interactively in session on
1 August 2026 (BD-D1: Airport road corridor; BD-D2: download authorised), the pinned
extract was retrieved and verified, and the feasibility build ran and was ACCEPTED. See
[`dhaka_corridor_feasibility_20260801.md`](dhaka_corridor_feasibility_20260801.md) for
the measured result; the frozen scope and pin are committed beside the receipt in
`evidence/`. The original empty template is preserved below for the record.**

Design: [`docs/platform/dhaka_corridor_design.md`](../platform/dhaka_corridor_design.md)
(REVIEWED). Contract: `traffictwin.integration.corridor_network`
(`corridor-network-build-1.0`). Runner: `scripts/build_dhaka_corridor_network.py`.

## BD-D1 — the corridor (owner decides)

The design's proposed default is the **Dhaka–Airport road corridor (Mohakhali → Hazrat
Shahjalal International)**; the named alternative is **Mirpur Road**. Per the reviewed
design, any congestion/operational/BRTC rationale must be independently sourced before
deciding — the proposal text is not traffic or BRTC evidence.

To freeze the decision, complete a scope JSON (`CorridorScope` schema) with:

| field | value |
|---|---|
| corridor (Airport road / Mirpur Road / other) | |
| bbox (min_lon, min_lat, max_lon, max_lat) | |
| ≥4 landmarks (name, lon, lat) | |
| decided_by | |
| decision date | |

A fixture-shaped example (test values, NOT a decision) lives in
`tests/unit/test_corridor_network.py`.

## BD-D2 — the dated extract (owner decides; authorises the download)

Resolve a **dated** Geofabrik Bangladesh artifact (never `-latest`; the contract refuses
it) and record, into an `ExtractPin` JSON:

| field | value |
|---|---|
| final dated URL | |
| reference/publication date | |
| byte size | |
| SHA-256 | |
| provider checksum (if published) | |
| retrieval time (UTC) | |

Licence and attribution are fixed by the contract: ODbL 1.0,
`© OpenStreetMap contributors, ODbL 1.0`, carried through the receipt and any rendered
map. Raw and derived bytes stay in the owner workspace unless publication is separately
reviewed.

## Run (after both answers)

```
uv run python scripts/build_dhaka_corridor_network.py \
    --workspace <workspace> --scope <bd_d1_scope.json> --pin <bd_d2_pin.json> \
    --confirm-network
```

The output is a receipted **network-build feasibility result** — role
`corridor_network_candidate`, `observation_status: unavailable`, excluded claims stated
in the receipt. Stop rule: one corridor, one pinned extract; a city-wide build,
observation acquisition, or any experiment needs a new owner decision.

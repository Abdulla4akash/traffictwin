# Dhaka corridor network-build feasibility result (1 August 2026)

**Status: `owner_approved_candidate`, network-layer engineering feasibility artifact
ONLY. Role `corridor_network_candidate`; `observation_status: unavailable`. This record
carries no observations, demand, routes, calibration, behavioural model, VEC execution
or scientific validation, and is for the transferability/funding discussion — it is not
admitted dissertation evidence and does not claim a twin runs in Dhaka.**

Design: [`docs/platform/dhaka_corridor_design.md`](../platform/dhaka_corridor_design.md)
(REVIEWED). Contract: `corridor-network-build-1.0` (Phase 146). Receipt (committed,
publication-safe, no private path):
[`evidence/dhaka_corridor_build_receipt_20260801.json`](evidence/dhaka_corridor_build_receipt_20260801.json).

## Decisions (BD-D1 / BD-D2 — answered by the owner in session, 1 August 2026)

- **BD-D1**: the **Dhaka–Airport road corridor (Mohakhali → Hazrat Shahjalal
  International)** — the design's proposed default, selected interactively by the owner.
  Frozen scope (bbox 90.37, 23.765 → 90.435, 23.865; four landmarks):
  [`evidence/dhaka_corridor_scope_bd_d1_20260801.json`](evidence/dhaka_corridor_scope_bd_d1_20260801.json).
  Landmark coordinates are approximate OSM-derived points, recorded as such in the scope.
- **BD-D2**: the owner authorised the download in session. Pinned dated artifact:
  `bangladesh-260731.osm.pbf` (Geofabrik, reference date 2026-07-31), 350,592,973 bytes,
  sha256 `9ba6545d…20cfc067`, provider md5 `7408d0ea…` verified on retrieval:
  [`evidence/dhaka_corridor_extract_pin_bd_d2_20260801.json`](evidence/dhaka_corridor_extract_pin_bd_d2_20260801.json).

## Measured result — ACCEPTED, zero feasibility gaps

| measured | value |
|---|---|
| tools | osmium 1.19.1, Eclipse SUMO netconvert 1.27.1 (pinned) |
| stage durations | clip 1.9 s, decode 0.3 s, build 4.6 s, validate 0.2 s |
| edges | 106,431 total; **24,642 real** (81,789 junction-internal) |
| junctions | 24,347 |
| no-shape real-edge share | **36.6%** (Manchester's 36% is comparison context only) |
| projection chosen by netconvert | UTM zone **46** (WGS84) — east of the 45N/46N boundary |
| network extent (own projection) | 90.3632, 23.7516 → 90.4646, 23.8816 |
| corridor containment (landmark hull) | **contained = true (measured)** |
| landmark reconciliation (150 m tolerance) | Mohakhali flyover 12.2 m; Banani Kakoli 27.7 m; Kurmitola Hospital 63.9 m; HSIA approach 15.0 m |
| derived network sha256 | `19a1b1ab…` (70,253,654 B) |
| canonical identity (banner-stripped) | `1c9943f8…` |

Raw extract, decoded XML and the built network stay in the owner workspace
(`network-build/dhaka-corridor/`); publication of derived bundles is not automatic.
OSM data © OpenStreetMap contributors, ODbL 1.0.

## Findings worth recording

1. **The corridor build is cheap and clean**: 6.8 s of tool time end to end on the
   pinned extract, no netconvert failure, no feasibility gap. The one-day estimate in the
   design was conservative by two orders of magnitude at corridor scale.
2. **The no-shape share (36.6%) matches Manchester's 36%** — the straight-line-geometry
   caveat transfers to Dhaka OSM data at almost exactly the same rate, which strengthens
   the comparison-context framing rather than any completeness claim.
3. **The contract's first real run caught a real defect**: the canonical identity's
   single-line comment matcher missed netconvert's multi-line banner (which also carries
   absolute input paths), so canonical equalled the raw digest. Fixed to block-stripping
   in the same phase; the committed receipt carries the corrected, banner-independent
   identity.
4. All four owner landmarks reconciled 12–64 m from network junctions through the
   network's own projection — the UTM 46N choice is validated against ground truth, not
   assumed.

## Stop rule

One corridor, one pinned extract, per the design: no city-wide build, no observation
acquisition, no threshold tuning, no experiment. Any of those needs a new owner decision.

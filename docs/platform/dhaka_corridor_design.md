# Design — Dhaka corridor network build (Bangladesh tier 2, optional)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. The one cheap artifact of
the Bangladesh direction: a receipted "the twin already runs on Dhaka roads" proof,
built through the EXISTING pipeline with zero new algorithmic work. Scheduled strictly
after the platform slices; it exists to strengthen the funding narrative, not the
dissertation's science.**

## 1. What is built

One Dhaka corridor network (not city-wide): pinned dated Geofabrik Bangladesh extract →
osmium clip to a declared corridor box → the committed decode → netconvert 1.27.1 build
→ streaming validation → durable storage with canonical identity digest + receipts —
the exact Manchester chain (`rebuild_baseline_network.py` pattern) with a new scope
config.

## 2. Scope decisions (owner, before build)

- **BD-D1 — the corridor.** Proposed default: the Dhaka–Airport road corridor
  (Mohakhali → Hazrat Shahjalal International), one of the canonical congestion
  corridors and plausibly the BRTC pilot alignment the concept note sketches. The
  alternative is Mirpur Road. One corridor only.
- **BD-D2 — the dated extract.** Pin the newest dated Geofabrik `bangladesh` file at
  build time (the `-latest`-redirect lesson applies verbatim); record URL, date, md5.

## 3. Known transfers and known unknowns

Transfers: the whole toolchain, the workspace-containment and identity-digest rules,
`admissible_role` semantics (the corridor is `sub_area_probe_only` by construction —
measured containment, same as the city-centre probe rule). Unknowns to MEASURE, not
assume, and record in the build receipt: OSM completeness/tagging quality for Dhaka
(expect sparser `shape`, more unclassified ways than the 36% no-shape / class mix
Manchester measured — the per-edge `geometry_source` recording carries over); UTM zone
45N/46N boundary (Dhaka sits near 90°E — verify netconvert's projection choice against
landmarks, the 4-landmark validation recipe); no count or live-bus data exists on this
side — the network ships **observation-empty**, and saying so is the point: it is the
funding ask made concrete.

## 4. Governance

New scope config + build script additions are new files; the Manchester scope config is
untouched. The build record states plainly that this artifact carries no observations,
no demand, no calibration — a network-layer transferability proof only, produced for
the transferability section (report tier 1) and the concept note (tier 3).

## 5. Effort

~1 day: extract download + clip (minutes), build (the corridor is far smaller than the
GM 2.11M-edge parent), validation + receipts + record. Effort is real but bounded; if
the OSM quality unknowns bite, the honest outcome is a *measured* quality report of the
gap — which serves the funding narrative just as well.

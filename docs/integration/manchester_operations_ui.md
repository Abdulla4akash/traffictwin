# Manchester Operations UI candidate

This document describes the thin Streamlit and PyDeck candidate above the
[MAN-08 map-layer service](manchester_map_layers.md). `MAN-08` remains `planned`: the page is
software evidence, not acceptance of any Manchester source, live feed, calibration, or comparison.

## Availability and setup

The page is additive at `/manchester` inside the normal v0.7 development router:

```bash
uv run python - <<'PY'
from traffictwin.release import initialise_v07_workspace

initialise_v07_workspace("/path/to/workspace-v0.7")
PY

export TRAFFICTWIN_WORKSPACE_PATH=/path/to/workspace-v0.7
uv run streamlit run src/traffictwin/ui/app.py
```

The complete v0.6 router remains available with `TRAFFICTWIN_V07_NAVIGATION=legacy`. Adding
Manchester Operations does not change the normative 34-page migration inventory or the immutable
`v0.6.0` release.

## Local scene contract

Only the five explicit source families described below may call DfT, WebTRIS, TfGM, BODS, or the
three fixed National Highways operational products. The page
never calls Randy, SUMO, or an arbitrary URL. Ordinary Streamlit reruns and **Refresh local
evidence** perform no acquisition. For the selected mode the page reads one fixed, bounded local
artifact:

| Mode | Workspace-relative artifact |
|---|---|
| Historical replay | `manchester/scenes/historical_replay.json` |
| Latest available | `manchester/scenes/latest_available.json` |
| Live vehicles | `manchester/scenes/live_vehicles.json` |

The National Highways overlays are independently validated at
`manchester/scenes/national_highways_latest_available.json` and
`manchester/scenes/national_highways_live_vehicles.json`. The loader composes a valid base scene
and valid operational overlay in memory. If either source family fails integrity checks, the other
remains usable; no source is fused or silently dropped from its own reconciliation.

Each file must be at most 8 MiB and validate as the exact `ManchesterMapScene` for that mode.
Missing files are unavailable. Empty, oversized, symlinked, escaped, unreadable, mutated, invalid,
or cross-mode files fail closed with display-safe reasons. The scene cache is bounded to 12 entries
with a 30-second TTL. The accepted WebTRIS and DfT catalogue caches are each bounded to four
entries; selected WebTRIS site-days are bounded to 12 entries, DfT filter inventories to 12, and
small explicit DfT survey views to 24, also for 30 seconds. The refresh action clears these local
caches.

## Explicit live-bus acquisition

The **Live vehicles** mode contains a form for one controlled BODS SIRI-VM request. Configure the
credential and an explicit request scope in the process environment before starting Streamlit:

```bash
export BODS_API_KEY='your-BODS-key'
export TRAFFICTWIN_BODS_BOUNDING_BOX='min_longitude,min_latitude,max_longitude,max_latitude'
```

TrafficTwin deliberately supplies no default Manchester boundary. The operator must enter four
ordered WGS84 coordinates in the form or set `TRAFFICTWIN_BODS_BOUNDING_BOX`. The API key is read
only when rendering readiness and passed transiently only after **Fetch latest buses** is clicked;
it is never placed in a model, receipt, scene, session-state value, error, or log. One form submit
performs one request. The control state permits only one refresh at a time and at least 60 seconds
between attempts. There is no timer, polling loop, automatic retry cycle, or network activity on
an ordinary UI rerun.

The controlled workflow is:

```text
explicit submit
  -> bounded authenticated BODS acquisition
  -> private quarantine before XML parsing
  -> accepted snapshot re-read and fingerprint reconciliation
  -> privacy-safe bus positions admitted through MAN-07
  -> exact OperatorRef Bee Network / other-or-unknown separation
  -> freshness-separated MAN-08 layers
  -> atomic replacement of manchester/scenes/live_vehicles.json
  -> bounded aggregate-only local history
```

The output means **BODS transit vehicle positions only**. It is not live road traffic, traffic
volume, or congestion. Five exact live-feed-verified policy-v1 `OperatorRef` values receive a Bee
Network label; every non-match stays other/unknown and `BNVB` remains pending. Stale observations
remain visibly separate from live observations. On later local reruns, source timestamps are
re-evaluated at the current UTC instant and expired layers become **stale cached** without changing
the stored scene. Raw and accepted source artifacts and the local scene are private; public export
remains unavailable. If any transport, quarantine, parser, fingerprint,
spatial, freshness, workspace, or file-publication check fails, the prior local scene is retained.
See [the controlled live workflow](manchester_bods_live.md) for the library contract. The page also
exposes a separate private-snapshot cleanup preview. Its precautionary default is 24 hours / 240
complete accepted-plus-quarantine families; the active scene and newest family are protected,
nothing is deleted automatically, and apply requires the exact plan-bound confirmation. This does
not claim approved legal retention or secure erasure.
Historical and latest scenes use the separate
[bounded local publication service](manchester_scene_publication.md); ordinary page rendering never
creates either scene.

## Explicit National Highways operational acquisition

**Latest available** and **Live vehicles** each expose the same explicit three-product refresh
form. Configure the subscription key before starting Streamlit:

```bash
export NATIONAL_HIGHWAYS_API_KEY='your-subscription-key'
```

The key is a transient redacted request header and never enters session state, receipts, scenes,
logs, errors, or stored URLs. One click performs exactly three bounded requests after the
one-minute/one-process-lock guard. It snapshots closures/incidents, imposed temporary limits, and
digital VMS status independently, then publishes source-separated overlays. The broad envelope is
shown explicitly and is not an official boundary. A failed refresh retains the prior overlay and
projects it stale; ordinary reruns perform no network activity. National Highways layers use the
required attribution and remain private pending release review.

## Explicit latest and historical acquisition

The **Latest available** mode contains two separate forms:

- WebTRIS accepts one numeric site ID and one explicit source date, fetches the site, daily report,
  and quality response through MAN-03, and publishes only the selected strategic-road site
  reference. Daily values stay in the separate interval chart and retain missing values and source
  warnings. This is latest-available/historical evidence, not live city-road telemetry.
- TfGM fetches the one audited static signal-location archive through MAN-04 and publishes its
  source-separated reference layer. It cannot represent signal phase, timing, queues, incidents,
  traffic counts, or live operational state.

The **Historical replay** mode contains one expanded DfT form for exact raw-count, count-point, and
AADF row IDs. Each request is Manchester-scoped and bounded to the selected row. The source-specific
survey view consumes only the raw-count result; the map consumes only the count-point reference;
AADF stays a separately labelled statistical artifact.

The workflows preserve exact source bytes, publish only after complete validation, retain unrelated
scene layers, and expose display-safe failure codes. See
[Manchester explicit source refresh workflows](manchester_source_refresh.md) for the tested
real-source behavior and residual boundaries.

## Rendering and interaction

- `st.segmented_control` selects the evidence mode.
- `st.pills` selects only layers already marked visible and locally renderable by MAN-08.
- Separate `st.pills` controls filter that selected layer inventory by exact geographic scope and
  freshness state. Defaults show every evidenced option; an empty selection honestly shows no map
  points.
- `st.pydeck_chart` renders admitted WGS84 points with a `TextLayer` symbol per source family.
- `map_provider=None` and `map_style=None` prevent a hidden external basemap request.
- Colour is supplemented by circle, square, diamond, triangle, or cross symbols and accessible
  source descriptions.
- The per-source table and cards retain status, deterministic reason, freshness,
  accepted/displayed/hidden/excluded point reconciliation, snapshot, publication class, and
  licence. These rows are never summed into a cross-source traffic total.
- Attribution and geographic scopes below the map follow the displayed point subset.
- Point identifiers are not sent through the evidence-details table; it contains layer-level
  reconciliation only.
- In **Historical replay**, a separate `st.selectbox` lists only verified accepted DfT raw-count
  snapshots. A single count point, survey date, and audited vehicle-class field combine with exact
  source-direction pills and local-clock-hour selections. The tested source service produces one
  output per matching source row without aggregation.
- A grouped native bar chart displays present DfT source counts by exact direction and
  timezone-undeclared local-clock label. A separate table retains every selected row and its
  present/missing state. Empty intersections and all-missing selections render explicit states,
  never substituted surveys or zero-filled bars.
- In **Historical replay** and **Latest available**, a `st.selectbox` lists only verified accepted WebTRIS daily-report
  snapshot IDs. The label retains exact site, source date, evidence class, and snapshot suffix;
  conflicting versions are never silently merged.
- Measurement-state pills filter `observed` and `missing` rows through the tested MAN-08 service.
  Separate native line charts show per-reported-interval volume and source mph without aggregation;
  missing measurements remain chart gaps. The x-axis is explicitly a timezone-undeclared source
  label, not UTC.

The page does not sum records across sources or call spatial-record counts traffic volume. DfT
survey bars are not a continuous time series, speed, AADF demand, or a SUMO input. WebTRIS charts
are available only when a compatible accepted daily snapshot exists; the map scene itself still
carries no interval observations. **Compare with SUMO** and **Prepare SUMO baseline** remain
disabled until the MAN-09 and MAN-10 contracts pass.

## Verification

The focused tests cover unavailable workspaces, missing artifacts, invalid and oversized JSON,
symlink refusal, cross-mode refusal, byte hashing, layer selection, no-basemap PyDeck output,
exact scope/freshness option derivation, unknown/duplicate/tampered filtered-view refusal,
empty-filter reconciliation, additive navigation, disabled actions, AppTest rendering and
interaction for both empty and valid local states, accepted DfT catalogue/filter/view rendering,
empty and missing survey semantics, accepted WebTRIS catalogue selection and chart projection with
missing-value gaps, live-form prerequisite gating, explicit
bounding-box validation, one-request publication, secret absence from persisted artifacts,
report-drift refusal, interval/concurrency guards, bounded aggregate history, live-to-stale local
projection, retention preview/confirmation/plan-drift checks, and preservation of the prior scene
after publication failure. The
scene-publication tests additionally cover fixed historical/latest paths, private-only output,
request and receipt tampering, interrupted atomic replacement, and preservation of the prior scene.

Controlled real-source vertical slices now pass for BODS, the three selected DfT products, one
WebTRIS site/day plus quality, the pinned TfGM archive, and all three National Highways operational
products. Full-source/bulk acceptance, browser
screenshots, mobile/keyboard/contrast checks, provider SLA decisions, continuous city-road
telemetry, and the complete MAN-01 through MAN-08 acceptance reconciliation remain outstanding.

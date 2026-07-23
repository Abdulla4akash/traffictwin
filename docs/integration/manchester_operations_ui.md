# Manchester Operations UI candidate

This document describes the thin Streamlit and PyDeck candidate above the
[MAN-08 map-layer service](manchester_map_layers.md). `MAN-08` remains `planned`: the page is
software evidence, not acceptance of any Manchester source, live feed, calibration, or comparison.

## Availability and setup

The page is additive at `/manchester` inside the opt-in v0.7 router:

```bash
uv run python - <<'PY'
from traffictwin.release import initialise_v07_workspace

initialise_v07_workspace("/path/to/workspace-v0.7")
PY

export TRAFFICTWIN_V07_NAVIGATION=1
export TRAFFICTWIN_WORKSPACE_PATH=/path/to/workspace-v0.7
uv run streamlit run src/traffictwin/ui/app.py
```

The complete v0.6 router remains the default. Adding Manchester Operations does not change the
normative 34-page migration inventory.

## Local scene contract

Except for the explicit BODS form described below, the page never calls DfT, WebTRIS, TfGM,
BODS, Randy, SUMO, or any arbitrary URL. Ordinary Streamlit reruns and **Refresh local evidence**
perform no acquisition. For the selected mode the page reads one fixed, bounded local artifact:

| Mode | Workspace-relative artifact |
|---|---|
| Historical replay | `manchester/scenes/historical_replay.json` |
| Latest available | `manchester/scenes/latest_available.json` |
| Live vehicles | `manchester/scenes/live_vehicles.json` |

Each file must be at most 8 MiB and validate as the exact `ManchesterMapScene` for that mode.
Missing files are unavailable. Empty, oversized, symlinked, escaped, unreadable, mutated, invalid,
or cross-mode files fail closed with display-safe reasons. The cache is bounded to 12 entries with
a 30-second TTL; the refresh action clears only this local scene cache.

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
performs one request. There is no timer, polling loop, automatic retry cycle, or network activity
on an ordinary UI rerun.

The controlled workflow is:

```text
explicit submit
  -> bounded authenticated BODS acquisition
  -> private quarantine before XML parsing
  -> accepted snapshot re-read and fingerprint reconciliation
  -> privacy-safe bus positions admitted through MAN-07
  -> freshness-separated MAN-08 layers
  -> atomic replacement of manchester/scenes/live_vehicles.json
```

The output means **BODS transit vehicle positions only**. It is not live road traffic, traffic
volume, congestion, or proof that a vehicle belongs to the Bee Network. Stale observations remain
visibly separate from live observations. Raw and accepted source artifacts and the local scene are
private; public export remains unavailable. If any transport, quarantine, parser, fingerprint,
spatial, freshness, workspace, or file-publication check fails, the prior local scene is retained.
See [the controlled live workflow](manchester_bods_live.md) for the library contract.
Historical and latest scenes use the separate
[bounded local publication service](manchester_scene_publication.md); ordinary page rendering never
creates either scene. An explicit [TfGM snapshot-to-scene bridge](manchester_tfgm_scene.md) can
populate the latest view with accepted static signal locations; those points are infrastructure,
not signal state or traffic observations.

## Rendering and interaction

- `st.segmented_control` selects the evidence mode.
- `st.pills` selects only layers already marked visible and locally renderable by MAN-08.
- `st.pydeck_chart` renders admitted WGS84 points with a `TextLayer` symbol per source family.
- `map_provider=None` and `map_style=None` prevent a hidden external basemap request.
- Colour is supplemented by circle, square, diamond, triangle, or cross symbols and accessible
  source descriptions.
- Source cards retain status, deterministic reason, freshness, rendered/excluded record counts,
  snapshot, publication class, and licence.
- Attribution and geographic scopes remain visible below the map.
- Point identifiers are not sent through the evidence-details table; it contains layer-level
  reconciliation only.

The page does not sum records across sources or call them traffic volume. Traffic charts remain
unavailable until compatible interval observations exist. **Compare with SUMO** and **Prepare SUMO
baseline** remain disabled until the MAN-09 and MAN-10 contracts pass.

## Verification

The focused tests cover unavailable workspaces, missing artifacts, invalid and oversized JSON,
symlink refusal, cross-mode refusal, byte hashing, layer selection, no-basemap PyDeck output,
additive navigation, disabled actions, AppTest rendering of both empty and valid local states,
live-form prerequisite gating, explicit bounding-box validation, one-request publication, secret
absence from persisted artifacts, report-drift refusal, and preservation of the prior scene after
publication failure. The scene-publication tests additionally cover fixed historical/latest paths,
private-only output, request and receipt tampering, interrupted atomic replacement, and preservation
of the prior scene.

Real-source Gate B acceptance using an operator-supplied valid key, historical/site/direction/
vehicle-class filters, compatible traffic charts, browser screenshots, mobile/keyboard/contrast
checks, and the complete MAN-05/MAN-08 acceptance gates remain outstanding.

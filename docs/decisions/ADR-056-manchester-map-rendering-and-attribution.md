# ADR-056: Manchester Map Rendering, Tiles, Offline Behaviour, and Attribution

- Status: accepted (Gate A decision; Gate C implements and accepts the map)
- Date: 2026-07-22
- Capability: `MAN-08`, `UX-02`, `UX-03` map layer; constrains `MAN-04` display

## Context

The v0.7 design requires a layered Manchester map with visible source/freshness state, offline
usability, and recorded licences for map tiles, boundary geometry, and network assets (design
§12, §19, §25 Q12). The repository currently contains no map or geographic rendering code. The
Gate A audit ([manchester-source-gate-a-audit-v0_7.md](../integration/manchester-source-gate-a-audit-v0_7.md))
confirmed (all 2026-07-22): pydeck 0.9.3 is Apache-2.0 and an unconditional Streamlit dependency
(`st.pydeck_chart`); pydeck's default basemap provider is Carto with `map_provider=None` as the
documented no-basemap mode; Carto's keyless basemap tier is formally limited to "CARTO grantees"
and its exact required attribution text could not be confirmed (`GA-MAP-1`); the OSM tile-usage
policy requires attribution and a distinct User-Agent, forbids bulk prefetch, and permits
blocking without notice; OSM data is ODbL; ONS Open Geography Portal boundary products are OGL
v3.0 with two required attribution statements; and the TfGM signals dataset ships dual
EPSG:27700/WGS84 coordinates with its own exact OGL attribution line.

## Decision

1. **Rendering component: `pydeck>=0.9.3,<1` through `st.pydeck_chart`.** The reviewed Streamlit
   lock resolves pydeck 0.9.3. Gate B adds a direct dependency only if Manchester code imports
   pydeck directly; otherwise the Streamlit dependency remains authoritative. The UI stays native
   Streamlit per design §3.14.
2. **Default map mode is basemap-free and offline-safe: `map_provider=None`.** Context comes
   from vector layers TrafficTwin controls: the Manchester/GM boundary polygons (ONS Open
   Geography Portal, OGL v3.0), accepted observation sites, signals, buses, and admitted SUMO
   geometry. The map therefore renders identically online and offline, and no third-party tile
   service is a runtime dependency or failure mode.
3. **No external tile provider is enabled at Gate A.** A Carto basemap remains blocked behind
   `GA-MAP-1` (grantee terms and attribution text unconfirmed); OSM raster tiles are not used by
   default (policy: distinct User-Agent, caching, attribution, blockable without notice). If a
   basemap is ever proposed, it needs its own reviewed decision recording provider terms, exact
   attribution, key handling, and offline fallback — and the fallback is always mode 2 above.
4. **Attribution is layer-manifest data, not decoration.** Each map layer's
   `ManchesterMapLayerManifest` records its licence and required attribution string, and the map
   view renders the union of visible layers' attributions. Frozen wording where already
   evidenced: TfGM — "Contains Transport for Greater Manchester data. Contains OS data © Crown
   copyright and database right <year as shipped in the acquired artifact>"; ONS boundaries —
   "Source: Office for National Statistics licensed under the Open Government Licence v.3.0" and
   "Contains OS data © Crown copyright and database right <year>". Every layer also retains the
   [official OGL v3.0 URI](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
5. **Boundary geometry is a versioned reference artifact** (design §10): dataset identity,
   edition (e.g. the May-2025 LAD boundaries edition), CRS, generalisation level, retrieval date,
   hash, and licence are recorded like any other snapshot; boundaries are re-acquired only
   through the same bounded sync path.
6. **Coordinate admission rule for every geographic layer.** A layer renders on the geographic
   map only with an evidenced CRS: TfGM dual coordinates cross-checked via the versioned
   projection service (EPSG:27700 ↔ WGS84 agreement within tolerance is a validation invariant);
   BODS positions as profile-documented WGS84; DfT easting/northing+lat/lon cross-checked the
   same way; SUMO/VEC geometry only through the network's declared projection binding. Artifacts
   without an evidenced CRS (e.g. Randy trace coordinates, VEC analysis sites) do not render on
   the geographic map and remain in the existing non-geographic views.

## Consequences

- The map works offline with accepted snapshots, satisfying the design's offline/stale
  requirements without a tile cache.
- Licence exposure is limited to OGL-attributed vector data TrafficTwin already snapshots; no
  tile-provider terms gate the dissertation demo.
- Visual context is sparser than a street-level basemap; if that proves insufficient for the
  usability goals (RQ16), adding a basemap is an explicit future decision, not a default.
- Attribution correctness becomes testable: UI acceptance can assert the rendered attribution
  set equals the visible layers' manifest union.

## Rejected alternatives

- Default Carto basemap (pydeck's out-of-the-box behaviour): rejected at Gate A; keyless tier is
  formally grantee-limited and attribution text is unconfirmed (`GA-MAP-1`).
- Direct OSM raster tiles: rejected as default; policy burden (User-Agent, caching, blockable
  without notice) and a hard runtime dependency on a charity-run service.
- folium/leaflet or a custom JS map component: rejected; new dependency and custom-component
  surface against design §3.14, with no capability pydeck lacks for the required layers.
- Bundling downloaded tiles for offline use: rejected; redistribution/licence risk and repository
  bloat for no evidentiary value.

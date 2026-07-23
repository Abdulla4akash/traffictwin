# Manchester offline map-layer manifests (`MAN-08` candidate)

## Purpose

`src/traffictwin/integration/manchester/map_layers.py` converts accepted MAN-07 spatial decisions
into renderer-neutral point layers and scenes. It does not import PyDeck or Streamlit, contact a
tile provider, fetch source data, transform coordinates, map-match, interpolate movement, or join
sources. A later thin Manchester Operations page can translate this tested payload into
`st.pydeck_chart` without owning evidence logic.

This is candidate Gate-C foundation only. It does not enable the MAN-08 page or change MAN-08 from
`planned`.

## Layer prerequisites

Every `MapLayerRequest` binds:

- one source family and one snapshot ID/fingerprint;
- the complete `SpatialAdmissionReport` from MAN-07;
- the matching source-specific freshness evaluation where that source has a freshness policy;
- publication class, licence ID/URI, and sorted attribution lines;
- the requested product mode and visibility; and
- the synthetic marker where applicable.

DfT, WebTRIS, and TfGM layers must retain the reviewed OGL v3 URI. Synthetic layers must use the
exact “not observed Manchester data” attribution. A private snapshot may render locally but cannot
be exported publicly. `metadata_only` likewise grants no point export.

## Deterministic availability

The service gives every layer one status and reason:

| Condition | Status | Reason |
|---|---|---|
| Snapshot identity absent | unavailable | `snapshot_unavailable` |
| No spatial point admitted | unavailable | `spatial_admission_unavailable` |
| Freshness evaluation unavailable | unavailable | `freshness_unavailable` |
| Accepted cached evidence is stale | partial and visible | `stale_cached_evidence` |
| Some spatial points excluded | partial | `spatial_admission_partial` |
| All prerequisites pass | available | `ready` |

Only admitted spatial results become `ManchesterMapPoint` values. Point coordinates are preserved
exactly, bounds are recomputed from the rendered inventory, and spatial inputs reconcile to
rendered plus excluded points. Missing or unadmitted coordinates never reach the payload.

## Offline and interpretation boundaries

- `basemap_provider` is always `None`, as required by ADR-056.
- `external_network_required` is always false.
- Source-specific symbols, legend text, and accessible descriptions accompany colour so colour is
  never the only distinction.
- Stale layers remain visible with `stale_badge_visible=true`; stale never becomes fresh or zero.
- Layers preserve their own geographic scope. A scene cannot claim equal coverage or compute
  cross-scope totals.
- Scene composition unions visible attribution lines exactly and does not fuse records.
- Points never claim map matching, identity joining, road occupancy, continuity, or movement.
- BODS point admission and display do not establish Bee Network membership.

## Usage

```python
from traffictwin.integration.manchester import (
    MapLayerRequest,
    OGL_V3_URI,
    build_map_layer,
    build_map_scene,
)

signals = build_map_layer(
    MapLayerRequest(
        layer_id="tfgm-signals",
        title="Traffic signals",
        mode="latest_available",
        source="tfgm_signals",
        snapshot_id=accepted_snapshot.snapshot_id,
        snapshot_fingerprint=accepted_snapshot.fingerprint(),
        spatial_report=signal_spatial_report,
        freshness=signal_freshness,
        publication_class=accepted_snapshot.publication_class,
        licence_id=accepted_snapshot.licence_id,
        licence_uri=OGL_V3_URI,
        attribution_lines=(accepted_snapshot.attribution_text,),
        synthetic=accepted_snapshot.synthetic,
    )
)
scene = build_map_scene("latest_available", (signals,))
```

The UI should render `scene.attributions`, `layer.style`, `layer.reason`, freshness state, snapshot
identity, reconciliation counts, and source scope directly rather than reconstructing them.
Historical/latest scenes reach the UI only through the
[bounded scene-publication service](manchester_scene_publication.md); constructing a scene in
memory does not write a file or make a source accepted.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_manchester_map_layers.py
.venv/bin/ruff check \
  src/traffictwin/integration/manchester/map_layers.py \
  tests/unit/test_manchester_map_layers.py
.venv/bin/mypy --strict \
  src/traffictwin/integration/manchester/map_layers.py \
  tests/unit/test_manchester_map_layers.py
```

The suite covers available, partial, stale, unavailable, private, hidden, and multi-layer scenes;
exact point/bounds/count reconciliation; source/freshness mismatch; OGL and synthetic attribution;
accessible fixed styles; attribution union; duplicate/mode refusal; mutation resistance; and strict
deterministic round trips.

## Evidence basis

- [TrafficTwin v0.7 design](../traffictwin-design-v0_7.md), §§10–12, 20–22 and Appendix A
- [ADR-056: Manchester map rendering, offline mode and attribution](../decisions/ADR-056-manchester-map-rendering-and-attribution.md)
- [MAN-07 spatial admission](manchester_spatial_admission.md)

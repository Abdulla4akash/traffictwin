# Manchester historical/latest scene publication

This candidate `MAN-08` service converts explicit, already-validated map-layer requests into the
fixed local scene files consumed by Manchester Operations. It performs no acquisition, parsing,
projection, source joining, metric calculation, simulator execution, or network access. Building a
scene therefore cannot make an unavailable source available.

## Fixed outputs

`ManchesterScenePublicationRequest.mode` admits only two values:

| Mode | Fixed v0.7 workspace path |
| --- | --- |
| `historical_replay` | `manchester/scenes/historical_replay.json` |
| `latest_available` | `manchester/scenes/latest_available.json` |

Live BODS positions continue through the explicit
[controlled live workflow](manchester_bods_live.md), which now reuses the same atomic file boundary
for `manchester/scenes/live_vehicles.json`. No request model exposes an arbitrary destination,
host, URL, query, credential, parser, or publication class.

## Use

Construct one or more sorted, uniquely identified `MapLayerRequest` values using admitted
[spatial evidence](manchester_spatial_admission.md), explicit freshness, a snapshot fingerprint,
and the correct licence/attribution evidence. Then publish them:

```python
from traffictwin.integration.manchester import (
    ManchesterScenePublicationRequest,
    publish_historical_scene,
)

publication_request = ManchesterScenePublicationRequest(
    mode="latest_available",
    layer_requests=(validated_layer_request,),
)
receipt = publish_historical_scene(v07_workspace, publication_request)
```

The returned `ManchesterScenePublicationReceipt` embeds and binds the request, deterministically
derived scene, canonical file hash and size, layer reconciliation, scene status, and private-layer
flag. Reloading the receipt re-derives those values; changed evidence is rejected rather than
trusted. The [Manchester Operations page](manchester_operations_ui.md) then reads the fixed scene
file on an ordinary offline rerun.

## Safety and truth boundaries

- The destination must be an initialized isolated v0.7 workspace.
- Layer IDs must be sorted and unique, and every layer must match the requested scene mode.
- Historical/latest publication refuses BODS vehicle-position layers; those require the explicit
  credential-gated live workflow.
- The complete canonical scene is limited to 8 MiB and validated before publication.
- Scene directories and targets cannot be symlinks or escape the resolved workspace.
- A mode-`0600` temporary file is flushed and atomically replaces the fixed target only after all
  checks pass. A failed replacement leaves the previous scene unchanged.
- Private layers remain locally renderable but are never public-exportable. Publication neither
  changes nor infers a layer's licence, freshness, scope, source truth, or scientific status.
- Layers remain separate. The service performs no source fusion, cross-scope totals, interpolation,
  resampling, or missing-as-zero substitution.

Synthetic layer requests are supported only when their evidence is explicitly synthetic. A
synthetic scene demonstrates the software path; it is not real Manchester evidence.

## Current limit

This completes the deterministic local publication path for historical and latest scenes, but it
does not by itself accept any real source. Real DfT, WebTRIS, TfGM, Randy, or BODS content must first
pass its own acquisition/replay, parser, projection, freshness, spatial, licence, and Gate B
requirements. `MAN-08` therefore remains planned until those end-to-end acceptance gates and the
remaining browser/accessibility checks pass.

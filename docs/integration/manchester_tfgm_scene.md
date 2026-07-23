# TfGM accepted snapshot to latest map scene

This candidate bridge closes the local software path from one accepted `MAN-04` TfGM traffic-signal
snapshot to a private `MAN-08` `latest_available` scene. It is explicit and offline: it performs no
download, retry, background refresh, network access, or source discovery.

The layer represents **static traffic-signal locations only**. It provides no phase, timing, queue,
count, incident, live state, signal programme, or traffic-flow evidence. Retrieval and evaluation
times do not become observation times.

## Workflow

`build_tfgm_signal_layer` performs the following fixed sequence:

1. verify that the target is an initialized isolated v0.7 workspace;
2. reload and internally validate the supplied `TfgmAcquisitionResult`;
3. reopen the accepted immutable snapshot and reconcile its stored receipt;
4. re-read and hash the preserved ZIP through the snapshot service;
5. re-run the bounded ZIP reader and reconcile the complete inventory plus selected CSV/OGL
   members;
6. re-run the exact MAN-04 CSV parser and require its fingerprint, status, warnings, and counts to
   reproduce the acquisition receipt;
7. apply MAN-07 dual-coordinate spatial admission to every accepted signal record; and
8. build a private, attributed, no-basemap MAN-08 layer request with complete counts.

The returned `TfgmSignalLayerBuild` retains the acquisition, parser report, spatial report, layer
request, and a small typed summary in memory. `publish_tfgm_latest_scene` then delegates to the
[bounded scene-publication service](manchester_scene_publication.md):

```python
from traffictwin.integration.manchester import publish_tfgm_latest_scene

result = publish_tfgm_latest_scene(
    v07_workspace,
    accepted_tfgm_acquisition,
    evaluated_at_utc=explicit_utc_time,
)
```

Optional additional `MapLayerRequest` values remain distinct scene layers. The bridge sorts them by
layer ID and the publication contract rejects duplicates, mode mismatches, source fusion, and
cross-scope totals.

## Publication and licence boundary

The complete acquired TfGM ZIP and the generated local scene remain `private`; public export is
false. The map layer carries the reviewed OGL v3 URI and the exact 2026 attribution shipped in the
audited ZIP. This local rendering decision does not grant broader hosting or redistribution rights.
The separate reviewed three-row derived sample is not created or relabelled by this workflow.

## Failure behaviour

Invalid workspaces, unsafe or changed accepted files, receipt/inventory/member drift, parser drift,
rejected evidence, failed spatial admission, duplicate scene layers, and unsafe publication all
fail closed with typed errors. A publication failure retains the prior latest scene. The workflow
never edits the raw ZIP, parser records, spatial evidence, or acquisition receipt.

## Verification and current limit

The focused offline suite uses an injected synthetic three-row archive and covers the complete
build/publication path, private/static semantics, layer separation, no-network replay, invalid
workspace, accepted-byte drift, parser-fingerprint drift, duplicate refusal, and typed-summary
mutation. It does not perform a real TfGM network acquisition. The code can consume a non-synthetic
receipt only when the acquisition boundary has already admitted the exact audited official hashes;
real Gate B acceptance is still outstanding, so `MAN-04` and `MAN-08` remain planned.

See also the [controlled TfGM acquisition](manchester_tfgm_acquisition.md),
[TfGM parser contract](manchester_tfgm_signal_adapter.md), and
[MAN-07 spatial admission](manchester_spatial_admission.md).

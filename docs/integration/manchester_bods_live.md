# Controlled BODS live-bus scene workflow

Status: **candidate vertical-slice evidence — `MAN-05`, `MAN-07`, and `MAN-08` remain `planned`**

`traffictwin.integration.manchester.bods_live` turns one explicitly requested BODS SIRI-VM
acquisition into the fixed local `live_vehicles` map scene. It composes existing, deterministic
Manchester services; it does not add a second HTTP, XML, privacy, spatial, freshness, or map-layer
implementation.

## Operator contract

The caller supplies:

- a marked, isolated v0.7 workspace;
- one explicit `BodsBoundingBox` in WGS84 longitude/latitude coordinates; and
- a BODS API key as a transient function argument.

There is no hard-coded Manchester boundary and no background polling. The Streamlit page calls
`refresh_bods_live_scene` only after the enabled **Fetch latest buses** form is submitted. Real
acquisition cannot inject a mock HTTP client or clock; those seams are restricted to clearly
labelled synthetic tests by the underlying MAN-05 boundary.

## Deterministic workflow

1. Validate the v0.7 workspace marker before transport.
2. Build the fixed one-member, 16 MiB-bounded `BodsAcquisitionRequest`.
3. Run the [controlled MAN-05 acquisition](manchester_bods_acquisition.md), which quarantines the
   exact private response before parsing and promotes only admitted evidence.
4. Re-read the accepted raw member using the bounded member reader, apply the same bounded
   content-decoding contract recorded by acquisition, and run the existing SIRI-VM parser at the
   acquisition receipt's exact evaluation time and bounding box.
5. Reconcile parser fingerprint, source identity, evidence class, scope, and every accepted/live/
   stale/synthetic count against the acquisition receipt.
6. Convert privacy-safe observations through MAN-07 spatial admission, split them into live, stale,
   historical, or synthetic freshness layers, and build the MAN-08 scene.
7. Canonicalise the scene and atomically replace only
   `manchester/scenes/live_vehicles.json` with mode `0600` after size and path checks.

The returned `BodsLiveRefreshSummary` contains fingerprints and reconciled counts only. It declares
`road_traffic_live_available=False` and `public_export_available=False`; it cannot represent those
claims as available. The UI stores only this secret-free canonical summary in session state.

## Failure and privacy behavior

- An invalid/unmarked workspace fails before any request.
- A failed fetch, unsafe XML, unadmitted warning, evidence drift, scope mismatch, or freshness
  mismatch cannot publish a scene.
- Scene publication refuses empty or over-8-MiB payloads, symlinked/escaped targets, and non-file
  destinations.
- Publication uses a same-directory temporary file, flush, `fsync`, permission `0600`, and atomic
  `os.replace`; failure preserves the prior scene.
- BODS `VehicleRef` values have already been replaced with snapshot-scoped privacy-safe tokens by
  the MAN-05 parser. The API key is absent from all models and written artifacts.
- Transit positions are never presented as general road traffic, volume, congestion, complete
  fleet coverage, or verified Bee Network membership.

## Focused verification

`tests/unit/test_manchester_bods_live.py` proves a single synthetic request publishes a validated
private scene that the UI loader can read; the credential is absent from every workspace artifact;
an unmarked workspace makes zero transport calls; report drift is rejected; and publication
failure preserves the prior scene. `tests/ui/test_manchester_operations.py` proves the form remains
disabled without a valid v0.7 workspace and environment credential and that bounding boxes are
explicitly validated.

No real BODS request is part of automated tests. A controlled operator-triggered real-source probe
passed on 23 July 2026 and is recorded in
[the BODS Gate-B probe](manchester_bods_gate_b_probe.md). The live vertical slice works locally,
but `MAN-05`, `MAN-07`, and `MAN-08` remain planned until the residual privacy, retention,
membership, terms, and complete Gate-B acceptance conditions are reconciled.

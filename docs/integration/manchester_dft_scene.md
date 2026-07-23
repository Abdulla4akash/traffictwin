# DfT accepted count points to Manchester map scenes

This offline bridge turns an already accepted `MAN-02` DfT **count-point reference** snapshot into
one source-separated `MAN-08` Manchester-local-authority map layer. It supports local
`historical_replay` and `latest_available` scene files and performs no download, refresh, source
discovery, map matching, raw-count conversion, or cross-source join.

The layer is survey-infrastructure reference evidence. It contains no raw survey-hour values, AADF
estimates, vehicle-class totals, observation timestamps, or live road state. Retrieval and
evaluation times do not become observation time, and a latest-available scene means only the latest
accepted local reference snapshot—not live traffic.

## Build workflow

`build_dft_count_point_layer` performs the following fixed sequence:

1. require an initialized isolated v0.7 workspace;
2. reload and internally validate the supplied `DftAcquisitionResult`;
3. refuse `raw_counts` and `aadf` products rather than relabel their measurements as references;
4. re-verify the immutable accepted snapshot, manifest, page inventory, hashes, licence,
   publication class, evidence class, and acquisition-receipt binding;
5. re-read every exact accepted JSON page through the shared snapshot boundary;
6. re-run the MAN-02 count-point parser and require its fingerprint, status, and counts to reproduce
   the acquisition result;
7. refuse multiple accepted rows for one count-point identity rather than selecting an arbitrary
   AADF year;
8. apply MAN-07 dual-coordinate admission to every accepted reference record; and
9. build one attributed MAN-08 point layer with complete admitted/excluded reconciliation.

```python
from traffictwin.integration.manchester import build_dft_count_point_layer

built = build_dft_count_point_layer(
    v07_workspace,
    accepted_dft_count_point_acquisition,
    mode="historical_replay",
    evaluated_at_utc=explicit_utc_time,
)
```

Published EPSG:27700 and WGS84 coordinates must satisfy the frozen MAN-07 agreement tolerance.
Records that fail coordinate admission remain typed exclusions. A mixture of admitted and excluded
records yields a partial layer; no record is silently corrected from visual proximity.

## Scene publication

`publish_dft_count_point_scene` composes the verified DfT layer with any explicit additional
same-mode layer requests and delegates to the
[bounded scene-publication service](manchester_scene_publication.md):

```python
from traffictwin.integration.manchester import publish_dft_count_point_scene

result = publish_dft_count_point_scene(
    v07_workspace,
    accepted_dft_count_point_acquisition,
    mode="latest_available",
    evaluated_at_utc=explicit_utc_time,
)
```

Every source remains a separate scene layer with its own scope, attribution, freshness label, and
publication class. The scene exposes no cross-scope total, performs no source fusion, and makes no
identity inference from nearby points. Public-export availability follows the accepted snapshot's
reviewed publication class; the bridge cannot upgrade it.

## Why measurements are not mapped here

DfT raw counts are historical neutral-day survey observations whose `hour` timezone remains
unresolved, while AADF rows are annual statistical estimates rather than instantaneous demand.
Both have their own parser and projection contracts. Mapping those measurements requires an
explicit interval/site/direction/measure selection and, for raw rows, a reviewed time-basis
decision. Until those prerequisites pass, only the count-point reference product can enter this
layer.

## Failure and verification

Invalid workspaces, measurement-product relabelling, unsafe or changed accepted bytes,
receipt/manifest drift, parser drift, duplicate point identity, invalid scene composition, and
unsafe publication fail closed with typed errors. Spatial mismatch remains visible as exclusion;
it is not a bridge failure. Atomic publication preserves the prior complete scene on failure.

The focused suite is entirely offline and uses injected, explicitly synthetic DfT responses. It
covers build and both publication modes, UI reload, source separation, no-network replay, workspace
and byte-integrity refusals, parser/publication binding, product refusal, duplicate identity,
available/partial/unavailable spatial outcomes, publication-class preservation, and scientific
truth-field mutation. No real DfT acceptance run is claimed; `MAN-02`, `MAN-07`, and `MAN-08`
remain planned.

See also the [controlled DfT acquisition](manchester_dft_acquisition.md),
[DfT parser contract](manchester_dft_adapter.md),
[MAN-07 spatial admission](manchester_spatial_admission.md), and
[Manchester source Gate-A audit](manchester-source-gate-a-audit-v0_7.md).

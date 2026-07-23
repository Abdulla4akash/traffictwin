# WebTRIS accepted sites to Manchester map scenes

This offline bridge turns an already accepted `MAN-03` WebTRIS **site-reference** snapshot into one
source-separated `MAN-08` strategic-road detector layer. It supports the local
`historical_replay` and `latest_available` scene files. It performs no download, refresh, source
discovery, site search, map matching, or cross-source join.

The point is infrastructure reference evidence. It is not a traffic observation. Daily interval
counts and quality reports are separate WebTRIS products and this bridge never attaches them to a
site merely because their caller-supplied site ID looks equal. The source's undeclared timestamp
basis is not promoted to UTC; retrieval and evaluation time do not become observation time; and the
layer cannot claim live Manchester road traffic.

## One-site build

`build_webtris_site_layer` performs this fixed sequence:

1. require an initialized isolated v0.7 workspace;
2. reload and validate the supplied `WebtrisAcquisitionResult`;
3. refuse every product except `site`;
4. re-verify the immutable accepted snapshot, manifest, member inventory, hashes, licence,
   publication class, evidence class, and acquisition receipt binding;
5. re-run the existing MAN-03 parser over the preserved `site/site.json` member;
6. require the parser fingerprint, status, and counts to reproduce the acquisition result;
7. require exactly one returned record and require its site ID to equal the ID selected by the
   audited `/api/v1.0/sites/{id}` endpoint request;
8. bind MAN-07 strategic-approach scope to the exact acquisition-request fingerprint;
9. apply deterministic spatial admission; and
10. build one attributed site-specific MAN-08 layer request.

```python
from traffictwin.integration.manchester import build_webtris_site_layer

built = build_webtris_site_layer(
    v07_workspace,
    accepted_webtris_site_acquisition,
    mode="historical_replay",
    evaluated_at_utc=explicit_utc_time,
)
```

The layer ID is `webtris-site-<selected-id>`, so independently acquired selected sites can remain
distinct. An inactive source record is retained in the reconciliation as a typed spatial exclusion;
it yields an unavailable layer rather than silently disappearing.

## Scene publication

`publish_webtris_site_scene` accepts one or more accepted site acquisitions, builds each one
independently, sorts the site-specific layers, refuses duplicate selected IDs, composes any explicit
additional layer requests without fusion, and delegates atomic writing to the
[bounded scene-publication service](manchester_scene_publication.md).

```python
from traffictwin.integration.manchester import publish_webtris_site_scene

result = publish_webtris_site_scene(
    v07_workspace,
    (accepted_site_34, accepted_site_35),
    mode="latest_available",
    evaluated_at_utc=explicit_utc_time,
)
```

The resulting scene retains separate source layers, scopes, attributions, and publication classes.
It exposes no cross-scope total and makes no inference from visual proximity. Public-export
availability follows the accepted snapshot's reviewed publication class; this orchestration step
does not upgrade it.

## Why daily values are not mapped here

The WebTRIS daily report contains 15-minute strategic-road observations but no coordinates, and its
time strings have no documented timezone semantics (`GA-WT-1`). The site endpoint supplies
coordinates but no daily measurements. Combining those products therefore needs a separate,
explicit, versioned join contract that proves site identity and preserves the undeclared time basis.
Until that contract is accepted, daily report and quality snapshots remain available to historical
table/chart and temporal-profile workflows but cannot be relabelled as this point layer.

## Failure and verification

Invalid workspaces, daily-product relabelling, unsafe or changed accepted bytes, receipt/manifest
drift, parser drift, selected/returned site mismatch, duplicate sites, and invalid scene composition
fail closed with typed errors. Publication uses a fixed local path and retains the prior complete
scene if a replacement fails.

The focused test suite is entirely offline and uses injected, explicitly synthetic WebTRIS
responses. It covers build and both publication modes, UI reload, source separation, no-network
replay, workspace and byte-integrity refusals, parser binding, endpoint/response identity binding,
inactive-site reconciliation, publication-class preservation, duplicate refusal, and scientific
truth-field mutation. No real WebTRIS acceptance run is claimed; `MAN-03` and `MAN-08` remain
planned.

See also the [controlled WebTRIS acquisition](manchester_webtris_acquisition.md),
[WebTRIS parser contract](manchester_webtris_adapter.md),
[MAN-07 spatial admission](manchester_spatial_admission.md), and
[Manchester source Gate-A audit](manchester-source-gate-a-audit-v0_7.md).

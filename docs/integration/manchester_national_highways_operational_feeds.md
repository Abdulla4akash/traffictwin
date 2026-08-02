# National Highways operational REST feeds

Status: **bounded implementation and one real-source acceptance case complete; the wider
`MAN-01`, `MAN-07`, and `MAN-08` capabilities remain planned**

Accessed: 24 July 2026

This extension replaces the earlier assumption that a new National Highways integration required
an NTIS callback. The current developer service is a key-authenticated HTTPS REST API. TrafficTwin
implements three products independently:

| Product | Exact path | Admitted query | Evidence meaning |
|---|---|---|---|
| Road and Lane Closures v2 | `/roads/v2.0/closures` | `closureType`, UTC-naive `startDateTime`, `endDateTime` | Planned or unplanned closures/incidents represented in active VSS information |
| Speed Managed Areas v1 | `/sma/v1.0/speedManagedAreas` | `speedRestrictionType`, UTC-naive `startDateTime`, `endDateTime` | Imposed temporary limits; not measured vehicle speed |
| Digital VMS v1 | `/dvms/v1.0/vms` | `bBox` | Sign working state, location, message information type, setting reason, and setting time |

All calls are pinned to `https://api.data.nationalhighways.co.uk`. The only secret input is the
`Ocp-Apim-Subscription-Key` request header. The endpoint policy fixes
`X-Response-MediaType: application/json` and `X-Data-Format: DATEXII`; callers cannot select a URL,
host, path, arbitrary query, parser, output class, or request header.

## Source and licence findings

The [official FAQ](https://developer.data.nationalhighways.co.uk/faq) says anyone may register and
subscribe, the feeds concern the Strategic Road Network, and each subscription key is limited to
10 calls per minute. It also states the Road and Lane Closures v2 and Speed Managed Areas v1
limitations: both depend on active Variable Signs and Signals information, so neither is complete
road coverage. TrafficTwin uses exactly three calls for each all-product refresh and enforces a
minimum minute between attempts. When a validated real workspace and process-only key are present,
one process-local daemon refreshes all three products every five minutes after the first app
session starts. This is 0.6 calls per minute on average and remains below the documented provider
limit.

The [current terms](https://developer.data.nationalhighways.co.uk/terms) state that data is
currently supplied without charge, allow copying/adaptation/commercial and non-commercial use
subject to the licence, and require the exact attribution:

> Powered by National Highways’ Transport Data Feeds

The terms may change and access may be suspended. TrafficTwin therefore records the access date,
terms URL, exact attribution, and keeps these source responses `private` pending release-level
publication review. No provider logo is included.

## Frozen observed schemas

All three successful responses have one `D2Payload` root and a source UTC `publicationTime`.
Closures and speed use `SituationPublication`, `situation[]`, and `situationRecord[]`; the exact
record wrappers are `sitRoadOrCarriagewayOrLaneManagement` and `sitSpeedManagement`. Their source
line geometry is a DATEX/GML `posList` labelled `ESPG::4326` in the observed response (the provider
spelling is deliberately accepted alongside `EPSG::4326`). Coordinates are latitude/longitude
pairs. Speed values are source km/h temporary limits, including the documented zero/suspended
case; they are never presented as observed speed.

Digital VMS uses `vmsPublication`, `vmsControllerStatus[]`, nested `vmsStatus[]`, and source WGS84
point coordinates. The observed message object exposes information type, setter, setting reason,
and `timeLastSet`; it does not expose literal displayed sign text. TrafficTwin makes that absence
structural (`literal_display_text_available=false`) rather than inventing a message.

Unknown top-level shape, wrong feed type, duplicate JSON keys, unbounded record counts, invalid
timestamps, invalid coordinates, conflicting identifiers, unsupported transfer encoding, or
schema-wrapper drift fails closed. Missing coordinates and points outside the study envelope are
separately reconciled rather than treated as zero events.

## Acquisition, replay, and stale behaviour

The shared bounded transport preserves the exact HTTP entity in quarantine before parsing. The
production service returned gzip entities in the acceptance case, so the parser reads a separately
bounded decoded JSON payload only after raw hash verification. Promotion is atomic and new-only.
Accepted snapshots retain the raw-entity hash, decoded parser/report fingerprint, redacted request
identity, source publication time, retrieval time, licence, and validation state. Offline replay
re-verifies the snapshot and reproduces the parser output without network access.

The broad initial study envelope is latitude `53.30–53.70`, longitude `−2.60–−1.90`. It is a
caller-declared source filter, not the separately packaged ONS Manchester or Greater Manchester
display boundary and not a complete-coverage claim. Linear records
enter the map only when an actual source vertex is inside the envelope; TrafficTwin displays one
deterministically selected in-envelope source vertex and retains the complete source geometry in
the immutable raw snapshot.

Freshness comes from `D2Payload.publicationTime`, never retrieval time. A self-imposed ten-minute
display threshold classifies an accepted operational snapshot `near_live`; after that it is
`stale`. This threshold is not a provider cadence or SLA. The five-minute worker normally replaces
the accepted overlay before that threshold. If a provider, transport, schema, workspace or
publication check fails, the previous accepted overlay remains available and is reclassified
stale; automatic refresh never hides that failure or changes another source.

The worker is process-local and idempotent per workspace. It starts only when
`TRAFFICTWIN_WORKSPACE_PATH` and `NATIONAL_HIGHWAYS_API_KEY` are configured, retains the key only in
process memory, records every automatic receipt with `automatic_polling_performed=true`, and stops
with the Streamlit process. It does not poll BODS, WebTRIS, DfT or TfGM. A 30-second local page
watcher notices a newly published overlay and rerenders Manchester Operations without making its
own network request. Manual refresh remains a fallback and shares the same file lock and one-minute
guard.

## Real-source acceptance

The machine-readable acceptance record is
[`national_highways_operational_acceptance_20260724.json`](evidence/national_highways_operational_acceptance_20260724.json).
One isolated temporary-workspace run completed all three requests, promoted all three private raw
snapshots, created both Latest-available and Live-vehicles overlays, and reconciled 548 admitted
in-envelope records: 7 closures/incidents, 60 temporary restrictions, and 481 unique VMS statuses.
The VMS source supplied 533 items; 52 exact logical duplicates were collapsed and recorded, so its
complete equation is `533 = 481 + 52`. The temporary workspace was removed after verification; no
key or real response was committed.

This accepts the bounded operational slice, not the complete capability catalogue. `MAN-01`,
`MAN-07`, and `MAN-08` still encompass other sources, release/publication review, manual
accessibility/participant acceptance, and full project-level reconciliation, so their
capability state remains `planned`.

## Use

Supply the credential only at process start:

```bash
export NATIONAL_HIGHWAYS_API_KEY='your subscription key'
export TRAFFICTWIN_WORKSPACE_PATH='/absolute/path/to/workspace-v0.7'
uv run streamlit run src/traffictwin/ui/app.py
```

Automatic refresh defaults to 300 seconds. The optional
`TRAFFICTWIN_NATIONAL_HIGHWAYS_AUTO_REFRESH_SECONDS` setting accepts 60–540 seconds; `off` or `0`
disables the daemon. Restart the server to apply an interval or key change. Open **Manchester
Operations**, choose **Latest available** or **Live vehicles**, and expand **National Highways
operational feeds** to see secret-free worker status. The manual planned/unplanned action remains
available. Ordinary page reruns are local; the daemon alone performs scheduled requests. The map
exposes three independently toggleable layers and preserves the required attribution.

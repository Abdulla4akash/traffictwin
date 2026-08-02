# Manchester live-feature matrix

This matrix separates software that now exists from claims that still require an external source,
provider/governance decision, or formal v0.7 gate acceptance. Code presence does not change any
`MAN-*` capability from `planned`.

| Live feature | Current truth | Evidence / limit |
|---|---|---|
| Explicit BODS bus-position fetch | Built and exercised with a real private response | One bounded authenticated request, quarantine-before-parse, accepted replay, privacy-safe local scene |
| Source-time live/stale classification | Built | Exact BODS `RecordedAtTime`, `ValidUntilTime`, and 60-second policy; retrieval time cannot upgrade freshness |
| Bee Network filtering | Built for five verified exact `OperatorRef` values, with a pending-candidate review | `BNDB`, `BNFM`, `BNGN`, `BNML`, `BNSM`; a later accepted `BNVB` observation opens review but cannot auto-activate policy; non-matches remain other-or-unknown |
| Live bus map, source cards, scope/freshness filters | Built locally | Private bus/transit layers only; no basemap network request and no public export |
| Cached outage/age fallback | Built | Display-time projection changes expired non-synthetic BODS layers to **stale cached** without mutating accepted evidence |
| Request-frequency and concurrency control | Built | Manual action only, one OS-locked refresh at a time, minimum 60 seconds between attempts |
| Aggregate live history | Built | Private 24-hour/240-entry history of Bee/other/live/stale counts; no raw positions or vehicle identifiers |
| Raw private snapshot retention control | Built as a precautionary software control | Read-only preview, 24-hour/240-family default, active/newest protection, exact confirmation, paired accepted/quarantine cleanup; legal approval and secure erasure remain unavailable |
| National Highways closures and incidents | Built and exercised with a real private response | Key-authenticated Road and Lane Closures v2 REST request; 7 in-envelope records in the 24 July 2026 acceptance case |
| National Highways temporary restrictions | Built and exercised with a real private response | Speed Managed Areas v1; 60 in-envelope imposed-limit records; these are restrictions, not measured vehicle speeds |
| National Highways digital VMS | Built and exercised with a real private response | Digital VMS v1; 481 unique in-envelope statuses after 52 exact duplicates collapsed; metadata does not contain literal displayed sign text |
| National Highways source-time freshness and outage fallback | Built | DATEX II `publicationTime`, self-imposed ten-minute near-live ceiling, stale cached fallback, and previous-overlay preservation after failed refresh |
| Combined BODS and National Highways Manchester map | Built locally | Source-separated private layers; buses remain `live_vehicle`, operational road events remain `near_live`/`stale`; no source fusion or cross-source total |
| Official Manchester geographic context | Built | Hash-pinned December 2025 ONS Manchester and Greater Manchester display boundaries with required ONS/OS attribution; no basemap request and no scientific clipping/coverage claim |
| National Highways request-frequency and history control | Built | Explicit three-call refresh only, one OS-locked run at a time, minimum 60 seconds, and 24-hour/240-entry source-separated aggregate history |
| Local live-status metadata download | Built | Downloadable source state, timestamps, attribution, and aggregate counts only; coordinates, IDs, credentials, raw snapshots, public metadata hosting, and public live-scene hosting are structurally refused |
| Desktop/mobile light/dark browser regression | Built and passed | 35 routes × two viewports × two themes = 140 screenshots, zero actionable semantic findings; this is automated evidence, not WCAG or participant acceptance |
| General live Manchester road counts/speeds | **Unavailable** | No authorised, audited city-road private-vehicle feed has been supplied; BODS buses cannot substitute for road traffic |
| WebTRIS `near_live` | **Refused after real-source probe** | The official cadence is normally about one month in arrears. On 24 July 2026 the 23 July report returned HTTP 204, while 24 June returned a complete 96-interval historical day and passed the controlled workflow; source timezone also remains undocumented (`GA-WT-1`) |
| Continuous traffic flow, measured speed, density, or congestion | **Unavailable** | The integrated National Highways products are operational-event/sign feeds, not continuous telemetry; WebTRIS remains historical |
| Live traffic-signal phase/timing state | **Unavailable** | TfGM source is a dated signal-location reference only; no phase, timing, queue, or controller-state feed exists |
| Complete Bee Network fleet/service claim | **Unavailable** | `BNVB`, branding-versus-franchise scope, NOC/schedule reference rights, and complete feed coverage remain unresolved |
| Public live-data hosting/export | **Unavailable** | A local metadata-only status download contains no positions or identifiers but does not accept public hosting. General BODS reuse/publication and API registration are documented; identifier privacy/retention, project public-output approval, National Highways release review, reference-data licences, and complete gate acceptance still block public metadata/raw/scene hosting |
| Always-on background source scheduler | Deliberately out of v0.7 scope | Streamlit reruns read local state only; a daemon/cloud scheduler would require a separate deployment/governance design |

## Current acceptance position

The buildable local live path now includes live BODS transit positions and three current National
Highways operational REST products. Each path fetches, validates, snapshots, replays, classifies,
maps, ages to stale, rate-limits, and retains aggregate-only history without background polling.
The National Highways slice completed one isolated real-source acceptance run on 24 July 2026 with
548 admitted records. It gives useful near-live closures/incidents, imposed temporary restrictions,
and VMS status—not continuous vehicle flow, measured traffic speed, complete city-road coverage,
or traffic-signal phases. WebTRIS remains useful historical evidence and is explicitly refused as
near-live. Remaining Bee policy/licence decisions, source-wide retention/publication decisions,
manual keyboard/screen-reader/contrast/participant acceptance, and formal capability
reconciliation remain open. `MAN-01`, `MAN-03`, `MAN-05`, `MAN-07`, and `MAN-08` therefore remain
`planned`, while the bounded operational slice is honestly recorded as built.

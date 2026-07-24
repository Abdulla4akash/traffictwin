# Manchester live-feature matrix

This matrix separates software that now exists from claims that still require an external source,
provider/governance decision, or formal v0.7 gate acceptance. Code presence does not change any
`MAN-*` capability from `planned`.

| Live feature | Current truth | Evidence / limit |
|---|---|---|
| Explicit BODS bus-position fetch | Built and exercised with a real private response | One bounded authenticated request, quarantine-before-parse, accepted replay, privacy-safe local scene |
| Source-time live/stale classification | Built | Exact BODS `RecordedAtTime`, `ValidUntilTime`, and 60-second policy; retrieval time cannot upgrade freshness |
| Bee Network filtering | Built for five verified exact `OperatorRef` values | `BNDB`, `BNFM`, `BNGN`, `BNML`, `BNSM`; `BNVB` and non-matches remain pending/other-or-unknown |
| Live bus map, source cards, scope/freshness filters | Built locally | Private bus/transit layers only; no basemap network request and no public export |
| Cached outage/age fallback | Built | Display-time projection changes expired non-synthetic BODS layers to **stale cached** without mutating accepted evidence |
| Request-frequency and concurrency control | Built | Manual action only, one OS-locked refresh at a time, minimum 60 seconds between attempts |
| Aggregate live history | Built | Private 24-hour/240-entry history of Bee/other/live/stale counts; no raw positions or vehicle identifiers |
| Raw private snapshot retention control | Built as a precautionary software control | Read-only preview, 24-hour/240-family default, active/newest protection, exact confirmation, paired accepted/quarantine cleanup; legal approval and secure erasure remain unavailable |
| General live Manchester road counts/speeds | **Unavailable** | No authorised, audited city-road private-vehicle feed has been supplied; BODS buses cannot substitute for road traffic |
| WebTRIS `near_live` | **Refused after real-source probe** | The official cadence is normally about one month in arrears. On 24 July 2026 the 23 July report returned HTTP 204, while 24 June returned a complete 96-interval historical day and passed the controlled workflow; source timezone also remains undocumented (`GA-WT-1`) |
| National Highways NTIS real-time road feed | **Candidate; not integrated** | A separate subscriber-only DATEX II push service exists, but TrafficTwin has no approved subscription, credentials, callback receiver, frozen schema/time contract, retention decision, or real acceptance fixture |
| Live traffic-signal state or incidents | **Unavailable** | TfGM source is a dated signal-location reference only; no phase, timing, queue, incident, or operational-state feed exists |
| Complete Bee Network fleet/service claim | **Unavailable** | `BNVB`, branding-versus-franchise scope, NOC/schedule reference rights, and complete feed coverage remain unresolved |
| Public live-data hosting/export | **Unavailable** | BODS terms, identifier retention/publication basis, reference-data licences, and complete gate acceptance remain open |
| Always-on background source scheduler | Deliberately out of v0.7 scope | Streamlit reruns read local state only; a daemon/cloud scheduler would require a separate deployment/governance design |

## Current acceptance position

The buildable local live-transit path is present: fetch, validate, classify, map, age to stale,
rate-limit, retain aggregate history, and preview private cleanup. The WebTRIS near-live option has
now been tested and rejected rather than left as a speculative UI option; its latest-available
historical path remains useful. True National Highways real-time traffic would be a new NTIS source
boundary, not a WebTRIS status change. It requires provider approval, a secured public callback,
frozen contracts, and real-source acceptance. Remaining Bee identifiers/licences and formal
Gate-B/UI acceptance also remain open. Until then, `MAN-03`, `MAN-05`, `MAN-07`, and `MAN-08`
remain `planned`, and unsupported states remain visibly unavailable.

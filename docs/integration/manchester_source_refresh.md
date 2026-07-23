# Manchester explicit source refresh workflows

Status: **working real-source vertical slices; v0.7 capability acceptance remains gated**

The Manchester Operations page exposes four operator-triggered workflows. Ordinary Streamlit
reruns and **Refresh local evidence** remain offline. There is no background poller, scheduler,
arbitrary URL, or automatic source fusion.

| UI mode | Action | Source truth |
|---|---|---|
| Live vehicles | Fetch latest buses | BODS SIRI-VM transit positions; the only live feed |
| Latest available | Fetch WebTRIS site, report, and quality | One selected National Highways strategic-road site/day; source timezone unresolved |
| Latest available | Fetch TfGM signal locations | Static signal infrastructure references; no operational state |
| Historical replay | Fetch selected DfT rows | Historical survey, count-point, and AADF rows; no live state |

Each workflow reuses the existing bounded transport, quarantine-before-parser, immutable accepted
snapshot, exact parser, spatial admission, and atomic scene-publication boundaries. Scene updates
replace only the same source layer and preserve unrelated source-separated layers. Source record
counts are never added together as one traffic total.

## WebTRIS

`refresh_webtris_site_day` accepts only a numeric site ID and one explicit source date. It first
acquires the site record and uses the source-reported site description as the daily scope name;
the caller cannot invent that binding. It then acquires one bounded 96-row daily report and the
matching quality response. Site geometry updates the latest-available map, while interval values
remain in their own historical chart boundary.

The real service returns gzip-encoded JSON. TrafficTwin preserves the exact compressed HTTP bytes,
decodes them only under the shared bounded gzip policy, records the raw member SHA-256 separately
from the parser-payload SHA-256, and reproduces the same report from accepted storage. Identity
fixtures without HTTP metadata remain identity-encoded for compatibility.

On 23 July 2026, site `34` (`M56/8150A`) and source date `2026-03-01` completed the controlled
workflow: 96 intervals were accepted, eight retained missing measurements, and one quality row was
accepted. The parser retained `LENGTH_TOTAL_MISMATCH` and `MISSING_INTERVAL_MEASUREMENTS` warnings;
neither is hidden or converted to a zero. A request for 22 July 2026 was rejected because the
source did not return a contract-complete site/day. This is expected fail-closed behavior during
the provider's announced 2026 service interruption.

WebTRIS is not labelled live: `GA-WT-1` still blocks UTC promotion, and this source covers the
National Highways strategic-road network rather than all Manchester roads.

## TfGM traffic-signal locations

`refresh_tfgm_signal_locations` uses the one fixed audited TfGM archive endpoint. It accepts no
URL, query, archive policy, or publication-class input. The full ZIP remains private. The latest
scene contains static signal-location points only; phase, timing, queue, incident, traffic-count,
and live-state fields are structurally unavailable.

The 23 July 2026 real-source run matched the audited archive and CSV hashes exactly and admitted
all 2,529 rows with zero spatial exclusions. The run also detected that the archive's required
attribution has two spaces between its two sentences. The frozen literal now retains those exact
shipped bytes instead of silently normalising them.

## DfT historical evidence

`refresh_dft_historical_rows` accepts three positive row identities and issues three Manchester-
scoped, one-row, bounded anonymous requests: raw counts, count-point metadata, and AADF. The raw
count enters the source-specific survey view; the count point supplies the historical map
reference; AADF remains a separately labelled statistical row and is not silently treated as an
observed traffic count.

The controlled 23 July 2026 run for raw-count row `43177`, count-point row `6046`, and AADF row
`9219` accepted and reproduced one row of each type. DfT source hour labels remain local-clock
labels with no invented timezone.

## Failure and storage behavior

- Transport or schema failure never becomes zero traffic or an empty successful scene.
- Raw responses are retained in the isolated v0.7 workspace before parsing.
- A failed scene update leaves the prior scene unchanged.
- Refresh summaries contain no credentials or unrestricted local paths.
- WebTRIS and TfGM provider drift is visible as a typed refusal.
- Public hosting and redistribution remain controlled by each snapshot's publication class.

These real-source runs prove the narrow acquisition-to-local-view paths. They do not resolve
provider SLAs/rate limits, WebTRIS timezone semantics, Bee Network membership, live city-road
incidents, live signal phases, comparison-contract admission, or public-hosting permission. Those
limits keep the encompassing `MAN-*` capability gates planned until integration reconciliation.

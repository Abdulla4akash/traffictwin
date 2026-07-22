# Manchester Source Gate A Audit v0.7

Status: **Gate A audit accepted with scoped downstream blockers; `MAN-01` remains planned**

This document records the v0.7 Gate A source, legal, schema, and dependency audit required by
[the v0.7 design](../traffictwin-design-v0_7.md) (§21, Gate A). It is discovery and decision
evidence only. Lead review corrected the WebTRIS quality and BODS SIRI-VM field contracts and
added the required fixture, publication, freshness, and dependency-version decisions. It does
not implement, accept, or enable any network adapter; every `MAN-*` capability remains `planned`
per
[implementation status](../implementation-status.md). Gate B must still implement and accept
acquisition before `MAN-01` can be reconciled as implemented.

All external facts below were read from official primary sources on **22 July 2026**. Facts that
could not be confirmed on an official page are listed as unresolved blockers with exact reasons,
not filled in from memory. No substantial real dataset was downloaded into or committed to this
repository; the only bulk file opened during the audit was the ~1.2 MB official TfGM
traffic-signals zip, inspected in a temporary directory outside the repository and discarded.

Related Gate A decisions:

- [ADR-054: bounded Manchester acquisition transport and parsing](../decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md)
- [ADR-055: Manchester time basis](../decisions/ADR-055-manchester-time-basis.md)
- [ADR-056: Manchester map rendering and attribution](../decisions/ADR-056-manchester-map-rendering-and-attribution.md)
- [ADR-057: Bee Network membership identifiers](../decisions/ADR-057-bee-network-membership-identifiers.md)

## 1. Source matrix summary

| Source | Endpoint class | Auth | Format | Licence basis (observed) | Time semantics | Snapshot suitability |
|---|---|---|---|---|---|---|
| DfT Road Traffic Statistics | Anonymous JSON API + bulk CSV zips | none | JSON; zipped CSV | OGL v3.0 (site footer on about/downloads/FAQ pages) | Dated historical surveys; `hour` clock ranges with undocumented timezone | High: stable historical records, annual updates |
| National Highways WebTRIS | Anonymous JSON API v1.0 | none | JSON | OGL named on WebTRIS privacy-policy page | 15-minute intervals observed; timezone undocumented | High, but a 3–6 month 2026 service interruption is announced |
| TfGM traffic signals | Anonymous static zip download | none | CSV/GeoJSON/SHP/GPKG/KML/TAB | OGL v3.0 + exact attribution text in dataset | Versioned reference data (no per-record time) | High: small, versioned by content hash + access date |
| DfT BODS SIRI-VM | API key + registered account | account + `api_key` | SIRI-VM XML (DfT 2.0 (Q) profile); GTFS-RT alternative | OGL v3.0 (portal footer); "no license needed" statement | UTC timestamps documented; ~10-second cache | Medium: live feed, no historical service, key handling required |
| Randy/TOS Manchester artifacts (optional) | Local pinned Git evidence only | n/a | NPZ/CSV/XML per v0.6 contract | Written permission only; no repository licence file | Simulation clocks; not wall-clock observations | Already snapshot-audited by `VEC-01`; no new acquisition |

## 2. DfT Road Traffic Statistics

### 2.1 Endpoint and version

- API documentation: <https://roadtraffic.dft.gov.uk/api-documentation> (page states last updated
  19 June 2026). No API version identifier is documented anywhere (confirmed absent).
- Documented endpoints under `https://roadtraffic.dft.gov.uk/api/`: `count-points`, `raw-counts`,
  `average-annual-daily-flow`, `average-annual-daily-flow-by-direction`, `countries`, `regions`,
  `local-authorities`, `local-authority-traffic`, `region-traffic-by-road-type`,
  `region-traffic-by-vehicle-type`. Live anonymous calls to `raw-counts`, `count-points`, and
  `average-annual-daily-flow` succeeded on 2026-07-22.
- Bulk alternative: zipped CSVs on `https://storage.googleapis.com/dft-statistics/road-traffic/…`
  linked from <https://roadtraffic.dft.gov.uk/downloads> (count points 46,754 records; raw counts
  5,269,632 records; AADF 600,551 records; all 2000–2025 at audit time). Note the bulk host is a
  shared multi-tenant object store; any allowlist entry must be path-prefixed
  (`/dft-statistics/road-traffic/`), not host-wide.

### 2.2 Access and authentication

"This API is not authenticated" (api-documentation page). Anonymous access verified in practice.

### 2.3 Request/response format

JSON with a Laravel-style pagination envelope observed live (`current_page`, `per_page`, `total`,
`last_page`, `next_page_url`, `data`, …). Query parameters documented: `page[size]`,
`page[number]`, `fields`, `include`, `sort`, `filter[field]`.

### 2.4 Schema

- Authoritative schema document: "Road Traffic Statistics Metadata" PDF at
  <https://storage.googleapis.com/dft-statistics/road-traffic/all-traffic-data-metadata.pdf>
  (linked from the official downloads page; read in full).
- Raw-count fields (PDF and live API agree): `id`, `count_point_id`, `direction_of_travel`,
  `year`, `count_date`, `hour`, `region_id`, `local_authority_id`, `road_name`, `road_category`,
  `road_type`, `start_junction_road_name`, `end_junction_road_name`, `easting`, `northing`,
  `latitude`, `longitude`, `link_length_km`, `link_length_miles`, plus twelve vehicle-class count
  columns from `pedal_cycles` through `all_motor_vehicles`.
- `hour` is documented as a clock range: "7 represents between 7am and 8am, and 17 represents
  between 5pm and 6pm" (metadata PDF p5). **No timezone is documented** (blocker `GA-DFT-1`).
- `count_date` is a date-only value (live sample `2004-05-21`); it must never be converted into a
  fabricated instant ([ADR-055](../decisions/ADR-055-manchester-time-basis.md)).
- `direction_of_travel` codes: `N`, `S`, `E`, `W`, and `C` = combined (PDF p9). Road categories:
  `PM`, `PA`, `TM`, `TA`, `M`, `MB`, `MCU` (PDF p8).
- AADF records carry `estimation_method` / `estimation_method_detailed`; the PDF warns AADFs from
  different count points must not be added together.
- There is no measured-speed field in any documented raw-count or AADF schema, matching the v0.7
  design's DfT exclusions.

### 2.5 Geographic and modal coverage

Great Britain; every major-road (motorway and A-road) junction-to-junction link has a count
point, minor roads are sampled (about page). `E08000003` is the Manchester local authority in the
North West region. Counts come from ~7,000 annual manual roadside counts and ~300 DfT automatic
counters plus partner counters. Twelve vehicle classes from pedal cycles to six-axle articulated
HGVs.

### 2.6 Observation-time semantics

Manual counts run 07:00–19:00 on "neutral" weekdays (March–October, excluding public and school
holidays; ~110 neutral days per year — about and FAQ pages). A raw count is the vehicles passing
on that specific `count_date`, by direction and hour. AADF is an annual average and is not an
instantaneous or hourly demand value.

### 2.7 Publication cadence

Data published 20 May 2026; "Next data update is planned for summer 2027" (about page, as
displayed on 2026-07-22). Annual cycle.

### 2.8 Rate limits

None stated on the api-documentation, downloads, or FAQ pages (blocker `GA-DFT-2`: absence of a
policy is not proof one does not exist; the adapter must self-impose conservative bounds).

### 2.9 Licence, attribution, retention, redistribution

"All content is available under the Open Government Licence v3.0, except where otherwise stated"
with Crown copyright, on the about, downloads, and FAQ pages, linking the
[official OGL v3.0 text](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
OGL v3.0 requires source acknowledgement using any provider-specified attribution where practical;
the snapshot manifest therefore retains the provider wording, OGL URI, and access date. No
additional retention or redistribution conditions were observed.

### 2.10 Privacy

All documented and observed fields are road/location/count attributes. No personal-data field
exists in the schema; note this is inference from the complete observed schema, not an
affirmative DfT statement.

### 2.11 Outage and failure behaviour

No status page, SLA, or outage documentation found (blocker `GA-DFT-3`). The adapter must treat
unavailability as `unavailable`, never as zero traffic.

### 2.12 Snapshot suitability

High. Records are dated historical survey evidence; the API is unversioned, so each snapshot must
record retrieval time, full request parameters, response hashes, and the pagination envelope
totals to make later revisions detectable.

### 2.13 Manchester page facts (discovery evidence only)

On 2026-07-22, <https://roadtraffic.dft.gov.uk/local-authorities/E08000003> reported 342 count
points, 39,072 raw count records, and a 1993–2025 estimate series. These reconcile with the v0.7
design §5.1 figures and remain discovery evidence, not permanent truths.

### 2.14 What TrafficTwin may and may not claim

May: dated Manchester survey-hour counts by direction and vehicle class; count-point locations;
long-term context series; OGL-attributed reuse.
May not: measured speed (field does not exist); live or continuous coverage; AADF as hourly/SUMO
demand; summed AADFs across count points; any UTC instant for `hour` until `GA-DFT-1` resolves.

## 3. National Highways WebTRIS

### 3.1 Endpoint and version

- API v1.0, all endpoints under `https://webtris.nationalhighways.co.uk/api/v1.0/`; Swagger spec
  at <https://webtris.nationalhighways.co.uk/api/swagger/docs/v1>, UI at
  <https://webtris.nationalhighways.co.uk/api/swagger/ui/index>.
- Resources: `areas`, `sites`, `sitetypes`, `sitetypes/{id}/sites`, `quality/overall`,
  `quality/daily`, `reports/{report_type}` and `reports/{start_date}/to/{end_date}/{report_type}`.
  `report_type` is described only informally as "Daily, Monthly, Annual" — no formal enum
  (blocker `GA-WT-3`).

### 3.2 Access and authentication

Anonymous; the API overview states there is no need to register. No keys.

### 3.3 Request/response format

JSON. Report endpoints require `page` and `page_size` (int32). Request dates use `ddmmyyyy`.
Daily report responses contain a `Header` (row counts, date range, `nextPage` link) and `Rows`.
Observed: a site with no data returns field names with **empty-string values** — empty string
must be parsed as missing, never as zero.

### 3.4 Schema

- Sites: `Id`, `Name`, `Description`, `Longitude`, `Latitude`, `Status` ("Active"/"Inactive");
  `Id` returned as a string. Areas: `Id`, `Name`, `Description`, and X/Y corner coordinates.
- **The daily report row schema is not defined in the Swagger spec** (reports return a generic
  object). Observed live fields: `Site Name`, `Report Date` (e.g. `2026-03-01T00:00:00`),
  `Time Period Ending` (e.g. `00:14:59`), `Time Interval`, vehicle-length bins (`0 - 520 cm`,
  `521 - 660 cm`, `661 - 1160 cm`, `1160+ cm`), speed bins spanning 0–10 mph through 80+ mph,
  `Avg mph`, `Total Volume`. The exact spelling of every speed-bin column is unconfirmed
  (blocker `GA-WT-2`); Gate B must freeze the observed schema from a real accepted fixture.
- Quality: `/quality/daily` returns `Qualities` rows `{Date, Quality}` with integer values
  (observed 89, 99). The [official WebTRIS FAQ](https://webtris.nationalhighways.co.uk/Home/Faqs)
  defines this as a percentage: minutes of available data divided by the possible minutes in the
  selected day range, multiplied by 100. It is a data-availability marker, not sensor-accuracy or
  traffic-validity evidence.

### 3.5 Geographic and modal coverage

Strategic road network (motorways/trunk roads). Site types: 1 = MIDAS, 2 = TAME, 3 = TMU,
4 = TRADS Legacy. Sensors are aggregate loop/radar counts — no vehicle-level records. Observed
Manchester-relevant active sites include M56 (e.g. Id 34, `M56/8150A`, 53.3578, −2.3075), M60
(e.g. Id 100, `M60/9462B`, 53.4790, −2.1191), and M62 western end (Id 122, `M62/1758A`); the
sites listing was truncated by the audit tooling, so these are examples, not a census.

### 3.6 Observation-time semantics

Fifteen-minute intervals observed directly (96 rows for one day; `Time Period Ending` steps of
15 minutes). **Timezone is not documented anywhere fetched** (blocker `GA-WT-1`): report
timestamps must be preserved verbatim and not converted to UTC instants until National Highways
confirms the basis ([ADR-055](../decisions/ADR-055-manchester-time-basis.md)).

### 3.7 Publication cadence

FAQ: data is "usually processed and uploaded to the WebTRIS service a month in arrears"
(consistent with March 2026 data being retrievable in July 2026). WebTRIS is therefore a
**historical/latest-accepted source, not a near-live source**, under current publication
behaviour; any `near_live` labelling for WebTRIS is unavailable until observed latency evidence
says otherwise.

### 3.8 Rate limits

None stated on any fetched page (blocker `GA-WT-5`); the web UI (not the API) caps reports at 30
sites. Adapter must self-impose bounds.

### 3.9 Licence, attribution, retention, redistribution

The WebTRIS privacy-policy page states site information may be used and re-used free of charge
"under the terms of the Open Government Licence" (logos excluded). The TRIS open-data landing
page carries no licence text. The snapshot manifest retains that provider statement and the
[official OGL v3.0 URI](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

### 3.10 Privacy

Observed data is aggregate per-interval counts/speeds in bins; no vehicle-level or personal
identifiers observed. The privacy policy does not make an affirmative anonymity statement about
traffic data.

### 3.11 Outage and failure behaviour

Material, current, and confirmed: the WebTRIS homepage states the service "will likely be
interrupted in 2026" for around **three to six months**, and the interruption has already been
rescheduled repeatedly (news items 11/07/2024, 30/04/2025, 31/01/2026). The related TRIS portal
states it "will no longer be updated from July 2026". Consequences for v0.7:

- the WebTRIS adapter must treat a long outage as a first-class `unavailable`/`stale` state, not
  an error path;
- Gate B acceptance evidence (a real fixture) should be captured **before** the interruption
  begins where possible; and
- no v0.7 claim may assume WebTRIS availability during the dissertation period.

### 3.12 Snapshot suitability

High for accepted windows; the undocumented report schema and announced interruption make early
immutable snapshots plus verbatim raw preservation essential.

### 3.13 What TrafficTwin may and may not claim

May: strategic-road interval volumes/average speeds for covered sites; the source-reported data
availability percentage calculated by the published WebTRIS formula; OGL-based reuse per the
privacy-policy statement.
May not: city-road coverage; near-live status under month-in-arrears publication; a UTC
interpretation of report timestamps (`GA-WT-1`); interpret quality as sensor accuracy or complete
traffic validity; service availability during the announced 2026 interruption.

## 4. TfGM traffic-signal locations

### 4.1 Endpoint and version

- data.gov.uk listing "GM Traffic Signal Locations" (publisher Transport for Greater Manchester):
  <https://www.data.gov.uk/dataset/3bfccaf7-3760-4f85-aedc-2904943a7ef7/traffic-signal-locations>
- Data zip (all formats): <https://odata.tfgm.com/opendata/downloads/TrafficSignals/TrafficSignals_OpenData.zip>
- Supporting information PDF (schema document):
  <https://odata.tfgm.com/opendata/downloads/TrafficSignals/TrafficSignalsSupportingInfo.pdf>
- Version identity at audit time: data.gov.uk label "Nov 2025 Traffic Signal locations data",
  "Last Updated: 14 January 2026"; files inside the zip timestamped 14 Jan 2026. **The zip URL is
  unversioned and overwritten in place** — content hash plus retrieval date is the only reliable
  version identity, which matches the v0.7 immutable-snapshot contract exactly.

### 4.2 Access and authentication

Anonymous HTTPS GET (verified; ~1.2 MB zip). The dataset is not behind the TfGM developer API.
`developer.tfgm.com` 302-redirects to a JS-rendered tfgm.com portal page whose key mechanics
could not be read (blocker `GA-TFGM-1`, not blocking for this dataset). TfGM's own Open Data
Portal is stated to be "no longer in operation" (tfgm.com/open-data), with real-time bus data
delegated to BODS.

### 4.3 Format and schema

Zip contains CSV, GeoJSON, GeoPackage, KML, SHP (with `.prj`), TAB formats plus `TFGM_OGL.txt`.
Exact observed CSV header:

```text
FRAS_ref,Description,Type,Controller,BUS_GATE,Easting,Northing,Type_Of_Control,Authority,HA_AGENCY_MAINTAINED,Longitude,Latitude,NIS_node,COMMENTS,KRN
```

2,529 data rows at audit time. The supporting-info PDF §5.2 documents all fifteen fields
(`FRAS_ref` = unique ID; `BUS_GATE` = dedicated bus signals; `KRN` = Key Route Network; etc.) and
§5.3 warns field names may be truncated in some formats.

### 4.4 Coordinate reference system

Dual: OSGB eastings/northings **and** WGS84 longitude/latitude columns (PDF §5.2). The shapefile
`.prj` declares British National Grid, EPSG:27700. The v0.7 rule that coordinates are transformed
only through a versioned, tested projection service applies; the presence of both systems allows
a cross-check invariant at validation time.

### 4.5 Coverage and record semantics

All ten GM boroughs present (observed counts: Manchester 615, Stockport 313, Wigan 260, Salford
250, Bolton 236, Oldham 191, Tameside 181, Rochdale 177, Trafford 171, Bury 135). A record is one
signal-controlled site; observed `Type` values: Junction 1376, Puffin 640, Toucan 243, Pelican
231, Sparrow 16, Pegasus 10, Wig Wag 9, PCAT 3, Pedex 1. Infrastructure reference only — no
signal state, phase, timing, queue, count, or incident meaning, exactly as the v0.7 design
requires.

### 4.6 Observation-time semantics and cadence

Static reference data with a dataset-level version date and no per-record timestamp. The PDF
states TfGM "aims to update this dataset twice per year".

### 4.7 Rate limits

Not applicable (static anonymous download); none stated.

### 4.8 Licence, attribution, retention, redistribution

OGL v3.0 stated in three places (PDF §2.1, data.gov.uk page, and `TFGM_OGL.txt` inside the zip).
Exact required attribution (PDF §2.2):

> Contains Transport for Greater Manchester data. Contains OS data © Crown copyright and
> database right 2025.

The zip's `TFGM_OGL.txt` carries the same wording with year **2026** — a PDF/zip year discrepancy
to record verbatim in the snapshot; use the wording shipped inside the acquired artifact.

### 4.9 Privacy

None: fields are infrastructure identifiers, coordinates, and equipment types only (confirmed
from the full header and sample rows).

### 4.10 Outage and failure behaviour

No status page or SLA; contact is an email address in the PDF. Failure handling is the generic
snapshot policy (last accepted snapshot stays authoritative; new fetch failures quarantine).

### 4.11 Snapshot suitability

High: small, complete, versioned by hash and access date. The in-place-overwritten URL makes the
prior-snapshot relationship and duplicate/no-change detection in the v0.7 snapshot contract
directly necessary.

### 4.12 What TrafficTwin may and may not claim

May: signal/crossing site locations by type and borough with OGL attribution; a reference map
layer with dataset version date.
May not: signal states, phases, timings, queues, counts, incidents, or any live meaning; any
claim that the layer is current beyond its recorded dataset version date.

## 5. DfT Bus Open Data Service (SIRI-VM)

### 5.1 Endpoint and version

- Bus location API: `https://data.bus-data.dft.gov.uk/api/v1/datafeed/?api_key=[API_KEY]`,
  documented at <https://data.bus-data.dft.gov.uk/guidance/requirements/?section=apireference>.
- Documented filters: `boundingBox` (minLongitude, minLatitude, maxLongitude, maxLatitude),
  `operatorRef` (NOC), `lineRef`, `producerRef`, `originRef`/`destinationRef` (normally NaPTAN),
  `vehicleRef`.
- A processed GTFS-RT output also exists; its exact endpoint path is behind sign-in
  (blocker `GA-BODS-1`).
- Profile: feeds are validated against the "Department for Transport SIRI-VM 2.0 (Q) Profile"
  (<https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm/technical-guidance-siri-vm>).

### 5.2 Access and authentication

Registered account plus API key required ("Use of the APIs requires an API key which can be
obtained from Account Settings"). **The key is passed as a URL query parameter**, which directly
drives the credential-handling rules in
[ADR-054](../decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md): request
URLs must never be logged or stored unredacted, and snapshot request metadata must strip
`api_key` before persistence.

### 5.3 Request/response format

SIRI-VM XML (untrusted input → hardened parsing per ADR-054). GTFS-RT alternative exists.
Download-all page lists location data as "SIRI-VM GTFS-RT, File type: ZIP, Update frequency:
Every 10 seconds".

### 5.4 Documented schema

The authoritative
[DfT SIRI-VM profile](https://www.gov.uk/government/publications/technical-guidance-publishing-location-data-using-the-bus-open-data-service-siri-vm/technical-guidance-siri-vm)
defines the mandatory structures and elements used by TrafficTwin: `ResponseTimestamp`,
`ProducerRef`, `VehicleMonitoringDelivery`/`VehicleActivity`, `RecordedAtTime`, `ValidUntilTime`,
`MonitoredVehicleJourney`, `OperatorRef`, `LineRef`, `PublishedLineName`, `DirectionRef`,
`OriginRef`, `OriginName`, `DestinationRef`, `VehicleLocation` (`Longitude`, `Latitude`),
`Bearing`, `BlockRef`, `VehicleJourneyRef`, and `VehicleRef`. The detailed cardinality table
confirms `VehicleRef` as 1:1 even though the page's shorter mandatory summary omits it.

Optional fields include `DestinationName`, `OriginAimedDepartureTime`,
`DestinationAimedArrivalTime`, `Velocity` (default metres per second), `Occupancy`,
`ItemIdentifier`, and `MonitoredCall`. The profile does not define a mandatory `Speed` element;
`Velocity` is optional, so TrafficTwin cannot claim complete bus-speed coverage. `OperatorRef`
"shall be the operator's National Operator Code (NOC) from the Traveline NOC database".

### 5.5 Timestamp semantics

Documented directly: "All timestamps are stated in UTC" (xsd:dateTime; `RecordedAtTime` = when
vehicle data was recorded; `ValidUntilTime` = validity horizon). This is the only v0.7 source
with a documented UTC basis, and the only source eligible for the `live_vehicle` truth state.

### 5.6 Coverage

Every local bus service in England is required to publish (Bus Services Act 2017). No
completeness or exemption statement was observed; completeness of the Bee Network fleet is
therefore not claimable (matches the v0.7 design exclusion "not a complete fleet guarantee").

### 5.7 Publication/update cadence

Publishers must update at least every 30 seconds (15 accepted); BODS's consumer cache updates
every 10 seconds; the national bulk zip may be requested no more than every 5 seconds.
"Historical real time data is not currently provided by the service" — TrafficTwin's own
immutable snapshots are the only replay evidence, which makes the v0.7 snapshot-first design
load-bearing for RQ12/RQ13.

### 5.8 Rate limits

Only the 5-second national-zip spacing is documented. No general consumer rate-limit policy was
found (blocker `GA-BODS-3`); the adapter must self-impose a conservative poll interval well above
the 10-second cache period.

### 5.9 Licence, attribution, retention, redistribution

Portal footer: OGL v3.0, Crown copyright; guidance states "You do not need a license to use the
data." No retention or republication conditions observed beyond OGL. However, the v0.7
privacy/retention decision (design §18.2) remains TrafficTwin's own to make and record before
acceptance; OGL permission does not settle the longitudinal-trace question below.

### 5.10 Privacy-sensitive identifiers

`VehicleRef` is a per-vehicle reference that "must be consistent through the day" and is
generated by vehicle equipment; multi-day persistence is undocumented (blocker `GA-BODS-4`).
Precautionary Gate A position: treat `VehicleRef` as a potentially persistent vehicle identifier
that can create longitudinal movement traces. Raw snapshots retain it (raw evidence is
immutable), but display, export, and public-fixture policy must apply the design's §18.2
retention/redaction contract, and no BODS identifier appears in logs. TrafficTwin infers nothing
about passengers, drivers, or people.

### 5.11 Outage and failure behaviour

A service changelog and technical-contact route exist; no consumer-facing SLA or status page was
found (blocker `GA-BODS-5`). Feed gaps must degrade to `stale`/`unavailable` states, never to
interpolated positions.

### 5.12 Snapshot suitability

Medium-high: each poll is a natural immutable snapshot (response bytes + request metadata with
`api_key` stripped + retrieval time). Because BODS keeps no history, retention bounds (count/age
per the design's bounded-retention requirement) must be decided at Gate B; deduplication uses
(`VehicleRef`, `RecordedAtTime`) within the accepted window without inventing intermediate
positions.

### 5.13 What TrafficTwin may and may not claim

May: recent bus/transit vehicle positions with UTC observation timestamps; `live_vehicle` status
computed from `RecordedAtTime` under a versioned freshness policy; bus-labelled aggregate counts.
May not: private-vehicle flow, road speed, congestion, or "traffic volume"; fleet completeness;
historical replay beyond TrafficTwin's own accepted snapshots; any person-level inference.

## 6. Bee Network membership identifiers

Full decision: [ADR-057](../decisions/ADR-057-bee-network-membership-identifiers.md). Audit facts:

1. The Traveline NOC database (the controlled operator list that the DfT SIRI-VM profile
   mandates for `OperatorRef`) contains dedicated "Bee Network" operator records. Observed on
   2026-07-22 via <https://www.travelinedata.org.uk/traveline-open-data/transport-operations/browse/>:
   **BNDB** (group Rotala), **BNFM** (First), **BNGN** (Go-Ahead), **BNML** (ComfortDelgro),
   **BNSM** (Stagecoach), **BNVB** (no group) — all with Operator Public Name "Bee Network",
   mode Bus.
2. `OperatorRef` + `LineRef`/`PublishedLineName` are mandatory in the profile, and the datafeed
   API filters on both, so membership is decidable from identifiers alone **if** live GM
   publishers actually populate `OperatorRef` with the BN\* codes. That linchpin fact requires an
   API key and is a Gate B verification step (blocker `GA-BEE-1`).
3. No official machine-readable "Bee Network franchised services" list was found on tfgm.com,
   data.gov.uk, or BODS. The closest join target is TfGM's "GM Public Transport Schedules — GTFS
   and TXC" dataset (nightly, all GM bus and Metrolink services,
   <https://www.data.gov.uk/dataset/c3ca6469-7955-4a57-8bfc-58ef2361b797/gm-public-transport-schedules-gtfs>)
   — which is licensed **ODbL v1.0, not OGL** (blocker/`GA-BEE-3` licence-mixing consequence: any
   artifact derived from a join against this dataset takes on ODbL share-alike/attribution
   obligations and needs its own publication-class decision).
4. Geography cannot define membership: TfGM's service-permits page confirms non-franchised
   (mostly cross-boundary) buses operate within Greater Manchester. Marketing wording ("all local
   bus services are now part of the Bee Network") and the franchised-contract set are not
   provably identical from official pages (blocker `GA-BEE-2`).
5. The NOC database's own licence is **not confirmed** — no licence text was found on
   travelinedata.org.uk, and circulating OGL claims trace to non-official summaries
   (blocker `GA-BEE-4`).

Gate A position (per ADR-057): membership is determined only by identifier matching —
`OperatorRef` against a frozen, evidence-verified BN\* allowlist, optionally corroborated by a
`LineRef` join to an accepted TfGM schedule snapshot. **Display-name matching (e.g. on
`PublishedLineName` or operator public names in free text) is prohibited** as a membership test.
Vehicles matching neither rule are labelled `non_franchised_or_unknown`, never silently dropped
or silently included.

## 7. Optional Randy/TOS Manchester artifacts (repository evidence only)

No new acquisition, endpoint, or permission exists. Existing evidence (unchanged by this audit):

- Pinned sources: `vec_env` `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` and `tos-data`
  `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`, audited read-only in
  [the v0.6 source-snapshot audit](randy-source-snapshot-audit-v0_6.md) (154 hashed files).
- The five processed traces (`wd_am`, `wd_pm`, `ev`, `inc`, `we`) are Manchester-derived
  simulation artifacts with one-second clocks and exact occupancy identity — simulation-clock
  evidence, not wall-clock observations, and carry no authenticated CRS/geographic display
  contract.
- The v0.6 audit records that the FCD trace builder defaults to Manchester-specific
  Drakewell-derived RSU placements (`rsu_placement_is_manchester_specific`); those generated
  sites remain analysis locations, not deployed infrastructure, and must not be rendered as
  evidenced Manchester infrastructure on the v0.7 map without a separate join to evidenced
  reference data.
- Neither external repository contains a licence file; reuse remains bounded by Randy's written
  permission (sanitised samples/aggregates, both repositories cited, engine
  `v2_post_nrsus_fix`, `_s102` labels). Nothing in v0.7 widens this.
- What TrafficTwin may claim: optional case-study evidence under the exact v0.6 contract.
  May not claim: a live feed, general Manchester telemetry, geographic ground truth, or any
  redistribution beyond the recorded permission.

## 8. Reconciliation requirements (all sources)

Every Gate B validator and every projection/join must publish complete accounting with explicit
denominators; none of these states may be silently collapsed:

| State | Required meaning |
|---|---|
| `matched` | Record admitted by exact identifier/geometry/time rules, with the rule version recorded |
| `unmatched` | Record valid but no counterpart (e.g. BODS vehicle with no schedule-line join); retained and counted |
| `ambiguous` | More than one candidate under the rules (e.g. duplicate `FRAS_ref`, one vehicle in two operators); withheld from projection, listed for review |
| `missing` | Expected by the source contract but absent (e.g. WebTRIS empty-string interval, absent mandatory SIRI element); never imputed, never zero |
| `stale` | Accepted snapshot older than the source-specific freshness threshold; usable only with the visible `stale` label |
| `excluded` | Outside declared scope (out-of-boundary site, non-GM operator, out-of-window interval, unsupported schema version); counted with reason codes |

Source-specific minimums: DfT — out-of-area count points and revised records between snapshots;
WebTRIS — inactive sites, empty-string intervals, quality-flagged days; TfGM — borough scope and
duplicate/changed `FRAS_ref` between dataset versions; BODS — deduplication key
(`VehicleRef`, `RecordedAtTime`), stale-by-`ValidUntilTime` positions, and the three-way
membership outcome (franchised-matched / non-franchised-or-unknown / out-of-scope).

## 9. ManchesterTimeBasis requirements

Decision detail in [ADR-055](../decisions/ADR-055-manchester-time-basis.md). Audit-driven facts:

| Source | Documented basis | Gate A handling |
|---|---|---|
| BODS | UTC, documented in the DfT profile | Parse as UTC instants; the only source eligible for `live_vehicle` |
| DfT raw counts | Clock-hour ranges + date-only `count_date`; timezone undocumented (`GA-DFT-1`) | Keep as (date, local-clock-hour-label) pairs; no fabricated UTC instant |
| WebTRIS | Local-looking timestamps; timezone undocumented (`GA-WT-1`) | Preserve verbatim source strings; no UTC conversion until confirmed |
| TfGM signals | Dataset version date only | Date-only version identity; no instant |
| Randy/TOS | Simulation clocks | Never mixed with wall-clock bases |

Cross-cutting: all internal absolute timestamps UTC; display via `Europe/London` (stdlib
`zoneinfo` with `tzdata` pinned); DST tests must cover the missing spring hour and repeated
autumn hour; date-only evidence never becomes an instant; a record with an undocumented timezone
can never be labelled `near_live` or `live_vehicle`.

### 9.1 Frozen freshness policy v1

`manchester-freshness-v1` computes state from source observation evidence, never download time:

- **BODS:** `live_vehicle` requires a valid accepted snapshot, documented UTC timestamps,
  `RecordedAtTime <= evaluated_at_utc <= ValidUntilTime`, and an observation age no greater than
  60 seconds. The 60-second ceiling is a conservative TrafficTwin engineering threshold derived
  from the documented 30-second publisher update obligation and 10-second consumer cache; it is
  not an uptime or latency guarantee from BODS. Future-dated, expired, unparseable, or older
  records are `stale` or `unavailable`. Offline/replay use is always labelled historical or stale,
  never live.
- **DfT:** all admitted raw counts and AADF records are `historical`; retrieval date cannot
  upgrade them.
- **WebTRIS:** accepted reports are `historical` under the documented month-in-arrears process.
  The newest accepted report may be called “latest available”, but not `near_live`.
- **TfGM signals:** the layer is versioned reference infrastructure. The UI shows the dataset
  version and age; it never receives a traffic freshness label or live meaning.
- **Randy/TOS:** records retain `simulation_clock` and the v0.6 source labels. They never enter
  wall-clock freshness evaluation.

The policy is versioned so a later source statement can change thresholds without rewriting raw
evidence or silently reclassifying old results.

## 10. Acquisition dependency decisions

Decision detail in [ADR-054](../decisions/ADR-054-bounded-manchester-acquisition-transport-and-parsing.md)
and [ADR-056](../decisions/ADR-056-manchester-map-rendering-and-attribution.md). Summary:

- **HTTP client: `httpx>=0.28.1,<1`** (BSD; enforced default timeouts; redirects **off** by
  default; no implicit retries; documented streaming API for byte ceilings). `requests` rejected for
  no-timeout/follow-redirects defaults that invert the fail-closed posture.
- **XML/SIRI parsing: `defusedxml==0.7.1`** plus a startup `pyexpat.EXPAT_VERSION` record. Every
  parse call explicitly sets `forbid_dtd=True`, `forbid_entities=True`, and
  `forbid_external=True`; `forbid_dtd` defaults to false and must not be left implicit. The
  stdlib's protections are Expat-version-dependent and cannot be assumed on user machines.
- **Compression/archive handling is app-bounded**: the stdlib documents no decompression-bomb
  protection, so streamed decompression with output-byte ceilings, per-member zip size and ratio
  caps, and member-count/path/symlink checks are mandatory adapter code.
- **Map: `pydeck>=0.9.3,<1` compatibility range via `st.pydeck_chart`** (Apache-2.0). The
  development lock currently resolves pydeck 0.9.3 through Streamlit; Gate B declares the direct
  dependency only if Manchester code imports pydeck directly. Default configuration is
  **`map_provider=None`** (documented no-basemap mode) with
  the ONS OGL boundary polygon as a layer — offline-safe and licence-clean. Carto's keyless
  basemap tier is formally restricted to "grantees" and its exact attribution text was not
  confirmed (`GA-MAP-1`), so a Carto basemap is not enabled at Gate A. OSM raster tiles are not
  used by default (usage policy demands distinct User-Agent, caching, attribution, and permits
  blocking without notice).
- **Boundaries: ONS Open Geography Portal** local-authority boundaries under OGL v3.0 with the
  required two-line ONS/OS attribution.
- **Timezone: stdlib `zoneinfo`** with `tzdata>=2026.3,<2027`; the reviewed development lock is
  `tzdata==2026.3` (Windows fallback documented on PyPI).
- **Product shell: `streamlit>=1.58,<2`**, with development lock `streamlit==1.59.2`. The
  candidate 45-test navigation suite passes on both 1.58.0 and 1.59.2; the built wheel contains
  all 34 direct page scripts and its installed root passes AppTest. This accepts the Gate A
  version decision, not `UX-01` cutover.

All dependency additions are Gate B implementation work; nothing is added to `pyproject.toml` by
this audit.

## 11. Source-specific threat matrix

Controls marked ✓ are mandatory for the affected source at Gate B; the design §18.1 controls
apply globally.

| Threat | DfT API/bulk | WebTRIS | TfGM zip | BODS | Mandatory control |
|---|---|---|---|---|---|
| SSRF / host abuse | ✓ (bulk host is shared `storage.googleapis.com`) | ✓ | ✓ | ✓ | Exact HTTPS host allowlist; the Google Storage entry must be **path-prefixed** (`/dft-statistics/road-traffic/`); no user-supplied URLs anywhere |
| Redirect abuse | ✓ | ✓ | ✓ (`developer.tfgm.com` 302 observed) | ✓ | `httpx` redirects off; follow only same-host redirects up to a small fixed depth; cross-host redirects fail closed and are recorded as findings |
| Decompression bomb | ✓ (zipped CSVs) | – (JSON) | ✓ (multi-format zip) | ✓ (bulk ZIP option; gzip transfer encoding) | Streamed decompression with output ceilings; zip member count/size/ratio caps; reject nested archives, absolute paths, traversal, symlinks, duplicate members |
| Unsafe XML (DTD/XXE/entity expansion) | – | – | – (KML member excluded from parsing) | ✓ (SIRI-VM) | `defusedxml`; DTDs, external entities, and network access rejected; parse only after byte-ceiling enforcement |
| Oversized response | ✓ | ✓ (mandatory pagination; `page_size` self-capped) | ✓ | ✓ | Byte ceilings enforced on the stream, never trusted from `Content-Length`; page-count caps; row caps |
| Credential leakage | – (anonymous) | – (anonymous) | – (anonymous) | ✓✓ (`api_key` **in the URL query string**) | Secrets only via environment/`st.secrets`; full request URLs never logged or persisted; snapshot request metadata stores the endpoint identity with the query-credential stripped; keys never fingerprinted into artifacts |
| Malformed timestamps | ✓ (`hour` out of range, invalid `count_date`) | ✓ (undocumented timezone, empty strings) | ✓ (version-date parsing) | ✓ (non-ISO `RecordedAtTime`, `ValidUntilTime` in the past) | Strict parsing to typed findings; a record with an unparseable/undocumented time basis is `missing`/`unavailable`, never defaulted to retrieval time and never `live` |
| Snapshot replacement / rollback | ✓ (unversioned API) | ✓ | ✓✓ (URL overwritten in place) | ✓ (no source history exists) | Atomic new-only publication; failed/partial fetch quarantined; prior-snapshot linkage with duplicate/no-change detection; accepted snapshots read-only |

## 12. Gate B fixture and publication plan

Gate A selects the smallest legally and scientifically useful real cases. Raw operational
snapshots live outside Git. Repository fixtures carry one of the design's exact publication
classes: `private`, `redistributable_raw`, `redistributable_derived`, or `metadata_only`.

| Source | Minimal real Gate B acceptance case | Local snapshot treatment | Repository publication class |
|---|---|---|---|
| DfT | One Manchester count point, one `count_date`, its bounded raw-count page/rows, count-point metadata, and relevant AADF metadata | Preserve exact API bytes and pagination metadata in the private Manchester workspace | A small OGL-attributed, manifest-bound raw fixture may be `redistributable_raw` after licence and schema checks |
| WebTRIS | One active Manchester-relevant site, one complete daily report (normally 96 15-minute rows), site metadata, and daily quality response | Preserve exact JSON responses and the undocumented time strings | A small OGL-attributed, manifest-bound accepted fixture may be `redistributable_raw` |
| TfGM signals | One full official traffic-signals zip, including its shipped OGL text, hash, and member inventory | Preserve the exact zip locally; parse only the allowlisted CSV/GeoJSON/CRS members | Exact header plus three representative attributed rows is `redistributable_derived`; the full zip stays workspace-only unless separately approved |
| BODS | One bounded Greater-Manchester SIRI-VM poll with credential-stripped request metadata and the full required/optional-field audit | Treat raw response as `private`; apply retention bounds and never expose raw `VehicleRef` in logs or public fixtures | Real raw fixture is `private`; repository tests use schema-faithful synthetic XML, while a redacted aggregate/schema manifest may be `metadata_only` |
| Randy/TOS | The accepted v0.6 VEC-11 sanitised sample and aggregates only | Reuse the existing permission-manifested pack; acquire no new raw material | Existing permission class only; public hosting remains unauthorised |
| ONS boundary, if selected | One exact named boundary edition with CRS, generalisation, hash, and attribution | Preserve the original locally | A simplified/hash-bound derivative may be `redistributable_derived` after OGL attribution review |

No repository fixture is admitted merely because its endpoint is public. Its manifest must bind
the exact source, access date, licence/attribution, schema, redactions, hashes, and permitted
publication class. BODS credentials and raw vehicle identifiers are always excluded from Git and
package artifacts.

## 13. Unresolved blockers

Each blocker blocks only its dependent capability/claim, per the v0.7 design §25.

| ID | Blocker | Blocks |
|---|---|---|
| `GA-DFT-1` | DfT raw-count `hour` timezone undocumented in the metadata PDF or any fetched page | Any UTC instant for survey hours; hour-level cross-source alignment (`MAN-07`, `MAN-09` temporal profile precision) |
| `GA-DFT-2` | No DfT rate-limit/fair-use statement found | Sync frequency defaults must stay conservative (`MAN-02`) |
| `GA-DFT-3` | No DfT status/SLA page found | Outage classification relies on adapter-observed failures only |
| `GA-WT-1` | WebTRIS report timestamp timezone undocumented (swagger, FAQ, overview all silent) | UTC conversion of WebTRIS intervals; observed-vs-simulated alignment at sub-day precision (`MAN-03`, `MAN-10`) |
| `GA-WT-2` | Exact spelling of all daily-report speed-bin columns unconfirmed (no swagger schema; tooling summarised the live row) | Frozen WebTRIS report schema (`MAN-03` Gate B fixture) |
| `GA-WT-3` | `report_type`/sub-type enums not formally documented | Monthly/annual report support (`MAN-03` scope) |
| `GA-WT-5` | No WebTRIS API rate-limit statement found | Sync bounds must stay conservative (`MAN-03`) |
| `GA-TFGM-1` | TfGM developer-portal mechanics unreadable (JS-rendered); irrelevant to the static signals zip | Only future TfGM API sources, none planned |
| `GA-BODS-1` | GTFS-RT endpoint path behind sign-in | GTFS-RT alternative evaluation (`MAN-05` optional path) |
| `GA-BODS-3` | No general consumer rate-limit policy found (only the 5-second national-zip spacing) | Poll-interval defaults must stay conservative (`MAN-05`) |
| `GA-BODS-4` | `VehicleRef` persistence beyond one day undocumented | Retention/display/export policy must assume potential persistence (`MAN-05`, design §18.2) |
| `GA-BODS-5` | No BODS consumer SLA/status page found | Outage classification relies on adapter-observed failures |
| `GA-BEE-1` | Whether live GM SIRI-VM `OperatorRef` values are the BN\* NOCs requires an API key to verify | Activating identifier-based Bee Network membership (`MAN-05`, ADR-057) |
| `GA-BEE-2` | Bee Network branding set vs franchised-contract set not provably identical from official pages | Any "all GM buses are Bee Network" wording; membership label stays three-valued |
| `GA-BEE-3` | TfGM GTFS/TXC schedule dataset is ODbL v1.0 (not OGL); derived-join publication class unresolved | Publishing any artifact derived from a schedule join (`MAN-05`, `MAN-08` exports) |
| `GA-BEE-4` | Traveline NOC database licence not confirmed on travelinedata.org.uk | Redistributing NOC-derived reference tables; local lookup use only until resolved |
| `GA-MAP-1` | Carto keyless-basemap grantee terms and exact attribution text unconfirmed | Enabling any Carto basemap (ADR-056 keeps `map_provider=None`) |
| `GA-BODS-6` | BODS account registration terms not reviewed (account creation was out of audit scope) | Account creation and key issuance at Gate B |

## 14. What this audit does and does not establish

Does: freeze the observed endpoint identities, formats, schemas or schema blockers, time
semantics, licences as displayed, privacy postures, outage facts, and the transport/parsing/time
/map/membership decisions needed to write Gate B contracts, with every uncertainty named.

Does not: implement or accept any adapter; create credentials; verify live BODS feed content;
grant any publication right; change any capability state. This accepted Gate A record authorises
Gate B to implement only the frozen decisions above; it is not acquisition acceptance. `MAN-01`
remains `planned` until the common snapshot service and source-specific Gate B evidence pass.

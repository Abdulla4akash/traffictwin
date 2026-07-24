# Provider Enquiry Drafts (DfT, WebTRIS, BODS)

The 24 July 2026 documentation probe
([machine record](evidence/manchester_source_docs_probe_20260724.json)) found the official
reference pages silent on three source facts that block Gate-B closure and full canonical time
projection. These drafts are ready to send; they ask only for documented facts and assert nothing.
Send from the project account, then record each reply as dated evidence under
`docs/integration/evidence/` and reconcile the affected open questions and capability rows.

Nothing in these drafts commits the project to a licence, retention practice, or publication; they
are fact-finding only.

---

## 1. DfT Road Traffic Statistics — raw-count hour timezone (`GA-DFT-1`)

**To:** DfT road traffic statistics team (via the roadtraffic.dft.gov.uk contact/feedback route)
**Subject:** Timezone basis of the `hour` field in Road Traffic API raw counts

> I am using the DfT Road Traffic Statistics API
> (https://roadtraffic.dft.gov.uk/api-documentation) for academic research on Manchester
> count-point data. The raw-count records expose an `hour` field, but I cannot find a statement of
> its timezone/clock basis in the API documentation.
>
> Could you confirm, for the raw-count and count-point endpoints:
> 1. Is the survey `hour` recorded in local clock time (Europe/London, i.e. subject to BST), in
>    UTC/GMT, or on another basis?
> 2. For count dates during British Summer Time, does the hour value follow the local clock or a
>    fixed offset?
> 3. Is there an authoritative methodology document that states this?
>
> I need this only to label the data's time basis correctly and will not reinterpret the values
> beyond what you confirm. Thank you.

**Unblocks:** open question `GA-DFT-1`; full `MAN-02`/`MAN-07` canonical time projection for DfT
survey rows (currently kept as typed source-local exclusions).

---

## 2. National Highways WebTRIS — report clock/timezone semantics

**To:** National Highways WebTRIS support (webtris.nationalhighways.co.uk support/contact route)
**Subject:** Timezone basis of WebTRIS daily-report time periods

> I am using the WebTRIS API (https://webtris.nationalhighways.co.uk/api/swagger/ui/index) for
> academic research. The daily report exposes `Time Period` / interval fields and report dates in
> `ddmmyyyy` format, but I cannot find a statement of the timezone/clock basis for these times.
>
> Could you confirm:
> 1. Are the daily-report interval times recorded in local clock time (Europe/London, subject to
>    BST) or in UTC/GMT?
> 2. During British Summer Time, do the 15-minute interval labels follow the local clock (so a day
>    has the usual DST gap/overlap) or a fixed offset?
> 3. Is there an authoritative document stating this?
>
> I only need this to label the source time basis correctly. Thank you.

**Unblocks:** WebTRIS timezone open question; full `MAN-03`/`MAN-07` canonical time projection.
Note: the separate 24 July 2026 recency probe already confirmed WebTRIS is **not** near-live
(publication is about a month in arrears); this enquiry does not reopen that.

---

## 3. Bus Open Data Service — retention, republication, and identifier terms

**To:** BODS service (bus open data service support route from
https://www.gov.uk/guidance/find-and-use-bus-open-data)
**Subject:** Retention and republication terms for SIRI-VM vehicle-location data

> I am using the Bus Open Data Service SIRI-VM location feed for academic research on Bee Network
> vehicles in Manchester. The guidance pages state Open Government Licence v3.0 for the site
> content, but I cannot find explicit consumer-side terms for the live location data itself.
>
> Could you confirm, for a data consumer:
> 1. What licence and terms govern reuse of the SIRI-VM vehicle-location payload (as distinct from
>    the guidance pages)?
> 2. Are there retention or storage limits on downloaded vehicle-position snapshots that include
>    `VehicleRef`/`BlockRef` identifiers?
> 3. What may be republished — for example aggregate counts versus individual positions or
>    identifiers — in an academic dissertation or a public demonstration?
> 4. Are the operator/NOC reference tables (used to identify Bee Network services) covered by the
>    same terms, and may they be redistributed?
>
> I currently retain snapshots privately with a precautionary time/space-bounded cleanup and make
> no public export; I want to confirm the actual permitted basis. Thank you.

**Unblocks:** BODS retention/registration/publication open question; complete `MAN-05` scope and
any public live/aggregate output. Until answered, the precautionary private-retention controls and
identifier-only Bee Network scope remain.

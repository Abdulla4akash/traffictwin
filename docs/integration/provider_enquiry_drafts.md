# Provider Enquiry Drafts (DfT, WebTRIS, BODS)

The 24 July 2026 documentation probe
([machine record](evidence/manchester_source_docs_probe_20260724.json)) found the then-probed
reference pages silent on three source facts. The deeper 2 August
[authoritative-source re-audit](manchester_authoritative_source_reaudit_20260802.md) leaves both
timezone questions open but closes the generic BODS reuse/publication and API-registration facts
from the official implementation guide. These narrowed drafts ask only for facts still absent.
They are ready to send if the project chooses to contact the providers.
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

## 3. Bus Open Data Service — residual identifier persistence and retention semantics

**To:** BODS service (bus open data service support route from
https://www.gov.uk/guidance/find-and-use-bus-open-data)
**Subject:** Multi-day `VehicleRef` persistence and SIRI-VM snapshot retention guidance

> I am using the Bus Open Data Service SIRI-VM location feed for academic research on Bee Network
> vehicles in Manchester. The official BODS implementation guide permits consumers to copy,
> adapt, publish, distribute and transmit the open data, documents API registration/attribution,
> and the SIRI-VM profile requires `VehicleRef` to be consistent through the day.
>
> I cannot find a statement of whether `VehicleRef` is expected to persist across service days or
> any source-specific retention guidance for downloaded SIRI-VM snapshots. Could you confirm:
> 1. May a publisher reuse the same `VehicleRef` across days, or is its defined consistency scope
>    limited to one service day?
> 2. Does BODS publish any consumer retention/deletion guidance specifically for stored location
>    snapshots containing `VehicleRef`/`BlockRef`?
> 3. Is there an authoritative privacy or data-management note for longitudinal use of these
>    identifiers, distinct from the general open-data reuse rights?
>
> I currently retain snapshots privately with a precautionary time/space-bounded cleanup and make
> no public export; I want to confirm the actual permitted basis. Thank you.

**Unblocks:** the residual project privacy/data-management treatment of longitudinal identifiers.
It no longer asks for generic reuse/publication or API-registration rights: those are documented.
Until answered or separately approved by the project data controller, precautionary private
retention and identifier redaction remain.

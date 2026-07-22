# ADR-055: Manchester Time Basis

- Status: accepted (Gate A decision; Gate B contracts must encode and test it)
- Date: 2026-07-22
- Capability: `MAN-07` time/freshness semantics; constrains `MAN-02`–`MAN-05`, `MAN-09`, `MAN-10`

## Context

The v0.7 design requires UTC internal timestamps, explicit BST/DST handling, preserved source
timezones for historical labels, and a ban on fabricating instants from date-only evidence
(design §10, §11). The Gate A audit
([manchester-source-gate-a-audit-v0_7.md](../integration/manchester-source-gate-a-audit-v0_7.md))
established that the four public sources have **three different documented time postures**:

- BODS SIRI-VM: "All timestamps are stated in UTC" (documented in the DfT profile) — the only
  source with a documented UTC basis.
- DfT raw counts: a date-only `count_date` plus an `hour` field defined as local clock ranges
  ("7 represents between 7am and 8am") with **no documented timezone** (`GA-DFT-1`).
- WebTRIS: `Report Date`/`Time Period Ending` strings with **no documented timezone** anywhere
  fetched (`GA-WT-1`).
- TfGM signals: a dataset-level version date only; no per-record time.

The canonical `TrafficObservationRecord.timestamp_s` is simulation-relative seconds; the separate
canonical time-basis/schema decision remains an open v0.7 design question and is not resolved by
this ADR.

## Decision

1. **`ManchesterTimeBasis` is a typed, versioned property of every source record family**, with
   exactly these values at v1: `utc_instant` (BODS), `local_clock_hour` (DfT raw-count hour),
   `source_string_undeclared` (WebTRIS report times until `GA-WT-1` resolves),
   `date_only` (DfT `count_date`, TfGM dataset version date), and `simulation_clock`
   (Randy/TOS artifacts, which are never mixed with wall-clock bases).
2. **Storage rules.** All absolute instants are stored as UTC. Non-instant bases are stored in
   their own typed shape: date-only as calendar dates; DfT hours as (date, hour-label 0–23)
   pairs; WebTRIS times as the verbatim source strings plus parsed components. A value is
   promoted to a UTC instant only when its source basis documents one; promotion by assumption
   is prohibited.
3. **No fabricated instants.** A `date_only` value never becomes a midnight instant; a
   `local_clock_hour` never becomes a UTC hour while `GA-DFT-1` is open; a
   `source_string_undeclared` value never converts to UTC while `GA-WT-1` is open. Records with
   unparseable or contradictory time fields become `missing`-time findings, never retrieval-time
   defaults.
4. **Freshness eligibility follows the basis.** Only `utc_instant` records can satisfy
   `live_vehicle`; `near_live` requires a documented source timestamp basis; undocumented-basis
   records are at best `historical` or `stale`. This makes the design's "freshness is computed
   from source observation time" rule mechanically enforceable.
5. **Display timezone is `Europe/London` via stdlib `zoneinfo`**, with
   `tzdata>=2026.3,<2027` declared for platforms without system zone data and
   `tzdata==2026.3` in the reviewed development lock. Conversion happens at display time only;
   stored evidence is never rewritten.
6. **DST is tested, not assumed.** Gate B contracts must include golden tests for: the missing
   spring-forward local hour, the repeated autumn local hour (ambiguous local times must carry
   fold/offset disambiguation or stay labelled ambiguous), date-only labels spanning a DST
   transition, and half-open window behaviour across both transitions. DfT "neutral day" survey
   dates (March–October) fall almost entirely inside BST, which makes the undocumented-timezone
   blocker material rather than theoretical.
7. **Cross-source comparison requires compatible bases.** `MAN-10` comparisons may pair records
   only where both sides share a documented common basis at the compared granularity; mixed-basis
   pairs are `excluded` with reason codes. Day-level comparison of DfT survey dates is permitted
   (dates are timezone-safe at day granularity for this use); hour-level cross-source alignment
   is blocked until `GA-DFT-1`/`GA-WT-1` resolve.

## Consequences

- Undocumented source timezones degrade precision visibly (day-level instead of hour-level
  alignment) instead of silently producing shifted hours around DST boundaries.
- The truth-label table in design §6 gains a mechanical gate: no documented observation basis, no
  live/near-live label.
- Resolving `GA-DFT-1`/`GA-WT-1` later (an official statement of the timezone basis) upgrades
  precision through a versioned policy change, without rewriting stored evidence.

## Rejected alternatives

- Assuming DfT hours and WebTRIS timestamps are `Europe/London` local time because it is
  plausible: rejected; plausibility is not evidence, and a wrong assumption corrupts every hour
  near DST transitions.
- Storing everything as naive local datetimes: rejected; ambiguous and missing local hours make
  naive values unsound.
- Converting date-only evidence to midnight UTC for convenience: rejected by design §10.

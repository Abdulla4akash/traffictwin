# WebTRIS accepted daily reports to Manchester historical interval evidence

This offline service turns already accepted or already quarantined-and-replayed
`MAN-03` daily-report and daily-quality artifacts into one bounded,
source-specific `MAN-08` candidate inventory of historical interval rows for
filters and charts. It performs no download, refresh, source discovery, map
association, coordinate emission, cross-source fusion, cross-site aggregation,
interpolation, resampling, or publication-class upgrade.

The rows are historical strategic-road evidence only. Source date and
time-period strings stay verbatim under time basis `source_string_undeclared`
while blocker `GA-WT-1` is open and are never promoted to UTC instants;
retrieval or evaluation time never becomes observation time; source-empty
intervals stay `missing` and are never filled with zero; the daily quality
percentage stays a data-availability marker and never becomes a
sensor-accuracy or traffic-validity score; and no live-road-traffic or
city-road-coverage claim is possible.

## Filtered build

`build_webtris_timeseries` performs this fixed sequence:

1. refuse an empty or over-bound evidence set;
2. require an initialized isolated v0.7 workspace;
3. re-validate the filter and every supplied receipt by JSON round-trip;
4. refuse mixed synthetic/real evidence;
5. refuse conflicting duplicate site-day evidence and collapse identical
   duplicates with their surplus counted and an order-invariant
   representative;
6. enforce the combined input-page bound;
7. re-verify the immutable accepted snapshot or quarantine (manifest,
   receipt binding, request scope, member inventory, hashes, licence,
   publication class, evidence class) for every retained site-day;
8. replay the exact `MAN-03` parser over the re-read and re-hashed bytes and
   require the receipt's parser-report fingerprint, counts, and status;
9. attach the site-day availability percentage only from a verified quality
   artifact bound to the same site, name, and date, retaining the quality
   snapshot's own publication class separately;
10. emit sorted interval rows plus a typed exclusion for every filtered-out
    interval.

```python
from datetime import date

from traffictwin.integration.manchester.webtris_timeseries import (
    WebtrisTimeseriesEvidence,
    WebtrisTimeseriesFilter,
    build_webtris_chart_series,
    build_webtris_timeseries,
    build_webtris_timeseries_from_accepted_snapshots,
    verify_webtris_timeseries,
    verify_webtris_timeseries_from_accepted_snapshots,
)

evidence = (
    WebtrisTimeseriesEvidence(
        daily_acquisition=daily_receipt,
        quality_acquisition=quality_receipt,
    ),
)
result = build_webtris_timeseries(
    workspace_root,
    evidence,
    interval_filter=WebtrisTimeseriesFilter(
        site_ids=("34",),
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 1),
        measurement_states=("missing", "observed"),
    ),
)
series = build_webtris_chart_series(result)
verified = verify_webtris_timeseries(workspace_root, evidence, result)

# A later local process can reopen an accepted daily report by its safe ID;
# no in-memory acquisition receipt is required.
reopened = build_webtris_timeseries_from_accepted_snapshots(
    workspace_root,
    (daily_snapshot_id,),
    interval_filter=result.interval_filter,
)
verified_reopened = verify_webtris_timeseries_from_accepted_snapshots(
    workspace_root,
    (daily_snapshot_id,),
    reopened,
)
```

Accepted snapshots are consumed through their promoted acquisition receipts;
quarantined bytes are consumed through their offline replay receipts and are
re-replayed through the existing binding checks before any row exists. Both
paths re-hash every member and reproduce the recorded parser report exactly.
The receipt-free accepted-snapshot path uses the bounded MAN-03 catalogue
opener, admits only daily reports, refuses conflicting site-day snapshots, and
counts repeated identical IDs as collapsed duplicates. It deliberately does
not attach an accepted daily-quality percentage: the generic accepted quality
manifest lacks the source site-name scope needed for exact parser replay, so
availability stays unreported rather than being inferred.

## Filters and chart data

`WebtrisTimeseriesFilter` admits only evidenced dimensions: selected site
IDs, a bounded source date range, the interval measurement state
(`observed`/`missing`), and a minimum data-availability percentage. Every
WebTRIS site is a per-carriageway identity, so site selection is the only
admitted direction/carriageway dimension; no audited contract defines a
direction column or a site-name decoding rule, and the filter structurally
pins `carriageway_direction_dimension_available`,
`vehicle_class_dimension_available`, and `utc_window_dimension_available` to
`False`. When a minimum availability is requested, site-days without a
verified quality artifact are excluded as `availability_unreported` — never
treated as zero or one hundred percent.

Rows preserve the exact site identity and name, the verbatim source
`Report Date` and `Time Period Ending` strings, the interval index, the
source volume in `vehicles_per_reported_interval`, the source average speed
in mph with its exact deterministic m/s conversion, the availability state,
and full lineage (snapshot ID, member path, member hash, page, row index,
quality snapshot). `build_webtris_chart_series` groups admitted rows into one
series per verified (site ID, site name) identity without aggregation, so a
site renamed between source days never has earlier rows relabelled; missing
intervals stay gaps with explicit `measurement_state`, and every series binds
the result fingerprint and the source-local time-axis basis.

## Duplicates and reconciliation

Two evidence entries for one site-day are identical only when they reference
the same snapshots, raw fingerprints, and parser reports; identical
duplicates collapse to one verified input with the surplus reported in
`identical_duplicates_collapsed`. Anything else covering the same site-day is
refused as `CONFLICTING_DUPLICATE_EVIDENCE` — never arbitrated. The result
carries complete reconciliation counts (evidence supplied/admitted/collapsed,
pages, intervals expected, rows seen/admitted/excluded, missing-measurement
intervals, and per-reason exclusion counts), and rows plus exclusions must
partition every site-day's 96 intervals exactly.

Every persisted result re-derives its internal structure on reload: the
embedded filter, input lineage, rows, exclusions, counts, fingerprints, units,
evidence class, and negative claims are cross-checked by the model validator.
This is tamper-evident self-consistency, not a signature: an actor can create a
different internally consistent artifact with a new fingerprint. Use
`verify_webtris_timeseries` with the original evidence receipts and workspace
before trusting a reloaded result. It repeats the immutable-byte verification,
parser replay, and complete build and requires exact artifact equality. The
supplied/collapsed evidence tallies remain build-time attestations and are
therefore also checked by this reproduction step.
For receipt-free results,
`verify_webtris_timeseries_from_accepted_snapshots` repeats the same build from
the exact safe snapshot-ID inventory and requires artifact equality.

## Why intervals stay source-local strings

The WebTRIS report timestamp timezone is undocumented (`GA-WT-1`), so this
service never fabricates UTC timestamps, never uses retrieval time as
observation time, and keeps `utc_timestamps_available` structurally `False`.
Chart axes are source-local interval labels. Resolving the blocker later is a
versioned policy change in the time-basis contract, not a rewrite of stored
evidence or of these rows.

## Failure and verification

Missing or unmarked workspaces, invalid receipts, mixed evidence classes,
conflicting duplicates, exceeded bounds, tampered accepted or quarantined
bytes, receipt/manifest mismatches, parser-report mismatches, and rejected
parses all fail closed with typed `WebtrisTimeseriesError` codes; a persisted
result that does not reproduce exactly fails as
`RESULT_VERIFICATION_MISMATCH`, and no partial result is produced. The focused
test suite is entirely offline: it uses
injected, explicitly synthetic WebTRIS responses plus the retained official
OGL-recorded fixtures replayed read-only as schema evidence, and covers
snapshot tampering, receipt mismatches, scope mismatches, schema drift,
conflicting and identical duplicates, missing values, unit and timezone
strengthening, input-order invariance, bounds, and persisted-result mutation.
This is candidate offline evidence, not real-source acceptance. No real
WebTRIS acceptance run is claimed; `MAN-03` and `MAN-08` remain planned.

See also: the [controlled WebTRIS acquisition workflow](manchester_webtris_acquisition.md),
the [WebTRIS adapter contract](manchester_webtris_adapter.md), the
[WebTRIS site scene bridge](manchester_webtris_scene.md), the
[Manchester time basis](manchester_time_basis.md), and the accepted
[Gate A source audit](manchester-source-gate-a-audit-v0_7.md).

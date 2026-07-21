# ADR-016: Fixed-Window Metric Semantics

Status: accepted

## Context

TrafficTwin v0.5 `MET-01` requires deterministic metrics over fixed configurable time windows.
Without a declared interval boundary, alignment origin, record anchor, empty-window policy, and
partial-edge policy, the same records can produce different series and a chart can hide missing
evidence. Windowing must also preserve the ordinary metric engine's availability and provenance
contracts.

Canonical tables do not share one event meaning. A task row contains its outcome and always has an
arrival/cohort timestamp, while `completion_time_s` is optional; a trip contains its outcome and
always has a departure/cohort timestamp, while arrival is optional;
infrastructure, vehicle, traffic, and incident rows are observations at a timestamp. No canonical
sampling interval or sensor-completeness field exists.

## Decision

- Use aligned half-open grid intervals `[start, end)`. A record exactly at `end` belongs to the
  later window. Grid bounds are `alignment_origin_s + k * width_s` and are calculated with decimal
  arithmetic derived from the declared numeric inputs.
- Assign records by this versioned anchor policy:

  | Canonical table | Anchor |
  |---|---|
  | tasks | `arrival_time_s` |
  | infrastructure | `timestamp_s` |
  | vehicles | `timestamp_s` |
  | traffic | `timestamp_s` |
  | trips | `departure_time_s` |
  | incidents | `timestamp_s` |

- Treat task and trip results as cohort outcomes. For example, a task that arrives in one window
  and completes later remains in its arrival window; TrafficTwin does not invent a completion
  event timestamp.
- When no explicit range is supplied, infer the smallest aligned envelope containing every
  canonical anchor. When an explicit `[analysis_start_s, analysis_end_s)` is supplied, generate
  every grid window that intersects it and clip only the effective edge bounds.
- Record edge coverage as `effective overlap / grid width`. This is requested-range coverage only;
  it is not sampling density, observation duration, or sensor completeness.
- Let callers explicitly include or exclude partial edge windows. Excluded windows remain in the
  artifact with disposition `excluded_partial` and no `MetricCollection`; they are never hidden.
- Emit empty included windows. Their applicable metrics use the ordinary engine and are
  `unavailable` with ordinary reason codes rather than being fabricated as zero.
- Apply the ordinary deterministic metric engine to the filtered canonical tables, then retain
  the 50 definitions present when this decision was accepted. ADR-018 through ADR-020 extend the
  current applicable total to 60 task, infrastructure, traffic, trip, energy, fairness, and
  contracted spatial/per-RSU definitions. The three comparison definitions are not single-run
  window metrics. Each definition declares its applicability and primary anchor in the generated
  metric catalogue.
- For a multi-table metric such as vehicle-tier completion, independently filter every required
  table by its declared table anchor before the ordinary join. Missing within-window support stays
  unavailable.
- Preserve each metric's availability, reason codes, computation timestamp, input fingerprint,
  definition version, and metadata. Add the window ordinal, grid/effective bounds, coverage,
  boundary, partial flag, base scope, and anchor-policy version.
- Bound one request to 10,000 windows by default and 100,000 at the schema maximum. Reject an
  over-bound request before metric computation.
- Reuse ordinary metric provenance after exact window filtering. A trace and a complete accepted-
  row contribution ledger are available for each included window. These are arithmetic lineage,
  not causal attribution.

## Non-Additive And Boundary Effects

Window results are not generally expected to recombine to the whole-run value. Means,
percentiles, ratios, distinct counts, and grouped objects are non-additive. Saturation episodes
and durations are recalculated from observations inside each window, so a sequence crossing a
boundary is deliberately clipped and may be counted in both adjacent windows. Traffic time
coverage is also local to the observations in a window. Counts can be partitioned only where the
underlying definition and cohort anchor make addition meaningful.

`WindowedMetricSeries.warnings` states this limitation. The implementation does not create an
incident-aligned temporal EvidencePack or run R6; those are separate `DIA-01` work.

## Consequences

- The same input, metric configuration, window configuration, and clock produce the same series.
- Gaps are visible and cannot be mistaken for zero activity.
- Users can reproduce a chart from the JSON artifact because range, alignment, coverage, and
  record anchors travel with the values.
- Cohort outcomes answer "what happened to records starting in this interval", not "what events
  completed during this interval".
- A source with irregular sampling can be windowed, but TrafficTwin cannot claim complete temporal
  observation without a future evidenced coverage contract.
- Windowed artifacts are downloadable and queryable but are not silently persisted as ordinary
  whole-run collections in the registry.

## Acceptance Evidence

- Unit tests cover paired explicit bounds, exact boundary membership, inferred aligned envelopes,
  partial include/exclude behavior, empty windows, rejected evidence, request bounds,
  determinism, and partition invariants across widths and origins.
- Golden tests pin the baseline window contract and selected task/infrastructure/traffic/trip
  values, including unavailable empty intervals.
- CSV, gzip-CSV, Parquet, and collected-streaming inputs produce equivalent window projections.
- Integration tests cover JSON/text CLI output, file export, per-window provenance, and complete
  filtered contribution ledgers.
- UI-service and Streamlit AppTest coverage verify that the Temporal Metrics page delegates to the
  library and renders a typed series.

## Alternatives Considered

- Closed intervals: rejected because adjacent windows would double-assign boundary records.
- Assign every task metric by completion time: rejected because incomplete tasks and some
  completed tasks lack that optional field, and generated/cohort denominators would move to a
  different population.
- Omit empty windows: rejected because it visually compresses gaps and changes temporal meaning.
- Fill empty counts with zero: rejected because no records is an evidence-availability state, not
  proof of zero activity.
- Infer sampling coverage from first/last timestamps: rejected because irregular observations do
  not establish complete sensor operation.
- Sum window results to recreate the whole run: rejected as invalid for most metric families and
  boundary-clipped episodes.

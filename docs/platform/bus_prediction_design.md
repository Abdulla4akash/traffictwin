# Design — Bus prediction layer (platform P-2, and the producer-independent study)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. Doubles as the owner's
producer-independent study: a forecasting model trained on OUR OWN collected BODS data,
validated on held-out days, under the house predeclaration discipline. Zero producer
content anywhere in this slice.**

## 1. What it predicts

From the session archive (attended + scheduled), per hour-of-day over the GM box:

- **Fleet concurrency** — median/max per-snapshot `live_vehicle` count (the honest
  concurrency measure per the 28-July metric-trap lesson — never
  `vehicles_linked_across_snapshots`, which grows with session length).
- **Progression speed** — per-segment aggregate speed (the B2
  `measure_session_progression` statistic; never displacement÷interval, per the same
  session's pitfall list).

Targets: (a) *climatology* — the expected value for hour h and day-type d (weekday /
weekend); (b) *nowcast* — next-hour value given the current hour's observation. Both
with intervals and support counts; thin cells visibly thin, never smoothed over.

## 2. Model — small, honest, upgradeable

Start as climatology + persistence blend: `ŷ(h+1) = α·y(h)·r(h→h+1) + (1−α)·μ(h+1,d)`
where `r` is the climatological hour-to-hour ratio and `α` fitted by least squares.
This family is the *baseline every forecasting paper must beat*; with weeks (not years)
of data it is also the most a model can honestly claim. If the archive grows enough, a
ridge regression on {hour, day-type, last-obs, trend} may be *compared against* it under
the same predeclared protocol — added only if it wins on held-out days. Intervals:
per-(hour, day-type) empirical residual quantiles once ≥5 support days exist; before
that, the cell reports `insufficient_support` rather than an interval.

## 3. The predeclared validation (what makes it a study, not a demo)

A short predeclaration, frozen before the held-out days are scored: chronological split
(first N days fit, last M days held out — no shuffling; time leaks), primary metric MAE
per (hour, day-type) cell with support shown, the persistence-only and
climatology-only baselines reported beside the blend, and a **publishable null fixed in
advance**: "the blend does not beat persistence" is a complete, reportable outcome.
Verdict code committed before the held-out days exist, self-tested on the fit days —
the ceiling-law pattern applied to our own data.

## 4. Data dependency — the honest constraint

Four attended sessions ≈ 4 distinct day-windows: enough to *fit* climatology cells for
those windows, NOT enough for held-out-day validation. The study's calendar is therefore
set by the [scheduled runner](bods_scheduled_runner_design.md): ~7 days of scheduled
sessions → first fit; ~14 days → first honest held-out verdict. This is why the runner
builds first, and the design says so rather than hiding the dependency.

## 5. Provenance

Fit reads only committed/receipted session measurement JSONs (each digest recorded in
the fit artifact); outputs typed `forecast` with `evidence: False`; the forecast page
displays the fit digest and source-session count. Session-scoped identity is untouched —
the model consumes aggregates only, so the privacy boundary is inherited, not
re-negotiated.

## 6. Deliverables

`bus_prediction.py` (dataset build, fit, predict, validate), the predeclaration doc, the
verdict script, the results record after the held-out window, and the forecast page
(see [dashboard design](dashboard_design.md)). Register row when the verdict lands.

## 7. Testing

Deterministic fixtures (synthetic session aggregates with known climatology); the
chronological-split guard (a shuffled split must be refused); interval-support rules;
verdict-script self-test. No live data in tests.

## 8. What this is not

Not a traffic model (buses only); not causal (fleet size and time-of-day covary — the
speed–density record's own caveat carries over verbatim); not transferable beyond the
GM box without new data — which is precisely the Bangladesh pitch's data-gap argument,
stated here so the two documents agree.

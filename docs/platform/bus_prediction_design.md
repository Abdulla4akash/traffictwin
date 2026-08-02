# Design — Bus prediction layer (platform P-2, and the producer-independent study)

**Status: IMPLEMENTED as an aggregate-only forecasting backend in Phase 143 (`9d804f3`) at
the `owner_approved_candidate` ceiling. The same phase closed the scheduled-runner
progression-aggregate dependency. It doubles as the owner's producer-independent study: a
forecasting model trained only on aggregate BODS session measurements and designed for
held-out service-date validation under the house predeclaration discipline. Zero VEC
producer data, code, parameters or results enter this slice. The real archive still lacks
enough eligible service dates for a held-out verdict, so no validated forecast result is
claimed.**

## 1. What it predicts

From eligible aggregate attended or scheduled session measurements,
per local hour-of-day over the fixed Greater Manchester BODS box:

- **Fleet concurrency** — median/max per-snapshot `live_vehicle` count (the honest
  concurrency measure per the 28-July metric-trap lesson — never
  `vehicles_linked_across_snapshots`, which grows with session length).
- **Bus progression speed** — per-fix-to-fix-segment aggregate speed (the B2
  `measure_session_progression` statistic; never displacement÷interval, per the same
  session's pitfall list). It includes stops, signals and layover and is never labelled
  general road-traffic speed.

Targets: (a) *climatology* — the expected value for hour h and day-type d (weekday /
weekend); (b) *nowcast* — next-hour value given the current hour's observation. Both
with intervals and support counts; thin cells visibly thin, never smoothed over.

The DfT hourly demand profile named in the platform plan is a separate public-road
descriptive series. It may be shown as a digested historical climatology, but it is not a
bus target, ground truth for BODS, or a joint feature until a separate cross-source protocol
is frozen. No bus/road causal comparison is implied.

## 2. Model — small, honest, upgradeable

Start as climatology + persistence blend: `ŷ(h+1) = α·y(h)·r(h→h+1) + (1−α)·μ(h+1,d)`
where `r` is the climatological hour-to-hour ratio and `α` is fitted by least squares then
constrained to `[0,1]`. Cells with a zero/unsupported ratio denominator refuse rather than
divide or borrow another day type.
This family provides transparent persistence and climatology baselines; with weeks (not
years) of data it is also the most this project can honestly claim. If the archive grows enough, a
ridge regression on {hour, day-type, last-obs, trend} may be *compared against* it under
the same predeclared protocol — added only if it wins on held-out days. Intervals:
per-(hour, day-type) empirical residual quantiles once ≥5 support days exist; before
that, the cell reports `insufficient_support` rather than an interval.

## 3. The predeclared validation (what makes it a study, not a demo)

A short predeclaration is frozen before held-out service dates are inspected or scored. It
fixes N fit dates, M held-out dates, minimum complete windows per date, eligible refusal/gap
rules, and the exact evaluation horizon. All windows from one `Europe/London` local service
date stay on the same side of the chronological split; no row-level shuffle, UTC-hour leak,
or BST/GMT relabelling is allowed. Primary metric: MAE per (hour, day-type) cell with
support shown. Persistence-only and climatology-only baselines are reported beside the
blend, and a **publishable null fixed in advance** — "the blend does not beat persistence"
— is a complete outcome. Verdict code is committed and self-tested using fit dates only
before the held-out dates exist.

Forecast records remain `evidence: false`. A later held-out evaluation is a separate
analysis artifact: it receives no scientific standing merely because code ran, and may
reach at most its predeclared/admitted `owner_approved_candidate` ceiling. Thin or absent
day-type cells yield `insufficient_support`, never a pooled headline.

## 4. Data dependency — the honest constraint

Four attended windows on two dates are enough to demonstrate dataset construction, NOT to
fit a weekday/weekend climatology or validate on held-out dates. Readiness is based on the
number of eligible, distinct local service dates and per-cell support after refusals — not
"~7 days" or "~14 days" of wall-clock operation. In particular, 14 calendar days can
still leave fewer than five weekend support dates.

Phase 143 extended the [scheduled runner](bods_scheduled_runner_design.md) to write one
digest-bound `bods_session_activity_aggregate` containing concurrency-by-snapshot and hourly
`SessionProgressionMeasurement`. It computes both inside the same fresh session-scoped salt
and discards that salt. A separate owner-run builder can create the identical aggregate for
stored attended sessions through the reviewed identity boundary. The forecaster still may
not reopen arbitrary raw BODS data, persist identifiers or infer cross-session identity.
Operational scheduling has not been activated, and the four measured windows on two dates
remain insufficient for the predeclared held-out study.

## 5. Provenance

Fit reads only schema-validated, digest-verified aggregate measurement JSONs whose session
records reconcile to accepted snapshots. A source need not be committed if it is private
workspace material, but every logical session id, content digest, eligibility decision and
aggregate schema version is recorded in the fit artifact. Repository outputs contain no
absolute/private paths, raw identifiers, salts, or snapshot bytes. Forecasts are typed
`forecast: true`, `evidence: false`, `causal: false`; the forecast page displays the fit
digest, source-date/session counts, per-cell support and exclusions. Session-scoped identity
is untouched because the model consumes aggregates only.

## 6. Deliverables

Delivered surfaces are `bus_prediction.py` (aggregate dataset build, fit, predict,
validate), the scheduled/attended activity-aggregate boundary and builder, the proposed
unsigned predeclaration, and the deterministic verdict self-test. Phase 145 connected the
backend to the [dashboard](dashboard_design.md). No real held-out results record or register
row exists; either is created only after an authorised analysis is completed and admitted.
No participant evaluation is claimed.

## 7. Testing

Deterministic fixtures (synthetic session aggregates with known climatology); schema/digest
and aggregate-only input gates; whole-local-date chronological splitting; DST fixtures;
duplicate/session-overlap refusal; unsupported ratio and interval-support rules; baseline
comparisons; forecast labelling; private-path/identifier rejection; and verdict-script
self-test. A dependency test refuses speed fitting when only Phase-139 cadence artifacts
exist. No live network or raw BODS data in tests.

## 8. What this is not

Not a general traffic model (the learned targets are buses only); not causal (fleet size,
time of day, service schedules and general congestion covary); not validated until the
predeclared held-out service dates exist; not transferable beyond the fixed GM box without
new data. The separate DfT profile does not repair those limits. This measured lack of
transfer support informs the Bangladesh funding direction but is not itself evidence about
Dhaka.

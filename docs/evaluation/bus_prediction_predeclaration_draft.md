# Bus Forecast Held-Out Validation — Predeclaration (PROPOSED — UNSIGNED)

**Status: PROPOSED/UNSIGNED draft, `owner_approved_candidate` ceiling. Nothing here is
approved, no held-out service date exists yet, and no evaluation may run until a human
completes the sign-off table below binding this document's final SHA-256. This is the
producer-independent study's protocol: zero VEC producer data, code, parameters or
results are involved anywhere in it.**

Design: [`docs/platform/bus_prediction_design.md`](../platform/bus_prediction_design.md)
(REVIEWED). Implementation: `traffictwin.platform.bus_prediction`
(`bods-bus-forecast-1.0`, Phase 143).

## 1. Question and hypothesis

Does a climatology + persistence blend forecast next-hour Greater Manchester bus-fleet
activity better than persistence alone? Targets: per-snapshot fleet concurrency
(median and max `live_vehicle`) and hourly bus progression speed, per (day-type, local
hour) cell. The predeclared **publishable null — "the blend does not beat persistence" —
is a complete outcome** and will be reported as such.

## 2. Data and eligibility (fixed before any held-out date is inspected)

- Sources: `bods_session_activity_aggregate` artifacts only (schema-validated,
  digest-recorded, private-content screened, duplicate-refused), from scheduled sessions
  and owner-built attended aggregates.
- Eligibility: a session needs at least **10 accepted snapshots** (proposed
  `min_snapshots_per_session=10`); a local service date needs at least **3 of its 4
  scheduled windows** captured to count as complete (owner decision D2 below).
- Whole-`Europe/London`-local-service-date discipline: every window of one local date
  stays on one side of the split; no row-level shuffle, no UTC-hour leak, no BST/GMT
  relabelling. Aggregates declare their local date and hours at capture time; the
  builder never re-derives them.

## 3. The chronological split (rule, not dates)

Held-out dates cannot be named yet — the archive does not exist. The RULE is fixed
instead: order all eligible complete dates chronologically; the **first N form the fit
set and the last M the held-out set**, with proposed **M = 5, of which at least 2 are
weekend dates**; N is everything before them once readiness (design §4) is met. The
evaluation runs ONCE on the held-out set. If weekend support has not reached 2 dates,
weekend cells report `insufficient_support` and are excluded from the verdict rather
than pooled.

## 4. Model, horizon, endpoints

- Model: `y(h+1) = a * y(h) * r(h->h+1) + (1-a) * mu(h+1, d)`, `a` least-squares on fit
  dates, clamped [0,1]; unsupported ratio cells refuse. Fitted once on the fit set;
  frozen before scoring.
- Horizon: next local hour only; no cross-midnight nowcast.
- Primary metric: **MAE per (hour, day-type) cell with support counts shown**, blend
  beside persistence-only and climatology-only baselines.
- Intervals: per-cell empirical residual quantiles at >=5 support dates; thinner cells
  report `insufficient_support`.

## 5. Verdict rule (fixed in advance)

Per target, over all evaluable held-out consecutive-hour pairs: pooled MAE of the blend
strictly below the persistence baseline → `BLEND_BEATS_PERSISTENCE`; otherwise
`NULL_PERSISTENCE_NOT_BEATEN` (publishable); no evaluable pairs → `NOT_EVALUABLE`.
The verdict code is committed (`evaluate_held_out` + `verdict_self_test` in
`bus_prediction.py`) and self-tests on fit dates only before any held-out date exists.
No other reading is licensed; a ridge-regression comparison, if ever added, needs its
own predeclaration.

## 6. Interpretation limits binding on any output

- Forecasts and evaluations are `evidence: false`, non-confirmatory, non-causal; the
  ceiling is `owner_approved_candidate`.
- Buses only — never general road traffic; the fixed GM box only — no transfer claim,
  including to Dhaka; the DfT profile stays a separate descriptive series under its own
  future protocol.
- A held-out evaluation gains no standing merely because code ran.

## 7. Owner decisions required before signing

- **D1**: held-out size M (proposed 5, >=2 weekend) and the weekend-shortfall handling.
- **D2**: minimum complete windows per eligible date (proposed 3 of 4).
- **D3**: minimum snapshots per session (proposed 10).
- **D4**: whether attended aggregates join the fit set or stay descriptive context.

## 8. Sign-off (EMPTY — a human must complete this)

| field | value |
|---|---|
| approved_by | |
| approved_role | |
| approved_at_utc | |
| predeclaration_sha256 (of the FINAL bytes) | |

The evaluation binds this document's final digest; editing after approval voids it.

# Design — Scheduled BODS session runner (implements platform decision P-D2)

**Status: PROPOSED design, `owner_approved_candidate` ceiling. Implements the owner's
tentative-yes to unattended acquisition (30 July,
[platform plan](../traffictwin-data-platform-v1-plan.md) §7). The accepted acquisition
rules are UNCHANGED — the only thing this slice changes is who triggers a session.**

## 1. Purpose

Turn the four hand-run observation sessions into a continuous archive. Every unattended
day adds training data for the [bus prediction layer](bus_prediction_design.md) and
freshness to the [platform inventory](dashboard_design.md). The measured 66–68 s feed
cadence fixes the sampling design; nothing new is learned by polling faster.

## 2. Boundary — inherited verbatim, none of it relaxed

≥60 s between requests; one request in flight at a time (the existing
`coordinated_bods_live_refresh` lock); GM bounding box; `BODS_API_KEY` from the
environment, never echoed or persisted; every snapshot quarantined with manifest +
member sha before any read; per-session in-process salt (session-scoped identity,
discarded at session end); aggregate-only outputs; refusal ledger with
continue-on-fail-closed-refusal and the 8-consecutive-refusals stop (the
`bus_attended_session.py` semantics, reused not reimplemented).

## 3. Architecture

One new module `bods_scheduled_sessions.py` + one runner script. The runner wraps the
*existing* attended-session core; the schedule is data, not code:

```
schedule.json (committed):
  sessions: [ {label: "night",   start_local: "23:30", snapshots: 15},
              {label: "dawn",    start_local: "05:30", snapshots: 52},
              {label: "am_peak", start_local: "08:00", snapshots: 52},
              {label: "pm_peak", start_local: "16:30", snapshots: 85} ]
  interval_seconds: 65
```

The four windows mirror the four measured density points so scheduled data extends the
existing series rather than starting a new one. ~204 snapshots/day ≈ well inside any
rate concern at one request/65 s.

**Trigger:** a single long-lived detached supervisor (`start_new_session` +
`caffeinate -i` + pid file — the pattern proven by the campaign chain), started once by
the owner, which sleeps until the next window. **Not launchd.** The Sparse-64 homecoming
deviations are the direct design input, and there are now **two** of them: the first
launchd relaunch re-ran a completed step 147 times, and — after that supervisor was
repaired — a second relaunch still produced one more repeat, because the terminal record
was written *after* a fallible cleanup step that a restart could interrupt. This
project's own evidence therefore says two things: launchd relaunch semantics violate
run-once guarantees, and a repaired wrapper is not a guarantee either — only completion
state written *before* anything fallible is.

**Run-once guards, three layers:** (1) a pid-file singleton — a second supervisor
refuses to start; (2) a per-(date, window) completion marker written by the session
writer itself (the `randomTrips --validate` lesson: the writer writes the marker, not
the wrapper), and written **atomically before any fallible post-step** — aggregation,
report rendering, retention pruning all happen strictly after the marker exists, so an
interruption at any point can only lose post-processing (recoverable from quarantine),
never the ran-once fact (the Sparse-64 terminal-write ordering lesson, adopted here
from the start rather than after our own deviation); (3) a window that is already past
its start when the supervisor wakes is **skipped and ledgered**, never run late — late
data would silently shift the density point the window exists to measure.

## 4. Provenance and outputs

Each scheduled session produces exactly what an attended one does — quarantine dir,
refusal ledger, measurement JSON, session record — plus `triggered_by: "schedule"` and
the schedule digest in the session record, so scheduled and attended sessions are never
conflatable. Outputs land under `<workspace>/manchester/scheduled/<date>/<label>/`;
nothing ever writes to the attended sessions' paths (the 28-July default-path clobber
near-miss is the precedent). Daily disk ≈ 204 snapshots × ~250 KB ≈ 50 MB/day; a
declared retention rule (raw quarantine pruned after N days once aggregates are
committed, N owner-decided, default 14) keeps the archive bounded.

## 5. Failure policy

A session that hits the 8-consecutive-refusal stop ends and is ledgered; the supervisor
moves to the next window — it never retries a window. A missing/invalid API key refuses
at supervisor start, not mid-window. Machine asleep or supervisor dead = windows
silently skipped; the inventory page surfaces gaps (freshness), which is the monitoring
— no alerting subsystem in v1.

## 6. Testing

Unit tests with an injected clock and fake acquisition function: window selection,
skip-late rule, completion-marker idempotency, singleton refusal, ledger contents,
schedule-digest stamping. No live network in tests. One owner-attended smoke of a real
1-snapshot scheduled window before first unattended day.

## 7. Out of scope

Streaming (proven unnecessary — plan §4); schedule UI editing; multi-region boxes;
retention automation beyond the single rule above.

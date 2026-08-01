# Design — Scheduled BODS session runner (implements platform decision P-D2)

**Status: IMPLEMENTED in Phase 139 (`de66002`), at the
`owner_approved_candidate` ceiling. The owner-attended one-snapshot smoke and the owner's
separate unattended launch remain outstanding; no scheduled acquisition has been claimed.
This implements the owner's tentative-yes to unattended acquisition (30 July,
[platform plan](../traffictwin-data-platform-v1-plan.md) §7). The accepted acquisition
rules are UNCHANGED — the only boundary this slice changes is who triggers a session.**

## 1. Purpose

Provide the capability to extend the four hand-run observation sessions into a scheduled
archive. A successfully captured unattended day can add aggregate inputs for the
[bus prediction layer](bus_prediction_design.md) and freshness to the
[platform inventory](dashboard_design.md). The measured 66–68 s feed cadence fixes the
sampling design; nothing new is learned by polling faster. Implementation alone does not
create a new session, and the owner smoke/launch boundary is intentionally visible.

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

**Clock boundary:** `start_local` is interpreted in the supervisor host's local timezone.
Before both the attended smoke and the unattended launch, the owner must verify that the
host is using `Europe/London` and that the displayed UTC offset is correct for BST/GMT.
The current implementation does not pin an IANA timezone in the schedule, so moving the
supervisor to another host without this check is a recorded portability limitation, not
permission to shift the observation windows.

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
report rendering and the retention-eligibility report all happen strictly after the
marker exists, so an interruption at any point can only lose post-processing (recoverable
from quarantine),
never the ran-once fact (the Sparse-64 terminal-write ordering lesson, adopted here
from the start rather than after our own deviation); (3) a window that is already past
its start when the supervisor wakes is **skipped and ledgered**, never run late — late
data would silently shift the density point the window exists to measure.

## 4. Provenance and outputs

Each scheduled session produces a completion marker before fallible post-processing, then
a refusal ledger, aggregate cadence measurement where at least two snapshots were accepted,
and a session record. The records carry `triggered_by: "schedule"` and the schedule digest,
so scheduled and attended sessions are never conflatable. Outputs land under
`<workspace>/manchester/scheduled/<date>/<label>/`; nothing ever writes to the attended
sessions' paths (the 28-July default-path clobber near-miss is the precedent).

Daily raw quarantine growth is estimated at ~204 snapshots × ~250 KB ≈ 50 MB/day. The
implemented `retention_report_days` value (default 14) only identifies scheduled snapshots
that are old enough and have an aggregate cadence measurement. It deletes nothing. Private
raw bytes may be removed only through the existing owner-invoked, confirmation-gated
retention flow. Consequently the archive is not automatically bounded; the inventory must
surface both the eligibility count and the fact that owner action is pending.

## 5. Failure policy

A session that hits the 8-consecutive-refusal stop ends and is ledgered; the supervisor
moves to the next window — it never retries a window. A missing API key refuses at
supervisor start; an invalid key fails closed through the acquisition refusal path. A
same-day window found beyond the five-minute tolerance is skip-marked and never run late.
Windows from earlier dates leave an absence rather than retroactive markers, so the
inventory must infer those gaps from schedule-versus-record reconciliation. This freshness
view is the monitoring; no alerting subsystem exists in v1.

## 6. Testing

Implemented unit tests use an injected clock and fake acquisition function for window
selection, skip-late behaviour, completion-marker idempotency, singleton refusal, ledger
contents, schedule-digest stamping, shared attended/scheduled refusal semantics, and the
delete-nothing retention report. Phase 139 recorded 22 focused passes; no test opens the
network. One owner-attended smoke of a real one-snapshot scheduled window is still required
before the first unattended day, followed by an explicit owner launch. Neither is delegated
to an agent by this design.

## 7. Out of scope

Streaming (proven unnecessary — plan §4); schedule UI editing; multi-region boxes;
automatic retention deletion; hourly progression aggregation for forecasting. The last
item is a real downstream gap: Phase 139 emits cadence aggregates, not the
`measure_session_progression` hourly series. The bus-prediction slice must close that
aggregate-only contract before scheduled sessions can be claimed as progression-speed
training data.

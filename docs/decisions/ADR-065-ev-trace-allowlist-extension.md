# ADR-065: Reviewed Admission of the `ev` Trace

- Status: accepted (owner-delegated reviewed allowlist extension, 27 July 2026)
- Date: 2026-07-27
- Capability: none accepted or changed; extends the VEC-07 reviewed-trace set consumed by
  [ADR-061](ADR-061-vec-fresh-run-scientific-admission.md) fresh-run admission, repeating
  the [ADR-062](ADR-062-inc-trace-allowlist-extension.md) pattern.

## Context

The `ev` trace is the Champions League event night in the Etihad/Co-op Live event district
(17:30–24:00 window per the producer's provenance sidecar) — the supervisor's own stadium
what-if scenario from the project's founding meeting, and the natural next study after the
completed capacity pilot. VEC-07's `PINNED_REVIEWED_TRACES` held only the weekend and
incident traces, so an `ev` request refused, and ADR-062 recorded that each later admission
"repeats this measured probe and its own decision record". This is that record, executed
under the standing in-session owner delegation of 27 July 2026 ("take reasonable choices
and keep working").

`ev` is one of the five Gate-A-audited source pairs; the accepted VEC-07 boundary wording
already reads "an exact Gate-A-reviewed trace".

## Decision

1. **Measure first.** Before any edit, both `ev` blobs were read from the local pinned
   tos-data clone at the audited commit via `git cat-file` (no fetch) and verified against
   the Gate-A hashes, and the vehicle identity snapshot was built with the production code
   path: T=23,400, maxN=175, 1,898,428 masked vehicle-seconds, 9,130 occupancy spans /
   9,129 distinct vehicles, zero missing and zero inactive identity cells, reconciled in
   1.51 s. Evidence:
   `docs/integration/evidence/vec_ev_trace_admission_probe_20260727.json`.
2. **Extend the allowlist by exactly one audited identity.** `PINNED_REVIEWED_TRACES`
   gains the `ev` hash → `traces/trace_ev_fullrsu.npz`; fresh-run admission's scenario map
   gains the matching `occupancy_ev.csv` binding. Nothing else in the runner — controls,
   preflight, timeout bounds, actor set, output gate — changes.
3. **The weekday traces stay refused.** `wd_am` and `wd_pm` remain outside the allowlist;
   a test pins the allowlist to exactly the three admitted identities so growth stays
   deliberate.

## Consequences

**What this unblocked.** An `ev` execution can now pass VEC-07 preflight and enter
fresh-run scientific admission — the stadium what-if scenario is reachable end to end.
Admission alone enables no experiment: any `ev` study still requires its own
predeclaration and an approval-gated campaign, unchanged.

**Open measured risk.** No `ev` execution has been timed. The trace is 23,400 steps
(6.5 hours) at 175 slots; because slot width dominates runtime (the 139-slot weekend full
run measured 225.7 s while the 2,488-slot incident hour measured 3,556 s), the expected
cost is minutes-scale — but the first execution must be treated as a timing measurement
against the 7,200-second request ceiling, which remains an escalation trigger, never a
bound to raise.

**What it did not change.** No reproduction grade, no scientific result, no capability
movement. The scenario-identity description cites the producer's sidecar at upstream
commit `6e56393` (a documentation-only commit; the data blobs are identical at the audited
commit); the pinned clones remain unfetched pending the R1 re-pin decision.

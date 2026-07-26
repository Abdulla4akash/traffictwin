# ADR-062: Reviewed Admission of the `inc` Trace

- Status: accepted (owner-directed reviewed allowlist extension, 26 July 2026)
- Date: 2026-07-26
- Capability: none accepted or changed; extends the VEC-07 reviewed-trace set consumed by
  [ADR-061](ADR-061-vec-fresh-run-scientific-admission.md) fresh-run admission.

## Context

The predeclared first experiment — the capacity squeeze — targets the incident trace
(`inc`), the scenario with the strongest resource-pressure signal (peak 2,488 concurrent
slots in one hour). VEC-07's `PINNED_REVIEWED_TRACES` contained only the weekend trace, so
an `inc` request refused with "trace is neither reviewed nor backed by a VEC-06 receipt",
and fresh-run admission refused with `UNREVIEWED_TRACE_REFUSED`. The independent
experiment-readiness review recorded exactly two remedies: an accepted VEC-06 receipt, or a
reviewed extension of the allowlist.

`inc` is not an arbitrary trace. It is one of the five Gate-A-audited source pairs whose
identities, shapes, and reconciliation results are recorded in the source-snapshot audit —
and the accepted VEC-07 boundary wording already reads "an exact Gate-A-reviewed trace".
The single-entry pin was a conservative implementation choice, not a recorded scientific
restriction on the other audited traces.

## Decision

1. **Measure first.** Before any edit, both `inc` blobs were read at the audited tos-data
   commit and verified against the Gate-A hashes, and the vehicle identity snapshot was
   built with the production code path: T=3,600, maxN=2,488, 8,747,692 masked
   vehicle-seconds, 5,307 occupancy spans, reconciled in 1.14 s. Evidence:
   `docs/integration/evidence/vec_inc_trace_admission_probe_20260726.json`.
2. **Extend the allowlist by exactly one audited identity.** `PINNED_REVIEWED_TRACES`
   gains the `inc` hash → `traces/trace_inc_fullrsu.npz`; fresh-run admission's scenario
   map gains the matching `occupancy_inc.csv` binding. Nothing else in the runner —
   controls, preflight, timeout bounds, actor set, output gate — changes.
3. **The other audited traces stay refused.** `wd_am`, `wd_pm`, and `ev` remain outside
   the allowlist per the review's "admit only the trace needed for the first study"; each
   later admission repeats this measured probe and its own decision record. A test pins
   the allowlist to exactly the two admitted identities so growth stays deliberate.

## Consequences

**What this unblocked.** A full-length `inc` execution can now pass VEC-07 preflight and,
once completed, enter fresh-run scientific admission (ADR-061) — the capacity-squeeze
pilot's target scenario is reachable end to end.

**Open measured risk.** The VEC-07 request ceiling is 7,200 seconds while the slowest
historical source run took 15,305.9 seconds. The weekend full run measured locally at
225.7 seconds, but `inc` arrays are ~18× wider (2,488 versus 139 slots); the first `inc`
execution must be treated as a timing measurement, and if it approaches the ceiling the
escalation question goes to the owner rather than the bound being silently raised.

**What it did not change.** No reproduction grade, no scientific result, no capability
movement, and no statement about the informal "calm/stressed" scenario labels, which
remain untracked classifications.

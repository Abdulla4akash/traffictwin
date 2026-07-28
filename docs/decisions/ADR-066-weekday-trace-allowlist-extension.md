# ADR-066: Reviewed Admission of the Weekday Peak Traces (`wd_am`, `wd_pm`)

- Status: accepted (owner-delegated reviewed allowlist extension, 28 July 2026)
- Date: 2026-07-28
- Capability: none accepted or changed; extends the VEC-07 reviewed-trace set consumed by
  [ADR-061](ADR-061-vec-fresh-run-scientific-admission.md), repeating the
  [ADR-062](ADR-062-inc-trace-allowlist-extension.md)/[ADR-065](ADR-065-ev-trace-allowlist-extension.md)
  pattern for the last two Gate-A-audited pairs.

## Context

The three-trace grid bracketed the capacity outcome-sensitivity threshold between 175 and
2,488 concurrent slots. The weekday peak traces were probed (read-only, `git cat-file` at
the audited commit, no fetch) expecting intermediate density; both reconciled exactly and
both measured LOW density (`wd_am` maxN=215, `wd_pm` maxN=163) — itself a finding: only
the collapse hour is dense in this district's trace set. Admitting them completes the
five-regime sweep and slightly tightens the bracket.

## Decision

1. **Measured first.** Both blob pairs match the Gate-A hashes exactly at the audited
   tos-data commit, and both identity snapshots reconcile with the production code path:
   `wd_am` T=10,800, maxN=215, 1,166,439 masked vehicle-seconds, 5,381 spans, 0
   missing/inactive; `wd_pm` T=25,200, maxN=163, 2,621,666 masked vehicle-seconds,
   12,232 spans, 0 missing/inactive. Evidence:
   `docs/integration/evidence/vec_wd_traces_admission_probe_20260728.json`.
2. `PINNED_REVIEWED_TRACES` and the fresh-admission scenario map gain both identities;
   tests pin the allowlist to exactly five and assert unknown hashes stay refused.
3. Nothing else in the runner changes; the 7,200 s ceiling stands.

## Consequences

All five Gate-A source pairs are now reachable end to end, each admitted only after its
own measured probe. No scientific use is enabled by admission alone; every study still
requires its own predeclaration and approval.

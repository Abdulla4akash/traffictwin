# E0 — Accounting and Evaluator Validation

## Purpose

Establish that the evaluator represented the lifecycle of every offered task before interpreting any scheduler performance.

## Requirements

- Offered tasks reconcile to admitted tasks plus all declared rejection/unavailability categories.
- Every active task has one terminal outcome.
- Rejected/unavailable work is not executed.
- V2I and vehicle service-work ledgers conserve.
- Sequential finite-queue and explicit reject semantics do not silently lose work.
- Deadline and latency denominators distinguish offered, admitted and deadline-met tasks.

## Result

The corrected bounded smoke and 3,600-step strongest-link reference passed the required accounting, finite-value, terminal-outcome, V2I-work and vehicle-work checks. E0 was a measurement-validity foundation, not a scheduler-performance experiment.

## Authoritative identities

- Full E0 evidence commit: `29d8945862b7df1bd5d7879ba1d980a388f6be0d`
- Corrected smoke record commit: `1c344e1061bba5da9521aad8c170c7d1228e9566`
- Full-reference manifest SHA-256: `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f`
- Smoke manifest SHA-256: `8d81cf30f1ada3e9af7c799c9ebd0e01a427a67c570f583b658b11717a5eab93`
- Full validation SHA-256: `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa`
- Raw-root checksum ledger SHA-256: `688baf8155afb848487a3b1393066e36f01e20560bd178ede03d55f4bbc3fec4`

## Public evidence

The [full validation record](evidence/e0_full_reference_validation_v1.json) and both manifests are byte-identical public-safe copies. Their hashes are listed in [checksums](evidence/checksums.sha256).

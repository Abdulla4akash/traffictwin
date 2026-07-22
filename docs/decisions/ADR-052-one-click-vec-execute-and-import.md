# ADR-052: One-Click VEC Execute-and-Import Orchestration

- Status: accepted
- Date: 2026-07-22
- Capability: `VEC-10` extension (`vec-execute-and-import-1.0`)

## Context

The accepted VEC-07 runner executes the audited evaluator from typed requests, and VEC-10 exposes
request-specific preflight and foreground execution through CLI/UI. Completed results stayed on
disk as receipts and were never registered, so imported-results pages could not show locally
executed evidence, and users had to hand-author request JSON. A one-click workflow must not become
a second evaluator, bypass preflight, invent scientific claims, or write ad hoc SQLite.

## Decision

1. Add a typed orchestration library (`traffictwin.integration.vec_orchestration`) that composes
   the existing accepted services in a fixed order: registry-destination admission, VEC-07
   preflight, VEC-07 execution, byte-exact receipt/output revalidation from disk, current
   external-repository and raw-input immutability verification, and one registry import. No stage
   recomputes VEC-07/VEC-08/VEC-09 logic.
2. Accept only two closed repository-defined presets: a two-step smoke run and the exact accepted
   VEC-08 protocol-seed full run, both over the reviewed weekend trace and audited UK-2030
   Model-C actor. No executable, module, flag, environment variable, Git reference, URL, or
   free-form command text is accepted; a receipt whose request does not match a preset
   fingerprint exactly is refused at import.
3. Import through the existing `Registry.register_bundle_import` pathway (no schema migration):
   `bundle_id = vec-exec:<receipt fingerprint>`, `run_id = vec:exec:<receipt fingerprint[:16]>`,
   and an idempotency fingerprint equal to the import record's stable fingerprint, which excludes
   only the import wall-clock time. Re-import of identical evidence is idempotent; a differing
   record for the same identity raises a visible `RegistryConflictError`.
4. Bind the immutable `VecExecutionImportRecord` to the typed request and its fingerprint, the
   preflight fingerprint taken from the receipt, the receipt file SHA-256 and receipt
   fingerprint, the output fingerprint with per-file hashes and sizes, the exact audited commits,
   runtime evidence, the preset and its evidence grade, and the importer version.
5. Keep scientific truth literal in the record: scientific admission is `unavailable` with
   standing reason codes (the accepted VEC-09 admission binds the audited source run only);
   deadline success is never physical completion; action selection is never confirmed transfer;
   aggregate energy is never per-task energy; smoke output is never a scientific finding; import
   grants no publication permission. Evidence grades separate structural smoke execution from an
   unverified-reproduction full protocol run, which stays distinct from `_s102` best-of-seeds
   evidence.
6. Refuse to import failed, timed-out, cancelled, rejected, partial, malformed, or
   source-mutating executions; refuse unsafe result/registry paths, symlinks, and registry
   destinations inside the result directory or either external repository. The registry
   destination is admitted before execution starts.
7. Expose the workflow through one CLI command (`integration vec execute-and-import`) plus a
   bounded re-import command (`integration vec import-result`), and one explicit
   "Validate, Run and Import" action in the VEC workbench that shows factual workload properties,
   requires explicit confirmation for the long full run, and displays stages, fingerprints,
   inventory, and limitations. Execution remains foreground-only.
8. Seed Streamlit session state from the configured UI settings: `ensure_session_state` now
   honours `TRAFFICTWIN_REGISTRY_PATH` (and configured TOS/fixture paths) so pages no longer fall
   back to `data/registry/traffictwin.sqlite` when a demo workspace registry is configured, while
   never overwriting an intentional in-session selection.

## Consequences

- One explicit action produces registered, inspectable, structurally graded local execution
  evidence with end-to-end fingerprint bindings and proven source immutability.
- Local executions become visible in registry-backed pages without any new scientific claim;
  unavailable evidence stays unavailable with reasons rather than zeros.
- Re-running a preset creates a distinct record (different receipt identity); re-importing the
  same published result is deterministic and idempotent.
- Reproduction grading still requires the separate VEC-08 verification over a calibration pair;
  the one-click workflow deliberately does not run it.

## Acceptance evidence

Unit, UI, CLI, and integration tests cover exact preset fingerprints, preflight gating without
execution, no-import on failed/timed-out/cancelled/malformed/mutated results, single-creation
import, idempotent re-import, visible fingerprint conflict, unsafe destination refusal, literal
semantic guards, configured-registry session-state regression, CLI success/failure states, and a
real two-step audited-evaluator acceptance run with before/after external repository state proof.

## Rejected alternatives

- A second simplified evaluator or embedded command construction: rejected; only VEC-07 executes.
- A new registry table/migration for executions: rejected; the existing idempotent
  `register_bundle_import` conventions already provide identity, conflict, and payload storage.
- Importing failed runs for debugging: rejected; failure evidence lives in the typed workflow
  receipt and runner receipts, not the scientific registry.
- Automatic VEC-08 reproduction grading inside the one-click flow: rejected; it needs a
  calibration pair and separate review, and silently attaching grades would overstate evidence.
- Reusing the accepted VEC-09 admission for local runs: rejected; its prerequisites bind the
  audited source instrumented run, not local executions.

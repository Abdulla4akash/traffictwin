# ADR-063: Bounded, Approval-Gated VEC Campaign Execution

- Status: accepted (owner-directed, 26 July 2026)
- Date: 2026-07-26
- Capability: none accepted or changed. Completes the experiment-readiness instrument alongside
  [ADR-061](ADR-061-vec-fresh-run-scientific-admission.md) and
  [ADR-062](ADR-062-inc-trace-allowlist-extension.md).

## Context

After fresh-run admission and `inc` trace admission, one gap from the independent
experiment-readiness review remained open: "campaign orchestration, timeout, disk, memory,
concurrency and failure-recovery budgets" did not exist. A predeclared 12-cell design could
only be executed by hand — twelve manual library calls, no declared budget, no resumability
after an interruption, and nothing binding the executed runs to the design they were meant to
test. Two further gaps compounded it: no interface existed to register an `Experiment` plan at
all (STA-01 needs one for its pairing seed set), and nothing prevented an exploratory pass from
consuming the seeds reserved for the confirmatory estimate.

The measured cost of an `inc` run made this urgent rather than cosmetic. The weekend trace runs
in 225.7 s; the first full-length `inc` execution exceeded 30 minutes of wall-clock at ~370%
CPU. A twelve-cell pilot is therefore an overnight operation, and an overnight operation that
cannot resume after an interruption is one that will be restarted from zero.

## Decision

1. **Approval is a required, byte-bound input.** A campaign design cannot be constructed
   without a typed approval naming a real approver and role plus the SHA-256 of the
   predeclaration document; placeholder identities are rejected. Before any cell runs the file
   is re-hashed and a mismatch refuses with `PREDECLARATION_CHANGED_AFTER_APPROVAL`.

   Code cannot verify that a human approved a design. It can refuse to proceed silently, refuse
   to run a design that changed after approval, and keep both facts in the receipt. That is the
   honest boundary, and it is deliberately stricter than a free-text "approved: yes" field.

2. **Held-out seeds require separate explicit authorisation.** A `held_out` phase design is
   invalid unless `held_out_authorised` is set. The predeclaration's whole value is the disjoint
   pilot/confirmatory split; a tool that could quietly spend the reserved seeds would destroy it.

3. **Sequential foreground execution only.** No background job, detached process, persistent
   queue, scheduler, or concurrency — the accepted VEC-10 prohibitions are preserved literally,
   and the receipt carries them as type-level `False` literals. A long campaign is a long
   foreground operation that can be interrupted and resumed, not a service that outlives its
   caller.

4. **Seed-major ordering, because that is what makes an interruption survivable.** Every arm for
   one seed, then the next seed. An interrupted campaign then holds complete arm coverage for
   the seeds it finished, which yields usable pairs; arm-major ordering would leave every seed
   half-populated and produce none. Resumability follows: a cell with an intact `completed`
   receipt for the same request fingerprint is reused, not re-executed.

5. **Declared bounds halt rather than continue.** Cell count is validated against the design
   itself; a cell whose outputs would exceed the remaining byte budget is skipped and the
   campaign halts; the first failure halts by default. A failure is recorded with its reason and
   never retried with altered controls, because a silent retry under different settings is how a
   sweep becomes a search for a preferred result.

6. **The service is scientifically inert.** It computes no metric, chooses no threshold, and
   records no conclusion; `scientific_conclusion_recorded` is a literal `False`. Experiment
   registration refuses with `EXPERIMENT_PLAN_CONFLICT` rather than attaching a campaign to a
   plan that differs from its design.

## Consequences

**What this unblocked.** An approved predeclaration can now be executed as one bounded,
resumable, receipted operation, and the `Experiment` plan STA-01 needs is registered as part of
it. The research instrument is complete end to end: predeclare → approve → execute → admit →
pair.

**What it did not change.** No capability row moves. Nothing here authorises a run: the
capacity-squeeze predeclaration remains unsigned, and a campaign against it refuses until a
person signs it. VEC-11/VEC-12 packaging still binds the audited source run only.

**Cost and residual risk.** The foreground-only constraint means a twelve-cell `inc` pilot
occupies a terminal for hours; resumability mitigates interruption but not duration. The
runner's 7,200-second per-request ceiling versus `inc`'s measured cost remains the open risk
recorded in ADR-062 — if a cell approaches it, the escalation goes to the owner rather than the
bound being raised to fit the design.

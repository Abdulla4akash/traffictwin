# Weekly Research Progress

## Executive summary

The week was one connected investigation, not a collection of unrelated runs. Each experiment answered a specific ambiguity left by the previous stage:

**measurement validity → queue-capacity intervention → placement pilot → placement/admission decomposition → matched replication → implementation audit → construct-validity falsification test**

The final direction reversal is scientifically important because it changed the interpretation of the earlier result rather than hiding it. Under a shared deadline-aware gate, the inherited common-target-per-substep implementation was lower than strongest-link execution, while a per-task sequential implementation was higher.

## E0 — make the measurement trustworthy

### Initial issue

Scheduler results cannot be interpreted if offered tasks, rejected work, queue service or terminal outcomes can silently disappear.

### Problem discovered

The evaluator required an explicit, auditable lifecycle for offered, admitted, rejected, unavailable, executed and deadline-successful tasks. Waiting-room and service semantics also needed to be physically distinguishable.

### Action

The evaluator and validators were corrected and exercised with finite reject-mode queues, sequential queue updates, explicit terminal categories, V2I service-work accounting and vehicle service-work accounting.

### Evidence

The corrected smoke and full reference passed task conservation, terminal-outcome reconciliation, V2I work conservation, vehicle work conservation and finite/nonnegative checks. Exact identities are recorded in [Provenance](PROVENANCE.md).

### Decision

E0 closed as a validity foundation. It did not compare schedulers. With accounting trusted, the first controlled resource question could be asked.

## E1 — waiting-room capacity at fixed compute service

### Initial issue

A larger RSU queue is often casually interpreted as “more capacity,” even though it does not increase compute throughput.

### Problem discovered

Changing the waiting-room ceiling can lower rejection while increasing queueing. Offered-task and admitted-task outcomes may therefore move differently.

### Action

Five matched fleet draws were evaluated at 0.75× (1,866 tasks/RSU), 2.5× (6,220) and 40× (99,520), while RSU service remained fixed at 1×.

### Evidence

For the predeclared 40×−0.75× offered-attainment contrast, the five differences were −0.000171609043, −0.000122129965, 0, −0.000253436884 and 0. The mean was −0.000109435178 and the 95% Student-t interval was [−0.000246462456, +0.000027592099]. Larger caps admitted more tasks and rejected fewer, but sharply increased admitted latency and reduced admitted-task attainment.

### Decision

The primary result was **inconclusive at this replication size**—not equivalence, a tie or significant harm. The observed trade-off established that queue capacity is not compute service capacity. The next question moved from queue size to infrastructure placement.

## E2 — native infrastructure placement pilot

### Initial issue

Could infrastructure-side least-busy placement reduce overload and improve deadlines while the vehicle actor remained frozen?

### Problem discovered

The original evaluator output did not fully expose radio ingress, selected execution target and actual execution. Inferring paths from aggregate queues would not be valid.

### Action

Output-only native path instrumentation was added and proved no-effect. A one-draw pilot compared strongest-link/default (`off`), inherited least-busy placement (`jsq`) and inherited least-busy placement plus deadline-aware admission (`dla`).

### Evidence

`off` offered attainment was 0.683619229; `jsq` was 0.675681775, a difference of −0.007937454. The inherited policy made execution much more balanced yet worsened the primary deadline outcome. `dla` reached 0.694939919 but admitted far fewer V2I tasks and gate-rejected 2,373,522 tasks.

### Decision

The DLA improvement could not be assigned to placement because DLA changed both placement and admission. This confounding directly motivated E2b.

## E2b — separate placement from admission

### Initial issue

E2 lacked the strongest-link-plus-deadline-gate cell needed to isolate mechanisms.

### Problem discovered

Without that missing cell, `dla - off` was a joint intervention rather than a placement effect.

### Action

The `ingress_dla` mode was added: strongest-link execution with the exact same deadline-aware gate as `dla`, no forwarding and unchanged actor/queue semantics. This completed a 2×2 placement × admission table using one new full arm and hash-reused E2 controls.

### Evidence

Offered attainment was 0.683619229 (`off`), 0.675681775 (`jsq`), 0.715773211 (`ingress_dla`) and 0.694939919 (`dla`). Admission improved attainment under strongest-link by +0.032153983 and under inherited least-busy placement by +0.019258144. With admission held constant, `dla - ingress_dla` was −0.020833292.

### Decision

Deadline-aware admission was associated with a substantial improvement under both placement rules. The clean same-gate placement difference was negative, but one draw could only generate a hypothesis. E2c was predeclared as a matched multi-draw replication.

## E2c — matched multi-draw placement replication

### Initial issue

Would the E2b same-gate placement direction persist across new matched fleet draws?

### Problem discovered

Seed 0 generated the hypothesis and could not legitimately be folded into the primary replication interval. Individual tasks could not be treated as independent observations.

### Action

Four new fleet draws (seeds 1–4) compared `dla` with `ingress_dla`; evaluator seed 0 and all other conditions were frozen. Fleet seed was the replication unit.

### Evidence

All four `dla - ingress_dla` differences were negative: −0.022097034972, −0.020519134179, −0.021447383092 and −0.020825491499. Their mean was −0.021222260935 and 95% Student-t interval [−0.022335254070, −0.020109267800]. Path evidence showed about 85% of admitted DLA V2I tasks forwarded at zero cost, but actual execution occurred on only five of ten RSUs.

### Decision

The bounded result supported a common-target implementation-specific deficit. It also triggered a source-level mechanism audit rather than a universal “JSQ is harmful” conclusion.

## E2c source/mechanism audit — identify the construct

### Initial issue

The execution distribution was unexpectedly restricted despite a policy described broadly as least-busy/JSQ.

### Problem discovered

The inherited implementation selected one `argmin(rsu_busy_ms)` target once per task substep and broadcast that target across the substep's V2I candidates. It was not per-task target recomputation.

### Action

The implementation was renamed precisely in research prose as **common-target-per-substep least-busy placement**. `rsu_busy_ms` was traced as remaining RSU compute-service workload in milliseconds.

### Evidence

The common-target arm had one selected target per active substep, zero within-substep target switching and only five RSUs with actual V2I execution across all four new draws.

### Decision

E2c remained valid for the implementation it actually tested. A new construct-validity question followed: would the negative direction survive per-task sequential least-busy placement?

## E2d — per-task sequential least-busy robustness

### Initial issue

The E2c result could have been substantially shaped by dispatch granularity rather than by the broad least-busy principle.

### Problem discovered

The new mode had to preserve actor, ingress, deadline gate, candidate order, tie-breaking, service-work reservation, PRNG structure and all existing modes while updating effective RSU workload only after admitted assignments.

### Action

`per_task_dla` processed task-substep index ascending, then padded vehicle-slot index ascending; chose the lowest-index minimizer through `jnp.argmin`; applied the existing deadline gate at that target; and updated temporary workload only after admission.

### Engineering quality-control event

The first frozen E2d package received independent `APPROVE`, but before any Manchester trace process started the execution agent noticed that its runner would perform seed-1 smokes → seed-1 full → seed-2 smokes. The protocol required all eight smokes before any full cell. Execution stopped with zero trace runs and zero discarded evidence. The orchestrator and manifest were corrected, new identities were frozen, and a fresh exact-head independent review returned `APPROVE` before execution.

### Evidence

Eight existing-mode replays, eight new-arm smokes and four full cells all passed; there were no failures, retries or discarded runs. The four `per_task_dla - ingress_dla` differences were +0.004636732564, +0.005867285642, +0.005071796666 and +0.005509919752. The mean was +0.005271433656 and 95% interval [+0.004422143925, +0.006120723387]. The secondary `per_task_dla - common-target dla` mean was +0.026493694591.

Per-task placement used all ten RSUs, forwarded about 600,000 admitted V2I tasks per draw, switched targets about 643,000 times within substeps and produced an execution-share range of roughly 0.0007–0.0014.

### Decision

The observed direction reversed. Within these four matched incident draws, per-task sequential least-busy placement exceeded strongest-link execution under the shared deadline-feasibility rule. The common-target convention was an important mechanism behind E2c's negative direction, but was not proven to be the sole cause. E2d closed with no automatic follow-on authority.

## What the week established

- Measurement corrections enabled valid performance questions.
- A negative or inconclusive result was retained when that was the evidence.
- Each ambiguity was resolved with a narrower controlled comparison.
- The final construct-validity experiment successfully challenged the tempting broad interpretation of E2c.
- Exact scheduling semantics—not just a high-level algorithm label—can reverse a systems-performance conclusion.

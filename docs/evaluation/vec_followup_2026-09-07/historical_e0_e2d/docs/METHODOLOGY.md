# Methodology

## Fixed experimental setting

Later placement studies used a one-hour Manchester incident trace for Friday 15 March 2024, 20:00–21:00 Europe/London, with 3,600 evaluator steps, ten RSUs and a padded fleet width of 2,488. The fleet preset was provisional `uk2030`; evaluator seed was fixed at 0. Arrival lambda was 1.5.

The physical queue settings were sequential substep queueing, three reconciliation iterations, conserved vehicle queues and explicit reject admission. The waiting-room ceiling was fixed at 2.5×, resolving to 6,220 tasks per RSU. RSU service remained fixed at 1×, scaling was off and forwarding latency was 0 ms.

## Frozen vehicle actor

The frozen Paper-2A MAPPO actor had a 17-dimensional observation and selected only Local, V2I or V2V. It did not observe current RSU load and did not select the execution RSU. The placement and admission interventions were infrastructure-side.

Actor artifact SHA-256:

`93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`

Trace artifact SHA-256:

`e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`

## Task lifecycle and accounting

For each offered task, validators required exactly one terminal outcome: admitted or a declared rejection/unavailability reason. Existing taxonomy included local queue rejection, V2I cap rejection, V2I deadline-gate rejection, V2I unavailability, V2V queue rejection and V2V unavailability.

For V2I tasks, native path records distinguished:

- strongest-link radio ingress;
- selected execution target before final admission;
- actual execution RSU for admitted work;
- forwarding status and charged forwarding latency;
- explicit V2I admission.

Rejected/unavailable work could not be recorded as executed or forwarded. Aggregate path counts had to reconcile exactly with task-level arrays.

## Denominators

- Offered-task deadline attainment: `deadline_met / offered_tasks` (primary).
- Admitted-task deadline attainment: `deadline_met / admitted_tasks`.
- Offered latency: penalty-inclusive latency sum divided by offered tasks.
- Admitted latency: admitted latency sum divided by admitted tasks.
- Deadline-met latency: met-task latency sum divided by deadline-met tasks.
- Energy: reported per offered task.

## Interventions

| Mode | Radio ingress | Execution placement | Deadline gate | Forwarding |
|---|---|---|---|---|
| `off` | Strongest link | Ingress | Off | None |
| `jsq` | Strongest link | Inherited least-busy | Off | Possible |
| `ingress_dla` | Strongest link | Ingress | On | None |
| `dla` | Strongest link | One common least-busy target per task substep | On | Possible |
| `per_task_dla` | Strongest link | Least-busy recomputed per candidate after admitted reservation | On | Possible |

“DLA” is not described as deadline-aware placement. In the inherited evaluator it combines least-busy placement with deadline-aware admission.

## E2d selector semantics

`rsu_busy_ms` represented remaining RSU compute-service workload in milliseconds. In `per_task_dla`, candidates were ordered by task-substep index ascending and padded vehicle-slot index ascending. `jnp.argmin` selected the minimum workload, breaking ties at the lowest RSU index. Temporary effective workload increased by the real service-work reservation only after admission; rejected or unavailable candidates reserved no work.

## Replication and statistics

Fleet draws/fleet seeds—not tasks—were the independent replication units. E1 used five matched draws. E2 and E2b were one-draw descriptive/hypothesis-generating studies. E2c used four new matched draws, excluding its hypothesis-generating seed 0. E2d used four matched draws and reused exact E2c controls.

For the predeclared multi-draw contrasts, the reports give raw paired differences, sample standard deviation with `n − 1`, standard error and two-sided 95% Student-t intervals. No task-level confidence interval, equivalence margin, non-inferiority test or population-wide claim was introduced.

## Validity gates

Cells were accepted for identity and scientific validity, never for producing a favourable outcome. Gates covered exact source/artifact/environment identities, deterministic repeated smokes, matched task/action/fleet streams, finite/nonnegative values, complete terminal outcomes, no silent loss, V2I work conservation, vehicle work conservation, path reconciliation, no overwrite, compute/storage limits and checksum completeness.

## Internal review gates

Independent exact-head technical review was used as an internal experimental quality-control gate before execution and after final evidence. It checked code, manifests, estimands, stop rules, accounting and claim boundaries. This was not scholarly peer review.

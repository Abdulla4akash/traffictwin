# VEC per-task lifecycle instrumentation contract v1

**Implemented:** 6 August 2026
**Method:** `vec-task-lifecycle-1.0`
**Status:** provisional instrumentation software; no native evaluator producer, scientific result
or admission

## Purpose

The current audited evaluator records task activity, modelled latency, deadline attainment and
task type. It does not record a complete physical lifecycle linking offered work to admission,
rejection, execution and result return. This module defines the strict event boundary a future
native evaluator or reviewed adapter must satisfy before TrafficTwin uses physical-completion,
throughput, rejection or work-conservation language.

The implementation is additive:

- `src/traffictwin/integration/vec_task_lifecycle/models.py` defines frozen event, report and
  contract models;
- `src/traffictwin/integration/vec_task_lifecycle/service.py` validates event order, time, node
  continuity and conservation; and
- `tests/unit/test_vec_task_lifecycle.py` exercises complete, open and invalid synthetic ledgers.

It does not change or wrap the pinned evaluator. There is deliberately no adapter from the current
`task_met`/latency arrays because those arrays cannot reconstruct the missing events.

## Event vocabulary

Every task begins at sequence index zero with the exact originating local vehicle and uses
contiguous indexes with non-decreasing event time:

```text
offered
→ action_selected
→ ingress_assigned
→ admitted | rejected

admitted
→ retained | forwarded [→ forwarded ...]
→ execution_started | dropped
→ execution_completed | dropped
→ result_returned | result_return_failed

physical terminal outcome
→ deadline_assessed
```

The supported action remains local/V2I/V2V. The action and ingress type must agree:

| Action | Required ingress kind |
|---|---|
| local | originating local vehicle |
| V2I | RSU |
| V2V | eligible peer vehicle |

Forwarding is recorded only as an explicit RSU-to-RSU hop. Each hop must start at the task's
current node, name a different destination RSU and preserve continuity into execution. Result
return must start at the execution node and target that exact originating local vehicle. For a
local action, ingress must also be that same vehicle. The validator does not choose any of these
nodes; it checks events produced elsewhere.

Event time means that the named event has completed: `admitted` is the ingress admission instant,
`forwarded` is arrival at the destination RSU, `execution_started`/`execution_completed` bound the
compute interval, and `result_returned` is arrival back at the originating vehicle. A later metric
layer may derive segment durations only from a native producer that follows these definitions.
The contract does not currently calculate them.

Rejection, drop and return failure require one closed machine-readable reason code. The contract
does not prescribe which reasons are scientifically correct; that remains part of the producer or
owner-approved semantics decision.

## Task-count conservation foundation

For every validated ledger, task counts satisfy:

```text
offered = pending_admission + admitted + rejected

admitted = admitted_in_progress + dropped + returned + return_failed
```

A closed-required validation refuses any task that has not reached one explicit physical terminal
outcome and a separate deadline assessment. An open validation is available for bounded
instrumentation snapshots, but its pending and in-progress populations remain visible rather than
being treated as success, failure or zero.

This is a necessary foundation for work conservation, not the complete physical claim. The v1
ledger does not reconcile CPU-work units, server time or service budgets, because their intended
semantics remain unresolved. The report therefore exposes `task_count_conservation_holds`; it does
not claim generic work conservation.

Input order is not trusted. Events are grouped by task and ordered by their explicit sequence
index. Duplicate/gapped sequence indexes, time regression, mixed run ids, invalid transitions,
wrong nodes and broken forwarding/return chains fail closed. The canonical event fingerprint uses
the same task/sequence ordering, so input permutations produce an identical report.

## Physical return and deadline attainment are separate

`result_returned` is the contract's only positive physical-result-return event. It is never derived
from `task_met`.

`deadline_assessed` records modelled deadline attainment after the physical path reaches a
terminal state. Modelled latency is optional: if it is absent for a rejected, dropped or otherwise
unobserved path, the report counts that absence and never imputes a value. A returned result may
still miss its deadline. Conversely, the contract does not automatically turn an early rejection
into deadline success. The producer or signed experiment semantics must state how each terminal
outcome is scored.

Reports carry structural refusals:

- `physical_return_is_deadline_attainment = false`;
- `legacy_task_met_imported = false`;
- `legacy_evaluator_compatible = false`; and
- `scientific_evidence = false`.

`modelled_latency_observed_count` makes the latency denominator explicit and may be lower than
`deadline_assessed_count`.

This preserves the 6 August correction: `task_met` is modelled deadline attainment, not eventual
physical completion.

## What is verified now

Synthetic tests cover:

- a local result that returns after its deadline;
- explicit RSU admission and RSU-to-RSU forwarding;
- rejection at the ingress admission boundary;
- a dropped peer-execution task;
- execution completion followed by return failure;
- complete task and admitted-task conservation;
- open-ledger visibility and closed-required refusal;
- deterministic fingerprints under input permutation;
- exact originating-vehicle, action/ingress, execution-node, forwarding-source and return-source/
  target mismatch refusals;
- invalid transitions, sequence gaps/duplicates and time regression; and
- strict payload rejection of a fabricated legacy `task_met` field.

These are software-contract tests over synthetic events. They do not prove that the current
evaluator emits the events or that the provisional transition semantics match the producer's
intention.

## What remains

The next slices are separate and still unbuilt:

1. obtain producer answers or freeze explicit provisional service/admission/return semantics;
2. implement a native lifecycle producer in a reviewed evaluator boundary;
3. validate one hand-calculated two-RSU case against the native event stream;
4. add deterministic strongest-link/no-forwarding, least-loaded and predicted-earliest-completion
   policies behind a separate scheduler interface;
5. extend VEC runner output validation, fresh admission and metrics to the new native artifact;
6. sign and execute a matched deterministic comparison; and
7. build learned scheduling and capacity-aware actor retraining only as later distinct treatments.

No campaign, registry, checkpoint, approval, evidence or digest-bound artifact is read or changed
by this module.

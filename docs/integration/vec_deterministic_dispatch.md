# Deterministic VEC execution-RSU dispatcher v1

**Implemented:** 6 August 2026
**Method:** `vec-deterministic-dispatch-1.0`
**Status:** provisional deterministic application software; no native-evaluator integration,
campaign result, scientific evidence or actor retraining

## Purpose and architecture boundary

This module implements the first downstream execution-RSU dispatcher required before a learned
scheduler comparison. It operates only after the frozen actor has selected V2I. The actor still
chooses local/V2I/V2V, and strongest-link environment logic still supplies the V2I ingress RSU.
The dispatcher chooses or refuses a separate execution reservation from one complete candidate
snapshot.

This architecture does not change the actor observation or action contract and therefore does not
require retraining. Adding RSU load, capacity, headroom, telemetry age or cost to the actor itself
would change that contract and remains a separate retraining experiment.

## Common information and cost contract

All three policies receive exactly the same `VecDispatchRequest`. Every candidate declares:

| Field | Meaning |
|---|---|
| `reachable` | candidate is radio/topology reachable in the supplied snapshot |
| `execution_enabled` | candidate is allowed to execute this task |
| `link_quality_milliunits` | bounded synthetic or future native link ranking input |
| `execution_slot_limit` | execution/in-flight concurrency ceiling |
| `occupied_execution_slots` | already occupied slots |
| `reserved_execution_slots` | capacity reserved by earlier decisions |
| `telemetry_age_ms` | age checked against the request's maximum |
| `forwarding_ms` | post-ingress transfer delay; zero at ingress |
| `forwarding_energy_millijoules` | declared forwarding cost; zero at ingress |
| `predicted_queue_wait_ms` | caller-supplied predicted wait |
| `predicted_compute_ms` | caller-supplied predicted compute duration |
| `predicted_return_ms` | caller-supplied predicted result-return duration |

The concurrency ceiling and reservations are not processor speed, computation power, service
rate, worker count or bandwidth. Predicted compute time is a separate declared input. No field is
inferred from the current evaluator's aggregate arrays.

An execution candidate is eligible only when it is reachable, enabled, fresh enough and has
headroom for the task after occupied and already reserved slots. The ingress must be present, be
reachable, have maximum link quality among reachable candidates, and declare zero forwarding
delay and energy.

Prediction begins at the post-ingress dispatch boundary:

```text
predicted completion
= forwarding delay
+ predicted queue wait
+ predicted compute
+ predicted return
```

Ingress transmission remains a preceding lifecycle segment and is not counted twice.

## Policies and deterministic ties

### Strongest-link/no forwarding

This policy considers only the supplied strongest-link ingress. It reserves that RSU when eligible;
otherwise it refuses execution dispatch with an exact ingress reason. It never falls back or
forwards to another RSU, even when another candidate has headroom.

### Least loaded

Eligible candidates are ranked by projected execution-slot utilisation after reserving the task:

```text
(occupied + already reserved + task slots) / execution-slot limit
```

The implementation compares the exact integer fraction. Ties use, in order: predicted completion,
forwarding energy, higher link quality and lexical RSU id.

### Predicted earliest completion

Eligible candidates are ranked by the four-component predicted completion above. Ties use, in
order: lower forwarding energy, lower exact projected utilisation, higher link quality and lexical
RSU id.

These are application-level deterministic policies, not Kubernetes pod scheduling, a learned
model or a claim that one policy is scientifically superior.

## Reservation-aware batches

`dispatch_vec_batch()` sorts tasks by their explicit unique contiguous `decision_order`, carries a
shared reservation population between decisions, and returns one selected or unavailable outcome
per task. Input list order is ignored. Every selected task increments its target reservation before
the next task is evaluated, preventing simultaneous-looking tasks from reusing one visible slot.

The batch report reconciles:

```text
requests = selected + unavailable
final reservation = initial reservation + newly reserved slots
```

This is an explicit deterministic ordering contract, not a physical concurrency-time model.
Reservation release belongs to later lifecycle execution/terminal events and is not fabricated by
the dispatcher.

## Two-RSU reference behaviour

The existing [synthetic hand calculation](vec_two_rsu_handcheck.md) supplies the canonical state:

- RSU A: link 900, one execution slot, one occupied, zero headroom;
- RSU B: link 600, one execution slot, empty, one slot of headroom;
- B costs: 4 ms forwarding, 400 mJ forwarding energy, 2 ms queue, 10 ms compute and 5 ms return.

On that identical request:

| Policy | Result |
|---|---|
| strongest-link/no forwarding | unavailable: ingress has no execution headroom |
| least loaded | reserve and forward to RSU B |
| predicted earliest completion | reserve and forward to RSU B; post-ingress prediction = 21 ms |

Two identical ordered tasks demonstrate reservation safety: the first reserves B's one slot and
the second becomes unavailable rather than selecting the same apparent headroom.

## What is and is not complete

Implemented and tested:

- strict frozen candidate, request, decision, batch, reservation-summary and contract models;
- all three versioned policies over one common information contract;
- freshness, reachability, execution-enable and headroom gates;
- exact policy-specific ranking and stable ties;
- reservation-aware, input-order-independent batches;
- typed refusal for missing targets and ambiguous batch state; and
- structural declarations that selection does not confirm execution, return or deadline outcome.

Still separate and unbuilt:

1. a reviewed native evaluator lifecycle/state producer or adapter, followed by the implemented
   [native runner sidecar validation](vec_native_runner_sidecar.md);
2. live runner production and admission integration for validated dispatcher requests/decisions;
3. contact-time, bandwidth, reliability and service-budget semantics;
4. a signed matched deterministic comparison on identical traffic/tasks/seeds;
5. scientific metrics and admitted result evidence; and
6. a learned scheduler using the same information and costs.

Scheduling computing tasks does not itself make roads less congested. That would require a separate
closed-loop traffic-control intervention and evidence.

No campaign, registry, checkpoint, approval, evidence or digest-bound artifact is read or changed
by this module.

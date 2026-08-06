# Matched deterministic VEC dispatch study v1

**Status:** implemented synthetic structural comparison

**Method:** `vec-matched-dispatch-study-1.0`

**Evidence boundary:** deterministic engineering projection only; no native lifecycle result,
policy winner, campaign result or scientific evidence

## Purpose

The study harness answers one bounded engineering question:

> When all three deterministic execution-RSU policies receive the exact same synthetic task and
> candidate-state batch, where do their routing and reservation projections agree or diverge?

It compares:

1. strongest-link ingress with no forwarding;
2. least projected execution-slot load; and
3. predicted earliest completion.

All three policies already exist in the
[deterministic dispatcher](vec_deterministic_dispatch.md). The study harness does not add another
selection policy. It exact-matches their input, retains all three complete batch reports and
reconciles their structural differences.

Library: `traffictwin.integration.vec_dispatch_study`

## Exact matched-input boundary

`compare_vec_dispatch_policies()` accepts one study identifier and one bounded sequence of strict
`VecDispatchRequest` models. The plan:

- is always labelled `synthetic_fixture = true`;
- requires one candidate snapshot, unique task identities and contiguous explicit decision order;
- canonicalises caller input by decision order;
- fixes the policy set and its order; and
- caps the batch at 100,000 requests, matching the underlying dispatcher bound.

Each policy receives the same immutable canonical request tuple. Every resulting
`VecDispatchBatchReport.input_fingerprint` must equal the report's one
`common_input_fingerprint`. A partial, reordered or extra policy set is invalid.

The policies then carry their own reservation states forward. Consequently, the original input
fingerprint remains matched while a later task's policy-specific evaluated-request fingerprint may
differ after earlier policies reserved different RSUs. That divergence is part of the result, not
an input mismatch.

## Reported projections

The report contains three layers.

### Complete policy reports

The complete reservation-aware dispatcher report is retained for each policy, including every
decision, refusal reason and batch-end reservation summary.

### Policy summaries

Each policy summary reconciles only deterministic integer quantities:

- requests, selected tasks, unavailable tasks and forwarded tasks;
- selected execution slots;
- the sum of caller-supplied predicted completion time for selected tasks;
- the sum of caller-supplied forwarding delay and forwarding energy for selected tasks; and
- per-RSU initial occupied slots, initial/final reservations, selected task/slot counts and final
  occupied-plus-reserved slot fraction in parts per million.

Unavailable tasks are not treated as zero-cost successes. They increase the unavailable count and
are excluded from selected-task predicted-cost sums.

The final slot fraction is a batch-end projection of execution-slot occupancy plus reservations.
It is not CPU utilisation, service rate, processor speed, worker count, bandwidth or evidence of
physical completion.

### Per-task comparisons

Every original request retains its fingerprint and all three exact policy decisions.

`route_agreement` means the three policies produced the same selected/unavailable disposition,
execution RSU and forwarding flag. `projection_agreement` additionally requires matching refusal,
eligible-candidate, evaluated-request, reservation, projected-load and predicted-cost fields.

Agreement is not evidence that a decision is good. Disagreement is not evidence that one policy is
better. The report fixes `winner_selected = false`.

## Structural reconciliation

The report fails closed unless:

```text
one plan fingerprint
= one canonical input fingerprint for every policy

requests
= route agreements + route disagreements
= projection agreements + projection disagreements

selected execution slots per policy
= newly reserved execution slots across RSUs
```

It also rebuilds every policy summary from the retained batch report and every RSU projection from
the original plan plus reservation summaries. Altered input fingerprints, summaries, task joins or
RSU projections fail model validation.

## Example

```python
from traffictwin.integration.vec_dispatch_study import (
    compare_two_rsu_handcheck_policies,
)

report = compare_two_rsu_handcheck_policies()
```

This public helper maps the exact existing two-RSU hand-check state and costs into one strict
dispatcher request. General callers use `compare_vec_dispatch_policies(study_id, requests)`, where
`requests` contains strict `VecDispatchRequest` objects. Neither function performs a file,
registry, campaign, evaluator or network operation.

## Tests

Focused synthetic coverage proves:

- the strong-link-full/weaker-link-idle case separates no-forwarding from both load-aware policies;
- the public two-RSU comparison remains exact-bound to the earlier hand-check fixture;
- all three policies can agree without creating a winner claim;
- equal information still permits distinct policy selections;
- multi-task reservations reconcile separately for every policy;
- caller request ordering cannot change the canonical report;
- mixed snapshots, invalid order and shared-resource drift fail closed;
- input, policy-summary and task-comparison tampering is rejected;
- partial or reordered policy sets are invalid; and
- unavailable decisions remain unavailable rather than becoming zero-cost successes.

## Scientific boundary and remaining work

This v1 harness deliberately has no native evaluator input and joins no realised lifecycle. Its
completion and forwarding fields are caller-supplied predictions. It does not measure execution,
physical return, deadline attainment, task energy or a road-traffic outcome. Scheduling computing
tasks does not make roads less congested without a separate closed-loop traffic-control
intervention.

The next evidence-producing sequence remains:

1. obtain an authorised native lifecycle/state producer or reviewed adapter;
2. validate its output through the [native runner sidecar](vec_native_runner_sidecar.md);
3. wire each deterministic treatment into identical native traffic, tasks and seeds;
4. join realised lifecycle outcomes and admit only supported scientific metrics;
5. run a predeclared matched comparison with uncertainty; and
6. compare a learned scheduler later using the same information and costs.

Capacity-aware actor retraining remains a separate experiment because it changes the actor's
observation contract. No evaluator, external repository, run, campaign, registry, checkpoint,
approval, evidence, digest-bound candidate, release or tag is read or changed by this module.

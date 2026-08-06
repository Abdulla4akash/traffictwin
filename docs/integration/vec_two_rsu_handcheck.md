# Synthetic two-RSU hand-check v1

**Implemented:** 6 August 2026
**Method:** `vec-two-rsu-handcheck-1.0`
**Status:** synthetic provisional reference case; no current-evaluator validation, reusable
scheduler or scientific evidence

## Question answered

Can one small, deterministic case make the proposed ingress/forwarding lifecycle arithmetic fully
visible before a general dispatcher is built?

Yes, under the explicit provisional assumptions below. The executable fixture presents one V2I
task to two reachable RSUs:

| State at the decision instant | RSU A | RSU B |
|---|---:|---:|
| Link quality (synthetic milliunits) | 900 | 600 |
| Execution-slot ceiling | 1 | 1 |
| Occupied execution slots | 1 | 0 |
| Execution-slot headroom | 0 | 1 |
| Role | unique strongest-link ingress | weaker-link execution destination |

RSU A's ceiling is an execution/in-flight concurrency boundary. It is not processor speed,
computation power, service rate, worker count or bandwidth. Its one initial occupant is a declared
boundary condition outside the one-task validation cohort.

## Provisional fixture semantics

The case freezes these assumptions rather than attributing them to the current evaluator or its
producer:

1. strongest link chooses ingress only;
2. the sole RSU with execution-slot headroom is the predeclared execution destination;
3. application admission at ingress and the destination execution reservation are atomic at the
   admitted timestamp;
4. the destination reservation occupies one slot until execution completes;
5. forwarding delay and energy are synthetic integer reference costs; and
6. every lifecycle event is supplied by the fixture, not inferred from `task_met` or current
   evaluator arrays.

These semantics define one oracle. They do not implement strongest-link/no-forwarding,
least-loaded or predicted-earliest-completion policies.

## Hand calculation

The exact task path is:

```text
vehicle-reference-1
  → strongest-link ingress rsu-a-strong-full
  → one execution-slot reservation at rsu-b-weaker-idle
  → forward A to B
  → execute at B
  → return to vehicle-reference-1
```

The event and arithmetic table is deliberately small enough to check manually:

| Event/component | Event time (ms) | Increment (ms) |
|---|---:|---:|
| offered/action/ingress selected | 0 | — |
| admitted at A and reservation created at B | 2 | ingress transmission = 2 |
| arrived at B after forwarding | 6 | forwarding = 4 |
| execution started at B | 8 | queue wait = 2 |
| execution completed and reservation released | 18 | compute = 10 |
| result returned to originating vehicle | 23 | return = 5 |
| deadline assessed | 23 | modelled end-to-end latency = 23 |

Therefore:

```text
end-to-end latency = 2 + 4 + 2 + 10 + 5 = 23 ms
forwarding energy = 4 ms × 100 mJ/ms = 400 mJ
deadline outcome = 23 ms ≤ 25 ms = met

offered = 1
admitted = 1
forwarded = 1
execution completed = 1
physically returned = 1
closed terminal lifecycle = 1
```

The reservation independently reconciles `0 → 1 → 0` occupied slots at RSU B. RSU A remains at
its declared initial occupancy; the fixture does not pretend to own or complete that background
work.

## Implementation and refusal behaviour

`src/traffictwin/integration/vec_task_lifecycle/two_rsu_handcheck.py` provides:

- frozen two-RSU state, reservation, case and report models;
- `build_two_rsu_handcheck_case()` for the canonical fixture; and
- `validate_two_rsu_handcheck()` as an independent fail-closed oracle.

The oracle first runs the v1 lifecycle validator, then recomputes unique strongest-link ingress,
execution headroom, reservation creation/release, the exact node path, each timing interval,
forwarding energy, end-to-end latency, deadline outcome and task counts. Tests alter these inputs
one at a time and require a typed refusal for changed RSU occupancy/link state, reservation counts
or times, event order/nodes, component timing, forwarding energy and deadline outcome.

The report structurally declares:

- `scheduler_included = false`;
- `native_evaluator_validated = false`; and
- `scientific_evidence = false`.

## What this completes and what remains

This completes the synthetic, hand-calculated reference fixture requested before deterministic
scheduler work. It does not complete native validation because the audited evaluator still emits
no lifecycle, reservation, forwarding or physical-return events.

The next bounded steps are:

1. obtain producer answers or approve a versioned provisional producer semantics record;
2. implement a reviewed native lifecycle producer/adapter;
3. replay this exact arithmetic against its emitted event stream;
4. build the separate deterministic dispatcher interface and three policies; and
5. add separately justified bandwidth, service-budget, contact, telemetry-age and reliability
   treatments only after their semantics are frozen.

No campaign, registry, checkpoint, approval, evidence or digest-bound artifact is read or changed
by this reference case.

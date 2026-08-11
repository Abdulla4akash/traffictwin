# E2d per-task placement robustness decision record — 11 August 2026

## Decision and authority

E1, E2, E2b and E2c remain closed. E2d is a narrowly bounded construct-validity study authorised
by Abdulla on 11 August 2026. It adds one evaluator mode, `per_task_dla`, and four new full cells
for fleet seeds 1–4. The completed E2c `ingress_dla` and `dla` cells for the same seeds are reused
only after their frozen root ledger and selected file hashes verify.

This record, the manifest, implementation, tests and synthetic production probes do not grant
trace-execution authority. Eight existing-mode ten-step replays, eight new-arm ten-step smokes and
four new 3,600-step cells remain forbidden until an independent Claude review returns exact
`APPROVE`; that exact `APPROVE` must bind the TrafficTwin pre-run head, vec_env candidate head and
manifest SHA-256.
`APPROVE_WITH_MINOR_FIXES` is not authority.

## Preserved pre-execution stop and corrected package

The first exact independent review returned `APPROVE` for TrafficTwin
`6443b936064dba2766dcb8dee9146b246bc769bf`, vec_env
`2f63706f46319433a2ba3af1df97afd0e56a95d1` and manifest SHA-256
`b2d04fa31ae40fb0519ebd019817599be428392bf6b1ee98656740ea509aa420`. The identity,
closed-evidence, environment, process and storage preflight checks passed. Before any Manchester
trace process launched, however, inspection showed that the reviewed runner combined each seed's
two smokes with its full cell. That executable ordering contradicted the frozen requirement that
all eight new-arm smokes pass before any 3,600-step cell.

Execution authority for that superseded package was revoked immediately. Zero replay probes, zero
new-arm smokes and zero full cells ran; no scientific output existed or was discarded. The original
approval receipt remains immutable outside Git at
`independent_review/claude_review_verdict.json`, with SHA-256
`853756c699386b70a16045e15cf96bf042c8200a3d18de406df44fa0bd03e549`.

The corrected TrafficTwin-only package exposes three disjoint commands, in order:

1. `--run-replay-gate` runs only the eight existing-mode ten-step probes;
2. `--run-smoke-gate` requires the replay gate and runs all eight ordered new-arm smokes without
   any full cell;
3. `--full-cell-index {1,2,3,4}` requires the replay gate, the global smoke PASS record, all eight
   revalidated smoke records and prior full-cell completion, then runs only the selected full cell.

This orchestration correction changes no evaluator, intervention, seed, configuration, metric,
statistic or scientific claim. It creates a new TrafficTwin head and manifest SHA and therefore
requires a fresh exact Claude `APPROVE`. The new manifest binds a distinct immutable receipt path,
`independent_review/claude_review_verdict_v2.json`; the superseded receipt cannot authorise the
corrected package. The corrected TrafficTwin scientific-code commit is
`eb8571810cc0f29c8477b14e15a73d7e3c915f69`; the regenerated manifest SHA-256 is
`f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`.

## Why this intervention is required

E2c found a negative `dla - ingress_dla` offered-task deadline-attainment direction in all four
matched fleet draws. Its inherited `dla` selector computes one common `argmin(rsu_busy_ms)` per
task substep and broadcasts that target to the substep's padded vehicle slots. E2d tests whether
the strongest-link comparison changes when the same least-busy criterion is recomputed after each
candidate's admitted service reservation. The E2c result is known, so E2d is not described as an
independent held-out replication.

No new strongest-link or inherited-DLA full run is needed. Reusing their exact E2c records makes
the one new construct the only scientific intervention and avoids eight unnecessary full cells.

## Source-level feasibility and terminology audit

At vec_env parent `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`, `rsu_busy_ms` is the total
remaining RSU compute workload in milliseconds of service work. Admitted `rsu_compute_ms` is
added, at most 1,000 ms is drained per simulated second, and the remainder is carried. Minimising
this state is therefore **least-busy / shortest-workload placement**, not a task-count
shortest-queue rule and not an assertion of canonical JSQ.

Inherited `dla` selects one `jnp.argmin(rsu_busy_ms)` target per Model-C task substep. The domain
is all configured RSUs: reachability, ingress quality and capacity do not filter the argmin.
Radio ingress remains the strongest-link RSU. The post-selection candidate check requires a
positive ingress-link quality and a selected target below the cap at substep entry.

Task substeps are scanned in ascending index. Within each substep, padded vehicle slots are
processed in ascending index, the same stable order used by existing co-batch offsets and scatter
updates. `jnp.argmin` resolves an exact workload tie to the lowest RSU index.

The inherited deadline gate is the strict backlog-only comparison

```text
effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]
```

It excludes the candidate's own service time, radio transfer, return transfer and forwarding
latency. “Deadline-aware feasibility” in E2d retains that exact limited meaning.

The service reservation is the realised RSU work used by the queue: split index 1 from the
existing five-way `process_agent` subkey split, evaluated by
`compute_time_ms(..., RSU_TIER_IDX)` and divided by the selected target's service multiplier.
E2d's locked multiplier is 1.0. No new random key or split is introduced.

Inherited common-target DLA needs its three-pass fixed-point reconciliation because vectorised
gate/cap rejection removes work from later offsets. The new causal scan never reserves rejected
work, so its first pass is already self-consistent. The implementation repeats the complete scan
from the same live `rb`/`rl` state for the configured three iterations and uses the final result.
The passes are deterministic and idempotent; work is not accumulated across passes. This is the
single scientifically coherent mapping of the inherited three-iteration setting onto a causal
per-task state update, and it preserves the same gate formula and outcome precedence.

## Exact `per_task_dla` algorithm

The implemented construct is **per-task sequential least-busy placement** (equivalently,
per-task sequential shortest-workload placement in the audited state units). At each task
substep:

1. initialise temporary effective busy/load vectors from live `rb`/`rl`;
2. scan padded vehicle slots in ascending index;
3. recompute the lowest-index `argmin(effective_busy_ms)` across all RSUs;
4. record that selected target for a V2I attempt;
5. apply inherited ingress-radio and substep-entry coarse-cap eligibility;
6. apply the strict backlog deadline gate at the selected target;
7. apply the live in-batch cap with inherited gate-before-cap outcome precedence;
8. only if admitted, add one load unit and the exact selected service work to temporary state;
9. leave temporary state unchanged for unavailable, gate-rejected or cap-rejected work;
10. commit admitted work later through the evaluator's unchanged queue scatter.

Actual execution is populated only for admitted V2I work. Forwarding is true exactly for admitted
execution away from strongest-link ingress. Rejected work retains selection where the frozen E2
instrumentation does, has execution `-1`, never forwards and never enters a queue. Forwarding
latency is zero under the frozen design.

The intervention can change placement, gate/cap outcomes and the admitted set by design. It does
not change radio ingress, actor observations/actions, PRNG structure, gate formula, deadline,
service unit/rate, queue/cap semantics, outcome taxonomy, reward, energy, latency, forwarding
definition, output schema or any existing mode branch.

## Frozen comparison and analysis

The primary per-seed estimand is:

```text
offered attainment(per_task_dla) - offered attainment(ingress_dla)
```

The secondary construct-validity contrast is:

```text
offered attainment(per_task_dla) - offered attainment(dla)
```

Only fleet seeds 1–4 are replication units. Seed 0 is not run or analysed. Each contrast reports
four raw differences, sign counts, mean, sample SD, SE, two-sided 95% Student-t interval with
three degrees of freedom, median and range. Individual tasks are never statistical replicates.
The primary decision labels are frozen in the manifest and analyzer before outcomes.

The configuration is the E2c Manchester incident hour, provisional `uk2030` fleet, evaluator seed
0, 2.5x/6,220-task cap, sequential queue, three iterations, conserved vehicle queue, reject
admission, fixed 1x service, scaling off and zero-cost backhaul. This isolates placement
construction; it does not test backhaul sensitivity.

## Validity and claim boundaries

A cell passes on identities, deterministic repeats, complete task outcomes, path reconciliation,
actor/task/fleet identity, V2I and vehicle-work conservation, finite values, checksums and exact
configuration—not on whether its deadline outcome improves.

The evidence remains limited to four matched draws from one provisional fleet family, one fixed
evaluator seed, one Manchester incident hour, one cap, fixed service and zero-cost backhaul. The
frozen actor neither observes current RSU load nor selects the execution RSU. Deadline attainment
is a simulator outcome, not confirmed physical task-result return. No ordinary/free-flow control,
physical deployment or Kubernetes execution is present. No task-level significance, equivalence,
universal least-busy result, general controller superiority, population-wide or Manchester-wide
claim is permitted.

No seed outside 1–4, existing-arm full rerun, `off`, `jsq`, P2C, nonzero backhaul, scaling,
learning, retraining, prediction, ordinary traffic, backend change or follow-on study is
authorised. E2d stops first for exact independent pre-run review and, if execution later passes,
for independent post-run evidence review.

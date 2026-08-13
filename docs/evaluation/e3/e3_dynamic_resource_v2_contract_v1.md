# E3 Dynamic Resource v2 — Scientific Contract v1

**Campaign:** `e3-dynamic-resource-v2`
**Contract version:** `e3_dynamic_resource_v2_contract_v1`
**Status:** `predeclared_before_any_e3_trace_execution`
**Created:** `2026-08-13`
**Base commit (exact):** `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`
**Lane:** `01` (`worker/e3-lane-01-contract`)

This is the **normative** scientific contract for the E3 dynamic-resource study. It is
predeclared before any E3 evaluator trace runs. The machine-readable twin
`e3_dynamic_resource_v2_contract_v1.json` is semantically equivalent; either file
governs, but the JSON is the strict validator input. Any post-observation source
change (evaluator code, actor, filtered trace, checklist, or derived manifest)
requires a **successor contract** with a new version and new hashes — it cannot
amend this contract in place.

---

## 1. Research question

> Under the frozen Manchester incident trace and frozen MAPPO vehicle actor, do
> infrastructure-side placement among `ingress_dla`, `per_task_dla`, and `p2c_dla`
> and dynamic compute-resource scaling among `fixed_1x`, `static_overprovisioned`,
> `reactive`, and `proactive` improve offered-task deadline attainment and its
> trade-off with rejection and resource cost, when evaluated as paired fleet-draw
> differences over four matched draws within the bounded staged grid where E3a
> isolates placement at `fixed_1x`, E3b holds placement fixed at `per_task_dla`
> for scaling contrasts, and E3c tests selected stale-state contrasts
> (`0/1000/3000 ms`), without fully crossing every placement with every scaler?

The comparison explicitly includes all three placement arms `ingress_dla`,
`per_task_dla`, and `p2c_dla` (not reduced to “strongest-link vs P2C”) and all four
scaling arms `fixed_1x`, `static_overprovisioned`, `reactive`, `proactive`. The
question isolates **three orthogonal mechanisms**:

| Mechanism | What it controls | What it does NOT control |
|---|---|---|
| **Placement** | Which RSU executes an admitted V2I task (`ingress_dla` vs `per_task_dla` vs `p2c_dla`) | Whether a task is admitted; how much compute is active |
| **Admission** | Whether an offered V2I task is admitted (deadline-aware feasibility gate) | Where it executes if admitted; compute capacity |
| **Scaling** | How many compute units (1–3) are active per RSU over time (`fixed_1x`/`static_overprovisioned`/`reactive`/`proactive`) | Which RSU is chosen; admission decision |

No experiment varies more than one mechanism in its primary contrast without a
separately labelled joint contrast. Learning, retraining, action masking, or
RSU-load observation by the vehicle actor are **out of scope** for E3.

The bounded staged grid does **not** fully cross every placement with every scaler.
Exactly: **E3a isolates placement** at `fixed_1x` (three placements × four draws),
**E3b holds placement fixed** at `per_task_dla` for scaling contrasts
(`fixed_1x`/`static_overprovisioned`/`reactive`/`proactive` × four draws), and
**E3c tests selected stale-state contrasts** (`0/1000/3000 ms` views on two
predeclared comparisons) rather than a full placement × scaler factorial. The phrase
`alone and jointly` is removed because it would imply a complete factorial crossing
that this bounded grid does not provide.

### 1.1 Predeclared hypotheses H1–H5 — hypotheses, not expected truths

All five hypotheses are predeclared with explicit status
`hypothesis_not_expected_truth` (strict typed value). They are **hypotheses**,
never results, conclusions, or expected truths. **Negative, null, or opposite
results are acceptable** and remain valid — no hypothesis requires superiority or
positive effect. Any report that relabels a hypothesis as a result/conclusion or
describes it as an expected truth violates this contract.

| ID | Status | Hypothesis (may, not truth) |
|---|---|---|
| H1 | `hypothesis_not_expected_truth` | P2C (`p2c_dla`) may approach `per_task_dla` offered deadline attainment with less global inspection (two feasible candidates vs. global least-busy scan), but may not exceed it. |
| H2 | `hypothesis_not_expected_truth` | Reactive scaling may improve deadline attainment or reduce rejection relative to `fixed_1x`, but may increase `resource_unit_seconds` and churn (scale actions). |
| H3 | `hypothesis_not_expected_truth` | Proactive scaling may help relative to reactive when load change outruns the 2s actuation delay (forecast horizon 2000 ms), but may not otherwise. |
| H4 | `hypothesis_not_expected_truth` | Global least-busy placement (`per_task_dla`) may degrade faster than P2C (`p2c_dla`) under stale state (`1000`/`3000 ms` delayed views). |
| H5 | `hypothesis_not_expected_truth` | Additional compute (`static_overprovisioned` or scaling-up policies) may not win once `resource_unit_seconds` is considered in the deadline–cost trade-off. |

Each hypothesis carries kind `hypothesis` and status `hypothesis_not_expected_truth`;
no hypothesis is a `result`, `conclusion`, or `expected_truth`.

---

## 2. Frozen prerequisites and identities

### 2.1 Closed E-series history (immutable, reused by hash)

| Study | Final commit | Manifest SHA-256 | Role |
|---|---|---|---|
| E2b | `fe2ed4e9bd9043b19b96a5f179390db629b01ccb` | (frozen E2b manifest) | Missing-cell factorial |
| E2c | `1a08d6e148a1e8c430da39c3d575eda3f8ea5929` | (frozen E2c manifest) | Gated placement replication |
| E2d | `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761` | `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740` | Per-task placement robustness |

E2 identities are **exact and preserved** — this contract does not rewrite them.

### 2.2 Frozen actor, trace, and evaluator seed

| Artifact | Path identity (logical) | SHA-256 |
|---|---|---|
| Actor | `checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz` | `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` |
| Trace | `traces/trace_inc_fullrsu.npz` | `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056` |
| Evaluator seed | `0` (all E3 cells) | — |

The actor is **frozen**: it never observes RSU load/backlog/busy state and never
selects the execution RSU. Its observation is exactly the 17-dim vehicle state
trained at seed 100. Any actor that conditions on RSU state is a different
actor and requires a successor contract.

The trace is the Manchester incident trace (`2024-03-15 20:00–21:00 Europe/London`,
`uk2030` provisional fleet, `lambda=1.5`, 10 RSUs, `padded_fleet_width=2488`,
`3600` steps). One **fleet draw** is one fixed padded-slot assignment for the
trace — not a new draw per unique SUMO vehicle. Fleet draws 1–4 are the only
authorised draws for primary inference; seed 0 is excluded from primary
intervals (it generated hypotheses).

### 2.3 Replication unit

Raw manifests serialize `fleet_seed` (integer 1–4). Frozen records explicitly
equate one `fleet_seed` value with one conceptual `fleet_draw`. Every E3 record
must serialize **both**:

- `replication_unit = "fleet_draw"` (conceptual unit)
- `replication_key = "fleet_seed"` (raw pairing key, integer)

`N` is the number of **fleet draws**, never the number of tasks. Tasks within a
draw are not independent replicates. `N=4` for every primary E3 interval.

---

## 3. Fixed scenario and evaluator constants

All E3 cells inherit the E2d scenario unless explicitly overridden by the
placement/scaling/staleness axes below:

- `steps = 3600`, `smoke_steps = 10`
- `evaluator_seed = 0`
- `fleet = "uk2030"` (provisional), `fleet_seeds = [1, 2, 3, 4]`
- `arrival_lambda = 1.5`, `waiting_room_cap_per_vehicle = 2.5` → `6220` tasks/RSU
- `rsus = 10`, `padded_fleet_width = 2488`
- `substep_queue = "sequential"` with 3 iterations, `vehicle_queue = "conserved"`
- `rsu_admission = "reject"` (rejected work never executes, §5)
- `backhaul_ms = 0.0` (zero-cost forwarding plane, except forwarding latency
  accounting where present)
- `rsu_cap_mode = "reject"`

Any deviation is a different study and requires a successor contract.

---

## 4. Queue ceiling is not compute capacity

The waiting-room / queue ceiling (`waiting_room_cap_per_vehicle`, `6220` tasks/RSU)
limits **how many tasks may wait** at an RSU. It does **not** represent RSU
processing power, core count, or service rate. Compute capacity is measured in
**compute units** (§7) and controls service rate. No report may describe a
waiting-room change as a compute-capacity change, and no validator may accept
`queue_cap == compute_capacity`. The arm `static_overprovisioned` is fixed 3×
compute service (multiplier `3`) and never queue capacity.

---

## 5. Rejected work never executes

A task that is **gate-rejected** (deadline-infeasible) or **cap-rejected**
(queue full) is never forwarded, never computed, never completed, and never
counts as deadline-met. Rejected tasks consume no compute service and incur no
execution-side resource cost beyond the admission decision itself. The
`task_outcome` taxonomy must reflect this; validator must reject any ledger
where a rejected task has a non-null execution RSU or positive compute time.

---

## 6. Placement, admission, and scaling — exact separation

### 6.1 Admission (deadline-aware feasibility gate)

All E3 arms use the **inherited deadline-aware admission gate**:

```
admit  iff  effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]
```

where `effective_busy_ms` is the RSU's remaining service workload in
milliseconds at the decision instant, and `TASK_DEADLINE_MS` is the per-type
deadline. The gate excludes own compute, radio transfer, return transfer, and
forwarding latency — it tests backlog only. Admission never selects a target;
it only gates the target already chosen by placement.

- `ingress_dla`: strongest-link ingress RSU + inherited gate
- `per_task_dla`: per-task sequential least-busy placement (§6.2) + same gate
- `p2c_dla`: P2C placement (§6.3) + same gate

### 6.2 Per-task placement (inherited from E2d, frozen)

`per_task_dla` is the E2d mechanism: for each V2I candidate in ascending
task-substep / padded-slot order, recompute `argmin(effective_busy_ms)` over all
10 RSUs, test the gate at that target, and on admission add the task's service
work to the temporary effective vectors before the next candidate. Ties break
by lowest RSU index. No RNG is involved.

### 6.3 P2C placement (power-of-two-choices, candidate for E3)

P2C is the **only new placement mechanism** in E3. Its contract is:

1. **Feasibility first.** Only RSUs whose effective backlog passes the feasibility
   gate (`effective_busy_ms < deadline`) are candidates. If zero or one feasible
   RSU exists, P2C reduces to direct admission/rejection at the feasible target
   or immediate rejection — no pair is fabricated.
2. **Two distinct feasible candidates without replacement.** Sample two distinct
   feasible RSUs uniformly without replacement using a **stable counter-based key**
   containing exactly `(evaluator_seed, fleet_seed, tick, task_slot, sequential_ordinal)`.
   The key is stable across reruns; no global RNG stream is consumed.
3. **Inspect only the pair.** Compare only the two sampled RSUs; no other RSU's
   state may be inspected for this decision.
4. **Lower declared workload wins.** Choose the candidate with lower
   `effective_busy_ms` (remaining service workload). Ties break by **lowest RSU id**
   (stable, deterministic).
5. **Immediate reservation.** On admission, immediately add the task's service
   work to the chosen RSU's effective backlog before the next candidate in the
   same tick/slot sequence.
6. **One candidate allowed.** P2C never revisits or re-samples for the same task;
   at most one admitted execution per offered task.
7. **Common-target prohibition.** P2C must not collapse to one common broadcast
   target per substep (the E2c `dla` limitation). Each task draws its own pair.

Validator must reject any P2C record that uses a global RNG without the counter
key, samples with replacement, inspects beyond the pair, or selects a common
target.

### 6.4 Stale snapshots (delayed views)

When `stale_ms > 0`, the placement decision and reactive/proactive scaling
signal see a **stale snapshot**: an immutable delayed view of
`service_workload_ms` / `arrival_work_ms` from `stale_ms` milliseconds ago.
Rules:

- Stale snapshots are **immutable delayed views** — they reflect the true state
  at `now - stale_ms` with no future leakage.
- **Same-tick reservation overlay:** admissions already decided in the current
  outer tick (1000 ms) are overlaid on the stale view, so two tasks in the same
  tick do not both see the same stale value without accounting for each other.
- Each staleness probe must expose `state_age_ms` (integer simulator ms, the age
  of the signal snapshot) so reviewers can verify the exact delay. Candidate
  levels are exactly `0, 1000, 3000 ms` in E3c.

---

## 7. Compute service and scaling

### 7.1 Compute service baseline

- `fixed_1x` means **one active compute unit per RSU**, i.e., the baseline service
  rate (`rsu_service_mult = 1.0`). It is a **compute-service** multiplier, not a
  queue size.
- `static_overprovisioned` means **fixed 3x compute** — three active units per RSU
  for the entire run, declared service multiplier `3`, no scaling. It never
  changes queue/waiting-room capacity. Arm IDs `static3x` and `static_3x` are
  forbidden synonyms.

### 7.2 Dynamic scaling bounds and configuration

Dynamic scaling varies active units per RSU within **1--3 capacity units** (1–3)
inclusive. The exact dynamic policy is defined in §7.3 (reactive) and §7.4
(proactive); inclusive thresholds `<=200ms` and `>=800ms` are **mutually exclusive**
and the `600ms` gap between them **is** hysteresis — no additional
`hysteresis_ms` excursion beyond the thresholds is required or allowed.
Every dynamic record must bind:

| Parameter | Exact value | Meaning |
|---|---|---|
| `signal` | `service_workload_ms` (reactive) / `arrival_work_ms` forecast (proactive) | work-ms, independent of capacity (reactive); per-RSU admitted arrival work (proactive) |
| `scale_up_threshold_ms` | `800` inclusive | scale up when `signal >= 800` |
| `scale_down_threshold_ms` | `200` inclusive | scale down when `signal <= 200` |
| `threshold_gap_ms` | `600` | hysteresis = mutually exclusive gap; stable inclusive edges |
| `cooldown_ms` | `5000` | from applied action; no new decision until cooldown elapsed |
| `actuation_delay_ms` | `2000` | exactly 2 outer ticks; bounds 1..3; one level per action |
| `actuation_delay_ticks` | `2` | same as 2000ms |
| `min_units` | `1` | floor |
| `max_units` | `3` | ceiling |
| `action_step` | `1` | exactly one level (±1) |
| `max_pending_actions` | `1` | at most one pending action per RSU; apply due actions before the tick's decision |

No configuration may specify unbounded, fractional-beyond-1–3, or free scaling.
Validator must reject any record with `min_units < 1`, `max_units > 3`, missing
thresholds, non-`800`/`200` thresholds, non-`600` gap, non-`5000` cooldown,
non-`2000`/`2` actuation delay, non-`±1` step, `hysteresis_ms` as extra
excursion, or more than one pending action, and must verify stable inclusive
edges and signal units.

### 7.3 Reactive scaling — exact specification

Reactive scaling uses **only the current observed per-RSU `service_workload_ms`**
(remaining service workload in work-ms, independent of capacity) at each RSU.
It does not predict future arrivals.

- Signal: `service_workload_ms` per RSU, work-ms, independent of capacity.
- Thresholds: scale **up** when `signal >= 800ms`; scale **down** when
  `signal <= 200ms` (inclusive, mutually exclusive; gap `600ms` is hysteresis).
- Cooldown: `5000ms` from **applied** action before next decision may be taken.
- Actuation delay: `2000ms` (2 outer ticks) from decision to effect.
- Bounds: `1..3` inclusive; action is exactly **one level** (`±1`).
- Pending: at most **one pending action** per RSU at any time.
- Timing: **apply due actions before the tick's decision** — actions that
  become due at tick `t` take effect before decisions for tick `t` are made.
- Edges: **stable inclusive edges** — `>=800` up, `<=200` down, with no extra
  `hysteresis_ms` beyond the thresholds.
- State age: reactive decisions use the current snapshot; when staleness is
  applied in E3c, state age is the age of the signal snapshot and candidate
  values are exactly `0, 1000, 3000ms`.

Validator must bind signal units, `800`/`200` inclusive thresholds, `600ms` gap,
`5000ms` cooldown from applied, `2000ms`/`2`-tick delay, `1..3` bounds, one-level,
one-pending, apply-due-before-decision, and state-age values, and reject any
`hysteresis_ms` excursion beyond thresholds.

### 7.4 Proactive scaling — exact specified method

Proactive scaling is transparent baseline, not an optimal predictor: a single specified baseline and not an optimal predictor. Candidate specification is exactly:

- **Signal:** per-RSU `admitted arrival_work_ms` observations at **one-second
  ticks** (outer tick `1000ms`).
- **Window:** exactly **four observations** `W[0]..W[3]` oldest-to-newest at
  `1-second` intervals; window order is oldest-to-newest.
- **Warm-up:** exactly **four valid observations** before any proactive decision
  is allowed; no decisions during warm-up.
- **Formula:** for that window `W`:
  ```
  older_mean  = mean(W[0:2])        # mean of first two points
  recent_mean = mean(W[2:4])        # mean of last two points
  trend       = recent_mean - older_mean
  forecast    = max(0, mean(W) + 2*trend)
  ```
  forecasting **two ticks (2000ms) ahead**. Mean is arithmetic mean.
- **No future leakage:** use only samples at or before the **declared
  observation time** `t`; no observation from `t+1` or later may be used to
  decide at `t`. `prediction_uses_future` must be `false`.
- **Thresholds:** scale **up** when `forecast >= 800ms`; scale **down** when
  `forecast <= 200ms` (same `600ms` gap/hysteresis, inclusive, mutually exclusive).
- **Shared timing/bounds:** same `cooldown 5000ms` from applied action,
  `actuation delay 2000ms` (2 ticks), bounds `1..3`, **one level**, **one pending
  action**, **apply due before the tick's decision**, **stable inclusive edges**.
- **Alternative formulas forbidden:** no alternative trend/forecast formulation may be substituted; only the exact formula above is allowed.

Validator must reject any proactive record with `window_size != 4`,
`window_interval_ms != 1000`, alternative window order, `warm_up < 4`,
formula deviating from exactly `mean(W[0:2])`/`mean(W[2:4])`/`recent-older`/
`max(0, mean+2*trend)`, `horizon_ms != 2000`, wrong thresholds, non-`5000`
cooldown, non-`2000` delay, wrong bounds/step/pending, future leakage,
or undisclosed `hysteresis_ms` excursion, and must enforce signal units
`admitted arrival_work_ms` at one-second ticks.

---

## 8. Time model

| Concept | Duration | Advances physical time? |
|---|---|---|
| Outer tick | `1000 ms` (1 second) | Yes |
| State age (`state_age_ms`) | Integer simulator ms; age of signal snapshot | — |
| Within-tick task slots | 5 slots per outer tick | **No** — slots order candidates within a tick without advancing the clock |
| Stale levels | `0, 1000, 3000 ms` | Candidate values only; reactive/proactive signal age |

Validator must reject any record claiming `state_age_ms = 200ms` or any
non-integer / non-multiple-of-1000 stale level, or any record where within-tick
slots advance the simulator clock.

---

## 9. Cost — resource_unit_seconds

Cost is **`resource_unit_seconds`**:

```
resource_unit_seconds = Σ_over_RSU Σ_over_interval (active_compute_units × interval_seconds)
```

It is **never monetary** (no currency, no billing, no price). The interval is
the outer tick (1 second) or finer accounting quantum if declared, but the
product is always `units × seconds`. Validator must reject any record with
`cost_currency`, `cost_dollars`, or equivalent monetary field. Arm
`static_overprovisioned` contributes `3 × interval_seconds` per RSU per interval.

---

## 10. Task accounting — required and unavailable

### 10.1 Required accounting (every cell must report)

| Field | Meaning |
|---|---|
| `offered` | All tasks the trace offered in the window |
| `admitted` | Tasks passing the admission gate and queue cap |
| `rejected` | `offered - admitted` (with breakdown) |
| `genuine_classes` | Per `task_type` offered/admitted/rejected split |
| `forwarded` | Admitted tasks whose execution RSU ≠ ingress RSU |
| `deadline_success` | Tasks with `task_met == true` |

Rejection breakdown must separate `gate_rejected` (deadline-infeasible) and
`cap_rejected` (queue full), plus `unavailable` (no feasible RSU).

### 10.2 Unavailable lifecycle fields (must remain null)

The following remain **null** with explicit reasons — E3 does not yet model
physical completion/return:

- `started = null` (reason: `"physical_execution_not_modelled"`)
- `compute_completed = null` (reason: `"physical_execution_not_modelled"`)
- `returned = null` (reason: `"result_return_not_modelled"`)
- `dropped = null` (reason: `"physical_drop_not_modelled"`)

Validator must reject any record where these fields are `0` or any non-null
value — zero is not null and would falsely imply measured zero rather than
unmodelled.

### 10.3 Outcome hierarchy

- **Headline:** `offered_deadline_attainment = deadline_success / offered`
- **Diagnostic:** `admitted_deadline_attainment = deadline_success / admitted`
  (conditional on admission; not the primary estimand)

Reports must present the headline first and label the diagnostic as conditional.
The scaling trade-off is reported jointly with rejection and
`resource_unit_seconds`.

---

## 11. Staged design — candidate before benchmark reduction

The full candidate grid is staged as E3a → E3b → E3c. All primary cells are
**fresh** (new runs), matched on `fleet_seed` (1–4), and use `fixed_1x` unless
the scaling axis explicitly varies. Identical fresh cells are reused across stage summaries rather than rerun and counted twice — the same physical fresh
execution serves any stage contrast that references it. Maximum candidate grid is
**60 unique cells**; the final machine plan must be **reduced before execution**
if a representative benchmark projects an unreasonable bounded local budget.

### 11.1 E3a — P2C placement under fixed 1x

| Dimension | Values |
|---|---|
| Placement | `ingress_dla`, `per_task_dla`, `p2c_dla` |
| Scaling | `fixed_1x` only |
| Staleness | `0 ms` only |
| Fleet draws | `1, 2, 3, 4` (fresh, matched) |

- **Cells:** 3 placements × 4 draws = **12 fresh cells**
- **Primary estimand:** `P2C_minus_per_task` offered deadline attainment
  (`p2c_dla - per_task_dla` at `fixed_1x`, `stale=0`)

### 11.2 E3b — Scaling trade-off family at fixed per-task placement

| Dimension | Values |
|---|---|
| Placement | `per_task_dla` (fixed) |
| Scaling | `fixed_1x`, `static_overprovisioned`, `reactive`, `proactive` |
| Staleness | `0 ms` only |
| Fleet draws | `1, 2, 3, 4` (fresh, matched) |

- **Cells:** 4 scaling × 4 draws = **16 fresh cells**
- **Co-primary trade-off family** (jointly interpreted):
  1. `deadline_attainment` (offered, headline)
  2. `rejection_rate` (rejected / offered)
  3. `resource_unit_seconds` (cost, §9 — denominator required)

No single metric dominates; the family is reported as a trade-off.
`static_overprovisioned` is fixed 3× compute service with multiplier `3`.

### 11.3 E3c — Staleness sensitivity (depends on fresh construct gates)

E3c **reuses identical fresh cells** from E3a/E3b — no new draws beyond the
fresh cells already defined. It compares:

| Contrast | At fixed | Over staleness |
|---|---|---|
| `per_task_dla` vs. `p2c_dla` | `fixed_1x` | `0, 1000, 3000 ms` |
| `reactive` vs. `proactive` | `per_task_dla` placement | `0, 1000, 3000 ms` |

Reused identical fresh cells serve multiple stage summaries; they are not
rerun and not counted twice in totals.

- **Additional cells for staleness variants:** staleness is a view parameter on
  placement decisions and scaling signals, not a separate fleet draw. If the
  evaluator requires reruns for stale views, each stale level is a distinct cell
  variant. Candidate unique stale-augmented cells ≤ 32 (E3a stale variants +
  E3b stale variants), but many are covered by reusing fresh `stale=0` cells.
- **Total candidate unique cells ≤ 60** (12 + 16 + ≤32). The exact count depends
  on whether stale views require reruns vs. post-hoc view replay — declared in
  the manifest.
- **E3c depends on fresh construct gates:** unit tests, construct tests (P2C
  feasibility, stable key, backlog reservation, stale immutability, scaling
  formula/bounds/timing), and tiny smoke must pass before E3c cells execute.

### 11.4 Budget reduction rule

Before any full 3600-step execution, a **representative benchmark** (at least one
full cell per arm type) must project total evaluator wall time and storage
against the bounded local budget (declared `maximum_evaluator_wall_seconds` and
`minimum_initial_free_bytes`). If the projection is unreasonable, the **final
machine plan must be reduced** — fewer stale levels, fewer scaling arms, or
fewer draws — and the reduction recorded in a manifest amendment. No silent
overrun.

---

## 12. Inference contract

For every primary and co-primary estimand:

1. **Unit:** `fleet_draw` (conceptual) keyed by `fleet_seed` (integer 1–4).
2. **Raw values:** report all four per-draw paired values.
3. **Paired differences:** `d_i = metric(treatment, draw_i) - metric(control, draw_i)`
   for `i = 1..4`, matched on `fleet_seed`.
4. **Summary:** mean difference `d̄`, sample SD `s` (Bessel, `n-1`), SE `= s/√n`.
5. **Interval:** two-sided **95% Student-t** interval with `df = n-1 = 3`,
   compatible with E2 unless predeclared otherwise:
   `d̄ ± t_{0.975,3} × SE`, where `t_{0.975,3} = 3.182`.
6. **Includes-zero flag:** `includes_zero = (interval_low ≤ 0 ≤ interval_high)`.
7. **Decision labels:**
   - `interval_above_zero` → directional advantage for treatment within bounded draws
   - `interval_below_zero` → directional deficit for treatment within bounded draws
   - `interval_includes_zero` → inconclusive at this replication size

**Prohibited:**

- Using tasks as `N` (task-as-N pseudoreplication)
- Reporting `p`-values as primary inference
- Citywide, population, or Manchester-wide generalisation
- Equivalence or non-inferiority claims without a predeclared margin
- Including seed 0 in primary intervals (seed 0 is hypothesis-generating only)

---

## 13. Execution preconditions and stop rules

### 13.1 Required before any full cell

- Unit tests pass (including validator and contract tests)
- Construct tests pass (P2C feasibility, stable counter key, reservation overlay,
  stale immutability, backlog-only admission, cost denominator, scaling exact
  thresholds/timing/formula)
- Tiny smoke: at least one `10`-step run per new arm (all checks pass)
- Representative benchmark: at least one `3600`-step cell per arm type, with
  runtime/storage projection
- Machine plan with exact cell list, order, and budget gate
- Independent review: `APPROVE` for exact TrafficTwin HEAD, vec_env commit, and
  manifest SHA-256
- Immutable manifest written and checksummed before first trace replay

### 13.2 Stop rules (any triggers immediate halt)

- Identity mismatch (actor/trace/evaluator/seed/manifest drift)
- Offered-task or fleet-assignment mismatch across matched draws
- Task accounting, path reconciliation, or work-conservation failure
- Rejected work executes or is forwarded
- Non-finite, negative, or monetary cost value
- Future leakage in proactive window or stale view
- Common-target P2C collapse
- Budget or storage gate violation
- Any unpredeclared arm, command, or code change required

---

## 14. What is preserved and what is not claimed

- E2, E2b, E2c, E2d remain **frozen history** — their manifests, validation
  records, and evidence indices are unchanged and cited by hash.
- This contract authorises **only** the bounded E3 study described above.
- Physical result-return, monetary cost, Kubernetes orchestration, learned
  controllers, and Manchester-wide deployment claims are **not tested** and must
  not be implied.
- Any post-observation source change creates a **successor contract**.

---

## 15. Validation

The validator `scripts/validate_e3_dynamic_resource_contract.py` enforces this
contract strictly. It rejects (at minimum):

- `queue_ceiling == compute_capacity` or `static_overprovisioned` interpreted as queue
- Task replication (tasks as `N`)
- Actor observes RSU load or selects execution RSU
- Free, unbounded, or threshold-free scaling; wrong thresholds/gap/cooldown/delay/bounds/step; extra `hysteresis_ms` excursion; wrong signal units; extra pending action; wrong timing
- Proactive window not exactly four one-second `arrival_work_ms` samples oldest-to-newest, warm-up not four, formula not `max(0, mean+2*trend)` with `older_mean=mean(W[0:2])`/`recent_mean=mean(W[2:4])`, horizon not 2000ms, or future leakage
- Legacy arm IDs `static3x`/`static_3x`/`fixed1x`/`static3x`-style synonyms
- Unavailable lifecycle fields coerced to `0` instead of `null`
- Monetary cost (`cost_currency`, `cost_dollars`)
- Hidden `fleet_seed` label (missing `replication_key` or `replication_unit`)
- `200 ms` pseudo-time state ages or non-integer staleness
- Missing `resource_unit_seconds` denominator
- Actual Kubernetes orchestration claim
- Future leakage in proactive window
- Common-target P2C

Mutation tests in `tests/test_e3_dynamic_resource_contract.py` prove each
rejection by changing a valid payload and observing failure **without editing
the canonical contract file in place**.

---

## 16. Manifest and review

The E3 manifest (to be written before execution) will bind:

- Exact TrafficTwin, vec_env, and tos-data commits
- Actor/trace/evaluator identities and hashes
- Full 60-cell candidate grid and reduced machine plan (reused identical fresh
  cells not double-counted)
- Scaling configurations (exact thresholds `800`/`200`/`600`, cooldown `5000`,
  delays `2000`, bounds `1..3`, one-level, one-pending, timing, signal units,
  and proactive formula `max(0, mean+2*trend)`)
- P2C and proactive formulas with warm-up
- Compute/storage projections and budget gates
- Review verdicts (`APPROVE` exact SHA)

No E3 trace execution is authorised until that manifest is independently
reviewed and approved.

---

*End of normative contract v1.*

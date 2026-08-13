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

- **Additional cells for staleness variants:** staleness is a view parameter on placement decisions and scaling signals, not a separate fleet draw. If the evaluator requires reruns for stale views, each stale level is a distinct cell variant. Candidate unique stale-augmented cells are exactly **32 additional** cells beyond the 28 fresh cells (12 E3a + 16 E3b), for a **total of 60** unique cells (12 + 16 + 32). This is the 32-cell explanatory gloss: 32 stale-augmented variants plus 28 fresh cells equals 60 total; many stale=0 cells are reused across stage summaries rather than rerun and not counted twice.
- **Total candidate unique cells = 60** (12 + 16 + 32). The count is exact for the candidate grid; if stale views are executed via post-hoc replay rather than reruns the physical rerun count may be lower, but the candidate unique total remains 60 — declared in the manifest.
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

## 15. Validation (predeclaration scope)

The validator `scripts/validate_e3_dynamic_resource_contract.py` is a **predeclaration-only** validator. It enforces this contract strictly before any E3 trace execution. It rejects (at minimum):

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

Later result ledger, record, and manifest validators remain **dependency-gated** and are not implied by a passing predeclaration check; this validator does not pretend to validate post-execution ledgers.

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


## Appendix — Canonical JSON (machine-readable)

This appendix is the deterministic machine-readable twin. The fenced JSON block is generated deterministically via `json.dumps(sort_keys=True, indent=2)` from the canonical JSON and must byte-equally match it. Validators check deep equality and byte-equivalence; prose is not parsed as data.

## 20. Exact P2C candidate predicate and low-cardinality behavior

A task has **no execution candidates** unless it is an active frozen-actor V2I attempt and its ingress radio is currently viable. For such an attempt, the sorted feasible RSU set contains exactly each RSU for which BOTH: (a) `observed_decision_backlog_work_ms[rsu] < task_deadline_ms`; and (b) `true_current_waiting_room_occupancy[rsu]` plus prior same-tick admitted reservations is strictly below the unchanged queue ceiling. Radio and queue safety are current; only the backlog/deadline belief is aged. `n=0`: select no target and reject without execution. If ingress radio is not viable, classify `v2i_unavailable`. Otherwise, if no RSU is observed deadline feasible classify `v2i_gate_rejected`; otherwise (deadline-feasible RSUs exist but all are full) classify `v2i_cap_rejected`. `n=1`: select that sole feasible RSU without a second hash/modulo and record ranking inspections=1. `n>=2`: use the deterministic distinct pair and lower observed backlog, stable lowest-ID tie break. Reserve true load/raw work and decision overlay immediately only on admission. Kill sample-before-filter, stale queue-cap, undefined n=0/1, rejection ambiguity, or rejected-work reservation.

---

## 21. Fully reproducible uint64 P2C mixer

Declare every field as non-negative unsigned 64-bit with bounds, ordered exactly `evaluator_seed`, `fleet_seed`, `outer_tick`, `task_slot`, `sequential_task_ordinal`. Use wrap modulo 2^64 after every operation. Define SplitMix64 exactly: `z=(x+0x9E3779B97F4A7C15) mod 2^64; z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64; z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64; return z xor (z>>31)`. Fold with `h=0x6A09E667F3BCC909`, then for each ordered field `h=splitmix64(h xor uint64(field))`. For `n>=2` `first_index=h % n; j=splitmix64(h) % (n-1); second_index=j if j<first_index else j+1`. Candidate order is ascending unique RSU ID; sort the resulting pair only for telemetry, not before indexing. Three independently computed exact hex/index test vectors are normative: all-zero fields `h=0x7d19c361a3548205` with `n=10` gives `first_index=9, second_index=1, sorted_pair=[1,9]`; boundary `evaluator_seed=0,fleet_seed=1,outer_tick=3599,task_slot=4,sequential_task_ordinal=12439` gives `h=0x295c562a48f4f730` with `n=10` gives `first_index=2, second_index=7, sorted_pair=[2,7]`; and `evaluator_seed=0,fleet_seed=2,outer_tick=1234,task_slot=2,sequential_task_ordinal=5678` gives `h=0x350f2378ad774558` with `n=10` gives `first_index=2, second_index=8, sorted_pair=[2,8]`. For `n=1` hashing is skipped. Kill alternate SplitMix variants, string/byte serialization, signed overflow, field reordering, or missing vectors. Do not claim modulo exact uniformity. The candidate order is sorted ascending unique feasible RSU IDs, final pair sorted, hash is SplitMix64, uniformity not claimed because modulo reduction has negligible bias. Resource-state diagnostics use capacity-adjusted utilization drained_work_ms / (active_capacity_units * 1000 work_ms) bounded [0,1]; waiting-room occupancy is a separate task count and never denominator. Execution share is actual admitted V2I execution count at RSU / total admitted V2I execution count; when denominator is zero it is null with an explicit reason, not zeros. Target switching is counted over consecutive admitted V2I tasks in the exact deterministic (outer_tick, task_slot, vehicle_slot) order; first admitted task is not a switch, rejected/non-V2I tasks are excluded, and counts never cross fleet draws. Resource_unit_seconds denominator stays required for diagnostic deadline per resource cost. H1 is hypothesis about pair-only ranking vs global least-busy dependence not proved networking cost; must not claim only two total global state reads or proven lower total state acquisition or distributed communication savings. Not double-counted, transparent baseline, not an optimal predictor, work-ms, independent of capacity, optimistic stale admitted executes and may miss per true latency, pessimistic stale rejected never executes, deadline_success is based on true simulated latency never the controller's stale estimate, not evidence of physical started/completed/returned lifecycle, do not retroactively reprice, dense position identity, independent of active mask, feasibility_workload_checks, ranking_workload_inspections, unique_workload_values_observed, only two total global state reads, proven lower total state acquisition, pair-only ranking, drained_work_ms / (active_capacity_units * 1000 work_ms), actual admitted V2I execution count, when denominator is zero it is null, Target switching is counted over consecutive admitted V2I, first admitted task is not a switch, resource_unit_seconds denominator stays required.

---

## 22. Canonical tick/snapshot/scaler transition, used by every E3 cell

Use `control_clock_offset_ms=3000` and the same telemetry schema for E3a/b/c, including fresh cells, so reused `state_age=0` cell bytes can truly be identical. At each zero-based trace tick with control time `t`: (i) start from true state after the prior interval drain; (ii) apply the one pending action if due, emit applied receipt, clear pending; (iii) capture the immutable tick-entry infrastructure snapshot after due action application and before any current-tick placement/admission; (iv) select the exact `t-state_age` snapshot for decision signals; (v) if no pending action and cooldown permits, make at most one scaler decision per RSU and possibly emit/schedule one requested action; (vi) process all five task slots sequentially without advancing time; (vii) drain true raw backlog once by `min(backlog,u*1000 work_ms)`; (viii) charge post-due-action capacity `u` for interval `[t,t+1000ms)`. Cooldown starts at actual application time; `elapsed>=5000ms` permits a new request. A just-applied action starts cooldown, so cannot request again that tick. Any pending action blocks all new directions. Requested receipt fields: `draw,rsu,direction,from_units,requested_to_units,decision_time_ms,due_time_ms,observed_state_time_ms,state_age_ms,signal_name,signal_value`. Applied receipt adds `actual_application_time_ms` and `actual_to_units`. Counts expose scheduled requests and applied up/down actions separately; resource cost follows applied capacity only. Kill decision-time cooldown, same-tick post-apply request, action-count conflation, or ambiguous timestamps. Reactive tick-entry signal is the aged raw service backlog snapshot. Proactive samples are completed prior trace-interval admitted-arrival-work samples: at tick `t` no sample from current tick is available; four actual trace intervals must have completed, and an aged arm uses only samples that are present in its selected snapshot. Pretrace empty values never satisfy warm-up. Kill use of current/future arrivals or environment-produced samples that have not become observable under the declared lag.

---

## 23. Exact simulated V2I latency/outcome contract

At admission time record, with `u=current applied units`: `simulated_latency_ms = current_ingress_tx_ms + forwarding_ms + true_execution_backlog_work_ms/u + raw_task_service_work_ms/u + current_return_tx_ms`. Radio/forward/return formulas and random raw service draw remain inherited; raw work enqueued is never divided by `u`. Deadline success is this recorded admitted simulated latency `< task deadline`. Later scaling does not recompute latency; backlog still evolves thereafter under actual capacity. Rejected work never enqueues, never succeeds, and the inherited `10*deadline` penalty is explicitly not a valid latency observation. Report admitted-task latency only (and any declared deadline-met diagnostic); offered-task latency is null/unavailable because rejected penalty values are not physical latency. `started`, `compute_completed`, `returned` and `dropped` remain null with reasons. Kill backlog-only/stale outcome latency, divided enqueue work, later repricing, or rejected penalty in a latency mean.

---

## 24. Lossless accounting and exact contrast completion

Require and validate task counts: `offered = admitted + rejected; rejected = v2i_gate_rejected + v2i_cap_rejected + local_mqd_rejected + v2v_mqd_rejected + v2i_unavailable + v2v_unavailable; 0 <= deadline_success <= admitted; 0 <= forwarded <= admitted_v2i <= admitted`. Rejection share is `rejected/offered`; forwarding share is `forwarded/admitted_v2i` and is null+reason if denominator zero. Deadline per normalized cost is `offered deadline attainment/resource_unit_seconds` and is null+reason if resource cost is zero (cost should be positive for a complete cell). Also preserve exact work-ms conservation where instrumented, separately for V2I and vehicle queues; unavailable V2V work has no destination-service work and remains an explicit count rather than fabricated zero work. Missing/incomplete cells make the matched contrast status incomplete/null; never reduce `n`. A reportable contrast requires all four paired seeds 1..4 and uses exact treatment-minus-control sign. Predeclare machine-readable contrast IDs/signs/metrics: E3a primary `p2c_dla-minus-per_task_dla` for offered deadline attainment at `fixed_1x/state_age=0`; secondary `p2c_dla-minus-ingress_dla`. E3b, `per_task_dla/state_age=0`: each of `static_overprovisioned`, `reactive`, `proactive` minus `fixed_1x` for the co-primary family `offered deadline attainment,rejection_share,resource_unit_seconds`, plus `proactive-minus-reactive` as a declared diagnostic. No scalar 'best' objective. E3c at each state age: `p2c_dla-minus-per_task_dla` under `fixed_1x`, and `proactive-minus-reactive` under `per_task_dla`, for `offered deadline attainment, rejection_share,resource_unit_seconds` plus declared imbalance/action diagnostics. Keep draw as `N=4`; tasks never become replicates.

---

<!-- BEGIN_E3_CANONICAL_JSON -->
```json
{
  "accounting_and_contrast_completion": {
    "draw_is_N_4_tasks_never_become_replicates": true,
    "lossless_accounting": {
      "deadline_success_between_0_and_admitted": true,
      "forwarded_between_0_and_admitted_v2i_between_0_and_admitted": true,
      "offered_equals_admitted_plus_rejected": true,
      "rejected_equals_sum": [
        "v2i_gate_rejected",
        "v2i_cap_rejected",
        "local_mqd_rejected",
        "v2v_mqd_rejected",
        "v2i_unavailable",
        "v2v_unavailable"
      ]
    },
    "missing_incomplete_cells_make_matched_contrast_status_incomplete_null_never_reduce_n": true,
    "predeclared_contrasts": {
      "E3a_primary": {
        "for": "offered deadline attainment at fixed_1x/state_age=0",
        "id": "p2c_dla-minus-per_task_dla",
        "secondary": "p2c_dla-minus-ingress_dla"
      },
      "E3b_per_task_dla_state_age_0": {
        "each_of": [
          "static_overprovisioned",
          "reactive",
          "proactive"
        ],
        "for_co_primary_family": [
          "offered deadline attainment",
          "rejection_share",
          "resource_unit_seconds"
        ],
        "minus": "fixed_1x",
        "no_scalar_best_objective": true,
        "plus_proactive_minus_reactive_as_declared_diagnostic": true
      },
      "E3c_at_each_state_age": {
        "contrasts": [
          "p2c_dla-minus-per_task_dla under fixed_1x",
          "proactive-minus-reactive under per_task_dla"
        ],
        "for": [
          "offered deadline attainment",
          "rejection_share",
          "resource_unit_seconds"
        ],
        "plus_declared_imbalance_action_diagnostics": true
      }
    },
    "reportable_contrast_requires_all_four_paired_seeds_1_to_4_and_uses_exact_treatment_minus_control_sign": true,
    "shares": {
      "deadline_per_normalized_cost_is_offered_deadline_attainment_div_resource_unit_seconds_and_null_reason_if_cost_zero": true,
      "forwarding_share_is_forwarded_div_admitted_v2i_and_null_reason_if_denominator_zero": true,
      "rejection_share_is_rejected_div_offered": true
    },
    "unavailable_V2V_work_has_no_destination_service_work_and_remains_explicit_count_rather_than_fabricated_zero_work": true,
    "work_ms_conservation_where_instrumented_separately_for_V2I_and_vehicle_queues": true
  },
  "admission_gate": {
    "excludes": [
      "own_compute",
      "radio_transfer",
      "return_transfer",
      "forwarding_latency"
    ],
    "formula": "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]",
    "never_selects_target": true,
    "queue_safety_uses_current_not_stale": true,
    "radio_viability_is_current": true,
    "stale_view_applies_to_deadline_workload": true,
    "state_units": "milliseconds_of_remaining_service_workload"
  },
  "authority_note": "JSON is the single normative scientific contract; Markdown is a deterministic generated view via render_markdown and must byte-equal its output (byte mismatch is authoritative).",
  "base_commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
  "branch": "worker/e3-lane-01-contract",
  "campaign": "e3-dynamic-resource-v2",
  "claim_boundaries": {
    "any_post_observation_source_change_requires_successor": true,
    "kubernetes_orchestration_tested": false,
    "learned_controller_tested": false,
    "manchester_wide_deployment_tested": false,
    "monetary_cost_tested": false,
    "physical_result_return_tested": false,
    "proactive_is_transparent_baseline_not_optimal": true
  },
  "compute_scaling": {
    "dynamic_bounds": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "apply_due_before_tick_decision": true,
      "free_scaling_forbidden": true,
      "hysteresis_is_gap": true,
      "hysteresis_ms_extra_forbidden": true,
      "max_pending_actions": 1,
      "max_units": 3,
      "min_units": 1,
      "one_level_per_action": true,
      "threshold_gap_ms": 600,
      "unbounded_scaling_forbidden": true
    },
    "fixed_1x": {
      "active_units_per_rsu": 1,
      "multiplier": 1,
      "rsu_service_mult": 1.0,
      "scaling": "off"
    },
    "proactive": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "alternative_formula_forbidden": true,
      "apply_due_before_tick_decision": true,
      "bounds_max": 3,
      "bounds_min": 1,
      "cooldown_ms": 5000,
      "formula_declared": true,
      "formulas": {
        "forecast": "max(0, mean(W) + 2*trend)",
        "older_mean": "mean(W[0:2])",
        "recent_mean": "mean(W[2:4])",
        "trend": "recent_mean - older_mean"
      },
      "horizon_ms": 2000,
      "horizon_ticks": 2,
      "hysteresis_is_gap": true,
      "max_pending_actions": 1,
      "ml": false,
      "no_decisions_during_warm_up": true,
      "no_future_leakage": true,
      "observation_interval_ms": 1000,
      "per_rsu": true,
      "prediction_uses_future": false,
      "scale_down_inclusive": true,
      "scale_down_threshold_ms": 200,
      "scale_up_inclusive": true,
      "scale_up_threshold_ms": 800,
      "signal": "arrival_work_ms",
      "stable_inclusive_edges": true,
      "threshold_gap_ms": 600,
      "transparent": true,
      "transparent_baseline_not_optimal": true,
      "uses_only_samples_at_or_before_observation_time": true,
      "warm_up_ticks_declared": true,
      "warm_up_valid_observations": 4,
      "window_interval_ms": 1000,
      "window_order": "oldest_to_newest",
      "window_size": 4
    },
    "reactive": {
      "action_step": 1,
      "actuation_delay_ms": 2000,
      "actuation_delay_ticks": 2,
      "apply_due_before_tick_decision": true,
      "cooldown_ms": 5000,
      "hysteresis_is_gap": true,
      "hysteresis_ms_extra": false,
      "max_pending_actions": 1,
      "max_units": 3,
      "min_units": 1,
      "per_rsu": true,
      "prediction": false,
      "scale_down_inclusive": true,
      "scale_down_threshold_ms": 200,
      "scale_up_inclusive": true,
      "scale_up_threshold_ms": 800,
      "signal": "service_workload_ms",
      "signal_units": "work_ms_independent_of_capacity",
      "stable_inclusive_edges": true,
      "state_age_ms_values": [
        0,
        1000,
        3000
      ],
      "threshold_gap_ms": 600
    },
    "static_overprovisioned": {
      "active_units_per_rsu": 3,
      "forbidden_synonyms_rejected": [
        "static3x",
        "static_3x"
      ],
      "is_compute_not_queue": true,
      "multiplier": 3,
      "rsu_service_mult": 3.0,
      "scaling": "off"
    },
    "unit": "compute_unit (service capacity, not queue slots)"
  },
  "compute_service_semantics": {
    "active_capacity_for_entire_tick": true,
    "admission_gate_unit": "raw_backlog_work_ms",
    "at_most_one_interval_per_RSU_per_tick": true,
    "backlog_equation": "backlog_work_ms[t+1] = backlog_work_ms[t] + enqueued_raw_work_ms - drained_work_ms",
    "backlog_is_invariant_baseline": true,
    "backlog_storage_unit": "work_ms",
    "drain_applies_to_all_queued_work_including_pre_scale": true,
    "drain_capacity_is_not_queue_slots": true,
    "drain_equation": "drain_work_ms = min(backlog_work_ms, active_capacity_units * 1000)",
    "drain_tick_ms": 1000,
    "enqueue_adds_raw_1x_work_ms": true,
    "enqueue_equation": "enqueued_work_ms = raw_1x_service_work_ms",
    "enqueue_forbidden_division": "enqueued_work_ms != raw_1x_service_work_ms / active_capacity_units",
    "enqueue_must_not_divide_by_capacity": true,
    "initial_capacities": {
      "dynamic_max_units": 3,
      "dynamic_min_units": 1,
      "dynamic_start_units": 1,
      "fixed_1x_units": 1,
      "static_overprovisioned_from_tick": 0,
      "static_overprovisioned_units": 3
    },
    "latency_equation": "(raw_work_ahead_ms + raw_own_service_work_ms) / active_capacity_units",
    "latency_not_retroactively_repriced": true,
    "latency_physical_lifecycle_fields_remain_null": true,
    "latency_radio_forwarding_unchanged": true,
    "latency_semantics": "admission_time_estimate_not_physical_lifecycle",
    "placement_workloads_unit": "raw_backlog_work_ms",
    "proactive_observation_unit": "raw_admitted_arrival_work_ms",
    "queue_ceiling_uses_current_occupancy_plus_same_tick_reservations": true,
    "queue_safety_is_current_not_stale": true,
    "reactive_signal_unit": "raw_backlog_work_ms",
    "reduces_to_E2d_at_fixed_1x": true,
    "reduction_equation": "at fixed_1x (u=1): drain = min(backlog_work_ms, 1000) and latency = raw_work_ahead_ms + raw_own_service_work_ms",
    "resource_time_charged_even_when_idle": true,
    "resource_time_equation": "resource_unit_seconds_per_RSU_per_tick = active_capacity_units * 1",
    "same_tick_reservation_overlay_unit": "raw_task_work_ms",
    "scaling_applied_at_tick_start_before_placement_admission": true,
    "scaling_applied_before_latency_estimate_and_drain": true,
    "scaling_forbidden_units": [
      "queue_slots",
      "capacity_normalized_work_ms"
    ],
    "scaling_must_not_change_placement_or_admission_unit": true,
    "stale_does_not_mutate_true_state": true,
    "stale_snapshot_unit": "raw_backlog_work_ms"
  },
  "contract_authority": "json_is_normative_markdown_is_generated_view",
  "cost": {
    "forbidden_fields": [
      "cost_currency",
      "cost_dollars",
      "cost_price",
      "cost_billing"
    ],
    "formula": "sum_over_RSU sum_over_interval (active_compute_units * interval_seconds)",
    "interval_seconds": 1,
    "metric": "resource_unit_seconds",
    "monetary": false
  },
  "created": "2026-08-13",
  "execution_preconditions": {
    "before_any_full_cell": [
      "unit_tests_pass",
      "construct_tests_pass",
      "tiny_smoke_10step_per_new_arm",
      "representative_benchmark_3600_per_arm_type",
      "runtime_storage_projection",
      "machine_plan_with_exact_cells_and_order",
      "independent_review_APPROVE_exact_HEAD_and_manifest_SHA",
      "immutable_manifest_before_first_replay"
    ],
    "stop_rules": [
      "identity_mismatch",
      "offered_or_fleet_mismatch_across_matched_draws",
      "task_accounting_or_conservation_failure",
      "rejected_work_executes_or_forwards",
      "non_finite_or_negative_or_monetary_cost",
      "future_leakage",
      "common_target_p2c",
      "budget_or_storage_gate_violation",
      "unpredeclared_arm_or_code_change"
    ]
  },
  "frozen_prerequisites": {
    "actor": {
      "frozen": true,
      "observes_current_rsu_load": false,
      "path": "checkpoints/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz",
      "selects_execution_rsu": false,
      "sha256": "93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208"
    },
    "e2b": {
      "commit": "fe2ed4e9bd9043b19b96a5f179390db629b01ccb",
      "status": "closed"
    },
    "e2c": {
      "commit": "1a08d6e148a1e8c430da39c3d575eda3f8ea5929",
      "status": "closed"
    },
    "e2d": {
      "commit": "80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761",
      "manifest_sha256": "f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740",
      "status": "closed"
    },
    "evaluator_seed": 0,
    "trace": {
      "path": "traces/trace_inc_fullrsu.npz",
      "sha256": "e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056"
    }
  },
  "h1_state_inspection": {
    "any_duplicated_reads_remain_visible": true,
    "common_feasibility_decision_observation_cost_remains_visible": true,
    "feasibility_first_must_enumerate_all_RSU_deadline_feasibility": true,
    "forbidden_claims": [
      "two_total_reads",
      "hidden_feasibility_scan",
      "communication_savings_proven"
    ],
    "h1_is_hypothesis_about_pair_only_ranking_vs_global_least_busy_dependence_not_proved_networking_cost": true,
    "h1_remains_hypothesis_allowed_to_fail": true,
    "must_not_claim_distributed_communication_savings": true,
    "must_not_claim_only_two_total_global_reads": true,
    "must_not_claim_proven_lower_total_state_acquisition": true,
    "p2c_ranking_inspection_is_0_1_2_according_to_feasible_count": true,
    "per_task_dla_global_argmin_ranks_all_R": true,
    "separately_record": [
      "feasibility_workload_checks",
      "ranking_workload_inspections",
      "unique_workload_values_observed"
    ]
  },
  "hypotheses": {
    "boundary": "negative, null, or opposite results acceptable; hypotheses are not expected truths",
    "hypotheses_are_not_expected_truths": true,
    "items": [
      {
        "compares": [
          "p2c_dla",
          "per_task_dla"
        ],
        "id": "H1",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "offered_deadline_attainment",
        "statement": "P2C (p2c_dla) may approach per_task_dla offered deadline attainment with less global inspection, but may not exceed it.",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "reactive",
          "fixed_1x"
        ],
        "id": "H2",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "deadline_attainment_rejection_resource_tradeoff",
        "statement": "Reactive scaling may improve deadline attainment or reduce rejection relative to fixed_1x, but may increase resource_unit_seconds and churn (scale actions).",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "proactive",
          "reactive"
        ],
        "id": "H3",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "deadline_attainment",
        "statement": "Proactive scaling may help relative to reactive when load change outruns the 2s actuation delay, but may not otherwise.",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "per_task_dla",
          "p2c_dla"
        ],
        "id": "H4",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "offered_deadline_attainment_under_staleness",
        "statement": "Global least-busy placement (per_task_dla) may degrade faster than P2C (p2c_dla) under stale state (1000/3000 ms).",
        "status": "hypothesis_not_expected_truth"
      },
      {
        "compares": [
          "static_overprovisioned",
          "fixed_1x"
        ],
        "id": "H5",
        "interpretation": "hypothesis_not_expected_truth",
        "kind": "hypothesis",
        "metric": "resource_unit_seconds_tradeoff",
        "statement": "Additional compute (static_overprovisioned or scaling-up policies) may not win once resource_unit_seconds is considered in the deadline–cost trade-off.",
        "status": "hypothesis_not_expected_truth"
      }
    ],
    "negative_results_acceptable": true,
    "note": "All hypotheses are predeclared as hypotheses_not_expected_truths; negative, null, or opposite results are acceptable and remain valid. No hypothesis is an expected truth or guaranteed result."
  },
  "inference": {
    "compatible_with_e2_unless_predeclared": true,
    "decisions": {
      "interval_above_zero": "directional_advantage_for_treatment_within_bounded_draws",
      "interval_below_zero": "directional_deficit_for_treatment_within_bounded_draws",
      "interval_includes_zero": "inconclusive_at_this_replication_size"
    },
    "fleet_seeds": [
      1,
      2,
      3,
      4
    ],
    "forbidden": [
      "task_as_n",
      "p_value_as_primary",
      "citywide_generalisation",
      "population_claim",
      "equivalence_without_margin",
      "seed_0_in_primary"
    ],
    "includes_zero_flag": true,
    "interval": "two-sided 95% Student-t, df=3, t_0.975,3 = 3.182",
    "key": "fleet_seed",
    "mean_difference": "d_bar = mean(d_i)",
    "n": 4,
    "paired_differences": "d_i = metric(treatment, draw_i) - metric(control, draw_i) matched on fleet_seed",
    "per_draw_values_required": true,
    "sample_sd": "Bessel n-1",
    "se": "s / sqrt(n)",
    "unit": "fleet_draw"
  },
  "lane": "01",
  "markdown_is_generated_view": true,
  "mechanism_separation": {
    "actor_never_observes_rsu_load": true,
    "actor_never_selects_execution_rsu": true,
    "admission": "Whether an offered V2I task is admitted (deadline feasibility gate)",
    "placement": "Which RSU executes an admitted V2I task",
    "queue_ceiling_is_not_compute_capacity": true,
    "rejected_work_never_executes": true,
    "scaling": "How many compute units (1-3) are active per RSU over time"
  },
  "p2c_candidate_predicate": {
    "admission_requires": "active frozen-actor V2I attempt and ingress radio currently viable",
    "feasible_RSU_predicate": {
      "candidate_order": "sorted ascending unique feasible RSU IDs",
      "conditions_both": [
        "observed_decision_backlog_work_ms[rsu] < task_deadline_ms",
        "true_current_waiting_room_occupancy[rsu] + prior same-tick admitted reservations < queue_ceiling"
      ],
      "only_backlog_deadline_belief_is_aged": true,
      "queue_safety_is_current_not_stale": true,
      "radio_is_current": true
    },
    "forbidden_behaviors": [
      "sample-before-filter",
      "stale queue-cap",
      "undefined n=0/1",
      "rejection ambiguity",
      "rejected-work reservation"
    ],
    "n_equals_0": {
      "classification": {
        "elif_no_RSU_observed_deadline_feasible": "v2i_gate_rejected",
        "else_deadline_feasible_exist_but_all_full": "v2i_cap_rejected",
        "if_ingress_radio_not_viable": "v2i_unavailable"
      },
      "reject_without_execution": true,
      "select_no_target": true
    },
    "n_equals_1": {
      "hashing_skipped": true,
      "no_second_hash_modulo": true,
      "ranking_inspections": 1,
      "select_sole_feasible_RSU": true
    },
    "n_gte_2": {
      "deterministic_distinct_pair": true,
      "selection": "lower observed backlog",
      "tie_break": "stable lowest-ID",
      "without_replacement": true
    },
    "reservation": {
      "rejected_work_never_reserved": true,
      "reserve_true_load_raw_work_and_decision_overlay_immediately_only_on_admission": true
    }
  },
  "p2c_dense_counter_key_mapping": {
    "declared_mixer_fields_remain_exactly_five": [
      "evaluator_seed",
      "fleet_seed",
      "outer_tick",
      "task_slot",
      "sequential_task_ordinal"
    ],
    "forbidden_behaviors": [
      "active_only_ordinal",
      "ordinal_reset_or_collision",
      "200ms_time_interpretation",
      "outcome_dependent_key_shifts"
    ],
    "outer_tick": {
      "advances_physical_time": "per_outer_tick_1000ms",
      "definition": "zero_based_trace_tick",
      "range": "[0,3599]"
    },
    "outer_tick_is_zero_based": true,
    "padded_fleet_width": 2488,
    "per_outer_tick_range": "[0,12439]",
    "sequential_task_ordinal": {
      "dense_position_identity": true,
      "earlier_outcomes_never_shift_later_pairs": true,
      "formula": "task_slot * padded_fleet_width + vehicle_slot",
      "independent_of_active_mask": true,
      "independent_of_actor_choice": true,
      "independent_of_admission_or_rejection": true,
      "independent_of_feasibility": true,
      "per_outer_tick": true,
      "range": "[0,12439]"
    },
    "task_slot": {
      "advances_physical_time": false,
      "definition": "zero_based_within_tick_substep",
      "note": "does not advance physical time",
      "range": "[0,4]"
    },
    "task_slot_is_zero_based": true,
    "vehicle_slot": {
      "definition": "zero_based_padded_fleet_slot",
      "padded_fleet_width": 2488,
      "range": "[0,2487]"
    },
    "vehicle_slot_is_provenance_but_not_mixer_field": true,
    "vehicle_slot_is_zero_based": true
  },
  "p2c_mixer": {
    "field_declaration": {
      "bounds": {
        "evaluator_seed": "[0, 2^64-1] actual 0",
        "fleet_seed": "[0, 2^64-1] actual [1,4] for primary draws",
        "outer_tick": "[0, 3599]",
        "sequential_task_ordinal": "[0, 12439]",
        "task_slot": "[0, 4]"
      },
      "field_type": "non-negative unsigned 64-bit (uint64)",
      "fields_ordered": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "wrap_modulo": "2^64 after every operation"
    },
    "fold": {
      "field_order": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "for_each_ordered_field": "h=splitmix64(h xor uint64(field))",
      "h_init": "0x6A09E667F3BCC909"
    },
    "forbidden_behaviors": [
      "alternate SplitMix variants",
      "string/byte serialization",
      "signed overflow",
      "field reordering",
      "missing vectors",
      "claim modulo exact uniformity"
    ],
    "modulo_bias_note": "modulo reduction has negligible bias not mathematically exact-uniform",
    "pair_indices": {
      "for_n_equals_0_no_indices": true,
      "for_n_equals_1_hashing_skipped": true,
      "for_n_gte_2": {
        "candidate_order_is_ascending_unique_RSU_ID": true,
        "first_index": "h % n",
        "j": "splitmix64(h) % (n-1)",
        "second_index": "j if j<first_index else j+1",
        "sort_resulting_pair_only_for_telemetry_not_before_indexing": true
      }
    },
    "splitmix64_definition": {
      "constants_hex": [
        "0x9E3779B97F4A7C15",
        "0xBF58476D1CE4E5B9",
        "0x94D049BB133111EB"
      ],
      "steps": [
        "z=(x+0x9E3779B97F4A7C15) mod 2^64",
        "z=((z xor (z>>30))*0xBF58476D1CE4E5B9) mod 2^64",
        "z=((z xor (z>>27))*0x94D049BB133111EB) mod 2^64",
        "return z xor (z>>31)"
      ],
      "wrap_modulo_2_64_after_every_operation": true
    },
    "test_vectors": [
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 0,
          "outer_tick": 0,
          "sequential_task_ordinal": 0,
          "task_slot": 0
        },
        "first_index": 9,
        "h_dec": 9014450953278226949,
        "h_hex": "0x7d19c361a3548205",
        "n": 10,
        "note": "all-zero fields",
        "second_index": 1,
        "sorted_pair": [
          1,
          9
        ]
      },
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 1,
          "outer_tick": 3599,
          "sequential_task_ordinal": 12439,
          "task_slot": 4
        },
        "first_index": 2,
        "h_dec": 2980351793025054512,
        "h_hex": "0x295c562a48f4f730",
        "n": 10,
        "note": "boundary outer_tick=3599/task_slot=4/ordinal=12439",
        "second_index": 7,
        "sorted_pair": [
          2,
          7
        ]
      },
      {
        "fields": {
          "evaluator_seed": 0,
          "fleet_seed": 2,
          "outer_tick": 1234,
          "sequential_task_ordinal": 5678,
          "task_slot": 2
        },
        "first_index": 2,
        "h_dec": 3823313609874163032,
        "h_hex": "0x350f2378ad774558",
        "n": 10,
        "note": "mid vector",
        "second_index": 8,
        "sorted_pair": [
          2,
          8
        ]
      }
    ],
    "uniformity_claim_forbidden": true
  },
  "permission_boundaries": {
    "authorised_after_exact_approval": "bounded fresh E3a/E3b/E3c cells as reduced machine plan, matched analysis, private branches",
    "forbidden": [
      "trace_run_before_exact_approval",
      "seed_0_in_primary",
      "new_ingress_dla_dla_without_fresh",
      "nonzero_backhaul",
      "scaling_outside_1_3",
      "learning_retraining",
      "actor_observes_rsu_load"
    ]
  },
  "placement": {
    "ingress_dla": {
      "admission": "inherited_deadline_aware_gate",
      "mechanism": "strongest-link ingress execution"
    },
    "p2c_dla": {
      "candidates": 2,
      "common_target_forbidden": true,
      "counter_key_fields": [
        "evaluator_seed",
        "fleet_seed",
        "outer_tick",
        "task_slot",
        "sequential_task_ordinal"
      ],
      "counter_key_stable": true,
      "distinct_feasible_only": true,
      "feasibility_first": true,
      "h1_concern": "pair_only_inspection_global_state_dependence_not_statistical_uniformity_proof",
      "immediate_reservation": true,
      "inspect_only_pair": true,
      "mechanism": "power-of-two-choices with feasibility-first",
      "modulo_bias_note": "modulo reduction has negligible bias not mathematically exact-uniform",
      "no_global_rng_stream": true,
      "one_candidate_per_task": true,
      "pair_mapper": {
        "candidate_order": "sorted_ascending_unique_feasible_RSU_IDs",
        "distinct_without_replacement": true,
        "final_pair_sorted": true,
        "first_index_formula": "h % n",
        "hash": "SplitMix64",
        "hash_input_fields_exact": [
          "evaluator_seed",
          "fleet_seed",
          "outer_tick",
          "task_slot",
          "sequential_task_ordinal"
        ],
        "mapper_type": "deterministic_pseudo_random_modulo_mapper",
        "no_hidden_global_RNG": true,
        "second_index_formula": "splitmix64(h) % (n-1) adjusted around first",
        "uniformity_not_claimed": true
      },
      "selection": "lower effective_busy_ms",
      "stale_snapshot": {
        "delay_ms_field": "state_age_ms",
        "exposes_state_age_ms": true,
        "immutable_delayed_view": true,
        "no_future_leakage": true,
        "same_tick_reservation_overlay": true
      },
      "tie_break": "lowest RSU id (stable)",
      "uniformity_claim_forbidden": [
        "uniform",
        "unbiased",
        "exact-uniform",
        "exact_uniform"
      ],
      "without_replacement": true
    },
    "per_task_dla": {
      "gate": "same inherited deadline gate applied causally per candidate",
      "mechanism": "per-task sequential least-busy placement",
      "order": "ascending task-substep then padded-slot index",
      "reservation": "add service work to effective vectors only on admission",
      "rng": "none",
      "state": "effective_busy_ms (remaining service workload)",
      "tie_break": "lowest RSU index (jnp.argmin)"
    }
  },
  "replication": {
    "fleet_draw_note": "One fleet_draw is one fixed padded-slot assignment for the trace, not a new draw per unique SUMO vehicle.",
    "fleet_seeds": [
      1,
      2,
      3,
      4
    ],
    "n": 4,
    "replication_key": "fleet_seed",
    "replication_unit": "fleet_draw",
    "seed_0_in_primary": false,
    "tasks_are_not_replicates": true
  },
  "research_question": "Under the frozen Manchester incident trace and frozen MAPPO vehicle actor, do infrastructure-side placement among ingress_dla, per_task_dla, and p2c_dla and dynamic compute-resource scaling among fixed_1x, static_overprovisioned, reactive, and proactive improve offered-task deadline attainment and its trade-off with rejection and resource cost, when evaluated as paired fleet-draw differences over four matched draws within the bounded staged grid where E3a isolates placement at fixed_1x, E3b holds placement fixed at per_task_dla for scaling contrasts, and E3c tests selected stale-state contrasts (0/1000/3000 ms), without fully crossing every placement with every scaler?",
  "resource_state_diagnostics": {
    "capacity_adjusted_utilization": {
      "bounded": "[0,1]",
      "formula": "drained_work_ms / (active_capacity_units * 1000 work_ms)",
      "utilization_is_per_RSU_per_tick": true,
      "waiting_room_occupancy_is_separate_task_count_and_never_denominator": true
    },
    "execution_share": {
      "formula": "actual_admitted_V2I_execution_count_at_RSU / total_admitted_V2I_execution_count",
      "when_denominator_zero_is_null_with_explicit_reason_not_zeros": true
    },
    "forbidden_behaviors": [
      "raw_over_1000_utilization_under_u_gt_1",
      "queue_occupancy_as_denominator",
      "zero_fill_shares_when_denominator_zero",
      "rejected_task_switches",
      "unordered_or_across_draw_switches",
      "missing_cost_denominator"
    ],
    "no_monetary_or_automatically_authoritative_objective_claim": true,
    "resource_unit_seconds_denominator_stays_required_for_diagnostic_deadline_per_resource_cost": true,
    "target_switching": {
      "counted_over_consecutive_admitted_V2I_tasks_in_deterministic_order": "(outer_tick, task_slot, vehicle_slot)",
      "counts_never_cross_fleet_draws": true,
      "first_admitted_task_is_not_a_switch": true,
      "order_is_exact_deterministic_outer_tick_task_slot_vehicle_slot": true,
      "rejected_and_non_V2I_tasks_excluded": true
    }
  },
  "scenario": {
    "arrival_lambda": 1.5,
    "backhaul_ms": 0.0,
    "date": "2024-03-15",
    "fleet": "uk2030",
    "fleet_status": "provisional",
    "padded_fleet_width": 2488,
    "resolved_cap_tasks_per_rsu": 6220,
    "rsu_admission": "reject",
    "rsu_cap_mode": "reject",
    "rsus": 10,
    "scenario": "Manchester incident trace",
    "smoke_steps": 10,
    "steps": 3600,
    "substep_queue": "sequential",
    "substep_queue_iterations": 3,
    "vehicle_queue": "conserved",
    "waiting_room_cap_per_vehicle": 2.5,
    "window_local": "20:00-21:00 Europe/London"
  },
  "schema_version": "e3_dynamic_resource_v2_contract_v1",
  "staged_design": {
    "budget_reduction_required_if_unreasonable": true,
    "e3a": {
      "cells": 12,
      "equation": "3 placements * 1 scaling * 1 stale * 4 draws = 12",
      "fleet_seeds": [
        1,
        2,
        3,
        4
      ],
      "fresh": true,
      "label": "P2C placement under fixed 1x",
      "placement": [
        "ingress_dla",
        "per_task_dla",
        "p2c_dla"
      ],
      "primary_estimand": "p2c_dla minus per_task_dla offered deadline attainment at fixed_1x stale=0",
      "scaling": [
        "fixed_1x"
      ],
      "scaling_ids_exact": [
        "fixed_1x"
      ],
      "stage_listed_cells": 12,
      "stale_ms": [
        0
      ],
      "unique_cells": 12
    },
    "e3a_stage_listed_cells": 12,
    "e3a_unique_cells": 12,
    "e3b": {
      "cells": 16,
      "co_primary_family": [
        "offered_deadline_attainment",
        "rejection_rate",
        "resource_unit_seconds"
      ],
      "co_primary_note": "Trade-off family, no single metric dominates",
      "equation": "4 scalers * 1 placement * 1 stale * 4 draws = 16 stage-listed; 16 - 4 overlap = 12 unique",
      "fleet_seeds": [
        1,
        2,
        3,
        4
      ],
      "fresh": true,
      "label": "Scaling trade-off family at fixed per-task placement",
      "overlap_note": "per_task_dla/fixed_1x/state_age_ms=0 byte-identical to E3a reused not rerun",
      "overlap_with_e3a": 4,
      "placement": [
        "per_task_dla"
      ],
      "scaling": [
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive"
      ],
      "scaling_ids_exact": [
        "fixed_1x",
        "static_overprovisioned",
        "reactive",
        "proactive"
      ],
      "stage_listed_cells": 16,
      "stale_ms": [
        0
      ],
      "unique_additional": 12,
      "unique_cells": 12
    },
    "e3b_overlap_with_e3a": 4,
    "e3b_stage_listed_cells": 16,
    "e3b_unique_additional": 12,
    "e3b_unique_equation": "16 - 4 = 12",
    "e3c": {
      "additional_stale_variant_cells_max": 32,
      "contrasts": [
        {
          "comparison": "per_task_dla vs p2c_dla",
          "fixed": "fixed_1x",
          "over_stale_ms": [
            0,
            1000,
            3000
          ]
        },
        {
          "comparison": "reactive vs proactive",
          "fixed_placement": "per_task_dla",
          "over_stale_ms": [
            0,
            1000,
            3000
          ]
        }
      ],
      "depends_on": "fresh construct gates (unit, construct, tiny smoke)",
      "equation": "2 contrasts * 3 staleness * 2 placements? 48 observations; 32 stale variants unique",
      "fresh_observations_reused": 16,
      "identical_fresh_cells_reused_not_rerun": true,
      "label": "Staleness sensitivity (reuses identical fresh cells)",
      "not_double_counted": true,
      "reuses_identical_fresh_cells": true,
      "stale_is_view_parameter": true,
      "stale_variant_equation": "48 - 16 = 32",
      "total_contrast_observations": 48
    },
    "e3c_fresh_observations_reused": 16,
    "e3c_stale_variant_equation": "48 - 16 = 32",
    "e3c_total_contrast_observations": 48,
    "identical_fresh_cells_reused_not_rerun": true,
    "maximum_candidate_unique_cells": 56,
    "not_double_counted": true,
    "note": "Candidate grid before benchmark reduction; final machine plan must be reduced if representative benchmark projects unreasonable bounded local budget. Identical fresh cells are reused across stage summaries rather than rerun and counted twice. Stage-listed base/additional entries = 60 (12 E3a + 16 E3b stage-listed + 32 E3c stale variants); unique planned executions = 56 (12 + 12 + 32) after reusing 4 E3a/E3b overlaps and 16 E3c fresh observations. Equations: 12+16+32=60 stage-listed; 12+12+32=56 unique; 48 total E3c contrast observations -16 fresh reused =32 stale variants. Equations with spaces: 12 + 16 + 32 = 60 stage-listed; 12 + 12 + 32 = 56 unique.",
    "stage_listed_cells": 60,
    "stage_listed_equation": "12 + 16 + 32 = 60",
    "unique_equation": "12 + 12 + 32 = 56"
  },
  "stale_decision_vs_true_execution": {
    "current_capacity_action_application_and_drain_operate_on_true_state": true,
    "deadline_admission_gate_uses_observed_backlog_only": true,
    "deadline_success_based_on_true_simulated_latency_never_stale_estimate": true,
    "deadline_success_is_simulator_outcome_not_physical_lifecycle_evidence": true,
    "forbidden_behaviors": [
      "stale_belief_used_for_actual_latency_or_success",
      "true_state_used_for_stale_decision",
      "executing_pessimistically_rejected_work",
      "delaying_true_capacity_or_drain"
    ],
    "later_scale_actions_do_not_retroactively_reprice_recorded_task": true,
    "observed_decision_backlog_work_ms": "fresh_or_delayed_immutable_backlog_work_ms_plus_decision_overlay_plus_same_tick_reservation_overlay",
    "observed_decision_definition": "fresh/delayed immutable workload plus the decision overlay (stale view plus same-tick reservation overlay); placement and the backlog-only deadline admission gate use this observed value",
    "optimistic_stale_admitted_executes_and_may_miss_per_true_latency": true,
    "pessimistic_stale_rejected_never_executes_even_if_true_would_have_been_feasible": true,
    "physical_started_completed_returned_remain_null": true,
    "placement_uses_observed": true,
    "queue_cap_safety_still_wins_current_not_stale": true,
    "scaling_decisions_observe_delayed_signals": true,
    "true_execution_backlog_work_ms": "current_true_backlog_work_ms_plus_actual_prior_same_tick_admitted_work_at_chosen_RSU",
    "true_execution_determines": [
      "simulated_queue_wait",
      "task_latency",
      "deadline_success",
      "enqueue",
      "subsequent_true_drain"
    ]
  },
  "stale_state_semantics": {
    "applies_to": [
      "invariant_raw_backlog_work_ms_view_for_placement",
      "inherited_backlog_only_deadline_gate",
      "reactive_signal",
      "proactive_signal"
    ],
    "deadline_formula_unchanged": "effective_busy_ms[selected_rsu] < TASK_DEADLINE_MS[task_type]",
    "deadline_workload_observation_has_state_age": true,
    "does_not_mutate": [
      "true_environment",
      "current_active_capacity",
      "pending_actions",
      "current_queue_safety_state"
    ],
    "exposes": [
      "requested_state_age_ms",
      "actual_state_age_ms",
      "observation_time_ms",
      "control_time_ms"
    ],
    "forbidden_behaviors": [
      "stale_deadline_view_silently_becoming_fresh",
      "stale_queue_cap",
      "mutation_of_true_state",
      "pretrace_values_counted_as_proactive_warmup",
      "clock_clamp",
      "state_age_laundering",
      "offset_added_to_action_delay"
    ],
    "fresh_cells_reusable_because": {
      "formulas_use_elapsed_differences": true,
      "offset_does_not_enter_p2c_key_outer_tick_does": true,
      "state_age_0_views_identical": true
    },
    "initialization": {
      "applies_when": "when_stale_robustness_evaluated_all_arms",
      "control_clock_offset_ms": 3000,
      "infrastructure_backlog_and_admitted_arrival_history": "inherited_empty_initial_state",
      "is_declared_simulator_initial_condition": true,
      "not_observed_pretrace_manchester_traffic": true,
      "not_real_world_historical_claim": true,
      "permits_exact_0_1000_3000_without_clamping": true,
      "permits_no_future_leakage": true,
      "permits_no_unavailable_age_laundering": true,
      "prepopulate_control_times_ms": [
        0,
        1000,
        2000
      ],
      "prepopulate_value": "empty_initial_infrastructure_state",
      "pretrace_zeros_do_not_satisfy_proactive_warmup": true,
      "proactive_still_requires_four_actual_trace_observations": true,
      "scaling_delay_cooldown_use_control_clock_differences_no_extra_delay": true,
      "trace_tick_0_maps_to_control_time_ms": 3000
    },
    "queue_ceiling_enforcement": "true_current_waiting_room_occupancy_plus_same_tick_admitted_reservations",
    "queue_ceiling_uses_stale_view": false,
    "queue_safety_invariant_is_current": true,
    "queue_safety_uses_current_not_stale": true,
    "radio_viability_is_current_frozen_channel": true
  },
  "status": "predeclared_before_any_e3_trace_execution",
  "task_accounting": {
    "genuine_classes_dimension": "task_type",
    "outcome_hierarchy": {
      "diagnostic": "admitted_deadline_attainment = deadline_success / admitted (conditional)",
      "headline": "offered_deadline_attainment = deadline_success / offered",
      "headline_is_offered": true
    },
    "rejected_never_executes": true,
    "rejection_breakdown": [
      "gate_rejected",
      "cap_rejected",
      "unavailable"
    ],
    "required": [
      "offered",
      "admitted",
      "rejected",
      "genuine_classes",
      "forwarded",
      "deadline_success"
    ],
    "unavailable_lifecycle": {
      "compute_completed": null,
      "compute_completed_reason": "physical_execution_not_modelled",
      "dropped": null,
      "dropped_reason": "physical_drop_not_modelled",
      "null_means_unmodelled_not_zero": true,
      "returned": null,
      "returned_reason": "result_return_not_modelled",
      "started": null,
      "started_reason": "physical_execution_not_modelled"
    }
  },
  "tick_transition": {
    "applied_receipt_adds": [
      "actual_application_time_ms",
      "actual_to_units"
    ],
    "control_clock_offset_ms": 3000,
    "cooldown": {
      "any_pending_action_blocks_all_new_directions": true,
      "elapsed_gte_5000ms_permits_new_request": true,
      "just_applied_action_starts_cooldown_so_cannot_request_again_that_tick": true,
      "starts_at_actual_application_time": true
    },
    "counts_expose_separately": [
      "scheduled_requests",
      "applied_up_actions",
      "applied_down_actions"
    ],
    "forbidden_behaviors": [
      "decision-time cooldown",
      "same-tick post-apply request",
      "action-count conflation",
      "ambiguous timestamps"
    ],
    "future_leakage_forbidden": true,
    "proactive_samples_are_completed_prior_trace_interval_admitted_arrival_work_samples": {
      "aged_arm_uses_only_samples_present_in_selected_snapshot": true,
      "at_tick_t_no_sample_from_current_tick_available": true,
      "four_actual_trace_intervals_must_have_completed": true,
      "pretrace_empty_values_never_satisfy_warm_up": true
    },
    "reactive_tick_entry_signal_is_aged_raw_service_backlog_snapshot": true,
    "requested_receipt_fields": [
      "draw",
      "rsu",
      "direction",
      "from_units",
      "requested_to_units",
      "decision_time_ms",
      "due_time_ms",
      "observed_state_time_ms",
      "state_age_ms",
      "signal_name",
      "signal_value"
    ],
    "resource_cost_follows_applied_capacity_only": true,
    "reused_state_age_0_cell_bytes_truly_identical": true,
    "telemetry_schema_same_for_E3a_b_c_including_fresh_cells": true,
    "zero_based_trace_tick_control_time_t": {
      "i_start_from_true_state_after_prior_interval_drain": true,
      "ii_apply_one_pending_action_if_due_emit_applied_receipt_clear_pending": true,
      "iii_capture_immutable_tick_entry_infrastructure_snapshot_after_due_action_before_current_tick_placement_admission": true,
      "iv_select_exact_t_state_age_snapshot_for_decision_signals": true,
      "v_if_no_pending_and_cooldown_permits_make_at_most_one_scaler_decision_per_RSU_and_possibly_emit_schedule_one_requested_action": true,
      "vi_process_all_five_task_slots_sequentially_without_advancing_time": true,
      "vii_drain_true_raw_backlog_once_by_min_backlog_u_times_1000_work_ms": true,
      "viii_charge_post_due_action_capacity_u_for_interval_t_t_plus_1000ms": true
    }
  },
  "time_model": {
    "candidate_stale_levels_ms": [
      0,
      1000,
      3000
    ],
    "control_clock_applies_when": "when_stale_robustness_evaluated_all_arms",
    "control_clock_offset_ms": 3000,
    "is_declared_simulator_initial_condition_not_observed_traffic": true,
    "outer_tick_ms": 1000,
    "permits_exact_views_without_clamping": true,
    "prepopulate_control_times_ms": [
      0,
      1000,
      2000
    ],
    "prepopulate_value": "empty_initial_infrastructure_state",
    "proactive_pretrace_does_not_satisfy_warmup": true,
    "scaling_delay_uses_control_clock_differences": true,
    "stale_levels_are_candidate_values": true,
    "state_age_is_signal_snapshot_age": true,
    "state_age_unit": "integer_simulator_ms",
    "trace_tick_0_maps_to_control_time_ms": 3000,
    "within_tick_slots_advance_physical_time": false,
    "within_tick_task_slots": 5
  },
  "v2i_latency_outcome_contract": {
    "at_admission_record_with_u_current_applied_units": {
      "backlog_still_evolves_thereafter_under_actual_capacity": true,
      "deadline_success_is_recorded_admitted_simulated_latency_less_task_deadline": true,
      "later_scaling_does_not_recompute_latency": true,
      "radio_forward_return_formulas_and_random_raw_service_draw_remain_inherited": true,
      "raw_work_enqueued_is_never_divided_by_u": true,
      "rejected_work_never_enqueues_never_succeeds_and_inherited_10_deadline_penalty_is_explicitly_not_valid_latency_observation": true,
      "simulated_latency_ms_equation": "current_ingress_tx_ms + forwarding_ms + true_execution_backlog_work_ms/u + raw_task_service_work_ms/u + current_return_tx_ms"
    },
    "forbidden_behaviors": [
      "backlog-only/stale outcome latency",
      "divided enqueue work",
      "later repricing",
      "rejected penalty in latency mean"
    ],
    "report": {
      "admitted_task_latency_only_and_any_declared_deadline_met_diagnostic": true,
      "offered_task_latency_is_null_unavailable_because_rejected_penalty_values_are_not_physical_latency": true,
      "started_compute_completed_returned_dropped_remain_null_with_reasons": true
    }
  }
}
```
<!-- END_E3_CANONICAL_JSON -->

*End of normative contract v1.*

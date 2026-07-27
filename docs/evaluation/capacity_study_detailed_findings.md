# The Capacity-Squeeze Finding in Full Detail — Setup, Execution, Results, Interpretation

**Status: exploratory `owner_approved_candidate` evidence, descriptive and non-causal
throughout.** This is the long-form narrative companion to the concise
[pilot results record](capacity_pilot_results_20260727.md); every number below traces to a
committed artifact or the local hash-verified analysis outputs, and nothing here upgrades
any claim beyond its recorded ceiling. The separate held-out confirmatory campaign (signed
[candidate (b)](capacity_confirmatory_candidate_b_latency_primary.md)) was in execution
when this document was written; its result is reported in its own record, never here.

- Written: 27 July 2026, after the pilot completed (12/12 cells) and before the
  confirmatory receipt existed
- Design fingerprint (pilot): `de474e038523e5e79e2d167364f312dc7c2ea273e610f2d26ec1cf253f41bb90`
- Analysis artifacts: `data/vec-fresh/capacity-pilot/campaign_analysis.{json,md}` (local,
  hash-verified); mechanism exhibit:
  [capacity_pilot_mechanism_report_20260727.md](capacity_pilot_mechanism_report_20260727.md)

## 1. The question

Vehicular edge computing assumes roadside units (RSUs) absorb the computation that
vehicles cannot do onboard. The obvious stress question: **if RSU capacity is squeezed,
does task-deadline attainment degrade gracefully — or fall off a cliff?** The
predeclared hypothesis (H1) expected a cliff somewhere on the studied grid; the
predeclaration equally committed to publishing the null with identical prominence.

## 2. The environment: whose simulator, whose traffic

- **Traffic**: a pre-recorded trace produced by the upstream researcher's calibrated SUMO
  model of the Manchester **Etihad / Co-op Live event district** (not city-wide). The
  pilot uses the `inc` trace: **Friday 2024-03-15, 20:00–21:00 — a documented
  reactive-rule VSL-collapse hour**, SUMO seed 43, per the producer's provenance sidecar
  (`traces/PROVENANCE.md`, upstream commit `6e56393`). The trace is a *film*: per-second
  positions for up to **2,488 concurrent vehicle slots over 3,600 seconds**, replayed
  identically in every run. SUMO itself never executes during our experiments.
- **Physics and policy**: the upstream JAX evaluator (pinned `vec_env` commit
  `068b4ea3…`) overlays a computing economy on the film each second — synthetic task
  arrivals in three 3GPP-grounded classes (safety 100 ms, platooning 500 ms, awareness
  100 ms), a heterogeneous fleet of onboard computers dealt by the fleet seed, radio
  physics from recorded positions, queueing, and energy. The trained **MAPPO actor
  `ukfleettrain_mappo_model_c_17`** decides per task: local / offload to RSU (V2I) /
  offload to neighbour (V2V).
- **Integrity**: trace and occupancy identities are Gate-A audited
  (trace sha `e188ce07…`); the trace joined the reviewed allowlist only after a measured
  identity-reconciliation probe (ADR-062); execution is CPU-only, matching the pinned
  numerical-equivalence evidence.

## 3. The instrument: what TrafficTwin adds

The experiment ran through the platform's full evidence chain:

1. **Predeclaration before results existed** — design, arms, seeds, primary endpoint,
   analysis plan, and the null-publication commitment fixed in
   [the pilot predeclaration](capacity_squeeze_pilot_predeclaration.md); approval recorded
   with its exact SHA-256 and re-verified at run time (ADR-063).
2. **Bounded campaign execution** — 12 cells, seed-major order, sequential foreground,
   declared cell/byte budgets, halt-on-failure; each cell is one full 3,600-step
   evaluator run with a hash-verified receipt.
3. **Fresh-run scientific admission (ADR-061)** — every cell's published bytes
   re-verified, per-second task-join reconciliation, then registry admission; anything
   that does not reconcile is refused, never repaired.
4. **Predeclared statistics** — STA-01 common-seed paired studies with tool defaults
   (0.95 confidence, 10,000/10,000 resampling, fixed resampling seed), rendered by the
   deterministic analysis harness whose non-confirmatory status is a type-level literal.

## 4. The experimental knob, precisely

`rsu_capacity_per_vehicle` bounds **how many tasks an RSU may serve concurrently,
expressed per padded vehicle slot in the scene**. Arms: baseline **2.5**, variations
**1.5, 1.0, 0.75** — a **3.3×** squeeze end to end. The per-*padded*-vehicle semantics is
a recorded interpretation limit: the knob is a resource-pressure dial of the evaluator,
not a physical Manchester quantity. Everything else — trace bytes, actor checkpoint,
fleet preset (`uk2030`), evaluator seed (0), task generation, timeout (7,200 s) — is
pinned identical across arms. Pairing is on **fleet seed {0, 1, 2}**: the same dealt
fleet experiences every capacity level, so each seed is its own control.

## 5. Execution record

12/12 cells executed and admitted, zero failures, zero skips; **12.47 hours** of
sequential compute on one Apple M5 laptop (CPU-only, ~390% of the 4 performance cores);
cells ran 3,534.6–3,846.7 s; **1.17 GB** of hash-verified outputs; registry
`.demo/registry-capacity-pilot.sqlite`; the campaign receipt's design fingerprint matches
the committed launcher script (`scripts/capacity_pilot_campaign.py`) exactly.

## 6. Results

### 6.1 Primary endpoint: deadline-success rate — flat (the predeclared null holds)

Arm means by descending capacity: **0.790412 / 0.790522 / 0.790591 / 0.790737** — every
*reduction* in capacity is associated with a faint *rise* (+0.000110, +0.000069,
+0.000146 per adjacent step). Per seed:

| fleet seed | cap-2.5 | cap-1.5 | cap-1.0 | cap-0.75 |
|---|---|---|---|---|
| 0 | 0.792485 | 0.792816 | 0.793023 | 0.793179 |
| 1 | 0.812794 | 0.812794 | 0.812794 | 0.813074 |
| 2 | 0.765957 | 0.765957 | 0.765957 | 0.765957 |

Note the honesty detail: seeds 1 and 2 are *exactly unchanged* at most levels — the tiny
positive mean differences rest almost entirely on seed 0. The predeclared paired
comparisons (variation − baseline): +0.000111 [0.000000, 0.000332], +0.000180
[0.000000, 0.000539], +0.000325 [0.000000, 0.000694]; randomisation diagnostics 1.0 /
1.0 / 0.5, reported verbatim and never as acceptance. **The hypothesised cliff does not
exist on this grid.**

### 6.2 Secondary: mean task latency — monotone 3.2× collapse

Arm means: **9,798.8 → 6,029.6 → 4,089.9 → 3,083.6 ms** by descending capacity. Per seed
(ms):

| fleet seed | cap-2.5 | cap-1.5 | cap-1.0 | cap-0.75 |
|---|---|---|---|---|
| 0 | 9,942.6 | 6,061.7 | 4,068.0 | 3,060.7 |
| 1 | 6,277.9 | 3,961.8 | 2,771.9 | 2,097.7 |
| 2 | 13,176.0 | 8,065.2 | 5,429.7 | 4,092.4 |

**Within every seed, every adjacent capacity step reduces mean latency — 0 of 3 seeds
invert at any step.** (Stated carefully after a correction: pooled per-arm ranges *do*
overlap between adjacent arms, because between-seed variation exceeds adjacent-arm
separation; the strict statement is the within-seed ordering. See the corrected results
record.) Paired differences versus baseline average **−3,769 / −5,709 / −6,715 ms**.

### 6.3 The mechanism: the policy is capacity-invariant

Offload rates are **bit-identical across all four capacities within every seed**
(0.402608 / 0.406349 / 0.414181 by seed), and the no-eligible-target rate is constant
(~0.0024%). The committed
[mechanism exhibit](capacity_pilot_mechanism_report_20260727.md) re-presents this from the
analysis artifacts.

**Measured upgrade (28 July 2026).** The Phase 82 GPU-track audit correctly noted that
aggregate-rate equality does not by itself prove identical action *sequences*. The keyed
comparison has now been run on the admitted artifacts
([evidence](../integration/evidence/vec_pilot_keyed_action_comparison_20260728.json)):
within every fleet seed, the complete per-second per-vehicle-slot action arrays —
including the chosen RSU and V2V targets — are element-wise identical across all four
capacity arms: **0 mismatches in 8,956,800 cells for every one of the nine arm pairs**.
The invariance therefore holds at the keyed action level, not only in aggregate: the knob
changes only the queueing consequences downstream of a literally unchanged decision
stream.

## 7. Interpretation — labelled by confidence

**Established by the measurements:** on this collapse-hour trace, a 3.3× capacity squeeze
did not reduce deadline attainment; mean latency fell threefold; the policy's choices are
capacity-oblivious.

**Consistent reading, checkable but not yet checked:** deadlines are 100–500 ms while
mean latencies are seconds — both can hold only if the latency distribution is heavily
right-skewed: a bulk of fast tasks (which decide the ~79% deadline figure) plus a tail of
queue blowups (which dominate the mean). A tighter concurrency bound plausibly truncates
the tail without touching the bulk — squeezing shrinks the pathological pileups, so the
mean collapses while deadline attainment stands still. The per-task logs exist; drawing
the latency distribution per arm is the natural next figure and would settle this
reading. Until then it is interpretation, clearly so.

**Mechanism located (28 July 2026): an observation-space gap, not learned indifference.**
Challenged with "could this be a quirk?", the published state arrays answered
([evidence](../integration/evidence/vec_pilot_observability_gap_20260728.json)): the
capacity knob changes RSU-side state pervasively (~41% of RSU-second cells differ across
arms) while **every published vehicle-side quantity the policy's observation draws on is
bit-identical across arms** — own queue state, tasks in flight, positions (trace-fixed),
and therefore channel quality. The documented observation contains no RSU-load input. A
deterministic policy whose observed world is identical must act identically: the
invariance is **structural blindness by observation design**, fully explaining the
bit-identical action sequences. This yields a falsifiable prediction — the baseline
actor shares the observation design, so it should be equally capacity-invariant, which
the predeclared crossover study can test — and it makes the capacity-aware retraining
direction (B-CAP) a surgical fix rather than a fishing expedition. One code-level
confirmation remains open: verifying from the evaluator's observation-builder source
that no capacity-dependent term enters the vector.

**Why this matters beyond the number:** the result is a worked example of the
explainability gap the Year-1 report points at — an aggregate-reward-trained policy whose
behaviour under a changed resource regime is invisible until an instrument makes the
decision stream itself inspectable. The finding was reachable *because* admission
preserves per-decision evidence, not just averages.

## 8. What followed from it (programme consequences)

- The confirmatory protocol's knee rule — largest adjacent-step *drop* in deadline
  success — selected **nothing** (every step rises). Its predeclared fallback fork was
  taken by recorded owner delegation: **candidate (b)** declares `task.latency.mean_ms`
  the confirmatory primary for the held-out campaign, legitimately, because the
  declaration precedes any held-out data.
- STA-05 power arithmetic sealed the choice: detecting the deadline-rate differences
  would need **17–42 seeds** against the 5 held out (power ≈0.16–0.34 at n=5), while the
  latency effect needs **3 seeds at every level** (power ≈0.995 at n=5).
- Held-out seeds {10–14} were untouched by the pilot and are consumed only by the signed
  confirmatory campaign; pilot numbers are never pooled into any confirmatory estimate.

## 9. Limitations (binding, unchanged)

One actor, one fleet preset, one reviewed trace — a deliberately anomalous collapse hour
in one event district; three pilot seeds; uncorrected shared-baseline multiplicity;
per-padded-vehicle capacity semantics; deadline success ≠ physical completion;
`owner_approved_candidate` throughout — not supervisor-approved, not validated, not
causal, not generalisable beyond the studied grid.

## 10. Reproduction pointers

| Artifact | Where |
|---|---|
| Pilot design + launcher (fingerprint-bound) | `scripts/capacity_pilot_campaign.py` |
| Predeclaration + approval digest | `docs/evaluation/capacity_squeeze_pilot_predeclaration.md` |
| Concise results record (with the range-overlap correction) | `docs/evaluation/capacity_pilot_results_20260727.md` |
| Full analysis + STA-01 appendices | `data/vec-fresh/capacity-pilot/campaign_analysis.md` (local) |
| Mechanism exhibit | `docs/evaluation/capacity_pilot_mechanism_report_20260727.md` |
| Figures / tables for the dissertation | `docs/dissertation_appendices/figures/`, `…/tables/` |
| Registry of admitted evidence | `.demo/registry-capacity-pilot.sqlite` (local) |
| Trace provenance | producer sidecar at upstream `6e56393`; ADR-062 probe evidence |

# ChatGPT 5.6 Pro Suggestions — 19 August 2026

## TrafficTwin VEC future experiment roadmap

**Status:** planning document only. This file does not authorise a scientific campaign.

**Purpose:** collect the credible future research directions available from the current TrafficTwin VEC setup, with the research question, hypothesis, proposed design, compute estimate, backend suitability, source of the recommendation, and likely value for publication and the MSc dissertation.

> **Completion overlay, 7 September 2026:** the
> [private follow-up archive](vec_followup_2026-09-07/README.md) records the
> completed five-cell incident state-delay pilot, qualified fixed-overhead
> forwarding sensitivity, two-cell morning pilot and twelve-cell three-arm
> morning replication. The replication used new fleet seeds 0, 2, 3 and 4,
> excluding inspected pilot seed 1 from primary inference. It took 41.43 minutes
> including probes, validation and analysis, excluding preparation and figures.
> The incident-derived hours-per-cell forecasts below must not be applied to
> that completed morning campaign. These are bounded implementations of selected
> directions, not completion of every larger design proposed below. Current
> findings and limits are in the [integrated dissertation section](../dissertation/vec_results_integration_2026-09-07.md).

## 1. Current scientific position

E0, E1, E2, E2b, E2c, and E2d are complete. The frozen result already supports a publishable construct-validity and systems-evaluation paper:

- common-target-per-substep least-busy placement was approximately **2.12 percentage points below** strongest-link ingress execution under the same admission rule;
- per-task sequential shortest-workload placement was approximately **0.527 percentage points above** ingress;
- the direct per-task-versus-common-target contrast was approximately **+2.649 percentage points**.

The main contribution is not that least-busy scheduling is universally better. It is that two operational implementations carrying the same broad scheduler label produced opposite deadline-performance conclusions under matched controls, rejection-aware accounting, and task/service-work conservation.

No additional experiment is required to make the current result meaningful. New work should strengthen replication, identify operating boundaries, improve generalisation, or explain the mechanism. It should not dilute the existing paper into a large undirected benchmark.

## 2. Compute assumptions

Planning estimates use the measured E2d average:

- **one full cell: approximately 1.73 evaluator-hours on the Mac**;
- **one full cell: approximately 213 MB raw output**;
- serial execution unless a different backend/concurrency configuration passes an exact qualification replay.

These are planning estimates, not guarantees. New mechanisms can change runtime.

### Backend rules

#### Mac

- Current validated reference backend.
- Best for exact replays, engineering probes, and small campaigns.
- Slow for large grids.

#### CSF

- Preferred for independent seed-by-arm campaign cells.
- Use a Slurm job array so different cells can run concurrently.
- Before scientific use, replay at least one frozen Mac cell on CSF and compare actions, placements, admission, rejection, task outcomes, conservation identities, and numerical outputs under a predeclared agreement contract.
- Do not mix Mac and CSF cells inside one primary paired comparison unless backend equivalence has been demonstrated.
- CSF active-runtime estimates below exclude queue waiting and assume approximately the same per-cell speed as the Mac.

#### Google Colab

- Suitable for analysis, figure generation, source development, counterfactual transformations, unit tests, and bounded smokes.
- Not the preferred backend for long confirmatory campaigns because runtime continuity, assigned hardware, and environment availability can vary.
- A Colab full campaign is acceptable only after backend qualification, immutable commands, persistent output/checkpoint handling, and exact post-run validation.

## 3. Priority summary

| Rank | Direction | New full cells | Mac estimate | Recommended by | Publication value | Dissertation value |
|---:|---|---:|---:|---|---|---|
| 1 | Write E0–E2d paper and mechanism analysis | 0 | 0 h | Sandra; literature audit | Very high | Essential |
| 2 | Existing-array forwarding-cost sensitivity | 0 | engineering checks only | Literature/repository audit | Very high per compute hour | Very high |
| 3 | RSU state-staleness robustness | 12–20 | 20.8–34.6 h | Sandra | Very high if a boundary appears | Very high |
| 4 | Six-draw confirmatory replication + forwarding robustness | 18 | 33–35 h total | Literature/repository audit | Highest strengthening package | High |
| 5 | Cross-traffic-condition generalisation | 8–12 | 13.8–20.8 h | Sandra; literature audit | High | Very high |
| 6 | Candidate ordering × dispatch granularity | 8–16 | 13.8–27.7 h | Inference from adjacent MSc work | High, but overlap must be managed | Medium-high |
| 7 | Staleness × forwarding-cost envelope | 12–16 | 20.8–27.7 h | Synthesis of Sandra + literature audit | Potentially very high | High |
| 8 | Per-task MAPPO mode selection | 8–12 plus possible retraining | ≥13.8–20.8 h evaluation | Randy | High-risk/high-upside | Medium |
| 9 | Action masking | 8 | 13.8 h | Sandra | Medium | Medium |
| 10 | Workload-estimation error | 12–20 | 20.8–34.6 h | Sandra-adjacent information question | Medium-high | High |
| 11 | V2V helper selection | 12 | 20.8 h | Sandra | Medium | Low-medium |
| 12 | P2C comparison | 16 | 27.7 h | Existing evaluator capability | Low-medium | Low-medium |
| 13 | Placement × reactive scaling | 24 | 41.5 h | Layered architecture discussion | Medium, with overlap risk | Low-medium |
| 14 | Queue capacity × service × demand | 16–72 | 27.7–124.6 h | Sandra’s factor-separation guidance | Low-medium | Medium |
| 15 | Independent external traffic dataset | 12 after integration | 20.8 h simulation plus major data work | Sandra | Very high | Medium due schedule risk |
| 16 | Physical/topology-aware inter-RSU forwarding | 12–20 after development | 20.8–34.6 h plus major engineering | Sandra’s architecture questions | High as future paper | Low for current MSc |

## 4. Experiments in detail

## 4.1 Write the current E0–E2d paper and dissertation chapter

### Research task

No new scientific hypothesis. Convert the frozen programme into a complete paper and dissertation narrative.

### Required outputs

- layered architecture: MAPPO mode choice, communication target, infrastructure placement/admission, forwarding, and future scaling;
- explicit common-target versus per-task operational definitions;
- a worked three-RSU/multiple-task example;
- paired deadline-attainment results;
- offered/admitted/rejected lifecycle tables;
- task and service-work conservation evidence;
- RSU execution-share and workload figures;
- rejection causes, forwarding, queue/backlog, latency, and target-switch evidence;
- limitations, threats to validity, and explicit nonclaims.

### Compute

- New full cells: **0**.
- Mac simulation: **0 hours**.
- CSF: not needed.
- Colab: useful for analysis and figures.

### Source of recommendation

- Sandra explicitly endorsed the scheduler-semantics reversal as the stronger and more publishable framing.
- The literature audit independently ranked the existing E0–E2d story as submission-worthy.

### Value

- Publication: **5/5**.
- Dissertation: **5/5**.

This work must begin immediately and must not wait for another campaign.

---

## 4.2 Existing-array forwarding-cost sensitivity

### Research question

How does controlled inter-RSU forwarding overhead change the per-task placement advantage?

### Hypothesis

The paired `per_task_dla − ingress_dla` advantage will decrease as forwarding overhead increases. It may cross zero within the tested simulator-relative range.

### Setup

Use the immutable E2d task-level arrays and calculate:

```text
latency_d = latency_0 + d × task_forwarded
```

at:

```text
0, 1, 2.5, 5, and 10 ms
```

Recompute deadline status using the original task deadline.

### Hard validity gates

1. Reconstruct every frozen zero-delay aggregate exactly.
2. Prove from source that scalar forwarding delay does not feed back into target selection, admission, queue state, actor observations, actions, or service reservation.
3. Run a bounded matched zero/nonzero evaluator smoke.
4. Require exact agreement between actual nonzero output and transformed zero-delay output.
5. Stop if the equivalence is approximate rather than exact.

### Compute

- New full cells: **0**.
- Engineering work: approximately **2–6 hours**, mostly coding, checks, and short prefixes.
- Mac: suitable.
- CSF: unnecessary, though usable for the smoke.
- Colab: suitable for transformation and analysis.

### Possible results

- Positive through 10 ms: bounded robustness.
- Crossing near an intermediate point: useful break-even envelope.
- Immediate loss of advantage: zero-cost forwarding was a load-bearing assumption.
- Different draw-level crossing ranges: fleet sensitivity.

### Source of recommendation

- Live literature/repository audit, 17 August 2026.

### Value

- Publication: **4.5/5 per compute hour**.
- Dissertation: **4/5**.

---

## 4.3 Six-draw confirmatory replication plus forwarding robustness

### Research question

Does the dispatch-granularity direction reversal reproduce in six new predeclared fleet draws, and does the per-task advantage survive controlled forwarding overhead?

### Hypotheses

1. At zero forwarding, held-out/predeclared `per_task_dla − ingress_dla` remains positive.
2. At zero forwarding, common-target `dla − ingress_dla` remains negative.
3. The forwarding-cost curve is non-increasing for the per-task arm.

### Setup

Fleet seeds:

```text
5, 6, 7, 8, 9, 10
```

Arms per seed:

```text
ingress_dla
common-target dla
per_task_dla
```

All full simulations run at zero forwarding. The forwarding curve is derived afterward from the task arrays, subject to equivalence proof.

Existing seeds 1–4 remain labelled discovery evidence. New seeds 5–10 form the confirmatory population. A pooled estimate is secondary only.

### Compute

- Full cells: **18**.
- Full-cell Mac time: **31.14 hours**.
- Total Mac budget with replay/smoke/analysis/reporting: **approximately 33–35 hours**.
- Raw storage: **approximately 3.84 GB**; maintain at least **6 GB free**.
- CSF active runtime with 4 concurrent tasks: approximately **8.65 hours** plus queue.
- CSF active runtime with 8 concurrent tasks: approximately **5.19 hours** plus queue.
- Colab: not preferred as the primary confirmatory backend.

### Possible results

- Both original signs reproduce: strongest validation of the scheduler-semantics story.
- Per-task stays positive but common-target does not remain negative: partial scenario/fleet dependence.
- Zero-delay reversal fails: important limitation and reason to narrow the paper.
- Forwarding cost removes the advantage: clear coordination-cost boundary.

### Source of recommendation

- Top-ranked path in the literature/repository audit.

### Value

- Publication: **5/5**.
- Dissertation: **4/5**.

---

## 4.4 RSU state-staleness robustness

### Research question

How old can RSU workload information become before per-task sequential least-busy placement stops improving offered-task deadline attainment?

### Hypothesis

```text
fresh state > moderately stale state > strongly stale state
```

The per-task advantage will shrink as the state becomes older and may cross zero.

### Scientific definition required before implementation

Specify exactly:

- whether `rsu_busy_ms`, `rsu_load`, or both are stale;
- whether only placement uses stale state or admission also uses it;
- whether all RSUs share one delayed central snapshot;
- the snapshot/reporting cadence;
- how 100 ms and 500 ms relate to task-substep timing;
- whether state is delayed, sampled-and-held, or corrupted by estimation error.

Do not use delay labels without a precise state-update contract.

### Pilot design

Four matched fleet draws with three stale treatments:

```text
100 ms
500 ms
1 second
```

Reuse frozen fresh/ingress controls only after exact replay/compatibility proof.

- New cells: **12**.
- Mac: **20.76 hours**.
- CSF, 4-way: **5.19 active hours** plus queue.
- CSF, 8-way: **3.46 active hours** plus queue.

### Clean self-contained design

Per draw:

```text
ingress
fresh per-task
100 ms stale
500 ms stale
1 second stale
```

Four draws:

- New cells: **20**.
- Mac: **34.60 hours**.
- CSF, 4-way: **8.65 active hours** plus queue.
- CSF, 8-way: **5.19 active hours** plus queue.

### Possible results

- Robust to modest delay: practical resilience.
- Benefit gradually disappears: information-freshness envelope.
- Becomes negative: stale least-busy routing can be worse than ingress.
- Remains positive at one second: strong bounded robustness.

### Source of recommendation

- Sandra directly proposed testing 100 ms, 500 ms, and 1-second state delay.
- Primary correspondence: [Sandra's 18 August 2026 reply, PDF page 4](../correspondence/sandra_randy_vec_progress_email_thread_2026-08-18.md#pdf-page-4), transcribed from the owner-supplied Outlook PDF. The complete thread also includes her 17 August architecture discussion and Randy's 18 August implementation confirmations.

### Value

- Publication: **5/5 if a clear boundary or reversal appears**.
- Dissertation: **5/5**.

---

## 4.5 Cross-traffic-condition generalisation

### Research question

Does the per-task-versus-ingress direction appear outside the frozen Manchester incident hour?

### Hypothesis

Per-task sequential placement retains a positive paired effect under another queue-correct Manchester traffic condition.

### Full design

Four new fleet draws across:

```text
ingress_dla
common-target dla
per_task_dla
```

- New cells: **12**.
- Mac: **20.76 hours**.
- CSF, 4-way: **5.19 active hours** plus queue.
- CSF, 8-way: **3.46 active hours** plus queue.

### Cheap design

Four draws across:

```text
ingress_dla
per_task_dla
```

- New cells: **8**.
- Mac: **13.84 hours**.
- CSF, 4-way: **3.46 active hours** plus queue.
- CSF, 8-way: **1.73 active hours** plus queue.

### Interpretation boundary

The currently available queue-correct working-day/weekend traces use a standardised nine-RSU footprint rather than the frozen ten-RSU incident topology. This is internal scenario robustness, not external geographic validation and not a clean causal incident-versus-ordinary comparison.

### Possible results

- Same sign pattern: stronger scenario robustness.
- Per-task positive, common-target not negative: partial generalisation.
- No effect or reversed effect: useful regime dependence.

### Source of recommendation

- Sandra explicitly encouraged another use case or dataset.
- Literature audit ranked it as an optional extension.

### Value

- Publication: **4/5**.
- Dissertation: **5/5**.

---

## 4.6 Candidate ordering × dispatch granularity

### Motivation

The adjacent MSc admission-ordering study found that replacing arbitrary vehicle-index scan order with effective-due-date ordering improved offered-task completion by approximately 3.5 percentage points. The E2d per-task placement scan also uses a fixed candidate order. Candidate ordering may therefore be another hidden operational construct.

### Research question

Does the per-task least-busy result depend on the order in which simultaneous V2I candidates are processed?

### Hypotheses

1. Effective-due-date order improves deadline attainment over vehicle-index order.
2. Candidate order and dispatch granularity interact.
3. Per-task placement may gain more from urgency ordering because it updates the execution state after each accepted candidate.

### Focused design

Within `per_task_dla`:

```text
vehicle-index order
effective-due-date order
```

Four draws:

- New cells: **8**.
- Mac: **13.84 hours**.
- CSF, 4-way: **3.46 active hours** plus queue.
- CSF, 8-way: **1.73 active hours** plus queue.

### Stronger 2×2 design

```text
Dispatch: common-target / per-task
Order: vehicle-index / effective-due-date
```

Four draws:

- New cells: **16**.
- Mac: **27.68 hours**.
- CSF, 4-way: **6.92 active hours** plus queue.
- CSF, 8-way: **3.46 active hours** plus queue.

### Collaboration/overlap boundary

This direction overlaps with the adjacent student’s admission-ordering contribution. Do not duplicate it without discussion. Coordinate with Sandra and the student, use a clear division of mechanisms, or treat the interaction as a joint analysis.

### Source of recommendation

- Inference from the adjacent MSc progress report and the E2d candidate-order contract.

### Value

- Publication: **4/5 if coordinated and interaction-focused**.
- Dissertation: **3.5/5**.

---

## 4.7 Staleness × forwarding-cost coordination envelope

### Research question

Under what combination of state freshness and forwarding overhead does per-task RSU placement remain beneficial?

### Hypothesis

Per-task placement requires both sufficiently fresh state and sufficiently low forwarding overhead.

### Setup

Run full cells at:

```text
fresh state
moderately stale state
strongly stale state
```

Then derive the forwarding-cost curve from each state condition’s task arrays, only if source equivalence remains valid.

Four draws × three state conditions:

- New cells: **12**.
- Mac: **20.76 hours**.
- CSF, 4-way: **5.19 active hours** plus queue.
- CSF, 8-way: **3.46 active hours** plus queue.

Add four ingress cells for a self-contained package:

- Total cells: **16**.
- Mac: **27.68 hours**.
- CSF, 8-way: **3.46 active hours** plus queue.

### Possible headline

> Per-task RSU load management helps only inside a coordination envelope defined by dispatch granularity, state freshness, and forwarding overhead.

### Source of recommendation

- Synthesis of Sandra’s Questions 10–11 and the literature audit’s forwarding recommendation.

### Value

- Publication: **5/5 if the simple staleness study first validates cleanly**.
- Dissertation: **4/5**.

---

## 4.8 Per-task MAPPO mode selection

### Research question

Does one mode decision per task arrival improve performance compared with one Local/V2V/V2I decision per vehicle-second?

### Hypothesis

Heterogeneous bursts benefit from separate task-level decisions because safety-critical and less-urgent tasks need not share one mode.

### Exploratory frozen-actor setup

Four draws ×:

```text
one action per vehicle-second
one action per task arrival
```

- New cells: **8**.
- Baseline Mac estimate: **13.84 hours**.
- Safer planning range: **approximately 14–25 hours**, because actor inference is called more often.
- CSF: suitable after qualification.
- Colab: useful for development and small benchmark runs.

### Main scientific risk

The actor was trained under the one-action-per-vehicle-second contract. Calling it per task is a new inference contract. A strong confirmatory claim may require retraining with task-level actions, multiple training seeds, and new validation. That compute cannot be estimated responsibly without a pilot training benchmark.

### Source of recommendation

- Randy explicitly identified per-task-type/action decisions as future work.

### Value

- Publication: **4/5 if retrained and validated; lower as a frozen-actor ablation**.
- Dissertation: **2/5 because it can become a second thesis**.

---

## 4.9 Action masking

### Research question

Does masking infeasible Local/V2I/V2V actions reduce unavailable attempts and improve offered-task outcomes?

### Hypothesis

Masking infeasible V2I/V2V actions reduces avoidable failures and may improve deadline attainment and energy use.

### Setup

Four draws ×:

```text
unmasked frozen actor
masked frozen actor
```

- New cells: **8**.
- Mac: **13.84 hours**.
- CSF: suitable.
- Colab: possible for development/pilot.

### Source of recommendation

- Sandra described action masking and infrastructure scheduling as complementary layers.

### Value

- Publication: **3/5**.
- Dissertation: **3/5**.

Audit existing B-mask evidence first to avoid duplicating completed work.

---

## 4.10 Workload-estimation error

### Research question

How much estimation error can per-task shortest-workload placement tolerate?

### Hypothesis

Small estimation errors preserve the benefit; sufficiently biased estimates reduce or reverse it.

### Three-level design

```text
correct workload estimate
moderate under-estimate
moderate over-estimate
```

Four draws:

- New cells: **12**.
- Mac: **20.76 hours**.
- CSF, 8-way: **3.46 active hours** plus queue.

### Five-level curve

- New cells: **20**.
- Mac: **34.60 hours**.
- CSF, 8-way: **5.19 active hours** plus queue.

### Source of recommendation

- Inference from Sandra’s information-quality question and the adjacent student’s service-time miscalibration analysis.

### Value

- Publication: **4/5**.
- Dissertation: **4/5**.

This is simpler than true temporal staleness but answers a slightly different question.

---

## 4.11 V2V helper-selection study

### Research question

Is the strongest-radio-link eligible peer also the best compute helper?

### Candidate policies

```text
strongest-link eligible peer
lowest-workload eligible peer
estimated end-to-end-latency peer
mobility/contact-duration-aware peer
```

### Clean-design requirement

V2V helper identity/tier enters the actor observation. A helper intervention can therefore alter MAPPO’s Local/V2I/V2V decision. Freeze/replay the action stream or redesign the observation path before claiming an isolated helper-selection effect.

Four draws × three helper policies:

- New cells: **12**.
- Mac: **20.76 hours**.
- CSF: suitable.
- Colab: suitable for development/pilots.

### Source of recommendation

- Sandra raised V2V target selection as a future research opportunity.

### Value

- Publication: **3/5**.
- Dissertation: **2/5**.

The literature is crowded and the intervention has actor-observation confounding.

---

## 4.12 P2C versus exact least-busy placement

### Research question

Can power-of-two choices reduce concentration with less global state than exact least-busy placement?

### Hypothesis

P2C may approach per-task least-busy performance while requiring less complete RSU state.

### Setup

Four draws ×:

```text
ingress
common-target
per-task
P2C
```

- New cells: **16**.
- Mac: **27.68 hours**.
- CSF: suitable.
- Colab: possible but not preferred for the full grid.

### Source of recommendation

- Existing evaluator capability, not the currently preferred supervisor/literature direction.

### Value

- Publication: **2.5/5**.
- Dissertation: **2/5**.

Risk: ordinary algorithm benchmark with a weaker paper story.

---

## 4.13 Placement × reactive scaling

### Research question

Do per-task placement and service scaling complement each other or substitute for each other?

### Hypothesis

Scaling may reduce the need for placement, amplify it, or shift the bottleneck to another layer.

### Setup

```text
Placement: ingress / per-task
Scaling: off / static / reactive
Four draws
```

- New cells: **24**.
- Mac: **41.52 hours**.
- CSF, 8-way: **5.19 active hours** plus queue.
- Colab: not recommended for the full design.

### Source of recommendation

- The layered architecture discussion.

### Overlap risk

The adjacent MSc student is already studying an ordering × worker-scaling interaction. Coordinate before entering this area.

### Value

- Publication: **2.5–3/5**.
- Dissertation: **2/5**.

Do not describe the service multiplier as a real Kubernetes deployment.

---

## 4.14 Queue capacity × compute service × demand

### Research question

Is the benefit of placement/admission governed by the capacity-to-demand operating point rather than queue size alone?

### Hypothesis

Scheduler/admission gains depend on available compute service relative to offered demand; increasing waiting-room capacity alone does not reproduce service scaling.

### Compute ranges

- Focused one-factor package: **16 cells / 27.68 Mac hours**.
- Moderate factorial: **32 cells / 55.36 Mac hours**.
- Large factorial: **72 cells / 124.56 Mac hours**.

- CSF: technically suitable.
- Colab: unsuitable for a large confirmatory factorial.

### Source of recommendation

- Sandra’s guidance to keep admission capacity, compute capacity, placement, forwarding, and scaling separate.

### Overlap risk

The adjacent MSc project has already analysed service rate, offered load, hard admission ceilings, local fallback, and energy boundaries. A new study needs a clearly different estimand.

### Value

- Publication: **2/5**.
- Dissertation: **3/5**.

---

## 4.15 Independent external traffic dataset

### Research question

Does the dispatch-semantics reversal occur outside the Manchester data and topology?

### Hypothesis

The common-target/per-task distinction remains material under an independently sourced mobility setting.

### Simulation package after integration

Four draws × three arms:

- New cells: **12**.
- Mac simulation: **20.76 hours**.
- CSF: suitable.
- Colab: useful for data engineering.

### Main cost

The high cost is not simulator time. It is:

- finding suitable FCD/mobility data;
- confirming licence/access;
- placing RSUs;
- validating timestamps and vehicle identities;
- regenerating the trace;
- checking queue/reset semantics;
- proving evaluator compatibility.

### Source of recommendation

- Sandra’s request for another use case or traffic dataset.

### Value

- Publication: **5/5**.
- Dissertation: **3/5 due schedule risk**.

---

## 4.16 Physical/topology-aware inter-RSU forwarding

### Research question

Do topology, bandwidth contention, routing, and control-message cost change whether remote RSU execution remains beneficial?

### Hypothesis

A detailed forwarding network will narrow or reshape the regime in which per-task remote execution helps.

### Estimated simulation after implementation

- Approximately **12–20 cells**.
- Mac: **20.76–34.60 hours**.
- CSF: suitable.
- Colab: development only.

### Main cost

Large software-engineering and validation burden:

- inter-RSU topology;
- link capacities and contention;
- routing;
- packet/result-transfer semantics;
- state/control traffic;
- conservation and lifecycle changes.

### Source of recommendation

- Sandra’s forwarding architecture questions.

### Value

- Publication: **4/5 as a future paper**.
- Dissertation: **1/5 for the current timeline**.

## 5. Recommended practical paths

### Minimum-compute publication path

1. Write the E0–E2d paper now.
2. Add the worked example and mechanism figures.
3. Perform existing-array forwarding sensitivity after exact equivalence gates.
4. Submit without another full campaign if time is tight.

### Best dissertation path

1. Write E0–E2d immediately.
2. Add mechanism analysis.
3. Run either:
   - compact cross-traffic generalisation: **8–12 cells / 13.84–20.76 Mac hours**, or
   - state-staleness pilot: **12 cells / 20.76 Mac hours**.
4. Do not run both unless CSF qualification and the writing schedule make it safe.

### Strongest paper-strengthening path

1. Existing-array forwarding analysis.
2. Six new predeclared fleet draws × three zero-delay arms.
3. Report discovery and confirmatory cohorts separately.
4. Add staleness only as a later study.

Expected compute:

- **18 full cells**;
- **33–35 Mac hours total**;
- approximately **5–9 CSF active hours** with 4–8 concurrent tasks, excluding queue.

### Most original follow-on paper

A coordination-envelope study:

```text
dispatch granularity
× state freshness
× forwarding overhead
```

Potential thesis:

> Infrastructure-side RSU load management helps only within a coordination envelope defined by how tasks are dispatched, how fresh the scheduler’s state is, and how costly remote execution is.

## 6. Final ranking

1. Write the current paper and mechanism analysis.
2. Existing-array forwarding sensitivity.
3. State-staleness pilot.
4. Six-draw confirmatory replication plus forwarding robustness.
5. Cross-traffic-condition generalisation.
6. Candidate-ordering interaction, only with coordination/collaboration.
7. Staleness × forwarding envelope.
8. Per-task MAPPO mode decisions.
9. Action masking.
10. Workload-estimation error.
11. V2V helper selection.
12. P2C comparison.
13. Placement × scaling.
14. Large capacity/service/demand factorials.
15. Independent external dataset when time permits.
16. Physical forwarding as a future-paper project.

## 7. Authority boundary

This roadmap does not launch or authorise any scientific run.

Before a new full campaign:

1. define one clear research question;
2. freeze the arms, seeds/draws, primary estimand, outcome, statistical unit, stop rules, backend, runtime, and storage;
3. qualify CSF or Colab against a frozen Mac reference if used;
4. pass replay, smoke, accounting, conservation, determinism, and raw/summary equality gates;
5. retain every successful output regardless of its result;
6. keep E0–E2d immutable;
7. do not mix several mechanisms unless the interaction is the declared research question.

The current work is already publishable. Additional compute should buy a clearer boundary, stronger replication, or real generalisation—not merely more cells.

# TrafficTwin complete experiment history

**Coverage:** project research and research-adjacent experiments completed through 6 August 2026

**Evidence ceiling:** `owner_approved_candidate`; descriptive and non-causal unless a narrower
internal label is stated

**External standing:** no result is supervisor-approved, externally validated, causal, or a
production-deployment verdict

## Abstract

TrafficTwin's experimental programme progressed from a predeclared local capacity intervention,
through mechanism and breadth studies, to GPU retraining diagnostics, real live-bus observation,
hybrid bus-mobility simulation, and Manchester network/demand investigations. The central signed
result is narrow: under one audited evaluator, actor, fleet preset and incident trace, reducing a
configured per-RSU admission/in-flight concurrency ceiling from the cap-2.5 arm to cap-0.75 reduced
mean modelled latency by 8,310.9 ms on five held-out paired seeds, while modelled deadline
attainment and keyed actor decisions remained effectively unchanged. This was not faster
computation. Median modelled latency stayed near 44.3 ms; the change was concentrated in the
already-deadline-failed tail, and the evaluator does not record a complete offered-to-returned task
lifecycle.

The wider programme found that the audited 17-dimensional actors could not observe the capacity
control, that normal-density traces were almost entirely insensitive to it, that the offload
partition aligned strongly with vehicle compute tier, and that per-RSU modelled load was highly
asymmetric. A later actor comparison found no winner crossover but refuted the prediction that the
latency slope was actor-independent. A predeclared exact-equality density-onset law was also
refuted. Colab experiments showed that retrained 19-dimensional policies supplied with configured
capacity and selected-RSU headroom can change their decisions with capacity, but those private
synthetic diagnostics did not establish better physical completion or admit new actors.

Four attended BODS sessions supplied real bus-mobility measurements. Bus feed cadence was stable
across a 36-fold active-fleet range, and buses progressed more slowly at peak than at night, but
the association was observational and not causal. The B-BUS successor experiments combined that
captured mobility with synthetic tasks, compute equipment, radio/queue assumptions and generated
analysis sites. They are therefore real-data-informed simulations, not observations of real VEC
task completion.

This record consolidates the authoritative
[experiment register](../experiments_and_findings_20260728.md), the
[detailed catalogue](experiment_catalogue_20260730.md), the signed capacity records, the Colab and
B-BUS records, and the 6 August
[semantic audit](../current_status_5_6_pro_analysis.md). Where an older record uses stronger queue
or completion language, the 6 August correction governs the interpretation here.

---

## 1. Scope, terminology and evidence rules

### 1.1 What is included

This history includes:

- all 17 entries in the completed capacity programme, including new campaigns, timing probes and
  analysis-only mechanism studies;
- every completed Colab/GPU campaign and engineering smoke recorded in the experiment catalogue;
- all attended live-bus observation sessions and their derived analyses;
- the dawn-to-peak B-BUS trace preparation, corridor experiment and Sparse-64 executions;
- the Manchester demand, reachability, source-identity and regeneration investigations; and
- negative results, fail-closed refusals, execution deviations and withdrawn interpretations.

Software unit tests, packaging tests and synthetic demo generation are not treated as research
experiments. Proposed but unexecuted benchmark, participant, calibration, bus-prediction and
learned-scheduler studies are identified as absent rather than presented as results.

### 1.2 The capacity intervention

The capacity control was not CPU power, computation speed, bandwidth, RSU count or a measured
hardware capacity. The CLI scaling value was multiplied by the padded trace width to form a
**per-RSU admission/in-flight concurrency ceiling**:

```text
per-RSU ceiling = round(control × padded trace width)
```

For the `inc` trace, padded width 2,488 produced ceilings of 6,220 tasks at cap-2.5 and
1,866 tasks at cap-0.75. “Queue capacity” is only shorthand: the evaluator does not cleanly
separate offered, admitted, rejected, waiting, executing, completed and returned states, worker
count, service rate or queue length. The saved `rsu_load` value is post-drain, so a stored value
below the ceiling does not prove that the admission clamp was unbound before drain.

### 1.3 Completion and latency language

The principal endpoint called completion in older experiment records is `task_met`: **modelled
deadline attainment**, not eventual physical task completion. Modelled latency is an evaluator
output. The system lacks a complete task-lifecycle ledger connecting offered work to admitted,
rejected, queued, started, executed, finished and returned outcomes. Consequently:

- the latency reduction is not evidence of faster computation;
- “fail fast” or “queue truncation caused the effect” is not established as a complete causal
  mechanism;
- throughput and physical completion cannot be reconstructed safely from the current outputs;
  and
- lower mean modelled latency must be reported beside deadline attainment, percentiles, tail mass,
  action identity and lifecycle limitations.

### 1.4 Standing labels used below

| Label | Meaning in this project |
|---|---|
| `owner_approved_candidate` | Owner-attested candidate ceiling; not an authenticated signature, supervisor approval or external validation. |
| Exploratory admitted | Executed through the reviewed local campaign/admission chain, but not confirmatory. |
| Internally confirmatory | One contrast fixed before reserved outcomes and executed on held-out seeds; still only an internal project standing. |
| Non-admitted diagnostic | Useful for engineering or hypothesis generation, but outside the scientific admission chain. |
| `admitted_with_execution_deviation` | Owner-admitted descriptive use with a permanently visible execution deviation; not clean protocol-confirmed evidence. |
| Withdrawn | The stated inference is no longer supported; retained for audit history. |

---

## 2. Capacity programme: common apparatus

The local capacity programme used Randy Putra's audited VEC evaluator and exact reviewed source
identities through TrafficTwin's approval-bound campaign and fresh-run admission services. The
primary actor was `ukfleettrain_mappo_model_c_17`; the principal fleet preset was `uk2030`; the
evaluator seed was held at 0 while fleet seeds supplied paired replicates. Five reviewed traces
covered weekend (`we`, padded width 139), weekday PM (`wd_pm`, 163), event night (`ev`, 175),
weekday AM (`wd_am`, 215), and an incident/VSL-collapse hour (`inc`, 2,488). The `inc` trace is one
modelled hour in the Etihad/Co-op Live district, not Manchester in general.

Across the complete capacity campaign family, 154 fresh-run cells were completed and admitted.
Analyses that reused those cells are separated below from experiments that executed new cells.

## 3. Capacity experiment 1 — predeclared squeeze pilot

**Question.** Would reducing the per-RSU admission/in-flight ceiling create a degradation cliff in
modelled deadline attainment?

**Design.** Four arms, cap-2.5/1.5/1.0/0.75, crossed with common fleet seeds 0–2 on the full
3,600-step `inc` trace: 12 cells. The primary endpoint was modelled deadline-attainment rate.
The design was frozen before execution and the null was explicitly publishable.

**Execution.** All 12 cells completed and were admitted, with no failures or skips. Total cell
compute was 12.47 hours and the admitted outputs occupied approximately 1.17 GB.

**Results.** Mean deadline attainment was 0.790412, 0.790522, 0.790591 and 0.790737 as the ceiling
fell. The predicted degradation cliff did not occur. Mean modelled latency fell monotonically
from 9,798.8 to 6,029.6, 4,089.9 and 3,083.6 ms. The per-seed ordering was uniform even though
pooled adjacent-arm ranges overlapped. Offload rates were identical within seed.

**Standing and interpretation.** Exploratory admitted evidence. The experiment established an
unexpected evaluator response and motivated a separately signed held-out contrast. It did not
show faster computing or better physical completion. See
[pilot results](capacity_pilot_results_20260727.md).

## 4. Capacity experiment 2 — signed held-out confirmation

**Question.** Would the pilot's mean-latency contrast reproduce on untouched seeds when latency
was declared as the primary endpoint before any held-out outcome existed?

**Design.** Cap-2.5 versus cap-0.75 on reserved fleet seeds 10–14: 10 cells. The signed candidate
(b) bytes were digest-bound; held-out use was explicitly authorised. Pilot seeds were not pooled.

**Execution.** All 10 cells completed and were admitted. Two session interruptions occurred. The
first real resume exposed a defect in repeat-admission fingerprinting; fail-closed behaviour
prevented a bad registry write, the defect was fixed and regression-tested, and three completed
cells were later receipt-reused rather than rerun. Total cell compute was 10.37 hours.

**Primary result.** Every paired seed moved in the predeclared direction:

- mean paired modelled-latency difference: **−8,310.9 ms**;
- 95% deterministic bootstrap interval: **[−9,097.5, −7,524.3] ms**;
- exact two-sided sign/randomisation floor with five unanimous pairs: **p = 0.0625**; and
- arm means: **12,027.5 ms to 3,716.6 ms**.

**Companion results.** Deadline attainment was 0.770944 versus 0.772073 and moved faintly upward
on every seed. Offload rates were identical between arms within seed.

**Standing and interpretation.** This is the programme's sole internally confirmatory contrast,
at an `owner_approved_candidate` ceiling. It confirms a change in **mean modelled latency**, not
physical execution speed or eventual completion. Seeds 10–14 are spent for capacity work. See
[confirmatory results](capacity_confirmatory_results_20260728.md).

## 5. Capacity experiment 3 — keyed action identity

**Question.** Did equal aggregate offload rates hide different per-vehicle decisions or targets?

**Design.** Read-only element-wise comparison of `veh_action`, `veh_best_rsu` and `veh_best_v2v`
arrays for nine pilot arm pairs, within the same fleet seeds.

**Result.** There were **zero mismatches** over 8,956,800 per-vehicle-slot actions per arm pair,
including the stored RSU and V2V target arrays.

**Standing.** Exploratory analysis of admitted artifacts. It establishes literal action-array
identity under the evaluated deterministic replay; it does not by itself identify why. See
[machine evidence](../integration/evidence/vec_pilot_keyed_action_comparison_20260728.json).

## 6. Capacity experiment 4 — observability-gap probe

**Question.** Was the actor ignoring a visible capacity effect, or was capacity absent from its
observed state?

**Design.** Compare published vehicle-side state and RSU-side state between arms.

**Result.** Vehicle task counts and vehicle queue-state inputs were bit-identical, while RSU-side
load differed in 134,278 of 324,000 compared RSU-time cells, approximately 41%. The documented
17-dimensional observation had no configured-capacity or RSU-load input.

**Interpretation.** Within this evaluator, the deterministic actor received the same observed
world and therefore produced the same decisions. This is structural observation blindness, not
evidence that the actor considered capacity and learned to ignore it. The observation vector was
not itself published, so the conclusion combines admitted state arrays with reviewed source
semantics. See [machine evidence](../integration/evidence/vec_pilot_observability_gap_20260728.json).

## 7. Capacity experiment 5 — baseline-actor invariance prediction

**Question.** Would a second 17-dimensional actor sharing the same observation design also remain
capacity-invariant?

**Design.** `baseline_model_c_17` on `ev`, four standard arms and seeds 50–52: 12 admitted cells,
with a verdict rule frozen before execution.

**Result.** The prediction held: every metric was exactly identical across capacity arms within
each seed. Mean deadline attainment was 0.928651, modelled latency 53.03 ms and offload rate
0.426517. On matched fleets, the trained actor was descriptively higher in attainment (0.934865),
lower in latency (51.21 ms), and offloaded about four percentage points less.

**Standing.** Exploratory admitted evidence; not an actor ranking. See
[baseline-invariance results](baseline_invariance_results_20260728.md).

## 8. Capacity experiment 6 — weekend and event-night grid

**Question.** Was the `inc` response a general capacity effect or a saturated-regime effect?

**Design.** Four standard arms and seeds 50–52 on `we` and `ev`: 24 admitted cells.

**Result.** Every metric was exactly identical across all arms in all seeds on both traces. Mean
deadline attainment/modelled latency were 0.931624/52.0 ms on `we` and 0.934865/51.2 ms on `ev`.
The event night resembled the weekend at the VEC layer; the incident trace was the distinctive
regime.

**Standing.** Exploratory admitted evidence. It brackets outcome sensitivity above the tested
normal regimes but does not locate a physical density threshold. See
[grid results](capacity_grid_results_20260728.md).

## 9. Capacity experiment 7 — five-regime completion

**Question.** Would weekday AM and PM traces change the normal-regime conclusion?

**Design.** Four standard arms and seeds 50–52 on `wd_am` and `wd_pm`: 24 admitted cells after
their trace admission.

**Result.** Both traces were exactly invariant across arms. Across `we`, `wd_pm`, `ev` and
`wd_am`, widths 139–215, the standard capacity grid was inert; the 2,488-width `inc` regime was
the only standard-grid trace with a material latency response.

**Standing.** Exploratory admitted evidence. See
[sweep-completion results](capacity_sweep_completion_results_20260728.md).

## 10. Capacity experiment 8 — deep squeeze on event night

**Question.** At what extreme control level would the low-density `ev` trace first cease to be
exactly invariant?

**Design.** Cap-2.5 baseline plus cap-0.5, cap-0.25 and cap-0.1 on seeds 50–52: 12 admitted
cells.

**Result.** Cap-0.5 and cap-0.25 remained exactly identical to baseline. Cap-0.1 produced a very
small response: deadline attainment increased by about 0.000011 and mean modelled latency fell by
about 0.024 ms, with unchanged decisions. The tested bracket was therefore `(0.1, 0.25]` under the
then-used equality definition.

**Standing.** Exploratory admitted evidence. The magnitude is operationally tiny and should not
be equated with the incident-trace response.

## 11. Capacity experiment 9 — runtime and admission probes

The full `ev` timing probe completed in 265.9 s, producing about 28 MB and leaving 6,934 s under
the 7,200 s request ceiling. The full `inc` probe took 3,555.96 s and about 100 MB. During `inc`
admission, float32 verification-side summation exceeded the existing reconciliation tolerance at
large totals; float64 verification passed all 3,600 steps without changing the tolerance or
scientific data. This was an engineering verification repair, not an experimental effect.

**Standing.** Timing and integrity evidence only. The timing probes did not themselves create a
scientific result. See [the `ev` timing record](../integration/evidence/vec_ev_timing_probe_20260728.json).

## 12. Capacity experiment 10 — latency-tail analysis

**Question.** How could mean modelled latency fall sharply while deadline attainment stayed flat?

**Design.** Analysis of approximately 39.2 million active task observations per arm from the
admitted pilot arrays.

**Results.** The median was approximately 44.3 ms at every arm. The share above one second changed
only from 11.4816% to 11.4138%, while p99 fell from 99,854 to 30,034 ms and p90 from 32,260 to
21,947 ms. Between 97.94% and 99.35% of total modelled-latency mass came from observations above
one second.

**Current interpretation.** The arm contrast compressed the extreme tail among tasks already
missing their deadlines. The analysis does not establish that those observations represent
physically completed tasks or a clean waiting-time queue, because the complete task lifecycle is
not recorded. See [tail analysis](latency_tail_analysis_20260728.md).

## 13. Capacity experiment 11 — per-RSU load asymmetry

**Question.** How was modelled RSU load distributed across the ten generated analysis units?

**Result.** Three RSUs carried exactly zero saved load at every standard arm, a fourth carried
less than 5%, and the busiest carried approximately 24%. Load Gini changed only from 0.486 to
0.467 under the squeeze. The relative load distribution did not rebalance.

**Current interpretation.** The asymmetry is measured, but its geographic or routing cause is
unresolved. Generated RSUs are not observed roadside hardware, saved load is post-drain, and the
analysis does not prove that relocating units or changing association would improve outcomes. See
[RSU-load analysis](rsu_load_asymmetry_20260728.md).

## 14. Capacity experiment 12 — pilot dynamics and the ceiling regularity

**Design.** Analysis-only study of all 12 pilot cells across time, task classes and vehicle slots.

**Results.** The p95 modelled latency of missed tasks divided by the control value was highly
stable: mean **39,959 ms**, sample SD 166 ms, relative spread 0.41% across 36
cell-by-class observations. The implied upper-tail levels were approximately 100, 60, 40 and
30 seconds over the four arms. Only about 3.5–4.1% of occupied slots ever mixed local/offload
behaviour; most were always or never offload, identically across capacity. Failure-rate Gini was
about 0.62, with the worst decile bearing 34–36% of failures despite task-count Gini of 0.028.
The arm-ratio signature appeared after the early fill period and persisted.

**Current interpretation.** `L(c) ≈ 39,959 ms × c` is a strong empirical regularity of the
modelled missed-task tail for this actor/subsystem, not a physical service-time law. Incomplete
lifecycle accounting prevents treating it as a complete queueing mechanism. See
[pilot-dynamics analysis](pilot_dynamics_analysis_20260728.md).

## 15. Capacity experiment 13 — offload partition

**Question.** What measured feature separated always-offload and never-offload vehicles?

**Design.** Five admitted cells spanning four seeds and controls from 2.5 to 0.1; workload and
task mix checked as potential confounds.

**Results.** In every analysed cell, the always-offload group was exactly the tier-0 vehicle
population; the never-offload group contained no tier-0 vehicle. Tier-0 capability was about
13 times lower than tier 2 in the producer configuration. Tasks per slot and 20/30/50 class mix
were effectively matched, while failure differed sharply. In two 25-fold comparisons, the
never-offload population remained at about 39.6 ms with identical attainment; the always-offload
population fell from roughly 25.6–27.4 seconds to 1.06–1.07 seconds.

**Interpretation.** The fleet mean combined two highly different populations; no individual
vehicle necessarily experienced the −8.3 s fleet-average contrast. The empirical ceiling
regularity appeared only in the offloading population. The alignment with tier is descriptive;
whether offloading helped tier-0 vehicles requires a counterfactual actor comparison. See
[offload-partition analysis](offload_partition_analysis_20260729.md).

## 16. Capacity experiment 14 — RSU association analysis and withdrawal

**Measurements that stand.** Four RSUs carried 99.1% of saved load and operated near the
configured concurrency ceiling in analysed cells; the same four dominated across a 25-fold
squeeze and another seed. Source review showed that the environment's best-RSU calculation uses
link-quality argmax and does not include load.

**Withdrawn inference.** The original analysis counted `veh_best_rsu` per vehicle-step as V2I
sends, but that count did not reconcile with the environment's V2I-task total and attributed sends
to an RSU with zero busy time. Therefore the claim that idle RSUs were frequently selected, and
that association rather than placement caused the asymmetry, was withdrawn the same day.

**Standing conclusion.** Load asymmetry is real; the exact cause is unresolved and needs
per-task lifecycle/target attribution. See the
[partially withdrawn record](rsu_association_analysis_20260729.md).

## 17. Capacity experiment 15 — pre-registered ceiling prediction

**Question.** Would the empirical tail regularity predict much deeper `inc` arms on fresh seeds?

**Design.** Cap-0.5/0.25/0.1, seeds 60–62: 12 admitted cells and 18.4 hours. Predicted upper-tail
levels 19,980/9,990/3,996 ms, a ±5% band and HELD/REFUTED/BOUNDED rule were frozen before
outcomes; verdict code was committed while only two cells existed.

**Result.** The predeclared verdict was **HELD**: all 27 arm-by-class-by-seed pairs were inside
the band. Mean observed constants were 40,157, 40,309 and 40,716 ms. Error grew systematically
as the control fell, particularly for T2, reaching +3.42% at cap-0.1. Deadline attainment moved
slightly upward on all seeds; the decision partition remained identical; the p50 prediction was a
partial miss on seed 61.

**Standing.** Pre-registered exploratory evidence, not the signed confirmatory study and not a
universal system law. See [prediction results](ceiling_law_prediction_results_20260729.md).

## 18. Capacity experiment 16 — actor crossover

**Question.** Would the baseline actor overtake the trained actor as the ceiling tightened, and
would both actors share approximately the same modelled-latency slope?

**Design.** The trained actor reused its 12 admitted pilot cells; the baseline actor ran 12
matched `inc` cells over four arms and seeds 0–2. Winner-reversal and a ≤5% relative slope band
were frozen before the baseline outcomes existed.

**Results.** No crossover occurred. The trained actor retained a 6.0835–6.0946 percentage-point
deadline-attainment advantage at every arm. The latency-slope prediction was **refuted**:
3,828.2 versus 6,555.4 ms per control unit, a 52.53% symmetric relative contrast. The baseline
offloaded about 6.23 percentage points more.

**Interpretation.** The slope was not actor-independent in this design. Checkpoint policy and
fleet-preset mismatch cannot be separated, so this is not an algorithm-family comparison. See
[actor-crossover results](actor_crossover_results_20260730.md).

## 19. Capacity experiment 17 — normal-regime onset scaling

**Question.** Would the first exact non-identity arm scale proportionally with padded trace width?

**Design.** `we`, `wd_pm` and `wd_am`, each with cap-2.5/0.5/0.25/0.1 and seeds 60–62: 36
admitted cells. Six exact-equality predictions and a binary verdict were frozen pre-data.

**Result.** The prediction was **refuted**, with four of six checks correct. `we` and `wd_pm`
each differed at cap-0.25 in one seed, but only by 0.243 and 0.024 microseconds of mean modelled
latency. Measured exact-rule onsets were 0.25, 0.25, 0.1 and 0.1 for `we`, `wd_pm`, `ev` and
`wd_am`, not ordered by widths 139, 163, 175 and 215. At cap-0.1 all four normal traces moved in
the same tiny direction: attainment +0.0011–0.0043 percentage points and latency −0.024 to
−0.205 ms, with unchanged decisions.

**Interpretation.** The exact-identity proportional law is refuted. Because the failures are
sub-microsecond and the grid is coarse, the result does not establish that density is irrelevant.
See [onset-scaling results](onset_scaling_prediction_results_20260730.md).

---

## 20. Capacity-programme synthesis

The complete local programme supports the following bounded chain:

1. the configured control changes a per-RSU admission/in-flight ceiling;
2. the audited 17-dimensional actors do not observe that control or RSU load;
3. keyed actions therefore remain unchanged across arms under deterministic replay;
4. normal-density traces are practically or exactly insensitive across the studied grid;
5. on the dense `inc` trace, the extreme modelled-latency tail scales strongly with the control;
6. tasks already missing deadlines dominate the mean, while median latency and deadline
   attainment change little; and
7. incomplete lifecycle accounting prevents converting that evaluator response into a claim of
   faster computation, higher throughput, or improved physical completion.

The programme also found large vehicle-tier and RSU heterogeneity that aggregate means conceal.
The exact cause of geographic RSU idleness remains unresolved. The correct next step is complete
lifecycle/work-conservation instrumentation before causal scheduler claims.

---

## 21. Colab/GPU programme: purpose and common limits

Google Colab supplied a T4 for the first engineering smoke and owner-managed G4 Blackwell-class
GPUs for the later from-scratch MAPPO work that would be slow or impractical locally. The general
GPU programme used producer code under recorded permission and citation, but most campaigns used
the producer's synthetic highway and no producer traces or BODS data. Private archives remained
gitignored and content-addressed. Except for the later narrow Sparse-64 owner decision, these
outputs are non-admitted diagnostics and the returned actors are not actor-admitted.

### 21.1 B-CAP engineering smoke

One short seed compared a 17-dimensional hidden-capacity control with a 19-dimensional treatment
that appended normalized configured capacity and selected-RSU headroom. The control was exactly
invariant and the treatment changed local/V2I decisions with capacity. At this tiny scale the
treatment did not improve synthetic performance (approximately 98.86% versus 99.24% completion).
The smoke proved the information path, not benefit. See
[smoke evidence](../integration/evidence/bcap_engineering_smoke_20260728.json).

### 21.2 B-CAP full training

Ten from-scratch jobs, paired seeds 100–104, compared 17-D hidden-capacity and 19-D
capacity/headroom observations. Each requested five million environment steps with randomized
ceilings 50/30/20/15. The 17-D actors were exactly capacity-invariant; the 19-D actors changed
decisions with capacity. This independently reproduced the observation-blindness mechanism and
showed that a capacity-aware policy can be trained. It did not establish that responsiveness
improves admitted trace outcomes. Private archive prefix: `77204c47…`. See the
[B-CAP predeclaration](bcap_training_predeclaration_20260728.md).

### 21.3 B-REWARD

Ten jobs, paired seeds 200–204, held the 19-D observation fixed and compared balanced QoS/energy
reward (`alpha=0.7`) with pure QoS (`alpha=1.0`). In the sealed synthetic diagnostic, pure QoS
changed completion by approximately +0.017 percentage points, energy by +0.04 J/task, local
execution by about +10 percentage points, produced slightly lower modelled latency, and reduced
capacity-conditioned action switching from 3.51% to 1.94%. This describes the private synthetic
diagnostic, not admitted Manchester performance. Archive prefix: `316092d9…`. See the
[B-REWARD predeclaration](breward_training_predeclaration_20260728.md).

### 21.4 B-MASK

Ten jobs, paired seeds 300–304, compared training with and without the producer's feasibility
mask; every checkpoint was then evaluated with deployment masking on and off at four ceilings.
All jobs completed. Across 80 diagnostic cells and 10,240,000 recorded decisions, masked
deployment selected zero infeasible actions, satisfying the invariant. Wider treatment and
interaction contrasts remain sealed pending review. Archive SHA-256 prefix: `cf18bedf…`. See the
[preservation record](../integration/evidence/bmask_full_campaign_preservation_20260728.json).

### 21.5 B-BUS and IPPO smokes

Synthetic stand-in smokes proved the bus-native training path and a second IPPO algorithm-family
pipeline. They were infrastructure checks only: no real bus verdict, actor admission or
algorithm comparison resulted.

### 21.6 B-DOMAIN

Fifteen jobs, seeds 400–404, trained 19-D actors under default, safety-dominant and
pilot-inspired task-type mixtures, then evaluated the complete train-by-domain matrix at baseline
and squeezed ceilings. All 15 completed, covering 90 diagnostic cells and 11,520,000 decisions.
Descriptive contrasts remain pending independent review. The experiment used a synthetic highway
and procedural task mixtures, not literal trace B4 or Manchester distribution shift. Archive
prefix: `0d17154e…`. See the
[preservation record](../integration/evidence/bdomain_full_campaign_preservation_20260728.json).

### 21.7 B-DENSITY phase 1 and cost probe

The engineering smoke tested densities 128 and 1,024, controls 2.5 and 0.25, seeds 700/701 and
2,000 steps. It proved that the density axis reached a real GPU backend and that manifests
round-tripped byte-exactly. Its simplified model treated capacity as a service rate, opposite to
the audited evaluator's allowance semantics, so no smoke outcome is a scientific result.

Source review showed that `VEC_JAX_N_VEHICLES` and `VEC_JAX_RSU_MAX_CONCURRENT` already exposed
the necessary axes; the proposed source transform was unnecessary. A cost probe measured about
5.92 s/update at N=512 and 31.08 s/update at N=2,048, implying about 99 GPU-hours for the frozen
six-density, three-seed, five-million-step grid. The full B-DENSITY campaign was therefore not
run. The synthetic environment also had only two fixed RSUs on a 2 km corridor, limiting any
Manchester interpretation. See [B-DENSITY results](bdensity_phase1_results_20260729.md).

---

## 22. Live BODS observation programme

All acquisition was owner-triggered/attended, one request at a time with at least 60 seconds
between calls. Each session used a fresh operator-scoped HMAC pseudonym salt that died with the
process. Raw vehicle references, salts and private coordinates were not published. “Active”
means linked support across a declared session; per-snapshot counts are the concurrency measure.
Buses are not general road traffic.

### 22.1 Night cadence probe

Fifteen snapshots observed 872 buses but only 41 active linked vehicles. Median/p90 update cadence
was 68/75 s. A legitimate 28.4 m/s coach corrected the proposed plausibility ceiling from 25 to
32 m/s before later trace work. The session was useful for cadence, not daytime fleet density.

### 22.2 Shallow-dawn session

Fifty-two snapshots observed 1,676 buses and 1,162 active linked vehicles. Median/p90 cadence was
67/76 s. This was already 81.1% of the morning peak's active support.

### 22.3 Morning peak

Fifty-two verified quarantines observed 1,677 buses and 1,433 active linked vehicles; per-snapshot
concurrency reached 1,216 with median 1,192. Median/p90 cadence was 66/75 s. One strict parser
refusal remained unpromoted but could be reduced separately to aggregate session evidence.

### 22.4 Evening peak

The refusal-resilient runner attempted 85 snapshots, accepted 83 and recorded two refusals. It
observed 1,741 buses and 1,522 active linked vehicles. A 52-snapshot matched prefix contained
1,481 active vehicles, 3.3% more than the morning session. Concurrency reached 1,250 with median
1,215, cresting at 17:41 BST and declining to 999 by 18:47. Cadence remained 66/75 s.

### 22.5 Identity and refusal diagnosis

Long sessions showed that bare `VehicleRef` is reused across operators. Five preserved refusals
each contained exactly one two-activity collision across different operators and zero conflicts
after grouping by `(OperatorRef, VehicleRef, RecordedAtTime)`. Session identity policy v1.1
therefore scopes pseudonyms by operator and vehicle reference. Refused snapshots remained refused;
the analysis diagnosed a silent-corruption risk without weakening the parser boundary. See
[refusal evidence](../integration/evidence/man05_refusal_diagnosis_20260728.json).

### 22.6 Bus progression speed against fleet size

Median bus progression speed fell from 6.290 m/s at night to 4.441 m/s at dawn, 3.518 m/s in the
morning peak and 3.610 m/s across the full evening session. Resolving the evening session by hour
produced six near-monotone fleet-size points, ending at 1,462 vehicles and 3.369 m/s during the
evening crest. The peak/night contrast was about 44%.

**Interpretation.** This is the project's first end-to-end live-data relationship, but it is
observational and non-causal. Time of day, general congestion and bus fleet size covary. Bus
progression includes dwell and signals and must not be relabelled road speed. See
[speed-density analysis](bus_speed_density_20260728.md).

---

## 23. B-BUS dawn-to-peak hybrid experiments

### 23.1 Parent trace preparation and fail-closed refusal

The approved design used captured dawn mobility for training and captured morning-peak mobility
for held-out evaluation. After operator-scoped pseudonymisation, network matching, routing,
120-second gap, 15 m dwell, 80% matched-fix and 32 m/s drop-and-count rules, the private traces
retained 961 dawn and 1,212 peak buses, with peak concurrent widths 827 and 1,000. Approximately
98.4% of derived vehicle-seconds were interpolated because source cadence was 66–67 seconds.

The accepted VEC-06 placement contract allowed at most 2,000 occupied 50 m cells. The full traces
occupied 66,291 and 72,208 cells, so both refused before placement. No threshold was relaxed and
no favourable subwindow was selected. The owner then approved both successors: a bounded corridor
with full generated coverage, and whole-fleet Sparse-64 explicitly outside VEC-06. See
[trace-preparation result](bbus_dawn_peak_trace_preparation_20260728.md).

### 23.2 What was real and what was simulated

In both successors, bus positions/motion came from real captured BODS sessions. The trajectories
were derived and heavily interpolated. Computing tasks, task classes, payloads, deadlines,
equipment tiers, channel/fading model, energy accounting, queues and task outcomes were synthetic.
RSUs were generated analysis sites, not observed or deployed infrastructure. Thus the correct
description is **real captured bus mobility with synthetic vehicular-computing demand and generated
analysis infrastructure**.

### 23.3 Corridor dawn-to-peak

The corridor was a frozen 750 m capsule retaining 7.44% of dawn and 8.87% of peak parent
vehicle-seconds, with 12 separately generated full-coverage sites per window. Five actors, seeds
30–34, trained from scratch on dawn for 4,998,400 effective steps and were evaluated on the full
peak trace at per-RSU ceilings derived from cap-0.75 and cap-2.5.

At cap-0.75, equal-weight peak modelled deadline attainment was **0.809841** (sample SD 0.053436;
seed range 0.746932–0.854758), with T1/T2/T3 rates 0.623084/0.944427/0.803651 and mean modelled
latency 108.445 ms. Cap-2.5 attainment was 0.809672 and latency 108.656 ms. Four seeds were
numerically identical between capacity arms; one changed slightly. The actor action mixtures
varied substantially between seeds.

**Standing.** Preliminary non-admitted diagnostic pending independent homecoming/actor review.
It does not measure a dawn-to-peak loss because the frozen actors were not evaluated with an
endpoint-equivalent dawn procedure. See
[detailed settings and result](bbus_dawn_peak_settings_and_preliminary_results_20260729.md).

### 23.4 Sparse-64 first completed return

Sparse-64 preserved the whole fleet but used exactly 64 dawn-selected analysis sites reused at
peak. Only 45.0141% of dawn and 45.9960% of peak vehicle-seconds lay within 500 m of a site; the
experiment is outside VEC-06. Five seeds trained to 4,998,400 effective steps through durable
checkpoint recovery.

The retained cap-0.75 peak attainment was **0.519215** (sample SD 0.088806; range
0.427187–0.618675), with T1/T2/T3 0.337793/0.595472/0.545997 and latency 885.133 ms. Cap-2.5
attainment was 0.519108 and latency 1,042.527 ms. Four seeds were numerically identical across
capacity arms; one differed.

After completed training, `launchd` restarted the supervisor and caused 147 unintended repeats of
the same fixed held-out evaluation/return. Training, actors and checkpoints did not change and no
metric-based selection occurred, but the review retained and bound only the final return, so
cross-return metric identity could not be verified. The literal one-shot rule failed.

**Standing.** Execution-deviated and non-admitted. See
[homecoming result](bbus_sparse64_homecoming_results_20260730.md).

### 23.5 Sparse-64 clean rerun and owner admission

A new owner-approved execution used the unchanged frozen pack. All five seeds again completed
through checkpoint recovery. The retained cap-0.75 result was **0.501355** (sample SD 0.088677;
range 0.400527–0.634229), with T1/T2/T3 0.314816/0.592028/0.521530 and latency 895.561 ms.
Cap-2.5 attainment was 0.501233 and latency 1,055.814 ms.

After the first valid result download, a terminal-state ordering timeout caused one unintended
second fixed held-out evaluation/return. Training, actors, checkpoints and scientific settings
were not overwritten or changed, and no metric-based selection occurred. Cross-return metric
identity remained unverifiable. The ordering defect was repaired and tested.

On 2 August the owner admitted the retained clean rerun only as descriptive evidence with the
immutable **`admitted_with_execution_deviation`** qualifier. The earlier 147-repeat return remains
non-admitted. Neither result is pooled with protocol-confirmed VEC evidence, and neither supports
actor admission, causal rush-hour effects, general-Manchester conclusions, observed-RSU claims or
physical-completion claims. See the
[append-only owner decision](bbus_sparse64_clean_rerun_owner_admission_20260802.json).

---

## 24. Manchester network and demand investigations

### 24.1 Demand diagnosis

The predeclared diagnosis reproduced 43,200 routes and sampled 749,267 vehicles from the committed
count artifact. The recorded fringe-bias hypothesis was refuted: only 0.06% of pool routes began on
an entry-fringe edge, below the 1.88% unweighted edge base rate. Routes were long, with median
8.17 km and 134 edges in sampled demand.

The binding issue was structural reachability. Four counted edges had zero pool routes and were
100% unmet. Two additional edges carrying 61.4% of total shortfall had only two pool routes each,
against a median of about 395. Six edges with coverage of at most two routes accounted for 72.8%
of unmet vehicles. The three frozen repair variants targeted non-binding mechanisms, so no variant
ran and the design returned to the owner. See
[demand-diagnosis results](demand_diagnosis_results_20260728.md).

### 24.2 Counted-edge reachability

Topology and permission analysis identified two causes. Exactly four of 150 counted edges allowed
only buses/bicycles and were exactly the four zero-coverage edges; a passenger-only route pool
cannot reproduce motor-vehicle counts on those lanes. The two dominant-shortfall edges were the
southernmost M56 segments at the clip boundary, one with only one upstream edge within eight hops
against a typical median of 208. Together the six edges accounted for 122,235 unmet vehicles.
This was a modelling-scope diagnosis, not authority to exclude targets or change the study area.
See [reachability evidence](../integration/evidence/counted_edge_reachability_20260728.json).

### 24.3 N1 source-identity re-examination

The earlier claim that a dated Geofabrik extract mutated was withdrawn. The on-disk compressed PBF
matched the provider's published MD5 and first acquisition record. A prior evidence record had
placed the decoded XML identity in source-extract fields, then compared it with the compressed-PBF
checksum. Decoding the verified PBF reproduced the recorded decoded SHA-256 exactly, and the
rebuilt network reproduced the canonical network identity. No provider mutation occurred. See
[N1 evidence](../integration/evidence/n1_reexamination_and_peak_concurrency_20260728.json).

### 24.4 Observation-chain regeneration

After a session workspace disappeared, the network/subnetwork/index/match chain was regenerated
from committed pins. The regenerated study network contained exactly 285,794 of 804,611 parent
real edges, preserving every study edge ID. DfT reacquisition returned 342 count points and 39,072
raw-count rows over 79 pages with matching fingerprint prefixes. The 305-site match split
reproduced v1.0 counts 106/178/21 and v1.1 counts 131/165/9, including 51 override edges and 1,339
refused candidates. The review surface reopened with 174 pending rows and no fabricated decision.

One historical reconciliation fingerprint could not be verified because its computation recipe
lived only in the lost session script. The methodological result is that a digest is reproducible
evidence only when its defining code is retained. See
[restoration evidence](../integration/evidence/manchester_chain_restoration_20260728.json).

---

## 25. Cross-programme scientific conclusions

### 25.1 Findings with the strongest current support

- The cap-2.5 to cap-0.75 intervention changed a model admission/in-flight ceiling, not computing
  power.
- On the signed five-seed held-out `inc` contrast, mean modelled latency fell by 8,310.9 ms while
  modelled deadline attainment stayed flat-to-rising.
- Keyed actions were identical across capacity arms for the audited 17-D actor, and a second 17-D
  actor was also invariant.
- The modelled-latency change was concentrated in the already-deadline-failed extreme tail; median
  latency was essentially unchanged.
- Normal-density traces were insensitive across the standard grid, and deep-squeeze responses were
  tiny.
- The exact-equality density-proportional onset prediction was refuted.
- The trained actor retained an approximately 6.09 percentage-point deadline-attainment advantage
  over the baseline actor; no crossover occurred, but actor-independent latency slope was refuted.
- Live BODS sessions measured stable update cadence and a non-causal negative association between
  bus fleet size/time of day and bus progression speed.
- The clean Sparse-64 result is owner-admitted only as descriptive evidence with an execution
  deviation; it is not clean protocol-confirmed VEC evidence.

### 25.2 Findings that are suggestive but not resolved

- Per-RSU load is strongly asymmetric, but the precise spatial/association cause is unresolved.
- The actor's offload partition aligns exactly with compute tier in analysed cells, but the causal
  benefit or harm of offloading tier-0 vehicles is not identified.
- B-CAP proves that capacity/headroom information can influence a retrained actor, but admitted
  trace-level outcome benefit is untested.
- B-BUS suggests large seed and infrastructure-scope sensitivity, but its compute workload and
  infrastructure are simulated and its corridor/Sparse arms are not interchangeable treatments.
- Bus progression changes with time-of-day fleet size, but general congestion is unmeasured.

### 25.3 Claims explicitly unavailable

- faster computation caused by lowering the ceiling;
- improved physical task completion or throughput;
- a causal queue/fail-fast mechanism without complete lifecycle instrumentation;
- verified load-aware RSU routing benefit;
- real deployed RSU performance or real bus-computing task outcomes;
- general Manchester or multi-city validity;
- supervisor, ethics, publication or production approval; and
- superiority of a learned scheduler over deterministic forwarding.

---

## 26. Methodological lessons

1. **Predeclare outcomes and publish nulls.** The expected deadline cliff, actor crossover and
   onset law failed; those failures are results rather than discarded runs.
2. **Separate execution, admission and interpretation.** A completed GPU archive is not
   automatically admitted scientific evidence; an admitted descriptive result is not causal or
   supervisor-approved.
3. **Instrument below aggregates.** Action arrays, task classes, vehicle tiers and per-RSU state
   exposed mechanisms hidden by fleet means.
4. **Retain negative and withdrawn findings.** The N1 provider-mutation claim and the RSU
   association attribution were corrected in place rather than erased.
5. **Treat orchestration as experimental provenance.** Resume defects, stale credentials and
   duplicate returns are material even when actors/settings do not change.
6. **Preserve computation recipes beside digests.** A hash without the code defining its input
   projection is not reproducible evidence.
7. **Real input does not make every layer real.** B-BUS used captured mobility, but tasks,
   hardware, radio, queues, sites and outcomes remained simulated.

---

## 27. Defensible next research sequence

1. Clarify and instrument complete task-lifecycle and work-conservation semantics: offered,
   admitted, rejected, queued, started, executed, finished and returned states plus drop causes.
2. Test deterministic application-level RSU dispatch/forwarding baselines—no forwarding,
   least-loaded eligible RSU and predicted earliest completion—with explicit queueing, forwarding
   delay, stale-state age, reservation and return-path rules. Under matched seeds, measure
   physical-completion proxies, throughput, modelled deadline attainment, rejection, queue age,
   forwarding rate, per-RSU utilisation and balance.
3. Compare a learned scheduler only after the deterministic baseline exists under matched
   information, actions and compute budget.
4. Treat capacity-aware actor retraining as a separate experiment. A frozen actor can feed a
   downstream dispatcher without retraining; an actor that directly observes load/capacity or
   chooses the execution RSU requires retraining.

This ordering follows the [6 August audit](../current_status_5_6_pro_analysis.md) and supersedes
older recommendations that moved directly from the latency result to a scheduler.

---

## 28. Primary source index

- [Consolidated register](../experiments_and_findings_20260728.md)
- [Detailed experiment catalogue](experiment_catalogue_20260730.md)
- [Capacity pilot](capacity_pilot_results_20260727.md)
- [Signed held-out result](capacity_confirmatory_results_20260728.md)
- [Capacity detailed findings](capacity_study_detailed_findings.md)
- [Grid and sweep results](capacity_grid_results_20260728.md)
- [Latency-tail analysis](latency_tail_analysis_20260728.md)
- [Pilot dynamics](pilot_dynamics_analysis_20260728.md)
- [Offload partition](offload_partition_analysis_20260729.md)
- [RSU asymmetry](rsu_load_asymmetry_20260728.md)
- [Partially withdrawn RSU association analysis](rsu_association_analysis_20260729.md)
- [Ceiling prediction](ceiling_law_prediction_results_20260729.md)
- [Actor crossover](actor_crossover_results_20260730.md)
- [Onset-scaling result](onset_scaling_prediction_results_20260730.md)
- [BODS session results](bus_session_results_20260728.md)
- [Bus speed-density analysis](bus_speed_density_20260728.md)
- [B-BUS detailed settings](bbus_dawn_peak_settings_and_preliminary_results_20260729.md)
- [Sparse-64 first homecoming](bbus_sparse64_homecoming_results_20260730.md)
- [Sparse-64 clean rerun](bbus_sparse64_clean_rerun_results_20260730.md)
- [Sparse-64 owner admission](bbus_sparse64_clean_rerun_owner_admission_20260802.json)
- [Demand diagnosis](demand_diagnosis_results_20260728.md)
- [Research directions](../research_directions_v2.md)
- [6 August semantic and architecture audit](../current_status_5_6_pro_analysis.md)

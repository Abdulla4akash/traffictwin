# Live-bus and Google Colab experiments

**Coverage:** attended BODS observations, Colab/GPU experiments and B-BUS hybrid runs completed
through 6 August 2026

**Evidence ceiling:** descriptive and non-causal unless a narrower internal label is stated

**External standing:** no result is supervisor-approved, externally validated or a production
deployment verdict

## Abstract

TrafficTwin conducted two related but scientifically distinct bodies of work. First, four
attended Bus Open Data Service (BODS) sessions measured real Manchester bus positions, feed
cadence, linked-fleet support and bus progression. These observations found stable feed cadence
across a roughly 36-fold fleet range and slower bus progression during peak periods. The
relationship is real-world and end-to-end, but observational rather than causal: time of day, bus
fleet size and unmeasured general congestion covary.

Second, Google Colab supplied GPU compute for synthetic policy-training diagnostics and for B-BUS
hybrid experiments. The generic B-CAP, B-REWARD, B-MASK, B-DOMAIN and B-DENSITY work did not use
live bus data. The later B-BUS corridor and Sparse-64 experiments did use trajectories derived
from the captured BODS sessions, but their computing tasks, deadlines, equipment, radio/channel
model, queues, energy accounting, roadside units and task outcomes were simulated. They are
therefore **real-data-informed simulations**, not observations of real vehicular-edge-computing
completion.

The strongest live-data finding is the non-causal association between bus-fleet support and bus
progression speed. The Colab programme established engineering feasibility, reproduced the
capacity-observability gap in synthetic training and showed that a 19-dimensional actor supplied
with capacity/headroom can change its decisions. It did not establish that such responsiveness
improves admitted Manchester outcomes. The clean Sparse-64 rerun has the narrow standing
`admitted_with_execution_deviation`; all other Colab outputs remain non-admitted diagnostics.

---

## 1. Scientific scope and terminology

### 1.1 Included work

This document covers:

- four attended live BODS sessions: night, shallow dawn, morning peak and evening peak;
- offline session analyses of cadence, fleet support, identity collisions, parser refusals and
  bus progression speed;
- the Colab B-CAP, B-REWARD, B-MASK, B-BUS/IPPO smoke, B-DOMAIN and B-DENSITY programmes;
- B-BUS trace preparation and its fail-closed placement refusal;
- the B-BUS corridor dawn-to-peak experiment; and
- the first and clean-rerun Sparse-64 dawn-to-peak executions.

The earlier local capacity campaign is outside this document except where its terminology is
needed to prevent a false interpretation of B-BUS capacity arms.

### 1.2 Evidence labels

| Label | Meaning here |
|---|---|
| Live observation | Aggregate measurement derived from attended BODS acquisition; not a randomized intervention. |
| Non-admitted diagnostic | Engineering or hypothesis-generating output outside the scientific admission chain. |
| `owner_approved_candidate` | Internal owner-attested ceiling; not an authenticated signature, independent review or supervisor approval. |
| `admitted_with_execution_deviation` | Owner-admitted descriptive use with an immutable execution deviation; not clean protocol-confirmed evidence. |
| Actor-admitted | A trained checkpoint has passed the separate reviewed actor-admission chain. No actor in this document has that standing. |

### 1.3 What was real and what was simulated

| Study family | Real input | Simulated or generated layer | Defensible description |
|---|---|---|---|
| Attended BODS sessions | Provider responses, bus observations and source timestamps | No simulator used for the reported session aggregates | Live bus observations |
| B-CAP, B-REWARD, B-MASK, B-DOMAIN, B-DENSITY | Producer code and real GPU execution | Synthetic highway, vehicles, tasks, RSUs and outcomes | Synthetic GPU diagnostics |
| B-BUS corridor and Sparse-64 | Bus positions/motion derived from captured BODS sessions | Tasks, deadlines, hardware, radio/channel, queues, energy, RSUs and outcomes | Real-mobility-informed VEC simulation |

Real bus input does not make a simulated task outcome a real-world completion measurement. Buses
also cannot be relabelled as general road traffic.

### 1.4 Capacity language used in B-BUS

The B-BUS cap-2.5 and cap-0.75 arms changed a configured **per-RSU admission/in-flight
concurrency ceiling**, not computation power or physical processor speed. The task-lifecycle
accounting does not completely connect offered, admitted, rejected, queued, started, executed,
finished and returned work. Accordingly, differences in mean modelled latency are not evidence
of faster computation or improved physical completion.

---

## 2. Chronology

| Date | Work | Venue/data | Current standing |
|---|---|---|---|
| 27 Jul 2026 | Night BODS cadence probe | Attended live BODS | Descriptive live observation |
| 28 Jul 2026 | Shallow-dawn and morning-peak BODS sessions | Attended live BODS | Descriptive live observations |
| 28 Jul 2026 | Evening-peak BODS session | Attended live BODS | Descriptive live observation |
| 28 Jul 2026 | Identity/refusal and bus speed–fleet analyses | Offline aggregate analysis of captured BODS data | Descriptive, non-causal |
| 28 Jul 2026 | B-CAP, B-REWARD, B-MASK, B-BUS/IPPO smokes and B-DOMAIN | Colab T4/G4; mostly synthetic producer environment | Non-admitted diagnostics |
| 28 Jul 2026 | B-BUS parent trace preparation | Derived dawn/peak BODS mobility | Failed closed at VEC-06 placement |
| 28–29 Jul 2026 | B-BUS corridor training/evaluation | Colab G4; captured mobility plus simulated VEC layers | Preliminary non-admitted diagnostic |
| 29 Jul 2026 | B-DENSITY phase 1 and cost probe | Colab G4; synthetic producer environment | Non-admitted engineering diagnostic; full grid not run |
| 29–30 Jul 2026 | B-BUS Sparse-64 first execution | Colab G4; captured mobility plus simulated VEC layers | Execution-deviated, non-admitted |
| 30 Jul–2 Aug 2026 | B-BUS Sparse-64 clean rerun and owner decision | Colab G4; unchanged frozen pack | `admitted_with_execution_deviation`, descriptive only |

---

## 3. Attended live-bus observation programme

### 3.1 Acquisition and privacy contract

Every acquisition was owner-triggered and attended. Requests were made one at a time with at
least 60 seconds between calls. Each declared session used a new in-process HMAC pseudonym salt,
scoped by operator and vehicle reference, that died with the process. Raw vehicle references,
salts and private coordinates were not published.

“Vehicles seen” counts any bus observed in the session. “Active” means an operator-scoped
session pseudonym supported by at least two distinct recorded times; it is not a simultaneous
traffic count. Per-snapshot concurrency is reported separately where measured.

### 3.2 Night cadence probe

**Purpose.** Measure update cadence and test early plausibility assumptions with a short,
low-fleet session.

**Design and execution.** Fifteen snapshots were captured around midnight. The session observed
872 buses but produced only 41 active linked vehicles.

**Results.** Median/p90 update cadence was 68/75 seconds. Median displacement between distinct
updates was 417.9 m. A legitimate coach observation implied 28.4 m/s, refuting the proposed
25 m/s plausibility ceiling and motivating the later predeclared 32 m/s drop-and-count rule.

**Interpretation.** The probe was informative about provider cadence but not representative of
daytime fleet support.

### 3.3 Shallow-dawn session

**Purpose.** Measure whether early-morning acquisition could supply enough linked vehicles for
trajectory construction.

**Design and execution.** Fifty-two snapshots from 06:12–07:09 BST observed 1,676 buses and
1,162 active linked vehicles.

**Results.** Median/p90 cadence was 67/76 seconds and median displacement was 300.9 m. Dawn
already supplied 81.1% of the later morning peak's active support.

**Interpretation.** Fleet support grew sharply while provider update cadence remained similar to
the night probe.

### 3.4 Morning-peak session

**Purpose.** Measure rush-hour linked support, concurrency and cadence for a candidate held-out
peak mobility trace.

**Design and execution.** Fifty-two verified quarantines from 08:02–08:58 BST contained 1,677
buses and 1,433 active linked vehicles. Fifty-one snapshots were promoted; the final strict-parser
refusal remained refused and could be reduced only through the separately verified aggregate
session layer.

**Results.** Per-snapshot concurrent live support reached 1,216 with median 1,192. Median/p90
cadence was 66/75 seconds and median displacement was 231.4 m. Feed concurrency sat between the
earlier normal-density and collapse-hour synthetic trace widths, although feed concurrency is not
automatically the slot width of a derived simulation trace.

**Interpretation.** The session supplied substantial live bus support. It did not itself execute
a VEC experiment or measure task completion.

### 3.5 Evening-peak session

**Purpose.** Extend peak observation using a refusal-resilient attended runner and measure the
crest and decline of the evening service period.

**Design and execution.** Eighty-five snapshots were attempted; 83 were accepted and two were
preserved as refusals. The session observed 1,741 buses and 1,522 active linked vehicles. A
52-snapshot matched prefix contained 1,481 active vehicles, 3.3% more than the morning session.

**Results.** Concurrency reached 1,250 with median 1,215. It crested at 17:41 BST and declined to
999 by 18:47. Median/p90 cadence remained 66/75 seconds.

**Interpretation.** The evening run broadened the live-data range without weakening the strict
parsing boundary.

### 3.6 Identity-collision and refusal diagnosis

**Question.** Were rush-hour refusals malformed provider data, overload, or an identity-scope
problem?

**Method.** All five preserved refusals were replayed read-only after byte verification. Raw
grouping and operator-scoped grouping were compared without changing parser acceptance.

**Results.** Each refusal contained exactly one collision consisting of two activities under the
same bare `VehicleRef` and time but different operators. Grouping by
`(OperatorRef, VehicleRef, RecordedAtTime)` left zero conflicts. Longer sessions also showed that
bare `VehicleRef` values are reused across operators; merging them would manufacture impossible
kilometre-per-second trajectories.

**Interpretation.** The refusals diagnosed a provider-identity scope defect and a silent-corruption
risk. They were not evidence of feed overload. Session identity policy v1.1 therefore scopes the
pseudonym by operator and vehicle reference, while refused snapshots remain refused.

### 3.7 Bus progression speed against fleet support

**Question.** How did observed bus progression change across the night-to-peak fleet range?

**Method.** Progression speed was calculated per accepted segment, then summarized from hourly
medians. This is bus displacement over time, including stops, signals and layover; it is not road
speed.

| Session | Snapshots | Active fleet | Median progression | Approx. km/h |
|---|---:|---:|---:|---:|
| Night | 15 | 41 | 6.290 m/s | 22.6 |
| Shallow dawn | 52 | 1,162 | 4.441 m/s | 16.0 |
| Morning peak | 51 | 1,431 | 3.518 m/s | 12.7 |
| Evening peak | 83 | 1,522 | 3.610 m/s | 13.0 |

The progression table uses the 51 promoted morning snapshots and 1,431 linked vehicles that
support accepted movement segments. The wider session aggregate includes the final separately
reduced refusal and therefore reports 52 verified quarantines and 1,433 active vehicles. These
figures answer different questions and are not contradictory.

Resolving the sessions by hour produced six near-monotone points ordered by fleet support,
ending at 1,462 vehicles and 3.369 m/s during the evening crest. Median bus progression at the
morning peak was about 44% lower than at night; p90 progression also fell.

**Scientific standing.** This is the strongest end-to-end live-data relationship in the project,
but it is observational and non-causal. Bus fleet size, time of day and unmeasured general road
congestion covary. The evidence supports “buses progressed more slowly in the larger peak-period
fleet,” not “more buses caused the slowdown.”

---

## 4. Google Colab synthetic GPU programme

### 4.1 Shared purpose and limitations

The Colab programme used a T4 for the first engineering smoke and owner-managed G4
Blackwell-class GPUs for later from-scratch MAPPO training. Producer code was used under recorded
permission and citation. The generic campaigns used the producer's synthetic highway and no
producer trace or BODS data. Private archives stayed gitignored and were represented publicly only
by content-addressed preservation records.

Training completion, reward curves and greedy synthetic diagnostics do not admit an actor or
constitute Manchester evidence. No returned actor in this programme completed the separate actor
admission path.

### 4.2 B-CAP engineering smoke

**Question.** Does adding configured capacity and selected-RSU headroom to the observation reach
the policy and change its behavior?

**Design.** One short seed compared the original 17-dimensional hidden-capacity actor with a
19-dimensional treatment appending normalized capacity and selected-RSU headroom.

**Result.** The 17-D control was exactly invariant across four ceilings. The 19-D treatment
changed its local/V2I decisions with capacity. At the tiny smoke scale, its synthetic reported
completion proxy was approximately 98.86%, compared with 99.24% for the control.

**Standing.** Engineering proof of the information path, not evidence of benefit.

### 4.3 B-CAP full training

**Question.** Does randomized training with explicit capacity/headroom information make a policy
capacity-sensitive?

**Design.** Ten from-scratch jobs paired seeds 100–104 across a 17-D hidden-capacity arm and a
19-D capacity/headroom arm. Each requested five million environment steps, randomizing per-RSU
ceilings 50/30/20/15.

**Result.** The 17-D actors remained exactly capacity-invariant, while the 19-D actors changed
decisions with capacity. This reproduced the observation-blindness mechanism in synthetic
training and showed that a capacity-aware policy can be trained.

**Standing.** Non-admitted diagnostic. Responsiveness was not shown to improve admitted
trace-level outcomes. Frozen actors do not need retraining merely to feed a downstream dispatcher;
an actor that itself observes capacity/load or chooses the execution RSU does require retraining.

### 4.4 B-REWARD

**Question.** With the 19-D observation fixed, how does removing the energy term affect learned
behavior in the synthetic environment?

**Design.** Ten jobs paired seeds 200–204 between balanced QoS/energy reward (`alpha=0.7`) and
pure QoS (`alpha=1.0`).

**Result.** Pure QoS changed the reported completion proxy by approximately +0.017 percentage
points, energy by +0.04 J/task, local execution by roughly +10 percentage points, slightly lowered
modelled latency and reduced capacity-conditioned action switching from 3.51% to 1.94%.

**Standing.** Sealed synthetic diagnostic, not admitted Manchester performance and not a general
reward recommendation.

### 4.5 B-MASK

**Question.** How do training-time and deployment-time feasibility masks affect infeasible action
selection?

**Design.** Ten jobs paired seeds 300–304 with and without the producer's training mask. Every
checkpoint was evaluated with deployment masking both on and off at four ceilings.

**Result.** All ten jobs completed. Across 80 diagnostic cells and 10,240,000 recorded decisions,
masked deployment selected zero infeasible actions, satisfying the declared invariant.

**Standing.** Non-admitted diagnostic. Broader treatment and interaction contrasts remain sealed
pending independent review.

### 4.6 B-BUS and IPPO engineering smokes

Synthetic stand-in smokes proved that a bus-native training path and a second IPPO
algorithm-family path could execute. They did not use the later live-derived bus traces and did
not produce a real-bus verdict, actor admission or algorithm comparison.

### 4.7 B-DOMAIN

**Question.** How sensitive are capacity-aware actors to different procedural task-type training
mixtures?

**Design.** Fifteen jobs, seeds 400–404, trained 19-D actors under default, safety-dominant and
pilot-inspired mixtures, then evaluated the full train-by-domain matrix at baseline and squeezed
ceilings.

**Result.** All 15 jobs completed, producing 90 diagnostic cells and 11,520,000 decisions.

**Standing.** Non-admitted synthetic diagnostic. Descriptive contrasts remain pending independent
review. The procedural mixtures are not literal Manchester or BODS distribution shift.

### 4.8 B-DENSITY phase 1 and cost probe

**Question.** Could the synthetic GPU environment expose a density axis suitable for a full
density-by-capacity training grid, and what would that grid cost?

**Design.** The smoke crossed densities 128/1,024, controls 2.5/0.25 and seeds 700/701 over 2,000
steps. A later timing probe measured larger workloads.

**Results.** The density axis reached the GPU and manifests round-tripped byte-exactly. Source
review found that existing environment variables already exposed density and per-RSU concurrency,
so the proposed source transformation was unnecessary. Timing rose from approximately 5.92
seconds/update at N=512 to 31.08 seconds/update at N=2,048, implying roughly 99 GPU-hours for the
frozen full design.

**Standing.** The full campaign was not run. The smoke's compact model treated capacity as a
service rate, opposite to the audited evaluator's admission/in-flight allowance semantics, so its
outcomes are not scientific results. The synthetic environment also contained only two fixed RSUs
on a 2 km corridor and cannot establish a Manchester density threshold.

---

## 5. B-BUS: Colab experiments using captured live-bus mobility

### 5.1 Trace preparation and fail-closed placement

**Purpose.** Construct a dawn training trace and morning-peak held-out trace from captured BODS
mobility without exposing raw identities or coordinates.

**Method.** Operator-scoped pseudonymization, network matching and routing were followed by a
120-second gap rule, 15 m dwell rule, 80% matched-fix floor and 32 m/s drop-and-count rule. The
private traces retained 961 dawn and 1,212 peak buses, with concurrent widths 827 and 1,000.
Because BODS cadence was around 66–67 seconds, approximately 98.4% of derived vehicle-seconds were
interpolated.

**Result.** The accepted VEC-06 placement contract allowed at most 2,000 occupied 50 m cells. The
full traces occupied 66,291 and 72,208 cells, so both refused before placement. No threshold was
relaxed and no favorable subwindow was selected.

**Successors.** The owner separately approved a bounded, fully covered corridor and a whole-fleet
Sparse-64 design explicitly outside VEC-06.

### 5.2 B-BUS corridor dawn-to-peak

**Design.** A frozen 750 m capsule retained 7.44% of dawn and 8.87% of peak parent
vehicle-seconds. Twelve generated analysis sites supplied full coverage in each window. Five
actors, seeds 30–34, trained from scratch on dawn for 4,998,400 effective steps and were evaluated
on the peak trace under cap-0.75 and cap-2.5 per-RSU concurrency ceilings.

**Results.** At cap-0.75, equal-weight peak modelled deadline attainment was 0.809841 (sample SD
0.053436; seed range 0.746932–0.854758), with T1/T2/T3 rates
0.623084/0.944427/0.803651 and mean modelled latency 108.445 ms. At cap-2.5, attainment was
0.809672 and latency 108.656 ms. Four seeds were numerically identical between arms; one changed
slightly. Action mixtures varied substantially between seeds.

**Standing.** Preliminary non-admitted diagnostic. It does not measure dawn-to-peak degradation
because the actors were not evaluated with an endpoint-equivalent dawn procedure. It also does not
show an infrastructure or capacity benefit.

### 5.3 Sparse-64 first completed return

**Design.** Sparse-64 retained the whole derived fleet but used exactly 64 dawn-selected generated
analysis sites reused at peak. Only 45.0141% of dawn and 45.9960% of peak vehicle-seconds were
within 500 m of a site, placing the study outside VEC-06. Five seeds trained to 4,998,400 effective
steps through checkpoint recovery.

**Results.** Retained cap-0.75 peak attainment was 0.519215 (sample SD 0.088806; range
0.427187–0.618675), with T1/T2/T3 rates 0.337793/0.595472/0.545997 and latency 885.133 ms.
Cap-2.5 attainment was 0.519108 and latency 1,042.527 ms. Four seeds were numerically identical
across capacity arms; one differed.

**Execution deviation.** After training completed, `launchd` restarted the supervisor and caused
147 unintended repeats of the same fixed held-out evaluation/return. Training, actors and
checkpoints were unchanged and there was no metric-based selection. The review retained and bound
only the final return, so cross-return metric identity is unverifiable and the literal one-shot
rule failed.

**Standing.** Execution-deviated and non-admitted.

### 5.4 Sparse-64 clean rerun and owner admission

**Design.** A new owner-approved execution used the unchanged frozen pack. All five seeds again
completed through checkpoint recovery.

**Results.** Retained cap-0.75 peak attainment was 0.501355 (sample SD 0.088677; range
0.400527–0.634229), with T1/T2/T3 rates 0.314816/0.592028/0.521530 and latency 895.561 ms.
Cap-2.5 attainment was 0.501233 and latency 1,055.814 ms.

**Execution deviation.** A terminal-state ordering timeout caused one unintended second fixed
held-out evaluation/return after the first valid result download. Training, actors, checkpoints
and scientific settings were not overwritten or changed, and no metric-based selection occurred.
Cross-return metric identity remains unverifiable. The ordering defect was repaired and tested.

**Standing.** On 2 August the owner admitted only the retained clean rerun as descriptive evidence
with the immutable `admitted_with_execution_deviation` qualifier. The earlier 147-repeat return
remains non-admitted. Neither may be pooled with protocol-confirmed VEC evidence or used to claim
actor admission, causal rush-hour effects, general Manchester validity, observed-RSU performance,
faster computation or improved physical completion.

---

## 6. Scientific conclusions

### 6.1 Supported within the stated bounds

- Live BODS cadence remained near 66–68 seconds median and 75–76 seconds p90 across a roughly
  36-fold active-fleet range.
- Bus progression was lower during peak periods than at night; the measured peak/night contrast
  was approximately 44%.
- Bare `VehicleRef` was not globally unique across operators. Operator scoping prevented identity
  merging that would otherwise create impossible trajectories.
- A 19-D synthetic actor supplied with configured capacity and selected-RSU headroom changed its
  decisions with capacity, whereas the 17-D hidden-capacity actor remained invariant.
- Deployment feasibility masking selected zero infeasible actions in the recorded B-MASK
  diagnostic cells.
- B-BUS demonstrated that privacy-preserving, captured bus mobility can drive a GPU training and
  evaluation pipeline, subject to heavy interpolation and generated infrastructure.

### 6.2 Not established

- that bus fleet size caused slower progression;
- that bus progression equals general road speed;
- that any Colab actor improves admitted Manchester outcomes;
- that lower B-BUS mean modelled latency represents faster computation or physical completion;
- that generated analysis sites represent observed or deployed RSUs;
- that corridor and Sparse-64 are interchangeable infrastructure treatments;
- that a learned scheduler outperforms deterministic forwarding; or
- that any result has supervisor, publication, production or external-validation standing.

### 6.3 Defensible next sequence

1. Instrument complete task-lifecycle and work-conservation semantics.
2. Test a deterministic application-level RSU dispatcher/forwarder under matched seeds.
3. Compare a learned scheduler only after the deterministic baseline exists.
4. Treat capacity-aware actor retraining as a separate experiment. Frozen-actor forwarding does
   not itself require retraining; adding RSU load/capacity to the actor does.

---

## 7. Source records

- [Complete experiment history](complete_experiment_history_20260806.md)
- [Detailed experiment catalogue](experiment_catalogue_20260730.md)
- [Live BODS session results](bus_session_results_20260728.md)
- [Evening-peak session results](bus_evening_peak_session_20260728.md)
- [Bus progression against fleet size](bus_speed_density_20260728.md)
- [Aggregate BODS session evidence](../integration/evidence/bods_bus_sessions_20260728.json)
- [MAN-05 refusal diagnosis](../integration/evidence/man05_refusal_diagnosis_20260728.json)
- [B-CAP smoke evidence](../integration/evidence/bcap_engineering_smoke_20260728.json)
- [B-CAP full-training predeclaration](bcap_training_predeclaration_20260728.md)
- [B-REWARD predeclaration](breward_training_predeclaration_20260728.md)
- [B-MASK preservation record](../integration/evidence/bmask_full_campaign_preservation_20260728.json)
- [B-DOMAIN preservation record](../integration/evidence/bdomain_full_campaign_preservation_20260728.json)
- [B-DENSITY phase-1 results](bdensity_phase1_results_20260729.md)
- [B-BUS trace-preparation result](bbus_dawn_peak_trace_preparation_20260728.md)
- [B-BUS corridor settings and result](bbus_dawn_peak_settings_and_preliminary_results_20260729.md)
- [Sparse-64 first homecoming](bbus_sparse64_homecoming_results_20260730.md)
- [Sparse-64 clean-rerun result](bbus_sparse64_clean_rerun_results_20260730.md)
- [Sparse-64 owner admission](bbus_sparse64_clean_rerun_owner_admission_20260802.json)
- [6 August semantic audit](../current_status_5_6_pro_analysis.md)

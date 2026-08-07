# TrafficTwin MSc Dissertation Research Audit

**Audit date:** 7 August 2026
**Mode:** read-only scientific and implementation audit; no code was modified and no expensive campaign was launched.
**Requested scope:** TrafficTwin, `vec_env`, and `tos-data`, using the source-authority hierarchy in the supplied brief.
**Important coverage limitation:** the GitHub repositories and branches were inspected. The local working trees under
`/Users/akashx/...`, untracked files, local result directories and scheduler queues were not accessible from this audit.
Therefore, “not found” means “not found in the inspected repository state,” not “cannot exist on a local disk.”

## Audit pins

| Resource | Audited identity |
|---|---|
| TrafficTwin requested branch | `codex/traffictwin-v0.7 @ ae5b543df6a37e8083c5807aa766aba12872ff21` |
| TrafficTwin current main observed during branch inventory | `main @ a462c72b81f1668eef4ea0b7f8e806be4d208b47` |
| TrafficTwin sequential research-prototype tip | `agent/vec-matched-dispatch-study-v1 @ 3813431f7366c833924fcc79d50268be2179e974` |
| vec_env | `main @ 0f01f4d2082d3e8b735e74a873095ab8eeba37cc` |
| tos-data | `main @ a75bbdb1a956f828ee0e9b97b33506bd32d31b85` |

## Evidence labels used

Every major claim below is assigned one label only:

`DIRECT_SUPERVISOR_DIRECTION`, `RANDY_REPORTED_RESULT`, `RANDY_PROPOSAL`,
`CODE_VERIFIED_IMPLEMENTATION`, `REPOSITORY_REPRODUCED_EVIDENCE`, `INFERENCE`,
`NEW_RECOMMENDATION`, or `MISSING_INFORMATION`.

# 1. Executive verdict

**[DIRECT_SUPERVISOR_DIRECTION]** Sandra's problem is not “make a queue smaller” and not simply
“use Kubernetes.” It is whether infrastructure-side load management can improve VEC task outcomes when the
frozen vehicle actor lacks adequate RSU-capacity awareness, while keeping admission ceilings, compute service,
placement and scaling conceptually separate.

**[CODE_VERIFIED_IMPLEMENTATION]** The current `vec_env` evaluator already contains enough machinery to begin
a corrected no-retraining study directly: physical reject semantics, sequential queue updates, conserved vehicle
queues, per-vehicle and absolute RSU caps, JSQ/P2C/deadline-aware placement, backhaul delay, and fixed/static/reactive
compute scaling.

**[CODE_VERIFIED_IMPLEMENTATION]** The requested TrafficTwin branch cannot orchestrate that current evaluator
faithfully. Its runner contract pins the older reviewed `vec_env`/`tos-data` snapshots and does not expose the new
physical-semantics, placement, absolute-cap or scaling flags.

**[CODE_VERIFIED_IMPLEMENTATION]** TrafficTwin also has a five-commit sequential prototype chain containing a
lifecycle contract, synthetic two-RSU hand check, deterministic dispatcher, future-native sidecar validator and
matched synthetic harness. These are useful engineering foundations, but they are unmerged and explicitly mark
themselves as non-scientific, non-native evidence.

**[REPOSITORY_REPRODUCED_EVIDENCE]** One old weekend evaluation was reproduced twice through TrafficTwin against
the old reviewed engine with exact/within-tolerance agreement. This proves the old bounded runner path, not the
corrected August engine, the disputed queue sweep, native scheduling benefit, or Kubernetes-style scaling.

**[MISSING_INFORMATION]** No repository artifact establishes Randy's reported `0.6943` completion and
approximately `4.9 → 128.4 s` latency sweep: the raw JSON/CSV, exact commands, cap grid, actor/checkpoint, seed list,
environment and numerical table are absent from the pinned repositories.

**[NEW_RECOMMENDATION]** Research execution can begin now, but only in two layers:

1. **Immediate engineering/scientific gate:** run E0, a current-engine corrected reference with full provenance and
   conservation.
2. **First causal experiment:** run E1, the matched legacy-versus-physical waiting-room sweep, before claiming any
   scheduler or scaling improvement.

**[NEW_RECOMMENDATION]** The strongest defensible MSc contribution is:

> A semantics-aware, conservation-checked evaluation of infrastructure-side RSU scheduling with a frozen vehicle
> actor, showing when deterministic load-aware placement and compute scaling help, tie or harm under admission
> limits, forwarding cost and stale state.

This contribution is smaller and stronger than immediately training another neural policy.

# 2. What Sandra wants

| Evidence class | Supervisor-directed point | Research consequence |
|---|---|---|
| DIRECT_SUPERVISOR_DIRECTION | The `2.5× → 0.75×` intervention changed an RSU admission/waiting-room ceiling, not computation power. | Reinterpret the prior latency result; do not call it compute scaling. |
| DIRECT_SUPERVISOR_DIRECTION | The frozen vehicle policy does not have adequate awareness of current RSU capacity/load. | Keep the actor frozen first and isolate infrastructure-side decisions. |
| DIRECT_SUPERVISOR_DIRECTION | Investigate deterministic infrastructure load balancing. | Compare strongest-link with transparent load-aware placement under matched tasks/seeds. |
| DIRECT_SUPERVISOR_DIRECTION | Investigate learned RSU scheduling/load balancing. | Treat learning as a gated extension after deterministic baselines. |
| DIRECT_SUPERVISOR_DIRECTION | Investigate AI-based Kubernetes/resource control. | Compare fixed 1×, static 3× and reactive/proactive simulated resource control, with cost denominators. |
| DIRECT_SUPERVISOR_DIRECTION | Report completion over offered work, conditional admitted completion, latency, energy, decisions, rejection, conservation, forwarding and scaling. | Freeze a semantic/metric contract before the campaign. |

A later planning synthesis of Supervisor Meeting 4 narrows the intended mechanism to scheduling under incomplete or
ageing RSU state, strongest-link versus a weaker but less-loaded RSU, forwarding cost and telemetry freshness.
Because that document explicitly says it is not a verbatim transcript or supervisor approval, those details are
treated here as **[INFERENCE]**, not upgraded to direct requirements.

# 3. What Randy added

| Evidence class | Randy contribution | Audit treatment |
|---|---|---|
| RANDY_REPORTED_RESULT | A waiting-room sweep from `0.75×` to `40×` reportedly kept completion near `0.6943` while mean latency rose from roughly `4.9 s` to `128.4 s`. | Unverified until raw outputs and exact manifest are supplied. |
| RANDY_PROPOSAL | Add RSU-load information to the actor and retrain. | Valid later ablation; not the first experiment. |
| RANDY_PROPOSAL | Use JSQ, P2C, deadline-aware admission/placement and combinations. | Current code supports most of this; comparisons must distinguish placement from admission. |
| RANDY_PROPOSAL | Compare fixed 1×, static 3×, reactive scaling and proactive forecasting. | Good staged architecture if resource use and actuation delay are reported. |
| RANDY_PROPOSAL | Sweep remote-state staleness at 0/100/500/1000 ms and backhaul cost. | Strong condition-map extension; staleness is not currently implemented. |
| RANDY_PROPOSAL | Keep Kubernetes worker/resource management separate from application placement/admission. | Correct architecture boundary; name current work “Kubernetes-style” until a real deployment exists. |
| CODE_VERIFIED_IMPLEMENTATION | August commits added reject semantics, sequential queue updates, conservation fields, absolute caps and scaling. | These are implementation facts, not evidence that a corrected campaign has run. |

# 4. What the code actually implements

## 4.1 TrafficTwin requested branch

**[CODE_VERIFIED_IMPLEMENTATION]**

- The requested branch is `ae5b543...`, but it diverges from main: GitHub reports it as four commits ahead and
  **271 commits behind** `a462c72...`.
- The branch's VEC runner is a bounded old-engine wrapper. Its request model pins the older reviewed external
  snapshots and exposes only the old trace/actor/cap/max-step/seed/fleet/output flags.
- It has accepted archival/reproduction/scientific-admission machinery for the old VEC evidence chain.
- It does not natively run current physical reject semantics, absolute caps, JSQ/P2C/deadline-aware placement or
  Kubernetes-style scaling.

**Interpretation:** the requested branch is appropriate for reading the new supervisor-direction documents, but it
is not the authoritative execution base for the new experiments.

## 4.2 TrafficTwin current main and unmerged prototypes

**[CODE_VERIFIED_IMPLEMENTATION]**

Starting from current main `a462c72...`, the sequential prototype chain adds:

1. `b7bc0cc...`: strict provisional per-task lifecycle ledger and task-count conservation over synthetic fixtures;
   no native producer and no CPU-work conservation.
2. `ec256ba...`: synthetic two-RSU oracle, with strong-link RSU A full, weaker RSU B idle, one forwarded task,
   `23 ms` end-to-end arithmetic and `400 mJ` forwarding arithmetic; not an evaluator run.
3. `3b13856...`: pure deterministic strongest-link/no-forwarding, least-loaded and predicted-earliest-completion
   policies with reservation-aware batching; caller supplies predicted state/costs.
4. `9fa1c37...`: read-only sidecar verifier for future native lifecycle/dispatch JSONL files; current evaluator does
   not emit those files.
5. `3813431...`: matched synthetic three-policy harness; explicitly no measured execution, return, deadline or
   scientific winner.

These prototypes substantially reduce future integration work but do not answer Sandra's research question yet.

## 4.3 vec_env current main

**[CODE_VERIFIED_IMPLEMENTATION]**

`eval/eval_sumo_stage1_mc.py` implements:

- `--rsu-cap-per-veh` and `--rsu-cap-abs`;
- `--substep-queue snapshot|sequential`;
- `--veh-queue legacy|conserved`;
- `--rsu-cap-mode clamp|reject`, with physical reject coupled to sequential updates;
- LB modes `off`, `jsq`, `p2c`, `dla`, `dla_p2c`;
- configurable backhaul delay;
- compute modes `off/fixed`, static multiplier and reactive Kubernetes-style scaling;
- offered/admitted populations, rejection reasons, class completion, conditional latency, capacity summaries and
  exact work conservation under the physical mode.

The evaluator does **not** currently implement:

- remote-state staleness;
- proactive load forecasting;
- a learned infrastructure dispatcher;
- an actor observation containing RSU load/capacity/age;
- complete ingress→execution→return per-task path evidence;
- forwarding count/energy as first-class output;
- physical return failure distinct from modelled deadline status;
- a real Kubernetes deployment.

`jaxmarl/env/vec_jax.py` and the PyTorch environment expose three actor actions:
Local, V2I and V2V. Exact V2I/V2V targets are environment-selected. In the JAX environment,
`best_rsu_load_frac` is computed but omitted from the 17-dimensional observation. The frozen actor therefore does
not observe current RSU load.

`jaxmarl/scripts/train_mappo_vec.py` has explicit action-mask training support, but masking is a separate trained
policy variant, not a harmless evaluator switch.

## 4.4 tos-data

**[REPOSITORY_REPRODUCED_EVIDENCE]**

- The repository contains 300 historical evaluation rows, five Manchester traces, actor checkpoints, per-step
  arrays, six showcase per-task arrays, training curves and machine records.
- The package is explicitly the older `v2_post_nrsus_fix` engine, produced before the 5 August physical-accounting
  commits.
- The five baseline incident/UK2030 fleet draws in the master CSV have old-engine completion values from
  approximately `0.7170` to `0.7414` (mean about `0.7247`).
- One sample incident run records about 13.1 million offered tasks and roughly 10,743 seconds wall time.
- Historical retraining records show that matching gridlock speed/density while keeping a two-RSU training topology
  transferred badly to the ten-RSU Manchester incident. That is a warning against retraining before the
  infrastructure topology and causal intervention are correct.

**[CODE_VERIFIED_IMPLEMENTATION]** The data package contains no corrected reject/ledger, LB or Kubernetes-style
campaign output. Its numbers must not be mixed with current-engine results.

# 5. What has actually been reproduced

| Evidence class | Item | Verdict |
|---|---|---|
| REPOSITORY_REPRODUCED_EVIDENCE | TrafficTwin old weekend protocol-seed case, run twice through the bounded old runner | Old pipeline reproducibility demonstrated. |
| REPOSITORY_REPRODUCED_EVIDENCE | Historical `tos-data` master CSV, per-step/per-task arrays and training records | Usable as old-engine historical evidence with its caveats. |
| RANDY_REPORTED_RESULT | `0.75×–40×` waiting-room sweep | Not repository-reproduced; raw evidence missing. |
| MISSING_INFORMATION | Current corrected-engine frozen baseline | No admitted repository output located. |
| MISSING_INFORMATION | Current physical waiting-room sweep | No admitted repository output located. |
| MISSING_INFORMATION | Native strongest-link versus load-aware placement study | No admitted repository output located. |
| MISSING_INFORMATION | Reactive/proactive scaling comparison | No admitted repository output located. |
| MISSING_INFORMATION | Native stale-state study | No implementation/output located. |
| MISSING_INFORMATION | Local untracked runs | Local working trees were outside audit visibility. |

# 6. Contradictions and semantic risks

| Severity | Evidence class | Risk | Required treatment |
|---|---|---|---|
| Critical | CODE_VERIFIED_IMPLEMENTATION | Requested TrafficTwin branch is 271 commits behind main and lacks the new execution path. | Select an authoritative base branch before implementing or running through TrafficTwin. |
| Critical | DIRECT_SUPERVISOR_DIRECTION | Admission ceiling was described as computation power. | Rename and separate admission, service rate, workers and scaling everywhere. |
| Critical | CODE_VERIFIED_IMPLEMENTATION | Old `tos-data` predates physical rejection/work conservation. | Never combine old and current-engine rows in one causal table. |
| Critical | MISSING_INFORMATION | Reported queue-sweep raw outputs/manifests are absent. | Treat numbers as reported only. |
| High | CODE_VERIFIED_IMPLEMENTATION | `completion` is deadline attainment, not necessarily physical completion/return. | Use explicit lifecycle names and denominators. |
| High | CODE_VERIFIED_IMPLEMENTATION | TrafficTwin prototypes validate synthetic structure but not native truth. | Do not promote them to experimental evidence. |
| High | CODE_VERIFIED_IMPLEMENTATION | Current actor chooses only Local/V2I/V2V; exact RSU target is environment-selected. | Describe infrastructure placement as downstream of the actor. |
| High | CODE_VERIFIED_IMPLEMENTATION | Current actor omits RSU load despite computing a load fraction internally. | Freeze actor for infrastructure experiments; retrain only as a separate ablation. |
| High | CODE_VERIFIED_IMPLEMENTATION | DLA changes admission feasibility as well as target selection. | Do not call every DLA comparison a pure placement effect. |
| High | CODE_VERIFIED_IMPLEMENTATION | Simulated scaling is not an actual Kubernetes deployment. | Use “reactive Kubernetes-style resource-scaling simulation.” |
| High | INFERENCE | Two-RSU training versus ten-RSU incident evaluation can alter learned strategy. | Report topology as a transfer factor and avoid causal claims about traffic matching alone. |
| Medium | CODE_VERIFIED_IMPLEMENTATION | `rsu-cap-per-veh` scales with `maxN`, which differs strongly across traces. | Run the absolute-cap sensitivity. |
| Medium | CODE_VERIFIED_IMPLEMENTATION | P2C is stochastic while JSQ/deadline-aware rules can be deterministic. | Predeclare controller RNG seeds and keep P2C secondary. |
| Medium | CODE_VERIFIED_IMPLEMENTATION | Current backhaul model is simple one-hop delay without bandwidth/loss/energy. | Bound claims and run sensitivity rather than claim realistic networking. |
| Medium | CODE_VERIFIED_IMPLEMENTATION | `docs/REPRODUCING.md` says traces are not shipped, while the pinned tree contains Manchester trace files. | Correct documentation before release/reproduction handoff. |
| Medium | MISSING_INFORMATION | Local SUMO was documented as 1.27.1 while canonical evidence says 1.27.0. | Either reproduce in 1.27.0 or run/version a compatibility check. |
| Medium | INFERENCE | Millions of tasks within one run are not independent replications. | Use run/seed as the replication unit; retain temporal diagnostics without pseudo-replication. |

# 7. Ranked experiment matrix

**Common reporting contract for all applicable experiments**

1. `completion_offered = deadline_success / offered_tasks` is the headline deadline metric.
2. `completion_admitted = deadline_success / admitted_tasks` is reported only as a conditional diagnostic.
3. Report `offered`, `admitted`, `rejected`, and rejection reason counts, with
   `offered = admitted + rejected`.
4. Under physical sequential/reject semantics, report work conservation with an explicit unit and identity.
5. Keep physical execution, result return, and deadline attainment separate. A deadline-met flag is not
   automatically evidence of physical completion and return.
6. Report mean, median, p95 and p99 latency for admitted/served tasks; report deadline-met latency separately.
   Do not make rejected work look artificially fast by assigning it zero latency.
7. Report T1/T2/T3 completion, Local/V2I/V2V decision shares, and energy both per offered task and per admitted
   task.
8. For placement studies, report ingress RSU, execution RSU, forwarding count, forwarding delay, forwarding
   energy/cost, and refusal reason.
9. For scaling studies, report mean multiplier, core-seconds or equivalent service-budget denominator, scale
   event count, first scale-up time, and time at every multiplier.
10. Every result must bind code commit, data/trace checksum, actor checksum, environment versions, SUMO version,
full command/manifest, evaluator seed, fleet seed, training seed where relevant, and output checksums.

| Rank | Experiment ID | Research question | Hypothesis | Independent variable | Controlled variables | Scenario and evaluation window | Vehicle actor/checkpoint | Infrastructure controller | Required retraining | Seeds | Primary outcome | Secondary metrics | Required code changes | Implementation readiness | Estimated compute cost | Expected scientific value | Major confounders | Failure criteria | Evidence required for acceptance | Supervisor alignment | Priority |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | E0 — corrected reference and ledger gate | Can the frozen actor be evaluated on the pinned Manchester incident trace under current physical admission semantics with complete task/work conservation and stable provenance? | Sequential queue updates plus reject semantics will conserve offered tasks/work and may change the legacy completion/latency interpretation even with no load balancing or scaling. | None for the reference; semantics fixed to `substep-queue=sequential`, `veh-queue=conserved`, `rsu-cap-mode=reject`. | Actor, trace, fleet, cap, RSU placement, backhaul, scaling, task RNG, fleet draw and SUMO identity. | Manchester incident, 15 March 2024, 20:00–21:00; weekend ordinary cell as one control after the incident gate. | Frozen Paper-2A 17D MAPPO seed-100 actor; exact SHA/MD5 recorded before launch. Add ukfleettrain seed-100 only as a later actor sensitivity. | Existing strongest/best-link target; LB off; fixed 1× compute; no forwarding intervention. | No. | Smoke: evaluator seed 0, fleet seed 0. Accepted reference: fleet seeds 0–4 with evaluator seed fixed and disclosed; retain raw per-seed rows. | Task/work conservation and completion over all offered tasks. | Admitted completion, rejection reasons, class completion, mean/p50/p95/p99 latency, deadline-met latency, energy denominators, action shares. | None in current `vec_env`; TrafficTwin runner/allowlist must be upgraded or bypassed for this gate. | Immediately feasible by invoking current `vec_env` directly; not feasible through the requested TrafficTwin branch's old runner contract. | Smoke is low. Historical old-engine incident evidence was about 3 CPU-hours for one full seed; use that only as a planning anchor. | Essential validity gate. Prevents every later comparison from resting on silent loss or denominator ambiguity. | SUMO 1.27.0 versus locally documented 1.27.1; actor identity drift; legacy versus current engine; unrecorded local files. | Any conservation mismatch, missing denominator, unknown actor/trace identity, non-deterministic rerun without explanation, or incomplete drain/terminal accounting. | Raw JSON/NPZ, manifest, checksums, environment record, conservation assertions, repeated seed-0 check, and per-seed table. | Directly supports the requested accounting correction and frozen-actor baseline. | ESSENTIAL |
| 2 | E1 — waiting-room semantic sweep | Was the reported low-capacity latency improvement a fail-fast artifact, and how do legacy clamp and physical reject semantics differ? | Lower admission ceilings will increase explicit rejection and may reduce admitted-task latency, while completion over offered tasks will decline or reveal previously hidden lost work. | Admission ceiling (pilot: 0.75×, 2.5×, 40×; expand only if useful) crossed with legacy clamp versus physical reject semantics. | Same E0 actor, trace, fleet draws, task RNG, LB off, fixed 1× compute, backhaul and RSU placement. | Incident hour primary; one ordinary control cell at selected cap points. | Same exact frozen actor as E0. | Strongest/best-link; no LB; no scaling. | No. | Fleet seeds 0–4; evaluator seed fixed/disclosed. Use identical seed pairs across every cell. | Completion over offered tasks and rejection fraction. | Admitted completion, latency tails, work loss/conservation, rejection reason, per-class effects, energy/action shares. | No evaluator change for aggregate study; add explicit campaign manifest and legacy-loss diagnostic to the analysis. | Ready in current evaluator. Exact reproduction of Randy's reported numbers is blocked by missing raw manifest and identities. | Three caps × two semantics × five draws is roughly 30 full runs; about 90 CPU-hours if the old incident runtime remains representative. | High. It resolves the original causal misunderstanding and can turn a misleading pilot into a defensible negative/measurement result. | Legacy clamp is not a physical system; cap scales with padded fleet size in per-vehicle mode; latency denominator; drain policy. | Reporting latency without rejection, mixing legacy and physical semantics, or treating unchanged admitted completion as unchanged service quality. | Full cap table, raw outputs, offered/admitted/rejected identities, conservation rows, paired deltas and exact legacy reproduction inputs. | Directly addresses Sandra's correction. | ESSENTIAL |
| 3 | E2 — deterministic execution-RSU placement | With the vehicle actor frozen, does load-aware infrastructure placement improve offered-task outcomes over strongest-link targeting? | JSQ or deadline-aware placement will reduce concentrated RSU overload in the incident cell, but benefit will be limited in ordinary traffic and can disappear when forwarding cost is high. | Placement policy: strongest-link/LB-off, JSQ, deterministic deadline-aware placement; P2C and DLA-P2C as secondary stochastic variants. | Physical queue semantics, fixed 1× compute, same actor/tasks/traces/seeds/cap/backhaul assumptions. | Incident hour primary plus weekend ordinary control. | Frozen 17D MAPPO seed-100 actor. | Current `vec_env` LB modes. The TrafficTwin least-loaded/earliest-completion prototype is not used as native evidence until connected to evaluator state. | No. | Fleet seeds 0–4. P2C additionally needs declared controller RNG sensitivity on the incident cell. | Offered-task completion difference versus strongest-link. | Per-RSU load imbalance, rejection, tail latency, forwarding, class completion, energy, action shares, conservation. | Add native ingress/execution/forwarding counters and costs; optionally adapt the provisional TrafficTwin event contract. | Policies are implemented; complete placement evidence is not, because forwarding/path output is incomplete. | High: at least three deterministic policies × two cells × five draws, plus optional P2C. | Very high and central to the MSc contribution: isolates infrastructure scheduling without retraining the actor. | DLA includes an admission rule as well as placement; P2C is stochastic; current actor was trained with a two-RSU topology; remote state is fresh in current code. | No path-level evidence, policy comparisons with different tasks/seeds, or claiming placement benefit from admitted-only completion. | Matched run manifests, path events, per-RSU time series, paired per-seed effects, null/harm cases, and common-information proof. | Directly aligned with deterministic infrastructure load balancing. | ESSENTIAL |
| 4 | E3 — forwarding/backhaul sensitivity | At what forwarding cost does load-aware placement stop helping? | Placement benefit will shrink monotonically with added forwarding delay; urgent T1/T3 tasks will lose benefit before T2. | Backhaul delay (recommended 0, 2, 5, 10 ms; add 20 ms only if the crossover is not observed). | Best deterministic placement from E2, same cap, fixed 1× compute, actor, traces and seed pairs. | Incident hour; ordinary control only at 0 and the nominal 2 ms. | Same frozen actor. | Selected deterministic placement plus strongest-link comparator. | No. | Fleet seeds 0–4. | Offered completion delta versus strongest-link as a function of backhaul. | Forwarded count, added latency/energy, class-specific crossover, tail latency, rejection and conservation. | Forwarding count/cost instrumentation; delay flag already exists. | Delay is ready; evidence fields need a small instrumentation patch. | Medium–high: four delays × two policies × five draws on the incident cell. | High. Prevents a free-network assumption from making the dispatcher look artificially strong. | Current model assumes full-mesh, one-hop, no bandwidth contention/loss and no forwarding energy unless instrumented. | Using delay without recording which tasks forwarded, or generalising beyond the modelled network assumptions. | Path-level forwarding evidence, explicit network model, paired curves and confidence intervals. | Strongly aligned with the supervisor's mechanism question. | ESSENTIAL |
| 5 | E4 — fixed, static and reactive compute scaling | Does actual compute-service scaling improve outcomes beyond placement and admission control? | Static 3× and reactive scaling will improve incident offered completion, but reactive benefit depends on actuation delay and may spend fewer core-seconds than static 3×. | Fixed 1×, static 3×, reactive Kubernetes-style scaling. | Physical queue semantics, fixed placement policy for the main effect, actor, trace, seeds and admission ceiling. | Incident hour primary; one ordinary cell to measure unnecessary scaling. | Same frozen actor. | Scaling controller only; first keep placement fixed, then run one selected placement × scaling interaction. | No. | Fleet seeds 0–4. | Offered completion per core-second/service-budget unit. | Latency tails, rejection, mean multiplier, time at multiplier, scale events, first-up time, energy and class completion. | Aggregate controls exist; add/derive exact time-at-capacity and explicit resource denominator. | Ready for aggregate pilot in current evaluator. | Medium–high: three modes × five draws; interaction adds selected cells. | High if resource cost is reported; otherwise it is merely 'more compute helps'. | Simulated multiplier is not a real Kubernetes deployment; placement interaction; scale-down semantics; no monetary/resource price. | Calling the simulation Kubernetes load balancing, omitting resource use, or changing placement simultaneously in the main-effect comparison. | Scaling timeline, core-seconds, events, matched outputs and explicit 'Kubernetes-style simulation' wording. | Directly aligned with AI-based/reactive infrastructure control, scoped honestly. | STRONG EXTENSION |
| 6 | E5 — remote-state staleness | How robust is load-aware placement when remote RSU state is delayed? | Fresh-state load balancing helps under concentrated overload, but benefit degrades and can become harmful at 500–1000 ms staleness. | Remote placement-state age: 0, 100, 500, 1000 ms. | Local admission remains fresh; same actor, tasks, cap, placement algorithm, backhaul and compute mode. | Incident hour primary; selected ordinary control. | Same frozen actor. | Best deterministic placement from E2. | No. | Fleet seeds 0–4. | Offered completion degradation versus fresh state. | Wrong-target rate relative to fresh oracle, rejection, forwarding, load imbalance, latency tails and class effects. | Implement a delayed remote-state buffer with exact timestamp/age provenance; current evaluator has no staleness control. | Not implemented; bounded extension after E2. | Medium once implemented: four ages × five draws. | Very high as a mechanism/condition-map result and stronger than merely adding a complex model. | Do not stale local admission state; distinguish telemetry age from Kubernetes actuation delay; preserve identical tasks. | No verifiable delayed snapshot, mixing state delay with actuation delay, or changing local admission semantics. | Snapshot timestamps, age distributions, fresh-oracle comparison, matched outputs and tests. | Strongly aligned with the documented stale-state concern. | STRONG EXTENSION |
| 7 | E6 — fleet-scaled versus absolute admission limits | Does a per-vehicle ceiling create misleading cross-trace comparisons compared with an absolute RSU limit? | Fleet-scaled caps partly track padded/max fleet size and can hide overload differences; absolute limits will expose trace-specific demand more clearly. | Cap mode: per-vehicle scalar versus matched absolute cap. | Same effective cap at a reference trace, actor, placement off, fixed 1× compute, physical semantics and seeds. | Incident plus at least one ordinary cell with different maxN. | Same frozen actor. | Strongest-link; no scaling. | No. | Fleet seeds 0–4. | Cross-trace offered completion and rejection under transparent capacity definitions. | Latency, admitted fraction, work conservation, cap per RSU and class completion. | None; both flags exist. | Ready. | Medium. | Moderate–high methodological contribution; improves comparability and removes a major confound. | Matching absolute and scaled limits requires an explicit reference; maxN is not simultaneous active fleet size. | Equating cap values without documenting conversion or comparing traces with different effective physical capacities. | Conversion table, raw cap fields, matched seeds and sensitivity plots. | Supports the supervisor's request to separate capacity concepts. | STRONG EXTENSION |
| 8 | E7 — scaling actuation-delay sensitivity | How much of reactive scaling's benefit survives realistic actuation delay? | Reactive scaling approaches static 3× at very short delay but loses incident benefit as delay increases. | Actuation delay, recommended 0, 5, 15, 30 and 60 s. | Reactive thresholds/sync/stabilization, placement, cap, actor, trace and seeds. | Incident hour. | Same frozen actor. | Reactive scaling; static 3× and fixed 1× retained as bounds. | No. | Fleet seeds 0–4. | Offered completion and resource-normalized benefit versus delay. | First-up time, missed demand before actuation, scale events, core-seconds and latency tails. | None for delay flag; analysis must derive resource timeline. | Ready after E4. | Medium–high. | Moderate–high, especially if it identifies a delay threshold. | Controller sync and stabilization also impose delay; do not vary them simultaneously. | Changing multiple controller parameters at once or omitting resource cost. | Predeclared delay grid, scale timelines, matched bounds and raw manifests. | Strong extension of reactive infrastructure control. | STRONG EXTENSION |
| 9 | E8 — proactive load forecasting for scaling | Does forecasting future RSU load improve downstream control beyond reactive scaling and static overprovisioning? | Persistence/EWMA may capture most useful signal; a more complex model is justified only if it improves completion/resource trade-offs on held-out windows. | Persistence, moving average/EWMA, regularized regression or gradient boosting, reactive, static 3× and oracle future load. | Same scaling policy wrapper, feature availability, forecast horizon, actor, placement, traces and seeds. | Chronological train/validation/test split across ordinary/event windows; incident retained as held-out stress test where feasible. | Frozen actor. | Forecast-driven capacity controller. | Forecast model training only; no vehicle actor retraining. | Model seeds declared; evaluation fleet seeds 0–4. | Downstream offered completion per core-second, not forecast error alone. | MAE, calibration/interval coverage, scale events, latency, rejection and oracle gap. | Forecast controller and leakage-safe dataset pipeline are absent. | Not implemented; begin only after E4/E7 show a reactive-delay problem worth predicting. | Medium for simple models, high for a broad controller grid. | Potentially high, but easy to overscope. | Prediction accuracy is not control benefit; temporal leakage; oracle information; capacity/placement interactions. | Complex model without beating persistence/EWMA downstream, leakage, or reporting forecast metrics as scheduling benefit. | Frozen splits, feature contract, simple baselines, downstream paired results, oracle bound and model artifact hashes. | Aligned as a later proactive-control extension. | OPTIONAL / GATED |
| 10 | E9 — load/capacity/age-aware vehicle actor | Does exposing infrastructure state to the vehicle actor improve decisions beyond a frozen actor plus downstream dispatcher? | A load-aware actor may reduce infeasible V2I choices, but a downstream deterministic dispatcher may capture most benefit more cheaply and robustly. | Original 17D observation versus a predeclared load/capacity/telemetry-age observation contract. | Training budget, reward, algorithm, training distribution, actor selection rule, evaluation traces and infrastructure controller. | Training distribution plus held-out Manchester ordinary/event/incident cells. | New multi-seed MAPPO actors versus frozen seed-100 baseline. | Compare with strongest-link and best deterministic downstream dispatcher. | Yes. | At least five training seeds; checkpoint selection rule fixed before evaluation; five fleet draws per held-out cell. | Held-out offered completion versus frozen actor plus dispatcher. | Strategy shares, rejection, latency, energy, calibration to load, seed stability and training cost. | Observation schema, trainer/checkpoint compatibility, evaluation flags, training records and tests. | Not implemented. Current JAX and PyTorch actors do not observe RSU load. | High overall. Historical standard N=40 training was roughly 15–18 minutes per seed on A100-class hardware, but evaluation dominates and hardware provenance must stay separate. | High only if deterministic infrastructure methods leave a clear residual gap. | Observation-space change, reward change, actor-seed selection, two-RSU training versus ten-RSU evaluation, train/eval contamination. | Single selected seed, unequal budgets, no deterministic baseline, or in-domain fit presented as generalization. | Training records, all seeds/curves/checkpoints, predeclared selection, held-out evaluation and matched infrastructure baselines. | Aligned as a later architecture comparison, not a first experiment. | OPTIONAL / GATED |
| 11 | E10 — learned infrastructure dispatcher | Is a learned execution-RSU policy justified after deterministic placement baselines? | A learned dispatcher is justified only if it improves the completion/resource/robustness trade-off under staleness and forwarding cost beyond JSQ/deadline-aware rules. | Learned dispatcher versus strongest-link, JSQ, P2C and deadline-aware deterministic policies. | Frozen vehicle actor, common candidate information, task streams, seeds, reward and compute budget. | Held-out incident/event/ordinary conditions with staleness/backhaul sweeps. | Frozen actor. | Second-stage learned execution-RSU policy. | Yes, infrastructure policy only. | At least five training seeds plus matched evaluation seeds. | Held-out offered completion/resource trade-off versus strongest deterministic baseline. | Robustness to staleness, forwarding, rejection, latency, training stability and inference cost. | Environment/API for dispatcher training, reward, replay/evaluation and policy artifacts. | Not implemented; the TrafficTwin deterministic study is synthetic structural software, not a learned scheduler. | High. | Potentially high but unnecessary unless deterministic baselines are inadequate. | Reward shaping, common-information fairness, overfitting, actor/dispatcher non-stationarity and selected-seed bias. | No deterministic comparator, no held-out conditions, or marginal gain without cost/robustness benefit. | All training seeds, common-information contract, held-out matched results, ablations and artifact hashes. | Aligned with Sandra's learned scheduling idea, explicitly gated. | OPTIONAL / GATED |
| 12 | E11 — action masking | Does masking infeasible Local/V2I/V2V choices improve policy quality compared with explicit rejection? | Masking will reduce invalid actions but changes the policy-learning problem and should not be mixed into the infrastructure baseline. | Masked versus unmasked policy under an otherwise identical training/evaluation contract. | Observation, reward, algorithm, budget, training distribution, infrastructure semantics and seeds. | Training distribution plus held-out Manchester cells. | New masked and unmasked actors. | Fixed baseline controller. | Yes. | At least five training seeds and five fleet draws. | Offered completion. | Invalid/rejected action rate, strategy shares, latency, energy and seed stability. | Masking support exists in training; complete campaign/checkpoints and compatibility evidence are missing. | Partially implemented; no accepted current campaign identified. | High due paired retraining and evaluation. | Moderate and separable; not part of the minimum contribution. | Masking changes the action distribution and exploration; it is not merely an evaluator toggle. | Applying a mask only at evaluation, comparing differently trained policies without matched budgets, or bundling it with load balancing. | Paired training records, masks at every training/eval step, all seeds and held-out results. | Separate extension only. | OPTIONAL |

## Statistical analysis rule

**[NEW_RECOMMENDATION]** Use matched per-seed differences as the primary analysis unit. With only five fleet draws,
emphasize raw effects, bootstrap intervals and sensitivity rather than pretending millions of tasks are independent.
An exact paired permutation test with five pairs has coarse resolution, so a null p-value must not erase a practically
meaningful effect. Predeclare the actor, cap, policy, seed pairs, primary metric and stopping rule.

# 8. Recommended minimum viable research contribution

**[NEW_RECOMMENDATION]**

The minimum dissertation contribution should contain four admitted components:

1. **Corrected semantic contract and E0 reference:** offered/admitted/rejected accounting, physical reject semantics,
   work conservation and complete provenance.
2. **E1 queue-semantic result:** show exactly why low waiting-room capacity can create a fail-fast latency appearance.
3. **E2 deterministic placement result:** frozen actor; strongest-link versus transparent load-aware placement on the
   incident cell and one ordinary control.
4. **E3 forwarding sensitivity:** identify the condition under which placement benefit disappears.

E4 fixed/static/reactive scaling is the first add-on if compute permits.

A defensible contribution statement would be:

> This study separates vehicle offloading choice, RSU admission, execution-RSU placement and compute scaling, then
> evaluates them under matched Manchester mobility traces using explicit rejection and conservation. It identifies
> when load-aware infrastructure control improves deadline attainment over all offered tasks and when rejection,
> forwarding cost or stale state removes that benefit.

Do not claim “Kubernetes load balancing” unless an actual Kubernetes deployment is built. For the current evaluator,
use “Kubernetes-inspired” or “Kubernetes-style reactive resource scaling.”

# 9. Stronger extension if time permits

**[NEW_RECOMMENDATION]**

The strongest extension is **E5 stale-state sensitivity**, not an LLM or a large neural controller. It directly tests
whether the information required by a load-aware dispatcher remains useful at realistic age. Combine it with the
best deterministic placement and report a condition map over traffic regime, backhaul and telemetry age.

Only after E2/E5 establish a residual decision problem should the project attempt:

1. E8 proactive forecasting, beginning with persistence and EWMA;
2. E9 load-aware actor retraining; or
3. E10 a learned infrastructure dispatcher.

A complex model that fails to beat JSQ/deadline-aware placement under held-out conditions is still a valid negative
result, but it should not consume the first week.

# 10. Independent bus-thread recommendation

**[NEW_RECOMMENDATION]** Keep the Manchester bus prediction thread alive as a **parallel feasibility track**, not the
primary dissertation claim yet.

The focused question is:

> Do recent bus trajectories plus admitted traffic/event information improve short-horizon corridor travel-time and
> severe-delay prediction beyond persistence and historical time-of-day baselines?

First-stage models should be persistence, historical median, moving average/regularized regression and gradient
boosting. Use chronological splits, source-ablation, freshness/dropout tests and calibrated uncertainty. An LLM may
coordinate validated sources or explain already-computed predictions, but must not generate the numerical forecast.

**Switch-primary gate:** reconsider making the bus thread primary only if (a) the VEC native-evidence/ownership block
remains unresolved after the first bounded coordination cycle and (b) the bus audit confirms sufficient repeated
trajectories, labels, geographic overlap, legal use and a leakage-safe held-out test. Until both conditions hold,
the VEC study remains the supervisor-aligned primary thread.

# 11. Missing-information register

## 11.1 Hard blockers before a full scientific campaign

| ID | Evidence class | Missing item | Why it blocks | Owner/request |
|---|---|---|---|---|
| H1 | MISSING_INFORMATION | Authoritative TrafficTwin execution base: requested diverged branch, current main, or prototype tip | Changes code availability and provenance | Abdulla + repository owner: choose and record base/merge strategy |
| H2 | MISSING_INFORMATION | Signed/predeclared first-campaign manifest | Without actor, trace, flags, seeds and outputs, E0 cannot be an accepted reference | Abdulla; review with Randy |
| H3 | MISSING_INFORMATION | Confirmed environment and SUMO version for current engine | 1.27.0/1.27.1 drift can invalidate exact reproduction | Randy/Abdulla |
| H4 | MISSING_INFORMATION | Native forwarding/path and physical-return evidence boundary | Required before claiming scheduler execution benefit rather than selection/projection | Randy + implementation owner |
| H5 | MISSING_INFORMATION | CSF3 access, partition/quota and durable output location | Required for a five-seed/full-hour matrix at practical wall-clock | Sandra/Randy/CSF owner |
| H6 | MISSING_INFORMATION | Local `git status`, untracked outputs and local result inventory | GitHub absence does not prove local absence | Abdulla on the three supplied local paths |

## 11.2 Required to reproduce Randy's reported result

| ID | Evidence class | Missing item |
|---|---|---|
| R1 | MISSING_INFORMATION | Raw sweep JSON/CSV and any per-task/per-step sidecars |
| R2 | MISSING_INFORMATION | Exact command or SLURM manifest for every cap point |
| R3 | MISSING_INFORMATION | Exact cap grid and whether values were per-vehicle or absolute |
| R4 | MISSING_INFORMATION | Actor filename plus checksum and training identity |
| R5 | MISSING_INFORMATION | Trace checksum/window, fleet preset and fleet seed(s) |
| R6 | MISSING_INFORMATION | Evaluator/task RNG seed(s) and P2C/controller seed if relevant |
| R7 | MISSING_INFORMATION | vec_env/tos-data commits and environment/SUMO versions used |
| R8 | MISSING_INFORMATION | Definition of completion, latency denominator, drain horizon and rejection treatment |
| R9 | MISSING_INFORMATION | Full numerical table, not only the two endpoints |

## 11.3 Required for new supervisor experiments

| ID | Evidence class | Missing item |
|---|---|---|
| N1 | MISSING_INFORMATION | Approved first deterministic comparator: current JSQ/deadline-aware code or integrated TrafficTwin least-loaded/earliest-completion prototype |
| N2 | MISSING_INFORMATION | Exact service-rate/core semantics and a separately controlled compute-speed parameter |
| N3 | MISSING_INFORMATION | Forwarding network assumptions: delay, bandwidth, energy, loss and reachability |
| N4 | MISSING_INFORMATION | Remote-state staleness producer/buffer and timestamp contract |
| N5 | MISSING_INFORMATION | Resource-cost denominator for static/reactive scaling |
| N6 | MISSING_INFORMATION | Tail-latency and path-event output schema for the current engine |
| N7 | MISSING_INFORMATION | Supervisor-approved essential cell set and campaign deadline |

## 11.4 Required for multi-seed retraining

| ID | Evidence class | Missing item |
|---|---|---|
| T1 | MISSING_INFORMATION | Frozen load/capacity/age observation schema and normalization |
| T2 | MISSING_INFORMATION | Reward and masking contract |
| T3 | MISSING_INFORMATION | Training seed set, checkpoint selection rule and equal-budget protocol |
| T4 | MISSING_INFORMATION | GPU allocation and storage for all seeds/curves/checkpoints |
| T5 | MISSING_INFORMATION | Held-out topology/trace matrix and contamination labels |
| T6 | MISSING_INFORMATION | Availability of non-selected baseline actor seeds for actor-seed sensitivity |

## 11.5 Coordination and ownership

| ID | Evidence class | Missing item |
|---|---|---|
| C1 | MISSING_INFORMATION | Ethan's exact branch, experiment ownership and current outputs |
| C2 | MISSING_INFORMATION | Who may modify/review the authoritative `vec_env` evaluator |
| C3 | MISSING_INFORMATION | Who owns native lifecycle/path instrumentation |
| C4 | MISSING_INFORMATION | Where campaign manifests/results are committed and who admits them |
| C5 | MISSING_INFORMATION | Authorship/data-governance boundary for Randy-originated assets |
| C6 | MISSING_INFORMATION | Sandra's expected dissertation deliverable and decision date |

## 11.6 Useful but non-blocking

- Formal versioned schema for the current evaluator JSON/NPZ.
- Corrected documentation about whether traces ship in `vec_env`.
- Public/dissertation publication permission for any new raw or derived VEC artifact.
- Complete FCD-replay training record for every historical variant referenced by the data dictionary.
- Bus-source licence, retention, temporal depth, geographic overlap and target-label audit.
- Hardware-specific runtime benchmark for the current corrected engine.

# 12. Exact questions for Sandra

1. Is the primary MSc question the frozen vehicle actor plus infrastructure-side scheduling, with actor retraining and
   a learned dispatcher treated as gated extensions?
2. Which deliverables are mandatory for the dissertation: corrected queue accounting, deterministic placement,
   static/reactive scaling, proactive forecasting, or all of them?
3. Is one incident trace plus one ordinary control trace acceptable for the core causal study, provided five matched
   fleet draws and complete provenance are reported?
4. Do you agree that completion over **all offered tasks** is the primary metric, with admitted-task completion only a
   conditional diagnostic?
5. Do you require physical execution-and-return instrumentation, or is the current modelled deadline outcome
   acceptable if its limitation is stated explicitly?
6. Which frozen actor should be primary: the Paper-2A seed-100 baseline, the UK-fleet-trained seed-100 actor, or both?
7. Should the current scaling simulation be described as “Kubernetes-inspired/Kubernetes-style” unless an actual
   Kubernetes deployment is built?
8. Is stale remote RSU state a required core factor or a stronger extension after deterministic placement?
9. May the Manchester bus prediction thread proceed as a parallel feasibility/contingency study?
10. What exact artifact and deadline do you expect at the end of the next seven days?

# 13. Exact questions for Randy

1. Please provide the raw JSON/CSV for the `0.75×–40×` waiting-room sweep and the exact command/SLURM manifest.
2. Which actor/checkpoint and checksum, trace/checksum, fleet preset, fleet seeds and evaluator seeds produced the
   reported `0.6943` completion and `4.9→128.4 s` latency values?
3. Which `vec_env` and `tos-data` commits, Python/JAX versions and SUMO version were used?
4. Was the sweep run under legacy clamp/snapshot semantics or physical sequential/reject semantics?
5. Was completion calculated over offered tasks or admitted tasks, and how were rejected/lost tasks handled?
6. What exact latency population was averaged, and was the queue drained after the one-hour trace?
7. Does `rsu_max_concurrent` include waiting plus executing tasks, and is it applied independently per RSU?
8. What is the separately configurable compute service-rate/core parameter, and exactly how does the Kubernetes-style
   multiplier change service budget?
9. Which RSUs are eligible after a V2I action, how is ingress selected, and how are ties handled?
10. Can the current evaluator emit stable per-task IDs for offered, admitted/rejected, ingress, execution RSU,
    forwarded/retained, start, compute completion, return and terminal/deadline status?
11. Is the nominal backhaul assumption still 2 ms, one hop, full mesh, with no bandwidth/loss/energy? Which deviations
    should the MSc study test?
12. For P2C, which RNG seed protocol should be used? For deterministic policies, should evaluator seed remain fixed
    while fleet seed runs 0–4?
13. Which corrected-engine comparison do you regard as canonical: LB off/JSQ/P2C/DLA/DLA-P2C, and what exactly does
    DLA change beyond placement?
14. Can Abdulla use CSF3 now; which CPU/GPU partition, quota, storage path and maximum array concurrency are approved?
15. Which current work belongs to Ethan, and where should duplicate effort be avoided?
16. Which new outputs may be committed or used in the dissertation, and what attribution/publication restrictions
    apply?

# 14. Exact coordination questions for Ethan

1. Which repository, branch and commit are you currently using?
2. Are you implementing admission accounting, execution-RSU placement, scaling, forecasting, lifecycle events or
   analysis?
3. Which experiments have already run, and where are their raw manifests and outputs?
4. What exact controller definitions and metric denominators are you using?
5. Can we divide ownership so one person owns native lifecycle/path instrumentation and the other owns the matched
   experiment/analysis?
6. Which files or APIs should remain stable to avoid duplicate incompatible implementations?
7. Who will review and merge the authoritative evaluator changes?
8. What result naming, output storage and checksum convention will both of us use?
9. Which findings are exploratory versus admitted dissertation evidence?
10. What is your expected completion date and what dependency do you need from Abdulla?

# 15. Seven-day execution plan

## Day 1 — freeze the experiment identity

- Record authoritative branch/commit decisions.
- Send the Sandra/Randy/Ethan questions.
- Inventory local working trees with `git status`, branches, untracked result directories and actor/trace checksums.
- Write the E0 manifest before running.
- Build the canonical SUMO 1.27.0 environment or document a deliberate 1.27.1 compatibility test.
- Run only a bounded `--max-steps` smoke under physical semantics.

**Exit condition:** command, inputs, outputs and conservation fields are complete; no silent work loss.

## Day 2 — full corrected reference

- Run E0 incident seed-0/fleet-0.
- Repeat the same identity once to verify deterministic/stable output.
- Validate offered/admitted/rejected and work conservation.
- Confirm whether the current output can support tail latency and path evidence; implement only the smallest missing
  instrumentation.

**Exit condition:** one accepted current-engine reference candidate.

## Day 3 — queue-semantic pilot

- Run E1 at 0.75×, 2.5× and 40× under legacy and physical semantics for seed-0/fleet-0.
- Produce the first table showing offered/admitted/rejected, offered completion, admitted completion and latency.
- Do not launch the full grid if the pilot exposes a semantic or provenance defect.

**Exit condition:** decision on the final cap grid and whether the reported result is reproducible.

## Day 4 — multi-draw core queue study

- If CSF3 parallel capacity is available, run fleet seeds 0–4 for the selected cap grid.
- Add one ordinary control at the most informative cap points.
- If compute is unavailable, finish the complete seed-0 pilot and queue the predeclared multi-draw campaign rather
  than pretending one seed is conclusive.

**Exit condition:** admitted multi-draw E1 outputs or a fully ready campaign manifest.

## Day 5 — native placement evidence

- Validate the two-RSU strong-link-full/weaker-idle case against current evaluator state.
- Add ingress/execution/forwarding counters if absent.
- Run strongest-link, JSQ and deterministic deadline-aware placement for one incident seed.

**Exit condition:** path-level evidence and a matched deterministic pilot.

## Day 6 — placement plus cost

- Run the selected E2 policies across fleet seeds 0–4 if compute permits.
- Run the E3 backhaul pilot at 0, 2 and 10 ms.
- Run a fixed 1×/static 3×/reactive seed-0 scaling pilot only after placement/accounting is stable.

**Exit condition:** first condition-map figure or a documented null/harm result.

## Day 7 — analysis and supervisor decision pack

- Produce paired per-seed tables, uncertainty intervals, conservation audit and provenance appendix.
- Separate observed results from expected mechanisms.
- Write a one-page decision note: MVP complete/in progress, best next extension (staleness versus scaling), blockers and
  compute need.
- Complete the bus-thread feasibility inventory separately; do not mix its data or claims with VEC.

**Realism note:** one historical incident run took about three CPU-hours. A 30-run E1 grid is about 90 CPU-hours if
runtime is similar. The five-seed core is feasible within seven days only with parallel compute; serial local work
should prioritize correctness, the seed-0 pilot and ready-to-launch manifests.

# 16. Reproducibility checklist

- [ ] Authoritative repository branch and full commit for every codebase.
- [ ] Clean/dirty local `git status`; untracked output inventory retained.
- [ ] Full actor filename, checksum, training record and selected-seed disclosure.
- [ ] Full trace filename, checksum, date/window, maxN, RSU placement and SUMO seed.
- [ ] Python, JAX, NumPy, SUMO and OS/container identity.
- [ ] Hardware/partition and wall-clock recorded without pooling unlike machines.
- [ ] Complete command, environment variables and SLURM manifest.
- [ ] Evaluator seed, fleet seed, training seed and controller RNG seed separated.
- [ ] Queue/admission/service/placement/scaling semantics written explicitly.
- [ ] Offered/admitted/rejected task and work identities checked.
- [ ] Drain/terminal policy documented.
- [ ] Metric denominators and unavailable metrics written into the schema.
- [ ] Tail-latency and class metrics retained.
- [ ] Ingress/execution/forwarding/return path retained for placement claims.
- [ ] Capacity timeline/core-seconds retained for scaling claims.
- [ ] Raw JSON/NPZ/log files immutable and checksummed.
- [ ] Campaign directory and filenames never reused.
- [ ] Analysis plan, primary metric and seed set predeclared.
- [ ] Paired raw rows and null/negative results retained.
- [ ] Train/eval contamination labels for every retrained/FCD model.
- [ ] Publication/attribution permission checked before sharing any private artifact.

# 17. Sources and traceability

## Primary TrafficTwin sources

- `AGENTS.md`
- `SUPERVISOR_RESEARCH_DIRECTION.md`
- `docs/research_start_2026-08-07.md`
- `docs/randy_email_research_analysis_2026-08-07.md`
- `docs/msc_students_qna_research_record_2026-08-05.md`
- `docs/implementation-status.md`
- `docs/traffictwin-design-v0_7.md`
- `docs/current_progress_v0_7.md`
- `docs/integration/vec_end_to_end_research_artifact.md`
- `docs/integration/randy-source-snapshot-audit-v0_6.md`
- `docs/integration/vec_evaluator_runner.md`
- `docs/integration/vec_reproduction_verification.md`
- `docs/integration/vec_scientific_admission.md`
- `docs/experiment_protocol.md`
- `docs/statistical_studies.md`
- `docs/reproducibility.md`
- `src/traffictwin/integration/vec_runner/models.py`

## TrafficTwin branch/prototype sources

- Branch comparison: `a462c72...` versus requested `ae5b543...`
- `b7bc0cc...` — provisional lifecycle contract
- `ec256ba...` — synthetic two-RSU hand check
- `3b13856...` — deterministic dispatcher
- `9fa1c37...` — native sidecar validator
- `3813431...` — matched synthetic dispatch study
- `a43ce2a.../docs/evaluation/supervisor_meeting_4_and_independent_bus_research_plan.md`

## vec_env sources

- `README.md`
- `docs/DATA_CONVENTIONS.md`
- `docs/REPRODUCING.md`
- `eval/eval_sumo_stage1_mc.py`
- `jaxmarl/env/vec_jax.py`
- `pytorch/env/vec_offloading_env.py`
- `jaxmarl/scripts/train_mappo_vec.py`
- `validation/fidelity_trace_replay.py`
- `validation/gen_forced_actors.py`
- `slurm/README.md`
- Change commits `d4d5dfc`, `e592662`, `4cb7c06`, `eb5ed93`, `df022e6`, `82d3ecf`

Stable code anchors for local line-number verification:

- `eval_sumo_stage1_mc.py`: argument parser; admission/queue setup; LB/DLA routing; queue drain/scaling; JSON output.
- `vec_jax.py`: `process_agent`, `best_rsu_load_frac`, observation construction and action masks.
- `train_mappo_vec.py`: `--use-mask`, actor construction, checkpoint save and greedy evaluation.
- `vec_offloading_env.py`: strongest-channel target selection and 17D observation construction.

## tos-data sources

- `README.md`
- `DATA_DICTIONARY.md`
- `records/DATA_CONVENTIONS.md`
- all eight relevant `TRAINING_*.md` records for UK-fleet, cap-scalar, gridlock and fine-tuned variants
- `traces/PROVENANCE.md`
- `evals/eval_results_master.csv`
- `instrumented/json/baseline_uk2030_inc_fs0.json`
- actor/checkpoint, trace, occupancy, tripinfo and instrumented tree inventory

# Direct answers

**Can research execution begin now?**
**Yes for E0 smoke/reference work and manifest preparation. No for a large accepted campaign until branch authority,
exact first-run identity, environment/compute and metric/path boundaries are frozen.**

**What is the first experiment?**
**E0: the current-engine frozen-actor reference under sequential, conserved, physical reject semantics, with complete
offered/admitted/rejected and work-conservation evidence. E1 is the first causal comparison.**

**What is the main research contribution?**
**A semantics-aware condition map for infrastructure-side RSU scheduling and compute scaling with a frozen vehicle
actor, explicit conservation and offered-task denominators.**

**What information must Abdulla request immediately?**
**Randy's raw sweep/manifests and identities; Sandra's mandatory scope/metric/actor/deadline decisions; Ethan's
ownership/branch/status; CSF3 access and storage; and the authoritative TrafficTwin branch/merge decision.**

**What work can proceed without waiting for replies?**
**Local repository/status inventory, E0 manifest, environment pinning, bounded current-engine smoke, conservation
validation, tail/path instrumentation design, and a separate bus-data feasibility inventory.**

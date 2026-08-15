# Current Status — 5.6 Pro Analysis

**Recorded:** 6 August 2026<br>
**Status:** Owner-supplied external technical analysis, retained as descriptive and non-causal.
It is not supervisor-approved, publication-approved, or cryptographically authenticated as a
model-generated report. Local review reproduced its central admission-clamp counts from
receipt-matched pilot artifacts; the report's percentage-validity scores remain explicitly
subjective expert judgments.

**Supplied-file SHA-256:** `c6b872873bab3205fe44493228d15d90d8270b0aa278a6b5a3b73c8147df5845`

---

# **Technical Audit Report: What Sandra’s Email Gets Right and Wrong**

## **Scope and evidence basis**

I successfully accessed **`Abdulla4akash/traffictwin`**, with the current `main` branch pointing to commit **`49be6a2db8a69409a1b92fb02e954db7cf1441f6`**. TrafficTwin’s runner pins the evaluated external `vec_env` implementation to commit **`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`**, including hashes for `eval/eval_sumo_stage1_mc.py` and `jaxmarl/env/vec_jax.py`.

I treated Sandra’s email, Agent 1’s Opus analysis and Agent 2’s Codex analysis as competing interpretations, rather than deciding by majority agreement. That follows the audit framework you supplied.

One evidence limitation matters: the private upstream repository and the raw local pilot NPZ files were not directly available to me in this environment. Therefore, exact reconstructed figures such as **1,096,583 versus 1,157,465 non-admissions** are reported from Agent 2’s local artifact analysis rather than independently recomputed here. The broader conclusions about parameter meaning, metric semantics, action space, tail behaviour and missing lifecycle evidence are independently supported by the committed TrafficTwin records.

---

# **A. Executive verdict**

Sandra’s **central correction is correct**: the experiment did not reduce RSU processor speed, computation throughput or service power. It changed a per-RSU limit derived from a per-padded-vehicle scaling factor.

The values `2.5` and `0.75` were not literal queue lengths. On the 2,488-slot incident trace, they became effective per-RSU bounds of **6,220** and **1,866** tasks.

The reported reduction in mean latency was a genuine change in the simulator’s numerical output, but it was **not evidence that computation became faster**. Median latency was unchanged, while the extreme latency tail of tasks already missing their deadlines was compressed.

Sandra is partly right that RSU admission clipping was involved. However, the stronger claim that the result was caused by cleanly recorded **“quick rejection” or “fail fast”** is not established. The evaluator does not provide a complete per-task record distinguishing offered, admitted, rejected, started and physically completed tasks.

The email also incorrectly uses “completion” as though it meant physical task completion. In the reviewed evidence, “completion” means modelled latency within the deadline.

Sandra is right that load-aware RSU management is a sensible research direction. But she overstates what MAPPO decides, what caused the idle-RSU pattern, whether capacity broadcasting is impossible, whether Kubernetes directly performs this kind of task scheduling, whether retraining is unnecessary in general, and whether improvement should occur in both free-flow and congestion.

The strongest overall judgment is:

> **Sandra correctly identified the major interpretation problem and a useful next research direction, but her detailed causal explanation and proposed architecture are considerably more certain than the evidence allows.**

---

# **B. What the experiment actually changed**

## **1\. The configured control**

The experiment varied:

\--rsu-cap-per-veh \= 2.5, 1.5, 1.0, 0.75

The experiment documents define this as a **per-padded-vehicle concurrent-task capacity bound**. They explicitly state that it is not CPU capacity, bandwidth, physical RSU hardware capacity or the number of RSUs.

The effective relation was:

RSU\_MAX\_CONCURRENT<br>
    \= round(rsu\_capacity\_per\_vehicle × padded trace width)

For the incident trace:

padded trace width \= 2,488 slots

2.5 × 2,488 \= 6,220 tasks per RSU<br>
0.75 × 2,488 \= 1,866 tasks per RSU

Therefore, the intervention was:

6,220 → 1,866 maximum admitted/in-flight tasks per RSU

It was not:

2.5 tasks → 0.75 tasks

The pilot design fixed the same trace, actor, fleet, evaluator seed and full 3,600-step duration across capacity arms; only the capacity control changed.

## **2\. Is “queue capacity” accurate?**

“Queue capacity” or “waiting room” is an understandable informal description, but it is incomplete.

A conventional queueing model normally separates:

* work currently executing;<br>
* work waiting for execution;<br>
* number of parallel servers;<br>
* service rate;<br>
* maximum queue length;<br>
* maximum total work in the system.

Here, `RSU_MAX_CONCURRENT` functions more like a combined **admission/in-flight concurrency ceiling**. The source evidence does not establish that it represents only tasks waiting and excludes tasks considered to be executing.

The safest technical term is:

> **Per-RSU admission/in-flight concurrency ceiling.**

Sandra is therefore right that this is not computation power, but calling it purely an administrative waiting-room size is somewhat oversimplified.

## **3\. Did it change computation power?**

No evidence indicates that the experiment changed:

* CPU or GPU frequency;<br>
* cycles processed per second;<br>
* task workload;<br>
* task service-time formula;<br>
* processor count;<br>
* number of service workers;<br>
* RSU service/drain rate;<br>
* network bandwidth;<br>
* or radio transmission rate.

The predeclaration explicitly warned that the control was not CPU capacity or physical RSU hardware capacity.

Therefore:

| Description | Accuracy |
| ----- | ----- |
| “Computational capacity” | Incorrect or materially misleading |
| “Processing power” | Incorrect |
| “RSU CPU capacity” | Incorrect |
| “Edge capacity” | Too vague; easily misinterpreted |
| “Queue capacity” | Partly accurate but simplified |
| “Admission/in-flight concurrency ceiling” | Most accurate |

---

# **C. Claim-by-claim audit of Sandra’s email**

| Email claim | Verdict | Evidence and explanation | Confidence |
| ----- | ----- | ----- | ----- |
| The experiment reduced an RSU queue control rather than computation power. | **Mostly correct** | It did not alter processor/service power. The control is better described as an admission/in-flight concurrency ceiling than a pure waiting queue. | High |
| The value was reduced directly from 2.5 to 0.75 queue places. | **Misleading** | These were scaling values. On this trace they produced 6,220 and 1,866 tasks per RSU. | High |
| The reduced limit caused the RSU to start refusing tasks. | **Partly correct** | Agent 2’s reconstruction reports that the admission clamp bound, but it was already binding at 2.5; it did not suddenly start only at 0.75. | Medium |
| Quick rejection caused the lower latency. | **Plausible but not established** | Backlog clipping is supported. Individual rejection times and properly classified rejected-task outcomes are not recorded. | High |
| This is a “fail-fast” situation. | **Too certain** | Excluding work from a backlog is not automatically a properly measured fail-fast mechanism. | High |
| The lower latency was an accounting effect rather than real improvement. | **Mostly correct** | The mean fell because the extreme already-failed tail was compressed; ordinary successful tasks did not become substantially faster. | High |
| Task completion did not improve. | **Terminologically wrong but directionally reasonable** | The recorded measure is deadline success, not physical task admission, execution and return. | High |
| MAPPO fails to consider capacity. | **Mostly correct for this actor** | The evaluated actor could not observe the varied capacity/load state. This is a limitation of the supplied observation design, not MAPPO generally. | High |
| RSUs do not broadcast capacity because information becomes obsolete. | **Unsupported generalisation** | The inspected evaluator does not provide such broadcasting, but that does not establish a universal property of RSU systems. | Medium |
| The trained model chooses the best available RSU link. | **Misleading** | The policy chooses local/V2I/V2V. Environment logic computes the best-link RSU. | High |
| Congested-road RSUs become overloaded while farther RSUs stay idle. | **Partly supported, partly unproved** | Severe RSU imbalance was measured. The geographical and per-task causal attribution was not established. | High |
| Load management is a worthwhile problem to solve. | **Correct** | The evidence strongly motivates load-aware dispatch or forwarding experiments. | High |
| Kubernetes is the deterministic RSU load-balancing framework needed here. | **Technically inaccurate** | Kubernetes schedules Pods to Nodes and exposes groups of backend Pods; a queue-aware VEC task dispatcher would be an application-level mechanism or custom extension. | High |
| No retraining is required. | **Conditionally correct** | True for a frozen actor plus post-offload forwarding baseline; false if the actor observes load or chooses the execution RSU. | High |
| Completion should improve in free-flow and congestion. | **Unsupported prediction** | The free-flow/event traces were unsaturated and invariant across capacity arms; forwarding could add overhead there. | High |
| A DRL load-balancing model is worth testing. | **Reasonable research direction** | It should follow a corrected deterministic baseline and explicit task accounting. | High |
| “AI-based Kubernetes” is a well-defined next system. | **Too vague** | It needs a specific definition: scheduler plugin, controller, task dispatcher, service-routing policy or something else. | High |

---

# **D. Percentage validity**

These percentages are **structured expert judgments**, not statistical confidence intervals. I divided the email into ten material claims, assigned each a weight based on its importance, and scored factual accuracy using:

1.00 \= correct<br>
0.75 \= mostly correct<br>
0.50 \= partly correct<br>
0.25 \= weakly supported<br>
0.00 \= incorrect

| Material claim | Weight | Factual score | Evidence score | Practical-use score |
| ----- | ----- | ----- | ----- | ----- |
| Control was not computation power | 15 | 1.00 | 1.00 | 0.90 |
| Queue/waiting-room interpretation | 10 | 0.50 | 0.70 | 0.60 |
| Refusal/fail-fast mechanism | 15 | 0.40 | 0.25 | 0.55 |
| Lower mean was not genuine service improvement | 10 | 0.80 | 0.80 | 0.90 |
| Actor lacked capacity awareness | 10 | 0.75 | 0.80 | 0.90 |
| Capacity is not broadcast because it becomes stale | 8 | 0.25 | 0.05 | 0.45 |
| Best-link selection explains overloaded/idle RSUs | 12 | 0.50 | 0.40 | 0.80 |
| Kubernetes as the deterministic solution | 8 | 0.40 | 0.25 | 0.70 |
| No retraining required | 6 | 0.50 | 0.30 | 0.60 |
| Improvement expected in both regimes | 6 | 0.25 | 0.10 | 0.45 |

### **Result**

* **Factual correctness of the email: 57%**<br>
* **Strength of evidence supporting the email as written: 51%**<br>
* **Practical usefulness of the proposed direction: 71%**

The distinction is important. The email is not highly reliable as a literal technical account, but it is substantially more useful as a **research redirection**: stop treating this control as compute power, repair the accounting and study RSU load management.

---

# **E. Where Sandra is right**

## **1\. The original shorthand was misleading**

Your earlier sentence used:

> “tightening per-vehicle edge capacity”

That phrase strongly suggests reduced computation resource or processing throughput. The experiment documents were more precise: the variable was a per-padded-vehicle concurrent-task bound and not physical computational capacity.

Sandra is therefore justified in correcting the external interpretation.

The experiment itself was not necessarily executed contrary to its predeclaration. The problem was that the result was later summarised using language that was too broad and invited a compute-power interpretation.

## **2\. The latency reduction should not be presented as faster computing**

The repository’s latency-tail analysis found:

* p50 stayed approximately **44.3 ms** across all capacity arms;<br>
* the proportion exceeding one second changed very little;<br>
* p99 fell from approximately **99.9 seconds to 30.0 seconds**;<br>
* roughly **97.9–99.4%** of latency mass came from the extreme tail.

That means the ordinary task population did not become broadly faster. The dominant change was that tasks already far beyond their deadlines accumulated less extreme modelled backlog.

This supports Sandra’s main scientific concern:

> A reduction in raw mean latency did not demonstrate better edge-computing performance.

## **3\. Queue/admission clipping is involved**

Agent 2 reports reconstructing the admission boundary across all three pilot seeds:

cap 2.5:<br>
1,096,583 of 5,973,330 eligible V2I tasks not admitted<br>
\= 18.36%

cap 0.75:<br>
1,157,465 of 5,973,330 eligible V2I tasks not admitted<br>
\= 19.38%

It also reports that saved `rsu_load` was post-drain, so observing stored load slightly below the ceiling did not prove that the pre-drain admission limit never bound.

Assuming that reconstruction is correct, Sandra is substantially right that the admission ceiling affected how much work entered the RSU backlog.

However, notice that the baseline already showed substantial clipping. Lowering the ceiling added **60,882** reported non-admissions; it did not create refusal from nothing.

## **4\. The evaluated actor could not adapt to capacity**

The keyed-action comparison found complete action identity across capacity arms within each seed. The observation-gap analysis concluded that RSU-side state changed while policy-visible vehicle-side state remained identical.

So Sandra is right in practical terms that the evaluated policy was not capacity-aware.

The precise wording should be:

> The evaluated MAPPO actor was given an observation space that did not expose the changed RSU capacity/load state.

It should not be:

> MAPPO as an algorithm cannot consider capacity.

MAPPO can only learn from the state, observations, actions and reward supplied to it.

## **5\. Load management is a legitimate research direction**

The committed per-RSU analysis found substantial load asymmetry and multiple RSUs with negligible or zero backlog while others carried large loads.

Even though the full causal explanation is unresolved, this is enough to justify studying:

* load-aware direct RSU selection;<br>
* ingress-RSU forwarding;<br>
* least-loaded scheduling;<br>
* predicted-earliest-completion scheduling;<br>
* stale-information sensitivity;<br>
* deterministic versus learned dispatch.

Sandra’s broad research instinct is therefore useful.

## **6\. A deterministic baseline should precede learned scheduling**

Sandra’s proposed progression has merit:

existing DRL offloading<br>
        \+<br>
deterministic RSU scheduling

followed by:

existing DRL offloading<br>
        \+<br>
learned RSU scheduling

That sequencing is scientifically sensible, provided the deterministic mechanism is properly defined and inter-RSU forwarding is not treated as free.

---

# **F. Where Sandra is wrong, imprecise or too certain**

## **1\. `2.5` and `0.75` were not literal queue sizes**

This is a clear terminology/numerical error.

The values were multiplied by the padded vehicle-slot count. Sandra’s wording makes it sound as though the system had a queue containing 2.5 tasks and was reduced to 0.75 tasks, which would not even be a meaningful integer queue definition.

The actual endpoint bounds were:

6,220 and 1,866 tasks per RSU

## **2\. “Waiting room” is not a complete semantic definition**

The source calls the relevant quantity `RSU_MAX_CONCURRENT`. The model does not clearly expose the conventional distinction between:

* executing tasks;<br>
* queued tasks;<br>
* server count;<br>
* service rate;<br>
* queue length;<br>
* maximum total in-flight tasks.

Calling it a waiting room is helpful conversationally but should not appear as the final formal definition until Randy confirms the intended abstraction.

## **3\. The RSU did not simply “start refusing” at 0.75**

Agent 2’s reported reconstruction suggests that the clamp already excluded substantial work at the baseline:

18.36% at cap 2.5<br>
19.38% at cap 0.75

Therefore Sandra’s sequence:

reduce from 2.5 to 0.75<br>
→ RSU begins refusing tasks

is inaccurate.

A better statement is:

> The admission clamp was already active at the baseline, and lowering the ceiling modestly increased the amount of offered V2I work excluded from the RSU backlog.

## **4\. “Fail fast” is not proved**

A proper fail-fast claim requires a clear lifecycle:

task offered<br>
→ task rejected<br>
→ rejection timestamp<br>
→ rejection reason<br>
→ latency/outcome assigned<br>
→ denominator defined

The committed audit instead says:

* per-task physical completion is absent;<br>
* admission/rejection is not individually identified;<br>
* action selection does not prove that a transfer occurred;<br>
* current evidence cannot support exact rejected-task or throughput claims.

Agent 2 additionally reports that modelled latency and deadline outcomes were calculated separately from the later admission clamp, and that non-admitted compute did not enter the backlog even though those tasks remained scored.

The strongest justified language is:

> **Admission/backlog clipping occurred, but genuine fast-rejection accounting was not established.**

The observed mean reduction is best understood as:

1. backlog-tail clipping;<br>
2. possible synthetic unavailable-path penalties;<br>
3. incomplete alignment between task outcome accounting and admission accounting.

It should not simply be labelled “fail fast.”

## **5\. “Completion” does not mean physical completion**

The audit states that `task_met`, `done` and summary completion represent deadline success, not eventual physical execution. Per-task energy and eventual physical-completion events are absent.

Therefore:

deadline attainment unchanged

is supported.

But:

physically completed tasks unchanged

is not supported.

The distinction matters because a task might:

* be assigned a modelled latency;<br>
* be classified as meeting or missing a deadline;<br>
* but not have an independently recorded admission or physical-completion event.

## **6\. MAPPO does not appear to choose a specific RSU**

The action codes are:

0 \= local<br>
1 \= V2I<br>
2 \= V2V

The environment separately calculates the best RSU from link quality. The repository’s source reading identifies:

best\_rsu\_idx \= jnp.argmax(all\_v2i\_q, axis=1)

The action audit also warns that an offload selection does not prove an actual transfer.

So Sandra’s statement that:

> “the trained model learned to offload tasks to the best available RSU link”

mixes two mechanisms:

* **Actor:** chooses local, V2I or V2V.<br>
* **Environment:** chooses the best-link target.

The actor did not directly learn an RSU identity or load-balancing rule.

## **7\. The exact cause of idle RSUs remains unproved**

Load imbalance is real. But one earlier attempt to attribute sends to RSUs using `veh_best_rsu` was formally withdrawn because it used the wrong unit and assigned traffic to an RSU that demonstrably performed no work.

The standing repository position is:

* load asymmetry is measured;<br>
* the association rule contains no load term;<br>
* actual per-task ingress/execution attribution is incomplete;<br>
* the precise cause of individual idle RSUs remains undetermined.

Therefore:

> “Some RSUs carry most of the modelled load while others are idle”

is supported.

But:

> “RSUs near congested roads overload, while farther RSUs remain idle because the model always chooses those nearby RSUs”

is plausible but not yet demonstrated.

## **8\. The claim about RSU capacity broadcasting is unsupported**

The audited evaluator does not include a general RSU-capacity broadcasting system. But absence in this model does not prove that real RSUs cannot or do not share load information.

Stale telemetry is a legitimate concern, but it can be studied through:

* periodic updates;<br>
* delayed observations;<br>
* a central edge controller;<br>
* reservation tokens;<br>
* destination acknowledgements;<br>
* bounded-staleness models;<br>
* local forwarding at the ingress RSU.

The accurate research statement is:

> Load information may become stale and its age should be modelled.

Sandra’s statement treats one architecture choice as a universal fact.

## **9\. Kubernetes is being described inaccurately**

Kubernetes’ default scheduler matches newly created or unscheduled **Pods** to **Nodes**, using filtering, scoring and binding. A Kubernetes Service exposes one or more backend Pods behind a network abstraction. Neither mechanism is automatically a queue-aware per-task VEC scheduler that chooses execution RSUs using live backlog and deadline information. ([Kubernetes](https://kubernetes.io/docs/concepts/scheduling-eviction/kube-scheduler/?utm_source=chatgpt.com))

A technically accurate design would be:

Long-running RSU worker Pods<br>
          \+<br>
Application-level VEC task dispatcher

Kubernetes could provide:

* deployment;<br>
* node placement;<br>
* health management;<br>
* worker discovery;<br>
* scaling;<br>
* custom scheduler/controller infrastructure.

But the application-level dispatcher would still need to implement:

* task-level queue awareness;<br>
* deadline logic;<br>
* inter-RSU forwarding cost;<br>
* reservations;<br>
* retry/failure semantics;<br>
* result return.

Until actual Kubernetes components are deployed, the simulation should be called:

> **Kubernetes-inspired deterministic edge scheduling**

not simply:

> Kubernetes load balancing.

## **10\. “No retraining required” is only conditionally true**

There are two materially different architectures.

### **Architecture A: direct load-aware actor decision**

Actor observes RSU load/headroom<br>
Actor chooses a specific execution RSU

This changes the observation and/or action space. The actor must be retrained.

### **Architecture B: post-offload forwarding**

Frozen actor chooses V2I<br>
Environment selects best-link ingress RSU<br>
Separate scheduler chooses execution RSU

This can be tested without retraining the original actor.

However, even under Architecture B, the frozen actor is only a **baseline**, not guaranteed to remain optimal. Forwarding changes:

* latency;<br>
* energy;<br>
* queue dynamics;<br>
* availability;<br>
* return path;<br>
* reward consequences;<br>
* environment transition dynamics.

The project’s own research plan distinguishes frozen actors, random-capacity training and explicit capacity-aware retraining.

## **11\. Improvement in free-flow is not supported**

On the weekend and event-night traces, every measured metric was exactly identical across the tested capacity arms. These traces did not drive the model into the same saturated regime as the incident trace.

In free flow, forwarding may:

* provide no useful redistribution;<br>
* add an extra hop;<br>
* increase transmission energy;<br>
* increase end-to-end latency;<br>
* introduce reservation/control overhead.

Therefore the correct hypothesis is:

> Load balancing may improve deadline success under imbalanced congestion, while producing little benefit or some overhead under uncongested conditions.

Sandra’s prediction of improvement in both regimes is too confident.

---

# **G. Review of Agent Report 1 — Opus**

Agent 1’s report contains several strong observations, but one central measurement mistake materially weakens it.

## **What Agent 1 got right**

It correctly identified that:

* the intervention was not compute power;<br>
* `2.5` and `0.75` should not be treated as literal queue counts;<br>
* padding is a cross-trace comparability issue;<br>
* an action-mask function exists but is not applied by the trace evaluator;<br>
* compute/service controls and the backlog drain are distinct from `RSU_MAX_CONCURRENT`;<br>
* excess work apparently does not enter the backlog while task outcomes are still scored;<br>
* task conservation should be made explicit;<br>
* the original clarification email was too long;<br>
* post-offload forwarding versus capacity-aware actor retraining must be separated;<br>
* “Kubernetes-inspired deterministic edge scheduler” is safer terminology.

These are valuable conceptual and architectural points.

## **Where Agent 1 was wrong**

Agent 1 interpreted:

51 V2I decision rows with no eligible target

as:

51 RSU capacity rejections

Those are not the same thing.

According to Agent 2’s follow-up reconstruction:

* 51 was a seed-0 count of vehicle-decision rows choosing V2I without an eligible target;<br>
* those rows represented 107 tasks;<br>
* the same-step admission clamp excluded far more tasks;<br>
* stored `rsu_load` was post-drain, so not equalling the ceiling did not prove that the pre-drain clamp was inactive.

Agent 1 therefore made an incorrect inference when it concluded:

> “Randy’s fail-fast mechanism did not happen.”

The safer conclusion is:

> The explicit no-eligible-target path was small, but the same-step admission clamp appears to have been highly active.

## **What Agent 1 overstated**

Calling the unapplied action mask definitively a **defect** was premature. The project records that unmasked logits were intentionally retained for the primary comparison to match the original launchers and evaluator. Masked deployment is a separate factor.

Whether the unmasked evaluator is scientifically desirable is a separate question from whether it accidentally deviates from the intended design.

## **Overall assessment of Agent 1**

Agent 1 was strong on:

* architecture;<br>
* terminology;<br>
* experimental design;<br>
* missing accounting;<br>
* email structure.

But its rejection-count classification was load-bearing and incorrect.

**Overall reliability: moderate.** It should not be used as the sole factual basis for the rejection mechanism.

---

# **H. Review of Agent Report 2 — Codex**

Agent 2 is stronger on the disputed admission-clamp issue and produces the better reconciled interpretation.

## **What Agent 2 got right**

It correctly distinguished:

V2I selected with no eligible target

from:

offered V2I work excluded by the same-step admission clamp

It also recognised that saved `rsu_load` was post-drain and reconstructed the pre-drain admission condition.

Its reported aggregate results were:

cap 2.5:<br>
1,096,583 non-admitted of 5,973,330 eligible V2I tasks<br>
18.36%

cap 0.75:<br>
1,157,465 non-admitted of 5,973,330 eligible V2I tasks<br>
19.38%

It therefore correctly rejected both extremes:

* Sandra’s implication that refusal began only after reducing the limit;<br>
* Agent 1’s claim that the mechanism effectively never occurred.

Agent 2 also correctly identified the deeper accounting issue:

* outcomes are calculated separately from the later admission clamp;<br>
* only admitted work enters the backlog;<br>
* non-admitted work is not exposed as a proper per-task rejection lifecycle;<br>
* “completion” remains deadline success rather than physical completion.

It also made the proper distinction between:

* frozen actor plus downstream forwarding;<br>
* actor-level capacity awareness requiring retraining.

## **Limitations of Agent 2**

The exact clamp counts and nominal per-RSU workload ratios came from local NPZ artifacts and a reconstruction script shown in the transcript. Those analysis outputs are not part of the GitHub evidence I could independently rerun.

Before using those numbers in a dissertation, email or paper, the following should be preserved:

* analysis script;<br>
* exact input file hashes;<br>
* source commit;<br>
* formulas;<br>
* treatment of no-target rows;<br>
* treatment of substeps;<br>
* resulting JSON/CSV;<br>
* output hash.

Its **32.33 million compute-ms** figure is also described as nominal workload based on task classes and a noiseless service formula. It should not be presented as exact realised randomly perturbed work without qualification.

Agent 2 occasionally says load balancing is “strongly supported.” The imbalance motivates the experiment, but actual benefits remain untested, and actual per-task execution-RSU attribution is incomplete.

## **Overall assessment of Agent 2**

Agent 2 is the more reliable report on:

* clamp activity;<br>
* rejection classification;<br>
* post-drain state;<br>
* task accounting;<br>
* conditional retraining.

**Overall reliability: high, with a reproducibility caveat around locally reconstructed numerical counts.**

---

# **I. Final reconciled interpretation**

> In the incident-trace experiment, the evaluator converted `--rsu-cap-per-veh` into a per-RSU admission/in-flight bound using the padded trace width, changing the endpoint bound from 6,220 to 1,866 tasks per RSU. This intervention did not alter processor speed, task service demand or RSU service rate. Lowering the bound constrained how much offered work entered the RSU backlog and compressed the extreme latency tail of tasks that had already missed their deadlines; it did not broadly accelerate successful tasks, whose median latency remained approximately unchanged. The available outputs do not provide a complete per-task lifecycle linking offered work to admission, explicit rejection, execution and eventual completion, so the result should not be described as demonstrated fail-fast performance or improved physical completion. The evaluated actor selected only local, V2I or V2V, while deterministic environment logic selected the best-link RSU, and the actor lacked the observation information needed to react to the capacity intervention. The pilot therefore demonstrates sensitivity to admission/backlog accounting and motivates an explicitly instrumented load-aware RSU dispatcher; it does not demonstrate improved computational capacity or establish that Kubernetes-based forwarding will improve outcomes in every traffic regime.

---

# **J. Clarifications still required**

These are the questions that cannot be fully resolved from the committed evidence.

## **Questions for Randy**

1. **What is the intended formal meaning of `RSU_MAX_CONCURRENT`?**<br>
   Does it count waiting tasks, executing tasks, waiting plus executing tasks, or an abstract total in-flight population?<br>
2. **What is the intended outcome for same-step work above the limit?**<br>
   Should it be explicitly rejected, dropped, queued outside the RSU, retried, executed locally, forwarded or assigned a penalty?<br>
3. **Should task work be conserved?**<br>
   Must every offered task end in exactly one lifecycle state such as admitted, rejected, dropped or rerouted?<br>
4. **What should “physical completion” mean?**<br>
   Admission, service start, compute finish, result return, or another event?<br>
5. **Which parameter should represent genuine RSU computation power?**<br>
   Hardware-tier parameters, a service-rate multiplier, number of workers, backlog drain budget or something else?<br>
6. **Is unmasked evaluation intentional?**<br>
   Should an infeasible V2I choice receive a penalty, or should the policy be forced to choose a feasible local/V2V action?<br>
7. **Which architecture is intended?**<br>
   Direct load-aware execution-RSU selection, or best-link ingress followed by RSU-to-RSU forwarding?<br>
8. **What are the forwarding assumptions?**<br>
   Topology, bandwidth, transfer latency, energy, reliability, return path and maximum forwarding depth.

## **Question for Sandra**

9. **What exactly is meant by “Kubernetes load balancing”?**<br>
   Pod-to-node scheduling, Kubernetes Service routing, a scheduler plugin, a custom controller, or an application-level dispatcher hosted on Kubernetes?

---

# **K. Recommended next work**

## **1\. Accounting and instrumentation fixes**

Implement an explicit task lifecycle:

generated<br>
→ action selected<br>
→ ingress target identified<br>
→ admitted or rejected<br>
→ forwarded or retained<br>
→ execution started<br>
→ execution completed or dropped<br>
→ result returned<br>
→ deadline met or missed

Record at least:

* `task_id`;<br>
* offered count;<br>
* selected action;<br>
* ingress RSU;<br>
* admission outcome;<br>
* rejection reason;<br>
* execution RSU;<br>
* forwarding count;<br>
* transmission time;<br>
* forwarding time;<br>
* queue wait;<br>
* compute time;<br>
* return time;<br>
* physical-completion outcome;<br>
* deadline outcome;<br>
* energy.

Enforce:

offered tasks<br>
\=<br>
admitted<br>
\+ explicitly rejected<br>
\+ explicitly dropped<br>
\+ explicitly rerouted

No task should disappear through fractional backlog accounting.

## **2\. Small hand-checkable validation tests**

### **Test 1: admission boundary**

one RSU<br>
three tasks arrive<br>
one place remains

Expected result:

offered \= 3<br>
admitted \= 1<br>
rejected \= 2

Every task should have a visible final state.

### **Test 2: load balancing**

two reachable RSUs<br>
RSU A full<br>
RSU B empty

Verify:

* target selection;<br>
* reservation;<br>
* forwarding cost;<br>
* execution RSU;<br>
* final deadline outcome;<br>
* task conservation.

### **Test 3: masking**

Run the same state with:

unmasked actor<br>
masked actor

Confirm whether the infeasible V2I action becomes:

* a penalised choice;<br>
* local;<br>
* V2V;<br>
* or another action.

## **3\. Deterministic load-balancing baselines**

Compare:

1. no redistribution;<br>
2. round robin;<br>
3. least admitted/in-flight count;<br>
4. shortest predicted wait;<br>
5. earliest predicted completion;<br>
6. weighted earliest completion including forwarding and return cost.

A defensible score would be:

inter-RSU transfer<br>
\+ destination queue wait<br>
\+ destination compute time<br>
\+ result-return time<br>
\+ optional energy penalty

Use reservation so simultaneous assignments cannot all consume the same apparent capacity.

## **4\. DRL scheduling experiment**

Only after the deterministic baseline works, train a scheduling policy whose state includes:

* task class;<br>
* workload;<br>
* deadline;<br>
* queue/in-flight counts;<br>
* RSU service rate;<br>
* link and forwarding costs;<br>
* telemetry age.

Its action should choose:

* an execution RSU;<br>
* local fallback;<br>
* rejection;<br>
* or no forwarding.

Compare it with the deterministic algorithms using identical traces, arrivals and seeds.

## **5\. Kubernetes prototype**

Keep long-running worker Pods representing RSU compute services.

Use Kubernetes for:

* worker deployment;<br>
* health;<br>
* discovery;<br>
* node placement;<br>
* scaling;<br>
* possibly a custom scheduler/controller.

Use an application-level dispatcher for individual VEC tasks.

Do **not** create one Pod per microsecond-scale task.

## **Minimum defensible dissertation scope**

The safest scope is:

1. repair the lifecycle accounting;<br>
2. validate it with hand-checkable cases;<br>
3. implement no-forwarding and one or two deterministic schedulers;<br>
4. evaluate on the incident trace and one unsaturated trace;<br>
5. report deadline success, rejection, throughput, latency percentiles and forwarding cost.

A full DRL scheduler and “AI Kubernetes” system should be treated as extensions, not necessary minimum deliverables.

---

# **L. Professional response to Sandra**

**Subject: Clarification of the RSU-capacity result and next steps**

Dear Sandra,

Thank you for the detailed feedback, and please thank Randy for inspecting the implementation.

I agree with the central correction. My earlier phrase “per-vehicle edge capacity” was insufficiently precise and could be read as computation power. The evaluated control was converted into a per-RSU admission/in-flight concurrency bound; on the 2,488-slot incident trace, the endpoint values corresponded to limits of 6,220 and 1,866 tasks per RSU. The experiment did not directly change CPU frequency, processor count or the RSU service rate.

I also agree that the lower mean latency should not be presented as evidence of faster computation or a general performance improvement. The distributional analysis shows that median latency remained approximately unchanged, while the extreme latency tail of tasks that had already missed their deadlines was compressed.

There is one point I would like to clarify before describing the mechanism specifically as fail-fast rejection. The current evaluator does not expose a complete per-task admission and rejection lifecycle. The admission clamp appears to restrict how much work enters the RSU backlog, but deadline and latency outcomes are calculated separately, and the outputs do not identify every surplus task as an explicit rejected event. I therefore think the safest present description is admission/backlog clipping with incomplete rejection accounting, rather than confirmed fail-fast performance.

I agree that RSU load management is a valuable next research direction. My proposed first step is to repair the task accounting and then compare the existing frozen offloading actor under no forwarding, least-loaded forwarding and predicted-earliest-completion forwarding. The forwarding mechanism would include inter-RSU latency, energy, bandwidth and return-path costs.

For the simulation, I would initially use the term “Kubernetes-inspired deterministic edge scheduler.” An actual Kubernetes prototype could use long-running worker Pods at RSUs and an application-level dispatcher, rather than treating each short VEC task as a newly created Pod.

Could Randy please confirm:

1. whether `RSU_MAX_CONCURRENT` is intended as a waiting-queue limit, total in-flight-task limit or combined admission limit;<br>
2. how same-step tasks above the limit should be recorded and scored;<br>
3. what event should count as physical task completion;<br>
4. which parameter should represent genuine RSU compute/service capacity;<br>
5. whether unmasked V2I evaluation is intentional; and<br>
6. whether the intended load-balancing architecture is direct RSU selection or best-link ingress followed by forwarding?

Once those semantics are frozen, I can implement the corrected accounting and deterministic baseline before proceeding to learned scheduling.

Best regards,<br>
Abdulla

---

## **Final assessment in one sentence**

**Sandra is right about the central mistake and the need for load management; she is wrong or too certain about the exact queue semantics, fail-fast causality, completion meaning, MAPPO’s role in RSU selection, broadcasting, Kubernetes, retraining and guaranteed improvement across traffic regimes.**

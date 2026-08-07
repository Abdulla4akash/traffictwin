# Research direction after Supervisor Meeting 4

**Prepared:** 7 August 2026  
**Status:** planning synthesis for review  
**Evidence boundary:** this document combines the sanitized Meeting 4 record, current repository
status and a proposed independent Manchester bus research direction. It is not a verbatim meeting
transcript, supervisor approval, a signed experiment predeclaration or authority to make scientific
claims.

## 1. What the supervisor wants from Meeting 4

Meeting 4 narrowed the supervisor-directed investigation to **task scheduling under incomplete and
rapidly ageing RSU state**.

The existing trained MAPPO actor supplied through PhD student Randy's upstream environment makes a
high-level local/V2I/V2V decision. It does not observe RSU queue or in-flight load, configured
capacity or headroom, current reservations, or telemetry age. After a V2I action, the environment
normally selects an RSU through strongest/best-link logic rather than a load-aware scheduling
decision.

The supervisor therefore wants the project to investigate:

- whether strongest-link selection makes poor choices when the strongest RSU is busy;
- whether a deterministic dispatcher can use a weaker but less-loaded RSU;
- when forwarding delay, bandwidth and energy costs remove that benefit;
- whether stale or missing RSU state makes load-aware decisions unreliable;
- whether adding more RSUs helps when the selection mechanism can expose usable alternatives;
- whether the frozen actor can remain unchanged while a downstream dispatcher schedules V2I work;
- whether a retrained actor with load, capacity and telemetry-age observations improves outcomes;
- whether a two-stage learned system is worthwhile; and
- the conditions under which each approach helps, ties or harms.

The requested comparison contains four architectures:

1. the existing frozen actor with strongest/best-link environment selection;
2. the frozen actor followed by deterministic no-forwarding, least-loaded and
   earliest-completion dispatch policies;
3. a retrained load-aware actor; and
4. a two-stage system in which one model chooses local/V2I/V2V and another scheduler selects the
   execution RSU or forwarding action.

The intended result is a **condition map**, not a claim that one algorithm is universally best.
The experiments must identify the traffic, workload, RSU-load, forwarding-cost and
telemetry-freshness conditions under which each approach works.

Before large experiments, the task lifecycle must be measured explicitly:

```text
offered -> action selected -> admitted/rejected -> retained/forwarded
-> started -> completed/dropped -> returned/return failed
-> deadline met/missed
```

This distinction is essential because modelled deadline attainment is not the same as physical
task completion and return. The previous 2.5 to 0.75 intervention changed an admission/in-flight
ceiling, not RSU count or computing power. Its lower mean modelled latency did not by itself prove
faster computation or better physical completion.

## 2. How much of the supervisor-directed work is done

These percentages are planning estimates, not formal capability acceptance.

| Workstream | Estimated completion | Current position |
|---|---:|---|
| General TrafficTwin platform | 80-90% | Ingestion, validation, metrics, diagnostics, provenance, reporting and UI are extensive |
| Research problem and experiment design | About 80% | Question, candidate factors, hypotheses and experiment sequence are documented |
| Task-lifecycle foundation | About 60% | Lifecycle contract, conservation rules and synthetic two-RSU oracle exist; native event production is missing |
| Deterministic dispatchers | About 60% | Three policies and a matched synthetic comparison exist; they are not yet connected to native execution |
| Existing-model limitation analysis | 65-70% | Capacity blindness and invariant high-level actor decisions are documented; native lifecycle confirmation remains |
| Native scheduling evidence | 10-20% | No authorized native lifecycle producer or realised matched policy comparison exists |
| Load-aware actor retraining | About 10% | A synthetic capacity-aware diagnostic exists but is not an admitted native study |
| Two-stage learned scheduler | Under 10% | Proposed and designed, but not experimentally implemented |
| Final algorithm comparison | 0-5% | Blocked by native instrumentation and the earlier experiments |
| Dissertation-ready scheduling conclusions | 25-35% | Strong planning and audit material exists, but the central scheduling evidence is unfinished |

Overall, the Meeting 4 research programme is approximately **40-45% complete**, with **55-60%
remaining**. Engineering preparation is further advanced than the scientific evidence. The main
remaining obstacle is trustworthy native task-lifecycle and execution-target evidence, not simply
writing more scheduler code.

Several scheduling components currently live on sequential feature branches rather than `main`:

- strict lifecycle and conservation contracts;
- a hand-checkable two-RSU synthetic oracle;
- deterministic strongest-link/no-forwarding, least-loaded and earliest-completion policies;
- read-only validation for future native lifecycle and dispatch sidecars; and
- a matched synthetic dispatcher study.

These are useful engineering foundations, but they must not be described as realised native
scientific results.

## 3. Relationship to PhD student Randy's work

The trained 17-dimensional MAPPO actor, checkpoints and upstream VEC environment originate from
PhD student Randy's work. TrafficTwin did not create that original model. TrafficTwin imported,
audited and instrumented the available artifacts and identified important limits in their current
observation, target-selection and lifecycle semantics.

The supervisor-directed scheduling investigation therefore builds on the upstream environment in
order to test and potentially improve its behaviour. That does not require the entire dissertation
to depend on it. Two research threads can be kept distinct:

- **Supervisor-directed scheduling thread:** finish the minimum native lifecycle and deterministic
  comparison needed to answer the Meeting 4 question responsibly.
- **Independent Manchester bus thread:** investigate prediction, data fusion, freshness and
  evidence-grounded decision support using live and historical public transport data.

TrafficTwin remains useful to both threads as the ingestion, validation, provenance, experiment and
reporting platform. Scientific claims, datasets and model results should not be silently transferred
between the two threads.

## 4. How to move forward with the supervisor-directed work

The most efficient path is to answer the supervisor's core question with the smallest defensible
experiment before committing to expensive retraining.

### Step 1: confirm upstream semantics

Obtain written answers about:

- what the admission/concurrency control represents;
- how tasks enter, wait, start, complete, drop and return;
- whether service rate is separately configurable;
- which RSUs are eligible at decision time;
- how strongest-link selection, masking and forwarding work; and
- whether the upstream environment can emit the required lifecycle and dispatch events.

Legacy aggregate latency and `task_met` arrays cannot reconstruct events that were never recorded.

### Step 2: produce native lifecycle events

Add or review an authorized adapter that emits exact-bound lifecycle, dispatch-request and
dispatch-decision records. Validate task conservation and preserve native identities and timestamps.
No scheduler comparison should be promoted until this evidence exists.

### Step 3: replay the two-RSU hand check

Run one case in which the strong-link RSU is busy and a weaker-link RSU is idle. Verify by hand:

- eligibility and reservations;
- ingress and forwarding;
- queue wait and computation;
- execution location;
- result return;
- forwarding delay and energy; and
- final deadline and physical-return outcomes.

### Step 4: run the deterministic matched comparison

Compare existing selection, no forwarding, least-loaded and earliest completion using identical
traffic, tasks, seeds, RSU placement and cost assumptions. Retain agreements and disagreements,
not only aggregate means.

### Step 5: run one-factor sensitivity experiments

Vary one factor at a time:

1. task arrival rate;
2. RSU count;
3. genuine RSU service rate;
4. background load;
5. telemetry age;
6. traffic regime; and
7. forwarding cost.

Use matched seeds, report uncertainty, retain null results and show the changed factor directly in
every figure.

### Step 6: make a retraining decision

Only retrain the actor if the deterministic comparison shows that load-aware information matters
and the remaining question genuinely requires actor-level decisions. Compare the original
observation contract with a load/capacity/age-aware contract using the same training budget,
checkpoint rule, evaluation data and seeds.

### Minimum useful deliverable

A defensible bounded contribution would consist of native lifecycle instrumentation, the verified
two-RSU case, a matched deterministic comparison and one focused freshness/load sensitivity study.
The larger retrained and two-stage DRL comparison should be treated as a later gate rather than an
automatic requirement.

## 5. Independent Manchester bus research angle

The independent thread should use observed mobility and road evidence to investigate a clear
prediction problem. A strong candidate is:

> Can recent bus trajectories, historical traffic measurements and near-live road-event
> information improve short-horizon prediction of bus corridor travel time and severe-delay risk
> compared with bus-position history alone?

### Data roles and boundaries

- BODS or an admitted TfGM bus-position feed provides live vehicle positions, not general road
  speed or observed computing tasks.
- National Highways provides near-live closures, restrictions and other operational events on the
  strategic-road network, not measured city-wide congestion.
- WebTRIS provides historical/latest volume and speed measurements where its strategic-road
  coverage overlaps the study area.
- DfT count data provides historical demand context; AADF is not live demand.
- Existing TfGM signal records describe infrastructure, not live signal phases.
- Any newly obtained TfGM source requires its own schema, licence, time, identity, retention and
  geographic-admission review.

### Prediction targets

The study should select one primary target and at most one secondary target:

- segment or corridor travel time over the next 5, 10 or 15 minutes;
- probability of severe delay over a declared threshold;
- bus-bunching risk;
- corridor disruption probability; or
- expected recovery time after a detected operational event.

The recommended primary target is **short-horizon corridor travel time**, with **severe-delay
probability** as the secondary target.

### Model strategy

Begin with simple, difficult-to-beat baselines:

1. last observed travel time;
2. historical median by route, weekday and time window;
3. moving-average or regularized linear model; and
4. a bus-position-only gradient-boosted model.

Then test the incremental value of each source:

1. bus history only;
2. bus history plus traffic measurements;
3. bus history plus road events;
4. bus history plus infrastructure and temporal context; and
5. all admitted sources combined.

A gradient-boosted tree model with quantile outputs is an appropriate first research model. A
temporal neural model such as a TCN, LSTM or Transformer should be attempted only if the captured
dataset is large and stable enough to justify it. Complexity is not evidence of quality.

### Agentic and LLM component

The numerical prediction should come from trained and evaluated models, not from an LLM guessing a
travel time. An LLM-powered agent can instead:

- inspect admitted source availability and freshness;
- construct validated model queries;
- select from pre-approved models and feature sets;
- structure textual incident descriptions under a tested extraction contract;
- compare prediction scenarios;
- explain which validated features influenced an output;
- produce analyst-facing summaries; and
- refuse or qualify a prediction when coverage, freshness or uncertainty is unacceptable.

Every response should retain the source timestamps, model version, feature contract, uncertainty
and refusal reason. LLM explanations must be tested for faithfulness against the actual model inputs
and must not invent causal explanations.

### Evaluation design

- Use chronological train/validation/test splits to prevent future leakage.
- Hold out complete dates and, where feasible, corridors.
- Report MAE/RMSE and calibrated prediction-interval coverage.
- Evaluate peak/off-peak and event/non-event periods separately.
- Perform source ablations to measure incremental value.
- Simulate realistic source delay, dropout and staleness.
- Compare against simple persistence and historical baselines.
- Report when the model refuses and whether refusal improves reliability.

## 6. Candidate research questions

The project should choose one primary question and a small number of supporting questions rather
than attempting all of these.

### Recommended primary question

**RQ1.** To what extent do traffic measurements and near-live road-event information improve
short-horizon bus corridor travel-time and severe-delay prediction beyond recent bus trajectories
and historical time-of-day baselines?

### Supporting questions

**RQ2.** How does the freshness, missingness and spatial coverage of each source affect predictive
accuracy and uncertainty?

**RQ3.** Under which corridor, traffic-regime and event conditions does each external source add
useful information, provide no measurable benefit or reduce performance?

**RQ4.** How well do models trained on selected dates or corridors generalize to held-out dates,
routes and operational conditions?

**RQ5.** Can calibrated uncertainty and an explicit refusal policy produce more reliable operational
predictions than always returning a point estimate?

**RQ6.** Can an LLM agent generate faithful, evidence-grounded explanations of predictions and
source limitations without introducing unsupported causal claims?

**RQ7.** Do validated what-if scenarios help an analyst understand the likely direction and
uncertainty of disruption effects without presenting the scenarios as observed outcomes?

The strongest focused study would use RQ1 as the primary question, RQ2 and RQ3 as mechanism and
robustness questions, and RQ5 or RQ6 as one carefully bounded system contribution.

## 7. Proposed immediate plan

During the first week of the independent thread:

1. inventory the exact available bus, TfGM, National Highways, WebTRIS and DfT artifacts;
2. document source rights, timestamps, identifiers, coverage, retention and missingness;
3. identify one or two bus corridors with sufficient repeated observations and genuine source
   overlap;
4. define the primary prediction target, horizon, unit and denominator;
5. construct persistence and historical-median baselines;
6. build the first chronological modelling table without future leakage;
7. run a small bus-only feasibility pilot;
8. add one external source at a time and record ablation results; and
9. prepare a short supervisor decision note comparing the bounded scheduling deliverable with the
   independent bus research proposal.

The independent thread should advance only if the data audit confirms enough temporal depth,
geographic overlap and legal permission for a defensible study. A negative feasibility result
should remain visible rather than being repaired with synthetic claims.

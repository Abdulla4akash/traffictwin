# Supervisor Meeting 4 — technical record and experiment direction

**Record prepared:** 6 August 2026

**Status:** sanitized technical reconstruction from owner-supplied meeting notes. It is not a
verbatim transcript, supervisor approval, signed predeclaration or authority to execute an
experiment.

## Executive summary

The meeting identified the central dissertation problem as **decision-making with incomplete and
rapidly ageing distributed state**.

The existing trained 17-dimensional MAPPO actor does not observe RSU load, queue/in-flight state,
configured capacity or telemetry age. It chooses only the high-level local/V2I/V2V action. The
environment then chooses the V2I RSU using strongest/best-link logic rather than current RSU load.
Consequently, changing hidden RSU conditions may leave actor decisions unchanged, and additional
RSUs may provide no benefit if the selection path cannot use them.

This is not evidence that MAPPO as an algorithm is inherently poor. The limitation may arise from:

1. the actor observation and action design;
2. the training data and reward;
3. deterministic environment-side RSU selection; and
4. the wider system's incomplete task-lifecycle and state-exchange semantics.

The proposed MSc contribution is to compare multiple ways of addressing that limitation and
identify the conditions under which each approach works best. There is no assumption that one
algorithm is universally superior.

## The dynamic-information problem

An RSU can be idle when it advertises its state but overloaded when a decision reaches it. Vehicles
also enter and leave coverage quickly. A scheduler therefore needs both the reported state and its
freshness.

Candidate state includes:

- queue or admitted/in-flight task count;
- service rate and remaining headroom;
- current reservations;
- link quality and expected contact time;
- observation timestamp and age;
- task size, CPU work and deadline; and
- transfer, forwarding and result-return cost.

Stale telemetry is a first-class experimental factor, not noise to hide. The scheduler may need to
learn that an apparently attractive measurement is too old to trust.

## Architectures to compare

### A. Existing frozen actor and environment selection

- Actor chooses local, V2I or V2V.
- Environment chooses the strongest/best-link RSU.
- RSU load/capacity is hidden from the actor.
- This is the existing reference, not a load-aware scheduler.

### B. Frozen actor plus deterministic dispatcher

- Keep the actor's local/V2I/V2V decision unchanged.
- After V2I selection, choose or forward to an eligible RSU using explicit rules.
- Candidate rules: no forwarding, least-loaded and predicted earliest completion.
- No actor retraining is required.
- This is a necessary baseline but not sufficient novelty by itself.

“Kubernetes-inspired” should mean an application-level task dispatcher over long-running worker
services. It should not imply that standard Kubernetes automatically schedules individual VEC
microtasks or that one Pod is created per task.

### C. Retrained load-aware actor

- Add load, capacity/headroom, contact and telemetry-age information to the observation.
- Optionally allow the actor to select the final execution RSU.
- The changed observation/action contract requires retraining from scratch.

### D. Two-stage learned system

- First model decides local/V2I/V2V offloading.
- A second DRL scheduler chooses the execution RSU or forwarding action.
- Compare with the deterministic dispatcher using identical information, tasks, traces and budget.

## Relationship between traffic data and task scheduling

TfGM and BODS data contain vehicle movement, not computing tasks. Their role is to create realistic
mobility conditions:

```text
traffic counts/speeds and bus movement
→ SUMO routes, positions, speeds and density
→ coverage, contact time, handover and contention
+ explicit synthetic task workload
→ offloading and RSU scheduling experiment
```

The computing-task model must still be declared: arrival rate, input/output size, CPU work,
deadline, class and vehicle compute capability. RSUs, radio assumptions and computing demand
remain simulated unless separately observed.

Buses offer a useful trace-driven scenario because they repeatedly traverse routes, operate under
time constraints and can act as mobile sensing platforms. Any accident-reporting, sensing or
passenger-service task is nevertheless a **synthetic application scenario**, not an observed BODS
task.

The scheduler does not make the physical roads less congested. Traffic conditions affect the
computing system. A scheduling effect on vehicle speed would require a separate closed-loop
traffic-control intervention.

## SUMO context

The supervisor described SUMO as a widely used academic traffic-simulation platform and advised
using its documentation alongside producer clarification. Historical deployment anecdotes from
the meeting must be independently sourced before use in the dissertation.

SUMO documentation can define traffic routes, lanes, speeds, vehicle types and detector-derived
demand. Producer-specific VEC task, queue, RSU and actor semantics still require confirmation from
the upstream producer.

## Core research objective

> Under which traffic, task-load, RSU-load and telemetry-freshness conditions do the existing
> strongest-link path, a deterministic load-aware dispatcher, a retrained load-aware actor and a
> two-stage DRL scheduler perform best?

## Draft parameter catalogue

The values below are candidate experimental levels for supervisor/producer review, not approved
settings.

| Parameter | Definition and role | Candidate variation | Rationale |
|---|---|---|---|
| Traffic regime | Mobility/density window | night, dawn, morning peak, evening peak | Test free-flow to high-support conditions |
| Vehicle density | Simultaneously active vehicles | calibrated regime values; optional controlled scaling | Separate density from time-of-day labels |
| Vehicle speed | Per-step movement/contact duration | observed/calibrated distributions | Test faster short-contact versus slower long-contact cases |
| Route | Ordered SUMO edges per vehicle | fixed per seed; alternative reviewed route sets later | Routes determine future RSU contact |
| Vehicle mix | Bus/general-vehicle composition | observed/calibrated mix; class-separated sensitivity | Avoid treating buses as all traffic or double-counting them |
| Global task rate | Total offered tasks per second | 0.5×, 1× and 2× declared baseline | Isolate compute load while mobility stays fixed |
| Per-vehicle task rate | Offered tasks per active vehicle | 0.5×, 1× and 2× baseline | Test natural scaling as vehicle count changes |
| Task class | T1/T2/T3 workload/deadline contract | fixed mix, then one class at a time | Identify workload-specific effects |
| Task CPU work | Required compute operations/time | low, baseline and high | Test service-demand pressure |
| Task payload | Input/output transmission size | low, baseline and high | Separate radio from compute pressure |
| Task deadline | Maximum acceptable end-to-end delay | loose, baseline and tight | Test deadline sensitivity |
| RSU count | Available analysis/compute sites | 1, 2, 4, 8 and current 10, subject to coverage feasibility | Test whether usable choice changes outcomes |
| RSU placement | Spatial site configuration | fixed nested placement first; alternatives later | Avoid confounding count with relocation |
| RSU service rate | Genuine compute/work-drain capability | 0.5×, 1× and 2× baseline | Test computation power separately from admission |
| Admission ceiling | Per-RSU admission/in-flight bound | reviewed 0.75/1.0/1.5/2.5 controls only after semantic repair | Preserve distinction from computation power |
| Background load | Non-study work occupying an RSU | none, balanced and hotspot | Create non-trivial busy-versus-strong-link choices |
| Forwarding cost | RSU-to-RSU transfer/return cost | zero engineering bound, baseline and high | Identify when redistribution stops helping |
| Telemetry age | Delay between state measurement and use | 0, 1, 2, 5 and 10 s | Test stale distributed information |
| Refresh interval | Frequency of RSU-state publication | 0.1, 1 and 5 s candidate levels | Trade freshness against communication overhead |
| Missing state | Fraction of unavailable telemetry | 0%, 10% and 30% candidate levels | Test resilience to incomplete information |
| Scheduler | Execution-RSU decision policy | existing, no-forwarding, least-loaded, earliest-completion, learned | Primary algorithm comparison |
| Random seed | Mobility/task/training replication | matched, disjoint declared sets | Measure variability without post-hoc selection |

Exact values must be justified by source evidence, producer semantics, a bounded engineering probe
or a written provisional rationale. They must not become defaults merely because they appear here.

## Required experiment sequence

### Experiment 0 — Lifecycle and hand-check validation

Instrument:

```text
offered → selected → admitted/rejected → retained/forwarded
→ started → completed/dropped → returned → deadline met/missed
```

Use one hand-checkable case with a strong-link busy RSU and a weaker-link idle RSU. Confirm task
conservation, reservation, forwarding cost, execution location and final outcome.

### Experiment 1 — Existing-model limitation

- Hold traffic, tasks, seeds and actor fixed.
- Vary one hidden state: RSU load, telemetry or usable RSU count.
- Test whether actor actions remain unchanged and whether environment-side targets change.
- Do not infer target behaviour from unreconciled aggregate arrays.

### Experiment 2 — Deterministic baseline

- Compare existing selection, no forwarding, least-loaded and earliest completion.
- Hold trace, tasks, seeds, RSU placement and costs fixed.
- Demonstrate that the dispatcher can exploit a second eligible RSU in a non-trivial case.

### Experiment 3 — One-factor sensitivity

Vary one factor at a time while recording every constant:

1. task arrival rate;
2. RSU count;
3. RSU service rate;
4. telemetry age;
5. traffic regime; and
6. forwarding cost.

Only after the main effects are understood should a small predeclared factorial study test
interactions such as traffic regime × task rate or scheduler × telemetry age.

### Experiment 4 — Retrained actor

- Compare randomized-capacity training with the original observation against explicit
  load/capacity/age observation.
- Use matched training budget, checkpoint rule, evaluation traces, tasks and seeds.
- Separate the effect of information from the effect of extra training.

### Experiment 5 — Final algorithm comparison

Compare the strongest deterministic baseline, retrained actor and two-stage learned scheduler on
selected boundary conditions:

- free-flow/low task load;
- peak/high task load;
- fresh telemetry; and
- stale telemetry.

The intended finding is a map of conditions where each method helps, ties or harms—not one
universal winner.

## Non-trivial scenario requirements

Avoid scenarios whose outcome can be guessed from the algorithm description. Each comparison
should contain:

- at least two genuinely eligible RSUs;
- a trade-off between strong link and current load;
- non-zero transfer and return cost;
- heterogeneous task sizes or deadlines;
- state changes between observation and action; and
- enough load to exercise queues without forcing every task to fail.

If the strongest-link and least-loaded rules always select the same RSU, the scenario does not
test scheduling.

## Outcome measures

- offered, admitted, rejected, dropped, started, completed and returned task counts;
- throughput and physical-return rate;
- modelled deadline attainment;
- p50/p95/p99 end-to-end latency;
- queue wait/age and compute time;
- forwarding count, delay, bandwidth and energy;
- handover/contact-loss failures;
- per-RSU utilisation, load distribution and imbalance;
- action/target switch rate; and
- state age at decision plus stale-state error.

## Draft hypotheses

1. The current frozen actor will not adapt to hidden RSU load/capacity changes.
2. Deterministic forwarding will help under load imbalance and saturation.
3. Forwarding benefit will shrink or reverse under low load or high transfer cost.
4. Increasing RSU count will help only when coverage and selection expose usable alternatives.
5. Stale telemetry will reduce the value of load-aware scheduling.
6. An age-aware learned scheduler may be more robust in highly dynamic conditions, while a
   deterministic method may match or outperform it in stable/simple conditions.

Every null or contrary result remains publishable.

## Figures and dissertation reporting

Every figure must state:

- the single changed factor;
- all held-constant factors;
- algorithm and seed set;
- metric definition and denominator;
- uncertainty or per-seed distribution;
- scientific interpretation; and
- limitations.

RSU-count experiments must display RSU count explicitly on an axis or facet. Flat lines must be
explained rather than hidden. A graph that does not expose the varied parameter cannot support a
claim about that parameter.

## Boundaries and corrections

- The completed 2.5→0.75 TrafficTwin intervention changed an admission/in-flight ceiling, not RSU
  count or computation power.
- Lower mean modelled latency did not prove faster computation or physical completion.
- Exact per-task execution-RSU attribution remains incomplete and must be instrumented.
- Frozen-actor forwarding does not require retraining; actor-level load/capacity observation does.
- Comments in the meeting about another student's RSU-count experiment and graph must not be
  attributed to the TrafficTwin capacity experiment.
- Historical anecdotes about SUMO must be sourced before dissertation use.

## Requested deliverables and actions

1. Produce a reviewed next-experiment document listing parameters, definitions, values, constants,
   hypotheses and rationale.
2. Ask the upstream producer to clarify RSU concurrency, task lifecycle, service rate, masking,
   target selection and forwarding semantics.
3. Complete lifecycle instrumentation and hand-checkable validation before large campaigns.
4. Implement the simplest deterministic dispatcher baseline, then rerun matched experiments.
5. Improve visualisations so every varied parameter, especially RSU count, is visible.
6. Explain and analyse every dissertation figure rather than treating plots as self-explanatory.
7. Receive/review the promised bus dataset without treating mobility records as task evidence.
8. Use official SUMO documentation for traffic parameters and retain unresolved producer-specific
   questions for the upstream author.

## Related records

- [Traffic-to-VEC scheduling experiment plan](traffic_to_vec_scheduling_experiment_plan_20260806.md)
- [Current capacity/scheduling audit](../current_status_5_6_pro_analysis.md)
- [Short live-experiment and TfGM reply](live_experiments_and_tfgm_reply_short_20260806.md)
- [Supervisor data questions](supervisor_rsu_scheduling_clarification_questions_20260806.md)

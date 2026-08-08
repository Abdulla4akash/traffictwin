# Randy Email Research Analysis — 7 August 2026

> **Supporting source analysis:** Randy's reported results and proposals inform the research but
> do not set the current execution order. Read
> [RESEARCH_NEXT.md](evaluation/RESEARCH_NEXT.md) for the authoritative current direction.

This document records the research value extracted from a technical email from
PhD student Randy Putra that Abdulla supplied on 7 August 2026. It paraphrases
the relevant technical content rather than reproducing personal email headers.
The email refers to a more detailed `MSc Students QnA.docx`. The attachment was
subsequently supplied and reviewed; its technical decisions are captured in the
[MSc Students Q&A research record](msc_students_qna_research_record_2026-08-05.md).
The raw waiting-room sweep outputs were not supplied with either source.

This is a research-planning and source-audit note. Email statements are labelled
as reported claims until their configurations, seeds, outputs, and calculations
have been reproduced. This document does not change any formal TrafficTwin
capability or gate status.

Sandra Sampaio's direct research instruction precedes this implementation
discussion and is recorded in the prominent
[`SUPERVISOR_RESEARCH_DIRECTION.md`](../SUPERVISOR_RESEARCH_DIRECTION.md).

## Executive assessment

The email provides three immediately useful contributions:

1. a concrete MAPPO observation ablation: add RSU load and retrain;
2. implemented evaluator, admission, load-balancing, and reactive-scaling
   foundations in the latest `vec_env`; and
3. a strong independent research direction: proactive, delay-aware RSU
   autoscaling compared with fixed, static, reactive, deadline-aware, and
   oracle baselines.

The waiting-room sweep is useful as a reported negative result, but it must be
repeated under the latest physical work-conserving queue semantics before its
conclusion is accepted.

## Source state inspected

The source audit used the authorised private [`vec_env`](https://github.com/Abdulla4akash/vec_env)
mirror at current `main` commit
`0f01f4d2082d3e8b735e74a873095ab8eeba37cc`. The TrafficTwin-reviewed historical
snapshot remains preserved separately at
`068b4ea33e640f206ce6a7d04f3d6fae2ac831f4`.

The current source contains the following relevant increments:

| Commit | Implemented evidence |
|---|---|
| `d4d5dfc` | Inter-RSU `jsq` and `p2c` load balancing over a modelled fibre backhaul |
| `e592662` | Deadline-aware admission (`dla`) and placement |
| `4cb7c06` | Physical RSU-cap rejection, sequential substep queueing, vehicle-order admission, and static/reactive Kubernetes-style scaling |
| `eb5ed93` | Absolute per-RSU admission ceiling through `--rsu-cap-abs` |
| `df022e6` | Offered/admitted population reporting and per-task lifecycle outcomes |
| `82d3ecf` | Work-conservation ledger in evaluator JSON results |

The principal implementation is
[`eval/eval_sumo_stage1_mc.py`](https://github.com/Abdulla4akash/vec_env/blob/0f01f4d2082d3e8b735e74a873095ab8eeba37cc/eval/eval_sumo_stage1_mc.py).

## 1. RSU waiting-room sensitivity

### Reported result

The email reports a sensitivity sweep of the RSU waiting-room limit from
`0.75 × fleet size` to `40 × fleet size` under this stated case:

- Manchester Etihad and Co-op area;
- incident-gridlock scenario;
- Friday 15 March 2024;
- evaluation window 20:00–21:00; and
- reported completion `0.6943` at every tested limit.

The email reports that a larger waiting room admitted more V2I tasks and
rejected fewer tasks but increased mean latency from approximately `4.9 s` to
`128.4 s`. The proposed explanation is fail-fast accounting: tasks rejected by
a small waiting room fail immediately, while tasks admitted by a large waiting
room wait longer before missing their deadlines.

### Why the result is useful

- It warns that mean latency can be dominated by how failed work is accounted
  for rather than by an improvement in successful service.
- It shows why offered, admitted, completed, rejected, unavailable, and
  deadline-met populations require separate denominators.
- It argues against describing a fleet-scaled waiting-room limit as physical RSU
  capacity. The experiment convenience and physical interpretation are distinct.

### Why it must be repeated

The latest evaluator documents that the legacy `clamp` path did not conserve
all offered work when the RSU cap bound; in collapse cells, some eligible V2I
work could disappear at enqueue. The newer physical path provides:

- `--rsu-cap-mode reject`;
- `--substep-queue sequential`;
- `--veh-queue conserved`; and
- `--rsu-cap-abs` to specify an absolute physical ceiling rather than tying the
  ceiling to fleet size.

Therefore the invariant-completion conclusion is currently implementation-
dependent. The required audit is to repeat the sweep under the physical path
and compare it directly with the legacy path. Completion may remain invariant,
but that result must emerge from conserved task accounting rather than from a
queue clamp artifact.

The exact sweep manifests, seeds, JSON outputs, and detailed attachment are not
present in the inspected `tos-data` mirror. Until obtained, `0.6943`, `4.9 s`,
and `128.4 s` remain email-reported values rather than repository-reproduced
TrafficTwin evidence.

## 2. Fine-grained evaluator recording

The email supports detailed recording for auditability. The current evaluator
already implements much of the requested foundation:

- optional per-step and per-task NPZ output;
- per-task lifecycle outcomes;
- offered and admitted task populations;
- overall and admitted-population completion;
- admitted-task and deadline-met latency;
- V2I cap rejection, DLA rejection, vehicle-queue rejection, and channel
  unavailability counts;
- local, V2I, and V2V decision shares;
- per-class completion;
- energy per offered task;
- work offered, admitted, rejected, or unavailable by queue family; and
- Kubernetes multiplier, scale-event, and first-scale-up accounting.

This recording should be treated as mandatory for selected audit runs and
research exemplars, not necessarily every large training step. Aggregate JSON
and instrumented NPZ streams should reconcile exactly before a run is admitted
for analysis.

## 3. RSU load in the MAPPO observation

### Current source semantics

The current environment calculates a normalized load fraction for the selected
best RSU, `best_rsu_load_frac`, but deliberately discards it when constructing
the default policy observation. The default observation is 17-dimensional; the
capability-scalar variant is 13-dimensional. An RSU-load variant would therefore
normally become 18-dimensional, or 14-dimensional when combined with the
capability-scalar representation.

The relevant source is
[`jaxmarl/env/vec_jax.py`](https://github.com/Abdulla4akash/vec_env/blob/0f01f4d2082d3e8b735e74a873095ab8eeba37cc/jaxmarl/env/vec_jax.py).

Because the input space changes, an old actor cannot be evaluated as though it
were the new variant. Both actor and critic must be retrained, and the PyTorch
and JAX environment contracts should remain synchronized or explicitly labelled
as different variants.

### Clean ablation

Compare:

1. the current observation;
2. current observation plus normalized best-RSU load; and, if justified,
3. a richer but separately named variant containing candidate-RSU load or
   predicted waiting time rather than only the chosen best RSU.

Hold constant:

- training steps and optimizer settings;
- MAPPO/IPPO algorithm choice;
- fleet composition;
- task arrival distribution;
- training and evaluation traces;
- scenario and evaluation window; and
- common seed set.

Use a multi-seed campaign and report the complete distribution, not only the
best seed. The primary question is not merely whether reward rises, but whether
the added load signal changes V2I/V2V/local decisions and improves offered-task
completion, deadline performance, latency, energy, and resource use without
overfitting to one congestion regime.

## 4. Channel and target-selection semantics

The policy chooses the action family:

- local execution;
- V2I offloading; or
- V2V offloading.

The environment then selects an eligible RSU or vehicle using the strongest
available channel, primarily influenced by distance and refreshed at the
one-second decision interval. Signal quality is therefore one observation among
several; the learned policy does not currently choose a specific target.

This distinction matters when interpreting agent intelligence. A successful
V2I decision does not prove that the policy learned RSU selection. Target
selection and load balancing are currently environment/controller mechanisms.
A later learned-target variant would be a different action space and must not be
silently compared with the three-action policy.

## 5. Deadline-aware admission and RSU dispatch

The email recommends a deadline-aware doorman and an inter-RSU dispatcher. The
current evaluator already exposes:

- `--rsu-lb jsq`: least-backlog placement;
- `--rsu-lb p2c`: power-of-two-choices placement;
- `--rsu-lb dla`: JSQ plus deadline-aware rejection;
- `--rsu-lb dla_p2c`: P2C plus deadline-aware rejection; and
- `--rsu-backhaul-ms`: explicit forwarding delay when execution moves away from
  the radio-ingress RSU.

These are valuable experimental baselines. They should first be tested with a
frozen actor so that the infrastructure intervention is isolated. Joint policy
retraining can follow as a separately labelled experiment because it changes
both the controller and the learned response.

## 6. Kubernetes-style RSU scaling

### Existing baseline

The email supports an Option-B-style vertical scaling model: the VEC service
starts with a conservative CPU allocation and can scale toward the remaining
RSU cores. The current evaluator implements:

- `off`: fixed 1× legacy capacity;
- `static`: fixed capacity multiplier; and
- `reactive`: HPA-style threshold control using a utilization EMA.

The current reactive defaults model:

- 15-second synchronization;
- 15-second actuation delay;
- 300-second downscale stabilization;
- 60-second utilization EMA; and
- scale levels from 1× to 3×.

These parameters encode assumptions, not universal Kubernetes facts. They must
be recorded in every result and tested for sensitivity.

### Strong independent research question

> Can proactive, delay-aware RSU autoscaling forecast incoming workload and
> activate capacity early enough to improve offered-task completion and
> deadline performance, while consuming fewer core-seconds than static 3×
> capacity and outperforming the existing reactive controller?

The motivation is sound: metrics collection, controller evaluation,
stabilization, actuation, and control-plane communication introduce cumulative
delay. A reactive scaler may respond too late to short bursts or incident-driven
load changes.

### Required controller comparison

| Controller | Purpose |
|---|---|
| Fixed 1× | Existing-capacity baseline |
| Static 3× | Upper-resource, non-adaptive baseline |
| Reactive | Existing HPA-style baseline |
| Reactive + DLA | Tests interaction between capacity and admission |
| Proactive forecast | Proposed contribution |
| Oracle future-load | Non-deployable upper bound |

The proactive controller should begin with simple forecast baselines before a
complex model: persistence, moving average or EWMA, and a small regression or
gradient-boosted model. Temporal neural or graph models should be added only if
they improve held-out accuracy and downstream control outcomes sufficiently to
justify their complexity.

## 7. Metrics and experimental controls

Every comparison should report:

- completion over all offered tasks;
- completion over admitted tasks;
- mean, percentile/tail, admitted-task, and deadline-met latency;
- task-class-specific completion;
- average energy per offered task and clearly defined energy boundaries;
- local, V2I, and V2V decision shares;
- DLA, cap, queue, and unavailable rejection counts;
- offered/admitted/rejected work conservation;
- mean capacity multiplier or core-seconds;
- scale events, first-scale-up time, and time spent at each capacity;
- backhaul-forwarding count and latency; and
- scenario, date, evaluation window, actor variant, code/data commits,
  checkpoint, seed, and environment identity.

Use common random seeds, multiple training/evaluation seeds, confidence
intervals or paired uncertainty, and incident plus non-incident scenarios. A
policy frozen across infrastructure variants answers a different question from
a policy retrained for each variant; results must keep those designs separate.

## 8. Claims requiring caution

### GPU scaling

The email expects little system-wide benefit from GPU scaling because GPU
vehicles are rare and some small tasks may lose time to GPU overhead. This is a
plausible hypothesis, not established evidence for all VEC workloads. Prior MLP
experiments on edge devices do not alone establish the CPU/GPU crossover for
the task classes, batching, transfer, and queueing modeled here.

If investigated, measure task-size and batching crossover explicitly. Otherwise
keep GPU scaling outside the first study so it does not dilute the CPU-scaling
and admission-control contribution.

### Stable private WAN

A high-availability fibre backhaul is a reasonable primary scenario for managed
RSU clusters, but zero or negligible forwarding cost is still an assumption.
Use `--rsu-backhaul-ms` for a bounded sensitivity analysis rather than treating
the assumption as universal.

### Informal agent language

Phrases such as an agent “believes” an offload benefits the system are useful
intuition, but the technical claim is narrower: the policy was optimized under
a specific reward, observation, training distribution, and action-selection
contract. Evaluation must test whether that behavior generalizes.

## 9. LLM and agentic role

The predictive scaler should be a measurable forecasting/control model rather
than an unconstrained LLM controller. An LLM-based agent may add value by:

- assembling registered experiment requests;
- invoking approved deterministic tools;
- checking required provenance and missing evidence;
- comparing already-computed results; and
- explaining model outputs and limitations.

It must not calculate scientific metrics, invent findings, silently choose
unsupported configurations, or replace the forecast/controller evaluation.
Any analyst-assistance claim requires its own evaluation protocol.

## 10. Proposed research sequence

1. Preserve the supplied detailed Q&A in the authorised private evidence
   boundary, and obtain the sweep manifest, seed list, checkpoint identity, and
   raw/aggregate outputs.
2. Reproduce one current evaluator baseline and verify aggregate-versus-
   instrumented reconciliation.
3. Repeat the RSU-cap sweep under legacy and physical queue semantics.
4. Train the RSU-load observation ablation with common multi-seed design.
5. Evaluate fixed, static, reactive, and DLA infrastructure variants with a
   frozen actor.
6. Implement simple proactive forecast baselines and an oracle upper bound.
7. Evaluate held-out incident and non-incident scenarios, resource cost,
   robustness, and sensitivity to control delays and backhaul latency.
8. Only then consider joint retraining, richer prediction models, or learned
   target selection as clearly separate extensions.

## Coordination note

The email says Ethan may also work on an RSU load-management variant and copies
Yuxiang Wang. Before implementation or campaign execution, confirm who owns the
observation, dispatcher, reactive-scaling, and proactive-scaling variants. Use
disjoint branches, explicit variant names, shared metric definitions, and one
agreed seed/scenario matrix to prevent duplicated work or incomparable results.

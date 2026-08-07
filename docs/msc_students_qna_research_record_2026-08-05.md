# MSc Students Q&A Research Record — 5 August 2026

This document is a research-facing record of the technical answers supplied by
PhD student Randy Putra to S M Abdulla Al Mamun on 5 August 2026. The private
source was supplied as `MSc Students QnA.docx` and reviewed on 7 August 2026.
This record paraphrases the research content; it does not reproduce personal
message headers or commit the raw attachment.

Statements attributed to the Q&A remain reported design decisions or reported
results until the relevant code version, configuration, actor, seeds, commands,
and raw outputs have been reproduced. This record does not change any formal
TrafficTwin capability or evidence-gate status.

## Executive interpretation

The Q&A establishes a clearer intended model for RSU admission, queueing,
inter-RSU placement, and Kubernetes-style capacity control. It also separates
two learning problems:

1. the existing vehicle-side MAPPO policy chooses local, V2I, or V2V
   execution; and
2. a proposed infrastructure-side controller predicts RSU demand, scales CPU
   capacity, and dispatches admitted tasks among RSUs.

The strongest immediate research contribution is not further tuning of the
waiting-room limit. It is a controlled comparison of fixed, reactive,
deadline-aware, and proactive RSU resource management under explicit scaling
delay, followed by a separate vehicle-observation ablation if time permits.

## 1. RSU admission and capacity semantics

### Intended waiting-room meaning

The Q&A says that the variable historically named `RSU_MAX_CONCURRENT` counts
every task admitted to an RSU, including tasks waiting and being served. It is
an admission or in-flight task ceiling, not a measure of processing power and
not a literal worker count. A clearer formal name is therefore:

> per-RSU admission/in-flight task ceiling

The fleet-scaled limit is an experimental convention inherited from training:
50 seats for 20 vehicle slots, or `2.5 ×` the padded trace width. Randy states
that this scaling is intended to expose policies to comparable crowding across
scenarios; it is not a claim that physical RSU buffers grow with traffic.

For physical or cross-scenario interpretation, experiments should also use an
absolute per-RSU ceiling. The current evaluator provides `--rsu-cap-abs` for
that purpose.

### Processing-capacity meaning

The simulator does not model a separate collection of processor workers. It
models service capacity through a rate multiplier:

| Capacity level | Intended abstraction |
|---|---|
| `1×` | Conservative 4-core CPU allocation |
| `2×` | 8-core CPU allocation |
| `3×` | Full 12-core RSU allocation |

Within this abstraction, multiple workers are represented by a proportional
increase in aggregate service rate. Waiting-room capacity and computation rate
must therefore remain separate experimental variables.

## 2. Rejection and task lifecycle

When an RSU has no admission capacity, the intended outcome is immediate,
terminal rejection. The task is not retried, executed locally, redirected to
V2V, or forwarded again. The rationale given is that a task which cannot meet
its deadline is obsolete in the modelled dynamic environment.

The Q&A supports a fine-grained ledger in which every offered task can be
traced through its lifecycle. At minimum, a rejection record should identify:

- the decision second, substep, and vehicle or task identity;
- the reason, such as deadline gate, RSU capacity, vehicle queue, or no radio;
- the time of rejection;
- its latency-accounting convention;
- its energy-accounting convention; and
- the resulting deadline outcome.

Rejected work must never enter the RSU backlog, but it must remain visible in
the evaluation ledger. Aggregate conservation should reconcile offered work
with admitted, rejected, unavailable, completed, and unfinished outcomes.

Two completion populations must be reported separately:

- `completion`: successful tasks divided by all tasks generated or offered;
- `completion_admitted`: successful tasks divided by tasks admitted for
  service.

The Q&A also confirms that completion includes successful result return to the
source vehicle, rather than compute completion alone.

The current `vec_env` source implements much of this evaluator foundation,
including offered/admitted reporting, per-task lifecycle outcomes, rejection
reasons, and a work-conservation ledger. Exact field meanings must still be
verified against the output schema used in each campaign.

## 3. Reported waiting-room experiments

Randy reports testing fleet-scaled limits of `0.75×`, `2.5×`, `10×`, and
`40×`, as well as a fixed absolute ceiling of 500 seats. The Q&A reports no
change in task completion across those settings and attributes this to compute
service rate, rather than waiting-room size, being the limiting factor.

The related email supplies additional reported values for the incident-gridlock
case on 15 March 2024 from 20:00 to 21:00: completion `0.6943` throughout the
sweep, while mean latency rose from approximately `4.9 s` to `128.4 s` as more
tasks were admitted and left waiting. Those numbers are recorded and assessed
in the [email research analysis](randy_email_research_analysis_2026-08-07.md).

These are useful reported findings, but the DOCX contains no raw JSON or CSV,
seed list, checkpoint identity, executable command, or numerical result table.
They are not yet reproduced TrafficTwin evidence. The sweep must be repeated
under both legacy and physical work-conserving queue semantics before drawing
a final conclusion.

## 4. Within-second timing semantics

The intended evaluator timing is:

1. radio candidates and channel quality are refreshed once per one-second
   mobility interval;
2. task arrivals are divided into five 200 ms slices per second;
3. routing and admission are evaluated per individual task;
4. capacity reservations update immediately, so later tasks see earlier
   admissions; and
5. service drain follows the one-second compute clock and should remain
   conceptually continuous rather than depend on scheduler frequency.

Vehicles do not switch RSU associations within the same second because the
mobility trace contains one position per second. This timing contract should be
preserved unless a separately named higher-resolution model supplies evidence
for different radio dynamics.

## 5. Vehicle-side policy semantics

The current learned vehicle policy chooses an action family:

- local execution;
- V2I offloading; or
- V2V offloading.

The environment, not the learned policy, selects the exact eligible RSU or
vehicle using the strongest available channel. Signal strength is one input to
the collective policy objective; it is not the sole basis for choosing the
action family.

Action masking is intentionally disabled in the referenced baseline. If V2I or
V2V is infeasible, there is no automatic fallback. An action-masked policy is a
valid separate ablation, but it changes the decision contract and requires
separate training and labelling.

## 6. RSU-load observation ablation

Adding RSU load, queue, or backlog to the vehicle observation changes the model
input and therefore requires retraining. It creates a new model variant rather
than an evaluator-only switch.

The Q&A also raises an important counter-hypothesis: load information observed
by a moving vehicle may become stale quickly, while the vehicle cannot directly
scale RSUs or freely choose distant RSUs. Adding load could therefore push the
policy toward local execution without improving global outcomes. This is not a
reason to skip the experiment; it gives the ablation a falsifiable question:

> Does a normalized RSU-load observation improve offered-task completion and
> deadline performance without degrading energy, latency, or the useful
> Local/V2I/V2V decision balance?

Compare the existing observation against exactly one load-augmented observation
using common training budgets, traces, seeds, reward, and evaluation windows.
Report the full multi-seed distribution rather than the best checkpoint alone.

## 7. Infrastructure-side load management

The Q&A selects an Option-B architecture:

- Kubernetes manages worker deployment, health, and CPU allocation at each
  RSU;
- a fast application-level dispatcher performs admission and inter-RSU task
  placement; and
- an independent learning or predictive controller decides when and where to
  scale capacity.

Deadline-aware admission and dispatch are controller mechanisms, not features
that Kubernetes supplies automatically. They should be modelled and evaluated
separately from orchestration mechanics.

Kubernetes scaling is explicitly delayed. The Q&A identifies cumulative delay
from metrics collection and averaging, autoscaler evaluation, stabilization,
actuation, and control-plane communication. It gives approximately 15 seconds
as an initial scale-action assumption and motivates predicting load far enough
ahead to make capacity ready before a rush arrives. That duration is an
experimental assumption requiring sensitivity analysis, not a universal
Kubernetes constant.

GPU scaling remains outside the first campaign. The Q&A hypothesizes that it
will have limited system-wide value because GPU-equipped vehicles are a small
share of the fleet and small tasks may be dominated by GPU overhead. This is a
plausible hypothesis, not yet evidence for the present workload.

## 8. Inter-RSU placement and backhaul assumptions

The proposed first infrastructure model uses a managed private fibre WAN with:

- full-mesh, one-hop RSU connectivity;
- uniform forwarding cost;
- bandwidth treated as non-binding;
- a flat `--rsu-backhaul-ms 2` round-trip-equivalent cost when execution moves
  away from the ingress RSU;
- no task-size-dependent transfer time, forwarding energy, or packet loss;
- destination-side deadline and capacity admission;
- atomic destination reservation;
- no forwarding chain and no migration after enqueue; and
- result return included in the forwarding-cost abstraction.

Placement is decided before a task enters the ingress queue. With an
event-driven transport model, the recommended invariant is reserve-then-forward:
reserve capacity atomically at the destination, count the task in transit, and
never count it in the ingress queue. A non-zero `rejected_at_destination`
counter after reservation would indicate a broken or non-atomic reservation
contract.

These assumptions are suitable for a primary controlled experiment, but the
2 ms latency and non-binding bandwidth require bounded sensitivity tests before
generalising beyond a well-managed fibre cluster.

## 9. Freshness and staleness experiment

The infrastructure controller observes two different state types:

- admission uses the executing RSU's local queue and should be fresh; and
- placement uses other RSUs' state and may be stale.

The agreed evaluation order is perfect remote state first, followed by a
remote-state staleness sweep of `0`, `100`, `500`, and `1000 ms`. Admission
freshness must not be changed in that experiment. This isolates whether stale
cluster information harms placement without conflating it with local deadline
admission.

## 10. Controlled experiment sequence

The supervisor-aligned thread should proceed in this order:

1. **Reproduce one frozen baseline.** Record code and data commits, actor,
   seed, scenario, date, evaluation window, SUMO version, and environment.
2. **Verify the ledger.** Reconcile aggregate JSON with instrumented per-task
   outcomes and confirm work conservation.
3. **Repeat the admission-ceiling sweep.** Compare legacy clamp semantics,
   physical rejection semantics, fleet-scaled limits, and an absolute limit.
4. **Freeze the vehicle actor and compare infrastructure controllers.** Test
   fixed `1×`, static `3×`, reactive, deadline-aware, and combined variants.
5. **Add simple proactive baselines.** Begin with persistence, EWMA or moving
   average, and a small regression or gradient-boosted forecast; include an
   oracle future-load upper bound.
6. **Test control realism.** Sweep scaling delay, remote-state staleness, and
   fibre latency under incident and non-incident demand.
7. **Run the RSU-load observation ablation.** Retrain current and
   load-augmented variants with common multi-seed controls.
8. **Only then consider extensions.** Joint retraining, learned target
   selection, action masking, or richer temporal/graph models must be separate
   named experiments.

Every campaign should report offered and admitted completion, latency
distributions, energy, Local/V2I/V2V decision shares, rejection reasons,
work-conservation counts, backhaul use, mean capacity/core-seconds, scaling
events, scenario identity, actor variant, seed, and software/data identities.

## 11. What is available and what is still missing

### Available

- the authorised private `vec_env` and `tos-data` mirrors;
- the current evaluator with physical queueing, DLA/load-balancing, static and
  reactive scaling, lifecycle recording, and work-conservation foundations;
- frozen actor checkpoints and Manchester evaluation data in the private data
  boundary;
- local SUMO 1.27.1; and
- the email and detailed Q&A describing the intended research direction.

### Still required for reproduction

- the raw waiting-room sweep outputs;
- exact sweep commands or manifests;
- seed list and checkpoint identity;
- the software and data commits used for the reported numbers;
- a machine-readable result table supporting the reported completion and
  latency values;
- confirmed ownership boundaries with Ethan and Randy; and
- confirmation of the compute environment and accelerator allocation for new
  multi-seed training.

Possessing the source and attachment is enough to start the research workflow.
It is not yet enough to claim that Randy's reported experiment has been
reproduced.

## Related records

- [Research start status](research_start_2026-08-07.md)
- [Randy email research analysis](randy_email_research_analysis_2026-08-07.md)
- [VEC end-to-end research artifact](integration/vec_end_to_end_research_artifact.md)
- [TrafficTwin implementation status](implementation-status.md)

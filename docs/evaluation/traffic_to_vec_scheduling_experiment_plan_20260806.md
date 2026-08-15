# Traffic-to-VEC scheduling experiment plan

**Prepared:** 6 August 2026

**Status:** proposed research plan; not supervisor-approved, predeclared or executable.

## Central idea

TfGM and BODS traffic data do not contain computing tasks. They provide the real mobility and
traffic conditions in which a separately specified task-offloading system can be tested.

```text
Real traffic data
(counts, speeds and bus movement)
        ↓
Calibrated SUMO mobility
(vehicle routes, positions and density)
        ↓
Communication conditions
(RSU coverage, contact time, link quality and handovers)
        +
Explicit synthetic computing tasks
(arrival, size, CPU work and deadline)
        ↓
Offloading and RSU scheduling experiment
```

The contribution is therefore **real-traffic-informed mobility combined with controlled synthetic
computing tasks**. It is not a claim that TfGM observed real VEC tasks.

## Why traffic affects task scheduling

Vehicle position, speed and route influence:

- which RSUs and neighbouring vehicles are reachable;
- how long a vehicle remains inside RSU coverage;
- whether a result can return before the vehicle moves away;
- radio/link quality and transmission time;
- handovers between RSUs;
- the number of vehicles simultaneously competing for an RSU; and
- where RSU queue and load imbalances develop.

Congested traffic may create more simultaneous task generators and contention, while slower
vehicles may remain in coverage longer. Night traffic may reduce contention but shorten contact
time because vehicles move faster. These are competing hypotheses, not assumed outcomes.

ETSI's V2X MEC specification treats mobility, dynamic topology, radio information and location as
relevant to service operation. Vehicular-offloading research likewise identifies RSU switching,
limited edge resources and vehicle movement as sources of delay or offloading failure:

- [ETSI MEC V2X specification](https://www.etsi.org/deliver/etsi_gs/MEC/001_099/030/03.03.01_60/gs_MEC030v030301p.pdf)
- [Trajectory-aware task-offloading study](https://doi.org/10.1016/j.dcan.2024.08.003)
- [Joint computation offloading and resource allocation](https://doi.org/10.1016/j.dcan.2022.12.002)

## Traffic-data limitations

Detector counts do not provide the route of every individual car. SUMO must construct plausible
vehicles and routes from counts, turn counts, origin/destination evidence or declared modelling
assumptions. Different route sets may reproduce the same detector counts, particularly in a city
network. SUMO documents this as an underdetermined demand-generation problem:

- [SUMO routes from observation points](https://sumo.dlr.de/docs/Demand/Routes_from_Observation_Points.html)
- [SUMO vehicle and route definitions](https://sumo.dlr.de/docs/Definition_of_Vehicles%2C_Vehicle_Types%2C_and_Routes.html)

BODS can constrain bus movement, but the project's observed cadence was approximately 66–68
seconds, so its derived one-second traces required substantial interpolation.

General traffic and buses must not be double-counted. If TfGM totals already include buses,
explicit BODS buses cannot simply be added on top. The design must use class-separated counts or
treat the explicit buses as part of the calibrated total.

## Research questions

1. Can a bounded SUMO scenario reproduce held-out TfGM counts and/or speeds?
2. How do night and peak mobility change V2I/V2V contact and RSU load?
3. Does deterministic load-aware RSU dispatch improve task outcomes over no forwarding?
4. Is any scheduler benefit limited to saturated traffic/task regimes?
5. Does a learned scheduler improve on deterministic baselines under matched information and
   compute budgets?

## Experiment programme

| Experiment | What changes | What remains matched | Intended finding |
|---|---|---|---|
| 1. Traffic validation | Observed versus SUMO counts/speeds | Area, sites and intervals | Whether the mobility model is adequate |
| 2. Mobility-only | Night versus peak trace | Global task stream and scheduler | Effect of movement/contact conditions |
| 3. Natural system load | Same task rate per vehicle | Task model and scheduler | Combined density and task-volume effect |
| 4. Scheduler comparison | No forwarding, least-loaded and earliest-completion | Trace, tasks and seeds | Load-balancing benefit or harm |
| 5. Learned scheduler | Learned versus deterministic policy | State, actions, seeds and budget | Whether learning adds value |

The mobility-only and natural-load experiments must remain separate. Otherwise, the effect of
vehicle movement is confounded with the effect of generating more tasks from more vehicles.

## Stage 1 — Traffic construction and validation

Use a small, predeclared Manchester area and separate observation windows, for example:

- night/free-flow;
- morning peak;
- evening peak; and
- optionally one incident or event period.

Use TfGM counts/speeds to calibrate general traffic and BODS evidence to constrain buses. Split
observations into development and held-out windows. Compare compatible observed and simulated
intervals using coverage, exclusions, residuals and an approved MAE/RMSE or other predeclared
metric.

This stage answers only whether SUMO reproduces the selected traffic evidence. It makes no
task-offloading claim.

## Stage 2 — Synthetic task overlay

Generate controlled tasks for declared connected vehicles with:

- arrival time;
- input and output size;
- required CPU work;
- deadline;
- task class; and
- local-computing capability.

The existing T1/T2/T3 model may be reused only if its semantics remain fixed and cited. Task
arrivals, sizes and deadlines must be predeclared and identical across scheduler comparisons.
They must be labelled synthetic; TfGM cannot supply them.

## Stage 3 — Complete VEC lifecycle

Before scheduler comparisons, instrument each task through an explicit work-conserving lifecycle:

```text
offered → action selected → ingress target
→ admitted/rejected → retained/forwarded
→ execution started → completed/dropped
→ result returned → deadline met/missed
```

Record task, ingress RSU, execution RSU, rejection/drop reason, transmission, forwarding, queue,
compute and return times. No offered task may disappear through aggregate backlog accounting.

## Stage 4 — Deterministic scheduler comparison

Start with:

1. no forwarding;
2. least-loaded eligible RSU; and
3. predicted-earliest-completion RSU, including transfer, queue, compute and return cost.

Use reservations so simultaneous decisions cannot all select the same apparently free capacity.
Run every scheduler on identical traffic bytes, task arrivals and seeds.

Measure:

- offered, admitted, rejected, dropped and returned tasks;
- throughput and physical-return rate;
- modelled deadline attainment;
- p50/p95/p99 end-to-end latency;
- queue waiting time and age;
- forwarding rate, delay and energy;
- handover/contact-loss failures; and
- per-RSU utilisation and load balance.

## Stage 5 — Learned scheduling

Train a learned scheduler only after the deterministic baseline works. It should receive the same
task, RSU-load, service-rate, link, contact-time, forwarding-cost and telemetry-age information
available to the strongest deterministic baseline.

Frozen-actor downstream forwarding does not require retraining. An actor that observes RSU
load/capacity or directly chooses the execution RSU does require retraining and is a separate
experiment.

## Primary hypotheses

- Load-aware forwarding will help most when both traffic density and task demand create RSU
  saturation or imbalance.
- Forwarding may add unnecessary cost in unsaturated/night conditions.
- Route/contact-time information may reduce result-return failures.
- A learned scheduler may or may not outperform deterministic scheduling; a null result is
  publishable.

## Claims that remain unavailable

- that road traffic observations contain real computing-task demand;
- that a scheduler makes physical roads less congested or vehicles faster;
- that lower modelled latency proves faster computation or physical completion;
- that generated analysis sites are deployed RSUs;
- that a Manchester-calibrated SUMO trace validates a VEC actor automatically; and
- that a learned scheduler is superior before a matched comparison exists.

Traffic affects the computing experiment. The computing scheduler does not change road congestion
unless a separate, explicitly modelled closed-loop traffic-control intervention is introduced.

## Relationship to completed work

The existing B-BUS experiment already combined captured bus mobility with synthetic tasks and
generated infrastructure. It proved the pipeline but not a clean rush-hour scheduling effect:
trajectories were heavily interpolated, full traces failed the placement bound, and the successor
designs did not provide an endpoint-equivalent dawn-versus-peak comparison.

This plan corrects those limitations through held-out traffic validation, matched task streams,
complete task-lifecycle accounting and deterministic scheduling baselines before learned
scheduling.

Related repository records:

- [Live-bus and Colab experiments](live_bus_and_colab_experiments_20260806.md)
- [TfGM measured-traffic experiment brief](tfgm_measured_traffic_experiment_brief_20260806.md)
- [Current scheduling audit](../current_status_5_6_pro_analysis.md)

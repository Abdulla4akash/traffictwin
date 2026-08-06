# TrafficTwin publication directions — reviewed and corrected

**Original proposal:** Meta Muse Spark 1.2, 6 August 2026<br>
**Review date:** 6 August 2026<br>
**Status:** planning guidance only; not supervisor approval, publication approval, a signed
predeclaration or authority to release data, artifacts, software or tags

This revision replaces the original claim that several papers are immediately publishable. It
reconciles the proposal with the complete experiment history, the capacity-semantics correction
and Supervisor Meeting 4:

- [complete experiment history](evaluation/complete_experiment_history_20260806.md);
- [current 5.6 Pro interpretation audit](current_status_5_6_pro_analysis.md);
- [Supervisor Meeting 4](evaluation/supervisor_meeting_4_20260806.md); and
- [future research directions v2](research_directions_v2.md).

Implemented software, passing tests and complete documentation are valuable foundations. They do
not by themselves establish research novelty, external validity, venue fit, publication rights or
a scientifically supported result.

## Recommended primary direction

### Freshness-aware, work-conserving RSU task scheduling

**Research question**

> Under which traffic, task-load, RSU-load and telemetry-freshness conditions do strongest-link
> selection, deterministic load-aware dispatch and learned scheduling help, tie or harm?

The existing 17-dimensional MAPPO actor chooses local, V2I or V2V. It does not observe configured
RSU capacity, RSU load, queue/in-flight state or telemetry age. The environment selects the V2I
RSU using strongest/best-link logic. Therefore, the existing result is a limitation of the supplied
observation/action/environment design, not proof that MAPPO generally cannot schedule well.

The required sequence is:

1. **Clarify and instrument the complete task lifecycle and work-conservation semantics.** Record
   offered, selected, admitted/rejected, retained/forwarded, started, completed/dropped, returned
   and deadline-met/missed states. Validate one hand-checkable two-RSU case.
2. **Implement and test deterministic application-level dispatch/forwarding.** Compare no
   forwarding, strongest-link, least-loaded and predicted-earliest-completion rules with explicit
   forwarding and return costs. The frozen actor can be retained; this treatment does not require
   retraining.
3. **Compare a learned scheduler afterward.** Give the learned scheduler the same eligible nodes,
   state, telemetry age, task information and cost model as the deterministic baseline.
4. **Treat capacity-aware actor retraining as a separate experiment.** Adding RSU load, capacity,
   headroom or telemetry age changes the actor observation contract and requires retraining. It
   must not be conflated with frozen-actor forwarding.

The intended result is a **condition map**, not one universal winner. Primary factors should be
varied one at a time before a small predeclared interaction study:

- task arrival rate and task class;
- genuine RSU service rate;
- RSU count and placement;
- background load;
- telemetry age and missing state;
- forwarding/return cost; and
- traffic regime and contact time.

At least two RSUs must be genuinely eligible, and the scenario must create a real trade-off between
link strength, current load, contact duration and forwarding cost.

## Required interpretation of existing capacity evidence

The `2.5` to `0.75` intervention changed a **per-RSU admission/in-flight concurrency ceiling**. It
did not reduce computation power, processor speed, service rate, worker count or bandwidth.

The held-out experiment confirmed a reduction in mean **modelled** latency, but:

- keyed actor decisions remained unchanged;
- modelled deadline attainment remained essentially flat;
- median latency remained near 44.3 ms;
- the change was concentrated in the already-deadline-failed extreme tail; and
- complete offered-to-returned lifecycle accounting is unavailable.

Consequently, the result is not evidence of faster computation, improved physical completion or a
proved fail-fast mechanism. It motivates lifecycle instrumentation and load-aware scheduling.

## Role of TfGM, BODS and SUMO evidence

Traffic data supplies **mobility conditions**, not computing-task observations:

```text
traffic counts, speeds and bus movement
→ routes, positions, density, contact time and handover
+ explicitly synthetic task workload and simulated RSU/radio assumptions
→ task-offloading and scheduling experiment
```

TfGM/BODS rows must never be described as observed edge-computing tasks. Buses may support a
real-data-informed mobility scenario, but task arrivals, payloads, CPU work, deadlines, compute
nodes and radio/queue behaviour remain synthetic unless separately observed.

## Secondary publication possibilities

### 1. Task-lifecycle measurement and misleading aggregate latency

**Potential contribution:** demonstrate how incomplete lifecycle accounting and tail-dominated
means can produce an apparently favourable latency result without evidence of faster computation
or better physical completion.

This becomes a defensible paper only after the evaluator records the complete lifecycle and the
study compares lifecycle-aware endpoints against aggregate latency. The present evidence supports
the motivation and limitation, not the final mechanism.

### 2. TrafficTwin research-software paper

The import-first, deterministic, provenance-aware platform may support a software paper. Candidate
contributions include explicit unavailable states, permission-aware research objects, bounded
provenance and reproducible evidence contracts.

This is **not currently unblockable**. Before selecting a software venue, the project needs:

- an approved project licence compatible with the intended venue;
- a public repository containing only material authorised for public release;
- an archived release and stable citation record;
- a related-work comparison establishing need and distinction; and
- a concise, independently reproducible software evaluation.

Private VEC-derived artifacts are not required for a platform paper and must not be released merely
to strengthen it.

### 3. Evidence-gated reproduction of an external VEC evaluator

The pinned-source audit, occupancy-bounded identity, typed runner, reproduction tolerance and
explicit unavailable outcomes form a potentially useful reproducibility case study.

It requires an updated manuscript based on the complete August experiment record and permission
review. A checksum proves identity, not scientific truth or publication rights. No private source,
checkpoint, raw trace or restricted row-level artifact may be attached without explicit written
authority.

### 4. Provenance, statistics and diagnostic components

The provenance, paired-study, equivalence, regression-gate, mutation and deterministic-diagnostic
components are strong supporting methods. They should initially strengthen the primary scheduling
study or software paper. Separate papers would require a focused novelty claim, comparison with
existing methods and an evaluation beyond demonstrating that the implementation works.

## Directions to defer

The following are not presently justified as stand-alone publication claims:

- an official-source audit described as a new open dataset;
- a durable operational-history paper before a real retention policy and real execution exist;
- observed-to-SUMO calibration results while human mapping review, uncertainty approval and a
  gridlock-free calibrated demand remain incomplete;
- a Manchester traffic-effects paper based only on synthetic fixtures;
- physical-completion, throughput, confirmed-transfer or per-task-energy results not recorded by
  the evaluator; and
- causal claims about traffic, scheduling or policy effects without an appropriate design.

The source-audit, operational-history and mapping work can remain dissertation methodology or
future work until their data, validation and release requirements are satisfied.

## Publication and release boundaries

- Do not publish or redistribute the pinned external repositories, checkpoints, raw traces,
  private source identities, credentials, machine paths or restricted row-level information.
- Do not publish VEC-11/VEC-12 or another Randy-derived artifact merely because it is checksummed,
  pseudonymised or stored in a private workflow. Follow the governing publication manifest and
  written permission exactly.
- Do not move or create release tags, publish a Zenodo archive or change a publication manifest as
  part of this planning document.
- Do not describe `task_met` as eventual physical completion.
- Do not describe `veh_best_rsu = -1` as a confirmed transfer failure.
- Do not describe generated analysis sites as observed physical RSUs.
- Keep every result within its actual evidence ceiling: descriptive/non-causal and not
  supervisor-approved unless separately recorded.

## Recommended publication sequence

1. Complete lifecycle/work-conservation semantics and the hand-check validation.
2. Run the deterministic dispatcher comparison.
3. Run the learned-scheduler comparison on selected boundary conditions.
4. Decide whether the result supports one scheduling paper or a dissertation-only study.
5. Consider a separate capacity-aware actor-retraining study.
6. Prepare a TrafficTwin software paper only after licensing, public-release and related-work gates
   are closed.
7. Treat the lifecycle/latency-accounting paper as a secondary opportunity after the missing
   outcomes are instrumented.

## Bottom line

The strongest current publication direction is not a collection of independent platform papers.
It is one coherent study of **RSU scheduling under incomplete and stale distributed state**, built
on complete lifecycle accounting and compared first against a deterministic baseline. TrafficTwin's
software, provenance and statistical machinery should support that study. They should not replace
the scientific question.

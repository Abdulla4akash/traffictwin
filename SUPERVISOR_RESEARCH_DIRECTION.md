# Current Supervisor Research Direction

This is the prominent agent-facing record of the current research direction
given directly by supervisor Sandra Sampaio. It is based on Sandra's message in
the Outlook thread **“Week 4 progress: a confirmed finding overnight, and two
scoping questions”**, sent to S M Abdulla Al Mamun on 4 August 2026 at 22:19,
with Randy Putra copied.

The message is paraphrased here rather than reproduced with private mailbox
metadata. It is a supervisor-direction record, not experimental evidence, and
does not change any formal TrafficTwin implementation or evidence-gate status.

## Read this first

Any agent planning or implementing the supervisor-aligned VEC research thread
must read this record before the later Randy email and Q&A records.

The source hierarchy is:

1. **Sandra's email:** defines the research problem and requested investigation.
2. **Randy's email and Q&A:** clarify current simulator semantics, report prior
   experiments, and propose implementation details and extensions.
3. **Inspected source:** establishes what the current `vec_env` code actually
   implements.
4. **Reproduced outputs:** are required before reported numerical results become
   accepted TrafficTwin evidence.

Do not silently promote Randy's proposed implementation details into direct
supervisor requirements, and do not treat Sandra's expected outcomes as
confirmed results.

## Sandra's correction to the capacity experiment

The exploratory result had been described as tightening per-vehicle edge
capacity by approximately `3.3×`, leaving deadline attainment unchanged while
reducing mean latency. Sandra relayed Randy's inspection that this
interpretation was incorrect:

- the changed parameter was the RSU queue or waiting-room ceiling;
- it was reduced from the `2.5×` default to `0.75×`;
- the parameter controls how many tasks may wait at an RSU;
- it does not represent RSU processing power; and
- reduced latency with unchanged completion is most likely a fail-fast
  accounting effect caused by quicker rejection.

Therefore, queue admission capacity, compute service rate, and available CPU
cores must remain separate variables in every experiment and report. No agent
may describe a waiting-room reduction as a computation-capacity reduction.

## Research problem identified by Sandra

Sandra identifies missing RSU capacity awareness and load management as the
substantive problem:

- the vehicle-side MAPPO offloading policy does not adequately account for
  current RSU capacity;
- rapidly changing RSU state may become stale before a vehicle can use a
  capacity broadcast;
- strongest-link offloading can concentrate work at RSUs near congested roads;
  and
- farther RSUs may remain idle while nearby RSUs become bottlenecks.

The research opportunity is to redistribute work within the RSU infrastructure
and test whether doing so improves completion under both congested and
free-flow conditions.

## Investigations requested by Sandra

Sandra asks for the following approaches to be investigated and compared.

### 1. Deterministic infrastructure load balancing

> DRL-based task offloading + deterministic Kubernetes-style load balancing

Keep the existing vehicle-side offloading actor frozen. After a vehicle chooses
V2I and sends a task to the strongest-link ingress RSU, an infrastructure
mechanism may forward it to a quieter RSU. This is intended as a no-retraining
baseline that isolates the effect of infrastructure-side load management.

Sandra described this as Kubernetes load balancing. In the simulator and
architecture, preserve the more precise separation established by the later
Q&A: Kubernetes manages compute resources and worker deployment, while an
application-level dispatcher performs deadline-aware task placement among RSUs.
Do not claim Kubernetes natively implements the research scheduler.

### 2. Learned RSU scheduling and load balancing

> DRL-based task offloading + DRL-based scheduling/load balancing

Train a separate infrastructure-side learning model to decide which RSU should
execute a task. Keep its observation, action, reward, authority, training data,
and relationship to the vehicle actor explicit. It must be compared with simple
deterministic baselines rather than evaluated in isolation.

### 3. AI-based Kubernetes control

> DRL-based task offloading + AI-based Kubernetes load balancing

Investigate an intelligent controller for infrastructure resource management.
The later Q&A develops this into delayed, proactive CPU scaling and identifies
fixed, static, reactive, deadline-aware, predictive, and oracle controllers as
candidate comparisons. Those are implementation proposals that operationalise
Sandra's requested direction; they are not yet reproduced results.

## Experimental interpretation

The supervisor email supports three distinct questions:

1. **Placement:** Can tasks be moved from an overloaded ingress RSU to another
   RSU without missing their deadlines?
2. **Capacity:** When should an RSU activate additional CPU service capacity?
3. **Learning:** Does a learned controller improve completion or resource use
   beyond deterministic placement and reactive scaling?

Do not change placement, capacity, the vehicle observation, and the learned
actor simultaneously in the first experiment. Each intervention needs a
separate variant so its effect remains identifiable.

## Minimum comparison sequence

1. Reproduce one frozen vehicle-policy baseline.
2. Verify offered/admitted/rejected/completed task conservation.
3. Establish fixed `1×` and static `3×` compute-capacity baselines.
4. Add deterministic inter-RSU placement with the vehicle actor frozen.
5. Add deadline-aware admission and compare it separately and jointly with
   placement.
6. Compare reactive scaling against the fixed and static baselines.
7. Add simple proactive prediction and an oracle upper bound.
8. Only then test a learned dispatcher, joint retraining, action masking, or an
   RSU-load-augmented vehicle observation as separately named variants.

Every result must state the scenario, date and evaluation window, actor and
controller variant, seed, checkpoint, code and data commits, SUMO version,
queue semantics, capacity semantics, and all relevant controller parameters.

## Success measures

The primary test is whether infrastructure load management improves completion
over all offered tasks. Reports must also include:

- completion over admitted tasks;
- latency distribution and deadline-met latency;
- energy with a declared accounting boundary;
- Local/V2I/V2V decision shares;
- rejection and unavailability reasons;
- offered/admitted/rejected work conservation;
- inter-RSU forwarding count and cost;
- capacity multiplier or core-seconds; and
- scaling events and time spent at each capacity.

An expected improvement stated in an email is a hypothesis. Only reproduced,
multi-seed outputs can establish whether the improvement occurs.

## Current evidence boundary

The authorised private `vec_env` and `tos-data` mirrors, local SUMO, detailed
Q&A, and current evaluator are available. The raw waiting-room sweep outputs,
exact commands, seed list, checkpoint identity, and machine-readable numerical
table supporting the reported values remain missing.

The project can start implementation and fresh experiments now. It cannot yet
claim reproduction of Randy's reported waiting-room result.

## Supporting records

- [Research start status](docs/research_start_2026-08-07.md)
- [Randy email research analysis](docs/randy_email_research_analysis_2026-08-07.md)
- [MSc Students Q&A research record](docs/msc_students_qna_research_record_2026-08-05.md)
- [Formal implementation status](docs/implementation-status.md)

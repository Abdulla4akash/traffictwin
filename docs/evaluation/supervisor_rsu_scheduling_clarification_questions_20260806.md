# Supervisor clarification questions: RSU scheduling direction

**Meeting with:** Sandra

**Prepared:** 6 August 2026

**Purpose:** Agree the architecture, experimental sequence and minimum dissertation scope before
any RSU scheduling implementation begins.

## Opening statement

> I understand your central correction: the `2.5` to `0.75` intervention changed a per-RSU
> admission/in-flight concurrency ceiling, not computation power. The lower mean modelled latency
> came from compression of the extreme, already-deadline-failed tail under incomplete task-lifecycle
> accounting; it is not evidence of faster computation or improved physical completion. I would
> like to confirm the intended load-balancing architecture and dissertation scope before I
> implement anything.

## Priority questions for Sandra

1. **Meaning of “Kubernetes load balancing”**

   When you say “Kubernetes load balancing,” do you mean an actual Kubernetes prototype, a
   Kubernetes-inspired application-level dispatcher inside the VEC simulation, or only a
   conceptual analogy?

   **Decision/notes:**

2. **Where the execution RSU is selected**

   Should a vehicle's V2I task first enter the best-link RSU and then be forwarded, or should a
   dispatcher directly select the final execution RSU?

   **Decision/notes:**

3. **Order of the research work**

   Do you agree with the following sequence?

   1. Repair and instrument complete task-lifecycle and work-conservation semantics.
   2. Test deterministic forwarding with the existing frozen offloading actor.
   3. Compare a learned scheduler afterward.
   4. Treat capacity-aware actor retraining as a separate experiment.

   **Decision/notes:**

4. **Minimum dissertation contribution**

   Is corrected lifecycle accounting plus a deterministic scheduler comparison sufficient as the
   minimum dissertation contribution, with a learned/DRL scheduler treated as an extension, or is
   a learned scheduler required?

   **Decision/notes:**

5. **Retraining boundary**

   Do you agree that downstream forwarding can be evaluated with the existing frozen actor, while
   an actor that observes RSU load/capacity or directly selects the execution RSU must be retrained?

   **Decision/notes:**

6. **Primary success measures**

   Which outcomes should define success: physically returned tasks, deadline success, explicit
   rejection rate, admitted throughput, latency percentiles, forwarding delay, energy cost or
   bandwidth cost? Which should be the primary endpoint?

   **Decision/notes:**

7. **Evaluation scenarios and expected nulls**

   Should the saturated incident trace be the primary case, with an unsaturated weekend or event
   trace as a control? Is a null result in the unsaturated case acceptable, given that forwarding
   may add overhead when RSUs are not saturated?

   **Decision/notes:**

8. **Forwarding-cost model**

   Which forwarding assumptions must the simulation represent: RSU topology, transfer latency,
   bandwidth, energy, reliability, return path and maximum forwarding depth?

   **Decision/notes:**

## Permission to clarify producer semantics

Ask Sandra whether the following questions should be sent to Randy before implementation:

> May I ask Randy to confirm exactly what `RSU_MAX_CONCURRENT` counts and what happens to work above
> that limit: explicit rejection, dropping, queuing elsewhere, retrying, local execution,
> forwarding or another state? I would also ask whether every offered task is intended to terminate
> in exactly one recorded lifecycle state.

**Sandra's decision/notes:**

## Decisions required before implementation

The meeting should ideally end with explicit answers to these three scope-defining points:

1. Simulation-only dispatcher or an actual Kubernetes prototype.
2. Best-link ingress plus forwarding or direct final-RSU selection.
3. Learned scheduler required for the dissertation or optional after the deterministic baseline.

This document records questions and meeting decisions only. It does not approve an experiment,
change the standing of existing evidence or authorise implementation.

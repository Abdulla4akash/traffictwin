# Supervisor-directed RSU scheduling: build and blocker audit

**Audited:** 6 August 2026
**Repository state:** `agent/current-status-5-6-pro-analysis` at
`c098ef85baa7cf6464c8fe04db46ce69d83d87f1` before this report
**Status:** implementation audit and planning record only; not supervisor approval, an executable
experiment, a predeclaration or authority to alter the pinned external repositories

## Bottom line

TrafficTwin has strong execution, evidence, experiment-management and planning foundations, but
the new RSU scheduling system discussed after Supervisor Meeting 4 is **not implemented**.

The existing audited evaluator can replay a frozen actor that chooses local/V2I/V2V while
environment logic selects the strongest-link RSU. TrafficTwin can run that evaluator safely,
validate its current outputs, admit completed campaign cells and analyse matched experiments. It
does not yet record a complete task lifecycle, conserve every offered task through a terminal
state, forward work between RSUs, select a least-loaded or earliest-completion RSU, model telemetry
age, or run a learned execution-RSU scheduler.

Using the eight-stage research sequence below as a simple planning count:

- **2 stages are complete:** existing-limitation diagnosis and written experiment design;
- **1 stage is partial:** load-aware actor feasibility has private non-admitted diagnostic evidence;
- **5 stages are not built or executed.**

That is **25% complete by unweighted stage count**, with one additional partial stage. This is not
an earned-value or effort estimate. More importantly, **0 of the 4 core new software milestones**
is complete: task-lifecycle instrumentation, the two-RSU validator, deterministic RSU dispatch,
and learned RSU scheduling.

## What the supervisor-relevant direction is

The defensible TrafficTwin contribution is a comparison of decision paths under incomplete and
ageing distributed state:

1. existing strongest-link selection;
2. no forwarding;
3. least-loaded eligible RSU dispatch;
4. predicted-earliest-completion dispatch with transfer, queue, compute and return costs;
5. a learned scheduler using the same information and costs; and
6. separately, a retrained actor that observes RSU load/capacity/headroom or chooses the execution
   RSU directly.

The intended outcome is a condition map showing when each method helps, ties or harms. It is not a
claim that MAPPO generally failed or that one algorithm must win.

The detailed parameter-plan, RSU-count-graph and rapid-repair comments in Meeting 4 were primarily
directed to Ethan during his presentation. They must not all be attributed to Abdulla. The wider
problem of strongest-link selection, hidden/stale load state and deterministic-versus-learned RSU
scheduling is nevertheless directly relevant to TrafficTwin's research direction.

## Verified build inventory

| Required surface | Verified state | What is actually present | What it does not provide |
|---|---|---|---|
| Audited VEC execution | **Built, bounded** | `integration/vec_runner` verifies the exact audited evaluator, two pinned 17-dimensional actors, reviewed traces, runtime, inputs and output hashes before publishing a terminal receipt. | It cannot load a new scheduler or actor dynamically and is not a training system. |
| Current evaluator reference path | **Built upstream and safely runnable** | The actor emits local/V2I/V2V; the evaluator selects the V2I target by link-quality `argmax`; queue/load state is updated and drained in aggregate. | It has no explicit execution-RSU dispatcher or inter-RSU forwarding policy. |
| Existing output contract | **Built for current outputs** | The TOS v2 contract validates per-step state/action arrays and per-task `task_active`, `task_lat_ms`, `task_met` and `task_type`. | `task_met` is deadline attainment. The contract has no offered/admitted/rejected/started/finished/returned lifecycle, execution-RSU identity, drop cause or forwarding record. |
| Campaign execution and admission | **Built, bounded** | Digest-bound campaign design, sequential execution, receipt reuse, registry admission, paired analysis and offline verification exist. The capacity programme completed 154 fresh-run cells across its campaign family. | These services cannot manufacture lifecycle fields absent from evaluator output or turn a proposed scheduler into an executable one. |
| Existing limitation diagnosis | **Complete for the audited design** | Keyed actions are identical across capacity arms; the 17-dimensional actor does not receive the changed RSU capacity/load state; load asymmetry and tail compression are documented. | This is not a general MAPPO verdict and does not prove a complete rejection/fail-fast mechanism. |
| Capacity-aware feasibility | **Partial, diagnostic only** | Private B-CAP 17-D versus 19-D training diagnostics show that a retrained policy supplied with capacity/headroom information can change its decisions. | The actors are not admitted, the outputs are non-admitted diagnostics, and responsiveness was not shown to improve physical completion. |
| Benchmark protocol tooling | **Built as protocol/package only** | The post-v1 benchmark code enumerates unsigned factorial jobs, validates contracts and runs a tiny deterministic synthetic fixture. | Its own source fixes `training_allowed=false`, `scientific_execution_allowed=false` and `evidence=false`; it has no real actor loader, optimiser, scheduler client, cloud submission or scientific campaign. |
| Scenario lifecycle service | **Built, but different lifecycle** | The platform service links scenario drafts, approval artifacts, receipts, analyses and human admission records in an append-only registry. | This is experiment-artifact lifecycle, not the offered-to-returned lifecycle of an individual computing task. |
| Kubernetes deployment | **Not built and not required first** | No Kubernetes task-dispatch implementation or Kubernetes dependency was found. | Kubernetes would not itself define the per-task VEC scheduling rule. The first implementation should be an application-level deterministic dispatcher. |

Focused verification of the existing foundations passed:

```text
118 passed in 13.86s
```

The focused set covered the current TOS output contract, VEC runner unit/integration paths,
benchmark protocol/package and scenario-lifecycle service.

## Stage-by-stage completion

| Stage | Required result | Status | Completion evidence or missing work |
|---|---|---|---|
| 1. Diagnose the existing limitation | Show what the actor observes/chooses and what environment logic chooses | **Complete** | Source audit, keyed-action identity and observability-gap evidence exist. |
| 2. Freeze the research design | Define factors, constants, hypotheses, endpoints and sequence | **Complete as a proposal** | Meeting-4 record and traffic-to-VEC plan exist; neither is a signed predeclaration. |
| 3. Complete task lifecycle | Record offered → selected → admitted/rejected → retained/forwarded → started → completed/dropped → returned → deadline state | **Not built** | Current per-task contract has only activity, modelled latency, deadline attainment and type. |
| 4. Hand-checkable two-RSU validation | Busy strong-link RSU, idle weaker-link RSU, explicit reservations/costs and conserved tasks | **Not built** | No matching source module or test exists. |
| 5. Deterministic dispatcher | Existing/no-forwarding, least-loaded and predicted-earliest-completion policies | **Not built** | No dispatcher/scheduler source or tests exist; target selection remains strongest-link `argmax`. |
| 6. Matched deterministic experiment | Same mobility, tasks, seeds, placement and costs across policies | **Not executed** | No signed scheduler predeclaration, campaign receipt, registry evidence or result exists. |
| 7. Learned execution-RSU scheduler | Learned policy compared with the strongest deterministic baseline under matched information/budget | **Not built** | Benchmark packaging is contract-only and synthetic; there is no real learned scheduler implementation. |
| 8. Capacity-aware actor retraining | Formal separately admitted treatment with changed observation/action contract | **Partial diagnostic only** | B-CAP feasibility ran privately, but no actor admission or matched admitted performance study exists. |

## What is keeping the core system from being built

### A. Semantic decisions needed before changing the evaluator

The upstream producer still needs to confirm, or the owner must explicitly freeze provisional
assumptions for:

- the formal meaning of `RSU_MAX_CONCURRENT`;
- how above-ceiling work is recorded and scored;
- whether all offered work must be conserved;
- the distinction between queued, executing, finished and returned work;
- the genuine service-rate/worker model;
- action-mask intent;
- direct execution-RSU selection versus ingress-RSU forwarding; and
- forwarding topology, transfer/return latency, bandwidth, energy, reliability and maximum depth.

Without these decisions, code could be written, but its scientific meaning would be arbitrary.
The first two-RSU fixture can proceed only under clearly recorded provisional assumptions if the
owner chooses not to wait for producer answers.

### B. The current data contract cannot express the required outcomes

`PERTASK_KEYS` currently contains only:

```text
task_active, task_lat_ms, task_met, task_type
```

A versioned successor must add stable task identity and mutually reconciling lifecycle events or
terminal states. At minimum it needs ingress RSU, execution RSU, admission outcome, rejection/drop
cause, queue/start/finish/return timing and forwarding count/cost. The admission and analysis
layers then need matching validators and metrics. Adding only a scheduler without this ledger
would repeat the current interpretation problem.

### C. Target selection is embedded inside the pinned evaluator

The audited evaluator computes all V2I qualities and immediately chooses the target with
link-quality `argmax`. There is no scheduler interface at that boundary. A new implementation must
introduce an explicit, deterministic policy contract receiving the eligible-RSU set, link/contact
information, load/service state, reservations, telemetry timestamps and task requirements.

TrafficTwin currently executes hash-pinned blobs from the audited external commit. The external
repositories must remain unmodified in this worktree. A scheduler therefore requires a new,
explicitly scoped implementation branch and one of these reviewed routes:

1. an upstream-authorised new external revision with new audited hashes; or
2. a new TrafficTwin-owned evaluator/adapter boundary whose semantics, provenance and equivalence
   limits are reviewed independently.

It cannot be slipped into PR #2, which is documentation-only.

### D. The runner is intentionally fixed to the historical actor contract

The current runner accepts two actor identifiers and verifies a `17-64-64-3` checkpoint shape.
Adding load/capacity/headroom or telemetry age changes the observation width; allowing the actor to
choose a specific RSU also changes the action contract. Formal retraining therefore needs:

- a versioned observation and action definition;
- training code and a frozen training protocol;
- checkpoint-selection rules and independent training seeds;
- reviewed actor/evaluator hashes and shapes;
- fresh matched evaluation seeds; and
- a separate actor-admission decision.

The private 19-dimensional B-CAP diagnostics prove feasibility only; they cannot be inserted into
the current admitted runner as if already reviewed.

### E. The deterministic experiment still needs a scientific contract

Before a campaign, the owner must freeze:

- the two-RSU fixture and broader eligible-RSU construction;
- queue discipline, reservations and simultaneous-arrival handling;
- genuine service-rate levels, distinct from the admission ceiling;
- forwarding/return cost and failure semantics;
- telemetry timestamp, age, refresh and missing-state rules;
- task-arrival, payload, CPU-work and deadline distributions;
- primary lifecycle/physical-return endpoint and secondary metrics;
- matched seed roles, budget, stopping rules and deviation policy; and
- the exact null/negative-result reporting rule.

The existing unsigned 2,400-job capacity/multi-algorithm proposal is broader than the minimum
deterministic study and does not authorise execution.

### F. Operational blockers after implementation

- GitHub Actions currently fails or cancels before recording any job steps, consistent with the
  documented external billing/spending-limit start blocker. Local verification remains available,
  but hosted CI is not currently a demonstrated gate.
- Learned training requires an approved compute venue, budget and execution action. This does not
  block lifecycle instrumentation or the deterministic two-RSU baseline.
- A real Manchester/TfGM task workload does not exist. Traffic data can inform mobility only;
  computing tasks, RSUs, radio behaviour and queues remain synthetic unless separately observed.

## What does **not** block the safest first implementation slice

The following are not prerequisites for lifecycle instrumentation and a synthetic two-RSU test:

- a Kubernetes cluster;
- a learned scheduler;
- a GPU budget;
- live TfGM road telemetry;
- a new large campaign;
- publication approval; or
- actor retraining.

The frozen actor can remain unchanged while a downstream deterministic dispatcher is developed
and validated. Retraining becomes necessary only when RSU state enters the actor observation or
the actor chooses the execution RSU.

## Safest build sequence

1. Obtain producer answers or freeze a versioned provisional semantics record.
2. Define the task-lifecycle v1 contract and conservation invariant without changing scientific
   outcomes.
3. Implement one deterministic two-RSU fixture and prove every task reaches exactly one terminal
   state.
4. Add a narrow scheduler interface and implement existing/strongest-link, no-forwarding,
   least-loaded and predicted-earliest-completion policies.
5. Add reservations, forwarding/return costs and telemetry age; rerun the hand calculation.
6. Freeze and sign a small deterministic comparison before running new data.
7. Build the learned scheduler only after the deterministic results and information contract are
   stable.
8. Treat capacity-aware actor retraining as a separate experiment and admission path.

## Evidence used

- [Supervisor Meeting 4](supervisor_meeting_4_20260806.md)
- [Traffic-to-VEC scheduling experiment plan](traffic_to_vec_scheduling_experiment_plan_20260806.md)
- [Current 5.6 Pro interpretation audit](../current_status_5_6_pro_analysis.md)
- [Complete experiment history](complete_experiment_history_20260806.md)
- [Experiment catalogue](experiment_catalogue_20260730.md)
- [Capacity-aware benchmark design](../platform/capacity_aware_benchmark_design.md)
- [Scenario lifecycle integration design](../platform/scenario_lifecycle_integration_design.md)
- `src/traffictwin/integration/tos/contract_v2.py`
- `src/traffictwin/integration/vec_runner/`
- `src/traffictwin/platform/benchmark_protocol.py`
- `src/traffictwin/platform/benchmark_execution.py`
- `src/traffictwin/platform/scenario_lifecycle.py`

No external repository was fetched, pulled or modified. No campaign, registry, approval, evidence,
checkpoint or digest-bound candidate byte was changed.

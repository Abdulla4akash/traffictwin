# Design — Capacity-aware and multi-algorithm benchmark (post-v1 B-1)

**Status: IMPLEMENTED for maximum-coverage local protocol tooling in Phase 169; Phase 177 added
bounded execution packaging, contract-only manifests, an unsigned 2,400-job export and a tiny
synthetic engineering worker. The benchmark research remains `PROPOSED / UNSIGNED`; no real actor
binding, training, evaluation, cloud submission, spend, scientific execution, evidence creation or
admission occurred. Maximum policy ceiling: `owner_approved_candidate`.**

The delivered implementation is
`src/traffictwin/platform/benchmark_protocol.py`; its focused verification is
`tests/unit/test_benchmark_protocol.py`; and its exact generated draft is
[`capacity_multi_algorithm_benchmark_predeclaration_20260802.md`](../evaluation/capacity_multi_algorithm_benchmark_predeclaration_20260802.md).
The implementation contains no training loop or cloud client.

## 1. Frozen research questions

The owner-directed candidate protocol covers all three selected questions:

1. the main effect of capacity awareness under matched contracts;
2. the main effect of algorithm family under matched contracts; and
3. the interaction between capacity representation and algorithm family.

A null, mixed or worse capacity-aware result is complete and publishable under the protocol. The
design does not assume that capacity awareness or any algorithm improves service.

## 2. Maximum-coverage factorial

Five families receive matched training/evaluation cells:

- MAPPO;
- IPPO;
- QMIX;
- VDN; and
- Independent DQN.

The deterministic heuristic and random policy are evaluation-only controls and therefore receive
zero training jobs. Every candidate contract is digest identified; real implementation digests
must replace those bindings before execution. Trained families use five million interactions per
seed and terminal-checkpoint selection. A policy selected using held-out outcomes is refused as
`CHECKPOINT_SELECTION_LEAKAGE`.

The six observation/capacity representations are:

- capacity blind;
- global scalar;
- per-RSU vector;
- local observable;
- provisioned plus remaining capacity; and
- local utilisation plus queue state.

All capacity-aware features are visible before the action on the same tick, normalised only by the
frozen training-design envelope and refused when missing, dimensionally incompatible or outside
that envelope. The capacity-blind track adds no visible capacity dimension.

Each trained algorithm crosses:

- six capacity representations;
- four rewards: balanced QoS/energy, pure QoS, outcome-coherent and fairness-aware; and
- two discrete local/V2I/V2V action tracks: unmasked and feasibility masked.

This yields exactly 240 compatible training cells and 2,400 matched training jobs across ten
training seeds. The two evaluation-only controls are listed separately so their zero training
budget is not mistaken for a matched learned-policy cell.

## 3. Separate domain coverage

The protocol covers six independently analysed domains:

- procedural VEC;
- pinned Manchester corridor periods;
- a future whole-fleet Sparse-64-compatible design;
- additional safe Manchester periods;
- pinned SUMO network fixtures; and
- the Dhaka corridor synthetic or approved-aggregate scope.

Mobility, fleet, infrastructure and simulator contracts remain digest-bound per domain. Results
from incompatible domains are not pooled. Actor, observation, action, reward or budget mismatch is
reported `INCOMPATIBLE`, not ranked as though the comparison were matched.

The clean Sparse-64 rerun admitted in Phase 166 retains its
`admitted_with_execution_deviation` standing. The older 147-repeat and B-CAP diagnostics retain
their non-admitted standing. Prior results may motivate this design but none are benchmark evidence
inputs, pooled returns or substitutes for the fresh evaluation namespace.

## 4. Seed, checkpoint and endpoint protocol

The exact mutually disjoint namespaces are:

- engineering dry-run: 2000–2002;
- training: 2100–2109;
- tuning: 2200–2204; and
- fresh paired evaluation: 2300–2319.

Every namespace is checked against all registered/spent cohorts. Current held-out seeds and any
other registered cohort are refused. Post-hoc seed expansion is prohibited. At least 18 of the 20
fresh paired evaluation seeds must complete for admission eligibility.

The primary endpoint is equal-weight task-class deadline completion. Every analysis must also
report mean latency, mean energy, completion/failure composition, action/offloading behaviour and
persistent-minority failure concentration. Latency alone cannot determine the verdict.

The terminal checkpoint is primary. Checkpoints at 25%, 50%, 75% and 100% of the frozen budget are
robustness views only and cannot be selected from evaluation outcomes.

## 5. Frozen statistical contract

The proposed analysis uses paired differences, a 95% paired bootstrap interval, the exact sign
test and a paired permutation test. Confirmatory families use Holm FWER 0.05; exploratory families
use Benjamini–Hochberg FDR 0.05. Domains remain separate. Ties and nulls are reported.

The protocol-digest-bound practical thresholds are:

- 0.01 absolute deadline-completion difference;
- 100 ms mean-latency difference;
- 0.1 J mean-energy difference;
- 0.01 absolute failure-rate difference;
- 0.05 absolute action-share difference; and
- 0.02 absolute persistent-minority-share difference.

These are proposed study thresholds, not universal scientific or operational standards.

## 6. Resource plan is an estimate, not authority

The candidate plan records GCP Batch as the primary scheduler, AWS Batch as failover, and L4, A100
and H100 calibration with cross-accelerator reproducibility checks. It estimates ceilings of 5,000
GPU-hours and GBP 5,000, including GBP 250 calibration and GBP 750 pilot allowances.

All figures carry `estimate_only: true` and `authority: false`. No account was contacted, no
credential was read, no allocation was made and no money was spent. The code can enumerate and
account for the plan but cannot submit it.

## 7. Execution, analysis and admission remain distinct

The generated predeclaration is deterministic and binds its full protocol digest. Its sign-off
table is intentionally empty. Execution eligibility requires a timezone-aware, policy-validated
human-owner signature binding both the exact protocol digest and the final Markdown digest. The
eligibility response records `execution_started: false` and requires an external scheduler; it is
not an execution command.

After a separately authorised campaign, rule-based admission eligibility requires:

- exact protocol and signed-predeclaration digests;
- at least 18 successful fresh pairs;
- complete frozen analysis and multiplicity handling;
- separate domains;
- unchanged seed namespaces;
- the frozen checkpoint rule; and
- only deviations allowed by the predeclared rule.

Eligibility never creates an admission record or evidence. It returns
`admission_created: false` and `evidence_created: false`; an actual admission artifact belongs to a
separate governed workflow after real results exist.

## 8. Synthetic verification and typed refusals

The local dry run uses only the three engineering seeds, exercises the frozen analysis methods,
preserves a synthetic deviation and returns a publishable null with `evidence: false`,
`confirmatory: false` and `synthetic_dry_run: true`.

Typed refusals cover owner-decision gaps, unsigned or mismatched predeclarations, incompatible
contracts, observation dimensions, unfrozen capacity features, seed contamination, unmatched
budgets, checkpoint leakage, incomplete endpoints, non-admitted-result reuse, resource ceilings,
private content and unauthorised non-synthetic analysis.

## 9. Current scientific context

The existing admitted capacity result remains exactly:

- Lowering RSU capacity from 2.5 to 0.75 reduced mean latency by 8,310.9 ms.
- Bootstrap interval: [−9,097.5, −7,524.3] ms.
- All five held-out seeds moved in the same direction.
- The exact two-sided sign-test floor is p=0.0625.
- Do not claim conventional statistical significance.
- Deadline attainment remained effectively flat.
- Actions/offloading decisions were invariant across capacity arms.
- The latency change occurred within already-failed tasks and was not an improvement experienced
  by an individual vehicle.
- The post-hoc capacity-scaled latency ceiling was approximately 39,959 ms × capacity.
- Failure was concentrated among a persistent minority of vehicles.
- The broader finding is that standard VEC QoS metrics can improve when the system is degraded.

This context motivates the benchmark. It is not a forecast of its outcome and is not pooled with
future benchmark results.

## 10. Residual limitations

No real actor implementation, simulator image, domain artifact, cloud account, hardware,
checkpoint, training receipt or evaluation receipt is bound yet. The proposed predeclaration is
unsigned. Scientific execution still requires a separately signed final artifact and explicit
external compute action; this phase intentionally provides neither. Any changed scope, budget,
seed, threshold or analysis rule changes the digest and requires a new proposed predeclaration.

All producer-derived implementations and results must satisfy
[`docs/producer_citation_requirements.md`](../producer_citation_requirements.md). Repository
artifacts must not contain credentials, private paths, raw BODS data, private permission text or
non-redistributable checkpoints.

## 11. Phase-177 execution package

[`benchmark_execution_infrastructure_design.md`](benchmark_execution_infrastructure_design.md)
defines the bounded package now implemented in
`src/traffictwin/platform/benchmark_execution.py`. It deterministically binds contract-only
manifests for all seven families, validates pure observation/action/reward adapters, exports all
240 cells and 2,400 matched training jobs as unsigned/non-dispatching canonical records, and
exports the provider-neutral Phase-169 resource ceilings as estimates only.

The only runnable worker is a four-step in-process synthetic adapter exercise across seven
families and the three engineering seeds (21 jobs). Its path-free receipts, retries, checkpoint
inventory and analysis-input freeze remain `synthetic_dry_run: true`, `evidence: false` and
non-admitting. Future planned returns must bind an exact human-owner signature, budget, seed,
endpoint set and 25/50/75/100 checkpoint inventory before they are merely marked compatible; that
gate does not analyse or admit them. No actor implementation, scientific checkpoint or scheduler
was supplied in Phase 177.

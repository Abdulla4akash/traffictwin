# Design — Capacity-aware and multi-algorithm benchmark (post-v1 B-1)

**Status: IMPLEMENTED for gates 1–2 tooling only in Phase 154 and completed/reconciled in Phase
161: schemas, compatibility checks, frozen training-design capacity features, seed namespaces,
matched-budget estimates, synthetic-only frozen analysis and an unsigned predeclaration renderer.
The research design remains PROPOSED/UNSIGNED and is not authorised for scientific execution.
Actor/trace/endpoint/seed/hardware choices, sign-off, training, evaluation and admission remain
owner-controlled later gates. Maximum policy ceiling: `owner_approved_candidate`. No experiment or compute
campaign may start from this document. Actor families, budgets, seeds, endpoints and
admission protocol require explicit owner decisions and a frozen predeclaration first.**

## 1. Research purpose

Meeting 3 asked why capacity was absent from the observation, whether policy behaviour
changed, whether a capacity-aware agent would behave differently, and whether other
algorithms should be compared. The existing confirmed study shows invariant actions across
capacity arms, but it does not answer how a retrained capacity-aware policy would behave.

This benchmark would test two separable questions:

1. Does exposing a capacity representation change policy actions or outcome coherence under
   a matched training/evaluation contract?
2. Do selected alternative algorithms produce materially different action/mechanism
   behaviour under the same observation, action, reward and resource budgets?

Neither question is a foregone improvement claim. A null or worse capacity-aware result is
a complete outcome.

## 2. Existing evidence boundary

The current B-CAP 17D/19D GPU diagnostic and the Sparse-64 bus/GPU campaigns retain their
recorded roles, deviations and `NON_ADMITTED` status. They may motivate protocol choices but
must not be reused, relabelled or pooled as admitted benchmark evidence. The fresh Sparse-64
five-seed completion does not relax VEC-06 and does not automatically require another run.

Held-out seeds already inspected by current studies cannot become unseen benchmark seeds.
Training, tuning, dry-run and final evaluation seed namespaces must be newly declared and
disjoint where the protocol requires independence.

## 3. Comparison families

The owner must select the smallest scientifically useful set. The proposed minimum is:

- **Capacity-blind reference:** the compatible existing actor/architecture under its frozen
  observation contract.
- **Capacity-aware matched actor:** the same family and training contract with one reviewed,
  normalised capacity feature or capacity vector added.
- **Optional alternative algorithm:** at most one additional family initially, chosen only
  after confirming that its discrete/continuous action support, reward, observation and
  checkpoint semantics can be matched.

An algorithm name alone does not make a valid baseline. If observation/action/reward or
training budget cannot be made comparable, the row is reported `INCOMPATIBLE`, not ranked.

## 4. Capacity representation

Before implementation, freeze:

- whether capacity is scalar total, per-RSU vector or a local observable;
- units and normalisation based only on training-design information;
- missing/out-of-range behaviour;
- whether the feature represents provisioned compute, remaining compute or both;
- the causal timing rule: what capacity value is visible before each action;
- the relationship between 17D/19D observations and existing checkpoint compatibility.

No evaluation-arm statistic may be used to normalise or engineer the feature. A changed
observation dimension requires new training; existing checkpoints are not silently padded.

## 5. Matched protocol

The predeclaration must fix:

- compatible trace set, fleet preset/size and capacity arms;
- actor families, implementations and checkpoint-selection rule;
- observation/action/reward contracts and the single intended difference;
- training interactions, tuning budget, early-stopping rule and hardware accounting;
- paired fresh evaluation seeds and blocked randomisation/order;
- primary endpoint, mechanism endpoints, uncertainty method and multiplicity treatment;
- minimum successful-pair rule, refusal/deviation policy and publishable null;
- wall-clock/GPU ceilings and stop rule.

The primary endpoint should test outcome coherence rather than latency alone. Latency,
deadline attainment, completion/failure and action/offloading behaviour must be reported
together. Mechanism diagnostics should include capacity-scaled ceiling behaviour, failed
task distribution, tail concentration and action changes.

With very small paired seed counts, exact-test resolution must be stated before execution.
Five unanimous paired differences still have a two-sided sign-test floor of p=0.0625; more
seeds are a design/budget decision, not a post-hoc repair after seeing results.

## 6. Execution and admission separation

Implementation proceeds in gates:

1. schema/compatibility design and synthetic dry-run tests;
2. unsigned predeclaration draft and resource estimate (`evidence: false`);
3. explicit owner decisions and policy-valid sign-off;
4. separately authorised training/evaluation execution;
5. blind/frozen analysis against the predeclared verdict;
6. independent admission decision with deviations visible.

The benchmark tooling may be built before compute authority only if tests use synthetic or
tiny non-scientific fixtures. It must have no automatic cloud submission path and must not
reuse runtime credentials.

## 7. Artifacts

Proposed artifacts are a versioned `BenchmarkProtocol`, `ActorCompatibilityRecord`,
`TrainingReceipt`, `CheckpointSelectionReceipt`, paired `EvaluationReceipt`, frozen
`BenchmarkAnalysis` and admission record. Each binds source/code/environment digests,
seeds, budgets, actor contract, capacity representation and deviations.

Repository artifacts contain no checkpoints whose licence forbids redistribution, private
paths, credentials or raw BODS data. Producer-derived code/results include the citation
bundle required by [producer citation requirements](../producer_citation_requirements.md).

## 8. Typed refusals

At minimum: `OWNER_DECISION_MISSING`, `PREDECLARATION_UNSIGNED`,
`COMPUTE_AUTHORITY_MISSING`, `ACTOR_CONTRACT_INCOMPATIBLE`,
`OBSERVATION_DIMENSION_MISMATCH`, `CAPACITY_REPRESENTATION_UNFROZEN`,
`SEED_NAMESPACE_CONTAMINATED`, `TRAINING_BUDGET_UNMATCHED`,
`CHECKPOINT_SELECTION_LEAKAGE`, `PRIMARY_ENDPOINT_MISSING`,
`EXISTING_NON_ADMITTED_REUSE` and `RESOURCE_BUDGET_EXCEEDED`.

## 9. Verification and acceptance

Before any scientific execution, tests must pin feature construction, dimension checks,
capacity visibility timing, actor compatibility, deterministic seed partitions, matched
budget accounting, checkpoint-selection isolation, endpoint completeness and refusal on
non-admitted reuse. A synthetic end-to-end dry run must prove that the frozen analysis
produces a publishable null and retains all deviations.

Acceptance for the design/tooling phase means the protocol can be frozen and audited
without launching compute. Scientific acceptance is a later admission decision and is not
guaranteed by successful execution.

## 10. Owner decisions and stop conditions

Required decisions: research priority, actor families, capacity representation, trace/fleet
scope, primary endpoint, seed count, compute budget, hardware source and whether any new
training is justified. Stop before training or evaluation until all are explicit and the
predeclaration is signed. Also stop if comparison requires incompatible contracts,
post-hoc seed expansion, hidden checkpoint selection, VEC-06 relaxation or promotion of
existing non-admitted runs.

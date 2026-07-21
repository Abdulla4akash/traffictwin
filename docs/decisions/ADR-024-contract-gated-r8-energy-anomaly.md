# ADR-024 — Contract-Gated R8 Energy-Anomaly Diagnosis

Status: accepted
Date: 20 July 2026
Capability: `DIA-03`

## Context

`MET-03` computes three energy metrics only under the exact canonical v1.0 task-energy contract.
The v0.5 design requires R8 to compare energy cost with completed work without triggering from
missing energy or mixed units. An absolute joule threshold is not portable across arbitrary task,
hardware, or external-source semantics, and the current SUMO and TOS adapters do not satisfy the
canonical row-level energy contract.

R8 therefore needs a deliberately narrow admission policy, visible insufficiency, and a
provisional development threshold. It must consume `EvidencePack` metrics rather than task rows or
source files.

## Decision

R8 v1.0 evaluates one whole-run metric:

- `task.energy.per_completed_j`, whose value is the mean total energy of completed tasks with
  eligible energy evidence;
- the metric must be `available`, finite, non-negative, and have unit `J/task`;
- metadata must identify energy family `1.0`, the exact canonical v1.0
  `TaskEnergyContract` fingerprint, quantity `per_task_total_energy`, energy unit `J`, and
  eligibility `completed_and_finite_non_negative_energy`;
- `coverage_fraction` must equal `1.0`; `eligible_count` and `population_count` must be equal,
  non-negative integers;
- `task.completed.count` must be available with unit `count`, be a non-negative integer value, and
  equal the energy metric's completed-task population.

The provisional configuration is:

- `minimum_energy_per_completed_task_j = 1.50`;
- `minimum_completed_tasks = 10`;
- the energy boundary is inclusive (`observed >= threshold`).

Status is deterministic:

- `triggered` when the admitted value meets the boundary and completed-task support meets the
  configured minimum;
- `conflicting_evidence` when the boundary is met but completed-task support is below the minimum;
- `not_triggered` when admitted energy is below the boundary;
- `insufficient_evidence` when the metric/denominator is missing, unavailable, partial, invalid,
  non-finite, unit-incompatible, contract-incompatible, incompletely covered, or inconsistent.

The default separates labelled synthetic development cases so trigger/non-trigger/boundary/thin
evidence can be tested. It is not a hardware benchmark, operational standard, calibrated anomaly
detector, statistical outlier test, or externally validated threshold. R8 never compares unlike
units and does not use source-specific TOS aggregate joules-per-arrival as completed-task energy.

R8 records its threshold, support minimum, observed value, completed count, contract fingerprint,
coverage, and denominator policy in `RuleResult` metadata. Ordinary rule provenance traces the
result through the admitted energy metric and its accepted-row ledger. This is calculation lineage,
not causal energy attribution.

The default ruleset advances from `1.2` to `1.3` and enables R8. Generic/synthetic capability is
conditional on the exact energy contract; current SUMO and TOS source manifests report R8 false.

## Consequences

- A high single-run mean is an energy-cost candidate only; task-class mix, workload, offload
  decisions, latency, hardware, and finite-sample variation remain alternatives.
- R8 does not compare a run with a baseline or learn a distribution. Later statistical and
  nearest-flip capabilities remain separate.
- Partial completed-task energy never becomes zero or a trigger.
- Future energy contracts or units require an explicit R8 decision rather than silent conversion.
- UI and CLI controls call the same library rule and do not implement the threshold calculation.

## Acceptance Evidence

- Unit tests pin trigger, inclusive boundary, non-trigger, thin-support conflict, missing/partial
  evidence, wrong units, wrong contract, incomplete coverage, denominator mismatch, and
  configuration validation.
- Integration tests cover bundle/EvidencePack CLI evaluation, source capability boundaries, and
  metric/finding/source-row provenance.
- UI tests prove controls delegate to the library service and render status, limitations, and JSON
  export without scientific calculations in Streamlit.
- Golden output pins the R8 contract and deterministic result projection.
- Generated references, documentation, lint, strict typing, full tests/coverage, lockfile, package
  build, and release smoke checks complete the capability gate.

## Alternatives Considered

- Trigger from any `energy_j` column: rejected because a column name and unit do not prove quantity
  or eligibility semantics.
- Reuse TOS joules per arrival: rejected because arrival and completed-task denominators differ and
  row-level eligibility is absent.
- Trigger on partial energy coverage: rejected because missing energy is not zero or low use.
- Compare energy and energy-delay product numerically: rejected because they have different units
  and meanings; R8 v1.0 admits one explicit completed-task energy indicator.
- Claim a statistical anomaly from one threshold: rejected because R8 is a deterministic
  diagnostic candidate, not distributional inference.

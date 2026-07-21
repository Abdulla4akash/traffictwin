# ADR-018: Contract-Gated Task-Energy Metrics

Status: accepted

## Context

TrafficTwin v0.5 `MET-03` requires per-task energy, energy per completed task, and energy-delay
product only when source unit and eligibility semantics are confirmed. The generic adapter already
converts a declared `energy_j` field in joules, and the labelled synthetic generator produces one
modelled total-energy value for each completed task. A unit alone does not establish whether a
source value is instantaneous power, interval energy, per-arrival aggregate energy, or per-task
total energy.

The TOS evaluation summary reports aggregate joules per arrival. It does not provide canonical
row-level energy with the completion and latency eligibility needed by this family. SUMO output
contains no canonical task-energy evidence.

## Decision

- Add a strict `TaskEnergyContract` to `BundleManifest`. Its only v1.0 admission is:
  - quantity `per_task_total_energy`;
  - one value per canonical task record;
  - canonical energy unit `J` and delay unit `ms`;
  - finite, non-negative per-task energy eligibility;
  - completed plus eligible energy for completed-task energy;
  - completed plus eligible energy and latency for energy-delay product.
- Require `files.tasks.units.energy_j: J` whenever the contract is present. A missing contract
  leaves every canonical energy-family metric unavailable with `ENERGY_CONTRACT_UNAVAILABLE`, even
  if an `energy_j` column exists.
- Reject negative energy during generic validation with `TASK_ENERGY_NEGATIVE`. Missing energy is
  excluded and never treated as zero.
- Compute these deterministic run/window metrics:
  - `task.energy.mean_per_observed_task_j = sum(E) / n(E eligible)`;
  - `task.energy.per_completed_j = sum(E completed) / n(E completed eligible)`;
  - `task.energy_delay_product.mean_j_ms = sum(E * latency_ms) / n(E,L completed eligible)`.
- Attach contract fingerprint/version, quantity, units, eligibility policy, eligible count,
  population count, and coverage to every result. No eligible observations produce explicit
  unavailability. Incomplete completed-task coverage produces `partial`, so it is not silently
  compared.
- Compare energy metrics only when both available results carry the same semantic-contract
  fingerprint. A mismatch produces `COMPARISON_PAIR_INCOMPATIBLE`.
- Enable the family for explicitly contracted generic/synthetic bundles. Keep the canonical family
  false for the current SUMO and TOS adapters. Retain TOS joules per arrival under its separate
  source-specific metric key and warning.
- Attribute windowed energy outcomes to the existing task-arrival cohort. Reuse ordinary metric
  traces and complete accepted-row ledgers; eligibility is lineage, not causality.

## Consequences

- Generated synthetic bundles gain a fingerprint change because the immutable manifest now records
  energy semantics.
- Manually authored generic sources can opt in only by declaring the exact supported contract and
  joule unit. Manifest inference does not invent or automatically confirm energy meaning.
- Cross-source calculations are possible when contracts are identical, but source identity alone
  is neither sufficient nor a reason for rejection.
- R8 energy anomaly diagnosis remains separately unimplemented; `MET-03` does not choose a
  diagnostic threshold or claim external validity for the synthetic energy model.

## Acceptance Evidence

- Contract/model tests cover strict literals, stable fingerprinting, and unit mismatch rejection.
- Metric tests pin exact synthetic values, coverage, unavailable-without-contract behavior,
  window equivalence, compatible/incompatible comparison, validation, and full row lineage.
- A reviewed golden projection pins all three values and metadata.
- CLI, report, Run Overview, capability, SUMO/TOS boundary, generated-reference, lint, typing,
  package-build, and full-suite gates cover public surfaces.

## Alternatives Considered

- Treat every `energy_j` column as compatible: rejected because a unit does not define quantity or
  denominator.
- Reuse TOS joules per arrival as completed-task energy: rejected because deadline success and
  eventual completion are not equivalent and row-level eligibility is absent.
- Fill missing energy with zero: rejected because missing evidence is not zero consumption.
- Convert unsupported energy units automatically: rejected until the source quantity and a
  versioned conversion contract are evidenced.

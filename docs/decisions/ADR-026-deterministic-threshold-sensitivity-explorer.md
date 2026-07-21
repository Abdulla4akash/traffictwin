# ADR-026 — Deterministic Threshold-Sensitivity Explorer

Status: accepted
Date: 20 July 2026
Capability: `DIA-06`

## Context

The v0.5 design requires an interactive explorer that evaluates a complete threshold grid, shows
trigger stability and flip boundaries, labels provisional defaults, and does not silently persist
threshold changes. The Streamlit page must remain a thin renderer over a deterministic library
service. A UI loop that implements rule logic, selectively hides unfavourable grid points, or
writes changed defaults into the registry would violate that boundary.

The nearest-flip contract in ADR-025 establishes defensible monotonic single-boundary semantics
for R5, R7, and R8. The remaining core and arbitrary declarative rules have compound, discrete,
temporal, or otherwise uncontracted configuration spaces.

## Decision

`DIA-06` v1.0 sweeps only the inclusive continuous severity thresholds already admitted by
ADR-025:

| Rule | Swept parameter | Unit | Fixed configuration |
|---|---|---|---|
| R5 | `r5.maximum_absolute_gap` | ratio | enablement and minimum pair count |
| R7 | `r7.minimum_outcome_gap` | ratio | dimension, enablement, and minimum group support |
| R8 | `r8.minimum_energy_per_completed_task_j` | J/task | enablement and minimum completed tasks |

The caller declares finite non-negative inclusive lower and upper bounds and between 2 and 101
linearly spaced requested points. R7 bounds cannot exceed 1.0. Grid generation uses both endpoints,
rounds generated values to 12 decimal places under the versioned `inclusive_linear_v1` method,
and inserts the exact source threshold when it lies inside the range but is not already present.
The artifact records requested and evaluated counts and whether insertion occurred.

Every point is evaluated with:

- the same immutable `EvidencePack`;
- the same complete `RuleSetConfig`, except for the one swept threshold;
- every non-selected core rule disabled only in the temporary evaluation copy; and
- one shared analysis timestamp.

The report retains every evaluated point, including `insufficient_evidence`,
`conflicting_evidence`, `invalid`, and `not_triggered` outcomes. It records point configurations,
result fingerprints, evidence keys, finding counts, and missing-evidence counts. It never filters
the grid to triggered or favourable values.

Trigger stability records the full status distribution, triggered fraction, ordinary status
transition count, trigger-membership transition count, whether all statuses match, and whether
trigger membership is a monotonic prefix as thresholds rise. A sampled flip interval is reported
only between adjacent grid points whose `triggered` membership differs. The exact nearest-flip
artifact from DIA-05 is embedded when its source-status/support gate admits one; its absence or
reason remains visible and is not approximated from the sampled grid.

R0-R4, R6, and arbitrary declarative rules remain explicitly unsupported under the v1.0 sweep
contract. This does not make those rules unavailable for ordinary evaluation.

The Streamlit page calls the library sweep service and renders its typed report. It may accept a
complete `RuleSetConfig` JSON only after an explicit apply action. Imported configuration is kept
in Streamlit session state; it does not update repository files, registry records, package
defaults, or source evidence. Export is an explicit download of a complete validated
`RuleSetConfig`, either the current source configuration or one selected evaluated grid point.
Changing a range, point count, rule selector, or export selector does not persist anything.

The artifact carries a deterministic fingerprint that normalises only analysis timestamps,
including the timestamp in an embedded nearest-flip artifact. The diagnostic ruleset remains
`1.3` because no rule defaults or evaluation semantics change.

## Consequences

- The full evaluated grid and its stability are reproducible and auditable.
- UI controls cannot become a second rule engine.
- Thin, missing, incompatible, or conflicting evidence remains visible at every grid point.
- Sampled flip intervals are not misrepresented as exact boundaries.
- Explicit config download/import supports reproducible exploration without silent persistence.
- Multi-parameter, temporal, compound, and arbitrary declarative sweeps require a later
  monotonicity and admissibility contract.
- Current SUMO and TOS source manifests report threshold-sensitivity sweep support as false.

## Acceptance Evidence

- Unit tests cover grid generation, source-threshold insertion, all supported families, full
  status retention, flip intervals, monotonicity, unsupported/disabled rules, invalid bounds,
  immutable inputs, explicit point-config export, and timestamp-normalised fingerprints.
- A golden artifact pins the public contract and a complete R8 sweep.
- UI-service tests prove config parsing/export and delegation to the library service.
- Streamlit AppTest coverage exercises rule selection, sweep execution, result rendering, and
  explicit downloads without registry or source writes.
- Generated schemas and a machine-readable contract expose the typed public boundary.
- Documentation labels all defaults provisional and sensitivity as descriptive rather than
  calibration, optimisation, significance, causality, or recommendation.

## Alternatives Rejected

- Sweep every core setting: rejected because unlike units and compound status paths still lack a
  defensible contract.
- Compute status directly in the page: rejected because the UI must contain no scientific logic.
- Return only transition points: rejected because the design requires the complete evaluated grid.
- Treat a sampled interval as the exact flip: rejected because DIA-05 provides separately verified
  exact semantics when admissible.
- Automatically save the last selected threshold: rejected because exploration must not silently
  rewrite defaults or registry state.

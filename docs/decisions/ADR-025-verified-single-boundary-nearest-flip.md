# ADR-025 — Verified Single-Boundary Nearest-Flip Analysis

Status: accepted
Date: 20 July 2026
Capability: `DIA-05`

## Context

The v0.5 design asks for the smallest admissible rule-configuration change that would turn an
eligible non-triggered result into a triggered result. A generic distance across probabilities,
counts, seconds, queue lengths, and compound temporal settings would be arbitrary. Several core
rules also combine multiple predicates or change status through conflicting-evidence states, so a
single numeric answer would conceal important constraints.

Nearest-flip analysis must use the existing `EvidencePack` and rule engine. It must not alter the
evidence, rewrite a default, search for a favourable threshold, or present a mathematical boundary
as a recommendation.

## Decision

`DIA-05` v1.0 supports the three core rules whose severity decision has one exact inclusive
continuous boundary after separate discrete support admission:

| Rule | Threshold parameter | Observed boundary | Discrete constraints left unchanged |
|---|---|---|---|
| R5 | `r5.maximum_absolute_gap` | admitted maximum training-validation absolute gap | `r5.minimum_pair_count` |
| R7 | `r7.minimum_outcome_gap` | admitted selected-dimension completion-rate gap | minimum group count and `r7.minimum_group_support` |
| R8 | `r8.minimum_energy_per_completed_task_j` | admitted mean completed-task energy | `r8.minimum_completed_tasks` |

For these rules, the triggering comparison is `observed >= threshold`. If the current result is
`not_triggered` and every discrete constraint is satisfied, the unique one-axis candidate is to
decrease the threshold to the exact admitted observed value. The absolute distance is reported in
that parameter's existing unit. v1.0 never compares distances across unlike parameter units.

The candidate is accepted only after the ordinary rule engine is called again with:

- the same immutable `EvidencePack`;
- the same rule configuration except for the one threshold field;
- only the selected core rule enabled; and
- the same analysis timestamp.

The verified candidate must return `triggered`. Otherwise the report is `not_applicable` with a
stable reason rather than approximating or returning an unverified value.

The source rule must be enabled and its current status must be exactly `not_triggered`.
`triggered`, `conflicting_evidence`, `insufficient_evidence`, and `invalid` results are not eligible.
An unmet discrete support constraint is visible and is never changed by the analysis.

R0-R4, R6, and arbitrary declarative rules are `unsupported` in v1.0. R0 has no severity threshold;
R1-R4 have compound status logic and potentially unlike parameter units; R6 couples window,
duration, deterioration, and recovery settings; arbitrary declarative definitions require a
separate monotonicity/admissibility contract. Unsupported does not mean that the rule itself is
unavailable.

The typed artifact records:

- source and candidate statuses;
- exact source and candidate rule configurations;
- parameter path, direction, unit, inclusive boundary, and absolute delta;
- every discrete constraint and whether it was satisfied;
- ties through an ordered candidate list and explicit tie count;
- EvidencePack, source-bundle, current-result, and candidate-result fingerprints;
- stable reason codes and limitations; and
- a deterministic artifact fingerprint that normalises only the analysis timestamp.

The v1.0 families each expose one admissible continuous axis, so an available result has one
candidate and `tie_count=1`. The schema retains an ordered candidate list so a later, separately
decided family can report exact equal-distance ties without discarding them.

The analysis is in-memory. CLI export writes a new artifact only when explicitly requested; it
does not persist or replace `RuleSetConfig`. The diagnostic ruleset remains `1.3` because no rule
semantics or defaults change.

## Consequences

- The result is exact, reproducible, and auditable for R5/R7/R8.
- Missing, incompatible, thin, conflicting, or already-triggered evidence cannot be converted into
  a favourable sensitivity result.
- Absolute distance is scientifically interpretable because each supported analysis has one
  parameter axis and one unit.
- Broader multi-parameter nearest-flip work requires an explicit distance, monotonicity, and
  constraint contract rather than silent grid search.
- `DIA-06` remains separate: this decision adds no interactive threshold sweep or persistence UI.
- Generic/synthetic capability is conditional on eligible R5/R7/R8 evidence. Current SUMO and TOS
  source capability manifests report nearest-flip analysis false.

## Acceptance Evidence

- Unit tests cover all supported families, exact inclusive boundaries, target-RSU reduction,
  discrete-support failure, disabled/unsupported/already-triggered/insufficient states, immutable
  input/config behavior, verified re-evaluation, and deterministic fingerprints.
- CLI tests cover bundle and saved-EvidencePack inputs, text/JSON export, invalid formats, and
  stable non-applicable output.
- A golden artifact pins the v1.0 contract and one exact R8 result.
- Generated Pydantic schemas and a machine-readable capability contract expose the public models.
- Documentation states that the result is sensitivity, not calibration, optimisation, causality,
  or a recommendation.

## Alternatives Rejected

- Search every core configuration field: rejected because unlike units and compound status paths
  do not have one defensible distance.
- Lower discrete sample/group requirements: rejected because support admission is evidence quality,
  not a severity threshold to tune around the data.
- Return the algebraic boundary without re-evaluation: rejected because the ordinary rule engine is
  the authoritative status implementation.
- Add the threshold-sweep UI at the same time: rejected because it is the separate `DIA-06`
  capability with additional state and export requirements.

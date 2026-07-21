# Nearest-Flip Analysis

`DIA-05` v1.0 computes the smallest verified one-parameter configuration change that would turn
an eligible `not_triggered` R5, R7, or R8 result into `triggered`. It is a deterministic threshold-
sensitivity artifact over an existing `EvidencePack`; it does not change evidence or recommend a
new threshold.

## Supported Rules

| Rule | Continuous parameter | Exact flip boundary | Unchanged discrete constraint |
|---|---|---|---|
| R5 | `r5.maximum_absolute_gap` | observed maximum training-validation absolute gap | `minimum_pair_count` |
| R7 | `r7.minimum_outcome_gap` | observed selected-dimension completion gap | group count and `minimum_group_support` |
| R8 | `r8.minimum_energy_per_completed_task_j` | observed mean energy per completed task | `minimum_completed_tasks` |

Each supported rule uses an inclusive `observed >= threshold` severity comparison. When the
current threshold is above the admitted observation, the exact one-axis flip is therefore to lower
the threshold to the observation. The reported distance is the absolute change in the parameter's
existing unit: ratio for R5/R7 and `J/task` for R8.

R0-R4, R6, and arbitrary declarative rules are explicitly unsupported in v1.0. Their absent result
is not replaced with a grid search or a distance across unlike configuration units. R0 has no
severity threshold; R1-R4 have compound status logic; R6 couples temporal and recovery settings;
local declarative rules need a separate monotonicity contract.

## Admission and Verification

The analysis:

1. receives an `EvidencePack`, rule ID, and complete `RuleSetConfig`;
2. evaluates only the selected rule through the ordinary rule engine;
3. requires the source status to be exactly `not_triggered`;
4. reads the admitted observed value from that typed `RuleResult`;
5. reports every discrete pair/group/task support constraint without changing it;
6. creates an in-memory configuration differing only at the supported threshold field; and
7. calls the ordinary rule engine again at the exact inclusive boundary.

A candidate is returned only when the second evaluation is `triggered`. The same EvidencePack and
analysis timestamp are used for both evaluations. The input pack and configuration are not
mutated.

## Result States

| Status | Stable reason examples | Meaning |
|---|---|---|
| `available` | `AVAILABLE` | One exact boundary was verified as triggered. |
| `not_applicable` | `RULE_DISABLED` | The selected rule is disabled. |
| `not_applicable` | `SOURCE_RULE_NOT_NOT_TRIGGERED` | The current rule is already triggered, conflicting, insufficient, or invalid. |
| `not_applicable` | `DISCRETE_CONSTRAINT_UNMET` | Required pair/group/task support is too thin and is not relaxed. |
| `not_applicable` | `OBSERVED_BOUNDARY_INVALID` | No finite admissible one-axis boundary can be represented. |
| `not_applicable` | `CANDIDATE_DID_NOT_TRIGGER` | Authoritative rule-engine verification rejected the algebraic candidate. |
| `unsupported` | `UNSUPPORTED_RULE` | The rule family has no v1.0 nearest-flip contract. |

An available v1.0 artifact has one candidate and `tie_count=1`. The schema uses an ordered
candidate list and explicit tie count so future separately approved families can retain equal-
distance candidates rather than selecting one silently.

## CLI Usage

Analyse a compatible bundle with default ruleset configuration:

```bash
uv run traffictwin diagnose nearest-flip path/to/bundle R8 --format json
```

Use an explicitly exported complete `RuleSetConfig`:

```bash
uv run traffictwin diagnose nearest-flip path/to/evidence.json R7 \
  --rule-config ruleset.json \
  --format text
```

Write a new analysis artifact:

```bash
uv run traffictwin diagnose nearest-flip path/to/bundle R8 \
  --output nearest-flip.json
```

The command accepts a bundle directory/ZIP or a saved EvidencePack JSON. `--rule-config` is read-
only. `--output` writes only the analysis result and does not persist its candidate as a default.

## Python Usage

```python
from traffictwin.diagnostics.sensitivity import analyse_nearest_flip
from traffictwin.rules.config import RuleSetConfig

analysis = analyse_nearest_flip(
    evidence_pack,
    "R8",
    RuleSetConfig(),
)

if analysis.status.value == "available":
    candidate = analysis.candidates[0]
    print(candidate.parameter_path, candidate.flip_value, candidate.unit)
```

Use `nearest_flip_contract()` for the machine-readable support, distance, tie, verification,
discrete-constraint, and persistence policies.

## Provenance and Reproducibility

Every artifact records:

- EvidencePack ID and deterministic fingerprint;
- source-bundle fingerprint when available;
- metric version and cited evidence keys;
- exact source and candidate rule configurations;
- current and candidate `RuleResult` fingerprints;
- source and verified candidate statuses;
- parameter path, values, unit, direction, operator, boundary inclusion, and absolute delta;
- every discrete constraint and whether it passed; and
- the analysis version, ruleset version, synthetic flag, timestamp, and deterministic artifact
  fingerprint.

The artifact fingerprint normalises only `analysed_at`. Changing evidence, selected rule,
configuration, observed boundary, support, or verification output changes the fingerprint.

## Appropriate Uses

Nearest-flip analysis can support:

- explaining how far a non-triggered synthetic R8 case is from its current energy boundary;
- auditing whether a non-triggered R7 outcome is close to a predeclared operational gap;
- checking a compatible R5 experiment result against its current descriptive drift threshold;
- proving that thin support is not tuned away;
- exporting an exact sensitivity boundary for a methods appendix or later predeclared sweep; and
- showing why compound or unsupported rules do not receive an invented scalar answer.

It cannot establish:

- a scientifically valid, optimal, fair, efficient, or recommended threshold;
- statistical significance, uncertainty, equivalence, causality, or external validity;
- that the source evidence should be relabelled or a support minimum reduced;
- compatibility for SUMO/TOS evidence that cannot admit R5/R7/R8; or
- the complete-grid interactive threshold sweep implemented separately by `DIA-06`.

Selecting the exact observed value after seeing a result is descriptive sensitivity, not a
predeclared analysis threshold. External interpretation still requires representative evidence,
calibration, expert review, and an analysis plan fixed before inspecting outcomes.

## References

- [ADR-025](decisions/ADR-025-verified-single-boundary-nearest-flip.md)
- [Diagnostic rules](diagnostic_rules.md)
- [R7 diagnosis](fairness_diagnosis.md)
- [R8 diagnosis](energy_diagnosis.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Generated nearest-flip contract](reference/generated/nearest_flip_contract.json)
- [Threshold-sensitivity explorer](threshold_sensitivity_explorer.md)
- [Limitations and future work](limitations_and_future_work.md)

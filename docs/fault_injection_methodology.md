# Fault-Injection Methodology

Phase 5 uses synthetic EvidencePack-level fixtures to verify deterministic rule behavior.
This is engineering evaluation of rule implementation, not real-world diagnostic validation.

## Fixture Set

Fixture file:

```text
tests/fixtures/diagnostics/cases.json
```

Cases:

- `baseline_no_strong_hypothesis`
- `under_offloading`
- `infrastructure_bottleneck`
- `trivial_scenario`
- `mixed_fault`
- `insufficient_evidence`
- `contradictory_evidence`

The file labels each case as `development` or `held_out`.

`build_extended_fixture_set(...)` expands the declared families, including R4/R5 cases, over
`low`, `moderate`, and `high` severity and random seeds `7`, `17`, and `29`. The current expanded
software-verification matrix contains 81 labelled synthetic cases.

## Evaluation

The utility `evaluate_fixture_set(...)` builds synthetic EvidencePacks from the fixture definitions, evaluates the deterministic rule engine, and reports:

- true positives;
- false positives;
- false negatives;
- true negatives;
- support count;
- precision;
- recall;
- false-positive rate and specificity;
- confusion table.
- development and held-out summaries;
- per-severity robustness summaries;
- failed case IDs;
- a transparent KPI-threshold baseline for comparison.

Zero denominators produce `null`, never `NaN`.

## Current Results

With the current expanded synthetic fixture set, every supported R0-R5 rule has precision and
recall `1.0` and false-positive rate `0.0`. R4 and R5 each have nine positive support cases across
the severity/seed matrix.

These numbers are implementation checks over labelled synthetic cases. They are not evidence that the rules are externally valid for real Manchester, SUMO, or Randy/VEC runs.

R6-R8 use separate typed fixtures because their temporal, grouped, and contract-gated evidence
cannot be represented faithfully by the original flat R0-R5 case schema. R8 tests cover exact and
just-below thresholds, sufficient and thin support, missing/partial evidence, wrong units,
incompatible contracts, incomplete coverage, and count/population disagreement. They are
deterministic admission and rule-behavior checks, not external diagnostic validation.

DIA-05 nearest-flip tests are separate from the fault-injection score. They verify that an eligible
non-triggered R5, R7, or R8 result can cross its single inclusive continuous boundary while every
discrete support constraint remains unchanged, then require the ordinary rule engine to trigger
under the candidate configuration. This verifies sensitivity mechanics; it does not validate or
recommend a threshold.

DIA-06 tests are also separate from that score. They retain the full R5/R7/R8 grid, including
conflicting or insufficient states, verify trigger stability and sampled intervals, and confirm
that UI/config exploration does not mutate evidence or persistence. This is software sensitivity
evidence, not calibration or external rule validation.

DIA-07 tests remain separate from precision/recall as well. They verify the closed R1/R2 conflict,
R1/R4 corroboration, and explicit R0 blocker-suppression policy; exact overlap/status gates;
retention and fingerprinting of all original results; deterministic ordering; and unclassified or
unresolved outcomes. They do not assign a winning rule, raise confidence, or convert a synthetic
relationship into causal or external-validity evidence.

EXP-02 scenario-mutation tests are also separate from the diagnostic precision/recall fixture
score. Row dropout, timestamp jitter, and RSU removal verify deterministic input transformation,
immutability, provenance, and validation mechanics. They do not assign diagnostic labels, calibrate
a physical fault magnitude, simulate routing consequences, or demonstrate real-world robustness.
Any later diagnostic evaluation over a mutated bundle must declare the operator, parameters,
random seed, parent/derived fingerprints, and synthetic/evaluation status.

EXP-03 measurement-imperfection tests are likewise separate from diagnostic precision/recall.
They verify deterministic bounded observation errors, clamps, exact missing-row counts, semantic
audits, and unchanged clean outcome tables. Any later rule-stability study must predeclare the
clean/impaired pairing, both seeds, bounds/dropout fractions, metrics/rules, and multiplicity or
statistical method. The fixture does not calibrate a real sensor, packet-loss process, or physical
fault.

## Limitations

- Thresholds are provisional.
- Some rule inputs are aggregate metrics rather than direct temporal evidence.
- R1 lacks a direct T1-by-low-tier cross-tab.
- R2 lacks task-to-saturation temporal overlap.
- R3 requires experiment-level EvidencePack metrics that normal single-run bundles do not yet produce.
- R8's energy and support thresholds are provisional and do not encode a statistical population.
- Severity transformations are deterministic software fixtures, not calibrated fault magnitudes.
- The KPI baseline is transparent engineering context, not a statistical or learned benchmark.

## Related Documents

- [Diagnostic rules](diagnostic_rules.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Deterministic cross-rule reasoning](cross_rule_reasoning.md)
- [Testing strategy](testing_strategy.md)
- [Limitations and future work](limitations_and_future_work.md)

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

## Evaluation

The utility `evaluate_fixture_set(...)` builds synthetic EvidencePacks from the fixture definitions, evaluates the deterministic rule engine, and reports:

- true positives;
- false positives;
- false negatives;
- support count;
- precision;
- recall;
- confusion table.

Zero denominators produce `null`, never `NaN`.

## Current Results

With the Phase 5 synthetic fixture set:

- R0 precision/recall: `1.0` / `1.0`
- R1 precision/recall: `1.0` / `1.0`
- R2 precision/recall: `1.0` / `1.0`
- R3 precision/recall: `1.0` / `1.0`

These numbers are implementation checks over labelled synthetic cases. They are not evidence that the rules are externally valid for real Manchester, SUMO, or Randy/VEC runs.

## Limitations

- Thresholds are provisional.
- Some rule inputs are aggregate metrics rather than direct temporal evidence.
- R1 lacks a direct T1-by-low-tier cross-tab.
- R2 lacks task-to-saturation temporal overlap.
- R3 requires experiment-level EvidencePack metrics that normal single-run bundles do not yet produce.

## Related Documents

- [Diagnostic rules](diagnostic_rules.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Testing strategy](testing_strategy.md)
- [Limitations and future work](limitations_and_future_work.md)

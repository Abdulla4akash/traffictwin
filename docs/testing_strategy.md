# Testing Strategy

TrafficTwin uses a test pyramid: focused unit tests at the base, integration tests for the pipeline, golden tests for deterministic outputs, and UI smoke tests where reliable.

## Current Snapshot

Verified during this documentation pass:

- 119 tests passed.
- Coverage: 76%.

Coverage is a useful signal, not the only quality measure. Streamlit page rendering and CLI workflows are partly covered through service tests, AppTest-style tests, and smoke commands rather than exhaustive browser automation.

## Unit Tests

Located under `tests/unit/`.

Coverage includes:

- scenario seed validation;
- YAML seed IO;
- capability manifest behavior;
- registry operations and status transitions;
- manifest validation;
- bundle loader safety;
- validation codes;
- metric catalogue and calculators;
- comparison and aggregation;
- EvidencePack generation;
- rule configuration, registry, models, engine, and R0-R3 behavior.

## Integration Tests

Located under `tests/integration/`.

They check:

- bundle import;
- directory and ZIP validation;
- bundle to metrics;
- bundle to diagnostics;
- evidence to diagnostics;
- UI service/demo flows.

## Golden Tests

Located under `tests/golden/` with expected JSON under `tests/golden/expected/`.

Golden files verify exact projections for:

- baseline metrics;
- variation metrics;
- comparison output;
- validation reports;
- diagnostic reports.

Do not update golden files merely to pass tests. Recompute expected values from fixture rows and document the intended behavior change.

## Streamlit Tests

Located under `tests/ui/` and relevant integration tests.

The approach is to test:

- formatting;
- labels;
- chart-data preparation;
- service models;
- state defaults;
- page guards against rejected bundles.

Full browser automation is not required for the current documentation pass.

## CLI Smoke Tests

Representative smoke commands:

```bash
traffictwin validate-seed examples/seeds/arena_gridlock.yaml
traffictwin bundle validate tests/fixtures/bundles/baseline_valid
traffictwin metrics compute tests/fixtures/bundles/baseline_valid
traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
traffictwin evidence build tests/fixtures/bundles/baseline_valid --output evidence-baseline.json
traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
```

## ZIP Security Tests

Bundle loader tests cover safe ZIP behavior:

- reject absolute paths;
- reject path traversal;
- reject symlinks;
- extract in controlled temporary directories;
- clean up after validation.

## Invariants

Tests and code enforce or exercise:

- completed tasks do not exceed generated tasks;
- decision shares are explicit and deterministic;
- rejected bundles do not produce ordinary metrics;
- unavailable metrics have no numeric value;
- JSON contains no `NaN` or infinity;
- rules cite existing evidence keys;
- rules do not mutate EvidencePacks;
- repeated imports are idempotent;
- directory and ZIP bundles produce equivalent results.

## Fixture Policy

Synthetic fixtures are small and hand-auditable. They live under `tests/fixtures/` and are clearly labelled synthetic. Future real-schema fixtures must be sanitised and documented before committing.

## Diagnostic Evaluation Limit

The synthetic fault-injection precision/recall values are implementation checks over labelled synthetic cases. They are not evidence that R0-R3 are externally valid for Manchester, SUMO, or Randy/VEC runs.

Related documents:

- [Reproducibility guide](reproducibility.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Developer guide](developer_guide.md)

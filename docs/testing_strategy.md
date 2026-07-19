# Testing Strategy

TrafficTwin uses a test pyramid: focused unit tests at the base, integration tests for the pipeline, golden tests for deterministic outputs, and UI smoke tests where reliable.

## Current Snapshot

Verified after the Experiment Protocol Exporter increment:

- 229 tests passed.
- Coverage: 79%.

Coverage is a useful signal, not the only quality measure. Streamlit page rendering and CLI
workflows are partly covered through service tests, AppTest-style tests, and smoke commands rather
than exhaustive browser automation.

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
- rule configuration, registry, models, engine, and R0-R3 behavior;
- provenance trace models, graph validation, source-row preview, query service, serialisation, and
  Markdown export.

## Integration Tests

Located under `tests/integration/`.

They check:

- bundle import;
- directory and ZIP validation;
- bundle to metrics;
- bundle to diagnostics;
- evidence to diagnostics;
- bundle to provenance;
- diagnostic fixture to EvidencePack-only provenance;
- UI service/demo flows.

## Golden Tests

Located under `tests/golden/` with expected JSON under `tests/golden/expected/`.

Golden files verify exact projections for:

- baseline metrics;
- variation metrics;
- comparison output;
- validation reports;
- diagnostic reports;
- provenance trace projections and Markdown export.

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
traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
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
- provenance traces do not mutate metric or rule outputs;
- provenance exports contain no absolute local paths;
- source-row preview rejects path traversal;
- repeated imports are idempotent;
- directory and ZIP bundles produce equivalent results.
- generated standalone bundles validate through the existing Phase 2 path;
- standalone reports contain no unescaped HTML or absolute local paths;
- demo workspace reset requires explicit confirmation.

## Fixture Policy

Synthetic fixtures are small and hand-auditable. They live under `tests/fixtures/` and are clearly labelled synthetic. Future real-schema fixtures must be sanitised and documented before committing.

Standalone generated workspaces are created under temporary paths during tests. They are not committed
as fixtures; the generator configuration and deterministic tests provide reproducibility.

## Standalone Product Tests

Standalone tests cover:

- deterministic synthetic generation for fixed seeds;
- different seeds changing generated records;
- generated bundles passing the existing validator;
- expected R1/R2/R3 diagnostic behavior through EvidencePacks;
- demo workspace initialise/reset/status safety;
- Typer CLI smoke tests for demo, report, and provenance commands;
- HTML escaping and no absolute path leakage in reports.

## TOS Integration Tests

The optional read-only TOS integration is tested with a tiny package generated at test time. This
preserves the supplied schema and representative contracts without copying Randy's raw files into
TrafficTwin. Tests cover:

- evaluation CSV and JSON-summary reconciliation;
- supported engine/version gating;
- NPZ member path, symlink, pickle, decompressed-size, key, and shape safety;
- source-summary metric and partial EvidencePack construction;
- unchanged R0-R3 behavior over incomplete evidence;
- bounded replay and per-arrival inspection;
- confirmed-unit labels, time/slot action joins, and RSU concurrency-pressure calculation;
- versioned source-contract serialization and launch-blocker reporting;
- aggregate provenance to the source summary row;
- registry persistence, conflict checks, and idempotent imports;
- Typer and Streamlit service/AppTest workflows.

An optional local smoke pass validates the separately checked-out package and confirms its Git
worktree remains unchanged. Raw TOS files are not test fixtures and are not committed.

## Diagnostic Evaluation Limit

The synthetic fault-injection precision/recall values are implementation checks over labelled synthetic cases. They are not evidence that R0-R3 are externally valid for Manchester, SUMO, or Randy/VEC runs.

Current verified repository snapshot:

- tests: 229 passed;
- coverage: 79%.

Related documents:

- [Reproducibility guide](reproducibility.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Developer guide](developer_guide.md)
- [Provenance model](provenance_model.md)
- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)

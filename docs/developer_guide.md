# Developer Guide

This guide describes how to work on the current TrafficTwin prototype without weakening its import-first, deterministic architecture.

## Supported Python

The package declares Python 3.11 or newer. The local quality-gate environment used during this documentation pass is Python 3.12.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Runtime dependencies are declared in [pyproject.toml](../pyproject.toml):

- Pydantic v2
- PyYAML
- Typer
- Streamlit
- Plotly

Development dependencies:

- pytest
- pytest-cov
- Ruff
- mypy
- types-PyYAML

## Development Commands

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
.venv/bin/python scripts/generate_reference_docs.py
```

Use `python -m pytest` from the repository root so the local `tests` package is importable.

## Package Structure

```text
src/traffictwin/
├── adapters/      # raw-source boundaries; generic CSV currently implemented
├── canonical/     # in-memory canonical record models
├── config/        # seed IO and capability manifests
├── diagnostics/   # DiagnosticReport models and serialisation
├── domain/        # ScenarioSeed, Experiment, Run, enums
├── evidence/      # Evidence availability and EvidencePack builder
├── experiments/   # experiment-level grouping placeholders
├── ingestion/     # bundle loader, manifest, canonicalisation, fingerprints
├── metrics/       # metric definitions, calculators, comparison, aggregation
├── provenance/    # read-only trace DAG, source-row preview, JSON/Markdown export
├── rules/         # deterministic diagnostic rules R0-R3
├── storage/       # SQLite registry
├── ui/            # Streamlit app, services, components, pages
└── validation/    # validation codes, findings, reports, reconciliation
```

## Adding A Canonical Record

1. Add the Pydantic model in [canonical/records.py](../src/traffictwin/canonical/records.py).
2. Add a list field and count entry in [canonical/tables.py](../src/traffictwin/canonical/tables.py).
3. Add manifest support only if the source file kind is part of the bundle contract.
4. Add adapter parsing and validation.
5. Add evidence availability behavior.
6. Add tests for parsing, validation, provenance, and missing evidence.
7. Update [data_contract.md](data_contract.md), [run_bundle_spec.md](run_bundle_spec.md), and generated schemas.

Do not add a canonical field because a future simulator might have it. Add it when there is a supported source or a documented optional contract.

## Adding A Manifest Field

1. Update [ingestion/manifest.py](../src/traffictwin/ingestion/manifest.py).
2. Keep schema version behavior explicit.
3. Add validation tests for valid, missing, and invalid values.
4. Update bundle fixtures only when the new field is part of the documented contract.
5. Update [run_bundle_spec.md](run_bundle_spec.md) and generated Pydantic schemas.

Do not silently accept extra manifest fields; the current models use `extra="forbid"`.

## Adding A Metric

1. Add a `MetricDefinition` in [metrics/catalogue.py](../src/traffictwin/metrics/catalogue.py).
2. Implement the calculator in the correct domain module.
3. Return explicit unavailable or invalid results when evidence is missing.
4. Keep output ordering deterministic.
5. Add unit tests, fixture tests, and golden expected output if fixture data supports the metric.
6. Update [metrics_catalogue.md](metrics_catalogue.md), [evidence_pack_spec.md](evidence_pack_spec.md), and generated references.

Do not compute from raw CSV files. Metrics consume canonical records and evidence availability only.

## Adding A Diagnostic Rule

1. Define required metric/evidence keys.
2. Add versioned configuration in [rules/config.py](../src/traffictwin/rules/config.py).
3. Implement a rule class under [rules/](../src/traffictwin/rules/).
4. Register it in [rules/registry.py](../src/traffictwin/rules/registry.py).
5. Add catalogue metadata in [rules/catalogue.py](../src/traffictwin/rules/catalogue.py).
6. Add unit tests for triggered, not-triggered, insufficient, conflicting, disabled, and invalid paths.
7. Add synthetic fault-injection cases only if they are clearly labelled synthetic.
8. Update [diagnostic_rules.md](diagnostic_rules.md), [diagnostic_report_spec.md](diagnostic_report_spec.md), and generated references.

Rules consume only EvidencePack objects. They must not recompute metrics or read raw/canonical rows.

## Adding A Provenance Trace Root

1. Add builder support in [provenance/builder.py](../src/traffictwin/provenance/builder.py).
2. Expose a read-only query function in [provenance/query.py](../src/traffictwin/provenance/query.py).
3. Use existing `MetricCollection`, `EvidencePack`, `DiagnosticReport`, catalogues, and canonical `source_file`/`source_row` fields.
4. Add unavailable-reference nodes when a link is missing.
5. Add JSON and Markdown export coverage.
6. Add unit, integration, and golden tests.
7. Update [provenance_model.md](provenance_model.md) and [provenance_explorer.md](provenance_explorer.md).

Do not recompute metric values, reinterpret rule outputs, read unsafe paths, or invent row-level
contribution weights for aggregate metrics.

## Adding A Streamlit Page

1. Add page logic under [ui/pages/](../src/traffictwin/ui/pages/).
2. Add a label in [ui/labels.py](../src/traffictwin/ui/labels.py).
3. Add routing in [ui/app.py](../src/traffictwin/ui/app.py).
4. Put reusable display pieces under [ui/components/](../src/traffictwin/ui/components/).
5. Call library services through [ui/services.py](../src/traffictwin/ui/services.py).
6. Add tests for service models, chart/table data, state, and page guards.

Do not duplicate metric, validation, comparison, diagnostic, or provenance logic in Streamlit code.

Product polish pages follow the same rule. `Scenario Builder` may call the synthetic generator,
`Experiment Manager` may read registry/workspace metadata, `Reports` may call reporting builders,
and `Search` may scan local metadata. They must not add metrics, diagnostic rules, adapters, live
data, or launch behavior.

## Adding An Adapter Safely

1. Complete discovery first: source files, schemas, units, identifiers, row counts, provenance, and execution commands.
2. Document the mapping under `docs/integration/`.
3. Create sanitised real-schema fixtures if permitted.
4. Implement adapter-specific code outside `generic_csv`.
5. Preserve source file and row provenance.
6. Reject ambiguous units.
7. Generate a standard TrafficTwin run bundle or canonical records that pass Phase 2 validation.
8. Keep unsupported capabilities `false` or `unknown`.

Randy/VEC and SUMO adapters are currently blocked by missing artifacts.

## Registry Migration Principles

- Use additive schema changes where possible.
- Preserve existing seeds, experiments, runs, bundle imports, metrics, and evidence packs.
- Store large or row-level data outside SQLite unless a design decision justifies otherwise.
- Add tests for old-registry compatibility when schema changes.

## Deterministic Testing

- Use fixed clocks for golden outputs.
- Avoid wall-clock sleeps in replay or diagnostics tests.
- Avoid `NaN` and infinity in JSON.
- Compare projections when volatile timestamps are irrelevant.
- Verify repeated imports are idempotent.

## Golden-File Policy

Golden files encode expected behavior. Do not update them simply to make tests pass.

Before changing a golden file:

1. Identify the intended behavior change.
2. Update implementation and docs.
3. Recompute expected values from fixture rows.
4. Review the diff manually.

## Coding Conventions

- Keep modules small and domain-specific.
- Use Pydantic models for structured contracts.
- Use `pathlib.Path`.
- Keep side effects at CLI, UI, ingestion, or registry boundaries.
- Preserve raw inputs unchanged.
- Prefer explicit unavailable states over default zeros.
- Keep causal language out of deterministic rules and UI copy.

## Commit Conventions

Use clear conventional-style messages, for example:

- `feat(metrics): add trip duration metric`
- `test(golden): update baseline expected metrics`
- `docs(integration): document randy schema sample`
- `chore(docs): regenerate reference artifacts`

## Common Failure Modes

| Symptom | Likely cause | Response |
|---|---|---|
| `ModuleNotFoundError: tests` | Running pytest through an entry point that omits repo root | Use `.venv/bin/python -m pytest`. |
| Bundle rejected before metrics | Manifest or seed invalid | Inspect `traffictwin bundle report PATH --format json`. |
| Metric shows unavailable | Required table/field missing | Check evidence availability and reason codes. |
| R3 insufficient | Single-run EvidencePack lacks experiment-level metrics | Use experiment-level evidence in future work. |
| Direct launch disabled | No adapter reports support | Keep export/import workflow. |

## Standalone Product Development

Standalone modules are wrappers around the existing pipeline:

- `src/traffictwin/synthetic/` writes standard bundles.
- `src/traffictwin/demo/` prepares a marked workspace and imports bundles through the registry.
- `src/traffictwin/reporting/` renders existing objects into Markdown or HTML.
- `src/traffictwin/release/` exposes lightweight release metadata.

When adding a new synthetic scenario:

1. Add a preset in `synthetic/scenarios.py`.
2. Ensure generated files validate through `validate_bundle`.
3. Add a test proving deterministic generation for a fixed seed.
4. Document the scenario as synthetic and avoid real-world claims.

Do not add new metrics, rules, or simulator behavior from the standalone layer. If a scenario needs
new evidence, first extend the canonical contract and metric/rule layers deliberately.

Related documents:

- [Architecture](architecture.md)
- [API reference](api_reference.md)
- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)
- [Report export](report_export.md)
- [Provenance model](provenance_model.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility guide](reproducibility.md)
- [ADR index](decisions/index.md)

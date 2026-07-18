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

## Adding A Streamlit Page

1. Add page logic under [ui/pages/](../src/traffictwin/ui/pages/).
2. Add a label in [ui/labels.py](../src/traffictwin/ui/labels.py).
3. Add routing in [ui/app.py](../src/traffictwin/ui/app.py).
4. Put reusable display pieces under [ui/components/](../src/traffictwin/ui/components/).
5. Call library services through [ui/services.py](../src/traffictwin/ui/services.py).
6. Add tests for service models, chart/table data, state, and page guards.

Do not duplicate metric, validation, comparison, or diagnostic logic in Streamlit code.

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

Related documents:

- [Architecture](architecture.md)
- [API reference](api_reference.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility guide](reproducibility.md)
- [ADR index](decisions/index.md)

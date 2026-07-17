# TrafficTwin Initial Architecture

This document proposes the Phase 1-4 architecture for the protected vertical slice. It is based on the canonical v0.4 design text at `docs/traffictwin-design-v0_4.md` and the current repository evidence. No Randy integration, live feed, or real simulator capability is assumed.

## Architectural Goal

TrafficTwin should be a tested research-software library with a thin Streamlit interface. The guaranteed workflow is import-first:

```text
Scenario seed YAML
        |
        v
Seed validation and registry
        |
        v
Export or import completed run bundle
        |
        v
Bundle and data validation
        |
        v
Canonical records
        |
        v
Deterministic metrics
        |
        v
Evidence pack
        |
        v
Deterministic diagnostic hypotheses
        |
        v
Streamlit views and documentation
```

Direct launch is an adapter capability, not a default feature. The UI may show a Run action only when an adapter proves support for direct execution.

## Core Boundaries

### Config

Owns versioned seed schemas, capability manifests, and YAML I/O.

Phase 1 modules:

- `config.capabilities`
- `config.seed_io`

### Domain

Owns first-class research objects independent of file formats and UI:

- `ScenarioSeed`
- `Experiment`
- `Run`
- canonical record models where lightweight Pydantic validation is useful
- evidence and diagnostic output structures in later phases

### Adapters

Own uncertainty at the edges. Adapter interfaces should describe what an environment can do and how raw files map to canonical records.

Initial adapter plan:

- `synthetic`: creates deterministic fixture bundles only.
- `generic_csv`: imports the documented bundle contract only.
- `sumo`, `vec`, and `sensor`: interface stubs later, with unavailable capabilities until real contracts exist.

### Ingestion And Validation

Ingestion must preserve raw files and produce a validation report before metrics run.

Validation outputs must include:

- errors
- warnings
- info findings
- machine-readable codes
- affected file and row references
- `metrics_may_proceed`
- unavailable metric reasons

### Storage

Phase 1 uses SQLite for metadata and filesystem paths for raw/canonical/derived artifacts. It is simpler and sufficient while there are no data-volume requirements.

Proposed layout:

```text
diss/data/
    raw/
    canonical/
    derived/
    registry/
```

DuckDB and Parquet can be introduced when run sizes or cross-run analytics justify them.

### Metrics

Metrics should be registered by stable metadata:

- key
- human name
- definition
- required fields
- units
- aggregation level
- implementation version

Metrics must refuse to run when required canonical fields are absent.

### Rules

Rules consume evidence packs, not raw data. Rule outputs are diagnostic hypotheses with alternatives and missing evidence, never proven causes.

Phase 2 starts with R0. Phase 5 completes R1-R3 after metrics and comparison are stable.

### Experiments And Comparison

Experiments group baseline and variation seeds, algorithms, checkpoints, and common random seeds. Comparison should pair runs by random seed where possible and report missing evidence rather than forcing conclusions.

### Launcher

The only guaranteed launcher is `export_only`. A subprocess launcher should remain unavailable until a documented external command exists.

### Replay

Replay uses a logical clock over imported historical or synthetic records. Tests advance the clock directly and do not depend on wall-clock sleeping.

### UI

Streamlit pages should read from services and registries, not compute research logic inline.

First UI pages after the library slice:

- Home / Project Status
- Scenario Studio
- Import Run Bundle
- Operations View
- Run Overview
- Infrastructure & Congestion
- What-if Compare
- Journey-Time Lens
- Diagnostic Hypotheses

Every replay or fixture view must label the data mode, for example `Historical Replay` or `Synthetic Fixture`.

## Implemented Phase 1 Package Tree

```text
diss/
    README.md
    pyproject.toml
    .gitignore
    src/
        traffictwin/
            __init__.py
            cli.py
            config/
                __init__.py
                capabilities.py
                seed_io.py
            domain/
                __init__.py
                enums.py
                experiment.py
                run.py
                scenario.py
            storage/
                __init__.py
                registry.py
    tests/
        fixtures/
            seeds/
                invalid_class_mix.yaml
                invalid_schema_version.yaml
        unit/
            test_seed_io.py
            test_scenario.py
            test_capabilities.py
            test_registry.py
```

## Current Package Boundary

Implemented:

- domain models
- YAML seed I/O
- capability manifest
- SQLite metadata registry
- CLI
- unit tests
- run-bundle manifests
- directory and ZIP bundle loading
- generic CSV adapter
- in-memory canonical records
- validation reports
- evidence availability
- idempotent bundle import
- golden and integration tests

Not implemented:

- metrics
- full diagnostic rules
- Streamlit
- external adapters
- launchers

## Implemented Phase 2 Package Additions

```text
diss/
    src/
        traffictwin/
            adapters/
                __init__.py
                base.py
                generic_csv.py
            canonical/
                __init__.py
                records.py
                tables.py
            evidence/
                __init__.py
                availability.py
                insufficient.py
            ingestion/
                __init__.py
                bundle.py
                canonicalise.py
                hashes.py
                loader.py
                manifest.py
            validation/
                __init__.py
                codes.py
                findings.py
                files.py
                manifest.py
                report.py
                reconciliation.py
                rows.py
    tests/
        fixtures/
            bundles/
                baseline_valid/
                variation_valid/
                partial_valid/
                invalid_manifest/
                invalid_rows/
        golden/
        integration/
```

Phase 2 keeps validation orchestration focused in `ingestion.bundle` and row conversion in `adapters.generic_csv`; the empty validation placeholder modules document the intended later split without adding behaviour.

## Dependency Set

Runtime:

- Python 3.11+
- Pydantic v2
- PyYAML
- Typer

Development:

- pytest
- pytest-cov
- Ruff
- mypy
- types-PyYAML

Deferred:

- pandas
- DuckDB
- Polars
- PyArrow
- Streamlit
- Plotly
- pre-commit

## Capability Model

Capabilities should use three-valued support:

- `true`: explicitly supported by the selected adapter.
- `false`: explicitly unsupported.
- `unknown`: not evidenced.

For `generic_csv`, initial capabilities should be:

```yaml
environment:
  adapter: generic_csv
  supports:
    seed_import: true
    seed_export: true
    run_bundle_import: true
    direct_launch: false
    asynchronous_launch: false
    task_arrival_multiplier: unknown
    workload_class_mix: unknown
    workload_ordering: unknown
    vehicle_count: unknown
    vehicle_tier_mix: unknown
    rsu_count: unknown
    rsu_capacity: unknown
    rsu_placement: unknown
    rsu_failure: unknown
    action_toggles: unknown
    signal_timing: unknown
    lane_closure: unknown
```

Synthetic fixtures may support controlled fixture generation, but must be labelled synthetic and must not imply real Randy execution.

## Smallest Vertical Slice

The smallest complete slice is a deterministic synthetic baseline-versus-variation workflow:

- two seed YAML files
- two synthetic run bundles
- manifest validation
- CSV validation
- canonical task, infrastructure, traffic, and trip tables
- deterministic metrics
- baseline/variation comparison
- R0-R3 evidence outputs
- Streamlit display with explicit synthetic/replay labels

This slice proves the research-software contract without fabricating external integration.

## Initial ADR Candidates

- ADR-001: Import-first architecture and export-only fallback.
- ADR-002: Three-valued capability manifest.
- ADR-003: SQLite metadata registry before DuckDB/Parquet.
- ADR-004: Deterministic metrics and rules before UI.
- ADR-005: Synthetic fixtures as golden integration evidence.

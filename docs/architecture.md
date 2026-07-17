# TrafficTwin Initial Architecture

This document proposes the Phase 1-5 architecture for the protected vertical slice. It is based on the canonical v0.4 design text at `docs/traffictwin-design-v0_4.md` and the current repository evidence. No Randy integration, live feed, or real simulator capability is assumed.

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

Direct launch is an adapter capability, not a default feature. The UI may show a Run action only when an adapter documents support for direct execution.

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

Implemented Phase 3 modules:

- `metrics.catalogue` and `metrics.definitions` register stable metric definitions.
- `metrics.engine` orchestrates deterministic calculation over canonical records.
- `metrics.task`, `metrics.infrastructure`, `metrics.traffic`, and `metrics.trips` own domain calculators.
- `metrics.comparison` compares baseline and variation metric collections.
- `metrics.aggregation` provides descriptive experiment-level summaries.
- `evidence.pack` and `evidence.builder` create versioned evidence packs for deterministic rules.

### Rules

Rules consume evidence packs, not raw data. Rule outputs are diagnostic hypotheses with alternatives and missing evidence, never proven causes.

Implemented Phase 5 modules:

- `rules.config` owns versioned provisional thresholds.
- `rules.models` owns rule statuses, findings, confidence categories, and conditional recommendations.
- `rules.r0_insufficient_evidence` implements data-readiness qualification.
- `rules.r1_under_offloading` implements the under-offloading candidate.
- `rules.r2_infrastructure_bottleneck` implements the infrastructure-bottleneck candidate.
- `rules.r3_scenario_triviality` implements the scenario-triviality candidate when experiment-level EvidencePack metrics exist.
- `rules.engine` evaluates rules independently and validates cited evidence keys.
- `diagnostics.report` owns the versioned DiagnosticReport contract.

R3 returns `insufficient_evidence` for ordinary single-run EvidencePacks because cross-algorithm dispersion is not present there.

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
- Evidence & Diagnostic Hypotheses

Every replay or fixture view must label the data mode, for example `Historical Replay` or `Synthetic Fixture`.

Implemented Phase 4 UI boundary:

- `ui.services` calls Phase 1-3 library functions.
- `ui.state` owns reconstructable session defaults and logical replay clock state.
- `ui.charts` and `ui.tables` prepare display data without metric formulas.
- `ui.pages` render Streamlit pages and guard rejected bundles from analysis views.
- Direct launch remains disabled for the default generic CSV adapter.

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
- deterministic metric catalogue and engine
- task, infrastructure, traffic, and trip metrics
- baseline-versus-variation comparison
- descriptive experiment aggregation
- versioned evidence packs
- metric/evidence JSON references in the SQLite registry
- Streamlit application shell
- Home, Scenario Studio, Bundle Import, Operations, Run Overview, Infrastructure, Compare, Journey-Time, and Evidence & Diagnostic Hypotheses pages
- deterministic rules R0-R3
- versioned diagnostic reports
- synthetic fault-injection evaluation utility
- golden and integration tests

Not implemented:

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

## Implemented Phase 3 Package Additions

```text
diss/
    src/
        traffictwin/
            metrics/
                __init__.py
                aggregation.py
                availability.py
                catalogue.py
                comparison.py
                definitions.py
                engine.py
                engine_config.py
                infrastructure.py
                results.py
                statistics.py
                task.py
                traffic.py
                trips.py
            evidence/
                builder.py
                pack.py
            experiments/
                __init__.py
                aggregation.py
                comparison.py
                grouping.py
```

Phase 3 remains library-first. The CLI calls these modules, and future Streamlit pages should do the same rather than recomputing metrics in the UI.

## Implemented Phase 4 Package Additions

```text
diss/
    src/
        traffictwin/
            ui/
                app.py
                charts.py
                formatting.py
                labels.py
                navigation.py
                services.py
                state.py
                tables.py
                components/
                pages/
```

The UI launch command is:

```bash
streamlit run src/traffictwin/ui/app.py
```

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

This slice demonstrates the research-software contract without fabricating external integration.

## Initial ADR Candidates

- ADR-001: Import-first architecture and export-only fallback.
- ADR-002: Three-valued capability manifest.
- ADR-003: SQLite metadata registry before DuckDB/Parquet.
- ADR-004: Deterministic metrics and rules before UI.
- ADR-005: Synthetic fixtures as golden integration evidence.

# TrafficTwin Implementation Status

Phase 0 status: approved. Repository and contract discovery are complete for the current workspace.

## Repository Assessment

Workspace root inspected: `/Users/akashx/AntigravityTest`

TrafficTwin project root: `diss/`

This was confirmed by Abdulla before Phase 1 began.

## Existing Contents

| Path | Type | Assessment |
|---|---|---|
| `diss/AGENTS.md` | Agent instruction document | Concise active implementation guidance. Points agents to the canonical product specification. |
| `diss/docs/traffictwin-design-v0_4.md` | Canonical design specification | Complete attached TrafficTwin v0.4 design copy, preserved exactly from the supplied attachment. |
| `XITS/README.md` | Research workspace note | Earlier project note. States materials were still being collected and design should not be locked before `MATERIALS COMPLETE`. |
| `XITS/research_context.md` | Research context note | Earlier ITS framing and working rules. Useful historical context, not implementation code. |
| `XITS/source_inventory.md` | Literature/source inventory | Contains a supplied reading list and claims requiring later verification. No PDFs or data files are present. |
| `XITS/open_questions.md` | Earlier open questions | Superseded in part by the TrafficTwin brief, but still useful for provenance. |
| `colab_smoke_test.py` | Small Python script | Standalone JSON/platform smoke test. Not part of TrafficTwin. |

## Relevant Assets Found

- No existing TrafficTwin package.
- No `pyproject.toml`, dependency lockfile, or test configuration.
- No existing `README.md` for TrafficTwin.
- No CSV, TSV, JSON, YAML, Parquet, SQLite, SUMO, notebook, run-bundle, or simulator files were found in the inspected workspace.
- No Git repository metadata was found at `/Users/akashx/AntigravityTest`.
- No Randy VEC environment, SUMO network, launch script, API, schema, checkpoint, or logs were found.

## Design Specification Status

Requested primary design paths:

- `./traffictwin-design-v0_4.md`: not found.
- `./docs/traffictwin-design-v0_4.md`: present when `diss/` is treated as the project root.

Design source used for Phase 0:

- `diss/AGENTS.md`: attached v0.4 design copy, 445 lines, read completely before relocation.
- `diss/docs/traffictwin-design-v0_4.md`: canonical specification after relocation.

## Confirmed From Repository Evidence

- The wider workspace contains historical research notes, a small smoke-test script, and the confirmed `diss/` project root.
- The TrafficTwin v0.4 design exists at `diss/docs/traffictwin-design-v0_4.md`.
- There is currently no executable project scaffold.
- There is currently no real run data, no simulator integration, and no environment adapter evidence.
- The import-first architecture is necessary because no headless execution contract is present.

## Unknown Or Unconfirmed

- Randy's CSV schema, file names, units, task columns, RSU logging fields, and trip-output availability.
- Whether Randy's environment supports headless launch, seed overrides, or a Python API.
- Whether SUMO networks, FCD output, trip output, or Manchester sensor data can be supplied.
- Whether environment versions, commits, checkpoints, and random seeds are available in completed runs.
- Which scenario controls are truly executable in Randy's environment.
- Whether the dissertation should lead with OffloadLens, journey-time analysis, or the dual-lens framing.
- Whether user evaluation will be formal and ethics-approved.

## Implemented

- Phase 0 discovery notes.
- Initial architecture proposal.
- Initial open questions.
- Initial assumption register.
- Canonical design specification relocation.
- Concise `AGENTS.md`.
- Python `.gitignore`.

## Partially Implemented

- None for Phase 0.

## Blocked

- Real VEC/SUMO adapters are blocked until representative run bundles, schemas, and invocation details are supplied.
- Direct launch is blocked until a documented CLI, Python API, or script contract exists.
- Live or near-live modes are blocked until real feed details exist.
- Claims about algorithm performance, training checkpoints, and paper gaps are blocked until primary evidence is verified.

## Not Started

- Python package scaffold.
- Pydantic schemas.
- Seed YAML import/export.
- Capability manifest.
- Registries.
- Run-bundle ingestion.
- Validation.
- Canonicalisation.
- Metrics.
- Diagnostic rules.
- Streamlit UI.
- Tests.
- Synthetic fixtures.

## Evidence Required Next

- One example of Randy's completed run output, even if partial.
- Header rows and units for task, infrastructure, vehicle, traffic, trip, and incident files.
- Confirmation of supported scenario controls.
- Environment invocation contract, if direct launch is expected.

## Phase 1 Proposed File Tree

Phase 1 should create only core schemas, seed I/O, capability handling, registries, tests, and packaging.

```text
diss/
    README.md
    pyproject.toml
    ruff.toml
    .gitignore
    traffictwin/
        __init__.py
        cli.py
        config/
            __init__.py
            capabilities.py
            models.py
            seed_io.py
        domain/
            __init__.py
            enums.py
            experiment.py
            models.py
            run.py
        storage/
            __init__.py
            paths.py
            registry.py
            metadata.py
        validation/
            __init__.py
            report.py
    tests/
        fixtures/
            seeds/
                valid_seed.yaml
                invalid_seed.yaml
        unit/
            test_seed_io.py
            test_seed_validation.py
            test_capabilities.py
            test_registry.py
```

## Phase 1 Proposed Dependencies

Runtime:

- `pydantic>=2`
- `pyyaml`
- `typer`
- `rich`
- `pandas`
- `plotly`
- `streamlit`

Development:

- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`
- `types-PyYAML`

Deferred until data scale or integration evidence justifies them:

- `duckdb`
- `polars`
- `pyarrow`
- `pre-commit`

Explicitly excluded for the protected vertical slice:

- FastAPI
- React
- Celery
- Redis
- Kafka
- cloud infrastructure
- microservice scaffolding

## Smallest Complete Synthetic Vertical Slice

The smallest end-to-end demonstration should stay import-first and synthetic:

1. Create baseline and variation `ScenarioSeed` YAML files.
2. Baseline: normal demand, standard RSU capacity, mixed fleet.
3. Variation: doubled demand, one RSU capacity reduced, same random seed.
4. Generate two synthetic run bundles with `manifest.yaml`, `seed.yaml`, `tasks.csv`, `infra_state.csv`, `traffic_obs.csv`, and `trips.csv`.
5. Validate both bundles before metrics.
6. Canonicalise task, infrastructure, traffic, and trip records.
7. Compute deterministic metrics for task completion, latency, offload share, RSU utilisation, queue length, traffic speed/count, and trip duration.
8. Compare baseline versus variation by aligned random seed.
9. Run R0-R3 on the evidence pack.
10. Show the result in Streamlit using replay-labelled historical/simulated fixture data.

Fixture values must be labelled synthetic and must not be presented as Randy or Manchester results.

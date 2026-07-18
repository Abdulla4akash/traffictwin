# TrafficTwin Implementation Status

Phase 0 status: approved and committed.

Phase 1 status: implemented and committed.

Phase 2 status: implemented and quality-gate checked.

Phase 3 status: implemented and quality-gate checked.

Phase 4 status: implemented and quality-gate checked.

Phase 5 status: implemented and quality-gate checked.

Phase 6 status: the evidenced read-only TOS Data boundary and `vec_env` source audit are
implemented. Evaluation summaries can be imported; instrumented arrays support unit-aware replay,
task/action inspection, and RSU active-task/backlog inspection; a versioned source contract records
field semantics, controls, execution evidence, and blockers. Full canonical conversion, canonical
RSU metrics, SUMO XML/trips, and launch remain blocked.

Documentation pass status: completed and quality-gate checked.

Productisation Provenance Explorer status: implemented. The explorer is read-only and traces
metrics, diagnostic rule results, source rows, run metadata, metric definitions, validation
findings, EvidencePacks, DiagnosticReports, and bundle fingerprints where existing Phase 1-5
artifacts provide the links.

Standalone Product status: implemented. TrafficTwin can now create a deterministic synthetic demo
workspace, generate standard run bundles, import them through the existing registry path, compute
metrics, build EvidencePacks, evaluate diagnostics, prepare provenance traces, export
Markdown/HTML reports, and launch Streamlit without Randy/VEC, SUMO, live data, or external
services.

Product Polish & Research UX status: implemented. The Streamlit UI now includes Scenario Builder,
Experiment Manager, Reports, Search, Settings, About, improved Replay controls, shared badges/cards,
and a clearer Home dashboard. This is workflow polish only; it adds no new metrics, diagnostic
rules, simulator adapters, live data, launchers, ML algorithms, or LLM behavior.

TOS Results Workbench status: implemented. The optional read-only integration now includes an
evaluation matrix, exact fleet-seed paired campaign comparison, processed-FCD logical replay,
source-specific RSU pressure/backlog summaries, full showcase task aggregation, bounded training
histories, conservative generalisation labels, a reproducibility audit, deterministic research
reports, and a self-contained aggregate atlas. These features do not change canonical metrics,
diagnostic rules, direct-launch capability, or external-integration blockers.

## Repository Assessment

Workspace root inspected: repository parent workspace

TrafficTwin project root: `diss/`

Git repository: initialised inside `diss/` on branch `main`.

Canonical product specification: `docs/traffictwin-design-v0_4.md`

The historical `../XITS/` notes remain unchanged as research material. They are not active implementation blockers for the approved TrafficTwin v0.4 build.

## Existing Contents

| Path | Type | Assessment |
|---|---|---|
| `AGENTS.md` | Agent instruction document | Concise active implementation guidance. Points agents to the canonical product specification. |
| `docs/traffictwin-design-v0_4.md` | Canonical design specification | Complete attached TrafficTwin v0.4 design copy, preserved exactly from the supplied attachment. |
| `pyproject.toml` | Packaging and tool configuration | Python 3.11+ package metadata, runtime dependencies, dev extras, pytest, Ruff, mypy. |
| `README.md` | Quick start | Minimal install and CLI examples with current-scope disclaimer. |
| `src/traffictwin/` | Python package | Phase 1 domain models, seed I/O, capabilities, registry, and CLI. |
| `examples/seeds/arena_gridlock.yaml` | Example seed | Valid synthetic Phase 1 seed. |
| `tests/fixtures/bundles/` | Synthetic run bundles | Baseline, variation, partial, invalid-manifest, and invalid-row fixtures. |
| `docs/run_bundle_spec.md` | Contract documentation | Run-bundle format, manifest, units, ZIP safety, partial bundles, idempotency. |
| `docs/data_contract.md` | Canonical data documentation | Phase 2 in-memory canonical record contract. |
| `docs/validation_codes.md` | Validation documentation | Stable validation code catalogue and severity policy. |
| `tests/` | Test suite | Unit, golden, and integration tests. |
| `docs/metrics_catalogue.md` | Metrics documentation | Phase 3 metric definitions, formulas, availability, and percentile policy. |
| `docs/evidence_pack_spec.md` | Evidence documentation | Versioned evidence-pack contract for future deterministic rules. |
| `docs/comparison_methodology.md` | Comparison documentation | Pairwise comparison and descriptive aggregation policy. |
| `docs/user_guide.md` | User guide | Phase 5 launch and workflow instructions. |
| `docs/diagnostic_rules.md` | Rules documentation | R0-R3 logic, thresholds, evidence requirements, and limitations. |
| `docs/diagnostic_report_spec.md` | Report documentation | Versioned DiagnosticReport schema and evidence-key policy. |
| `docs/fault_injection_methodology.md` | Evaluation documentation | Synthetic fault-injection cases and engineering evaluation limits. |
| `docs/ui_design.md` | UI design | Streamlit page structure and presentation policy. |
| `docs/demo_script.md` | Demo script | Keystone synthetic demonstration steps and expected states. |
| `docs/integration/` | Integration discovery documentation | Phase 6A artifact inventory, schema mapping, execution contract, gap analysis, and implementation decision. |
| `docs/index.md` | Documentation index | Organised guide to all current documentation. |
| `docs/system_overview.md` | System overview | Problem, platform vision, protected vertical slice, workflow, and integration boundary. |
| `docs/developer_guide.md` | Developer guide | Setup, package structure, extension points, and contribution rules. |
| `docs/cli_reference.md` | CLI reference | Current Typer commands only, with examples and exit behavior. |
| `docs/api_reference.md` | API reference | Principal public Python interfaces. |
| `docs/reproducibility.md` | Reproducibility guide | Deterministic design choices, fingerprints, commands, fixture provenance. |
| `docs/testing_strategy.md` | Testing strategy | Test pyramid, invariants, fixture policy, and coverage interpretation. |
| `docs/viva_guide.md` | Viva guide | Concise answers to likely supervisor/examiner questions. |
| `docs/decisions/` | ADRs | Concise architecture decision records for major project decisions. |
| `src/traffictwin/provenance/` | Provenance package | Read-only trace graph, query service, source-row previews, and JSON/Markdown export. |
| `docs/provenance_explorer.md` | Provenance documentation | User and CLI workflow for trace inspection. |
| `docs/provenance_model.md` | Provenance model documentation | Trace model, current row-level gaps, and aggregate limitations. |
| `src/traffictwin/synthetic/` | Synthetic generator | Deterministic standalone scenario, bundle, and experiment generation. |
| `src/traffictwin/demo/` | Demo workspace | Safe workspace initialisation, reset, status, and Streamlit launch helpers. |
| `src/traffictwin/reporting/` | Report export | Deterministic Markdown and standalone HTML research reports. |
| `.github/workflows/ci.yml` | CI workflow | Python 3.11/3.12 quality gates and standalone smoke checks. |
| `src/traffictwin/integration/tos/` | TOS Data integration | Versioned source contract, read-only validation/import, unit-aware replay, task/action and RSU-state inspection, partial evidence, and provenance. |
| `docs/integration/tos_data_adapter.md` | Integration guide | Supported TOS boundary, semantics, CLI, security, and limitations. |

## Relevant Assets Found

- Randy's external `TOS Data` package is present outside `diss/` at `external/tos-data`.
- Randy's external `vec_env` source is present outside `diss/` at `external/vec_env`; TrafficTwin
  records inspected source commit `e98441196270b8fd4cc0eede892df4a0053b2185` as semantics evidence,
  not as the asserted producer of every run.
- The external package includes evaluation summary CSV, training curves, greedy-evaluation JSON, instrumented per-step NPZ files, instrumented per-task NPZ files, Manchester trace NPZ files, and training-record documentation.
- The source repository includes an evaluator and CSF-specific scripts, but actor checkpoints, the
  instrumented-array writer, raw SUMO XML/config, and a locally verified path-independent runtime
  are unavailable.
- The only CSV/YAML/JSON run artifacts present are TrafficTwin synthetic fixtures under `tests/fixtures/`.
- A read-only external TOS Data results integration is implemented; it cannot execute the source
  environment.
- Streamlit UI is implemented for synthetic fixtures and imported historical bundles.
- Deterministic diagnostic rules R0-R3 are implemented over EvidencePacks.
- No full Randy/VEC canonical converter, SUMO adapter, direct launcher, or canonical row storage
  for TOS runs is implemented.
- Python 3.12 is available locally and was used for validation. The package declares Python 3.11+ support.

## Design Specification Status

Requested primary design paths:

- `./traffictwin-design-v0_4.md`: not used.
- `./docs/traffictwin-design-v0_4.md`: present when `diss/` is treated as the project root.

The canonical design file was copied byte-for-byte from the supplied attachment before `AGENTS.md` was replaced with concise instructions.

## Implemented In Phase 0

- Repository assessment.
- Initial implementation status, assumption register, open questions, and architecture proposal.
- Canonical design specification relocation.
- Concise `AGENTS.md`.
- Python `.gitignore`.
- Initial Git commit.

## Implemented In Phase 1

- `src/` package layout.
- `ScenarioSeed`, `Experiment`, and `Run` domain models.
- Supporting enums and nested seed configuration models.
- Explicit seed schema version handling with supported version `1.0`.
- Strict Pydantic v2 validation using `extra="forbid"`.
- Seed YAML load, validation, deterministic dump, and normalisation.
- Valid example seed and invalid seed fixtures.
- Three-valued capability manifest: `true`, `false`, `unknown`.
- Export/import-only default manifest for `generic_csv`.
- SQLite metadata registry for seeds, experiments, and runs.
- Duplicate-ID rejection.
- Creation and update timestamps.
- Basic status transitions with invalid-transition rejection.
- Minimal Typer CLI:
  - `validate-seed`
  - `normalise-seed`
  - `capabilities`
  - `registry init`
  - `registry inspect`
- Focused unit tests.

## Implemented In Phase 2

- Versioned `manifest.yaml` model.
- Directory and safe ZIP bundle loading.
- Manifest-driven generic CSV adapter.
- Canonical in-memory records for tasks, infrastructure, vehicles, traffic observations, trips, and incidents.
- Schema, file, unit, row, and reconciliation validation.
- Machine-readable validation report with JSON export.
- Evidence availability summary.
- Minimal R0-compatible insufficient-evidence summary.
- Synthetic baseline, variation, partial, invalid-manifest, and invalid-row bundles.
- Registry bundle-import metadata and idempotent import behavior.
- CLI commands:
  - `bundle validate`
  - `bundle inspect`
  - `bundle import`
  - `bundle report`
- Run-bundle, data-contract, and validation-code documentation.
- Unit, golden, and integration tests.

## Implemented In Phase 3

- Stable metric-definition catalogue.
- Metric result models with available, unavailable, partial, and invalid statuses.
- Deterministic metric engine over Phase 2 canonical records.
- Task metrics:
  - generated and completed counts;
  - completion and incomplete rates;
  - completion by class;
  - deadline-miss rate over completed observed tasks;
  - latency count, mean, P50, and P95;
  - decision counts and shares;
  - offload rate;
  - drop and energy metrics as unavailable when evidence is absent.
- Infrastructure metrics:
  - per-RSU summary;
  - observed RSU count;
  - queue mean and max;
  - utilisation mean and P95;
  - configurable saturation episode count and duration;
  - capacity-normalised load balance as unavailable without capacity and active-task evidence.
- Traffic metrics:
  - observation count;
  - total and mean counts;
  - mean, P50, P95, and minimum speed;
  - time coverage;
  - sensor count.
- Trip metrics:
  - record, completed, and incomplete counts;
  - completion rate;
  - duration count, mean, P50, P95, min, and max.
- Versioned evidence-pack model and builder.
- Baseline-versus-variation comparison model and deterministic seed-parameter diff.
- Experiment-level descriptive aggregation and paired random-seed differences.
- Additive SQLite tables for metric collection JSON and evidence-pack JSON references.
- CLI commands:
  - `metrics compute`
  - `metrics report`
  - `compare`
  - `evidence build`
  - `experiment summarise`
- Golden expected metric and comparison outputs for synthetic fixtures.

## Implemented In Phase 4

- Streamlit application shell at `src/traffictwin/ui/app.py`.
- UI state defaults and logical replay clock.
- UI service layer over Phase 1-3 library functions.
- Home / Project Status page.
- Scenario Studio with YAML preview, seed validation, export, and disabled direct-launch control.
- Bundle Import & Validation page.
- Operations View in historical replay mode.
- Run Overview page.
- Infrastructure & Congestion page.
- What-if Compare page.
- Journey-Time Lens page.
- Evidence & Diagnostic Readiness page, later updated in Phase 5.
- Reusable UI components for badges, cards, validation, provenance, unavailable states, and selectors.
- Plotly chart preparation for traffic, infrastructure, task events, trip durations, and metric availability.
- UI tests for formatting, state, chart data, service models, page guards, and AppTest startup.
- Demo documentation and UI design notes.

## Implemented In Phase 5

- Versioned diagnostic rule configuration.
- Rule result models with triggered, not-triggered, insufficient-evidence, conflicting-evidence, and invalid statuses.
- Deterministic R0 data-readiness rule.
- Deterministic R1 under-offloading candidate rule.
- Deterministic R2 infrastructure-bottleneck candidate rule.
- Deterministic R3 scenario-triviality candidate rule.
- Rule registry and catalogue.
- Rule engine with independent execution, disabled-rule support, evidence-key validation, and exception isolation.
- Versioned DiagnosticReport model with readiness, provenance, warnings, and conflict observations.
- Synthetic fault-injection fixture set with development and held-out labels.
- Fault-injection evaluation utility reporting precision, recall, support count, and confusion table.
- CLI commands:
  - `diagnose bundle`
  - `diagnose evidence`
  - `diagnose report`
  - `diagnose evaluate`
- UI page updated to Evidence & Diagnostic Hypotheses with rule results, alternatives, missing evidence, confidence basis, thresholds, and JSON download.
- Golden diagnostic expected outputs.
- Unit, golden, integration, and UI tests.

## Implemented In Productisation Provenance Explorer Phase

- Versioned provenance trace models:
  - `ProvenanceNode`;
  - `ProvenanceEdge`;
  - `ProvenanceTrace`;
  - `SourceRowPreview`.
- Internal deterministic trace graph with edge endpoint validation.
- Metric trace builder from `MetricCollection`, metric catalogue, canonical tables, validation
  findings, source rows, manifest, run, seed, experiment, environment, and fingerprint.
- Diagnostic-rule trace builder from `DiagnosticReport`, findings, evidence keys, metric results,
  metric definitions, canonical evidence, and unavailable links.
- EvidencePack-only diagnostic trace support with canonical/source-row links explicitly unavailable.
- Safe CSV source-row preview using existing Phase 2 bundle loader and bundle-relative paths.
- Provenance query service for bundle-backed traces.
- JSON and deterministic Markdown export.
- Typer commands:
  - `provenance metric`
  - `provenance rule`
  - `provenance run`
  - `provenance source`
  - `provenance export`
- Streamlit `Provenance Explorer` page.
- Golden provenance trace projections and Markdown output.
- Documentation:
  - `docs/provenance_explorer.md`
  - `docs/provenance_model.md`
  - `docs/viva_traceability_demo.md`

Known limitation: Phase 3 metrics do not store materialised per-row contribution lists for every
aggregate metric. Provenance therefore reports required tables, eligible record counts, source-row
samples, and limitations rather than fabricated row-level contribution weights.

## Implemented In Phase 6

- Initial repository and workspace discovery for Randy/VEC and SUMO artifacts.
- Updated discovery after Randy granted GitLab access to the external `TOS Data` package.
- Confirmation that real Randy/VEC result artifacts are now present outside `diss/` in `external/tos-data`.
- Inspection of the separately granted `vec_env` repository and its reproducibility, environment,
  evaluator, trace-builder, configuration, and SLURM source.
- Confirmation that the external package is not a standard TrafficTwin run bundle.
- Confirmation that raw SUMO XML/config, checkpoint files, and the instrumented NPZ writer are not
  supplied; the evaluator/SLURM scripts are not yet safe TrafficTwin launch contracts.
- Documentation of the distinction between summary metrics, instrumented NPZ source arrays, trace NPZ files, and TrafficTwin canonical records.
- Integration discovery documents:
  - `docs/integration/randy_artifact_inventory.md`
  - `docs/integration/randy_schema_mapping.md`
  - `docs/integration/randy_execution_contract.md`
  - `docs/integration/randy_gap_analysis.md`
  - `docs/integration/phase6_decision.md`
- Capability decision:
  - `direct_launch=false`
  - `asynchronous_launch=false`
  - source controls are documented separately, while the read-only adapter keeps them disabled
- Read-only `traffictwin.integration.tos` package:
  - versioned source models and stable run/experiment identifiers;
  - safe evaluation CSV, JSON, and NPZ header readers;
  - complete package validation and instrumented-summary reconciliation;
  - source-summary MetricCollections with a separate implementation version;
  - partial EvidencePacks consumed by the unchanged R0-R3 engine;
  - idempotent SQLite registration of experiments, runs, metrics, and evidence;
  - bounded historical replay joined by timestamp and time-local vehicle slot;
  - confirmed simulation-second, network-metre, and m/s replay units;
  - bounded per-task showcase inspection with joined actions and `deadline_met` semantics;
  - confirmed RSU in-flight task count, compute backlog, concurrency capacity, and pressure
    inspection without relabelling them as canonical utilisation/queue metrics;
  - versioned machine-readable `vec_env` source contract and CLI output;
  - aggregate metric/rule provenance to exact evaluation CSV rows;
  - `traffictwin integration tos ...` CLI group;
  - Streamlit `TOS Data Import` page.
- Runtime tests generate a synthetic-schema package; no Randy artifact is committed.
- Full canonical conversion remains stopped until physical completion/identity and compatible
  canonical infrastructure evidence, exact producer provenance, and fixture permissions are
  resolved.

## Implemented In Documentation Pass

- Rewritten root README as the project entry point.
- Documentation index.
- System overview.
- Revised architecture document with Mermaid diagrams.
- Developer guide.
- Expanded user guide.
- CLI reference derived from actual commands.
- API reference for principal public interfaces.
- Reproducibility guide.
- Testing strategy.
- Revised demo script and executable demo checklist.
- Viva guide.
- Dissertation mapping.
- Traceability matrix.
- Glossary.
- Limitations and future work.
- Security and privacy.
- ADR index and ten concise ADRs.
- Screenshot manual-capture checklist.
- Generated reference artifacts under `docs/reference/generated/`.
- Cross-links added to data, validation, metrics, evidence, comparison, and diagnostic contract documents.

## Quality Gates

Commands run successfully:

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m pytest --cov=traffictwin --cov-report=term-missing
.venv/bin/python scripts/generate_reference_docs.py
.venv/bin/traffictwin validate-seed examples/seeds/arena_gridlock.yaml
.venv/bin/traffictwin normalise-seed examples/seeds/arena_gridlock.yaml build/traffictwin_arena_gridlock.normalised.yaml
.venv/bin/traffictwin capabilities
.venv/bin/traffictwin registry init build/traffictwin_phase1_registry.sqlite
.venv/bin/traffictwin registry inspect build/traffictwin_phase1_registry.sqlite
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin bundle validate <baseline.zip>
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/partial_valid
.venv/bin/traffictwin bundle validate tests/fixtures/bundles/invalid_manifest
.venv/bin/traffictwin bundle import tests/fixtures/bundles/baseline_valid --registry <tmp-registry>
.venv/bin/traffictwin bundle report tests/fixtures/bundles/partial_valid --format json
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/variation_valid
.venv/bin/traffictwin metrics compute tests/fixtures/bundles/partial_valid
.venv/bin/traffictwin metrics report <baseline.zip> --format json
.venv/bin/traffictwin compare tests/fixtures/bundles/baseline_valid tests/fixtures/bundles/variation_valid
.venv/bin/traffictwin evidence build tests/fixtures/bundles/baseline_valid --output <tmp-evidence>
.venv/bin/traffictwin experiment summarise --registry <tmp-registry> --experiment-id exp-gridlock-001
.venv/bin/traffictwin diagnose bundle tests/fixtures/bundles/baseline_valid
.venv/bin/traffictwin diagnose bundle tests/fixtures/bundles/invalid_rows
.venv/bin/traffictwin diagnose evidence <tmp-evidence>
.venv/bin/traffictwin diagnose report tests/fixtures/bundles/baseline_valid --format json
.venv/bin/traffictwin diagnose evaluate tests/fixtures/diagnostics/cases.json
.venv/bin/traffictwin provenance metric tests/fixtures/bundles/baseline_valid task.completion.rate
.venv/bin/traffictwin provenance rule tests/fixtures/bundles/variation_valid R2
.venv/bin/traffictwin provenance source tests/fixtures/bundles/baseline_valid tasks.csv 2
.venv/bin/traffictwin provenance export tests/fixtures/bundles/baseline_valid --root-type metric --root-id task.completion.rate --format json
streamlit run src/traffictwin/ui/app.py --server.headless true --server.port <tmp-port>
http://127.0.0.1:<tmp-port>/_stcore/health
find <workspace-root> ... <artifact discovery searches>
```

Results:

- Ruff format: clean after formatting.
- Ruff check: all checks passed.
- mypy: no issues found.
- pytest after Phase 4: 85 passed.
- pytest after Phase 5: 119 passed.
- coverage after Phase 4: 71%.
- coverage after Phase 5: 76%.
- CLI seed validation: passed.
- CLI seed normalisation: passed.
- CLI capability manifest: direct and asynchronous launch are `false`; unconfirmed Randy controls are `unknown`.
- Registry smoke: registry created by one process and inspected by another.
- Bundle CLI smoke: valid directory, valid ZIP, partial bundle, rejected bundle, idempotent import, and JSON report passed.
- Metrics CLI smoke: baseline, variation, partial, ZIP report, and rejected-manifest failure passed.
- Comparison CLI smoke: baseline versus variation bundle comparison passed.
- Evidence CLI smoke: evidence-pack JSON generation passed.
- Diagnostic CLI smoke: baseline, R1 fixture, R2 fixture, R3 fixture, mixed fault, insufficient evidence, saved EvidencePack, and rejected bundle behavior passed.
- Fault-injection evaluation: precision/recall returned without `NaN` or infinity.
- Original Phase 6A discovery: no real Randy/VEC or SUMO artifacts were present before Randy's GitLab package was cloned.
- Updated Phase 6 discovery: `external/tos-data` contains real Randy/VEC result artifacts. The
  conservative read-only integration is covered by generated synthetic-schema tests; real fixture
  permission is still required before committing a source-derived sample.
- Updated Phase 6A documentation validation: Ruff format check passed; Ruff check passed; mypy passed; 168 tests passed; coverage remained 77%.
- Documentation pass quality gates: Ruff format/check passed; mypy passed; generated reference JSON regenerated and parsed; Markdown links checked; API imports checked; fixture paths checked; Mermaid fences checked; unsupported-claim scan completed; 119 tests passed; coverage remained 76%; synthetic CLI demo flow passed; Streamlit health check returned `200 ok`.
- Provenance Explorer quality gates: Ruff format/check passed; mypy passed; 147 tests passed; coverage reached 77%; generated reference JSON regenerated; Markdown links checked; provenance CLI metric/rule/source/export smoke checks passed; Streamlit AppTest rendered the Provenance Explorer; Streamlit headless server started; exported provenance JSON contained no absolute local paths; provenance Markdown contained no causal-proof wording.
- Experiment summary CLI smoke: registry-backed summary over stored metric collections passed.
- Streamlit smoke: headless server started and health endpoint responded.
- Streamlit AppTest: Home and all core pages rendered with synthetic defaults without uncaught exceptions.
- JSON finite check: metric JSON contained no `NaN` or infinity.
- Fixture raw-file hashes were unchanged after validation/import smoke checks.

## Blocked

- Full canonical VEC/SUMO adapters are blocked by absent physical-completion, persistent-identity,
  per-vehicle tier/target/link evidence, raw SUMO/trip data, and sanitised fixture permission.
- Direct launch is blocked by missing checkpoints/instrumented writer, source-specific paths, and
  an unverified local runtime despite the discovered evaluator CLI.
- Live or near-live modes are blocked until real feed details exist.
- Metrics using energy, drop causes, queue-clearance time, or capacity-normalised load remain blocked until source fields and units exist.

## Not Started

- External SUMO/VEC/sensor adapters.
- LLM rendering.
- XAI.

## Evidence Required Next

- Definitions for `rsu_busy_ms`, `rsu_load`, and `rsu_max_concurrent`; confirmed trace units; and
  clarification of eventual completion remain required for canonical conversion.
- Permission to commit a small sanitised real-schema fixture.
- Access to the separate `vec_env` reproduction documentation if direct execution or stronger capability mapping is required.
- Confirmation of supported scenario controls.
- Environment invocation contract, if direct launch is expected.

## Current File Tree Summary

```text
diss/
    AGENTS.md
    README.md
    pyproject.toml
    .gitignore
    docs/
        traffictwin-design-v0_4.md
        implementation-status.md
        open-questions.md
        assumption-register.md
        architecture.md
    examples/
        seeds/
            arena_gridlock.yaml
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
                builder.py
                insufficient.py
                pack.py
            diagnostics/
                __init__.py
                builder.py
                report.py
                serialization.py
            experiments/
                __init__.py
                aggregation.py
                comparison.py
                grouping.py
            ingestion/
                __init__.py
                bundle.py
                canonicalise.py
                hashes.py
                loader.py
                manifest.py
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
            rules/
                __init__.py
                base.py
                catalogue.py
                config.py
                conflicts.py
                engine.py
                evaluation.py
                models.py
                registry.py
                r0_insufficient_evidence.py
                r1_under_offloading.py
                r2_infrastructure_bottleneck.py
                r3_scenario_triviality.py
            validation/
                __init__.py
                codes.py
                findings.py
                files.py
                manifest.py
                reconciliation.py
                report.py
                rows.py
    tests/
        fixtures/
            bundles/
                baseline_valid/
                variation_valid/
                partial_valid/
                invalid_manifest/
                invalid_rows/
            seeds/
                invalid_class_mix.yaml
                invalid_schema_version.yaml
            diagnostics/
                cases.json
        golden/
            test_baseline_bundle.py
            test_validation_reports.py
        integration/
            test_bundle_import.py
            test_zip_import.py
        unit/
            test_bundle_loader.py
            test_capabilities.py
            test_manifest.py
            test_registry.py
            test_scenario.py
            test_seed_io.py
```

## Dependency Decisions

Runtime dependencies used in Phase 1:

- `pydantic>=2`: strict schemas and validation.
- `PyYAML>=6`: seed YAML load/dump.
- `typer>=0.12`: minimal CLI.

Development dependencies:

- `pytest`
- `pytest-cov`
- `ruff`
- `mypy`
- `types-PyYAML`

Runtime dependencies added in Phase 4:

- `streamlit`
- `plotly`

Deferred:

- `pandas`, `polars`, `duckdb`: wait until data-size evidence. Streamlit installs pandas and pyarrow transitively, but TrafficTwin code does not import them directly.
- `pre-commit`: practical later, not required for Phase 1.
- ORM: avoided; Phase 1 uses standard library `sqlite3`.

## Phase 6 Outcome And Next Gate

Phase 6 inspected the supplied TOS results and `vec_env` source, then implemented the safe
read-only boundary. The next external increment requires:

1. exact producer commit and instrumented writer;
2. one approved checkpoint and small expected output;
3. permission for a sanitised matched fixture;
4. any additional physical-completion, identity, target/link, and raw trip/SUMO evidence;
5. a path-independent evaluator smoke run before any launcher decision.

Until then, canonical conversion and direct launch remain stopped. LLM rendering, XAI, portfolio
selection, and training orchestration remain outside this integration boundary.

## Implemented In Standalone Product Phase

- `SyntheticScenarioConfig` and documented synthetic policy profiles.
- Deterministic generated bundles for baseline, stressed demand, under-offloading,
  infrastructure bottleneck, mixed fault, partial evidence, and trivial multi-algorithm cases.
- `traffictwin synthetic presets`, `synthetic generate-preset`,
  `synthetic experiment-generate-preset`, and `synthetic verify`.
- `traffictwin demo initialise`, `demo reset`, `demo status`, and `demo launch`.
- Reproducible demo workspace with SQLite registry, generated seeds, bundles, exports, reports,
  logs, and manifest.
- Multi-seed low-pressure experiment evidence for the existing R3 rule.
- Deterministic report export commands for run, comparison, diagnostics, and full reports.
- Streamlit Home standalone demo status section.
- Release metadata helper, changelog, release guide, and GitHub Actions CI workflow.

## Implemented In Product Polish & Research UX

- `Scenario Builder` page over `SyntheticScenarioConfig`.
- Improved replay controls: play, pause, resume, restart, timestamp jump, scrubber, speed presets,
  step controls, and deterministic filters.
- `Experiment Manager` page over registry/workspace metadata.
- `Reports` page for deterministic report inventory, downloads, and explicit regeneration.
- `Search` page for local metadata search.
- `Settings` page for session-scoped preferences.
- `About` page for version, schema, metric, diagnostic, provenance, Python, commit, and licence
  metadata.
- Shared section headers, report cards, metadata cards, status badges, and lightweight UI theme.
- Homepage dashboard improvements for workspace, reports, comparisons, provenance exports, quick
  actions, and recent artifacts.
- Quality gates: Ruff format/check passed; mypy passed; 168 tests passed; coverage 77%; demo
  workspace smoke passed; comparison/report/provenance smoke checks passed; Streamlit health check
  returned `ok`; package build passed.

## Standalone Product Remaining Limits

- Synthetic generation is not calibrated simulation.
- Synthetic policy profiles are not real trained algorithms.
- Registry-run report shortcuts are not the primary report path; bundle paths are supported first.
- Read-only TOS result inspection is available with source-evidenced units and RSU meanings; full
  canonical conversion and SUMO integration remain blocked by missing canonical outcome/identity
  evidence, raw outputs, producer/runtime artifacts, and sanitised fixture permission.
- Direct launch, near-live, and true-live support remain unavailable.

## Implemented In Read-Only TOS Integration Increment

- Optional `tos` dependency extra for bounded NumPy archive inspection.
- Strict evaluation-master parsing, supported-engine gating, package inventory, Git commit, and
  deterministic package fingerprint.
- Deep per-step, per-task, and trace NPZ key/shape validation plus JSON-summary reconciliation.
- Source-summary MetricCollections with a distinct implementation version and explicit unavailable
  results for unsupported canonical metrics.
- Partial EvidencePacks evaluated by the unchanged R0-R3 rules.
- Idempotent SQLite registration of 10 source experiment groups and 300 source runs in the supplied
  package, without storing canonical rows or absolute source paths.
- Unit-aware historical replay, time-indexed recycled vehicle slots, confirmed source-specific RSU
  pressure/backlog views, and bounded per-arrival task/action samples.
- Aggregate metric/rule provenance to exact evaluation CSV rows, package commit/fingerprint, run,
  experiment grouping, actor, and engine version.
- Versioned `tos_source_contract()`, `contract`/`rsu-series` CLI commands, and updated Streamlit
  `TOS Data Import` page.
- Quality gates: Ruff format/check passed; mypy passed; 185 tests passed; coverage 78%. External
  package validation, idempotent 300-run import, CLI, unit-aware replay, task/action and RSU-state
  inspection, diagnostics, provenance, AppTest, generated references, and source immutability
  checks passed.

## Implemented In TOS Results Workbench Increment

- Stable source-analysis catalogue for deadline success by class, all-arrival latency, per-arrival
  energy, decision shares, and offload share.
- Campaign/cell/fleet evaluation matrices with deterministic descriptive statistics.
- Exact baseline/variation pairing by common fleet seed with compatibility and unmatched-seed
  findings.
- Conservative in-domain/held-out/unknown matrix sourced from package documentation.
- Bounded training-history reader with unavailable warm-up handling and separate greedy summaries.
- Processed-FCD trace profiles, exact source RSU pressure/backlog summaries, and exact full-showcase
  task outcome aggregation.
- Reproducibility audit for package coverage, actor/training matching, and blocked producer assets.
- Deterministic imported-simulation report, JSON research pack, and self-contained aggregate atlas.
- Focused Streamlit pages: `TOS Results`, `TOS Mobility & RSU Replay`, and `TOS Training & Audit`.
- Twelve new/extended TOS CLI smoke workflows and generated reference documentation.
- Quality gates: Ruff format/check passed; strict mypy passed; 197 tests passed; coverage 78%.
  Real-package matrix, comparison, training, replay, task, RSU, audit, report, atlas, path-safety,
  JSON-finiteness, UI AppTest, and source immutability checks passed.

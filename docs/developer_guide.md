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

To develop or inspect the optional external TOS Data result reader:

```bash
python -m pip install -e ".[dev,tos]"
```

For the committed dependency graph:

```bash
uv sync --extra dev --extra tos
uv lock --check
```

Runtime dependencies are declared in [pyproject.toml](../pyproject.toml):

- Pydantic v2
- PyYAML
- Typer
- Streamlit
- Plotly
- NumPy only in the optional `tos` extra, for bounded NPZ inspection

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
├── adapters/      # raw-source boundaries; generic declared tabular adapter
├── canonical/     # in-memory canonical record models
├── config/        # seed IO and capability manifests
├── diagnostics/   # reports, temporal orchestration, sensitivity, and cross-rule reasoning
├── domain/        # ScenarioSeed, Experiment, Run, enums
├── evidence/      # Evidence availability and EvidencePack builder
├── experiments/   # protocols, deterministic studies, rankings, gates, power, and parameter sweeps
├── ingestion/     # loader, manifest/inference, ordinary/batch/streaming canonicalisation, hashes
├── integration/   # evidenced source-specific boundaries, readiness gates, private TOS packs
├── metrics/       # metric definitions, calculators, comparison, aggregation
├── provenance/    # trace DAG, source rows, ledgers, PRO-01 differences, PRO-02 graph exports
├── reporting/     # typed reports, research exports, annotations, and structured report diffs
├── rules/         # deterministic R0-R8 and closed declarative-rule compiler
├── release/       # synthetic static deployment and release metadata
├── storage/       # SQLite registry
├── ui/            # Streamlit app, services, components, pages
└── validation/    # validation codes, findings, reports, reconciliation
```

## Extending Manifest Inference

`ingestion/manifest_inference.py` owns the versioned `ING-02` catalogue. When adding an alias,
distinctive value vocabulary, file kind, or unit suffix:

1. confirm it maps an existing evidenced generic CSV semantic rather than a source-specific guess;
2. update the inference version and machine-readable contract when behavior changes;
3. retain the published bounds and non-executable draft state;
4. add a positive golden projection and an ambiguity/rejection case;
5. verify confirmation fingerprints still reconcile with embedded `BundleManifest.files`;
6. update ADR-012 and the manifest-inference guide.

Never add a numeric-range unit heuristic or let the adapter consume `ManifestInferenceDraft`
directly.

## Extending Streaming Ingestion

Keep new declared formats behind `iter_declared_table_chunks` and preserve the ordinary scalar
mapping, logical source-row order, exact raw fingerprint, and stable findings. Any global check
must remain exact and disk-backed or have a separately reviewed bounded contract. Add
ordinary-versus-streaming equivalence at multiple chunk sizes and publish runtime/memory method
before changing defaults. Consumers are synchronous and provisional until final validation;
consumer failures must propagate as `StreamingConsumerError`, not become source findings. See
[ADR-015](decisions/ADR-015-memory-bounded-streaming-canonicalisation.md).

## Extending Parameter Sweeps

`experiments/parameter_sweep.py` owns the EXP-01 closed paths, complete-grid bounds, fingerprints,
mode separation, and response policy. Add a path only when the strict base model can validate it
independently; coupled mix/list/placement/failure semantics need a dedicated operator rather than
a dotted-field shortcut. Never infer an external command or change `not_executed` to an execution
claim. Reuse the ordinary synthetic generator, bundle validator, and metric engine, then update
ADR-036, the public contract, generated schemas/help, positive golden projection, and rejection/
immutability/source-capability tests.

## Extending Scenario Mutations

`experiments/scenario_mutation.py` owns EXP-02 admission, operator semantics, bounds, fingerprints,
exact ledgers, validation, and transactional publication. New operators must be discriminated
request models with deterministic, validity-preserving behavior over an explicit table contract.
Do not add arbitrary field paths, process-global randomness, silent ledger truncation, inferred
routing, or mutation of imported/raw evidence. Encoding support requires a separately documented
byte/logical-identity contract.

Reuse ordinary manifest parsing and bundle validation. Update ADR-037, the public/generated
contract, capabilities, CLI/UI services, example, and positive/rejection/immutability/golden tests.
Any multi-step experiment must chain separately materialised parent-linked results so each operator
remains independently auditable.

## Extending Measurement Imperfections

`domain/measurement.py` owns the strict EXP-03 public config/audit/contract and semantic
reconciliation; `synthetic/measurement.py` owns row copying, exact dropout, and bounded field
application. Keep the layer generated-observation-only and do not route imported bundles through
it. A new field requires an explicit unit, numeric bound, clamp policy, independent stable hash
input, stream-admission rule, semantic audit expectation, generated schema/contract update, and
bound/determinism/axis/outcome/tamper/golden tests.

A different distribution, correlation/drift model, all-row dropout, outcome/timestamp change, or
empirical calibration claim requires a new versioned decision rather than a hidden extension of
`bounded_uniform` v1.0. Update ADR-038, capabilities, CLI/UI, usage/limitations/reproducibility
records, generated references, and external-source denials together.

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

For a product-owned core metric, use the following process:

1. Add a `MetricDefinition` in [metrics/catalogue.py](../src/traffictwin/metrics/catalogue.py).
2. Implement the calculator in the correct domain module.
3. Return explicit unavailable or invalid results when evidence is missing.
4. Keep output ordering deterministic.
5. Add unit tests, fixture tests, and golden expected output if fixture data supports the metric.
6. Update [metrics_catalogue.md](metrics_catalogue.md), [evidence_pack_spec.md](evidence_pack_spec.md), and generated references.

Do not compute from raw CSV files. Metrics consume canonical records and evidence availability only.

For a local research extension that does not belong in the core catalogue, use the explicit
`MetricPluginRegistry` described in [Custom metric plugins](custom_metric_plugins.md). Declare the
complete canonical input/availability/output/provenance contract, use a `plugin.<plugin_id>.*` key,
keep the callable side-effect-free, and add determinism, failure-isolation, output-schema, window,
comparison, and provenance tests. Never add a file-upload or arbitrary-module loader for plugin
code; v1.0 is reviewed trusted in-process Python and is not sandboxed.

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

Nearest-flip support is not automatic for a new rule. It requires an ADR establishing one
admissible monotonic configuration axis, its unit/distance, inclusive or strict boundary behavior,
unchanged discrete constraints, ties, and ordinary-engine verification. Do not add a rule to
`SUPPORTED_NEAREST_FLIP_RULE_IDS` merely because it has numeric config fields.

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

For a new PRO-01 arithmetic metric, add the key and human-readable formula to the closed registry
in `provenance/differences.py`, implement its accepted-row term, and add reconciliation tests proving
that both run sums reproduce the ordinary metric values and signed delta. Never infer weights for
percentiles, grouped outputs, or plugins from their input ledger alone; leave them lineage-only or
unavailable and update ADR-033 through a versioned decision.

For graph work, extend the existing `ProvenanceTrace` builder first. Do not derive lineage in DOT,
GraphML, or Streamlit. `provenance/graph_export.py` owns stable exported IDs, root-centred bounds,
path redaction, disclosure profiles, and serialization. New graph data needs parser tests, golden
output, path-injection tests, and explicit hard bounds.

For PRO-03, never parse report prose. Add or change report claims only through
`reporting/claims.py`, keep the renderer and query on the same ordered typed references, and retain
unavailable results in the denominator. A new `source_row_complete` route requires a non-empty
complete accepted-row ledger plus valid locators; a sampled trace row is insufficient. Add exact
denominator/classification, null, fingerprint, CSV, golden, CLI, and UI-service tests, and update
ADR-035 if the denominator or weighting policy changes.

For REP-01, add scientific content only to the source metric/comparison/study/rule artifact. Keep
`reporting/latex.py` renderer-only. A new artifact family needs a typed projector, stable ordering,
source-mode handling, published bounds, escaping/path tests, exact golden output, CLI/UI coverage,
and a versioned contract/ADR change. The `.tex` and optional figure must continue to derive from
the same `ResearchExportProjection`; never convert rule confidence to probability or bar direction
to favourability.

For REP-02, keep authored commentary in `traffictwin.annotations` and the registry annotation
table. Do not add it to a metric, EvidencePack, DiagnosticReport, computed report section, claim
reference, or provenance fingerprint. Add new target/decision kinds only through a versioned
contract/ADR change. Preserve monotonic history, database update/delete guards, pagination, exact
target matching, complete-or-refuse report attachment, output escaping, CLI/UI tests, and a golden
history. Corrections are new annotations, never updates.

For REP-03, add scientific values to `ReportClaimSnapshot` only by projecting an existing typed
metric, rule, or comparison artifact. Never parse a section body or rendered output. Preserve the
reference/snapshot one-to-one inventory, report-independent scientific keys, strict source/type/
denominator compatibility, canonical JSON bounds, unavailable behavior, and the exclusion of
identity, timestamps, prose, warnings, commands, labels, and annotations. A new report or claim
kind requires contract, ADR, schema, golden, CLI, UI-service, and compatibility tests.

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
and `Search` may scan local metadata. `Experiment Planner` may validate and persist the existing
`Experiment` model. `experiments.protocol` may derive deterministic run slots, seed fingerprints,
exports, and manifest matches, but must not create `Run` records or launch work. These pages must not add
metrics, diagnostic rules, adapters, live data, or launch behavior.

Protocol changes must preserve exhaustive ordering and backward compatibility. Never truncate a
run sheet silently, infer an external checkpoint, or treat suggested identifiers as execution
evidence. Add exact, compatible, mismatch, and unmatched tests when changing matching fields.

## Adding An Adapter Safely

1. Complete discovery first: source files, schemas, units, identifiers, row counts, provenance, and execution commands.
2. Document the mapping under `docs/integration/` and record its versioned decision.
3. Create sanitised real-schema fixtures if permitted.
4. Implement a source-specific read-only validator outside `generic_csv`.
5. Implement the OPS-05 `ExternalSourceAdapter` protocol with exact safe markers, field semantics,
   complete capability truth, provenance requirements, conversion outputs, blockers, and limits.
6. Preserve source file/row provenance and reject ambiguous units, identities, joins, and rights.
7. Produce only the source-specific, aggregate, or canonical outputs supported by evidence; never
   force a complete generic bundle.
8. Add non-mutation, path/symlink, no-match/ambiguity, deterministic inspection, golden, CLI, and
   source-validator reconciliation tests.
9. Update the closed registry, generated contract, architecture, assumption/open-question records,
   security, limitations, traceability, and implementation status.

The read-only `integration.tos` boundary is implemented for the evidenced evaluation-summary and
instrumented-array contracts. It must remain separate from `generic_csv`. A full canonical
Randy/VEC adapter remains blocked by absent eventual-completion and persistent-identity fields,
compatible canonical infrastructure evidence, trip/raw SUMO outputs, exact producer provenance,
fixture permission, and a verified runnable package. The separate `integration.sumo` boundary
implements the evidenced public SUMO 1.27 tripinfo/summary contract only; extend it through
ADR-011's version, semantics, licence, immutable-fixture, and test gates.

The closed OPS-05 registry is in `integration/external/`. Do not add dynamic entry points, uploaded
adapter code, heuristic marker scores, or automatic tie-breaking. A conversion label describes
produced artifacts and is not a maturity or trust score. See the
[general external-source contract](integration/external_source_contract.md).

TOS integration tests use generated schema-compatible NPZ/CSV/JSON samples. Do not copy Randy's raw
package into this repository without explicit sanitised-fixture permission. Confirmed
`rsu_load`/`rsu_busy_ms`/`rsu_max_concurrent` meanings are exposed only through source-specific
models. Any future promotion to canonical metrics requires a deliberate metric/data-contract
decision and new tests; do not reinterpret them in UI code.

### Extending The TOS Results Workbench

Keep source-specific descriptive analysis in `src/traffictwin/integration/tos/`; do not add it to
the canonical Phase 3 metric catalogue unless a standard canonical mapping is later evidenced.

- Register source measures once in `analysis.py`.
- Pair only exact source keys; report compatibility differences and unmatched seeds.
- Represent non-finite source observations as unavailable rather than JSON NaN.
- Keep UI pages on `ui.services`; do not repeat calculations in Streamlit.
- Inject clocks in report and golden tests.
- Use generated schema-compatible fixtures in `tests/tos_helpers.py`.
- Never expose machine-record contents or absolute external paths in exports.

Regenerate `docs/reference/generated/` after changing a public model or CLI command.

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
| Statistical study is insufficient/incompatible | Fewer than three exact pairs, duplicates, or contract mismatch | Inspect the pairing audit; fix source/plan evidence rather than dropping inconvenient seeds. |
| TOS NPZ command says NumPy is required | Optional `tos` extra is absent | Install `.[dev,tos]`; the core generic-bundle workflow remains NumPy-free. |
| TOS canonical RSU metrics are unavailable | Source semantics do not match canonical utilisation/queue fields | Inspect bounded pressure/backlog state; do not relabel it as utilisation or queue length. |

## Standalone Product Development

Standalone modules are wrappers around the existing pipeline:

- `src/traffictwin/synthetic/` writes standard bundles.
- `src/traffictwin/demo/` prepares a marked workspace and imports bundles through the registry.
- `src/traffictwin/reporting/` renders existing objects into Markdown/HTML/A4 PDF and projects four
  completed artifact families into escaped LaTeX plus deterministic SVG/PDF figures; it also
  compares compatible prose-free typed report claims before rendering.
- `src/traffictwin/release/` stages synthetic-only static deployments and exposes release metadata.
- `src/traffictwin/integration/tos/supervisor.py` creates private checksummed review packs.
- `src/traffictwin/integration/tos/readiness.py` records missing evidence and permissions as gates.

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
- [LaTeX research tables and static figures](latex_research_exports.md)
- [Structured report diffing](structured_report_diffing.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)
- [Provenance model](provenance_model.md)
- [Testing strategy](testing_strategy.md)
- [Reproducibility guide](reproducibility.md)
- [ADR index](decisions/index.md)
- [Common-seed paired statistical studies](statistical_studies.md)
- [Paired common-seed power analysis](power_analysis.md)

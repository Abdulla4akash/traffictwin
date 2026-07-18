# TrafficTwin Architecture

This document describes the implemented Phase 1-6A plus Provenance Explorer architecture. It is grounded in the current repository and the canonical design specification at [docs/traffictwin-design-v0_4.md](traffictwin-design-v0_4.md). It does not assume runnable Randy/VEC, SUMO XML, Manchester sensor, near-live, true-live, or external launch support.

## Architectural Position

TrafficTwin is a tested Python research-software library with a thin Streamlit interface and Typer CLI. The guaranteed workflow is import-first:

```text
seed YAML -> run bundle -> validation -> canonical records -> metrics -> EvidencePack -> diagnostics/provenance/UI
```

Direct launch is an adapter capability, not a default feature.

## A. High-Level Platform Architecture

```mermaid
flowchart TD
    subgraph Interfaces
        CLI[Typer CLI]
        UI[Streamlit UI]
    end

    subgraph CoreLibrary[TrafficTwin library]
        Config[config: seed IO and capabilities]
        Domain[domain: ScenarioSeed, Experiment, Run]
        Ingestion[ingestion: bundle loading and manifest parsing]
        Adapters[adapters: generic CSV boundary]
        Canonical[canonical: in-memory records]
        Validation[validation: findings and reports]
        Metrics[metrics: deterministic metric engine]
        Evidence[evidence: EvidencePack builder]
        Rules[rules: deterministic R0-R3]
        Diagnostics[diagnostics: DiagnosticReport]
        Provenance[provenance: read-only trace DAG]
        Storage[storage: SQLite metadata registry]
    end

    CLI --> CoreLibrary
    UI --> CoreLibrary
    Config --> Domain
    Ingestion --> Adapters
    Adapters --> Canonical
    Ingestion --> Validation
    Canonical --> Metrics
    Validation --> Metrics
    Metrics --> Evidence
    Evidence --> Rules
    Rules --> Diagnostics
    Metrics --> Provenance
    Diagnostics --> Provenance
    Validation --> Provenance
    Ingestion --> Storage
    Metrics --> Storage
    Evidence --> Storage
```

## Layer Responsibilities

| Layer | Modules | Responsibility |
|---|---|---|
| Configuration | `src/traffictwin/config/` | Seed YAML loading/dumping and capability manifests. |
| Domain | `src/traffictwin/domain/` | `ScenarioSeed`, `Experiment`, `Run`, enums, and strict validation. |
| Ingestion | `src/traffictwin/ingestion/` | Bundle loading, manifest parsing, fingerprints, and validation orchestration. |
| Adapters | `src/traffictwin/adapters/` | Raw source interpretation at boundaries. Currently generic CSV only. |
| Canonical | `src/traffictwin/canonical/` | In-memory canonical record models and table container. |
| Validation | `src/traffictwin/validation/` | Stable codes, findings, reports, and reconciliation helpers. |
| Metrics | `src/traffictwin/metrics/` | Deterministic metric definitions, calculators, comparison, and aggregation. |
| Evidence | `src/traffictwin/evidence/` | Versioned EvidencePack construction and data-readiness summaries. |
| Rules | `src/traffictwin/rules/` | Deterministic R0-R3 rule evaluation over EvidencePack only. |
| Diagnostics | `src/traffictwin/diagnostics/` | DiagnosticReport schema and serialisation. |
| Provenance | `src/traffictwin/provenance/` | Read-only trace graph, source-row preview, JSON and Markdown export. |
| Storage | `src/traffictwin/storage/` | SQLite registry for metadata and JSON payload references. |
| UI | `src/traffictwin/ui/` | Streamlit presentation and UI services over library calls. |
| Product UX | `src/traffictwin/ui/pages/` and `src/traffictwin/ui/components/` | Scenario Builder, Experiment Manager, Reports, Search, Settings, About, replay controls, and reusable presentation helpers. |

## Dependency Direction

Dependencies flow inward from interfaces to library modules. Metrics do not read raw files. Rules do not read raw files or canonical rows. Provenance does not recompute metrics or reinterpret rules. The UI does not implement metrics, validation, comparison, diagnostic formulas, or provenance derivation logic.

```mermaid
flowchart LR
    UI[Streamlit pages] --> Services[ui.services]
    CLI[Typer commands] --> Library[Core library]
    Services --> Library
    Library --> Models[Pydantic models]
    Library --> Registry[(SQLite)]
```

## B. Import Pipeline

```mermaid
flowchart TD
    Source[Directory or ZIP bundle] --> Loader[open_bundle]
    Loader --> Manifest[manifest.yaml parsing]
    Manifest --> Seed[seed.yaml validation]
    Manifest --> Files[Declared file checks]
    Files --> CSV[GenericCsvAdapter]
    CSV --> Rows[Row parsing and semantic checks]
    Rows --> Tables[CanonicalTables]
    Tables --> EvidenceAvailability[EvidenceAvailability]
    EvidenceAvailability --> Report[ValidationReport]
    Report --> ImportDecision{may_import?}
    ImportDecision -->|yes or warnings| Registry[(register bundle metadata)]
    ImportDecision -->|no| Reject[Reject and preserve report]
```

Bundle loading supports directories and ZIP files. ZIP extraction rejects absolute paths, path traversal, and symlinks, and works in a controlled temporary directory.

## Canonical Records

Canonical records are Pydantic models in [src/traffictwin/canonical/records.py](../src/traffictwin/canonical/records.py):

- `TaskRecord`
- `InfrastructureRecord`
- `VehicleStateRecord`
- `TrafficObservationRecord`
- `TripRecord`
- `IncidentRecord`

Every record preserves `source_file` and `source_row`. Missing optional source fields remain absent or null. Phase 6A does not store full canonical rows in SQLite.

## Validation

Validation runs before metrics. It produces `ValidationReport`, a serialisable report with:

- status: `accepted`, `accepted_with_warnings`, or `rejected`;
- `may_import`;
- stable validation findings;
- files inspected;
- canonical record counts;
- available and unavailable evidence categories.

Validation continues where safe so a user sees a complete report rather than only the first problem.

## Metrics

Metrics are deterministic functions over `CanonicalTables`, `RunMetricContext`, `EvidenceAvailability`, and `MetricEngineConfig`.

Key properties:

- stable metric definitions;
- no mutation of canonical records;
- unavailable metrics are explicit;
- no `NaN` or infinity in JSON;
- synthetic-demo saturation threshold is configurable and documented.

## C. Evidence And Diagnostics Pipeline

```mermaid
flowchart TD
    Canonical[CanonicalTables] --> MetricEngine[compute_metrics]
    Validation[ValidationReport] --> MetricEngine
    Availability[EvidenceAvailability] --> MetricEngine
    MetricEngine --> Collection[MetricCollection]
    Collection --> EvidencePack[EvidencePack]
    Validation --> EvidencePack
    Availability --> EvidencePack
    EvidencePack --> R0[R0 insufficient evidence]
    EvidencePack --> R1[R1 under-offloading candidate]
    EvidencePack --> R2[R2 infrastructure-bottleneck candidate]
    EvidencePack --> R3[R3 scenario-triviality candidate]
    R0 --> Report[DiagnosticReport]
    R1 --> Report
    R2 --> Report
    R3 --> Report
```

EvidencePack is the only supported input to diagnostic rules. Rules cite metric keys and return candidate hypotheses with alternatives, missing evidence, and conditional recommendations. They do not prove root causes.

## Provenance Pipeline

```mermaid
flowchart TD
    Report[DiagnosticReport] --> RuleResult[RuleResult]
    RuleResult --> Finding[Finding]
    Finding --> EvidenceKey[Evidence key]
    EvidenceKey --> MetricResult[MetricValue]
    MetricResult --> MetricDefinition[MetricDefinition]
    MetricResult --> CanonicalTable[Canonical table]
    CanonicalTable --> CanonicalRecord[Canonical record sample]
    CanonicalRecord --> SourceRow[Source CSV row]
    SourceRow --> SourceFile[Source file]
    CanonicalRecord --> ValidationFinding[Validation finding]
    SourceFile --> Manifest[manifest.yaml]
    Manifest --> Run[Run metadata]
    Run --> Seed[ScenarioSeed]
    Run --> Experiment[Experiment id]
    Run --> Environment[Environment version]
    Manifest --> Fingerprint[Bundle fingerprint]
```

The provenance layer builds a small internal DAG from existing objects:

- `BundleValidationResult`;
- `MetricCollection`;
- `EvidencePack`;
- `DiagnosticReport`;
- metric and rule catalogues;
- canonical record `source_file` and `source_row` fields.

For aggregate metrics, row provenance is reported as eligible input records and bounded source-row samples. The explorer does not assign fabricated per-row contribution weights. EvidencePack-only diagnostic fixtures can trace rule findings to metric keys, but source rows are explicit unavailable links unless the original run bundle is also available.

## Metadata Registry

The registry in [src/traffictwin/storage/registry.py](../src/traffictwin/storage/registry.py) uses SQLite and stores:

- seeds;
- experiments;
- runs;
- bundle import metadata;
- metric collection JSON;
- evidence pack JSON.

It does not store raw files, canonical rows, or private simulator data. Schema changes must be additive unless an explicit migration is designed.

## D. UI, Service, And Library Flow

```mermaid
flowchart TD
    Pages[ui.pages] --> State[ui.state]
    Pages --> Components[ui.components]
    Pages --> Services[ui.services]
    Services --> Bundle[validate_bundle/import_bundle]
    Services --> Metrics[compute_metrics_for_bundle]
    Services --> Evidence[build_evidence_pack]
    Services --> Rules[evaluate_rules]
    Services --> Provenance[build provenance traces]
    Services --> Compare[compare_metric_collections]
    Services --> Registry[Registry]
```

The Streamlit app is launched with:

```bash
streamlit run src/traffictwin/ui/app.py
```

All calculations come from library services. UI modules prepare chart/table data and render unavailable states honestly.

## E. External-Adapter Boundary

```mermaid
flowchart LR
    External[Randy/VEC, SUMO, sensors] --> Adapter[Future evidenced adapter]
    Adapter --> StandardBundle[Standard TrafficTwin run bundle]
    StandardBundle --> ExistingPipeline[Existing validation pipeline]
    ExistingPipeline --> Metrics[Existing metrics]
    Metrics --> Evidence[Existing EvidencePack]
    Evidence --> Diagnostics[Existing diagnostics]
```

Updated Phase 6A discovery found Randy's external `TOS Data` result package under
`external/tos-data`. Those files are real result artifacts, but they are not standard TrafficTwin
run bundles and they do not provide a runnable environment contract. Future adapters must:

- declare supported schemas and units;
- preserve raw sources;
- map only evidenced fields;
- emit validation findings for ambiguous data;
- produce standard TrafficTwin bundles or canonical records through existing validation;
- keep unsupported capabilities `unknown` or `false`.

The generic CSV adapter must not accumulate Randy-specific assumptions.

## Standalone Product Layer

The standalone product layer is intentionally outside the core metric and diagnostic logic:

```mermaid
flowchart TD
    Config[SyntheticScenarioConfig] --> Generator[Synthetic generator]
    Generator --> Bundle[Standard run bundle]
    Bundle --> Phase2[Existing validation and canonicalisation]
    Phase2 --> Phase3[Existing metric and evidence pipeline]
    Phase3 --> Phase5[Existing diagnostic rules]
    Phase3 --> Provenance[Existing Provenance Explorer]
    Phase5 --> Reports[Deterministic reports]
    Provenance --> Reports
    Workspace[Demo workspace] --> Registry[(SQLite registry)]
    Phase2 --> Registry
    Phase3 --> Registry
```

`src/traffictwin/synthetic/` writes ordinary bundles. `src/traffictwin/demo/` prepares a local
workspace and imports those bundles through the same registry path as historical imports.
`src/traffictwin/reporting/` renders existing validation, metric, evidence, diagnostic, comparison,
and provenance objects into Markdown or standalone HTML.

No standalone module introduces Randy/SUMO behavior, live data, new metrics, new rules, or simulator
launch support.

## Security Considerations

- Imported files are read as data, not executed.
- ZIP loading rejects path traversal, absolute paths, and symlinks.
- Raw source fixtures remain unchanged.
- SQLite is local metadata storage, not a credential store.
- Randy's external `TOS Data` package is kept outside `diss/`; raw external files should not be
  copied into this repository until sanitised fixture permission is explicit.
- Future live or user-study data would require a stronger privacy and threat model.

See [security_and_privacy.md](security_and_privacy.md).

## Extension Points

| Extension | Current gate |
|---|---|
| New canonical record | Add model, table field, validation, metrics availability, docs, tests. |
| New manifest field | Add Pydantic field, validation, bundle spec, fixtures, tests. |
| New metric | Add definition, calculator, availability behavior, golden tests, metrics docs. |
| New diagnostic rule | Add EvidencePack inputs, rule config, rule model output, tests, docs. |
| Provenance trace root | Add builder/query support without recomputing metrics or reading unsafe paths. |
| New Streamlit page | Add service-backed page; no duplicated formulas. |

## Product Polish Layer

The Product Polish & Research UX phase adds workflow pages and reusable presentation components
without changing the deterministic pipeline:

```mermaid
flowchart LR
    Pages[Streamlit pages] --> Services[ui.services]
    Components[Reusable UI components] --> Pages
    Services --> Generator[Synthetic generator]
    Services --> Registry[SQLite registry]
    Services --> Reports[Reporting builders]
    Services --> Existing[Validation / metrics / evidence / diagnostics / provenance]
```

Scenario Builder uses `SyntheticScenarioConfig` and `write_synthetic_bundle`; Experiment Manager
uses registry and workspace metadata; Reports calls `traffictwin.reporting`; Search performs local
metadata search. None of these pages implement new metrics, rules, adapters, live data, or launchers.
| Real adapter | Wait for real artifacts, schemas, units, and approval after discovery. |

## Related Documents

- [System overview](system_overview.md)
- [Developer guide](developer_guide.md)
- [Data contract](data_contract.md)
- [Run bundle specification](run_bundle_spec.md)
- [Metrics catalogue](metrics_catalogue.md)
- [Diagnostic rules](diagnostic_rules.md)
- [Provenance Explorer](provenance_explorer.md)
- [Provenance model](provenance_model.md)
- [Standalone demo](standalone_demo.md)
- [Synthetic data model](synthetic_data_model.md)
- [Report export](report_export.md)
- [Integration decision](integration/phase6_decision.md)

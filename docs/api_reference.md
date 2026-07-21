# API Reference

This reference lists the principal public Python interfaces implemented in the current repository. It focuses on stable contracts used by tests, CLI, and UI.

Generated JSON schemas are available at [reference/generated/pydantic_schemas.json](reference/generated/pydantic_schemas.json).

## Domain And Configuration

### `ScenarioSeed`

Import path:

```python
from traffictwin.domain.scenario import ScenarioSeed
```

Role: versioned what-if scenario seed. Important sections include demand, workload, fleet, infrastructure, allowed decisions, policy, evaluation, and provenance.

Limitations: supports schema version `1.0`; rejects unknown fields; does not prove that Randy/SUMO can execute any setting.

### `SeedDocument`

Import path:

```python
from traffictwin.domain.scenario import SeedDocument
```

Role: top-level YAML document wrapper with matching top-level and nested schema versions.

### `Experiment`

Import path:

```python
from traffictwin.domain.experiment import Experiment
```

Role: research comparison metadata: baseline seed, variations, algorithms, common random seeds, planned replicates, status, timestamps.

### `Run`

Import path:

```python
from traffictwin.domain.run import Run
```

Role: one imported/exported/executed run metadata record. Used by registry and bundle import.

### `TaskEnergyContract`

Import path:

```python
from traffictwin.domain.energy import TaskEnergyContract
```

Role: strict v1.0 semantic admission contract for canonical task-energy metrics. It fixes the
quantity as per-task total energy, units as joules, row observation level, three eligibility
policies, and milliseconds for the energy-delay product. `fingerprint()` returns the
stable compatibility identifier used by metrics and comparisons.

### `OperationalFairnessPolicy`

Import path:

```python
from traffictwin.domain.fairness import OperationalFairnessPolicy
```

Role: strict v1.0 admission and interpretation policy for the operational vehicle-tier and RSU
fairness family. It fixes exact grouping, minimum group count/support, complete coverage, and the
non-protected attribute boundary. `fingerprint()` is recorded on results and required, with the
exact group-set fingerprint, for compatible scalar comparisons.

### `TaskRsuTargetContract` And `VehicleSpatialGridContract`

Import path:

```python
from traffictwin.domain.spatial import TaskRsuTargetContract, VehicleSpatialGridContract
```

Role: independent strict v1.0 admission contracts for `MET-05`. The first fixes V2I target meaning,
exact canonical RSU joins, complete target coverage, and non-causal interpretation. The second
fixes vehicle position semantics, source-frame identity, metre units, origin/cell geometry, floor
assignment, and complete coordinate coverage. Each exposes `fingerprint()` for metric provenance.

### `CapabilityManifest`

Import path:

```python
from traffictwin.config.capabilities import CapabilityManifest, default_export_import_manifest
```

Role: describes adapter capabilities with `true`, `false`, or `unknown`. The default manifest uses
adapter `generic_csv`, declares streaming canonicalisation and time-windowed metrics `true`, keeps
`direct_launch=false`, and leaves unconfirmed external controls `unknown`.

## Read-only Environment Doctor

Import path:

```python
from traffictwin.doctor import doctor_contract, doctor_report_to_text, run_doctor
```

- `doctor_contract() -> DoctorContract`
- `run_doctor(workspace=None, registry=None, bundle=None, cache_root=None) -> DoctorReport`
- `doctor_report_to_text(report) -> str`

`DoctorReport` contains strict `DoctorCheck`, `DoctorDependency`,
`DoctorCapabilitySummary`, `DoctorWorkspaceDiagnosis`, `DoctorRegistryDiagnosis`, OPS-01 migration
status, and optional OPS-02 cache status records. `fingerprint()` binds the complete observed
environment report. Overall `healthy`, `degraded`, or `blocked` uses only checks required by the
selected invocation.

The service is always read-only. It does not install packages, run external commands, initialise
or migrate registries, create or repair caches/workspaces, change permissions, launch simulators,
or compute scientific results. See [TrafficTwin doctor](doctor.md).

## RO-Crate Research Objects

Import path:

```python
from traffictwin.research_object import (
    ResearchObjectRequest,
    build_research_object,
    create_research_object_archive,
    research_object_contract,
    verify_research_object,
    verify_research_object_bytes,
)
```

- `research_object_contract() -> ResearchObjectContract`
- `build_research_object(bundle, request) -> BuiltResearchObject`
- `create_research_object_archive(bundle, destination, request, overwrite=False) -> ResearchObjectArchiveReceipt`
- `verify_research_object(path) -> ResearchObjectVerification`
- `verify_research_object_bytes(payload) -> ResearchObjectVerification`

`ResearchObjectRequest` owns publication date/scope, authors, raw disposition and permission,
licence statements, and optional identifier. The manifest reconciles every embedded/referenced/
excluded raw item with source/software/method fingerprints. Creation verifies the deterministic
archive before atomic publication; verification is bounded and read-only. See
[RO-Crate research objects](research_objects.md).

## General External-source Contract

Import path:

```python
from traffictwin.integration.external import (
    ExternalSourceAdapter,
    discover_external_sources,
    external_source_adapters,
    external_source_catalogue,
    inspect_external_source,
)
```

- `external_source_adapters() -> tuple[ExternalSourceAdapter, ...]`
- `external_source_catalogue() -> ExternalSourceCatalogue`
- `discover_external_sources(path) -> ExternalDiscoveryReport`
- `inspect_external_source(path, adapter_id=None, deep=False) -> ExternalSourceInspection`

`ExternalSourceAdapter` is runtime-checkable and defines `discover`, `contract`, `validate`, and
`inspect`. The v1 registry is closed to `sumo_results_v1` and `tos_data_read_only` and performs no
dynamic module loading. `ExternalAdapterContract` binds exact safe markers, field semantics,
complete capability truth, provenance requirements, a non-ordinal conversion profile, typed
blockers, and interpretation limits.

Discovery returns one match, no match, ambiguity, or blocked state. Inspection calls the existing
source-specific validator and emits a deterministic path-free portable summary without source,
registry, or simulator mutation. SUMO exposes partial canonical trips; TOS exposes aggregate
summary/source-specific artifacts with no canonical-row claim. See the
[general external-source contract](integration/external_source_contract.md).

## Seed IO

```python
from traffictwin.config.seed_io import load_seed, dump_seed, normalise_seed_file
```

- `load_seed(path) -> ScenarioSeed`
- `dump_seed(seed) -> str`
- `normalise_seed_file(source, destination) -> SeedDocument`

Errors: wraps invalid YAML/Pydantic errors in `SeedIOError`.

## Registry

Import path:

```python
from traffictwin.storage.registry import Registry
```

Role: SQLite-backed metadata registry.

Important methods:

- `initialize()`
- `add_seed(seed)` / `get_seed(seed_id)`
- `list_seeds()`
- `add_experiment(experiment)` / `get_experiment(experiment_id)`
- `list_experiments()`
- `update_experiment_status(experiment_id, new_status)`
- `add_run(run)` / `get_run(run_id)`
- `list_runs()`
- `update_run_status(run_id, new_status)`
- `register_bundle_import(...)`
- `store_metric_collection(...)`
- `get_metric_collection_json(run_id)`
- `store_evidence_pack(...)`
- `inspect()`

Errors:

- `DuplicateIdentifierError`
- `RegistryNotFoundError`
- `InvalidStatusTransitionError`
- `RegistryConflictError`

## Experiment Planning

```python
from traffictwin.experiments import summarise_experiment_plan
```

`summarise_experiment_plan(experiment, registered_seeds, preview_limit=200)` validates registered
seed references, baseline/variation separation, policy labels, common random seeds, and replicate
count. It returns an `ExperimentPlanSummary` containing deterministic design counts, a bounded
`ExperimentPlanCell` preview, seed-parameter differences, and warnings.

The function is side-effect free. It does not create `Run` records, execute a policy, or launch a
simulator. Persist the validated `Experiment` separately through `Registry.add_experiment`.

### Parameter Sweep Composer

```python
from traffictwin.experiments import (
    ParameterSweepMode,
    ParameterSweepRequest,
    SweepAxis,
    SweepParameter,
    execute_parameter_sweep,
    expand_parameter_sweep,
    parameter_sweep_contract,
    parameter_sweep_response_to_csv,
)
```

`ParameterSweepRequest` declares one strict `SyntheticScenarioConfig` or `ScenarioSeed`, one to
four closed scalar axes, one of three materialisation modes, and local core response metrics when
applicable. `expand_parameter_sweep(request)` validates and returns the complete deterministic grid
without filesystem writes. `execute_parameter_sweep(request, output_dir, overwrite=False)` writes
the transactional seed/bundle/request artifacts and typed `ParameterSweepResult`; it rejects
empty, symbolic-link, current/home/root, and current/home ancestor destinations before expansion.

Only `local_synthetic_bundles` executes anything: the existing labelled synthetic generator,
ordinary bundle validator, and ordinary metric engine. `external_run_requests` always records
`not_executed`, false direct-launch support, and no launcher/command. See
[Parameter sweep composer](parameter_sweeps.md) for the bounds and exact path catalogue.

### Scenario Mutation Operators

```python
from traffictwin.experiments import (
    RowDropoutMutation,
    RsuRemovalMutation,
    ScenarioMutationRequest,
    TimestampJitterMutation,
    execute_scenario_mutation,
    plan_scenario_mutation,
    scenario_mutation_contract,
)
```

`ScenarioMutationRequest` declares exactly one closed operator. `plan_scenario_mutation(...)`
performs complete source admission and returns a fingerprinted exact change plan without writing.
`execute_scenario_mutation(..., output_dir, overwrite=False)` copies the source transactionally,
applies the plan, validates the derived bundle through the ordinary ingestion boundary, verifies
the planned fingerprint, and publishes the typed result and manifest.

Only ordinarily valid bundles explicitly labelled synthetic/evaluation are admitted. Mutation
targets are declared uncompressed CSV tables; non-target files remain byte-identical. The result
retains every admitted row/file change, states that the raw source was unchanged, and records that
no external launch occurred. See [scenario mutation operators](scenario_mutations.md).

### Synthetic Measurement Imperfections

```python
from traffictwin.domain.measurement import (
    MeasurementTableKind,
    SyntheticMeasurementImpairmentAudit,
    SyntheticMeasurementImpairmentConfig,
    measurement_impairment_contract,
)
from traffictwin.synthetic import load_synthetic_scenario_config
from traffictwin.synthetic.bundles import write_synthetic_bundle
from traffictwin.synthetic.generator import generate_run_data
```

`SyntheticMeasurementImpairmentConfig` is the strict EXP-03 input embedded optionally in
`SyntheticScenarioConfig`. `generate_run_data(...)` applies the model only after clean rows exist
and exposes `measurement_impairment_audit`; `write_synthetic_bundle(...)` embeds that audit and
publishes transactionally. `measurement_impairment_contract()` exposes the closed fields, bounds,
dropout tables, clamps, and limitations. See
[Synthetic measurement noise and dropout](measurement_imperfections.md).

### Experiment Protocol

```python
from traffictwin.experiments import (
    ExperimentProtocol,
    ProtocolBundleMatch,
    build_experiment_protocol,
    match_bundle_manifest,
    protocol_to_csv,
    protocol_to_yaml,
)
```

`build_experiment_protocol(experiment, registered_seeds, max_slots=10000, clock=None)` validates
the plan and returns an exhaustive `ExperimentProtocol`. The protocol embeds seed snapshots,
fingerprints, deterministic slot identifiers, suggested run/bundle identifiers, checkpoint
requirements, warnings, and limitations. It raises `ValueError` rather than returning a truncated
run sheet.

`protocol_to_yaml(protocol)` returns the versioned protocol document. `protocol_to_csv(protocol)`
returns one row per planned slot in stable order.

`match_bundle_manifest(protocol, manifest) -> ProtocolBundleMatch` compares an already validated
`BundleManifest` with the protocol. Status is `exact`, `compatible`, `mismatch`, or `unmatched`.
It does not validate files, import the bundle, create a run, or establish scientific validity; call
`validate_bundle` first.

See [Experiment protocol export](experiment_protocol.md) for identifier and checkpoint semantics.

## Experiment Research Analysis

```python
from traffictwin.experiments import (
    ExperimentEvidenceOptions,
    PairedMetricEndpoint,
    PortfolioStudyReport,
    ProtocolTracker,
    TrainingValidationObservation,
    build_experiment_evidence_pack,
    build_winner_map,
    default_synthetic_portfolio_rules,
    evaluate_portfolio,
    evaluate_portfolio_study,
    select_portfolio_policy,
    training_validation_observation_from_collections,
)
```

`build_experiment_evidence_pack` aggregates stored run-level metric collections and includes
training-validation gaps only for explicit `TrainingValidationObservation` pairs.
`training_validation_observation_from_collections` builds a pair only from available finite scalar
metrics with explicit experiment and environment provenance; the pair model rejects incompatible
policy, checkpoint, seed, metric-version, or unit metadata.
`build_winner_map` computes deterministic per-seed policy ranks, ties, and regret for a scalar
metric. `select_portfolio_policy` and `evaluate_portfolio` expose every matched synthetic selector
rule and its descriptive outcome. `evaluate_portfolio_study` evaluates a fixed ruleset on disjoint
development and held-out seed sets and reports held-out constituent comparisons.

`ProtocolTracker` adds manual SQLite lifecycle tracking for an exported protocol. It validates
slot transitions and never launches, validates, or imports an external run.

### Common-Seed Paired Statistical Study

```python
from traffictwin.experiments import (
    PairedStudyConfig,
    StatisticalStudy,
    evaluate_paired_statistical_study,
    statistical_study_contract,
    statistical_study_pairs_to_csv,
    statistical_study_to_markdown,
)
```

`evaluate_paired_statistical_study(collections, config, clock=...) -> StatisticalStudy` admits only
exact compatible common-random-seed pairs from already-computed `MetricCollection` objects. It
returns the complete plan/pairing audit, original-unit paired estimate, deterministic percentile
bootstrap, exact or seeded-Monte-Carlo two-sided sign-flip result, paired effect sizes, provenance,
and limitations. With inadequate evidence, the same typed artifact records `insufficient` or
`incompatible`; missing values never become zero. The service reads no raw rows and mutates no
input or registry state.

`statistical_study_contract()` exposes the versioned method boundary. The renderer helpers produce
strict deterministic Markdown and pair-audit CSV. See
[common-seed paired statistical studies](statistical_studies.md) and [ADR-028](decisions/ADR-028-common-seed-paired-statistical-study.md).

### N-Way Common-Seed Policy Ranking

```python
from traffictwin.experiments import (
    NWayRankingConfig,
    NWayRankingStudy,
    evaluate_n_way_ranking,
    n_way_ranking_contract,
    n_way_ranking_to_csv,
    n_way_ranking_to_markdown,
)
```

`evaluate_n_way_ranking(collections, config, seed_aliases=..., clock=...) -> NWayRankingStudy`
builds exact complete multi-policy random-seed rows independently inside each scenario family,
retains missing/duplicate/incompatible evidence, and sends only admitted rows to the existing
winner map. Families with at least three rows receive deterministic joint paired-seed bootstrap
mean/rank uncertainty. Thin or incompatible families keep a typed audit; unavailable values are
never zero-filled or imputed.

The contract and renderer helpers expose the versioned method boundary and deterministic
JSON/Markdown/CSV content. See [N-way policy ranking](n_way_ranking.md) and
[ADR-029](decisions/ADR-029-common-seed-n-way-ranking.md).

### Paired Equivalence Testing

```python
from traffictwin.experiments import (
    EquivalenceMarginBasis,
    EquivalenceStudy,
    EquivalenceStudyConfig,
    equivalence_study_to_csv,
    equivalence_study_to_markdown,
    equivalence_testing_contract,
    evaluate_equivalence_study,
)
```

`evaluate_equivalence_study(collections, config, clock=...) -> EquivalenceStudy` delegates the
complete pairing/compatibility decision to STA-01 and evaluates paired-mean TOST only for an
available cohort with at least three observations and positive finite sample variance. The config
requires a positive symmetric absolute original-unit margin, basis, justification, optional
required literature reference, and alpha. The result exposes both one-sided hypotheses,
statistics, p-values, the reconciled Student-t interval, bounded conclusion, inherited audit,
source paired-study fingerprint, provenance, warnings, assumptions, and limitations.

`equivalence_testing_contract()` publishes the versioned method and interpretation boundary. The
renderers produce deterministic Markdown and audit CSV from the typed artifact. See
[paired equivalence testing](equivalence_testing.md) and
[ADR-030](decisions/ADR-030-paired-tost-equivalence-testing.md).

### Versioned Regression Gates

```python
from traffictwin.experiments import (
    GoldenApprovalStatus,
    RegressionGateReport,
    RegressionGoldenContract,
    RegressionToleranceSpec,
    SourceIdentityPolicy,
    build_regression_golden_contract,
    evaluate_regression_gate,
    parse_regression_golden_contract_json,
    parse_statistical_study_json,
    regression_gate_method_contract,
    regression_gate_to_csv,
    regression_gate_to_markdown,
)
```

`build_regression_golden_contract(subject, ..., tolerances=...) -> RegressionGoldenContract`
creates a deterministic candidate or explicitly approved contract from a completed
`MetricCollection` or STA-01 `StatisticalStudy`. It admits only available finite scalar targets,
requires explicit non-negative absolute/relative tolerances, and records typed context plus exact
or compatible-context source policy.

`evaluate_regression_gate(subject, contract, clock=...) -> RegressionGateReport` verifies approval,
subject/context/source compatibility, unit and implementation versions, and every scalar assertion.
Each allowed error is `max(absolute_tolerance, relative_tolerance × abs(expected))`; equality passes.
Missing or incompatible requirements are unavailable, complete outside-tolerance values fail, and
only a complete all-pass contract passes. Inputs are verified unchanged.

The strict parsers apply a two-megabyte JSON bound. The method-contract and renderers expose
reconciled JSON, Markdown, and CSV interfaces. See [versioned regression gates](regression_gates.md)
and [ADR-031](decisions/ADR-031-versioned-regression-gates.md).

### Paired Common-Seed Power Analysis

```python
from traffictwin.experiments import (
    PairedVarianceBasis,
    PowerAnalysis,
    PowerAnalysisConfig,
    TargetEffectBasis,
    evaluate_power_analysis,
    power_analysis_method_contract,
    power_analysis_to_csv,
    power_analysis_to_markdown,
)
```

`evaluate_power_analysis(config, clock=...) -> PowerAnalysis` evaluates one prospective
two-sided paired-mean normal-approximation plan. The config declares the metric/unit, signed target
effect, paired-difference variance, alpha, target power, evidence bases/justifications/references,
pilot size, synthetic state, and search ceiling. It returns the smallest common-seed pair count
meeting target power, achieved and preceding approximate power, total policy runs, labels,
provenance, assumptions, or a typed unavailable reason.

The service does not read completed studies, choose an effect or variance, calculate retrospective
power, launch runs, or mutate inputs. The method contract and renderer helpers provide deterministic
JSON, Markdown, and CSV boundaries. See [paired common-seed power analysis](power_analysis.md) and
[ADR-032](decisions/ADR-032-paired-normal-power-planning.md).

`evaluate_fixture_set(build_extended_fixture_set(...))` reports per-rule confusion counts,
precision, recall, false-positive rate, specificity, split summaries, severity robustness, and a
transparent KPI baseline over labelled synthetic fixtures.

See [Experiment research tools](experiment_research_tools.md) for interpretation limits.

## Bundle Manifest And Ingestion

### `BundleManifest`

Import path:

```python
from traffictwin.ingestion.manifest import BundleManifest
```

Role: versioned run-bundle manifest. Contains bundle, run, environment, file declarations,
provenance, and optional `TaskEnergyContract`, `TaskRsuTargetContract`, and
`VehicleSpatialGridContract` blocks. Each contract validates the required declared files,
columns/units, and downstream semantic admission boundary.

### `FileDeclaration`

Import path:

```python
from traffictwin.ingestion.manifest import FileDeclaration
```

Role: declared source file path, physical format (`csv` or `parquet`), optional CSV `gzip`
compression, file schema version, required columns, optional column map, units, optional checksum,
and required flag.

### Bundle Functions

```python
from traffictwin.ingestion.bundle import validate_bundle, inspect_bundle, import_bundle
```

- `validate_bundle(path) -> BundleValidationResult`
- `inspect_bundle(path) -> BundleValidationResult`
- `import_bundle(path, registry_path) -> BundleImportResult`

`BundleValidationResult` contains source path, fingerprint, manifest, seed, canonical tables, evidence availability, insufficient-evidence summary, and validation report.

Limitations: the standard run-bundle path supports explicitly declared plain CSV, gzip-CSV, and
flat scalar Parquet driven by its manifest. Public SUMO
results use the separate, bounded `traffictwin.integration.sumo` contract; Randy/VEC conversion is
not inferred through either path.

### Batch Bundle Functions

```python
from traffictwin.ingestion.batch import (
    BatchBundleSummary,
    import_bundle_batch,
    validate_bundle_batch,
)
```

- `validate_bundle_batch(inputs) -> BatchBundleSummary`
- `import_bundle_batch(inputs, registry_path) -> BatchBundleSummary`

The typed summary contains bounded input resolution issues, consolidated counts, and deterministic
per-candidate `BatchBundleResult` objects. Import uses one ordinary transaction per accepted
candidate, preserving single-bundle idempotency and conflicts while isolating failures. Use
`batch_summary_to_text`, `batch_summary_to_csv`, or `summary.to_json()` for export. CSV is a
per-candidate view; JSON retains the complete consolidated artifact. See the
[batch bundle import guide](integration/batch_bundle_import.md).

### Streaming Bundle Functions

```python
from traffictwin.ingestion import (
    CanonicalChunk,
    StreamingCanonicalisationConfig,
    collect_bundle_streaming,
    import_bundle_streaming,
    validate_bundle_streaming,
)
```

- `validate_bundle_streaming(path, config=None, consumer=None) -> StreamingBundleValidationResult`
  emits synchronous provisional chunks to an optional consumer and retains only the typed summary
  and validation artifacts.
- `collect_bundle_streaming(path, config=None) -> CollectedStreamingBundleResult` materialises all
  canonical rows for ordinary downstream analysis and therefore is not memory-bounded.
- `import_bundle_streaming(path, registry_path, config=None) -> StreamingBundleImportResult`
  validates without retention and applies ordinary metadata import/idempotency/conflict semantics.

`StreamingCanonicalisationSummary` records configuration, chunk/file counts, source and canonical
counts, observed bounds, and exact disk-backed reconciliation. `CanonicalChunk` preserves table
kind, source file, logical source-row interval, decoded-byte estimate, and one `CanonicalTables`
payload. Consumers must treat output as provisional until `result.report.may_import` is true. See
the [streaming canonicalisation guide](integration/streaming_canonicalisation.md).

### Manifest Inference Interfaces

```python
from traffictwin.ingestion.manifest_inference import (
    apply_canonicalisation_to_template,
    confirm_manifest_inference,
    infer_manifest,
    manifest_inference_contract,
)
```

Principal models are `ManifestInferenceDraft`, `CsvFileInference`, `FileKindCandidate`,
`FieldSuggestion`, `ManifestInferenceSelections`, `FileSelection`, `ConfirmedFileMapping`, and
`CanonicalisationManifest`.

- `infer_manifest(path) -> ManifestInferenceDraft` hashes complete CSVs and inspects bounded
  headers/value samples. The result is always non-executable.
- `confirm_manifest_inference(draft, source, confirmed_by=..., accept_suggestions=...,
  selections=...) -> CanonicalisationManifest` rechecks source identity and validates explicit
  acceptance or edits.
- `apply_canonicalisation_to_template(canonicalisation, template) -> BundleManifest` merges only a
  confirmed mapping into complete user-supplied bundle metadata.
- `load_inference_draft(...)` and `load_canonicalisation_manifest(...)` validate JSON/YAML
  artifacts.
- `manifest_inference_contract() -> ManifestInferenceContract` publishes the closed catalogue,
  bounds, score semantics, and unsupported behavior.

Inference scores order deterministic evidence; they are not probabilities. Units without explicit
header evidence require a user selection. See the
[manifest inference guide](integration/manifest_inference_wizard.md).

## Canonical Records

Import path:

```python
from traffictwin.canonical.records import (
    TaskRecord,
    InfrastructureRecord,
    VehicleStateRecord,
    TrafficObservationRecord,
    TripRecord,
    IncidentRecord,
)
from traffictwin.canonical.tables import CanonicalTables
```

Role: in-memory canonical records. Each record carries `source_file` and `source_row`.

Limitations: full canonical row persistence is not implemented.

## Validation

```python
from traffictwin.validation.report import ValidationReport
from traffictwin.validation.findings import ValidationFinding, Severity
from traffictwin.validation.codes import ValidationCode
```

`ValidationReport` exposes status, `may_import`, findings, files inspected, record counts, evidence availability categories, import timestamp, and validator version. Use `to_json()` for serialisation.

## Metrics

```python
from traffictwin.metrics.engine import compute_metrics, compute_metrics_for_bundle
from traffictwin.metrics.engine_config import MetricEngineConfig
from traffictwin.metrics.results import MetricCollection, MetricValue
```

- `compute_metrics(canonical_tables, run_context, evidence_availability, config=None, plugin_registry=None, clock=...) -> MetricCollection`
- `compute_metrics_for_bundle(bundle_result, config=None, plugin_registry=None, clock=...) -> MetricCollection`

Metrics are deterministic and side-effect free. Rejected bundles produce invalid metric results rather than computed numbers.

### Trusted Custom Metric Plugins

```python
from traffictwin.metrics import (
    MetricPluginRegistry,
    PluginMetricContract,
    PluginMetricInput,
    PluginMetricResult,
)
from traffictwin.metrics.plugins import (
    MetricPluginApiContract,
    MetricPluginRegistryReport,
    PluginOutputSchema,
    PluginTableRequirement,
    metric_plugin_api_contract,
)
```

- `registry.register(contract, compute) -> None` admits one reviewed callable.
- `registry.definitions() -> dict[str, MetricDefinition]` returns the local extension catalogue.
- `registry.report() -> MetricPluginRegistryReport` returns sorted contracts and a stable registry
  fingerprint.
- `metric_plugin_api_contract() -> MetricPluginApiContract` describes the static trust and failure
  boundary.

`PluginMetricInput` contains deep-copied declared canonical tables, run context, and engine config.
The callable returns `PluginMetricResult`, never a complete `MetricValue`; the engine owns run
provenance, availability reasons, repeatability checking, and output validation. See
[Custom metric plugins](custom_metric_plugins.md).

### Fixed-Window Metrics

```python
from traffictwin.metrics import (
    MetricWindow,
    PartialWindowPolicy,
    WindowedMetricConfig,
    WindowedMetricSeries,
    compute_windowed_metrics,
    compute_windowed_metrics_for_bundle,
)
```

- `compute_windowed_metrics(canonical_tables, run_context, evidence_availability, window_config, metric_config=None, plugin_registry=None, clock=...) -> WindowedMetricSeries`
- `compute_windowed_metrics_for_bundle(bundle_result, window_config, metric_config=None, plugin_registry=None, clock=...) -> WindowedMetricSeries`
- `series.slice_at(ordinal) -> WindowMetricSlice`

`WindowedMetricConfig` requires a positive width, accepts an alignment origin, requires explicit
start/end together, records `include` or `exclude` partial-edge behavior, and bounds the number of
windows. The result records aligned/effective half-open bounds, requested-range coverage, table
anchors, source counts, availability, warnings, and per-window collections. See
[Time-windowed metrics](time_windowed_metrics.md).

## Evidence Packs

```python
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.builder import attach_temporal_evidence
from traffictwin.evidence.pack import EvidencePack
from traffictwin.evidence.temporal import TemporalEvidenceConfig, build_temporal_evidence
```

- `build_evidence_pack(bundle_result, metric_collection=None, config=None, plugin_registry=None, clock=...) -> EvidencePack`
- `build_temporal_evidence(windowed_series, config) -> TemporalEvidence`
- `attach_temporal_evidence(evidence_pack, windowed_series, config) -> EvidencePack`

EvidencePack contains validation summary, evidence availability, metric-engine config, metric
collection, optional typed temporal evidence, provenance, and deterministic fingerprinting. The
temporal projection preserves the complete window grid, eligibility states, metric direction,
source-series identity, and optional declared event. It contains no narrative diagnosis.

## Comparison And Aggregation

```python
from traffictwin.metrics.comparison import compare_metric_collections
from traffictwin.metrics.aggregation import aggregate_experiment
```

- `compare_metric_collections(baseline, variation, request=None, baseline_seed=None, variation_seed=None, clock=None) -> ComparisonReport`
- `aggregate_experiment(collections, metric_keys=None, baseline_seed_id=None, variation_seed_id=None, clock=None) -> ExperimentAggregationReport`

Comparisons are descriptive. They report absolute and relative deltas, compatibility findings, and unavailable comparisons.

## Diagnostics

```python
from traffictwin.diagnostics.cross_rule import (
    CrossRuleReasoningReport,
    cross_rule_reasoning_contract,
    evaluate_cross_rule_reasoning,
    rule_result_fingerprint,
)
from traffictwin.diagnostics.sensitivity import (
    NearestFlipAnalysis,
    analyse_nearest_flip,
    nearest_flip_contract,
)
from traffictwin.diagnostics.threshold_sweep import (
    ThresholdSensitivityReport,
    ThresholdSweepRequest,
    config_for_evaluated_point,
    evaluate_threshold_sweep,
    threshold_sensitivity_contract,
)
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.declarative import (
    DeclarativeRuleRegistry,
    declarative_rule_contract,
    evaluate_declarative_rule,
    load_declarative_rule,
)
from traffictwin.rules.engine import evaluate_rules
from traffictwin.rules.r7_fairness import r7_rule_definition
from traffictwin.rules.r8_energy_anomaly import (
    R8EnergyAnomalyRule,
    r8_energy_diagnosis_contract,
)
from traffictwin.diagnostics.report import DiagnosticReport
from traffictwin.diagnostics.temporal import (
    evaluate_temporal_bundle,
    evaluate_temporal_series,
    temporal_diagnosis_contract,
)
```

- `evaluate_rules(evidence_pack, rule_config=None, clock=...) -> DiagnosticReport`
- `evaluate_cross_rule_reasoning(results, *, diagnostic_report_id, evidence_pack_id, ruleset_version, source_evidence_fingerprint, synthetic, generated_at) -> CrossRuleReasoningReport`
- `cross_rule_reasoning_contract() -> CrossRuleReasoningContract`
- `rule_result_fingerprint(result) -> str`
- `evaluate_temporal_series(bundle_result, windowed_series, temporal_config, metric_config=None, rule_config=None, plugin_registry=None, clock=...) -> TemporalDiagnosticAnalysis`
- `evaluate_temporal_bundle(bundle_result, window_config, temporal_config, rule_config=None, metric_config=None, clock=...) -> TemporalDiagnosticAnalysis`
- `temporal_diagnosis_contract() -> TemporalDiagnosisContract`
- `declarative_rule_contract() -> DeclarativeRuleContract`
- `load_declarative_rule(path, allow_reserved_core_id=False) -> DeclarativeRuleDefinition`
- `evaluate_declarative_rule(definition, evidence_pack, evaluated_at=None, allow_reserved_core_id=False) -> RuleResult`
- `DeclarativeRuleRegistry.register/definitions/report/evaluate_all`
- `r7_rule_definition(config=None) -> DeclarativeRuleDefinition`
- `r8_energy_diagnosis_contract() -> R8EnergyDiagnosisContract`
- `R8EnergyAnomalyRule(config=None).evaluate(evidence_pack, evaluated_at=None) -> RuleResult`
- `analyse_nearest_flip(evidence_pack, rule_id, rule_config=None, clock=...) -> NearestFlipAnalysis`
- `nearest_flip_contract() -> NearestFlipContract`
- `evaluate_threshold_sweep(evidence_pack, request, rule_config=None, clock=...) -> ThresholdSensitivityReport`
- `threshold_sensitivity_contract() -> ThresholdSensitivityContract`
- `config_for_evaluated_point(report, source_config, threshold) -> RuleSetConfig`

Rules consume only EvidencePack objects. `DiagnosticReport` includes ordered rule results,
triggered/insufficient/conflicting IDs, readiness, provenance, warnings, conflict observations,
the additive typed DIA-07 cross-rule artifact, and JSON/fingerprint helpers. The temporal
orchestration result retains its window artifact,
temporal EvidencePack, full ruleset report, and direct R6 result. See
[Temporal diagnosis](temporal_diagnosis.md). Declarative rules use a closed trusted-local grammar,
compile to ordinary results, and never calculate metrics. R7 selects exactly one contracted
operational completion dimension. R8 consumes only complete v1.0 completed-task energy evidence,
cross-checks its population against the completed-task count, and applies configured deterministic
thresholds. See [declarative rules](declarative_rules.md), [R7 diagnosis](fairness_diagnosis.md),
and [R8 diagnosis](energy_diagnosis.md). `NearestFlipAnalysis` is a separate deterministic
sensitivity artifact: it supports verified single-boundary R5/R7/R8 candidates, leaves discrete
support unchanged, reports unsupported/not-applicable states, and does not persist configuration.
See [nearest-flip analysis](nearest_flip_analysis.md).

`ThresholdSensitivityReport` is the separate DIA-06 complete-grid artifact. It retains every
ordinary R5/R7/R8 point status, stability summary, sampled trigger-membership interval, and exact
DIA-05 artifact when admissible. Config export is limited to exact retained points and never
persists a default. See [threshold-sensitivity explorer](threshold_sensitivity_explorer.md).

`CrossRuleReasoningReport` evaluates only completed RuleResults. It retains every original
result/fingerprint, records the bounded R1/R2 conflict, R1/R4 contextual corroboration, and R0
explicit-blocker suppression policies, and never changes status or confidence. Undeclared pairs
remain unclassified. See [deterministic cross-rule reasoning](cross_rule_reasoning.md).

## Provenance

```python
from traffictwin.provenance.builder import (
    build_metric_trace,
    build_window_metric_trace,
    build_rule_trace,
    build_run_trace,
    build_evidence_rule_trace,
)
from traffictwin.provenance.models import (
    ProvenanceTrace,
    ProvenanceNode,
    ProvenanceEdge,
    SourceRowPreview,
)
from traffictwin.provenance.query import (
    build_provenance_context,
    get_comparison_provenance_completeness,
    get_difference_contributions,
    get_metric_provenance,
    get_rule_provenance,
    get_run_provenance,
    get_report_provenance_completeness,
    get_source_provenance,
)
from traffictwin.provenance.source_rows import get_source_row
from traffictwin.provenance.contributions import (
    build_window_metric_contribution_report,
)
from traffictwin.provenance.differences import (
    build_difference_contribution_report,
    difference_contribution_report_to_csv,
    difference_provenance_contract,
)
from traffictwin.provenance.graph_export import (
    GraphRedactionMode,
    build_provenance_graph_view,
    provenance_graph_export_contract,
    provenance_graph_to_dot,
    provenance_graph_to_graphml,
)
from traffictwin.provenance.completeness import (
    ProvenanceCompletenessReport,
    provenance_completeness_contract,
    provenance_completeness_report_to_csv,
)
```

- `build_metric_trace(metric_key, bundle_result, metric_collection, evidence_pack=None, diagnostic_report=None, clock=...) -> ProvenanceTrace`
- `build_window_metric_trace(metric_key, bundle_result, series, window_ordinal, clock=...) -> ProvenanceTrace`
- `build_window_metric_contribution_report(bundle_result, series, window_ordinal, metric_key) -> WindowMetricContributionReport`
- `build_rule_trace(rule_id, bundle_result, metric_collection, evidence_pack, diagnostic_report, clock=...) -> ProvenanceTrace`
- `build_run_trace(bundle_result, metric_collection=None, evidence_pack=None, diagnostic_report=None, clock=...) -> ProvenanceTrace`
- `build_evidence_rule_trace(rule_id, evidence_pack, diagnostic_report, clock=...) -> ProvenanceTrace`
- `build_provenance_context(path, metric_config=None, rule_config=None, clock=None) -> ProvenanceContext`
- `build_difference_contribution_report(baseline_bundle, baseline_metrics, variation_bundle, variation_metrics, metric_key) -> DifferenceContributionReport`
- `get_difference_contributions(baseline_context, variation_context, metric_key) -> DifferenceContributionReport`
- `difference_contribution_report_to_csv(report) -> str`
- `difference_provenance_contract() -> DifferenceProvenanceContract`
- `build_provenance_graph_view(trace, node_limit=120, edge_limit=240, redaction_mode="safe") -> ProvenanceGraphView`
- `provenance_graph_to_dot(view) -> str`
- `provenance_graph_to_graphml(view) -> str`
- `provenance_graph_export_contract() -> ProvenanceGraphExportContract`
- `get_report_provenance_completeness(context, report_type="run", comparison_baseline=None, clock=None) -> ProvenanceCompletenessReport`
- `get_comparison_provenance_completeness(baseline_context, variation_context, clock=None) -> ProvenanceCompletenessReport`
- `provenance_completeness_contract() -> ProvenanceCompletenessContract`
- `provenance_completeness_report_to_csv(report) -> str`
- `get_source_row(bundle_reference, source_file, source_row, context_rows=2, ...) -> SourceRowPreview`

Provenance builders are read-only. They do not recompute metrics with alternate formulas, reinterpret
rules, or mutate source files. Bundle-backed traces can preview declared CSV, gzip-CSV, and Parquet
source rows. EvidencePack-only
traces mark canonical/source-row links unavailable unless the original bundle is also supplied.
Window lineage first applies the exact half-open table-anchor filter; excluded partial slices have
no metric collection and reject provenance queries visibly.

Difference provenance delegates compatibility and the ordinary delta to the metric comparison
service. Its closed direct-formula registry emits signed row terms only after reconciliation;
non-decomposable compatible scalar metrics retain complete eligible lineage with null weights.
Mapping-valued or incompatible comparisons remain unavailable. See
[difference provenance](difference_provenance.md) and
[ADR-033](decisions/ADR-033-accepted-row-difference-provenance.md).

PRO-02 graph export projects that already-built trace through deterministic root-centred bounds.
Safe mode recursively redacts local paths; structure-only mode additionally removes descriptions,
attributes, and source references. Exact omission counts are part of the view, DOT/GraphML share
the same typed nodes and stable edge IDs, and volatile timestamps are excluded from graph identity.
See [provenance graph exports](provenance_graph_exports.md) and
[ADR-034](decisions/ADR-034-deterministic-bounded-provenance-graph-exports.md).

PRO-03 queries classify the exact typed claims in a supported report template. Unavailable claims
remain in the denominator; only non-empty reconciled accepted-row claims enter the unweighted
numerator. Trace depth and complete-ledger coverage are separate. A zero-claim report has a null
score. See [provenance completeness](provenance_completeness.md) and
[ADR-035](decisions/ADR-035-explicit-report-claim-provenance-completeness.md).

## Minimal Example

```python
from pathlib import Path

from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.provenance.builder import build_metric_trace
from traffictwin.rules.engine import evaluate_rules

bundle = validate_bundle(Path("tests/fixtures/bundles/baseline_valid"))
metrics = compute_metrics_for_bundle(bundle)
pack = build_evidence_pack(bundle, metrics)
report = evaluate_rules(pack)

print(metrics.run_id)
print(report.overall_readiness)

trace = build_metric_trace("task.completion.rate", bundle, metrics, pack, report)
print(trace.root_node_id)
```

## Standalone Product Interfaces

Primary imports:

- `traffictwin.synthetic.config.SyntheticScenarioConfig`
- `traffictwin.synthetic.config.SyntheticPolicyProfile`
- `traffictwin.synthetic.scenarios.preset_config`
- `traffictwin.synthetic.bundles.write_synthetic_bundle`
- `traffictwin.synthetic.experiments.generate_trivial_multi_algorithm_experiment`
- `traffictwin.synthetic.experiments.build_r3_evidence_pack_from_bundles`
- `traffictwin.synthetic.validation.verify_synthetic_path`
- `traffictwin.demo.workspace.initialise_workspace`
- `traffictwin.demo.workspace.reset_workspace`
- `traffictwin.demo.workspace.workspace_status`
- `traffictwin.demo.launcher.launch_workspace`
- `traffictwin.reporting.builder.build_run_report`
- `traffictwin.reporting.builder.build_comparison_report`
- `traffictwin.reporting.builder.build_diagnostics_report`
- `traffictwin.reporting.builder.build_full_report`
- `traffictwin.reporting.markdown.report_to_markdown`
- `traffictwin.reporting.html.report_to_html`
- `traffictwin.reporting.pdf.report_to_pdf_bytes`
- `traffictwin.reporting.latex.latex_export_contract`
- `traffictwin.reporting.latex.project_metric_collection`
- `traffictwin.reporting.latex.project_comparison_report`
- `traffictwin.reporting.latex.project_statistical_study`
- `traffictwin.reporting.latex.project_diagnostic_report`
- `traffictwin.reporting.latex.projection_to_latex_fragment`
- `traffictwin.reporting.latex.projection_to_svg`
- `traffictwin.reporting.latex.projection_to_pdf`
- `traffictwin.reporting.latex.write_projection_exports`

These interfaces create synthetic bundles, workspaces, reports, and launch plans. They do not add
new metric formulas or diagnostic rules.

The REP-01 projectors accept only their named completed typed artifact. They return a bounded
`ResearchExportProjection`; table and optional figure renderers consume that same object. The
writer publishes exact `.tex`/`.svg`/`.pdf` paths and returns a path-free checksummed
`ResearchExportReceipt`. See [LaTeX research tables and static figures](latex_research_exports.md).

REP-02 append-only analyst-history interfaces:

- `traffictwin.annotations.AnalystArtifactReference`
- `traffictwin.annotations.AnalystAnnotationRequest`
- `traffictwin.annotations.AnalystAnnotation`
- `traffictwin.annotations.AnalystAnnotationHistory`
- `traffictwin.annotations.analyst_annotation_contract`
- `Registry.append_analyst_annotation`
- `Registry.get_analyst_annotation`
- `Registry.list_analyst_annotations`
- `reporting.annotation_rendering.attach_analyst_annotations`
- `reporting.annotation_rendering.attach_registry_annotations`

Stored target kinds are existence-checked. History is ordered/paginated and database triggers
reject update/delete. Report attachment changes only the dedicated `analyst_annotations` field and
named claim exclusion; computed sections and typed claim references remain unchanged. See
[analyst annotations](analyst_annotations.md).

REP-03 structured-report-diff interfaces:

- `traffictwin.reporting.models.ReportClaimSnapshot`
- `traffictwin.reporting.diffing.ReportDiffContract`
- `traffictwin.reporting.diffing.StructuredReportDiff`
- `traffictwin.reporting.diffing.report_diff_contract`
- `traffictwin.reporting.diffing.parse_research_report_json`
- `traffictwin.reporting.diffing.report_scientific_fingerprint`
- `traffictwin.reporting.diffing.compare_structured_reports`
- `traffictwin.reporting.diffing.report_diff_to_markdown`

The comparator gates payload schema, report type, source mode, claim denominator, supported type,
and reference/snapshot completeness before comparing canonical claim JSON. It never parses
rendered section bodies or analyst annotations. See
[structured report diffing](structured_report_diffing.md).

REP-04 executive-summary interfaces:

- `traffictwin.reporting.executive.ExecutiveSummaryContract`
- `traffictwin.reporting.executive.ExecutiveSummary`
- `traffictwin.reporting.executive.executive_summary_contract`
- `traffictwin.reporting.executive.project_executive_summary`
- `traffictwin.reporting.executive.executive_summary_to_markdown`
- `traffictwin.reporting.executive.executive_summary_to_html`
- `traffictwin.reporting.executive_pdf.executive_summary_to_pdf_bytes`

The projector admits one compatible complete typed report, publishes exact availability and
bounded selection state, retains all source warnings/limitations, and adds relative fingerprinted
source/claim links. The PDF renderer returns exactly one A4 page or raises
`ExecutiveSummaryLayoutError`; it never removes caveats. See
[one-page executive summary](executive_summary.md).

REP-05 deterministic registry-search interfaces:

- `traffictwin.registry_search.SearchCategory`
- `traffictwin.registry_search.RegistrySearchHit`
- `traffictwin.registry_search.RegistrySearchResult`
- `traffictwin.registry_search.RegistrySearchContract`
- `traffictwin.registry_search.registry_search_contract`
- `traffictwin.registry_search.search_registry`

The service projects six closed local categories, redacts absolute paths before matching, applies
bounded Unicode-normalised lexical AND ranking, and opens existing SQLite state read-only. It
returns complete inventory/match/omission/skip/redaction counts plus canonical JSON and an exact
result fingerprint. See [full-text registry search](registry_search.md).

OPS-01 registry-migration interfaces:

- `traffictwin.storage.migrations.RegistryMigrationDescriptor`
- `traffictwin.storage.migrations.RegistryMigrationStatus`
- `traffictwin.storage.migrations.RegistryMigrationResult`
- `traffictwin.storage.migrations.RegistryMigrationContract`
- `traffictwin.storage.migrations.registry_migration_contract`
- `traffictwin.storage.migrations.inspect_registry_migrations`
- `traffictwin.storage.migrations.migrate_registry`
- `traffictwin.storage.migrations.require_current_registry_schema`

The migration runner owns five contiguous SQLite schema versions, applies the complete pending
plan and immutable checksummed ledger updates in one transaction, validates every boundary, and
preserves existing payload columns. Read-only status inspection never migrates. See
[registry schema migrations](registry_migrations.md).

OPS-02 canonical-cache interfaces:

- `traffictwin.ingestion.cache.CanonicalCacheKey`
- `traffictwin.ingestion.cache.CanonicalCacheStatus`
- `traffictwin.ingestion.cache.CanonicalCacheContract`
- `traffictwin.ingestion.cache.canonical_cache_contract`
- `traffictwin.ingestion.cache.canonical_cache_key`
- `traffictwin.ingestion.bundle.inspect_bundle_cache`
- `traffictwin.ingestion.bundle.validate_bundle_cached`

`validate_bundle_cached` always reopens and fingerprints raw evidence before a hit. It returns
`CachedBundleValidationResult`, containing an ordinary `BundleValidationResult` and a typed cache
receipt. Only accepted ordinary generic results are published as six checksummed strict Parquet
tables outside the bundle. Stale, incompatible, corrupt, and symlinked entries are never used or
overwritten. See [canonical-table caching](canonical_table_caching.md).

Additional research-support interfaces:

- `traffictwin.case_studies.build_synthetic_case_study_pack`
- `traffictwin.provenance.query.get_metric_contributions`
- `traffictwin.provenance.contributions.contribution_report_to_csv`
- `traffictwin.provenance.query.get_difference_contributions`
- `traffictwin.provenance.differences.difference_contribution_report_to_csv`
- `traffictwin.reporting.pdf.report_to_pdf_bytes`
- `traffictwin.rendering.findings.render_diagnostic_findings`
- `traffictwin.rendering.findings.diagnostic_narrative_to_markdown`
- `traffictwin.evaluation.participants.load_mock_participant_dataset`
- `traffictwin.evaluation.participants.analyse_participant_results`
- `traffictwin.evaluation.participants.participant_analysis_to_csv`
- `traffictwin.ui.charts.corridor_figure`
- `traffictwin.ui.audit.analyse_accessibility_snapshots`

The metric contribution report contains every accepted canonical candidate row but never assigns
unsupported causal weights. The findings renderer copies computed findings only. Participant
analysis accepts only explicitly labelled synthetic mock datasets.

## SUMO Result Interfaces

The import-only adapter is exported from `traffictwin.integration.sumo`:

```python
from traffictwin.integration.sumo import (
    compute_metrics_for_sumo,
    import_sumo_results,
    sumo_results_capability_manifest,
    sumo_source_contract,
    validate_sumo_results,
)
```

Principal models are `SumoResultManifest`, `SumoValidationResult`, `SumoTripObservation`,
`SumoSummaryStep`, `SumoSourceContract`, and `SumoImportResult`.

- `validate_sumo_results(path) -> SumoValidationResult` verifies metadata, checksums, safe XML,
  trip consistency, and summary time order without mutating raw files.
- `compute_metrics_for_sumo(result, plugin_registry=None) -> MetricCollection` runs the existing deterministic engine
  over supported canonical trips. Summary occupancy remains source-specific.
- `import_sumo_results(path, registry_path, ...) -> SumoImportResult` registers an accepted result
  idempotently and stores its metric collection.
- `sumo_source_contract() -> SumoSourceContract` describes every mapping and unavailable feature.

Adapter v1 supports SUMO 1.27.x tripinfo and summary XML. It excludes FCD, person/container
canonicalisation, traffic-count relabelling, and all launch behavior. See the
[SUMO output adapter guide](integration/sumo_output_adapter.md).

## TOS Data Result Interfaces

The optional read-only integration is exported from `traffictwin.integration.tos`. NPZ operations
require the `tos` dependency extra.

```python
from traffictwin.integration.tos import (
    build_tos_evidence_pack,
    build_evaluation_matrix,
    build_generalisation_matrix,
    build_static_results_atlas,
    build_tos_research_report,
    build_tos_metric_trace,
    build_tos_rule_trace,
    compare_campaigns,
    audit_tos_package,
    import_evaluation_summaries,
    inspect_tos_package,
    load_replay_frame,
    load_rsu_replay_series,
    load_task_sample,
    load_training_run,
    list_training_runs,
    metric_collection_from_evaluation,
    read_evaluation_runs,
    tos_source_contract,
    summarise_rsu_run,
    summarise_task_outcomes,
    summarise_trace,
    write_tos_results_pack,
    tos_metric_catalogue,
    validate_tos_package,
)
```

Principal models:

- `TosEvaluationRun`: one strictly parsed evaluation-master row with stable TrafficTwin run and
  experiment references.
- `TosValidationReport`: package inventory, stable findings, source commit/fingerprint, engine
  versions, import gate, and explicit capability boundary.
- `TosReplayFrame`: one bounded, time-indexed historical frame with source vehicle slots and raw RSU
  state carrying confirmed source meanings and units.
- `TosRsuReplayPoint`: one RSU/time point with active tasks, compute backlog, concurrency bound,
  and source-specific pressure.
- `TosTaskSample`: bounded per-arrival observations retaining NPZ indices, joined decision,
  simulation time, and deadline-success semantics.
- `TosImportSummary`: created/existing registry counts for an idempotent summary import.
- `TosSourceContract`: versioned field, unit, control, execution, and limitation evidence derived
  from the inspected `vec_env` source.
- `TosEvaluationMatrix`: source measure definition plus campaign/cell aggregates and fleet-seed
  values.
- `TosCampaignComparisonReport`: exact common-fleet-seed observations and descriptive deltas.
- `TosGeneralisationMatrix`: explicit in-domain, held-out, or unknown provenance labels.
- `TosTrainingRun`: bounded source training points and optional greedy summary.
- `TosTraceSummary`, `TosRsuRunSummary`, and `TosTaskOutcomeSummary`: read-only descriptive views
  over evidenced NPZ arrays.
- `TosReproducibilityAudit`: artifact coverage and blocked reproducibility checks.
- `TosIntegrationReadinessReport`: versioned gates and capability decisions for deeper integration.
- `TosSupervisorPackManifest`: checksummed private-pack inventory and publication boundary.
- `SyntheticStaticSiteManifest`: synthetic/live/external flags and page hashes for static staging.

Key functions:

- `inspect_tos_package(path, deep=False) -> TosValidationReport`
- `validate_tos_package(path, deep=True) -> TosValidationReport`
- `read_evaluation_runs(path) -> list[TosEvaluationRun]`
- `metric_collection_from_evaluation(run, package_fingerprint, clock=...) -> MetricCollection`
- `tos_metric_catalogue() -> dict[str, MetricDefinition]`
- `build_tos_evidence_pack(run, report, metrics, clock=...) -> EvidencePack`
- `import_evaluation_summaries(path, registry_path, validation_report=None, clock=...) -> TosImportSummary`
- `load_replay_frame(path, run_key, index, max_vehicles=25) -> TosReplayFrame`
- `load_rsu_replay_series(path, run_key, stride=1) -> list[TosRsuReplayPoint]`
- `load_task_sample(path, run_key, limit=25) -> TosTaskSample`
- `tos_source_contract() -> TosSourceContract`
- `build_tos_metric_trace(...) -> ProvenanceTrace`
- `build_tos_rule_trace(...) -> ProvenanceTrace`
- `build_evaluation_matrix(rows, path, measure_key=..., evaluation_fleet=..., clock=...) -> TosEvaluationMatrix`
- `compare_campaigns(rows, path, baseline, variation, ...) -> TosCampaignComparisonReport`
- `build_generalisation_matrix(rows, path) -> TosGeneralisationMatrix`
- `list_training_runs(path) -> list[TosTrainingRunSummary]`
- `load_training_run(path, training_id, max_points=800) -> TosTrainingRun`
- `summarise_trace(path, trace_name, max_profile_points=600) -> TosTraceSummary`
- `summarise_rsu_run(path, run_key) -> TosRsuRunSummary`
- `summarise_task_outcomes(path, run_key) -> TosTaskOutcomeSummary`
- `audit_tos_package(path, clock=...) -> TosReproducibilityAudit`
- `build_tos_research_report(path, variation_campaign=..., clock=...) -> ResearchReport`
- `build_static_results_atlas(path, clock=...) -> str`
- `write_tos_results_pack(path, output, variation_campaign=..., clock=...) -> TosResultsPack`
- `build_tos_integration_readiness(path, ..., clock=...) -> TosIntegrationReadinessReport`
- `write_tos_supervisor_pack(path, output, ..., clock=...) -> TosSupervisorPack`
- `build_tos_supervisor_pack_zip(path, ..., clock=...) -> bytes`
- `stage_public_tos_atlas(path, output, publication_permission_confirmed=...) -> Path`
- `stage_synthetic_demo_site(workspace, output, overwrite=False, clock=...) -> SyntheticStaticSiteManifest`

The metric builder wraps source-provided aggregates using distinct implementation/version metadata;
it does not invoke Phase 3 calculators over absent canonical rows. Source deadline success has its
own definitions, `tos.task.deadline_success.rate` and
`tos.task.deadline_success.rate_by_class`; it is not relabelled as TrafficTwin physical completion.
The EvidencePack is intentionally partial, so existing rules cannot treat unavailable completion,
infrastructure, tier, trip, or temporal evidence as present. Source paths in registry records and
exported traces are package-relative references.

Limitations: no full canonical conversion, no canonical RSU utilisation/queue mapping, no
persistent vehicle identity, no SUMO/trip data, and no executable TrafficTwin launcher. The
source evaluator contract is documented, but checkpoint/path/writer/runtime blockers remain. See
[integration/tos_data_adapter.md](integration/tos_data_adapter.md).
The focused analysis behavior is documented in
[integration/tos_results_workbench.md](integration/tos_results_workbench.md).

Related documents:

- [Developer guide](developer_guide.md)
- [Data contract](data_contract.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Standalone demo](standalone_demo.md)
- [Report export](report_export.md)
- [Deployment](deployment.md)
- [Supervisor and viva pack](supervisor_pack.md)

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

### `CapabilityManifest`

Import path:

```python
from traffictwin.config.capabilities import CapabilityManifest, default_export_import_manifest
```

Role: describes adapter capabilities with `true`, `false`, or `unknown`. The default manifest uses adapter `generic_csv`, `direct_launch=false`, and unconfirmed controls as `unknown`.

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
- `add_experiment(experiment)` / `get_experiment(experiment_id)`
- `update_experiment_status(experiment_id, new_status)`
- `add_run(run)` / `get_run(run_id)`
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

## Bundle Manifest And Ingestion

### `BundleManifest`

Import path:

```python
from traffictwin.ingestion.manifest import BundleManifest
```

Role: versioned run-bundle manifest. Contains bundle, run, environment, file declarations, and provenance.

### `FileDeclaration`

Import path:

```python
from traffictwin.ingestion.manifest import FileDeclaration
```

Role: declared source file path, file schema version, required columns, optional column map, units, optional checksum, and required flag.

### Bundle Functions

```python
from traffictwin.ingestion.bundle import validate_bundle, inspect_bundle, import_bundle
```

- `validate_bundle(path) -> BundleValidationResult`
- `inspect_bundle(path) -> BundleValidationResult`
- `import_bundle(path, registry_path) -> BundleImportResult`

`BundleValidationResult` contains source path, fingerprint, manifest, seed, canonical tables, evidence availability, insufficient-evidence summary, and validation report.

Limitations: real Randy/SUMO schemas are not implemented. Current adapter is generic CSV driven by the manifest.

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

- `compute_metrics(canonical_tables, run_context, evidence_availability, config=None, clock=...) -> MetricCollection`
- `compute_metrics_for_bundle(bundle_result, config=None, clock=...) -> MetricCollection`

Metrics are deterministic and side-effect free. Rejected bundles produce invalid metric results rather than computed numbers.

## Evidence Packs

```python
from traffictwin.evidence.builder import build_evidence_pack
from traffictwin.evidence.pack import EvidencePack
```

- `build_evidence_pack(bundle_result, metric_collection=None, config=None, clock=...) -> EvidencePack`

EvidencePack contains validation summary, evidence availability, metric-engine config, metric collection, provenance, and deterministic fingerprinting. It contains no narrative diagnosis.

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
from traffictwin.rules.config import RuleSetConfig
from traffictwin.rules.engine import evaluate_rules
from traffictwin.diagnostics.report import DiagnosticReport
```

- `evaluate_rules(evidence_pack, rule_config=None, clock=...) -> DiagnosticReport`

Rules consume only EvidencePack objects. `DiagnosticReport` includes ordered rule results, triggered/insufficient/conflicting IDs, readiness, provenance, warnings, conflict observations, and JSON/fingerprint helpers.

## Provenance

```python
from traffictwin.provenance.builder import (
    build_metric_trace,
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
    get_metric_provenance,
    get_rule_provenance,
    get_run_provenance,
    get_source_provenance,
)
from traffictwin.provenance.source_rows import get_source_row
```

- `build_metric_trace(metric_key, bundle_result, metric_collection, evidence_pack=None, diagnostic_report=None, clock=...) -> ProvenanceTrace`
- `build_rule_trace(rule_id, bundle_result, metric_collection, evidence_pack, diagnostic_report, clock=...) -> ProvenanceTrace`
- `build_run_trace(bundle_result, metric_collection=None, evidence_pack=None, diagnostic_report=None, clock=...) -> ProvenanceTrace`
- `build_evidence_rule_trace(rule_id, evidence_pack, diagnostic_report, clock=...) -> ProvenanceTrace`
- `build_provenance_context(path, metric_config=None, rule_config=None, clock=None) -> ProvenanceContext`
- `get_source_row(bundle_reference, source_file, source_row, context_rows=2, ...) -> SourceRowPreview`

Provenance builders are read-only. They do not recompute metrics with alternate formulas, reinterpret
rules, or mutate source files. Bundle-backed traces can preview CSV source rows. EvidencePack-only
traces mark canonical/source-row links unavailable unless the original bundle is also supplied.

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

These interfaces create synthetic bundles, workspaces, reports, and launch plans. They do not add
new metric formulas or diagnostic rules.

## TOS Data Result Interfaces

The optional read-only integration is exported from `traffictwin.integration.tos`. NPZ operations
require the `tos` dependency extra.

```python
from traffictwin.integration.tos import (
    build_tos_evidence_pack,
    build_tos_metric_trace,
    build_tos_rule_trace,
    import_evaluation_summaries,
    inspect_tos_package,
    load_replay_frame,
    load_task_sample,
    metric_collection_from_evaluation,
    read_evaluation_runs,
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
  fields.
- `TosTaskSample`: bounded per-arrival observations retaining NPZ indices and deadline-success
  semantics.
- `TosImportSummary`: created/existing registry counts for an idempotent summary import.

Key functions:

- `inspect_tos_package(path, deep=False) -> TosValidationReport`
- `validate_tos_package(path, deep=True) -> TosValidationReport`
- `read_evaluation_runs(path) -> list[TosEvaluationRun]`
- `metric_collection_from_evaluation(run, package_fingerprint, clock=...) -> MetricCollection`
- `tos_metric_catalogue() -> dict[str, MetricDefinition]`
- `build_tos_evidence_pack(run, report, metrics, clock=...) -> EvidencePack`
- `import_evaluation_summaries(path, registry_path, validation_report=None, clock=...) -> TosImportSummary`
- `load_replay_frame(path, run_key, index, max_vehicles=25) -> TosReplayFrame`
- `load_task_sample(path, run_key, limit=25) -> TosTaskSample`
- `build_tos_metric_trace(...) -> ProvenanceTrace`
- `build_tos_rule_trace(...) -> ProvenanceTrace`

The metric builder wraps source-provided aggregates using distinct implementation/version metadata;
it does not invoke Phase 3 calculators over absent canonical rows. Source deadline success has its
own definitions, `tos.task.deadline_success.rate` and
`tos.task.deadline_success.rate_by_class`; it is not relabelled as TrafficTwin physical completion.
The EvidencePack is intentionally partial, so existing rules cannot treat unavailable completion,
infrastructure, tier, trip, or temporal evidence as present. Source paths in registry records and
exported traces are package-relative references.

Limitations: no full canonical conversion, no RSU utilisation/queue mapping, no persistent vehicle
identity, no SUMO/trip data, and no source-environment execution contract. See
[integration/tos_data_adapter.md](integration/tos_data_adapter.md).

Related documents:

- [Developer guide](developer_guide.md)
- [Data contract](data_contract.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Standalone demo](standalone_demo.md)
- [Report export](report_export.md)

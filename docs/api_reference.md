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

Related documents:

- [Developer guide](developer_guide.md)
- [Data contract](data_contract.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Diagnostic report specification](diagnostic_report_spec.md)

# Custom Metric Plugins

TrafficTwin `MET-06` supports explicit trusted local Python metrics. It does **not** accept uploaded
code, import arbitrary module paths, or sandbox extensions. Use this API only with code you have
reviewed and deliberately included in the local application.

## Minimal example

```python
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics import (
    MetricPluginRegistry,
    PluginMetricContract,
    PluginMetricInput,
    PluginMetricResult,
    compute_metrics_for_bundle,
)
from traffictwin.metrics.definitions import AggregationScope, MetricDefinition, MetricDomain
from traffictwin.metrics.plugins import (
    PluginOutputKind,
    PluginOutputSchema,
    PluginRowPolicy,
    PluginScalarType,
    PluginTableRequirement,
)

contract = PluginMetricContract(
    plugin_id="dissertation",
    plugin_version="1.0.0",
    definition=MetricDefinition(
        key="plugin.dissertation.latency_observation_count",
        human_name="Latency observation count",
        description="Count canonical task rows with observed latency.",
        domain=MetricDomain.CUSTOM,
        unit="count",
        aggregation_scope=AggregationScope.RUN,
        required_tables=["tasks"],
        required_fields={"tasks": ["latency_ms"]},
        implementation_version="1.0.0",
        time_window_applicable=True,
        time_anchor="tasks.arrival_time_s",
    ),
    inputs=[
        PluginTableRequirement(
            table="tasks",
            required_fields=["latency_ms"],
            row_policy=PluginRowPolicy.DROP_INCOMPLETE,
            minimum_eligible_rows=1,
        )
    ],
    output_schema=PluginOutputSchema(
        kind=PluginOutputKind.SCALAR,
        scalar_type=PluginScalarType.INTEGER,
    ),
)

def count_latency_rows(inputs: PluginMetricInput) -> PluginMetricResult:
    return PluginMetricResult(
        value=len(inputs.tables.tasks),
        metadata={"formula": "count(admitted task rows)"},
    )

plugins = MetricPluginRegistry()
plugins.register(contract, count_latency_rows)

validation = validate_bundle(".demo/bundles/baseline")
metrics = compute_metrics_for_bundle(validation, plugin_registry=plugins)
print(metrics.by_key()[contract.definition.key].model_dump_json(indent=2))
```

The same registry can be passed to `compute_metrics`, `compute_windowed_metrics`,
`compute_windowed_metrics_for_bundle`, `compute_metrics_for_sumo`, `build_evidence_pack`, and
`build_provenance_context`.

## Contract rules

- Keys must use `plugin.<plugin_id>.*` and the `custom` domain.
- Required tables and fields in the metric definition must exactly match input declarations.
- A `require_complete` input blocks execution if any row lacks a declared field.
- A `drop_incomplete` input supplies only complete rows and records all exclusions in provenance.
- Every input requires fully available evidence and its declared minimum eligible-row count.
- Windowed metrics must use the standard time anchor of one declared input table.
- Metrics without a declared window anchor are omitted before slice evaluation, so their plugin
  functions are never called by the fixed-window engine.
- Scalar outputs support finite numbers, integers, booleans, or strings.
- Grouped outputs use non-empty string keys and one declared scalar type. Null group values require
  both `allow_null_group_values=True` and a `partial` result.
- An unavailable result must have `value=None` and identify missing evidence.

## Execution and failure behavior

TrafficTwin invokes each plugin twice using fresh deep copies. Canonical JSON outputs must match.
The engine then validates the output schema and creates the ordinary metric result. Availability,
exceptions, nondeterminism, and invalid outputs become stable unavailable reasons; they do not stop
core metrics or other extensions.

Use the machine-readable boundary command when integrating tooling:

```bash
traffictwin metrics plugin-api --format json
```

## Provenance and comparison

Plugin results embed their full validated contract and fingerprint. The provenance service uses the
embedded definition even when the original in-memory registry is no longer present. Contribution
ledgers enumerate every candidate row and show which rows were supplied through the declared input
view. This is input lineage, not causality or an additive attribution.

Scalar baseline/variation comparison is admitted only when both plugin contract fingerprints match.
Changing a version, field rule, output schema, unit, or other contract field makes the pair
incompatible.

## Author checklist

1. Keep the function deterministic, side-effect-free, and independent of wall-clock time, network,
   ambient files, and process-global state.
2. Declare every canonical input field actually needed.
3. Return unavailable or partial instead of substituting zero for missing evidence.
4. Use a new implementation/plugin version whenever semantics change.
5. Add exact-value, missing-evidence, determinism, exception, output-schema, window, comparison, and
   provenance tests.
6. Record scientific limitations in the metric definition.

The complete decision and limitations are in
[ADR-021](decisions/ADR-021-trusted-local-custom-metric-plugin-api.md).

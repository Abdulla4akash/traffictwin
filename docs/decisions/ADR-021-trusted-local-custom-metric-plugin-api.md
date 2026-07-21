# ADR-021 — Trusted Local Custom Metric Plugin API

Status: accepted and implemented
Date: 20 July 2026
Capability: `MET-06`

## Context

TrafficTwin's original metric engine used a fixed catalogue and direct calls to built-in metric
families. v0.5 requires a way for trusted researchers to add deterministic metrics without
weakening input semantics, unavailable states, output typing, provenance, or failure isolation.
The extension boundary must not become arbitrary uploaded-code execution or allow a plugin to read
raw files behind the canonicalisation boundary.

## Decision

TrafficTwin provides an explicit, in-process `MetricPluginRegistry`. Application code constructs a
registry, registers a `PluginMetricContract` and callable, and passes the registry to the ordinary
whole-run, windowed, bundle, SUMO, evidence, or provenance service. There is no uploaded-code UI,
module-path option, automatic entry-point discovery, `eval`, or dynamic file import.

Every v1.0 contract declares:

- a `plugin.<plugin_id>.*` metric key, plugin version, and ordinary `MetricDefinition`;
- canonical input tables and fields;
- `require_complete` or `drop_incomplete` row treatment and a minimum eligible-row count;
- unit, aggregation scope, output kind, scalar type, and grouped-null policy;
- a canonical time anchor when the metric is window-applicable;
- pre-evaluation exclusion from fixed-window execution when the metric is whole-run-only;
- explicit-null unavailable behavior;
- the `declared_input_rows_v1` provenance mapping; and
- the `trusted_local_code` and `repeatable_pure_function_v1` declarations.

Registration rejects malformed contracts, duplicate plugin keys, core-key collisions, mixed
versions for one plugin ID, unknown canonical fields, and inconsistent table/field/anchor
declarations before evaluation.

The engine owns admission and result construction. It checks evidence status, applies the declared
row policy, supplies deep-copied declared canonical inputs, runs the callable twice with fresh
copies, compares canonical JSON outputs, validates the closed scalar/grouped schema, and then wraps
the output in an ordinary `MetricValue`. One plugin cannot mutate engine-owned canonical tables.

Failures are isolated per metric:

| Condition | Stable reason |
|---|---|
| availability contract not met | `PLUGIN_AVAILABILITY_REQUIREMENT_UNMET` |
| callable raises or cannot return the typed result | `PLUGIN_EXECUTION_FAILED` |
| the two evaluated outputs differ, or only the repeat run fails | `PLUGIN_NONDETERMINISTIC` |
| output is non-finite, non-JSON, or violates its schema | `PLUGIN_OUTPUT_INVALID` |
| plugin deliberately returns unavailable with missing evidence | `PLUGIN_DECLARED_UNAVAILABLE` |

Exception messages are not copied into public output. Stable exception class names may be retained
as technical metadata. Base and other plugin metrics continue computing.

Each result embeds the validated contract, contract fingerprint, input/eligible row counts,
execution state, and determinism-verification state. Provenance resolves the embedded definition
and builds a complete ledger over every declared candidate row. Included means the row was supplied
to the bounded plugin input; this is lineage, not an additive weight or causal attribution.

Scalar plugin comparison requires equal contract fingerprints. Windowed plugins reuse the ordinary
half-open filtering engine and must declare an admitted canonical anchor. The core catalogue remains
63 definitions and 60 window-applicable definitions; plugins extend a particular explicitly supplied
registry rather than silently altering the global catalogue.

## Consequences

- Researchers can extend metrics in local Python while retaining ordinary metric, comparison,
  evidence, window, report-serialization, and provenance artifacts.
- The API is deterministic-by-contract and detects repeatability failures for the evaluated input.
- The API is not a security sandbox and cannot prove global purity, scientific validity, or freedom
  from hidden external state.
- Plugin functions execute twice, so authors must keep them side-effect-free and account for the
  deliberate verification cost.
- Long-running-code timeouts, process isolation, dependency discovery, signed packages, uploaded
  extensions, and remote plugin marketplaces are not part of v1.0.
- SUMO canonical trip evidence can be consumed through the same explicit registry. The read-only TOS
  workbench remains outside this API because it does not provide an ordinary canonical run bundle.

## Rejected alternatives

- **Uploaded Python or a module-path CLI option:** violates the trusted-local boundary and creates an
  unsafe code-execution surface.
- **Automatic package entry-point discovery:** makes the active scientific catalogue depend on
  ambient environment state. Explicit registry construction is easier to audit and reproduce.
- **Let plugins return `MetricValue` directly:** would let extensions bypass availability,
  provenance, version, and run-context controls owned by the engine.
- **Run once and trust a determinism flag:** does not satisfy the required repeatability acceptance
  evidence.
- **Catch one plugin error around the entire engine:** would allow a single extension to suppress
  unrelated results.

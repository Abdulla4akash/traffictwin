# EvidencePack Specification

An EvidencePack is the Phase 3 handoff object consumed by Phase 5 deterministic diagnostic rules. It contains structured evidence only. It does not contain narrative diagnoses, causal claims, recommendations, LLM prose, or XAI output.

## Schema

Current schema version: `1.0`.

Top-level fields:

- `schema_version`
- `pack_id`
- `generated_at`
- `synthetic`
- `run_context`
- `source_bundle_fingerprint`
- `validation_summary`
- `evidence_availability`
- `metric_engine_config`
- `metric_collection`
- `temporal_evidence` (optional)
- `excluded_record_counts`
- `warnings`
- `provenance`

## Run Context

The run context records:

- run ID;
- experiment ID;
- seed ID;
- algorithm;
- checkpoint;
- random seed;
- environment name;
- environment version or commit.

## Metric Collection

The embedded metric collection contains ordered `MetricValue` objects. Each metric carries:

- metric key;
- status;
- value or `null`;
- unit;
- aggregation scope;
- required and missing evidence;
- reason codes;
- embedded custom-metric contracts/fingerprints and evaluated-input repeatability metadata when an
  explicit trusted plugin registry supplied the metric;
- implementation version;
- run provenance;
- computation timestamp.

## Optional Temporal Evidence

`temporal_evidence` is a typed projection of one existing `WindowedMetricSeries` for one scalar
metric. It preserves the complete window grid and records, for every ordinal, the value or its
explicit ineligibility reason. It also records metric unit/version/direction, source-series
fingerprint, coverage requirement, and optional researcher-declared event context. The event maps
to the containing half-open effective window; TrafficTwin does not infer an event from a change.

Unavailable, excluded, partial, low-coverage, missing, non-scalar, and incompatible windows remain
explicit and are never replaced by zero. See [Temporal diagnosis](temporal_diagnosis.md).

## Fingerprinting

`EvidencePack.fingerprint()` uses canonical JSON with generated timestamps normalised. Attached
temporal evidence includes both the source-series and projection fingerprints. These identifiers
are intended for reproducibility checks, not as security signatures.

## Provenance Use

The Provenance Explorer can use an EvidencePack to trace metric keys, metric results, rule evidence,
and run context. EvidencePack-only traces cannot inspect canonical rows or source tabular rows unless the
original run bundle is also available; those links are represented as unavailable.

## Validation And Evidence

The evidence pack includes the Phase 2 validation status and evidence availability categories. Phase 5 rules use this information to suppress unsupported hypotheses.

## Diagnostic Consumption

Rules consume only the EvidencePack:

- R0 reads validation status, evidence availability, and metric statuses.
- R1 reads task-class completion, task count, offload rate, and mean utilisation.
- R2 reads saturation, queue, utilisation, and task outcome metrics.
- R3 requires experiment-level metric keys such as `experiment.algorithm.count` and `experiment.cross_algorithm_dispersion`.
- R6 requires compatible typed temporal evidence and evaluates sustained adverse change plus
  bounded recovery from an optional declared event.
- R7 reads one already-computed exact operational group metric from the ordinary metric collection;
  it requires compatible policy/contract fingerprints, full coverage, group count, and support.
- R8 reads exact canonical completed-task energy and its completed-count denominator; it requires
  compatible contract fingerprint, units, complete coverage, support, and consistent counts.
- Local declarative rules likewise read only admitted metric keys/status/units/metadata from this
  boundary and cannot access raw or canonical rows.

`DIA-05` nearest-flip analysis also accepts only the EvidencePack plus an explicit rule ID and
`RuleSetConfig`. It reads the admitted observation from the ordinary R5/R7/R8 `RuleResult`, retains
discrete support, and re-evaluates the exact one-field candidate through the same rule engine. It
does not read canonical/source rows, recalculate a metric, or mutate the EvidencePack.

`DIA-06` threshold sensitivity accepts the same boundary plus explicit bounded grid controls. It
temporarily changes only that contracted threshold, retains every ordinary point status/config/
result fingerprint, and keeps support/dimension settings fixed. The Streamlit page cannot add
evidence or calculate a status.

`DIA-07` cross-rule reasoning runs only after the ordinary rules have completed. It reads the
retained `RuleResult` sequence and its cited evidence keys; it does not read raw or canonical rows,
recalculate metrics, change the EvidencePack, or create a new rule result. Exact source evidence
overlap and explicit R0 blocker targets are recorded in the additive DiagnosticReport artifact.

Rules do not mutate the EvidencePack.

## Limitations

- Excluded row counts are zero for accepted synthetic fixtures because Phase 2 rejects bundles with invalid rows rather than computing partial metrics from rejected data.
- Canonical rows remain in memory; the evidence pack stores metric results and provenance, not raw CSV contents.
- The read-only TOS path builds partial EvidencePacks from source summaries. Tasks are `partial`;
  infrastructure, vehicles, traffic, trips, and incidents remain `unavailable` because no canonical
  row evidence or compatible RSU utilisation/queue and trip mapping exists. Source-specific RSU
  active-task pressure is inspectable but does not satisfy those dependencies.
- TOS deadline success uses source-specific keys and does not satisfy TrafficTwin physical-task
  completion dependencies in R1.
- Current TOS and SUMO evidence does not satisfy R7's exact vehicle-tier or execution-target group
  contract; R7 remains explicitly insufficient rather than interpreting source summaries.
- Current TOS and SUMO evidence does not satisfy R8's canonical completed-task energy contract;
  source-specific aggregate energy is not relabelled and R8 remains explicitly insufficient.
- Full Randy/SUMO canonical evidence remains unavailable until compatible outcome/identity,
  infrastructure, target/trip, producer, and fixture evidence is supplied.
- R1 lacks direct T1-by-low-tier cross-tab evidence in current packs.
- R2 lacks direct task-to-saturation temporal overlap in current packs.
- R3 experiment-level evidence is available only in synthetic diagnostic fixtures at this stage.

## Related Documents

- [Metrics catalogue](metrics_catalogue.md)
- [Diagnostic rules](diagnostic_rules.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Verified nearest-flip analysis](nearest_flip_analysis.md)
- [Threshold-sensitivity explorer](threshold_sensitivity_explorer.md)
- [Deterministic cross-rule reasoning](cross_rule_reasoning.md)
- [Provenance model](provenance_model.md)
- [Provenance Explorer](provenance_explorer.md)
- [Standalone demo](standalone_demo.md)
- [Reproducibility guide](reproducibility.md)
- [Generated Pydantic schemas](reference/generated/pydantic_schemas.json)
- [TOS Data read-only integration](integration/tos_data_adapter.md)

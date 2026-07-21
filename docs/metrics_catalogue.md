# Metrics Catalogue

TrafficTwin Phase 3 metrics are deterministic functions over Phase 2 canonical records. Metrics never infer absent evidence. When a required table or field is unavailable, the metric result is present with status `unavailable` or `invalid` and a stable reason code.

Metric implementation version: `1.0`.

## Availability Policy

- `available`: required evidence exists and the value was computed.
- `unavailable`: required table or field is absent, no valid rows exist, or the metric does not apply to a single run.
- `partial`: the metric has a usable value but one configured sub-result is unavailable, such as relative delta with a zero baseline.
- `invalid`: source validation rejected the bundle, so metrics are not computed.

Unavailable metrics have `value: null`. JSON outputs must not contain `NaN` or infinity.

In the Phase 4 UI, unavailable metrics are displayed as `Unavailable` with reason codes. They must not be rendered as zero in cards, charts, or tables.

## Fixed-Window Scope

The ordinary core catalogue contains 63 definitions. `MET-01` applies the 60 current single-run
task, infrastructure, traffic, trip, energy, fairness, and contracted spatial/per-RSU definitions
over a versioned fixed-window contract. The three comparison definitions are excluded because they
need two compatible runs rather than one canonical time slice. Each generated `MetricDefinition`
declares `time_window_applicable` and its primary `time_anchor`. An explicitly supplied `MET-06`
registry may add trusted custom definitions for that computation; it does not mutate the global
core catalogue.

| Metric domain | Primary record anchor |
|---|---|
| `task.*` | `tasks.arrival_time_s` |
| `infra.*` | `infrastructure.timestamp_s` |
| `spatial.rsu.task.*` | `tasks.arrival_time_s`; infrastructure independently uses `timestamp_s` |
| `spatial.vehicle.*` | `vehicles.timestamp_s` |
| `traffic.*` | `traffic.timestamp_s` |
| `trip.*` | `trips.departure_time_s` |

For multi-table definitions, every required canonical table is independently filtered: vehicle
records use `vehicles.timestamp_s`, and incident records use `incidents.timestamp_s`. A task's
completed/latency/energy outcome remains with its arrival cohort because `completion_time_s` is
optional and generated/incomplete denominators have no completion event. A trip outcome remains
with its departure cohort because arrival is optional.

Windows are aligned to an origin and use half-open `[start,end)` membership. Empty included
windows retain ordinary metric unavailability instead of becoming zero. Edge-window coverage is
requested-range overlap divided by grid width and does not assert sampling completeness. Means,
ratios, percentiles, distinct/grouped results, Jain indices, traffic coverage, and clipped
saturation sequences generally cannot be recombined into the whole-run result. Full usage and
interpretation rules are in [Time-windowed metrics](time_windowed_metrics.md) and
[ADR-016](decisions/ADR-016-fixed-window-metric-semantics.md).

## Percentiles

Percentiles use deterministic linear interpolation:

```text
rank = (n - 1) * percentile
```

Values are sorted ascending. If `rank` falls between two observations, the result is linearly
interpolated. The method is recorded as `linear-rank-n-minus-1-v1` in percentile metadata. The
task-latency family is P50/P95/P99. With the default `minimum_sample_size=1`, one valid latency
returns that value with an explicit single-observation warning. If a configured minimum is not
met, each task-latency percentile is unavailable with `INSUFFICIENT_SAMPLE_SIZE`; zero valid
latencies use `NO_LATENCY_VALUES`. The mean remains available whenever at least one valid latency
exists. A sample P99 is descriptive and must not be presented as a worst-case or confidence bound.

## Task Metrics

| Key | Formula | Unit | Required evidence |
|---|---|---|---|
| `task.generated.count` | count of valid task records | count | tasks |
| `task.completed.count` | count where `completed` is true | count | tasks |
| `task.completion.rate` | completed valid tasks / generated valid tasks | ratio | tasks |
| `task.incomplete.rate` | incomplete valid tasks / generated valid tasks | ratio | tasks |
| `task.completion.rate_by_class` | completion rate grouped by `T1`, `T2`, `T3`, `unknown` | ratio | tasks |
| `task.completion.rate_by_vehicle_tier` | completion rate grouped by exact stable operational vehicle tier | ratio | tasks, vehicles, fairness policy |
| `task.deadline_miss.completed_observed_rate` | completed tasks with `latency_ms > deadline_ms` / completed tasks with latency and deadline | ratio | tasks |
| `task.latency.count` | count of non-missing non-negative latency observations | count | tasks |
| `task.latency.mean_ms` | arithmetic mean latency | ms | tasks |
| `task.latency.p50_ms` | P50 latency | ms | tasks |
| `task.latency.p95_ms` | P95 latency | ms | tasks |
| `task.latency.p99_ms` | P99 latency | ms | tasks |
| `task.decision.counts` | counts by canonical decision | count | tasks |
| `task.decision_share.local` | local decisions / recognised decisions | ratio | tasks |
| `task.decision_share.v2i` | V2I decisions / recognised decisions | ratio | tasks |
| `task.decision_share.v2v` | V2V decisions / recognised decisions | ratio | tasks |
| `task.decision_share.unknown` | unknown decisions / generated valid tasks | ratio | tasks |
| `task.offload.rate` | V2I plus V2V decisions / recognised decisions | ratio | tasks |
| `task.drops.by_cause` | counts grouped by `drop_reason` | count | tasks with drop reason |
| `task.energy.mean_per_observed_task_j` | mean `energy_j` over eligible energy-observed tasks | J/task | tasks, v1.0 energy contract |
| `task.energy.per_completed_j` | mean `energy_j` over eligible completed tasks | J/task | tasks, v1.0 energy contract |
| `task.energy_delay_product.mean_j_ms` | mean `energy_j * latency_ms` over eligible completed tasks | J*ms/task | tasks, v1.0 energy contract |

Incomplete tasks are not counted as deadline misses in Phase 3. They are reported through `task.incomplete.rate`.

### Task-Energy Admission And Coverage

The three canonical energy metrics are admitted only when `manifest.energy_contract` declares the
exact v1.0 semantics recorded in [ADR-018](decisions/ADR-018-contract-gated-task-energy-metrics.md)
and `files.tasks.units.energy_j` is `J`. An energy column without that semantic contract is not
enough. Results carry the contract fingerprint, eligibility rule, eligible count, population
count, and coverage fraction. Missing values are excluded and never treated as zero. Completed-
task energy and energy-delay product become `partial` when some completed tasks lack eligible
evidence; partial results are not pairwise-compared.

The synthetic generator's values are deterministic modelled energy for software evaluation, not
measured consumption. TOS joules per arrival remains a separate source metric, and the SUMO/TOS
adapters do not claim support for this canonical family.

## Infrastructure Metrics

| Key | Formula | Unit |
|---|---|---|
| `infra.rsu.summary` | per-RSU observation count and available queue/utilisation/arrival/drop/active-task summaries | mixed |
| `infra.observed_rsu.count` | distinct RSU IDs | count |
| `infra.queue_length.mean` | mean queue length over valid observations | tasks |
| `infra.queue_length.max` | maximum queue length | tasks |
| `infra.utilisation.mean` | mean utilisation fraction | fraction |
| `infra.utilisation.p95` | P95 utilisation fraction | fraction |
| `infra.saturation.episode_count` | count of per-RSU maximal saturated sequences | count |
| `infra.saturation.duration_s` | sum of timestamp gaps inside saturated sequences | s |
| `infra.load_balance.jain_capacity_normalised` | Jain index over mean `active_tasks / capacity` by RSU | index |

Saturation uses `MetricEngineConfig.saturation_threshold`, default `0.90`, for synthetic demonstration only. This threshold is configurable and is not treated as a validated research threshold. Last saturated points contribute zero duration unless a next timestamp exists. Gaps larger than `saturation_max_gap_s` split episodes and do not add duration.

Capacity-normalised load balance is governed by the operational-fairness admission policy below,
not merely by the presence of one eligible row.

## Operational Fairness Metrics

| Key | Formula | Unit | Required evidence |
|---|---|---|---|
| `fairness.vehicle_tier.completion_rate.max_gap` | maximum minus minimum completion rate across admitted tiers | ratio-point gap | tasks, exact stable vehicle tiers |
| `fairness.vehicle_tier.completion_rate.jain` | Jain index over admitted tier completion rates | index | tasks, exact stable vehicle tiers |
| `fairness.rsu.capacity_normalised_load.by_group` | mean `active_tasks / capacity` grouped by exact RSU ID | ratio by RSU | infrastructure active tasks and positive capacity |
| `fairness.rsu.capacity_normalised_load.max_gap` | maximum minus minimum per-RSU mean capacity-normalised load | ratio-point gap | infrastructure active tasks and positive capacity |

The existing `task.completion.rate_by_vehicle_tier` and
`infra.load_balance.jain_capacity_normalised` are part of the same six-output family.
`OperationalFairnessPolicy` v1.0 admits results only when at least two operational groups exist,
every observed group has at least two eligible observations, and coverage is complete. A vehicle
tier must be non-empty and stable for the exact vehicle within the scope. An RSU observation must
have non-negative `active_tasks` and positive `capacity`. Under-supported groups are not dropped.

Every result carries the policy version/fingerprint, exact group-set fingerprint, support counts,
eligible and population counts, and coverage. Scalar cross-run comparisons require matching
policy and group-set fingerprints. Grouped dictionaries are not forced into arithmetic deltas.
Jain uses `(sum(x)^2) / (n * sum(x^2))`; an all-zero set is unavailable because the formula is
undefined. Vehicle tiers are operational resource categories only. These metrics make no claim
about protected attributes, demographics, causal fairness, or overall outcome quality. See
[ADR-019](decisions/ADR-019-evidence-gated-operational-fairness.md).

## Spatial And Per-RSU Metrics

| Key | Formula | Unit | Required evidence |
|---|---|---|---|
| `spatial.rsu.task.count_by_target` | count V2I tasks grouped by exact execution-target RSU | count by RSU | tasks, infrastructure, target contract |
| `spatial.rsu.task.completion_rate_by_target` | completed targeted V2I tasks / targeted V2I tasks by RSU | ratio by RSU | tasks, infrastructure, target contract |
| `spatial.rsu.task.deadline_miss.completed_observed_rate_by_target` | completed targeted V2I tasks with `latency_ms > deadline_ms` / completed targeted V2I tasks with observed latency by RSU | ratio by RSU | tasks, infrastructure, target contract |
| `spatial.vehicle.observation_count_by_grid_cell` | vehicle-state observation count by fixed source-frame cell | observations by cell | vehicles, grid contract |
| `spatial.vehicle.distinct_count_by_grid_cell` | distinct vehicle IDs observed by fixed source-frame cell | vehicles by cell | vehicles, grid contract |
| `spatial.vehicle.speed.mean_mps_by_grid_cell` | arithmetic mean eligible vehicle speed by fixed source-frame cell | m/s by cell | vehicles, grid contract |

`TaskRsuTargetContract` v1.0 declares that `target_id` on a canonical V2I task is its observed
executing RSU. Every in-scope V2I task must have a non-empty target that exactly matches an
in-scope canonical `infrastructure.rsu_id`; otherwise all three task-target outputs are unavailable.
Local/V2V tasks are outside the denominator. Deadline-miss groups retain the ordinary completed-
observed denominator, and missing group latency becomes partial/null rather than zero.

`VehicleSpatialGridContract` v1.0 declares vehicle-position-at-observation semantics, a named
source coordinate frame, metre units, fixed origin and cell dimensions, and floor-based cell
assignment. Every in-scope vehicle observation needs finite x/y before any grid output is admitted.
Speed can be partial when coordinates are complete but speed is absent. These cells are not
latitude/longitude or geographic areas without separate CRS evidence.

Existing `infra.rsu.summary` and `fairness.rsu.capacity_normalised_load.by_group` supply per-RSU
load evidence without duplicating it under a new key. Every new metric carries contract and exact
group/cell-set fingerprints, support, and coverage. TrafficTwin does not infer task positions,
nearest RSUs, routes, missing targets, or causality. See
[ADR-020](decisions/ADR-020-contract-gated-spatial-and-rsu-breakdowns.md).

## Trusted Custom Metric Plugins

`MET-06` admits reviewed local Python functions only through an explicit `MetricPluginRegistry`.
Every `plugin.<plugin_id>.*` metric declares a complete definition, canonical table/field inputs,
row handling, minimum eligible support, unit, scope, version, closed scalar/grouped output schema,
unavailable behavior, time anchor where applicable, and declared-input-row provenance mapping.

The engine filters and deep-copies declared canonical inputs, invokes each function twice, compares
canonical outputs, validates finite JSON-safe values, and constructs the ordinary `MetricValue`.
Availability failure, exceptions, unequal repeated outputs, invalid output, or deliberate
unavailability remain explicit and isolated from core/other plugin metrics. A scalar comparison
also requires equal complete contract fingerprints.

This is a trusted extension API, not a sandbox or plugin marketplace. TrafficTwin does not load
uploaded Python or arbitrary module paths. Full authoring and usage details are in
[Custom metric plugins](custom_metric_plugins.md) and
[ADR-021](decisions/ADR-021-trusted-local-custom-metric-plugin-api.md).

## Traffic Metrics

| Key | Formula | Unit |
|---|---|---|
| `traffic.observation.count` | count of valid traffic observations | count |
| `traffic.count.total` | sum of `count` | vehicles |
| `traffic.count.mean` | mean count per observation | vehicles |
| `traffic.speed.mean_mps` | mean average speed | m/s |
| `traffic.speed.p50_mps` | P50 average speed | m/s |
| `traffic.speed.p95_mps` | P95 average speed | m/s |
| `traffic.speed.min_mps` | minimum average speed | m/s |
| `traffic.time_coverage` | first timestamp, last timestamp, and last minus first | s |
| `traffic.sensor.count` | distinct sensor IDs | count |

Traffic count semantics are preserved as declared source observations; Phase 3 does not infer whether counts are point counts or interval totals.

## Trip Metrics

| Key | Formula | Unit |
|---|---|---|
| `trip.records.count` | total trip records | count |
| `trip.completed.count` | trips with arrival or valid duration evidence | count |
| `trip.incomplete.count` | total minus completed | count |
| `trip.completion.rate` | completed / total | ratio |
| `trip.duration.count` | count of valid durations | count |
| `trip.duration.mean_s` | mean duration | s |
| `trip.duration.p50_s` | P50 duration | s |
| `trip.duration.p95_s` | P95 duration | s |
| `trip.duration.min_s` | minimum duration | s |
| `trip.duration.max_s` | maximum duration | s |

Explicit `duration_s` is used when present. Otherwise duration is derived as `arrival_time_s - departure_time_s` only when both fields exist and validation accepted the record.

## Comparison Definitions

Comparison reports use:

- `absolute_delta = variation - baseline`
- `relative_delta = (variation - baseline) / abs(baseline)`
- `comparison.seed_aligned_difference` for same-experiment, same-random-seed paired runs where required.

If baseline is zero and variation is zero, relative delta is `0`. If baseline is zero and variation is non-zero, relative delta is unavailable with `BASELINE_ZERO`. Infinity is never emitted.

## Experiment-Level Metrics

The experiment research layer builds a first-class experiment EvidencePack from stored run-level
MetricCollections. It may contain:

- `experiment.algorithm.count`
- `experiment.cross_algorithm_dispersion`
- `experiment.always_local_gap_from_best`
- `experiment.pressure.indicator`
- `experiment.training_validation.pair_count`
- `experiment.training_validation.max_absolute_gap`
- `experiment.training_validation.mean_absolute_gap`
- `experiment.training_validation.mean_signed_gap`

The first four values support R3. The training-validation values support R5 only when the caller
supplies explicit pairs. They are not produced by the single-run metric engine, so ordinary
bundle-derived EvidencePacks return R3 and R5 as `insufficient_evidence`.

## TOS Source-Summary Definitions

The optional TOS result reader adds two source-specific definitions outside the Phase 3 canonical
calculator catalogue:

| Key | Definition | Unit |
|---|---|---|
| `tos.task.deadline_success.rate` | source-reported arrivals meeting their deadline / source arrivals | ratio |
| `tos.task.deadline_success.rate_by_class` | the same source outcome grouped by T1/T2/T3 | ratio |

These names prevent source deadline success from being presented as TrafficTwin
`task.completion.rate`, whose definition is physical completion over valid canonical task records.
The values carry the distinct implementation version
`tos-source-summary-v2_post_nrsus_fix-1.0`, source-row metadata, and a warning that they were not
recomputed from canonical rows. Existing diagnostic rules are unchanged and do not treat these
source-specific keys as physical-completion evidence.

## Related Documents

- [Data contract](data_contract.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Comparison methodology](comparison_methodology.md)
- [Diagnostic rules](diagnostic_rules.md)
- [Generated metric catalogue](reference/generated/metric_catalogue.json)
- [Time-windowed metrics](time_windowed_metrics.md)
- [TOS Data read-only integration](integration/tos_data_adapter.md)
- [Experiment research tools](experiment_research_tools.md)

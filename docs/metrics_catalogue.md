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

## Percentiles

Percentiles use deterministic linear interpolation:

```text
rank = (n - 1) * percentile
```

Values are sorted ascending. If `rank` falls between two observations, the result is linearly interpolated. One value returns that value. Zero values make the metric unavailable unless the metric is an observation count.

## Task Metrics

| Key | Formula | Unit | Required evidence |
|---|---|---|---|
| `task.generated.count` | count of valid task records | count | tasks |
| `task.completed.count` | count where `completed` is true | count | tasks |
| `task.completion.rate` | completed valid tasks / generated valid tasks | ratio | tasks |
| `task.incomplete.rate` | incomplete valid tasks / generated valid tasks | ratio | tasks |
| `task.completion.rate_by_class` | completion rate grouped by `T1`, `T2`, `T3`, `unknown` | ratio | tasks |
| `task.completion.rate_by_vehicle_tier` | completion rate grouped by vehicle tier | ratio | tasks, vehicles |
| `task.deadline_miss.completed_observed_rate` | completed tasks with `latency_ms > deadline_ms` / completed tasks with latency and deadline | ratio | tasks |
| `task.latency.count` | count of non-missing non-negative latency observations | count | tasks |
| `task.latency.mean_ms` | arithmetic mean latency | ms | tasks |
| `task.latency.p50_ms` | P50 latency | ms | tasks |
| `task.latency.p95_ms` | P95 latency | ms | tasks |
| `task.decision.counts` | counts by canonical decision | count | tasks |
| `task.decision_share.local` | local decisions / recognised decisions | ratio | tasks |
| `task.decision_share.v2i` | V2I decisions / recognised decisions | ratio | tasks |
| `task.decision_share.v2v` | V2V decisions / recognised decisions | ratio | tasks |
| `task.decision_share.unknown` | unknown decisions / generated valid tasks | ratio | tasks |
| `task.offload.rate` | V2I plus V2V decisions / recognised decisions | ratio | tasks |
| `task.drops.by_cause` | counts grouped by `drop_reason` | count | tasks with drop reason |
| `task.energy.per_completed_j` | mean `energy_j` over completed tasks | J/task | tasks with energy |

Incomplete tasks are not counted as deadline misses in Phase 3. They are reported through `task.incomplete.rate`.

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

Capacity-normalised load balance is unavailable unless both `capacity` and `active_tasks` are present with compatible units.

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

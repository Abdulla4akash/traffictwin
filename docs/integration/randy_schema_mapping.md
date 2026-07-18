# Randy/VEC Schema Mapping

Discovery date: 2026-07-18

External package: `external/tos-data`

Status: read-only summary/replay integration implemented; full canonical conversion is not
implemented.

## Boundary

The TOS package is not a TrafficTwin run bundle. `traffictwin.integration.tos` reads documented
evaluation summaries and selected NPZ arrays directly. It does not add Randy-specific behavior to
the generic CSV adapter and does not bypass the standard canonical pipeline for other bundles.

Two outputs are deliberately different:

1. **Source-summary results** use `MetricCollection` for comparison, aggregation, evidence, and
   provenance. They carry a distinct implementation version and are labelled not recomputed.
2. **Instrumented source views** expose bounded replay frames and task samples. They are not
   canonical records and do not feed Phase 3 formulas.

## Source Mapping

| Source | Confirmed meaning | Current target | Current policy |
|---|---|---|---|
| `evals/eval_results_master.csv` identity columns | campaign, scenario cell, fleet, fleet seed, actor, observation variant, trace, engine | `Experiment`, `Run`, metric provenance | register idempotently; no fabricated seed snapshot |
| `completion`, `t1/2/3_completion` | fraction of arrivals meeting deadline | `tos.task.deadline_success.rate` and `tos.task.deadline_success.rate_by_class` | source-specific definitions; not mapped to TrafficTwin physical completion |
| `avg_latency_ms_per_task` | mean ms over all arrivals, including misses/backlog | `task.latency.mean_ms` source summary | available; no P50/P95 inference |
| `p_local`, `p_v2i`, `p_v2v` | action shares | decision-share/offload source summaries | available after sum-to-one validation |
| `avg_energy_j_per_task` | joules per arrival | provenance metadata only | not mapped to energy per completed task |
| `T`, `maxN` | trace duration seconds and padded vehicle-slot count | run/metric metadata | preserve |
| instrumented JSON | matched run summary, tier histogram, total tasks, wall time, RSU bound | validation/reconciliation | reconcile with master; do not create canonical rows |
| per-step `times`, arrivals, `done`, latency sum, active, action counts | per-second aggregate source evidence | `TosReplayPoint` | `done` is labelled deadline met |
| per-step vehicle arrays | action, arrivals, deadline-met count, queue delay per padded slot | `TosVehicleSlotState` | join only at same timestamp and slot |
| per-step `rsu_load`, `rsu_busy_ms` | exact semantics unresolved | `TosRsuSourceState` | raw display only; excluded from metrics/rules |
| per-task `task_active` | valid arrival mask | sample inclusion | include true entries only |
| per-task `task_type` | `0 -> T1`, `1 -> T2`, `2 -> T3` by exhaustive result consistency | `TosTaskObservation.task_class` | bounded inspection only |
| per-task `task_lat_ms` | task latency in ms | `TosTaskObservation.latency_ms` | preserve |
| per-task `task_met` | deadline success by exhaustive deadline consistency | `TosTaskObservation.deadline_met` | never call eventual completion |
| trace positions/speed/mask | time-aligned padded mobility state | replay source view | retain source units; no canonical unit conversion |
| trace `rsu_xy` | RSU source coordinates | replay source view | retain source units |

## Empirical Checks

The complete supplied package was checked, not only a screenshot or one row:

- 300 evaluation rows parse under one 20-column contract;
- all use engine `v2_post_nrsus_fix`;
- 60 per-step files share the required keys and dimensions;
- 6 per-task files share the required keys and dimensions;
- 5 trace files share the required keys and dimensions;
- instrumented JSON values reconcile with matching evaluation rows;
- all active per-task entries support `0/1/2` as T1/T2/T3;
- every active `task_met` equals `task_lat_ms <= deadline` using 100 ms for T1/T3 and 500 ms for
  T2.

These checks support deterministic parsing. They do not prove a physical model or replace source
author confirmation for dissertation interpretation.

## Source-Summary Metric Availability

Available:

- `tos.task.deadline_success.rate`;
- `tos.task.deadline_success.rate_by_class`;
- `task.latency.mean_ms`;
- local/V2I/V2V/unknown decision shares;
- `task.offload.rate`.

Unavailable:

- generated and completed counts;
- TrafficTwin `task.completion.rate` and `task.completion.rate_by_class`;
- eventual incomplete rate;
- completed-task deadline-miss denominator;
- latency count/P50/P95;
- decision counts;
- energy per completed task;
- drops;
- infrastructure, traffic, trip, and comparison-placeholder metrics.

The imported collection version is `tos-source-summary-v2_post_nrsus_fix-1.0`. Comparisons require
matching experiments, fleet seeds, versions, and units under existing Phase 3 policies.

## Vehicle Slot Finding

Trace and per-step arrays align by `[T,N]`, but inspection shows padded slots can disappear,
reappear, and represent different physical vehicles. TrafficTwin therefore uses references such
as `slot:7@time-index:120`; it does not construct `vehicle_id=veh_7` across the full trace.

## Unresolved RSU Mapping

`rsu_busy_ms` can exceed 1,000 during one one-second observation, so dividing by 1,000 would be
invalid. `rsu_load` may be zero despite V2I decisions and behaves differently under incident load.
`rsu_max_concurrent` resembles an internal array/service bound, but physical capacity semantics are
not evidenced.

Consequently TrafficTwin does not map these fields to:

- queue length;
- active tasks;
- utilisation fraction;
- capacity;
- saturation episodes;
- load balance;
- R2 evidence.

## Unsupported Or Absent Evidence

- per-vehicle tier;
- link quality and action availability;
- V2I target RSU and V2V target vehicle;
- trip or journey-time records;
- raw SUMO config/XML outputs;
- checkpoint files;
- a tested execution command.

## Future Canonical Conversion

A future converter should first target one matched showcase and write a standard run bundle. It
must preserve source array indices, distinguish deadline success from eventual completion, map
only confirmed units, and pass the existing Phase 2 validator. It must not retrofit ambiguous RSU
fields into the generic adapter.

## Remaining Questions

1. What exactly are `rsu_load`, `rsu_busy_ms`, and `rsu_max_concurrent`?
2. What are the confirmed coordinate and speed units?
3. Is late physical completion represented separately?
4. Are vehicle tier, action availability, link quality, or action targets available elsewhere?
5. Are trip/SUMO outputs available?
6. Which sanitised samples may be committed?
7. What tested command produced the outputs?

## Related Documents

- [TOS Data integration](tos_data_adapter.md)
- [Artifact inventory](randy_artifact_inventory.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)
- [Phase 6 decision](phase6_decision.md)

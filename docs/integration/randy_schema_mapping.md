# Randy/VEC Schema Mapping

Discovery date: 2026-07-18

External data package inspected: `external/tos-data`

Status: discovery only. No TrafficTwin adapter has been implemented.

## Mapping Status

Randy's `TOS Data` package provides confirmed source schemas for evaluation summaries,
instrumented per-step arrays, instrumented per-task arrays, and Manchester mobility traces.

These schemas are not yet TrafficTwin run bundles. They require an adapter/converter that creates
standard TrafficTwin bundle files and manifest metadata before Phase 2 validation, Phase 3 metrics,
Phase 5 diagnostics, and provenance can run.

The generic CSV adapter must remain generic. Randy-specific NPZ/summary behavior should live in a
future adapter-specific module.

## Confirmed Source-To-Canonical Candidates

| Source | Source fields | Confirmed units/semantics | Candidate canonical target | Transformation | Unresolved ambiguity | Status |
|---|---|---|---|---|---|---|
| `evals/eval_results_master.csv` | `campaign`, `cell`, `eval_fleet`, `fleet_seed`, `actor`, `obs_variant`, `completion`, `t1_completion`, `t2_completion`, `t3_completion`, `avg_energy_j_per_task`, `avg_latency_ms_per_task`, `p_local`, `p_v2i`, `p_v2v`, `fleet_ev_share`, `T`, `maxN`, `trace`, `engine_version` | Fractions for completion/action shares; J/task; ms/task; `T` seconds; `maxN` padded vehicles | Experiment summary / metric reconciliation, not raw canonical rows | Preserve as external summary or convert to precomputed metric references only with explicit labelling | It cannot produce row-level `TaskRecord`, `InfrastructureRecord`, `TripRecord`, or source-row provenance by itself | confirmed source schema; not enough for canonical raw records |
| `instrumented/json/*.json` | Summary keys overlapping master CSV plus `total_tasks`, `rsu_max_concurrent`, `wall_s`, `fleet_tier_hist`, `trace` | Summary values documented; same physics as instrumented NPZ | Run summary/provenance and reconciliation | Use to cross-check converted NPZ outputs and populate manifest/run metadata | Not row-level; `rsu_max_concurrent` meaning as capacity needs confirmation | confirmed source schema |
| `instrumented/perstep/*_perstep.npz: times` | `times[T]` | seconds according to dictionary's per-second description | canonical timestamps | Use as `timestamp_s` for infrastructure/vehicle/event rows | Need confirm exact start time/window relation | confirmed enough for relative timestamps |
| `instrumented/perstep/*_perstep.npz: arrivals/done/active` | `arrivals[T]`, `done[T]`, `active[T]` | per-second aggregate counts | aggregate evidence, possible task event table extension | Can support arrivals/completions timeline; not individual task records | Current canonical model has no aggregate task-time record | partial |
| `instrumented/perstep/*_perstep.npz: n_local/n_v2i/n_v2v` | `n_local[T]`, `n_v2i[T]`, `n_v2v[T]` | per-second action counts | aggregate decision evidence | Can support action-share time series or validate task decision shares | Not individual task decisions | partial |
| `instrumented/perstep/*_perstep.npz: veh_action` | `veh_action[T,N]`, values 0/1/2 | dictionary maps 0=L, 1=V2I, 2=V2V | vehicle action/state evidence | Map to vehicle-state auxiliary attributes or aggregate action counts | Current `VehicleStateRecord` has no action field; task-level causality not implied | partial |
| `instrumented/perstep/*_perstep.npz: veh_k/veh_done/veh_queue_ms` | `veh_k[T,N]`, `veh_done[T,N]`, `veh_queue_ms[T,N]` | arrivals/completions/queue backlog per vehicle; ms implied | vehicle/task pressure evidence | Can support replay and queue context | Vehicle ID slot semantics and tier mapping are absent | partial |
| `instrumented/perstep/*_perstep.npz: rsu_busy_ms` | `rsu_busy_ms[T,R]` | busy milliseconds implied by name | `InfrastructureRecord.utilisation_fraction` candidate | Possibly divide by timestep milliseconds to get fraction | Must confirm denominator and clipping policy before mapping as utilisation | unknown conversion |
| `instrumented/perstep/*_perstep.npz: rsu_load` | `rsu_load[T,R]` | per-RSU load; exact meaning not defined in discovered docs | `InfrastructureRecord.queue_length` or `active_tasks` candidate | Map only after Randy confirms whether this is queue length, active tasks, workload, or another count | Queue semantics unknown | unknown conversion |
| `instrumented/pertask/*_pertask.npz: task_active` | `task_active[T,5,N]` | active task mask | Task row inclusion | Generate one task row per true element | Need stable task ID construction policy for converted bundles | partial |
| `instrumented/pertask/*_pertask.npz: task_type` | `task_type[T,5,N]` | task type, deadline classes described in dictionary | `TaskRecord.task_class` | Map integer labels to T1/T2/T3 only after exact encoding confirmed | Whether values are 0/1/2 or 1/2/3 must be confirmed | unknown conversion |
| `instrumented/pertask/*_pertask.npz: task_lat_ms` | `task_lat_ms[T,5,N]` | latency in ms | `TaskRecord.latency_ms` | Copy for active task rows | Whether latency includes missed/backlog semantics needs preservation in metadata | partial |
| `instrumented/pertask/*_pertask.npz: task_met` | `task_met[T,5,N]` | deadline-met boolean | `TaskRecord.completed` candidate or separate deadline-met field | TrafficTwin currently models `completed`; mapping `task_met` to completed needs design note because deadline met is not identical to physical completion in all systems | completion semantics need confirmation | partial |
| `traces/trace_*_fullrsu.npz` | `pos_x`, `pos_y`, `speed`, `mask`, `rsu_xy`, `times`, `dt`, `maxN`, `T`, `window`, `sumo_seed` | trace arrays documented; exact units for position/speed not explicitly confirmed in package docs | `VehicleStateRecord`, RSU placement provenance | Join with per-step vehicle arrays on T,N; use mask to include valid vehicle rows | Coordinate system and speed units need confirmation | partial |

## Unsupported Or Not Found

| Desired evidence | Status | Impact |
|---|---|---|
| SUMO `.sumocfg`, `.net.xml`, `.rou.xml`, detector, queue, summary, FCD XML, or `tripinfo.xml` | not present | SUMO XML adapters remain unsupported. |
| Trip/journey-time records | not present | Real journey-time metrics remain unavailable. |
| Per-vehicle tier labels | not found | R1 cannot directly evaluate T1 misses on low-tier vehicles. |
| Link quality/action availability | not found | R1 alternatives remain unresolved. |
| Explicit RSU capacity configuration | not found in data package | Capacity-normalised load balance remains unavailable unless capacity can be derived with confirmation. |
| Headless command/API/script | not present | Direct launch remains disabled. |
| Checkpoint files | not present | Checkpoints can be referenced by path/hash in provenance but not executed. |

## Adapter Direction For Future Phase 6B

The safest first adapter would be an offline converter, not a launcher:

```text
external/tos-data selected run artifacts
    -> adapter-specific validation
    -> generated TrafficTwin run bundle
    -> existing Phase 2 validator
    -> existing canonical records
    -> existing metrics/evidence/diagnostics/provenance
```

Recommended first target:

1. A single showcase run with matching files:
   - `instrumented/pertask/baseline_uk2030_wd_am_fs0_pertask.npz`
   - `instrumented/perstep/baseline_uk2030_wd_am_fs0_perstep.npz`
   - `traces/trace_wd_am_fullrsu.npz`
   - matching `instrumented/json/baseline_uk2030_wd_am_fs0.json`
2. Convert only confirmed fields:
   - task latency and deadline-met evidence from per-task NPZ;
   - per-RSU timestamps and load/busy fields after unit confirmation;
   - vehicle coordinates/speed after unit confirmation;
   - run metadata from JSON and filename conventions.
3. Leave trip metrics unavailable unless Randy supplies trip outputs.

## Required Questions Before Coding

Ask Randy to confirm:

1. Integer encoding for `task_type`.
2. Whether `task_met` means task completed by deadline, physical completion, or both.
3. Whether `task_lat_ms` includes backlog values for missed tasks and how those should be interpreted.
4. Exact unit and denominator for `rsu_busy_ms`.
5. Exact meaning of `rsu_load`.
6. Position and speed units in trace NPZ files.
7. Whether vehicle slot index is a stable vehicle ID within a trace.
8. Whether per-vehicle tier labels are available anywhere.
9. Whether any trip/journey-time outputs exist outside this package.
10. Whether small sanitised NPZ/CSV fixtures from this package may be committed to TrafficTwin tests.


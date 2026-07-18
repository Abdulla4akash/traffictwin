# Randy/VEC Artifact Inventory

Discovery date: 2026-07-18

TrafficTwin root inspected: `diss/`

External data package inspected: `external/tos-data`

External data package commit: `d27294ef5213e6a20f55632448bd20f5a76a45ab`

## Discovery Method

Randy granted GitLab access to the `TOS Data` project. The repository was cloned outside
TrafficTwin under `external/tos-data` so the TrafficTwin repository remains separate from the
external data package.

Discovery inspected:

- package README and data dictionary;
- training/evaluation convention records;
- file tree, extensions, and sizes;
- CSV headers and row counts;
- JSON summary keys;
- NPZ array keys, shapes, and dtypes.

No raw data files were copied into `diss/`. No adapter code was implemented. No source files in
Randy's repository were modified.

## Summary Finding

Real Randy/VEC result artifacts are now available for discovery. They are not TrafficTwin run
bundles yet.

The package contains:

- an evaluation master CSV with 300 evaluation-run summary rows;
- 66 training-curve CSV files;
- 65 final greedy-evaluation JSON files;
- 60 per-step instrumented NPZ files;
- 6 per-task instrumented NPZ files;
- 60 instrumented summary JSON files;
- 5 Manchester mobility trace NPZ files;
- 8 training-record Markdown files plus data conventions.

The package does not contain:

- the `vec_env` source-code repository;
- documented reproduction commands from `vec_env/docs/REPRODUCING.md`;
- SUMO `.sumocfg`, network, route, detector, tripinfo, queue, or summary XML files;
- direct launch scripts or job scripts that TrafficTwin can execute;
- model checkpoint files.

Therefore Phase 6B adapter work is now plausible for offline import/conversion, but direct launch
remains unsupported.

## Source Inventory

| Source name | Producer | Purpose | Format | Canonical target | Source schema | Units/status | Row or shape summary | Current metric sufficiency | R1 sufficiency | R2 sufficiency | R3 sufficiency |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `README.md` | Randy/TOS Data package | Package overview and provenance pointer | Markdown | Documentation/provenance | n/a | Engine version confirmed as `v2_post_nrsus_fix`; older pre-2026-07-16 outputs superseded | n/a | n/a | n/a | n/a | n/a |
| `DATA_DICTIONARY.md` | Randy/TOS Data package | Schemas, caveats, reference values, suggested views | Markdown | Mapping evidence | n/a | Several meanings confirmed; some array units still need clarification | n/a | supports adapter design | partial | partial | partial |
| `evals/eval_results_master.csv` | Randy evaluation process | Tidy long evaluation summary, one row per evaluation run | CSV | External summary metrics / experiment overview, not raw canonical records | `campaign`, `cell`, `eval_fleet`, `fleet_seed`, `actor`, `obs_variant`, completion fields, energy, latency, action shares, `T`, `maxN`, `trace`, `engine_version` | Completion fractions, energy J/task, latency ms/task, action shares, trace length seconds; confirmed by dictionary | 300 rows | useful for dashboard/reconciliation; should not be treated as raw task records | partial, lacks per-task low-tier cross-tab | weak, no RSU time series | strong summary evidence for multi-campaign comparison if represented carefully |
| `training/*.csv` | Randy training process | Per-update training curves | CSV | Training provenance / optional learning-curve view | `update`, `env_step`, `mean_return`, `mean_completion`, action shares, energy, latency, per-type completion, `elapsed_s`, `sps` | Training-distribution metrics; not directly comparable to eval CSV | 66 files, 781 rows each | not a Phase 3 run-metric source without a training-curve adapter | no | no | partial, training stability context only |
| `training/*_greedy_eval.json` | Randy training process | Final greedy evaluation on training distribution | JSON | Training provenance / optional summary | `mean_completion`, `std_completion`, per-type completion, action shares, energy, latency, elapsed time, episode count | Training distribution only | 65 files, common schema | not comparable 1:1 with eval CSV | no | no | partial, training stability context only |
| `training/*.machine.txt` | Randy training process | Machine provenance for selected runs | text key-value | Run/training provenance | `machine`, `host`, `gpu`, `end`, `wall_s`, `concurrency` where present | wall-clock seconds | 13 files | provenance only | no | no | no |
| `records/TRAINING_*.md` | Randy training process | Formal training records per variant | Markdown | Experiment/provenance mapping | free text with checkpoint paths, seeds, machine notes, flags | Confirms some environment variables and flags, not executable command contract | 8 files | supports experiment metadata | partial | partial | partial |
| `records/DATA_CONVENTIONS.md` | Randy/TOS Data package | Campaign naming and contamination labelling | Markdown | Experiment metadata and interpretation constraints | n/a | Confirms campaign/cell/fleet naming rules | n/a | supports grouping | partial | partial | yes for grouping labels |
| `instrumented/json/*.json` | Randy instrumented evaluation writer | Summary JSON for instrumented runs | JSON | External summary/provenance | `T`, `actor`, completion fields, action shares, `fleet`, `trace`, `rsu_max_concurrent`, `total_tasks`, `wall_s`, etc. | Completion fractions, action shares, latency ms/task, energy J/task | 60 files | useful summary; not raw canonical rows | partial | partial only with paired NPZ | partial |
| `instrumented/perstep/*_perstep.npz` | Randy instrumented evaluation writer | Per-second aggregates, per-vehicle action/queue arrays, per-RSU state arrays | NPZ | `InfrastructureRecord`, `VehicleStateRecord` with trace join, aggregate task-time evidence | keys: `times`, `arrivals`, `done`, `lat_sum`, `active`, `n_local`, `n_v2i`, `n_v2v`, `veh_action`, `veh_k`, `veh_done`, `veh_queue_ms`, `rsu_busy_ms`, `rsu_load` | `times` seconds confirmed by dictionary; `veh_queue_ms`/`rsu_busy_ms` imply ms but utilisation conversion must be confirmed | 60 files; T varies by cell, vehicle slots vary 139-2488, RSUs 9-12 | strong for time-series and infrastructure after adapter | partial, no vehicle tier per slot found | promising, needs `rsu_busy_ms` and `rsu_load` semantics | no |
| `instrumented/pertask/*_pertask.npz` | Randy instrumented evaluation writer | Full per-arrival task logs for showcase runs | NPZ | `TaskRecord` candidate | keys: `task_type`, `task_lat_ms`, `task_met`, `task_active`; arrays `[T, K_MAX=5, N]` | latency ms confirmed by key/dictionary; task type label mapping likely T1/T2/T3 but needs exact code mapping | 6 files | strong for task metrics on 6 showcase runs after adapter | partial, lacks vehicle-tier evidence | partial when joined to perstep | no |
| `traces/trace_*_fullrsu.npz` | Randy/SUMO trace generation | Manchester mobility traces and RSU coordinates | NPZ | `VehicleStateRecord`, environment/scenario provenance | keys: `pos_x`, `pos_y`, `speed`, `mask`, `rsu_xy`, `times`, `dt`, `maxN`, `T`, `window`, `sumo_seed` | Timestamp seconds inferred/confirmed by T and dictionary; position/speed coordinate units need confirmation | 5 files | strong for replay/vehicle state after adapter; not trip metrics | no | no | no |

## Confirmed Campaign And Scenario Dimensions

From `evals/eval_results_master.csv`:

| Dimension | Values |
|---|---|
| Campaigns | `baseline`, `capscalar_ippo`, `capscalar_mappo`, `fcdtrain_manwe_mappo`, `fcdtrain_manwe_mappo_s102`, `gridlocktrain_ft_ippo`, `gridlocktrain_ft_mappo`, `gridlocktrain_ippo`, `gridlocktrain_mappo`, `ukfleettrain_ippo`, `ukfleettrain_mappo` |
| Cells | `wd_am`, `wd_pm`, `we`, `ev`, `inc` |
| Evaluation fleets | `synthetic`, `uk2030` |
| Engine version | `v2_post_nrsus_fix` for all 300 rows |
| Replication unit | `fleet_seed` 0-4 according to the data dictionary |

## Confirmed Per-Step NPZ Schema

The per-step schema is stable by key set. Shapes vary with the Manchester cell:

| Key | Shape pattern | Dtype | Meaning from dictionary | Mapping note |
|---|---:|---|---|---|
| `times` | `[T]` | `float32` | per-second timestamps | `timestamp_s` candidate |
| `arrivals` | `[T]` | `int32` | per-second task arrivals | aggregate task event evidence |
| `done` | `[T]` | `int32` | per-second completed tasks | aggregate task event evidence |
| `lat_sum` | `[T]` | `float32` | latency sum | unit likely ms but needs confirmation |
| `active` | `[T]` | `int32` | active tasks | infrastructure/task pressure evidence |
| `n_local` | `[T]` | `int32` | local action count | action-share evidence |
| `n_v2i` | `[T]` | `int32` | V2I action count | action-share evidence |
| `n_v2v` | `[T]` | `int32` | V2V action count | action-share evidence |
| `veh_action` | `[T,N]` | `int8` | 0=local, 1=V2I, 2=V2V | vehicle action trace, not task-level decision by itself |
| `veh_k` | `[T,N]` | `int8` | vehicle arrivals | vehicle-level aggregate |
| `veh_done` | `[T,N]` | `int16` | vehicle completed tasks | vehicle-level aggregate |
| `veh_queue_ms` | `[T,N]` | `float32` | vehicle queue backlog in ms | queue evidence, not current canonical queue field |
| `rsu_busy_ms` | `[T,R]` | `float32` | per-RSU busy time | possible utilisation numerator; conversion needs confirmation |
| `rsu_load` | `[T,R]` | `int32` | per-RSU load | queue/active-task semantics need confirmation |

## Confirmed Per-Task NPZ Schema

| Key | Shape pattern | Dtype | Meaning from dictionary | Mapping note |
|---|---:|---|---|---|
| `task_type` | `[T,5,N]` | `int8` | task type | needs exact integer-to-T1/T2/T3 mapping |
| `task_lat_ms` | `[T,5,N]` | `float32` | task latency in ms | maps to `latency_ms` where `task_active` true |
| `task_met` | `[T,5,N]` | `bool` | deadline met | maps to completion/deadline outcome policy after confirmation |
| `task_active` | `[T,5,N]` | `bool` | valid task arrival mask | rows where false should not become task records |

## Confirmed Trace NPZ Schema

| Key | Shape pattern | Dtype | Mapping note |
|---|---:|---|---|
| `pos_x` | `[T,N]` | `float32` | vehicle x coordinate; unit needs confirmation |
| `pos_y` | `[T,N]` | `float32` | vehicle y coordinate; unit needs confirmation |
| `speed` | `[T,N]` | `float32` | vehicle speed; unit needs confirmation |
| `mask` | `[T,N]` | `bool` | active/valid vehicle position mask |
| `rsu_xy` | `[R,2]` | `float32` | RSU coordinates; unit needs confirmation |
| `times` | `[T]` | `float32` | trace timestamp candidate |
| `dt` | scalar | `float32` | timestep length |
| `maxN` | scalar | `int32` | padded vehicle-slot count |
| `T` | scalar | `int32` | trace length |
| `window` | scalar string | unicode | source window label |
| `sumo_seed` | scalar | `int32` | SUMO trace seed |

## Initial Sufficiency Assessment

| TrafficTwin area | Evidence status | Notes |
|---|---|---|
| Task metrics | partially confirmed | Six per-task NPZ files can likely be converted to task records after task-type and completion semantics are confirmed. Other runs only have aggregate task counts unless per-task extraction is provided. |
| Infrastructure metrics | partially confirmed | Per-RSU arrays exist in 60 per-step files. `rsu_busy_ms` and `rsu_load` semantics must be confirmed before utilisation/queue mapping. |
| Traffic observations | partial/unknown | Mobility traces provide vehicle positions and speed, not detector-style traffic observations. Aggregating speeds would be a new adapter decision and needs unit confirmation. |
| Trip metrics | unsupported | No `tripinfo`, trip table, or journey-time output was found. |
| R1 under-offloading | partial | T1 outcomes and action shares are available in summaries; per-task detail exists for 6 runs. Vehicle-tier per-task/per-vehicle evidence and action availability are not found. |
| R2 infrastructure bottleneck | partial | Per-RSU state and task outcomes can potentially be aligned for showcase runs, but units and semantics must be confirmed. |
| R3 scenario triviality | partial | Master CSV provides multiple campaigns, policies, cells, and fleet seeds. A TrafficTwin-compatible experiment-level evidence representation would be needed before R3 can consume it. |
| Direct launch | unsupported | Data package points to a separate `vec_env` repository; no command contract is present here. |
| SUMO adapter | unsupported | Trace NPZ files are present, but raw SUMO XML/config outputs are not present. |

## Privacy And Repository Policy

Do not commit Randy's raw files into `diss/` until Randy confirms what can be used as small
sanitised fixtures. The current discovery docs record schemas and counts only.


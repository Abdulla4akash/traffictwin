# Randy/VEC Schema Mapping

Status: evidenced read-only integration; no full canonical conversion.

## Boundary

`traffictwin.integration.tos` is a source-specific adapter around the inspected TOS package. It
does not add Randy-specific assumptions to the generic CSV adapter. Source summaries become
explicitly labelled `MetricCollection` values; instrumented arrays remain bounded source views.
Neither path pretends that the TOS package is a standard TrafficTwin run bundle.

The machine-readable contract is returned by:

```bash
traffictwin integration tos contract --format json
```

Its semantics source is `vec_env` commit
`e98441196270b8fd4cc0eede892df4a0053b2185`. This is interpretation evidence, not a per-run
producer commit.

## Evaluation Summary Mapping

| Source | TrafficTwin target | Policy |
|---|---|---|
| campaign/cell/fleet/fleet seed/actor | `Experiment`, `Run`, source scenario reference | Preserve source identity; do not fabricate a seed snapshot |
| `completion`, `t1_completion`, `t2_completion`, `t3_completion` | `tos.task.deadline_success.rate` and `.rate_by_class` | Source-defined deadline success, not physical completion |
| `avg_latency_ms_per_task` | `task.latency.mean_ms` | Compatible unit and denominator; marked source-provided |
| `p_local`, `p_v2i`, `p_v2v` | decision-share and offload metrics | Validate fractions and sum-to-one |
| `avg_energy_j_per_task` | provenance metadata | Joules per arrival is not energy per completed task |
| `T`, `maxN`, trace, engine | metric/run provenance | `maxN` is peak padded slots, not unique vehicle count |

The source metric version remains
`tos-source-summary-v2_post_nrsus_fix-1.0`; the source audit changed interpretation metadata, not
metric formulae or values.

## Instrumented Task Mapping

| Source | Meaning | Current model | Limitation |
|---|---|---|---|
| `task_active[t,k,n]` | Valid arrival at time/task/slot index | sample inclusion | False entries are ignored |
| `task_type[t,k,n]` | `0=T1`, `1=T2`, `2=T3` | `TosTaskObservation.task_class` | Source-only observation |
| `task_lat_ms[t,k,n]` | End-to-end modelled latency including backlog | `latency_ms` | Failed/unavailable paths may use capped latency |
| `task_met[t,k,n]` | latency within source deadline | `deadline_met` | Not eventual completion |
| `times[t]` | simulation timestamp | `arrival_time_s` | Exact time-index join |
| `veh_action[t,n]` | local/V2I/V2V decision for the time-local slot | `decision` | Target is not exported |

TrafficTwin joins per-task and per-step arrays only on exact `(time_index, vehicle_slot)`. It does
not reconstruct vehicle identity or infer a per-task target.

## Replay And RSU Mapping

| Source | Meaning | UI/source view | Canonical mapping |
|---|---|---|---|
| trace `times` | simulation seconds | replay timestamp | none |
| trace `pos_x`, `pos_y` | network metres | vehicle position | none, because persistent ID is absent |
| trace `speed` | metres per second | vehicle speed | none |
| trace `mask` | active slot at timestep | frame inclusion | none |
| trace `rsu_xy` | network-metre RSU position | replay RSU position | none |
| `rsu_load` | in-flight tasks at RSU | active task count | not queue length or utilisation |
| `rsu_busy_ms` | remaining compute backlog | backlog in ms | no canonical queue field |
| `rsu_max_concurrent` | maximum concurrent in-flight tasks | capacity bound | source-specific task-count capacity |
| load/capacity | concurrency pressure | `TosRsuReplayPoint.concurrency_pressure_fraction` | explicitly not `infra.utilisation.*` |

The ratio is useful for inspecting the environment's own concurrency bound. It is not promoted to
the Phase 3 metric catalogue because that catalogue defines infrastructure utilisation and queue
evidence differently. R1/R2 therefore remain evidence-limited.

## Vehicle Identity

`eval/build_trace.py` maps active SUMO IDs into a fixed-width array and reuses free slots. The
processed trace discards the source string ID. TrafficTwin consequently uses references such as
`slot:7@time-index:120`; `veh_7` across the whole trace would be false identity.

## Availability By Research Feature

| Feature | Status | Reason |
|---|---|---|
| Source deadline-success/action/mean-latency summaries | available | Validated evaluation CSV contract |
| Bounded task/action inspection | available for six showcases | Matched per-task and per-step arrays |
| Mobility replay | available | Processed traces and per-step timestamps align |
| RSU active-task pressure/backlog inspection | available | Semantics confirmed in source |
| Generic completed-task metrics | unavailable | Eventual physical completion is not exported |
| Vehicle-tier task cross-tab | unavailable | Only aggregate tier histogram exists |
| Canonical infrastructure utilisation/queue metrics | unavailable | Source fields are active tasks/backlog, not canonical fields |
| Trip/journey-time metrics | unavailable | No trip output |
| Decision target/link/action-availability evidence | unavailable | Internal values are not exported |

## No Silent Reconstruction

TrafficTwin does not replay JAX random-number generation to guess vehicle tiers, derive physical
completion from deadline failure, infer targets from proximity, or call concurrency pressure CPU
utilisation. Missing links stay explicit.

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Execution contract](randy_execution_contract.md)
- [TOS integration guide](tos_data_adapter.md)
- [Data contract](../data_contract.md)
- [Metrics catalogue](../metrics_catalogue.md)

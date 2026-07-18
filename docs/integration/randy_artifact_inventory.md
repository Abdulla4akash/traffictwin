# Randy/VEC Artifact Inventory

Discovery date: 2026-07-18

## Repositories Inspected

| Repository | Purpose | Inspected commit | TrafficTwin treatment |
|---|---|---|---|
| `TOS Data` | Evaluation, training, instrumented, and processed mobility results | `d27294ef5213e6a20f55632448bd20f5a76a45ab` | External, read-only data package |
| `vec_env` | VEC environment, evaluator, trace builder, training scripts, and reproducibility notes | `e98441196270b8fd4cc0eede892df4a0053b2185` | Source of field and execution semantics |

The two commit identifiers have different meanings. The TOS commit identifies the inspected data
package. The `vec_env` commit establishes source semantics but is **not** claimed as the producer
commit for every result row. Neither external repository is vendored into TrafficTwin.

## Discovery Method

The audit inspected file trees, documentation, evaluator and environment source, CSV headers and
row counts, JSON keys, NPZ headers, array shapes/dtypes, SLURM scripts, configuration paths, and
recorded actor references. Read-only scripts then checked all supplied evaluation, per-step,
per-task, summary, and trace artifacts. No external source file was changed.

## Data Package Inventory

| Artifact | Count | Purpose | Current use |
|---|---:|---|---|
| `evals/eval_results_master.csv` rows | 300 | One source-summary row per evaluated campaign/cell/fleet/seed | Validated registry import, source metrics, comparison, aggregate provenance |
| `training/*.csv` | 66 | Training curves | Inventory and provenance only |
| `training/*_greedy_eval.json` | 65 | Final greedy training-distribution summaries | Inventory only |
| `instrumented/perstep/*_perstep.npz` | 60 | Per-second task, vehicle-slot, and RSU state | Historical replay and bounded RSU inspection |
| `instrumented/pertask/*_pertask.npz` | 6 | Per-arrival showcase arrays | Bounded task inspection |
| `instrumented/json/*.json` | 60 | Instrumented run summaries | Reconciliation and capacity metadata |
| `traces/*.npz` | 5 | Processed Manchester SUMO FCD mobility and RSU positions | Historical replay |
| `records/TRAINING_*.md` | 8 | Training provenance and conventions | Discovery evidence |

Approximate payload sizes measured during discovery were 85.8 MB of traces, 240.8 MB of per-step
arrays, and 282.1 MB of per-task arrays. These are package observations, not performance claims.

## Source Repository Inventory

| Source | Purpose | Discovery result |
|---|---|---|
| `docs/REPRODUCING.md` | Reproducibility contract | Python 3.11, JAX/JAXlib 0.4.30, SUMO 1.27.0; FCD-to-trace-to-evaluation workflow; at least five fleet seeds per cell/fleet |
| `jaxmarl/env/vec_jax.py` | VEC environment | Defines task/action codes, deadlines, latency, action availability, RSU state, and capacity semantics |
| `eval/build_trace.py` | SUMO FCD conversion | Defines processed trace fields, units inherited from FCD, padding, and slot reuse |
| `eval/eval_sumo_stage1_mc.py` | Headless evaluator | Defines trace, actor, seed, fleet, capacity, duration, and JSON-output arguments |
| `eval/place_rsus_full.py` and related scripts | RSU preprocessing | Encodes RSU count and placement into trace artifacts |
| `slurm/eval_array.slurm` | CSF batch wrapper | Shows a source-author-specific SLURM workflow and hard-coded paths |
| `jaxmarl/scripts/train_*` | Training entry points | Defines stress/task/fleet controls; training is not integrated into TrafficTwin |

## Confirmed Field Semantics

| Field | Meaning | Unit | Canonical status |
|---|---|---|---|
| `task_type` | `0=T1`, `1=T2`, `2=T3` | code | Bounded source task view only |
| `task_met` / source `completion` | Modelled latency is within the class deadline | boolean/ratio | Not mapped to eventual physical completion |
| `task_lat_ms` | Modelled end-to-end latency including compute backlog; unavailable paths may use capped failure latency | ms | Bounded source task view |
| `veh_action` | `0=local`, `1=V2I`, `2=V2V` | code | Time-local source decision view |
| `times` | SUMO simulation time | s | Historical replay |
| `pos_x`, `pos_y`, `rsu_xy` | SUMO network coordinates | m | Historical replay |
| `speed` | SUMO vehicle speed | m/s | Historical replay |
| `rsu_load` | In-flight task count assigned to an RSU | tasks | Source-state inspection, not canonical queue/utilisation |
| `rsu_busy_ms` | Remaining compute backlog over in-flight tasks | ms | Source-state inspection |
| `rsu_max_concurrent` | Maximum concurrent in-flight task count per RSU | tasks | Source capacity bound |
| `rsu_load / rsu_max_concurrent` | Concurrency pressure | ratio | Source inspection only; not CPU utilisation |
| trace vehicle index | Padded time-local slot reused by the trace builder | none | Never treated as persistent vehicle ID |
| `fleet_tier_hist` | Aggregate tier counts over padded fleet slots | vehicles | No per-slot tier mapping |

## Complete-Package Checks

The audit checked all available files, not one sample:

- all 300 evaluation rows use engine `v2_post_nrsus_fix`;
- all 60 per-step array contracts and all 5 trace timelines are structurally valid;
- every trace timestamp sequence advances by one simulation second;
- all 60 RSU streams contain non-negative load/backlog and load never exceeds recorded capacity;
- maximum observed concurrency pressure is approximately `0.990354`;
- all 6 per-task files reconcile active arrivals and deadline-success counts to per-step arrays;
- all active per-task records use task codes 0/1/2 and action codes 0/1/2;
- every active `task_met` equals `task_lat_ms <= deadline` for source deadlines;
- 60 instrumented summaries record wall times from roughly 266 seconds to 15,306 seconds, with a
  median near 813 seconds. These are historical source-reported runtimes, not a TrafficTwin
  benchmark and not evidence that the evaluator runs locally.

## Absent Or Unrecoverable Artifacts

- actor/checkpoint files referenced by evaluation rows;
- exact producer commit for each result;
- the source writer that generated the supplied per-step and per-task NPZ files;
- persistent vehicle IDs in processed traces;
- per-vehicle tier, V2I target, V2V target, link quality, and action availability exports;
- trip or journey-time outputs;
- raw `.sumocfg`, `.net.xml`, `.rou.xml`, FCD XML, detector, queue, summary, or `tripinfo.xml` files;
- a locally tested, path-independent execution command.

## Privacy And Repository Policy

TrafficTwin commits no private checkpoint or raw TOS payload. Tests build a tiny
synthetic-schema package at runtime. Permission is still required before a sanitised real sample
is committed or reproduced in dissertation figures.

## Related Documents

- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)
- [Phase 6 decision](phase6_decision.md)
- [TOS integration guide](tos_data_adapter.md)

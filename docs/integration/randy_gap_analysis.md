# Randy/VEC Gap Analysis

Discovery date: 2026-07-18

External data package inspected: `external/tos-data`

## Discovery Update

The earlier Phase 6A conclusion, "no Randy artifacts present", is superseded by the cloned GitLab
data package. Real Randy/VEC result artifacts are now present for discovery.

The stop condition now changes from "no artifacts" to "do not implement adapters until the
remaining schema/unit/execution gaps below are resolved".

## What Is Now Unblocked

| Area | Status | Evidence |
|---|---|---|
| Evaluation-summary analysis | partially unblocked | `evals/eval_results_master.csv` has 300 rows with campaign/cell/fleet-seed summaries and documented fields. |
| Training-curve inventory | unblocked for documentation | 66 CSV files share a common training-curve schema. |
| Training-summary inventory | unblocked for documentation | 65 greedy-eval JSON files share a common schema. |
| Per-step instrumented schema | partially unblocked | 60 per-step NPZ files share documented keys and per-cell shape variants. |
| Per-task instrumented schema | partially unblocked | 6 per-task NPZ files provide full per-arrival logs for showcase runs. |
| Manchester trace schema | partially unblocked | 5 trace NPZ files provide vehicle positions, speed, mask, RSU coordinates, times, and metadata. |
| Engine version provenance | confirmed | Package documents `v2_post_nrsus_fix`; all master rows use this engine version. |

## Remaining Blocking Gaps

| Gap | Status | Impact | Required evidence |
|---|---|---|---|
| Runnable `vec_env` source/reproduction docs absent | unknown | Cannot implement launchers or confirm command/config controls. | Access to the source repo or copied `docs/REPRODUCING.md`. |
| `task_type` integer mapping source-confirmation absent | strongly inferred | Data consistency supports `0 -> T1`, `1 -> T2`, `2 -> T3`, but source confirmation is still preferable. | Randy confirmation or source-code enum. |
| `task_met` semantics need final confirmation | strongly inferred | It matches `task_lat_ms <= deadline` and JSON completion exactly, so it appears to mean deadline-met completion. | Written semantics or source-code definition, especially for late physical completion. |
| `rsu_busy_ms` utilisation conversion unconfirmed | unknown | It can exceed 1,000 ms per 1-second timestep, so it must not be naively mapped to utilisation fraction. | Denominator, timestep relation, and intended normalisation. |
| `rsu_load` meaning source-confirmation absent | strongly inferred | It is tightly correlated with `rsu_busy_ms` and approaches `rsu_max_concurrent` in incident runs, suggesting active load/backlog pressure. | Field definition confirming whether it is active tasks, queue length, backlog, or another count. |
| Trace coordinate/speed units source-confirmation absent | strongly inferred | Raw ordinary-cell speed around 9 maps plausibly to m/s (~33 km/h), and coordinates look SUMO metre-like. | SUMO/export unit documentation. |
| Per-vehicle tier data absent | not found | R1 cannot directly test low-tier T1 miss pattern. | Per-vehicle tier array/table or task-level vehicle-tier field. |
| Link quality/action availability absent | not found | R1 alternatives remain unresolved. | Any per-decision availability/connectivity evidence. |
| Trip/journey-time outputs absent | not found | Real Journey-Time Lens remains unavailable. | SUMO `tripinfo` or equivalent trip output. |
| Raw SUMO files absent | not found | SUMO-specific adapters remain unsupported. | `.sumocfg`, `.net.xml`, `.rou.xml`, FCD/tripinfo/detector/queue/summary outputs if intended. |
| Checkpoint files absent | partial | Run provenance can cite checkpoint paths/hash, but TrafficTwin cannot execute or inspect checkpoints. | Checkpoint files only if approved and necessary; otherwise keep as metadata. |
| Sanitised fixture permission absent | unknown | Cannot commit representative Randy fixtures into TrafficTwin tests. | Randy confirmation of what may be committed. |

## Metric And Rule Readiness

| Capability | Readiness from `TOS Data` | Notes |
|---|---|---|
| Task completion metrics | partial | Per-task NPZ supports six showcase runs after mapping confirmation. Master CSV has external precomputed completion but not raw task rows. |
| Decision shares/offload rate | partial | Master CSV and per-step arrays expose action shares/counts; task-level decisions are not directly available in per-task NPZ. |
| Latency metrics | partial | Per-task latency exists for six runs; master CSV latency is already averaged externally and includes missed/backlog semantics. |
| Energy metrics | summary only | Energy appears in summary CSV/JSON, but no per-task energy field was found. |
| Infrastructure queue/utilisation | partial | Per-RSU arrays exist. `rsu_load` is a strong pressure signal, but exact queue/utilisation mapping still needs confirmation. |
| Capacity-normalised load balance | blocked | Explicit capacity units/config not available in package. |
| Traffic speed/replay | partial | Trace NPZ includes speed and coordinates; units need confirmation. |
| Trip metrics | blocked | No trip records found. |
| R1 | partial/low confidence | T1 outcomes and offload summaries exist, but vehicle-tier and action-availability evidence are missing. |
| R2 | partial | Per-RSU and per-task showcase runs may support a candidate after conversion; temporal overlap needs adapter/evidence design. |
| R3 | partial | Master CSV supports multi-campaign/multi-seed comparison, but current R3 consumes EvidencePacks, not external summary rows. |

## Recommended Phase 6B Scope

Do not start with direct launch. Start with an offline conversion spike:

1. Select one matched showcase run:
   - per-task NPZ;
   - per-step NPZ;
   - trace NPZ;
   - matching summary JSON.
2. Confirm ambiguous field meanings with Randy.
3. Build a sanitised, small fixture if permission is granted.
4. Implement an adapter-specific converter that writes a standard TrafficTwin bundle.
5. Validate that generated bundle with the existing Phase 2 validator.
6. Run existing Phase 3 metrics, Phase 5 diagnostics, and provenance without changing their logic.

Possible first run: `baseline_uk2030_wd_am_fs0`, because matching per-task, per-step, trace, and
summary JSON artifacts are present and its dimensions are smaller than the incident cell.

## Integration Risks

- The evaluation master CSV contains metrics already computed by Randy's engine. Treating it as raw
  canonical evidence would bypass TrafficTwin's deterministic metrics.
- Per-step arrays are aggregate/time-series records, while TrafficTwin's current task canonical
  model is event-level. A converter must preserve this distinction.
- NPZ files do not have CSV row numbers. Provenance needs array-index references or generated CSV
  bundle rows with manifest provenance back to the original NPZ file.
- Large NPZ files should not be committed to TrafficTwin. Sanitised fixtures should be small and
  representative.
- Some training records include already interpreted "verdict" statements. TrafficTwin should not
  import those as diagnostic conclusions; rules must still operate on EvidencePacks only.

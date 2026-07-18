# Phase 6 Discovery Decision

Decision date: 2026-07-18

## Decision

Phase 6A discovery is reopened and updated because Randy's `TOS Data` package is now available in
`external/tos-data`.

Phase 6B real-adapter implementation is not started yet.

Reason: the data package confirms useful result schemas, but several field semantics, units,
fixture permissions, and the execution contract remain unresolved. Implementing a converter before
those points are confirmed would require guessing.

## What Is Confirmed

- Randy has provided access to a real VEC task-offloading results data package.
- The package commit inspected is `d27294ef5213e6a20f55632448bd20f5a76a45ab`.
- The package documents engine version `v2_post_nrsus_fix`.
- `evals/eval_results_master.csv` contains 300 evaluation summary rows.
- Training CSV, greedy-eval JSON, machine-provenance text, and training-record Markdown schemas are
  inspectable.
- Instrumented per-step NPZ files expose per-second task aggregates, per-vehicle actions/queues,
  and per-RSU arrays.
- Instrumented per-task NPZ files expose full per-arrival logs for 6 showcase runs.
- Trace NPZ files expose Manchester mobility positions, speeds, masks, RSU coordinates, and trace
  metadata.

## What Is Not Confirmed

- The runnable `vec_env` repository and its `docs/REPRODUCING.md` commands.
- Direct launch or asynchronous job invocation.
- Source-code or Randy confirmation of the strongly inferred `task_type` mapping: `0 -> T1`, `1 -> T2`, `2 -> T3`.
- Source-code or Randy confirmation that `task_met` means deadline-met completion.
- Utilisation or backlog normalisation for `rsu_busy_ms`.
- Whether `rsu_load` is active work, backlog, queue length, or another pressure counter.
- Source-code or Randy confirmation of the strongly inferred trace units.
- Per-vehicle tier evidence required for higher-confidence R1.
- Trip/journey-time outputs.
- Raw SUMO XML/config files.
- Permission to commit small sanitised real-schema fixtures.

## Capability Decision

| Capability | Decision | Evidence |
|---|---|---|
| Direct launch | `false` | Data package has no complete executable command contract. |
| Asynchronous launch | `false` | Training records mention CSF3/SLURM history, but no runnable job interface is present. |
| Standard TrafficTwin run-bundle import | `false` | Randy files are not standard TrafficTwin bundles yet. |
| Offline result conversion | `unknown` | Plausible from NPZ/JSON/CSV schemas, but needs ambiguity resolution and implementation. |
| Evaluation summary import | `unknown` | CSV schema is confirmed, but using precomputed external metrics requires a carefully labelled summary path. |
| Task arrival multiplier | `unknown` | Training records mention task-generation settings, but no safe config/invocation contract is present. |
| Workload class mix | `unknown` | Task mix is documented in summaries; external control is not confirmed. |
| Workload ordering | `unknown` | Not evidenced. |
| Vehicle count | `unknown` | Trace sizes and gridlock env variables are documented, but safe external control is not confirmed. |
| Vehicle tier mix | `unknown` | Training records mention fleet probabilities; safe external control is not confirmed. |
| RSU count | `unknown` | RSU counts are visible in traces; placement/control is not confirmed. |
| RSU capacity | `unknown` | `rsu_max_concurrent` appears in JSON; configurable capacity semantics are not confirmed. |
| RSU placement | `unknown` | `rsu_xy` exists in traces; safe control is not confirmed. |
| RSU failure | `unknown` | Not evidenced. |
| Action toggles | `unknown` | Action shares exist; enabling/disabling actions is not evidenced. |
| Signal timing | `unknown` | No SUMO config/control files present. |
| Lane closure | `unknown` | No SUMO config/control files present. |

## Implementation Decision

Do not implement yet:

- direct Randy/VEC launcher;
- SUMO XML adapters;
- dashboard claims of live or directly runnable Randy integration;
- changes to existing metrics or diagnostic rules.

Recommended next implementation, after Randy confirms the open mapping questions:

- `feat(integration): convert randy instrumented showcase runs to standard bundles`

This should be an offline adapter/converter only and should target one small sanitised showcase run
before attempting broader campaign import.

## Approval Gate For Phase 6B

Before writing adapter code, obtain:

- confirmation of inferred task-type encoding;
- confirmation of inferred `task_met` semantics;
- `rsu_busy_ms` and `rsu_load` definitions;
- coordinate/speed units;
- confirmation of vehicle-slot ID stability;
- fixture permission;
- and preferably access to the `vec_env` reproduction documentation.

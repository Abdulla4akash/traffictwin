# Phase 6 Integration Decision

Decision date: 2026-07-18

## Decision

Implement the evidenced, read-only portion of TOS Data integration without waiting for the
remaining RSU and execution-contract answers.

The approved boundary is:

- validate the external package and documented schemas;
- import the 300 evaluation summaries as explicitly source-provided metric collections;
- register source experiments and runs idempotently;
- expose bounded per-step replay and per-task showcase inspection;
- build partial EvidencePacks and let the unchanged rules report insufficient evidence;
- provide aggregate-level source-row provenance;
- preserve ambiguous RSU arrays as raw source values only.

This is not approval for a full Randy/VEC canonical adapter, SUMO adapter, or launcher.

## Evidence Supporting Implementation

- Package commit inspected: `d27294ef5213e6a20f55632448bd20f5a76a45ab`.
- All 300 evaluation rows use engine `v2_post_nrsus_fix`.
- The package documents evaluation summary meanings and units.
- All 60 per-step NPZ files share the expected key contract.
- All 6 per-task NPZ files share the expected key contract.
- All 5 trace NPZ files share the expected key contract.
- The 60 instrumented JSON summaries reconcile with matching evaluation rows.
- Across all active per-task entries, `0/1/2` maps consistently to T1/T2/T3 and `task_met`
  matches the package deadlines.

The last point is strong empirical evidence suitable for read-only inspection. TrafficTwin still
does not map `task_met` to eventual physical completion.

## Capability Decision

| Capability | State | Reason |
|---|---|---|
| Evaluation-summary import | supported | Documented CSV contract and engine version validate. |
| Instrumented historical replay | supported | Per-step and trace arrays align by time and padded slot. |
| Per-task showcase inspection | supported | Bounded, read-only inspection with explicit deadline semantics. |
| Source-summary comparison/aggregation | supported | Uses existing comparison/aggregation with a distinct metric version. |
| Partial EvidencePack and diagnostics | supported | Existing rules consume the pack unchanged and report evidence gaps. |
| Aggregate provenance | supported | Exact CSV row, package fingerprint, run, actor, and engine are available. |
| Standard TrafficTwin bundle import | unsupported | The external package is not a run bundle. |
| Canonical task conversion | unsupported | Eventual completion and persistent vehicle identity are not established. |
| Infrastructure metric mapping | unsupported | RSU field semantics and denominator are unresolved. |
| Trip/journey-time integration | unsupported | No trip output is present. |
| Direct launch | unsupported | No tested headless execution contract exists. |
| Asynchronous launch | unsupported | No locally callable job interface exists. |

Scenario-control capabilities remain `unknown`; data presence does not prove external control.

## Metric Policy

Source summaries use metric implementation version
`tos-source-summary-v2_post_nrsus_fix-1.0`. Available values are marked as source-provided and not
TrafficTwin recomputations. Metrics with incompatible definitions remain unavailable, including:

- TrafficTwin task completion rate; source deadline success uses the separate stable key
  `tos.task.deadline_success.rate`;
- generated/completed counts;
- eventual incomplete rate;
- latency P50/P95;
- energy per completed task;
- infrastructure, traffic, and trip metrics.

No Phase 3 formula was changed.

## Diagnostic Policy

The source-summary EvidencePack marks task evidence partial and infrastructure/trip evidence
unavailable. The unchanged rules therefore produce R0 evidence qualification and
`insufficient_evidence` for R1-R3 on ordinary source-summary runs. No real-data diagnostic claim is
enabled by this increment.

## Deferred Until Confirmation

- `rsu_load` definition;
- `rsu_busy_ms` denominator and interpretation;
- `rsu_max_concurrent` meaning;
- trace coordinate and speed units for canonical conversion;
- per-vehicle tier, link quality, action availability, and target evidence;
- trip/SUMO artifacts;
- sanitised real-fixture permission;
- `vec_env` execution contract.

## Repository Policy

The external package remains outside `diss/`. Tests generate a tiny synthetic-schema package at
runtime. No Randy data, private path, checkpoint, credential, or claimed research result is added
to TrafficTwin.

## Related Documents

- [TOS Data integration](tos_data_adapter.md)
- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)

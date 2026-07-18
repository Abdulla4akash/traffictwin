# Phase 6 Integration Decision

Decision date: 2026-07-18

## Decision

Retain the import-first TOS adapter and extend it only with interpretations directly evidenced by
the supplied `vec_env` source. Do not implement canonical conversion, SUMO XML support, or direct
launch from the current artifacts.

The approved implementation:

- validates and imports source-summary runs idempotently;
- exposes confirmed FCD-derived units in historical replay;
- joins per-task arrivals to source decisions by exact time/slot indices;
- displays RSU in-flight task count, compute backlog, and concurrency pressure;
- records the source-code semantics commit separately from data-package provenance;
- exposes a versioned machine-readable source contract;
- leaves existing Phase 3 metric values and Phase 5 rules unchanged.

A later productisation increment also adds read-only evaluation/training exploration, exact
fleet-seed paired comparisons, conservative domain labels, reproducibility auditing, and
aggregate report/atlas export. These features consume the same evidenced source boundary and do
not alter the canonical pipeline or launch decision.

## Evidence

- TOS package commit: `d27294ef5213e6a20f55632448bd20f5a76a45ab`.
- Semantics source commit: `e98441196270b8fd4cc0eede892df4a0053b2185`.
- All 300 evaluation rows and supplied NPZ/JSON artifacts were checked.
- `vec_jax.py` confirms task/action/deadline/RSU semantics.
- `build_trace.py` confirms FCD parsing and slot reuse.
- `eval_sumo_stage1_mc.py` confirms the evaluator arguments and capacity calculation.
- Official SUMO FCD conventions support seconds, network metres, and metres per second for the
  fields copied by the trace builder.

## Capability Decision

| Capability | State | Reason |
|---|---|---|
| Summary import/comparison | supported | Stable evaluation contract |
| Historical replay | supported | Time-aligned per-step and trace arrays with confirmed units |
| Evaluation/training workbench | supported | Deterministic source summaries and bounded curves |
| Aggregate research report/atlas | supported locally | Public sharing remains permission-gated |
| Task/action showcase | supported | Exact indexed join and confirmed codes |
| RSU source-state inspection | supported | Source meanings confirmed |
| Standard run-bundle conversion | unsupported | Canonical task completion/vehicle identity remain absent |
| Canonical infrastructure metrics | unsupported | Active-task pressure is not canonical utilisation/queue length |
| Journey-time integration | unsupported | No trip records |
| Direct launch | unsupported | Missing checkpoint, hard-coded paths, untested runtime |
| Instrumented rerun | unsupported | Writer source absent |
| Asynchronous launch | unsupported | CSF-specific wrapper is not a local observable job interface |

Scenario controls found in the source are documented but remain disabled in the read-only adapter.

## Metric And Diagnostic Policy

The source metric version remains
`tos-source-summary-v2_post_nrsus_fix-1.0`. Concurrency pressure is an inspection field, not a new
metric. EvidencePacks continue to mark canonical infrastructure evidence unavailable, so R0
qualifies the run and R1-R3 remain insufficient for ordinary imported source-summary runs.

## Provenance Policy

TrafficTwin records:

- TOS package fingerprint and Git commit;
- engine version and source row;
- actor/checkpoint reference and fleet seed;
- `vec_env` semantics evidence commit.

It does not claim that the semantics commit produced each run. No external file is copied into the
TrafficTwin repository.

## Deferred Evidence

- exact result-producing source commit;
- actor/checkpoint and instrumented writer;
- raw SUMO/trip outputs;
- per-vehicle tier and decision-time targets/link/action availability;
- permission for sanitised fixtures;
- locally tested evaluator runtime.

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)
- [TOS integration guide](tos_data_adapter.md)
- [TOS Results Workbench](tos_results_workbench.md)

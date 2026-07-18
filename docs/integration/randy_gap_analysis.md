# Randy/VEC Gap Analysis

Discovery date: 2026-07-18

## Position After Source Audit

Access to both `TOS Data` and `vec_env` closes most field-definition questions. TrafficTwin can
now explain trace units, deadline outcomes, action codes, RSU active-task load/backlog, capacity,
and the source evaluator interface. It still cannot claim complete canonical integration or
launch the environment.

## Implemented From Available Evidence

| Area | Status | Boundary |
|---|---|---|
| Package inventory and validation | implemented | CSV, JSON, NPZ headers, versions, and reconciliation |
| Evaluation summary import | implemented | Source metrics with separate implementation version |
| Registry persistence | implemented | Idempotent experiments, runs, metrics, and EvidencePacks |
| Historical mobility/task replay | implemented | Confirmed seconds, metres, m/s, and time-local slot identity |
| Per-task showcase inspection | implemented | Task class, deadline outcome, latency, and joined action |
| RSU source-state inspection | implemented | Active in-flight tasks, compute backlog, concurrency pressure |
| Comparison, partial evidence, diagnostics | implemented | Existing deterministic services; no new formulas/rules |
| Aggregate provenance | implemented | Exact summary CSV row, package fingerprint/commit, semantics commit |
| Machine-readable source contract | implemented | Fields, units, controls, evaluator template, blockers |

## Remaining Gaps

| Gap | Evidence status | Impact | Current fallback |
|---|---|---|---|
| Exact producer commit per run | unknown | Cannot bind each result to an environment commit | Preserve data commit, engine version, actor reference, and semantics commit separately |
| Actor/checkpoint files | unavailable | Evaluator cannot run | Direct launch false |
| Instrumented writer | unavailable | Per-step/per-task output cannot be reproduced | Import supplied arrays read-only |
| Persistent vehicle ID | contradicted | Cannot form longitudinal canonical vehicle records | Time-local slot references |
| Eventual task completion | unavailable | Cannot populate canonical `TaskRecord.completed` honestly | Source `deadline_met` view only |
| Per-vehicle tier | unavailable | No T1-by-low-tier R1 evidence | Aggregate fleet histogram only; R1 insufficient |
| Targets/link/action availability | unavailable | Important policy alternatives remain unresolved | Mark missing evidence |
| Canonical queue/utilisation fields | incompatible | Source active-task pressure is not Phase 3 utilisation/queue | Keep infrastructure metrics and R2 unavailable |
| Trip/journey-time output | unavailable | Journey-Time Lens has no real TOS evidence | Unavailable |
| Raw SUMO XML/config | unavailable | No SUMO XML adapter or trace regeneration | Processed-trace replay only |
| Sanitised fixture permission | unknown | Cannot commit a real-schema sample | Runtime synthetic-schema tests |

## Why The RSU Discovery Does Not Enable R2

The source now establishes that `rsu_load` is an in-flight task count and `rsu_busy_ms` is
remaining compute backlog. This permits honest inspection and the source-specific ratio
`rsu_load / rsu_max_concurrent`. It does not provide canonical CPU utilisation, queue length, or
task-to-RSU failure overlap expected by current Phase 3 metrics and R2. Promoting the ratio would
change metric/rule semantics, which this integration intentionally avoids.

## Rule Readiness

| Rule | TOS source-summary status | Missing evidence |
|---|---|---|
| R0 | triggered/ready | Correctly qualifies partial source evidence |
| R1 | insufficient | Task count denominator, per-vehicle tier, action availability, compatible infrastructure metric |
| R2 | insufficient | Canonical saturation/queue metrics and temporal task-failure overlap |
| R3 | insufficient for a single run | Experiment-level rule input representation |

Real artifacts do not automatically validate or activate a diagnostic hypothesis.

## Smallest Safe Next Integration

The next implementation should wait for permission and missing artifacts. A sensible first step
would be a sanitised, matched showcase plus its exact producing commit and writer. It could test a
source-specific conversion without claiming eventual completion, persistent identity, or trip
evidence. A launcher is a separate later decision.

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [TOS integration guide](tos_data_adapter.md)

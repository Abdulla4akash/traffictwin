# Randy/VEC Gap Analysis

Discovery date: 2026-07-18

External package: `external/tos-data`

## Current Position

The package closes the earlier “no artifacts” gap. TrafficTwin now has an implemented read-only
path for evaluation summaries, instrumented replay, task samples, partial evidence, diagnostics,
and aggregate provenance.

It does not close the canonical-integration or execution gaps.

## Implemented From Current Evidence

| Area | Status | Boundary |
|---|---|---|
| Package inventory/validation | implemented | CSV, JSON, NPZ headers, engine versions, reconciliation |
| Evaluation summary import | implemented | source-provided metrics, distinct metric version |
| Registry persistence | implemented | 10 experiments and 300 runs for the supplied package; idempotent |
| Historical replay | implemented | bounded per-step/trace source views |
| Per-task showcase inspection | implemented | bounded source-array entries, deadline semantics |
| Source-summary comparison | implemented | existing Phase 3 comparison logic |
| EvidencePack | implemented, partial | task summaries partial; other categories unavailable |
| Diagnostics | implemented, evidence-limited | unchanged R0-R3; infrastructure rules remain insufficient |
| Provenance | implemented, aggregate | exact CSV row/package/run lineage; no canonical contributors |
| Streamlit and CLI entry points | implemented | offline inspection only |

## Remaining Gaps

| Gap | Status | Impact | Fallback |
|---|---|---|---|
| `vec_env` source/reproduction contract | unknown | no launcher or config capability proof | direct/asynchronous launch `false` |
| RSU field definitions | unknown | no infrastructure canonical records or metrics | preserve raw values only |
| trace units | inferred, not confirmed | no canonical vehicle speed/position conversion | label source units |
| persistent vehicle identity | contradicted by slot reuse | cannot join a slot as one vehicle over a trace | time-local slot references |
| eventual completion distinct from deadline success | unknown | no canonical `completed` mapping | retain `deadline_met` only |
| per-vehicle tier | absent | no direct low-tier/T1 R1 evidence | R1 insufficient/limited |
| link/action availability and targets | absent | important alternatives unresolved | mark missing evidence |
| trip/journey-time records | absent | no real Journey-Time Lens metrics | unavailable |
| raw SUMO artifacts | absent | no SUMO adapter | unsupported |
| checkpoint files | absent | no checkpoint execution/inspection | retain actor reference only |
| fixture permission | unknown | real samples cannot enter Git | runtime synthetic-schema tests |

## Metric Reconciliation Policy

Randy's master CSV already contains calculated summaries. TrafficTwin does not present those as
canonical Phase 3 recomputation. Compatible values use a separate implementation version and
source warnings. Incompatible definitions remain unavailable rather than being forced to agree.

No “Randy legacy” metric keys were added because the current source values can be represented with
metadata under existing display keys. A future dissertation methodology may choose explicit
separate keys if external and TrafficTwin formulas are compared side by side.

## Rule Readiness

| Rule | Current TOS summary readiness | Reason |
|---|---|---|
| R0 | ready | reports partial/unavailable evidence accurately |
| R1 | insufficient | task count, per-vehicle tier, action availability, and infrastructure utilisation absent |
| R2 | insufficient | no interpreted queue/utilisation/saturation evidence |
| R3 | insufficient per run | ordinary EvidencePacks lack experiment-level dispersion inputs |

Real data presence does not promote a rule automatically.

## Recommended Next Integration Step

Wait for Randy's answers, then decide whether one matched showcase can be converted honestly to a
standard bundle. Start only with fields whose semantics and units are confirmed. A launcher should
remain a separate later decision after `vec_env` execution documentation is available.

## Related Documents

- [TOS Data integration](tos_data_adapter.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Phase 6 decision](phase6_decision.md)

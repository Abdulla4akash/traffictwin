# TOS Data Read-Only Integration

Status: implemented, source-evidenced, import-first.

The adapter reads Randy Putra's external TOS result package without modifying it. It imports
validated summary rows, provides bounded instrumented inspection, and routes comparisons,
EvidencePacks, diagnostics, and provenance through existing TrafficTwin services. It does not
execute `vec_env` or SUMO.

## Installation

NumPy is isolated in the optional TOS dependency because the generic standalone workflow does not
need it.

```bash
python -m pip install -e ".[tos]"
```

For development:

```bash
python -m pip install -e ".[dev,tos]"
```

## Supported Boundary

| Function | State | Notes |
|---|---|---|
| Evaluation-master validation/import | supported | Validates 20-column schema and engine version; registry import is idempotent |
| Source metric collections | supported | Distinct source version and semantics warnings |
| Historical replay | supported | Simulation seconds, network metres, m/s; slots are time-local |
| Per-task inspection | supported | Class, latency, deadline outcome, and joined local/V2I/V2V action |
| RSU source history | supported | In-flight tasks, compute backlog, maximum concurrency, pressure ratio |
| Comparison/evidence/diagnostics | supported but evidence-limited | Uses existing Phase 3/5 code unchanged |
| Aggregate source provenance | supported | Exact evaluation CSV row and package fingerprint/commit |
| Standard bundle/canonical conversion | unsupported | Completion identity and canonical infrastructure fields are incomplete |
| Trip/journey-time evidence | unsupported | No source output |
| Direct/asynchronous launch | unsupported | Execution blockers remain |

## CLI

```bash
traffictwin integration tos contract --format json
traffictwin integration tos inspect PATH
traffictwin integration tos validate PATH
traffictwin integration tos runs PATH --limit 25
traffictwin integration tos import PATH --registry data/registry/traffictwin.sqlite
traffictwin integration tos metrics PATH RUN_ID
traffictwin integration tos replay PATH RUN_KEY --index 0
traffictwin integration tos rsu-series PATH RUN_KEY --stride 10 --limit 250
traffictwin integration tos task-sample PATH RUN_KEY --limit 25
traffictwin integration tos diagnose PATH RUN_ID
traffictwin integration tos provenance PATH RUN_ID \
  --root-type metric --root-id tos.task.deadline_success.rate --format json
```

`RUN_ID` resembles `tos:baseline:wd_am:uk2030:fs0`; instrumented `RUN_KEY` resembles
`baseline_uk2030_wd_am_fs0`.

## Source Contract

`tos_source_contract()` reports:

- `vec_env` commit used as interpretation evidence;
- field meanings, units, evidence paths, and limitations;
- source-environment controls separately from adapter-exposed controls;
- the evaluator command template;
- direct-launch blockers and unavailable outputs.

The generated copy is [tos_source_contract.json](../reference/generated/tos_source_contract.json).

## Metric Semantics

Available source summaries:

- `tos.task.deadline_success.rate`;
- `tos.task.deadline_success.rate_by_class`;
- `task.latency.mean_ms`;
- local/V2I/V2V decision shares;
- `task.offload.rate`.

Unavailable examples remain present with reason codes:

- TrafficTwin task completion/generated/completed/incomplete metrics;
- latency count/P50/P95;
- energy per completed task;
- infrastructure utilisation/queue/saturation/load-balance metrics;
- traffic and trip metrics.

The adapter does not equate deadline success with eventual completion. The source reports joules
per arrival rather than per completed task. RSU concurrency pressure is not silently inserted as
CPU utilisation.

## Replay And Task Inspection

Replay joins the processed trace and per-step stream by exact timestamp and array index. It labels
positions in metres and speed in metres per second. Because the trace builder reuses padded slots,
references are time-local, such as `slot:4@time-index:20`.

Per-task inspection reads only active entries and joins `times[t]` and `veh_action[t,n]`. A result
includes both source indices. The join does not provide persistent identity or a V2I/V2V target.

RSU history exposes:

```text
active_task_count = rsu_load
remaining_compute_backlog_ms = rsu_busy_ms
concurrency_pressure_fraction = rsu_load / rsu_max_concurrent
```

The ratio is bounded and deterministic but source-specific. It does not feed the Phase 3 metric
engine or Phase 5 rules.

## Evidence, Diagnostics, And Provenance

Source-summary EvidencePacks intentionally keep task evidence partial and canonical
infrastructure/trip evidence unavailable. R0 reports this qualification and R1-R3 remain
`insufficient_evidence` for ordinary source runs.

Aggregate provenance reaches the exact evaluation CSV row, package fingerprint and commit, run,
experiment, source-scenario reference, actor reference, engine version, and semantics source
commit. It cannot identify canonical contributing task rows because those were not used to
compute the source summary.

## Security

- package-relative paths are containment checked;
- NPZ members reject traversal, absolute paths, and symlink entries;
- NumPy reads use `allow_pickle=False`;
- replay/task previews are bounded;
- external files are read-only;
- tests use generated synthetic-schema packages, not Randy's data.

## Validation Context Codes

In addition to structural/reconciliation findings, the report includes:

- `TOS_RSU_SEMANTICS_CONFIRMED`;
- `TOS_TRACE_UNITS_CONFIRMED`;
- `TOS_TASK_OUTCOME_SEMANTICS`;
- `TOS_TRIP_EVIDENCE_UNAVAILABLE`;
- `TOS_EXECUTION_CONTRACT_PARTIAL`;
- `TOS_INSTRUMENTED_WRITER_UNAVAILABLE`.

The final item is a warning because supplied instrumented results are inspectable but cannot be
regenerated from the shared source.

## Remaining Questions

- What exact source commit and writer produced each instrumented run?
- Can an approved actor checkpoint and small expected output be supplied?
- Are raw SUMO/trip outputs available?
- May a small sanitised matched sample be committed and shown in the dissertation?
- Is modification of the external environment permitted if instrumentation is later requested?

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)
- [Architecture](../architecture.md)
- [CLI reference](../cli_reference.md)

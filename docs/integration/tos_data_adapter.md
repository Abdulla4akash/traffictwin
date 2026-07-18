# TOS Data Read-Only Integration

Status: implemented as an evidence-gated offline integration.

This integration reads Randy Putra's external `TOS Data` result package without modifying it. It
does not execute `vec_env`, launch SUMO, convert the package into standard TrafficTwin bundles, or
assign unconfirmed semantics to RSU arrays.

## Supported Boundary

| Function | Status | Notes |
|---|---|---|
| Evaluation-master validation | supported | Validates the documented 20-column CSV and engine version. |
| Evaluation-summary registry import | supported | Registers experiments/runs and explicitly source-provided metric collections. |
| Instrumented NPZ header validation | supported | Reads NPY headers without materialising full arrays. |
| Historical replay inspection | supported | Uses documented per-step aggregates and time-aligned mobility slots. |
| Per-task showcase inspection | supported | Bounded read-only sample; `task_met` is labelled `deadline_met`. |
| Aggregate provenance | supported | Traces source metrics to an exact evaluation CSV row and package fingerprint. |
| Standard bundle conversion | unsupported | Canonical task outcome and RSU mappings remain incomplete. |
| RSU utilisation/queue metrics | unsupported | `rsu_load`, `rsu_busy_ms`, and `rsu_max_concurrent` remain raw source fields. |
| Trip/journey-time metrics | unsupported | No trip output exists in the package. |
| Direct/asynchronous launch | unsupported | No tested execution contract is present. |

## Installation

NumPy is optional because the standalone and generic bundle workflows do not require it.

```bash
python -m pip install -e ".[tos]"
```

Development installs can combine extras:

```bash
python -m pip install -e ".[dev,tos]"
```

## CLI

```bash
traffictwin integration tos inspect PATH
traffictwin integration tos validate PATH
traffictwin integration tos runs PATH --limit 25
traffictwin integration tos import PATH --registry data/registry/traffictwin.sqlite
traffictwin integration tos metrics PATH RUN_ID
traffictwin integration tos replay PATH RUN_KEY --index 0
traffictwin integration tos task-sample PATH RUN_KEY --limit 25
traffictwin integration tos diagnose PATH RUN_ID
traffictwin integration tos provenance PATH RUN_ID \
  --root-type metric --root-id tos.task.deadline_success.rate --format json
```

Use `RUN_ID` values such as `tos:baseline:wd_am:uk2030:fs0`. Instrumented `RUN_KEY` values follow
the package filenames, such as `baseline_uk2030_wd_am_fs0`.

## Evaluation Summary Semantics

The integration exposes compatible source values under the existing metric-result model with
implementation version `tos-source-summary-v2_post_nrsus_fix-1.0`. Every available result carries
warnings and metadata stating that it is source-provided and was not recomputed from canonical
records.

Available source summaries:

- deadline-success fraction under `tos.task.deadline_success.rate`;
- deadline-success fraction by T1/T2/T3 under
  `tos.task.deadline_success.rate_by_class`;
- mean latency over all arrivals, including deadline misses and backlog;
- local, V2I, and V2V action shares;
- offload share.

Explicitly unavailable examples:

- TrafficTwin `task.completion.rate` and `task.completion.rate_by_class`, because source deadline
  success is not silently equated with physical completion;
- generated/completed task counts, because the master CSV has no count denominator;
- eventual incomplete rate, because deadline failure is not silently equated with physical
  non-completion;
- latency P50/P95, because only a mean is present;
- energy per completed task, because the source reports joules per arrival;
- all infrastructure, traffic, and trip metrics from the summary table.

These source metric collections can use TrafficTwin's existing comparison and descriptive
aggregation services when versions, units, experiments, and random seeds are compatible.

## Evidence And Diagnostics

Each imported run receives a partial EvidencePack:

- tasks: `partial`;
- infrastructure, vehicles, traffic, trips, incidents: `unavailable`;
- diagnosis: `partial`.

The existing rules remain unchanged. R0 reports the evidence limitation, while R1-R3 return
`insufficient_evidence` for ordinary imported summary runs. The integration does not inject rule
results or manufacture infrastructure evidence.

## Replay And Per-Task Inspection

Replay joins per-step and mobility arrays only by `(timestamp, padded slot index)`. A slot is
labelled, for example, `slot:4@time-index:20`; it is not presented as a persistent vehicle ID.
Positions and speeds retain `source units` in the UI until Randy confirms their units.

Raw RSU values are visible for audit but carry `semantics_status: unresolved`. TrafficTwin does not
calculate `rsu_load / rsu_max_concurrent`, divide `rsu_busy_ms` by the timestep, or enable R2 from
those values.

Per-task inspection maps the empirically verified integer encoding `0 -> T1`, `1 -> T2`,
`2 -> T3`. The six supplied showcases were checked exhaustively: active `task_met` values match
`task_lat_ms <= deadline` using 100 ms for T1/T3 and 500 ms for T2. The source field is still
displayed as `deadline_met`, not eventual completion.

## Provenance

Evaluation-summary provenance reaches:

```text
metric or rule evidence
  -> exact evaluation CSV row
  -> evaluation master file
  -> external package
  -> package fingerprint and Git commit
  -> run, experiment, source-scenario reference, actor, and engine version
```

Canonical contributors are represented by explicit unavailable nodes. This is aggregate-level
provenance and does not claim per-task contribution weights.

The package fingerprint covers `README.md`, `DATA_DICTIONARY.md`, the evaluation master, and the
Git commit. Large NPZ payloads can be hashed individually when selected, but are not all rehashed
during routine inspection.

## Security And Data Policy

- NPZ members reject absolute paths, traversal components, and symlink entries.
- `allow_pickle=False` is used for NumPy reads.
- source paths are resolved inside the selected package root;
- replay and task previews are bounded;
- package files are read-only;
- no raw Randy files are committed to TrafficTwin;
- tests generate a tiny synthetic-schema package at runtime.

## Validation Findings

The TOS reader has a source-specific report rather than pretending the package uses the standard
run-bundle manifest. Stable finding families include:

- package/evaluation: `TOS_PACKAGE_NOT_FOUND`, `TOS_REQUIRED_FILE_MISSING`,
  `TOS_EVALUATION_MASTER_INVALID`, `TOS_EVALUATION_ROWS_EMPTY`, `TOS_RUN_ID_DUPLICATE`, and
  `TOS_ENGINE_VERSION_UNSUPPORTED`;
- array contracts: `TOS_PERSTEP_*`, `TOS_PERTASK_*`, and `TOS_TRACE_*` for invalid archives,
  missing arrays, or incompatible dimensions;
- reconciliation: `TOS_INSTRUMENTED_SUMMARY_INVALID`,
  `TOS_INSTRUMENTED_SUMMARY_UNMATCHED`, and `TOS_SUMMARY_RECONCILIATION_MISMATCH`;
- provenance/capability context: `TOS_PACKAGE_FINGERPRINT_UNAVAILABLE`,
  `TOS_PACKAGE_COMMIT_UNAVAILABLE`, `TOS_RSU_SEMANTICS_UNRESOLVED`,
  `TOS_TASK_OUTCOME_SEMANTICS`, `TOS_TRIP_EVIDENCE_UNAVAILABLE`, and
  `TOS_EXECUTION_CONTRACT_UNAVAILABLE`.

Missing required summary metadata, duplicate run IDs, unsupported engine versions, or an
unavailable package fingerprint reject summary import. Malformed optional NPZ/JSON artifacts do not
discard valid evaluation summaries, but they disable the affected replay or task-inspection
capability and remain visible as warnings.

## Remaining Questions

The implemented boundary does not require answers to proceed. Stronger conversion still requires:

- exact definitions and denominator for `rsu_load`, `rsu_busy_ms`, and `rsu_max_concurrent`;
- confirmed position and speed units;
- per-vehicle tier, action availability, link quality, and action target evidence if available;
- trip/SUMO outputs if journey-time integration is expected;
- `vec_env` reproduction documentation for any launcher work;
- permission before committing a sanitised real-schema sample.

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Gap analysis](randy_gap_analysis.md)
- [Phase 6 decision](phase6_decision.md)
- [Architecture](../architecture.md)

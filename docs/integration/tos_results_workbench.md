# TOS Results Workbench

Status: implemented as a read-only, source-evidenced product layer.

The workbench analyses Randy Putra's separately supplied TOS Data package without copying or
modifying it. It extends the conservative import boundary with ten coordinated inspection and
export features. It does not add a launcher, canonical converter, new research metric, new
diagnostic rule, or live-data capability.

## Feature Set

| Feature | Inputs | Output | Boundary |
|---|---|---|---|
| TOS Evaluation Explorer | 300-row evaluation master | campaign/cell/fleet matrix | Descriptive source measures only |
| Paired Experiment Comparison | common cell and fleet seeds | variation-minus-baseline deltas | No causal or algorithm-ranking claim |
| Historical Mobility Replay 2.0 | per-step NPZ and processed FCD NPZ | logical replay and bounded spatial frames | Simulation; slots are not persistent IDs |
| RSU Pressure Explorer | `rsu_load`, `rsu_busy_ms`, concurrency bound | per-RSU pressure/backlog history | Pressure is not CPU utilisation |
| Task Outcome Explorer | six per-task showcase NPZ files | exact class/decision outcome aggregates | Deadline success, not eventual completion |
| Training History Explorer | 66 training CSVs and greedy JSON | bounded curves and final source summaries | Training distribution, not Manchester evaluation |
| Generalisation Matrix | data dictionary and training records | in-domain/held-out/unknown labels | Unknown remains unknown |
| Reproducibility Auditor | package inventory and cross-references | pass/information/warning/blocked checks | Engineering audit, not scientific validation |
| Dissertation Results Pack | preceding aggregate models | Markdown, HTML, JSON, static atlas | Permission review required before sharing |
| Static Results Atlas | precomputed aggregate matrix | standalone interactive HTML | No remote assets or raw/private host metadata |

## Install And Inspect

```bash
python -m pip install -e ".[dev,tos]"
export TOS_DATA_PATH=../external/tos-data
traffictwin integration tos validate "$TOS_DATA_PATH"
traffictwin integration tos matrix "$TOS_DATA_PATH"
traffictwin integration tos compare-campaigns \
  "$TOS_DATA_PATH" baseline ukfleettrain_mappo
```

Launch Streamlit and use:

1. **TOS Data Import** to validate the external package and optionally register summaries.
2. **TOS Results** for the matrix, paired comparison, and domain labels.
3. **TOS Mobility & RSU Replay** for logical replay and source-array inspection.
4. **TOS Training & Audit** for training curves, audit checks, and deliberate exports.

## Source Analysis Measures

The workbench has a separate source-analysis catalogue. It does not silently add these fields to
TrafficTwin's canonical Phase 3 metric catalogue.

- `tos.task.deadline_success.rate`
- `tos.task.deadline_success.t1_rate`
- `tos.task.deadline_success.t2_rate`
- `tos.task.deadline_success.t3_rate`
- `tos.task.latency.mean_all_arrivals_ms`
- `tos.task.energy.mean_per_arrival_j`
- `tos.decision.share.local`
- `tos.decision.share.v2i`
- `tos.decision.share.v2v`
- `tos.decision.offload_share`

Matrix entries report `n`, arithmetic mean, sample standard deviation when `n >= 2`, minimum,
maximum, and linear-interpolated P50. They describe fleet-seed replicates and are not confidence
intervals.

## Paired Comparison

Rows pair only when campaign, evaluation fleet, source cell, and fleet seed align. TrafficTwin
also reports mismatched engine, observation variant, trace, duration, or maximum slot count.

```text
absolute delta = variation - baseline
relative delta = (variation - baseline) / abs(baseline)
```

Zero-versus-zero has relative delta `0`; a zero baseline with non-zero variation is unavailable.
No comparison is automatically called improved or worsened.

## Historical Replay

Playback advances a logical source index at a selected rate. It does not sleep in library code or
simulate missing records. The lightweight aggregate timeline is loaded once per selected run.
Spatial frames are loaded deliberately because each frame must read compressed source arrays.

Processed trace fields are simulation seconds, SUMO network metres, and metres per second.
Vehicle slots are recycled; a slot may only be identified at one time index.

## RSU And Task Semantics

```text
active in-flight task count = rsu_load
remaining compute backlog (ms) = rsu_busy_ms
concurrency pressure = rsu_load / rsu_max_concurrent
```

The explorer does not call these queue length or CPU utilisation. Full per-task aggregation is
available only for the six supplied showcase arrays and is clearly separated from the 300-row
headline matrix. `task_met` means modelled latency was within the class deadline.

## Training And Generalisation

Training CSV `nan` warm-up values are represented as unavailable, never JSON NaN. Greedy summaries
are displayed separately. Machine-record content is not exposed because it may contain private
host details.

The domain matrix uses three states:

- `in_domain`: explicitly documented relationship;
- `held_out`: explicitly documented held-out mobility relationship;
- `unknown`: the inspected package does not establish the relationship.

The labels describe provenance. They do not establish external validity.

## Results Pack And Atlas

```bash
traffictwin integration tos report "$TOS_DATA_PATH" \
  --variation ukfleettrain_mappo --output tos-report.md
traffictwin integration tos atlas "$TOS_DATA_PATH" --output tos-atlas.html
traffictwin integration tos results-pack "$TOS_DATA_PATH" --output tos-results
```

`results-pack` writes:

- `research-report.md`;
- `research-report.html`;
- `evaluation-matrix.json`;
- `paired-comparison.json`;
- `reproducibility-audit.json`;
- `results-atlas.html`.

The output directory must be empty. The atlas is self-contained, uses precomputed aggregates, has
no remote assets, excludes machine-specific absolute paths, and carries an explicit research-use
and permission notice. It is technically suitable for static hosting, but TrafficTwin does not
publish Randy-provided values until permission is confirmed.

## Remaining Blocks

- actor checkpoint payloads;
- exact instrumented-array writer and producing commit;
- raw SUMO configuration/XML and trip records;
- persistent vehicle identity;
- eventual completion for deadline misses;
- per-vehicle tier and action target/availability/link evidence;
- permission to commit or publicly host sanitised source-derived fixtures/results.

## Related Documents

- [TOS adapter](tos_data_adapter.md)
- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Execution contract](randy_execution_contract.md)
- [Phase 6 decision](phase6_decision.md)
- [Architecture](../architecture.md)

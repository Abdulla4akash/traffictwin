# Randy/SUMO Gap Analysis

Discovery date: 2026-07-17

## Stop Condition Triggered

The Phase 6A stop condition is met: no real Randy/VEC or SUMO artifacts are present in the inspected workspace.

Adapter implementation must not proceed from the current evidence because it would require inventing schemas, units, launch commands, or simulator behavior.

## Blocking Gaps

| Gap | Status | Impact | Required evidence |
|---|---|---|---|
| Real Randy task schema absent | unknown | Cannot implement VEC task adapter or validate real task files. | Sample task log with headers, units, row examples, field definitions. |
| Real Randy infrastructure schema absent | unknown | Cannot implement RSU utilisation, queue, capacity, or R2-ready mappings. | Per-RSU time-series output with units and semantics. |
| Vehicle tier/action availability/link quality absent | unknown | R1 remains lower-confidence or insufficient on real data. | Vehicle-tier file or task-level tier column; action availability and link-quality evidence if available. |
| SUMO source files absent | unknown | Cannot implement FCD, tripinfo, detector, queue, or scenario adapters. | Actual SUMO output formats and run configuration. |
| Units absent | unknown | Cannot safely convert real fields to canonical units. | Per-file unit documentation or manifest. |
| Identifier conventions absent | unknown | Cannot join tasks, vehicles, RSUs, trips, sensors, and routes. | ID definitions and examples across files. |
| Execution contract absent | unsupported | Direct launch must stay disabled. | CLI/API/script/notebook/job contract with command examples and output semantics. |
| Runtime and output sizes absent | unknown | Cannot assess local, CSF, or hybrid execution feasibility. | Lightweight and SUMO runtime measurements, output-size estimates, sweep plans. |
| Existing metric scripts absent | unknown | Cannot reconcile Randy's current metrics against TrafficTwin formulas. | Plotting/metric scripts, notebooks, or written formula definitions. |
| Environment version or commit absent | unknown | Provenance cannot be complete for real runs. | Git commit, release tag, environment version, dependency notes. |

## Evidence Required Before Phase 6B

Request the following from Randy or the environment owner:

1. One complete real or sanitised output directory from a single validation run.
2. Header rows and unit documentation for every exported file.
3. A short README describing whether the sample is training, lightweight validation, SUMO validation, or a post-processed summary.
4. Task outputs with task ID, vehicle ID, task class, arrival time, deadline, decision, decision target, completion status, completion time or latency, and any available workload, data-size, energy, or drop fields.
5. Infrastructure outputs with RSU ID, timestamp, queue length, utilisation, arrivals, completions or active tasks, drops, and capacity if available.
6. Vehicle state outputs or SUMO FCD files if vehicle trajectories or tiers should be analysed.
7. Trip outputs, preferably SUMO `tripinfo`, if journey-time metrics are required.
8. Detector, traffic observation, queue, incident, or event files if present.
9. SUMO `.sumocfg`, `.net.xml`, `.rou.xml`, `.add.xml`, FCD, tripinfo, detector, queue, and summary files actually used by the workflow.
10. Scenario configuration files and a description of which seed controls are genuinely supported.
11. Environment version, Git commit, algorithm, checkpoint ID/path, random seed, training budget, and evaluation seed provenance.
12. Existing plotting scripts, metric scripts, or notebooks used to generate Randy's current reported numbers.
13. The exact command, Python call, notebook sequence, shell script, or CSF job script used to generate the sample.
14. Lightweight-environment runtime, SUMO-validation runtime, expected output size, and number of runs per experiment.
15. Written confirmation of which files can be committed as sanitised fixtures and which must remain private.

## Metric And Rule Readiness Gaps

| Capability | Current real-data readiness | Missing evidence |
|---|---|---|
| Existing Phase 3 task metrics | blocked for real data | Real task file schema, units, and valid row examples. |
| Existing Phase 3 infrastructure metrics | blocked for real data | Real per-RSU queue/utilisation schema and units. |
| Existing Phase 3 traffic metrics | blocked for real data | Real traffic observation or detector schema and units. |
| Existing Phase 3 trip metrics | blocked for real data | SUMO tripinfo or equivalent trip schema and units. |
| R1 under-offloading | insufficient for real data | T1 outcomes, vehicle tier evidence, offload rate, RSU utilisation, action availability and link-quality context where available. |
| R2 infrastructure bottleneck | insufficient for real data | Per-RSU utilisation and queue history, saturation intervals, task misses, temporal alignment, capacity semantics. |
| R3 scenario triviality | insufficient for real data | Multiple compatible algorithms/policies, common seeds, always-local baseline if available, cross-algorithm dispersion metrics. |

## Integration Risk

The most likely integration risks remain:

- multiple incompatible output schemas across training, lightweight validation, and SUMO validation;
- missing or inconsistent units;
- output summaries that omit row-level identifiers needed for joins;
- notebook-only execution with hidden state;
- checkpoints referenced in metadata but unavailable;
- existing metric scripts using definitions that differ from TrafficTwin's formulas.

These are manageable only after representative artifacts are supplied and documented.

# Randy/SUMO Execution Contract

Discovery date: 2026-07-17

## Execution Discovery Result

No documented Randy/VEC or SUMO invocation contract was found in the inspected workspace.

The following were not present:

- CLI entry point;
- Python API;
- shell script;
- notebook workflow with executable state;
- CSF, SLURM, PBS, or other job script;
- documented command arguments;
- configuration override examples;
- output directory contract;
- exit status semantics;
- runtime measurement;
- checkpoint files;
- environment version or commit;
- existing logs showing how outputs are produced.

## Invocation Classification

| Interface type | Evidence found | Status |
|---|---|---|
| CLI | none | unsupported |
| Python API | none | unsupported |
| Shell script | none | unsupported |
| Notebook only | none | unsupported |
| CSF or job script | none | unsupported |
| Documented output bundle | none | unsupported |

Because no invocation contract exists locally, TrafficTwin must remain import-first and export-only for Randy/SUMO integration.

## Capability Manifest Decision

This manifest records the capability decision from inspected evidence only.

```yaml
environment:
  adapter: randy_vec_discovery
  evidence_date: "2026-07-17"
  supports:
    seed_import: unknown
    seed_export: unknown
    run_bundle_import: unknown
    direct_launch: false
    asynchronous_launch: false
    task_arrival_multiplier: unknown
    workload_class_mix: unknown
    workload_ordering: unknown
    vehicle_count: unknown
    vehicle_tier_mix: unknown
    rsu_count: unknown
    rsu_capacity: unknown
    rsu_placement: unknown
    rsu_failure: unknown
    action_toggles: unknown
    signal_timing: unknown
    lane_closure: unknown
```

Notes:

- `direct_launch` is `false` because no documented and tested headless command exists.
- `asynchronous_launch` is `false` because no observable queue or job mechanism exists in the workspace.
- Scenario controls remain `unknown`, not `false`, because no real configuration files or command arguments were available to inspect.
- Existing `generic_csv` import remains supported for documented TrafficTwin bundles, but that does not prove Randy/SUMO compatibility.

## Runtime And Output-Size Evidence

| Item | Status | Evidence |
|---|---|---|
| Lightweight-environment runtime | unknown | No command, logs, or benchmark output found. |
| SUMO-validation runtime | unknown | No SUMO configuration, command, logs, or benchmark output found. |
| Expected output size | unknown | No real output files found. |
| Runs per experiment | unknown | No real experiment plan or job script found. |
| Checkpoint availability | unknown | No checkpoint files found. |

## Launcher Decision

No launcher should be implemented in Phase 6A.

A future launcher may be considered only after supplied evidence confirms:

- stable headless entry point;
- documented argument list;
- controlled working directory and output directory;
- non-interactive execution;
- exit status behavior;
- timeout and cancellation behavior;
- no automatic retraining;
- no destructive side effects;
- small test case that can run locally or in a documented environment.

Until then, the UI Run button must remain disabled or absent for Randy/SUMO adapters.

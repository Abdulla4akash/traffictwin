# Randy/VEC Execution Contract

Discovery date: 2026-07-18

External data package inspected: `external/tos-data`

## Execution Discovery Result

The `TOS Data` package is a results/data package. It is not the runnable VEC/SUMO environment.

The package README states that the code which produced the data lives in a separate `vec_env`
repository and refers to `docs/REPRODUCING.md` in that repository. That source repository and its
reproduction documentation were not present in the cloned data package.

## Invocation Classification

| Interface type | Evidence found in `external/tos-data` | Status |
|---|---|---|
| CLI | No executable command contract. Training records mention flags such as `--fleet uk2030` and `--cap-scalar`, but not a complete command. | unknown |
| Python API | none | unsupported |
| Shell script | none | unsupported |
| Notebook workflow | none | unsupported |
| CSF/SLURM job script | Training records mention CSF3/SLURM logs and job IDs, but no job scripts or logs are present in this package. | unknown |
| Standard TrafficTwin output bundle | none | unsupported until a converter is built |
| Offline data import | Real result files are present and documented. | plausible for Phase 6B after mapping questions are answered |

## Runtime And Output-Size Evidence

| Item | Evidence | Status |
|---|---|---|
| Data package size | approximately 1.2 GB cloned repository | confirmed |
| Instrumented folder size | approximately 499 MB | confirmed |
| Trace folder size | approximately 82 MB | confirmed |
| Training folder size | approximately 5.5 MB | confirmed |
| Evaluation master CSV size | small, 300 rows | confirmed |
| Per-run wall time | Summary JSONs include `wall_s`; training records include approximate wall-clock ranges by machine | partial |
| Lightweight-environment runtime | no runnable small command present | unknown |
| SUMO-validation runtime | no SUMO command/config present | unknown |
| Runs per experiment | master CSV has campaigns x cells x fleet seeds; full experiment-generation command absent | partial |
| Checkpoint availability | checkpoint paths and md5 values are documented; checkpoint files are not present | partial |

## Capability Manifest Decision

This manifest is based only on inspected evidence. It does not enable UI launch controls.

```yaml
environment:
  adapter: randy_tos_data_discovery
  evidence_date: "2026-07-18"
  source_package_commit: "d27294ef5213e6a20f55632448bd20f5a76a45ab"
  supports:
    direct_launch: false
    asynchronous_launch: false
    run_bundle_import: false
    offline_result_conversion: unknown
    eval_summary_import: unknown
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

- `direct_launch` is `false` because no complete documented and tested headless command exists in
  the data package.
- `asynchronous_launch` is `false` for TrafficTwin because no observable queue/job interface is
  available locally, even though training records mention CSF3/SLURM history.
- `run_bundle_import` is `false` because Randy's files are not TrafficTwin bundles yet.
- `offline_result_conversion` is `unknown`, not `true`, until the NPZ field ambiguities are resolved
  and a converter is implemented.
- Scenario controls remain `unknown` because records mention some environment variables/flags but no
  safe invocation contract or config schema is present.

## Launcher Decision

No launcher should be implemented from the current package.

A future launcher may be considered only after the separate execution repository or Randy's
documentation confirms:

- stable headless entry point;
- complete argument list;
- seed/config override policy;
- controlled input and output directories;
- non-interactive execution;
- exit status semantics;
- timeout/cancellation behavior;
- no automatic retraining;
- small smoke run that can be executed safely.

Until then, TrafficTwin remains import-first for Randy/VEC data.


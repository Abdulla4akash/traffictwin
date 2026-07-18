# Randy/VEC Execution Contract

Status: evaluator interface discovered; TrafficTwin launch remains disabled.

## Evidenced Workflow

`vec_env/docs/REPRODUCING.md` documents this sequence:

```text
SUMO FCD XML
  -> eval/build_trace.py
  -> processed trace NPZ and RSU placement
  -> eval/eval_sumo_stage1_mc.py with an actor checkpoint
  -> aggregate summary JSON
```

The inspected source specifies Python 3.11, JAX/JAXlib 0.4.30, and SUMO 1.27.0. It recommends at
least five fleet seeds per scenario cell/fleet. TrafficTwin records these as source-contract
evidence; it has not reproduced the runtime locally.

## Evaluator CLI

The source exposes a headless Python command equivalent to:

```bash
python eval/eval_sumo_stage1_mc.py \
  --trace TRACE.npz \
  --actor ACTOR_PARAMS.npz \
  --seed 0 \
  --fleet uk2030 \
  --fleet-seed 0 \
  --rsu-cap-per-veh 2.5 \
  --out-json OUT.json
```

Additional source options include maximum steps and `--cap-scalar`. The evaluator patches vehicle
count, trace length, RSU positions/count, and the per-RSU concurrency bound from the selected
trace and arguments.

The current evaluator writes an aggregate JSON summary. It does **not** contain the writer that
created the TOS package's per-step and per-task NPZ files.

## Why Direct Launch Is False

TrafficTwin does not expose the command as a launcher because:

1. referenced actor/checkpoint files are not supplied;
2. the evaluator contains a source-author-specific hard-coded repository path;
3. the instrumented NPZ writer is absent from the repository and history inspected;
4. raw SUMO inputs are not supplied for rebuilding traces;
5. dependency installation, exit behavior, deterministic rerun, and output discovery have not
   been tested in the TrafficTwin environment;
6. the SLURM wrapper is tied to CSF paths and environment setup.

These are execution blockers, not reasons to reject the existing result package. Import-first
analysis remains operational.

## Source Controls Versus Adapter Controls

| Control | Source evidence | TrafficTwin adapter |
|---|---|---|
| Task arrival rate | training stress config/environment values | disabled |
| Task class mix | `VEC_JAX_TASK_DIST` presets | disabled |
| Task ordering | stress config (`iid`, `markov`, `round_robin`, `front_loaded`) | disabled |
| Vehicle count | environment config or trace `maxN` | disabled |
| Fleet/tier mix | evaluator fleet preset and fleet seed | disabled |
| RSU count/placement | trace preprocessing | disabled |
| RSU capacity | `--rsu-cap-per-veh` | disabled |
| Local/V2I/V2V scenario toggles | no external scenario toggle evidenced | unknown in source, disabled in adapter |
| Signal timing | not evidenced | unknown/disabled |
| Lane closure | not evidenced | unknown/disabled |

Source code containing a control does not make it safe for UI launch. The read-only `tos_data`
adapter therefore continues to report all launch controls as false or unknown.

## Runtime Evidence

The 60 instrumented summary files record historical wall times:

- minimum approximately 265.5 seconds;
- median approximately 813.0 seconds;
- maximum approximately 15,305.9 seconds.

These values vary by source run and machine. They are not local benchmarks, service-level claims,
or evidence that TrafficTwin can execute the evaluator.

## Required Evidence Before A Launcher

- a redistributable or locally accessible actor checkpoint;
- a path-independent evaluator revision;
- exact producer source commit;
- a small approved trace and expected output;
- tested dependency setup and working directory;
- exit-code, timeout, cancellation, and deterministic-seed behavior;
- an output contract, including whether aggregate JSON alone is acceptable;
- explicit approval before modifying the external environment.

## Machine-Readable View

```bash
traffictwin integration tos contract --format json
```

The command reports the discovered command template and blockers but cannot execute it.

## Related Documents

- [Artifact inventory](randy_artifact_inventory.md)
- [Schema mapping](randy_schema_mapping.md)
- [Gap analysis](randy_gap_analysis.md)
- [Phase 6 decision](phase6_decision.md)

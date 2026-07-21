# VEC-07 safe local evaluator runner

Status: implemented library capability; direct launch remains unavailable pending VEC-08.

TrafficTwin can now execute the exact audited Model-C evaluator locally without executing a shell
string or modifying either external repository. The public library is
`traffictwin.integration.vec_runner`; CLI and UI surfaces intentionally remain assigned to VEC-10.

## Accepted inputs

`VecRunRequest` permits only:

- one of the two audited 17-input Model-C actors at the pinned `tos-data` commit;
- the reviewed weekend full-RSU trace, or a trace identified by a valid VEC-06 preprocessing
  receipt;
- a closed evaluator fleet preset;
- finite bounded seeds, RSU capacity, step count, and timeout; and
- a new output directory outside inputs, this repository, and both external repositories.

The request accepts no executable, Python module, arbitrary flag, environment variable, shell
fragment, network location, installer, scheduler, or Git operation.

## Preflight and execution

`preflight_vec_run(input_root, vec_repo, tos_data_repo, request)` is read-only. It verifies the
clean external worktrees and pinned remote refs, loads and hashes the exact evaluator/environment/
actor Git blobs, checks the actor's `17 -> 64 -> 64 -> 3` float32 structure, validates the trace
through VEC-02, and requires JAX/JAXLIB 0.4.30 on CPU.

`run_vec_evaluator(...)` repeats admission, stages exact blobs in a private workspace, neutralises
the evaluator's fixed import path through a controlled namespace-only `PYTHONPATH`, constructs one
allowlisted argv, and captures bounded path-redacted logs. It always requests the run JSON,
per-step NPZ, and per-task NPZ. Successful outputs must pass the exact VEC-02 schemas and aggregate
reconciliation before a new read-only directory is atomically published.

Timeout, cancellation, evaluator failure, malformed output, source drift, or input drift returns a
typed terminal receipt through `VecRunnerError.receipt` and publishes nothing. A successful receipt
records the redacted argv, runtime/hardware evidence, source/input identities before and after,
logs, output hashes, and an output fingerprint.

## Example library use

```python
from traffictwin.integration.vec_runner import VecRunRequest, run_vec_evaluator

request = VecRunRequest(
    run_id="weekend-two-step",
    trace_file="traces/trace_we_fullrsu.npz",
    trace_sha256="a2612865f5e1ef6d066975d6430693225f5d16060f139176548c8ae020e428be",
    actor_id="ukfleettrain_mappo_model_c_17",
    evaluator_seed=0,
    fleet="uk2030",
    fleet_seed=0,
    max_steps=2,
)

receipt = run_vec_evaluator(
    input_root="../external/tos-data",
    vec_repo="../external/vec_env",
    tos_data_repo="../external/tos-data",
    output_dir="./local-evidence/weekend-two-step",
    request=request,
)
```

Install the optional runtime with `uv sync --extra dev --extra vec-runner`. The output directory
must not already exist.

## Acceptance evidence and limits

The real integration test executes two steps from exact audited evaluator, environment, actor, and
trace blobs, validates all three produced scientific artifacts, verifies both repositories and the
trace are unchanged, and confirms atomic read-only publication. Focused tests also cover dirty
source, unavailable runtime, actor incompatibility, malformed output, timeout, cancellation,
existing/overlapping destinations, and fail-closed non-publication.

This capability proves safe local software execution only. It does not establish numerical
reproduction, validate dissertation claims, prove completed task transfers, enable SUMO launch or
training, or make TrafficTwin's generic `direct_launch` capability true. VEC-08 must produce the
reviewed reproduction report before those scientific and product gates can change.

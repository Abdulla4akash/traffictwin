# Sub-second placement-workload delay

This optional extension starts from frozen E2d commit
`2f63706f46319433a2ba3af1df97afd0e56a95d1`. It supports Sandra's suggested
100 ms, 500 ms and 1-second ages using `--rsu-state-delay-ms`, with an
explicit fresh control at zero. The supported range is integer 0–1000 ms.

## Information and timing contract

The experiment varies the age of **the remaining RSU compute workload used
for placement**. The selected RSU still applies the inherited deadline and
capacity admission checks to its actual workload and in-flight task count.
Latency, energy, execution, forwarding and service accounting also use the
actual state. This represents delayed placement reports with immediate
admission acknowledgements from the execution RSU. It does not model delayed
admission decisions, delayed acknowledgements or physical control messages.

Model C retains one mode/link decision per vehicle per second. Its K_MAX
task slots are ordered admissions at the same logical time, first by slot
and then by vehicle index. They are **not 200 ms clock ticks**. All admissions
in a batch precede the existing one-second service drain.

To define intermediate report times without moving task arrivals or changing
that drain, this extension explicitly assumes continuous service between
the existing admission batches. Let `B[t-1000]` be the previous batch's true
post-admission workload, in milliseconds of service, before its drain. For
`0 < d <= 1000`, the report used at elapsed time `t` is:

```text
captured_at = t - d
report_workload = max(B[t-1000] - (1000-d), 0)
```

The implementation uses `B - min(B, elapsed_service)`, matching the live
drain's arithmetic. It reconstructs only past service from retained past
state; it never interpolates through a future admission. At exactly one
second of delay, the source is the previous batch **after its admissions**.
At zero delay, the selector uses its original live-state path directly.

For example, if the previous post-admission workload was 800 ms, its live
workload at the next batch is zero. The 100/500/1000 ms reports are respectively
0/300/800 ms. Adding the delay to the current empty queue would be incorrect.

All task slots in the current second use the same report. The scheduler
adds this batch's acknowledged admitted work to its placement view, including
admissions from earlier slots. Each candidate reserves work only if admitted;
rejected and unavailable tasks reserve nothing. The original ascending
vehicle ordering, lowest-index tie break and reconciliation setting remain.

At the first batch there is no history. All arms use the initial live state;
the output marks this as warmup for positive delays and records actual age
zero. From the second batch onward, actual age equals requested age exactly.
Audit timestamps are elapsed milliseconds from the first trace row; trace
timestamps must be finite and one second apart. No new random draw is added.

## Interpretation limits

This is a placement-information sensitivity study under Model C's existing
batched arrivals and the explicitly added continuous-service report model.
The frozen evaluator did not previously expose intermediate-time states.
The new assumption supplies those report states without changing its
admission times, live queue evolution, or endpoint service rule.

An RSU can be idle at several report times, so different ages can correctly
produce equal reports, decisions or outcomes. In particular, a queue that
empties before the last 100 ms of a second supplies the same empty report
to the 100 ms and fresh conditions. Do not interpret such equality as general
robustness to communication delay. Distributing arrivals across the second,
delaying admission information, adding periodic polling, or omitting immediate
reservation acknowledgements would define different experiments requiring
their own controls. The older whole-second E3 resource-scaling snapshot module
is a separate contract and is not changed by this extension.

## Running

Use CPython 3.11.15 and the recorded CPU dependency versions:

```sh
uv venv --python 3.11.15 .venv
uv pip install --python .venv/bin/python -r eval/requirements-e2d-cpu.txt
uv pip install --python .venv/bin/python pytest==8.4.2
.venv/bin/python -m pytest -q tests
```

The evaluator now loads `jaxmarl/env/vec_jax.py` from its own checkout,
without an external `~/scratch` symlink or the optional JaxMARL training
wrapper. The environment source itself is unchanged.

For a short probe, use a new output directory and the frozen trace/actor:

```sh
mkdir -p results
mkdir results/delay-100-smoke
JAX_PLATFORMS=cpu JAX_ENABLE_X64=false PYTHONHASHSEED=0 \
VEC_JAX_K_MIN=0 VEC_JAX_K_MAX=5 \
.venv/bin/python eval/eval_sumo_stage1_mc.py \
  --trace /path/to/trace_inc_fullrsu.npz \
  --actor /path/to/mappo_modelc_17dim__envs128__lr3e-3__seed100_actor_params.npz \
  --max-steps 10 --seed 0 --fleet uk2030 --fleet-seed 1 \
  --rsu-cap-per-veh 2.5 --lambda-arrival 1.5 --rsu-service-mult 1.0 \
  --rsu-lb per_task_dla --rsu-state-delay-ms 100 \
  --rsu-backhaul-ms 0 --k8s-scale off \
  --substep-queue sequential --substep-queue-iters 3 \
  --rsu-cap-mode reject --veh-queue conserved \
  --out-json results/delay-100-smoke/summary.json \
  --per-step-out results/delay-100-smoke/per_step.npz \
  --per-task-out results/delay-100-smoke/per_task.npz
```

Use separate output directories for 0, 500 and 1000 ms. For the
`ingress_dla` control, omit `--rsu-state-delay-ms`. The option requires
`per_task_dla`, sequential queues, reject admission and `--k8s-scale off`;
unsupported combinations fail before loading inputs. Existing flags and
output schemas remain unchanged when the delay option is omitted.

An explicit delay adds `rsu_state_delay` metadata to the summary. The
per-step archive adds observed/captured timestamps, actual age, warmup,
reported workload, true batch-entry workload and true pre-drain workload.
The per-task archive adds the selected target's placement-view workload
immediately before each candidate, with `-1` for non-V2I attempts. Existing
task outcome and execution fields retain their meaning.

## Validation and the earlier experiments

Tests cover timestamp boundaries, empty queues, startup, JIT execution,
observed versus actual workload, live admission, reservations, rejected work,
capacity and input guards. A production test replays a six-second synthetic
trace against the frozen E2d evaluator, comparing every existing array's
shape, dtype and bytes, and all scientific summary fields (excluding wall
time). It checks both omitted delay and explicit zero, plus every inherited
placement mode. Delayed runs check the report against the previous true
pre-drain state and check queue/service-work conservation independently.

The frozen source comparison requires the base commit to be present in Git
history. It constructs an isolated minimal import adapter for the parent's
unchanged environment, matching its historical runtime setup.

These checks establish implementation compatibility in their tested cases.
They do not constitute a completed scientific campaign or a full replay of
all published E2d runs. Preserve those results and describe this as an
extension. Keep the fresh and ingress controls, actor, trace, runtime, seeds,
admission and service settings matched when running the new experiment.

Recorded local validation: **66 tests passed**, followed by five ten-step
Manchester incident trace runs (frozen parent and 0/100/500/1000 ms, fleet
seed 1, actual 2,488-slot width and ten RSUs). The zero-delay scientific
summary and every existing step/task array matched the frozen parent exactly,
excluding wall time. All delayed arms passed report-age, task/action identity,
queue/service-work conservation, finite-value and rejection/execution checks.
Each trace probe took about 25 seconds of evaluator time, including compilation;
this is not an estimate of full-campaign runtime. See the
[validation receipt](../validation/evidence/rsu_state_delay_compatibility_v1.json)
for input/source hashes, runtime versions, checks and raw artifact hashes.

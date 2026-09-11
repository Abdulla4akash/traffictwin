# E3a placement experiment on CSF3 — 11 September 2026

This additive research package executes the previously declared E3a comparison:
`ingress_dla`, `per_task_dla`, and `p2c_dla`, under fresh state and fixed 1x compute,
for fleet seeds 1–4 and evaluator seed 0 on the frozen 3600-second incident trace.
The owner asked the controller to identify the due experiment from project
records and launch the needed computation on CSF3, then instructed it to use the
records and continue. This authorizes this bounded campaign and its qualification.
The old no-execution records describe their historical release and remain intact.

The completed E0–E2d, September state-delay pilot and 32-run joint confirmation
remain separate evidence. The revised 11 September dissertation identifies E3
as unexecuted. E3 is additional work, not a prerequisite for completing that report.

## Why E3a, and why twelve runs

The historical normative JSON's `staged_design.e3a` already specifies these exact
three arms and four draws. The other stages need further design consideration.
With the production strict backlog gate (deadline at most 500ms), raw own RSU
service below 38.889ms and a 1000ms drain, initially empty RSU queues remain below
538.889ms before each drain and empty at outer-tick entry. Immediate reservations
still distinguish placement within a tick. Whole-second stale entry snapshots
and the 800ms reactive threshold therefore do not exercise their intended
mechanisms under these assumptions. This is a source-based deduction, not a
measured campaign result. Proactive forecasting can still overshoot its threshold;
it is not established to be inactive. No scaling/staleness study is launched here.

The preserved host E3 evaluator accepts tiny synthetic task batches rather than
the full incident workload. This package adds P2C to a new copy of the actual
float32 JAX evaluator and keeps the original comparators. Counter-based SplitMix64
uses two uint32 limbs so it does not enable JAX x64 or consume the actor/task RNG.
Its dense identity is `(evaluator_seed, fleet_seed, outer_tick, task_slot,
task_slot * 2488 + vehicle_slot)`. P2C filters deadline/cap feasibility before
sampling two distinct feasible RSUs, then ranks that pair by workload and RSU ID.

P2C's feasibility scan still observes all RSUs. Pair ranking counts and feasibility
counts are separate logical diagnostics. Repeated reconciliation passes are not
hidden, and logical final-pass counts must not be reported as total hardware reads,
runtime operations, or proved communication savings.

## Protocol and execution identity

`protocol.json` freezes scope, controls, contrasts, qualifications, budgets and
failure rules before replay. `qualification_reference.py` compares authenticated
September incident archives with the new comparator outputs. `validation.py`
checks the new instrumentation independently of the evaluator. `campaign.py`
enforces the manifest, runtime, Slurm allocation and immutable output directories.

The bundle manifest binds every deployed source, input and reference file plus
the exact Git commit. Its SHA is supplied externally at invocation. An independent
review receipt binds the exact pushed commit and manifest. Qualification runs ten
steps per arm, then 3600 steps per arm, all at fleet seed 1/evaluator seed 0. The
control runs must reproduce the archived discrete outcomes exactly. Qualified
runtime and storage projections gate the twelve full study cells. Qualification
executions are retained and excluded from statistical replication.

The study unit is one complete fleet draw. Report four paired differences and
their mean and Student-t interval; never count tasks as independent observations.
The actor is frozen, but observations/actions may respond to endogenous state;
matched exogenous inputs must be identical. Physical compute completion, returned
results and drops are not modelled and must not be reported as observed zeros.

## Existing CPU portability check

CSF3 job **20185137** completed on `node1201` with four CPUs, Python 3.11.15,
JAX/JAXlib 0.4.30 and NumPy 1.26.4. It replayed the archived morning per-task arm
for 300 and 10800 steps using byte-identical existing scientific source. All
inherited arrays and the unchanged accounting validator passed the predeclared
comparison checks. Slurm reported 7m44 elapsed, exit 0 and MaxRSS 1,183,140 KiB.
This qualifies that CPU control replay, not the incident workload or P2C.

The immutable operation bundle and receipts are retained locally at
`/Users/akashx/TrafficTwinCSF3/qualification-20260911` and remotely at
`/scratch/h99877sm/traffictwin/csf3-qualification-20260911`.

## Evidence sources

- Current product base: `1e01b755b8b633f43c9c7bb6fdd0d75beb6469e8`.
- Dormant E3 contract: research branch `origin/research/e3-dynamic-resource-v2`,
  `docs/evaluation/e3/e3_dynamic_resource_v2_contract_v2.json`.
- Actual evaluator parent: `docs/dissertation/joint_confirmation_2026-09-08/experimental/evaluator_v2.py`
  at the current product base; its new instrumentation extends the established evaluator.
- Archived incident comparator evaluator: VEC commit
  `908bd10f86542de94fc38af90dd56c2ccc08cf9b`.
- Incident references: `state-delay-pilot-2026-09-07/preflight/attempt_001`,
  `cells/01_fresh/attempt_001`, and `cells/05_ingress/attempt_001` under
  `/Users/akashx/Downloads/diss_mat`; each original validation receipt authenticates
  its source command and outputs. These are qualification references only.

Results and job receipts belong to the externally sealed run bundle. This source
document makes no claim that E3 has finished or that any policy has won.

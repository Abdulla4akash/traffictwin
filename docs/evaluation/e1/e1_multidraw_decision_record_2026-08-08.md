# E1 physical multi-draw campaign decision record

**Decision date:** 8 August 2026

**Researcher authority:** direct instruction from Abdulla dated 8 August 2026

**TrafficTwin parent:** `b7dd42be5d02d6c2f6bfb120d9fabf90f7b9ca66`

**Campaign manifest:**
[`e1_multidraw_physical_campaign_manifest_v1.json`](e1_multidraw_physical_campaign_manifest_v1.json)

**Manifest SHA-256:**
`0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`

**Decision:** the seed-0 scientific-design gate and later backend gate are closed. The selected
campaign backend is the established macOS arm64 CPU runtime with JAX/JAXLIB 0.4.30. New campaign
execution remains conditional on two serial ten-step smokes passing before each corresponding full
cell; no campaign cell had started when this backend decision was recorded.

This record freezes the decisions made after the descriptive
[seed-0 three-cap study](e1_seed0_three_cap_research_record_2026-08-08.md). It does not report a
multi-draw result and does not authorise E2 or another extension.

## Same-day backend amendment

Before any new E1 campaign smoke or full run, Google Colab GPU must be evaluated with the exact
pinned evaluator, actor, trace, scientific configuration and package versions. The governing
bounded test is
[e1_colab_gpu_backend_smoke_manifest_v1.json](e1_colab_gpu_backend_smoke_manifest_v1.json). It
has SHA-256 `5f6a69cea9fd479cf0c8152565bfb52d01b6f080bacf9012da8b8f87708eb5b7`
and allows two identical ten-step 2.5x/fleet-seed-0 repeats, because repeatability is part of the
validated smoke contract; it permits no full run.

The Colab result must identify the genuine JAX GPU device, packages, wall time, numerical
differences, physical accounting verdict and deterministic repeat verdict against the validated
macOS CPU smoke. Colab is a candidate only if it passes every gate and is at least 1.25x faster by
the predeclared median ten-step measure. The ten-step extrapolation remains a JIT/startup-dominated
planning estimate.

If selected, the full physical grid must use Colab exclusively and all three fleet-seed-0 cap
points must be rerun there; the confirmatory analysis must not combine the existing macOS seed-0
full outputs with Colab seeds 1-4. If Colab is invalid or not materially faster, that negative
result must be retained and the macOS CPU backend must be explicitly selected in the campaign
manifest and `RESEARCH_NEXT.md` before launch.

### G4 gate outcome

The later G4-only CLI attempt is recorded in
[e1_colab_g4_backend_smoke_report_2026-08-08.md](e1_colab_g4_backend_smoke_report_2026-08-08.md).
The requested G4 and genuine NVIDIA Blackwell device, package versions and all input hashes passed
preflight, but the first evaluator process failed at its initial JAX PRNG operation because the
pinned JAX 0.4.30 CUDA-12 `ptxas` could not compile for the assigned future architecture. It
produced no task output, so the second repeat was stopped and no speed, conservation or numerical
comparison exists. At that gate, G4 was not selected, the campaign backend remained pending and no
full cell was authorised.

### CUDA-13 compatibility outcome and final backend selection

A still-later direct instruction authorised one isolated G4 compatibility intervention with stable
JAX/JAXLIB/CUDA plugin/PJRT 0.11.0. Its immutable
[manifest](e1_g4_jax13_compatibility_smoke_manifest_v1.json), SHA-256
`d91abe1f6fb95c22387cd150e5f027483391cc72bf23e8ccd0318e71f8cbf659`, and
[result](e1_g4_jax13_compatibility_smoke_result_v1.json), SHA-256
`d713594c750396ede2d5bf3b9d850cff285170553d253b5fd1fd8944a7d0a9be`, keep that intervention
separate from the first failure.

All locked input and package identities passed on a genuine G4 RTX PRO 6000 Blackwell Server
Edition, but the very first synchronized `jax.random.PRNGKey(0)` operation failed with an observed
PJRT FFI/ABI-size mismatch. The remaining primitive operations and both evaluator repeats were not
started; there is no G4 task, conservation, repeatability or speed result.

The direct decision rule therefore stops further G4 experimentation and selects the already
validated macOS arm64 CPU environment: Python 3.11.15, JAX/JAXLIB 0.4.30, NumPy 1.26.4, SciPy
1.17.1 and `TFRT_CPU_0`. The executable SHA-256 is
`e3938f2a272dafdc33f3dd12b093dfc85354629476cb97a7d7d4a7201b8482dd`. The three validated
macOS seed-0 physical results remain reused by hash; new full cells remain fleet seeds 1-4 by all
three caps, 12 total, serialized at concurrency one. No G4 and macOS full results are mixed.
The [CPU backend selection validation](e1_macos_cpu_backend_selection_validation_v1.json), SHA-256
`faf09089ec494fab386fda9e0eb3d54f6f2b96858593f36f7896cfcb02aac1bc`, passed the exact
repository/input, interpreter/package/device, reused-seed-0, storage and output-absence preflight
without launching a campaign process.

## Research question and bounded hypotheses

The campaign asks whether the seed-0 admission-versus-queueing pattern is stable over five matched
provisional fleet draws when only the per-RSU waiting-room ceiling changes. It is not yet the
dissertation's strongest-link-versus-load-aware-placement comparison.

- **Primary null framing:** the mean paired fleet-seed difference in offered-task deadline
  attainment, `40x - 0.75x`, is zero within this bounded simulator study.
- **Directional alternative framing:** the mean paired difference is nonzero. Positive values
  favour 40x; negative values favour 0.75x.
- **Mechanism expectation, secondary:** increasing the ceiling may admit more V2I tasks and reduce
  cap rejection while increasing admitted and penalty-inclusive latency through longer waiting.
  This expectation does not substitute for the predeclared primary decision rule.

## Locked decisions

### 1. Final cap grid

All three provisional ceilings are retained:

| Label | Exact ceiling per RSU | Meaning |
|---|---:|---|
| 0.75x | 1,866 tasks | admission/in-flight waiting-room ceiling |
| 2.5x | 6,220 tasks | admission/in-flight waiting-room ceiling |
| 40x | 99,520 tasks | admission/in-flight waiting-room ceiling |

The values are source-resolved as `int(round(ratio * 2488))`. They are not computation-power
settings. The grid is retained because seed 0 showed materially different admission, rejection and
latency behaviour, and because 40x still rejected 352,967 tasks at the cap. It was therefore still
binding and cannot be described as empirically unlimited. Keeping the middle point permits a
matched replication of the observed admission-versus-queueing shape rather than reducing it to an
endpoint-only contrast.

### 2. Confirmatory semantic path

Only the corrected physical package is confirmatory:

- sequential substep queue accounting with three reconciliation iterations;
- explicit per-task RSU rejection;
- conserved vehicle queues; and
- complete task, V2I service-work and vehicle service-work accounting.

No new legacy cell will run. Existing seed-0 legacy results remain a historical diagnostic only.
The legacy snapshot/clamp path does not provide admitted identities, complete terminal outcomes or
service-work conservation, so it cannot support confirmatory replicated inference.

### 3. Fleet

The `uk2030` fleet definition is accepted provisionally for this bounded E1 replication only. It is
not a validated real-world fleet model and must not be presented as one.

### 4. Replication unit and seeds

Fleet seed is the replication unit. Fleet seeds are 0, 1, 2, 3 and 4. Evaluator seed is fixed at 0
and disclosed. Actor training seed remains 100 and trace SUMO seed remains 43. Under the original
macOS CPU plan, the exact validated seed-0 physical artifacts are reused by hash and only fleet
seeds 1-4 receive new full runs. The same-day backend amendment conditionally supersedes that
handling: if Colab is selected, seed 0 is rerun once at all three caps on Colab so every analysed
draw shares one backend; it is still one fleet-seed replicate, not artificial duplication.

Within a fleet seed, every cap must retain an identical offered-task count, `task_active` array and
`task_type` array. Individual tasks are not independent statistical observations.

### 5. Fixed controls

Every cell fixes the frozen 17-dimensional Paper-2A MAPPO actor, Manchester incident trace for
Friday 15 March 2024 from 20:00 to 21:00, 3,600 steps, 2,488 padded slots, ten RSUs, evaluator seed
0, strongest-link/default placement, load balancing off, zero backhaul cost, fixed 1x RSU service,
all scaling off and `lambda_arrival = 1.5`. The actor selects only Local, V2I or V2V and does not
observe current RSU load.

### 6. Ordinary-traffic control

No ordinary-traffic control is included. The campaign is a matched multi-draw replication of the
completed Manchester-incident seed-0 E1 study. Ordinary traffic is recorded as a later robustness
extension, not added post hoc to this matrix.

### 7. Primary estimand and decision rule

For each fleet seed, the primary estimand is:

`deadline_attainment_offered_40x - deadline_attainment_offered_0.75x`.

The five paired differences will be summarized with their mean, sample standard deviation,
standard error, two-sided 95% Student-t confidence interval with four degrees of freedom, median,
minimum and maximum. If the interval excludes zero, the report may state that there is evidence of
a directional difference within this five-draw bounded study. Otherwise the comparison is
inconclusive at this replication size. An interval containing zero is not evidence of equivalence.
No equivalence or non-inferiority claim is permitted without a separately predeclared margin.

### 8. Secondary contrasts and outcomes

The 0.75x-versus-2.5x and 2.5x-versus-40x paired comparisons are secondary. So are admitted-task
deadline attainment, cap rejection, total rejection/unavailability, penalty-inclusive latency per
offered task, latency per admitted task, available mean/p50/p95/p99 and deadline-met latency,
task-class completion, Local/V2I/V2V shares, and V2I/vehicle service-work conservation. Primary and
secondary results must remain visibly separated.

## Seed-0 evidence motivating the grid

The validated physical seed-0 observations were:

| Cap | Offered | Admitted | Total rejected/unavailable | Cap rejected | Deadline attainment / offered | Deadline attainment / admitted | Penalty latency ms / offered | Latency ms / admitted |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75x | 13,076,234 | 11,630,198 | 1,446,036 | 865,895 | 0.6837908376371974 | 0.7688096969630268 | 5,461.601257976876 | 3,808.757481858864 |
| 2.5x | 13,076,234 | 11,661,973 | 1,414,261 | 834,120 | 0.6836192285944103 | 0.7665225258196019 | 17,262.11832061127 | 12,140.312200002521 |
| 40x | 13,076,234 | 12,143,126 | 933,108 | 352,967 | 0.6836192285944103 | 0.7361502301796095 | 160,827.13705612795 | 126,782.74757784775 |

These are direct simulator observations already validated in the cumulative record. They motivate
replication; they do not establish a population-level effect or equivalence.

## Compute and output plan

The selected backend is the established local macOS arm64 CPU runtime. CSF3 remains unavailable
from this machine because the `csf3` hostname was not resolvable on 8 August 2026. Both G4 attempts
are retained pre-task failures and are no longer candidate campaign paths.

The mean of the three seed-0 physical run times was 6,026.733 seconds. Twelve new full cells project
to 20.089 run-hours, below the 48-hour ceiling. Their projected full output is 1,253,449,648 bytes;
the doubled-storage gate is 2,506,899,296 bytes. Predeclaration observed 284,091,928,576 bytes free.
Concurrency is one because the runtime exposes one TFRT CPU device using the ten-core host. Seed 0
is reused by exact hash, so the projected 12-cell total remains 20.089 CPU-hours. The first exact
execution gate is the two serial ten-step smokes for fleet seed 1 at 0.75x. Only their pass permits
that corresponding full cell.

Raw evidence remains outside Git at
`local-output:e1_outputs/e1-multidraw-physical-seeds0-4-v1`. Each unique cell directory retains its
exact command, selected environment, summary, per-step and per-task arrays, combined log, runner
status and SHA-256 file. Existing directories are never reused or overwritten. Failed and negative
outputs remain retained.

## Execution and stopping rules

The full order is seed-major, with 0.75x, 2.5x and 40x within fleet seeds 1, 2, 3 and 4. Before each
new full cell, two independent serial ten-step physical smokes must agree exactly in scientific
summary after excluding wall-clock timing and in every instrumentation array's shape, dtype and
byte hash. All physical accounting checks must pass. Smoke non-binding does not imply absence of a
cap effect; the smoke is an identity, accounting, numerical-sanity and repeatability gate.

Later cells stop immediately if any mandatory manifest condition fails, including identity drift,
repeat mismatch, within-seed task-stream mismatch, task or work nonconservation, silent loss,
NaN/infinity/unexplained negative values, cap-resolution drift, accidental placement/scaling/service
changes, overwrite risk, raw Git staging, unsafe disk/compute budget, an unpredeclared command, or
publication of a private artifact. Failed outputs and logs are retained.

## Known validity threats

- Five provisional fleet draws are a small replication set; evaluator seed remains fixed at 0.
- The `uk2030` fleet definition is provisional.
- Evidence covers one Manchester incident hour with no ordinary-traffic control.
- Per-vehicle cap resolution uses padded fleet width; the three ceilings are not real RSU capacities.
- Installed SUMO is 1.27.1 while trace provenance is 1.27.0. The evaluator replays the NPZ and does
  not invoke SUMO, but this is not an exact canonical SUMO 1.27.0 reproduction.
- The simulator intervention supports controlled within-simulator attribution only, not
  real-world causal or optimality claims.
- The actor does not observe current RSU load; this campaign varies admission capacity, not actor or
  infrastructure placement intelligence.

## Unsupported claims

This campaign cannot establish formal equivalence, non-inferiority, real-world optimality, a real
Kubernetes deployment, native physical completion/result return, or validated UK fleet realism. It
does not test strongest-link against a load-aware controller. It does not make old `tos-data`
results corrected-engine baselines. Randy's reported `0.6943` remains unreproduced.

## Authority boundary and next gate

The backend selection, final matrix, seed-0 reuse, concurrency and runtime estimate must be committed
and pushed before campaign execution. The exact next gate is two serial ten-step macOS CPU smokes
for fleet seed 1 at 0.75x. Their deterministic identity, task/work conservation, finite/nonnegative,
storage and no-overwrite checks must all pass before the corresponding full cell may start. Failure
of any gate revokes authority for subsequent cells. E2 and every other extension remain prohibited
pending a new reviewed direction.

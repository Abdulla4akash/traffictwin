# E1 fleet-seed-1 three-cap campaign report

**Date:** 8 August 2026

**Verdict:** fleet seed 1 passed the repeated-smoke and full-cell validity gates at 0.75x, 2.5x
and 40x. The within-seed comparison passed all 31 checks. Execution stopped before fleet seed 2.

**Governing manifest:**
[`e1_multidraw_physical_campaign_manifest_v1.json`](e1_multidraw_physical_campaign_manifest_v1.json),
SHA-256 `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`

**Machine-readable records:**

- [within-seed validation](e1_seed1_three_cap_validation_v1.json), SHA-256
  `cfb6e076cb70f7aeb4143f7a91c33bd2b04c9af6d4af60b2b082b87889dd58db`;
- [within-seed comparison](e1_seed1_three_cap_comparison_v1.json), SHA-256
  `0f2ea863a91419412130f70d201814ff7f75fcce7f03019afaa48c6132709c5d`.

## Question and bounded hypotheses

This gate asks only how the three provisional RSU waiting-room ceilings behave for fleet seed 1
under the corrected physical semantics. It does not answer the eventual infrastructure-placement
research question.

The descriptive alternatives were that raising the ceiling could improve offered-task deadline
attainment by reducing rejection, leave it numerically unchanged while increasing queueing, or
harm it because more admitted work waits too long. No inferential null, equivalence margin or
non-inferiority margin is tested at one fleet seed. The predeclared five-draw primary estimand is
not calculated here.

## Frozen design and provenance

All three cells used evaluator seed 0, fleet seed 1, the frozen 17-dimensional Paper-2A MAPPO
actor, the Manchester incident trace for 15 March 2024 from 20:00-21:00, 3,600 steps, strongest
link/default placement, fixed 1x service, sequential substep accounting, explicit rejection,
conserved vehicle queues, zero backhaul, and load balancing/scaling off.

TrafficTwin was at execution parent `fcc4602d337de4824fb3b23ead9697aba41c3621`;
vec_env remained clean at `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`; tos-data remained
clean at `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`. The backend was
`macos_arm64_cpu_jax_0_4_30` with Python 3.11.15, JAX/JAXLIB 0.4.30 and `TFRT_CPU_0`.

Local SUMO remained 1.27.1 while trace provenance names 1.27.0. The evaluator replayed the frozen
NPZ and did not invoke SUMO, but this remains a compatibility mismatch and is not an exact
canonical SUMO reproduction.

## Gate results

The accepted 0.75x cell and both new cap cells passed two serial ten-step smokes. For 2.5x, the
evaluator times were 12.9 and 12.7 seconds; for 40x they were 15.0 and 16.4 seconds. Within each
cell, the scientific summaries were identical after excluding wall time, and every instrumentation
array matched in shape, dtype and bytes. Offered count, `task_active` and `task_type` also matched
across all three caps.

Each 3,600-step full cell passed all 32 accounting, conservation and numerical checks. Evaluator
wall times for 0.75x, 2.5x and 40x were 6,440.6, 7,077.9 and 7,379.8 seconds respectively. The two
new runner wall times were 7,102.692 and 7,401.016 seconds.

## Direct observations

The waiting-room ceiling is an admission/in-flight limit, not compute power.

| Measure | 0.75x (1,866) | 2.5x (6,220) | 40x (99,520) |
|---|---:|---:|---:|
| Offered tasks | 13,076,234 | 13,076,234 | 13,076,234 |
| Admitted tasks | 11,779,070 | 11,805,950 | 12,149,755 |
| Rejected/unavailable | 1,297,164 | 1,270,284 | 926,479 |
| Rejection fraction / offered | 0.0992001 | 0.0971445 | 0.0708521 |
| V2I cap rejection | 639,848 | 612,968 | 269,163 |
| Deadline-met tasks | 9,001,257 | 8,999,660 | 8,999,660 |
| Deadline attainment / offered | 0.688367691 | 0.688245561 | 0.688245561 |
| Deadline attainment / admitted | 0.764173827 | 0.762298671 | 0.740727694 |
| Penalty-inclusive latency / offered | 4,642.546 ms | 14,519.940 ms | 117,993.732 ms |
| Latency / admitted | 3,412.179 ms | 10,805.719 ms | 91,659.184 ms |
| Admitted latency p95 | 29,306.017 ms | 98,655.953 ms | 733,367.087 ms |
| Admitted latency p99 | 29,975.150 ms | 99,871.668 ms | 1,588,365.432 ms |

Local-queue rejection remained 38,444; V2V helper-queue rejection remained 618,761; V2I
unavailability remained 111; V2I gate and V2V-unavailable outcomes remained zero. The cap
intervention changed V2I cap admission while the actor's Local/V2I/V2V decisions stayed fixed.

## Code-derived within-seed contrasts

All differences below are higher cap minus lower cap.

| Contrast | Admitted tasks | Rejected/unavailable | Offered deadline attainment | Admitted deadline attainment | Offered penalty latency | Admitted latency |
|---|---:|---:|---:|---:|---:|---:|
| 2.5x - 0.75x | +26,880 | -26,880 | -0.000122130 | -0.001875156 | +9,877.394 ms | +7,393.540 ms |
| 40x - 2.5x | +343,805 | -343,805 | 0.000000000 | -0.021570978 | +103,473.792 ms | +80,853.465 ms |
| 40x - 0.75x | +370,685 | -370,685 | -0.000122130 | -0.023446133 | +113,351.186 ms | +88,247.005 ms |

The equality of the observed 2.5x and 40x offered-task values is a numerical observation for this
draw, not evidence of formal equivalence or a tie. The 40x ceiling remained binding, with 269,163
V2I cap rejections, and therefore is not empirically unlimited.

## Conservation

All task outcomes reconciled and every active task had exactly one terminal outcome. No NaN,
infinity, unexplained negative value or silent task loss was found. Offered and admitted deadline
denominators remained separate.

V2I work conserved in milliseconds:

- 0.75x: `40,107,836 = 29,815,326 + 10,292,510`;
- 2.5x: `40,107,836 = 30,252,578 + 9,855,258`;
- 40x: `40,107,836 = 35,782,356 + 4,325,480`.

Vehicle work was identical and conserved at every cap:
`282,604,672 = 270,455,040 + 12,149,632` milliseconds.

## Comparison with seed 0

The code-derived qualitative pattern matched the retained seed-0 physical three-cap comparison on
all seven declared fields:

- admissions increased and total/V2I-cap rejection decreased as the ceiling rose;
- offered-task deadline attainment decreased slightly from 0.75x to 2.5x and then plateaued at
  40x;
- admitted-task deadline attainment was nonincreasing;
- penalty-inclusive offered latency and admitted latency were nondecreasing.

The offered-attainment range was 0.000122130 for seed 1 and 0.000171609 for seed 0. These two
descriptive draws support retention of the admission-versus-queueing pattern as a hypothesis for
the remaining replications. They do not establish a population effect or justify pooling tasks as
independent observations.

## Evidence and limitations

Raw evidence remains outside Git at
`local-output:e1_outputs/e1-multidraw-physical-seeds0-4-v1/fleet_seed_1`. The complete 89-file
checksum index has SHA-256
`f7b9cdbc7f74a465a06bf2f0f11e1792eb9b97b286669eb67280fbd4fad045df`; every indexed file
passed verification.

The uk2030 fleet and all three cap values remain provisional. This is one new fleet draw, one
incident window, one frozen actor and a fixed evaluator seed. Deadline attainment is a simulated
outcome, not confirmed native physical completion or result return. Randy's reported `0.6943`
remains unreproduced. No E2, scaling, retraining, prediction, bus modelling or backend experiment
was started.

## Stop and next gate

Execution stopped before fleet seed 2. No five-draw inference has been calculated. The next action
is researcher review of this seed-1 record. If continuation is explicitly directed, the next
manifest cell is fleet seed 2 at 0.75x, beginning with two serial ten-step smokes; no full cell is
permitted until that separate gate passes.

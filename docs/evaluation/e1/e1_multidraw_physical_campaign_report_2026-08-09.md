# E1 physical multi-draw campaign report

**Completion date:** 9 August 2026

**Verdict:** all 24 predeclared smoke runs and all 12 new full cells passed. The five-draw primary comparison is inconclusive at this replication size; it is not an equivalence or non-inferiority result.

**Governing manifest:** [`e1_multidraw_physical_campaign_manifest_v1.json`](e1_multidraw_physical_campaign_manifest_v1.json), SHA-256 `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`

**Machine-readable records:**

- [campaign validation](e1_multidraw_physical_campaign_validation_v1.json), SHA-256 `f1edacf318109eb0b9ccb7c8848b68fa199056c78d8329e1aa5e92c2e2395e0b`;
- [campaign comparison](e1_multidraw_physical_campaign_comparison_v1.json), SHA-256 `b2f7e8bf8769e7359bf5731b4b98d1007d294ed55595ec4977886f976d600ec3`;
- [result summary](e1_multidraw_physical_campaign_result_summary_v1.json), SHA-256 `bd0b81fcdfc65986f8eb1de10a972aeec0c96ddda8568d70518c0490a6ad2ce8`;
- [evidence index](e1_multidraw_physical_campaign_evidence_index_v1.json), SHA-256 `aeecdece2cbfffef4d7e68ac398c42fb2f36af5a6a1256536f58186c547f74e5`.

## Research question and hypotheses

This campaign asks whether the seed-0 admission-versus-queueing pattern is stable over five matched provisional fleet draws when only the per-RSU waiting-room ceiling changes. It does not compare strongest-link placement with a load-aware controller.

The primary null framing is a zero mean paired fleet-seed difference in offered-task deadline attainment for `40x - 0.75x`; the directional alternative is nonzero. Positive values favour 40x and negative values favour 0.75x. The secondary mechanism expectation is that a higher ceiling can reduce rejection while increasing queueing latency.

## Locked design and provenance

All cells used evaluator seed 0, fleet seeds 0-4 as matched replication units, the frozen 17-dimensional Paper-2A MAPPO actor, the Manchester incident trace for Friday 15 March 2024 from 20:00-21:00, 3,600 steps, strongest-link/default placement, sequential substep accounting, explicit physical rejection, conserved vehicle queues, fixed 1x service, zero backhaul and load balancing/scaling off. The cap points were 1,866, 6,220 and 99,520 tasks per RSU; these are waiting-room/admission ceilings, not compute power.

TrafficTwin execution used commit `5111cbc23ec16b031435b2aba5a11e9f9074d3e9`. vec_env remained at `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` and tos-data at `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`. The backend was `macos_arm64_cpu_jax_0_4_30` with Python 3.11.15, JAX/JAXLIB 0.4.30 and `TFRT_CPU_0`.
The evaluator SHA-256 was `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`; actor SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`; and trace SHA-256 `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`.

Local SUMO was 1.27.1 while trace provenance names 1.27.0. The evaluator replayed the frozen NPZ and did not invoke SUMO, so this is not an exact canonical SUMO reproduction.

## Campaign and gate results

The three seed-0 full records were reused by exact hash. Fleet seeds 1-4 contributed 12 new full cells. Every new cell first passed two serial ten-step smokes with identical scientific summaries after wall time was excluded and exact instrumentation identity. Every full run then passed all 32 accounting, conservation and numerical checks.

The 12 new evaluator runs consumed 23.662 wall-hours at concurrency one, within the 48 CPU-hour bound. No cell failed or stopped.

## Direct observations

| Fleet seed | Cap | Offered | Admitted | Rejected/unavailable | Offered attainment | Admitted attainment | Penalty latency / offered (ms) | Latency / admitted (ms) | V2I cap rejected | Wall time (s) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0p75 | 13,076,234 | 11,630,198 | 1,446,036 | 0.683790838 | 0.768809697 | 5461.601 | 3808.757 | 865,895 | 5709.9 |
| 0 | 2p5 | 13,076,234 | 11,661,973 | 1,414,261 | 0.683619229 | 0.766522526 | 17262.118 | 12140.312 | 834,120 | 5870.3 |
| 0 | 40x | 13,076,234 | 12,143,126 | 933,108 | 0.683619229 | 0.736150230 | 160827.137 | 126782.748 | 352,967 | 6500.0 |
| 1 | 0p75 | 13,076,234 | 11,779,070 | 1,297,164 | 0.688367691 | 0.764173827 | 4642.546 | 3412.179 | 639,848 | 6440.6 |
| 1 | 2p5 | 13,076,234 | 11,805,950 | 1,270,284 | 0.688245561 | 0.762298671 | 14519.940 | 10805.719 | 612,968 | 7077.9 |
| 1 | 40x | 13,076,234 | 12,149,755 | 926,479 | 0.688245561 | 0.740727694 | 117993.732 | 91659.184 | 269,163 | 7379.8 |
| 2 | 0p75 | 13,076,234 | 11,487,269 | 1,588,965 | 0.672495613 | 0.765517896 | 5766.406 | 3830.263 | 1,008,169 | 6666.1 |
| 2 | 2p5 | 13,076,234 | 11,517,771 | 1,558,463 | 0.672495613 | 0.763490609 | 18568.223 | 12523.297 | 977,667 | 6436.2 |
| 2 | 40x | 13,076,234 | 12,088,334 | 987,900 | 0.672495613 | 0.727454255 | 190432.480 | 152020.734 | 407,104 | 6287.0 |
| 3 | 0p75 | 13,076,234 | 11,529,285 | 1,546,949 | 0.670291538 | 0.760228323 | 5582.432 | 3761.606 | 949,566 | 6282.9 |
| 3 | 2p5 | 13,076,234 | 11,560,414 | 1,515,820 | 0.670038101 | 0.757894570 | 17837.518 | 12170.657 | 918,437 | 6822.2 |
| 3 | 40x | 13,076,234 | 12,043,357 | 1,032,877 | 0.670038101 | 0.727502722 | 175059.602 | 132346.967 | 435,494 | 8361.5 |
| 4 | 0p75 | 13,076,234 | 11,509,474 | 1,566,760 | 0.676422967 | 0.768502974 | 6069.204 | 4037.195 | 1,067,026 | 8102.9 |
| 4 | 2p5 | 13,076,234 | 11,539,582 | 1,536,652 | 0.676422967 | 0.766497868 | 19706.681 | 13317.202 | 1,036,918 | 7490.7 |
| 4 | 40x | 13,076,234 | 12,116,297 | 959,937 | 0.676422967 | 0.730013881 | 204058.692 | 159632.328 | 460,203 | 7835.1 |

## Primary matched analysis

The five raw `40x - 0.75x` offered-deadline differences, in fleet-seed order 0-4, were: `-0.000171609043, -0.000122129965, 0.000000000000, -0.000253436884, 0.000000000000`.

| Statistic | Value |
|---|---:|
| Mean | -0.000109435178 |
| Sample standard deviation | 0.000110357776 |
| Standard error | 0.000049353498 |
| Two-sided 95% Student-t CI | [-0.000246462456, 0.000027592099] |
| Median | -0.000122129965 |
| Minimum | -0.000253436884 |
| Maximum | 0.000000000000 |

The interval includes zero. Under the predeclared rule, the comparison is **inconclusive at this replication size**. The individual tasks were not treated as independent statistical replicates.

## Secondary contrasts and mechanism

For `2.5x - 0.75x`, the mean offered-attainment difference was -0.000109435178 with 95% CI [-0.000246462456, 0.000027592099]; this was also inconclusive.

For `40x - 2.5x`, all five offered-attainment differences were numerically zero. This exact observation is not evidence of formal equivalence or a tie because no equivalence margin or non-inferiority design was predeclared.

Across every fleet draw, 40x admitted more tasks and rejected fewer than 0.75x, while admitted-task attainment fell and both admitted and penalty-inclusive offered latency rose sharply. The 40x ceiling remained binding in every seed. Actor Local/V2I/V2V decision shares were unchanged across caps within each seed; the intervention changed downstream admission and queueing, not actor decisions.

## Conservation and reproducibility

All 15 full cells passed complete task accounting, rejection reconciliation, terminal outcome uniqueness, finite/nonnegative checks, offered/admitted denominator separation, V2I work conservation and vehicle-work conservation. Work is measured in milliseconds of service work. Offered count, `task_active` and `task_type` were identical across caps within every fleet seed. No silent task loss was observed.

## Evidence, failures and validity threats

Raw evidence remains outside Git at `local-output:e1_outputs/e1-multidraw-physical-seeds0-4-v1`. The campaign directory contains 369 files totalling 1261337011 bytes. The evidence index retains each cell's smoke/full validation hashes and every authoritative full-output hash. There were no failed or stopped scientific cells. The initial direct-file controller invocation failed before imports, evidence creation or evaluator launch; module-mode invocation then executed the unchanged committed controller.

Validity threats are five provisional fleet draws, a fixed evaluator seed, one incident hour, no ordinary-traffic control, a provisional `uk2030` fleet, padded-width cap resolution, and the SUMO 1.27.1/1.27.0 provenance mismatch. Results support only this controlled simulator intervention, not real-world causal or optimality claims.

Deadline attainment is a simulated outcome, not confirmed native physical completion or result return. Randy's reported `0.6943` remains unreproduced. No E2, load-aware placement, scaling, retraining, prediction, bus modelling or backend investigation ran.

## Interpretation and exact next gate

The bounded evidence is consistent with an admission-versus-queueing trade-off: higher ceilings reduce rejection but substantially increase latency, without a conclusive five-draw change in offered-task deadline attainment. This is an interpretation of the controlled simulator observations, not a claim of equivalence or real-world policy superiority.

The E1 campaign gate is complete. Stop for researcher review. E2 and every extension remain unauthorised; the next task requires a new direct instruction.

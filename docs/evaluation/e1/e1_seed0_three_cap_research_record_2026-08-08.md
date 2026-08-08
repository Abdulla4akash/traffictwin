# E0-to-E1 seed-0 corrected-evaluator research record

Date: 2026-08-08

Status: **E0 passed; the bounded E1 three-cap seed-0/fleet-0 pilot passed its validity checks and
is complete for descriptive use; E1 replication and E2 remain unstarted**.

This is the cumulative human-readable record for the corrected evaluator work executed on 7-8
August 2026. The companion
[machine-readable research summary](e1_seed0_three_cap_research_summary_v1.json) points to every
authoritative manifest and validation record by path and SHA-256. The summary's SHA-256 is
`346a9bdd9ecd3a24d9e77d7e3050d1e54054e54f82f0f499ade0353874b31133`.

## Executive conclusion

The corrected physical evaluator accounted for every offered task and conserved V2I and vehicle
service work in the repeated bounded smoke and all three full cap points. Exact input and task-
stream identities were retained across the matched comparisons.

For evaluator seed 0 and fleet seed 0, increasing the provisional per-RSU waiting-room ceiling
from 1,866 to 99,520 tasks admitted more work and reduced explicit cap rejection, but greatly
increased penalty-inclusive latency. Offered-task deadline attainment across the three physical
points spanned only 0.01716090427871242 percentage points. This narrow span is descriptive, not a
formal equivalence or tie result. The 40x ceiling still produced 352,967 cap rejections and was not
empirically unbounded.

The legacy path produced different completion and latency values on the same offered task stream,
but it lacks admitted identities, terminal outcomes and a service-work ledger. It is an explicitly
non-conserving historical-control diagnostic, not a valid physical baseline.

Nothing here tests load-aware placement. Randy's reported `0.6943` has not been reproduced.

## Question hierarchy

The eventual dissertation question is:

> Given a frozen vehicle actor that chooses only Local, V2I or V2V and does not observe current
> RSU load, when does downstream infrastructure-side load-aware placement improve, tie or harm
> task outcomes relative to strongest-link placement?

This execution did not answer that question. It addressed two prerequisite questions:

1. **E0 validity:** does the corrected evaluator account for every offered task, retain separate
   offered/admitted denominators and conserve service work?
2. **E1 semantics and admission sensitivity:** what is observed under legacy
   snapshot/clamp/legacy and physical sequential/reject/conserved semantics at provisional 0.75x,
   2.5x and 40x waiting-room ceilings?

E2—strongest-link versus downstream load-aware placement—remains a future comparison.

## Evidence and truth hierarchy

The evidence order used throughout this record is:

1. supervisor direction defines the research question and correction;
2. Randy's email and Q&A clarify reported history and proposed semantics;
3. pinned source establishes what the inspected evaluator implements;
4. predeclared manifests establish what each new run intended to do;
5. raw outputs and deterministic validation establish what was observed;
6. this prose interprets those machine records without recalculating metrics.

Reported historical results do not become reproduced evidence without their original manifest,
commands, actor identity, seeds and raw outputs. Synthetic TrafficTwin prototypes are not native
VEC evidence. A simulated deadline-met outcome is not a confirmed physical execution completion
or result return.

## Hypotheses and evaluation status

### E0-HV1: task and work conservation

The corrected physical evaluator should satisfy:

`offered = admitted + every explicit terminal rejection or unavailability reason`

and should separately conserve V2I and vehicle service work in milliseconds. This validity
hypothesis was supported for both ten-step repeats and the full seed-0 reference.

### E0-HV2: deterministic bounded repeatability

With identical actor, trace, seeds, environment variables and argv, repeated ten-step executions
should have identical scientific summaries after excluding wall time and identical dtype, shape
and byte identities for every instrumentation array. This was supported by the corrected E0
repeats and by both arms of the later 0.75x and 40x smoke gates.

### E1-H1: bundled semantic sensitivity

The predeclared E1 manifests allowed the legacy and physical semantic packages to produce
different offered-task completion and latency, with no assumed direction. The paths differed at
all three caps. Because three semantics change together, this does not identify the effect of
snapshot accounting, clamp admission or legacy vehicle queues individually.

### E1-H2: waiting-room admission/latency tradeoff

The supervisor correction suggested that reducing the waiting room could reject work earlier and
therefore reduce latency without increasing compute speed. The predeclared cap hypotheses remained
directionally agnostic about offered-task attainment. At this seed, higher ceilings admitted more
tasks and reduced cap rejection while latency increased. No population-level or causal cap claim
is supported without replication.

### E2-H1: load-aware placement

Infrastructure-side load-aware placement may improve, tie or harm outcomes relative to strongest-
link placement. This hypothesis is untested here. Load balancing remained off in every run.

## Experimental design

### Fixed inputs

| Item | Identity or setting |
|---|---|
| TrafficTwin | E0 started at `95e7b1e4048a11a2002473e83eb0aa1c584c9bbc`; cumulative record branch `agent/e1-waiting-room-40x-v1` at prior evidence commit `7b42c260815e76e12b28223fbd224b613aa92ca2` |
| vec_env | commit `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` |
| tos-data | commit `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` |
| Evaluator | `eval/eval_sumo_stage1_mc.py`; SHA-256 `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669` |
| Frozen actor | 17-dimensional Paper-2A MAPPO actor; SHA-256 `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` |
| Actor choices | Local, V2I or V2V; current RSU load is not in its observation |
| Trace | Manchester incident; SHA-256 `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056` |
| Window | Friday 15 March 2024, 20:00-21:00; 3,600 steps; 2,488 padded fleet slots; 10 RSUs |
| Seeds | evaluator 0; fleet 0; actor training 100; trace SUMO 43 |
| Fleet | provisional `uk2030` preset |
| Placement | strongest-link/default; load balancing off; backhaul cost 0 ms |
| Compute service | fixed 1x; scaling off |
| Arrival setting | `lambda_arrival=1.5` |

The runtime was Python 3.11.15, JAX/JAXLIB 0.4.30, NumPy 1.26.4 and CPU backend on macOS arm64.
Installed SUMO 1.27.1 differs from trace provenance SUMO 1.27.0. The evaluator replayed the NPZ
and did not invoke SUMO, so these are not exact canonical SUMO 1.27.0 reproductions.

### Experimental arms

| Arm | Substep accounting | RSU admission | Vehicle queue | Evidence boundary |
|---|---|---|---|---|
| Legacy | snapshot | clamp | legacy | No admitted identities, terminal outcomes or work ledger; conservation unavailable |
| Physical | sequential, three iterations | explicit per-task reject | conserved | Offered/admitted/rejected and work ledgers available |

The contrast is deliberately described as a bundled semantics comparison. It is not a component
ablation.

### Cap definition

The evaluator resolves `rsu_cap_per_veh` as `int(round(ratio * padded fleet width))`:

| Provisional multiplier | Resolved ceiling | Meaning |
|---:|---:|---|
| 0.75x | 1,866 tasks per RSU | admission/in-flight waiting-room ceiling |
| 2.5x | 6,220 tasks per RSU | admission/in-flight waiting-room ceiling |
| 40x | 99,520 tasks per RSU | admission/in-flight waiting-room ceiling |

These values are not compute power, CPU cores or Kubernetes deployments. All service remained at
fixed 1x and simulated scaling remained off.

### Stop/go sequence

Each new cap unit was predeclared before execution. New semantic arms began with two serial
ten-step repeats. A full run was allowed only after input identity, task accounting, numeric
sanity, available work conservation and repeat stability passed. Legacy full runs had an interim
25-check gate before the matched physical full run. Any failed invariant would have stopped the
sequence before later cells.

The 2.5x physical arm is the exact independently predeclared and validated E0 full reference; it
was reused by hash rather than rerun. The 2.5x E1 unit added the missing legacy arm. The 0.75x and
40x units ran both arms.

## Authorization and decision conversation

This section records execution governance, not scientific evidence. It is a concise decision log,
not a transcript.

| Date | Decision |
|---|---|
| 2026-08-07 | Begin only with the bounded E0 smoke. Do not start a full campaign, retrain MAPPO, run E2 or push to Randy's repositories. |
| 2026-08-07 | After E0 smoke passed, authorize one full corrected strongest-link reference under the same physical semantics. |
| 2026-08-07 | Continue with the bounded 2.5x E1 pair, reusing the exact validated E0 physical arm and running only the missing legacy arm. |
| 2026-08-08 | Continue one bounded cap unit at a time: first 0.75x, then the remaining 40x pair, each with repeated smoke and stop/go validation. |
| 2026-08-08 | Publish a cumulative record of hypotheses, experiment, observations, results, interpretation and limitations. Do not launch seeds 1-4 or E2 automatically. |

Throughout the sequence, the unrelated untracked PDF was preserved, raw actor/trace/run artifacts
stayed outside Git, and neither external repository was modified or pushed.

## E0 observations and result

The two corrected ten-step repeats each passed 32/32 checks and were identical in scientific
summary and instrumentation-array identity. They observed:

`36,856 offered = 35,195 admitted + 108 local MQD rejected + 1,553 V2V MQD rejected`.

They also conserved V2I work as `122,473 = 122,473 + 0` ms and vehicle work as
`820,565.8125 = 789,046.9375 + 31,518.875` ms. The ten-step window did not exercise RSU-cap or
unavailability rejection.

The subsequent full corrected 2.5x strongest-link reference passed 32/32 checks and observed:

- `13,076,234` offered tasks;
- `11,661,973` admitted tasks;
- `1,414,261` terminal rejection/unavailability outcomes;
- offered-denominator deadline attainment `0.6836192285944103`;
- admitted-denominator deadline attainment `0.7665225258196019`.

This established a corrected, conserved reference under a provisional configuration. It did not
establish a controller baseline comparison or reproduce Randy's result.

## E1 repeated-smoke observations

At both newly executed 0.75x and 40x points:

- two legacy smokes passed 25/25 available checks each;
- two physical smokes passed 32/32 checks each;
- the scientific summary and instrumentation arrays were identical within each arm;
- cross-arm offered count, task-active mask and task type were identical;
- the first ten steps did not bind the RSU cap, so the smoke demonstrated accounting and
  repeatability rather than cap response.

The 2.5x legacy repeated smoke had already passed the same 25/25 available-check contract. The
corrected E0 smoke supplied the repeated physical evidence for that configuration.

## E1 full results

Every legacy full scan passed 25/25 available common checks. Every physical full run passed 32/32
checks, including offered/admitted/rejected and V2I/vehicle work conservation. Cross-arm task-
stream identities matched at each cap, and the three-cap comparator passed 31/31 checks.

### Physical sequential/reject/conserved arm

Values below are copied from the code-generated three-cap comparison.

| Cap | Offered | Admitted | Rejected/unavailable | RSU-cap rejected | Offered deadline attainment | Admitted deadline attainment | Penalty-inclusive latency per offered task (ms) | Latency per admitted task (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75x | 13,076,234 | 11,630,198 | 1,446,036 | 865,895 | 0.6837908376371974 | 0.7688096969630268 | 5,461.601257976876 | 3,808.757481858864 |
| 2.5x | 13,076,234 | 11,661,973 | 1,414,261 | 834,120 | 0.6836192285944103 | 0.7665225258196019 | 17,262.11832061127 | 12,140.312200002521 |
| 40x | 13,076,234 | 12,143,126 | 933,108 | 352,967 | 0.6836192285944103 | 0.7361502301796095 | 160,827.13705612795 | 126,782.74757784775 |

Other terminal reasons were invariant across these three physical runs: 34,124 local MQD
rejections, 545,879 V2V MQD rejections, 138 V2I-unavailable outcomes, and zero V2V-unavailable or
gate outcomes.

### Legacy snapshot/clamp/legacy arm

| Cap | Offered | Offered deadline attainment | Penalty-inclusive latency per offered task (ms) | Admitted/rejected/work evidence |
|---:|---:|---:|---:|---|
| 0.75x | 13,076,234 | 0.7290600642356201 | 5,314.834518868353 | unavailable |
| 2.5x | 13,076,234 | 0.7286572724226257 | 17,116.584494281764 | unavailable |
| 40x | 13,076,234 | 0.7286572724226257 | 160,676.9823127974 | unavailable |

Legacy zero-valued rejection fields are source placeholders. They are not evidence that no tasks
were rejected, and no admitted-denominator metric may be inferred.

### Physical minus legacy within each cap

| Cap | Offered-deadline-attainment delta | Percentage-point delta | Penalty-inclusive offered-latency delta (ms) |
|---:|---:|---:|---:|
| 0.75x | -0.045269226598422696 | -4.52692265984227 | +146.76673910852242 |
| 2.5x | -0.04503804382821541 | -4.503804382821541 | +145.53382632950525 |
| 40x | -0.04503804382821541 | -4.503804382821541 | +150.15474333055317 |

These deltas compare a conserved physical path with a non-conserving legacy path and cannot be
read as a conventional treatment effect.

### Code-generated physical cap deltas

| Comparison | Admitted delta | Rejected delta | Cap-rejection delta | Offered-attainment delta (percentage points) | Admitted-attainment delta (percentage points) | Offered-latency delta (ms) |
|---|---:|---:|---:|---:|---:|---:|
| 0.75x to 2.5x | +31,775 | -31,775 | -31,775 | -0.01716090427871242 | -0.22871711434249153 | +11,800.517062634393 |
| 2.5x to 40x | +481,153 | -481,153 | -481,153 | 0.0 | -3.037229563999244 | +143,565.01873551667 |
| 0.75x to 40x | +512,928 | -512,928 | -512,928 | -0.01716090427871242 | -3.2659466783417357 | +155,365.53579815108 |

## Direct observations

The following statements are direct descriptions of validated records:

1. Offered task count and the active/type task stream were identical across all matched arms and
   all three cap points.
2. Physical admissions were nondecreasing and physical cap rejections were nonincreasing as the
   ceiling increased.
3. Physical penalty-inclusive offered latency was nondecreasing as the ceiling increased.
4. Offered-task deadline attainment across the physical cap points spanned
   `0.0001716090427871242`, or `0.01716090427871242` percentage points.
5. Admitted-denominator deadline attainment decreased as the cap increased in this seed-0 record.
6. The 40x ceiling still bound, with 352,967 RSU-cap rejections.
7. The physical deadline-met numerator at 2.5x and 40x was identical, while their admitted and
   rejected populations differed. No formal tie test was performed.
8. Legacy and physical offered-task outputs differed even though their offered task streams were
   identical.

## Interpretation

### What the record supports

The waiting-room ceiling is consequential in this evaluator even when offered-task deadline
attainment changes little. A larger waiting room converts some early cap rejections into admitted
tasks, but those tasks can spend much longer in queues. This exposes why completion over offered
tasks, completion over admitted tasks, explicit rejection reasons and latency denominators must be
reported together.

The seed-0 pattern is consistent with the supervisor's fail-fast interpretation: reducing the
admission ceiling can shorten measured queue latency because work is rejected earlier. It does not
show that RSU computation became faster; service stayed fixed at 1x.

The legacy path can appear to have higher offered-task deadline attainment, but its scoring is not
backed by the corrected physical task/work conservation contract. The appropriate conclusion is
that evaluator semantics materially affect reported outcomes, not that legacy is a superior
physical system.

### What the record does not support

- no formal equivalence, non-inferiority or tie claim;
- no confidence interval, variance estimate or multi-seed generalisation;
- no component-level attribution among clamp, snapshot or vehicle-queue semantics;
- no approved real-world RSU buffer recommendation;
- no compute-power or Kubernetes-deployment interpretation of the cap;
- no strongest-link versus load-aware-placement conclusion;
- no native physical completion or result-return claim;
- no reproduction of Randy's `0.6943` or historical sweep.

## Validity threats and limitations

### Internal validity

- The legacy-versus-physical contrast changes three semantics together.
- Legacy does not emit enough information for the physical conservation contract.
- The 2.5x physical arm was reused from E0 by exact hashes; this strengthens identity but means
  its execution occurred in the preceding bounded unit rather than alongside the legacy scan.
- The trace lacks an `enter` channel and therefore uses mask-only reset semantics.

### Statistical conclusion validity

- Only evaluator seed 0 and fleet seed 0 were run.
- No uncertainty interval or formal tie margin was predeclared.
- Exact numerical equality at two points is not statistical equivalence.

### Construct validity

- Deadline attainment is simulated, not a native physical result-return event.
- The per-RSU ceiling is an admission/in-flight task limit, not processing power.
- The `uk2030` fleet and all three cap values remain provisional.

### External validity

- Evidence covers one Manchester incident trace, one hour, one actor, one fleet draw and one
  strongest-link configuration.
- No free-flow counterpart, other date/window, additional seed or alternative actor was tested.
- Installed SUMO differs from trace provenance, although SUMO was not invoked during NPZ replay.

## Reproducibility and evidence index

| Stage | Manifest SHA-256 | Validation SHA-256 | Decision |
|---|---|---|---|
| E0 10-step repeated smoke | `8d81cf30f1ada3e9af7c799c9ebd0e01a427a67c570f583b658b11717a5eab93` | `ff095ac91765c1e59410c4b902ff47e018cf00a7c9513ca33e2983a8e18ae38d` | PASS |
| E0 full corrected 2.5x reference | `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f` | `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa` | PASS |
| E1 2.5x semantics pair | `318b909749f514833eba4a09bc34978b33bdefd570bfc3d59e189cebe9334bf5` | `3a0227d355852c68273d4c9b0159782f98d9a345a11528b19ddd5b36feedd10a` | PASS with legacy conservation unavailable |
| E1 0.75x semantics pair | `d299998d0346aa20466afcb156868cff6fabd614d15c5a91dc6427f58d857b5d` | `1b0ce7612fda194cb91ed70d01b4f18dfecd7d06b7d77a14c38480ab734fc09e` | PASS with legacy conservation unavailable |
| E1 40x semantics pair | `f156d19ed8d59bff479c6f3767291acc2e5c681bdc8e4d630665aba67c3c10e8` | `fc8ec5b33c2e0b5de74e86fbf4545b36234eda6e65d1208295632632d9e91ad6` | PASS with legacy conservation unavailable |

The authoritative cross-cap comparison is
[e1_three_cap_sweep_seed0_v1.json](e1_three_cap_sweep_seed0_v1.json), SHA-256
`e1153d11a73480668bdb730c19c2671b12413c3bd1e85c9c3a8e56735cdadfc2`. It passed 31/31 checks.

Detailed arm reports retain exact commands, environment variables, output sizes, checksums and
wall times:

- [E0 smoke report](../e0/e0_readiness_report_2026-08-07.md);
- [E0 full corrected reference](../e0/e0_full_reference_report_2026-08-07.md);
- [2.5x pair report](e1_2p5_semantics_pair_report_2026-08-07.md);
- [0.75x pair report](e1_0p75_semantics_pair_report_2026-08-08.md);
- [40x pair report](e1_40x_semantics_pair_report_2026-08-08.md).

Raw outputs remain outside Git at these permission-safe locators:

- `local-output:e0_outputs/e0-corrected-reference-v1`;
- `local-output:e0_outputs/e0-full-corrected-reference-v1`;
- `local-output:e1_outputs/e1-2p5-semantics-pair-seed0-v1`;
- `local-output:e1_outputs/e1-0p75-semantics-pair-seed0-v1`;
- `local-output:e1_outputs/e1-40x-semantics-pair-seed0-v1`.

The checked-in validation records retain the raw file and instrumentation-array SHA-256 identities.

## Publication chain

The research evidence is intentionally stacked for review:

| Draft PR | Branch | Scope |
|---:|---|---|
| [#4](https://github.com/Abdulla4akash/traffictwin/pull/4) | `agent/e0-corrected-reference-v1` | E0 smoke and full corrected reference |
| [#5](https://github.com/Abdulla4akash/traffictwin/pull/5) | `agent/e1-waiting-room-2p5-v1` | E1 2.5x semantics pair |
| [#6](https://github.com/Abdulla4akash/traffictwin/pull/6) | `agent/e1-waiting-room-0p75-v1` | E1 0.75x pair and two-cap comparison |
| [#7](https://github.com/Abdulla4akash/traffictwin/pull/7) | `agent/e1-waiting-room-40x-v1` | E1 40x pair, three-cap comparison and this cumulative record |

All remain draft and unmerged. No push was made to vec_env or tos-data.

## Exact blockers

1. Evaluator and fleet seeds 1-4 have not been run; no uncertainty or replication evidence exists.
2. The provisional cap and fleet definitions have not been accepted as physical configuration
   choices.
3. Legacy admitted/rejected identities and service-work conservation are unavailable by source
   contract.
4. Randy's historical manifest, exact command, actor identity, seed list and raw outputs are
   unavailable.
5. The trace lacks an `enter` channel and uses mask-only reset semantics.
6. Installed SUMO 1.27.1 differs from trace provenance SUMO 1.27.0.
7. Native physical completion and result-return lifecycle events are unavailable.
8. GitHub Actions jobs cannot start while the repository-owner billing/spending-limit restriction
   remains active.
9. E2 strongest-link versus load-aware placement has not begun.

## Decision and next gate

The bounded seed-0 three-cap pilot is complete and safe to retain for descriptive use. It provides
a conservation-checked basis for deciding whether replication is worth the compute cost. It does
not by itself authorize E2.

Before any next experiment, decide whether to:

1. accept or revise the provisional cap definitions;
2. accept or revise the provisional `uk2030` fleet definition;
3. accept the legacy evidence limitation or require instrumentation;
4. allocate an explicit compute budget for seeds 1-4.

If those four decisions are approved, the next defensible experiment is a separately predeclared
multi-seed E1 replication using the same conserved physical contract. E2, MAPPO retraining,
proactive prediction, learned scheduling and bus modelling are not the automatic next step.

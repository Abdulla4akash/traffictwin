# E1 bounded 2.5x waiting-room semantics pair

Date: 2026-08-07

Decision: **PASS for one matched seed-0/fleet-0 semantics pair at 2.5x; E1 remains incomplete**

Conservation verdict: **physical arm passed; legacy arm is non-conserving and its admitted,
rejected and work quantities are unavailable by source contract**.

No 0.75x or 40x cell, additional seed, placement comparison or E2 experiment was started.

The authoritative machine records are the
[predeclared manifest](e1_2p5_semantics_pair_manifest_v1.json),
[repeated legacy smoke validation](e1_legacy_smoke_validation_v1.json), and
[full pair validation](e1_2p5_semantics_pair_validation_v1.json). Their SHA-256 identities are:

- manifest: `318b909749f514833eba4a09bc34978b33bdefd570bfc3d59e189cebe9334bf5`;
- smoke validation: `97ccbf515fa7ef40257ffe50426dfb4896d6c656f161cc1f45f941a72feafc9f`;
- full pair validation: `3a0227d355852c68273d4c9b0159782f98d9a345a11528b19ddd5b36feedd10a`.

## Verified facts

The pair used:

- vec_env commit `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` from the preserved clean pinned
  worktree;
- tos-data commit `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` from its preserved clean pinned
  worktree;
- evaluator SHA-256 `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`;
- frozen 17-dimensional Paper-2A actor SHA-256
  `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`;
- Manchester incident trace SHA-256
  `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`;
- evaluator seed 0, fleet seed 0, provisional `uk2030` fleet, strongest-link/default placement,
  fixed 1x service and scaling off;
- the provisional 2.5x fleet-scaled ceiling, resolved as 6,220 tasks per RSU.

The legacy arm used `substep-queue=snapshot`, `rsu-cap-mode=clamp` and
`veh-queue=legacy`. The physical arm reused the independently predeclared and validated E0 output
using `substep-queue=sequential`, `rsu-cap-mode=reject` and `veh-queue=conserved`.

The two ten-step legacy smokes each passed all 25 available checks. Their scientific summaries
and all instrumentation-array identities were exactly equal; only wall time and consequently raw
summary/log file hashes differed. The full legacy arm then passed the same 25 checks. The full
pair validator also confirmed exact equality of offered count, per-task active mask and task type
between the legacy and physical arms. The reused E0 physical outputs and validation retained every
predeclared SHA-256 identity.

The environment was Python 3.11.15, JAX/JAXLIB 0.4.30, NumPy 1.26.4 and the CPU backend. Local
SUMO is 1.27.1 while trace provenance records SUMO 1.27.0. The evaluator replayed the NPZ and did
not invoke SUMO, so this is not an exact canonical SUMO 1.27.0 reproduction.

## Observed outputs

The following values are copied from the code-generated validation report. The delta sign is
physical minus legacy.

| Metric | Legacy snapshot/clamp | Physical sequential/reject | Physical minus legacy |
|---|---:|---:|---:|
| Offered tasks | 13,076,234 | 13,076,234 | not used as an effect metric |
| Simulated deadline-met outcomes | 9,528,093 | 8,939,165 | not reported separately |
| Offered-denominator deadline attainment | 0.7286572724226257 | 0.6836192285944103 | -0.04503804382821541 (-4.503804382821541 percentage points) |
| Penalty-inclusive latency per offered task (ms) | 17,116.584494281764 | 17,262.11832061127 | +145.53382632950525 |
| Admitted tasks | unavailable | 11,661,973 | unavailable |
| Admitted-denominator deadline attainment | unavailable | 0.7665225258196019 | unavailable |
| Terminal rejection/unavailability count | unavailable | retained in E0 validation | unavailable |
| Work conservation | unavailable; non-conserving source path | passed in E0 | not comparable |

The legacy full scan took `4542.2` seconds and exited with status 0. It emitted no per-task
outcome codes, admitted count, terminal rejection identities or work ledger. Its six zero-valued
rejection fields are placeholders set by the non-sequential path and are **not** interpreted as
observed zero rejection.

Raw legacy output locator:
`local-output:e1_outputs/e1-2p5-semantics-pair-seed0-v1/legacy_full/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,580 | `9c9d6c5078758ec98892fd387412872375c70bbdff7ba4b3cbfaa0ff30d13840` |
| `per_step.npz` | 20,135,512 | `6e1ef1007e60b6eed7dbb5ceca483f9b8ecdb9135b6f8d454617b071d00e8ea8` |
| `per_task.npz` | 77,140,892 | `f4facd0634099b6f7930628a0f84a0bbd3b63a922905af999c0ee97805be422e` |
| `stdout_stderr.log` | 2,164 | `6f345d2bee0f804ec365b9d43e6e016cbcf37cbfa3892fecdcc3d840af56d8f4` |

The local full-run checksum file has SHA-256
`d77da675e26d76c2760015583d8553d697926ef11da1b6de85c6c872c890fd89`. Raw artifacts remain
outside Git.

## Bounded inference

For this exact trace, actor, task stream, cap and seed pair, the two bundled semantic packages
produce different simulated deadline-attainment and penalty-inclusive offered-latency outputs.
The task-stream identity check rules out a different offered task population as the explanation.

The result does **not** show that legacy clamp is a better physical system. The legacy path scores
surplus tasks while discarding a fraction of their enqueued work and does not retain admitted or
rejected task identities. Its offered deadline-attainment numerator is therefore not backed by the
physical task/work conservation contract that the E0 arm passed.

The pair also changes within-substep queue accounting, RSU-cap handling and vehicle-queue
semantics together. It cannot isolate which component produced the observed difference. One cap
and one seed provide no uncertainty estimate, cap-response curve or general causal conclusion.

Randy's reported `0.6943` was not reproduced: the historical raw manifest, actor identity, seed
table and outputs remain unavailable, and this legacy result is not numerically relabelled as that
historical experiment.

Deadline attainment remains a simulated evaluator outcome. Neither arm supplies evidence of
native physical execution completion or result return.

## Exact blockers and missing information

1. The complete seed-0 E1 pilot still lacks the 0.75x and 40x legacy/physical pairs, so four of
   six intended pilot cells remain absent. The 2.5x physical cell was reused from E0; only the
   missing 2.5x legacy cell was newly executed in this session.
2. Fleet seeds 1-4 have not been run, so no paired uncertainty or replication evidence exists.
3. The pinned legacy path has no per-task admission/rejection outcomes or post-clamp work ledger.
   It cannot satisfy the common offered/admitted/rejected/work reporting contract.
4. The original waiting-room sweep manifest, commands, actor identity, seeds and raw outputs are
   still missing, so Randy's reported result cannot be reproduced exactly.
5. The 6,220-task fleet-scaled ceiling and `uk2030` fleet remain provisional rather than approved
   physical configuration choices.
6. The legacy-versus-physical contrast bundles snapshot/clamp/legacy and
   sequential/reject/conserved changes; it is not a component-level ablation.
7. The trace lacks an `enter` channel and retains mask-only reset semantics.
8. Installed SUMO 1.27.1 differs from trace provenance 1.27.0.
9. Native physical completion and result-return lifecycle events remain unavailable.

## Readiness and recommendation

The bounded 2.5x pair is reproducible and safe to retain as an E1 diagnostic. It is not sufficient
to call E1 complete or to proceed automatically to E2.

Before spending compute on the remaining cap/seed grid, decide whether the scientific contract
accepts legacy as an explicitly invalid historical-control diagnostic, or whether an
instrumentation-only evaluator fork must record aggregate post-clamp slots/work without changing
legacy scoring. That decision is necessary because further uninstrumented legacy cells will still
lack the admitted/rejected/work quantities required by the common reporting contract.

No further experiment is authorised by this report. If continuation is approved with the current
source-bound limitation accepted, the next bounded unit is a predeclared seed-0/fleet-0 0.75x
legacy/physical pair, again beginning with repeated short smokes. E2 remains gated until the E1
scope and legacy evidence contract are resolved.

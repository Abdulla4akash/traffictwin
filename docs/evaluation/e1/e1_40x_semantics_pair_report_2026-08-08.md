# E1 bounded 40x waiting-room semantics pair

Date: 2026-08-08

Decision: **PASS for one matched seed-0/fleet-0 semantics pair at the provisional 40x
waiting-room ceiling, and PASS for the descriptive three-cap seed-0 pilot; E1 remains
incomplete**.

Conservation verdict: **the 40x physical arm passed every offered/admitted/rejected and
service-work identity; the legacy arm's conservation verdict remains unavailable and
non-conserving by source contract**.

No additional seed, placement comparison, E2 experiment, actor retraining or scaling
intervention was started.

The authoritative machine records are the
[predeclared manifest](e1_40x_semantics_pair_manifest_v1.json),
[dual-arm repeated-smoke validation](e1_40x_smoke_validation_v1.json),
[full pair validation](e1_40x_semantics_pair_validation_v1.json), and
[three-cap comparison](e1_three_cap_sweep_seed0_v1.json). Their SHA-256 identities are:

- manifest: `f156d19ed8d59bff479c6f3767291acc2e5c681bdc8e4d630665aba67c3c10e8`;
- smoke validation: `ef851cec13c510bea9e1805f01479c76f4fa215da03e8ed78686c24de9d5bb30`;
- full pair validation: `fc8ec5b33c2e0b5de74e86fbf4545b36234eda6e65d1208295632632d9e91ad6`;
- three-cap comparison: `e1153d11a73480668bdb730c19c2671b12413c3bd1e85c9c3a8e56735cdadfc2`.

## Verified facts

The 40x pair used:

- TrafficTwin base commit `65dab1f327f87362f5b6765903a5d46c44b24ac0` on the dedicated
  `agent/e1-waiting-room-40x-v1` branch; `origin/main` was
  `a462c72b81f1668eef4ea0b7f8e806be4d208b47`;
- vec_env commit `0f01f4d2082d3e8b735e74a873095ab8eeba37cc` from the clean pinned
  `agent/traffictwin-e0-pinned-0f01f4d` worktree;
- tos-data commit `a75bbdb1a956f828ee0e9b97b33506bd32d31b85` from the clean pinned
  `agent/traffictwin-e0-data-a75bbd` worktree;
- evaluator SHA-256 `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`;
- frozen 17-dimensional actor SHA-256
  `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`;
- Manchester incident trace SHA-256
  `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`;
- Friday 15 March 2024, 20:00-21:00, evaluator seed 0, fleet seed 0, provisional
  `uk2030` fleet, strongest-link/default placement, fixed 1x service and scaling off;
- the source-resolved provisional 40x fleet-scaled RSU waiting-room ceiling,
  `round(40 * 2488) = 99,520` admitted/in-flight tasks per RSU. This is an admission
  ceiling, not compute power.

The legacy arm used snapshot substep queues, clamp admission and legacy vehicle queues. The
physical arm used three sequential substep iterations, per-task physical rejection and conserved
vehicle queues. The exact environment and argv are retained in the manifest. Runtime versions
were Python 3.11.15, JAX/JAXLIB 0.4.30, NumPy 1.26.4 and CPU backend. Installed SUMO 1.27.1 differs
from trace provenance SUMO 1.27.0; replay did not invoke SUMO, and this is not an exact canonical
SUMO 1.27.0 reproduction.

Both ten-step repeats in each arm were identical in scientific summary and instrumentation-array
hashes. Each legacy repeat passed 25/25 available checks; each physical repeat passed 32/32. The
physical cap did not bind in the first ten steps, so the smoke established determinism and
accounting only, not a cap effect. Cross-arm offered count, task-active mask and task type were
identical.

The full legacy run passed 25/25 available checks. The full physical run passed 32/32 checks. The
full pair validator again confirmed exact cross-arm offered-count, task-active and task-type
identity. The three-cap comparator passed 31/31 checks, including the independently validated E0
reuse hash chain for the 2.5x physical arm and exact actor, trace, common physical configuration,
offered count and physical/legacy task-stream identities across 0.75x, 2.5x and 40x.

The validation code used for this unit has SHA-256 identities:

- new-cap pair validator: `88917795dcf2abce1e0c1103fc0ec74a529c72eaf828769e05525fa2df4cc134`;
- three-cap comparator: `64c4dcd8cb8b0c00231f476216a67e80e235bf7092467d5e4bf74e121d823a31`.

## Observed 40x pair

Values below are copied from the code-generated full-pair validation. The delta sign is physical
minus legacy.

| Metric | Legacy snapshot/clamp | Physical sequential/reject | Physical minus legacy |
|---|---:|---:|---:|
| Offered tasks | 13,076,234 | 13,076,234 | task stream identical |
| Offered-denominator deadline attainment | 0.7286572724226257 | 0.6836192285944103 | -0.04503804382821541 (-4.503804382821541 percentage points) |
| Penalty-inclusive latency per offered task (ms) | 160,676.9823127974 | 160,827.13705612795 | +150.15474333055317 |
| Admitted tasks | unavailable | 12,143,126 | unavailable |
| Admitted-denominator deadline attainment | unavailable | 0.7361502301796095 | unavailable |
| Work conservation | unavailable | passed | not comparable |

For the physical arm, the validator reconciled:

- offered tasks `13,076,234 = 12,143,126 admitted + 933,108 rejected/unavailable`;
- terminal reasons `933,108 = 352,967 RSU-cap + 34,124 local MQD + 545,879 V2V MQD +
  138 V2I unavailable + 0 V2V unavailable + 0 gate`;
- V2I work `42,670,748 = 36,995,000 admitted + 5,675,748 rejected/unavailable` ms;
- vehicle work `281,346,752 = 270,951,552 admitted + 10,395,200 rejected` ms.

The legacy run does not emit admitted identities, terminal outcomes or a work ledger. Its zero
rejection counters are placeholders and are not interpreted as observed zero rejection. Offered-
task and admitted-task denominators remain separate. The 40x ceiling still bound in the physical
full run, so this point is high-cap rather than empirically unbounded.

## Descriptive three-cap seed-0 physical comparison

The table below is copied from the code-generated comparison after all cross-cap identity checks
passed.

| Provisional cap multiplier | Resolved ceiling per RSU | Admitted | Rejected/unavailable | RSU-cap rejected | Offered-denominator deadline attainment | Admitted-denominator deadline attainment | Penalty-inclusive latency per offered task (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.75x | 1,866 | 11,630,198 | 1,446,036 | 865,895 | 0.6837908376371974 | 0.7688096969630268 | 5,461.601257976876 |
| 2.5x | 6,220 | 11,661,973 | 1,414,261 | 834,120 | 0.6836192285944103 | 0.7665225258196019 | 17,262.11832061127 |
| 40x | 99,520 | 12,143,126 | 933,108 | 352,967 | 0.6836192285944103 | 0.7361502301796095 | 160,827.13705612795 |

The code-generated descriptive trend checks found nondecreasing admissions, nonincreasing RSU-cap
rejections and nondecreasing penalty-inclusive latency as the ceiling increased. Across all three
physical points, offered-denominator deadline attainment spanned
`0.0001716090427871242`, or `0.01716090427871242` percentage points. From 0.75x to
40x, the physical arm admitted 512,928 more tasks and rejected 512,928 fewer, while latency per
offered task increased by 155,365.53579815108 ms and admitted-denominator deadline attainment
decreased by 3.2659466783417357 percentage points.

These are deterministic seed-0 descriptions, not estimates of a population response and not a
formal tie finding. They show that the provisional cap remains an influential admission/queueing
choice in this evaluator. They do not compare placement controllers.

## Raw output provenance

Raw outputs remain outside Git under the permission-safe locator
`local-output:e1_outputs/e1-40x-semantics-pair-seed0-v1`.

Legacy full locator: `local-output:e1_outputs/e1-40x-semantics-pair-seed0-v1/legacy_full/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,580 | `16e94bea6e6c8c992f73063fcae87408aceada6eafdd30fcab2bd55513a85b4c` |
| `per_step.npz` | 20,169,620 | `dd0250080c91ccd26d638012bf4c8ad70b4b85682e943d1057410bd95ca8c615` |
| `per_task.npz` | 76,544,645 | `e4c4579b66b0a030c51aa54b28e767d09c6c231062a687c802ed71315215d691` |
| `stdout_stderr.log` | 2,165 | `09636084900682f71491553bf8480027a9f71de92fed1790d847f0a78e2d2785` |

Legacy wall time was 4,967.4 seconds. Its checksum-file SHA-256 is
`c5712776d7d1d8dfd5d92e59baf9fe9654163b6082580cbaccab15b41f217d1d`.

Physical full locator:
`local-output:e1_outputs/e1-40x-semantics-pair-seed0-v1/physical_full/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,855 | `c3bd33440f2328a0e40d948896b4b2882673d42946b2e14b19a386288d34af58` |
| `per_step.npz` | 20,125,632 | `393cda2bd37520eca4693a7d720d42bd8edd07c8ba4e63008203e108a10a78e3` |
| `per_task.npz` | 84,017,582 | `8c29745cf5738eeeac61f2a9e1e044ac119c0d0d87f79d2cb736e87aadfe62f3` |
| `stdout_stderr.log` | 2,705 | `e7f410880054a36ea69da9b42e00a7b2f75fa94cb1c396f4417a1bc243666969` |

Physical wall time was 6,500.0 seconds. Its checksum-file SHA-256 is
`5714e6f5a8da65e7867f46b0d0c82e786b0434dafc4a3d1e579d187253980cc0`.

Both checksum files were reverified after validation. The local interim legacy-gate report is
retained beside the raw outputs with SHA-256
`2f4dbc4a0421fb9911e6fceafd8e8b60f483ac0f2f93b60181be6208d75b67e5`.

## Interpretation boundary

All three physical points are conserved and directly matched on the offered task stream. Each
within-cap legacy-versus-physical contrast still bundles substep queue, RSU admission and vehicle-
queue semantics, and legacy does not satisfy the physical conservation contract. It cannot
identify a component-level causal effect or establish that either semantic package represents a
better physical system.

Only one evaluator seed and one fleet seed are present. The narrow offered-completion span and the
large latency/admission changes are descriptive, with no uncertainty estimate. Replication is
required before generalisation or any practical cap recommendation.

Deadline attainment is a simulated evaluator outcome. It is not evidence of native physical
execution completion or result return. Randy's reported `0.6943` has not been reproduced. The
historical raw manifest, actor identity, seed table and outputs remain unavailable.

## Exact blockers and missing information

1. Fleet/evaluator seeds 1-4 have not been run, so no uncertainty or replication evidence exists.
2. Legacy admitted/rejected identities and service-work conservation remain unavailable by source
   contract; its zero rejection fields are placeholders.
3. The waiting-room ceilings and `uk2030` fleet remain provisional rather than approved physical
   configuration choices.
4. The original waiting-room sweep manifest, commands, actor identity, seeds and raw outputs are
   unavailable, so Randy's historical result cannot be reproduced exactly.
5. The trace lacks an `enter` channel and uses mask-only reset semantics.
6. Installed SUMO 1.27.1 differs from trace provenance SUMO 1.27.0.
7. Native physical completion and result-return lifecycle events are unavailable.
8. E2 strongest-link versus load-aware placement has not begun and remains outside this result.

## Readiness and next bounded action

The seed-0 three-cap pilot is complete and valid to retain for descriptive use within the stated
boundaries. E1 is not complete and E2 is not authorised by this evidence.

The next reasonable decision is whether the observed admission/latency sensitivity justifies a
separately predeclared replication across evaluator/fleet seeds 1-4. No replication campaign
should start automatically: it requires approval of the provisional cap and fleet definitions and
an explicit compute budget. Placement/E2 remains gated until that decision and is not the next
experiment by default.

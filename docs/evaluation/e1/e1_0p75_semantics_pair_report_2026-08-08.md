# E1 bounded 0.75x waiting-room semantics pair

Date: 2026-08-08

Decision: **PASS for one matched seed-0/fleet-0 semantics pair at 0.75x, and PASS for a
descriptive two-cap comparison with the validated 2.5x point; E1 remains incomplete**.

Conservation verdict: **the 0.75x physical arm passed all offered/admitted/rejected and service-
work identities; the legacy arm's conservation verdict remains unavailable and non-conserving by
source contract**.

No 40x cell, additional seed, placement comparison, E2 experiment, actor retraining or scaling
intervention was started.

The authoritative machine records are the
[predeclared manifest](e1_0p75_semantics_pair_manifest_v1.json),
[dual-arm repeated-smoke validation](e1_0p75_smoke_validation_v1.json),
[full pair validation](e1_0p75_semantics_pair_validation_v1.json), and
[two-cap comparison](e1_0p75_vs_2p5_cap_comparison_seed0_v1.json). Their SHA-256 identities are:

- manifest: `d299998d0346aa20466afcb156868cff6fabd614d15c5a91dc6427f58d857b5d`;
- smoke validation: `a70ecce0aca3a1bd976f7b9332981539ea9b47856af4cb95fad3ca6de8c7fd3a`;
- full pair validation: `1b0ce7612fda194cb91ed70d01b4f18dfecd7d06b7d77a14c38480ab734fc09e`;
- two-cap comparison: `0a0d99d47267de6edf490b9f8cadd59286892cb654466a3c44e80b4b5d974999`.

## Verified facts

The 0.75x pair used:

- TrafficTwin base commit `ed2a9328b9a8951750ef1c5a61a7c989a8a086ca` on the dedicated
  `agent/e1-waiting-room-0p75-v1` branch; `origin/main` was
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
- the source-resolved 0.75x fleet-scaled RSU waiting-room ceiling,
  `round(0.75 * 2488) = 1866` admitted/in-flight tasks per RSU. This is an admission ceiling,
  not compute power.

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
identity. The post-validation cap comparator passed 22/22 checks, including the independently
validated E0 reuse hash chain and exact physical/legacy task-stream identity across 0.75x and
2.5x.

The validator scripts used for this unit have SHA-256 identities:

- new-cap pair validator: `88917795dcf2abce1e0c1103fc0ec74a529c72eaf828769e05525fa2df4cc134`;
- two-cap comparator: `5197dc50297a44644109e8b382ff145350e46956d71fa6af21fb2cbae5190e8b`.

## Observed 0.75x pair

Values below are copied from the code-generated full-pair validation. The delta sign is physical
minus legacy.

| Metric | Legacy snapshot/clamp | Physical sequential/reject | Physical minus legacy |
|---|---:|---:|---:|
| Offered tasks | 13,076,234 | 13,076,234 | task stream identical |
| Offered-denominator deadline attainment | 0.7290600642356201 | 0.6837908376371974 | -0.045269226598422696 (-4.52692265984227 percentage points) |
| Penalty-inclusive latency per offered task (ms) | 5,314.834518868353 | 5,461.601257976876 | +146.76673910852242 |
| Admitted tasks | unavailable | 11,630,198 | unavailable |
| Admitted-denominator deadline attainment | unavailable | 0.7688096969630268 | unavailable |
| Work conservation | unavailable | passed | not comparable |

For the physical arm, the validator reconciled:

- offered tasks `13,076,234 = 11,630,198 admitted + 1,446,036 rejected/unavailable`;
- terminal reasons `1,446,036 = 865,895 RSU-cap + 34,124 local MQD + 545,879 V2V MQD +
  138 V2I unavailable + 0 V2V unavailable + 0 gate`;
- V2I work `42,670,748 = 28,753,338 admitted + 13,917,410 rejected/unavailable` ms;
- vehicle work `281,346,752 = 270,951,552 admitted + 10,395,200 rejected` ms.

The legacy run does not emit admitted identities, terminal outcomes or a work ledger. Its zero
rejection counters are placeholders and are not interpreted as observed zero rejection. Offered-
task and admitted-task denominators remain separate.

## Descriptive 0.75x versus 2.5x physical comparison

The comparison below is code-generated after exact input and task-stream identity checks. Delta
is 0.75x minus 2.5x.

| Metric | 0.75x (cap 1,866) | 2.5x (cap 6,220) | Low minus high |
|---|---:|---:|---:|
| Offered tasks | 13,076,234 | 13,076,234 | 0 |
| Admitted tasks | 11,630,198 | 11,661,973 | -31,775 |
| Rejected/unavailable tasks | 1,446,036 | 1,414,261 | +31,775 |
| Rejection fraction | 0.11058505071108395 | 0.10815506972420347 | +0.0024299809868804784 |
| RSU-cap rejections | 865,895 | 834,120 | +31,775 |
| Offered-denominator deadline attainment | 0.6837908376371974 | 0.6836192285944103 | +0.0001716090427871242 (+0.01716090427871242 percentage points) |
| Admitted-denominator deadline attainment | 0.7688096969630268 | 0.7665225258196019 | +0.0022871711434249153 (+0.22871711434249153 percentage points) |
| Penalty-inclusive latency per offered task (ms) | 5,461.601257976876 | 17,262.11832061127 | -11,800.517062634393 |
| Latency per admitted task (ms) | 3,808.757481858864 | 12,140.312200002521 | -8,331.554718143658 |

At this one matched seed, lowering the waiting-room ceiling produced more explicit admission
rejection while substantially reducing simulated queue latency; offered-denominator deadline
attainment was nearly tied. This is bounded descriptive evidence of a queueing/admission tradeoff,
not a general cap-response curve. It does not compare placement controllers.

## Raw output provenance

Raw outputs remain outside Git under the permission-safe locator
`local-output:e1_outputs/e1-0p75-semantics-pair-seed0-v1`.

Legacy full locator: `local-output:e1_outputs/e1-0p75-semantics-pair-seed0-v1/legacy_full/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,579 | `9b5b0f60b7dec30283483c27b0db1068b06df542bd6d57f6b2ca92fd618136cd` |
| `per_step.npz` | 20,137,724 | `07cfc8dbffec9406e1d5c355d5606ad207058df6a7c4b8520db48849b76e5ee2` |
| `per_task.npz` | 77,500,874 | `84e1e892cbd4daacf75073af96019133b7dd8c27eb2ac26d0a55747e7a2af574` |
| `stdout_stderr.log` | 2,165 | `7350403b00bda673e38cdc84ff1658426781107359d9e62942eb2a89af94f553` |

Legacy wall time was 4,527.5 seconds. Its checksum-file SHA-256 is
`3a33bfdcc5948cc4cf187bf9fb5042fc4281a34a25cfb73d6d69b711833a4110`.

Physical full locator:
`local-output:e1_outputs/e1-0p75-semantics-pair-seed0-v1/physical_full/run_1`.

| Artifact | Size (bytes) | SHA-256 |
|---|---:|---|
| `summary.json` | 1,855 | `abde7cffdc21e73a074b6cb3bd10e54a25fb70c3008b6d6cba0e679b12fd8d14` |
| `per_step.npz` | 20,094,003 | `7a4b20e50f9d1ef14835c01344baaa7a598bb37bcfbe22f469f78e648fd3aff7` |
| `per_task.npz` | 84,637,406 | `d89d36d353cdea405f60e710244d75c04c3bd296c66c6302502b7a0ee2281f7f` |
| `stdout_stderr.log` | 2,706 | `0d1529ea0ad3e92e9fd51f316f0b6f4028445965704b5415c37fcde03f6ba59d` |

Physical wall time was 5,709.9 seconds. Its checksum-file SHA-256 is
`178d9f395d47847596f3e1b5f9dad2ff60239c4e351928633d385faef0d3b163`.

The local interim legacy-gate report is retained beside the raw outputs with SHA-256
`4d1405bfb71df9208e2c13f74c13156a9aac508a0398701656dd4d7cd43ebff5`.

## Interpretation boundary

The 0.75x physical arm is conserved and the two physical cap points are directly matched on the
offered task stream. The within-cap legacy-versus-physical contrast still bundles substep queue,
RSU admission and vehicle-queue semantics, and legacy does not satisfy the physical conservation
contract. It cannot identify a component-level causal effect or establish that either semantic
package represents a better physical system.

Only one evaluator seed and one fleet seed are present. The small offered-completion difference
between physical cap points is descriptive, with no uncertainty estimate. The large latency
difference is also seed-0 evidence and requires replication before generalisation.

Deadline attainment is a simulated evaluator outcome. It is not evidence of native physical
execution completion or result return. Randy's reported `0.6943` has not been reproduced. The
historical raw manifest, actor identity, seed table and outputs remain unavailable.

## Exact blockers and missing information

1. The intended seed-0 three-cap pilot still lacks the 40x legacy/physical pair.
2. Fleet/evaluator seeds 1-4 have not been run, so no uncertainty or replication evidence exists.
3. Legacy admitted/rejected identities and service-work conservation remain unavailable by source
   contract; its zero rejection fields are placeholders.
4. The waiting-room ceilings and `uk2030` fleet remain provisional rather than approved physical
   configuration choices.
5. The original waiting-room sweep manifest, commands, actor identity, seeds and raw outputs are
   unavailable, so Randy's historical result cannot be reproduced exactly.
6. The trace lacks an `enter` channel and uses mask-only reset semantics.
7. Installed SUMO 1.27.1 differs from trace provenance SUMO 1.27.0.
8. Native physical completion and result-return lifecycle events are unavailable.
9. E2 strongest-link versus load-aware placement has not begun and remains outside this result.

## Readiness and next bounded action

The 0.75x pair is valid to retain, and the two-cap seed-0 comparison is safe for descriptive use
within the stated boundaries. E1 is not complete and E2 is not authorised by this evidence.

If the current legacy evidence limitation remains accepted as a historical-control diagnostic,
the next bounded unit is a separately predeclared seed-0/fleet-0 40x legacy/physical pair,
beginning with repeated short smokes and the same stop/go gates. That run should not be launched
automatically: 40x remains provisional, and its high ceiling may be effectively non-binding while
still incurring two full evaluator scans. After the seed-0 cap pilot, the next decision is whether
the observed cap tradeoff justifies seeds 1-4; placement/E2 remains gated.

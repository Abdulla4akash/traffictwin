# E1 multi-draw fleet-seed-1 / 0.75x cell report

**Date:** 8 August 2026

**Verdict:** the two serial ten-step smokes and the corresponding 3,600-step physical full cell
passed. Execution stopped before the next cap point; no 2.5x, 40x or later-seed process started.

**Machine-readable validation:**
[`e1_multidraw_seed1_0p75_cell_validation_v1.json`](e1_multidraw_seed1_0p75_cell_validation_v1.json)

**Governing campaign manifest:**
[`e1_multidraw_physical_campaign_manifest_v1.json`](e1_multidraw_physical_campaign_manifest_v1.json),
SHA-256 `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`

## Locked execution

The selected backend was `macos_arm64_cpu_jax_0_4_30`: Python 3.11.15, JAX/JAXLIB 0.4.30,
NumPy 1.26.4, SciPy 1.17.1 and `TFRT_CPU_0`. TrafficTwin was at
`ca4c04890346e01a572b728da4a785026fa87d5a`; vec_env remained clean at
`0f01f4d2082d3e8b735e74a873095ab8eeba37cc`; tos-data remained clean at
`a75bbdb1a956f828ee0e9b97b33506bd32d31b85`.

The evaluator, frozen actor and trace SHA-256 identities were respectively
`260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`,
`93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208` and
`e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`. Local SUMO was
1.27.1 while trace provenance names 1.27.0. The evaluator replayed the frozen NPZ and did not invoke
SUMO, but this remains a compatibility mismatch and is not an exact canonical SUMO reproduction.

Both the initial and pre-full preflights passed all 39 manifest, runner, repository, input,
interpreter/package/device, adapter, reused-seed-0, output and storage checks. The cell used fleet
seed 1, evaluator seed 0, the provisional 0.75x waiting-room ceiling resolved to 1,866 tasks per
RSU, physical sequential/reject/conserved semantics, strongest-link/default placement, fixed 1x
service, zero backhaul, and load balancing/scaling off.

## Repeated-smoke gate

Both ten-step runs passed individually and agreed exactly after excluding wall-clock timing.
Every instrumentation array had the same dtype, shape and bytes. Each run offered 36,856 tasks,
admitted 35,133 and recorded offered-task deadline attainment of 0.6988821358801823. Evaluator
times were 13.4 and 13.7 seconds; runner times were 14.180 and 14.444 seconds. The retained smoke
validation SHA-256 is `dc3f17edac164a34d73775cf09d4a16931824e541a9ed07e77b6f738f52091bb`.

The controller that launched the smokes encountered a display-only `KeyError` after writing the
passing validation and campaign-status records because its console summary requested a field not
present in the repeat record. No evaluator output was altered, and the full cell remained absent
until the passing JSON was independently read and checked. This is retained as an orchestration
observation, not a scientific failure.

## Full-cell observations

The complete validator passed all 32 checks with zero failures.

| Metric | Observed value |
|---|---:|
| Offered tasks | 13,076,234 |
| Admitted tasks | 11,779,070 |
| Rejected/unavailable tasks | 1,297,164 |
| Deadline-met tasks | 9,001,257 |
| Served but deadline-missed tasks | 2,777,813 |
| Deadline attainment / offered | 0.6883676905751305 |
| Deadline attainment / admitted | 0.7641738269659659 |
| Penalty-inclusive latency / offered task | 4,642.545912225187 ms |
| Latency / admitted task | 3,412.17931534493 ms |
| Latency / deadline-met task | 47.282843274000506 ms |
| Evaluator wall time | 6,440.6 s |
| Runner wall time | 6,462.124663833063 s |

Rejection and unavailability counts were: 639,848 V2I cap rejections; 38,444 local queue
rejections; 618,761 V2V helper-queue rejections; 111 V2I-unavailable tasks; and zero V2I gate or
V2V-unavailable outcomes. These sum with admitted tasks to the offered count under the validator.

Admitted latency p50/p95/p99 was 52.9176139831543 / 29,306.016699218748 /
29,975.150390625 ms. Deadline-met latency p50/p95/p99 was 35.71510314941406 /
139.5860717773437 / 339.69069946289045 ms. Local/V2I/V2V decision shares were
0.5316876403404833 / 0.1906163502427381 / 0.2776960094167786.

## Conservation verdict

Task accounting passed: every active task had exactly one terminal outcome, the offered count
equalled admitted plus every rejection/unavailability category, and no silent task loss was found.
All aggregate numbers and arrays were finite; required count, work, latency and queue fields were
nonnegative; offered and admitted deadline denominators remained separate.

V2I service work conserved in milliseconds:

`40,107,836 offered = 29,815,326 admitted + 10,292,510 rejected/unavailable`.

Vehicle service work conserved in milliseconds:

`282,604,672 offered = 270,455,040 admitted + 12,149,632 rejected`.

## Evidence and stopping boundary

Raw evidence remains outside Git at
`local-output:e1_outputs/e1-multidraw-physical-seeds0-4-v1/fleet_seed_1/cap_0p75`.
The full summary/per-step/per-task SHA-256 values are respectively
`d2be5e57598e4e894b9a1c5fa647656ea6d83cc88a67d5ae89a586941a4b32fc`,
`2e2c92f3561fa37d597b10d328e52e8f3aa5cbb2044db7aff0650b2d2b44549e` and
`9a37b6222ec51fb2efa2d293ef85c7371f964a6040e6c590ee352118016180ae`.
The full validation SHA-256 is
`e9499a3c74510c343de179ea3cd12cc71241bacb3d9d65ec213690419b404c32`;
the 29-file checksum index SHA-256 is
`94d2e233af9a685e9b05edc4a91c3051b518c08a351eb78c3ebb7c8c06a8cea7`.
Every indexed file passed checksum verification.

This is one fleet-seed/cap observation, not the primary paired campaign result. It does not support
cross-cap inference, equivalence, real-world optimality or a claim of native physical result
return. The waiting-room ceiling is not compute power, and Randy's reported `0.6943` remains
unreproduced.

Execution has stopped. If the researcher directs continuation, the next manifest cell is fleet
seed 1 at 2.5x and must begin with two serial ten-step smokes. No 2.5x full cell is permitted until
that separate repeated-smoke gate passes. E2 and all non-manifest extensions remain prohibited.

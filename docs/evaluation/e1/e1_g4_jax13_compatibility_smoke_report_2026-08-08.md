# E1 G4 JAX/CUDA-13 compatibility-smoke report

**Date:** 8 August 2026

**Verdict:** failed at the mandatory primitive gate. G4 scientific compatibility, repeatability,
conservation and speed were not demonstrated. No evaluator process or full E1 cell ran. Under the
direct decision rule, further G4 experimentation stops and the already validated macOS/JAX 0.4.30
CPU backend is selected for the campaign.

**Machine-readable result:**
[`e1_g4_jax13_compatibility_smoke_result_v1.json`](e1_g4_jax13_compatibility_smoke_result_v1.json)

**Governing manifest:**
[`e1_g4_jax13_compatibility_smoke_manifest_v1.json`](e1_g4_jax13_compatibility_smoke_manifest_v1.json),
SHA-256 `d91abe1f6fb95c22387cd150e5f027483391cc72bf23e8ccd0318e71f8cbf659`

The first [G4/JAX 0.4.30 failure](e1_colab_g4_backend_smoke_report_2026-08-08.md) remains separate,
immutable negative evidence. This result does not rewrite it or label it successful.

## Direct observations

The installed Colab CLI 0.6.0 provisioned the exact command
`colab new -s e1-g4-jax13-smoke --gpu G4`. CLI status and independent in-runtime NVIDIA and JAX
probes all confirmed the requested device; no fallback accelerator was used.

| Field | Observed value |
|---|---|
| Requested/status accelerator | G4 / G4 |
| Actual NVIDIA model | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| Compute capability / VRAM | 12.0 / 97,887 MiB |
| Driver / `nvidia-smi` maximum CUDA | 580.82.07 / 13.0 |
| Host `nvcc` toolkit | CUDA 12.8, V12.8.93 |
| Python / platform | 3.12.13 / Linux 6.6.122+ x86-64 |
| JAX / JAXLIB | 0.11.0 / 0.11.0 |
| CUDA plugin / PJRT package | `jax-cuda13-plugin` 0.11.0 / `jax-cuda13-pjrt` 0.11.0 |
| CUDA runtime / NVCC wheel | 13.3.29 / 13.3.73 |
| NumPy / SciPy | 2.5.1 / 1.18.0 |
| XLA/JAX backend and device | `gpu` / `cuda:0` |
| JAX device kind | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| JAX platform-version string | unavailable (`null` in the retained probe) |

All 23 frozen package identities and all 11 predeclared code/input/reference identities passed.
The exact wheel-only lock is
[`e1_g4_jax13_compatibility_requirements_v1.txt`](e1_g4_jax13_compatibility_requirements_v1.txt),
SHA-256 `e5d604c612002b4ad0054dea7351e59d456e0b59c3d24f0e07b6c00e80426e57`.
The package installation completed in 62.506 seconds. Pip also warned that the ambient Colab
`numba 0.60.0` declares `numpy<2.1`, while the frozen resolution installed NumPy 2.5.1. This did
not cause the observed primitive failure, but its evaluator impact was not assessable because the
evaluator never started.

## Primitive gate and mandatory stop

The first allowed primitive, synchronized `jax.random.PRNGKey(0)`, failed with
`JaxRuntimeError`:

> `INVALID_ARGUMENT: Unexpected PJRT_FFI_UserData_Add_Args size: expected 48, got 40.`

The retained error further says that the plugin was built with a later framework interface and
reports PJRT API version 0.76. This is direct evidence of an observed PJRT FFI/ABI mismatch; the
record does not infer which ambient component would need replacement.

Because the first primitive failed, the small GPU array, `jax.jit` compile, warmed synchronized
operation and both evaluator repeats were not started. This is the predeclared mandatory stop, not
a partially completed scientific smoke. No TrafficTwin scientific source was changed.

## Repeat, conservation and CPU comparison

| Required item | Result |
|---|---|
| Primitive compilation | Failed at `jax.random.PRNGKey(0)` |
| Evaluator repeat 1 | Not started |
| Evaluator repeat 2 | Not started |
| Offered/admitted/rejection accounting | Unavailable—no evaluator output |
| V2I work conservation | Unavailable—no evaluator output |
| Vehicle-work conservation | Unavailable—no evaluator output |
| Task-active/task-type identity | Unavailable—no G4 task arrays |
| G4 repeat determinism | Unavailable—no repeat ran |
| Full/campaign cells | 0 started |

The established CPU smoke remains the comparison reference: macOS arm64, Python 3.11.15,
JAX/JAXLIB 0.4.30, NumPy 1.26.4 and the TFRT CPU device. Its two evaluator times were 12.7 and
12.6 seconds (median 12.65 seconds), with 36,856 offered tasks, 35,195 admitted tasks and 25,227
deadline-met tasks. G4 produced none of the required discrete identities, numerical outcomes,
latency, decision-share or service-work fields, so there are no CPU-versus-G4 scientific
differences to calculate. CPU conservation passed in the established reference; G4 conservation
is unavailable rather than failed or passed.

There is no valid G4 evaluator wall time, warm-run time, speedup or campaign-runtime estimate.
Neither the 62.506-second package installation nor time-to-failure is an evaluator speed
measurement. The predeclared 1.25x worthwhile-speed threshold therefore cannot pass.

## Interpretation and backend decision

The exact stable CUDA-13 lock could identify the genuine Blackwell GPU but could not execute the
first seeded JAX primitive in this Colab runtime. Consequently, the unchanged evaluator was never
reached and G4 is not scientifically acceptable for this campaign.

This is the second separately retained G4 compatibility failure. The researcher's rule now stops
further G4 experimentation and selects the already validated macOS CPU backend. Existing validated
macOS seed-0 physical cap artifacts remain reusable by exact hash, while the new campaign matrix
remains the 12 full cells for fleet seeds 1-4 and all three caps. No macOS and G4 full results will
be mixed because no G4 full result exists.

Selection does not itself launch a cell. The exact next execution gate is two serial ten-step CPU
smokes for fleet seed 1 at 0.75x, followed by their deterministic/accounting validation. Only a
pass authorises that corresponding full cell under the campaign runner. E2 and every other
extension remain prohibited.

## Evidence and limitations

Raw evidence is retained outside Git at
`local-output:e1_outputs/e1-g4-jax13-compatibility-smoke-v1`. The downloaded archive SHA-256 is
`8469f9049a64abb62c855d12e4dafacd80662c0b0527a12da47bde0c9f35fcfb`; the raw result is
`104801ae79e8b1621c354fc23de02fd0678f8c9adcb7b0e673278b4ccb8bd772`; the pip install report is
`e155230d999c766b24fd42fb5d106accfbbc608d19a2d35c150772200c13809e`; and the local checksum
index is `4fb26d6ae5a9dccf96fe918ea02b1ade253bf1864f48c0f041ddb6111d4ab702`.
Raw artifacts remain outside Git. The Colab session was terminated after retrieval and the CLI
reported no remaining session.

The failure cannot establish how the evaluator behaves on a working Blackwell stack, whether
CPU/GPU floating-point differences would affect task decisions, or whether G4 would be faster.
The selected CPU campaign remains a bounded simulator study of one incident hour with a
provisional `uk2030` fleet and waiting-room limits that are not compute-power interventions.
Deadline attainment is simulated, not proof of native physical result return. Randy's `0.6943`
remains unreproduced.

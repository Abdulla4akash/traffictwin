# E1 Google Colab G4 backend smoke report

**Date:** 8 August 2026

**Decision:** failed before task generation; G4 is not selected for the campaign under the pinned
environment. The E1 campaign remains on hold and no full cell is authorised.

**Machine-readable result:**
[`e1_colab_g4_backend_smoke_result_v1.json`](e1_colab_g4_backend_smoke_result_v1.json)

**Governing predeclared manifest:**
[`e1_colab_gpu_backend_smoke_manifest_v1.json`](e1_colab_gpu_backend_smoke_manifest_v1.json),
SHA-256 `5f6a69cea9fd479cf0c8152565bfb52d01b6f080bacf9012da8b8f87708eb5b7`

## Direct observations

The installed Google Colab CLI was version 0.6.0. It allocated the named session
`e1-g4-smoke` from the exact request `colab new -s e1-g4-smoke --gpu G4`. Both the CLI status and
the in-runtime probes were checked; no fallback accelerator was accepted.

| Field | Observed value |
|---|---|
| Requested/status accelerator | G4 / G4 GPU |
| Actual NVIDIA model | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| VRAM | 97,887 MiB |
| Driver / `nvidia-smi` maximum CUDA | 580.82.07 / 13.0 |
| `nvcc` toolkit | CUDA 12.8, V12.8.93 |
| JAX backend/device | `gpu` / `cuda:0` |
| Python | 3.12.13 |
| JAX / JAXLIB | 0.4.30 / 0.4.30 |
| CUDA plugin / PJRT | 0.4.30 / 0.4.30 |
| NumPy / SciPy | 1.26.4 / 1.17.1 |

All six evaluator, actor, trace, adapter, `vec_jax` and CPU-validation identities passed. All six
required package identities passed, and JAX reported the genuine GPU. The uploaded private bundle
was `e1-colab-gpu-backend-smoke-v1-inputs-r3.tar.gz`, SHA-256
`7cf78ed99f912bfbcd7d50f08a1dd2baa0c89a9de8260a5bf05be9d3838b6091`.

The first predeclared ten-step process then exited at
`eval/eval_sumo_stage1_mc.py:306`, while creating `jax.random.PRNGKey(0)`. The retained JAX/XLA
error reports that `ptxas` could not compile a program targeting `sm_90a` for the assigned future
Blackwell architecture. The process stopped in 1.167912805 seconds, before it wrote a summary,
per-step array or per-task array. The second repeat was not started. No 3,600-step or campaign cell
started. The session was stopped after download, and the CLI then reported no active sessions.

## Validation verdict

This was a backend feasibility failure, not a completed scientific smoke:

- task, V2I-work and vehicle-work conservation are unavailable because no task output exists;
- task-stream identity and numerical differences versus macOS are unavailable;
- repeat determinism is unavailable because the mandatory stop prevented repeat 2;
- the 1.1679-second failure time is not an evaluator runtime and must not be divided into the CPU
  baseline to claim a speedup;
- measured G4 speedup and a G4 campaign-runtime estimate are therefore unavailable, not zero and
  not positive.

The validated macOS CPU contract remains the comparison reference: its two ten-step evaluator
times were 12.7 and 12.6 seconds, with 36,856 offered tasks, 35,195 admitted tasks and 25,227
deadline-met tasks. None of those scientific fields has a G4 counterpart from this attempt.
The unchanged CPU planning estimate for the twelve new cells is 20.089 hours; it is not a G4
runtime estimate and does not itself select CPU for execution.

## Interpretation

The exact pinned JAX 0.4.30 CUDA-12 package set can discover this G4 Blackwell device but cannot
execute even the first seeded PRNG operation on it. Consequently, the current manifest contract is
not executable on the assigned G4 architecture. Changing JAX/CUDA packages would be a new backend
compatibility intervention and was not performed.

The G4 backend is not selected. This result does not justify falling back silently to T4, L4,
A100, CPU or TPU, and it does not justify mixing any macOS and Colab full outputs. The main campaign
backend remains pending a reviewed decision.

## Evidence and provenance

Raw evidence is retained outside Git at
`local-output:e1_outputs/e1-colab-gpu-backend-smoke-v1`. The local checksum index has SHA-256
`a869102f165452e4faf1faa83a02b63b3f43c5b0a2dc8d592f0af3366de08761`.
The downloaded archive has SHA-256
`a2d650e0779c9620d4acf3a4c31c471375f75515dc7ea6fcc457c10b0141c7d0`; the hardware record has
SHA-256 `41968612e05a7580735ad4a043a636582c1648d12e4c07a86d201f9ae7a4de34`;
and the failure log has SHA-256
`421b93cff29d68cb624fb3eb8fa14cee76989a7397a1e28fa83f34417f26b0ef`.

The immutable manifest was present in the uploaded bundle before allocation, but the intended
pre-run TrafficTwin commit and draft PR had not yet been published because the preceding turn was
interrupted. This is retained as a protocol deviation. Since the evaluator produced no task data,
the attempt is used only as negative backend-compatibility evidence, not an E1 scientific result.

## Remaining gate

Before any new smoke or full run, the researcher must explicitly choose one of two separately
reviewed paths: select the already validated macOS CPU backend under an updated campaign decision,
or authorise a new package-compatibility smoke whose changed JAX/CUDA contract is predeclared. The
current authority does not permit changing packages merely to make G4 execute. E2, scaling,
retraining, prediction, bus modelling and Randy-result reproduction remain out of scope.

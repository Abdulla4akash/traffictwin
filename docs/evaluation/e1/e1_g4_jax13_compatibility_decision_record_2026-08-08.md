# E1 G4 JAX/CUDA-13 compatibility-smoke decision record

**Decision date:** 8 August 2026

**Authority:** direct researcher instruction from Abdulla dated 8 August 2026

**Decision:** authorise one separately predeclared G4 compatibility smoke. Do not select a campaign
backend and do not launch a full E1 cell.

**Manifest:**
[`e1_g4_jax13_compatibility_smoke_manifest_v1.json`](e1_g4_jax13_compatibility_smoke_manifest_v1.json)

**Manifest SHA-256:**
`d91abe1f6fb95c22387cd150e5f027483391cc72bf23e8ccd0318e71f8cbf659`

## Immutable prior result

The [first G4 result](e1_colab_g4_backend_smoke_result_v1.json), SHA-256
`cfbe8a966c60b5eae1f784bc51bf8525da91715251573d1491c59dd933fcacc6`, remains immutable
negative evidence. Its exact JAX 0.4.30 CUDA-12 package identities passed, but `ptxas` failed before
task generation on the assigned Blackwell GPU. This new gate neither rewrites that observation nor
labels it successful.

## Single compatibility intervention

All scientific inputs, seeds and controls remain identical: vec_env commit
`0f01f4d2082d3e8b735e74a873095ab8eeba37cc`, tos-data commit
`a75bbdb1a956f828ee0e9b97b33506bd32d31b85`, evaluator and actor identities, Manchester incident
trace, evaluator/fleet seed 0, 2.5x waiting-room ceiling resolved to 6,220 tasks per RSU, ten steps,
sequential/reject/conserved physical semantics, strongest-link placement, fixed 1x service, no load
balancing, no scaling and zero backhaul.

The only intended intervention is the execution stack required for Blackwell compatibility. The
official JAX installation guide recommends the CUDA-13 wheels. The current stable non-prerelease
tag is JAX 0.11.0. A wheel-only CPython-3.12 Linux resolution is frozen in
[`e1_g4_jax13_compatibility_requirements_v1.txt`](e1_g4_jax13_compatibility_requirements_v1.txt),
SHA-256 `e5d604c612002b4ad0054dea7351e59d456e0b59c3d24f0e07b6c00e80426e57`.
It records all 23 packages, including JAX/JAXLIB/plugin/PJRT 0.11.0, NumPy 2.5.1, SciPy 1.18.0
and every resolved CUDA-13 dependency. Nightly builds are prohibited.

If the unchanged evaluator or `vec_jax.py` encounters an API incompatibility requiring a source
edit, execution stops before any evaluator retry. Such an edit would be a separate intervention.

## Primitive and evaluator gates

The CLI must allocate only `e1-g4-jax13-smoke` with `--gpu G4`. Both CLI status and in-runtime
NVIDIA/JAX evidence must confirm the requested G4. Before TrafficTwin, synchronized
`jax.random.PRNGKey(0)`, a small GPU array, and first plus warmed `jax.jit` executions must pass.
Primitive failure permits no evaluator process.

After a primitive pass, exactly two independent serial ten-step evaluator processes may run. Both
must pass the corrected E0 task, rejection, V2I-work, vehicle-work, finite/nonnegative and no-loss
contract. Their scientific summaries must be exactly equal after excluding wall time, and every
instrumentation array must have identical dtype, shape and bytes.

## Cross-backend comparison and materiality

CPU and G4 do not need floating-point byte identity. Every difference is nevertheless retained.
Discrete task streams, decisions, terminal outcomes and aggregate task/rejection counts must be
exact. Continuous arrays and scientific summary fields must satisfy `rtol = 1e-6` and
`atol = 1e-5`. Any difference outside those bounds is classified as scientifically material for
this gate and rejects G4 unless separately investigated; no post hoc tolerance is allowed.

Performance uses the median evaluator-reported wall time from the two fresh processes against the
validated 12.7/12.6-second macOS observations. A speedup of at least 1.25x is the predeclared
“worthwhile” threshold. Primitive first-compile and warmed timings are reported separately. The
ten-step ratio is compilation-heavy and provides only a provisional campaign-runtime estimate.

## Decision outcomes

If scientific compatibility and the 1.25x threshold both pass, the report may recommend G4, but
must not launch the campaign. A separate reviewed change must select G4, freeze the installed
environment and change the campaign matrix to all 15 full cells: fleet seeds 0-4 by all three caps.
Existing macOS seed-0 full outputs would not enter that confirmatory analysis.

If compatibility or worthwhile speed fails, further G4 experimentation stops and the report
recommends the already validated macOS CPU backend. CPU selection and campaign launch still require
the separate campaign-manifest and `RESEARCH_NEXT.md` update; this gate does not perform them.

E2, full runs, other accelerators, scientific source changes, placement/scaling changes, actor
retraining, external-repository writes, PR merge and deletion of negative evidence remain
prohibited.

# E1 waiting-room semantics evidence

This directory records the bounded E1 seed-0/fleet-0 waiting-room pilot at the provisional 0.75x,
2.5x and 40x ceilings. Each point contrasts the pinned evaluator's bundled legacy
snapshot/clamp/legacy semantics with its sequential/reject/conserved physical semantics. The
three-cap record is descriptive single-seed evidence, not a replicated cap sweep.

## Final multi-draw result

The physical E1 campaign is complete under the frozen
[campaign manifest](e1_multidraw_physical_campaign_manifest_v1.json), SHA-256
`0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`. Start with the
[final campaign report](e1_multidraw_physical_campaign_report_2026-08-09.md), then use the
[machine comparison](e1_multidraw_physical_campaign_comparison_v1.json),
[validation](e1_multidraw_physical_campaign_validation_v1.json),
[result summary](e1_multidraw_physical_campaign_result_summary_v1.json),
[evidence index](e1_multidraw_physical_campaign_evidence_index_v1.json) and
[record checksums](e1_multidraw_physical_campaign_checksums_v1.sha256).

All 24 new smokes, 12 new full cells and all 15 analysed full records passed their declared gates.
The primary five-draw `40x - 0.75x` offered-deadline comparison was inconclusive at this
replication size; it is not an equivalence, non-inferiority or tie result. Raw artifacts remain
outside Git. E2 and all extensions remain unauthorised pending a new direct instruction.

The remainder of this page preserves the chronological evidence and authority history.

Start with the cumulative
[E0-to-E1 research record](e1_seed0_three_cap_research_record_2026-08-08.md) and its
[machine-readable summary](e1_seed0_three_cap_research_summary_v1.json). They consolidate the
hypotheses, design, authorization sequence, observations, results, interpretation, validity
limits, evidence hashes and next decision gate without replacing the authoritative per-run
validation records below.

- [Predeclared 2.5x pair manifest](e1_2p5_semantics_pair_manifest_v1.json)
- [Repeated legacy smoke validation](e1_legacy_smoke_validation_v1.json)
- [Full 2.5x pair validation](e1_2p5_semantics_pair_validation_v1.json)
- [Result and readiness report](e1_2p5_semantics_pair_report_2026-08-07.md)
- [Validator](../../../scripts/validate_e1_semantics_pair.py)
- [Focused validator tests](../../../tests/test_validate_e1_semantics_pair.py)
- [Predeclared 0.75x pair manifest](e1_0p75_semantics_pair_manifest_v1.json)
- [0.75x dual-arm repeated-smoke validation](e1_0p75_smoke_validation_v1.json)
- [Full 0.75x pair validation](e1_0p75_semantics_pair_validation_v1.json)
- [0.75x versus 2.5x cap comparison](e1_0p75_vs_2p5_cap_comparison_seed0_v1.json)
- [0.75x result and readiness report](e1_0p75_semantics_pair_report_2026-08-08.md)
- [New-cap pair validator](../../../scripts/validate_e1_new_cap_pair.py)
- [Two-cap comparator](../../../scripts/compare_e1_cap_points.py)
- [New-cap validator tests](../../../tests/test_validate_e1_new_cap_pair.py)
- [Two-cap comparator tests](../../../tests/test_compare_e1_cap_points.py)
- [Predeclared 40x pair manifest](e1_40x_semantics_pair_manifest_v1.json)
- [40x dual-arm repeated-smoke validation](e1_40x_smoke_validation_v1.json)
- [Full 40x pair validation](e1_40x_semantics_pair_validation_v1.json)
- [Three-cap seed-0 comparison](e1_three_cap_sweep_seed0_v1.json)
- [40x result and readiness report](e1_40x_semantics_pair_report_2026-08-08.md)
- [Three-cap comparator](../../../scripts/compare_e1_cap_sweep.py)
- [Three-cap comparator tests](../../../tests/test_compare_e1_cap_sweep.py)

Raw actor, trace and evaluator outputs remain outside TrafficTwin Git. The manifest and report
retain permission-safe logical locators and SHA-256 identities.

At the seed-0 gate, no multi-seed inference was available. Randy's reported `0.6943` remains
unreproduced, and E1 does not address E2 load-aware placement.

The seed-0 decision gate was subsequently closed by the
[multi-draw decision record](e1_multidraw_decision_record_2026-08-08.md). The exact bounded
physical replication is governed by the
[multi-draw campaign manifest](e1_multidraw_physical_campaign_manifest_v1.json), SHA-256
`0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`. Until its checked-in
campaign evidence says otherwise, this paragraph records authority and design rather than a result.

A later same-day researcher instruction paused that campaign pending a
[predeclared Colab GPU backend smoke](e1_colab_gpu_backend_smoke_manifest_v1.json), SHA-256
`5f6a69cea9fd479cf0c8152565bfb52d01b6f080bacf9012da8b8f87708eb5b7`. No campaign cell
may run until the bounded GPU evidence is compared with the validated macOS CPU contract and one
backend is selected in both the campaign manifest and `RESEARCH_NEXT.md`. Cross-backend full results
must not be mixed in the confirmatory five-draw analysis.

Backend-smoke execution materials:

- [private upload-bundle receipt](e1_colab_gpu_backend_bundle_receipt_v1.json);
- [Colab notebook](../../../notebooks/e1_colab_gpu_backend_smoke_v1.ipynb);
- [Colab smoke runner](../../../scripts/run_e1_colab_gpu_backend_smoke.py);
- [focused runner tests](../../../tests/test_run_e1_colab_gpu_backend_smoke.py).

The subsequent G4-only attempt is retained in the
[machine-readable result](e1_colab_g4_backend_smoke_result_v1.json) and
[backend report](e1_colab_g4_backend_smoke_report_2026-08-08.md). Input, package and genuine-GPU
preflight checks passed, but the pinned JAX 0.4.30 toolchain failed before task generation on the
assigned Blackwell device. G4 was not selected, no speedup or conservation comparison is available,
and no full campaign cell started.

A later direct instruction authorises one isolated modern-stack retry. Its
[decision record](e1_g4_jax13_compatibility_decision_record_2026-08-08.md),
[manifest](e1_g4_jax13_compatibility_smoke_manifest_v1.json) and
[complete package lock](e1_g4_jax13_compatibility_requirements_v1.txt) govern that gate. The prior
failure remains immutable. The retry may run only a primitive G4 gate and two ten-step repeats; it
cannot select a campaign backend or launch a full cell by itself.

Compatibility-gate execution materials:

- [private bundle receipt](e1_g4_jax13_compatibility_bundle_receipt_v1.json);
- [bounded compatibility runner](../../../scripts/run_e1_g4_jax13_compatibility_smoke.py);
- [focused comparison tests](../../../tests/test_run_e1_g4_jax13_compatibility_smoke.py).

That separately predeclared retry also stopped before TrafficTwin. All locked inputs and packages
passed on the genuine G4 Blackwell device, but `jax.random.PRNGKey(0)` failed at the mandatory
primitive gate with an observed PJRT FFI/ABI-size mismatch. The
[machine-readable result](e1_g4_jax13_compatibility_smoke_result_v1.json) and
[compatibility report](e1_g4_jax13_compatibility_smoke_report_2026-08-08.md) retain the negative
evidence. No evaluator repeat, conservation comparison, speed measurement or full cell ran.

The direct decision rule therefore closes G4 investigation and selects the already validated
macOS arm64 CPU/JAX 0.4.30 backend in the updated campaign manifest. The final new matrix remains
12 cells for fleet seeds 1-4; the three validated macOS seed-0 physical records are reused by hash.
The exact next process is the two-repeat ten-step gate for seed 1 at 0.75x, not an unconditional
full run.

The [macOS CPU backend selection validation](e1_macos_cpu_backend_selection_validation_v1.json)
records the passing read-only repository, input, interpreter/package/device, reused-seed-0 and
compute/output preflight. It also confirms that the campaign output directory did not exist and no
campaign process had started when CPU was selected.

The first new campaign cell is now complete. Fleet seed 1 at 0.75x passed its two serial ten-step
smokes, exact repeat comparison and 3,600-step full validation. See the
[machine-readable one-cell validation](e1_multidraw_seed1_0p75_cell_validation_v1.json), SHA-256
`b145c801901bf40c1447f3852d8b549a3157d56674acb2b44ea0536d127028ae`, and the
[cell report](e1_multidraw_seed1_0p75_cell_report_2026-08-08.md). All 32 full checks and the 29-file
checksum index passed. That record remains the immutable one-cell evidence; the later three-cap
record below supersedes its historical stop boundary.

Fleet seed 1 is now complete at all three cap points. Its six smokes, three full validations,
cross-cap task-stream identity and 31-check descriptive comparator passed. See the
[seed-1 comparison](e1_seed1_three_cap_comparison_v1.json), [validation](e1_seed1_three_cap_validation_v1.json)
and [campaign report](e1_seed1_three_cap_campaign_report_2026-08-08.md). The
[comparator](../../../scripts/compare_e1_seed_three_cap.py) and
[focused tests](../../../tests/test_compare_e1_seed_three_cap.py) retain the calculation contract.
The seed-1 qualitative admission/rejection/deadline/latency pattern matched seed 0. That record's
stop-before-seed-2 boundary is historical and was later superseded by direct researcher authority;
the final five-draw records at the top of this page now govern the completed result.

# E1 waiting-room semantics evidence

This directory records the bounded E1 seed-0/fleet-0 waiting-room pilot at the provisional 0.75x,
2.5x and 40x ceilings. Each point contrasts the pinned evaluator's bundled legacy
snapshot/clamp/legacy semantics with its sequential/reject/conserved physical semantics. The
three-cap record is descriptive single-seed evidence, not a replicated cap sweep.

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

The seed-0 three-cap pilot is complete, but E1 provides no multi-seed inference, does not
reproduce Randy's reported `0.6943`, and does not address E2 load-aware placement.

The seed-0 decision gate was subsequently closed by the
[multi-draw decision record](e1_multidraw_decision_record_2026-08-08.md). The exact bounded
physical replication is governed by the
[multi-draw campaign manifest](e1_multidraw_physical_campaign_manifest_v1.json), SHA-256
`35531f397bc3ba5c93e2d49ac60b8d0f7bc016121f253bf2cc1496170ec2c66c`. Until its checked-in
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

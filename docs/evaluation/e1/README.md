# E1 waiting-room semantics evidence

This directory records two bounded E1 seed-0/fleet-0 waiting-room points at the provisional 2.5x
and 0.75x ceilings. Each contrasts the pinned evaluator's bundled legacy snapshot/clamp/legacy
semantics with its sequential/reject/conserved physical semantics. The cross-cap record is a
descriptive single-seed comparison, not a completed cap sweep.

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

Raw actor, trace and evaluator outputs remain outside TrafficTwin Git. The manifest and report
retain permission-safe logical locators and SHA-256 identities.

This is not the complete three-cap E1 pilot, provides no multi-seed inference, does not reproduce
Randy's reported `0.6943`, and does not address E2 load-aware placement.

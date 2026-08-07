# E1 waiting-room semantics evidence

This directory records the first bounded E1 unit: one seed-0/fleet-0 comparison at the provisional
2.5x waiting-room ceiling. It contrasts the pinned evaluator's bundled legacy
snapshot/clamp/legacy semantics with its sequential/reject/conserved physical semantics.

- [Predeclared 2.5x pair manifest](e1_2p5_semantics_pair_manifest_v1.json)
- [Repeated legacy smoke validation](e1_legacy_smoke_validation_v1.json)
- [Full 2.5x pair validation](e1_2p5_semantics_pair_validation_v1.json)
- [Result and readiness report](e1_2p5_semantics_pair_report_2026-08-07.md)
- [Validator](../../../scripts/validate_e1_semantics_pair.py)
- [Focused validator tests](../../../tests/test_validate_e1_semantics_pair.py)

Raw actor, trace and evaluator outputs remain outside TrafficTwin Git. The manifest and report
retain permission-safe logical locators and SHA-256 identities.

This is not the complete three-cap E1 pilot, does not reproduce Randy's reported `0.6943`, and
does not address E2 load-aware placement.

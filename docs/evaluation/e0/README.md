# E0 corrected-evaluator validity gate

This directory records the bounded E0 smoke for the corrected Randy/VEC evaluator. Raw actor,
trace and run artifacts remain outside TrafficTwin Git. Their identities are retained by SHA-256.

- [Predeclared machine-readable manifest](e0_manifest_v1.json)
- [Deterministic conservation validation](e0_validation_v1.json)
- [Execution provenance and readiness decision](e0_readiness_report_2026-08-07.md)
- [Full corrected-reference manifest](e0_full_reference_manifest_v1.json)
- [Full corrected-reference validation](e0_full_reference_validation_v1.json)
- [Full corrected-reference result](e0_full_reference_report_2026-08-07.md)
- [Validator](../../../scripts/validate_e0_smoke.py)
- [Focused validator tests](../../../tests/test_validate_e0_smoke.py)

E0 is an accounting validity gate. It does not compare controllers and is not the dissertation
contribution.

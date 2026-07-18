# Diagnostic Report Specification

`DiagnosticReport` is the Phase 5 output of the deterministic rule engine.

Pipeline:

```text
EvidencePack -> evaluate_rules(...) -> DiagnosticReport
```

## Top-Level Fields

- `schema_version`: report schema version, currently `1.0`.
- `report_id`: deterministic for fixed EvidencePack, ruleset version, and clock.
- `evidence_pack_id`: source evidence pack.
- `run_context`: copied from the EvidencePack.
- `generated_at`: injected clock timestamp.
- `ruleset_version`: rule configuration version.
- `rule_config`: full threshold configuration used.
- `results`: ordered `RuleResult` entries.
- `triggered_rule_ids`: rules with triggered hypotheses.
- `insufficient_rule_ids`: rules lacking required evidence.
- `conflicting_rule_ids`: rules with material contradictions.
- `blocked_rules`: rules blocked by missing evidence.
- `evidence_summary`: validation and evidence availability snapshot.
- `overall_readiness`: `ready`, `partially_ready`, `insufficient`, or `invalid`.
- `synthetic`: copied from EvidencePack provenance.
- `provenance`: evidence fingerprint, bundle fingerprint, and metric version.
- `warnings`: technical rule-engine warnings.
- `conflict_observations`: report-level observations preserving mixed hypotheses.

## Rule Results

Each `RuleResult` contains:

- `rule_id`
- `rule_version`
- `title`
- `status`
- `hypothesis`
- `findings`
- `evidence_keys`
- `supporting_evidence`
- `contradicting_evidence`
- `missing_evidence`
- `alternative_explanations`
- `recommendations`
- `confidence`
- `confidence_basis`
- `limitations`
- `synthetic`
- `evaluated_at`

There is deliberately no `proven_cause` field.

## Evidence Keys

The engine validates cited evidence keys against the EvidencePack metric collection.
If a rule cites a missing key, that result is marked `invalid` and a technical warning is added.

## Provenance Use

Diagnostic provenance starts from a `RuleResult`, then traces findings to cited evidence keys,
metric results, metric definitions, canonical evidence, validation findings, and source rows when an
accepted run bundle is available. Recommendations and alternatives are displayed as rule outputs,
not as source evidence.

## JSON Policy

Reports serialise with Pydantic JSON. Golden tests use fixed clocks and projections that exclude volatile timestamps.

No `NaN`, infinity, invented probabilities, or causal-proof language is allowed.

## Related Documents

- [Diagnostic rules](diagnostic_rules.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Provenance Explorer](provenance_explorer.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [API reference](api_reference.md)

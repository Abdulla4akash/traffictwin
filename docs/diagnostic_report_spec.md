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
- `evidence_summary`: validation/evidence availability plus optional temporal status, metric,
  eligible/ineligible counts, and fingerprints.
- `overall_readiness`: `ready`, `partially_ready`, `insufficient`, or `invalid`.
- `synthetic`: copied from EvidencePack provenance.
- `provenance`: evidence fingerprint, bundle fingerprint, and metric version.
- `warnings`: technical rule-engine warnings.
- `conflict_observations`: report-level observations preserving mixed hypotheses.
- `cross_rule_analysis`: typed additive DIA-07 conflict/corroboration/suppression relationships,
  exact overlap, precedence, retained-result fingerprints, and limitations.

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
- `metadata`: rule-specific finite scalar configuration/evaluation details. Declarative rules
  include their definition fingerprint and predicate completeness; R7 also includes its dimension,
  threshold, and support requirement. R8 includes its threshold, support, observed completed-task
  energy, counts, coverage, contract fingerprint, boundary, and denominator policy.

There is deliberately no `proven_cause` field.

`NearestFlipAnalysis` is a separate `DIA-05` artifact rather than a field added to every
DiagnosticReport. It records one selected source result and verified candidate without changing
the source report or ruleset default.

`ThresholdSensitivityReport` is likewise a separate `DIA-06` artifact. It records the complete
evaluated grid and status stability without expanding, suppressing, or rewriting the ordinary
`DiagnosticReport`; sampled intervals and config downloads are sensitivity artifacts, not new
findings or persisted defaults.

`CrossRuleReasoningReport` is embedded because it is a deterministic downstream interpretation of
the complete result set. It never replaces `results`. It records the static policy/version,
activated relationships, exact shared/source-only/target-only keys, source/target precedence and
status, presentation effect, every original result fingerprint, suppressed/unclassified/
unresolved IDs, source-evidence and policy fingerprints, warnings, and limitations. R0 suppression
marks a retained result non-actionable; it does not remove or rewrite it. Legacy R1/R2 conflict
prose is derived from the typed relationship.

## Evidence Keys

The engine validates cited evidence keys against the EvidencePack metric collection.
If a rule cites a missing key, that result is marked `invalid` and a technical warning is added.

## Provenance Use

Diagnostic provenance starts from a `RuleResult`, then traces findings to cited evidence keys,
metric results, metric definitions, canonical evidence, validation findings, and source rows when an
accepted run bundle is available. Recommendations and alternatives are displayed as rule outputs,
not as source evidence.

For TOS source-summary EvidencePacks, aggregate provenance can reach the exact evaluation CSV row,
package commit/fingerprint, run, source experiment grouping, actor, and engine version. Canonical
task and infrastructure links remain explicit unavailable nodes. The separate `vec_env` semantics
commit documents interpretation but is not asserted as the run producer. R0 therefore qualifies the
evidence and R1-R8 remain `insufficient_evidence`; the integration does not reinterpret rule logic.

## JSON Policy

Reports serialise with Pydantic JSON. Golden tests use fixed clocks and projections that exclude volatile timestamps.

No `NaN`, infinity, invented probabilities, or causal-proof language is allowed.

## Related Documents

- [Diagnostic rules](diagnostic_rules.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [Provenance model](provenance_model.md)
- [Provenance Explorer](provenance_explorer.md)
- [Report export](report_export.md)
- [Standalone demo](standalone_demo.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [Declarative diagnostic rules](declarative_rules.md)
- [R7 operational outcome-disparity diagnosis](fairness_diagnosis.md)
- [R8 completed-task energy-anomaly diagnosis](energy_diagnosis.md)
- [Verified nearest-flip analysis](nearest_flip_analysis.md)
- [Threshold-sensitivity explorer](threshold_sensitivity_explorer.md)
- [Deterministic cross-rule reasoning](cross_rule_reasoning.md)
- [API reference](api_reference.md)
- [TOS Data read-only integration](integration/tos_data_adapter.md)

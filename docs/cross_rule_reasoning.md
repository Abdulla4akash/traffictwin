# Deterministic Cross-Rule Reasoning

`DIA-07` adds a typed, additive relationship layer over completed diagnostic `RuleResult` objects.
It records explicitly declared conflict, corroboration, and presentation suppression without
choosing a root cause, inventing probability, or changing an original result.

The implementation is deliberately bounded. It is useful because mixed-fault and incomplete-data
reports become machine-readable and auditable, while undeclared relationships remain absent rather
than guessed.

## Version 1 Policy

| Policy | Activation | Exact connection | Effect |
|---|---|---|---|
| R1/R2 conflict | R1 and R2 are both `triggered` | Both cite `task.generated.count` | Retain both competing candidates; choose no winner |
| R1/R4 corroboration | R1 and R4 are both `triggered` | Both cite `infra.utilisation.mean` | Retain compatible capacity/load-distribution context; do not raise confidence |
| R0 suppression | R0 is `triggered` and explicitly names the target in `blocked_rules` | Explicit readiness-blocker metadata; an exact shared available key is not required | Retain the target and mark it non-actionable while blocked |

R0 data readiness has presentation precedence `100`. Every ordinary diagnostic rule has equal
precedence `50`. There is no ranking among ordinary rules.

R3, R5-R8, undeclared core pairs, and arbitrary declarative rules are unclassified in v1. A
simultaneous trigger, shared word, or shared evidence domain does not create a relationship.

## Retention And Confidence Guarantees

- `DiagnosticReport.results` remains authoritative and unchanged.
- Every input rule ID and timestamp-normalised result fingerprint is recorded.
- A suppression relationship does not delete a result, change its status, remove its evidence, or
  alter its recommendations.
- Conflict chooses no winner.
- Corroboration does not increase categorical confidence.
- No probability, strength score, causal attribution, automatic diagnosis, or new recommendation
  is calculated.
- Exact shared evidence keys record common lineage context; they do not prove independence,
  association, or cause.

## Streamlit Usage

Start TrafficTwin:

```bash
uv run streamlit run src/traffictwin/ui/app.py
```

Open **Diagnostics & Evidence**, then find **Cross-Rule Relationships**. The section shows:

- conflict, corroboration, suppression, and retained-result counts;
- every activated relationship and exact shared key;
- source and target precedence;
- presentation effect and policy statement;
- suppressed-for-action rule IDs, with the originals still shown immediately below;
- unclassified triggered rules;
- policy version, provenance, limitations, and report fingerprint; and
- a complete `CrossRuleReasoningReport` JSON download.

Changing UI state does not change the relationship policy, input evidence, registry, rule results,
or configuration.

## CLI Usage

Inspect the static contract:

```bash
uv run traffictwin diagnose cross-rule-contract --format json
```

Evaluate a bundle or saved EvidencePack and emit only the typed relationship artifact:

```bash
uv run traffictwin diagnose cross-rule PATH_TO_BUNDLE --format json
uv run traffictwin diagnose cross-rule evidence-pack.json --format text
uv run traffictwin diagnose cross-rule PATH_TO_BUNDLE --output cross-rule.json
```

A complete diagnostic report embeds the same artifact:

```bash
uv run traffictwin diagnose report PATH_TO_BUNDLE --format json > diagnostic-report.json
```

The commands import and analyse existing evidence only. They do not launch SUMO or TOS.

## Python Usage

Normal rule evaluation produces the relationship artifact automatically:

```python
from traffictwin.rules.engine import evaluate_rules

diagnostic_report = evaluate_rules(evidence_pack)
cross_rule = diagnostic_report.cross_rule_analysis

if cross_rule is not None:
    print(cross_rule.counts_by_type)
    print(cross_rule.suppressed_rule_ids)
    print(cross_rule.fingerprint())
```

The lower-level service accepts completed results and explicit report provenance:

```python
from traffictwin.diagnostics.cross_rule import evaluate_cross_rule_reasoning

analysis = evaluate_cross_rule_reasoning(
    diagnostic_report.results,
    diagnostic_report_id=diagnostic_report.report_id,
    evidence_pack_id=evidence_pack.pack_id,
    ruleset_version=diagnostic_report.ruleset_version,
    source_evidence_fingerprint=evidence_pack.fingerprint(),
    synthetic=evidence_pack.synthetic,
    generated_at=diagnostic_report.generated_at,
)
```

Inputs must have unique rule IDs and one consistent synthetic/source label. The service sorts by
stable rule ID, does not mutate inputs, and rejects duplicate IDs rather than resolving them
silently.

## Artifact Contents

`CrossRuleReasoningReport` includes:

- schema, policy, analysis, diagnostic-report, EvidencePack, and ruleset identity;
- complete relationship records;
- counts by relationship type;
- retained, suppressed, unclassified-triggered, and unresolved-blocker rule IDs;
- timestamp-normalised fingerprints for every original result;
- source-evidence, result-sequence, and policy-contract fingerprints;
- source/synthetic label, warnings, and limitations.

Each `CrossRuleRelationship` includes the activated policy, relationship type, source/target status,
overlap basis, shared/source-only/target-only evidence keys, precedence, presentation effect,
unchanged result fingerprints, and limitations.

The generated static contract is
[`reference/generated/cross_rule_reasoning_contract.json`](reference/generated/cross_rule_reasoning_contract.json).

## Usage Cases

### Mixed policy and infrastructure candidates

If R1 and R2 both trigger on the same task population, inspect both hypotheses and plan controlled
follow-up experiments. Do not call the relationship proof that either explanation caused the
outcome.

### Compatible under-use and load-distribution context

If R1 and R4 both trigger while citing the same mean-utilisation metric, the report records their
compatible context. Treat this as a navigation aid across two retained hypotheses, not additional
confidence.

### Incomplete evidence

If R0 names R1, R2, or R4 as blocked, the UI highlights those results as non-actionable while still
showing their original insufficient/invalid/other status and reason. Repair evidence and regenerate
the report; do not manually remove the relationship.

### Reproducibility audit

Use the policy, evidence, result-sequence, and per-result fingerprints to verify that two exports
used the same relationship contract and unchanged rule outputs.

## Capability Boundary

The generic import-first adapter declares `cross_rule_reasoning: true` because compatible core
RuleResults can be produced from admitted generic/synthetic evidence. The current SUMO and TOS
source manifests declare `false`: they do not provide the v1 core diagnostic relationship set.

Capability support does not establish scientific calibration or external validity.

## Limitations

- The v1 relationship catalogue is intentionally small and not externally calibrated.
- No relationship is inferred for R3, R5-R8, undeclared core pairs, or local declarative rules.
- Whole-run evidence overlap does not establish temporal overlap.
- Shared evidence can make two rules statistically dependent; no independence claim is made.
- Conflict, corroboration, and suppression are deterministic presentation/context records, not
  causal conclusions.
- A non-relationship does not mean two hypotheses are independent or unrelated in the real system.
- Expert review and controlled fault-injection/generalisation studies remain necessary before
  external diagnostic-validity claims.

## Related Documents

- [Diagnostic rules](diagnostic_rules.md)
- [Diagnostic report specification](diagnostic_report_spec.md)
- [Fault-injection methodology](fault_injection_methodology.md)
- [ADR-027](decisions/ADR-027-deterministic-cross-rule-relationships.md)
- [Limitations and future work](limitations_and_future_work.md)

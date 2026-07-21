# Declarative Diagnostic Rules

TrafficTwin `DIA-04` compiles a bounded trusted-local YAML definition into the same deterministic
`RuleResult` used by core rules. The evaluator reads only already-computed metrics from an
`EvidencePack`; it does not read raw files, calculate new metrics, call a simulator, or execute
Python from YAML.

This is a closed configuration grammar, not a general programming language or a security sandbox.
Only reviewed local rule files should be admitted.

## Supported Grammar

The v1.0 contract supports:

| Element | Supported values |
|---|---|
| Combination | one flat `all` or `any` over 1–16 predicates |
| Numeric operator | `lt`, `lte`, `gt`, `gte` |
| Numeric reducer | `scalar`, `mapping_max_gap` |
| Boolean predicate | exact `boolean_equals` |
| Evidence check | exact metric key, `available` status, exact unit, optional exact scalar metadata |
| Group admission | explicit minimum group count and per-group support metadata |
| Output | hypothesis, findings, evidence citations, alternatives, conditional follow-ups, limitations, and definition fingerprint |

The parser rejects unknown fields, custom tags, anchors/aliases, duplicate keys, multiple YAML
documents, non-UTF-8 input, documents over 65,536 bytes, non-finite thresholds, duplicate
predicate IDs, and reserved core rule IDs. Local identifiers must match `LOCAL_...`.

Imports, function calls, `eval`, `exec`, templates, regular expressions, arbitrary formulas,
nested rule references, dynamic metric keys, and custom reducers are not grammar features. No UI
evaluates YAML; the CLI and Python API call the library compiler.

The generated machine-readable boundary is
[`reference/generated/declarative_rule_contract.json`](reference/generated/declarative_rule_contract.json).

## Minimal Rule

```yaml
schema_version: "1.0"
grammar_version: "1.0"
rule_id: LOCAL_COMPLETION
rule_version: "1.0"
title: Local completion threshold
purpose: Check an already-computed completion ratio.
condition: all
predicates:
  - kind: numeric_threshold
    predicate_id: COMPLETION
    metric_key: task.completion.rate
    reducer: scalar
    operator: gte
    threshold: 0.80
    expected_unit: ratio
    statement: Completion meets the declared local threshold.
triggered_hypothesis: The declared completion threshold is met.
alternative_explanations:
  - the selected run may not represent the intended operating conditions
recommendations:
  - action: repeat the comparison over predeclared common seeds
    rationale: replication can test stability of the observed condition
    expected_direction: variability becomes measurable
    prerequisite: compatible evidence and a predeclared experiment protocol
    verification_step: evaluate the same definition over each compatible EvidencePack
limitations:
  - This local threshold is not a performance standard or causal result.
```

For `mapping_max_gap`, the metric value must be a mapping of finite numbers. The predicate must
also declare `minimum_group_count`, `group_count_metadata_key`, `minimum_group_support`, and
`group_support_metadata_key`. The mapping keys and support keys must match exactly. Null, thin, or
inconsistent groups make the predicate unavailable; they are never discarded or converted to
zero.

## CLI Use

Inspect the contract:

```bash
uv run traffictwin diagnose rule-contract --format json
```

Validate and fingerprint a local file without evaluating it:

```bash
uv run traffictwin diagnose rule-validate local-rule.yaml --format json
```

Evaluate a validated bundle:

```bash
uv run traffictwin diagnose rule-evaluate \
  local-rule.yaml \
  tests/fixtures/bundles/baseline_valid \
  --format json \
  --output /tmp/local-rule-result.json
```

The second input may instead be a saved `EvidencePack` JSON file. It is not a generic metric JSON
or `DiagnosticReport` file.

## Python API

```python
from traffictwin.rules.declarative import (
    evaluate_declarative_rule,
    load_declarative_rule,
)

definition = load_declarative_rule("local-rule.yaml")
result = evaluate_declarative_rule(definition, evidence_pack)
print(definition.fingerprint())
print(result.status)
```

`DeclarativeRuleRegistry` provides explicit in-process registration, stable ordering, duplicate-ID
rejection, an inventory fingerprint, and batch evaluation. It performs no directory scanning or
ambient package discovery.

## Three-Valued Evaluation

Each predicate evaluates to `true`, `false`, or `unavailable`.

- `all`: any false predicate produces `not_triggered`; all true produces `triggered`; otherwise the
  result is `insufficient_evidence`.
- `any`: any true predicate produces `triggered`; all false produces `not_triggered`; otherwise the
  result is `insufficient_evidence`.

An `any` trigger that also has unavailable predicates receives low categorical confidence. A
complete trigger receives moderate confidence. Confidence is not a probability. The result
records the canonical definition fingerprint, grammar version, predicate counts, evidence keys,
and exact missing-evidence reasons.

## Reproducibility And Security Boundary

- Preserve the YAML file and its SHA-256 definition fingerprint with study artifacts.
- Predeclare thresholds before viewing study outcomes when the result supports a research claim.
- Treat local YAML as trusted configuration. The closed grammar prevents YAML-defined code
  execution, but it is not process isolation for the surrounding application.
- A valid definition proves schema admission and deterministic evaluation, not scientific
  validity, calibration, fairness, causality, or external generalisation.
- Core IDs are reserved. R7 is parsed through the same grammar only by the internal built-in path.

The governing decision is
[ADR-023](decisions/ADR-023-declarative-rule-grammar-and-r7-fairness.md).

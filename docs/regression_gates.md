# Versioned Regression Gates

TrafficTwin implements `STA-04` as a deterministic CI gate over an intentionally approved,
versioned golden contract. It answers a narrow software/research-workflow question:

> Does this completed typed artifact still satisfy every declared scalar expectation, tolerance,
> compatibility rule, and source-identity policy?

It does not prove scientific validity, statistical equivalence, causality, improved policy quality,
or deployment safety.

## Supported use cases

Version 1.0 supports:

1. a completed run-level `MetricCollection`, including metrics freshly computed from a validated
   bundle or loaded from the registry; and
2. a completed STA-01 paired `StatisticalStudy` JSON artifact.

Useful examples include:

- exact-fixture CI: detect an unintended change in a synthetic completion-rate result;
- benchmark tolerance CI: require a repeated compatible run to remain inside a declared latency or
  completion boundary while allowing a different input fingerprint;
- method regression CI: pin the paired mean, bootstrap bounds, p-value, or effect-size projection of
  a constructed STA-01 study; and
- release evidence: emit one machine-readable pass/fail/unavailable artifact that retains the
  golden, actual values, errors, tolerances, fingerprints, and limitations.

STA-02 rankings, STA-03 equivalence studies, grouped/array metrics, diagnostic reports, rendered
reports, arbitrary JSON paths, and prose are not admitted in version 1.0.

## Golden lifecycle

A generated golden starts as `candidate`. This prevents the current output from silently accepting
itself as correct. Review the contract, its source identity, expected values, units, implementation
versions, and tolerances. Only then create or edit an `approved` version with:

- a stable `contract_id`;
- a dotted `contract_version` such as `1.0.0`;
- a meaningful description;
- `approved_by` identifying the responsible person or project role; and
- an `approval_note` recording the scope of acceptance.

An unapproved candidate evaluates as `unavailable`, never pass.

Golden files are normal JSON and are suitable for version control. TrafficTwin never overwrites or
updates them during evaluation. When an intentional scientific or implementation change alters an
expectation, review the evidence and create a new contract version; do not widen a tolerance merely
to make CI green.

## Tolerance rule

Every assertion declares both an absolute and relative tolerance. Explicit zero means that form of
movement is not allowed. For expected value `e` and actual value `a`:

```text
absolute_error = abs(a - e)
allowed_error = max(absolute_tolerance, relative_tolerance * abs(e))
pass when absolute_error <= allowed_error
```

The boundary is inclusive. At `e = 0`, the relative component is zero, so a non-zero absolute
tolerance is required to permit movement around zero.

Example: an expected completion rate of `0.80`, absolute tolerance `0.01`, and relative tolerance
`0.02` permits an error of `max(0.01, 0.016) = 0.016`. An actual value from `0.784` through `0.816`
passes that single assertion, subject to floating-point representation and the other compatibility
checks.

TrafficTwin does not infer tolerances from current results, historical variance, confidence
intervals, or synthetic fixtures. Their scientific or operational basis is the owner's decision.

## Source identity policies

Choose one policy in the golden:

| Policy | Meaning |
|---|---|
| `exact` | Require the current metric input fingerprint or complete paired-study input-fingerprint map to equal the approved golden. Use this for deterministic fixtures and exact reproducibility. |
| `compatible_context` | Permit different source inputs only after all typed context and semantic checks pass. Use this for a declared threshold across repeated compatible runs. |

`compatible_context` is not an exact-reproducibility claim. Reports show a warning whenever this
policy is used.

For metric collections, context includes metric-collection version, experiment, seed family,
policy, checkpoint, synthetic label, and environment identity/version or commit. Each asserted metric must
also match its unit and implementation version.

For paired studies, context includes study schema/method/config fingerprints, metric unit,
synthetic label, and compatibility-signature fingerprint. The available scalar selector list is:

```text
pairing_audit.eligible_pair_count
estimate.mean_paired_difference
estimate.sample_sd_paired_difference
estimate.standard_error
bootstrap_interval.lower
bootstrap_interval.upper
randomisation_test.p_value
effect_sizes.cohen_dz
effect_sizes.matched_pairs_rank_biserial
```

## Outcomes and CI exit codes

| Outcome | Exit code | Meaning |
|---|---:|---|
| `passed` | `0` | Every declared assertion was available, compatible, and within tolerance. |
| `failed` | `1` | The comparison was complete, and at least one actual scalar exceeded tolerance. |
| `unavailable` | `2` | Approval, subject, source, context, unit/version, or required scalar evidence was missing or incompatible. |

Unavailable takes precedence over failure when the same multi-assertion gate contains both. This
prevents an obvious failed check from concealing that the complete contract could not be evaluated.
Every individual check remains visible.

## CLI workflow

Publish the method boundary:

```bash
uv run traffictwin experiment regression-contract --format json
```

Generate a candidate golden from a registered metric collection:

```bash
uv run traffictwin experiment regression-golden run-baseline-1 \
  --registry .traffictwin/registry.sqlite \
  --contract-id completion-ci \
  --contract-version 1.0.0 \
  --tolerance task.completion.rate=0.01,0.02 \
  --output contracts/completion-ci-candidate.json
```

After review, create the approved version explicitly:

```bash
uv run traffictwin experiment regression-golden run-baseline-1 \
  --registry .traffictwin/registry.sqlite \
  --contract-id completion-ci \
  --contract-version 1.0.0 \
  --tolerance task.completion.rate=0.01,0.02 \
  --source-identity-policy exact \
  --approval-status approved \
  --approved-by repository-owner \
  --approval-note "Approved for the deterministic baseline fixture" \
  --output contracts/completion-ci-v1.json
```

Evaluate the current registered result:

```bash
uv run traffictwin experiment regression-gate run-baseline-1 \
  --registry .traffictwin/registry.sqlite \
  --golden contracts/completion-ci-v1.json \
  --format json \
  --output exports/completion-ci-result.json
```

For a validated bundle path, use the bundle directory or ZIP as the subject instead of a run ID;
TrafficTwin performs the ordinary validation and metric computation before the gate. For a paired
study, pass its JSON path and add `--subject-kind paired_statistical_study` while creating the
golden. Gate evaluation infers the subject kind from that golden.

Available output formats are `json`, `markdown`, and `csv`. In a shell CI job, preserve and act on
the process exit code rather than grepping formatted text.

## Streamlit workflow

1. Open **Analysis → Statistical Study**.
2. Select **Versioned regression gate (STA-04)**.
3. Upload an existing candidate or approved golden JSON.
4. For a metric golden, select the registered run. For a paired-study golden, first evaluate the
   matching STA-01 study in the same UI session.
5. Select **Evaluate regression gate**.
6. Inspect the overall status, every expected/actual/error/tolerance row, blocking compatibility
   findings, ignored-field count, source policy, and fingerprints.
7. Download the reconciled JSON, Markdown, or CSV artifact.

The UI evaluates and displays the uploaded contract. It does not generate, edit, approve, persist,
or widen a golden.

## Python API

```python
from traffictwin.experiments import (
    GoldenApprovalStatus,
    RegressionToleranceSpec,
    build_regression_golden_contract,
    evaluate_regression_gate,
)

golden = build_regression_golden_contract(
    metric_collection,
    contract_id="completion-ci",
    contract_version="1.0.0",
    description="Approved deterministic completion fixture",
    tolerances=[
        RegressionToleranceSpec(
            selector="task.completion.rate",
            absolute_tolerance=0.01,
            relative_tolerance=0.02,
        )
    ],
    approval_status=GoldenApprovalStatus.APPROVED,
    approved_by="repository-owner",
    approval_note="Approved for the versioned synthetic fixture",
)

report = evaluate_regression_gate(metric_collection, golden)
print(report.status.value)
print(report.to_json())
```

## Evidence and provenance

The golden fingerprints its complete approval, context, source policy, assertions, expected values,
units, versions, and tolerances. The gate report records:

- the embedded golden and its fingerprint;
- timestamp-normalised subject fingerprint;
- source-identity fingerprint;
- every assertion and blocking finding;
- expected and actual values, unit, absolute/relative tolerance, allowed error, absolute/relative
  error, and reason code;
- pass/fail/unavailable and ignored-field counts;
- method-contract fingerprint, warnings, and limitations; and
- a deterministic report fingerprint with only `generated_at` normalised.

Inputs are copied for evaluation checks and verified unchanged. Raw source data and registry state
are never modified.

## Interpretation limits

- A pass applies only to selected assertions; unselected fields may have changed.
- A fail is a versioned numerical regression decision, not proof that a policy is scientifically
  worse or an implementation is unusable.
- Unavailable means the contract could not make its declared comparison; it is not a pass.
- Synthetic golden results establish software/method behavior only.
- Golden approval and tolerance justification remain human research/project decisions.
- The regression gate does not replace STA-01 inference, STA-03 equivalence testing, validation,
  provenance review, or external evaluation.

The complete method decision is recorded in
[ADR-031](decisions/ADR-031-versioned-regression-gates.md), and the generated machine-readable
boundary is [regression_gate_contract.json](reference/generated/regression_gate_contract.json).

# Paired Equivalence Testing

TrafficTwin implements `STA-03` as a predeclared paired-mean two one-sided tests procedure (TOST)
over the exact common-random-seed cohort admitted by `STA-01`.

Use it to ask a bounded question such as:

> Is the mean completion-rate change between this variation and baseline precise enough to lie
> strictly within a practically negligible region of `-0.02` to `+0.02`?

It does **not** turn an ordinary non-significant difference test into equivalence. It also does not
prove that two policies are identical, interchangeable in every metric, causally similar, or safe
to deploy.

## Required analysis plan

Before evaluating the data, declare:

- registered experiment, baseline family, variation family, policy, checkpoint, and scalar metric;
- the exact common random-seed set from the registered experiment;
- a finite positive symmetric absolute margin in the metric's original unit;
- margin basis: `practical_threshold`, `literature`, or `provisional_design`;
- a written justification and, for `literature`, a reference;
- one-sided alpha, normally `0.05`; and
- the single predeclared comparison policy.

TrafficTwin deliberately provides no universal default margin. A `0.02` completion-rate margin,
`5 ms` latency margin, and `0.1 J/task` energy margin have different practical meanings. The
researcher must defend the selected value from domain requirements, literature, stakeholder
requirements, or label it explicitly provisional.

## Evidence boundary

The service evaluates the existing [`STA-01` pairing contract](statistical_studies.md) first. It
therefore requires exactly one compatible endpoint for baseline and variation at each admitted
`random_seed`, with matching:

- experiment, policy, checkpoint, metric, unit, and implementation versions;
- synthetic/source mode and environment identity/version or commit;
- source input fingerprints; and
- energy, fairness, plugin, target-RSU, or spatial semantic fingerprints when applicable.

Missing, partial, unavailable, non-scalar, non-finite, duplicate, unmatched, unplanned, or
incompatible endpoints remain in the pairing audit. They are never zero-filled or selected by
input order. Multiple compatibility signatures make the study incompatible; TrafficTwin does not
choose a favourable subgroup.

## Method

For paired differences `variation - baseline`, symmetric margin `m`, and predeclared one-sided
alpha, version 1.0 tests:

1. `H0 lower: mean <= -m` against `H1 lower: mean > -m`; and
2. `H0 upper: mean >= +m` against `H1 upper: mean < +m`.

Equivalence is demonstrated only when both one-sided p-values are strictly below alpha. The same
decision is shown as the `100 × (1 - 2 alpha)%` paired Student-t interval lying strictly inside
`(-m, +m)`. For alpha `0.05`, this is a 90% interval.

The method requires at least three compatible pairs, positive finite paired-difference sample
variance, independence across random-seed experimental units, and approximately normal paired
differences. Student-t probabilities and critical values use a deterministic versioned
regularised-incomplete-beta implementation checked against reference quantiles.

## Conclusions and unavailable states

| Result | Meaning |
|---|---|
| `equivalence_demonstrated` | Both predeclared one-sided nulls rejected and the interval lies strictly inside the margin. |
| `equivalence_not_demonstrated` | The method ran, but at least one null did not reject. This does not prove meaningful difference. |
| `insufficient` | Fewer than three compatible pairs were admitted. |
| `incompatible` | The inherited pairing cohort did not define one compatibility signature. |
| `degenerate` | Paired-difference sample variance was zero or invalid, so finite Student-t statistics were unavailable. |

Objective direction affects the inherited descriptive favourable/unfavourable labels only. It
never reverses the stored difference, margin, hypotheses, interval, or equivalence conclusion.

## Streamlit usage

1. Open **Analysis → Statistical Study**.
2. Select **Paired equivalence TOST (STA-03)**.
3. Choose the registered experiment, variation, policy, checkpoint, and metric.
4. Enter the absolute margin in that metric's displayed unit.
5. Select and justify the margin basis; add a reference when the basis is `literature`.
6. Choose alpha and click **Evaluate equivalence study**.
7. Inspect both one-sided p-values, the interval, conclusion, exact pairs, and inherited audit.
8. Download the reconciled JSON, Markdown, or CSV artifact.

The UI keeps the plan in the current session only. It does not persist, recommend, or validate the
scientific adequacy of the margin.

## CLI usage

Publish the method contract:

```bash
uv run traffictwin experiment equivalence-contract --format json
```

Evaluate one registered comparison:

```bash
uv run traffictwin experiment equivalence-study \
  --registry .traffictwin/registry.sqlite \
  --experiment-id exp-paired \
  --baseline-seed seed-baseline \
  --variation-seed seed-variation \
  --algorithm policy-a \
  --metric task.completion.rate \
  --equivalence-margin 0.02 \
  --margin-basis practical_threshold \
  --margin-justification "Two percentage points is the predeclared practical limit" \
  --alpha 0.05 \
  --format json \
  --output exports/completion-equivalence.json
```

For a literature basis, also pass `--margin-reference`. Formats are `json`, `markdown`, and `csv`.
An available study exits `0` whether equivalence is demonstrated or not. Insufficient,
incompatible, or degenerate studies still emit the typed artifact and exit `1`.

## Python usage

```python
from traffictwin.experiments.equivalence_testing import (
    EquivalenceMarginBasis,
    EquivalenceStudyConfig,
    evaluate_equivalence_study,
)

plan = EquivalenceStudyConfig(
    experiment_id="exp-paired",
    baseline_seed_id="seed-baseline",
    variation_seed_id="seed-variation",
    algorithm="policy-a",
    metric_key="task.completion.rate",
    equivalence_margin=0.02,
    margin_basis=EquivalenceMarginBasis.PRACTICAL_THRESHOLD,
    margin_justification="Predeclared practical completion-rate limit",
    expected_random_seeds=[1, 2, 3, 4, 5],
)
study = evaluate_equivalence_study(metric_collections, plan)
```

The returned `EquivalenceStudy` contains the exact plan and fingerprint, copied pairing audit and
observations, TOST estimate/tests/interval/conclusion, source STA-01 fingerprint, immutable input
fingerprints, provenance, warnings, assumptions, and limitations.

## Synthetic demo artifact

`traffictwin demo initialise` writes:

- `exports/synthetic_equivalence_study.json`;
- `exports/synthetic_equivalence_study.md`; and
- `exports/synthetic_equivalence_study_audit.csv`.

These files use a constructed, explicitly synthetic provisional margin to verify the method and
export paths. They are not real experiment results or evidence that a dissertation metric has a
defensible margin.

## Reporting checklist

Report all of the following together:

- metric, original unit, estimand, baseline/variation direction, policy, and checkpoint;
- exact margin, basis, justification, reference, and confirmation it was predeclared;
- alpha, TOST method/version, `n`, degrees of freedom, mean, SD, and standard error;
- both one-sided hypotheses, statistics, p-values, and rejection decisions;
- corresponding confidence interval and strict margin containment;
- missing, duplicate, incompatible, and expected-seed audit;
- source mode, environment/semantic compatibility, fingerprints, assumptions, and limitations.

The method decision is recorded in
[ADR-030](decisions/ADR-030-paired-tost-equivalence-testing.md). The machine-readable contract is
[equivalence_testing_contract.json](reference/generated/equivalence_testing_contract.json).

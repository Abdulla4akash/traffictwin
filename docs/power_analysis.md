# Paired Common-Seed Power Analysis

`STA-05` is a deterministic prospective sample-size helper for one two-sided baseline-versus-
variation paired comparison. It estimates the minimum number of common random seeds required under
a declared target effect, prospective paired-difference variance, alpha, target power, and bounded
normal-approximation method.

The output is always a **planning aid, not a guarantee**. It does not prove that a completed study
was adequately powered and does not choose a scientifically meaningful effect or variance for the
researcher.

## Supported use cases

Use the helper to:

- plan how many common random seeds to request before producing confirmatory baseline and
  variation runs;
- compare prospective plans with different predeclared alpha or target-power values;
- record whether an effect or variance came from a practical threshold, literature, pilot study,
  synthetic fixture, or provisional design choice;
- expose small-pilot, small-planned-sample, synthetic, and provisional qualifications;
- export a deterministic JSON, Markdown, or CSV planning artifact for a protocol or dissertation
  appendix; and
- reproduce the exact versioned calculation and its assumptions from a config fingerprint.

Do not use it as retrospective observed power, a significance prediction, an automatic budget
recommendation, or proof of practical importance, equivalence, causality, or external validity.

## Method boundary

Version 1.0 implements `two_sided_paired_mean_normal_approximation_v1`. For target-effect magnitude
`|delta|`, prospective paired-difference standard deviation `sigma`, common-seed pair count `n`, and
two-sided critical value `z`, it evaluates:

```text
lambda(n) = sqrt(n) * |delta| / sigma
power(n)  = Phi(-z - lambda(n)) + Phi(lambda(n) - z)
z         = Phi^-1(1 - alpha/2)
```

TrafficTwin searches the declared integer range and returns the smallest `n` whose approximate
power is at least the target. When possible it records power at `n - 1` to demonstrate that the
reported boundary is minimal. Each common seed requires two compatible policy runs, so the artifact
also reports `2n` total baseline-plus-variation runs.

The prospective variance must describe variation-minus-baseline paired differences in the metric's
unit squared. A run-level variance, separate-group variance, standard deviation, or standard error
is not interchangeable with this input.

## Required planning inputs

| Input | Meaning |
|---|---|
| `metric_key` | Scalar outcome being planned. |
| `unit` | Original metric unit; variance therefore has `unit^2`. |
| `target_effect` | Signed variation-minus-baseline mean effect. Two-sided power uses its magnitude while preserving the sign in provenance. |
| `paired_difference_variance` | Prospective variance of complete paired differences. |
| `alpha` | Two-sided type-I error rate, from `0.001` through `0.20`. |
| `target_power` | Desired approximate power, from `0.50` through `0.999`. |
| `target_effect_basis` | `practical_threshold`, `literature`, `pilot_study`, `synthetic`, or `provisional_design`. |
| `variance_basis` | `literature`, `pilot_study`, `synthetic`, or `provisional_design`. |
| justifications | At least 12 non-space characters for both inputs. |
| references | Required for each input claimed to be literature-based. |
| `pilot_sample_size` | Required when either input is pilot-derived. |
| `synthetic` | Must be true when either input basis is synthetic. |
| `maximum_replicates` | Bounded search ceiling, default `100000`, maximum `1000000`. |

The repository deliberately supplies no universal target effect or variance. Those are
study-specific scientific decisions and should be declared before confirmatory results are
inspected.

## Labels and warnings

Every artifact includes `planning_aid_not_a_guarantee`. Additional labels are deterministic:

- `small_pilot_sample`: the declared pilot has fewer than 30 pairs;
- `small_planned_sample`: the returned plan has fewer than 30 pairs;
- `synthetic_input`: at least one planning input is labelled synthetic; and
- `provisional_input`: at least one input has a provisional-design basis.

The threshold of 30 is a visible approximation warning, not a rule that makes 30 observations
automatically sufficient. Normal approximation quality still depends on the paired-difference
distribution and variance uncertainty.

## Unavailable states

TrafficTwin returns a typed `unavailable` calculation rather than a number when:

- `ZERO_TARGET_EFFECT`: zero effect has no finite positive-effect sample-size solution;
- `NON_POSITIVE_VARIANCE`: version 1.0 requires a positive planning variance; or
- `MAXIMUM_REPLICATES_EXCEEDED`: the requested power was not reached by the declared ceiling.

Invalid non-finite values, unsupported bounds, missing pilot sizes, missing literature references,
short justifications, and unlabelled synthetic bases are rejected as invalid plans. Unavailable is
never displayed as zero.

## CLI workflow

Inspect the method contract:

```bash
uv run traffictwin experiment power-contract --format json
```

Calculate a prospective plan:

```bash
uv run traffictwin experiment power-analysis \
  --metric task.completion.rate \
  --unit ratio \
  --target-effect 0.05 \
  --paired-difference-variance 0.0025 \
  --effect-basis practical_threshold \
  --effect-justification "Minimum difference worth detecting in the planned study" \
  --variance-basis pilot_study \
  --variance-justification "Paired-difference variance from the documented pilot" \
  --pilot-sample-size 12 \
  --alpha 0.05 \
  --target-power 0.80 \
  --format json \
  --output power-plan.json
```

Use `--format markdown` or `--format csv` for reconciled human-readable exports. An available plan
exits `0`; a typed unavailable result or invalid plan exits `2`.

For a synthetic planning demonstration, use synthetic bases and include `--synthetic`:

```bash
uv run traffictwin experiment power-analysis \
  --metric task.completion.rate \
  --unit ratio \
  --target-effect 0.05 \
  --paired-difference-variance 0.0025 \
  --effect-basis synthetic \
  --effect-justification "Synthetic target for deterministic method demonstration" \
  --variance-basis synthetic \
  --variance-justification "Synthetic variance for deterministic method demonstration" \
  --synthetic
```

## Streamlit workflow

1. Open **Analysis → Statistical Study**.
2. Choose **Power analysis helper (STA-05)**.
3. Declare the metric, unit, target paired effect, paired-difference variance, alpha, and target
   power.
4. Select and justify the effect and variance bases. Supply references or pilot size when required.
5. Mark synthetic inputs explicitly and set the bounded maximum pair count.
6. Select **Calculate required common-seed pairs**.
7. Review the required pair count, total policy-run count, achieved and preceding approximate
   power, labels, warnings, assumptions, and provenance.
8. Download JSON, Markdown, or CSV without changing the calculation.

The page contains no power formula. It builds `PowerAnalysisConfig`, calls the UI service, and
renders the typed library artifact.

## Python API

```python
from traffictwin.experiments.power_analysis import (
    PairedVarianceBasis,
    PowerAnalysisConfig,
    TargetEffectBasis,
    evaluate_power_analysis,
)

config = PowerAnalysisConfig(
    metric_key="task.completion.rate",
    unit="ratio",
    target_effect=0.05,
    paired_difference_variance=0.0025,
    target_effect_basis=TargetEffectBasis.PRACTICAL_THRESHOLD,
    target_effect_justification="Minimum difference worth detecting in the planned study",
    variance_basis=PairedVarianceBasis.PILOT_STUDY,
    variance_justification="Paired-difference variance from the documented pilot",
    pilot_sample_size=12,
)
analysis = evaluate_power_analysis(config)
print(analysis.calculation.required_common_seed_replicates)
print(analysis.labels)
```

Use `power_analysis_method_contract()`, `power_analysis_to_markdown()`, and
`power_analysis_to_csv()` for the machine-readable contract and alternate renderings.

## Interpreting the result

Suppose `target_effect=0.5`, paired variance `1.0`, two-sided alpha `0.05`, and target power `0.80`.
Version 1.0 returns 32 common-seed pairs: approximate power at 32 is `0.80743`, while power at 31
is `0.79501`. This means 64 planned policy runs under the assumption that every seed produces one
compatible baseline and one compatible variation result.

It does not mean that 32 guarantees significance. The true effect and variance may differ, runs
may be missing or incompatible, the distribution may challenge the normal approximation, and the
eventual analysis method may have different power.

## Evidence and provenance

`PowerAnalysis` records:

- schema and method versions;
- the complete strict config and its fingerprint;
- signed and standardized effects, variance and standard deviation;
- alpha, target power, critical value, required pairs and total runs;
- achieved and preceding approximate power;
- bases, references, justifications, pilot size, and synthetic flag;
- labels, warnings, assumptions, limitations, and stable reason code; and
- method-contract and timestamp-normalised artifact fingerprints.

The explicitly synthetic demo workspace exports:

- `exports/synthetic_power_analysis.json`;
- `exports/synthetic_power_analysis.md`; and
- `exports/synthetic_power_analysis.csv`.

## Interpretation limits

- This is prospective normal-approximation planning, not exact power for the STA-01 sign-flip test.
- It does not calculate paired TOST, N-way, multiple-comparison, sequential, adaptive, cluster,
  simulation-based, or unpaired power.
- It does not automatically extract observed effects or variance from stored results and does not
  calculate retrospective power.
- It assumes independent common-seed pairs, fixed prospective variance, complete compatible runs,
  one two-sided comparison, and no attrition.
- It does not validate practical or literature claims supplied by the researcher.
- Small-pilot, small-planned, synthetic, and provisional labels must remain visible in reports.
- It adds no simulator launcher and does not create or execute a run protocol.
- Power does not establish effect importance, policy superiority, equivalence, causality, external
  validity, or deployment suitability.

The binding method decision is
[ADR-032](decisions/ADR-032-paired-normal-power-planning.md). The generated contract is
[power_analysis_contract.json](reference/generated/power_analysis_contract.json).

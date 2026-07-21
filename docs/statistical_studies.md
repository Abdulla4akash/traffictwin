# Common-Seed Paired Statistical Studies

TrafficTwin implements `STA-01` as a deterministic, predeclared comparison of one variation with
one baseline over compatible common-random-seed replicates. It answers a bounded question:

> For this experiment, policy/checkpoint, metric, environment contract, and declared seed set,
> what is the mean variation-minus-baseline paired difference, its bootstrap uncertainty, its
> two-sided sign-flip result, and the paired effect sizes?

It does not prove causality, practical importance, equivalence, external validity, or adequate
power. Those claims require separate designs and evidence.

For ranking two or more policies over identical complete common seeds, use the separate
implemented [STA-02 N-way workflow](n_way_ranking.md). It reuses the winner map and does not change
this single-contrast test. For a positive practical-equivalence claim over this same pairing
cohort, use the separate implemented [STA-03 paired TOST workflow](equivalence_testing.md).
To pin a completed metric collection or this study's stable scalar projection for CI, use the
separate implemented [STA-04 regression-gate workflow](regression_gates.md); a passing gate is not
an equivalence conclusion.

## When To Use It

Use a paired study when:

- a registered `Experiment` declares baseline and variation seeds plus common random seeds;
- the external producer has completed those planned replicates;
- each result has been imported and stored as a completed `MetricCollection`;
- the baseline and variation collections describe the same algorithm, checkpoint, metric contract,
  environment contract, and random-seed experimental unit; and
- one metric and objective direction were chosen before inspecting the result.

Do not use it to compare unrelated runs, select a favourable subset after inspection, treat absent
replicates as zero, compare mixed units/contracts, or claim that non-significance means equivalence.

## Analysis Plan

`PairedStudyConfig` fixes the full plan:

| Field | Meaning |
|---|---|
| `experiment_id` | Registered experiment whose run plan is being evaluated. |
| `baseline_seed_id` / `variation_seed_id` | Exact two seed roles. They must differ. |
| `algorithm` / `checkpoint` | Exact policy implementation identity. |
| `metric_key` | One scalar metric. Default: `task.completion.rate`. |
| `objective` | `maximise` or `minimise`; affects interpretation labels only. |
| `expected_random_seeds` | Exact predeclared pairing population. |
| `confidence_level` | Percentile-bootstrap interval level; default `0.95`. |
| `bootstrap_repetitions` | Deterministic paired resamples; default `10,000`, allowed `1,000–100,000`. |
| `randomisation_repetitions` | Monte Carlo sign assignments above 16 pairs; same bounds/default. |
| `resampling_seed` | Local reproducibility seed; default `20260720`. |

The study always defines a difference as:

```text
paired difference = variation metric value - baseline metric value
```

The objective never changes that sign. For a maximised metric a positive difference favours the
variation; for a minimised metric a negative difference favours it.

## Compatibility And Pairing Audit

The exact pairing key is `random_seed`. A pair is admitted only when both endpoints are complete,
finite scalar observations and all applicable contracts agree. The audit checks:

- experiment, baseline/variation role, algorithm, checkpoint, and declared seed;
- metric-collection and metric-implementation version;
- metric unit and synthetic/real label;
- environment name plus version or commit;
- immutable source fingerprint for each endpoint; and
- energy, fairness, custom-plugin, target-RSU, or spatial-grid semantic fingerprints where
  applicable.

Every unplanned, unavailable, non-scalar, unmatched, duplicate, or incompatible input remains in a
typed exclusion. Expected seeds without a usable pair remain visible. TrafficTwin never silently
chooses one duplicate, one compatibility subgroup, or a convenient subset.

At least three compatible pairs are required for inferential components. With fewer, the artifact
is `insufficient` but still contains the observations, source fingerprints, exclusions, and reason.

## Statistical Methods

### Primary estimand

The primary effect is the arithmetic mean of complete paired differences in the original metric
unit. The artifact also reports sample standard deviation, standard error, range, `n`, and the
objective-aware interpretation.

### Paired percentile-bootstrap interval

TrafficTwin resamples whole paired differences with replacement and computes their mean. It uses a
local seeded Python Mersenne Twister and deterministic linear-interpolated percentile endpoints.
The default is 10,000 repetitions at 95% confidence. This is empirical paired-sample uncertainty,
not a population or external-validity guarantee.

### Two-sided paired sign-flip test

The test statistic is the absolute mean paired difference. Up to 16 pairs, every one of the `2^n`
sign assignments is enumerated. Above 16, the declared number of assignments is sampled with a
separate local seed, and the p-value uses the plus-one correction. The null requires exchangeable
paired-difference signs under a sharp zero effect. The method is always two-sided; TrafficTwin does
not choose a one-sided alternative after seeing results.

### Effect sizes

The original-unit mean paired difference is primary. Secondary outputs are:

- Cohen's `dz`, only when the paired-difference sample standard deviation is non-zero; and
- matched-pairs rank-biserial correlation over non-zero absolute-rank differences, with ties kept
  separately.

Cliff's delta is explicitly `not_calculated_for_paired_primary_design`; it is an unpaired dominance
measure and is not silently substituted for a paired effect.

## Streamlit Usage

Start TrafficTwin using the normal workspace command, then open **Analysis → Statistical Study**:

```bash
uv run traffictwin demo initialise .traffictwin-demo
uv run traffictwin demo launch .traffictwin-demo
```

On the page:

1. select a registered experiment that has stored metric collections;
2. select baseline and variation seeds, algorithm, optional checkpoint, metric, and objective;
3. confirm the exact common-seed plan and resampling settings;
4. choose **Evaluate paired study**;
5. inspect the plan, pairing audit, exclusions, estimate, interval, test, and effect sizes; and
6. download strict JSON, Markdown, or the pair-audit CSV.

The page performs no statistical calculation. It validates the registered plan and delegates to
the same library service used by the CLI. If no eligible experiment exists, the control remains
visibly unavailable instead of displaying invented data.

## CLI Usage

Inspect the immutable method boundary:

```bash
uv run traffictwin experiment study-contract --format text
uv run traffictwin experiment study-contract --format json
```

Evaluate a registered study and print strict JSON:

```bash
uv run traffictwin experiment statistical-study \
  --registry .traffictwin-demo/registry.sqlite \
  --experiment-id EXPERIMENT_ID \
  --baseline-seed BASELINE_SEED_ID \
  --variation-seed VARIATION_SEED_ID \
  --algorithm ALGORITHM \
  --metric task.completion.rate \
  --objective maximise \
  --confidence-level 0.95 \
  --bootstrap-repetitions 10000 \
  --randomisation-repetitions 10000 \
  --resampling-seed 20260720 \
  --format json
```

Add `--checkpoint CHECKPOINT` when the registered plan requires one. Use `--format markdown` for a
human-readable study or `--format csv` for the complete pair/exclusion audit. `--output PATH`
writes the selected representation. An available study exits `0`; an insufficient or incompatible
study still emits its typed artifact and exits `1`.

The command rejects a baseline/variation/algorithm/checkpoint/common-seed selection that does not
exactly match the registered `Experiment`.

## Python Usage

```python
from traffictwin.experiments.statistical_study import (
    PairedStudyConfig,
    evaluate_paired_statistical_study,
)

plan = PairedStudyConfig(
    experiment_id="experiment-01",
    baseline_seed_id="baseline",
    variation_seed_id="variation",
    algorithm="policy-a",
    checkpoint="checkpoint-100",
    metric_key="task.completion.rate",
    objective="maximise",
    expected_random_seeds=[1, 2, 3, 4, 5],
    confidence_level=0.95,
    bootstrap_repetitions=10_000,
    randomisation_repetitions=10_000,
    resampling_seed=20260720,
)

study = evaluate_paired_statistical_study(metric_collections, plan)
print(study.to_json())
```

`metric_collections` is the sequence of already-computed `MetricCollection` artifacts. The service
does not read raw rows, recompute metrics, mutate collections, or persist a result. Callers can use
`statistical_study_to_markdown(study)` and `statistical_study_pairs_to_csv(study)` for deterministic
exports.

## Reading A Result

Read the artifact in this order:

1. **Status and plan:** confirm the intended experiment, metric, direction, seeds, and method.
2. **Pairing audit:** confirm expected, eligible, missing, unmatched, duplicate, and excluded seeds.
3. **Original-unit effect:** interpret the signed mean in the metric's actual unit.
4. **Interval:** report both endpoints and method/repetition/seed details.
5. **Sign-flip test:** report mode, assignment count, two-sided p-value, and exchangeability
   assumption.
6. **Secondary effects:** state why `dz` or rank-biserial is available or unavailable.
7. **Provenance and limits:** retain the config, method, compatibility, source, and artifact
   fingerprints plus every warning and limitation.

For example, `mean_paired_difference = 0.04` for a maximised completion-rate fraction means the
variation averaged four percentage points higher over the admitted common seeds. It does not mean
the variation caused the increase, will generalise, or is practically worthwhile.

## Reproducibility And Validation

The artifact records schema/method version `1.0`, the complete plan and its fingerprint, every
source collection fingerprint, the compatibility-signature fingerprint, pair values, exclusions,
method seeds/repetitions, method-contract fingerprint, and a timestamp-normalised artifact
fingerprint. Ambient random state is never read.

Constructed-distribution tests pin known effect and null behavior, exact and Monte Carlo sign-flip
modes, bootstrap determinism, effect sizes, objective interpretation, missingness, duplicate keys,
environment/semantic incompatibility, timestamp and input-order stability, source immutability,
strict bounds, CLI behavior, UI services, page rendering, and golden output.

The method decision is [ADR-028](decisions/ADR-028-common-seed-paired-statistical-study.md). The
machine-readable method contract is
[statistical_study_contract.json](reference/generated/statistical_study_contract.json).

## Explicit Limits And Next Capabilities

- One baseline-versus-variation comparison only; implemented N-way ranking is the separate
  `STA-02` artifact.
- The STA-01 artifact makes no equivalence claim; implemented paired TOST is the separate `STA-03`
  artifact with its own predeclared margin and hypotheses.
- CI regression is the separate implemented `STA-04` artifact with an approved golden, explicit
  tolerances, and pass/fail/unavailable semantics.
- No retrospective-power calculation or automatic target-effect/variance extraction. Prospective
  paired planning is the separate implemented `STA-05` method documented in
  [paired common-seed power analysis](power_analysis.md).
- No post-hoc subgroup search, multiplicity correction for undeclared families, causal attribution,
  external calibration, Bayesian inference, or model-based adjustment.
- Current SUMO and TOS adapters do not meet the registered common-seed study boundary, so the
  capability remains unavailable there.
- Synthetic known-distribution evidence validates implementation behavior only, not a real policy,
  Manchester transport conditions, Randy/VEC, or any deployment claim.

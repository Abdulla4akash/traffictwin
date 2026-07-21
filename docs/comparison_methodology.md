# Comparison Methodology

Phase 3 comparisons are deterministic descriptive comparisons. They do not make causal claims and do not present one run as a definitive algorithm conclusion.

## Pairwise Comparison

Inputs:

- baseline `MetricCollection`;
- variation `MetricCollection`;
- optional baseline and variation seed snapshots;
- `ComparisonRequest`.

Compatibility checks include:

- metric version;
- unit;
- metric availability;
- same experiment when required;
- same random seed when required;
- scalar numeric value.

Mismatches produce unavailable metric comparisons where possible rather than rejecting the whole report.

## Delta Policy

```text
absolute_delta = variation - baseline
relative_delta = (variation - baseline) / abs(baseline)
```

Zero-baseline policy:

- baseline `0`, variation `0`: relative delta is `0`;
- baseline `0`, variation non-zero: relative delta is unavailable with `BASELINE_ZERO`;
- infinity and `NaN` are never emitted.

Direction is neutral:

- `increased`;
- `decreased`;
- `unchanged`;
- `unavailable`.

TrafficTwin does not label a metric as improved or worsened automatically in Phase 3.

## Seed Diff

When seed snapshots are available, the comparison report includes a deterministic structured diff of experimental parameters. Identity and display fields are excluded:

- schema version;
- seed ID;
- name;
- description;
- parent seed ID;
- `compare_against`;
- provenance.

Synthetic baseline-versus-variation fixtures currently show changes in demand multiplier, workload birth-rate multiplier, RSU capacity mode, and failed RSUs.

## Experiment Aggregation

Experiment aggregation groups metric collections by:

- experiment ID;
- seed ID;
- algorithm;
- checkpoint.

For scalar available metrics, the report includes:

- replicate count;
- arithmetic mean;
- sample standard deviation when `n >= 2`;
- minimum;
- maximum;
- P50 using the same linear interpolation method as run metrics.

Paired summaries align baseline and variation conditions by common random seed and report:

- paired count;
- unmatched baseline random seeds;
- unmatched variation random seeds;
- mean paired difference;
- sample standard deviation of paired differences when `n >= 2`.

These Phase 3 summaries remain descriptive. Formal paired inference is implemented separately by
`STA-01` and never inferred automatically from a descriptive comparison. A `PairedStudyConfig`
must predeclare the experiment, exact common-seed contrast, metric, objective, and method settings;
only compatible complete `MetricCollection` endpoints are admitted. See
[common-seed paired statistical studies](statistical_studies.md).

For two or more policies, `STA-02` forms identical complete common-seed rows independently inside
each selected scenario family, excludes incompatible evidence, delegates objective/tie/rank/regret
to the existing winner map, and jointly bootstraps rows for mean/rank uncertainty. Numerical ties
and interval overlap are not equivalence. See [N-way policy ranking](n_way_ranking.md).

For one positive practical-equivalence claim, `STA-03` reuses the exact STA-01 pairing cohort and
requires a predeclared symmetric absolute original-unit margin, basis, justification, and alpha.
Paired-mean TOST demonstrates equivalence only when both one-sided nulls reject; ordinary
difference-test non-significance is irrelevant to that decision. See
[paired equivalence testing](equivalence_testing.md).

For deterministic CI, `STA-04` compares a completed metric collection or STA-01 artifact with an
approved versioned golden contract. It first enforces typed context and exact/compatible source
policy, then checks only declared finite scalars against the inclusive maximum of absolute and
relative tolerance. Missing or incompatible evidence is unavailable; a complete out-of-tolerance
scalar fails. Regression pass is not statistical equivalence. See
[versioned regression gates](regression_gates.md).

For prospective sample-size planning, `STA-05` takes a researcher-declared target paired effect,
prospective paired-difference variance, two-sided alpha, and target power. It returns the smallest
bounded common-seed count meeting the versioned normal-approximation rule and records power at the
preceding count. It does not inspect completed results, calculate retrospective power, or claim
exact power for STA-01 sign flips. See [paired common-seed power analysis](power_analysis.md).

For source-row audit, `PRO-01` reuses this ordinary pairwise compatibility and absolute delta. A
closed direct count/sum/mean/rate registry decomposes each run independently, signs baseline terms
negative and variation terms positive, and requires their sum to reconcile to the ordinary delta.
Compatible percentiles and other non-decomposable scalar metrics expose both complete eligible-row
ledgers with null weights. This is arithmetic lineage, not a statistical test, effect attribution,
or causal claim. See [difference provenance](difference_provenance.md).

## TOS Source-Summary Comparison

TOS evaluation rows can use the same scalar delta service when experiment grouping, fleet seed,
metric version, and unit are compatible. These comparisons use the distinct collection version
`tos-source-summary-v2_post_nrsus_fix-1.0`. Source deadline success is compared only under
`tos.task.deadline_success.rate`; it is not compared as TrafficTwin physical completion. Structured
class mappings and unavailable canonical metrics remain unavailable comparisons.

## Related Documents

- [Metrics catalogue](metrics_catalogue.md)
- [EvidencePack specification](evidence_pack_spec.md)
- [User guide](user_guide.md)
- [Reproducibility guide](reproducibility.md)
- [TOS Data read-only integration](integration/tos_data_adapter.md)
- [Common-seed paired statistical studies](statistical_studies.md)
- [N-way common-seed policy ranking](n_way_ranking.md)
- [Paired equivalence testing](equivalence_testing.md)
- [Versioned regression gates](regression_gates.md)
- [Paired common-seed power analysis](power_analysis.md)
- [Accepted-row difference provenance](difference_provenance.md)

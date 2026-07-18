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

No formal hypothesis tests or confidence intervals are implemented in Phase 3.

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

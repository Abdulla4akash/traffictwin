# Difference Provenance

`PRO-01` traces one compatible baseline/variation metric comparison to both complete accepted-row
eligibility ledgers. It answers two distinct questions without merging them:

1. Which accepted canonical rows were eligible on each comparison side?
2. For a directly decomposable metric, what signed arithmetic term did each eligible row contribute
   to `variation - baseline`?

It does not answer why the real-world outcome changed or which entity caused it.

## Status and Boundary

Version 1.0 is implemented for validated generic imported and explicitly synthetic run bundles.
It consumes the ordinary completed `MetricCollection` for each bundle and never changes raw files,
canonical records, metrics, registry data, or comparison configuration. Direct launch is unrelated
and remains unavailable.

The source pair must satisfy the ordinary comparison contract: same required experiment and random
seed, compatible metric version and unit, available finite scalar values, and equal applicable
energy/fairness/plugin semantic fingerprints. An invalid pair returns `unavailable`; it is not
silently coerced, regrouped, or treated as a zero difference.

Current SUMO and TOS adapter capability manifests report difference provenance as unsupported.
Those adapters have separate source boundaries and are not relabelled as generic accepted-row
bundles.

## Output Modes

`DifferenceContributionReport.status` has three values:

| Status | Meaning |
|---|---|
| `arithmetic` | The metric has an admitted row formula. Signed row terms reconcile to the ordinary absolute delta. |
| `lineage_only` | The scalar comparison is compatible, but no additive row formula is admitted. Eligible rows are shown and all contribution fields are `null`. |
| `unavailable` | The ordinary comparison or required ledger is unavailable/incompatible. Candidate audit rows may remain visible, but no difference term is asserted. |

Arithmetic version 1.0 admits direct scalar:

- task counts, completion/incomplete/deadline-miss rates, decision shares, offload rate, latency
  count/mean, and contract-admitted energy means;
- infrastructure queue and utilisation means;
- traffic observation count, count total/mean, and speed mean;
- trip record/completed/incomplete/duration counts, completion rate, and duration mean.

The exact closed list and formula text are published in the
[generated contract](reference/generated/difference_provenance_contract.json). Percentiles,
minimum/maximum extrema, distinct counts, state-machine episode metrics, grouped mappings,
fairness/spatial aggregates, and plugin metrics without an admitted decomposition are lineage-only
when their ordinary scalar comparison is available. Mapping-valued outputs remain unavailable
rather than being flattened implicitly.

## Arithmetic Interpretation

Each run is decomposed independently using its own eligible denominator. Baseline row terms receive
a negative sign and variation row terms receive a positive sign:

```text
signed contribution sum
  = sum(variation run terms) - sum(baseline run terms)
  = variation metric value - baseline metric value
```

For example, a mean-latency row term is its eligible `latency_ms` divided by that run's eligible
latency-row count. A completion-rate row term is its completed indicator divided by that run's
accepted task count. Different denominators therefore remain explicit and correct; rows are not
matched across runs by task or vehicle ID.

Every arithmetic report records the reconstructed sum and `reconciles_to_absolute_delta=true`.
TrafficTwin refuses construction if the formula and ordinary delta disagree beyond the published
`1e-12` tolerances. An excluded row has `null` contribution fields, preserving the difference
between exclusion and an admitted numerical zero.

## CLI Usage

Inspect the method boundary:

```bash
traffictwin provenance difference-contract --format text
traffictwin provenance difference-contract --format json
```

Export an additive completion-rate difference:

```bash
traffictwin provenance difference-contributors \
  tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid \
  task.completion.rate \
  --format json \
  --output completion-difference-provenance.json
```

Export percentile lineage without weights:

```bash
traffictwin provenance difference-contributors \
  tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid \
  task.latency.p95_ms \
  --format csv \
  --output p95-difference-lineage.csv
```

JSON preserves the complete nested typed artifact. CSV repeats comparison identity, status,
values, row source, eligibility, optional arithmetic fields, canonical JSON, and the mandatory
non-causality statement on every row.

## Streamlit Usage

1. Open **What-if Compare**.
2. Choose existing baseline and variation bundle paths.
3. Review the ordinary compatibility findings and metric comparisons.
4. Under **Difference provenance**, select any compatible scalar metric.
5. Check whether the result is `arithmetic` or `lineage_only`.
6. Inspect both run-side ledgers and download JSON or CSV.

The page performs no decomposition. It calls `difference_contributions_for_ui`, which delegates to
the same deterministic library service as the CLI.

## Python Usage

```python
from traffictwin.ingestion.bundle import validate_bundle
from traffictwin.metrics.engine import compute_metrics_for_bundle
from traffictwin.provenance.differences import build_difference_contribution_report

baseline = validate_bundle("tests/fixtures/bundles/baseline_valid")
variation = validate_bundle("tests/fixtures/bundles/variation_valid")

report = build_difference_contribution_report(
    baseline,
    compute_metrics_for_bundle(baseline),
    variation,
    compute_metrics_for_bundle(variation),
    "task.latency.mean_ms",
)

assert report.reconciles_to_absolute_delta is True
print(report.absolute_delta)
print(report.rows[0].signed_difference_contribution)
```

Use `get_difference_contributions` with two `ProvenanceContext` objects when the ordinary query
service boundary is preferred.

## Reading the Artifact

Important fields are:

- `baseline` and `variation`: run ID, immutable input fingerprint, synthetic label, and row counts;
- `baseline_value`, `variation_value`, `absolute_delta`: the ordinary comparison values;
- `decomposition_method`: present only for an admitted arithmetic formula;
- `rows[].included` and `inclusion_reason`: the ordinary metric eligibility decision;
- `rows[].run_metric_contribution`: the row term in its own run aggregate;
- `rows[].signed_difference_contribution`: the term after applying the comparison-side sign;
- `arithmetic_contribution_sum` and `reconciles_to_absolute_delta`: the integrity check;
- `comparison_reason_codes` and `compatibility_findings`: retained unavailable/incompatibility audit;
- `non_causality_statement`: mandatory integrity language in JSON and CSV;
- `fingerprint()`: deterministic hash of the complete typed report.

Rows rejected during source validation never became canonical records. Find them in the normal
`ValidationReport`; do not interpret their absence from this accepted-row ledger as an admitted
zero.

## Research Use Cases

- audit why a reported arithmetic delta has the exact value shown;
- verify denominator changes between baseline and variation means or rates;
- trace a percentile change to both eligible input populations without claiming row weights;
- attach machine-readable source-row lineage to a dissertation table or supervisor review;
- regression-test exact decompositions with golden projections;
- distinguish incompatibility or absent evidence from a true zero delta.

Difference provenance is calculation transparency, not causal inference, feature importance,
counterfactual attribution, statistical significance, or external validation. A reconciled sum
does not prove that the changed policy caused the observed outcome.

## Related Documents

- [ADR-033](decisions/ADR-033-accepted-row-difference-provenance.md)
- [Provenance model](provenance_model.md)
- [Provenance Explorer](provenance_explorer.md)
- [Comparison methodology](comparison_methodology.md)
- [Reproducibility](reproducibility.md)
- [Limitations and future work](limitations_and_future_work.md)

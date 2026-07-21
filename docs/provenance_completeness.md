# Provenance Completeness

TrafficTwin `PRO-03` answers a deliberately narrow question: **what fraction of the typed computed
claims in this report has complete accepted-canonical-row lineage?** It does not score truth,
causality, scientific value, writing quality, or raw-input acceptance.

## Supported reports

The version 1.0 method supports four report templates:

| Report type | Denominator |
|---|---|
| `run` | selected run-report metric results plus every diagnostic rule result |
| `diagnostics` | the same selected metric results plus every diagnostic rule result, under diagnostic-report sections |
| `comparison` | every selected typed metric comparison, including unavailable comparisons |
| `full` | run claims plus optional comparison claims, rebased to unique full-report claim IDs |

The report builder and scorer share the same typed claim-key functions. Rendered prose is never
parsed. External reports without `ReportClaimReference` entries are unsupported.

## Denominator and exclusions

Every explicit metric, rule, or comparison reference in the selected template enters the
denominator. `unavailable` is a classification, not a reason to remove the claim. This prevents a
report with missing evidence from appearing more complete by omission.

The artifact publishes all excluded categories and reasons. Version 1.0 excludes presentation and
narrative, identity/reproduction metadata, validation/evidence-inventory metadata, and comparison
context. These remain auditable elsewhere; they are not silently ignored result claims.

## Classifications

| Classification | Exact meaning | Score contribution |
|---|---|---:|
| `source_row_complete` | available result with a non-empty, reconciled complete accepted-row ledger and valid source locators; rules also require complete cited dependencies and no missing evidence; comparisons require complete ledgers on both sides | 1 |
| `aggregate_only` | a typed result exists, but complete source-row admission is not established | 0 |
| `unavailable` | unavailable/invalid metric or comparison, or invalid/insufficient rule | 0 |

There is no partial credit or claim weighting. The primary score is
`source_row_complete_count / denominator_count`. The separate
`aggregate_or_better_fraction` reports the share that at least has a typed aggregate result.

If there are no claims, both fractions are null and status is `no_claims`. Null must not be
displayed as zero or 100%.

## Trace depth versus completeness

Depth follows directed provenance edges outward from a claim root and selects the deepest
available reachable type:

1. `source_row`
2. `source_file`
3. `canonical_record`
4. `canonical_table`
5. `aggregate`
6. `unavailable`

A trace can show `source_row` depth while the claim remains `aggregate_only`. Depth can be
established from a retained/sample row, whereas `source_row_complete` also requires the separate
complete accepted-row ledger to reconcile over the whole candidate population.

## CLI use

Publish the immutable method contract:

```bash
traffictwin provenance completeness-contract --format json
```

Score a run or diagnostic report:

```bash
traffictwin provenance completeness tests/fixtures/bundles/baseline_valid \
  --report-type run --format json --output run-completeness.json

traffictwin provenance completeness tests/fixtures/bundles/baseline_valid \
  --report-type diagnostics --format csv --output diagnostic-completeness.csv
```

Score a full report that includes a comparison section:

```bash
traffictwin provenance completeness tests/fixtures/bundles/variation_valid \
  --report-type full \
  --comparison-baseline tests/fixtures/bundles/baseline_valid \
  --format json --output full-completeness.json
```

Score the comparison template directly:

```bash
traffictwin provenance comparison-completeness \
  tests/fixtures/bundles/baseline_valid \
  tests/fixtures/bundles/variation_valid \
  --format csv --output comparison-completeness.csv
```

JSON contains the contract, counts, score, every claim assessment, exclusions, rules, reasons, and
limitations. CSV has one row per denominator claim; it never drops unavailable rows. Text is a
compact count summary.

## Streamlit use

In **Provenance Explorer**, expand **Report claim provenance completeness (PRO-03)**, choose `run`
or `diagnostics`, inspect the five summary values and full static claim table, and download JSON or
CSV. The static table avoids hiding rows behind interactive grid state.

In **Comparison**, choose baseline and variation bundles, then inspect **Comparison provenance
completeness** below difference provenance. The table and downloads represent all selected
comparison-template claims, including unavailable ones.

## Python use

```python
from traffictwin.provenance.query import (
    build_provenance_context,
    get_comparison_provenance_completeness,
    get_report_provenance_completeness,
)

baseline = build_provenance_context("tests/fixtures/bundles/baseline_valid")
variation = build_provenance_context("tests/fixtures/bundles/variation_valid")

run_score = get_report_provenance_completeness(baseline, "run")
comparison_score = get_comparison_provenance_completeness(baseline, variation)
```

Use `provenance_completeness_report_to_csv(report)` for the complete CSV inventory and
`provenance_completeness_contract()` to embed or validate the published method boundary.

## How to interpret a result

Read the denominator and class counts before the percentage. Then inspect unavailable and
aggregate-only reason codes. A lower score can be the honest result of a richer report template
that keeps unsupported metrics visible. A higher score says only that a greater fraction of that
specific typed denominator has complete accepted-row lineage.

`source_row_complete` covers accepted canonical candidates. Rows rejected during validation are
preserved in validation findings and raw inputs but are not candidates for a metric that never
admitted them. Review the validation report alongside this artifact when raw-ingestion coverage
matters.

Do not compare scores from different report templates without showing both denominators. Do not
interpret an equal-weight score as a weighted scientific-quality index. Do not use it to claim a
result is correct or causal.

## Reproducibility and sharing

The report fingerprint normalises the generation timestamp. Claim fingerprints use stable
evidence fields rather than volatile trace IDs. Identical accepted evidence, report template, and
method contract therefore yield the same fingerprints.

The completeness JSON/CSV includes source-relative filenames, artifact IDs, statuses, and reason
codes. It should be reviewed before external sharing. It does not include raw row values, but it is
not an anonymisation artifact.

## Boundaries

- The generic/import-first report pipeline supports PRO-03.
- Current SUMO and TOS adapter manifests report the capability as false.
- No LLM calculates or changes the inventory, classification, score, or reasons.
- The score does not replace PRO-01 difference lineage or PRO-02 graph inspection.
- It does not measure rejected-row coverage, causal identification, accuracy, calibration,
  fairness, energy validity, or simulator fidelity.

See [ADR-035](decisions/ADR-035-explicit-report-claim-provenance-completeness.md), the
[provenance model](provenance_model.md), [difference provenance](difference_provenance.md), and
[provenance graph exports](provenance_graph_exports.md).

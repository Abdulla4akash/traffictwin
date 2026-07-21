# ADR-033 — Accepted-Row Difference Provenance

Status: accepted and implemented
Date: 20 July 2026
Capability: `PRO-01`

## Context

TrafficTwin already reconstructs a complete accepted-canonical-row eligibility ledger for one run
metric. The v0.5 design requires compatible baseline/variation comparisons to expose their input
lineage and, only where mathematically defined, each row's arithmetic term in the ordinary
variation-minus-baseline difference. Percentiles and other non-additive aggregates must not receive
invented weights, and no contributor report may be presented as causal attribution.

The existing `MetricContributionReport` deliberately means eligibility, not a numeric
decomposition. Changing that artifact would make older ledgers appear more informative than they
are. Compatibility and absolute delta are already defined by the ordinary metric comparison
service, so a second comparison policy would also risk contradictory answers.

## Decision

TrafficTwin adds a separate `DifferenceContributionReport` version 1.0. The builder consumes two
validated generic run bundles and their already-computed `MetricCollection` artifacts. It delegates
experiment, random-seed, metric-version, unit, metric-status, scalar-value, energy, fairness, and
plugin compatibility to `compare_metric_collections`. An incompatible or unavailable ordinary
comparison produces a typed `unavailable` difference report; absent evidence is never zero.

Both complete `MetricContributionReport` ledgers are retained in comparison-side order. Every row
records its run, source file and row, canonical values, ordinary inclusion state, and inclusion
reason. Rows rejected before canonicalisation remain in the corresponding `ValidationReport`.

Version 1.0 has a closed arithmetic registry for direct scalar counts, sums, means, and rates whose
ordinary run value can be reconstructed as a sum of accepted-row terms. It includes direct task,
infrastructure, traffic, trip, and contract-admitted energy formulas published by
`difference_provenance_contract`. A row's run term is calculated with that run's own eligible
denominator. The signed difference term is:

```text
baseline row:  - run_metric_contribution
variation row: + run_metric_contribution
sum of signed rows = variation metric - baseline metric
```

The service checks the final sum against the ordinary absolute delta with relative and absolute
tolerances of `1e-12`. A failure raises a construction error rather than exporting an inaccurate
decomposition. Excluded rows retain `None`, not a fabricated weight.

Percentiles, extrema, distinct counts, saturation episodes/durations, grouped or mapping-valued
metrics, fairness/spatial aggregates, and trusted plugin outputs without a separately admitted
formula are not in the arithmetic registry. When the ordinary comparison has a compatible scalar
delta, their report status is `lineage_only`: both complete eligibility ledgers are exposed and all
numeric row contribution fields are `None`. Mapping-valued metrics remain unavailable because the
ordinary comparison has no implicit scalar flattening rule.

Every JSON report and every CSV row carries this mandatory statement:

> This report records deterministic arithmetic and eligible input lineage only; it does not
> establish that any row, vehicle, RSU, or incident caused the observed difference.

Reports also retain source fingerprints, synthetic labels, per-side candidate/included/excluded
counts, comparison findings, reason codes, grouping metadata, limitations, and a deterministic
fingerprint. The CLI, UI, and demo only render the typed artifact.

## Consequences

- Exact additive differences can be audited to individual accepted source rows without pairing
  unrelated row identifiers across runs.
- Different run denominators are represented correctly because each row contributes to its own
  run aggregate before the baseline sign is applied.
- Percentiles and other non-additive aggregates still have complete eligible lineage without
  misleading Shapley-like, interpolation, rank, or causal weights.
- The original single-run ledger keeps its eligibility-only meaning.
- Generic imported/synthetic bundles advertise the capability. Current SUMO and TOS adapter
  manifests remain false because they do not use this two-bundle accepted-row boundary.
- Adding a metric to the arithmetic registry is a versioned scientific-contract change requiring
  a proven row formula and reconciliation tests.

## Rejected Alternatives

- **Subtract rows with matching IDs:** IDs need not correspond across policy runs, and matching
  would invent a paired-row semantic absent from the metric definition.
- **Assign equal percentile weights:** linear percentile interpolation depends on order statistics;
  equal weights do not reproduce the percentile.
- **Attribute the whole difference to rows near a percentile rank or maximum:** this is a choice of
  influence narrative, not the implemented aggregate arithmetic.
- **Flatten grouped mappings automatically:** group alignment, missing-group behavior, and a scalar
  objective are not declared by the ordinary comparison contract.
- **Treat excluded rows as numerical zero contributors:** `None` preserves the distinction between
  not admitted and an admitted zero-valued term.
- **Infer plugin decompositions from input rows:** a trusted plugin may combine rows arbitrarily;
  its input ledger alone does not establish additivity.
- **Use causal language because arithmetic reconciles:** arithmetic lineage identifies calculation
  terms, not intervention effects or causes.

## Acceptance Evidence

- Unit tests cover every comparable admitted formula, reconciliation, denominator changes,
  percentile lineage-only behavior, incompatibility, deterministic fingerprints, and mandatory
  JSON/CSV warnings.
- A golden projection pins the exact mean-latency decomposition, including an excluded variation
  row.
- CLI integration tests cover the public contract plus arithmetic JSON and lineage-only CSV.
- UI service tests prove that the comparison page delegates to the typed library artifact.
- The synthetic demo workspace exports reviewable JSON and CSV difference provenance.
- Capability manifests, generated Pydantic schemas, generated CLI help, generated contract,
  architecture, usage, integrity limitations, status, and traceability records are reconciled.

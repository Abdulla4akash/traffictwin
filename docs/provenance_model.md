# TrafficTwin Provenance Model

## Implementation Gap Note

Phase 1-5 artifacts already preserve strong run-level and row-level provenance for imported tabular
bundles: manifests identify the run, seed, experiment, environment, declared files, and bundle
fingerprint; canonical records retain `source_file` and `source_row`; metric results retain run
context; EvidencePacks retain validation summaries and metric collections; DiagnosticReports cite
stable evidence keys.

Metric results do not materialise per-row contribution lists. The normal trace remains compact:
required canonical tables, fields, eligible counts, bounded source-row samples, and validation
findings. When a complete ledger is requested, `MetricContributionReport` reconstructs every
accepted candidate row from the validated bundle and records deterministic eligibility. Neither
view assigns fabricated contribution weights to individual rows.

Custom metric results embed their validated `PluginMetricContract`. Provenance reconstructs the
metric definition from that immutable result metadata, so a later trace does not depend on the
original in-memory registry. Its contribution ledger uses the contract's declared canonical input
tables/fields and execution-admission metadata. An included row means it was supplied to the
bounded plugin input, not that it had an additive or causal effect on the output.

## Model Boundary

Provenance in TrafficTwin means traceability through the deterministic software pipeline. It shows
how a displayed result was derived from available records, metric definitions, rule configuration,
and bundle metadata. It does not prove real-world causality or external validity.

## Trace Objects

`ProvenanceTrace` is a versioned directed acyclic trace containing:

- `ProvenanceNode`: typed pipeline object, such as a metric result, metric definition, canonical
  table, source row, validation finding, run, seed, environment, or diagnostic rule result.
- `ProvenanceEdge`: typed relation between two nodes, such as `computed_from`, `defined_by`,
  `canonicalised_from`, `validated_by`, or `unavailable_because`.
- `TraceCompletenessSummary`: categorical completeness for run metadata, seed, experiment, bundle,
  validation, canonical records, metrics, diagnostics, and source rows.

The construction graph remains internal and requires no external graph database. PRO-02 can
project an existing trace into a bounded `ProvenanceGraphView` and serialize it as DOT or GraphML;
deterministic generation still requires no Graphviz runtime.

## Bounded Graph Projection

`ProvenanceGraphView` retains the root and a deterministic breadth-first neighbourhood up to
declared node/edge limits. It reports exact omissions, preserves retained relation direction, and
uses one complete-sanitised-graph identity plus an exact bounded-view fingerprint. Volatile trace
and node timestamps are excluded.

Safe exports redact machine-local paths recursively. Structure-only exports additionally remove
descriptions, attributes, and source references. Safe mode is not anonymisation: ordinary domain
identifiers and scalar values may remain. DOT and GraphML are deterministic content artifacts;
renderer layout is presentation only. See [Provenance graph exports](provenance_graph_exports.md)
and ADR-034.

## Report-Claim Completeness

`ResearchReport` carries typed `ReportClaimReference` entries beside the rendered sections.
PRO-03 classifies that exact inventory without parsing prose. Every unavailable reference remains
in the denominator, while named presentation/metadata/validation/context exclusions are published
separately.

`ProvenanceCompletenessReport` separates directed trace depth from complete population coverage.
A source-row-reachable trace establishes depth; `source_row_complete` additionally requires a
non-empty reconciled ledger covering every accepted canonical candidate. Rule claims require all
cited metric dependencies complete and no missing evidence. Comparison claims require complete
ledgers on both sides. Aggregate-only and unavailable claims contribute zero to the equal-weight
score, and an empty denominator produces null. See [Provenance completeness](provenance_completeness.md)
and ADR-035.

## Source Rows

Generic source-row previews are read-only for declared CSV, gzip-CSV, and Parquet files. The
explorer opens directory and ZIP bundles through the existing safe loader, validates bundle-relative
paths, applies the same decoded-table safety bound as ingestion, returns only the requested row
window, and avoids rendering untrusted HTML.

If a source bundle is unavailable or the requested source path escapes the bundle, the preview
returns a structured unavailable result.

## Aggregate Metrics

For aggregate metrics such as `task.completion.rate` or `infra.utilisation.p95`, the trace uses the
term "eligible input" rather than "cause." The source-row list is a bounded sample with exact
eligible-record counts, not a complete causal explanation.

The eligibility-ledger query is complete for accepted canonical candidates and exports JSON or
CSV. It reports source file/row and full canonical values. Rows rejected before
canonicalisation remain in `ValidationReport`; percentile/group membership still does not imply
individual causal effect.

## Comparison Difference Lineage

`DifferenceContributionReport` extends—not changes—the single-run eligibility ledger. It consumes
two ordinary accepted bundle/metric contexts and delegates compatibility plus the absolute delta to
the existing comparison service. Both complete row ledgers remain visible with run side, source
location, eligibility, canonical values, source fingerprint, and synthetic state.

For the closed ADR-033 registry of direct scalar counts, sums, means, and rates, each eligible row
has a run-aggregate term and signed variation-minus-baseline term. Baseline terms are negative;
variation terms are positive. The report is created only after the signed sum reconciles with the
ordinary comparison delta. This arithmetic does not require or imply matching baseline and
variation record identifiers.

Compatible percentiles, extrema, distinct counts, episode metrics, fairness/spatial aggregates,
and plugins without admitted formulas expose `lineage_only`: the complete eligible populations are
retained while every row weight is `null`. Mapping-valued differences remain unavailable rather
than being flattened. JSON and CSV carry the same mandatory statement that arithmetic and eligible
lineage do not establish that any row or entity caused the difference.

For a `WindowedMetricSeries`, `build_window_metric_trace` first filters every canonical table with
the selected slice's effective half-open bounds and versioned anchor policy, then invokes the same
ordinary metric-lineage builder. `WindowMetricContributionReport` wraps the window contract around
the complete accepted-row eligibility ledger. An excluded partial window has no metric collection
and therefore no fabricated trace or ledger.

Typed temporal evidence adds a stable fingerprint of the complete window series and a fingerprint
of the one-metric projection. R6 metadata cites exact baseline, episode, missing-observation, and
recovery ordinals. The existing window trace and contribution-ledger commands resolve any cited
ordinal to its filtered canonical records and accepted source rows; the diagnostic result does not
invent per-row weights or causal contributors.

Declarative rule-result nodes retain `result_metadata`, including the complete definition
fingerprint, grammar/schema versions, predicate completeness, and—on R7—the selected dimension,
threshold, and support requirement. Finding evidence keys follow the ordinary metric-to-canonical-
row/source-row path. This records lineage and configuration, not scientific validity or cause.

R8 rule-result nodes retain the exact energy-contract fingerprint/family metadata, configured
energy and support thresholds, admitted counts and coverage, and both cited evidence keys. The
completed-task energy metric and completed-task count can share one canonical task-table node while
preserving their separate metric-definition and source-row paths. The trace does not assign causal
energy contribution or claim that a high mean is a statistical anomaly.

`NearestFlipAnalysis` embeds rather than invents its calculation lineage: the EvidencePack and
source-bundle fingerprints, cited evidence keys, exact source/candidate rule configurations,
normalised current/candidate RuleResult fingerprints, discrete constraints, and verified statuses.
It does not assign row-level sensitivity weights. The existing rule/metric trace can be requested
separately from the cited source result when a bundle is available.

`ThresholdSensitivityReport` retains that EvidencePack/source identity plus the complete declared
grid, every point's exact selected-rule config and normalised result fingerprint, the source-result
fingerprint, status-sequence fingerprint, stability, sampled intervals, and embedded DIA-05
artifact/fingerprint. This is calculation lineage for sensitivity, not row-level influence,
calibration evidence, or cause.

`CrossRuleReasoningReport` records downstream rule-result lineage without recalculating evidence:
the source evidence fingerprint, policy-contract fingerprint, ordered result-sequence fingerprint,
every timestamp-normalised original result fingerprint, and each relationship's exact shared,
source-only, and target-only cited keys. Suppression retains the target fingerprint and status.
This proves which deterministic policy connected which immutable outputs; it does not establish
causal, statistical, or independent evidential support.

STA-01 adds an artifact-level paired lineage audit without claiming arithmetic row causality. Each
eligible observation retains baseline/variation run IDs, values, random seed, immutable input
fingerprints, and timestamp-normalised `MetricCollection` fingerprints. The study also retains the
exact analysis-plan, compatibility-signature, source-sequence, method-contract, and final artifact
fingerprints plus every excluded input. It does not invent row weights for non-decomposable metrics
or imply that the observed difference was caused by the variation.

## Related Documents

- [Provenance Explorer](provenance_explorer.md)
- [Evidence Pack Specification](evidence_pack_spec.md)
- [Diagnostic Report Specification](diagnostic_report_spec.md)
- [Nearest-flip analysis](nearest_flip_analysis.md)
- [Threshold-sensitivity explorer](threshold_sensitivity_explorer.md)
- [Deterministic cross-rule reasoning](cross_rule_reasoning.md)
- [Difference provenance](difference_provenance.md)
- [Provenance graph exports](provenance_graph_exports.md)
- [Provenance completeness](provenance_completeness.md)
- [Architecture](architecture.md)

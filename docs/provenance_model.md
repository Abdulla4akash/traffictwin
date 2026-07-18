# TrafficTwin Provenance Model

## Implementation Gap Note

Phase 1-5 artifacts already preserve strong run-level and row-level provenance for imported CSV
bundles: manifests identify the run, seed, experiment, environment, declared files, and bundle
fingerprint; canonical records retain `source_file` and `source_row`; metric results retain run
context; EvidencePacks retain validation summaries and metric collections; DiagnosticReports cite
stable evidence keys.

The current metric results do not store a materialised per-row contribution list for every
aggregate metric. The Provenance Explorer therefore reports aggregate-level provenance honestly:
required canonical tables, required fields, eligible record counts, included source-row samples, and
validation findings affecting those rows. It does not assign fabricated contribution weights to
individual rows.

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

The graph is intentionally internal and small. No external graph database or visualisation runtime
is required.

## Source Rows

CSV source-row previews are read-only. The explorer opens directory and ZIP bundles through the
existing Phase 2 safe loader, validates bundle-relative paths, reads only the requested row window,
and avoids rendering untrusted HTML.

If a source bundle is unavailable or the requested source path escapes the bundle, the preview
returns a structured unavailable result.

## Aggregate Metrics

For aggregate metrics such as `task.completion.rate` or `infra.utilisation.p95`, the trace uses the
term "eligible input" rather than "cause." The source-row list is a bounded sample with exact
eligible-record counts, not a complete causal explanation.

## Related Documents

- [Provenance Explorer](provenance_explorer.md)
- [Evidence Pack Specification](evidence_pack_spec.md)
- [Diagnostic Report Specification](diagnostic_report_spec.md)
- [Architecture](architecture.md)

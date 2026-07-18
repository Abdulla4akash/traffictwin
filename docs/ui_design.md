# UI Design

The current UI is a thin Streamlit layer over the tested TrafficTwin library.

## Principles

- Validation, metrics, comparison, evidence packs, diagnostics, and provenance traces are computed by library services.
- Streamlit pages render state and call UI service functions.
- Unsupported and unknown capabilities are disabled.
- Direct launch is visibly unavailable for the generic CSV adapter.
- Every analysis view labels data as synthetic, imported, or historical replay.

## Pages

- Home: registry counts, workspace status, quick actions, recent reports, capability manifest, and
  limitations.
- Scenario Builder: synthetic generator configuration, validation, YAML preview, bundle generation,
  and normal bundle validation.
- Bundle Import & Validation: manifest, files, validation findings, evidence availability, import.
- Experiment Manager: experiments, runs, seeds, policies, fingerprints, comparisons, reports, metric
  storage, and evidence storage.
- Replay: historical replay clock, deterministic controls, filters, and time-series views.
- Run Overview: KPI cards, task charts, metric availability, provenance.
- Infrastructure & Congestion: RSU queue/utilisation, saturation config, load balance availability.
- Comparison: compatibility, seed diff, metric deltas by domain.
- Journey-Time Lens: imported trip duration metrics and comparison.
- Diagnostics & Evidence: validation/evidence state, rule results, alternatives, missing evidence,
  conditional recommendations, and report download.
- Provenance Explorer: read-only metric, diagnostic-rule, source-row, and run-context traces with JSON and Markdown export.
- Reports: existing report inventory, downloads, and explicit report regeneration.
- Search: local metadata search over runs, experiments, reports, metrics, rules, and source files.
- Settings: session-scoped UI preferences.
- About: version, schema, generator, diagnostic, provenance, build, and licence metadata.

## Shared Components

The UI uses reusable helpers for:

- `StatusBadge`, `ScenarioBadge`, `EvidenceBadge`, and related compact labels;
- `MetricCard`;
- `ReportCard`;
- `SectionHeader`;
- metadata tables;
- unavailable-data panels.

Pages should call service functions and shared components rather than duplicating formulas, report
builders, validation logic, or diagnostic interpretation.

## Visual Policy

The UI uses neutral Plotly time-series and bar charts. It does not use colours to imply improvement, harm, or causal judgement. It does not render maps when coordinates are absent.

## Data Modes

Operational modes in Phase 4:

- `SYNTHETIC`
- `IMPORTED`
- `HISTORICAL REPLAY`

`NEAR-LIVE` and `TRUE LIVE` may appear only as unsupported future capability labels.

## Diagnostic Presentation

The diagnostic page uses cautious language:

- “candidate hypothesis”
- “may indicate”
- “is consistent with”
- “requires verification”

It avoids causal-proof language that would turn a candidate hypothesis into a settled conclusion. Recommendations are displayed as conditional follow-up checks, not automatic actions.

## Provenance Presentation

The Provenance Explorer uses a readable vertical lineage and grouped node tables rather than a
force-directed graph. It distinguishes:

- observed source evidence;
- canonical records;
- metric results and definitions;
- rule findings;
- candidate hypotheses;
- missing or unavailable links.

Aggregate metrics show eligible input rows and bounded samples. The UI must not imply that an
individual row caused an aggregate result.

## Standalone Demo Presentation

When launched through `traffictwin demo launch`, Home shows a `Standalone Demo` section with
workspace status, scenario count, imported runs, and diagnostic preparation status. This is a status
badge and selector aid only; the normal import-first pages remain the same.

The UI must continue to label all generated data as synthetic and must not enable direct launch,
Randy/SUMO integration, near-live data, or true-live data from the standalone workspace.

## Product Polish

The Product Polish phase adds research workflow pages and consistent navigation without changing the
scientific pipeline. See [Product polish and research UX](product_polish.md).

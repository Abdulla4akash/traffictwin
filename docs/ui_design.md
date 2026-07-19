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
- Guided Demo: mobile-visible, stage-based navigation through either the standalone synthetic
  pipeline or the read-only imported TOS evidence workflow.
- Experiment Planner: registered-seed selection, common-random-seed design, bounded run-matrix
  preview, seed diff, planned-experiment registration, exhaustive protocol YAML/CSV, and read-only
  completed-bundle matching without run creation.
- Scenario Builder: synthetic generator configuration, validation, YAML preview, bundle generation,
  and normal bundle validation.
- Bundle Import & Validation: manifest, files, validation findings, evidence availability, import.
- TOS Data Import: read-only external result inventory, NPZ contract validation, source-summary
  registry import, source-contract inspection, and aggregate provenance.
- TOS Results: source evaluation matrix, exact fleet-seed paired deltas, and explicit
  in-domain/held-out/unknown labels.
- TOS Mobility & RSU Replay: logical source playback, deliberate processed-FCD spatial snapshots,
  bounded task views, and RSU pressure/backlog. Pressure remains separate from canonical
  utilisation/queue metrics.
- TOS Training & Audit: bounded training curves, greedy summaries, reproducibility checks,
  machine-readable integration gates, and deliberate private supervisor/report/atlas downloads.
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

Guided Demo is a workflow catalogue and navigation surface. Its stage definitions are
framework-independent, but every analysis action opens an existing page backed by the established
services. The guide itself performs no scientific computation.

Experiment Planner delegates design validation to `traffictwin.experiments.planning` and registry
operations to `ui.services`. `traffictwin.experiments.protocol` supplies every slot, fingerprint,
export, and match result. The page does not generate synthetic records, compute metrics, create
`Run` objects, import matched bundles, or expose a launch control.

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
full Randy/SUMO integration, near-live data, or true-live data from the standalone workspace. The
optional TOS page labels its content `IMPORTED SIMULATION` and `HISTORICAL REPLAY`.

Home exposes primary actions in the page body because Streamlit collapses its sidebar on narrow
viewports. Guided Demo uses short stage controls and stable dimensions so the workflow remains
usable on phone-sized screens.

## Product Polish

The Product Polish phase adds research workflow pages and consistent navigation without changing the
scientific pipeline. See [Product polish and research UX](product_polish.md).

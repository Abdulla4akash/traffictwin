# UI Design

The current UI is a thin Streamlit layer over the tested TrafficTwin library.

## Principles

- Validation, metrics, comparison, evidence packs, diagnostics, and provenance traces are computed by library services.
- Streamlit pages render state and call UI service functions.
- Unsupported and unknown capabilities are disabled.
- Direct launch is visibly unavailable for the generic CSV adapter.
- Every analysis view labels data as synthetic, imported, or historical replay.

## Pages

- Home / Project Status: registry counts, capability manifest, limitations.
- Scenario Studio: seed draft, validation, YAML preview, export, optional registry save.
- Bundle Import & Validation: manifest, files, validation findings, evidence availability, import.
- Operations View: historical replay clock and time-series views.
- Run Overview: KPI cards, task charts, metric availability, provenance.
- Infrastructure & Congestion: RSU queue/utilisation, saturation config, load balance availability.
- What-if Compare: compatibility, seed diff, metric deltas by domain.
- Journey-Time Lens: imported trip duration metrics and comparison.
- Evidence & Diagnostic Hypotheses: validation/evidence state, rule results, alternatives, missing evidence, conditional recommendations, and report download.
- Provenance Explorer: read-only metric, diagnostic-rule, source-row, and run-context traces with JSON and Markdown export.

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

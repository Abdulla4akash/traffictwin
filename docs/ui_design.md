# UI Design

The Phase 4 UI is a thin Streamlit layer over the tested TrafficTwin library.

## Principles

- Validation, metrics, comparison, and evidence packs are computed by library services.
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
- Evidence & Diagnostic Readiness: validation/evidence state and evidence-pack download.

## Visual Policy

The UI uses neutral Plotly time-series and bar charts. It does not use colours to imply improvement, harm, or causal judgement. It does not render maps when coordinates are absent.

## Data Modes

Operational modes in Phase 4:

- `SYNTHETIC`
- `IMPORTED`
- `HISTORICAL REPLAY`

`NEAR-LIVE` and `TRUE LIVE` may appear only as unsupported future capability labels.

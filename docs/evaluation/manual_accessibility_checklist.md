# Manual Accessibility Checklist And Evidence Record (UX-03)

This checklist supports the manual accessibility acceptance that the automated 140-snapshot
browser audit deliberately does **not** provide (see
[assumption register](../assumption-register.md): "Automated screenshot capture is a complete
accessibility evaluation" is `contradicted`). It is an execution template for a human reviewer;
completing it does not by itself accept `UX-03`, and TrafficTwin never records a WCAG-conformance
claim without the underlying evidence.

## How to run

1. Start the v0.7 app: `traffictwin demo launch .demo` (or point `TRAFFICTWIN_WORKSPACE_PATH` at a
   v0.7 workspace and run Streamlit directly). Visit each route at `?page=<url-path>` where the
   grouped router exposes it.
2. For each route, perform the four checks below and record `pass` / `fail` / `n/a` with a note.
3. Repeat the keyboard and contrast checks at 200% browser zoom.
4. Record the reviewer, date, browser, assistive technology, and viewport in the header block.
5. File the completed copy under `docs/evaluation/evidence/` with a dated filename. Do not mark any
   `UX-*` capability accepted from this document alone; the lead reconciles it with the other gates.

### Per-route checks

- **K (keyboard):** every interactive control is reachable and operable by keyboard alone, focus
  order is logical, and focus is always visible.
- **S (screen reader):** headings, buttons, form fields, tables, and status/badge text expose a
  meaningful accessible name; unavailable/partial/stale evidence states are announced, not just
  colour-coded.
- **C (contrast):** text and essential non-text indicators meet a legible contrast ratio in both
  light and dark themes; no critical copy is truncated.
- **Z (zoom/reflow):** at 200% zoom, content reflows without loss of function or horizontal
  scrolling of the page body.

## Evidence header (fill in)

| Field | Value |
|---|---|
| Reviewer | |
| Date | |
| Browser + version | |
| Assistive technology | |
| Viewports tested | desktop 1440×1000 / mobile 390×844 |
| App commit | |

## Route matrix (35 routes)

| Group | URL path | Page | K | S | C | Z | Notes |
|---|---|---|---|---|---|---|---|
| Overview | `home` | Home | | | | | |
| Overview | `guided-workflow` | Guided Demo | | | | | |
| Overview | `manchester` | Manchester Operations | | | | | |
| Build & run | `experiment-planner` | Experiment Planner | | | | | |
| Build & run | `parameter-sweep` | Parameter Sweep | | | | | |
| Build & run | `scenario-mutations` | Scenario Mutations | | | | | |
| Build & run | `scenario-builder` | Scenario Builder | | | | | |
| Build & run | `bundle-import` | Bundle Import & Validation | | | | | |
| Build & run | `sumo` | SUMO Output Import | | | | | |
| Build & run | `tos-import` | TOS Data Import | | | | | |
| Build & run | `vec` | VEC Reproduction Workbench | | | | | |
| Build & run | `experiments` | Experiment Manager | | | | | |
| Analyse | `tos-results` | TOS Results | | | | | |
| Analyse | `tos-replay` | TOS Mobility & RSU Replay | | | | | |
| Analyse | `tos-training` | TOS Training & Audit | | | | | |
| Analyse | `triviality` | Triviality & Winner Map | | | | | |
| Analyse | `replay` | Replay | | | | | |
| Analyse | `run-overview` | Run Overview | | | | | |
| Analyse | `temporal-metrics` | Temporal Metrics | | | | | |
| Analyse | `energy` | Energy Evidence | | | | | |
| Analyse | `fairness` | Fairness Evidence | | | | | |
| Analyse | `threshold-sensitivity` | Threshold Sensitivity | | | | | |
| Analyse | `spatial-rsu` | Spatial & RSU Evidence | | | | | |
| Analyse | `infrastructure` | Infrastructure & Congestion | | | | | |
| Analyse | `compare` | Comparison | | | | | |
| Analyse | `journey-time` | Journey-Time Lens | | | | | |
| Evidence | `statistics` | Statistical Study | | | | | |
| Evidence | `diagnostics` | Diagnostics & Evidence | | | | | |
| Evidence | `provenance` | Provenance Explorer | | | | | |
| Evidence | `reports` | Reports | | | | | |
| Evidence | `mock-evaluation` | Mock Evaluation Analysis | | | | | |
| Advanced | `manifest-inference` | Manifest Inference Wizard | | | | | |
| Advanced | `search` | Search | | | | | |
| Advanced | `settings` | Settings | | | | | |
| Advanced | `about` | About | | | | | |

## Outcome

- Total routes: 35. Passed: ___ / Failed: ___ / N/A: ___.
- Blocking issues (must fix before UX-03 acceptance):
- Non-blocking issues:
- Reviewer conclusion (not a WCAG conformance claim):

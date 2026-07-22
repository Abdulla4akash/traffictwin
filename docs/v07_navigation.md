# v0.7 Task-oriented Navigation Candidate

This document describes the implemented candidate foundation for `UX-01` from the
[TrafficTwin v0.7 design](traffictwin-design-v0_7.md#13-product-information-architecture-and-visual-design).
`UX-01` remains `planned`; the candidate is opt-in until its complete atomic-cutover gate passes.

## Current behaviour

The ordinary application continues to use the complete v0.6 radio router. No existing page has
been removed, hidden, renamed in the legacy UI, or made dependent on a Manchester source.

An explicit environment flag enables the candidate router:

```bash
TRAFFICTWIN_V07_NAVIGATION=1 uv run streamlit run src/traffictwin/ui/app.py
```

The candidate uses `st.navigation(..., position="sidebar")` and `st.Page`. Its five visible groups
are **Overview**, **Build & run**, **Analyse**, **Evidence**, and **Advanced**. A hidden root route
renders Home while the visible Home page retains the stable `/home` route.

## Page preservation

All 34 current `UiPage` values have exactly one visible candidate route, unique URL path, Material
Symbol, direct script under `src/traffictwin/ui/app_pages/`, and existing tested renderer. Page
scripts remain thin: they select the typed `UiPage` and delegate to the shared runtime; scientific
logic, loading, metrics, diagnostics, execution, and source access remain in existing services.

The shared runtime replaces the former 34-branch entry-point dispatch without changing renderer
inputs. Router-aware page actions preserve the legacy callback/state key for the v0.6 router and
invoke `st.switch_page` from normal top-level script execution for the candidate. The latter is
deliberately not called inside a widget callback, where Streamlit treats its rerun as a no-op.

## Acceptance evidence

Automated checks currently prove:

- exact 34-page membership against the `UiPage` enumeration;
- exact group and URL mapping against Appendix D of the v0.7 design;
- unique script and URL paths;
- existence of every direct page script;
- complete renderer coverage;
- Material icons and navigation construction accepted by the locked Streamlit runtime;
- candidate hidden-root Home rendering without the legacy radio;
- default fallback to all 34 legacy options;
- candidate page-to-page callback routing; and
- successful AppTest smoke rendering of every direct page with initialized shared state;
- the complete 45-test navigation suite on both `streamlit==1.58.0` and the locked
  `streamlit==1.59.2` development environment; and
- a source-distribution/wheel build containing all 34 direct scripts, followed by installation
  into an isolated environment and a successful candidate-root AppTest from `site-packages`;
- live-browser rendering of all 34 exact direct URL paths with the expected page heading and no
  Streamlit exception; and
- live-browser acceptance of direct-route refresh, Home-to-Guided page action, and browser
  back/forward history. This check found and drove the top-level page-action correction above.

## Remaining cutover gates

The feature flag must not become the default until the project also passes:

- cross-page state tests for representative research workflows;
- desktop/mobile screenshots, keyboard order, labels, contrast, and truncation checks;
- final removal of deprecated `use_container_width` calls under `UX-03`; and
- shared capability, documentation, package-requirement (`streamlit>=1.58,<2`), version, and
  release reconciliation.

Until those gates pass, this candidate is development evidence only and the complete v0.6 router
remains the guaranteed default.

# v0.7 Task-oriented Navigation Candidate

This document describes the implemented candidate foundation for `UX-01` from the
[TrafficTwin v0.7 design](traffictwin-design-v0_7.md#13-product-information-architecture-and-visual-design).
`UX-01` remains `planned`; making this the normal development router does not accept its complete
atomic-cutover gate.

## Current behaviour

The ordinary v0.7 development application uses the grouped router. No existing page has been
removed, hidden, or made dependent on a Manchester source. The complete v0.6 radio router remains
available as an explicit compatibility route:

```bash
TRAFFICTWIN_V07_NAVIGATION=legacy uv run streamlit run src/traffictwin/ui/app.py
```

Values `0`, `false`, and `no` select the same compatibility route. Omitting the variable, or using
`1`, selects the grouped router:

```bash
uv run streamlit run src/traffictwin/ui/app.py
```

The candidate uses `st.navigation(..., position="sidebar")` and `st.Page`. Its five visible groups
are **Overview**, **Build & run**, **Analyse**, **Evidence**, and **Advanced**. A hidden root route
renders Home while the visible Home page retains the stable `/home` route. The additive
Manchester Operations candidate appears under Overview at `/manchester`, and the additive
Match Review candidate appears under Source evidence at `/match-review`; the additive RSU
Monitor candidate also appears under Source evidence, at `/rsu-monitor`, drilling into one
imported run's per-RSU load, and the additive Bus Sessions candidate appears there too, at
`/bus-sessions`, rendering aggregate-only attended-session measurements. The additive Campaigns
candidate also appears under Source evidence, at `/campaigns`, rendering one explicitly named
campaign receipt file at a time — it never scans a directory, so no campaign is opened unless a
person types its path. All five are outside the normative 34-page migration inventory and cannot
replace any v0.6 destination.

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
- each additive route (Manchester, Match Review, RSU Monitor, Bus Sessions, Campaigns) is unique
  and its direct script exists;
- complete renderer coverage;
- Material icons and navigation construction accepted by the locked Streamlit runtime;
- default grouped hidden-root Home rendering without the legacy radio;
- explicit compatibility fallback to all 34 legacy options;
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

## Remaining acceptance gates

The development-router default does not make `UX-01` implemented. Release acceptance still
requires:

- cross-page state tests for representative research workflows;
- manual keyboard order, screen-reader, contrast, zoom, truncation, and participant checks; and
- minimum-version acceptance for each new page, shared capability/documentation, package version,
  and release reconciliation. Packaging now declares the reviewed `streamlit>=1.58,<2` floor.

The bounded automated slice is complete: the 34 normative routes plus additive Manchester
Operations pass 140 browser snapshots across desktop/mobile and light/dark, and the deprecated
`use_container_width` migration is complete. These results do not replace the remaining manual
acceptance gates.

Until those gates pass, this candidate is development evidence only. The immutable `v0.6.0` tag
and its complete router remain the guaranteed release baseline, while the v0.7 branch retains the
explicit legacy compatibility route.

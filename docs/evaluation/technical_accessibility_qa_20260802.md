# Technical browser accessibility QA

## Status and boundary

- Phase: 183
- Date: 2 August 2026
- Evidence class: automated/agent-operated engineering QA
- WCAG, screen-reader, participant or Gate-C acceptance: not claimed

This pass supplements the existing semantic AppTests and 140-view visual-regression matrix with
rendered browser inspection. It does not replace the unticked
[manual accessibility checklist](manual_accessibility_checklist.md). No agent observation is
represented as a human assistive-technology session.

## Owned paths

- `docs/evaluation/technical_accessibility_qa_20260802.md`
- `docs/evaluation/technical_accessibility_qa_20260802.json`
- `docs/evaluation/manual_accessibility_checklist.md`
- `docs/index.md`
- `docs/implementation-status.md`
- `docs/current_progress_v0_7.md`
- `CHANGELOG.md`
- `AGENTS.md`
- `src/traffictwin/ui/app.py` (discovered shared-shell defect only)
- `tests/ui/test_accessibility.py` (matching regression assertion only)

## Planned browser checks

1. Start the repository application locally with no external service configuration.
2. Inspect Home, Manchester Operations, Manchester Gate D, Guided Demo, Decision Safety and
   Decision Audit as representative navigation, map, workflow, table and evidence-heavy routes.
3. For each route, record top-level heading count, empty/duplicate control labels, horizontal
   overflow and rendered error text at desktop and narrow viewports.
4. Exercise forward keyboard traversal on representative controls and record whether focus remains
   visible and escapes the navigation/content surfaces.
5. Inspect 200% and 400% zoom/reflow states where the selected browser surface supports genuine
   zoom; record unsupported checks as not performed rather than infer a result.
6. Calculate deterministic contrast heuristics only for rendered opaque text/background pairs that
   can be resolved from computed styles. Report unresolved transparency, images, charts and focus
   indicators separately.

## Acceptance

The structured record must name every checked route/state and every untested boundary. Any
actionable defect must either be fixed under an amended exact-path claim or remain explicitly open.
The human checklist stays unticked and unsigned regardless of the engineering result.

## Executed matrix

The local application was inspected in Chrome through the rendered browser surface. Each of the
six routes was checked first at a 1,440 × 900 CSS-pixel desktop viewport and then at a 390 × 844
narrow viewport. The structured companion record contains the per-state counts.

| Route | Surface represented | Desktop result | Narrow result |
|---|---|---|---|
| Home | navigation, cards, primary actions | no exception, empty name, horizontal overflow or resolved-pair contrast failure | same |
| Manchester Operations | map/scene and operational tables | same | same |
| Manchester Gate-D | dense evidence tables and unavailable states | same | same |
| Guided Demo | cross-page workflow | same | same |
| Decision Safety | rules and evidence tables | same | same |
| Decision Audit | XAI/disagreement tables | same | same |

The contrast probe inspected visible text with a non-transparent foreground and a resolvable
opaque ancestor background. It resolved 38/61 to 57/90 candidate pairs per desktop route and
32/44 to 59/80 per narrow route. It found no pair below the applicable 4.5:1 normal-text or 3:1
large-text threshold. Transparent composites, charts, images, component boundaries and focus-ring
contrast were not accepted by this heuristic and remain manual work.

## Defect and repair

The first rendered pass found two visible `<h1>` elements on every route: the page title and the
shared `TrafficTwin` sidebar brand. The Phase-183 claim was amended before code. The brand now uses
strong paragraph text, leaving the registered page as the sole top-level heading. A post-change
rerun of all six routes found exactly one visible `<h1>` on each route, with no rendered exception,
empty interactive name, horizontal overflow or resolved-pair contrast failure. The matching source
regression prevents the shell from returning to `st.sidebar.title`.

Chrome reported a 1,800 × 1,125 CSS viewport and device-pixel ratio 0.8 during the post-fix rerun
despite the unchanged 1,440 × 900 viewport override. This browser-surface discrepancy is preserved
rather than normalised or interpreted; it does not replace the original exact desktop/narrow
matrix.

## Keyboard observation

A bounded forward-Tab traversal covered twelve consecutive focus stops on Home: nine navigation
links, the navigation expander, Deploy and Main menu. Focus advanced on every press and did not
trap. The two header buttons exposed a computed box shadow. Sidebar links changed background on
focus; their computed outline style remained `none`, so this observation does not establish focus
indicator contrast or complete visibility for every control. No Shift+Tab, modal, expander-body,
main-content, full-route or assistive-technology traversal is inferred.

## Residuals and non-claims

- Streamlit emits repeated `Link to heading` anchor names and repeated table-toolbar names such as
  `Show/hide columns`, `Download as CSV`, `Search` and `Fullscreen`. Manchester Operations also
  exposes repeated framework `Open`/`Show data` affordances. These are recorded as framework-level
  accessible-name ambiguity and were not hidden by weakening the repository's application-control
  tests.
- Genuine 200%/400% browser zoom could not be driven or verified through the selected browser
  surface. The narrow viewport is reflow evidence only, not a zoom substitute.
- Screen-reader announcements, text-spacing overrides, dark-theme contrast, chart/non-text
  contrast and human task completion were not performed.
- The manual checklist remains entirely unticked and unsigned. Phase 183 does not accept UX-03 or
  Gate C and does not claim WCAG conformance.

## Verification

The acceptance commands and exact pass counts are recorded in the completion section of the phase
claim and in the current-progress tracker. This report and its JSON companion are engineering
receipts, not participant or scientific evidence.

# Claude UI feedback and suggestions

- **Author:** Claude (AI agent), 2026-07-23
- **What this is:** Advisory design feedback on the TrafficTwin Streamlit UI — why it
  currently looks poor, with file:line evidence and a prioritized fix plan.
- **What this is not:** Not a capability claim, not project truth, not a shared
  integration surface. No UI file was modified when producing this document.
- **How it was produced:** The app was run locally (`streamlit run
  src/traffictwin/ui/app.py`) and inspected page by page (Home, Run Overview,
  Diagnostics & Evidence), combined with a five-lens code audit over all of
  `src/traffictwin/ui/` (shell, shared components, core pages, analysis pages,
  workflow pages). Every count below was produced by grep and is reproducible.

## Root cause (one sentence)

The repository's honesty rules ("keep the UI thin over tested library code",
"never claim more than the evidence allows") have been implemented as *showing
raw evidence artifacts directly*, so the app renders like a debug console for
auditors instead of a product; the constraints are right, the missing step is a
presentation layer that translates typed artifacts into designed UI.

## The six concrete causes

### 1. Zero theming

- `.streamlit/config.toml` contains only `[client]` and `[browser]` — **no
  `[theme]` section**. Everything renders in stock Streamlit defaults,
  including the default red primary button.
- The only styling is a ~24-line CSS shim in `src/traffictwin/ui/theme.py`
  (`apply_research_theme`) that hardcodes light-mode colors
  (`background: #f6f8fa`, `rgba(250,250,252,0.72)`), which breaks visually in
  dark mode.

### 2. The navigation wall

- Default navigation is one flat `st.sidebar.radio("Navigation", ...)` over
  **34 Title-Case entries** with no icons and no visible grouping
  (`src/traffictwin/ui/navigation.py:65`; groups defined at
  `navigation.py:12-51` are flattened by `page_options()` and never shown).
- A properly grouped, icon-bearing `st.navigation` router already exists
  (`src/traffictwin/ui/navigation_v07.py`) but is opt-in behind
  `TRAFFICTWIN_V07_NAVIGATION=1` (`app.py:37-41`), so the shipped default is
  the radio wall. Even in v0.7 nav, the "Analyse" group holds 14 pages.

### 3. Raw JSON dumps as primary page content (biggest offender)

- Counts across `src/traffictwin/ui/pages/`: **31 `st.json`**, **59
  `st.write(...)`**, **62 `model_dump` call sites** feeding them.
- Observed on screen: "Evidence Availability" renders as a syntax-highlighted
  JSON blob (`{"tasks": "available", ...}`) as the page body
  (`pages/evidence_readiness.py:31-55`); Home's "Current Limitations" is a
  Python list dumped through `st.write`, displaying `0:"..." 1:"..."` indices
  (`pages/home.py:303-316`).
- The shared "unavailable" panel renders raw dicts with SCREAMING_SNAKE reason
  codes (`components/unavailable.py:18-23`), and shared components
  (`components/source_preview.py:13-21`, `components/trace_tree.py:14-24`)
  institutionalize the dump aesthetic, replicating it to all ~38 pages.
- Full SHA-256 fingerprints appear in user-facing page headers and captions
  (e.g. Run Overview header line "… | Fingerprint: b778c4c3…"; also
  `pages/manchester_operations.py:215-217`).

### 4. Fake badges, misused metrics, unconfigured tables

- "Badges" are bold inline-code markdown — `st.markdown(f"**\`{label}\`**")`
  (`components/badges.py:24-39`) — so every status ("ACCEPTED WITH WARNINGS",
  "HISTORICAL REPLAY") is an ALL-CAPS monospace chunk with no color semantics,
  instead of `st.badge`.
- `st.metric` cards hold whole sentences ("Standalone product polish
  prototype", "TrafficTwin v0.5") that truncate to "Standal…" on screen
  (Home KPI row); Run Overview shows a nine-metric wall with unit-less values
  ("Latency P50 — 120").
- **91 `st.dataframe` calls, zero `column_config`** anywhere; tables expose
  machine columns verbatim (`run_id`, `experiment_id`, `seed_id`,
  `random_seed` at `pages/home.py:287-299`; `metric_key`, `absolute_delta`,
  `reason_codes` from `tables.py:63-76`).

### 5. Warning-banner dominance and duplicated headings

- ~**272 alert calls** across 38 page files (`st.info`=115, `st.error`=96,
  `st.warning`=61) plus 163 `st.caption` calls — roughly seven banners per
  page, mostly negative capability messaging; entire sections render as
  all-"Unavailable" metrics.
- The same page description string is rendered twice on screen — once in the
  sidebar (`navigation.py:127-130`) and once under the title
  (`navigation.py:133-138`); the v0.7 Home stacks `st.title` directly on
  `st.header` (`pages/home.py:47-48`). Section structure is monotone: 86
  `st.subheader` vs 1 `st.header`.

### 6. Almost no charts, almost no layout

- The whole UI contains **two `st.line_chart` calls** (`pages/sumo_import.py:265-266`)
  and one pydeck map; zero Altair/Plotly — despite pages named Temporal
  Metrics, Energy Evidence, Fairness Evidence, Statistical Study. Statistical
  Study is 1,137 lines with nine `st.download_button` blocks and no chart.
- `st.tabs` is used once in the entire app (`pages/provenance_explorer.py:265`),
  bordered containers six times; 63 grey collapsed `st.expander`s are the
  dominant grouping device. With `layout="wide"` (`app.py:21`) everything is a
  full-width vertical scroll.

## Suggestions (prioritized; aligned with the approved v0.7 design §12–§13, UX-01–UX-03)

The highest-leverage fixes are in a handful of *shared* files, because those
replicate to every page. None of these change scientific truth — they change
how already-computed, already-typed evidence is presented.

1. **Add a `[theme]` to `.streamlit/config.toml`** (primaryColor, fonts,
   subdued neutrals) and delete the hardcoded light-mode CSS from `theme.py`
   or make it theme-aware. One file; changes every page instantly.
2. **Make the v0.7 `st.navigation` router the default** (flip the env-var
   gate) so pages get groups and Material icons; keep group sizes ≤ ~8 by
   splitting "Analyse". The 34-item radio should never be the first
   impression.
3. **Redesign the five shared components** — this removes most of the debug
   aesthetic in one pass:
   - `components/badges.py`: use `st.badge` with color semantics
     (green accepted / yellow warnings / red rejected / grey historical).
   - `components/unavailable.py`: render a bordered container with an icon, a
     one-sentence human explanation, and the reason code as small caption —
     never a raw dict.
   - `components/source_preview.py`, `components/trace_tree.py`: formatted
     labels and `st.dataframe` with `column_config`, not `st.write(dict)`.
   - `navigation.py:render_page_header`: drop the duplicated description
     (keep it in one place), keep breadcrumb small.
4. **Banish raw dumps from primary content.** `st.json`/`st.write(dict)` and
   full fingerprints belong inside an "Evidence / Advanced" expander (the v0.7
   design already prescribes exactly this split); page bodies should show
   formatted values. Truncate hashes to 12 chars with copy-on-click, full
   value in the expander.
5. **Tables:** add `column_config` everywhere (human labels, number/percent
   formats, hidden machine-ID columns by default). The design doc's rule about
   removing sensitive columns before render already implies a mapping layer —
   extend it with display names and units.
6. **Metrics:** `st.metric` only for numbers with units; text facts
   ("Design version", "Adapter") belong in a caption row or small table.
   Split the nine-KPI wall into 3–4 KPIs + a details expander.
7. **Charts:** the metric families (temporal, energy, fairness, threshold
   sensitivity, statistical study) should each get one native/Altair chart
   with explicit units and source labels, per design §12.1/§13. Suppress or
   merge "unknown" axis categories with an explicit footnote instead of a bare
   "unknown" bar.
8. **Banner diet:** one status strip per page (mode + evidence state + source
   badge). Capability limitations move to a single collapsible "Limitations"
   panel; repeated per-widget warnings become disabled-with-reason controls
   (the design already requires exact reason codes on disabled buttons —
   render them as help tooltips, not stacked `st.warning` boxes).
9. **Widget modernization:** `st.segmented_control` for mode switches
   (design §12.1 already mandates it), `st.pills` for small sets, sentence
   casing for labels and titles, Material icons over emojis, and no
   `use_container_width` (deprecated; use `width="stretch"` — this also
   satisfies UX-03).

## Coordination notes for whichever agent implements this

- The checkout is shared; many `src/traffictwin/ui/` files are currently dirty
  from another agent's in-flight v0.7 work (navigation, app_pages, Manchester
  operations). Coordinate ownership before editing those; the shared-component
  files (`components/*`, `theme.py`, `tables.py`, `.streamlit/config.toml`)
  were clean at the time of writing and are the best-isolated starting point.
- Keep every honesty invariant intact: unavailable stays visibly unavailable
  (never zero, never hidden), evidence states stay explicit, no capability is
  claimed implemented by styling alone, and Streamlit pages must stay thin —
  presentation mapping (labels, units, formats) should live in tested library
  code, not inline in pages.
- UI acceptance for `MAN-08`/`UX-01`–`UX-03` still requires the gates in
  `docs/traffictwin-design-v0_7.md`; this document is design feedback only and
  does not advance any capability status.

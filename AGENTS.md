# TrafficTwin Agent Instructions

Repository root: `diss/`

Canonical product specification: `docs/traffictwin-design-v0_7.md`

Before architectural work or implementation decisions, read the canonical specification completely. Treat it as the product and research specification, while keeping unconfirmed external integrations behind explicit capability interfaces.

After reading the canonical specification, use `docs/current_progress_v0_7.md` for current
sequencing, remaining work, dependencies, and blockers. It is a working tracker rather than an
acceptance authority; `docs/implementation-status.md` remains the formal implementation truth.

The v0.7 specification is the approved future product design for Manchester historical/live
evidence, observed-to-SUMO calibration, SUMO-to-VEC research flow, and the task-oriented product
interface. Every `MAN-*`, `UX-*`, and `REL-01` capability begins planned; design inclusion does not
make it implemented. The immutable `v0.6.0` release remains the implemented reproducible baseline.
VEC-01 through VEC-12 have passed their recorded evidence gates, but this does not broaden any
residual scientific, licensing, hosting, canonicalisation, or generic-launch boundary. Use
`docs/implementation-status.md` for current truth.

## Non-Negotiable Constraints

- The guaranteed workflow is import-first.
- Direct Randy VEC/SUMO launch is conditional and must not be faked.
- Metrics must be computed by deterministic code.
- Diagnostic hypotheses must be produced by deterministic rules.
- An LLM, if added later, may only render already-computed findings into prose.
- Do not let an LLM calculate metrics, invent findings, or recommend unsupported actions.
- Do not fabricate Randy schemas, CSV fields, simulator capabilities, launch commands, live data, experimental results, paper claims, or performance numbers.
- Preserve raw inputs unchanged.
- Keep unsupported or unknown functionality visibly unavailable rather than silently simulated.
- Use synthetic fixtures only when clearly labelled synthetic.
- Keep the UI thin over tested library code.

## Project Records

As the project evolves, update:

- `docs/current_progress_v0_7.md` for v0.7 sequencing and remaining-work changes
- `docs/implementation-status.md`
- `docs/assumption-register.md`
- `docs/open-questions.md`
- `docs/architecture.md` when architecture decisions change

## v0.7 Work Coordination

### Completed parallel ownership: Claude UI presentation Phase 1

- Claude owns advisory presentation groundwork for `UX-01`–`UX-03` on
  `claude/ui-redesign`, forked from the first pushed lead v0.7 integration commit after
  `c2160999c6c66ab3b871b2ebd0ef6645a1ee6952` that records this grant. This grant does not accept a
  gate or permit any capability-status change.
- The exclusive Phase 1 file set is `.streamlit/config.toml`,
  `src/traffictwin/ui/theme.py`, `src/traffictwin/ui/tables.py`, every tracked source file under
  `src/traffictwin/ui/components/`, and new tests named
  `tests/unit/ui/test_components_*.py` or `tests/unit/ui/test_tables_display.py`.
- Existing public functions, imports, arguments, and return shapes in the claimed presentation
  modules must remain backward compatible because lead-owned in-flight pages consume them. New
  display models and helpers may be additive; removing or renaming an existing API requires a new
  lead review.
- Claude must not edit `src/traffictwin/ui/app.py`, either navigation module,
  `src/traffictwin/ui/manchester_operations.py`, any file under `src/traffictwin/ui/pages/`, any
  existing test outside the exact new-test allowance, `pyproject.toml`, `uv.lock`, integration or
  CLI code, shared project records, generated references, documentation indexes, changelog, or
  this `AGENTS.md` file.
- If the branch was created earlier, it must be rebased onto that pushed integration commit before
  work continues. Merge is conditional on focused component tests, existing UI tests, the full
  relevant unit suite, light- and dark-theme smoke checks, and lead review of the complete branch
  diff. Phase 2 page or navigation work requires a fresh disjointness check and a separate
  ownership grant.

Phase 1 was lead-reviewed and merged at `11eacb6`; the lead then removed the residual CSS injector
at `0da8175` so native Streamlit configuration is the only theme mechanism. The Phase 1 file claim
is closed. Later edits to those shared presentation files require a new grant.

### Completed parallel ownership: Claude UI presentation Phase 2A

- Claude owns the bounded `UX-01`–`UX-03` shell and first-impression presentation slice after
  fast-forwarding `claude/ui-redesign` to the latest `codex/traffictwin-v0.7`. This work remains
  presentation-only: it cannot accept a gate, change capability truth, fetch evidence, or compute
  scientific results.
- The exclusive Phase 2A source files are `src/traffictwin/ui/app.py`,
  `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, and exactly these page
  files: `src/traffictwin/ui/pages/home.py`, `src/traffictwin/ui/pages/run_overview.py`, and
  `src/traffictwin/ui/pages/evidence_readiness.py`.
- Claude may edit `tests/ui/test_navigation_v07.py` and `tests/ui/test_product_polish.py`, and may
  add tests named `tests/unit/ui/test_page_presentation_*.py`. The linked-worktree About regression
  test must remain intact. No other existing test file is transferred.
- Phase 2A must make grouped `st.navigation` the normal v0.7 route while preserving an explicit,
  tested compatibility path; remove duplicated shell copy; move raw dictionaries/JSON and full
  machine identifiers out of primary page content into clearly labelled Advanced/Evidence
  expanders; use numeric `st.metric` cards only; and apply the merged table/badge/fingerprint
  presentation helpers without changing the underlying values.
- Use native Streamlit APIs and `.streamlit/config.toml`: no custom HTML/CSS, no
  `unsafe_allow_html`, no deprecated `use_container_width`, no new dependency, and no scientific or
  acquisition logic in a page. Unavailable, stale, synthetic, historical, near-live, and
  live-vehicle evidence states must remain explicit and must never be hidden, combined, or filled
  with defaults.
- Claude must not edit `src/traffictwin/ui/pages/manchester_operations.py`,
  `src/traffictwin/ui/manchester_operations.py`, `src/traffictwin/ui/services.py`,
  `src/traffictwin/ui/page_runtime.py`, `src/traffictwin/ui/labels.py`, any `app_pages/` wrapper,
  any Phase 1 shared presentation file, integration/CLI code, dependencies, shared project records,
  generated references, documentation indexes, changelog, or this `AGENTS.md` file.
- Handoff requires focused tests, all `tests/ui`, all `tests/unit`, ruff, strict mypy on edited
  source, `git diff --check`, light/dark screenshots of the Home and one evidence-heavy page, and a
  complete list of residual raw dumps or presentation debt. Leave changes committed only on
  `claude/ui-redesign`; the lead owns final review, merge, capability reconciliation, and push.

#### Phase 2A closure amendment after lead review

- Before any Phase 2B page work, Claude must rebase `claude/ui-redesign` onto lead commit
  `e3a793765c7ab1a1edd15b7221700376b787b705` and close the 18 reproducible full-UI-suite failures
  caused by making grouped `st.navigation` the default. This is test migration, not a reason to
  restore the legacy router as the default.
- Claude may additionally edit exactly these existing tests:
  `tests/ui/test_analyst_annotations.py`, `tests/ui/test_executive_summary.py`,
  `tests/ui/test_experiment_planner.py`, `tests/ui/test_latex_exports.py`,
  `tests/ui/test_manifest_inference_services.py`, `tests/ui/test_measurement_imperfections.py`,
  `tests/ui/test_parameter_sweep.py`, `tests/ui/test_registry_search.py`,
  `tests/ui/test_report_diffing.py`, `tests/ui/test_scenario_mutation.py`,
  `tests/ui/test_sumo_services.py`, `tests/ui/test_tos_analysis_pages.py`, and
  `tests/ui/test_tos_services.py`. Migrate only navigation setup from `app.radio[0]` to the exact
  `AppTest.switch_page(page_script_for(UiPage...))` route; preserve the scientific and interaction
  assertions.
- In the already-owned `src/traffictwin/ui/pages/home.py`, replace the stale legacy statement that
  no live Manchester data is connected with the current source truth: live BODS evidence covers
  buses only, while general live/near-live Manchester road traffic remains unavailable. Do not
  imply that WebTRIS is near-live; the lead's new reassessment explicitly refuses that claim.
- Re-run all `tests/ui` with zero failures, all `tests/unit`, focused navigation/page tests, ruff,
  strict mypy, and `git diff --check`, and supply the required light/dark screenshots. Do not begin
  the proposed Phase 2B page/table harvest until the lead merges this closed Phase 2A branch and
  records a new file-level grant.

Phase 2A was lead-reviewed and merged at
`b4f4d39c66c9e10d9ce16c5ba232d09e51abfea3`. The lead then reconciled its Manchester evidence
copy against the accepted BODS and National Highways operational slices. The Phase 2A source and
test claim is closed; later edits require a new explicit grant.

### Completed parallel ownership: Claude UI presentation Phase 2B Tier 1

- Claude owns the first bounded page-presentation harvest after fast-forwarding
  `claude/ui-redesign` to the pushed `codex/traffictwin-v0.7` HEAD that contains this grant. The
  work is presentation-only groundwork for `UX-01`–`UX-03`; it cannot accept a gate, change
  capability truth, fetch evidence, alter deterministic calculations, or edit source data.
- The exclusive source files are exactly
  `src/traffictwin/ui/pages/{helpers.py,sumo_import.py,bundle_import.py,compare.py,about.py,tos_data_import.py,experiment_manager.py}`.
  The shared helper may shorten a primary-display fingerprint only while retaining the complete
  value in an Advanced/Evidence surface. The six pages may adopt the existing badge, table,
  column-configuration, fingerprint, bordered-container, and numeric-metric presentation helpers.
- Claude may edit only these existing tests where a presentation assertion must follow the owned
  page: `tests/ui/test_product_polish.py`, `tests/ui/test_sumo_services.py`, and
  `tests/ui/test_tos_services.py`. Scientific, service, navigation, and interaction assertions
  must remain intact. Claude may add tests named
  `tests/unit/ui/test_page_presentation_tier1*.py`; no other existing test file is transferred.
- Primary content must use human labels, explicit units, native Streamlit tables/charts, numeric
  `st.metric` values, and concise evidence states. Raw dictionaries/JSON, complete fingerprints,
  machine IDs, and implementation metadata may move only to clearly labelled Advanced/Evidence
  expanders; unavailable, rejected, warning, stale, historical, synthetic, and live states must
  remain visible and exact. Hiding a display column must not be used as a privacy boundary.
- Do not edit `.streamlit/config.toml`, navigation/app files, `src/traffictwin/ui/labels.py`, any
  Manchester Operations file, Phase 1 shared components or `tables.py`, `vec_workbench.py`, any
  integration/service/CLI module, dependency file, project record, generated reference,
  documentation index, changelog, or this `AGENTS.md`. In particular,
  `client.showSidebarNavigation` is not part of this grant; the installed Streamlit contract says
  it controls legacy `pages/` auto-navigation, not the explicit `st.navigation` router.
- Handoff requires a clean branch, exact changed-file inventory, focused new/edited tests, all
  `tests/ui`, all `tests/unit`, repository Ruff, strict mypy, `git diff --check`, and light/dark
  screenshots of at least one import page and one comparison/metadata page. Leave commits only on
  `claude/ui-redesign`; the lead owns review, merge, shared records, capability reconciliation, and
  push. Phase 2B Tier 2 remains ungranted.

Phase 2B Tier 1 was lead-reviewed on 24 July 2026 and integrated by cherry-picking the six
reviewed `claude/ui-redesign` commits onto the `claude/complete-v0.7` integration branch created
at `v0.7.0-alpha.4`. The reviewed diff stayed exactly inside the granted seven-page file set plus
the permitted new Tier 1 presentation test; the lead-owned action-aware Guided Demo, National
Highways layers, and all shared records were untouched. The Tier 1 source and test claim is
closed; later edits to those pages require a new explicit grant.

### Active parallel ownership grant: Claude UI presentation Phase 2B Tier 2

- The repository owner granted Phase 2B Tier 2 presentation work on 24 July 2026 from the clean
  pushed integration head `6c554164ed86f5174ca9c75fea4b24aa141287c2` on `claude/complete-v0.7`.
  The work is presentation-only groundwork for `UX-01`–`UX-03`; it cannot accept a gate, change
  capability truth, fetch evidence, alter deterministic calculations, or edit source data, and no
  capability moves off `planned`.
- The exclusive source files are exactly
  `src/traffictwin/ui/pages/{statistical_study.py,vec_workbench.py,temporal_metrics.py,threshold_sensitivity.py}`.
  These four pages may adopt the existing badge, table, column-configuration, fingerprint,
  bordered-container, tab, chart, and numeric-metric presentation helpers.
- Permitted existing tests to edit for presentation assertions:
  `tests/ui/test_statistical_study_services.py`, `tests/integration/test_statistical_study_ui.py`,
  `tests/ui/test_vec_oneclick_ui.py`, `tests/ui/test_threshold_sensitivity_services.py`, and the
  presentation-related assertions for these four pages in `tests/integration/test_ui_demo_flow.py`.
  Scientific, service, navigation, and interaction assertions must remain intact. New tests may be
  added under `tests/unit/ui/` named `test_page_presentation_tier2*`,
  `test_statistical_study_presentation*`, `test_vec_workbench_presentation*`,
  `test_temporal_metrics_presentation*`, or `test_threshold_sensitivity_presentation*`.
- Primary content uses human labels, explicit units, native tables/charts, numeric `st.metric`
  values, tabs/bordered sections, and concise evidence states. Raw dictionaries/JSON, complete
  fingerprints, machine IDs, commands, and receipts move only to clearly labelled Advanced/Evidence
  surfaces; unavailable, partial, stale, rejected, and synthetic states remain visible and exact.
  No page performs a scientific calculation, and statistical difference is never presented as
  causality or practical superiority.
- Do not edit scientific libraries, integration adapters, source contracts, capability manifests,
  dependency files, external repositories, other page/navigation/app files, Phase 1 shared
  components, or protected tags. No new dependency and no deprecated `use_container_width`.
- Handoff requires the exact changed-file inventory, focused new/edited tests, all `tests/ui`, all
  `tests/unit`, affected integration tests, repository Ruff and format checks, strict mypy,
  `git diff --check`, light/dark desktop/mobile screenshots of all four pages, and confirmation
  the 140-view browser audit is not weakened. Commit in small logical commits on
  `claude/complete-v0.7`; never create or move a release tag.

Phase 2B Tier 2 was completed on 24 July 2026 across the four granted pages
(`statistical_study.py`, `vec_workbench.py`, `temporal_metrics.py`, `threshold_sensitivity.py`):
tabs/bordered panels, semantic badges for categorical states, `column_config` tables, deterministic
charts over already-computed values, and all machine detail behind Advanced/Evidence, with services,
navigation, and interaction unchanged and every capability still `planned`. The integrated gate
passed 1,640 unit + 169 UI = 1,809 tests, Ruff/format, strict mypy over 708 files, `git diff --check`,
and the 35-route/140-snapshot browser audit with zero findings. The Tier 2 source and test claim is
closed; later edits to those pages require a new explicit grant.

### Completed parallel ownership: Claude UI presentation Phase 2B Tier 3

- The repository owner granted Phase 2B Tier 3 presentation work on 24 July 2026 from the clean
  pushed integration head `9973e3f87768c86c17d04f8233b50ce175ea6c2a` on `claude/complete-v0.7`,
  covering the remaining highest-impact debug-console pages. The work is presentation-only
  groundwork for `UX-01`–`UX-03`; it cannot accept a gate, change capability truth, fetch evidence,
  alter deterministic calculations, or edit source data, and no capability moves off `planned`.
- The exclusive source files are exactly
  `src/traffictwin/ui/pages/{evidence_readiness.py,provenance_explorer.py,operations.py,triviality.py,participant_evaluation.py,manifest_inference.py}`.
  `operations.py` is the historical-replay Operations View; `manchester_operations.py` is NOT in
  this grant and must not be edited. These six pages may adopt the existing badge, table,
  column-configuration, fingerprint, bordered-container, tab, chart, and numeric-metric helpers.
- Permitted existing tests to edit, changing only assertions related to the six owned pages:
  `tests/ui/test_provenance_services.py`, `tests/ui/test_manifest_inference_services.py`,
  `tests/ui/test_cross_page_state.py`, `tests/integration/test_ui_demo_flow.py`, and
  `tests/integration/test_ui_diagnostics_flow.py`. Scientific, service, navigation, and interaction
  assertions must remain intact. New tests may be added under `tests/unit/ui/` named
  `test_page_presentation_tier3*`.
- Primary content uses human labels, explicit units, native tables/charts, numeric `st.metric` for
  numeric quantities only, and structured readiness/lineage/checklist surfaces. Raw dictionaries/JSON,
  complete fingerprints, machine locators, and inferred manifests move only to clearly labelled
  Advanced/Evidence surfaces; unavailable, rejected, partial, blocked, historical, synthetic, draft,
  mock, and unapproved states remain visible and exact. No page performs a scientific calculation, a
  hypothesis is never presented as a confirmed cause, provenance never implies causality, replay is
  never implied to be live monitoring, no algorithm is declared universally best, and no consent,
  ethics approval, participant response, or usability finding is fabricated.
- Do not edit scientific libraries, integration adapters, source contracts, capability manifests,
  dependency files, external repositories, `manchester_operations.py`, other page/navigation/app
  files, Phase 1 shared components, protected tags, or the user's checkout. No new dependency, no
  arbitrary CSS, and no deprecated `use_container_width`.
- Handoff requires the exact changed-file inventory, focused new/edited tests, all `tests/ui`, all
  `tests/unit`, affected integration tests, repository Ruff and format checks, strict mypy,
  `git diff --check`, light/dark desktop/mobile screenshots of all six pages, confirmation that
  cross-page state and replay selection still work, and confirmation the 140-view browser audit is
  not weakened. Commit in small logical commits on `claude/complete-v0.7`; never create or move a
  release tag.

Phase 2B Tier 3 was completed on 24 July 2026 across the six granted debug-console pages
(`evidence_readiness.py`, `provenance_explorer.py`, `operations.py`, `triviality.py`,
`participant_evaluation.py`, `manifest_inference.py`) and accepted as a completed presentation
increment at pushed commit `e8bf792`. The seven Tier 3 commits kept every capability `planned`,
added `tests/unit/ui/test_page_presentation_tier3.py`, and passed the full 1,816-test unit+UI suite
and the 35-route/140-snapshot browser audit with zero findings. Categorical rule/evidence states are
badges, raw JSON/fingerprints live under Advanced/Evidence, and the non-causal, non-live,
non-universal-best, and no-fabricated-consent framings hold. The Tier 3 source and test claim is
lead-owned for reconciliation.

### Active parallel ownership grant: Claude UI presentation Phase 2B Tier 4

- The repository owner granted Phase 2B Tier 4 "analysis-evidence presentation" work on 24 July 2026
  from the clean pushed integration head `e8bf792` on `claude/complete-v0.7`, verified in sync with
  `origin/claude/complete-v0.7`. The work is presentation-only groundwork for `UX-01`–`UX-03`; it
  cannot accept a gate, change capability truth, fetch evidence, alter deterministic calculations, or
  edit source data, and no capability moves off `planned`.
- The exclusive source files are exactly
  `src/traffictwin/ui/pages/{energy.py,fairness.py,infrastructure.py,journey_time.py,spatial_rsu.py}`.
  These five analysis-evidence pages may adopt the existing badge, table, column-configuration,
  fingerprint, bordered-container, native-chart, and numeric-metric helpers, and native Vega charts
  built inline from already-computed results. `charts.py`, `tables.py`, `components/*`, navigation,
  services, and every other module stay untouched.
- Permitted existing tests to edit, changing only assertions related to these five owned pages:
  `tests/integration/test_ui_demo_flow.py`, `tests/ui/test_services.py`, `tests/ui/test_chart_data.py`,
  and `tests/ui/test_product_polish.py`. Scientific, service, navigation, and interaction assertions
  must remain intact. New tests are added under `tests/unit/ui/` named `test_page_presentation_tier4*`.
- Objectives: (1) Energy — coverage-first dashboard showing observed-task, completed-task and
  energy-delay evidence with units and denominators, deterministic charts from computed results,
  explicit available/partial/unavailable family separation, Randy/TOS per-task physical energy kept
  unavailable where unsupported, and never inferring efficiency or superiority from lower energy.
  (2) Fairness — eligible groups, denominators, disparities, uncertainty and exclusions shown
  clearly, charts only for compatible existing group metrics, insufficient groups and
  protected-attribute limitations kept visible, never labelling a policy fair/unfair without the
  predeclared contract and sufficient evidence, and never manufacturing demographic or
  protected-attribute data. (3) Infrastructure — RSU capacity, pressure, utilisation and task
  evidence with explicit units and time windows, canonical infrastructure separated from
  synthetic/source infrastructure, structured tables plus existing computed charts, missing
  capacity/mapping/canonical-identity kept unavailable, and source RSU slots never presented as
  verified Manchester roadside infrastructure. (4) Journey Time — trip-duration evidence, cohort
  coverage, completion status and exclusions, a deterministic distribution/comparison chart where
  existing data supports it, missing trip joins and incomplete journeys shown explicitly, no
  conversion of incomplete/missing journeys to zero, and no causal claim between offloading policy
  and journey time. (5) Spatial & RSU — coordinate frame, spatial coverage, RSU assignment and
  exclusion reconciliation, the existing map/plot used only when its coordinate contract permits,
  synthetic/source coordinates distinguished from geographic Manchester coordinates, unprojectable
  or unmatched records shown explicitly, and no implied live geographic position or official RSU
  location without accepted evidence.
- Primary content uses human labels, explicit units, native tables/charts, bordered horizontal KPI
  rows, numeric `st.metric` for numeric-with-units only, badges for categorical states, and
  `column_config` where it materially improves tables. Raw JSON, complete fingerprints, and machine
  metadata move only to clearly labelled Advanced/Evidence surfaces; unavailable, partial, synthetic,
  historical, and rejected states remain visible and exact. No page performs a scientific calculation
  or accesses source data. Horizontal radio controls in owned pages become `st.segmented_control`
  when behaviour is equivalent. No new dependency, no arbitrary CSS, and no deprecated
  `use_container_width`.
- Do not edit services, scientific libraries, Manchester Operations, navigation, adapters,
  dependency files, capability manifests, external repositories, protected tags, other page/app
  files, Phase 1 shared components, or the user's checkout.
- Handoff requires the exact changed-file inventory, focused new/edited tests, all `tests/unit`, all
  `tests/ui`, affected integration tests, repository Ruff and format checks, strict mypy,
  `git diff --check`, the complete 35-route desktop/mobile light/dark browser audit, verification of
  all five pages at desktop and mobile widths, and confirmation that no existing interaction or
  scientific assertion was weakened. Commit each page as a small logical commit and push continuously,
  then add one documentation reconciliation commit covering `AGENTS.md`, `current_progress_v0_7.md`,
  and `implementation-status.md`; never create or move a release tag.

Phase 2B Tier 4 was implemented on 24 July 2026 across the five granted analysis pages in six pushed
commits — `381b813` (grant record), `b249ed1` (Energy), `587ac8e` (Fairness), `0d0dadf`
(Infrastructure), `02c9d76` (Journey-Time), `cc89a62` (Spatial & RSU) — plus this documentation
reconciliation commit. Every capability stayed `planned`; the scientific services, `charts.py`,
`tables.py`, shared components, navigation, and `manchester_operations.py` were untouched; new charts
are native Vega built inline from already-computed results, with no new dependency and no
`use_container_width`. Verification: 1,655 unit and 169 UI tests pass (1,824 combined),
`tests/unit/ui/test_page_presentation_tier4.py` (8 adversarial tests) and the updated UI-demo-flow
energy/fairness owned-page assertions pass with the R8/R7 transitions and R7 dimension selection
still asserted, repository-wide Ruff and format checks pass, strict mypy passes over 693 configured
files, `git diff --check` is clean, and the 35-route desktop/mobile light/dark browser audit passes
(140 snapshots, zero findings) with all five pages captured at both widths in both themes. Six
pre-existing integration failures (Statistical Study ×4, VEC Workbench ×1, and one Manchester DfT
source-hash probe) fail identically at the base commit `e8bf792`, exercise no Tier 4 page, touch no
module Tier 4 changed, and are outside this grant. Awaiting repository-owner acceptance.

### Completed parallel ownership: integration-regression repair slice

- The repository owner independently reproduced the six pre-existing integration failures and, on
  25 July 2026, granted a repair slice from the pushed head `8fe2301` on `claude/complete-v0.7`. No
  presentation work proceeds until all six failures are resolved honestly. No capability moves off
  `planned`.
- The exclusive owned surfaces are exactly `tests/integration/test_equivalence_ui.py`,
  `tests/integration/test_n_way_ranking_ui.py`, `tests/integration/test_power_analysis_ui.py`,
  `tests/integration/test_regression_gate_ui.py`, `tests/integration/test_vec_interface.py`,
  `tests/integration/test_manchester_dft_gate_b_probe.py`, the DfT Gate-B probe documentation, and a
  new immutable dated evidence record if required.
- Grouped-navigation repair: migrate the four Statistical Study tests and the one VEC Workbench test
  from legacy `app.radio[0]` navigation to the normal v0.7 AppTest mechanism
  `app.switch_page(page_script_for(UiPage...))`, following existing grouped-navigation conventions.
  Legacy navigation is not enabled to hide the failures. Every scientific, interaction, registry, and
  execution-gating assertion is preserved, and the tests exercise the direct Statistical Study and VEC
  Workbench pages under normal v0.7 routing.
- DfT source-hash repair: diagnose exactly which recorded implementation file changed after the
  23 July probe and why. The historical `manchester_dft_gate_b_probe_20260723.json` is immutable
  evidence — never overwrite it, never replace its recorded hash, never claim current code executed
  the old probe. One new minimal, anonymous, bounded, read-only DfT probe against the same three
  audited endpoints in an isolated temporary v0.7 workspace is authorised if necessary; it must use
  current bounded transport/acquisition/parser code, request only the minimum one-row evidence,
  record the exact clean branch commit and implementation hashes, preserve quarantine-before-parse and
  immutable promotion, contain no private path/credential/uncontrolled raw payload, keep capability
  `planned`, retain all timezone/rate-limit/SLA blockers, and create a new dated evidence record
  rather than changing historical evidence. Raw responses stay outside Git; only reviewed
  permission-safe evidence/fixtures are committed. If the provider is unavailable, the failure is
  recorded honestly without fabricating a successful probe or silently weakening the integrity
  assertion. The offline integrity test is updated so historical records remain historical and the
  newest accepted probe binds the current executed implementation.
- Validation: run the six previously failing tests first; run the complete `tests/integration` suite
  and require zero failures (the documented optional real-SUMO skip is acceptable only when SUMO is
  truly unavailable in that process); run all `tests/unit` and `tests/ui`; run Ruff, format check,
  strict mypy, and `git diff --check`; re-run the affected Statistical Study and VEC Workbench
  AppTests under grouped navigation; confirm no old evidence file or protected tag changed. Commit the
  navigation repair and the DfT evidence repair separately, inspect both staged diffs, push to
  `claude/complete-v0.7`, and never create or move a release tag.

The integration-regression repair was completed on 25 July 2026 in two pushed commits — `7011b6f`
(grouped-navigation `switch_page` migration of the four Statistical Study tests and the VEC Workbench
render test) and `7c63213` (DfT Gate-B re-probe binding the current implementation). Diagnosis:
`transport.py`'s byte hash drifted after the 23 July probe because of unrelated National Highways /
WebTRIS work; the historical `manchester_dft_gate_b_probe_20260723.json` correctly bound the code
that executed that probe and is unchanged. A bounded, anonymous, read-only re-probe of the same three
audited endpoints (LA 85; filters 43177/6046/9219; one row each) through the current transport/
acquisition/parser code reproduced byte-identical accepted evidence, so the committed one-row
fixtures were reused unchanged; the new `manchester_dft_gate_b_probe_20260725.json` binds the current
implementation hashes and a recorded clean commit, keeps capability `planned`, commits no raw bytes,
and retains every scoped blocker (GA-DFT-1/2/3). The offline integrity test now discovers all dated
probe records, treats historical records as immutable well-formed evidence (files exist, hashes not
re-bound to current code), and requires the newest accepted probe to bind current code exactly.
Verification: the six previously failing tests pass; the complete `tests/integration` suite passes
with zero failures (no real-SUMO skip required); the full unit+UI+integration suite reports 2035
passed; repository Ruff/format checks, strict mypy over 693 files, and `git diff --check` are clean;
the affected Statistical Study and VEC Workbench AppTests pass under grouped navigation; and no
historical evidence file or protected tag changed. The repository owner accepted this repair as
complete at pushed commit `522dc16`.

### Completed parallel ownership: Claude UI presentation Phase 2B Tier 5

- The repository owner granted Phase 2B Tier 5 "research-workflow presentation" work on 25 July 2026
  from the accepted pushed head `522dc16` on `claude/complete-v0.7`. The work is presentation-only
  groundwork for `UX-01`–`UX-03`; it cannot accept a gate, change capability truth, fetch evidence,
  alter deterministic calculations, or edit source data, and no capability moves off `planned`.
- The exclusive source files are exactly
  `src/traffictwin/ui/pages/{scenario_builder.py,scenario_mutation.py,experiment_planner.py,parameter_sweep.py,reports.py}`.
  They may adopt the existing badge, table, column-configuration, fingerprint, bordered-container,
  native-chart, form, and numeric-metric helpers. Services, scientific libraries, adapters,
  navigation, Manchester Operations, shared components, and capability manifests stay untouched.
- Permitted existing tests to edit, changing only assertions related to these five pages:
  `tests/ui/test_measurement_imperfections.py`, `tests/ui/test_scenario_mutation.py`,
  `tests/ui/test_experiment_planner.py`, `tests/ui/test_parameter_sweep.py`,
  `tests/ui/test_analyst_annotations.py`, `tests/ui/test_executive_summary.py`,
  `tests/ui/test_latex_exports.py`, `tests/ui/test_report_diffing.py`, and
  `tests/integration/test_ui_demo_flow.py`. Every existing interaction and Guided Demo assertion is
  preserved. New tests are added under `tests/unit/ui/` named `test_page_presentation_tier5*.py`.
- Objectives: (1) Scenario Builder — a visually sequential preset → configure → review → generate
  workflow that keeps SYNTHETIC/deterministic/import-first labels prominent, distinguishes authored
  configuration from generated evidence, presents traffic/vehicle/RSU/task/incident/measurement
  settings in coherent sections, keeps unsupported controls disabled with exact reasons, presents the
  preview and generated-bundle receipt as structured summaries, and never implies SUMO/Randy/VEC/live
  launch. (2) Scenario Mutations — source → mutation → candidate as three distinct stages with
  changed/unchanged/excluded/unsupported fields explicit, a human-readable before/after table, and
  deterministic fingerprints/provenance under Advanced/Evidence, never implying simulator execution
  or validation. (3) Experiment Planner — define → validate → inspect run matrix → register with
  common-random-seed design, algorithms, replicates and compatibility visible, the run-matrix size
  numeric, registration separate from execution, the Guided Demo hook only after successful
  registration, and no implication that registering launches runs. (4) Parameter Sweep — choose
  parameter → define bounded values → preview combinations → export/register with grid size, affected
  fields, and evidence limitations shown, a deterministic preview chart/table, unsupported/duplicate/
  invalid/excessive grids explicit, and never an "optimal" parameter or an "executed" claim.
  (5) Reports — inventory, deterministic regeneration, structured comparison, research exports, and
  analyst annotations as clear peer views with lazy/open-state gating where practical without changing
  behaviour, readable report type/format/modified/source cards or tables, separated preview/generate/
  download actions, the Guided Demo hook only after successful report generation, analyst annotations
  visibly separate from computed findings, and no automatic regeneration or annotation-driven change
  to scientific results.
- Primary content uses native Streamlit components and the existing design system, bordered and
  responsive horizontal containers, `st.form` to batch related inputs where appropriate,
  `st.segmented_control` in place of any owned-page horizontal radio when behaviour is equivalent,
  numeric `st.metric` only for numeric-with-units values, and meaningful `column_config` with
  sensitive fields removed before display. Raw JSON/YAML, complete fingerprints, and machine metadata
  live under Advanced/Evidence or explicit preview/download surfaces; unavailable, partial, planned,
  synthetic, and rejected states stay visible. No page performs a scientific computation or external
  acquisition. No new dependency, custom CSS, or deprecated `use_container_width`.
- Verification requires adversarial presentation tests for all five pages, preserved interaction and
  Guided Demo assertions, focused page tests, the complete unit/UI/integration suites at zero
  failures, Ruff/format/strict-mypy/`git diff --check`, the 35-route desktop/mobile light/dark browser
  audit with all five pages captured at both widths and themes, unchanged generated artifacts and
  registries unless a test uses an isolated temporary workspace, and unchanged protected tags and
  historical source evidence. Commit each page separately, push continuously, and finish with one
  documentation reconciliation commit covering `AGENTS.md`, `current_progress_v0_7.md`, and
  `implementation-status.md`; never create or move a release tag.

Phase 2B Tier 5 was completed on 25 July 2026 across the five granted research-workflow pages in
seven pushed commits — `10f5ea8` (grant record), `7255ea8` (Scenario Mutations), `e40b586`
(Experiment Planner), `df4d3eb` (Parameter Sweep), `9fa922f` (Scenario Builder), `1fb533d` (Reports),
and `c9442e5` (test format) — plus this documentation reconciliation commit. Scenario Mutations now
renders source → mutation → candidate as three badged stages with a human-readable before/after table
and fingerprints/manifest under Advanced/Evidence; Experiment Planner shows a define → validate →
inspect run matrix → register sequence with an explicit numeric common-random-seed run matrix and a
Stage 4 registration-not-execution caption; Parameter Sweep shows choose → define → preview → export
with grid size, affected fields, a deterministic preview chart, and no optimal/executed claim;
Scenario Builder is a sequential preset → configure → review → generate flow that separates authored
configuration from a structured generated-bundle receipt and never implies SUMO/Randy/VEC/live
launch; and Reports is organised into five peer-view tabs (Inventory/Regenerate/Compare/Exports/
Annotations) with annotations kept separate from computed findings and no automatic regeneration.
Every capability stayed `planned`; services, scientific libraries, adapters, navigation, Manchester
Operations, shared components, and capability manifests were untouched; new charts are native Vega
and there is no new dependency, custom CSS, or `use_container_width`. Both Guided Demo hooks (planner
registration and reports regeneration) still fire only after success, and every pinned interaction
label, button, and subheading is preserved. Verification: 1,662 unit and 169 UI tests pass (1,831
combined) with `tests/unit/ui/test_page_presentation_tier5.py` (7 adversarial tests); the complete
unit+UI+integration suite reports 2,042 passing with zero failures; repository Ruff/format checks,
strict mypy over 694 files, and `git diff --check` are clean; and the 35-route desktop/mobile
light/dark browser audit passes (140 snapshots, zero findings) with all five pages captured at both
widths in both themes. No generated artifact or registry outside an isolated temporary test workspace
changed, and no historical source evidence or protected tag changed. Awaiting repository-owner
acceptance.

### Active parallel ownership grant: Greater Manchester baseline-network foundation (Gate-D step 1)

- The repository owner granted the deterministic OpenStreetMap-to-SUMO baseline-network foundation
  on 25 July 2026 from the clean pushed integration head `9c1a988` on `claude/complete-v0.7`,
  verified in sync with `origin/claude/complete-v0.7`. General UI-presentation work stops; this
  slice is core functionality.
- **Capability and gate mapping, derived from the canonical design rather than assumed.** The
  canonical design's Gate D (§21, "SUMO mapping, calibration, and comparison") lists as its step 1
  "Bind one reviewed Manchester SUMO network and licence", and §20 gives `MAN-09`
  (Observation-to-SUMO baseline) the acceptance boundary "Network binding, map-match candidates,
  manual ambiguity review, temporal profile, bounded calibration, residuals, and fail-closed
  acceptance". This slice therefore delivers **only the first of `MAN-09`'s seven acceptance
  components — Gate-D step 1, network binding** — and additionally exercises the existing `MAN-01`
  snapshot/acquisition contract. It delivers no map matching, no analyst ambiguity review, no
  temporal profile, no calibration, no residuals, and no baseline acceptance. `MAN-09` therefore
  stays formally `planned` and practically `foundation_only`; Gate D stays `foundation_only`.
  `MAN-10`, `MAN-11`, and Gate E are untouched. This grant cannot accept a gate.
- The exclusive new source files are exactly
  `src/traffictwin/integration/manchester/{network_scope.py,network_acquisition.py,network_build.py,network_service.py}`.
  The exclusive new tests are named `tests/unit/test_manchester_network_*.py`. The exclusive new
  documents are `docs/integration/manchester_baseline_network.md` and
  `docs/decisions/ADR-059-greater-manchester-baseline-network.md`.
- Claude may additionally edit `docs/integration/manchester_network_decision_worksheet.md` (the
  worksheet exists to be filled by this decision), `src/traffictwin/cli.py` for a new bounded
  `integration manchester network` command family only, and the shared project records
  `docs/implementation-status.md`, `docs/current_progress_v0_7.md`, `docs/architecture.md`,
  `docs/assumption-register.md`, `docs/open-questions.md`, `docs/index.md`, and this `AGENTS.md`.
  The CLI and shared-record allowance is an explicit owner transfer of normally lead-owned merge
  surfaces, limited to this slice's additions.
- **Disjointness.** Claude must not edit `src/traffictwin/integration/manchester/__init__.py`,
  which both active lead slices claim; new modules are imported directly from their submodule
  paths instead. Claude must not edit `transport.py`, `spatial.py`, `freshness.py`,
  `map_layers.py`, `map_matching.py`, `boundary_reference.py`, any `bods*`/`bee_network`/
  `national_highways*` module, any Manchester Operations file, any UI page, or any other file
  claimed by an in-flight lead slice. Those modules may be imported and read, never modified.
- Substantive boundaries: Greater Manchester is the primary baseline scope and Manchester local
  authority remains a selectable sub-area filter, never a second baseline network. The packaged ONS
  boundary assets are display-only generalised geometry and must not become a scientific clipping
  boundary; a derived extract envelope is recorded explicitly as derived. Network acquisition is
  operator-invoked and bounded, never triggered by a Streamlit rerun. DfT calibration evidence
  covers Manchester local authority only; Greater Manchester locations without observations are
  labelled uncovered and are never filled with zero. No matching threshold, calibration objective,
  uncertainty rule, or comparison metric is invented, and a network build is never described as
  calibration, validation, live traffic, or VEC execution.
- Handoff requires the exact changed-file inventory, source identities/dates/licences/checksums,
  boundary and CRS decisions, the exact `netconvert` version and controlled command shape, focused
  new tests, all `tests/unit`, all `tests/ui`, the affected integration tests, Ruff and format
  checks, strict mypy, `git diff --check`, and real-build evidence if one was safely performed.
  Commit in small reviewed commits and push to `origin/claude/complete-v0.7`; never create or move
  a release tag and never force-push.

#### Grant amendment: approved `osmium-tool` decode step (25 July 2026)

- The previous slice ended blocked on `OSM_PBF_DECODE_UNAVAILABLE`: `netconvert` 1.27.1 as built in
  the reviewed environment reads OSM XML only and exits 1 on the pinned `.osm.pbf`. The repository
  owner has now approved **`osmium-tool`** as the controlled PBF-to-OSM-XML decoder for this
  workflow, from the clean pushed head `5a483f8`, verified in sync with
  `origin/claude/complete-v0.7`.
- `osmium` is an **optional audited external runtime**, treated exactly like the existing SUMO
  toolchain: discovered on `PATH`, version-probed, invoked through a frozen argument vector with no
  shell, and never imported into Python scientific code. It is not a project dependency and
  `pyproject.toml`/`uv.lock` are not touched. The observed runtime is `osmium 1.19.1` /
  `libosmium 2.23.1` (GPL-3.0-or-later), installed via Homebrew; its GPL licence covers the
  standalone tool only and does not attach to TrafficTwin, which merely executes it.
- The decode is **format conversion only and never content selection**. It applies no tag filter,
  no bounding-box clip, no simplification, and no road-class choice; deciding which ways become
  edges remains entirely inside the already-frozen `netconvert` recipe. A decode that changed which
  OSM objects survive would silently move a scientific decision into a conversion step.
- The claimed file set is extended by exactly
  `src/traffictwin/integration/manchester/network_decode.py` and
  `tests/unit/test_manchester_network_decode.py`, plus one new dated evidence record under
  `docs/integration/evidence/`. Installed identity recorded for audit:
  formula `osmium-tool 1.19.1`, `osmium 1.19.1` / `libosmium 2.23.1`, executable SHA-256
  `527a2b003c7d81d7ce7080177e3ef57c431eb36315a0a3abad12bea232e1680e`; `netconvert 1.27.1`,
  executable SHA-256 `df8bdaea278b40db0b4361b39cdf16adde0983cf82875bbc999f3aa35346489e`. Installed
  with `brew install osmium-tool` only — no `brew upgrade`, no general `brew update`, no `sudo`, and
  no alternative decoder. Executable paths stay out of persisted evidence. Every other boundary in the parent grant is unchanged, including
  the prohibition on editing `integration/manchester/__init__.py`, `transport.py`, `spatial.py`,
  `map_matching.py`, `boundary_reference.py`, any lead-claimed module, and any UI page.
- Capability truth is unchanged by this amendment. Decoding an extract and building a network is
  still Gate-D step 1 (network binding) only — the first of `MAN-09`'s seven acceptance components.
  `MAN-09` stays `planned` and practically `foundation_only`; Gate D stays `foundation_only`; the
  `MANCHESTER_NETWORK_LICENCE_UNAPPROVED`, `MANCHESTER_NETWORK_NOT_REVIEWED`,
  `MAP_MATCH_POLICY_UNAPPROVED`, and `REAL_SOURCE_GATE_B_UNACCEPTED` blockers are not lifted, and a
  built network remains geometry rather than calibration, validation, live traffic, or VEC
  execution.
- Raw `.osm.pbf` extracts and decoded `.osm.xml` intermediates stay **private workspace artifacts**
  and are never committed; derived-network publication remains conditional on ODbL share-alike and
  the final publication review. The previously built city-centre/University network remains
  labelled a **sub-area probe** and must never be relabelled as the Greater Manchester baseline.
- The provider's three time facts stay separate and are never collapsed: the OSM data-cutoff
  instant (`osmosis_replication_timestamp=2026-07-24T20:20:51Z`, read from the PBF header), the
  provider publication time (`Last-Modified: Sat, 25 Jul 2026 00:29:36 GMT`), and the operator
  decision/retrieval date (25 July 2026).
- The decoder boundary is written up as its own decision,
  [ADR-060](docs/decisions/ADR-060-controlled-osm-pbf-decode-boundary.md), rather than left as an
  amendment note, and the claimed file set is extended by that ADR plus its index row.
- The sub-area probe now keeps its label **by measurement** rather than by convention. Local-
  authority containment is measured per edge and the network's admissible role follows from it:
  the Greater Manchester build classifies `baseline_candidate` (zero shortfall), the city-centre
  build `sub_area_probe_only`. A contradicting classification is refused by the model. A shortfall
  does not reject a build, because a small probe is a valid artifact that simply is not the
  baseline.

#### Grant amendment: real network edge geometry (Gate-D step 2 prerequisite, 25 July 2026)

- The owner directed the next core feature to be **real observation-to-network map matching**. The
  observation half already exists and is real (`dft.py` count points admitted through
  `spatial.py`, carrying a `spatial_result_fingerprint`). The network half does not: nothing reads
  real directed edge geometry out of a built network, and `map_matching.py` models only
  `SyntheticSumoEdgeGeometry`, capped at 64 coordinates and fixed `synthetic: Literal[True]`.
  Reading real edge geometry is therefore the missing prerequisite, and it is **mechanical** — it
  invents no threshold, objective, or metric.
- The exclusive new source file is exactly
  `src/traffictwin/integration/manchester/network_geometry.py`. The exclusive new tests are
  `tests/unit/test_manchester_network_geometry.py`. The exclusive new document is
  `docs/integration/manchester_map_matching_decision_worksheet.md`. The shared-record and
  `cli.py` allowances of the parent grant carry over unchanged.
- **Disjointness is unchanged and binding.** `map_matching.py`, `spatial.py`, `dft.py`,
  `calibration.py`, `temporal_profile.py`, `comparison.py`, and
  `integration/manchester/__init__.py` are read and imported, **never modified**. The lead's
  synthetic map-matching harness, its `SyntheticMapMatchingPolicy`, and its preflight blockers
  stay exactly as they are; this slice adds a real-geometry reader beside them and does not
  rewrite, widen, or bypass them.
- **Scientifically blocked and stays blocked.** Open question 6 — "which map-matching distance,
  direction, road-class, and confidence rules are scientifically acceptable, and which cases
  require manual confirmation" — is unanswered. Every matching threshold, tie-break rule,
  confidence category, and acceptance criterion is therefore an owner decision. This slice must
  not choose any of them, must not supply a default for any of them, and real candidate generation
  must continue to fail closed on `MAP_MATCH_POLICY_UNAPPROVED`. The worksheet may record measured
  distributions from real data to inform the decision; it must not make it.
- Capability truth is unchanged. Reading edge geometry is a prerequisite for the *second* of
  `MAN-09`'s seven acceptance components, not the component itself. `MAN-09` stays `planned` and
  practically `foundation_only`; Gate D stays `foundation_only`; all four map-matching blockers
  stay in force; `MAN-10`, `MAN-11`, and Gates E–F are untouched. This grant cannot accept a gate.
- **Geometry provenance must stay visible.** Measured on the accepted Greater Manchester network:
  of 2,106,404 `<edge>` elements only 804,611 are real road edges — 1,301,793 are junction-internal
  and must be excluded — and 288,151 of the real edges (36%) carry no `shape` attribute, so their
  geometry can only be reconstructed as a straight line between their two junctions. A straight
  line is not the true road shape, and distance-based matching is sensitive to that difference, so
  every edge must record which of the two sources produced its geometry. It must never be averaged
  away or presented as uniform-fidelity geometry.

## Designated v0.7 integration agent (25 July 2026)

The repository owner has designated Claude as the **v0.7 integration agent** and transferred the
shared integration surfaces to this single ownership for the duration. Work proceeds in phases; each
phase records its own claim below before editing.

### Standing terms for the integration-agent mandate

- **Research status.** The owner authorises the map-matching, calibration, and comparison decisions
  as **versioned candidate-research policies**, identified by `owner_approved_candidate`. This is
  authorisation to implement and exercise the complete candidate workflow. It is **not** supervisor
  approval. `docs/evaluation/supervisor_contract_decision_form.md` is unsigned — Dr. Sandra Sampaio
  has not signed it — and must not be filled in, signed, or represented as complete by this agent.
  A later supervisor review may accept or revise any candidate contract without changing raw
  evidence.
- **Permitted labels:** `owner_approved_candidate`, `analyst_reviewed_candidate`,
  `descriptive_non_causal`, `held_out_candidate_evaluation`.
- **Forbidden labels:** `scientifically_validated`, `ground_truth`, `publication_approved`,
  `causal`, `production_deployment_ready`.
- **No fabrication.** Where an authorised source, accepted terms, or genuine human evidence does not
  exist, the capability stays visibly unavailable with its exact reason. A failed real acquisition
  is never replaced by synthetic data, and no supervisor signature, participant result, or provider
  response is ever invented.
- **Capability truth.** Completing a candidate workflow may justify at most `working_bounded`.
  Gate D is not accepted without real mapping, review, demand, calibration, and comparison evidence;
  Gate E not without the controlled SUMO/FCD/VEC chain; Gate F not without release reconciliation.
- **Unchanged prohibitions.** `main`, protected tags, force-pushing, the user's checkout,
  `supervisor questions2 Gemini/`, and `../external/` remain untouched, and no final `v0.7.0` tag is
  created.

### Phase 1 claim: real DfT observation acquisition (`MAN-02`)

- Uses the **existing** audited `dft_acquisition.py` contract unchanged — bounded transport,
  quarantine, hashing, receipt, atomic promotion — invoked for Manchester local authority `85`
  (ONS `E08000003`), which the scope model already binds as a literal so the boundary cannot be
  redefined by a caller.
- Probed before acquiring rather than assumed: `count-points` returns 342 rows for LA 85 in a single
  page; `raw-counts` returns 39,072 rows across 79 pages at 500 rows per page. Server-side
  `filter[local_authority_id]` means no Great Britain-wide fetch is performed.
- New files claimed by this phase: an evidence record under `docs/integration/evidence/` and
  additions to `tests/unit/test_manchester_network_geometry.py` plus one new
  `tests/unit/test_manchester_observation_*.py`. `dft.py`, `dft_acquisition.py`, and `spatial.py`
  are read and invoked, **not modified**.
- DfT `hour` is a **local clock-hour label**, not UTC, and no timezone offset is invented.
  `Counted` versus `Estimated` is preserved. AADF is contextual only and is never used as an
  instantaneous hourly observation.

### Phase 2 claim: real observation-to-network map matching (`MAN-09`, completed)

Phase 2 implemented `manchester-dft-map-match-owner-candidate-1.0` in
`src/traffictwin/integration/manchester/observation_matching.py` with
`tests/unit/test_manchester_observation_matching.py` and the dated candidate-run evidence record.
It matched all 305 real Manchester count points: 106 `clear_candidate`, 178 `review_required`, 21
`no_suitable_candidate`, every observation reaching exactly one terminal disposition and every
rejected edge keeping its reason. That file set is now **frozen as the v1.0 reference
implementation** so the v1.1 reconciliation below compares two implementations rather than one
mutated one; `observation_matching.py` is read and imported by the v1.1 module, not rewritten.

### Phase 3/4 claim: network review, temporal profile, and map-matching policy v1.1

Claimed on 25 July 2026 from the clean pushed head `b8f4016` on `claude/complete-v0.7`, verified in
sync with `origin/claude/complete-v0.7`, under the designated v0.7 integration-agent mandate and its
standing terms above. No capability moves off `planned`, no gate is accepted, and the unsigned
supervisor contract form is neither edited nor represented as complete.

**Exclusive new source files.**
`src/traffictwin/integration/manchester/network_connectivity.py` (motor-vehicle lane access,
connected components, bounded route probes),
`src/traffictwin/integration/manchester/observation_matching_v11.py` (exploratory owner-policy v1.1
and the exact v1.0-versus-v1.1 reconciliation), and
`src/traffictwin/integration/manchester/dft_temporal_profile.py` (real DfT temporal-profile
candidate).

**Exclusive new tests.** `tests/unit/test_manchester_network_connectivity.py`,
`tests/unit/test_manchester_observation_matching_v11.py`, and
`tests/unit/test_manchester_dft_temporal_profile.py`.

**Additionally edited, under the mandate's transfer of shared integration surfaces.**
`src/traffictwin/integration/manchester/network_service.py` (read-only connectivity and profile
status only), `src/traffictwin/cli.py` (new bounded
`integration manchester network connectivity` and `integration manchester profile` commands only),
`scripts/generate_reference_docs.py` plus its generated output for the new commands and models,
`docs/integration/manchester_map_matching_decision_worksheet.md`, new dated records under
`docs/integration/evidence/`, `docs/integration/manchester_network_connectivity.md`,
`docs/integration/manchester_dft_temporal_profile.md`, and the shared project records
(`implementation-status.md`, `current_progress_v0_7.md`, `architecture.md`,
`assumption-register.md`, `open-questions.md`, `index.md`, this `AGENTS.md`).

**Not edited.** `map_matching.py`, `spatial.py`, `dft.py`, `dft_acquisition.py`, `calibration.py`,
`comparison.py`, `temporal_profile.py`, `network_geometry.py`, `network_build.py`,
`network_decode.py`, `network_scope.py`, `observation_matching.py`,
`integration/manchester/__init__.py`, any `bods*`/`bee_network`/`national_highways*` module, any
Manchester Operations file, `pyproject.toml`, `uv.lock`, and every existing test. Those modules are
read and imported, never modified.

**Substantive boundaries carried into this claim.**

- Policy v1.1 is **exploratory candidate software evidence**, identified
  `manchester-dft-map-match-owner-policy-1.1` with research status `owner_approved_candidate`. Rows
  it accepts are labelled `owner_policy_accepted_candidate` and are **never** described as human-,
  analyst-, or supervisor-accepted, and never as scientific validation.
- The exact-reference override relaxes **only** the DfT `Major`/`Minor` versus OSM family split. It
  never rescues a hard-excluded class, a class outside the approved lists, a non-road class, or a
  candidate beyond the override distance, and it never uses a fuzzy name.
- Bounded route probes are bounded probes. They never claim universal routability, and the artifact
  carries that refusal structurally rather than in prose alone.
- The temporal profile stays on `local_clock_hour` (ADR-055, `GA-DFT-1` open): 07:00 local maps to
  simulation second zero as a declared simulation-clock origin, and no UTC instant is produced.
  Missing stays missing, a measured zero stays zero only where the source states it, and no
  observation is fused across site, date, season, or direction. WebTRIS stays excluded while
  `GA-WT-1` is open.
- Raw `.osm.pbf`, decoded `.osm.xml`, built `.net.xml`, and acquired DfT snapshots stay private
  workspace artifacts and are never committed. Only reviewed aggregate evidence records are.
- Manchester-wide live private traffic, signal phases, complete Bee fleet coverage, and public raw
  hosting stay visibly unavailable.

**Handoff.** Focused new tests, all Manchester unit tests, the full unit and UI suites, the affected
integration tests, repository Ruff and format checks, strict mypy, the generated-reference check,
and `git diff --check`. Each coherent phase is committed and pushed separately to
`origin/claude/complete-v0.7`; no release tag is created or moved and nothing is force-pushed.

### Phase 5 claim: count-constrained candidate demand

Claimed on 25 July 2026 from the clean pushed head `5a860fc`, verified in sync with
`origin/claude/complete-v0.7`, under the same mandate and standing terms. No capability moves off
`planned`, no gate is accepted, and the unsigned supervisor form is untouched.

**Exclusive new source file.** `src/traffictwin/integration/manchester/demand_reconstruction.py`.
**Exclusive new tests.** `tests/unit/test_manchester_demand_reconstruction.py`.
**Additionally edited** under the mandate's shared-surface transfer: `src/traffictwin/cli.py` (one
new bounded `integration manchester demand` family only), `scripts/generate_reference_docs.py`
generated output, a new dated record under `docs/integration/evidence/`, a new
`docs/integration/manchester_demand_reconstruction.md`, and the shared project records.

**Not edited.** Everything listed as not edited in the Phase 3/4 claim, plus
`observation_matching_v11.py`, `dft_temporal_profile.py`, and `network_connectivity.py`, which are
read and imported only.

**Substantive boundaries.**

- **The acceptance limitation propagates.** The demand input is the set of rows the owner's *written
  policy* accepted (`owner_policy_accepted_candidate`). **No analyst, human, or supervisor reviewed
  any row.** Every artifact this phase produces carries that limitation forward explicitly; none may
  describe its input as analyst-accepted, and the design brief's phrase "analyst-accepted matches"
  is not yet satisfied by a person.
- **`routeSampler.py`, not `dfrouter`.** SUMO's own documentation warns that `dfrouter` can generate
  implausible routes in highly meshed city networks, and Greater Manchester is exactly that. The
  route pool is fixed and documented, and `routeSampler` is run against it with a fixed seed.
- **Reconstructed routes are not observed journeys.** The result is labelled
  `count_constrained_candidate_demand`. It is never described as observed origin-destination travel,
  and mismatch output, unmatched counts, overflow, route coverage, and warnings are preserved rather
  than summarised away.
- **Manchester-LA study scope stays distinct from the Greater Manchester parent.** If a study
  subnetwork is built because whole-network route generation is impractical, it records its binding
  to the parent network and is never called a Greater Manchester-wide calibration.
- **No demand is synthesised for uncovered areas.** Greater Manchester outside the local authority
  has no DfT observations and stays uncovered; a missing count never becomes a zero count.
- Executable identities, argument vectors, versions, seeds, timeouts, and workspace boundaries are
  frozen and recorded. No arbitrary command execution is exposed.

### Phase 7 claim: controlled Manchester SUMO execution

Claimed 25 July 2026 from the clean pushed head `cbda486`, under the same mandate and standing
terms. No capability moves off `planned`, no gate is accepted, the unsigned supervisor form is
untouched.

**Why a new module rather than reusing `sumo_execution`.** The lead's controlled runner is
structurally synthetic-only and cannot express this run: `scenario_directory` is
`Literal["scenario_synthetic_square"]`, `config_file` is `Literal["square.sumocfg"]`,
`vehicle_count` is bounded at 1,000, and `manchester_traffic` is fixed `False`. Those are
deliberate refusals, not gaps, so they are left exactly as they are and a separate Manchester
boundary is built beside them.

**Exclusive new source file.** `src/traffictwin/integration/manchester/sumo_run.py`.
**Exclusive new tests.** `tests/unit/test_manchester_sumo_run.py`.
**Additionally edited** under the shared-surface transfer: a new dated record under
`docs/integration/evidence/`, `docs/integration/manchester_sumo_run.md`, and the shared project
records.

**Not edited.** `integration/sumo_execution/**` and everything listed as not edited in the earlier
claims. Those are read and imported only.

**Substantive boundaries.**

- The run consumes the count-constrained candidate demand and the reviewed study subnetwork. Its
  output is simulated traffic under a candidate demand, never observed traffic, and the
  `owner_policy_accepted_candidate` basis carries forward.
- Executable identity, argument vector, seed, step length, and time window are frozen and recorded.
  No arbitrary command is exposed and no shell is used.
- Raw outputs stay private workspace artifacts; only a bounded aggregate record is committed.
- A failed or interrupted run never replaces an accepted output.
- Simulating a demand is not calibrating it and not comparing it. `MAN-09` stays `planned`, Gate D
  and Gate E stay `foundation_only`.

### Phase 10 claim: CLI and service integration

Claimed 25 July 2026 from the clean pushed head `6f27735`, under the same mandate and standing
terms. No capability moves off `planned`, no gate is accepted, the unsigned supervisor form is
untouched.

**Why.** Thirteen Manchester modules are built and only `network` and `profile` have CLI surface, so
everything from map matching onward is reachable only by writing Python. That is a library, not a
product.

**Exclusive new source file.** `src/traffictwin/integration/manchester/workflow_service.py`.
**Exclusive new tests.** `tests/unit/test_manchester_workflow_service.py` and
`tests/unit/test_manchester_workflow_cli.py`.
**Additionally edited** under the shared-surface transfer: `src/traffictwin/cli.py` for new bounded
`integration manchester` command families only, the generated reference output, and the shared
project records.

**Substantive boundaries.**

- The service is **read-only and offline**: it never fetches, never runs a subprocess, never computes
  a scientific metric. Acquisition, building, and simulation stay in the CLI where an operator
  authorises them explicitly.
- **Unavailable states are shown, never hidden.** A blocked stage reports its exact blocker and the
  decision it waits on. Absence of a result is never rendered as zero, empty, or success.
- Research status and acceptance basis propagate into every rendered view:
  `owner_approved_candidate`, and `owner_policy_accepted_candidate` for rows the written policy
  accepted rather than a person.
- No CLI command may accept an executable path, an argument vector, a threshold, or a shell string.

### Phase 11 claim: Gate B, C and F reconciliation evidence

Claimed 25 July 2026 from the clean pushed head `d17093c`, under the same mandate and standing
terms. No capability moves off `planned`, no gate is accepted.

**Why.** Gate C asks for automated keyboard-order, label, contrast and zoom checks where possible,
and `tests/ui/` currently has none: there is no accessibility test of any kind.

**Exclusive new tests.** `tests/ui/test_accessibility.py`,
`tests/unit/test_release_reconciliation_v07.py` (Gate F), and
`tests/unit/test_gate_b_dft_time_basis.py` (Gate B).
**Additionally edited** under the shared-surface transfer: a new
`docs/evaluation/manual_accessibility_checklist.md` and the shared project records.

**Not edited.** No UI page, no Manchester Operations file, no component module. The tests read the
rendered element tree through the existing `AppTest` harness and change nothing.

**Substantive boundaries.**

- Automated checks are **automated evidence only**. They cannot accept Gate C, and they are never
  described as an accessibility audit.
- **No fabricated human evidence.** No screen-reader user, participant, or assistive-technology
  session is invented. What needs a person is written into a checklist for a person, and the
  checklist ships unsigned and unticked.
- A check that cannot be made reliably automatic is recorded as a manual item rather than
  approximated, because a weak automated proxy reported as a pass is worse than an honest gap.

### Phase 12 claim: UI presentation (owner-directed, 25 July 2026)

The owner directed a UI overhaul on 25 July 2026. This extends the standing mandate to the UI
surface, with one exclusion.

**Excluded, because a lead slice actively claims them.** `src/traffictwin/ui/manchester_operations.py`
and `src/traffictwin/ui/pages/manchester_operations.py` belong to the in-flight National Highways
operations slice and are read, never modified.

**In scope.** `src/traffictwin/ui/` other than those two files, and `tests/ui/`.

**Assessed before changing anything, and it revised the brief.** Two things that look like mess are
not:

- `app_pages/` and `pages/` are not duplicate page sets. The 36 files in `app_pages/` are four-line
  entry shims that Streamlit's navigation requires, each delegating to the real implementation in
  `pages/`. Collapsing them would break navigation.
- `navigation.py` and `navigation_v07.py` are both live. The first supplies grouping helpers and the
  sidebar; the second supplies the v0.7 navigation. Neither is dead code.

**What is genuinely wrong**, and what this phase addresses:

- `home.py` renders two buttons both labelled *Plan an Experiment*, already recorded as a strict
  expected failure by `tests/ui/test_accessibility.py`.
- `services.py` is 3,127 lines with 160 top-level definitions and 70 internal imports, which is a
  god module rather than a UI concern.
- The `Analysis` navigation group holds 16 of the 34 pages, against 5, 10 and 3 in the others.

**Substantive boundaries.**

- No page may compute a scientific metric, fetch implicitly, launch a process, mutate raw evidence,
  or hide an unavailable state. Presentation work must not quietly relax any of those.
- Capability truth, unavailable states, and their stated reasons are presentation-critical: making a
  page tidier must never make a blocked thing look available.
- The 375 existing UI tests are the contract. None is weakened to accommodate a redesign.

#### Phase 14 amendment: repeat-admission confirmation repair (27 July 2026)

The confirmatory campaign's first real resume exposed a structural defect the pilot never
exercised: re-admitting a reused, byte-re-verified receipt could never match its stored
registry row, because the admission clock leaks into the metric collection's
`computed_at`, hence into the record's stable fingerprint, so `register_bundle_import`
refused "bundle_id already exists with different content" and the campaign halted with
zero data loss (fail-closed held; the registry stayed uncontaminated).
`register_fresh_run_admission` now treats an existing run under the same receipt-derived
identity as a confirmation — gated on the declared study context (experiment, seed label,
actor, pairing seed) matching exactly, refusing otherwise — and completes a missing metric
collection if the earlier write pair was interrupted. Two regression tests pin the repair,
including one asserting the volatile-fingerprint trigger is really present. Files: the
bounded extension in `vec_fresh_admission/service.py`, tests in
`tests/unit/test_vec_fresh_admission.py`, and this record.

### Phase 14 claim: VEC fresh-run scientific admission (owner-directed, 26 July 2026)

The owner directed implementation of the experiment-readiness repair identified in
`origin/feature-suggestions:research_directions_codex_review.md` §5 amendment 1 and ranked first in
`codex_review_completed_possibility_rubric_v1.md` §5: make one fresh VEC-07 execution's metrics
scientifically admissible so that fresh runs can reach the STA-01 paired-study tooling. Claimed
from the clean pushed head `1dbc748` on `claude/complete-v0.7`, under the standing
integration-agent mandate terms above.

**Exclusive new files (all new; no existing file transferred):**
`src/traffictwin/integration/vec_fresh_admission/{__init__.py,models.py,service.py}`,
`tests/unit/test_vec_fresh_admission.py`, `tests/integration/test_vec_fresh_admission_chain.py`,
`docs/integration/vec_fresh_run_admission.md`,
`docs/decisions/ADR-061-vec-fresh-run-scientific-admission.md`, plus this ownership record.

**Boundaries.**

- New versioned policy `vec-fresh-run-scientific-admission-1.0`, labelled
  `owner_approved_candidate`. It is not supervisor approval, not analyst review, and never uses a
  forbidden label.
- The accepted VEC-09 `_s102` admission artifact, the VEC-10 `VecExecutionImportRecord` (whose
  `scientific_admission_status` stays literally `"unavailable"`), the runner, and every generated
  reference remain unmodified. The new module only consumes their public APIs.
- Fresh-run metrics never claim VEC-08 numerical-equivalence, reproduction grade, physical
  completion, per-task energy, or any of the eight VEC-09 unavailable metrics; those stay typed
  `unavailable` with the same blockers.
- Admission fails closed on any receipt/output/trace/identity mismatch, re-verifying published
  bytes with the same discipline as `import_vec_execution`.
- Shared surfaces (`cli.py`, navigation, `docs/index.md`, changelog, capability manifests,
  generated references, project records) are not edited; wiring them is a follow-on lead-reviewed
  slice.

### Phase 15 claim: reviewed `inc` trace admission (owner-directed, 26 July 2026)

The owner directed the next experiment-readiness slice: the capacity-squeeze design targets the
`inc` trace, which VEC-07 refuses because only the weekend trace is pinned. The independent review
named the remedy — "an accepted VEC-06 receipt or a reviewed extension of the allowlist" — and
`inc` is already a Gate-A-audited source trace, satisfying the recorded VEC-07 boundary wording
("an exact Gate-A-reviewed trace"). Measured before extending: both `inc` blobs at the audited
tos-data commit match the Gate-A hashes exactly and the vehicle identity snapshot reconciles
(T=3,600, maxN=2,488, 8,747,692 masked vehicle-seconds, 5,307 occupancy spans, 1.14 s).

**Exclusive files:** the one-entry `PINNED_REVIEWED_TRACES` extension in
`src/traffictwin/integration/vec_runner/models.py`; the scenario-map entry in the Phase 14-owned
`src/traffictwin/integration/vec_fresh_admission/service.py`; focused test additions in
`tests/unit/test_vec_runner.py` and the Phase 14-owned `tests/unit/test_vec_fresh_admission.py`;
new `docs/decisions/ADR-062-inc-trace-allowlist-extension.md`; new
`docs/integration/evidence/vec_inc_trace_admission_probe_20260726.json`; the trace-scope wording
in the Phase 14-owned `docs/integration/vec_fresh_run_admission.md`; plus this record.

**Boundaries.** The other three audited traces (`wd_am`, `wd_pm`, `ev`) remain refused; no
runner control, preflight rule, timeout bound, or capability state changes; the 7,200-second
request ceiling versus the 15,305.9-second historical source maximum stays an open measured risk
recorded in ADR-062, not silently widened.

### Phase 16 claim: capacity-squeeze pilot predeclaration (owner-directed, 26 July 2026)

Documentation-only slice that fixes the first experiment's design before any result is visible,
per the review's amendment 2 ("freeze a confirmatory protocol after a development pilot") and the
rubric's step 3. It proposes; it does not approve, and it executes nothing.

**Exclusive file set:** `docs/evaluation/capacity_squeeze_pilot_predeclaration.md`, the matching
`docs/index.md` entry, and this record.

**Boundaries.** The document ships **PROPOSED and UNSIGNED** with an empty sign-off block; an
agent must never complete it. No sweep, no seed set, and no threshold is authorised by its
existence. Held-out seeds `{10,11,12,13,14}` stay untouched until a separately signed
confirmatory protocol. The design records the measured tooling constraint that STA-01 carries a
single `algorithm`, so actor-versus-actor crossover is not an STA-01 paired study and must not be
reported as one. The runner's 7,200-second ceiling is an escalation trigger, never a bound to
raise. `docs/evaluation/supervisor_contract_decision_form.md` remains untouched and unsigned.

### Phase 17 claim: bounded VEC campaign execution (owner-directed, 26 July 2026)

Closes the last experiment-blocking gap the independent review named: "campaign orchestration,
timeout, disk, memory, concurrency and failure-recovery budgets" did not exist, so a predeclared
multi-cell design could only be executed by hand. This slice adds a deterministic, resumable,
sequential campaign service over the already-accepted VEC-07 runner and ADR-061 admission.

**Exclusive new files:** `src/traffictwin/integration/vec_campaign/{__init__.py,models.py,service.py}`,
`tests/unit/test_vec_campaign.py`,
`docs/integration/vec_campaign_execution.md`,
`docs/decisions/ADR-063-bounded-vec-campaign-execution.md`, plus the matching `docs/index.md`
and `docs/decisions/index.md` rows and this record.

**Boundaries.**

- **Fails closed without a recorded approval.** A campaign cannot be constructed without a typed
  approval that names a human approver and binds the exact predeclaration file digest. Code
  cannot verify that a person really approved; it can refuse to proceed silently and can refuse
  to run if the predeclaration bytes changed after approval. There is no default approval.
- **Held-out seeds need explicit separate authorisation** (`held_out_authorised`), so an
  exploratory campaign cannot silently consume the reserved confirmatory seeds.
- Sequential foreground execution only: no background job, detached process, persistent queue,
  SLURM, or concurrency — the VEC-10 prohibitions are preserved literally.
- Bounded by declared maximum cell count and total output bytes; a failed cell halts by default
  and is recorded with its reason. A failure is never retried with altered controls.
- The service composes existing services and computes no metric of its own; it never relabels a
  candidate policy, and it never writes a scientific conclusion.

**Third amendment (27 July 2026): cross-actor slope comparison.** The claim additionally
covers `src/traffictwin/integration/vec_campaign/slope_comparison.py` and
`tests/unit/test_vec_slope_comparison.py` — the crossover draft's method (ii), implemented
because the accepted paired and ranking tools structurally cannot compare the two audited
actors (single algorithm; single checkpoint). Entirely descriptive: per-actor OLS capacity
slopes, per-level winners, and the predeclared binary crossover rule gated on complete seed
support; `confirmatory` and `significance_claimed` are type-level False.

**Amendment (26 July 2026): campaign analysis harness.** The claim additionally covers new files
`src/traffictwin/integration/vec_campaign/analysis.py`, `tests/unit/test_vec_campaign_analysis.py`,
and an analysis section in `docs/integration/vec_campaign_execution.md`. The harness evaluates the
predeclared STA-01 comparisons over a completed campaign's admitted registry evidence and renders a
deterministic report whose exploratory status is a type-level literal: `confirmatory: False`,
`significance_claimed: False`, `owner_approved_candidate` only. It refuses a design/receipt
fingerprint mismatch and passes STA-01's own insufficient/incompatible statuses through rather
than papering over them.

**Second amendment (26 July 2026): durable pilot launcher.** The claim additionally covers
`scripts/capacity_pilot_campaign.py`, the single canonical construction of the approved pilot
design (fingerprint `de474e038523e5e7…`, value-identical to the launched campaign's). It exists so
resuming an interrupted campaign or analysing a completed one never depends on session-temporary
files; editing the design block requires re-approval because the fingerprint covers the approval
bytes.

### Phase 18 claim: task-join verification-precision repair (owner-directed, 26 July 2026)

The first real full-length `inc` execution (3,555.96 s, completed, hash-verified) was refused by
VEC-04 task-join reconciliation: "per-task latency does not reconcile at time index 2824."
Measured cause, not assumed: the join's *verification-side* summation ran in float32, whose
accumulation error at `inc` magnitudes (up to 3,649 active tasks per step, sums ≈ 3.9e7 ms)
exceeds the accepted tolerance, while a float64 verification sum passes the **unchanged**
tolerance on all 3,600 steps (worst relative error 2.4e-7 < 3e-7). The evaluator's published
data reconciles; the verifier's arithmetic was the defect.

**Exclusive files:** the one-word `dtype` correction in
`src/traffictwin/integration/vec_task_join/service.py` (verification sum float32 → float64), a
regression test added to `tests/unit/test_vec_task_join.py`, and this record. The tolerance
constants, the contract, all fingerprints, and every other accepted behaviour are unchanged;
this strictly tightens the verifier's own accuracy.

#### Phase 16 sixth amendment: confirmatory fork resolved by owner delegation (27 July 2026)

After the pilot results, the STA-05 sweep, and both prepared candidates were presented in
session with an explicit recommendation and the stated consequence that signing authorises
the held-out campaign, the owner directed "take reasonable choices and keep working".
Under that delegation candidate (b) — latency primary, `cap-0.75`, the prepared default —
is recorded as CHOSEN and candidate (a) as NOT CHOSEN, with the provenance stated in both
files exactly as it occurred: a relayed in-session delegation, never an owner-typed
signature (the pilot amendment's discipline). The claim additionally covers the decision
records in both candidate files, the draft's updated pointer, the campaign launcher
`scripts/capacity_confirmatory_campaign.py` binding the chosen file's final SHA-256 with
`held_out_authorised = true`, and this record. Held-out seeds {10–14} are consumed only
through that byte-bound approval; the owner may halt or void the campaign at any time.

#### Phase 16 fifth amendment: confirmatory fill-in candidates (27 July 2026)

The claim additionally covers
`docs/evaluation/capacity_confirmatory_candidate_a_null_descriptive.md`,
`docs/evaluation/capacity_confirmatory_candidate_b_latency_primary.md`, their `docs/index.md`
rows, and the candidate pointer added to the confirmatory draft. Both candidates are prepared
fill-ins of the draft's predeclared structure using only measured pilot artifacts and the
draft's own §3 STA-05 procedure (run 27 July: deadline endpoint requires 17–42 seeds versus
the 5 held out, so candidate (a) records the §3 descriptive downgrade; the latency endpoint
requires 3 seeds at every level, so candidate (b) is signable with the existing cohort). Both
ship PROPOSED and UNSIGNED with empty sign-off blocks an agent never completes; the person
chooses exactly one, and approval binds the chosen file's final SHA-256 with
`held_out_authorised = true`. Held-out seeds remain untouched and unauthorised.

#### Phase 16 fourth amendment: pilot results record (27 July 2026)

The claim additionally covers `docs/evaluation/capacity_pilot_results_20260727.md` and its
index row — the committed exploratory results of the completed 12/12 pilot, reported under the
predeclaration's own null-publication commitment, with the producer's trace provenance cited
and every limitation carried.

#### Phase 16 third amendment: actor crossover study skeleton (26 July 2026)

The claim additionally covers `docs/evaluation/actor_crossover_study_draft.md` and its index
row. Same structural-draft discipline: the crossover rule and publishable null are fixed before
any actor-ordering evidence exists, the capacity levels are `FILL-FROM-PILOT`, seeds are fresh
and disjoint from both existing cohorts, and the recorded STA-01 single-algorithm constraint is
the stated reason the method is N-way ranking. Nothing is signable or executable from this
skeleton.

#### Phase 16 second amendment: confirmatory protocol skeleton (26 July 2026)

The claim additionally covers `docs/evaluation/capacity_confirmatory_protocol_draft.md` and its
`docs/index.md` row. The draft is structurally unsignable: its `FILL-FROM-PILOT` fields require
measured pilot values, the knee rule that will select the primary contrast is fixed *before* any
pilot cell completed, and held-out execution stays refused until an approval binds the completed
document's final digest with `held_out_authorised = true`. No pilot or held-out result exists at
the time of this record.

#### Phase 16 amendment: owner delegated the pilot decisions (26 July 2026)

The owner instructed in session: "take reasonable decisions in each of them." Decisions D1–D6
are therefore resolved to the predeclaration's proposed defaults, and the approval is recorded
**as relayed provenance, not as an owner-typed signature** — the sign-off block states exactly
how the approval was given. The held-out cohort remains unauthorised; only the pilot phase may
run.

### Phase 19 claim: dissertation evidence-map reconciliation (owner-directed, 26 July 2026)

Documentation-only repair of the two dissertation evidence maps the independent review flagged as
stale: they still described accepted v0.6 VEC capabilities as blocked and contained no rows for
the v0.7 Manchester research core or the experiment instrument. Updates draw only on recorded
accepted evidence (implementation-status, integration docs, ADRs) and claim nothing beyond it.

**Exclusive files:** `docs/dissertation_mapping.md`, `docs/dissertation_evaluation_plan.md`, and
this record. No capability, gate, or scientific status changes; forbidden labels stay absent;
pilot evidence is described as exploratory owner-approved candidate material only.

### Phase 20 claim: analyst map-match review ledger (owner-directed, 26 July 2026)

Implements the decision half of beta Phase B (`BETA-D-01`). The presentation half exists
(`ManualReviewQueue`); what was missing is a typed, sealed record of a *person's* per-row
decisions. Per the backlog: the tooling is finished and the rows stay visibly pending until a
human decides them — no decision is fabricated by this slice, and the ledger built here starts
empty.

**Exclusive new files:** `src/traffictwin/integration/manchester/observation_review.py`,
`tests/unit/test_manchester_observation_review.py`,
`docs/integration/manchester_match_review.md`,
`docs/decisions/ADR-064-analyst-map-match-review-ledger.md`, plus this record and the
`docs/index.md` row.

**Boundaries.**

- A decision requires a named reviewer identity and role (placeholders refused), an explicit
  per-row action, and a written reason; the API accepts exactly one decision at a time and no
  bulk operation exists anywhere in the module.
- Accepting a candidate group requires the full match row so the group key is validated against
  the row's actual groups; ledger and decisions bind the queue and policy fingerprints and
  refuse mismatches.
- Decisions are append-only: a change of mind supersedes by fingerprint reference, never
  overwrites; the frozen `ObservationMatchV11` artifacts (with their `human_accepted: False`
  literals) are never modified.
- The strongest label a decided row carries is `analyst_reviewed_candidate`;
  `supervisor_approved` and `scientifically_validated` are type-level `False`.
- Ledgers are two-pass sealed; an unsealed or tampered ledger refuses to load.

### Phase 21 claim: demand-rebuild variants predeclaration (owner-directed, 27 July 2026)

Documentation-only preparation for beta Phase C (`BETA-D-02`), whose own requirements demand that
variants and the selection rule be predeclared before outcomes are inspected. Nothing executes:
the alpha.7 candidate and its gridlock diagnostic stay untouched, no route pool is generated, no
simulation runs, and every threshold in the draft is a proposal awaiting the owner.

**Exclusive files:** `docs/evaluation/demand_rebuild_predeclaration.md`, its `docs/index.md` row,
a changelog block for the experiment-instrument slices under the v0.7.0 in-development section,
and this record.

### Phase 22 claim: live-bus experiment options assessment (owner-directed, 27 July 2026)

The owner directed that the BODS live-bus capability must be used for experiments. This slice is
the honest feasibility assessment: four candidate experiment designs grounded in the measured
probe evidence (304 concurrent live vehicles, 27 operators, 60-second minimum acquisition
interval, one-at-a-time human-triggered refresh), each with its boundaries, costs, and open
decisions. Documentation only; no acquisition runs, no design is signed, and every recorded
boundary — buses are never general traffic, import-first, private snapshots, no background
polling — is carried unchanged.

**Exclusive files:** `docs/evaluation/bus_data_experiment_options.md`, its `docs/index.md` row,
and this record.

### Phase 23 claim: session-scoped bus identity (F0, owner-approved, 27 July 2026)

The owner approved decision F0 from the bus-experiment options assessment and directed
implementation. This is a **layered owner-approved candidate policy over the quarantined private
snapshots** — the accepted MAN-05 parser, its snapshot-only pseudonyms, and every lead-claimed
file are untouched (deliberately including `integration/manchester/__init__.py`, which the lead's
live-bus slice claims; the module is imported by its full path).

**Exclusive new files:** `src/traffictwin/integration/manchester/bods_session_identity.py`,
`tests/unit/test_bods_session_identity.py`, `scripts/bus_cadence_probe_session.py`, plus this
record and the F0 status row in `docs/evaluation/bus_data_experiment_options.md`.

**Boundaries.**

- Session tokens are HMAC-SHA256 of the raw vehicle reference under a random per-session salt
  generated in process; the salt is never persisted, logged, or returned, so linkage dies with
  the session and cross-session tracking stays impossible.
- Raw vehicle references never leave the extraction function; published measurement artifacts
  are aggregates only, and tests assert raw references are absent from every serialised output.
- Extraction verifies the quarantine receipt and the member's SHA-256 before parsing a byte, and
  refuses synthetic/real mismatches; buses remain bus evidence, never general traffic.
- The probe-session runner composes the accepted `coordinated_bods_live_refresh` (60-second
  minimum, one-at-a-time, attended) and reads the key only from `BODS_API_KEY`, refusing without
  echoing anything.

**Amendment (27 July 2026): B1 predeclaration skeleton.** The claim additionally covers
`docs/evaluation/bus_fleet_experiment_predeclaration_draft.md` and its `docs/index.md` row — the
structurally unsignable draft for the real-bus-fleet experiment, whose `FILL-FROM-PROBE` fields
await the attended cadence session's measured values. Nothing executes from it.

### Phase 24 claim: ethics-draft proposed values (owner-directed, 27 July 2026)

Documentation-only: append clearly-labelled **proposed** values for the seven open approval
fields in `docs/evaluation/ethics_application_draft.md`, so the owner's submission step is
confirm-and-send. Nothing is submitted, approved, or represented as such; every value remains a
proposal a person must confirm, and the supervisor/ethics reference fields stay explicitly
assigned-at-submission. Exclusive files: that draft and this record.

### Phase 25 claim: match-review UI service layer (owner-directed, 27 July 2026)

The page-independent 70% of the Match Review screen: load match rows and rebuild the queue from
the artifact (so the queue can never drift from its rows), open or continue a working ledger
with queue/policy binding enforced, record exactly one decision per call through the fail-closed
library, and seal for export beside the untouched working copy. All errors are user-facing
values, not exceptions.

**Exclusive new files:** `src/traffictwin/ui/review_services.py`,
`tests/unit/ui/test_review_services.py`, plus this record. `services.py` is deliberately not
grown.

**Page slice executed (27 July 2026) via the additive-route mechanism instead.** Discovery:
`V07AdditivePageSpec` exists precisely for v0.7-only routes outside the counted 34-page
inventory (Manchester Operations precedent), so the page landed with **zero** enum or count
edits: an additive spec at `/match-review` under Source evidence, a runtime hook, a two-line
shim, the thin page, and AppTest coverage of the full decide-persist-resume-seal flow. The
claim extends to `src/traffictwin/ui/pages/match_review.py`,
`src/traffictwin/ui/app_pages/match_review.py`, the additive-spec and hook edits in
`navigation_v07.py`/`page_runtime.py`, `tests/ui/test_match_review_page.py`, the additive-route
sentences in `docs/v07_navigation.md`, and the `docs/index.md` row.

### Phase 26 claim: workspace continuity audit and network-chain recovery (27 July 2026)

Read-only audit of surviving research artifacts plus the deterministic recovery of the dead
network chain from committed pins. Recovery consumes only recorded identities (the pinned
Geofabrik extract verified against sha `233af3fa…` before use, the frozen v1.1 policy, seed 42
and the recorded pool envelope) and reconciles every regenerated artifact against its recorded
counts — a difference is reported as a finding, never silently adopted.

**Exclusive files:** `docs/integration/manchester_workspace_continuity_20260727.md`, its
`docs/index.md` row, this record, and recovery outputs under the gitignored
`data/network-recovery/` only.

### Phase 27 claim: bus-versus-DfT hourly shape comparison (owner-directed, 27 July 2026)

The declared B2 comparison step, built entirely from committed artifacts: the surviving
Option-A edgeData counts reduce to an hourly road-demand shape (local clock-hour labels under
the unresolved GA-DFT-1 blocker, carried as literals), and attended-session bus progression
aligns against it descriptively — support-gated hours, an explicit declared UTC-to-local
offset, tie-aware Spearman rank correlation reported verbatim, and type-level guards that bus
speed is never road speed, road counts are never bus counts, and nothing is causal. Measured
during construction and recorded rather than adopted: the surviving edgeData file totals
2,027,275 entered vehicles against the demand record's 2,024,123 — an open reconciliation
note for the demand-rebuild signing.

**Exclusive new files:** `src/traffictwin/integration/manchester/bus_profile_comparison.py`,
`tests/unit/test_bus_profile_comparison.py`, plus this record.

### Phase 28 claim: STA-02 per-algorithm checkpoint extension (owner-directed, 27 July 2026)

The reviewed extension the crossover's G6 option (i) names: `NWayRankingConfig` gains an
optional `checkpoint_by_algorithm` mapping — mutually exclusive with the single `checkpoint`,
keys required to equal the declared algorithms — so distinct trained actors, whose checkpoints
necessarily differ, can be ranked together. Selection and context reconciliation use the
per-algorithm expectation; the default single-checkpoint path is behaviourally unchanged and
its tests still pass untouched. The generated STA-02 contract's compatibility wording was
regenerated accordingly. Recorded consequence: adding the optional field changes the canonical
JSON of every `NWayRankingConfig`, so config fingerprints differ from pre-extension values; no
stored artifact pins one, and the study schema version is unchanged.

**Files:** `src/traffictwin/experiments/n_way_ranking.py` (bounded extension),
`tests/unit/test_n_way_ranking.py` (additions), the regenerated
`docs/reference/generated/n_way_ranking_contract.json` and `pydantic_schemas.json`, and this
record.

### Phase 29 claim: week-4 supervisor-expectation progress record (owner-directed, 27 July 2026)

Documentation-only: the owner directed a checklist of the supervisor's expectations
(reconstructed from the owner's private notes of the two July supervision meetings and Randy's
Year-1 report) with per-item status and next steps. The record claims no supervisor approval,
takes no queued owner decision, and keeps every referenced result at its recorded exploratory
`owner_approved_candidate` ceiling. The private meeting notes themselves stay outside the
repository.

**Exclusive files:** `docs/current_progress_week4.md`, its `docs/index.md` row, and this record.

### Phase 30 claim: services.py facade split (owner-directed, 27 July 2026)

The owner directed the deferred hygiene slice: the 3,127-line `src/traffictwin/ui/services.py`
god module becomes the `src/traffictwin/ui/services/` package — an `__init__.py` facade
re-exporting every existing public name from cohesive submodules, so all 59 consumer files
keep their `from traffictwin.ui.services import X` imports unchanged. Measured before
claiming: no consumer imports the module object, no test patches a `traffictwin.ui.services.*`
string target, no consumer imports a private name, and no scripts reference the module — the
public surface is exactly the from-import name set. Behaviour, signatures, and values are
unchanged; no page, test assertion, scientific library, or shared record is edited. Lands as
one commit gated on the full UI suite, full unit suite, repository Ruff/format, and strict
mypy.

**Exclusive files:** `src/traffictwin/ui/services.py` (replaced) and the new
`src/traffictwin/ui/services/` package modules, plus this record.

### Phase 31 claim: reviewed `ev` trace admission (owner-delegated, 27 July 2026)

Under the standing in-session delegation ("take reasonable choices and keep working"), the
next readiness slice repeats the ADR-062 pattern for the Gate-A-audited event-night trace
`ev` — the supervisor's own stadium what-if scenario. Measured before any edit (read-only
probe, 27 July): both `ev` blobs match the Gate-A hashes exactly at the audited tos-data
commit via local `git cat-file` (never a fetch), and the identity snapshot reconciles with
the production code path — T=23,400, maxN=175, 1,898,428 masked vehicle-seconds, 9,130
spans, zero missing/inactive cells, 1.51 s.

**Exclusive files:** the one-entry `PINNED_REVIEWED_TRACES` extension in
`src/traffictwin/integration/vec_runner/models.py`; the scenario-map entry in
`src/traffictwin/integration/vec_fresh_admission/service.py`; focused test updates in
`tests/unit/test_vec_runner.py` and `tests/unit/test_vec_fresh_admission.py`; new
`docs/decisions/ADR-065-ev-trace-allowlist-extension.md`; new
`docs/integration/evidence/vec_ev_trace_admission_probe_20260727.json`; the trace-scope
wording in `docs/integration/vec_fresh_run_admission.md`; index rows; plus this record.

**Boundaries.** `wd_am` and `wd_pm` remain refused; a test pins the allowlist to exactly
three entries. No runner control, preflight rule, timeout bound, or capability changes. The
admission enables no experiment by itself — any `ev` study needs its own predeclaration and
approval-gated campaign. Scenario identity (Champions League night) cites the producer's
provenance sidecar at upstream commit `6e56393`, read via a blob-less scratchpad peek; the
pinned clones stay unfetched pending R1.

### Phase 32 claim: demo-docs command refresh (owner-delegated, 27 July 2026)

Documentation-only: the three demo documents still instructed the retired
`python3.12 -m venv` / `pip install -e` / `.venv/bin/python` setup; every setup and CLI
invocation now uses the repository's actual `uv sync` / `uv run` workflow. No flow step,
caveat, boundary statement, or capability wording changed. Exclusive files:
`docs/demo_script.md`, `docs/demo_checklist.md`, `docs/standalone_demo.md`, and this record.

### Phase 33 claim: owner action pack (owner-directed, 27 July 2026)

The owner asked for the pending communications and the next-day plan to be committed:
`docs/owner_action_pack_20260727.md` carries the three send drafts (supervisor progress
email, Randy provenance/baseline/permission email, CSF access request) and the Monday
to-do. All are explicitly DRAFTS the owner reviews and sends personally; no agent sends
external communications; recipient addresses are omitted. Exclusive files: that document,
its `docs/index.md` row, and this record.

### Phase 34 claim: parallel-agent feature master prompt (owner-directed, 27 July 2026)

The owner directed a buildable-feature batch for a second agent session to execute while
the confirmatory campaign and external replies are pending. `PARALLEL_FEATURES_MASTER_PROMPT.md`
(repo root) carries six fully-specified features with exact disjoint new-file sets, the
live-campaign compute hazard, the shared-branch verification discipline, and all standing
boundaries. Parallel claims start at Phase 40; the primary session owns numbers below 40.
Exclusive files: that prompt and this record.

### Phase 40 claim: RSU monitor page (parallel session, 27 July 2026)

Feature 1 of the Phase 34 master prompt: the per-RSU drill-down that answers the
supervisor-relayed Study Case 1 question "which RSU is overwhelmed, and how overwhelmed",
over an already-imported TOS run. The existing TOS Replay page carries an all-RSU pressure
expander; this route adds the single-RSU window view and the cross-RSU load-asymmetry
measures, with every derived quantity computed in a unit-tested service module rather than
in the page.

**Exclusive new files:** `src/traffictwin/ui/rsu_monitor_services.py`,
`src/traffictwin/ui/pages/rsu_monitor.py`, `src/traffictwin/ui/app_pages/rsu_monitor.py`,
`tests/unit/ui/test_rsu_monitor_services.py`, `tests/ui/test_rsu_monitor_page.py`, plus the
additive-spec and runtime-hook lines in `navigation_v07.py`/`page_runtime.py`, one
`docs/v07_navigation.md` sentence, and one `docs/index.md` row.

**Boundaries.**

- Read-only through the existing accepted loaders `load_tos_rsu_series_for_ui`,
  `tos_rsu_summary_for_ui`, and `tos_task_summary_for_ui`. No raw artifact is parsed here and
  no accepted loader is edited.
- Measured before building, and carried as explicit unavailable states rather than filled in:
  the source RSU history exposes in-flight task count, remaining compute backlog, and the
  concurrency-pressure fraction only. **Per-RSU energy does not exist** in any accepted RSU
  loader (`avg_energy_j_per_task` is a run-level summary field), and **per-RSU processed-task
  counts do not exist** either — the per-task arrays carry no RSU attribution. Both are shown
  as typed unavailable reasons; the run-level figures appear only under an explicit
  run-level, not-per-RSU label.
- Pressure is in-flight tasks divided by recorded maximum concurrent tasks; it is never CPU
  utilisation, and the page never implies live monitoring — every series is labelled with its
  run key, source file, and window bounds.
- Additive route only, via `V07AdditivePageSpec` (the Phase 25 match-review precedent), so
  the counted 34-page `UiPage` inventory is untouched.

### Phase 41 claim: demand-diagnosis library (parallel session, 27 July 2026)

Feature 2 of the Phase 34 master prompt: the §2 measurements of
`docs/evaluation/demand_rebuild_predeclaration.md` implemented as a tested library so the
signed rebuild's diagnosis step is execution-ready. **It runs on no real data.** No route
pool is generated, no simulation runs, and the alpha.7 candidate demand and its gridlock
diagnostic stay untouched.

**Exclusive new files:** `src/traffictwin/integration/manchester/demand_diagnosis.py`,
`tests/unit/test_manchester_demand_diagnosis.py`, plus this record.

**Boundaries.**

- Measurements only. `purpose` is the type-level literal `measurements_only`, and
  `viability_verdict_included`, `threshold_applied`, and `variant_selected` are type-level
  `False`. The §4 thresholds are owner decision E3 and appear nowhere in this module; the
  library reports distributions and lets the person compare them.
- The library never loads a route file into memory. `iter_route_pool` streams with
  `defusedxml`'s hardened `iterparse` — streaming *and* entity/external-reference safe, the
  parser family the Manchester adapters already use — and clears both the element and the
  document root after every route, so peak memory is bounded by one route regardless of file
  size. That is the 1.28 GB lesson, and a test asserts the iterator really is lazy rather
  than reading ahead.
- **Recorded deviation from the master prompt's wording:** the prompt asked for line
  iteration; XML attributes may legally span lines, so a line-regex would silently drop
  routes, and a diagnosis that silently under-counts is worse than one that is slower.
  Streaming `iterparse` meets the actual constraint (never load the whole file) without that
  failure mode, and a test asserts a multi-line route is still parsed.
- Unmeasurable routes are recorded, never dropped silently: a route referencing an edge
  absent from the supplied mapping is counted in `routes_with_unknown_edges` and excluded
  from the length and residence-time distributions, whose own `n` is reported.
- Percentiles reuse the accepted deterministic `percentile_linear` helper rather than a new
  convention.

### Phase 42 claim: campaign mechanism report (parallel session, 27 July 2026)

Feature 3 of the Phase 34 master prompt: the explainability exhibit that sits beside the
exploratory campaign analysis. Given a completed analysis (parsed model or the plain dict of
one), it renders the per-seed evidence for *how* the arms differ — the full seed × arm
matrix for primary and secondary metrics, an invariance check naming the metrics the control
never moved, and an adjacent-arm range comparison.

**Exclusive new files:** `src/traffictwin/integration/vec_campaign/mechanism_report.py`,
`tests/unit/test_vec_mechanism_report.py`, plus this record.

**Boundaries.**

- Re-presentation only: it computes no metric, reads no registry, launches nothing, and
  imports no campaign service — only the models and analysis modules. `descriptive_non_causal`
  and `exploratory` are type-level `True`; `confirmatory`, `significance_claimed`, and
  `causal_claim` are type-level `False`.
- Invariance is stated precisely as *exact equality of the recorded values across arms within
  a seed*, and the report says so rather than leaning on the looser word "bit-identical"
  alone. A single-arm metric is never called invariant across arms.
- The report deliberately separates two questions that are easy to collapse: arm-level range
  overlap (across seeds) and per-seed ordering consistency. Reporting only the first
  understates the evidence; reporting only the second overstates it.

**Measured finding for the lead, recorded rather than acted on.** Run read-only against the
pilot's `campaign_analysis.json`, the report reproduces the pilot's mechanism finding exactly
— `task.offload.rate` is invariant across all four arms in every seed, and
`tos.task.no_eligible_target.rate_among_offload` is too. It also shows that for
`task.latency.mean_ms` the adjacent-arm **ranges overlap** at every step (e.g. `cap-2.5`
spans [6277.9, 13176.0] against `cap-1.5`'s [3961.8, 8065.2]) while the **per-seed ordering
is perfectly consistent** (0 of 3 seeds invert at any step). The sentence in
`docs/evaluation/capacity_pilot_results_20260727.md` — "per-arm ranges that do not overlap
between adjacent arms at any seed" — is true on the per-seed-ordering reading and false on
the plain range reading. That file is outside this session's claim and was not edited; the
lead may want to tighten the wording to "no seed inverts the ordering" before the
dissertation quotes it.

### Phase 43 claim: stadium event-study predeclaration skeleton (parallel session, 27 July 2026)

Feature 4 of the Phase 34 master prompt, documentation-only: the structural draft for the
supervisor's own stadium what-if on the admitted `ev` trace, in the same discipline as the
crossover draft. Nothing executes from it, and no `ev` execution has ever been run.

**Exclusive files:** `docs/evaluation/stadium_event_study_draft.md`, its `docs/index.md` row,
and this record.

**Boundaries.**

- Ships **UNSIGNED** with an empty sign-off block an agent never completes. The control,
  levels, actors, and primary endpoint are all `FILL-AT-SIGNING`, so the document is
  structurally unsignable until a person fills them.
- Fresh seeds `{40–44}` are proposed and confirmed disjoint from pilot `{0–2}`, held-out
  `{10–14}`, crossover `{20–24}`, and bus-fleet `{30–34}`.
- The publishable null is fixed before any evidence exists, and the pilot's honoured null is
  cited as the precedent.
- **Method constraint made explicit rather than discovered later:** `ev` and `inc` differ in
  duration, density, and scenario at once, so they are not exchangeable units. A cross-trace
  contrast is therefore *not* an STA-01 paired study and the draft forbids reporting one; any
  tested contrast lives within `ev`, and the pilot's numbers enter only as cited descriptive
  context, never pooled. The STA-02 per-algorithm checkpoint extension (Phase 28) is named as
  what would make multi-actor ranking possible if D2 chooses it.
- The runtime section carries ADR-065's recorded risk unchanged rather than substituting new
  arithmetic: no `ev` run has been timed, the recorded slot-scaling evidence (139 slots →
  225.7 s; 2,488 slots → 3,555.96 s) is labelled an extrapolation from two points, the first
  cell is a timing probe that re-costs the campaign, and the 7,200-second ceiling stays an
  escalation trigger and never a bound to raise.

### Phase 44 claim: dissertation appendix generators (parallel session, 27 July 2026)

Feature 5 of the Phase 34 master prompt: deterministic generators for the dissertation's
appendix payload, so the write-up never retypes a capability state or a dependency version by
hand.

**Exclusive new files:** `scripts/generate_dissertation_appendices.py`, the generated
`docs/dissertation_appendices/{appendix_a_capability_catalogue,appendix_b_software_versions}.md`,
`tests/unit/test_dissertation_appendices.py`, the `docs/index.md` row, and this record.

**Boundaries.**

- Sources are read through existing public APIs and committed files only: the capability
  states through `traffictwin.config.capabilities`, the ADR register from the committed
  `docs/decisions/index.md` table, and versions from `pyproject.toml` and `uv.lock` via
  `tomllib`. No manifest, generated reference, or capability state is written or changed.
- Deterministic by construction — no timestamps, no environment paths, every collection
  sorted — so regeneration on an unchanged tree is byte-identical and never shows up as commit
  churn. A test asserts that, and another asserts the committed files match a fresh run.
- The three-valued capability state is preserved; `unknown` is never collapsed into `false`.

**Recorded deviation, and the reason.** The master prompt specified a capability table
carrying `family` and `ADR refs`. **Neither exists in machine-readable form:** `CapabilitySet`
declares no family taxonomy, and no per-capability ADR mapping is recorded anywhere in the
repository. Grouping the rows by eye or guessing which decision governs which capability would
put fabricated structure into a dissertation appendix, so the generator emits the two
registers it can source honestly — the capability catalogue and the complete ADR register —
and the document itself states in §A.1.1 that the join is unavailable and why. A test asserts
no fabricated family column appears. **Handoff for the owner:** if the join is wanted for the
write-up, the fix is to record capability→family→ADR in the manifest, which is a lead-claimed
surface this session did not touch.

### Phase 45 claim: bus-session aggregates page (parallel session, 27 July 2026)

Feature 6 of the Phase 34 master prompt: the additive Bus Sessions route rendering the
aggregate-only measurement artifacts an attended live-bus session leaves in a workspace.

**Exclusive new files:** `src/traffictwin/ui/bus_sessions_services.py`,
`src/traffictwin/ui/pages/bus_sessions.py`, `src/traffictwin/ui/app_pages/bus_sessions.py`,
`tests/unit/ui/test_bus_sessions_services.py`, `tests/ui/test_bus_sessions_page.py`, plus the
additive-spec and hook lines in `navigation_v07.py`/`page_runtime.py`, a
`docs/v07_navigation.md` sentence, and one `docs/index.md` row.

**Boundaries.**

- Read-only over the Phase 23 measurement models. No acquisition is triggered, no snapshot is
  opened, and the accepted session-identity module is imported by full path and never edited.
- Aggregates only. The artifacts carry `aggregates_only: True` and
  `raw_identifiers_published: False` as type-level literals, so a tampered artifact fails
  validation before it loads; the loader keeps its own belt-and-braces check for the same
  condition, and tests exercise both paths. Further tests assert no token, salt, raw vehicle
  reference, or snapshot id reaches any rendered row.
- Buses stay buses: bus progression speed is never road speed, road-traffic volume is not
  available from this source, and both statements are on the page rather than implied.
- Absent workspace, absent Manchester directory, and absent artifact are three distinct
  explicit unavailable states, each carrying its reason. Nothing is defaulted to zero.
- **Recorded state of the world:** only the cadence artifact has a producer today
  (`scripts/bus_cadence_probe_session.py` writes
  `<workspace>/manchester/bus_cadence_probe_measurement.json`). The progression measurement
  primitive exists but **no runner publishes it**, so the page declares the sibling filename
  convention and reports the artifact's normal absence with exactly that reason rather than
  implying a session failed to record it.
- Additive route only, via `V07AdditivePageSpec`; the counted 34-page inventory is untouched.

### Phase 46 claim: bus-trajectory derivation library (parallel session, 27 July 2026)

Feature 7 of the `PARALLEL_FEATURES_MASTER_PROMPT_2.md` batch: the §3 trace-construction
rules of `docs/evaluation/bus_fleet_experiment_predeclaration_draft.md` implemented as a
tested library so the B1 execution step is ready before the document is signable. **It runs
on no real data.** No quarantine member is opened, no BODS call is made, no session artifact
is read or written, and no snapshot reaches this module.

**Exclusive new files:** `src/traffictwin/integration/manchester/bus_trajectory.py`,
`tests/unit/test_manchester_bus_trajectory.py`, plus this record.

**Boundaries.**

- The four §3/§5 parameters — gap ceiling (s), dwell radius (m), matched-share floor,
  implied-speed bound (m/s) — are **required keyword arguments with no defaults anywhere in
  the module**. They are owner decision G2 and the library refuses to imply one. The tests
  pass `120 / 15 / 0.8 / 32` as *test* values only, never as a recommendation.
- Type-level labels on every output: `derived_scenario` is `True`, `observed_fcd` is `False`,
  `buses_only` is `True`. The derived trace is never observed FCD and never general traffic.
- Interpolation follows the **caller-supplied matched path** only. A segment with no matched
  path is dropped and counted; the module contains no straight-line fallback, because a
  straight line through buildings is exactly what §3 forbids. A supplied path that does not
  connect the two fixes it spans is a matcher defect and is refused, not repaired.
- **Ordering recorded rather than left implicit:** the gap ceiling is applied *before* dwell
  detection. The probe's stale vehicles emit repeated identical fixes hours apart, so a
  dwell-first reading would convert 3.2-hour staleness into 3.2 hours of fabricated
  stationary occupancy. The ceiling drops those by design, as §5 states.
- Implied-speed screening **flags and never drops**: a segment over the bound is retained,
  counted, and reported with its measured value, so the person sees what the screen caught
  rather than a silently thinned trace.
- Vehicles below the matched-share floor are excluded whole, with counts; dropped seconds,
  dwell seconds, unmatched segments, and the per-vehicle interpolated-versus-observed share
  are all reported. Nothing is defaulted to zero and nothing is invented.
- **Deliberately out of scope, recorded:** §3's trace-window rule ("longest contiguous span
  with ≥ N linked vehicles") is not implemented — the feature brief scopes this library to
  the six named rules, and the window threshold is a further `FILL-AT-SIGNING` value. The
  window is selected over this module's output, not inside it.

### Phase 47 claim: confirmatory-mode campaign report renderer (parallel session, 27 July 2026)

Feature 8 of the batch-2 prompt: the analysis harness is type-level exploratory
(`confirmatory: False`), correctly — running it is not what makes a result confirmatory. The
signed predeclaration, the bound approval digest, the authorised held-out cohort, and a
completed declared matrix are. This is the separate renderer that verifies all of those and
then presents **exactly one** contrast as the confirmatory result.

**Exclusive new files:** `src/traffictwin/integration/vec_campaign/confirmatory_report.py`,
`tests/unit/test_vec_confirmatory_report.py`, plus this record.

**Boundaries.**

- **Fails closed with typed codes.** `render_confirmatory_report` refuses unless the design
  phase is held-out, `held_out_authorised` is set, the approval digest equals the digest the
  caller passed, the receipt's fingerprint/identity/approval match the design and it records
  the predeclaration verified unchanged, the campaign status is `completed` with zero failed
  and zero skipped cells, and the analysis binds to the same design fingerprint, experiment,
  campaign status, primary endpoint, and baseline arm. There is no override, flag, or partial
  mode. The digest is a required argument rather than read from the design, so a design
  cannot vouch for itself.
- **"Exactly one contrast" is true by construction, not by selection.** A design declaring
  more than one variation arm is refused outright; choosing one after the evidence exists is
  the failure mode the refusal exists to prevent.
- **Two additions to the prompt's gate list, both strictly stricter, recorded rather than
  assumed:** `predeclaration_verified_unchanged` must be true (otherwise the report would
  cite a digest it cannot stand behind), and the receipt's approval must equal the design's.
- **Measured limitation, recorded rather than papered over:** `VecCampaignAnalysis` carries
  no receipt fingerprint, so the strongest analysis-to-receipt binding the recorded models
  support is the shared design fingerprint plus the campaign status the analysis copied from
  its receipt. The module states that in place rather than implying a stronger link.
- An STA-01 study that could not be evaluated **renders** with its status shown and its
  values marked unavailable; it is not a refusal. Hiding an unevaluable primary endpoint is
  the one outcome the publishable-null commitment cannot tolerate.
- **The null renders identically.** A test asserts the section headings and the
  confirmatory-section offset are byte-identical between a signal, a null, a reversed, and an
  unevaluable result.
- Every number outside the single contrast is labelled descriptive context. Effect direction
  is the sign of the estimate and explicitly nothing more. No significance language beyond
  STA-01's own outputs; label ceiling `owner_approved_candidate`; supervisor approval,
  ethics approval, validation, and causality are each explicitly disclaimed.
- Imports the models and analysis modules only — no campaign service, no registry, no live
  campaign data. Tests build synthetic designs, receipts, and analyses in memory and use
  ordinary integer fleet seeds; the reserved confirmatory cohort is never named in code.

### Phase 48 claim: campaigns receipt browser page (parallel session, 27 July 2026)

Feature 9 of the batch-2 prompt: the additive `/campaigns` route rendering one campaign
receipt file at a time, so a completed campaign's declared matrix, approval provenance, and
resource usage can be read without opening a registry or a terminal.

**Exclusive new files:** `src/traffictwin/ui/campaigns_services.py`,
`src/traffictwin/ui/pages/campaigns.py`, `src/traffictwin/ui/app_pages/campaigns.py`,
`tests/unit/ui/test_campaigns_services.py`, `tests/ui/test_campaigns_page.py`, plus the
additive-spec and hook lines in `navigation_v07.py`/`page_runtime.py`, the
`docs/v07_navigation.md` sentences, the `docs/index.md` row, and this record.

**Boundaries.**

- **It never goes looking.** No default path, no directory scan, no glob, no recent-files
  list: a text input with an empty value is the only way in, and a directory path is refused
  rather than searched. That is the property keeping this page away from the campaign
  directory of a campaign that is executing.
- **A receipt is a terminal record, and the page says so.** It is written when a campaign
  stops; nothing polls, refreshes, or reports current state. A test asserts that every
  rendered fragment mentioning liveness or running state is *denying* it — a bare mention
  would be the implication to avoid — and that the page addresses it rather than staying
  silent.
- Receipts only. No registry access, no analysis computation, no scientific number: states,
  elapsed seconds, and byte counts are the only quantities surfaced, and a test asserts no
  metric key reaches any row. Phase and approval fields, including `held_out_authorised`,
  are displayed verbatim with badges in both directions.
- Honest typed errors as values rather than exceptions: nothing supplied, directory, missing
  file, unreadable bytes, oversize, invalid JSON, non-object JSON, no method version,
  *another* artifact kind named by its own method version, and a receipt that fails
  validation.
- **Recorded gap:** `VecCampaignReceipt` carries budget *usage* but not the declared ceilings
  — `max_cells` and `max_total_output_bytes` live in the design document, which the receipt
  does not embed. The page reports usage and states the ceilings are absent rather than
  rendering a percentage of something it cannot see. Arms and seeds are likewise read back
  from the recorded cells, which the page says on the surface.
- Additive route only, via `V07AdditivePageSpec`; the counted 34-page `UiPage` inventory is
  untouched, and the navigation edits extend the same additive tuple batch 1 extended.

### Phase 49 claim: dissertation docs pack (parallel session, 27 July 2026)

Feature 10 of the batch-2 prompt, documentation-only: the trace-provenance appendix and the
video storyboard. No code, no test, no capability, and no gate changes.

**Exclusive files:** `docs/dissertation_appendices/trace_provenance.md`,
`docs/video_storyboard.md`, their two `docs/index.md` rows, and this record.

**Boundaries.**

- Every number in the appendix is copied from a committed machine record — the Gate-A
  `vec_source_snapshot_audit.json` and the two admission-probe evidence JSONs. Nothing is
  retyped from memory, recomputed by hand, or carried over from another trace.
- **Two recorded deviations, both because the honest answer is smaller than the brief's:**
  1. The brief expected *three* probe evidence files (we/inc/ev). **Only two exist.** `we`
     was the originally pinned reviewed trace, so admitting it needed no allowlist extension
     and produced no probe document; its shape and reconciliation numbers come from the
     Gate-A record, and its identity-snapshot fingerprint and build time are recorded as
     not separately measured rather than borrowed from another trace.
  2. The rationale column is **not fully filled.** Only `inc` and `ev` rationales are
     recorded anywhere in this repository. The producer's sidecar `traces/PROVENANCE.md` at
     upstream commit `6e56393` is cited as the brief requires, but that commit is **not
     present in the local pinned clone** (`git cat-file` on it fails) and reaching it would
     need a fetch, which is forbidden. The `we`/`wd_am`/`wd_pm` rationales are therefore
     marked "not restated here — read from the cited sidecar", which a person can complete
     and no agent may invent.
- `wd_am` and `wd_pm` carry audit-table values only and are marked **not admitted**, with
  the reason: outside the reviewed allowlist, no probe run, no identity snapshot built.
- Appendix lettering is left to the write-up: batch 1's generated
  `appendix_b_software_versions.md` already holds `B`, so the trace table is referenced by
  name and says so rather than colliding on a letter.
- The storyboard **states no scientific result and contains no result number**. The shot
  that needs one points the camera at the committed results record and instructs the speaker
  to name the record, not read from it.
- The rubric split is stated as recorded (Use of Medium 40%, Complementing the Report 40%),
  and the remaining 20% is explicitly *not guessed* — the storyboard says the note does not
  itemise it.
- The un-reported shots are named and justified (replay animation, RSU Monitor drill-down,
  provenance DAG click-through, Match Review decide-persist-seal), each mapped to its
  demo-script step or additive route, and the spoken-caveats checklist reuses
  `docs/demo_checklist.md`'s required caveats verbatim plus two the recorded medium needs.
- The generated appendix files and the appendix generator are untouched; a run of the
  Phase 44 generator test confirms the new hand-written sibling does not disturb it.

### Phase 50 claim: TOS reader forked-child segfault (parallel session, 27 July 2026)

Feature 11 of the batch-2 prompt: diagnose first, then repair only if the honest repair is
bounded. It was, so both landed.

**Exclusive files:** `docs/integration/tos_reader_fork_diagnosis.md`, its `docs/index.md`
row, the one-keyword change in `src/traffictwin/integration/tos/readers.py`, two regression
tests appended to `tests/unit/test_tos_integration.py`, and this record.

**Measured, not assumed.**

- **Reproduced:** 14 baseline runs of `tests/ui/test_tos_analysis_pages.py`. Six printed
  **exactly 13** segfault dumps; eight printed zero. Never any other count — the behaviour is
  bimodal per process. Every run exited `0` with `4 passed`, which is why it survived.
- **Localised:** all 13 dumps in a captured run carry the same innermost project frame,
  `readers.py:256` — the `subprocess.run` inside `package_git_commit` — reached by three
  routes (`package_fingerprint` ×8, `validation.py` ×3, `audit.py` ×2) from three pages.
- **Mechanism:** `capture_output=True` leaves `close_fds` at its default `True`, which
  disqualifies CPython's `posix_spawn` fast path, so the call takes `_fork_exec`. That fork
  happens on a Streamlit script-runner thread in a multithreaded process; on macOS the child
  faults, and pytest's inherited faulthandler prints the shared thread state, which is why
  each dump shows the parent's frames.
- **Ruled out by measurement:** disabling CPython's vfork fast path still produced 13 dumps
  on 3 of 6 runs. It is plain fork-after-threads, not the vfork variant.
- **Not established, recorded as open:** why the 0-or-13 pattern is decided per process. The
  repair removes both branches, but the condition was not identified and is not guessed at.

**Impact was looked for and not found, and the document says so.** The parent swallows child
failures (`except (OSError, subprocess.SubprocessError): return None`), so a silent wrong
answer is structurally possible. A probe ran 600 pre-fix lookups against a real checkout from
a thread pool with eight further live threads: zero `None` results, one distinct commit, no
faults. The failing tests' package has no `.git`, so `None` was correct there either way. The
record therefore states that the observed defect is the dump noise and that no lost return
value was reproduced — the silent-failure shape is a latent risk the repair also removes, not
a bug caught misbehaving.

**The repair, and the three alternatives rejected with reasons.** `close_fds=False` on that
one call, which satisfies every `posix_spawn` condition CPython requires (darwin, absolute
executable, no `preexec_fn`, no `pass_fds`, no `cwd` — the command uses `git -C` — capture
pipes above fd 2, no session/group/uid/gid/umask option). PEP 446 makes Python-created
descriptors non-inheritable, so the child receives the same descriptors either way. Command,
arguments, parsing, timeout, exception handling, and return values are untouched. Rejected:
disabling `_USE_VFORK` (measured ineffective, and mutating a CPython private global is worse
than the problem); a `.git` existence guard (**changes returned values** — `git -C` walks up
to an enclosing repository, so a package nested inside a checkout currently reports that
repository's commit); and reading `.git/HEAD` directly (reimplements git plumbing —
`packed-refs`, detached HEAD, worktree indirection — far past the Phase 18 scale).

**Verification.** Ten consecutive runs of the file with zero dumps against a required three,
then three more at the end of the slice. Full suites after the repair: 3,126 passed across
`tests/unit` and `tests/ui`, with Ruff, format, strict mypy over 790 files, and
`git diff --check` clean.

**The regression test asserts the call shape deliberately, and says why in its docstring.**
The fault kills only a transient child while the parent returns normally, so no behavioural
assertion can catch a regression; the test pins the `posix_spawn` conditions instead, and a
second test pins both return branches unchanged.

### Phase 35 claim: batch-2 parallel feature prompt + range-wording correction (27 July 2026)

Batch 1 (Phases 40–45) was independently re-verified by the primary session (ruff clean,
strict mypy 781 files, 2,579 unit + 467 UI green — matching the batch's own report), and
its pilot-results finding was confirmed against the analysis JSON and corrected: pooled
per-arm latency ranges DO overlap between adjacent arms; the true statement is the
within-seed ordering (0 of 3 seeds invert at any step). The correction lands in the results
record and the confirmatory draft; candidate (b) carries the same sentence but is
byte-frozen by the running campaign's approval digest, so its correction is recorded beside
it, never applied to it. `PARALLEL_FEATURES_MASTER_PROMPT_2.md` (repo root) specifies batch
2 — Phases 46–50: bus-trajectory derivation library, confirmatory-mode report renderer,
campaigns browser page, dissertation docs pack, tos-reader fork-segfault diagnosis.
Exclusive files: that prompt, the two corrected evaluation documents, and this record.

### Phase 36 claim: batch-3 parallel feature prompt (27 July 2026)

Batch 2 (Phases 46–50) was independently re-verified by the primary session (ruff clean,
strict mypy 790 files, 2,652 unit + 476 UI green; the Phase 50 fork-segfault repair held
across the verification runs). `PARALLEL_FEATURES_MASTER_PROMPT_3.md` (repo root) specifies
batch 3 — Phases 51–55: capacity-study research figures through the accepted export
machinery, the user-evaluation instrument draft, the bus post-session report script, the
mechanism-report CLI with the committed pilot exhibit, and the objectives-traceability and
abbreviations appendices. It grants one read-only carve-out: the completed pilot's local
analysis JSON; the live confirmatory directory stays untouchable. Exclusive files: that
prompt and this record.

### Phase 51 claim: capacity-study research figures (parallel session, 27 July 2026)

Feature 12 of the `PARALLEL_FEATURES_MASTER_PROMPT_3.md` batch: the dissertation's static
capacity-study figures, generated **only** through the accepted REP-01 export machinery in
`src/traffictwin/reporting/latex.py`, which is read and imported and never modified.

**Exclusive new files:** `scripts/generate_capacity_figures.py`,
`tests/unit/test_capacity_figures_script.py`, the generated
`docs/dissertation_appendices/figures/*`, the `docs/index.md` row, and this record.

**Boundaries.**

- The analysis-JSON path is a **required positional argument with no default**, so the script
  can never reach for a campaign directory on its own. The committed figures were rendered
  from the completed pilot's `campaign_analysis.json` under the batch-3 read-only carve-out;
  nothing under `data/vec-fresh/**` was written, and the live confirmatory directory was
  never opened.
- Re-presentation only. Every rendered number is a value the accepted analysis already
  recorded; the script computes no metric, no difference, and no summary of its own.
- `exploratory`, `owner_approved_candidate`, and `descriptive non-causal` appear in each
  figure's **rendered** text. The two renderers draw different fields — the SVG draws the
  title and source line, the LaTeX fragment draws the caption — so the labels are carried in
  the source id *and* the caption to reach both, and a test asserts their presence in every
  published file of both kinds.

**Three properties of the accepted renderer, measured and recorded rather than worked
around.**

1. **Its numeric figures are horizontal bar series, not polylines.** The brief asked for
   per-seed latency *curves*. `ResearchExportProjection` carries a flat label/value entry
   list, and `projection_to_svg` draws it as bars on a shared signed scale; there is no
   polyline path in the accepted exporter. Adding one would mean editing `latex.py`, which
   this feature is explicitly forbidden to modify. The curve is therefore published as an
   ordered bar series — one contiguous run per fleet seed, in capacity order — with the
   exact values in the companion table, and a test pins the seed-major ordering. If the
   write-up wants true polylines, that is a `latex.py` change and a lead decision.
2. **Its numeric scale is zero-anchored by construction** (`_numeric_scale` takes
   `min(0, …)`/`max(0, …)`), so there is no zoom to state in the caption: the zero-anchored
   chart is the only thing the machinery produces. The `~0.79` deadline-success band is
   published at true size, which is what makes the flatness visible as flatness, and the
   analysis's **own recorded** paired differences are published beside it as the readable
   companion. No deviation, deviation-from-baseline, or rescaled value is computed here.
3. **A title long enough to carry the status labels overflows the canvas.** Measured with
   the renderer's own font metrics: the labelled titles ran 1,238–1,324 px against a 920 px
   drawable width at the fixed 24 px title size, and the exporter neither wraps nor rejects
   them — the viewport would have silently clipped them. The labels moved to the 13 px
   source line, which measures 890–903 px, and a test asserts every published title and
   source line fits, since nothing else in the pipeline would catch a regression.

**Recorded state of the world.** `data/vec-fresh/capacity-pilot/campaign_analysis.json` is
**not tracked by git**, so the committed figures cannot be regenerated from a fresh clone
and no test asserts committed-equals-fresh. The provenance note therefore records the source
file's SHA-256 beside the design fingerprint and every projection fingerprint, which is the
only link a later reader has between a committed figure and the payload that produced it.
The tests assert determinism on synthetic payloads instead.

### Phase 52 claim: user-evaluation instrument draft (parallel session, 27 July 2026)

Feature 13 of the batch-3 prompt, documentation-only: the survey instrument the ethics
application references, drafted so submission is attach-and-send.

**Exclusive files:** `docs/evaluation/user_evaluation_instrument_draft.md`, its
`docs/index.md` row, and this record.

**Boundaries.**

- Ships **PROPOSED and unsigned**. Every value carried from the ethics draft's proposed-value
  table is marked as a proposal a person confirms at submission, and the bracketed fields
  only a person can supply — contacts, storage service, ethics reference, session dates —
  stay bracketed. No approval, signature, reference number, or participant response is
  invented, and none ever will be by an agent.
- Composes the existing instrument documents rather than replacing them. `survey.md`,
  `consent_and_privacy.md`, `participant_task_script.md`, and `interview_guide.md` are read
  and cited; none is edited, and none is outside this claim by accident.

### Phase 53 claim: bus-session post-session report script (parallel session, 27 July 2026)

Feature 14 of the batch-3 prompt: the one command that turns an attended session's workspace
artifacts into the numbers the B1 draft needs, so the post-session step after tomorrow's peak
session is reading a report rather than assembling one.

**Exclusive new files:** `scripts/bus_session_report.py`,
`tests/unit/test_bus_session_report_script.py`, plus this record.

**Boundaries.**

- Composes the accepted `bods_session_identity` and `bus_profile_comparison` modules
  **read-only and by full module path**, because the Manchester package `__init__` is
  lead-claimed. Neither module is edited and neither measurement is recomputed.
- **No acquisition, no API key, no network, no snapshot.** The script reads two JSON
  measurement artifacts from an explicit workspace path and, optionally, one committed
  edgeData file. There is no default workspace.
- Aggregates only. The artifacts must declare `aggregates_only` and not
  `raw_identifiers_published` or they are refused, and no session token, salt, raw vehicle
  reference, or snapshot id reaches the rendered report.
- The B1 block emits **candidate values a person confirms at signing**. It never writes into
  the predeclaration draft and never converts a measurement into a chosen threshold.

### Phase 54 claim: mechanism-report CLI and the committed pilot exhibit (parallel session, 27 July 2026)

Feature 15 of the batch-3 prompt: the command line over the Phase 42 mechanism report, and
the one rendered exhibit it produced from the completed pilot.

**Exclusive new files:** `scripts/render_mechanism_report.py`,
`tests/unit/test_render_mechanism_report_script.py`,
`docs/evaluation/capacity_pilot_mechanism_report_20260727.md`, the `docs/index.md` row, and
this record.

**Boundaries.**

- Both the analysis-JSON path and the output path are **required positional arguments with no
  defaults**, and an existing output is kept unless `--overwrite` is passed.
- The accepted `render_mechanism_report_markdown` body is emitted **verbatim**. The script
  adds a provenance header and a reading note around it and changes not one byte of what the
  accepted renderer produced.
- **The corrected range-overlap wording only.** The header states the distinction in its
  general form — pooled per-arm ranges can overlap while every seed still ranks the pair the
  same way, and the paired within-seed contrast is what the machinery uses. The superseded
  "ranges that do not overlap between adjacent arms at any seed" sentence is never
  reintroduced, and a test asserts it cannot appear in any rendered output.
- The exhibit is a **new** file. `capacity_pilot_results_20260727.md` is cited and not
  edited, and `capacity_confirmatory_candidate_b_latency_primary.md` — byte-frozen by the
  live approval digest — is neither read into nor touched by this feature.

### Phase 55 claim: objectives traceability and abbreviations appendices (parallel session, 27 July 2026)

Feature 16 of the batch-3 prompt, documentation-only: the O1–O7 traceability spine and the
abbreviation list, both written for the dissertation to cite directly.

**Exclusive files:** `docs/dissertation_appendices/objectives_traceability.md`,
`docs/dissertation_appendices/abbreviations.md`, their two `docs/index.md` rows, and this
record.

**Boundaries.**

- **Statuses are honest, including where they are unflattering.** O7's user-evaluation strand
  is `pending ethics` with zero participants and no data; the Manchester confirmatory
  campaign is `in execution`, not complete and not accepted. Nothing is recorded as achieved
  because it is nearly achieved.
- **Every count was re-measured rather than copied.** The working evidence map's "35-route
  UI" and "3,167 tests" are both stale; the verified figures at this commit are 34 `UiPage`
  values plus 5 additive routes, and 3,454 collected tests (2,701 unit, 476 UI, 214
  integration, 63 golden). Collected counts are reported as collected, not as passed.
- Objective wording is carried from the owner's dissertation skeleton rather than reworded,
  so the appendix and Chapter 1 cannot drift apart.

### Phase 56 claim: CSF job-pack contract (parallel session, 27 July 2026)

Feature 17 of the batch-4 prompt: the import-first contract for the day university compute
becomes available. One approved campaign design is *exported* as a fingerprinted job pack
naming its inputs by identity; a returned cell-receipt set is *verified* against that pack
before anything downstream may read it.

**Exclusive new files:** `src/traffictwin/integration/vec_campaign/job_pack.py`,
`tests/unit/test_vec_job_pack.py`, `docs/integration/csf_job_pack_contract.md`, the
`docs/index.md` row, and this record.

**Boundaries.**

- **Contract only — there is no executor.** No SSH, no network, no scheduler, no SLURM
  submission, no file transfer, no clock. Every function is pure over supplied models, and
  the pack's `created_at_utc` is a caller-supplied argument rather than a read clock, so a
  pack is byte-reproducible.
- **Input identity, never input bytes.** `VecJobPackInputRef` carries repository, audited
  commit, path, SHA-256, and size for each declared input; `external_repository_bytes_included`
  is type-level `False` and a validator refuses any pack whose refs name a repository outside
  the audited `vec_env`/`tos-data` pair. The pinned tos-data commit is recorded so a remote
  site can be told exactly what to check out — the packs never carry the checkout.
- **A verified import is NOT an admission.** `admission_granted`, `scientific_admission`, and
  `registry_write_performed` are type-level `False` on the verification result, and the
  verification's own docstring points at the ADR-061 path, which stays local and unchanged.
  Verification answers one question — are these receipts the ones this pack asked for, intact
  — and hands the answer to a person.
- Verification is **complete before it is favourable**: design-fingerprint match, every
  receipt's `request_fingerprint` ∈ the pack's declared cells, no duplicate and no unexpected
  cell, per-file `sha256` present on every published output plus a recomputed
  `output_fingerprint` match, and unfulfilled cells reported by name. Missing cells make an
  import `partial`, never `verified`; any mismatch makes it `refused`.
- Imports models from `vec_campaign.models` and `vec_runner.models` only. No campaign
  service, no registry, no admission module.

### Phase 57 claim: bus-versus-DfT comparison report script (parallel session, 27 July 2026)

Feature 18 of the batch-4 prompt: one command over an explicit workspace path that runs the
accepted `bus_profile_comparison` machinery against the committed Option-A edgeData file and
writes the comparison out as a JSON artifact and a markdown report.

**Exclusive new files:** `scripts/bus_dft_comparison_report.py`,
`tests/unit/test_bus_dft_comparison_report_script.py`, plus this record.

**Boundaries.**

- Composes the accepted `bods_session_identity` and `bus_profile_comparison` modules
  **read-only and by full module path** (the Manchester package `__init__` is lead-claimed).
  Neither module is edited and no measurement is recomputed — the alignment, the support gate,
  and the rank correlation are all the accepted functions' own output.
- **The UTC-to-local offset is a required argument with no default.** The session artifacts
  record UTC hours and the DfT profile records local clock-hour labels; a defaulted offset
  would silently misalign two independent real sources by an hour, so the script refuses to
  run without one.
- **Aggregates only, and snapshot ids do not travel.** The workspace artifact must declare
  `aggregates_only` and must not claim `raw_identifiers_published` or it is refused. A
  snapshot id is a locator into the quarantine directory, so the written report publishes
  `session_snapshot_count` and sets `session_snapshot_ids_published` to a type-level `False`;
  the ids stay in the workspace artifact. Neither written file contains an absolute path.
- **Support-gated hours are reported with their counts.** The accepted comparison records only
  which hours it excluded; the report looks each excluded hour's segment count back up in the
  progression measurement, so a reader sees how much support an excluded hour actually had
  rather than only that it was dropped.
- Bus speed is never road speed and road counts are never bus counts, both carried as
  type-level literals. The Spearman value is reported as a rank correlation between two
  observed shapes with no significance test, no threshold, and no causal reading;
  `significance_claimed` is type-level `False` and a test pins a causal-vocabulary ban over
  the rendered markdown.
- No acquisition, no API key, no network, no snapshot read, no quarantine access. Both output
  paths are supplied; an existing output is kept unless `--overwrite` is passed.

### Phase 58 claim: quality-gate snapshot appendix generator (parallel session, 27 July 2026)

Feature 19 of the batch-4 prompt: the dissertation's §3.2 quality table as a generated
artifact, so the figures in the write-up are collected by a command rather than retyped from
a terminal scrollback that has since scrolled away.

**Exclusive new files:** `scripts/generate_quality_snapshot.py`,
`tests/unit/test_quality_snapshot_script.py`,
`docs/dissertation_appendices/quality_snapshot.md` (generated), the `docs/index.md` row, and
this record.

**Boundaries.**

- **No test is executed.** Every pytest invocation carries `--collect-only -q`, and a test
  asserts that property over the generated command list rather than trusting the author.
  Collection is cheap and is explicitly permitted while the confirmatory campaign runs; the
  campaign, `data/vec-fresh/**`, and the registries are untouched.
- **Collected counts are reported as collected, not as passed.** The document says so in
  the row itself, because a collected count is an inventory and a passed count is a result,
  and the dissertation must not blur them.
- **The mypy file count is a supplied value, not a measured one.** A full `mypy src tests`
  run is exactly the kind of sustained compute the live campaign forbids, so the generator
  takes `--mypy-file-count` and, when it is absent, prints the row as not collected together
  with the command a reader runs. It never guesses the number and never leaves a stale one
  in place silently.
- Ruff check and ruff format are run because they are seconds of single-process work, and
  their status strings are recorded verbatim rather than reduced to a pass/fail bit.
- **Every row carries the exact command that reproduces it.** A number in this appendix that
  a reader cannot re-derive is not evidence, so the command column is required by the
  renderer rather than optional.
- The generation timestamp and the commit are recorded together, and a dirty working tree is
  reported as dirty — a snapshot taken over uncommitted changes says so on its face.

### Phase 62 claim: job-pack CLI wrapper (parallel session, 27 July 2026)

Feature 23 of the batch-5 prompt: the operational entry point for the Phase 56 job-pack
contract, so the day CSF access arrives the contract is reachable from a terminal without
the lead-owned `cli.py` being touched.

**Exclusive new files:** `scripts/vec_job_pack.py`, `tests/unit/test_vec_job_pack_cli.py`,
and this record.

**Boundaries.**

- **Still no executor.** `export` writes a JSON file a person carries; `verify` reads a
  directory a person carried back. No SSH, no network call, no scheduler, no submission, no
  transfer, and no registry — the script is a mouth for the library, not a new capability.
- **Library refusals are passed through verbatim.** `JobPackError` reaches the operator in
  the library's own words rather than being reworded into something friendlier, because a
  provenance refusal softened on its way to a terminal is a refusal somebody talks past.
- **No clock.** `--created-at-utc` is required, matching the library's caller-supplied
  timestamp, so the same design and checkout always produce the same pack bytes. A test
  asserts two exports of the same arguments are byte-identical.
- **Hashes are the audited pins; only sizes are measured.** The manifest is assembled from
  the design's reviewed trace identity plus `PINNED_ACTORS`/`PINNED_EVALUATOR_FILES`, so the
  command line cannot introduce an input or launder a local file into an identity — the
  library refuses any manifest that names anything else. The checkout's HEAD commit is read
  (`git rev-parse`, read-only, no fetch) and must equal the audited commit for that
  repository; a checkout at any other commit is refused rather than silently packed.
  `--verify-input-hashes` re-hashes every declared input and is **off by default**, because
  re-reading multi-gigabyte traces is the sustained I/O that must not run beside the live
  campaign.
- **Only a `verified` import exits 0.** `partial` and `refused` both exit 1: a script that
  exited 0 on a partial import is the thing that lets a half-returned campaign be read as a
  whole one. Every summary states that a verified import is not a scientific admission, and
  the written report carries the library's type-level `admission_granted` /
  `scientific_admission` / `registry_write_performed` falses.
- Fixtures are tiny synthetic checkouts and receipts under `tmp_path`. No test touches an
  external repository, `data/vec-fresh/**`, a registry, or the network.

**Gates.** 29 focused tests green; 2,794 `tests/unit` green; `ruff check src tests scripts`
clean; `ruff format --check` clean on both touched files; `mypy src tests` clean over 798
files (the standalone-script `import-untyped` notes are the same pre-existing ones every
`scripts/` file produces); `git diff --check` clean. No UI file touched, so `tests/ui` was
not required.

### Phase 63 claim: single-command gate battery (parallel session, 27 July 2026)

Feature 24 of the batch-5 prompt: the handoff gate list, which currently lives in `AGENTS.md`,
four batch prompts, a checklist, and terminal scrollback, written down once as a command that
runs it.

**Exclusive new files:** `scripts/run_all_gates.py`,
`tests/unit/test_run_all_gates_script.py`, and this record.

**Boundaries.**

- **The battery never modifies anything.** `ruff check` without `--fix`, `ruff format` with
  `--check`, `mypy`, `pytest`, and `git diff --check`, which reports whitespace damage rather
  than repairing it. A test asserts the read-only property over the declared command list
  against a `MUTATING_ARGUMENTS` table, so a future gate that would write something fails the
  suite rather than the reviewer's attention.
- **A gate that did not run is never reported as passed.** Gates after a stopping failure
  render as `NOT RUN`, `--skip`ped gates render as `SKIP`, and both are visible rows with a
  named summary line. The exit code is 0 only when every declared gate passed — a skipped or
  unreached gate exits 1, because the table's whole purpose is to be pasted into a handoff.
- **No new dependency and no parallelism.** Standard library only; each command runs to
  completion one at a time in declared order. `--skip` exists so a suite that must not run
  right now — the integration suite while a campaign holds the machine — is excluded
  explicitly and shows as excluded. An unknown `--skip` name is refused (exit 2) rather than
  silently ignored.
- **The tests never run a real gate.** The runner and the clock are injected; every command is
  answered from a table. Running the real suites from a unit test would take longer than the
  suites and would prove nothing about the battery. Only `--list` and the unknown-skip refusal
  were exercised as real invocations, neither of which executes a gate.
- `ruff format --check` is repository-wide in the battery. The per-feature gate checks only a
  feature's touched files; a battery cannot know what "touched" means, and the wider check is
  the stricter one — recorded here so the two are not read as contradicting each other.

**Gates.** 25 focused tests green; 2,819 `tests/unit` green; `ruff check src tests scripts`
clean; `ruff format --check` clean on both touched files; `mypy src tests` clean over 799
files and clean on the script itself; `git diff --check` clean. No UI file touched, so
`tests/ui` was not required.

### Phase 65 claim: printable participant documents (parallel session, 27 July 2026)

Feature 26 of the batch-5 prompt, documentation-only: the two documents an ethics submission
attaches as separate files, split out of the Phase 52 instrument so the submission step is
attach-and-send rather than a writing task.

**Exclusive new files:** `docs/evaluation/participant_information_sheet_draft.md`,
`docs/evaluation/consent_form_draft.md`, their two `docs/index.md` rows, and this record.

**Boundaries.**

- **Ships PROPOSED and unsigned, and no consent exists.** No committee has seen either
  document, no supervisor has signed one, and no reference number exists — the ethics reference
  is stated as assigned-at-submission in both files and is never pre-filled. No participant,
  participant code, response, quotation, approval, or signature is invented, and the consent
  form says on its face that an agent never completes, signs, dates, or witnesses it.
- **Aligned to the ethics draft's proposed values, which remain the authority.** Survey not
  interview, no recording, random participant code only, University-approved encrypted storage,
  retention until degree award plus 12 months, a 14-day withdrawal cutoff, and
  supervisor-mediated recruitment. Both documents state that if they ever disagree with
  `ethics_application_draft.md`, the ethics draft wins and the file is wrong.
- **No recording-consent item appears.** The earlier combined draft carried an optional
  recording statement; recording is proposed as none, so including the item would misdescribe
  the study. The form says why it is absent and that recording would need its own application.
- **The consent format is not chosen.** The Phase 52 instrument records that wet signature,
  tick-box return, and recorded verbal consent are an approval decision an agent does not make;
  the attestation block is a labelled placeholder rather than a signature line, and rebuilding
  it to match the chosen format is on the person's checklist.
- The proposal that a completed consent record, if the format captures a name, is stored
  separately from response data is **marked as a proposal**. It is a faithful reading of the
  ethics draft's separate participant-code-key rule, not a new policy, and
  `anonymised_result_schema.json` still has no name field.
- **The existing drafts are untouched.** `user_evaluation_instrument_draft.md`,
  `consent_and_privacy.md`, `survey.md`, `participant_task_script.md`, and
  `ethics_application_draft.md` are read and cited, none is edited, and `docs/index.md` gained
  exactly the two permitted rows.

**Gates.** Documentation-only, so no focused test applies; 2,819 `tests/unit` green;
`ruff check src tests scripts` clean; `mypy src tests` clean over 799 files; `git diff --check`
clean. Every `docs/index.md` link and every sibling document reference in the two new files was
resolved against the tree. `ruff format` does not apply to markdown, and no UI file was touched.

### Phase 37 claim: batch-4 parallel feature prompt (27 July 2026)

Batch 3 (Phases 51–55) fully verified by the primary session (ruff clean, UI 476 green,
unit 2,703 and strict mypy 793 during the same window; artifacts spot-checked: appendix
documents, SVG/TeX figures, and the mechanism exhibit with correct exploratory labels).
`PARALLEL_FEATURES_MASTER_PROMPT_4.md` (repo root) specifies batch 4 — Phases 56–60: the
CSF job-pack contract (models and design doc, no executor), the bus-versus-DfT comparison
report script, the quality-gate snapshot generator, and two features hard-gated on the
detached confirmatory campaign completing first (page figure capture; the single ev timing
probe measuring ADR-065's open risk, timing evidence only, no admission). Exclusive files:
that prompt and this record.

### Phase 38 claim: batch-5 parallel feature prompt (27 July 2026)

Batch 4's Features 17–19 verified on the live tree (2,765 unit + 476 UI green, ruff,
strict mypy 797). `PARALLEL_FEATURES_MASTER_PROMPT_5.md` (repo root) specifies batch 5 —
carried Features 20–21 (Phases 59–60, unchanged specs, campaign-completion gated) plus
Phases 61–65: confirmatory figures through the existing generator (gated on the committed
confirmatory results record), the job-pack CLI wrapper, the single-command gate battery,
the stadium fill-in candidate (gated on the ev timing probe), and the printable
participant documents. Adds the post-completion read-only carve-out for the confirmatory
analysis artifacts. Exclusive files: that prompt and this record.

### Phase 39 claim: batch-6 parallel feature prompt (27 July 2026)

`PARALLEL_FEATURES_MASTER_PROMPT_6.md` (repo root) specifies batch 6 — Phases 66–71: the
read-only campaign offline verifier, dissertation results tables through the accepted
export machinery, the B1 bridge from derived bus trajectories to the VEC-06 request shape
(construction only, never an accepted receipt), the crossover fill-in candidate (gated on
the confirmatory results record; notes that G6 option (i) became available with the
Phase 28 STA-02 extension), methodology diagram drafts, and the video narration script.
Batch 6 must not start until batch 5's end report exists. Phase numbering: 66–71 for this
batch, 72–79 reserved unused, and the primary session moves to Phase 80+ hereafter (this
is the last below-40 primary claim). Exclusive files: that prompt and this record.

### Phase 66 claim: campaign offline verifier (parallel session, 27 July 2026)

Feature 27 of the batch-6 prompt: the examiner-facing "campaign doctor" that re-derives a
completed campaign's own claims from the artifacts on disk and reports every disagreement.

**Exclusive new files:** `src/traffictwin/integration/vec_campaign/verify.py`,
`scripts/verify_campaign.py`, `tests/unit/test_vec_campaign_verify.py`,
`docs/integration/vec_campaign_verification.md`, its one `docs/index.md` row, and this record.

**What it re-derives.** Six named check groups: the design fingerprint (plus experiment id and
seed cohort) recomputed from the supplied design against `campaign_receipt.json`; the full
(arm, seed) grid with each cell's run id and request fingerprint recomposed from the design's
controls; each executed cell's `execution_receipt.json` re-read and its request fingerprint,
run id, terminal status, and own fingerprint re-compared; every published output file re-hashed
and re-sized on disk; every admitted cell looked up under the receipt-derived registry identity
`vec:fresh:<receipt[:16]>` with its run's experiment/arm/pairing seed, its metric collection,
and the registered experiment plan; and the approval block with its predeclaration digest
re-hashed against the document on disk.

**Boundaries.**

- **Read-only with no repair path.** No `--fix`, no reconciliation, no default output location;
  `repairs_performed` and `writes_performed` are type-level `False`. A test snapshots every
  campaign file's size and digest, the predeclaration bytes, and the registry run count across a
  full verification pass and asserts all three unchanged. The one honest caveat is recorded in
  the module, the docs page, and here: the public `Registry` read methods apply their own
  idempotent schema migration on open, exactly as any other reader does; no run, metric
  collection, experiment, annotation, bundle record, or evidence pack is ever written.
- **PASS is a consistency statement, never a scientific one.** Five standing limitations carried
  in every report: not a finding/accepted result/reproduction/approval; read-only; the design is
  the caller's and verification cannot prove it is the one a person approved; re-hashing proves
  unchanged bytes and never numerical reproduction; and a halted campaign verifies cleanly when
  its receipt records the halt faithfully, so PASS never means the campaign succeeded.
- **Absent evidence is a finding, never a pass.** Missing cell directories, deleted payloads, an
  unreachable registry, and an absent predeclaration each produce a WARNING finding. Checks the
  caller declined (no registry supplied, `--skip-output-hashes`) are listed in `checks_not_run`
  so a skipped check can never read as a passed one. Exit codes separate the three cases: `0`
  passed, `1` a check failed, `2` verification could not be performed at all.
- **No live campaign was touched.** Every fixture is synthetic under `tmp_path`; the module,
  script, and tests never read a committed campaign directory, open a real registry, or import a
  `scripts/capacity_*.py` design constructor, and the verifier was not run against the pilot or
  confirmatory directories. The docs page warns that re-hashing a real campaign reads ~100 MB
  per cell and must not be aimed at an executing directory.
- The design constructor is imported, which executes the module's top level; the module docstring,
  the script docstring, and the docs page all state that only a trusted repository script may be
  passed, never a Python file that arrived with the campaign being verified.

**Gates.** 29 focused tests green; 2,848 `tests/unit` green; `ruff check src tests scripts`
clean; `ruff format --check` clean on the three touched Python files; `mypy src tests` clean over
801 source files; `git diff --check` clean. No UI file was touched, so `tests/ui` does not apply.

**Observed pre-existing flake (not from this claim).** On the first full-unit run,
`tests/unit/test_manchester_tfgm_acquisition.py::test_failures_never_replace_accepted_and_repeat_is_refused`
failed with `DID NOT RAISE ManchesterSnapshotError`. Its `snapshot_id` carries a one-second
timestamp (`tfgm_traffic_signals-\d{8}T\d{6}Z-<hash>`), so the two back-to-back acquisitions only
collide into `DESTINATION_EXISTS` when they land in the same wall-clock second. It passes in
isolation, in its own module, and on the immediate re-run of the full suite (2,848 passed). No
file in this claim touches Manchester code; recorded for the primary session, not repaired here.

### Phase 67 claim: dissertation results tables (parallel session, 27 July 2026)

Feature 28 of the batch-6 prompt: the two results tables the write-up quotes, generated only
through the accepted REP-01 exporter so no number is ever retyped by hand.

**Exclusive new files:** `scripts/generate_results_tables.py`,
`tests/unit/test_results_tables_script.py`, the generated
`docs/dissertation_appendices/tables/vec_capacity_squeeze_pilot_{arm_descriptives.tex,
predeclared_comparisons.tex,predeclared_comparisons.svg,provenance.md}`, its one `docs/index.md`
row, and this record. `src/traffictwin/reporting/latex.py` was read and not modified.

**What ships.** Per-arm descriptives (every arm × primary and secondary metric, with mean,
minimum, maximum and the per-seed values, each row labelled primary or secondary by which list of
the analysis it came from) and the predeclared comparisons (mean paired difference, bootstrap
interval with its confidence level, randomisation p-value, admitted pair count, and the estimate's
own interpretation). Both are `ResearchExportProjection` models rendered by
`write_projection_exports`; the script computes nothing.

**Boundaries.**

- **Values are copied at full round-trip precision.** Cells use `repr` of the recorded float, so
  a dissertation quote loses nothing. A test pins the choice by asserting that the six-significant-
  figure form of a fixture value differs from the emitted form and does not appear in the output.
  Absent statistics render as `unavailable`, never as `0`.
- **Labels are read from the artifacts, never inferred.** The exploratory/confirmatory stance and
  the research status come from the analysis payload's own type-level fields; the seed cohort comes
  from the sibling `campaign_receipt.json` and is reported as `undeclared` when no receipt is
  present. Recorded in the script, the provenance note, and here: the accepted analysis module
  fixes `confirmatory` to `False` for **every** campaign it analyses, so a held-out cohort is
  reported as a held-out cohort while the statistical stance still reads exploratory. Consuming a
  reserved cohort does not promote a result; signing the confirmatory protocol does.
- **The descriptives table ships without a figure, on purpose.** Its rows mix a success ratio with
  a latency in milliseconds, and the accepted exporter draws numeric entries on one shared linear
  scale, so a combined figure would misrepresent them. The provenance note states this and points
  at the per-metric figures under `dissertation_appendices/figures/`. The comparisons table does
  carry a figure: every paired difference it plots is in the primary endpoint's single unit.
- **Deterministic and non-clobbering.** No timestamp and no local path reaches any output;
  regeneration on unchanged input rewrote byte-identical files (verified against the committed
  set). Existing outputs are never replaced without `--overwrite`, and the analysis path is a
  required argument with no default, so the script cannot wander into an executing campaign.
- The exporter's 160-character caption/cell bound is handled by an explicit fit that truncates
  **and** records the truncation in the projection's own warnings, so a long experiment identifier
  can neither crash the run nor silently lose characters.

**Confirmatory half: PENDING, not skipped.** The precondition is a confirmatory results record
under `docs/evaluation/`; only `capacity_confirmatory_{candidate_a_null_descriptive,
candidate_b_latency_primary,protocol_draft}.md` exist, and the held-out campaign was still
executing during this batch (launcher alive, cell `cap-2.5-fs14` running, on-disk receipt still the
superseded `halted_on_failure` one from 16:39). The generator is phase-agnostic and needs no change
to run for the confirmatory payload: `uv run python scripts/generate_results_tables.py
<confirmatory>/campaign_analysis.json`. Nothing under `data/vec-fresh/capacity-confirmatory/` was
written, and no `capacity_*` evaluation document was touched.

**Gates.** 18 focused tests green; 2,866 `tests/unit` green; `ruff check src tests scripts` clean;
`ruff format --check` clean on both touched Python files; `mypy src tests` clean over 802 source
files; `git diff --check` clean. No UI file was touched, so `tests/ui` does not apply.

### Phase 68 claim: B1 bridge to the VEC-06 request shape (parallel session, 27 July 2026)

Feature 29 of the batch-6 prompt: the join between batch 2's `bus_trajectory` derivation and
VEC-06 preprocessing, so the B1 execution step has its input ready before signing.

**Exclusive new files:** `src/traffictwin/integration/manchester/bus_vec_bridge.py`,
`tests/unit/test_manchester_bus_vec_bridge.py`, and this record. `bus_trajectory` and the VEC-06
models are imported by full module path and neither is modified; no `docs/index.md` row was
added because the batch brief names none for this feature.

**What it assembles.** The dense motion arrays in the accepted `(T, maxN)` shape (`pos_x`,
`pos_y`, `speed`, `mask`, `times`, `dt`, `maxN`, `T` at the contract's exact dtypes), the
occupancy span table under the accepted header `sumo_vehicle_id, slot, t_enter, t_exit`, and a
`BusVecRequestDraft` that composes the accepted `VecFcdPreprocessRequest` once the caller supplies
the two raw-input digests.

**Boundaries.**

- **Construction only, and the type says so.** `vec06_admitted` is `Literal[False]` on both the
  draft and the result, with no code path that sets it otherwise; a test asserts the model refuses
  `True`. The composition literals ride through unchanged: `derived_scenario=True`,
  `observed_fcd=False`, `buses_only=True`. The output is an input FOR the accepted machinery,
  never a preprocessing receipt, an accepted trace, or admitted evidence.
- **RSU placement is not fabricated.** The accepted bundle also carries `rsu_xy`, `window`, and
  `sumo_seed`; `rsu_xy` is VEC-06's own reviewed placement stage's output, so the bridge emits the
  motion subset, names the three keys it does not emit in `UNBRIDGED_TRACE_KEYS`, and states why.
  A test asserts the emitted mapping and the unbridged keys are disjoint and together equal the
  full contract key set.
- **Two coordinate spaces kept visibly separate.** Occupancy `t_enter`/`t_exit` are **row indices**
  into the arrays (VEC-06 reconciles by `mask[t_enter : t_exit + 1, slot]`, inclusive), not
  absolute seconds; emitting seconds would corrupt every identity join by exactly
  `window_start_s`. Relatedly, `times` is `[0, 1, ..., T-1]` because the contract stores it as
  `float32`, which cannot separate consecutive epoch-scale seconds — a test makes that hazard
  explicit by asserting `float32(1_784_000_000) == float32(1_784_000_001)` and then showing the
  bridge loses nothing. The absolute base is recorded in `window_start_s` on both the arrays and
  the draft.
- **Slot assignment is deterministic and documented.** Each vehicle's track splits into contiguous
  runs (a dropped gap ends one run and starts another), runs are ordered by
  `(t_enter, vehicle_key, t_exit)`, and each takes the lowest slot free at its start second, with
  a slot freeing at `t_exit + 1`. Tests cover slot reuse after release, refusal to reuse while
  occupied, order-independence across input permutations, gap-dropped vehicles yielding one span
  per run, a third vehicle borrowing a slot inside another's gap, and exact mask/span
  reconciliation including both rejection directions (active cell without identity, identity on an
  inactive cell) and a double-claimed slot-second.
- **Sizes are checked before allocation** against the contract's timestep, concurrency, dense-cell,
  and observation ceilings, so an over-sized fleet is refused rather than allocated (the 1.28 GB
  lesson). An empty derivation and duplicate seconds for one vehicle are refused too.
- Session tokens are the vehicle ids, carried through unchanged; no raw reference, operator id, or
  vehicle registration is introduced anywhere. Nothing reads a file, opens a session artifact,
  calls BODS, touches a snapshot, or executes any part of VEC-06.

**Gates.** 29 focused tests green; 2,895 `tests/unit` green; `ruff check src tests scripts` clean;
`ruff format --check` clean on both touched files; `mypy src tests` clean over 804 source files;
`git diff --check` clean. No UI file was touched, so `tests/ui` does not apply.

**Shared-checkout note.** The lead's uncommitted `docs/project_guide.md` claim and index row were
in the working tree during this commit. Only `AGENTS.md` content equal to `HEAD` plus this claim
was staged, so the lead's in-flight edits stayed uncommitted and untouched in the working tree.

### Phase 70 claim: methodology diagram drafts (parallel session, 27 July 2026)

Feature 31 of the batch-6 prompt, documentation-only: three hand-authored schematics for the
dissertation's methodology chapter, each labelled DRAFT on its face.

**Exclusive new files:** `docs/dissertation_appendices/figures/diagrams/`
`{architecture_layers_draft.svg,manchester_data_flow_draft.svg,experiment_instrument_draft.svg,
README.md}`, its one `docs/index.md` row, and this record.

**What they show.** (a) The layered architecture — ingestion → canonical →
metrics/diagnostics/statistics → provenance → reporting → UI/CLI — with the "the UI never
computes" boundary drawn as an explicit labelled line between reporting and presentation. (b) The
Manchester chain — raw sources → quarantine → accepted snapshots → matching/demand → evidence
records — marking the two places it fails closed (nothing leaves quarantine unvalidated; accepted
snapshots are immutable and never replaced). (c) The experiment instrument — predeclaration →
byte-bound approval → campaign cells → fresh admission → registry → STA-01 → results record —
with four fail-closed points marked (digest changed, failed cell halts, unreviewed trace refused,
too few pairs → unavailable). Layer and stage names were checked against the actual packages and
the accepted contracts rather than drawn from memory.

**Boundaries.**

- **Illustrative drafts, and the README says so plainly.** No generator produced them, no script
  regenerates them, and no value in them was read from a receipt, an analysis payload, or the
  registry. The README draws the contrast with the neighbouring `figures/` and `tables/` output,
  which are generated through the accepted exporter and carry provenance notes naming a source
  digest; these carry none because there is no source payload to name. It also records that they
  are unreviewed, are not accepted documentation, and that where a diagram and the code disagree
  the code is right.
- **Self-contained and theme-neutral.** Plain rectangles, lines, polygons and text only. No
  external font file, stylesheet, script, image, or network reference — verified by parsing all
  three and asserting the SVG namespace is the only URL. Each paints its own light-neutral panel
  so it stays legible on a light or dark page; no fill is pure white or pure black (darkest ink
  `#1f2328`, lightest fill `#e6e8eb`). Boundaries and refusals are marked with dashed outlines
  rather than colour, so the meaning survives greyscale and colour-blind viewing.
- **No new scientific claim.** The diagrams assert structure and refusal points, not results. (c)
  ends by stating that completing the chain is software evidence rather than a finding, and that
  promotion from exploratory to confirmatory is a signed human decision and never a pipeline
  output. (b) states that bus observations are never relabelled as general road traffic and that
  absent measures stay explicitly unavailable.
- Every file was checked to be well-formed XML, and every text run was measured against the
  canvas so no label overflows its box or the viewBox.

**Gates.** Documentation-only, so no focused test applies; 2,895 `tests/unit` green;
`ruff check src tests scripts` clean; `mypy src tests` clean over 804 source files;
`git diff --check` clean. `ruff format` does not apply to SVG or markdown, and no UI file was
touched.

### Phase 71 claim: video narration script (parallel session, 27 July 2026)

Feature 32 of the batch-6 prompt, documentation-only: the spoken text for the committed
storyboard, so the recording is read rather than improvised.

**Exclusive new files:** `docs/video_narration_script.md`, its one `docs/index.md` row, and this
record. `video_storyboard.md`, `demo_checklist.md`, and the results record were read and none was
edited.

**What ships.** One narration block per storyboard shot, in shot order, each with an explicit
`[SCREEN: …]` cue — 12 cues against the storyboard's 12 shots, verified to match. A timing table
budgeted at 140 words per minute with per-shot word counts, speech length, and headroom, plus a
caveat-placement table.

**Boundaries.**

- **Every measurement in the file was computed, not estimated.** Word counts, per-shot speech
  lengths, headroom, and the total were derived by counting the blocks programmatically and
  written back into the document, so the table cannot drift from the text above it. Total spoken
  is **837 words ≈ 5:58** under the storyboard's 7:00 picture — inside the ≤ 8-minute ceiling.
- **The nine required spoken caveats appear word for word**, verified by string comparison against
  the `Required Spoken Caveats` section of `demo_checklist.md`, at their storyboard positions
  (shots 2, 3, 6, 8, 9, 11, and the two conditional ones held back as conditional). Two initially
  read with a lowercased first letter to fit mid-sentence; the sentences were restructured so the
  checklist wording is reproduced exactly. Where the storyboard paraphrases a caveat in its own
  list, the file records that the checklist wording is the authority.
- **The one-sentence pilot framing is quoted exactly** from `capacity_pilot_results_20260727.md`,
  including the correction that record carries, verified by string comparison.
- **No new scientific claim, and numbers appear in exactly one place.** The framing quotation in
  shot 12 is the only spoken number anywhere in the script, read as an attributed quotation with
  the record on screen. Everywhere else the speaker names a record. The storyboard's shot-11 rule
  ("name the records; do not read their numbers") is honoured — the quotation was placed at shot
  12 instead, and the file explains why.

**One unresolved conflict, flagged rather than papered over.** Shot 12 does not fit its slot. The
storyboard allots the wrap 0:25; the mandatory verbatim framing sentence is about 0:20 by itself
and still needs an attribution phrase and the closing limitation the storyboard says to end on.
Trimmed to the minimum that keeps all three, the block measures **0:28 — three seconds over**, and
the timing table shows it as `−0:03` rather than rounding it away. Two resolutions are laid out as
owner decisions (give shot 12 five seconds from shot 8 or 10, which carry +0:10 each; or drop the
closing limitation, which is the worse trade), because `video_storyboard.md` is outside this
feature's file set and was not edited. The file states that speaking faster or paraphrasing the
quotation are not acceptable fixes.

**Gates.** Documentation-only, so no focused test applies; 2,895 `tests/unit` green;
`ruff check src tests scripts` clean; `mypy src tests` clean over 804 source files;
`git diff --check` clean. `ruff format` does not apply to markdown, and no UI file was touched.

### Completed lead ownership: repository owner project guide (27 July 2026)

- The lead completed the read-only repository and local-context audit and owns only
  `docs/project_guide.md`, its Getting Started index row, and this note; no code, runtime data,
  external clone, generated artifact, capability state, or digest-bound evidence changed.

### Phase 80 claim: detailed capacity-finding narrative (owner-directed, 27 July 2026)

The owner directed a long-form public record of the capacity finding — environment,
instrument, knob semantics, execution record, per-seed results tables, mechanism, and
interpretation — as the narrative companion to the concise results record. Interpretive
content is explicitly confidence-labelled (the tail-truncation reading is marked
checkable-but-unchecked); every number traces to committed or hash-verified artifacts;
all ceilings and the range-overlap correction are carried. Exclusive files:
`docs/evaluation/capacity_study_detailed_findings.md`, its `docs/index.md` row, and this
record.

### Phase 81 claim: future research directions v2 (owner-directed, 27 July 2026)

Proposals-only strategy document tiered by cost and gating: within-dissertation options
(three-trace grid, crossover, stadium, the latency-tail analysis, RSU asymmetry), the GPU
track (capacity-aware retraining via the producer's capacity-scalar observation variant,
bus-native trace-replay training, reward-engineering variants, the train-×-evaluate
matrix) with its venue and permission constraints stated, and platform directions
(own-network experiments, the methodological claim, multi-city, the separated agentic
layer, sensor validation). Nothing executes from it; every direction requires its own
predeclaration and approval. Exclusive files: `docs/research_directions_v2.md`, its
`docs/index.md` row, and this record.

### Phase 82 claim: Codex GPU-track technical recommendation (owner-directed, 27 July 2026)

The owner directed Codex to incorporate its read-only GPU-track audit into the v2 research
directions and push the result. This documentation-only amendment corrects the meaning of the
producer's `capscalar` variant, distinguishes aggregate-rate equality from unmeasured keyed
action-sequence equality, reconciles the newer start-now coding brief with the earlier sequencing,
and records a matched B-CAP design, implementation prerequisites, execution route, and B-BUS
boundaries. Nothing in the amendment approves an experiment, moves producer/bus assets, admits a
checkpoint, or changes a capability, pin, scientific result, or evidence label. Exclusive files:
`docs/research_directions_v2.md` and this record.

### Phase 83 claim: keyed action-sequence comparison (28 July 2026)

The Phase 82 audit correctly distinguished measured aggregate-rate equality from
unmeasured action-sequence equality. The keyed comparison was run read-only over the
twelve admitted pilot cells' published per-step arrays: within every fleet seed, the
per-second per-vehicle-slot actions and their RSU/V2V targets are element-wise identical
across all four capacity arms — zero mismatches in 8,956,800 cells for each of the nine
arm pairs. Evidence:
`docs/integration/evidence/vec_pilot_keyed_action_comparison_20260728.json`; dated
measured-upgrade addenda in the detailed findings record and the v2 research directions.
Nothing was written to campaign directories or registries. Exclusive files: the evidence
record, the two addenda, and this record.

### Phase 86 claim: first Colab B-CAP synthetic smoke (owner-directed, 28 July 2026)

The owner directed Codex to write the first Google Colab experiment. This slice owns a
synthetic-only B-CAP engineering smoke: a testable pure-JAX driver, a Colab notebook wrapper,
operator documentation, and focused unit tests. It randomizes the pilot capacity grid and compares
matched 17-D hidden-capacity versus 19-D explicit-capacity/load toy policies over five model seeds,
but it is deliberately not MAPPO, not producer-environment execution, and not scientific evidence.
It refuses to consume Randy's repositories, TOS checkpoints, real traces, bus artifacts, or any
local campaign bytes; its manifests make those exclusions and the non-admissible diagnostic status
machine-readable. The live confirmatory launcher remains untouched and only a tiny bounded CPU
test may run locally. Exclusive files: new `gpu/__init__.py`, `gpu/README.md`,
`gpu/colab/__init__.py`, `gpu/colab/bcap_synthetic_smoke.py`,
`gpu/colab/bcap_synthetic_smoke.ipynb`, `tests/unit/test_bcap_synthetic_smoke.py`, and this
record. No external repository, project pin, evaluator, campaign, registry, evidence artifact,
generated reference, or shared documentation index is edited.

### Phase 87 claim: second Colab B-BUS synthetic trace-replay smoke (owner-directed, 28 July 2026)

The owner directed Codex to do the second Google Colab experiment. This slice owns the
permission-safe B-BUS precursor: a pure-JAX synthetic trace-replay driver, Colab notebook,
operator documentation, and focused tests. It generates deterministic bus-like and general-traffic
motion fixtures in memory, trains matched toy policies on each synthetic domain over at least five
model seeds, and evaluates the resulting checkpoints on a common two-domain matrix. It is not
MAPPO, not real-bus training, not producer-environment execution, and not scientific evidence.
It refuses real traces, uploads, Drive mounts, Randy's repositories, BODS or derived bus bytes,
local campaign artifacts, and quarantine material; outputs permanently record their synthetic,
diagnostic, non-admissible status. The live confirmatory launcher remains untouched and only a tiny
bounded CPU fixture may run locally. Exclusive files: new
`gpu/colab/bbus_synthetic_trace_smoke.py`,
`gpu/colab/bbus_synthetic_trace_smoke.ipynb`,
`tests/unit/test_bbus_synthetic_trace_smoke.py`, additions to `gpu/README.md`, and this record.
No external repository, project pin, evaluator, campaign, registry, evidence artifact, generated
reference, or shared documentation index is edited.

### Phase 84 claim: observability-gap probe (28 July 2026)

Read-only mechanism probe answering the "could the invariance be a quirk" challenge:
across all seeds and arm pairs, RSU-side state differs in 134,278 of 324,000 RSU-second
cells while the vehicle-side arrays the observation draws on show zero mismatches —
combined with the documented observation content (no RSU-load input), the
capacity-invariance is structural observation-space blindness, with the code-level
observation-builder confirmation recorded as the remaining check and a falsifiable
prediction recorded for the crossover study (the baseline actor should be equally
invariant). Evidence: `docs/integration/evidence/vec_pilot_observability_gap_20260728.json`;
dated mechanism addendum in the detailed findings record. Exclusive files: those two plus
this record.

### Phase 85 claim: producer code-permission record (28 July 2026)

The owner relayed the producer's statement permitting use of his code with citation. The
record keeps the conservative scope split — code (covered, any venue, cited) versus data
blobs off-machine and publication of data-derived aggregates (still the drafted email's
open asks) — states the citation obligations, and lists what it unlocks (B-CAP on real
code on Colab; B-BUS on our own bus data) versus what stays local/CSF-only. Relayed
provenance, to be superseded by the producer's written form. This claim also records
ownership of `CODEX_GPU_TRACK_BRIEF.md` (committed `d718eb5` under the same owner
delegation, record omitted at the time). Exclusive files: 
`docs/integration/randy_code_permission_20260728.md`, its `docs/index.md` row, the brief,
and this record.

### Phase 86 claim: confirmatory results record (28 July 2026)

The held-out campaign completed 10/10 (7 admitted + 3 resume-confirmed, zero failures,
design fingerprint verified). The confirmatory primary — mean paired latency difference
−8,310.9 ms, bootstrap [−9,097.5, −7,524.3], all five held-out seeds in the predeclared
direction, randomisation p at the n=5 floor — is recorded under the signed candidate (b)
digest, rendered through the gated confirmatory renderer (all refusal checks passed),
with the deadline null and capacity-invariance replications reported descriptively and
the interruption/repair history preserved as reproducibility evidence. Held-out seeds
{10–14} are recorded as spent for capacity studies. Exclusive files:
`docs/evaluation/capacity_confirmatory_results_20260728.md`, the committed render
`docs/evaluation/capacity_confirmatory_report_20260728.md`, their `docs/index.md` rows,
and this record.

### Phase 87 claim: session context prompt v2 (owner-directed, 28 July 2026)

The owner asked for the complete current context in one agent-bootstrap document so a
fresh session can continue everything — including running the attended peak bus session
on the owner's word — as this session's context fills. `CLAUDE_SESSION_CONTEXT_PROMPT_V2.md`
(repo root) carries the confirmed finding and mechanism, the framing and scope decisions,
the attended-session procedure with the attendance rule stated as unbreakable, the
unblocked work queue, the decision queue, boundaries, and gotchas; it supersedes the v1
prompt. Exclusive files: that prompt and this record.

### Phase 88 claim: B-CAP smoke artifact preservation (28 July 2026)

Codex's Colab engineering smoke (real producer code under the recorded citation
permission; producer data never moved; VM terminated) proved the B-CAP plumbing: a 17-D
control trained with capacity hidden is exactly invariant across capacity levels —
independently reproducing the observability-gap mechanism in a from-scratch policy —
while the 19-D capacity-observation variant demonstrably changes decisions with capacity.
The short-run performance numbers are explicitly non-evidence. The artifact zip was
copied from volatile /tmp to data/gpu-track/ and its SHA-256 re-verified
(885f6914…). Exclusive files: docs/integration/evidence/bcap_engineering_smoke_20260728.json
and this record.

### Phase 90 claim: full B-CAP G4 training campaign (owner-directed, 28 July 2026)

The owner explicitly directed Codex to execute the full data-free B-CAP training experiment and
requested a Colab G4 GPU. Codex owns an isolated, code-only campaign slice: a fail-closed
transformation of the audited producer JAX environment, the matched 17-D hidden-capacity and 19-D
capacity/headroom MAPPO launch matrix (five model seeds each, five million requested timesteps),
deterministic manifests and resumable status, a predeclaration frozen before outcomes, its
byte-bound owner-delegation receipt, focused tests, and this record. Producer data, traces,
checkpoints, the pinned external clones, local scientific campaign directories, registries, and
the byte-frozen confirmatory candidate remain untouched. Training curves are diagnostics; returned
actors remain non-admitted and the label ceiling is `owner_approved_candidate` pending reviewed
checkpoint homecoming and separately admitted local evaluation. Exclusive files:
`gpu/real_bcap/{__init__.py,prepare_source.py,run_campaign.py,README.md}`,
`tests/unit/test_bcap_real_campaign.py`,
`docs/evaluation/bcap_training_predeclaration_20260728.md`,
`docs/evaluation/bcap_training_approval_20260728.json`, and this claim.

### Phase 91 claim: full B-REWARD G4 training campaign (owner-directed, 28 July 2026)

The owner directed Codex to execute the next runnable GPU experiment after B-CAP. B2 remains
blocked by the attended bus session and signed bus-data gates, so Codex owns the data-free B3
reward-ablation slice: two matched 19-D capacity-aware from-scratch MAPPO treatments using the
producer's documented constant-alpha values 0.7 and 1.0, fresh model seeds {200–204}, five million
requested steps per job, and a common 32-episode x four-capacity fixed-grid diagnostic. The exact
design and harness are byte-bound before outcomes. Producer data, bus bytes, checkpoints, external
clones, local scientific campaigns, registries, and the confirmatory digest-bound candidate remain
untouched. Returned actors and diagnostics are non-admitted `owner_approved_candidate` outputs.
Exclusive files: `gpu/real_breward/{__init__.py,evaluate_fixed_grid.py,run_campaign.py,README.md}`,
`tests/unit/test_breward_real_campaign.py`,
`docs/evaluation/breward_training_{predeclaration_20260728.md,approval_20260728.json}`, and this
claim.

### Phase 89 claim: three-trace capacity grid + ev timing probe (owner-directed, 28 July 2026)

Under the standing delegation, reaffirmed in session ("I want to do some experimenting
now"): the A1 grid predeclaration (we + ev, pilot-mirroring arms, fresh seeds {50-52},
exploratory, mechanism predictions recorded in advance as falsifiable), the single ev
timing probe answering ADR-065's open risk (timing evidence only, no admission), and the
grid campaign launcher binding the predeclaration digest with held_out_authorised=False.
Exclusive files: docs/evaluation/capacity_grid_predeclaration.md and its docs/index.md
row, scripts/ev_timing_probe.py, docs/integration/evidence/vec_ev_timing_probe_20260728.json,
scripts/capacity_grid_campaign.py, plus this record.

### Phase 90 claim: three-trace grid results record (28 July 2026)

Both grid campaigns completed 12/12 with zero failures. On the weekend and event-night
traces every metric is exactly identical across all four capacity arms in every seed
(paired differences literally zero) — the predeclared mechanism predictions held, and the
three regimes now separate policy blindness (everywhere, structural) from outcome
sensitivity (only where load saturates the concurrency bound: 2,488-slot collapse hour
yes; 139/175-slot regimes no; threshold bracketed, not located). Exclusive files:
docs/evaluation/capacity_grid_results_20260728.md, its docs/index.md row, and this record.

### Phase 91 claim: integration handoff + changelog reconciliation (28 July 2026)

`CODEX_INTEGRATION_HANDOFF.md` (repo root) gives the lead the review range, claim map,
gate evidence, absolute hazards (external clones never fetched; the byte-frozen signed
candidate; evidence stores read-only; a B0 campaign possibly in flight), the fast-forward
procedure, and the untouched owner decision queue. The changelog's in-development section
gains the 27-28 July research-arc block. Exclusive files: the handoff document,
CHANGELOG.md's new block, and this record.

### Phase 92 claim: weekday admissions + sweep completion + deep-squeeze onset (28 July 2026)

Under the standing delegation: both weekday peak pairs probed (read-only, exact Gate-A
match, snapshots reconcile: wd_am T=10,800/maxN=215, wd_pm T=25,200/maxN=163 — both LOW
density, itself a district-trace-set finding) and admitted as ADR-066 with the allowlist
pinned to exactly five; the sweep-completion + deep-squeeze predeclaration fixes
predictions in advance (peaks inert like we/ev; ev-deep arms {0.5, 0.25, 0.1} measure the
binding onset or its absence); launcher specs added with per-spec arms. Exclusive files:
the two allowlist maps and their tests, the campaign-test unknown-hash literal, ADR-066 +
probe evidence + index rows, the vec_fresh_run_admission.md wording,
docs/evaluation/capacity_sweep_completion_predeclaration.md + index row, the
scripts/capacity_grid_campaign.py extensions, and this record.

### Phase 93 claim: B0 verdict record (28 July 2026)

B0 completed 12/12: the baseline actor is exactly as capacity-invariant as the
ukfleettrain actor on the event-night trace (all metrics identical across arms in every
seed), so the predeclared prediction HOLDS and the observability-gap mechanism stands on
four independent legs. The identical-fleet descriptive actor contrast is recorded without
any ranking claim. Exclusive files: docs/evaluation/baseline_invariance_results_20260728.md,
its docs/index.md row, and this record.

### Phase 94 claim: full B-MASK G4 training campaign (owner-directed, 28 July 2026)

The owner directed Codex to execute the next runnable data-free training experiment after
B-REWARD. B4 remains Colab-blocked because recorded producer permission covers code but not
producer trace bytes. Codex therefore owns the separately predeclared action-masking factor from
the B-CAP recommendation: capacity-aware MAPPO trained with the producer feasibility mask off/on,
fresh paired model seeds {300–304}, five million requested steps per job, and a common two-mode ×
four-capacity diagnostic that evaluates every checkpoint both with and without deployment
masking. The design distinguishes learned-policy effects from runtime enforcement, and fails if a
masked deployment selects any infeasible action. Producer data, bus bytes, checkpoints, external
clones, local scientific campaigns, registries, and held-out cohorts remain untouched. Outputs
are non-admitted `owner_approved_candidate` diagnostics. Exclusive files:
`gpu/real_bmask/{__init__.py,evaluate_mask_grid.py,run_campaign.py,README.md}`,
`tests/unit/test_bmask_real_campaign.py`,
`docs/evaluation/bmask_training_{predeclaration_20260728.md,approval_20260728.json}`, and this
claim.

### Phase 95 claim: full B-DOMAIN G4 training campaign (owner-directed, 28 July 2026)

The owner directed Codex to execute the next data-free experiment after B-MASK. The literal B4
trace matrix remains Colab-blocked by producer trace-data permission, so Codex owns a code-only
procedural distribution-shift precursor using the producer's built-in task-mixture variants:
default, safety-dominant, and pilot-inspired. The frozen matrix trains five fresh capacity-aware,
unmasked, balanced-reward MAPPO checkpoints per domain (seeds {400–404}; 15 full jobs) and
evaluates every checkpoint on all three domains at baseline and squeezed RSU capacity with common
keys. Uniform is excluded before outcomes to preserve five-seed replication and full budgets
within the compute envelope. Producer data, traces, bus bytes, checkpoints, external clones,
scientific campaigns, registries, and held-out cohorts remain untouched. Outputs are non-admitted
`owner_approved_candidate` diagnostics. Exclusive files:
`gpu/real_bdomain/{__init__.py,evaluate_domain_matrix.py,run_campaign.py,README.md}`,
`tests/unit/test_bdomain_real_campaign.py`,
`docs/evaluation/bdomain_training_{predeclaration_20260728.md,approval_20260728.json}`, and this
claim.

### Phase 95 claim: session context prompt v3 (owner-directed, 28 July 2026)

Context-full handoff: `CLAUDE_SESSION_CONTEXT_PROMPT_V3.md` (repo root) carries the
morning-of-28-July state — the confirmed finding, the four-legged mechanism, the
unanimous five-regime sweep, the in-flight ev-deep onset leg, Codex's four GPU campaigns
with preserved artifacts, the live attended bus sessions and their processing steps, the
morning queue, and the Phase-91 numbering collision note. Supersedes V2. Exclusive files:
that prompt and this record.

### Phase 96 claim: sweep-completion results record (28 July 2026)

All three legs 12/12, zero failures. Weekday peaks exactly inert (predictions held);
the deep-squeeze leg located the binding onset between cap-0.25 and cap-0.1 on the
event regime — the first non-identical outcomes in a normal regime, in the collapse
hour's direction, with decisions invariant throughout. Exclusive files:
docs/evaluation/capacity_sweep_completion_results_20260728.md, its docs/index.md row,
and this record.

### Phase 97 claim: consolidated experiments-and-findings register (owner-directed, 28 July 2026)

One register of every experiment across the capacity programme, the GPU training track,
and the bus sessions, each row linking its full record and carrying its ceiling.
Exclusive files: docs/experiments_and_findings_20260728.md, its docs/index.md row, and
this record.

### Phase 98 claim: session context prompt v4 (owner-directed, 28 July 2026)

Afternoon handoff superseding V3: the completed capacity programme, both captured-but-
unprocessed bus sessions with the recurring rush-hour PARSE_REJECTED finding and the
exact post-hoc processing recipe, Codex's B-MASK completion and B-DOMAIN start, the
consolidated experiments register, and the afternoon queue. Exclusive files:
CLAUDE_SESSION_CONTEXT_PROMPT_V4.md and this record.

### Phase 99 claim: post-hoc bus-session measurement + identity-scope correction (owner-directed, 28 July 2026)

The owner directed the primary integration agent to process, without new acquisition or
attendance, the durable 28-July dawn and rush-hour BODS snapshot sets into B1's measured
numbers. The first read-only reduction exposed a real long-session defect hidden by the
15-snapshot probe: `VehicleRef` is not globally unique across operators, so the v1.0
session token merged 7 dawn and 9 peak cross-operator references and manufactured
17–19 km/s maxima. The two rush-hour MAN-05 refusals have the same root shape: one
raw-ref/time group contains two conflicting activities from different operators; the
conflict disappears when identity is operator-scoped. This slice therefore amends only
the layered session-identity policy to v1.1 (`HMAC(salt, OperatorRef || NUL ||
VehicleRef)`), retains read compatibility for the historical v1.0 aggregate, and leaves
the lead-owned MAN-05 parser and both rejected quarantines untouched.

The new post-hoc command selects an explicit inclusive snapshot-id range, generates one
fresh in-process salt, verifies every quarantine member before extraction, and writes
only cadence/progression aggregate JSONs into a session-specific private workspace view.
The accepted report command then renders each view without opening snapshots. The result
record compares night/dawn/peak density, maps measured values onto B1 as **proposals only**,
and records both `PARSE_REJECTED` events as a data-quality finding; no B1 experiment runs,
no G1–G5 decision is taken, and buses remain buses.

**Measured outcome:** all three views verified against their committed hashes. Active
session support is night/dawn/peak **41 / 1,162 / 1,433** (dawn 28.3× night; peak
35.0× night and 23.3% above dawn), while cadence stays stable at median 66–68 s / p90
75–76 s. Peak contains 52 verified quarantines (51 MAN-05 promotions + the final
refusal). Its corrected 64.7 m/s maximum means the proposed 32 m/s B1 gate needs an
owner-signed outlier rule; the recommendation is recorded, not taken. Focused gates:
49 tests, ruff clean, strict mypy clean, and evidence-to-private-artifact hashes exact
for 3/3 sessions.

**Exclusive files:** amendment to
`src/traffictwin/integration/manchester/bods_session_identity.py` and its unit test;
`scripts/process_bus_session_posthoc.py` and its unit test;
`docs/integration/evidence/bods_bus_sessions_20260728.json`;
`docs/evaluation/bus_session_results_20260728.md`; proposed-value amendments to
`docs/evaluation/bus_fleet_experiment_predeclaration_draft.md` and
`docs/evaluation/bus_data_experiment_options.md`; the bus rows in
`docs/experiments_and_findings_20260728.md`; their `docs/index.md` entries; and this
record. Private workspace measurements and reports are untracked aggregate evidence;
their hashes are recorded in the committed evidence JSON.

### Phase 100 claim: B-MASK/B-DOMAIN volatile campaign preservation (owner-directed, 28 July 2026)

The primary integration agent owns the narrow preservation and provenance reconciliation
for Codex's completed B-MASK and B-DOMAIN full G4 campaign archives. The exact volatile
`/private/tmp` ZIP bytes are copied into the gitignored `data/gpu-track/` workspace,
verified by SHA-256 and ZIP integrity, and described by committed evidence records. The
archives and checkpoints remain private, non-admitted diagnostics: preservation does not
authorise a scientific verdict, actor admission, producer-data use, the literal trace B4
experiment, an external send, or any owner decision.

**Exclusive files:**
`docs/integration/evidence/bmask_full_campaign_preservation_20260728.json`,
`docs/integration/evidence/bdomain_full_campaign_preservation_20260728.json`, the B-MASK
and B-DOMAIN rows in `docs/experiments_and_findings_20260728.md`, their `docs/index.md`
entries, and this record. The copied ZIPs under `data/gpu-track/` are gitignored private
workspace artifacts and are not repository evidence bytes.

### Phase 101 claim: cross-regime capacity-response dissertation figure (owner-directed, 28 July 2026)

The primary research/integration agent owns one deterministic dissertation figure that
places the completed five-regime capacity results on aligned density and latency-response
axes, with the event-night deep-squeeze onset shown separately at its true smaller scale.
The projection is bound to the six completed campaign-analysis hashes and the generated
trace-audit hash; it may derive only transparent paired mean differences from recorded
per-seed values. It remains descriptive, non-causal, and `owner_approved_candidate`; the
figure does not turn exploratory regimes into confirmatory evidence or imply a city-wide
Manchester result.

**Exclusive files:** `scripts/generate_cross_regime_capacity_figure.py`, its focused unit
test, `docs/integration/evidence/vec_cross_regime_capacity_projection_20260728.json`, new
files under `docs/dissertation_appendices/figures/cross_regime/`, the corresponding
`docs/index.md` entry, and this record.

### Phase 102 claim: Week-4→5 owner checkpoint and integration handoff refresh (owner-directed, 28 July 2026)

The primary research/integration agent owns a documentation-only reconciliation of the
Week-4 checklist, owner action drafts, and Codex fast-forward handoff after completion of
the capacity programme, bus-session processing, GPU archive preservation, and cross-regime
figure. The checkpoint may present recommendations and exact branch state, but it cannot
send communications, sign a protocol, approve a re-pin, fast-forward the official branch,
or record a supervisor decision that has not been received.

**Exclusive files:** `docs/current_progress_week5.md`, amendments to
`docs/owner_action_pack_20260727.md` and `CODEX_INTEGRATION_HANDOFF.md`, their
`docs/index.md` entries, and this record. No experiment design, evidence bytes, source
contract, generated reference, campaign artifact, registry, or external repository is
changed.

### Phase 103 claim: ADR-066 dissertation-appendix regeneration (28 July 2026)

The primary integration agent owns the mechanical regeneration of Appendix A after the
committed ADR register gained accepted ADR-066. The existing generator and its inputs are
unchanged; the only authorised output delta is the missing ADR-066 row and decision count
65→66. This hygiene slice makes the focused appendix freshness gate current and takes no
scientific or owner decision.

**Exclusive file:** `docs/dissertation_appendices/appendix_a_capability_catalogue.md` and
this record.

### Phase 104 claim: bus-session interpretation section (owner-directed, 28 July 2026)

The owner directed that the meaning of the processed bus measurements be recorded beside
them. An interpretation section was appended to the Phase-99 results record: the
possible placement of an observed bus fleet inside the capacity study's unresolved
density band (explicitly an inference, with the offline concurrency computation named as
the step that would settle it), cadence stability closing B1's interpolation risk, the
displacement-versus-density consistency signal, the identity defect framed as an averted
silent corruption, the collection constraint the parser refusals impose, and the
statements the sessions cannot support. Measured, inferred, and open claims are labelled
separately; no measurement, ceiling, or boundary in the original record was altered.
Exclusive files: the appended section in
`docs/evaluation/bus_session_results_20260728.md` and this record.

### Phase 105 claim: N1 re-examination and peak-concurrency measurement (owner-directed, 28 July 2026)

Two offline checks. (1) **N1 as recorded is withdrawn**: the on-disk dated extract is
50,502,348 bytes / md5 `c73b16ec…`, matching the provider's published checksum and the
first acquisition record exactly; the 996.9 MB / `233af3fa…` identity was the *decoded
XML*, stored in the second record's source fields, so its md5 was compared against the
compressed file's checksum and could never reconcile. Decoding the on-disk file today
reproduces the recorded decode identity byte-exactly (2.665 s). No provider mutation
occurred, the network chain is rebuildable without a forced identity change, and no
Geofabrik-mutation claim may be published. (2) **Peak concurrency measured**: 1,216 max /
1,192 median concurrently live over 52 quarantines, placing the observed fleet inside the
capacity sweep's unresolved band. Exclusive files:
`docs/integration/evidence/n1_reexamination_and_peak_concurrency_20260728.json`, the dated
correction in `docs/integration/manchester_workspace_continuity_20260727.md`, the promoted
subsection in `docs/evaluation/bus_session_results_20260728.md`, and this record.

### Phase 106 claim: artifact-integrity guards (owner-directed, 28 July 2026)

The preventive control for the Phase-105 finding. New
`src/traffictwin/integration/manchester/artifact_integrity.py` refuses the two shapes
that let a wrong network identity propagate: a record whose source and derived identities
coincide (`SOURCE_DERIVED_IDENTITY_COLLISION` / `SOURCE_DERIVED_SIZE_COLLISION` — the
exact 25-July defect, verified to fire on the real record), and a later-phase dependency
on a session-scoped or system-temporary path (`EPHEMERAL_DEPENDENCY_REFUSED` — the reason
the network chain vanished). It also verifies a recorded identity against the on-disk
file. No acquisition, no decode, no network access; a passing audit is never an
admission. The acquisition path already failed closed on provider-checksum mismatch
(`CHECKSUM_IDENTITY_DRIFT`), so no change was needed there. Exclusive files: that module,
`tests/unit/test_manchester_artifact_integrity.py` (7 tests), and this record.

### Phase 107 claim: approved dawn-to-peak real B-BUS campaign (owner-directed, 28 July 2026)

The primary research/integration agent owns the explicitly approved private-Colab
B-BUS experiment that derives a bus-only scenario from the two already captured
Manchester sessions, trains on dawn, and evaluates once on held-out peak.  The
frozen choices are: 120 s gap ceiling, 15 m dwell radius, 80% matched-fix share,
32 m/s implied-speed ceiling with violating segments dropped and counted,
capacities 2.5 and 0.75, and common seeds 30--34.  Only derived,
pseudonymised trace bytes may leave the local processing boundary for the owner's
private Colab; raw BODS material, raw identifiers, session salts, and cross-session
identity links may not.  Buses remain a derived scenario rather than observed FCD
or general traffic, and returned GPU bytes remain non-admitted diagnostics until
their hashes, protocol binding, and held-out evaluation are independently checked.
This claim records owner approval but does not take a supervisor decision, public
hosting decision, actor-admission decision, or scientific verdict.

**Exclusive files:** new
`docs/evaluation/bbus_dawn_peak_protocol_20260728.md`, B-BUS dawn/peak evidence
records under `docs/integration/evidence/`, new campaign-specific bus trace
preparation code and focused tests, new files under `gpu/real_bbus/`, the focused
real-B-BUS campaign test, the exact B-BUS dawn/peak row in
`docs/experiments_and_findings_20260728.md`, its `docs/index.md` entries, and this
record.  This phase does not own or edit `scripts/rebuild_baseline_network.py`;
it may consume a later committed, verified network artifact from that disjoint
ownership slice.

### Phase 108 claim: baseline network rebuilt into a durable location (28 July 2026)

Acting on Phase 105 (the chain was always rebuildable) with the Phase 106 guards applied
before any expensive step. `scripts/rebuild_baseline_network.py` verifies the extract
against its recorded identity, refuses an ephemeral destination, refuses a source/derived
identity collision, decodes, and builds.

**Result: the rebuild reproduces the original network exactly.** The decode returns
996,913,352 bytes / `233af3fa…` byte-for-byte, and the built network's canonical identity
is `ce285f85d07fee24414cc3318cf85ea1ca0cb967e2eadb2ac7bcb3f96bde2577` — identical to the
25-July record. Raw bytes differ by 2 (1,248,945,776 vs 1,248,945,774) solely through
netconvert's generation banner, which is exactly why the canonical comment-stripped digest
is the recorded identity. The network lives under durable
`data/network-build/gm-baseline-20260728` with a receipt, not a session scratchpad. N1 no
longer gates the demand cascade or B1 map matching, and no new network identity was forced.

**Two defects met and recorded, neither fixed here.** (1) `decode_pbf_to_osm_xml` runs
osmium with `cwd` set to a private staging directory, so a *relative* source path cannot
resolve; callers must pass absolute paths (the script does, with a comment). (2) After a
successful decode, the module's receipt handling raises `TypeError: Object of type date is
not JSON serializable`, so a decode producing a byte-correct artifact still reports
`DECODE_FAILED`; the caller must reuse the artifact on a second pass. Both are in accepted
lead-owned `network_decode.py`, left untouched for a lead/Codex slice. Exclusive files:
`scripts/rebuild_baseline_network.py` (committed at `03f4316`) and this record.

### Phase 109 claim: approved paired B-BUS successor campaigns (owner-directed, 28 July 2026)

After the full-region VEC-06 placement refusal, the owner explicitly chose **both** offered
successors. The primary research/integration agent owns two separately labelled dawn-to-peak
campaigns: (1) a fixed 750 m capsule around the pre-existing St Peter's Square--University of
Manchester landmark line, with deterministic full-coverage placement separately verified for
both windows; and (2) the unchanged whole-fleet trace with exactly 64 sparse analysis sites
selected from dawn vehicle-seconds only and reused unchanged at peak. The corridor is frozen
before inspecting its bus counts. The sparse arm is exploratory and outside accepted VEC-06;
it cannot inherit the corridor arm's contract status. Both preserve the Phase-107 trajectory,
privacy, seed, capacity, training, held-out, hardware, and claim ceilings. No new acquisition
or attendance is authorised, and neither campaign takes a supervisor verdict, actor admission,
public-hosting decision, or scientific conclusion.

**Exclusive files:** new paired-successor protocols and owner-approval evidence under
`docs/evaluation/` and `docs/integration/evidence/`; new successor transformation/placement
code and focused tests; `scripts/prepare_bbus_successors.py`; new files under
`gpu/real_bbus/`; the exact paired-result rows in
`docs/experiments_and_findings_20260728.md`; related `docs/index.md` entries; and this record.
Private derived outputs remain below gitignored `data/` and are never committed.

### Phase 110 claim: latency-tail analysis (owner-directed, 28 July 2026)

Analysis-only over the 12 admitted pilot cells' per-task arrays (39.2M active tasks per
arm). Settles the previously unverified tail-truncation interpretation: p50 is 44.3 ms at
every capacity level (-0.10% across the 3.3x squeeze), the >1 s population moves only
-0.07 pp, but p99 falls 69.9% and 97.9-99.4% of latency mass sits above 1 s. The squeeze
moves latency only within the already-deadline-failed population, which is precisely why
the confirmed -8.3 s mean effect coexists with a flat deadline rate. Records that mean
latency is ~99% tail mass and that future protocols should predeclare a percentile or
tail-share endpoint beside it, without weakening the predeclared confirmed result.
Exclusive files: `docs/evaluation/latency_tail_analysis_20260728.md`, its `docs/index.md`
row, and this record.

### Phase 111 claim: per-RSU load asymmetry (owner-directed, 28 July 2026)

Analysis-only over the admitted pilot cells' per-step rsu_load arrays. Three of ten RSUs
carry exactly zero load at every capacity level and a fourth carries under 5%, while the
busiest carries ~24%; Gini moves only 0.486 -> 0.467 across the 3.3x squeeze, so the
control does not redistribute load - consistent with the observation-gap mechanism. Total
load falls 3.2x, tracking the latency-tail collapse. Answers the producer's Study Case 1
question descriptively; placement remains VEC-06 generated and is never presented as
verified Manchester infrastructure. Exclusive files:
`docs/evaluation/rsu_load_asymmetry_20260728.md`, its `docs/index.md` row, and this record.

### Phase 112 claim: session context prompt v5 and register refresh (owner-directed, 28 July 2026)

Resume set for a fresh session: `CLAUDE_SESSION_CONTEXT_PROMPT_V5.md` supersedes V4 and
carries the closed capacity mechanism (including the measured latency-tail result and the
"mean latency is ~99% tail mass" caution), the withdrawn N1 with its explicit prohibition
on repeating the provider-mutation claim, the rebuilt durable network and the two recorded
decode defects, the bus track with Codex's ownership and the map-matching deviation flag,
and the queue with owner-gated items marked. The consolidated register gains the
latency-tail, RSU-asymmetry, and N1/concurrency entries. Exclusive files: that prompt, the
register rows, and this record.

### Phase 113 claim: observation chain restored end to end (owner-directed, 28 July 2026)

The three artifacts the 27-July continuity audit declared dead-but-regenerable — the study
subnetwork, the edge index, and the 305-row v1.1 match artifact — are regenerated from
committed pins, and **regenerability held exactly**. The clip of the durable Phase-108
parent returns 285,794 study edges against 804,611 parent edges in 31.46 s with every edge
id preserved and all 150 committed Option-A counted edges present. The rebuilt index over
the parent carries 804,611 real edges with geometry fingerprint
`4019252e50e58555f6e9531263b108a42975a118a4cf3c69e02030a4c6cad63d`. The regenerated match
artifact reproduces the 25-July split exactly — 106/178/21 under v1.0, 131/165/9 under
v1.1, 106 strict plus 25 override acceptances, 51 override edges, 1,339 refused edges — and
the Match Review page loads it with 174 queued rows, every one visibly pending.

The observation side had to be re-acquired: only single-record probes (`page[size]=1`)
survived in the durable workspace, so the 342-point and 79-page/39,072-row DfT datasets
were re-fetched through the accepted bounded MAN-01/MAN-02 machinery. **Both returned the
same raw-fingerprint prefix and identical page and row counts as the 25-July snapshots they
replace**, so the DfT historical archive is externally reproducible — a claim deliberately
limited to prefix equality, because the committed record preserves only 12 hex characters.

One recorded defect, not fixed here: the 25-July `reconciliation_fingerprint`
(`ae3ecff1…`) is computed by no committed code, so it cannot be verified against anything
reproducible; this run publishes an explicitly defined digest beside it and records that a
fingerprint published without the code that computes it is not verifiable later.

Exclusive files: `scripts/clip_study_subnetwork.py`,
`scripts/regenerate_match_artifact.py`,
`docs/integration/evidence/manchester_chain_restoration_20260728.json`, its `docs/index.md`
row, the restoration section of
`docs/integration/manchester_workspace_continuity_20260727.md`, the restored-chain row in
`docs/experiments_and_findings_20260728.md`, and this record. Derived networks, indexes,
and match rows stay in gitignored `data/` and the private workspace, never committed.

### Phase 114 claim: BETA-D-02 §2 demand diagnosis (owner-directed, 28 July 2026)

The four predeclared §2 measurements ran over the restored study subnetwork, published as
§2 requires regardless of outcome. The alpha.7 envelope reproduces faithfully — 43,200
trips, 43,200 pool routes at 88,163,681 B against the recorded 88,163,497 B, 91.72% count
achievement against 91.32%, zero overflow, and the same two dominant shortfall edges.

**The recorded hypothesis is half refuted and half beside the point.** Fringe entry is
**0.06% of pool routes and 0.38% of demand vehicles**, below what no weighting at all would
produce against a 1.88% entry-fringe edge share — published beside the broader 4.03%
`sumolib`-style definition so the result cannot be dismissed as definitional. Route length
is genuinely long (demand median 8.17 km / 134 edges, the latter reproducing the truncated
survivor's median exactly). But the binding constraint is neither: **four counted edges are
traversed by no pool route and are 100% unmet, and the two edges carrying 61.4% of the
shortfall are traversed by exactly two routes each against a median of 395. Six of 150
counted edges carry coverage ≤2 and account for 72.8% of all unmet vehicles.** That is
structural reachability, not weighting or sizing.

Consequently all three predeclared variants target non-binding mechanisms, and §2's own
rule returns the variant order to the owner. Three options are tabled in the results record;
none is taken, no variant ran, no threshold was applied, and the predeclaration is unedited.

Also closed: the open +3,152 B2 reconciliation note. The committed Option-A artifact holds
150 edges / 1,800 cells / 2,027,275 vehicles against the record's 149 / 1,788 / 2,024,123,
the 11 measured-zero cells match exactly, and no single edge totals the missing 3,152 — so
no 149-edge subset reproduces the recorded total and the committed artifact is not
byte-exactly what alpha.7 consumed. Quantified, not resolved.

Exclusive files: `scripts/run_demand_diagnosis.py`,
`docs/evaluation/demand_diagnosis_results_20260728.md`,
`docs/integration/evidence/manchester_demand_diagnosis_20260728.json`, their `docs/index.md`
rows, the demand-diagnosis row in `docs/experiments_and_findings_20260728.md`, and this
record. Pool, trips and the 1.28 GB demand stay in gitignored `data/`, never committed.

### Phase 115 claim: refusal-resilient attended BODS session runner (owner-directed, 28 July 2026)

The owner opened an evening-peak observation window. `bus_cadence_probe_session.py` ended it
after two snapshots: the MAN-05 parser refused attempt 3 with `PARSE_REJECTED`, and because
that runner catches only `BodsLiveControlError`, the `BodsAcquisitionError` propagated and
killed the process. The same refusal cost ~52 snapshots this morning and 2 this evening —
three refusals across two rush hours, all replaying as the one cross-operator `VehicleRef`
collision already diagnosed.

`scripts/bus_attended_session.py` keeps the accepted acquisition boundary exactly as it is
— ≥60 s apart, one at a time, human-triggered, the recorded Greater Manchester box, key
read from the environment and never echoed, in-process salt, aggregate-only measurement —
and changes only what happens *after* a fail-closed refusal: the refusal is recorded in a
ledger with its attempt number, UTC time and the quarantine directory that was written but
never promoted, and the attended window continues. Eight *consecutive* refusals end the
session, on the reasoning that a feed refusing that persistently is not a transient shape
problem.

**Nothing about the parser, the promotion rule, or the evidence boundary moves.** A refused
snapshot is still refused, is still never measured, and is counted in its own denominator so
accepted and refused can never blur. MAN-05 stays untouched and lead-owned; this is a
session-runner change, not a parser change. Prints are flushed so an attended operator can
watch a redirected log live.

Exclusive files: `scripts/bus_attended_session.py`, its session records under
`docs/evaluation/`, and this record. The existing probe runner is left in place unchanged.

### Phase 116 claim: MAN-05 rush-hour refusal diagnosis (owner-directed, 28 July 2026)

Offline read-only replay of **every** fail-closed MAN-05 refusal recorded on 28 July — two
this morning and two this evening — each member re-read from quarantine, hashed, and
verified against its quarantine manifest before parsing (all four verified; the manifest
hash covers the stored gzip bytes and is checked before decompression).

**All four are one defect.** Every refused snapshot has exactly one conflicting identity
group holding exactly two vehicle activities, the two always belong to *different
operators*, and grouping by `(OperatorRef, VehicleRef, RecordedAtTime)` instead of
`(VehicleRef, RecordedAtTime)` leaves **zero** conflicts. That is the whole fix, and it is a
one-line reproduction.

Three things the earlier note did not have. The colliding refs are 5204, 3051, 3042 and 3042
— **three distinct values, so this is a family of overlapping numbering ranges, not one bad
vehicle**. The two evening refusals are the *same* ref 22 minutes apart (ANWE line 2 vs BNGN
line 582), so a collision persists while both vehicles stay in service, which is why
retrying does not escape it. And the overlap is **asymmetric**: BNGN appears in all four,
ANWE in three, HIPK in one. All four struck at 1,588–1,620 activities per snapshot while the
41-vehicle night probe never triggered one — a refusal needs two overlapping-numbered
vehicles reporting in the same second, so the hazard scales with fleet size and is
structurally a rush-hour defect.

MAN-05 stays lead-owned and untouched; every refusal stays a refusal, and no refused
snapshot was promoted, measured, or admitted. Exclusive files:
`docs/integration/evidence/man05_refusal_diagnosis_20260728.json`, its `docs/index.md` row,
and this record.

### Phase 117 claim: evening-peak bus session (owner-attended, 28 July 2026)

Owner-triggered at 17:13 BST. **83 accepted / 2 refused of 85**, 16:16:43Z–17:49:40Z — the
longest clean rush-hour window captured to date, and the fourth density point.

**1,741 seen / 1,522 active** over the full session. The support figure is *not* directly
comparable with the morning's 1,433, because `vehicles_linked_across_snapshots` grows with
session length, so it is also re-measured over a length-matched 52-snapshot prefix:
**1,481 against 1,433, +3.3%**. Per-snapshot concurrency, which needs no such correction, is
**1,250 max / 1,215 median against morning's 1,216 / 1,192**. The evening fleet is
marginally denser than the morning one and sits inside the capacity sweep's unresolved
(215, 2488] band. The window caught the crest at 17:41 BST and a clean monotonic taper to
999 by 18:47 — a curve a single-point sample cannot show.

Cadence is **66 s median / 75 s p90**, identical to the morning peak and stable at 66–68 s
across all four sessions, so feed cadence does not degrade with fleet size.
`implied_speed_mps_max` is 66.79 m/s, again over the proposed 32 m/s B1 ceiling, reinforcing
the standing keep-32-and-drop-and-count recommendation on a second peak window; still a
recommendation, not a taken G2 decision.

Both refusals were absorbed by the Phase-115 runner. Without it the session would have
ended at 19 snapshots and no evening density point would exist. The five-refusal diagnosis
is extended to cover them: BNGN now appears in all five, ANWE in four, and three of the four
distinct colliding refs sit in the 3000 series where ANWE and BNGN numbering overlaps.

No B1 experiment ran; G1–G5 stay unsigned. This session does not alter the frozen B-BUS
traces or either Colab pack. Exclusive files:
`docs/evaluation/bus_evening_peak_session_20260728.md`, the extended
`man05_refusal_diagnosis_20260728.json`, their `docs/index.md` rows, and the register rows.

### Phase 118 claim: pilot dynamics analysis — the mechanism in closed form (28 July 2026)

Analysis-only over all 12 admitted pilot cells; no run executed. **The tail-latency ceiling
is linear in per-vehicle capacity**: p95 latency of missed tasks divided by capacity is
39,959 ms with standard deviation 166 ms — a 0.41% relative spread across all 36
(cell x class) pairs, i.e. 100 s at cap-2.5, 60 s at cap-1.5, 40 s at cap-1.0, 30 s at
cap-0.75. Since ~99% of latency mass sits at that ceiling, mean latency is linear in
capacity too (predicted arm ratio 3.33, confirmatory measured 3.24), and every deadline is
60-300x below the ceiling at every capacity, so attainment cannot move. **That closes the
confirmed finding's mechanism as a functional form rather than a narrative.**

Two further results. **The policy is bimodal, not probabilistic**: counting only steps where
a slot carries tasks, 1,413/988/87 slots never/always/sometimes offload at seed 0
(1,393/992/103 and 1,384/1,018/86 at seeds 1-2), identical across all four capacities, so
only ~3.5% of slots ever switch behaviour and the ~0.40 aggregate is a partition rather than
a per-situation rate. **Deadline failure is concentrated and not by workload**: failure-rate
Gini 0.616-0.627 with the worst decile carrying 34-36% of all failures, while task-count
Gini is 0.028. Also: the three task classes fail in qualitatively different ways (T1 misses
are 3.7x near-misses barely moved by the squeeze, T2 misses sit at the ceiling and fall 71%),
and saturation is immediate rather than gradual - the capacity ratio is reached by ~10% into
the run and offload share is flat at 0.398-0.407 throughout.

Exclusive files: `scripts/analyse_pilot_dynamics.py`,
`docs/evaluation/pilot_dynamics_analysis_20260728.md`, its `docs/index.md` row, the register
row, and this record. Arrays stay in gitignored `data/`.

### Phase 119 claim: bus speed-density series (28 July 2026)

The four attended sessions span a 36x fleet range under one boundary and one identity
policy, so they form a speed-density series measured end to end from live open data. Speed
is per-segment via the accepted B2 primitive, never median-displacement over median-interval.
**Buses at peak move 44% slower than at night** (6.290 -> 3.518 m/s), and resolving the
evening session into its two UTC hours turns four session points into six hour points that
fall essentially monotonically with fleet size (6.290 / 4.523 / 4.358 / 3.850 / 3.518 /
3.369 m/s), with the single inversion sitting between two dawn hours of near-identical fleet
and very unequal support.

The hourly split also dissolves an apparent contradiction: at session level the evening peak
looks faster than the morning peak despite carrying more vehicles, but hour for hour the
evening crest (1,462 vehicles, 3.369 m/s) is both denser and slower than the morning peak
(1,429, 3.518) - the session average merely mixed the crest with the recovery.

Explicitly non-causal: fleet size and time of day covary and general congestion is an
unmeasured common cause. Sessions are bounded by explicit UTC stamp ranges, not hour
prefixes, because a prefix folds the aborted 07:57 BST attempt's single promotion into dawn;
session sizes reconcile exactly with the recorded three-session results. Exclusive files:
`scripts/analyse_bus_speed_density.py`, `docs/evaluation/bus_speed_density_20260728.md`, its
`docs/index.md` row, the register row, and this record.

### Phase 120 claim: counted-edge reachability diagnosis (28 July 2026)

Read-only topology and permission audit of the restored study subnetwork, answering why six
of 150 counted edges hold 72.8% of the demand shortfall. **Two structural causes, cleanly
separated, and no predeclared variant addresses either.**

(a) **Vehicle-class exclusion.** Exactly four counted edges carry `allow="bus bicycle"`
lanes - on the A6, A56 and A665 - and they are **exactly** the four edges no pool route
traverses, a 1:1 match with no false positives or negatives. The pool was generated with
`randomTrips --vehicle-class passenger`, so their 19,091 observed vehicles are unmet by
construction at any pool size. Their upstream reachability is normal (259-522 edges within
8 hops against a typical median of 208), so this is permission, not topology. It is a
modelling mismatch: DfT counts motor vehicles including buses, the pool is passenger-only,
and a passenger-only demand cannot reproduce a count taken on a bus lane.

(b) **Boundary truncation.** The two edges carrying 61.4% of the entire shortfall are M56
motorway segments at the southern clip boundary - the 1st and 2nd southernmost of all 150
counted edges, at 3,682 m and 3,692 m against a counted-edge range of 3,652-23,325 m. One
has a **single** upstream edge within 8 hops against a typical 208. This quantifies the
clipping limitation the 25-July subnetwork record already stated in words.

Four options are tabled (exclude the passenger-forbidden targets; exclude or down-weight the
truncated pair; generate a multi-class demand; widen the clip) and none is taken - excluding
a target is an owner decision. Exclusive files:
`docs/integration/evidence/counted_edge_reachability_20260728.json`, its `docs/index.md`
row, the register row, and this record.

### Phase 121 claim: session context prompt v6 (owner-directed, 28 July 2026)

Resume set for a fresh session. `CLAUDE_SESSION_CONTEXT_PROMPT_V6.md` supersedes V5 and
leads with the three detached campaigns running unattended, because they survive session
death and must be checked before anything is relaunched. Carries the closed-form capacity
mechanism (the tail-latency ceiling law and its two structural findings) and the
pre-registered prediction test now in flight; the restored observation chain; the demand §2
diagnosis with both structural causes of the shortfall and the variant order returned to the
owner; the evening-peak bus session with the length-matched comparison caveat and the
five-refusal MAN-05 diagnosis; the density gap with both blocked routes recorded untaken and
the two indirect routes queued; the eight gotchas learned this session; the owner decision
queue including the GPU track's gate state; and the paste-ready prompt.

Exclusive files: that prompt and this record.

### Phase 122 claim: pre-registered ceiling-law verdict computation (28 July 2026)

The `inc-deep` campaign tests a prediction whose pass band and verdict rule were frozen before
any cell ran. This slice commits the code that computes that verdict **before the tested data
exists**, so the rule cannot be adjusted once the arms are visible — the same argument the
register already makes about digests (*a digest is only evidence if the code that computes it
is committed beside it*), applied to a pre-registered outcome.

`scripts/verify_ceiling_law_prediction.py` re-hashes
`docs/evaluation/ceiling_law_prediction_predeclaration.md` and refuses on
`PREDECLARATION_CHANGED_AFTER_APPROVAL`; it also checks its own transcribed literals against
the law they encode (the ±5% band and each per-arm ceiling are re-derived from K = 39,959 and
must equal the predeclared values). The frozen rule is applied in the precedence the
predeclaration implies — HELD when every deep arm × class pair is inside the band, else
BOUNDED when cap-0.5 is clean, else REFUTED — and a pair with no missed tasks is reported as
**INCOMPLETE** rather than silently counted as a pass. cap-2.5 is measured but excluded from
the verdict and labelled a replication check, because it is one of the capacities the law was
fitted on.

A `selftest` mode recomputes K from the already-published pilot dynamics JSON, reading no
arrays, and it earned its place immediately: the first run reproduced K (39,959.07) and the
0.41% spread but not the published σ of 166 ms, because the original statistic is the
**sample** standard deviation — the population estimator gives 163.4 over these 36 pairs. The
recipe was corrected to match the one that produced the law and the discrepancy is recorded in
the code rather than reconciled away. Selftest now passes on all three statistics.

Exclusive files: `scripts/verify_ceiling_law_prediction.py` and this record. No campaign
design, launcher, fingerprint, predeclaration or admitted artifact is touched, and the `verify`
mode is deliberately not run while cells are timed.

### Phase 123 claim: onset-scaling prediction operationalised before its data (28 July 2026)

The three queued onset legs (`we-deep`, `wd-am-deep`, `wd-pm-deep`) are bound to
`density_gap_options_20260728.md`, which states their hypothesis — *onset capacity scales with
concurrent density* — as a direction with **no definition of what counts as onset**. Without
one the threshold could be chosen after the arms were visible. All three output directories
were still empty when this slice was written, so the rule was fixed first.

`docs/evaluation/onset_scaling_prediction_predeclaration.md` is an addendum, not an edit: the
memo stays byte-frozen at `00681a14…` because three launched campaign designs bind that digest
and moving it would break their approval check and their resume. The onset rule is
**transcribed** from the committed five-regime and deep-squeeze records, which already judge
response by exact identity ("paired diffs literally 0.000000") — an arm is inert when every
metric at every seed equals the baseline exactly, and there is no tolerance parameter to tune.
The one measured onset bracket, `c_onset(ev) ∈ (0.1, 0.25]`, is propagated as a **band** rather
than collapsed to a midpoint, which yields six decidable predictions and three cells the sweep
resolves rather than tests. The addendum states plainly that five of the six are inert
predictions and near-free, and that the load-bearing claim is the single prediction **`wd_am`
binds at cap-0.1** — so a reader does not have to notice that asymmetry independently.

`scripts/verify_onset_scaling_prediction.py` re-hashes both documents, re-derives the whole
prediction table from the propagated band and refuses if it disagrees with the transcribed
literals, and reports INCOMPLETE — naming the missing legs — rather than reading absent data as
a passed prediction. Verdict is binary (HELD/REFUTED) with two descriptive qualifiers reported
alongside it, never in place of it: whether measured onsets stay ordered by density, and
whether every arm was inert at the grid floor. Its selftest reproduces the published `ev`
result exactly (inert at 0.5 and 0.25, binding at 0.1, onset 0.1). Both modes read only
campaign-analysis JSON, so the verdict costs no CPU and is safe to run beside timed cells.

Exclusive files: that addendum, that script, and this record. No campaign design, launcher,
fingerprint, existing predeclaration or admitted artifact is touched.

### Phase 124 claim: actor-crossover runner and prediction (3) made decidable (28 July 2026)

The crossover study had a complete, tested rule in the accepted
`vec_campaign/slope_comparison.py` and **no way to run it** — no script anywhere loads two
campaign analyses and applies it. Without this, the `inc-baseline` campaign would have landed
and its analysis would have been written after its results were visible.

`scripts/analyse_actor_crossover.py` applies the accepted module **unchanged** to the admitted
capacity pilot (`ukfleettrain_mappo_model_c_17`) against the `inc-baseline` campaign
(`baseline_model_c_17`), reads only campaign-analysis JSON, and carries the fleet-preset
asymmetry into every output rather than leaving a reader to rediscover it. Nothing about the
pilot is re-run or altered; it is read as one arm of the contrast.

`docs/evaluation/crossover_slope_prediction_addendum.md` makes the candidate's §5 prediction
(3) decidable. The candidate names it as *the interesting outcome* but states it as "the slope
contrast should be small", which is not a decidable claim, so the threshold would otherwise
have been chosen after both curves were visible. The statistic is the relative contrast between
the two actors' OLS mean-latency slopes over capacity; the ±5% band is **transcribed** from the
ceiling-law predeclaration's tolerance for the same underlying quantity rather than chosen
here. The addendum also fixes, in advance, what a refutation would *not* establish: the preset
matches one actor's training distribution and not the other's, so an actor-dependent slope has
two live explanations that this comparison cannot separate. The candidate itself is untouched —
it is byte-bound at `b8f0efa2…` into the launched design.

Exercised end to end on the real `ev` actor pair (grid-ev against B0), which is the candidate's
own inert-regime control: no crossover, rule applicable, both slopes exactly zero — and
prediction (3) correctly returns INCOMPLETE rather than manufacturing a pass out of a 0/0
contrast. That degenerate case is the one a naive implementation would have scored as a perfect
0% agreement.

Exclusive files: that addendum, that script, and this record. The accepted comparison module,
the candidate, every campaign design and every admitted artifact are unchanged; the local OLS
for the secondary series is a deliberate reimplementation rather than an edit to accepted code.

### Phase 125 claim: B-DENSITY Phase 1 on Colab G4, and its method corrected (owner-directed, 29 July 2026)

The owner directed Colab G4 execution via the CLI, which resolved the open routing decision —
B-DENSITY had been prepared and deliberately unlaunched because the GPU track is the lead's
lane. Phase 1 ran on a freshly allocated G4 (RTX PRO 6000 Blackwell, jax 0.7.2, real `gpu`
backend, not a `--allow-cpu` dry run) and the session was released immediately. The density axis
responds at both smoke capacities, so the predeclaration's Phase-2 gate is passed; the manifest
digest was printed on the VM and re-verified byte-exactly against the downloaded artifact.

**The material finding is a correction to the design's own method.** Both the predeclaration §4
and the handoff specify reaching the density axis "via a reviewed transform of a disposable copy
of `vec_jax.py`". Reading the producer source instead of assuming shows that is unnecessary:
`VEC_JAX_N_VEHICLES` and `VEC_JAX_RSU_MAX_CONCURRENT` are already documented producer knobs, and
the producer's own comment on the latter states its purpose is to "match the eval engine's
per-RSU concurrency scaling (2.5 × fleet)" — the allowance semantics the handoff insists Phase 2
must preserve, and the same relation visible in the running campaign's receipt
(`RSU_MAX_CONCURRENT=6220` at 2,488 slots). Recorded as an explicit deviation, not a silent
simplification: it is the safer route, since `prepare_source.py` rewrites nine source regions and
each is a chance to alter semantics, whereas the env-var route leaves the environment unpatched.
The frozen grid, hypothesis, prediction and verdict rule are untouched and the predeclaration is
not edited.

Reading the source also bounded what Phase 2 may claim: `N_RSUS = 2` and is **not**
env-overridable, on a 2,000 m corridor with `EPISODE_LENGTH = 200`. At the top of the frozen grid
that is 2,048 vehicles served by two RSUs, so no onset capacity from this environment may be
quoted as a property of `inc` or the Etihad district — already forbidden by §5, now concrete.

A pre-existing orphaned G4 assignment with no local CLI record was visible throughout and was
**not touched** — the CLI log shows nothing used it between 08:10 and this session while the
B-BUS track was actively committing Colab work, so it is most likely that track's live browser
session. Flagged for the owner, not stopped.

Exclusive files: `docs/evaluation/bdensity_phase1_results_20260729.md` and this record. No
predeclaration, campaign design, launcher, producer clone or admitted artifact is modified;
Phase 2 is not launched.

### Phase 126 claim: producer data and publication permission recorded (owner-relayed, 29 July 2026)

The owner stated that the producer has granted permission covering **code, data and
publication** in writing, i.e. all three items the 28 July record listed as open asks.
`docs/integration/randy_data_and_publication_permission_20260729.md` records it and the earlier
document carries a superseded-in-scope banner rather than being edited or removed, because
several frozen predeclarations link to it by path and it records the state under which those
campaigns were approved. No digest binds either file, so nothing frozen is disturbed.

**The consequential change is publication, not compute.** The confirmed latency result, the
ceiling law and every figure in the experiments register were previously outside the recorded
permission for public output, so this gates the dissertation write-up. The Colab question that
surfaced it is the lesser half, and is still blocked on budget regardless: the remaining queue
is ~460 compute units against a ~196.6 balance.

Recorded honestly as second-hand: the written artifact is not in the repository and this agent
has not seen it. Filing the message text or a dated quoted excerpt is left as a small open
action, worth closing before the dissertation cites any producer-derived number. Label ceilings,
the non-admitted status of third-party-venue outputs, citation obligations, the
never-fetch rule and per-experiment predeclaration all stand unchanged — this permission
concerns intellectual property and data use, not scientific validation.

Exclusive files: the new permission record, the banner on the 28 July record, and this record.

### Phase 127 claim: producer citation requirements (29 July 2026)

The producer's permission is granted **on condition of citation**, and it now binds more output
than before because every capacity number in the dissertation is producer-derived. No citation
apparatus existed anywhere in the repository. `docs/producer_citation_requirements.md` assembles
it: both pinned commits verified read-only against the clones
(`068b4ea3…` vec_env, `f6c67acb…` tos-data), the engine version `v2_post_nrsus_fix`, the Year-1
report, SUMO, and the per-trace provenance table.

Two corrections it carries forward into the write-up. The network is the Manchester **Etihad /
Co-op Live event district**, not city-wide, so any wording implying a city-scale VEC twin is
wrong. And every confirmed capacity result is on `inc` alone — the modelled collapse hour, the
only one of five regimes where capacity moves outcomes at all.

The document states plainly that its entries are assembled from the repository and local files
rather than a bibliographic database, and must be verified against sources before submission;
the supervisor's standard makes citation failure a degree risk, so an unverified reference
string presented as checked would be worse than none. Two items are flagged as needing external
confirmation rather than guessed: the SUMO reference details and the Lourenço demand
calibration. Also records what remains impermissible — rehosting repository content, and
committing the Year-1 PDF or any producer data blob.

Exclusive files: that document and this record.

### Phase 128 claim: what the offload decision is a function of (29 July 2026)

The pilot dynamics analysis established the decision is bimodal but never asked what decides
which side a vehicle falls on. It is **vehicle compute tier, and nothing else measured**: across
five admitted cells spanning two campaigns, four seeds and capacities 2.5 down to 0.1, the
always-offload group is **exactly** the tier-0 population (100.0% every cell) and the
never-offload group contains **no tier-0 vehicle in any cell**. Tier 0 is ~13x weaker than tier
2 by the producer's own capability scalars. The worst-failing decile is 100% always-offload in
every cell.

Both obvious confounds were measured rather than assumed: workload is even (5,263 vs 5,243 tasks
per slot) and task mix is identical (20/30/50), with failure diverging *within* every class —
tier-1/2 vehicles miss a 500 ms deadline literally never.

Two consequences for the write-up. The ~79% attainment figure is a **fleet-composition
artifact**, not a property of the algorithm — it is 40% of the fleet failing about half the time
averaged against 60% succeeding ~97%. And capacity invariance gains a simpler explanation than
the observation gap: the decision does not vary on anything a run changes, because it is fixed
by hardware.

Explicitly not established: whether offloading *helps* the vehicles that do it. That
counterfactual needs a different actor on the same trace, which is the already-queued crossover
campaign — reframing that leg from marginal to decisive.

Extended the same slice with the effect decomposition (§6): over a 25x squeeze the never-offload
population's mean latency, p50, p95-of-missed and attainment are **bit-identical**, while the
always-offload population carries the entire effect (-24,564 ms seed 60, -26,364 ms seed 61).
Three consequences: the confirmed fleet-mean -8,310.9 ms **describes no vehicle**, since it
averages a bimodal population where ~60% moved by exactly zero; the ceiling law is an
**RSU-queue** law rather than a system property, absent entirely from locally-executing traffic
and recovered by the pooled measurement only because ~92% of missed tasks are offloaded ones;
and the earlier seed-difference puzzle resolves as the tier-0 gain diluted by tier-0 share
(0.0102 x 0.41 = 0.0042 against a measured 0.00416).

Exclusive files: `scripts/analyse_offload_partition.py`,
`docs/evaluation/offload_partition_analysis_20260729.md`, the register row, and this record.

### Completed lead ownership: v0.7 beta goal consolidation (25 July 2026)

- The integrating lead owns a documentation-only consolidation of every v0.7 capability and gate
  that is not fully accepted at the `v0.7.0-alpha.7` checkpoint. This work records current evidence,
  blockers, beta acceptance targets, and the dependency order; it does not change the canonical
  v0.7 design, capability truth, scientific policy, source contracts, or any gate status.
- The exclusive file set is this ownership record,
  `docs/traffictwin-design-v0_7_beta-goals.md`, and the corresponding entry in `docs/index.md`.
  No implementation, test, generated reference, capability manifest, existing progress record, or
  external repository is edited in this slice.

### Completed lead ownership: alpha.7 merge-verification repair (26 July 2026)

- During the owner-requested alpha.7 integration check, a clean environment without SUMO exposed
  that `preflight_run` probed the optional toolchain before enforcing its caller-supplied FCD-size
  bound. The integrating lead owns the narrow fail-fast ordering repair and its deterministic
  regression test before the official branch is advanced.
- The exclusive implementation/test files are
  `src/traffictwin/integration/manchester/sumo_run.py` and
  `tests/unit/test_manchester_sumo_run.py`, plus this ownership record. No scientific threshold,
  executable boundary, capability status, evidence record, or external repository is changed.
- Verification: the focused module has 21 passing tests; the complete suite has 3,138 passing and
  24 environment-dependent SUMO/netconvert skips in the merge process, with no failures; Ruff,
  format checking, and strict mypy over 728 source files pass.

### Active lead ownership: MAN-05/MAN-08 live-bus completion slice

- The lead owns the identifier-only Bee Network verification/classification slice for `MAN-05`,
  its BODS live-scene integration, generated contract wiring, exact aggregate probe evidence,
  private snapshot retention, manual refresh coordination, aggregate live history, display-time
  stale fallback, lead-owned Manchester Operations wording, project records, and focused tests.
- Lead implementation files are limited to new `bee_network.py` library/tests/docs/evidence plus
  new `bods_retention.py` and `bods_live_control.py` library/tests/docs,
  `integration/manchester/__init__.py`, `bods_live.py`, the Manchester Operations service/page and
  their existing tests, the reference generator/output, and lead-owned status/index records.
  These files do not overlap Claude's Phase 1 presentation-layer grant.
- The slice may activate only exact `OperatorRef` values observed in accepted live-feed evidence;
  display names and geography remain prohibited membership tests. Unobserved candidates,
  non-matches, malformed rows, and out-of-scope rows remain explicitly accounted for, and public
  export remains unavailable.

### Active lead ownership: MAN-03/MAN-07 WebTRIS recency reassessment

- The lead owns the bounded 24 July 2026 WebTRIS real-source recency probe, the resulting
  machine-readable evidence and interpretation document, and reconciliation of the Manchester
  live-feature matrix and lead-owned project records. This reassessment may refine blockers but
  cannot promote WebTRIS historical observations to `near_live` or accept a `MAN-*` capability.
- The exclusive file set is
  `docs/integration/evidence/manchester_webtris_recency_probe_20260724.json`,
  `docs/integration/manchester_webtris_near_live_reassessment.md`,
  `docs/integration/manchester_live_feature_matrix.md`, `docs/implementation-status.md`,
  `docs/open-questions.md`, `docs/assumption-register.md`, `docs/index.md`, and this ownership
  record. The lead also owns the narrow HTTP-204 classification correction in
  `src/traffictwin/integration/manchester/transport.py` and
  `tests/unit/test_manchester_transport.py`. The work is disjoint from Claude's active Phase 2A
  UI claim.
- The older NTIS callback assumption was superseded on 24 July 2026 by direct tests of the current
  National Highways REST products. The new source boundary is owned and audited separately below;
  it must not be represented as WebTRIS evidence or as complete Manchester road telemetry.

### Active lead ownership: MAN-01/MAN-07/MAN-08 National Highways operations slice

- The lead owns the bounded current National Highways REST integration for Road and Lane Closures
  v2, Speed Managed Areas v1, and Digital VMS v1. This includes the Gate-A extension record,
  secret-header transport support, exact DATEX II JSON parsers, immutable private snapshots,
  offline replay, source-specific freshness/outage state, explicit Manchester-area envelope,
  aggregate refresh history, and separate Operations-map layers.
- The exclusive implementation files are new `national_highways*.py` modules and focused tests,
  `src/traffictwin/integration/manchester/{transport.py,freshness.py,spatial.py,map_layers.py,__init__.py}`,
  `src/traffictwin/ui/manchester_operations.py`,
  `src/traffictwin/ui/pages/manchester_operations.py`, focused Manchester Operations tests, and
  lead-owned design/audit/status/index/architecture/assumption/open-question records. These files
  remain disjoint from Claude's active Phase 2A grant.
- Authentication is a transient `Ocp-Apim-Subscription-Key` header only. No credential value may
  enter a model, URL, query, snapshot, receipt, scene, log, exception, test fixture, documentation,
  Git object, or rendered UI. The current 10-request-per-key-per-minute provider limit is enforced
  more conservatively by one explicit three-product refresh per minute; no background polling is
  introduced.
- The operational sources cover the Strategic Road Network only. Closures/incidents, imposed
  temporary speed restrictions, and displayed VMS messages remain three separate evidence kinds;
  they are never relabelled as measured traffic speed, traffic volume, congestion, or complete
  Manchester coverage. Capability state changes remain lead-reconciled after real-source evidence.

- Use `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01`, and Gates A–F from the v0.7 design as units of
  ownership. Record the capability and files owned before editing; agents sharing one checkout
  must use disjoint file sets.
- v0.7 Gate A is accepted in
  `docs/integration/manchester-source-gate-a-audit-v0_7.md` and ADR-054 through ADR-057. It is the
  serial prerequisite for source-specific schema, time/freshness, licence, publication, transport,
  and parser work. Agents may implement Gate B only against those frozen decisions and scoped
  blockers; documentation or a successful API response alone still does not accept an adapter or
  complete `MAN-01`.
- Acquisition, parsing, normalisation, map matching, calibration, comparison, and UI work must
  remain separate tested boundaries. Streamlit pages read accepted local snapshots through
  services and must not fetch external APIs or implement scientific formulas.
- Treat the v0.6 tag and valuable v0.6 workspaces as immutable. v0.7 compatibility is read-only and
  copy-on-write until `REL-01` passes migration, rollback, and side-by-side acceptance.
- Shared integration surfaces—CLI, capability manifests, generated references, navigation,
  changelog, documentation indexes, and project records—remain lead-owned merge files unless
  ownership is explicitly transferred.
- No agent may independently mark a v0.7 capability implemented. The integrating agent reconciles
  code, tests, real-source acceptance evidence, security/licence checks, UI acceptance, generated
  contracts, documentation, and capability truth.

## Preserved v0.6 Evidence Boundaries

- Use the v0.6 capability IDs and Gates A–G as the unit of ownership. Record the capability and
  files owned before editing; agents sharing one checkout must use disjoint file sets.
- v0.6 Gate A (`VEC-01`) is the serial prerequisite and is now accepted in
  `docs/integration/randy-source-snapshot-audit-v0_6.md` plus its generated machine record. No
  agent may implement a schema, mapping, join, or launcher from the email alone; use the pinned
  observed contract, limits, hashes, and blockers from that audit.
- After v0.6 Gate A, contract/fixture work (`VEC-02`), read-only identity/trip joins (`VEC-03`–`VEC-05`),
  and preprocessing/runner work (`VEC-06`–`VEC-08`) may proceed in separate worktrees or explicitly
  disjoint modules. `VEC-09` and `VEC-10` consume only accepted upstream artifacts; `VEC-11` is
  accepted through its permission-manifested pack, and `VEC-12` closes the final reconciliation
  gate with an offline-verifiable artifact.
- Gate C read-only joins (`VEC-03`–`VEC-05`), Gate D (`VEC-06`), the library-level `VEC-07` runner,
  the pinned-case `VEC-08` reproduction verifier, and Gate F scientific admission (`VEC-09`) are
  accepted. VEC-03 identities are valid only inside
  exact reconciled inclusive occupancy spans and a snapshot is bound to the complete trace
  fingerprint. `VEC-07` may consume only
  an exact Gate-A-reviewed trace or a trace identified by a completed, validated VEC-06 receipt; it
  must not bypass preflight or execute an arbitrary script/NPZ. VEC-08 establishes scoped numerical
  equivalence only for its recorded full weekend protocol-seed CPU case.
- VEC-09 admits only contract-compatible task/latency/decision/trip-duration metrics plus separately
  named TOS deadline-success, slot-tier, and no-target measures. It must keep physical completion,
  per-task energy, canonical infrastructure, confirmed-target, protected-attribute fairness, and
  occupancy-cohort trip completion unavailable. R1, R2, and R7 remain blocked; R6 is conditional
  and no threshold or finding was evaluated during admission.
- VEC-10 is accepted as a thin interface. Its VEC evaluator control is conditional on the exact
  request-specific VEC-07 preflight and foreground current-process execution. Do not add arbitrary
  commands, detached/background jobs, a persistent queue, training, dependency installation, or
  source mutation. Default generic/SUMO direct launch remains false.
- VEC-02 and VEC-11 are accepted together at Gate B/G: the exact observed contract is accompanied
  by the reviewed three-row pseudonymised/rounded `_s102` sample and VEC-09 aggregates. Never add
  raw IDs, identity mappings, clocks, targets, private paths, checkpoints, repositories, or
  third-party SUMO assets. Pseudonymisation is not anonymity; public hosting remains unauthorised
  until the project licence and every external publication basis are explicit.
- VEC-12 is accepted at the final Gate-G boundary. Its deterministic 27-member ZIP may embed only
  the allowlisted audit/software metadata and VEC-11 sanitised sample/aggregates. Preserve the
  VEC-08 protocol-seed versus VEC-09/VEC-11 `_s102` run distinction, complete limitations and
  exclusions, fixed ZIP metadata, checksums, offline verification, and new-only publication. Do
  not add raw external/execution bytes or strengthen licensing, hosting, anonymity, completion,
  energy, transfer, diagnostic, causal, scenario, or platform claims.
- Treat shared integration surfaces—`src/traffictwin/cli.py`, capability manifests, generated
  references, documentation indexes, changelog, and project records—as lead-owned merge files.
  Feature agents should expose tested library APIs first and leave final shared-surface wiring to
  the integrating agent unless ownership is explicitly transferred.
- External repositories under `../external/` are read-only evidence. One designated audit owner
  may synchronise them after confirming a clean state; no agent may edit, commit, clean, switch,
  merge, or push those repositories as part of TrafficTwin implementation.
- Each handoff must include exact source commits, inspected relative paths and hashes, changed
  files, tests run, residual blockers, and capability truth. Agents cannot independently mark a
  v0.6 capability implemented; the integrating agent reconciles code, tests, docs, generated
  references, and acceptance evidence first.
- Prefer separate branches/worktrees. If agents must share the current checkout, do not run broad
  formatters, generators, staging, commits, or cleanup while another agent owns overlapping files.

The historical `../XITS/` notes are preserved as research material. They are not active
implementation blockers for the approved TrafficTwin design.

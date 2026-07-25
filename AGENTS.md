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
  `docs/integration/evidence/`. Every other boundary in the parent grant is unchanged, including
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

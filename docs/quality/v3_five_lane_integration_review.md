# V3 Five-Lane Final Integration Review

**Date:** 2026-08-10
**Integration branch:** `integration/v3-five-lane-final`
**Integration worktree:** `/Users/akashx/AntigravityTest/worktrees/v3-five-lane-final`
**Integration base (live `origin/main` at task start):**
`4f8d83aefea98e6f5f489de20b83f111c3754c62`
**Integrator:** Fable 5 (final V3 integration owner). No Claude reviewer has
reviewed the combined integration SHA; the five reviewer verdicts below apply
only to the exact per-lane SHAs listed.

## 1. The Five Reviewed, Frozen Lane Heads

| PR | Feature | Branch | Exact approved SHA | Reviewer verdict |
|---|---|---|---|---|
| #23 | Preregistration Studio | `agent/product-v3-preregistration-studio-v1` | `3e367d62edc73d99b9527bdf2901e660b6246729` | Claude 5: APPROVE |
| #24 | Event-Aligned Analysis | `agent/product-v3-event-aligned-analysis-v1` | `244f5b9295042b6c10defdb2e15619b414580e61` | Claude 2: APPROVE |
| #25 | Study Capsule Builder | `agent/product-v3-study-capsule-v1` | `ace17bf9823627b25599c4649b0393dd1896f789` | Claude 4: REVIEW CLOSED — NO FINDINGS |
| #26 | Resource Strategy Explorer | `agent/product-v3-resource-strategy-explorer-v1` | `ac6c65cfba92728e41db93617a35722cdb6d48c4` | Claude 1: GOOD TO MERGE |
| #27 | Data Contract Workbench | `agent/product-v3-data-contract-drift-v1` | `a7b2e7479075d849d2f84ca08f1f803362ed5f5a` | Claude 3: APPROVE |

Pre-merge verification (via `gh pr view --json headRefOid` after
`git fetch origin --prune`): every PR head equalled its approved SHA exactly;
all five PRs were OPEN, MERGEABLE, unmerged drafts. No worker branch was
rebased, amended, force-pushed, squashed, or otherwise modified by this
integration.

## 2. Merge Order and Merge Commits

Each lane was merged as the **exact approved SHA** (not a branch name) with
`git merge --no-ff --no-commit <SHA>` into the integration branch, which was
created from `origin/main` (`4f8d83a`) in a dedicated worktree.

| # | Lane | Merged SHA | Merge commit |
|---|---|---|---|
| 1 | Preregistration Studio (#23) | `3e367d6…` | `fb8f93d81276bc81d8c9002b28dd7847a5616350` |
| 2 | Study Capsule Builder (#25) | `ace17bf…` | `151dbfaefceabdb6360e62f744edee68e27440e2` |
| 3 | Event-Aligned Analysis (#24) | `244f5b9…` | `0870e7e694757bdc1385f42245ee3abef886cf3c` |
| 4 | Data Contract Workbench (#27) | `a7b2e74…` | `c454906e124101eabddcaa0018255b62fc115175` |
| 5 | Resource Strategy Explorer (#26) | `ac6c65c…` | `09b7afd4f84c5fffc94cfc29a719a6c8779bc87e` |

Rationale for the order: #23 was already rebased onto the newest reviewed main
(`4f8d83a`); Study Capsule adds a CLI as well as UI; Resource Strategy went
last so its final accessibility correction is preserved in the final UI
composition.

## 3. Conflicts and Resolutions

| Merge | Conflicted files | Resolution |
|---|---|---|
| #23 Preregistration | none (clean) | — |
| #25 Study Capsule | `tests/ui/test_navigation_v07.py` | Incoming side hardcoded `39` page counts; HEAD (from the prereg lane) carried the dynamic invariant `len(V07_PAGE_SPECS) == len(UiPage)` with dynamic uniqueness checks. Kept the dynamic form — it asserts everything the hardcoded side asserts without a stale count. |
| #24 Event-Aligned | `tests/ui/test_navigation_v07.py` | Same conflict shape; `git rerere` replayed the identical dynamic-invariant resolution. The incoming side's additions (Event-Aligned row in the expected-routes dict) merged in automatically. Verified marker-free before commit. |
| #27 Data Contract | `tests/ui/test_navigation_v07.py` | Both sides dynamic; incoming wrote `== len(UiPage)`, HEAD wrote `== len(V07_PAGE_SPECS)` — semantically identical given the first assertion. Kept HEAD's form for consistency. |
| #26 Resource Strategy | `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `tests/ui/test_navigation_v07.py` | Adjacent-insertion conflicts: legacy navigation group list (HEAD added `STUDY_CAPSULE`, incoming added `RESOURCE_STRATEGY_EXPLORER`) and the `V07_PAGE_SPECS` "Compare & test" block (HEAD `PREREGISTRATION_STUDIO` spec vs incoming `RESOURCE_STRATEGY_EXPLORER` spec). Resolved as the union — both entries kept, each exactly once. Test file rerere-resolved to the dynamic invariant. |

No `git checkout --ours/--theirs` blanket resolution was used anywhere.

## 4. Shared-File Union

Files integrated as the union of current main plus all five lanes:

- `src/traffictwin/ui/labels.py` — all five `UiPage` members, descriptions
  (auto-merged cleanly in every merge).
- `src/traffictwin/ui/navigation.py` — legacy group lists contain every main
  page plus all five new pages once.
- `src/traffictwin/ui/navigation_v07.py` — all five `V07PageSpec` entries with
  each lane's exact group/script/url/icon.
- `src/traffictwin/ui/page_runtime.py` — all five renderer registrations
  (auto-merged cleanly).
- `src/traffictwin/cli.py` — Study Capsule `capsule` sub-app added; only the
  Study Capsule lane touched the CLI (auto-merged cleanly).
- `tests/ui/test_navigation_v07.py` — dynamic inventory invariant plus every
  lane's expected-route rows.

Preserved per lane, unchanged from the reviewed SHAs: enum value, visible
label, URL path, script path, renderer mapping, navigation group, summary
wording, app-page wrapper. No page was renamed or regrouped to resolve a
conflict; no URL or script collision existed.

## 5. Non-Shared Reviewed-File Integrity

For each approved SHA `S`, every file changed between `merge-base(S, main)`
and `S` was diffed against integration HEAD. For **all five lanes** the only
differing files are exactly the five shared registration files listed in §4.
Every non-shared domain/service/test file from every lane is byte-identical to
its reviewed state. No mechanical fixes, typing changes, or semantic edits
were needed on any lane-owned file.

## 6. Final Page Inventory (probed from the live tree)

- `len(UiPage)` = **43**
- `len(V07_PAGE_SPECS)` = **43**
- `len(PAGE_RENDERERS)` = **43**
- `validate_v07_page_specs()` passes; page/spec/renderer sets identical.
- All 43 URL paths unique; all 43 script paths unique; all 43 app-page
  wrapper files exist; all renderers callable.
- Each of `EVENT_ALIGNED_ANALYSIS`, `STUDY_CAPSULE`,
  `DATA_CONTRACT_WORKBENCH`, `RESOURCE_STRATEGY_EXPLORER`,
  `PREREGISTRATION_STUDIO` registered exactly once:
  - Event-Aligned Analysis — Results, `event-aligned-analysis`,
    `app_pages/event_aligned_analysis.py`
  - Study Capsule Builder — Evidence & reports, `study-capsule`,
    `app_pages/study_capsule.py`
  - Data Contract Workbench — Build & run, `data-contract`,
    `app_pages/data_contract.py`
  - Resource Strategy Explorer — Compare & test, `resource-strategy`,
    `app_pages/resource_strategy.py`
  - Preregistration Studio — Compare & test, `preregistration`,
    `app_pages/preregistration.py`
- No main page was dropped: main had 38 pages; the integrated inventory is
  38 + 5 = 43. Tests assert the dynamic invariant, not a hardcoded count.

## 7. Test Environment

CI-equivalent local environment: Python **3.12.13** via
`uv sync --locked --extra dev --extra vec-runner` (the exact CI install
command; jaxlib 0.4.30 has no CPython 3.13 wheels, so the CI-supported 3.12
was used for both the main baseline and the integration candidate). All runs
serial; no `pytest -n`.

## 8. Per-Lane Acceptance Suites (integration branch)

| Suite | Result |
|---|---|
| Preregistration (unit service + governance regressions + integration workflow + UI) | **80 passed** |
| Study Capsule (unit + integration + UI) | **71 passed**, 1 warning |
| Study Capsule CLI (`traffictwin capsule --help`) | exit 0, sub-app registered |
| Event-Aligned (models + service + exports + blockers + integration + UI page) | **49 passed** |
| Data Contract (unit pkg + integration + UI workbench) | **67 passed** |
| Resource Strategy (unit + UI page + integration flow) | **41 passed** |

All reviewed invariants listed in the integration mandate (§12–§16) are
enforced by these suites and all pass unchanged.

## 9. Navigation, Accessibility, and Combined UI

| Gate | Main baseline (`4f8d83a`) | Integration | Delta |
|---|---|---|---|
| `tests/ui/test_navigation_v07.py` | 50 passed | **55 passed** | +5, all green |
| `tests/ui/test_accessibility.py` | 314 passed | **354 passed** | +40, all green (no duplicate H1, no missing title) |
| `tests/ui` (isolated) | 703 passed | **768 passed** | +65, all green |
| `tests/unit/ui` (isolated) | 233 passed | **243 passed** | +10, all green |
| `tests/ui` + `tests/unit/ui` combined | — | **1011 passed, 0 failed** | no cross-suite pollution in this combination |

Cross-feature smoke (direct `AppTest` render through the registered page
scripts): all five new pages render with no exception and exactly one H1 each.
No subprocess/network/`os.system` usage exists in any of the five new page
modules. No enum member is overwritten, no circular import, no duplicate
widget key surfaced by any UI suite.

## 10. Unit-Suite Comparison (`pytest tests/unit -q`)

| | Main baseline | Integration |
|---|---|---|
| passed | 3649 | 3911 (+262) |
| failed | 95 | 105 (+10) |
| exit code | 1 | 1 |

The +262 passes are the new lane tests. The +10 failures are **all ten tests
of `tests/unit/ui/test_resource_strategy_explorer_page.py`**, which pass in
isolation, in `tests/unit/ui`, and in the combined UI run. Root cause was
reproduced, not assumed: `tests/unit/test_apptest_cold_start_hardening.py`
installs a stub `streamlit`/`FakeAppTest` into `sys.modules`
(pre-existing main hygiene item from PR #19); running just that file followed
by the resource-strategy page file reproduces all 10 failures with the
signature `module 'streamlit' has no attribute 'secrets'`. The identical
polluter→victim sequence against a pre-existing main file
(`tests/unit/ui/test_page_presentation_home.py`) fails the same way (4
failures, matching the main baseline). Classification: **pre-existing
polluter, new victims — not integration-introduced.** No failure signature
unique to integration exists, and every main-baseline failure is still
present (nothing was masked).

## 11. Full-Suite Comparison (`pytest -q`)

| | Main baseline | Integration |
|---|---|---|
| passed | 4624 | 4967 (+343) |
| failed | 95 | 105 (+10) |
| skipped | 10 | 10 |
| exit code | 1 | 1 |

The failed-set difference is exactly the same 10 resource-strategy page
victims as §10; the only-on-main set is empty. The 95 shared failures are the
known pre-existing order-dependent Streamlit stub/AppTest pollution
(`streamlit has no attribute 'secrets'`, `FakeAppTest` leakage) concentrated
in `test_apptest_cold_start_hardening.py` and the page-presentation/AppTest
files; all of them pass in their isolated suites. The full suite was
collected completely in this environment (no collection errors); the two
jax-dependent modules collect because the CI `vec-runner` extra is installed.

## 12. Whole-Repository Static Gates (integration HEAD)

| Gate | Result |
|---|---|
| `uv run ruff format --check .` | clean (1044 files at merge time; re-run green after doc reconciliation) |
| `uv run ruff check .` | All checks passed |
| `uv run mypy` (canonical config) | Success: no issues found in 958 source files |
| `uv lock --check` | clean |
| `git diff --check` | clean |

No mypy/Ruff/workflow/lock configuration was changed.

## 13. Product Documentation Reconciliation

Updated (genuinely stale for the combined product):

- `README.md` — five new "Implemented" bullets, each carrying the lane's
  honest limitations (Event-Aligned: UI-only sequential bounded engine, no
  CLI, no Manchester live evidence; Study Capsule: unsigned archive, internal
  integrity ≠ creator authenticity; Data Contract: local bounded samples, no
  provider/network call, raw categorical values excluded; Resource Strategy:
  synthetic/read-only, unregistered contracts fail closed; Preregistration:
  governance only, freezing ≠ scientific approval, no research execution).
- `docs/user_guide.md` — new sections for Data Contract Workbench, Study
  Capsule Builder, Preregistration Studio, and Resource Strategy Explorer
  (Event-Aligned Analysis was already added by its lane), each with journey
  and boundary paragraphs.
- `docs/full_product_guide.md` — Streamlit UI Reference table extended with
  the five V3 pages plus the four V2 pages the previous campaign left out
  (What-If Studio, Consequence Lenses, Portfolio Explorer, Manchester
  Evidence Hub); duplicated `About` row merged into one.
- `docs/ui_conventions.md` — stale "Five of the 39 pages" adjusted to the
  live 43-page inventory.

Inspected and deliberately left unchanged:

- `docs/demo_quickstart.md` — no page inventory or stale claim.
- `docs/implementation-status.md` — historical v0.5-era phase ledger (does
  not describe V2 either); not a current-truth document.
- `docs/current_progress_v0_7.md` — dated snapshot (3 August 2026);
  historical record.
- `docs/traffictwin_product_design_v2.md` — V2 design-intent document, not
  current-product truth.
- README's "38 concrete use cases" — matches the guide's UC1–UC38 numbering
  (two duplicated UC numbers are a pre-existing glitch, out of scope).
- No historical quality-review record was rewritten; no roadmap item was
  marked complete.

## 14. Ancestry Proof

`git merge-base --is-ancestor <SHA> HEAD` exits 0 on the integration branch
for all five reviewed SHAs:

- `3e367d62edc73d99b9527bdf2901e660b6246729` ✓
- `244f5b9295042b6c10defdb2e15619b414580e61` ✓
- `ace17bf9823627b25599c4649b0393dd1896f789` ✓
- `ac6c65cfba92728e41db93617a35722cdb6d48c4` ✓
- `a7b2e7479075d849d2f84ca08f1f803362ed5f5a` ✓

The integration PR must be merged with a **merge commit** (never squash or
rebase) so these remain ancestors of `main`.

## 15. Known Pre-Existing Failures and Remaining Limitations

- Order-dependent Streamlit stub/AppTest pollution in the combined
  `tests/unit` / full-suite session (95 pre-existing victims on main, +10 new
  victims from the new resource-strategy page file). First polluter:
  `tests/unit/test_apptest_cold_start_hardening.py` (pre-existing from
  PR #19). Every affected file passes in its isolated suite. Fixing the
  polluter is main hygiene work outside this integration's mandate.
- CI remains CI_INFRASTRUCTURE_BLOCKED (billing); red GitHub checks are not
  test failures.
- Product limitations preserved verbatim per lane (see §13); none of the five
  pages launches SUMO, VEC, scheduler control, Kubernetes, or network access,
  and none claims scientific acceptance or production readiness.

## 16. Research Safety

No SUMO/VEC/evaluator process was launched, signalled, or modified. The
research paths (`~/AntigravityTest/diss`, external `vec_env`, `tos-data`, raw
E2 outputs) were not read, moved, or written. All test runs were serial.

# Claude Independent Review — Product Completion Vertical Slice v0.7

**PR:** #9 `product: complete first demo-ready v0.7 vertical slice`
**Branch:** `agent/product-completion-v1`
**Parent (origin/main):** `a462c72b81f1668eef4ea0b7f8e806be4d208b47`
**Reviewed commit (HEAD):** `b6f7311`
**Checkout:** `/Users/akashx/AntigravityTest/traffictwin-claude-review`
**Reviewer:** Claude (independent, mandatory, per AGENTS.md) — no E1 worktree touched
**Date:** 2026-08-08
**Review file:** `docs/reviews/product_completion_claude_review_2026-08-08.md`

---

## 0. Scope and method

This review was performed **only** in the review checkout above on branch `agent/product-completion-v1`. The evaluator process PID 21677 (`eval_sumo_stage1_mc.py`) was confirmed active (`ps aux` shows `R` at 343.9% CPU, 208m) and was left untouched. No writes were made to `/Users/akashx/AntigravityTest/diss`, no mutation of PR #8, no writes to `e1_outputs/colab_inputs/vec_env/tos-data`, no port 8501/8502 listeners started, no `SUMO`/`VEC` execution, no parallel full-suite runs. `vec_env` does not exist in this checkout (`ls vec_env` → No such file).

Documents read completely (via `cat`):

- `AGENTS.md` (header 250 lines, plus coordination grants)
- `docs/traffictwin-design-v0_7.md` (first 200 lines + evidence-source portfolio, plus §6 product modes)
- `docs/implementation-status.md` (first 120 lines + MAN/UX/REL rows grep)
- `docs/current_progress_v0_7.md` (header + tail 200 lines, Phases 190–198)
- `docs/product_completion_execution_2026-08-08.md` (full 255 lines, gap matrix, AC contract)
- `docs/demo_quickstart.md` (full 84 lines)
- `docs/v07_usage.md` (first 80 + last 80), `docs/user_guide.md` (first 80)
- PR description via `gh pr view 9 --json title,body,url`
- Complete diff via `git diff origin/main...HEAD` (682 insertions, 5 files) and `git diff --stat`
- Every changed file full content: `src/traffictwin/ui/demo_workspace_service.py` (220 lines), `src/traffictwin/ui/pages/home.py` (433 lines), `src/traffictwin/ui/pages/bundle_import.py` (351 lines)
- Relevant unchanged callers/services: `src/traffictwin/demo/workspace.py` (safety checks), `src/traffictwin/ui/state.py` (UiConfig, load_ui_config, default_session_state), `src/traffictwin/ui/app.py` (load_ui_config wiring), `src/traffictwin/ui/pages/guided_demo.py`, `src/traffictwin/ui/navigation_v07.py`

Focused validation executed under E1 isolation (no full repo, no parallel, no SUMO):

- `uv sync --extra dev` — ok (traffictwin 0.7.0 installed)
- `uv run ruff check src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py` — **All checks passed!**
- `uv run ruff format --check ...` — **3 files already formatted**
- `uv run mypy src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py` — **Success: no issues found in 3 source files** (unused section warning for gpu/jax/plotly only)
- `uv run pytest tests/unit/test_demo_workspace.py tests/unit/ui/test_page_presentation_home.py -q` — first run: 12 collected, 1 transient failure on timeout=25 then rerun **12 passed in 73.48s** (verbose confirms each)
- `git diff --check` — clean (EXIT 0)
- `grep -rn "TRAFFICTWIN.*KEY\|private.*path\|credentials" src/traffictwin/ui/demo_workspace_service.py` — only hit is doc comment `guesses a private path` (line 112), no credential leak
- `grep -rn` across `src/` for same pattern — no leaked BODS/National Highways keys; `platform_services` etc. correctly refuse private paths
- AppTest journey exercised via `streamlit.testing.v1.AppTest`:
  - Home with `v07_active=True` renders `Model a traffic scenario. Run or import it. Compare the evidence.` title, 5 buttons including **Create demo workspace**, synthetic caption true, metrics `Visible local layers:3, Registered runs:0, Comparisons:0`, no exception.
  - Bundle Import renders **Open example baseline** / **Open example variation** buttons (both present).
  - Clicking **Create demo workspace** with fresh `Path(tmp)/demo` → `st.success` = `Demo workspace created at /tmp/.../demo: 62 scenarios, 62 runs, 3 comparisons. All data is synthetic — no Manchester or live source was used.` + `st.info` about Manchester unavailable; `registry.sqlite` and `workspace.yaml` created, `workspace_status.valid_workspace True`.
  - `ensure_demo_workspace` probed directly for 7 scenarios: create → `created`, idempotent second call → `already_exists`, non-empty dir → `non_empty_without_force`, `/` → `unsafe_path`, `None`/`""` → `invalid_path`, `inspect_demo_workspace` ready vs missing correctly.

---

## 1. PR summary

**Parent audit finding:** bare `streamlit run src/traffictwin/ui/app.py` with no `TRAFFICTWIN_WORKSPACE_PATH` left Home with `workspace_path=None` and generic “No accepted Manchester scene” text, offering no in-UI creation path. Every downstream page therefore required CLI knowledge.

**Selected slice (CODE only, per execution record §5):** thin service-to-page wiring for clean-workspace bootstrapping + honest empty-state copy + Bundle Import discoverability. No provider credential flow, no map-matching/calibration, no MAN/UX/REL status change, no new generation logic.

**Files changed (from `git diff --stat`):**

| File | Change |
|---|---|
| `docs/demo_quickstart.md` | new 84 lines — one-command quick-start, demo vs real workspace table |
| `docs/product_completion_execution_2026-08-08.md` | new 255 lines — gap matrix, ranking, acceptance contract, blockers |
| `src/traffictwin/ui/demo_workspace_service.py` | new 220 lines — `DEFAULT_DEMO_WORKSPACE_PATH`, `DemoWorkspaceResult`, `inspect_demo_workspace`, `ensure_demo_workspace`, `_coerce_workspace_path` |
| `src/traffictwin/ui/pages/home.py` | +91 −7 — imports `ensure_demo_workspace`, adds `has_workspace/workspace_ready` check, branches `Current evidence context` caption, adds `_render_demo_workspace_empty_state()` (container, expander, text_input, primary button, session wiring) |
| `src/traffictwin/ui/pages/bundle_import.py` | +39 — adds `_render_example_shortcuts()` container with two stretch buttons setting `selected_bundle_path` + `selected_baseline_run` / `selected_variation_run` + `st.rerun()` |

No test files changed (gap vs AC-R1).

---

## 2. Validation summary (evidence, not paraphrase)

```
uv run ruff check ...                          → All checks passed!
uv run ruff format --check ...                 → 3 files already formatted
uv run mypy ...                                → Success: no issues found in 3 source files
uv run pytest tests/unit/test_demo_workspace.py tests/unit/ui/test_page_presentation_home.py -v
                                               → 12 passed in 73.48s (8 demo workspace + 4 home presentation)
git diff --check                               → (no output) EXIT 0
grep leaked secrets in demo_workspace_service   → 112: guesses a private path and never mutates ...
AppTest Home empty-state                        → Has Create demo workspace: True, Has caption synthetic: True
AppTest Bundle Import                           → Has Open example baseline: True, Has Open variation: True
AppTest Click Create (tmp/demo)                → Success: Demo workspace created at ... 62 scenarios, 62 runs, 3 comparisons.
inspect/ensure service probe                   → create created 62/62/3 True; already_exists True; non_empty_without_force; unsafe_path; invalid_path; inspect ready True
git diff origin/main...HEAD -- tests/           → (empty — no tests added)
git diff origin/main...HEAD -- docs/implementation-status.md → (empty — correctly unchanged)
ps aux | grep eval_sumo                        → 21677 R 343.9 ... eval_sumo_stage1_mc.py ... (still running, untouched)
ls /Users/akashx/AntigavityTest/traffictwin-claude-review/vec_env → No such file
```

---

## 3. Mandatory 20 questions

| # | Question | Verdict | Evidence | File / line |
|---|---|---|---|---|
| 1 | Does this implementation actually improve a complete user journey? | **CONCERN** (partial pass) | Yes — fresh clone now offers a one-click **Create demo workspace** card that deterministically creates `workspace.yaml` + `registry.sqlite` (62/62/3) and Bundle Import one-click fixtures reduce path-typing friction. Verified via AppTest above. However the journey does not fully close end-to-end: after creation Home's KPIs (`Registered runs`, `Comparisons`) and `manchester.scene` still read `config.workspace_path` (env var) which remains `None`, so metrics stay `0` and the empty-state reappears on rerun as `already_exists` rather than `ready`. Guided Demo / Reports / Compare therefore still see “No standalone workspace is configured” until the process is restarted with `TRAFFICTWIN_WORKSPACE_PATH`. The improvement is real but the last wiring link is missing. | `src/traffictwin/ui/pages/home.py:38-47` (metrics from `config.workspace_path`), `96-101` (`has_workspace` from env), `222-223` (session write only), `src/traffictwin/ui/state.py:142-144` (`load_ui_config` reads env), `src/traffictwin/ui/pages/guided_demo.py:158-161` (still checks `config.workspace_path`) |
| 2 | Is there a simpler existing service that should have been reused? | **PASS** | No duplication. The new module is a thin typed wrapper over `traffictwin.demo.workspace.initialise_workspace` / `workspace_status` with safety checks already in that library (`_ensure_safe_workspace_path` blocking `/`, `$HOME`, `cwd`). No simpler page-level helper existed; reusing `demo/launcher.py` would have pulled CLI process-spawning into UI. | `src/traffictwin/ui/demo_workspace_service.py:15`, `131`, `160`, `src/traffictwin/demo/workspace.py:850-854` |
| 3 | Has scientific or evidence logic leaked into Streamlit/UI code? | **PASS** | Pages remain thin. Home only calls `workspace_status`, `visible_layer_ids`, `build_manchester_deck`; Bundle Import only calls `validate_bundle_for_ui` / `safe_import_bundle_for_ui`. No metric, diagnostic (R0-R8), or provenance calculation inside `st.*` code. The service does not compute metrics. | `src/traffictwin/ui/pages/home.py:7,43,47`, `src/traffictwin/ui/pages/bundle_import.py:12-17`, `src/traffictwin/ui/demo_workspace_service.py:104-113` (docstring: “never duplicates generation logic”) |
| 4 | Does any page or service overclaim what a source provides? | **PASS** (code) / **CONCERN** (docs — see Q16) | Code is honest: empty-state caption says “The demo workspace is synthetic and local. It contains no Manchester, Randy, or live data. All generated records carry `synthetic: true`” (`home.py:185-189`); post-create `st.info` says Manchester scenes remain unavailable and require separately activated real workspace (`home.py:229-232`); Bundle Import caption says fixtures “never represent Manchester or live traffic” (`bundle_import.py:142-145`). No BODS as traffic, no WebTRIS as near-live, no TfGM as live signals. | `src/traffictwin/ui/pages/home.py:185-189`, `229-232`, `src/traffictwin/ui/pages/bundle_import.py:142-145`, `src/traffictwin/ui/demo_workspace_service.py:197-201` |
| 5 | Are unavailable, stale, historical, near-live, live-vehicle and synthetic states still correctly separated? | **PASS** | Evidence-state separation untouched. Home uses `evidence_state_badge(manchester.status)` (`home.py:68`), guided demo badge row `SYNTHETIC·OFFLINE·DETERMINISTIC` (`guided_demo.py` via service), bundle evidence table renders per-category states. No collapse into “live”. | `src/traffictwin/ui/pages/home.py:68`, `src/traffictwin/ui/pages/guided_demo.py:161-163`, `docs/traffictwin-design-v0_7.md` §6, `docs/implementation-status.md` (all MAN still `planned`) |
| 6 | Does any code fabricate defaults when evidence is absent? | **PASS** | Empty workspace → honest empty-state container, not fabricated Manchester layers or zero-filled counts. `inspect_demo_workspace` returns `failed` with `invalid_path`/`unsafe_path` when absent, never inventing counts (`demo_workspace_service.py:50-59,79-87`). Home shows no pydeck chart when `manchester.scene is None`. Bundle Import disables shortcut buttons when fixture missing (`bundle_import.py:178-185`). | `src/traffictwin/ui/demo_workspace_service.py:46-79`, `src/traffictwin/ui/pages/home.py:102-117`, `src/traffictwin/ui/pages/bundle_import.py:178-185` |
| 7 | Does the implementation accidentally broaden Manchester, Randy/VEC or source claims? | **PASS** | No. Demo workspace manifest stays `workspace_type: traffictwin_standalone_demo`, `synthetic: true`, disclaimer “not real Manchester, Randy/VEC, or SUMO output” (`demo/workspace.py:_write_workspace_manifest`). Home warning lists DfT/WebTRIS/TfGM/BODS/National Highways limits verbatim (`home.py:167-171`). No new coverage map, no city-road inference. | `src/traffictwin/demo/workspace.py:846-866`, `src/traffictwin/ui/pages/home.py:167-171` |
| 8 | Are privacy-sensitive paths, identifiers, credentials or raw evidence exposed? | **PASS** with **LOW** concern | No credentials, API keys, or raw BODS rows rendered. The only path echo is `f"Demo workspace created at {workspace}"` (`demo_workspace_service.py:196-199` → `home.py:227` via `st.success`). The underlying `initialise_workspace` blocks the three most sensitive roots (`/`, `$HOME`, `cwd`) (`workspace.py:852`), but an absolute private path like `/Users/akashx/secret/demo` would still be echoed verbatim. Existing pages already expose workspace paths (legacy home `demo_status.path`, `source_health` etc.), so pattern is consistent, but ideally use relative display or the project’s `private path` refusal helper. No `TRAFFICTWIN.*KEY` or `credentials` leak (`grep` shows only comment). | `src/traffictwin/ui/demo_workspace_service.py:112,196-199`, `src/traffictwin/ui/pages/home.py:227`, `src/traffictwin/demo/workspace.py:850-854`, `src/traffictwin/ui/platform_services.py:56-62` (reference pattern) |
| 9 | Is the implementation deterministic where science requires determinism? | **PASS** | `ensure_demo_workspace` → `initialise_workspace` uses `DETERMINISTIC_CREATED_AT` (`2026-07-18`), deterministic `default_workspace_configs()`, deterministic `write_synthetic_bundle`, `Registry` init, and `_fixed_clock()`. Re-read via `workspace_status` reports same counts (62/62/3) on repeat. No randomness or LLM in UI path. | `src/traffictwin/demo/workspace.py:846`, `850-866`, `src/traffictwin/ui/demo_workspace_service.py:197` (re-read authoritative counts) |
| 10 | Are tests testing behaviour rather than merely implementation details? | **FAIL** | The PR adds **zero** test files (`git diff origin/main...HEAD -- tests/` empty). The claimed AC-R1 “unit test for thin service + AppTest for Home→button→success and Bundle Import wiring” is absent. Existing `tests/unit/test_demo_workspace.py` tests the underlying `demo.workspace` library (8 tests) and `tests/unit/ui/test_page_presentation_home.py` tests pre-existing hero/badge presentation (4 tests) — neither exercises the new `demo_workspace_service` or the new empty-state/button path. Behaviour of the new slice is therefore unverified by checked-in tests. | `git diff --stat` (5 files, none under `tests/`), `docs/product_completion_execution_2026-08-08.md:164-165` (claims AC-R1), actual `tests/` diff empty |
| 11 | Are important failure/refusal paths tested? | **FAIL** | Same gap as Q10. The service correctly maps failures to typed reasons (`invalid_path`, `unsafe_path`, `non_empty_without_force`, `already_exists`, `unexpected_error`) and was manually probed for all 7 scenarios (see Validation summary) — but no committed test asserts them. The non-empty refusal is tested at library level (`test_workspace_initialise_refuses_non_empty_path`) but not at the UI wrapper level where the message is surfaced. Unsafe-path, invalid-path, already_exists idempotency have no test. | `src/traffictwin/ui/demo_workspace_service.py:19-27` (reason literals), `48-87`, `131-189` (mapping), manual probe results above, missing `tests/unit/ui/test_demo_workspace_service.py` |
| 12 | Did the implementation add unnecessary abstractions or complexity? | **PASS** with **NIT** | The abstraction is minimal and justified: one dataclass `DemoWorkspaceResult`, two functions, one helper. Nits: `workspace_valid` duplicates information already in `status`; `DemoWorkspaceReason` has `"already_has_workspace"` variant never emitted (dead literal); `inspect_demo_workspace` vs `ensure_demo_workspace` split is clean. | `src/traffictwin/ui/demo_workspace_service.py:19-42` |
| 13 | Are there dead paths, duplicated logic or state inconsistencies? | **CONCERN** (MEDIUM) | Three issues: (1) **Dead path:** `inspect_demo_workspace` defined (`demo_workspace_service.py:46`) but never imported anywhere (`grep` shows zero callers). (2) **Duplicated logic:** Home calls `workspace_status(config.workspace_path)` three times — for `comparison_count` (`:43`), `workspace_ready` (`:100`), and legacy home (`:300`) — could reuse one result. (3) **State inconsistency (high impact):** Home writes `st.session_state["active_registry_path"]` and `["_active_demo_workspace_path"]` (`home.py:222-223`), but Home’s own KPIs (`run_count` from `load_project_status(config.registry_path)`, `comparison_count` from `config.workspace_path`) and Guided Demo (`workspace_status(config.workspace_path)`) read from `UiConfig` (env var), not session. The two sources of truth diverge after in-browser creation, causing stale KPIs and “No standalone workspace is configured” persisting. Bundle Import correctly uses session for `selected_bundle_path`, so that chain survives, but workspace context does not. | `src/traffictwin/ui/demo_workspace_service.py:46-79`, `src/traffictwin/ui/pages/home.py:43-47`, `96-101`, `222-223`, `src/traffictwin/ui/state.py:142-144`, `src/traffictwin/ui/pages/guided_demo.py:158-161` |
| 14 | Does navigation/state survive the intended workflow? | **CONCERN** (MEDIUM-HIGH) | **Bundle path survives:** `bundle_import.py:175-176,184-185` sets session, `helpers.selected_bundle_path()` reads session, `tests/ui/test_cross_page_state.py` proves it (existing test). **Workspace/registry does not:** after Home creation, `active_registry_path` session is set but `config.workspace_path`/`config.registry_path` (derived from `TRAFFICTWIN_WORKSPACE_PATH` env) stays `None`; navigating to Guided Demo, Reports (`list_workspace_reports(config.workspace_path)`), Source Health, etc. still sees `None`. AppTest after click still has `has_workspace False`. The intended journey “Home → Create → Explore Manchester / Start Guided Demo → Compare → Reports” breaks at the second hop without a process restart with env vars. | `src/traffictwin/ui/pages/bundle_import.py:175-185`, `src/traffictwin/ui/pages/helpers.py:13-17`, `src/traffictwin/ui/pages/home.py:222-223` vs `src/traffictwin/ui/state.py:142-144`, `src/traffictwin/ui/pages/guided_demo.py:158-165`, `src/traffictwin/ui/pages/home.py:157` (`list_workspace_reports(config.workspace_path)`) |
| 15 | Is the clean-workspace experience actually usable? | **CONCERN** (MEDIUM) | For a true clean clone (`STREAMLIT_SERVER_HEADLESS`, no env vars), Home now renders the **Create demo workspace** card with an editable path defaulting to `.traffictwin-demo` and bounded help text — usability win confirmed via AppTest. Clicking creates `workspace.yaml`/`registry.sqlite` deterministically and shows honest success + “Manchester scenes remain unavailable …” info. However the empty-state remains visible on next render (as `already_exists` info) and KPIs stay at `0` because they still read env-based config, so a non-technical user sees a success toast that does not translate into visible `Registered runs: 62` or Reports inventory without restarting the server with `TRAFFICTWIN_WORKSPACE_PATH=.traffictwin-demo`. The Bundle Import shortcuts are usable even before workspace, but Reports/Provenance/Comparison pages that depend on `config.workspace_path` remain empty. Usable to create files, not yet usable to continue without CLI. | `src/traffictwin/ui/pages/home.py:190-233`, AppTest evidence: metrics `0` before and after creation, success message vs stale `has_workspace`; `docs/demo_quickstart.md:22-31` |
| 16 | Are documentation and implementation-status updates factually justified? | **CONCERN** (MEDIUM) | **Implementation-status:** correctly **not** changed — `git diff origin/main...HEAD -- docs/implementation-status.md` empty, all `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01` remain `planned`, no capability promoted. Good. **Demo quick-start:** mostly accurate and disclosure-heavy, but overstates one point: § “What the demo workspace contains” and § “End-to-end browser journey” step 1 claim “Home — after creation shows `Visible local layers: 0` … `Registered runs: 62`, `Comparisons: 3`” — true for `traffictwin demo launch .traffictwin-demo` (Option B) but false for the in-browser Option A as currently wired (AppTest shows `0`). Troubleshooting table is accurate. Execution record §5 acceptance contract AC-F1 says button “displays success with scenario/run/comparison counts. Pressing again when a workspace is ready is a safe no-op” — true for toast, but the contract omits that KPIs stay stale and that a process reload with env vars is still needed to see inventory. No private path or credential documented. | `docs/demo_quickstart.md:22-31`, `docs/product_completion_execution_2026-08-08.md:131-135`, `git diff --stat` |
| 17 | Has any MAN/UX/REL capability been promoted beyond its accepted evidence? | **PASS** | No promotion. Docs explicitly list remaining blockers (H-B1 174 rows, S-B1 calibration, P-B1 BODS retention, etc.) and the PR does not edit `implementation-status.md` or `current_progress_v0_7.md`. Badge copy and unavailable states keep `planned` vs `working_bounded` distinct. | `docs/product_completion_execution_2026-08-08.md:182-193`, `docs/implementation-status.md` (still `planned`), `docs/demo_quickstart.md:49-53` |
| 18 | Does the work remain completely independent of the E1 campaign? | **PASS** | Verified. `git diff origin/main...HEAD` touches only `docs/*` and `src/traffictwin/ui/*`; no `diss/`, `e1_outputs/`, `colab_inputs`, `vec_env/tos-data`, or `agent/e1-*` branches. Evaluator PID 21677 still `R`. No port 8501/8502 use in PR, no SUMO/VEC imports in new code. `.traffictwin-demo` is repo-local and does not collide with `e1_outputs/e1-multidraw-physical-*`. | `git diff --stat`, `ps aux`, `ls diss`, `ls vec_env` (no such file) |
| 19 | Would this survive a dissertation-supervisor demonstration? | **CONCERN** (MEDIUM) | Supervisor viewing the honest copy and synthetic badges would be reassured (all demo records carry `synthetic: true`, Manchester/BODS/WebTRIS limits stated verbatim, no live claim). The one-click creation toast is supervisor-friendly. What would not survive is the follow-through: supervisor clicks **Start Guided Demo** expecting the “Active evidence context: Workspace Ready | Scenarios 62” banner but instead sees the warning “No standalone workspace is configured” (because `guided_demo.py` reads `config.workspace_path`), and Home still shows `Registered runs: 0` despite “62 runs” toast. A supervisor asking “show me the reports you just generated” would see an empty `list_workspace_reports(config.workspace_path)` inventory. The CLI path (`traffictwin demo launch .traffictwin-demo`) survives perfectly; the in-browser path needs the session/env wiring fix to be viva-ready. | `src/traffictwin/ui/pages/guided_demo.py:158-165`, `src/traffictwin/ui/pages/home.py:38-47,157`, AppTest post-click state |
| 20 | Is anything sufficiently serious that the PR should not be merged? | **CONCERN** → **REQUEST_CHANGES** (not BLOCK) | No **BLOCKER** (no data loss, no credential leak, no evidence fabrication, no broadened coverage claim, no E1 contamination). But the three **HIGH** issues (state inconsistency breaking the advertised end-to-end journey, and missing committed tests violating AC-R1) are material enough that merging now would publish documentation promising “one-click … `Registered runs: 62`” that the in-browser path does not fulfil, and would land dead code (`inspect_demo_workspace`) and a write-only session key. These are fixable in the same branch without scope creep. Verdict below reflects this. | Findings table §4 |

---

## 4. Findings (classified)

| ID | Severity | File / lines | Function / component | Problem | Why it matters | Evidence | Recommended correction |
|---|---|---|---|---|---|---|---|
| F-1 | **HIGH** | `src/traffictwin/ui/pages/home.py:222-223` vs `src/traffictwin/ui/state.py:142-144`, `src/traffictwin/ui/pages/home.py:38-47,96-101`, `src/traffictwin/ui/pages/guided_demo.py:158-165` | Home empty-state success handler + `UiConfig` wiring | After **Create demo workspace**, Home writes `active_registry_path` + `_active_demo_workspace_path` to `st.session_state`, but all downstream reads (Home KPIs `run_count`/`comparison_count`, Manchester scene `load_local_manchester_scene`, Reports `list_workspace_reports`, Guided Demo banner) use `config.workspace_path` / `config.registry_path` derived from `TRAFFICTWIN_WORKSPACE_PATH` env var, not session. So success toast shows “62 scenarios” yet metrics stay `0`, empty-state reappears as `already_exists` on rerun, and Guided Demo still warns “No standalone workspace is configured”. | Breaks the advertised “clean-workspace → Create → see counts → follow Guided Demo” end-to-end journey; supervisor demo fails at second click; violates AC-F1 intent that creation “wires session/registry in-place” and “displays success with counts” translating to visible inventory. | AppTest after click: `st.success` shows `62 scenarios` but `app.metric` still `0` on same run; `has_workspace` recomputed from `config.workspace_path` remains `False`; second `ensure_demo_workspace` call returns `already_exists` not `ready`. Code: `load_ui_config()` reads `os.getenv("TRAFFICTWIN_WORKSPACE_PATH")` only. | Make the workspace path observable via session fallback. Minimal options: (a) have `load_ui_config` respect `st.session_state["_active_demo_workspace_path"]` when env var absent (or add `active_workspace_path()` helper used by Home, Guided Demo, Reports), **or** (b) change Home to call `st.success` and then `st.rerun()` after setting `os.environ["TRAFFICTWIN_WORKSPACE_PATH"]` for the child process (and document that a real server restart via `traffictwin demo launch` is the canonical path), **or** (c) make Home read `active_registry_path` session fallback for KPIs (e.g., `Path(st.session_state.get("active_registry_path", config.registry_path))`). Smallest fix is (c) + reusing one `workspace_status` result for `has_workspace`, `comparison_count`, and `run_count`. Add an AppTest asserting post-click `has_workspace`/`run_count` updates. Do not guess private owner paths — only honour the user-confirmed demo path. |
| F-2 | **HIGH** | `src/traffictwin/ui/demo_workspace_service.py` (all) vs `tests/` (no change) | New thin UI service — test coverage | PR adds a new public service with 7 distinct reason codes and idempotency, but commits **zero** tests. `git diff -- tests/` empty. AC-R1 claimed “unit test … proving deterministic initialisation, refusal on non-empty path, and idempotency” and “AppTest covering Home empty-state → button → success” — neither exists in branch. | Violates the execution record’s own acceptance contract; leaves failure paths (`non_empty_without_force`, `unsafe_path`, `invalid_path`, `already_exists`, `unexpected_error`) unverified in CI; AppTest for empty-state wiring missing means F-1 could have been caught earlier. | `git diff --stat` shows 0 test files; `git log --name-only` lists only the 5 files; manual probe shows correct behaviour but no committed test. | Add `tests/unit/ui/test_demo_workspace_service.py` covering `ensure_demo_workspace` (create deterministic 62/62/3, already_exists idempotent, non_empty refusal, unsafe `/`/`$HOME`/`cwd`, None/empty, string path coercion, whitespace trim) and `inspect_demo_workspace` (ready vs missing vs invalid). Add `tests/unit/ui/test_page_presentation_home_demo_workspace.py` (or extend `test_page_presentation_home.py`) with AppTest: empty-state renders button, click with `tmp_path` creates `workspace.yaml` + `registry.sqlite`, asserts `st.success` contains `62` and `synthetic`, asserts on rerun button becomes `already_exists` info, asserts Bundle Import shortcuts set session keys. Keep E1 isolation: no parallel, no SUMO, timeout ≥25s. |
| F-3 | **MEDIUM** | `src/traffictwin/ui/demo_workspace_service.py:46-79` | `inspect_demo_workspace` | Defined, typed, documented, but never imported or called anywhere in `src/` (`grep -rn inspect_demo_workspace src/` returns only definition). | Dead public surface; readers assume it is used for the initial empty-state inspect, but Home calls `workspace_status` directly (`home.py:100`) instead. Increases maintenance burden and suggests an intended inspection path that was not wired. | `grep` result above; `home.py` imports only `ensure_demo_workspace`, not `inspect_demo_workspace`. | Either wire it (e.g., use `inspect_demo_workspace(config.workspace_path)` in Home to unify reason handling, or reuse `ensure_demo_workspace` path’s pre-check) or delete it and inline the need via `workspace_status`. Do not keep both without use. |
| F-4 | **MEDIUM** | `src/traffictwin/ui/pages/home.py:38-47` + `96-101` + `300` | Home KPI + ready check | `workspace_status(config.workspace_path)` called three times per render (for `comparison_count`, `workspace_ready`, and legacy home `demo_status`). Each call hits filesystem (`workspace.yaml` read, `registry.sqlite` query). | Duplication; also masks the fact that all three derive from same path — fixing F-1 in one place but not the others is a bug vector. | Code lines cited; no single `status = workspace_status(...)` reused. | Cache locally: `ws_status = workspace_status(config.workspace_path) if has_workspace else None` then derive `comparison_count`, `workspace_ready`, `scenario_count` etc. from that one object. Share with `_render_demo_workspace_empty_state` via argument if needed. |
| F-5 | **MEDIUM** | `docs/demo_quickstart.md:31` + `docs/product_completion_execution_2026-08-08.md:137-141` | Documentation — counts visibility | Quick-start step 1 says “Home — after creation shows `Visible local layers: 0` … `Registered runs: 62`, `Comparisons: 3`.” Execution record AC-F2 says Home’s “Current evidence context” honestly reads `SYNTHETIC …` and map area shows honest copy. As currently wired (F-1), in-browser creation does **not** make those KPIs read `62`/`3`; only CLI `traffictwin demo launch .traffictwin-demo` does. | Docs overpromise the in-browser vertical slice; a fresh user following Option A will see `0` and think creation failed despite success toast, leading to a support question during demo day. | AppTest evidence: after `ensure_demo_workspace` + `st.success`, `app.metric` still `Registered runs 0`; docs line `Registered runs: 62` contradicts observed. | Reword quick-start to distinguish Option A (in-browser) vs Option B (CLI): “Option B shows `62`/`3` immediately because the launcher sets `TRAFFICTWIN_WORKSPACE_PATH` in its child process; Option A creates the same files (verify with `uv run traffictwin demo status .traffictwin-demo` — expect `valid_workspace True, 62/3`) but Home KPIs update only after restarting the server with `TRAFFICTWIN_WORKSPACE_PATH=.traffictwin-demo` or after the session-fallback fix (F-1) lands.” Add a one-line “Verify” snippet after creation: `uv run traffictwin demo status .traffictwin-demo`. |
| F-6 | **MEDIUM** | `src/traffictwin/ui/pages/home.py:222-223` | Session key `_active_demo_workspace_path` | Written but never read anywhere (`grep -rn _active_demo_workspace_path src/` returns only this write). | Write-only state suggests an intended “active workspace” propagation that was not finished; confuses future maintainers searching for where demo path is consumed. | `grep` result above. | Either read it where `config.workspace_path` is needed (as part of F-1 fix) or remove it if `active_registry_path` alone is the contract (but then reports still need workspace path for comparisons/exports). Prefer reading it via a small helper `current_workspace_path(config)` that prefers session demo path when env var absent. |
| F-7 | **LOW** | `src/traffictwin/ui/demo_workspace_service.py:19-27` + `src/traffictwin/ui/demo_workspace_service.py:196-199` | `DemoWorkspaceResult` + path echo | `DemoWorkspaceReason` includes `"already_has_workspace"` never emitted (only `"already_exists"` used); `workspace_valid` duplicates `status != "failed"`; success message interpolates `Path` verbatim. | Minor API debt + low-grade private-path exposure (see Q8). | Literal `"already_has_workspace"` not found elsewhere; `f"Demo workspace created at {workspace}"` at line 197. | Remove unused literal variant, or emit it; consider deriving `workspace_valid` property from `status`. For path echo, display `workspace.name` or relative path via `_workspace_relative` pattern, or gate through a safe-display helper that refuses absolute private paths. |
| F-8 | **LOW** | `src/traffictwin/ui/pages/bundle_import.py:175-185` | Example shortcuts | Buttons correctly set `selected_bundle_path` + `selected_*_run` and `st.rerun()`, but do not touch `active_registry_path`. If user created demo workspace at a non-default location, selecting a fixture still leaves registry pointing at demo registry — correct for demo, but if user later imports via batch to a different registry, shortcut and registry text_input diverge. | Low confusion; not a bug because demo registry is the intended target, but worth noting that shortcut + workspace creation are independent. | Code lines cited; `st.session_state["active_registry_path"] = str(registry_path)` only in `bundle_import.py:52` from text_input, not from shortcut. | No change needed now; optionally have shortcut read `active_registry_path` fallthrough or document that shortcuts select fixtures, registry remains the demo registry. |
| F-9 | **NIT** | `src/traffictwin/ui/pages/home.py:225-227` | Comment about reload | Comment says “Pages that read `TRAFFICTWIN_WORKSPACE_PATH` via UiConfig inherit on next rerun; for the current rerun we also publish the comparison/run signal via registry path.” The second clause is not realised — no comparison/run signal is published beyond `active_registry_path` which Home KPIs ignore. | Stale comment will mislead next editor into thinking the fix is already present. | Lines 225-227. | Update comment to reflect actual contract after F-1 fix, or remove until fix lands. |
| F-10 | **NIT** | `src/traffictwin/ui/demo_workspace_service.py:72-76` | `inspect_demo_workspace` error mapping | When `workspace_status.valid_workspace` is False but messages exist, function returns `reason="unexpected_error"` with joined messages, rather than a more specific `invalid_path`/`non_empty_without_force`. | NIT — error taxonomy is coarse but not harmful; the caller surfaces `st.error(result.message)` verbatim, so user sees the underlying messages anyway. | Lines 72-87. | Keep as is or map to `"invalid_path"` for missing marker; low priority. |

No **BLOCKER** findings. The three HIGH-severity issues are the only merge-preventers; the rest are polish that can ride the same branch.

---

## 5. Evidence-state boundary audit

Honoured. Synthetic records self-identify as `synthetic: true`, `SYNTHETIC`/`DETERMINISTIC`/`OFFLINE` badges appear on Home, Guided Demo, Bundle Import caption, and workspace manifest disclaimer. Manchester evidence-state badges (`historical`, `near_live`, `live_vehicle`, `stale`, `unavailable`, `synthetic`) remain distinct and source-specific; no pipeline presents BODS `LiveTransitVehicleObservation` as `TrafficObservationRecord` or general traffic flow. National Highways overlays remain `near_live`/`stale`, TfGM signals remain infrastructure-only. No page fabricates coverage or fills missing observations with synthetic/stale values (explicit caption at `home.py:112-115`).

---

## 6. Privacy and non-broadening audit

No Manchester/Randy/VEC source claim broadened. All `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01` remain `planned` per `implementation-status.md` (unchanged in diff). No new basemap provider, no public hosting, no credentials committed. The only path rendering is the user-confirmed demo directory itself; the three sensitive roots (`/`, `$HOME`, `cwd`) are blocked by `_ensure_safe_workspace_path`. No `TRAFFICTWIN*KEY` or `BODS_API_KEY` handling in new code.

---

## 7. Determinism audit

The demo workspace generation is pinned: `DETERMINISTIC_CREATED_AT = 2026-07-18T00:00:00Z`, `default_workspace_configs()` fixed, `Registry` seeded, `_fixed_clock()` used throughout, and final counts re-read authoritatively via `workspace_status` after creation. `ensure_demo_workspace` is synchronous and bounded; reruns yield identical `62`/`62`/`3` counts (verified). Bundle Import shortcuts are deterministic path selections, not generation.

---

## 8. Navigation / state survival (beyond F-1)

Bundle-selection survival is correct and tested (`helpers.selected_bundle_path()` reads `st.session_state["selected_bundle_path"]`, `test_cross_page_state.py` in existing suite). The missing link is workspace/registry propagation (F-1). No regression in existing `st.navigation` grouping; `home.py` preserves both `v07` and legacy branches and the `Streamlit` navigation guard.

---

## 9. Clean-workspace usability (beyond Q15)

The empty-state card itself is usable: bordered container, clear headline “Create a demo workspace”, help expander with default directory, `width="stretch"` primary button, bounded validation messages, and idempotent already_exists handling. The friction removed vs typing `traffictwin demo launch .traffictwin-demo` is substantial. The gap is only the post-creation KPI visibility (F-1/F-5). No new filesystem surface beyond the user-confirmed demo directory; `non_empty_without_force` refuses to clobber existing user content with a clear caption.

---

## 10. Documentation accuracy

`docs/demo_quickstart.md` is concise, disclosure-heavy, and correctly distinguishes demo vs real workspace in a table (path, initialiser, content, provider use, claim, marker). It points to `v07_usage.md`, `v07_durable_workspace.md`, `v07_real_workspace_run.md` for real activation and to `implementation-status.md`/`open-questions.md` for unavailable functions. The only factual overstatement is the immediate `62`/`3` KPI visibility for Option A (F-5). `docs/product_completion_execution_2026-08-08.md` is thorough, but its acceptance contract would benefit from the same Option-A vs Option-B caveat and from noting that AC-R1 tests are not yet committed.

---

## 11. E1 campaign isolation (explicit proof)

- **Branch touch scope:** `git diff origin/main...HEAD --stat` = 5 files, all under `docs/` or `src/traffictwin/ui/` in the **product** checkout (`/Users/akashx/AntigravityTest/traffictwin-claude-review`). Zero files under `diss/`, `e1_outputs/`, `colab_inputs`, `vec_env/`, `tos-data`.
- **Evaluator still running:** `ps aux | grep eval_sumo_stage1_mc.py` → PID 21677 `R` 343.9% CPU, start 19:02, 208m elapsed, same `tos-data-full` trace/actor/out-json as in PR description — not signalled, not stopped, not niced.
- **No port contention:** no `lsof -nP -iTCP:8501/8502` listeners started by this review; `uv run` invocations only ran `ruff`/`mypy`/`pytest` and short `AppTest` runs that create/destroy ephemeral Streamlit runners without binding.
- **No SUMO/VEC execution:** `grep -rn vec_env\|eval_sumo\|substep-queue` in changed files = 0; focused pytest did not invoke `sumolib`.
- **Worktree separation:** `ls /Users/akashx/AntigravityTest/diss` shows `agent/e1-multidraw-physical-v1` untouched; `ls vec_env` in review checkout → No such file. The review file itself is the only new file in the review checkout (to be committed on this branch).

---

## 12. Overall verdict — **REQUEST_CHANGES**

**Not BLOCK** — no blocker-grade defect (no data loss, no credential leak, no evidence fabrication, no E1 contamination, no broadened Manchester/Randy claim, and the change is additive behind an empty-state branch that leaves existing workspaces untouched; revert is one commit per execution record §“Risk & rollback”).

**Not APPROVE / APPROVE_WITH_MINOR_FIXES** — the in-browser vertical slice promises an end-to-end journey (“Home → Create → see `62`/`3` → Guided Demo → Compare → Reports”) that is currently broken at the session→`UiConfig` wiring seam (F-1), and the branch lands no committed tests for the new public service despite claiming them (F-2). Merging as-is would publish documentation (`demo_quickstart.md:31`) that a fresh `streamlit run` + button yields visible `62` runs, which the current code does not. Those are **HIGH** findings that a supervisor demo would surface.

**REQUEST_CHANGES** with narrow scope:

1. Fix workspace/registry propagation so that in-browser creation is reflected in Home KPIs and downstream pages without requiring a manual `TRAFFICTWIN_WORKSPACE_PATH` restart (F-1) — small helper like `current_workspace_path(config)` respecting `st.session_state["_active_demo_workspace_path"]` and a session-aware registry fallback, plus reuse of one `workspace_status` result.
2. Land the missing committed tests (F-2) — unit tests for `ensure_demo_workspace`/`inspect_demo_workspace` covering all reason codes and idempotency, plus AppTest for Home empty-state → button → success → already_exists and Bundle Import shortcuts.
3. Address polish that rides the same diff with negligible risk: remove or wire `inspect_demo_workspace` (F-3), de-duplicate `workspace_status` calls (F-4), and correct the `62`/`3` KPI claim in `demo_quickstart.md` to distinguish Option A vs Option B (F-5).

All other aspects — evidence honesty, determinism, privacy, E1 isolation, ruff/format/mypy/pytest, and the underlying thin-service design — are **PASS** and should not be regressed.

---

## 13. Recommended correction checklist (for the branch owner)

- [ ] **F-1** Introduce `def current_workspace_path(config: UiConfig) -> Path | None` (or `current_registry_path`) that prefers `st.session_state.get("_active_demo_workspace_path")` / `active_registry_path` when `config.workspace_path`/`config.registry_path` is `None`, and use it in `home.py` for `run_count`/`comparison_count`/`manchester.scene`/`list_workspace_reports` and in `guided_demo.py` banner. Set the session key to the resolved `result.path` (already done) and ensure `workspace_status` is called once and reused.
- [ ] **F-2** Add `tests/unit/ui/test_demo_workspace_service.py` (7 scenarios) and extend `tests/unit/ui/test_page_presentation_home.py` or add `test_page_presentation_home_demo_workspace.py` with the AppTest journey described; run `uv run pytest tests/unit/ui/test_demo_workspace_service.py tests/unit/ui/test_page_presentation_home.py::test_v07_home_* -q` and include in CI.
- [ ] **F-3** Either make Home call `inspect_demo_workspace(config.workspace_path)` instead of direct `workspace_status` (and delete the duplicated try/except), or delete `inspect_demo_workspace` if not needed.
- [ ] **F-4** Deduplicate `workspace_status` calls in Home into a single `ws_status` local.
- [ ] **F-5** Edit `docs/demo_quickstart.md:31` step 1 to clarify Option A requires either the session-fallback fix or a `TRAFFICTWIN_WORKSPACE_PATH` restart / `uv run traffictwin demo status .traffictwin-demo` verification; keep Option B as immediate `62`/`3`.
- [ ] **F-6** Either consume `_active_demo_workspace_path` in the helper or remove the write.
- [ ] Re-run mandated gates: `uv run ruff check` + `ruff format --check` + `uv run mypy src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py` + `uv run pytest tests/unit/test_demo_workspace_service.py tests/unit/ui/test_page_presentation_home.py -q` + `git diff --check`.
- [ ] Update `docs/product_completion_execution_2026-08-08.md` AC-R1 to reflect committed test file names and the caveat fixed in F-5.

---

## 14. Commands executed (so the owner can re-run)

```bash
git -C /Users/akashx/AntigravityTest/traffictwin-claude-review diff origin/main...HEAD --stat
git -C /Users/akashx/AntigravityTest/traffictwin-claude-review diff origin/main...HEAD
gh pr view 9 --json title,body,url
uv sync --extra dev
uv run ruff check src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py
uv run ruff format --check src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py
uv run mypy src/traffictwin/ui/demo_workspace_service.py src/traffictwin/ui/pages/home.py src/traffictwin/ui/pages/bundle_import.py
uv run pytest tests/unit/test_demo_workspace.py tests/unit/ui/test_page_presentation_home.py -q   # (and -v retry)
git diff --check
grep -rn "TRAFFICTWIN.*KEY\|private.*path\|credentials" src/traffictwin/ui/demo_workspace_service.py
ps aux | grep eval_sumo
ls /Users/akashx/AntigravityTest/diss | head
# AppTest probes (via uv run python - <<'PY' with streamlit.testing.v1.AppTest)
```

All probes were bounded, synchronous, single-process, and left PID 21677 untouched — consistent with the task’s E1 isolation requirement.

---

## 15. Top 3 findings (for the hand-off)

1. **[HIGH] Workspace context does not survive navigation** — `home.py` writes `active_registry_path` to session but KPIs, Manchester scene, Reports, and Guided Demo read `config.workspace_path` from the env var, so the success toast says “62 scenarios” while Home still shows `0` and Guided Demo still warns “No workspace configured”. Fix via a small session-aware helper and single `workspace_status` reuse.

2. **[HIGH] Missing committed tests for the new service/UI** — branch claims AC-R1 tests but `git diff -- tests/` is empty; `inspect_demo_workspace`/`ensure_demo_workspace` reason codes and Home’s button wiring have no checked-in coverage. Add `test_demo_workspace_service.py` and AppTest for Home/Bundler shortcuts.

3. **[MEDIUM] Docs overstate immediate KPI visibility for the in-browser path** — `demo_quickstart.md:31` says in-browser creation shows `Registered runs: 62` immediately, but with current wiring only CLI `traffictwin demo launch .traffictwin-demo` does. Needs Option-A vs Option-B caveat (or F-1 fix).

---

*Reviewer: Claude (independent mandatory review, per task spec). No E1 worktree touched, no PR #8 mutated, no port 8501/8502 used, no SUMO/VEC executed. Do not merge until REQUEST_CHANGES addressed. Do not silently fix code — owner lands the corrections on `agent/product-completion-v1` and pushes. This review file is the only artifact written in the review checkout.*

---

## Re-review 2026-08-08 (fixes 5606a7c)

**Re-reviewer:** Claude (mandatory, per AGENTS.md) — no E1 worktree touched
**Re-reviewed commit:** `5606a7c` (`product: address Claude review findings for demo-ready slice`)
**Base of diff:** `b6f7311` (original REQUEST_CHANGES commit) .. `5606a7c`
**Checkout:** `/Users/akashx/AntigravityTest/traffictwin-claude-review` on `agent/product-completion-v1`
**Date:** 2026-08-08
**Evaluator PID 21677:** confirmed `R` / `372% CPU` before and after — left untouched, no writes to `diss/`, `e1_outputs/`, `vec_env`, no parallel full suite, no SUMO/VEC, no ports 8501/8502 (E1 isolation respected).
**Method:** `git diff b6f7311..5606a7c` read; all 7 changed/new files read; `uv sync --extra dev` + focused gates + manual AppTest probes via `uv run python` with `streamlit.testing.v1.AppTest`.

### Fix commit summary

`git diff --stat b6f7311..5606a7c`:

- `docs/demo_quickstart.md` — reworded Home step 1 to distinguish session vs `TRAFFICTWIN_WORKSPACE_PATH` and added `uv run traffictwin demo status .traffictwin-demo` check.
- `src/traffictwin/ui/demo_workspace_service.py` — removed dead literal `already_has_workspace` from `DemoWorkspaceReason` (1 line).
- `src/traffictwin/ui/pages/home.py` — added `Path` import, new helpers `_resolve_effective_demo_paths`, `_comparison_count_for`, `_workspace_presence`; wired `load_project_status`/`comparison_count`/`manchester`/`list_workspace_reports` to effective paths; renamed `hint_col` → `_hint_col`; `has_workspace`/`workspace_ready` now via helper.
- `src/traffictwin/ui/pages/guided_demo.py` — session fallback for `_active_demo_workspace_path` when `config.workspace_path is None` (6 lines + `Path` import).
- `tests/unit/ui/test_demo_workspace_service.py` — new 10-test file covering `ensure_demo_workspace`/`inspect_demo_workspace`.
- `tests/unit/ui/test_page_presentation_home_demo_workspace.py` — new 7-test AppTest file for Home auto-hide and Bundle Import shortcuts.
- `docs/reviews/product_completion_claude_review_2026-08-08.md` — original review (already present at `b6f7311`) retained verbatim; this re-review is an append-only addendum.

### Focused gates (E1-isolated, no full suite, no parallel)

```
uv sync --extra dev                                         → Resolved 91 packages / 80 checked — ok
uv run ruff check src/traffictwin/ui/demo_workspace_service.py \
                src/traffictwin/ui/pages/home.py \
                src/traffictwin/ui/pages/guided_demo.py       → All checks passed!
uv run ruff format --check (same 3 files)                    → 3 files already formatted
uv run mypy (same 3 files)                                   → Success: no issues found in 3 source files
uv run pytest tests/unit/ui/test_demo_workspace_service.py \
              tests/unit/ui/test_page_presentation_home_demo_workspace.py -q → 17 passed in 95.88s
git diff --check                                             → clean (exit 0)
```

All gates were run exactly as tasked; no replacement linter/mypy invocation, no `-k 'not ...'` filtering.

### Finding-by-finding verification

#### F-1 — Clean-workspace KPIs show 62/3 after session creation (HIGH)

**Fix:** `src/traffictwin/ui/pages/home.py` now introduces `_resolve_effective_demo_paths(config)` which (a) treats an invalid `config.workspace_path` (e.g. the diss harness `TRAFFICTWIN_WORKSPACE_PATH=/Users/akashx/AntigravityTest/diss/data/workspace-v0.7` whose `workspace.yaml` is missing → `valid_workspace False`) as absent, (b) falls back to `st.session_state["_active_demo_workspace_path"]`/`active_registry_path` with validation and a prefix guard (`candidate.startswith(workspace)` when workspace valid; honour any demo registry when no valid workspace). All downstream reads in `_render_v07_home` — `load_project_status(effective_registry_path)`, `_comparison_count_for(effective_workspace)`, `load_local_manchester_scene(workspace, ...)`, `list_workspace_reports(effective_workspace)` — now use effective paths. `guided_demo.py:_render_track_status` adds the session fallback when `config.workspace_path is None` (showing `Ready | Scenarios: 62`).

**Verified via AppTest (`uv run python /tmp/verify_home_kpi.py`):**

- `TRAFFICTWIN_WORKSPACE_PATH` in this checkout is the diss path; `workspace_status(env)` → `valid=False, 0/0/0, ["No such file: workspace.yaml", "registry.sqlite is missing"]` — correctly treated as absent.
- Home with `initialise_workspace(tmp/"kpi-demo")` then `session_state["_active_demo_workspace_path"]=...` / `active_registry_path=...` + two `run(timeout=30)` → metrics `Visible local layers: 0, Registered runs: 62, Comparisons: 3` and `Create demo workspace` button hidden — **pass**.
- Guided Demo with clean env (`TRAFFICTWIN_WORKSPACE_PATH` unset, `session_state` set) → `**Workspace:** Ready | Scenarios: 62 | Imported runs: 62 | Comparisons: 3` — **pass** for the intended clean-checkout journey.
- Click flow: before click `Registered runs: 0, Comparisons: 0` with button present; after `Create demo workspace` click → `st.success` contains `62 scenarios, 62 runs, 3 comparisons` + `synthetic`; on immediate rerun same-process metrics still `0` (expected — session state propagation completes on next Streamlit rerun); on next `run()` → `62/3` and button hidden — matches Streamlit's rerun semantics observed in `tests/unit/ui/test_page_presentation_home_demo_workspace.py:test_home_effective_workspace_hides_create_after_session_creation` (two-run pattern). The task's "KPIs now show 62/3 after session creation" is therefore satisfied on the effective next render.

**Residual nuance (minor, not merge-blocking):** `guided_demo.py` only falls back when `config.workspace_path is None`, not when it is present but invalid (non-`None` invalid diss path). With the diss env set, a user who creates a demo workspace then navigates to Guided Demo in the *same shell* sees `Workspace: Unavailable | Scenarios: 0` until the shell's `TRAFFICTWIN_WORKSPACE_PATH` is cleared (clean checkout has no such var, so the issue does not arise for the advertised `streamlit run src/traffictwin/ui/app.py` clean-clone flow). Home handles the invalid-env case; Guided Demo does not yet mirror that branch. Classified **LOW** — does not affect the clean-clone (env unset) journey and can be aligned in a follow-up by reusing the same `valid_workspace` check as `home.py:195`.

**Verdict on F-1: RESOLVED** (with the LOW guided-demo invalid-env edge noted above).

#### F-2 — Tests for service + Home/Bundler wiring (HIGH)

New files exist and pass:

- `tests/unit/ui/test_demo_workspace_service.py` — 10 tests: `test_ensure_creates_deterministic_demo_with_counts` (62/62/3 + `synthetic` + files exist), `test_ensure_is_idempotent_on_existing_workspace`, `test_ensure_refuses_non_empty_without_marker`, `test_ensure_rejects_unsafe_paths` (`/`, `Path.home()`, `Path.cwd()`), `test_ensure_rejects_none_and_empty_string` (`None`/`""`/`"   "`), `test_ensure_accepts_string_path`, `test_ensure_trims_whitespace`, `test_inspect_reports_ready_for_existing`, `test_inspect_reports_failed_for_missing`, `test_default_path_is_repo_relative`. Covers every `DemoWorkspaceReason` except `unexpected_error` as an explicit `reason == "unexpected_error"` assertion — but the two `failed` paths exercise it (`non-existent` and `corrupt workspace.yaml` both yield `reason="unexpected_error"` as seen in probe; the tests assert `status=="failed"` without narrowing reason, which is acceptable because `unexpected_error` is the catch-all for non-typed failures). All required reason codes are hit.
- `tests/unit/ui/test_page_presentation_home_demo_workspace.py` — 7 AppTests: `test_home_empty_state_offers_create_demo_workspace`, `test_home_create_demo_workspace_creates_and_shows_success`, `test_home_create_demo_workspace_shows_already_exists_on_rerun`, `test_home_effective_workspace_hides_create_after_session_creation`, `test_bundle_import_shows_example_shortcuts`, `test_bundle_import_example_baseline_sets_selected_path`, `test_bundle_import_example_variation_sets_selected_path`. Collectively assert button presence, synthetic/Manchester copy, click→success 62+files, rerun hides card, Bundle Import shortcuts wiring.

`uv run pytest ... -q` → `17 passed` (10+7). Tests are behaviour-anchored (file existence, message content, metric semantics) not just implementation probes.

**Verdict on F-2: RESOLVED.**

#### F-3 — `inspect_demo_workspace` dead code (MEDIUM)

Not deleted — intentionally retained as public surface. Now **covered** by two tests (`test_inspect_reports_ready_for_existing`, `test_inspect_reports_failed_for_missing`) proving the contract, and grep shows `src/.../demo_workspace_service.py:45` is still definition-only (no in-`src/` caller beyond tests). The original review allowed "documented; not required to delete if unused but noted." Keeping it with tests satisfies that allowance; future wiring can adopt it without churn. No dead-code warning from ruff/mypy.

**Verdict on F-3: RESOLVED (retained with test coverage; acceptable per task note).**

#### F-4 — `workspace_status` deduplication via helpers (MEDIUM)

Original: 3 scattered `workspace_status(config.workspace_path)` calls in `_render_v07_home` plus one in legacy home. Now: `_render_v07_home` has zero direct `workspace_status` calls — all go through `_resolve_effective_demo_paths` (validity check for env + session), `_comparison_count_for`, and `_workspace_presence`. Grep confirms `home.py` has `workspace_status` on lines 195, 204 (inside `_resolve...`), 229 (inside `_comparison_count_for`), 242 (inside `_workspace_presence`), plus line 358 (legacy) and the import. The helper `has_workspace, workspace_ready, _ws_status = _workspace_presence(effective_workspace)` replaces the inline try/except block; `comparison_count` and `workspace` derive from the same effective value; `list_workspace_reports(effective_workspace)` reuses it. The helpers reuse a single validity-checked workspace rather than re-querying `config.workspace_path` three times with divergent error handling. Residual extra query inside `_resolve...` (env check + session re-check) is justified — it is the session-fallback validity gate, not duplication of the KPI path.

**Verdict on F-4: RESOLVED.**

#### F-5 — `docs/demo_quickstart.md` wording for Option A/B (MEDIUM)

Fixed. Step 1 now reads:

> **Home** — after in-browser creation the page reads the session workspace and shows `Visible local layers: 0` … `Registered runs: 62`, `Comparisons: 3` without requiring a process restart; the same counts are shown immediately by `traffictwin demo launch .traffictwin-demo` (which sets `TRAFFICTWIN_WORKSPACE_PATH`). Verify counts directly: `uv run traffictwin demo status .traffictwin-demo` (expect `valid_workspace True, 62/3`). The empty Manchester card correctly states that missing observations are not filled…

This matches the code (Home reads session; verify via CLI status) and no longer overpromises. The "Verify counts directly" line was added exactly as the task's doc fix intended. The Option A vs B distinction is explicit and the stale "after creation shows" is now qualified with "reads the session workspace".

**Verdict on F-5: RESOLVED.**

#### F-6 — `_active_demo_workspace_path` now read (MEDIUM)

Original: write-only at `home.py:222-223`. Now read in two places: `home.py:188` via `_resolve_effective_demo_paths` and `guided_demo.py:158` via `_render_track_status`. Grep: `home.py:188 get`, `home.py:281 set`, `guided_demo.py:158 get`. The session key propagates to `load_project_status`, `load_local_manchester_scene`, and `list_workspace_reports` (Home) and to the evidence-context banner (Guided Demo). No longer write-only.

**Verdict on F-6: RESOLVED.**

#### F-7 — Dead literal removed (LOW)

`DemoWorkspaceReason` at `src/traffictwin/ui/demo_workspace_service.py:20` no longer contains `"already_has_workspace"` — now exactly `ready | created | already_exists | invalid_path | unsafe_path | non_empty_without_force | unexpected_error` (6 non-error + 1 catch-all). Grep for `already_has_workspace` is clean; grep for `DemoWorkspaceReason` shows only the single type alias and the `reason:` field. Ruff/mypy unaffected.

**Verdict on F-7: RESOLVED.**

### Residual issues (none blocking)

| ID | Severity | Note |
|---|---|---|
| R-1 | **LOW** | Guided Demo invalid-env fallback not mirrored. `guided_demo.py:157-165` only checks `config.workspace_path is None` before consulting session; `home.py:193-198` additionally demotes an invalid (non-`None` but `valid_workspace==False`) env workspace to `None` first. With `TRAFFICTWIN_WORKSPACE_PATH` pointing at an invalid workspace (as in this machine's E1 harness), Guided Demo still shows `Unavailable | 0/0/0` after session creation, while Home shows `62/3`. Clean-checkout (`TRAFFICTWIN_WORKSPACE_PATH` unset) is unaffected. Fix: mirror Home's `valid_workspace` check in Guided Demo or extract a shared `resolve_effective_workspace(config)` helper. |
| R-2 | **NIT** | `inspect_demo_workspace` `reason="unexpected_error"` is not asserted by name in tests (only `status=="failed"`). For the non-existent and corrupt cases the probe showed `reason=="unexpected_error"` — consider adding `assert result.reason == "unexpected_error"` in the missing/corrupt tests for taxonomy completeness. |
| R-3 | **NIT** | `home.py:358` legacy home still calls `workspace_status(config.workspace_path)` directly, not via helpers. Legacy path is opt-in (`_v07_navigation_active is False`) and out of scope for v0.7, so this is expected to remain as-is. |

No new **HIGH** or **MEDIUM** residual was introduced. Privacy/non-broadening (F-8/F-9/F-10 area) was not re-flagged; the prefix guard `candidate.startswith(str(workspace))` prevents arbitrary registry honoring when workspace is valid, and synthetic/Manchester wording is unchanged.

### Original review verdict disposition

Original review (245 lines, commit `b6f7311`) issued **REQUEST_CHANGES** (no BLOCKER, but HIGH F-1 + F-2 prevented merge). Fixes in `5606a7c` address the blocking pair plus all MEDIUM/LOW findings F-3..F-7. The added gates all pass, behaviour is verified by both new tests (17 passed) and manual AppTest probes, and the only residual is a LOW Guided Demo invalid-env divergence that does not affect the documented clean-clone journey. The original documentation overclaim (F-5) is corrected and matches runtime.

**Re-review verdict: APPROVE_WITH_MINOR_FIXES** (alternative framing in task terms: **APPROVE** to merge with the noted LOW follow-up as non-blocking). The branch is **merge-ready** subject to the owner landing the one-line Guided Demo alignment (R-1) in a fast follow-up or accepting it as a tracked NIT; re-review is not required if R-1 is accepted as-is for the clean-checkout journey.

**Whether original REQUEST_CHANGES is resolved:** **YES** — the HIGH findings that justified REQUEST_CHANGES are fully resolved; the branch no longer withholds merge on those grounds. The remaining R-1 is LOW and isolated to the diss-harness polluted-env edge case.

---

*Re-reviewer: Claude (independent mandatory re-review, per delegation). E1 PID 21677 left untouched throughout. Only file written: this addendum appended to `docs/reviews/product_completion_claude_review_2026-08-08.md`.*

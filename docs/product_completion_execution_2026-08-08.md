# Product Completion Execution Record — 2026-08-08

**Parent commit:** `a462c72b81f1668eef4ea0b7f8e806be4d208b47` (origin/main)
**Branch:** `agent/product-completion-v1`
**Checkout:** `/Users/akashx/AntigravityTest/traffictwin-product`
**Evaluator active:** Yes — `eval_sumo_stage1_mc.py` (PID 21677, 367% CPU) left untouched.
**E1 isolation applied:** No full-suite run, no parallel tests, no heavy SUMO/VEC, no port 8501/8502 use.

---

## 1. Bounded Product Audit Summary

### What genuinely works (verified via source + tests)

| Surface | Evidence |
|---|---|
| CLI: `traffictwin demo initialise/launch/status`, `bundle validate/import`, `compare`, `metrics compute`, `diagnose`, `provenance`, `report`, `doctor`, `vec/*`, `registry/*`, `manchester provider template/status` | `src/traffictwin/cli.py` ~120 commands, tested in `tests/integration/` |
| Streamlit: 34 normative + 10 additive pages, grouped navigation (`st.navigation` 7 normative + Platform groups), thin service wrappers | `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/app_pages/`, `src/traffictwin/ui/pages/` |
| Services & adapters: bundle validation, canonical projection, deterministic metrics, comparison, diagnostics (R0-R8), provenance, reporting, evidence-pack, streaming, cache, archive | `src/traffictwin/{ingestion,metrics,diagnostics,provenance,reporting,synthetic}` |
| Manchester backends: DfT/WebTRIS/TfGM/BODS/operational acquisition, quarantine/promotion, replay, map-layer, freshness, spatial admission, survey-view | `src/traffictwin/integration/manchester/` (60 modules) |
| Demo workspace: deterministic synthetic bundles, registry, exports, comparisons | `src/traffictwin/demo/workspace.py`, tested in `tests/unit/test_demo_workspace.py` |
| Manchester Operations page: historical/latest/live-vehicle modes, source-separated overlays, bounded live fetch, stale fallback | `src/traffictwin/ui/pages/manchester_operations.py` |
| Guided Demo, Source Health, Match Review, Reports, Compare, Import | Implemented with action-aware progress and refusal states |
| Deterministic metrics/diagnostics/provenance: pure functions, no LLM metric calculation | `src/traffictwin/metrics/`, `src/traffictwin/diagnostics/` |

### What is rehearsed but not yet accepted

All `MAN-01`–`MAN-11`, `UX-01`–`UX-03`, `REL-01` remain `planned` per `implementation-status.md`.
Platform slices (inventory, forecasts, composer, analytics-quality, evidence-matrix,
observatory, decision-safety, XAI audit) are `working_bounded` but lack participant
or authority evidence. This matches the design's external/scientific blockers.

---

## 2. Gap Matrix — Major User Journeys

Each journey is scored against the P0 target in the task statement.

| # | User goal | Current route / CLI | Implementation state | Code & test evidence | What works now | Exact missing connection | Blocker | Possible now? | Priority | Selected action |
|---|---|---|---|---|---|---|---:|---|---|---|
| 1 | **Start product locally with one documented command from a clean checkout** | `streamlit run src/traffictwin/ui/app.py` (bare) vs `traffictwin demo launch .demo` (two-step) | Partially working | `src/traffictwin/demo/launcher.py:launch_workspace` auto-initialises if marker absent; `src/traffictwin/ui/app.py` does NOT auto-create when `TRAFFICTWIN_WORKSPACE_PATH` is unset; `README.md` docs both paths but the bare `streamlit run` leaves `workspace_path=None` | `demo launch` is one-command when a path is given; bare `streamlit run` loads fixtures only via `tests/fixtures` | A fresh user running plain `streamlit run src/traffictwin/ui/app.py` lands with no workspace, zero guidance on how to create one, and no in-UI one-click creation; home shows "No accepted Manchester scene" generically without telling the user to run `demo launch` or initialise | CODE | Yes | **P0-1 HIGH** | **SELECTED — vertical slice** |
| 2 | Understand available evidence & provenance at a glance (MAP-LED home) | Home (`app_pages/home.py` via `pages/home.py`) | `working_bounded` | `pages/home.py:_render_v07_home` shows evidence-state badge, layer count, run/comparison counts, pydeck map when scene exists; empty state is static text | Map/freshness display works when a v0.7 workspace with scenes exists; provenance copy is accurate | For demo/synthetic workspaces (no Manchester scenes) the empty Manchester card is confusing: it says "No accepted Manchester scene" but offers no action; no distinction shown between "demo synthetic" vs "real workspace empty"; no call-to-action to Guided Demo when empty | CODE | Yes | **P0-2 HIGH** | Part of selected slice |
| 3 | Select supported historical/latest/live-vehicle or demo context with correct truth labels | Manchester Operations (`pages/manchester_operations.py`) + `manchester_operations.py` helpers | `working_bounded` | Three modes, freshness service, source-separated layers, staged unavailable states | Mode selector, evidence-state badges, stale/unavailable/synthetic separation correct | Live-vehicle mode's "one controlled BODS request" form is discoverable only after mode switch; no top-level affordance from Home to create a live scene; historical/live states correctly separated in code but gap 1 makes the happy path unreachable without CLI | CODE | Yes | **P0-3 MEDIUM** | Follow-on slice |
| 4 | Inspect map & source provenance ( titres, attribution, snapshot ids ) | Manchester Operations + map-layer service | `working_bounded` | `map_layers.py`, `boundary_reference.py`, `manchester_operations.py` renders `TextLayer` over ONS polygons, source cards show snapshot/licence/attribution | Map renders admitted WGS84 points, ONS boundaries display-only, no basemap requests | Correct but only reachable after workspace setup (blocked by 1); no demo-scene or synthetic map to give new users any visual payoff | CODE (small) | Yes | Part of selected slice (guidance) |
| 5 | Import or select an accepted example without private data | Bundle Import (`pages/bundle_import.py`), fixtures at `tests/fixtures/bundles/{baseline,variation}_valid` | Implemented | `ui/services.py:validate_bundle_for_ui`, `safe_import_bundle_for_ui`; fixtures committed, used in home's session default `selected_bundle_path` | Validation/import works when bundle exists; import-first remains unconditional | Page uses only `st.text_input` for paths; no file-uploader, no one-click "open example" button; fresh user must type path correctly; no first-run guidance component (`first_run_guidance`) wired on this page | CODE | Yes | **P0-5 MEDIUM** | Part of selected slice |
| 6 | Inspect deterministic metrics & diagnostics | Run Overview, Evidence Readiness, Diagnostics | Implemented | `pages/run_overview.py`, `pages/evidence_readiness.py`, `src/traffictwin/metrics/`, `src/traffictwin/diagnostics/` | Metrics computed deterministically, diagnostics R0-R8 rendered with thresholds, first-run guidance on `run_overview` | Good — minor polish only: metrics correctly show unavailable states, no LLM calculation path | CODE | No change needed | — |
| 7 | Compare compatible runs/scenarios | What-if Compare (`pages/compare.py`) | Implemented | `pages/compare.py:compare_runs_for_ui`, `tests/integration/test_ui_demo_flow.py` | Deterministic deltas, provenance, completeness exports, compatibility badge | Usable when two bundles exist; needs workspace/bundles from gap 1; first-run guidance present on this page | CODE | Already wired | — |
| 8 | Export a report/evidence artifact | Reports (`pages/reports.py`) | Implemented | `pages/reports.py`, `reporting/builder.py`; `list_workspace_reports` | Inventory, regenerate (run/compare/diagnostics/full), download, annotations | Requires workspace (gap 1); otherwise functional | CODE | Already wired | — |
| 9 | Understand exactly what remains unavailable | Every page + implementation-status + open-questions | Pattern applied unevenly | `components/unavailable.py`, `components/badges.py`, `labels.py:REQUIRED_PROTOTYPE_NOTICE` | Each Manchester source correctly shows unavailable/stale/historical with reason codes; VEC/Randy correctly unavailable | Home's generic "No accepted Manchester scene" is not specific enough (doesn't name which sources or that demo workspaces never have them); not all gaps point to `open-questions` or `implementation-status` | CODE | Yes | Part of selected slice |
| 10 | End-to-end journey survives navigation without losing context | Cross-page state (`ui/state.py`), navigation (`navigation_v07.py`) | `working_bounded` | `tests/ui/test_cross_page_state.py` proves `selected_bundle_path` and evidence-pack survive group switches; guided_runtime consumes pending pages | Bundle selection and evidence-pack survive navigation; legacy + v07 routers both tested | Works; no gap | — | — | — |
| 11 | One-click creation of a safe demo workspace inside the product | — none — CLI only (`traffictwin demo launch .demo`) | Missing | `demo/launcher.py` exists but is CLI-only; `demo/workspace.py:initialise_workspace` is never called from Streamlit | No UI path exists | Fresh user must leave browser, run terminal command, know env vars | CODE | Yes | **P0-1 (same as #1)** |
| 12 | Reports/bundles discoverable without memorised paths | Bundle Import text inputs default to fixtures; no file picker | Partial | `bundle_import.py` | Deterministic validation/import | No upload affordance beyond batch path; but fixtures are sufficient for demo per design (import-first) | CODE | Medium | Deferred |
| 13 | Scenario comparison via map & task-oriented navigation | Navigation groups, scenarios, operations | Working but broad | 44 pages across 8 groups | Navigation render, grouped sidebar | New user must guess which group answers their question; gap 1 dominates | CODE | Yes | Guidance fixes |

---
## 3. Scope Labels

Blocker types per task spec:

* **CODE** — fixable in this branch without external decision.
* **HUMAN_DECISION** — requires 174 named-person Manchester map-review row decisions.
* **SCIENTIFIC_DECISION** — calibration objective/bounds/uncertainty/held-out design, observed-vs-simulated comparison contract approval, viable demand replacement.
* **PROVIDER** — BODS/National Highways/TfGM/NTIS terms, credentials, rate limits, `BNVB`, retention scope.
* **LICENCE_OR_PRIVACY** — BODS retention/publication, identifier erasure, package redistribution limits.
* **DEPENDENCY** — external `osmium`, `netconvert`, `SUMO 1.27.x` runtime (already pinned).
* **RELEASE** — tag, package, workspace-migration acceptance.

Only **CODE** rows are selected below.

---

## 4. Ranking — Top Five Unblocked CODE Gaps

All are CODE, all are demo-ready, all use existing deterministic services.

| Rank | Gap | Why it outranks others | Effort | Risk |
|---|---|---|---|---|
| **1** | **Clean-workspace, demo-ready vertical journey: one-click demo-workspace creation + Home empty-state guidance + in-UI quick-start** | Unlocks the entire P0 chain; without it every other page is unreachable for a fresh checkout user who starts via `streamlit run`; uses only tested `initialise_workspace`/`workspace_status`; no provider or scientific input; demo-boundary stays explicit | Small–Medium (one service wrapper, two page edits, one doc) | Low |
| 2 | Bundle Import: add one-click "Open example baseline/variation" + first-run guidance | Removes path-typing hurdle; imports are already import-first but friction is high | Small | Low |
| 3 | Home: empty-demo workspace gets honest synthetic context instead of misleading "No Manchester scene" | Fixes false impression that demo workspace is broken; truthful empty vs synthetic distinction | Small | Low (copy only) |
| 4 | Manchester Operations: make the bounded live-bus request reachable after guided steps | Improves discoverability of already-built live workflow | Small | Low |
| 5 | Reports/Compare discoverability from Home when workspace just created | Shortens path to export; wiring exists but CTA missing | Small | Low |

Other CODE polish (file-uploader vs path input, upload streaming) is lower priority than
closing the end-to-end loop.

---

## 5. Selected Vertical Slice — "Clean-workspace, demo-ready vertical journey"

### Why this slice

* Direct default from the task spec, confirmed by audit: the default P0 journey is **not yet complete**.
* Highest-value unblocked gap; it makes the product usable from `git clone` without reading `v07_usage.md`.
* Uses only committed fixtures/accepted cached artifacts/clearly labelled synthetic examples.
* Preserves import-first operation, deterministic metrics, evidence-state distinctions, and privacy.
* Does not require provider credentials, supervisor decisions, scientific choices, or E1 outputs.
* Completable cleanly in one PR; reduces manual repository-level steps from ~4 commands to essentially
  one browser session.
* Reduces support load for MSc viva demo day.

### Preferred user story after slice

A fresh user should be able to:

1. `uv sync` (or `pip install -e ".[dev]"`) then `streamlit run src/traffictwin/ui/app.py` (or `traffictwin demo launch .demo`);
2. land on Home, which now **recognises** an empty/clean workspace and offers a single
   **"Create demo workspace"** action that initialises a deterministic synthetic workspace under
   a safe directory and wires session/registry in-place;
3. see immediately that the workspace is synthetic, how many scenarios/runs/comparisons it contains,
   and exactly which evidence is and is not present (Manchester layers remain unavailable in demo);
4. press **Explore Manchester** or **Start Guided Demo** and stay on a coherent path where bundle
   selection, comparison, diagnostics, and provenance all navigate without losing state;
5. open a committed fixture or demo bundle with one click instead of memorising a path;
6. compare compatible runs deterministically;
7. export a report/evidence artifact; and
8. understand, from visible copy on every relevant page, what remains unavailable and why.

### Non-goals for this slice

* No provider credential flow; no live Manchester acquisition is started or claimed.
* No map-matching, temporal-profile, calibration, or baseline acceptance claim.
* No change to `MAN-*`/`UX-*`/`REL-01` formal status — working is not accepted.
* No in-browser filesystem mutation beyond the demo workspace directory the user explicitly confirms.
* No background scheduler/sync worker is started.

### Acceptance contract (what must be true for the slice to be accepted)

**Functional:**

* AC-F1 — A clean workspace (no `TRAFFICTWIN_WORKSPACE_PATH` env and no existing default workspace
  directory) shows on Home a focused empty-state card with a single primary **Create demo workspace**
  button. Pressing it initialises a deterministic synthetic workspace, sets `active_registry_path`,
  `selected_bundle_path`, `selected_baseline_run`, `selected_variation_run`, and displays success
  with scenario/run/comparison counts. Pressing again when a workspace is ready is a safe no-op
  with a clear message.
* AC-F2 — After creation, Home's "Current evidence context" honestly reads
  `SYNTHETIC · OFFLINE · IMPORT-FIRST` and states that Manchester sources remain unavailable in demo.
  The map area either shows an empty-state with honest synthetic copy (no Manchester basemap claim) or
  the existing "No accepted Manchester scene — expected in demo" wording. It never presents buses as
  traffic or fabricates coverage.
* AC-F3 — Bundle Import offers a one-click **Open example baseline** / **Open example variation**
  action that selects the committed fixture without requiring the user to type a path, plus the
  existing text input for arbitrary paths. The selection propagates to Compare and Run Overview via
  cross-page session state (already tested). When a custom path does not exist it shows the existing
  error.
* AC-F4 — Guided Demo's standalone track is reachable from Home in one click and the first stage
  (plan) works against the freshly created demo workspace (seeds pre-registered).
* AC-F5 — Compare deterministically validates compatibility and renders deltas; no quality or causal
  badge is inferred.
* AC-F6 — Reports inventory lists demo reports and the Download action succeeds.
* AC-F7 — All synthetic sources carry `SYNTHETIC`/`DETERMINISTIC`/`OFFLINE` badges; Manchester
  evidence-state badges remain distinct (`historical`, `near_live`, `live_vehicle`, `stale`,
  `unavailable`, `synthetic`).

**Documentation & safety:**

* AC-D1 — A single concise quick-start (`docs/demo_quickstart.md` or equivalent) records the
  one-command launch and the in-UI creation path, distinguishes demo vs real workspace, and points
  to `v07_usage.md` / `implementation-status.md` for Manchester/real-workspace activation. No
  credential or private path is documented.
* AC-R1 — Two focused tests: (a) unit test for the thin demo-workspace service wrapper proving
  deterministic initialisation, refusal on non-empty path, and idempotency; (b) AppTest covering
  Home empty-state → button → success → metrics rendered, plus Bundle Import one-click wiring.
* AC-V1 — `ruff format --check`, `ruff check`, focused `mypy` over changed files, focused unit+UI
  tests, and `git diff --check` pass. Under E1 isolation: no full-suite, no parallel.

### Implementation sketch

1. Thin service `src/traffictwin/ui/demo_workspace_service.py` (or reuse `demo/workspace.py`) exposing
   `demo_workspace_path_for_home` / `ensure_demo_workspace_for_ui` that validates the target path,
   calls `initialise_workspace`, reconciles session keys, and returns a typed result with blockers.
2. Home (`src/traffictwin/ui/pages/home.py`): add empty-state branch that calls the service and
   renders honest synthetic empty copy; wire button with `width="stretch"` and primary type.
3. Bundle Import (`src/traffictwin/ui/pages/bundle_import.py`): add two small buttons that set
   `selected_bundle_path` / baseline / variation to fixture paths.
4. One new page or card? No — keep `pages/home.py` thin; use existing navigation helper
   `navigation_button` where a page jump is needed.
5. One concise doc (`docs/demo_quickstart.md`).
6. Two tests under `tests/unit/ui` and `tests/ui`.

### Exact human/provider/scientific blockers (not bypassed by this slice)

* `H-B1` 174 named-person Manchester map-review decisions (deferred, correctly blocks `MAN-09`).
* `H-B2` Manual accessibility and participant-study acceptance (`UX-03`/`REL-01`).
* `S-B1` Calibration objective, parameter bounds, uncertainty and held-out design (blocks `MAN-09` calibration).
* `S-B2` Observed-versus-simulated comparison contract production registration (`MAN-10`).
* `S-B3` Viable demand replacement for the gridlocking route pool (`MAN-09`).
* `P-B1` BODS retention/publication/budget decisions, `BNVB`/Bee scope completeness, city-road coverage inference (blocks `MAN-05` full acceptance).
* `P-B2` National Highways licence/publication/reconciliation breadth beyond the 3-product 24-Jul-2026 run (blocks `MAN-01`/`MAN-08` acceptance).
* `P-B3` TfGM/NTIS SCOOT/UTC/UTMC/counter and NTIS measured-traffic provider response/schema/terms for `NEXT-08` (blocks `NEXT-08`).
* `R-B1` Release/licence/publication/tag decisions and real-workspace migration authority (`REL-01`).

These blockers remain open and the slice must point to them instead of coding around them.

### What was already working (before slice)

* Deterministic synthetic generation, bundle validation, metrics, comparison, diagnostics, provenance,
  reporting, streaming/batch ingestion work when a workspace exists.
* Home, Guided Demo, Manchester Operations, Source Health, Match Review, Reports, Compare all render
  correctly when a workspace is wired via `TRAFFICTWIN_WORKSPACE_PATH` / `traffictwin demo launch`.
* Bundle selection state survives navigation (tested).
* Manchester evidence states are correctly separated; unavailable blockers are explicit.

### Gap implemented by slice

The missing **service-to-page wiring for clean-workspace bootstrapping and honest demo empty-state
presentation**, plus the smallest discoverability fix on Bundle Import. Everything else remains.

### Risk & rollback

* Change is additive and behind an empty-state branch; existing workspaces are untouched.
* The service reuses the tested `initialise_workspace` boundary; no new filesystem or security surface.
* Session mutation is limited to the same keys Home already writes (`active_registry_path`,
  `selected_*_run`). No new session contract beyond demo-path recording.
* Reverting is a single commit: drop the service module, revert two page edits, revert doc, revert tests.

---

## 6. Next Recommended Slices (after this one)

1. Manchester Operations empty-state preview: render the ONS Manchester/Greater Manchester boundaries
   as a static empty map even when no source scene exists, so new users get a geographic payoff without
   fabricating evidence. (CODE, small)
2. Reports-first demo: pre-compute one more comparison artifact into the demo workspace and surface
   its Download from Home for a sub-minute demo. (CODE, small)
3. Bundle Import file-uploader alternative to text input for local teaching labs. (CODE, medium)
4. Real-workspace affordance: a read-only "Connect existing v0.7 workspace" inspector on Home that
   never guesses private paths. (CODE, medium)
5. Human-decision: obtain reviewer identity and decide the 174 map-review rows with the sealed ledger
   (`MAN-09` / Gate D). (HUMAN_DECISION, owner decides)

---

## 7. Evidence-State Boundaries Honoured

* `historical` / `near_live` / `live_vehicle` / `stale` / `unavailable` / `synthetic` remain mutually
  explicit and source-specific. This slice does not collapse them into "live".
* BODS positions remain `LiveTransitVehicleObservation`, never `TrafficObservationRecord`; no private-vehicle flow is inferred.
* National Highways operational overlays remain `near_live`/`stale`, never `live_vehicle`.
* TfGM signals remain infrastructure, never signal state/queue.
* All demo data self-identifies as `SYNTHETIC` / `DETERMINISTIC` / mock in manifest, badge, and caption.

---

## 8. E1 Isolation Statement

* The evaluator at PID 21677 was active when the product audit began (confirmed via `pgrep`/`ps`).
* No experiment worktree (`/Users/akashx/AntigravityTest/diss`) was modified.
* No branch, PR #8, output root (`e1_outputs`/`colab_inputs`), or external repository was touched.
* This record was written only to the product checkout.

---

*Prepared by the product-completion agent. Implementation of the selected slice follows.*

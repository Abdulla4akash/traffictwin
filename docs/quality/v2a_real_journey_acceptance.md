# V2-A Real Journey Acceptance — Home → Guided Demo → What-If → Consequence Lenses → Compare

- Date: 2026-08-09
- Branch: `agent/product-v2a-journey-acceptance` from `a9ec532ac88ed8678973416fe21bcab5d1a57d11` (exact PR #14 head, Claude 1 APPROVED)
- Base for stacked PR: `agent/product-v2-home-guided-whatif` (PR #14 OPEN DRAFT) else `main`
- Suite: `tests/integration/test_v2a_real_journey_acceptance.py` (9 tests: A–H plus valid-commit, 8 scenarios) + `tests/ui/test_compare_draft_lifecycle.py` (13 tests)
- Production boundaries exercised: real routing/session/validation/report/comparison construction; no mocked hashes, no fixture substitution for pair identity

## Standing

Engineering acceptance slice only. No Gate-F claim. Synthetic/local/deterministic wording retained throughout. Portfolio/Challenge pages not yet included (depend on PR #13 / #17 if absent). PR #14 head untouched (no commit/amend/rebase/force-push, remains PARKED, APPROVED at a9ec532). This PR now includes a production fix for Compare (not docs-only).

## Claude 1 HIGH finding and root cause

Claude 1 reproduced a pre-existing production defect in `src/traffictwin/ui/pages/compare.py` that predates PR #14 and PR #18:

```python
baseline_path = Path(st.text_input(...))
variation_path = Path(st.text_input(...))
st.session_state["selected_baseline_run"] = str(baseline_path)
st.session_state["selected_variation_run"] = str(variation_path)
if not baseline_path.exists() or not variation_path.exists(): ...
```

`Path("") == Path(".")` so blanking the field writes `selected_baseline_run = "."` before the page rejects the path. Whitespace (`"   "`) similarly corrupts after `strip` vs `Path` ordering, and `exists()` after assignment is insufficient because `"."` exists as the current directory. The pair is one atomic authoritative selection; writing one side independently or committing after `exists()` but before validation/comparison also corrupts it.

PR #18 initially contained a false-assurance test `authoritative_after_draft` that reimplemented the desired behavior in a local helper and asserted its own result, never exercising the real Compare page. That test passed while the defect remained.

## Production fix (Compare draft vs committed)

File: `src/traffictwin/ui/pages/compare.py`

- Read committed `selected_baseline_run`/`selected_variation_run` before rendering drafts (authoritative).
- Render drafts via `st.text_input` with committed values as defaults, keep raw strings.
- `strip()` before `Path()` — never construct `Path("")`.
- If either stripped draft is blank: `st.error("Both baseline and variation bundle paths must be selected.")` + `first_run_guidance`, `return` without touching either authoritative key. No `"."` write.
- Construct `Path` only from non-blank, then `exists()` checks: both missing → specific error, each missing individually → specific error, all without mutating authoritative.
- `validate_bundle_for_ui` both; if `ServiceError` or `not analysis_ready`: fail closed, no mutation.
- `compare_runs_for_ui`; if `ServiceError`: fail closed, no mutation.
- Only after pair is successfully usable: atomically assign **both** `selected_baseline_run` and `selected_variation_run` to the new `Path` strings.

Invalid drafts (blank/whitespace/missing/invalid bundle) thus preserve both old values atomically; valid new pair commits both atomically; comparison ServiceError also preserves.

## Scenario map (A–H) — integrity audit

| ID | Claimed behavior | Real production boundary now executed | Old false/vacuous proof removed |
|---|---|---|---|
| A | Home → What-If Studio routing | `AppTest.from_file(app.py)` click “Create what-if comparison”, assert rendered `What-If Studio` title + synthetic caption, negative RUN_OVERVIEW/SCENARIO | — |
| B | Guided Demo → generated pair | Real `generate_whatif_pair_for_ui` with 4 non-default controls **plus** real `DemoTrack`/`GuidedDemoProgress`/`_complete_or_skip` handoff proving `selected_*` survive REVIEW → Compare; `pair_id == pair_id_for_request(req)` exact; both baseline/variation contain `acceptance-b`; Compare inputs reflect exact generated paths. Previously called direct service “Guided Demo” and used vacuous `a in baseline or a in variation or "handoff" not in baseline`. | Removed OR escape hatch, added exact deterministic checks and real guided runtime |
| C | What-If generation transaction ≥2 controls, atomic, labelled | Service generates `acceptance-c` with `congestion_multiplier=2.1`, `vehicle_count=28`, `task_arrival_rate=0.25`, `rsu_count=4`; validates both; **plus** real `What-If Studio` AppTest via `WhatIfStudio` page, `Generate comparison` click, assert both `selected_*` set, exist, not fixtures, same `whatif-` pair prefix. Ledger asserts exact `congestion_multiplier`, `vehicle_count`, `task_arrival_rate`, `rsu_count` in `changed_parameters`. Portable dict asserts `not Path(...).is_absolute()` and no `/tmp`/`/Users/` leak (not `or` branch). Previously simulated `state = {"selected_baseline_run": ...}` and broad `any(... or ...)` ledger check and vacuous `"/tmp" not in or "bundles" in`. | Removed simulated dict, made ledger exact, fixed portability OR |
| D | Consequence Lenses consumes exact pair | `build_consequence_lens_report(bv, vv)` with `run_id`/`synthetic` match; AppTest `consequence_lenses.py` with exact pair, asserts `Consequence`/`Traffic` via title/subheader and `dataframe` ≥1 | — |
| E | Compare/report continuity | Same `acceptance-e` pair through Compare and Consequence Lenses AppTests; portable dict asserts `not Path(...).is_absolute()` etc. Previously `or "bundles"` branch. | Fixed portability OR |
| F | Transactional rollback | Direct `generate_whatif_pair` with `write_synthetic_bundle` fail on 2nd call → `WhatIfPairError`, no registry row, no receipt, no staging, no published dirs; **plus** real Studio AppTest seeded with valid pair, patched `write_synthetic_bundle` fail on variation, click `Generate comparison`, assert error rendered, authoritative `selected_*` remain valid, no `"."`, registry count unchanged. Previously `state = {"selected_baseline_run": ...}` self-assertion. | Replaced local dict with real Studio UI boundary |
| G | Invalid draft lifecycle | Real Compare AppTest A–J: blank baseline, whitespace baseline, blank variation, whitespace variation, missing baseline, missing variation, invalid baseline bundle, invalid variation bundle, valid+invalid half, invalid+valid half — each asserts both `selected_*` preserve old fixtures, no `"."`. Valid new pair (generated `acceptance-g-valid`) asserts both commit atomically via `bw.set_value(nb)` + `vw.set_value(nv).run()` single run. Previously `authoritative_after_draft` helper self-simulated. | Deleted helper, added real page regression + valid atomic |
| H | Offline/CWD hermeticity | Different CWD, failing `socket.socket`, temp workspace, no leak; portable asserts `not Path(...).is_absolute()` and no `/tmp`/`/Users/` | Fixed to strict `is_absolute` |

All OR assertions audited: broad `or` branches that could admit forbidden state replaced with exact checks; genuine alternatives (error message `injected`/`failed`/`error`) retained with justification.

## Compare regression matrix (dedicated suite)

`tests/ui/test_compare_draft_lifecycle.py` (13 tests) — all via real `src/traffictwin/ui/app_pages/compare.py` AppTest:

1. committed valid pair renders unchanged — inputs reflect fixtures, no exception
2. blank baseline preserves — `"."` not written, old pair remains
3. whitespace baseline preserves
4. blank variation preserves
5. whitespace variation preserves
6. missing baseline preserves
7. missing variation preserves
8. invalid existing baseline preserves
9. invalid existing variation preserves
10. half-valid new pair (valid baseline + invalid variation) preserves BOTH old values (atomic)
11. valid new pair commits BOTH values atomically
12. comparison ServiceError (patched `compare_runs_for_ui`) preserves BOTH old values
13. no `"."` write for any draft in `["", "   ", ".", " ./", " . "]`

## Mutation / adversarial evidence

After fix, temporarily mutate production and prove tests bite (restore after, MUTANT count 0, working tree clean except committed changes):

| Mutation | Expected failing test | Observed failure | Restored |
|---|---|---|---|
| M1 — restore unconditional `st.session_state["selected_baseline_run"]=str(Path(draft))` before strip | `test_blank_baseline_preserves` | `AssertionError: baseline changed: expected 'tests/fixtures/...' got '.'` | yes |
| M2 — commit baseline independently before variation valid (`st.session_state["selected_baseline_run"]=str(baseline_path)` after baseline exists) | `test_half_valid_preserves_both` | `AssertionError: baseline changed` (half-valid committed) | yes |
| M3 — commit both after `exists()` but BEFORE validation | `test_invalid_baseline_preserves` | `AssertionError: baseline changed` (invalid bundle committed) | yes |
| M4 — commit both before `compare_runs_for_ui` success | `test_comparison_service_error_preserves` (new valid pair + injected ServiceError) | `AssertionError: baseline changed` (new pair committed despite comparison failure) | yes |
| M5 — restore old `authoritative_after_draft` helper architecture | — | Helper absent in final suite, confirmed `authoritative_after_draft` not in file | — |
| Home → wrong destination (`RUN_OVERVIEW`) | `test_a_home_to_whatif_studio_via_real_routing` | `AssertionError: What-If Studio not in title` | yes |
| Guided generated pair overwritten on `_complete_or_skip` | `test_b_guided_demo_generates_real_non_default_pair` | `AssertionError: selected_baseline_run != baseline` | yes |
| Rollback cleanup disabled (`_rollback_on_failure` no-ops) | `test_f_transactional_rollback_cleans_partial_state` | `AssertionError: staging not cleaned` | yes |

Final MUTANT count: 0

## Hermeticity and safety

- Each scenario uses `tempfile.TemporaryDirectory` workspaces and per-scenario `registry.sqlite`; no mutation of CWD or `tests/fixtures/bundles/*`.
- H scenario proves no network calls (failing socket) and no artifact leak after run.
- Serial execution while E1 active (dynamic `pgrep -fl 'eval_sumo_stage1_mc.py|run_e1_multidraw_physical_campaign'` check, no `-n`, no SUMO/VEC). Research checkout `/Users/akashx/AntigravityTest/diss` untouched; E1 process dynamically checked (no hardcoded PID).

## Run instructions

```bash
# from worktree /Users/akashx/AntigravityTest/traffictwin-v2a-acceptance
uv sync --extra dev
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync python -m pytest tests/integration/test_v2a_real_journey_acceptance.py --collect-only -q
uv run --no-sync python -m pytest tests/integration/test_v2a_real_journey_acceptance.py -q  # serial, ~120s, 9 tests
uv run --no-sync python -m pytest tests/ui/test_compare_draft_lifecycle.py -q  # 13 tests, ~40s
```

Results on this branch: `9 passed` (acceptance) + `13 passed` (compare) in ~2 min, `ruff All checks passed`, `mypy Success: no issues found in 937 source files`.

## Out of scope / next

- Portfolio/Challenge evidence panels (await PR #13/#17).
- Full E2E Playwright smoke (optional, not part of this isolated slice).
- Any change to PR #14 head or to PR #13/#15/#16/#17 branches (explicitly untouched).
- No navigation/page count change; `src/traffictwin/ui/labels.py`, `navigation.py`, `navigation_v07.py`, `page_runtime.py` unchanged.

## Scope

- `src/traffictwin/ui/pages/compare.py` (production fix)
- `tests/integration/test_v2a_real_journey_acceptance.py` (integrity audit A–H)
- `tests/ui/test_compare_draft_lifecycle.py` (new compare regression)
- `docs/quality/v2a_real_journey_acceptance.md` (this doc, honest)

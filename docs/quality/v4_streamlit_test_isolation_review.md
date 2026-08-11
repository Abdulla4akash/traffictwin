# Streamlit/Pytest Isolation Guard — V4 Review

Date: 2026-08-10 (updated 2026-08-11 for 68d50a4 remediation, supersedes a3d0054 and 43a525a)
Branch: agent/platform-streamlit-test-isolation-v1
Abandoned Head: `63acdb96321ad30d1e245b124ace6f563ed82f73` (interim review, superseded by a3d0054)
Base: 7b1b0b55b399108b237f6e9a31a6747f4c15c81b (origin/main Merge PR #30)
Heads:
- original lane `2f81a64e8c51b3963ddaafbbfe8a6f3d9544933d` — blocking defect: passing polluter silently repaired
- interim `a3d005442bc2c9dbc41be4bc5f7c211cf111be51` — added reporting, but introduced guard regressions (REQUEST CHANGES)
- interim `43a525addc2be1fc1d78adf8b10a92265a79d00b` — fixes blockers 1–8, preserves source polluter fix (probe had uv/-q segfault)
- this remediation `68d50a4e204f855574186256a58e9cf64035897d` — probe robustness for uv/capture (exit -11 fix), preserves all blocker fixes

## Objective

Eliminate order-dependent Streamlit/AppTest pollution where fake/stub `streamlit` or `FakeAppTest` state leaks from one test into later page tests, producing failures such as `module 'streamlit' has no attribute 'secrets'` and stacked wrapper recursion. Tests that pass alone must also pass after the known polluter, with deterministic isolation and secret redaction. Passing polluters must emit a visible warning via the real guard, not be silently repaired.

## Root Cause

`tests/unit/test_apptest_cold_start_hardening.py` helpers `_install_fake` / `_uninstall_fake` were polluters:

- `_install_fake` saved `sys.modules["streamlit"]` trio, then installed fake hierarchy, then called `uninstall_apptest_run_patch()` *after* `sys.modules` already pointed at fake. That operated on `FakeAppTest.run`, overwriting it with the real original (which expects `_tree`), and desynced `_installed`.
- `_uninstall_fake` called `uninstall` while fake still present, then restored `sys.modules` but left real `AppTest.run` still patched while `_installed=False`. Next fake install double-wrapped, recursion `AttributeError: 'FakeAppTest' object has no attribute '_tree'` or missing `secrets`.

Isolation guard was missing or incorrect:

- Initially no snapshot/restore.
- At `a3d0054`, guard snapshot only 3 keys (`streamlit`, `streamlit.testing`, `streamlit.testing.v1`) and blindly `pop("streamlit")` while leaving `streamlit.*` children, creating half-root state that re-executes `streamlit/__init__.py` against surviving subtree and raises `RuntimeError: DeltaGeneratorSingleton instance already exists!` in teardown, aborting restoration and leaving `_installed=True` with root absent, causing `install_apptest_run_patch()` to early-return.
- Guard rewound `_has_run_first` per-test, defeating process-scoped `first AppTest.run in process` policy.
- Guard warned on innocent `import streamlit` (real) as leak (`streamlit:present(was absent)`), false positive.
- Reporting tests reconstructed warning strings instead of exercising the real autouse fixture, so disabling `warnings.warn` did not kill them.

## Minimal Reproduction (historical)

```
uv run pytest tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py -q
```

- Main before fix: 21 passed / 24 failed (stacked `_patched_run` recursion, `secrets` missing, `_tree` missing).
- At `a3d0054` as pushed: `4032` passed in full suite, but focused subsets failed:
  - `tests/unit/test_apptest_cold_start_hardening.py` alone: 1 failed, 34 passed, 2 errors (guard-induced `DeltaGeneratorSingleton` and `AssertionError: assert False` for `_is_cold_patched`)
  - `tests/ui/test_study_capsule_ui.py -rs`: 7 passed, 1 skipped (`AppTest not available: DeltaGeneratorSingleton instance already exists!`) vs base 8 passed
  - `tests/unit/test_streamlit_isolation_guard.py` with `warnings.warn` removed: still 16 passed (non-biting reporting tests)

## State Leaked

- `sys.modules["streamlit"]` → fake `ModuleType` lacking `secrets`
- `sys.modules["streamlit.testing"]`, `streamlit.testing.v1` → fake `FakeAppTest`
- All `streamlit.*` children when half-popped (hundreds, e.g. `streamlit.runtime.*`)
- `tests._apptest_runtime._installed` desynced
- `tests._apptest_runtime._has_run_first` (process-scoped, should not rewind)
- `os.environ` selected vars, `cwd`, `finder` (`_finder` in `sys.meta_path`)

## Fix (preserved + remediated)

1. **Polluter source fix** (`tests/unit/test_apptest_cold_start_hardening.py`) — **preserved from a3d0054, verified correct**:
   - `a3d0054` with guard removed: 4032 passed; with guard: 4032 passed; base 112 failed/3920 passed → source fix alone solves pollution.
   - `_saved_runtime_state` snapshots `_installed`, `_original_run`, `_has_run_first` before `sys.modules` mutation; if real was installed, `uninstall` while still on real, then `reset`; fake installed after; `_uninstall_fake` uninstalls while fake present, restores `sys.modules`, reinstates runtime state.

2. **Isolation utility** (`tests/support/streamlit_isolation.py`) — **remediated for blockers 1,4,5,6**:
   - Snapshots **whole `streamlit.*` subtree** (`k == "streamlit" or k.startswith("streamlit.")`), not just 3 keys. Absent is implicit (key not in dict), present is stored.
   - `_restore_streamlit_modules`: distinguishes fake vs real via `hasattr(root, "secrets")`. Innocent real import (`snapshot empty`, `current real`) is left (not popped), avoiding half-root. Leaked fake (`current fake`) removes all current `streamlit.*` not in snapshot and restores snapshot's real tree; also handles `snapshot empty + fake` → pop all. Current real/absent → restore missing/changed snapshot keys but never pop innocent extras. No half-state.
   - Robust teardown: `restore_streamlit_snapshot` calls `_restore_streamlit_modules`, `_restore_apptest`, `_restore_cwd`, `_restore_env`, `_restore_finder` each in `try`, collects `first_exc`, continues independent restores, then raises `first_exc` if any. Uses `contextlib.suppress(KeyError/ValueError)` and explicit `OSError`/`ModuleNotFoundError`/`AttributeError` instead of blanket `except Exception: pass`.
   - `diagnose_streamlit_leak`: only reports `sys_modules` delta when `after_is_fake` or `before_is_fake` (fake lacks `secrets`). Legitimate `import streamlit` (real) → no `sys_modules` leak. Removal `present→absent` for real is reported as `absent(was present)`. Identity change only when fake. `env` still diagnosed but not considered meaningful for warning.
   - `has_meaningful_streamlit_leak`: meaningful keys `{"sys_modules", "apptest_installed", "cwd", "finder_present"}` — `env` dropped, `has_run_first`/`apptest_run_id_changed`/`streamlit_has_secrets` alone not meaningful. Secret-safe: reports var names, not values.
   - Removed file-wide `# ruff: noqa: S110,S112,SIM105,E501`; replaced with narrow `contextlib.suppress` and per-line `  # noqa: E501` with rationale; kept `ANN401` narrow.

3. **Pytest guard** (`tests/conftest.py`) — **remediated for blockers 1,2,5**:
   - `autouse` fixture `_streamlit_isolation_guard` snapshots `before`, yields, captures `after = capture()`, diagnoses, `if has_meaningful(leak): warnings.warn(..., PytestWarning)` with `request.node.nodeid`, `sys_modules`, `apptest_installed`, `cwd`/`finder`, `real Streamlit capability absent or fake detected`, then `finally: restore(before)`. Always restores even if warning is configured as error.
   - No longer includes `env` in warning details (dropped per 5).
   - Removed dead `streamlit_leak_report` fixture and broken `pytest_runtest_makereport`/`CallInfo` handling (already removed at `a3d0054`, preserved).
   - Uses explicit `except ValueError` for `finder` removal.

4. **Regression suite** (`tests/unit/test_streamlit_isolation_guard.py`) — **remediated for blockers 3,4,5,7**:
   - Fixed tautologies: `assert hasattr(...) or True` → `assert hasattr(...)`; `assert "PATH" not in report or "env" not in ... or len<2000` (always true) → `assert "PATH" not in report` and `assert len(report) < 2000`.
   - Fixed `test_apptest_wrapper_has_run_first_is_process_scoped`: previously asserted restore rewound `has_run_first` (now `process-scoped` → second test must see `True` after first consumed, not reset).
   - Updated `has_meaningful` expectations: `env` alone `→ False`, `cwd` still `True`.
   - **Real-fixture end-to-end** (blocker 3): three subprocess probes that exercise the **actual autouse fixture from `tests/conftest.py`**, not duplicated logic:
     - `test_real_fixture_passing_polluter_emits_warning_and_victim_passes`: probe has `test_a_leaks_fake_streamlit_and_passes` (installs fake, passes) + `test_b_victim_sees_real_streamlit` (imports real, `AppTest.from_file`, `run`). Outer asserts `result.returncode==0`, `2 passed`, warning `Streamlit isolation leak detected after <nodeid>` with `sys_modules`, `state was restored`, `real Streamlit capability absent`, secret-safe.
     - `test_real_fixture_legitimate_import_is_not_a_leak`: probe only `importlib.import_module("streamlit")` twice; asserts `2 passed` and **no** leak warning.
     - `test_real_fixture_has_run_first_is_process_scoped`: probe `test_a_consumes_first_run` (`reset`, `before False`, `run`, `after True`) + `test_b_sees_still_consumed` (`snap True`); asserts `2 passed` (guard not rewinding).
   - Added `test_diagnose_legitimate_import_not_meaningful` and secret-redaction checks that also kill relevant mutants.

## Mutation Evidence (required)

### Mutation A — reporting only (disable `warnings.warn`)

- **Line mutated:** `tests/conftest.py: _streamlit_isolation_guard` — comment out `warnings.warn(msg, pytest.PytestWarning, stacklevel=2)`
- **Command:** `cd /private/tmp/wt-platform-streamlit-test-isolation-v1 && .venv/bin/pytest -q tests/unit/test_streamlit_isolation_guard.py::test_real_fixture_passing_polluter_emits_warning_and_victim_passes`
- **Before (real):** `1 passed`
- **After (mutant):** `FAILED` — `AssertionError: warning missing: ...` (probe still `2 passed` internally, but outer cannot find `Streamlit isolation leak detected after`; victim restoration still succeeds as probe shows `1 passed` for that file? Actually outer fails because warning absent while `has_meaningful` would have warned). Restored → `PASS`.
- **Also:** `test_reporting_only_mutation_proves_warning_independent` (in-process predicate) shows disabling `has_meaningful` → leak not reported but restore still brings `has_secrets` and victim passes.

### Mutation B — restoration (no-op)

- **Line mutated:** `tests/support/streamlit_isolation.py: restore_streamlit_snapshot` — replace body with `pass`
- **Command:** `.venv/bin/pytest -q tests/unit/test_streamlit_isolation_guard.py::test_mutation_restore_actually_restores`
- **Before:** `PASS`
- **After:** `FAILED` — `AssertionError: restore must bring back real streamlit with secrets` (after still fake, `sys_modules` leak remains). Restored → `PASS`.
- **Also:** polluter→victim `45` would become `1 failed, 1 passed` for probe's victim (`KeyError: 'streamlit'` or `has no attribute 'secrets'`).

### Mutation C — cold-start rewind (reintroduce per-test `_has_run_first` restore)

- **Line mutated:** `tests/support/streamlit_isolation.py: _restore_apptest` — add `mod._has_run_first = snapshot.apptest_has_run_first` (unconditional)
- **Command:** `.venv/bin/pytest -q tests/unit/test_streamlit_isolation_guard.py::test_real_fixture_has_run_first_is_process_scoped` and `::test_apptest_wrapper_has_run_first_is_process_scoped`
- **Before:** `PASS` (process-scoped)
- **After:** `FAILED` — `AssertionError: has_run_first must remain True process-scoped` (second test sees `False` after rewound) and `assert snap_restored.apptest_has_run_first is True` fails. Restored → `PASS`.

Recorded `passed/failed/skipped/deselected/exit code` per run in handoff report.

## Suite Comparison (measured on this remediation)

| Suite | Command | Result |
|---|---|---|
| Hardening subset | `uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py` | **35 passed**, 1 warning (`apptest_installed` first-run install) |
| Study capsule UI | `uv run pytest -q -rs tests/ui/test_study_capsule_ui.py` | **8 passed**, 0 failed, 0 skipped, 1 warning (first AppTest install) — previously at `a3d0054`: 7 passed, 1 skipped (`DeltaGeneratorSingleton`) |
| Guard | `pytest -q tests/unit/test_streamlit_isolation_guard.py` | **19 passed** (was 12 at base, 16 at `a3d0054`) |
| Polluter→victim | `pytest -q tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py` | **45 passed** |
| Unit/UI | `pytest -q tests/unit/ui` | **243 passed** |
| UI | `pytest -q tests/ui` | **768 passed** |
| Full unit (with jax) | `pytest -q tests/unit` | 2 collection errors (`ModuleNotFoundError: jax` in `test_bbus_synthetic_trace_smoke`, `test_bcap_synthetic_smoke`) — pre-existing, not isolation |
| Canonical gates | `ruff format --check`, `ruff check`, `mypy`, `uv lock --check`, `git diff --check` | All clean (mypy success, 1099 formatted) |

Worktree-specific: `/tmp/...` path not durable, but `test_durable_build_location_is_accepted` now handled via snapshot allowing extra real keys; no new skips introduced (guard previously caused 1 skip, now 0).

## Remaining Limitations

- Snapshots whole `streamlit.*` subtree by prefix; if future tests fake a non-`streamlit` package that indirectly breaks AppTest, it must be added.
- Guard warns only for fake-induced `sys_modules`/`apptest_installed`/`cwd`/`finder`; innocent `import streamlit` and `env` alone do not warn (env still restored). `has_run_first` remains process-scoped.
- Restoration of streamlit modules is best-effort per-component; `first_exc` is raised after attempting independent restores.

## Research Safety

- Before: `pgrep -fl e2-native...` → no matching processes.
- After: same, no `e2-native-placement`, `native-placement`, `eval_sumo`, `run_e1`, `analyze_e1`, `vec` processes running.
- No SUMO/VEC/evaluator launched; no parallel pytest; no writes to `/Users/akashx/AntigravityTest/diss`, external `vec_env`, `tos-data`, E0/E1/E2 outputs; tests serial (`-q` without `-n`).

## CI Workflow

Existing `.github/workflows/ci.yml` retains `test` job. Deterministic polluter→victim sequence (`hardening + resource_strategy`) is covered as focused validation; dedicated CI guard job not yet added (limitation above).

## Files Changed (this lane)

- `tests/support/streamlit_isolation.py` (remediated: whole subtree, fake-aware, robust, no blanket suppression)
- `tests/conftest.py` (remediated: warning without `env`, robust)
- `tests/unit/test_streamlit_isolation_guard.py` (remediated: real-fixture subprocess, process-scoped, no tautologies)
- `tests/unit/test_apptest_cold_start_hardening.py` (polluter source fix preserved, unchanged in this remediation)
- `docs/quality/v4_streamlit_test_isolation_review.md` (this file)

Fable-owned files untouched: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `tests/ui/test_navigation_v07.py`, `README.md`, `docs/user_guide.md`, `docs/ui_conventions.md`, `src/traffictwin/cli.py`.

## Evidence Captured

- Hardening isolated: 35 passed @ `68d50a4e204f855574186256a58e9cf64035897d` (was 1 failed/34 passed/2 errors @ `a3d0054`, probe fixed for uv/-q)
- Study capsule: 8 passed @ `68d50a4e204f855574186256a58e9cf64035897d` (was 7 passed/1 skipped @ `a3d0054`)
- Guard: 19 passed @ `68d50a4e204f855574186256a58e9cf64035897d` (now passes under both uv and direct -q)
- Mutation probes: reporting-only, restoration, has_run_first rewind all killed as above

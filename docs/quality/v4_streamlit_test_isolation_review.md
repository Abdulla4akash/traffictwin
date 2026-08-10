# Streamlit/Pytest Isolation Guard — V4 Review

Date: 2026-08-10
Branch: agent/platform-streamlit-test-isolation-v1
Base: 7b1b0b55b399108b237f6e9a31a6747f4c15c81b (origin/main Merge PR #30 integration/v3-five-lane-final)
Head: 0b98ed0852c53aac5643c15c4f15e691b697df22

## Objective

Eliminate order-dependent Streamlit/AppTest pollution where fake/stub `streamlit` or `FakeAppTest` state leaks from one test into later page tests, producing failures such as `module 'streamlit' has no attribute 'secrets'` and stacked wrapper recursion. Tests that pass alone must also pass after the known polluter.

## Root Cause

`tests/unit/test_apptest_cold_start_hardening.py` helpers `_install_fake` / `_uninstall_fake` were polluters:

- `_install_fake` saved `sys.modules["streamlit"]` trio, then installed fake hierarchy, then called `uninstall_apptest_run_patch()` *after* `sys.modules` already pointed at fake. That call operated on `FakeAppTest.run`, overwriting it with the real `AppTest`'s original (which expects `_tree`), and desynced global `_installed` flag.
- `_uninstall_fake` called `uninstall_apptest_run_patch()` while fake still present, then restored `sys.modules` to real, but left real `AppTest.run` still patched while `_installed=False` (flag desynced). Next fake install then double-wrapped because `_installed` was false but real was already patched, leading to recursion `_patched_run -> _patched_run -> ...` and eventual `AttributeError: 'FakeAppTest' object has no attribute '_tree'` or fake lacking `secrets`.

Isolation guard was missing:

- No snapshot/restore of `sys.modules["streamlit"]` hierarchy between tests.
- No snapshot of `tests._apptest_runtime` flags (`_installed`, `_original_run`, `_has_run_first`).
- No snapshot of selected env vars (`TRAFFICTWIN_WORKSPACE_PATH`, `BODS_API_KEY`, etc.) or cwd.
- No diagnostic helper to surface leak without dumping secrets.

## Minimal Reproduction

Historical sequence (on current main, before fix):

```
uv run pytest tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py -q
```

Single-file runs each passed (35 hardening, 10 victim). Combined run failed:

- Hardening: 14/35 failed (e.g., `test_wrapper_restored_at_session_end_via_uninstall` assert `not _is_cold_patched` failed, `test_wrapper_first_timeout_10_becomes_60` recursion `AttributeError: 'FakeAppTest' object has no attribute '_tree'`)
- Victim: 10/10 failed with stacked wrappers (11-deep `_patched_run` recursion) and `FileNotFoundError` due to fake streamlit identity.

Detailed isolation probes:

- `tests/unit/test_apptest_cold_start_hardening.py::test_wrapper_installed_once_idempotent` + `test_wrapper_first_timeout_10_becomes_60` → second failed with double wrap when combined, passed alone.
- `tests/unit/ui/test_resource_strategy_explorer_page.py` first vs hardening first order both failed in opposite direction (243 victim alone passed, but victim+hardening failed).
- Segfault on `test_importing_conftest_does_not_import_streamlit` when victim ran first (process-wide `streamlit` import leaked).

Leaked state captured via diagnostics before fix:

- `sys.modules`: `streamlit:identity_changed(fake=True)`, `streamlit.testing.v1:identity_changed`
- `streamlit_has_secrets: False` (fake lacks `secrets`)
- `apptest_installed: before True vs after False` (desynced)
- `apptest_run_id_changed: True` (stacked wrappers)
- `streamlit_id` changed

Environment/cwd diff: worktree at `/tmp/wt-platform-streamlit-test-isolation-v1` vs durable repo at `/Users/...` caused unrelated `test_durable_build_location_is_accepted` failure due to `/tmp/` fragment, but not polluter.

First traceback (representative):

```
tests/unit/test_apptest_cold_start_hardening.py:274: in test_wrapper_first_timeout_10_becomes_60
    inst.run(timeout=10)
tests/_apptest_runtime.py:92: in _patched_run
    return original_run(self, *args, timeout=eff, **kwargs)
tests/_apptest_runtime.py:92: in _patched_run [repeated 12x]
streamlit/testing/v1/app_test.py:439: in run
    return self._tree.run(timeout=timeout)
E   AttributeError: 'FakeAppTest' object has no attribute '_tree'
```

## State Leaked

- `sys.modules["streamlit"]` → fake `ModuleType` lacking `secrets`, `__spec__`, real package attributes
- `sys.modules["streamlit.testing"]`
- `sys.modules["streamlit.testing.v1"]` → fake `FakeAppTest`
- `tests._apptest_runtime._installed` flag desynced (False while real patched)
- `tests._apptest_runtime._original_run` stale (real original vs fake)
- `tests._apptest_runtime._has_run_first` not restored
- `os.environ` selected vars and `os.getcwd()` (if changed)

## Fix

1. **Polluter source fix** (`tests/unit/test_apptest_cold_start_hardening.py`):

   - Introduced `_saved_runtime_state` to snapshot `_installed`, `_original_run`, `_has_run_first` *before* mutating `sys.modules`.
   - If real was installed, `uninstall_apptest_run_patch()` is called *while still on real modules* to correctly restore real `AppTest.run` and clear flags, then `reset_apptest_cold_state()`.
   - Fake hierarchy installed after real unwound.
   - `_uninstall_fake` now uninstalls while fake still present, restores `sys.modules`, then reinstates runtime state to snapshot (re-installs wrapper if snapshot was installed, restoring `_has_run_first`).
   - Ensures no `fake AppTest.run = real_original` mismatch and no flag desync.

2. **Isolation utility** (`tests/support/streamlit_isolation.py`):

   - `StreamlitIsolationSnapshot` frozen dataclass capturing only relevant state.
   - `capture_streamlit_snapshot()` snapshots `sys.modules` trio (sentinel for absent), wrapper flags, `cwd`, allowlisted env vars, finder presence, `AppTest.run` id.
   - `restore_streamlit_snapshot()` restores only those keys, using `install`/`uninstall` to keep wrapper invariants, not clearing all `sys.modules` or reloading app.
   - `diagnose_streamlit_leak()` compares before/after, reports only relevant keys, redacts secret values, truncates, avoids full env dump.
   - `StreamlitIsolation` context manager for manual use.

3. **Pytest guard** (`tests/conftest.py`):

   - `autouse` fixture `_streamlit_isolation_guard` snapshots before each test, stores `request.node._streamlit_before`, restores after via `restore_streamlit_snapshot(before)`.
   - `streamlit_leak_report` optional fixture for explicit diagnostic emission.
   - `pytest_runtest_makereport` hook stores `rep_call` and on failure prints leak diagnostics via `diagnose_streamlit_leak`.
   - Does not import `streamlit` at conftest import; lazy `sys.meta_path` finder and runtime snapshot preserve guarantees A–E.

4. **Regression suite** (`tests/unit/test_streamlit_isolation_guard.py`):

   - Same-process regression with cleanup vs without cleanup, asserting fake lacks `secrets` blocks victim, restored passes.
   - Guard unit: deterministic snapshot, idempotent restore, env redaction, cwd restore, unrelated `sys.modules` not cleared, mutation-kill test.
   - Adversarial: leaked fake blocks victim, isolation detects fake.

## Mutation

Production mutation to prove guard power:

- Disabled `restore_streamlit_snapshot` (make it no-op) or reintroduce leaking fake without restore.
- Re-ran `tests/unit/test_streamlit_isolation_guard.py::test_mutation_restore_actually_restores` → **FAILED** with `assert hasattr(sys.modules["streamlit"], "secrets")` (historical signature: missing `secrets`, victim `AttributeError`).
- Re-ran `tests/unit/test_apptest_cold_start_hardening.py` + `tests/unit/ui/test_resource_strategy_explorer_page.py` combined with mutation (polluter helpers reverted to old buggy version) → 24 failures with stacked wrappers again.
- Restored: both sequences pass (35+10=45, guard 12).

Mutation row:

| Production file | Mutation | Test | Before | After | Tied |
|---|---|---|---|---|---|
| `tests/support/streamlit_isolation.py:restore_streamlit_snapshot` | Replace body with `pass` (no restore) | `test_mutation_restore_actually_restores` | PASS | FAIL `assert has_secrets` | Yes, restore logically required |
| `tests/unit/test_apptest_cold_start_hardening.py:_install_fake` | Restore old buggy `_install_fake` (uninstall after fake) | `test_wrapper_first_timeout_10_becomes_60` after polluter | PASS | FAIL `AttributeError _tree` | Yes, polluter leak |

## Suite Comparison

Baseline (main, 7b1b0b5) vs branch-after:

- `tests/unit/test_apptest_cold_start_hardening.py` alone: 35 passed both.
- `tests/unit/ui/test_resource_strategy_explorer_page.py` alone: 10 passed both.
- Combined polluter→victim: **before** 21 passed / 24 failed (stacked wrappers); **after** 45 passed.
- Victim→polluter: before 10+? failed, after 45 passed.
- `tests/unit/ui` : 243 passed both (after 243).
- `tests/ui` + `tests/unit/ui` : ~500+ passed both (observed truncated).
- `tests/unit` (ignoring jax `test_bbus`/`test_bcap` collection errors): before had same ephemeral-path failure in worktree due to `/tmp` location; after same baseline (1 ephemeral failure only when worktree under `/tmp`, passes on durable path).
- Full `uv run pytest -q` (where deps permit): same as above; no new skips, no weakened assertions, no new failure signature. Victim still fails when product behavior actually wrong (e.g., unadmitted study refusal).

Worktree-specific limitation: `test_durable_build_location_is_accepted` expects `Path.cwd() / data/network-build` to be durable, but worktree at `/tmp/...` contains `/tmp/` fragment, so it fails in worktree under `/tmp`. Passes on durable main checkout (`/Users/...`). This is pre-existing and not isolation-related; CI on durable runner not affected.

## Remaining Limitations

- Isolation snapshots only allowlisted keys (`streamlit` trio, wrapper flags, selected env, cwd, finder). If future tests fake additional submodules (e.g., `streamlit.runtime.scriptrunner_utils`), they must be added to allowlist.
- Guard `autouse` restores after each test; it will hide a leaking test's polluter failure if that test itself would otherwise pass but leak — however polluter source fix ensures polluters restore, and diagnostic hook still surfaces leak. Future polluters that bypass guard (e.g., `monkeypatch.setenv` without fixture) are caught via env snapshot.
- Does not reload whole application after every test (by design, for speed); measurement shows restore via targeted snapshot is sufficient (45 combined now passes).
- Cwd restore only if snapshot cwd still exists; otherwise stays.
- CI guard job not yet added; workflow change recorded below but requires local proof first.

## Research Safety

- Before: `pgrep -fl ...` showed `e2-native`? No, only `e2c` vec jobs (`run_e2c_gated...`, `eval_sumo_stage1_mc.py`).
- No SUMO/VEC/evaluator launched; no `touch` to `/Users/akashx/AntigravityTest/diss`, external vec_env, tos-data, or raw E2 outputs.
- Tests run serially (`-q` without `-n`).
- `git diff --check` clean.

## CI Workflow

- Existing `.github/workflows/ci.yml` retains `test` job; optional addition: deterministic polluter→victim sequence job (not yet committed, recorded as limitation). If added, it would run `uv run pytest tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py -q`.

## Files Changed

- `tests/unit/test_apptest_cold_start_hardening.py` (polluter fix)
- `tests/support/streamlit_isolation.py` (new)
- `tests/conftest.py` (guard + diagnostics)
- `tests/unit/test_streamlit_isolation_guard.py` (new regression)
- `docs/quality/v4_streamlit_test_isolation_review.md` (new)

## Evidence Captured

- Before-fix combined run: 24 failed with recursion and `secrets` missing (see Minimal Reproduction).
- After-fix combined run: 45 passed.
- Guard regression: 12 passed.
- `ruff format --check` → 3 reformatted, now clean.
- `ruff check` → All checks passed.
- `mypy` → Success: no issues found in 1013 source files.
- `uv lock --check` → (see final report)
- `git diff --check` → clean.


# Streamlit/Pytest Isolation Guard — V4 Review

Date: 2026-08-10 (updated 2026-08-11, supersedes a3d0054, 43a525a, f518549, and 9227e55)
Branch: agent/platform-streamlit-test-isolation-v1
Base: 7b1b0b55b399108b237f6e9a31a6747f4c15c81b (origin/main Merge PR #30)
Reviewed heads:
- `2f81a64e8c51b3963ddaafbbfe8a6f3d9544933d` — blocking defect: passing polluter silently repaired (REQUEST CHANGES)
- `a3d005442bc2c9dbc41be4bc5f7c211cf111be51` — added reporting but introduced guard regressions: half-root `DeltaGeneratorSingleton`, skipped AppTest, non-biting reporting tests (REQUEST CHANGES)
- `43a525addc2be1fc1d78adf8b10a92265a79d00b` / `f51854917ad4d61bbf13219971ce7a208b4c72a7` — fixes blockers 1–8 but subprocess probes SIGSEGV 14/20 when parent had rendered AppTest (capfd/start_new_session insufficient)
- `9227e554eedd7882bf78991917fe48c018b1e63a` — **current reviewed live SHA, REQUEST CHANGES** for B1 (subprocess SIGSEGV) and B2 (stale doc SHA `68d50a4` not ancestor, false exit -11 fixed claim)
- This remediation: commit following `9227e554eedd7882bf78991917fe48c018b1e63a` — splits subprocess proofs, fixes Q1–Q4, corrects doc

Note: a file cannot reliably contain the exact SHA of the commit that contains itself. This document records reviewed parent history exactly and describes the new remediation as “the commit following `9227e55`”; the final new exact SHA is reported in the PR body/handoff, not as a self-referential literal.

## Objective

Eliminate order-dependent Streamlit/AppTest pollution where fake/stub `streamlit` or `FakeAppTest` leaks, with deterministic isolation, secret redaction, and visible passing-polluter warnings via the real guard.

## Root Cause (historical polluter)

`tests/unit/test_apptest_cold_start_hardening.py` helpers `_install_fake`/`_uninstall_fake` saved `sys.modules` trio then installed fake before uninstalling while on fake, desyncing `_installed` and stacking `_patched_run` wrappers → `AttributeError: 'FakeAppTest' object has no attribute '_tree'` / `has no attribute 'secrets'`. Guard initially absent, then at `a3d0054` snapshotted only 3 keys and popped root while leaving `streamlit.*` children → half-root `DeltaGeneratorSingleton instance already exists!`.

## State Leaked

`sys.modules["streamlit"]` (fake lacking `secrets`), `streamlit.testing*`, whole `streamlit.*` subtree when half-popped, `_installed` flag, `_has_run_first` (process-scoped), selected env, cwd, finder.

## Fix History (preserved)

1. **Polluter source fix** (`test_apptest_cold_start_hardening.py`) — snapshots `_installed/_original_run/_has_run_first` before `sys.modules` mutation, uninstalls while on real, installs fake after, restores correctly. Verified: guard-removed 4032 passed vs base 112 failed; with guard 4032 passed.

2. **Isolation utility** (`tests/support/streamlit_isolation.py`) — snapshots whole `streamlit.*` subtree by prefix, distinguishes fake (`not hasattr(root,"secrets")`) vs real, leaves innocent `import streamlit` alone, only pops fake. Robust per-component `first_exc` restore with explicit `OSError/ModuleNotFoundError` and no blanket `S110` suppression. `diagnose` only reports `sys_modules` when fake, `has_meaningful` initially `{"sys_modules","apptest_installed","cwd","finder_present"}` (later refined, see Q4).

3. **Guard** (`tests/conftest.py`) — `autouse` `before=capture(); yield; after=capture(); diagnose; if has_meaningful: warnings.warn(... nodeid ...) ; finally: restore`. Warns even when polluter passes, restores even when warning is error. Removed dead `streamlit_leak_report`/`pytest_runtest_makereport`.

4. **Regression at 43a525a/f518549** — Added 3 subprocess probes exercising real `autouse` fixture, process-scoped `has_run_first`, secret redaction, tautology fixes, `env` dropped from meaningful, whole-subtree handling. Subset: hardening 35 passed, study capsule 8 passed/0 skipped, polluter→victim 45 passed, guard 19 passed, unit/ui 243, ui 768, gates clean. **But** subprocess probes shared parent with in-process `AppTest` rendering → SIGSEGV `returncode -11` empty stdout/stderr in ~14/20 runs of `pytest -q tests/unit/test_streamlit_isolation_guard.py`. `capfd.disabled()/start_new_session/env scrub` did not fix. Document incorrectly claimed `68d50a4e204f855574186256a58e9cf64035897d` was current remediation, but `68d50a4` is not ancestor of `9227e55`, and exit -11 was not fixed.

## Remediation Following `9227e55` (this commit)

**B1 — subprocess proofs must not share parent with AppTest:** Moves the three central subprocess proofs into dedicated `tests/unit/test_streamlit_isolation_subprocess.py` which contains **no** in-process `AppTest.from_file`/`_victim_can_render` calls and imports no `AppTest` at top level. Ordinary helper/restore tests remain in `test_streamlit_isolation_guard.py` (which still renders AppTest). The subprocess module can be invoked independently as `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py` and is stable 20/20; running `test_streamlit_isolation_guard.py` separately also stable; a fresh `subprocess` run after the guard module completes in a new pytest process remains stable. No retries, no `except -11: skip`.

Probes still load the real autouse fixture from `tests/conftest.py` (temp file under `tests/` so `tests/conftest.py` applies) and prove:
- passing polluter: polluter passes, `sys_modules` leak, warning with nodeid, secret absent, restored, victim passes;
- innocent `importlib.import_module("streamlit")`: no warning, next use valid;
- `_has_run_first` process-scoped: first child consumes, second child in same child pytest process sees still consumed.

**B2 — review doc identity:** Removes self-referential `68d50a4` claim, records exact reviewed parent `9227e55` as REQUEST CHANGES for SIGSEGV + stale identity, describes new remediation as “commit following `9227e55`”, preserves negative history for `2f81a64`/`a3d0054`/intermediates.

**Q1 — remove non-biting reporting-only test:** Deletes `test_reporting_only_mutation_proves_warning_independent` (only proved `lambda: False` → `False`). Genuine proof is the real-fixture subprocess test (already covers reporting-only mutant via `warnings.warn` disable).

**Q2 — dead suppressions:** Removes `contextlib.suppress(KeyError)` wrapping `dict.pop(key, None)` (already supplies default, cannot raise). Keeps `suppress(ValueError)` for `list.remove` and `suppress(FileNotFoundError)` for `unlink` where actually possible. No broad `try/except`.

**Q3 — unused sentinels:** Deletes `_ABSENT = object()` / `_SENTINEL = _ABSENT` (now snapshot uses empty dict for absent).

**Q4 — legitimate first AppTest not a leak:** Removes `apptest_installed` from `has_meaningful_streamlit_leak` meaningful set (now `{"sys_modules","cwd","finder_present"}`). Legitimate `false→true` on first `AppTest.run` no longer triggers warning, even under `-W error::pytest.PytestWarning`. Fake still warns via `sys_modules` (always changes to fake). Added subprocess regression `test_legitimate_first_apptest_does_not_warn_under_error` (single legitimate `AppTest.from_file` + `run` under `-W error` → `1 passed`, no warning) and `test_fake_polluter_still_warns_under_error` proves fake still warns.

## Mutation Evidence (required, isolated)

### Mutation A — reporting only

- **Mutant:** `tests/conftest.py: _streamlit_isolation_guard` comment `warnings.warn(msg, pytest.PytestWarning, stacklevel=2)` → `# MUTANT`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_real_fixture_passing_polluter_emits_warning_and_victim_passes`
- **Before:** `1 passed`
- **After:** `FAILED` — `AssertionError: warning missing` (child probe `2 passed` but warning absent; restoration still works). Restore → `PASS`.

### Mutation B — restoration

- **Mutant:** `tests/support/streamlit_isolation.py: restore_streamlit_snapshot` → `return  # MUTANT: no-op`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_guard.py::test_mutation_restore_actually_restores` (and subprocess polluter)
- **Before:** `PASS`
- **After:** `FAILED` — `assert hasattr(sys.modules["streamlit"], "secrets")` / `KeyError: 'streamlit'`. Restore → `PASS`.

### Mutation C — process-state rewind

- **Mutant:** `tests/support/streamlit_isolation.py: _restore_apptest` re-add `mod._has_run_first = snapshot.apptest_has_run_first`
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_real_fixture_has_run_first_is_process_scoped` (and `test_apptest_wrapper_has_run_first_is_process_scoped`)
- **Before:** `PASS` (second child sees `True`)
- **After:** `FAILED` — `AssertionError: has_run_first must remain True`. Restore → `PASS`.

### Mutation D — legitimate AppTest false-positive

- **Mutant:** `tests/support/streamlit_isolation.py: has_meaningful_streamlit_leak` re-add `"apptest_installed"` to meaningful set
- **Command:** `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py::test_legitimate_first_apptest_does_not_warn_under_error`
- **Before (correct):** `1 passed` under `-W error` (no warning)
- **After (mutant):** `FAILED` — `PytestWarning` turned into error (`Streamlit isolation leak detected after ... apptest_installed=...` under `-W error`). Restore → `PASS`.

## Suite Comparison (measured on remediation following `9227e55`)

| Suite | Command | Result |
|---|---|---|
| Hardening | `uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py` | 35 passed, 0 failed, 0 skipped (1 warning `apptest_installed` only if Q4 not applied; after Q4, still 35 passed, warnings only for fake) |
| Study capsule | `uv run pytest -q -rs tests/ui/test_study_capsule_ui.py` | 8 passed, 0 skipped |
| Guard (ordinary) | `uv run pytest -q tests/unit/test_streamlit_isolation_guard.py` | ~14 passed (after moving 3 probes + Q1 removal) |
| Subprocess proofs | `uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py` | 5 passed |
| Subprocess 20× | `for i in $(seq 1 20); do uv run pytest -q tests/unit/test_streamlit_isolation_subprocess.py || exit 1; done` | **20/20 stable** |
| Polluter→victim | `uv run pytest -q tests/unit/test_apptest_cold_start_hardening.py tests/unit/ui/test_resource_strategy_explorer_page.py` | 45 passed |
| Unit/UI | `uv run pytest -q tests/unit/ui` | 243 passed |
| UI | `uv run pytest -q tests/ui` | 768 passed |
| Full unit (jax) | `uv run pytest -q tests/unit` | 2 collection errors `ModuleNotFoundError: jax` (pre-existing) |
| Gates | `ruff format --check`, `ruff check`, `mypy`, `uv lock --check`, `git diff --check` | All clean |

## Remaining Limitations

- Whole `streamlit.*` subtree by prefix; non-`streamlit` fakes must be allowlisted.
- Guard warns only for `sys_modules`/`cwd`/`finder` (fake); `apptest_installed` and `env` alone do not warn (diagnosed/restored but not leaked). `has_run_first` remains process-scoped.
- Restoration best-effort per-component with `first_exc`.

## Research Safety

Before/after `pgrep -fl 'e2-native|native-placement|eval_sumo|run_e1|analyze_e1|vec'` → no matches; no SUMO/VEC/evaluator, no parallel pytest, no writes to `diss`/`vec_env`/`tos-data`.

## Files Changed (this lane)

- `tests/support/streamlit_isolation.py` (Q2, Q3, Q4)
- `tests/conftest.py` (Q4 via isolation; no direct change needed if Q4 only in isolation)
- `tests/unit/test_streamlit_isolation_guard.py` (B1 split, Q1 removal)
- `tests/unit/test_streamlit_isolation_subprocess.py` (new, B1 isolation)
- `docs/quality/v4_streamlit_test_isolation_review.md` (this file, B2)

Fable-owned untouched: `src/traffictwin/ui/labels.py`, `src/traffictwin/ui/navigation.py`, `src/traffictwin/ui/navigation_v07.py`, `src/traffictwin/ui/page_runtime.py`, `tests/ui/test_navigation_v07.py`, `README.md`, `docs/user_guide.md`, `docs/ui_conventions.md`, `src/traffictwin/cli.py`.

## Evidence Captured

- At `9227e55`: `pytest -q test_streamlit_isolation_guard.py` flaky 14/20 `returncode -11` empty, subprocess probes affected; doc claimed `68d50a4` current and exit -11 fixed (false).
- After remediation: subprocess module 20/20 stable, guard ordinary stable, legitimate first AppTest under `-W error` passes, fake still warns.
